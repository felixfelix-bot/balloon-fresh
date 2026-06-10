# Two-Device Test Plan + Autonomous Work Plan

Two ESP32-C3 SuperMini V1 boards, each with NiceRF LoRa2021 module.
Board 1: `/dev/ttyACM2` (serial `B0:A6:04:00:96:DC`) — original board (`D60BE809`)
Board 2: `/dev/ttyACM3` (serial `88:56:A6:7B:C6:98`) — second board (`53A53B5D`)

---

## Phase 0: Autonomous Work While User Away

These tasks can be completed without the user present (boards stay connected on USB).

### 0.1 Duration/Stability Test (~30 min)

- [ ] P0.T1: Start `meshcli msgs_subscribe` logging for 30 min on Board 1 → `logs/duration_test_b1.log`
- [ ] P0.T2: Start `meshcli msgs_subscribe` logging for 30 min on Board 2 → `logs/duration_test_b2.log`
- [ ] P0.T3: Send adverts from both boards at start
- [ ] P0.T4: After 30 min, check `meshcli contacts` on both boards — note counts
- [ ] P0.T5: Verify no errors/crashes in logs
- [ ] P0.T6: Update results table below

### 0.2 Additional FLRC Test Targets (~15 min)

- [ ] P0.F1: Add `flrc_tx_650` / `flrc_rx_650` (868 MHz, 650 kbps, +22 dBm)
- [ ] P0.F2: Add `flrc_tx_24_max` / `flrc_rx_24_max` (2.4 GHz, 2600 kbps, +12 dBm)
- [ ] P0.F3: Add `lora_tx_sf8` / `lora_rx_sf8` (868 MHz, SF8/BW62.5, MeshCore PHY)
- [ ] P0.F4: Build all new targets, verify compilation
- [ ] P0.F5: Add Makefile targets for flash/monitor

### 0.3 flrc-test/README.md (~10 min)

- [ ] P0.R1: Create README with wiring, build/flash commands, test procedure, results template

### 0.4 MeshCore ESP-IDF Component Extraction (B.2/B.7, ~4-6 hrs)

#### 4A: Copy + Adapt Core Files (~2 hrs)

- [ ] 4A.1: Create `tracker/firmware/components/meshcore/` directory
- [ ] 4A.2: Copy `MeshCore.h` — wrap `Arduino.h` in `#ifdef ARDUINO`, add `ESP_LOG` macros
- [ ] 4A.3: Copy `Packet.h/.cpp` — replace `SHA256.h` with `mbedtls/sha256.h`
- [ ] 4A.4: Copy `Dispatcher.h/.cpp` — wrap `Arduino.h` in `#ifdef`
- [ ] 4A.5: Copy `Mesh.h/.cpp` — already clean, minimal changes
- [ ] 4A.6: Copy `Identity.h/.cpp` — `#ifdef` out `Stream&` methods
- [ ] 4A.7: Copy `Utils.h/.cpp` — replace `AES.h`/`SHA256.h` with mbedTLS stubs
- [ ] 4A.8: Copy `StaticPoolPacketManager.h/.cpp` — clean, no changes
- [ ] 4A.9: Copy `SimpleMeshTables.h` — clean, no changes
- [ ] 4A.10: Create `CMakeLists.txt` for meshcore component

#### 4B: Crypto Adaptation (~1 hr)

- [ ] 4B.1: Create `tracker/firmware/components/crypto/` directory
- [ ] 4B.2: Extract `ed25519.c`/`ed25519.h` from rweather/Crypto (~2,000 lines)
- [ ] 4B.3: Implement AES-128 ECB wrapper using `mbedtls/aes.h`
- [ ] 4B.4: Implement SHA-256 wrapper using `mbedtls/sha256.h`
- [ ] 4B.5: Implement HMAC-SHA-256 wrapper using `mbedtls/md.h`
- [ ] 4B.6: Create `CMakeLists.txt` for crypto component with `REQUIRES mbedtls`

