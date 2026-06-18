# Mesh Stack — DIY Open-Source Mesh Internet Transport

## Vision

A network of stratospheric pico balloons acting as mesh relay nodes, connecting multiple ground stations with internet backhaul. UDP transport with erasure-coded reliability. 2.4 GHz primary link (LR2021), Sub-GHz fallback. MultiWAN bonding across multiple balloon paths for aggregate throughput.

This is **not** a competitor to Starlink (50-350 Mbps via 12 GHz Ku/Ka-band phased arrays + thousands of LEO satellites). Realistic targets are **1-130 kbps per link**, aggregate **4-520 kbps** with 4 balloons bonded. Usable for messaging, small images, sensor data, emergency communication where no other connectivity exists.

## Layered Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Application Layer                                       │
│  Internet transport: IP tunnel / SOCKS / transparent     │
│  proxy. MultiWAN bonding across balloon paths.           │
├─────────────────────────────────────────────────────────┤
│  Transport Layer                                         │
│  UDP datagrams. NO TCP — RTT too high for TCP congestion │
│  control. Reliability from erasure coding below.         │
├─────────────────────────────────────────────────────────┤
│  Network Layer                                           │
│  Mesh routing between balloons. Erasure-coded            │
│  fragmentation (fountain codes). Fragment reassembly.    │
├─────────────────────────────────────────────────────────┤
│  Link Layer                                              │
│  TDMA with coordinator election. Contention windows for  │
│  new node join. Dynamic slot leases. Clock sync via      │
│  GPS PPS (balloons) + ranging (ground stations).         │
├─────────────────────────────────────────────────────────┤
│  Physical Layer                                          │
│  LR2021 2.4 GHz (FLRC high-rate / LoRa long-range)       │
│  LR2021 Sub-GHz (868 MHz LoRa, fallback)                 │
│  Hardware FEC built into LoRa/FLRC modem.                │
└─────────────────────────────────────────────────────────┘
```

## Reference Repositories by Layer

### Physical Layer

| Repo | URL | Notes |
|------|-----|-------|
| RadioLib | `https://github.com/jgromes/RadioLib` | Our RF driver. Supports LR2021 LoRa, FLRC, RTToF ranging. v7.6.0 in use. |
| Semtech USP | `https://github.com/Lora-net/usp` | Official Semtech Unified Software Platform for LR2022/SX1280. Reference for register-level control. |
| Poucet_LCIS_LoRa24 | `https://github.com/Hedwyn/Poucet_LCIS_LoRa24` | SX1280 ranging PHY config. Tip: use 1600 kHz BW for ranging accuracy. |

### Link Layer — TDMA

| Repo | URL | Notes |
|------|-----|-------|
| ts-lora | `https://github.com/deltazita/ts-lora` | Time-slotted LoRa framework. TDMA frame structure, slot scheduling, guard bands. |
| LoRaMesher | `https://github.com/LoRaMesher/LoRaMesher` | TDMA superframes, distributed nodes, deterministic role changes, mesh routing. |
| sx1280-serial | `nostr://npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/relay.ngit.dev/sx1280-serial` | Our proven TDMA + coordinator election (Rust). Fragmentation, reassembly, peer warmup, crypto identity. Most mature of our repos. |

### Link Layer — Clock Sync

| Repo | URL | Notes |
|------|-----|-------|
| LoraRangingTest | `https://github.com/yplam/LoraRangingTest` | SX1280 ranging on STM32/mbed. Bare-metal ranging implementation for clock calibration. |
| ublox-GNSS-Arduino | `https://github.com/u-blox/ublox-GNSS-Arduino-Library` | u-blox GPS library. PPS config, airborne mode (UBX-CFG-NAV5 dynamic model 6/7). |
| Poucet_LCIS_LoRa24 | `https://github.com/Hedwyn/Poucet_LCIS_LoRa24` | Ranging PHY optimization (see above). |

### Network Layer — Erasure Coding

| Repo | URL | Notes |
|------|-----|-------|
| Wirehair | `https://github.com/catid/wirehair` | **Primary candidate.** Fountain code library in C. O(N) performance, zero deps. Best fit for embedded. |
| Shorthair | `https://github.com/catid/shorthair` | Streaming erasure codes by same author. UDP-oriented, fixed overhead per generation. |
| OpenFEC | `https://github.com/OpenFEC/OpenFEC` | Academic-grade multi-algorithm: Reed-Solomon, LDPC-Staircase, LT codes, Raptor. Heavier but useful for comparison. |

### Network Layer — Ground Station Tools

| Repo | URL | Notes |
|------|-----|-------|
| pywirehair | `https://github.com/sz3/pywirehair` | Python wrapper for Wirehair. Ground station decode. |
| pyeclib | `https://github.com/openstack/pyeclib` | Python erasure coding with Intel ISA-L backend. |
| ErasureCodes | `https://github.com/ianopolous/ErasureCodes` | JavaScript Reed-Solomon for web UI monitoring. |

### Testing & Methodology (Our Repos)

| Repo | URL | Notes |
|------|-----|-------|
| sx1280-correlation-test | `nostr://npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/relay.ngit.dev/sx1280-correlation-test` | Field-tested range testing. 35k CSV records, 30-37% delivery ratio. Deterministic payload + correlation methodology. |
| sx1280-testing | `nostr://npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/relay.ngit.dev/sx1280-testing` | Basic bring-up, ~1 kbps throughput benchmark. |
| sx1280-ethernet-adapter | `nostr://npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/relay.ngit.dev/sx1280-ethernet-adapter` | ESP32-S3 + SX1280 Wi-Fi AP bridge scaffold. Architecture closest to what ground station could look like. |

### Mesh Networking (FIPS + MeshCore + TollGate)

| Repo | URL | Notes |
|------|-----|-------|
| FIPS | `https://github.com/jmcorgan/fips` | Free Internetworking Peering System. Self-organizing encrypted mesh, Nostr identity, Noise IK/XK, v0.3.0. |
| microfips | `https://github.com/Amperstrand/microfips` | FIPS leaf node on STM32 + ESP32 (D0WD, S3). Rust/no_std. Transport trait, Noise handshakes, FSP sessions. |
| MeshCore | `https://github.com/meshcore-dev/MeshCore` | Lightweight LoRa mesh protocol. 2.9k stars. Repeater firmware, geographic routing, EU community (UK/DE/Benelux). |
| TollGate protocol | `https://github.com/OpenTollGate/tollgate` | Payment protocol spec (TIP-01/02, HTTP-01, NOSTR-01, WIFI-01). Cashu ecash for network access. |
| TollGate OpenWRT | `https://github.com/OpenTollGate/tollgate-module-basic-go` | Reference TollGate implementation. Go. Cashu payments, Nostr relay, WiFi captive portal on OpenWRT. |
| ESP32 TollGate + Nostr | `https://gitworkshop.dev/npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/git.orangesync.tech/esp32-tollgate` | ESP32 TollGate + integrated Nostr relay (our implementation) |
| strfry | `https://github.com/hoytech/strfry` | Efficient Nostr relay in C++. For ground station deployment. |

