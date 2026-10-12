# Array power architecture — per-wing 6 V, topology, and the real limit on losing a wing

> **STATUS: CONSULTANT ANALYSIS — NOT A DECISION RECORD.**
> This is a reasoned engineering analysis with numbers, produced for the operator to decide
> on. It is **not** an ADR, it does **not** amend ADR-006 / ADR-046 / ADR-047 / ADR-048 /
> ADR-049, and nothing here may be read as an accepted design. It carries **no authorisation
> to change any board, BOM, schematic, wing outline or series count**. Every number below is
> either (a) computed with its formula shown, (b) cited to an in-repo document, or
> (c) marked `TODO(unverified)` with the open question named. Where this analysis disagrees
> with an accepted record it says so explicitly.

| | |
|---|---|
| Date | 2026-10-07 |
| Author | subagent (Hermes), branch `analysis/array-power-architecture` |
| Worktree | `/home/c03rad0r/worktrees/bf-wingarch` |
| Base commit | `af9a672` — the tip of `main` when the task was issued, and an ancestor of `github/main`. **`github/main` has since advanced to `c54da64`** (the in-flight `analysis/wing-ngon` and `analysis/wing-ladder` studies merged); this branch does **not** include those two merges. They are geometry/insolation work cited as in flight in §9/§10, so nothing in this analysis depends on them |
| Lens | **power topology, source/load matching, protection** — *not* mechanical, not geometry, not layout |
| Model script | `docs/analysis/array_power_architecture_model.py` (stdlib only; every figure below is its own printed output) |
| Scope ruled out | no board code, no schematic edit, no BOM change, no wing redraw in this document |
| Not duplicated | the **jettison / release** study (branch `analysis/wing-jettison`, commit `5365dac`) and the **geometry / insolation** studies (`analysis/wing-insolation`, `analysis/wing-omni`, `analysis/wing-ngon`, `analysis/wing-ladder`, and `docs/analysis/wing-insolation-geometry.md`) are **in flight** and are cited, not re-derived |
| Read first | ADR-006 (Accepted), ADR-036, ADR-044, ADR-046 §2.3, ADR-047, ADR-049, `docs/analysis/wing-electrical.md`, `docs/POWER-BUDGET-V9-D2BE.md` |

---

## 0. Answer first

**Recommendation: keep the accepted direct-connected 12-cell series array.** Do **not** build
per-wing 6 V, do **not** add a per-wing converter, do **not** add a charge-path MPPT converter,
and do **not** oversize the array. Accept a reduced TX power (about −1.6 dB) after the loss of
one wing. The one thing that must change is already on the record: **fit the per-wing bypass
Schottky and re-rate it to ≥ 2 A / 40 V** (ADR-049 §Consequences clause 1).

The five findings that carry it, each with its number:

1. **"Each wing provides 6 V" costs 4× everything.** 0.5 V/cell means **12 cells per wing**,
   so **48 cells** for four wings — **4.00× cells, 4.00× installed area (1466.7 cm² vs
   366.7 cm²), 4.00× cell mass (72.0 g vs 18.0 g) and 4.00× peak power (28.80 W vs 7.20 W)**
   (§1). And that array is **4.68×** the radio's 6.15 W maximum draw and **74.2×** the
   mission's average draw — it is not needed by any requirement.
2. **A capacitor does not stabilise anything.** It buffers and decouples transients; its
   terminal voltage is whatever charge divided by C gives, and it droops
   ($\Delta V = I\,t/C$). A photovoltaic source's voltage is not 6 V: a "12-cell 6 V" wing's
   open-circuit output spans **7.44 V at 25 °C to 9.58 V at −60 °C — 24 % to 60 % above the
   number it is called**. What holds a rail is a **closed-loop voltage regulator** — an
   LDO, a switching regulator, or a shunt clamp (§2).
3. **The real limit is the duty cycle, not the topology.** With 3 of 4 wings the array peak
   is **5.40 W = 0.878×** the 6.15 W maximum draw (a **−0.749 W** deficit), and with 2 wings
   **3.60 W = 0.586×** (**−2.549 W**). Topology cannot fix that. But the mission average is
   **0.388 W**, which is **15.85×** below the peak; one wing alone (1.80 W) covers the
   average **4.64×** over, and three wings cover it **13.92×** over (§3).
4. **A bypass diode buys string conduction, not mission function.** With one wing bypassed
   the string continues at 4.5 V, but the bank can then only be charged to **4.2 V**, never
   the design's 5.4 V. 4.5 V cannot charge a 5.4 V bank (§4).
5. **The actual fix is the diode you already specified, plus accepting a lower rail.** At
   4.2 V the radio makes **31.44 dBm** instead of 33.0 dBm (**−1.56 dB**) but the radio's
   minimum is 3.0 V, so the **mission continues**; with 2 wings the bank tops at **2.70 V**,
   below the radio's 3.0 V minimum and below the LDO's dropout, so the **mission ends**.
   One wing lost = survivable; two = not (§4, §7).

The deciding number is **15.85×** — the ratio of the radio's maximum draw (6.15 W) to the
mission's average draw (0.388 W). Any redundancy scheme sized against the *peak* is oversized
by that factor, which is why the self-contained per-wing 6 V idea buys nothing.

---

## 1. THE COST OF PER-WING 6 V

### 1.1 Assumptions used (with basis)

