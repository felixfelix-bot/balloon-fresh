#!/usr/bin/env python3
"""Fab preflight: gate the hub board on REAL defects only.

WHY -- the board has 4 families of intentional geometry (see
docs/HUB-V9-DRC-EXCLUSIONS.md) that every checker flags forever: edge-card
socket lands outside the outline, slot Edge.Cuts at the copper edge, and the
F-B pad pairs the inserted wing tab bridges mechanically. A gate that reports
them as defects is a gate nobody can pass, so it gets ignored -- the failure
mode that makes fab gates useless.

This script consumes a KiCad DRC JSON report and splits it into WAIVED (by
documented family) and REAL. Exit code: 0 iff zero REAL errors remain.

Usage:
  kicad-cli pcb drc --severity-error --format json -o /tmp/drc.json BOARD
  python3 tracker/hardware/fab_preflight.py /tmp/drc.json [--verbose]
"""
from __future__ import annotations

import argparse
import json
import re
import sys

# Waiver families -- MUST match docs/HUB-V9-DRC-EXCLUSIONS.md
EDGE_FAMILIES = ("J_W", "ANT", "CUT_SENSE")


def is_waived(violation: dict) -> tuple[bool, str]:
    """Return (waived, family) for one KiCad DRC violation."""
    vtype = violation.get("type", "")
    items = violation.get("items", [])
    descs = " ".join(it.get("description", "") for it in items)

    # W1: unconnected items where ALL mentions are edge-card wing/antenna pads
    if vtype == "unconnected_items":
        refs = re.findall(r"\b(J_W\d|ANT\d|CUT_SENSE\w*)\b", descs)
        if refs and len(set(refs)) >= 1 and "Pad" in descs:
            # every item must reference an edge family
            n_items = len(items)
            n_edge = sum(1 for it in items
                         if re.search(r"\b(J_W\d|ANT\d|CUT_SENSE\w*)", it.get("description", "")))
            if n_items and n_edge == n_items:
                return True, "W1-socket-fb-pair"

    # W2/W3: copper edge clearance on the SOCKET LAND itself (pad geometry) or
    # on ATTRIBUTED slot outline graphics of the wing sockets. NEVER a Track,
    # Via or Zone: those are real routing geometry that must respect edge
    # clearance. NEVER an anonymous "Rectangle on Edge.Cuts": the report gives
    # it pos (0,0), so we cannot prove it is a socket slot -- require the
    # footprint name (e.g. "Segment of J_W1 on Edge.Cuts").
    if vtype == "copper_edge_clearance":
        for it in items:
            dsc = it.get("description", "")
            # pad lands of the socket (attributed by definition: "Pad N of J_Wx")
            if "Pad" in dsc and re.search(r"\b(J_W\d|ANT\d|CUT_SENSE\w*)", dsc) \
                    and "Track" not in dsc and "Via" not in dsc:
                return True, "W2-socket-land"
            # attributed slot outline graphics
            if re.search(r"(Segment|Rectangle|Circle|Arc) of (J_W\d|ANT\d|CUT_SENSE)", dsc):
                return True, "W3-slot-outline"

    return False, ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    d = json.load(open(args.report))
    viols = d.get("violations", []) + d.get("unconnected_items", [])

    waived, real = [], []
    for v in viols:
        ok, fam = is_waived(v)
        (waived if ok else real).append((v, fam))

    print(f"fab preflight: {len(viols)} items -> "
          f"{len(waived)} waived (documented), {len(real)} REAL")
    if waived:
        from collections import Counter
        print("  waived families:", dict(Counter(f for _, f in waived)))
    if real:
        from collections import Counter
        print("  REAL by type:", dict(Counter(v.get("type") for v, _ in real)))
        if args.verbose:
            for v, _ in real:
                first = v.get("items", [{}])[0].get("description", v.get("type", ""))
                print(f"    - [{v.get('type')}] {first[:90]}")
        return 1
    print("  -> GATE PASS (no real errors)")
    return 0


if __name__ == "__main__":
    sys.exit(main())