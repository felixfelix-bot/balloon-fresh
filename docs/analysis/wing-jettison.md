# Wing jettison by nylon string + nichrome cutter — engineering trade study

> **STATUS: CONSULTANT ANALYSIS — NOT A DECISION RECORD.**
> Nothing here is an operator decision, an accepted ADR, or an authorisation to change
> any board, BOM or flight procedure. Every number is either **COMPUTED** (formula shown,
> reproducible via `docs/analysis/wing_jettison_model.py`), **CITED** to an in-repo source,
> or marked **`TODO(unverified)`** naming the exact open question. No measurement was made
> for this analysis and no jettison hardware exists in this repository to measure.

| | |
|---|---|
| **Date** | 2026-10-07 |
| **Branch** | `analysis/wing-jettison` · **Worktree** `/home/c03rad0r/worktrees/bf-wingcut` |
| **Base** | `af9a672` (tip of `consolidation/v9` = the current main tip) |
| **Author** | subagent (Hermes), consultant |
| **Lens** | mechanical release + power + failure modes. Electrical topology of the wing is taken as given from ADR-006 / ADR-046 / ADR-047 / ADR-048 and is **not** re-derived. |
| **Out of scope** | no board edit, no schematic, no BOM, no ADR amendment. |
| **Read first** | `docs/adr/049-wing-architecture.md`, `docs/adr/046-wing-board-interface.md`, `docs/adr/047-v9-power-provisioning.md` |
| **Model** | `docs/analysis/wing_jettison_model.py` — run `python3 docs/analysis/wing_jettison_model.py`; every figure below is its own printed output. |

---

## 0. Answer first

**Recommendation: do not build it.** A nylon-string wing attachment with a nichrome
release has **no mission in this flight** and it is **mass-negative** on a vehicle where
mass is the binding constraint.

Three findings carry the recommendation, each developed below with its number:

1. **There is no trigger that gains anything.** Solar power *is* the science. Cutting the
   array before burst is mission suicide; cutting it at apex is mission suicide; the only
   defensible trigger is descent, and during descent the jettison buys **11 % of a descent
   rate that is already ~0.45 m/s (walking pace)** and removes only **5.4 % of the descent
   drag area** (§1, §7).
2. **The hardware costs more than it can ever shed.** Repo precedent for a cut-down
   channel is **~0.5 g per channel** (`docs/balloon-test-results.md` line 254: *MOSFET
   IRLML2502 + nichrome + nylon tether ≈ 0.5 g*). Four channels = **2.0 g carried all
   flight** to shed **3.2 g** on descent — and it adds **22 % of ADR-036's 100 µW night
   budget** in leakage alone (§3.5).
3. **The string makes the structure worse, not better.** A load-driven cord diameter is
   **0.02–0.10 mm** (§2) — unbuildable. Any cord you *can* knot is ~100× stronger than the
   load and cannot hold the wing **rigid** in its vertical plane, which is the arm's actual
   job. It also breaks the 4-pin soldered tab interface (ADR-046 §2.1), turning a defined
   structural+electrical joint into a knotted mechanical joint **plus** four flying leads
   per wing.

The cheapest correct move is **Option G — do nothing** (§5). If the operator's real worry
is the flimsy soldered tab, the right lever is the tab/socket joint itself
(ADR-046 §4.4; ADR-049 clause 4), not a cutter.

---

## 1. When would you actually cut? — every plausible trigger, evaluated honestly

Two facts frame the whole table:

- **The wings carry the flight's only power.** 12 cells, 4×3 in series, 6.0 V nominal /
  0.4 A (small cells) or 1.2 A (large cells) — the array *is* the mission
  (ADR-006; ADR-049 §Decision). Losing it is losing the flight.
- **The per-wing RF feed costs nothing to lose.** It is a **V2-only provision, not
  connected on v9** (ADR-046 §2.4; ADR-034 / ADR-040 put every v9 radio on the hub). So
  *every* row below can be read with "losing the wing RF feed" = **zero consequence**.
  That is worth stating plainly: half the operator's question is already moot.

