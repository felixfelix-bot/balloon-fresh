#!/usr/bin/env python3
"""build_pressure_rig.py -- generate the balloon pre-stretch pressure rig board.

Operator directive 2026-11-10: "design around the esp32-s3, not c3" and "pressure will leak out so we
can just run the pump to maintain the pressure without needing a release valve."

WHAT THIS BOARD IS
  S3 module + BMP280 pressure sensor + one logic-level MOSFET switching a pump. No relief valve
  (the envelope leaks, so control is one-directional). Bench powered over USB-C, flashing over the
  S3's own USB-Serial-JTAG (no bridge chip). No RF, no controlled impedance, no stackup discipline:
  this is deliberately the SIMPLEST board in the project.

WHY GENERATED, NOT DRAWN
  Same reason as build_wing_interconnect.py: a text generator is reviewable, diffable and
  re-runnable, and it cannot silently drift from the spec in docs/fab/pressure-rig/SPEC.md.

BOARD SIZE
  Sized from content, not chosen: the widest row is USB-C (9.0 mm) plus two 2-pin screw terminals on
  the left edge, the S3 module is 19.2 x 18.0 mm, and the BMP280 is 2.0 x 2.5 mm. A 60 x 40 mm
  outline leaves a real routing channel between the MCU and the connectors.

LAYER TABLE
  Declares copper, PASTE, MASK, silk, edge -- mask in particular. Measured 2026-11-10 on the wing
  interconnect: a board that omits F.Mask/B.Mask exports NO mask gerbers and cannot be built, while
  DRC still reports 0/0. That failure mode is not repeated here.

NOT YET PLACED
  This script emits the netlist-carrying board with footprints and the ratsnest. Placement and
  routing are the next steps; AGENTS.md 21 puts routing AFTER the placement gate.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "pressure_rig", "pressure_rig_v1.kicad_pcb")

# ---------------------------------------------------------------- geometry (mm)
BOARD_W = 60.0
BOARD_H = 40.0
EDGE = 1.6


def _f(x):
    return f"{x:.4f}".rstrip("0").rstrip(".")


NETS = [
    ("GND", 1), ("+3V3", 2), ("+5V", 3), ("VIN_12V", 4),
    ("I2C_SDA", 5), ("I2C_SCL", 6), ("PUMP_EN", 7), ("PUMP_SW", 8),
    ("USB_DP", 9), ("USB_DN", 10),
]

# ref, value, footprint-name, (x,y), pads [(num, net, dx, dy, w, h)]
PARTS = [
    ("U1", "ESP32-S3-WROOM-1U", "ESP32-S3-WROOM-1U", (30.0, 14.0), [
        ("3", "+3V3", -9.6, -9.0), ("2", "GND", -9.6, -7.73),
        ("19", "USB_DN", -9.6, 4.5), ("20", "USB_DP", -9.6, 5.77),
        ("8", "I2C_SDA", -9.6, -2.5), ("9", "I2C_SCL", -9.6, -1.23),
        ("4", "PUMP_EN", -9.6, -3.77),
    ]),
    ("U2", "BMP280", "LGA-8_BMP280", (12.0, 30.0), [
        ("6", "I2C_SDA", -1.0, 0.0), ("4", "I2C_SCL", -1.0, 0.95),
        ("8", "+3V3", 1.0, -0.95), ("1", "GND", 1.0, 0.95),
    ]),
    ("U3", "TPS7A0233", "SOT-23-5", (12.0, 20.0), [
        ("1", "+5V", -1.0, -0.95), ("3", "+5V", -1.0, 0.0),
        ("2", "GND", -1.0, 0.95), ("5", "+3V3", 1.0, 0.0),
    ]),
    ("Q1", "IRLML6344", "SOT-23", (48.0, 30.0), [
        ("1", "PUMP_EN", -1.0, 0.0), ("2", "PUMP_SW", 1.0, 0.95),
        ("3", "GND", 1.0, -0.95),
    ]),
    ("D1", "SS24", "D_SMA", (48.0, 22.0), [
        ("1", "PUMP_SW", -2.0, 0.0), ("2", "VIN_12V", 2.0, 0.0),
    ]),
    ("D2", "BAT54", "D_SOD-123", (54.0, 22.0), [
        ("1", "VIN_12V", -1.7, 0.0), ("2", "+5V", 1.7, 0.0),
    ]),
    ("C1", "10uF", "C_0603_1608Metric", (18.0, 22.0), [
        ("1", "+3V3", -0.8, 0.0), ("2", "GND", 0.8, 0.0),
    ]),
    ("C2", "100nF", "C_0402_1005Metric", (21.0, 22.0), [
        ("1", "+3V3", -0.5, 0.0), ("2", "GND", 0.5, 0.0),
    ]),
    ("C3", "100uF", "C_1206_3216Metric", (48.0, 14.0), [
        ("1", "VIN_12V", -1.6, 0.0), ("2", "GND", 1.6, 0.0),
    ]),
    ("J1", "USB_C", "USB_C_Receptacle_USB2.0", (30.0, 34.0), [
        ("A1", "GND", -4.0, -1.5), ("B1", "GND", -4.0, 2.0),
        ("A4", "+5V", -2.5, -1.5), ("B9", "+5V", 2.5, -1.5),
        ("A6", "USB_DP", 0.0, -1.5), ("A7", "USB_DN", 1.25, -1.5),
    ]),
    ("J2", "PUMP", "TerminalBlock_1x02_P5.08mm", (8.0, 30.0), [
        ("1", "PUMP_SW", 0.0, -2.54), ("2", "VIN_12V", 0.0, 2.54),
    ]),
    ("J3", "12V_IN", "TerminalBlock_1x02_P5.08mm", (8.0, 10.0), [
        ("1", "VIN_12V", 0.0, -2.54), ("2", "GND", 0.0, 2.54),
    ]),
]


def main():
    L = []
    A = L.append
    A("(kicad_pcb (version 20241229) (generator pcbnew)")
    A("  (general (thickness 0.8))")
    A('  (paper "A4")')
    A("  (layers")
    A('    (0 "F.Cu" signal) (31 "B.Cu" signal)')
    A('    (13 "F.Paste" user) (15 "B.Paste" user)')
    A('    (1 "F.Mask" user) (3 "B.Mask" user)')
    A('    (36 "B.SilkS" user "b.silkscreen") (37 "F.SilkS" user "f.silkscreen")')
    A('    (44 "Edge.Cuts" user)')
    A("  )")
    A("  (setup (pad_to_mask_clearance 0.05))")
    for name, code in NETS:
        A(f'  (net {code} "{name}")')

    o = [(0, 0), (BOARD_W, 0), (BOARD_W, BOARD_H), (0, BOARD_H)]
    for i in range(4):
        x1, y1 = o[i]
        x2, y2 = o[(i + 1) % 4]
        A(f'  (gr_line (start {_f(x1)} {_f(y1)}) (end {_f(x2)} {_f(y2)}) '
          f'(stroke (width 0.1) (type solid)) (layer "Edge.Cuts"))')

    netcode = dict(NETS)
    for ref, val, fp, (px, py), pads in PARTS:
        A(f'  (footprint "pressure_rig:{fp}" (layer "F.Cu") (at {_f(px)} {_f(py)})')
        A(f'    (property "Reference" "{ref}")')
        A(f'    (property "Value" "{val}")')
        for p in pads:
            num, net, dx, dy = p[0], p[1], p[2], p[3]
            w = p[4] if len(p) > 4 else 1.0
            h = p[5] if len(p) > 5 else 0.9
            code = netcode[net]
            A(f'    (pad "{num}" smd roundrect (at {_f(dx)} {_f(dy)}) '
              f'(size {_f(w)} {_f(h)}) (layers "F.Cu" "F.Paste" "F.Mask") '
              f'(net {code} "{net}"))')
        A("  )")
    A(")")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write("\n".join(L) + "\n")
    print(OUT)
    print(f"size {_f(BOARD_W)} x {_f(BOARD_H)} mm, 2 layers, 0.8 mm")
    print(f"{len(PARTS)} footprints, {sum(len(p[4]) for p in PARTS)} pads, {len(NETS)} nets")


if __name__ == "__main__":
    main()