| Symbol | Value | Basis |
|---|---|---|
| Cell voltage, both classes | 0.50 V nominal | CITED `docs/adr/049-wing-architecture.md` §Measured inputs; `docs/analysis/wing-electrical.md` §0.1 |
| Large cell | 78.55 × 38.90 mm, 30.556 cm², ≈1.2 A, ≈1.50 g | CITED ADR-049 §Measured inputs; wing-electrical §0.1 |
| Small cell | 52.07 × 19.65 mm, 10.232 cm², 0.4 A, ≈0.50 g | CITED ADR-049 §Measured inputs; wing-electrical §0.1 |
| Accepted array | 4 wings × 3 cells = 12, 1.5 V/wing, 6.0 V @ 1.2 A = 7.20 W | CITED ADR-049 §Decision; wing-electrical §3(a). **The 7.2 W / 1.2 A figure is ADR-049's large-cell result**; ADR-006's own 2.4 W / 400 mA line is the small-cell original (ADR-006 §Komponenten) — the two are not in conflict, they are different cell classes |
| Outline convention | `width = rows·cell_w + (rows−1)·6 + 8`; `length = cols·cell_l + (cols−1)·6 + 8` | CITED wing-electrical §3(a) margin convention (3 mm each side, 6 mm land gap, 4 mm end margin) |
| FR4 carrier | 0.6 mm FR4 = 127.6 mg/cm² | CITED ADR-049 §rejected-options table |
| Large-cell current | 1.2 A (area-scaled) | `TODO(unverified)` — the 0.54 W listing implies 1.08 A; never reconciled by measurement (wing-electrical §0.2). Every large-cell number scales linearly with this |
| Cell masses | 1.50 g / 0.50 g | `TODO(unverified)` — `docs/component-guide.md` figures, not weighed (wing-electrical §3a) |

### 1.2 What "each wing provides 6 V" requires

```
cells per wing for 6.0 V = 6.0 V / 0.5 V per cell        = 12 cells
cells total, 4 wings     = 4 × 12                         = 48 cells
```

| Quantity | 4 wings × 12 (LARGE) | 4 wings × 12 (SMALL) | Accepted 12 large | Multiple vs accepted |
|---|---:|---:|---:|---:|
| Cells | 48 | 48 | 12 | **4.00×** |
| Power per wing (`6.0 V × I`) | 7.20 W | 2.40 W | 1.80 W | 4.00× |
| **Array peak power** | **28.80 W** | **9.60 W** | **7.20 W** | **4.00×** |
| Installed cell area | 1466.7 cm² | 491.1 cm² | 366.7 cm² | **4.00×** |
| Installed cell mass | 72.0 g | 24.0 g | 18.0 g | **4.00×** |

Formulas as printed by the model:
`area = 48 × 30.556 cm² = 1466.6880 cm²`; `mass = 48 × 1.50 g = 72.0000 g`;
`P_array = 4 × (6.0 V × 1.2 A) = 28.8000 W`.

### 1.3 Resulting wing outline, in millimetres, both cell classes

| Build | Packing | Board outline | Board area |
|---|---|---|---|
| **LARGE, 12 cells/wing** | 4 rows × 3 columns, cells 78.55 mm along the arm | **255.65 × 181.60 mm** | 464.3 cm² |
| **SMALL, 12 cells/wing** | 2 rows × 6 columns (52.07 mm along the arm) | **350.42 × 53.30 mm** | 186.8 cm² |
| SMALL, 12 cells/wing (ADR-046 orientation: 52 mm across the width) | 1 row × 12 along | **309.80 × 60.07 mm** | 186.1 cm² |

For reference, the two in-repo 3-cell large arms — **ADR-049 §Recommended outline
(167.1 × 86.8 mm = 145.0 cm²)** and **wing-electrical §3(a) (255.65 × 44.90 mm = 114.8
cm²)** — put the 12-cell large wing at **4× either: 580.2 cm² or 459.1 cm²**. The two
in-repo arms are themselves not identical (a 26 % area difference for the same 3 cells); that
disagreement is **stated, not resolved, here** — it belongs to the wing-geometry work already
in flight.

Note the physical consequence: a **255.65 mm** long arm against today's **176.0 × 25.0 mm**
body (ADR-046 §3.2) makes four much larger wings — 4× the cell area means ~4× the swept area
on a 50 N payload, which is a drag and handling change, not just a mass change. (The
mechanical and insolation consequences belong to the in-flight geometry studies; they are not
re-derived here.)

### 1.4 Is that array size needed at all? — No.

| Comparison | Value |
|---|---:|
| Accepted 12-large array ÷ radio peak (6.1495 W) | **1.171×** — the accepted array **already exceeds** the maximum draw (as ADR-049 §Decision states) |
| Per-wing-6 V large array ÷ radio peak | **4.684×** |
| Per-wing-6 V small array ÷ radio peak | 1.561× |
| Per-wing-6 V large array ÷ mission average (0.388 W) | **74.227×** |

The requirement the per-wing 6 V idea is trying to buy is **tolerance to a lost wing** — and
that tolerance is **not** a function of array size (§3). The array does not need to be bigger;
the question is whether the array's *voltage* can still reach the bank, which is §4.

### 1.5 The reading the task did not ask for, stated because it is the only cheap version

There is one way to satisfy "fewer wing boards" at **zero extra cells**: put the *same*
12-cell series string on fewer boards (one board of 12 cells, or two of 6). That preserves
6.0 V, 7.2 W and the 12-cell count, but it (a) destroys the four-arm 3D harvest rationale
(ADR-006 §3D-Solar-Vorteil; the in-flight geometry studies quantify the loss), and (b)
concentrates the whole array into a **single point of failure** — one lost board now kills
everything, where today a per-wing bypass diode at least preserves the other three. **It is a
board-count saving, not a redundancy gain, and it makes the operator's own worry worse.**
Verdict: REJECT.

---

## 2. TERMINOLOGY, PRECISELY — what a capacitor does and does not do

The operator says the 6 V output would be "stabilised by a capacitor". Stated plainly:

**What a capacitor does.** It stores charge, `Q = C·V`. Its impedance is `Z = 1/(2πfC)`, so it
is a low impedance at high frequency and an open circuit at DC. That makes it a **buffer** and
a **decoupler**: it supplies the *fast* part of a load step (the PA's current edge, before the
source can respond) and it shunts fast noise away from a node. ADR-047 §4.3 is the in-repo
statement of exactly this: a 100 µF bulk cap "covers the PA's current step for the first
~8 µs within 100 mV, after which the bank is the source".

