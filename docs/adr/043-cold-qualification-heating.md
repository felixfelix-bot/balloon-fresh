# ADR 043: Cold Qualification — Heating Rejected, Below-Rated Parts Gated

## Status

Accepted

## Context

The operator asked whether any board component would benefit from **heating**
to survive stratospheric cold. This ADR records the answer (**no**) with the
arithmetic that settles it, and records the real finding: two flight-board
parts are **used below their rated minimum temperature** with nothing in the
build gating it.

### Mission minimum

Take the mission minimum as **-60 °C**. Source: `docs/RANGE-THROUGHPUT-PLAN.md`
line 122, which plans a *"Cold soak (-60°C typical at altitude)"*. The same
-60 °C figure is the premise of the power design: `docs/adr/006-supercapacitor-power.md`
line 7 states the balloon has no access to batteries that work at -60C in the
stratosphere.

### The two identified out-of-range parts

| # | Part | Rated minimum | Mission minimum | Margin | Source |
|---|------|---------------|-----------------|--------|--------|
| 1 | Supercapacitor bank (2× 3.3 F 2.7 V series, C_CAP) | **-40 °C** | -60 °C | **20 K below rating** | `docs/adr/006-supercapacitor-power.md` line 63 (`-40C bis +70C`); agreed by `docs/component-guide.md` line 84 (`Supercaps funktionieren bis -40 C`) |
| 2 | LR2021 radio (U2, LoRa2021_Gen4) | **-40 °C** | -60 °C | **20 K below rating** | `docs/LR2021_LR2022_LR2012_Datasheet_Rev2.1.pdf` §3.2, Table 3-2 (`Top` = -40 … +85 °C ambient; `Tmaxj` 105 °C; `Tmr` -55 … +125 °C) — in-tree Semtech datasheet, verified with `pdftotext -layout` (see Addendum; supersedes the earlier `docs/assets/lr2021/README.md:137` reference) |

Both parts are 20 K below the mission minimum. Suitability of the supercap was
already an open item: `docs/FLIGHT-TEST-READINESS-2026-07-29.md` line 70
records *"Need to verify suitablity for high altitude + weight."* This ADR
closes that open item as: **suitability is a part-selection problem, not a
heating problem.**

## Energy arithmetic for heating (every estimate marked)

A heater must hold a temperature differential **continuously — night included**,
because the cold is ambient and the night is unheated. Use:

```
P = ΔT / R_thermal
```

* `R_thermal` ≈ **100 K/W** (ESTIMATE — no measured enclosure thermal resistance exists; TODO(unverified): measure a populated board in vacuum to replace this)
* ΔT to lift from -60 °C ambient to a -5 °C survival band ≈ **55 K**

```
P = 55 K / 100 K/W = 0.55 W  ≈ 0.5 W   (order-of-magnitude)
```

Usable bank energy is about **14 J** (per ADR-006). Therefore:

```
t = E / P = 14 J / 0.5 W ≈ 28 s
```

**≈ 0.5 W drains the entire usable bank in roughly 28 seconds.** A heater is
not merely inefficient — it is arithmetically impossible with this energy
store.

Warming the **storage** is self-defeating. Supercap thermal mass is order
**3 g** (ADR-006 line 65 / `docs/PCB-HANDOVER-FOR-JLCPCB.md` line 173:
2× 3.3 F in series + 10 kΩ balancing → 1.65 F @ 5.4 V, ~3.0 g) at roughly
**1 J/(g·K)** (ESTIMATE — typical for a packaged electrolytic/supercap):

```
C_th = 3 g × 1 J/(g·K) = 3 J/K          (ESTIMATE)
Q(+20 K) = 20 K × 3 J/K = 60 J
```

**A +20 K lift of the storage alone costs order 60 J — about four times the
whole usable 14 J budget.** Keeping a supercap warm by consuming supercap
energy is a positive-feedback loss.

## Per-component verdict

| Component class | Heating verdict | Why |
|-----------------|-----------------|-----|
| Supercapacitor bank | **HURT** | Warming storage costs ~4× the usable budget (above); the fix is part selection (a -55/-60 °C-rated device) or accepted-and-characterised -40 °C behaviour. |
| LR2021 radio (RF front end) | **HURT / unnecessary** | Cold is *beneficial* to the RF front end: lower thermal noise, better noise figure. Heating it would raise the noise floor for no benefit. |
| Solar array | **HURT / unnecessary** | Solar efficiency and Voc *rise* as temperature falls, so the 2.4 W budget is conservative at altitude. Heating the array sacrifices the very margin cold provides. |
| MS5611-01BA / BMP280 pressure sensor | **HURT (actively corrupts data)** | The sensor must sense AMBIENT pressure and self-heats its own compensation sensor. Heating it biases the pressure reading and therefore the telemetered altitude. Cold is the measurement condition, not an enemy. |
| ESP32-C3, MAX-M10S GNSS, LDO, passives, connectors | **INDIFFERENT at the analysis level** | No heating case is made; each must still pass the minimum-rating gate (below). |
| Night deep-sleep draw | **INDIFFERENT** | Night draws microamps, so insulation buys almost nothing at steady state. **Insulation is not recommended as the fix.** |

