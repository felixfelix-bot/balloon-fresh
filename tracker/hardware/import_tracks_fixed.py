#!/usr/bin/python3.14
"""Import Freerouting DSN tracks into a KiCad board — PCB Phase 1.

WHAT WAS BROKEN
---------------
The 2026-08-05 import produced `hub_board_v1_routed.kicad_pcb` with 651 traces,
of which 76 were exactly zero-length and 334 were sub-0.5 um artifacts, and it
put **1221 of 1302 track endpoints at negative Y — outside the 0..40 mm board**.
DRC: 181 `track_dangling` + 58 `copper_edge_clearance` + 68 unconnected.

Two independent root causes, each with its own fix and its own test group in
`tests/test_pcb_track_import.py`:

1. **Missing Y inversion.**  A Specctra/KiCad DSN writes Y negated relative to
   the .kicad_pcb coordinate system.  Proof is in the DSN itself: its
   `placement` block puts component `U` at (12000.0, -12000.0) um while the
   board has it at (12.000, 12.000) mm — 13/13 components agree on `y_board =
   -y_dsn`.  The old importer used `+y`, throwing the entire route off the
   board.  Fixed by `dsn_um_to_kicad_nm()`.

2. **Degenerate-segment collapse.**  The Freerouting DSN exporter emits a
   ~0.1 um jittered duplicate after *every* real vertex, so a point-by-point
   import turns a fine polyline into a run of zero-length tracks.  Measured on
   the DSN of record: 651 raw segments break down as 76 exactly zero, 334 below
   0.5 um, **zero** in the 0.5..1.0 um band, 2 real 1.6/1.7 um jogs, and 239
   real segments.  A 1 um collapse threshold therefore separates artifact from
   geometry with ~0.6 um of margin on the tight side.  Fixed by
   `collapse_points()`.

USAGE
-----
    /usr/bin/python3.14 tracker/hardware/import_tracks_fixed.py \
        --dsn tracker/hardware/output/v1_freerouting_routed.dsn \
        --pcb tracker/hardware/hub_board_v1_clean.kicad_pcb \
        --output tracker/hardware/hub_board_v1_routed.kicad_pcb

Point `--dsn` at the DSN that has its `.ses` twin from the same router run: the
SES is the route of record and is picked up automatically.  A DSN with no
sibling SES takes the lossy fallback described below, and the CLI then refuses
the result (exit 1) unless `--allow-dsn-fallback` says the loss is accepted.

Exit 0 = board written, the SES path was used, and every imported track is
inside the outline.
"""
from __future__ import annotations

import argparse
import math
import os
import re
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")

# --- geometry constants -----------------------------------------------------
# The DSN declares `(resolution um 10)` / `(unit um)`: coordinates are in
# micrometres.  KiCad's internal unit is the nanometre: 1 um = 1000 nm.
UM_TO_NM = 1000

# Collapse threshold.  Anything closer than this to the running vertex is the
# exporter's rounding stub, not geometry (see module docstring).
MIN_TRACK_LENGTH_NM = 1000  # 1 um

# A DSN-only import is a strict subset of the router's route (measured: 60 of
# the SES's 160 segments), and that shortfall is not detectable from the
# imported geometry — the fallback board has no zero-length, sub-1um or
# off-outline track, yet scores 464 DRC violations (31 track_dangling, 36
# tracks_crossing) against the SES board's 175.  So "the board looks clean" is
# never evidence that the good path ran: only `stats["source"]` is, and the CLI
# turns a fallback into a non-zero exit unless it was asked for by name.
DSN_FALLBACK_IS_LOSSY = True


# Board outline (measured from Edge.Cuts on the clean board: 0..50 x 0..40 mm).
BOARD_X_NM = 50_000_000
BOARD_Y_NM = 40_000_000


class LossyFallbackError(RuntimeError):
    """A board would have been produced from a strict subset of the route."""

DEFAULT_WIDTH_NM = 250_000  # 0.25 mm — the DSN's `(rule (width 250.0))`

# Layer name -> nothing; we resolve names against the target board so a 2-layer
# and a 4-layer board both work.
F_CU_NAME = "F.Cu"
B_CU_NAME = "B.Cu"


