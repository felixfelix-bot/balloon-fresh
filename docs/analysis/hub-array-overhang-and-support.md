# Hub array overhang and support — what "panels may overhang the board" changes

**STATUS: CONSULTANT ANALYSIS, not a decision record.** Nothing here is an operator decision,
an accepted ADR, or an authorisation to change `tracker/hardware/hub_board_v9.kicad_pcb`, any
schematic, netlist, BOM or footprint. **No hardware is ordered by this analysis. No outline is
frozen for fab, and no board is re-placed.** Every number below is either **CITED** to an in-repo
source, **COMPUTED** by the committed script `docs/analysis/hub_array_overhang_model.py`
(formula shown inline), or marked `TODO(unverified)` naming the exact open question. **Nothing is
invented — in particular no material strength, no allowable and no modulus beyond the one the
repo already carries.**

- **Date:** 2026-10-08
- **Branch:** `analysis/array-overhang-support` · **Worktree:** `/home/c03rad0r/worktrees/bf-arrayover`
- **Base:** `github/main` @ `716974a`
- **Model:** `docs/analysis/hub_array_overhang_model.py` — run
  `python3 docs/analysis/hub_array_overhang_model.py`. Every figure quoted below is that
  script's own printed output.
- **Decision it underwrites:** the **ADR-055 amendment of 2026-10-08** (the operator's overhang
  decision) and **ADR-063** (the outline/support consequence).
- **Lens:** mechanical support of the **end-only, unbonded 0.21 mm cells** on the **hub** array,
  once the hub board is no longer required to be as large as the array. The wing structure, the
  electrical topology (ADR-006/046/051/054), the charge path (ADR-050) and the fab pipeline
  (ADR-030) are taken as given and are **not** re-derived.

---

## 0. The one-line answer

**Allowing the panels to overhang decouples board area from array area, and that is the whole of
its mechanical consequence — it removes the board from the cell's support path over the
overhanging span and does not remove the need for support.** The board can shrink to what the
**components** need (a measured **2582 mm²** courtyard ⇒ ≈**60 × 60 mm**, §5), while the cells are
carried by a **separate rib/strip carrier at a pitch the cells can tolerate** (§3, §6).
**The pitch is the one number that decides the design and it is NOT in the record** — the 0.21 mm
cell's flexural strength appears in no in-repo source and in no datasheet the operator has sent,
so **the maximum unsupported span is `TODO(unverified)`** and is closed by one named bench test
(§7). Two arithmetic findings ride along and are worth recording on their own:

1. **A 103 × 103 mm board cannot hold the cells ADR-055 D5 sized it for.** Only **2** LARGE cells
   tile inside 103 × 103 mm (**61.11 cm²**), while the 106.1 cm² target needs **≥ 4**. ADR-055 D5's
   board was **arithmetically too small for its own array target** — which is exactly the coupling
   the operator's decision breaks (§2).
2. **Overhang buys duty margin, not just board saving.** With the array free to overhang, the
   achievable array area is no longer 106.1 cm² (a board-driven number) — 4 LARGE cells
   (122.2 cm² = 115 % of full duty) or 6 (183.3 cm² = 173 %) are reachable (§4).

---

## 1. The decision, and what it is not

**Operator decision, verbatim, 2026-10-08:**

> **"I'm fine with panels overhang[ing] the board. No need to waste board space."**

This is the authoritative design decision. It is **not** re-litigated here. What it means
mechanically, stated once:

- Until now the hub outline was driven by the **array**: ADR-055 D5 sized the hub at
  **103 × 103 mm = 106.09 cm²** precisely so a 106.1 cm² array would fit, and that is why a
  55 × 45 mm outline was rejected (`tracker/hardware/PLACEMENT-S0-FREEZE-v9-hub.md` §3).
- If cells may overhang, **board area and array area are two independent numbers**. The outline is
  then driven by the **components + the attachment lands**, and the array may be as large as its
  own support allows.
