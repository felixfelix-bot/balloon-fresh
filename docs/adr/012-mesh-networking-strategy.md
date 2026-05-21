# ADR 012: Mesh Networking Strategy — FIPS + MeshCore + TollGate + Nostr

## Status

Accepted

## Context

The mesh stack needs networking, community engagement, a business model, and async messaging for balloon-based internet transport. The original ROADMAP.md Phase 4 proposed custom mesh routing, but FIPS (Free Internetworking Peering System) already provides self-organizing mesh routing, Nostr-native identity, Noise encryption, and transport-agnostic framing — making a custom routing protocol unnecessary.

The NiceRF LoRa2021 module has two independent antenna ports: Sub-GHz (868 MHz, Pin 9) and 2.4 GHz (Pin 10). This allows dual-band operation on a single radio module, which is ideal for running two protocols simultaneously via time-division.

We have proven components from prior work: sx1280-serial provides TDMA coordinator election, fragmentation/reassembly (SLIP + CRC-32, 128-byte fragments), and secp256k1 crypto identity binding in Rust. The gap is erasure coding (Wirehair fountain codes), which has not yet been integrated with the fragmentation layer.

MeshCore (2.9k GitHub stars, active European community in UK/DE/Benelux) provides an established Sub-GHz LoRa mesh with geographic routing, repeater firmware, and coverage mapping tools (mapme.sh). Running MeshCore on the balloon's Sub-GHz band provides immediate community value: stratospheric coverage mapping and long-range message relay.

TollGate provides a Cashu-based payment protocol for selling network access. It runs at ground stations with WiFi captive portals. The esp32-tollgate implementation also includes a Nostr relay, enabling async messaging.

Nostr (NIP-01) events are small JSON documents with secp256k1 signatures. They fit naturally over LoRa links when kept short (~500 bytes for kind 0/1/7 events). A store-and-forward relay on the balloon allows disconnected ground stations to exchange messages through the balloon's flash buffer.

## Decision

Adopt a layered architecture using existing open-source components at each layer:

| Layer | Protocol | Role | Runs On |
|-------|----------|------|---------|
| L7 | TollGate + Nostr | Payment gating + async messaging | Ground station + balloon (store-and-forward) |
| L6 | FIPS Noise XK | End-to-end encrypted sessions | Balloon + ground station |
| L5 | FIPS mesh routing | Spanning-tree + bloom-filter discovery | Balloon + ground station |
| L4 | UDP/IP tunnel | Transport over FIPS mesh | Ground station (balloon is relay) |
| L3 | Erasure-coded fragmentation | Wirehair fountain codes + sx1280-serial fragmentation | Balloon + ground station |
| L2 | TDMA dual-band scheduler | Time-shares LR2021 between Sub-GHz and 2.4 GHz | Balloon |
| L1 | LR2021 radio | LoRa/FLRC dual-band | Balloon + ground station |

### Dual-Band Allocation

| Band | Frequency | Protocol | Pin | Antenna | Role |
|------|-----------|----------|-----|---------|------|
| Sub-GHz | 868 MHz | MeshCore (EU preset: SF8, BW62.5, CR8) | Pin 9 | Wire dipole (8.6 cm legs) | Community mesh repeater + coverage mapping |
| 2.4 GHz | 2.4 GHz | FIPS (LoRa/FLRC adaptive) | Pin 10 | Wire dipole (3.1 cm legs) | Mesh networking + Nostr transport + TollGate relay |

MeshCore on Sub-GHz is integrated from day one, sharing the TDMA scheduler with the 2.4 GHz FIPS transport.

### Nostr Strategy

- **Phase 2**: Nostr over FIPS over LoRa (simple path)
  - Short text events only (kind 0 metadata, kind 1 short text, kind 7 reactions)
  - Max ~500 bytes per event → fits in 4-8 LoRa fragments after erasure coding
  - Balloon stores events in SPIFFS/LittleFS FIFO buffer (~500 events = ~250 KB)
  - Ground station runs full Nostr relay with internet bridge
