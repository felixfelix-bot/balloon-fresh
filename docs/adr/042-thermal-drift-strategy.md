# ADR-042 — Thermal / frequency-drift strategy for the balloon radio

- Status: **Proposed** — the *decision* this ADR records (reject the board heater; prefer
  TCXO, then firmware f(T) pre-distortion, then wider channel plan) is recorded here;
  the *text* has not been accepted by a human, so it does not say Accepted.
- Date: 2026-10-07
- Decision owner: Felix (operator)
- Author: Hermes agent (sub-delegated)
- Related: ADR-006 (`docs/adr/006-supercapacitor-power.md`), ADR-036
  (`docs/adr/036-energy-policy-burst-storage-daylight-only-tx.md`, branch
  `adr/energy-policy`, commit `b304efd`), ADR-029
  (`docs/adr/029-dual-band-flight-board.md`, branch `adr/radioband-tdm`),
  `docs/LR2021-LESSONS-2026-09.md` (branch `docs/lr2021-lessons`, commit `581b38b`).
- Related artefacts in this repo:
  `docs/adr/006-supercapacitor-power.md`,
  `docs/adr/036-energy-policy-burst-storage-daylight-only-tx.md` (branch
  `adr/energy-policy`),
  `docs/adr/029-dual-band-flight-board.md` (branch `adr/radioband-tdm`),
  `docs/LR2021-LESSONS-2026-09.md` (branch `docs/lr2021-lessons`).
- Datasheet source for **Addendum A** (amendment, 2026-10-07):
  `docs/LR2021_LR2022_LR2012_Datasheet_Rev2.1.pdf` and
  `docs/data-handover/HARMONIZATION-GAP-ANALYSIS.md` (row N4) — both on branch
  `docs/lr2021-lessons` (commit `581b38b`).

> Numbering note: 042 was selected because 036–038 are taken on concurrent branches
> (`adr/energy-policy`, `adr/radioband-tdm`/`adr/mcu-s3-no-fem`, `adr/wifi-bt-disabled`),
> 039–041 are being written concurrently by other workers, and no `042-*` file exists on
> any branch inspected.

---

## Context

The operator asked whether to add a **heater on the board near the radios** to counter
frequency drift, "now that we have all this excess energy". This ADR settles that
question with arithmetic, ranks the alternatives, names the deciding number, and records
a direct conflict with the pressure sensor.

The thermal facts from the repo:

- `docs/LR2021-LESSONS-2026-09.md` §"Temperature drift (PLAIN crystal — OPEN, consultant
  pass in flight)" states that the **plain** NiceRF LoRa2021 modules used by the project
  have **NO TCXO and NO NTC**; the crystal frequency drifts with temperature; community
  evidence says TX drifts out of channel at narrow bandwidth; stratosphere ambient is
  about **−44 °C to −60 °C**; the LoRa RX side tolerates some carrier-frequency offset,
  but the quantification is pending a consultant pass.
- `docs/LR2021-LESSONS-2026-09.md` also notes that the **NiceRF LoRa2021F33-2G4** module
  (the v9 candidate with the LR2021 chip) has a **0.5 ppm industrial TCXO**.
- ADR-006 records the power architecture as **2 x AVX SCC 3.3 F 2.7 V in series = 1.65 F
  @ 5.4 V**, fed by **4 wings x 3 cells = 12 cells in series = 6.0 V @ 400 mA = 2.4 W peak**.
- ADR-036 records the operator's decision that the buffer is sized to **one burst, not the
  mission**, and that **TX is energy-gated and daylight-only**. ADR-036 also states that
  **night is mandatory deep sleep** and that a continuous night load is the known budget
  breaker: its own note says **1 mW x 10 h = 36 J is not feasible** with the fitted bank.
- ADR-029 item O5 records that the v9 board has **NO 5 V rail**; the F33-2G4's 5 V
  high-power point is not provisioned.

## Decision

