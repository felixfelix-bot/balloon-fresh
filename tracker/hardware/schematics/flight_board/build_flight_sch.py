#!/usr/bin/env python3
"""Derive a loading KiCad 9 schematic for the C3 flight board FROM the frozen PCB.

Direction of truth: the placed/routed PCB (`output/v_c3_flight_4layer_placed.kicad_pcb`)
plus the tested firmware are authoritative; this generated schematic is a MIRROR of
that netlist, never the other way round.  Nothing here invents connectivity: every
net, every pin and every declared no-connect is read out of the PCB file.

Outputs (all regenerated deterministically from the PCB sha256 in the header):
  v_c3_flight.kicad_sch   the schematic
  sym-lib-table           library table so ERC resolves the embedded lib_symbols
  balloon_flight.kicad_sym  custom symbols (LR2021F33) as a real library
  balloon_flight.pretty   the PCB's own footprints, exported verbatim
  fp-lib-table            footprint library table so Footprint fields resolve

Run:  python3 build_flight_sch.py
"""
import hashlib
import itertools
import os
import re
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
PCB = os.path.join(REPO, "tracker", "hardware", "output",
                   "v_c3_flight_4layer_placed.kicad_pcb")
OUT_SCH = os.path.join(HERE, "v_c3_flight.kicad_sch")
OUT_LIBTABLE = os.path.join(HERE, "sym-lib-table")
OUT_FPLIB = os.path.join(HERE, "balloon_flight.pretty")
OUT_FPTABLE = os.path.join(HERE, "fp-lib-table")
OUT_CUSTOM_SYM = os.path.join(HERE, "balloon_flight.kicad_sym")
SYMDIR = "/usr/share/kicad/symbols"
FP_LIBNAME = "balloon_flight"

FROZEN_SHA256 = "f3cf0143e7deff991e9650643f1322945388fd135efbf5191f51520dcd6edaa6"

POWER_NETS = ("+3V3", "GND")

# footprint lib-id -> schematic symbol lib-id.  Identity where the KiCad v9
# libraries carry a symbol for the same part.
PART_MAP = {
    "Resistor_SMD:R_0402_1005Metric": "Device:R",
    "Capacitor_SMD:C_0402_1005Metric": "Device:C",
    "Capacitor_SMD:C_0603_1608Metric": "Device:C",
    "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm": "Device:C_Polarized",
    "Diode_SMD:D_SOD-123": "Device:D_Schottky",
    "LED_SMD:LED_0603_1608Metric": "Device:LED",
    "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical":
        "Connector_Generic:Conn_01x02",
    "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical":
        "Connector_Generic:Conn_01x04",
    "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical":
        "Connector_Generic:Conn_01x06",
    "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical":
        "Connector:Conn_Coaxial",
    "RF_Module:ESP32-C3-WROOM-02": "RF_Module:ESP32-C3-WROOM-02",
    "RF_Module:HOPERF_RFM9XW_SMD": "balloon_flight:LR2021F33",
    "RF_GPS:ublox_MAX": "RF_GPS:MAX-M10S",
    "Package_TO_SOT_SMD:SOT-23-5": "Regulator_Linear:TPS7A0533PDBV",
    "Package_LGA:Bosch_LGA-8_2.5x2.5mm_P0.65mm_ClockwisePinNumbering":
        "Sensor:BME280",
}

# Custom inline symbol: the LR2021F33 module as the board actually wires it.
# The board uses the 16-pad HOPERF RFM9xW footprint; pad names below follow the
# RFM9xW reference pinout cited in PCB-S0-NETLIST-AUDIT.md, NOT the 18-pin
# castellated map in the NiceRF datasheet (that mismatch is an open question).
LR2021_PINS = [
    ("1", "GND"), ("2", "MISO"), ("3", "MOSI"), ("4", "SCK"),
    ("5", "NSS"), ("6", "RESET"), ("7", "IO7"), ("8", "GND"),
    ("9", "ANT"), ("10", "GND"), ("11", "GND_TAB11"), ("12", "BUSY"),
    ("13", "VCC"), ("14", "DIO0"), ("15", "IO15"), ("16", "GND_TAB16"),
]

