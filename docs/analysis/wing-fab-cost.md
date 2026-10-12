# Wing fabrication, hand-assembly and order-cost analysis

**STATUS: CONSULTANT ANALYSIS — not a decision record.** This document is a reasoned
manufacturability / hand-assembly / order-cost analysis with numbers and a recommendation.
It is **not** an ADR, carries **no** operator decision, and every figure below is either
marked `LIVE` (read from a live JLCPCB page on 2026-10-07), `COMPUTED` (derived here with the
formula shown) or `TODO(unverified)` / `ESTIMATE` (explicitly not verified — never present a
remembered price as verified).

- Date: 2026-10-07
- Branch: `analysis/wing-fab-cost`
- Base commit: `76dd04d` (the tip of `github/main`; the local `main` in the primary checkout is
  at `8fa2202` — this branch is cut from `github/main` as instructed)
- Lens: **manufacturability, hand-assembly effort, order cost.**
- Established facts treated as given (cited, not re-derived): one hub + **four identical wings**
  soldered at 90°; the operator **hand-solders every module and every joint**; boards are
  fabricated by **JLCPCB**; small cell **52.07 × 19.65 mm, one pad on the FRONT face and one on
  the BACK face**; large cell **78.55 × 38.90 mm, pad layout unconfirmed**; ≈100 small panels
  in hand, large count unknown; the wing as it stands is **176 × 25 mm + 8 × 9 mm tab, 2-layer,
  B_Cu EMPTY, one 1.6 × 4.0 mm land per cell, order-gate PASS with 23 cosmetic DRC warnings,
  and is KNOWN WRONG for one-pad-per-face cells**; the wing interface is a **4-pin tab,
  9.0 mm wide, a 0.9 × 6.0 mm Edge.Cuts slot in the hub** (ADR-046 / ADR-048), the hub owns the
  series chain and each wing carries a DNP bypass Schottky.

---

## 0. Top-line

1. **Joint count is the primary risk metric on this vehicle.** The vehicle is hand-built: every
   joint is made by a human, and every joint is an independent opportunity for a cold joint, a
   bridge or a lifted pad. The cell count, not the cell size, sets the joint count — so the
   biggest single lever on build risk is *how many cells per wing*.
2. **Three series cells per wing is the minimum-joint option (9 cell joints/wing, 36/aircraft).**
   Both the 3-large and the 3-small builds hit 9/wing; the 9-small parallel build is **3×**
   that (27/wing) and the 12-small build is **4×** (36/wing).
3. **A one-pad-per-face cell costs 3 hand joints per cell (not 2)** unless the board is cut to
   present a wrap-around land or the cell arrives pre-tabbed. **A via cannot substitute for a
   jumper** — the far pad is on the cell, not the board.
4. **The 0.9 mm hub slot in ADR-046 is below JLCPCB's published minimum for a non-plated slot
   (1.0 mm)** and its worst-case gap against a 0.6 mm tab is **0.00 mm** (LIVE tolerances) ⇒ the
   tab may not insert at all. This is a hub-side blocker, not a wing-side one.
5. **Live price for the exact wing board: 2-layer, 25 × 184 mm, qty 5 = $6.40; the same board
   at 4 layers = $28.00** (a ×4.4 / +$21.60 step). Two distinct designs cost a *few dollars* more
   in engineering, not hundreds.
6. **Recommendation:** order **hub + ONE small-cell wing** first, once the cell pad geometry is
   measured; keep the large-cell wing as a **second dedicated design** (not a "universal" board).
   See §4.

---

## 1. JOINT COUNT

### 1.1 What one cell costs in hand joints

A cell has **one pad on the FRONT face and one on the BACK face** (given). It therefore presents
**two electrical terminations**, and both must reach board copper:

