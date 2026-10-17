"""How much routing depends on the J_W* wing-socket pads?

WHY. The wing-interface fix (rotations made consistent, inboard offset 5.20 -> 0.00) currently lives ONLY in
tracker/hardware/output/hub_board_v9_seed.kicad_pcb. The board that actually goes to the fabricator is
tracker/hardware/hub_board_v9.kicad_pcb (regen_fab_package.py DEFAULT_BOARD), and that board still carries
the defect: J_W1/J_W3 slots buried 5.25 mm inboard, J_W2/J_W4 crossing their edges by 0.75 mm.

Moving the footprints would move their pads, so any track ending on a J_W* pad would need re-routing. This
measures that cost BEFORE anyone decides to apply the fix.
"""

import pcbnew

BOARD = "tracker/hardware/hub_board_v9.kicad_pcb"
TOL_NM = 1000  # 1 micron, in KiCad internal units (nanometres)


def main() -> int:
    b = pcbnew.LoadBoard(BOARD)
    print(f"board: {BOARD}")
    print(f"  footprints: {len(b.GetFootprints())}")

    pad_pos = {}
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if ref.startswith("J_W"):
            for p in fp.Pads():
                pad_pos[(ref, p.GetNumber())] = p.GetPosition()

    print(f"  J_W* footprints: {len({k[0] for k in pad_pos})}")
    print(f"  J_W* pads: {len(pad_pos)}")

    tracks = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T]
    vias = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
    print(f"  tracks: {len(tracks)}   vias: {len(vias)}")

    on_pad, on_via = set(), set()
    for t in tracks:
        s, e = t.GetStart(), t.GetEnd()
        for key, pos in pad_pos.items():
            for pt in (s, e):
                if abs(pt.x - pos.x) <= TOL_NM and abs(pt.y - pos.y) <= TOL_NM:
                    on_pad.add(key)
    for v in vias:
        vp = v.GetPosition()
        for key, pos in pad_pos.items():
            if abs(vp.x - pos.x) <= TOL_NM and abs(vp.y - pos.y) <= TOL_NM:
                on_via.add(key)

    print()
    print(f"  J_W* pads with a TRACK endpoint on them: {len(on_pad)}")
    print(f"  J_W* pads with a VIA on them:            {len(on_via)}")
    touched = sorted({k[0] for k in on_pad} | {k[0] for k in on_via})
    print(f"  J_W* footprints electrically touched:    {touched if touched else 'NONE'}")

    print()
    if not touched:
        print("  => the wing sockets carry NO copper connections on this board.")
        print("     Moving them would not disturb any routed net; the cost is placement + DRC only.")
    else:
        print("  => moving these footprints WOULD disturb routed nets; those nets need re-routing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
