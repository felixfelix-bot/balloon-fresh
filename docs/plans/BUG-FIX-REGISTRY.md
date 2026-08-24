# BUG-FIX-REGISTRY: `github/master` ↔ `github/range-tests` Firmware Diff

**Date**: 2026-07-26
**Analyst**: Subagent (manager profile)
**Scope**: Functional firmware + tooling differences between `github/master` and `github/range-tests` in `~/repos/balloon-fresh`
**Method**: `git diff github/master github/range-tests -- <file>` for every key file; commit archaeology for the three named fixes.

> **Diff convention**: In all `git diff master range-tests` output, `-` lines are **master-only** and `+` lines are **range-tests-only**. The `github/range-tests` branch is 179 commits ahead of master and is the more feature-complete codebase. The three named master commits (`dce248f`, `0880443`, `2752fa1`) are **NOT merge-ancestors** of `range-tests`, but in two of three cases the *same bug* has been independently fixed on `range-tests` via a different code path.

---

## 1. Critical Questions Answered First

The task asked three yes/no questions. Answers + evidence:

### Q1: Does `range-tests` have the `totalCycleSec` accumulation fix (`dce248f` on master)?
**YES — SUPERSEDED.** Range-tests solves the same bug with a cleaner implementation.

| | master (`dce248f`) | range-tests |
|---|---|---|
| Fix location | `rx_v4.cpp` SET_TIME handler — adds `totalCycleSec = 0;` inside BOTH the interleave and non-interleave branches (2-line patch) | `rx_v4.cpp` SET_TIME handler — moves the reset to BEFORE the `if (interleaveMode)` branch and also resets the new `totalCycleMs` variable |
| Commit | `dce248f` (Sun Jul 26 16:12) | Folded into the ms-precision refactor commit `e303327` ("fix(rx): ms-precision phase computation matches TX") |

**Both branches reset before accumulating, so the unbounded-growth bug is absent on both.** Range-tests additionally resets `totalCycleMs` (a new variable that does not exist on master). **Classification: SUPERSEDED.**

### Q2: Does `range-tests` have RMC time parsing without GPS fix (`0880443` on master)?
**YES — CONFLICTING IMPLEMENTATION (functionally equivalent).**

| | master (`0880443`) | range-tests |
|---|---|---|
| Strategy | **Two-step parse**: (1) minimal sscanf `"$%*2sRMC,%12[^,],%c"` extracts time+status always; (2) second sscanf for lat/lon only when `status == 'A'` | **Single sscanf**: `"$%*2sRMC,%15[^,],%c,%15[^,],%c,%15[^,],%c,"` parses all 6 fields in one call; uses `parsed >= 2` threshold so time+status are captured even when position fields are empty (sscanf stops at `,,`) |
| GGA handling | `parsed >= 6` required | `parsed >= 1` (time-only) |
| Debug logging | `RMC_DEBUG` lines for first 5 sentences | Removed |
| Commit | `0880443` (Sun Jul 26 07:31) | `ce2a3da` ("fix(tx): NMEA parser — extract time from RMC/GGA with empty fields") |

Both approaches correctly extract UTC time from RMC sentences with `V` status (no fix). **Classification: CONFLICT** — different code, same outcome. Range-tests' single-sscanf is simpler but more fragile if NMEA fields are reordered; master's two-step is more explicit. **Pick one during merge — do not combine.**

### Q3: Does `range-tests` have TX 5s boot instead of 60s gate (`2752fa1` on master)?
**NO — GENUINE CONFLICT. Range-tests reverted to a stricter 60s gate with a no-transmit WAIT state.**

