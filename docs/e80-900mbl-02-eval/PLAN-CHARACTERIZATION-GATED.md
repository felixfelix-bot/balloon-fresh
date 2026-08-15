# E80/LR2021 Characterization Plan — GATED (2026-08-15)

Supersedes the phase list in PLAN-E80-LR2021-EVAL-2026-08-15.md for execution.
Route (Felix decision): boards AS-IS via USB — our bench firmware on each kit's
STM32F103, flashed over USB. No host MCUs, no jumpers.

Gates below are HARD: a phase does not start until the previous phase's exit
gates are GREEN and recorded in this file (append ✅ + date + evidence hash).

## D1 — OPEN DECISION (blocks ALL RF incl. indoor bench — consultant grill #1)
SKU is E80-**900**M (module band per datasheet ≈902–928 MHz). Felix's location
regulates 865–867 MHz (India) — NOT covered by this SKU; no E80 SKU covers it.
OPTIONS for Felix: (a) accept low-power indoor 915 bench TX as engineering
practice + decide outdoor separately, (b) run all RF clamped 865–867 and accept
severe filter/PA mismatch degradation (SKU front-end tuned 902–928), (c) no RF
on this SKU, characterization SPI-only until different-band hardware.
HARD RULE until D1 decided: firmware ships TX-inhibited (radio sleep) and
frequency clamped to the approved band. P4 power sweep capped at D1-approved level.

## P0 — Safety & Inventory (no RF, no flash)
- G0.1 Antenna confirmation: photo of both boards with whips on SUB1G SMA.
  BLOCKS all TX. (Diagnostic SPI phases exempt.)
- G0.2 Stock flash dump BOTH boards (`stm32flash -r`), CRC-verified vs demo
  E80.hex; dumps committed to repo (stock-restore guarantee). BLOCKS P2.
