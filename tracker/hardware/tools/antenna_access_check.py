#!/usr/bin/env python3
"""Deterministic, fail-closed antenna solder-access checker (ADR-045).

WHY
---
The v9 balloon flight board carries four RF parts, every one of them
**hand-soldered by the operator** (ADR-040; `docs/V9-RADIO-SITE-MATRIX.md`).
A hand-soldered part is only buildable if a soldering iron can physically
reach its antenna pad from OUTSIDE the module body. ADR-045 records that as a
hard constraint and this script is its mechanical gate.

WHAT IT CHECKS
--------------
For every RF-module footprint on a `.kicad_pcb`, for **every pad**, it reports:

  * the pad number;
  * whether the pad is an **edge / castellated pad** -- i.e. its copper bbox
    reaches or crosses the footprint body outline (derived here from the
    `F.Fab`/`B.Fab` graphics bbox, falling back to the pad-copper union, then
    to the courtyard bbox).  A pad that lies strictly inside the body is
    "under the module body" and is NOT edge-accessible;
  * the **nearest other footprint courtyard** and the **gap in millimetres**
    (minimum Euclidean distance, pad copper rectangle to courtyard polygon).

The ANTENNA-PORT pads of each module are then gated:

  * FAIL     (exit 1)  -- the pad is not edge-accessible (occluded by the
                          module body), or its nearest-courtyard gap is
                          strictly less than `--min-gap` (default 1.0 mm);
  * CANNOT-VERIFY      -- the footprint is an RF part whose antenna pin set is
                          not known (no committed datasheet / no pin map entry
                          and no `--antenna-pins` override), or its geometry
                          cannot be read.

EXIT CODES (fail-closed -- an unknown antenna pin is never a silent pass)
------------------------------------------------------------------------
  0  PASS           every known antenna-port pad is edge-accessible and clear
  1  FAIL           at least one antenna-port pad is occluded or inside the gap
  2  CANNOT-VERIFY  the board cannot be read, an RF footprint cannot be
                    identified, or an antenna pin set is unknown
A definite FAIL (1) outranks CANNOT-VERIFY (2).  Exit 0 is only possible when
every RF footprint's antenna ports are known AND pass.

ANTENNA PIN MAP (provenance -- ADR-045 D1)
------------------------------------------
  LoRa2021F33_2G4   pins 9,10  F33 datasheet v1.1 §7: 9=ANT (sub-GHz),
                               10=ANT-2G4 (2.4 GHz)              [VERIFIED]
  LoRa2021 (bare)   pins 9,10  LoRa2021 module datasheet V1.3 §7:
                               9=ANTA/ANT (sub-GHz), 10=2.4/S_ANTA [VERIFIED]
  SX1280            unknown    no SX1280 datasheet committed       [TODO]
  ublox_MAX / GNSS  unknown    no MAX-M10S datasheet committed     [TODO]
  U.FL_*            pad 1      centre signal conductor, footprint-level
                               (not a datasheet attribution)       [VERIFIED]

LIMITS (read before trusting a PASS)
------------------------------------
The courtyard gap is a *proxy* for the approach path.  It does not model
neighbour height, a copper keep-out that is not a footprint, or the board
edge.  A PASS is necessary, not sufficient; the human build check is the
authority.  See ADR-045 D2 "Honest limit of the predicate".

INPUTS
------
  BOARD [BOARD ...]        one or more `.kicad_pcb` paths
  --min-gap MM             minimum access gap (default 1.0)
  --refs REF [REF ...]     restrict to these reference designators
  --antenna-pins REF:PINS  override the antenna pin set, e.g. U2:9,10
                           (repeatable; makes an unknown part checkable)
  --json                   emit a machine-readable report instead of a table
"""

import argparse
import json
import math
import os
import sys

try:
    import pcbnew  # type: ignore
except Exception:  # pragma: no cover - exercised only without KiCad
    pcbnew = None

DEFAULT_MIN_GAP_MM = 1.0
EPS_EDGE_MM = 0.05

