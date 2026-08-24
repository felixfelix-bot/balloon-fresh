# E80 Hardware Integration Test — Findings & Bug Fixes

## Date: 2026-08-23

## Test Setup

- **Hardware:** 2× E80 STM32 boards with SX1280 radio, CH340 USB-UART bridge, CMSIS-DAP SWD probe
- **TX board:** /dev/ttyUSB4, SWD probe serial `148757200D2D1425`
- **RX board:** /dev/ttyUSB3, SWD probe serial `203584200D2D0D42`
- **Firmware:** `0561b29` (2.4GHz dual-band support)
- **Baud:** 2000000
- **Host:** T470 (i7-7600U, Ubuntu 26.04, openocd 0.12.0)
- **Config preset:** `configs/outdoor-10.json` (5 configs, mixed FLRC/LoRa)

## Bugs Found and Fixed

### Bug 1: `rx_lead` missing from inter-config schedule gap
**Severity:** Critical — RX had no time to re-arm between configs
**Root cause:** `build_preset_schedule()` computed inter-config gap as `expected_s + settle + guard` but omitted `rx_lead`. RX needs `rx_lead` seconds before each config to arm — without it, RX was still finishing the previous capture when the next config's TX burst started.
**Fix:** Added `rx_lead` to inter-config gap in `build_preset_schedule()`.
**Commit:** `5cda2f6`

### Bug 2: `cmd(expect_ok=False)` still blocked waiting for reply
**Severity:** High — fire-and-forget commands like STOP and ROLE NONE would hang
**Root cause:** `BoardSerial.cmd()` with `expect_ok=False` still called `readline()` waiting for a response, defeating the purpose of a non-blocking send.
**Fix:** Made `expect_ok=False` truly fire-and-forget — send only, no read.
**Commit:** `5cda2f6`

### Bug 3: No SWD reset between modulation changes
**Severity:** Critical — SX1280 cannot hot-switch modulation parameters
**Root cause:** The SX1280 radio chip cannot change SF/BR/BW via the firmware `MOD` command at runtime. Firmware returns "OK MOD" but the radio doesn't reconfigure. `e80_campaign.py` had `maybe_reset()` for this, but `e80_bench_ctl.py` did not.
**Fix:** Added SWD reset (openocd `reset halt; resume`) between configs when `mod`, `sf`, `br`, or `bw` changes. Added `_mod_params_changed()` helper for detection. Added `swd_reset_maybe()` to both `run_tx_mode` and `run_rx_mode`.
**Commit:** `b199549`

### Bug 4: STOP command triggers IWDG watchdog reset
**Severity:** High — TX board would randomly reset between configs
**Root cause:** The firmware `STOP` command triggers an IWDG watchdog reset on the STM32. This was used on the TX side between configs to stop ongoing transmissions, but it caused the board to reboot unpredictably.
**Fix:** Removed `STOP` command from TX side between configs. Replaced with `drain()` (same as RX side already did).
**Commit:** `b199549`

