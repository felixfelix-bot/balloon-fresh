# Hub plate stiffness / deflection — the gate on ADR-055 D4's 0.4 mm decision

**STATUS: CONSULTANT ANALYSIS, not a decision record.** Nothing here is an operator decision,
an accepted ADR, or an authorisation to change
`tracker/hardware/schematics/flight_board/v9_flight.kicad_sch`, the netlist, the BOM or any
board file. **No hardware is ordered by this analysis. No thickness is frozen for fab.**
Every number below is either **CITED** to an in-repo source, **COMPUTED** by the committed
script `docs/analysis/hub_thickness_deflection_model.py` (formula shown inline), or marked
`TODO(unverified)` naming the exact open question. Nothing is invented.

- **Date:** 2026-10-07
- **Branch:** `analysis/hub-thickness-deflection` · **Worktree:** `/home/c03rad0r/worktrees/bf-stiff`
- **Base:** `8032cb4` (tip of `github/main`)
- **Model:** `docs/analysis/hub_thickness_deflection_model.py` — run
  `python3 docs/analysis/hub_thickness_deflection_model.py`. Every figure quoted below is
  that script's own printed output.
- **Lens:** closed-form structural mechanics of the hub **plate** and of the **end-only cell
  joint** at its ends. The array's electrical topology (ADR-006 / ADR-046 / ADR-051 / ADR-054),
  the charge path (ADR-050) and the fabrication pipeline (ADR-030) are taken as given and are
  **not** re-derived.
