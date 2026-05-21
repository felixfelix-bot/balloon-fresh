# Master Implementation Plan — ESP32 Balloon Tracker + Mesh Stack

**Created**: 2026-05-21
**Last Updated**: 2026-05-21

## Status Legend

- [ ] Not started
- [x] Done
- [~] In progress / partially done

---

## Phase A: First Flight Ready (Tracker + Ground Station)

### A.1 Ground Station Receiver Firmware
- [x] Fix P0 bug: `readData()` return value check (`gs_main.cpp:99,104`)
- [x] Fix P1 bug: swap ISR registration before `startReceive()` (`gs_main.cpp:85,91`)
- [x] Fix P3: change telemetry symlink to relative path
- [x] Run `idf.py reconfigure` to fetch RadioLib
- [x] Run `idf.py build` — verify compilation — **BUILD SUCCESS** (181 KB, 82% free)
- [ ] Flash to second ESP32-C3_Mini_V1 (USB-C, `/dev/ttyACM0`)
- [ ] Verify JSON output on serial monitor

**References**: `docs/ground-station-assessment.md`

### A.2 Tracker Firmware Polish
- [x] Configurable callsign hash (Kconfig: `CONFIG_CALLSIGN_HASH_HEX`)
- [x] Fixed duplicate `radio->sleep()` and `sky66112_shutdown()` in `deep_sleep()`
- [x] Configurable TX power (Kconfig: `CONFIG_RADIO_TX_POWER_DBM`)
- [x] Configurable SF (Kconfig: `CONFIG_RADIO_SF`)
- [x] Configurable frequency (Kconfig: `CONFIG_RADIO_FREQ_MHZ_X10`)
- [x] Verify `idf.py build` still passes after changes — **BUILD SUCCESS** (227 KB, 78% free)
- [x] Run unit tests — **17/17 passed**

**References**: `tracker/firmware/main/app_main.cpp`

### A.3 Hardware Assembly (User Tasks)
- [ ] Wire tracker breadboard per `docs/breadboard-wiring-guide.md`
- [ ] Wire ground station breadboard per `docs/breadboard-wiring-guide.md`
- [ ] Cut wire dipole antennas (868 MHz: 8.6 cm legs each side)
- [ ] Connect antennas to U.FL connectors on LoRa2021 modules
- [ ] Verify BMP280 on I2C (GPIO8 SDA, GPIO9 SCL)
- [ ] Verify GPS on UART1 (GPIO0 TX, GPIO1 RX) — if GPS module available
- [ ] Power test: verify 3.3V stable under TX load

### A.4 Bench Test — Full TX→RX Chain
- [ ] Flash tracker firmware on first ESP32-C3_Mini_V1
- [ ] Flash ground station receiver on second ESP32-C3_Mini_V1
- [ ] Place antennas 1-2 meters apart
- [ ] Verify telemetry packets received (JSON on serial monitor)
- [ ] Verify CRC-16 validation passing
- [ ] Test at different SF settings (SF7, SF9, SF10)
- [ ] Test GPS fix outdoors (if GPS module available)
- [ ] Test deep sleep cycle (wake → TX → sleep)
- [ ] Measure current consumption (TX burst, sleep, GPS on)

### A.5 Shakedown Flight Prep
- [ ] Inflation test: DecoGlee balloon + He fill + heat seal
- [ ] Leak test: measure diameter over 24-48 hours
- [ ] Weight check: tracker payload on scale (< 4.8g net lift budget)
- [ ] Antenna orientation test: vertical dipole on balloon
- [ ] Ground range test: 100m, 500m, 1km, 5km with tracker on pole/tree
- [ ] Prepare first flight checklist per `docs/first-flight-checklist.md`
- [ ] HYSPLIT trajectory prediction for launch date
- [ ] File NOTAM if required
- [ ] Launch shakedown flight (DecoGlee + He, 3-8 day target)

---

## Phase B: Mesh Foundation (MeshCore + Erasure Coding)

### B.1 MeshCore PlatformIO Integration (Dev/Testing)
- [ ] Fork MeshCore repo
- [ ] Create `variants/nicerf_lr2021/` with our pin mapping
  - DIO9→GPIO5, NSS→GPIO10, RST→GPIO3, BUSY→GPIO4
  - SCLK→GPIO6, MISO→GPIO2, MOSI→GPIO7
- [ ] Handle DIO9 IRQ mapping in `CustomSX1262::std_init()`
- [ ] Remove `SX126X_DIO2_AS_RF_SWITCH` (NiceRF has own RF switch)
- [ ] Build with PlatformIO
- [ ] Flash to 2× ESP32-C3_Mini_V1 dev boards
- [ ] Bench test: MeshCore flood routing between 2 nodes
- [ ] Test encryption (Ed25519 identity, AES-128)
- [ ] Range test: MeshCore SF8/BW62.5 vs our tracker SF9/BW125
- [ ] Document results

**References**: `mesh-stack/research/routing/meshcore-study.md`