# Pads declared deliberately unconnected (INTENTIONAL rows of the audit).
INTENTIONAL_NC = {
    ("J1", "6"), ("U3", "4"), ("U3", "5"), ("U3", "13"),
    ("U3", "14"), ("U3", "16"), ("U3", "17"),
}
# Pads in the audit whose GAP verdict is still open (PCB-S0b owns the ruling).
DECLARED_GAP = {
    ("U2", "7"): "unmodelled RF module I/O",
    ("U2", "11"): "probable GND tab left floating",
    ("U2", "15"): "unmodelled RF module I/O",
    ("U2", "16"): "probable GND tab left floating",
    ("U3", "6"): "V_BCKP power_in, nothing drives it",
    ("U3", "9"): "~RESET floating",
    ("U3", "11"): "RF_IN, no GPS antenna feed on this board",
    ("U3", "15"): "VIO_SEL floating",
    ("U3", "18"): "~SAFEBOOT floating",
    ("U4", "3"): "EN floating, rail never explicitly enabled",
    ("U4", "4"): "OUT/NC contradiction between in-repo sources",
}

# Functional column layout: (column index, ordered refs)
COLUMNS = [
    ["SOLAR", "D1", "C_CAP", "U4", "C1", "C3", "R_DIV1", "R_DIV2"],
    ["U1", "C2", "C4", "R_PD", "R_LED", "LED1"],
    ["U2", "ANT1"],
    ["U3"],
    ["U5", "J1", "J2"],
]
COLUMN_TITLES = [
    "SOLAR INPUT / SUPERCAP / 3V3 LDO",
    "ESP32-C3-WROOM-02 + SUPPORT",
    "LR2021F33 RADIO (16-pad footprint)",
    "MAX-M10S GNSS",
    "BME280 + PROGRAMMING / DEBUG HEADERS",
]


# ---------------------------------------------------------------- helpers
# DETERMINISTIC uuids.  The .kicad_sch is a build product: regenerating it from
# the same PCB must be byte-identical, otherwise the recorded sha256 is not
# provenance and every re-run churns the diff.  uuid5 over a fixed namespace
# plus a per-run sequence is stable because the generator walks the board file
# in file order (no sets, no dicts built from unordered input).
UID_NAMESPACE = uuid.UUID("b4a1c0de-0000-5000-a000-f1a5b0a1d0e0")
_uid_seq = itertools.count(1)


def uid():
    return str(uuid.uuid5(UID_NAMESPACE, "flight-sch-%06d" % next(_uid_seq)))


def fmt(v):
    s = "%.4f" % round(float(v) + 0.0, 4)
    s = s.rstrip("0").rstrip(".")
    return s if s and s != "-0" else "0"


def clean(text):
    """Kill float repr noise before it reaches KiCad's parser."""
    return re.sub(r"-?\d+\.\d{5,}", lambda m: fmt(float(m.group(0))), text)


def blocks_by_prefix(text, prefix):
    """Every balanced block in `text` whose first chars are `prefix`."""
    i = 0
    while True:
        i = text.find(prefix, i)
        if i < 0:
            return
        d = 0
        j = i
        while j < len(text):
            if text[j] == "(":
                d += 1
            elif text[j] == ")":
                d -= 1
                if d == 0:
                    yield text[i:j + 1]
                    break
            j += 1
        i = j + 1


def parse_pcb(path):
    text = open(path).read()
    footprints = []
    for blk in blocks_by_prefix(text, "\t(footprint "):
        fpid = re.search(r'\(footprint "([^"]+)"', blk).group(1)
        if ":" not in fpid:
            fpid = ":" + fpid
        ref = re.search(r'\(property "Reference" "([^"]*)"', blk).group(1)
        value = re.search(r'\(property "Value" "([^"]*)"', blk).group(1)
        at = re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)', blk)
        pads = []
        for pb in blocks_by_prefix(blk, "\t\t(pad "):
            num = re.search(r'\(pad "([^"]*)"', pb).group(1)
            nm = re.search(r'\(net \d+ "([^"]*)"\)', pb)
            npth = "np_thru_hole" in pb
            pads.append(dict(num=num, net=(nm.group(1) if nm else ""),
                             npth=npth))
        footprints.append(dict(ref=ref, value=value, fpid=fpid,
                               leaf=fpid.split(":", 1)[-1], raw=blk,
                               at=(float(at.group(1)), float(at.group(2))),
                               pads=pads))
    return footprints


