# FIX-T6 pre-flight verdict — HW verify FLRC (BR sweep + LEN bisect)

Card: **t_c5d28b3f** (FIX-T6) · Date: 2026-09-16 · Branch: `fix/t6-sweep-preflight`
(base `origin/main` b862357) · Status: **HOLD — no sweep run** (operator/manager
decision on t_aaef19d4, option (a) merge-forward; card re-parented on
**t_52ede356 FIX-R2**).

This document is the executable precursor to the sweep, not the sweep. It records
(a) why the sweep could not produce a valid result today, with hardware evidence,
(b) the three tool defects that would have silently corrupted the verdict, now
fixed and gated, and (c) the exact commands for the resumed run.

## 1. Why there is no FLRC data in this card

FIX-T6's input is FIX-T5's flash. FIX-T5 (`t_4e225809`) **never flashed
anything**: its own thread records the blocked pre-flight and the card is `done`
only because the fleet offload write-back marked it so. FIX-T6's acceptance
criteria are all of the form "X must now pass CRC **after the Match123 fix**",
so running the sweep against any currently-attached board would measure the wrong
binary and produce a confident, meaningless verdict.

### Hardware reality (re-verified 2026-09-16, read-only, mutex held for the probe)

| Host | CMSIS-DAP probe | CH340 console | What it is |
|---|---|---|---|
| T470 / CobradorWave (this box) | **none** | **none** | `/dev/ttyUSB0-2` are the Sierra **EM7455 LTE modem** (`ID_MODEL_ID=9079`) — not E80 boards; `lsusb` shows no `1a86`/`2e8a` at all |
| DQ05 `c03rad0r-DQ05proplus` | `203584200D2D0D42` = **RX probe only** | `/dev/ttyUSB0` answers, `/dev/ttyUSB1` silent | one E80 board |

`/dev/ttyUSB0` on DQ05 @115200 baud (the pre-flight gate's own output):

```
ids={'TX': 'ID E80BENCH v1.2 fw=5fa7912 role=NONE armed=0 mod=lora sf=8 ', 'RX': ''}
PREFLIGHT FAIL: TX probe 148757200D2D1425 not attached to this host
PREFLIGHT FAIL: RX: no console reply to ID?
GATE EXIT=2
```

`fw=5fa7912` is the **Aug-29 demo firmware** — it is not `07dbb8d` (chain tip),
not `a1fcd27` (T3), not `b862357` (main). No FIX candidate has ever been flashed.

Two hard stops, either one sufficient on its own: (1) the **TX board is not on the
fleet** (`148757200D2D1425` absent from both hosts; `docs/FRIDAY-DEMO-HANDOVER-2026-08-29.md`
records board A as "walks with Felix"), and (2) the **reconciled head does not exist
yet** — `t_52ede356` is the card that produces it. A sweep needs TX and RX keyed
simultaneously; there is no partial-coverage version of this measurement.

## 2. Defects found while preparing the run (fixed here, gated)

### F1 — console-baud contract was broken on `main` (silent failure class)

`src/main.h`: `#define E80_BENCH_BAUD_DEFAULT 115200U`
`tools/e80_sweep_full.py`: `BAUD = 2000000` · `tools/e80_bench_ctl.py`: `BAUD = 2000000`

Both host tools hardcoded the 2 Mbaud console of the **unmerged** `feat/2g4-sweep`
firmware (0561b29). Against any board built from `main` every command is dropped:
the CSVs fill with "no reply" rows that read as **RF death** rather than a wrong
baud. Confirmed against real hardware — the board on DQ05 answers at **115200**
and is silent at 2000000.

Fix: the tool now **derives its baud from the firmware header** (single source of
truth, `fw_default_baud()` / `resolve_baud()`) with an `E80_BAUD` env override for
legacy firmware, and the pre-flight gate makes a tool↔firmware baud disagreement a
**fatal** condition instead of a silent no-op.

### F2 — the FIX chain base cannot run FIX-T6 as specified

Running this card's gate suite against the **chain tip `07dbb8d`** (same file, same
test file, its own `src/main.h`):

```
33 failed, 1 passed
FAILED TestFlrcCoverage::test_flrc_len_matrix_covers_acceptance_set_at_br650
FAILED TestFlrcCoverage::test_flrc_len_matrix_gap_is_not_silently_absorbed
FAILED TestFlrcCoverage::test_flrc_len_br_interaction_rows_present
FAILED TestFlrcCoverage::test_no_lora_row_exceeds_255
... (7/7 coverage tests red)
```