#### 4C: ESP-IDF Interface Implementations (~1 hr)

- [ ] 4C.1: Create `tracker/firmware/components/meshcore/esp_idf/` directory
- [ ] 4C.2: `EspIdfRadio.h/.cpp` — `mesh::Radio` wrapping RadioLib HAL with mutex
- [ ] 4C.3: `EspIdfClock.h` — `mesh::MillisecondClock` via `esp_timer_get_time()`
- [ ] 4C.4: `EspIdfRNG.h` — `mesh::RNG` via `esp_random()`
- [ ] 4C.5: `EspIdfRTC.h` — `mesh::RTCClock` via GPS time
- [ ] 4C.6: `EspIdfBoard.h` — `mesh::MainBoard` (battery ADC, reboot)

#### 4D: Build Verification (~1 hr)

- [ ] 4D.1: Update main `CMakeLists.txt` to include meshcore + crypto components
- [ ] 4D.2: Run `idf.py build` — fix compilation errors iteratively
- [ ] 4D.3: Verify flash size within budget (< 4 MB)
- [ ] 4D.4: Verify DRAM usage within budget (< 150 KB static)
- [ ] 4D.5: Tag build (e.g., `v0.4.0-meshcore-espidf`) if successful

### 0.5 StratoRelay Clustering Layer — Independent Utilities (B.8 Phase A, ~2 hrs)

These have no MeshCore dependency — pure algorithm classes:

- [ ] 5A.1: Create `tracker/firmware/components/stratorelay/` directory
- [ ] 5A.2: Implement `StaticBloomFilter<N, FP>` (~60 lines) — `StaticBloomFilter.h`
- [ ] 5A.3: Unit test StaticBloomFilter: insert, contains, FP rate, clear
- [ ] 5A.4: Implement `UnionFind` with path compression + rank (~50 lines) — `UnionFind.h`
- [ ] 5A.5: Unit test UnionFind: union, find, separate components, path compression
- [ ] 5A.6: Implement `NodeTable<N>` with LRU eviction + aging (~120 lines) — `NodeTable.h`
- [ ] 5A.7: Unit test NodeTable: insert, find, aging, overflow eviction, update
- [ ] 5A.8: Implement `ClusterHeadElector` with scoring (~80 lines) — `ClusterHeadElector.h`
- [ ] 5A.9: Unit test ClusterHeadElector: election, stale fallback, score ordering
- [ ] 5A.10: Create `CMakeLists.txt` for stratorelay component
- [ ] 5A.11: Run `idf.py build` — verify compilation

## Phase 1: MeshCore Two-Device LoRa Test

**Objective**: Verify LR2021 MeshCore firmware works device-to-device: advert discovery, encrypted chat, public channel, repeater relay, RSSI/SNR reporting.

**PHY**: 868 MHz, LoRa SF8, BW 62.5 kHz, CR 4/5, sync word 0x12 (MeshCore EU default)

### Setup

- [x] P1.S1: Second LR2021 soldered to second ESP32-C3 SuperMini
- [x] P1.S2: Flash `companion_radio_usb` on Board 2 (`/dev/ttyACM3`) — **53A53B5D**
- [x] P1.S3: Verify Board 2 serial connection: `meshcli -s /dev/ttyACM3 infos` — **confirmed**
- [x] P1.S4: Place both boards 2-5 meters apart (different USB ports/battery packs)

### Tests

- [x] P1.T1: **Advert discovery** — Board 1 advert → Board 2 sees D60BE809 in contacts ✅
- [x] P1.T2: **Bidirectional advert** — Board 2 advert → Board 1 sees 53A53B5D + 70 community nodes ✅
- [x] P1.T3: **Flood advert** — Both boards sent floodadv, B1 has 120 contacts, B2 has 1 contact ✅
- [x] P1.T4: **Encrypted chat** — B1→B2 DM received, B2→B1 DM received, bidirectional ✅
- [x] P1.T5: **Public channel** — B1 received B2's public msg, B2 received B1's public msg ✅
- [ ] P1.T6: **Repeater mode** — Flash repeater on Board 1, companion on Board 2, verify relay works (needs user)
- [ ] P1.T7: **RSSI/SNR** — Note signal strength and SNR from both sides at 2m, 5m, 10m (needs user)
- [ ] P1.T8: **Duration test** — Leave both running 30 min, verify no crashes, stable connection