def raw_symbol(lib, name):
    path = os.path.join(SYMDIR, lib + ".kicad_sym")
    text = open(path, errors="replace").read()
    head = '(symbol "%s"\n' % name
    i = text.find(head)
    if i < 0:
        raise KeyError("symbol %s:%s not in KiCad v9 libraries" % (lib, name))
    d = 0
    j = i
    while j < len(text):
        if text[j] == "(":
            d += 1
        elif text[j] == ")":
            d -= 1
            if d == 0:
                break
        j += 1
    return text[i:j + 1]


def load_lib_symbol(lib, name):
    """Raw block, with `(extends PARENT)` flattened and renamed to LIB:NAME.

    Many KiCad v9 parts (e.g. TPS7A0533PDBV) are *derived* symbols that carry no
    pins of their own - the pin table lives in the parent.  A schematic's
    lib_symbols cache cannot express `extends`, so the parent's drawing/pin
    sub-symbols are inlined here.
    """
    block = raw_symbol(lib, name)
    m = re.search(r'\n[ \t]*\(extends "([^"]+)"\)', block)
    if m:
        parent = m.group(1)
        praw = raw_symbol(lib, parent)
        kids = list(blocks_by_prefix(praw, '\t\t(symbol "'))
        if not kids:
            raise KeyError("%s extends %s but the parent has no unit symbols"
                           % (name, parent))
        inj = "\n".join(k.replace('(symbol "%s_' % parent,
                                 '(symbol "%s_' % name, 1) for k in kids)
        block = block.replace(m.group(0), "\n" + inj)
    head = '(symbol "%s"' % name
    if not block.startswith(head):
        raise KeyError("unexpected symbol head for %s:%s" % (lib, name))
    return '(symbol "%s:%s"' % (lib, name) + block[len(head):]


PIN_RE = re.compile(
    r'\(pin\s+(\S+)\s+\S+\s+\(at\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\)'
    r'\s*\(length\s+([-\d.]+)\)[\s\S]*?\(number\s+"([^"]+)"')


def symbol_pins(block):
    """{'1': {'x':0.0,'y':3.81,'a':270.0,'len':1.27,'type':'passive'}}"""
    out = {}
    for m in PIN_RE.finditer(block):
        out[m.group(6)] = dict(type=m.group(1), x=float(m.group(2)),
                               y=float(m.group(3)), a=float(m.group(4)),
                               length=float(m.group(5)))
    return out


def symbol_extent(block):
    """Rough lib-coord bbox from pins + rectangles, as (x0,y0,x1,y1)."""
    xs, ys = [], []
    for m in re.finditer(r'\(rectangle\s*\(start\s+([-\d.]+)\s+([-\d.]+)\)'
                         r'\s*\(end\s+([-\d.]+)\s+([-\d.]+)\)', block):
        xs += [float(m.group(1)), float(m.group(3))]
        ys += [float(m.group(2)), float(m.group(4))]
    for p in symbol_pins(block).values():
        xs.append(p["x"])
        ys.append(p["y"])
    if not xs:
        return (-5.0, -5.0, 5.0, 5.0)
    return (min(xs), min(ys), max(xs), max(ys))


DIR = {0.0: (1, 0), 90.0: (0, 1), 180.0: (-1, 0), 270.0: (0, -1)}


def pin_point(sym_x, sym_y, pin):
    """Absolute schematic coordinate of a pin's connection end (rot = 0)."""
    return (sym_x + pin["x"], sym_y - pin["y"])


def stub_end(sym_x, sym_y, pin, length):
    """Wire out of the pin, away from the symbol body, on the 1.27 grid."""
    ox, oy = DIR[pin["a"] % 360.0]
    px, py = pin_point(sym_x, sym_y, pin)
    return (px - ox * length, py + oy * length)


