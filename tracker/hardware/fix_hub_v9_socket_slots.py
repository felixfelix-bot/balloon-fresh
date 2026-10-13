#!/usr/bin/env python3
"""fix_hub_v9_socket_slots.py -- pull the two off-board socket connectors inward
so all four slots become edge notches instead of 6 mm edge stabs.

WHY (measured 2026-10-12, tracker/hardware/cut_hub_v9_socket_slots.py):
  board outline 103 x 103 mm, 1 outline / 0 holes.
  J_W1 slot x 0..6        -> edge notch, OK
  J_W3 slot x 97..103     -> edge notch, OK
  J_W2 slot y 103..109    -> pokes 6 mm OUTSIDE (needs -6 mm in y)
  J_W4 slot y -6..0       -> pokes 6 mm OUTSIDE (needs +6 mm in y)

Moving J_W2 and J_W4 inward 6 mm makes every slot mouth sit exactly on the board
edge -- the geometry a fab house expects.  This also removes the floating edges
KiCad's copper_edge_clearance was measuring the socket pads against.

The move is a pure translation of the whole footprint (pads + graphics), so the
netlist is unchanged; only placement changes.  Verify with DRC afterwards.

KiCad 9 pitfall: pcbnew.FootprintMove() via board.FindFootprintByReference.
"""
import argparse
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6

# reference -> (dx_mm, dy_mm)
MOVES = {"J_W2": (0.0, -6.0), "J_W4": (0.0, +6.0)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--apply", action="store_true",
                    help="actually move (default: dry-run report only)")
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.inp)

    for ref, (dx, dy) in MOVES.items():
        fp = b.FindFootprintByReference(ref)
        if fp is None:
            print(f"REFUSED: {ref} not found", file=sys.stderr)
            return 2
        pos = fp.GetPosition()
        # slot bbox before
        xs, ys = [], []
        for g in fp.GraphicalItems():
            if g.GetLayer() != pcbnew.Edge_Cuts:
                continue
            s, e = g.GetStart(), g.GetEnd()
            xs += [s.x, e.x]
            ys += [s.y, e.y]
        if not xs:
            print(f"REFUSED: {ref} has no Edge.Cuts slot", file=sys.stderr)
            return 2
        print(f"{ref}: pos ({pos.x/MM:.3f},{pos.y/MM:.3f})  "
              f"slot x {min(xs)/MM:.3f}..{max(xs)/MM:.3f} "
              f"y {min(ys)/MM:.3f}..{max(ys)/MM:.3f}  "
              f"-> move ({dx:+.1f},{dy:+.1f}) mm")
        if args.apply:
            np = pcbnew.VECTOR2I(pos.x + int(dx * MM), pos.y + int(dy * MM))
            fp.SetPosition(np)
            xs2, ys2 = [], []
            for g in fp.GraphicalItems():
                if g.GetLayer() != pcbnew.Edge_Cuts:
                    continue
                s, e = g.GetStart(), g.GetEnd()
                xs2 += [s.x, e.x]
                ys2 += [s.y, e.y]
            print(f"   after: slot x {min(xs2)/MM:.3f}..{max(xs2)/MM:.3f} "
                  f"y {min(ys2)/MM:.3f}..{max(ys2)/MM:.3f}")

    if args.apply:
        b.Save(args.out)
        print(f"written: {args.out}")
    else:
        print("dry-run only; pass --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
