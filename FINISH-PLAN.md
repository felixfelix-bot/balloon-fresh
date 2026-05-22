# FINISH-PLAN.md — Comprehensive Plan to Complete All Remaining Work

**Created**: 2026-05-23
**Status**: Planning
**Scope**: Fix, integrate, test, and deploy everything identified in the integration audit

---

## Summary of Current State

- **15 firmware components** built with **82/82 tests passing** (17 C host + 65 Python)
- **Tracker firmware v0.2** compiles and builds OK (4.5MB ELF, 235KB BIN)
- **Ground station receiver** compiles with WiFi uplink (864KB BIN)
- **7 protocol components** (FIPS, pipeline, erasure, frag, TDMA, nostr_store, mesh_adapter) are **wired into app_main.cpp** via CONFIG_ENABLE_MESH
- **Ground station** reads JSON from gs_main.cpp, WiFi HTTP POST uplink working
- **Nostr bridge** has real Schnorr (BIP-340) signatures + WebSocket relay publishing
- **GPS/power_manager tests** now include production source (not duplicated)
- **`crypto` component** is unused but kept per user decision
- **RadioLib** vendored as git submodule (v7.6.0, pinned commit)
- **Wirehair** has 9/9 host tests (encode, decode, loss recovery, reuse)
- **No on-target testing has happened** — bench boards are ESP32-S3 TollGate routers, need ESP32-C3 + LR2021 hardware

---

## Work Streams

### W1: Vendor RadioLib as Git Submodule ~~DONE~~
**Priority**: High (blocks all ESP-IDF builds on fresh clones)
**Effort**: Small
**Status**: COMPLETE

- [x] Add RadioLib v7.6.0 as git submodule at `components/RadioLib` (shared between tracker + GS)
- [x] Update `idf_component.yml` in both projects to reference the local path instead of GitHub
- [x] Remove `managed_components/RadioLib` from both projects
- [x] Verify both `idf.py build` succeed
- [x] Add the submodule to `.gitignore` exceptions if needed
- [x] Verify fresh clone + submodule init + build works

**Acceptance**: `git clone --recurse-submodules` + `idf.py build` works without network access to GitHub

---

### W2: Fix Duplicated Tests ~~DONE~~
**Priority**: High (tests silently passing on stale code)
**Effort**: Small
**Status**: COMPLETE

#### W2a: Fix GPS test to include production source
- [x] Refactor `gps.c` to extract NMEA parsers to `gps_parser.h` (static inline, pure C, no ESP-IDF deps)
- [x] Update `test_gps.c` to include production parser via `gps_parser.h`
- [x] Verify all 8 GPS tests still pass

#### W2b: Fix power_manager test to include production source
- [x] Update `test_power_manager.c` to `#include "../power_manager.c"` instead of duplicating `raw_to_mv()`
- [x] Add ESP-IDF stubs: `esp_adc/adc_oneshot.h`, `esp_adc/adc_cali.h`, `esp_adc/adc_cali_scheme.h`
- [x] Verify all 5 power_manager tests still pass

**Acceptance**: Both test files compile against actual production source, not duplicated copies. Deliberate bugs in production code cause test failures.

---

### W3: End-to-End Host Integration Test ~~DONE~~
**Priority**: High (validates the full protocol stack as a unit)
**Effort**: Medium
**Status**: COMPLETE (4/4 tests passing)

- [x] Create `tracker/firmware/components/mesh_adapter/test/test_e2e.c`
- [x] Lossless telemetry roundtrip through full stack
- [x] Loss recovery with erasure coding
- [x] Out-of-order delivery
- [x] Single-frame payload (no fragmentation needed)
- [x] Wire into pytest as `TestEndToEnd`
- [x] Wire into pytest

### W4: Integrate Protocol Stack into app_main.cpp ~~DONE~~
**Priority**: High (the 7 protocol components are built but unused)
**Effort**: Medium-Large
**Status**: COMPLETE

#### W4a: Add Kconfig options for mesh mode
- [x] Add CONFIG_ENABLE_MESH, CONFIG_ENABLE_TDMA, CONFIG_ENABLE_NOSTR_STORE to `Kconfig.projbuild`

#### W4b: Update CMakeLists.txt
- [x] Add conditional REQUIRES based on CONFIG_ENABLE_MESH/TDMA/NOSTR_STORE

#### W4c: Wire mesh_adapter into app_main.cpp
- [x] When CONFIG_ENABLE_MESH=y, use mesh_adapter_send() instead of raw radio TX
- [x] Builds both ON and OFF (235KB BIN)

### W5: Ground Station ~~DONE~~
**Priority**: High (current pipeline is broken)
**Effort**: Medium
**Status**: COMPLETE

#### W5a: Fix ground_station.py to read JSON from gs_main.cpp
- [x] Added `--mode json|binary` flag (default: json)
- [x] New `decode_json_line()` parses gs_main.cpp JSON output
- [x] 20 ground_station tests passing

#### W5b: Add WiFi uplink to gs_main.cpp
- [x] WiFi STA mode with auto-reconnect
- [x] HTTP POST telemetry JSON to configurable endpoint
- [x] Kconfig: GS_WIFI_SSID, GS_WIFI_PASS, GS_UPLINK_URL
- [x] Graceful degradation (works without WiFi, serial-only)
- [x] GS BIN: 864KB (was 186KB, WiFi+HTTP stack)