**What a capacitor does not do.** It does **not** hold a voltage at a setpoint. It has no
reference, no error amplifier and no control loop; there is nothing in a capacitor that
decides what voltage the node should be. Its terminal voltage is simply the charge divided by
its capacitance, and with no source it **droops** at `ΔV = I·t/C` — ADR-047 §4.2 computes
that droop for this bank and finds the ESR term dominates by three orders of magnitude
(`I·ESR = 1.2 A × 0.10 Ω = 0.120 V` vs `I·t/C = 1.2 × 0.100/3.3 = 36.4 mV`), i.e. **the one
term a capacitor cannot reduce is the dominant one**. A capacitor cannot raise a voltage
either: a 4.5 V source charging a capacitor through a diode stops at ≈4.2 V, full stop (§4).

**And a photovoltaic source is not a 6 V source.** Its voltage moves with illumination,
temperature and load. Computed from the cells' assumed coefficients (CITED wing-electrical
§5.1 — both coefficients are themselves `TODO(unverified)`):

```
V_OC,cell(-60 °C) = 0.62 V + (-2.1 mV/°C/cell)(-85 °C)   = 0.7985 V
V_OC,array(-60 °C) = 12 × 0.7985 V                        = 9.5820 V
post-BAT54                   = 9.5820 - 0.3 V             = 9.2820 V
V_OC,array(25 °C) = 12 × 0.62 V                           = 7.4400 V
```

So a "12-cell 6 V" wing's **open-circuit** output is **24 % to 60 % above the 6.0 V it is
called**, and its *working* voltage is whatever the load or the bank clamps it to. Calling
that node "6 V" is a nominal label, not a specification.

**What actually regulates or stabilises a rail** — the specific circuit class:

- **Linear regulator (LDO)** — a series pass element in a negative-feedback loop against a
  voltage reference. Dissipative: it burns `(V_in − V_out)·I`. This design already has one:
  the **TPS7A02 3.3 V** at `I_Q = 25 nA` (ADR-006 §LDO Regler).
- **Switching regulator (buck / boost / buck-boost)** — an inductor, a switch and a PWM
  control loop against a reference. Efficient, but it is an intrinsic noise source. This is
  the class ADR-044 §3 option (b) refused for the radio rail.
- **Shunt regulator / clamp** — sinks excess current to hold a node *down* (dissipative).
  ADR-049 §Consequences clause 3 and ADR-047 §7 require exactly this at the raw supercap node,
  because the array's cold open-circuit voltage is ~9.3 V against a 5.4 V bank.
- For the **source** side of a PV array specifically, the stabilising circuit class is a
  **maximum-power-point tracker (MPPT)** — a switching converter whose control loop
  deliberately *does not* hold the input at a fixed voltage, but dithers it to wherever the
  array's `V·I` product is maximal. That is §5.

**The sentence to keep:** a capacitor buffers transients; a **regulator** sets a rail; an
**MPPT** makes a PV array's output usable at any illumination. The operator's phrase names the
first and means one of the other two.

---

## 3. THE REAL LIMIT — peak versus average

### 3.1 Peak case (per-wing 6 V or accepted array, both 1.80 W/wing)

| Wings remaining | Array peak (`n × 1.80 W`) | ÷ radio peak 6.1495 W | Deficit |
|---:|---:|---:|---:|
| 4 | 7.2000 W | 1.171× | +1.051 W surplus |
| **3** | **5.4000 W** | **0.878×** | **−0.749 W** |
| 2 | 3.6000 W | 0.586× | −2.549 W |
| 1 | 1.8000 W | 0.293× | −4.349 W |

**Can topology fix a power deficit? No, and this is not debatable.** For a photovoltaic array
the delivered power is `P = A · G · η` — installed cell area × irradiance × efficiency.
Series and parallel wiring only **redistributes voltage and current**; it cannot create watts.
A series string of 3 wings delivers `4.5 V × 1.2 A`; a parallel string of 3 wings delivers
`1.5 V × 3.6 A`; both are **5.40 W**, because both are the same three panels in the same light.
What topology *can* fix is (i) **mismatch** — making sure a shaded or weak element does not
throttle the others (bypass diode, or MPPT) — and (ii) **the voltage window in which the
available power can be delivered** (§4). Neither is a power deficit.

### 3.2 Average case — the crux

The duty cycle is what decides the operator's question. CITED `docs/POWER-BUDGET-V9-D2BE.md`
§2: TX is **1 %** duty on the 5 V rail (`0.01 × 1.20 A + 0.99 × 0.020 A = 31.8 mA` →
`0.159 W`), the 3.3 V rail averages `49.6 mA → 0.164 W`, and with a 20 % distribution
allowance the representative **input power is `(0.159 + 0.164) × 1.20 = 0.388 W`**. ADR-036 is
what makes this the *policy* number: **TX is energy-gated and daylight-only**, storage is sized
to one burst, and night is deep sleep.

| Wings remaining | Array peak | ÷ average 0.388 W |
|---:|---:|---:|
| 4 | 7.20 W | 18.557× |
| 3 | 5.40 W | **13.918×** |
| 2 | 3.60 W | 9.278× |
| 1 | 1.80 W | **4.639×** |

**Deciding number: `6.1495 W ÷ 0.388 W = 15.848×`** — the peak draw is **15.85×** the average
draw, so any redundancy scheme sized against the peak is oversized by ~16×.

**So how many wings can be lost before the MISSION is compromised?** Two different answers,
and the distinction is the whole point:

- **On power/energy: three.** A **single** wing (1.80 W peak) covers the 0.388 W average
  **4.64×** over. The mission's *energy* budget does not need four wings, three wings, or even
  two.
- **On voltage/topology as wired: none.** The four wings are **one series string**
  (ADR-046 §2.3), so what a loss costs is not 25 % of the power — it is **1.5 V of string
  voltage**:

