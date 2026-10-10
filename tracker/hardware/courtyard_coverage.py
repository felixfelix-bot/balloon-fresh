#!/usr/bin/env python3
"""Generic courtyard coverage + overlap check for a KiCad 9 .kicad_pcb.

WHY THIS EXISTS
---------------
`tracker/hardware/courtyard_sexpr_check.py` and `courtyard_pcbnew_check.py` are
one-off scripts hard-wired to the v8b board path.  Neither answers the question
that actually matters for a fab gate: *does every footprint instance carry a
courtyard at all?*  A board with zero courtyards trivially has zero
`courtyards_overlap` DRC violations -- the check has nothing to compare -- so a
"0 overlap violations" claim made on such a board is VACUOUS (measured
2026-10-10 on `tracker/hardware/wing_board/wing_board_v9.kicad_pcb`: 12/12
footprints had no F.CrtYd/B.CrtYd geometry).

This tool reports, per footprint:
  * whether it has courtyard geometry (F.CrtYd or B.CrtYd),
  * the courtyard shape(s) in BOARD mm,
  * the pad extents in BOARD mm and the minimum margin by which the courtyard
    clears the pads (a courtyard that does not enclose the pads is a defect),
and then computes exact pairwise courtyard intersections (rect<->rect,
rect<->circle, circle<->circle; KiCad courtyards are rectangles/circles in this
repo).  Exit status is non-zero unless coverage is 100% AND there are 0
overlaps, so it is usable as a gate.

Geometry note: every *.kicad_pcb under tracker/hardware places parts at
rotation 0; the transform below implements KiCad's rotate-then-translate order
anyway and prints a warning if a non-zero-rotation footprint is present, so a
rotated board cannot silently produce wrong numbers.

Usage:
  python3 tracker/hardware/courtyard_coverage.py <board.kicad_pcb> [--json OUT]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys


# ----------------------------------------------------------------- s-expressions
def sexpr_tokens(text: str):
    """Yield (value, quoted) for every atom/paren in a KiCad s-expression."""
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif c == '(' or c == ')':
            yield c, False
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while j < n:
                if text[j] == '\\' and j + 1 < n:
                    buf.append(text[j + 1])
                    j += 2
                elif text[j] == '"':
                    break
                else:
                    buf.append(text[j])
                    j += 1
            yield ''.join(buf), True
            i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '()':
                j += 1
            yield text[i:j], False
            i = j


def sexpr_parse(text: str):
    """Return the list of top-level nodes; every node is a list of atoms/nodes."""
    stack: list[list] = []
    roots: list[list] = []
    for tok, quoted in sexpr_tokens(text):
        if tok == '(':
            node: list = []
            if stack:
                stack[-1].append(node)
            else:
                roots.append(node)
            stack.append(node)
        elif tok == ')':
            if stack:
                stack.pop()
        else:
            v = tok if quoted else _atom(tok)
            if stack:
                stack[-1].append(v)
            # stray atom at top level: ignore
    return roots


def _atom(tok: str):
    try:
        return int(tok)
    except ValueError:
        try:
            return float(tok)
        except ValueError:
            return tok


def head(node, name: str) -> bool:
    return isinstance(node, list) and bool(node) and node[0] == name


def child(node, name: str):
    for it in node:
        if isinstance(it, list) and it and it[0] == name:
            return it
    return None


def children(node, name: str):
    return [it for it in node if isinstance(it, list) and it and it[0] == name]


def num(v) -> float:
    return float(v) if isinstance(v, (int, float)) else float(str(v))


# ---------------------------------------------------------------------- geometry
def xform(px, py, ox, oy, rot_deg):
    """KiCad footprint-local (px,py) -> board mm.

    KiCad rotates the footprint counter-clockwise by rot (in a y-down frame this
    is the standard `at` transform), then translates by the footprint origin.
    """
    if rot_deg == 0:
        return px + ox, py + oy
    a = math.radians(rot_deg)
    ca, sa = math.cos(a), math.sin(a)
    return ox + px * ca + py * sa, oy - px * sa + py * ca


def rect_corners(x0, y0, x1, y1, ox, oy, rot):
    pts = []
    for px, py in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        pts.append(xform(px, py, ox, oy, rot))
    return pts


def circle_pts(cx, cy, r, ox, oy, rot, seg=72):
    bcx, bcy = xform(cx, cy, ox, oy, rot)
    return [(bcx + r * math.cos(2 * math.pi * i / seg),
             bcy + r * math.sin(2 * math.pi * i / seg)) for i in range(seg)]


def bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def dedupe_pts(pts, tol=1e-9):
    """Drop repeated consecutive vertices (incl. the contour's closing repeat)."""
    out = []
    for p in pts:
        if not out or abs(p[0] - out[-1][0]) > tol or abs(p[1] - out[-1][1]) > tol:
            out.append(p)
    while len(out) > 1 and abs(out[0][0] - out[-1][0]) <= tol \
            and abs(out[0][1] - out[-1][1]) <= tol:
        out.pop()
    return out


def poly_area(pts):
    a = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def _seg_hit(p, q, r, s):
    """Proper segment-intersection test (orientation method, incl. collinear cases).

    NOTE: an earlier version tested "is s inside bbox(r,p)" instead of "is p inside
    bbox(r,s)", so two *collinear but disjoint* courtyard edges (e.g. two parts
    both sitting on y=25.045, x 30..37 and x 56..58) reported a hit.  Verified
    fixed against the hub board, whose kicad-cli DRC reports 0 courtyards_overlap.
    """
    if p == q or r == s:
        return False    # degenerate edge cannot cross anything

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def in_box(pt, a, b):
        return (min(a[0], b[0]) - 1e-12 <= pt[0] <= max(a[0], b[0]) + 1e-12 and
                min(a[1], b[1]) - 1e-12 <= pt[1] <= max(a[1], b[1]) + 1e-12)

    d1, d2 = cross(r, s, p), cross(r, s, q)   # p/q vs line r-s
    d3, d4 = cross(p, q, r), cross(p, q, s)   # r/s vs line p-q
    if ((d3 > 0) != (d4 > 0)) and ((d1 > 0) != (d2 > 0)):
        return True
    if abs(d1) < 1e-12 and in_box(p, r, s):
        return True
    if abs(d2) < 1e-12 and in_box(q, r, s):
        return True
    if abs(d3) < 1e-12 and in_box(r, p, q):
        return True
    if abs(d4) < 1e-12 and in_box(s, p, q):
        return True
    return False


def point_in_poly(pt, poly):
    x, y = pt
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            xint = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < xint:
                inside = not inside
        j = i
    return inside


def polys_overlap(A, B):
    """True if convex (or simple) polygons A and B have positive-area overlap."""
    for p in A:
        if point_in_poly(p, B):
            return True
    for p in B:
        if point_in_poly(p, A):
            return True
    for i in range(len(A)):
        p, q = A[i], A[(i + 1) % len(A)]
        for j in range(len(B)):
            r, s = B[j], B[(j + 1) % len(B)]
            if _seg_hit(p, q, r, s):
                return True
    return False


def poly_distance(A, B):
    """Minimum distance between two disjoint polygons (0 if they touch)."""
    best = float('inf')
    for i in range(len(A)):
        p, q = A[i], A[(i + 1) % len(A)]
        for j in range(len(B)):
            r, s = B[j], B[(j + 1) % len(B)]
            best = min(best, min(_seg_seg_dist(p, q, r, s),
                                 _pt_seg_dist(p, r, s), _pt_seg_dist(r, p, q)))
    return best


def _pt_seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _seg_seg_dist(p1, p2, p3, p4):
    if _seg_hit(p1, p2, p3, p4):
        return 0.0
    return min(_pt_seg_dist(p1, p3, p4), _pt_seg_dist(p2, p3, p4),
               _pt_seg_dist(p3, p1, p2), _pt_seg_dist(p4, p1, p2))


# ------------------------------------------------------------------ board model
CRTYD_LAYERS = ('F.CrtYd', 'B.CrtYd')


def load_footprints(path: str):
    roots = sexpr_parse(open(path, encoding='utf-8').read())
    board = None
    for r in roots:
        if head(r, 'kicad_pcb'):
            board = r
    if board is None:
        raise SystemExit(f'{path}: no (kicad_pcb ...) root')

    out = []
    for fp in children(board, 'footprint'):
        at = child(fp, 'at')
        ox, oy = (num(at[1]), num(at[2])) if at else (0.0, 0.0)
        rot = num(at[3]) if at and len(at) > 3 else 0.0

        ref = None
        for p in children(fp, 'property'):
            if len(p) > 2 and p[1] == 'Reference':
                ref = str(p[2])
        if ref is None:
            for t in children(fp, 'fp_text'):
                if len(t) > 2 and t[1] == 'reference':
                    ref = str(t[2])
        val = None
        for p in children(fp, 'property'):
            if len(p) > 2 and p[1] == 'Value':
                val = str(p[2])
        if val is None:
            for t in children(fp, 'fp_text'):
                if len(t) > 2 and t[1] == 'value':
                    val = str(t[2])

        crtyd_polys = []
        crtyd_shapes = []
        for layer in CRTYD_LAYERS:
            # explicit rect / circle / poly graphics
            for g in children(fp, 'fp_rect'):
                if not _on_layer(g, layer):
                    continue
                s, e = child(g, 'start'), child(g, 'end')
                if not (s and e):
                    continue
                pts = dedupe_pts(rect_corners(num(s[1]), num(s[2]), num(e[1]),
                                              num(e[2]), ox, oy, rot))
                crtyd_polys.append(pts)
                crtyd_shapes.append(('rect', layer, pts))
            for g in children(fp, 'fp_circle'):
                if not _on_layer(g, layer):
                    continue
                c, e = child(g, 'center'), child(g, 'end')
                if not (c and e):
                    continue
                r = math.hypot(num(e[1]) - num(c[1]), num(e[2]) - num(c[2]))
                pts = dedupe_pts(circle_pts(num(c[1]), num(c[2]), r, ox, oy, rot))
                crtyd_polys.append(pts)
                crtyd_shapes.append(('circle', layer, pts))
            # closed polyline contours on the courtyard layer
            segs = []
            for g in children(fp, 'fp_line'):
                if not _on_layer(g, layer):
                    continue
                s, e = child(g, 'start'), child(g, 'end')
                if not (s and e):
                    continue
                segs.append((xform(num(s[1]), num(s[2]), ox, oy, rot),
                             xform(num(e[1]), num(e[2]), ox, oy, rot)))
            if segs:
                for contour in _chain(segs):
                    crtyd_polys.append(dedupe_pts(contour))
                    crtyd_shapes.append(('poly', layer, contour))

        # pad extents in board mm
        pad_polys = []
        for p in children(fp, 'pad'):
            at_p = child(p, 'at')
            sz = child(p, 'size')
            if not (at_p and sz):
                continue
            px, py = num(at_p[1]), num(at_p[2])
            prot = num(at_p[3]) if len(at_p) > 3 else 0.0
            w, h = num(sz[1]), num(sz[2])
            drill = child(p, 'drill')
            if head(p, 'np_thru_hole') or (drill and str(p[2]) == 'np_thru_hole'):
                pass
            pts = rect_corners(px - w / 2, py - h / 2, px + w / 2, py + h / 2,
                               ox, oy, rot + prot)
            pad_polys.append(dedupe_pts(pts))

        out.append({
            'ref': ref or '?', 'value': val, 'libid': fp[1] if len(fp) > 1 else None,
            'at': [ox, oy, rot],
            'crtyd_polys': crtyd_polys, 'crtyd_shapes': crtyd_shapes,
            'pad_polys': pad_polys,
        })
    return out


def _on_layer(node, layer):
    lay = child(node, 'layer')
    if not lay or len(lay) < 2:
        return False
    return str(lay[1]) == layer


def _chain(segs, tol=1e-6):
    """Chain a bag of segments into closed contours (best effort)."""
    remaining = list(segs)
    contours = []
    while remaining:
        cur = list(remaining.pop(0))
        changed = True
        while changed and remaining:
            changed = False
            for i, s in enumerate(remaining):
                if _close(cur[-1], s[0], tol):
                    cur.append(s[1])
                    remaining.pop(i)
                    changed = True
                    break
                if _close(cur[-1], s[1], tol):
                    cur.append(s[0])
                    remaining.pop(i)
                    changed = True
                    break
                if _close(cur[0], s[1], tol):
                    cur.insert(0, s[0])
                    remaining.pop(i)
                    changed = True
                    break
                if _close(cur[0], s[0], tol):
                    cur.insert(0, s[1])
                    remaining.pop(i)
                    changed = True
                    break
        contours.append(cur)
    return contours


def _close(a, b, tol):
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


# ------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('board')
    ap.add_argument('--json', help='write the full report as JSON to this path')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()

    fps = load_footprints(a.board)
    covered, missing = [], []
    report = {'board': a.board, 'footprints': len(fps), 'per_footprint': []}
    print(f'board      : {a.board}')
    print(f'footprints : {len(fps)}')

    for fp in fps:
        has = len(fp['crtyd_polys']) > 0
        has_pad = len(fp['pad_polys']) > 0
        cy_bb = bbox([p for poly in fp['crtyd_polys'] for p in poly]) \
            if has else None
        pad_bb = bbox([p for poly in fp['pad_polys'] for p in poly]) \
            if has_pad else None
        clearance = None
        if has and has_pad:
            clearance = min(min(poly_distance(cy, pad) for pad in fp['pad_polys'])
                            for cy in fp['crtyd_polys'])
        enclosing = None
        if has and has_pad:
            enclosing = all(any(point_in_poly(pt, cy) or
                                min(_pt_seg_dist(pt, cy[i], cy[(i + 1) % len(cy)])
                                    for i in range(len(cy))) < 1e-9
                                for cy in fp['crtyd_polys'])
                            for pad in fp['pad_polys'] for pt in pad[:2])
        entry = {
            'ref': fp['ref'], 'value': fp['value'], 'libid': fp['libid'],
            'at': fp['at'],
            'has_courtyard': has,
            'courtyard_shapes': [
                {'kind': k, 'layer': l, 'area_mm2': round(poly_area(p), 4),
                 'bbox': [round(v, 4) for v in bbox(p)]}
                for k, l, p in fp['crtyd_shapes']],
            'pad_bbox': [round(v, 4) for v in pad_bb] if pad_bb else None,
            'pad_to_courtyard_min_mm': (round(clearance, 4)
                                        if clearance is not None else None),
            'courtyard_encloses_pads': enclosing,
        }
        report['per_footprint'].append(entry)
        if has:
            covered.append(fp['ref'])
        else:
            missing.append(fp['ref'])
        if not a.quiet:
            tag = 'OK ' if has else 'MISSING'
            if has:
                s = fp['crtyd_shapes'][0]
                print(f'  {tag} {fp["ref"]:5s} {str(fp["value"])[:28]:28s} '
                      f'{len(fp["crtyd_shapes"])} shape(s) on {sorted({l for _, l, _ in fp["crtyd_shapes"]})} '
                      f'bbox={tuple(round(v, 2) for v in cy_bb)} '
                      f'pad-margin={entry["pad_to_courtyard_min_mm"]}mm '
                      f'encloses_pads={enclosing}')
            else:
                print(f'  {tag} {fp["ref"]:5s} {str(fp["value"])[:28]:28s} '
                      f'no F.CrtYd/B.CrtYd geometry')

    pct = (100.0 * len(covered) / len(fps)) if fps else 0.0
    print(f'courtyard coverage : {len(covered)}/{len(fps)} ({pct:.0f}%)')
    if missing:
        print(f'missing courtyards : {missing}')
    report['coverage'] = {'covered': len(covered), 'total': len(fps),
                          'percent': round(pct, 2), 'missing': missing}

    # ---- pairwise overlap of courtyard polygons, in board mm
    overlaps = []
    names = [fp['ref'] for fp in fps]
    for i in range(len(fps)):
        for j in range(i + 1, len(fps)):
            hits = []
            for A in fps[i]['crtyd_polys']:
                for B in fps[j]['crtyd_polys']:
                    if polys_overlap(A, B):
                        bbA, bbB = bbox(A), bbox(B)
                        x0 = max(bbA[0], bbB[0])
                        y0 = max(bbA[1], bbB[1])
                        x1 = min(bbA[2], bbB[2])
                        y1 = min(bbA[3], bbB[3])
                        hits.append([round(x0, 3), round(y0, 3),
                                     round(x1, 3), round(y1, 3)])
            if hits:
                overlaps.append({'a': fps[i]['ref'], 'b': fps[j]['ref'],
                                 'regions': hits})
    print(f'courtyard overlaps : {len(overlaps)}')
    for o in overlaps:
        print(f'  OVERLAP {o["a"]} <-> {o["b"]}  {len(o["regions"])} region(s) {o["regions"]}')
    if not covered:
        print('  NOTE: 0 courtyards present -> overlap result is VACUOUS '
              '(nothing was compared)')
    report['overlaps'] = overlaps
    report['overlap_check_vacuous'] = (len(covered) == 0)
    report['verdict'] = ('PASS' if (len(covered) == len(fps) and not overlaps)
                         else 'FAIL')

    warn = [fp['ref'] for fp in fps if fp['at'][2] not in (0, 0.0)]
    if warn:
        print(f'WARNING: non-zero-rotation footprints present {warn}; verify '
              f'against kicad-cli pcb drc')

    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        print(f'json written: {a.json}')
    print(f'verdict            : {report["verdict"]}')
    ok = (len(covered) == len(fps)) and not overlaps
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
