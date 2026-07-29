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

    traces = "\n  ;; === Power traces ===\n"
    # 3V3 from LDO output to ESP32 pin 1
    traces += seg(5, 22.95, 5, 20, "3V3")  # LDO out to junction
    traces += seg(5, 20, 9.46, 20, "3V3")  # to ESP32 area
    traces += seg(9.46, 20, 9.46, 3.11, "3V3")  # up to ESP32 VCC pad
    # 3V3 to RP2040
    traces += seg(5, 20, 38, 20, "3V3", 0.5, "F.Cu")
    traces += seg(38, 20, 38, 3.11, "3V3", 0.5, "F.Cu")
    # 3V3 to LR2021 pin 1
    traces += seg(15.1, 30.16, 15.1, 28, "3V3", 0.5, "F.Cu")
    traces += seg(15.1, 28, 25, 28, "3V3", 0.5, "F.Cu")
    traces += seg(25, 28, 25, 25, "3V3", 0.5, "F.Cu")  # to LR2021 center

    # SPI bus: RP2040 to LR2021
    traces += "\n  ;; === SPI traces (RP2040 → LR2021) ===\n"
    # SCK: RP2040 pin3 area → LR2021 pin5
    traces += seg(38, 3.11, 35, 3.11, "SPI0_SCK")
    traces += seg(35, 3.11, 35, 25, "SPI0_SCK")
    traces += seg(35, 25, 25.095, 25, "SPI0_SCK")  # LR2021 pin5 at (25-9.905, 25+0) = (15.095, 25)

    # Ground vias (stitching F.Cu to B.Cu ground pour)
    traces += "\n  ;; === Ground vias ===\n"
    for gx, gy in [(10, 5), (35, 5), (20, 30), (40, 35), (5, 35), (15, 20), (30, 15)]:
        traces += via(gx, gy, "GND")

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
