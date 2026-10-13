# Firmware Harmonization — Wave 4+ Task Cards

> **Generated:** 2026-08-20
> **Source:** `2026-08-20_firmware-harmonization-schedule.md` (Phase 1, Waves 1-4)
> **Supplementary:** `2026-08-20_prbs15-harmonization-schedule.md` (PRBS-15 port, P1-P8)
> **Additional:** `docs/MEAS-task-chain-spec.md` (MEAS-1, MEAS-2)
> **Status:** Phase 1 (18 tasks) ✅ Complete. PRBS-15 port in progress (uncommitted, partial).

---

## Status Summary

### Phase 1 (Waves 1-3): COMPLETE ✅

All 18 tasks committed and pushed:
- E80-1 through E80-8: ✅ Committed on `balloon-e80bench` / `feat/persist-tx-seq`
- C3-1 through C3-4: ✅ Committed on `balloon-fresh` / `feat/c3-harmonization` (C3-5 = no-op, absorbed in C3-3)
- HOST-1 through HOST-4: ✅ Committed on `balloon-fresh` / `feat/c3-harmonization`
- HOST-2: ✅ Committed on `balloon-e80bench` / `feat/persist-tx-seq`
- RP-1: ✅ Committed on `balloon-fresh` / `feat/c3-harmonization` (RP2040 firmware built with harmonized 23-field format)
- Readiness check: ✅ `tools/fw_harm_readiness_check.sh` (READY=true)
- Measurement script: ✅ `tools/fw_harm_measurement.py`
- E80 build fix: ✅ `.thumb_set`→`.set` for binutils 2.45 compat

### Phase 1 Wave 4 (INT-1): NOT STARTED ⚠️

INT-1 is the end-to-end integration test requiring Felix at the bench. It depends on all Phase 1 tasks being done (they are) but has NOT been executed because it requires physical hardware access.

### PRBS-15 Port (P1-P8): IN PROGRESS — Uncommitted Changes

The E80 repo (`balloon-e80bench`) has significant uncommitted working-tree changes that implement most of the PRBS-15 port. These changes appear to be from a delegated task (deleg_374319f4) that is mid-flight. The working tree state is:

**Files modified (uncommitted):**
- `src/prbs.c` — Real PRBS-15 implementation (replaces TDD stub) — P2 ✅ code done
- `src/prbs.h` — PRBS-15 header — P2 ✅ code done
- `src/bench_payload.c` — xorshift32 replaced with `prbs15_fill`/`prbs15_verify` — P3 ✅ code done
- `src/bench_payload.h` — API updated: `bench_lfsr_next` removed, `bench_payload_verify` new signature — P4 ✅ code done
- `src/bench_pkt.c` — `bit_err`/`bytes_bad` now from `evt` fields (not hardcoded 0,0) — P3 scope ✅ code done
- `src/bench_pkt.h` — `bit_err`/`bytes_bad` fields added to `bench_pkt_evt_t` — ✅ code done
- `src/bench.c` — `#include "prbs.h"`, `prbs15_verify()` call in RX_OK path, `bit_err`/`bytes_bad` passed to `bench_pkt_evt_t` — P3 scope ✅ code done
- `src/radio_bench.c` — seq extraction changed from LE to BE (matches C3) — ✅ code done
- `tests/test_prbs.c` — 6 tests for PRBS-15 fill/verify (TDD) — P1 ✅ code done
- `tests/test_bench_payload.c` — Updated for PRBS-15 API, xorshift tests removed — P5 ✅ code done
- `tests/test_bench_seq.c` — LFSR tests renamed to PRBS, `test_seq_and_len_agree` removed — P5 ✅ code done
- `tests/test_bench_pkt.c` — `bench_pkt_format` calls updated for new `bit_err`/`bytes_bad` params — ✅ code done
- `CMakeLists.txt` — `src/prbs.c` added to firmware sources — P2 ✅ code done
- `tests/CMakeLists.txt` — `test_prbs` added, `prbs.c` linked to payload/seq tests — P1 ✅ code done

**Test results:** 12/13 host tests pass. 1 failure in `test_bench_payload` (test_big_endian_header expects BE seq but bench_payload.c still uses `put_u32le`). This is a known incompatibility — the test expects big-endian but the code writes little-endian. **This test failure needs to be resolved before committing.**