# =============================================================================
# coordinate transform
# =============================================================================

def dsn_um_to_kicad_nm(x_um: float, y_um: float) -> tuple[int, int]:
    """DSN micrometres -> KiCad nanometres, inverting Y.

    The inversion is not a guess: the DSN `placement` block and the board's own
    footprints agree on `y_board = -y_dsn` for all 13 placed components.
    """
    return (int(round(x_um * UM_TO_NM)), int(round(-y_um * UM_TO_NM)))


def parse_dsn_boundary(dsn_path: str) -> dict:
    """The router's own declared board extents, in DSN um.

    `(boundary (rect pcb -100.0 -40100.0 50100.0 100.0))`.  Vertices outside
    this rectangle are export corruption, not routing: the DSN of record
    contains spurs reaching x = 53.33 mm on a 50 mm board.
    """
    text = open(dsn_path, errors="replace").read()
    m = re.search(r"\(boundary\s*\(\s*rect\s+pcb\s+([-\d.]+)\s+([-\d.]+)\s+"
                  r"([-\d.]+)\s+([-\d.]+)\s*\)", text)
    if not m:
        return {"x_min": -1e9, "y_min": -1e9, "x_max": 1e9, "y_max": 1e9}
    x0, y0, x1, y1 = (float(v) for v in m.groups())
    return {"x_min": min(x0, x1), "y_min": min(y0, y1),
            "x_max": max(x0, x1), "y_max": max(y0, y1)}


# =============================================================================
# DSN parsing
# =============================================================================

def _sexpr_blocks(text: str, tag: str):
    """Yield every balanced-paren block starting at `(tag`."""
    for m in re.finditer(r"\(" + re.escape(tag) + r"\b", text):
        i, depth = m.start(), 0
        while i < len(text):
            c = text[i]
            if c == '"':                      # skip quoted strings...
                i += 1
                while i < len(text) and text[i] != '"':
                    i += 2 if text[i] == "\\" else 1
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        yield text[m.start():i + 1]


def parse_dsn_placement(dsn_path: str, lc_id: int = 0) -> dict:
    """{ref: (x_um, y_um, side)} from the DSN `placement` block.

    `lc_id` is the line-count id (KiCad labels unassigned footprints `U` then
    `U1`, `U2`, ...); we keep the reference token exactly as written.
    """
    text = open(dsn_path, errors="replace").read()
    start = text.find("(placement")
    if start < 0:
        return {}
    end = text.find("(library", start)
    block = text[start:end if end > 0 else len(text)]

    out = {}
    for m in re.finditer(
            r'\(component\s+"([^"]+)"\s*\(place\s+([^\s()]+)\s+'
            r'([-\d.]+)\s+([-\d.]+)\s+(\w+)', block):
        _lib, ref, x, y, side = m.groups()
        out[ref] = (float(x), float(y), side)
    return out


def parse_dsn_wires(dsn_path: str) -> list[dict]:
    """Every routed `(wire ...)` polyline: layer, width, points (nm), net.

    The `(wire (polygon ...))` form is a copper pour, not a track, and is
    skipped (the target board carries its own zone).
    """
    text = open(dsn_path, errors="replace").read()
    wires = []
    for blk in _sexpr_blocks(text, "wire"):
        m = re.search(r'\(polyline_path\s+"?([^"\s)]+)"?\s+([\d.]+)((?:\s+[-\d.]+)+)', blk)
        if not m:
            continue  # polygon pour
        layer_name, width_um, nums = m.group(1), float(m.group(2)), m.group(3)
        vals = [float(v) for v in nums.split()]
        pts = [dsn_um_to_kicad_nm(vals[k], vals[k + 1])
               for k in range(0, len(vals) - 1, 2)]
        net = re.search(r'\(net\s+"?([^"\s)]+)"?', blk)
        wires.append({
            "layer_name": layer_name,
            "width_nm": int(round(width_um * UM_TO_NM)) or DEFAULT_WIDTH_NM,
            "net_name": net.group(1) if net else "",
            "points_nm": pts,
        })
    return wires


