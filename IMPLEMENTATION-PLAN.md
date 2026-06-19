# Master Implementation Plan — ESP32 Balloon Tracker + Mesh Stack

**Created**: 2026-05-21
**Last Updated**: 2026-06-10 (Bench test A.4 in progress, B.7.1-B.7.12 complete)

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

**Setup**:
- Board 1 (ttyACM2, MAC B0:A6:04:00:96:DC) → Tracker TX (`CONFIG_BENCH_TEST_MODE=y`, continuous TX every 10s)
- Board 2 (ttyACM3, MAC 88:56:A6:7B:C6:98) → Ground Station RX (minimal, WiFi+serial, no FIPS/mesh)
- Both boards: LR2021 on Sub-GHz antenna (wire dipole or U.FL stub)
- Boards placed 1-2 meters apart on bench

**Preparation**:
- [x] Add `CONFIG_BENCH_TEST_MODE` Kconfig option to tracker firmware (continuous TX loop, no deep sleep)
- [x] Configure ground station receiver: WiFi SSID=STUDIO, disable FIPS/mesh for minimal RX
- [x] Build tracker firmware with `CONFIG_BENCH_TEST_MODE=y`
- [x] Build ground station receiver (minimal config)

**Flash & Test**:
- [x] Flash tracker TX firmware on Board 1 (`idf.py -p /dev/ttyACM2 flash`)
- [x] Flash ground station RX firmware on Board 2 (`idf.py -p /dev/ttyACM3 flash`)
- [x] Monitor Board 2 (RX): verify JSON telemetry output on serial
- [x] Verify CRC-16 validation passing (no "CRC mismatch" warnings)
- [x] Verify RSSI and SNR values are reasonable (expect -30 to -50 dBm at 1-2m)
- [x] Monitor Board 1 (TX): verify "TX complete" every 10 seconds
- [x] Verify packet sequence numbers incrementing correctly

**Results** (2026-06-10):
- Board 1 (TX): Tracker firmware v0.2, `CONFIG_BENCH_TEST_MODE=y`, 2 dBm TX, continuous 10s interval
- Board 2 (RX): Ground station receiver, no WiFi, no FIPS/mesh, minimal LoRa RX
- **First telemetry received at seq=42**, RSSI=-45 dBm, SNR=12.8 dB, CRC valid
- JSON output: `{"type":"telemetry","source":"raw","seq":42,...,"voltage_mv":1762,...,"rssi":-45,"snr":12.8}`
- Supercap voltage readings vary (1538-1966 mV) — real sensor data
- No GPS/BMP280 (not connected to these boards)

**Bugs Found & Fixed**:
1. GS receiver missing `tcxoVoltage=0.0f` → LR2021 init failed (-707)
2. WiFi PHY init interferes with LR2021 SPI → disabled WiFi for bench test
3. Board 2 LR2021 frontend calibration fails (-1300) → patched `setFrequency()` to tolerate cal failure
4. `startReceive()` returns -706 after `readData()` → added `standby()` before `startReceive()`
5. `readData(buf, 256)` returns len=0 even though `getPacketLength()` returns 28 → LR2021 RX pkt length register is consumed on first read; fixed by calling `getPacketLength()` first then `readData(buf, pktLen)`

**Extended Tests** (after basic TX→RX verified):
- [ ] Test at different SF settings (SF7, SF9, SF10)
- [ ] Test at different TX power levels (10, 15, 22 dBm)
- [ ] Verify WiFi uplink: ground station connects to SSID "STUDIO", HTTP POST telemetry
- [ ] Test GPS fix outdoors (if GPS module available)
- [ ] Test deep sleep cycle (wake → TX → sleep) with `CONFIG_BENCH_TEST_MODE=n`
- [ ] Measure current consumption (TX burst, sleep, GPS on)

