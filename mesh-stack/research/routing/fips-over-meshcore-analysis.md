# FIPS-over-MeshCore Feasibility Analysis

**Date**: 2026-05-22
**Status**: Complete
**Decision**: Strategy A (side-by-side, dual-band)

## TL;DR

FIPS and MeshCore are architecturally incompatible at the routing layer (different identity systems, encryption, routing). Running FIPS *through* MeshCore is possible but awkward. The correct approach is **Strategy A**: run them side-by-side on separate LR2021 bands (Sub-GHz = MeshCore, 2.4 GHz = FIPS) with TDMA time-sharing. No integration needed.

## 1. Why "Hard If Not Impossible"

### 1.1 Double Encryption Overhead

MeshCore encrypts all payloads with AES-128 CTR + 2-byte MAC-then-Encrypt. FIPS adds ChaCha20-Poly1305 AEAD (16-byte tag). Nesting FIPS inside MeshCore means:

- MeshCore outer layer: AES-128 CTR + 2-byte MAC
- FIPS inner layer: ChaCha20-Poly1305 + Noise framing (~50 bytes overhead)
- Effective payload: 184 - 2 (MAC) - 16 (AEAD tag) - 32 (FMP framing) = **~134 bytes**

That's 27% wasted on redundant encryption.

### 1.2 Identity System Clash

| Aspect | MeshCore | FIPS |
|--------|----------|------|
| Curve | Ed25519 | secp256k1 |
| Key size | 32 bytes | 32 bytes |
| Identity hash | 1 byte (first byte of pubkey) | 16 bytes (SHA-256(pubkey)[:16]) |
| Key exchange | X25519 ECDH | Noise IK/XK |
| Signature | Ed25519 | Schnorr (BIP-340) |

MeshCore routes packets by 1-byte identity hash. FIPS routes by 16-byte node address. These are fundamentally incompatible — MeshCore cannot interpret FIPS routing headers.

### 1.3 RAW_CUSTOM Limitation

MeshCore's `PAYLOAD_TYPE_RAW_CUSTOM` (0x0F) is the natural tunnel for opaque FIPS frames. However, from `Mesh.cpp`:

```cpp
case PAYLOAD_TYPE_RAW_CUSTOM: {
  if (pkt->isRouteDirect() && !_tables->hasSeen(pkt)) {
    onRawDataRecv(pkt);
    //action = routeRecvPacket(pkt);    don't flood route these (yet)
  }
  break;
}
```

RAW_CUSTOM packets are **direct-routed only** — no flood discovery. This means:
- Can only send to pre-known neighbors (zero-hop)
- No multi-hop without manually establishing source routes first
- Path discovery requires a separate MeshCore session (TXT_MSG or ANON_REQ)

### 1.4 MTU Mismatch

| Constraint | Value |
|------------|-------|
| MeshCore MAX_PACKET_PAYLOAD | 184 bytes |
| MeshCore header + path overhead | 2-66 bytes |
| FIPS Noise IK MSG1 | 114 bytes (fits) |
| FIPS Noise IK MSG2 | 69 bytes (fits) |
| FIPS FMP data frame overhead | ~32 bytes |
| FIPS FSP session overhead | ~64 bytes additional |
| Effective FIPS payload (FMP only) | 184 - 32 = ~152 bytes |
| Effective FIPS payload (FMP + FSP) | 184 - 64 = ~120 bytes |

FITS for handshakes, but fragmentation is needed for any real data transfer.

### 1.5 CSMA vs TDMA Conflict

MeshCore uses CSMA with:
- RSSI-based channel activity detection before TX
- Random jittered retransmit delay
- 50% duty cycle management in 1-hour window
- Noise floor calibration every 2 seconds

Our FIPS design uses TDMA with:
- Fixed time slots (500 ms each)
- GPS PPS clock discipline
- Guaranteed airtime per slot
- No contention

Running FIPS handshakes through MeshCore's CSMA dispatcher means:
- 183-byte Noise IK handshake at SF8/BW62.5 = ~1.5s airtime
- MeshCore may delay or throttle the second message
- No guaranteed latency for time-critical FIPS operations

## 2. Integration Strategies

### Strategy A: Side-by-Side (Recommended)

```
LR2021 Radio Core (shared, time-division multiplexed)
├── Sub-GHz (868 MHz, Pin 9): MeshCore repeater
│   ├── Community mesh routing
│   ├── Coverage mapping
│   └── CSMA medium access
└── 2.4 GHz (Pin 10): FIPS transport
    ├── Noise IK/XK encrypted sessions
    ├── Nostr event relay
    └── TDMA scheduled slots
```

**TDMA frame** (2 seconds):
```
Slot 0: Sub-GHz RX (MeshCore)  500ms
Slot 1: 2.4 GHz TX (FIPS)      500ms
Slot 2: Sub-GHz RX (MeshCore)  500ms
Slot 3: 2.4 GHz RX (FIPS)      500ms
```

**Pros**: No protocol conflicts, each stack optimized for its band, clean separation.
**Cons**: Single radio core cannot RX on both bands simultaneously.
**Effort**: Already designed in INTEGRATION-ARCHITECTURE.md. Implementation is straightforward.

### Strategy B: FIPS as MeshCore RAW_CUSTOM Tunnel