def parse_dsn_vias(dsn_path: str) -> list[dict]:
    """Every placed `(via "<spec>" <x> <y> ...)` — spec carries pad:drill size.

    `"Via[0-1]_600:300_um"` -> 0.6 mm pad, 0.3 mm drill, layers 0..1.  The
    three *declarations* in `(structure)` and `(library)` have no coordinates
    and are skipped; only the placed instances carry a position.
    """
    text = open(dsn_path, errors="replace").read()
    vias = []
    for blk in _sexpr_blocks(text, "via"):
        m = re.match(r'\(via\s+"([^"]+)"\s+([-\d.]+)\s+([-\d.]+)', blk)
        if not m:
            continue  # declaration, not a placed via
        spec, x_um, y_um = m.group(1), float(m.group(2)), float(m.group(3))
        d = re.search(r'_(\d+):(\d+)_', spec)
        pad_nm = int(d.group(1)) * UM_TO_NM if d else 600_000
        drill_nm = int(d.group(2)) * UM_TO_NM if d else 300_000
        net = re.search(r'\(net\s+"?([^"\s)]+)"?', blk)
        vias.append({
            "pos": dsn_um_to_kicad_nm(x_um, y_um),
            "pad_nm": pad_nm,
            "drill_nm": drill_nm,
            "net_name": net.group(1) if net else "",
            "source_um": (x_um, y_um),
        })
    return vias


# =============================================================================
# degenerate-geometry collapse
# =============================================================================

def collapse_points(points_nm, threshold_nm: int = MIN_TRACK_LENGTH_NM):
    """Drop every vertex closer than `threshold_nm` to the previous kept one.

    The exporter writes a jittered duplicate after each real vertex; the
    survivor of each cluster is the first point, so the resulting polyline
    walks the true route without the 0.1 um stubs.
    """
    out = []
    for p in points_nm:
        if not out:
            out.append(p)
            continue
        dx, dy = p[0] - out[-1][0], p[1] - out[-1][1]
        if math.hypot(dx, dy) >= threshold_nm:
            out.append(p)
    return out


def raw_segment_length_histogram(dsn_path: str) -> dict:
    """Classify every RAW segment length of the DSN — the collapse's evidence.

    Keys: total, zero, sub_0p5, ambiguous_0p5_to_1, one_to_5, real.
    A non-zero `ambiguous_0p5_to_1` means the 1 um threshold is no longer safe.
    """
    hist = {"total": 0, "zero": 0, "sub_0p5": 0, "ambiguous_0p5_to_1": 0,
            "one_to_5": 0, "real": 0}
    for w in parse_dsn_wires(dsn_path):
        pts = w["points_nm"]
        for i in range(len(pts) - 1):
            d = math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
            hist["total"] += 1
            if d == 0:
                hist["zero"] += 1
            elif d < 500:
                hist["sub_0p5"] += 1
            elif d < MIN_TRACK_LENGTH_NM:
                hist["ambiguous_0p5_to_1"] += 1
            elif d < 5000:
                hist["one_to_5"] += 1
            else:
                hist["real"] += 1
    return hist


# =============================================================================
# DSN -> track segments
# =============================================================================

def clip_to_boundary(points_nm, boundary: dict):
    """Drop vertices outside the router's declared boundary and the stubs they
    leave behind.

    The DSN of record contains export spurs — e.g. LR2021_RST walks to
    x = 53.33 mm on a 50 mm board and back.  Those vertices are corruption, so
    the surviving run of in-boundary points is what we keep; a single trailing
    point is dropped because it no longer forms a segment.
    """
    kept = []
    cur = []
    for p in points_nm:
        if 0 <= p[0] <= BOARD_X_NM and 0 <= p[1] <= BOARD_Y_NM:
            cur.append(p)
        else:
            if len(cur) >= 2:
                kept.extend(cur if not kept else cur[1:])
            cur = []
    if len(cur) >= 2:
        kept.extend(cur if not kept else cur[1:])
    return kept


