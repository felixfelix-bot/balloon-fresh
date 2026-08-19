# Firmware Harmonization — Execution Schedule

> **Generated:** 2026-08-20
> **Source Plan:** `2026-08-19_firmware-harmonization.md` (2318 lines, 92KB)
> **Quality Gates:** v3.1.0 (plan references v2.2.0 — **use v3.1.0** per current skill)
> **Workers:** worker-balloon (E80), worker-balloon (C3), worker-admin (Host tools)

---

## Plan Validation Summary

### 18 Phase 1 Tasks Reviewed

| Task | Verdict | Notes |
|------|---------|-------|
| E80-1 | ✅ Correct | FW_HASH in boot banner. `FW_GIT_SHA` already injected via Makefile. Trivial. |
| E80-2 | ✅ Correct | Baud 115200→2000000. Config-only. **R1 critical dependency: must complete before E80-6.** |
| E80-3 | ✅ Correct | tx_buf 96→160. Additive, backward-compatible. R4 is LOW risk. |
| E80-4 | ✅ Correct | Add `cr` field to `radio_bench_cfg_t`. R6 mitigated by preserving default values. |
| E80-5 | ✅ Correct | Remove `tx_seq = 0` from START handler. R2 is LOW — `bench_stats_reset()` handles PER. Test is structural-only (acceptable for firmware without hardware). |
| E80-6 | ⚠️ Correct, monitor flash | Per-packet output + 23-field format. **Depends on E80-2 (R1), E80-3, E80-4.** Uses `snprintf` — R8: if flash > 35K, switch to incremental `console_put`. **Add explicit post-build flash size check to Gate 2.** |
| E80-7 | ✅ Correct | CRC-failed packet RSSI extraction. Depends on E80-6. R3: seq unreliable for CRC fails — documented in struct. |
| E80-8 | ✅ Correct | CONFIG_START markers. Depends on E80-6 (CONFIG command handler). Trivial. |
| C3-1 | ✅ Correct | FW_HASH via CMake `execute_process`. Gate 1 exception (firmware, build check only). |
| C3-2 | ✅ Correct | uint32 non-resetting seq. R7: TX+RX must be flashed simultaneously — payload format unchanged, only values change. Safe. |
| C3-3 | ✅ Correct | 23-field PKT format. Depends on C3-2. Also includes CONFIG command + CONFIG_START (absorbs C3-5). |
| C3-4 | ✅ Correct | CRC-failed packet logging. Depends on C3-3. |
| C3-5 | ✅ Trivial | Already implemented in C3-3. Verification only. 0 min. |
| HOST-1 | ✅ Correct | M2 firmware-hash gate. Depends on E80-1 + C3-1 (needs FW_HASH format). TDD with pytest. |
| HOST-2 | ⚠️ **Repo mismatch** | Updates baud in `~/repos/balloon-e80bench/tools/`. This is the **E80 repo**, not balloon-fresh. **Assign to E80 worker, not worker-admin.** |
| HOST-3 | ✅ Correct | session_id injection. Depends on HOST-1. TDD with pytest. |
| HOST-4 | ✅ Correct | 23-field PKT parser. No deps — can start immediately. TDD with pytest. |
| RP-1 | ✅ Deferred | RP2040 firmware not yet written. Hardware not ready. Correct to defer. |
| INT-1 | ✅ Correct | End-to-end integration test. Depends on all Phase 1 tasks. **Operator-gate: requires Felix at bench.** |

### Risk Table Validation

