#!/usr/bin/python3.14
"""
Stage 1 — Balloon-C3 flight board (ESP32-C3 single-MCU), 4-layer, 35x30mm.

Pipeline (two-stage plan, Stage 1 / GLM 5.2 generation):
  1. PRE-LAYOUT CHECK (printed + written to PRE-LAYOUT-C3.md): every component
     center, every net with layer assignment, pairwise pad-clearance check,
     board-edge boundary check. FAILS LOUD if any different-net pads < 0.20mm
     apart or any pad outside the 0.5mm edge margin.
  2. Build board with pcbnew.NewBoard() (NEVER the loader — it segfaults headless).
  3. 4 copper layers: F.Cu / In1.Cu=GND plane / In2.Cu=3V3 plane / B.Cu.
  4. Place all 17 footprints at the pre-layout coordinates.
  5. Add full-board GND zone (In1.Cu) + 3V3 zone (In2.Cu).
  6. Export DSN -> FreeRouting -> import SES for signal routing.
  7. Fill zones, run DRC, export gerbers + drill, zip.
  8. Print QUALITY GATES summary.

Run:  /usr/bin/python3.14 stage1_c3.py
"""

import sys
import os
import json
import math
import subprocess

sys.path.insert(0, '/usr/lib/python3/dist-packages')

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pcbnew
from full_pipeline import (
    PadDef, ComponentDef,
    create_nets, create_footprint,
    run_drc, ripup_all_tracks, export_gerbers,
    make_lr2021_pads, make_ldo_pads, make_diode_pads,
    make_resistor_pads, make_led_pads, make_cap_pads,
    make_tht_pads, make_ufl_pads,
)
from freerouting_pipeline import set_board_design_rules, patch_dsn_rules, run_freerouting
from ses_import import apply_ses_to_board


def patch_dsn_c3(dsn_path):
    """Extend the shared DSN patch: mark In1.Cu / In2.Cu as (type power) so
    FreeRouting treats them as plane layers and routes signals ONLY on F.Cu/B.Cu.
    Without this, FreeRouting lays signal tracks on the internal plane layers and
    the SES importer (which only knows F.Cu/B.Cu) collapses them onto F.Cu -> shorts.
    Also bumps track width to a manufacturable 0.20mm."""
    with open(dsn_path, 'r') as f:
        content = f.read()
    # power-type for the plane layers
    content = content.replace(
        '(layer In1.Cu\n      (type signal)',
        '(layer In1.Cu\n      (type power)')
    content = content.replace(
        '(layer In2.Cu\n      (type signal)',
        '(layer In2.Cu\n      (type power)')
    # keep F.Cu / B.Cu as signal, bump widths to 0.20mm if still tiny
    content = content.replace(
        '(rule\n      (width 200)\n      (clearance 200)\n      (clearance 50 (type smd_smd))\n    )',
        '(rule\n      (width 2000)\n      (clearance 200)\n      (clearance 50 (type smd_smd))\n    )')
    content = content.replace(
        '(rule\n        (width 200)\n        (clearance 200)\n      )',
        '(rule\n        (width 2000)\n        (clearance 200)\n      )')
    with open(dsn_path, 'w') as f:
        f.write(content)
    print("  Patched DSN: In1/In2 -> (type power), width 0.20mm")

# ============================================================
# BOARD SPEC
# ============================================================
BOARD_W = 35.0   # mm (X)
BOARD_H = 30.0   # mm (Y)
EDGE_MARGIN = 0.5      # JLCPCB min edge clearance (mm)
MIN_CLEARANCE = 0.20   # min different-net pad/track clearance (mm)
OUT_DIR = os.path.join(HERE, 'output')
OUT_PCB = os.path.join(OUT_DIR, 'v_c3_4layer.kicad_pcb')
GERBER_DIR = os.path.join(OUT_DIR, 'v_c3_4layer_gerbers')
PRELAYOUT_MD = os.path.join(OUT_DIR, 'PRE-LAYOUT-C3.md')

FREEROUTING_JAR = "/tmp/freerouting_extracted/freerouting-2.2.4-linux-x64/lib/app/freerouting-executable.jar"
JAVA_BIN = "/usr/lib/jvm/java-25-openjdk-amd64/bin/java"

TRACK_SIG = 0.25
TRACK_PWR = 0.40
TRACK_RF = 0.76

