# PCB-U2 verification evidence — t_f48320db

Card: PCB-U2 replace RFM9xW land pattern with NiceRF LoRa2021 18-pin + net remap + RF re-route
Branch: `pr/u2-lora2021-landpattern` — commit e05a736 (base b485363 = `pr/pcb-s1b-gerbers`)
PR: https://github.com/felixfelix-bot/balloon-fresh/pull/17 (against `pr/pcb-s1b-gerbers`)
Final board: `tracker/hardware/output/v8h_krt_u2_lora2021.kicad_pcb`
Board sha256_12: **d2e7c3d1ae55**  (re-verified by worker-pcb, 2026-10-04)
Full sha256: d2e7c3d1ae5510006549f17a06bd65c91c548a1a67a41ad71ea67827e4508528

## 1. Footprint identity — U2 vs custom:LoRa2021_Castellated

`tracker/hardware/u2_lora2021_verify.py output/v8h_krt_u2_lora2021.kicad_pcb` → **ALL CHECKS PASSED** (exit 0)

- U2 = `LoRa2021_Castellated` (value LoRa2021_Gen4), rot 180°, at (38.000, 9.000)
- pad count = **18** ✓
- pad columns at x = [28.095, 47.905] → row span **19.810 mm** ✓
- every pad 2.0 × 0.7 mm; each column = 9 pads at **1.29 mm pitch** ✓
- pad → net map matches the plan-of-record table exactly:

  | pad | net | plan |
  |---|---|---|
  | 1 | +3V3 | +3V3 |
  | 2 | GND | GND |
  | 3 | SPI_MISO | SPI_MISO |
  | 4 | SPI_MOSI | SPI_MOSI |
  | 5 | SPI_SCK | SPI_SCK |
  | 6 | SPI_NSS | SPI_NSS |
  | 7 | LR_BUSY | LR_BUSY |
  | 8 | GND | GND |
  | 9 | RF_OUT | RF_OUT |
  | 10 | (no net) | (none) |
  | 11 | GND | GND |
  | 12 | GND | GND |
  | 13 | (no net) | (none) |
  | 14 | LR_RST | LR_RST |
  | 15 | LR_IRQ | LR_IRQ |
  | 16 | (no net) | (none) |
  | 17 | (no net) | (none) |
  | 18 | GND | GND |

- pads 10/13/16/17 deliberately unconnected ✓

## 2. No RFM9xW geometry survives

- no footprint whose lib id contains `RFM9`/`HOPERF`
- no pad named `NSS` / `RST` / `BUSY` / `DIO0` anywhere
- no net named `LR_DIO0`
→ signature list empty ("clean"). 20 footprints on the board; `LR_IRQ` net present.

## 3. RF trace

- 8 `RF_OUT` segments, total 23.081 mm, **all width 0.39 mm**, all on **F.Cu** ✓
- U2.9 `RF_OUT` ↔ ANT1.1 `RF_OUT`, pad separation 9.839 mm
- Microstrip Z0 (JLCPCB 4-layer, h=0.21 mm, Er=4.4, t=0.035 mm Cu):
  - w=0.20 mm → ~69.4 Ω  (the old width)
  - w=0.34 mm → ~52.7 Ω
  - **w=0.39 mm → ~48.7 Ω**  (the shipped width)

## 4. DRC row (frozen rules — no relaxed design rules)

- `.kicad_dru` used = `tracker/hardware/jlcpcb-s1-frozen.kicad_dru` (byte-identical to the v8h sibling .dru)
- `.kicad_pro` = byte-identical to the v8f board's `.kicad_pro` (no "FAB FLOOR RELAXED" rewrite)
- Result: **shorts 0 / clearance 0 / unconnected 0**, violations = 5, all cosmetic
  (`silk_edge_clearance` ×3, `silk_over_copper` ×2)
- vias = **55, every one 0.60 / 0.30** (histogram: only `0.6/0.3: 55`)
- segments 399, copper 821.1 mm, footprints 20, **fab_ready = 1**

## 5. Placement

- gate25 on the placement input (`output/.placement/v8g_placement_input.kicad_pcb`):
  **fp=20, pad_overlaps=0, segments=0 → PASS**
- placement input sha256: 93cb770e7dfd861c836d1a071ad96a8d01010ddf9fb6d0759dd60093c8ca88cc
- final routed board sha256_12: d2e7c3d1ae55
- courtyard check on the final board: **0 overlapping footprint pairs** (U2's larger
  courtyard does not collide with U1/U3/antenna keepout — no option set required)
- The v8f freeze contract (sha 0358ad04414a) is **superseded** by this board.

## 6. JLCPCB package

`tracker/hardware/output/gerbers_v8h_jlcpcb.zip` — 145,267 bytes, flat, 16 files.
Copper layers non-empty (D-codes/draws/flashes):
- F_Cu 26/604/173 · In1_Cu 8/2833/81 · In2_Cu 8/2843/81 · B_Cu 7/54/81
- drill: PTH 81 holes / 6 tools; NPTH 0
- pos_v8h.csv = 20-part CPL