- G0.3 Stable USB mapping: udev rules by CH340 serial → /dev/e80-a, /dev/e80-b.
- G0.4 Board inventory logged: serial numbers, kit version, antenna type/model.
- G0.5 (grill #6/#12, blocks P3): firmware TX-inhibit DEFAULT verified in code
  review (compile-time RF_ENABLE=off, radio held SLEEP, TX only after explicit
  armed command) + frequency clamp to D1-approved band + band/freq logged at
  identity time. Also: USB autosuspend disabled on host, powered hub, one
  verified stock dump stored OFF-host (grill #10).
- Exit: all five GREEN, recorded here.

## P1 — Bench firmware build (branch feat/e80-stm32-bench, RUNNING)
- G1.1 Test-first on testable logic: packet format/CRC/seq-fragility, stats
  accumulation, command parser → host-side unit tests (Python, pytest, RED first).
  Firmware radio paths: build-check exception (embedded target, declared).
- G1.2 Compile clean (arm-none-eabi-gcc); .elf/.hex/.bin artifacts; size report
  fits STM32F103C8 (≤64K flash, ≤20K RAM) with ≥8K margin.
- G1.3 CROSS-FAMILY COLD REVIEW (Kimi vs GLM worker) of full branch diff
  BEFORE any flash. Verdict APPROVED required (max 2 cycles → manager escalation).
  Review focus: register-write sequences, PA table indexing (wrong index =
  PA damage), TCXO voltage, reset states, USART robustness.
- G1.4 Docs + code same commits; branch pushed (Gate 5).
- Exit: build green + review APPROVED + pushed.

## P2 — Non-RF validation (flash day, SPI only)
- G2.1 Flash board A with bench fw. `ID?` responds: chip identity resolved
  (LR2021 vs SX1280 derivative — settles H1/H2 permanently).
- G2.2 SPI sanity: version register stable across 100 reads; TCXO starts
  (BUSY timing as expected); no error flags.
- G2.3 ROUND-TRIP: reflash stock dump → verify demo enumerates → reflash bench.
  Proves no-brick recovery path. Both boards.
- G2.4 Board B: G2.1–G2.3 repeated.
- Exit: both boards round-trip proven, identity logged.

## P3 — Bench RF @1 m, low power (indoor, PA min — BLOCKED on D1 + G0.5)
- G3.1 First link: FLRC-650 (or highest BR available on LF after G2.1 identity),
  1000×255B, PER logged. RSSI sanity @1 m ≈ −25…−45 dBm (coarse only — RSSI
  uncalibrated, grill #8; link budget derives from PER, not RSSI).
- G3.2 Power-step monotonicity: PA sweep min→+10 dBm THROUGH 30 dB attenuator
  (or ≥10 m separation) so RX stays linear — flattening/compression at 1 m
  would fake monotonicity (grill #5). RSSI must rise monotonically. HARD gate
  before any high power.
- G3.3 Modulation matrix @1 m: fixed geometry, λ/2 position dither + average
  (multipath, grill #9), noise floor logged per session. FLRC 650/1300/2600
  per chip availability ON THE IDENTIFIED SILICON (settled at G2.1 — do not
  assume SX128x 2.4G lineage, grill #3); LoRa SF5–SF12 BW125–500; payload
  32/64/127/255. PER + kbps + RSSI per cell (SNR LoRa-only — FLRC pkt-status
  has no SNR, worker-verified). Sample size per regime (grill #4): n=10,000
  for PER≤1% claims (0 err → PER<0.03% @95%), n=1,000 for PER≤10% regime,
  report raw counts + Wilson 95% CI in every table.
- G3.4 Cross-check vs 1377 kbps RP2040 baseline: ONLY valid if that baseline
  ran FLRC on the same band/chip family — verify from repo history BEFORE
  using as reference; otherwise mark not-comparable and rely on G3.5.
- G3.5 (grill #2) SENSITIVITY SWEEP: step attenuator 0–60 dB (need ~2 SMA
  barrels + 10/20/30 dB pads or a step attenuator — cheap, order if absent):
  PER vs input level per modulation → dBm@PER1% table. THIS feeds P6 link
  budget — walked range is corroboration only.
- Exit: G3.2 monotonic + matrix CSV w/ CIs + sensitivity table committed.

## P4 — Max-throughput desk characterization
- Sweep TX power × modulation × payload for max clean throughput (PER ≤1%).
- Output: throughput-vs-power curve per modulation (log-scale plots).
- Exit: curves + CSV committed, best-config table written.

## P5 — Range characterization (BLOCKED on D1 + G0.1 + G5.1)
- G5.1 (grill #7) AUTOMATION GATE before any walking: single-command full-matrix
  run per stop (e80_bench_ctl auto mode), per-cell time caps (SF12 capped at
  300 pkts or 10 min — SF12/BW125/255B ≈ 9 s/pkt makes 1000-pkt cells = 2.5 h),
  early-stop at PER>50%, auto-CSV append w/ timestamp + distance + config.
- Distances: 1 m → 10 m indoor → outdoor LOS 50/100/250/500 m, 1 km if link holds.
- Per point: FLRC-650, FLRC-1300, LoRa SF7/SF10/SF12; power +22/+10/0 dBm
  (as D1 allows). ≥3 repeats per distance (grill #11), fade margin recorded.
- ≥1000 pkts per cell (or documented PER>10% cutoff). Auto-logged CSV.
- Exit: complete matrix or documented cutoff per cell.

## P6 — Analysis & link budget
- PRIMARY input: G3.5 sensitivity table (dBm@PER) + TX power → link budget.
  Walked range (P5) = corroboration + fade-margin estimate, not the budget base.
- Path-loss fit w/ variance across repeats, FLRC-range vs LoRa-range tradeoff,
  extrapolation to balloon altitudes (10–40 km LOS) with explicit fade margin.
- Deliverable: report + plots (log Y), feeds flight link-budget model.

## Gate ledger
(append ✅/❌ + date + evidence as phases complete)
- P0: pending (G0.5 added — grill)
- P1: running (deleg_35fd6c25, branch feat/e80-stm32-bench)
- Grill applied 2026-08-15: 12 findings (1 blocker D1-before-all-RF, 5 major →
  G0.5 TX-inhibit+band clamp, G3.5 sensitivity sweep, G3.2 attenuator, G3.4
  baseline-validity check, sample-size/CIs, SF12 time caps) — consultant deleg_a0c4f8cf.