### External References (not GitHub)

| Resource | URL | Notes |
|----------|-----|-------|
| Stuart's Balloon Tracker | `https://StuartsProjects.com` | Real SX1280 balloon tracker. Ranging calibration data at 40-85 km. High-altitude GPS + antenna weight data. |
| Semtech Advanced Ranging | Semtech docs site | Theory of SX1280 ranging engine. |
| "Damn Cool Algorithms: Fountain Codes" | `https://blog.notdot.net/2012/01/Damn-Cool-Algorithms-Fountain-Codes` | Excellent Fountain Code explainer. |

## How Erasure Coding Transforms the Architecture

Without erasure coding, every lost fragment requires a retransmission ACK round-trip:

```
Node TX: [frag0] [frag1] [frag2] [frag3]
                              ↑ LOST
Ground:  "I got 0,1,3 but not 2 — please retransmit 2"
Node TX:  .............. [frag2 retransmit]
                                  ↑ LOST AGAIN
Ground:  "Still don't have 2..."
```

With fountain codes (Wirehair), the transmitter generates an infinite stream of encoded fragments. The receiver needs ANY k fragments to decode:

```
Node TX: [E0] [E1] [E2] [E3] [E4] [E5]   ← 6 encoded from 4 original
                        ↑ LOST      ↑ LOST
Ground:  "I got E0,E1,E3,E5 — that's 4 (=k). DECODE SUCCESS."
```

**Why this matters for balloons:**
1. **No ACK round-trip** — balloon blasts encoded fragments in its TDMA slot, goes back to sleep
2. **Works with 30-37% packet loss** — exactly what `sx1280-correlation-test` measured in field tests
3. **Predictive leases** — if loss is ~35%, transmit ~1.5x fragments (k=4 → send 6 encoded blocks)
4. **Eliminates TCP need** — reliability at network layer, UDP above

## Clock Synchronization Options

| Approach | Accuracy | Weight Added | Complexity | Requires Ground Contact? |
|----------|----------|-------------|------------|-------------------------|
| Free-running (no sync) | Seconds/day drift | 0g | Useless for TDMA | N/A |
| TCXO only | ±0.5 ppm (~seconds/week) | ~0g (on-chip) | Moderate | No |
| RTToF ranging sync | ±microseconds | 0g | Complex | Yes — needs 2-way ranging exchange |
| GPS PPS (u-blox MAX-M10S) | ±nanoseconds | ~0.6g bare, ~2g with antenna | Simple | No — self-synchronized |

**Recommended for balloons:** GPS PPS discipline with u-blox MAX-M10S (0.6g bare). Provides stratum-1 clock, PPS hardware interrupt for TDMA slot boundaries, position data for routing. Must configure Airborne <1G mode (UBX-CFG-NAV5 dynamic model 6) to bypass COCOM 18km altitude limit. Supports up to 80,000m.

**Recommended for ground stations without GPS:** RTToF ranging sync. Ground station initiates ranging with balloon, gets distance + propagation delay, balloon injects GPS-corrected time.

## Cold-Start Sync Protocol (Ranging-Based)

For nodes without GPS (ground stations, or balloons recovering from long offline):

```
[ Node (no GPS) ]                           [ Balloon (GPS PPS) ]
      |                                              |
      | -- (1) Broadcast: "I am Node X, need sync" ->|
      |                                              |
      | <- (2) SX1280/LR2021 RTToF Ranging -------- |  Measures ToF
      |                                              |  (exact distance)
      |                                              |
      | <- (3) Data: [GPS_UTC_Time + ToF_Delay] ---- |
      |                                              |
 [Calibrate local clock]                             |
 [Enter TDMA frame clock]                            |
```

Software drift tracking maintains accuracy between sync events:
- `master_time = offset + local_ticks * drift_rate`
- `drift_rate` updated from two sequential sync measurements 60s apart
- Guard bands auto-expand based on time since last sync

## Throughput Estimates

| Mode | Frequency | Modulation | Data Rate | Range | Use Case |
|------|-----------|-----------|-----------|-------|----------|
| LoRa SF12 / 125 kHz | 868 MHz | LoRa | ~0.25 kbps | ~480 km | Maximum range emergency |
| LoRa SF9 / 125 kHz | 868 MHz | LoRa | ~1.7 kbps | ~300 km | Current tracker design |
| LoRa SF10 / 1625 kHz | 2.4 GHz | LoRa | ~12 kbps | ~50 km | Primary mesh link |
| LoRa SF9 / 1625 kHz | 2.4 GHz | LoRa | ~22 kbps | ~40 km | Balanced mesh link |
| FLRC / 1625 kHz | 2.4 GHz | FLRC | ~130 kbps | ~20 km | High-rate short-range |

**MultiWAN bonding estimate:** 4 balloons at FLRC 130 kbps each = ~520 kbps aggregate (before erasure coding overhead). With 1.5x erasure overhead for 35% loss: ~350 kbps net.

**Note:** These are air data rates. Actual throughput depends on TDMA overhead, guard bands, contention windows, erasure coding overhead, and protocol headers. Expect 50-70% of air data rate as net throughput.

**SX1280 USB dongle bottleneck:** The Ebyte E28-2G4T27SX USB dev boards use a CH341 USB-serial chip that bottlenecks throughput at ~9600-115200 baud serial. The dongles are useful for range testing and protocol prototyping but **cannot** measure actual radio throughput. Our LR2021 on ESP32-C3 with direct SPI does not have this bottleneck.

## Relationship to Existing Work

See also: `docs/adr/012-mesh-networking-strategy.md` (strategic decisions) and `mesh-stack/INTEGRATION-ARCHITECTURE.md` (detailed technical architecture).

### What We Already Have

