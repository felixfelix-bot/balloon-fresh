#!/usr/bin/env python3.14
"""Ground-truth courtyard bboxes via pcbnew (board mm).  Validation harness for
tracker/hardware/courtyard_coverage.py."""
import json
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

mm = lambda v: v / 1e6
b = pcbnew.LoadBoard(sys.argv[1])
out = {}
for fp in b.GetFootprints():
    ref = fp.GetReference()
    rec = {"pos": [round(mm(fp.GetPosition().x), 4), round(mm(fp.GetPosition().y), 4)],
           "rot": round(fp.GetOrientationDegrees(), 3), "shapes": []}
    for layer, nm in ((pcbnew.F_CrtYd, "F.CrtYd"), (pcbnew.B_CrtYd, "B.CrtYd")):
        cy = fp.GetCourtyard(layer)
        if cy.OutlineCount() == 0:
            continue
        bb = cy.BBox()
        rec["shapes"].append({
            "layer": nm, "kind": "poly", "outlines": cy.OutlineCount(),
            "bbox": [round(mm(bb.GetX()), 4), round(mm(bb.GetY()), 4),
                     round(mm(bb.GetX() + bb.GetWidth()), 4),
                     round(mm(bb.GetY() + bb.GetHeight()), 4)]})
    out[ref] = rec
json.dump(out, open(sys.argv[2], "w"), indent=2, sort_keys=True)
print(f"wrote {sys.argv[2]} ({len(out)} footprints)")
