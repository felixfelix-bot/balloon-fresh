# Wing mass and shape — consultant analysis

**STATUS: CONSULTANT ANALYSIS, not a decision record.** Nothing here is an operator
decision, an accepted ADR, or an authorisation to change
`tracker/hardware/wing_board/wing_board_v9.kicad_pcb`. Every number below is either
**COMPUTED** by the committed script `docs/analysis/wing_mass_model.py` (formula shown
inline), **CITED** to an in-repo document or to the operator's caliper, or marked
`TODO(unverified)` naming the exact open question. No measurement was performed for this
analysis; the only observation taken from a tool is the Edge.Cuts bounding box read from
the committed wing gerber.

- **Date:** 2026-10-07
- **Branch:** `analysis/wing-mass-shape` · **Worktree:** `/home/c03rad0r/worktrees/bf-wingmass`
- **Base:** `76dd04d` (current tip of `github/main`)
- **Lens:** mechanical, mass and shape optimisation of the wing. Electrical topology is
  taken as given from ADR-006 / ADR-046 / ADR-047 / ADR-048 and is **not** re-derived.
- **Model:** `docs/analysis/wing_mass_model.py` — run `python3 docs/analysis/wing_mass_model.py`.
  Every gram quoted below is that script's own printed output.

---

## 0. The one-line answer

**No — a full PCB carrier is not the right structure for maximum solar power per gram.**
At 0.6 mm FR4 the carrier costs **127.6 mg per cm²** while a 0.21 mm silicon cell costs
**48.9 mg per cm²** — the board is **2.61× heavier per unit area than the cell it carries**.
The wing as built therefore spends **5.709 g of FR4 to carry 1.502 g of silicon** and the
four-wing array weighs **29.20 g** against a whole-payload mass target of ~14 g. Replacing
the full carrier with a spine-and-ribs frame takes the array to **12.85 g** (−16.35 g).

---

## 1. Item 1 — the mass model

### 1.1 Constants and their provenance

| Constant | Value | Provenance |
|---|---|---|
| FR4 density | **1.85 g/cm³** | **CITED** — `docs/PAYLOAD-WEIGHT-ESTIMATES.md` line 20 ("FR4 density: 1.85 g/cm³") |
| Substrate thickness | **0.6 mm** | **CITED** — ADR-046 §3.2; `docs/hardware-design.md` line 63 |
| Finished-board uplift | **×1.15** | **CITED** — `docs/PAYLOAD-WEIGHT-ESTIMATES.md` line 20 ("Finished board adds ~15 % for copper, soldermask, silkscreen") |
| Silicon density | **2.33 g/cm³** | physical constant (crystalline Si, 2.329 g/cm³) |
| Cell thickness | **0.21 mm** | **CITED** — operator caliper (0.20–0.21 mm) |
| Copper thickness | 0.035 mm (1 oz) | `TODO(unverified)` — see §8 item 3 |
| Solder-mask thickness / density | 0.025 mm / 1.30 g/cm³ | `TODO(unverified)` — see §8 item 4 |
| Solder density | 7.40 g/cm³ | SAC305, physical constant |
| Hub outline | 22 × 22 mm | **CITED** — `docs/hardware-design.md` line 13 (used only for the arm-length datum) |

**Board material, cross-checked.** For the current full carrier (4472 mm²):

```text
FR4  = 44.72 cm2 x 0.0600 cm x 1.85 g/cm3                 = 4.9639 g
Cu   = 44.72 cm2 x 0.0035 cm x 8.96 g/cm3 (1 oz, full)    = 1.4024 g
mask = 44.72 cm2 x 0.0025 cm x 1.30 g/cm3                 = 0.1453 g
explicit sum                                              = 6.5117 g
repo's own rule  FR4 x 1.15                               = 5.7085 g
```

The repo's own **+15 %** rule gives 5.7085 g, the *lower* of the two; the explicit
decomposition gives 6.5117 g. **The model uses the conservative-but-cited 5.7085 g**, so
the full-carrier board mass quoted throughout is a **floor**, not a ceiling. (The gap is
almost entirely the copper line: the as-built wing has an **empty B_Cu** and only
212 mm² of F_Cu — `docs/adr/046-wing-board-interface.md` §7b, `copper_mm: 212.0` — so the
real copper is nearer 5 % of full cover than 100 %, and the true board mass sits close to
the 5.71 g figure. That is *convenient*, not *proven*; see §8 item 3.)

### 1.2 Cell mass (MARKED ESTIMATE)

```text
small: area = 52.07 mm x 19.65 mm            = 1023.18 mm2 = 10.2318 cm2
       mass = 10.2318 cm2 x 0.021 cm x 2.33  = 0.5006 g
large: area = 78.55 mm x 38.90 mm            = 3055.59 mm2 = 30.5559 cm2
       mass = 30.5559 cm2 x 0.021 cm x 2.33  = 1.4951 g
```