| | master (`2752fa1`) | range-tests |
|---|---|---|
| Boot gate | `while (!gps.hasTime && (millis()-gpsStart) < 5000)` — 5s non-blocking probe, then starts sweeping on `millis()` fallback | `while (!gps.hasTime)` with internal `if ((millis()-gpsStart) > GPS_FIX_TIMEOUT_MS) break;` where `GPS_FIX_TIMEOUT_MS = 60000` (60s) |
| After timeout | TX starts transmitting immediately using `millis()` as time source; switches to GPS UTC when satellites arrive | TX enters `WAITING_FOR_GPS_TIME` state — **does NOT transmit** until GPS time or laptop `SET_TIME` arrives |
| Laptop override | None — SET_TIME processed in main loop only | `if (hasLaptopTime()) break;` — bench mode bypasses the gate |
| Beacon | `sendBeacon()` every 5s (BEACON_INTERVAL_MS) — removed in range-tests | Removed entirely; status folded into 10s heartbeat |
| Comment | `2752fa1`: "60s blocking GPS wait caused millis() fallback → phase desync" | Range-tests explicitly re-adds the gate: "TX will NOT transmit until GPS FIX acquired" |

**Classification: CONFLICT.** This is the single most important decision for the merge.
- **Master's philosophy** (2752fa1): start fast, fix desync later. TX transmits unsynced but becomes synced when GPS locks.
- **Range-tests' philosophy** (ADR-018, commit `98795c0`): **never transmit without GPS fix** (Felix's requirement). TX stays silent on a power bank until satellites are acquired. The sweep loop still runs (radio reconfigs continue) so TX is phase-ready the instant fix returns.

**Recommendation**: keep range-tests' approach for balloon deployments; keep master's 5s probe as a documented bench-mode shortcut only.

---

## 2. File-by-File Registry

### 2.1 `firmware/rp2040/src/multi_radio_sweep_gps_v4.cpp` (TX firmware)

**Lines changed**: ~400 (large diff). Range-tests is the more evolved version.