- **Closes:** ADR-051 §2.3 (`TODO(unverified)` — "whether a 90–115 mm panel survives the
  mechanical loads that a 22 mm hub did … no in-repo source analyses it"),
  ADR-046 §7 item 8 / §4.4 (the tab fillet's structural adequacy **not analysed**),
  ADR-048 §5 item 7, `wing-mass-shape.md` §8 item 6, and ADR-055 D4 / Open item 3 (the
  0.4 mm stack-up / stiffness check). **In part** — see §14, "what it does NOT close".

---

## 0. The one-line answer

**The record does not contain the numbers that decide this.** The plate's **boundary
condition**, FR4's **elastic modulus**, the end-only solder joint's **allowable shear strain**,
the cell's **float gap**, the wing's **orientation** (a live contradiction), the vehicle's
**rotation rate** and its **launch/release acceleration** are *all* absent from the repo.
Because of that, the same arithmetic gives **opposite verdicts** depending on which honest
reading of the missing inputs you take: under the global-plate model 0.4 mm sits **inside** a
defensible joint budget; under the local-socket model it sits **1.4–2.7× outside** it.

**What *is* robust and worth recording now:** the thickness lever is real and confirmed
(**4.51 g**), it costs **3.375×** the deflection and **2.250×** the surface strain (exact, from
`t³` and `t²`), the thermal CTE term is **thickness-independent** so it is not a
differentiator, and the wing reaction that loads the cells enters through the **four socket
land rows** — so the question is a *local socket* question, not a global plate question.
**Bench measurement required before 0.4 mm is frozen (§13).**

---

## 1. What is being gated, and by whose words

ADR-055 **D4** (2026-10-07) sets **0.4 mm FR4 as the TARGET** hub thickness and sizes the
prize (§1.5, verified against this checkout):

```
0.6 mm FR4 : 106.1 cm2 x 127.65 mg/cm2 = 13.542 g   (ADR-055 1.5 prints 13.54 g)
0.4 mm FR4 : 106.1 cm2 x  85.10 mg/cm2 =  9.028 g   (ADR-055 1.5 prints  9.03 g)
saving                                 =  4.514 g   (ADR-055 1.5 prints "≈4.5 g")
```

D4 calls that **"LARGER than any other single lever left on the hub"** and then, in the
record's own words:

> **"A stack-up / stiffness check is REQUIRED before 0.4 mm is frozen — a lighter board that
> warps or flexes the cells off their end-only joints is not a saving."**

and lists it as **Open item 3**: *"Whether a 0.4 mm plate of the ≈103 mm size survives the
loads the four ≈176 mm cantilevered wings impose … `TODO(unverified)`."*

**That check is what this analysis runs.** It is not a fab-readiness check (the *stack-up* half
of Open item 3 — can the layer count be fabbed at 0.4 mm — is a supplier question, not a
mechanics question, and is **not** answered here).

---

## 2. Inputs — all CITED, none re-derived

### 2.1 Geometry and mass

| Quantity | Value | Source |
|---|---|---|
| Plate | **103.0 × 103.0 mm** | ADR-055 D5 (`√106.1 cm² ≈ 103 mm`); ADR-051 §2.3 |
| Plate area | **106.09 cm² (1.0609 × 10⁻² m²)** | derived from the above |
| Plate thickness | **0.6 mm (current) / 0.4 mm (target)** | ADR-055 D4; `docs/hardware-design.md` line 14 ("oder 0.4mm fuer Gewichtsoptimierung") |
| FR4 density | **1.85 g/cm³** | `wing-mass-shape.md` §1.1 (CITED to `docs/PAYLOAD-WEIGHT-ESTIMATES.md` line 20) |
| Finished-board uplift | **×1.15** | `wing-mass-shape.md` §1.1 (same source: "adds ~15 % for copper, soldermask, silkscreen") |
| Areal mass, 0.6 mm | **127.65 mg/cm²** | ADR-055 §1.5; `wing-mass-shape.md` §2.1 |
| Areal mass, 0.4 mm | **85.10 mg/cm²** | ADR-055 §1.5; `wing-mass-shape.md` §2.1 |
| Plate mass, 0.6 mm | **13.542 g** | COMPUTED (above) |
| Plate mass, 0.4 mm | **9.028 g** | COMPUTED (above) |
| Wing body length | **176 mm** | `wing-mass-shape.md` §1.4 (Edge.Cuts x-range 0…176 mm, read from the gerber) |
| Wing mass, **end-only** (current) | **≈1.9525 g/wing** (7.81 g/array) | ADR-052 §2.6, END-ONLY row |
| Wing mass, spine+ribs | **3.212 g/wing** (12.848 g/array) | `wing-mass-shape.md` §1.4 (b) |
| Wing mass, full carrier | **7.300 g/wing** (29.200 g/array) | `wing-mass-shape.md` §1.4 (a) |
| Wing interfaces | **4, at 90°** | ADR-046 §1/§4.1; ADR-048 §2.1 |
| Wing **tab width** (load entered over this) | **9.0 mm** | ADR-046 §4.1; ADR-048 §2.2 |
| Wing **plane orientation** | **VERTICAL** (blade); long axis radial, 25 mm width vertical | **ADR-049 §5 item 6** ("Wing plane orientation is VERTICAL … resolved by arithmetic") — note ADR-048 §5 item 6 / sheet item `OPEN-23` still carry the *un*resolved contradiction with socket-spec §1 |
| Hub cell (LARGE) | **78.55 × 38.90 × 0.21 mm**, 30.6 cm², 0.50 V, 1.2 A | ADR-049 Measured inputs; ADR-051 §1.4 |
| Hub cell mass (LARGE) | **1.4951 g (silicon-only estimate)** | `wing-mass-shape.md` §1.2 |
| Cell mounting overhead | **≈0.15 g/cell** (`TODO(unverified)` in ADR-052 §2.6) | ADR-052 §2.6 |
| Cell end land | **4.0 × 1.2 mm**, pitch 1.8 mm | ADR-046 §2.2; ADR-048 §2.2 |
| Socket joint | **pad-to-tab solder joint, NO slot** (the 0.9 mm slot was rejected) | ADR-049 §5 item 4 ("**ADR-046's 0.9 mm hub slot is below JLCPCB's minimum non-plated slot (1.0 mm)** … Fix: slot ≥ 1.0 mm, **or drop the slot in favour of plain solder pads**"); ADR-046 §4.2 Option B |
| Joint load path | **the solder fillet carries the mechanical load** | ADR-046 §4.4 (`docs/hardware-design.md` line 162, "Loetverbindungen an allen 4 Slots tragen mechanisch", confirmed as the load path) |
| Ascent velocity / aero drag | **5 m/s; 23.2 mN at 20 km (whole 4-arm array)** | `wing-mass-shape.md` §2.3 |
| Design case | **−60 °C**; verified part limits **−55 °C (diodes) / −40 °C (converters)** | ADR-054 §4 (lines 327–328) |
| Flight environment | 10–12 km, 19–26 kPa, −50…−56 °C | ADR-052 §2.3 |

### 2.2 The two facts that make this a **joint** question, not a plate question

1. **ADR-052 §2.1: the cells are mounted END-ONLY, with NO adhesive bond and no full-face
   lamination.** Each cell is attached "at its two ends only, and is otherwise free to move."
   The rationale is **thermal contraction**, not vacuum.
2. **ADR-046 §4.4: the solder fillet carries the mechanical load** in both socket options.

So the plate's job, as far as the cells are concerned, is to keep the **two end joints of each
cell** inside a strain budget. Any plate curvature across a cell's length is a direct demand on
those joints. This is exactly ADR-055 D4's stated worry.

---

## 3. Material properties that are **NOT in the repo** (carried as ranges)

A repo-wide search for a Young's modulus, an elastic modulus or a GPa figure returns **nothing
for FR4** — the repo's own mass model (`wing-mass-shape.md` §1.1) carries only *density* and
thickness for FR4, never stiffness. The load-bearing property for this analysis is therefore
**absent**, and it is used below as a labelled standard range, never as one silently-chosen
number.

| Property | Range used | Status |
|---|---|---|
| FR4 in-plane elastic modulus `E` | **18–24 GPa**, nominal **20 GPa** at 25 °C | `TODO(unverified)` — standard E-glass/epoxy laminate range; **not in-repo** |
| FR4 cold stiffening (`E(−60 °C)/E(25 °C)`) | **1.00–1.20** | `TODO(unverified)` — FR4 stiffens as it cools |
| FR4 Poisson ratio `ν` | **0.15** (0.13–0.20) | `TODO(unverified)` |
| FR4 in-plane CTE | **12–18 ppm/K** | `TODO(unverified)` |
| Si CTE | **2.6 ppm/K** | standard (crystalline Si) |
| Si modulus | 170 GPa | standard |
| **Solder (SAC305) allowable imposed shear strain `γ`** | **0.1 %–1.0 %** (1000–10000 µε) | `TODO(unverified)` — the elastic limit is ≈0.17 % (τ_y ≈25 MPa / G ≈15 GPa); 1 % is a common high-cycle-fatigue onset allowance; **no in-repo source** |
| **Cell float gap / solder fillet standoff `h_j`** | **0.05–0.15 mm** | `TODO(unverified)` — **no in-repo source**; the fillet height is not specified anywhere |

**The modulus sensitivity.** Because `E` is carried as 18–24 GPa, every deflection below moves
by ×0.83…×1.11 and every strain by the same factor — small next to the boundary-condition
spread (§7) and the joint-allowable band (§10), and dwarfed by the 3.375×/2.25× thickness
effect. **The modulus range does not change any conclusion; the missing *joint allowable* does.**

---

## 4. The boundary condition — **ASSUMED**, and stated as an assumption

**The record does not fix how the hub plate is attached to the suspension.** The only recorded
mechanics statement is a v1 concept doc, `docs/hardware-design.md` lines 158–165:

> *"Loetverbindungen an allen 4 Slots tragen mechanisch"* / *"4 Wings stuetzen sich
> gegenseitig"* / *"Hub-Board oben"* / *"**Aufhaengung: 30AWG Draht vom Hub-Board zum
> Ballon**"*

ADR-055 **D6** adds only that *"the suspension attachment is raised on a standoff above the
array"* — and states the **standoff height is `TODO(unverified)`**. **No attachment stiffness,
no mount count and no mount positions are recorded anywhere.**

**So the boundary condition is an ASSUMPTION, and it is named here rather than buried.**
Three idealisations are carried so the reader can see the spread:

| ID | Assumption | Why it is on the list |
|---|---|---|
| **BC-A** | **Centre suspension** — a single 30 AWG line to a central standoff; the four wings cantilever off the four edges | the literal reading of `hardware-design.md` line 163 + ADR-055 D6. **Used as the design case (worst case).** |
| **BC-B** | **Four-corner supports** (standoffs/mounting holes at the corners) | `hardware-design.md` line 161 ("4 Wings stuetzen sich gegenseitig") could imply peripheral support |
| **BC-C** | **Local socket** — the wing's root moment applied as a **line moment over the 9 mm tab** on the plate edge (`M′ = M_w / w_tab`) | where the load *actually enters*. This is the local detail the global models average away |

`TODO(unverified)`: **the real attachment.** A deflection or strain number without its BC is
meaningless, and the record does not supply one — this is the first of the two reasons §12
cannot be settled.

---

## 5. The thickness scaling laws — the exact, robust part

Thin-plate (Kirchhoff) flexural rigidity per unit width:

```
D = E t^3 / (12 (1 − ν²))
D(0.4 mm) = 20e9 x (0.4e-3)^3 / (12 x (1 − 0.15^2)) = 0.10912 N·m
D(0.6 mm) = 20e9 x (0.6e-3)^3 / (12 x (1 − 0.15^2)) = 0.36829 N·m
```

Therefore, at **equal load**:

```
thickness ratio 0.4/0.6                     = 0.6667
plate stiffness  D ∝ t^3                    = 0.2963   (−70.4 %)
plate deflection δ ∝ 1/t^3                  = 3.3750x  MORE at 0.4 mm
plate surface strain eps = κ t/2 ∝ M t/(E t^3) = 2.2500x  MORE at 0.4 mm
```

**These three ratios are exact and do not depend on any assumption.** They are the numbers that
decide the *relative* risk of the 4.5 g lever. Nothing else in this document is that clean.

---

## 6. Load case **a** — static gravity (the design case)

### 6.1 The wing root moment — the load the plate actually sees

Wing plane is **vertical** (ADR-049 §5 item 6): the 176 mm body extends radially and the 25 mm
width is vertical, so the wing's weight is a **diving-board load** on the plate edge:

```
M_w = m_wing x g x x_cg ,  x_cg = 0.176/2 = 0.088 m   (uniform strip; CITED geometry)
end-only 1.9525 g : M_w = 1.9525e-3 x 9.80665 x 0.088 = 1.685 mN·m / wing
spine    3.212  g : M_w = 2.772 mN·m / wing
full     7.300  g : M_w = 6.301 mN·m / wing
```

**Caveat, stated because it is 7×:** if the wing's 176 mm axis were *vertical* instead of
radial, gravity would be axial and the root moment would fall to
`m g × 12.5 mm = 0.24 mN·m` — **7× smaller**. The wing orientation is **VERTICAL-per-ADR-049
§5 item 6**, but **ADR-048 `OPEN-23` still carries the unresolved contradiction** with
socket-spec §1 (wings 1–2 "horizontal", 3–4 at ≈30°). **The orientation must be frozen before
this moment is trusted to better than an order of magnitude.**

### 6.2 On-plate load census (the uniform part)

```
hub cells   4 x 1.4951 g = 5.980 g   (4 LARGE cells are the minimum that covers 106.1 cm²:
                                      3 x 30.6 = 91.8 < 106.1 — see §12 note on ADR-051 H2)
mounting    4 x 0.15 g   = 0.600 g   (ADR-052 2.6, itself TODO(unverified))
electronics              = 2.000 g   TODO(unverified) — order-of the v8i 2.76 g hub line
                                                       (docs/POWER-BUDGET-V9-D2BE.md line 172)
                                        ; ADR-055 D7's "≈25 cm²" radio court is TODO(unverified)
on-plate total           = 8.580 g   -> q = 8.580e-3 x 9.80665 / 0.010609 = 7.93 N/m²
wings                    = 7.810 g   (end-only) / 12.848 g (spine) / 29.200 g (full)
```

### 6.3 Results — all three BCs, all three wing masses, both thicknesses

`d_q` uniform load · `d_P` wing weight at the edge · `d_M` wing root moment · **TOTAL** mm ·
`κ` max curvature · `eps` board surface strain. (BC-A uses a cylindrical-bending strip of the
full plate width, half-span 51.5 mm; BC-B is the textbook simply-supported square plate
`δ = 0.00406 q a⁴/D` plus the beam terms; BC-C is the local edge line moment.)

```
--- wing = END-ONLY 1.9525 g/wing  (ADR-052 2.6, the design case) ---
  BC-A centre-post   0.6 mm : d_q=0.0189 d_P=0.0230 d_M=0.0589  TOTAL=0.1008 mm  κ=0.099 1/m  eps= 29.7 ue
  BC-A centre-post   0.4 mm : d_q=0.0639 d_P=0.0776 d_M=0.1988  TOTAL=0.3403 mm  κ=0.334 1/m  eps= 66.8 ue
  BC-B 4-corner      0.6 mm : TOTAL=0.0917 mm
  BC-B 4-corner      0.4 mm : TOTAL=0.3096 mm
  BC-C local socket  0.6 mm : M'=0.1872 N·m/m  κ=0.508 1/m  eps=152.5 ue
  BC-C local socket  0.4 mm : M'=0.1872 N·m/m  κ=1.716 1/m  eps=343.1 ue
--- wing = SPINE 3.212 g/wing ---
  BC-A centre-post   0.6 mm : TOTAL=0.1536 mm  κ=0.144 1/m  eps= 43.3 ue
  BC-A centre-post   0.4 mm : TOTAL=0.5186 mm  κ=0.487 1/m  eps= 97.5 ue
  BC-C local socket  0.4 mm : κ=2.822 1/m  eps=564.5 ue
--- wing = FULL CARRIER 7.300 g/wing (the rejected structure) ---
  BC-A centre-post   0.6 mm : TOTAL=0.3251 mm  κ=0.292 1/m  eps= 87.5 ue
  BC-A centre-post   0.4 mm : TOTAL=1.0972 mm  κ=0.985 1/m  eps=197.0 ue
  BC-C local socket  0.4 mm : κ=6.415 1/m  eps=1282.9 ue
```

**Reading this:**

- **Global plate deflection is sub-millimetre at 0.4 mm** — **0.340 mm** (BC-A, end-only wings)
  or **0.310 mm** (BC-B). Against the plate's own 103 mm span that is **0.33 %**, i.e. *smaller
  than ordinary bare-FR4 panel warpage*. **Global plate flexure is not itself the failure.**
- **The socket is where the thinned plate hurts.** The wing's root moment enters through a 9 mm
  tab, and the resulting **local** curvature at 0.4 mm is `κ = 1.716 1/m` → a **343 µε** board
  surface strain at the cell lands, against **152 µε** at 0.6 mm (ratio 2.25×, §5).
- The **thermal and uniform** terms are small; **the wing root moment dominates every BC.**

---

## 7. Load case **b** — rotation / centrifugal (**BOUNDED**; no rate in the record)

ADR-055 D1(b) states only that *"the vehicle has no attitude control and rotates slowly."* **No
angular rate appears anywhere in the repo** (verified by repo-wide search). It is therefore
**bounded**, with the bound stated:

```
wing CG radius from hub centre  R = 51.5 + 88.0 = 139.5 mm
a_centrifugal = ω² R
   1 rpm : ω=0.1047 rad/s -> a = 0.0015 m/s² = 0.0002 g
   6 rpm : ω=0.6283 rad/s -> a = 0.0551 m/s² = 0.0056 g   (6x below the gravity term)
  12 rpm : ω=1.2566 rad/s -> a = 0.2203 m/s² = 0.0225 g
  60 rpm : ω=6.2832 rad/s -> a = 5.507  m/s² = 0.5616 g
  a 1 g-equivalent centrifugal load requires ω = √(g/R) = 8.384 rad/s = 80.1 rpm
```

**Bound: the rotation case only becomes significant above ~80 rpm**, which is fast for a
passive pico-balloon payload hanging under a 30 AWG line. At ≤10 rpm it is **≥40× below the
gravity term** and can be neglected. `TODO(unverified)` — **the bound is an assertion about the
vehicle class, not a measurement**; the repo states no rate, and a fast-spin failure (e.g. a
line-wrap) would change the case. Note the centrifugal load is *in-plane* (it pulls the four
wings outward), so even a large value loads the plate in **membrane tension, which stiffens it**
against out-of-plane bending rather than bending it — the bending component comes only from the
wings being non-coplanar, which is itself an unresolved geometry (`OPEN-23`).

---

## 8. Load case **c** — ascent / launch (**BOUNDED**; no acceleration in the record)

**Sourced:** ascent velocity **5 m/s** and the flat-plate drag on the whole 4-arm array
(175 cm²) versus the standard atmosphere (`wing-mass-shape.md` §2.3):

```
20 km : F = 23.2 mN  = 0.144 g-equivalent of the 16.4 g payload
25 km : F = 10.5 mN  = 0.065 g-equivalent
30 km : F =  4.7 mN
```

**Not sourced: any launch / release / shock acceleration.** Both `ADR-046 §7 item 8` and
`wing-mass-shape.md §8 item 6` record it as unanalysed, and ADR-046 §4.4 names **"shock"** as
one of the two things loading the tab joint.

**Bound: ≤2 g vertical**, on the grounds that a helium balloon lifts a ~25 g payload
quasi-statically (there is no boost phase, and the wings are attached during ascent because
they are jettisoned later — ADR-051 §0/§2.4). Under that bound the ascent case is **≤2 g vs the
1 g design case**, i.e. a factor ≤2 on every number in §6 — **far smaller than the 3.375×
thickness lever**.

`TODO(unverified)`: **the release/snatch transient, and any pre-launch drop or handling bump.**
A *drop* is the only load in the vehicle's life that plausibly beats 2 g, and it is not bounded
by anything in the repo. **If the vehicle is dropped, every number in §6 scales linearly with
the g and this analysis does not cover it.**

---

## 9. Load case **d** — thermal (the −60 °C design case)

Two effects, in **opposite** directions — stated in the direction each cuts:

| Effect | Direction | Number |
|---|---|---|
| **(i) FR4 stiffens as it cools** | **HELPS** stiffness (raises `D`, cuts deflection and strain) | `E(−60 °C) = E(25 °C) × (1.00–1.20)` `TODO(unverified)` → `D(0.4 mm)` rises from 0.10912 to ≤0.13095 N·m (**+20 %** at the top of the range) |
| **(ii) CTE mismatch FR4 ↔ Si** | **HURTS** the joints — *this is ADR-052 §2.1's own rationale for the end-only mount* | see below |

```
CTE mismatch strain = (CTE_FR4 − CTE_Si) x |ΔT| ,  ΔT = −60 − 20 = −80 K
  CTE 12 ppm/K : (12−2.6)e-6 x 80 = 752 ue over the cell's 78.55 mm = 59 µm end-to-end
  CTE 18 ppm/K : (18−2.6)e-6 x 80 = 1232 ue over the cell's 78.55 mm = 97 µm end-to-end
```

**The decisive thermal point for THIS decision:** the CTE-mismatch strain is set by the cell's
**length** and the **in-plane CTEs** only — it is **completely independent of plate thickness**.
0.4 mm and 0.6 mm carry **exactly the same** thermal term. **Thermal is therefore not a
differentiator between 0.4 and 0.6 mm**, and it cannot be used as an argument either way. What
makes it survivable is **ADR-052's end-only mount** (the cell floats instead of a bond being
strained), which is already the decision — and which is exactly why the *deflection* term (§6)
is the one the thickness lever actually moves.

`TODO(unverified)`: no in-repo CTE, no Si-on-FR4 joint thermal-cycle result. ADR-052 §2.7 items
1–3 already file the cold-soak test as the operator's own bench work, and it is unrun.

---

## 10. The deflection limit, derived from the end-only joint

**The limit is set by the two end joints of each cell, not by a comfort number.** Geometry:
the cell (0.21 mm, **78.55 mm long**) is soldered at **both ends** to **4.0 × 1.2 mm lands**
(ADR-046 §2.2) and **nowhere else** (ADR-052 §2.1). Plate curvature across the cell's length is
a direct demand on those joints.

Two joint models are carried, because **the joint's allowable is not in the record**:

**M1 — rigid-cell (joint takes the rotation).** The board's end slopes rotate the joint
relative to the (stiff) cell. For a parabolic board sag δ over the cell span:

```
Theta_end = 4 δ / L_cell                       (surface slope at each end, relative to the chord)
gamma_joint = Theta_end x (l_land/2) / h_j     (shear over the 2 mm half-land / fillet height)
 => delta_allow = gamma_allow x L_cell x h_j / (2 l_land)
```

**M2 — floating-cell (the cell bows; the limit is the gap it can bow into).**

```
delta_allow = gap  (the cell-to-board standoff it may close before contact)
```

The derived allowable, printed by the script:

```
M1, gamma_allow = 0.1 %  , h_j 0.05/0.10/0.15 mm -> delta_allow =  0.49 / 0.98 / 1.47 µm
M1, gamma_allow = 1.0 %  , h_j 0.05/0.10/0.15 mm -> delta_allow =  4.91 / 9.82 / 14.73 µm
M2, gap = 100 µm (assumed, TODO(unverified))     -> delta_allow = 100 µm
```

**Maximum allowable plate deflection (local sag over one 78.55 mm cell span): a BAND of
≈1–100 µm — two orders of magnitude.** `TODO(unverified)` on **both** ends of it: `γ_allow`
(0.1–1 %) and `h_j` (0.05–0.15 mm) are *not in the repo*, and the float gap is assumed at
100 µm. **This is the honest answer to "derive the maximum plate deflection": it cannot be
narrowed from the record.**

### 10.1 The demand, on the same metric

Local sag over one cell span, `δ = κ L_cell²/8`, from each BC's max curvature:

```
                        BC-A centre-post     BC-C local socket
0.6 mm, end-only wing        76 µm               392 µm
0.4 mm, end-only wing       258 µm              1323 µm
0.4 mm, spine wing          376 µm              2177 µm
0.4 mm, full-carrier wing   760 µm              4947 µm
```

**Demand 258 µm (0.4 mm global) to 1323 µm (0.4 mm local): it lies ABOVE the whole derived
band (1–100 µm) at the tight end and ABOVE the 100 µm gap limit at the global end too — but so,
at the tight end, does the 0.6 mm plate (392 µm local).** That is the crux of §12: the tight
reading of the missing allowable **condemns the record's own 0.6 mm "safe value" as well**,
which means the tight reading is not the right model — and the *right* model cannot be selected
without the joint data.

### 10.2 The same thing expressed as joint shear strain

```
gamma = eps_surf x l_land / h_j     (demand)
allowable band: gamma_allow = 0.10 % .. 1.00 %
```

```
0.6 mm  BC-A centre (global)  eps= 29.7 ue -> gamma = 0.238 % (h_j 0.05) / 0.079 % (h_j 0.15)
0.6 mm  BC-C local socket     eps=152.5 ue -> gamma = 1.220 %        / 0.407 %
0.4 mm  BC-A centre (global)  eps= 66.8 ue -> gamma = 0.534 %        / 0.178 %
0.4 mm  BC-C local socket     eps=343.1 ue -> gamma = 2.745 %        / 0.915 %
```

**0.4 mm sits *inside* the band under the global model (0.18–0.53 %) and 1.4–2.7× *outside*
it under the local-socket model (0.92–2.75 %).** The model choice **is** the missing boundary
condition. That is the whole finding.

---

## 11. Three options, with the grams and the deflection for each

Stiffening assumed: **4 glued 0.4 mm FR4 doublers, 20 × 9 mm, one over each socket land row**
(a rib/boss at the wing mounts and socket lands — where the load actually enters).

```
option                             plate g  stiff g   total g  d(BC-A) mm  eps_socket ue
(i)   0.6 mm plain                  13.542    0.000    13.542      0.1008      152 -> 152
(ii)  0.4 mm plain                   9.028    0.000     9.028      0.3403      343 -> 343
(iii) 0.4 mm + local stiffening      9.028    0.613     9.641      0.3403      343 ->  86
```

```
stiffening mass (4 x 20 x 9 x 0.4 mm FR4, glued)  = 0.613 g
ADR-055 D4 prize (0.6 -> 0.4 mm plate)            = 4.514 g   (CONFIRMED, matches D4's ≈4.5 g)
... minus the stiffening                          = 3.901 g   net
```

- **Option (iii) recovers MORE margin at the socket than 0.6 mm has.** Doubling the local `t`
  cuts the socket surface strain by ≈**4×** (`1/t²`): **343 → 86 µε**, i.e. **better than the
  0.6 mm plate's 152 µε** — while still banking **3.90 g** of the 4.5 g.
- **But it is not free, and the record says why:** the operator **hand-solders every joint and
  the repo counts joint count as a primary risk metric**. Four glued doublers are **4 added
  hand operations and 4 added interfaces**, on a payload whose whole design philosophy
  (ADR-052, ADR-049) is *minimum part count*. There is **no way to get a local thickness step
  on a single 2-layer FR4 core** — a doubler is a *second part*, not a board setting.
- And **the global plate deflection is unchanged** by the doublers (0.3403 mm), because they
  sit only at the sockets. If the real governing case turns out to be the **global** one, local
  stiffening does not help it and the answer is 0.6 mm or better.

---

## 12. Why this cannot be settled from the record

The arithmetic in §6–§11 is complete and reproducible. It gives **opposite verdicts** on which
reading of the seven missing inputs you take:

| Missing input | Where it should be | Status |
|---|---|---|
| 1. Plate **boundary condition** (mount count/positions/stiffness) | not in any record; only `hardware-design.md` 158–165 (v1 concept) + ADR-055 D6 | **ABSENT** — assumed (BC-A/B/C) |
| 2. FR4 **elastic modulus** | nowhere in the repo (only density) | **ABSENT** — standard range used |
| 3. End-only joint **allowable shear strain** | nowhere | **ABSENT** — 0.1–1 % range |
| 4. Cell **float gap / fillet height `h_j`** | nowhere | **ABSENT** — 0.05–0.15 mm assumed |
| 5. Wing **orientation** | ADR-049 §5 item 6 resolves it *vertical*; **ADR-048 `OPEN-23` still carries the contradiction** | **CONTRADICTION LIVE** — changes the root moment **7×** |
| 6. **Rotation rate** | nowhere | **ABSENT** — bounded (≥80 rpm for 1 g) |
| 7. **Launch / release / drop** acceleration | nowhere (`ADR-046 §7 item 8`, `wing-mass-shape §8 item 6` both say unanalysed) | **ABSENT** — bounded at ≤2 g |

**The conditional decision table — the honest form of the answer:**

| If the joint's real limit is … | then at 0.4 mm | verdict |
|---|---|---|
| the **gap-limited / floating-cell** reading (~100 µm; ADR-052's "cells float") | global sag **258 µm > 100 µm** | **not adequate** without local stiffening |
| the **global-plate** model's joint budget (γ 0.18–0.53 % inside the 0.1–1 % band) | inside the band | **adequate** |
| the **local-socket** model's joint budget (γ 0.92–2.75 % vs 0.1–1 %) | 1.4–2.7× outside | **not adequate** without local stiffening, (and 0.6 mm is marginal too) |

**Opposite verdicts from the same arithmetic. The deciding number is a quantity the record does
not contain.** Per the brief's own rule — *"a precise-looking number built on an invented
modulus is worse than a named gap"* — the verdict is **`cannot be settled from the record`**,
and the gap is named below rather than papered over.

**One inconsistency found while reading the inputs, recorded here because it is live:**
**ADR-051 §2.2 recommends H2 = 2 LARGE cells = 61.2 cm² on a sub-µA harvester, while ADR-055 D5
sizes the plate at 106.1 cm² — which needs ≥4 LARGE cells (3 × 30.6 = 91.8 < 106.1).** ADR-055
D3 does say the 106.1 cm² figure is a *ceiling* (full duty) so the two are not strictly
contradictory, but the **cell count on the plate is unsettled** and it moves the on-plate mass
by ~3 g (5.98 g → 2.99 g). It does **not** change this analysis's verdict (a 3 g delta is ~19 %
of the on-plate load and a fraction of the BC spread), but it should be noted before either
figure is frozen.

---

## 13. The bench measurement that WOULD settle it

**One measurement, on a coupon, settles the whole question.** It is the operator's own bench
work (ADR-052 §2.7 already reserves the cold-soak test as his), and it is small:

> **Solder one of the operator's real cells end-only onto a 0.4 mm FR4 coupon of the real
> 103 mm class, using the real 4.0 × 1.2 mm land (ADR-046 §2.2) and the real hand fillet, and
> measure (a) the fillet height `h_j`, then (b) the joint's shear strain at first damage as the
> coupon is bent to a measured curvature, i.e. find `κ_damage` — the board curvature at which
> the end joint cracks. Then repeat at −55 °C.**
>
> The one number it produces is **`κ_damage` (or equivalently the allowable end-rotation
> `Θ_end,allow`)**. With `κ_damage` in hand:
> - `delta_allow,cell = κ_damage · L_cell² / 8` replaces the 1–100 µm band with a single value;
> - comparing it to §10.1's demand (258 µm at 0.4 mm, 76 µm at 0.6 mm) gives a **yes/no**;
> - and the same coupon run gives `γ_allow`, so both M1 and M2 collapse to one model.

**Supporting measurements, in priority order:**
1. **Weigh the as-built hub array and one wing** (ADR-052 §2.7 item 2 / `wing-mass-shape.md`
   §8 item 1) — the whole load census is arithmetic on copies of a 4×-disputed cell mass.
2. **Weigh the plate** at both thicknesses — confirms the 4.514 g lever (expected: 13.54/9.03 g).
3. **Measure the panel flatness** of a bare 103 × 103 × 0.4 mm panel (fabricated or an
   equivalent offcut) against the assembly flatness the end-only cell placement needs. **This is
   the *warpage* half of ADR-055 D4's sentence, is a build risk (not a flight-load risk), and is
   the one item of the whole question that no coupon bend test covers.**
4. **Freeze the wing orientation** (`OPEN-23`) — it is worth **7×** on the governing moment.
5. **State the suspension attachment** (mount count, positions, standoff) — the boundary
   condition that every number above depends on.

---

## 14. Verdict

- **`cannot be settled from the record.`** The plate's **boundary condition**, FR4's **modulus**,
  the end-only **joint allowable**, the **float gap** and the **wing orientation** are all absent
  or contradictory in the repo, and the same arithmetic gives **opposite verdicts** (§12) across
  the honest readings. **A bench coupon test (§13) settles it with one number.**
- **The robust, decision-relevant findings that DO transfer:**
  1. **The 4.5 g is real and confirmed: 4.514 g** (13.542 → 9.028 g), matching ADR-055 D4.
  2. **The lever costs 3.375× the deflection and 2.250× the surface strain** — exact, assumption-
     free (§5).
  3. **Thermal is not a differentiator**: the CTE-mismatch term (752–1232 µε) is **independent of
     plate thickness** (§9), and cold *helps* the plate's stiffness.
  4. **The load enters at the four socket land rows**, so the binding question is **local**
     (the 9 mm tab on the plate edge), not global (§6.3). Global plate deflection at 0.4 mm is
     **0.34 mm = 0.33 % of span** — smaller than normal bare-FR4 warpage.
  5. **A local stiffener at the four sockets (≈0.613 g) recovers MORE socket margin than 0.6 mm
     has** (86 µε vs 152 µε) while still banking **3.90 g** — *but* it is **4 added hand
     joints** on a hand-soldered, minimum-part-count payload, and it does **not** help the
     global case. **So if it IS settled mechanically, the likely answer is "adequate only with
     local stiffening", at a cost of ~0.6 g and 4 joints — not a free 4.5 g.**
- **Action on ADR-055:** the record is **unchanged in its decision** (0.4 mm remains the
  target, correctly), but its **Open item 3 is only partly closed** and D4's "stiffness trade is
  noted" gains the numbers above. A dated **appended decision section** records this (repo
  convention: ADR-042/056 were corrected by appended sections), **not** a rewrite.
- **Order nothing. Freeze nothing.** No schematic, netlist, placement, BOM or fab change is
  authorised by this analysis.

---

## 15. What this analysis does NOT establish

- **No measurement of any physical part.** All numbers are arithmetic on cited constants and
  standard material ranges; the two decisive quantities (`E_FR4`, `γ_allow`) are ranges, not
  measurements.
- **No answer to the *stack-up* half of ADR-055 D4 / Open item 3** — whether a 0.4 mm layer
  count is fabricable on the chosen supplier. That is a supplier question.
- **No answer on panel warpage.** §13 item 3 names it and it is not bounded here.
- **No re-derivation of any electrical decision** (ADR-006/046/051/054) and no charge-path
  claim (ADR-050).
- **No relaxation of any dynamic case.** A pre-launch **drop** is unbounded (§8) and would scale
  every §6 number linearly with g.
- **No fab authorisation.** This is design analysis only. **Order nothing.**

---

## Appendix — full model output

Run `python3 docs/analysis/hub_thickness_deflection_model.py` to reproduce every figure above
byte-for-byte. The script is committed alongside this document.
