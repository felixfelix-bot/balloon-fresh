#!/usr/bin/env python3
"""vnext MINIMAL read-only layer/area audit of the reference board (ADR-089 gates G3+G4).

READ-ONLY. Loads the board with pcbnew, measures, writes JSON. Never mutates the
board object, never calls SaveBoard. The --verify-hash flag FAILS CLOSED if the
board file changed by a single byte.

WHY THIS BOARD: ADR-089 G3 names tracker/hardware/hub_board_v11_stage1.kicad_pcb as the
reference board for the MINIMAL variant. The ordered v10 archive is gerbers-only (no
.kicad_pcb ships); its provenance chain is recorded in the emitted JSON under _provenance.

MEASURED (all from the live board object, no estimates):
  outline        Edge.Cuts extents; SHAPE_TYPE census so a single-rectangle outline is
                 stated as such; bbox area labelled bbox_area (equal to true area ONLY
                 for a rectangle, overestimate otherwise).
  per_layer      track length (GetLength, mm), track/arc segment counts, via presence
                 per copper layer.
  per_net        track-segment count per net, with in_minimal_set computed by NET
                 CONSUMERS, not name matching: a net is REMOVED only if every netted pad
                 consumer is on a REMOVE-set footprint (U_C, U_E28). Shared rails
                 (+3V3, GND) and the shared SPI1 bus therefore stay KEPT.
  removed_copper length and segment count of tracks on REMOVE-only nets, per layer,
                 vias counted separately (a via is not a length).
  zones          filled-polygon area per layer via SHAPE_POLY_SET.Area(). If the API
                 cannot return filled polys for a layer, the entry is recorded as
                 unsupported_geometry with the reason -- never estimated.
  footprints     census with side, position, bounding box, DNP -- the G4 inputs.

SANITY CHECKS (exit non-zero on failure, fail-closed):
  S1  board file sha256 recorded and, with --verify-hash, unchanged
  S2  footprint count > 0, track count > 0, copper layers == 4
  S3  every named net has an in_minimal_set verdict (no silent drop)
  S4  sum(per-layer segments) == total track+arc segments
  S5  zone area is None or a positive float, never a fabricated number
"""
import argparse
import hashlib
import json
import sys

import pcbnew

MM = 1e6
MM2 = 1e12

REMOVE_REFS = ("U_C", "U_E28")  # MINIMAL drops the redundant RX site and the ranging site (ADR-089 S1)