| Component | Source | Status |
|-----------|--------|--------|
| LR2021 RadioLib driver | `tracker/firmware/` (C++) | Working, builds v0.2 |
| ESP32-C3 HAL for RadioLib | `tracker/firmware/main/EspHalC3.h` | Working |
| TDMA + coordinator election | `sx1280-serial` (Rust) | Proven, needs port to C++ or esp-rs |
| Fragmentation + reassembly | `sx1280-serial` (Rust) | Proven: SLIP + CRC-32 + 128-byte frags |
| Crypto identity binding | `sx1280-serial` (Rust) | Proven: secp256k1 Schnorr signatures |
| Range testing methodology | `sx1280-correlation-test` | 35k records, deterministic payloads, 30-37% loss |
| Hardware debug ladder (L0→L3) | `sx1280-serial` feature branch | Proven methodology |
| Wi-Fi AP + HTTP status | `sx1280-ethernet-adapter` | Scaffold only (Rust/ESP-IDF) |
| PCB design for balloon | `tracker/hardware/` | In progress (KiCad) |
| FIPS mesh networking | `github.com/jmcorgan/fips` (Rust) | v0.3.0: spanning-tree, Noise IK/XK, Nostr identity |
| FIPS embedded leaf node | `github.com/Amperstrand/microfips` (Rust/no_std) | Runs on STM32 + ESP32 (D0WD, S3) |
| MeshCore mesh protocol | `github.com/meshcore-dev/MeshCore` (C++) | 2.9k stars, repeater firmware, EU community |
| MeshCore LR2021 variant | `mesh-stack/meshcore-lr2021/` (C++) | 9 files, radio init verified on hardware |
| TollGate protocol | `github.com/OpenTollGate/tollgate` | TIP-01/02 specs, Cashu ecash payments |
| TollGate OpenWRT impl | `github.com/OpenTollGate/tollgate-module-basic-go` (Go) | Cashu, Nostr relay, WiFi captive portal |
| ESP32 TollGate + Nostr relay | `https://gitworkshop.dev/npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/git.orangesync.tech/esp32-tollgate` | ESP32 TollGate + integrated Nostr relay (our implementation) |
| GPS NMEA parser | `tracker/firmware/components/gps/` (C) | Working: GGA/RMC, sleep/wakeup |
| Telemetry packet (28 bytes) | `tracker/firmware/components/telemetry/` (C) | Working: CRC-16, 17/17 tests pass |

### What's New (Not in Any Existing Repo)

| Component | Library | Notes |
|-----------|---------|-------|
| Erasure/fountain coding | `github.com/catid/wirehair` | Critical gap — not yet integrated with sx1280-serial fragmentation |
| Wirehair + sx1280-serial integration | Custom | Erasure encoding layer between fragmentation and LoRa PHY |
| FIPS Transport trait for LoRa | Custom | Implement FIPS `Transport` over LoRa using sx1280-serial + Wirehair |
| MeshCore LR2021 radio wrapper | Custom | Port MeshCore's `RadioLibWrapper` to LR2021 Sub-GHz via RadioLib |
| Cluster-aware stratorelay | Custom | StratoRelayMesh: union-find clustering + bloom filter filtering + cluster head bridging |
| Balloon telemetry over MeshCore | Custom | GPS adverts + chat telemetry + on-demand REQ/RESP |
| MeshCore core extraction to ESP-IDF | Custom | ~1,500 lines framework-agnostic C++ for single MCU flight firmware |
| Dual-band TDMA scheduler | Custom | Time-shares LR2021 between Sub-GHz (MeshCore) and 2.4 GHz (FIPS) |
| Nostr-over-FIPS protocol | Custom | Simplified NIP-01 over FIPS encrypted sessions, store-and-forward |
| microfips ESP32-C3 (RISC-V) port | `github.com/Amperstrand/microfips` | Currently tested on Xtensa (ESP32-D0WD/S3), needs RISC-V target |
| Clock sync protocol | Custom + RadioLib ranging | New protocol design |
| GPS PPS discipline | `github.com/u-blox/ublox-GNSS-Arduino-Library` | New hardware component |
| MultiWAN bonding | Custom | New capability |
| UDP/IP transport over FIPS | Custom | FIPS provides mesh routing, we add IP tunneling |

## Phased Roadmap

### Phase 1: Balloon Tracker (Current Scope — `tracker/`)
- 1 balloon, 1 ground station
- 868 MHz LoRa telemetry (28 bytes, CRC-16, GPS)
- No mesh, no TDMA, no erasure coding
- **Status: Done** — firmware v0.2, 17/17 tests pass, ADR-011 first flight strategy

### Phase 2: FIPS + MeshCore Dual-Band Flight (`mesh-stack/`)
- Implement FIPS `Transport` trait over LoRa (sx1280-serial fragmentation + Wirehair erasure coding)
- Port MeshCore repeater firmware to LR2021 Sub-GHz (868 MHz, SF8/BW62.5/CR8)
- **MeshCore LR2021 bench test**: PlatformIO build, 2-node test, community mesh test
- **MeshCore core extraction to ESP-IDF**: Single MCU flight firmware (`tracker/firmware/components/meshcore/`)
- **Cluster-aware stratorelay**: `StratoRelayMesh` with union-find clustering + bloom filter membership
  - Ground nodes remain stock — all intelligence on balloon
  - Only bridge between cluster heads, prevent flood storms
  - See `docs/adr/013-cluster-aware-stratorelay.md`
- **Balloon telemetry over MeshCore**: GPS adverts + chat telemetry + on-demand queries
- Implement dual-band TDMA scheduler (Sub-GHz MeshCore + 2.4 GHz FIPS)
- GPS PPS discipline for TDMA slot boundaries
- RTToF ranging for clock sync via RadioLib
- Bench validation: dual-band operation, FIPS handshake over LoRa, MeshCore advert reception
- First dual-band flight: MeshCore stratospheric repeater + FIPS mesh node
- Coverage mapping: MeshCore advert log → mapme.sh data
- **Upstream PRs**: (1) LR2021 variant to MeshCore, (2) StratoRelayMesh example
- **Status: Radio verified** — MeshCore LR2021 radio init verified on hardware (ESP-IDF HAL). Companion running on ESP32-C3 SuperMini. Next: Berlin community test, repeater build, upstream PR. See `mesh-stack/meshcore-lr2021/README.md` test plan.

### Phase 3: Nostr Store-and-Forward + Ground Station (`mesh-stack/`)
- Implement Nostr-over-FIPS protocol (simplified NIP-01 over FIPS encrypted sessions)
- Balloon store-and-forward: SPIFFS/LittleFS FIFO buffer (~2000 events)
- Short text events only (kind 0/1/7, ~500 bytes max)
- Ground station Nostr relay bridge (strfry or esp32-tollgate relay)
- Two ground station options: minimal (ESP32-C3) or full (Raspberry Pi + TollGate)
- TollGate at full ground station: tollgate-module-basic-go on OpenWRT, Cashu WiFi captive portal
- **Status: Not started**

