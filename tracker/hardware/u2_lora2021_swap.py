#!/usr/bin/python3.14
"""U2 land-pattern replacement: HOPERF RFM9xW (SX1276) -> NiceRF LoRa2021 18-pin.

WHY THIS EXISTS (card t_f48320db)
--------------------------------
`output/v8f_krt_margin_escaped.kicad_pcb` carries U2 as a byte-identical copy of
KiCad's `RF_Module:HOPERF_RFM9XW_SMD` (16 pads, pad map NSS=5 / RST=6 / BUSY=12 /
DIO0=14 -> RFM95W pinout), while the plan of record
(`tracker/hardware/FLIGHT-BOARD-PLAN.md` section RF) and the firmware
(`mesh-stack/meshcore-lr2021/patches/CustomLR2021.h` -> `class CustomLR2021 :
public LR2021`) both target the NiceRF LoRa2021 18-pin castellated module.

This script performs the structural swap only.  It computes NO coordinates:

  * rips every track / via (a moved part leaves copper detached; the placement
    stage requires a copper-free input - see prep_placement_input.py);
  * removes the U2 footprint object and mounts `custom:LoRa2021_Castellated`
    (tracker/hardware/hub_board_diy/custom.pretty) on the same seat, rotated
    180 deg, so the module's ANT pad (pin 9) lands on the module's EAST column
    facing ANT1 - the U.FL port on the east board edge (a mechanical fact, see
    placement-source-of-truth.json).  The 180 deg is a topology constraint
    (antenna port adjacent to the antenna connector), not a coordinate: the
    final position is computed by KRT py_placer/place_optimize.py.
  * remaps the 18 pads to the plan-of-record table
    (MISO 3 / MOSI 4 / SCK 5 / NSS 6 / BUSY 7 / RST 14 / DIO9-IRQ 15 / VCC 1 /
     GND 2,8,11,12,18 / ANT 9).  No RFM9xW pad->signal mapping survives.
  * renames the IRQ net LR_DIO0 -> LR_IRQ, because "DIO0" is the RFM95W pad
    name for that signal (docs/PCB-HANDOVER-FOR-JLCPCB.md appendix A already
    documents the LR2021 net as LR_IRQ, driven from pin 15 / DIO9).
  * drops stale zone fill geometry on the two pours.

Pads 10 (2.4G/S_ANT), 13 (VTCXO), 16 (DIO8), 17 (DIO7) carry NO net: the card's
net table does not assign them and this board has no 2.4 GHz port.  They are
reported, not silently grounded.

Writes a NEW file; the input board is never edited.
"""
from __future__ import annotations

import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

HERE = "."
LIB_DIR = "hub_board_diy/custom.pretty"
FOOTPRINT = "LoRa2021_Castellated"

SRC = "output/v8f_krt_margin_escaped.kicad_pcb"
DST = "output/v8g_u2_lora2021_unrouted.kicad_pcb"

# Plan of record: tracker/hardware/FLIGHT-BOARD-PLAN.md section RF + docs/PCB-HANDOVER-FOR-JLCPCB.md
PAD_NETS = {
    "1": "+3V3",       # VCC
    "2": "GND",
    "3": "SPI_MISO",
    "4": "SPI_MOSI",
    "5": "SPI_SCK",
    "6": "SPI_NSS",
    "7": "LR_BUSY",
    "8": "GND",
    "9": "RF_OUT",     # ANT (sub-GHz, 50 ohm)
    "11": "GND",
    "12": "GND",
    "14": "LR_RST",
    "15": "LR_IRQ",    # DIO9, level-triggered IRQ in the raw LR2021 driver
    "18": "GND",
    # deliberately unconnected (not in the card's table, no port on this board):
    # 10 = 2.4G/S_ANT, 13 = VTCXO, 16 = DIO8, 17 = DIO7
}
UNCONNECTED = ("10", "13", "16", "17")

U2_ROTATION_DEG = 180.0


