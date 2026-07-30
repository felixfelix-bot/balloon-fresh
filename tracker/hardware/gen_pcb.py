#!/usr/bin/env python3
"""Generate complete .kicad_pcb files for both hub board variants.
Writes S-expression text directly — no pcbnew module needed.
Outputs valid KiCad 9 PCB files with components, routing, and ground pour."""

import os, textwrap, uuid
from router import Router

OUTDIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# Common helpers
# ============================================================

def header(thickness=0.6):
    return f'''(kicad_pcb
  (version 20250114)
  (generator "pcbnew")
  (general
    (thickness {thickness})
  )
  (paper "A4")
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (32 "B.Adhes" user)
    (33 "F.Adhes" user)
    (34 "B.Paste" user)
    (35 "F.Paste" user)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user)
    (39 "F.Mask" user)
    (40 "Dwgs.User" user "User.Drawings")
    (41 "Cmts.User" user "User.Comments")
    (42 "Eco1.User" user "User.Eco1")
    (43 "Eco2.User" user "User.Eco2")
    (44 "Edge.Cuts" user)
    (45 "Margin" user)
    (46 "B.CrtYd" user "B.Courtyard")
    (47 "F.CrtYd" user "F.Courtyard")
    (48 "B.Fab" user "B.Fab")
    (49 "F.Fab" user)
  )
  (setup
    (pad_to_mask_clearance 0.05)
    (aux_axis_origin 0 0)
    (grid_origin 0 0)
    (pcbplotparams
      (layerselection 0x00010fc_ffffffff)
      (plot_on_all_layers_selection 0x0000000_00000000)
      (disableapertmacros false)
      (usegerberextensions false)
      (usegerberattributes true)
      (usegerberadvancedattributes true)
      (creategerberjobfile true)
      (dashed_line_dash_ratio 8.0)
      (dashed_line_gap_ratio 7.0)
      (svgprecision 6)
      (plotframeref false)
      (viasonmask false)
      (mode 1)
      (useauxorigin true)
      (hpglpenwidth 0.05)
      (hpglpenspeed 20)
      (hpglpencolor 255)
      (polygonnegativeps false)
      (psa4outputorientation false)
      (plotreference true)
      (plotvalue true)
      (plotfabbtp false)
      (plotinvisibletext false)
      (sketchpadsonfab false)
      (subtractmaskfromsilk true)
      (outputformat 1)
      (mirror false)
      (drillshape 0)
      (scaleselection 1)
      (outputdirectory "gerbers/")
    )
  )
'''

def net_defs(net_names):
    lines = '  (net 0 "")\n'
    for i, name in enumerate(net_names, 1):
        lines += f'  (net {i} "{name}")\n'
    return lines

NET_CLASSES = '''  (net_class "Default" "Default signal traces"
    (clearance 0.25)
    (trace_width 0.25)
    (via_dia 0.6)
    (via_drill 0.3)
    (uvia_dia 0.3)
    (uvia_drill 0.1)
  )
  (net_class "Power" "Power traces"
    (clearance 0.3)
    (trace_width 0.5)
    (via_dia 0.8)
    (via_drill 0.4)
    (uvia_dia 0.3)
    (uvia_drill 0.1)
  )
  (net_class "RF" "RF antenna traces"
    (clearance 0.3)
    (trace_width 0.8)
    (via_dia 0.8)
    (via_drill 0.4)
    (uvia_dia 0.3)
    (uvia_drill 0.1)
  )
'''

def board_outline(w, h):
    return f'''  (gr_rect (start 0 0) (end {w} {h}) (stroke (width 0.15) (type default)) (fill none) (layer "Edge.Cuts") (uuid "edge-1"))
'''

def ground_pour(w, h, net_id=2, clearance=0.3):
    return f'''  (zone (net {net_id}) (net_name "GND") (layers "B.Cu") (uuid "gnd-pour")
    (hatch edge 0.5)
    (connect_pads (clearance {clearance}))
    (min_thickness 0.25)
    (filled_areas_thickness no)
    (fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5))
    (polygon
      (pts
        (xy 0.5 0.5)
        (xy {w-0.5} 0.5)
        (xy {w-0.5} {h-0.5})
        (xy 0.5 {h-0.5})
      )
    )
  )
'''

# ============================================================
# V1: Non-PA Hub Board (bare LoRa2021)
# ============================================================