```
4 wings → 6.0 V string top        (bank can reach its 5.4 V design top)
3 wings → 4.5 V string top        (bank tops out at 4.5 − 0.3 = 4.20 V)
2 wings → 3.0 V string top        (bank tops out at 3.0 − 0.3 = 2.70 V)
1 wing  → 1.5 V string top        (bank tops out at 1.2 V)
```

with the BAT54 blocking any reverse flow once the bank is above the string (ADR-006). So:

| Wings left | Bank top reachable | Usable energy to 3.0 V (3.3 F bank) | Consequence |
|---:|---:|---:|---|
| 4 | 5.4 V | 33.264 J | design case |
| **3** | **4.20 V** | **14.256 J** | **mission continues**, TX power reduced |
| 2 | 2.70 V | **0 J above 3.0 V** | radio's 3.0 V minimum and the LDO's ~3.5 V input are both unreachable → **mission over** |

**Therefore: exactly ONE wing can be lost and the mission continues; losing TWO ends it.**
And that conclusion is set by the **series count** (voltage), not by **power** — which is why
making each wing 6 V *does* address the operator's real worry, and why making the array bigger
does not. The cheap version of the same fix is the bypass diode and a re-rated wing count
(§4, §7).

---

## 4. THE SERIES-CUT PROBLEM, AND WHAT ACTUALLY FIXES IT

### 4.1 What a per-wing bypass diode achieves

The four wings are one series string; the bypass Schottky sits across one wing
(`SOLAR_P`–`SOLAR_N`, cathode to `SOLAR_P`) — this is already mandated by **ADR-046 §2.3** and
repeated in ADR-048 §2.3, and ADR-049 §Consequences clause 1 re-rates it.

```
without bypass: a cut/dark wing opens the string → array current collapses to ≈ 0
                and the other 3 wings (4.5 V of drive) push current through the
                dead wing's cells in REVERSE: 4.5 V × 1.2 A = 5.4 W over 3 cells
                = 1.8 W/cell → hot spot  [wing-electrical §4.1: 0.60 W/cell at 0.4 A]
with bypass:    the dead wing is shunted; the string continues with 3 of 4 wings
                string voltage = 3 × 1.5 V = 4.5 V
                minus the bypass Schottky drop ≈ 0.3 V → 4.2 V available
```

**What the diode DOES buy:**