**What remains for PRBS-15:**
1. Fix `test_bench_payload.c::test_big_endian_header` — either change `bench_payload.c` to use `put_u32be` (matching C3), or fix the test to expect LE. The `radio_bench.c` diff already changed seq extraction to BE, so the payload header should also be BE for consistency. **The `put_u32le` in `bench_payload.c` needs to become `put_u32be` and `get_u32le` needs to become `get_u32be`.**
2. Commit all PRBS-15 changes (P1-P5) in proper atomic commits.
3. Push to remote.
4. P6: Verify C3 PRBS-15 matches E80 (read-only, C3 side).
5. P7: Cross-platform host test (`tests/test_prbs15_cross.py`) — NOT created yet.
6. P8: Documentation update — NOT done yet.

### MEAS-1 / MEAS-2: NOT STARTED

Spec exists at `docs/MEAS-task-chain-spec.md`. MEAS-1 requires Felix at bench. MEAS-2 is fully automated but depends on MEAS-1.

### Future Tasks (MEAS-3 through MEAS-6): NOT STARTED

Mentioned in MEAS task chain spec as deferred future work.

---

## Task Cards

### TASK: PRBS-COMMIT — Commit and Fix PRBS-15 Port (P1-P5 batch)

**Task ID:** PRBS-COMMIT
**Description:** The PRBS-15 port code (P1-P5) is implemented in the working tree but uncommitted. One test fails (`test_big_endian_header` expects BE but `bench_payload.c` still writes LE). Fix the endianness mismatch, verify all tests pass, then commit in proper atomic commits and push.

**Dependencies:**
- Phase 1 complete ✅ (all E80-1..8, C3-1..4, HOST-1..4 committed)
- PRBS-15 code written in working tree (deleg_374319f4 in-flight)

**Files to modify:**
- `firmware/e80-stm32-bench/src/bench_payload.c` — Change `put_u32le` → `put_u32be`, `get_u32le` → `get_u32be` (align with C3 big-endian seq header and `radio_bench.c` BE extraction)
- (All other PRBS files are already modified in working tree, just need committing)

**Quality gates:**
- [ ] Gate 1 (TDD): P1 tests written ✅ (test_prbs.c exists, 6 tests)
- [ ] Gate 2 (Tests): `make test-host` — ALL 13 tests must pass (currently 12/13, fix test_big_endian_header)
- [ ] Gate 2.1 (Flash): `make firmware` builds, `arm-none-eabi-size build-fw/e80_bench.elf` < 35,000 B
- [ ] Gate 3 (Docs): `bench_payload.h` comment already updated (says PRBS-15, not xorshift32)
- [ ] Gate 4 (Atomic commit): Commit in sequence:
  1. `git commit -m "test: add failing PRBS-15 host tests (TDD red-first)"` (P1: test_prbs.c, tests/CMakeLists.txt)
  2. `git commit -m "feat: port PRBS-15 generator/verifier from C3 to E80"` (P2: prbs.c, prbs.h, CMakeLists.txt)
  3. `git commit -m "feat: replace xorshift32 with PRBS-15 in bench_payload"` (P3: bench_payload.c, bench_pkt.c, bench_pkt.h, bench.c, radio_bench.c)
  4. `git commit -m "refactor: update bench_payload.h API for PRBS-15 verify with bit_err"` (P4: bench_payload.h)
  5. `git commit -m "test: update host tests for PRBS-15 payload verification"` (P5: test_bench_payload.c, test_bench_seq.c, test_bench_pkt.c)
- [ ] Gate 5 (Push): `git -c core.hooksPath=/dev/null push github feat/persist-tx-seq`

**Estimated time:** 30 min (fix endianness + verify tests + commit sequence + push)

**Repo + branch:** `~/repos/balloon-e80bench` / `feat/persist-tx-seq`

**Auto-dispatchable:** ✅ YES — No hardware needed. All work is code, tests, commit, push.

---

### TASK: P6 — Verify C3 PRBS-15 Matches E80

**Task ID:** P6
**Description:** Compare C3 `prbs.cpp`/`prbs.h` and E80 `src/prbs.c`/`src/prbs.h` line-by-line. Confirm identical algorithm, seed init, byte ordering. Run C3 build to confirm no breakage.

