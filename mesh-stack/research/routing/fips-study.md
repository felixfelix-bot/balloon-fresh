# FIPS + microfips Study for Balloon Integration

## 1. FIPS Architecture Overview

FIPS (Free Internetworking Peering System) is a self-organizing encrypted mesh network using Nostr identities (secp256k1 keypairs). It operates over arbitrary transports without central infrastructure.

### Protocol Layers

| Layer | Protocol | Encryption | Scope |
|-------|----------|------------|-------|
| Transport | UDP/TCP/Ethernet/Tor/BLE/serial | None | Raw datagram delivery |
| FMP (Mesh) | Noise IK | ChaCha20-Poly1305 | Hop-by-hop (each link) |
| FSP (Session) | Noise XK | ChaCha20-Poly1305 | End-to-end |
| Application | IPv6 TUN / native API | — | Unmodified IP apps or FIPS-native |

**Key design**: Two independent encryption layers. Every packet is encrypted twice: once at the link layer (FMP), once at the session layer (FSP). Intermediate nodes cannot read session payloads.

### Identity System

- **Keypair**: secp256k1 (Nostr standard)
- **node_addr**: `SHA-256(compressed_pubkey)[:16]` — routing identifier in packet headers
- **IPv6 address**: `fd00::/8` derived from node_addr — for TUN adapter
- **npub**: bech32-encoded pubkey — application-layer addressing

Intermediate nodes see only `node_addr` (16 bytes), not the full pubkey. This provides metadata protection.

### Routing

- **Spanning tree**: Distributed parent selection, gives every node a coordinate
- **Bloom filters**: Gossip-based reachability propagation, no global routing tables
- **Forwarding**: Local decisions using cached coordinates + peer bloom filters
- **Recovery**: Three error signals (CoordsRequired, PathBroken, MtuExceeded)

### FMP Frame Format

```
[4 bytes: prefix] [variable: payload]
Prefix: [version:4bits | phase:4bits] [flags:8] [payload_len:16 LE]
```

### FMP Noise IK Handshake (Link Layer)

Pattern: `Noise_IK_secp256k1_ChaChaPoly_SHA256`

```
<- s                    (responder's static key known)
-> e, es, s, ss         (MSG1: 106 bytes Noise payload)
<- e, ee, se            (MSG2: 57 bytes Noise payload)
```

Wire sizes:
- MSG1: 4 (prefix) + 4 (sender_idx) + 106 (noise) = **114 bytes**
- MSG2: 4 (prefix) + 4 (sender) + 4 (receiver) + 57 (noise) = **69 bytes**
- **Total handshake: 183 bytes**

After handshake, transport keys derived via `HKDF-SHA256(ck, &[])` → 64 bytes split into k_send and k_recv.

### FSP Noise XK Session (End-to-End)

3-message XK handshake for end-to-end sessions. Initiator knows responder's npub (pre-message). Responder learns initiator's identity from msg3 (identity protection). Session datagrams dispatched by index (O(1) lookup, WireGuard-inspired).

---

## 2. microfips Architecture Overview

microfips is a minimal FIPS leaf node proven on STM32F469I-DISCO and ESP32-D0WD. It implements the full FMP + FSP stack in `no_std` Rust.

### Crate Structure

| Crate | Role | std? |
|-------|------|------|
| `microfips-core` | Noise IK/XK, FMP, FSP, identity | `no_std` |
| `microfips-protocol` | Transport trait, framing, Node runtime | `no_std` |
| `microfips-service` | Request/response layer | transport-agnostic |
| `microfips-http-demo` | Optional HTTP adapter | optional |

### Transport Trait (Simple Interface)

The transport abstraction is minimal — any medium implementing these operations can carry FIPS traffic:

```
send(frame: &[u8]) -> Result<()>
recv() -> Result<Frame>
mtu() -> usize
```

Implemented transports: USB CDC, UART, BLE GATT, BLE L2CAP, WiFi UDP.

### Proven Capabilities

- Noise IK handshake with live FIPS VPS ✅
- FSP session protocol (XK handshake + encrypted data) ✅
- MCU-to-MCU FSP PING/PONG through FIPS ✅
- Sustained heartbeat exchange (70+ seconds) ✅
- ESP32 BLE L2CAP direct transport (no bridge) ✅
- 169 tests (90 core + 21 error injection + 22 compatibility + 17 wire format + 13 FSP + 6 FSP integration)

### ESP32 Support

- ESP32-D0WD (Xtensa LX6, 240 MHz) — proven with UART, BLE, WiFi
- ESP32-S3 (Xtensa LX7, 240 MHz) — WiFi verified (with issues)
- **No ESP32-C3 (RISC-V) support yet** — would need `esp-hal` RISC-V target

---

## 3. LoRa Transport Feasibility

### Handshake RTT Budget over LoRa

**Scenario**: Balloon ↔ Ground Station at 300 km, SF7/BW125, 868 MHz

