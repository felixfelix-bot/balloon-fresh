# ADR-085 — Wing-socket slot placement on a 70 × 70 mm hub: rotations derive from the footprint datum, and every slot must reach its own edge

- **Status:** **Proposed** — the *defect and the rule* are measured; the **text is not
  human-accepted**. Per the ADR-first rule (ADR-029 §Context) no BOM freeze, placement freeze or
  fabrication may treat it as frozen until a human accepts it.
- **Date:** 2026-10-17
- **Decision owner:** Felix (operator). The text is not accepted.
- **Author:** subagent (Hermes), branch `pr/wing-slot-rule`, worktree `~/worktrees/wing-fix`.
- **Number allocated with `python3 scripts/adr_next_number.py`, which printed `85`** (verified
  before use; no file renamed, no number hard-coded past this allocation).
- **Corrects / supersedes:** **ADR-048 §2.1**, row *"Hub outline the slots sit on"*, which records
  **22 × 22 mm**. The hub is **70 × 70 mm** (ADR-068 as revised 2026-10-14). The correction is
  **recorded in place** in ADR-048, not silently rewritten — see §5.
- **Related:**
  - `docs/adr/046-wing-board-interface.md` — the *wing* side (4-pin tab, land 4.0 × 1.2 mm,
    pitch 1.8 mm, insert depth 6.0 mm, hub slot 0.9 mm ±0.10 mm, 90° attach).
  - `docs/adr/048-v9-hub-wing-interfaces.md` §2.1/§2.2 — the hub side; §2.2 requires
    *"Identical geometry, differing only in assembly tilt | yes"*.
  - `docs/adr/068-hub-v9-outline-60x60.md` — the 70 × 70 mm outline (as revised).
  - `docs/WING-TO-HUB-SOCKET-SPEC.md` §2.1 — Option A is a **"milled edge slot"**.
  - `docs/fab/WING-INTERFACE-ROOT-CAUSE.md`, `docs/fab/WING-INTERFACE-VERIFICATION.md` — the
    measurement and the root cause.
  - `docs/fab/WING-INTERFACE-SEAT-RULE-FIX.md` — the fix, before/after, and why the canonical
    routed board is not overwritten.
  - `docs/fab/hub-v9/PEEL-COUPON.md` — the solder-joint load case this interface feeds.

---

## 1. Context — a placement rule written for a board a third the size

ADR-048 §2.1 records the outline the wing slots sit on as **22 × 22 mm**, cited to
`docs/hardware-design.md` line 13. That was the v9 design-intent hub. The hub that was actually
built is **70 × 70 mm** (ADR-068). **The slot-placement rule was written against a board a third the
size and the four tabs were never re-derived for the larger outline** — the same defect class as the
other two-records-one-parameter collisions recorded in `AGENTS.md`.

The consequence, measured on `tracker/hardware/hub_board_v9.kicad_pcb`
(sha256 `e55a2946…`):

```
tab    edge    rot     origin            slot union (absolute mm)        slot vs edge
J_W1   west      0.0   ( 5.20, 35.00)    x  5.17 … 11.22   y 34.52…35.48  WHOLLY INSIDE, 5.25 mm
J_W2   north   270.0   (35.00, 64.80)    x 34.52 … 35.48   y 64.78…70.83  crosses bottom, +0.75 mm
J_W3   east    180.0   (64.80, 35.00)    x 58.77 … 64.83   y 34.52…35.48  WHOLLY INSIDE, 5.25 mm
J_W4   south    90.0   (35.00,  5.20)    x 34.52 … 35.48   y -0.82… 5.22  crosses top,    +0.75 mm
```

All four footprints have **identical local geometry** (slot local `x ∈ [-0.03, +6.02]`, 0.96 mm
wide; lands at local `x = +3.0`) and the **same 5.20 mm origin offset**. Only the **rotation**
differed — and it sent the slot in **opposite directions**:

```
J_W1 west   rot   0   local +x -> absolute +x   slot goes INBOARD  -> buried
J_W3 east   rot 180   local +x -> absolute -x   slot goes INBOARD  -> buried
J_W4 south  rot  90   local +x -> absolute -y   slot goes OUTBOARD -> crosses the edge
J_W2 north  rot 270   local +x -> absolute +y   slot goes OUTBOARD -> crosses the edge
```