### Phase 4: Multi-Balloon Mesh + Internet Transport (`mesh-stack/`)
- FIPS mesh routing between multiple balloons (spanning-tree, bloom-filter discovery)
- MultiWAN bonding across balloon paths for aggregate throughput
- IP tunneling over FIPS mesh (UDP transport)
- Full internet transport: user → LoRa → balloon mesh → ground station → internet
- TollGate payment gating on all ground stations
- Expand Nostr: DMs, long-form content, zap receipts
- **Status: Not started**

### Phase 5: Multi-Balloon Reliability Research
- Prerequisites: 3+ successful Phase 2 flights
- Multi-balloon configurations (cut-down, redundant lift)
- Long-duration flight reliability
- See `mesh-stack/ROADMAP.md` Phase 5 section
- **Status: Not started**

---

## Research Checklist

### Step 1: Erasure Coding
- [ ] Clone `https://github.com/catid/wirehair` — study API, encoder/decoder init, memory usage
- [ ] Determine ESP32-C3 feasibility: 400KB RAM, 160MHz RISC-V — can Wirehair run?
- [ ] Benchmark: What's the maximum block size that fits in ESP32-C3 RAM?
- [ ] Clone `https://github.com/catid/shorthair` — study streaming variant, compare with Wirehair
- [ ] Clone `https://github.com/OpenFEC/OpenFEC` — compare algorithms (LT vs Raptor vs RS vs LDPC)
- [ ] Design fragment header format: `block_id` (4 bytes) + `seed/fragment_index` (1 byte) + `k` (1 byte) + payload
- [ ] Write findings to `mesh-stack/research/erasure-coding/notes.md`

### Step 2: TDMA
- [ ] Clone `https://github.com/deltazita/ts-lora` — study TDMA frame structure, slot scheduling
- [ ] Clone `https://github.com/LoRaMesher/LoRaMesher` — study mesh superframes, node discovery, routing
- [ ] Review `sx1280-serial` TDMA design (`src/link/tdma.rs`, `coord.rs`) — our proven approach
- [ ] Design TDMA frame: epoch structure, contention window size, slot duration, guard bands
- [ ] Determine: Is ts-lora, LoRaMesher, or our sx1280-serial design the best starting point?
- [ ] Write findings to `mesh-stack/research/tdma/notes.md`

### Step 3: Clock Sync
- [ ] Clone `https://github.com/yplam/LoraRangingTest` — study SX1280 ranging implementation
- [ ] Clone `https://github.com/Hedwyn/Poucet_LCIS_LoRa24` — study ranging PHY optimization (1600 kHz BW)
- [ ] Clone `https://github.com/u-blox/ublox-GNSS-Arduino-Library` — study PPS config, airborne mode API
- [ ] Verify: Does LR2021 support the same ranging engine as SX1280, or is it RTToF-only?
- [ ] Verify: What's the ranging accuracy of LR2021 vs SX1280 at 300 km?
- [ ] Design cold-start sync protocol (ranging-based for no-GPS nodes)
- [ ] Design software drift tracking loop (offset + drift_rate)
- [ ] Study Stuart's Balloon Tracker ranging calibration data (40-85 km)
- [ ] Write findings to `mesh-stack/research/clock-sync/notes.md`

### Step 4: Mesh Routing → FIPS Integration
- [ ] Study FIPS architecture: `https://github.com/jmcorgan/fips` — spanning-tree, bloom-filter, Noise IK/XK
- [ ] Study microfips Transport trait: `https://github.com/Amperstrand/microfips` — `crates/microfips-protocol/src/`
- [ ] Design FIPS `Transport` implementation for LoRa: how FIPS frames map to sx1280-serial fragments + Wirehair
- [ ] Evaluate: Can microfips run on ESP32-C3 (RISC-V)? Test `cargo build -p microfips --target riscv32imc-unknown-none-elf`
- [ ] Evaluate: C++ FIPS leaf node — estimate effort to implement Noise IK/XK + FMP + FSP in C++/ESP-IDF
- [ ] Decision: Rust (microfips) vs C++ (ESP-IDF) for mesh firmware
- [ ] Write findings to `mesh-stack/research/fips-integration/notes.md`

### Step 5: MeshCore LR2021 Port
- [x] Study MeshCore radio abstraction: `https://github.com/meshcore-dev/MeshCore` — `arch/esp32/`, RadioLibWrapper
- [x] Verify: Does MeshCore's `RadioLibWrapper` work with LR2021 via RadioLib v7.6.0?
- [x] Create MeshCore variant for ESP32-C3 + LR2021 (pin mapping, SPI config)
- [x] Create custom `esp32c3_supermini` board definition (fixes XIAO D-pin/GPIO conflict)
- [x] Install PlatformIO (`pip install platformio`)
- [x] Clone MeshCore + apply patches (`make setup`)
- [x] Build `LR2021_companion_radio_usb` successfully — 501KB flash, 136KB RAM
- [x] Build all 7 LR2021 targets (`make build-all`) — all 7 pass
- [x] Flash to ESP32-C3 SuperMini + LR2021 dev board — companion on `/dev/ttyACM2`
- [x] Radio init verified on hardware (ESP-IDF HAL bypasses Arduino SPI)
- [ ] Repeater firmware build + flash with EspIdfHal
- [ ] Verify all 7 targets rebuild with EspIdfHal changes
- [ ] Test: MeshCore passive RX in Berlin (10-30 min serial monitoring for community adverts)
- [ ] Test: MeshCore TX in Berlin (advert, needs MeshCore app)
- [ ] Test: Encrypted chat with community node
- [ ] Test: KISS modem serial bridge
- [ ] Range test: MeshCore SF8/BW62.5 vs our tracker SF9/BW125
- [x] Evaluate: PlatformIO build vs ESP-IDF port — **Decision: ESP-IDF for flight, PlatformIO for bench/PR**
- [x] Write findings to `mesh-stack/research/meshcore-study.md` and `mesh-stack/research/meshcore-radiolib-wrapper-study.md`

### Step 5b: Cluster-Aware Stratorelay
- [x] Analyze MeshCore virtual hooks for subclassing (`filterRecvFloodPacket`, `allowPacketForward`, `onAdvertRecv`, `routeRecvPacket`)
- [x] Evaluate bloom filter libraries: ArashPartow/bloom, jvirkki/libbloom, aappleby/smhasher — **Decision: custom StaticBloomFilter**
- [x] Design union-find clustering from flood path observations
- [x] Design cluster head election scoring (recency + SNR + stability)
- [x] Design packet filtering logic (drop from non-heads, bridge between clusters)
- [x] Calculate memory budget: ~6.5 KB for 256 nodes / 32 clusters on ESP32-C3
- [x] Write findings to `mesh-stack/research/routing/cluster-aware-bridge.md`
- [x] Write ADR-013: `docs/adr/013-cluster-aware-stratorelay.md`
- [ ] Fly basic MeshCore repeater first → collect node density + advert frequency data
- [ ] Tune parameters (MAX_NODES, REBUILD_INTERVAL, bloom sizes) based on flight data
- [ ] Implement StratoRelayMesh + NodeTable + UnionFind + StaticBloomFilter as ESP-IDF component
- [ ] Bench test with 3+ ground nodes
- [ ] Submit upstream PR #2: StratoRelayMesh example to MeshCore

