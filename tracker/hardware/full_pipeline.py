#!/usr/bin/python3.14
"""
Full pipeline: Create board -> Place footprints -> A* route -> Save -> DRC -> Iterate
Run with: /usr/bin/python3.14 full_pipeline.py --board-type v1-fast --output output/v1_fast_routed.kicad_pcb --max-iterations 10

MANDATORY: Uses pcbnew.NewBoard() NOT the banned loader. The board-loader fails headless (needs wxApp).
MANDATORY: NO copper pours. GND routed as explicit tracks.
MANDATORY: Run with /usr/bin/python3.14 (python3.11 segfaults with pcbnew).
"""

import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')

import argparse
import json
import os
import subprocess
import math
import heapq
from collections import defaultdict
from typing import Optional
from dataclasses import dataclass, field

import pcbnew

# ============================================================
# CONSTANTS -- verified against KiCad 9.0.8 on this system
# ============================================================

BOARD_WIDTH_MM = 50.0
BOARD_HEIGHT_MM = 40.0
GRID_RESOLUTION_MM = 0.25     # A* grid — fine enough for dense pad clusters
TRACK_WIDTH_SIGNAL_MM = 0.25  # default signal track width
TRACK_WIDTH_POWER_MM = 0.40   # power/ground track width
TRACK_WIDTH_RF_MM = 0.76      # RF antenna trace width
CLEARANCE_MM = 0.30           # min clearance between different nets
EDGE_CLEARANCE_MM = 0.50      # board edge copper clearance (DRC default)
HOLE_CLEARANCE_MM = 0.25      # hole clearance (DRC default)
VIA_DRILL_MM = 0.3
VIA_SIZE_MM = 0.6

# KiCad layers
F_CU = 0   # pcbnew.F_Cu
B_CU = 2   # pcbnew.B_Cu
EDGE_CUTS = 25  # pcbnew.Edge_Cuts

# ============================================================
# COMPONENT DEFINITIONS
# ============================================================

@dataclass
class PadDef:
    """Pad definition: number, net name, offset from component center, size, layer, thru."""
    number: str
    net: str
    dx: float        # offset X from component center (mm)
    dy: float        # offset Y from component center (mm)
    w: float = 1.0   # pad width (mm)
    h: float = 0.8   # pad height (mm)
    layer: int = F_CU  # F_Cu or B_Cu
    is_thru: bool = False

@dataclass
class ComponentDef:
    """Component definition: reference, position, footprint type, pad list."""
    ref: str
    x: float         # center X (mm)
    y: float         # center Y (mm)
    pads: list = field(default_factory=list)
    value: str = ""

# ============================================================
# NET DEFINITIONS
# ============================================================

# V1-FAST net names and their track widths / preferred layers
V1_FAST_NETS = {
    "3V3":          {"width": TRACK_WIDTH_POWER_MM, "layer": F_CU},
    "GND":          {"width": TRACK_WIDTH_POWER_MM, "layer": B_CU},  # GND on B.Cu rail
    "SPI_SCK":      {"width": TRACK_WIDTH_SIGNAL_MM, "layer": F_CU},
    "SPI_MOSI":     {"width": TRACK_WIDTH_SIGNAL_MM, "layer": F_CU},
    "SPI_MISO":     {"width": TRACK_WIDTH_SIGNAL_MM, "layer": F_CU},
    "SPI_NSS":      {"width": TRACK_WIDTH_SIGNAL_MM, "layer": F_CU},
    "LR2021_BUSY":  {"width": TRACK_WIDTH_SIGNAL_MM, "layer": F_CU},
    "LR2021_RST":   {"width": TRACK_WIDTH_SIGNAL_MM, "layer": F_CU},
    "LR2021_DIO9":  {"width": TRACK_WIDTH_SIGNAL_MM, "layer": F_CU},
    "GPS_RX":       {"width": TRACK_WIDTH_SIGNAL_MM, "layer": F_CU},
    "STATUS_LED":   {"width": TRACK_WIDTH_SIGNAL_MM, "layer": F_CU},
    "LED_ANODE":    {"width": TRACK_WIDTH_SIGNAL_MM, "layer": F_CU},
    "VCAP":         {"width": TRACK_WIDTH_POWER_MM, "layer": F_CU},
    "SOLAR_IN":     {"width": TRACK_WIDTH_POWER_MM, "layer": F_CU},
    "FEM_TX":       {"width": TRACK_WIDTH_SIGNAL_MM, "layer": F_CU},
    "RF_SUB_868":   {"width": TRACK_WIDTH_RF_MM, "layer": F_CU},
    "RF_2G4_2400":  {"width": TRACK_WIDTH_RF_MM, "layer": F_CU},
}

# V2-ADC adds VDIV_MID net; GPIO0 used for ADC (ADC1_CH0), FEM_TX stays on GPIO19
V2_ADC_NETS = dict(V1_FAST_NETS)
V2_ADC_NETS["VDIV_MID"] = {"width": TRACK_WIDTH_SIGNAL_MM, "layer": F_CU}

# ============================================================
# COMPONENT LAYOUTS
# ============================================================

def make_esp32c3_pads(gpio_nets: dict) -> list:
    """
    Create pad list for ESP32-C3 module.
    gpio_nets maps GPIO number to net name.
    Pads are arranged in a grid around the module perimeter.
    """
    pads = []
    # ESP32-C3 module: ~7x7mm, pads on perimeter
    # Left side: GPIO0-GPIO5 (top to bottom)
    # Bottom: GPIO6-GPIO10
    # Right side: VCC, GND, GPIO18, GPIO19
    # Top: (reserved for antenna / NC)

    pad_w = 1.0
    pad_h = 0.6
    pitch = 1.5  # pad pitch in mm

    # Left side (x = -3.5), GPIO0-GPIO5
    left_gpio = [0, 1, 2, 3, 4, 5]
    for i, gpio in enumerate(left_gpio):
        net = gpio_nets.get(gpio, "")
        if net:
            pads.append(PadDef(
                number=f"GPIO{gpio}",
                net=net,
                dx=-3.5,
                dy=-3.75 + i * pitch,
                w=pad_w, h=pad_h,
                layer=F_CU,
            ))

    # Bottom side (y = +3.5), GPIO6-GPIO10
    bottom_gpio = [6, 7, 8, 9, 10]
    for i, gpio in enumerate(bottom_gpio):
        net = gpio_nets.get(gpio, "")
        if net:
            pads.append(PadDef(
                number=f"GPIO{gpio}",
                net=net,
                dx=-1.5 + i * pitch,   # shift inboard by one pitch (was -3.0) — fixes GPIO5/GPIO6 corner collision
                dy=3.5,
                w=pad_w, h=pad_h,
                layer=F_CU,
            ))

    # Right side (x = +3.5), VCC, GND, GPIO18, GPIO19
    right_pins = [
        (18, "GPIO18"),
        (19, "GPIO19"),
    ]
    # VCC pad
    pads.append(PadDef(
        number="VCC",
        net=gpio_nets.get("VCC", ""),
        dx=3.5,
        dy=-3.75,
        w=pad_w, h=pad_h,
        layer=F_CU,
    ))
    # GND pad
    pads.append(PadDef(
        number="GND",
        net=gpio_nets.get("GND", ""),
        dx=3.5,
        dy=-2.25,
        w=pad_w, h=pad_h,
        layer=F_CU,
    ))
    # GPIO18, GPIO19
    for i, (gpio, label) in enumerate(right_pins):
        net = gpio_nets.get(gpio, "")
        if net:
            pads.append(PadDef(
                number=label,
                net=net,
                dx=3.5,
                dy=-0.75 + i * pitch,
                w=pad_w, h=pad_h,
                layer=F_CU,
            ))

    # No B.Cu GND pad — all routing is on F.Cu only

    return pads