1. **String conduction.** Without it, one lost or shaded wing kills the whole array and
   reverse-stresses its cells at a hot-spot-level dissipation (ADR-046 §2.3 names this as "a
   hot-spot / cell-degradation risk, not just a power loss"). With it, three-quarters of the
   array keeps working.
2. **A rechargeable bank.** The bank can still be charged — but only **up to 4.2 V**.

**What the diode does NOT buy:**

- **The 5.4 V rail.** 4.5 V cannot charge a 5.4 V bank; **4.2 V cannot either**. A source
  cannot drive charge into a capacitor whose voltage is above the source's own. The design's
  top is **unreachable** with 3 of 4 wings.
- **Full TX power.** ADR-047 §5's own table: the module makes **33.0 dBm at 5.0 V**,
  **31.8 dBm at 4.5 V**, **31.2 dBm at 4.0 V**. Interpolating between the 4.0 V and 4.5 V
  rows for a 4.2 V rail gives
  `31.2 + 0.2 × (31.8 − 31.2)/0.5 = 31.44 dBm`, i.e. **−1.56 dB** against 33.0 dBm, and the
  module's full 2 W (33.0 dBm) requires **≥ 5.0 V** — **not available** with three wings.
  (Interpolation between published rows, as ADR-047 §5 itself does; it is not a datasheet
  claim.)

**And it does not buy per-cell protection.** The diode is *across a whole wing*: a wing with
one shaded cell still sources ≈1.0 V from its two lit cells, so the wing diode never turns on
and the shaded cell is reverse-stressed from inside its own string. Per-cell shading needs
**per-cell** bypass (wing-electrical §4.2). That finding is in flight elsewhere and is not
re-derived here.

### 4.2 The actual fix, stated three ways

There is **no passive fix** for "3 wings cannot reach a 5.4 V bank". The options are exactly:

1. **More series cells behind each connector** — i.e. raise the string voltage with fewer
   wings. This is precisely the operator's per-wing-6 V idea, and it works — at 4.00× the
   cells, area and mass (§1, §6).
2. **A step-up converter on the charge path** — let a 4.5 V (or 3.0 V) array charge a 5.4 V
   bank. This is §5.
3. **Accept a lower rail after a loss** — 4.2 V, −1.56 dB of TX power, mission continues.
   This is §3's answer and the recommendation.

Also note the current state: the bypass diode is **DNP for the first build** (ADR-046 §2.3;
ADR-048 §2.3) and the specified part is **undersized** — a BAT54-class part is rated
**200 mA / 30 V** against a **1.2 A** string, i.e. **6× under-rated** (ADR-049 clause 1;
wing-electrical §4.3). So **today, losing one wing kills the array.** Fitting and re-rating
that diode (≥ 2 A / 40 V, e.g. SS24 or PMEG4020ER) is the cheapest change in this entire
analysis and it converts a mission-ending failure into a −1.6 dB TX degradation.

---

## 5. THE CONVERTER OPTION — one MPPT boost or buck-boost on the charge path

Configuration assessed: **one converter between the array and the supercap bank**, input
≈ 3.0–6.5 V, output ≈ 5.4 V, i.e. a **boost** (or buck-boost, since the array's open circuit is
above 5.4 V when cold):

```
boost ratio at Vin = 3.0 V : 5.4 / 3.0 = 1.80×
boost ratio at Vin = 4.5 V : 5.4 / 4.5 = 1.20×
at Vin = 6.0 V             : 5.4 / 6.0 = 0.90×  → buck-boost, not a pure boost
```

### (a) What it buys

- **MPPT at any illumination.** The array is always operated at its maximum-power point
  instead of being clamped to the bank's voltage. Quantified below.
- **Tolerance of a lost or shaded wing.** With an input floor of 3.0 V, **three wings (4.5 V)
  and even two wings (3.0 V) still charge the bank to 5.4 V** — the failure that ends the
  mission in §3 simply stops being a failure. This is the single biggest thing the
  converter buys, and it buys it **for 12 cells, not 48**.
- **No per-wing bypass diodes needed for function.** (They are still needed for hot-spot
  protection of a shaded wing's *cells* — the converter does not protect a cell that is being
  reverse-driven inside its own string. State this plainly; it is not a free deletion.)
- **Freedom of series count** (see (d)).

### (b) What it costs

| Cost | Value | Basis |
|---|---|---|
| Conversion efficiency | **ASSUMPTION 85 %** | **`TODO(unverified)`** — no part is selected. ADR-044 §3 option (b) records the part choice as not made; both named candidates (TPS61099, LTC3525) are in `docs/F33-MODULE-PLAN.md`, not in this repo as datasheets |
| Quiescent current | **`TODO(unverified)`** — part-dependent | ADR-044 §3 option (b): "a switcher's I<sub>Q</sub> is part-dependent and not yet selected". For scale: **1 µA at 5.4 V = 5.4 µW = 5.4 %** of ADR-036's 100 µW night anchor, and the converter sits on the **raw VSCAP node**, so its I<sub>Q</sub> drains the bank continuously |
| Mass / cost | **0.5–1.5 g**, **€1.50–4.00** + inductor + reservoir caps | CITED ADR-044 §3 option (b) |
| Part count | controller + inductor + switch (if not integrated) + input/output caps + feedback network | ADR-044 §3 option (b) |
| New failure point | **one.** A switcher can fail open (no charging) or short (array shorted into the bank); there is no such failure mode on a wire | derived |
| Re-freezes forced | BOM (active parts), ADR-030 placement keep-out, ADR-032 simulation of switcher harmonics | CITED ADR-044 §3 option (b) |

**Energy balance — the number that decides whether MPPT pays.** Using a stated, conservative
direct-connection model (`P_direct(V_b) = V_b × I_MPP`, which *understates* the direct design
because a PV cell's current rises above `I_MPP` as its voltage falls toward `I_sc`) against an
MPPT at `η × P_MPP = 0.85 × 7.20 W = 6.12 W`, independent of bank voltage:

| Bank voltage | Direct connection `V_b × 1.2 A` | MPPT at 85 % | MPPT gain |
|---:|---:|---:|---:|
| 3.0 V | 3.60 W | 6.12 W | **+70.0 %** |
| 3.5 V | 4.20 W | 6.12 W | +45.7 % |
| 4.0 V | 4.80 W | 6.12 W | +27.5 % |
| 4.5 V | 5.40 W | 6.12 W | +13.3 % |
| 5.0 V | 6.00 W | 6.12 W | +2.0 % |
| **5.4 V (full charge)** | **6.48 W** | **6.12 W** | **−5.6 %** |

```
break-even bank voltage = P_mppt / I_MPP = 6.12 W / 1.2 A = 5.10 V
                        = 94.4 % of the 5.4 V bank top
```

**The finding: below 5.10 V of bank voltage the converter wins; above it, the direct
connection wins.** And ADR-036's policy keeps this bank **near its top during daylight** —
TX is daylight-only and energy-gated, so the bank is deliberately charged before it transmits.
The MPPT's real win is therefore concentrated in exactly the regime the design tries to avoid
(deep discharge, or a lost wing), while its 15 % conversion loss is paid **all the time**. On
energy alone, at η = 85 % this converter is **not** justified for the nominal mission; it is
justified as *insurance* against a degraded array. At η = 90 % the break-even moves to 5.40 V
and the argument gets stronger; at η = 80 % it moves to 4.80 V and gets weaker. **The
efficiency is the whole question, and it is unmeasured — `TODO(unverified)`.** Note also that
the numbers are all scaled by the large cell's unverified 1.2 A (wing-electrical §0.2).

### (c) The EMI question — is ADR-044's refusal a different question?

ADR-044 §3/§4 **refused option (b), a boost converter holding 5 V for the RADIO RAIL**,
because that converter would sit **~2 mm from a −136 dBm 2.4 GHz receiver** on the tightest
board in the project, forcing ADR-032 simulation of switcher harmonics and making ADR-029 §5
tests 1 and 3 (**2.4 GHz noise-floor rise < 3 dB; GNSS C/N0 drop < 1 dB**) the acceptance
numbers for an intrinsic noise source. ADR-047 §5 repeats the refusal for the radio rail. A
**charge-path** converter is a different converter answering a different question — but the
distinction is **only partly real, and it must be measured, not asserted**:

**Where the distinction IS real:**

1. **Purpose and placement freedom.** A charge-path converter transfers energy *into* the
   bank; its switched loop can be laid out at the array end of the hub and is not obliged to
   sit beside the radio's LNA. ADR-044's objection is specifically about a converter that must
   be *at the radio module's pin 1*, i.e. 2 mm from the victim.
2. **Coupling mechanism.** For the radio-rail boost the dominant worry is a **radiated** field
   from the switching loop into the co-located LNA/antenna. For a charge-path converter the
   dominant worry is **conducted ripple on VSCAP** — which is a real path, because ADR-047
   §2.1 makes **VSCAP itself the radio's VCC** (the pin-1 tap). That is a *different* path, and
   a conducted path is filterable (the bank is a low-impedance node; a ferrite/LC at the
   converter output is possible) in a way a 2 mm radiated path is not.
3. **Spectral overlap.** A typical boost's switching frequency (fractions of a MHz to a few
   MHz) and its low-order harmonics are well below both the 433 MHz TX band and the 2.4 GHz
   RX band; what couples is the switching *edge* spectrum and PDN resonances, not the
   fundamental.

**Where the distinction is NOT real:**

1. **The hub is small.** The v9 flight board is **55.15 × 45.15 mm** (ADR-029, via
   POWER-BUDGET §4). "At the hub" is still centimetre-scale from the radio — better than 2 mm,
   not far.
2. **The output node IS the radio's supply.** Conducted ripple on VSCAP directly modulates the
   F33's VCC, so the charge-path converter has a coupling path the radio-rail boost shares.
3. **ADR-044's third re-freeze applies either way:** ADR-032 simulation of switcher harmonics
   and ADR-029 §5 tests 1 and 3 as acceptance numbers.

**How to verify (cheap, decisive, and the order the project uses):** build the converter on a
bench harness, run the receiver in RX at the mission's sensitivity floor with the converter
switching at its worst-case duty, and measure (i) ADR-029 §5 test 1 (< 3 dB 2.4 GHz noise-floor
rise), (ii) test 3 (< 1 dB GNSS C/N0 drop), and (iii) **conducted ripple on VSCAP** against the
existing rail acceptance number, ADR-029 §5 test 4 (rail dip **< 20 mV**). Until then, this is
`TODO(unverified)`. **Recommendation on the evidence available: do not adopt the converter on
an EMI argument either way — adopt it or reject it on the energy and mass numbers, and let the
measurement settle the EMI.**

### (d) Should the series count change, and does the small-cell build become preferable?

**Series count: yes, it becomes free — and that buys nothing here.** With an MPPT whose input
floor is 3.0 V, the series count is set by the converter's window rather than by the bank
voltage, so the array could drop to 8 cells (4.0 V nominal) or stay at 12. But the accepted
`n = 12` is driven by the **charge target**, not by preference: wing-electrical §5.3 derives
`n ≥ (5.4 V + 0.3 V)/0.5 V = 11.4 → 12`, and separately `n ≤ 5.5 V/0.80 V = 6.9 → ≤ 6` to keep
the **cold open-circuit** voltage under the radio's 5.5 V maximum. Those are mutually
exclusive (12 vs ≤ 6), which is *why* the shunt clamp is required regardless of series count
(ADR-049 clause 3, ADR-047 §7). So a converter's "freedom of series count" is a freedom the
design cannot spend: the clamp is already mandated, so the count is already unconstrained by
the over-voltage path — it is constrained only by the charge threshold, which the converter
would remove but the clamp already covers.

**Small-cell build (3 parallel × 3 series per wing = 9 small cells/wing, 36 total; ADR-049
§Decision fallback; wing-electrical §2.2(a)):** a converter makes it *more* admissible and
does **not** make it preferable:

- **Arguments it gains:** the electrical objections to small cells were (i) current-matching
  when positions are paralleled and (ii) the resulting need for per-cell bypass. A converter
  tolerates the resulting voltage/current shifts, so these stop being *functional* constraints.
  Stock is the other gain: **~100 small panels are in hand** (ADR-049 §Measured inputs), the
  intact **large** panel count is `TODO(unverified)`.
- **Arguments it does not gain:** the **joint count** — **20 joints per wing vs 8**
  (wing-electrical §2.3/§3b-ii), i.e. **108 hand-soldered joints per aircraft vs 36**
  (ADR-049 §Decision). This is a labour and reliability cost the converter does not touch, on
  an operator who hand-solders everything.
- **Neutral:** board area is **the same within 0.3 %** — 114.4 cm² for the 9-small wing vs
  114.8 cm² for the 3-large wing (wing-electrical §3(b-ii)); the small build is lighter per
  wing (4.5 g vs 6 g of cells).

**Verdict on (d):** a converter removes the *series count* argument (which the clamp already
covers) but not the *joint-count* argument, which is the decisive one for the large cell. The
small-cell build remains the **fallback if the large-panel count fails** (ADR-049 §Decision),
not the preferred build, with or without a converter.

---

## 6. THE REDUNDANCY PRICE — full power with N−1 wings

If the requirement is **full peak power with N−1 wings**, then each remaining wing must
**alone** exceed the load:

```
required per wing  = P_radio_peak = 6.1495 W
at 6.0 V that needs  I = 6.1495 / 6.0 V = 1.0248 A
one 12-large-cell series string gives 6.0 V × 1.2 A = 7.20 W   →  it qualifies
⇒ each self-contained 6 V wing must be 12 LARGE cells            (identical to §1.2)
⇒ 4 such wings = 48 cells
```

| Quantity | Value | vs accepted 12-cell array |
|---|---:|---:|
| Cells | **48** | **4.00×** |
| Installed cell area | **1466.7 cm²** | 4.00× |
| Cell mass | **72.0 g** | **+54.0 g** (18.0 → 72.0 g) |
| Array peak power | 28.80 W | 4.00× |
| Wing board area (per wing) | **459.2–580.1 cm²** (from §1.3) | ~4× ADR-049's 145.0 cm² arm |
| FR4 carrier at 127.6 mg/cm², if full-area | **58.6 g/wing → 234.4 g** for 4 wings | (ADR-049 rejects full-area FR4 outright) |
| Charge path current (parallel 6 V buses) | **4.8 A** at 6.0 V | **4.00×** the accepted 1.2 A |

Notes that matter:

- **The FR4 figure is the rejected one and is shown to make the point, not to propose it.**
  ADR-049 §rejected-options table rejects the full-area carrier precisely because
  0.6 mm FR4 is **127.6 mg/cm² vs 48.9 mg/cm² per cell area — 2.61× heavier per unit area than
  the silicon it carries**. The real carrier is spine+ribs, which is lighter — but it still
  scales with the installed area, so 4× the cells is 4× the frame.
- **Paralleling four 6 V wings is a second change nobody has quoted.** To avoid the series-cut
  problem the four self-contained wings must be wired in **parallel**, which means the charge
  path, the BAT54 stack diode, the clamp and the hub copper all move from **1.2 A to 4.8 A**
  (4×), and the wing-to-hub tab lands — currently **4.0 × 1.2 mm ≈ 2.7 A at 1 oz / 10 °C**
  (wing-electrical §6.3) — are then **under-rated**.
- **And the mission does not need it.** Three wings already deliver **5.40 W = 13.92×** the
  0.388 W average draw; the loss of one wing costs TX power, not mission life (§3).

**Verdict, plainly: the N−1 full-power array is NOT consistent with mass being the binding
constraint.** It is **+54.0 g of cells** (4.00×), plus ~4× the wing frame and 4× the array
area on a 50 N payload, to buy protection that the mission's duty cycle does not require.
**REJECT.**

---

## 7. RECOMMENDATION

> **Keep the accepted direct-connected 12-cell series array (ADR-006, Accepted) with a single
> cell class (ADR-049, Proposed), fit the per-wing bypass Schottky at ≥ 2 A / 40 V instead of
> DNP, keep the mandated shunt clamp, and ACCEPT A REDUCED TX POWER OF ABOUT −1.6 dB AFTER THE
> LOSS OF ONE WING. Do not build per-wing 6 V. Do not add a per-wing converter or a charge-path
> MPPT converter. Do not oversize the array.**

**The deciding number:** `P_radio_peak ÷ P_average = 6.1495 W ÷ 0.388 W = 15.85×` — the
mission's average draw is **15.85×** below the radio's peak, and three wings still deliver
**13.92×** the average. Every option that buys redundancy is sizing against the **peak**, i.e.
against a condition that lasts 1 % of the time; the **duty cycle**, not the topology, is what
makes a wing loss survivable.

**The one thing that must change (and is already on the record):** the per-wing bypass
Schottky. ADR-046 §2.3 mandates it, ADR-048 §2.3 places it, and ADR-049 §Consequences clause 1
re-rates it to **≥ 2 A / 40 V** (SS24 / PMEG4020ER class) because the BAT54 family
(200 mA / 30 V) is **6× under-rated** for a 1.2 A string even before the large cell was chosen.
It is DNP for the first build. **Fit it.** It is the difference between "one lost wing kills
the array" and "one lost wing costs −1.6 dB of TX power and the mission continues" — and at
four diodes it is the cheapest change in this analysis.

**The condition under which the recommendation flips:**

- If the operator decides that the vehicle must **keep flying after losing TWO wings**, then
  no array/parallel scheme with 4 wings works (§3.2: 2 wings top the bank at 2.70 V, below the
  radio's 3.0 V minimum) and the answer is a **charge-path MPPT converter** — the only option
  that lets 3.0 V of array charge a 5.4 V bank — pending its measured efficiency (break-even
  5.10 V of bank voltage at η = 85 %, §5b) and its EMI bench numbers (§5c).
- If a **bench measurement** shows the sagged rail breaks the mission link at 4.2 V, the
  converter returns with the measurement in hand — which is the evidence-driven order ADR-044
  §4 already prescribes for the radio-rail question, applied to the charge path.

### 7.1 What each alternative forces on ADR-006 (Accepted → explicit supersede required)

| Alternative | What it changes in ADR-006 | Supersede / amendment burden |
|---|---|---|
| **Per-wing 6 V (48 cells)** | ADR-006 §Power-Architektur — "4 Wings, je 3 Solarzellen in Serie" and "Alle 4 Wings in SERIES" — becomes 12 cells per wing and a parallel bus; the array line 2.4 W / 6.0 V / 400 mA goes to 28.8 W | **Explicit supersede of ADR-006 required**, plus amendments to ADR-046 (outline, tab, series order), ADR-048 (series wiring → parallel bus), ADR-049 (wing outline, cell count) and a re-rate of the whole charge path to 4.8 A |
| **Per-wing converter** | breaks ADR-006's direct `Solarzellen → Schottky → Supercap` element (there is no converter in that block) | **Explicit supersede of ADR-006 required**; re-opens ADR-047 §5's refusal and re-triggers ADR-044 §3 option (b)'s three re-freezes (BOM, placement keep-out, ADR-032 EMI simulation) |
| **Single charge-path MPPT** | same as above — it deletes the direct connection | **Explicit supersede of ADR-006 required**; argument must be made against ADR-044 §3 option (b) / ADR-047 §5 (different converter, same objection class: mass, I<sub>Q</sub>, EMI) |
| **Oversize for N−1** | ADR-006's 12-cell array and the bank's 1.65 F / 5.4 V sizing premise; wing geometry (ADR-049); mass budget | **Explicit supersede of ADR-006 required**; contradicts "mass is the binding constraint" and forces changes to ADR-046/048/049 |
| **Keep the accepted design + reduced TX after a loss (RECOMMENDED)** | **nothing** — the array, bank, Schottky, LDO and series count are untouched | **No supersede needed.** ADR-006 stands as Accepted. The only edits are the ones already recorded as needed: the bypass diode rating (ADR-046 §2.3 per ADR-049 clause 1) and the clamp (ADR-049 clause 3) |

**Stated plainly, as asked:** yes — the recommendation is **"keep the accepted design and
accept a reduced TX duty after a loss."**

---

## 8. Failure modes, ranked by severity × likelihood

| # | Failure | Severity × Likelihood | Mitigation |
|---|---|---|---|
| 1 | One wing lost with the bypass diode **DNP** (current first-build state) → whole array dead, shaded cells reverse-stressed | **S5 × L4 = 20** | **Fit the bypass Schottky (≥ 2 A / 40 V).** Listed as "DNP for the first prototype" in ADR-046 §2.3 / ADR-048 §2.3 — this is the top item to change |
| 2 | One wing lost with the bypass fitted → bank tops at 4.2 V, TX power −1.56 dB, full 2 W unavailable | S2 × L3 = 6 | none — **accepted**. ADR-036's energy-gated, daylight-only TX policy is exactly the regime that tolerates it; firmware already reduces power rather than claiming it (ADR-047 §6.2 R4) |
| 3 | Two wings lost → bank tops at 2.70 V, radio minimum 3.0 V and LDO input unreachable → mission over | S5 × L2 = 10 | none with the accepted topology — **accepted**. Requires a charge-path MPPT to survive (§5); measured against the mission average (13.92× margin with 3 wings) this is the residual risk the operator must accept or pay 4× to remove |
| 4 | Cold open-circuit voltage (~9.3 V) over-volts the bank / radio | S5 × L3 = 15 | the mandated **shunt clamp** (ADR-047 §7, ADR-049 clause 3). Set point still `TODO(unverified)` — the window is 5.4 V to an unpublished damage threshold |
| 5 | Array-side diode/current-path re-rate mistaken if the array is ever paralleled | S4 × L2 = 8 | keep the array in **series**; if it is ever paralleled, re-rate to 4.8 A and the wing tab lands (§6) |
| 6 | Large cell's real current (1.08 A vs 1.2 A) | S3 × L3 = 9 | `TODO(unverified)`; every large-cell number here scales linearly. Measure it (wing-electrical §0.2) |

---

## 9. Open items — every `TODO(unverified)`, gathered

1. **The large cell's maximum-power current.** 1.2 A by area scaling vs 1.08 A by the 0.54 W
   listing; never reconciled by measurement. Every large-cell number in this document scales
   linearly with it. (wing-electrical §0.2; ADR-049 §Measured inputs.)
2. **The chosen MPPT/boost part's conversion efficiency.** No part is selected; ADR-044 §3
   option (b) records the selection as not made. This document's 85 % is an **ASSUMPTION** and
   the break-even bank voltage (5.10 V) moves directly with it.
3. **A switched converter's quiescent current.** Part-dependent (ADR-044 §3 option (b)); the
   bank's night budget is at the 100 µW scale, and the converter sits on the raw VSCAP node.
4. **EMI of a charge-path converter.** Not measured. Verification: ADR-029 §5 tests 1 and 3
   (< 3 dB 2.4 GHz noise-floor rise; < 1 dB GNSS C/N0 drop), plus conducted ripple on VSCAP
   against ADR-029 §5 test 4 (< 20 mV rail dip).
5. **The cells' temperature coefficients and the array's −60 °C open-circuit voltage.**
   The 7.44 V / 9.58 V span in §2 rests on an assumed `V_OC(25 °C) = 0.62 V` and
   `−2.1 mV/°C/cell` (wing-electrical §5.1), neither measured. Carried from ADR-047 §7.
6. **The F33's actual damage threshold** and therefore the clamp's set point — unpublished
   in datasheet Rev 1.1 (ADR-047 §7).
7. **Per-cell masses** (component-guide figures, not weighed) — wing-electrical §3a.
8. **The intact large-panel count** — ADR-049 §Open items. This is what decides between the
   preferred large-cell build and the 9-small-cell fallback.
9. **The supercap cell ESR**, on which ADR-047 §4's rail-step numbers depend — not in this
   repository (ADR-047 §3/§4).
10. **In-flight studies not duplicated here:** the wing **release/jettison** analysis
    (`analysis/wing-jettison`, `5365dac`) and the **geometry/insolation** analyses
    (`wing-insolation`, `wing-omni`, `wing-ngon`, `wing-ladder`; `wing-insolation-geometry.md`)
    — both are cited, neither is re-derived.

---

## 10. Sources cited

- `docs/adr/006-supercapacitor-power.md` (**Accepted**) — 4 wings × 3 cells series, 6.0 V,
  BAT54, bank 1.65 F @ 5.4 V, TPS7A02, the direct-connection architecture.
- `docs/adr/036-energy-policy-burst-storage-daylight-only-tx.md` — burst-sized storage,
  daylight-only and energy-gated TX, the 100 µW night anchor.
- `docs/adr/044-v9-power-rails.md` — option (b) boost REFUSED for the radio rail (**EMI, mass,
  I<sub>Q</sub>**), the three forced re-freezes, the 5.4 V vs 5.5 V margin.
- `docs/adr/046-wing-board-interface.md` §2.3 (series order, per-wing bypass Schottky, DNP),
  §3.2 (176.0 × 25.0 mm outline).
- `docs/adr/047-v9-power-provisioning.md` §1.2 (**6.15 W**), §2 (VSCAP = the radio's VCC),
  §3 (bank 1.65 F / 3.3 F), §4 (rail step; capacitors buffer, do not hold), §5 (the refusal and
  the voltage-vs-power table), §6.2 (firmware power reduction), §7 (over-voltage, clamp).
- `docs/adr/048-v9-hub-wing-interfaces.md` §2.3 — 4 hub sockets, series wiring, DNP bypass.
- `docs/adr/049-wing-architecture.md` — **large cell class, 12 cells, 7.2 W**; the four-wing
  vertical recommendation; clause 1 (bypass re-rate ≥ 2 A / 40 V), clause 3 (clamp required,
  must sink 1.2 A); rejected-options table (full-area FR4 127.6 mg/cm²; half-shape 3.0 V
  cannot charge the 5.4 V bank); the 9-small-cell fallback; open items.
- `docs/analysis/wing-electrical.md` — cell data and area arithmetic §0.1; the large-cell
  current conflict §0.2; series/parallel rules §1; per-wing power and joint counts §2.3/§7;
  only-large and matched-small outcomes §3; bypass and diode ratings §4; charge-path
  over-voltage arithmetic and the `n ≥ 11.4` / `n ≤ 6` derivation §5; conductor and tab-land
  ampacity §6.
- `docs/POWER-BUDGET-V9-D2BE.md` §2 — the load table, the **0.388 W** representative daylight
  average and the **1 % TX duty**; §4 — board 55.15 × 45.15 × 0.6 mm and the mass table.
- `docs/component-guide.md` — per-cell masses, cell options.
- In flight (cited, not duplicated): `analysis/wing-jettison` (`5365dac`), `analysis/wing-insolation`,
  `analysis/wing-omni`, `analysis/wing-ngon`, `analysis/wing-ladder`, `docs/analysis/wing-insolation-geometry.md`.