**The rotation set was 180° inconsistent between the {west,east} pair and the {north,south} pair**,
so ADR-048 §2.2's *"identical geometry, differing only in assembly tilt"* was **not met**. The
**pads** were equivalent (every tab's pad set matches `J_W4` after a 90° multiple); only the
**milled slot** was not.

### 1.1 Why it survived: the 2026-10-14 offset is a compensation for the rotation error

`build_hub_board_v9.py` carried a documented repair in `wing_socket_inboard_offset()` that added a
uniform **5.20 mm inboard offset** because *"16 of 32 wing-socket pads landed OUTSIDE the board
outline"*. They landed outside **because the rotations were already inconsistent**: with local `+x`
pointing **outboard** on the north/south edges, the lands (local `x = +3.0`) went 3 mm off the
board. The offset pulled the pads on and pushed the west/east slots 5.25 mm inboard — it **hides the
error on two edges and creates the defect on the other two**. Neither number alone fixes it:

| choice | slot | pads |
|---|---|---|
| offset → 0 | on the edge ✓ | off the board ✗ |
| offset = 5.2 (as found) | 5.25 mm inboard ✗ | on the board ✓ |
| **rotations consistent + offset re-derived** | **on the edge ✓** | **on the board ✓** |

---

## 2. Decision

> **The four `J_W*` seat rotations are DERIVED from the footprint's own datum convention, the
> inboard offset is re-derived from the corrected rotations, and every wing slot must reach its own
> board edge — asserted by a check, not by review.**

### 2.1 The datum convention fixes the rotations

The footprint's datum is *"the intersection of the hub's INTERFACE (outer) edge with the SLOT CENTRE
LINE, **+x INBOARD**"*. The board frame is KiCad's (x right, **y down**), so *inboard* — from a hub
edge toward the board interior — is, per edge:

| edge | inboard (absolute) | derived rotation | as found |
|---|---|---|---|
| west  (x = 0) | **+x** | **0°** | 0° |
| east  (x = w) | **−x** | **180°** | 180° |
| north (y = h) | **−y** | **90°** | 270° ✗ |
| south (y = 0) | **+y** | **270°** | 90° ✗ |

KiCad rotates a footprint CCW by `θ` in this y-down frame, so local `+x` maps to absolute
`(cos θ, −sin θ)`; the rotation is `θ = atan2(−dy, dx)` for the edge's inboard direction.
**The rotations are computed (`seat_rotation_deg`), never typed** — rule R2.

### 2.2 The inboard offset is then re-derived, and it is small

With `+x` inboard on every edge, the datum convention itself places the datum **on** the interface
edge: the milled slot (local `x = −0.03 … +6.02`) opens onto the edge, and the lands (local
`x = +3.0`) sit inboard. The offset is therefore only the smallest inboard shift that still keeps
every pad on the board by the fab edge clearance:

```
offset = max(0, FAB_EDGE_CLEARANCE − min_over_pads(pad_x0_local))
       = max(0, 0.20 − 1.00) = 0.00 mm        # Wing_Tab_4P: land centre 3.0 − half 2.0 = 1.0
```

**Offset before 5.20 mm → after 0.00 mm.** It is derived from the footprint's measured pad
geometry, not a literal.

### 2.3 The rule that makes this class of defect visible

**Every `J_W*` slot union bbox must intersect its own board edge, within a stated tolerance of
0.30 mm.** Enforced by `tracker/hardware/verify_wing_interfaces.py`, whose edge-reach assertion
**drives the process exit code**:

```
0 = all four wing slots reach their own edge
1 = at least one slot is wholly inside the board (not an edge slot)
```

Nothing electrical sees this class of defect — DRC does not know a slot is supposed to be an edge
slot — so the detector is the gate.

---

## 3. Consequences

Measured after the change (regenerated placement, `verify_wing_interfaces.py` **EXIT 0**):

```
tab    edge   rot   slot union (absolute mm)              verdict
J_W1   west     0   x  -0.03 …  6.03   y 34.52…35.48      reaches LEFT   edge
J_W2   north   90   x  34.52 … 35.48   y 63.98…70.03      reaches BOTTOM edge
J_W3   east   180   x  63.98 … 70.03   y 34.52…35.48      reaches RIGHT  edge
J_W4   south  270   x  34.52 … 35.48   y -0.03… 6.03      reaches TOP    edge
```

Outline `Edge.Cuts` bbox `x −0.07 … 70.08  y −0.07 … 70.08`. Every slot crosses its own edge by
**0.03 mm** (the footprint's own slot local `x` starts at `−0.03`), well inside the 0.30 mm
tolerance. Every land is 1.0 mm inboard, so the pads stay on the board.

**Consequences to expect, not to hide:**

- **The four wings can now seat symmetrically.** They are 176 mm panels soldered in at 90° spacing;
  with the left/right slots 5.25 mm inboard while top/bottom opened onto the edge, the four wings
  could not seat symmetrically, which changed the array geometry **and** the solder-joint load case
  `docs/fab/hub-v9/PEEL-COUPON.md` exists to measure.
- **A footprint move changes clearance and routing.** The west/east sockets move 5.20 mm outboard
  (to the edge) and the north/south sockets move 5.20 mm (from 64.80/5.20 to 70.00/0.00). Tracks
  that reached the old pad positions must be re-routed. This ADR does **not** re-route.
- **The 30 `copper_edge_clearance` items on `J_W1..J_W4` are expected to change** once the board is
  re-routed: the west/east slots now add edge-located copper that was previously 5.25 mm inboard.
  That edge-located copper is the intentional ADR-046/048 interface.
- **The canonical routed board is not replaced by this ADR.** `hub_board_v9.kicad_pcb` is the routed
  board (834 tracks / 286 vias / 57-59 nets, promoted by `ff87f4953`). The builder is a *placement*
  writer whose output carries no tracks; the repo's own `fab_readiness_guard.py` refuses a
  placed-only canonical board. Re-routing + promotion is a separate step
  (`tracker/hardware/fab_grade.sh`), recorded as remaining work in
  `docs/fab/WING-INTERFACE-SEAT-RULE-FIX.md`.

---

## 4. Evidence and reproduce

```bash
# the detector (exit code 0 = every slot reaches its edge)
~/venvs/kicad/bin/python tracker/hardware/verify_wing_interfaces.py [board.kicad_pcb]

# the derived rotations and the derived offset
~/venvs/kicad/bin/python - <<'PY'
import importlib.util
spec = importlib.util.spec_from_file_location("b", "tracker/hardware/build_hub_board_v9.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
print([(r, e, m.seat_rotation_deg(e)) for r, e in m.EDGE_SEATS])
PY

# regenerate the placement
KRT_DIR=/data/repos/KiCadRoutingTools ~/venvs/kicad/bin/python \
    tracker/hardware/build_hub_board_v9.py \
    --out tracker/hardware/output/hub_board_v9_seed.kicad_pcb --publish
```

Root cause: `docs/fab/WING-INTERFACE-ROOT-CAUSE.md` · independent measurement:
`docs/fab/WING-INTERFACE-VERIFICATION.md` · fix record:
`docs/fab/WING-INTERFACE-SEAT-RULE-FIX.md`.

---

## 5. The stale ADR-048 §2.1 record — corrected IN PLACE, with the correction recorded

ADR-048 §2.1's table row recorded the outline the slots sit on as **22 × 22 mm**. It is **not**
silently rewritten. ADR-048 now carries a **SUPERSEDED** annotation on that row that (a) keeps the
original value and its original citation visible, (b) names the governing record (ADR-068, 70 × 70 mm),
and (c) records *why* the stale value mattered — it is the contributing cause of this defect, because
the placement rule was written against a board a third the size. This ADR is the rule for the 70 × 70
outline.

**For future sessions:** when a record asserts a value for a *registered* parameter (outline, land
size, wing orientation, …), grep for a competing value and cite the record that owns it. A
contradiction that names no winner is a **defect**, not an ambiguity.
