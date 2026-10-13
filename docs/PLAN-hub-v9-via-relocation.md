# PLAN — Hub v9: plane-via relocation + 2-net resolution

**Date:** 2026-10-12 · **Board:** `hub_board_v9_final.kicad_pcb` (KiCad DRC 32/21)
**Branch:** `feat/hub-routing-v9` · tip `d10778f`

## Problem statement (all measured)

1. **FAB BLOCKER** — 14 `(via blind (layers "F.Cu" "In2.Cu"))` + 4 more = 18 `+3V3`
   plane vias. agentee `via-lamination`: *"cannot be drilled."* JLCPCB standard
   4-layer = plated **through** vias only; blind is HDI (3-5x cost) or reject.
   KiCad DRC does not flag this. The board is **not orderable** as it stands.

2. **2 nets unrouted** — `SX1280_DIO2` (U1.11 → U4.11) and `SX1280_MISO`
   (U1.9 → U4.9). FreeRouting cannot route them: 53 s, score 979.96, 10
   unrouted, "cannot make further progress", **no SES**. Cause is capacity:
   F.Cu + B.Cu carry every signal, In1.Cu = GND plane, In2.Cu = +3V3 plane →
   **no spare signal layer.**

3. Silk-text (28) proven unfixable at this layout (agentee's own auto-fixer
   places 0 of 20).
4. fiducials + 1.5 mm tooling holes MISSING (both JLCPCB requirements).

## Proposed change (operator-directed: "move them to genuinely free space")

### Step A — move the 18 `+3V3` plane vias to genuinely free positions

Measured free-space search (5 mm radius, 0.25 mm grid, checks F.Cu+B.Cu tracks,
all pads, all vias on foreign nets, clearance 0.25 mm + 0.30 mm via radius):

| # | current (x,y) mm | move | target |
|---|---|---|---|
| 12 | — | **0.00 mm** | already free — no change |
| 1 | (46.299, 0.572) | 0.25 mm | (46.082, 0.697) |
| 1 | (43.222, 25.047) | 0.25 mm | (43.045, 25.224) |
| 1 | (81.000, 13.995) | 0.25 mm | (80.783, 14.120) |
| 1 | (58.950, 4.220) | 0.25 mm | (58.773, 4.043) |
| 1 | (1.465, 17.515) | 1.25 mm | (2.349, 18.399) |
| 1 | (44.770, 23.643) | 1.75 mm | (44.317, 21.952) |
| 1 | (41.645, 26.295) | 4.00 mm | (39.645, 22.831) |

Then **convert all 18 to THROUGH vias in place** (`SetViaType(VIATYPE_THROUGH)` +
`SetLayerPair(F.Cu, B.Cu)`) — no blind vias left.

**Why this is safe:** the +3V3 plane is on In2.Cu and B.Cu is a GND plane, so a
through via F.Cu→In2.Cu crosses B.Cu *by design*; the GND zone forms the antipad
automatically on refill. The only true obstacle is a foreign-net *track* or
*pad*, which the search now checks on **both** signal layers (the earlier
attempt only checked B.Cu and produced shorts).

### Step B — stub each moved via back to its pad

A via must be electrically joined to the pad it serves. For each via that MOVED,
add a 0.20 mm track from the new via position to the original via position
(which is the pad centre / its stub). Same net, same layer (F.Cu).

### Step C — refill zones, then re-DRC

`refill_hub_v9_zones.py` → KiCad DRC + agentee. Gate: `via-lamination` = 0,
`short` = 0, `hole-to-hole` = 0, and KiCad violations ≤ 32.

### Step D — the 2 unrouted nets (LAYOUT DECISION — needs operator)

FreeRouting cannot help (no spare layer). Options:
- **D1** — free a signal layer by moving In1.Cu GND to a stitching-only role
  and using In1.Cu as a signal layer. Needs a stackup re-plan; cheapest fab-wise
  (still a plain 4-layer board).
- **D2** — move U4 (SX1280) closer to U1 (ESP32) to shorten the corridor; risks
  the RF layout (antenna keep-out, ADR-049 geometry lock).
- **D3** — accept 2 unrouted nets as a documented exception; hand-route a short
  2-wire connection on the least-congested path and verify by DRC.

### Step E — 3D model + assembly adjustment (operator-directed)

Moving vias does not move any part, so `export_3d`/STEP is unaffected — **but**
the blind→through change alters **drill data** (14 blind holes become 18 through
holes). The drill file and the assembly drawing must be regenerated, and any
enclosure/keep-out that assumed a blind via must be re-checked.

Explicit check: does any 3D model or enclosure feature depend on a via position
or on via type? Report before/after drill counts.

### Step F — remaining fab items

- fiducials: 3 × 1.0 mm F.Cu round, mask-opened, away from parts
- tooling holes: 3 × 1.5 mm NPTH in corners
- `via-in-pad` (12) / `via-annulus-past-pad` (4): add the IPC-4761 type VII
  fill+cap note, or shrink those vias to 0.45/0.25 mm

## Questions for the visual consultant

1. Is the **through-via + automatic GND antipad** reasoning correct for a
   4-layer stackup (F.Cu signal / In1.Cu GND / In2.Cu +3V3 / B.Cu GND)? Any
   case where a through via must NOT cross B.Cu?
2. Does moving a plane via **4.00 mm** (the (41.645,26.295) case) away from its
   pad create an unacceptable **current-loop / IR-drop** problem on the +3V3
   plane return? Is a 0.20 mm stub acceptable at that length?
3. Is **D1** (use In1.Cu as a signal layer, stitch GND on B.Cu) sound, or does it
   break the RF reference plane under the SX1280/antenna feed?
4. Does the **blind→through drill change** compromise any mechanical/enclosure
   assumption (e.g. a blind via under a keep-out or an adhesive area)?
5. Any spatial reason the 2 unrouted nets (DIO2/MISO, both short 12 mm 2-wire
   signals to the radio) should NOT be prioritised over other work?

## Refusals / limits
- Will not hand-route through 109 obstacles without DRC verification.
- Will not hide refdes (unlabeled boards cannot be debugged).
- Will not move parts unilaterally (geometry lock).
