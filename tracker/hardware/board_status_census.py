#!/usr/bin/env python3
"""board_status_census.py — machine census of PCB routing state, per board.

Emits JSON.  Every number that ends up in the board-status figure comes from
here; nothing in the figure is hand-typed.

Run with /usr/bin/python3.14 (pcbnew is only importable there).

  /usr/bin/python3.14 board_status_census.py board1.kicad_pcb board2.kicad_pcb ...

Counts, per board:
  * copper layer count, footprint count
  * per copper layer: track segments, total track length (mm), vias, zones
    (filled / unfilled)
  * pads split by mounting side: front (F.Cu), back (B.Cu), through-hole
  * DRC unconnected items (kicad-cli, authoritative) and a routed verdict

The verdict is derived from the counts, not asserted by a human:
  placed_only   no segments, no vias, no zones
  partial       some copper, but DRC reports unconnected items
  routed        copper present and DRC reports zero unconnected items
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pcbnew  # only importable under /usr/bin/python3.14

# KiCad copper layer ids.  F_Cu = 0 and B_Cu = 31 are fixed; a 4-layer board
# additionally enables In1_Cu and In2_Cu.
LAYER_IDS = (
    ("F.Cu", pcbnew.F_Cu),
    ("In1.Cu", pcbnew.In1_Cu),
    ("In2.Cu", pcbnew.In2_Cu),
    ("B.Cu", pcbnew.B_Cu),
)

SMD = pcbnew.PAD_ATTRIB_SMD
PTH = pcbnew.PAD_ATTRIB_PTH
NPTH = pcbnew.PAD_ATTRIB_NPTH
CONN = pcbnew.PAD_ATTRIB_CONN


def drc_unconnected(path: Path) -> int | None:
    """Authoritative unconnected count from kicad-cli.  None if DRC failed."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        out = Path(tmp.name)
    try:
        proc = subprocess.run(
            ["kicad-cli", "pcb", "drc", "--format", "json",
             "--severity-all", "-o", str(out), str(path)],
            capture_output=True, text=True, timeout=600,
        )
        if proc.returncode != 0 or not out.exists():
            return None
        with out.open() as fh:
            report = json.load(fh)
        return len(report.get("unconnected_items", []))
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return None
    finally:
        out.unlink(missing_ok=True)


def census(path: Path, with_drc: bool = True) -> dict:
    board = pcbnew.LoadBoard(str(path))
    if board is None:
        raise SystemExit(f"cannot load {path}")

    layers = {name: {"segments": 0, "length_mm": 0.0, "vias": 0,
                     "zones": 0, "zones_filled": 0}
              for name, _ in LAYER_IDS}
    by_id = {lid: name for name, lid in LAYER_IDS}

    for item in board.GetTracks():
        lid = item.GetLayer()
        name = by_id.get(lid, pcbnew.LayerName(lid))
        slot = layers.setdefault(name, {"segments": 0, "length_mm": 0.0,
                                        "vias": 0, "zones": 0,
                                        "zones_filled": 0})
        if item.GetClass() == "PCB_VIA":
            slot["vias"] += 1
        else:
            slot["segments"] += 1
            slot["length_mm"] += item.GetLength() / 1e6

    for zone in board.Zones():
        lid = zone.GetLayer()
        name = by_id.get(lid, pcbnew.LayerName(lid))
        slot = layers.setdefault(name, {"segments": 0, "length_mm": 0.0,
                                        "vias": 0, "zones": 0,
                                        "zones_filled": 0})
        slot["zones"] += 1
        if zone.IsFilled():
            slot["zones_filled"] += 1

    pads = {"front": 0, "back": 0, "through": 0, "npth": 0}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            attr = pad.GetAttribute()
            if attr == NPTH:
                pads["npth"] += 1
                continue
            if attr in (PTH, CONN):
                pads["through"] += 1
                continue
            lset = pad.GetLayerSet()
            if lset.Contains(pcbnew.F_Cu):
                pads["front"] += 1
            elif lset.Contains(pcbnew.B_Cu):
                pads["back"] += 1

    result = {
        "file": str(path),
        "name": path.stem,
        "copper_layers": board.GetCopperLayerCount(),
        "footprints": len(board.GetFootprints()),
        "pads": pads,
        "layers": layers,
        "totals": {
            "segments": sum(v["segments"] for v in layers.values()),
            "vias": sum(v["vias"] for v in layers.values()),
            "zones": sum(v["zones"] for v in layers.values()),
            "zones_filled": sum(v["zones_filled"] for v in layers.values()),
        },
        "drc_unconnected": drc_unconnected(path) if with_drc else None,
    }

    t = result["totals"]
    # A via's GetLayer() is only its primary layer, so per-layer via counts would
    # mislead; vias are reported board-total only (see figure caption).
    if t["segments"] == 0 and t["vias"] == 0 and t["zones"] == 0:
        result["verdict"] = "placed_only"
    elif t["segments"] == 0 and t["vias"] == 0 and t["zones"] > 0:
        result["verdict"] = "plane_only"
    elif result["drc_unconnected"] == 0:
        result["verdict"] = "routed"
    else:
        result["verdict"] = "partial"
    return result


def main(argv: list[str]) -> int:
    with_drc = "--no-drc" not in argv
    paths = [Path(a) for a in argv if not a.startswith("--")]
    if not paths:
        print(__doc__)
        return 2
    out = [census(p, with_drc=with_drc) for p in paths]
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
