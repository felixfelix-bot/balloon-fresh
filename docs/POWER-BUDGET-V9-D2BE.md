# v9 flight-board power + mass budget (reconciled against ADR-006 and ADR-036)

Status: **reconciled engineering budget.** All figures either cite an in-repo
authority/datasheet, are derived by a shown formula, or are explicitly marked
`TODO(unverified)`. This document closes the missing rail sum in ADR-029 O5 and
records the operator's 2026-10-07 energy policy (ADR-036) in the power/mass
budget rather than leaving it as prose only.

## Authorities and scope

| Record | Role in this budget |
|---|---|
| `docs/adr/006-supercapacitor-power.md` (Status **Akzeptiert**) | Solar array, supercap bank, LDO, and original load are the **unchallengeable authority** for those items. |
| `docs/adr/036-energy-policy-burst-storage-daylight-only-tx.md` (operator decision, 2026-10-07) | Storage sized to **one burst**, **daylight-only TX**, mandatory night deep sleep, cold-start-at-dawn accepted. |
| `docs/adr/034-radio-band-split-433-tx-2g4-rx.md` / `docs/adr/035-tdm-radio-schedule.md` (2026-10-07) | v9 RF complement and TDM schedule used as the **current flight-board architecture**. |
| `docs/adr/029-dual-band-flight-board.md` O5 | 5 V rail remains open; this document restates it with the bank-at-5.4 V observation. |

Scope: the budget is written for the **v9 board** (ESP32-S3 + F33-2G4 433 TX +
bare `LoRa2021` 2.4 GHz RX + SX1280 ranging + MAX-M10S + MS5607) while grounding
the storage and solar figures in ADR-006. Where the v9 architecture conflicts
with ADR-006's original single-radio/3.3 V record, the conflict is stated in
§5 rather than silently resolved.

## 1. Solar array and storage (ADR-006 ground truth)

### Solar array

```
4 wings × 3 cells in series = 12 cells total
Wing voltage: 3 × 0.5 V = 1.5 V per wing
All 4 wings in series: 4 × 1.5 V = 6.0 V @ 400 mA
Peak power: 6.0 V × 0.400 A = 2.4 W (direct sun)
Cell area per wing: 3 × (52 mm × 19 mm) = 2.964 cm²; total array ≈ 120 cm²
```

Provenance: `[datasheet docs/adr/006-supercapacitor-power.md §Power-Architektur]`.

### Supercapacitor bank

```
2 × AVX SCC 3.3 F 2.7 V in series → 1.65 F @ 5.4 V
Balancing: 2 × 10 kΩ parallel resistors
Bank energy (ideal, fully charged): E = ½·C·V²
  = ½ × 1.65 F × (5.4 V)² = 24.1 J
Usable energy to LDO dropout (assume Vmin = 3.5 V):
  Eusable = ½ × 1.65 × (5.4² − 3.5²) = 13.9 J ≈ 14 J
```

Provenance: `[datasheet docs/adr/006-supercapacitor-power.md §Komponenten]`.

### 3.3 V rail

`TPS7A02 3.3 V LDO, IQ = 25 nA` — the quiescent is negligible for every budget
line below. Provenance: `[datasheet docs/adr/006-supercapacitor-power.md §LDO Regler]`.

## 2. Power budget

All currents are at the named load rail. "Average" is the time-average under the
representative daylight TDM duty-cycle assumptions stated in the table. These duty
cycles are **design targets**, not measured flight values; they must be replaced
by logged values before flight.

### Load table