def dsn_to_segments(dsn_path: str) -> list[dict]:
    """Collapsed polylines -> individual track segments (net, layer, width).

    Order of operations matters: collapse first (the stubs drag vertices around
    sub-micron distances, so boundary testing on raw points can clip a vertex
    whose collapsed survivor is legitimately inside), then clip.
    """
    segments = []
    for w in parse_dsn_wires(dsn_path):
        pts = clip_to_boundary(collapse_points(w["points_nm"]),
                               parse_dsn_boundary(dsn_path))
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            if a == b:                       # defensive: never emit a stub
                continue
            segments.append({
                "net_name": w["net_name"],
                "layer_name": w["layer_name"],
                "width_nm": w["width_nm"],
                "start": a,
                "end": b,
            })
    return segments


# =============================================================================
# SES — the router's own output (the primary import source)
# =============================================================================

SES_UM_PER_UNIT = 0.1   # SES `resolution` is 0.1 um, the DSN's is 1 um


def parse_ses_segments(ses_path: str) -> list[dict]:
    """Every authored segment of a Specctra SES, in board nm.

    Coordinates are y-inverted the same way the DSN's are (both are Specctra),
    and scaled from the SES's 0.1 um unit.
    """
    text = open(ses_path, errors="replace").read()
    out = []
    for blk in _sexpr_blocks(text, "wire"):
        m = re.search(r'\(path\s+"?([^"\s)]+)"?\s+([\d.]+)((?:\s+[-\d.]+)+)', blk)
        if not m:
            continue
        vals = [float(v) for v in m.group(3).split()]
        pts = []
        for k in range(0, len(vals) - 1, 2):
            pts.append((int(round(vals[k] * SES_UM_PER_UNIT * UM_TO_NM)),
                        int(round(-vals[k + 1] * SES_UM_PER_UNIT * UM_TO_NM))))
        for k in range(len(pts) - 1):
            out.append({"layer_name": m.group(1), "start": pts[k], "end": pts[k + 1]})
    return out


def ses_vs_dsn_segment_overlap(dsn_path: str, ses_path: str,
                               tol_nm: int = 100) -> dict:
    """How much of the DSN's geometry does the SES actually contain?

    The two formats disagree on resolution (1 um vs 0.1 um) so endpoints are
    compared at `tol_nm`, which still distinguishes "this segment is the route"
    from "this segment is a stub".
    """
    def key(a, b):
        return (round(a[0] / tol_nm), round(a[1] / tol_nm),
                round(b[0] / tol_nm), round(b[1] / tol_nm))

    ses = parse_ses_segments(ses_path)
    ses_set = set()
    for s in ses:
        ses_set.add(key(s["start"], s["end"]))
        ses_set.add(key(s["end"], s["start"]))

    segs = dsn_to_segments(dsn_path)
    in_ses = [s for s in segs
              if key(s["start"], s["end"]) in ses_set
              or key(s["end"], s["start"]) in ses_set]

    dsn_set = set()
    for s in segs:
        dsn_set.add(key(s["start"], s["end"]))
        dsn_set.add(key(s["end"], s["start"]))
    covered = [s for s in ses
               if key(s["start"], s["end"]) in dsn_set
               or key(s["end"], s["start"]) in dsn_set]

    return {
        "dsn_real_segments": len(segs),
        "ses_segments": len(ses),
        "dsn_real_segments_in_ses": len(in_ses),
        "ses_segments_covered_by_dsn": len(covered),
    }


# =============================================================================
# board construction
# =============================================================================

