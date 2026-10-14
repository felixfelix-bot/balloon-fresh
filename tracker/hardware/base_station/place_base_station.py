#!/usr/bin/env python3
"""Place the base-station PCBA v1 board.

Reuses the hub's PROVEN machinery by importing it as a module, but does its OWN footprint loading
with a fresh pcbnew import, because importing the hub builder via importlib leaves pcbnew's
FootprintLoad plugin as None:

    AttributeError: 'NoneType' object has no attribute 'FootprintLoad'

MEASURED 2026-10-14: `pcbnew.FootprintLoad` works fine in a bare interpreter on the SAME library
path, so the fault is the import ORDER, not the library. The fix is to import pcbnew and load the
footprints BEFORE pulling in the hub builder as a module.

Run: python3 base_station/place_base_station.py --outline 60x45
"""
import argparse
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)                      # tracker/hardware
REPO = os.path.dirname(os.path.dirname(HW))

sys.path.insert(0, "/usr/lib/python3/dist-packages")

NETLIST = os.path.join(HERE, "base_station_v1.net")
OUT = os.path.join(HERE, "base_station_v1_placed.kicad_pcb")


def _hubgen():
    spec = importlib.util.spec_from_file_location("hubgen", os.path.join(HW, "build_hub_board_v9.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def load(w, h):
    """Load the netlist into a scaffolded board. pcbnew is imported HERE, before _hubgen()."""
    import pcbnew
    hubgen = _hubgen()

    comps, nets = hubgen.read_netlist(NETLIST)
    scaf = os.path.join(HERE, "output", ".bs_v1_scaffold.kicad_pcb")
    os.makedirs(os.path.dirname(scaf), exist_ok=True)
    with open(scaf, "w") as f:
        f.write(hubgen.scaffold_text(w, h))
    pcbnew.KIID.SeedGenerator(20261014)
    board = pcbnew.LoadBoard(scaf)
    if board is None:
        raise SystemExit("scaffold failed to load")

    for _code, name, _n in nets:
        if name and board.FindNet(name) is None:
            board.Add(pcbnew.NETINFO_ITEM(board, name))

    pin_net = {(r, p): n for _c, n, nodes in nets for r, p in nodes}

    # local libs first (they need normalisation), then the standard KiCad library verbatim
    lib_dirs = {}
    # repo-local libs first: the hub's own v9 libs, PLUS this board's vendored library
    local = dict(hubgen.LOCAL_LIBS)
    local["base_station_lib"] = os.path.join(HERE, "library.pretty")
    for lib, d in local.items():
        lib_dirs[lib] = hubgen.normalise_library(
            d, os.path.join(hubgen.LIB_CACHE, lib + ".pretty"))

    placed, skipped = [], []
    for c in comps:
        if not c["lib_id"]:
            skipped.append(c)
            continue
        lib, name = c["lib_id"].split(":", 1)
        libdir = lib_dirs.get(lib, os.path.join(hubgen.KICAD_PRETTY, f"{lib}.pretty"))
        if not os.path.isdir(libdir):
            print(f"   MISSING LIB  {c['ref']:10s} {c['lib_id']}  ({libdir})")
            skipped.append(c)
            continue
        fp = pcbnew.FootprintLoad(libdir, name)
        if fp is None:
            print(f"   LOAD FAILED  {c['ref']:10s} {c['lib_id']}  ({libdir})")
            skipped.append(c)
            continue
        fp.SetReference(c["ref"])
        fp.SetValue(c["value"])
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        for pad in fp.Pads():
            nm = pin_net.get((c["ref"], pad.GetNumber()))
            if nm:
                pad.SetNet(board.FindNet(nm))
        board.Add(fp)
        placed.append((c["ref"], fp))
    return board, placed, skipped, comps, nets


def main() -> int:
    import pcbnew
    ap = argparse.ArgumentParser()
    ap.add_argument("--outline", default="60x45", help="board outline WxH in mm")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    w, h = (float(v) for v in a.outline.lower().split("x"))

    board, placed, skipped, comps, nets = load(w, h)
    hubgen = _hubgen()
    overflow = hubgen.pack_rest(board, placed, [], w, h)
    planes = hubgen.add_gnd_plane(board, w, h)
    pcbnew.SaveBoard(a.out, board)

    print(f"netlist    : {os.path.relpath(NETLIST, REPO)}")
    print(f"components : {len(comps)} on netlist / {len(placed)} placed / {len(skipped)} skipped")
    for s in skipped:
        print(f"   skipped     {s['ref']:10s} {s['value'][:40]}")
    print(f"nets       : {len(nets)}")
    print(f"outline    : {w} x {h} mm")
    print(f"gnd planes : {planes or 'none'}")
    if overflow:
        print(f"OVERFLOW   : {len(overflow)} did not seat: {overflow[:10]}")
    print(f"board      : {os.path.relpath(a.out, REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
