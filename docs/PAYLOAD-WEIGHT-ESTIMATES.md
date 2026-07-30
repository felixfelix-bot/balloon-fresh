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

### A. Minimal Tracker (V1 Board, no RP2040, no solar/supercap)

GPS-tracking-only pico balloon. Battery-powered for short flights.

| Item | Weight |
|------|--------|
| V1 PCB (finished) | 2.5 g |
| SMD parts + solder paste | 0.19 g |
| ESP32-C3-Mini-1 (U1) | 2.5 g |
| LR2021 bare radio module | 1.2 g |
| MAX-M10S GPS, bare (U3) | 0.4 g |
| MS5611 baro, bare (U4) | 0.03 g |
| Antenna wire (868 MHz) | 0.2 g |
| 40mAh LiPo battery (backup) | 1.0 g |
| **Total** | **~8.0 g** |
| **Target: < 9g** | **✅ PASS — 1.0g margin** |

### B. Minimal Tracker (V1 Board, with solar + supercap)

Solar-powered for multi-day flights. No RP2040 coprocessor.

| Item | Weight |
|------|--------|
| V1 PCB (finished) | 2.5 g |
| SMD parts + solder paste | 0.19 g |
| ESP32-C3-Mini-1 (U1) | 2.5 g |
| LR2021 bare radio module | 1.2 g |
| MAX-M10S GPS, bare (U3) | 0.4 g |
| MS5611 baro, bare (U4) | 0.03 g |
| 1F 5.5V supercap (SC) | 1.8 g |
| Antenna wire (868 MHz) | 0.2 g |
| Solar array (4 thin-film cells) | 1.6 g |
| **Total (thin-film cells)** | **~10.4 g** |
| **Total (standard 2g cells)** | **~16.4 g** |
| **Target: < 9g** | **❌ FAIL** — over by 1.4g (thin-film) or 7.4g (standard) |

> **Finding:** The minimal tracker with solar exceeds the 9g target even with thin-film cells. Options: (1) drop to battery-only (Config A), (2) use 2 cells instead of 4 (~9.6g, still borderline), (3) use bare ESP32-C3 chip instead of dev module (saves ~1.5g).

### C. Mesh V1 (Full Hub Board, solar-powered)

Complete mesh relay node: ESP32-C3 + RP2040 + LR2021 + GPS + baro + supercap + solar.

| Item | Weight |
|------|--------|
| V1 PCB (finished) | 2.5 g |
| SMD parts + solder paste | 0.19 g |
| ESP32-C3-Mini-1 (U1) | 2.5 g |
| RP2040-Zero (U2) | 1.2 g |
| LR2021 bare radio module | 1.2 g |
| MAX-M10S GPS, bare (U3) | 0.4 g |
| MS5611 baro, bare (U4) | 0.03 g |
| 1F 5.5V supercap (SC) | 1.8 g |
| Antenna wire (868 MHz) | 0.2 g |
| Solar array (4 thin-film cells) | 1.6 g |
| **Total (thin-film cells)** | **~11.6 g** |
| **Total (standard 2g cells, 4 cells)** | **~17.6 g** |
| **Target: < 14g** | **✅ PASS** with thin-film (2.4g margin) |

> **Finding:** Mesh V1 passes the 14g target with thin-film solar cells but **fails with standard 2g cells**. Cell choice is the critical swing factor.

### D. Mesh V1 with Standard Solar Cells (2 cells minimum)

Reduced solar (2 cells instead of 4) with standard 2g cells.

| Item | Weight |
|------|--------|
| Board + all modules + supercap + antenna (as Config C) | 10.0 g |
| Solar array (2 standard cells) | 4.0 g |
| **Total** | **~14.0 g** |
| **Target: < 14g** | **⚠️ RIGHT AT LIMIT — 0g margin** |

### E. V2 (F33 PA) — Ground Station / Heavy-Lift

For reference. V2 is not a pico balloon target.

| Item | Weight |
|------|--------|
| V2 PCB (finished) | 7.0 g |
| SMD parts (F33 support) | 0.25 g |
| ESP32-C3-Mini-1 | 2.5 g |
| RP2040-Zero | 1.2 g |
| LR2021F33 2W PA module | 4.0 g |
| MAX-M10S GPS, bare | 0.4 g |
| MS5611 baro, bare | 0.03 g |
| 1F 5.5V supercap | 1.8 g |
| 2× SMA connectors + pigtails | 3.0 g |
| **Total (no solar)** | **~20.2 g** |
| **With solar (4 thin-film cells)** | **~21.8 g** |

---

## 6. Summary Comparison

| Config | Board | Solar | Est. Weight | Target | Verdict |
|--------|-------|-------|------------|--------|---------|
| A: Minimal tracker (battery) | V1 | None (LiPo) | **~8.0 g** | < 9g | ✅ PASS |
| B: Minimal tracker (solar) | V1 | 4 thin-film | **~10.4 g** | < 9g | ❌ FAIL |
| C: Mesh V1 (thin-film solar) | V1 | 4 thin-film | **~11.6 g** | < 14g | ✅ PASS |
| D: Mesh V1 (standard cells, 2) | V1 | 2 standard | **~14.0 g** | < 14g | ⚠️ AT LIMIT |
| E: V2 F33 PA (ground station) | V2 | 4 thin-film | **~21.8 g** | N/A | Reference |

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