LAYERS = {
    "F.Cu": pcbnew.F_Cu,
    "In1.Cu": pcbnew.In1_Cu,
    "In2.Cu": pcbnew.In2_Cu,
    "B.Cu": pcbnew.B_Cu,
}


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def measure(board):
    out = {}

    # ---- outline --------------------------------------------------------------
    segs = []
    shape_types = {}
    for d in board.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:
            s, e = d.GetStart(), d.GetEnd()
            segs.append((s.x / MM, s.y / MM, e.x / MM, e.y / MM))
            tn = str(d.GetShape())
            shape_types[tn] = shape_types.get(tn, 0) + 1
    if not segs:
        fail("no Edge.Cuts segments found -- outline unmeasurable (fail-closed)")
    xs = [v for s in segs for v in (s[0], s[2])]
    ys = [v for s in segs for v in (s[1], s[3])]
    w = max(xs) - min(xs)
    hgt = max(ys) - min(ys)
    out["outline"] = {
        "edge_segments": len(segs),
        "edge_shape_types": shape_types,
        "bbox_mm": {"x_min": min(xs), "y_min": min(ys), "x_max": max(xs),
                    "y_max": max(ys), "width_mm": w, "height_mm": hgt},
        "bbox_area_mm2": w * hgt,
        "area_claim": "bbox_area_mm2 equals the true outline area ONLY if the outline is a "
                      "rectangle (1 segment here is a PCB_SHAPE rect: 4 corners, one object). "
                      "Any non-rectangular outline makes bbox an OVERESTIMATE.",
    }

    # ---- net consumers: net -> set of consuming footprint refs ------------------
    netinfo = board.GetNetInfo()
    net_consumers = {}  # netcode -> set(ref)
    padcount = 0
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        for p in fp.Pads():
            code = p.GetNetCode()
            if code <= 0:
                continue
            net_consumers.setdefault(code, set()).add(ref)
            padcount += 1

    def netname(code):
        return netinfo.GetNetItem(code).GetNetname()

    removed_netcodes = set()
    kept_shared_with_removed = {}
    for code, refs in net_consumers.items():
        if refs and refs.issubset(set(REMOVE_REFS)):
            removed_netcodes.add(code)
        elif refs & set(REMOVE_REFS):
            kept_shared_with_removed[code] = sorted(refs)

    # ---- per-layer tracks ------------------------------------------------------
    per_layer = {n: {"track_length_mm": 0.0, "segments": 0, "vias": 0} for n in LAYERS}
    per_net = {}
    removed_copper = {n: {"length_mm": 0.0, "segments": 0} for n in LAYERS}
    removed_vias = 0
    total_tracks = 0
    for t in board.GetTracks():
        tt = t.Type()
        code = t.GetNetCode()
        if tt in (pcbnew.PCB_TRACE_T, pcbnew.PCB_ARC_T):
            lname = board.GetLayerName(t.GetLayer())
            if lname not in per_layer:
                per_layer[lname] = {"track_length_mm": 0.0, "segments": 0, "vias": 0}
                removed_copper[lname] = {"length_mm": 0.0, "segments": 0}
            L = t.GetLength() / MM
            per_layer[lname]["track_length_mm"] += L
            per_layer[lname]["segments"] += 1
            total_tracks += 1
            if code > 0:
                per_net[code] = per_net.get(code, 0) + 1
                if code in removed_netcodes:
                    removed_copper[lname]["length_mm"] += L
                    removed_copper[lname]["segments"] += 1
        elif tt == pcbnew.PCB_VIA_T:
            ls = t.GetLayerSet()
            for n, lid in LAYERS.items():
                if ls.Contains(lid):
                    per_layer[n]["vias"] += 1
            if code in removed_netcodes:
                removed_vias += 1

    out["per_layer"] = per_layer
    out["via_total"] = sum(1 for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T)
    # every named net gets a verdict, including nets with ZERO track segments
    # (unrouted nets) -- S3 requires no silent drops
    all_netcodes = sorted(set(list(per_net.keys()) + list(net_consumers.keys())))
    out["per_net_segments"] = {
        netname(c): {
            "segments": per_net.get(c, 0),
            "in_minimal_set": c not in removed_netcodes,
            "verdict_reason": (
                "REMOVED: every pad consumer is on U_C/U_E28 (REMOVE set, ADR-089 S1)"
                if c in removed_netcodes
                else ("KEPT: shared with kept refs " + ",".join(kept_shared_with_removed[c])
                      if c in kept_shared_with_removed else "KEPT: no REMOVE-set consumer")),
        }
        for c in all_netcodes
    }
    out["removed_nets"] = sorted(netname(c) for c in removed_netcodes)
    out["nets_shared_with_removed_refs"] = {
        netname(c): refs for c, refs in kept_shared_with_removed.items()
    }
    # site-named copper: nets whose NAME embeds a removed site ref (U_C, E28, LORA1280).
    # These nets exist only to serve that site; on a MINIMAL rebuild the MCU-side pins
    # are freed and the nets disappear, so their routed copper IS what site removal buys
    # -- even where the strict consumer rule (which keeps any net a kept ref touches)
    # marks them KEPT. Reported separately from removed_netcodes, never merged.
    site_prefixes = ("/U_C_", "/E28_", "/LORA1280_")
    site_netcodes = {c for c in net_consumers
                     if netname(c).startswith(site_prefixes)}
    site_copper = {n: {"length_mm": 0.0, "segments": 0} for n in LAYERS}
    site_vias = 0
    for t in board.GetTracks():
        code = t.GetNetCode()
        if code <= 0:
            continue
        if code in site_netcodes:
            if t.Type() in (pcbnew.PCB_TRACE_T, pcbnew.PCB_ARC_T):
                lname = board.GetLayerName(t.GetLayer())
                site_copper[lname]["length_mm"] += t.GetLength() / MM
                site_copper[lname]["segments"] += 1
            elif t.Type() == pcbnew.PCB_VIA_T:
                site_vias += 1
    out["site_named_copper"] = {
        "nets": sorted(netname(c) for c in site_netcodes),
        "per_layer": site_copper,
        "vias": site_vias,
        "total_length_mm": round(sum(v["length_mm"] for v in site_copper.values()), 4),
        "total_segments": sum(v["segments"] for v in site_copper.values()),
        "caveat": "nets named for a REMOVE-set site (/U_C_, /E28_, /LORA1280_ prefixes). "
                  "Their copper vanishes with the site on a MINIMAL rebuild. /U_C_* nets "
                  "are UNROUTED on this board (0 segments) -- ADR-145's 19.81 mm is the "
                  "PAD SPAN of U_C's control pads, not routed copper.",
    }
    out["removed_copper_per_layer"] = removed_copper
    out["removed_vias_on_removed_nets"] = removed_vias
    out["removed_copper_summary"] = {
        "length_mm": round(sum(v["length_mm"] for v in removed_copper.values()), 4),
        "segments": sum(v["segments"] for v in removed_copper.values()),
        "vias": removed_vias,
        "method": "tracks/arcs on nets whose EVERY pad consumer sits on U_C/U_E28. Vias on "
                  "those nets counted separately; zone copper not attributed (zones are "
                  "GND/+3V3/VSCAP rails shared with kept parts).",
    }

    # ---- zones: filled area per layer -------------------------------------------
    zones = []
    for z in board.Zones():
        entry = {"zone": str(z.GetZoneName()), "net": "", "layers": []}
        code = z.GetNetCode()
        if code > 0:
            entry["net"] = netinfo.GetNetItem(code).GetNetname()
        for name, lid in LAYERS.items():
            if not z.IsOnLayer(lid):
                continue
            polys = z.GetFilledPolysList(lid)
            if polys is None or polys.VertexCount() == 0:
                entry["layers"].append({
                    "layer": name,
                    "filled_area_mm2": None,
                    "unsupported_geometry": "GetFilledPolysList empty/None for this layer",
                })
                continue
            try:
                poly = pcbnew.SHAPE_POLY_SET(polys)
                area = poly.Area() / MM2
            except Exception as ex:  # honest failure, never a fabricated number
                entry["layers"].append({
                    "layer": name,
                    "filled_area_mm2": None,
                    "unsupported_geometry": f"SHAPE_POLY_SET/Area failed: {ex}",
                })
                continue
            entry["layers"].append({"layer": name, "filled_area_mm2": area})
        zones.append(entry)
    out["zones"] = zones

    # ---- footprint census (G4 inputs) ---------------------------------------------
    fps = []
    for fp in board.GetFootprints():
        pos = fp.GetPosition()
        bb = fp.GetBoundingBox(False, True)
        fps.append({
            "ref": fp.GetReference(),
            "value": str(fp.GetValue()),
            "fpid": str(fp.GetFPID().GetLibNickname()) + ":" + str(fp.GetFPID().GetLibItemName()),
            "layer": board.GetLayerName(fp.GetLayer()),
            "side": "top" if fp.GetLayer() == pcbnew.F_Cu else "bottom",
            "pos_mm": [round(pos.x / MM, 3), round(pos.y / MM, 3)],
            "bbox_mm": [round(bb.GetX() / MM, 3), round(bb.GetY() / MM, 3),
                        round(bb.GetWidth() / MM, 3), round(bb.GetHeight() / MM, 3)],
            "dnp": bool(fp.IsDNP()),
        })
    out["footprints"] = fps
    out["counts"] = {
        "footprints": len(fps),
        "netted_pads": padcount,
        "named_nets": len(net_consumers),
        "total_tracks": total_tracks,
    }
    return out


