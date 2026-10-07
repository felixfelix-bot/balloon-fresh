#!/usr/bin/env python3.14
"""Build v8j MS5611 flight board from v8i — THE single deterministic writer of
`output/v8j_krt_ms5611.kicad_pcb`.

Root cause of the 170-error/11-unconnected v8j (cb6e61094455):
  The prior worker swapped U5's footprint from BMP280 (Bosch_LGA-8_2.5x2.5mm,
  0.65 mm pitch, clockwise pin numbering) to MS5611 (LGA-8_3x5mm_P1.25mm) but
  left the OLD v8i tracks in place and assigned pad nets using the BMP280 pin
  positions (pad3=SDA, pad4=SCL) — on the MS5611 those pads are GND and PS.
  Result: 138 stale-zone clearance, 11 unconnected at U5, 12 under-size drills.

Fix (ADR-030 deterministic pipeline):
  1. Load the PASSING v8i board (sha 638de5638772..., 0 errors / 8 silk warnings).
  2. Replace U5: load MS5611 LGA-8_3x5mm_P1.25mm from the official library.
  3. Assign the CORRECT MS5611 I2C pad-to-net mapping:
       pin 1 VDD    -> +3V3
       pin 2 GND    -> GND
       pin 3 GND    -> GND
       pin 4 PS     -> GND  (I2C mode)
       pin 5 CSB    -> +3V3 (address 0x76, CSB high)
       pin 6 SDO    -> GND  (address LSB = 0)
       pin 7 SDI/SDA -> I2C_SDA
       pin 8 SCLK/SCL -> I2C_SCL
  4. Strip ALL tracks + vias (placement-gate pre-condition, ADR-030 D3).
  5. Save as v8j_krt_ms5611_unrouted.kicad_pcb (the placed, un-routed board).

KRT routing + zone refill is a separate step (route_v8j.sh).
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

SRC = 'tracker/hardware/output/v8i_krt_gnss.kicad_pcb'
DST = 'tracker/hardware/output/v8j_krt_ms5611_unrouted.kicad_pcb'
LIBS = '/usr/share/kicad/footprints'
MM = 1e6

# MS5611-01BA I2C pad-to-net mapping (datasheet + KiCad MS5607/MS5611 symbol).
# Pin  function     net
#  1   VDD          +3V3
#  2   GND          GND
#  3   GND          GND
#  4   PS           GND  (GND => I2C protocol selected)
#  5   CSB          +3V3 (high => I2C addr 0x76)
#  6   SDO          GND  (low => addr LSB 0)
#  7   SDI/SDA      I2C_SDA
#  8   SCLK/SCL     I2C_SCL
MS5611_NETS = {
    '1': '+3V3',
    '2': 'GND',
    '3': 'GND',
    '4': 'GND',
    '5': '+3V3',
    '6': 'GND',
    '7': 'I2C_SDA',
    '8': 'I2C_SCL',
}


def main() -> int:
    board = pcbnew.LoadBoard(SRC)
    fps = list(board.GetFootprints())
    print(f'loaded {SRC}: {len(fps)} footprints')

    u5 = board.FindFootprintByReference('U5')
    if u5 is None:
        raise SystemExit('U5 not found on source board')
    u5_pos = u5.GetPosition()
    u5_rot = u5.GetOrientation()
    print(f'  old U5: value={u5.GetValue()!r} fpid={u5.GetFPID().GetLibItemName()!r}'
          f' pos=({u5_pos.x/MM:.3f},{u5_pos.y/MM:.3f}) rot={u5_rot.AsDegrees():.1f}')

    # Record the old pad nets so we can verify we are re-wiring correctly.
    print('  old U5 pad nets:', {p.GetNumber(): p.GetNet().GetNetname()
          for p in u5.Pads()})

    # Remove old U5 from the board.
    board.Remove(u5)

    # Load the MS5611 footprint from the official KiCad library.
    plug = pcbnew.PCB_IO_MGR.PluginFind(pcbnew.PCB_IO_MGR.KICAD_SEXP)
    new_u5 = plug.FootprintLoad(f'{LIBS}/Package_LGA.pretty',
                                'LGA-8_3x5mm_P1.25mm')
    if new_u5 is None:
        raise SystemExit('MS5611 footprint not found in library')
    new_u5.SetFPID(pcbnew.LIB_ID('', new_u5.GetFPID().GetLibItemName()))
    new_u5.SetReference('U5')
    new_u5.SetValue('MS5611-01BA')
    new_u5.SetPosition(u5_pos)
    new_u5.SetOrientation(u5_rot)
    board.Add(new_u5)

    # Assign pad nets per the MS5611 I2C mapping.
    for pad in new_u5.Pads():
        netname = MS5611_NETS.get(pad.GetNumber())
        if netname is None:
            print(f'  WARNING: U5 pad {pad.GetNumber()} has no mapping')
            continue
        net = board.FindNet(netname)
        if net is None:
            print(f'  WARNING: net {netname!r} not found on board — creating')
            net = pcbnew.NETINFO_ITEM(board, netname)
            board.Add(net)
        pad.SetNet(net)
    print('  new U5 pad nets:', {p.GetNumber(): p.GetNet().GetNetname()
          for p in new_u5.Pads()})

    # Strip ALL tracks and vias (placement-gate pre-condition, ADR-030 D3).
    tracks = list(board.GetTracks())
    n_seg = sum(1 for t in tracks if t.Type() == pcbnew.PCB_TRACE_T)
    n_via = sum(1 for t in tracks if t.Type() == pcbnew.PCB_VIA_T)
    for t in tracks:
        board.Remove(t)
    print(f'  stripped {n_seg} tracks + {n_via} vias')

    # Save the placed, un-routed board.
    pcbnew.SaveBoard(DST, board)
    print(f'wrote {DST}: {len(list(board.GetFootprints()))} footprints, 0 tracks')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())