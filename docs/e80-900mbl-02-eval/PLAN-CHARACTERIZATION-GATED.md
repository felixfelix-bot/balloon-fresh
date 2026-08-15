# E80/LR2021 Characterization Plan — GATED (2026-08-15)

Supersedes the phase list in PLAN-E80-LR2021-EVAL-2026-08-15.md for execution.
Route (Felix decision): boards AS-IS via USB — our bench firmware on each kit's
STM32F103, flashed over USB. No host MCUs, no jumpers.

Gates below are HARD: a phase does not start until the previous phase's exit
gates are GREEN and recorded in this file (append ✅ + date + evidence hash).

## D1 — OPEN DECISION (blocks outdoor RF only)
SKU is E80-**900**M (module band per datasheet ≈902–928 MHz). Felix's location
regulates 865–867 MHz (India UWB-free band) — NOT covered by this SKU.
Bench tests indoors at low power: acceptable engineering practice.
OUTDOOR range tests at 915 MHz: needs Felix's call on legality/exposure.
Default: all range testing outdoors DEFERRED until D1 decided.

## P0 — Safety & Inventory (no RF, no flash)
- G0.1 Antenna confirmation: photo of both boards with whips on SUB1G SMA.
  BLOCKS all TX. (Diagnostic SPI phases exempt.)
- G0.2 Stock flash dump BOTH boards (`stm32flash -r`), CRC-verified vs demo
  E80.hex; dumps committed to repo (stock-restore guarantee). BLOCKS P2.
- G0.3 Stable USB mapping: udev rules by CH340 serial → /dev/e80-a, /dev/e80-b.
- G0.4 Board inventory logged: serial numbers, kit version, antenna type/model.
- Exit: all four GREEN, recorded here.

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

## P3 — Bench RF @1 m, low power (indoor, PA min)
- G3.1 First link: FLRC-650, 1000×255B, PER logged. RSSI sanity @1 m ≈ −25…−45 dBm.
- G3.2 Power-step monotonicity: PA sweep min→+10 dBm, RSSI must rise monotonically
  (catches PA-table indexing bugs — HARD gate before any high power).
- G3.3 Modulation matrix @1 m: FLRC 650/1300/2600 (LF band; if 2600 unavailable
  on LF per chip docs, record + move on), LoRa SF5–SF12 BW125–500; payload
  32/64/127/255; PER + kbps + RSSI/SNR per cell.
- G3.4 Cross-check: FLRC-650/1300 throughput within ±20% of our own-boards
  baseline (1377 kbps FLRC-650 @RP2040). Divergence → investigate before trust.
- Exit: G3.2 monotonic + matrix CSV committed + cross-check within band.

## P4 — Max-throughput desk characterization
- Sweep TX power × modulation × payload for max clean throughput (PER ≤1%).
- Output: throughput-vs-power curve per modulation (log-scale plots).
- Exit: curves + CSV committed, best-config table written.

## P5 — Range characterization (BLOCKED on D1 + G0.1)
- Distances: 1 m → 10 m indoor → outdoor LOS 50/100/250/500 m, 1 km if link holds.
- Per point: FLRC-650, FLRC-1300, LoRa SF7/SF10/SF12; power +22/+10/0 dBm.
- ≥1000 pkts per cell (or documented PER>10% cutoff). Auto-logged CSV w/ GPS/phone
  distance. Felix walks; stats over USB.
- Exit: complete matrix or documented cutoff per cell.

## P6 — Analysis & link budget
- Path-loss fit, FLRC-range vs LoRa-range tradeoff curve, extrapolation to
  balloon altitudes (10–40 km LOS).
- Deliverable: report + plots (log Y), feeds flight link-budget model.

## Gate ledger
(append ✅/❌ + date + evidence as phases complete)
- P0: pending
- P1: running (deleg_35fd6c25, branch feat/e80-stm32-bench)
