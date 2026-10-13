# Wing progressive-shed ladder (hanging boards on nylon thread) — engineering trade study

> ## STATUS: CONSULTANT ANALYSIS — NOT A DECISION RECORD.
> Nothing here is an operator decision, an accepted ADR, or an authorisation to change any
> board, schematic, BOM, firmware or flight procedure. Every number is either **COMPUTED**
> (formula shown, reproducible via `docs/analysis/wing_ladder_model.py`), **CITED** to an
> in-repo source, or marked **`TODO(unverified)`** naming the exact open question. No
> measurement was performed for this analysis, and the repo contains **no release or
> actuator hardware of any kind** to measure (no MOSFET, nichrome, actuator or cut-down part
> exists anywhere in `tracker/`).

| | |
|---|---|
| **Date** | 2026-10-07 |
| **Branch** | `analysis/wing-ladder` · **Worktree** `/home/c03rad0r/worktrees/bf-wingladder` |
| **Base** | `af9a672` (the current main tip; cut with `git worktree add … af9a672`) |
| **Author** | subagent (Hermes), consultant |
| **Model** | `docs/analysis/wing_ladder_model.py` — every figure below is its own printed output |
| **Read first** | `docs/adr/049-wing-architecture.md`, `docs/adr/046-wing-board-interface.md`, `docs/adr/047-v9-power-provisioning.md`, and the four `docs/analysis/wing-*.md` files |

## 0. The scheme being evaluated, and the answer

**The operator's proposal, quoted:**

> "make multiple wing boards hanging from each other by a nylon thread; if weight is an
> issue, drop the lowest wing board and keep the ones above; then drop the next one if
> weight continues to be an issue, and so on; and put the MOSFET for cutting off wing boards
> at the place where the next wing board that hangs underneath is connected."

**Answer, up front: the progressive ladder does not earn its complexity. `REJECT`.**

Five findings carry the recommendation, each developed with its number below:

1. **The mass it can shed is at most 3.21 g per cut, and the FIRST cut costs the whole
   array.** Because the four wings are one **series string** (ADR-046 §2.3), physically
   removing one wing **opens the circuit**: the array goes from 7.2 W to **0 W**, not to
   5.4 W (§3). To get back to 5.4 W you must fit a bypass across the removed wing — which
   is *already* the `D_BP` provision ADR-046 specifies as DNP. The "ladder" is therefore
   not a ladder at all: cut one and you have a 3-wing array whose power is **below the
   radio's 6.15 W maximum draw** and whose charge ceiling has dropped from 5.4 V to 4.2 V
   (§2). There is no second useful cut.
2. **Shedding mass cannot lower the float altitude** — it either does nothing (vented
   zero-pressure balloon) or makes the vehicle **climb** (superpressure balloon). The 3.21 g
   saving moves the equilibrium altitude **up by ≈ 685 m**, i.e. toward the burst margin
   (§1). It is a hazard, not a remedy.
3. **The descent-rate change is in the noise**: −5.3 % (spine wing) to −12.0 % (full
   carrier), i.e. 0.447 → 0.423 / 0.394 m/s, adding 25 or 61 minutes to a 7.5-hour fall
   (§1). Descent is already at walking pace (Ruthroff: "~1 mile per hour",
   `docs/balloon-flight-lessons.md` line 472).
4. **The hardware costs more than it can ever save** in the never-cut case, and it adds
   mass exactly where it is trying to save it: **≈ 0.87 g per junction** (§5), against a
   0.5 g repo precedent for the cut channel alone (`docs/balloon-test-results.md` line 253).
5. **A hanging chain is a compound pendulum** with a shading penalty, a guaranteed
   collision path for the falling board, and a *stack of new failure modes* on a vehicle
   that currently has none (§4, §5).

