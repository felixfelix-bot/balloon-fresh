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
| 2 | LR2021 radio (U2, LoRa2021_Gen4) | **-40 °C** | -60 °C | **20 K below rating** | `docs/assets/lr2021/README.md` line 137 (LR2021 Operating Temperature `-40 / 25 / 85 C`) — TODO(unverified): this path was not present in the worktree at time of writing; line 137 per the task brief |

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

| Ref | Part / value | Rated min | Source |
|-----|--------------|-----------|--------|
| U2 | LoRa2021_Gen4 (LR2021 radio) | -40 °C | `docs/assets/lr2021/README.md` line 137 — TODO(unverified) path |
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
* Closing the two sourced FAILs requires part selection or an explicit
  accepted-and-characterised decision, tracked as follow-up work.
* Cold is documented as *beneficial* for the RF front end and the solar array,
  so future "keep it warm" proposals must argue against that, not for it.

## Related

* `docs/adr/006-supercapacitor-power.md` (power architecture, -60 °C premise, -40 °C supercap rating)
* `docs/RANGE-THROUGHPUT-PLAN.md` (cold soak test at -60 °C)
* `docs/component-guide.md` (supercap -40 °C range)
* `docs/FLIGHT-TEST-READINESS-2026-07-29.md` (open item: supercap suitability)
* `tracker/hardware/tools/bom_temp_gate.py` + `test_bom_temp_gate.py` (the gate)