### W6: Fix Nostr Bridge ~~DONE~~
**Priority**: Medium (needed for internet visibility of balloon)
**Effort**: Medium
**Status**: COMPLETE

#### W6a: Proper Nostr key derivation
- [x] Real secp256k1 x-only pubkey derivation via `coincurve`
- [x] 32-byte pubkey (NIP-01 compliant)

#### W6b: Real Schnorr signatures
- [x] BIP-340 Schnorr signatures via `coincurve.sign_schnorr()` (64 bytes)
- [x] No more DER or placeholder signatures

#### W6c: WebSocket relay publishing
- [x] `websockets` library for NIP-01 relay publishing
- [x] `publish_to_relay()` with real WebSocket connection

#### W6d: Update tests
- [x] 14 telemetry_to_nostr tests (was 11), includes pubkey + signing tests

### W7: Wirehair Unit Tests ~~DONE~~
**Priority**: Low (wirehair is for future mesh relay, not first flight)
**Effort**: Small
**Status**: COMPLETE (9/9 host tests)

- [x] Create `tracker/firmware/components/wirehair/test/test_wirehair.cpp` with proper assertions
- [x] Test cases: init, N=1 edge case, multi-block encode/decode, 30% loss recovery, recover_block, decoder_becomes_encoder, codec reuse, invalid inputs
- [x] Wire into `tests/test_c_host.py` as `TestWirehair` class
- [x] Added to CI

**Acceptance**: Wirehair has 5+ structured unit tests with pass/fail assertions, integrated into CI.

---

### W8: Remove Dead Code and Clean Up ~~IN PROGRESS~~
**Priority**: Low
**Effort**: Small
**Status**: IN PROGRESS

- [x] Fix stale duplicate sections in `tests/TEST-PLAN.md`
- [x] Update `tests/TEST-PLAN.md` test count to 82
- [x] Fix MISO/MOSI swap in `docs/execution-checklist.md`
- [x] Fix board name "XIAO" → "ESP32-C3_Mini_V1" in execution-checklist.md
- [x] Update FINISH-PLAN.md workstream statuses (W1-W7 → DONE)
- [x] Mark `tracker/firmware/components/lr2021/` as deprecated (already removed)
- [ ] Update `IMPLEMENTATION-PLAN.md` to reflect actual completion status
- [x] Fix absolute-path symlink for `EspHalC3.h` in ground station (now relative)
- [x] Add `README.md` to `tracker/firmware/components/crypto/` explaining it's reserved for future use

**Acceptance**: No stale TODO checkboxes, no absolute-path symlinks, deprecated components clearly marked.

---

### W9: Bench Test Preparation ~~DONE~~
**Priority**: Medium (first hardware validation)
**Effort**: Medium
**Status**: COMPLETE (code prep done, needs ESP32-C3 + LR2021 hardware)

#### W9a: Create bench test script
- [x] Create `tools/bench-test.sh` with mutex locking, auto-flash, telemetry wait

#### W9b: Create hardware checklist document
- [x] `docs/execution-checklist.md` exists with wiring diagram, pin mapping, power notes

#### W9c: Add diagnostic commands to CLI
- [x] `radio_test`: transmit a test packet without deep sleep
- [x] `radio_recv`: switch to receive mode and print any incoming packets (30s)
- [x] `i2c_scan`: scan I2C bus for BMP280 (address 0x76/0x77)

**Note**: Bench boards at /dev/ttyACM0,1 are ESP32-S3 TollGate routers. Need ESP32-C3 + LR2021 hardware for actual radio testing.

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

| Milestone | Total Tests | Status |
|-----------|------------|--------|
| Current | 82/82 | W1-W7, W9 COMPLETE, W8 IN PROGRESS |
| After W10 | ~86 | GS pipeline integration |
| After bench test | ~86 | First on-target test! |

## Remaining Work

| Work Stream | Status | What's Left |
|-------------|--------|-------------|
| W8: Clean up | IN PROGRESS | Update IMPLEMENTATION-PLAN.md |
| W10: GS pipeline integration | PENDING | FIPS decrypt + defragmentation in gs_main.cpp |

## Key Risks

1. **RadioLib submodule path** — ESP-IDF component manager expects `managed_components/` by default. Submodule at a different path may require CMake override. Mitigation: test on fresh clone immediately.
2. **FIPS RAM usage on ESP32-C3** — secp256k1 ECDH + ChaCha20-Poly1305 may be tight on a 400KB RAM device. Mitigation: measure with `esp_get_free_heap_size()` before and after FIPS operations.
3. **GPS test refactoring** — `gps.c` has ESP-IDF UART dependencies that may be hard to stub cleanly. Mitigation: extract parser functions into a separate `gps_parser.c` with no ESP-IDF deps.
4. **WiFi on ground station** — ESP32-C3 WiFi + RadioLib SPI may have interrupt contention. Mitigation: use `CONFIG_SPI_MASTER_ISR_IN_IRAM=y` (already set).