**Reject the board heater. It is incompatible with ADR-036's one-burst, daylight-only,
deep-sleep policy. Ranked mitigation alternatives: (1) TCXO stability, (2) firmware f(T)
pre-distortion characterised in the cryo bath, (3) wider channel plan / LoRa carrier-offset
tolerance. The deciding number — carrier offset tolerance versus actual drift — is
currently unquantified and is the gate that decides whether any mitigation is needed at
all.**

> **Amendment (2026-10-07, Addendum A):** the runtime temperature sensor is confirmed; the
> 100 K NTC-on-pin-3 fix is ranked alongside the TCXO and strictly above the heater; a
> temperature-triggered recalibration requirement and the ±10 ppm / −20…+70 °C characterised
> window are recorded. §D1's heater arithmetic is **unchanged and still stands**.

### D1 — Reject the board heater

A board heater must hold a temperature **differential continuously**, including through the
night. In steady state:

```
P_heater = ΔT / R_thermal
```

For a module-scale part in a small enclosure in still air, the thermal resistance to ambient
is of order **R_thermal ≈ 100 K/W**.

- Warming **10 K** costs:
  `P = 10 K / 100 K/W = 0.1 W = 100 mW` continuous.
- Lifting the part from **−55 °C to 0 °C** (ΔT = 55 K) costs:
  `P = 55 K / 100 K/W = 0.55 W ≈ 0.5 W` continuous.
- At **0.5 W for a 10 h night**, the energy required is:
  `E = 0.5 W × 10 h = 0.5 W × 36 000 s = 18 000 J = 18 kJ`.
- The supercap bank at 5.4 V that could supply this would need:
  `C = 2 E / V² = 2 × 18 000 J / (5.4 V)² ≈ 1235 F`.
  The fitted bank is **1.65 F** (ADR-006); the shortfall is about **750×**.
- Even **1 mW** of heating buys only:
  `ΔT = 1 mW × 100 K/W = 0.001 W × 100 K/W = 0.1 K`,
  which is negligible against a 55 K lift.

The solar array's 2.4 W is a **daylight peak**, not a continuous source. ADR-006 states it
is "more than 10x the average demand", implying an average of roughly **240 mW** or less,
and the sun is absent exactly when a heater would run. A continuous night load of the size
needed to warm the board would break ADR-036 explicitly: 1 mW × 10 h = 36 J is already
"not feasible" with the fitted bank, and a heater needs hundreds of milliwatts.

Therefore: **no board heater.**

**Assumptions marked as such:**

- `R_thermal ≈ 100 K/W` for a module-scale part in a small enclosure in still air is
  `TODO(unverified)`. The measurement that settles it is a calibrated heater step test
  on the actual v9 enclosure: apply a known P, measure ΔT at equilibrium, compute
  R_thermal = ΔT / P. Any result ≥ 30 K/W keeps the conclusion (heater rejected); only a
  value below roughly 10 K/W would materially change it, which is implausible for an
  unsealed, small, still-air enclosure at stratospheric pressure.
- The chosen lift target (0 °C) is arbitrary; the arithmetic is shown for ΔT = 10 K and
  ΔT = 55 K so the operator can scale to any target.
- The bank is assumed to be usable down to its lower cutoff; actual usable energy depends
  on the LDO dropout and the cold ESR of the supercaps (ADR-036 leaves this open).

### D2 — First-choice mitigation: TCXO stability

The heater already exists at the right scale **inside the crystal that is designed for it**:
a TCXO is an oven-controlled crystal at milliwatt scale because it holds only a tiny
thermal mass, not the whole board.

- The **LoRa2021F33-2G4** carries a **0.5 ppm industrial TCXO** (cited from
  `docs/LR2021-LESSONS-2026-09.md`), so selecting the F33 for v9 already solves the drift
  problem for the module itself.
- For the **plain LoRa2021 module** (crystal only, no TCXO), the equivalent escape hatch
  is an external TCXO on the bare module or a module swap to the F33.
