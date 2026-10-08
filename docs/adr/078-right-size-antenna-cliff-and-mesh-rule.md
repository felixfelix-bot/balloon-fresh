# ADR-078 — Right-size the antenna: small dish / wide beam over big dish / narrow beam; the positioner-class cliff and the mesh rule

- **Status:** **Proposed** — an engineering analysis (the cliff is quantified; the specific rung
  choice is not operator-ratified). It orders nothing and freezes no BOM.
- **Date:** 2026-10-08
- **Decision owner:** Felix (operator) — the questions (*where is the cliff, how do we raise
  performance without crossing it, what are the sweet spots*)
- **Author:** Hermes subagent (consolidation pass), branch `design/adr-set-groundstation`
- **Related (stable references):** ADR-071 (design basis — one positioner), ADR-073 (FLRC-max),
  ADR-075 (the F33 that removes the big-dish requirement), ADR-076 (stow), ADR-077 (print/buy),
  ADR-081 (the tier ladder), ADR-034 / ADR-041 (2.4 GHz uplink, licence-exempt point).
- **Evidence:** `docs/analysis/gain-per-dollar-cliff.md` +
  `docs/analysis/gain_per_dollar_cliff_model.py` +
  `docs/analysis/assets/gain-per-dollar/fig{1,2,3}-*.png` (source branch
  `design/gain-per-dollar-cliff`, whose file `docs/adr/068-ground-station-antenna-class-cliff.md`
  is **superseded by this record** / ADR-081); the mesh/wind model in
  `docs/analysis/ground-station-flrc-max-throughput.md` §4 (source branch
  `design/ground-station-flrc-max`); `docs/analysis/positioner-lowcost-3dprinted.md` §8;
  `docs/analysis/ground-station-gain-per-dollar.md` (Yagi-before-dish). Reproduce:
  `python3 docs/analysis/gain_per_dollar_cliff_model.py`.

**Numbering and collision note.** Numbers **066–070 are claimed on sibling design branches**
(see **ADR-071 §Numbering and collision note** for the full table) and are **not reused**.
`scripts/adr_next_number.py` prints 066 because it is branch-blind. This record takes the fresh
number below (verified free, prefix-anchored, against every `github/*` branch, 2026-10-08).

---

## Context

**The operator's question is a cost-cliff question**, and the answer decides the whole station.

**1. The cliff is real, quantified, and mostly a ROTATOR-CLASS step.** Whole-station marginal cost
of the next dB of 433 gain is **~50–86 EUR/dB up to a ~1.0 m dish**, then **~592 EUR/dB across the
1.00 → 1.20 m step** — a **6.9× jump** driven by the purchasable AZ+EL rotator price stepping from
**EUR 359** (Yaesu G-450CDC) to **EUR 1,132** (SPX-01) and **EUR 1,775** (SPID BIG-RAS). Of the
EUR 938 paid for 1.58 dB across that step, **EUR 773 is the rotator class step** — the reflector is
a minority of it. **The expensive step is the CLASS CHANGE, not the size.**

**2. Small dish / wide beam beats big dish / narrow beam, and the 2.4 GHz dish is the sole cause of
the class.** At 27 dBi / 2.4 GHz the ground beam is **7.3°** (pointing budget 0.73° at 10 % of
HPBW); at 15 dBi it is **29°** (2.9° budget). A second, independent cliff comes from **pointing
tolerance ∝ 1/D vs constant backlash**: a 0.5° backlash consumes the 10 % HPBW budget at
**D = 1.75 m** at 2.4 GHz (0.874 m at 1.0°), while at 433 MHz the equivalent is 4.85–9.69 m — so
the **433 dish is not pointing-limited; the 2.4 GHz dish is**. Removing the 2.4 GHz dish and
right-sizing the antenna is what deletes the positioner class (the amplifier-led analysis reaches
the same conclusion from the other direction).

**3. Beam discipline is bought with a bigger beam, not a bigger reflector.** Since both bands share
one positioner, the station's pointing need is set by the **narrowest** beam. A modest 2.4 GHz
antenna (~8–15 dBi) both satisfies the uplink (required ground gain is **negative**: −17.4 dBi at
300 km, −10.7 dBi at 650 km) and removes the precision-tracking requirement.

**4. The MESH RULE — and exactly where its edge is.** At 433 MHz the **λ/10 reflector-hole rule is
69.2 mm**, so 6–25 mm commodity welded mesh is **electrically solid** (the one vendor in this
market rates its 6 mm mesh to 6 GHz, i.e. 11.5× finer than needed at 433 MHz) **and** cuts the wind
moment to **~0.14–0.27 of a solid dish**. Against the **SPID BIG-RAS holding torque of 2,712 N·m**
(vendor spec, fetched):

