#!/usr/bin/env python3
"""Gate 2.5 screen for a .kicad_pcb  (S0 evidence generator, PCB-S0 t_7c65638f).

What it measures, and with what authority
-----------------------------------------
* pad-overlap pairs at a 0.2 mm margin, using the Gate 2.5 PAD-BOX proxy
  (footprint pad centres bbox +/- the largest pad half-extent).  This proxy is
  deliberately CONSERVATIVE - it uses one half-extent for the whole footprint,
  so it can overstate a conflict.  It is the SCREEN, and the plan's Gate S0
  number.  Reported also: the exact pad-rectangle overlaps ("true").
* `courtyards_overlap` and every other violation class, taken verbatim from
  `kicad-cli pcb drc --format json` - the AUTHORITY.  This file never
  re-implements a courtyard test.
* segments / vias / zones / footprints / pads-with-no-net, from the board text.

Geometry note: pad `(at ...)` inside a footprint is LOCAL; positions here are
converted to board coordinates with the footprint's own rotation, which is what
makes the pad-boxes comparable across revisions of the placement.

usage:
  python3 gate25_check.py <board.kicad_pcb> [--json out.json] [--margin 0.2]
  exit 0 = PASS (0 proxy pairs, courtyards_overlap 0, 0 segments, fp >= 10)
"""
from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


def s_expr_blocks(text: str, keyword: str):
    """Yield the raw text of every (keyword ...) block in text."""
    out = []
    i = 0
    tok = "(" + keyword
    while True:
        s = text.find(tok, i)
        if s < 0:
            break
        nxt = text[s + len(tok):s + len(tok) + 1]
        if nxt and (nxt.isalnum() or nxt == "_"):
            i = s + 1
            continue
        depth, j = 0, s
        while j < len(text):
            c = text[j]
            if c == '"':
                j += 1
                while j < len(text) and text[j] != '"':
                    if text[j] == "\\":
                        j += 1
                    j += 1
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append(text[s:j + 1])
        i = j + 1
    return out


def parse_board(path: str) -> dict:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    fps = []
    for blk in s_expr_blocks(text, "footprint "):
        ref = re.search(r'\(property "Reference" "([^"]+)"', blk)
        value = re.search(r'\(property "Value" "([^"]+)"', blk)
        libid = re.match(r'\(footprint "([^"]+)"', blk)
        at = re.search(r"\n\s*\(at ([-\d.]+) ([-\d.]+)(?:\s+([-\d.]+))?\)", blk)
        pads = []
        for pb in s_expr_blocks(blk, "pad "):
            pnum = re.match(r'\(pad\s+"?([^"\s]*)"?', pb)
            pat = re.search(r"\(at ([-\d.]+) ([-\d.]+)(?:\s+([-\d.]+))?\)", pb)
            psz = re.search(r"\(size ([-\d.]+) ([-\d.]+)\)", pb)
            pnet = re.search(r'\(net (\d+)\s*(?:"([^"]*)")?\)', pb)
            typ = re.search(r'\(pad\s+"?[^"\s]*"?\s+(\w+)\s+(\w+)', pb)
            drill = re.search(r"\(drill ([\d.]+)", pb)
            pads.append({
                "num": pnum.group(1) if pnum else "",
                "netnum": int(pnet.group(1)) if pnet else 0,
                "net": (pnet.group(2) or "") if pnet else "",
                "x": float(pat.group(1)) if pat else None,
                "y": float(pat.group(2)) if pat else None,
                "rot": float(pat.group(3) or 0) if pat else 0.0,
                "w": float(psz.group(1)) if psz else 0.0,
                "h": float(psz.group(2)) if psz else 0.0,
                "type": typ.group(1) if typ else "",
                "shape": typ.group(2) if typ else "",
                "drill": float(drill.group(1)) if drill else 0.0,
            })
        fps.append({
            "ref": ref.group(1) if ref else "?",
            "value": value.group(1) if value else "",
            "libid": libid.group(1) if libid else "?",
            "x": float(at.group(1)) if at else 0.0,
            "y": float(at.group(2)) if at else 0.0,
            "rot": float(at.group(3) or 0) if at else 0.0,
            "pads": pads,
        })
    return {
        "text": text,
        "fps": fps,
        "segments": len([b for b in s_expr_blocks(text, "segment") if re.match(r"\(segment[\s(]", b)]),
        "vias": len([b for b in s_expr_blocks(text, "via") if re.match(r"\(via[\s(]", b)]),
        "zones": len([b for b in s_expr_blocks(text, "zone") if re.match(r"\(zone[\s(]", b)]),
    }


def rot_pt(x: float, y: float, deg: float):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (x * c + y * s, -x * s + y * c)


def to_global(fp: dict) -> list:
    """Pad `at` is LOCAL to the footprint; return pads in board coordinates."""
    out = []
    for p in fp["pads"]:
        if p["x"] is None:
            continue
        dx, dy = rot_pt(p["x"], p["y"], fp["rot"])
        q = dict(p)
        q["gx"] = fp["x"] + dx
        q["gy"] = fp["y"] + dy
        out.append(q)
    return out