- ADR-029 O5 records that the v9 board has **no 5 V rail**. The F33's TCXO is run at
  **3.3 V** per the lessons addendum (`LR20XX_SYSTEM_TCXO_CTRL_3_3V` in NiceRF demo code),
  so the TCXO itself does not need the missing 5 V rail. The F33's **5 V high-power TX
  point** is a separate issue and is not required for the TCXO function. Any external-TCXO
  path for a bare module must state its own rail and current draw; that is left as
  `TODO(unverified)` unless/until that path is pursued.

**Decision:** wherever the project has a choice, prefer the TCXO-bearing part (F33-2G4) over
the plain crystal module. The TCXO path is the first-choice mitigation because it is
zero-firmware, zero-characterisation, and consumes milliwatts inside the part instead of
watts on the board.

### D3 — Second-choice mitigation: firmware f(T) pre-distortion

If a bare-crystal module must be flown, the crystal's f(T) curve is repeatable. The
project can characterise it once and offset the synthesizer by the inverse.

**Concrete characterisation protocol (pass/fail):**

1. **Instrument:** use the existing E80/RF cryo facility (the operator owns the
   instrument; it has already been used for radio characterisation in this project).
2. **DUT:** one representative plain LoRa2021 module on the flight firmware, at the
   planned reference frequency and modulation settings.
3. **Temperature sweep:** soak at −60 °C, −40 °C, −20 °C, 0 °C, +20 °C, +40 °C, with at
   least 20 min soak per step and a calibrated thermometer on the module shield/can.
4. **Measurement:** at each step, measure actual carrier frequency with a calibrated SDR
   or counter; compute `Δf(T) = f_measured(T) − f_nominal`.