### A.5 Shakedown Flight Prep
- [ ] Pre-stretch Yokohama 32" balloon: inflate with aquarium pump to 100-105" circumference, hold 10-24h
- [ ] Leak test: heat seal + pressure sensor, monitor 30-60 min
- [ ] Deflate and store for helium fill day
- [ ] Get industrial He 4.6 (Air Liquide ALbee Fly, ~EUR 30-50)
- [ ] Inflation test: Yokohama + He 4.6 fill + heat seal + Kapton tape
- [ ] Leak test: measure circumference over 24-48 hours
- [ ] Weight check: tracker payload on scale (< 4.8g net lift budget)
- [ ] Antenna orientation test: vertical dipole on balloon
- [ ] Ground range test: 100m, 500m, 1km, 5km with tracker on pole/tree
- [ ] Prepare first flight checklist per `docs/first-flight-checklist.md`
- [ ] HYSPLIT trajectory prediction for launch date
- [ ] File NOTAM if required
- [ ] Launch shakedown flight (Yokohama 32" + He 4.6, Minimal variant)

---

## Phase B: Mesh Foundation (MeshCore + Erasure Coding)

### B.1 MeshCore PlatformIO Integration (Dev/Testing)

**Variant files created** (commit `4a589e7`):
- [x] `variants/nicerf_lr2021/` with our pin mapping (DIO9→GPIO5, NSS→GPIO10, RST→GPIO3, BUSY→GPIO4, SCLK→GPIO6, MISO→GPIO2, MOSI→GPIO7)
- [x] `CustomLR2021.h` — RadioLib wrapper with `tcxoVoltage=0.0`, `irqDioNum=9`, `isReceiving()`
- [x] `CustomLR2021Wrapper.h` — MeshCore RadioLibWrapper subclass with LR2021-specific methods
- [x] `NiceRFLR2021Board.h` — Board class (deep sleep, battery ADC, GPIO5 wakeup)
- [x] `target.cpp` / `target.h` — Radio init, SPI begin, identity generation
- [x] `platformio.ini` — 7 build targets (companion USB/BLE/WiFi, chat, KISS, repeater, room)
- [x] `Makefile` — Build/flash/test/monitor automation, pinned to `companion-v1.15.0`
- [x] `apply-patches.sh` — Copies variant files into MeshCore clone + framework dir

**Custom board definition** (commit `540a8d6`+):
- [x] `boards/esp32c3_supermini.json` — Board JSON with correct flash config (4MB, DIO)
- [x] `variants/esp32c3_supermini/pins_arduino.h` — SuperMini V1 pin mapping (D0-D10 = GPIO0-GPIO10)
  - Fixes XIAO board D-pin conflict (D6=GPIO21, D7=GPIO20 vs our GPIO6/GPIO7)
  - Default SPI pins: `MOSI=7, MISO=2, SCK=6, SS=10` (matches LR2021 wiring)
  - GPIO10 is CS only (not also MOSI as on XIAO variant)
- [x] `platformio.ini` updated to `board = esp32c3_supermini`
- [x] PlatformIO variant resolution fixed: `pins_arduino.h` copied to framework package dir

**ESP-IDF HAL** (latest, radio init fix):
- [x] `EspIdfHal.h` — Custom RadioLib HAL using ESP-IDF `spi_bus_initialize()` directly
  - Bypasses Arduino `SPIClass` which returns all-zero responses from LR2021
  - Same approach as tracker firmware's `EspHalC3.h`
  - Uses `Module(&hal, cs, irq, rst, busy)` constructor instead of `Module(cs, irq, rst, busy, spi)`
- [x] `CustomLR2021.h` updated: `std_init()` no longer takes `SPIClass*` parameter
- [x] `target.cpp` updated: uses `EspIdfHal` instead of `SPIClass`
- [x] Radio init verified on hardware: `std_init result: OK`

**Bench testing**:
- [x] T0.1: Install PlatformIO (`pip install platformio`) — PlatformIO 6.1.19
- [x] T0.2: Clone MeshCore and apply patches (`make setup`) — tag companion-v1.15.0
- [x] T0.3: Verify toolchain with existing Xiao C3 variant (`make verify-toolchain`) — BUILD SUCCESS
- [x] T1.1: Build `LR2021_companion_radio_usb` successfully — 529KB flash, 41.6% RAM
- [x] T1.2: Build all 7 LR2021 targets successfully (`make build-all`) — all 7 pass
- [x] T2.1: Flash companion_radio to ESP32-C3 SuperMini (`/dev/ttyACM2`) — FLASH SUCCESS
- [x] T2.2: Radio init succeeds — **VERIFIED** (was -707 with Arduino SPI, now OK with ESP-IDF HAL)
- [x] T2.3: MeshCore boot sequence completes — VERIFIED (companion running, listening on 869.618 MHz)
- [x] T2.4: Repeater firmware builds and flashes with EspIdfHal
- [x] T2.5: Passive RX test — **70+ Berlin community nodes discovered at Freifunk meetup**
- [x] T2.6: TX test — advert sent, community interaction bidirectional confirmed
- [x] T2.7: All 7 targets rebuild with EspIdfHal changes
- [x] T3.P1.1-P1.6: meshcore-cli v1.5.7 installed, serial connected, adverts sent
- [x] T3.P2.1-P2.5: Community discovery — 70+ nodes found at Freifunk Berlin meetup
- [x] T3.P3.1-P3.9: Interactive monitoring — no nodes indoors, but Freifunk meetup successful
- [~] T3.P4.1-P4.8: Two-device self-test — P4.1-P4.5 done (adverts bidirectional), P4.6-P4.8 pending
- [x] T3.P5.1-P5.5: Outdoor test — **DONE** (Freifunk meetup, carried device + MeshCore app)
- [ ] T3.P6.1-P3.P6.4: Register on MeshCore map, prepare upstream PR
- [ ] T4.1-T4.8: Two-device integration tests (encrypted chat, range, RSSI)
- [x] P1.T3-P1.T5: Flood advert, encrypted chat, public channel — **all bidirectional** ✅
- [ ] P1.T6-P1.T7: Repeater mode test, RSSI vs distance (needs user)
- [x] Phase 2 FLRC benchmark: firmware BUILT (6 targets, all compile) — flash + test needs user
- [ ] P1.T8: Duration test (30 min) — in progress
- [ ] 0.2: Additional FLRC targets (650 kbps, 2600 kbps, SF8 baseline)
- [ ] 0.4: MeshCore ESP-IDF component extraction (B.2/B.7) — **core copied + adapted, building**
- [x] 0.5: StratoRelay utility classes (B.8 Phase A) — 11/11 tests passing
- [ ] Document results in README.md
- [ ] Upstream PR #1: LR2021 variant to MeshCore (after bench validation)

**References**: `mesh-stack/research/routing/meshcore-study.md`, `mesh-stack/meshcore-lr2021/README.md`

### B.2 MeshCore Core Extraction (ESP-IDF Flight Firmware)
- [x] Copy core files: Packet, Dispatcher, Mesh, Identity, Utils, helpers (14 files)
- [x] Copy ed25519 C library (17 files, self-contained with own SHA512)
- [x] Create `tracker/firmware/components/meshcore/` component with CMakeLists.txt
- [x] Adapt Utils.cpp: dual crypto backend (mbedtls on ESP_PLATFORM, Arduino Crypto otherwise)
- [x] Adapt Identity.cpp: replace rweather Ed25519 C++ with C ed25519 API
- [x] Adapt Packet.cpp: dual SHA256 backend
- [x] Guard all Stream/Arduino methods with `#ifdef ARDUINO`
- [x] Guard SimpleMeshTables filesystem persistence with `#ifdef ARDUINO`
- [x] Fix member init order in Dispatcher.h and Mesh.h
- [x] Verify `idf.py build` passes — **BUILD SUCCESS** (246KB binary, 76% free)
- [x] Implement `EspIdfRadio` wrapping RadioLib LR2021 as `mesh::Radio`
- [x] Implement `EspIdfClock` (`esp_timer_get_time() / 1000`)
- [x] Implement `EspIdfRNG` (`esp_fill_random()`)
- [x] Implement `EspIdfRTC` (epoch + offset from EspIdfClock)
- [x] Implement `EspIdfBoard` (battery ADC, deep sleep, reboot)
- [x] Wire MeshCore into `app_main.cpp` (BalloonMesh subclass, minimal init + loop)
- [ ] Unit tests for mesh routing (flood + direct) — B.7.13
- [ ] Integration test: 2 nodes on ESP-IDF firmware — B.7.14

**References**: `mesh-stack/research/routing/meshcore-study.md` Section 8

**Component size**: ~41KB flash (ed25519: 27KB, MeshCore: 13KB, pktmgr: 1KB), zero heap allocations

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

### B.7 MeshCore Core Extraction (ESP-IDF)

MeshCore is PlatformIO + Arduino. Our tracker is ESP-IDF. For single-MCU flight firmware, we extract MeshCore's framework-agnostic core (~1,500 lines C++) into an ESP-IDF component. The PlatformIO build (`mesh-stack/meshcore-lr2021/`) remains for bench testing and upstream contributions.

**References**: `mesh-stack/research/routing/meshcore-study.md` Section 5 (Option B), `mesh-stack/research/routing/cluster-aware-bridge.md`

| ID | Task | Est. | Status |
|---|---|---|---|
| B.7.1 | Copy MeshCore core files to `tracker/firmware/components/meshcore/` (Packet, Dispatcher, Mesh, Identity, Utils, helpers) | 1 hr | [x] |
| B.7.2 | Create CMakeLists.txt for meshcore component | 30 min | [x] |
| B.7.3 | Port ed25519 C library + adapt crypto (mbedtls AES/SHA256/HMAC, C ed25519 API) | 2 hrs | [x] |
| B.7.4 | Implement `EspIdfRadio` wrapping our RadioLib HAL (shares radio with tracker via mutex) | 2 hrs | [x] |
| B.7.5 | Implement `EspIdfClock` (`esp_timer_get_time() / 1000`) | 15 min | [x] |
| B.7.6 | Implement `EspIdfRNG` (`esp_fill_random()`) | 15 min | [x] |
| B.7.7 | Implement `EspIdfRTC` (epoch + offset from EspIdfClock) | 30 min | [x] |
| B.7.8 | Implement `EspIdfBoard` (battery ADC, deep sleep via esp_sleep) | 1 hr | [x] |
| B.7.9 | Verify `StaticPoolPacketManager` compiles (already in meshcore core) | — | [x] |
| B.7.10 | Remove `RADIOLIB_GODMODE` dependency (use subclass access for protected members) | 1 hr | [x] |
| B.7.11 | Verify `idf.py build` passes with meshcore component | 15 min | [x] |
| B.7.12 | Wire MeshCore into `app_main.cpp` (minimal: init + loop, BalloonMesh subclass) | 1 hr | [x] |
| B.7.13 | Unit tests: flood routing, direct routing, encryption, identity | 2 hrs | [ ] |
| B.7.14 | Integration test: 2 ESP32-C3 nodes running ESP-IDF MeshCore firmware | 2 hrs | [ ] |
| B.7.15 | Memory profiling: measure actual DRAM usage, confirm < 50 KB total | 1 hr | [ ] |

**Estimated total**: ~14 hours

### B.8 Cluster-Aware Stratorelay

The balloon acts as a smart MeshCore relay that identifies ground node clusters, elects cluster heads, and only bridges messages between clusters — preventing flood storms from a high-altitude vantage point. Ground nodes remain completely stock.

**Architecture**: `StratoRelayMesh` extends `mesh::Mesh`, overriding virtual hooks (`filterRecvFloodPacket`, `allowPacketForward`, `onAdvertRecv`, `routeRecvPacket`). Clustering via union-find on observed flood paths + per-cluster bloom filters for membership tests. No external bloom filter library needed — custom `StaticBloomFilter` (~60 lines) with FNV-1a hashing, zero heap allocation.

**References**: `docs/adr/013-cluster-aware-stratorelay.md`, `mesh-stack/research/routing/cluster-aware-bridge.md`

| ID | Task | Est. | Status |
|---|---|---|---|
| B.8.1 | Implement `StaticBloomFilter` template class (~60 lines, no deps, no heap) | 1 hr | [x] |
| B.8.2 | Unit test StaticBloomFilter: insert, contains, FP rate measurement (target < 1%) | 30 min | [x] |
| B.8.3 | Implement `NodeTable` with fixed-size array, LRU eviction, aging | 2 hrs | [x] |
| B.8.4 | Unit test NodeTable: insert, find-by-hash, aging timeout, overflow eviction | 1 hr | [x] |
| B.8.5 | Implement `UnionFind` with path compression + rank balancing | 1 hr | [x] |
| B.8.6 | Unit test UnionFind: union, find, separate components, path compression | 30 min | [x] |
| B.8.7 | Implement `ClusterHeadElector` with scoring (recency + SNR + stability) | 1.5 hrs | [x] |
| B.8.8 | Unit test ClusterHeadElector: election, stale fallback, score ordering | 30 min | [x] |
| B.8.9 | Implement `StratoRelayMesh` class extending `mesh::Mesh` | 3 hrs | [ ] |
| B.8.10 | Override `onAdvertRecv()`: populate NodeTable + UnionFind from advert paths | 1 hr | [ ] |
| B.8.11 | Override `filterRecvFloodPacket()`: drop packets from non-cluster-head nodes | 1 hr | [ ] |
| B.8.12 | Override `allowPacketForward()`: enable bridging only between clusters | 30 min | [ ] |
| B.8.13 | Override `routeRecvPacket()`: selective retransmission via zero-hop to cluster heads | 1 hr | [ ] |
| B.8.14 | Implement periodic cluster rebuild (REBUILD_INTERVAL, STALE_TIMEOUT) | 1 hr | [ ] |
| B.8.15 | Integration test: 3+ ground nodes, verify cluster detection + packet filtering | 3 hrs | [ ] |
| B.8.16 | Simulated density test: log playback with 50+ synthetic nodes, verify scalability | 2 hrs | [ ] |
| B.8.17 | Parameter tuning: adjust MAX_NODES, bloom sizes, timeouts based on 2a flight data | 2 hrs | [ ] |

**Estimated total**: ~22 hours

**Configurable parameters** (compile-time defines, tunable after flight data):
```
STRATO_MAX_NODES          = 256   (max tracked ground nodes)
STRATO_MAX_CLUSTERS       = 32    (max detected clusters)
STRATO_REBUILD_INTERVAL   = 300   (cluster rebuild, seconds)
STRATO_STALE_TIMEOUT      = 1800  (node aging, seconds)
STRATO_BLOOM_FP_RATE      = 0.01  (1% false positive)
STRATO_MIN_CLUSTER_SIZE   = 2     (minimum nodes to form cluster)
STRATO_BIDIRECTIONAL_ONLY = 1     (require bidirectional edges for union)
```

**Memory budget** (static, no heap):
```
NodeTable:     256 × 9 bytes = 2.3 KB
Bloom filters: 32 × 125 bytes = 4.0 KB
Cluster heads: 32 × 7 bytes = 224 bytes
Total:         ~6.5 KB static DRAM
```

### B.9 Balloon Telemetry over MeshCore

The balloon broadcasts its position and status via standard MeshCore adverts and chat messages. Any MeshCore user in range (~700+ km at altitude) sees the balloon on their map. This provides a backup telemetry path independent of internet, WSPR, or LoRaWAN.

| ID | Task | Est. | Status |
|---|---|---|---|
| B.9.1 | Integrate GPS data into MeshCore advert builder (`AdvertDataBuilder(REPEATER, name, lat, lon)`) | 1 hr | [ ] |
| B.9.2 | Implement telemetry formatting: `"ALT:12345 BAT:3200 SOL:180 TMP:-45 GPS:52.5N,13.4E SAT:8 UP:12h30m"` | 30 min | [ ] |
| B.9.3 | Implement periodic telemetry broadcast via `PAYLOAD_TYPE_TXT_MSG` flood (15 min interval) | 1 hr | [ ] |
| B.9.4 | Implement REQ/RESP handler for on-demand telemetry queries from ground users | 1.5 hrs | [ ] |
| B.9.5 | Add altitude + battery to advert `feat1`/`feat2` fields (16-bit custom data) | 30 min | [ ] |
| B.9.6 | Test: verify balloon appears on MeshCore companion app map | 30 min | [ ] |
| B.9.7 | Test: verify telemetry messages received by remote MeshCore node | 30 min | [ ] |

**Estimated total**: ~5.5 hours

### B.10 Documentation + Upstream PRs

| ID | Task | Est. | Status |
|---|---|---|---|
| B.10.1 | Write ADR-013: Cluster-Aware Stratorelay decision | 2 hrs | [x] |
| B.10.2 | Write research doc: clustering algorithm analysis (`mesh-stack/research/routing/cluster-aware-bridge.md`) | 1.5 hrs | [x] |
| B.10.3 | Update `mesh-stack/AGENTS.md` with stratorelay section | 30 min | [x] |
| B.10.4 | Update `IMPLEMENTATION-PLAN.md` with B.7–B.10 tasks | 30 min | [x] |
| B.10.5 | Update `mesh-stack/ROADMAP.md` with stratorelay milestones | 30 min | [x] |
| B.10.6 | Update `mesh-stack/meshcore-lr2021/Makefile` to pin MeshCore release tag | 15 min | [x] |
| B.10.7 | **Upstream PR #1**: LR2021 variant to MeshCore (after B.1 bench validation) | 2 hrs | [ ] |
| B.10.8 | **Upstream PR #2**: StratoRelayMesh as MeshCore example (after B.8 validation) | 2 hrs | [ ] |

**Estimated total**: ~8 hours (5 hrs documentation done, 3 hrs upstream PRs pending hardware validation)

---

## Phase C: FIPS + Nostr Integration

### C.1 FIPS Transport over LoRa
- [x] Study FIPS daemon architecture (https://github.com/jmcorgan/fips)
- [x] Study microfips leaf node (https://github.com/Amperstrand/microfips)
- [x] Assess feasibility: FIPS Noise XK handshake over LoRa (roundtrip budget) — **PROVEN 2026-06-19**
- [x] Implement FIPS session establishment over erasure-coded fragmentation — **handshake works over FLRC**
- [x] Implement Nostr-native identity (secp256k1 keypairs) — **FIPS built-in**
- [x] Implement Noise encryption (ChaCha20-Poly1305) — **FIPS built-in**
- [ ] FIPS mesh routing: spanning-tree + bloom-filter discovery — **needs stable radio link**
- [ ] UDP/IP tunnel over FIPS mesh — **needs stable radio link + end-to-end session**
- [ ] Integration test: 2 nodes, encrypted transport, UDP ping — **blocked on radio stability**

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
| MeshCore core extraction | `tracker/firmware/components/meshcore/` | **Builds OK** (330KB with MeshCore, 246KB without) | B.7.13-B.7.15 pending (unit tests, integration, profiling) |
| StratoRelay cluster layer | `tracker/firmware/components/stratorelay/` | Builds OK | **11/11 passed** |

## Build System Decision

**Flight firmware: ESP-IDF** (single MCU approach)
- Tracker firmware is ESP-IDF, owns radio via RadioLib
- MeshCore core extracted into `tracker/firmware/components/meshcore/`
- StratoRelay layer in `tracker/firmware/components/stratorelay/`
- FreeRTOS tasks: tracker task + mesh task, sharing radio via mutex
- 258 KB free DRAM after tracker; mesh additions need ~32 KB; well within budget

**Bench testing + upstream PRs: PlatformIO**
- `mesh-stack/meshcore-lr2021/` retains PlatformIO build for quick testing
- Upstream PR #1 (LR2021 variant) and PR #2 (StratoRelayMesh example) use PlatformIO
- MeshCore release pinned to `companion-v1.15.0` tag for reproducibility

## Bloom Filter Decision

**Custom `StaticBloomFilter`** — no external library.
- Evaluated ArashPartow/bloom (std::vector = heap), jvirkki/libbloom (malloc), aappleby/smhasher (hash only)
- Our filters are tiny (96-125 bytes each, 32 clusters = ~4 KB total)
- Keys are 1-byte node hashes — trivially hashed with FNV-1a
- MeshCore coding principles: "No dynamic memory allocation"
- ~60 lines, zero dependencies, zero heap allocation

## Existing Completed Work

- [x] ADR-001 through ADR-013 written
- [x] Tracker firmware v0.2 (deep sleep, GPS, 28-byte telemetry, Kconfig)
- [x] **LR2021 radio fully working** (commit `5175ada`): TX at 868 MHz, SF9, 22 dBm
  - Root cause of -707 found: XTAL not TCXO → `tcxoVoltage=0.0` fixes it
  - RadioLib config() patched for calibration error tolerance
  - ESP-IDF SPI master driver (not raw registers), full-duplex, byte-by-byte
- [x] 17/17 unit tests passing (NMEA parsing, CRC-16, packet format)
- [x] 82/82 tests passing across all components (wirehair, FIPS, pipeline, TDMA, erasure, etc.)
- [x] Ground station receiver code (WiFi uplink + mesh pipeline, 864KB BIN)
- [x] Wirehair ported to ESP-IDF — 9/9 host tests
- [x] FIPS-over-LoRa Noise IK — 13/13 host tests + 4/4 pipeline integration
- [x] Pipeline integration — 9/9 host tests
- [x] Semtech PRBS23-XOR erasure coding — 5/5 host tests
- [x] TDMA scheduler — 12/12 host tests
- [x] Nostr event store — 7/7 host tests
- [x] Mesh adapter component — 8/8 tests
- [x] MeshCore LR2021 variant files (8 files, commit `4a589e7`) — never compiled yet
- [x] Cluster-aware bridge design + algorithm (`mesh-stack/research/routing/cluster-aware-bridge.md`)
- [x] INTEGRATION-ARCHITECTURE.md — full 7-layer mesh stack
- [x] Protocol specification: `mesh-stack/protocol/SPEC.md`
- [x] Breadboard wiring guide
- [x] First flight checklist
- [x] BOM updated
- [x] Power budget analysis
- [x] Yokohama 32" Crystal Clear valveless 10-pack ARRIVED (€105.95)
- [x] Heat sealer + Kapton tape ARRIVED
- [x] Aquarium air pump available for pre-stretching
- [x] Some helium available (industrial He 4.6 recommended for first flight)

## Key File Index

| File | Purpose |
|------|---------|
| `docs/ground-station-assessment.md` | Ground station bugs and build steps |
| `mesh-stack/research/erasure-coding/fragmentation-erasure-coding-study.md` | Fragmentation + erasure coding comparison |
| `mesh-stack/research/routing/meshcore-study.md` | MeshCore architecture + LR2021 port plan |
| `mesh-stack/INTEGRATION-ARCHITECTURE.md` | Full 7-layer mesh stack architecture |
| `mesh-stack/ROADMAP.md` | Phase 1-5 roadmap with reference repos |
| `docs/adr/012-mesh-networking-strategy.md` | FIPS + MeshCore + TollGate strategy |
| `docs/adr/013-cluster-aware-stratorelay.md` | Cluster-aware stratorelay decision |
| `mesh-stack/research/routing/cluster-aware-bridge.md` | Clustering algorithm analysis + MeshCore hooks |
| `docs/adr/011-first-flight-strategy.md` | Single balloon, He 4.6, Minimal variant |
| `docs/adr/008-telemetry-protocol.md` | 28-byte telemetry packet format |
| `docs/breadboard-wiring-guide.md` | ESP32-C3_Mini_V1 + LoRa2021 + GPS + BMP280 |
| `docs/first-flight-checklist.md` | Pre-flight through post-launch checklist |
| `docs/power-budget.md` | TX interval power analysis |
| `bom/BOM.md` | Bill of materials |