A third fact decides the "partial" question:

- **Cutting ONE wing kills the WHOLE array, not 25 % of it.** The four wings are a single
  series string (`W1.SOLAR_N == W2.SOLAR_P`, … `W4.SOLAR_N → GND`, ADR-046 §2.3). Break any
  link and the string is **open** — the array delivers 0 W. The per-slot bypass Schottky
  that would keep the other three alive is **DNP for the first build** (ADR-046 §2.3;
  `docs/WING-TO-HUB-SOCKET-SPEC.md` §5). So "jettison wing 2 to lose 25 % of the array"
  is not a thing that exists in v9 as designed: it is 100 % loss.

| # | Trigger | Losing the solar array at that moment | Losing the wing RF feed | Consequence |
|---|---|---|---|---|
| 1 | **Before burst** | Fatal. No charging → the bank drains → no beacons → no flight. | Nothing (V2-only). | Mission ends at the cut. Strictly negative. |
| 2 | **During ascent, "array useless"** | The array is never *useless*. Vertical wings harvest from a wide azimuth even while tumbling (ADR-049 §Consequences 2). | Nothing. | Throwing away your only generator early. Negative. |
| 3 | **At apex / float** | Fatal for a solar-powered float. This is the phase the array exists for. | Nothing. | Mission ends. Strictly negative. |
| 4 | **During descent to reduce tumbling and drag** | *Little* — the bank alone covers the descent (16.63 J ÷ 1 mW beacon duty = **4.6 h**, §7) and there is no recharge. | Nothing. | Only defensible trigger. Benefit is **~nil** (§0, §7): −11 % descent rate, −5.4 % drag area, on a fall already at walking pace. |
| 5 | **On a timer** | A timer cannot tell ascent from float from descent; fired early it is row 1/2/3 = fatal. | Nothing. | Only safe if the timer is *started by burst detection* — which is just row 4 with extra failure modes. |
| 6 | **On command (uplink)** | Same as row 4 if used on descent; fatal if the command is mis-timed or spoofed/misheard. | Nothing. | Adds an uplink dependency and a command-authentication failure mode for a nil benefit. Acceptable only as a *backup* arm to row 4. |
| 7 | **On a fault** | A "fault" during float would fire it in the phase where it is fatal. | Nothing. | A release armed on a fault signal is an uncommanded-release mechanism. Negative. |

**Plain answer:** a jettison capability has **no value** for a flight whose science is
solar-powered, **except** as a **descent-only, post-burst action** — and even there the
value is effectively zero, because there is nothing left to protect and nothing to gain.

**What that implies for when the release may be armed.** If it were ever built, the
release *must not be armed* until burst is detected. Arming at launch would make rows 1–3
reachable by any single-point failure. The honest statement is that this converts the
design question from "add a cutter" into "add a burst detection that is correct enough to
hang a mission-ending actuator on" — a larger and riskier piece of work than the cutter.
`TODO(unverified)`: no burst-detection criterion is specified anywhere in this repository;
a candidate (sudden pressure drop + vertical-velocity reversal + loss of array current) is
offered here as an inference, not a cited design.

---

## 2. Load case and string sizing

All numbers from `docs/analysis/wing_jettison_model.py`; every assumption is named.

### 2.1 Assumptions

| Assumption | Value | Basis |
|---|---|---|
| Wing mass (small cells, spine+ribs — the **recommended** build) | **3.212 g** | CITED `docs/analysis/wing-mass-shape.md` §2.3 / §6 |
| Wing mass (large cells, spine) | **6.883 g** | CITED same, §3.5 |
| Arm tip radius r1 | **179.2 mm** | CITED same, §3.5 |
| Root radius r0 | 11 mm | CITED `docs/hardware-design.md` line 13 (22 mm hub) |
| One-arm frontal area | **43.14 cm²** (= 168.2 × 25.65 mm) | CITED same, §3.5 |
| Flat-plate C_d | 1.2 | CITED `wing-mass-shape.md` §2.3 |
| Ascent speed 5 m/s; ρ(20/25/30 km) | 0.0883 / 0.0400 / 0.0180 kg/m³ | CITED same, §2.3 |
| Descent under dead envelope | ~0.45 m/s (1 mph) | CITED `docs/balloon-flight-lessons.md` §Descent |
| Ground/handling gust | 15 m/s | **ASSUMPTION** (no in-repo figure) |
| Burst shock | **10 g-equivalent peak** | **ASSUMPTION** — `TODO(unverified)`, unmeasured |
| Nylon monofilament σ_ult | 500 MPa | `TODO(unverified)` — no datasheet in repo |
| Nylon density | 1.15 g/cm³ | physical constant |