| # | Risk | Severity | Validation |
|---|------|----------|------------|
| **R1** | **IWDG blocking per-packet output** | **HIGH** | ✅ **Critical path verified.** E80-2 (baud bump) → E80-6 (per-packet output) dependency is explicit. At 2 Mbps, 160-byte line = 0.8ms; at 190 pkt/s = 7.8% CPU. IWDG won't fire. **Schedule enforces E80-2 in Wave 1, E80-6 in Wave 2 — cannot be violated.** |
| R2 | M6 seq changes PER | LOW | ✅ `bench_stats_reset()` tracks per-session first/last seq. Verified in plan. |
| R3 | CRC-failed seq is garbage | MEDIUM | ✅ Documented in `rb_evt_t` struct. PKT line emits `crc_ok=0` with `seq=0` for CRC fails. |
| R4 | tx_buf enlargement | LOW | ✅ Additive change, backward-compatible. |
| **R5** | **Baud change breaks host tools** | **LOW** | ✅ **Mitigation: E80-2 + HOST-2 must deploy together.** Schedule places both in same wave window. ⚠️ HOST-2 is in E80 repo — assigned to E80 worker to ensure atomic deployment. |
| R6 | CR field changes radio behavior | LOW | ✅ Defaults preserve existing hardcoded values (LoRa 5=4/5, FLRC 1=3/4). |
| R7 | C3 payload format breaks TX/RX | MEDIUM | ✅ Format unchanged (4 bytes BE), only values change. Flash both boards simultaneously. **Operator-gate.** |
| R8 | snprintf flash overhead | LOW | ⚠️ **Add explicit Gate 2 check: post-build flash size < 35K.** If exceeded, switch to `console_put` incremental approach. |
| R9 | C3 is C3 not S3 | INFO | ✅ No impact. ESP-IDF + RadioLib work on C3. |
| R10 | rx_capture.py doesn't exist | INFO | ✅ Actual tools identified and targeted in plan. |

### Issues Found

