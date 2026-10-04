#!/usr/bin/env python3.14
"""Decisive courtyard check: parse the board S-expression directly.

pcbnew's GetBoundingBox() mixes coordinate frames for footprint graphics, so the
authoritative read is the file itself. Extracts each footprint's F.CrtYd geometry
and computes real rectangle intersections.
"""
import re, sys

BOARD = "/home/c03rad0r/worktrees/t_157df236/tracker/hardware/output/v8b_krt_routed.kicad_pcb"
txt = open(BOARD).read()

def blocks(text, head):
    """Yield (start, body) for balanced-paren blocks starting with `head`."""
    i = 0
    while True:
        m = re.search(r"\(" + head + r"[\s(]", text[i:])
        if not m:
            return
        s = i + m.start()
        depth = 0
        j = s
        in_str = False
        while j < len(text):
            c = text[j]
            if c == '"' and text[j - 1] != "\\":
                in_str = not in_str
            if not in_str:
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        break
            j += 1
        yield s, text[s:j + 1]
        i = j + 1

def num(s):
    return float(s)

def courtyard_rects(fp_body):
    """Return list of F.CrtYd rects (x1,y1,x2,y2) in board mm."""
    out = []
    # fp_rect on F.CrtYd
    for m in re.finditer(r"\(fp_rect\s+\(start\s+([-\d.]+)\s+([-\d.]+)\)\s+\(end\s+([-\d.]+)\s+([-\d.]+)\)"
                         r"[\s\S]{0,400}?\(layer\s+\"(F\.CrtYd|B\.CrtYd)\"\)", fp_body):
        x1, y1, x2, y2 = map(num, m.groups()[:4])
        out.append((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
    # fp_line segments on F.CrtYd -> fold into a bbox per contiguous group (conservative)
    segs = []
    for m in re.finditer(r"\(fp_line\s+\(start\s+([-\d.]+)\s+([-\d.]+)\)\s+\(end\s+([-\d.]+)\s+([-\d.]+)\)"
                         r"[\s\S]{0,400}?\(layer\s+\"(F\.CrtYd|B\.CrtYd)\"\)", fp_body):
        x1, y1, x2, y2 = map(num, m.groups()[:4])
        segs.append((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
    if segs:
        out.append((min(s[0] for s in segs), min(s[1] for s in segs),
                    max(s[2] for s in segs), max(s[3] for s in segs)))
    return out, len(segs)

def xy(fp_body, key="at"):
    m = re.search(r"\(at\s+([-\d.]+)\s+([-\d.]+)(?:\s+([-\d.]+))?\)", fp_body)
    return (num(m.group(1)), num(m.group(2)), num(m.group(3) or 0)) if m else None

fps = {}
for _, body in blocks(txt, "footprint"):
    ref = re.search(r'\(property "Reference" "([^"]+)"', body) or \
          re.search(r'\(fp_text reference "([^"]+)"', body)
    if not ref:
        continue
    fps[ref.group(1)] = body

print("footprints parsed:", len(fps), sorted(fps))
geo = {}
for ref, body in fps.items():
    rects, nseg = courtyard_rects(body)
    val = re.search(r'\(property "Value" "([^"]*)"', body) or \
          re.search(r'\(fp_text value "([^"]*)"', body)
    geo[ref] = rects
    print(f"\n== {ref} ({val.group(1) if val else '?'}) at={xy(body)}")
    for r in rects:
        print(f"   CrtYd rect ({r[0]:.3f},{r[1]:.3f})-({r[2]:.3f},{r[3]:.3f}) "
              f"size {r[2]-r[0]:.2f}x{r[3]-r[1]:.2f}")
    if not rects:
        print("   (no CrtYd geometry found)")
    pads = re.findall(r'\(pad\s+"?([^"\s]+)"?\s+\w+', body)
    print(f"   {len(pads)} pads")

print("\n=== REAL courtyard intersections (board mm) ===")
def inter(A, B):
    x1, y1 = max(A[0], B[0]), max(A[1], B[1])
    x2, y2 = min(A[2], B[2]), min(A[3], B[3])
    if x2 <= x1 or y2 <= y1:
        return None
    return (x1, y1, x2, y2, (x2 - x1) * (y2 - y1))

names = sorted(geo)
found = 0
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        for A in geo[names[i]]:
            for B in geo[names[j]]:
                r = inter(A, B)
                if r:
                    found += 1
                    print(f"  {names[i]} <-> {names[j]}: overlap "
                          f"{r[4]:.3f} mm^2  region ({r[0]:.2f},{r[1]:.2f})-({r[2]:.2f},{r[3]:.2f})")
if not found:
    print("  none")
