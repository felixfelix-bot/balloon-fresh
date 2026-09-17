#!/usr/bin/env python3
"""PCB-S0b: apply the operator-decided netlist ties to a COPY of the frozen flight board.

Card: t_a1f8e389.  The frozen placement artefact
`output/v_c3_flight_4layer_placed.kicad_pcb` (sha256 f3cf0143…) is the comparability
anchor for S1/S2 and is left BYTE-IDENTICAL.  This tool writes the netlist of record
next to it, so a later routing pass has a correct netlist to route:

    output/v_c3_flight_4layer_placed.kicad_pcb       (frozen placement, unchanged)
        -> output/v_c3_flight_4layer_placed_netfix.kicad_pcb   (netlist of record)

Three pads that carried no net are tied, all to nets that already exist on the board
(so NO footprint, track, via or zone is added or moved, and the net table is unchanged):

  U4.3  EN      -> VCAP   TPS7A02 DBV pin 3, EN.  The part has a smart enable pulldown:
                          a floating EN is pulled LOW internally, i.e. the 3V3 rail is
                          never enabled.  TI SBVS277C Table 5-1/§7.3.4.  VCAP is the
                          regulator's own input rail (U4.1 = IN = VCAP), and the EC
                          table is specified at VEN = VIN, so EN-to-IN is the
                          datasheet's always-on configuration.  "Pull EN high to VIN".
  U3.9  RESET_N -> +3V3   MAX-M10S active-low reset.  U-BLOX UBX-20035208 Table 10 p.9:
                          "System reset (active low). Has to be low for at least 1 ms to
                          trigger a reset."  Tied high = never in reset (Table 11 lists
                          an internal 7–13 kΩ pull-up; the tie is deterministic, not
                          dependent on it).
  U3.6  V_BCKP  -> +3V3   MAX-M10S backup supply, 1.65–3.6 V (UBX-20035208 Table 10 p.9
                          / supply table).  +3V3 = 3.3 V is in range -> hot-start backup.

Run (KiCad 9 needs the 3.14 interpreter):

    /usr/bin/python3.14 tracker/hardware/netlist_fix_s0b.py            # apply + verify
    /usr/bin/python3.14 tracker/hardware/netlist_fix_s0b.py --check    # verify only

Exit codes: 0 = applied and all invariants hold, 1 = an invariant failed, 2 = usage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402  (KiCad 9 python module, python3.14)

HERE = Path(__file__).resolve().parent
SRC = HERE / "output" / "v_c3_flight_4layer_placed.kicad_pcb"
DST = HERE / "output" / "v_c3_flight_4layer_placed_netfix.kicad_pcb"
SRC_SHA256 = "f3cf0143e7deff991e9650643f1322945388fd135efbf5191f51520dcd6edaa6"

# (ref, pad number) -> (net name, why)
FIXES = {
    ("U4", "3"): ("VCAP", "TPS7A02 EN: smart enable pulldown holds a floating EN low -> "
                          "rail never enabled; tie to the input rail IN=VCAP (TI SBVS277C "
                          "Table 5-1 p.3, §7.3.4, EC table spec'd at VEN=VIN)"),
    ("U3", "9"): ("+3V3", "MAX-M10S RESET_N (active low): tie high so the module is never "
                          "held in reset; internal 7-13k pull-up is the fallback "
                          "(UBX-20035208 Table 10 p.9 / Table 11)"),
    ("U3", "6"): ("+3V3", "MAX-M10S V_BCKP backup supply 1.65-3.6 V; +3V3 = 3.3 V in range, "
                          "enables hot-start backup (UBX-20035208 Table 10 p.9)"),
}
SIBLINGS = (".kicad_dru", ".kicad_pro")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def census(board):
    """Full pad/net/position census used for the before/after invariants.

    Pads are keyed `ref.padnum`; unnamed library pads (U1 carries 9 of them) share an
    empty pad number, so they are keyed `ref.#n` in footprint order - a census that
    collapsed them would under-count the netless pads the audit is about.
    """
    pads = {}
    fps = {}
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        pos = fp.GetPosition()
        fps[ref] = [round(pcbnew.ToMM(pos.x), 4), round(pcbnew.ToMM(pos.y), 4),
                    round(fp.GetOrientationDegrees(), 4),
                    fp.GetFPID().GetUniStringLibId()]
        unnamed = 0
        for p in fp.Pads():
            num = p.GetNumber()
            key = f"{ref}.{num}"
            if not num:
                unnamed += 1
                key = f"{ref}.#{unnamed}"
            pp = p.GetPosition()
            pads[key] = {
                "net": p.GetNetname(),
                "size": [round(pcbnew.ToMM(p.GetSize().x), 4), round(pcbnew.ToMM(p.GetSize().y), 4)],
                "pos": [round(pcbnew.ToMM(pp.x), 4), round(pcbnew.ToMM(pp.y), 4)],
            }
    nets = sorted(n.GetNetname() for n in board.GetNetInfo().NetsByNetcode().values()
                  if n.GetNetname())
    coop = {"segments": len([t for t in board.GetTracks()
                             if t.Type() == pcbnew.PCB_TRACE_T]),
            "vias": len([t for t in board.GetTracks()
                         if t.Type() == pcbnew.PCB_VIA_T]),
            "zones": len(list(board.Zones()))}
    return {"pads": pads, "footprints": fps, "nets": nets, "copper": coop}


def check(src_census, dst_census, report):
    ok = True

    def fail(msg):
        nonlocal ok
        ok = False
        report["failures"].append(msg)

    if src_census["footprints"] != dst_census["footprints"]:
        a, b = src_census["footprints"], dst_census["footprints"]
        diff = {k: (a.get(k), b.get(k)) for k in set(a) | set(b) if a.get(k) != b.get(k)}
        fail(f"PLACEMENT CHANGED for {sorted(diff)}: {diff[:3] if isinstance(diff, list) else diff}")
    else:
        report["placement_identical"] = f"{len(src_census['footprints'])} footprints, "
        report["placement_identical"] += "position+rotation+footprint identical"

    if src_census["copper"] != dst_census["copper"]:
        fail(f"COPPER CHANGED: {src_census['copper']} -> {dst_census['copper']}")
    else:
        report["copper_unchanged"] = src_census["copper"]

    changed = {}
    for k, v in src_census["pads"].items():
        w = dst_census["pads"].get(k)
        if w is None:
            fail(f"pad {k} disappeared")
            continue
        if v["net"] != w["net"]:
            changed[k] = [v["net"], w["net"]]
        if v["pos"] != w["pos"] or v["size"] != w["size"]:
            fail(f"pad {k} moved/resized: {v} -> {w}")
    report["pads_whose_net_changed"] = changed
    expected = {f"{r}.{p}": [None, n] for (r, p), (n, _) in FIXES.items()}
    expected = {k: ["", v[1]] for k, v in expected.items()}
    if changed != expected:
        fail(f"unexpected net-change set: expected {expected}, got {changed}")

    if src_census["nets"] != dst_census["nets"]:
        fail(f"net table changed: {src_census['nets']} -> {dst_census['nets']}")
    else:
        report["net_table_unchanged"] = len(src_census["nets"])

    before = sum(1 for v in src_census["pads"].values() if not v["net"])
    after = sum(1 for v in dst_census["pads"].values() if not v["net"])
    report["pads_with_no_net"] = {"before": before, "after": after}
    if before - after != len(FIXES):
        fail(f"netless pad count fell by {before - after}, expected {len(FIXES)}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(SRC))
    ap.add_argument("--out", default=str(DST))
    ap.add_argument("--check", action="store_true",
                    help="verify the existing output instead of writing it")
    a = ap.parse_args()

    src, out = Path(a.src), Path(a.out)
    if not src.exists():
        print(f"missing source board {src}")
        return 2

    src_sha = sha256(src)
    report = {"source": str(src), "source_sha256": src_sha,
              "expected_source_sha256": SRC_SHA256,
              "source_is_the_frozen_placement": src_sha == SRC_SHA256,
              "fixes": {f"{r}.{p}": {"net": n, "why": w} for (r, p), (n, w) in FIXES.items()},
              "failures": []}

    board = pcbnew.LoadBoard(str(src))
    src_census = census(board)

    if a.check:
        if not out.exists():
            print(f"missing output board {out}")
            return 2
        dst_census = census(pcbnew.LoadBoard(str(out)))
    else:
        for (ref, padnum), (netname, _why) in FIXES.items():
            fp = next((f for f in board.GetFootprints() if f.GetReference() == ref), None)
            if fp is None:
                print(f"footprint {ref} not found")
                return 1
            pad = next((p for p in fp.Pads() if p.GetNumber() == padnum), None)
            if pad is None:
                print(f"pad {ref}.{padnum} not found")
                return 1
            if pad.GetNetname():
                print(f"pad {ref}.{padnum} already carries net {pad.GetNetname()!r} - refusing")
                return 1
            net = board.FindNet(netname)
            if net is None:
                print(f"net {netname!r} does not exist on the board - refusing to invent it")
                return 1
            pad.SetNet(net)
            print(f"set {ref}.{padnum} -> {netname} (netcode {net.GetNetCode()})")
        board.BuildConnectivity()
        pcbnew.SaveBoard(str(out), board)
        dst_census = census(pcbnew.LoadBoard(str(out)))

    ok = check(src_census, dst_census, report)

    # the delivery siblings: identical rule + project files, as in S1
    if not a.check:
        for ext in SIBLINGS:
            s = src.with_suffix(ext)
            d = out.with_suffix(ext)
            if s.exists():
                shutil.copyfile(s, d)
                same = sha256(s) == sha256(d)
                report.setdefault("siblings", {})[d.name] = {
                    "sha256": sha256(d), "identical_to_source_sibling": same}
                if not same:
                    ok = False
                    report["failures"].append(f"sibling {d.name} not byte-identical")
    report["output"] = str(out)
    report["output_sha256"] = sha256(out) if out.exists() else None
    report["verdict"] = "PASS" if ok else "FAIL"

    dest = HERE / "output" / "s0b"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "netlist_fix_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
