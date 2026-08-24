# Firmware Bug Root Cause Analysis + Fix Plan
# Date: 2026-07-26
# Status: EXECUTING

## ROOT CAUSE ANALYSIS

### BUG 1 — BLOCKING: Makefile uses wrong PlatformIO env names

**Symptom**: 40% PER on FLRC, tx_fw=unknown in packets
**Root cause**: Makefile defines `TX_ENV = rp2040-sweep-tx` and `RX_ENV = rp2040-sweep-rx`
These compile the OLD firmware:
  - `rp2040-sweep-tx` → `multi_radio_sweep.cpp` (NO CRC24, NO V4 fixes)
  - `rp2040-sweep-rx` → `multi_radio_sweep_rx.cpp` (old RSSI, old phase logic)

The V4 firmware (all fixes) is in:
  - `rp2040-sweep-tx-v4` → `multi_radio_sweep_gps_v4.cpp` (CRC24, GPS, ms-precision)
  - `rp2040-sweep-rx-v4` → `multi_radio_sweep_rx_v4.cpp` (9-bit RSSI, CRC guard)

**Impact**: `make flash-tx/rx` flashes OLD firmware. Felix's laptop would get broken firmware.
**Fix**: Change 2 lines in Makefile: `TX_ENV = rp2040-sweep-tx-v4`, `RX_ENV = rp2040-sweep-rx-v4`

### BUG 2 — COSMETIC (consequence of BUG 1): tx_fw=unknown
**Cause**: Old envs lack `extra_scripts = pre:tools/inject_git_version.py`
**Fix**: Auto-resolved when BUG 1 is fixed (V4 envs have the script)

### BUG 3 — NOT A BUG: CALIB_FRONT_END per phase
**Finding**: Both TX and RX call `rfCalibrate()` inside `rfInitForPhase()`. Working correctly.

### BUG 4 — EXPECTED: FLRC 40% PER at close range
**Finding**: AGC saturation at 30cm with +10dBm TX. BER=0.00 on decoded packets.
**Action**: Re-test after BUG 1 fix. If PER drops significantly, old firmware was the cause.

### BUG 5 — EXPECTED: Phase sync loss on later phases
**Finding**: TX's getBestUnixTime() degrades after 10s without GPS update (GPS_TIME_STALE_MS).
**Action**: Not a bug. For walk tests, GPS maintains lock outdoors. Document this.

## FIX PLAN

### Step 1: Fix Makefile env names (orchestrator — infrastructure)
Change TX_ENV and RX_ENV to V4 env names.

### Step 2: Re-flash both boards with V4 firmware
make flash-tx && make flash-rx (now using V4 envs)

### Step 3: Re-run 300s sweep capture
Verify: CRC24 working, tx_fw=git hash, PER improvement

### Step 4: Delegate results to sub-managers for consensus
range-tests: verify TX V4 fixes active
speed-tests: verify RX V4 fixes active

### Step 5: Commit + push fix
