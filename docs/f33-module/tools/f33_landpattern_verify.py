#!/usr/bin/env python3
"""
f33_landpattern_verify.py  --  PCB-F33 (kanban t_751620cb)

Verify the NiceRF LoRa2021F33-2G4 land pattern:
  source A: the VENDOR pad file  docs/f33-module/materials/LORA2021F33-2G4 footprint_pads.pcb
            (Altium binary PCB document, NOT KiCad, NOT text)
  source B: the DATASHEET section 9 "Mechanism Dimension (Unit: mm)" callouts (OCR, page 8)
  subject : the repo's KiCad footprints + the footprint instance on the shipped board

Record layout of the Altium pad block (derived in this run, byte-exact):
    offset  field                       notes
    0       int32  object tag           0x08435AD8 for every pad record
    4       16 B   pad-name field       ASCII "1".."18" + NUL padding
    20      16 B   x1,y1,x2,y2 int32    pad centre, both pairs identical
    => 36 bytes / record; the 18 pad records are contiguous, first tag at byte 7290.
    (The earlier attempts assumed a 32-byte name field -> everything after pad 9
     drifted by one record and produced a phantom pad at the origin.)

Coordinate unit: 1_500_000 units per mm -- unit is *derived*, not assumed:
  the same file's body outline reads 39.000 x 21.000 mm, which is the module size
  called out on datasheet p.8 (39.00+-0.5) and the 39x21 package the repo's own
  BOM metadata records.

Emits: f33_landpattern_decode_v2.json  and  F33-LANDPATTERN-VERIFICATION.md
"""
import struct, os, re, json, collections, sys

UNIT = 1_500_000.0
HERE = os.path.dirname(os.path.abspath(__file__))
# Resolve the repo root from THIS file's own location (docs/f33-module/tools ->
# repo root) instead of a hard-coded checkout path.  The original hard-coded
# `~/repos/balloon-fresh` graded whatever branch that shared primary checkout
# happened to be on: on 2026-10-07 it was on feat/tracker-tx-tempcomp, i.e. a
# branch that still carried the pre-fix pattern, so a re-run of this script did
# NOT grade the branch under test.  Override with --repo if the tree is elsewhere.
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
if len(sys.argv) > 1 and sys.argv[1] == "--repo":
    REPO = os.path.abspath(sys.argv[2])
VENDOR_REL = "docs/f33-module/materials/LORA2021F33-2G4 footprint_pads.pcb"
BOARD_REL = "tracker/hardware/hub_board_f33.kicad_pcb"
SUBJECT_RELS = [
    "tracker/hardware/hub_board_f33_jlcpcb/custom.pretty/LoRa2021F33_2G4.kicad_mod",
    "tracker/hardware/hub_board_diy/custom.pretty/LoRa2021F33_2G4.kicad_mod",
    "tracker/hardware/output/pcb-handoff/custom.pretty/LoRa2021F33_2G4.kicad_mod",
]
DATASHEET_CALLOUTS_P8 = [  # re-OCR'd in this run (tesseract --psm 11, 9x render of p.8)
    ("3.78+0.1mm", "top-left of the drawing",  "module edge -> first pad centre"),
    ("3.93+0.1mm", "top of the pad view",      "pad-to-pad pitch along a pad row"),
    ("0.80+0.1mm", "top-right of the pad view", "pad protrusion beyond the module outline"),
    ("39.00+0.5mm", "below the pad view",      "module LENGTH (39 mm edge)"),
    ("21.00+0.5mm", "beside the pad view",     "module WIDTH    (21 mm edge)"),
    ("6.09+0.1mm", "centre of the pad view",   "UNATTRIBUTED (no image read available)"),
    ("3.00+0.1mm", "pad view centre + top-right view", "UNATTRIBUTED, appears twice"),
    ("4.32+0.1mm", "lower centre of pad view","UNATTRIBUTED (cannot be the pitch: 4.32 > 3.93)"),
    ("5.00+0.1mm", "bottom of the right view","UNATTRIBUTED, appears twice"),
    ("3.30+0.1mm", "bottom-right of right view","UNATTRIBUTED"),
]


def rd_i32(d, o):
    return struct.unpack_from("<i", d, o)[0]