This is **bare silicon only** — it ignores the cell's own metallisation, busbars, tabbing
ribbon and any encapsulant. It is *marked as an estimate*.

**It disagrees with the repo by 4×.** `docs/PAYLOAD-WEIGHT-ESTIMATES.md` lines 92/96 give
the 52 × 19 mm cell as "**~2g each**". Silicon at 2.00 g would need a density of
9.3 g/cm³ (2.00 / 0.6446 cm³), which is not silicon, not solder (7.4), not glass (2.5) and
not copper (8.96 — closer, but the cell is not copper). **Neither figure is a measurement.**

> **This is the single largest uncertainty in the entire model and it changes the answer to
> Item 4.** Sensitivity, at 2.000 g/cell instead of 0.501 g:
> `(a)` wing 5.709 + 0.090 + 3×2.000 = **11.799 g** (array 47.20 g);
> `(b)` wing 1.620 + 0.090 + 3×2.000 = **7.710 g** (array 30.84 g).
> At 2 g/cell the cells — not the board — are the largest item in `(b)`.
> See §8 item 1: **weigh one cell on a 0.01 g scale before any structural decision.**

### 1.3 Solder-joint allowance (estimate)

```text
cell land 1.6 x 4.0 mm2, 0.10 mm thick: 6.4 mm3 x 7.40e-3 g/mm3 = 4.74 mg  x 6 lands
tab  land 4.0 x 1.2 mm2, 0.15 mm thick: 4.8 mm3 x 7.40e-3 g/mm3 = 5.33 mg  x 4 lands
wire joint                                                       10.00 mg  x 4 joints
                                                          TOTAL = 89.7 mg = 0.090 g/wing
```

Order of magnitude agrees with the repo's own solder-paste line
(`docs/PAYLOAD-WEIGHT-ESTIMATES.md`: "~50 mg total for V1 pad coverage"). Per-land thickness
is `TODO(unverified)` (§8 item 5).

### 1.4 The current wing and every candidate — grams

All four candidates carry the **same** 3 small cells in series (1.5 V / 0.6 W per wing),
so they differ only in structure. `c/b` = cell area ÷ board area. `W/g` = the 4-wing
array's peak power (2.4 W, ADR-006) ÷ array mass.

| Candidate | PCB area (mm²) | cell area (cm²) | PCB (g) | solder (g) | cells (g) | **wing (g)** | **array ×4 (g)** | c/b | W/g |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **(a) FULL CARRIER** (current, as built) | 4472.0 | 30.69 | 5.709 | 0.090 | 1.502 | **7.300** | **29.201** | 0.686 | **0.082** |
| **(b) SPINE + RIBS** | 1269.1 | 30.69 | 1.620 | 0.090 | 1.502 | **3.212** | **12.846** | 2.419 | **0.187** |
| **(c) CELLS ONLY + FLEX/RIBBON** | 1069.3 | 30.69 | 0.266 | 0.320 | 1.502 | **2.088** | **8.352** | 2.871 | **0.287** |
| **(d) DOUBLE-SIDED CARRIER** (6 cells) | 4472.0 | 61.39 | 5.709 | 0.179 | 3.004 | **8.892** | **35.567** | 1.373 | **0.067** |

The current wing's own outline is confirmed from a tool, not assumed: parsing
`tracker/hardware/output/gerbers_wing_v9/wing_board_v9-Edge_Cuts.gm1` gives an x-range of
`-8.0 … 176.0 mm` and a y-range of `-25.0 … 0.0 mm` → **184.0 × 25.0 mm**, i.e. the
176 × 25 mm body plus the 8 × 9 mm tab of ADR-046 §3.2. Board area 176×25 + 8×9 =
**4472 mm²**.

---

## 2. Item 2 — is a full PCB carrier the right structure at all?

### 2.1 The controlling ratio

```text
0.6 mm FR4 carrier: 0.060 cm x 1.85 g/cm3 x 1.15 = 0.1276 g/cm2 = 127.6 mg/cm2
0.21 mm Si cell   : 0.021 cm x 2.33 g/cm3        = 0.0489 g/cm2 =  48.9 mg/cm2
ratio                                            = 2.609 x
```

**Every square centimetre of PCB costs 2.61 cm² of silicon, in mass terms.** So the answer
to "maximum power per gram" is a pure area-accounting question: put PCB exactly where the
electrical interconnect and the mechanical load path require it, and let the cells be
everything else. A carrier that covers the whole cell footprint violates this by
construction — it pays FR4 for the 31 % of the outline that carries no cell.