**Recommendation: (d) — do not carry the mass in the first place.** The ADR-049 spine-and-ribs
wing already removes **16.35 g** from the four-wing array (29.20 g → 12.85 g) **before
launch**, with zero strings, zero actuators, zero cut risk and zero new failure modes. That
is **1.27×** the mass of the *entire* four-wing array the ladder would aspire to shed (§6).
If the operator's worry is free lift at launch, the correct lever is **gas fill**, not
shedding: free lift is set on the ground by how much helium goes in (target 5–7 g,
`docs/balloon-flight-lessons.md` §Success Factor #5).

**Relationship to the parallel analysis.** A separate consultant is analysing a **single
cut that releases the whole array** (`analysis/wing-jettison`, commit `5365dac7`, in flight
at the time of writing). This document does **not** duplicate it; where its result is used
it is cited as *in-flight, not assumed*. That analysis also recommends doing nothing
(its Option G).

---

## 1. THE MASS ECONOMICS — settled first

### 1.1 What is actually shed, and how much that is

**CITED** wing masses, small-cell build (`docs/analysis/wing-mass-shape.md` §1.4):

| Build | Wing mass | 4-wing array |
|---|---:|---:|
| spine-and-ribs, 3 small cells | **3.212 g** | 12.846 g |
| full 0.6 mm FR4 carrier, 3 small cells | **7.300 g** | 29.201 g |
| spine-and-ribs, 3 LARGE cells (ADR-049 preferred) | **6.883 g** | 27.53 g |

**The payload mass band.** The repo gives **no v9 all-up mass**: `docs/POWER-BUDGET-V9-D2BE.md`
line 188 states *"Total mass cannot be stated"* because 11 of its 13 mass lines are
`TODO(unverified)`. The sourced/computed subtotal is 5.76 g. Representative figures that
*are* in-repo: minimal tracker **9 g**, Mesh V1 **14 g**, Mesh V2 **22 g**
(`docs/balloon-flight-lessons.md` §Success Factor #6, our own table); literature payloads
**12–30 g** (IEEE Spectrum, ibid. line 264).

> **Figure used in this analysis: payload = 20 g (mid-band). `TODO(unverified)` — no v9
> all-up mass exists in the repo; this is a band midpoint, not a measurement.** The
> descent-relevant stack used is payload + balloon envelope = 20 + 10.5 = **30.5 g**.

**Percentage of the payload band** (`f = m_shed / 20 g`):

| Shed item | grams | % of 20 g payload | % of 30.5 g stack |
|---|---:|---:|---:|
| one spine-and-ribs wing | 3.212 | **16.1 %** | 10.5 % |
| one full-carrier wing | 7.300 | **36.5 %** | 23.9 % |
| one large-cell spine wing | 6.883 | 34.4 % | 22.6 % |

One wing is **16 % of the payload** (spine) or **37 %** (full carrier). Not nothing — but
see what it buys.

### 1.2 Does one cut change the FLOAT ALTITUDE? — yes, and the wrong way

A balloon floats where the lift equals the total mass:

```
equilibrium:   rho_air(h) · V · g  =  m_total · g      (superpressure, V ~ constant)
=>             rho_air(h)  ∝  m_total
with           rho(h) = rho0 · exp(-h/H):
               -dh/H = -dm/m   =>   dh = H · (dm/m)      H = scale height
```

Using the stratospheric scale height **H = 6 500 m** (assumption; `TODO(unverified)` — no
in-repo value) and the 30.5 g stack:

```
spine wing :  dh = 6500 m × 3.212/30.5 =  685 m   (UPWARD)
full carrier: dh = 6500 m × 7.300/30.5 = 1556 m   (UPWARD)
```

**Answer.** Float altitude is set by *lift versus total mass*, and lift is fixed at launch
by the gas fill. Shedding mass therefore **cannot lower the altitude**: on a constant-volume
(superpressure) pico balloon the vehicle **climbs** to a new, higher equilibrium (**+685 m**
for one spine wing); on a vented zero-pressure balloon it simply **vents gas** and the
altitude is **unchanged**. In neither case does the cut buy altitude or descent authority.
What it *does* buy, on a superpressure balloon, is **685 m less burst margin** — the opposite
of what a weight-saving cut is usually for.

### 1.3 Does one cut change the DESCENT RATE? — with an explicit drag model

Descent after burst is drag-limited. The popped envelope "acts like a small parachute"
(`docs/balloon-flight-lessons.md` line 471):

```
terminal velocity:   m g = ½ rho Cd A v²      =>   v = sqrt( 2 m g / (rho Cd A) )
differentiate:       d(ln v) = ½ d(ln m)      =>   %dv = ½ · %dm
```

**Assumptions:** (i) descent is at terminal velocity at every altitude, so the logarithmic
derivative holds with `rho`, `Cd` and `A` cancelling; (ii) the reference rate is **0.447 m/s
(~1 mph)**, Ruthroff's figure for a light pico payload (`docs/balloon-flight-lessons.md`
line 472) — `TODO(unverified)`: the actual `Cd·A` of a popped Yokohama envelope is not in the
repo; (iii) the descent-relevant mass is the whole 30.5 g stack (payload + 10.5 g envelope).

| Shed | dm/m | dv/v | v (m/s) | 12 km fall (h) | Δt |
|---|---:|---:|---|---:|---:|
| spine wing 3.212 g | 10.5 % | **5.3 %** | 0.447 → 0.423 | 7.46 → 7.87 | **+25 min** |
| full carrier 7.300 g | 23.9 % | **12.0 %** | 0.447 → 0.394 | 7.46 → 8.47 | **+61 min** |

**Plainly: the mass saving is in the noise for descent.** One wing buys a 5 % slower fall,
i.e. **+25 minutes on a 7.5-hour descent** — while the parallel single-cut analysis finds the
same order (it reports −11 % descent rate for the whole array, in-flight). If the operator
instead measures against the payload alone (20 g, not the 30.5 g stack) the numbers double
to −8.0 % and −18.3 %; even then, one 3.21 g wing adds ~40 minutes to a 7.5-hour fall.

---

## 2. THE POWER COST OF SHEDDING

### 2.1 What is lost, in area and in power

**Array area** (`docs/analysis/wing-electrical.md` §0.1, cells 12 total):

```
large-cell wing  = 3 × 78.55 × 38.90 mm = 91.67 cm²   array = 366.7 cm²
small-cell wing  = 3 × 52.07 × 19.65 mm = 30.70 cm²   array = 122.8 cm²
AREA SHED PER WING = 1/4 = 25.0 %   (both builds)
```

**Array power.** The four wings are one series string (ADR-046 §2.3). In series the voltage
adds and the current is set by the weakest wing, so dropping one equal wing at fixed current
removes exactly 1/4 of the power:

| large-cell build (ADR-049 preferred) | V | I | P | vs 6.15 W radio |
|---|---:|---:|---:|---|
| 4 wings (peak) | 6.0 V | 1.2 A | **7.20 W** | **1.17× ABOVE** |
| after **1** cut | 4.5 V | 1.2 A | **5.40 W** | **0.88× BELOW** |
| after 2 cuts | 3.0 V | 1.2 A | 3.60 W | 0.59× below |
| after 3 cuts | 1.5 V | 1.2 A | 1.80 W | 0.29× below |

**The first cut already takes the array below the radio's 6.15 W maximum draw.** The
remaining array can no longer key the PA from solar alone at all; the whole TX burst must
come from the bank. Worse, the *charge ceiling* collapses:

```
bank charge floor = V_bank + BAT54 drop = 5.4 + 0.3 = 5.7 V
  4 wings = 6.0 V -> charges to the 5.4 V top -> usable 33.26 J  (100 %)
  3 wings = 4.5 V -> ceiling 4.2 V          -> usable 14.26 J  ( 43 %)   <-- FIRST CUT
  2 wings = 3.0 V -> ceiling 2.7 V          -> usable  0.00 J  (  0 %, cannot charge)
  1 wings = 1.5 V -> below the 3.0 V floor  -> usable  0.00 J  (  0 %)
```

So a **single** cut removes **57 % of the bank's usable energy** (33.26 J → 14.26 J) *and*
the array's ability to key the radio. The second cut removes the rest of the charging
function entirely. Shedding is not progressive in any useful sense: **cut 1 destroys the
power system; cuts 2–4 destroy what is left.**

For completeness, the accepted **small-cell 12-cell array peaks at 2.4 W — already 2.56×
below the radio's 6.15 W** (ADR-047 §1.4). On that build the "does the remaining array still
exceed 6.15 W" test fails **even before any cut**.

### 2.2 The asymmetry, stated plainly

An array that is oversized is useful **only** in the two cases that matter for a
daylight-only, burst-storage vehicle: **poor sun** (low winter elevation — 16.6° at 50 N;
`docs/analysis/wing-insolation-geometry.md` §1) and **high load** (the 6.15 W PA burst,
ADR-047 §1). Shedding area trades a capability that **cannot be recovered in flight** for a
mass saving that the vehicle **may not need**, and that is already **outweighed by simply
building the lighter wing on the ground**. The array is the mission (ADR-036: daylight-only
TX; the bank covers one burst); trading array area for grams is trading the mission for
grams.

---

## 3. THE SERIES-STRING PROBLEM — the scheme's hardest flaw

### 3.1 What happens electrically when an element of a series string is CUT AWAY

```
ADR-046 §2.3 series order:
  stack_top = W1.SOLAR_P -> BAT54 -> supercap bank
              W1.SOLAR_N == W2.SOLAR_P
              W2.SOLAR_N == W3.SOLAR_P
              W3.SOLAR_N == W4.SOLAR_P
  stack_bot = W4.SOLAR_N -> system GND
```

There is **one current path**. Physically cutting one wing out of it **opens the circuit**:
`I_string = 0`.

```
array output after the cut, with NO bypass = 6.0 V (3 wings) × 0 A = 0 W
                                  NOT       = 4.5 V × 1.2 A     = 5.4 W
```

**The array does not lose a quarter — it loses everything.** The "drop the lowest board"
step is, electrically, "turn the solar array off". This is the scheme's hardest flaw and it
is invisible in the mechanical picture the proposal is drawn from.

### 3.2 What hardware is required at each junction

To keep the remaining string alive when a level is cut, the removed wing's two solar
terminals must be **bridged**. Three candidate elements:

| Option | Devices | Mass/device | Verdict |
|---|---|---|---|
| **Passive Schottky** across `SOLAR_P`–`SOLAR_N`, **fitted** | **1** | ~20 mg (SOD-323) / 30 mg (SMA) | **Sufficient.** This is *exactly* the `D_BP1..D_BP4` provision ADR-046 §2.3 already specifies (currently DNP). Must be **≥ 2 A / 40 V** (ADR-049 clause 1; ADR-046's BAT54 is 200 mA / 30 V and is already undersized). |
| **Shorting MOSFET**, normally-OFF, turned ON at the cut | **1** + gate drive | ~20 mg | **Not sufficient alone.** A two-terminal MOSFET cannot simultaneously *pass the live wing's own current* and *bypass it when the wing is gone*; it needs a control line whose trigger must **survive the cut** and whose gate must be held in the correct state with the wing absent. |
| **Make-before-break connector** at the junction | 1 connector | 0.1–0.3 g | Electrically clean and passive, but it is a mechanical part in the cold/creep path (§5). |

**Part count and mass per junction (minimum electrically-correct set):**

- **Passive solution: 1 Schottky per junction** (≈ 20 mg) — the clean answer, and it is
  already in the design as a DNP population change, not a redesign.
- **Active solution: 2 devices per junction** (1 series-pass MOSFET **plus** 1 bypass
  Schottky) **plus** a surviving gate-drive/sense — i.e. **more** hardware than the operator
  proposes, not less.

> **Is a single MOSFET per junction, as the operator proposes, sufficient? No.** The
> minimum correct passive part is **one Schottky**; the minimum correct *active* set is
> **two devices plus a control path**. The operator's single MOSFET would either short the
> live wing or fail to bridge the cut wing — it cannot do both jobs from one device.

### 3.3 The topology that makes progressive shedding electrically clean — and its voltage cost

Two candidates:

1. **Keep the string whole, bypass each level** (§3.2, option i). This is the ADR-046
   design. It is electrically clean and costs **one 20 mg Schottky per junction**. But note
   what it does *not* do: it protects the *other* wings; the cut wing's own 1.8 W and its
   structure are gone, and the surviving 3-wing string still drops to **4.5 V ≤ 5.7 V charge
   floor** (§2), i.e. it can only charge the bank to 4.2 V.

2. **Make each hanging level a PARALLEL group.** Then a cut removes a branch without opening
   the string — electrically clean. **Cost:** N parallel 1.5 V wings give **1.5 V** total
   (voltage adds only in series), a **4× collapse** from 6.0 V, far below the 5.7 V charge
   floor. It would need a **boost converter, which ADR-047 explicitly refuses**. So the
   parallel-group topology is *electrically clean but system-illegal*; it cannot charge the
   5.4 V bank at all.

**Conclusion.** With these 3-cell (1.5 V) wings there is **no topology that both permits
progressive shedding and keeps the 6.0 V string** — the only clean option is #1, which
requires the DNP bypass diodes to be **fitted** and preserves only the other three wings,
at 4.5 V. The proposal therefore either (a) needs the ADR-046 bypass fitted *anyway*, making
the "MOSFET at the junction" redundant, or (b) needs a boost converter the repo has refused.

---

## 4. THE SHADING PENALTY OF A HANGING CHAIN

### 4.1 Model

Levels hang one below another with vertical spacing **s**. A ray at elevation `h` drops `s`
in falling from one level to the next while drifting horizontally by

```
dx = s / tan(h)
```

The upper plate (horizontal width `W`) casts its shadow on the lower plate offset by `dx`,
so the **shaded fraction** of the lower plate is (worst case: sun in the chain's own plane)

```
f = max( 0, 1 - s / (W · tan h) )
```

At 50 °N winter noon, `h = 16.56°` (`docs/analysis/wing-insolation-geometry.md` §1),
`tan h = 0.2974`.

### 4.2 Required spacing for < 10 % shading

| Sun elevation | small wing, **W = 176 mm** (long axis horizontal) | small wing, **W = 25 mm** (long axis vertical) |
|---|---:|---:|
| **16.56° (winter noon — worst case)** | **s ≥ 47.1 mm** (f = 0 at 52.3 mm) | s ≥ 6.7 mm |
| 10° | s ≥ 27.9 mm | s ≥ 4.0 mm |
| 5° (near sunrise/sunset) | s ≥ 13.9 mm | s ≥ 2.0 mm |
| 2° | s ≥ 5.5 mm | s ≥ 0.8 mm |

**Two honest results:**

1. **Winter noon is the worst case, not sunrise/sunset.** At low sun the ray is nearly
   horizontal, so its shadow is thrown *far sideways* and the required spacing **shrinks**.
   The chain is most penalised when the sun is highest — the middle of the 7.85 h winter
   day.
2. **Orientation dominates.** If the boards hang with their **long (176 mm) axis horizontal**,
   the minimum in-plane spacing is **47 mm**. If they hang with the long axis **vertical**
   (W = 25 mm), it is only **6.7 mm** — because the boards present only a 25 mm width for the
   shadow to fall on. So the chain's shading is a **layout choice**, and the cheap fix is to
   hang the boards edge-on to the chain axis (long axis vertical) — which, however, is the
   opposite of the "blade facing the sun" orientation the vertical-wing analysis wants.

### 4.3 What that spacing does to the chain, the inertia and the swing

With the defensible in-plane spacing `s = 47.1 mm` for four levels (board height t = 25 mm):

```
chain length  L = 3·s + 4·t = 3(47.1) + 4(25) = 241.3 mm
pendulum period  T = 2π sqrt(L/g) = 2π sqrt(0.2413/9.81) = 0.99 s
```

- **Chain length: ≈ 241 mm**, against a current coplanar-cross vertical extent of ≈ 25 mm —
  the payload becomes **~10× taller**, roughly doubling the span of the current small-cell
  arm (358.4 mm tip-to-tip, `wing-mass-shape` §3.5) in the vertical direction.
- **Swing moment of inertia** about the suspension point, `I = Σ m r²`, four 3.212 g masses
  at radii `r = d0 + k·s` with `d0 = 100 mm` (suspension) and `s = 47.1 mm`:

```
r = [0.100, 0.147, 0.194, 0.241] m   ->   I = 4.10 × 10⁻⁴ kg·m²
```

  Compare a compact 4-arm cross at ~0.09 m arm radius: `I ≈ 1.4 × 10⁻⁴ kg·m²`
  (`wing-mass-shape` §3.1, 4 × 3.662e-5). **The chain roughly triples the swing inertia.**
- **Swing:** the period lengthens from ~0.45 s (compact) to **~0.99 s**, and at 100 mm
  spacing to **1.27 s**. A longer period is a *slower*, larger-amplitude pendulum for the
  same disturbing impulse, and its amplitude is driven by balloon rotation, jetstream
  gusts on Ascent, and the recoil of each cut (§5).

---

## 5. THE MECHANICAL AND FLIGHT RISKS

A chain of boards on threads below a balloon is a **compound pendulum** with **several
independent bodies joined by flexible, non-rigid links**, which is the worst kinematic case
for entanglement. Risks, ranked worst first:

| # | Risk | Why it ranks here |
|---|---|---|
| **1** | **Tangling of threads** — with each other, and with the main suspension line | Any two threads that touch can knot; a knot ties the levels together, defeating the cut and putting the whole train at risk. Worst at **balloon burst** (the envelope snaps, the train whips and the main line crosses the level threads) and during **ascent** through the jetstream (150+ km/h relative airflow, `docs/balloon-test-results.md` §Altitude Effects). Compounds with every risk below (it is the single point that can lose the whole flight). |
| **2** | **A cut board falling past the boards below** | Geometrically **guaranteed interference**: the released board must pass the levels beneath it. At the 47 mm spacing §4 demands, a 176 mm board **cannot** clear a board 47 mm below without striking it in any non-vertical attitude, and it drags its own thread down the chain. A snag is a possible loss of the *remaining* levels, i.e. the cut can destroy the array it was protecting. |
| **3** | **Swing amplitude and what drives it** | Driven by (a) balloon rotation about the vertical axis (the payload "rotates slowly", so any asymmetry couples spin into swing), (b) jetstream gusts at ascent and float, (c) the **cut recoil** — severing a loaded nylon thread releases stored elastic energy and instantly removes a mass, exciting the compound pendulum. With `I ≈ 4.1 × 10⁻⁴ kg·m²` and `T ≈ 0.99 s` the chain is a slower, larger-Amplitude pendulum than the compact cross. |
| **4** | **Junction hardware ADDS mass where the scheme saves it** | The cut channel (MOSFET + nichrome + nylon) is **0.5 g** by repo precedent (`docs/balloon-test-results.md` line 253). Adding the electrically-required bypass (0.02 g), a 4-way flexible interconnect across the hanging junction (0.20 g, `ESTIMATE`) and a small junction carrier board (0.15 g, `ESTIMATE`) gives **≈ 0.87 g per junction** (below). Three junctions = **2.61 g carried all flight** to shed at most 9.64 g, and only after three separate cuts. |
| **5** | **Nylon at stratospheric cold** | Nylon 6,6 has a **dry glass transition `Tg ≈ 47–60 °C`**; at −60 °C it is **~110 K below Tg**, i.e. deep in the glassy, **brittle, notch-sensitive** regime (elongation at break falls from tens of percent to a few percent). `TODO(unverified)` — the exact nylon grade and its dry/wet state are not in the repo, and nylon's absorbed water plasticises it (wet PA6 Tg can drop to ~−60 °C), so the two grades behave very differently at −60 °C. Secondary effects: **creep** under sustained tension (slow at cold, but a knotted thread under constant load creeps and **loosens**), and a **thermal contraction mismatch** — nylon's CTE ≈ 8 × 10⁻⁵ /K over ΔT = 85 K shrinks a tensioned thread **~0.7 %**, slackening a taut chain. **The knot, not the cord, is the weak link** (parallel single-cut analysis, in-flight; unmeasured). |

### 5.1 Added mass per junction and the net saving per cut

```
  cut channel (MOSFET + nichrome + nylon)   0.50 g   CITED
  bypass Schottky (SS24/PMEG4020ER class)   0.02 g   CITED (ADR-049 rating basis)
  4-way flexible interconnect              0.20 g   ESTIMATE
  junction carrier board                   0.15 g   ESTIMATE
  PER JUNCTION TOTAL                     ≈ 0.87 g

  1 junction carried  -> +0.87 g all flight ; shed 3.212 g  -> net +2.34 g
  3 junctions carried -> +2.61 g all flight ; shed 9.64 g   -> net +7.03 g
```

Because **every junction must be carried from launch** (you cannot add hardware mid-flight),
the ladder carries its whole penalty on the way up: in the never-cut case the mass balance
is **purely negative (−0.87 g per junction)**, and even the best case (three cuts, dropping
all three lower boards) nets only **+7.03 g** against a scheme whose launch mass penalty is
already 8.5 % of the payload.

---

## 6. VERDICT AND THE BETTER VERSION

### 6.1 The five options, with numbers

| # | Option | Array mass carried | Added hardware | Failure modes added | Bench-testable? |
|---|---|---:|---|---|---|
| **(a)** | **Progressive-shed ladder** (operator's scheme) | 12.85 g + **2.61 g** (3 junctions) | 3 × 0.87 g ≈ 2.61 g | tangle, cut-through, snagged fall, nylon cold-brittle, **array open-circuit on first cut**, bank ceiling 5.4→4.2 V | Hard — needs vacuum-cold tangle rig, no such rig exists |
| **(b)** | **Single cut, whole array** | 12.85 g + 0.87 g (1 junction) | ≈ 0.87 g | one cut path; loses **all** solar (7.2 W → 0 W) at once | Moderate — one cut, one evidence line |
| **(c)** | **Stowed-and-deployed** (fold for launch/ascent, deploy at float) | 12.85 g + hinges/latches (**unquantified**) | hinges/latches/hold-downs | deploy failure (a known CubeSat risk with proven mitigations) | Yes — deploy test on the bench in a cold chamber; a **proven CubeSat pattern** |
| **(d)** | **Don't carry the mass** (ADR-049 spine-and-ribs, fewer/appropriate cells) | **12.85 g** (from 29.20 g) | **none** | **none** | Trivially — it is a PCB, weighed on a scale |
| **(e)** | **Do nothing** | 29.20 g (if a full carrier is kept) | none | none | n/a |

### 6.2 Ranking

- **By mass:** (d) = (c) = (a) = (b) tie on the array at 12.85 g spine; **(a) is worst once
  its 2.61 g of junctions is counted**; (e) is worst of all if a full carrier is retained.
- **By complexity:** (d) < (e) < (c) < (b) < (a). The ladder is the most complex by a wide
  margin: 3 cut channels + 3 bypass devices + 3 flexible interconnects + 3 junction boards.
- **By failure risk:** (d) = (e) = 0 added < (b) < (c) ≪ **(a)**. The ladder uniquely adds
  tangling, cold-brittle nylon, a snagged falling board, and an **array-killing first cut**.
- **By bench-testability:** (d) > (e) > (c) > (b) > (a). A spine PCB is weighed; a cold-chamber
  deploy test is routine; a tangle-and-cut rig at −60 °C in vacuum is a programme of its own.

### 6.3 Recommendation

**Rank: (d) > (c) > (e) > (b) > (a). Build (d). Reject the progressive ladder.**

**(d) is the answer, and it is already the ADR-049 recommendation.** The spine-and-ribs wing
removes **16.35 g from the four-wing array (29.20 g → 12.85 g) before launch** — **1.27×** the
mass of the *entire* array the ladder would hope to shed, achieved with **zero** strings,
**zero** actuators, **zero** new failure modes, and **weighed on a bench scale** rather than
proven in flight. Against that, the ladder's best case is a net **+7.03 g** after three cuts,
paid for with a first cut that **turns the solar array off**.

> **Does the progressive ladder earn its complexity? No — the same goal is met far more
> cheaply.** The goal it is aimed at (less mass) is met, better, by building the lighter
> frame. The goal it *achieves* (a 5 % slower descent) is negligibly small. And the mechanism
> it uses is defeated by the very series topology the array runs on.

**(c) is the only shedding-family option worth keeping**, and only if the real constraint is
**launch stowage volume** (a 358 mm tip-to-tip cross is awkward to handle) rather than mass:
blades folded for launch, deployed to hang at float, is a proven CubeSat pattern, adds no
actuator to the power path, and is bench-testable in a cold chamber. It is **not** a mass
saving — it is a stowage measure, and it must be costed as one.

### 6.4 What the operator should do instead

If the worry is **mass**: build the spine-and-ribs wing (ADR-049) and confirm the cell
masses on a 0.01 g scale (`wing-mass-shape` §8 item 1 is the single largest uncertainty in
the mass model — the repo's "~2 g/cell" and the model's 0.50 g/cell differ **4×**). This is
the entire mass remedy, and it is 16.35 g.

If the worry is **free lift at launch**: set free lift with the **gas fill** (target 5–7 g,
`docs/balloon-flight-lessons.md` §Success Factor #5). Mass is not "an issue" at float
because free lift is decided on the ground; a heavier payload asks for more helium (or a
larger envelope), not for a cutter.

If the worry is the **flimsy soldered tab** (the real structural concern this payload has):
fix the **tab/socket joint itself** (ADR-046 §4.4; ADR-049 clause 4 — the 0.9 mm slot is
below JLCPCB's 1.0 mm minimum and its worst-case clearance is 0.00 mm), not a cutter. This
is the same conclusion the parallel single-cut analysis reaches.

If the worry is **descent rate after burst**: it is already ~0.447 m/s (walking pace) over
7.5 hours; shedding one wing changes it by **5 %**. Do nothing.

---

## 7. TODO(unverified) — the exact open questions

1. `TODO(unverified)` — the **v9 all-up payload mass**. Repo says "Total mass cannot be
   stated" (`docs/POWER-BUDGET-V9-D2BE.md` line 188). §1.1 uses a 20 g band midpoint.
2. `TODO(unverified)` — the **stratospheric density scale height** used for the float-altitude
   shift (6 500 m assumed). No in-repo value.
3. `TODO(unverified)` — the **`Cd·A` of a popped Yokohama envelope**, so the descent model's
   reference rate (0.447 m/s) is a literature figure, not a measurement.
4. `TODO(unverified)` — the **nylon grade and its dry/wet state**, hence its actual `Tg` and
   low-temperature toughness at −60 °C. §5 row 5.
5. `TODO(unverified)` — the **junction interconnect and carrier-board masses** (0.20 g and
   0.15 g here) are estimates; only the 0.5 g cut channel is repo-cited.
6. `TODO(unverified)` — whether a **fitted bypass Schottky** can carry the string current
   through a *mechanically* cut socket (the socket's own lands and any remaining stub), or
   whether the bridge must be a separate shorting contact.
7. `TODO(unverified)` — the actual **winter launch latitude/season** (50 N / winter solstice
   assumed; `wing-insolation-geometry` §7 item 1) and therefore the exact noon elevation.

## 8. Sources cited

- `docs/adr/049-wing-architecture.md` — spine+ribs recommendation, bypass rating, clamp.
- `docs/adr/046-wing-board-interface.md` §2.1/§2.3 — 4-pin tab, series order, DNP bypass.
- `docs/adr/047-v9-power-provisioning.md` §1.2/§1.4/§3.2 — 6.15 W, 2.56× array gap, 33.264 J.
- `docs/adr/006-supercapacitor-power.md` (Accepted) — 12 cells, 6.0 V, array = mission.
- `docs/adr/048-v9-hub-wing-interfaces.md` — hub sockets, hub-owned series wiring.
- `docs/analysis/wing-mass-shape.md` §1.4/§3.1 — 3.212 g / 7.300 g wings, arm inertia.
- `docs/analysis/wing-electrical.md` §0.1/§2.3 — cell areas, joint counts, series rule.
- `docs/analysis/wing-insolation-geometry.md` §1/§2b — 16.56° noon, series mismatch.
- `docs/analysis/wing-fab-cost.md` §1 — joint count as the primary hand-build risk metric.
- `docs/POWER-BUDGET-V9-D2BE.md` — mass table (mostly TODO), array/bank references.
- `docs/PAYLOAD-WEIGHT-ESTIMATES.md` — per-cell and per-module mass estimates.
- `docs/balloon-flight-lessons.md` §Success Factor #5/#6, line 472 — free lift, payload band, descent.
- `docs/balloon-test-results.md` line 253 — 0.5 g per cut-down channel precedent.
- `analysis/wing-jettison` (commit `5365dac7`, **in-flight**) — single-cut whole-array study.

## 9. Reproduction

```
python3 docs/analysis/wing_ladder_model.py     # stdlib only; prints every number above
```