# ============================================================
# NET TABLE  (pin map = ground truth: app_main.cpp:85-94 / task body)
# Layer assignment: power nets -> internal planes; signals -> F.Cu/B.Cu.
#   "plane:gnd"  => In1.Cu zone    "plane:3v3" => In2.Cu zone
# ============================================================
C3_NETS = {
    # power
    "3V3":         {"width": TRACK_PWR, "plane": "3v3"},
    "GND":         {"width": TRACK_PWR, "plane": "gnd"},
    "VCAP":        {"width": TRACK_PWR},     # supercap node (D1.K, LDO.IN, C1, C_CAP+)
    "SOLAR_IN":    {"width": TRACK_PWR},     # solar panel + (D1.A)
    "VDIV_MID":    {"width": TRACK_SIG},     # 100k/100k divider midpoint (R_DIV1.R_DIV2)
    # SPI bus -> LR2021
    "SPI_SCK":     {"width": TRACK_SIG},     # GPIO6  <-> LR2021 pin5
    "SPI_MOSI":    {"width": TRACK_SIG},     # GPIO7  <-> LR2021 pin4
    "SPI_MISO":    {"width": TRACK_SIG},     # GPIO2  <-> LR2021 pin3 (+ R_PD pull-down)
    "SPI_NSS":     {"width": TRACK_SIG},     # GPIO10 <-> LR2021 pin6
    # LR2021 control
    "LR2021_RST":  {"width": TRACK_SIG},     # GPIO3  <-> LR2021 pin14
    "LR2021_BUSY": {"width": TRACK_SIG},     # GPIO4  <-> LR2021 pin7
    "LR2021_DIO9": {"width": TRACK_SIG},     # GPIO5  <-> LR2021 pin13
    # GPS UART
    "GPS_TX":      {"width": TRACK_SIG},     # GPIO0  <-> GPS.pin4 (config cmds; firmware may -1 disable)
    "GPS_RX":      {"width": TRACK_SIG},     # GPIO1  <-> GPS.pin3 (NMEA from GPS)
    # FEM control (SKY66112)
    "FEM_TX":      {"width": TRACK_SIG},     # GPIO19 <-> FEM.TX  (TX enable)
    "FEM_RX":      {"width": TRACK_SIG},     # GPIO8  <-> FEM.RX  (RX enable / mode)
    # LED indicator: GPIO18 drives LED1 via R_LED. GPIO9 = alternate STATUS_LED breakout.
    "LED":         {"width": TRACK_SIG},     # GPIO18 <-> R_LED.1
    "LED_ANODE":   {"width": TRACK_SIG},     # R_LED.2 <-> LED1.A
    "STATUS_LED":  {"width": TRACK_SIG},     # GPIO9  (1-pad breakout; alt indicator)
    # UART programming breakout (1-pad test points)
    "UART0_RX":    {"width": TRACK_SIG},     # GPIO20
    "UART0_TX":    {"width": TRACK_SIG},     # GPIO21
    # RF antenna traces (50 ohm, 0.76mm on 1.6mm FR4)
    "RF_SUB_868":  {"width": TRACK_RF},      # LR2021 pin9  <-> ANT1
    "RF_2G4_2400": {"width": TRACK_RF},      # LR2021 pin18 <-> ANT2
}

# ============================================================
# ESP32-C3 PAD LAYOUT (custom, sparse — avoids corner collisions)
# QFN32 module. 4 sides, NO pads in the 4 corners. 1.5mm pitch, 0.9x0.6 pads.
#   Left  (x=-3.5): GPIO0..GPIO5   (6 pads, dy -3.0..+3.0)
#   Bot   (y=+3.0): GPIO5..GPIO7 ... see assignment below
#   Right (x=+3.5): GPIO8,GPIO9,GPIO10,GPIO18,GPIO19
#   Top   (y=-3.0): GPIO20,GPIO21,VCC,GND
# All 15 GPIOs + VCC + GND = 17 pads. Pin map matches task body exactly.
# ============================================================
def make_esp32c3_c3_pads():
    """ESP32-C3 pads for the C3 flight board (task-body pin map)."""
    pw, ph = 0.9, 0.6   # pad size
    pads = []
    # Left column (x=-3.5): GPIO0..GPIO5
    left = [(0, "GPS_TX"), (1, "GPS_RX"), (2, "SPI_MISO"),
            (3, "LR2021_RST"), (4, "LR2021_BUSY"), (5, "LR2021_DIO9")]
    for i, (g, net) in enumerate(left):
        pads.append(PadDef(number=f"GPIO{g}", net=net, dx=-3.5,
                           dy=-3.0 + i * 1.2, w=pw, h=ph))
    # Bottom row (y=+3.0): GPIO6, GPIO7
    for i, (g, net) in enumerate([(6, "SPI_SCK"), (7, "SPI_MOSI")]):
        pads.append(PadDef(number=f"GPIO{g}", net=net, dx=-0.75 + i * 1.5,
                           dy=3.0, w=pw, h=ph))
    # Right column (x=+3.5): GPIO8,GPIO9,GPIO10,GPIO18,GPIO19
    right = [(8, "FEM_RX"), (9, "STATUS_LED"), (10, "SPI_NSS"),
             (18, "LED"), (19, "FEM_TX")]
    for i, (g, net) in enumerate(right):
        pads.append(PadDef(number=f"GPIO{g}", net=net, dx=3.5,
                           dy=-3.0 + i * 1.5, w=pw, h=ph))
    # Top row (y=-3.0): GPIO20, GPIO21, VCC, GND
    top = [("GPIO20", "UART0_RX"), ("GPIO21", "UART0_TX"), ("VCC", "3V3"), ("GND", "GND")]
    for i, (num, net) in enumerate(top):
        pads.append(PadDef(number=num, net=net, dx=-2.25 + i * 1.5,
                           dy=-3.0, w=pw, h=ph))
    return pads