5. **Fit:** fit a cubic (or vendor-recommended) polynomial `Δf(T)` over the sweep range.
6. **Apply:** firmware writes `f_set = f_nominal − Δf(T)` into the LR2021 frequency
   synthesizer, using a **runtime** temperature reading. *(Correction, Addendum A point 1: a
   runtime sensor **does** exist — the LR2021 exposes `GetTemp` (raw or °C, with a selectable
   source). The "on-board sensor or … last known soak temperature **if no runtime sensor
   exists**" fallback that stood here is retracted; see Addendum A.)*
7. **Pass criterion:** after applying the correction at each soak temperature, residual
   carrier offset is **< 50 % of the uncorrected offset at that temperature**, across the
   whole −60 °C … +40 °C range, AND the residual offset stays inside the LoRa carrier-offset
   tolerance budget named in §D5.
8. **Hysteresis bound:** run the sweep twice (cold → hot, then hot → cold). The correction
   is valid only if the **hysteresis loop (offset at the same T on the two passes) is
   smaller than the residual-offset target**; otherwise the crystal is not repeatable
   enough and pre-distortion is rejected.

This path has **zero mass and negligible power** (a table lookup + one synth write). Its
limit is crystal hysteresis and ageing; it is bounded by the measurement above.

### D4 — Third-choice mitigation: wider bandwidth / channel plan

LoRa's demodulator tolerates real carrier offset. The third choice is to relax the channel
plan so the expected drift stays inside the passband. This is the fallback when neither
hardware (TCXO) nor firmware (pre-distortion) is available.

The deciding quantity is the same as in D5: **carrier-offset tolerance vs actual drift**.
If the measured drift at −60 °C is smaller than the LoRa bandwidth's carrier-offset budget,
a channel-plan change alone may suffice. This is recorded as a live option, not a
recommendation, because it costs spectrum efficiency and link budget.

### D5 — THE DECIDING NUMBER: carrier-offset tolerance vs actual drift

No mitigation decision can be final until the following number is known:

> **Δf_max = (measured carrier drift from −60 °C to +40 °C) − (LoRa carrier-offset
> tolerance for the chosen BW/SF).**

If Δf_max ≤ 0, **no mitigation is needed**. If Δf_max > 0, the magnitude decides which of
D2–D4 is required.

**What produces this number:**

- The **drift** half is produced by a cold-sweep measurement of the actual module (plain or
  F33) in the cryo bath, comparing measured carrier frequency at −60 °C, −40 °C, −20 °C,
  0 °C, +20 °C, +40 °C against the nominal channel.
- The **tolerance** half is produced from the LR2021 / LoRa datasheet: the maximum carrier
  frequency offset the modem can correct for the selected bandwidth and spreading factor.
  For LoRa this is typically a fraction of the bandwidth (often quoted as ±25 % of the
  bandwidth up to a few kHz, but the exact figure depends on BW and SF and must be read
  from the current datasheet revision).

This number is **UNVERIFIED in the repo**. It is the gate. Until it is measured, D2 (TCXO)
is the conservative default because it removes the drift question from the flight-critical
path.

### D6 — Conflict: deliberate heating biases the MS5611 pressure measurement

ADR-029 D6 selects an MS56xx barometric sensor (MS5607-02BA03 cost pick, MS5611-01BA03
reference) on the same small board. The sensor measures absolute pressure for altitude
telemetry.

**Conflict:** deliberate heating near the radios warms the board, which warms the pressure
sensor, which changes its temperature reading and can bias its pressure output through
temperature-dependent offset/span coefficients. Even if the MS56xx is internally
temperature-compensated, the compensation has residual error; heating the part to an
unknown, spatially-varying temperature corrupts the altitude estimate being telemetered.

This conflict is **additional and independent** of the energy argument: even if a heater
could be afforded, it would fight the pressure-sensing function. The no-heater decision
therefore protects both the energy budget and the altitude telemetry.

## Relationship to standing decisions

### Amended / constrained

- **ADR-006 `006-supercapacitor-power.md`: "Akzeptiert" — the 1.65 F bank is constrained
  by this ADR.** ADR-036 already amended the bank's role to "one burst, not the mission";
  ADR-042 adds that the bank **cannot** be used for continuous thermal management. The
  solar architecture itself is unchanged. ADR-006 is **not edited**; the relationship is
  stated here.

### Reinforced / promoted

- **ADR-036 `036-energy-policy-burst-storage-daylight-only-tx.md`: "Proposed" — the
  daylight-only, deep-sleep policy rejects the heater.** ADR-042 records the thermal
  consequence of that policy explicitly. ADR-036 is **not edited**; the relationship is
  stated here.

### Referenced, still open

- **ADR-029 item O5 (the 5 V rail) — still open.** The F33's TCXO runs at 3.3 V and does
  not need the missing 5 V rail; the F33's 5 V high-power TX point remains unprovisioned.
  Any bare-module-plus-external-TCXO path must do its own rail check. ADR-029 is **not
  edited**; the relationship is stated here.

- **ADR-029 D6 (MS56xx barometer) — referenced as the conflict.** The pressure sensor is
  on the same board; any heating strategy must account for altitude-bias. This ADR records
  that conflict and resolves it by rejecting the heater.

## Open items (kept open, not resolved here)

- **R_thermal measurement — TODO(unverified).** Calibrated heater step test on the v9
  enclosure to replace the assumed 100 K/W.
- **Carrier-offset tolerance vs actual drift — TODO(unverified).** Cold-sweep carrier drift
  measurement and LoRa BW/SF tolerance lookup; this is the gate for D2–D4.
- **External-TCXO rail and current for bare module — TODO(unverified).** Only needed if
  v9 flies a bare module with an external TCXO instead of the F33.
- **Cryo-bath f(T) characterisation pass/fail — TODO(unverified).** Only needed if D3
  (firmware pre-distortion) is selected.

## What would falsify this

- A measured R_thermal below ~10 K/W in the actual enclosure would make a low-grade heater
  energy-feasible; it would still have to be reconciled with the MS5611 altitude-bias
  conflict in D6.
- A measured carrier drift smaller than the LoRa carrier-offset tolerance (Δf_max ≤ 0)
  would make all hardware/firmware mitigations optional; the no-heater conclusion would
  still stand because no heater is needed.
- A bench measurement showing the F33's TCXO does not meet its 0.5 ppm spec at −60 °C
  would reopen the TCXO-first choice.

## Addendum A — datasheet correction: a runtime temperature sensor exists, and the NTC fix

**Added 2026-10-07 as an AMENDMENT to this ADR — not a rewrite.** Every quote below was
verified against the in-tree datasheet `docs/LR2021_LR2022_LR2012_Datasheet_Rev2.1.pdf`
(branch `docs/lr2021-lessons`; Semtech *Final Datasheet Rev. 2.1*, `DS.LR20xx 13/04/26`,
243 pp) using `pdftotext -layout`; the chapter/table and the quoted line are given per point.
Nothing in §D1 (the heater-rejection arithmetic) is removed or re-derived.

### A1 — CORRECTION: a runtime temperature sensor DOES exist

§D3 step 6 previously read "…using a temperature reading from an on-board sensor or from the
last known soak temperature **if no runtime sensor exists**". **That premise is wrong and is
retracted here.** The LR2021 has a temperature measurement command:

- **§6.5.2 `GetTemp`** (datasheet p.113), `Table 6-32: GetTemp Command` /
  `Table 6-33: GetTemp Response`. Quoted: *"The GetTemp command retrieves the current value of
  the temperature in the specified Format."*
- The command-table row (`Table 5-3: System Configuration Commands (Sheet 2 of 2)`, p.83) gives
  `GetTemp 0x0125`, described as *"Measures and returns raw temperature measurement, or the
  temperature in °C"*, with fields `Source(1:0)`, `Format`, `Resolution(2:0)`.
- **`Source(1:0)`** — "sets the temperature sensor source for temperature measurement"
  (§6.5.2, p.114): `0x00` Built-in junction temperature Vbe; `0x01` Built-in junction
  temperature close to XOSC; `0x02` **NTC**; `0x03` RFU. `Format` selects raw vs °C.

So firmware can read a real, runtime, **source-selectable** temperature — from the die, the die
near the oscillator, or an external NTC. The "last known soak temperature" fallback is not
needed for this reason.

### A2 — THE CHEAP HARDWARE FIX (rank ABOVE the heater, alongside the TCXO)

The LR2021 already contains the correct closed loop. The datasheet describes it directly:

- **§1.9.2 "32MHz Crystal"** (datasheet p.32; footer "32 of 243"). Quoted: *"The optional XTAL
  temperature compensation mechanism measures the XTAL temperature change and compensates on
  chip for the induced frequency shift. When the temperature compensation mechanism is used,
  the VTCXO pin can be used to power an external temperature sensor (R and NTC) monitoring the
  XTAL temperature. The NTC output is then fed into the chip via pin NTC and measured by an
  increase in ADC. The resulting temperature information is used by the chip to automatically
  compensate, to some extent, the frequency shift due to XTAL heating."* (Figure 1-15
  "NTC Connection".)