### Step 6: Nostr over FIPS over LoRa
- [ ] Study esp32-tollgate Nostr relay implementation: `https://gitworkshop.dev/npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/git.orangesync.tech/esp32-tollgate`
- [ ] Study strfry relay: `https://github.com/hoytech/strfry` — for ground station
- [ ] Design Nostr-over-FIPS message types (EVENT, REQ, REPLY, OK, TOO_LARGE)
- [ ] Design SPIFFS/LittleFS event storage layout for balloon (FIFO, TTL, indexing)
- [ ] Calculate: How many kind 0/1 events fit in LoRa airtime budget per TDMA frame?
- [ ] Prototype: Serialize NIP-01 event → FIPS encrypted frame → erasure-coded fragments → LoRa
- [ ] Write findings to `mesh-stack/research/nostr-over-lora/notes.md`

### Step 5: Throughput & Link Budget
- [ ] Calculate TDMA overhead: contention window, guard bands, slot headers
- [ ] Calculate erasure coding overhead for various loss rates (20%, 35%, 50%)
- [ ] Calculate net throughput per modulation mode after all overheads
- [ ] Model MultiWAN bonding: N balloons × per-link throughput × (1 - erasure_overhead)
- [ ] Determine: how many balloons at what modulation for usable internet?
- [ ] Measure actual LR2021 FLRC throughput on ESP32-C3 via SPI (no CH341 bottleneck)
- [ ] Write findings to `mesh-stack/research/throughput/notes.md`

### Step 6: Protocol Specification
- [ ] Write `mesh-stack/protocol/SPEC.md` — layered protocol specification
- [ ] Define PHY modes and their parameters
- [ ] Define TDMA frame format and slot types
- [ ] Define fragment format with erasure coding metadata
- [ ] Define routing packet format
- [ ] Define clock sync message format

### Step 7: Project Reorganization
- [ ] Move `firmware/` → `tracker/firmware/`
- [ ] Move `hardware/` → `tracker/hardware/`
- [ ] Move `ground-station/` → `tracker/ground-station/`
- [ ] Update `AGENTS.md` with new paths
- [ ] Update build commands in docs
- [ ] Write `mesh-stack/AGENTS.md` — scoped context for mesh stack work
- [ ] Git commit and push

---

## Open Research Questions

### Critical (blocks design decisions)
1. **Can Wirehair run on ESP32-C3?** The ESP32-C3 has 400KB RAM and a 160MHz single-core RISC-V CPU. What's Wirehair's peak memory usage for typical block sizes (1-10 KB)? What's encode/decode latency?
2. **Does LR2021 support the same ranging engine as SX1280?** The SX1280 has a hardware ToF ranging engine. The LR2021 datasheet mentions RTToF ranging. Are they the same hardware? Does RadioLib's `range()` function work on LR2021?
3. **What's the realistic FLRC throughput on LR2021 via SPI?** The E28 USB dongles are bottlenecked by the CH341 serial chip (~115200 baud). Direct SPI on ESP32-C3 should be much faster. What's the actual ceiling?

### Important (affects architecture)
4. **Which TDMA framework to use as starting point?** Our `sx1280-serial` TDMA is proven but in Rust. `ts-lora` and `LoRaMesher` are C/C++ but need evaluation. Which is closest to what we need?
5. **What TDMA slot duration for 300 km links?** At 300 km, propagation delay is 1 ms. LoRa packets at SF10 take 10-100 ms airtime. What slot duration + guard band gives usable throughput while tolerating clock drift?
6. **Mesh routing: proactive or reactive?** Balloons move slowly relative to each other (same wind layer). Ground stations are fixed. Does this simplify routing enough to avoid a full mesh protocol?
7. **What GPS module for balloons?** u-blox MAX-M10S is the community favorite (0.6g bare, 25 mW, 80km ceiling). But do we need a full GPS, or can we get away with TCXO + ranging sync for weight savings in the Minimal plan?

### Interesting (deeper investigation)
8. **Shorthair vs Wirehair for streaming?** Shorthair is designed for continuous streams, Wirehair for bulk blocks. Which fits our use case better? We're sending continuous telemetry streams AND occasional bulk data.
9. **MultiWAN bonding algorithm?** How to bond multiple high-latency, variable-loss links? MPTCP won't work (no TCP). Custom UDP bonding? Packet-level striping across balloons?
10. **Coordinator election at altitude?** The sx1280-serial coordinator election assumes all nodes can potentially hear each other. At altitude with directional antennas, the topology is different. How does this change the protocol?
11. **Can we use LoRa hardware FEC + erasure coding together effectively?** LoRa has built-in CR (coding rate) 4/5 to 4/8. Does using a higher CR (more hardware FEC) plus erasure coding give better throughput than lower CR (less overhead) with more erasure overhead? Where's the sweet spot?
12. **Temperature impact on LR2021 frequency stability?** At -60°C stratospheric temps, the LR2021's oscillator may drift. Does this affect ranging accuracy? Do we need TCXO on the radio module too, not just the MCU?

### High-Throughput Multi-Radio Track (ADR-014)
13. **Can the LR2021 native FIFO batch multiple packets?** The LR2021 has dedicated RX/TX FIFOs with threshold interrupts and auto-RX-TX mode — capabilities the SX1280 lacks. `getRxFifoLevel()` returns uint16_t (possible >256 bytes). If the FIFO accumulates multiple packets, we can achieve 800+ kbps without extra hardware. **This is the immediate priority test.**
14. **What throughput can DMA streaming achieve on ESP32-C3?** Replace RadioLib blocking SPI calls with raw register access + DMA burst reads from LR2021 FIFO. Skip PRBS verification in production mode (FIPS AEAD provides integrity). Target: 800 kbps - 2.6 Mbps on single radio.
15. **FPGA (iCE40 UP5K) vs RP2040 for bent-pipe relay?** FPGA: ~1µs latency, ~5mA, Verilog. RP2040: ~5µs latency, ~15-25mA, C/C++ with PIO. Both power-gated by ESP32-C3 during night-off. Which is better for flight hardware?
16. **How many radios per balloon?** 2 radios (dual relay, +1.3g), 3 radios (triband, +1.8g), 4 radios (quad crossbar, +2.8g). Weight/power/throughput tradeoffs for Mesh V2/V3 variants.
17. **Multi-balloon relay chain latency?** With FPGA bent-pipe: 3-hop relay = ~1.8ms (vs 47ms with MCU). Enables near-real-time communication across the mesh. How does this change the application layer (voice, interactive text, responsive payments)?
18. **TDMA with multiple independent radios?** Each radio operates on a different frequency/mode. How do we synchronize TDMA slots across radios? Can we use GPS PPS for multi-radio clock sync?

