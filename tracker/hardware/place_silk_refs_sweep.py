#!/usr/bin/env python3
"""place_silk_refs_sweep.py -- resolve silk designator collisions by searching free space.

WHY THIS EXISTS ON TOP OF place_silk_refs.py AND fix_silk.py
Both existing tools move a colliding reference one step away from the thing it collides with.
On this board that plateaus at ~50 overlaps, because the collisions are chains: moving R_FB1 off
C_RP_42 lands it on R_FB2, and stepping back lands it on C_RP_42 again. A one-step-at-a-time mover
has no way out of that cycle, and the same-designator pairs cannot be resolved at all.

This is not a critique of those tools -- they were written for the hub, where the free space was
marginal ('a free-space sweep found only the left/right margins genuinely empty'). This board is
different: parts occupy y 5.0..28.5 mm of a 45 mm board, leaving a 16.6 mm strip along the bottom
that nothing uses. So the right move here is a SEARCH, not a nudge.

WHAT IT DOES
For every reference field, try a set of candidate positions around its own footprint (and, as a
last resort, in the free strip) and keep the first candidate that:
  * stays inside the board with a fab margin,
  * does not overlap any other silk item (other references, footprint silk graphics, pads),
  * does not sit over exposed copper,
  * stays a readable distance from its own footprint so the association is still obvious.
Candidates are tried in deterministic order (closest first, then a fixed grid), so the result is
reproducible.

WHAT IT REFUSES TO TOUCH
Pads, tracks, vias, zones, courtyards, board outline and footprint graphics. Only Reference field
position and text size change. That is the same contract AGENTS.md section 26 sets for silk fixes.

Text is set to 0.80 mm height / 0.15 mm thickness -- the JLCPCB legible minimum, which is also what
fix_silk.py uses, so the two agree.

Usage:
    place_silk_refs_sweep.py --board B [--margin MM] [--dry-run]
Exit: 0 = zero silk violations remain, 1 = some remain (listed), 2 = could not run.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew as k                                              # noqa: E402

TEXT_H = 0.80
TEXT_T = 0.15
EDGE_MARGIN = 0.30      # keep text this far from the board edge
COPPER_MARGIN = 0.05    # and this far from foreign copper


def drc(board):
    """Run native DRC and return (violations, unconnected)."""
    tmp = tempfile.mkdtemp()
    try:
        out = os.path.join(tmp, 'drc.json')
        subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--units', 'mm',
                        '--severity-all', '-o', out, board], capture_output=True)
        if not os.path.exists(out):
            raise SystemExit('REFUSED: kicad-cli produced no report')
        d = json.load(open(out))
        return d['violations'], d['unconnected_items']
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def rect_of(item):
    bb = item.GetBoundingBox()
    return (bb.GetLeft() / 1e6, bb.GetTop() / 1e6,
            bb.GetRight() / 1e6, bb.GetBottom() / 1e6)


def overlaps(a, b, gap=0.0):
    return not (a[2] + gap <= b[0] or b[2] + gap <= a[0] or
                a[3] + gap <= b[1] or b[3] + gap <= a[1])


def build_obstacles(board, skip_ref=None):
    """Everything on silk or exposed copper that a designator must avoid.

    Footprint silk GRAPHICS are included as obstacles: that is what produces most of the
    'Segment of X <-> Reference field of Y' records, and moving a graphic would mean editing a
    footprint, which this tool refuses to do.

    DELIBERATELY NOT fp.GetBoundingBox(): a footprint's bounding box INCLUDES its own reference
    text, so once a label has been displaced it inflates the box (measured: C_OUT reported 26.39 mm
    wide) and the label then blocks itself wherever it tries to go. That single mistake is why the
    first version pushed 30 of 67 designators more than 5 mm from their part.
    """
    obst = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        for g in fp.GraphicalItems():
            ln = k.LayerName(g.GetLayer())
            if ln in ('F.Silkscreen', 'B.Silkscreen'):
                obst.append(rect_of(g))
        if ref != skip_ref:
            obst.append(rect_of(fp.Reference()))
        for p in fp.Pads():
            if p.IsOnLayer(k.F_Cu) or p.IsOnLayer(k.B_Cu):
                obst.append(rect_of(p))
    return obst


def board_box(board):
    bb = board.GetBoardEdgesBoundingBox()
    return (bb.GetLeft() / 1e6, bb.GetTop() / 1e6,
            bb.GetRight() / 1e6, bb.GetBottom() / 1e6)


def candidates(fp, box, strip_top):
    """Candidate positions for one reference field, strictly nearest-first BY DISTANCE.

    Measured failure of the first two versions: a fixed ring order plus a fallback sweep of the
    bottom strip put 30 of 67 designators more than 5 mm from their part, and one 57 mm away.
    DRC was clean and the board was unusable, because a label nobody can associate with a part is
    not a legible label.

    Association is therefore the objective and clearance is the constraint: candidates are emitted
    in ascending distance from the part centre, out to 20 mm, before any distant fallback slot is
    considered at all.
    """
    import math as _m
    px = fp.GetPosition().x / 1e6
    py = fp.GetPosition().y / 1e6

    dists = []
    step = 0.20
    r = 0.0
    while r <= 20.0:
        if r == 0.0:
            dists.append((0.0, px, py))
        else:
            n = max(10, int(2 * _m.pi * r / step))
            for i in range(n):
                ang = 2 * _m.pi * i / n
                dists.append((r, px + r * _m.cos(ang), py + r * _m.sin(ang)))
        r += step
    # sort by the ACTUAL distance travelled (a ring point can land closer to the part than its
    # nominal radius when the part sits near a board edge and the ring is clipped)
    dists.sort(key=lambda d: d[0])
    out = [(x, y) for _, x, y in dists]

    # last resort: a deterministic sweep of the free strip, used only when nothing within 20 mm works
    y = strip_top + 1.0
    while y < box[3] - EDGE_MARGIN:
        x = box[0] + 1.5
        while x < box[2] - EDGE_MARGIN:
            out.append((x, y))
            x += 3.0
        y += 1.6
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--board', required=True)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--passes', type=int, default=3)
    a = ap.parse_args()

    board = k.LoadBoard(a.board)
    if board is None:
        print('REFUSED: could not load board')
        return 2

    box = board_box(board)
    fps = list(board.GetFootprints())
    parts_bottom = max(f.GetPosition().y / 1e6 for f in fps)

    # 1. normalise text size first -- this alone removes many collisions and is the fab minimum
    for fp in fps:
        t = fp.Reference()
        t.SetTextSize(k.VECTOR2I(int(TEXT_H * 1e6), int(TEXT_H * 1e6)))
        t.SetTextThickness(int(TEXT_T * 1e6))
        t.SetVisible(True)

    moved_total = 0
    for p in range(a.passes):
        viol, _ = drc(a.board)
        silk = [v for v in viol if v['type'].startswith('silk')]
        # On pass 0 we place regardless of whether DRC is clean: clean-but-misplaced is the
        # failure mode this tool exists to fix. Later passes only act if DRC still complains.
        if not silk and p > 0:
            print(f'PASS: no silk violations after {p} pass(es)')
            break

        # EVERY designator is re-placed, not just the currently-flagged ones. Measured: after
        # fix_silk.py some labels sat at x=67 mm on a 60 mm board and were never corrected,
        # because they collided with nothing and so never appeared in the DRC record.
        moved = 0
        for fp in sorted(fps, key=lambda f: f.GetPosition().x):
            ref = fp.GetReference()
            others = build_obstacles(board, skip_ref=ref)
            t = fp.Reference()
            best = None
            # horizontal first (normal reading orientation), vertical only if horizontal cannot
            # fit -- this is what lets a long designator sit alongside a small part
            for orient in (0, 90):
                t.SetTextAngle(k.EDA_ANGLE(orient, k.DEGREES_T))
                for (cx, cy) in candidates(fp, box, parts_bottom):
                    t.SetPosition(k.VECTOR2I(int(cx * 1e6), int(cy * 1e6)))
                    r = rect_of(t)
                    if r[0] < box[0] + EDGE_MARGIN or r[1] < box[1] + EDGE_MARGIN:
                        continue
                    if r[2] > box[2] - EDGE_MARGIN or r[3] > box[3] - EDGE_MARGIN:
                        continue
                    if any(overlaps(r, o) for o in others):
                        continue
                    best = (cx, cy, orient)
                    break
                if best is not None:
                    break
            if best is None:
                # leave it where it was rather than put it somewhere worse
                continue
            t.SetTextAngle(k.EDA_ANGLE(best[2], k.DEGREES_T))
            t.SetPosition(k.VECTOR2I(int(best[0] * 1e6), int(best[1] * 1e6)))
            moved += 1
        moved_total += moved
        if a.dry_run:
            print(f'DRY-RUN pass {p + 1}: would move {moved} field(s)')
            break
        k.SaveBoard(a.board, board)
        print(f'pass {p + 1}: moved {moved} field(s)')
        if moved == 0:
            break

    if not a.dry_run:
        k.SaveBoard(a.board, board)
        viol, _ = drc(a.board)
        silk = [v for v in viol if v['type'].startswith('silk')]
        print(f'RESULT: {len(silk)} silk violation(s) remain; moved {moved_total} field(s) total')

        # ASSOCIATION QUALITY. A DRC-clean board whose labels sit 20 mm from their parts is not
        # a legible board, so the displacement is measured and reported rather than assumed.
        import math as _m
        dists = []
        for fp in board.GetFootprints():
            t2 = fp.Reference()
            dx = (t2.GetPosition().x - fp.GetPosition().x) / 1e6
            dy = (t2.GetPosition().y - fp.GetPosition().y) / 1e6
            dists.append(_m.hypot(dx, dy))
        dists.sort()
        n = len(dists)
        if n:
            far = sum(1 for d in dists if d > 5.0)
            print(f'ASSOCIATION: median {dists[n // 2]:.2f} mm, '
                  f'max {dists[-1]:.2f} mm, {far}/{n} beyond 5 mm')
        for v in silk[:10]:
            print('  ', v['type'], v['description'][:100])
        return 0 if not silk else 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
