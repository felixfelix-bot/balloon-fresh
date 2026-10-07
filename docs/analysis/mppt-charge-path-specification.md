# MPPT charge-path converter — specification, failure/operations analysis, bench test plan

> **STATUS: ENGINEERING SPECIFICATION SUPPORTING ADR-050 — NOT A DECISION RECORD.**
> This document carries the computed evidence behind `docs/adr/050-mppt-charge-path.md`. It is
> **not** an ADR and it does **not** amend ADR-006 / ADR-044 / ADR-046 / ADR-047 / ADR-048 /
> ADR-049. Nothing here authorises a BOM, schematic, placement or flight change. Every number is
> (a) **computed** with its formula shown, (b) **cited** to an in-repo document, (c) **read from
> a vendor page on 2026-10-07** (stated as such, with the reading instrument named), or (d)
> marked **`TODO(unverified)`** with the open question named. No measurement was performed for
> this document.
>
> **It does not duplicate the in-flight studies.** The wing geometry / insolation work
> (`analysis/wing-insolation`, `wing-omni`, `wing-ngon`; `docs/analysis/wing-insolation-geometry.md`),
> the progressive-shed ladder (`docs/analysis/wing-ladder.md`) and the single-cut whole-array
> jettison study (`analysis/wing-jettison`, `5365dac`) are **cited, not re-derived**.

| | |
|---|---|
| Date | 2026-10-07 |
| Branch | `feat/mppt-charge-path` · worktree `~/worktrees/bf-mppt` |
| Base | `0f98afb` (tip of `main` = tip of `github/main` at the time of writing) |
| Lens | charge-path power conversion, failure modes, receiver EMI, bench verification |
| Scope ruled out | no board code, no schematic edit, no BOM change, no wing redraw |
| Reads first | ADR-006 (Accepted), ADR-044, ADR-047, ADR-049, `docs/analysis/array-power-architecture.md`, `docs/analysis/wing-electrical.md` |

**Operator decisions taken as given** (ADR-050 §0): (1) the mission needs high TX duty but the
operator prefers degrading performance over losing the vehicle — shedding panels and running at
reduced throughput over time is **acceptable**; (2) the operator has **approved** a single MPPT
charge-path converter between the array and the supercap bank so that **any number of wings can be
cut off without breaking charging**.

---

## 0. The baseline being modified (cited, not re-derived)

| Quantity | Value | Source |
|---|---|---|
| Array | 4 wings × 3 cells in series = 12 cells | ADR-006 (Accepted); ADR-049 §Decision |
| Nominal MPP voltage | 0.50 V/cell → 1.5 V/wing, 6.0 V array | ADR-049 §Measured inputs; `wing-electrical` §0.1 |
| Peak array power (large cell) | 6.0 V × 1.2 A = **7.20 W** | ADR-049 §Decision; `wing-electrical` §3(a) |
| Large-cell current | 1.2 A (area-scaled) | `TODO(unverified)` — `wing-electrical` §0.2 (0.54 W listing implies 1.08 A; never reconciled) |
| Charge element | BAT54 Schottky, array → bank | ADR-006; ADR-047 §2.1 |
| Bank | 2× AVX SCC 3.3 F 2.7 V series = **1.65 F @ 5.4 V**, to be **doubled to 3.3 F** | ADR-006; ADR-047 §3 |
| Usable bank energy (doubled, 5.4 → 3.0 V) | **33.264 J** | ADR-047 §3.2 (`½·3.3·(5.4²−3.0²)`) |
| Radio maximum draw | 1118 mA @ 5.5 V = **6.1495 W** | ADR-047 §1.2 (F33 datasheet §8) |
| Radio mission average | **0.388 W** | `docs/POWER-BUDGET-V9-D2BE.md` §2 (via `array-power-architecture` §3.2) |
| Radio stated VCC max | **5.5 V** (no absolute-maximum table published) | ADR-044 §2; ADR-047 §7 |
| LDO | TPS7A02 3.3 V, I_Q = 25 nA | ADR-006 §LDO Regler |
| Night budget anchor | **100 µW** | ADR-036 (via ADR-047 §6.1) |
| Array open-circuit voltage, 12 cells @ −60 °C | **≈ 9.58 V** | `wing-electrical` §5.1, itself `TODO(unverified)` on the coefficients |
| Rail acceptance numbers | 2.4 GHz noise-floor rise **< 3 dB**; GNSS C/N0 drop **< 1 dB**; rail dip **< 20 mV** | ADR-029 §5 tests 1, 3, 4 (via ADR-044 §3 option (b)) |

---

# DELIVERABLE 2 — the specifications that will kill this design if they are wrong

## 2(a) INPUT RANGE

### 2(a).1 The array's input voltage, one to four wings (computed)

```
V_MPP,cell = 0.50 V nominal                        (CITED ADR-049 §Measured inputs)
V_MPP,wing = 3 cells × 0.50 V             = 1.50 V
V_MPP,n    = n × 1.50 V
```

| Wings connected | Cells | `V_in = n × 1.5 V` | Array peak (`n × 1.80 W`) |
|---:|---:|---:|---:|
| 1 | 3 | **1.50 V** | 1.80 W |
| 2 | 6 | **3.00 V** | 3.60 W |
| 3 | 9 | **4.50 V** | 5.40 W |
| 4 | 12 | **6.00 V** | 7.20 W |

**Stated range (as required by the brief): 1.50 V (one wing) to 6.00 V (four wings).**

### 2(a).2 The input maximum — and it is NOT 6.0 V (computed, cited)

`wing-electrical` §5.1 computes the cell open-circuit voltage at −60 °C and the array total:

```
V_OC,cell(−60 °C) = 0.62 V + (−2.1 mV/°C/cell)(−85 °C) = 0.7985 V
V_OC,array(−60 °C) = 12 × 0.7985 V                     = 9.5820 V  ≈ 9.58 V
V_OC,array(25 °C)  = 12 × 0.62 V                       = 7.4400 V
```

**A converter input capacitor with no load charges to the source's open-circuit voltage.** At
cold dawn (or whenever the bank is full and the converter stops switching) the unloaded input
capacitor therefore charges to **≈ 9.58 V**, which is **1.61 V higher than the type-plate number
6.0 V** — i.e. the array's own label understates its cold open-circuit output by a factor
`9.5820 / 6.00 = 1.60×` (+60 %).

### 2(a).3 Required input voltage rating, with margin

```
required V_in,rating ≥ V_OC,max × margin
                     = 9.5820 V × 1.25 = 11.98 V          (25 % margin)
→ specify V_in,rating ≥ 12 V ; prefer ≥ 16 V
```

The **25 % margin** is chosen to absorb the two `TODO(unverified)` inputs beneath the 9.58 V
figure (the assumed `V_OC(25 °C) = 0.62 V` and the assumed `−2.1 mV/°C/cell`). If those
coefficients are wrong by 10 % the number moves by ±0.96 V; a 12 V rating absorbs that; a 16 V
rating absorbs it comfortably. **Prefer ≥ 16 V** and state the rating on the schematic.

### 2(a).4 What happens to a converter rated only to 6 V — plainly

```
over-voltage factor = 9.5820 V / 6.00 V = 1.597×  → 60 % above rating
```

A converter whose input is rated 6 V has an absolute-maximum input of order 6.5–7 V (typical for
a 6 V-class switch). At **9.58 V** the input switch and/or the controller's VIN pin is driven
**~60 % past its rating**. The mechanism is not graceful: the input switch's drain-source or the
controller's supply goes into avalanche/breakdown, the die heats, and the part fails —
**short circuit is the common outcome for a MOSFET in avalanche**, which (see §3.2) then presents
the array's 9.58 V to the bank and radio. **A 6 V-rated converter does not "derate": it dies, and
its most likely death short-circuits the array into the bank.**

### 2(a).5 Does the regulated output REPLACE the mandatory shunt clamp? — **No. Stated explicitly.**

The short answer, because it changes the parts list: **the clamp is still required.** The
regulated output removes the array's *normal-operation* over-charge path to the bank, but it does
**not** remove the three paths that the ADR-044/ADR-047 clamp exists to cover:

| # | Path that survives the converter | Why the regulated output does not cover it |
|---|---|---|
| 1 | **The converter's own input node** | The clamp lives at the bank (post-converter). The **input** node still sees the array's full 9.58 V, and (2a.4) an input switch in avalanche tends to fail **short**. The input side needs its own rating (≥ 12–16 V) and, if the chosen part's rating is below ~12 V, its **own** limiter. |
| 2 | **Converter failure pass-through** | A shorted high-side switch, a shorted inductor, or a control loop that never closes presents the array's open-circuit voltage **directly to VSCAP**. Without a clamp, 9.58 V lands across a 5.4 V-rated cap string and a 5.5 V-stated radio whose damage threshold is unpublished (ADR-047 §7). |
| 3 | **Start-up / fault transient** | Before the regulation loop closes (cold start, a brownout recovery, an overload release) the output is not yet regulated; the array current flows into the bank node uncontrolled for the loop's settling time. |