| # | Difference | Classification | Detail |
|---|---|---|---|
| TX-1 | **Phase table reordered**: FLRC narrow→wide before SF12 (was SF12→FLRC). Both HF and LF paths. | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Reduces harsh modulation transitions. Master has SF12 in position 3; range-tests moves it to position 7 (last in HF). Commit `0a9fa51`. |
| TX-2 | **Channel sweep added**: 13 WiFi-channel HF freqs + 8 EU-868 LF freqs appended to interleave table. `interleavePhases[64]` → `[128]`. | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Commit `0562e73`. Master has no channel sweep capability. |
| TX-3 | **FLRC slot time 2000ms → 3000ms** | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Reliable reconfig window. Commit in the V4-walk series. |
| TX-4 | **Unified time selector `getBestUnixTime()`** | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Priority: fresh GPS > GPS hold (millis+offset) > laptop SET_TIME > degraded. Master uses inline if/else chains. Commit `25dac1b`. |
| TX-5 | **GPS time hold (`gpsTimeOffset`)** | BUG_FIX_IN_RANGE_NOT_IN_MASTER | If GPS goes stale (>10s), extrapolate from `millis() + offset`. RP2040 crystal accurate enough over minutes. Master has no hold — drops to `millis()` or laptop. Commit `25dac1b`. |
| TX-6 | **`abortTxIfActive()`** — force SET_STANDBY before phase reconfig | BUG_FIX_IN_RANGE_NOT_IN_MASTER | SF12-255B takes ~8s; if phase boundary falls during TX, radio is mid-transmission. Master has no abort → hardware reset during active TX → undefined state. |
| TX-7 | **TX spin timeout 6s → 16s** | BUG_FIX_IN_RANGE_NOT_IN_MASTER | LF-LoRa-SF12-32B takes ~13s. Master's 6s timeout always expired mid-TX. |
| TX-8 | **TX_TIMEOUT log** when IRQ doesn't fire | COSMETIC | Diagnostic only. |
| TX-9 | **FLRC modulation params `0x25` → `0x15`** | BUG_FIX_IN_RANGE_NOT_IN_MASTER | CR=3/4 + BT=0.5 (FEC enabled). Master had CR=1 + BT=0.5. Commit `0a9fa51`. |
| TX-10 | **FLRC packet params `0x0C,0x4C` → `0x0E,0x7C`** | BUG_FIX_IN_RANGE_NOT_IN_MASTER | CRC24 + Match123 sync (was CRC16-off + Match1). Matches TheClams reference. Commit `7f5e2bd`. |
| TX-11 | **LoRa packet params: hardcoded `LORA_PKT_SIZE` → dynamic `p.pktSize`** | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Master always used compile-time constant; range-tests uses per-phase size. |
| TX-12 | **Dynamic phase-transition guard (500ms or 1000ms)** | BUG_FIX_IN_RANGE_NOT_IN_MASTER | 1000ms when next phase changes modulation type or RF band. Master always uses flat 500ms. |
| TX-13 | **SF12 recovery delay (500ms extra)** | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Extra settle time after SF12 phases. |
| TX-14 | **CDC watchdog guard `if (Serial && ...)`** | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Prevents reboot on power bank (no USB host). Master would reboot and lose `utcOffset`. Commit `3efdebe`. |
| TX-15 | **CDC watchdog disarmed on SET_TIME** | BUG_FIX_IN_RANGE_NOT_IN_MASTER | `lastCdcSuccessMs = 0` after time sync — bench mode stays stable. Commit `3efdebe`. |
| TX-16 | **GPS fix gate (TX never transmits without fix)** | CONFLICT with 2752fa1 | See Q3 above. Commit `98795c0` (ADR-018). |
| TX-17 | **`totalCycleMs` — ms-precision phase computation** | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Eliminates 15-28s accumulated truncation drift over 56 phases. Master uses seconds-only. Commit `e303327`. |
| TX-18 | **Beacon removed** (`BEACON_INTERVAL_MS`, `lastBeaconMs`, `sendBeacon()`) | SUPERSEDED | Master's 2752fa1 added beacon; range-tests removed it (status in heartbeat). |
| TX-19 | **RMC parser: single-sscanf vs two-step** | CONFLICT with 0880443 | See Q2 above. |
| TX-20 | **GGA parser: `parsed >= 6` → `parsed >= 1`** | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Time extraction from GGA even without fix. |
| TX-21 | **NMEA_RAW passthrough in boot gate** | COSMETIC | Debug aid for GPS module diagnostics. |
| TX-22 | **Boot gate: indefinite wait + 60s timeout + laptop override** | CONFLICT with 2752fa1 | See Q3 above. |
| TX-23 | **Channel-sweep frequency override (`getChannelFreq()`)** | BUG_FIX_IN_RANGE_NOT_IN_MASTER | 7 HF + 5 LF characterization channels. Commit `0562e73`. |

### 2.2 `firmware/rp2040/src/multi_radio_sweep_rx_v4.cpp` (RX firmware)

**Lines changed**: ~350. Range-tests is the more evolved version.

