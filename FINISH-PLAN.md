# FINISH-PLAN.md — Comprehensive Plan to Complete All Remaining Work

**Created**: 2026-05-23
**Status**: Planning
**Scope**: Fix, integrate, test, and deploy everything identified in the integration audit

---

## Summary of Current State

- **15 firmware components** built with **73 host tests passing**
- **Tracker firmware v0.2** compiles and builds OK (4.5MB ELF, 229KB BIN)
- **Ground station receiver** compiles and builds OK (186KB BIN)
- **7 protocol components** (FIPS, pipeline, erasure, frag, TDMA, nostr_store, mesh_adapter) are built and tested in isolation but **NOT wired into app_main.cpp**
- **Ground station** has a broken pipeline: `gs_main.cpp` outputs JSON but `ground_station.py` expects raw binary
- **Nostr bridge** has stub signatures and fake pubkey derivation
- **2 test files** (GPS, power_manager) duplicate production code instead of testing it
- **`crypto` component** is unused dead weight (kept per user decision)
- **RadioLib** is gitignored, needs vendoring for reproducibility
- **No on-target testing has happened** — no boards flashed, no bench tests

---

## Work Streams

### W1: Vendor RadioLib as Git Submodule
**Priority**: High (blocks all ESP-IDF builds on fresh clones)
**Effort**: Small
**Files**: `.gitmodules`, `tracker/firmware/managed_components/`, `tracker/ground-station/receiver/managed_components/`

- [ ] Add RadioLib v7.6.0 as git submodule at `components/RadioLib` (shared between tracker + GS)
- [ ] Update `idf_component.yml` in both projects to reference the local path instead of GitHub
- [ ] Remove `managed_components/RadioLib` from both projects
- [ ] Verify both `idf.py build` succeed
- [ ] Add the submodule to `.gitignore` exceptions if needed
- [ ] Verify fresh clone + submodule init + build works

**Acceptance**: `git clone --recurse-submodules` + `idf.py build` works without network access to GitHub

---

### W2: Fix Duplicated Tests
**Priority**: High (tests silently passing on stale code)
**Effort**: Small

#### W2a: Fix GPS test to include production source
- [ ] Refactor `gps.c` to extract `parse_nmea_gga()` and `parse_nmea_rmc()` as non-static functions (or provide a test-only header)
- [ ] Update `test_gps.c` to `#include "../gps.c"` instead of duplicating the parser
- [ ] Add ESP-IDF stubs needed: `driver/uart.h` (for `gps_init`/`gps_read`/`gps_sleep`)
- [ ] Verify all 8 GPS tests still pass
- [ ] Verify test catches a deliberate bug introduced in `gps.c`

#### W2b: Fix power_manager test to include production source
- [ ] Update `test_power_manager.c` to `#include "../power_manager.c"` instead of duplicating `raw_to_mv()`
- [ ] Add ESP-IDF stubs needed: `esp_adc/adc_oneshot.h`, `esp_adc/adc_cali.h`, `esp_adc/adc_cali_scheme.h`
- [ ] Verify all 5 power_manager tests still pass
- [ ] Verify test catches a deliberate bug introduced in `power_manager.c`

**Acceptance**: Both test files compile against actual production source, not duplicated copies. Deliberate bugs in production code cause test failures.

---

### W3: End-to-End Host Integration Test
**Priority**: High (validates the full protocol stack as a unit)
**Effort**: Medium

Create a host-side test that exercises the full chain:
```
Nostr event → mesh_adapter_send → [pipeline: encode → fragment → erasure encode]
    → simulated radio frames (byte copy)
    → mesh_adapter_receive_frame → [pipeline: defragment → erasure decode → decode]
    → original Nostr event recovered
```

- [ ] Create `tests/test_e2e.py` (or `tests/test_c_host.py` class `TestEndToEnd`)
- [ ] Write C test file that:
  1. Creates a 28-byte telemetry packet
  2. Sends it through `mesh_adapter_send()` with frag_size=50, redundancy=4
  3. Copies all output frames to an input array (simulating radio)
  4. Feeds each frame to `mesh_adapter_receive_frame()` on the RX side
  5. Verifies the recovered data matches the original telemetry
- [ ] Add lossy variant: drop 30% of frames, verify recovery still works
- [ ] Add FIPS variant: wrap telemetry in FIPS encrypt → mesh_adapter → radio → mesh_adapter → FIPS decrypt
- [ ] Add TDMA variant: verify TDMA slot callbacks fire at correct times for TX/RX slots
- [ ] Wire into pytest