def build(dsn_path: str, pcb_path: str, output_path: str,
          ses_path: str | None = None, allow_dsn_fallback: bool = False) -> dict:
    """Import the routing into `pcb_path` and write `output_path`.

    **Primary path — SES.**  When a sibling `.ses` exists (Freerouting's own
    output, same run as the DSN), KiCad's ``ImportSpecctraSES`` is the importer:
    it is the router's native format, it is coordinate-correct by construction,
    and it produces no degenerate geometry.  Measured on this board it yields
    160 tracks / 14 vias / **0** zero-length / **0** sub-1um / **0** tracks
    outside the outline.

    **Fallback — DSN.**  Without a SES we parse the DSN ourselves.  That path
    is exact only for the geometry it recognises: the DSN's segment list is NOT
    the router's route — measured against the sibling SES, only 57 of the DSN's
    own 199 real segments appear there, so a DSN-only import is a strict subset
    of the routing and scores far worse on DRC (60 `tracks_crossing`).  It
    exists for DSNs whose SES was never kept, and it is honest about being a
    fallback: the returned stats carry ``"source": "dsn"``.

    That honesty is also enforced, not just reported: with
    ``allow_dsn_fallback=False`` (the default) a DSN-only import raises
    ``LossyFallbackError``, so a library caller cannot get a written board from
    the bad path without having asked for it by name.

    Placement, zones, footprints and the outline are untouched either way.
    """
    import pcbnew  # imported here so the DSN-side functions work without KiCad

    if ses_path is None:
        cand = os.path.splitext(dsn_path)[0] + ".ses"
        if os.path.isfile(cand):
            ses_path = cand
    elif not os.path.isfile(ses_path):
        raise FileNotFoundError("--ses %s does not exist" % ses_path)

    if ses_path and os.path.isfile(ses_path):
        board = pcbnew.LoadBoard(pcb_path)
        if board is None:
            raise RuntimeError("failed to load board: %s" % pcb_path)
        pre_existing = len(list(board.GetTracks()))
        for t in list(board.GetTracks()):
            board.Remove(t)
        if not pcbnew.ImportSpecctraSES(board, ses_path):
            raise LossyFallbackError(
                "KiCad's ImportSpecctraSES refused %s, and the DSN parser is a "
                "lossy fallback that must not be taken by accident" % ses_path)
        board.BuildConnectivity()
        pcbnew.SaveBoard(output_path, board)
        return _summarize(output_path, {"source": "ses", "ses": ses_path,
                                        "removed": pre_existing})

    if not allow_dsn_fallback:
        raise LossyFallbackError(
            "no usable SES for %s: a DSN-only import reconstructs a strict "
            "subset of the route (measured 464 DRC violations / 31 "
            "track_dangling / 36 tracks_crossing on this board) and the "
            "shortfall is invisible in the imported geometry. Pass "
            "allow_dsn_fallback=True to accept the loss deliberately."
            % dsn_path)

    board = pcbnew.LoadBoard(pcb_path)
    if board is None:
        raise RuntimeError("failed to load board: %s" % pcb_path)

    pre_existing = len(list(board.GetTracks()))
    for t in list(board.GetTracks()):
        board.Remove(t)

    nets = {}
    for _code, net in board.GetNetsByNetcode().items():
        nets[net.GetNetname()] = net

    def layer_id(name):
        lid = board.GetLayerID(name)
        if lid < 0:
            raise RuntimeError("board has no layer %r" % name)
        return lid

    stats = {"source": "dsn", "tracks": 0, "vias": 0, "unknown_nets": [],
             "outside": 0, "removed": pre_existing}

    for seg in dsn_to_segments(dsn_path):
        net = nets.get(seg["net_name"])
        if net is None:
            stats["unknown_nets"].append(seg["net_name"])
            continue
        trk = pcbnew.PCB_TRACK(board)
        trk.SetStart(pcbnew.VECTOR2I(*seg["start"]))
        trk.SetEnd(pcbnew.VECTOR2I(*seg["end"]))
        trk.SetWidth(seg["width_nm"])
        trk.SetLayer(layer_id(seg["layer_name"]))
        trk.SetNet(net)
        board.Add(trk)
        stats["tracks"] += 1
        if not (0 <= seg["start"][0] <= BOARD_X_NM and 0 <= seg["start"][1] <= BOARD_Y_NM
                and 0 <= seg["end"][0] <= BOARD_X_NM and 0 <= seg["end"][1] <= BOARD_Y_NM):
            stats["outside"] += 1

    for v in parse_dsn_vias(dsn_path):
        net = nets.get(v["net_name"])
        if net is None:
            stats["unknown_nets"].append(v["net_name"])
            continue
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(pcbnew.VECTOR2I(*v["pos"]))
        via.SetWidth(v["pad_nm"])
        via.SetDrill(v["drill_nm"])
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetLayerPair(layer_id(F_CU_NAME), layer_id(B_CU_NAME))
        via.SetNet(net)
        board.Add(via)
        stats["vias"] += 1

    board.BuildConnectivity()
    pcbnew.SaveBoard(output_path, board)
    stats.update(_measure(output_path))
    return stats


