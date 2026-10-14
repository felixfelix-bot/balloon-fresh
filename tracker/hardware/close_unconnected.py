#!/usr/bin/env python3
"""Close the 5 unconnected items on the hub board -- two distinct faults, two distinct fixes.

FAULT A -- /SX1280_MISO: the router left a 0.0510 mm stub. A 51-micron segment is not a route, it is
an artifact, and it is why the net reports as failed. The two pads are U4.9 at (52.000, 28.200) and
U1.9 at (49.950, 13.110) -- about 15.2 mm apart, which is why the router could not finish it.

FAULT B -- Pad 2 [GND] of J_W2 and J_W3: the F.Cu pad and the B.Cu pad are DISTINCT items with NO
hole, so they are NOT plated through to each other, and neither reaches its plane. MEASURED: J_W2's
pad spans y 67.200..68.400 with the board bottom at 71.650 (3.025 mm to the pad edge) and J_W3's pad
spans x 59.800..63.800 with the board right at 70.150 (8.275 mm). So these are SURFACE pads sitting
inside the pour, and the pour's 0.200 mm clearance is not reaching them -- J_W1 and J_W4 are fine,
which localises the fault to the two sockets whose pad geometry differs.

FIX for B is a VIA AT THE PAD CENTRE. The repo already uses exactly this idiom: fab_grade.sh's
stitch_gnd_planes.py reports "vias at pad centre: 15", and a via at the pad centre joins F.Cu and
B.Cu and gives the pour a target on both layers without moving any existing copper. That is
deliberately NOT a new invention -- it is the repo's own established method, applied to the two pads
the DRC named.

Usage:  ~/venvs/kicad/bin/python close_unconnected.py <board> <out> [--check]
"""
import os
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

SRC = sys.argv[1]
DST = sys.argv[2]
CHECK = "--check" in sys.argv

VIA_DIA = 0.6      # the board's frozen via size
VIA_DRILL = 0.3    # the board's frozen via drill
TRACK_W = 0.2      # the board's frozen track width

board = pcbnew.LoadBoard(SRC)
MM = pcbnew.ToMM


def net_by_name(name):
    for code, ni in board.GetNetInfo().NetsByNetcode().items():
        if ni.GetNetname() == name:
            return ni
    return None


# ---------------------------------------------------------------- A. the stub on /SX1280_MISO
print("=== A. /SX1280_MISO stub ===")
stub_removed = 0
todel = []
for t in board.GetTracks():
    if t.GetNetname() == "/SX1280_MISO" and t.Type() == pcbnew.PCB_TRACE_T:
        if MM(t.GetLength()) < 0.10:
            todel.append(t)
for t in todel:
    s, e = t.GetStart(), t.GetEnd()
    print(f"  removing stub len {MM(t.GetLength()):.4f} mm "
          f"({MM(s.x):.3f},{MM(s.y):.3f}) -> ({MM(e.x):.3f},{MM(e.y):.3f})")
    board.Remove(t)
    stub_removed += 1
print(f"  stubs removed: {stub_removed}")

# ---------------------------------------------------------------- B. vias at the named GND pads
print()
print("=== B. vias at the centre of the named GND pads ===")
TARGETS = [("J_W2", "2"), ("J_W3", "2")]
gnd = net_by_name("GND")
added = []
_seen_pos = set()   # a footprint may carry SEPARATE F.Cu and B.Cu pads with the SAME number, so the
                    # same centre can be visited twice; one via per POSITION, not per pad, or the
                    # board would gain two co-located holes (a `holes_co_located` violation).
for ref, num in TARGETS:
    fp = board.FindFootprintByReference(ref)
    if fp is None:
        print(f"  {ref}: NOT FOUND")
        continue
    for p in fp.Pads():
        if p.GetNumber() != num:
            continue
        pos = p.GetPosition()
        key = (round(MM(pos.x), 4), round(MM(pos.y), 4))
        if key in _seen_pos:
            print(f"  skip {ref}.{num}: a via already sits at {key}")
            continue
        _seen_pos.add(key)
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(pos)
        via.SetWidth(pcbnew.FromMM(VIA_DIA))
        via.SetDrill(pcbnew.FromMM(VIA_DRILL))
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        if gnd is not None:
            via.SetNet(gnd)
        board.Add(via)
        added.append(f"{ref}.{num}")
        print(f"  via at {ref}.{num} centre ({MM(pos.x):.3f},{MM(pos.y):.3f}) "
              f"dia {VIA_DIA} drill {VIA_DRILL}")
print(f"  vias added: {len(added)}")

if CHECK:
    print("\n(check mode -- nothing written)")
    sys.exit(0)

pcbnew.SaveBoard(DST, board)
print(f"\n  wrote {os.path.relpath(DST)}")