| Termination | Placement | Hand joints | Why |
|---|---|---|---|
| Pad facing the board | against a board land | **1** | direct solder, land-to-pad |
| Pad facing away from the board | pointing away | **2** if soldered via a **jumper** (one joint at the cell pad, one at the board land) | the pad is not in contact with any board copper |
| Pad facing away, board has an **edge wrap** land | the wrapping land is a *fab* feature, not a joint | **1** (pad-to-wrap) | total 2 joints/cell |
| **via** instead of a jumper | — | **does not work** | a via connects *board layers*; the pad is on the *cell*, so a via removes no joint — you still need a jumper, so 3 joints **and** a wasted via |
| cell shipped **pre-tabbed** (supplier welds the ribbon on) | ribbon already on the far pad | **1** at the board | total 2 joints/cell |

**Baseline used below: 3 hand joints per cell** (one direct + a two-end jumper), which is the
realistic case for a flat-mounted one-pad-per-face cell on a plain 2-layer wing. The **2-joint**
case (edge-wrap land or a pre-tabbed cell) is given as a parallel column.

`COMPUTED` per cell: 2 terminations; 1 is a direct joint; the off-face termination costs 2
(jumper) or 1 (edge wrap / pre-tab). ⇒ **3 joints/cell (jumper) · 2 joints/cell (wrap/tab).**

To this, every wing adds its **wing→hub tab: 4 pads soldered on both faces = 8 joints/wing**
(ADR-046 §4.1, "the wing tab inserts 6 mm into the slot and is soldered on both faces").
The DNP bypass Schottky adds **0** joints in the first prototype (DNP).

`TODO(unverified)`: whether the operator solders the tab on one face (4 joints) or both (8);
this document uses **8** and states the assumption.

### 1.2 Electrical count for the parallel case (c)

`COMPUTED` from the given requirement: **≈1.2 A per series position ÷ ≈0.4 A per small cell =
3 small cells in parallel per series position.** With 3 series positions (3 × 0.5 V ≈ 1.5 V per
wing, ADR-006):

- **9 small cells/wing** = 3 series × **3** parallel → 1.2 A/position.
- **12 small cells/wing** = 3 series × **4** parallel → 1.6 A/position (a 33 % current margin).

### 1.3 Joint count per option

`COMPUTED` (joints/cell = 3; tab = 8/wing; aircraft = 4 wings). Ranked by total joints.

| Rank | Wing build | Cells/wing | J/wing (cells) | J/wing incl. tab | J/aircraft (cells) | J/aircraft incl. tab | Edge-wrap variant J/aircraft |
|---|---|---|---|---|---|---|---|
| 1 | **(b) 3 SMALL in series** | 3 | **9** | 17 | **36** | 68 | 56 |
| 1= | **(a) 3 LARGE in series** | 3 | **9** | 17 | **36** | 68 | 56 |
| 1= | **(d1) mixed 1 LARGE + 2 SMALL** | 3 | **9** | 17 | **36** | 68 | 56 |
| 4 | (d2) mixed 1 LARGE + 6 SMALL | 7 | 21 | 29 | 84 | 116 | 88 |
| 5 | **(c9) 9 SMALL (3 s × 3 p)** | 9 | 27 | 35 | **108** | 140 | 104 |
| 6 | **(c12) 12 SMALL (3 s × 4 p)** | 12 | 36 | 44 | **144** | 176 | 128 |

`COMPUTED` ratio: (c9) is **3.0×** and (c12) is **4.0×** the joint count of the 3-in-series
builds, because the only term that changes is the cell count.

**Statement of the metric:** on a hand-built vehicle the **joint count is the primary risk
metric** — it multiplies the cold-joint / bridge / lifted-pad probability, it multiplies operator
hours, and it is the number that a wrong land pattern multiplies *again*. A build that triples
the joints triples the rework surface. The cheapest risk reduction available is to carry **three
cells per wing**, not nine or twelve.

### 1.4 Layout consequence (why (a), (c9), (c12) do not fit the current wing)

`COMPUTED` against the current **176 × 25 mm** body (cells 52.07 × 19.65 small, 78.55 × 38.90 large):

| Build | Series length | Width across | Fits 176 mm length? | Fits 25 mm width? |
|---|---|---|---|---|
| (a) 3 LARGE in series | 3 × 78.55 = **235.65 mm** | 38.90 mm | **No** | **No** |
| (b) 3 SMALL in series | 3 × 52.07 = **156.21 mm** | 19.65 mm | Yes | Yes |
| (c9) 9 SMALL (3 s × 3 p) | 156.21 mm | 3 × 19.65 = **58.95 mm** | Yes | **No** |
| (c12) 12 SMALL (3 s × 4 p) | 156.21 mm | 4 × 19.65 = **78.60 mm** | Yes | **No** |