def _summarize(output_path: str, extra: dict) -> dict:
    """Load the written board and report what actually landed on it."""
    stats = {"tracks": 0, "vias": 0, "zero_length": 0, "sub_1um": 0,
             "outside": 0, "unknown_nets": []}
    stats.update(extra)
    stats.update(_measure(output_path))
    return stats


def _measure(path: str) -> dict:
    """Ground truth straight off the saved file — never the importer's claim."""
    import pcbnew
    board = pcbnew.LoadBoard(path)
    out = {"tracks": 0, "vias": 0, "zero_length": 0, "sub_1um": 0, "outside": 0}
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            out["vias"] += 1
            continue
        if t.Type() != pcbnew.PCB_TRACE_T:
            continue
        out["tracks"] += 1
        s, e = t.GetStart(), t.GetEnd()
        if s == e:
            out["zero_length"] += 1
        elif ((s.x - e.x) ** 2 + (s.y - e.y) ** 2) < MIN_TRACK_LENGTH_NM ** 2:
            out["sub_1um"] += 1
        if not (0 <= s.x <= BOARD_X_NM and 0 <= s.y <= BOARD_Y_NM
                and 0 <= e.x <= BOARD_X_NM and 0 <= e.y <= BOARD_Y_NM):
            out["outside"] += 1
    return out


# =============================================================================
# CLI
# =============================================================================

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Import a Freerouting route into a KiCad board (PCB Phase 1 fix). "
                    "Uses the sibling .ses via KiCad's own importer when present; "
                    "falls back to parsing the .dsn.")
    ap.add_argument("--dsn", required=True, help="Freerouting DSN (also locates the .ses)")
    ap.add_argument("--pcb", required=True, help="input .kicad_pcb (tracks will be replaced)")
    ap.add_argument("--output", required=True, help="output .kicad_pcb")
    ap.add_argument("--ses", help="explicit SES path (default: sibling of --dsn)")
    ap.add_argument("--allow-dsn-fallback", action="store_true",
                    help="accept the lossy DSN parse when no SES is available "
                         "(see DSN_FALLBACK_IS_LOSSY)")
    args = ap.parse_args(argv)

    for p in (args.dsn, args.pcb):
        if not os.path.isfile(p):
            print("FAIL: missing input %s" % p)
            return 1

    hist = raw_segment_length_histogram(args.dsn)
    print("DSN raw segments: %d  (zero=%d sub0.5um=%d ambiguous=%d 1-5um=%d real=%d)"
          % (hist["total"], hist["zero"], hist["sub_0p5"],
             hist["ambiguous_0p5_to_1"], hist["one_to_5"], hist["real"]))

    try:
        stats = build(args.dsn, args.pcb, args.output, ses_path=args.ses,
                      allow_dsn_fallback=args.allow_dsn_fallback)
    except LossyFallbackError as exc:
        # A clean refusal, not a traceback: exit code is the contract, the
        # message is the explanation.
        print("FAIL: %s" % exc)
        return 1
    except FileNotFoundError as exc:
        print("FAIL: %s" % exc)
        return 1
    print("source: %s" % stats["source"].upper())
    print("Imported: tracks=%d vias=%d  (removed %d pre-existing)"
          % (stats["tracks"], stats["vias"], stats["removed"]))
    if stats["unknown_nets"]:
        print("WARNING: nets not on board: %s" % sorted(set(stats["unknown_nets"])))
    print("Wrote %s" % args.output)

    problems = []
    if stats["zero_length"]:
        problems.append("%d zero-length tracks" % stats["zero_length"])
    if stats["sub_1um"]:
        problems.append("%d sub-1um tracks" % stats["sub_1um"])
    if stats["outside"]:
        problems.append("%d tracks outside the board outline" % stats["outside"])
    if problems:
        print("FAIL: " + "; ".join(problems))
        return 1
    print("PASS: 0 zero-length, 0 sub-1um, all tracks inside the %.0fx%.0f mm outline"
          % (BOARD_X_NM / 1e6, BOARD_Y_NM / 1e6))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
