# Wing insolation geometry and orientation — consultant analysis

**STATUS: CONSULTANT ANALYSIS — input to a decision; it is NOT a decision record.**
Nothing here is an operator decision, an accepted ADR, or an implementation authorisation.
Every number is either (i) printed by the committed script
`docs/analysis/insolation_factors.py` (run it to reproduce), (ii) cited to an in-repo
source, or (iii) carries an explicit `TODO(unverified)` naming the open question.

- Date: 2026-10-07
- Branch: `analysis/wing-insolation` (worktree `/home/c03rad0r/worktrees/bf-wingsun`)
- Base: `76dd04d` (main tip)
- Lens: **insolation geometry and wing orientation only.** Mass, structural, thermal,
  layout/fab and electrical-I-V analyses are other consultants' deliverables and are
  not duplicated here (§7 lists the boundaries explicitly).

---

## 0. What the repo actually says about wing orientation (the determination asked for)

The task asks whether the resulting wing planes end up **HORIZONTAL** or **VERTICAL**.
The repo does not state it in one place, and its records **contradict each other**:

| Source | What it says | Reading |
|---|---|---|
| `docs/hardware-design.md` §3D-Assembly (lines 140–158) | "Hub-Board **waagerecht** halten"; wing 1 through the N slot "(**horizontal**, Yagi zeigt nach Norden)", wing 2 horizontal, wings 3–4 "nach unten **geneigt ~30°**"; result "Abdeckung des gesamten **unteren Halbraums**" | a mostly-flat cross, two arms drooped 30°; a lower-hemisphere **antenna**-coverage statement |
| `docs/adr/046-wing-board-interface.md` §4.1 (line 272) | "Attach angle **90° to the hub plane, wing plane normal to the hub plane**" | wing plane **perpendicular** to the hub plane = vertical (if the hub is horizontal) |
| `docs/WING-TO-HUB-SOCKET-SPEC.md` §1 (lines 25–29) | "the wing's **long axis is perpendicular to the hub plane**" **and**, two sentences later, "Wings 1–2 **horizontal** in the hub plane (3–4 inclined ≈30° below it)" | **self-contradictory** within one paragraph |
| `docs/adr/048-v9-hub-wing-interfaces.md` §5 item 6 = sheet `OPEN-23` | records exactly that contradiction and says "**The footprint therefore asserts no rotation**" | the conflict is **already filed as open** |

**Determination (derived, not cited) — the wing planes are VERTICAL, i.e. perpendicular to
the hub plane.** The decisive evidence is the tab/slot arithmetic, which is self-consistent
in both records and physically excludes the "coplanar with the hub" reading:

1. `ADR-046 §4.1`: slot **0.9 mm wide** × 6.0 mm deep, wing tab thickness 0.6 mm
   (= substrate, `hardware-design.md` line 63/195), and **"Nominal solder gap 0.30 mm
   (0.9 mm slot − 0.6 mm tab)"**. That equation is only meaningful if the slot's **width
   direction is the tab's thickness direction**.
2. The tab is a plate of the wing PCB; its thickness direction is **normal to the wing
   plane**. Therefore the slot's width direction is the wing-plane normal direction.
3. An `Edge.Cuts` slot is a **through-cut in the hub's plane**: both its 0.9 mm width and
   its 6.0 mm depth lie **in the hub plane**, and it is open through the hub's thickness.
   So the slot-width direction lies in the hub plane, hence the wing-plane normal lies in
   the hub plane, hence **the wing plane is perpendicular to the hub plane → VERTICAL**.
4. The same conclusion follows from the tab **width**: the tab is **9.0 mm** wide
   (`ADR-046 §2.1`), which cannot fit a 6.0 mm deep in-plane slot; its 9.0 mm must
   therefore be the out-of-plane (vertical) extent, which is unconstrained by a 0.6–1.6 mm
   thick hub. A tab lying **in** the hub plane, 0.6 mm thick, cannot enter a 0.9 mm
   in-plane slit at all — so the coplanar/horizontal reading is mechanically impossible.

Consequences of the determination:

- The `hardware-design.md` phrase "wing 1 … horizontal" is then read as **the wing extends
  horizontally** (its long axis lies in the hub plane and points radially outward), **not**
  "the wing plane is horizontal" — the latter is excluded by point 4. The socket spec's
  "long axis is perpendicular to the hub plane" is the phrase that is **wrong**.
