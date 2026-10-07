# Wing geometry: is a VERTICAL CYLINDRICAL solar array better than four vertical blades?

**STATUS: CONSULTANT ANALYSIS — input to a decision; it is NOT a decision record.**
Nothing here is an operator decision, an accepted ADR, or an implementation
authorisation. Every number is either (i) printed by the committed script
`docs/analysis/wing_omnidirectional.py` (run it to reproduce; it imports the
rotation-average primitives from `docs/analysis/insolation_factors.py` so the two
analyses cannot drift), (ii) cited to an in-repo source, or (iii) carries an explicit
`TODO(unverified)` naming the open question.

- Date: 2026-10-07
- Branch: `analysis/wing-omni` · Worktree: `/home/c03rad0r/worktrees/bf-winggeo`
- Base: `af9a672` (== current `github/main` tip; local `main` is a different SHA, so
  the worktree was created from `af9a672` as instructed)
- Lens: the **omnidirectional** question (cylinder vs blades) and its **buildability**.
  This is not a redo of `docs/analysis/wing-insolation-geometry.md` (which establishes
  the flat-vs-vertical and 4-arm rotation analysis) nor of `docs/adr/049-wing-architecture.md`
  (the consolidated recommendation). Both are read and cited below.
- Trigger: the operator saw a **vertical cylindrical** commercial solar array and asks
  whether that shape would be better for this payload.

---

## 0. The one-line answer

**No. Keep four vertical flat blades.** A vertical cylinder and four vertical blades
harvest **exactly the same energy per installed cm² of cell — `(1/π)·cos e`** — so on a
total-mass basis, for equal harvest, they **tie**. The cylinder is therefore not a gain;
and the moment the envelope (projected frontal area) is fixed, the cylinder costs
**π/2 = 1.57× the cells (+7 cells, +10.5 g)** for the same harvest. Since **mass is the
binding constraint**, the tie resolves in favour of the blades. The cylinder's only real
edge — perfectly smooth output — **does not matter**, because the load is a supercap bank
with a shunt clamp, not a battery. The only geometry change that buys anything per gram is
a **~17° outward lean**, worth **+4.6 %/day (+9.5 % at noon)** — and that is already
available to the blade architecture (ADR-049 §5(2) rejected the spin for 3–10 %).

---

## 1. VERIFY the preliminary derivation (my own maths, committed script)

### 1.1 The vertical cylinder

Radius `r`, height `h`, uniformly covered. Sun vector `s = (cos e, 0, sin e)`; a surface
element at azimuth θ around the barrel has outward normal `n = (cos θ, sin θ, 0)`, so

```
s·n = cos e · cos θ          (positive only on the lit half, |θ| < π/2)
A_eff  = ∫₀^h ∫_{-π/2}^{π/2} r · cos e · cos θ  dθ dz  =  2 r h · cos e
A_inst = 2 π r h                                        (full wrap, uniformly covered)
```

`A_eff / A_inst = cos e / π`. **Script lines** `cylinder_effective_area_numeric()` and
the closed form agree to 6 dp: `2 r h cos e = 1.917044` (closed) = `1.917044` (numeric
surface integral, 2×10⁵ points) for `r = h = 1`.

> **Refinement of the task's phrasing.** The task states "the sun-facing effective area is
> ∫cos θ over the lit half = 2 r h". That `2 r h` is the **pure geometry** factor (the
> silhouette). The **flux** factor `cos e` multiplies it: `A_eff = 2 r h · cos e`. The
> final per-installed-area result is unchanged: `cos e / π`.

### 1.2 A single vertical flat blade

Width `w`, height `h`, normal `n = (cos ψ, sin ψ, 0)` at rotation angle ψ:

```
s·n = cos e · cos ψ          (lit for |ψ| < π/2; dark half the rotation → 0)
<F> = (1/2π) ∫_{-π/2}^{π/2} cos e · cos ψ  dψ  =  cos e / π
```

Closed form and numeric rotation integral (2×10⁵ points) agree: `0.305107` both.
`<max(0,cos ψ)> = 1/π = 0.318310`; `<|cos ψ|> = 2/π = 0.636620`. The `2/π` figure is the
average of `|cos ψ|`, which a **single-sided** panel earns at half rate.

### 1.3 Numbers