**Acceptance**: End-to-end test passes for: (a) lossless, (b) 30% loss, (c) FIPS encrypted, (d) with TDMA timing. Test count increases by 4-6.

---

### W4: Integrate Protocol Stack into app_main.cpp
**Priority**: High (the 7 protocol components are built but unused)
**Effort**: Medium-Large

#### W4a: Add Kconfig options for mesh mode
- [ ] Add to `tracker/firmware/main/Kconfig.projbuild`:
  ```
  config ENABLE_MESH
      bool "Enable mesh networking (FIPS + Pipeline + TDMA)"
      default n
  
  config ENABLE_NOSTR_STORE
      bool "Enable Nostr event store (for mesh relay)"
      default n
      depends on ENABLE_MESH
  ```

#### W4b: Update CMakeLists.txt
- [ ] Add conditional REQUIRES: `fips_transport`, `pipeline`, `erasure`, `frag`, `tdma`, `nostr_store`, `mesh_adapter`, `micro_ecc`
- [ ] Use CMake `if(CONFIG_ENABLE_MESH)` pattern for conditional linking

#### W4c: Wire mesh_adapter into app_main.cpp
- [ ] When `CONFIG_ENABLE_MESH=y`:
  - Include mesh_adapter, fips_transport, tdma headers
  - After radio init, call `mesh_adapter_init()` with radio send callback
  - Replace raw `radio->startTransmit(buf, size)` with `mesh_adapter_send()` which internally calls pipeline → fragmentation → erasure → sends each frame via radio
  - In the GPS-wait loop, also call `mesh_adapter_receive_frame()` on any incoming data (for mesh relay)
  - Integrate TDMA: `tdma_init()`, register TX/RX callbacks that call mesh_adapter, `tdma_start()`, tick in main loop
  - Deep sleep at end of TDMA frame instead of fixed interval

#### W4d: Wire FIPS sessions into mesh_adapter
- [ ] Replace the stub `mesh_adapter_set_fips_sessions()` with real implementation
- [ ] `mesh_adapter_send()` should call `fips_encrypt()` before fragmentation
- [ ] `mesh_adapter_receive_frame()` should call `fips_decrypt()` after reassembly
- [ ] FIPS handshake happens on first TX (initiator) or first RX (responder)

#### W4e: Wire nostr_store for mesh relay
- [ ] When `CONFIG_ENABLE_NOSTR_STORE=y`:
  - On successful `mesh_adapter_receive_frame()` + FIPS decrypt, parse as Nostr event
  - Store in `nostr_store` for later relay
  - On TX slot, relay stored events through mesh_adapter to next hop

**Acceptance**: Firmware builds with `CONFIG_ENABLE_MESH=y` and `CONFIG_ENABLE_MESH=n`. Both modes compile cleanly. Mesh mode binary is larger but includes all 7 protocol components.

---

### W5: Ground Station Compatibility Fix
**Priority**: High (current pipeline is broken)
**Effort**: Medium

#### W5a: Fix ground_station.py to read JSON from gs_main.cpp
- [ ] Rewrite `ground_station.py` sync logic: instead of looking for `\x42\x4C\x4E` binary sync word, parse JSON lines from stdin/serial
- [ ] Keep the CRC-16 validation as a fallback for raw binary mode (add `--mode json|binary` flag)
- [ ] Update telemetry struct parsing to use JSON fields instead of `struct.unpack`
- [ ] Add RSSI/SNR display from the JSON output
- [ ] Keep backward compatibility with test suite (14 tests must still pass)
- [ ] Update `tests/test_ground_station.py` for the new JSON-based parsing

#### W5b: Add WiFi uplink to gs_main.cpp
- [ ] Enable WiFi in `tracker/ground-station/receiver/sdkconfig.defaults` (only for ground station, NOT tracker)
- [ ] Add Kconfig options: WiFi SSID, password, Nostr relay URL
- [ ] Add WiFi station mode init in `gs_main.cpp`
- [ ] After receiving + decoding telemetry, POST JSON to configurable endpoint:
  - Option 1: HTTP POST to custom API
  - Option 2: WebSocket to Nostr relay (NIP-01)
  - Option 3: HTTP POST to Sondehub/sonde monitor
- [ ] Add mDNS announcement for local network discovery
- [ ] Add OTA update support (optional, nice-to-have)

**Acceptance**: `python3 ground_station.py --port /dev/ttyACM0 --mode json` displays telemetry correctly. With WiFi enabled, telemetry is also forwarded to a configurable endpoint. All 14 ground_station tests still pass.

---