`07dbb8d`'s `build_configs()` has **no FLRC LEN matrix**: its only length list is
`LEN_SWEEP = [16, 64, 128, 255, 511]`, applied to LoRa **without the 255 cap** — so
the chain tip emits an illegal LoRa L=511 row and has no 256/300/384/448 FLRC rows
at all. The acceptance set (300/384/448/511 all 50/50 CRC-clean) is therefore
**untestable from the chain tip**. The GREEN implementation exists on
`fix/t1-sweep-start-validation` tip `2e4a2c6`, which is **not an ancestor of
`07dbb8d`** (the chain branches from T1's RED test commit `925474b`). The
reconciled head must fold in T1's implementation — rebasing T3+T4 alone does not
make this green.

### F3 — one duplicated config made knob-tuple section selection wrong

The full matrix emits `(br=650, pa=5, plen=64, 868 MHz)` **twice** (section D's BR
sweep row and section G's L64 row), so any `--section` predicate written over knob
tuples returns **9 rows for the 8-row BR sweep**. Each section is therefore its own
**builder** (`build_flrc_{br,len,len_br}_configs()`, reached through
`SECTION_BUILDERS`), not a filter over the full list.

The first attempt tagged each config with a `flag` key — that is a schema change,
and `tools/test_balloon_sweep.py::E80ParityTests::test_build_configs_identical`
pins dict-for-dict parity with `balloon_sweep.build_configs()`, so it went red.
The ctest line only names the failing test, so this hid behind a pre-existing
failure **of the same name** (`test_balloon_sweep_python`); it was caught only by
re-running the gate under an interpreter that has pyserial. Lesson for the next
run: compare the failure *reason*, never the test name, before calling something
pre-existing. With builders (no key added) the parity test is green and the full
111-row matrix is unchanged.

### Still open (no hardware, not measurable today)

**M1 — the +35 dB RSSI step at LEN ≥ 255** (`flrc-retest-20260821.md`: −69 → −34 dBm
at the same link budget, with LEN=255 the only CRC-failing length at both BRs).
Whether the Match123 fix also removes the RSSI discontinuity is exactly what the
resumed run must record per LEN. If it persists after Match123, it is a separate
finding (the radio config path really does change at 255), not a Match123 artefact.

## 3. What this branch delivers

* `tools/test_e80_sweep_preflight.py` — 40 host tests pinning the config-matrix
  coverage, the baud contract, the pre-flight decision, and (via a fake serial
  seam) that the gate only ever sends `ID?`.
* `tools/e80_sweep_full.py` — header-derived baud, `--section` selectors
  (`flrc-br` / `flrc-len` / `flrc-len-br` / `flrc-bisect` / `all`), `--npkts`,
  `--expected-fw`, `--preflight`, `--force`; LEN 253-257 bisect builder; a
  **pre-flight gate that refuses to key the radio** unless both boards are
  attached and (when `--expected-fw` is given) carry the firmware under test;
  per-section output stems so a bisect CSV can never be read as the BR sweep;
  `fw_measured` + preflight verdict recorded in the run metadata JSON.
* `tests/CMakeLists.txt` — the gate is wired into `make test-host`
  (works without pyserial: the tool's `serial` import is now tolerant).

Evidence: RED on `main` = **25 failed / 4 passed** before implementation; GREEN =
**40 passed**. `make test-host` on the branch = **21/21, 100% (0 failed)** — it now
runs 21 suites instead of the base's 20 and every one passes. The base's one red
(`test_balloon_sweep_python`) was an import error under the gate's `python3` (no
pyserial); making the tool's `serial` import tolerant lets that suite actually
execute, which is how the F3 regression above was caught. `tools/` pytest = 636
passed vs 596 at base (+40 new), same single pre-existing `cvm_relay_test.py`
error. `make firmware` = 100%, FLASH 29252 B (44.64%).

## 4. Runbook for the resumed card (after t_52ede356 reports its SHA)

```bash
cd ~/repos/balloon-e80bench && git fetch github && git checkout <reconciled-head>
cd firmware/e80-stm32-bench

# 0. gate FIRST — read-only, sends ID? only, exits 2 if anything is off
/usr/bin/python3 tools/e80_sweep_full.py --preflight --expected-fw <sha7>
#   must print Preflight: PASS with fw=<sha7> on BOTH boards.
#   A FAIL here is the answer, not an obstacle: do not key the radio.

# (a) FLRC BR sweep: 8 BRs 260-2600 @pa5 plen64 868, N=50
/usr/bin/python3 tools/e80_sweep_full.py --section flrc-br      --npkts 50 \
    --expected-fw <sha7> 2>&1 | tee /tmp/t6-flrc-br.log

# (b) LEN boundary bisect 253-257 @BR1300 pa10, N=20  (BUG 3 / M1)
/usr/bin/python3 tools/e80_sweep_full.py --section flrc-bisect   --npkts 20 \
    --expected-fw <sha7> 2>&1 | tee /tmp/t6-bisect.log

# (c) large-packet matrix: 16..511 @BR650 pa5 + 1300/384, 1300/511, 2600/511, N=50
/usr/bin/python3 tools/e80_sweep_full.py --section flrc-len      --npkts 50 \
    --expected-fw <sha7> 2>&1 | tee /tmp/t6-len.log
/usr/bin/python3 tools/e80_sweep_full.py --section flrc-len-br   --npkts 50 \
    --expected-fw <sha7> 2>&1 | tee /tmp/t6-len-br.log
```

Acceptance is unchanged from the card: `crc_err=0`, 50/50, PRBS `bit_err=0`,
monotonic `seq`, `drops=0` (STAT), RSSI −60..−80 dBm, **SNR 0.0 expected by
design** (FLRC sets `snr_qdb=0` — `radio_bench.c:432/459`). LEN=255 must pass CRC.
If chip CRC still fails 100% at FLRC, fall back to Plan B (`crc_type=CRC_OFF`,
app-layer `pcrc16`/PRBS verification) and re-run unchanged.

Only **after** a PASS preflight whose `fw_measured` matches `<sha7>` may the CSVs
be claimed as FIX-T6 evidence.