| # | Difference | Classification | Detail |
|---|---|---|---|
| RX-1 | **Phase table reordered** (matches TX) | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Same as TX-1. TX/RX phase tables MUST match for decode. |
| RX-2 | **Channel sweep added** (matches TX) | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Same as TX-2. |
| RX-3 | **FLRC slot time 2000ms → 3000ms** (matches TX) | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Same as TX-3. |
| RX-4 | **`totalCycleMs` ms-precision phase computation** | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Same fix as TX-17. Commit `e303327`. |
| RX-5 | **`totalCycleSec = 0` reset in SET_TIME handler** | SUPERSEDED | See Q1. Master's `dce248f` adds the reset inside both branches; range-tests moves it before the branch + adds `totalCycleMs = 0`. **Same bug, fixed differently — no data loss either way.** |
| RX-6 | **Phase-sync from TX packets** (`txPhaseId` extraction) | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Once any packet decodes, RX jumps to TX's actual phase instead of relying on drifting `millis()`. Commit `1fc9a72`. |
| RX-7 | **CRC buffer-overread guard** (`gpsOff + crcLen + 2 > readLen` bounds check) | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Prevents buffer overread on false sync matches. Commit `1fc9a72`. |
| RX-8 | **RX buffer `rxBuf[256]` → `rxBuf[264]`** + read 8 extra bytes | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Room for chip framing prefix (syncOffset 0-2). |
| RX-9 | **FLRC modulation `0x25` → `0x15`** (matches TX) | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Same as TX-9. |
| RX-10 | **FLRC packet params `0x0C,0x4C` → `0x0E,0x7C`** (matches TX) | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Same as TX-10. Commit `7f5e2bd`. |
| RX-11 | **TX-alive beacon detection** (`phaseId == 0xFE`) | COSMETIC | Logs when TX is searching for GPS. |
| RX-12 | **BER analysis** (bit-error-rate on fill pattern) | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Compares received bytes to expected `byte[i]=i&0xFF`. Per-packet BER logging. |
| RX-13 | **Dynamic phase-transition guard (500ms/1000ms)** (matches TX) | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Same as TX-12. |
| RX-14 | **LORA_CFG log includes frequency** | COSMETIC | `freq=%.1f` added to diagnostic. |
| RX-15 | **APP_CRC_FAIL log includes pktSize** | COSMETIC | `pSz=%d` added. |

### 2.3 `firmware/rp2040/platformio.ini`

**Lines changed**: ~250 (massive expansion on range-tests).

| # | Difference | Classification | Detail |
|---|---|---|---|
| PIO-1 | **`default_envs` changed**: master = `rp2040` (single generic env); range-tests = `rp2040-sweep-tx-v4, rp2040-sweep-rx-v4` | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Master's default env doesn't build the V4 sweep firmware. |
| PIO-2 | **Shared `[env]` base config** with `board_build.core = earlephilhower` | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Master has a single `[env:rp2040]` with RadioLib dep. Range-tests factors out shared config and DROPS RadioLib (raw SPI). |
| PIO-3 | **RadioLib dependency removed** | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Master: `lib_deps = jgromes/RadioLib @ ^7.6.0`. Range-tests: no lib_deps for sweep envs. Aligns with ADR-020 (ban RadioLib for LR2021). |
| PIO-4 | **~30 new build environments added** | BUG_FIX_IN_RANGE_NOT_IN_MASTER | range-tx, range-rx, range-tx-auto, range-rx-auto, per-bitrate (1300/650/325), per-power (p0/p3/p6/p9/p12/p125), sweep-tx/rx-v3, sweep-tx/rx-v4, dual-tx/rx, gps-tx/rx, lora-868-tx/rx, gps-time-test, raw-rx-127, raw-rx-debug, etc. |
| PIO-5 | **Throughput envs removed** (`rp2040-throughput-tx/rx`) | SUPERSEDED | Replaced by sweep envs. |

### 2.4 `Makefile`

**Lines changed**: ~125 (complete rewrite). This is a **CONFLICT** — the two Makefiles serve completely different purposes.

| | master | range-tests |
|---|---|---|
| Purpose | **PlatformIO build/flash/monitor** for RP2040 sweep firmware | **BOOTSEL flashing** via ESP32 controller or 1200-baud touch |
| Key targets | `flash-tx`, `flash-rx`, `flash-all`, `build-all`, `monitor-tx`, `monitor-rx`, `walk-test`, `test`, `test-unit`, `clean` | `bootsel-build`, `bootsel-flash`, `bootsel-trigger`, `bootsel-flash-rp2040`, `bootsel-1200`, `bootsel-1200-tx/rx/both`, `identify-ports` |
| Board serials | `TX_SERIAL = E663B035977F242D`, `RX_SERIAL = E663B035973B8332` | Uses serial suffixes `8332` and `F242D` (same boards, different matching) |
| Walk test | `make walk-test` → `walk_capture.py` | No walk-test target (uses shell scripts directly) |
| Testing | `make test` → pytest | No test target |