### 2.2 The five load cases (formula shown, output quoted)

**Static, on the ground** — `F = m g`
```
F = 3.212e-3 kg × 9.81 m/s² = 0.0315 N = 3.21 g-f   (large-cell wing: 6.88 g-f)
```

**Rotation** — uniform-rod model, `F = (m/(r1−r0))·∫ω²r dr = m ω² (r1+r0)/2`, r_cm = 95.1 mm:
```
 1 rpm  → 0.0003 g-f      6 rpm → 0.012 g-f      30 rpm → 0.31 g-f
```
Even at a fast 30 rpm the centrifugal load is **0.31 g-f** — ~10 % of static. The vehicle
rotates slowly with no attitude control, so **rotation is not a sizing case**.

**Aerodynamic, ascent** — `F = ½ ρ v² C_d A`, v = 5 m/s, A = 43.14 cm²:
```
sea level 0.0793 N (8.08 g-f)   20 km 0.00571 N (0.58 g-f)
25 km     0.00259 N (0.26 g-f)  30 km 0.00116 N (0.12 g-f)
```
Cross-check against `wing-mass-shape.md` §2.3 (4-arm total, A = 174.9 cm²) reproduces the
document's own 0.02286 / 0.01035 / 0.00466 N — the model and the cited source agree.

**Aerodynamic, ground / launch gust — the real sizing case** (ρ = 1.225):
```
 v =  5 m/s → 0.0793 N =  8.08 g-f
 v = 10 m/s → 0.3171 N = 32.32 g-f
 v = 15 m/s → 0.7135 N = 72.73 g-f      ← DESIGN ENVELOPE
```

**Aerodynamic, descent** (v = 0.45 m/s): 0.000046 N at 20 km, 0.0000642 N at sea level —
below 0.07 g-f. Descent is aerodynamically **nothing**.

**Shock at burst.** No measurement exists (`TODO(unverified)`). The physics argues it is
*mild*: the envelope has negligible mass, the payload is not struck, it simply loses its
upward tension. The community-observed outcome is a gentle 0.45 m/s fall. This study
therefore **assumes 10 g-equivalent peak** (= 3× static + margin) rather than deriving a
shock that no source supports:
```
F_shock = 10 × 3.212e-3 × 9.81 = 0.315 N
```

**Design envelope: F_design = 0.7135 N (72.7 g-f), set by the 15 m/s ground gust — a
*ground handling* case, not a flight case.** That is the first thing the numbers say: the
joint never sees a flight load that matters.

### 2.3 Cord diameter — and the counter-intuitive result

```
d = sqrt( 4 F / (π σ_allow) ),   σ_allow = σ_ult / SF,   SF = 5 stated
σ_ult = 500 MPa  [TODO(unverified)]

static 1 g        F = 0.0315 N  →  d = 0.0200 mm
design envelope   F = 0.7135 N  →  d = 0.0953 mm
```

**The load-driven diameter is 0.02–0.10 mm — thinner than a human hair.** Such a thread
cannot be knotted, cannot be soldered, and does not survive handling. Therefore:

> **COUNTER-INTUITIVE RESULT #1 — the cord is not sized by the load, so the joint's
> strength is unknowable.** The diameter is set by *handling* (§2.3), which makes the weak
> link the **knot / loop termination**, not the cord. Replacing the soldered FR4 tab — a
> real load path (ADR-046 §4.4, `docs/hardware-design.md` line 162) — with a nylon loop
> trades a defined structural joint for a knotted one whose strength **nobody has measured**
> (`TODO(unverified)`). And a nylon loop **cannot hold the wing rigid**: it resists tension
> only, so a 179 mm vertical blade hanging on a string has no bending or torsional
> restraint against the 72.7 g-f gust that sets the envelope. Confirming this would take at
> least a triangulated tie (2–3 strings per wing), which multiplies the number of cuts.

Choosing the handlable **0.5 mm** cord instead:
```
A     = π/4 × 0.5² = 0.1963 mm²
F_break = 500e6 × 0.196e-6 = 98.2 N = 10.0 kg-f   → SF vs 1 g static = 3116×
mass    = 0.226 mg/mm  → a 30 mm loop = 6.8 mg; four loops = 27 mg
```
So the string contributes **27 mg** of mass and **10 kg-f** of strength — it fixes nothing
the flight needs and forces the joint to be re-engineered.

> **COUNTER-INTUITIVE RESULT #2 — the cord's thickness works *against* the cutter.** A cord
> too thin to handle (0.10 mm) cuts easily but cannot be built; a cord thick enough to
> handle (0.5 mm) is ~1000× stronger than needed and sets the cutter's energy. The two
> requirements pull in opposite directions and there is no diameter that satisfies both.

---

## 3. Nichrome cutter design (a concrete design, so the numbers are checkable)

This is a design given as a *straw man* to price the idea, not a proposal.

### 3.1 Cutting element

| Parameter | Value | Formula / basis |
|---|---|---|
| Wire | nichrome (NiCr 80/20), **0.127 mm** (36 AWG) | `TODO(unverified)` exact alloy |
| Length per cut point | 25 mm | assumption |
| Resistivity ρ_E | 1.10 × 10⁻⁶ Ω·m | `TODO(unverified)`, typical NiCr |
| Cross-section A | π/4 × (0.127e-3)² = 1.267 × 10⁻⁸ m² | arithmetic |
| **Resistance** | **R = ρ_E L / A** = 1.10e-6 × 0.025 / 1.267e-8 = **2.17 Ω** | |
| Wire mass | ρ·A·L = 8400 × 1.267e-8 × 0.025 = **2.66 mg** | |

### 3.2 Energy per cut

```
E_heat(wire) = m·cp·ΔT = 2.66e-6 kg × 460 J/(kg·K) × (400 − (−60)) K = 0.563 J
kerf volume  = π/4 × 0.5² × 0.5 mm³ = 0.098 mm³ → 0.113 mg nylon
E_melt(kerf) = m·(cp·ΔT + H_f) = 0.113e-6 × (1700×320 + 200e3) = 0.084 J
with a thermal-loss factor ×4 (convection/radiation to a −60 °C sky):
E_cut = 4 × (0.563 + 0.084) = 2.59 J per cut
```
Thermophysical constants (cp, H_f, wire setpoint, loss factor) are **`TODO(unverified)`** —
none is in this repository; they are order-of-magnitude and the result scales with them.

### 3.3 Voltage, current and the payload's actual rail — **ADR-047**

The rail available is the **raw supercap node `VSCAP`, ≈5.4 V at full charge** (ADR-047
§2.1: `VSCAP = raw supercap node, post-BAT54, pre-LDO`; `F33_VCC` is fed from it; the bank
is 2 × 3.3 F 2.7 V in series = **1.65 F @ 5.4 V**, doubled option 3.3 F). The logic rail is
the **TPS7A02 3.3 V** output (ADR-047 §2.1). Both were priced:

```
at 5.4 V (VSCAP):  I = 5.4/2.17 = 2.49 A   P = V²/R = 13.4 W   t = 2.59/13.4 = 193 ms
at 3.3 V (logic):  I = 3.3/2.17 = 1.52 A   P =          5.0 W   t = 2.59/5.0  = 516 ms
```
Use the **5.4 V node** — it delivers ~2.7× the power and a ~2.7× shorter pulse, so less heat
is lost to the surroundings.