# ---------------------------------------------------------------- LR2021 custom symbol
def lr2021_symbol():
    body = []
    body.append('(symbol "balloon_flight:LR2021F33"')
    body.append("\t\t(pin_names\n\t\t\t(offset 1.016)\n\t\t\t(hide no)\n\t\t)")
    body.append("\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)")
    body.append('\t\t(property "Reference" "U"\n\t\t\t(at 0 16.51 0)\n'
                "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
                "\t\t\t\t)\n\t\t\t)\n\t\t)")
    body.append('\t\t(property "Value" "LR2021F33"\n\t\t\t(at 0 -16.51 0)\n'
                "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
                "\t\t\t\t)\n\t\t\t)\n\t\t)")
    body.append('\t\t(property "Footprint" "RF_Module:HOPERF_RFM9XW_SMD"\n'
                "\t\t\t(at 0 0 0)\n\t\t\t(effects\n\t\t\t\t(font\n"
                "\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(hide yes)\n"
                "\t\t\t)\n\t\t)")
    ds = ("https://www.nicerf.com/pdf/lora2021f33-2g4-2w-high-power-high-speed-"
          "multi-band-lr2021-wireless-communication-module-v1.1.pdf")
    body.append('\t\t(property "Datasheet" "%s"\n\t\t\t(at 0 0 0)\n'
                "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
                "\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)" % ds)
    body.append('\t\t(property "Description" "NiceRF LoRa2021F33-2G4 LR2021 '
                'module, 16-pad RFM9xW-style footprint"\n\t\t\t(at 0 0 0)\n'
                "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
                "\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)")
    body.append('\t\t(symbol "LR2021F33_0_1"\n\t\t\t(rectangle\n'
                "\t\t\t\t(start -11.43 12.7)\n\t\t\t\t(end 11.43 -12.7)\n"
                "\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n"
                "\t\t\t\t\t(type default)\n\t\t\t\t)\n"
                "\t\t\t\t(fill\n\t\t\t\t\t(type background)\n\t\t\t\t)\n"
                "\t\t\t)\n\t\t)")
    pins = []
    for idx, (num, name) in enumerate(LR2021_PINS):
        if idx < 8:
            x, y, ang = -13.97, 8.89 - idx * 2.54, 0
        else:
            x, y, ang = 13.97, -8.89 + (idx - 8) * 2.54, 180
        pins.append(
            "\t\t\t(pin passive line\n\t\t\t\t(at %s %s %s)\n"
            "\t\t\t\t(length 2.54)\n\t\t\t\t(name \"%s\"\n\t\t\t\t\t(effects\n"
            "\t\t\t\t\t\t(font\n\t\t\t\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t\t\t\t)\n\t\t\t\t\t)\n\t\t\t\t)\n"
            "\t\t\t\t(number \"%s\"\n\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n"
            "\t\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t\t)\n\t\t\t\t\t)\n"
            "\t\t\t\t)\n\t\t\t)"
            % (fmt(x), fmt(y), fmt(ang), name, num))
    body.append('\t\t(symbol "LR2021F33_1_1"\n' + "\n".join(pins) + "\n\t\t)")
    body.append("\t)")
    return "\n".join(body)


# ---------------------------------------------------------------- PCB parsing
def resolve_symbol(fpid):
    if fpid in PART_MAP:
        return PART_MAP[fpid]
    leaf = fpid.split(":")[-1]
    for k, v in PART_MAP.items():
        if k.split(":")[-1] == leaf:
            return v
    raise KeyError("no symbol mapping for footprint %s (add to PART_MAP)" % fpid)


