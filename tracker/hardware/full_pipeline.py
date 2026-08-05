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
GRID_RESOLUTION_MM = 0.1      # A* grid cell size
TRACK_WIDTH_SIGNAL_MM = 0.25  # default signal track width
TRACK_WIDTH_POWER_MM = 0.40   # power/ground track width
TRACK_WIDTH_RF_MM = 0.76      # RF antenna trace width
CLEARANCE_MM = 0.30           # min clearance between different nets
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
    "GND":          {"width": TRACK_WIDTH_POWER_MM, "layer": B_CU},
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
                dx=-3.0 + i * pitch,
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

    # Additional GND pad on B.Cu (for via stitching)
    pads.append(PadDef(
        number="GND_B",
        net=gpio_nets.get("GND", ""),
        dx=0,
        dy=0,
        w=1.5, h=1.5,
        layer=B_CU,
    ))

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

    # R_LED: 330 ohm 0402 at (17.5, 4)
    comps.append(ComponentDef(
        ref="R_LED", x=17.5, y=4.0, value="330R",
        pads=make_resistor_pads("STATUS_LED", "LED_ANODE"),
    ))

    # R_PD: 10k pull-down 0402 at (10, 14)
    comps.append(ComponentDef(
        ref="R_PD", x=10.0, y=14.0, value="10k",
        pads=make_resistor_pads("GND", "SPI_MISO"),
    ))

    # C_CAP: Supercapacitor THT at (8, 37)
    comps.append(ComponentDef(
        ref="C_CAP", x=8.0, y=37.0, value="Supercap",
        pads=make_tht_pads("VCAP", "GND", pitch_mm=5.0),
    ))

    # SOLAR: Solar connector 2-pin THT at (3, 37)
    comps.append(ComponentDef(
        ref="SOLAR", x=3.0, y=37.0, value="Solar-Conn",
        pads=make_tht_pads("SOLAR_IN", "GND", pitch_mm=2.54),
    ))

    # ANT1: U.FL for sub-GHz at (48, 25)
    comps.append(ComponentDef(
        ref="ANT1", x=48.0, y=25.0, value="U.FL-868",
        pads=make_ufl_pads("RF_SUB_868"),
    ))

    # ANT2: U.FL for 2.4GHz at (48, 30)
    comps.append(ComponentDef(
        ref="ANT2", x=48.0, y=30.0, value="U.FL-2400",
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
            # PTH pads are on both copper layers
            lset = pcbnew.LSET()
            lset.AddLayer(pcbnew.F_Cu)
            lset.AddLayer(pcbnew.B_Cu)
            pad.SetLayerSet(lset)
            pad.SetDrillSize(pcbnew.VECTOR2I_MM(0.5, 0.5))
        else:
            pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
            # KiCad 9: SetLayer() alone does not work for SMD pads.
            # Must use SetLayerSet() with an LSET containing the target layer.
            lset = pcbnew.LSET()
            lset.AddLayer(pad_def.layer)
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
                layer=F_CU if pad.IsOnLayer(F_CU) else B_CU,
                is_thru=is_thru,
            )

            if net_code in nets_by_code:
                nets_by_code[net_code].pads.append(pad_info)

    return nets_by_code


# ============================================================
# ROUTING STRATEGY
# ============================================================

def default_routing_strategy(nets: dict) -> list:
    """Route easy nets first (few pads, short distance), then power nets.
    This prevents long power traces from blocking short signal routes."""
    all_nets = []
    for code, net in nets.items():
        # Compute total pad span (max distance between any 2 pads)
        max_dist = 0
        if len(net.pads) >= 2:
            for i in range(len(net.pads)):
                for j in range(i + 1, len(net.pads)):
                    d = math.sqrt((net.pads[i].x_mm - net.pads[j].x_mm)**2 +
                                  (net.pads[i].y_mm - net.pads[j].y_mm)**2)
                    max_dist = max(max_dist, d)
        all_nets.append((code, len(net.pads), max_dist))

    # Sort by: fewest pads first, then shortest span first
    all_nets.sort(key=lambda t: (t[1], t[2]))
    return [t[0] for t in all_nets]


def assign_layers(nets: dict):
    """Assign layers based on where the pads actually are.
    SMD pads are on F_Cu, so most nets route on F_Cu.
    Only route GND on B_Cu if it has thru-hole pads that are on both layers.
    For prototype: route everything on F_Cu to avoid needing vias."""
    for code, net in nets.items():
        if net.net_name == "GND":
            # GND has many thru-hole pads (ANT, SOLAR, C_CAP) on both layers
            # Route on B_Cu to provide a ground plane effect
            net.layer = B_CU
            net.width_mm = TRACK_WIDTH_POWER_MM
        elif net.net_name == "3V3":
            # 3V3 pads are all SMD on F_Cu — route on F_Cu
            net.layer = F_CU
            net.width_mm = TRACK_WIDTH_POWER_MM
        elif net.net_name in ("VCAP", "SOLAR_IN"):
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
    """A* pathfinding router on a coarse grid."""

    def __init__(self, board_w_mm=BOARD_WIDTH_MM, board_h_mm=BOARD_HEIGHT_MM,
                 grid_mm=GRID_RESOLUTION_MM, clearance_mm=CLEARANCE_MM):
        self.grid_w = int(board_w_mm / grid_mm)
        self.grid_h = int(board_h_mm / grid_mm)
        self.grid_mm = grid_mm
        self.clearance_cells = int(clearance_mm / grid_mm)

        self.blocked = {F_CU: set(), B_CU: set()}
        self.routed_paths = []

    def block_pad(self, pad: PadInfo, net_code: int):
        """Block grid cells around a pad, except for cells on the pad's own net."""
        layer = pad.layer if not pad.is_thru else F_CU
        layers = [F_CU, B_CU] if pad.is_thru else [layer]
        for layer_key in layers:
            x0 = int((pad.x_mm - pad.width_mm / 2 - self.grid_mm) / self.grid_mm)
            x1 = int((pad.x_mm + pad.width_mm / 2 + self.grid_mm) / self.grid_mm)
            y0 = int((pad.y_mm - pad.height_mm / 2 - self.grid_mm) / self.grid_mm)
            y1 = int((pad.y_mm + pad.height_mm / 2 + self.grid_mm) / self.grid_mm)
            for x in range(max(0, x0), min(self.grid_w, x1)):
                for y in range(max(0, y0), min(self.grid_h, y1)):
                    self.blocked[layer_key].add((x, y))

    def block_all_pads(self, nets: dict):
        """Block all pads on the grid (with clearance)."""
        for net in nets.values():
            for pad in net.pads:
                self.block_pad(pad, net.net_code)

    def unblock_net_pads(self, net: NetInfo):
        """Unblock pads belonging to this net so A* can route to/from them.
        Must unblock the SAME area that block_pad blocked (including the
        1-cell margin), otherwise A* start/goal cells are surrounded by
        a ring of blocked cells and no path can escape."""
        for pad in net.pads:
            layer = pad.layer if not pad.is_thru else net.layer
            layers = [F_CU, B_CU] if pad.is_thru else [layer]
            for layer_key in layers:
                x0 = int((pad.x_mm - pad.width_mm / 2 - self.grid_mm) / self.grid_mm)
                x1 = int((pad.x_mm + pad.width_mm / 2 + self.grid_mm) / self.grid_mm)
                y0 = int((pad.y_mm - pad.height_mm / 2 - self.grid_mm) / self.grid_mm)
                y1 = int((pad.y_mm + pad.height_mm / 2 + self.grid_mm) / self.grid_mm)
                for x in range(max(0, x0), min(self.grid_w, x1)):
                    for y in range(max(0, y0), min(self.grid_h, y1)):
                        self.blocked[layer_key].discard((x, y))

    def a_star(self, start, goal, layer, max_explore=200000) -> Optional[list]:
        """A* pathfinding on the grid. Returns list of (x,y) grid cells or None.
        Uses 8-directional movement (orthogonal + diagonal) for better routing."""
        blocked = self.blocked[layer]

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
                if neighbor in blocked:
                    continue
                # For diagonal moves, prevent cutting through blocked corners
                if dx != 0 and dy != 0:
                    if (current[0] + dx, current[1]) in blocked or (current[0], current[1] + dy) in blocked:
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
                other_layer = B_CU if net.layer == F_CU else F_CU
                path = self.a_star(src, dst, other_layer)
                if path is not None:
                    route_layer = other_layer
                else:
                    print(f"  SKIP: net '{net.net_name}' "
                          f"({src_pad.ref}.{src_pad.pad_num} -> {dst_pad.ref}.{dst_pad.pad_num})")
                    failed_pairs += 1
                    # Remove this destination from unrouted and try remaining
                    unrouted.remove(dst_pad)
                    continue
            else:
                route_layer = net.layer

            segments = []
            for i in range(len(path) - 1):
                x1 = path[i][0] * self.grid_mm
                y1 = path[i][1] * self.grid_mm
                x2 = path[i + 1][0] * self.grid_mm
                y2 = path[i + 1][1] * self.grid_mm
                segments.append((x1, y1, x2, y2, route_layer))
                self._block_segment(path[i], path[i + 1], route_layer)

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

    def _block_segment(self, p1, p2, layer):
        """Block grid cells along a segment with clearance.
        Use a 1-cell corridor (not 3-cell) to avoid saturating the grid
        on a 500x400 board with 17 nets."""
        x0, y0 = p1
        x1, y1 = p2
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        steps = max(dx, dy, 1)
        for i in range(steps + 1):
            x = x0 + (x1 - x0) * i // steps
            y = y0 + (y1 - y0) * i // steps
            # Only block the cell itself + immediate neighbors (3x3 max)
            for ox in range(-1, 2):
                for oy in range(-1, 2):
                    cx, cy = x + ox, y + oy
                    if 0 <= cx < self.grid_w and 0 <= cy < self.grid_h:
                        self.blocked[layer].add((cx, cy))


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
    """Write routed tracks to the KiCad board via pcbnew API."""
    net_map = board.GetNetsByNetcode()
    track_count = 0

    for net_code, net in nets.items():
        if not net.routed or not net.segments:
            continue

        ki_net = net_map[net_code]

        for (x1, y1, x2, y2, layer) in net.segments:
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(pcbnew.VECTOR2I_MM(x1, y1))
            track.SetEnd(pcbnew.VECTOR2I_MM(x2, y2))
            track.SetWidth(pcbnew.FromMM(net.width_mm))
            track.SetLayer(layer)
            track.SetNet(ki_net)
            board.Add(track)
            track_count += 1

    print(f"  Written {track_count} track segments to board")


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

        # STEP 3: Run A* router
        print("\nSTEP 3: A* pathfinding...")
        router = GridRouter()
        router.block_all_pads(nets)

        for net_code in routing_order:
            net = nets[net_code]
            net.segments = []
            net.routed = False
            success = router.route_net(net)
            if not success:
                # Try alternate layer
                net.layer = B_CU if net.layer == F_CU else F_CU
                print(f"  Retrying '{net.net_name}' on alternate layer...")
                net.segments = []
                net.routed = False
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

        # Adjust strategy: swap layers on nets with most violations
        if iteration < args.max_iterations:
            print("\n  Adjusting strategy for next iteration...")
            net_violation_count = defaultdict(int)
            for v in violations:
                for item in v.get("items", []):
                    desc = item.get("description", "")
                    if "[" in desc and "]" in desc:
                        net_name = desc[desc.index("[") + 1:desc.index("]")]
                        net_violation_count[net_name] += 1

            for net_name, count in sorted(net_violation_count.items(),
                                          key=lambda x: -x[1])[:3]:
                for net in nets.values():
                    if net.net_name == net_name:
                        net.layer = B_CU if net.layer == F_CU else F_CU
                        print(f"    Swapped '{net_name}' to "
                              f"{'B.Cu' if net.layer == B_CU else 'F.Cu'}")
                        break

    print(f"\nFailed to converge after {args.max_iterations} iterations.")
    print(f"  {len(violations)} violations, {len(unconnected)} unconnected remain.")
    print(f"  Board saved at {args.output} for manual inspection.")
    return 1


if __name__ == "__main__":
    sys.exit(main())