| Step | Payload | ToA (ms) | Notes |
|------|---------|----------|-------|
| MSG1 → | 114 bytes | ~370 | e, es, s, ss |
| MSG2 ← | 69 bytes | ~250 | e, ee, se |
| **Total** | **183 bytes** | **~620 ms** | Plus processing time |

At SF7/BW125 (air rate ~5.5 kbps):
- Processing overhead: ~50 ms per side (secp256k1 point multiply on ESP32-C3 @ 80 MHz ≈ 30-50 ms)
- Propagation delay at 300 km: ~1 ms (negligible)
- **Total handshake time: ~750 ms**

**Verdict**: Feasible in a single 1-second TDMA slot, or across two 500-ms slots.

### FSP Session Establishment (3 round trips)

| Step | Messages | LoRa ToA | Cumulative |
|------|----------|----------|------------|
| RT 1 | XK msg1 → msg2 ← | ~620 ms | 620 ms |
| RT 2 | XK msg3 → ack ← | ~400 ms | 1020 ms |
| RT 3 | Data → ack ← | ~300 ms | 1320 ms |
| **Total** | | | **~1.3 seconds** |

At SF7, a full FSP session takes ~1.3 seconds. At SF9 (longer range), multiply by ~4x = ~5 seconds. At SF12, multiply by ~16x = ~21 seconds.

**Verdict**: Session establishment is practical at SF7-SF9. At SF12, use connectionless mode (single datagrams without FSP session).

### MTU Considerations

LoRa MTU depends on SF:
- SF7: ~222 bytes payload
- SF9: ~115 bytes
- SF12: ~51 bytes

FMP overhead per packet: 4 bytes prefix + 4 bytes receiver_idx + 8 bytes counter + 16 bytes AEAD tag = **32 bytes**
FSP overhead: additional ~32 bytes per session datagram

**Effective payload at SF7**: 222 - 32 (FMP) - 32 (FSP) = **~158 bytes per frame**

For 28-byte telemetry: fits easily in a single frame with room to spare.
For mesh payloads: need fragmentation for anything > 158 bytes (see our existing `frag/` component).

### RAM Requirements

| Component | RAM (est.) |
|-----------|------------|
| secp256k1 point multiply | ~2-4 KB (temporary) |
| Noise state (CK, h, keys) | ~256 bytes |
| FMP peer state (1 peer) | ~128 bytes |
| FSP session state (1 session) | ~256 bytes |
| Transport buffers (TX/RX) | ~512 bytes |
| **Total (single peer + single session)** | **~3-5 KB** |

ESP32-C3 has 400 KB SRAM. FIPS leaf node would use < 5 KB. Very feasible.

### Flash Requirements

microfips-core on STM32: ~100-150 KB flash (estimated from crate size).
ESP32-C3 has 4 MB flash. Plenty of room.

---

## 4. Integration Path: Three Options

### Option A: Port microfips-core to ESP32-C3 via esp-rs (Rust)

**Approach**: Use `esp-rs` toolchain to compile microfips-core for RISC-V, implement a LoRa transport using RadioLib's C API via FFI.

**Pros**:
- Reuses proven microfips-core (169 tests passing)
- Stays on the same Rust codebase as microfips
- FIPS identity, Noise, FMP, FSP all working

**Cons**:
- Requires esp-rs nightly toolchain (Rust on RISC-V ESP32-C3)
- RadioLib is C++ → needs C FFI wrapper → Rust FFI → complex interop
- Our tracker firmware is C++/ESP-IDF → two separate firmware images or hybrid
- esp-rs ecosystem less mature than ESP-IDF for RISC-V

**Effort**: 3-5 days (LoRa transport + RISC-V target + integration testing)

### Option B: Re-implement FMP/FSP in C++ for ESP-IDF

**Approach**: Extract the protocol logic from microfips-core and re-implement in C++ as ESP-IDF components. Use our existing RadioLib C++ integration.

**Pros**:
- Consistent with our C++/ESP-IDF tracker firmware
- Direct RadioLib integration (no FFI)
- Full ESP-IDF toolchain (stable, well-supported)
- Smaller binary than Rust equivalent

**Cons**:
- Duplicates microfips-core effort
- Need to implement Noise IK/XK from scratch in C++
- Need secp256k1 C library (e.g., micro-ecc or libsecp256k1)
- Higher risk of protocol bugs vs using proven Rust code

**Effort**: 5-10 days (Noise implementation + FMP/FSP + testing)

### Option C: Hybrid — C++ Tracker + Rust FIPS via Component

**Approach**: Build tracker in C++/ESP-IDF (current), add microfips-core as a pre-compiled Rust static library linked via ESP-IDF CMake.

**Pros**:
- Best of both worlds: proven Rust protocol + stable C++ RadioLib
- No code duplication
- Can share identity keys between tracker telemetry and FIPS mesh

**Cons**:
- Build complexity: Rust → static lib → ESP-IDF CMake linkage
- Debugging across Rust/C++ boundary is harder
- Two toolchains in CI

**Effort**: 4-7 days (Rust cross-compile + CMake integration + LoRa transport)

### Recommendation