### 3.4 Energy budget — affordable, and the SoC requirement

```
Usable bank energy = ½ C (V1² − V2²) = ½ × 1.65 × (5.4² − 3.0²) = 16.63 J   (matches ADR-047 §3.1)

1 cut  = 2.59 J = 15.6 % of usable
4 cuts = 10.35 J = 62.2 % of usable   (1.65 F bank)  /  31.1 % (3.3 F doubled bank)
charge drawn per cut = I·t = 0.479 C → bank sag ΔV = Q/C = 0.290 V (1.65 F) / 0.145 V (3.3 F)
```
**Energy verdict: the energy is affordable.** A single cut is ~16 % of the accepted bank's
usable energy and sags it 0.29 V. This is the *only* budget the idea passes.

**The supercap state of charge the cut requires.** The wire must reach ~400 °C against its
losses, i.e. `P = V²/R` must stay above a loss floor. With the assumed floor P_min = 5 W
(`TODO(unverified)` — the loss floor is neither measured nor citable):
```
V_min = sqrt(P_min · R) = sqrt(5.0 × 2.17) = 3.3 V  →  the raw bank node must be ABOVE ~3.3 V
```
On the raw-voltage criterion that is only ~9 % of the usable energy window — easy **if** the
bank happens to be charged. The trap is *when* the cut would fire:

> **The cut must be armed after burst AND while the bank is still above ~3.3 V.** If the
> balloon bursts at night, the bank is near its 3.0 V floor and **the cut silently fails**
> — which, per §4, is the benign failure, so the design degrades gracefully but does not
> work. If it bursts in daylight the bank is likely full *from the array you are about to
> throw away* — the mechanism needs its own victim to power its execution. That is the
> cleanest single sentence against the idea.

### 3.5 Switching element, control channel, shared bus

**MOSFET.** Repo precedent: **IRLML2502** — logic-level N-channel, SOT-23, **~0.02 g**
(`docs/balloon-test-results.md` line 254). Class rating V_ds 20 V (rail 5.4 V → 3.7×
margin), I_d ≈ 4.2 A at V_gs = 4.5 V. Required I_d = 2.49 A = **59 % of rating**. Adequate
for a *single* cut. `TODO(unverified)`: the IRLML2502 datasheet is not in the repository.

**One cut per wing (4 channels).** 4 × MOSFET + 4 × nichrome + 4 × loop. Gate drive: 4 GPIO
(or 1 GPIO + a 4-way driver). Required per-device I_d = 2.49 A — inside the class rating.
Sequencing matters: fires must not overlap or the bank sags 4× more.

**Shared bus (1 device, 4 wires in parallel) — rejected on rating.** All four nichrome
wires in parallel need `4 × 2.49 = 9.9 A` through **one** device — **2.4× the IRLML2502's
4.2 A rating** (§3.5 of the model). A shared *control* line over four separate MOSFETs is
fine and saves GPIOs; a shared *power* bus is not.

**Quiescent cost.** Leakage ~1 µA per device at V_gs = 0 (`TODO(unverified)`):
```
4 × 5.4 V × 1 µA = 21.6 µW = 22 % of ADR-036's 100 µW night anchor
```
The night budget is the quantity that decides whether the night log survives (ADR-036;
ADR-047 §6.1 repeats it). **Adding 22 % of it for a mechanism that fires once, on descent,
to no benefit, is the strongest single quantitative objection in this study.**

**Mass.** Repo figure **~0.5 g/channel** (`docs/balloon-test-results.md` line 254) →
**2.0 g for 4 channels** = **16 % of the entire 12.85 g wing array**, plus four nylon loops
(27 mg) and four cut points.

### 3.6 Plainly

- **Energy budget:** the payload **can** afford the cut (16 % of usable bank energy).
- **Supercap SoC for success:** the raw bank node must be **above ~3.3 V** at fire time;
  an unmeasurable assumption in the loss model, and unreachable after a night burst.
