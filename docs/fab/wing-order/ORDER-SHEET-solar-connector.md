# Solar-cell connector board (wing interconnect) — JLCPCB order sheet

**Board of record:** `tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb`
sha256 `c05d5d5aa601b57c305574320fdeb8a98e1fcf8ada87b03cb0ed9998df1f0b0d`
**Package:** `docs/fab/wing-order/interconnect-jlcpcb-upload.zip`
**Package state:** `build_wing_order.py --check` → **REPRODUCIBLE, 40/40 files byte-identical**
**DRC:** `kicad-cli pcb drc` → **0 violations, 0 unconnected items, 0 parity errors**

This is the board the four solar-cell tails solder to (per-cell SS24 bypass, ADR-132/134).
Every number below was read out of the board file, not from prose.

---

## ⚠ READ THIS FIRST — this order is FABRICATION-ONLY

The repo currently marks this board **NOT ORDERABLE**, and it is right to — but **both of its
blockers are assembly questions**, and neither applies to a bare-board order. That distinction
is what makes this sheet useful, and getting it wrong is how you end up with 5 unassembled
boards and no explanation.

| open item (repo) | applies to | does it block FABRICATION? |
|---|---|---|
| **Q1** — JLC's zero-angle model lands the SS24 banded end on pad 1 | SMT placement | **No.** No part is placed. |
| **Q2** — a 34.6 × 20.0 × 0.4 mm board assemblable at all (0.4 mm is outside Economic PCBA; Standard needs ≥70 × 70 mm) | SMT assembly | **No.** No assembly is ordered. |

So: **order bare boards, solder the three SS24s yourself.** That is not a compromise — it is the
route the repo's own evidence supports, and it closes neither open question by pretending to.

**Cost of self-soldering:** 3 × SMA diodes per board. A 2-pad SMA joint is a hand joint, and the
package already carries the paste apertures and CPL so a later assembly order stays possible.

---

## Order settings (fab only)

| field | value | source |
|---|---|---|
| Dimensions | **34.60 × 20.00 mm** Edge.Cuts **centreline** | 4 straight Edge.Cuts segments; bbox reads 34.70 × 20.10 because it includes half the line width |
| Layers | **2** | `GetCopperLayerCount()` |
| Thickness | **0.4 mm** | board file |
| Surface finish | **ENIG** (required) | JLC: boards with thickness ≤ 0.4 mm do not support HASL |
| Min board size check | 3 × 3 mm at ≥0.6 mm; **"Manual review required for thinner PCBs"** | see below — this is the one thing to confirm at upload |
| Copper weight | 1 oz | default, matches the rules the board was checked against |
| Panelisation | **none** — order as single boards | panel arithmetic exists in `PANELIZATION.md` but is unapproved and unnecessary for a bare order |

### The one item to confirm at upload

JLC's published minimum-dimension row reads: *"FR4/Rogers/PTFE: 3 × 3 mm … **These limits apply
to PCBs with thickness ≥ 0.6 mm. Manual review required for thinner PCBs.**"*

At 34.6 × 20.0 mm this board is far above 3 × 3 mm on both axes, so the *size* is not the
question — the question is whether a 0.4 mm board needs the manual review their note mentions.
**Upload the package and read the automated quote.** If the quote returns a price, accept it;
if it flags manual review, that is the answer and it costs a day. Do not pre-emptively thicken
the board — 0.4 mm is a wing-mass decision (ADR-132: 0.79 g/wing), not a fab convenience.

## Drill table

| size | kind | count |
|---|---|---|
| 0.400 mm | via (through) | 2 |

Two holes total, both 0.400 mm vias. No PTH component holes, no NPTH. Every size is a JLC stock
size — **do not normalise**.

## Parts (hand-solder after the boards arrive)

| ref | part | LCSC | qty/board |
|---|---|---|---|
| D1, D2, D3 | SS24 (SMA) | C50645 | 3 |

**Check polarity before soldering.** The repo proves the diode *cathode net* is on pad 1 (merged
polarity guard, 3 reversed-diode rejection tests). It has **not** proven that JLC's placement
model agrees — which is exactly why hand-soldering with the silkscreen cathode band and a
continuity check is the safe route here. Mark the cathode on every board before fitting.

## How many to order

Four wings, so **order 10+ boards**: the minimum quantity, plus spares for the near-certainty of
one damaged tail joint. They are small and cheap; the shipping dominates.

## What NOT to do

- Do **not** order assembly. Both open questions are assembly questions and both are unanswered.
- Do **not** change the thickness to 0.8 mm to slip into Economic PCBA. That trades a mass
  decision for a fab convenience and would need a new ADR.
- Do **not** panelise. `PANELIZATION.md` is explicitly *"ARITHMETIC ONLY. No panel design exists
  and none has been approved."*

## Why the 3D render looks empty — it is not a preview of a real part

**This board carries no 3D models at all.** Measured:

```
scripts/model_resolution_census.py --check --require-refs D1,D2,D3,J1,SC1,SC2,SC3
  -> 7 footprints, 0 model refs, 0 resolved, 0 unresolved
  -> no model block: D1, D2, D3, J1, SC1, SC2, SC3
```

`grep -c "(model"` on the board returns **0**, and none of the three footprints in
`wing_ic.pretty/` defines one. So `kicad-cli pcb render` produces substrate, copper and
silkscreen with **no component bodies** — and it exits 0 without warning, which is the documented
hazard. Do not read a sparse render as "parts not placed": the parts are placed, they simply have
no artwork.

For a visual check before ordering, use the **fab layer plots** in
`docs/fab/wing-order/interconnect/` rather than a 3D render.

## Reproduce

```bash
cd <repo>
sha256sum tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb
# c05d5d5aa601b57c305574320fdeb8a98e1fcf8ada87b03cb0ed9998df1f0b0d
/usr/bin/python3 tracker/hardware/build_wing_order.py --check     # REPRODUCIBLE, 40/40
kicad-cli pcb drc --format json --units mm -o /tmp/wi.json \
  tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb  # 0/0/0
```