def gen_v1():
    W, H = 50, 40
    nets = [
        "3V3", "GND", "SPI0_SCK", "SPI0_MOSI", "SPI0_MISO", "SPI0_NSS",
        "LR2021_BUSY", "LR2021_RST", "LR2021_DIO9",
        "I2C_SDA", "I2C_SCL",
        "RF_SUB_868", "RF_2G4_2400",
        "ESP_TX_RP2040_RX", "RP2040_TX_ESP_RX", "GPS_TX_ESP_RX",
        "VDIV_MID", "STATUS_LED", "LED_ANODE",
        "VCAP", "SOLAR_IN",
    ]
    nid = {name: i+1 for i, name in enumerate(nets)}

    out = header(0.6)
    out += net_defs(nets)
    out += NET_CLASSES
    out += board_outline(W, H)

    # Silkscreen
    out += f'  (gr_text "Balloon Hub V1 — Non-PA" (at {W/2} 2.5) (layer "F.SilkS") (uuid "txt-1") (effects (font (size 1.2 1.2) (thickness 0.2))))\n'
    out += f'  (gr_text "JLCPCB 2-layer 0.6mm" (at {W/2} {H-2}) (layer "B.SilkS") (uuid "txt-2") (effects (font (size 1 1) (thickness 0.15)) (justify mirror)))\n'

    # === Component placements ===
    # ESP32-C3 Mini_V1 header at (12, 12), occupies ~18x22mm
    out += f'''
  (footprint "custom:ESP32-C3_Mini_V1_Header" (layer "F.Cu") (uuid "fp-esp32")
    (at 12 12)
    (descr "ESP32-C3 Mini V1 dev board")
    (property "Reference" "U" (at 0 -11.5) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
    (property "Value" "ESP32-C3-Mini-1" (at 0 11.5) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
    (fp_line (start -9 -11.26) (end 9 -11.26) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
    (fp_line (start 9 -11.26) (end 9 11.26) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
    (fp_line (start 9 11.26) (end -9 11.26) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
    (fp_line (start -9 11.26) (end -9 -11.26) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
    (pad "1" thru_hole rect (at -2.54 -8.89) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["3V3"]} "3V3"))
    (pad "2" thru_hole oval (at -2.54 -6.35) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["GND"]} "GND"))
    (pad "3" thru_hole oval (at -2.54 -3.81) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["ESP_TX_RP2040_RX"]} "ESP_TX_RP2040_RX"))
    (pad "4" thru_hole oval (at -2.54 -1.27) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["RP2040_TX_ESP_RX"]} "RP2040_TX_ESP_RX"))
    (pad "5" thru_hole oval (at -2.54 1.27) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["GPS_TX_ESP_RX"]} "GPS_TX_ESP_RX"))
    (pad "6" thru_hole oval (at -2.54 3.81) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["VDIV_MID"]} "VDIV_MID"))
    (pad "7" thru_hole oval (at -2.54 6.35) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["I2C_SDA"]} "I2C_SDA"))
    (pad "8" thru_hole oval (at -2.54 8.89) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["I2C_SCL"]} "I2C_SCL"))
    (pad "9" thru_hole oval (at 2.54 8.89) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["STATUS_LED"]} "STATUS_LED"))
    (pad "10" thru_hole oval (at 2.54 6.35) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask"))
  )
'''

    # RP2040-Zero header at (38, 12), 13 pins
    rp_x, rp_y = 38, 12
    rp_nets = ["3V3","GND","SPI0_SCK","SPI0_MOSI","SPI0_MISO","SPI0_NSS",
               "LR2021_BUSY","LR2021_DIO9","LR2021_RST",None,
               "RP2040_TX_ESP_RX","ESP_TX_RP2040_RX","GND"]
    rp_pads = ""
    for i, netname in enumerate(rp_nets):
        pin = i + 1
        y = -8.89 + i * 1.5  # spread pins vertically
        pad_type = "rect" if pin == 1 else "oval"
        net_str = f' (net {nid[netname]} "{netname}")' if netname else ""
        rp_pads += f'    (pad "{pin}" thru_hole {pad_type} (at 0 {y:.2f}) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask"){net_str})\n'

    out += f'''
  (footprint "Connector_PinHeader_2.54mm:PinHeader_1x13_P2.54mm_Vertical" (layer "F.Cu") (uuid "fp-rp2040")
    (at {rp_x} {rp_y})
    (descr "RP2040-Zero interface")
    (property "Reference" "U1" (at 0 -2) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
    (property "Value" "RP2040-Zero" (at 0 20) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
    (fp_line (start -1.27 -1.27) (end 1.27 -1.27) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
    (fp_line (start 1.27 -1.27) (end 1.27 32.77) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
    (fp_line (start 1.27 32.77) (end -1.27 32.77) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
    (fp_line (start -1.27 32.77) (end -1.27 -1.27) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
{rp_pads}  )
'''

    # LR2021 module at (25, 25) — 19.81x14.98mm SMD
    lr_x, lr_y = 25, 25
    lr_left_pins = ["3V3","GND","SPI0_MISO","SPI0_MOSI","SPI0_SCK","SPI0_NSS","LR2021_BUSY","GND","RF_SUB_868"]
    lr_right_pins = ["RF_2G4_2400","GND","GND",None,"LR2021_RST","LR2021_DIO9",None,None,"GND"]
    lr_pads = ""
    for i, netname in enumerate(lr_left_pins):
        pin = i + 1
        y = 5.16 - i * 1.29
        net_str = f' (net {nid[netname]} "{netname}")' if netname else ""
        lr_pads += f'    (pad "{pin}" smd rect (at -9.905 {y:.2f}) (size 2 0.7) (layers "F.Cu" "F.Paste" "F.Mask"){net_str})\n'
    for i, netname in enumerate(lr_right_pins):
        pin = i + 10
        y = -5.16 + i * 1.29
        net_str = f' (net {nid[netname]} "{netname}")' if netname else ""
        lr_pads += f'    (pad "{pin}" smd rect (at 9.905 {y:.2f}) (size 2 0.7) (layers "F.Cu" "F.Paste" "F.Mask"){net_str})\n'

    out += f'''
  (footprint "custom:LoRa2021_Castellated" (layer "F.Cu") (uuid "fp-lr2021")
    (at {lr_x} {lr_y})
    (attr smd)
    (descr "NiceRF LoRa2021 18-pin castellated")
    (property "Reference" "U2" (at 0 -9) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
    (property "Value" "LoRa2021" (at 0 9.5) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
    (fp_line (start -9.905 -7.49) (end 9.905 -7.49) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
    (fp_line (start 9.905 -7.49) (end 9.905 7.49) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
    (fp_line (start 9.905 7.49) (end -9.905 7.49) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
    (fp_line (start -9.905 7.49) (end -9.905 -7.49) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
{lr_pads}  )
'''

    # GPS header at (6, 33)
    gps_nets = ["3V3","GND","GPS_TX_ESP_RX",None]
    gps_pads = ""
    for i, netname in enumerate(gps_nets):
        pin = i+1
        y = -3.81 + i*2.54
        net_str = f' (net {nid[netname]} "{netname}")' if netname else ""
        gps_pads += f'    (pad "{pin}" thru_hole oval (at 0 {y:.2f}) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask"){net_str})\n'
    out += f'''
  (footprint "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical" (layer "F.Cu") (uuid "fp-gps")
    (at 6 33)
    (property "Reference" "U3" (at 0 -5) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
    (property "Value" "MAX-M10S" (at 0 8) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.1))))
{gps_pads}  )
'''

    # MS5611 header at (44, 33)
    ms_nets = ["3V3","GND","I2C_SDA","I2C_SCL"]
    ms_pads = ""
    for i, netname in enumerate(ms_nets):
        pin = i+1
        y = -3.81 + i*2.54
        ms_pads += f'    (pad "{pin}" thru_hole oval (at 0 {y:.2f}) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid[netname]} "{netname}"))\n'
    out += f'''
  (footprint "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical" (layer "F.Cu") (uuid "fp-ms5611")
    (at 44 33)
    (property "Reference" "U4" (at 0 -5) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
    (property "Value" "MS5611" (at 0 8) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.1))))
{ms_pads}  )
'''

    # TPS7A02 LDO at (5, 22) — SOT-23-5
    ldo_nets = {1:"VCAP",2:"GND",3:"VCAP",5:"3V3"}
    ldo_pads = ""
    for pin, netname in ldo_nets.items():
        x = [-0.95,0.95,0.95,-0.95,0.95][pin-1]
        y = [-0.95,-0.95,0,0,0.95][pin-1]
        ldo_pads += f'    (pad "{pin}" smd rect (at {x} {y}) (size 0.6 0.6) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid[netname]} "{netname}"))\n'
    out += f'''
  (footprint "Package_TO_SOT_SMD:SOT-23-5" (layer "F.Cu") (uuid "fp-ldo")
    (at 5 22)
    (property "Reference" "U5" (at 0 -2) (layer "F.SilkS") (effects (font (size 0.6 0.6) (thickness 0.1))))
    (property "Value" "TPS7A02" (at 0 2.5) (layer "F.Fab") (effects (font (size 0.6 0.6) (thickness 0.1))))
{ldo_pads}  )
'''

    # BAT54 diode at (4, 18) — SOD-123
    out += f'''
  (footprint "Diode_SMD:D_SOD-123" (layer "F.Cu") (uuid "fp-bat54")
    (at 4 18)
    (property "Reference" "D1" (at 0 -2) (layer "F.SilkS") (effects (font (size 0.6 0.6) (thickness 0.1))))
    (property "Value" "BAT54" (at 0 2.5) (layer "F.Fab") (effects (font (size 0.6 0.6) (thickness 0.1))))
    (pad "1" smd rect (at -1.5 0) (size 1 0.8) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["SOLAR_IN"]} "SOLAR_IN"))
    (pad "2" smd rect (at 1.5 0) (size 1 0.8) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["VCAP"]} "VCAP"))
  )
'''

    # Supercap pads at (8, 37)
    out += f'''
  (footprint "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm" (layer "F.Cu") (uuid "fp-cap")
    (at 8 37)
    (property "Reference" "SC" (at 0 -5) (layer "F.SilkS") (effects (font (size 0.6 0.6) (thickness 0.1))))
    (property "Value" "1F 5.5V" (at 0 5.5) (layer "F.Fab") (effects (font (size 0.6 0.6) (thickness 0.1))))
    (pad "1" thru_hole rect (at -1.75 0) (size 1.5 1.5) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["VCAP"]} "VCAP"))
    (pad "2" thru_hole oval (at 1.75 0) (size 1.5 1.5) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["GND"]} "GND"))
  )
'''

    # Solar input at (3, 37)
    out += f'''
  (footprint "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical" (layer "F.Cu") (uuid "fp-solar")
    (at 3 37)
    (property "Reference" "J" (at 0 -3) (layer "F.SilkS") (effects (font (size 0.6 0.6) (thickness 0.1))))
    (property "Value" "SOLAR" (at 0 5) (layer "F.Fab") (effects (font (size 0.6 0.6) (thickness 0.1))))
    (pad "1" thru_hole rect (at 0 -1.27) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["SOLAR_IN"]} "SOLAR_IN"))
    (pad "2" thru_hole oval (at 0 1.27) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["GND"]} "GND"))
  )
'''

    # LED + resistor at (16, 4)
    out += f'''
  (footprint "LED_SMD:LED_0603_1608Metric" (layer "F.Cu") (uuid "fp-led")
    (at 16 4)
    (property "Reference" "D2" (at 0 -1.5) (layer "F.SilkS") (effects (font (size 0.5 0.5) (thickness 0.08))))
    (property "Value" "STATUS" (at 0 1.5) (layer "F.Fab") (effects (font (size 0.5 0.5) (thickness 0.08))))
    (pad "1" smd rect (at -0.8 0) (size 0.8 0.8) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["GND"]} "GND"))
    (pad "2" smd rect (at 0.8 0) (size 0.8 0.8) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["LED_ANODE"]} "LED_ANODE"))
  )
  (footprint "Resistor_SMD:R_0402_1005Metric" (layer "F.Cu") (uuid "fp-rled")
    (at 18.5 4)
    (property "Reference" "R5" (at 0 -1.2) (layer "F.SilkS") (effects (font (size 0.4 0.4) (thickness 0.06))))
    (property "Value" "330R" (at 0 1.2) (layer "F.Fab") (effects (font (size 0.4 0.4) (thickness 0.06))))
    (pad "1" smd rect (at -0.5 0) (size 0.5 0.5) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["STATUS_LED"]} "STATUS_LED"))
    (pad "2" smd rect (at 0.5 0) (size 0.5 0.5) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["LED_ANODE"]} "LED_ANODE"))
  )
'''

    # Antenna pads at right edge
    out += f'''
  (footprint "TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm" (layer "F.Cu") (uuid "fp-ant1")
    (at {W-2} 20)
    (property "Reference" "AE1" (at 0 -2) (layer "F.SilkS") (effects (font (size 0.6 0.6) (thickness 0.1))))
    (property "Value" "868MHz" (at 0 2.5) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))
    (pad "1" thru_hole circle (at 0 0) (size 2 2) (drill 1.0) (layers "*.Cu" "*.Mask") (net {nid["RF_SUB_868"]} "RF_SUB_868"))
  )
  (footprint "TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm" (layer "F.Cu") (uuid "fp-ant2")
    (at {W-2} 25)
    (property "Reference" "AE2" (at 0 -2) (layer "F.SilkS") (effects (font (size 0.6 0.6) (thickness 0.1))))
    (property "Value" "2.4GHz" (at 0 2.5) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))
    (pad "1" thru_hole circle (at 0 0) (size 2 2) (drill 1.0) (layers "*.Cu" "*.Mask") (net {nid["RF_2G4_2400"]} "RF_2G4_2400"))
  )
'''

    # Test points along bottom edge
    tp_nets = ["SPI0_SCK", "SPI0_MOSI", "3V3", "GND"]
    for i, tpn in enumerate(tp_nets):
        tx = 25 + i * 4
        out += f'''  (footprint "TestPoint:TestPoint_Pad_D1.0mm" (layer "F.Cu") (uuid "fp-tp{i}")
    (at {tx} {H-2})
    (property "Reference" "TP{i+1}" (at 0 -1.5) (layer "F.SilkS") (effects (font (size 0.4 0.4) (thickness 0.06))))
    (property "Value" "{tpn}" (at 0 1.5) (layer "F.Fab") (effects (font (size 0.4 0.4) (thickness 0.06))))
    (pad "1" smd circle (at 0 0) (size 1 1) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid[tpn]} "{tpn}"))
  )
'''

    # Decoupling caps (simple 0402/0805 SMD)
    caps = [
        ("C1", 9.46, 3.11, "100nF", "3V3", "GND", "0402"),   # ESP32
        ("C2", 38, 3, "100nF", "3V3", "GND", "0402"),          # RP2040
        ("C3", 15.1, 30.16, "100nF", "3V3", "GND", "0402"),    # LR2021
        ("C4", 15.1, 32, "10uF", "3V3", "GND", "0805"),        # LR2021 bulk
        ("C5", 6, 30, "100nF", "3V3", "GND", "0402"),           # GPS
        ("C6", 44, 30, "100nF", "3V3", "GND", "0402"),          # MS5611
        ("C7", 6, 24, "10uF", "3V3", "GND", "0805"),            # LDO output
    ]
    for ref, cx, cy, val, p1net, p2net, pkg in caps:
        w = "0.5" if pkg == "0402" else "0.65"
        sz = "0.5 0.5" if pkg == "0402" else "0.8 0.8"
        out += f'''  (footprint "Capacitor_SMD:C_{pkg.upper()}_{"1005" if pkg=="0402" else "2012"}Metric" (layer "F.Cu") (uuid "fp-{ref}")
    (at {cx} {cy})
    (property "Reference" "{ref}" (at 0 -1) (layer "F.SilkS") (effects (font (size 0.4 0.4) (thickness 0.06))))
    (property "Value" "{val}" (at 0 1) (layer "F.Fab") (effects (font (size 0.4 0.4) (thickness 0.06))))
    (pad "1" smd rect (at -{w} 0) (size {sz}) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid[p1net]} "{p1net}"))
    (pad "2" smd rect (at {w} 0) (size {sz}) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid[p2net]} "{p2net}"))
  )
'''

    # I2C pull-ups
    for ref, x, y, net2 in [("R1", 42, 30, "I2C_SDA"), ("R2", 43, 33, "I2C_SCL")]:
        out += f'''  (footprint "Resistor_SMD:R_0402_1005Metric" (layer "F.Cu") (uuid "fp-{ref}")
    (at {x} {y})
    (property "Reference" "{ref}" (at 0 -1) (layer "F.SilkS") (effects (font (size 0.4 0.4) (thickness 0.06))))
    (property "Value" "4.7k" (at 0 1) (layer "F.Fab") (effects (font (size 0.4 0.4) (thickness 0.06))))
    (pad "1" smd rect (at -0.5 0) (size 0.5 0.5) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["3V3"]} "3V3"))
    (pad "2" smd rect (at 0.5 0) (size 0.5 0.5) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid[net2]} "{net2}"))
  )
'''

    # Voltage divider resistors
    out += f'''  (footprint "Resistor_SMD:R_0402_1005Metric" (layer "F.Cu") (uuid "fp-R3")
    (at 3 15)
    (property "Reference" "R3" (at 0 -1) (layer "F.SilkS") (effects (font (size 0.4 0.4) (thickness 0.06))))
    (property "Value" "1M" (at 0 1) (layer "F.Fab") (effects (font (size 0.4 0.4) (thickness 0.06))))
    (pad "1" smd rect (at -0.5 0) (size 0.5 0.5) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["VCAP"]} "VCAP"))
    (pad "2" smd rect (at 0.5 0) (size 0.5 0.5) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["VDIV_MID"]} "VDIV_MID"))
  )
  (footprint "Resistor_SMD:R_0402_1005Metric" (layer "F.Cu") (uuid "fp-R4")
    (at 5 15)
    (property "Reference" "R4" (at 0 -1) (layer "F.SilkS") (effects (font (size 0.4 0.4) (thickness 0.06))))
    (property "Value" "1M" (at 0 1) (layer "F.Fab") (effects (font (size 0.4 0.4) (thickness 0.06))))
    (pad "1" smd rect (at -0.5 0) (size 0.5 0.5) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["VDIV_MID"]} "VDIV_MID"))
    (pad "2" smd rect (at 0.5 0) (size 0.5 0.5) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["GND"]} "GND"))
  )
'''

    # === CLEARANCE-AWARE ROUTING (uses Router class) ===
    rt = Router(W, H, clearance=0.3)
    n3 = nid["3V3"]; nG = nid["GND"]; nSK = nid["SPI0_SCK"]
    nMO = nid["SPI0_MOSI"]; nMI = nid["SPI0_MISO"]; nNS = nid["SPI0_NSS"]
    nBY = nid["LR2021_BUSY"]; nRST = nid["LR2021_RST"]; nD9 = nid["LR2021_DIO9"]
    nSDA = nid["I2C_SDA"]; nSCL = nid["I2C_SCL"]
    nRS = nid["RF_SUB_868"]; nR4 = nid["RF_2G4_2400"]
    nET = nid["ESP_TX_RP2040_RX"]; nRT = nid["RP2040_TX_ESP_RX"]; nGT = nid["GPS_TX_ESP_RX"]
    nVD = nid["VDIV_MID"]; nLED = nid["STATUS_LED"]; nLA = nid["LED_ANODE"]
    nVC = nid["VCAP"]; nSI = nid["SOLAR_IN"]

    # --- Register component pads as obstacles ---
    TH = 1.7  # through-hole pad size
    SMD = 0.5  # SMD pad size
    # ESP32 pads
    esp_pads = [(9.46,3.11,n3),(9.46,5.65,nG),(9.46,8.19,nET),(9.46,10.73,nRT),
                (9.46,13.27,nGT),(9.46,15.81,nVD),(9.46,18.35,nSDA),(9.46,20.89,nSCL),
                (14.54,20.89,nLED),(14.54,18.35,0)]
    for px,py,pn in esp_pads:
        if pn: rt.add_pad(px,py,TH,TH,pn)
    # RP2040 pads
    rp_pads = [(38,3.11,n3),(38,4.61,nG),(38,6.11,nSK),(38,7.61,nMO),
               (38,9.11,nMI),(38,10.61,nNS),(38,12.11,nBY),(38,13.61,nD9),
               (38,15.11,nRST),(38,18.11,nRT),(38,19.61,nET),(38,21.11,nG)]
    for px,py,pn in rp_pads:
        rt.add_pad(px,py,TH,TH,pn)
    # LR2021 pads (left x=15.095, right x=34.905)
    # Pin order: pin1 at BOTTOM (y=30.16), pin9 at TOP (y=19.84)
    lr_left = [(15.095,30.16,n3),(15.095,28.87,nG),(15.095,27.58,nMI),
               (15.095,26.29,nMO),(15.095,25.0,nSK),(15.095,23.71,nNS),
               (15.095,22.42,nBY),(15.095,21.13,nG),(15.095,19.84,nRS)]
    lr_right = [(34.905,30.16,nG),(34.905,28.87,nG),(34.905,27.58,0),
                (34.905,26.29,nD9),(34.905,25.0,nRST),(34.905,23.71,0),
                (34.905,22.42,nG),(34.905,21.13,nG),(34.905,19.84,nR4)]
    for px,py,pn in lr_left+lr_right:
        if pn: rt.add_pad(px,py,SMD,SMD,pn)

    # --- 3V3 POWER BUS on B.Cu ---
    # Main trunk at y=5, connects ESP32 3V3 → RP2040 3V3 → LR2021 3V3
    rt.place(9.46,3.11, 9.46,5, n3, 0.5)  # ESP32 → B.Cu entry
    rt.via(9.46,5, n3)
    rt.place(9.46,5, 38,5, n3, 0.5, "B.Cu")  # main trunk
    rt.via(38,5, n3)
    rt.place(38,5, 38,3.11, n3, 0.5)  # → RP2040
    # Branch to LR2021
    rt.via(25,5, n3)
    rt.place(25,5, 25,19.84, n3, 0.5, "B.Cu")
    rt.place(25,19.84, 15.095,19.84, n3, 0.5)
    # Branch to GPS (6,29.19)
    rt.via(12,5, n3)
    rt.place(12,5, 12,29.19, n3, 0.5, "B.Cu")
    rt.place(12,29.19, 6,29.19, n3, 0.5)
    # Branch to MS5611/R1/R2 (44,29-35)
    rt.via(42,5, n3)
    rt.place(42,5, 42,29.19, n3, 0.5, "B.Cu")
    rt.place(42,29.19, 44,29.19, n3, 0.5)
    rt.place(44,29.19, 44,33, n3, 0.5)
    rt.place(42.5,33, 44,33, n3, 0.25)
    rt.place(41.5,30, 43.5,30, n3, 0.25)
    # Decoupling caps
    rt.place(14.6,30.16, 15.1,30.16, n3, 0.25)
    rt.place(14.45,32.0, 14.6,32.0, n3, 0.25)
    rt.place(14.6,32.0, 14.6,30.16, n3, 0.25)
    # U5 LDO output → 3V3
    rt.place(5.95,22.95, 5.0,22.95, n3, 0.25)
    rt.place(5.0,22.95, 5.0,29.19, n3, 0.5)
    rt.place(5.0,29.19, 6,29.19, n3, 0.5)
    # TP3
    rt.place(33,38, 33,35, n3, 0.25)

    # --- GND connections on B.Cu (stubs only, zone pour fills the rest) ---
    # GND stitching vias (NOT full mesh lines — those conflict with 3V3 bus)
    for gx,gy in [(10,5),(20,5),(30,5),(40,5),(10,15),(20,15),(30,15),
                  (10,25),(20,25),(30,25),(5,35),(15,35),(25,35),(35,35),(45,35)]:
        rt.via(gx,gy, nG)
    # GND pad → nearest via stubs
    rt.place(9.46,5.65, 10,5.65, nG, 0.25); rt.via(10,5.65, nG)
    rt.place(9.96,3.11, 10,3.11, nG, 0.25); rt.place(10,3.11, 10,5, nG, 0.25)
    rt.place(38.5,3.0, 40,3.0, nG, 0.25); rt.place(40,3.0, 40,5, nG, 0.25)
    rt.place(15.095,21.13, 15.5,20.5, nG, 0.25); rt.via(15.5,20.5, nG)
    rt.place(15.095,28.87, 15.5,29.5, nG, 0.25); rt.via(15.5,29.5, nG)
    rt.place(34.905,21.13, 34.5,20.5, nG, 0.25); rt.via(34.5,20.5, nG)
    rt.place(34.905,22.42, 34.5,23.0, nG, 0.25); rt.via(34.5,23.0, nG)
    rt.place(34.905,30.16, 34.5,30.5, nG, 0.25); rt.via(34.5,30.5, nG)
    rt.place(5.95,21.05, 5.0,21.05, nG, 0.25); rt.via(5.0,21.05, nG)
    rt.place(6.65,24, 6.0,24, nG, 0.25); rt.via(6.0,24, nG)
    rt.place(5.5,15, 5.5,14, nG, 0.25); rt.via(5.5,14, nG)
    rt.place(44.5,30, 45,30, nG, 0.25); rt.via(45,30, nG)
    rt.place(15.2,4, 15.2,5, nG, 0.25)
    rt.place(37,38, 37,37, nG, 0.25); rt.via(37,37, nG)
    rt.place(3,38.27, 3,37, nG, 0.5); rt.via(3,37, nG)
    rt.place(9.75,37, 10,37, nG, 0.5); rt.via(10,37, nG)
    rt.place(6.5,30, 7,30, nG, 0.25); rt.via(7,30, nG)
    rt.place(6,31.73, 5,35, nG, 0.25); rt.via(5,35, nG)
    rt.place(15.6,30.16, 16,30, nG, 0.25); rt.via(16,30, nG)

    # --- VCAP / SOLAR power chain ---
    rt.place(3,35.73, 3,33, nSI, 0.5)
    rt.place(3,33, 2.5,18, nSI, 0.5)
    rt.place(2.5,18, 4,18, nSI, 0.5)
    rt.place(5.5,18, 8,18, nVC, 0.5)
    rt.place(8,18, 8,37, nVC, 0.5)
    rt.place(8,37, 6.25,37, nVC, 0.5)
    rt.place(5.95,22, 5.95,18, nVC, 0.25)
    rt.place(5.95,18, 5.5,18, nVC, 0.25)
    rt.place(4.05,21.05, 4.05,22, nVC, 0.25)
    rt.place(4.05,22, 5.95,22, nVC, 0.25)
    rt.place(5.95,22, 5.95,22.95, nVC, 0.25)
    rt.place(2.5,16, 2.5,15, nVC, 0.25)
    rt.place(2.5,15, 4.5,15, nVC, 0.25)

    # --- SIGNAL ROUTING on F.Cu ---
    # SPI bus (RP2040 → LR2021) — pad coords: pin5 SCK=(15.095,25), pin4 MOSI=(15.095,26.29),
    # pin3 MISO=(15.095,27.58), pin6 NSS=(15.095,23.71)
    rt.connect(38,6.11, 15.095,25.0, nSK, 0.25)
    rt.connect(38,7.61, 15.095,26.29, nMO, 0.25)
    rt.connect(38,9.11, 15.095,27.58, nMI, 0.25)
    rt.connect(38,10.61, 15.095,23.71, nNS, 0.25)
    # Control signals — pin7 BUSY=(15.095,22.42), DIO9=right pin (34.905,26.29), RST=right (34.905,25.0)
    rt.connect(38,12.11, 15.095,22.42, nBY, 0.25)
    rt.connect(38,13.61, 34.905,26.29, nD9, 0.25)
    rt.connect(38,15.11, 34.905,25.0, nRST, 0.25)
    # UART
    rt.connect(9.46,8.19, 38,19.61, nET, 0.25)
    rt.connect(38,18.11, 9.46,10.73, nRT, 0.25)
    rt.connect(6,34.27, 9.46,13.27, nGT, 0.25)
    # I2C
    rt.connect(9.46,18.35, 44,33, nSDA, 0.25)
    rt.connect(9.46,20.89, 44,35.54, nSCL, 0.25)
    rt.place(44,33, 44,34.27, nSDA, 0.25)
    rt.place(44,35.54, 44,36.81, nSCL, 0.25)
    # Status LED
    rt.place(14.54,20.89, 14.54,4, nLED, 0.25)
    rt.place(14.54,4, 18,4, nLED, 0.25)
    rt.place(19,4, 16.8,4, nLA, 0.25)
    # Voltage divider
    rt.place(9.46,15.81, 3.5,15.81, nVD, 0.25)
    rt.place(3.5,15.81, 3.5,15, nVD, 0.25)
    rt.place(4.5,15, 5.0,15.81, nVD, 0.25)
    # RF antenna traces
    rt.place(15.095,19.84, 15.095,18, nRS, 0.8)
    rt.place(15.095,18, 48,18, nRS, 0.8)
    rt.place(48,18, 48,20, nRS, 0.8)
    rt.place(34.905,19.84, 34.905,17, nR4, 0.8)
    rt.place(34.905,17, 47,17, nR4, 0.8)
    rt.place(47,17, 47,25, nR4, 0.8)
    rt.place(47,25, 48,25, nR4, 0.8)
    # VCAP bus on F.Cu (local)
    rt.place(2.5,16, 8,16, nVC, 0.25)

    stats = rt.summary()
    print(f"  Router: {stats['segments']} segments, {stats['vias']} vias, "
          f"{stats['warnings']} warnings ({stats['forced_count']} forced, "
          f"{stats['blocked_count']} blocked)")
    if rt.warnings:
        for w in rt.warnings[:5]:
            print(f"    {w}")

    out += rt.emit()

    # Ground pour
    out += "\n  ;; === Ground pour ===\n"
    out += ground_pour(W, H, nid["GND"])

    out += ")\n"  # close (kicad_pcb ...)

    filepath = os.path.join(OUTDIR, "hub_board_v1.kicad_pcb")
    with open(filepath, "w") as f:
        f.write(out)
    print(f"V1 PCB written: {filepath} ({len(out)} bytes)")
    print(f"  Board: {W}x{H}mm, 2-layer, 0.6mm")
    print(f"  Nets: {len(nets)}")
    print(f"  Traces: {len(rt.segments)} ({len(rt.vias)} vias)")
    return filepath