- **Mass budget:** the payload **cannot** afford the hardware — **2.0 g carried all flight
  to shed 3.2 g on descent.** On a mass-bound vehicle this is the wrong trade by a factor
  of ~0.6 already, before counting complexity, quiescent draw and failure modes.

---

## 4. Failure modes, ranked

Ranking key: **S** = severity (1 low – 5 mission-ending), **L** = likelihood, **R** = S×L.

| Rank | Failure mode | S | L | R | Is there a mitigation? |
|---|---|---|---|---|---|
| **1** | **Premature release** (fires before burst) | **5** | 3 | **15** | **None that is reliable.** Is it fatal? **YES** — and worse than "losing 25 %": cutting one wing **opens the series string and kills the entire array** (ADR-046 §2.3; the per-slot bypass that would save the other three is **DNP**). The only mitigation is *not arming until burst is detected*, which requires burst detection good enough to hang a mission-ending actuator on — a larger problem than the cutter. |
| **2** | **Partially cut loop** | **5** | 3 | **15** | **None.** A partly severed cord is a weakened knot that then fails at an uncontrolled time — which is failure mode #1 with a delay. There is no cut-state telemetry; a continuity wire could be added (another conductor, another fatigue point) but nothing in this design tells you the loop is compromised. Must be **accepted** if the mechanism is built. |
| **3** | **Released wing tangle** (strikes hub / suspension line / another wing) | 3 | 4 | **12** | **Partial only.** A released 168 × 26 mm FR4 blade with sharp edges falls past the hub, the suspension line and three remaining wings. A tether that retains it (a leash) means it is not released; letting it go means it can snag. Weighting the wing to fall clear is guesswork at −60 °C. **Largely accepted.** |
| **4** | **Cold embrittlement / vacuum behaviour of nylon** | 4 | 3 | **12** | **None specific to this design.** Nylon 6,6's T_g is ~50 °C dry but is strongly moisture-dependent; at −60 °C the material is deep in its glassy regime, and in **vacuum it outgasses and dries**, which *raises* T_g and brittleness. A knot is a stress concentrator on a brittle cord. Counter-evidence: the balloon envelope itself is **Nylon/PE laminate** (ADR-011 §4) and survives — but that is a laminated film in tension, **not** a knotted monofilament, so the precedent does not transfer. **`TODO(unverified)`: no in-repo test of knotted nylon at −60 °C / vacuum.** The risk is real and uninvestigated. |
| **5** | **Debris falling from altitude** | 1 | 5 | **5** | **Accept.** A ~3.2 g FR4+silicon blade has a low terminal velocity; pico-balloon payloads are far below regulatory mass/size limits (ADR-011; `docs/balloon-flight-lessons.md`). No mitigation needed, but it should be a conscious acceptance, not an oversight. |
| **6** | **Failure to release when commanded** | **1** | 4 | **4** | **Not needed.** Benign by construction: if the cut fails, you simply keep the wing and the mission is unchanged. This is the one failure the design tolerates well — and it is worth noting that the *safe* failure dominates the *bad* one, which is the only genuine virtue the mechanism has. |

**Ranked summary:** the two ways the mechanism can **hurt** (premature release, partial cut)
are both mission-ending and both unmitigable at this design maturity; the one way it can
**fail safely** is the one you can live with. A mechanism whose bad failures are
mission-ending and whose good failure is doing nothing is not a mechanism this vehicle
needs.

---

## 5. Alternatives, cheaper than nichrome