### Results

| Test | Board 1 Result | Board 2 Result | Notes |
|------|---------------|---------------|-------|
| P1.T1 | Advert sent | D60BE809 in contacts | ✅ Same room, USB power |
| P1.T2 | 53A53B5D + 70 community nodes in contacts | Advert sent | ✅ B1 has Freifunk meetup data |
| P1.T3 | 120 contacts (70 community + flood) | 1 contact (B1) | ✅ Flood advert propagates |
| P1.T4 | B2→B1 DM received ✅ | B1→B2 DM received ✅ | Bidirectional encrypted chat |
| P1.T5 | Received B2 public msg ✅ | Received B1 public msg ✅ | Bidirectional public channel |
| P1.T6 | | | Needs user (reflash) |
| P1.T7 | RSSI: SNR: | RSSI: SNR: | Needs user (distance) |
| P1.T8 | | | |

---

## Phase 2: FLRC Throughput Benchmark

**Objective**: Measure actual FLRC throughput between two LR2021 devices at various bit rates on both 868 MHz and 2.4 GHz. Compare with LoRa baseline.

**Firmware**: Custom PlatformIO project in `mesh-stack/flrc-test/`, using RadioLib FLRC API + EspIdfHal.

### FLRC Technical Details

LR2021 FLRC bit rates (from RadioLib `LR2021_commands.h`):

| Constant | Bit Rate | Bandwidth | Notes |
|----------|----------|-----------|-------|
| `FLRC_BR_2600` | 2600 kbps | 2666 kHz | Max throughput, 2.4 GHz only |
| `FLRC_BR_2080` | 2080 kbps | 2222 kHz | |
| `FLRC_BR_1300` | 1300 kbps | 1333 kHz | |
| `FLRC_BR_1040` | 1040 kbps | 1333 kHz | |
| `FLRC_BR_650` | 650 kbps | 888 kHz | |
| `FLRC_BR_520` | 520 kbps | 769 kHz | |
| `FLRC_BR_325` | 325 kbps | 444 kHz | Max legal 868 MHz BW (exceeds 125kHz ISM limit) |
| `FLRC_BR_260` | 260 kbps | 444 kHz | |

**EU regulatory note**: 868 MHz ISM band limited to 125 kHz bandwidth, 10% duty cycle. Only LoRa (BW ≤ 125 kHz) is legal at 868 MHz for continuous operation. FLRC at 868 MHz exceeds bandwidth limits — use for lab testing only, or use 2.4 GHz for real deployment.

**LR2021 power limits**:
- Sub-GHz PA: -9 to +22 dBm
- 2.4 GHz PA: -19 to +12 dBm (10 dB less = ~3x shorter range)

### Setup

- [x] P2.S1: Create `mesh-stack/flrc-test/` PlatformIO project
- [x] P2.S2: Port EspIdfHal.h from meshcore-lr2021 project
- [x] P2.S3: Implement TX firmware (configurable freq, bitrate, packet count, payload size)
- [x] P2.S4: Implement RX firmware (receive, count packets, measure RSSI/SNR, report stats)
- [x] P2.S5: Build and verify all 6 targets compile — **all SUCCESS** (~301KB flash, 4.7% RAM)
- [ ] P2.S6: Flash TX on Board 1 and RX on Board 2 (needs user confirmation)
- [ ] P2.S7: Verify basic TX→RX works at 2m before running full benchmarks

### Test Matrix

Each test: TX sends 1000 packets of 50 bytes, RX counts received packets and measures RSSI/SNR.

