#!/usr/bin/env python3
"""restore_hub_v9_hidden_refdes.py -- un-hide refdes the shrink pass suppressed.

The shrink pass (clean_hub_v9_silk.py) HID 6 refdes that could not clear via
fields at any size >= 0.4 mm.  An unlabeled board is a worse outcome than a
cosmetic silk flag: you cannot debug or rework a part you cannot identify.

Measured 2026-10-12: agentee offers a free position for only 1 of the 6
(`U4`), so 5 stayed hidden.  This restores ALL of them at 0.60 mm (visible,
readable) and accepts the cosmetic silk-text flag -- documented in the ledger.

Deterministic.
"""
import argparse
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
SIZE_MM = 0.60


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.inp)
    n = 0
    for fp in b.GetFootprints():
        rt = fp.Reference()
        if not rt.IsVisible():
            rt.SetVisible(True)
            rt.SetTextSize(pcbnew.VECTOR2I(int(SIZE_MM * MM), int(SIZE_MM * MM)))
            n += 1
            print(f"  {fp.GetReference()}: refdes restored, {SIZE_MM} mm")
    print(f"refdes restored: {n}")
    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