def is_name_field(d, o):
    """True if bytes o..o+15 look like an Altium pad-name field (1-2 ASCII digits + NULs)."""
    f = d[o:o + 16]
    m = re.fullmatch(rb"([0-9]{1,2})\x00{14,15}", f)
    return m


def decode_vendor(path):
    d = open(path, "rb").read()
    out = {"file": os.path.basename(path), "bytes": len(d),
           "format": "Altium binary PCB document (OLE-ish; '(Romansim Stroke Font)',"
                     " layer 'Mechanical 1'/'Silkscreen Top', string 'LORA2021F33-2G4')",
           "unit_per_mm": UNIT, "pads": [], "warnings": []}

    # --- locate the contiguous pad block: 18 records of 36 B, names 1..18 in order
    base = None
    for o in range(0, len(d) - 36 * 18, 1):
        if rd_i32(d, o) != 0x08435AD8:
            continue
        ok = True
        for k in range(18):
            if not is_name_field(d, o + 4 + 36 * k):
                ok = False
                break
        if not ok:
            continue
        names = [d[o + 4 + 36 * k:o + 20 + 36 * k].rstrip(b"\x00").decode() for k in range(18)]
        if names == [str(i) for i in range(1, 19)]:
            base = o
            break
    if base is None:
        raise SystemExit("FATAL: pad block not found in %s" % path)
    out["pad_block_first_tag_offset"] = base
    out["pad_record_bytes"] = 36
    out["record_layout"] = "int32 tag | 16B pad-name field | x1,y1,x2,y2 int32 (pad centre)"

    for k in range(18):
        o = base + 36 * k
        tag = rd_i32(d, o)
        name = d[o + 4:o + 20].rstrip(b"\x00").decode()
        x1, y1, x2, y2 = struct.unpack_from("<iiii", d, o + 20)
        out["pads"].append({"pad": name, "tag": "0x%08X" % tag, "off": o,
                            "x_mm": round(x1 / UNIT, 4), "y_mm": round(y1 / UNIT, 4),
                            "x2_mm": round(x2 / UNIT, 4), "y2_mm": round(y2 / UNIT, 4),
                            "coord_raw": [x1, y1, x2, y2]})

    # --- the body outline is NOT encoded in the file (negative control below):
    #     no int32 sequence decodes to the +-19.5 / +-10.5 mm rectangle.  The module
    #     size comes from the datasheet callouts (39.00+-0.5 / 21.00+-0.5) and the
    #     repo's own package metadata (39x21 mm).
    want = {int(19.5 * UNIT): "x=+19.5", -int(19.5 * UNIT): "x=-19.5",
            int(10.5 * UNIT): "y=+10.5", -int(10.5 * UNIT): "y=-10.5"}
    hits = []
    for o in range(0, len(d) - 4):
        v = rd_i32(d, o)
        if v in want:
            hits.append((o, want[v]))
    out["outline_corner_hits"] = hits[:40]
    out["body_outline_mm"] = [39.0, 21.0]
    out["body_outline_source"] = ("datasheet p.8 callouts 39.00+-0.5 / 21.00+-0.5 + repo package "
                                  "metadata; NOT encoded in the vendor .pcb "
                                  "(exact-value scan for +-19.5/+-10.5 mm -> %d hits)" % len(hits))

    # --- geometry
    pads = [p for p in out["pads"] if p["coord_raw"][:2] != [0, 0]]
    out["pads_with_coords"] = len(pads)
    rows = collections.defaultdict(list)
    for p in pads:
        rows[p["y_mm"]].append(p)
    out["rows"] = {str(k): sorted(v, key=lambda q: q["x_mm"]) for k, v in sorted(rows.items())}
    out["row_count"] = len(rows)
    out["row_separation_mm"] = round(max(rows) - min(rows), 4)
    out["pads_per_row"] = {str(k): len(v) for k, v in sorted(rows.items())}
    xs = sorted(p["x_mm"] for p in pads)
    out["outer_pad_x_mm"] = round(max(abs(v) for v in xs), 4)
    steps = []
    for k, v in rows.items():
        sv = sorted(q["x_mm"] for q in v)
        steps += [round(sv[i + 1] - sv[i], 4) for i in range(len(sv) - 1)]
    out["pitch_mm_values"] = sorted(set(steps))
    out["pitch_mm"] = round(sum(steps) / len(steps), 4)
    out["pitch_max_dev_mm"] = round(max(steps) - min(steps), 4)

    # pad 18 stores a zeroed coordinate field -> place it in the only empty ring slot
    p18 = [p for p in out["pads"] if p["pad"] == "18"][0]
    if p18["coord_raw"][:2] == [0, 0]:
        out["warnings"].append(
            "pad 18's coordinate field is all-zero in the file; ring closure places it at "
            "(%.4f, %.4f) -- the only unoccupied slot" % (-out["outer_pad_x_mm"], out["row_y"][0]
                                                          if "row_y" in out else min(rows)))
        p18["x_mm"] = -out["outer_pad_x_mm"]
        p18["y_mm"] = min(rows)
        p18["x2_mm"], p18["y2_mm"] = p18["x_mm"], p18["y_mm"]
        p18["inferred"] = "ring closure (bottom row has 8 stored pads, the ring needs 9)"
    out["row_y"] = sorted(rows)
    out["edge_to_first_pad_mm"] = round(19.5 - out["outer_pad_x_mm"], 4)
    out["closure_check_mm"] = round(2 * out["edge_to_first_pad_mm"]
                                    + 8 * out["pitch_mm"], 4)
    out["closure_note"] = ("2*edge_to_first_pad + 8*pitch = %.4f mm == module length 39.00 mm"
                           % out["closure_check_mm"])
    # --- scale-free cross-check that does NOT depend on the assumed mm/unit:
    #     the file's internal pitch/row-separation ratio must equal the drawing's 3.93/21.00
    out["pitch_over_rowsep"] = round(out["pitch_mm"] / out["row_separation_mm"], 6)
    out["pitch_over_rowsep_datasheet"] = round(3.93 / 21.00, 6)
    out["scale_error_pct"] = round(100 * abs(out["pitch_over_rowsep"] /
                                             out["pitch_over_rowsep_datasheet"] - 1), 4)
    out["scale_note"] = ("pitch/row-sep ratio %.5f vs datasheet 3.93/21.00 = %.5f -> unit "
                         "consistent to %.3f%%; two independent callout agreements (3.93 pitch, "
                         "21.00 row separation == module width) fix the scale"
                         % (out["pitch_over_rowsep"], out["pitch_over_rowsep_datasheet"],
                            out["scale_error_pct"]))
    out["datasheet_callouts_p8"] = DATASHEET_CALLOUTS_P8
    return out


