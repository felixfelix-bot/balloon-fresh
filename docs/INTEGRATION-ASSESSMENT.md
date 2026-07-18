# Ground Station Receiver Assessment

**Date**: 2026-05-21
**Status**: 2 bugs found, fixes pending

## Current State

The ground station receiver firmware is at `tracker/ground-station/receiver/`. Code is complete but has 2 bugs preventing correct operation. RadioLib has not been fetched yet (needs `idf.py reconfigure`).

### Directory Structure

```
tracker/ground-station/receiver/
  CMakeLists.txt                    (project-level)
  sdkconfig.defaults                (ESP32-C3, 80 MHz, size opt)
  main/
    CMakeLists.txt                  (component registration)
    gs_main.cpp                     (application, 117 lines)
    EspHalC3.h                      (RadioLib HAL, 259 lines, identical to tracker)
    idf_component.yml               (RadioLib v7.6.0 dependency)
  components/
    telemetry -> ../../firmware/components/telemetry  (symlink)
```

### What Works
- Project structure is valid ESP-IDF layout
- RadioLib dependency declared correctly (`idf_component.yml`)
- EspHalC3.h is correct and identical to tracker version
- Telemetry component properly symlinked
- sdkconfig.defaults appropriate (80 MHz, SPI ISR in IRAM, -Os)
- Radio config matches tracker (868 MHz, BW125, SF9, CR4/7, sync 0x12, +22 dBm)
- `irqDioNum = 9` correct for NiceRF LoRa2021 DIO9
- JSON output format is well-designed (all fields + RSSI/SNR)

## Bugs Found

### P0: `readData()` Return Value Misuse

**File**: `main/gs_main.cpp:99,104`
**Severity**: Critical — no telemetry will ever be displayed

RadioLib's `LR11x0::readData()` returns `RADIOLIB_ERR_NONE` (value `0`) on success, NOT the number of bytes read. The comparison `len == TELEMETRY_SIZE` (28) is always false.

```cpp
// BROKEN (line 99):
int16_t len = radio->readData(buf, TELEMETRY_SIZE);
// BROKEN (line 104):
if (len == TELEMETRY_SIZE) {  // Always false — len is 0 on success
```

**Fix**:
```cpp
int16_t state = radio->readData(buf, TELEMETRY_SIZE);
if (state == RADIOLIB_ERR_NONE) {
```

### P1: Callback Registration Order

**File**: `main/gs_main.cpp:85,91`
**Severity**: Medium — first received packet silently lost

`startReceive()` is called before `setPacketReceivedAction()`. If a packet arrives between these two calls, the IRQ fires but no ISR is registered.

**Fix**: Swap lines 85-91 — register ISR first, then start receive.

### P2: RadioLib Not Fetched

`managed_components/` does not exist. Must run `idf.py reconfigure` before `idf.py build`.

### P3: Absolute Symlink

The telemetry symlink uses an absolute path. Should be relative for portability:
```
../../firmware/components/telemetry
```

## Build Steps (After Fixes)

```bash
source ~/esp/esp-idf/export.sh
cd tracker/ground-station/receiver
idf.py reconfigure    # Fetch RadioLib
idf.py build
idf.py -p /dev/ttyACM0 flash monitor
```

## Implementation Tasks

- [x] Fix P0: change `readData()` return value check to `state == RADIOLIB_ERR_NONE`
- [x] Fix P1: swap `setPacketReceivedAction()` before `startReceive()`
- [x] Fix P3: change symlink to relative path
- [x] Run `idf.py reconfigure` to fetch RadioLib
- [x] Run `idf.py build` to verify compilation — **BUILD SUCCESS** (181 KB binary, 82% partition free)
- [ ] Flash to second ESP32-C3_Mini_V1
- [ ] Bench test: tracker TX → ground station RX