def main() -> int:
    board = pcbnew.LoadBoard(SRC)

    # ---- 1. rip all copper -------------------------------------------------
    copper = list(board.GetTracks())
    for t in copper:
        board.Remove(t)
    print(f"ripped {len(copper)} copper items "
          f"({sum(1 for t in copper if t.Type() == pcbnew.PCB_VIA_T)} vias, "
          f"{sum(1 for t in copper if t.Type() == pcbnew.PCB_TRACE_T)} segments)")

    # ---- 2. net rename: LR_DIO0 -> LR_IRQ ----------------------------------
    # Collect NETINFO_ITEM objects up front: FindNet() consults a name map that a
    # rename does not refresh, so pads are attached to the OBJECT, not a lookup.
    nets = {ni.GetNetname(): ni
            for code, ni in board.GetNetInfo().NetsByNetcode().items()
            if ni.GetNetname()}
    if "LR_DIO0" not in nets:
        sys.exit("ABORT: net LR_DIO0 not found - refusing to guess")
    if "LR_IRQ" in nets:
        sys.exit("ABORT: net LR_IRQ already exists - refusing to merge")
    ni_irq = nets.pop("LR_DIO0")
    ni_irq.SetNetname("LR_IRQ")
    nets["LR_IRQ"] = ni_irq
    print("net LR_DIO0 renamed -> LR_IRQ (RFM95W pad name must not survive)")

    # ---- 3. remove U2 and mount the LoRa2021 land pattern ------------------
    old = [fp for fp in board.GetFootprints() if fp.GetReference() == "U2"]
    if len(old) != 1:
        sys.exit(f"ABORT: expected exactly 1 U2, found {len(old)}")
    old = old[0]
    old_id = old.GetFPID().GetLibItemName()
    seat = old.GetPosition()
    old_pads = len(list(old.Pads()))
    board.Remove(old)
    print(f"removed U2 = {old_id} ({old_pads} pads) at "
          f"({seat.x/1e6:.3f},{seat.y/1e6:.3f})")

    io = pcbnew.PCB_IO_MGR.PluginFind(pcbnew.PCB_IO_MGR.KICAD_SEXP)
    fp = io.FootprintLoad(LIB_DIR, FOOTPRINT)
    if fp is None:
        sys.exit(f"ABORT: could not load {LIB_DIR}:{FOOTPRINT}")
    if len(list(fp.Pads())) != 18:
        sys.exit(f"ABORT: {FOOTPRINT} has {len(list(fp.Pads()))} pads, expected 18")

    fp.SetReference("U2")
    fp.SetValue("LoRa2021_Gen4")
    fp.SetPosition(seat)
    fp.SetOrientationDegrees(U2_ROTATION_DEG)
    board.Add(fp)
    print(f"mounted custom:{FOOTPRINT} on the same seat, rotation {U2_ROTATION_DEG:g} deg")

    # ---- 4. remap the 18 pads ---------------------------------------------
    applied = {}
    for pad in fp.Pads():
        num = pad.GetNumber()
        name = PAD_NETS.get(num)
        if name is None:
            if num not in UNCONNECTED:
                sys.exit(f"ABORT: pad {num} is in neither the net table nor the "
                         f"unconnected list - refusing to guess")
            pad.SetNetCode(0)
            applied[num] = None
            continue
        if name not in nets:
            sys.exit(f"ABORT: net {name} does not exist on the board")
        pad.SetNet(nets[name])
        applied[num] = name

    print("pad -> net remap:")
    for num in sorted(applied, key=int):
        print(f"   pad {num:>3s} -> {applied[num] or '(no net)'}")

    # ---- 5. drop stale zone fill ------------------------------------------
    zones = list(board.Zones())
    for z in zones:
        z.UnFill()
    print(f"unfilled {len(zones)} zones")

    pcbnew.SaveBoard(DST, board)

    # ---- 6. verify from disk ----------------------------------------------
    chk = pcbnew.LoadBoard(DST)
    u2 = [f for f in chk.GetFootprints() if f.GetReference() == "U2"]
    assert len(u2) == 1, "U2 not present after save"
    u2 = u2[0]
    pads = sorted(u2.Pads(), key=lambda p: int(p.GetNumber()))
    print(f"\nverify {DST}:")
    print(f"  U2 = {u2.GetFPID().GetLibItemName()}  pads={len(pads)}  "
          f"rot={u2.GetOrientationDegrees():g}")
    segs = [t for t in chk.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T]
    vias = [t for t in chk.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
    print(f"  copper: {len(segs)} segments {len(vias)} vias (must be 0/0)")
    print(f"  footprints: {len(list(chk.GetFootprints()))}")
    bad = [p.GetNumber() for p in pads if p.GetNetname() != (PAD_NETS.get(p.GetNumber()) or "")]
    print(f"  pad/net mismatches vs table: {bad if bad else 'none'}")
    return 0 if not segs and not vias and not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