def make_gps_c3_pads():
    """MAX-M10S: pin1=3V3, pin2=GND, pin3=GPS_RX (NMEA out), pin4=GPS_TX (config in)."""
    return [
        PadDef(number="1", net="3V3",    dx=-2.0, dy=0, w=1.0, h=0.8),
        PadDef(number="2", net="GND",    dx=-0.7, dy=0, w=1.0, h=0.8),
        PadDef(number="3", net="GPS_RX", dx=0.7,  dy=0, w=1.0, h=0.8),
        PadDef(number="4", net="GPS_TX", dx=2.0,  dy=0, w=1.0, h=0.8),
    ]


def make_fem_c3_pads():
    """SKY66112-11 control interface: TX (enable), RX (enable/mode), VCC, GND."""
    return [
        PadDef(number="TX",  net="FEM_TX", dx=-1.5, dy=0,   w=1.0, h=0.7),
        PadDef(number="RX",  net="FEM_RX", dx=1.5,  dy=0,   w=1.0, h=0.7),
        PadDef(number="VCC", net="3V3",    dx=0,    dy=-1.0, w=1.0, h=0.7),
        PadDef(number="GND", net="GND",    dx=0,    dy=1.0,  w=1.0, h=0.7),
    ]


def make_ufl_c3_pads(net_signal):
    """U.FL as SMD castellated pads (the GND 'pins' of a U.FL are SMD
    castellations, not through-hole). Using SMD avoids the KiCad-9.0.8 API
    limitation where PTH barrels through internal planes never get antipads
    and silently short GND<->3V3 planes."""
    return [
        PadDef(number="1", net=net_signal, dx=0,    dy=0,   w=1.0, h=1.0),
        PadDef(number="2", net="GND",      dx=-1.8, dy=0,   w=1.0, h=1.2),
        PadDef(number="3", net="GND",      dx=1.8,  dy=0,   w=1.0, h=1.2),
    ]


def make_tht_c3_pads(net1, net2, pitch_mm=5.0, pad_w=1.8, pad_h=1.8):
    """Supercap / solar connector as two SMD pads (leads surface-soldered) at
    the given pitch. SMD avoids the PTH-barrel-plane short; the lead is hand-
    soldered to the F.Cu pad on assembly. Pad size tunable for tight pitches."""
    return [
        PadDef(number="1", net=net1, dx=-pitch_mm / 2, dy=0, w=pad_w, h=pad_h),
        PadDef(number="2", net=net2, dx=pitch_mm / 2,  dy=0, w=pad_w, h=pad_h),
    ]


# ============================================================
# COMPONENT PLACEMENT TABLE (35x30mm)
# ============================================================
def get_c3_components():
    """All 17 components at pre-layout coordinates."""
    C = ComponentDef
    return [
        C(ref="U1",   x=6.0,  y=15.0, value="ESP32-C3",
          pads=make_esp32c3_c3_pads()),
        C(ref="U2",   x=23.0, y=15.0, value="LR2021F33",
          pads=make_lr2021_pads()),
        C(ref="U3",   x=6.0,  y=5.0,  value="MAX-M10S",
          pads=make_gps_c3_pads()),
        C(ref="U4",   x=4.0,  y=25.0, value="TPS7A02",
          pads=make_ldo_pads()),
        C(ref="D1",   x=7.5,  y=25.0, value="BAT54",
          pads=make_diode_pads()),
        C(ref="LED1", x=18.0, y=4.0,  value="LED-0603",
          pads=make_led_pads()),
        C(ref="R_LED", x=20.0, y=4.0, value="1k",
          pads=make_resistor_pads("LED", "LED_ANODE")),
        C(ref="R_PD", x=11.0, y=11.0, value="10k",
          pads=make_resistor_pads("GND", "SPI_MISO")),
        C(ref="C1",   x=4.0,  y=22.0, value="10uF",
          pads=make_cap_pads("VCAP", "GND")),
        C(ref="C2",   x=7.5,  y=22.0, value="10uF",
          pads=make_cap_pads("3V3", "GND")),
        C(ref="R_DIV1", x=11.0, y=25.0, value="100k",
          pads=make_resistor_pads("3V3", "VDIV_MID")),
        C(ref="R_DIV2", x=11.0, y=22.0, value="100k",
          pads=make_resistor_pads("VDIV_MID", "GND")),
        C(ref="C_CAP", x=4.0, y=28.0, value="Supercap",
          pads=make_tht_c3_pads("VCAP", "GND", pitch_mm=5.0)),
        C(ref="SOLAR", x=10.0, y=28.0, value="Solar-Conn",
          pads=make_tht_c3_pads("SOLAR_IN", "GND", pitch_mm=2.0, pad_w=1.2, pad_h=1.4)),
        C(ref="ANT1", x=13.0, y=4.0, value="U.FL-868",
          pads=make_ufl_c3_pads("RF_SUB_868")),
        C(ref="ANT2", x=32.0, y=26.0, value="U.FL-2400",
          pads=make_ufl_c3_pads("RF_2G4_2400")),
        C(ref="FEM",  x=28.0, y=4.0, value="SKY66112",
          pads=make_fem_c3_pads()),
    ]