**Consequence for the parts list:** the clamp **stays**, and may **multiply** (one at the
converter input if the part's rating is marginal, one at VSCAP as now). This is not a saving the
converter buys; the converter's output-regulation loop and the clamp do different jobs.
**Answer to the question asked: the regulated output does NOT replace the ADR-044/047 shunt
clamp.**

### 2(a).6 Input and output capacitance (computed / specified)

**Input capacitance.** The array is a current source; the input capacitor must not be allowed to
collapse at the switch edges, and it sets the MPPT sample time constant.

```
slew of the input cap under full array current:  dV/dt = I / C_in
  = 1.2 A / 22 µF = 54 545 V/s ≈ 54.5 mV/µs
specify C_in ≥ 22 µF  X7R/X5R,  rated ≥ 25 V  (≥ 2× the 12 V input spec)  + 100 nF HF
```

**A 22 µF cap at 1.2 A slews 54.5 mV/µs** — the input-regulation loop must be faster than that or
it will not hold a setpoint; this is a control-loop requirement to verify on the bench (§4). The
capacitor voltage rating (≥ 25 V) is set by the 9.58 V cold open-circuit with margin.

**Output capacitance.** The bank *is* the output capacitance (3.3 F once doubled), so the
converter needs only its own loop-stabilising capacitor plus a ripple filter at the point where
its output meets the radio's supply node:

```
C_out(local) = 100 µF low-ESR  + 100 nF HF        (CITED value: ADR-047 §4.3 C_BULK = 100 µF)
plus a ≥ 1.5 A-class ferrite between the converter output and the VSCAP/radio node
```

The ADR-044 §5 finding applies unchanged: a capacitor buffers, it does not set a rail; the bank
supplies the burst. The ferrite is a **new** line item, because `array-power-architecture` §5(c)
identifies **conducted ripple on VSCAP** as a real coupling path (VSCAP *is* the radio's VCC,
ADR-047 §2.1).

## 2(b) LOW-INPUT EFFICIENCY

### 2(b).1 Input current at low input voltage (computed)

```
P = V_in × I_in   →   I_in = P / V_in
```

| Case | Power | `V_in` | `I_in = P / V_in` |
|---|---:|---:|---:|
| Full 7.2 W (four-wing array) | 7.20 W | 1.50 V | **4.80 A** |
| Single wing | 1.80 W | 1.50 V | **1.20 A** |
| Full 7.2 W at the 6.0 V nominal | 7.20 W | 6.00 V | **1.20 A** |

**The same 7.2 W costs 4.8 A at 1.5 V against 1.2 A at 6.0 V — a 4× current.** The resistive
conduction loss scales as `I²R`, so for the *same transferred power* the low-voltage case carries

```
I²R loss ratio = (4.80 A / 1.20 A)² = 4² = 16×   more conduction loss at 1.5 V than at 6.0 V
```

This is the arithmetic behind the brief's phrase "increasing the input current by lowering
voltage losses": operating the array at 1.5 V rather than at its 6 V maximum-power point forces
four times the current through the same switches and the same inductor, for the same delivered
watts.

### 2(b).2 Efficiency achievable at 1.5 V vs 6.0 V — **`TODO(unverified)`**

**No efficiency figure is asserted.** No datasheet efficiency curve was read for a candidate
part, and no measurement exists. What can be stated without inventing a number:

- The **direction is certain**: efficiency at 1.5 V input is **lower** than at 6.0 V, for two
  sizeable reasons — (i) the 16× conduction-loss ratio above, and (ii) at `V_in = 1.5 V` a
  fixed switch/inductor voltage drop is a larger fraction of the input voltage, so the
  conversion ratio is worse before any switching loss is counted.
- The **magnitude is `TODO(unverified)`** and must come from §4's bench efficiency sweep.

> **`TODO(unverified)` — the converter's efficiency at 1.5 V and at 6.0 V input.** The value is
> not in this repository and no datasheet curve has been read. It decides the break-even
> (below), which is why ADR-050 records the break-even as *conditional on an assumed 85 %*.

### 2(b).3 The break-even, cited — and why efficiency is *not* the binding argument

CITED `docs/analysis/array-power-architecture.md` §5(b):

```
break-even bank voltage = P_mppt / I_MPP = 6.12 W / 1.2 A = 5.10 V
                        = 94.4 % of the 5.4 V bank top        (at the ASSUMED η = 85 %)
MPPT gain at a 3.0 V bank = +70.0 % ; at a 5.4 V (full) bank = −5.6 %
```

The finding, restated: **below 5.10 V of bank voltage the converter wins; above it the direct
connection wins** — and ADR-036's policy (daylight-only, energy-gated TX) deliberately keeps the
bank **near its top** during daylight. **On energy alone, at η = 85 %, this converter is not
justified for the nominal mission.** The 15 % conversion loss is paid all the time; the MPPT's
win is concentrated in the regime the design tries to avoid (deep discharge, or a lost wing).

**Which argument is binding — the record says so plainly.** The operator has chosen this
converter for **MISSION CONTINUITY under panel loss, not for efficiency.** The two arguments are
different and must not be blurred: the *efficiency* argument is **negative** at the bank's normal
operating point and does **not** justify the converter; the *continuity* argument is
**positive** and is the binding one. ADR-050 states this explicitly and does not sell the
converter on the MPPT energy gain.

### 2(b).4 Is a single wing worth connecting at all? — **threshold, and the honest answer is no**

Two independent reasons:

1. **No verified part runs at 1.5 V.** Every wide-input part read on 2026-10-07 has an input
   minimum of 2.42 V or higher (§2(d)); the parts that do reach 1.5 V top out at ~5.5 V input,
   which fails the 9.58 V requirement (§2(a)). So the 1.5 V case is **outside every verified
   candidate's window** — it is a part-selection gap, not a control choice.
2. **The efficiency at 1.5 V is `TODO(unverified)` and the loss ratio is 16×** (§2(b).1–2).

**Recommendation: the converter SHUTS DOWN below its own input floor and does not attempt to
charge from one wing.** Set the operating floor at **two wings (3.0 V)** with the verified
candidate (TPS63060's 2.5 V input minimum leaves only 0.5 V of margin) or at **three wings
(4.5 V)** for comfortable margin. State plainly, as asked: **a single wing is NOT worth
connecting** — the converter should shut down below the threshold rather than run a 4.8 A-class
input at an unmeasured efficiency.

Note what is *not* claimed: the single wing's 1.8 W would cover the 0.388 W mission average
**4.64× over** (`array-power-architecture` §3.2), so a single wing **would** be energetically
useful *if a part existed*; none does. That residual gap is recorded as an open item.

## 2(c) MPPT or NOT?

**True MPPT is NOT required. A plain converter with the part's own input-voltage-regulation
(fraction-of-Voc) loop is sufficient; a firmware hill-climb is NOT worth its parts or its
dithering loss.** The reasoning, against the two facts the brief supplies:

| Fact given | Consequence for the control scheme |
|---|---|
| The **load is a supercap bank that clamps the output** | The output voltage is not the thing being optimised; the bank holds the output near 5.4 V and the converter's job is to move charge into it. There is no output-side maximum to track. |
| The **input is a directly-irradiated array** | The input's maximum-power voltage moves with **temperature** (`−2.1 mV/°C/cell`, `wing-electrical` §5.1) and, to first order, far less with illumination (illumination moves current, not V_MPP). A **fixed hard setpoint** therefore drifts off MPP as the array cools; a **fraction-of-Voc sample** tracks it. |

**Sensing and control method (specified):**

- **Sensing:** a resistor divider from the converter input to the controller's input-voltage-sense
  / MPP pin. No current-sense resistor is required for the *fraction-of-Voc* scheme, because the
  controller samples Voc and sets the operating point to a fraction of it.
- **Control:** the controller's own input-voltage-regulation loop holds `V_in` at that fraction of
  the sampled Voc. The LTC3129-1 advertises exactly this class ("Programmable Maximum Power Point
  Control", §2(d)) — it is *constant-voltage* MPPT, not dithering MPPT.
- **What true MPPT would add in parts and quiescent draw:** a current-sense element (a shunt or
  the controller's internal sense), an ADC channel on the ESP32-S3, and a firmware
  perturb-and-observe loop whose dithering itself throws away energy (typically ~1–2 % as the
  operating point oscillates around the peak) — on a bank whose night budget is at the **100 µW**
  scale (ADR-036), any added always-on draw is the wrong trade.

**Verdict, stated plainly:** **MPPT is unnecessary; a plain converter is enough.** The
fraction-of-Voc input regulation is the free part of many harvest-capable controllers; if the
chosen part has no MPP pin, a fixed setpoint is acceptable but will run off-MPP at the cold end
(`TODO(unverified)`: the cold off-MPP loss is not computed and would be settled by the §4 bench
efficiency sweep at −60 °C and at +20 °C).

## 2(d) PART SELECTION

### 2(d).1 Candidates and their parameter tables (vendor pages read 2026-10-07)

Parameters below are **read from TI product-page parameter tables on 2026-10-07** (curl of
`ti.com/product/<partname>`, text extracted from the page). The ADI line is **vendor search-result
text quoting the LTC3129-1 datasheet feature list on 2026-10-07** — it is **not** a read of the
datasheet itself and is labelled as such.

| Class | Part | `V_in` min | `V_in` max | `V_out` | switch / output limit | `I_Q` typ | package | Verdict |
|---|---|---:|---:|---|---|---:|---|---|
| Boost-only, low Vin | **TPS61099** | 0.7 V | **5.5 V** | 1.8–5.5 V | 1 A switch limit | 0.8 / 1 µA | WSON-6 2×2 mm | Vin max **fails** 9.58 V; boost-only cannot pull 6.0 V in down to 5.4 V out |
| Boost-only, low Vin | **TPS61200** | 0.3 V | **5.5 V** | 1.8–5.5 V | 1.3 A switch limit | 50 µA | — | same two failures; I_Q too high |
| Harvest boost + MPPT | **BQ25570** | 0.6 V | **5.1 V** (abs max 5.5 V) | 2.2–5.5 V charge | **0.1 A charge current** | **488 nA** | VQFN-20 | Vin max fails 9.58 V; 0.1 A is **~15× below** the 7.2 W array (0.54 W at 5.4 V) → trickle only |
| Buck-boost, wide Vout | **TPS63020** | 1.8 V | **5.5 V** | 1.2–5.5 V | 4 A switch limit | 25 µA | — | Vin max **fails** 9.58 V |
| **Buck-boost, full current** | **TPS63060** | **2.5 V** | **12 V** | 2.5–8 V | 2.25 A switch limit | 30 µA | — | **best verified fit**: covers 3–4 wings and 9.58 V (1.25× margin). Vin min 2.5 V → **one wing (1.5 V) out of spec**; I_Q 30 µA over the night budget |
| Buck-boost, µA Iq + MPP pin | *LTC3129-1* (vendor-quoted, ≥2.42 V) | 2.42 V (1.92 V bootstrapped) | **15 V** | 1.4–15.75 V | **200 mA** in buck | **1.3 µA** | — | Vin max 15 V (**1.57×** margin), I_Q 7 µW, has **programmable MPP**. But **200 mA output is ~7× below** the ~1.5 A a 7.2 W charge path needs → cannot carry the array |

### 2(d).2 The finding that matters: there is a part-selection GAP

```
required input window    : 1.50 V  …  9.58 V   (6.4 : 1)
required output current  : ~1.5 A at 5.4 V for 7.2 W   (7.2 W / 5.4 V / 0.85 ≈ 1.57 A)

parts that reach 1.50 V  → all top out at 5.1–5.5 V input   (BQ25570, TPS61099, TPS61200)
parts that reach 9.58 V  → all start at 1.8–2.5 V input     (TPS63020/TPS63060/LTC3129-1)
```

**No single-IC converter read on 2026-10-07 covers 1.5–9.58 V input AND ~1.5 A output AND a night
budget quiescent draw.** This is the specification that would kill the design if the brief
assumed it were freely available. Two ways to satisfy the 1.5 V end:

1. **Two-stage.** A front-end **limiter/clamp** holds the input below the low-Vin part's 5.5 V
   maximum, and a harvest part (BQ25570-class) charges the bank — but the verified 0.1 A charge
   class delivers **0.54 W at 5.4 V**, ~13× below the 7.2 W array (so it is a trickle charger, not
   a charge path), and the front-end limiter must sink whatever the array makes above the clamp —
   up to **6.6 W at 5.5 V** (1.2 A × 5.5 V). Rejected for the main charge path.
2. **Accept a floor above one wing.** Use the **TPS63060** (buck-boost, 2.5–12 V, 2.25 A switch
   limit) and set the operating floor at **two wings (3.0 V)** — margin only 0.5 V — or three
   wings (4.5 V) for comfortable margin. **One wing does not charge.**

**Recommendation: option 2.** It converts the mission-ending case ("lose two wings") into a
surviving case ("lose two wings → charging continues"), which is precisely the operator's
mission-continuity requirement, even though the 1.5 V single-wing case is out of scope. Record the
single-wing gap as an open item.

### 2(d).3 Inductor and capacitor values the parts require

`TODO(unverified) — the exact values are set by the chosen part's datasheet design example, which
has not been read.` Order-of-magnitude starting points consistent with a 2.25 A-switch buck-boost
at 500 kHz–1 MHz and the currents of §2(b):

| Element | Starting value | Constraint |
|---|---|---|
| Inductor `L` | **4.7–10 µH**, saturation ≥ 3 A | must not saturate at the 2.25 A switch limit with headroom; **shielded** (see §2(e)) |
| Input cap `C_in` | **22 µF** X7R/X5R **≥ 25 V** + 100 nF | rating set by 9.58 V cold Voc (§2(a).3); slew 54.5 mV/µs (§2(a).6) |
| Output cap `C_out` | **100 µF** low-ESR + 100 nF | cited value (ADR-047 §4.3 C_BULK) |
| Output ferrite | **≥ 1.5 A**-class | conducted-ripple isolation between converter output and VSCAP (new line item, §2(e)) |
| Feedback / MPP divider | 2 resistors + 1 cap | sets the fraction-of-Voc setpoint (§2(c)) |

### 2(d).4 Mass estimate and part count

| Line | Mass | Basis |
|---|---:|---|
| Controller IC (VQFN-20 / WSON-6) | 0.02 g | ADR-044 §3 option (b) order, via `array-power-architecture` §5(b) |
| Shielded inductor 4.7–10 µH, ≥3 A | 0.20–0.50 g | ESTIMATE — `TODO(unverified)`, part not selected |
| `C_in` 22 µF ×2 + 100 nF | 0.10 g | ESTIMATE |
| `C_out` 100 µF + 100 nF | 0.10 g | ESTIMATE |
| Ferrite (≥1.5 A) | 0.05 g | ESTIMATE |
| Feedback/MPP divider | 0.01 g | ESTIMATE |
| Retained clamp (§2(a).5) | 0.05 g | ADR-044 §3 option (c): `< 0.1 g` |
| Extra PCB area (~150 mm² at 127.6 mg/cm²) | 0.19 g | ADR-049 rejected-options table (0.6 mm FR4 = 127.6 mg/cm²) |
| **Total** | **≈ 0.70–1.20 g** | consistent with ADR-044 §3 option (b) "order of 0.5–1.5 g" |

**Part count: 1 IC + 1 inductor + ~6 passives + 1 ferrite + 1 clamp + 1 BAT54 (or its replacement)
≈ 11 BOM lines, ONE active part.** On a 50 N payload on which mass is the binding constraint, this
is the number the operator must weigh against the mission-continuity benefit; it is not free.

## 2(e) EMI AND THE RECEIVER

### 2(e).1 Is the charge-path/radio-rail distinction real? — **partly, and it must be measured**

ADR-044 §3/§4 and ADR-047 §5 **refused a boost converter for the RADIO RAIL** because it would sit
**~2 mm from a −136 dBm receiver**. This converter is on the **charge path**. The distinction is
real where it exists and false where it does not:

| | Real | Not real |
|---|---|---|
| **Placement** | A charge-path converter is not obliged to sit at the module's pin 1; its switched loop can be laid out at the array/hub edge. | The v9 flight board is **55.15 × 45.15 mm** (ADR-029, via `POWER-BUDGET` §4). "At the hub" is still centimetre-scale, not far. |
| **Coupling mechanism** | The radio-rail boost's dominant worry is **radiated** field into the co-located LNA. | The charge-path converter's output node **IS the radio's supply**: ADR-047 §2.1 makes VSCAP the F33's VCC. So **conducted ripple on VSCAP** is a real coupling path the two converters share. |
| **Filterability** | A conducted path is filterable (the bank is a low-impedance node; a ferrite/LC at the output is possible) in a way a 2 mm radiated path is not. | The third re-freeze (ADR-032 simulation of switcher harmonics; ADR-029 §5 tests 1 and 3 as acceptance numbers) applies **either way**. |

**Coupling paths, named:** (1) **conducted** — switched ripple on VSCAP, which directly modulates
the F33's VCC; (2) **radiated** — the switched loop's magnetic field into the 2.4 GHz
(`ANT-2G4`/SX1280) front end and the GNSS L1 feed; (3) **common-mode/ground-bounce** — the
switching return current sharing the radio's ground.

### 2(e).2 Switching frequency — chosen, and why

**Choose f_sw in the range 500 kHz – 1 MHz, with spread-spectrum/frequency dithering if the part
offers it.**

Reasoning:

- The fundamental and its low harmonics sit **far below** both the 433 MHz TX band and the 2.4 GHz
  RX band; what couples is the switching **edge** spectrum and PDN resonances, not the fundamental.
  Keeping f_sw high enough that the first few harmonics stay below ~30 MHz keeps them away from the
  board's own structures that could resonate at 433/2400 MHz.
- A **higher** f_sw shrinks `L` and `C` and therefore **mass**, which is the binding constraint.
  That is the reason not to drop to ~100 kHz.
- **Spread spectrum** smears the edge energy across a band, lowering the peak spectral line that
  would reach the receiver — this is the single most effective cheap mitigation.

### 2(e).3 Mitigation specified

| Mitigation | Why |
|---|---|
| **Shielded inductor**, winding axis oriented **parallel to the array plane** and **≥ 15 mm** from the 2.4 GHz feed | keeps the switched magnetic field out of the antenna plane; orientation and distance are the two knobs `array-power-architecture` §5(c) names |
| **Input and output LC/ferrite filtering** (the ≥1.5 A ferrite of §2(d).3 plus caps) | attenuates **conducted** ripple on VSCAP — the coupling path that *is* shared with the radio rail |
| **RC snubber** across the switch node | slows the edge `dv/dt`, which is what radiates; costs a little efficiency |
| **Tight switched loop** with a local ground plane; converter placed at the hub edge | minimises loop area, hence the radiated H-field |
| **Retained shunt clamp + a series fuse/PTC** on the bank-to-converter path | failure containment, not EMI — see §3 |

### 2(e).4 The bench test that settles it — **this cannot be resolved on paper**

**Run the receiver in RX at the mission's sensitivity floor with the converter switching at its
worst-case duty, and measure the three acceptance numbers ADR-029 §5 already defines:**

1. **2.4 GHz noise-floor rise < 3 dB** (ADR-029 §5 test 1).
2. **GNSS C/N0 drop < 1 dB** (ADR-029 §5 test 3).
3. **Conducted ripple on VSCAP < 20 mV** (ADR-029 §5 test 4).

Plus a **near-field H-probe scan 30 MHz – 3 GHz** over the board to locate the dominant emitter.
**Until these are measured, the EMI verdict is `TODO(unverified)` and the converter must not be
declared EMI-clean or EMI-fatal.** This is the honest position: an EMI judgement on this part, at
this distance, on this board, is a measurement, not a derivation.

---

# DELIVERABLE 3 — failure-mode and operations analysis

## 3.1 Converter failure: OPEN

**Failure open** (an input or output switch open, an inductor open, a control loop that never
starts): **no charge current.** The array is disconnected from the bank.

- **No damage.** The bank is untouched; the radio is unaffected.
- **Behaviour:** the bank drains at `I_Q + load`. With **33.264 J** usable and the **0.388 W**
  mission average, that is `33.264 / 0.388 = 85.7 s` of average duty; with the 6.15 W burst it is
  `33.264 / 6.1495 = 5.41 s` (ADR-047 §3.2). The vehicle then goes dark on the power side —
  **survivable and diagnosable, not destructive.**
- **Mitigation:** none electrical. Telemetry must flag "no charge current" so the operator sees
  the degraded state.

## 3.2 Converter failure: SHORTED

Two distinct shorts, and the difference matters:

**(i) Input→output short (pass-through).** A shorted high-side switch or a shorted inductor
presents the array's **open-circuit voltage (up to 9.58 V)** directly to the bank and the radio.

```
bank (and radio VCC) forced to the array's Voc, which can reach 9.5820 V
  vs bank rating      5.40 V   → 9.5820 / 5.40  = 1.77× over the cap-string rating
  vs radio stated max 5.50 V   → 9.5820 / 5.50  = 1.74× over the radio's stated maximum
```

This is the **reason the shunt clamp stays** (§2(a).5). With the clamp fitted, the excess current
is shunted and held down; **without it**, the 2×2.7 V cap string is driven 77 % above rating (a
supercapacitor over-voltage failure mode) and the radio is driven 74 % above its stated maximum
into a damage threshold that **is not published** (ADR-047 §7). **`TODO(unverified)`: the F33's
actual damage threshold.** Recommend a **series fuse/PTC** in the bank-to-converter path as well,
so a pass-through short is not indefinite.

**(ii) Output→GND short.** The bank discharges through the short:

```
E_bank = 33.264 J  dumped in seconds  (τ = R_short × C = e.g. 0.1 Ω × 3.3 F = 0.33 s)
```

The shorted device and the copper take the heat; the array is also short-circuited through the
converter. **Mitigation:** the series fuse/PTC above, and a current-limited converter (most have
cycle-by-cycle current limit).

## 3.3 Losing panels one at a time — down to one wing, then zero

**With the converter (floor at two wings / 3.0 V), the ladder is graceful:**

| Wings left | `V_in` | Array peak | ÷ mission average 0.388 W | Bank chargeable to | Consequence |
|---:|---:|---:|---:|---:|---|
| 4 | 6.00 V | 7.20 W | 18.6× | 5.40 V (design top) | design case |
| 3 | 4.50 V | 5.40 W | 13.9× | 5.40 V | continues, full TX power available |
| 2 | 3.00 V | 3.60 W | 9.3× | 5.40 V (0.5 V margin over the part floor) | continues, full TX power available |
| **1** | **1.50 V** | 1.80 W | 4.6× | **not chargeable** — below every verified part's floor | **bank-only: 85.7 s of average duty, or 5.41 s of 6.15 W burst** |
| **0** | 0 | 0 W | — | not chargeable | bank-only, then dark |

**Contrast with the accepted direct-connected design** (`array-power-architecture` §3.2, §7):

| Wings left | Direct-connected bank ceiling | Mission |
|---:|---:|---|
| 3 | 4.20 V | continues at **−1.56 dB** TX ("mission continues") |
| 2 | **2.70 V** — below the radio's 3.0 V minimum and the LDO's input | **mission over** |

**The mission-continuity win, stated exactly:** the converter converts *"losing two wings ends the
mission"* into *"losing two wings still charges the bank to 5.4 V"*, and converts *"losing three
wings ends the mission"* into *"losing three wings still charges the bank to 5.4 V and the
mission continues"*. With one wing or zero, the vehicle degrades to the **bank-only** budget
above and then goes dark — **but it does not lose the vehicle, and it does not fail on a single
cut.** This is precisely the failure mode the operator chose the converter to remove, and it is
what makes the converter's negative efficiency argument (§2(b).3) acceptable.

## 3.4 Can the cut be powered from the bank through the converter's output?

**Yes — and that is the correct wiring.** The converter's output node **is** the bank node (both
sit at VSCAP), so a cut channel fed from that node is fed from the bank. Consequences, all
favourable:

- The cut works **at night and at zero sun**, because the bank, not the array, is the source.
- The cut works **even if the converter has failed open** (§3.1), because it does not depend on the
  converter running.
- The cut must **not** be wired to the converter's input (array) side, because the array is dead at
  night and because the input can be at 9.58 V.

**Recommended wiring:** bank node (VSCAP) → firmware-gated MOSFET (the repo's cut channel,
`docs/balloon-test-results.md` line 253) → nichrome → the tether. Note the cut channel's own
quiescent draw (zero when off, but the MOSFET's leakage and the gate-drive bias are non-zero) must
join the night budget of §2's quiescent accounting.

## 3.5 How many joules a cut costs — and how many cuts the vehicle can afford

**Model (formula shown; the input values are `TODO(unverified)`):**

```
E_cut = V_cut × I_cut × t_cut            (the cut is a resistive nichrome load on the bank)
cuts affordable = floor( E_usable / E_cut ) ,   E_usable = 33.264 J   (ADR-047 §3.2)
```

| `V_cut` | `I_cut` | `t_cut` | `E_cut` | cuts on 33.264 J |
|---:|---:|---:|---:|---:|
| 5.4 V | 1.0 A | 3 s | **16.2 J** | **2** |
| 5.4 V | 1.0 A | 1 s | 5.4 J | 6 |
| 3.3 V | 1.0 A | 3 s | **9.9 J** | **3** |
| 3.3 V | 1.0 A | 1 s | 3.3 J | **10** |
| 3.3 V | 0.5 A | 2 s | 3.3 J | **10** |
| 3.3 V | 0.5 A | 1 s | 1.65 J | 20 |

**The striking result, stated plainly: at a 5.4 V × 1 A × 3 s cut, one cut costs 16.2 J — 49 % of
the vehicle's entire usable bank — and the vehicle can afford only TWO.** This is because a cut is
a *resistive heater* held on for seconds, not a logic pulse. In TX terms:

```
one cut at 16.2 J = 16.2 / 0.615 = 26 sub-GHz TX slots    (6.15 W × 0.1 s = 0.615 J per slot)
one cut at  3.3 J =  3.3 / 0.615 =  5.4 sub-GHz TX slots
```

**Recommended cut-energy budget: ≤ 10 % of the usable bank = ≤ 3.33 J per cut.** Grounds: (i) at
≤ 3.33 J the vehicle affords ~10 cuts, which covers any plausible shedding sequence with margin;
(ii) 3.33 J leaves ≥ 30 J for the mission's TX; (iii) 3.33 J ≈ **5.4 TX slots**, a tolerable
one-off cost. Enforce it with a **firmware maximum on-time** on the cut channel and **verify the
actual energy on the bench** (§4.6). If the measured cut energy cannot be brought under 3.33 J
(e.g. the tether is too thick or the nichrome too low-resistance), the fix is a **mechanical/spring
release** triggered by a small actuator rather than a longer nichrome burn — a change that would
re-open the cut-mechanism trade (and it belongs to the in-flight jettison study, which is
**cited, not duplicated** here).

---

# DELIVERABLE 4 — bench test plan (this cannot be validated on paper)

**Every measurement below must be taken before this converter is trusted.** Unless otherwise
stated, the DUT is one converter assembly with the specified `L`, `C_in`, `C_out` and ferrite, on a
representative board or a breakout, in a shielded enclosure for the emissions tests.

| # | Measurement | Instrument | Setup | Pass criterion |
|---:|---|---|---|---|
| 4.1 | **Efficiency at 6.0 V input** | 4-wire DC power analyser (e.g. Yokogawa WT310 class) or two calibrated DMMs + a current shunt | array simulated by a DC supply (with a series resistor to emulate a PV source if wanted); output into a fixed 5.4 V load / the bank | **η ≥ 85 %** — the break-even target of `array-power-architecture` §5(b). Below 85 % the break-even bank voltage falls below 5.10 V and the converter's energy case weakens. |
| 4.2 | **Efficiency at 1.5 V input** | as 4.1, with a supply capable of **≥ 5 A at 1.5 V** | same, `V_in = 1.5 V` | **No fixed threshold yet — this number sets the threshold.** Record it. Decision rule: if `η(1.5 V) × 1.8 W` is not ≥ 2× the converter's own quiescent draw, one-wing operation is refused (§2(b).4). |
| 4.3 | **Efficiency at 3.0 V input** (the recommended floor) | as 4.1 | `V_in = 3.0 V` | Record; this is the number that decides whether the two-wing floor is worth it. |
| 4.4 | **Quiescent draw** | picoammeter / 6.5-digit DMM (e.g. Keysight 34465A) | converter enabled, no load, `V_in` = 0 and `V_out` = 5.4 V (bank side); then disabled | **I_Q ≤ 5 µA drawn from the bank at 5.4 V (≤ 27 µW = 27 % of the ADR-036 100 µW night anchor); target ≤ 2 µA (≤ 10.8 µW).** A part that draws 30 µA (162 µW, 162 % of the anchor) **fails** unless firmware disables it at night, and the disabled-state leakage must then be measured and pass the same bound. |
| 4.5 | **Maximum input voltage the part actually survives** | programmable DC supply, current-limited; scope on `V_in` | **destructive-adjacent — use a spare part.** Step `V_in` from 6.0 V upward in 1 V steps, dwell, record input current and function; continue to failure | **Survives ≥ 12 V with no damage and full function afterwards** (9.58 V × 1.25, §2(a).3). Record the actual survival voltage. A part that fails below 12 V is rejected. |
| 4.6 | **Cut energy** | scope + current shunt across the cut channel | nichrome/tether in a **cold chamber at the intended temperature**; fire one cut at the firmware's maximum on-time | **E_cut ≤ 3.33 J** = 10 % of the 33.264 J bank (§3.5). If over, reduce on-time/current or change the mechanism. |
| 4.7 | **Conducted emissions on VSCAP** | scope with AC-coupled probe or a LISN-style pickoff | converter at worst-case duty, RX idle | **Conducted ripple on VSCAP < 20 mV** (ADR-029 §5 test 4). |
| 4.8 | **Radiated emissions into the receiver** | spectrum analyser + calibrated antenna (near-field H-probe for localisation) | **the radio in RX at the mission's sensitivity floor**, converter at worst-case duty | **2.4 GHz noise-floor rise < 3 dB** (ADR-029 §5 test 1) **and GNSS C/N0 drop < 1 dB** (test 3). |
| 4.9 | **Cold start and cold efficiency** | cold chamber + the 4.1 setup | soak DUT and `L`/`C` to −60 °C; power from the simulated array; start and charge | **Starts and charges at −60 °C**; record η. (Capacitor dielectric and inductor core behaviour at −60 °C is the risk; an electrolytic output cap would be disqualified.) |
| 4.10 | **Input-regulation (MPP) setpoint accuracy and cold drift** | 4.1 setup at −60 °C and +20 °C | hold the array simulator's `V_OC` at the cold and warm values; observe the regulated input voltage | The chosen setpoint must sit **between ~0.7 and ~0.85 × Voc** at both temperatures; if a fixed setpoint drifts outside that at −60 °C, the fraction-of-Voc sample is required (§2(c)). |

**Order of operations:** 4.5 (survival) is a gate on the part and can be done first; 4.1–4.3 and
4.9 set the efficiency basis; 4.4 sets the night budget; 4.7–4.8 are the EMI gate and are the ones
that cannot be answered on paper; 4.6 sets the cut budget; 4.10 closes the control-scheme choice.

---

# Open items — every `TODO(unverified)`, gathered

1. **The converter's efficiency at 1.5 V and at 6.0 V** (§2(b).2) — no datasheet curve read, no
   measurement. Sets the break-even, which ADR-050 records as conditional on an assumed 85 %.
2. **A part that covers 1.5–9.58 V input at ~1.5 A output with a night-budget quiescent draw**
   (§2(d).2) — none was found on 2026-10-07. The 1.5 V single-wing case is out of scope until one
   is found or a two-stage design is accepted.
3. **The array's −60 °C open-circuit voltage** — cited as 9.58 V from `wing-electrical` §5.1, but
   the two coefficients beneath it (`V_OC(25 °C) = 0.62 V`, `−2.1 mV/°C/cell`) are themselves
   unverified. Every input-rating number scales with them.
4. **The F33's actual damage threshold** (ADR-047 §7) — unpublished in datasheet Rev 1.1, so the
   retained clamp's set point is still not closable.
5. **The chosen part's datasheet design example** — the `L`, `C_in`, `C_out` values in §2(d).3 are
   order-of-magnitude starting points, not the converted design values.
6. **The EMI verdict** (§2(e).4) — unmeasured; the bench plan (4.7–4.8) is the only route.
7. **The cut channel's real energy and its off-state leakage** (§3.4, §3.5, 4.6) — the 0.5 g
   hardware is repo-cited (`docs/balloon-test-results.md` line 253) but the electrical energy is
   not in the repository.
8. **The large cell's maximum-power current** (1.2 A by area vs 1.08 A by the 0.54 W listing;
   `wing-electrical` §0.2) — every array-power and input-current number here scales linearly.
9. **The supercap cell ESR and its −60 °C behaviour** — ADR-047 §3/§4 open items; the converter's
   output loop stability depends on the bank's ESR, which is unverified.
10. **In-flight studies cited, not duplicated:** the wing geometry/insolation work, the
    progressive-shed ladder (`docs/analysis/wing-ladder.md`), and the single-cut whole-array
    jettison study (`analysis/wing-jettison`, `5365dac`).

# Sources cited

- `docs/adr/006-supercapacitor-power.md` (**Accepted**) — 12-cell series array, 6.0 V, BAT54,
  1.65 F @ 5.4 V bank, TPS7A02, the direct-connection architecture this converter modifies.
- `docs/adr/029-dual-band-flight-board.md` — board 55.15 × 45.15 mm; §5 tests 1–4 acceptance numbers.
- `docs/adr/036-energy-policy-burst-storage-daylight-only-tx.md` — burst storage, daylight-only TX, 100 µW anchor.
- `docs/adr/044-v9-power-rails.md` — option (b) boost refused for the radio rail; option (c) clamp; 0.5–1.5 g converter mass order.
- `docs/adr/047-v9-power-provisioning.md` — 6.15 W, VSCAP = radio VCC, bank 1.65 F/3.3 F, 33.264 J, clamp required insurance, over-voltage path.
- `docs/adr/049-wing-architecture.md` — large cell class, 12 cells, 7.2 W; bypass re-rate; clamp required.
- `docs/analysis/array-power-architecture.md` — break-even 5.10 V at assumed 85 %; the peak/average 15.85×; the converter option (a)–(d); the EMI distinction.
- `docs/analysis/wing-electrical.md` — cell data; `n = 12`; cold Voc 9.58 V; clamp sizing.
- `docs/analysis/wing-ladder.md` — the 0.5 g cut channel precedent, series-open on a cut (cited, not duplicated).
- `docs/balloon-test-results.md` line 253 — per-channel cut hardware (MOSFET + nichrome + nylon ≈ 0.5 g).
- `docs/POWER-BUDGET-V9-D2BE.md` §2 — 0.388 W representative average, 1 % TX duty.
- Vendor parameter tables read 2026-10-07 via curl of `ti.com/product/{TPS61099,TPS61200,TPS63020,TPS63060,BQ25570}` (text-extracted product-page parameter tables).
- Vendor search-result text quoting the **LTC3129-1** datasheet feature list, read 2026-10-07 (not a read of the datasheet itself).