- (b) fits the current outline as-is. Cell area 3 069 mm² vs 4 400 mm² wing area — comfortable.
- (a) needs **≈236 × 39 mm** (plus margins) — a *different wing* (and a much wider wing on a
  22 mm hub edge). 236 mm is inside JLCPCB's max (LIVE: 670 × 600 mm, §2).
- (c9) needs **≈160 × 66 mm** and (c12) **≈165 × 85 mm** (cell area 9 209 / 12 278 mm² vs the
  current 4 400 mm² ⇒ ≈2.1× / 2.8× the board area).

So the parallel builds are not "more cells on the same wing" — they are **a new, wider wing**,
which re-opens the hub mechanical interface. That is an additional reason to prefer 3-in-series.

---

## 2. FAB CONSTRAINTS AT JLCPCB

Provenance key: **LIVE** = read off a live JLCPCB page on 2026-10-07 (URLs given) ·
**COMPUTED** = derived here with the formula shown · **ESTIMATE** / **TODO(unverified)** = not verified.

### 2.1 LIVE — capabilities (https://jlcpcb.com/capabilities/pcb-capabilities)

| Item | LIVE value | Relevance |
|---|---|---|
| Layer count | 1–32 | 2-layer wing and (if the hub is 4-layer) coexist in one order |
| **Minimum Dimensions** | FR4/Rogers/PTFE **3 × 3 mm**; limits apply to thickness ≥ 0.6 mm | the 176–250 mm wing and the 22 mm hub are far above the minimum |
| Maximum Dimensions | FR4 2-layer **670 × 600 mm**; 4-layer 663 × 593 mm; **thinner FR4 (< 0.8 mm) 599 × 497 mm** | **a 250 mm wing is deep inside the envelope** — a length question is a *price class*, not a feasibility question |
| Thickness | 0.4–4.5 mm; FR4 options 0.4 / **0.6** / 0.8 / 1.0 / 1.2 / 1.6 / 2.0 mm | the wing's 0.6 mm is an offered option |
| **Min. Non-Plated Slots** | **1.0 mm** (draw in GM1/GKO) | **ADR-046's 0.9 mm slot is BELOW this minimum** ⇒ not orderable as a standard NPTH slot |
| Min. Plated Slots Width | 2-layer 0.5 mm / multilayer 0.35 mm; length ≥ 2 × width | a 0.9 mm *plated* slot is inside the minimum (but plating is copper — see §2.3) |
| Slot Hole size Tolerance | plated **+0.13 / −0.08 mm**; non-plated **±0.2 mm** | drives the tolerance stack in §2.3 |
| Routed | copper clearance from routed slots ≥ 0.2 mm; routed-edge tolerance ±0.2 (regular) / ±0.1 (precision); precision needs min dim 50 × 50 mm and ≥ 3 tooling holes ≥ 1.5 mm | the wing tab pads must clear the slot edge by ≥ 0.2 mm |
| Rectangular holes / slots | **NOT supported** without rounded corners | a slot must be drawn with rounded ends |
| Min. track width / spacing (1 oz) | 0.10 / 0.10 mm | the wing's nets are coarse; not a constraint |
| Min. Non-plated holes | 0.50 mm | the wing's handling holes must be ≥ 0.5 mm |

### 2.2 LIVE — the pricing STRUCTURE and a real quote for the actual wing