- **The board stops being the cell's support across the overhanging span.** Something else must
  carry the cell there, or the cell flexes and cracks. The decision **relocates support mass**;
  it does not delete it. That relocation is the subject of §3, §6 and §7.

---

## 2. The arithmetic that raised the question, checked

### 2.1 Does "only ~2 cells tile inside a 103 mm square" hold?

**Yes — verified, and the bound is proved, not just searched.** A LARGE cell is
**78.55 × 38.90 mm** (ADR-049 Measured inputs). Place cells in a 103 × 103 mm square:

```
along an axis, at most floor(103 / 38.90) = 2 cells can stack on their 38.90 mm side.
2 stacked long-ways cells occupy 78.55 x 77.80 mm, leaving 25.20 mm of height
   -> nothing more fits (the cell's smallest side is 38.90 > 25.20).
one long-ways cell (78.55 x 38.90) leaves a 24.45 mm x-strip (useless) and a
   64.10 mm y-band; a second long-ways cell fits there, a short-ways cell needs
   78.55 mm of y and does not.
=> maximum 2 LARGE cells, i.e. 2 x 30.5559 = 61.11 cm^2
```

(`max_cells()` in the model reproduces this by bottom-left candidate search: **2**.)
**61.11 cm² is 58 % of the 106.1 cm² target.** So the observation in the task is **correct**.

### 2.2 Is "4 LARGE cells are the minimum that covers 106.1 cm²" wrong?

**No — it is correct as an AREA statement, and it is consistent with §2.1. The two statements
together are the finding.**

```
area minimum: 106.1 / 30.5559 = 3.47 LARGE  -> 4 cells (122.2 cm^2)  >= 106.1
              3 LARGE = 91.7 cm^2 < 106.1   (ADR-055 §8 append reads the same)
tiling limit: only 2 LARGE fit in 103 x 103 mm (61.11 cm^2)
```

**Verdict: the earlier claim is NOT wrong, but ADR-055 D5 is internally inconsistent.** The board
D5 sizes at 103 mm cannot hold the ≥ 4 LARGE cells its own 106.1 cm² target requires; 4 cells
need a 2 × 2 block of **157.1 × 77.8 mm**, which overflows the 103 mm square by 54 mm on one axis.
So the 106.1 cm² "full duty" figure was **never realisable on the board D5 specified** — it needed
either a bigger board or the overhang the operator has now authorised. (For completeness: SMALL
cells 52.07 × 19.65 tile **8** = 81.85 cm² in the same square, **77 %** of target — also short.)

**This is the strongest single reason the operator's decision is the right one**: the board D5
chose could not have carried D5's own array anyway.

---

## 3. Question 1 — the maximum unsupported span of a 0.21 mm cell

### 3.1 The honest answer first

**There is no sourceable allowable.** A repo-wide search for a silicon flexural strength, a
modulus of rupture, a bend strength or an allowable span returns **nothing**: the repo carries
only the cell's **geometry** (0.21 mm thickness, ADR-052/§1.5), its **areal mass**
(48.93 mg/cm², `wing-mass-shape.md` §2.1) and **one elastic constant** — Si modulus
**170 GPa**, carried as "standard" in `docs/analysis/hub-thickness-deflection.md` §3. **No strength
is in the repo and no datasheet the operator sent states one.** Per the repo's own honesty rule
and ADR-055 §8's precedent — *"a precise-looking number built on an invented modulus is worse than
a named gap"* — **the maximum unsupported span is `TODO(unverified)`**, and §7 names the bench
measurement that supplies it. What this section *can* do is give the **demand** on the same
metric, so that any measured allowable converts to a span in one step.

### 3.2 The demand — 0.21 mm silicon under its own weight

The **end-only mount is a simply-supported beam** whose span is the cell's own length: the cell is
soldered at its two ends (ADR-052 §2.1) and is unsupported everywhere between them. For a
rectangular section of width `b`, thickness `t`, under its own distributed weight:

```
sigma_max = 3 rho g L^2 / (4 t)          (derived: M = m g L / 8, Z = b t^2 / 6, m = rho b t L)
delta_max = 5 rho g L^4 / (32 E t^2)     (derived: delta = 5 w L^4 / (384 E I), I = b t^3/12)
```

with `rho = 2330 kg/m³` (crystalline Si, physical constant), `g = 9.80665 m/s²`,
`t = 0.21 mm`, `E = 170 GPa` (the repo's own value). The model prints:

| span (mm) | σ @ 1 g (MPa) | σ @ 2 g (MPa) | δ @ 1 g (µm) |
|---:|---:|---:|---:|
| 19.65 (SMALL cell width) | 0.032 | 0.063 | 0.1 |
| 38.90 (LARGE cell width) | 0.123 | 0.247 | 1.1 |
| 52.07 (SMALL cell length) | 0.221 | 0.443 | 3.5 |
| **78.55 (LARGE cell length)** | **0.504** | **1.007** | **18.1** |
| 100.0 | 0.816 | 1.632 | 47.6 |
| 103.0 | 0.866 | 1.732 | 53.6 |

**Read this carefully.** Under **1 g** the full-length LARGE cell (78.55 mm) carries **0.504 MPa**
of surface bending stress and sags **18.1 µm**. Under the bounded launch case (**≤ 2 g**, ADR-055
§8 append / hub-thickness-deflection §8) that is **1.007 MPa / 36 µm**. The **cantilever** case —
which is what a cell becomes if **one** of its two end lands is left **uncarried** (the literal
"overhanging with nothing under the far end" failure) — is **4 ×** the stress and **9.6 ×** the
sag:

```
cantilever 78.55 mm, 1 g : sigma = 2.01 MPa, delta = 174 um
```

**All of these are DEMANDS.** Silicon's flexural strength is on the order of hundreds of MPa for
bulk wafer — but **that figure is not in the repo and is not asserted here**; it is exactly the
scope of the measurement §7 requires. What the demand table does establish without any strength
number:

- **Self-weight alone is a small load.** Even the cantilever at 1 g is ~2 MPa. The risk is not the
  static case being close to any plausible strength; it is **fatigue, handling, launch transients
  and the drop case** (hub-thickness-deflection §8 bounds a pre-launch drop as **unbounded**) —
  i.e. the *allowable* must absorb a life, not one g.
- **The demand scales as `L²/t`** (span squared over thickness). The cell's **own length is the
  span that matters** and thickness is fixed at 0.21 mm, so the only design lever is **how far a
  cell is carried unsupported**, i.e. **the rib pitch** — exactly what ADR-049's open item already
  says: *"whether spine-and-ribs leaves unsupported silicon spans that crack; **the frame's rib
  pitch is set by that answer**"* (`docs/adr/049-wing-architecture.md` §Open items).

### 3.3 Thermal is NOT the overhang differentiator

The thermal term is **independent of any support arrangement**, and this is worth stating because
it is where a reader might look for the risk. From `hub-thickness-deflection.md` §9 (CITED):

```
CTE mismatch FR4<->Si = (12..18 - 2.6) ppm/K x 80 K = 752 .. 1232 ue over the 78.55 mm cell
```

That strain is set by the cell's **length** and the two **in-plane CTEs** only. It is the reason
ADR-052 chose the **end-only, unbonded** mount (cells float) — and it is **the same number whether
the cell sits on a board, on ribs, or overhangs**. **Thermal does not choose between the support
arrangements of §6.** (ADR-052 §2.3's environment: 10–12 km, 19–26 kPa, −50…−56 °C.)

---

## 4. Question 2 — the array area achievable with overhang

### 4.1 Board area and array area are now independent

ADR-055 D5 fixed `board area = array area` (`√106.1 ≈ 103 mm`). With overhang allowed, the array's
footprint is `board side + 2 × overhang` per axis:

```
board 60 x 60 mm  (component floor, §5)
  overhang/side   footprint   footprint area   duty vs 106.1 cm^2
     0.0 mm        60.0 mm       36.0 cm^2           34 %
     8.9 mm        77.8 mm       60.5 cm^2           57 %
    15.0 mm        90.0 mm       81.0 cm^2           76 %
    21.5 mm       103.0 mm      106.1 cm^2          100 %
    25.0 mm       110.0 mm      121.0 cm^2          114 %
    48.6 mm       157.2 mm      247.1 cm^2          233 %
```

with the cell-granularity check:

```
2 LARGE cells =  61.1 cm^2 =  58 % of full duty
3 LARGE cells =  91.7 cm^2 =  86 %
4 LARGE cells = 122.2 cm^2 = 115 %
6 LARGE cells = 183.3 cm^2 = 173 %
```

### 4.2 Does overhang let the array exceed 106.1 cm² — i.e. buy duty margin?

**Yes.** The 106.1 cm² figure was a **board-driven ceiling** (`board area = array area`); with the
coupling broken it is no longer a ceiling at all. **4 LARGE cells (122.2 cm², 115 % of full duty)
fit in a 157.1 × 77.8 mm footprint**, which overhangs a 60 mm board by **48.6 mm** on the long axis
and **8.9 mm** on the short axis. So overhang buys **duty margin, not only board saving**.

### 4.3 What governs the ceiling

The ceiling is **not** board area. It is, in order of bindingness:

1. **The permitted unsupported span (the crack limit) — `TODO(unverified)`, §3/§7.** A cell can
   only extend beyond its supports by the amount the pitch allows, so the *real* ceiling is set by
   a number the record does not contain. **This is the governing term and it is unresolved.**
2. **Drag and span.** The overhung array is a flat plate: `wing-mass-shape.md` §2.3 gives
   **23.2 mN (0.144 g-equivalent)** of face-on drag for the whole 4-arm 175 cm² array at 20 km;
   the hub array is comparable in area, so drag is small next to the 1 g static case but grows
   with array area and is not the binding term in the range §4.1 explores.
3. **Mass.** Cells are 48.93 mg/cm² (`wing-mass-shape.md` §2.1) and the carrier is 85.1–127.65
   mg/cm²; each extra cell costs its mass plus whatever carries it (§6).
4. **ADR-051 §2.2's harvester input-power blocker.** A 61.2 cm² face-on array already exceeds the
   bq25570's 510 mW absolute-maximum input by **2.26×** (ADR-051 §2.2); **growing the array makes
   that worse**, not better. The duty margin overhang buys is real *only if the harvest path can
   absorb it* — either a higher-input-power harvester (LTC3105/SPV1040 class, ADR-051 §2.2's
   `TODO(unverified)` candidates) or deliberate sub-MPP operation. **An array larger than 61.2 cm²
   face-on is not usable on the named harvester without one of those two resolutions** — so the
   duty margin is *conditional on the charge path*, and that condition is carried, not hidden.

**Stated plainly:** the area ceiling is no longer a board dimension, but it is not free either —
**it is gated by (1) a bench-measured span allowance and (4) the harvester's input rating**, and
both are open.

---

## 5. Question 4 — what the components actually need, and the outline

### 5.1 The measured component floor

`tracker/hardware/PLACEMENT-S0-FREEZE-v9-hub.md` §3 records the measurement directly:

```
39 footprinted components demand 2582 mm^2 (25.82 cm^2) of courtyard
55 x 45 mm board = 2475 mm^2 (usable interior 2279 mm^2)
interior demand 2203 mm^2 into 2279 mm^2 = 96.7 % packing density  -> a best-effort pack
   left 28 of 39 parts unseated and scored 389 pad overlaps / 199 courtyard overlaps
```

**The 55 × 45 mm failure is a component-packing failure, not an array failure** — it happens with
the array entirely absent. So the component floor is a **hard lower bound independent of the
overhang question**, and it is **≈ 25.82 cm² plus attachment lands**.

### 5.2 The resulting minimum outline

At packing densities a real placer achieves (the 96.7 % demand failed; 72–80 % is the realistic
band, and every mm² of margin is worth having on a hand-assembled part count of 39):

```
25.82 cm^2 @ 72 % -> board >= 35.86 cm^2 -> square 59.9 mm
25.82 cm^2 @ 75 % -> board >= 34.43 cm^2 -> square 58.7 mm
25.82 cm^2 @ 80 % -> board >= 32.27 cm^2 -> square 56.8 mm
```

plus the four socket land rows (`4 × 8 × 4.0 × 1.2 mm = 154 mm²`) and their 1.0–5.0 mm inboard
keep-out band (ADR-048 §2.2/§2.4), and the ADR-045 antenna solder-access and ADR-040 radio sites.

**Minimum outline conclusion: ≈ 60 × 60 mm (36.0 cm²)**, i.e. **≈ 34 % of the 103 × 103 mm board
ADR-055 D5 chose** — a **66 % area reduction**, saving **5.96 g** of 0.4 mm FR4 (9.028 g → 3.064 g).
Square is retained because ADR-055 D5's square preference rests on the **four socket interfaces at
90°** (ADR-046/048), which the hub still has. The figure is **provisional pending the placement
re-run** on the new outline (§9) and pending the array support decision (§6) — it is the
**component-driven** floor, not a fab-frozen outline.

### 5.3 What it implies for the price tier

The concurrent pricing analysis (`docs/analysis/jlcpcb-pricing-and-size-tier.md`; its salvage
source `docs/analysis/jlcpcb-size-tier-quote.md` §3) measures the tier boundary **empirically**:

| largest side | 4-layer 1.6 mm, qty 5, matched options | class |
|---:|---:|---|
| 89 mm | $8.00 | cheap ("Special Offer") |
| 100 mm | $8.00 | cheap |
| 101 mm | $8.00 | cheap |
| **102 mm** | **$8.00** | **cheap (top of class)** |
| **102.5 mm** | **$31.50** | expensive (Engineering $25.00 + Board $6.50) |
| 102.9 mm | $31.60 | expensive |
| **103 mm** | **$31.60** | expensive — **the ADR-055 D5 board** |

The driver is the **largest single dimension** (proved by the `100 × 104`-vs-`102 × 102` and
`50 × 103` rows), and the split appears at 2 layers too (89/100 × 100 = $4.00 vs 103 = $9.20).
**A 60 × 60 mm outline is far inside the cheap class** — and, strikingly, **the 103 mm board
ADR-055 D5 chose sits just over the cliff at $31.60**, i.e. the shrink saves ~$24 per 5-piece
order *and* ~6 g of board. (Vendor-documented cause of the cliff is **not** stated by JLCPCB; the
salvage doc records the discontinuity as observed and does not invent a mechanism.)

> **Caveat carried:** the salvage analysis also records, from the quote page's own tooltip, that
> **0.6 mm thickness is capped at 100 × 100 mm and unavailable for 1/4/6-layer**, and that
> **0.4 mm requires ENIG**. If true, the 103 × 103 mm hub at 0.6 mm was **not orderable at all**,
> and any 0.4 mm board carries an ENIG surcharge. **The concurrent pricing doc owns this; cited
> here only so the outline decision is not made blind to it.**

---

## 6. Question 3 — the mounting arrangement, with mass and crack risk

### 6.1 The four candidates, and what each does about support

Because the board no longer reaches under the whole array, **every option must say where the
carried load goes**. The candidates, with the mass figures the repo has already measured (the
wing's own values, reused — **not re-derived**), plus the hub-scale arithmetic from the model:

| # | Arrangement | Board/structural mass | Cells (122.2 cm²) | Total | Crack risk |
|---|---|---|---:|---:|---:|---|
| **(a)** | **Full carrier** (blanket board under every cell), 0.6 mm | **13.542 g** (106.09 cm²) | 5.980 g | **19.523 g** | **LOW mechanically, but rejected for other reasons** |
| **(a′)** | Full carrier, **0.4 mm** | **9.028 g** | 5.980 g | **15.009 g** | Low *statically*; but a bonded full-face carrier re-opens ADR-052's **thermal bond** crack risk, and 0.4 mm is the un-cleared stiffness case |
| **(b)** | **Skeletonised carrier** (windows cut, board kept only where load/copper needs it) — board = **28.4 %** of footprint (the measured wing spine/full ratio, `wing-mass-shape.md` §1.4) | **2.952 g** (0.4 mm) / 4.428 g (0.6 mm) | 5.980 g | **8.932 g / 10.408 g** | **MEDIUM** — cells still sit **over** a substrate; if the residual substrate is bonded it re-opens the thermal crack; if unbonded it is just a rib frame (→ (c)) |
| **(c)** | **Spine + ribs** — **measured for the wing: 12.846 g per 4-arm array**, board 6.480 g (28.4 %) | **6.480 g** | 5.980 g | **12.460 g** | **MEDIUM — and it is the case ADR-049 already flags**: cells bridge open gaps, so **the rib pitch sets the crack limit** (ADR-049 §Open items, `TODO(unverified)`) |
| **(d)** | **Cells + ribbon harness** (cells held only at their ends by a flex/strip, minimal substrate) — **measured for the wing: 8.352 g per array**, of which the flex/tab harness is 1.872 g | harness **1.872 g** + **separate electronics board 3.052 g** (60 × 60, 0.4 mm) | 5.980 g | **10.904 g** | **HIGH** — no load path holds a plane; a cell with an uncarried end is a **cantilever (§3.2: 4× stress, 9.6× sag)**; rejected as a *wing* structure in `wing-mass-shape.md` §2.4 and no different as a hub carrier |

**Cross-checks a reader should make:**
- **(c) vs (b)** are close because (b) uses (c)'s measured board fraction; they differ only in
  whether the residual material is a **substrate under the cells** (b, bondable → thermal risk) or
  **discrete strips** (c, unbonded → ADR-052-compliant). **ADR-052 already decided that question:
  no bond.** So (b) collapses into (c) unless the windows leave a bonded face, which ADR-052
  forbids.
- **(a) vs (c)** is the **4.5 g-class** comparison the repo has already banked for the wing
  (full 29.20 g → spine 12.85 g = **−16.35 g**, ADR-052 §2.6); at hub scale, (c) vs (a′) is
  **15.009 → 12.460 g (−2.55 g)** and (c) vs (a) is **−7.06 g**.
- **Cells-alone is impossible here.** The measured cells-only wing (2.088 g) has **no load path**
  and `wing-mass-shape.md` §2.4 **rejects** it as a structure. For the hub the same holds: the
  array must be held out flat against gravity and drag by *something*.

### 6.2 Recommended arrangement

**Recommended: cells carried on a dedicated rib/strip structure — the spine-and-ribs pattern
(ADR-049) applied to the hub array — with the cells overhanging the hub board on two opposite
edges, not all four.**

Reasoning, ranked:

1. **Support must be re-established somewhere, and ribs are the pattern the record already
   validates.** The operator's decision removes the board from the support path; a rib frame puts
   a *support* back under the cell at a **pitch that is a design variable**, so the crack question
   becomes a **pitch to be set by measurement** rather than an unanswerable yes/no about the board.
2. **Two opposite edges, not all four.** With end-only lands, each cell must have **both** ends on
   a support land. Overhanging on **two opposite** edges keeps one axis of the array **fully on the
   board's own structure** (the lands and the first ribs), so at least one support line per cell is
   on solid board and only the far end is carried by a rib strip. Overhanging on **all four** puts
   **both** ends of the outer cells off-board, which (per §3.2) is the **cantilever** case — 4×
   the stress and 9.6× the sag — and it maximises the perimeter of cells with no board under them.
   **All-four overhang is the arrangement with the highest crack risk and the least mass saving;
   it is not recommended.**
3. **Unbonded, per ADR-052.** The strips are a frame; the cells are **not bonded** to them
   (ADR-052 §2.1). This keeps the thermal crack mechanism (§3.3) out of the new structure by
   construction.
4. **Mass.** The spine-and-ribs hub carrier is **12.460 g total** (board 6.480 g + cells 5.980 g)
   versus **19.523 g** for the 0.6 mm full carrier and **15.009 g** for the 0.4 mm full carrier
   (§6.1) — a **3.05–7.06 g saving** on the hub array, of the same order as the wing's banked
   16.35 g. The rib/strip board is a **separate part** from the electronics board (§5.2,
   ≈ 60 × 60 mm), which resolves ADR-055 D7's "integrated versus split carrier" question **for the
   hub** in favour of the split (the operator's decision forces it: the array is no longer confined
   to the board).
5. **Crack risk of the recommendation: MEDIUM, and unresolved.** The rib pitch is `TODO(unverified)`
   (§3.1, §7). The recommendation is safe **only at a pitch the cells are measured to tolerate**;
   that pitch is the deliverable of the coupon test. **Do not freeze a pitch from this analysis.**

### 6.3 Mass per option — summary line for the decision record

```
(a)  full carrier 0.6 mm, board = array footprint : 19.523 g   (crack risk LOW, bond risk HIGH)
(a') full carrier 0.4 mm                          : 15.009 g   (crack risk LOW-statically, bond+stiffness open)
(b)  skeletonised carrier (28.4 % board)          : 10.408 g (0.6 mm) / 8.932 g (0.4 mm)   (MEDIUM)
(c)  spine + ribs (measured, hub-scaled)          : 12.460 g   (MEDIUM — rib pitch governs)   <- RECOMMENDED
(d)  cells + ribbon harness + separate elec board : 10.904 g   (HIGH — cantilever risk; rejected as a structure)
```

(Cells = 122.2 cm² of 0.21 mm Si = 5.980 g in every row. `TODO(unverified)`: ADR-052 §2.6's
**≈ 0.15 g/cell** mounting overhead (4 cells ≈ 0.6 g) is a *derived* figure not included above;
weigh the as-built array before budgeting it.)

---

## 7. The measurement that closes the decision

**One coupon bend test supplies the missing number.** It is small, it is the operator's own bench
work (ADR-052 §2.7 already reserves the cold-soak as his), and it is the same coupon
`hub-thickness-deflection.md` §13 names — re-scoped here from the *joint* to the *span*:

> **Take one of the operator's real 78.55 × 38.90 × 0.21 mm cells and support it at its two ends
> over a gap `S`, in the real end-only manner (ADR-052: no bond). Load it to 1 g, then 2 g
> (or bend it to a measured curvature `κ`), and increase `S` until the cell cracks. Record
> `S_crack` — the unsupported span at which the 0.21 mm wafer fails — and the surface strain at
> first damage. Repeat cold-soaked at ≈ −55 °C and after N thermal cycles.**
>
> The one number it produces is **`S_crack` at the flight temperature**. With it:
> - the **rib pitch** is set directly (`pitch ≤ S_crack`, with margin for the drop case);
> - §3.2's demand table converts `S_crack` to the admissible surface stress, giving both M1 and M2
>   of `hub-thickness-deflection.md` §10 one model instead of a 1–100 µm band;
> - and the overhang length of §4 is bounded by `S_crack`, closing the array-area ceiling.

**Supporting measurements, in priority order:**
1. **Weigh the as-built hub array and one rib strip** (ADR-052 §2.7 item 2) — the load census is
   arithmetic on copies of a 4×-disputed cell mass (`wing-mass-shape.md` §1.2).
2. **Weigh the board** at both thicknesses (confirms the re-quantified 1.53 g lever, §8).
3. **Measure the panel flatness** of a bare ≈ 60 × 60 × 0.4 mm panel — the *warpage* half of
   ADR-055 D4, a build risk no coupon bend test covers.
4. **Quantify the harvester input-power headroom** (§4.3 item 4) — an array > 61.2 cm² face-on is
   outside the bq25570's rating; the duty margin is conditional on this.

---

## 8. What this implies for ADR-055's decisions

### D3 — the sustained-duty choice: **STILL OPEN**

ADR-055 D3 makes the array area the operator's **duty choice** (≈106 cm² = full duty, ≈80 = 75 %,
≈53 = 50 %), with 106.1 cm² a **ceiling, not a floor**. The overhang decision **does not choose the
duty** — it **raises the ceiling** by removing the board-size coupling (§4.2) and makes the choice
**cheaper** (a smaller board). **D3 remains open, and it is still the operator's.**

### D4 — the 0.4 mm thickness target: **AMENDED**

The **target (0.4 mm) stands**, but the quantified prize **shrinks with the board**, and the
"largest lever on the hub" claim **no longer holds at the new outline**:

```
103 x 103 mm (ADR-055 D5) : 0.6->0.4 mm saves 4.514 g   (13.542 -> 9.028 g)
 60 x  60 mm (component floor): 0.6->0.4 mm saves 1.532 g   (4.595 -> 3.064 g)
```

**D4 is amended: 0.4 mm is still the target; the lever is now ≈ 1.5 g, not ≈ 4.5 g, and the
stiffness/stack-up check (ADR-055 Open item 3) is a *different* problem** — a smaller plate that
carries **no cells** and therefore has no cell-joint strain budget at all. The existing
`hub-thickness-deflection.md` analysis (global plate + local socket) was written for a 103 mm
plate under the four wings; §7's "sub-millimetre global deflection, the socket is where it bites"
finding must be re-run against the new outline before 0.4 mm is frozen. **`TODO(unverified)`.**

### D5 — the outline coupling: **SUPERSEDED**

`board area = array area` is **superseded**. The outline is now driven by the components (§5) and
the attachment lands; the array overhangs on a separate carrier (§6). **D5's 103 × 103 mm is
retired** — and §2.1 shows it was arithmetically wrong for its own array target anyway.

### D7 — integrated versus split carrier: **RESOLVED for the hub**

The operator's decision **forces the split** (the array is no longer confined to the board), so
ADR-055 D7's "cost it, do not decide it" is **decided for the hub** in favour of a **separate
array carrier + a component-driven electronics board**.

---

## 9. The existing placement is PROVISIONAL

`tracker/hardware/hub_board_v9.kicad_pcb` is the **first v9 hub placement** (frozen by
`PLACEMENT-S0-FREEZE-v9-hub.md`, S0 PASS) on a **103 × 103 mm** outline. **That outline is now a
moving target** — this analysis retires it (§8, D5). Therefore:

> **The existing v9 hub placement is PROVISIONAL.** It is evidence that a zero-overlap placement
> of the 39 placed components is *possible*, and its **2582 mm² courtyard measurement is the
> component floor this analysis uses** — but its **outline, its seats and its placement hash are
> not a design of record** and must be re-placed on the new (≈ 60 × 60 mm) outline once the array
> support decision lands.

**No board is re-placed, re-routed or regenerated by this analysis.** Per the task constraint,
re-placing onto a moving target is exactly the waste to avoid: the outline moves **after** §7's
measurement closes the support question.

---

## 10. What this analysis does NOT establish

- **No measurement of any physical part.** All numbers are arithmetic on cited constants; the two
  decisive quantities (**the cell's flexural strength / `S_crack`**, and the harvested input-power
  headroom) are **not measured**.
- **No sourceable allowable for the unsupported span** — the central `TODO(unverified)` (§3.1).
- **No re-derivation of any electrical decision** (ADR-006/046/051/054) and no charge-path claim
  beyond citing ADR-050/051's existing harvester rating.
- **No fab authorisation, no order, no sign-off.** Design analysis only. **Order nothing.**
- **No board files touched.** `hub_board_v9.kicad_pcb` is unmodified (§9).

---

*Analysis only. No outline frozen, no pitch frozen, no board re-placed, nothing ordered.*
*Model: `docs/analysis/hub_array_overhang_model.py` (run it to reproduce every figure above).*