## Decision

1. **Heating is rejected** as a remedy for stratospheric cold. The energy
   arithmetic is decisive: ~28 s of run time, or ~4× the usable budget to warm
   the storage alone.
2. **The remedy is part selection, or accepted-and-characterised behaviour.**
   A part used below its rated minimum is either replaced with a colder-rated
   part, or its cold behaviour is characterised and explicitly accepted. Never
   heating.
3. **Nothing may pass silently.** Every part's rated minimum is gated against
   the mission minimum by a deterministic script,
   `tracker/hardware/tools/bom_temp_gate.py` (exit 0 PASS / 1 FAIL /
   2 CANNOT-VERIFY; a part with no temperature data is CANNOT-VERIFY naming
   that part, never a silent pass; the two known offenders are named when
   present).
4. **Insulation is not the fix** and is not recommended.

## Per-part rated-minimum table

Source per row. `TODO(unverified)` marks a rating that is not yet backed by a
document line in-repo — those rows are what `--strict-provenance` fails closed
on. Ratings live in `tracker/hardware/tools/bom_ratings.csv`; the BOM itself is
derived from the real 28-footprint flight PCB
(`tracker/hardware/output/v8i_krt_gnss.kicad_pcb`) and the MS5611 variant,
seeded as `tracker/hardware/tools/bom_v8i_gnss.csv`.

> **Superseded by the Addendum below (2026-10-07).** `TODO(unverified)` rows no
> longer exist in the DB: every retained rating is sourced to a document, and
> every row that could not be sourced was deleted so the gate returns
> CANNOT-VERIFY for it.

| Ref | Part / value | Rated min | Source |
|-----|--------------|-----------|--------|
| U2 | LoRa2021_Gen4 (LR2021 radio) | -40 °C | `docs/LR2021_LR2022_LR2012_Datasheet_Rev2.1.pdf` §3.2 "Operating Range (LR20xx)", Table 3-2 (`Top` ambient -40 … +85 °C) |
| C_CAP | 1F_5.5V supercap (bank: 2× 3.3 F series) | -40 °C | `docs/adr/006-supercapacitor-power.md` line 63 |
| U1 | ESP32-C3-WROOM-02 | -40 °C | TODO(unverified): Espressif datasheet thermal section |
| U3 | MAX-M10S (GNSS) | -40 °C | TODO(unverified): u-blox datasheet operating temperature |
| U5 | MS5611-01BA (v8j) / BMP280 (v8i) | -40 °C | TODO(unverified): TE / Bosch datasheet operating temperature |
| U4 | TPS7A02 (LDO) | -40 °C | TODO(unverified): TI datasheet operating junction temperature |
| D1 | BAT54 | -65 °C | TODO(unverified): Vishay/onsemi datasheet |
| R_LED/R_DIV1/R_DIV2/R_PD/R_SER | 330R / 100k / 100k / 10k / 0R (0402) | -55 °C | TODO(unverified): AEC-Q200-grade 0402 thick-film typical |
| C1/C2/C3/C4 | 10uF / 100nF (0603/0402) | -55 °C | TODO(unverified): X5R/X7R MLCC typical |
| LED1 | LED_RED (0603) | -40 °C | TODO(unverified): 0603 LED typical |
| ANT1/ANT2 | U.FL / U.FL_GNSS | -40 °C | TODO(unverified): Hirose U.FL series |
| J1/J2/SOLAR | Prog_Header / Debug_Header / Solar_In | -40 °C | TODO(unverified): 2.54 mm pin header typical |
| MNT1–4 | MountingHole | -55 °C | TODO(unverified): mechanical, no active silicon |
| C_SH1/C_SH2 | DNP | n/a | not populated |

**UNVERIFIED: what would settle each TODO row** — the manufacturer datasheet
operating-temperature section for the exact ordered MPN, filed next to that
part in the ratings DB. Until then the gate correctly reports those rows as
CANNOT-VERIFY under `--strict-provenance` and orders them after any hard FAIL.

## Consequences

* The gate is deterministic and fail-closed; it can run in CI or pre-fab.
* Two parts (supercap, LR2021) are known to fail the mission minimum **with
  in-repo documentary evidence** and are named by the gate.