- **Phase 3+**: Expand to DMs, long-form content, zap receipts
- **Later**: Nostr over TollGate over FIPS over LoRa (adds payment gating)

### Ground Station Options

| Option | Hardware | Capabilities | Use Case |
|--------|----------|-------------|----------|
| Minimal | ESP32-C3 + LR2021 | FIPS leaf node + Nostr buffer, no TollGate | Remote deployments, low cost |
| Full | Raspberry Pi / SBC + LR2021 | Full FIPS daemon + strfry relay + tollgate-module-basic-go on OpenWRT + WiFi AP | Permanent installations with internet |

### Firmware Language

Deferred. Two paths documented:

- **C++ / ESP-IDF**: Consistent with tracker firmware (`tracker/firmware/`). RadioLib already integrated. Would need C++ FIPS leaf node implementation.
- **Rust / esp-rs**: Consistent with microfips, sx1280-serial, FIPS ecosystem. microfips already runs on ESP32-D0WD and ESP32-S3. Would need RISC-V (ESP32-C3) target support.
- **Hybrid**: Tracker in C++, mesh firmware in Rust. Shared telemetry component via C ABI.

Decision to be made during Phase 2 implementation based on microfips ESP32-C3 porting effort vs C++ FIPS leaf node effort.

## Existing Proven Components

| Component | Source | What It Provides |
|-----------|--------|-----------------|
| TDMA + coordinator election | `sx1280-serial` (Rust) | Proven: slot scheduling, peer warmup, crypto identity |
| Fragmentation + reassembly | `sx1280-serial` (Rust) | Proven: SLIP + CRC-32, 128-byte frags |
| FIPS mesh networking | `jmcorgan/fips` (Rust) | v0.3.0: spanning-tree routing, Noise IK/XK, Nostr identity |
| FIPS embedded leaf node | `Amperstrand/microfips` (Rust) | Runs on STM32 + ESP32 (D0WD, S3), no_std |
| MeshCore mesh protocol | `meshcore-dev/MeshCore` (C++) | 2.9k stars, repeater firmware, geographic routing, EU community |
| TollGate protocol | `OpenTollGate/tollgate` | TIP-01/02, HTTP-01, NOSTR-01, WIFI-01 specs |
| TollGate OpenWRT impl | `OpenTollGate/tollgate-module-basic-go` (Go) | Cashu payments, Nostr relay, WiFi captive portal |
| ESP32 TollGate + Nostr | `https://gitworkshop.dev/npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/git.orangesync.tech/esp32-tollgate` | ESP32 TollGate + integrated Nostr relay (our implementation) |
| LR2021 radio driver | RadioLib v7.6.0 (C++) | LoRa, FLRC, GFSK, RTToF ranging on LR2021 |
| Range test data | `sx1280-correlation-test` (nostr git) | 35k records, 30-37% delivery ratio at range |

## The Gap: Erasure Coding

Wirehair fountain codes are the missing piece. Without erasure coding:
- Every lost fragment requires ACK + retransmission (expensive at 300 km, 1 ms propagation)
- With 30-37% packet loss (measured), retransmission storms degrade throughput

With Wirehair:
- Transmitter generates infinite encoded fragments from k originals
- Receiver needs any k encoded fragments to decode (no specific fragment required)
- No ACK round-trip needed — balloon blasts encoded fragments in TDMA slot, goes back to sleep
- Transmit ~1.5x fragments for 35% loss (k=4 → send 6 encoded blocks)

Integration point: between sx1280-serial's fragmentation layer and the LoRa PHY. Fragment format becomes:
`[block_id (4B)] [seed/fragment_index (1B)] [k (1B)] [Wirehair-encoded payload]`

## Phased Approach

| Phase | Focus | Status |
|-------|-------|--------|
| **Phase 1** | Balloon tracker (single balloon, 28-byte telemetry, GPS) | **Done** — firmware v0.2, 17/17 tests pass |
| **Phase 2** | FIPS over LoRa + MeshCore repeater (bench + first dual-band flight) | Research |
| **Phase 3** | Nostr store-and-forward on balloon + TollGate at ground station | Not started |
| **Phase 4** | Multi-balloon mesh + full internet transport + MultiWAN | Not started |
| **Phase 5** | Multi-balloon reliability research | Not started (requires 3 successful Phase 2 flights) |