---

## Balloon-to-Balloon Range at Altitude

At 12 km altitude, two balloons have geometric line-of-sight of ~780 km (4/3 Earth radius refraction model):

```
d = sqrt(2 * 4/3 * 6371 * h1) + sqrt(2 * 4/3 * 6371 * h2)
  = sqrt(2 * 8495 * 12000) + sqrt(2 * 8495 * 12000)
  = 2 * sqrt(203,880,000) = 2 * 14,280 m = ~28.6 km... wait
```

Correct formula: `d(km) = 4.12 * (sqrt(h1_m) + sqrt(h2_m))`

```
d = 4.12 * (sqrt(12000) + sqrt(12000)) = 4.12 * (109.5 + 109.5) = ~902 km geometric
Practical RF range: ~750-780 km due to FSPL and power constraints
```

### Practical 2.4 GHz LoRa Range (Balloon-to-Balloon)

Both balloons at 12 km, each with omnidirectional dipole (+22 dBm FEM):

| Distance | FSPL | Received | Best Modulation | Air Rate |
|----------|------|----------|-----------------|----------|
| 100 km | -140.0 dB | -116.0 dBm | SF8/1625 (-114) | 38 kbps |
| 300 km | -149.6 dB | -125.6 dBm | SF10/125 (-133.5) | 1.0 kbps |
| 500 km | -154.0 dB | -130.0 dBm | SF11/125 (-138.5) | 0.5 kbps |
| 780 km | -157.9 dB | -133.9 dBm | SF12/125 (-141.5) | 0.25 kbps |

Balloon-to-balloon at max range is limited to ~0.25 kbps — insufficient for internet transport. Primary mesh links should be balloon-to-ground (~300 km, ~22 kbps).

---

## Link Budget: Balloon to Ground

### Free Space Path Loss

| Distance | 2.4 GHz | 868 MHz |
|----------|---------|---------|
| 50 km | 134.0 dB | 125.2 dB |
| 100 km | 140.0 dB | 131.2 dB |
| 200 km | 146.0 dB | 137.2 dB |
| 300 km | 149.6 dB | 140.8 dB |
| 500 km | 154.0 dB | 145.2 dB |

### Receiver Sensitivity (LR2021/LR2022)

| Modulation | Sensitivity | Air Rate |
|-----------|-------------|----------|
| LoRa SF12/125 kHz | -141.5 dBm | 0.25 kbps |
| LoRa SF11/125 kHz | -138.5 dBm | 0.5 kbps |
| LoRa SF10/125 kHz | -133.5 dBm | 1.0 kbps |
| LoRa SF9/125 kHz | -129.0 dBm | 1.7 kbps |
| LoRa SF8/125 kHz | -126.0 dBm | 3.1 kbps |
| LoRa SF7/125 kHz | -123.0 dBm | 5.5 kbps |
| LoRa SF10/1625 kHz | -121.0 dBm | ~12 kbps |
| LoRa SF9/1625 kHz | -117.0 dBm | ~22 kbps |
| LoRa SF8/1625 kHz | -114.0 dBm | ~38 kbps |
| LoRa SF7/1625 kHz | -109.0 dBm | ~87 kbps |
| LoRa SF5/1625 kHz | -102.0 dBm | ~200 kbps |
| FLRC 325 kbps | -98.0 dBm | ~325 kbps |
| FLRC 1300 kbps | -88.0 dBm | ~1300 kbps |

### V1: Omnidirectional Balloon + Ground Station

Balloon: +22 dBm (FEM) + 2 dBi dipole. Ground: high-gain antenna.

**2.4 GHz with 18 dBi ground Yagi:**

| Distance | Received | Best Mode | Air Rate | Net (~40%) |
|----------|----------|-----------|----------|-----------|
| 50 km | -101.6 dBm | FLRC 325k | 325 kbps | ~130 kbps |
| 100 km | -107.6 dBm | SF7/1625 | 87 kbps | ~37 kbps |
| 200 km | -113.6 dBm | SF8/1625 | 38 kbps | ~16 kbps |
| 300 km | -117.6 dBm | SF9/1625 | 22 kbps | ~9 kbps |
| 500 km | -122.0 dBm | SF10/125 | 1.0 kbps | ~0.4 kbps |

**868 MHz with 12 dBi ground Yagi (dipole is omnidirectional, no pol issue):**

| Distance | Received | Best Mode | Air Rate | Net (~40%) |
|----------|----------|-----------|----------|-----------|
| 50 km | -89.2 dBm | SF7/125 | 5.5 kbps | ~2.3 kbps |
| 100 km | -95.2 dBm | SF7/125 | 5.5 kbps | ~2.3 kbps |
| 300 km | -104.8 dBm | SF9/125 | 1.7 kbps | ~0.7 kbps |
| 480 km | -108.8 dBm | SF10/125 | 1.0 kbps | ~0.4 kbps |

### V2: Directional Balloon (7 dBi Yagi) + Ground Station

**2.4 GHz with 18 dBi ground Yagi:**

| Distance | Received | Best Mode | Air Rate | Net (~40%) |
|----------|----------|-----------|----------|-----------|
| 50 km | -94.6 dBm | FLRC 1300k | 1300 kbps | ~550 kbps |
| 100 km | -100.6 dBm | FLRC 325k | 325 kbps | ~130 kbps |
| 200 km | -106.6 dBm | SF7/1625 | 87 kbps | ~37 kbps |
| 300 km | -110.6 dBm | SF8/1625 | 38 kbps | ~16 kbps |
| 500 km | -115.0 dBm | SF10/1625 | 12 kbps | ~5 kbps |

---

## Throughput: MultiWAN Bonding

With 4 balloons visible from a ground station:

| Distance | V1 Per-Link Net | 4x Bonded | V2 Per-Link Net | 4x Bonded |
|----------|----------------|-----------|----------------|-----------|
| 100 km | 37 kbps | **~150 kbps** | 130 kbps | **~520 kbps** |
| 200 km | 16 kbps | **~64 kbps** | 37 kbps | **~150 kbps** |
| 300 km | 9 kbps | **~36 kbps** | 16 kbps | **~64 kbps** |

Net efficiency ~40% of air rate (erasure coding 1.5x overhead for 35% loss + TDMA 20-30% + protocol 10-15%).