**Dependencies:**
- PRBS-COMMIT must be complete (E80 PRBS-15 committed and pushed)

**Files to modify:**
- None (read-only verification). If C3 needs any fixup: `mesh-stack/flrc-bench-espidf/main/prbs.cpp` (unlikely — C3 is the reference)

**Quality gates:**
- [ ] Gate 2 (Tests): `source ~/esp/esp-idf/export.sh && cd mesh-stack/flrc-bench-espidf && idf.py build` succeeds
- [ ] Gate 4 (Atomic commit): If no changes needed, no commit. If fixup: `git commit -m "docs: verify PRBS-15 matches E80 implementation"`
- [ ] Gate 5 (Push): `git -c core.hooksPath=/dev/null push github feat/c3-harmonization`

**Estimated time:** 10 min

**Repo + branch:** `~/repos/balloon-fresh` / `feat/c3-harmonization`

**Auto-dispatchable:** ✅ YES — Read-only verification + C3 build check. No hardware needed.

---

### TASK: P7 — Cross-Platform PRBS-15 Known-Vector Host Test

**Task ID:** P7
**Description:** Create `tests/test_prbs15_cross.py` — Python test that reimplements PRBS-15 and verifies against known-answer test vectors (precomputed from the C/E80 implementation). Include test vectors for seed=1 (len=32), seed=42 (len=128), seed=0xDEADBEEF (len=255), seed=0 (len=64).

**Dependencies:**
- PRBS-COMMIT must be complete (E80 PRBS-15 committed and pushed, test_prbs.c tests pass)
- P6 must be complete (C3 verified to match E80)

**Files to modify:**
- `tests/test_prbs15_cross.py` (CREATE) — Python reimplementation of PRBS-15 + known-vector tests

**Quality gates:**
- [ ] Gate 1 (TDD): Write pytest with known vectors → run → if vectors are wrong, test fails (expected). Fix vectors from C output.
- [ ] Gate 2 (Tests): `cd ~/repos/balloon-fresh && python3 -m pytest tests/test_prbs15_cross.py -v` passes
- [ ] Gate 4 (Atomic commit): `git commit -m "test: add cross-platform PRBS-15 known-vector tests"`
- [ ] Gate 5 (Push): `git -c core.hooksPath=/dev/null push github feat/c3-harmonization`

**Estimated time:** 20 min

**Repo + branch:** `~/repos/balloon-fresh` / `feat/c3-harmonization`

**Auto-dispatchable:** ✅ YES — Python test, no hardware. Requires precomputing test vectors from E80 C test output (can run `test_prbs` host test and capture stdout).

**Note:** Test vectors need to be precomputed. Generate by running the E80 host test `test_prbs.c` and capturing the PRBS-15 output bytes for known seeds. Or compile a small C helper that calls `prbs15_fill` and prints hex.

---

### TASK: P8 — PRBS-15 Documentation

**Task ID:** P8
**Description:** Document that both E80 and C3 platforms now use PRBS-15 as the common BER test pattern. Update READMEs in both repos.

**Dependencies:**
- PRBS-COMMIT complete
- P7 complete (cross-platform verification done)

**Files to modify:**
- `~/repos/balloon-e80bench/firmware/e80-stm32-bench/README.md` or `~/repos/balloon-e80bench/docs/ber-pattern.md` (CREATE/UPDATE) — Document PRBS-15 polynomial, seed, generation, verification, bit counting
- `~/repos/balloon-fresh/mesh-stack/flrc-bench-espidf/README.md` (UPDATE) — Note that C3 is the reference implementation, E80 now matches

**Quality gates:**
- [ ] Gate 3 (Docs): Documentation updated in both repos
- [ ] Gate 4 (Atomic commit):
  - E80 repo: `git commit -m "docs: document PRBS-15 as common BER pattern for both platforms"`
  - C3 repo: `git commit -m "docs: note C3 as PRBS-15 reference implementation"`
- [ ] Gate 5 (Push): Push to both repos

**Estimated time:** 10 min

**Repo + branch:**
- `~/repos/balloon-e80bench` / `feat/persist-tx-seq`
- `~/repos/balloon-fresh` / `feat/c3-harmonization`

**Auto-dispatchable:** ✅ YES — Documentation only, no hardware.

---