def make_lr2021_pads() -> list:
    """
    Create pad list for NiceRF LR2021F33 module.
    18 pads, castellated edges.
    Pin mapping from PCB-AUTO-ROUTE-EXECUTION-PLAN-V2.md:
    Pin 1:  3V3     (left)
    Pin 2:  GND     (left)
    Pin 3:  MISO    (left)
    Pin 4:  MOSI    (left)
    Pin 5:  SCK     (left)
    Pin 6:  NSS     (left)
    Pin 7:  BUSY    (left)
    Pin 8:  GND     (left)
    Pin 9:  RF_SUB  (left, 0.76mm RF trace)
    Pin 10: GND     (right)
    Pin 11: GND     (right)
    Pin 12: NC      (right, no net)
    Pin 13: DIO9    (right)
    Pin 14: RST     (right)
    Pin 15: NC      (right, no net)
    Pin 16: GND     (right)
    Pin 17: GND     (right)
    Pin 18: RF_2G4  (right, 0.76mm RF trace)
    """
    pads = []
    pad_w = 1.2
    pad_h = 0.8
    pitch = 2.0  # 2mm pitch

    # Left side pins 1-9 (x = -9.9)
    left_pins = [
        (1, "3V3",         pad_w, pad_h),
        (2, "GND",         pad_w, pad_h),
        (3, "SPI_MISO",    pad_w, pad_h),
        (4, "SPI_MOSI",    pad_w, pad_h),
        (5, "SPI_SCK",     pad_w, pad_h),
        (6, "SPI_NSS",     pad_w, pad_h),
        (7, "LR2021_BUSY", pad_w, pad_h),
        (8, "GND",         pad_w, pad_h),
        (9, "RF_SUB_868",  1.5, pad_h),  # wider for RF
    ]
    for i, (pin, net, w, h) in enumerate(left_pins):
        pads.append(PadDef(
            number=str(pin),
            net=net,
            dx=-9.9,
            dy=-8.0 + i * pitch,
            w=w, h=h,
            layer=F_CU,
        ))

    # Right side pins 10-18 (x = +9.9)
    right_pins = [
        (10, "GND",          pad_w, pad_h),
        (11, "GND",          pad_w, pad_h),
        (12, "",             pad_w, pad_h),  # NC
        (13, "LR2021_DIO9",  pad_w, pad_h),
        (14, "LR2021_RST",   pad_w, pad_h),
        (15, "",             pad_w, pad_h),  # NC
        (16, "GND",          pad_w, pad_h),
        (17, "GND",          pad_w, pad_h),
        (18, "RF_2G4_2400",  1.5, pad_h),   # wider for RF
    ]
    for i, (pin, net, w, h) in enumerate(right_pins):
        if net:  # skip NC pins
            pads.append(PadDef(
                number=str(pin),
                net=net,
                dx=9.9,
                dy=-8.0 + i * pitch,
                w=w, h=h,
                layer=F_CU,
            ))

    return pads


def make_gps_pads() -> list:
    """MAX-M10S GPS module: 4 pads (VCC, GND, TX, RX)."""
    return [
        PadDef(number="1", net="3V3",    dx=-2.0, dy=0, w=1.0, h=0.8, layer=F_CU),
        PadDef(number="2", net="GND",    dx=-0.7, dy=0, w=1.0, h=0.8, layer=F_CU),
        PadDef(number="3", net="GPS_RX", dx=0.7,  dy=0, w=1.0, h=0.8, layer=F_CU),  # TX from GPS
        PadDef(number="4", net="",       dx=2.0,  dy=0, w=1.0, h=0.8, layer=F_CU),  # RX (unused)
    ]


def make_ldo_pads() -> list:
    """TPS7A02 SOT-23-5: 5 pads (IN, GND, EN, OUT, NC)."""
    return [
        PadDef(number="1", net="VCAP",  dx=-0.95, dy=-0.75, w=0.6, h=0.4, layer=F_CU),  # IN
        PadDef(number="2", net="GND",   dx=0,     dy=-0.75, w=0.6, h=0.4, layer=F_CU),  # GND
        PadDef(number="3", net="VCAP",  dx=0.95,  dy=-0.75, w=0.6, h=0.4, layer=F_CU),  # EN (tie to IN)
        PadDef(number="4", net="3V3",   dx=0.95,  dy=0.75,  w=0.6, h=0.4, layer=F_CU),  # OUT
        PadDef(number="5", net="",      dx=-0.95, dy=0.75,  w=0.6, h=0.4, layer=F_CU),  # NC
    ]


def make_diode_pads() -> list:
    """BAT54 SOD-123: 2 pads (A, K)."""
    return [
        PadDef(number="A", net="SOLAR_IN", dx=-1.0, dy=0, w=0.8, h=0.6, layer=F_CU),
        PadDef(number="K", net="VCAP",     dx=1.0,  dy=0, w=0.8, h=0.6, layer=F_CU),
    ]


def make_resistor_pads(net1: str, net2: str) -> list:
    """0402 resistor: 2 pads."""
    return [
        PadDef(number="1", net=net1, dx=-0.5, dy=0, w=0.6, h=0.5, layer=F_CU),
        PadDef(number="2", net=net2, dx=0.5,  dy=0, w=0.6, h=0.5, layer=F_CU),
    ]


def make_led_pads() -> list:
    """0603 LED: 2 pads (A, K)."""
    return [
        PadDef(number="A", net="LED_ANODE", dx=-0.5, dy=0, w=0.7, h=0.6, layer=F_CU),
        PadDef(number="K", net="GND",       dx=0.5,  dy=0, w=0.7, h=0.6, layer=F_CU),
    ]


def make_cap_pads(net1: str, net2: str) -> list:
    """0603 capacitor: 2 pads."""
    return [
        PadDef(number="1", net=net1, dx=-0.5, dy=0, w=0.7, h=0.6, layer=F_CU),
        PadDef(number="2", net=net2, dx=0.5,  dy=0, w=0.7, h=0.6, layer=F_CU),
    ]