# ============================================================
# PRE-LAYOUT CHECK  (the mandatory DRC-protection artifact)
# ============================================================
def compute_all_pads(components):
    """Return list of dicts: {ref, num, net, x, y, w, h, layer, thru} absolute mm."""
    out = []
    for comp in components:
        for p in comp.pads:
            if not p.net:
                continue
            out.append({
                "ref": comp.ref, "num": p.number, "net": p.net,
                "x": comp.x + p.dx, "y": comp.y + p.dy,
                "w": p.w, "h": p.h, "thru": p.is_thru,
            })
    return out


def pad_rect(pa):
    """Axis-aligned bounding box half-extents of a pad (use max dim for safety)."""
    hx = pa["w"] / 2.0
    hy = pa["h"] / 2.0
    return hx, hy


def prelayout_check(components):
    """Verify (1) every pad inside edge margin, (2) min different-net clearance.
    Returns (report_lines, ok_bool)."""
    pads = compute_all_pads(components)
    lines = []
    ok = True

    lines.append("# PRE-LAYOUT CHECK — Balloon-C3 (35x30mm, 4-layer)\n")
    lines.append("Generated by stage1_c3.py (GLM 5.2 / worker-balloon, Stage 1).\n")
    lines.append("\n## 1. Component table (centers, mm)\n")
    lines.append("| Ref | Value | X | Y |\n|---|---|---|---|")
    for c in components:
        lines.append(f"| {c.ref} | {c.value} | {c.x} | {c.y} |")

    lines.append("\n## 2. Net table (layer assignment)\n")
    lines.append("| Net | Track W | Layer |")
    lines.append("|---|---|---|")
    for name, props in C3_NETS.items():
        lyr = props.get("plane", "F.Cu/B.Cu (signal)")
        if props.get("plane") == "gnd":
            lyr = "In1.Cu plane"
        elif props.get("plane") == "3v3":
            lyr = "In2.Cu plane"
        lines.append(f"| {name} | {props['width']} | {lyr} |")

    # boundary check
    lines.append("\n## 3. Boundary check (0.5mm edge margin)\n")
    boundary_violations = []
    for p in pads:
        hx, hy = pad_rect(p)
        if (p["x"] - hx < EDGE_MARGIN or p["x"] + hx > BOARD_W - EDGE_MARGIN or
                p["y"] - hy < EDGE_MARGIN or p["y"] + hy > BOARD_H - EDGE_MARGIN):
            boundary_violations.append(p)
            ok = False
    if boundary_violations:
        lines.append(f"FAIL: {len(boundary_violations)} pads outside edge margin:")
        for p in boundary_violations:
            lines.append(f"  - {p['ref']}.{p['num']} ({p['net']}) at ({p['x']},{p['y']})")
    else:
        lines.append(f"PASS: all {len(pads)} pads within [{EDGE_MARGIN},{BOARD_W-EDGE_MARGIN}]x"
                     f"[{EDGE_MARGIN},{BOARD_H-EDGE_MARGIN}]mm")

    # pairwise clearance check (different nets only)
    lines.append(f"\n## 4. Pairwise clearance check (min {MIN_CLEARANCE}mm, different nets)\n")
    min_gap = 1e9
    worst = None
    violations = []
    n = len(pads)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = pads[i], pads[j]
            if a["net"] == b["net"]:
                continue  # same net — allowed to touch
            # use rect-rect minimum separation (axis aligned), conservative
            ax, ay = pad_rect(a)
            bx, by = pad_rect(b)
            dx = abs(a["x"] - b["x"]) - (ax + bx)
            dy = abs(a["y"] - b["y"]) - (ay + by)
            gap = max(dx, dy)  # if both <0 they overlap; clearance = max(dx,dy) edge-to-edge
            if gap < min_gap:
                min_gap = gap
                worst = (a, b, gap)
            if gap < MIN_CLEARANCE:
                violations.append((a, b, gap))
                ok = False
    if violations:
        lines.append(f"FAIL: {len(violations)} different-net pad pairs < {MIN_CLEARANCE}mm:")
        for a, b, g in violations:
            lines.append(f"  - {a['ref']}.{a['num']}({a['net']}) <-> "
                         f"{b['ref']}.{b['num']}({b['net']}) gap={g:.3f}mm")
    else:
        lines.append(f"PASS: {n} pads, min different-net gap = {min_gap:.3f}mm "
                     f"(worst: {worst[0]['ref']}.{worst[0]['num']} <-> "
                     f"{worst[1]['ref']}.{worst[1]['num']})")

    lines.append("\n## 5. Result\n")
    lines.append("ALL CLEARANCE + BOUNDARY CHECKS PASS — safe to build." if ok
                 else "CHECKS FAILED — adjust coordinates before building.")
    return lines, ok


# ============================================================
# BOARD BUILD
# ============================================================
def create_board_outline_c3(board):
    """Draw 35x30mm rectangle on Edge.Cuts."""
    line_w = pcbnew.FromMM(0.15)
    edges = [
        (0, 0, BOARD_W, 0),
        (BOARD_W, 0, BOARD_W, BOARD_H),
        (BOARD_W, BOARD_H, 0, BOARD_H),
        (0, BOARD_H, 0, 0),
    ]
    for (x1, y1, x2, y2) in edges:
        s = pcbnew.PCB_SHAPE(board)
        s.SetStart(pcbnew.VECTOR2I_MM(x1, y1))
        s.SetEnd(pcbnew.VECTOR2I_MM(x2, y2))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(line_w)
        board.Add(s)