| Load | Rail | Peak / active | Sleep / idle / RX | Duty | Average | Provenance |
|---|---|---:|---:|---:|---:|---|
| F33 433 MHz TX (2 W) | 5 V tap | 1.20 A | — | 1 % | 12.0 mA | `[datasheet docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf]` via ADR-029 D2 / ADR-034 D2 |
| F33 idle / RX (sub-GHz port armed) | 5 V tap | 20 mA | — | 99 % | 19.8 mA | `[datasheet docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf]` via ADR-029 D2 |
| bare `LoRa2021` 2.4 GHz RX | 3.3 V | TODO | — | 5 % | TODO | `TODO(unverified)` |
| SX1280 ranging TX (+13 dBm) | 3.3 V | 70 mA | — | 0.2 % | 0.14 mA | `[computed: 0.002 × 70 mA; peak from original worker budget]` |
| SX1280 ranging RX | 3.3 V | 15 mA | — | 2 % | 0.30 mA | `[computed: 0.02 × 15 mA; peak from original worker budget]` |
| ESP32-S3 CPU + digital | 3.3 V | 240 mA | 10 µA | 10 % | 24.0 mA | `TODO(unverified)` (peak budget from original worker doc) |
| MAX-M10S GNSS tracking | 3.3 V | 25 mA | — | continuous | 25.0 mA | `TODO(unverified)` budget |
| MS5607 barometer conversion | 3.3 V | 1.5 mA | 10 µA | 10 % | 0.16 mA | `[computed: 0.1 × 1.5 mA + 0.9 × 0.01 mA]`; values `TODO(unverified)` |
| TPS7A02 LDO quiescent | 5.4 V | 25 nA | — | continuous | 25 nA | `[datasheet docs/adr/006-supercapacitor-power.md §LDO Regler]` |

**5 V rail average** (F33): `0.01 × 1.20 A + 0.99 × 0.020 A = 0.0318 A = 31.8 mA`
→ `31.8 mA × 5.0 V = 0.159 W`.

**3.3 V rail average** (known loads, excluding bare LoRa2021 RX):
`0.14 mA + 0.30 mA + 24.0 mA + 25.0 mA + 0.16 mA = 49.6 mA`
→ `49.6 mA × 3.3 V = 0.164 W`.

With a 20 % converter / distribution allowance the representative **input power**
is `(0.159 W + 0.164 W) × 1.20 = 0.388 W`.

### Array coverage check

The array peak is 2.4 W in direct sun. Because the four wings point in different
space angles (3D solar, ADR-006), at least 1–2 wings are typically illuminated:

```
1 wing peak = 1.5 V × 0.4 A = 0.6 W
2 wings peak = 3.0 V × 0.4 A = 1.2 W
4 wings peak = 6.0 V × 0.4 A = 2.4 W
```

The representative average load of **0.388 W** is therefore well below the
single-wing peak and below the conservative two-wing estimate of **1.2 W**. The
array can cover the average load and recharge the burst buffer during daylight.
This average is only valid if the TDM duty-cycle assumptions above are enforced
by firmware; any increase in TX duty cycle or continuous RX/TX must be re-budgeted.

### Night sleep and the LOG-survival question

ADR-036 mandates deep sleep at night. The deciding quantity is the payload's
actual deep-sleep current, which is **not yet measured**:

```
At 1 mW housekeeping for 10 h: 0.001 W × 36 000 s = 36 J
  → needs multi-farad storage, contradicts the burst-sized mass goal.
At 100 µW housekeeping for 10 h: 0.0001 W × 36 000 s = 3.6 J
  → ~0.3 F at 3.3 V (E = ½·C·V² → C ≈ 0.66 F, rounded to ~0.3 F usable with droop).
At 10 µA-level sleep @ 3.3 V = 33 µW for 10 h: 0.000033 W × 36 000 s = 1.19 J
  → decided by firmware, not by the capacitor.
```

A night gap in the **flight log** is worse than a night gap in the downlink
(ADR-036). The log survives only if deep-sleep current is in the µA range; this
is recorded as an **open measured item**, not resolved here.

## 3. TX burst buffer sizing (the modulation fork)