# ---------------------------------------------------------------- emit
def emit(footprints):
    lib_ids_used = []
    sym_defs = ["\t\t" + lr2021_symbol().replace("\n", "\n")]
    lib_blocks = {"balloon_flight:LR2021F33": lr2021_symbol()}
    resolved = []
    for fp in footprints:
        lib_id = resolve_symbol(fp["fpid"])
        if lib_id in lib_blocks:
            block = lib_blocks[lib_id]
            raw = None
        else:
            lib, name = lib_id.split(":")
            block = load_lib_symbol(lib, name)
            lib_blocks[lib_id] = block
        resolved.append(dict(fp=fp, lib_id=lib_id, block=block))
        if lib_id not in lib_ids_used:
            lib_ids_used.append(lib_id)

    # ---- validation: every numbered pad must have a pin in the symbol
    problems = []
    for r in resolved:
        pins = symbol_pins(r["block"])
        padnums = sorted({p["num"] for p in r["fp"]["pads"] if p["num"] != ""})
        missing = [n for n in padnums if n not in pins]
        if missing:
            problems.append("%s (%s -> %s): pads %s have no symbol pin"
                            % (r["fp"]["ref"], r["fp"]["fpid"], r["lib_id"], missing))
    if problems:
        print("PIN COVERAGE FAILURES:")
        for p in problems:
            print("  -", p)
        sys.exit(2)

    # ---- footprint library: the PCB's own footprints, exported verbatim, so the
    # schematic Footprint fields resolve (ERC footprint_link_issues = 0)
    os.makedirs(OUT_FPLIB, exist_ok=True)
    written = set()
    for r in resolved:
        leaf = r["fp"]["leaf"]
        if leaf in written:
            continue
        written.add(leaf)
        blk = re.sub(r'\(footprint\s+"[^"]*"',
                     '(footprint "%s"\n\t\t(version 20241229)\n'
                     '\t\t(generator "pcbnew")\n\t\t(generator_version "9.0")'
                     % leaf, r["fp"]["raw"], count=1)
        with open(os.path.join(OUT_FPLIB, leaf + ".kicad_mod"), "w") as fh:
            fh.write(clean(blk) + "\n")
    with open(OUT_FPTABLE, "w") as fh:
        fh.write('(fp_lib_table\n\t(version 7)\n\t(lib (name "%s")'
                 '(type "KiCad")(uri "${KIPRJMOD}/%s.pretty")(options "")'
                 '(descr "Flight board footprints exported from the frozen PCB"))'
                 '\n)\n' % (FP_LIBNAME, FP_LIBNAME))

    # ---- layout
    by_ref = {r["fp"]["ref"]: r for r in resolved}
    unknown = [c for col in COLUMNS for c in col if c not in by_ref]
    if unknown:
        sys.exit("layout lists unknown refs: %s" % unknown)
    placed_refs = {c for col in COLUMNS for c in col}
    extra = [r["fp"]["ref"] for r in resolved if r["fp"]["ref"] not in placed_refs]
    if extra:
        sys.exit("PCB footprints missing from COLUMNS layout: %s" % extra)

    sizes = {}
    for ref, r in by_ref.items():
        x0, y0, x1, y1 = symbol_extent(r["block"])
        sizes[ref] = (x1 - x0, y1 - y0)

    col_x, x = [], 25.4
    for col in COLUMNS:
        w = max(sizes[ref][0] for ref in col)
        col_x.append(x)
        x += w + 22.86

    pos = {}
    for ci, col in enumerate(COLUMNS):
        y = 45.72
        for ref in col:
            _, h = sizes[ref]
            pos[ref] = (round(col_x[ci] / 1.27) * 1.27, round(y / 1.27) * 1.27)
            y += h + 20.32

    # ---- body
    body, notes = [], []
    body.append('\t(text "BALLOON C3 FLIGHT BOARD - netlist mirror of '
                'v_c3_flight_4layer_placed.kicad_pcb"\n\t\t(exclude_from_sim no)\n'
                '\t\t(at 25.4 25.4 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t'
                '(size 2.54 2.54)\n\t\t\t)\n\t\t\t(justify left bottom)\n'
                '\t\t)\n\t\t(uuid "%s")\n\t)' % uid())
    body.append('\t(text "PCB sha256 %s - schematic is DERIVED, the PCB is the '
                'source of truth (ADR-028)"\n\t\t(exclude_from_sim no)\n'
                '\t\t(at 25.4 30.48 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t'
                '(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify left bottom)\n'
                '\t\t)\n\t\t(uuid "%s")\n\t)' % (FROZEN_SHA256[:16] + "...", uid()))
    for ci, title in enumerate(COLUMN_TITLES):
        body.append('\t(text "%s"\n\t\t(exclude_from_sim no)\n'
                    '\t\t(at %s 38.1 0)\n\t\t(effects\n\t\t\t(font\n'
                    '\t\t\t\t(size 1.524 1.524)\n\t\t\t)\n'
                    '\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)'
                    % (title, fmt(round(col_x[ci] / 1.27) * 1.27), uid()))

    power_syms, wires, labels, ncs, flags = [], [], [], [], []
    stats = dict(pins=0, nets=set(), labels=0, power=0, nc=0, gap=0, unnamed=0)

    for r in resolved:
        ref, fp, lib_id = r["fp"]["ref"], r["fp"], None
        lib_id = r["lib_id"]
        sx, sy = pos[ref]
        pins = symbol_pins(r["block"])
        padnums = sorted({p["num"] for p in fp["pads"] if p["num"] != ""},
                         key=lambda s: (len(s), s))
        pin_txt = "".join('\t\t(pin "%s"\n\t\t\t(uuid "%s")\n\t\t)\n' % (n, uid())
                          for n in padnums)
        body.append(
            "\t(symbol\n\t\t(lib_id \"%s\")\n\t\t(at %s %s 0)\n\t\t(unit 1)\n"
            "\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n"
            "\t\t(dnp no)\n\t\t(uuid \"%s\")\n"
            "\t\t(property \"Reference\" \"%s\"\n\t\t\t(at %s %s 0)\n"
            "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t\t)\n\t\t\t\t(justify left)\n\t\t\t)\n\t\t)\n"
            "\t\t(property \"Value\" \"%s\"\n\t\t\t(at %s %s 0)\n"
            "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t\t)\n\t\t\t\t(justify left)\n\t\t\t)\n\t\t)\n"
            "\t\t(property \"Footprint\" \"%s\"\n\t\t\t(at %s %s 0)\n"
            "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n"
            "%s\t\t(instances\n\t\t\t(project \"v_c3_flight\"\n"
            "\t\t\t\t(path \"/%s\"\n\t\t\t\t\t(reference \"%s\")\n"
            "\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n"
            % (lib_id, fmt(sx), fmt(sy), uid(), ref, fmt(sx + 2.54),
               fmt(sy - 6.35), fp["value"], fmt(sx + 2.54), fmt(sy + 2.54),
               "%s:%s" % (FP_LIBNAME, fp["leaf"]), fmt(sx), fmt(sy),
               pin_txt, uid(), ref))

        # netless-pad handling, keyed on the audit verdicts
        for pad in fp["pads"]:
            if pad["num"] == "":
                stats["unnamed"] += 1
                continue
            pin = pins[pad["num"]]
            px, py = pin_point(sx, sy, pin)
            stats["pins"] += 1
            key = (ref, pad["num"])
            if pad["net"] == "":
                ncs.append((px, py))
                stats["nc"] += 1
                if key in DECLARED_GAP:
                    stats["gap"] += 1
                    notes.append((px, py, "GAP %s.%s: %s"
                                  % (ref, pad["num"], DECLARED_GAP[key])))
                elif key not in INTENTIONAL_NC:
                    notes.append((px, py, "NETLESS %s.%s: unclassified"
                                  % (ref, pad["num"])))
                continue
            stats["nets"].add(pad["net"])
            ex, ey = stub_end(sx, sy, pin, 5.08)
            wires.append((px, py, ex, ey))
            if pad["net"] in POWER_NETS:
                power_syms.append((pad["net"], ex, ey))
                stats["power"] += 1
            else:
                labels.append((pad["net"], ex, ey))
                stats["labels"] += 1

    # ---- PWR_FLAG: rails fed only by connectors/passives need a driver
    flag_pts = {}
    for (net, x, y) in power_syms:
        flag_pts.setdefault(net, (x, y))
    for (net, x, y) in labels:
        flag_pts.setdefault(net, (x, y))
    flag_nets = {n for (n, _, _) in power_syms}
    for r in resolved:
        if r["fp"]["ref"] != "U4":
            continue
        for p in r["fp"]["pads"]:
            if p["num"] == "1" and p["net"]:
                flag_nets.add(p["net"])
    # a rail already driven by a real power-output pin needs no PWR_FLAG
    driven = set()
    for r in resolved:
        rpins = symbol_pins(r["block"])
        for p in r["fp"]["pads"]:
            if (p["num"] and p["net"]
                    and rpins.get(p["num"], {}).get("type") == "power_out"):
                driven.add(p["net"])
    flag_nets -= driven
    for net in sorted(flag_nets):
        if net not in flag_pts:
            continue
        x, y = flag_pts[net]
        wires.append((x, y, x + 5.08, y))
        flags.append((net, x + 5.08, y))

    for (x1, y1, x2, y2) in wires:
        body.append('\t(wire\n\t\t(pts\n\t\t\t(xy %s %s) (xy %s %s)\n\t\t)\n'
                    '\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n'
                    '\t\t(uuid "%s")\n\t)\n'
                    % (fmt(x1), fmt(y1), fmt(x2), fmt(y2), uid()))
    for (txt, x, y) in labels:
        body.append('\t(label "%s"\n\t\t(at %s %s 0)\n\t\t(effects\n'
                    '\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
                    '\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)\n'
                    % (txt, fmt(x), fmt(y), uid()))
    for i, (net, x, y) in enumerate(power_syms):
        pref = "#PWR0%03d" % (i + 1)
        body.append(('\t(symbol\n\t\t(lib_id "power:%s")\n\t\t(at %s %s 0)\n'
                    '\t\t(unit 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n'
                    '\t\t(on_board yes)\n\t\t(dnp no)\n\t\t(uuid "%s")\n'
                    '\t\t(property "Reference" "#PWR"\n\t\t\t(at %s %s 0)\n'
                    '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
                    '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'
                    '\t\t(property "Value" "%s"\n\t\t\t(at %s %s 0)\n'
                    '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
                    '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'
                    '\t\t(property "Footprint" ""\n\t\t\t(at %s %s 0)\n'
                    '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
                    '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'
                    '\t\t(pin "1"\n\t\t\t(uuid "%s")\n\t\t)\n'
                    '\t\t(instances\n\t\t\t(project "v_c3_flight"\n'
                    '\t\t\t\t(path "/%s"\n\t\t\t\t\t(reference "#PWR")\n'
                    '\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n'
                    % (net, fmt(x), fmt(y), uid(), fmt(x + 2.54), fmt(y + 2.54),
                       net, fmt(x + 2.54), fmt(y - 2.54), fmt(x), fmt(y),
                       uid(), uid())).replace('#PWR', pref))
    for i, (net, x, y) in enumerate(flags):
        body.append('\t(symbol\n\t\t(lib_id "power:PWR_FLAG")\n\t\t(at %s %s 0)\n'
                    '\t\t(unit 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n'
                    '\t\t(on_board yes)\n\t\t(dnp no)\n\t\t(uuid "%s")\n'
                    '\t\t(property "Reference" "#FLG0%d"\n\t\t\t(at %s %s 0)\n'
                    '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
                    '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'
                    '\t\t(property "Value" "PWR_FLAG"\n\t\t\t(at %s %s 0)\n'
                    '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
                    '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'
                    '\t\t(property "Footprint" ""\n\t\t\t(at %s %s 0)\n'
                    '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
                    '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'
                    '\t\t(pin "1"\n\t\t\t(uuid "%s")\n\t\t)\n'
                    '\t\t(instances\n\t\t\t(project "v_c3_flight"\n'
                    '\t\t\t\t(path "/%s"\n\t\t\t\t\t(reference "#FLG0%d")\n'
                    '\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n'
                    % (fmt(x), fmt(y), uid(), i + 1, fmt(x + 2.54), fmt(y + 2.54),
                       fmt(x + 2.54), fmt(y - 2.54), fmt(x), fmt(y), uid(),
                       uid(), i + 1))
    for (x, y) in ncs:
        body.append('\t(no_connect\n\t\t(at %s %s)\n\t\t(uuid "%s")\n\t)\n'
                    % (fmt(x), fmt(y), uid()))

    # gap / netless annotations: honest, visible, cites the audit
    seen_notes = set()
    for (x, y, txt) in notes:
        if txt in seen_notes:
            continue
        seen_notes.add(txt)
        body.append('\t(text "%s"\n\t\t(exclude_from_sim no)\n'
                    '\t\t(at %s %s 0)\n\t\t(effects\n\t\t\t(font\n'
                    '\t\t\t\t(size 1.016 1.016)\n\t\t\t)\n'
                    '\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)\n'
                    % (txt, fmt(x + 1.27), fmt(y), uid()))

    # power symbols come from the power library; make sure the defs exist
    for net in sorted({n for (n, _, _) in power_syms}):
        lib, name = "power", net
        if "power:" + net not in lib_blocks:
            block = load_lib_symbol(lib, name)
            lib_blocks["power:" + net] = block
    if flags and "power:PWR_FLAG" not in lib_blocks:
        lib_blocks["power:PWR_FLAG"] = load_lib_symbol("power", "PWR_FLAG")
    libdefs = "\n".join(lib_blocks[k] for k in lib_blocks)

    sch = ('(kicad_sch\n\t(version 20250114)\n\t(generator "eeschema")\n'
           '\t(generator_version "9.0")\n\t(uuid "%s")\n\t(paper "A2")\n'
           '\t(title_block\n\t\t(title "Balloon C3 Flight Board")\n'
           '\t\t(date "2026-09-17")\n\t\t(rev "v0-derived")\n'
           '\t\t(company "Balloon Relay")\n'
           '\t\t(comment 1 "DERIVED artifact: mirrors the frozen PCB netlist; '
           'PCB is the source of truth (ADR-028)")\n\t)\n'
           '\t(lib_symbols\n%s\n\t)\n%s'
           '\t(sheet_instances\n\t\t(path "/"\n\t\t\t(page "1")\n\t\t)\n\t)\n)\n'
           % (uid(), libdefs, "".join(body)))

    with open(OUT_SCH, "w") as fh:
        fh.write(clean(sch))

    # standalone symbol library for the custom parts (sym-lib-table resolves it)
    with open(OUT_CUSTOM_SYM, "w") as fh:
        fh.write('(kicad_symbol_lib\n\t(version 20241209)\n'
                 '\t(generator "kicad_symbol_editor")\n'
                 '\t(generator_version "9.0")\n')
        for k, blk in lib_blocks.items():
            if k.startswith(FP_LIBNAME + ":"):
                fh.write("\t" + blk.replace('(symbol "%s:' % FP_LIBNAME,
                                             '(symbol "', 1) + "\n")
        fh.write(")\n")

    libs = sorted({k.split(":")[0] for k in lib_blocks})
    with open(OUT_LIBTABLE, "w") as fh:
        fh.write('(sym_lib_table\n\t(version 7)\n')
        for lib in libs:
            uri = (os.path.join(SYMDIR, lib + ".kicad_sym") if lib != "balloon_flight"
                   else "${KIPRJMOD}/balloon_flight.kicad_sym")
            fh.write('\t(lib (name "%s")(type "KiCad")(uri "%s")(options "")'
                     '(descr ""))\n' % (lib, uri))
        fh.write(")\n")

    stats["flags"] = len(flags)
    return stats, resolved