(At 0.4 mm FR4 — the thickness `docs/hardware-design.md` line 14 already floats "oder 0.4mm
fuer Gewichtsoptimierung" — the carrier drops to **85.1 mg/cm²**, 1.74× the cell instead of
2.61×. That is a lever, not a substitute for the area argument.)

### 2.2 (a) FULL CARRIER — the current wing (176 x 25 mm body, as built)

- **PCB area** 4472 mm² (a 176 × 25 body whose 3069 mm² of cell field covers 68.6 %).
- **PCB mass** 5.709 g · **cell area** 30.69 cm² · **total wing** 7.300 g · **array** 29.20 g.
- **Stiffness verdict: excellent — and over-engineered for the job.** A 0.6 mm FR4 plate
  176 mm long is a stiff, warp-resistant cantilever; the cells are fully supported and
  protected; the *whole* arm is a structural member. It is the stiffest option by a wide
  margin and the only one where the solar cells are not themselves in the load path.
- **Hand-assembly difficulty: lowest.** One board, one flat cell placement, lands printed
  under every cell, all 6 cell connections reachable from the top face. This is the option a
  jig can be built for once and repeated 4× identically.
- **Verdict: structurally right, mass-wrong.** 5.709 g of board to carry 1.502 g of silicon.
  It is **4.089 g heavier per wing (16.35 g per array)** than the spine alternative for the
  same 2.4 W. Against a ~14 g whole-payload target the array alone would be 29.2 g.

### 2.3 (b) SPINE + RIBS — recommended

Concrete geometry: a **160.2 × 6.0 mm spine** along one long edge, **4 ribs** of
19.65 × 3.0 mm across the cell width, the 8 × 9 mm tab at the root; the three cells bridge
the gaps between ribs and overhang the spine.