Buffer size depends on modulation. The F33 433 MHz PA peak is taken as **6 W DC**
(5.0 V × 1.2 A) for the calculation; the actual burst energy must be measured on
the bench because TX power, packet length, and voltage droop margin all change
the result.

### Case A — FLRC ~2.6 Mbps

```
100 byte payload = 800 bit
Burst duration: t = 800 / 2.6×10⁶ = 0.308 ms
Burst energy: E = 6 W × 0.308 ms = 1.85 mJ ≈ 2 mJ
Required capacitance for 5.4 V → 5.0 V droop:
  C = 2E / (Vmax² − Vmin²)
    = 2 × 1.85 mJ / (5.4² − 5.0²)
    = 3.70 mJ / 4.16 V²
    = 0.89 mF ≈ 1 mF
Mass estimate: ~0.2 g (millifarad-class ceramic/small electrolytic) — `TODO(unverified)`.
```

### Case B — LoRa SF12 / BW125

```
Symbol time: Ts = 2^12 / 125 kHz = 32.8 ms
Minimal packet (preamble + header + payload) ≈ 20 symbols
Burst duration: t ≈ 20 × 32.8 ms = 0.656 s ≈ 0.65 s
Burst energy: E = 6 W × 0.656 s = 3.94 J ≈ 4 J
Required capacitance for 5.4 V → 3.5 V droop (full bank usable range):
  C = 2E / (5.4² − 3.5²)
    = 7.88 J / 16.91 V²
    = 0.47 F
```

So the LoRa case needs a buffer in the **tenths-of-a-farad** range and can be
served by the ADR-006 1.65 F bank with large margin; the FLRC case needs only a
**~1 mF** buffer (~0.2 g, `TODO(unverified)`) but only if FLRC is available on the
**433 MHz port** of the F33.

`TODO(unverified)`: whether FLRC at ~2.6 Mbps is available on the **sub-GHz port**
of the F33, or only at 2.4 GHz. This measurement decides which buffer mass applies.

## 4. Mass budget

Board dimensions from ADR-029: **55.15 mm × 45.15 mm**. Thickness from the
existing KiCad file `tracker/hardware/hub_board_v1_clean.kicad_pcb` line 1:
**0.6 mm**.

| Item | Mass (g) | Provenance |
|---|---:|---|
| FR4 PCB, 55.15 × 45.15 × 0.6 mm | 2.76 | `[computed: 5.515 cm × 4.515 cm × 0.060 cm × 1.85 g/cm³]`; thickness from `tracker/hardware/hub_board_v1_clean.kicad_pcb` |
| 2 × AVX SCC 3.3 F 2.7 V supercap | 3.00 | `[datasheet docs/adr/006-supercapacitor-power.md §Supercapacitors]` |
| TPS7A02 3.3 V LDO | — | `TODO(unverified)` |
| BAT54 Schottky diode | — | `TODO(unverified)` |
| 2 × 10 kΩ balancing resistors + 2 × 1 MΩ divider resistors | — | `TODO(unverified)` |
| 12 × solar cells (52 × 19 mm) | — | `TODO(unverified)` |
| ESP32-S3-WROOM-1U-N8R8 | — | `TODO(unverified)` |
| `LoRa2021F33-2G4` module (castellated) | — | `TODO(unverified)` |
| bare `LoRa2021` castellated module (2.4 GHz RX) | — | `TODO(unverified)` |
| `SX1280IMLTRT` + matching/passives | — | `TODO(unverified)` |
| MAX-M10S GNSS receiver | — | `TODO(unverified)` |
| MS5607-02BA03 barometer | — | `TODO(unverified)` |
| U.FL pigtails + antenna harness | — | `TODO(unverified)` |
| Misc passives, connectors, solder | — | `TODO(unverified)` |
| **Known / computed subtotal** | **5.76 g** | — |

**Total mass cannot be stated** because 11 of 13 lines are marked `TODO(unverified)`.
The sourced/computed portion is **5.76 g**; the all-up flight-board mass is that
plus the unverified items. The supercap bank and the PCB alone already account
for 5.76 g.

