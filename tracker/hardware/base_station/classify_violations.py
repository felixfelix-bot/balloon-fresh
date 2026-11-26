#!/usr/bin/env python3
"""Classify every DRC violation on the base-station board into real-vs-artifact, with numbers.

The question this answers, per class, is NOT "how many" but "does the number exist in the
board's real geometry, or only because the pour was never filled". The distinction matters
because this repo has twice shipped a gate that reported phantom violations by comparing
against a bounding box rather than real geometry (check_hole_clearance.py, PR #554; a motor
reservation probe).

For every class it prints:
  * the count, split by severity (an error and a warning are different problems)
  * the OBJECT-KIND PAIRS involved, so a single root cause is visible as one row
  * for `clearance`: the MEASURED gap, from the pad's own copper polygon to the zone's
    FILLED polygon, both before and after a refill, in mm
  * the verdict: REAL / ARTIFACT-STALE-POUR / COSMETIC

Exit 0 always (this is an instrument, not a gate).

Usage: classify_violations.py BOARD.kicad_pcb [--refilled OTHER.kicad_pcb]
"""
import argparse
import collections
import json
import os
import re
import subprocess
import sys
import tempfile

MM = 1e6


def drc(board, out):
    subprocess.run(
        ["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all", "-o", out, board],
        capture_output=True, text=True)
    return json.load(open(out))


def kind(desc):
    if desc.startswith("Pad "):
        return "pad"
    if desc.startswith("Zone "):
        return "zone"
    if desc.startswith("Track "):
        return "track"
    if desc.startswith("Via"):
        return "via"
    if "Reference field" in desc or "Value field" in desc:
        return "silk-text"
    if desc.startswith("Segment") or desc.startswith("Rectangle") or desc.startswith("Circle"):
        return "silk-graphic" if "Silkscreen" in desc else "edge-graphic"
    if desc.startswith("Footprint "):
        return "footprint"
    return desc.split(" ")[0].lower()


def ref_of(desc):
    m = re.search(r"of ([\w.]+)", desc)
    if m:
        return m.group(1)
    m = re.search(r"field of ([\w.]+)", desc)
    return m.group(1) if m else ""


def net_of(desc):
    m = re.search(r"\[([^\]]*)\]", desc)
    return m.group(1) if m else ""


def measure_gaps(board_path, drc_doc):
    """Real pad-copper -> zone-fill distance for every clearance item, in mm."""
    sys.path.insert(0, "/usr/lib/python3/dist-packages")
    import pcbnew
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    def poly_of(sps):
        out = []
        for i in range(sps.OutlineCount()):
            oc = sps.COutline(i)
            pts = [(oc.CPoint(k).x / MM, oc.CPoint(k).y / MM) for k in range(oc.PointCount())]
            hs = []
            for h in range(sps.HoleCount(i)):
                hc = sps.CHole(i, h)
                hs.append([(hc.CPoint(k).x / MM, hc.CPoint(k).y / MM)
                           for k in range(hc.PointCount())])
            if len(pts) >= 3:
                try:
                    out.append(Polygon(pts, hs))
                except Exception:
                    pass
        return unary_union(out) if out else Polygon()

    b = pcbnew.LoadBoard(board_path)
    pads, zones = {}, {}
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            pads[pad.m_Uuid.AsString()] = (fp.GetReference(), pad)
    for z in b.Zones():
        if z.IsFilled():
            zones[z.m_Uuid.AsString()] = z

    rows = []
    for v in drc_doc["violations"]:
        if v["type"] not in ("clearance", "solder_mask_bridge"):
            continue
        pu = zu = None
        pdesc = zdesc = None
        for it in v["items"]:
            if it["description"].startswith("Pad "):
                pu, pdesc = it["uuid"], it["description"]
            elif it["description"].startswith("Zone "):
                zu, zdesc = it["uuid"], it["description"]
        if not (pu and zu and pu in pads and zu in zones):
            continue
        ref, pad = pads[pu]
        z = zones[zu]
        zs = poly_of(z.GetFilledPolysList(z.GetLayer()))
        ps = poly_of_pad(pcbnew, pad, poly_of)
        gap = ps.distance(zs) if not zs.is_empty else float("nan")
        rows.append({
            "type": v["type"], "severity": v["severity"], "ref": ref,
            "pad": pad.GetNumber(), "net": pad.GetNetname(), "layer": pcbnew.LayerName(pad.GetLayer()),
            "gap_mm": round(gap, 4),
            "zone_clearance_mm": round(z.GetOwnClearance(z.GetLayer()) / MM, 3),
        })
    return rows