| Test | Band | Frequency | Modulation | Bit Rate | TX Power | Expected Throughput | Purpose |
|------|------|-----------|------------|----------|----------|-------------------|---------|
| F1 | Sub-GHz | 868 MHz | FLRC | 325 kbps | +22 dBm | ~100-200 kbps | Max FLRC at 868 |
| F2 | Sub-GHz | 868 MHz | FLRC | 260 kbps | +22 dBm | ~80-160 kbps | Reliable 868 FLRC |
| F3 | 2.4 GHz | 2450 MHz | FLRC | 1300 kbps | +12 dBm | ~400-800 kbps | FIPS target rate |
| F4 | 2.4 GHz | 2450 MHz | FLRC | 2600 kbps | +12 dBm | ~800-1600 kbps | Max throughput |
| F5 | Sub-GHz | 868 MHz | LoRa SF9/BW125 | ~1.8 kbps | +22 dBm | ~1.5 kbps | Baseline (tracker) |
| F6 | Sub-GHz | 868 MHz | LoRa SF8/BW62.5 | ~4.5 kbps | +22 dBm | ~3-4 kbps | Baseline (MeshCore) |

### Distance Tests (per modulation)

For each modulation that works at 2m, repeat at increasing distances:

- [ ] P2.D1: 2 meters (same room, baseline)
- [ ] P2.D2: 5 meters (same room / hallway)
- [ ] P2.D3: 10 meters (different room, through 1 wall)
- [ ] P2.D4: 20 meters (through 2+ walls)
- [ ] P2.D5: 50 meters (different floor / building)
- [ ] P2.D6: 100 meters (outdoor line-of-sight, if accessible)

### Results

*Fill in during testing:*

| Test | Distance | Packets TX | Packets RX | Loss % | RSSI (dBm) | SNR (dB) | Effective Throughput |
|------|----------|-----------|-----------|--------|------------|----------|---------------------|
| F1 | 2m | 1000 | | | | | |
| F2 | 2m | 1000 | | | | | |
| F3 | 2m | 1000 | | | | | |
| F4 | 2m | 1000 | | | | | |
| F5 | 2m | 1000 | | | | | |
| F6 | 2m | 1000 | | | | | |

### Analysis

*Fill in after testing:*

- LoRa vs FLRC throughput ratio at 868 MHz: __x
- FLRC 2.4 GHz vs FLRC 868 MHz throughput: __x
- FLRC 2.4 GHz max throughput: __ kbps
- Maximum reliable distance (FLRC 1300 kbps, 2.4 GHz): __ m
- Recommended modulation for FIPS balloon transport: __

---

## Throughput Comparison: LoRa vs FLRC (Theoretical)

| | LoRa SF9/BW125 | LoRa SF8/BW62.5 | FLRC 325 kbps | FLRC 1300 kbps | FLRC 2600 kbps |
|--|----------------|-----------------|---------------|----------------|----------------|
| **Frequency** | 868 MHz | 868 MHz | 868 MHz | 2.4 GHz | 2.4 GHz |
| **Bit rate** | 1.8 kbps | 4.5 kbps | 325 kbps | 1300 kbps | 2600 kbps |
| **TX power** | +22 dBm | +22 dBm | +22 dBm | +12 dBm | +12 dBm |
| **Sensitivity** | -137 dBm | -130 dBm | -110 dBm | -100 dBm | -97 dBm |
| **Link budget** | 159 dB | 152 dB | 132 dB | 112 dB | 109 dB |
| **Range (est.)** | 300+ km | 200+ km | 20-50 km | 3-10 km | 1-5 km |
| **Time-on-air (50B)** | ~220 ms | ~90 ms | ~2 ms | ~0.5 ms | ~0.3 ms |
| **Legal EU 868?** | Yes | Yes | No (BW >125kHz) | No (wrong band) | No (wrong band) |
| **Use case** | Tracker telemetry | MeshCore chat | Lab test only | FIPS transport | FIPS max speed |