**Classification: CONFLICT.** These are not reconcilable by simple merge — they need to be combined into one Makefile with both sets of targets. The master Makefile's `flash-tx/rx` targets use PlatformIO upload (which requires the firmware to be compiled), while range-tests' `bootsel-1200` targets flash pre-built UF2 files. **Both approaches are needed.**

### 2.5 `tools/` Directory

**Net change**: range-tests deleted 15 scripts and added 14 new ones. Two files (`pio_upload_guard.py`, `walk-capture.sh`) show `M` status but have **zero content diff** (mode/hash only).

#### Deleted on range-tests (present on master only)

| File | Classification | Note |
|---|---|---|
| `tools/walk_capture.py` | **BUG_FIX_IN_MASTER_NOT_IN_RANGE** | Master's `0880443` rewrote this to 537 lines: auto-reconnect, serial-number detection, timestamped files, zero data loss. **Range-tests deleted it** and replaced with `tools/walk_capture.sh` (a simpler dual-serial shell script). The Python version is more robust. |
| `tools/walk-capture-v2.sh`, `walk-capture-v3.sh` | SUPERSEDED | Evolved into `walk_capture.sh`. |
| `tools/board-lock-assert.py`, `board-lock-monitor.py`, `board-serial.py`, `board_serial.py`, `board_serial_guard.py`, `test-board-lock.py` | SUPERSEDED | Board mutex/lock infrastructure removed — range-tests uses `identify-ports` in Makefile instead. |
| `tools/definitive-capture.sh`, `direct_sync_capture.py`, `overnight-monitor.sh`, `time-sync-daemon.sh`, `time_forward_capture.py`, `walk_sync_capture.py` | SUPERSEDED | One-off capture scripts replaced by unified tools below. |

#### Added on range-tests (not on master)

| File | Classification | Note |
|---|---|---|
| `tools/walk_capture.sh` | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Dual serial capture (USB CDC + ESP32 bridge). Simpler than Python but less robust. |
| `tools/capture_rx_sweep.py` | BUG_FIX_IN_RANGE_NOT_IN_MASTER | RX sweep capture tool. |
| `tools/capture_with_timesync.py` | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Capture with SET_TIME injection. |
| `tools/flash_board.py` | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Board flash utility (serial-number based). |
| `tools/inject_git_version.py` | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Injects git hash into firmware build banner. |
| `tools/parse_unified_csv.py` | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Parses unified CSV capture format. |
| `tools/plot_characterization.py`, `plot_full_characterization.py`, `plot_range_sweep.py` | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Plotting tools for range/characterization data. |
| `tools/pre-walk-check.sh`, `pre_flight_check.sh` | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Pre-flight diagnostics. |
| `tools/rx_range_logger.py` | BUG_FIX_IN_RANGE_NOT_IN_MASTER | RX range logger (moved from `scripts/`). |
| `tools/test_runner.py` | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Test runner. |
| `tools/verify_flash.sh` | BUG_FIX_IN_RANGE_NOT_IN_MASTER | Flash verification. |
| `tools/99-balloon-boards.rules` | BUG_FIX_IN_RANGE_NOT_IN_MASTER | udev rules for board identification. |

#### Modified but identical content

| File | Classification |
|---|---|
| `tools/pio_upload_guard.py` | COSMETIC (0-line diff — mode/hash only) |
| `tools/walk-capture.sh` | COSMETIC (0-line diff — mode/hash only) |

---

## 3. Summary Classification Matrix

| Classification | Count | Action Required |
|---|---|---|
| **BUG_FIX_IN_RANGE_NOT_IN_MASTER** | 28 | Adopt range-tests version. Master is missing these fixes/features. |
| **BUG_FIX_IN_MASTER_NOT_IN_RANGE** | 1 | `tools/walk_capture.py` (537-line robust Python capture). **Preserve this file** — do not let the merge delete it. Consider porting its auto-reconnect logic into the range-tests shell approach. |
| **SUPERSEDED** | 7 | range-tests has a newer/different implementation of the same fix. No action — range-tests version wins. |
| **CONFLICT** | 5 | Requires manual resolution during merge (documented below). |
| **COSMETIC** | 5 | No functional impact. |