# (library-item-name substring, antenna pin set or None, kind, provenance)
ANTENNA_PIN_MAP = (
    ("lora2021f33", frozenset({"9", "10"}), "castellated",
     "LoRa2021F33-2G4 datasheet v1.1 §7: pin 9 ANT (sub-GHz), pin 10 ANT-2G4 (2.4 GHz)"),
    ("lora2021_castellated", frozenset({"9", "10"}), "castellated",
     "LoRa2021 module datasheet V1.3 §7: pin 9 ANTA/ANT (sub-GHz), pin 10 2.4/S_ANTA"),
    ("lora2021", frozenset({"9", "10"}), "castellated",
     "LoRa2021 family datasheet §7 (family default)"),
    ("sx128", None, "castellated",
     None),
    ("u.fl", frozenset({"1"}), "connector",
     "U.FL footprint: pad 1 is the centre signal conductor (footprint-level)"),
    ("ufl", frozenset({"1"}), "connector",
     "U.FL footprint: pad 1 is the centre signal conductor (footprint-level)"),
    ("ublox_max", None, "module",
     None),
    ("max-m10", None, "module",
     None),
    ("gnss", None, "module",
     None),
)

UNVERIFIED_QUESTION = {
    "sx128": ("which SX1280 pad is RFIO, and is it a perimeter/castellated pad "
              "rather than an underside thermal-adjacent pad? (no SX1280 datasheet "
              "in repo)"),
    "ublox_max": ("which pad of the ublox_MAX footprint is the GNSS RF_IN input? "
                  "(no MAX-M10S datasheet in repo)"),
    "max-m10": ("which pad of the MAX-M10S footprint is the GNSS RF_IN input? "
                "(no MAX-M10S datasheet in repo)"),
    "gnss": ("which pad of the GNSS footprint is the RF feed? (no datasheet in repo)"),
}


# --------------------------------------------------------------------------- #
# geometry helpers (pure python, mm floats)
# --------------------------------------------------------------------------- #

def _to_mm(nm):
    if pcbnew is not None:
        return pcbnew.ToMM(nm)
    return nm / 1_000_000.0