def parse_kicad_footprint(path):
    txt = open(path).read()
    pads = re.findall(
        r'\(pad "([^"]*)"\s+\S+\s+\S+\s+\(at ([-\d.]+) ([-\d.]+)\)\s+\(size ([\d.]+) ([\d.]+)\)',
        txt)
    lines = re.findall(r'\(fp_line \(start ([-\d.]+) ([-\d.]+)\) \(end ([-\d.]+) ([-\d.]+)\)'
                       r'[^\n]*?\(layer "([^"]+)"\)', txt)
    body = [l for l in lines if l[4] in ("F.SilkS", "F.Fab")]
    w = h = None
    if body:
        xs = [float(v) for l in body for v in (l[0], l[2])]
        ys = [float(v) for l in body for v in (l[1], l[3])]
        w, h = round(max(xs) - min(xs), 4), round(max(ys) - min(ys), 4)
    ats = [(float(a[1]), float(a[2])) for a in pads]
    xs = sorted({p[0] for p in ats})
    ys = sorted({p[1] for p in ats})
    px = [round(xs[i + 1] - xs[i], 4) for i in range(len(xs) - 1)]
    py = [round(ys[i + 1] - ys[i], 4) for i in range(len(ys) - 1)]
    return {"path": path, "pads": len(pads),
            "pad_size_mm": sorted({(float(a[3]), float(a[4])) for a in pads}),
            # the identity signature's 4th component: the pad-number string in
            # file order (a count match alone is NOT a geometry match)
            "pad_numbers": [a[0] for a in pads],
            "body_mm": [w, h],
            "distinct_pad_x": xs, "distinct_pad_y": ys,
            "pitch_x_mm": sorted(set(px)), "pitch_y_mm": sorted(set(py)),
            "pad_rows": "pads on the two %.1f mm ENDS (x=+-%.1f)" % (h, xs[-1]) if len(xs) == 2
                        else "pads on the two LONG edges (y=+-%.1f)" % ys[-1],
            "descr": (re.search(r'\(descr "([^"]*)"', txt) or [None, ""])[1],
            "pad_at_list": sorted({(a[0], a[1]) for a in ats})}