Phase 2 is the critical integration phase: port MeshCore to LR2021 Sub-GHz, implement FIPS Transport trait over LoRa with erasure coding, validate dual-band TDMA scheduler on the bench, then fly.

## Consequences

### Positive

- **No custom mesh routing**: FIPS provides production-quality spanning-tree routing with bloom-filter discovery
- **Community engagement from day one**: MeshCore's European user base gets stratospheric repeater coverage immediately
- **Async messaging**: Nostr store-and-forward enables disconnected ground stations to communicate through the balloon
- **Business model**: TollGate at ground stations provides Cashu-based pay-per-use internet access
- **Layered and testable**: Each layer can be validated independently (LoRa link → TDMA → FIPS transport → Nostr events)
- **Transport-agnostic FIPS**: Same mesh networking code works over LoRa, WiFi, BLE, serial — future-proof

### Negative

- **Complexity**: 7-layer stack with 4+ protocols (MeshCore, FIPS, Nostr, TollGate) is ambitious
- **Build system mismatch**: MeshCore is PlatformIO, tracker is ESP-IDF, FIPS is Cargo (Rust), TollGate is Go
- **RAM constraints**: ESP32-C3 has 400 KB RAM. FIPS Noise handshakes + Wirehair encode/decode + MeshCore routing + Nostr buffer is tight
- **MeshCore moving parts**: Porting MeshCore to LR2021 requires radio abstraction work (SX1262 → LR2021 via RadioLib)
- **No prior art**: Nobody has run FIPS over LoRa, or MeshCore from the stratosphere, or TollGate over a balloon relay

### Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| ESP32-C3 RAM insufficient for FIPS + Wirehair + MeshCore | Profile memory on bench first. Fallback: MeshCore on separate MCU, or use ESP32-S3 (more RAM) |
| MeshCore PlatformIO incompatible with our ESP-IDF build | Document both paths. Fallback: build MeshCore as separate PlatformIO firmware, flash alongside |
| Dual-band TDMA scheduler reduces per-band throughput | Accept reduced throughput. 2.4 GHz FIPS is primary link, Sub-GHz MeshCore is secondary/community |
| Wirehair too heavy for ESP32-C3 | Benchmark early. Fallback: simpler Reed-Solomon with fixed overhead |
| Nostr events too large for LoRa | Start with short text (~500 bytes). Reject oversized events. Compress with LZW (on FIPS roadmap) |

## Reference Repositories

| Repo | URL | Layer | Language |
|------|-----|-------|----------|
| FIPS | `https://github.com/jmcorgan/fips` | L5-6 | Rust |
| microfips | `https://github.com/Amperstrand/microfips` | L5-6 | Rust (no_std) |
| MeshCore | `https://github.com/meshcore-dev/MeshCore` | L1-3 | C++ |
| TollGate protocol | `https://github.com/OpenTollGate/tollgate` | L7 | Spec |
| TollGate OpenWRT | `https://github.com/OpenTollGate/tollgate-module-basic-go` | L7 | Go |
| ESP32 TollGate | `https://gitworkshop.dev/npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/git.orangesync.tech/esp32-tollgate` | L7 | C/C++ |
| sx1280-serial | `nostr://npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/relay.ngit.dev/sx1280-serial` | L2-3 | Rust |
| sx1280-ethernet-adapter | `nostr://npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/relay.ngit.dev/sx1280-ethernet-adapter` | L7 | Rust |
| sx1280-correlation-test | `nostr://npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/relay.ngit.dev/sx1280-correlation-test` | L1 | Rust |
| Wirehair | `https://github.com/catid/wirehair` | L3 | C |
| RadioLib | `https://github.com/jgromes/RadioLib` | L1 | C++ |
