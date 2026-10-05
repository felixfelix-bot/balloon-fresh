#!/usr/bin/env python3
"""Independent DRC-inspection helper for the V2-ADC board (kanban t_99cd30c5).

Read-only with respect to the board. Reproduces, from artefacts only:

  1. structural counts parsed straight out of the .kicad_pcb s-expression
  2. the DRC violation breakdown and the unconnected-item list per net,
     classified against the critical-net list in
     docs/coordination/PCB-DRC-CONSULTANT-STRATEGY.md
  3. the four quality gates of the verification card, PASS/FAIL
  4. pad-level geometry for the pads involved in reported shorting_items, so
     that placement-induced shorts can be told apart from routing shorts

Usage:
    kicad-cli pcb drc --format json --output /tmp/verify_drc.json \
        output/v2_adc_v3_clean.kicad_pcb
    python3 verify_v2adc_inspection.py output/v2_adc_v3_clean.kicad_pcb \
        /tmp/verify_drc.json [summary.json]
"""
import collections
import json
import math
import re
import sys

# Critical nets per PCB-DRC-CONSULTANT-STRATEGY.md Q5 / card t_4b22db97 Gate 2
CRITICAL = [
    "3V3", "GND", "SPI_MOSI", "SPI_MISO", "SPI_SCK", "SPI_NSS",
    "LR2021_RST", "LR2021_BUSY", "LR2021_DIO9",
    "GPS_RX", "VCAP", "SOLAR_IN",
]

STRUCT_TOKENS = ["segment", "arc", "via", "zone", "footprint", "pad",
                 "gr_line", "gr_poly", "gr_rect", "group", "net"]


def count_tok(src, tok):
    return len(re.findall(r"^\s*\(" + re.escape(tok) + r"[\s)]", src, re.M))