# ============================================================
# V2: F33 2W PA Hub Board
# ============================================================

def gen_v2():
    W, H = 75, 55
    nets = [
        "3V3", "GND", "SPI0_SCK", "SPI0_MOSI", "SPI0_MISO", "SPI0_NSS",
        "LR2021_BUSY", "LR2021_RST", "LR2021_IRQ", "LR2021_CE",
        "I2C_SDA", "I2C_SCL",
        "RF_SUB_868", "RF_2G4_2400",
        "ESP_TX_RP2040_RX", "RP2040_TX_ESP_RX", "GPS_TX_ESP_RX",
        "VDIV_MID", "STATUS_LED", "LED_ANODE",
        "VCAP", "SOLAR_IN",
    ]
    nid = {name: i+1 for i, name in enumerate(nets)}

    out = header(0.8)
    out += net_defs(nets)
    out += NET_CLASSES
    out += board_outline(W, H)

    out += f'  (gr_text "Balloon Hub V2 — F33 2W PA" (at {W/2} 3) (layer "F.SilkS") (uuid "txt-1") (effects (font (size 1.5 1.5) (thickness 0.25))))\n'
    out += f'  (gr_text "JLCPCB 2-layer 0.8mm" (at {W/2} {H-3}) (layer "B.SilkS") (uuid "txt-2") (effects (font (size 1.2 1.2) (thickness 0.2)) (justify mirror)))\n'

    # F33 module CENTER at (37.5, 28) — 39x21mm dominates the board
    f33_x, f33_y = 37.5, 28
    # F33 pin map (from datasheet V1.1):
    # Left pins 1-9 (top to bottom): VCC, GND, GND, GND, CE, GND, GND, GND, ANT
    # Right pins 10-18: ANT-2G4, GND, SCK, NSS, BUSY, MOSI, MISO, RESET, IRQ
    f33_left = ["3V3","GND","GND","GND","VCAP","GND","GND","GND","RF_SUB_868"]
    # Note: F33 VCC needs 5V from VCAP, but we model the net as "3V3" for routing.
    # Actually for F33, VCC connects to VCAP (5V supercap bus), NOT 3V3.
    f33_left[0] = "VCAP"  # F33 pin 1 = VCC = 5V from supercap
    f33_left[4] = "LR2021_CE"  # F33 pin 5 = CE
    f33_right = ["RF_2G4_2400","GND","SPI0_SCK","SPI0_NSS","LR2021_BUSY","SPI0_MOSI","SPI0_MISO","LR2021_RST","LR2021_IRQ"]

    f33_pads = ""
    # Left side: pins 1-9, pitch 2.0mm, offset 1.5mm from top
    for i, netname in enumerate(f33_left):
        pin = i+1
        y = 9.0 - i * 2.0  # first pad at +9.0, pitch 2.0mm
        f33_pads += f'    (pad "{pin}" smd rect (at -19.5 {y:.1f}) (size 2 1.0) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid[netname]} "{netname}"))\n'
    # Right side: pins 10-18
    for i, netname in enumerate(f33_right):
        pin = i+10
        y = -7.0 - i * 2.0  # first right pad at -7.0
        # Wait — right pins go top to bottom too. Pin 10 at top (+9), pin 18 at bottom (-7)
        y = 9.0 - i * 2.0
        f33_pads += f'    (pad "{pin}" smd rect (at 19.5 {y:.1f}) (size 2 1.0) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid[netname]} "{netname}"))\n'

    out += f'''
  (footprint "custom:LoRa2021F33_2G4" (layer "F.Cu") (uuid "fp-f33")
    (at {f33_x} {f33_y})
    (attr smd)
    (descr "NiceRF LoRa2021F33-2G4 2W PA module 39x21mm")
    (property "Reference" "U2" (at 0 -12) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
    (property "Value" "LoRa2021F33-2G4" (at 0 12.5) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
    (fp_line (start -19.5 -10.5) (end 19.5 -10.5) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
    (fp_line (start 19.5 -10.5) (end 19.5 10.5) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
    (fp_line (start 19.5 10.5) (end -19.5 10.5) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
    (fp_line (start -19.5 10.5) (end -19.5 -10.5) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
    (fp_circle (center -18 9) (end -17.7 9) (stroke (width 0.12) (type solid)) (fill none) (layer "F.SilkS"))
{f33_pads}  )
'''

    # ESP32 at (12, 15)
    out += f'''
  (footprint "custom:ESP32-C3_Mini_V1_Header" (layer "F.Cu") (uuid "fp-esp32")
    (at 12 15)
    (descr "ESP32-C3 Mini V1")
    (property "Reference" "U" (at 0 -11.5) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
    (property "Value" "ESP32-C3-Mini-1" (at 0 11.5) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
    (fp_line (start -9 -11.26) (end 9 -11.26) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
    (fp_line (start 9 -11.26) (end 9 11.26) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
    (fp_line (start 9 11.26) (end -9 11.26) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
    (fp_line (start -9 11.26) (end -9 -11.26) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
    (pad "1" thru_hole rect (at -2.54 -8.89) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["3V3"]} "3V3"))
    (pad "2" thru_hole oval (at -2.54 -6.35) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["GND"]} "GND"))
    (pad "3" thru_hole oval (at -2.54 -3.81) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["ESP_TX_RP2040_RX"]} "ESP_TX_RP2040_RX"))
    (pad "4" thru_hole oval (at -2.54 -1.27) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["RP2040_TX_ESP_RX"]} "RP2040_TX_ESP_RX"))
    (pad "5" thru_hole oval (at -2.54 1.27) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["GPS_TX_ESP_RX"]} "GPS_TX_ESP_RX"))
    (pad "6" thru_hole oval (at -2.54 3.81) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["VDIV_MID"]} "VDIV_MID"))
    (pad "7" thru_hole oval (at -2.54 6.35) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["I2C_SDA"]} "I2C_SDA"))
    (pad "8" thru_hole oval (at -2.54 8.89) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["I2C_SCL"]} "I2C_SCL"))
    (pad "9" thru_hole oval (at 2.54 8.89) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["STATUS_LED"]} "STATUS_LED"))
    (pad "10" thru_hole oval (at 2.54 6.35) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask"))
  )
'''

    # RP2040 at (63, 15), 14 pins now (added CE on GP9)
    rp_x, rp_y = 63, 15
    rp_nets = ["3V3","GND","SPI0_SCK","SPI0_MOSI","SPI0_MISO","SPI0_NSS",
               "LR2021_BUSY","LR2021_IRQ","LR2021_RST",None,"LR2021_CE",
               "RP2040_TX_ESP_RX","ESP_TX_RP2040_RX","GND"]
    rp_pads = ""
    for i, netname in enumerate(rp_nets):
        pin = i + 1
        y = -8.89 + i * 2.54
        pad_type = "rect" if pin == 1 else "oval"
        net_str = f' (net {nid[netname]} "{netname}")' if netname else ""
        rp_pads += f'    (pad "{pin}" thru_hole {pad_type} (at 0 {y:.2f}) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask"){net_str})\n'
    out += f'''
  (footprint "Connector_PinHeader_2.54mm:PinHeader_1x14_P2.54mm_Vertical" (layer "F.Cu") (uuid "fp-rp2040")
    (at {rp_x} {rp_y})
    (property "Reference" "U1" (at 0 -2) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
    (property "Value" "RP2040-Zero" (at 0 22) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
    (fp_line (start -1.27 -1.27) (end 1.27 -1.27) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
    (fp_line (start 1.27 -1.27) (end 1.27 32.77) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
    (fp_line (start 1.27 32.77) (end -1.27 32.77) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
    (fp_line (start -1.27 32.77) (end -1.27 -1.27) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
{rp_pads}  )
'''

    # SMA connectors at edges — end-launch
    # Sub-GHz SMA at left edge (y=28)
    out += f'''
  (footprint "custom:SMA_Edge_Mount" (layer "F.Cu") (uuid "fp-sma1")
    (at 2 28)
    (descr "SMA end-launch edge connector for sub-GHz antenna")
    (property "Reference" "J1" (at 5 -3) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
    (property "Value" "SMA-868" (at 5 4) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
    ;; Center signal pad
    (pad "1" smd rect (at 2 0) (size 2 1.5) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["RF_SUB_868"]} "RF_SUB_868"))
    ;; Ground pads
    (pad "2" smd rect (at 2 -2.5) (size 2 2) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["GND"]} "GND"))
    (pad "3" smd rect (at 2 2.5) (size 2 2) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["GND"]} "GND"))
  )
'''

    # 2.4GHz SMA at right edge
    out += f'''
  (footprint "custom:SMA_Edge_Mount" (layer "F.Cu") (uuid "fp-sma2")
    (at {W-2} 28)
    (descr "SMA end-launch edge connector for 2.4GHz antenna")
    (property "Reference" "J2" (at -5 -3) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
    (property "Value" "SMA-2G4" (at -5 4) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
    (pad "1" smd rect (at -2 0) (size 2 1.5) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["RF_2G4_2400"]} "RF_2G4_2400"))
    (pad "2" smd rect (at -2 -2.5) (size 2 2) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["GND"]} "GND"))
    (pad "3" smd rect (at -2 2.5) (size 2 2) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["GND"]} "GND"))
  )
'''

    # GPS header at (6, 45)
    gps_nets = ["3V3","GND","GPS_TX_ESP_RX",None]
    gps_pads = ""
    for i, netname in enumerate(gps_nets):
        pin = i+1
        y = -3.81 + i*2.54
        net_str = f' (net {nid[netname]} "{netname}")' if netname else ""
        gps_pads += f'    (pad "{pin}" thru_hole oval (at 0 {y:.2f}) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask"){net_str})\n'
    out += f'''
  (footprint "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical" (layer "F.Cu") (uuid "fp-gps")
    (at 6 45)
    (property "Reference" "U3" (at 0 -5) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
    (property "Value" "MAX-M10S" (at 0 8) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.1))))
{gps_pads}  )
'''

    # MS5611 at (68, 45)
    ms_nets = ["3V3","GND","I2C_SDA","I2C_SCL"]
    ms_pads = ""
    for i, netname in enumerate(ms_nets):
        pin = i+1
        y = -3.81 + i*2.54
        ms_pads += f'    (pad "{pin}" thru_hole oval (at 0 {y:.2f}) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid[netname]} "{netname}"))\n'
    out += f'''
  (footprint "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical" (layer "F.Cu") (uuid "fp-ms5611")
    (at 68 45)
    (property "Reference" "U4" (at 0 -5) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
    (property "Value" "MS5611" (at 0 8) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.1))))
{ms_pads}  )
'''

    # Power components
    out += f'''
  (footprint "Package_TO_SOT_SMD:SOT-23-5" (layer "F.Cu") (uuid "fp-ldo")
    (at 8 40)
    (property "Reference" "U5" (at 0 -2) (layer "F.SilkS") (effects (font (size 0.6 0.6) (thickness 0.1))))
    (property "Value" "TPS7A02" (at 0 2.5) (layer "F.Fab") (effects (font (size 0.6 0.6) (thickness 0.1))))
    (pad "1" smd rect (at -0.95 -0.95) (size 0.6 0.6) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["VCAP"]} "VCAP"))
    (pad "2" smd rect (at 0.95 -0.95) (size 0.6 0.6) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["GND"]} "GND"))
    (pad "3" smd rect (at 0.95 0) (size 0.6 0.6) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["VCAP"]} "VCAP"))
    (pad "5" smd rect (at 0.95 0.95) (size 0.6 0.6) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["3V3"]} "3V3"))
  )
  (footprint "Diode_SMD:D_SOD-123" (layer "F.Cu") (uuid "fp-bat54")
    (at 5 40)
    (property "Reference" "D1" (at 0 -2) (layer "F.SilkS") (effects (font (size 0.6 0.6) (thickness 0.1))))
    (property "Value" "BAT54" (at 0 2.5) (layer "F.Fab") (effects (font (size 0.6 0.6) (thickness 0.1))))
    (pad "1" smd rect (at -1.5 0) (size 1 0.8) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["SOLAR_IN"]} "SOLAR_IN"))
    (pad "2" smd rect (at 1.5 0) (size 1 0.8) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["VCAP"]} "VCAP"))
  )
'''

    # F33 bulk decoupling: 100µF (1206) + 10µF (0805) + 100nF (0402)
    out += f'''
  (footprint "Capacitor_SMD:C_1206_3216Metric" (layer "F.Cu") (uuid "fp-cblk")
    (at 18 37)
    (property "Reference" "C8" (at 0 -1.5) (layer "F.SilkS") (effects (font (size 0.6 0.6) (thickness 0.1))))
    (property "Value" "100uF" (at 0 1.5) (layer "F.Fab") (effects (font (size 0.6 0.6) (thickness 0.1))))
    (pad "1" smd rect (at -1.6 0) (size 1.5 1.6) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["VCAP"]} "VCAP"))
    (pad "2" smd rect (at 1.6 0) (size 1.5 1.6) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["GND"]} "GND"))
  )
  (footprint "Capacitor_SMD:C_0805_2012Metric" (layer "F.Cu") (uuid "fp-cblk2")
    (at 18 19)
    (property "Reference" "C9" (at 0 -1) (layer "F.SilkS") (effects (font (size 0.6 0.6) (thickness 0.1))))
    (property "Value" "10uF" (at 0 1) (layer "F.Fab") (effects (font (size 0.6 0.6) (thickness 0.1))))
    (pad "1" smd rect (at -0.85 0) (size 0.8 0.8) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["VCAP"]} "VCAP"))
    (pad "2" smd rect (at 0.85 0) (size 0.8 0.8) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["GND"]} "GND"))
  )
  (footprint "Capacitor_SMD:C_0402_1005Metric" (layer "F.Cu") (uuid "fp-cblk3")
    (at 16 19)
    (property "Reference" "C10" (at 0 -1) (layer "F.SilkS") (effects (font (size 0.4 0.4) (thickness 0.06))))
    (property "Value" "100nF" (at 0 1) (layer "F.Fab") (effects (font (size 0.4 0.4) (thickness 0.06))))
    (pad "1" smd rect (at -0.5 0) (size 0.5 0.5) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["VCAP"]} "VCAP"))
    (pad "2" smd rect (at 0.5 0) (size 0.5 0.5) (layers "F.Cu" "F.Paste" "F.Mask") (net {nid["GND"]} "GND"))
  )
'''

    # Solar input + supercap
    out += f'''
  (footprint "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical" (layer "F.Cu") (uuid "fp-solar")
    (at 4 48)
    (property "Reference" "J3" (at 0 -3) (layer "F.SilkS") (effects (font (size 0.6 0.6) (thickness 0.1))))
    (property "Value" "SOLAR" (at 0 5) (layer "F.Fab") (effects (font (size 0.6 0.6) (thickness 0.1))))
    (pad "1" thru_hole rect (at 0 -1.27) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["SOLAR_IN"]} "SOLAR_IN"))
    (pad "2" thru_hole oval (at 0 1.27) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["GND"]} "GND"))
  )
  (footprint "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm" (layer "F.Cu") (uuid "fp-cap")
    (at 10 48)
    (property "Reference" "SC" (at 0 -5) (layer "F.SilkS") (effects (font (size 0.6 0.6) (thickness 0.1))))
    (property "Value" "1F 5.5V" (at 0 5.5) (layer "F.Fab") (effects (font (size 0.6 0.6) (thickness 0.1))))
    (pad "1" thru_hole rect (at -1.75 0) (size 1.5 1.5) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["VCAP"]} "VCAP"))
    (pad "2" thru_hole oval (at 1.75 0) (size 1.5 1.5) (drill 0.8) (layers "*.Cu" "*.Mask") (net {nid["GND"]} "GND"))
  )
'''

    # === CLEARANCE-AWARE ROUTING (uses Router class) ===
    rt = Router(W, H, clearance=0.25)
    n3 = nid["3V3"]; nG = nid["GND"]; nSK = nid["SPI0_SCK"]
    nMO = nid["SPI0_MOSI"]; nMI = nid["SPI0_MISO"]; nNS = nid["SPI0_NSS"]
    nBY = nid["LR2021_BUSY"]; nRST = nid["LR2021_RST"]; nIRQ = nid["LR2021_IRQ"]
    nCE = nid["LR2021_CE"]; nSDA = nid["I2C_SDA"]; nSCL = nid["I2C_SCL"]
    nRS = nid["RF_SUB_868"]; nR4 = nid["RF_2G4_2400"]
    nET = nid["ESP_TX_RP2040_RX"]; nRT = nid["RP2040_TX_ESP_RX"]; nGT = nid["GPS_TX_ESP_RX"]
    nVD = nid["VDIV_MID"]; nLED = nid["STATUS_LED"]; nVC = nid["VCAP"]; nSI = nid["SOLAR_IN"]

    # Register component pads as obstacles
    TH = 1.7; SMD = 0.5
    # ESP32 at (12,15) — pads at x=12-2.54=9.46
    esp_nets = ["3V3","GND","ESP_TX_RP2040_RX","RP2040_TX_ESP_RX","GPS_TX_ESP_RX",
                "VDIV_MID","I2C_SDA","I2C_SCL","STATUS_LED"]
    for i, nn in enumerate(esp_nets):
        px = 9.46 if i < 8 else 14.54
        py = 15 + (-8.89 + i * 2.54) if i < 8 else 15 + 8.89
        rt.add_pad(px, py, TH, TH, nid[nn])
    # RP2040 at (63,15) — NOW 2.54mm pitch
    rp_nets2 = ["3V3","GND","SPI0_SCK","SPI0_MOSI","SPI0_MISO","SPI0_NSS",
                "LR2021_BUSY","LR2021_IRQ","LR2021_RST",None,"LR2021_CE",
                "RP2040_TX_ESP_RX","ESP_TX_RP2040_RX","GND"]
    for i, nn in enumerate(rp_nets2):
        py = 15 + (-8.89 + i * 2.54)
        if nn: rt.add_pad(63, py, TH, TH, nid[nn])
    # F33 left pads at x=18, right at x=57, pitch 2.0mm
    f33_left_nets = ["VCAP","GND","GND","GND","LR2021_CE","GND","GND","GND","RF_SUB_868"]
    f33_right_nets = ["RF_2G4_2400","GND","SPI0_SCK","SPI0_NSS","LR2021_BUSY",
                      "SPI0_MOSI","SPI0_MISO","LR2021_RST","LR2021_IRQ"]
    for i, nn in enumerate(f33_left_nets):
        py = 28 + (9.0 - i * 2.0)
        rt.add_pad(18, py, SMD, SMD, nid[nn])
    for i, nn in enumerate(f33_right_nets):
        py = 28 + (9.0 - i * 2.0)
        rt.add_pad(57, py, SMD, SMD, nid[nn])

    # 3V3 POWER BUS on B.Cu (FIX 1: all trunk segments on B.Cu, vias at endpoints)
    # FIX A: Route vertical at x=7 to avoid ESP32 through-hole pads at x=9.46
    rt.via(9.46, 6.11, n3)   # ESP32 pin1 (same net, OK on pad)
    rt.via(63, 6.11, n3)     # RP2040 pin1
    rt.via(6, 41.19, n3)     # GPS pin1
    # FIX 3: LDO output → right first, then up (avoid GND pad at 8.95,39.05)
    rt.place(8.95, 40.95, 12, 40.95, n3, 0.5)     # F.Cu: LDO pin5 → right to x=12
    rt.via(12, 40.95, n3)                           # transition to B.Cu
    rt.place(12, 40.95, 12, 38, n3, 0.5, "B.Cu")    # B.Cu: up to trunk (x=12, not x=10)
    # 3V3 trunk on B.Cu at x=12 (VCAP bus at x=10, 2mm separation)
    rt.place(12, 38, 7, 38, n3, 0.5, "B.Cu")        # trunk left to ESP32 column
    rt.via(7, 38, n3)
    rt.place(7, 38, 7, 6.11, n3, 0.5, "B.Cu")       # ESP32 vertical at x=7
    rt.via(7, 6.11, n3)
    rt.place(7, 6.11, 9.46, 6.11, n3, 0.5)          # to ESP32 pin1 on F.Cu

    rt.place(12, 38, 60, 38, n3, 0.5, "B.Cu")       # trunk to x=60
    rt.place(60, 38, 60, 6.11, n3, 0.5, "B.Cu")     # up to RP2040 row on B.Cu
    rt.via(60, 6.11, n3)
    rt.place(60, 6.11, 63, 6.11, n3, 0.5)           # to RP2040 pin1 on F.Cu

    rt.via(6, 38, n3)
    rt.place(12, 38, 6, 38, n3, 0.5, "B.Cu")        # to GPS on B.Cu
    rt.place(6, 38, 6, 41.19, n3, 0.5, "B.Cu")      # GPS pin1 on B.Cu
    rt.via(6, 41.19, n3)

    rt.place(60, 38, 68, 38, n3, 0.5, "B.Cu")       # to MS5611 on B.Cu
    rt.place(68, 38, 68, 41.19, n3, 0.5, "B.Cu")    # MS5611 pin1 on B.Cu
    rt.via(68, 41.19, n3)

    # VCAP power chain (F33 needs 5V from supercap)
    # FIX: VCAP traces on B.Cu to avoid F.Cu pad conflicts
    rt.place(4, 46.73, 4, 44, nSI, 0.8)
    rt.place(4, 44, 3.5, 40, nSI, 0.8)
    # BAT54 cathode → via → B.Cu VCAP bus
    rt.via(5, 40, nVC)
    rt.place(5, 40, 10, 40, nVC, 0.8, "B.Cu")
    # LDO pin1 (VCAP) at (7.05,39.05) → via → B.Cu
    rt.via(7.05, 39.05, nVC)
    rt.place(7.05, 39.05, 10, 39.05, nVC, 0.8, "B.Cu")
    # B.Cu VCAP bus at x=10, down to supercap
    rt.place(10, 40, 10, 48, nVC, 0.8, "B.Cu")
    rt.via(8.25, 48, nVC)
    rt.place(10, 48, 8.25, 48, nVC, 0.8, "B.Cu")
    # F33 VCC (pin1 at 18,37) → via → B.Cu
    rt.via(18, 37, nVC)
    rt.place(18, 37, 14, 37, nVC, 0.8, "B.Cu")
    rt.place(14, 37, 14, 19, nVC, 0.8, "B.Cu")
    rt.via(17.15, 19, nVC)
    rt.place(14, 19, 17.15, 19, nVC, 0.8, "B.Cu")

    # GND stitching vias (not mesh — zone pour handles GND)
    # FIX 2: (56,31)→(56,28); (57,31) removed (was on SPI0_NSS pad)
    # FIX B: (60,10)→(55,10) to avoid 3V3 trunk at x=60
    # FIX C: x=19 GND vias at (19,31),(19,27) → moved to (22,31),(22,27) to avoid F33 GND stubs
    for gx, gy in [(15,10),(55,10),(30,50),(70,50),(5,50),(40,45),
                   (19,35),(19,33),(22,31),(22,27),(19,25),(19,23),
                   (56,28),(20,37),(50,37)]:
        rt.via(gx, gy, nG)
    # F33 GND pad stubs
    for gy in [35,33,31,27,25,23]:
        rt.place(18, gy, 19, gy, nG, 0.5)
    # Extended stubs for moved vias at (22,31) and (22,27)
    rt.place(19, 31, 22, 31, nG, 0.5)
    rt.place(19, 27, 22, 27, nG, 0.5)
    # FIX: F33 right GND pad (57,35) → GND via at (55,37) (avoid SCK pad at 57,33)
    rt.place(57, 35, 55, 37, nG, 0.5)

    # SIGNAL ROUTING on F.Cu
    # CE: F33 pin5 (18,29) → RP pin11 (63, 15+(-8.89+10*2.54)=15+16.51=31.51)
    rt.connect(18, 29, 63, 31.51, nCE, 0.25)
    # RF traces (fat, short)
    rt.place(18, 21, 18, 17, nRS, 0.8)
    rt.place(18, 17, 2, 17, nRS, 0.8)
    # FIX: route RF_SUB at x=2 not x=4 to avoid SMA J1 GND pads at (4,25.5) and (4,30.5)
    rt.place(2, 17, 2, 28, nRS, 0.8)
    rt.place(2, 28, 4, 28, nRS, 0.8)
    # FIX: RF_2G4 route down from (57,37) → right at y=35 (avoid SCK pad at 57,33)
    rt.place(57, 37, 57, 35, nR4, 0.8)
    rt.place(57, 35, 72, 35, nR4, 0.8)
    # FIX: route at x=72 to avoid SMA J2 GND pads at (71,30.5)
    rt.place(72, 35, 72, 28, nR4, 0.8)
    rt.place(72, 28, 73, 28, nR4, 0.8)
    # SPI: F33 right → RP2040 (use B.Cu for long runs)
    # SCK: F33 pin12 (57,33) → RP pin3 (63, 15+(-8.89+2*2.54)=15-3.81=11.19)
    rt.connect(57, 33, 63, 11.19, nSK, 0.25)
    # NSS: F33 pin13 (57,31) → RP pin6 (63, 15+(-8.89+5*2.54)=15+3.81=18.81)
    rt.connect(57, 31, 63, 18.81, nNS, 0.25)
    # BUSY: F33 pin14 (57,29) → RP pin7 (63, 15+(-8.89+6*2.54)=15+6.35=21.35)
    rt.connect(57, 29, 63, 21.35, nBY, 0.25)
    # MOSI: F33 pin15 (57,27) → RP pin4 (63, 15+(-8.89+3*2.54)=15-1.27=13.73)
    rt.connect(57, 27, 63, 13.73, nMO, 0.25)
    # MISO: F33 pin16 (57,25) → RP pin5 (63, 15+(-8.89+4*2.54)=15+1.27=16.27)
    rt.connect(57, 25, 63, 16.27, nMI, 0.25)
    # RST: F33 pin17 (57,23) → RP pin9 (63, 15+(-8.89+8*2.54)=15+11.43=26.43)
    rt.connect(57, 23, 63, 26.43, nRST, 0.25)
    # IRQ: F33 pin18 (57,21) → RP pin8 (63, 15+(-8.89+7*2.54)=15+8.89=23.89)
    rt.connect(57, 21, 63, 23.89, nIRQ, 0.25)
    # UART (route on B.Cu to avoid crossing RF traces on F.Cu)
    # ESP_TX → RP_RX: ESP pin3 (9.46,11.19) → RP pin13 (63, 36.59)
    rt.via(9.46, 11.19, nET)
    rt.place(9.46, 11.19, 63, 11.19, nET, 0.25, "B.Cu")
    rt.place(63, 11.19, 63, 36.59, nET, 0.25, "B.Cu")
    rt.via(63, 36.59, nET)
    # RP_TX → ESP: RP pin12 (63, 34.05) → ESP pin4 (9.46,13.73)
    rt.via(63, 34.05, nRT)
    rt.place(63, 34.05, 8, 34.05, nRT, 0.25, "B.Cu")
    rt.place(8, 34.05, 8, 13.73, nRT, 0.25, "B.Cu")
    rt.place(8, 13.73, 9.46, 13.73, nRT, 0.25, "B.Cu")
    rt.via(9.46, 13.73, nRT)
    # GPS_TX → ESP: GPS pin3 (6,46.27) → ESP pin5 (9.46,16.27)
    rt.via(6, 46.27, nGT)
    rt.place(6, 46.27, 3, 46.27, nGT, 0.25, "B.Cu")
    rt.place(3, 46.27, 3, 16.27, nGT, 0.25, "B.Cu")
    rt.place(3, 16.27, 9.46, 16.27, nGT, 0.25, "B.Cu")
    rt.via(9.46, 16.27, nGT)
    # I2C (route on B.Cu, offset from pad columns)
    # SDA: ESP pin7 (9.46,21.35) → MS pin3 (68,46.27)
    rt.via(9.46, 21.35, nSDA)
    rt.place(9.46, 21.35, 65, 21.35, nSDA, 0.25, "B.Cu")
    rt.place(65, 21.35, 65, 46.27, nSDA, 0.25, "B.Cu")
    rt.place(65, 46.27, 68, 46.27, nSDA, 0.25, "B.Cu")
    rt.via(68, 46.27, nSDA)
    # SCL: ESP pin8 (9.46,23.89) → MS pin4 (68,48.81)
    # FIX: route at y=25 not y=23.89 to avoid IRQ pad at (63,23.89)
    rt.via(9.46, 23.89, nSCL)
    rt.place(9.46, 23.89, 9.46, 25, nSCL, 0.25, "B.Cu")
    rt.place(9.46, 25, 66, 25, nSCL, 0.25, "B.Cu")
    rt.place(66, 25, 66, 48.81, nSCL, 0.25, "B.Cu")
    rt.place(66, 48.81, 68, 48.81, nSCL, 0.25, "B.Cu")
    rt.via(68, 48.81, nSCL)
    # STATUS LED
    rt.place(14.54, 23.89, 14.54, 5, nLED, 0.25)
    rt.place(14.54, 5, 18, 5, nLED, 0.25)
    # VDIV
    rt.place(9.46, 18.81, 3, 18.81, nVD, 0.25)

    stats = rt.summary()
    print(f"  F33 Router: {stats['segments']} segments, {stats['vias']} vias, "
          f"{stats['warnings']} warnings")
    if rt.warnings:
        for w in rt.warnings[:5]:
            print(f"    {w}")

    out += rt.emit()

    # Ground pour + close
    out += ground_pour(W, H, nid["GND"])
    out += ")\n"

    filepath = os.path.join(OUTDIR, "hub_board_f33.kicad_pcb")
    with open(filepath, "w") as f:
        f.write(out)
    print(f"V2 F33 PCB written: {filepath} ({len(out)} bytes)")
    print(f"  Board: {W}x{H}mm, 2-layer, 0.8mm")
    print(f"  F33 module: 39x21mm at center")
    print(f"  SMA connectors: 2x edge-mount (sub-GHz + 2.4GHz)")
    print(f"  Traces: {len(rt.segments)} ({len(rt.vias)} vias)")
    return filepath


