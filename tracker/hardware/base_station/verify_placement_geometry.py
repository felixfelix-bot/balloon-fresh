#!/usr/bin/env python3
"""Is the placement physically real? Check on-board seating and pad overlap.

"44 placed" only means FootprintLoad succeeded and the packer returned. Verify the geometry:
  1. every footprint's bounding box wholly inside the outline
  2. no two footprints' bounding boxes overlapping (the packer should guarantee this)
  3. the board's own edge clearance
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/usr/lib/python3/dist-packages")


def load_board(path):
    import pcbnew
    return pcbnew, pcbnew.LoadBoard(path)


def main():
    w, h = (float(v) for v in (sys.argv[1] if len(sys.argv) > 1 else "60x45").split("x"))
    spec = importlib.util.spec_from_file_location("placer", os.path.join(HERE, "place_base_station.py"))
    placer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(placer)

    import pcbnew
    hubgen = placer._hubgen()

    board, placed, skipped, comps, nets = placer.load(w, h)
    # the placer's own main() calls this; replicate it so we grade exactly what ships
    overflow = hubgen.pack_rest(board, placed, [], w, h)
    hubgen.add_gnd_plane(board, w, h)

    print(f"outline {w} x {h} mm")
    print(f"placed  {len(placed)}, overflow {len(overflow) if overflow else 0}")
    print()

    # the GATE'S OWN rectangle (pad-box union courtyard) -- not GetBoundingBox, which includes
    # silkscreen and reference text and therefore over-reports collisions
    boxes = []
    for ref, fp in placed:
        rx0, ry0, rx1, ry1 = hubgen.rel_rect(fp)
        p = fp.GetPosition()
        x0, y0 = rx0 + p.x / 1e6, ry0 + p.y / 1e6
        x1, y1 = rx1 + p.x / 1e6, ry1 + p.y / 1e6
        boxes.append((ref, x0, y0, x1, y1))

    print("=== 1. wholly inside the outline (1 mm edge margin)? ===")
    offboard = [b for b in boxes if b[1] < 0 or b[2] < 0 or b[3] > w or b[4] > h]
    if offboard:
        print(f"  {len(offboard)} rectangle(s) extend past the outline:")
        for ref, x0, y0, x1, y1 in offboard:
            print(f"    {ref:10s} ({x0:7.2f},{y0:7.2f})-({x1:7.2f},{y1:7.2f})")
    else:
        print("  all rectangles inside the outline")

    print()
    print("=== 2. gate-rectangle overlaps (the measure the packer clears)? ===")
    CLR = 0.5
    ov = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            if (a[1] - CLR < b[3] and b[1] - CLR < a[3]
                    and a[2] - CLR < b[4] and b[2] - CLR < a[4]):
                ov.append((a[0], b[0]))
    if ov:
        print(f"  {len(ov)} overlapping pair(s):")
        for a, b in ov[:12]:
            print(f"    {a} <-> {b}")
    else:
        print("  no gate-rectangle overlaps")

    print()
    print("=== 3. area utilisation ===")
    part_area = sum((b[3] - b[1]) * (b[4] - b[2]) for b in boxes)
    print(f"  gate-rect area {part_area:.1f} mm2 of {w*h:.1f} mm2 board = "
          f"{part_area/(w*h)*100:.1f} %")
    return 0 if (not offboard and not ov) else 1


if __name__ == "__main__":
    raise SystemExit(main())
