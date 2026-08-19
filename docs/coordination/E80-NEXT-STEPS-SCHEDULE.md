# E80 STM32 Balloon Benchmark — Next Steps Execution Schedule

**Created:** 2026-08-20  
**Author:** Hermes Agent (manager profile) — firmware engineering consultant  
**Status:** DRAFT — pending operator approval  
**Firmware baseline:** c31fb30 on `feat/e80-stm32-bench`  
**E80 repo:** `~/repos/balloon-e80bench/`  
**Docs repo:** `~/repos/balloon-fresh/` (branch `feat/e80-spi-bypass`)  
**Plan reference:** `~/repos/balloon-fresh/.hermes/plans/2026-08-19_firmware-harmonization.md` (2318 lines)

---

## Table of Contents

1. [Current State Summary](#1-current-state-summary)
2. [Quality Gates Reference](#2-quality-gates-reference)
3. [Worker Profile Assignments](#3-worker-profile-assignments)
4. [Workstream A — IWDG Disable + Full 9-Test Matrix](#4-workstream-a--iwdg-disable--full-9-test-matrix-highest-priority)
5. [Workstream B — Short Payload CRC Investigation](#5-workstream-b--short-payload-crc-investigation-medium-priority)
6. [Workstream C — Firmware Harmonization Phase 1 (M1–M7)](#6-workstream-c--firmware-harmonization-phase-1-m1m7-scheduled-lower-priority)
7. [GANTT-Style ASCII Timeline](#7-gantt-style-ascii-timeline)
8. [Cross-Workstream Dependencies](#8-cross-workstream-dependencies)
9. [Risk Register](#9-risk-register)
10. [Definition of Done — Per Workstream](#10-definition-of-done--per-workstream)

---

## 1. Current State Summary

| Item | Status |
|------|--------|
| E80 boards | Both alive, firmware c31fb30 (ORE clearing + HAL_Delay NOP override) |
| Clean data points | 4 collected: 260/255 (84 kbps, -27.5 dBm), 650/255 (115 kbps, -28.0 dBm), 1300/64 (74 kbps, -16.0 dBm), 2600/128 (8 kbps, -15.5 dBm) — all 200/200, 0 CRC |
| IWDG watchdog | Blocks full 9-test matrix — kills TX board after first ARM TX. `iwdg_active` (bench.c:80) + `hiwdg` (bench.c:41), starts at first ARM TX via `iwdg_start_once()` (bench.c:310), 2–4s window, cannot be stopped, only power-cycle clears |
| Short payload CRC | 64B/128B at 260/650 kbps → 200 TX sent, 200 CRC errors on RX. Uninvestigated — likely coding rate / payload length mismatch |
| Harmonization plan | 25 tasks across 4 phases (M1–M7 + O4). 2318-line plan file exists. Phase 1 = 19 tasks |
| Test scripts | `tests/throughput-matrix/throughput_final6.py` is latest (v6). Scripts v1–v5 also present |
| Firmware build | CMake + arm-none-eabi-gcc, `make` builds, `make test-host` runs 5 PC unit tests. Flash: 19,500 B (29.7%), RAM: 2,808 B (8.7%) |
| SWD flash | openocd + cmsis-dap, stm32f1x target. **CRITICAL:** SWD halt poisons NVIC — power-cycle is only clean recovery. After power-cycle, avoid SWD `halt` |
| Board ports | A: ttyUSB4, B: ttyUSB3 — **ports swap on replug**, always scan USB serial numbers |

### IWDG Code Locations (for Workstream A)

| Symbol | File | Line | Purpose |
|--------|------|------|---------|
| `static IWDG_HandleTypeDef hiwdg` | `bench.c` | 41 | IWDG handle |
| `static bool iwdg_active` | `bench.c` | 80 | Tracks whether IWDG has started |
| `iwdg_start_once()` | `bench.c` | 310–319 | Starts IWDG at first ARM TX (PR=64, reload=1874, 2–4s) |
| `HAL_IWDG_Refresh(&hiwdg)` | `bench.c` | 933 | Fed in superloop when active |
| `iwdg_active` check (ARM TX) | `bench.c` | 517–521 | Prints "NOTE IWDG STARTED" after first ARM TX |
| `bench_safety_flash_plan(iwdg_active)` | `bench.c` | 762 | Refuses FLASH command when IWDG running |
| `bench_safety_boot_field(iwdg_active)` | `bench.c` | 442 | Reports boot field in ID? |
| `HAL_IWDG_MODULE_ENABLED` | `stm32f1xx_hal_conf.h` | 28 | Enables HAL IWDG driver |
| `BENCH_IWDG_PR_REG` / `BENCH_IWDG_RELOAD` | `bench_safety.h` | 85–86 | IWDG prescaler/reload constants |

---

## 2. Quality Gates Reference

Seven gates from quality-gates skill v2.2.0. Gate text must be embedded in kanban task bodies, not passed as `--skill`.

| Gate | Name | Description |
|------|------|-------------|
| G1 | TDD | Write failing test first. Firmware without target hardware: host unit test or build check minimum |
| G2 | Tests pass | Full test suite, zero failures. E80: `make test-host`. Config-only: build check |
| G3 | Cold review | Cross-family subagent reviews diff with zero context. GLM worker → Kimi reviewer |
| G4 | Docs updated | Source changes ship with doc changes in same commit |
| G5 | Atomic commits | Conventional messages, `git status` clean |
| G6 | Push | `git push` succeeds. Work isn't done until pushed |
| G7 | Manager validation | Task in `review` status, manager approves |

**Firmware-specific exceptions (declare in task comment):**
- Target hardware unavailable → G2 uses build check instead of hardware test
- Config-only changes → G1 may be relaxed; G5 still applies
- Docs-only tasks → G1 and G2 N/A; G5 still applies
- Bench testing tasks (no code change) → G1/G2 N/A for the test run itself; G4/G5/G6 apply to results commit

---

## 3. Worker Profile Assignments

| Profile | Role | Assigned Workstreams |
|---------|------|---------------------|
| `worker-balloon` | Firmware engineering | A (IWDG disable + flash), C (all E80 firmware tasks) |
| `worker-data` | Data analysis + test execution | A (run 9-test matrix, commit results), B (CRC investigation) |
| `worker-reviewer-kimi` | Cold review (G3) | C (review all E80 firmware diffs) |
| `manager` | Validation (G7), coordination | All workstreams (gate validation, scheduling) |

---

## 4. Workstream A — IWDG Disable + Full 9-Test Matrix (HIGHEST PRIORITY)

### 4.1 Objective

Disable the IWDG watchdog via a compile-time flag (`E80_BENCH_NO_IWDG`) so the full 9-test throughput matrix (3 rates × 3 payload sizes) can run without board resets. Collect clean data for all 9 cells.

### 4.2 Task Breakdown

| Task # | Task | Worker | Est. Duration | Depends On | Quality Gates |
|--------|------|--------|---------------|------------|---------------|
| A-1 | Add `E80_BENCH_NO_IWDG` compile-time flag to firmware | worker-balloon | 30 min | — | G1, G2, G4, G5, G6 |
| A-2 | Rebuild firmware with flag enabled, SWD flash both boards | worker-balloon | 20 min | A-1 | G2 (build passes), G5 (commit binary note) |
| A-3 | Power-cycle both boards (physical USB unplug 3+ seconds) | operator (Felix) | 5 min | A-2 | — (physical action) |
| A-4 | Verify board identity + port mapping via UART ID? command | worker-data | 10 min | A-3 | — (diagnostic) |
| A-5 | Run full 9-test throughput matrix (3 rates × 3 payloads) | worker-data | 45 min | A-4 | G1 (test exists: `throughput_final6.py`) |
| A-6 | Commit results + update findings doc | worker-data | 20 min | A-5 | G4 (docs), G5 (atomic commit), G6 (push) |

**Total estimated duration:** 2–2.5 hours (sequential)

### 4.3 Task Details

#### A-1: Add `E80_BENCH_NO_IWDG` compile-time flag

**Files to modify:**
- `firmware/e80-stm32-bench/src/bench.c` — wrap `iwdg_start_once()` call (line 519) in `#ifndef E80_BENCH_NO_IWDG`
- `firmware/e80-stm32-bench/src/bench.c` — wrap `HAL_IWDG_Refresh` call (line 933) in `#ifndef E80_BENCH_NO_IWDG`
- `firmware/e80-stm32-bench/src/bench.c` — wrap `iwdg_active` prints (lines 520–521) in `#ifndef E80_BENCH_NO_IWDG`
- `firmware/e80-stm32-bench/CMakeLists.txt` — add `E80_BENCH_NO_IWDG` option() defaulting to OFF; when ON, add `-DE80_BENCH_NO_IWDG` to compile flags
- `firmware/e80-stm32-bench/Makefile` — add `BENCH_NO_IWDG=1` make variable that passes `-DE80_BENCH_NO_IWDG`

**Implementation approach:**
```c
// bench.c, in iwdg_start_once() or at the ARM TX call site:
#ifndef E80_BENCH_NO_IWDG
    iwdg_start_once();
    if (iwdg_active)
        console_putln("NOTE IWDG STARTED (2-4S WINDOW) - 'FLASH' NOW REQUIRES POWER-CYCLE");
#else
    console_putln("NOTE IWDG DISABLED (BENCH MODE)");
#endif

// bench.c, in superloop feed:
#ifndef E80_BENCH_NO_IWDG
    if (iwdg_active)
        HAL_IWDG_Refresh(&hiwdg);
#endif
```

**Gate G1 (TDD):** Add host test verifying that `E80_BENCH_NO_IWDG` define suppresses IWDG start. Test: compile-time check that when `E80_BENCH_NO_IWDG` is defined, `iwdg_start_once()` is not called. Since this is a preprocessor guard, the test is a build check (compile with and without the flag).

**Gate G2:** `make test-host` passes. `make firmware BENCH_NO_IWDG=1` builds successfully. `arm-none-eabi-size` shows minimal flash delta.

**Gate G4:** Document the flag in `README.md` or `AGENTS.md` — add bench mode usage section.

**Gate G5:** Atomic commit:
```
feat(e80): add E80_BENCH_NO_IWDG compile-time flag for bench testing

When E80_BENCH_NO_IWDG is defined, iwdg_start_once() and HAL_IWDG_Refresh
are skipped via preprocessor guards. This allows the full 9-test throughput
matrix to run without board resets. Flag defaults to OFF (production safety).
CMake option + Makefile variable BENCH_NO_IWDG=1 control the flag.
```

**Gate G6:** `git push` to `feat/e80-stm32-bench`.

#### A-2: Rebuild + SWD Flash

**Build command:**
```bash
cd ~/repos/balloon-e80bench
make clean && make firmware BENCH_NO_IWDG=1
```

**Flash command (per board):**
```bash
openocd -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg \
    -c "program firmware/e80-stm32-bench/build-fw/e80_bench.bin verify reset exit 0x08000000"
```

**CRITICAL:** SWD `halt` poisons NVIC. Use `reset exit` (not `halt run`). After flashing, proceed to A-3 (power-cycle) before any UART communication.

**Gate G2:** Build passes, binary verifies on flash.

#### A-3: Power-Cycle Both Boards

Physical action by operator:
1. Unplug both CH340 USB cables
2. Wait 3+ seconds
3. Replug both
4. Note: ports may swap — do NOT assume ttyUSB3/ttyUSB4 mapping

#### A-4: Verify Board Identity + Port Mapping

```bash
# Scan all ttyUSB devices, send ID?\r to each, identify by response
for port in /dev/ttyUSB[0-9]; do
    echo "=== $port ==="
    timeout 2 bash -c "echo 'ID?\r' > $port && cat $port" 2>/dev/null || echo "no response"
done
```

Record which ttyUSB is Board A (TX) and which is Board B (RX). Update `throughput_final6.py` port variables accordingly.

#### A-5: Run Full 9-Test Throughput Matrix

**Test script:** `~/repos/balloon-e80bench/tests/throughput-matrix/throughput_final6.py`

**Test matrix (9 cells):**

| | 64B | 128B | 255B |
|---|---|---|---|
| 260 kbps | Cell 1 | Cell 2 | Cell 3 |
| 650 kbps | Cell 4 | Cell 5 | Cell 6 |
| 1300 kbps | Cell 7 | Cell 8 | Cell 9 |

**Parameters per test:**
- N=200 packets
- GAP=10000 (10ms inter-packet gap)
- PA=10 (indoor, +10 dBm)
- FREQ=869850000 (869.85 MHz)
- MOD flrc `<rate>` 10
- 4s wait between tests
- ROLE TX / ROLE RX (no ARM RX needed — ROLE RX is continuous)
- ARM TX + START as single serial write (zero gap)

**Per-test sequence:**
1. Reset both boards (ROLE NONE)
2. Set MOD, FREQ, PA on both
3. Set ROLE RX on RX board
4. Set ROLE TX on TX board
5. Send `ARM TX\rSTART N=200 LEN=<size> GAP=10000\r` as single write to TX board
6. Wait for TX completion + RX drain
7. Query `STAT?` on both boards
8. Record results

**Gate G1:** Test script `throughput_final6.py` exists and has been validated (v6 is latest working version).

**Success criteria:** All 9 cells produce TX=200, with RX and CRC values recorded. No IWDG resets during the full run.

#### A-6: Commit Results + Update Findings

**Files to update:**
- `~/repos/balloon-fresh/docs/data-handover/E80-THROUGHPUT-FINDINGS-2026-08-19.md` — append section 10 with 9-test matrix results
- `~/repos/balloon-e80bench/tests/throughput-matrix/` — commit any script updates made during the run
- `~/repos/balloon-e80bench/tests/throughput-matrix/v7_results.txt` — raw output

**Gate G4:** Findings doc updated in same commit as results data.

**Gate G5:** Atomic commit:
```
docs(e80): add full 9-test throughput matrix results (IWDG disabled)

Complete 3x3 matrix (260/650/1300 kbps × 64/128/255B) with IWDG
disabled via E80_BENCH_NO_IWDG flag. All 9 cells completed without
board resets. [N/9 cells clean 200/200 0 CRC].
```

**Gate G6:** Push to `feat/e80-spi-bypass` (docs repo) and `feat/e80-stm32-bench` (e80bench repo).

### 4.4 Risk Assessment + Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| SWD halt poisons NVIC after flash | High | High | Use `reset exit` not `halt run`. Power-cycle after flash. Do NOT use SWD after power-cycle. |
| Port swap after power-cycle | High | Medium | Scan all ttyUSB devices with ID? command before starting tests. Do not hardcode ports. |
| 2600 kbps FLRC not supported | Medium | Low | Exclude 2600 from primary matrix. Focus on 260/650/1300 kbps. Can add 2600 as supplementary test. |
| IWDG flag doesn't fully suppress watchdog | Low | High | Verify `iwdg_active` stays false by checking ID? response for absence of "IWDG STARTED" note. If IWDG still fires, check for other IWDG init paths. |
| Short payload CRC errors persist (64B/128B at 260/650) | High | Medium | Expected — this is what Workstream B investigates. Record results even if CRC errors occur. All data is valuable. |
| UART baud mismatch after rebuild | Low | Medium | Baud is still 115200 (E80-2 baud bump is Workstream C, not yet applied). Verify baud in script matches firmware. |

### 4.5 Definition of Done — Workstream A

- [ ] `E80_BENCH_NO_IWDG` flag implemented, builds with and without flag
- [ ] `make test-host` passes (all 5 host tests)
- [ ] Both boards flashed with IWDG-disabled firmware
- [ ] Both boards power-cycled, port mapping verified
- [ ] Full 9-test matrix completed (all 9 cells have recorded data)
- [ ] Results committed to findings doc with raw output
- [ ] All commits pushed to both repos
- [ ] No IWDG resets occurred during the full matrix run

---

## 5. Workstream B — Short Payload CRC Investigation (MEDIUM PRIORITY)

### 5.1 Objective

Investigate and diagnose the systematic CRC errors observed for 64B and 128B payloads at 260/650 kbps FLRC. Pattern: TX sends 200 packets, RX reports 200 CRC errors (0 good). Hypothesis: LR2021 coding rate / payload length mismatch at shorter payloads.

### 5.2 Task Breakdown

| Task # | Task | Worker | Est. Duration | Depends On | Quality Gates |
|--------|------|--------|---------------|------------|---------------|
| B-1 | Analyze existing data + LR2021 datasheet for CR/payload constraints | worker-data | 45 min | A-5 (use fresh 9-test data) | G4 (docs) |
| B-2 | Examine firmware radio config code for CR/payload handling | worker-balloon | 30 min | B-1 | G4 (docs) |
| B-3 | Test with explicit CR field setting (if firmware supports it) | worker-balloon | 30 min | B-2 | G4 (docs), G5 (commit), G6 (push) |
| B-4 | Document findings + root cause analysis | worker-data | 30 min | B-3 | G4 (docs), G5 (commit), G6 (push) |

**Total estimated duration:** 2–2.5 hours (can overlap with A-5 data analysis)

### 5.3 Task Details

#### B-1: Data Analysis + Datasheet Review

**Examine:**
- v6 results: 260/64 → 200 CRC err, 260/128 → 200 CRC err, 260/255 → 200/200 clean
- v6 results: 650/64 → 200 CRC err, 650/255 → 200/200 clean
- Pattern: 255B works, 64B/128B fail at low rates. 1300/64 works (manual test).
- Cross-reference: `docs/e80-900mbl-02-eval/e80-900mbl-02-spec-id4397.pdf` for LR2021 FLRC payload length / coding rate constraints
- Check: Does LR2021 FLRC have a minimum payload length per coding rate? Is 64B below the minimum for CR=3/4 at 260/650 kbps?

**Output:** Document the pattern, hypothesis, and datasheet findings in a new investigation doc.

#### B-2: Firmware Radio Config Review

**Examine firmware source:**
- `firmware/e80-stm32-bench/src/radio_bench.c` — `radio_bench_apply_cfg()` function
- How is FLRC coding rate set? (Currently hardcoded as 3/4 per plan)
- How is payload length handled? Does firmware pad short payloads?
- Is there a minimum payload length check?
- Check LR2021 driver: `lr20xx_driver` — does it enforce minimum payload size?

**Key question:** When `LEN=64` is sent, does the firmware pass 64 bytes to the radio, or does it add header bytes (6-byte header: u32 seq LE + u16 len LE → actual payload = 70B)?

#### B-3: Experimental Test with Explicit CR

**Prerequisite:** E80-4 (add CR field to config) is in Workstream C. If not yet implemented, test by temporarily hardcoding different CR values in `radio_bench.c`:

```c
// Try CR=2 (uncoded) for short payloads at 260/650 kbps
lr20xx_radio_set_flrc_modulation_params(..., LR20XX_FLRC_CR_UNCODED, ...);
```

**Test plan:**
1. Flash one board with CR=uncoded, other with CR=3/4 (current default)
2. Run 260/64, 260/128, 650/64, 650/128 with both CR settings
3. Compare CRC error rates

**Alternative if CR change requires both boards:** Flash both with CR=uncoded, run same 4 cells.

**Gate G5:** Commit any firmware changes (even experimental) as atomic commit:
```
test(e80): experiment with uncoded FLRC for short payloads

Testing CR=uncoded vs CR=3/4 for 64B/128B at 260/650 kbps.
Investigating systematic CRC errors on short payloads.
```

**Gate G6:** Push.

#### B-4: Document Findings

**Create:** `~/repos/balloon-fresh/docs/data-handover/E80-SHORT-PAYLOAD-CRC-INVESTIGATION-2026-08-20.md`

**Contents:**
- Observed pattern (data table from v6 + A-5 results)
- Root cause (or "inconclusive" with remaining hypotheses)
- Datasheet constraints found
- Firmware behavior confirmed
- Experimental results (CR=uncoded vs CR=3/4)
- Recommendation: fix or workaround

**Gate G4:** Doc created and committed.
**Gate G5:** Atomic commit.
**Gate G6:** Push.

### 5.4 Risk Assessment + Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Root cause not found (inconclusive) | Medium | Medium | Document all hypotheses and elimination steps. May require oscilloscope/SPI capture to fully diagnose. |
| CR change requires firmware rebuild + reflash | High | Low | Expected. Both boards need same CR setting. Use Workstream A's IWDG-disabled firmware as base. |
| LR2021 driver doesn't expose CR setting | Low | High | Check `lr20xx_driver` API. If not exposed, may need direct register write. Fallback: document as driver limitation. |
| 6-byte header makes 64B → 70B actual payload, but still fails | Medium | Low | Document the header overhead. Check if LR2021 has a 64-byte minimum for CR=3/4 FLRC (70B may still be below threshold). |

### 5.5 Definition of Done — Workstream B

- [ ] Data pattern analyzed and documented
- [ ] Firmware radio config reviewed for CR/payload handling
- [ ] Experimental test run with alternative CR setting (if feasible)
- [ ] Investigation document created with root cause or remaining hypotheses
- [ ] All commits pushed
- [ ] Findings cross-referenced in throughput findings doc

---

## 6. Workstream C — Firmware Harmonization Phase 1 (M1–M7) (SCHEDULED, LOWER PRIORITY)

### 6.1 Objective

Implement 19 firmware harmonization tasks across 4 rig workstreams (E80, C3, RP2040, Host Tools) to achieve the common 23-field PKT line format with non-resetting sequence counters, CRC-failed packet logging, firmware hash boot banners, and host-side session_id injection.

### 6.2 Task Schedule — E80 Workstream (8 tasks)

All tasks assigned to `worker-balloon` unless noted. All tasks require G7 (manager validation) in addition to gates listed.

| Task # | Task | Milestone | Est. Duration | Depends On | Quality Gates |
|--------|------|-----------|---------------|------------|---------------|
| E80-1 | Add FW_HASH to boot banner | M1 | 20 min | — | G1, G2, G3, G4, G5, G6, G7 |
| E80-5 | Make tx_seq non-resetting uint32 | M6 | 15 min | — | G1, G2, G3, G4, G5, G6, G7 |
| E80-3 | Enlarge tx_buf 96→160 bytes | M3 prep | 20 min | — | G1, G2, G3, G4, G5, G6, G7 |
| E80-2 | Bump UART baud to 2,000,000 | M3 | 15 min | E80-3 | G1 (exception: config-only), G2, G3, G4, G5, G6, G7 |
| E80-4 | Add coding rate (cr) field to radio_bench_cfg_t | M4 prep | 30 min | — | G1, G2, G3, G4, G5, G6, G7 |
| E80-6 | Per-packet 23-field PKT output format | M3+M4+M5 | 60 min | E80-3, E80-4, E80-2 | G1, G2, G3, G4, G5, G6, G7 |
| E80-7 | Log CRC-failed packets with RSSI | M7 | 30 min | E80-6 | G1, G2, G3, G4, G5, G6, G7 |
| E80-8 | CONFIG_START transition markers | O4 | 20 min | E80-6 | G1, G2, G3, G4, G5, G6, G7 |

**E80 total estimated duration:** ~3.5 hours sequential. Can parallelize E80-1, E80-5, E80-3, E80-4 (no dependencies).

### 6.3 Task Schedule — C3 Workstream (5 tasks)

| Task # | Task | Milestone | Est. Duration | Depends On | Quality Gates |
|--------|------|-----------|---------------|------------|---------------|
| C3-1 | Add FW_HASH to boot banner | M1 | 30 min | — | G1, G2, G3, G4, G5, G6, G7 |
| C3-2 | Widen sequence counter to uint32 | M6 | 45 min | — | G1, G2, G3, G4, G5, G6, G7 |
| C3-3 | Update PKT line to 23-field format | M4+M5 | 60 min | C3-1, C3-2 | G1, G2, G3, G4, G5, G6, G7 |
| C3-4 | Log CRC-failed packets | M7 | 30 min | C3-3 | G1, G2, G3, G4, G5, G6, G7 |
| C3-5 | CONFIG_START transition markers | O4 | 20 min | C3-3 | G1, G2, G3, G4, G5, G6, G7 |

**C3 total estimated duration:** ~3 hours sequential. C3-1 and C3-2 can run in parallel.

### 6.4 Task Schedule — Host Tools Workstream (4 tasks)

| Task # | Task | Milestone | Est. Duration | Depends On | Quality Gates |
|--------|------|-----------|---------------|------------|---------------|
| HOST-1 | M2 firmware-hash gate in capture tools | M2 | 45 min | E80-1, C3-1 | G1, G2, G3, G4, G5, G6, G7 |
| HOST-2 | Update baud rate to 2,000,000 in E80 host tools | M3 | 20 min | E80-2 | G1, G2, G3, G4, G5, G6, G7 |
| HOST-3 | Add session_id injection to capture tools | M5 | 45 min | HOST-1 | G1, G2, G3, G4, G5, G6, G7 |
| HOST-4 | Update CSV format for 23-field PKT lines | M4 | 30 min | HOST-3, E80-6 | G1, G2, G3, G4, G5, G6, G7 |

**Host total estimated duration:** ~2.5 hours. HOST-1 and HOST-2 can run in parallel after their firmware deps.

### 6.5 Task Schedule — RP2040 Workstream (1 task)

| Task # | Task | Milestone | Est. Duration | Depends On | Quality Gates |
|--------|------|-----------|---------------|------------|---------------|
| RP-1 | Build RP2040 firmware with harmonized format from start | M1–M7, O4 | 2–3 hours | HOST-4 (for format contract) | G1, G2, G3, G4, G5, G6, G7 |

### 6.6 E80 Task Details (Key Tasks)

#### E80-1: Add FW_HASH to boot banner (M1)

- **Files:** `bench.c:875` (boot banner), `tests/test_bench_cmd.c`
- **Context:** `FW_GIT_SHA` already injected via Makefile `-DFW_GIT_SHA=<sha7>`, printed in ID? reply (bench.c:399). Boot banner at bench.c:875 doesn't include it.
- **Change:** Add `FW_HASH=<sha>` to boot banner line
- **G1:** Write test checking `FW_GIT_SHA` is defined and banner format includes `FW_HASH=`
- **G2:** `make test-host` passes, `make firmware` builds, flash delta < 100 bytes
- **G3:** Kimi reviews diff — verify no banner format breakage
- **Validation:** Boot banner contains `FW_HASH=` followed by 7+ hex chars

#### E80-2: Bump UART baud to 2,000,000 (M3)

- **Files:** `main.h:64` (baud constant)
- **Context:** `E80_BENCH_BAUD_DEFAULT = 115200U`. ADR-029 mandates 2 Mbps. CH340 supports 2 Mbps. STM32F103 USART1 supports up to 4.5 Mbps. At 2 Mbps, 160-byte PKT line = 0.8ms; at 190 pkt/s = 7.8% CPU.
- **Change:** `115200U` → `2000000U`, update comment
- **G1:** Exception declared (config-only change, no TDD)
- **G2:** Build check + `make test-host` passes (5 tests unaffected)
- **Cross-dep:** HOST-2 must update host tools baud to match in same session
- **Risk:** If CH340 doesn't reliably do 2 Mbps on this host, fallback to 921600. Test UART comms after flash+power-cycle.

#### E80-3: Enlarge tx_buf 96→160 bytes

- **Files:** `console.c:22` (tx_buf), `console.h` (new constant)
- **Context:** 23-field PKT line worst case ~102 chars. Current 96-byte buffer truncates at 95. +64 bytes BSS (13.2% → 13.5% RAM — negligible).
- **Change:** Add `#define CONSOLE_TX_BUF_SIZE 160` in `console.h`, change `static char tx_buf[96]` → `static char tx_buf[CONSOLE_TX_BUF_SIZE]`
- **G1:** Test `CONSOLE_TX_BUF_SIZE >= 160`
- **G2:** `make test-host` passes, build shows +64 bytes BSS

#### E80-4: Add coding rate (cr) field to radio_bench_cfg_t

- **Files:** `radio_bench.h:39-47` (struct), `radio_bench.c` (apply_cfg), `bench.c` (MOD handler), `tests/test_bench_cmd.c`
- **Context:** CR hardcoded (LoRa 4/5, FLRC 3/4). Need `uint8_t cr` field. LoRa: denominator form (5=4/5, 7=4/7). FLRC: register code (0=1/2, 1=3/4, 2=uncoded).
- **G1:** Test `radio_bench_cfg_t` has `cr` field, can set/get
- **G2:** `make test-host` passes, build succeeds, defaults preserve old behavior
- **G3:** Kimi reviews CR enum mapping correctness
- **Note:** This task directly supports Workstream B investigation (B-3)

#### E80-5: Make tx_seq non-resetting (M6)

- **Files:** `bench.c:659` (remove `tx_seq = 0`), `tests/test_bench_stats.c`
- **Context:** `bench.c:68` declares `static uint32_t tx_seq`. START handler resets to 0. Removing that line makes it non-resetting from boot. `bench_stats_reset()` still tracks per-session first/last.
- **Change:** Delete `tx_seq = 0;` line in START handler, add comment documenting M6 contract
- **G1:** Structural test verifying `bench_stats_reset()` doesn't touch `tx_seq`
- **G2:** `make test-host` passes, build succeeds (flash may decrease few bytes)
- **Validation:** `grep 'tx_seq = 0' bench.c` returns no results in START handler

#### E80-6: Per-packet 23-field PKT output (M3+M4+M5)

- **Files:** `bench.c:826-843` (RX_OK/CRC handlers), new `bench_pkt.c` + `bench_pkt.h`, `tests/test_bench_pkt.c`
- **Context:** RX_OK handler has `e.seq`, `e.rssi_half_dbm`, `e.snr_qdb`, `e.len` in scope. RX_CRC handler just increments counter. Need to emit `PKT,...` line for every packet. Also add SESSION and CONFIG commands for session_id/config_id/replicate.
- **G1:** 3 tests: basic format, CRC fail format, truncation safety
- **G2:** `make test-host` passes, build succeeds. **Watch flash size** — snprintf from newlib may add significant flash. If > 32K, switch to incremental `console_put*()` approach.
- **G3:** Kimi reviews format correctness against ADR-029 23-field spec
- **Complexity:** Highest task — ~60 min. Creates 2 new files + modifies bench.c + adds tests.
- **Dependencies:** E80-3 (buffer size), E80-4 (cr field), E80-2 (baud bandwidth)

#### E80-7: Log CRC-failed packets with RSSI (M7)

- **Files:** `bench.c:841-843` (RX_CRC handler), `radio_bench.c` / `radio_bench.h` (verify rb_evt_t has seq/rssi for CRC events)
- **Context:** RX_CRC handler at bench.c:841-843 just increments `rx_crc_err`. Need to populate `e.seq`, `e.rssi_half_dbm` for CRC events and emit PKT line with `crc_ok=0`.
- **Key question:** Does `rb_evt_t` (radio_bench.h:65) have seq/rssi populated for CRC events? Plan notes "RX_OK only" — may need to fix in `radio_bench.c`.
- **G1:** Test CRC fail PKT line has `crc_ok=0` and RSSI value
- **G2:** `make test-host` passes, build succeeds
- **Dependencies:** E80-6 (PKT formatter must exist)

#### E80-8: CONFIG_START transition markers (O4)

- **Files:** `bench.c` (START/STOP command handlers), `bench_pkt.c` (emit transition lines)
- **Context:** Emit `CONFIG_START,<session_id>,<config_id>,<replicate>` and `CONFIG_END,...` markers to bracket test runs in the serial output stream.
- **G1:** Test that CONFIG_START/CONFIG_END lines are emitted with correct fields
- **G2:** `make test-host` passes, build succeeds
- **Dependencies:** E80-6 (session_id/config_id infrastructure)

### 6.7 Recommended Execution Order (E80 Workstream)

Tasks with no dependencies can be dispatched in parallel to `worker-balloon`:

**Wave 1 (parallel, ~30 min):**
- E80-1 (FW_HASH banner) — 20 min
- E80-5 (tx_seq non-resetting) — 15 min
- E80-3 (tx_buf enlarge) — 20 min
- E80-4 (cr field) — 30 min

**Wave 2 (after E80-3, ~15 min):**
- E80-2 (baud bump) — 15 min

**Wave 3 (after E80-2 + E80-3 + E80-4, ~60 min):**
- E80-6 (23-field PKT output) — 60 min ← critical path

**Wave 4 (after E80-6, ~30 min):**
- E80-7 (CRC-failed packet logging) — 30 min
- E80-8 (CONFIG_START markers) — 20 min (can parallel with E80-7)

**Critical path:** E80-4 → E80-6 → E80-7 = 120 min. Total with waves: ~3 hours.

### 6.8 Risk Assessment + Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| snprintf flash overhead exceeds budget | Medium | High | E80-6: monitor `arm-none-eabi-size` after build. If flash > 32K (50%), switch to incremental `console_put*()` formatting. Current: 19,500 B (29.7%). |
| 2 Mbps UART unreliable on CH340 | Low | High | E80-2: test UART comms after flash. Fallback to 921600 (still > 4x current). Document if fallback needed. |
| rb_evt_t missing seq/rssi for CRC events | Medium | Medium | E80-7: may need to modify `radio_bench.c` to populate fields for CRC events. Add as sub-task. |
| Cold review (G3) uncovers CR enum mapping error | Medium | Medium | E80-4: Kimi reviewer checks LoRa vs FLRC CR encoding. Map: LoRa 5=4/5, 7=4/7. FLRC 0=1/2, 1=3/4, 2=uncoded. |
| HOST-2 baud mismatch bricks UART comms | Medium | High | HOST-2 and E80-2 must be deployed in same board session. Flash firmware, update host tool baud, power-cycle, then test. |
| Integration test reveals format mismatch across rigs | Low | Medium | RP-1 (RP2040) depends on HOST-4 (format contract). Run integration test after all Phase 1 tasks complete. |

### 6.9 Definition of Done — Workstream C

- [ ] All 19 tasks implemented with TDD (G1) where applicable
- [ ] All tasks pass `make test-host` / `idf.py build` / `pytest` (G2)
- [ ] All E80 firmware diffs reviewed by Kimi (G3)
- [ ] All changes documented in same commit (G4)
- [ ] All commits atomic with conventional messages (G5)
- [ ] All commits pushed (G6)
- [ ] Manager validates each task (G7)
- [ ] Integration test: E80 + C3 + host tools produce matching 23-field PKT lines
- [ ] Memory budget verified: flash < 32K, RAM < 4K for E80

---

## 7. GANTT-Style ASCII Timeline

```
WORKSTREAM A (HIGHEST PRIORITY) — ~2.5 hours
═══════════════════════════════════════════════════════════════════
  T+0:00  A-1: IWDG flag           [██████████] 30min
  T+0:30  A-2: Build + flash       [██████] 20min
  T+0:50  A-3: Power-cycle         [██] 5min
  T+0:55  A-4: Verify ports        [████] 10min
  T+1:05  A-5: Run 9-test matrix   [██████████████████] 45min
  T+1:50  A-6: Commit + push       [████████] 20min
  T+2:10  ◆ DONE

WORKSTREAM B (MEDIUM PRIORITY) — ~2.5 hours, starts after A-5
═══════════════════════════════════════════════════════════════════
  T+1:50  B-1: Data + datasheet    [██████████████████] 45min
  T+2:35  B-2: Firmware review     [██████████] 30min
  T+3:05  B-3: CR experiment       [██████████] 30min
  T+3:35  B-4: Document findings   [██████████] 30min
  T+4:05  ◆ DONE

WORKSTREAM C (LOWER PRIORITY) — ~3.5 hours E80, parallelizable
═══════════════════════════════════════════════════════════════════
  Wave 1 (parallel):
  T+4:05  E80-1: FW_HASH banner    [████████] 20min  ──┐
  T+4:05  E80-5: tx_seq persist    [██████] 15min      │
  T+4:05  E80-3: tx_buf 160B       [████████] 20min    │  30min
  T+4:05  E80-4: cr field          [██████████] 30min ─┘
          │
  Wave 2:
  T+4:35  E80-2: baud 2M           [██████] 15min
          │
  Wave 3 (critical path):
  T+4:50  E80-6: 23-field PKT      [████████████████████████] 60min
          │
  Wave 4 (parallel):
  T+5:50  E80-7: CRC pkt logging   [██████████] 30min  ──┐
  T+5:50  E80-8: CONFIG_START      [████████] 20min     │  30min
                                                        ┘
  T+6:20  ◆ E80 WORKSTREAM DONE

  Parallel tracks (can start after their firmware deps):
  ─────────────────────────────────────────────────────
  C3 workstream:    C3-1 → C3-2 → C3-3 → C3-4 → C3-5   ~3h
  HOST workstream:  HOST-1 → HOST-2 → HOST-3 → HOST-4   ~2.5h
  RP2040:           RP-1 (after HOST-4)                  ~2-3h

TOTAL ESTIMATED: ~6-7 hours (A+B sequential, C in waves)
With parallelism across worker profiles: ~4-5 hours wall clock
```

---

## 8. Cross-Workstream Dependencies

```
                    ┌──────────────────┐
                    │  WORKSTREAM A    │
                    │  IWDG Disable    │
                    │  + 9-Test Matrix │
                    └────────┬─────────┘
                             │ A-5 results
                             ▼
                    ┌──────────────────┐
                    │  WORKSTREAM B    │
                    │  CRC Investigation│
                    └────────┬─────────┘
                             │ B-2 findings
                             ▼
                    ┌──────────────────┐
                    │  E80-4 (cr field)│ ← B-3 may use E80-4 early
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  WORKSTREAM C    │
                    │  Harmonization   │
                    │  E80-1..E80-8    │
                    │  C3-1..C3-5      │
                    │  HOST-1..HOST-4  │
                    │  RP-1            │
                    └──────────────────┘
```

**Key dependency notes:**
- Workstream A must complete before B (B uses fresh 9-test data)
- Workstream B's B-3 (CR experiment) may overlap with E80-4 (cr field) — if E80-4 is done first, B-3 uses the proper CR field; otherwise B-3 uses temporary hardcoded CR
- Workstream C can start after A completes (boards available for testing)
- E80-2 (baud bump) and HOST-2 (host baud update) MUST be deployed together — flashing firmware with 2 Mbps without updating host tools bricks UART comms
- RP-1 depends on HOST-4 (format contract) — RP2040 firmware implements the agreed 23-field format

---

## 9. Risk Register

| # | Risk | WS | Prob | Impact | Mitigation | Owner |
|---|------|----|------|--------|------------|-------|
| R1 | SWD halt poisons NVIC | A | High | High | Use `reset exit` not `halt run`. Power-cycle after flash. | worker-balloon |
| R2 | Port swap after power-cycle | A | High | Med | Scan ttyUSB with ID? before tests. Don't hardcode. | worker-data |
| R3 | IWDG flag doesn't fully suppress watchdog | A | Low | High | Verify `iwdg_active` stays false via ID? response. | worker-balloon |
| R4 | Short payload CRC errors persist in 9-test | A | High | Med | Expected — record all data. Investigated in WS B. | worker-data |
| R5 | LR2021 CR setting not exposed in driver | B | Low | High | Check lr20xx_driver API. Fallback: direct register write or document as limitation. | worker-balloon |
| R6 | Root cause not found for CRC errors | B | Med | Med | Document all hypotheses. May need SPI capture/oscilloscope. | worker-data |
| R7 | snprintf flash overhead exceeds 32K | C | Med | High | Monitor `arm-none-eabi-size`. Switch to incremental console_put* if needed. | worker-balloon |
| R8 | 2 Mbps UART unreliable on CH340 | C | Low | High | Test after flash. Fallback to 921600. | worker-balloon |
| R9 | E80-2 + HOST-2 baud mismatch bricks UART | C | Med | High | Deploy firmware + host tool baud change in same session. | manager |
| R10 | rb_evt_t missing seq/rssi for CRC events | C | Med | Med | Modify radio_bench.c to populate fields. Sub-task of E80-7. | worker-balloon |
| R11 | Cold review (G3) finds CR enum mapping error | C | Med | Med | Kimi reviewer checks LoRa vs FLRC CR encoding carefully. | worker-reviewer-kimi |
| R12 | 2600 kbps FLRC unsupported in matrix | A | Med | Low | Exclude from primary 9-test matrix. Add as supplementary test only. | worker-data |

---

## 10. Definition of Done — Per Workstream

### Workstream A — IWDG Disable + Full 9-Test Matrix

- [ ] `E80_BENCH_NO_IWDG` flag implemented with CMake option + Makefile variable
- [ ] Flag defaults to OFF (production safety preserved)
- [ ] `make test-host` passes (all 5 host tests)
- [ ] `make firmware BENCH_NO_IWDG=1` builds successfully
- [ ] Both boards flashed with IWDG-disabled firmware
- [ ] Both boards power-cycled, port mapping verified via ID?
- [ ] Full 9-test matrix completed — all 9 cells have TX/RX/CRC data
- [ ] No IWDG resets during the full matrix run
- [ ] Results appended to `E80-THROUGHPUT-FINDINGS-2026-08-19.md` (section 10)
- [ ] Raw output committed (`v7_results.txt`)
- [ ] All commits pushed to `feat/e80-stm32-bench` and `feat/e80-spi-bypass`

### Workstream B — Short Payload CRC Investigation

- [ ] Data pattern from v6 + A-5 results analyzed and documented
- [ ] LR2021 datasheet reviewed for CR/payload length constraints
- [ ] Firmware radio config code reviewed for CR/payload handling
- [ ] 6-byte header overhead documented (64B → 70B actual, 128B → 134B actual)
- [ ] Experimental test run with alternative CR setting (uncoded or 1/2)
- [ ] Investigation document created: `E80-SHORT-PAYLOAD-CRC-INVESTIGATION-2026-08-20.md`
- [ ] Root cause identified OR remaining hypotheses documented with next steps
- [ ] Findings cross-referenced in throughput findings doc
- [ ] All commits pushed

### Workstream C — Firmware Harmonization Phase 1

- [ ] All 8 E80 tasks (E80-1 through E80-8) implemented with TDD
- [ ] All 5 C3 tasks (C3-1 through C3-5) implemented
- [ ] All 4 HOST tasks (HOST-1 through HOST-4) implemented
- [ ] RP-1 (RP2040) implemented with harmonized format from start
- [ ] Every task passed its quality gates (G1–G7 as specified per task)
- [ ] All E80 firmware diffs cold-reviewed by worker-reviewer-kimi (G3)
- [ ] All changes documented in same commit as code (G4)
- [ ] All commits atomic with conventional messages (G5)
- [ ] All commits pushed (G6)
- [ ] Manager validated each task (G7)
- [ ] Integration test: E80 + C3 + host tools produce matching 23-field PKT lines
- [ ] E80 memory budget verified: flash < 32K (50%), RAM < 4K (20%)
- [ ] Boot banner shows `FW_HASH=<sha7>` on all rigs
- [ ] PKT lines contain all 23 fields per ADR-029 spec
- [ ] CRC-failed packets logged with RSSI on all rigs
- [ ] tx_seq non-resetting from boot (E80, C3)
- [ ] CONFIG_START/CONFIG_END transition markers emitted

---

## Appendix A: Firmware Command Syntax (confirmed from source)

```
MOD flrc <rate_kbps> <dbm>    — rate: 260, 325, 520, 650, 1040, 1300, 2080, 2600
FREQ <hz>                     — frequency in Hz
PA <dbm>                      — 0-10 indoor, 0-22 after POWER MODE OUTDOOR 2026
POWER MODE OUTDOOR 2026       — unlocks +22 dBm (pin=2026)
ROLE TX|RX|NONE               — RX is continuous, no ARM needed
ARM TX                        — enables TX (starts IWDG 2-4s window)
START N=<pkts> LEN=<6-511> GAP=<us>  — key is GAP, not GAP_US
STAT?                         — query statistics
ID?                           — query board identity + firmware hash
```

## Appendix B: Build + Flash Quick Reference

```bash
# Build firmware (standard)
cd ~/repos/balloon-e80bench
make firmware

# Build firmware (IWDG disabled for bench testing)
make firmware BENCH_NO_IWDG=1

# Run host unit tests
make test-host

# SWD flash (per board) — use reset exit, NOT halt run
openocd -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg \
    -c "program firmware/e80-stm32-bench/build-fw/e80_bench.bin verify reset exit 0x08000000"

# AFTER flashing: physically power-cycle (unplug USB 3+ seconds, replug)
# DO NOT use SWD after power-cycle — halt poisons NVIC
```

## Appendix C: Test Script Location

```
~/repos/balloon-e80bench/tests/throughput-matrix/
├── throughput_final6.py    ← LATEST (v6, use this)
├── throughput_matrix5.py   ← v5
├── throughput_matrix4.py   ← v4
├── throughput_matrix3.py   ← v3
├── throughput_matrix2.py   ← v2
├── throughput_matrix.py    ← v1
├── v6_results.txt          ← v6 raw output
├── uart_monitor.py         ← UART diagnostic
├── uart_check*.py          ← UART check scripts
├── uart_test*.py           ← UART test scripts
└── uart_id_test*.py        ← Board ID test scripts
```

## Appendix D: IWDG Implementation Details (for E80_BENCH_NO_IWDG)

**IWDG start sequence (bench.c:310–319):**
```c
static void iwdg_start_once(void) {
    if (iwdg_active) return;
    hiwdg.Instance       = IWDG;
    hiwdg.Init.Prescaler = IWDG_PRESCALER_64;  // PR reg 4, /64
    hiwdg.Init.Reload    = BENCH_IWDG_RELOAD;   // 1874 → 2-4 s window
    if (HAL_IWDG_Init(&hiwdg) != HAL_OK) return;
    iwdg_active = true;
}
```

**Called at first ARM TX (bench.c:517–521):**
```c
iwdg_start_once();
if (iwdg_active)
    console_putln("NOTE IWDG STARTED (2-4S WINDOW) - 'FLASH' NOW REQUIRES POWER-CYCLE");
```

**Fed in superloop (bench.c:932–933):**
```c
if (iwdg_active)
    HAL_IWDG_Refresh(&hiwdg);
```

**Guards needed for `E80_BENCH_NO_IWDG`:**
1. `iwdg_start_once()` call (bench.c:519) — wrap in `#ifndef`
2. `HAL_IWDG_Refresh` call (bench.c:933) — wrap in `#ifndef`
3. "NOTE IWDG STARTED" print (bench.c:520–521) — wrap in `#ifndef`
4. `HAL_IWDG_MODULE_ENABLED` in `stm32f1xx_hal_conf.h:28` — can optionally comment out to save flash, but preprocessor guards in bench.c are sufficient

**Safety property:** Flag defaults to OFF. Production firmware never defines it. Only bench testing builds use `BENCH_NO_IWDG=1`. The `bench_safety_flash_plan()` and `bench_safety_boot_field()` functions still check `iwdg_active` — with the flag, `iwdg_active` stays false, so FLASH command works and boot field reports "boot=jump-ok".

---

**Document end. Schedule pending operator (Felix) approval before dispatch to worker profiles.**