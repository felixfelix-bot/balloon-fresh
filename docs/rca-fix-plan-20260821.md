# RCA & Fix Plan — L511 non-bug, FLRC CRC, LEN=255 boundary (consultant + spot-test data)

Date: 2026-08-21. Consultant RCA (glm-5.2, 31 API calls, verified against code,
git history, RadioLib LR2021 module, balloon-range-tests 9b740aa) + same-day
empirical spot-tests (flrc-retest-20260821.md).

## BUG 1 — LoRa LEN=511: RESOLVED, no fw defect
- bench.c:688 correctly refuses LEN>255 LoRa (255 = uint8_t silicon limit in
  lr20xx lora pkt params). Host tool read-but-ignored the ERR reply → 90 s stall.
- Fix: host START-reply validation (fail fast, error= column) + LoRa LEN rows
  capped at 255 + NEW FLRC LEN sweep section (16..511 @BR650) where 511 is legal.
- Secondary: RX-board START lacks the cap (cosmetic parity, fix it).

## BUG 2 — FLRC CRC: root cause high confidence
- Primary (H1): FLRC RX sync-match `MATCH_SYNCWORD_1` broken for 32-bit sync
  words on LR2021 — sync bytes leak into payload → chip CRC fails 100% while
  packets demodulate. Both references (RadioLib, balloon-range-tests/TheClams
  raw config 0x7C = Match123) require `RX_MATCH_SYNCWORD_1_OR_2_OR_3`.
  range-tests' old Match1 (0x4C) produced the same failure family (9b740aa).
- Co-required (H2): bench NEVER calls lr20xx_radio_fifo_clear_rx() (0 grep
  matches). RadioLib clears after every read; 9b740aa fix #3 was exactly this.
- Fallback if hw verify fails: CRC_OFF + app-layer pcrc16/PRBS (range-tests'
  final architecture; pcrc16 field already in flashed fw).
- SNR=0.0 in FLRC is BY DESIGN (radio_bench.c:432/459 sets snr_qdb=0) — document.
- Watch: 115200 console vs 10 ms FLRC gaps — check drops= in STAT.

## BUG 3 (NEW, spot-test data) — LEN=255 exactly fails FLRC CRC
- 0/10 CRC at LEN=255 both BRs tested; 254≤ clean below, 256-511 clean above.
- RSSI jumps +35 dB at LEN≥255 (-69→-34) — radio config path actually differs
  at the 255 boundary. Suggests fw/radio branch on len>255 vs <=255 with an
  off-by-one at the boundary, or different RSSI readout path at large frames.
- Action: golden-test + boundary bisect on hardware (LEN 254/255/256/300),
  grep for 255 branches in radio_bench.c / bench.c payload paths.

## Task schedule (kanban e80-bench, strict quality gates)

| ID | Task | Deps |
|----|------|------|
| FIX-T1 | sweep tool: START-reply validation + LoRa cap + FLRC LEN section | — |
| FIX-T2 | fw: RX START len parity gate (TDD truth table) | — |
| FIX-T3 | fw: FLRC Match123 + pkt-params golden bytes + Match1 tripwire + 255-branch hunt (TDD) | — |
| FIX-T4 | fw: RX FIFO clear per re-arm (+TX clear) | T3 |
| FIX-T5 | build + SWD flash both boards (reset halt; resume) | T2,T3,T4 |
| FIX-T6 | HW verify: FLRC BR sweep + LEN boundary bisect 254/255/256 | T5 |
| FIX-T7 | HW verify: LoRa LEN sweep + negative test (LoRa L511 → ERR fast) | T5 |
| FIX-T8 | docs + data: README limits, Match123 rationale, SNR=0 note, new CSVs | T6,T7 |

Acceptance: FLRC 8 BR rows crc_err=0 50/50, PRBS bit_err=0, seq monotonic,
drops=0; FLRC L511 50/50 clean; LoRa LEN rows all tx_done 50/50; negative test
ERR within 1 s recorded in error= col.

## FIX-T6 pre-flight (2026-09-16) — HOLD, tool gate added

**Read `docs/FIX-T6-preflight-verdict-20260916.md` before running FIX-T6.** It
records, with hardware evidence, that FIX-T5 never flashed (the card is `done`
only via the fleet write-back), that only ONE E80 board (RX probe
`203584200D2D0D42`, fw=`5fa7912`) is attached to the fleet and that the TX board
probe is absent — so no sweep may be claimed as FIX-T6 evidence until
`t_52ede356` (FIX-R2) flashes the reconciled head.

Three defects were found and fixed on branch `fix/t6-sweep-preflight`
(base `origin/main` b862357) so the resumed run cannot silently produce a
misleading verdict:

1. **Console baud contract (silent failure).** `src/main.h` default is **115200**,
   but `tools/e80_sweep_full.py` and `tools/e80_bench_ctl.py` hardcoded
   `BAUD = 2000000` (the unmerged `feat/2g4-sweep` fw). Against a `main`-based
   board every command is dropped and the CSV reads as RF death. The sweep tool
   now derives the baud from the firmware header (`fw_default_baud()` /
   `resolve_baud()`, `E80_BAUD` override) and the pre-flight gate makes a
   mismatch fatal. Verified on hardware: the DQ05 board answers at 115200.
2. **The chain tip cannot cover the acceptance set.** `07dbb8d`'s
   `build_configs()` has no FLRC LEN matrix (only `LEN_SWEEP` applied to LoRa,
   uncapped), so 256/300/384/448 rows do not exist and an illegal LoRa L511 row
   is emitted — measured: 33 failed / 1 passed for this card's gate suite against
   that tree. The GREEN implementation (`2e4a2c6`, T1 tip) is **not an ancestor**
   of the chain tip; the reconciled head must fold it in.
3. **Duplicated `(br650, pa5, plen64)` row** (sections D and G) broke knob-tuple
   section selection (9 rows for an 8-row section); each section is now its own
   builder reached via `SECTION_BUILDERS`. (Tagging the config dicts with a `flag`
   key was the first attempt and is WRONG here: it breaks the dict-for-dict parity
   test with `balloon_sweep.build_configs()` in `tools/test_balloon_sweep.py`.
   That test hid behind a same-named pre-existing ctest failure — compare failure
   REASONS, not test names.)

New gate: `tools/test_e80_sweep_preflight.py` (40 tests, no pyserial needed) is
wired into `make test-host` and pins the matrix coverage, the baud contract and
the pre-flight decision — including that the gate only ever sends `ID?`. The
sweep now refuses to key the radio unless `--preflight` passes for both boards
and (with `--expected-fw <sha7>`) the boards report the firmware under test;
`fw_measured` is recorded in the run metadata JSON. With the tool's `serial`
import made tolerant, `make test-host` is **21/21 (100%)** on this branch, versus
19/20 on base.
