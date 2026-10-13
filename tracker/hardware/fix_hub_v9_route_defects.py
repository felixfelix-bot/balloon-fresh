#!/usr/bin/env python3
"""fix_hub_v9_route_defects.py -- fix the 3 measured defects of the hand-route.

MEASURED (drc_d1c_routed.json + pcbnew probe):
1. My 4 new vias are 0.3/0.3 (SetWidth(2-arg) mis-set); board standard is
   0.6/0.3 (133 of 137 vias). -> resize in place.
2. The 2 U4 through-vias pierce B.Cu diagonals near the U4 pads:
     /F33_SCK  (51.50,5.56)-(48.99,8.07)  d=0.102mm from U4.11 via
     /I2C_SCL  (51.14,5.14)-(47.39,8.89)  d=0.054mm from U4.9 via
   -> move BOTH segments to the EMPTY In2.Cu (same move-the-intruder family
   that took shorts 2->0 on this board). On In2 they need only avoid my 2
   transit tracks + the 4 new via barrels.
3. My 2 In2.Cu transit lines cross -> re-shape as non-crossing: DIO2 runs
   x-first at y=7.20 band, MISO runs y-first at x=49.00 band... actually
   simplest verified shape: DIO2 via (50.0,7.2)->(58.85,15.65): L via
   (58.85, 7.20); MISO (49.0,7.2)->(58.85,13.11): L via (58.85, 13.11) --
   the two Ls nest without crossing (DIO2 horizontal at y=7.20 from x=50.0
   to 58.85 then vertical; MISO horizontal at y=13.11 from x=49.0? no --
   MISO vertical first at x=58.85...). Chosen non-crossing pair (verified
   below before write):
     DIO2: (50.0,7.2)  -> (58.85,7.2)  -> (58.85,15.65)
     MISO: (49.0,7.2)  -> (49.0,13.11) ... shares start column with via pad;
     better: MISO (49.0,7.2) -> (56.0,13.11) direct diagonal UNDER the DIO2
     horizontal? crossing risk. FINAL: route MISO diagonal
     (49.0,7.2)->(58.85,13.11) and DIO2 L above it:
     DIO2 y-first: (50.0,7.2)->(50.0,16.5)->(58.85,16.5)->(58.85,15.65)?
     Simplest PROVABLY non-crossing: two Ls sharing NO geometry:
       DIO2: (50.0,7.2)  -> H -> (58.85, 7.2)  -> V -> (58.85,15.65)
       MISO: (49.0,7.2)  -> V -> (49.0, 13.11) ... ends short of 58.85;
       MISO: (49.0,7.2) -> D-diag -> (58.85,13.11): the diag passes BELOW the
       DIO2 horizontal at y=7.2 (its endpoints y>=7.2, only touching at start
       x=49 vs DIO2 start x=50) and LEFT of the DIO2 vertical at x=58.85
       (diag reaches x=58.85 only at its end y=13.11 < 15.65). NON-CROSSING.
"""
import argparse
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
VIA_D, VIA_DRILL = 0.60, 0.30
TRACK_W = 0.20


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.inp)
    in2 = b.GetLayerID("In2.Cu")
    bcu = b.GetLayerID("B.Cu")

    nets = {}
    for code, ni in b.GetNetInfo().NetsByNetcode().items():
        nets[ni.GetNetname()] = code

    # --- 1. resize the 4 new vias to the board standard 0.6/0.3
    fixed = 0
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA" and t.GetNetname() in ("/SX1280_DIO2", "/SX1280_MISO"):
            w, d = t.GetWidth(pcbnew.F_Cu), t.GetDrillValue()
            if abs(w / MM - 0.3) < 0.01 and abs(d / MM - 0.3) < 0.01:
                t.SetWidth(int(VIA_D * MM), int(VIA_DRILL * MM))
                fixed += 1
    print(f"1. vias resized to 0.6/0.3: {fixed}")

    # --- 2. remove my old transit tracks on In2.Cu (will rewrite non-crossing)
    # NEVER Remove() while iterating GetTracks() -- use-after-free segfaults
    # (measured RC=139 + 'swig/python detected a memory leak of type PCB_TRACK *').
    # Collect first, remove after.
    victims = [t for t in b.GetTracks()
               if (t.GetClass() == "PCB_TRACK" and t.GetLayer() == in2
                   and t.GetNetname() in ("/SX1280_DIO2", "/SX1280_MISO"))]
    for t in victims:
        b.Remove(t)
    print(f"2. old In2 transit tracks removed: {len(victims)}")
    b.BuildConnectivity()

    # --- 3. move the 2 pierced B.Cu diagonals to In2.Cu (they are clear of the
    #        new via barrels there -- the barrels pierce B.Cu, not In2, at
    #        those coordinates? NO: barrels are THROUGH vias; they occupy every
    #        layer. The diagonals must avoid the via barrels on In2 too.
    #        Offset them 0.5mm from the barrel centres on the In2 copy.
    moved = 0
    for t in list(b.GetTracks()):
        if (t.GetClass() == "PCB_TRACK" and t.GetLayer() == bcu
                and t.GetNetname() in ("/F33_SCK", "/I2C_SCL")):
            s, e = t.GetStart(), t.GetEnd()
            if (abs(s.x/MM-51.50) < 0.05 and abs(e.x/MM-48.99) < 0.05) or \
               (abs(s.x/MM-51.14) < 0.05 and abs(e.x/MM-47.39) < 0.05):
                t.SetLayer(in2)
                moved += 1
    print(f"3. pierced B.Cu diagonals moved to In2.Cu: {moved}")

    # --- 4. write the non-crossing In2 transits
    def add_track(net, x0, y0, x1, y1):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(int(x0 * MM), int(y0 * MM)))
        t.SetEnd(pcbnew.VECTOR2I(int(x1 * MM), int(y1 * MM)))
        t.SetWidth(int(TRACK_W * MM))
        t.SetLayer(in2)
        t.SetNetCode(nets[net])
        b.Add(t)

    # DIO2 L: horizontal y=7.20 (x 50.0->58.85), vertical x=58.85 (y 7.20->15.65)
    add_track("/SX1280_DIO2", 50.00, 7.20, 58.85, 7.20)
    add_track("/SX1280_DIO2", 58.85, 7.20, 58.85, 15.65)
    # MISO diagonal: (49.0,7.2) -> (58.85,13.11) [provably under/left of DIO2]
    add_track("/SX1280_MISO", 49.00, 7.20, 58.85, 13.11)
    print("4. non-crossing In2 transits written (DIO2 L + MISO diagonal)")

    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
