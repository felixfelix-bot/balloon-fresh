#!/usr/bin/env python3
"""place_hub_v9_silk.py -- move the remaining offender refdes to free space.

agentee reports, for each silk-text error, a free position as
`label = { at = [x, y] } is clear`.  Shrinking (clean_hub_v9_silk.py) cleared
10 of 28; the rest sit ON via fields, where shrink cannot help.  Move the
refdes text to the position agentee itself says is clear.

Input: the agentee drc JSON (--json output).  Only touches footprints whose
refdes is currently hidden or still flagged; leaves everything else alone.

Deterministic; no LLM.
"""
import argparse
import json
import re
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
PAT = re.compile(r"label\s*=\s*\{\s*at\s*=\s*\[\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\]")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("json")
    ap.add_argument("out")
    args = ap.parse_args()

    rep = json.load(open(args.json))
    # map refdes -> a free position, from the "at [x,y] is clear" hints
    free = {}
    for x in rep.get("diagnostics", []):
        if x.get("rule") != "silk-text":
            continue
        ref = x.get("at", "").replace("silk ", "").strip()
        m = PAT.search(x.get("message", ""))
        if m:
            free.setdefault(ref, (float(m.group(1)), float(m.group(2))))

    print(f"free positions offered: {len(free)} -> {sorted(free)}")

    b = pcbnew.LoadBoard(args.inp)
    moved = 0
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if ref not in free:
            continue
        rt = fp.Reference()
        x, y = free[ref]
        sz = rt.GetTextSize()
        rt.SetVisible(True)
        rt.SetPosition(pcbnew.VECTOR2I(int(round(x * MM)), int(round(y * MM))))
        moved += 1
        print(f"  {ref}: refdes -> ({x:.2f},{y:.2f}) size {sz.x/MM:.2f} mm")
    print(f"refdes moved: {moved}")
    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
