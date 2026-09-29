#!/usr/bin/python3.14
"""
Independent verification of the 4-layer V2-ADC board (kanban t_9c0e1e8f).

Runs each gate from scratch against the artifact on disk. No cached results,
no trusting the design card's summary. Emits JSON evidence to stdout.

Usage: /usr/bin/python3.14 verify_4layer_evidence.py <board.kicad_pcb> <gerber_dir>
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

BOARD = sys.argv[1]
GERB = sys.argv[2]
OUT_DRC = sys.argv[3] if len(sys.argv) > 3 else "/tmp/4layer_drc.json"

ev = {}

# ---------- Gate A: from-scratch kicad-cli DRC ----------
r = subprocess.run(
    ["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
     "--output", OUT_DRC, BOARD],
    capture_output=True, text=True)
ev["drc_exit_code"] = r.returncode
ev["drc_stderr"] = r.stderr.strip()[-400:]
if os.path.exists(OUT_DRC):
    d = json.load(open(OUT_DRC))
    vtypes = {}
    for v in d.get("violations", []):
        vtypes[v.get("type", "?")] = vtypes.get(v.get("type", "?"), 0) + 1
    untypes = {}
    for u in d.get("unconnected_items", []):
        untypes[u.get("type", "unconnected_items")] = \
            untypes.get(u.get("type", "unconnected_items"), 0) + 1
    ev["drc_violations_total"] = len(d.get("violations", []))
    ev["drc_violations_by_type"] = vtypes
    ev["drc_unconnected_total"] = len(d.get("unconnected_items", []))
    ev["drc_unconnected_by_type"] = untypes
    ev["drc_shorts"] = vtypes.get("shorting_items", 0)

# ---------- Gate B: board object inventory ----------
b = pcbnew.LoadBoard(BOARD)
ev["copper_layer_count"] = b.GetCopperLayerCount()
lids = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
ev["copper_layers_enabled"] = [b.GetLayerName(l) for l in lids
                               if b.IsLayerEnabled(l)]
ev["footprints"] = len(list(b.GetFootprints()))
ev["nets_nonzero"] = len([n for n in b.GetNetInfo().NetsByNetcode().keys()
                          if n != 0])
ev["pads"] = sum(len(list(fp.Pads())) for fp in b.GetFootprints())
tracks = [t for t in b.GetTracks()]
ev["tracks_total"] = len(tracks)
ev["tracks_by_layer"] = {}
for t in tracks:
    ln = b.GetLayerName(t.GetLayer())
    ev["tracks_by_layer"][ln] = ev["tracks_by_layer"].get(ln, 0) + 1
ev["vias"] = len([t for t in tracks if t.Type() == pcbnew.PCB_VIA_T])

# Edge.Cuts bbox -> board area
bb = b.GetBoardEdgesBoundingBox()
area_mm2 = (bb.GetWidth() / 1e6) * (bb.GetHeight() / 1e6)
ev["edge_cuts_bbox_mm"] = [round(bb.GetWidth() / 1e6, 3),
                           round(bb.GetHeight() / 1e6, 3)]
ev["board_area_mm2"] = round(area_mm2, 2)

# ---------- Gates C/D/E/F: zones ----------
zones = list(b.Zones())
ev["zones_total"] = len(zones)
zinfo = []
for z in zones:
    lset = z.GetLayerSet()
    lnames = [b.GetLayerName(l) for l in lset.Seq()]
    zarea = z.Outline().Area() / 1e12  # nm^2 -> mm^2
    zinfo.append({
        "name": z.GetZoneName(),
        "net": z.GetNetname(),
        "layers": lnames,
        "area_mm2": round(zarea, 2),
        "coverage_pct_of_board": round(100.0 * zarea / area_mm2, 2)
        if area_mm2 else None,
        "is_filled": bool(z.IsFilled()),
    })
ev["zones"] = zinfo

gnd_in1 = [z for z in zinfo if "In1.Cu" in z["layers"] and z["net"] == "GND"]
v33_in2 = [z for z in zinfo if "In2.Cu" in z["layers"] and z["net"] == "3V3"]
signal_zones = [z for z in zinfo
                if ("F.Cu" in z["layers"] or "B.Cu" in z["layers"])]
ev["gate_gnd_zone_in1_exists"] = bool(gnd_in1)
ev["gate_gnd_zone_in1_coverage_pct"] = gnd_in1[0]["coverage_pct_of_board"] \
    if gnd_in1 else 0.0
ev["gate_3v3_zone_in2_exists"] = bool(v33_in2)
ev["gate_3v3_zone_in2_coverage_pct"] = v33_in2[0]["coverage_pct_of_board"] \
    if v33_in2 else 0.0
ev["gate_no_zone_on_fcu_bcu"] = (len(signal_zones) == 0)

# ---------- Gate G: gerbers ----------
gfiles = sorted(os.listdir(GERB)) if os.path.isdir(GERB) else []
ev["gerber_dir_exists"] = os.path.isdir(GERB)
ev["gerber_file_count"] = len(gfiles)
ev["gerber_files"] = {f: os.path.getsize(os.path.join(GERB, f))
                      for f in gfiles}
expected = ["%s-F_Cu.gtl", "%s-B_Cu.gbl", "%s-F_Mask.gts", "%s-B_Mask.gbs",
            "%s-F_Silkscreen.gto", "%s-B_Silkscreen.gbo",
            "%s-Edge_Cuts.gm1", "%s.drl"]
base = os.path.splitext(os.path.basename(BOARD))[0]
ev["gerber_expected_present"] = {e % base: os.path.exists(
    os.path.join(GERB, e % base)) for e in expected}

# copper-content probe: a non-empty F_Cu gerber has >=1 flash/draw op (D01/D03)
def copper_ops(path):
    try:
        txt = open(path, errors="replace").read()
    except OSError:
        return None
    return txt.count("D01") + txt.count("D03") + txt.count("D02")

fc = os.path.join(GERB, "%s-F_Cu.gtl" % base)
bc = os.path.join(GERB, "%s-B_Cu.gbl" % base)
ev["fcu_gtl_size"] = os.path.getsize(fc) if os.path.exists(fc) else None
ev["fcu_gtl_copper_ops"] = copper_ops(fc) if os.path.exists(fc) else None
ev["bcu_gbl_size"] = os.path.getsize(bc) if os.path.exists(bc) else None
ev["bcu_gbl_copper_ops"] = copper_ops(bc) if os.path.exists(bc) else None

# drill hole count
drl = os.path.join(GERB, "%s.drl" % base)
if os.path.exists(drl):
    dtxt = open(drl, errors="replace").read()
    ev["drl_size"] = os.path.getsize(drl)
    ev["drl_coordinate_lines"] = dtxt.count("X") if "X" in dtxt else 0
    ev["drl_has_tools"] = "T1" in dtxt

print(json.dumps(ev, indent=2))