- **§6.12 "Temperature Compensation"** (p.128), quoted: *"The temperature compensation is
  useful to limit frequency drift during high power transmissions."*
- **§6.12.1 `SetTempCompCfg`** (p.129), `Table 6-69: SetTempCompCfg Command`, opcode
  **`0x0132`**: *"The SetTempCompCfg command configures the heating compensation block in Tx if
  an XTAL 32MHz is used."* Fields: `ntc` (1 = Enables NTC, 0 = Disables NTC) and
  `comp_mode(1:0)` (0x0 Disabled, 0x1 Relative, 0x2 Absolute, 0x3 RFU). Same section: *"If an
  NTC source is available, it is used to compensate the variation in temperature of the
  crystal, while the internal temperature measurement can always be used to compensate the
  frequency deviation due to chip self heating."*
- **§6.12.2 `SetNtcParams`** (`Table 6-70`, opcode `0x0133`) enters the `ntc_r_ratio` and
  `ntc_beta` parameters the loop needs.
- **Pin 3 = `NTC`** — `Table 2-1: Pin-out Description (Sheet 1 of 2)` (p.34), quoted:
  *"Negative Temperature Coefficient (NTC) resistor connection"*.

**On our module the loop is open.** `docs/LR2021-LESSONS-2026-09.md` line 22 (branch
`docs/lr2021-lessons`, commit `581b38b`) records the module census: the **NiceRF LoRa2021
(PLAIN — ours, 4x)** = *"crystal, no TCXO, no NTC (carlhodder deshielded to verify)"*. Line 24
records the **Waveshare Core2021-XF** as the *"only NTC variant found"* — *"NTC 100K mounted,
beta unverified (~4250K assumed)"*. So on the plain module pin 3 is **UNPOPULATED** and the
chip's compensation engine is idle: `SetTempCompCfg` would configure a sensor that is not
fitted.

