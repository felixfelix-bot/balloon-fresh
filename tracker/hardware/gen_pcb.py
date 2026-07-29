#!/usr/bin/env python3
"""Generate complete .kicad_pcb files for both hub board variants.
Writes S-expression text directly — no pcbnew module needed.
Outputs valid KiCad 9 PCB files with components, routing, and ground pour."""

import os, textwrap, uuid

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

    # === KEY TRACES (power + critical signal paths) ===
    # These are the most important traces. Unrouted nets can be added later or in KiCad GUI.
    seg_id = 1
    def seg(x1, y1, x2, y2, net_name, width=0.25, layer="F.Cu"):
        nonlocal seg_id
        s = f'  (segment (start {x1:.2f} {y1:.2f}) (end {x2:.2f} {y2:.2f}) (width {width}) (layer "{layer}") (net {nid[net_name]} "{net_name}") (uuid "seg-{seg_id:03d}"))\n'
        seg_id += 1
        return s

    def via(x, y, net_name):
        nonlocal seg_id
        s = f'  (via (at {x:.2f} {y:.2f}) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net {nid[net_name]} "{net_name}") (uuid "via-{seg_id:03d}"))\n'
        seg_id += 1
        return s

    traces = "\n"
    # === POWER TRACES ===
    traces += seg(5, 22.95, 5, 20, "3V3", 0.5)
    traces += seg(5, 20, 9.46, 20, "3V3", 0.5)
    traces += seg(9.46, 20, 9.46, 3.11, "3V3", 0.5)
    traces += seg(5, 20, 38, 20, "3V3", 0.5)
    traces += seg(38, 20, 38, 3.11, "3V3", 0.5)
    traces += seg(15.1, 30.16, 15.1, 28, "3V3", 0.5)
    traces += seg(15.1, 28, 25, 28, "3V3", 0.5)
    traces += seg(25, 28, 25, 25, "3V3", 0.5)
    # 3V3 to GPS + MS5611
    traces += seg(5, 20, 5, 29.19, "3V3", 0.5)
    traces += seg(5, 29.19, 6, 29.19, "3V3", 0.5)
    traces += seg(44, 29.19, 44, 33, "3V3", 0.5)

    # VCAP: solar → BAT54 → LDO → supercap
    traces += seg(3, 35.73, 3, 33, "SOLAR_IN", 0.5)
    traces += seg(3, 33, 2.5, 18, "SOLAR_IN", 0.5)
    traces += seg(2.5, 18, 4, 18, "SOLAR_IN", 0.5)  # wait, BAT54 at (4,18)
    traces += seg(5.5, 18, 8, 18, "VCAP", 0.5)  # BAT54 cathode → VCAP bus
    traces += seg(8, 18, 8, 37, "VCAP", 0.5)  # to supercap
    traces += seg(5.95, 22, 5.95, 20, "VCAP", 0.5)  # LDO input

    # === SPI BUS (RP2040 → LR2021) ===
    # SCK: pin3 (38,6.11) → LR2021 pin5 (15.095,25)
    traces += seg(38, 6.11, 36, 6.11, "SPI0_SCK")
    traces += seg(36, 6.11, 36, 25, "SPI0_SCK")
    traces += seg(36, 25, 15.095, 25, "SPI0_SCK")
    # MOSI: pin4 (38,7.61) → LR2021 pin4 (15.095,26.29)
    traces += seg(38, 7.61, 36.5, 7.61, "SPI0_MOSI")
    traces += seg(36.5, 7.61, 36.5, 26.29, "SPI0_MOSI")
    traces += seg(36.5, 26.29, 15.095, 26.29, "SPI0_MOSI")
    # MISO: pin5 (38,9.11) → LR2021 pin3 (15.095,27.58)
    traces += seg(38, 9.11, 37, 9.11, "SPI0_MISO")
    traces += seg(37, 9.11, 37, 27.58, "SPI0_MISO")
    traces += seg(37, 27.58, 15.095, 27.58, "SPI0_MISO")
    # NSS: pin6 (38,10.61) → LR2021 pin6 (15.095,23.71)
    traces += seg(38, 10.61, 35.5, 10.61, "SPI0_NSS")
    traces += seg(35.5, 10.61, 35.5, 23.71, "SPI0_NSS")
    traces += seg(35.5, 23.71, 15.095, 23.71, "SPI0_NSS")

    # === CONTROL SIGNALS ===
    # BUSY: pin7 (38,12.11) → LR2021 pin7 (15.095,22.42) — route on B.Cu
    traces += via(33, 12.11, "LR2021_BUSY")
    traces += seg(38, 12.11, 33, 12.11, "LR2021_BUSY")
    traces += seg(33, 12.11, 33, 22.42, "LR2021_BUSY", 0.25, "B.Cu")
    traces += via(33, 22.42, "LR2021_BUSY")
    traces += seg(33, 22.42, 15.095, 22.42, "LR2021_BUSY")
    # IRQ (DIO9): pin8 (38,13.61) → LR2021 pin15 (34.905,26.29)
    traces += seg(38, 13.61, 34.905, 13.61, "LR2021_DIO9")
    traces += seg(34.905, 13.61, 34.905, 26.29, "LR2021_DIO9")
    # RST: pin9 (38,15.11) → LR2021 pin14 (34.905,25)
    traces += seg(38, 15.11, 34.905, 15.11, "LR2021_RST")
    traces += seg(34.905, 15.11, 34.905, 25, "LR2021_RST")

    # === UART ===
    # ESP_TX → RP2040: ESP pin3 (9.46,8.19) → RP pin12 (38,19.61)
    traces += seg(9.46, 8.19, 8, 8.19, "ESP_TX_RP2040_RX")
    traces += via(8, 8.19, "ESP_TX_RP2040_RX")
    traces += seg(8, 8.19, 8, 19.61, "ESP_TX_RP2040_RX", 0.25, "B.Cu")
    traces += via(8, 19.61, "ESP_TX_RP2040_RX")
    traces += seg(8, 19.61, 38, 19.61, "ESP_TX_RP2040_RX")
    # RP_TX → ESP: RP pin11 (38,18.11) → ESP pin4 (9.46,10.73)
    traces += seg(38, 18.11, 33, 18.11, "RP2040_TX_ESP_RX")
    traces += via(33, 18.11, "RP2040_TX_ESP_RX")
    traces += seg(33, 18.11, 33, 10.73, "RP2040_TX_ESP_RX", 0.25, "B.Cu")
    traces += seg(33, 10.73, 9.46, 10.73, "RP2040_TX_ESP_RX", 0.25, "B.Cu")
    traces += via(9.46, 10.73, "RP2040_TX_ESP_RX")
    # GPS_TX → ESP: GPS pin3 (6,34.27) → ESP pin5 (9.46,13.27)
    traces += seg(6, 34.27, 4, 34.27, "GPS_TX_ESP_RX")
    traces += via(4, 34.27, "GPS_TX_ESP_RX")
    traces += seg(4, 34.27, 4, 13.27, "GPS_TX_ESP_RX", 0.25, "B.Cu")
    traces += via(4, 13.27, "GPS_TX_ESP_RX")
    traces += seg(4, 13.27, 9.46, 13.27, "GPS_TX_ESP_RX")

    # === I2C (ESP32 → MS5611) ===
    # SDA: ESP pin7 (9.46,18.35) → MS5611 pin3 (44,33)
    traces += seg(9.46, 18.35, 7, 18.35, "I2C_SDA")
    traces += via(7, 18.35, "I2C_SDA")
    traces += seg(7, 18.35, 7, 33, "I2C_SDA", 0.25, "B.Cu")
    traces += seg(7, 33, 44, 33, "I2C_SDA", 0.25, "B.Cu")
    traces += via(44, 33, "I2C_SDA")
    # SCL: ESP pin8 (9.46,20.89) → MS5611 pin4 (44,35.54)
    traces += seg(9.46, 20.89, 6, 20.89, "I2C_SCL")
    traces += via(6, 20.89, "I2C_SCL")
    traces += seg(6, 20.89, 6, 35.54, "I2C_SCL", 0.25, "B.Cu")
    traces += seg(6, 35.54, 44, 35.54, "I2C_SCL", 0.25, "B.Cu")
    traces += via(44, 35.54, "I2C_SCL")

    # === STATUS LED ===
    # ESP pin9 (14.54,20.89) → R5 (18.5,4) → LED (16.8,4)
    traces += seg(14.54, 20.89, 14.54, 4, "STATUS_LED")
    traces += seg(14.54, 4, 18, 4, "STATUS_LED")
    traces += seg(19, 4, 16.8, 4, "LED_ANODE")

    # === VOLTAGE DIVIDER ===
    # ESP pin6 (9.46,15.81) → R3/R4 junction (3.5,15)
    traces += seg(9.46, 15.81, 3.5, 15.81, "VDIV_MID")
    traces += seg(3.5, 15.81, 3.5, 15, "VDIV_MID")
    # VCAP to R3
    traces += seg(2.5, 15, 2.5, 16, "VCAP", 0.25)
    traces += seg(2.5, 16, 8, 16, "VCAP", 0.25)

    # === RF ANTENNA ===
    # RF_SUB_868: LR2021 pin9 (15.095,19.84) → antenna (48,20)
    traces += seg(15.095, 19.84, 15.095, 18, "RF_SUB_868", 0.8)
    traces += seg(15.095, 18, 48, 18, "RF_SUB_868", 0.8)
    traces += seg(48, 18, 48, 20, "RF_SUB_868", 0.8)
    # RF_2G4_2400: LR2021 pin10 (34.905,19.84) → antenna (48,25)
    traces += seg(34.905, 19.84, 34.905, 17, "RF_2G4_2400", 0.8)
    traces += seg(34.905, 17, 47, 17, "RF_2G4_2400", 0.8)
    traces += seg(47, 17, 47, 25, "RF_2G4_2400", 0.8)
    traces += seg(47, 25, 48, 25, "RF_2G4_2400", 0.8)

    # === GROUND STITCHING VIAS ===
    for gx, gy in [(10, 5), (35, 5), (20, 30), (40, 35), (5, 35), (15, 20), (30, 15)]:
        traces += via(gx, gy, "GND")

    # === LOCAL DECOUPLING + COMPONENT STUBS ===
    # 3V3 decoupling caps near LR2021 (C3 at 14.6,30.2 and C4 at 14.45,32.0)
    traces += seg(14.6, 30.16, 15.1, 30.16, "3V3", 0.25)
    traces += seg(14.45, 32.0, 14.6, 32.0, "3V3", 0.25)
    traces += seg(14.6, 32.0, 14.6, 30.16, "3V3", 0.25)
    # C3/C4 GND pads → GND track to nearest via
    traces += seg(15.6, 30.16, 15.75, 30.16, "GND", 0.25)
    traces += seg(15.75, 30.16, 15.75, 32.0, "GND", 0.25)
    traces += seg(15.75, 32.0, 15.75, 32.0, "GND", 0.25)
    traces += via(16.5, 31, "GND")
    traces += seg(15.75, 30.16, 16.5, 31, "GND", 0.25)
    # R1/C6 pullup 3V3 (at 41.5,30 and 43.5,30)
    traces += seg(41.5, 30, 43.5, 30, "3V3", 0.25)
    traces += seg(41.5, 30, 38, 20, "3V3", 0.25)
    traces += seg(43.5, 30, 44, 29.19, "3V3", 0.25)
    traces += seg(44, 29.19, 44, 34.27, "3V3", 0.25)  # MS5611 pin1
    # R2 3V3 pullup (42.5,33)
    traces += seg(42.5, 33, 44, 33, "3V3", 0.25)
    # TP3 test point (33,38)
    traces += seg(33, 38, 33, 35, "3V3", 0.25)
    traces += via(33, 35, "3V3")
    traces += seg(33, 35, 38, 35, "3V3", 0.25, "B.Cu")
    traces += via(38, 35, "3V3")
    # U5 LDO pin5 (5.95,22.95) to 3V3
    traces += seg(5.95, 22.95, 5.0, 22.95, "3V3", 0.25)
    traces += seg(5.0, 22.95, 5.0, 29.19, "3V3", 0.5)
    traces += seg(5.0, 29.19, 5.97, 29.19, "3V3", 0.5)  # GPS pin1

    # U5 LDO GND pins (5.95,21.05) and C1 GND (6.65,24)
    traces += seg(5.95, 21.05, 5.0, 21.05, "GND", 0.25)
    traces += via(5.0, 21.05, "GND")
    traces += seg(6.65, 24, 6.0, 24, "GND", 0.25)
    traces += via(6.0, 24, "GND")
    # BAT54 GND (5.5,15)
    traces += seg(5.5, 15, 5.5, 14, "GND", 0.25)
    traces += via(5.5, 14, "GND")
    # C2 VCAP (4.05,21.05) → U5 VCAP
    traces += seg(4.05, 21.05, 4.05, 22, "VCAP", 0.25)
    traces += seg(4.05, 22, 5.95, 22, "VCAP", 0.25)
    # U5 VCAP pin3 (5.95,22.0) → 3V3 out
    traces += seg(5.95, 22, 5.95, 22.95, "VCAP", 0.25)
    # BAT54 cathode VCAP (5.5,18) → VCAP bus
    traces += seg(5.5, 18, 5.95, 18, "VCAP", 0.25)
    traces += seg(5.95, 18, 5.95, 22, "VCAP", 0.25)
    # VCAP to supercap (8,37)
    traces += seg(8, 18, 8, 37, "VCAP", 0.5)
    traces += seg(8, 37, 6.25, 37, "VCAP", 0.5)  # SC pin1
    # VCAP to R3 (2.5,15)
    traces += seg(2.5, 16, 2.5, 15, "VCAP", 0.25)
    traces += seg(2.5, 15, 4.5, 15, "VCAP", 0.25)
    # R3 VDIV_MID (4.5,15) → R4 (5.5,15)
    traces += seg(4.5, 15, 5.0, 15.81, "VDIV_MID", 0.25)
    traces += seg(5.0, 15.81, 9.46, 15.81, "VDIV_MID", 0.25)
    # R4 GND
    traces += seg(5.5, 15, 5.5, 14, "GND", 0.25)

    # GND pads near LR2021 → via to B.Cu
    for gx, gy in [(15.095, 21.13), (15.095, 28.87), (34.905, 21.13), (34.905, 22.42), (34.905, 30.16)]:
        traces += via(gx + 1.0, gy, "GND")
        traces += seg(gx, gy, gx + 1.0, gy, "GND", 0.25)
    # ESP32 GND (9.96,3.11) → already has via at (10,5)
    traces += seg(9.96, 3.11, 10, 3.11, "GND", 0.25)
    traces += seg(10, 3.11, 10, 5, "GND", 0.25)
    # RP2040 GND (38.5,3.0)
    traces += seg(38.5, 3.0, 38.5, 5, "GND", 0.25)
    # GPS GND (6.5,30) → U3 pin2
    traces += seg(6.5, 30, 6.0, 31.73, "GND", 0.25)
    traces += via(6.0, 31.73, "GND")
    # C5 GND (6.5,30)
    traces += seg(6.5, 30, 7, 30, "GND", 0.25)
    traces += via(7, 30, "GND")
    # C6 GND (44.5,30)
    traces += seg(44.5, 30, 45, 30, "GND", 0.25)
    traces += via(45, 30, "GND")
    # LED cathode GND (15.2,4)
    traces += seg(15.2, 4, 15.2, 5, "GND", 0.25)
    # TP GND (37,38)
    traces += seg(37, 38, 37, 37, "GND", 0.25)
    traces += via(37, 37, "GND")
    # Solar GND (3,38.27) and supercap GND (9.75,37)
    traces += seg(3, 38.27, 3, 37, "GND", 0.5)
    traces += via(3, 37, "GND")
    traces += seg(9.75, 37, 10, 37, "GND", 0.5)
    traces += via(10, 37, "GND")
    # ESP32 extra GND (9.46,5.65)
    traces += seg(9.46, 5.65, 10, 5.65, "GND", 0.25)
    traces += via(10, 5.65, "GND")

    # Test points to SPI bus
    traces += via(36, 36, "SPI0_SCK")
    traces += seg(25, 38, 25, 36, "SPI0_SCK", 0.25)
    traces += seg(25, 36, 36, 36, "SPI0_SCK", 0.25)
    traces += seg(36, 36, 36, 25, "SPI0_SCK", 0.25, "B.Cu")
    traces += via(29, 37, "SPI0_MOSI")
    traces += seg(29, 38, 29, 37, "SPI0_MOSI", 0.25)
    traces += seg(29, 37, 36.5, 37, "SPI0_MOSI", 0.25, "B.Cu")
    traces += seg(36.5, 37, 36.5, 26.29, "SPI0_MOSI", 0.25, "B.Cu")

    # MS5611 SDA/SCL pad fixes — pin3 SDA at (44,34.27), pin4 SCL at (44,36.81)
    traces += seg(44, 33, 44, 34.27, "I2C_SDA", 0.25)
    traces += seg(44, 35.54, 44, 36.81, "I2C_SCL", 0.25)

    out += traces

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
    print(f"  Traces: {seg_id-1}")
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
        y = -8.89 + i * 1.5
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

    # === SIGNAL ROUTING ===
    seg_id2 = 1
    def seg2(x1, y1, x2, y2, net_name, width=0.25, layer="F.Cu"):
        nonlocal seg_id2
        s = f'  (segment (start {x1:.2f} {y1:.2f}) (end {x2:.2f} {y2:.2f}) (width {width}) (layer "{layer}") (net {nid[net_name]} "{net_name}") (uuid "seg-{seg_id2:03d}"))\n'
        seg_id2 += 1
        return s
    def via2(x, y, net_name):
        nonlocal seg_id2
        s = f'  (via (at {x:.2f} {y:.2f}) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net {nid[net_name]} "{net_name}") (uuid "via-{seg_id2:03d}"))\n'
        seg_id2 += 1
        return s

    t = "\n"
    # F33 pad absolute positions (center 37.5,28):
    # Left pins at x=37.5-19.5=18, pitch 2.0mm, pin1 y=28+9=37
    f33_left_x = 18.0
    # Right pins at x=37.5+19.5=57, pin10 y=28+9=37
    f33_right_x = 57.0

    # F33 VCC (pin1, left, y=37) → VCAP bus (FAT: 0.8mm for 1.2A PA current)
    t += seg2(f33_left_x, 37, 16.4, 37, "VCAP", 0.8)
    t += seg2(16.4, 37, 16.4, 19, "VCAP", 0.8)
    t += seg2(16.4, 19, 17.15, 19, "VCAP", 0.8)  # to C8/C9/C10 bulk caps
    # F33 GND pins (left pins 2,3,4,6,7,8 at y=35,33,31,27,25,23) → vias
    for gy in [35, 33, 31, 27, 25, 23]:
        t += via2(f33_left_x + 1, gy, "GND")
        t += seg2(f33_left_x, gy, f33_left_x + 1, gy, "GND", 0.5)
    # F33 GND pins right (11 at y=31)
    t += via2(f33_right_x - 1, 31, "GND")
    t += seg2(f33_right_x, 31, f33_right_x - 1, 31, "GND", 0.5)

    # CE: F33 pin5 (left, y=29) → RP2040 pin11 (63, 15+(-8.89+10*1.5)=15+6.11=21.11)
    t += seg2(f33_left_x, 29, 14, 29, "LR2021_CE")
    t += via2(14, 29, "LR2021_CE")
    t += seg2(14, 29, 14, 21.11, "LR2021_CE", 0.25, "B.Cu")
    t += via2(14, 21.11, "LR2021_CE")
    t += seg2(14, 21.11, 63, 21.11, "LR2021_CE")

    # RF_SUB_868: F33 pin9 (left, y=21) → SMA J1 (4, 28)
    t += seg2(f33_left_x, 21, f33_left_x, 17, "RF_SUB_868", 0.8)
    t += seg2(f33_left_x, 17, 4, 17, "RF_SUB_868", 0.8)
    t += seg2(4, 17, 4, 28, "RF_SUB_868", 0.8)
    # RF_2G4: F33 pin10 (right, y=37) → SMA J2 (73, 28)
    t += seg2(f33_right_x, 37, f33_right_x, 33, "RF_2G4_2400", 0.8)
    t += seg2(f33_right_x, 33, 71, 33, "RF_2G4_2400", 0.8)
    t += seg2(71, 33, 71, 28, "RF_2G4_2400", 0.8)
    t += seg2(71, 28, 73, 28, "RF_2G4_2400", 0.8)

    # SPI: F33 right pins → RP2040
    # SCK: F33 pin12 (right, y=33) → RP pin3 (63, 15+(-8.89+2*1.5)=9.61)
    t += seg2(f33_right_x, 33, 60, 33, "SPI0_SCK")
    t += via2(60, 33, "SPI0_SCK")
    t += seg2(60, 33, 60, 9.61, "SPI0_SCK", 0.25, "B.Cu")
    t += via2(60, 9.61, "SPI0_SCK")
    t += seg2(60, 9.61, 63, 9.61, "SPI0_SCK")
    # NSS: F33 pin13 (right, y=31) → RP pin6 (63, 10.61... wait recompute)
    # RP2040: pin1 y=-8.89, pin6 y=-8.89+5*1.5=-1.39, abs=15-1.39=13.61
    t += seg2(f33_right_x, 31, 59, 31, "SPI0_NSS")
    t += via2(59, 31, "SPI0_NSS")
    t += seg2(59, 31, 59, 13.61, "SPI0_NSS", 0.25, "B.Cu")
    t += via2(59, 13.61, "SPI0_NSS")
    t += seg2(59, 13.61, 63, 13.61, "SPI0_NSS")
    # BUSY: F33 pin14 (right, y=29) → RP pin7 (63, 15+0.11=15.11)
    t += seg2(f33_right_x, 29, 58, 29, "LR2021_BUSY")
    t += via2(58, 29, "LR2021_BUSY")
    t += seg2(58, 29, 58, 15.11, "LR2021_BUSY", 0.25, "B.Cu")
    t += via2(58, 15.11, "LR2021_BUSY")
    t += seg2(58, 15.11, 63, 15.11, "LR2021_BUSY")
    # MOSI: F33 pin15 (right, y=27) → RP pin4 (63, 15-4.39=10.61... wait)
    # RP pin4: y=-8.89+3*1.5=-4.39, abs=15-4.39=10.61
    t += seg2(f33_right_x, 27, 57, 27, "SPI0_MOSI")
    t += via2(57, 27, "SPI0_MOSI")
    t += seg2(57, 27, 57, 10.61, "SPI0_MOSI", 0.25, "B.Cu")
    t += via2(57, 10.61, "SPI0_MOSI")
    t += seg2(57, 10.61, 63, 10.61, "SPI0_MOSI")
    # MISO: F33 pin16 (right, y=25) → RP pin5 (63, 15-2.89=12.11)
    t += seg2(f33_right_x, 25, 56, 25, "SPI0_MISO")
    t += via2(56, 25, "SPI0_MISO")
    t += seg2(56, 25, 56, 12.11, "SPI0_MISO", 0.25, "B.Cu")
    t += via2(56, 12.11, "SPI0_MISO")
    t += seg2(56, 12.11, 63, 12.11, "SPI0_MISO")
    # RST: F33 pin17 (right, y=23) → RP pin9 (63, 15+3.11=18.11... wait)
    # RP pin9: y=-8.89+8*1.5=3.11, abs=15+3.11=18.11
    t += seg2(f33_right_x, 23, 55, 23, "LR2021_RST")
    t += via2(55, 23, "LR2021_RST")
    t += seg2(55, 23, 55, 18.11, "LR2021_RST", 0.25, "B.Cu")
    t += via2(55, 18.11, "LR2021_RST")
    t += seg2(55, 18.11, 63, 18.11, "LR2021_RST")
    # IRQ: F33 pin18 (right, y=21) → RP pin8 (63, 15+1.61=16.61)
    t += seg2(f33_right_x, 21, 54, 21, "LR2021_IRQ")
    t += via2(54, 21, "LR2021_IRQ")
    t += seg2(54, 21, 54, 16.61, "LR2021_IRQ", 0.25, "B.Cu")
    t += via2(54, 16.61, "LR2021_IRQ")
    t += seg2(54, 16.61, 63, 16.61, "LR2021_IRQ")

    # UART: ESP32 ↔ RP2040
    # ESP_TX → RP_RX: ESP pin3 (9.46,11.19) → RP pin13 (63, 15+7.61=22.61... wait)
    # RP pin13: y=-8.89+12*1.5=9.11, abs=15+9.11=24.11
    t += seg2(9.46, 11.19, 8, 11.19, "ESP_TX_RP2040_RX")
    t += via2(8, 11.19, "ESP_TX_RP2040_RX")
    t += seg2(8, 11.19, 8, 24.11, "ESP_TX_RP2040_RX", 0.25, "B.Cu")
    t += via2(8, 24.11, "ESP_TX_RP2040_RX")
    t += seg2(8, 24.11, 63, 24.11, "ESP_TX_RP2040_RX")
    # RP_TX → ESP: RP pin12 (63, 15+7.61=22.61... wait)
    # RP pin12: y=-8.89+11*1.5=7.61, abs=15+7.61=22.61
    t += seg2(63, 22.61, 52, 22.61, "RP2040_TX_ESP_RX")
    t += via2(52, 22.61, "RP2040_TX_ESP_RX")
    t += seg2(52, 22.61, 52, 13.73, "RP2040_TX_ESP_RX", 0.25, "B.Cu")
    t += seg2(52, 13.73, 9.46, 13.73, "RP2040_TX_ESP_RX", 0.25, "B.Cu")
    t += via2(9.46, 13.73, "RP2040_TX_ESP_RX")
    # GPS_TX → ESP: GPS pin3 (6, 45+1.27=46.27... wait GPS center 45, pin3 at -3.81+2*2.54=1.27, abs=46.27)
    # Hmm, GPS center (6,45), pin3 y offset=1.27, so abs=(6,46.27)
    t += seg2(6, 46.27, 4, 46.27, "GPS_TX_ESP_RX")
    t += via2(4, 46.27, "GPS_TX_ESP_RX")
    t += seg2(4, 46.27, 4, 16.27, "GPS_TX_ESP_RX", 0.25, "B.Cu")
    t += via2(4, 16.27, "GPS_TX_ESP_RX")
    t += seg2(4, 16.27, 9.46, 16.27, "GPS_TX_ESP_RX")

    # I2C: ESP32 → MS5611
    # SDA: ESP pin7 (9.46, 15+6.35=21.35) → MS pin3 (68, 45+1.27=46.27)
    t += seg2(9.46, 21.35, 7, 21.35, "I2C_SDA")
    t += via2(7, 21.35, "I2C_SDA")
    t += seg2(7, 21.35, 7, 46.27, "I2C_SDA", 0.25, "B.Cu")
    t += seg2(7, 46.27, 68, 46.27, "I2C_SDA", 0.25, "B.Cu")
    t += via2(68, 46.27, "I2C_SDA")
    # SCL: ESP pin8 (9.46, 15+8.89=23.89) → MS pin4 (68, 45+3.81=48.81)
    t += seg2(9.46, 23.89, 6, 23.89, "I2C_SCL")
    t += via2(6, 23.89, "I2C_SCL")
    t += seg2(6, 23.89, 6, 48.81, "I2C_SCL", 0.25, "B.Cu")
    t += seg2(6, 48.81, 68, 48.81, "I2C_SCL", 0.25, "B.Cu")
    t += via2(68, 48.81, "I2C_SCL")

    # POWER: 3V3 to ESP32, RP2040, GPS, MS5611
    t += seg2(8.95, 40.95, 8.95, 38, "3V3", 0.5)  # LDO out
    t += seg2(8.95, 38, 9.46, 38, "3V3", 0.5)
    t += seg2(9.46, 38, 9.46, 21.35, "3V3", 0.5)  # up to ESP32 area
    t += seg2(9.46, 21.35, 9.46, 6.11, "3V3", 0.5)  # ESP32 pin1
    t += seg2(9.46, 38, 63, 38, "3V3", 0.5)  # horizontal to RP2040
    t += seg2(63, 38, 63, 6.11, "3V3", 0.5)  # up to RP pin1
    t += seg2(9.46, 38, 6, 38, "3V3", 0.5)  # to GPS area
    t += seg2(6, 38, 6, 41.19, "3V3", 0.5)  # GPS pin1
    t += seg2(63, 38, 68, 38, "3V3", 0.5)  # to MS5611
    t += seg2(68, 38, 68, 41.19, "3V3", 0.5)  # MS pin1

    # VCAP power: solar → BAT54 → LDO → supercap → F33
    t += seg2(4, 46.73, 4, 44, "SOLAR_IN", 0.8)  # solar pin1
    t += seg2(4, 44, 3.5, 40, "SOLAR_IN", 0.8)  # to BAT54 anode
    t += seg2(5, 40, 6.5, 40, "VCAP", 0.8)  # BAT54 cathode → VCAP
    t += seg2(6.5, 40, 6.5, 48, "VCAP", 0.8)  # to supercap
    t += seg2(6.5, 48, 8.25, 48, "VCAP", 0.8)  # SC pin1

    # STATUS LED
    t += seg2(14.54, 23.89, 14.54, 5, "STATUS_LED")
    t += seg2(14.54, 5, 18, 5, "STATUS_LED")

    # VDIV
    t += seg2(9.46, 18.81, 3, 18.81, "VDIV_MID", 0.25)

    # GND stitching vias
    for gx, gy in [(15, 10), (60, 10), (30, 50), (70, 50), (5, 50), (40, 45)]:
        t += via2(gx, gy, "GND")

    out += t

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
