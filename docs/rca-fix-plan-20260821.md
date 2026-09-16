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

---

## Resolution status (2026-09-16) — what is fixed, what is VERIFIED, what is not

Written by FIX-T8 (t_b923f5a3). Read this before quoting a verdict from the
BUG sections above: **no FLRC/LoRa sweep data was produced for this plan**, so
the BUG 2 / BUG 3 hardware-verification columns are still PENDING.

### Data status: the FIX-T6 / FIX-T7 measurements DO NOT EXIST

| Card | Deliverable | Reality |
|------|-------------|---------|
| FIX-T5 (t_4e225809) | build + SWD flash both boards | `done` only because the fleet offload marked it so; the thread records a blocked pre-flight and **no flash happened** |
| FIX-T6 (t_c5d28b3f) | FLRC BR sweep + LEN boundary bisect CSVs | **no data.** Its single run is a blocked pre-flight (no TX probe on the fleet; the reconciled head did not exist) — verdict + runbook on branch `fix/t6-sweep-preflight` (9b8966d), `docs/FIX-T6-preflight-verdict-20260916.md` (not merged to `main`) |
| FIX-T7 (t_f04ee0b6) | LoRa LEN sweep + negative test CSVs | **zero runs recorded**; `fleet-writeback` set it `done` with no summary, no artifacts, no CSVs |
| FIX-R2 (t_52ede356) | build + flash the RECONCILED head, verify `ID?` SHA | still `todo` — no reconciled head exists on any remote yet |

Consequence: **there are no new sweep CSVs to commit with this document.**
The acceptance criteria at the end of this plan are unmet, not waived.

### Verdicts that ARE grounded in code + host tests

| Bug | Verdict | Evidence |
|-----|---------|----------|
| BUG 1 — LoRa LEN=511 | **RESOLVED (code), host-verified** | the cap is real and per-modulation: LoRa `pld_len_in_bytes` is a `uint8_t` (`third_party/Radio/lr20xx_driver/inc/lr20xx_radio_lora_types.h:247`), FLRC is `uint16_t` with documented range `[6:511]` (`.../lr20xx_radio_flrc_types.h:210`). Firmware TX gate is on `main` (`src/bench.c:786-790`); the RX parity gate + shared predicate is `fix/t2-rx-start-len-gate` (69dfd17); host-side START-reply fail-fast + LoRa cap + FLRC LEN section is `fix/t1-sweep-start-validation` (2e4a2c6). Hardware confirmation still pending (FIX-T7). |
| BUG 2 — FLRC CRC (Match123 + FIFO hygiene) | **IMPLEMENTED, hardware-UNVERIFIED** | Match123 + golden-byte host tests: `fix/t3-flrc-match123` (a1fcd27). RX FIFO clear per re-arm + TX FIFO clear: `fix/t4-fifo-clear` (07dbb8d). Both are branch-local — neither is an ancestor of `main`, so `main` still carries `RX_MATCH_SYNCWORD_1`. The "100 % chip CRC failure" claim has NOT been re-measured on hardware. |
| BUG 3 — LEN=255 exact boundary fail + +35 dB RSSI step | **OPEN / UNMEASURED** | the only evidence is the 2026-08-21 spot-test data (`flrc-retest-20260821.md`). The FIX-T6 bisect (LEN 253-257 @BR1300 PA10) never ran. If the +35 dB step survives the Match123 fix it is a separate firmware finding, not a Match123 artefact. |

### Line-reference corrections for the BUG sections above

- "bench.c:688 correctly refuses LEN>255 LoRa" → the per-modulation cap and
  its ERR string are at `src/bench.c:786-790` (TX `START`), and the same
  predicate gates the RX `START` on `fix/t2-rx-start-len-gate`.
- "radio_bench.c:432/459 sets snr_qdb=0" → the FLRC SNR clamp is in
  `src/radio_bench.c` on both the IRQ path and the poll path, each commented
  "FLRC has no SNR estimate". The 255-is-silicon claim now has a citation:
  `uint8_t pld_len_in_bytes` in the LoRa packet-params struct; FLRC's 511 is
  legal for the same reason (`uint16_t`, range `[6:511]`).
- Semantics of the fields analysis leans on (`pcrc16`, `snr_db=0.0` for FLRC,
  the two `drops=` counters, per-modulation LEN limits) are documented in
  `firmware/e80-stm32-bench/README.md` ("Bench Protocol Limits & Radio Notes")
  and `firmware/e80-stm32-bench/docs/RANGE-TEST-GUIDE.md` (§10).