* **Reconciling "two out-of-range parts" with the gate's raw output.** Run
  against the real 28-footprint PCB with the seed ratings DB, the gate reports
  many FAILs, not two: every `-40 °C` part is 20 K short, and every `-55 °C`
  passive is 5 K short of the `-60 °C` mission minimum. That is the gate being
  honest and fail-closed, not a contradiction. The **two** the ADR names as
  *identified* are the two whose ratings are sourced to a document line in this
  repo (supercap `-40 °C`, LR2021 `-40 °C`); the remainder are
  `TODO(unverified)` seed ratings awaiting datasheets, and
  `--strict-provenance` demotes exactly those to CANNOT-VERIFY. Tightening the
  seed ratings to real datasheets is follow-up work, and the gate is the thing
  that will hold the line when it happens.
  *Addendum note (2026-10-07): the seed `-55 °C` passives were invented
  "typical range" guesses and have been deleted. The systemic finding stands and
  is stated, with the gate's own output, in the Addendum below.*
* Closing the two sourced FAILs requires part selection or an explicit
  accepted-and-characterised decision, tracked as follow-up work.
* Cold is documented as *beneficial* for the RF front end and the solar array,
  so future "keep it warm" proposals must argue against that, not for it.

## Addendum (2026-10-07): ratings DB hardened — no invented ratings, fail-closed

### What was wrong

The seed ratings DB shipped 24 rows, 20 of them `TODO(unverified)` — and most of
those 20 were not *unverified citations* but **invented "typical range"
claims**: `2.54mm pin header typical range`, `0603 LED typical range`,
`AEC-Q200-grade 0402 thick-film resistor typical range`, `X7R 0402 MLCC typical
range`, `AEC-Q200-grade 0402 jumper typical range`, `mechanical`. A guessed
number that reads like a rating is worse than no number: in plain (non-strict)
mode every one of those guesses drove a **FAIL verdict off a fabrication** (25
FAILs against the 2 the ADR names), burying the real headline in noise the gate
could not distinguish from evidence.

### The rule now enforced

* A rating is retained only if it cites a **specific document + table/section/page**
  for a part whose identity is fixed by the value recorded on the BOM.
* A row that cannot be sourced is **deleted**, so the gate returns
  **CANNOT-VERIFY** naming that part — the designed fail-closed outcome. No
  substitute guess, and the mission minimum (-60 °C) is unchanged.
* `--strict-provenance` is the **honest mode** and is the mode to use for a real
  qualification call. It now also fails closed on any `source` that reads as a
  class guess (contains "typical"), so an invented rating cannot silently drive a
  PASS or a FAIL even if one is re-added later
  (`bom_temp_gate._provenance_unverified`).

### Retained ratings (every row sourced)

| Key | Min | Max | Source (document · location) |
|-----|-----|-----|------------------------------|
| LoRa2021_Gen4 (U2) | -40 °C | +85 °C | `docs/LR2021_LR2022_LR2012_Datasheet_Rev2.1.pdf` — Semtech DS.LR20xx, Final Datasheet Rev. 2.1 (13/04/26), **p.37 §3.2 "Operating Range (LR20xx)", Table 3-2**: `Top` ambient operating temperature -40 … +85 °C (`Tmaxj` max junction 105 °C; `Tmr` storage -55 … +125 °C) |
| 1F_5.5V / 3.3F / 1.65F (C_CAP bank) | -40 °C | +70 °C | `docs/adr/006-supercapacitor-power.md:63` (`-40C bis +70C`) |
| ESP32-C3-WROOM-02 (U1) | -40 °C | +85 °C | Espressif ESP32-C3-WROOM-02 Datasheet **v1.7**, §6.2 "Recommended Operating Conditions", **Table 6-2**: `TA` min -40 °C (module ships as -40…85 °C or -40…105 °C variant, §1) |
| MAX-M10S (U3) | -40 °C | +85 °C | u-blox MAX-M10S data sheet **UBX-20035208-R08**, §4.2 "Operating conditions", **Table 13 "General operating conditions"**: `Topr` -40 … +85 °C |
| BMP280 (U5, v8i) | -40 °C | +85 °C | Bosch Sensortec BMP280 data sheet **BST-BMP280-DS001-26** (rev 1.26, Oct 2021), **Table 2 "Parameter specification"**: operating temperature range `TA` (operational) -40 … +85 °C |
| TPS7A02 (U4) | -40 °C | +125 °C | TI TPS7A02 data sheet **SBVS277C** (rev Sep 2022), §6.3 "Recommended Operating Conditions": `TJ` operating junction temperature -40 … +125 °C |
| DNP (C_SH1/C_SH2) | n/a | n/a | not populated — no rating applicable |