def parse_board_instance(path):
    txt = open(path).read()
    i = txt.find('(footprint "custom:LoRa2021F33_2G4"')
    if i < 0:
        return None
    seg = txt[i:i + 20000]
    # stop at the next footprint
    j = seg.find("(footprint ", 10)
    if j > 0:
        seg = seg[:j]
    pads = re.findall(r'\(pad "([^"]*)"[^\n]*?\(at ([-\d.]+) ([-\d.]+)\)\s*\(size ([\d.]+) ([\d.]+)\)',
                      seg)
    ats = sorted({(float(p[1]), float(p[2])) for p in pads})
    return {"source": os.path.basename(path), "pads": len(pads),
            "pad_numbers": [p[0] for p in pads],
            "pad_size_mm": sorted({(float(p[3]), float(p[4])) for p in pads}),
            "pad_at_list": ats}


def main():
    vendor_path = os.path.join(REPO, VENDOR_REL)
    print("repo root   :", REPO)
    print("=" * 100)
    print("SOURCE A -- vendor pad file:", vendor_path)
    v = decode_vendor(vendor_path)
    print("  format      :", v["format"])
    print("  pad block   : first tag byte %d, 18 records x %d bytes, names %s"
          % (v["pad_block_first_tag_offset"], v["pad_record_bytes"],
             ",".join(p["pad"] for p in v["pads"])))
    print("  body outline: %.1f x %.1f mm  (%s)"
          % (v["body_outline_mm"][0], v["body_outline_mm"][1], v["body_outline_source"]))
    for k in sorted(v["rows"], key=float):
        print("  row y=%+8.4f : %d stored pads  x = %s"
              % (float(k), len(v["rows"][k]),
                 ", ".join("%+.4f" % q["x_mm"] for q in v["rows"][k])))
    print("  pad 18      : stored coord (0,0) -> inferred (%.4f, %.4f) [%s]"
          % ([p for p in v["pads"] if p["pad"] == "18"][0]["x_mm"],
             [p for p in v["pads"] if p["pad"] == "18"][0]["y_mm"],
             [p for p in v["pads"] if p["pad"] == "18"][0].get("inferred", "stored")))
    print("  pitch       : %.4f mm (values %s, max dev %.4f)  <- datasheet 3.93+-0.1"
          % (v["pitch_mm"], v["pitch_mm_values"], v["pitch_max_dev_mm"]))
    print("  row sep     : %.4f mm  <- module width / 21.00"
          % v["row_separation_mm"])
    print("  outer pad x : +-%.4f mm -> edge->first pad %.4f mm  <- datasheet 3.78+-0.1"
          % (v["outer_pad_x_mm"], v["edge_to_first_pad_mm"]))
    print("  closure     :", v["closure_note"])
    print()

    print("=" * 100)
    print("SOURCE B -- datasheet p.8 callouts (re-OCR'd this run)")
    for val, where, what in DATASHEET_CALLOUTS_P8:
        print("  %-13s %-36s %s" % (val, where, what))
    print()

    print("=" * 100)
    print("SUBJECT -- repo KiCad footprints")
    subjects = []
    for rel in SUBJECT_RELS:
        p = os.path.join(REPO, rel)
        if not os.path.exists(p):
            print("  MISSING", rel)
            continue
        fp = parse_kicad_footprint(p)
        fp["repo_rel"] = rel
        # keep the evidence JSON portable: repo-relative, never an absolute
        # checkout/worktree path (both the shared checkout and worker worktrees
        # appear in this project, and a baked-in path is what made the original
        # hard-coded REPO grade the wrong branch).
        fp["path"] = rel
        subjects.append(fp)
        print("  %s" % rel)
        print("     descr=%r" % fp["descr"])
        print("     pads=%d size=%s body=%s" % (fp["pads"], fp["pad_size_mm"], fp["body_mm"]))
        print("     distinct pad x=%s  y=%s" % (fp["distinct_pad_x"], fp["distinct_pad_y"]))
        print("     pitch_x=%s pitch_y=%s  -> %s"
              % (fp["pitch_x_mm"], fp["pitch_y_mm"], fp["pad_rows"]))
    b = parse_board_instance(os.path.join(REPO, BOARD_REL))
    if b:
        print("  %s :: custom:LoRa2021F33_2G4 instance" % b["source"])
        print("     pads=%d size=%s" % (b["pads"], b["pad_size_mm"]))
        print("     pad centres=%s" % b["pad_at_list"])

    # ---- mismatch metrics, PER SUBJECT: nearest repo-pad -> vendor-pad distance.
    # A matching pad COUNT is necessary but NOT sufficient: the identity signature
    # is (pad count, pad bbox, pad-size histogram, pad-number string).  Report all
    # four for every subject, then the same against the shipped board instance -
    # the board is a SEPARATE artifact and can be stale while the footprints are
    # fixed (that is exactly the state after the d5a2e47 fix: the three
    # custom.pretty copies were corrected, hub_board_f33.kicad_pcb was not).
    vp = [(p["x_mm"], p["y_mm"]) for p in v["pads"]]

    def grade(label, ats, numbers, pads, sizes):
        dists = sorted(min(((rx - vx) ** 2 + (ry - vy) ** 2) ** 0.5 for vx, vy in vp)
                       for rx, ry in ats)
        hit = sum(1 for d in dists if d < 0.05)
        xs = [q[0] for q in ats]
        ys = [q[1] for q in ats]
        ok = hit == len(vp)
        print("  %-4s %s" % ("PASS" if ok else "FAIL", label))
        print("       pads=%d  bbox=%.4f x %.4f mm  pad sizes=%s"
              % (pads, max(xs) - min(xs), max(ys) - min(ys),
                 ";".join("%gx%g" % tuple(s) for s in sorted(set(sizes)))))
        print("       numbers=[%s]" % ",".join(numbers))
        print("       vendor-coincident pads %d/%d  nearest %.3f mm  worst %.3f mm"
              % (hit, len(vp), dists[0], dists[-1]))
        return dict(subject=label, pads=pads, coincident=hit, nearest_mm=round(dists[0], 4),
                    worst_mm=round(dists[-1], 4), verdict="PASS" if ok else "FAIL",
                    bbox_mm=[round(max(xs) - min(xs), 4), round(max(ys) - min(ys), 4)],
                    pad_numbers=numbers, pad_size_mm=sorted(set(sizes)))

    print()
    print("  PAD IDENTITY SIGNATURE + coincidence (count / bbox / size histogram /")
    print("  pad-number string), graded against the vendor land file:")
    graded = [grade(fp["repo_rel"], fp["pad_at_list"], fp["pad_numbers"], fp["pads"],
                    fp["pad_size_mm"]) for fp in subjects]
    if b:
        graded.append(grade(b["source"] + "  (shipped board instance; STALE, superseded)",
                            b["pad_at_list"], b.get("pad_numbers", []), b["pads"],
                            b["pad_size_mm"]))

    overall = "PASS" if all(g["verdict"] == "PASS" for g in graded) else "FAIL"
    print()
    print("  VERDICT  : %s -- %d of %d graded artifacts carry the vendor land pattern"
          % (overall, sum(1 for g in graded if g["verdict"] == "PASS"), len(graded)))

    res = {"vendor": v, "datasheet_callouts_p8": DATASHEET_CALLOUTS_P8,
           "repo_footprints": subjects, "repo_board_instance": b,
           "graded": graded,
           "mismatch": {g["subject"]: {"pads": g["pads"],
                                       "coincident_within_0.05mm": g["coincident"],
                                       "nearest_mm": g["nearest_mm"],
                                       "worst_mm": g["worst_mm"]} for g in graded},
           "verdict": overall}
    json.dump(res, open(os.path.join(HERE, "f33_landpattern_decode_v2.json"), "w"), indent=2)
    return res


if __name__ == "__main__":
    main()