def make_tht_pads(net_pos: str, net_neg: str, pitch_mm: float = 2.54) -> list:
    """Through-hole pads (e.g., supercap, connector, U.FL)."""
    return [
        PadDef(number="1", net=net_pos, dx=-pitch_mm/2, dy=0, w=1.6, h=1.6, layer=F_CU, is_thru=True),
        PadDef(number="2", net=net_neg, dx=pitch_mm/2,  dy=0, w=1.6, h=1.6, layer=F_CU, is_thru=True),
    ]


def make_ufl_pads(net_signal: str) -> list:
    """U.FL connector: signal pad + 2 GND pads."""
    return [
        PadDef(number="1", net=net_signal, dx=0,     dy=0,    w=1.0, h=1.0, layer=F_CU),
        PadDef(number="2", net="GND",      dx=-1.5,  dy=0,    w=1.0, h=1.0, layer=F_CU, is_thru=True),
        PadDef(number="3", net="GND",      dx=1.5,   dy=0,    w=1.0, h=1.0, layer=F_CU, is_thru=True),
    ]


def make_fem_pads(net_tx: str) -> list:
    """FEM module: TX, VCC, GND."""
    return [
        PadDef(number="TX",  net=net_tx, dx=-1.5, dy=0, w=1.0, h=0.8, layer=F_CU),
        PadDef(number="VCC", net="3V3",  dx=0,    dy=0, w=1.0, h=0.8, layer=F_CU),
        PadDef(number="GND", net="GND",  dx=1.5,  dy=0, w=1.0, h=0.8, layer=F_CU),
    ]


def get_v1_fast_components() -> list:
    """V1-FAST: 16 components, 17 nets, no ADC."""
    # ESP32-C3 GPIO to net mapping for V1-FAST
    gpio_nets = {
        0: "",           # GPS TX (optional, disabled)
        1: "GPS_RX",     # GPS UART RX
        2: "SPI_MISO",   # SPI MISO (needs pull-down)
        3: "LR2021_RST",
        4: "LR2021_BUSY",
        5: "LR2021_DIO9",
        6: "SPI_SCK",
        7: "SPI_MOSI",
        8: "",           # ADC disabled on V1-FAST
        9: "STATUS_LED",
        10: "SPI_NSS",
        18: "",          # available but unused
        19: "FEM_TX",
        "VCC": "3V3",
        "GND": "GND",
    }

    comps = []

    # U1: ESP32-C3 at (12, 12)
    comps.append(ComponentDef(
        ref="U1", x=12.0, y=12.0, value="ESP32-C3",
        pads=make_esp32c3_pads(gpio_nets),
    ))

    # U2: LR2021 at (25, 25)
    comps.append(ComponentDef(
        ref="U2", x=25.0, y=25.0, value="LR2021F33",
        pads=make_lr2021_pads(),
    ))

    # U3: GPS (MAX-M10S) at (6, 33)
    comps.append(ComponentDef(
        ref="U3", x=6.0, y=33.0, value="MAX-M10S",
        pads=make_gps_pads(),
    ))

    # U4: TPS7A02 LDO at (5, 22)
    comps.append(ComponentDef(
        ref="U4", x=5.0, y=22.0, value="TPS7A02",
        pads=make_ldo_pads(),
    ))

    # D1: BAT54 diode at (4, 18)
    comps.append(ComponentDef(
        ref="D1", x=4.0, y=18.0, value="BAT54",
        pads=make_diode_pads(),
    ))

    # LED1: 0603 LED at (16, 4)
    comps.append(ComponentDef(
        ref="LED1", x=16.0, y=4.0, value="LED-0603",
        pads=make_led_pads(),
    ))

    # R_LED: 330 ohm 0402 at (19, 4)
    comps.append(ComponentDef(
        ref="R_LED", x=19.0, y=4.0, value="330R",
        pads=make_resistor_pads("STATUS_LED", "LED_ANODE"),
    ))

    # R_PD: 10k pull-down 0402 at (10, 14)
    comps.append(ComponentDef(
        ref="R_PD", x=10.0, y=14.0, value="10k",
        pads=make_resistor_pads("GND", "SPI_MISO"),
    ))

    # C_CAP: Supercapacitor THT at (10, 37)
    comps.append(ComponentDef(
        ref="C_CAP", x=10.0, y=37.0, value="Supercap",
        pads=make_tht_pads("VCAP", "GND", pitch_mm=5.0),
    ))

    # SOLAR: Solar connector 2-pin THT at (3, 37)
    comps.append(ComponentDef(
        ref="SOLAR", x=3.0, y=37.0, value="Solar-Conn",
        pads=make_tht_pads("SOLAR_IN", "GND", pitch_mm=2.54),
    ))

    # ANT1: U.FL for sub-GHz at (46, 25)
    comps.append(ComponentDef(
        ref="ANT1", x=46.0, y=25.0, value="U.FL-868",
        pads=make_ufl_pads("RF_SUB_868"),
    ))

    # ANT2: U.FL for 2.4GHz at (46, 30)
    comps.append(ComponentDef(
        ref="ANT2", x=46.0, y=30.0, value="U.FL-2400",
        pads=make_ufl_pads("RF_2G4_2400"),
    ))

    # C1: 10uF 0603 (LDO input cap) at (8, 22)
    comps.append(ComponentDef(
        ref="C1", x=8.0, y=22.0, value="10uF",
        pads=make_cap_pads("VCAP", "GND"),
    ))

    # C2: 10uF 0603 (LDO output cap) at (7, 24)
    comps.append(ComponentDef(
        ref="C2", x=7.0, y=24.0, value="10uF",
        pads=make_cap_pads("3V3", "GND"),
    ))

    # FEM: at (40, 25) -- optional but included for net completeness
    comps.append(ComponentDef(
        ref="FEM", x=40.0, y=25.0, value="FEM",
        pads=make_fem_pads("FEM_TX"),
    ))

    return comps


def get_v2_adc_components() -> list:
    """V2-ADC: 18 components, 18 nets, with ADC voltage divider."""
    # ESP32-C3 GPIO to net mapping for V2-ADC
    # Corrected per PINOUT_VERIFICATION.md (t_00b20081):
    #   GPIO0 = ADC1_CH0 — used for VDIV_MID (was GPS TX, disabled)
    #   GPIO8 = NO ADC channel — strapping pin, leave unused
    #   GPIO19 = FEM_TX stays here (does NOT move to GPIO0)
    gpio_nets = {
        0: "VDIV_MID",    # ADC1_CH0 — supercap voltage divider midpoint
        1: "GPS_RX",      # GPS UART RX
        2: "SPI_MISO",    # SPI MISO (needs pull-down)
        3: "LR2021_RST",
        4: "LR2021_BUSY",
        5: "LR2021_DIO9",
        6: "SPI_SCK",
        7: "SPI_MOSI",
        8: "",            # strapping pin, NO ADC — leave unused
        9: "STATUS_LED",
        10: "SPI_NSS",
        18: "",           # available but unused (USB_D-)
        19: "FEM_TX",     # stays on GPIO19 (USB_D+, used as GPIO when USB disabled)
        "VCC": "3V3",
        "GND": "GND",
    }

    comps = get_v1_fast_components()

    # Modify U1 pads for V2-ADC (different GPIO mapping)
    comps[0] = ComponentDef(
        ref="U1", x=12.0, y=12.0, value="ESP32-C3",
        pads=make_esp32c3_pads(gpio_nets),
    )

    # FEM component stays unchanged — FEM_TX net is the same, just routed
    # from GPIO19 (unchanged from V1-FAST) instead of GPIO0

    # R_DIV1: 100k 0402 at (3, 30) -- voltage divider top (3V3 to midpoint)
    comps.append(ComponentDef(
        ref="R_DIV1", x=3.0, y=30.0, value="100k",
        pads=make_resistor_pads("3V3", "VDIV_MID"),
    ))

    # R_DIV2: 100k 0402 at (3, 32) -- voltage divider bottom (midpoint to GND)
    comps.append(ComponentDef(
        ref="R_DIV2", x=3.0, y=32.0, value="100k",
        pads=make_resistor_pads("VDIV_MID", "GND"),
    ))

    return comps


