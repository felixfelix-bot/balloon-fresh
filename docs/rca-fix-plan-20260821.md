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

## FIX-T3 results (2026-08-21, branch fix/t3-flrc-match123)

**Match1 → Match123 shipped.** `src/radio_bench.c` FLRC pkt params now set
`match_sync_word = LR20XX_RADIO_FLRC_RX_MATCH_SYNCWORD_1_OR_2_OR_3`.
Rationale unchanged (BUG 2 above): Match1 + 32-bit sync word leaks sync
bytes into the payload → chip CRC fails 100% while packets still demodulate.

**Golden pkt-params bytes pinned by host tests** (`tests/test_radio_bench_cfg.c`,
runs in ctest): the test harness fake-HALs the lr20xx driver and captures
every SPI command emitted by the REAL `radio_bench.c` + REAL vendored driver.
FLRC SetPacketParams (opcode 0x0249, 6 B) on-wire golden values, verified
across apply_cfg / rx_arm(255) / tx_packet(len=255):

- byte[2] = 0x1E — PREAMBLE_LEN_32_BITS (0x07<<2) | SYNCWORD_LENGTH_4_BYTES (0x02)
- byte[3] = 0x7D — CRC_2_BYTES (0x01) | PKT_FIX_LEN (0x01<<2) |
  MATCH_1_OR_2_OR_3 (0x07<<3) | TX_SYNCWORD_1 (0x01<<6)
  (before the fix: 0x4D = Match1; balloon-range-tests 9b740aa raw cfg was
  0x7C = same as 0x7D but CRC_OFF)
- byte[4..5] = pld_len (0x00FF at apply_cfg; patched per op by rx_arm/tx)

Plus a Match1 tripwire test: decoded match field must equal Match123 and must
NOT equal Match1 — fires if anyone reintroduces the bug. Do not "fix" that test.

**LEN=255 branch hunt: NO firmware branch exists.** Greps over the full fw
payload path (`src/radio_bench.c`, `src/bench.c`, `src/buffer.c`, vendored
`lr20xx_radio_fifo.c` + `radio_hal/lr20xx_hal.c`) for 255/0xFF boundary
conditions found none. All 255s are constants (defaults, demo parity) or the
correct per-mod cap gate `len > max_len` (bench.c:688; 255 LoRa / 511 FLRC,
boundary values themselves allowed, as intended). RSSI readout has no
length-dependent path (FLRC rssi_avg from get_pkt_status, radio_bench.c:430).

Conclusion: the LEN=255-exactly CRC failure and the +35 dB RSSI step at
LEN>=255 (BUG 3) are NOT explainable by a host-MCU firmware branch — they are
chip-side (LR2021 silicon RSSI-averaging window / FLRC demod behavior) or
RF-side. Match123 removes the known config-side CRC killer; the remaining
boundary anomaly still needs the on-hardware LEN bisect 254/255/256/300
(FIX-T6) with the new fw.
