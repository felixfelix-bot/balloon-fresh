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
  - FIXED (FIX-T2, branch fix/t2-rx-start-len-gate): gate extracted into
    `bench_start_len_ok(mod,len)` + `bench_start_len_err_str()` in bench_cmd.c;
    BOTH the RX and TX START branches now reject with the identical
    `ERR LEN (MAX 255 LORA / 511 FLRC)` reply. Truth table
    LEN {6,255,256,511,512} x {LORA,FLRC} pinned in tests/test_bench_cmd.c.

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
