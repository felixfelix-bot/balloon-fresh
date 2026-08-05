# Payload Weight Estimates

**Date:** 2026-07-30
**Source:** Frozen V1 BOM (commit `7302dba`), board dimensions from `DUAL-VARIANT-DESIGN.md`
**Status:** ESTIMATES — actual weights require Felix's scale measurement once boards arrive

---

## Targets

| Configuration | Weight Target | Rationale |
|---------------|--------------|-----------|
| **Mesh V1** (ESP32-C3 + RP2040 + LR2021 + GPS + baro + solar) | **< 14g** | Pico balloon mesh relay — matches ~14g design goal from `balloon-options-analysis.md` |
| **Minimal Tracker** (ESP32-C3 + LR2021 + GPS + baro, no coprocessor) | **< 9g** | Ultra-light single-channel tracker |

---

## 1. Bare PCB Weight

FR4 density: 1.85 g/cm³. Finished board adds ~15% for copper, soldermask, silkscreen.

| Variant | Dimensions | Thickness | Volume | FR4 Weight | Finished Est. |
|---------|-----------|-----------|--------|-----------|---------------|
| **V1 (Non-PA)** | 50 × 40 mm | 0.6 mm | 1.20 cm³ | **2.22 g** | **~2.5 g** |
| **V2 (F33 PA)** | 75 × 55 mm | 0.8 mm | 3.30 cm³ | **6.11 g** | **~7.0 g** |

---

## 2. JLCPCB-Populated SMD Components (non-DNP)

Only 8 components are auto-placed by JLCPCB. Weights estimated from package dimensions.

| Ref | Part | Package | Qty | Unit Weight | Subtotal |
|-----|------|---------|-----|-------------|----------|
| U5 | TPS7A02 LDO | SOT-23-5 | 1 | 40 mg | 40 mg |
| D1 | BAT54 Schottky | SOD-123 | 1 | 15 mg | 15 mg |
| C1–C3 | 100nF cap | 0402 | 3 | 2.5 mg | 7.5 mg |
| C4–C5 | 10µF cap | 0805 | 2 | 15 mg | 30 mg |
| C6 | 100µF cap | 1206 | 1 | 30 mg | 30 mg |
| C7 | 10µF cap | 0805 | 1 | 15 mg | 15 mg |
| | | | **9 total** | | **137.5 mg** |

**V1 SMD total: ~0.14 g** (negligible)

**V2 SMD total: ~0.25 g** (additional F33 PA decoupling: extra 100µF + 10µF + 100nF + possible inductor)

### Solder Paste

JLCPCB applies solder paste to all pads. Estimated at ~50 mg total for V1 pad coverage.

---

## 3. DNP Module Weights (Hand-Soldered by Felix)

These modules are not placed by JLCPCB (marked DNP in BOM). Felix hand-solders them for flight.

| Module | Dimensions | Weight Est. (range) | Basis |
|--------|-----------|---------------------|-------|
| **ESP32-C3-Mini-1** (U1) | 22.52 × 18 mm | **2.5 g** (2–3 g) | Dev module: ESP32-C3 chip + USB-C connector + antenna PCB |
| **RP2040-Zero** (U2) | ~22 × 18 mm | **1.2 g** (1–1.5 g) | RP2040 + W25Q16 flash + USB-C connector |
| **LR2021 bare** (V1 radio) | 19.81 × 14.98 mm | **1.2 g** (1–2 g) | Castellated radio module (not in BOM excerpt — added per schematic) |
| **LR2021F33** (V2 radio) | 39 × 21 mm | **4.0 g** (3–5 g) | PA + TCXO + shielding can, significantly larger |
| **MAX-M10S GPS** (U3) | 12.2 × 16 mm | **0.4 g** bare / **1.0 g** breakout | u-blox module, ceramic patch |
| **MS5611 baro** (U4) | 5.0 × 3.0 mm | **0.03 g** bare / **0.3 g** breakout | MEMS pressure sensor |
| **1F 5.5V supercap** (SC) | Ø8 mm × 7 mm | **1.8 g** (1.5–2 g) | Gold capacitor for power buffering |

> **Note:** The provided V1 BOM excerpt does not include the LR2021 radio module (despite it being in the schematic). Weight is estimated from datasheet dimensions and included in all configurations below.

### Antennas

| Config | Antenna | Weight |
|--------|---------|--------|
| V1 | Wire dipole pads (THT D2.0mm) → ~82mm 26AWG wire for 868 MHz | **~0.2 g** |
| V2 | 2× SMA edge-mount connectors + pigtails | **~3.0 g** (1.5g each) |