def pad_box(fp: dict):
    """Gate 2.5 proxy box in mm: pad centres bbox +/- largest pad half-extent."""
    g = to_global(fp)
    if not g:
        return None
    xs, ys = [p["gx"] for p in g], [p["gy"] for p in g]
    hx, hy = max(p["w"] for p in g) / 2.0, max(p["h"] for p in g) / 2.0
    return (min(xs) - hx, min(ys) - hy, max(xs) + hx, max(ys) + hy)


def pad_rects(fp: dict):
    """True pad copper rectangles in board mm, as (x0, y0, x1, y1, net)."""
    out = []
    for p in to_global(fp):
        if p["w"] == 0:
            continue
        hw, hh = p["w"] / 2.0, p["h"] / 2.0
        tot = (fp["rot"] + p["rot"]) % 360
        cs = [rot_pt(dx, dy, tot) for dx, dy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]
        gx = [p["gx"] + c[0] for c in cs]
        gy = [p["gy"] + c[1] for c in cs]
        out.append((min(gx), min(gy), max(gx), max(gy), p["net"]))
    return out


def overlaps(a, b, m) -> bool:
    return a[0] - m < b[2] + m and b[0] - m < a[2] + m and \
           a[1] - m < b[3] + m and b[1] - m < a[3] + m


def gate25(board: str, margin: float = 0.2, drc_out: str | None = None) -> dict:
    b = parse_board(board)
    fps = [f for f in b["fps"] if f["pads"]]
    boxes = {f["ref"]: pad_box(f) for f in fps}
    boxes = {k: v for k, v in boxes.items() if v is not None}
    refs = sorted(boxes, key=lambda r: (boxes[r][1], boxes[r][0]))
    proxy = []
    for i in range(len(refs)):
        for j in range(i + 1, len(refs)):
            a, c = boxes[refs[i]], boxes[refs[j]]
            if overlaps(a, c, margin):
                proxy.append([refs[i], refs[j],
                              round(max(a[0] - c[2], c[0] - a[2]), 3),
                              round(max(a[1] - c[3], c[1] - a[3]), 3)])
    exact = []
    for i in range(len(fps)):
        for j in range(i + 1, len(fps)):
            for pa in pad_rects(fps[i]):
                for pb in pad_rects(fps[j]):
                    if overlaps(pa, pb, margin):
                        exact.append([fps[i]["ref"], fps[j]["ref"], pa[4], pb[4]])
    nonet = [{"ref": f["ref"], "pad": p["num"], "pos": [p["x"], p["y"]],
              "size": [p["w"], p["h"]], "drill": p["drill"], "type": p["type"]}
             for f in fps for p in f["pads"] if p["netnum"] == 0]
    if drc_out is None:
        drc_out = str(Path(board).with_suffix("")) + "_drc.json"
    r = subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json",
                        "--output", drc_out, board], capture_output=True, text=True)
    drc = {"path": drc_out, "rc": r.returncode}
    if Path(drc_out).exists():
        d = json.loads(Path(drc_out).read_text())
        c = Counter(v.get("type", "?") for v in d.get("violations", []))
        drc.update({
            "violations_total": sum(c.values()),
            "by_type": dict(c),
            "courtyards_overlap": c.get("courtyards_overlap", 0),
            "shorting_items": c.get("shorting_items", 0),
            "clearance": c.get("clearance", 0),
            "unconnected": len(d.get("unconnected_items", [])),
        })
    res = {
        "board": board,
        "footprints": len(b["fps"]),
        "pads": sum(len(f["pads"]) for f in b["fps"]),
        "segments": b["segments"],
        "vias": b["vias"],
        "zones": b["zones"],
        "margin_mm": margin,
        "pads_with_no_net": len(nonet),
        "no_net_pads": nonet,
        "pad_overlap_pairs_0.2mm": len(proxy),
        "pad_overlap_examples": proxy[:8],
        "exact_pad_overlap_pairs_0.2mm": len(exact),
        "exact_pad_overlap_examples": exact[:8],
        "courtyards_overlap": drc.get("courtyards_overlap"),
        "drc": drc,
    }
    res["placement_gate"] = "PASS" if (
        len(proxy) == 0 and drc.get("courtyards_overlap") == 0
        and b["segments"] == 0 and len(b["fps"]) >= 10) else "FAIL"
    return res


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    board = args[0]
    out_json = args[args.index("--json") + 1] if "--json" in args else None
    res = gate25(board)
    txt = json.dumps(res, indent=2)
    if out_json:
        Path(out_json).write_text(txt)
        summary = dict(res)
        summary.pop("no_net_pads", None)
        print(json.dumps(summary, indent=2))
    else:
        print(txt)
    return 0 if res["placement_gate"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