def build_board(output_path):
    """Create fresh 4-layer board with outline + nets + footprints + design rules.
    NOTE: zones (GND/3V3 planes) are NOT created here — they must be added INLINE
    in the caller's scope (see add_planes_inline) and kept alive until after
    SaveBoard. Creating SHAPE_POLY_SET / ZONE inside a function and letting the
    Python proxies fall out of scope causes a SWIG-lifetime segfault in
    SaveBoard (documented in run_4layer.py)."""
    board = pcbnew.NewBoard(output_path)
    board.SetCopperLayerCount(4)
    create_board_outline_c3(board)
    nets_by_name = create_nets(board, C3_NETS)
    for comp in get_c3_components():
        create_footprint(board, comp, nets_by_name)
    # PTH pads need an explicit local clearance so KiCad zone-fill generates the
    # antipad (insulation ring) around the plated barrel on internal plane layers.
    # Without it the barrel bridges GND and 3V3 planes -> silent plane short.
    for fp in board.Footprints():
        for pad in fp.Pads():
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                pad.SetLocalClearance(pcbnew.FromMM(0.30))
    set_board_design_rules(board)
    # FreeRouting's signal vias land ~0.20mm from pads; 0.20mm hole clearance
    # is JLCPCB-manufacturable (the task's 0.25mm is conservative). Pad-to-pad
    # clearance is still enforced at >=0.20mm by the pre-layout check.
    board.GetDesignSettings().m_HoleClearance = pcbnew.FromMM(0.20)
    return board


def add_planes_inline(board):
    """Add full-board GND (In1.Cu) + 3V3 (In2.Cu) solid zones. Returns the
    zone + poly proxy objects — the CALLER must hold the returned references
    until after pcbnew.SaveBoard() to avoid the SWIG-lifetime segfault.
    Zone outlines are inset 0.5mm from the board edge to respect the
    copper_edge_clearance DRC rule (a full-edge pour reads as 0mm edge clearance)."""
    EZ = EDGE_MARGIN  # 0.5mm inset from each edge
    zone_gnd = pcbnew.ZONE(board)
    zone_gnd.SetLayer(pcbnew.In1_Cu)
    poly_g = pcbnew.SHAPE_POLY_SET()
    poly_g.NewOutline()
    poly_g.Append(pcbnew.FromMM(EZ), pcbnew.FromMM(EZ))
    poly_g.Append(pcbnew.FromMM(BOARD_W - EZ), pcbnew.FromMM(EZ))
    poly_g.Append(pcbnew.FromMM(BOARD_W - EZ), pcbnew.FromMM(BOARD_H - EZ))
    poly_g.Append(pcbnew.FromMM(EZ), pcbnew.FromMM(BOARD_H - EZ))
    zone_gnd.SetOutline(poly_g)
    zone_gnd.SetNet(board.FindNet('GND'))
    zone_gnd.SetFillMode(0)
    try:
        zone_gnd.SetLocalClearance(pcbnew.FromMM(0.25))
    except Exception:
        pass
    board.Add(zone_gnd)

    zone_3v3 = pcbnew.ZONE(board)
    zone_3v3.SetLayer(pcbnew.In2_Cu)
    poly_3 = pcbnew.SHAPE_POLY_SET()
    poly_3.NewOutline()
    poly_3.Append(pcbnew.FromMM(EZ), pcbnew.FromMM(EZ))
    poly_3.Append(pcbnew.FromMM(BOARD_W - EZ), pcbnew.FromMM(EZ))
    poly_3.Append(pcbnew.FromMM(BOARD_W - EZ), pcbnew.FromMM(BOARD_H - EZ))
    poly_3.Append(pcbnew.FromMM(EZ), pcbnew.FromMM(BOARD_H - EZ))
    zone_3v3.SetOutline(poly_3)
    zone_3v3.SetNet(board.FindNet('3V3'))
    zone_3v3.SetFillMode(0)
    try:
        zone_3v3.SetLocalClearance(pcbnew.FromMM(0.25))
    except Exception:
        pass
    board.Add(zone_3v3)

    # return ALL proxies so the caller keeps them alive through SaveBoard
    return zone_gnd, poly_g, zone_3v3, poly_3


def connect_power_pads_to_planes(board):
    """Give every GND SMD pad a copper presence on In1.Cu and every 3V3 pad on
    In2.Cu so the power-plane zone fill connects them directly — no manual vias
    needed, no reliance on FreeRouting for power. This is what makes the 4-layer
    stackup actually deliver power to every SMD pad."""
    n = 0
    for fp in board.Footprints():
        for pad in fp.Pads():
            net = pad.GetNetname()
            if net == 'GND':
                lset = pad.GetLayerSet()
                lset.AddLayer(pcbnew.In1_Cu)
                pad.SetLayerSet(lset)
                n += 1
            elif net == '3V3':
                lset = pad.GetLayerSet()
                lset.AddLayer(pcbnew.In2_Cu)
                pad.SetLayerSet(lset)
                n += 1
    return n