Tunnel FIPS frames through MeshCore's `PAYLOAD_TYPE_RAW_CUSTOM` on Sub-GHz only.

**How**:
1. FIPS encrypts data → encrypted frame
2. `createRawData(frame, len)` → RAW_CUSTOM packet
3. `sendDirect()` or `sendZeroHop()` to known neighbor
4. Neighbor's `onRawDataRecv()` callback extracts FIPS frame
5. FIPS processes locally or re-wraps for next hop

**Limitations**:
- No flood routing (RAW_CUSTOM is direct-only)
- Must pre-establish routes via MeshCore path discovery
- ~134 bytes effective payload
- Single band only (Sub-GHz)
- MeshCore CSMA may throttle FIPS handshakes

**When useful**: Ground-station-to-ground-station tunneling via balloon relay on Sub-GHz when 2.4 GHz is unavailable.
**Effort**: 3-5 days.

### Strategy C: MeshCore Fork with FIPS Payload Type

Add `PAYLOAD_TYPE_FIPS` (0x0C, currently reserved) to MeshCore with:
- Flood routing enabled
- Custom dedup using FIPS `node_addr[:1]`
- Skip MeshCore encryption (FIPS has its own)
- Fragmentation-aware dispatch

**Pros**: Deep integration, single-band mesh with FIPS encryption.
**Cons**: Maintaining a fork, losing upstream compatibility, high complexity.
**Effort**: 2-3 weeks. Not recommended at this stage.

## 3. Strategy A Implementation Plan

### Component Dependency Graph

```
micro-ecc (secp256k1)  ──→ fips_transport (Noise IK + FMP)
                                    ↓
rweather/Crypto        ──→ meshcore_core (extracted)
                                    ↓
                            dual_band_radio (band switching)
                                    ↓
                            tdma_scheduler (already exists)
                                    ↓
                            app_main (integration)
```

### Phase 1: Foundation Components
- A7: micro-ecc ESP-IDF component (secp256k1 for FIPS)
- A6: rweather/Crypto port (Ed25519 + AES-128 for MeshCore)

### Phase 2: Core Protocol Implementations
- A2: MeshCore core extraction (framework-agnostic ~1,500 lines)
- A1: FIPS-over-LoRa C++ (Noise IK + FMP single-peer, ~500-800 lines)

### Phase 3: Integration
- A4: Dual-band radio abstraction (wraps RadioLib SX1262)
- A5: TDMA + radio integration (state machine)
- A8: Pipeline loss recovery (erasure decoder state machine)

### Phase 4: Bonus
- A9: RAW_CUSTOM tunnel (Strategy B, optional)

## 4. Technical Requirements

### FIPS-over-LoRa (A1) Dependencies

| Component | ESP-IDF Built-in? | Package |
|-----------|-------------------|---------|
| SHA-256 | Yes | `mbedtls/sha256.h` |
| HKDF-SHA256 | Yes | `mbedtls/hkdf.h` |
| ChaCha20-Poly1305 | Yes | `mbedtls/chachapoly.h` |
| secp256k1 ECDH | No | micro-ecc (~2 KB flash) |
| Random bytes | Yes | `esp_random()` |
| Total RAM | ~3-5 KB | ESP32-C3 has 400 KB SRAM |

### MeshCore Extraction (A2) Dependencies

| Component | ESP-IDF Built-in? | Package |
|-----------|-------------------|---------|
| Ed25519 | No | rweather/Crypto |
| X25519 ECDH | No | rweather/Crypto |
| AES-128 CTR | No | rweather/Crypto (or mbedtls) |
| SHA-256 | Yes | `mbedtls/sha256.h` |
| Total RAM | ~2-4 KB | For mesh state |

## 5. Performance Comparison

| Metric | Strategy A (Dual-Band) | Strategy B (RAW_CUSTOM) | Strategy C (Fork) |
|--------|----------------------|------------------------|-------------------|
| FIPS throughput | 9 kbps @ 300km (2.4 GHz) | ~1 kbps (Sub-GHz SF8) | ~1 kbps |
| MeshCore throughput | Native (Sub-GHz) | Shared with FIPS | Shared with FIPS |
| Max FIPS payload | ~158 bytes/frame | ~134 bytes/frame | ~152 bytes/frame |
| Multi-hop FIPS | Yes (FIPS routing) | Manual source routes | Yes (native) |
| Simultaneous mesh + FIPS | Yes (different bands) | No (same band) | No (same band) |
| Implementation effort | Low (separate stacks) | Medium (tunnel adapter) | High (fork) |
| Maintenance | Low (upstream MeshCore) | Low (minimal changes) | High (fork drift) |

## 6. Conclusion

Strategy A is the clear winner. The LR2021's dual-band capability makes separation natural:
- **Sub-GHz (868 MHz)**: Proven MeshCore community mesh, excellent propagation, hundreds of km range
- **2.4 GHz**: FIPS private mesh, higher data rates at shorter range, clean protocol design

The two networks share only the radio core (time-division) and the balloon platform (GPS, power, storage). No protocol-level integration needed.

Strategy B is a useful future addition for the specific case of tunneling FIPS through MeshCore when 2.4 GHz is unavailable, but should not be the primary architecture.

Strategy C is not recommended — the maintenance cost of a MeshCore fork outweighs the marginal benefit of single-band FIPS routing.