| Quantity | Value | Script line |
|---|---|---|
| winter-noon elevation at 50 N, δ=−23.44° (ADRs assume this; `TODO` §6) | `e = 16.56°` | `noon_elevation()` |
| `cos e` | `0.95852` | p1 |
| **per installed area, noon** `cos e/π` | **`0.305107`** | p1 |
| **per installed area, daylight-mean** `<cos e>/π` | **`0.311486`** | p1 |
| 24-hour-mean (night = 0, day length 7.852 h) | `0.101905` | p1 |
| half-day hour angle `H₀` | `58.8884°` → day 7.852 h | `sunset_hour_angle()` |

The **daylight-mean** (`0.311486`) is the convention used by `insolation_factors.py`;
the 24-hour mean is 0.1019 because 2/3 of the day is dark. The day average is *higher*
than noon because `cos e` grows as the sun drops — a vertical surface likes a low sun.

### 1.4 Do a cylinder and four blades really harvest the same per installed cm²?

**Yes — CONFIRMED.** The 4-blade cross (arms at 90°) has geometric total (sum of the four
arms' `cos(incidence)`) with rotation-average `1.22043` = `4 × 0.305107`, i.e. **also
`(1/π)·cos e` per installed blade area**. And here is the physical reason the two coincide,
which is the crux of the whole question:

> A blade is **dark for half the rotation** (`1/π = 0.318`), so its *time* average equals
> the cylinder's *instantaneous* average. A cylinder always presents a lit half, so its
> **instantaneous** value already equals the blade's **average**: both `cos e / π`.

All three shapes — vertical cylinder, single blade, 4-blade cross — are the same number per
installed cm². **A cylinder and four blades harvest identically per unit of installed cell
area. The preliminary derivation is CONFIRMED, not refuted.**

---

## 2. CELL USAGE and MASS for the same projected frontal area

Cell constants (CITED `docs/analysis/wing-mass-shape.md` §1.2; ADR-049 "Measured inputs"):

| Cell | Area | Mass (bare-Si estimate) |
|---|---|---|
| small 52.07 × 19.65 mm | `10.2318 cm²` | `0.5006 g` |
| large 78.55 × 38.90 mm | `30.5559 cm²` | `1.4951 g` |

`mass = area × (0.21/10 cm) × 2.33 g/cm³`. Both are `0.400 W/g`, so cell size is **not** a
per-gram lever.

**(A) Constrained by harvest (equal energy).** Because per-installed-area harvest is
identical (§1.4), **equal harvest requires equal installed area → equal cell count**.
12 large cells = `366.67 cm²` = `17.941 g`. **On a total-mass basis for equal harvest, the
cylinder and the blades TIE.** The cylinder has no harvest-per-gram and no mass advantage.

**(B) Constrained by projected frontal area (silhouette).** Installed area ÷ projected
frontal area:

| Shape | installed | silhouette | ratio |
|---|---|---|---|
| vertical cylinder (r, h) | `2πrh` | `2rh` | **π = 3.1416** |
| one flat blade (w, h) | `wh` | `wh` | 1 |
| four-blade 90° cross | `4wh` | `2wh` (two faces + two edges) | 2 |

> **For the same projected frontal area the cylinder needs π ≈ 3.14× the cells of one flat
> plate, and π/2 = 1.5708× the cells of a four-blade cross.** This is the "π factor".

Concretely, a 4-blade cross of **12** large cells (same silhouette) ↔ a cylinder of
`18.85 → 19` large cells:

```
cells:  12 → 19            (+7)
mass : 17.941 g → 28.407 g  (+10.466 g)   = +58 % cell mass
vs a single flat plate: 12π = 37.70 → 38 cells = 56.814 g
```

**Plainly: on a total-mass basis for equal harvest — TIE (blades win on everything else).
For equal projected frontal area — the BLADES win outright (+7 cells, +10.5 g).** Since mass
is the binding constraint (ADR-049 §Context), the blades win both readings that matter.

---

## 3. OTHER OMNIDIRECTIONAL GEOMETRIES

Reference harvest = the accepted 12-large-cell 4-blade array (`0.30511` per-area at noon,
7.2 W peak nameplate). "cells for same harvest" = `12 × 0.30511 / f_noon`; mass at
1.4951 g/cell. **Day** is the deciding metric (daily energy, not noon).

| Geometry | factor noon | factor day | vs vert (day) | cells / mass for same harvest | buildability (hand-soldered 0.21 mm) |
|---|---|---|---|---|---|
| **four vertical blades** (ADR-049) | 0.30511 | 0.31149 | — | 12.0 / 17.94 g | baseline; flat cells, proven |
| **vertical cylinder** (360° wrap) | 0.30511 | 0.31149 | 0.0 % | 12.0 / 17.94 g | **worst**: flat rigid cells cannot be wrapped |
| **horizontal-axis cylinder** ("rolling pin") | 0.22068 | 0.21276 | **−31.7 %** | 16.6 / 24.81 g | bad: axis azimuth uncontrolled → low mean + ripple |
| **cone/funnel, lean 17° from vertical** | 0.33421 | 0.32574 | **+4.6 %** | 11.0 / 16.38 g | cannot wrap; as 4 facets it *is* leaned blades |
| **blades, alternating tilt ±15°** | 0.29565 | 0.30135 | **−3.3 %** | 12.4 / 18.52 g | needs two tab angles; area-splitting loss |
| **flat horizontal cross** (β=0) | 0.28502 | 0.18653 | **−40.1 %** | 12.8 / 19.21 g | simplest, no mismatch, but lowest daily yield |

**Harvest-per-gram:** the only shape that beats four vertical blades is the **lean**
(cone or leaned blades) at **+4.6 %/day (+9.5 %/noon)**. Nothing else comes close:
the horizontal-axis cylinder loses 32 %, the alternating-tilt blades lose 3.3 %, the flat
cross loses 40 % daily. (These agree with `wing-insolation-geometry.md` §3/§4.)

**Smoothness (ripple as the payload rotates):**

| shape | instantaneous output |
|---|---|
| vertical cylinder / cone / flat cross | **constant** — ripple 0 % |
| four vertical blades | total `0.9585 … 1.3556` → **29.3 % of peak**, and it hits a **geometric zero 4× per rotation** (two arms exactly edge-on) |

**Does smoothness matter? No.** The load is a **supercap bank with a shunt clamp**
(ADR-047), **not a battery**. A supercapacitor integrates arbitrary current ripple with no
partial-state penalty, no memory effect and no cycle-life cost; a battery would care, a
supercap does not. **The one thing that *does* follow from smoothness is the
series-string voltage**: the 4-blade string collapses to ≈0 four times per rotation
without its bypass diodes (ADR-049 §Consequences 2), whereas a constant-output geometry
needs none. That is a component-population argument (ADR-046 §2.3 already provisions the
four `D_BP1..D_BP4` as DNP), not a reason to adopt a cylinder.

**Buildability of a "cylinder" from flat rigid cells.** A real cylinder is only buildable
as a **polygonal prism of N flat facets**. For a facet chord = the 38.90 mm cell side:

```
circumradius R =  60 mm → N =  9.5 facets ; smooth-bend strain t/2R = 1750 µε
circumradius R =  90 mm → N = 14.4 facets ; smooth-bend strain t/2R = 1167 µε
circumradius R = 120 mm → N = 19.3 facets ; smooth-bend strain t/2R =  875 µε
circumradius R = 200 mm → N = 32.3 facets ; smooth-bend strain t/2R =  525 µε
```

A hand-soldered N-facet prism is exactly an N-blade wheel — and **N = 4 is literally the
accepted 4-blade cross**. The cylinder is not a different architecture; it is the **N → ∞
limit of the blade cross**, bought at the cost of π/2 more cells (the wrapping penalty of
§2B) and of many more hand-soldered joints. `TODO(unverified)`: the fracture strain limit
of a 0.21 mm bare c-Si cell (no datasheet in-repo) — it decides how few facets could suffice.

---

## 4. SHADING AND SELF-SHADOWING

Winter-noon sun elevation 16.56° → **shadow-throw factor `cot e = 3.363`**: a shadow cast
from height Z lands `3.36 Z` horizontally away.

| Occluder | Shadow on the array | Source |
|---|---|---|
| **Balloon** (d ≈ 900 mm) at Z = 300 mm above the hub | shadow centre `3.363 × 300 = 1009 mm` away; its own half-width 450 mm → near edge at **509 mm**, clear of a ~180 mm-radius array. **The balloon does not shadow a vertical array in winter.** | d CITED `balloon-options-analysis.md` line 11/71; standoff `TODO(unverified)` |
| **Suspension line** (d ≈ 1 mm, `TODO`) | the line runs **UP from the hub** (balloon above), so it is **ABOVE** the hub while the array is **BELOW** it; its shadow lands `3.36 Z` away and misses the array for any segment > ~0.1 m above the array top. **Fraction ≈ 0.** | `TODO(unverified)` line diameter |
| **Hub / tab cluster** (22 × 22 mm board) | at most its own footprint `484 mm²` of the array's `36667 mm²` = **1.3 %**, shared by every geometry (all need a hub at the axis) | CITED `hardware-design.md` l.13 |

**Can the array be arranged BELOW the hub with the line ABOVE it? Yes** — and it *should*,
for both shapes. That single mounting rule removes the largest occluder (the line) from
either geometry, and it is a mounting rule, not a shape property, so it favours neither.

**Self-shadowing:** a vertical cylinder is **strictly convex** → a convex body casts **no
shadow onto itself** from a distant source → **0 %**. The four-blade cross: the sun-facing
blade is edge-on/back-facing to its opposite (which already produces ≈0) and radiates
perpendicular to the other two, so no blade shadows a *producing* surface → **≈0 %** except
the shared hub centre. (Consistent with `wing-insolation-geometry.md` §7 item 5, unmodelled.)

> **Which is more robust to self-shadowing: the cylinder** (strictly convex). But **the
> margin is small** — the blades are already within ~1.3 % of shadow-free, governed by the
> same hub term — and it is worth nothing against the π/2 cell-count penalty.

---

## 5. THE ANSWER

**Do not adopt a cylindrical array. Keep four vertical flat blades.** *Decision number:* a
vertical cylinder and four vertical blades both harvest **`(1/π)·cos e` = 0.305107** per
installed cm² (winter noon) / **0.311486** (daylight-mean, 50 N) — **identical** — so the
cylinder ties on harvest-per-gram and ties on mass for equal harvest, while costing
**π/2 = +57 % cells (+10.5 g)** whenever the envelope is fixed and requiring a
hand-soldered N-facet polygonal prism (N ≥ ~15 at a usable radius) instead of four flat
blades. Its one advantage (perfectly smooth output) is neutralised by the supercap + shunt
clamp load. **Blades win.**

**The one geometry change that would most improve the blades: a ~17° outward lean**
(panel tilt β ≈ 73° from horizontal, i.e. ~16.6° from vertical), worth
**+4.6 %/day, +9.5 % at noon** (β = 75° → +4.5 %/+9.0 %; β = 80° → +3.7 %/+6.7 %). This is
the **only** per-gram lever: it is the day-maximising tilt of the same family the blades
already live in, and a cone/leaned-blade geometry delivers it. Its cost is a cranked tab or
an angled slot — ADR-049 §5(2) rejected the spin for 3–10 %, and this analysis does not
overturn that; it merely confirms the number.

**Two candidate levers that give ZERO gain — computed, not assumed:**

- **Blade COUNT** (e.g. 3 at 120°, 4 at 90°, 6 at 60°): per-installed-blade factor is
  **0.30511 for N = 3, 4 and 6 — unchanged.** The `(1/π)cos e` factor is per-area and
  independent of count. Count affects only ripple and series granularity → **keep 4**.
- **Blade HEIGHT**: the per-area factor is scale-invariant → **0 % per-gram gain**. Height
  scales area, output and mass together.

---

## 6. `TODO(unverified)` register and reproduction

1. `TODO(unverified)` — launch latitude and season. Assumed 50.0 °N / winter solstice
   (δ = −23.44°); no in-repo source states either. Every number scales with these.
2. `TODO(unverified)` — suspension-line diameter (assumed 1.0 mm) and the balloon↔hub
   standoff (assumed 300 mm) in §4; the balloon diameter (900 mm) is CITED.
3. `TODO(unverified)` — fracture strain limit of a 0.21 mm bare c-Si cell (§3 buildability).
4. `TODO(unverified)` — exact hub/rigging shadow footprint (bound 484 mm² from the 22×22 mm
   hub outline).
5. `TODO(unverified)` — loaded `V_mp` / I–V behaviour of the cells (cited as open in
   `wing-insolation-geometry.md` §7 item 3); this document is purely geometric.
6. `TODO(unverified)` — diffuse / ground-reflected light, module temperature, and
   efficiency-vs-incidence beyond the cosine law.

```
python3 docs/analysis/wing_omnidirectional.py      # <1 s, stdlib only
```

Every number in this document is that script's own printed output. The script imports the
rotation-average primitives (`arm_average`, `day_average_arm`, `four_arm_minmax`,
`series_average`, `sun_elevation`, `sunset_hour_angle`) from
`docs/analysis/insolation_factors.py`, so the cylinder/blade factors here and the
flat/vertical factors there are computed by the same code.
