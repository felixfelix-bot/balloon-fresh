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
   synthesizer, using a temperature reading from an on-board sensor or from the last known
   soak temperature if no runtime sensor exists.
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

## Pending pointer conflicts

Other workers are editing `docs/adr/006-*.md`, `036-*.md` and `037-*.md` concurrently to add
supersede/relationship pointers. This ADR does **not** edit those files. The manager will
need to resolve any duplicate or contradictory relationship lines at merge time.