1. **Quality gates version mismatch:** Plan references v2.2.0, current skill is v3.1.0. Use v3.1.0.
2. **HOST-2 repo mismatch:** Task is listed under "Host-Side Tools" but modifies `~/repos/balloon-e80bench/tools/e80_bench_ctl.py` (E80 repo). Reassigned to E80 worker.
3. **E80-6 flash budget:** `snprintf` from newlib adds ~500-1000 bytes. Current flash is 19,456 B (29.7%). After all E80 changes: ~20,500 B (31.3%). If snprintf pushes it over 35K (53%), switch to incremental `console_put`. **Added as explicit Gate 2 sub-check.**
4. **E80-5 test weakness:** Test is structural-only (doesn't actually verify non-resetting behavior at runtime). Acceptable for firmware without hardware, but Gate 6 (manager validation) should confirm the line removal by code review.
5. **C3 Gate 1 exceptions:** All C3 tasks declare Gate 1 exception (firmware, no host tests, build check is minimum). This is correct per quality-gates skill firmware exceptions.

---

## Worker Assignments

| Worker | Profile | Repo | Branch | Scope |
|--------|---------|------|--------|-------|
| Worker-E80 | worker-balloon | `~/repos/balloon-e80bench/` | `feat/e80-stm32-bench` | E80-1..8 + HOST-2 (E80 repo) |
| Worker-C3 | worker-balloon | `~/repos/balloon-fresh/mesh-stack/flrc-bench-espidf/` | `feat/e80-spi-bypass` | C3-1..5 |
| Worker-Host | worker-admin | `~/repos/balloon-fresh/tools/` + `scripts/` | (same repo, harmonization branch) | HOST-1, HOST-3, HOST-4 |

> **Note:** Worker-E80 and Worker-C3 share the `worker-balloon` profile but operate on **different repos/branches**. Dispatch as separate kanban tickets with explicit repo paths. No file overlap between them.

---

## File Overlap Analysis

### E80 Worker (serial — same repo, same branch)

| Task | Files Touched | Overlaps With |
|------|--------------|---------------|
| E80-1 | `bench.c:875`, `test_bench_cmd.c` | E80-4, E80-5, E80-6, E80-8 (bench.c) |
| E80-2 | `main.h:64` | None |
| E80-3 | `console.c:22`, `console.h` | None |
| E80-4 | `radio_bench.h:39-47`, `radio_bench.c`, `bench.c:500-530`, `test_bench_cmd.c` | E80-1, E80-5, E80-6, E80-8 (bench.c); E80-7 (radio_bench.h/c) |
| E80-5 | `bench.c:659`, `test_bench_stats.c` | E80-1, E80-4, E80-6, E80-8 (bench.c) |
| E80-6 | `bench.c:826-843,692-733`, `bench_pkt.c` (new), `bench_pkt.h` (new), `bench_cmd.c`, `bench_cmd.h`, `test_bench_pkt.c` (new) | E80-1, E80-4, E80-5, E80-8 (bench.c) |
| E80-7 | `radio_bench.c`, `radio_bench.h:62-68`, `test_bench_pkt.c` | E80-4 (radio_bench.h/c) |
| E80-8 | `bench.c` (CONFIG handler), `test_bench_cmd.c` | E80-1, E80-4, E80-5, E80-6 (bench.c) |
| HOST-2 | `tools/e80_bench_ctl.py` | None (tools/ subdir, no firmware overlap) |

**Verdict:** All E80 tasks are **serial** (single worker, shared `bench.c`). Order matters for dependencies. HOST-2 is parallel-safe within the E80 repo (disjoint file).

### C3 Worker (serial — same file `range_test.cpp`)

| Task | Files Touched | Overlaps With |
|------|--------------|---------------|
| C3-1 | `range_test.cpp:480`, `CMakeLists.txt` | All C3 tasks (range_test.cpp) |
| C3-2 | `range_test.cpp:144-151,450-451` | All C3 tasks (range_test.cpp) |
| C3-3 | `range_test.cpp:461-467`, `range_test.h` | All C3 tasks (range_test.cpp) |
| C3-4 | `range_test.cpp:429-434` | All C3 tasks (range_test.cpp) |
| C3-5 | (none — already done in C3-3) | N/A |

**Verdict:** All C3 tasks are **serial** (single worker, shared `range_test.cpp`).

### Host Worker (serial — shared `rx_range_logger.py` and `monitor_range.py`)

| Task | Files Touched | Overlaps With |
|------|--------------|---------------|
| HOST-1 | `tools/firmware_hash_gate.py` (new), `tests/test_firmware_hash_gate.py` (new), `tools/rx_range_logger.py`, `monitor_range.py` | HOST-3 (rx_range_logger.py), HOST-4 (monitor_range.py) |
| HOST-3 | `tools/session_manager.py` (new), `tests/test_session_id.py` (new), `tools/rx_range_logger.py` | HOST-1 (rx_range_logger.py) |
| HOST-4 | `tools/pkt_parser.py` (new), `tests/test_pkt_parser.py` (new), `monitor_range.py` | HOST-1 (monitor_range.py) |

**Verdict:** All Host tasks are **serial** (shared capture tool files). HOST-4 has no dependencies and can go first.

### Cross-Worker Parallelism

| Pair | File Overlap | Parallel-Safe? |
|------|-------------|----------------|
| Worker-E80 ↔ Worker-C3 | Different repos entirely | ✅ Yes |
| Worker-E80 ↔ Worker-Host | HOST-2 is in E80 repo (reassigned to E80 worker) | ✅ Yes |
| Worker-C3 ↔ Worker-Host | Both in `balloon-fresh` repo but disjoint paths (`mesh-stack/` vs `tools/`) | ✅ Yes |

**Conclusion:** All three workers can run **truly parallel** across waves. No file conflicts between workers.

---

## Execution Schedule

### Dependency Graph

```
WAVE 1 (Foundation)          WAVE 2 (Core)              WAVE 3 (Extensions)        WAVE 4 (Integration)
─────────────────            ─────────────              ──────────────────          ──────────────────
                              ┌→ E80-6 (30m) ──┐
E80-1 (5m) ─┐                │                ├→ E80-7 (15m) ─┐
E80-2 (5m) ─┼→ [GATE] ──────┼┤                │                │
E80-3 (5m) ─┤                │                ├→ E80-8 (5m) ──┼→ [GATE] ─→ INT-1
E80-4 (10m)─┤                │                │                │              │
E80-5 (5m) ─┘                │                │                │              │
HOST-2 (5m)                  │                │                │              ├── [OPERATOR GATE]
                             │                │                │              │   (Felix at bench)
C3-1 (15m) ─┐                │                │                │              │
C3-2 (10m) ─┼→ [GATE] ──────┼→ C3-3 (30m) ──┼→ C3-4 (15m) ──┼→ [GATE] ──────┘
                             │                │  C3-5 (0m) ──┘
                             │                │
HOST-4 (20m) ────────────────┘                │
                             │                │
              [GATE] ────────┼→ HOST-1 (30m) ─┼→ HOST-3 (15m) ─→ [GATE]
                             │   (needs E80-1, │
                             │    C3-1 done)   │
```

### Wave 0: Preparation (5 min, all workers)

| Worker | Task | Action |
|--------|------|--------|
| Worker-E80 | Prep | `cd ~/repos/balloon-e80bench && git checkout feat/e80-stm32-bench && git pull` |
| Worker-C3 | Prep | `cd ~/repos/balloon-fresh/mesh-stack/flrc-bench-espidf && git checkout feat/e80-spi-bypass && git pull` |
| Worker-Host | Prep | `cd ~/repos/balloon-fresh && git checkout <harmonization-branch> && git pull` |

**Gate 0: Branch verification** — Confirm all workers on correct branches. No code changes yet.

---

### Wave 1: Foundation (30 min wall time)

**Goal:** Establish prerequisites — boot banners, baud rate, buffer size, CR field, seq counter, PKT parser module.

| Worker | Task | Est. | Files | Deps | Gate 1 (TDD) | Gate 2 (Tests) |
|--------|------|------|-------|------|---------------|-----------------|
| Worker-E80 | E80-1: FW_HASH boot banner | 5m | `bench.c`, `test_bench_cmd.c` | None | Write test for `FW_GIT_SHA` defined | `make test-host` |
| Worker-E80 | E80-2: Baud bump to 2 Mbps | 5m | `main.h` | None | Exception: config-only | `make test-host` + `make firmware` |
| Worker-E80 | E80-3: Enlarge tx_buf to 160 | 5m | `console.c`, `console.h`, tests | None | Write test for `CONSOLE_TX_BUF_SIZE >= 160` | `make test-host` + `make firmware` |
| Worker-E80 | E80-4: Add `cr` field to config struct | 10m | `radio_bench.h`, `radio_bench.c`, `bench.c`, tests | None | Write test for `cfg.cr` field | `make test-host` + `make firmware` |
| Worker-E80 | E80-5: Non-resetting tx_seq (M6) | 5m | `bench.c:659`, tests | None | Structural test (documented) | `make test-host` + `make firmware` |
| Worker-C3 | C3-1: FW_HASH boot banner | 15m | `range_test.cpp:480`, `CMakeLists.txt` | None | Exception: firmware | `idf.py build` |
| Worker-C3 | C3-2: Non-resetting uint32 seq (M6) | 10m | `range_test.cpp:144-151` | None | Exception: firmware | `idf.py build` |
| Worker-Host | HOST-4: 23-field PKT parser | 20m | `tools/pkt_parser.py` (new), `tests/test_pkt_parser.py` (new) | None | Write pytest tests first | `pytest tests/test_pkt_parser.py` |

**Worker-E80 serial queue:** E80-1 → E80-2 → E80-3 → E80-4 → E80-5 (30 min total)
**Worker-C3 serial queue:** C3-1 → C3-2 (25 min total)
**Worker-Host serial queue:** HOST-4 (20 min total)

**Parallel?** ✅ Yes — three workers on disjoint repos. No cross-worker deps in Wave 1.

**⚠️ R1 enforcement:** E80-2 (baud bump) MUST complete in this wave before E80-6 in Wave 2. This is the critical IWDG mitigation.

#### Gate 1 (TDD red-first) — per task
- Each worker writes failing test before implementation
- C3 tasks: Gate 1 exception declared (firmware, build check is minimum)
- E80-2: Gate 1 exception (config-only change)

#### Gate 2 (Tests pass) — per task
- E80: `make test-host` passes, `make firmware` builds, **flash size < 35K** (R8 check)
- C3: `idf.py build` succeeds
- Host: `pytest` passes

#### Gate 2.5 (Cross-family cold review) — Wave 1 batch
- **Reviewer:** Kimi subagent (cross-family: GLM workers → Kimi reviewer)
- **Scope:** All Wave 1 diffs from all three workers
- **Focus areas:**
  - E80-2: Verify 2000000U is correct, comment updated
  - E80-4: Verify CR enum mapping (LoRa denominator form, FLRC register code)
  - C3-1: Verify CMake `execute_process` syntax, `FW_GIT_SHA` quoting
  - HOST-4: Verify PKT field count = 23, type conversions correct
- **Felix override:** Felix may skip Gate 2.5 for speed. Document override in commit message.

#### Gate 3 (Docs) — per task
- E80-3: `console.h` updated with `CONSOLE_TX_BUF_SIZE` constant
- E80-4: `radio_bench.h` struct documented
- All others: Inline comments sufficient

#### Gate 4 (Atomic commit) — per task
- Each task = one commit with conventional message
- `git status` clean after each commit

#### Gate 5 (Push) — per task
- `git push` succeeds after each commit

**Wall time estimate:** 30 min (E80 worker is longest) + 15 min gates = **~45 min**

---

### Wave 2: Core Implementation (30 min wall time)

**Goal:** Implement the 23-field PKT line format on all platforms. This is the heart of the harmonization.

| Worker | Task | Est. | Files | Deps | Gate 1 (TDD) | Gate 2 (Tests) |
|--------|------|------|-------|------|---------------|-----------------|
| Worker-E80 | E80-6: Per-packet output + 23-field format (M3+M4+M5) | 30m | `bench.c`, `bench_pkt.c` (new), `bench_pkt.h` (new), `bench_cmd.c`, `bench_cmd.h`, `test_bench_pkt.c` (new) | **E80-2, E80-3, E80-4** (Wave 1) | Write `test_bench_pkt.c` with 3 tests (basic, CRC fail, truncation) | `make test-host` + `make firmware` **with flash < 35K check (R8)** |
| Worker-C3 | C3-3: 23-field PKT format (M4+M5) + CONFIG command + CONFIG_START | 30m | `range_test.cpp:461-467`, `range_test.h` | **C3-2** (Wave 1) | Exception: firmware | `idf.py build` |
| Worker-Host | HOST-1: M2 firmware-hash gate | 30m | `tools/firmware_hash_gate.py` (new), `tests/test_firmware_hash_gate.py` (new), `tools/rx_range_logger.py`, `monitor_range.py` | **E80-1, C3-1** (Wave 1 — needs FW_HASH format) | Write pytest tests first (5 test classes) | `pytest tests/test_firmware_hash_gate.py` |

**Worker-E80:** E80-6 is the largest single task. Creates new `bench_pkt.c/h` module with `snprintf`-based formatter. Adds SESSION/CONFIG commands. Modifies RX_OK and RX_CRC handlers. Adds STAT? config fields.

**Worker-C3:** C3-3 replaces 20-field PKT printf with 23-field format. Adds SESSION/CONFIG command parsing. CONFIG_START is included here (absorbs C3-5).

**Worker-Host:** HOST-1 creates `firmware_hash_gate.py` module. Integrates into `rx_range_logger.py` and `monitor_range.py`. Capture tool refuses to start without valid FW_HASH.

**Parallel?** ✅ Yes — three workers on disjoint repos. Cross-worker deps satisfied by Wave 1.

**⚠️ R1 critical path:** E80-6 depends on E80-2 (baud bump). If E80-2 failed or was skipped, **E80-6 MUST NOT proceed** — IWDG will fire at 115200 baud with per-packet output.

#### Gate 1–5 — same as Wave 1, per task

#### Gate 2.5 (Cross-family cold review) — Wave 2 batch
- **Reviewer:** Kimi subagent
- **Focus areas:**
  - E80-6: **Field order in PKT line** (must match 23-field contract exactly), `snprintf` buffer safety, CRC event path, SESSION/CONFIG command parsing
  - C3-3: Field order, `esp_timer_get_time()` units (ms), `crc_ok` derivation from `readData` return, `freq_hz` conversion (MHz→Hz if needed)
  - HOST-1: Regex patterns for `FW_HASH=` and `fw=`, `validate_fw_hash` edge cases, `SESSION_START` header format
- **This is the most critical Gate 2.5** — the 23-field format is the contract between firmware and host tools. Field order mismatch = silent data corruption.

**Wall time estimate:** 30 min (all workers equal) + 15 min gates = **~45 min**

---

### Wave 3: Extensions (20 min wall time)

**Goal:** CRC-failed packet logging (M7), CONFIG_START markers (O4), baud update for host tools, session_id injection.

| Worker | Task | Est. | Files | Deps | Gate 1 (TDD) | Gate 2 (Tests) |
|--------|------|------|-------|------|---------------|-----------------|
| Worker-E80 | E80-7: Extract RSSI on CRC-failed packets (M7) | 15m | `radio_bench.c`, `radio_bench.h:62-68`, `test_bench_pkt.c` | **E80-6** (Wave 2) | Write test for CRC event with RSSI populated | `make test-host` + `make firmware` |
| Worker-E80 | E80-8: CONFIG_START markers (O4) | 5m | `bench.c` (CONFIG handler), `test_bench_cmd.c` | **E80-6** (Wave 2) | Structural test | `make test-host` + `make firmware` |
| Worker-E80 | HOST-2: Update E80 host tool baud to 2 Mbps | 5m | `~/repos/balloon-e80bench/tools/e80_bench_ctl.py` | **E80-2** (Wave 1) | Exception: config-only | `grep 2000000 tools/` |
| Worker-C3 | C3-4: Log CRC-failed packets (M7) | 15m | `range_test.cpp:429-434` | **C3-3** (Wave 2) | Exception: firmware | `idf.py build` |
| Worker-C3 | C3-5: Verify CONFIG_START (O4) | 0m | (none — already in C3-3) | **C3-3** (Wave 2) | N/A | N/A |
| Worker-Host | HOST-3: session_id injection | 15m | `tools/session_manager.py` (new), `tests/test_session_id.py` (new), `tools/rx_range_logger.py` | **HOST-1** (Wave 2) | Write pytest tests first | `pytest tests/test_session_id.py` |

**Worker-E80 serial queue:** E80-7 → E80-8 → HOST-2 (25 min total)
**Worker-C3 serial queue:** C3-4 → C3-5 (15 min total)
**Worker-Host serial queue:** HOST-3 (15 min total)

**Parallel?** ✅ Yes — three workers on disjoint repos/files.

**⚠️ R5 enforcement:** HOST-2 (baud update in E80 host tools) MUST deploy in the same session as E80-2 (firmware baud bump). Both are now in the E80 repo (HOST-2 reassigned). Commit and push together or in immediate sequence.

#### Gate 1–5 — same as Wave 1, per task

#### Gate 2.5 (Cross-family cold review) — Wave 3 batch
- **Reviewer:** Kimi subagent
- **Focus areas:**
  - E80-7: LR2021 register access on CRC failure path, no FIFO overflow, `rb_evt_t` field documentation
  - C3-4: `radio->getRSSI()` call on CRC error (RadioLib behavior on failed readData), seq extraction from corrupt buffer
  - HOST-3: UUID generation uniqueness, SESSION command format matching firmware parser

**Wall time estimate:** 25 min (E80 worker is longest) + 15 min gates = **~40 min**

---

### Wave 4: Integration Test (30+ min wall time)

**Goal:** End-to-end validation across all rigs + host tools.

| Worker | Task | Est. | Deps | Operator Gate? |
|--------|------|------|------|----------------|
| Manager | INT-1: End-to-end integration test | 30m | **All Phase 1 tasks** (Waves 1-3) | ⚠️ **YES — Felix at bench** |

#### Pre-Integration Gate (before INT-1)

| Check | Verification |
|-------|-------------|
| All Wave 1-3 tasks pushed | `git log --oneline` shows all commits on correct branches |
| All Gate 2.5 reviews passed | Review notes in commit messages or kanban |
| All Gate 6 (manager) approvals done | Kanban tickets in `done` status |
| E80 firmware builds | `cd ~/repos/balloon-e80bench && make firmware` — flash < 35K |
| C3 firmware builds | `cd ~/repos/balloon-fresh/mesh-stack/flrc-bench-espidf && idf.py build` |
| Host tools tests pass | `cd ~/repos/balloon-fresh && pytest tests/ -v` |

#### INT-1 Validation Checklist

```
□ E80 boot banner contains FW_HASH=<7hexchars>
□ C3 boot banner contains FW_HASH=<7hexchars>
□ Capture tool refuses to start without valid firmware hash
□ SESSION_START header written to output file
□ PKT lines have exactly 23 comma-separated fields
□ session_id is non-empty (injected by capture tool)
□ config_id and replicate are set (from CONFIG command)
□ seq values are monotonic and don't reset across sessions (M6)
□ ts_ms is monotonic within session
□ rssi_dbm is in realistic range (-150 to -10 dBm)
□ snr_db is non-zero for LoRa, zero for FLRC
□ crc_ok is 1 for good packets, 0 for CRC failures
□ CRC-failed packets appear as individual PKT lines (not just a count)
□ freq_hz, mod, sf, bw_khz, cr, power_dbm, pkt_size are populated
□ CONFIG_START markers appear when configuration changes
□ E80 UART operates reliably at 2,000,000 baud (no data loss at 190 pkt/s)
```

#### Operator Gate (Felix at bench)

The following requires physical hardware access:

| Action | Hardware | Who |
|--------|----------|-----|
| Flash E80 firmware | STM32F103C8T6 via SWD/serial | Felix |
| Flash C3 firmware (TX board) | ESP32-C3 via USB | Felix |
| Flash C3 firmware (RX board) | ESP32-C3 via USB | Felix |
| Run TX/RX test on E80 | E80 rig + CH340 | Felix |
| Run TX/RX test on C3 | C3 rig (2 boards) | Felix |
| Verify 2 Mbps UART reliability | E80 + oscilloscope/logic analyzer | Felix |
| Verify CRC-failed packet capture | RF attenuator or distance | Felix |

> **R7 enforcement:** C3 TX and RX boards must be flashed simultaneously. Payload values change (uint16→uint32 seq), format unchanged. Version mismatch = RX can't parse TX.

#### Gate 6 (Manager validation)

- Manager reviews INT-1 checklist
- All items checked → Phase 1 complete
- Any failures → bug tickets created, assigned to appropriate worker

**Wall time estimate:** 30 min (if hardware ready) + variable operator gate = **30 min – 2 hours**

---

## Summary: Wall Time Estimates

| Wave | Worker-E80 | Worker-C3 | Worker-Host | Wall Time (max) | Gates |
|------|-----------|-----------|-------------|-----------------|-------|
| 0: Prep | 5m | 5m | 5m | 5m | Gate 0: branch check |
| 1: Foundation | 30m | 25m | 20m | 30m | Gates 1-5 per task, Gate 2.5 batch |
| 2: Core | 30m | 30m | 30m | 30m | Gates 1-5 per task, Gate 2.5 batch (critical) |
| 3: Extensions | 25m | 15m | 15m | 25m | Gates 1-5 per task, Gate 2.5 batch |
| 4: Integration | — | — | — | 30m+ | Pre-integration gate, operator gate, Gate 6 |
| **Total** | **90m** | **75m** | **70m** | **~2.5h code + 0.5-2h hardware** | |

**With 3 parallel workers:** ~2.5 hours wall time for code + 30 min to 2 hours for hardware validation.

---

## Kanban Ticket Template

```
Title: [WAVE-n] TASK-ID: Short description
Labels: firmware-harmonization, wave-n, <worker-profile>
Assignee: <worker-profile>
Repo: <repo-path>
Branch: <branch-name>

## Task
<Copy from plan: Objective + Files + Context>

## Dependencies
- <task-id> (must be DONE before starting)

## Quality Gates
- [ ] Gate 1: TDD red-first (or exception declared)
- [ ] Gate 2: Tests pass (make test-host / idf.py build / pytest)
- [ ] Gate 2: Flash size < 35K (E80 only, R8)
- [ ] Gate 2.5: Cross-family cold review (Kimi reviewer)
- [ ] Gate 3: Docs updated in same commit
- [ ] Gate 4: Atomic commit, conventional message
- [ ] Gate 5: git push succeeds
- [ ] Gate 6: Manager validation

## Files
- Modify: <file list>
- Create: <new file list>

## Est. Time
<minutes> min

## Risk Notes
<R1/R5/R7/R8 as applicable>
```

---

## Risk Enforcement Checklist

| Risk | Enforcement Point | How |
|------|------------------|-----|
| **R1** (IWDG blocking) | E80-2 MUST complete before E80-6 | Wave 1 → Wave 2 ordering. Kanban dependency. **BLOCK E80-6 if E80-2 not done.** |
| **R5** (Baud breaks host tools) | E80-2 + HOST-2 deploy together | Both in E80 worker. HOST-2 in Wave 3 (after E80-2 in Wave 1). Deploy in same session. |
| **R7** (C3 TX/RX mismatch) | Flash both C3 boards simultaneously | Operator gate in INT-1. Felix flashes both before testing. |
| **R8** (snprintf flash overflow) | Post-build flash size check | Added to Gate 2 for E80-6: `arm-none-eabi-size build/e80_bench.elf` — if > 35K, switch to `console_put`. |
| **R3** (CRC seq garbage) | Documented in struct | E80-7 updates `radio_bench.h` comments. PKT line emits `seq=0` for CRC fails. |

---

## Critical Path

```
E80-2 (5m) → E80-6 (30m) → E80-7 (15m) → INT-1 (30m+)
```

**Critical path wall time:** 80+ minutes (code only). The baud bump → per-packet output → CRC logging → integration test chain is the longest dependency chain and the one most at risk from R1.

---

## Notes for Manager

1. **HOST-2 reassignment:** Originally listed as a Host task, but it modifies files in the E80 repo (`~/repos/balloon-e80bench/tools/`). Reassigned to Worker-E80 to keep E80 repo changes atomic and avoid cross-repo worker access issues.

2. **C3-5 is a no-op:** CONFIG_START was already implemented in C3-3. C3-5 is a verification step only. Don't create a separate kanban ticket — fold into C3-3's validation checklist.

3. **RP-1 deferred:** RP2040 firmware doesn't exist yet. All M-items will be built in from the start when the firmware is written. No Phase 1 ticket needed.

4. **Gate 2.5 reviewer:** Use Kimi-profiled subagent for cross-family review. GLM workers (worker-balloon, worker-admin) produce code → Kimi reviewer checks diffs with zero context. Felix may override for speed — document override in commit message or kanban comment.

5. **Operator gate timing:** Schedule INT-1 for when Felix is at the bench with both E80 and C3 hardware. Code can be complete (Waves 1-3) without hardware, but INT-1 requires physical flashing and RF testing.

6. **Flash budget monitor (R8):** After E80-6 build, check `arm-none-eabi-size build/e80_bench.elf`. Current: 19,456 B (29.7%). Expected after all changes: ~20,500 B (31.3%). Hard limit: 35,000 B (53%). If exceeded, create follow-up ticket to replace `snprintf` with incremental `console_put` approach.