### B.2 MeshCore Core Extraction (ESP-IDF Flight Firmware)
- [ ] Copy core files: Packet, Dispatcher, Mesh, Identity, Utils, helpers
- [ ] Create `tracker/firmware/components/meshcore/` component
- [ ] Implement `mesh::Radio` interface wrapping our RadioLib HAL
- [ ] Implement `mesh::MillisecondClock` (esp_timer)
- [ ] Implement `mesh::RNG` (esp_random)
- [ ] Implement `mesh::RTCClock` (GPS time)
- [ ] Implement `mesh::MainBoard` (battery, sleep)
- [ ] Port `rweather/Crypto` as ESP-IDF component
- [ ] Remove `RADIOLIB_GODMODE` dependency
- [ ] Verify `idf.py build` passes
- [ ] Unit tests for mesh routing (flood + direct)
- [ ] Integration test: 2 nodes on ESP-IDF firmware

**References**: `mesh-stack/research/routing/meshcore-study.md` Section 8

### B.3 Wirehair Port to ESP-IDF
- [x] Clone Wirehair repo (https://github.com/catid/wirehair)
- [x] Create `tracker/firmware/components/wirehair/` component
- [x] Add RISC-V detection to `gf256.h` (`__riscv` and `ESP_PLATFORM` → `GF256_TARGET_MOBILE`)
- [x] Create CMakeLists.txt for ESP-IDF component
- [x] Verify `idf.py build` compiles — **BUILD SUCCESS**
- [x] Fix `WirehairCodec.h` type mismatches (`uint32_t` vs `unsigned`)
- [ ] Write benchmark test: create encoder, encode N=9 blocks, measure time
- [ ] Measure actual RAM usage (heap before/after encoder create)
- [ ] Test decode on ESP32-C3 (full encode → decode roundtrip)
- [ ] If RAM > 200 KB: evaluate GF256 log/exp table optimization
- [ ] Document benchmark results

**References**: `mesh-stack/research/erasure-coding/fragmentation-erasure-coding-study.md` Section 2.1

### B.4 Semtech PRBS23-XOR Erasure Coding
- [x] Create `tracker/firmware/components/erasure/` with clean C implementation
- [x] PRBS23 parity matrix generation
- [x] XOR-only encoder (~20 lines)
- [x] Decoder with single-loss peeling + GE solver for multi-loss
- [x] Unit tests: **5/5 passed** (no loss, single loss, 3 losses, all lost, random 30%)
- [x] Build with ESP-IDF — **BUILD SUCCESS**
- [ ] Known limitation: GE solver handles ~80% of random loss patterns correctly
- [ ] Future: port full Semtech `FragDecoder.c` for production quality

**References**: `mesh-stack/research/erasure-coding/fragmentation-erasure-coding-study.md` Section 1.3

### B.5 Fragmentation Layer
- [x] Design fragment header format: `block_id(2) + frag_index(1) + original_count(1) + crc16(2)` = 6 bytes
- [x] Create `tracker/firmware/components/frag/` component
- [x] Implement `frag_make_frame()`: split payload → add header + CRC-16 → output frame
- [x] Implement `frag_reassembler_feed()`: receive frame → validate → buffer → check completeness
- [x] Deduplication via bitmap (reject duplicate fragments)
- [x] Static buffer management (no malloc)
- [x] Unit tests: **3/3 passed** (fragment+reassemble, wrong block_id, duplicate)
- [x] Build with ESP-IDF — **BUILD SUCCESS**
- [ ] Integrate erasure coding: encode before fragment, decode after reassemble
- [ ] Integration test: encode → fragment → LoRa TX → RX → defragment → decode

**References**: `mesh-stack/research/erasure-coding/fragmentation-erasure-coding-study.md` Section 4

### B.6 Dual-Band TDMA Scheduler
- [ ] Study sx1280-serial TDMA implementation (Rust, our repo)
- [ ] Design TDMA frame: 2s total, 4×500ms slots (Sub-GHz / 2.4 GHz alternating)
- [ ] Implement slot scheduler with GPS PPS discipline
- [ ] Integrate with MeshCore (Sub-GHz slots) and FIPS (2.4 GHz slots)
- [ ] Coordinator election algorithm (if multi-balloon)
- [ ] Guard bands between slots
- [ ] Unit tests: slot timing, transitions, overlap detection

**References**: `mesh-stack/INTEGRATION-ARCHITECTURE.md`, `mesh-stack/research/tdma/`

---

## Phase C: FIPS + Nostr Integration

### C.1 FIPS Transport over LoRa
- [ ] Study FIPS daemon architecture (https://github.com/jmcorgan/fips)
- [ ] Study microfips leaf node (https://github.com/Amperstrand/microfips)
- [ ] Assess feasibility: FIPS Noise XK handshake over LoRa (roundtrip budget)
- [ ] Implement FIPS session establishment over erasure-coded fragmentation
- [ ] Implement Nostr-native identity (secp256k1 keypairs)
- [ ] Implement Noise encryption (ChaCha20-Poly1305)
- [ ] FIPS mesh routing: spanning-tree + bloom-filter discovery
- [ ] UDP/IP tunnel over FIPS mesh
- [ ] Integration test: 2 nodes, encrypted transport, UDP ping

### C.2 Nostr Store-and-Forward
- [ ] Design Nostr event storage format (SPIFFS/LittleFS)
- [ ] Implement FIFO event store (~2000 events, ~500 bytes each ≈ 1 MB)
- [ ] Nostr event types: kind 0 (metadata), kind 1 (text), kind 7 (reaction)
- [ ] Event serialization: compact binary for LoRa, JSON for ground station
- [ ] Receive → store → forward pipeline
- [ ] Bloom filter for deduplication
- [ ] Integration test: create event → LoRa TX → RX → store → retrieve

### C.3 Ground Station FIPS Daemon
- [ ] Install FIPS daemon on Raspberry Pi / SBC
- [ ] Configure FIPS to use LoRa serial interface (ground station ESP32-C3)
- [ ] Bridge LoRa-received Nostr events to internet Nostr relays
- [ ] Bridge internet Nostr events to LoRa for balloon upload
- [ ] strfry Nostr relay on ground station for local caching
- [ ] Integration test: full roundtrip Nostr event via balloon

---

## Phase D: TollGate + Multi-Balloon

### D.1 TollGate at Ground Stations
- [ ] Study TollGate protocol (https://github.com/OpenTollGate/tollgate)
- [ ] Study esp32-tollgate (https://gitworkshop.dev/.../esp32-tollgate)
- [ ] Implement Cashu WiFi captive portal on ground station
- [ ] Payment-gated internet access via balloon mesh
- [ ] Token verification over LoRa (mint quote → proof → access)

### D.2 Multi-Balloon Mesh
- [ ] Launch 2+ Phase B validated balloons
- [ ] Test inter-balloon relay (TDMA, FIPS routing)
- [ ] Test MultiWAN bonding across balloon paths
- [ ] Measure aggregate throughput (target: 36 kbps @ 300 km with 4 balloons)
- [ ] Test night-off / night-active modes
- [ ] Long-duration flight with Yokohama 32" + He 4.6

---

## Research Documents (Completed)

- [x] Fragmentation & erasure coding study → `mesh-stack/research/erasure-coding/fragmentation-erasure-coding-study.md`
- [x] MeshCore study → `mesh-stack/research/routing/meshcore-study.md`
- [x] Ground station assessment → `docs/ground-station-assessment.md`

## New Components Created

| Component | Path | Status | Tests |
|-----------|------|--------|-------|
| Wirehair fountain codes | `tracker/firmware/components/wirehair/` | Builds OK | Benchmark pending (needs hardware) |
| PRBS23-XOR erasure coding | `tracker/firmware/components/erasure/` | Builds OK | 5/5 passed |
| Fragmentation layer | `tracker/firmware/components/frag/` | Builds OK | 3/3 passed |

## Existing Completed Work

- [x] ADR-001 through ADR-012 written
- [x] Tracker firmware v0.2 (deep sleep, GPS, 28-byte telemetry, Kconfig)
- [x] 17/17 unit tests passing (NMEA parsing, CRC-16, packet format)
- [x] Ground station receiver code written (needs bug fixes)
- [x] Breadboard wiring guide
- [x] First flight checklist
- [x] BOM updated
- [x] Power budget analysis
- [x] Integration architecture documented
- [x] ROADMAP.md with reference repos
- [x] Yokohama 32" balloons ordered
- [x] Heat sealer ordered
- [x] Kapton tape ordered

## Key File Index

| File | Purpose |
|------|---------|
| `docs/ground-station-assessment.md` | Ground station bugs and build steps |
| `mesh-stack/research/erasure-coding/fragmentation-erasure-coding-study.md` | Fragmentation + erasure coding comparison |
| `mesh-stack/research/routing/meshcore-study.md` | MeshCore architecture + LR2021 port plan |
| `mesh-stack/INTEGRATION-ARCHITECTURE.md` | Full 7-layer mesh stack architecture |
| `mesh-stack/ROADMAP.md` | Phase 1-5 roadmap with reference repos |
| `docs/adr/012-mesh-networking-strategy.md` | FIPS + MeshCore + TollGate strategy |
| `docs/adr/011-first-flight-strategy.md` | Single balloon, He 4.6, Minimal variant |
| `docs/adr/008-telemetry-protocol.md` | 28-byte telemetry packet format |
| `docs/breadboard-wiring-guide.md` | ESP32-C3_Mini_V1 + LoRa2021 + GPS + BMP280 |
| `docs/first-flight-checklist.md` | Pre-flight through post-launch checklist |
| `docs/power-budget.md` | TX interval power analysis |
| `bom/BOM.md` | Bill of materials |