### TASK: INT-1 — End-to-End Integration Test

**Task ID:** INT-1
**Description:** End-to-end validation across all rigs + host tools. Verify the full 23-field harmonized output pipeline produces valid, realistic RF data end-to-end. Execute the 15-item INT-1 validation checklist (boot banner FW_HASH, 23-field PKT lines, session_id, CONFIG_START, monotonic seq, realistic RSSI, CRC-failed PKT lines, 2 Mbps UART reliability, etc.).

**Dependencies:**
- All Phase 1 tasks (E80-1..8, C3-1..4, HOST-1..4) — ✅ COMPLETE
- All PRBS-15 tasks (P1-P8) — IN PROGRESS (PRBS-COMMIT, P6, P7, P8 must finish first)
- E80 firmware builds with PRBS-15 changes
- C3 firmware builds
- Host tools tests pass: `cd ~/repos/balloon-fresh && pytest tests/ -v`

**Files to modify:**
- None (validation task, no code changes). May produce bug tickets if failures found.

**Quality gates:**
- [ ] Pre-Integration Gate:
  - All Wave 1-3 tasks pushed (verified via `git log --oneline`)
  - All Gate 2.5 reviews passed
  - E80 firmware builds: `cd ~/repos/balloon-e80bench/firmware/e80-stm32-bench && make firmware` — flash < 35K
  - C3 firmware builds: `source ~/esp/esp-idf/export.sh && cd mesh-stack/flrc-bench-espidf && idf.py build`
  - Host tools tests pass: `cd ~/repos/balloon-fresh && pytest tests/ -v`
- [ ] INT-1 Validation Checklist (15 items):
  - □ E80 boot banner contains `FW_HASH=<7hexchars>`
  - □ C3 boot banner contains `FW_HASH=<7hexchars>`
  - □ Capture tool refuses to start without valid firmware hash
  - □ SESSION_START header written to output file
  - □ PKT lines have exactly 23 comma-separated fields
  - □ session_id is non-empty (injected by capture tool)
  - □ config_id and replicate are set (from CONFIG command)
  - □ seq values are monotonic and don't reset across sessions (M6)
  - □ ts_ms is monotonic within session
  - □ rssi_dbm is in realistic range (-150 to -10 dBm)
  - □ snr_db is non-zero for LoRa, zero for FLRC
  - □ crc_ok is 1 for good packets, 0 for CRC failures
  - □ CRC-failed packets appear as individual PKT lines (not just a count)
  - □ freq_hz, mod, sf, bw_khz, cr, power_dbm, pkt_size are populated
  - □ CONFIG_START markers appear when configuration changes
  - □ E80 UART operates reliably at 2,000,000 baud (no data loss at 190 pkt/s)
- [ ] Gate 6 (Manager validation): Manager reviews INT-1 checklist. All items checked → Phase 1 complete.

**Estimated time:** 30 min (if hardware ready) – 2 hours (variable operator gate)

**Repo + branch:**
- `~/repos/balloon-e80bench` / `feat/persist-tx-seq` (E80 firmware)
- `~/repos/balloon-fresh` / `feat/c3-harmonization` (C3 firmware + host tools)

**Auto-dispatchable:** ❌ NO — **Requires Felix at bench.** Operator gate actions:
- Flash E80 firmware (STM32F103C8T6 via SWD/serial)
- Flash C3 firmware — TX board AND RX board simultaneously (R7 enforcement)
- Run TX/RX test on E80 rig
- Run TX/RX test on C3 rig (2 boards)
- Verify 2 Mbps UART reliability (oscilloscope/logic analyzer)
- Verify CRC-failed packet capture (RF attenuator or distance)

**Risk notes:**
- **R7:** C3 TX and RX boards must be flashed simultaneously. Payload values change (uint16→uint32 seq). Version mismatch = RX can't parse TX.
- **R1:** IWDG must not fire during continuous packet capture at 2 Mbps.
- **R5:** 2 Mbps baud rate validated under real traffic (not just unit test).

---

### TASK: MEAS-1 — Range Test Capture at 3 Distances

**Task ID:** MEAS-1
**Description:** Record the first RF measurement using the fully harmonized 23-field per-packet output format on the E80 rig (STM32F103C8T6 + LR2021). Range test at three fixed distances (1m, 10m, 30m) to characterize RSSI degradation and PER as a function of TX-RX separation. 60-second captures at each distance.