Read live from the quote page `https://cart.jlcpcb.com/quote` by uploading
`tracker/hardware/output/gerbers_wing_v9_jlcpcb.zip` (the repo's real wing gerber). The page
reported: **"Detected 2 layer board of 25x184mm(0.984x7.244 inches)."**

The pricing structure the page renders is **`Calculated Price`** (a labelled figure, not "PCB
Price") plus **`Shipping Estimate`**, built from named charge lines:

| Charge line (LIVE, as rendered) | 2-layer, qty 5 | 4-layer, qty 5 |
|---|---|---|
| Engineering fee | **$4.00** | **$25.00** |
| Board | **$2.30** | **$2.90** |
| Deburring / Edge rounding | $0.10 | $0.10 |
| Via Covering | $0.00 | $0.00 |
| Surface Finish | $0.00 | $0.00 |
| PCB Build Time (2 days) | $0.00 | $0.00 |
| **`Calculated Price`** | **$6.40** | **$28.00** |

- **LIVE 2-layer → 4-layer cost step: $6.40 → $28.00 = +$21.60 (×4.375)** on the identical wing,
  qty 5. The step lives almost entirely in the **Engineering fee ($4.00 → $25.00)**.
- **LIVE option set on the page:** Layers **1 / 2 / 4**; PCB Qty presets 5 … 50 000; PCB Thickness
  0.4 / 0.6 / 0.8 / 1.0 / 1.2 / 1.6 / 2.0 mm; **"Different Design: 1 2 3 4"** (so the *number of
  distinct designs on one order is a first-class, price-relevant input*); Delivery Format
  Single PCB / Panel by Customer / Panel by JLCPCB; Surface Finish default **OSP** (HASL-with-lead /
  LeadFree HASL / ENIG available).
- **LIVE thickness 0.6 mm:** toggling PCB Thickness to 0.6 mm left the Board and Engineering lines
  unchanged ⇒ **0.6 mm is a $0.00 delta** on this board (observed with an unrelated leftover
  Via-Covering line, but the Board/Engineering lines were identical).
- **LIVE shipping:** the page renders a **`Shipping Estimate`** section; the visible carrier was
  **DHL Express (DDP), 2–4 business days**, weight **0.20 kg** for qty 5. A shipping figure of
  **$31.23** was observed in one larger-order state — it is **indicative**, not isolated (see §2.4).
- **LIVE:** no line item named for length, narrowness or a "long board surcharge" appeared on any
  observed state. The only size-sensitive line is **Board** ($2.30 at qty 5 for 25 × 184 mm).

### 2.3 COMPUTED — the 0.9 mm slot vs a 0.6 mm tab (this is a blocker)

Using the **LIVE** tolerances (non-plated slot ±0.2 mm; board thickness ±0.1 mm below 1.0 mm) and
the ADR's numbers (slot 0.9 mm, tab 0.6 mm):

`COMPUTED`
- **Non-plated 0.9 mm slot:** nominal gap = 0.9 − 0.6 = **0.30 mm**;
  worst case (min slot − max tab) = 0.70 − 0.70 = **0.00 mm**; best case = 1.10 − 0.50 = **0.60 mm**.
  ⇒ the joint gap can reach **zero** — the tab may not insert at all, and the ADR's assumed
  ±0.10 mm slot tolerance is **tighter than JLCPCB's ±0.2 mm capability**.
- **Plated 0.9 mm slot (+0.13/−0.08):** gap = **0.12 … 0.53 mm** (always positive) — fits, **but**
  a plated slot is a copper-lined barrel that would electrically connect the four `W<n>_*` lands
  around the tab ⇒ **electrically wrong** for this interface.
- **Non-plated 1.0 mm slot** (the LIVE standard minimum): nominal gap 0.40 mm, worst case
  **0.10 mm**, best case 0.70 mm ⇒ correctable, but at 0.10 mm worst case a **0.6 mm tab is at the
  edge of the filler's reach**.
**Conclusion:** the 0.9 mm slot should be re-specified to **≥ 1.0 mm non-plated** (or the interface
falls back to ADR-046's Option B, plain pads, no slot). Either way the hub must be re-plotted —
this is a **hub-side** change, not a wing change.

### 2.4 ESTIMATE / TODO(unverified) — what is NOT verified

- `ESTIMATE` — **the Board fee for a 250 mm outline was not quoted live.** The live 184 mm wing is
  $2.30 (Board, qty 5, 2-layer). A longer board is plausibly a higher size class in the same
  "Board" line, but **no 250 mm gerber was uploaded and no 250 mm figure was observed.**
  `TODO(unverified)`: the actual 250 mm Board fee.
- `TODO(unverified)` — whether a 250 mm board **triggers a manual-review flag** (the capabilities
  page flags manual review only for **thickness < 0.6 mm**, not for length; length was not tested).
- `TODO(unverified)` — the shipping figure **$31.23** comes from an observed but **un-isolated**
  option state; DHL Express (DDP) 2–4 days and the 0.20 kg weight are the parts that were cleanly read.
- `TODO(unverified)` — the **hub** quote: **no v9 hub PCB exists** (confirmed: only `hub_board_v1*`,
  `hub_board_diy`, `hub_board_f33` exist on the branch), so the hub's layer count, thickness and
  price are unknown and cannot be quoted.
- `TODO(unverified)` — the **4-layer wing** figure ($28.00) is real, but the *same* option state
  showed a leftover **Via Covering $16.58** when reverted to 2 layers ($22.98). The clean figure is
  the **baseline $6.40** and the **4-layer $28.00**; the $22.98 / $256.10 / $289.18 states were
  observed with **un-isolated option sets** and are **indicative only** (e.g. selecting "Different
  Design = 2" added a `Panel $33.08` line). They are recorded here rather than presented as quotes,
  exactly because a quote is only valid with the options it was taken under.

---

## 3. ORDER SHAPE

Common to all: the wings must ride the **same JLCPCB order as the v9 hub** (operator intent).
`LIVE` fact that governs this: the order page carries a **"Different Design: 1 2 3 4"** input —
the number of distinct designs on the order is an explicit, price-relevant field.

| Order shape | Distinct designs | Sensible prototype qty | Does panelising the wing help? | Risk from ordering before the cell pads are measured |
|---|---|---|---|---|
| **(a) hub + ONE universal wing** | **2** | hub 5 + wing 5 (1 flight set + 1 spare), or 10 + 10 for two sets | Marginal. The wing is 176–184 mm long; at 5–10 pcs the panel saving does not cover the extra depanel burr/tolerance on the cell mounting face. | **HIGH** — one land must be right for *both* cell sizes; a wrong land wastes the whole wing order. |
| **(b) hub + TWO wings (small + large)** | **3** | hub 5 + small 5 + large 5 | No — different outlines cannot be panelised together economically. | **HIGHEST** — *two* unmeasured land patterns, and the large land is explicitly "unconfirmed" (given). Two independent chances to re-spin. |
| **(c) hub + ONE small-only wing** | **2** | hub 5 + wing 5 (10 if two sets) | Marginal at prototype qty; the wing (156 mm cell run) is one of the two shortest parts and can be panelised 2-up if qty rises. | **MEDIUM** — still unmeasured, but it is **the same outline that already exists**, the ≈100 small cells are in hand, and there is only **one** geometry to get right. |
| **(d) hub + ONE large-only wing** | **2** | hub 5 + wing 5 | No (a ≈236 × 39 mm part is already large). | **HIGH** — the large-cell pad layout is unconfirmed **and** the ≥236 × 39 mm wing changes the hub mechanical interface ⇒ re-freeze risk on the hub too. |

`LIVE` cost context for "designs": the 2-layer Engineering fee is **$4.00 per design** (measured),
so a second 2-layer wing design adds about **+$4.00** plus an order-level multi-design charge
(observed as a `Panel` line, **indicative**). At prototype quantities the **fab premium for a second
design is single-digit-to-low-tens of dollars**, which is small next to a re-spin.

---

## 4. THE UNIVERSAL-BOARD QUESTION, FROM THIS LENS

*Does ONE wing design that can carry either cell size cost more or less than two dedicated designs,
once hand-assembly effort and the risk of a wrong land are included?*

**It costs more. Recommendation: two dedicated designs (and for the first order, one small-only
design).**

| Consideration | ONE universal wing | TWO dedicated wings |
|---|---|---|
| Fab cost | 1 wing Engineering fee (**LIVE $4.00** 2-layer) | 2 Engineering fees (**+≈$4.00**) + multi-design charge (**indicative**) |
| Board area / land count | needs **dual or oversized lands** for both cells ⇒ more copper, larger board, more places to bridge | each land is matched to exactly one cell |
| Hand joints per wing | unchanged — joints are set by **cells used**, not the board (3 joints/cell) | unchanged |
| Wrong-land risk | **one** design that must be right for **two** geometries; an oversized "compromise" land that is right for neither is a solder-bridge generator on the small cell and a mis-alignment on the large | **two** independent land patterns, each correctable on its own; a wrong one costs only its own re-spin |
| Amendability | a wrong land re-spins **both** cell builds | a wrong land re-spins **one** cell build |

The universal board buys **≈$4 (single digit)** of fab engineering and pays for it in **bigger,
more crowded copper** and in the **worst failure mode on this project** (a land that fits neither
cell). **Two dedicated designs is the better value.** For the *first* order specifically, only one
cell size is actually in hand in quantity (≈100 small), so the right first move is **one dedicated
small-cell wing**, not a universal board and not a two-design gamble.

**Top-line recommendation:** order **hub + ONE small-cell wing**, and only after the small cell's
real pad geometry is measured. Keep the **large-cell wing as a separate, second design** for when
the large cells are in hand and measured. Do **not** order a "universal" wing.

---

## 5. PRE-ORDER CHECKLIST (⚠ = IRREVERSIBLE if wrong)

| # | Item to measure / decide | Owner | Irreversible? | Why it matters |
|---|---|---|---|---|
| 1 | The small cell's real **solder contact geometry** — contact width, position, whether a tab/ribbon is pre-welded | operator | ⚠ **IRREVERSIBLE** | the land is etched in copper; the ADR's 1.6 × 4.0 mm is a *routing-constrained* land, not a measured one (ADR-046 §3.4), and the current wing is already KNOWN WRONG for one-pad-per-face cells |
| 2 | The **joint scheme per cell** — direct+jumper (3 joints) vs edge-wrap / pre-tabbed (2 joints) | operator + layout | ⚠ **IRREVERSIBLE** | decides whether the board needs a wrap land or a window; the copper decides it |
| 3 | The **large cell pad layout** (explicitly unconfirmed) — only if a large wing is in scope | operator | ⚠ **IRREVERSIBLE** (for that board) | the large wing cannot be drawn without it |
| 4 | Which **cell size(s)** the first order carries, and the wing **outline(s)** | operator | ⚠ **IRREVERSIBLE** | Edge.Cuts and the hub interface are etched |
| 5 | The **hub slot spec** — must be ≥ 1.0 mm if non-plated (0.9 mm is below JLCPCB's minimum); plated vs non-plated | operator + hub layout | ⚠ **IRREVERSIBLE** (hub) | a 0.9 mm NPTH slot is not orderable; its worst-case gap is 0.00 mm (§2.3) |
| 6 | Wing **substrate thickness** (0.6 mm is orderable but is the thinnest standard FR4 and the tolerance edge) | operator | ⚠ effectively irreversible per revision | sets the tab/slot fit and the handling stiffness |
| 7 | **Hub layer count (2 vs 4)** | operator + hub layout | ⚠ per order | **LIVE**: the 2L→4L step on the wing is $6.40 → $28.00; also decides whether hub+wing can share a panel |
| 8 | Number of **distinct designs** on the order (the live "Different Design 1/2/3/4" input) and **quantities** | operator | No (pre-submit) | price-relevant; and it is what makes "two dedicated wings" a few dollars, not hundreds |
| 9 | Resolve the **bypass-Schottky location conflict**: ADR-046 §2.3 puts the DNP bypass **on the hub**; the task brief says **each wing carries** it | records owner | No (DNP) | a documentation conflict that must be closed before either board is plotted |
| 10 | Resolve the **ADR-046 land-size inconsistency**: §0.3 table says 1.6 × **14.0** mm; §3.4 says 1.6 × **4.0** mm | records owner | No, but blocks #1 | the land size is the part that must match the cell |
| 11 | Re-run the **DRC / order gate on the exact board+fab pair** before ordering | agent | No | the current wing's gate PASS (0 errors / 0 unconnected / 23 cosmetic warnings) is real but the board is known wrong; a PASS does not make it orderable |
| 12 | Decide whether the first prototype is **one flight set or two** (5 vs 10 wings) | operator | No | doubles the order |

---

## 6. Comparison table (single view)

| Build | Cells/wing | Cells/aircraft | J/wing (cells) | J/aircraft (cells) | J/aircraft incl. tab | Fits current 176 × 25 wing? | Needs new wing outline? |
|---|---|---|---|---|---|---|---|
| (b) 3 SMALL series | 3 | 12 | **9** | **36** | 68 | **Yes** | No |
| (a) 3 LARGE series | 3 | 12 | **9** | **36** | 68 | No (needs ≈236 × 39) | Yes (+ hub interface) |
| (d1) mixed 1L + 2S | 3 | 12 | **9** | **36** | 68 | No (large width) | Yes |
| (d2) mixed 1L + 6S | 7 | 28 | 21 | 84 | 116 | No | Yes |
| (c9) 9 SMALL (3 s × 3 p) | 9 | 36 | 27 | **108** | 140 | No (needs ≈160 × 66) | Yes (+ hub interface) |
| (c12) 12 SMALL (3 s × 4 p) | 12 | 48 | 36 | **144** | 176 | No (needs ≈165 × 85) | Yes (+ hub interface) |

Mixed-series caveat: a mixed string (large + small in one series string) is electrically unsound —
the string current is set by the weakest cell and the cell voltages differ (0.5 V small vs ≈0.54 V
large per `docs/component-guide.md` line 108) — so a mixed wing is only sane if the mixing is
**across parallel positions**, which raises the cell count and therefore the joint count.

---

## 7. Evidence actually observed (no claim beyond it)

| Fact | Source | Kind |
|---|---|---|
| Minimum dimension FR4 3 × 3 mm; max 2-layer 670 × 600 mm; min NPTH slot 1.0 mm; min plated slot 2-layer 0.5 mm; slot tolerance NPTH ±0.2 / plated +0.13−0.08 mm; thickness list incl. 0.6 mm; routed slot copper clearance ≥ 0.2 mm; rectangular slots need rounded corners | `https://jlcpcb.com/capabilities/pcb-capabilities`, fetched live 2026-10-07 | **LIVE** |
| Wing gerber detected as "2 layer board of 25x184mm"; qty 5, 2-layer **Calculated Price $6.40** = Engineering $4.00 + Board $2.30 + Deburring $0.10; qty 5, 4-layer **$28.00** = Engineering $25.00 + Board $2.90 + Deburring $0.10; layers 1/2/4; thickness 0.6 mm = $0.00 delta; "Different Design 1 2 3 4"; Delivery Format Single/Panel; weight 0.20 kg; shipping = DHL Express (DDP) 2–4 days | `https://cart.jlcpcb.com/quote` driven with `tracker/hardware/output/gerbers_wing_v9_jlcpcb.zip`, live 2026-10-07 | **LIVE** |
| 3 large in series = 235.65 mm, does not fit 176 mm; 3 small = 156.21 mm, fits; 9 small needs 58.95 mm width; 12 small needs 78.60 mm width | arithmetic on given cell dimensions | **COMPUTED** |
| 0.9 mm NPTH slot vs 0.6 mm tab: nominal gap 0.30 mm, worst case **0.00 mm** | arithmetic on LIVE tolerances | **COMPUTED** |
| Wing board gate: `pcb_order_gate` **PASS**, errors 0, unconnected 0, warnings 23 (12 lib_footprint_issues, 6 silk_edge_clearance, 2 silk_overlap, 2 text_height, 1 silk_over_copper), board sha256 `8448d76b...3682c`, fab sha256 `90cb2480...9477` | `tracker/hardware/wing_board/wing_v9-GATE-RECORD.json` in this worktree | observed (committed record) |
| No v9 hub PCB exists on this branch | `find` over `*.kicad_pcb` | observed |

---

*CONSULTANT ANALYSIS — not a decision record. Nothing here is an operator decision, and no figure
marked `TODO(unverified)` or `ESTIMATE` may be treated as verified.*