**Fitting a 100 K NTC on pin 3 closes the loop** — one component (plus a series R to the VTCXO
rail), a microwatt-scale bias current, and it corrects the **frequency** rather than trying to
hold a temperature. Two structural advantages over a board heater:

- It needs **no continuous power** to fight an ambient gradient: the loop dissipates nothing and
  draws only the NTC bias current from the VTCXO regulator (specified `ILTCXO` 1.5 mA typ /
  4 mA max in `Table 3-25: TCXO Regulator Specifications (LR20xx)`, p.68 — the NTC bias is a
  small fraction of that).
- It needs **no awake MCU** — the compensation runs on-chip. This is the point the heater cannot
  answer: a heater/oven is worthless at night (A3), whereas this loop is passive hardware inside
  the transceiver.

**Module-level constraint — `TODO(unverified)`.** On the NiceRF PLAIN module the 32 MHz crystal
sits under the **RF shield can** (per the deshield provenance in the lessons line above). The
exact NTC placement, its bonding point on the XTAL, the series-R value, and **whether pin 3 is
even broken out on the NiceRF module's castellation pads** are all `TODO(unverified)`. What
settles it: the **module mechanical drawing** (the module's pin-out, not just the chip's) or a
**deshield photo** of a PLAIN sample. Until then this is a high-confidence, cheap, best-fit fix,
not a shippable one.

**Ranking.** With the runtime sensor confirmed and the loop physically inside the part, the
mitigation ranking becomes **(1) TCXO stability, (1b) 100 K NTC on pin 3 for a crystal-only
module, (2) firmware f(T) pre-distortion, (3) wider channel plan.** The NTC fix sits alongside
the TCXO (both hardware frequency fixes, zero firmware) and strictly above the heater; the
heater was already rejected in §D1.

### A3 — Why a board-level oven / closed-loop heater still fails (arithmetic kept)

§D1's arithmetic stands and is not restated; it is joined here by the structural reasons:

1. **Heat-only control means the setpoint must exceed the hottest ambient.** A loop that can
   only add heat must reach the highest ambient it meets; with the ambient spanning roughly
   −60 °C to +20 °C the setpoint must sit above that band — up to ~80 K of lift. The lift, not
   the setpoint, is what the bank pays for (§D1: 55 K ≈ 0.55 W ⇒ 18 kJ/night ⇒ ≈1235 F vs the
   fitted 1.65 F).
2. **A control loop requires the MCU awake**, contradicting ADR-036's mandatory night
   deep-sleep (ADR-036: 1 mW × 10 h = 36 J is already "not feasible" with the fitted bank). Any
   *controlled* heater needs a sensor read + duty update at night.
3. **The loop controls the wrong node.** Sensor, heater, and crystal are separated by FR4, so
   there is a thermal gradient across the board: the loop regulates the *sensor's* temperature,
   not the *crystal's*. An NTC bonded at the XTAL (A2) measures the node that matters; a board
   heater under the module measures the board.
4. **The MS5611 conflict stands** (§D6): heating the board for the radio biases the pressure
   sensor and corrupts altitude telemetry.

### A4 — NEW CONSTRAINT: temperature-triggered recalibration (firmware requirement)