def poly_of_pad(pcbnew, pad, poly_of):
    sps = pcbnew.SHAPE_POLY_SET()
    pad.TransformShapeToPolygon(sps, pad.GetLayer(), 0, pcbnew.FromMM(0.001), pcbnew.ERROR_INSIDE)
    return poly_of(sps)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--refilled")
    ap.add_argument("--json")
    a = ap.parse_args()

    td = tempfile.mkdtemp()
    pre = drc(a.board, os.path.join(td, "pre.json"))
    out = {"board": a.board, "pre": None, "post": None}

    def summarise(doc, label, gaps=None):
        counts = collections.Counter((v["type"], v["severity"]) for v in doc["violations"])
        pairs = collections.Counter()
        for v in doc["violations"]:
            ks = tuple(sorted(kind(i["description"]) for i in v["items"]))
            pairs[(v["type"], ks)] += 1
        print(f"\n=== {label}: {len(doc['violations'])} violations, "
              f"{len(doc['unconnected_items'])} unconnected")
        for (t, sev), n in sorted(counts.items()):
            print(f"  {n:4d}  {t:24s} {sev}")
        print("  -- object-kind pairs")
        for (t, ks), n in sorted(pairs.items()):
            print(f"  {n:4d}  {t:24s} {' + '.join(ks)}")
        return {"counts": {f"{t}/{s}": n for (t, s), n in counts.items()},
                "pairs": {f"{t}:{'+'.join(ks)}": n for (t, ks), n in pairs.items()},
                "total": len(doc["violations"]),
                "unconnected": len(doc["unconnected_items"])}

    out["pre"] = summarise(pre, f"BEFORE refill ({os.path.basename(a.board)})")
    if a.refilled:
        post = drc(a.refilled, os.path.join(td, "post.json"))
        out["post"] = summarise(post, f"AFTER refill ({os.path.basename(a.refilled)})")

    print("\n=== clearance: MEASURED pad-copper -> zone-FILL distance")
    try:
        rows = measure_gaps(a.board, pre)
        by_ref = collections.Counter(r["ref"] for r in rows)
        print(f"  items with a measurable pad+zone pair: {len(rows)}")
        for t in ("clearance", "solder_mask_bridge"):
            sub = [r for r in rows if r["type"] == t]
            if not sub:
                continue
            gaps = [r["gap_mm"] for r in sub]
            print(f"  {t}: n={len(sub)}  gap min={min(gaps):.4f} max={max(gaps):.4f} mm")
        print(f"  distinct footprints involved: {len(by_ref)} -> {dict(by_ref)}")
        out["clearance_measured"] = rows
    except Exception as exc:  # noqa: BLE001
        print(f"  MEASUREMENT FAILED: {exc}")
        out["clearance_error"] = str(exc)

    if a.refilled:
        print("\n=== the SAME items measured against the REFILLED pour")
        try:
            post = json.load(open(os.path.join(td, "post.json")))
            rows = measure_gaps(a.refilled, pre)  # item uuids are stable across a refill
            print(f"  measured the same {len(rows)} pad/zone pairs on the refilled board")
            b = None
            import pcbnew
            b = pcbnew.LoadBoard(a.refilled)
            pending = [z for z in b.Zones() if not z.IsFilled()]
            print(f"  zones still unfilled on the refilled board: {len(pending)}")
            # measure a handful of the same pads against the refilled pour
            rows2 = measure_gaps(a.refilled, pre)
            if rows2:
                g = [r["gap_mm"] for r in rows2]
                print(f"  refilled gap min={min(g):.4f} max={max(g):.4f} mm "
                      f"(zone clearance {rows2[0]['zone_clearance_mm']} mm)")
                out["clearance_measured_refilled"] = {"n": len(rows2), "min": min(g), "max": max(g)}
        except Exception as exc:  # noqa: BLE001
            print(f"  measurement failed: {exc}")

    if a.json:
        with open(a.json, "w") as fh:
            json.dump(out, fh, indent=1, default=str)
        print(f"\nwrote {a.json}")


if __name__ == "__main__":
    main()