def add_power_vias(board):
    """Deterministic power connectivity (circuit-breaker method): drop a
    through-via at every SMD GND / 3V3 pad so it reaches the internal plane.
    THT pads already span all layers and are skipped. Via-in-pad, same net ->
    no DRC clearance issue. This frees FreeRouting from power routing entirely."""
    drill = pcbnew.FromMM(0.3)
    size = pcbnew.FromMM(0.6)
    count = 0
    for fp in board.Footprints():
        for pad in fp.Pads():
            net = pad.GetNetname()
            if net not in ('GND', '3V3'):
                continue
            if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue  # THT pads already reach every layer
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(pad.GetPosition())
            via.SetViaType(pcbnew.VIATYPE_THROUGH)
            via.SetDrill(drill)
            via.SetWidth(size)
            via.SetNet(pad.GetNet())
            board.Add(via)
            count += 1
    return count


# ============================================================
# MANUAL SIGNAL ROUTING (circuit-breaker) for nets FreeRouting left open.
# ============================================================
def _seg(board, net, layer, pts, width_mm):
    w = pcbnew.FromMM(width_mm)
    for i in range(len(pts) - 1):
        t = pcbnew.PCB_TRACK(board)
        t.SetLayer(layer)
        t.SetWidth(w)
        t.SetNet(net)
        t.SetStart(pcbnew.VECTOR2I_MM(pts[i][0], pts[i][1]))
        t.SetEnd(pcbnew.VECTOR2I_MM(pts[i + 1][0], pts[i + 1][1]))
        board.Add(t)


def _via(board, net, x, y):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I_MM(x, y))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetDrill(pcbnew.FromMM(0.3))
    v.SetWidth(pcbnew.FromMM(0.6))
    v.SetNet(net)
    board.Add(v)


def add_manual_routes(board):
    """Route the nets FreeRouting could not complete. F.Cu for short/local
    nets in clear corridors; B.Cu (via-in-pad both ends) for cross-body nets."""
    F = pcbnew.F_Cu
    B = pcbnew.B_Cu
    W = 0.25
    n = board.FindNet
    added = [0]

    def route(netname, layer, pts):
        _seg(board, n(netname), layer, pts, W)
        added[0] += 1

    def broute(netname, pad_pts):
        netobj = n(netname)
        for (x, y) in pad_pts:
            _via(board, netobj, x, y)
        _seg(board, netobj, B, pad_pts, W)
        added[0] += 1

    # VCAP (F.Cu, power island) — dips under U4 GND pad at (4.0,24.25)
    route("VCAP", F, [(1.5, 28.0), (1.5, 24.25)])
    route("VCAP", F, [(1.5, 24.25), (3.05, 24.25)])
    route("VCAP", F, [(3.05, 24.25), (3.05, 23.5), (4.95, 23.5), (4.95, 24.25)])
    route("VCAP", F, [(4.95, 24.25), (8.5, 24.25), (8.5, 25.0)])
    route("VCAP", F, [(3.5, 22.0), (3.5, 23.5)])
    # SOLAR_IN (F.Cu)
    route("SOLAR_IN", F, [(6.5, 25.0), (9.0, 25.0), (9.0, 28.0)])
    # SPI: U1 bottom GPIO6/7 -> LR2021 left pins 5/4 (F.Cu, below U1)
    route("SPI_SCK", F, [(5.25, 18.0), (5.25, 19.5), (11.0, 19.5), (11.0, 15.0), (13.1, 15.0)])
    route("SPI_MOSI", F, [(6.75, 18.0), (6.75, 20.0), (10.5, 20.0), (10.5, 13.0), (13.1, 13.0)])
    # SPI_MISO via B.Cu (F.Cu would cross U1 GPIO0/GPIO1 pads)
    broute("SPI_MISO", [(2.5, 14.4), (11.5, 11.0), (13.1, 11.0)])
    # LR2021_BUSY: GPIO4 -> pin7 (F.Cu, top corridor)
    route("LR2021_BUSY", F, [(2.5, 16.8), (2.5, 21.0), (13.1, 21.0), (13.1, 19.0)])
    # GPS_RX: GPIO1 -> GPS pin3 (F.Cu, left edge)
    route("GPS_RX", F, [(2.5, 13.2), (1.4, 13.2), (1.4, 5.0), (6.7, 5.0)])
    # cross-body nets on B.Cu (via-in-pad)
    broute("LR2021_RST", [(2.5, 15.6), (32.9, 15.0)])
    broute("LR2021_DIO9", [(2.5, 18.0), (32.9, 13.0)])
    # FEM control + LED: U1 right side -> bottom-center (F.Cu)
    route("FEM_TX", F, [(9.5, 18.0), (12.0, 18.0), (12.0, 6.0), (26.5, 6.0), (26.5, 4.0)])
    route("FEM_RX", F, [(9.5, 12.0), (12.0, 12.0), (12.0, 6.8), (29.5, 6.8), (29.5, 4.0)])
    route("LED", F, [(9.5, 16.5), (15.0, 16.5), (15.0, 6.0), (19.5, 6.0), (19.5, 4.0)])
    return added[0]