### Pin Headers (Prototyping Only)

| Footprint | Used By | Male (mg) | Female (mg) |
|-----------|---------|-----------|-------------|
| 1×14 P2.54mm | RP2040-Zero | 700 | 900 |
| 1×04 P2.54mm | MAX-M10S | 200 | 300 |
| 1×04 P2.54mm | MS5611 | 200 | 300 |
| 1×02 P2.54mm | Solar input (J3) | 100 | 150 |
| Custom header | ESP32-C3 | ~400 | ~500 |

**Flight boards: direct-solder all modules (0g headers).** This saves ~1.6–2.4g vs socketed prototyping boards. All weight estimates below assume **direct solder**.

---

## 4. Solar Array Estimate

Spec: 52 × 19 mm cells, ~0.5V 400mA each, ~2g each.

| Cell Type | Unit Weight | 2 Cells | 4 Cells | Notes |
|-----------|------------|---------|---------|-------|
| Standard (given spec) | ~2.0 g | 4.0 g | 8.0 g | Heavy — drives total over target |
| Thin-film amorphous Si (realistic for pico balloon) | ~0.4 g | 0.8 g | 1.6 g | Typical for solar pico balloons |

> **Assumption:** For a 5.5V supercap, need ≥6V from solar. At 0.5V/cell that's 12+ cells in series (impractical). A boost converter (e.g., TPS61099) would allow 2–4 cells. We estimate **4 cells** as the baseline solar array.

---

## 5. Total Payload Weight — Configurations

> **UPDATE 2026-08-05:** Original V1 board (dual-MCU: C3+RP2040) is OBSOLETE.
> Replaced by V1-FAST (16 components, no ADC) and V2-ADC (18 components, supercap
> voltage divider on GPIO0). Both 50×40mm, single-MCU (ESP32-C3 only), no RP2040,
> no baro. All weights below updated to reflect single-MCU architecture.

### A. Minimal Tracker (V1-FAST Board, no solar/supercap, battery)

GPS-tracking-only pico balloon. Battery-powered for short flights.

| Item | Weight |
|------|--------|
| V1-FAST PCB (50×40mm finished) | 2.5 g |
| SMD parts + solder paste | 0.19 g |
| ESP32-C3-Mini-1 (U1) | 2.5 g |
| LR2021 bare radio module | 1.2 g |
| MAX-M10S GPS, bare (U3) | 0.4 g |
| Antenna wire (868 MHz) | 0.2 g |
| 40mAh LiPo battery (backup) | 1.0 g |
| **Total** | **~8.0 g** |
| **Target: < 9g** | **✅ PASS — 1.0g margin** |

> No RP2040, no baro. Lightest practical configuration.

### B. Solar Tracker (V2-ADC Board, solar + supercap, no battery)

Solar-powered tracker with supercap voltage monitoring via ADC (GPIO0).

| Item | Weight |
|------|--------|
| V2-ADC PCB (50×40mm finished) | 2.5 g |
| SMD parts + solder paste (incl. R_DIV1/R_DIV2 0402) | 0.20 g |
| ESP32-C3-Mini-1 (U1) | 2.5 g |
| LR2021 bare radio module | 1.2 g |
| MAX-M10S GPS, bare (U3) | 0.4 g |
| 1F 5.5V supercap (SC) | 1.8 g |
| Antenna wire (868 MHz) | 0.2 g |
| Solar array (4 thin-film cells) | 1.6 g |
| **Total (thin-film cells)** | **~10.4 g** |
| **Total (standard 2g cells)** | **~16.4 g** |
| **Target: < 14g** | **✅ PASS** with thin-film (3.6g margin) |

> V2-ADC adds 2× 100kΩ 0402 resistors (~5mg) for supercap voltage divider — negligible weight.

### C. Solar Tracker (V1-FAST Board, solar + supercap)

Same as B but V1-FAST board (no ADC — no supercap voltage monitoring).

| Item | Weight |
|------|--------|
| V1-FAST PCB (finished) | 2.5 g |
| SMD parts + solder paste | 0.19 g |
| ESP32-C3-Mini-1 (U1) | 2.5 g |
| LR2021 bare radio module | 1.2 g |
| MAX-M10S GPS, bare (U3) | 0.4 g |
| 1F 5.5V supercap (SC) | 1.8 g |
| Antenna wire (868 MHz) | 0.2 g |
| Solar array (4 thin-film cells) | 1.6 g |
| **Total (thin-film cells)** | **~10.4 g** |
| **Target: < 14g** | **✅ PASS — 3.6g margin** |