### Bug 5: Off-by-one in `build_preset_schedule()` SWD reset gap
**Severity:** Critical — config 1 (FLRC-2600) received 0/10 packets
**Root cause:** The `swd_reset_s` extra time was added AFTER `starts.append(t)`, meaning it shifted all *subsequent* configs' start times but did NOT add gap time before the *current* config's SWD reset. This meant:
- cfg0→cfg1 (first mod-change transition): 0.0s available for SWD reset → boards still in old config → 0/10 received
- cfg1→cfg2, cfg2→cfg3, cfg3→cfg4: 10.0s available (from *previous* transition's extra) → works correctly

**Fix:** Moved `t += extra` to BEFORE `starts.append(t)`, so the SWD reset time is included in the gap before the config that needs it:
```python
# BEFORE (buggy):
starts.append(t)
extra = swd_reset_s if (prev is not None and _mod_params_changed(prev, c)) else 0
t += c["expected_s"] + settle + guard + rx_lead + extra  # extra shifts NEXT config

# AFTER (fixed):
extra = swd_reset_s if (prev is not None and _mod_params_changed(prev, c)) else 0
t += extra  # Add extra BEFORE this config's start time
starts.append(t)
t += c["expected_s"] + settle + guard + rx_lead
```
**Commit:** (this run)

### Bug 6: TX crashes on STAT? timeout after SWD reset
**Severity:** Medium — TX process dies after first SWD reset, preventing remaining configs from running
**Root cause:** After SWD reset + serial reopen, the board needs boot time. The TX polling loop calls `board.stat()` immediately, which can time out if the board isn't ready yet. This exception propagated uncaught and killed the TX process.
**Fix:** Wrapped `board.stat()` calls in try/except in both TX and RX modes. On error, keep last known `sent_ok` value and continue polling.
**Commit:** (this run)

## Test Results

### Run 1: Quick FLRC test (2 configs, no mod switching)
**Date:** 2026-08-23 18:47
**Config:** `/tmp/quick-flrc.json`

| Config | Label | Sent | Received | PER |
|--------|-------|------|----------|-----|
| 0 | FLRC-650 LEN64 | 10 | 10 | 0% |
| 1 | FLRC-650 LEN255 | 10 | 11 (10 CRC ok) | 0% |

### Run 2: Outdoor-10 (5 configs, with mod switching, pre-fix)
**Date:** 2026-08-23 18:57
**Config:** `outdoor-10.json`
**SWD reset:** Yes, but with off-by-one bug (Bug 5)

| Config | Label | Sent | Received | PER | Notes |
|--------|-------|------|----------|-----|-------|
| 0 | FLRC-650 LEN64 | 10 | 10 | 0% | ✓ |
| 1 | FLRC-2600 LEN64 | 10 | 0 | 100% | ✗ Bug 5: no SWD time for first transition |
| 2 | LoRa-SF7 BW125 LEN64 | 10 | 10 | 0% | ✓ (benefited from prev extra) |
| 3 | LoRa-SF12 BW125 LEN64 | 10 | 10 | 0% | ✓ |
| 4 | FLRC-650 LEN255 | 10 | 10 | 0% | ✓ |

### Run 3: Outdoor-10 (5 configs, post-fix, with STAT? resilience)
**Date:** 2026-08-23 19:30+
**Config:** `outdoor-10.json`
**Fixes applied:** Bug 5 (off-by-one) + Bug 6 (STAT? timeout)

(Results in test-data files)

## Root Cause Analysis: Config 1 (FLRC-2600) Failure

**Question:** Why did config 1 (FLRC-2600) fail while configs 2-4 succeeded?

**Answer:** Off-by-one in schedule gap calculation (Bug 5). The `swd_reset_s` extra time was added to the NEXT config's offset, not the CURRENT one. The first mod-change transition (cfg0→cfg1) got zero SWD reset time. Later transitions got 10s because they inherited the extra from the PREVIOUS transition.

**Proof:** Standalone test of FLRC-2600 (single config, no mod switching) passed perfectly — 10/10 received at RSSI -41 to -42 dBm. The radio mode itself is not broken.

**Fix verification:** After moving `t += extra` before `starts.append(t)`, the schedule gives 10.0s SWD time for ALL transitions including cfg0→cfg1. Run 3 shows config 1 now receiving 10/10 packets.

## Key Lessons

1. **SX1280 cannot hot-switch modulation parameters** — must SWD reset between configs that change mod/sf/br/bw
2. **STOP command triggers IWDG watchdog** — use drain() instead
3. **Schedule gap calculations need careful ordering** — extra time must be added BEFORE the config that needs it, not after
4. **Serial communication after SWD reset needs retry logic** — board boot time is variable
5. **NTP sync is sufficient for distributed operation** — 32s margin (rx_lead=10s + guard=20s + settle=2s) absorbs any clock drift

### Run 3: Outdoor-10 (5 configs, post-fix, ALL FIXES APPLIED)
**Date:** 2026-08-23 19:37
**Config:** `outdoor-10.json`
**Fixes applied:** Bug 5 (off-by-one schedule gap) + Bug 6 (STAT? timeout resilience)

| Config | Label | Sent | Received | CRC OK | PER | RSSI | SNR |
|--------|-------|------|----------|--------|-----|------|-----|
| 0 | FLRC-650 LEN64 | 10 | 10 | 10 | 0% | -41.7 | 0.0 |
| 1 | FLRC-2600 LEN64 | 10 | 10 | 10 | 0% | -41.8 | 0.0 |
| 2 | LoRa-SF7 BW125 LEN64 | 10 | 10 | 10 | 0% | -42.0 | 14.6 |
| 3 | LoRa-SF12 BW125 LEN64 | 10 | 10 | 10 | 0% | -42.0 | 10.0 |
| 4 | FLRC-650 LEN255 | 10 | 10 | 10 | 0% | -41.8 | 0.0 |

**RESULT: 50/50 packets received. 0% PER. ALL 5 CONFIGS PASS.**

SWD reset fired correctly on all 4 mod-change transitions (0→1, 1→2, 2→3, 3→4).
STAT? timeout resilience prevented TX crash after SWD reset.

### Known Issue: merge_csvs.py pkt_idx mismatch
The firmware does not reset pkt_idx counter between configs — it increments globally.
Config 0 gets pkt_idx 9-18, config 1 gets 19-28, etc.
merge_csvs.py expects per-config pkt_idx starting at 0, causing false packet loss in merge report.
This is a merge script bug, NOT a hardware issue. RX confirmed 10/10 per config via board STAT?.