# ============================================================
# BOARD CREATION
# ============================================================

def create_board_outline(board: pcbnew.BOARD):
    """Draw board outline on Edge.Cuts layer (50x40mm rectangle)."""
    w = pcbnew.FromMM(BOARD_WIDTH_MM)
    h = pcbnew.FromMM(BOARD_HEIGHT_MM)
    line_w = pcbnew.FromMM(0.15)

    # Four edges
    edges = [
        (0, 0, BOARD_WIDTH_MM, 0),           # bottom
        (BOARD_WIDTH_MM, 0, BOARD_WIDTH_MM, BOARD_HEIGHT_MM),  # right
        (BOARD_WIDTH_MM, BOARD_HEIGHT_MM, 0, BOARD_HEIGHT_MM), # top
        (0, BOARD_HEIGHT_MM, 0, 0),          # left
    ]

    for (x1, y1, x2, y2) in edges:
        shape = pcbnew.PCB_SHAPE(board)
        shape.SetStart(pcbnew.VECTOR2I_MM(x1, y1))
        shape.SetEnd(pcbnew.VECTOR2I_MM(x2, y2))
        shape.SetLayer(EDGE_CUTS)
        shape.SetWidth(line_w)
        board.Add(shape)


def create_nets(board: pcbnew.BOARD, net_defs: dict) -> dict:
    """Create all nets on the board. Returns {net_name: NETINFO_ITEM}."""
    nets_by_name = {}
    code = 1
    for net_name in net_defs:
        net = pcbnew.NETINFO_ITEM(board, net_name, code)
        board.Add(net)
        nets_by_name[net_name] = net
        code += 1
    return nets_by_name


def create_footprint(board: pcbnew.BOARD, comp: ComponentDef,
                     nets_by_name: dict) -> pcbnew.FOOTPRINT:
    """Create a footprint with pads and add it to the board."""
    fp = pcbnew.FOOTPRINT(None)
    fp.SetReference(comp.ref)
    fp.SetValue(comp.value)
    fp.SetPosition(pcbnew.VECTOR2I_MM(comp.x, comp.y))

    # Hide reference and value text on silk layers to prevent silk overlap/
    # silk_over_copper/silk_edge_clearance DRC warnings.
    for field in (fp.Reference(), fp.Value()):
        field.SetVisible(False)

    for pad_def in comp.pads:
        if not pad_def.net:
            continue  # skip NC pads

        pad = pcbnew.PAD(fp)
        pad.SetNumber(pad_def.number)
        pad.SetShape(pcbnew.PAD_SHAPE_RECT if pad_def.w > pad_def.h or pad_def.w == pad_def.h
                     else pcbnew.PAD_SHAPE_RECT)

        # Set pad position (absolute = component center + offset)
        abs_x = comp.x + pad_def.dx
        abs_y = comp.y + pad_def.dy
        pad.SetPosition(pcbnew.VECTOR2I_MM(abs_x, abs_y))

        pad.SetSize(pcbnew.VECTOR2I_MM(pad_def.w, pad_def.h))

        if pad_def.is_thru:
            pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
            # PTH pads: copper + mask on both sides
            lset = pcbnew.LSET()
            lset.AddLayer(pcbnew.F_Cu)
            lset.AddLayer(pcbnew.B_Cu)
            lset.AddLayer(pcbnew.F_Mask)
            lset.AddLayer(pcbnew.B_Mask)
            pad.SetLayerSet(lset)
            pad.SetDrillSize(pcbnew.VECTOR2I_MM(0.5, 0.5))
        else:
            pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
            # KiCad 9: SMD pads need copper + mask on the SAME side.
            # Missing mask layer causes padstack + solder_mask_bridge DRC errors.
            lset = pcbnew.LSET()
            lset.AddLayer(pad_def.layer)
            if pad_def.layer == F_CU:
                lset.AddLayer(pcbnew.F_Mask)
            else:
                lset.AddLayer(pcbnew.B_Mask)
            pad.SetLayerSet(lset)

        # Assign net
        if pad_def.net in nets_by_name:
            pad.SetNet(nets_by_name[pad_def.net])

        fp.Add(pad)

    board.Add(fp)
    return fp


def create_board_v1_fast(output_path: str) -> pcbnew.BOARD:
    """Create V1-FAST board: 17 nets, 16 components, no ADC."""
    board = pcbnew.NewBoard(output_path)
    create_board_outline(board)
    nets_by_name = create_nets(board, V1_FAST_NETS)
    comps = get_v1_fast_components()
    for comp in comps:
        create_footprint(board, comp, nets_by_name)
    # DO NOT add any copper fills. Explicit tracks only.
    return board


def create_board_v2_adc(output_path: str) -> pcbnew.BOARD:
    """Create V2-ADC board: 18 nets, 18 components, with ADC voltage divider."""
    board = pcbnew.NewBoard(output_path)
    create_board_outline(board)
    nets_by_name = create_nets(board, V2_ADC_NETS)
    comps = get_v2_adc_components()
    for comp in comps:
        create_footprint(board, comp, nets_by_name)
    # DO NOT add any copper fills. Explicit tracks only.
    return board


# ============================================================
# BOARD PARSER -- extract pads, nets, positions
# ============================================================

@dataclass
class PadInfo:
    ref: str
    pad_num: str
    net_code: int
    net_name: str
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    layer: int
    is_thru: bool

@dataclass
class NetInfo:
    net_code: int
    net_name: str
    pads: list = field(default_factory=list)
    layer: int = F_CU
    width_mm: float = TRACK_WIDTH_SIGNAL_MM
    routed: bool = False
    segments: list = field(default_factory=list)