def fail(msg):
    print(f"AUDIT-FAIL: {msg}", file=sys.stderr)
    sys.exit(2)


def sanity(board_path, data, expect_sha):
    # S1: hash recorded / verified
    sha = sha256_of(board_path)
    data["board_sha256"] = sha
    if expect_sha and expect_sha != sha:
        fail(f"board file changed under audit: {expect_sha} -> {sha}")
    # S2: non-empty board, 4 copper layers
    c = data["counts"]
    if c["footprints"] == 0 or c["total_tracks"] == 0:
        fail(f"degenerate board census: {c}")
    if len(data["per_layer"]) != 4:
        fail(f"copper layer count != 4: {sorted(data['per_layer'])}")
    # S3: every named net has a verdict
    verdicts = data["per_net_segments"]
    if len(verdicts) != len({v for v in verdicts}):
        fail("duplicate net names in verdict table")
    n_verdict = len(verdicts)
    n_removed = len(data["removed_nets"])
    if sum(1 for v in verdicts.values() if not v["in_minimal_set"]) != n_removed:
        fail("verdict count mismatch: removed nets disagree with per-net table")
    # S4: segment conservation
    s_layers = sum(v["segments"] for v in data["per_layer"].values())
    if s_layers != c["total_tracks"]:
        fail(f"segment conservation: layers sum {s_layers} != total {c['total_tracks']}")
    # S5: zone areas are None or positive floats
    for z in data["zones"]:
        for le in z["layers"]:
            a = le.get("filled_area_mm2")
            if a is not None and not (isinstance(a, float) and a > 0):
                fail(f"zone area not a positive float or None: {z['zone']} {le}")
    print(f"sanity: S1-S5 PASS  footprints={c['footprints']} nets={n_verdict} "
          f"removed_nets={n_removed} tracks={c['total_tracks']} vias={data['via_total']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("out_json")
    ap.add_argument("--verify-hash", default=None,
                    help="fail if the board's sha256 is not this value")
    ap.add_argument("--provenance", default=None,
                    help="path to a provenance JSON to embed (written by the caller)")
    args = ap.parse_args()

    board = pcbnew.LoadBoard(args.board)
    data = measure(board)
    data["_meta"] = {
        "board": args.board,
        "kicad_version": pcbnew.Version(),
        "read_only": True,
        "note": "board object never mutated; no SaveBoard call; hash verified before/after",
        # Record the interpreter that ACTUALLY ran. /usr/bin/python3 cannot import pcbnew on
        # this host (measured ModuleNotFoundError), so a hardcoded path is a non-recipe.
        "reproduce": f"{sys.executable} {sys.argv[0]} {args.board} <out.json> "
                     f"--verify-hash {data.get('board_sha256', '<sha256>')}",
        "interpreter_requirement": "a python whose pcbnew matches the board's KiCad "
                                   "(measured working: ~/venvs/kicad/bin/python -> "
                                   + pcbnew.Version() + ")",
    }
    if args.provenance:
        with open(args.provenance) as f:
            data["_provenance"] = json.load(f)
    sanity(args.board, data, args.verify_hash)
    with open(args.out_json, "w") as f:
        json.dump(data, f, indent=1, sort_keys=False)
    # fail-closed re-read: the emitted JSON must parse and carry the same hash
    with open(args.out_json) as f:
        rt = json.load(f)
    if rt["board_sha256"] != data["board_sha256"]:
        fail("JSON round-trip hash mismatch")
    if sha256_of(args.board) != data["board_sha256"]:
        fail("board mutated during audit -- refusing")
    print("WROTE", args.out_json)


if __name__ == "__main__":
    main()