def s_expr_blocks(src, opener):
    """Yield every balanced s-expression block that starts with `opener`."""
    i = 0
    while True:
        i = src.find(opener, i)
        if i < 0:
            return
        depth = 0
        j = i
        while j < len(src):
            if src[j] == "(":
                depth += 1
            elif src[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        yield src[i:j + 1]
        i = j + 1


def parse_pads(src):
    """Absolute-position + size for every pad, honouring footprint/pad rotation."""
    pads = []
    for blk in s_expr_blocks(src, "\n\t(footprint "):
        mref = re.search(r'\(property "Reference" "([^"]+)"', blk)
        if not mref:
            continue
        ref = mref.group(1)
        mfp = re.search(r"^\s*\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)", blk, re.M)
        fx, fy = float(mfp.group(1)), float(mfp.group(2))
        fang = float(mfp.group(3)) if mfp.group(3) else 0.0
        for pblk in s_expr_blocks(blk, "\n\t\t(pad "):
            mpn = re.search(r'\(pad "([^"]*)"', pblk)
            mpa = re.search(r"\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)", pblk)
            mps = re.search(r"\(size ([-\d.]+) ([-\d.]+)\)", pblk)
            if not (mpn and mpa and mps):
                continue
            pnet = re.search(r'\(net \d+ "([^"]*)"\)', pblk)
            mshape = re.search(r'\(pad "[^"]*" (\S+) (\S+)', pblk)
            pang = float(mpa.group(3)) if mpa.group(3) else 0.0
            rad = math.radians(fang)
            px, py = float(mpa.group(1)), float(mpa.group(2))
            pads.append({
                "ref": ref, "pad": mpn.group(1),
                "net": pnet.group(1) if pnet else "",
                "x": fx + px * math.cos(rad) - py * math.sin(rad),
                "y": fy + px * math.sin(rad) + py * math.cos(rad),
                "w": float(mps.group(1)), "h": float(mps.group(2)),
                "angle": (fang + pang) % 180.0,
                "shape": mshape.group(1) if mshape else "",
            })
    return pads


def pad_extent(p):
    """Axis-aligned copper extents of a 0/90-degree pad; None if rotated."""
    if abs(p["angle"]) > 1e-9 and abs(p["angle"] - 90.0) > 1e-9:
        return None
    w, h = (p["w"], p["h"]) if abs(p["angle"]) < 1e-9 else (p["h"], p["w"])
    return (p["x"] - w / 2, p["y"] - h / 2, p["x"] + w / 2, p["y"] + h / 2)


def overlap_area(a, b):
    ea, eb = pad_extent(a), pad_extent(b)
    if not ea or not eb:
        return None
    dx = min(ea[2], eb[2]) - max(ea[0], eb[0])
    dy = min(ea[3], eb[3]) - max(ea[1], eb[1])
    if dx <= 0 or dy <= 0:
        return 0.0
    return round(dx * dy, 4)


def describe(desc):
    m = re.search(r"\[([^\]]+)\]", desc)
    return m.group(1) if m else ""


def main():
    board = sys.argv[1] if len(sys.argv) > 1 else "output/v2_adc_v3_clean.kicad_pcb"
    drc_json = sys.argv[2] if len(sys.argv) > 2 else "/tmp/verify_drc.json"
    out_path = sys.argv[3] if len(sys.argv) > 3 else None

    src = open(board, encoding="utf-8").read()
    drc = json.load(open(drc_json, encoding="utf-8"))
    pads = parse_pads(src)
    by_ref_pad = {(p["ref"], p["pad"]): p for p in pads}

    violations = drc.get("violations", [])
    unconnected = drc.get("unconnected_items", [])

    per_net = collections.Counter()
    unconnected_pairs = []
    for item in unconnected:
        descs = [it.get("description", "") for it in item.get("items", [])]
        nets = {n for n in (describe(d) for d in descs) if n}
        for n in nets:
            per_net[n] += 1
        unconnected_pairs.append(descs)

    shorts, shorts_detail = 0, []
    for v in violations:
        if v["type"] != "shorting_items":
            continue
        shorts += 1
        refs = []
        for it in v.get("items", []):
            m = re.match(r"Pad ([^ ]+) \[([^\]]+)\] of (\S+)", it.get("description", ""))
            if m:
                refs.append((m.group(3), m.group(1), m.group(2)))
        row = {"description": v["description"], "items": refs}
        if len(refs) == 2:
            a = by_ref_pad.get((refs[0][0], refs[0][1]))
            b = by_ref_pad.get((refs[1][0], refs[1][1]))
            if a and b:
                row["c2c_mm"] = round(math.hypot(a["x"] - b["x"], a["y"] - b["y"]), 3)
                row["overlap_area_mm2"] = overlap_area(a, b)
                row["pad_sizes"] = [f"{a['w']}x{a['h']}", f"{b['w']}x{b['h']}"]
        shorts_detail.append(row)

    crit_un = sorted(n for n in CRITICAL if per_net.get(n))
    crit_ok = sorted(n for n in CRITICAL if not per_net.get(n))
    noncrit_un = sorted(n for n in per_net if n not in CRITICAL)

    summary = {
        "board": board,
        "drc_json": drc_json,
        "kicad_version": drc.get("kicad_version"),
        "drc_run_date": drc.get("date"),
        "structure": {t: count_tok(src, t) for t in STRUCT_TOKENS},
        "violations_total": len(violations),
        "violations_by_type": dict(collections.Counter(v["type"] for v in violations)),
        "violations_by_severity": dict(collections.Counter(v["severity"] for v in violations)),
        "shorting_items_detail": shorts_detail,
        "unconnected_total": len(unconnected),
        "unconnected_by_net": dict(per_net),
        "critical_nets_total": len(CRITICAL),
        "critical_nets_connected": crit_ok,
        "critical_nets_unconnected": crit_un,
        "noncritical_unconnected_nets": noncrit_un,
        "gates": {
            "gate1_zero_shorting_items": "PASS" if shorts == 0 else "FAIL",
            "gate2_critical_nets_connected": "PASS" if not crit_un else "FAIL",
            "gate3_no_zones": "PASS" if count_tok(src, "zone") == 0 else "FAIL",
        },
        "checks": {
            "copper_edge_clearance": sum(1 for v in violations if v["type"] == "copper_edge_clearance"),
            "tracks_crossing": sum(1 for v in violations if v["type"] == "tracks_crossing"),
            "solder_mask_bridge": sum(1 for v in violations if v["type"] == "solder_mask_bridge"),
            "noncritical_unconnected_max_2": "PASS" if len(noncrit_un) <= 2 else "FAIL",
        },
    }
    text = json.dumps(summary, indent=2, sort_keys=True)
    print(text)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"\n[written] {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