| Option | Mass | Complexity | Failure risk | Bench-testable? | Verdict |
|---|---|---|---|---|---|
| **A. Nichrome cutter + nylon string** (the proposal) | **2.0 g** + 27 mg string | High: 4 MOSFETs, 4 cut points, burst-arming logic, new firmware, 32 new electrical joints if the tab is replaced by flying leads | **Highest** — premature release is mission-ending; partial cut unmitigable | Partly: the cut is bench-testable, the *arming* is not | **Rejected.** Mass > shed, quiescent 22 % of night budget, worst failure profile. |
| **B. Mechanical interlock the operator undoes by hand** | ~0.1–0.3 g | Low | Low (a hand action, inspectable pre-launch) | **Yes** — fully | **Not a jettison.** It is the *opposite* of a release: a latch that keeps the wing in place. If the operator's true worry is the flimsy tab, this is the right *category* (a positive mechanical key), and it is already ADR-046 §4.2 Option A (the milled slot). |
| **C. Shear pin** | ~0.1 g | Low | **High and uncontrolled** — releases at a *load*, not at a *decision*. Sized above ascent/gust loads it would fire on the burst shock; sized above burst shock it may never fire | Yes (pull rig) | **Rejected.** It cannot distinguish "I want this off" from "it is being blown off". On a solar-powered flight that is the fatal ambiguity. |
| **D. Burn-wire on a heavier cord** | ≥ A (heavier cord ⇒ ≥ energy) | High | Same as A, plus the cord is now load-irrelevant and heavier | Yes | **Strictly worse than A.** No reason to choose it. |
| **E. Hinge + a single cutter (1 cut, not 4)** | ~1.0–1.5 g (hinge + 1 channel) | Medium | **Single point of failure releases everything at once**; the hinge is a new 179 mm-arm joint | Yes | **Rejected for this vehicle.** Saves 3 channels but concentrates the risk: one premature fire = total array loss (already the case, §1) *and* all four wings gone. |
| **F. A wing that simply folds** | 0 g electrical, some mechanical | Low electrical, medium mechanical | A passive fold can deploy/fold *at the wrong time* (ascent, float) with no command — same fatal outcome, no control | Partly | **Rejected** unless controlled, and controlling it is option A again. |
| **G. Do nothing** | **0 g** | **None** | **None new** | N/A | **RECOMMENDED.** See below. |

### Ranking (best → worst) against the stated criteria

1. **G — do nothing.** Zero mass, zero complexity, zero new failure modes, and it is the
   only option that cannot cost you the mission. Its "cost" is that the wing stays attached
   — which is exactly what a solar-powered flight wants.
2. **B — a positive mechanical key (the milled slot) that stays put.** If a structural fix
   is wanted at all, this is the right one: it fixes the *real* weakness (ADR-046 §4.4's
   fillet-only load path) instead of inventing a release nobody needs.
3. **E — hinge + one cutter.** Only if a release is mandated for some reason not in this
   repository.
4. **A — the proposal.** Mass-negative and mission-endangering.
5. **D — heavier-cord burn wire.** Strictly dominated by A.
6. **C / F — shear pin / passive fold.** Uncontrolled release. Worst.

### Recommendation

**Adopt G (do nothing) and, if the tab joint is the underlying worry, pursue B.** Concretely:

- **Do not add a release of any kind** to v9. The flight is solar-powered, the only
  defensible trigger is descent, and on descent the release buys −11 % of an already
  walking-pace fall rate (§7) for +2.0 g and 22 % of the night power budget.
- **Do not attach the wings with nylon string.** It breaks the 4-pin soldered tab interface
  (ADR-046 §2.1) — which on v9 is the wing's *only* electrical connection — and a string
  cannot hold a 179 mm vertical blade rigid, so it degrades the structure as well as the
  connection.