### High-Throughput Multi-Radio Projections (ADR-014)

With LR2021 native FIFO batching + DMA + multi-radio coprocessor:

| Architecture | Per-Link | 2-Radio Aggregate | 4-Radio Aggregate | Power | Weight |
|-------------|----------|-------------------|-------------------|-------|--------|
| Current (RadioLib, PRBS, 1 radio) | 80 kbps | — | — | 134 mW | 14g (V1) |
| DMA + skip PRBS + FIFO batch (1 radio) | ~800 kbps | — | — | 134 mW | 14g |
| + RP2040 dual-radio | ~800 kbps × 2 | **~1.6 Mbps** | — | 175 mW | 19-23g |
| + iCE40 FPGA 4-radio | ~2.6 Mbps × 4 | — | **~10.4 Mbps** | 89 mW | 21-25g |

Note: These are bench-range projections. At 300 km with path loss, per-link throughput drops significantly (see MultiWAN table above). The multi-radio advantage is frequency diversity + aggregate throughput, not range extension.

---

## Three-Board Hardware Strategy (ADR-015)

Three board variants sharing ESP32-C3 + LR2021 core, with progressive coprocessor upgrades:

### Board A: ESP32-C3 Solo (Tracker / Mesh V1)
- **Coprocessor**: None — software optimization only (inline SPI, skip PRBS)
- **Throughput**: 500-1000 kbps (from 80 kbps baseline)
- **Weight/Power**: 14-22g / 134-431 mW (unchanged)
- **Status**: 2 prototypes, firmware optimization in progress

### Board B: ESP32-C3 + RP2040 Coprocessor (Mesh V2)
- **Coprocessor**: RP2040-Zero (~$1, +1.3g) — PIO hardware SPI master, dual-core
- **Throughput**: 2000+ kbps per radio
- **Key advantage**: PIO = mini-FPGA for single-radio I/O, dual-core parallel processing
- **Power gating**: RP2040 OFF at night (ESP32-C3 sleeps at 5µA)
- **Status**: RP2040-Zero ordered, prototype pending

### Board C: ESP32-C3 + iCE40 UP5K FPGA (Mesh V3)
- **Coprocessor**: Lattice iCE40 UP5K (JLCPCB C2678152, ~$6, +0.8g) — hardware crossbar
- **Throughput**: 2600 kbps × N radios (full air rate per radio)
- **Key advantage**: N×N crossbar for multi-radio bent-pipe relay, 128KB SPRAM packet queue
- **Power gating**: FPGA OFF at night (ESP32-C3 sleeps at 5µA)
- **Configuration**: W25Q32JV flash, yosys + nextpnr open-source toolchain
- **Status**: Design phase — PCB to be ordered from JLCPCB (~$15-20/board)

See `docs/board-variants.md` for full pin assignments, BOMs, and checklists.
See `docs/adr/015-three-board-hardware-strategy.md` for the decision record.

### Board Variant Throughput Projections

| Variant | Bench (1m) | 50 km | 100 km | 300 km | Max Radios |
|---------|-----------|-------|--------|--------|------------|
| Board A (solo) | ~1000 kbps | ~130 kbps | ~37 kbps | ~9 kbps | 1 |
| Board B (RP2040) | ~2000 kbps | ~550 kbps | ~130 kbps | ~16 kbps | 1-2 |
| Board C (FPGA, 2 radio) | ~5200 kbps | ~1100 kbps | ~260 kbps | ~32 kbps | 2-6 |

---

## TX Power Tradeoffs

Each +3 dB (doubling TX power) roughly bumps one modulation step (~2x data rate).

| TX Power | Hardware Needed | DC Power | 300 km Throughput | Solar Cells |
|----------|----------------|----------|-------------------|-------------|
| +12 dBm (16 mW) | Bare LR2021 | 165 mW | 0.7 kbps | 6x |
| +22 dBm (158 mW) | **SKY66112 FEM (our design)** | 500 mW | 9 kbps | 6-8x |
| +24 dBm (250 mW) | SKY66112 at max | 660 mW | 16 kbps | 8-10x |
| +27 dBm (500 mW) | External PA stage | 1.65W | 37 kbps | 12x |
| +30 dBm (1 W) | SKY66114 or discrete PA | 3.3W | 85 kbps | 16-20x |

**Design decision:** Build +22 dBm first, design PCB for +30 dBm upgrade path (SKY66114 footprint).

### Regulatory Limits

| Region | 2.4 GHz ISM EIRP Limit | With 2 dBi Dipole |
|--------|------------------------|-------------------|
| EU | +20 dBm (100 mW) | +22 dBm TX = +24 dBm EIRP (technically over) |
| US | +30 dBm | +22 dBm TX = OK |

Pico balloons are a gray area — brief transmissions, international airspace.

---

## Power Budget: Mesh Scenarios

### Tracker (Current Design)

```
30s cycle, LoRa SF10 @ 2.4 GHz, 4 Wings Leuchtturm
Energy per cycle: ~205 mAs
Average power: ~7 mW
```

### Mesh Relay with Adaptive TX (50/50 RX/TX)

```
TDMA Frame (2s):
  Slot 1: RX from GS-close   (500ms, 11 mA)    = 5.5 mAs
  Slot 2: TX to GS-far        (500ms, 150 mA)   = 75.0 mAs
  Slot 3: RX from GS-far      (500ms, 11 mA)    = 5.5 mAs
  Slot 4: TX to GS-close      (500ms, 30 mA)    = 15.0 mAs
  Total per frame: ~101 mAs
  Average power: 101 mAs / 2s x 3.3V = ~167 mW
```

Adaptive TX saves 38% vs fixed +22 dBm (265 mW).

### Night-Off Default (ADR-010)

Balloon sleeps at night. Default configuration:

| Component | Night-Active | Night-Off |
|-----------|-------------|-----------|
| Supercaps | 2x 3.3F (3.0g) | 1x 0.47F (0.5g) |
| Solar cells | 12x (6.0g) | 6-8x (3.0-4.0g) |
| Total weight | ~17g | ~14g |
| Night coverage | Yes (single balloon) | No (needs multiple balloons) |

Night-off sequence: solar drops → announce "sleeping" → deep sleep (15 µA) → solar rises → GPS lock → announce "awake" → resume mesh. Ground stations estimate night position from wind data.

Configurable night-active mode: populate larger caps and more solar cells for special missions. Same PCB, different component population.

### Solar Adequacy

| Scenario | Avg Power | 12-Cell Avg Solar | Night Reserve |
|----------|-----------|-------------------|---------------|
| Tracker | ~7 mW | 480 mW | 73h |
| Mesh adaptive TX | ~167 mW | 480 mW | 8.8h |
| Mesh fixed +22 dBm | ~265 mW | 480 mW | 5.4h |
| Mesh +30 dBm adaptive | ~350 mW | 480 mW | 3.2h → need 16 cells |