### W6: Fix Nostr Bridge
**Priority**: Medium (needed for internet visibility of balloon)
**Effort**: Medium

#### W6a: Proper Nostr key derivation
- [ ] Replace `sha256(0x02 + nsec_bytes)` with proper secp256k1 public key derivation
- [ ] Use Python `coincurve` or `secp256k1` library for Schnorr signatures
- [ ] Or use `pynostr` library which handles all of this

#### W6b: Real Schnorr signatures
- [ ] Replace placeholder signature with actual Schnorr signing (NIP-01)
- [ ] Update `sign_event()` to use the derived pubkey + Schnorr

#### W6c: WebSocket relay publishing
- [ ] Replace `print("[RELAY] Would publish...")` with actual WebSocket client
- [ ] Use `websockets` or `aiohttp` library
- [ ] Implement NIP-01 EVENT message: `["EVENT", <event_json>]`
- [ ] Handle OK/NOTICE responses from relay
- [ ] Add retry logic for connection failures

#### W6d: Update tests
- [ ] Update `tests/test_telemetry_to_nostr.py` for real signing
- [ ] Add test for pubkey derivation correctness (known test vector)
- [ ] Add test for relay publishing (mock WebSocket)

**Acceptance**: `python3 telemetry_to_nostr.py --nsec <hex> --relay wss://relay.damus.io` publishes a valid, signed Nostr event that appears on the relay. All 11+ nostr tests pass.

---

### W7: Wirehair Unit Tests
**Priority**: Low (wirehair is for future mesh relay, not first flight)
**Effort**: Small

- [ ] Create `tracker/firmware/components/wirehair/test/test_wirehair.cpp` with proper assertions
- [ ] Test cases:
  - Encode N blocks, decode with all original blocks → success
  - Encode N blocks, drop K original blocks, decode with redundant blocks → success
  - N=1 edge case (single block, no erasure coding needed)
  - Large message (1000 bytes) roundtrip
  - Zero-length message handling
- [ ] Wire into `tests/test_c_host.py` as `TestWirehair` class
- [ ] Add to CI

**Acceptance**: Wirehair has 5+ structured unit tests with pass/fail assertions, integrated into CI.

---

### W8: Remove Dead Code and Clean Up
**Priority**: Low
**Effort**: Small

- [ ] Mark `tracker/firmware/components/lr2021/` as deprecated with a README
- [ ] Add `#warning "lr2021 component is deprecated, use RadioLib"` to `lr2021.h`
- [ ] Fix stale checkboxes in `SOFTWARE-SPRINT-PLAN.md`
- [ ] Fix stale duplicate sections in `tests/TEST-PLAN.md` (lines 86-105)
- [ ] Update `tests/TEST-PLAN.md` test count to 73 (currently says 72)
- [ ] Update `IMPLEMENTATION-PLAN.md` to reflect actual completion status
- [ ] Fix absolute-path symlink for `EspHalC3.h` in ground station (use relative path)
- [ ] Add `README.md` to `tracker/firmware/components/crypto/` explaining it's reserved for future use

**Acceptance**: No stale TODO checkboxes, no absolute-path symlinks, deprecated components clearly marked.

---

### W9: Bench Test Preparation
**Priority**: Medium (first hardware validation)
**Effort**: Medium
**Note**: This requires physical hardware — code prep can be done now, execution needs user at bench

#### W9a: Create bench test script
- [ ] Create `tools/bench_test.sh` that:
  1. Erases flash on both boards
  2. Flashes tracker firmware to Board 1 (`/dev/ttyACM0`)
  3. Flashes ground station to Board 2 (`/dev/ttyUSB0` or second ACM port)
  4. Opens monitor on ground station
  5. Waits for first telemetry reception
  6. Reports PASS/FAIL

#### W9b: Create hardware checklist document
- [ ] Create `docs/bench-test-checklist.md`:
  - Wiring diagram: ESP32-C3_Mini_V1 → LR2021 pin mapping (from AGENTS.md)
  - Power: USB-C for both boards (bench only)
  - Antenna: 868 MHz wire dipole on both (or just a piece of wire ~8.6cm)
  - Expected serial output for tracker
  - Expected serial output for ground station
  - Troubleshooting: common SPI failures, GPIO strapping, radio init errors

#### W9c: Add diagnostic commands to CLI
- [ ] Add `radio_test` CLI command: transmit a test packet without deep sleep
- [ ] Add `radio_recv` CLI command: switch to receive mode and print any incoming packets
- [ ] Add `i2c_scan` CLI command: scan I2C bus for BMP280 (address 0x76/0x77)
- [ ] Add `spi_test` CLI command: read LR2021 chip ID register and print it