> Config C (mesh V1, dual-MCU with RP2040) is OBSOLETE — single-MCU only.
> Without RP2040, no mesh relay capability. But ~1.2g lighter than old estimate.

### D. Heavy-Lift Reference (V2 F33 PA) — Ground Station Only

For reference. F33 PA board is not a pico balloon target.

| Item | Weight |
|------|--------|
| V2 PCB (75×55mm finished) | 7.0 g |
| SMD parts (F33 support) | 0.25 g |
| ESP32-C3-Mini-1 | 2.5 g |
| LR2021F33 2W PA module | 4.0 g |
| MAX-M10S GPS, bare | 0.4 g |
| 1F 5.5V supercap | 1.8 g |
| 2× SMA connectors + pigtails | 3.0 g |
| **Total (no solar)** | **~19.0 g** |
| **With solar (4 thin-film cells)** | **~20.6 g** |

> No RP2040 in single-MCU architecture. ~1.2g lighter than old V2 estimate.

---

## 6. Summary Comparison

| Config | Board | Solar | Est. Weight | Target | Verdict |
|--------|-------|-------|------------|--------|---------|
| A: Minimal tracker (battery) | V1-FAST | None (LiPo) | **~8.0 g** | < 9g | ✅ PASS |
| B: Solar tracker (V2-ADC) | V2-ADC | 4 thin-film | **~10.4 g** | < 14g | ✅ PASS (3.6g margin) |
| C: Solar tracker (V1-FAST) | V1-FAST | 4 thin-film | **~10.4 g** | < 14g | ✅ PASS (3.6g margin) |
| D: V2 F33 PA (ground station) | V2/F33 | 4 thin-film | **~20.6 g** | N/A | Reference |

---

## Weight Breakdown Pie (Mesh V1, Config C)

```
ESP32-C3-Mini-1   ████████████████████  2.5g (21.6%)
V1 PCB             ██████████████████    2.5g (21.6%)
LR2021 radio       ██████████            1.2g (10.3%)
RP2040-Zero        ██████████            1.2g (10.3%)
Supercap 1F        ██████████████        1.8g (15.5%)
Solar (4 cells)    █████████████         1.6g (13.8%)
GPS + baro + ant   ████                  0.63g (5.4%)
SMD + solder       █                     0.19g (1.6%)
```

**Biggest weight items:** Dev modules (ESP32-C3 + RP2040 = 3.7g) and supercap (1.8g) dominate. A custom-PCB ESP32-C3 (bare chip + crystal + antenna) would save ~1.5g vs the dev module.

---

## Key Assumptions

1. **Module weights are estimates** from datasheet dimensions and typical densities. Actual weights vary by manufacturer batch. **Felix must verify with a precision scale (0.01g resolution).**
2. **LR2021 radio module** is not in the provided BOM excerpt but is in the schematic. Weight estimated from 19.81 × 14.98mm dimensions with shielding can.
3. **Solar cell weight** is the largest uncertainty. The "~2g per cell" spec is heavy for pico balloon use. Thin-film alternatives at ~0.4g/cell are strongly recommended.
4. **Direct solder** assumed for all flight configurations (no pin headers). Prototyping boards with sockets add ~1.5–2.4g.
5. **MS5611 and MAX-M10S** assumed bare-die direct-soldered for flight. Breakout boards add ~0.6g and ~0.6g respectively.
6. **Solder paste** weight (~50mg) included but negligible.
7. **FR4 density** of 1.85 g/cm³ does not include copper weight. Finished boards with full copper pour weigh ~15% more.
8. **No enclosure/strain relief** weight included. Add ~0.5–1g for heat-shrink or conformal coating.
9. **Wire/strain relief** for solar and battery connections not separately counted (~0.2–0.5g).

---

## Recommendations

1. **Use thin-film solar cells** (~0.4g each, not 2g). This is the single biggest weight lever.
2. **Direct-solder all modules** for flight (saves ~2g vs socketed headers).
3. **Consider bare ESP32-C3** on a future PCB revision instead of the Mini dev module — saves ~1.5g and eliminates USB-C connector weight.
4. **Verify actual weights** with Felix's scale as soon as V1 boards arrive from JLCPCB.
5. **For minimal tracker flights**, use battery-only (Config A) to stay under 9g.
6. **For mesh relay flights**, thin-film solar is mandatory to stay under 14g.