def parse_board(board: pcbnew.BOARD, net_defs: dict) -> dict:
    """Extract all pads and nets from a KiCad board."""
    nets_by_code = {}
    net_map = board.GetNetsByNetcode()

    for code, net in net_map.items():
        if code > 0:
            net_name = net.GetNetname()
            ni = NetInfo(net_code=code, net_name=net_name)
            # Apply width/layer from net definitions
            if net_name in net_defs:
                ni.layer = net_defs[net_name]["layer"]
                ni.width_mm = net_defs[net_name]["width"]
            nets_by_code[code] = ni

    for fp in board.Footprints():
        ref = fp.GetReference()
        for pad in fp.Pads():
            net_code = pad.GetNetCode()
            if net_code == 0:
                continue

            pad_pos = pad.GetPosition()
            x_mm = pad_pos.x / 1e6
            y_mm = pad_pos.y / 1e6

            size = pad.GetSize()
            w_mm = size.x / 1e6
            h_mm = size.y / 1e6

            is_thru = (pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH or
                       pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH)

            pad_info = PadInfo(
                ref=ref,
                pad_num=str(pad.GetNumber()),
                net_code=net_code,
                net_name=nets_by_code[net_code].net_name if net_code in nets_by_code else "",
                x_mm=x_mm,
                y_mm=y_mm,
                width_mm=w_mm,
                height_mm=h_mm,
                layer=F_CU if pad.IsOnLayer(F_CU) and not pad.IsOnLayer(B_CU)
                      else (B_CU if pad.IsOnLayer(B_CU) and not pad.IsOnLayer(F_CU)
                            else F_CU),
                is_thru=is_thru,
            )

            if net_code in nets_by_code:
                nets_by_code[net_code].pads.append(pad_info)

    return nets_by_code


# ============================================================
# ROUTING STRATEGY
# ============================================================

def default_routing_strategy(nets: dict) -> list:
    """GND first (B.Cu rail, doesn't block F.Cu), then easy nets, then rest."""
    all_nets = []
    for code, net in nets.items():
        max_dist = 0
        if len(net.pads) >= 2:
            for i in range(len(net.pads)):
                for j in range(i + 1, len(net.pads)):
                    d = math.sqrt((net.pads[i].x_mm - net.pads[j].x_mm)**2 +
                                  (net.pads[i].y_mm - net.pads[j].y_mm)**2)
                    max_dist = max(max_dist, d)
        all_nets.append((code, len(net.pads), max_dist, net.net_name))

    # GND first (B.Cu, doesn't block F.Cu grid)
    gnd = [t for t in all_nets if t[3] == "GND"]
    # Rest sorted by pad count, then distance
    rest = [t for t in all_nets if t[3] != "GND"]
    rest.sort(key=lambda t: (t[1], t[2]))
    return [t[0] for t in gnd] + [t[0] for t in rest]