def clean_pcb(filepath):
    """Post-process generated .kicad_pcb: strip comments, fix format for KiCad 9."""
    import re, uuid as uuidmod
    with open(filepath) as f:
        content = f.read()

    # 1. Remove all ; comment lines (KiCad 9 chokes on these)
    lines = [l for l in content.split('\n') if not l.strip().startswith(';')]
    content = '\n'.join(lines)

    # 2. Fix version + generator_version
    content = content.replace('(version 20250114)', '(version 20241229)')
    if '(generator_version "9.0")' not in content:
        content = content.replace('(generator "pcbnew")\n', '(generator "pcbnew")\n  (generator_version "9.0")\n')

    # 3. Fix setup section: remove pcbplotparams, add mandatory fields
    content = re.sub(
        r'\(setup\n.*?\n  \)',
        '(setup\n    (pad_to_mask_clearance 0)\n    (allow_soldermask_bridges_in_footprints no)\n    (tenting front back)\n    (aux_axis_origin 0 0)\n    (grid_origin 0 0)\n  )',
        content, flags=re.DOTALL
    )

    # 4. Fix UUIDs: replace string-IDs with real UUID v4
    content = re.sub(
        r'\(uuid "([^"]{36})"\)',
        lambda m: f'(uuid "{m.group(1)}")',  # leave real UUIDs alone
        content
    )
    content = re.sub(
        r'\(uuid "(seg-\d+|via-\d+|edge-\d+|txt-\d+|fp-[a-zA-Z0-9_{}-]+|gnd-pour|pad-[a-zA-Z0-9_-]+|outline-[a-zA-Z0-9_-]+|fab-[a-zA-Z0-9_-]+|crtyd-[a-zA-Z0-9_-]+|fp-ref|fp-val|usb-label|ufl-label)"\)',
        lambda m: f'(uuid "{uuidmod.uuid4()}")',
        content
    )

    # 5. Fix segment net format: (net N "name") -> (net N) inside segments/vias
    content = re.sub(
        r'(\(segment .*?\(net \d+) "[^"]*"\)',
        r'\1)',
        content
    )
    content = re.sub(
        r'(\(via .*?\(net \d+) "[^"]*"\)',
        r'\1)',
        content
    )

    # 6. Fix zone layers -> layer
    content = content.replace('(zone (net', '(zone (net')  # no-op safety
    content = re.sub(
        r'(\(zone \(net \d+\) \(net_name "[^"]*"\) )\(layers "B\.Cu"\)',
        r'\1(layer "B.Cu")',
        content
    )

    with open(filepath, 'w') as f:
        f.write(content)


if __name__ == "__main__":
    v1 = gen_v1()
    v2 = gen_v2()
    clean_pcb(v1)
    clean_pcb(v2)
    print("\nDone. Both PCB files generated + cleaned for KiCad 9.")
    print(f"V1: {v1}")
    print(f"V2: {v2}")
