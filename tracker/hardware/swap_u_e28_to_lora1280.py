#!/usr/bin/env python3
"""Swap U_E28 (E28-2G4M27SX, 15x20) for U_LORA1280 (16x16) on hub v10, per ADR-139.

Dry run by default: reports what the swap would do and which foreign copper sits inside
the new footprint's courtyard. --apply performs it.

Why a dry run is the default: the same check gated ADR-137's Option A, and an earlier
router crash in this repo damaged the board from 775 tracks to 589. Measure, then act.

Net remap (E28 pin -> LoRa1280 pin) is a genuine change of pin order, not a rename:

    E28 3  MISO_TX   -> L1280 5  MISO
    E28 4  MOSI_RX   -> L1280 6  MOSI
    E28 5  SCK_RTSN  -> L1280 7  SCK
    E28 6  NSS_CTS   -> L1280 8  NSS
    E28 11 NRESET    -> L1280 13 NRESET
    E28 12 BUSY      -> L1280 15 BUSY
    E28 13 DIO1      -> L1280 16 DIO1
    E28 14 DIO2      -> L1280 1  DIO2
    E28 15 DIO3      -> L1280 2  DIO3
    E28 1  VCC       -> L1280 3  VCC
    E28 2/7/10/16 GND-> L1280 4/10/11/12/14 GND
    E28 8  RX_EN  (NC) -> (no pin on the new part)
    E28 9  TX_EN  (NC) -> (no pin on the new part)
    --                  L1280 9  ANT   (new: antenna pad, no net)
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import pcbnew

BOARD = "tracker/hardware/hub_board_v10.kicad_pcb"
FPDIR = "tracker/hardware/footprints/lora1280"
OLD_REF = "U_E28"
NEW_REF = "U_LORA1280"
NEW_VALUE = "LoRa1280"

# name on the old part -> name on the new part, matched by NET, not by pin number
NET_MAP = {
    "MISO": "MISO", "MOSI": "MOSI", "SCK": "SCK", "NSS": "NSS",
    "NRESET": "NRESET", "BUSY": "BUSY", "DIO1": "DIO1", "DIO2": "DIO2", "DIO3": "DIO3",
    "VCC": "VCC",
}
# new-part pin -> the E28 pin that carried the same function
NEW_PIN_FROM_OLD = {5: 3, 6: 4, 7: 5, 8: 6, 13: 11, 15: 12, 16: 13, 1: 14, 2: 15, 3: 1}
NEW_PIN_GND = [4, 10, 11, 12, 14]
OLD_PIN_GND = [2, 7, 10, 16]
NEW_PIN_ANT = 9


def mm(v):
    return v / 1e6


def bbox_of(fp):
    bb = fp.GetBoundingBox(False, False)
    return (mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom()))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--board", default=BOARD)
    # Placement offset in mm (board +y is down). The 16x16 body is 0.33mm taller at the
    # top edge than the 15x20 it replaces, which lands it 4.76 mm^2 inside U6's courtyard.
    # Shifting down clears U6 and still leaves ~3.7mm to the board edge below.
    ap.add_argument("--dy", type=float, default=0.0,
                    help="shift the new footprint down by this many mm")
    ap.add_argument("--dx", type=float, default=0.0)
    ap.add_argument("--rot", type=float, default=None,
                    help="override rotation (deg); default keeps the outgoing part's")
    ap.add_argument("--side", choices=("B.Cu", "F.Cu"), default=None,
                    help="override which side the part mounts on")
    a = ap.parse_args(argv)

    b = pcbnew.LoadBoard(a.board)
    old = next((f for f in b.GetFootprints() if f.GetReference() == OLD_REF), None)
    if old is None:
        print(f"FAIL: no {OLD_REF} on the board")
        return 1

    op = old.GetPosition()
    rot = old.GetOrientationDegrees()
    if a.rot is not None:
        rot = a.rot
    want_back = (old.GetLayer() == pcbnew.B_Cu) if a.side is None else (a.side == "B.Cu")
    ob = bbox_of(old)
    print(f"{OLD_REF}: pos ({mm(op.x):.3f},{mm(op.y):.3f}) rot {rot}")
    print(f"  old body bbox x {ob[0]:.2f}..{ob[2]:.2f}  y {ob[1]:.2f}..{ob[3]:.2f}"
          f"  ({ob[2]-ob[0]:.2f} x {ob[3]-ob[1]:.2f})")

    # where the new part lands: same centre, same rotation
    new = pcbnew.FootprintLoad(FPDIR, "LoRa1280")
    if new is None:
        print("FAIL: could not load LoRa1280 footprint")
        return 1
    new.SetReference(NEW_REF)
    new.SetValue(NEW_VALUE)
    # FootprintLoad() strips the library nickname, so the placed part would be bare
    # "LoRa1280" while every other part on the board carries "Lib:Name" and the netlist
    # names a library. The pad-audit gate refuses that mismatch, correctly.
    try:
        new.SetFPID(pcbnew.LIB_ID("NiceRF", "LoRa1280"))
    except Exception:
        _lid = pcbnew.LIB_ID()
        _lid.SetLibNickname("NiceRF")
        _lid.SetLibItemName("LoRa1280")
        new.SetFPID(_lid)
    tgt = pcbnew.VECTOR2I(op.x + int(a.dx * 1e6), op.y + int(a.dy * 1e6))
    new.SetPosition(tgt)
    new.SetOrientationDegrees(rot)
    b.Add(new)
    # The outgoing U_E28 was mounted on B.Cu (bottom side, two-sided population per
    # ADR-118). FootprintLoad() gives an F.Cu part, so it must be flipped or it lands on
    # the wrong side of the board and the router has nothing to reach.
    # Flip() segfaults on a library-loaded footprint, so it is done here, after Add().
    # NOTE: pad.GetLayerName() still reports "F.Cu" afterwards — that accessor is
    # misleading. The pad LAYER SET is what matters and is correctly
    # B.Cu/B.Mask/B.Paste. Verify with GetLayerSet(), never GetLayerName().
    if want_back and new.GetLayer() != pcbnew.B_Cu:
        new.Flip(tgt, False)
    nb = bbox_of(new)
    print(f"{NEW_REF}: same centre/rot -> body bbox x {nb[0]:.2f}..{nb[2]:.2f}  "
          f"y {nb[1]:.2f}..{nb[3]:.2f}  ({nb[2]-nb[0]:.2f} x {nb[3]-nb[1]:.2f})")

    boardsz = b.GetBoardEdgesBoundingBox()
    print(f"board: {mm(boardsz.GetWidth()):.2f} x {mm(boardsz.GetHeight()):.2f}; "
          f"new ul corner ({nb[0]:.2f},{nb[1]:.2f}) lr ({nb[2]:.2f},{nb[3]:.2f})")
    for name, val, lim in (("left", nb[0], 0), ("top", nb[1], 0),
                           ("right", nb[2], mm(boardsz.GetWidth())),
                           ("bottom", nb[3], mm(boardsz.GetHeight()))):
        if (name in ("left", "top") and val < lim) or (name in ("right", "bottom") and val > lim):
            print(f"  !! new body exceeds the board on the {name} side")

    # net remap report
    old_nets = {p.GetNumber(): p.GetNetname() for p in old.Pads()}
    print("\nnet remap:")
    for npin, opin in NEW_PIN_FROM_OLD.items():
        print(f"  L1280 pin {npin:>2} <- E28 pin {opin:>2}  net '{old_nets.get(str(opin)) or '(NC)'}'")
    gnd = old_nets.get("2") or "GND"
    print(f"  L1280 pins {NEW_PIN_GND} <- E28 pins {OLD_PIN_GND}  net '{gnd}'")
    print(f"  L1280 pin {NEW_PIN_ANT} ANT <- new antenna pad, no net")
    for p in ("8", "9"):
        print(f"  E28 pin {p} '{(old_nets.get(p) or '(NC)')}' -> deleted with the part")

    # obstruction: foreign-net items inside the NEW courtyard
    infl = new.GetCourtyard(pcbnew.F_CrtYd)
    box = infl.BBox()
    hits = {}
    for t in b.GetTracks():
        if t.GetNetname() and box.Contains(t.GetStart()) and box.Contains(t.GetEnd()):
            hits.setdefault(t.GetNetname(), []).append(t)
    for f in b.GetFootprints():
        if f.GetReference() in (OLD_REF, NEW_REF):
            continue
        fb = bbox_of(f)
        if not (fb[2] < nb[0] or fb[0] > nb[2] or fb[3] < nb[1] or fb[1] > nb[3]):
            hits.setdefault(f"fp:{f.GetReference()}", []).append(f)
    print(f"\nforeign-net items fully inside the new courtyard: "
          f"{sum(len(v) for v in hits.values())}")
    for k, v in sorted(hits.items()):
        print(f"  {k}: {len(v)}")

    if not a.apply:
        print("\nDRY RUN — nothing written. Re-run with --apply to perform the swap.")
        return 0

    # --- apply ------------------------------------------------------------
    # Net census taken while the board is still intact (see the note further down).
    by_name: dict[str, int] = {}
    for f in b.GetFootprints():
        for pad in f.Pads():
            n = pad.GetNetname()
            if n and n not in by_name:
                by_name[n] = pad.GetNetCode()
    print(f"nets seen on the intact board: {len(by_name)}")
    # existing radio-link copper ends on pins that no longer exist: drop those nets'
    # tracks so the router starts from a clean, honest state
    # ONLY the signal nets are stripped. Power and ground are deliberately excluded:
    # +3V3 and GND are board-wide nets carried by zones/tracks elsewhere, and deleting
    # every track on them would tear up copper that has nothing to do with this swap.
    # Those two pads join by zone/via as before.
    POWER_GND = {"+3V3", "GND", "VCC", "+5V", "VSCAP"}
    doomed = {old_nets.get(str(o)) for o in NEW_PIN_FROM_OLD.values()}
    doomed = {n for n in doomed if n and n not in POWER_GND}
    # ORDER MATTERS. Every accessor on a footprint/pad handle returns a bare SwigPyObject
    # once the footprint collection has been mutated (Remove()/Add()), so all pad work is
    # done first and the old part is removed LAST.
    new_pads = {p.GetNumber(): p for p in new.Pads()}
    gnd_code = by_name.get(gnd)
    assigned = 0
    missing = []
    for npin, opin in NEW_PIN_FROM_OLD.items():
        code = by_name.get(old_nets.get(str(opin)) or "")
        if code:
            new_pads[str(npin)].SetNetCode(code)
            assigned += 1
        else:
            missing.append((npin, old_nets.get(str(opin))))
    for npin in NEW_PIN_GND:
        if gnd_code:
            new_pads[str(npin)].SetNetCode(gnd_code)
            assigned += 1
    print(f"\nassigned {assigned} pads to nets; pin {NEW_PIN_ANT} (ANT) left netless")
    if missing:
        print(f"  !! no net found for {missing}")

    removed = 0
    for t in list(b.GetTracks()):
        if t.GetNetname() in doomed:
            b.Remove(t)
            removed += 1
    print(f"removed {removed} track/via items on nets {sorted(doomed)} (to be re-routed)")

    b.Remove(old)
    print(f"removed {OLD_REF}")

    pcbnew.SaveBoard(a.board, b)
    print(f"saved {a.board}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