def _bbox_of_points(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _rect_corners(rect):
    x0, y0, x1, y1 = rect
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _seg_point_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    if dx == 0.0 and dy == 0.0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _seg_seg_dist(a1, a2, b1, b2):
    d = min(
        _seg_point_dist(a1[0], a1[1], b1[0], b1[1], b2[0], b2[1]),
        _seg_point_dist(a2[0], a2[1], b1[0], b1[1], b2[0], b2[1]),
        _seg_point_dist(b1[0], b1[1], a1[0], a1[1], a2[0], a2[1]),
        _seg_point_dist(b2[0], b2[1], a1[0], a1[1], a2[0], a2[1]),
    )
    return d


def _point_in_poly(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < xin:
                inside = not inside
    return inside


def polygon_distance(poly_a, poly_b):
    """Minimum Euclidean distance between two simple closed polygons (mm).

    Returns 0.0 when they overlap or one contains the other.
    """
    if not poly_a or not poly_b:
        return None
    if _point_in_poly(poly_a[0], poly_b) or _point_in_poly(poly_b[0], poly_a):
        return 0.0
    best = float("inf")
    for i in range(len(poly_a)):
        a1, a2 = poly_a[i], poly_a[(i + 1) % len(poly_a)]
        for j in range(len(poly_b)):
            b1, b2 = poly_b[j], poly_b[(j + 1) % len(poly_b)]
            d = _seg_seg_dist(a1, a2, b1, b2)
            if d < best:
                best = d
    return 0.0 if best == float("inf") else best


def rect_inside_rect(inner, outer, tol):
    """True when `inner` is strictly inside `outer` by more than `tol` on both axes."""
    ix0, iy0, ix1, iy1 = inner
    ox0, oy0, ox1, oy1 = outer
    return (ix0 > ox0 + tol and ix1 < ox1 - tol
            and iy0 > oy0 + tol and iy1 < oy1 - tol)


def pad_is_edge_accessible(pad_rect, body_rect, tol=EPS_EDGE_MM):
    """ADR-045 D2 limb (a): pad copper reaches/crosses the body outline."""
    return not rect_inside_rect(pad_rect, body_rect, tol)


# --------------------------------------------------------------------------- #
# pcbnew extraction
# --------------------------------------------------------------------------- #

def _graphics_bbox(fp, layers):
    pts = []
    for item in fp.GraphicalItems():
        try:
            if item.GetLayer() not in layers:
                continue
        except Exception:
            continue
        try:
            bb = item.GetBoundingBox()
        except Exception:
            continue
        pts.append((_to_mm(bb.GetX()), _to_mm(bb.GetY())))
        pts.append((_to_mm(bb.GetX() + bb.GetWidth()), _to_mm(bb.GetY() + bb.GetHeight())))
    return _bbox_of_points(pts) if pts else None


def _courtyard_polygon(fp):
    for layer in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
        try:
            poly = fp.GetCourtyard(layer)
        except Exception:
            poly = None
        if poly is not None and poly.OutlineCount() > 0:
            chain = poly.Outline(0)
            pts = [(_to_mm(chain.CPoint(i).x), _to_mm(chain.CPoint(i).y))
                   for i in range(chain.PointCount())]
            if len(pts) >= 3:
                return pts, "pcbnew GetCourtyard"
    # fallback: courtyard graphics bbox
    rect = _graphics_bbox(fp, {pcbnew.F_CrtYd, pcbnew.B_CrtYd})
    if rect:
        return _rect_corners(rect), "F.CrtYd/B.CrtYd graphics bbox"
    return None, None


def _body_rect(fp, pad_rects, courtyard_poly):
    for layers in ({pcbnew.F_Fab, pcbnew.B_Fab},):
        rect = _graphics_bbox(fp, layers)
        if rect:
            return rect, "F.Fab/B.Fab outline"
    if pad_rects:
        pts = []
        for r in pad_rects:
            pts.extend(_rect_corners(r))
        return _bbox_of_points(pts), "pad copper union (no F.Fab graphics)"
    if courtyard_poly:
        return _bbox_of_points(courtyard_poly), "courtyard bbox (no F.Fab graphics)"
    return None, None


def _classify(libid):
    low = (libid or "").lower()
    for kw, pins, kind, prov in ANTENNA_PIN_MAP:
        if kw in low:
            return kw, pins, kind, prov
    return None, None, None, None


def _is_rf(libid):
    return _classify(libid)[0] is not None


def build_report(board_path, min_gap_mm, refs=None, overrides=None):
    """Return (report_dict, exit_code). Never raises for a board-level problem."""
    overrides = overrides or {}
    if not os.path.isfile(board_path):
        return {"board": board_path, "error": "board file not found",
                "exit_code": 2}, 2
    try:
        board = pcbnew.LoadBoard(board_path)
    except Exception as exc:  # pragma: no cover - depends on KiCad
        return {"board": board_path, "error": "pcbnew could not load board: %s" % exc,
                "exit_code": 2}, 2
    if board is None:
        return {"board": board_path, "error": "pcbnew returned no board",
                "exit_code": 2}, 2

    footprints = list(board.GetFootprints())

    # --- choose the RF footprints (optionally restricted by --refs) ---------
    modules = []
    for fp in footprints:
        ref = fp.GetReference()
        libid = str(fp.GetFPID().GetLibItemName())
        if refs is not None and ref not in refs:
            continue
        if not _is_rf(libid):
            continue
        kw, pins, kind, prov = _classify(libid)
        if ref in overrides:
            pins = overrides[ref]
            prov = "operator/CLI override (--antenna-pins)"
            kind = kind or "castellated"
        modules.append({"fp": fp, "ref": ref, "libid": libid, "kw": kw,
                        "pins": pins, "kind": kind, "prov": prov})

    report = {"board": board_path, "min_gap_mm": min_gap_mm, "modules": [],
              "failures": [], "unverified": []}

    if not modules:
        report["error"] = ("no identifiable RF footprint found on the board"
                           + (" (after --refs filter)" if refs is not None else ""))
        report["exit_code"] = 2
        return report, 2

    # --- courtyard polygons for every footprint (for the neighbour test) ---
    courtyards = {}
    for fp in footprints:
        poly, _src = _courtyard_polygon(fp)
        courtyards[fp.GetReference()] = poly

    for mod in modules:
        fp = mod["fp"]
        pad_rects = []
        pads = list(fp.Pads())
        pad_models = []
        for pad in pads:
            bb = pad.GetBoundingBox()
            rect = (_to_mm(bb.GetX()), _to_mm(bb.GetY()),
                    _to_mm(bb.GetX() + bb.GetWidth()),
                    _to_mm(bb.GetY() + bb.GetHeight()))
            pad_rects.append(rect)
            pad_models.append({"pad": pad.GetNumber(), "rect": rect})

        cy_poly, cy_src = _courtyard_polygon(fp)
        body, body_src = _body_rect(fp, pad_rects, cy_poly)

        mod_report = {
            "ref": mod["ref"], "libid": mod["libid"], "kind": mod["kind"],
            "antenna_pins": sorted(mod["pins"]) if mod["pins"] is not None else None,
            "provenance": mod["prov"],
            "body_source": body_src,
            "body_mm": [round(v, 4) for v in body] if body else None,
            "courtyard_source": cy_src,
            "pads": [],
        }

        if mod["pins"] is None:
            reason = ("antenna pin set unknown: "
                      + (UNVERIFIED_QUESTION.get(mod["kw"]) or "no pin map entry"))
            mod_report["verdict"] = "CANNOT-VERIFY"
            mod_report["unverified_reason"] = reason
            report["unverified"].append({"ref": mod["ref"], "reason": reason})

        if body is None:
            mod_report.setdefault("verdict", "CANNOT-VERIFY")
            reason = "footprint body geometry could not be derived"
            mod_report["unverified_reason"] = reason
            report["unverified"].append({"ref": mod["ref"], "reason": reason})

        for pm in pad_models:
            num = pm["pad"]
            rect = pm["rect"]
            edge = pad_is_edge_accessible(rect, body, EPS_EDGE_MM) if body else None

            nearest_ref, nearest_gap = None, None
            for other in footprints:
                oref = other.GetReference()
                if oref == mod["ref"]:
                    continue
                opoly = courtyards.get(oref)
                if not opoly:
                    continue
                d = polygon_distance(_rect_corners(rect), opoly)
                if d is None:
                    continue
                if nearest_gap is None or d < nearest_gap:
                    nearest_gap, nearest_ref = d, oref

            is_antenna = mod["pins"] is not None and num in mod["pins"]
            entry = {
                "pad": num,
                "edge_accessible": edge,
                "copper_bbox_mm": [round(v, 4) for v in rect],
                "nearest_other_ref": nearest_ref,
                "nearest_gap_mm": round(nearest_gap, 4) if nearest_gap is not None else None,
                "antenna_port": is_antenna,
                "status": "INFO",
                "reason": "",
            }

            if is_antenna and body is not None:
                problems = []
                if mod["kind"] == "castellated" and not edge:
                    problems.append("occluded: pad copper does not reach the module "
                                    "perimeter (sits under the module body)")
                if nearest_gap is None:
                    problems.append("cannot verify: no other footprint geometry "
                                    "available for the approach-path test")
                elif nearest_gap < min_gap_mm:
                    problems.append(
                        "blocked approach: nearest footprint courtyard %s is %.4f mm "
                        "away, < min access gap %.4f mm"
                        % (nearest_ref, nearest_gap, min_gap_mm))
                if problems:
                    entry["status"] = "FAIL"
                    entry["reason"] = "; ".join(problems)
                    report["failures"].append(
                        {"ref": mod["ref"], "pad": num, "reason": entry["reason"]})
                else:
                    entry["status"] = "PASS"
                    entry["reason"] = ("edge-accessible and gap %.4f mm >= %.4f mm"
                                       % (nearest_gap, min_gap_mm))
            elif is_antenna and body is None:
                entry["status"] = "CANNOT-VERIFY"
                entry["reason"] = "no body geometry"
            elif not is_antenna and mod["pins"] is None:
                entry["status"] = "UNMAPPED"
                entry["reason"] = "antenna pin set unknown for this part"
            elif not is_antenna:
                entry["status"] = "INFO"
                entry["reason"] = "not an antenna port"

            mod_report["pads"].append(entry)

        if mod_report.get("verdict") != "CANNOT-VERIFY":
            if any(p["status"] == "FAIL" for p in mod_report["pads"]):
                mod_report["verdict"] = "FAIL"
            else:
                mod_report["verdict"] = "PASS"
        report["modules"].append(mod_report)

    if report["failures"]:
        rc = 1
    elif report["unverified"]:
        rc = 2
    else:
        rc = 0
    report["exit_code"] = rc
    return report, rc


# --------------------------------------------------------------------------- #
# rendering / CLI
# --------------------------------------------------------------------------- #

def render_text(report):
    lines = []
    lines.append("antenna solder-access check (ADR-045) -- %s" % report.get("board"))
    if report.get("error"):
        lines.append("  ERROR: %s" % report["error"])
        lines.append("verdict: CANNOT-VERIFY (exit %d)" % report.get("exit_code", 2))
        return "\n".join(lines)
    lines.append("min access gap: %.4f mm   (pad is edge-accessible when its copper "
                 "reaches the module body outline)" % report["min_gap_mm"])
    for mod in report["modules"]:
        pins = mod["antenna_pins"]
        lines.append("")
        lines.append("footprint %s  (%s)  kind=%s  antenna pins=%s"
                     % (mod["ref"], mod["libid"], mod["kind"],
                        ",".join(pins) if pins else "UNKNOWN"))
        lines.append("  body: %s %s" % (mod["body_source"], mod["body_mm"]))
        lines.append("  courtyard: %s" % mod["courtyard_source"])
        lines.append("  %-5s %-9s %-8s %-10s %-8s %s"
                     % ("pad", "edge?", "antenna", "nearest", "gap/mm", "status"))
        for p in mod["pads"]:
            lines.append("  %-5s %-9s %-8s %-10s %-8s %s"
                         % (p["pad"],
                            "yes" if p["edge_accessible"] else "NO",
                            "yes" if p["antenna_port"] else "-",
                            p["nearest_other_ref"] or "-",
                            ("%.4f" % p["nearest_gap_mm"]) if p["nearest_gap_mm"] is not None else "-",
                            p["status"] + ((" -- " + p["reason"]) if p["reason"] else "")))
        if mod.get("unverified_reason"):
            lines.append("  UNVERIFIED: %s" % mod["unverified_reason"])
        lines.append("  verdict: %s" % mod["verdict"])
    if report["failures"]:
        lines.append("")
        lines.append("FAILURES (%d):" % len(report["failures"]))
        for f in report["failures"]:
            lines.append("  %s pad %s: %s" % (f["ref"], f["pad"], f["reason"]))
    if report["unverified"]:
        lines.append("")
        lines.append("CANNOT-VERIFY (%d):" % len(report["unverified"]))
        for u in report["unverified"]:
            lines.append("  %s: %s" % (u["ref"], u["reason"]))
    lines.append("")
    lines.append("verdict: %s (exit %d)"
                 % ({0: "PASS", 1: "FAIL", 2: "CANNOT-VERIFY"}[report["exit_code"]],
                    report["exit_code"]))
    return "\n".join(lines)


def _parse_overrides(values):
    out = {}
    for v in values or []:
        if ":" not in v:
            raise SystemExit("--antenna-pins expects REF:PIN[,PIN...], got %r" % v)
        ref, pins = v.split(":", 1)
        out[ref.strip()] = frozenset(p.strip() for p in pins.split(",") if p.strip())
    return out


def build_arg_parser():
    p = argparse.ArgumentParser(
        prog="antenna_access_check.py",
        description="Deterministic fail-closed antenna solder-access checker (ADR-045).")
    p.add_argument("boards", nargs="+", help="one or more .kicad_pcb paths")
    p.add_argument("--min-gap", type=float, default=DEFAULT_MIN_GAP_MM,
                   help="minimum access gap in mm (default %.1f)" % DEFAULT_MIN_GAP_MM)
    p.add_argument("--refs", nargs="+", default=None,
                   help="restrict to these reference designators")
    p.add_argument("--antenna-pins", action="append", default=[],
                   metavar="REF:PINS",
                   help="override antenna pin set, e.g. U2:9,10 (repeatable)")
    p.add_argument("--json", action="store_true", help="emit a JSON report")
    return p


def main(argv=None):
    if pcbnew is None:
        sys.stderr.write("antenna_access_check: python module 'pcbnew' (KiCad) "
                         "is not importable -> CANNOT-VERIFY\n")
        return 2
    args = build_arg_parser().parse_args(argv)
    overrides = _parse_overrides(args.antenna_pins)
    refs = set(args.refs) if args.refs else None

    worst = 0
    reports = []
    for board in args.boards:
        report, rc = build_report(board, args.min_gap, refs=refs, overrides=overrides)
        reports.append(report)
        if rc == 1:
            worst = 1
        elif rc == 2 and worst != 1:
            worst = 2

    if args.json:
        payload = reports[0] if len(reports) == 1 else {"boards": reports,
                                                        "exit_code": worst}
        if len(reports) == 1:
            payload["exit_code"] = worst
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for report in reports:
            report = dict(report)
            report["exit_code"] = worst if len(reports) == 1 else report["exit_code"]
            print(render_text(report))
            print()
    return worst


if __name__ == "__main__":
    sys.exit(main())
