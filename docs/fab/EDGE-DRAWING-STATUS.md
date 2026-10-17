# Edge-launch cross-section drawing — status after the r5–r8 review loop

Generator: `tracker/hardware/make_edge_section.py`
Artefacts: `docs/fab/jlc-query/edge-launch-cross-section.svg` / `.png`
Reviews: `docs/fab/reviews/edge-launch-r5.md` … `edge-launch-r8.md` (r1–r4 are the previous worker's)

## Outcome

- **Cycles run: 4** (r5, r6, r7, r8) — the bound set by the task. **Not CLEAN.**
- **Final verdict, r8, verbatim:**

  > `VERDICT: DEFECTS_PRESENT 2`

  with actionable defects (verbatim):
  > 1. **Define the internal slot-face land construction.** In Q6 and "Land construction — UNVERIFIED,"
  >    replace the unresolved construction with an approved detail showing how each of the four isolated
  >    copper lands on each slot face is produced, its thickness, and its connection to the corresponding
  >    board net. Include the applicable surface finish.
  > 2. **Complete the mating-fit specification.** Resolve "Mating fit — UNVERIFIED," Q3, and Q7 by
  >    specifying the finished tab thickness, slot width and depth tolerances, slot-end radius, tab-tip
  >    relief, and required solder clearances. Verify that the tolerance extremes permit the stated 6.0 mm
  >    insertion, then add those requirements to the drawing.

- **Both remaining defects are the two items that are EXPLICITLY OUT OF SCOPE.** They cannot be closed
  without inventing a construction, a process or a dimension, which the task forbids. They are
  **ACCEPTED-WITH-WAIVER**.

## Disposition of the five r4 defects

| r4 defect | Disposition |
|---|---|
| **(3) Short-circuit** — continuous tab-face copper in View B would connect `W1_SOLAR_P`, `GND`, `W1_RF`, `W1_SOLAR_N` | **FIXED (r5).** The copper is now **four separate conductors per face**, one per land, with bare substrate drawn in the 0.6 mm gap between them. Legend 7 states the four nets are not connected on either face. The r5 review no longer reports it, and no cycle since has. |
| **(1) View B's 0.6 mm dimension** attached to the copper, not the FR4 substrate | **FIXED (r5).** The tab's copper is now drawn on the substrate's **outer** faces, so the extension lines attach to the substrate's own boundaries and the span excludes both copper layers. The dimension is now labelled **"FR4 substrate 0.6 mm"** (led out to the free margin on two lines). |
| **(2) View B callout 10** sat in the hub material with no leader | **FIXED (r5).** Bubble 10 now carries a leader to the tab. |
| **(4) Slot-face copper construction undefined** (Q6's "F.Cu and B.Cu" mislabels internal routed faces as outer layers) | **OUT-OF-SCOPE-WAIVED** — this is the **JLCPCB question**, already asked as **section 2A** of `docs/fab/JLC-QUERY-DRAFT-MESSAGE.md` (PR #215) and as **Q6** on the sheet. The only permitted edit was applied: the wording no longer identifies the slot faces as `F.Cu`/`B.Cu` and now states the construction and layer connection are **UNRESOLVED**. The sheet's "Land construction — UNVERIFIED" row says the same. The r8 review still lists it, by design. |
| **(5) Mating-fit spec** (finished tab thickness, slot tolerances, solder clearances, slot-end radius, tab-tip relief) | **OUT-OF-SCOPE-WAIVED** — these are **design decisions** no record fixes. Nothing was invented. The sheet now carries a **"Mating fit — UNVERIFIED"** row naming every one of them and mapping them to **Q3/Q7**, and legend 5 says the 6.0 mm seating is a REQUIREMENT, not a verified fit. The r8 review still lists it, by design. |

## What changed in the generator (r5–r8)

1. **View B: continuous copper → four separate conductors.** The two full-width `tab copper` strips were
   removed; each land now gets its own conductor on each face, with the 0.6 mm inter-land gap left as bare
   substrate. (This is the short-circuit fix.)
2. **Tab copper moved to the substrate's OUTER faces** in both views, at `CU_DRAWN_MM = 0.05` (real is
   35 µm). The FR4 dimension therefore spans substrate only. Consequence, stated on the sheet: the drawn
   fillet lane is the **FINISHED** gap, narrower than `ADR-046 §4.1`'s 0.30 mm nominal on bare substrate —
   legends 4 and 8 now say so.
3. **View B dimension relabelled "FR4 substrate 0.6 mm"**, led out on two lines (the full phrase is wider
   than the margin at the dimension line).
4. **View B balloon 10 given a leader** to the tab.
5. **Q6 and the land-construction row reworded** so they do not identify the internal routed-slot faces as
   `F.Cu`/`B.Cu`; the construction is stated UNRESOLVED.
6. **"Alignment caveat" qualified** as a **bare-substrate** figure (0.30 mm → 2.86° / 8.79 mm), with the
   narrower finished play given as a derived approximation.
7. **"Mating fit — UNVERIFIED" row added**; **"Sheet scope" row** now says outright that only two sections
   are drawn, so the named-but-undrawn mask/keep-out items are a stated scope limit, not a silent omission.
8. `dim_v()` now tolerates an empty label (the caller places the text).

## Reviews, served model and reviewed artefact

Every review file records the **served model** and the **PNG sha256** it reviewed. Served model for all
four cycles: **`gpt-6-astra`**.

| cycle | verdict | PNG sha256 |
|---|---|---|
| r5 | `DEFECTS_PRESENT 2` | `cb0932733b237654de59227760b7b3beda30988775df4ed098db28bad9fccfd0` |
| r6 | `DEFECTS_PRESENT 3` | `0598b7fb2e41e6ec8d4f76c2a67c1cd9a8b210452fad2cd7866c9d00ce922e54` |
| r7 | `DEFECTS_PRESENT 4` | `0598b7fb2e41e6ec8d4f76c2a67c1cd9a8b210452fad2cd7866c9d00ce922e54` |
| r8 | `DEFECTS_PRESENT 2` | `a4c74efbb8ba65465297fb399dfe53a37f9877179df4c82f2f03597c1e500b79` |

**Honest note on r7.** No generator change was made between r6 and r7, so **r7 re-reviewed the same PNG
as r6** — the artefact was current, not stale, but the cycle produced no new information and one of the
four was spent. r5, r6 and r8 each reviewed a distinct, freshly-generated PNG.

**On the verdict count.** The count is not monotone because the reviewer's rubric surfaces *different*
items at different levels of caveat: r6/r7 also counted the named-but-undrawn solder-mask and keep-out
items under COMPLETENESS; once the sheet stated outright that it is two sections only, r8 dropped those
and returned to the two genuinely open, out-of-scope items. **No mechanical defect appeared in any cycle
after r5.**

## What remains open, and the question it maps to

| Open item | Where it is asked |
|---|---|
| Slot-face land construction, and its connection to the board copper | **Q6** on the sheet; **section 2A** of `docs/fab/JLC-QUERY-DRAFT-MESSAGE.md` (PR #215) |
| Mating fit — finished tab thickness, slot width/depth tolerances, finished solder clearances, slot-end radius, tab-tip relief | **Q3**, **Q7** on the sheet; design decisions |
| Routed-face / tab-face surface finish | **Q1** |
| Routed-edge positional tolerance | **Q2** |
| Minimum routable non-plated slot (0.9 mm is below the ~1.0 mm repo note) | **Q4** |
| Routed cut-out cost delta | **Q5** |
| The three `ADR-046 §4.2.2` items before any drawing is issued: wing-side land geometry (**W1**), peel figure, JLCPCB cost delta | `ADR-046 §4.2.2`; `tracker/hardware/trade_study_wing_joint.py` |

The board itself is **unchanged** (Option B, no slot). No ADR, no board file and no outline was touched.