---

## 4. Conflict Resolution Guide

### Conflict 1: TX Boot Gate (TX-16, TX-22)
- **Master** (`2752fa1`): 5s GPS probe → start sweeping on `millis()` → switch to GPS when available.
- **Range-tests** (`98795c0`, ADR-018): 60s gate → WAITING_FOR_GPS state → **never transmit without fix**.
- **Resolution**: **Keep range-tests.** It implements Felix's hard requirement ("TX shouldn't transmit without satellite fix"). Master's approach transmits unsynced packets that can never be decoded by RX.

### Conflict 2: RMC Time Parser (TX-19)
- **Master** (`0880443`): Two-step sscanf (time first, position only on A status).
- **Range-tests** (`ce2a3da`): Single sscanf with `parsed >= 2` threshold.
- **Resolution**: **Keep range-tests** (simpler, already tested in walk tests). Both produce identical time extraction. The two-step approach adds a redundant second sscanf that is not needed.

### Conflict 3: Makefile
- **Master**: PlatformIO build/flash/monitor targets.
- **Range-tests**: BOOTSEL flashing targets.
- **Resolution**: **Merge both** into one Makefile. They are complementary, not contradictory. Add master's `build-*`, `flash-*`, `monitor-*`, `test*`, `walk-test`, `clean` targets alongside range-tests' `bootsel-*` and `identify-ports` targets.

### Conflict 4: `platformio.ini` default_envs + base config
- **Master**: `default_envs = rp2040` with RadioLib.
- **Range-tests**: `default_envs = rp2040-sweep-tx-v4, rp2040-sweep-rx-v4` with earlephilhower core, no RadioLib.
- **Resolution**: **Keep range-tests.** Aligns with ADR-020 (ban RadioLib). Add any missing master envs back individually.

### Conflict 5: Walk Capture Tooling
- **Master**: `tools/walk_capture.py` (537-line Python, robust).
- **Range-tests**: `tools/walk_capture.sh` (shell, dual-serial).
- **Resolution**: **Keep BOTH.** The Python script is more robust for long captures; the shell script is simpler for quick dual-port capture. Name them distinctly.

---

## 5. Merge Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| Losing `walk_capture.py` robust auto-reconnect | **HIGH** | Explicitly `git checkout master -- tools/walk_capture.py` after merge |
| TX transmitting unsynced (if master's boot gate wins) | **HIGH** | Use range-tests' GPS fix gate unconditionally |
| FLRC decode failure (if master's `0x4C` packet params win) | **HIGH** | Use range-tests' `0x7C` (CRC24 + Match123) |
| Phase drift over 56 phases (if master's seconds-only math wins) | **MEDIUM** | Use range-tests' `totalCycleMs` ms-precision |
| Radio undefined state on phase boundary during SF12 TX | **MEDIUM** | Use range-tests' `abortTxIfActive()` |
| CDC watchdog reboot on power bank | **MEDIUM** | Use range-tests' `if (Serial && ...)` guard |

---

## 6. Methodology & Reproduction

All diffs were produced with:
```bash
cd ~/repos/balloon-fresh
git diff github/master github/range-tests -- <file>
```

Commit ancestry verified with:
```bash
git merge-base --is-ancestor <hash> github/master   # → YES for all three
git merge-base --is-ancestor <hash> github/range-tests  # → NO for all three
```

The three named commits (`dce248f`, `0880443`, `2752fa1`) exist only on `github/master`. However, the firmware files on both branches share a common commit history (`b7dd442` through `98795c0`), meaning the divergence happened via independent commits on each branch tip, not via cherry-pick. Range-tests independently solved the same bugs that master's three commits addressed.

**No firmware files were modified during this analysis.** This document is analysis-only.
