# Status of the interface drawing in this directory

**`edge-launch-cross-section.svg` / `.png` depict the COMMITTED hub-side interface geometry.** They are a
review sheet, not yet a fabrication release — but the reason is *not* that the interface is undecided.

## Current status (corrected 2026-10-17)

| | |
|---|---|
| **Geometry depicted** | **Option A** — a routed slot **0.9 × 6.0 mm** in the hub edge, the **0.6 mm tab seated 6.0 mm** into it, the four **4.0 × 1.2 mm** lands on the slot's faces, the fillet loaded in **SHEAR**. This is the **COMMITTED** geometry (`ADR-048 §2.2`; `ADR-046 §4.2.2`: *"Option A is the committed geometry"*). |
| **Board as built** | **Option B** — **no slot**, `J_W*` lands on `F.Cu` only, fillet in **peel**. Measured with `tracker/hardware/introspect_edge_interface.py`. **The board change is PENDING.** |
| **Slot-face land construction** | **UNVERIFIED — under query.** Asked of JLCPCB as **Q6** on the sheet and as **section 2A** of `docs/fab/JLC-QUERY-DRAFT-MESSAGE.md` (PR #215). No construction, process or finish is asserted. |
| **Mating fit** | **UNVERIFIED — under query.** Finished tab thickness, slot width/depth tolerances, finished solder clearances, slot-end radius and tab-tip relief are **design decisions no record fixes** (Q3/Q7). |
| **May it be sent to a fabricator?** | **Not yet** — see *"What still has to happen"* below. The blocking reasons are the three §4.2.2 items, not an undecided interface. |

## What changed in this file, and why (record kept)

**The previous version of this file said:**

> *"`edge-launch-cross-section.svg` / `.png` were generated but must NOT be sent to a fabricator yet."*

> *"The drawing depicts the hub-side wing interface. That geometry is **undecided**"* — citing
> `ADR-046 §4.2.1`'s **OPEN** status.

**That claim was stale.** `ADR-046 §4.2.1` (added 2026-10-16) marked the interface OPEN; **`ADR-046 §4.2.2`
(added the same day, after merging master) explicitly supersedes it on the direction**, because **ADR-048
is a LATER record that decides the question** — *"Option A is the committed geometry"*. The drawing was
also regenerated in the meantime (v3) and now **draws the ADR-048 committed geometry and says on the sheet
that the board as built is still Option B**. The old text described v1/v2 of the drawing, not this one.

**What survives from §4.2.1 — and is NOT undone by the correction:** §4.2's *stated reason* for Option A
(the slot "keys the 90° angle") remains falsified — 0.30 mm of play over a 6.0 mm insertion is **2.86°**,
i.e. **8.79 mm** of wing-tip movement at 176 mm, against 9.21 mm freehand. **ADR-048 does not repeat that
claim**, so it is a correction to ADR-046 that stands. The sheet states this on its *"Alignment caveat"*
row. The slot **bounds** the attach angle; it does not **key** it.

## What the drawing is now

Two sections, `View A` (along the insertion axis) and `View B` (across the tab), plus a requirement and
question table. It was taken through **four visual-review cycles (r1–r4) and a further four (r5–r8)**;
the r5–r8 record and the disposition of every r4 defect is in `docs/fab/EDGE-DRAWING-STATUS.md`.

The sheet states, on its face, that it depicts the committed geometry and must not be read as the built
state. It is **deliberately caveated**: `±0.10 mm` slot tolerance is PROPOSED, the slot-face land
construction is UNVERIFIED, and the mating fit is UNVERIFIED — each with the question it maps to.

## What still has to happen before it is sent

1. **The three `ADR-046 §4.2.2` items**: the wing-side land geometry (**W1**), a **peel figure** for this
   joint geometry, and the **JLCPCB routed-cut-out cost delta** from a live quote.
2. **The two open questions on the sheet**: the slot-face land construction (**Q6**) and the mating-fit
   spec (**Q7**, plus the slot tolerance **Q3**). These are *asked*, not answered — nothing is invented.

**Trade study:** `tracker/hardware/trade_study_wing_joint.py`
(output committed as `docs/fab/WING-JOINT-TRADE-STUDY.txt`).