| D | SOLID (× rating) | 6 mm coarse mesh (σ = 0.265) |
|---:|---:|---:|
| 1.90 m | 0.93× | 0.25× |
| **2.40 m** | **1.88× ✗** | **0.50× ✓** |
| **2.62 m** | **2.45× ✗** | **0.65× ✓** |
| 3.00 m | 3.67× ✗ | 0.97× (at the limit) |
| 3.49 m | 5.79× ✗ | 1.53× ✗ |
| 7.38 m | 54.7× ✗ | 14.5× ✗ |

**A solid 2.4 m or 2.62 m dish exceeds the strongest sourced rotator's holding torque at
120 km/h; the same dish as a coarse mesh sits at half to two-thirds of it.** The mesh is what
brings the large 433 dish back into a feasible positioner class — at **zero RF cost**. Quoted with
its edge: mesh is comfortable to **2.62 m (0.65×)**, nominally just under the line at **3.00 m
(0.97×)** with no usable margin, and over the line at **3.49 m (1.53×)** — so **≥ 3.0 m mesh
requires the slew-drive rotator class (SPID SPX-05/06, EUR 5,487) plus counterweights**.

**5. Pre-cliff vs post-cliff: the Yagi array and the dish.** For a 433 MHz high-gain station at the
balloon's own **+22 dBm** class, a **4-bay stack of commercially available 433 Yagis reaches
~20 dBi** — at or above the required **+18.9 dBi** for FLRC 2.6 Mbps at 650 km — with an effective
wind drag area of **0.454 m² (≈7 % of a 2.6 m solid dish's 6.37 m²)**, and it needs only the
**EUR 359** rotator class. On 433 gain-per-euro the 2.4–3.0 m dish rungs are **Pareto-dominated by
the array** (the dish has no more 433 gain and costs 4–5×). The dish is reserved for the
**low-power** regime, where FLRC 2.6 Mbps needs +27.9 dBi and no Yagi array reaches it.

## Decision

**D1 — Treat the rotator-class boundary at ~1.0 m² of antenna wind-load area as a DESIGN
CONSTRAINT.** Nothing may propose a ground antenna that exceeds ~1.0 m² of wind-load area without
explicitly stating that it crosses this cliff and naming the concrete capability the crossing buys.

**D2 — Prefer the SMALL antenna and the WIDE beam over the big antenna and the narrow beam.** The
station's pointing requirement is set by its narrowest beam; right-sizing the 2.4 GHz element to a
modest antenna (~8–15 dBi) is what removes the precision-tracker class. The **2.4 GHz dish is the
sole cause of the positioner class** and is removed by default.

**D3 — The pre-cliff sweet spots are the candidate operating points, not a dish rung** (costed in
ADR-081): the **most-accessible** station (one 433 Yagi + a 2.4 GHz omni on a printed tracker,
**≈ EUR 599**) is the default build and the measurement platform; the **best-bang-for-buck**
station (4-bay 433 Yagi array + 0.75 m 2.4 GHz dish, **≈ EUR 2,166**) is the performance point that
closes FLRC 2.6 Mbps **without crossing the cliff**. Two binding qualifications: size the array
against the rotator's **TOWER** rating (1.00 m², array at 45 %) — the **MAST** rating (0.50 m²)
leaves only 9 % margin and is too thin once frame, ice and cable are counted — and the pessimistic
drag case (1.104 m²) **exceeds the tower rating by ~10 % and is rejected** unless a higher-rated
support or a redesigned array is chosen.

**D4 — THE MESH RULE (standing constraint): any 433 MHz dish of 2 m or more built for this project
MUST be a coarse mesh reflector, not a solid one**, quoted with the 2.62 m / 3.00 m / 3.49 m edge
above. A solid 2.4 m+ 433 dish is mechanically infeasible on the strongest non-slew rotator in the
BOM.

**D5 — The dish is justified for ONE regime only: the low-power case** (+13…+22 dBm) where FLRC-max
needs gain no Yagi array reaches. **With the F33 (ADR-075) the required 433 ground class collapses
to a single Yagi** (0.74 m / +7.9 dBi at 650 km), so with the F33 neither the array nor the dish is
needed. This is the coherence rule between ADR-075 and this record.

**D6 — Mesh, stow + a MECHANICAL LATCH + anemometer, and balanced-axis geometry are the accepted
levers.** A counterweight is accepted for motor sizing and power-loss stability **only** — it does
**not** reduce wind torque; only balanced-axis placement does (~4×).

**D7 — Run the measurement campaign BEFORE any dish/rotator purchase.** A Tier-A Yagi station flies
the low-power LR2021 and measures the two currently **assumed** numbers — the **433 MHz FLRC
sensitivity** (today a 915 MHz datasheet proxy) and the **path-loss exponent n** (today assumed
2.0) — plus the residual margin at the flown range.

## Invariants

- **INV-1.** Any ground antenna exceeding ~1.0 m² of wind-load area must state that it crosses the
  cliff and name the capability bought.
- **INV-2.** Any 433 dish ≥ 2 m is **coarse mesh**.
- **INV-3.** The 2.4 GHz uplink antenna is not bought for gain above ~8 dBi (the EIRP-cap invariant)
  — a dish on that band is justified on interference/polarisation grounds only.
- **INV-4.** A **433** dish is never justified on pointing (it is not pointing-limited); it is
  justified on closure only in the low-power regime.
- **INV-5.** No rotator purchase before the measurement campaign (D7) reports.

## Consequences

### Positive
- The antenna decision is made on a **measured** link at a known range instead of a worst-case
  model, and the high-gain station is reachable at ~7 % of the wind drag area and ~7.6 % of the
  modelled wind moment of a 2.6 m dish.
- The cliff stops being an implicit trap and becomes a stated, quotable constraint.
- Right-sizing the 2.4 GHz element removes a whole class of tracker cost.

### Costs / risks
- **The array's advantage evaporates at +13 dBm / 2.6 Mbps**, where the dish is required (D5).
- A **linearly polarised** array is **not** robust to a tumbling balloon the way a circularly
  polarised dish feed is — the strongest genuine argument for a dish.
- The array's drag estimate is **dominated by its mounting frame** (0.252 of 0.454 m²).
- **The array is a SCREENING result, not a validated design**, until these close: the full
  gust/moment/structural load case; the array harness loss and the component-level frame Cd·A; the
  unmeasured 433 FLRC sensitivity; and the Yaesu G-450CDC's allowable moment (not published).

### Adjudicated conflict with ADR-079's sibling analysis
The off-branch `070-ground-station-amplifier-hypothesis` (§D4) **rejects a Yagi array** as
€76–94/needed dB, a narrower beam and a doubled wind moment. Both are right in their own frame and
**neither is deleted here**:
- *Relative to the F33* (0.40 USD/dB) **any** ground gain, array included, is bad value — that is
  ADR-075's ledger, and it holds.
- *Relative to the dish* the pre-cliff array beats the post-cliff dish on gain-per-euro and wind —
  that is this record's D3.
**Resolution (this record wins for the antenna class):** with the F33 locked (ADR-075), **neither
the array nor the dish is required** — a single Yagi closes the link (ADR-081 option B). The array
is retained only as the **no-F33 pre-cliff** answer, and the dish only as the **low-power** answer.

## Open items (not assumed)

- **`TODO(unverified)`** a **433 MHz prime-focus dish feed** (the vendor's feed range begins at
  900 MHz).
- **`TODO(unverified)`** the **rib/former set** for a >1.9 m DIY mesh dish (no vendor sells ribs
  without mesh; the ≥2.4 m kits are out of stock).
- **`TODO(unverified)`** the mesh wire diameter and the wind-drag exponent / rib-area allowance.
- **`TODO(unverified)`** a **measured** mesh-vs-solid reflector gain penalty in dB.
- **`TODO(unverified)`** the Yaesu G-450CDC allowable moment (a wind-load *area* is published, not
  a moment).
- **Flagged defect:** **SPX-06 is EUR 5,487 with a 716 N·m published rating while BIG-RAS is
  EUR 1,775 with a 2,712 N·m brake** — price and rating orderings disagree because the bases differ
  (slew rating vs brake). A contradiction that names no winner is a defect; not resolved here.

## Relation to other ADRs

- **Supersedes** the off-branch `068-ground-station-antenna-class-cliff`
  (`design/gain-per-dollar-cliff`) — its decision lands here and its sweet spots in ADR-081.
- **Supersedes** the Yagi-before-dish half of the off-branch `068-ground-station-gain-per-dollar`
  (`design/gain-per-dollar`) and its Yagi-array/right-sizing material.
- **Supersedes** the mesh rule and the "recommended 1.2–1.9 m coarse-mesh dish" sizing of the
  off-branch `067-flrc-max-433-tx-power-and-coarse-mesh` — the mesh rule is retained here; the dish
  recommendation is **conditional** on the low-power regime only (D5, per ADR-075).
- **Adjudicates** the array-vs-no-array conflict with the off-branch
  `070-ground-station-amplifier-hypothesis` §D4 (see Consequences).

## For future sessions

- **One-line rule:** **right-size the antenna and prefer the wide beam**; the cliff is the
  **rotator class (~1.0 m² wind area)**, not the reflector size; **any 433 dish ≥ 2 m is coarse
  mesh**; and **with the F33 a single Yagi closes the link** — no array, no dish.
- **Reproduce:** `python3 docs/analysis/gain_per_dollar_cliff_model.py`; the mesh table comes from
  `python3 docs/analysis/ground_station_flrc_max_model.py`.
- **Do not re-derive:** the scaling exponents (wind force D²·⁰⁰⁰, moment D³·⁰⁰⁰, mass D¹·⁸⁰ — log-log
  R²=1.000) or the 2,712 N·m BIG-RAS brake.