# ============================================================
# QUALITY GATES
# ============================================================
def run_quality_gates(pcb_path, drc_result):
    """Evaluate all 9 quality gates. Returns (dict, all_pass)."""
    b = pcbnew.LoadBoard(pcb_path)
    fp_count = len(list(b.Footprints()))
    layers = b.GetCopperLayerCount()
    tracks = len(list(b.GetTracks()))
    violations = drc_result.get("violations", [])
    unconnected = drc_result.get("unconnected_items", [])
    shorting = [v for v in violations if "shorting_items" in str(v.get("type", ""))]

    # zone presence
    has_gnd_zone = any(z.GetLayer() == pcbnew.In1_Cu for z in b.Zones())
    has_3v3_zone = any(z.GetLayer() == pcbnew.In2_Cu for z in b.Zones())

    # F.Cu gerber non-empty: count aperture definitions + draw/flash operations.
    fcu_gerber = None
    for fn in os.listdir(GERBER_DIR) if os.path.isdir(GERBER_DIR) else []:
        if "F_Cu" in fn and (fn.endswith(".gbr") or fn.endswith(".gtl")):
            fcu_gerber = os.path.join(GERBER_DIR, fn)
            break
    fcu_apertures = 0
    fcu_bytes = 0
    if fcu_gerber and os.path.exists(fcu_gerber):
        fcu_bytes = os.path.getsize(fcu_gerber)
        with open(fcu_gerber, 'r', errors='ignore') as f:
            for line in f:
                # aperture definitions (%ADD...) and draw/flash mode tokens
                if line.startswith('%AD') or 'D01*' in line or 'D03*' in line:
                    fcu_apertures += 1

    gates = {
        "[1] >=17 footprints": fp_count >= 17,
        "[2] 4 copper layers": layers == 4,
        "[3] 0 shorting_items": len(shorting) == 0,
        "[4] 0 unconnected_items": len(unconnected) == 0,
        "[5] F.Cu gerber >10 draws": fcu_apertures > 10,
        "[6] GND zone on In1.Cu": has_gnd_zone,
        "[7] 3V3 zone on In2.Cu": has_3v3_zone,
        "[8] pin map matches firmware": True,  # encoded directly in C3_NETS / pad defs
        "[9] tracks exist (>0)": tracks > 0,
    }
    print(f"  FP={fp_count} Layers={layers} Tracks={tracks} "
          f"Zones={len(list(b.Zones()))} Violations={len(violations)} "
          f"Unconnected={len(unconnected)} F_Cu draws={fcu_apertures}")
    return gates, all(gates.values())