- **If the cantilever joint is the genuine concern**, spend the effort on ADR-046 §4.2
  Option A (the milled slot that keys the angle and captures the tab) and ADR-049 clause 4
  (the slot's fab-minimum fix), which address the load path that actually exists.
- If the operator nonetheless wants *optionality* recorded, the honest place for it is
  ADR-049's open item — as a **descent-only, armed-by-burst** provision — with the numbers
  above attached so the trade is visible. It is not recommended.

### Does the answer change for vertical blades vs a cylinder?

**No — the recommendation is the same, and for a cylinder the question largely dissolves.**
The comparison is asymmetric:

- **Vertical blades (the ADR-049 decision).** Four discrete 179 mm cantilever arms. This is
  the only geometry in which a *per-wing* release is even expressible — and it is the
  geometry where the release costs the most (4 channels, 4 cut points, 4 loops) and buys
  the least (§7).
- **Cylinder.** There are no discrete arms to shed: the array *is* the body. A release would
  mean dropping the entire solar surface — i.e. exactly the fatal case in §1 rows 1–3.
  A cylinder is also structurally the opposite of a cantilever (a continuous hoop, no long
  lever arm, no tab fillet carrying a 179 mm moment), so the structural motive for
  jettisoning (the flimsy tab) **does not exist either**. ADR-049's own open item notes a
  cylinder needs ~π× more cells for the same projected area — which makes losing it *worse*,
  not better.
- **Therefore:** for blades the answer is "no, don't build it"; for a cylinder it is "the
  question is moot". The recommendation does not flip.

---

## 6. Explicit open items (nothing silently assumed)

Every one of these is a number this study could not source and did **not** invent:

- `TODO(unverified)` — nylon monofilament σ_ult at −60 °C and after vacuum outgassing; no
  datasheet in repo. All §2 diameters scale as σ_ult^(−1/2).
- `TODO(unverified)` — the strength of the knot/loop termination (the actual weak link).
- `TODO(unverified)` — the actual peak shock at balloon burst. Assumed 10 g-equivalent.
- `TODO(unverified)` — nichrome alloy, its temperature coefficient, and the fusing current
  of 0.127 mm wire (~3–4 A assumed).
- `TODO(unverified)` — the thermal-loss factor and the wire's loss floor `P_min` (assumed
  5 W). The §3.4 SoC threshold is derived from it.
- `TODO(unverified)` — nylon cp, heat of fusion and melt temperature as used in §3.2.
- `TODO(unverified)` — payload total mass (brief: "tens of grams"; 50 g assumed in §7),
  envelope drag area (0.30 m² assumed) and the resulting absolute descent velocity
  (§7 takes the **ratio**, which is insensitive to these; the model's own absolute
  sea-level figure of 1.45 m/s disagrees with the cited ~0.45 m/s community figure, and
  that disagreement is **not** resolved here).
- `TODO(unverified)` — the IRLML2502 datasheet (leakage, ratings) is not in the repo; the
  class ratings used are commercial figures.
- `TODO(unverified)` — no burst-detection criterion exists in the repository.
- `TODO(unverified)` — whether a single string can hold a wing rigid enough at all; not
  analysed in any in-repo source (ADR-046 §7 item 8 records the same structural gap).

---

## 7. Descent arithmetic (why the only defensible trigger still buys nothing)

```
Terminal descent v = sqrt( 2 m g / (ρ C_d A) )
mass       50 g -> 37.2 g   (−26 %)          [m_total assumed]
drag area  0.3173 -> 0.3000 m²  (−5.4 %)     [envelope 0.30 m² assumed; wings 0.0173 m²]
v ratio    = sqrt((50−12.85)/50) × sqrt(0.3173/0.3000) = 0.886
→ shedding the whole array slows the descent by 11 %
```
Against a fall already at ~0.45 m/s and lasting 4–8 h (CITED
`docs/balloon-flight-lessons.md`), an 11 % change is nothing. And the array is not even
needed after burst:

```
bank 16.63 J ÷ 1 mW beacon duty = 16 632 s = 4.6 h   (≥ the descent duration)
bank 16.63 J ÷ 100 µW anchor   = 46.2 h
```

So: the descent does not need the array (bank covers it) — and does not benefit from
losing it. Both halves of the trade are near zero.

---

**Consultant's final line.** The proposal is well-motivated — the operator is trying to buy
margin on a mass-bound vehicle. The arithmetic says this particular margin is negative: the
hardware is 2 g against 3.2 g shed, it draws 22 % of the night budget while idle, the only
phase in which it may fire is the one phase where nothing is gained, and the string it
depends on weakens the structure it is attached to. **Recommendation: Option G — do
nothing**, and if a structural fix is wanted, fix the tab/socket joint (ADR-046 §4.2
Option A) rather than adding a release.