## 5. Contradictions found against the original worker budget

| # | Original worker assumption (`docs/POWER-BUDGET-V9-D2BE.md` before this reconcile) | ADR-006 / ADR-036 ground truth | Delta / consequence |
|---|---|---|---|
| 1 | Used a **1 F, 5.5 V** capacitor for energy calculations. | ADR-006 specifies **1.65 F @ 5.4 V** (2× AVX SCC 3.3 F 2.7 V series). | Capacitance +65 %, voltage −0.1 V. Total stored energy rises from 15.1 J to 24.1 J. The 1 F assumption is withdrawn. |
| 2 | Sized the supercap for **hold-up time** at the 6 W peak (≈0.35 s). | ADR-036 changes the storage role to **one TX burst only**. | Hold-up time is no longer the sizing metric; burst energy (modulation-dependent) is. |
| 3 | Did not apply a **daylight-only / night-sleep** policy. | ADR-036 makes TX daylight-only, night deep sleep mandatory, cold start at dawn accepted. | Average load must exclude night TX; night log survival becomes a measured deep-sleep-current question, not a capacity question. |
| 4 | v9 four-radio architecture with a **5 V rail** for the F33. | ADR-006 records a **3.3 V rail** (`TPS7A02`) and an original load of C3 + LR2021 + SKY66112 + BMP280. | **Open conflict**: a board built exactly to ADR-006 cannot simultaneously meet ADR-034/035's 5 V / 1200 mA / dual-LR2021 requirements without a new power-ADR decision. O5 remains open. |
| 5 | O5 verdict was "BLOCKED, retain only as selectable schematic option". | ADR-036 notes the bank sits at 5.4 V, so a **5 V tap before the 3.3 V LDO** is an option. | O5 is still open, but the bank voltage makes a low-drop 5 V feed feasible without a boost converter. This is recorded as a possibility, not a decision. |

No contradiction changed the conclusion that the array can cover the average load;
the main change is that the storage element is now sized to a single burst and TX is
daylight-only.

## 6. Supersede / relationship section

* **ADR-006** (`docs/adr/006-supercapacitor-power.md`, Status **Akzeptiert**) is
  **amended in part** by ADR-036. Its solar architecture (4 wings × 3 cells,
  6.0 V / 400 mA / 2.4 W peak, Schottky diode, TPS7A02 3.3 V LDO) remains in
  force. Its 1.65 F bank is re-roled from "mission-sized" to "burst-sized".
* **ADR-036** (`docs/adr/036-energy-policy-burst-storage-daylight-only-tx.md`)
  records the operator's 2026-10-07 decision and is the source of the daylight-only
  TX, mandatory night deep sleep, and burst-buffer policy used here.
* **ADR-035** (`docs/adr/035-tdm-radio-schedule.md`) D7 "energy-opportunistic TX"
  hook is promoted from hook to policy by ADR-036; the TDM slot classes are the
  schedule this budget assumes.
* **ADR-034** (`docs/adr/034-radio-band-split-433-tx-2g4-rx.md`) sets the v9 RF
  complement used in the load table.
* **ADR-029 O5** (the 5 V rail) is restated: the supercap bank already sits at
  5.4 V, so a 5 V feed for the F33's 2 W / 33 dBm 433 MHz output may be a tap
  **before** the 3.3 V LDO rather than a separate boost converter. This is an
  **option to evaluate**, not a decision; O5 stays open pending measured regulator
  load-step and cold evidence.
* **Open items carried forward**:
  - FLRC availability on the F33 sub-GHz port.
  - Cold −60 °C capacitance / ESR characterization of the chosen buffer.
  - Payload deep-sleep current in µA (decides night LOG survival).
  - Bare `LoRa2021` 2.4 GHz RX current and mass.
  - All items in the mass table marked `TODO(unverified)`.