**Dependencies:**
- INT-1 must be in `done` status (all 15 format compliance items verified)
- All Phase 1 tasks implicitly complete (INT-1 depends on all)
- All PRBS-15 tasks complete (bit_err/bytes_bad fields populated in PKT lines)

**Files to modify:**
- `data/meas-1/` (CREATE directory + capture outputs)
- `data/meas-1/meas-1-metadata.json` (CREATE — session metadata)
- Uses existing tools: `tools/fw_harm_measurement.py`, `tools/capture_sweep.py`

**Quality gates (10 gates from MEAS spec):**
- [ ] QG-1: Firmware hash gate — `fw_harm_measurement.py` reports valid FW_HASH
- [ ] QG-2: Packet count — ≥ 50 PKT lines per distance
- [ ] QG-3: 23-field completeness — Every PKT line has exactly 23 fields
- [ ] QG-4: RSSI realism — rssi_dbm in [-150, -10] for all packets
- [ ] QG-5: RSSI distance correlation — Mean RSSI at 30m < mean RSSI at 1m
- [ ] QG-6: seq monotonicity — seq values monotonically increasing within each session
- [ ] QG-7: CRC failures at far distance — ≥ 1 `crc_ok=0` PKT line in 30m capture
- [ ] QG-8: Session ID present — Every PKT line has non-empty session_id
- [ ] QG-9: CONFIG_START present — ≥ 1 CONFIG_START marker in raw output
- [ ] QG-10: No data loss at 2 Mbps — Raw line count ≈ CSV PKT line count

**Estimated time:** 35 min (10m setup + 20m captures + 5m validation)

**Repo + branch:**
- `~/repos/balloon-fresh` / `feat/c3-harmonization` (capture tools)
- `~/repos/balloon-e80bench` / `feat/persist-tx-seq` (E80 firmware)

**Auto-dispatchable:** ❌ NO — **Requires Felix at bench.** Physical actions:
- Flash E80 firmware (TX + RX boards)
- Connect E80 RX to host laptop via CH340 USB-serial
- Position TX at 1m, 10m, 30m (clear LOS, outdoor)
- Power on TX, confirm TX LED blinking
- Post `HARDWARE_READY` confirmation to kanban task comment

**Risk notes:**
- Weather dependency: Outdoor LOS requires clear weather. Fallback to indoor at reduced distances.
- R1 (IWDG): Already validated in INT-1. If IWDG fires, E80 resets — detectable via boot banner in raw output.

---

### TASK: MEAS-2 — Analyze MEAS-1 Data + Generate Summary Report

**Task ID:** MEAS-2
**Description:** Parse the three capture datasets from MEAS-1, synthesize a cross-distance comparison summary report, write it to markdown, and surface to Felix. Create `tools/synthesize_meas_report.py` analysis script.

**Dependencies:**
- MEAS-1 must be in `done` status with all 10 quality gates passed
- `data/meas-1/` directory exists with 3 report files, 3 CSV files, and metadata JSON

**Files to modify:**
- `tools/synthesize_meas_report.py` (CREATE) — Synthesis script that reads JSON + CSV, builds comparison table, checks quality gates, writes report
- `docs/MEAS-1-report.md` (CREATE) — Human-readable summary report
- `data/meas-1/analysis_summary.json` (CREATE) — Machine-readable stats

**Quality gates:**
- [ ] QG-1: Report exists and is non-empty valid markdown
- [ ] QG-2: All distances analyzed (1m, 10m, 30m)
- [ ] QG-3: RSSI correlation noted (decreases with distance)
- [ ] QG-4: CRC analysis included (count + rate per distance)
- [ ] QG-5: Gate summary (pass/fail for all 10 MEAS-1 gates)
- [ ] QG-6: Signal message sent to Felix
- [ ] QG-7: Analysis script committed and pushed
- [ ] QG-8: JSON summary written
- [ ] Gate 4 (Atomic commit): `git commit -m "feat: add MEAS-1 analysis report + synthesis script"`
- [ ] Gate 5 (Push): `git -c core.hooksPath=/dev/null push github feat/c3-harmonization`

**Estimated time:** 15 min (8m script + 3m analysis + 4m commit/push/Signal)