- The four wings are four **near-vertical blades** whose planes radiate at **90° azimuth
  spacing**, each blade's **normal horizontal** (or, if leaned, tilted up by the lean).
  That is exactly the geometry analysed below.
- `TODO(unverified)` — the ±30° droop of wings 3–4: `hardware-design.md` lines 143–144 give
  it as an **antenna-coverage** measure ("Abdeckung des unteren Halbraums"), and the wing
  antenna is **V2-only and absent on v9** (`ADR-046 §2.4`: "the wing's 2.4 GHz PCB Yagi is
  deferred to V2 and is NOT etched on the v9 wing"). On a solar-only v9 wing the droop has
  no v9 rationale, and it costs solar (a normal 30° **below** horizontal sees the sun at
  incidence *h*+30°, e.g. `cos(46.56°) = 0.688` vs 0.958 for vertical at noon). **Whether
  the droop is retained on v9 is not recorded anywhere in the repo.** This document
  therefore analyses a **symmetric** four-blade array and treats the droop as open.

---

## 1. The baseline comparison (winter sun at 50 °N)

**Site/season assumption.** No latitude, launch site, month or date is stated anywhere in
the repo (searched `docs/` for latitude / launch site / solstice / insolation / azimuth /
Breitengrad / Startplatz: **0 matches**). Assumed: **latitude φ = 50.0 °N**, **winter
solstice**, declination **δ = −23.44°**. → `TODO(unverified)`: the actual launch latitude
and season; both change every number below (see §7).

Noon solar elevation (`90 − |φ − δ|`):

```
h_noon = 90 − |50.0 − (−23.44)| = 90 − 73.44 = 16.56°
```

Day length (hour angle at sunset, `cos H₀ = −tan φ · tan δ`):

```
H₀ = arccos(−tan 50° · tan(−23.44°)) = arccos(0.5167) = 58.888°
day length = 2 × 58.888° / 15 °/h = 7.85 h
```

With the sun only **16.56° above the horizon**, the per-unit-area factor
`f = cos(incidence)` of a flat panel is:

| Case | Normal | `f = cos(incidence)` | Value |
|---|---|---|---|
| **(a) HORIZONTAL panel** (normal straight up) | elevation 90° | `sin h` = sin 16.56° | **0.2850** |
| **(b) VERTICAL panel, normal facing the sun azimuth** | elevation 0°, azimuth = sun's | `cos h` = cos 16.56° | **0.9585** |
| **(c) OPTIMAL fixed tilt at noon** | normal at the sun → elevation = h | `cos 0` = 1 | **1.0000** |

**(c) the optimal tilt (derivation).** A panel plane tilted **β** from the horizontal has
its normal at elevation `90° − β`. To point the normal at the sun the normal elevation must
equal the sun elevation, so

```
β_opt(noon) = 90° − h_noon = 90 − 16.56 = 73.44°   (i.e. 16.56° from VERTICAL)
β_opt(sunrise/sunset, h = 0) = 90° − 0 = 90°       (i.e. exactly VERTICAL)
```

A single fixed tilt cannot be optimal at both: the **noon-optimal 73.44°** panel, evaluated
at `h = 0` with its azimuth aligned, gives `cos(90° − 73.44° − 0) = cos 16.56° = 0.9585`
instead of 1.0 — a 4.2 % loss at dawn/dusk for the noon-optimal tilt.

**Ratio (a)/(b)** and the headline:

```
(a)/(b) = sin h / cos h = tan h = tan 16.56° = 0.2974
(b)/(a) = cos h / sin h = 3.363
```

> **Headline (noon only):** a **horizontal** panel is **3.36× worse** than a **vertical**
> panel whose normal faces the sun — it captures **29.7 %** (`tan h`) of what the
> sun-facing vertical panel captures. Equivalently, at 50 °N winter noon a horizontal panel
> is almost **edge-on** to the sun, while a sun-facing vertical panel is almost **face-on**.

**But this headline is conditional on the panel FACING the sun, which this payload cannot
do** (no attitude control; azimuth uncontrolled). Once the azimuth is uncontrolled the
advantage collapses — see §2, where the same two panels become 0.305 vs 0.285 per unit
area (a factor of only **1.07** at noon). Stating §1's 3.36× without §2 would overstate the
case by an order of magnitude, so the two must be read together.

---

## 2. Rotation — average cos(incidence) over 360° of uncontrolled azimuth

Model: the sun is held in the azimuth plane (azimuth 0) at elevation `h`. A panel whose
plane is tilted **β from the horizontal** and whose azimuth (i.e. the payload's rotation) is
`ψ` has normal `n = (sin β cos ψ, sin β sin ψ, cos β)`; the sun is
`s = (cos h, 0, sin h)`, so

```
cos(incidence) = s·n = sin h cos β  +  cos h sin β · cos ψ  ≡  a + b·cos ψ
a = sin h · cos β        b = cos h · sin β
```

A flat panel facing away (negative cosine) delivers **zero**, so the average is of the
**positive part**:

```
                  1   ⎧ 2π
  <F>₁(β,h)  =  ───  ⎨      max(0, a + b cos ψ) dψ
                 2π  ⎩ 0
             =  a                                   if a ≥ b
             = ( a·ψ₀ + √(b² − a²) ) / π            if a < b,   ψ₀ = arccos(−a/b)
```

**One arm (single panel).** For a **vertical** blade (β = 90°): `a = 0`, `b = cos h`, `ψ₀ = π/2` →

```
  <F>₁ = cos h / π = 0.9585 / π = 0.30511
```

This is the classic body-mounted figure. Note the two standard averages that appear here and
elsewhere: over a full rotation `<|cos ψ|> = 2/π = 0.6366`, while the **useful** average
`<max(0,cos ψ)> = 1/π = 0.3183` — exactly half. A single-sided panel earns only the
`1/π = 0.318` (it is dark for half the rotation); `2/π` is what an opposed **pair** of arms
earns (`<|cos ψ|>` per arm summed over the pair).

**Four-arm cross (90° spacing).** Arms sit at azimuths `ψ + 90k`, so

```
  T(ψ) = Σₖ₌₀³ max( 0, a + b·cos(ψ + kπ/2) )
```

`k`-fold symmetry makes `T` periodic in **90°**, and each arm's rotation-average is the same,
so `<T> = 4·<F>₁`. For the **vertical** cross (a = 0) the closed form is exact:

```
  T(ψ) = ( |cos ψ| + |sin ψ| ) · cos h
  min  at ψ = 0° (sun on one arm) : 1.0000 · cos h = 0.95852
  max  at ψ = 45° (sun between two): √2     · cos h = 1.35555
  mean                             : 4/π    · cos h = 1.22043
```

as a fraction of the 4× nameplate: **min 0.2396, max 0.3389, mean 0.3051**.

**Horizontal array (β = 0).** `a = sin h, b = 0`, so the factor is **`sin h` at every
rotation angle** — genuinely rotation-independent:

```
  per panel = 0.28502 ;  4-arm total = 1.14008   (constant)
```

**Comparison (noon):**

```
  vertical cross mean 1.22043 / horizontal total 1.14008 = 1.0705   (+7.1 % only)
  day-mean single vertical arm  = <cos h>/π = 0.31149
  day-mean single horizontal arm= <sin h>   = 0.18653
  day ratio vertical/horizontal = 1.6699     (+67 %)
```

> **How much of the installed area does a rotating 4-arm cross harvest?** Installed area =
> 4 panels. The vertical cross's rotation-average total is `(4/π)·cos h = 1.2204`, i.e.
> **0.305 per installed panel** — **30.5 %** of nameplate, ranging 24.0 % (sun on one blade)
> to 33.9 % (sun at 45°). The `2/π = 0.637` figure is *not* the per-panel yield; it is the
> average of `|cos|`, which a single-sided panel only earns at half rate (`1/π`). The
> consequence is the whole point: **a rotating 4-arm cross throws away ≈ 70 % of its
> installed area at any instant**, and it only recovers the horizontal array's *noon* factor
> (0.285 vs 0.305, +7 %). Its real advantage is **daily**, not at noon.

---

## 2b. The series-string consequence — this changes the decision

`ADR-046 §2.3` wires **all four wings in ONE series string** (W1.P → … → W4.N, 6.0 V). In a
series string the **current is set by the weakest illuminated wing** and the voltage is the
sum of the illuminated wings. With an ideal per-wing bypass diode (the `D_BP1..D_BP4`
provisions, **DNP** in `ADR-046 §2.3` / `WING-TO-HUB-SOCKET-SPEC §5`) the best string
operating point is

```
  P / P_ideal = max_{j=1..4} ( j · cos_(j) ) / 4      cos_(j) = j-th LARGEST of the four
                                                       instantaneous cos(incidence)
  with NO bypass the string is limited by the unlit wing → P ≈ 0.
```

Results (script section `(2b)`):

| β | series P/P_ideal, noon | series P/P_ideal, day |
|---|---|---|
| 0° (horizontal cross) | **0.28502** (= sin h, no mismatch) | 0.18629 |
| 90° (vertical blades) | 0.25069 | **0.25589** |

Detailed instants at noon for the **vertical** cross: `ψ = 0°` (one blade dead-on the sun,
the two perpendicular blades exactly edge-on, `cos = 0`) → **0.2396**; `ψ = 45°` (all four
equally lit) → **0.3389**.

Two consequences, both decisive:

1. **The vertical cross is a mismatch machine.** At `ψ = 0, 90, 180, 270°` two blades are
   *exactly* edge-on (`cos(incidence) = 0` for any sun elevation — it is a geometric zero,
   not an approximation). In an unbbypassed series string the whole array therefore
   **drops to ≈ 0 four times per rotation**. **A vertical-blade array REQUIRES the four
   bypass Schottkys to be FITTED, not DNP.** `ADR-046 §2.3` already provisions them
   (a population change, not a respin), so this is a build decision, not a redesign.
2. **Because of the mismatch, the ranking flips at noon.** Series noon: horizontal
   **0.285** vs vertical **0.251** — the flat cross is **13.7 % better at noon**
   (`0.28502/0.25069 = 1.1369`). Over the **whole day** the ranking is the other way:
   vertical **0.2559** vs horizontal **0.1863** → the vertical cross is **1.374×**
   (**+37 %** daily), because `sin h` collapses at low sun while `cos h/π` does not.

`TODO(unverified)` — the above is a **flux/current** comparison. The array must also reach
the bank's **charging voltage**: the bank sits at **5.4 V** (`POWER-BUDGET-V9-D2BE §2`), the
string is 4 × 1.5 V = 6.0 V when all four wings are unbypassed, but drops to **3.0–4.5 V**
when 1–2 wings are bypassed. Whether a given geometry spends enough time above the bank
voltage (and above the `TPS7A02` 3.3 V LDO input) is an **electrical-I-V question, not
geometry**; no in-repo source computes loaded `V_mp` for the 52 × 19 mm cell
(`POWER-BUDGET-V9-D2BE` line 33's per-wing "2.964 cm²" is also a factor-10 typo — it should
be 29.64 cm²; the total "≈ 120 cm²" is right). **This document does not resolve it.**

---

## 3. Tilt versus vertical (4-arm cross, 90° spacing)

Sweep of wing tilt **β** (angle of the wing plane from the horizontal; β = 90° is a vertical
blade, β = 0° is the flat cross). Day-average uses the **time weighting: equal time per unit
hour angle H** (the sun's hour angle advances at a constant 15 °/h), integrated over the
sunny half-day — i.e. `mean_H [ <F>₁(β, h(H)) ]`, with
`sin h(H) = sin φ sin δ + cos φ cos δ cos H`, `H ∈ [0, H₀]`.

```
β(deg)   4-arm@noon    4-arm day  series@noon  series day
     0      1.14008      0.74612      0.28502     0.18629
     5      1.13574      0.75087      0.21022     0.13311
    10      1.12276      0.76644      0.18673     0.13268
    15      1.10123      0.79650      0.19375     0.14535
    20      1.10243      0.85200      0.20202     0.15924
    25      1.14136      0.92012      0.21037     0.17391
    30      1.18676      0.98840      0.22128     0.18924
    35      1.23108      1.05307      0.23298     0.20397
    40      1.27094      1.11219      0.24345     0.21742
    45      1.30449      1.16454      0.25243     0.22938
    50      1.33057      1.20927      0.25974     0.23974
    55      1.34843      1.24577      0.26529     0.24838
    60      1.35755      1.27357      0.26898     0.25521
    65      1.35764      1.29234      0.27077     0.26017
    70      1.34851      1.30185      0.27062     0.26321
    75      1.33012      1.30197      0.26852     0.26432
    80      1.30253      1.29264      0.26449     0.26346
    85      1.26588      1.27393      0.25853     0.26063
    90      1.22043      1.24594      0.25069     0.25589
```

Optima (0.5° grid):

| Metric | optimal β | value | vs plain vertical (β=90°) |
|---|---|---|---|
| geometric, noon | **62.5°** | 1.35874 | +11.3 % (vertical = 1.22043) |
| geometric, whole day | **72.5°** | 1.30309 | **+4.6 %** (vertical = 1.24594) |
| series, noon | **0°** | 0.28502 | +13.7 % **in favour of horizontal** |
| series, whole day | **75.5°** | 0.26432 | **+3.3 %** (vertical = 0.25589) |

> **Is the gain a few percent or a large factor? A few percent.** The single best fixed tilt
> beats plain vertical by **+3.3 % (series, whole day)** to **+11.3 % (geometric, noon)** —
> never more than ~11 %. The **large** factor in this problem is **vertical vs horizontal**,
> not tilt vs vertical (§2b). Note also that the series metric is not monotone in β: at
> β = 5–10° it *crashes* (0.133) because a nearly-flat cross with real four-fold azimuth
> structure has the worst mismatch of all.

---

## 4. The shapes, judged as concrete geometries

**(a) A flat horizontal cross** (all four wings in one plane = the hub plane, β = 0).

- Factor: **0.2850 per panel at noon, rotation-independent**; 4-arm total 1.14008; series
  noon **0.28502**; **series whole-day 0.18629**.
- Trade-offs: it is the **only shape with zero mismatch** — all four panels are equally
  illuminated, so the series string is automatically matched and **no bypass diodes are
  needed**; smallest cube span and lowest cantilever moment; the simplest hub (the wings
  simply continue the hub plane). Its cost is that it is nearly edge-on at noon and that its
  daily yield is the lowest of the three (0.186 series-day).
- `TODO(unverified)`: `hardware-design.md` lines 141–144's "wings 1–2 horizontal, 3–4 ~30°
  drooped" is a *mixed* flat cross, not the pure β=0 case; the 30° droop lowers arms 3–4's
  factor to `cos(h+30°)` and is analysed only as a variant.

**(b) Four vertical blades at 90° azimuth** (β = 90°; the geometry §0 derives).

- Factor: per-panel rotation-average **0.30511**; 4-arm total **min 0.9585 / max 1.3556 /
  mean 1.2204**; series noon 0.25069, **series whole-day 0.25589**.
- Trade-offs: **best whole-day yield** (1.37× the flat cross, series) and it needs no tilt
  hardware (the existing straight radial slot gives it). Cost: **it mandates the bypass
  diodes** (`ADR-046 §2.3`, currently DNP), the string voltage falls to 3.0–4.5 V when wings
  are bypassed (§2b `TODO`), and it is **13.7 % worse at noon** than the flat cross.

**(c) A V / inverted-V — two half-panels per arm at 75° and 40° from horizontal.**

Equal-area halves, so the arm's rotation-average is `0.5·<F>₁(75°) + 0.5·<F>₁(40°)`:

```
noon: 0.5×0.33253 + 0.5×0.31774 = 0.32513     day: 0.30177
a single full-area panel at the best single tilt (62.5°) :
noon 0.33969      day 0.32577
```

| Comparison (same installed area) | noon | whole day |
|---|---|---|
| V / single optimally-tilted panel | 0.9572 (**−4.3 %**) | 0.9263 (**−7.4 %**) |
| V / plain vertical | 1.0656 (+6.6 %) | 0.9688 (−3.3 %) |

**Fraction of area each half-panel gives up** (vs the best single tilt): the 75° half is
0.33253/0.33969 = **−2.1 %**; the 40° half is 0.31774/0.33969 = **−6.5 %**. Each half is
also only **half the area**, so per arm the V spends the same area to earn a factor
*below* the single tilt.

> **Answer: no.** Covering two elevations per arm does **not** beat spending the same area on
> one well-tilted panel — it costs **4.3 % (noon) to 7.4 % (daily)**. The reason is that on a
> **rotating, azimuth-uncontrolled** payload the *elevation* spread is already swept by the
> rotation and by the single tilt; adding a second tilt adds mismatch and area-splitting
> losses without adding any new place the sun can be caught. A second concrete obstacle:
> 3 cells cannot be split into two equal halves, so a V forces **4 cells/wing (16 cells)**
> or an asymmetric split — a cell-count/population change, not a geometry tweak.

**(d) A cone/funnel of four panels leaning ~17° from vertical** (= β = 73.44°, the
winter-noon optimum of §1(c); the four normals then point outward at elevation 16.56°).

- Factor: 4-arm total **noon 1.33685, day 1.30294** (geometric); series whole-day, the
  best tilt is 75.5° at 0.26432 vs vertical 0.25589 → **+3.3 %**.
- Comparison with plain vertical: **+9.5 % at noon, +4.6 % over the whole day** (geometric);
  **+3.3 %** whole-day on the series metric.
- **Is the lean worth the mechanical complexity?** The gain is **3–10 %, not a factor**.
  Against it: the tab is a plate in the wing plane (`§0` point 2), so a leaned wing needs
  either a **cranked/angled tab** or a **non-radial slot** — a new mechanical feature and a
  new tolerance on four hand-soldered joints. The 0.30 mm nominal slot gap (`ADR-046 §4.1`)
  can leave only a few degrees of free tilt. **Quantified:** the 0.30 mm nominal solder gap
  over the 6.0 mm insertion depth is an angular play of
  `atan(0.15/6.0) = 1.43°` to `atan(0.30/6.0) = 2.86°` — i.e. **≈ ±1.4–2.9°**, not 17°. So
  "the tilt is set at soldering time" (`WING-TO-HUB-SOCKET-SPEC §1`) **cannot** deliver a 17°
  lean in a 0.9 mm slot. **Verdict:
  not worth it for the first prototype at 3–10 %.** It becomes worth it only if the mechanical
  consultant finds a *free* way to set the tilt (e.g. a wedge boss) — then adopt ~15° from
  vertical, and expect a few percent, not a windfall.

**(e) A half-shaped wing (half the cells, one panel per arm).**

- **Energy: −50 %.** The per-unit-area factor is unchanged by size, so halving the installed
  area halves the harvested energy at the same tilt/orientation.
- **Gains:** ≈ −50 % wing/cell mass, ≈ −50 % tab cantilever load, ≈ −50 % cube span, six
  fewer cell solder joints, faster assembly. (Mass/structural verification is the mass
  consultant's deliverable; the figures here are statements about area, not measured mass.)
- **A hard disqualifier on one reading:** if "half the cells" means **half the cell count**
  (6 cells instead of 12), the string becomes **6 × 0.5 V = 3.0 V nominal**, which is
  **below the 5.4 V bank** (`POWER-BUDGET-V9-D2BE §2`) and below the `TPS7A02` 3.3 V LDO
  input (with dropout): a 3.0 V string **cannot charge the bank at all**. Only the other
  reading — keep 12 cells but half the *area* each — keeps 6.0 V and merely halves the
  current. So a half shape is viable **only** as "same cell count, smaller cells", never as
  "fewer cells", unless a boost converter is added (the flight board has none;
  `hardware-design.md` line 202 gives a boost only to the dev board).
- `TODO(unverified)` — whether the day's recharge budget tolerates a 50 % array: that is a
  statement about the ADR-036 one-burst/day duty cycle and the measured deep-sleep current,
  neither of which is settled in-repo (`POWER-BUDGET-V9-D2BE §Night sleep`).

---

## 5. The decision-relevant answer

**(1) VERTICAL or HORIZONTAL?** **VERTICAL** (four near-vertical blades, planes radiating at
90° azimuth — the geometry §0 derives from the slot/tab arithmetic). Justification, in the
metric that matches the actual wiring (series):

```
  whole-day series yield:  vertical 0.25589  vs  horizontal 0.18629   =  1.374×  (+37 %)
  geometric whole-day    :  vertical 1.24594  vs  horizontal 0.74612   =  1.670×  (+67 %)
```

Be honest about the two caveats that go with it: (i) **this is a daily advantage, not a noon
one** — at winter noon the *series* flat cross is **13.7 % better**; and (ii) the vertical
recommendation is **conditional on fitting the four bypass Schottkys** that `ADR-046 §2.3`
already provisions as DNP, because an unbbypassed vertical cross collapses to ≈ 0 four times
per rotation. If the electrical review finds the reduced string voltage (3.0–4.5 V with
wings bypassed) cannot charge the 5.4 V bank, the safe fallback is the **flat horizontal
cross**, which needs no bypass and has no mismatch.

**(2) Recommended tilt, with the justifying number.** **β = 75° (15° from vertical)**, worth
**+3.3 % whole-day (series)** / **+4.6 % (geometric)** over plain vertical — a **few
percent**. Because the gain is small and the mechanical cost of any β < 90° is a cranked tab
or an angled slot, the **default recommendation is β = 90° (plain vertical, existing straight
radial slot, no new mechanical feature)**, and β ≈ 75° is a **refinement to adopt only if the
tilt is genuinely free**. Do not spend a jig on 3 %.

**(3) Is a V/inverted-V or a half shape worth building?** **No to both.**
- V/inverted-V: **−4.3 % (noon) to −7.4 % (daily)** versus the same area as one optimally
  tilted panel, plus it forces 4 cells/wing. Reject.
- Half shape: it is not an orientation optimisation, it is a **−50 % energy** decision that
  is only acceptable if the recharge budget allows it and only in the "same 12 cells, half
  the area" form (a 6-cell/3.0 V string cannot charge the 5.4 V bank). Reject for v9 unless
  mass is the binding constraint (mass consultant's call).

**(4) The single change that buys the most winter energy.** **Mount the wing planes
VERTICAL instead of horizontal (i.e. perpendicular to the hub plane), and fit the four
bypass Schottkys.** This one change is worth **+37 % whole-day (series)** — ten times any
tilt tweak (+3.3 %) or shape change (negative). No tilt, V, cone or half shape comes close.

---

## 6. Recommended per-arm geometry (mm) and what it forces on the hub

Convention: the wing plane is **vertical (β = 90°)**, its **long axis is radial/horizontal**
(tab-ward at the hub edge), its **width is vertical**. The three cells of one wing's
1.5 V string are laid in a row **along the long axis**, so the string runs tip-ward
(`ADR-046 §3.3`'s table; see the note below). Length formula used:
`L_body = 3·w + 2·g + 2·m`, with inter-cell gap `g = 6.0 mm` (`ADR-046 §3.3`, pitch 58 mm =
52 + 6) and end margins `m = 3.8 mm` (to reproduce `ADR-046 §3.2`'s 176 mm).

**Small cells — 52.07 × 19.65 mm (10.23 cm²)**

| Dimension | Value | Derivation |
|---|---|---|
| Cell field along the wing | 3 × 52.07 = 156.21 mm | 3 in series |
| Inter-cell gaps | 2 × 6.0 = 12.0 mm | ADR-046 §3.3 |
| End margins | 2 × 3.8 = 7.6 mm | to match ADR-046 §3.2 |
| **Body** | **175.8 ≈ 176 × 25.0 mm** | width = 19.65 + 2 × 2.68 |
| **Tab** | **8.0 (protrusion) × 9.0 (width) mm** | ADR-046 §3.2/§2.1 |
| **Total outline** | **183.8 ≈ 184 mm** | matches ADR-046 §3.2 exactly |
| Cell area / wing | 3 × 52.07 × 19.65 = 3069.5 mm² = **30.70 cm²** | |
| Array (12 cells) | **122.8 cm²** | ≈ ADR-006's "≈ 120 cm²" |

**Large cells — 78.55 × 38.90 mm (30.56 cm²), 3 in series**

| Dimension | Value | Derivation |
|---|---|---|
| Cell field along the wing | 3 × 78.55 = 235.65 mm | |
| + gaps 12.0 + margins 7.6 | → **body 255.2 × 44.2 mm** | width = 38.90 + 5.4 |
| **Total outline (with the same 8 × 9 tab)** | **263.2 mm** | |
| Cell area / wing | **91.67 cm²** | |
| Array (12 cells) | **366.7 cm²** | 3.0× the small-cell array |
| **Alternative packing** (stack the 38.90 mm dimension along the wing) | body **136.3 × 83.9 mm**, total **144.3 mm** | squarer, shorter, taller |

`TODO(unverified)` — `ADR-046 §3.3`'s **prose** says the cells' "52 mm dimension [is] across
the wing (y)" while its **own table** puts the 52 mm along x (x span 4…56) and the 19 mm
across (y span 3…22). At a 25 mm wing width the prose cannot hold (52 mm across a 25 mm
wing); the **table** is the self-consistent reading and is what this document uses. The prose
defect is recorded, not resolved, here (wing-layout consultant's item).

**What the recommended geometry forces on the hub** (hub mechanics beyond the slot count are
the hub consultant's deliverable; these are the *inputs* insolation geometry imposes):

| Hub item | Requirement | Why |
|---|---|---|
| **Number of slots** | **4, at 90° azimuth spacing — unchanged** (`ADR-048 §2.1`) | four arms, four normals at 90°, is what the rotation-average assumes |
| **Slot orientation** | each slot **in the hub plane, on its edge's centre-line, its long (6.0 mm) axis RADIAL**; the slot's **0.9 mm width is across the hub edge (tangential)** | so the inserted tab's plane is **perpendicular to the hub plane** → vertical blade (§0) |
| **Tab angle** | **90° to the hub plane, straight** (for β = 90°). For a β = 75° lean the tab must be **cranked 15° off the wing plane**, or the slot cut **15° non-radial**; both are new features — the reason §5(2) defaults to β = 90° | the tab lies in the wing plane (§0), so a leaned wing needs a bent tab or an angled slot |
| **Slot fit check** | 9.0 mm tab centred on a 22 mm edge → (22 − 9)/2 = **6.5 mm per side** (`ADR-048 §2.4`), so the 4 slots do not interfere at either cell size; the **large-cell** wing is wider (44 mm) but its tab is still 9 mm, so the edge still fits | `ADR-048 §2.4` |
| **Bypass diodes** | **FIT `D_BP1..D_BP4`** (currently DNP) if the array is vertical | §2b: unbbypassed vertical string ≈ 0 four times per rotation |
| **Series topology** | **unchanged** (W1.P → … → W4.N) — but note the vertical array spends part of the rotation at 3.0–4.5 V (bypassed wings) | `ADR-046 §2.3`; §2b `TODO` |

**Span consequence of the cell choice** (stated, not judged — structural): the small-cell
wing's 4-arm diameter is 2 × 183.8 = **367.6 mm** and the assembly's vertical extent is ≈ 25 mm;
the large-cell wing's is 2 × 263.2 = **526.5 mm** with 44 mm vertical extent (or 2 × 144.3 =
**288.6 mm** with 84 mm for the alternate packing). The large cell multiplies the array area by
**3.0×** (122.8 → 366.7 cm²) and the cantilever length by **1.43×**.

---

## 7. Boundaries and `TODO(unverified)` register

Everything below is **not** resolved by this document and names the exact open question:

1. `TODO(unverified)` — the **launch latitude and season**. Assumed 50.0 °N / winter
   solstice (δ = −23.44°); no in-repo source states either. Every number in §1–§5 scales with
   these.
2. `TODO(unverified)` — **whether the ±30° droop of wings 3–4 is retained on v9** (its only
   recorded rationale is antenna lower-hemisphere coverage, and the wing antenna is V2-only).
3. `TODO(unverified)` — the **electrical I–V question**: can the string reach the 5.4 V bank
   (and the 3.3 V LDO input) with 1–2 wings bypassed? Owned by the electrical consultant;
   this document only supplies the geometric factors.
4. `TODO(unverified)` — **loaded `V_mp` of the 52 × 19 mm cell**; `POWER-BUDGET-V9-D2BE` line
   33's per-wing "2.964 cm²" is a factor-10 typo (29.64 cm² correct).
5. `TODO(unverified)` — **self-shading between the four blades is NOT modelled.** The blades
   are 0.6 mm thin and radiate from a 22 mm hub, so occlusion is expected small, but no
   measured or modelled figure exists and the four-arm factors above are unshaded.
6. `TODO(unverified)` — **`ADR-046 §3.3` prose vs table** (52 mm dimension orientation);
   the table is used here, the prose conflict is unresolved.
7. `TODO(unverified)` — **the wing's own mechanical adequacy** under a longer (large-cell)
   or leaned arm — `ADR-046 §7 item 8` already files the tab-fillet cantilever as unanalysed.
8. `TODO(unverified)` — **diffuse/ground-reflected light, module temperature, cell efficiency
   vs incidence beyond the cosine law, and bank/charging efficiency** are all outside the pure
   geometric `cos(incidence)` model used here.

---

## 8. Reproduction

```
python3 docs/analysis/insolation_factors.py      # ~37 s; prints every number above
```

The script is dependency-free (stdlib `math` only). Model summary: sun
`s = (cos h, 0, sin h)`; panel normal `n = (sin β cos ψ, sin β sin ψ, cos β)`;
`cos(incidence) = a + b cos ψ` with `a = sin h cos β`, `b = cos h sin β`; rotation averages
clamp the negative part to zero; the series metric is
`max_j (j · cos_(j))/4`; the day average weights **equal time per unit hour angle**.