With night-off default (6-8 cells), daytime margin is comfortable: 240-320 mW solar avg vs 167 mW load.

---

## FEM Comparison

| FEM | Max TX | Band | Antenna Diversity | Weight | Reference |
|-----|--------|------|-------------------|--------|-----------|
| **SKY66112-11** | **+24 dBm** | Sub-GHz + 2.4 GHz | No (separate SP4T) | ~0.1g | **In our design** |
| nRF21540 | +21 dBm | 2.4 GHz only | Yes (built-in SPDT) | ~0.1g | `https://github.com/ketoglou/nrf21540-custom-driver` |
| SE2431L | +20 dBm | 2.4 GHz only | Yes (PA+LNA+switch) | ~0.1g | `https://github.com/AnyLeaf/elrs-hardware` |
| SKY66114 | +30 dBm | Sub-GHz | No | ~0.3g | Upgrade path for V2 |

**nRF21540 interesting** — built-in antenna diversity (SPDT) simplifies V2 design. But 2.4 GHz only and lower power than SKY66112.

**SKY66112 driver reference:** `https://github.com/AxDen-Dev/SKY66112_NRF52_Ping_pong_example` — GPIO control for PA/LNA switching.

**ExpressLRS antenna diversity:** `https://github.com/ExpressLRS/ExpressLRS` — production SX1280 diversity firmware with RSSI scanning.

---

## Antenna Strategy (ADR-009)

**V1 (build first):** Omnidirectional wire dipoles for both bands. Ground station provides all gain.

- 868 MHz: wire dipole ~16.4cm + ground 12 dBi Yagi → 1.7 kbps at 300 km
- 2.4 GHz: wire dipole ~6cm + ground 18 dBi Yagi → 22 kbps at 300 km
- No SP4T, no switching firmware, no wing board antenna design
- Night-off default, 6-8 solar cells, ~14g total

**V2 (upgrade path):** Directional antennas when higher throughput needed.

- PCB Yagis on wing boards (current design) or custom CP patches
- SP4T switch + antenna diversity firmware
- 38-87 kbps at 300 km, +30 dBm PA upgrade path

**Ground station:** Dual-band — 868 MHz Yagi + 2.4 GHz CP helical (RHCP). The CP helical handles balloon rotation with fixed 3 dB loss.

---

## Phase 5: Multi-Balloon Reliability (Future Research)

Single Yokohama 32" balloon is proven for long-duration flights (528 days, Ruthroff JR29). However, multi-balloon configurations could theoretically provide redundancy against the #1 failure mode (balloon death). This research is deferred until single-balloon flights are proven.

### Research Questions

1. **Tandem rubbing mitigation**: Jetstream winds at 40,000 ft reach 150+ km/h. How to prevent balloons from abrading each other? Options: long tethers (5-10m), rigid spreader bars, vertical chain spacing.
2. **Superpressure fill calibration**: With 3 balloons, each must reach superpressure independently. Too much fill → altitude overshoot → burst. Too little → no superpressure → nightly descent. What fill volume per balloon gives stable altitude?
3. **Cut-down trigger**: When a balloon leaks, detect via BMP280 altitude drop or radio telemetry timeout. Trigger nichrome wire to sever tether. Hardware: MOSFET + nichrome + nylon tether, ~0.5g per channel.
4. **3x 20" vs 1x 32" cost tradeoff**: 3x 20" Yokohama = €12.90/flight with redundancy. 1x 32" = €9.70/flight with no redundancy. Is the €4.20 premium worth 2x redundancy?
5. **Community precedent**: No successful long-duration multi-balloon pico flights documented. This would be novel research.

### Potential Configurations

| Config | Balloons | Cost/Flight | Redundancy | Gross Lift | Risk |
|--------|----------|-------------|------------|------------|------|
| Standard | 1x 32" | €9.70 | None | ~250g | Low (proven) |
| Redundant | 3x 32" | €29.10 | 2 balloons | ~750g | High (overfill, rubbing) |
| Economy | 3x 20" | €12.90 | 2 balloons | ~180g | Medium (unproven size, rubbing) |
| Hybrid | 1x 32" + 2x 20" backup | €18.30 | 2 balloons | ~370g | Medium |

### Prerequisites Before Starting Phase 5

- [ ] At least 3 successful single-balloon flights completed
- [ ] Failure mode analysis from our own flights (what actually kills our balloons?)
- [ ] Balloon rubbing abrasion test (two inflated balloons in wind tunnel or car roof)
- [ ] Cut-down mechanism proven on ground (nichrome + nylon tether reliability)
- [ ] Altitude-based leak detection algorithm validated (BMP280 data from flights)

---

## Updated Research Checklist

### Completed
- [x] Link budget analysis at various distances (50-500 km, both bands)
- [x] Throughput per modulation mode with net efficiency (~40%)
- [x] Solar power requirements for mesh (167 mW avg with adaptive TX)
- [x] FEM product research (SKY66112, nRF21540, SE2431L, SKY66114)
- [x] Antenna product research (no 2.4 GHz CP patches exist for balloons)
- [x] Balloon-to-balloon range at 12 km altitude (~780 km geometric)
- [x] TX power tradeoffs (+12 to +33 dBm, throughput vs power vs weight)
- [x] Night-off vs night-active design decision
- [x] Adaptive TX power concept for relay scenario (38% savings)
- [x] Project reorganization (tracker/ subdirectory)

### Remaining
- [ ] Clone and study Wirehair (`https://github.com/catid/wirehair`) — ESP32-C3 feasibility
- [ ] Clone and study Shorthair (`https://github.com/catid/shorthair`) — streaming variant
- [ ] Clone and study OpenFEC (`https://github.com/OpenFEC/OpenFEC`) — algorithm comparison
- [ ] Clone and study ts-lora (`https://github.com/deltazita/ts-lora`) — TDMA frame structure
- [ ] Clone and study LoRaMesher (`https://github.com/LoRaMesher/LoRaMesher`) — mesh superframes
- [ ] Clone and study LoraRangingTest (`https://github.com/yplam/LoraRangingTest`) — ranging implementation
- [ ] Clone and study ublox library (`https://github.com/u-blox/ublox-GNSS-Arduino-Library`) — GPS PPS
- [ ] Verify LR2021 ranging vs SX1280 ranging compatibility
- [ ] Measure actual LR2021 throughput at various configurations via SPI
- [ ] Design TDMA frame structure with per-slot power/modulation parameters
- [ ] Write protocol specification (mesh-stack/protocol/SPEC.md)