**Repo + branch:** `~/repos/balloon-fresh` / `feat/c3-harmonization`

**Auto-dispatchable:** ✅ YES — Fully automated. No Felix at bench required. Parses existing data, generates report, posts to Signal.

---

### TASK: MEAS-3 — C3 Rig Cross-Validation (DEFERRED)

**Task ID:** MEAS-3
**Description:** Cross-validate the E80 range test results (MEAS-1) on the C3 rig. Run the same 3-distance range test on ESP32-C3 + LR2021 to confirm both platforms produce comparable RSSI/PER data.

**Dependencies:**
- MEAS-1 complete (E80 baseline established)
- MEAS-2 complete (analysis report confirms E80 data is valid)

**Files to modify:**
- `data/meas-3/` (CREATE) — C3 capture outputs
- May need C3-specific capture script adjustments

**Quality gates:** TBD (similar to MEAS-1 gates, adapted for C3)

**Estimated time:** 35-45 min (C3 has 2-board setup, R7 enforcement)

**Repo + branch:** `~/repos/balloon-fresh` / `feat/c3-harmonization`

**Auto-dispatchable:** ❌ NO — Requires Felix at bench (flash 2 C3 boards simultaneously, position at distances).

---

### TASK: MEAS-4 — SF/BW Sweep (DEFERRED)

**Task ID:** MEAS-4
**Description:** Sweep Spreading Factor and Bandwidth configurations on the E80 rig to characterize throughput vs. range tradeoffs. Uses `config_id` variation in the harmonized format.

**Dependencies:**
- MEAS-1 complete (baseline range test confirmed pipeline works)
- MEAS-2 complete (analysis tooling validated)

**Files to modify:**
- `data/meas-4/` (CREATE) — Sweep capture outputs
- May need sweep automation script

**Quality gates:** TBD

**Estimated time:** 60-90 min (multiple config combinations)

**Repo + branch:** `~/repos/balloon-fresh` / `feat/c3-harmonization`

**Auto-dispatchable:** ❌ NO — Requires Felix at bench (flash, position, config changes).

---

### TASK: MEAS-5 — Walk Test with GPS (DEFERRED)

**Task ID:** MEAS-5
**Description:** Mobile walk test carrying the RX board while TX is fixed. GPS coordinates logged alongside PKT data to produce a real-world RSSI-vs-position map.

**Dependencies:**
- MEAS-1 complete (fixed-distance baseline established)
- GPS module integration (not yet built — hardware dependency)

**Files to modify:**
- `data/meas-5/` (CREATE) — Walk test captures with GPS data
- May need GPS data integration in capture tool

**Quality gates:** TBD

**Estimated time:** 60 min (walk route + captures)

**Repo + branch:** `~/repos/balloon-fresh` / `feat/c3-harmonization`

**Auto-dispatchable:** ❌ NO — Requires Felix at bench + GPS hardware (not yet available).

---

### TASK: MEAS-6 — Throughput at Multiple Configs (DEFERRED)

**Task ID:** MEAS-6
**Description:** Sweep mode with `config_id` variation — measure throughput at multiple radio configurations (modulation, SF, BW, CR, power, packet size combinations).

**Dependencies:**
- MEAS-1 complete (baseline confirmed)
- MEAS-4 complete or in progress (SF/BW sweep establishes config methodology)

**Files to modify:**
- `data/meas-6/` (CREATE) — Multi-config throughput captures

**Quality gates:** TBD

**Estimated time:** 90-120 min (many config combinations)

**Repo + branch:** `~/repos/balloon-fresh` / `feat/c3-harmonization`

**Auto-dispatchable:** ❌ NO — Requires Felix at bench (flash, config changes, extended capture sessions).

---

## Execution Order

