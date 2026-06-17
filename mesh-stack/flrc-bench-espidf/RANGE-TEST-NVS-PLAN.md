# Range Test NVS Logging Plan

## Problem
- TX board (MAC 96:DC) keeps disconnecting from USB — unreliable serial monitoring
- During outdoor range tests, USB may disconnect due to movement/vibration
- If USB drops, all serial CSV data is lost
- Need offline data logging to NVS flash as fallback

## Solution
Both TX and RX log per-window summaries to NVS flash. A dedicated DUMP firmware variant
reads NVS and outputs CSV over serial for data recovery.

## Current State
- RX side: already saves per-window results to NVS via `NvsTestResult` struct (range_test.cpp:344-371)
- TX side: no NVS logging — all data lost if USB disconnects
- No way to recover NVS data without recompiling firmware

## Checklist

### Phase 1: Extend NVS Schema
- [ ] Add GPS fields to `NvsTestResult` (gps_lat, gps_lon, gps_alt, gps_sats, gps_hdop, gps_fix)
- [ ] Add loop_count field to `NvsTestResult`
- [ ] Add role field (TX vs RX) to distinguish data sources
- [ ] Update `nvs_print_all_results()` CSV header and output format

### Phase 2: TX NVS Logging
- [ ] Add NVS init + clear at TX boot
- [ ] Save per-window summary after each TX window completes
- [ ] Track: window name, packets sent, elapsed time, throughput
- [ ] Add loop counter to NVS ( survives across loops )

### Phase 3: RX NVS Enhancement
- [ ] Save GPS coordinates per window in NVS
- [ ] Save loop counter in NVS

### Phase 4: DUMP Mode
- [ ] Add `BENCH_MODE_DUMP` to Kconfig.projbuild
- [ ] Create `dump_main.cpp` with `#include <sdkconfig.h>` guard
- [ ] Dump mode: boot → read all NVS → output CSV to serial → halt
- [ ] Update `range_test.cpp` guard to exclude when DUMP mode selected
- [ ] Update `bench_main.cpp` guard to exclude when DUMP mode selected
- [ ] Update `autonomous_main.cpp` guard to exclude when DUMP mode selected

### Phase 5: Build & Flash
- [ ] Update CMakeLists.txt with new source files
- [ ] Build range_tx.bin with NVS logging
- [ ] Build range_rx.bin with GPS+NVS
- [ ] Build range_dump.bin for data recovery
- [ ] Flash and verify on hardware

## NVS Storage Budget
- NVS partition: ~24KB on ESP32-C3 (4MB flash, default partition table)
- `NvsTestResult` struct: ~80 bytes per window
- 16 windows per loop × 80 bytes = ~1.3KB per loop
- Can store ~300 window results (18+ loops) before filling
- Blobs stored as `test_0` ... `test_N` in "bench" namespace

## Build Variants
| Binary | Kconfig | Purpose |
|--------|---------|---------|
| range_tx.bin | BENCH_MODE_RANGE_TX | TX side, NVS logging |
| range_rx.bin | BENCH_MODE_RANGE_RX + RANGE_TEST_GPS | RX side, GPS + NVS |
| range_dump.bin | BENCH_MODE_DUMP | NVS data recovery via serial |
| auto_tx.bin | BENCH_MODE_AUTONOMOUS_TX | Autonomous benchmark TX |
| interactive.bin | BENCH_MODE_INTERACTIVE | Manual benchmarker |

## Data Recovery Workflow
1. Run range test (TX + RX boards, USB optional)
2. Both boards log per-window summaries to NVS flash
3. To recover data: flash `range_dump.bin` to board
4. Board boots, reads NVS, outputs CSV to serial
5. Capture CSV with `monitor_range.py` or `minicom`
6. Board halts with LED blink pattern indicating dump complete