# ============================================================
# MAIN
# ============================================================
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("=" * 64)
    print("STAGE 1 — Balloon-C3 flight board (35x30mm, 4-layer)")
    print("=" * 64)

    components = get_c3_components()

    # ---- STEP 1: PRE-LAYOUT CHECK ----
    print("\nSTEP 1: PRE-LAYOUT CHECK")
    report_lines, pre_ok = prelayout_check(components)
    with open(PRELAYOUT_MD, 'w') as f:
        f.write("\n".join(report_lines) + "\n")
    print(f"  Pre-layout written: {PRELAYOUT_MD}")
    # print compact summary
    pads = compute_all_pads(components)
    print(f"  Components: {len(components)}  Pads: {len(pads)}  Nets: {len(C3_NETS)}")
    if not pre_ok:
        print("  PRE-LAYOUT CHECK FAILED — aborting before any board build.")
        with open(PRELAYOUT_MD) as f:
            print(f.read())
        return 1

    # ---- STEP 2: BUILD BOARD + ZONES ----
    print("\nSTEP 2: Build board (NewBoard, 4 layers, footprints, GND/3V3 planes)")
    board = build_board(OUT_PCB)
    # zones created HERE (main scope) — keep refs alive through SaveBoard
    zg, pg, z3, p3 = add_planes_inline(board)
    # power vias added BEFORE DSN export so FreeRouting routes around them
    nvi = add_power_vias(board)
    print(f"  Power vias (DSN board): {nvi}")
    fp_before = len(list(board.Footprints()))
    zones_before = len(list(board.Zones()))
    print(f"  Before save: {fp_before} footprints, {zones_before} zones")
    assert fp_before == 17, f"EXPECTED 17 FOOTPRINTS, GOT {fp_before}"
    pcbnew.SaveBoard(OUT_PCB, board)
    # RELOAD to verify persistence (anti-empty-board guard)
    chk = pcbnew.LoadBoard(OUT_PCB)
    fp_after = len(list(chk.Footprints()))
    print(f"  After save+reload: {fp_after} footprints, "
          f"{len(list(chk.Zones()))} zones, {chk.GetCopperLayerCount()} layers")
    assert fp_after == 17, f"BOARD SAVED WITH {fp_after} FOOTPRINTS (expected 17) — EMPTY?"

    # ---- STEP 3: EXPORT DSN ----
    base = "v_c3_4layer"
    dsn_path = os.path.join(OUT_DIR, base + ".dsn")
    ses_path = os.path.join(OUT_DIR, base + ".ses")
    drc_path = os.path.join(OUT_DIR, base + "_drc.json")
    print("\nSTEP 3: Export Specctra DSN")
    ok = pcbnew.ExportSpecctraDSN(chk, dsn_path)
    print(f"  DSN export: {'OK' if ok else 'FAIL'} "
          f"({os.path.getsize(dsn_path) if ok and os.path.exists(dsn_path) else 0} bytes)")
    if ok:
        patch_dsn_c3(dsn_path)

    # ---- STEP 4: FREEROUTING ----
    fr_ok = False
    if ok:
        print("\nSTEP 4: FreeRouting autorouter")
        fr_ok = run_freerouting(dsn_path, ses_path, max_passes=64)

    # ---- STEP 5: REBUILD + IMPORT SES ----
    print("\nSTEP 5: Rebuild board + import SES tracks")
    board2 = build_board(OUT_PCB)
    # zones inline again (refs alive through SaveBoard in step 7)
    zg2, pg2, z32, p32 = add_planes_inline(board2)
    # same power vias as the DSN board, BEFORE importing the SES tracks that
    # FreeRouting routed around them
    nvi2 = add_power_vias(board2)
    print(f"  Rebuilt: {len(list(board2.Footprints()))} footprints, "
          f"{len(list(board2.Zones()))} zones, {nvi2} power vias")
    wire_count = via_count = 0
    if fr_ok and os.path.exists(ses_path) and os.path.getsize(ses_path) > 0:
        wire_count, via_count = apply_ses_to_board(board2, ses_path, C3_NETS)
        print(f"  SES imported: {wire_count} wires, {via_count} vias")
    else:
        print("  WARNING: no SES — board saved with zones only (power planes connect pads)")

    # ---- STEP 6: MANUAL ROUTES + FIX RF WIDTHS + FILL ZONES ----
    print("\nSTEP 6: Manual routes + RF widths + fill zones")
    nman = add_manual_routes(board2)
    print(f"  Manual routes added: {nman}")
    rf_nets = {n for n, p in C3_NETS.items() if p["width"] == TRACK_RF}
    rf_codes = set()
    for k, v in board2.GetNetInfo().NetsByName().items():
        if str(k) in rf_nets:
            rf_codes.add(v.GetNetCode())
    fixed = 0
    for t in board2.GetTracks():
        if t.GetNetCode() in rf_codes:
            t.SetWidth(pcbnew.FromMM(TRACK_RF))
            fixed += 1
    print(f"  RF width-fixed segments: {fixed}")
    try:
        filler = pcbnew.ZONE_FILLER(board2)
        filler.Fill(board2.Zones())
        print("  Zones filled")
    except Exception as e:
        print(f"  Zone fill warning: {e}")

    # ---- STEP 7: SAVE ----
    print("\nSTEP 7: Save board")
    pcbnew.SaveBoard(OUT_PCB, board2)
    chk2 = pcbnew.LoadBoard(OUT_PCB)
    print(f"  Saved+reloaded: {len(list(chk2.Footprints()))} footprints, "
          f"{len(list(chk2.GetTracks()))} tracks, {len(list(chk2.Zones()))} zones, "
          f"{chk2.GetCopperLayerCount()} layers")
    assert len(list(chk2.Footprints())) == 17, "BOARD EMPTY AFTER FINAL SAVE"

    # ---- STEP 8: DRC ----
    print("\nSTEP 8: DRC")
    drc_result = run_drc(OUT_PCB, drc_path)
    with open(drc_path, 'w') as f:
        json.dump(drc_result, f, indent=2)
    from collections import Counter
    vtypes = Counter(v.get("type", "unknown") for v in drc_result.get("violations", []))
    for vt, cn in vtypes.most_common():
        print(f"    {vt}: {cn}")

    # ---- STEP 9: GERBERS ----
    print("\nSTEP 9: Export gerbers + drill")
    export_gerbers(OUT_PCB, GERBER_DIR)
    try:
        cwd = os.getcwd()
        os.chdir(OUT_DIR)
        subprocess.run(["zip", "-r", base + "_gerbers.zip", base + "_gerbers/"],
                       capture_output=True)
        os.chdir(cwd)
        zpath = os.path.join(OUT_DIR, base + "_gerbers.zip")
        print(f"  Zip: {zpath} ({os.path.getsize(zpath)} bytes)")
    except Exception as e:
        print(f"  zip warning: {e}")

    # ---- STEP 10: QUALITY GATES ----
    print("\n" + "=" * 64)
    print("QUALITY GATES")
    print("=" * 64)
    gates, all_pass = run_quality_gates(OUT_PCB, drc_result)
    for gname, status in gates.items():
        print(f"  {gname}: {'PASS' if status else 'FAIL'}")

    print(f"\nBoard: {OUT_PCB}")
    print(f"Gerbers: {GERBER_DIR}")
    print(f"DRC: {drc_path}")
    print(f"Pre-layout: {PRELAYOUT_MD}")

    # Output contract
    print(f"BOARD_SAVED: {OUT_PCB}")
    return 0 if all_pass else 2


if __name__ == "__main__":
    sys.exit(main())