**Start with Option B for the minimum viable FIPS-over-LoRa**:
1. Implement only FMP (Noise IK) + single-peer mode (no FSP, no routing, no transit)
2. Balloon is a leaf node — no need for spanning tree or bloom filters
3. Add FSP later when multi-hop relay is needed

The minimum viable subset:
- Noise IK handshake (2 messages, 183 bytes)
- ESTABLISHED state: encrypted heartbeat + data frames
- Single peer (ground station)
- LoRa transport: TX/RX using RadioLib

This is ~500-800 lines of C++ including Noise handshake, AEAD, and framing.

---

## 5. LoRa Transport Design for FIPS

### Frame Mapping

```
FIPS Frame:    [prefix(4)] [payload]
LoRa Payload:  [FIPS Frame]
RadioLib TX:   radio.transmit(loRa_payload, length)
RadioLib RX:   radio.receive(loRa_buffer, &length)
```

The LoRa transport implements the same interface as microfips transports:
- `send(frame)`: Buffer frame, TX in next available slot
- `recv()`: RX buffer, return decoded frame
- `mtu()`: Return current LoRa MTU based on SF

### TDMA Integration

- Balloon has dedicated TX slot (sends FMP heartbeat + data)
- Ground station has dedicated RX + response slot
- Link establishment during balloon's first TX after wake
- Heartbeat every wake cycle (replaces FIPS's 10-second heartbeat with our deep-sleep cycle)

### Bandwidth Usage

| Mode | Interval | Bytes/cycle | Effective rate |
|------|----------|-------------|----------------|
| Tracker telemetry | 120s | 28 + 32 overhead = 60 | 4 bps |
| FMP heartbeat only | 120s | 32 (ESTABLISHED) | 2.1 bps |
| FMP + FSP data | 120s | 60 + 158 payload = 218 | 14.5 bps |
| Mesh V1 continuous | 1s TDMA | 218/s | 1.74 kbps |

---

## 6. Comparison with microfips ESP32 Support

| Feature | microfips (ESP32-D0WD) | Our Balloon (ESP32-C3) |
|---------|----------------------|----------------------|
| MCU | Xtensa LX6, 240 MHz | RISC-V RV32IMC, 160/80 MHz |
| Framework | esp-rs (Rust) | ESP-IDF (C++) |
| Radio | None (serial/BLE/WiFi) | LR2021 LoRa (RadioLib) |
| FIPS version | Full FMP + FSP | FMP-only (initially) |
| Identity | Deterministic test keys | Per-device key generation |
| Transport | UART / BLE / WiFi | LoRa (new transport) |
| Role | Leaf only | Leaf only (no transit) |

The key difference is the **LoRa transport** — neither FIPS nor microfips has a LoRa transport. We would be the first to implement FIPS-over-LoRa.

---

## 7. Implementation Priority

### Phase 1: Minimum Viable FIPS-over-LoRa (Tracker)

1. Noise IK handshake in C++ (~200 lines)
2. FMP framing: MSG1, MSG2, ESTABLISHED (~150 lines)
3. ChaCha20-Poly1305 AEAD (~100 lines using mbedtls, built into ESP-IDF)
4. LoRa transport adapter (~100 lines wrapping RadioLib)
5. Single-peer mode: ground station only

**Estimated total**: ~550-800 lines of C++
**Estimated effort**: 3-5 days

### Phase 2: FSP Session + Mesh Relay

1. Noise XK session handshake
2. Session datagram dispatch
3. Spanning tree + bloom filter (if multi-hop needed)
4. TDMA dual-band integration

### Phase 3: Full Integration

1. FIPS identity shared with tracker telemetry (same Nostr keypair)
2. Nostr event store-over-FIPS
3. TollGround station integration

---

## 8. Key Dependencies for C++ Implementation

| Component | ESP-IDF Built-in? | Alternative |
|-----------|-------------------|-------------|
| SHA-256 | ✅ `mbedtls/sha256.h` | — |
| secp256k1 ECDH | ❌ | `micro-ecc` (2 KB) or `libsecp256k1` (90 KB) |
| ChaCha20-Poly1305 | ✅ `mbedtls/chachapoly.h` | — |
| HKDF-SHA256 | ✅ `mbedtls/hkdf.h` | — |
| Random bytes | ✅ `esp_random()` | — |

**Recommendation**: Use `micro-ecc` for secp256k1 (compact, well-tested, ~2 KB flash). ESP-IDF's mbedtls provides everything else.

---

## 9. References

- FIPS repo: https://github.com/jmcorgan/fips
- FIPS concepts: https://github.com/jmcorgan/fips/blob/master/docs/design/fips-concepts.md
- FIPS architecture: https://github.com/jmcorgan/fips/blob/master/docs/design/fips-architecture.md
- microfips repo: https://github.com/Amperstrand/microfips
- microfips architecture: https://github.com/Amperstrand/microfips/blob/main/docs/architecture.md
- Noise Protocol Framework: https://noiseprotocol.org/
- Nostr NIPs: https://github.com/nostr-protocol/nips