The chip itself says temperature moves the calibration state, so firmware owes a
temperature-triggered recalibration cycle:

- **§6.4 "Chip Auto Calibration"** (p.109), quoted: *"Image calibration is necessary if there
  is a frequency change > 10MHz, or a temperature change > 10°C."*
- **§6.4.1 "Calibrate"** (p.110): *"It is advised to perform the PLL and AAF calibrations again
  for an RF frequency change greater than 50MHz, or for a temperature change beyond +/-20C."*

A launch-to-float temperature swing (ground conditions → stratospheric ≈ −60 °C) far exceeds
10 °C — and exceeds the ±20 °C PLL/AAF guidance too. **Firmware requirement:** after the
transceiver has seen a temperature change **> 10 °C** (and again past **±20 °C**), issue
`Calibrate` (opcode `0x0122`; `blocks_to_calibrate` = AAF/PLL/MU as needed) and refresh the
image calibration **before the next flight-critical TX**. The trigger is available at runtime
from `GetTemp` (A1). Recorded as a sourced firmware requirement, not a suggestion.

### A5 — Characterised window: ±10 ppm over −20…+70 °C (the mission is outside it)

- `Table 3-24: 32MHz Crystal Specifications. (LR20xx) For example NDK_NX2016SA` (p.68, §3.5
  "Reference Oscillator Crystal Specification", p.68) lists **`FRTOLHF` "Crystal frequency
  accuracy"**, conditions **"Over temperature (−20 to 70 °C)"** → **±10 ppm** (the same table:
  Initial ±10 ppm; Aging over 10 years ±10 ppm).
- The same §3.5 gives `Table 3-25: TCXO Regulator Specifications (LR20xx)` — the supply side of
  the TCXO option.

The balloon mission's −60 °C is **outside** this characterised window. The two ways of dealing
with it are exactly the two hardware fixes in A2/D2: the **NTC / on-chip compensation loop** and
the **TCXO**. **Neither gives a guaranteed ppm figure outside −20…+70 °C** — the ±10 ppm number
is not valid there and this ADR does **not** claim one. Quantifying the residual at −60 °C is the
cold-sweep measurement already named in §D5.

Supporting ratings, for completeness: §3.1 `Table 3-1: Absolute Maximum Ratings` `Tmr`
= **−55…125 °C**; §3.2 `Table 3-2: Operating Range` `Top` (ambient) = **−40…85 °C**, `Tmaxj`
= **105 °C**. −60 °C is below both the operating-range minimum (−40 °C) and the absolute-maximum
minimum (−55 °C) — a second reason the cold end must be measured rather than assumed.

### A6 — The ESP32's on-die sensor is available and unused: log, don't tune

The MCU already carries a temperature sensor that firmware does not read. `git grep` on `master`
finds `CONFIG_SOC_TEMP_SENSOR_SUPPORTED=y` in every ESP-IDF `sdkconfig` (e.g.
`tracker/firmware/sdkconfig:15`, `firmware/esp32-c3-flrc/sdkconfig:15`), and
`docs/data-handover/HARMONIZATION-GAP-ANALYSIS.md` row **N4** (branch `docs/lr2021-lessons`)
records: *"C3: ESP32 `CONFIG_SOC_TEMP_SENSOR_SUPPORTED=y` in `sdkconfig` but no code
reads/emits it"*, closing *"None emit voltage or temperature."*

**Disposition: a free logging channel, not a control input.** The ESP32 die sensor is at the MCU,
not at the crystal, so it is the wrong node for closed-loop control (A3 point 3), but it is a
zero-cost telemetry field. Log it; do not tune on it. The LR2021 `GetTemp` source `0x02` (NTC)
is the node that matters once A2 is fitted.

## Pending pointer conflicts

Other workers are editing `docs/adr/006-*.md`, `036-*.md` and `037-*.md` concurrently to add
supersede/relationship pointers. This ADR does **not** edit those files. The manager will
need to resolve any duplicate or contradictory relationship lines at merge time.