- **PCB area** spine 961.3 + ribs 235.8 + tab 72 = **1269.1 mm² (28.4 % of the full carrier)**.
- **PCB mass** **1.620 g** · cell area 30.69 cm² · **total wing 3.212 g** · **array 12.846 g**.
- **Stiffness verdict: adequate in bending, weak in torsion — and that is acceptable here.**
  The spine is a 6 mm wide, 0.6 mm thick strip: its second moment of area about the bending
  axis is `I = b·t³/12 = 6 × 0.6³/12 = 0.108 mm⁴` against the full carrier's
  `25 × 0.6³/12 = 0.450 mm⁴`, i.e. **1/4.2 of it** — so at equal thickness `EI` falls by
  4.2× and the arm is correspondingly more flexible in bending (and worse still in torsion,
  where the spine's offset centroid has no help from the plate). The cells themselves contribute nothing structural: a 0.21 mm bare cell bonded at
  its ends is a film, not a stressed skin. **Why that is acceptable:** the vehicle floats
  where the air is thin. The whole 4-arm array presents ~175 cm² of flat plate, and the
  face-on drag on it is

  ```text
  F = ½ ρ v² Cd A  (v = 5 m/s ascent, Cd = 1.2, A = 4 × 168.2 × 26 mm = 174.9 cm²)
    20 km: ρ = 0.0883 kg/m3 → F = 0.02317 N = 2.36 g-equivalent
    25 km: ρ = 0.0400 kg/m3 → F = 0.01050 N = 1.07 g-equivalent
    30 km: ρ = 0.0180 kg/m3 → F = 0.00472 N = 0.48 g-equivalent
  ```

  a fraction of a gram of load at float altitude. **The wing does not need to be stiff; it
  needs to not fall apart**, and the spine does that. `TODO(unverified)` (§8 item 6): the
  aerodynamic load at the *actual* float altitude, and the shock load at launch/release —
  neither is analysed anywhere in the repo (ADR-046 §7 item 8 records the same gap).
- **Hand-assembly difficulty: moderate.** The cells must be positioned and wired by hand
  (30AWG, as `docs/hardware-design.md` already plans), and each cell needs at least two
  support points so it cannot flap; the ribs provide them. The 6 cell lands sit on the ribs
  rather than under the whole cell.
- **Verdict: recommended.** It keeps a real load path, it keeps the "one identical board × 4,
  one order line" property of ADR-046 §5.1, and it saves **16.35 g on the array** — more than
  the whole payload mass target.

### 2.4 (c) CELLS ONLY + FLEX/RIBBON HARNESS

Cells joined by a 50 µm polyimide flex (160 × 6 mm) plus a 12 × 9 mm root tab carrying the
4-pin interface; the hub takes all mechanical load.

- **PCB area** 1069.3 mm² *of a different material class* (polyimide 1.42 g/cm³, not FR4).
- **PCB mass** **0.266 g** (flex 0.075 + flex copper 0.066 + root tab 0.138 — note this is
  **not** FR4, so the 2.61× area argument does not apply to it). Cell area 30.69 cm².
  **Total wing 2.088 g · array 8.352 g · W/g 0.287 — the best in the table.**
- **Stiffness verdict: unacceptable as a structure; acceptable as a *harness*.** A 50 µm
  polyimide strip has essentially zero bending stiffness; with no wing PCB there is no
  member to hold the arm out at 90°, so the four cells of an arm hang from a flex. Nothing
  stops the arm folding back onto the hub or flapping. The 6.0 V series chain is owned by the
  hub (ADR-046 §2.3), so the *electrical* function survives; the *geometric* function — hold
  the cell plane toward the sun — does not.
- **Hand-assembly difficulty: highest.** Every cell needs a flex tail attached (solder or
  ACF), the cells have no carrier to align to, and the 4-arm 90° geometry must be fixtured
  entirely at the hub.
- **Verdict: rejected as the wing, but adopt its *idea*.** The ribbon-harness part is good:
  0.5 m of 30AWG per wing costs about 0.23 g and is already the plan in
  `docs/hardware-design.md`. Keep the wire, keep the spine.

### 2.5 (d) DOUBLE-SIDED CARRIER — does the dark side produce anything useful?

**No. Plainly: the dark side produces nothing useful.** Three independent reasons:

1. The cells are **polycrystalline silicon — opaque**. Photons do not reach the second cell.
2. The two faces of a flat 0.6 mm FR4 carrier are **parallel and 0.6 mm apart**, so the
   sunward cell casts an essentially perfect geometric shadow on the cell on the far face.
   There is no angle at which both are lit.
3. The only light that could reach the far face is reflected off the balloon envelope, and
   the repo's derate model already treats the envelope as an **occluder** (`envelope
   shading ≈ 0.9`, `docs/SOLAR-PIN-REGULATORY.md` §1.1), not as a reflector. Counting the
   dark face would double-count a term that is already inside the 0.35 derate.

Numbers: **(d) wing 8.892 g and array 35.567 g for exactly the same 2.4 W as (a)** —
`W/g 0.067`, the worst in the table, because 3.004 g of cells are added and 0 W is added.
Its fill factor 1.373 is an artefact of counting dead cell area as filled.

- **Stiffness verdict:** identical to (a) — same board.
- **Hand-assembly difficulty:** worst of the full-carrier options: 12 lands (6 per face),
  two placement fixtures, and the back-face cells must be soldered blind.
- **Verdict: rejected.** It is strictly worse than (a) on every axis.

> **Do not conflate two different "double-sided" questions.** The **board** must have copper
> on both faces — that is forced, because the small cell has **one pad on the front face and
> one on the back** (operator caliper) and a single-sided board therefore cannot series-chain
> it (this is the known defect of the board as built). The **cell population** on both faces
> is separately unnecessary and mass-negative. Required: 2-layer copper. Rejected:
> cells on both faces.

### 2.6 Recommendation of Item 2

**Adopt (b) SPINE + RIBS.** It is the only candidate that is simultaneously light
(3.212 g/wing, 12.846 g/array — a **55.9 % cut** from the current 29.201 g), structurally
real (a 6 mm FR4 spine plus 4 ribs is a genuine load path that holds the 90° arm), and
buildable by hand (one board × 4, one order line, ADR-046 §5.1 preserved).
Option (c) is 4.5 g lighter again on the array but has no structure at all; its *harness*
technique (30AWG ribbon) should be folded into (b), which is where the 0.090 g solder +
wire allowance already comes from.
Option (a) should not be ordered at 0.6 mm FR4 for a mass-bound vehicle. If the operator
insists on a full carrier for handling robustness, the honest statement is that it costs
**+16.35 g** and the mass target must be re-set accordingly.

---

## 3. Item 3 — shape of one arm of the 4-arm 90° cross

### 3.1 The geometry is not free — 3 cells in series set the packing

ADR-006 fixes **3 cells in series per wing, 12 cells total**. Two packings of those three
cells exist, and the sweep below (root r0 = 11 mm = the hub's half-width,
`docs/hardware-design.md` line 13) shows they differ in mass *and* in shape:

| Cell size | packing | outline (mm, incl. 8 mm tab) | AR | arm tip r1 | PCB (mm²) | PCB (g) | wing (g) | fill | span (mm) | I (kg·m²) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| small | long+narrow (3 in a row) | 168.21 × 26.65 | 6.01 | 179.2 | 1269.1 | 1.620 | 3.212 | 2.419 | 358.4 | 3.662e-5 |
| small | short+wide (2 rows, 2+1) | 114.14 × 48.30 | 2.20 | 125.1 | 1143.5 | 1.460 | 3.052 | 2.684 | 250.3 | 1.745e-5 |
| large | long+narrow (3 in a row) | 247.65 × 45.90 | 5.22 | 258.6 | 1976.7 | 2.523 | 7.099 | 4.637 | **517.3** | 1.653e-4 |
| large | short+wide (2 rows, 2+1) | 167.10 × 86.80 | 1.83 | 178.1 | 1807.8 | 2.308 | 6.883 | **5.071** | 356.2 | 7.755e-5 |

`I` is one arm's moment of inertia about the hub's vertical axis,
`I = m(r1³ − r0³) / (3(r1 − r0))` for a uniform rod from r0 to r1; the vehicle's is 4× that.

### 3.2 Aspect ratio, long-narrow vs short-wide

- **Fill factor favours short-and-wide**, because the second row's cells are carried by the
  same spine: small cells 2.684 vs 2.419 (+11 %), large cells **5.071 vs 4.637** (+9 %).
  The mass difference is small (3.052 vs 3.212 g/wing for small; 6.883 vs 7.099 g for large).
- **Span and inertia favour short-and-wide decisively for the large cell**: 356 mm span
  instead of 517 mm, and `I` less than half. A 517 mm tip-to-tip span means every arm's tip
  is 259 mm from the hub — awkward to launch, awkward to handle, and it triples the
  `m·r²` term that any spin or swing has to accelerate.
- **Long-and-narrow is nevertheless the right answer for the SMALL cell**, for one reason the
  table hides: a single-row arm has *one* cell across the width (19.65 mm), which is what lets
  a single 6 mm spine carry the whole arm with 3 mm ribs. A two-row arm needs the ribs to span
  ~43 mm and the cell-to-cell interconnect to cross rows, and its 48 mm width doubles the
  array's face-on drag area for the same power.

### 3.3 Effect on the vehicle's rotation and aerodynamic stability

- **Rotation.** A 4-arm coplanar cross has 4-fold symmetry: no net aerodynamic torque to
  drive a rotor, and no in-plane preferred direction, so it does not weathervane within its
  plane. It is not a windmill (zero pitch). What aerodynamic torque does exist comes from the
  cross being a drag plate, and it is small (§2.3: ≤ 2.4 g-equivalent of drag force, and that
  is a *translational* force, not a couple). A higher `I` makes the vehicle *harder* to spin
  up — the long-narrow small-cell arm has `I = 3.662e-5` vs `1.745e-5` for short-wide, a
  **2.10×** difference, so at equal disturbing torque it spins at roughly half the rate.
- **Is spinning bad?** For this architecture, no — ADR-006 §"3D-Solar-Vorteil" treats rotation
  as *beneficial* ("Selbst bei Rotation des Ballons werden verschiedene Wings beschienen").
  A coplanar 4-arm cross cannot light all four wings at once regardless of spin, so there is
  no spin rate to protect. The real argument for higher `I` is the opposite one: a **slower,
  statelier** rotation avoids centrifugal and gyroscopic loads on a 179 mm arm and keeps the
  thermal/electrical duty cycle stable.
- **Out-of-plane stability.** The socket spec §1 (as written) makes wings 1–2 horizontal and
  wings 3–4 inclined ≈30° below the hub plane, which puts the array's centre of mass below the
  hub → pendulum/gradient stability, exactly the right behaviour for a suspended balloon
  payload. ADR-048 §5 item 6 already records that this sentence contradicts ADR-046 §4.1's
  "90° to the hub plane" and that no rotation is asserted by the footprint. **The two
  statements must be reconciled before the shape is frozen** — it is a real design fork
  (coplanar cross vs. tilted 4-arm), and it changes the array's angular coverage, not just its
  cosmetics.
- **Self-shading.** Four coplanar arms never shade each other. Four *tilted* arms can shade
  the horizontal ones near the hub at low sun — a small, near-hub effect.
- **Drag area.** Flat-plate drag scales with total arm area, and the two packings have
  essentially the same cell area; the short-wide packing pays more because its ribs are
 wider: for the small cell the rib area rises from 4 × 19.65 × 3 = 235.8 mm² to
 3 × 48.30 × 3 = 434.7 mm², i.e. **198.9 mm² (1.99 cm²) of extra board = 0.254 g per wing**,
 and the array's face-on drag area grows with the wider arm.

### 3.4 Should the 4 arms be identical?

**Yes — the boards must be identical; the deliberate asymmetry belongs in the assembly angle.**

1. **One design, one order line.** ADR-046 §5.1 fixes "one wing design, used four times";
   a second wing outline doubles the design and order complexity for no benefit.
2. **The series stack demands equal sources.** ADR-046 §2.3: the 6.0 V string's current is
   set by the *weakest* element. Four identical wings are four equal 1.5 V sources; a
   deliberately different arm (say one shorter wing) would become the string's limiting cell
   and would silently cap the whole array.
3. **4-fold symmetry avoids a mass imbalance.** An asymmetric arm moves the array's centre of
   mass off the hub and gives the pendulum a preferred swing direction, which feeds the
   rotation it was meant to avoid.
4. Identical arms also make self-shading symmetric and predictable.

**The asymmetry that *is* wanted is the assembly tilt** (wings 1–2 horizontal, 3–4 at ≈30°),
because it is set at soldering time at zero mass cost (socket spec §1, "only the assembly
tilt differs, and the tilt is set at soldering time, not by copper"). Keep it — but note the
contradiction in §3.3 above and resolve it.

### 3.5 Concrete recommended outline — BOTH cell sizes

**SMALL cell (52.07 × 19.65), spine wing, 3 in series — the recommendation**

| Element | Value |
|---|---|
| Cell field | **160.2 × 19.65 mm** (3 × 52.07 mm cells + 2 × 2.0 mm interconnect gaps) |
| Spine | **160.2 × 6.0 mm** along one long edge |
| Ribs | **4 × 19.65 × 3.0 mm** (at x = 0, 53.1, 106.2, 160.2) |
| Root tab | **8.0 × 9.0 mm** (unchanged from ADR-046 §2.1) |
| **Total outline** | **168.2 × 25.65 mm** (round to **168 × 26 mm**) |
| Board area | 1269.1 mm² · **1.620 g** · fill 2.419 |
| Arm tip radius / span | 179.2 mm / **358.4 mm** tip-to-tip |

**LARGE cell (78.55 × 38.90), spine wing, 3 in series — short-and-wide packing**

The one-row packing is **rejected**: 3 × 78.55 mm forces a **247.65 mm arm** and a
**517 mm** span for 0.216 g of saving. Use two rows instead:

| Element | Value |
|---|---|
| Cell field | **159.1 × 79.8 mm** (2 rows: 2 cells + 1 cell, 2.0 mm gaps) |
| Spine | **159.1 × 6.0 mm** along one long edge |
| Ribs | **3 × 86.8 × 3.0 mm** |
| Root tab | **8.0 × 9.0 mm** |
| **Total outline** | **167.1 × 86.8 mm** |
| Board area | 1807.8 mm² · **2.308 g** · fill 5.071 |
| Arm tip radius / span | 178.1 mm / **356.2 mm** tip-to-tip |
| Wing / array | 6.883 g / 27.53 g · **7.20 W** at 12 cells × 1.2 A |

(Check: 3 × 0.6 W = 1.8 W/wing × 4 = 7.2 W peak, `6.0 V × 1.2 A`.)

Note the large cell's fill factor (5.071) is **2.1× the small cell's** — a bigger cell
amortises the same spine over more silicon. That is the strongest technical argument for the
large cell, and it is a *structures* argument, not an electrical one.

---

## 4. Item 4 — fill factor, and what the ratio costs

|candidate|cell area ÷ board area|PCB (g) per wing|PCB grams per cm² of cell|
|---|---:|---:|---:|
|(a) full carrier|**0.686**|5.709|0.186|
|(b) spine + ribs|**2.419**|1.620|0.053|
|(c) cells only + flex|**2.871** (against flex area, a different material)|0.266|0.009|
|(d) double-sided carrier|**1.373** nominal — but **0.686 per *illuminated* cm²**, because half the counted cell area is dark|5.709|0.186 (per lit cm²)|

**What the ratio costs, in grams.** The fill factor is just the inverse of the board's
area overhead, so it converts directly into grams at 127.6 mg/cm² of 0.6 mm FR4:

```text
current wing: 4472.0 mm2 board, of which 3069.4 mm2 sits under a cell
              4472.0 - 3069.4          = 1403 mm2 of board carrying NO cell
              14.03 cm2 x 0.1276 g/cm2 = 1.790 g per wing = 7.16 g per array
spine wing  : 1269.1 mm2 total board  = 1.620 g per wing = 6.48 g per array
              board material removed  = 4472.0 - 1269.1 = 3202.9 mm2
              32.03 cm2 x 0.1276 g/cm2 = 4.087 g per wing = 16.35 g per array
```

So: **the full carrier's overhead over the (b) spine is 4.089 g/wing = 16.35 g/array**, of
which **1.790 g/wing is board that carries no cell at all** and the remaining 2.299 g/wing is
board that sits *under* the cells and is not needed there — a spine is enough beneath a cell.

### 4.1 The single largest mass item, and whether it can be removed

**In every candidate except (c), the largest item is the PCB carrier** —
(a) PCB 5.709 g vs cells 1.502 g (3.8×), (b) PCB 1.620 g vs cells 1.502 g (1.08×),
(d) PCB 5.709 g vs cells 3.004 g (1.9×).

**Can it be removed? Yes — mostly, and that is the whole recommendation.** The PCB's job is
threefold: (i) hold the 4-pin tab interface, (ii) route the wing's 3-cell series chain to the
hub, (iii) keep the cells aligned and keep the arm extended. Requirements (i) and (ii) need a
few hundred mm²; requirement (iii) needs a spine and ribs. **None of the three needs a
44.7 cm² plate.** Moving (a) → (b) removes **71.6 %** of the board mass; moving (a) → (c)
removes **95.3 %** and takes the structure with it.

**The cells cannot be removed** — they *are* the power source. The only cell-side levers are
(a) higher W/g cells and (b) not paying for cell area that never sees the sun (rejecting (d)).
Both cell sizes have the same W/g, `0.400 W/g` (0.200 W / 0.5006 g and 0.600 W / 1.4951 g —
the ratio is identical by construction, since power and mass both scale with area). **Cell
size is therefore not a W/g lever; carrier area is.**

**Caveat, restated:** if the repo's ~2 g/cell figure is right, the cells become the largest
item (6.000 g vs 5.709 g in (a); 6.000 g vs 1.620 g in (b)) and the "largest item" answer
flips. §8 item 1.

---

## 5. Item 5 — is a SINGLE WING BOARD CARRYING BOTH CELL SIZES a good idea?

**No. Reject it, from this lens, on two independent quantitative grounds.**

### 5.1 The series current is set by the weakest cell — the large cell's current is worth zero

The wing's 3 cells are in **series** (ADR-046 §2.1), and ADR-046 §2.3 states the rule
explicitly: the string current is set by the *weakest* element.

```text
small cell listing current: 400 mA
large cell by area:         30.5559 cm2 x (400 mA / 10.2318 cm2) = 1194.7 mA ≈ 1.2 A
series string current       = min(400 mA, 1200 mA) = 400 mA
```

**Contributing a large cell to a mixed string adds 30.5559 cm² and 1.4951 g and adds
0.000 A.** Per large cell inserted the array mass rises by 1.4951 g + its carrier share and
the power rises by **0 W**, so W/g strictly decreases. This is not a preference; it is the
series rule applied to two different current classes.

### 5.2 The board needed to carry both is enormous

A layout that carries 3 small **and** 1 large in one arm (worst case, in-row):

```text
length = 3 x 52.07 + 2 x 2.0 + 2.0 + 78.55          = 240.8 mm
width  = 19.65 + 2.0 + 38.90                        =  60.6 mm
full-carrier board area = 240.8 x 60.6              = 14592 mm2  (vs 4472 mm2 now)
board mass = 145.92 cm2 x 0.06 cm x 1.85 x 1.15     = 18.63 g per wing
```

**18.63 g of PCB per wing — 12.92 g more than the current full carrier, 51.7 g more per
array.** Even on the recommended spine structure the mixed board costs 2.865 g of PCB against
1.620 g (+1.245 g/wing, **+4.98 g/array**) — paid for a cell that contributes no current.

### 5.3 What to do instead

- **Keep the array homogeneous.** Build the 12-cell small-cell array that ADR-006 already
  fixes, on the (b) spine wing: 12.846 g, 2.4 W.
- **If the large cells are to be used, give them their own homogeneous array** — all 12 the
  same size, so the string current is 1.2 A throughout: `12 × 0.6 W = 7.20 W` peak, but
  `12 × 30.5559 cm² = 366.7 cm²` of cell area and `12 × 1.4951 = 17.94 g` of cells alone, on
  the short-wide outline of §3.5 (array 27.53 g). That is a **different vehicle**, not a
  mixed wing.
- **Never mix the two cell classes in one series string.** If a mixed mission is required, the
  only correct topologies put the classes in **parallel** branches or on separate converters —
  both outside this lens and both contradicting ADR-006's single 6.0 V series stack.

---

## 6. Recommendation summary

| Item | Answer |
|---|---|
| 1 | Full model committed: `docs/analysis/wing_mass_model.py`. Current wing **7.300 g**; spine **3.212 g**; cells-only **2.088 g**; double-sided **8.892 g**. |
| 2 | **No**, a full carrier is not right for max W/g. **Recommend (b) SPINE + RIBS**: 1.620 g of PCB, 3.212 g/wing, **12.846 g/array** (−16.35 g), W/g **0.082 → 0.187** (2.28×). (c) is lighter still but has no load path; (d) is strictly worse than (a). |
| 3 | Arms **identical**, asymmetry only in assembly tilt. Small cells: **168.2 × 25.65 mm**, arm tip 179.2 mm, span **358.4 mm**. Large cells: **167.1 × 86.8 mm** short-and-wide (the 247.65 mm one-row arm is rejected), span 356.2 mm. |
| 4 | Fill factor **0.686 → 2.419** measured as cell ÷ board area. The full carrier's overhead costs **16.35 g per array**. Largest item is the **PCB**, and it **can be removed** (−71.6 % of board mass) — subject to §8 item 1. |
| 5 | **Rejected.** A mixed wing adds 1.4951 g and 30.6 cm² per large cell for **0 extra amps** (series rule), on a board that would be 18.63 g full-carrier / 2.865 g spine. Use one homogeneous array instead. |

---

## 7. Where the grams actually are (full-carrier wing, for the reader's eye)

```text
small cells (Si est.)  ████                    1.502 g (20.6 %)
0.6mm FR4 carrier      ███████████████         5.709 g (78.2 %)
solder + wire          ▏                       0.090 g ( 1.2 %)
                                               -------
                                               7.300 g per wing  ->  29.201 g per 4-wing array
```

---

## 8. TODO(unverified) — the exact open questions

1. **What does one 52.07 × 19.65 mm cell actually weigh?** The model computes **0.5006 g**
   from area × thickness × silicon density; `docs/PAYLOAD-WEIGHT-ESTIMATES.md` lines 92/96
   say **~2 g**. The two differ by 4× and they flip the "largest mass item" answer. Settle
   it with a 0.01 g scale on the cells already in hand. **Do this before any structural
   decision.**
2. **Does a large cell really deliver ~1.2 A?** The 1.2 A figure used throughout is
   **inferred by area** (30.5559 cm² × 39.1 mA/cm²), not measured, and the large cell's pad
   layout is not yet confirmed. A one-cell IV measurement settles it.
3. **What is JLCPCB's outer copper weight on the 0.6 mm 2-layer stack, and what copper
   fraction will the new board actually have?** The model's 1 oz figure is an assumption; the
   as-built wing has an empty B_Cu and only 212 mm² of F_Cu. Neither the copper thickness nor
   the coverage of a new design is in any in-repo source.
4. **What are the real solder-mask thickness and density?** 0.025 mm / 1.30 g/cm³ are
   placeholders; the mask line is only 0.1453 g per wing, so this is a minor term, but it is
   unsourced.
5. **What is the real solder volume per joint?** The 0.10 mm (cell land) and 0.15 mm (tab
   land) fillet thicknesses are assumptions; the 10 mg per wire joint is a placeholder.
6. **What is the aerodynamic and shock load on a 179 mm arm, at the actual float altitude
   and at launch/release?** §2.3's drag figures are computed at 5 m/s ascent with standard-
   atmosphere densities (20/25/30 km). No source in the repo gives the float altitude, the
   ascent rate profile, or a launch shock figure, and ADR-046 §7 item 8 records that the tab
   fillet's structural adequacy under the 176 mm cantilever is **not analysed anywhere**.
   The spine's stiffness verdict in §2.3 rests on this gap.
7. **Is the wing 90° to the hub plane (ADR-046 §4.1) or are wings 1–2 horizontal and 3–4
   inclined 30° (socket spec §1)?** Already recorded as ADR-048 §5 item 6 / sheet item
   OPEN-23. It changes the array's angular coverage — a shape question, not a cosmetic one.
8. **Do the 3 cells sit in one row or two rows?** §3.5 picks one row for the small cell and
   two rows for the large cell on mass/shape grounds; whether the *assembly jig* and the
   30AWG interconnect can be built that way is not established in any in-repo source.
9. **Is 0.4 mm FR4 acceptable for a 168 mm spine** (JLCPCB availability, handling, warpage)?
   It would cut the spine from 1.620 g to 1.206 g (−0.414 g/wing, −1.66 g/array). ADR-046 §3.2
   already carries the 0.6 mm availability question; the 0.4 mm variant is a further unknown.

## 9. What this analysis does NOT establish

- It contains **no measurement** of any physical part. All masses are arithmetic on cited
  constants and caliper dimensions.
- It does not re-derive any electrical decision. ADR-006's array, ADR-046's 4-pin tab and
  series stack, ADR-047's 6.15 W provisioning and ADR-048's hub sockets are taken as given.
- It does not authorise a board change. The wing as built passes its order gate
  (`pcb_order_gate.py` → `ORDER GATE: PASS`, 0 errors / 0 unconnected,
  `docs/adr/046-wing-board-interface.md` §7b); this analysis says that board is the wrong
  *structure* for a mass-bound vehicle, which is a design question for the operator.
- It does not budget the hub. `docs/POWER-BUDGET-V9-D2BE.md` §4 already carries the hub's
  own mass table with supercaps (3.00 g) and FR4 (2.76 g for the 55.15 × 45.15 mm v8i);
  the v9 hub outline is unfixed (ADR-048 §5 item 5).
