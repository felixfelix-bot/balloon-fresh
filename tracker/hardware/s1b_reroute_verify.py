#!/usr/bin/python3.14
"""PCB-S1b verifier: the re-routed board must (a) move no footprint and (b) ship
the S0b netlist of record intact — including the three pads S0b newly netted.

WHY IT EXISTS
-------------
S1b re-routes from `v_c3_flight_4layer_placed_netfix.kicad_pcb` (netlist of
record, sha `aa76fbbb…`) instead of the pre-S0b board.  Two properties have to
be proven on the OUTPUT board, not asserted:

  P1 no placement drift — every footprint's position / orientation / layer /
     library identity is bit-identical to the frozen S0 placement
     (`v_c3_flight_4layer_placed.kicad_pcb`, sha `f3cf0143…`).
  P2 netlist of record intact — the pad->net map is identical to the netlist of
     record, so `U4.3` (TPS7A02 EN) really does carry `VCAP`, `U3.6` and
     `U3.9` really do carry `+3V3`, and no previously-netless pad was silently
     netted.
  P3 the three S0b nets carry copper and the ratsnest is closed (KiCad's own
     connectivity engine, not the router's self-report).

No coordinate literals (placement_guard R2): all geometry comes from the two
board files.  Nothing is written; this is read-only evidence.

usage: s1b_reroute_verify.py <routed.kicad_pcb> [<frozen_placement.kicad_pcb>
                                                  [<netlist_of_record.kicad_pcb>]]
exit 0 = P1+P2+P3 hold
"""
from __future__ import annotations

import sys

sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew  # noqa: E402

FROZEN_PLACEMENT = "output/v_c3_flight_4layer_placed.kicad_pcb"
NETLIST_OF_RECORD = "output/v_c3_flight_4layer_placed_netfix.kicad_pcb"

TOL_NM = 0  # bit-identical placement


def placement_map(board) -> dict:
    out = {}
    for fp in board.GetFootprints():
        p = fp.GetPosition()
        out[fp.GetReference()] = {
            "xy": (p.x, p.y),
            "rot": round(fp.GetOrientationDegrees(), 6),
            "layer": fp.GetLayer(),
            "libid": str(fp.GetFPID().GetLibItemName()),
            "value": fp.GetValue(),
        }
    return out


def pad_net_map(board) -> dict:
    out = {}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            out[f"{fp.GetReference()}.{pad.GetNumber()}"] = pad.GetNetname()
    return out


def copper_on(board, netname: str) -> tuple[int, int]:
    segs = vias = 0
    for t in board.GetTracks():
        if t.GetNetname() != netname:
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            vias += 1
        else:
            segs += 1
    return segs, vias


def open_ratsnest(board) -> int:
    """KiCad's own connectivity: number of unconnected items left."""
    board.BuildConnectivity()
    conn = board.GetConnectivity()
    # KiCad 9: CONNECTIVITY_DATA.GetUnconnectedCount(); older builds expose the
    # ratsnest list instead.  Try both rather than pinning one API.
    if hasattr(conn, "GetUnconnectedCount"):
        try:
            return int(conn.GetUnconnectedCount(False))  # KiCad 9: (visible_only)
        except TypeError:
            return int(conn.GetUnconnectedCount())
    return len(conn.GetUnconnectedRatsnest())


def main() -> int:
    routed_p = sys.argv[1]
    frozen_p = sys.argv[2] if len(sys.argv) > 2 else FROZEN_PLACEMENT
    record_p = sys.argv[3] if len(sys.argv) > 3 else NETLIST_OF_RECORD

    routed = pcbnew.LoadBoard(routed_p)
    frozen = pcbnew.LoadBoard(frozen_p)
    record = pcbnew.LoadBoard(record_p)

    rc = 0

    # ---- P1 placement parity ------------------------------------------------
    a, b = placement_map(frozen), placement_map(routed)
    moved = []
    for ref in sorted(set(a) | set(b)):
        if ref not in a:
            moved.append((ref, "EXTRA on routed board"))
            continue
        if ref not in b:
            moved.append((ref, "MISSING on routed board"))
            continue
        if a[ref]["xy"] != b[ref]["xy"] or a[ref]["rot"] != b[ref]["rot"] \
                or a[ref]["layer"] != b[ref]["layer"] \
                or a[ref]["libid"] != b[ref]["libid"]:
            moved.append((ref, f"{a[ref]} -> {b[ref]}"))
    print(f"P1 placement: {len(b)} footprints on the routed board, "
          f"{len(a)} on the frozen placement, moved/extra/missing = {len(moved)}")
    for ref, why in moved:
        print(f"   P1 FAIL {ref}: {why}")
    rc |= 1 if moved else 0

    # ---- P2 netlist of record parity ---------------------------------------
    r, o = pad_net_map(record), pad_net_map(routed)
    diff = []
    for key in sorted(set(r) | set(o)):
        if r.get(key) != o.get(key):
            diff.append((key, r.get(key), o.get(key)))
    print(f"P2 netlist: {len(o)} pads on the routed board, {len(r)} on the "
          f"netlist of record, pad/net differences = {len(diff)}")
    for key, want, got in diff:
        print(f"   P2 FAIL {key}: record={want!r} routed={got!r}")
    ties = {"U4.3": "VCAP", "U3.6": "+3V3", "U3.9": "+3V3"}
    for pad, net in ties.items():
        got = o.get(pad)
        ok = got == net
        print(f"   P2 {'ok  ' if ok else 'FAIL'} {pad} -> {got!r} (S0b tie, want {net!r})")
        rc |= 0 if ok else 1
    rc |= 1 if diff else 0

    # ---- P3 copper on the three S0b nets + closed ratsnest -----------------
    for net in ("VCAP", "+3V3", "GND"):
        segs, vias = copper_on(routed, net)
        print(f"P3 copper: net {net:<6} {segs} segments, {vias} vias")
        rc |= 0 if segs + vias > 0 else 1
    nets_pads = {}
    for fp in routed.GetFootprints():
        for pad in fp.Pads():
            nets_pads.setdefault(pad.GetNetname(), []).append(
                f"{fp.GetReference()}.{pad.GetNumber()}")
    vcap_pads = sorted(p for p in nets_pads.get("VCAP", []) if p in ("U4.1", "U4.3"))
    print(f"P3 VCAP pads present on the routed board: {vcap_pads}")
    open_ = open_ratsnest(routed)
    print(f"P3 KiCad connectivity: unconnected ratsnest lines = {open_} "
          f"(fp {len(list(routed.GetFootprints()))})")
    rc |= 1 if open_ else 0

    print("VERDICT:", "PASS" if rc == 0 else "FAIL")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