```
PRBS-COMMIT (30m, auto) ──┬→ P6 (10m, auto) ──┐
                          │                    ├→ P7 (20m, auto) ──┐
                          │                    │                    ├→ P8 (10m, auto) ──┐
                          │                    │                    │                    │
                          └────────────────────┘                    │                    │
                                                                    ↓                    ↓
                                                              [PRBS-15 COMPLETE]  [PRBS-15 DOCS DONE]
                                                                    │
                                                                    ↓
                                                            INT-1 (30m-2h, FELIX AT BENCH)
                                                                    │
                                                                    ↓
                                                            MEAS-1 (35m, FELIX AT BENCH)
                                                                    │
                                                                    ↓
                                                            MEAS-2 (15m, AUTO)
                                                                    │
                                                                    ↓
                                                            [MEAS-1/2 COMPLETE]
                                                                    │
                                                    ┌─────────────────┼─────────────────┐
                                                    ↓                 ↓                 ↓
                                              MEAS-3 (deferred)  MEAS-4 (deferred)  MEAS-5/6 (deferred)
                                              Felix at bench      Felix at bench      Felix at bench + GPS
```

## Auto-Dispatchable Tasks (No Hardware Needed)

| # | Task | Est. | Dependencies | Worker |
|---|------|------|--------------|--------|
| 1 | PRBS-COMMIT | 30m | Phase 1 done | worker-balloon (E80) |
| 2 | P6 | 10m | PRBS-COMMIT | worker-balloon (C3) |
| 3 | P7 | 20m | PRBS-COMMIT, P6 | worker-admin (host) |
| 4 | P8 | 10m | P7 | worker-balloon (E80) + worker-admin (C3) |
| 5 | MEAS-2 | 15m | MEAS-1 | worker-admin (host) |

**Total auto-dispatchable:** ~85 min (can parallelize P6 and P7 partially)

## Felix-at-Bench Tasks (Hardware Required)

| # | Task | Est. | Dependencies | Hardware |
|---|------|------|--------------|----------|
| 1 | INT-1 | 30m-2h | All Phase 1 + PRBS-15 done | E80 rig, C3 rig (2 boards), CH340, oscilloscope |
| 2 | MEAS-1 | 35m | INT-1 done | E80 rig, CH340, outdoor space |
| 3 | MEAS-3 | 35-45m | MEAS-2 done | C3 rig (2 boards), outdoor space |
| 4 | MEAS-4 | 60-90m | MEAS-2 done | E80 rig, outdoor space |
| 5 | MEAS-5 | 60m | MEAS-2 done + GPS hardware | E80/C3 rig + GPS module |
| 6 | MEAS-6 | 90-120m | MEAS-4 done | E80 rig, extended session |

---

## Notes for Manager

1. **PRBS-15 working tree state:** The E80 repo has uncommitted PRBS-15 changes that are ~95% complete. One test fails (`test_big_endian_header`) due to endianness mismatch — `bench_payload.c` still uses `put_u32le` for the seq header, but `radio_bench.c` was already changed to extract seq as big-endian, and `test_bench_payload.c::test_big_endian_header` expects BE. Fix: change `put_u32le` → `put_u32be` and `get_u32le` → `get_u32be` in `bench_payload.c`. This aligns the E80 header format with C3 (which uses 4-byte BE seq).

2. **PRBS-COMMIT should be dispatched FIRST.** It unblocks P6, P7, P8, and INT-1. All four downstream tasks depend on the PRBS-15 port being committed and pushed.

3. **INT-1 is the critical path to MEAS-1.** INT-1 requires Felix at the bench and validates the full pipeline. MEAS-1 (first real RF measurement) cannot start until INT-1 passes. Schedule Felix for a bench session that covers both INT-1 and MEAS-1 in one sitting (~1-2.5 hours).

4. **MEAS-2 can be dispatched immediately after MEAS-1.** It's fully automated — no Felix needed. The worker just parses the captured data and generates the report.

5. **MEAS-3 through MEAS-6 are deferred.** They are documented here for completeness but should not be dispatched until MEAS-1/MEAS-2 results are reviewed and Felix confirms the baseline data is valid.

6. **The original plan file `2026-08-19_firmware-harmonization.md` was not found.** It may have been renamed or merged into the schedule file. The schedule file (`2026-08-20_firmware-harmonization-schedule.md`) contains all task definitions from the original plan, so no tasks are missing.

7. **RP-1 is complete.** The RP2040 firmware was built with the harmonized 23-field format (commit `7c99923` on `feat/c3-harmonization`). The schedule originally deferred RP-1, but it has since been implemented. No remaining RP2040 tasks.

8. **C3-5 is a no-op.** CONFIG_START was already implemented in C3-3. No separate ticket needed (per schedule Notes for Manager #2).