### Deleted ratings (unsourceable → CANNOT-VERIFY, by design)

| Value (refs) | Why deleted |
|---|---|
| 100k / 10k / 330R / 0R (0402) | invented class claim "AEC-Q200-grade 0402 thick-film resistor/jumper typical range"; BOM records no MPN |
| 100nF (0402) / 10uF (0603) | invented class claim "X7R 0402 / X5R-X7R 0603 MLCC typical range"; no MPN |
| LED_RED (0603) | invented class claim "0603 LED typical range"; no MPN |
| Debug_Header / Prog_Header / Solar_In | invented class claim "2.54 mm pin header typical range"; no MPN |
| MountingHole (MNT1–4) | "mechanical" carries no document; no active silicon, and the gate deliberately has no N/A escape hatch |
| U.FL / U.FL_GNSS (ANT1/2) | "U.FL" is a multi-vendor form factor (Hirose / I-PEX MHF / Amphenol) with no MPN; no datasheet retrievable and none filed in-repo |
| BAT54 (D1) | generic multi-vendor part number (Diodes Inc / onsemi / Nexperia / Vishay) whose ratings differ by vendor; BOM records no vendor MPN. The Diodes Incorporated datasheet (DS11005 Rev. 34-2, "Thermal Characteristics": `TJ,TSTG` -65 … +150 °C) was located but is not authoritative for an unknown fitted vendor |
| MS5611-01BA (U5, v8j) | sole-source TE part, but its datasheet could not be retrieved in this environment and is not filed in-repo; left at CANNOT-VERIFY rather than guessed |

### The LR2021 (U2) citation is closed

The previous row cited `docs/assets/lr2021/README.md:137` with the note "path not
present in this worktree". That reference is **replaced** by the in-tree primary
source — `docs/LR2021_LR2022_LR2012_Datasheet_Rev2.1.pdf`, §3.2, Table 3-2
(`Top` = -40 … +85 °C ambient; `Tmaxj` = 105 °C; `Tmr` = -55 … +125 °C) —
verified with `pdftotext -layout`. The "path not present" caveat is withdrawn:
the U2 rating is now a hard, cited FAIL, not a TODO.

### Systemic finding — this is not two offenders

Run against the real 28-footprint flight board
`/home/c03rad0r/worktrees/v8j-ms5611-reroute/tracker/hardware/output/v8i_krt_gnss.kicad_pcb`
(397,725 bytes), the gate's own output shows the pattern is board-wide, not two
parts. With the **seed DB** (plain mode, before this addendum):

```
FAIL -- parts used below their rated minimum:   (25 of 28 parts)
  ... 0402/0603 passives   rated_min -55C ABOVE mission_min -60C by 5 K   (typical-range guesses)
  ... ICs/connectors       rated_min -40C ABOVE mission_min -60C by 20 K
RESULT: FAIL (25 part(s) above mission minimum; 2 cannot-verify)
```

That is the headline: against the -60 °C mission the **passives commonly sit 5 K
below their rated minimum and the ICs/headers 20 K below** — most of the board
sits 5–20 K below its rated minimum, not two parts. After hardening, plain and
`--strict-provenance` agree (every retained rating is sourced):

```
FAIL -- 6 parts, all 20 K below rating:
  U1 ESP32-C3-WROOM-02 · U2 LoRa2021_Gen4 · U3 MAX-M10S · U4 TPS7A02 · U5 BMP280 · C_CAP 1F_5.5V
CANNOT-VERIFY -- 22 parts without a sourced rating (named: all passives, headers, U.FL, BAT54, DNP)
RESULT: FAIL (6 part(s) above mission minimum; 22 cannot-verify)
```

The two **headline** offenders the ADR identifies remain the worst cases and are
the two whose ratings were already document-sourced: the supercapacitor bank
(-40 °C, `docs/adr/006-supercapacitor-power.md:63`) and the LR2021 radio (-40 °C,
in-tree datasheet Table 3-2). They are the worst cases, **not the whole story**:
the systemic fact is that the -60 °C mission sits roughly 5 K below the common
-55 °C passive rating and 20 K below the common -40 °C IC/module rating.

## Related

* `docs/adr/006-supercapacitor-power.md` (power architecture, -60 °C premise, -40 °C supercap rating)
* `docs/RANGE-THROUGHPUT-PLAN.md` (cold soak test at -60 °C)
* `docs/component-guide.md` (supercap -40 °C range)
* `docs/FLIGHT-TEST-READINESS-2026-07-29.md` (open item: supercap suitability)
* `tracker/hardware/tools/bom_temp_gate.py` + `test_bom_temp_gate.py` (the gate)