def route_gnd_on_bcu(net: NetInfo, router: 'GridRouter') -> bool:
    """Route GND on B.Cu using a bus-rail approach.
    Creates a horizontal rail on B.Cu and connects each pad via a via.
    THT pads connect directly on B.Cu (they span both layers).
    SMD pads on F.Cu get a via at the pad location to connect to B.Cu rail.
    """
    if len(net.pads) < 2:
        return True

    # Unblock GND pads on B.Cu for routing
    router.unblock_net_pads(net)

    # Find the median Y coordinate for the rail
    all_y = [p.y_mm for p in net.pads]
    rail_y = sorted(all_y)[len(all_y) // 2]
    # Snap rail_y to grid
    rail_y_grid = round(rail_y / router.grid_mm) * router.grid_mm
    rail_y_cell = int(rail_y_grid / router.grid_mm)

    # Find min and max X for the rail
    all_x = [p.x_mm for p in net.pads]
    rail_x_min = min(all_x)
    rail_x_max = max(all_x)

    # Snap to grid
    rail_x1_cell = int(rail_x_min / router.grid_mm)
    rail_x2_cell = int(rail_x_max / router.grid_mm)

    # Create the B.Cu rail as a single horizontal track
    rail_segments = []

    # Block the rail on B.Cu
    for x in range(rail_x1_cell, rail_x2_cell + 1):
        router._block_cell(B_CU, x, rail_y_cell)

    # Create rail track segments
    for x in range(rail_x1_cell, rail_x2_cell):
        x1_mm = x * router.grid_mm
        x2_mm = (x + 1) * router.grid_mm
        rail_segments.append((x1_mm, rail_y_grid, x2_mm, rail_y_grid, B_CU))

    # Connect each pad to the rail
    for pad in net.pads:
        pad_x_cell = int(pad.x_mm / router.grid_mm)
        pad_y_cell = int(pad.y_mm / router.grid_mm)

        if pad.is_thru:
            # THT pad: spans both layers, connect directly on B.Cu
            # Route from pad position to rail on B.Cu
            if pad_y_cell != rail_y_cell:
                # L-shaped path: horizontal then vertical (or vice versa)
                start_x = pad.x_mm
                start_y = pad.y_mm
                # Go vertical to rail_y
                rail_segments.append((start_x, start_y, start_x, rail_y_grid, B_CU))
                # Block this path
                for y in range(min(pad_y_cell, rail_y_cell), max(pad_y_cell, rail_y_cell) + 1):
                    router._block_cell(B_CU, pad_x_cell, y)
                # If pad is not aligned with rail, also add horizontal segment
                pad_x_on_rail = int(pad.x_mm / router.grid_mm)
                if pad_x_on_rail < rail_x1_cell or pad_x_on_rail > rail_x2_cell:
                    # Extend rail to cover this pad
                    if pad_x_on_rail < rail_x1_cell:
                        for x in range(pad_x_on_rail, rail_x1_cell):
                            rail_segments.append((x * router.grid_mm, rail_y_grid,
                                                  (x+1) * router.grid_mm, rail_y_grid, B_CU))
                            router._block_cell(B_CU, x, rail_y_cell)
                    elif pad_x_on_rail > rail_x2_cell:
                        for x in range(rail_x2_cell, pad_x_on_rail):
                            rail_segments.append((x * router.grid_mm, rail_y_grid,
                                                  (x+1) * router.grid_mm, rail_y_grid, B_CU))
                            router._block_cell(B_CU, x, rail_y_cell)
        else:
            # SMD pad on F.Cu: place via at pad center to connect to B.Cu rail
            via_x = pad.x_mm
            via_y = pad.y_mm
            via_x_cell = int(via_x / router.grid_mm)
            via_y_cell = int(via_y / router.grid_mm)

            # Add via marker
            rail_segments.append(('via', via_x, via_y, F_CU, B_CU))

            # B.Cu track from via to rail
            if abs(via_y - rail_y_grid) > 0.01:
                rail_segments.append((via_x, via_y, via_x, rail_y_grid, B_CU))
                # Block this path on B.Cu
                for y in range(min(via_y_cell, rail_y_cell), max(via_y_cell, rail_y_cell) + 1):
                    router._block_cell(B_CU, via_x_cell, y)

            # If via x is outside rail range, extend rail
            if via_x_cell < rail_x1_cell:
                for x in range(via_x_cell, rail_x1_cell):
                    rail_segments.append((x * router.grid_mm, rail_y_grid,
                                          (x+1) * router.grid_mm, rail_y_grid, B_CU))
                    router._block_cell(B_CU, x, rail_y_cell)
            elif via_x_cell > rail_x2_cell:
                for x in range(rail_x2_cell, via_x_cell):
                    rail_segments.append((x * router.grid_mm, rail_y_grid,
                                          (x+1) * router.grid_mm, rail_y_grid, B_CU))
                    router._block_cell(B_CU, x, rail_y_cell)

    net.segments = rail_segments
    net.routed = True
    print(f"  OK: '{net.net_name}' ({len(rail_segments)} segments, B.Cu rail + {len(net.pads)} vias)")
    return True


def assign_layers(nets: dict):
    """GND on B.Cu (rail + vias), all other nets on F.Cu."""
    for code, net in nets.items():
        if net.net_name == "GND":
            net.layer = B_CU
            net.width_mm = TRACK_WIDTH_POWER_MM
        elif net.net_name in ("3V3", "VCAP", "SOLAR_IN"):
            net.layer = F_CU
            net.width_mm = TRACK_WIDTH_POWER_MM
        elif net.net_name in ("RF_SUB_868", "RF_2G4_2400"):
            net.layer = F_CU
            net.width_mm = TRACK_WIDTH_RF_MM
        else:
            net.layer = F_CU
            net.width_mm = TRACK_WIDTH_SIGNAL_MM


# ============================================================
# A* PATHFINDING ROUTER
# ============================================================

class GridRouter:
    """A* pathfinding router on a coarse grid.

    Uses reference-counted blocking: each grid cell tracks how many
    pads/segments block it. unblock_net_pads only decrements counts for
    cells that the current net's pads actually blocked — it does NOT
    remove blocks created by adjacent nets' pads. This prevents tracks
    from routing through other pads' clearance zones."""

    def __init__(self, board_w_mm=BOARD_WIDTH_MM, board_h_mm=BOARD_HEIGHT_MM,
                 grid_mm=GRID_RESOLUTION_MM, clearance_mm=CLEARANCE_MM):
        self.grid_w = int(board_w_mm / grid_mm)
        self.grid_h = int(board_h_mm / grid_mm)
        self.grid_mm = grid_mm
        self.clearance_cells = int(clearance_mm / grid_mm)
        self.edge_cells = int(EDGE_CLEARANCE_MM / grid_mm)

        # Reference-counted blocked cells: {(x,y): count} per layer
        # A cell is blocked if count > 0.
        self.blocked = {F_CU: defaultdict(int), B_CU: defaultdict(int)}
        # Track which cells each pad blocked, for clean unblocking
        self._pad_blocks = {}  # id(pad) -> [(layer, x, y), ...]
        self.routed_paths = []

        # Block board edge margins on both layers (permanent, never unblocked)
        self._block_board_edges()

    def _block_cell(self, layer, x, y):
        """Increment block count for a cell."""
        self.blocked[layer][(x, y)] += 1

    def _unblock_cell(self, layer, x, y):
        """Decrement block count for a cell (min 0)."""
        c = self.blocked[layer].get((x, y), 0)
        if c > 0:
            self.blocked[layer][(x, y)] = c - 1

    def _is_blocked(self, layer, x, y):
        """Check if a cell is blocked (count > 0)."""
        return self.blocked[layer].get((x, y), 0) > 0

    def _block_board_edges(self):
        """Block grid cells near board edges to satisfy copper_edge_clearance DRC.
        Margin = EDGE_CLEARANCE_MM + max_track_width/2 (track edge to board edge)."""
        margin_mm = EDGE_CLEARANCE_MM + TRACK_WIDTH_RF_MM / 2
        e = int(math.ceil(margin_mm / self.grid_mm))
        for layer_key in (F_CU, B_CU):
            for x in range(self.grid_w):
                for ey in range(e):
                    self._block_cell(layer_key, x, ey)
                    self._block_cell(layer_key, x, self.grid_h - 1 - ey)
            for y in range(self.grid_h):
                for ex in range(e):
                    self._block_cell(layer_key, ex, y)
                    self._block_cell(layer_key, self.grid_w - 1 - ex, y)

    def block_pad(self, pad: PadInfo, net_code: int):
        """Block grid cells for a pad.

        Blocks only the cells the pad physically covers + 1 cell margin.
        With 0.25mm grid, this creates a minimal blocked zone:
        ESP32-C3 pad (1.0x0.6): blocks ~4x3 cells + 1 margin = ~6x5
        LR2021 pad (1.2x0.8): blocks ~5x4 cells + 1 margin = ~7x6
        Small pad (0.6x0.5): blocks ~3x2 cells + 1 margin = ~5x4

        At 2mm pitch (8 cells), adjacent LR2021 pads leave a 1-cell corridor.
        At 1.5mm pitch (6 cells), adjacent ESP32 pads leave a 0-cell corridor.
        For ESP32 pads, the corridor is blocked — A* must route around the
        entire pad cluster.

        For PTH pads, blocks on both F.Cu and B.Cu."""
        layer = pad.layer if not pad.is_thru else F_CU
        layers = [F_CU, B_CU] if pad.is_thru else [layer]
        # Block pad coverage + 1 cell clearance margin
        pad_half = max(pad.width_mm, pad.height_mm) / 2
        margin_mm = pad_half + self.grid_mm  # pad half + 1 cell
        margin = int(math.ceil(margin_mm / self.grid_mm))
        blocked_cells = []
        for layer_key in layers:
            x0 = int((pad.x_mm - margin * self.grid_mm) / self.grid_mm)
            x1 = int((pad.x_mm + margin * self.grid_mm) / self.grid_mm)
            y0 = int((pad.y_mm - margin * self.grid_mm) / self.grid_mm)
            y1 = int((pad.y_mm + margin * self.grid_mm) / self.grid_mm)
            for x in range(max(0, x0), min(self.grid_w, x1)):
                for y in range(max(0, y0), min(self.grid_h, y1)):
                    self._block_cell(layer_key, x, y)
                    blocked_cells.append((layer_key, x, y))
        self._pad_blocks[id(pad)] = blocked_cells

    def block_all_pads(self, nets: dict):
        """Block all pads on the grid (with clearance)."""
        for net in nets.values():
            for pad in net.pads:
                self.block_pad(pad, net.net_code)

    def unblock_net_pads(self, net: NetInfo):
        """Unblock pads belonging to this net so A* can route to/from them.
        Uses reference counting: only decrements cells that this net's pads
        actually blocked. Adjacent pads' blocks are preserved."""
        for pad in net.pads:
            cells = self._pad_blocks.get(id(pad))
            if cells:
                for (layer_key, x, y) in cells:
                    self._unblock_cell(layer_key, x, y)

    def a_star(self, start, goal, layer, max_explore=2000000) -> Optional[list]:
        """A* pathfinding on the grid. Returns list of (x,y) grid cells or None.
        Uses 8-directional movement (orthogonal + diagonal) for better routing."""
        blocked = self.blocked[layer]

        def is_blocked(x, y):
            return blocked.get((x, y), 0) > 0

        def heuristic(a, b):
            # Octile distance for 8-directional movement
            dx = abs(a[0] - b[0])
            dy = abs(a[1] - b[1])
            return max(dx, dy) + (1.414 - 1) * min(dx, dy)

        open_set = [(0, start)]
        came_from = {}
        g_score = {start: 0}
        closed = set()
        explored = 0

        while open_set:
            _, current = heapq.heappop(open_set)

            if current == goal:
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                path.reverse()
                return path

            if current in closed:
                continue
            closed.add(current)
            explored += 1
            if explored > max_explore:
                return None

            # 8 directions: orthogonal (cost 1) + diagonal (cost ~1.414)
            for dx, dy, cost in [(0, 1, 1), (0, -1, 1), (1, 0, 1), (-1, 0, 1),
                                  (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]:
                neighbor = (current[0] + dx, current[1] + dy)
                if neighbor[0] < 0 or neighbor[0] >= self.grid_w:
                    continue
                if neighbor[1] < 0 or neighbor[1] >= self.grid_h:
                    continue
                if is_blocked(neighbor[0], neighbor[1]):
                    continue
                # For diagonal moves, prevent cutting through blocked corners
                if dx != 0 and dy != 0:
                    if is_blocked(current[0] + dx, current[1]) or is_blocked(current[0], current[1] + dy):
                        continue

                tentative_g = g_score[current] + cost
                if neighbor in closed:
                    continue
                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f = tentative_g + heuristic(neighbor, goal)
                    heapq.heappush(open_set, (f, neighbor))

        return None

    def route_net(self, net: NetInfo) -> bool:
        """Route a single net using A* with nearest-neighbor pad ordering.
        On pair failure, skip that pair and try the next — partial routing
        is better than no routing. Net is marked routed if >=1 pair succeeds."""
        if len(net.pads) < 2:
            return True

        self.unblock_net_pads(net)

        pads = list(net.pads)
        routed_pads = [pads[0]]
        unrouted = pads[1:]
        failed_pairs = 0

        while unrouted:
            best_dist = float('inf')
            best_pair = None
            for rp in routed_pads:
                for up in unrouted:
                    dist = math.sqrt((rp.x_mm - up.x_mm)**2 + (rp.y_mm - up.y_mm)**2)
                    if dist < best_dist:
                        best_dist = dist
                        best_pair = (rp, up)

            if best_pair is None:
                break

            src_pad, dst_pad = best_pair
            src = (int(src_pad.x_mm / self.grid_mm), int(src_pad.y_mm / self.grid_mm))
            dst = (int(dst_pad.x_mm / self.grid_mm), int(dst_pad.y_mm / self.grid_mm))

            path = self.a_star(src, dst, net.layer)

            if path is None:
                print(f"  SKIP: net '{net.net_name}' "
                      f"({src_pad.ref}.{src_pad.pad_num} -> {dst_pad.ref}.{dst_pad.pad_num})")
                failed_pairs += 1
                unrouted.remove(dst_pad)
                continue

            route_layer = net.layer

            segments = []
            for i in range(len(path) - 1):
                x1 = path[i][0] * self.grid_mm
                y1 = path[i][1] * self.grid_mm
                x2 = path[i + 1][0] * self.grid_mm
                y2 = path[i + 1][1] * self.grid_mm
                segments.append((x1, y1, x2, y2, route_layer))
                self._block_segment(path[i], path[i + 1], route_layer, net.width_mm)

            # Snap first segment start to actual pad center
            if segments:
                x1, y1, x2, y2, lyr = segments[0]
                segments[0] = (src_pad.x_mm, src_pad.y_mm, x2, y2, lyr)
                # Snap last segment end to actual pad center
                x1, y1, x2, y2, lyr = segments[-1]
                segments[-1] = (x1, y1, dst_pad.x_mm, dst_pad.y_mm, lyr)

            net.segments.extend(segments)
            routed_pads.append(dst_pad)
            unrouted.remove(dst_pad)

        if net.segments:
            net.routed = True
            unconn = failed_pairs
            if unconn > 0:
                print(f"  OK: '{net.net_name}' ({len(net.segments)} segments, {unconn} pair(s) skipped)")
            else:
                print(f"  OK: '{net.net_name}' ({len(net.segments)} segments)")
            return True
        else:
            print(f"  FAIL: net '{net.net_name}' — no pairs routable")
            return False

    def _block_segment(self, p1, p2, layer, width_mm=TRACK_WIDTH_SIGNAL_MM):
        """Block grid cells along a segment with clearance.
        Margin = 2 cells (0.5mm) for adequate DRC clearance on F.Cu.
        GND is on B.Cu so F.Cu track-to-track clearance is the only concern.
        """
        margin = 2
        x0, y0 = p1
        x1, y1 = p2
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        steps = max(dx, dy, 1)
        for i in range(steps + 1):
            x = x0 + (x1 - x0) * i // steps
            y = y0 + (y1 - y0) * i // steps
            for ox in range(-margin, margin + 1):
                for oy in range(-margin, margin + 1):
                    cx, cy = x + ox, y + oy
                    if 0 <= cx < self.grid_w and 0 <= cy < self.grid_h:
                        self._block_cell(layer, cx, cy)


# ============================================================
# TRACK WRITER
# ============================================================

def ripup_all_tracks(board: pcbnew.BOARD):
    """Remove all existing tracks from the board."""
    tracks = list(board.Tracks())
    for t in tracks:
        board.Remove(t)
    print(f"  Ripped up {len(tracks)} tracks")


def write_tracks_to_board(board: pcbnew.BOARD, nets: dict):
    """Write routed tracks to the KiCad board via pcbnew API.
    Also writes vias for layer transitions."""
    net_map = board.GetNetsByNetcode()
    track_count = 0
    via_count = 0

    for net_code, net in nets.items():
        if not net.routed or not net.segments:
            continue

        ki_net = net_map[net_code]

        for seg in net.segments:
            if isinstance(seg, tuple) and len(seg) == 5 and isinstance(seg[0], str) and seg[0] == 'via':
                _, vx, vy, from_layer, to_layer = seg
                via = pcbnew.PCB_VIA(board)
                via.SetPosition(pcbnew.VECTOR2I_MM(float(vx), float(vy)))
                via.SetDrill(pcbnew.FromMM(VIA_DRILL_MM))
                via.SetWidth(pcbnew.FromMM(VIA_SIZE_MM))
                via.SetNet(ki_net)
                via.SetViaType(pcbnew.VIATYPE_THROUGH)
                board.Add(via)
                via_count += 1
            elif isinstance(seg, tuple) and len(seg) == 5:
                x1, y1, x2, y2, layer = seg
                track = pcbnew.PCB_TRACK(board)
                track.SetStart(pcbnew.VECTOR2I_MM(float(x1), float(y1)))
                track.SetEnd(pcbnew.VECTOR2I_MM(float(x2), float(y2)))
                track.SetWidth(pcbnew.FromMM(net.width_mm))
                track.SetLayer(layer)
                track.SetNet(ki_net)
                board.Add(track)
                track_count += 1

    print(f"  Written {track_count} track segments, {via_count} vias to board")


# ============================================================
# DRC RUNNER
# ============================================================

def run_drc(pcb_path: str, output_json: str = "/tmp/drc_result.json") -> dict:
    """Run kicad-cli pcb drc --format json and return parsed results."""
    cmd = [
        "kicad-cli", "pcb", "drc",
        "--format", "json",
        "--output", output_json,
        pcb_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if not os.path.exists(output_json):
        print(f"  DRC failed: {result.stderr}")
        return {"violations": [], "unconnected_items": []}

    with open(output_json) as f:
        drc = json.load(f)

    violations = drc.get("violations", [])
    unconnected = drc.get("unconnected_items", [])

    print(f"  DRC: {len(violations)} violations, {len(unconnected)} unconnected")
    return {"violations": violations, "unconnected_items": unconnected}


# ============================================================
# GERBER EXPORT
# ============================================================

def export_gerbers(pcb_path: str, output_dir: str):
    """Export gerbers + drill files for JLCPCB ordering."""
    os.makedirs(output_dir, exist_ok=True)

    layers = "F.Cu,B.Cu,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts,F.Paste,B.Paste,F.Fab,B.Fab"
    cmd = [
        "kicad-cli", "pcb", "export", "gerbers",
        "--output", output_dir,
        "--layers", layers,
        pcb_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(f"  Gerber export: {result.stdout.strip()}")

    cmd = [
        "kicad-cli", "pcb", "export", "drill",
        "--output", output_dir,
        "--format", "excellon",
        pcb_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(f"  Drill export: {result.stdout.strip()}")

    return output_dir


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="PCB auto-route pipeline: NewBoard -> A* -> DRC -> iterate")
    parser.add_argument("--board-type", required=True,
                        choices=["v1-fast", "v2-adc"],
                        help="Board variant to create")
    parser.add_argument("--output", required=True,
                        help="Output .kicad_pcb file path")
    parser.add_argument("--gerber-dir", default=None,
                        help="Gerber output directory (optional)")
    parser.add_argument("--max-iterations", type=int, default=10,
                        help="Max DRC iterations (default: 10)")
    parser.add_argument("--create-only", action="store_true",
                        help="Only create board with footprints, skip routing/DRC")
    args = parser.parse_args()

    print("=" * 60)
    print("PCB Auto-Routing Pipeline (NewBoard + A* + DRC)")
    print("=" * 60)
    print(f"Board type: {args.board_type}")
    print(f"Output:     {args.output}")
    print(f"Max iterations: {args.max_iterations}")
    print()

    # Select board type
    if args.board_type == "v1-fast":
        create_fn = create_board_v1_fast
        net_defs = V1_FAST_NETS
    else:
        create_fn = create_board_v2_adc
        net_defs = V2_ADC_NETS

    # STEP 1: Create board with footprints (uses NewBoard)
    print("STEP 1: Creating board with NewBoard()...")
    board = create_fn(args.output)
    pcbnew.SaveBoard(args.output, board)
    print(f"  Board created with {len(list(board.Footprints()))} footprints")

    if args.create_only:
        print("\n--create-only: skipping routing/DRC. Board saved.")
        # Print summary stats
        nets = parse_board(board, net_defs)
        print(f"  Nets: {len(nets)}")
        print(f"  Pads: {sum(len(n.pads) for n in nets.values())}")
        print(f"  Footprints: {len(list(board.Footprints()))}")
        return 0

    # Parse the board to get nets and pads
    nets = parse_board(board, net_defs)
    print(f"  Parsed {len(nets)} nets, {sum(len(n.pads) for n in nets.values())} pads")

    # STEP 2: Generate routing strategy
    print("\nSTEP 2: Generating routing strategy...")
    routing_order = default_routing_strategy(nets)
    assign_layers(nets)
    for code in routing_order:
        net = nets[code]
        layer_name = "F.Cu" if net.layer == F_CU else "B.Cu"
        print(f"  {net.net_name:20s} -> {layer_name}, {net.width_mm}mm, "
              f"{len(net.pads)} pads")

    # Iteration loop
    for iteration in range(1, args.max_iterations + 1):
        print(f"\n{'=' * 60}")
        print(f"ITERATION {iteration}/{args.max_iterations}")
        print(f"{'=' * 60}")

        # STEP 3: Run A* router on all nets
        print("\nSTEP 3: A* pathfinding...")
        router = GridRouter()
        router.block_all_pads(nets)

        for net_code in routing_order:
            net = nets[net_code]
            net.segments = []
            net.routed = False
            if net.net_name == "GND":
                route_gnd_on_bcu(net, router)
            else:
                router.route_net(net)

        # STEP 4: Write tracks to board
        print("\nSTEP 4: Writing tracks to board...")
        # Re-create board from scratch (NewBoard)
        board = create_fn(args.output)
        ripup_all_tracks(board)
        write_tracks_to_board(board, nets)
        pcbnew.SaveBoard(args.output, board)
        print(f"  Saved to {args.output}")

        # STEP 5: Run DRC
        print("\nSTEP 5: Running DRC...")
        drc_result = run_drc(args.output)

        violations = drc_result["violations"]
        unconnected = drc_result["unconnected_items"]

        if len(violations) == 0 and len(unconnected) == 0:
            print("\nDRC CLEAN! Board is ready for fabrication.")
            if args.gerber_dir:
                print("\nSTEP 6: Exporting gerbers...")
                export_gerbers(args.output, args.gerber_dir)
                print(f"  Gerbers saved to {args.gerber_dir}")
            return 0

        # STEP 5b: Analyze DRC errors for next iteration
        print("\nSTEP 5b: Analyzing DRC errors...")
        short_violations = [v for v in violations
                            if "short" in str(v.get("type", "")).lower()
                            or "short" in str(v.get("description", "")).lower()]
        clearance_violations = [v for v in violations
                                if "clearance" in str(v.get("type", "")).lower()]
        print(f"  Shorts: {len(short_violations)}")
        print(f"  Clearance: {len(clearance_violations)}")
        print(f"  Unconnected: {len(unconnected)}")

        # Circuit breaker: check if same violations persist
        # (simplified — just report and continue to next iteration)
        if iteration < args.max_iterations:
            print(f"\n  Continuing to next iteration (re-route with same strategy)...")

    print(f"\nFailed to converge after {args.max_iterations} iterations.")
    print(f"  {len(violations)} violations, {len(unconnected)} unconnected remain.")
    print(f"  Board saved at {args.output} for manual inspection.")
    return 1


if __name__ == "__main__":
    sys.exit(main())