def main():
    sha = hashlib.sha256(open(PCB, "rb").read()).hexdigest()
    print("PCB           :", PCB)
    print("PCB sha256    :", sha)
    print("frozen sha256 :", FROZEN_SHA256)
    print("sha match     :", sha == FROZEN_SHA256)
    if sha != FROZEN_SHA256:
        sys.exit("FROZEN_PCB_SHA_MISMATCH: %s != %s - the schematic mirrors a "
                 "DIFFERENT board; re-freeze and update FROZEN_SHA256 first"
                 % (sha, FROZEN_SHA256))
    fps = parse_pcb(PCB)
    print("footprints    :", len(fps))
    stats, resolved = emit(fps)
    print("symbols placed:", len(resolved))
    print("PCB pads (num):", stats["pins"])
    print("unnamed pads  :", stats["unnamed"], "(mechanical, cannot be netted)")
    print("no_connect    :", stats["nc"], "of which declared GAP:", stats["gap"])
    print("non-power fins:", stats["labels"])
    print("power pins    :", stats["power"])
    print("pwr_flags     :", stats["flags"])
    print("distinct nets :", len(stats["nets"]), sorted(stats["nets"]))
    print("wrote         :", OUT_SCH, OUT_LIBTABLE)


if __name__ == "__main__":
    main()