**Acceptance**: Bench test script and checklist exist. CLI has diagnostic commands for radio, I2C, and SPI testing.

---

### W10: Ground Station Pipeline Integration
**Priority**: Medium (needed for mesh mode ground station)
**Effort**: Medium-Large
**Depends on**: W4 (mesh mode in tracker)

#### W10a: Add pipeline/FIPS to ground station
- [ ] Add `pipeline`, `erasure`, `frag`, `fips_transport`, `micro_ecc` to ground station CMakeLists REQUIRES
- [ ] Symlink or copy component sources into `receiver/components/`
- [ ] In `gs_main.cpp`, after receiving a LoRa packet:
  - If packet is 28 bytes → raw telemetry (existing behavior)
  - If packet is a fragment frame (has frag header) → feed to `mesh_adapter_receive_frame()`
  - If reassembly complete → FIPS decrypt → display/forward
- [ ] Add FIPS session state to ground station (responder role)
- [ ] Handle handshake MSG1/MSG2 exchange

#### W10b: Add multi-source tracking
- [ ] Track multiple balloon callsign_hashes in a ring buffer
- [ ] Display last-seen timestamp and packet count per source
- [ ] JSON output includes source identifier

**Acceptance**: Ground station can receive and decode both raw telemetry and mesh-encrypted/fragmented packets. Multiple balloons tracked simultaneously.

---

## Execution Order

```
Phase 1 (Foundation):
  W1 (Vendor RadioLib)           ← unblocks all builds
  W2 (Fix duplicated tests)      ← test integrity
  W8 (Clean up stale docs)       ← housekeeping

Phase 2 (Integration):
  W4 (Wire protocol into app_main) ← core integration work
  W3 (E2E host test)             ← validates W4 on host

Phase 3 (Ground Station):
  W5a (Fix ground_station.py)    ← unblocks bench test
  W6 (Fix Nostr bridge)          ← internet visibility

Phase 4 (Hardware Prep):
  W9 (Bench test prep)           ← ready for hardware

Phase 5 (Advanced):
  W5b (WiFi uplink to GS)        ← requires WiFi config
  W7 (Wirehair tests)            ← future-proofing
  W10 (GS pipeline integration)  ← full mesh ground station
```

## Estimated Effort

| Work Stream | Effort | New Tests | Files Changed |
|-------------|--------|-----------|---------------|
| W1: Vendor RadioLib | S | 0 | 3-5 |
| W2: Fix duplicated tests | S | 0 (better) | 4 |
| W3: E2E host test | M | 4-6 | 2-3 |
| W4: Integrate protocol stack | L | 2-3 | 5-8 |
| W5a: Fix ground_station.py | M | 0 (update 14) | 2 |
| W5b: WiFi uplink | M | 2-3 | 3-4 |
| W6: Fix Nostr bridge | M | 3-4 | 2-3 |
| W7: Wirehair tests | S | 5 | 2 |
| W8: Clean up | S | 0 | 5-7 |
| W9: Bench test prep | M | 0 (new files) | 3-4 |
| W10: GS pipeline integration | L | 3-4 | 5-8 |
| **Total** | **~3-4 focused sessions** | **~20 new** | **~35-50** |

## Test Count Trajectory

| Milestone | Host Tests | On-Target |
|-----------|------------|-----------|
| Current | 73 | 0 |
| After W2 | 73 (but testing real code) | 0 |
| After W3 | 77-79 | 0 |
| After W7 | 82-84 | 0 |
| After W4+W10 | 87-91 | 0 |
| After W9 (bench) | 87-91 | First! |

## Key Risks

1. **RadioLib submodule path** — ESP-IDF component manager expects `managed_components/` by default. Submodule at a different path may require CMake override. Mitigation: test on fresh clone immediately.
2. **FIPS RAM usage on ESP32-C3** — secp256k1 ECDH + ChaCha20-Poly1305 may be tight on a 400KB RAM device. Mitigation: measure with `esp_get_free_heap_size()` before and after FIPS operations.
3. **GPS test refactoring** — `gps.c` has ESP-IDF UART dependencies that may be hard to stub cleanly. Mitigation: extract parser functions into a separate `gps_parser.c` with no ESP-IDF deps.
4. **WiFi on ground station** — ESP32-C3 WiFi + RadioLib SPI may have interrupt contention. Mitigation: use `CONFIG_SPI_MASTER_ISR_IN_IRAM=y` (already set).
