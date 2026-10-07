#!/usr/bin/env python3
"""Derive a loading KiCad 9 schematic for the C3 flight board FROM the frozen PCB.

Direction of truth: the placed/routed PCB (`output/v8i_krt_gnss.kicad_pcb`)
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
                   "v8i_krt_gnss.kicad_pcb")
OUT_SCH = os.path.join(HERE, "v_c3_flight.kicad_sch")
OUT_LIBTABLE = os.path.join(HERE, "sym-lib-table")
OUT_FPLIB = os.path.join(HERE, "balloon_flight.pretty")
OUT_FPTABLE = os.path.join(HERE, "fp-lib-table")
OUT_CUSTOM_SYM = os.path.join(HERE, "balloon_flight.kicad_sym")
SYMDIR = "/usr/share/kicad/symbols"
FP_LIBNAME = "balloon_flight"

FROZEN_SHA256 = "638de56387721460100cd3048fb23229294f510f0a2d89795026c7e6c0cfd0ea"

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
    "custom:LoRa2021_Castellated": "balloon_flight:LR2021F33",
    "MountingHole:MountingHole_2.2mm_M2": "Mechanical:MountingHole",
    "RF_GPS:ublox_MAX": "RF_GPS:MAX-M10S",
    "Package_TO_SOT_SMD:SOT-23-5": "Regulator_Linear:TPS7A0533PDBV",
    "Package_LGA:Bosch_LGA-8_2.5x2.5mm_P0.65mm_ClockwisePinNumbering":
        "Sensor:BME280",
    "Package_LGA:LGA-8_3x5mm_P1.25mm":
        "Sensor:BME280",
}

# Barometer: design intent is MS5611-01BA (10-1200 hPa) for the stratospheric flight
# profile. The frozen S0 placement PCB still labels this footprint as BMP280 because
# it predates the operator decision to switch; the generated schematic/netlist must
# reflect the intended part.  The BME280 *symbol* (Sensor:BME280) is used because it
# shares the BMP280 clockwise LGA-8 pad numbering that the board is wired for; only
# the Value and Footprint fields are overridden to MS5611-01BA / LGA-8_3x5mm_P1.25mm.
BARO_REF = "U5"
BARO_VALUE = "MS5611-01BA"
BARO_FOOTPRINT = "Package_LGA:LGA-8_3x5mm_P1.25mm"
# Custom inline symbol: the LR2021 Gen4 LoRa module as the board actually wires it.
# The board uses the 18-pin castellated LoRa2021_Castellated footprint; pad names
# below are derived from the v8i board netlist, with un-routed pads left neutral.
LR2021_PINS = [
    ("1", "VCC"), ("2", "GND"), ("3", "MISO"), ("4", "MOSI"),
    ("5", "SCK"), ("6", "NSS"), ("7", "BUSY"), ("8", "GND"),
    ("9", "ANT"), ("10", "PAD10"), ("11", "GND"), ("12", "GND"),
    ("13", "PAD13"), ("14", "RESET"), ("15", "DIO0"), ("16", "PAD16"),
    ("17", "PAD17"), ("18", "GND"),
]

# Pads declared deliberately unconnected (INTENTIONAL rows of the audit).
INTENTIONAL_NC = {
    ("J1", "6"), ("U3", "4"), ("U3", "5"), ("U3", "13"),
    ("U3", "14"), ("U3", "16"), ("U3", "17"),
}
# Pads in the audit whose GAP verdict is still open (PCB-S0b owns the ruling).
DECLARED_GAP = {
    ("U2", "10"): "TODO(unverified): LoRa2021 Gen4 pad 10 function / termination",
    ("U2", "13"): "TODO(unverified): LoRa2021 Gen4 pad 13 function / termination",
    ("U2", "16"): "TODO(unverified): LoRa2021 Gen4 pad 16 function / termination",
    ("U2", "17"): "TODO(unverified): LoRa2021 Gen4 pad 17 function / termination",
    ("U3", "15"): "TODO(unverified): MAX-M10S VIO_SEL tie-off required",
    ("U3", "18"): "TODO(unverified): MAX-M10S ~SAFEBOOT inactive level tie-off required",
    ("U4", "4"): "TODO(unverified): TPS7A02 pin 4 function / tie-off",
}

# Functional column layout: (column index, ordered refs)
COLUMNS = [
    ["SOLAR", "D1", "C_CAP", "U4", "C1", "C3", "R_DIV1", "R_DIV2"],
    ["U1", "C2", "C4", "R_PD", "R_LED", "LED1"],
    ["U2", "ANT1"],
    ["U3", "ANT2", "R_SER", "C_SH1", "C_SH2"],
    ["U5", "J1", "J2"],
    ["MNT1", "MNT2", "MNT3", "MNT4"],
]
COLUMN_TITLES = [
    "SOLAR INPUT / SUPERCAP / 3V3 LDO",
    "ESP32-C3-WROOM-02 + SUPPORT",
    "LR2021F33 RADIO (18-pin castellated)",
    "MAX-M10S GNSS + ANT2 FEED",
    "MS5611 + PROGRAMMING / DEBUG HEADERS",
    "MOUNTING HOLES",
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
    lib_blocks = {"balloon_flight:LR2021F33": lr2021_symbol()}
    resolved = []
    for fp in footprints:
        lib_id = resolve_symbol(fp["fpid"])
        if lib_id in lib_blocks:
            block = lib_blocks[lib_id]
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
                 '\n\t(lib (name "%s")(type "KiCad")'
                 '(uri "${KIPRJMOD}/v9_lib/%s.pretty")(options "")'
                 '(descr "v9 flight board footprints (F33 fixed pattern + bare '
                 'LoRa2021 + SX1280 UNVERIFIED)"))\n)\n'
                 % (FP_LIBNAME, FP_LIBNAME, V9_LIBNAME, V9_LIBNAME))

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
                'v8i_krt_gnss.kicad_pcb"\n\t\t(exclude_from_sim no)\n'
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
        # design intent override for the barometer (frozen PCB labels it BMP280)
        value = BARO_VALUE if ref == BARO_REF else fp["value"]
        footprint = BARO_FOOTPRINT if ref == BARO_REF else "%s:%s" % (FP_LIBNAME, fp["leaf"])
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
               fmt(sy - 6.35), value, fmt(sx + 2.54), fmt(sy + 2.54),
               footprint, fmt(sx), fmt(sy),
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

    libs = sorted({k.split(":")[0] for k in lib_blocks}
                  | {"Sensor_Pressure", "Diode", V9_LIBNAME})
    with open(OUT_LIBTABLE, "w") as fh:
        fh.write('(sym_lib_table\n\t(version 7)\n')
        for lib in libs:
            uri = (os.path.join(SYMDIR, lib + ".kicad_sym")
                   if lib not in ("balloon_flight", V9_LIBNAME)
                   else ("${KIPRJMOD}/balloon_flight.kicad_sym"
                         if lib == "balloon_flight"
                         else "${KIPRJMOD}/v9_lib/%s.kicad_sym" % V9_LIBNAME))
            fh.write('\t(lib (name "%s")(type "KiCad")(uri "%s")(options "")'
                     '(descr ""))\n' % (lib, uri))
        fh.write(")\n")

    stats["flags"] = len(flags)
    return stats, resolved


# =====================================================================
# v9 TRI-BAND FLIGHT BOARD  (ADR-029 / 029-f33-sx1280-pin-plan / 034 / 035 /
# 036-043)
# ---------------------------------------------------------------------
# The C3 schematic above is DERIVED from a frozen PCB sha256.  No v9 PCB
# exists, so this variant is a DESIGN-INTENT schematic instead: every net
# below is transcribed from a landed decision record (named in V9_NET_SRC),
# and every pin whose electrical treatment no record fixes is left OPEN with
# a visible TODO(unverified) note.  Nothing is guessed -- in particular no
# tie-off is invented for the 2 W PA module, for an RF port, or for a power
# pin whose rail the records leave open (ADR-029 O5).
# =====================================================================

V9_OUT_SCH = os.path.join(HERE, "v9_flight.kicad_sch")
V9_LIBDIR = os.path.join(HERE, "v9_lib")
V9_FPLIB = os.path.join(V9_LIBDIR, "balloon_flight_v9.pretty")
V9_SYMLIB = os.path.join(V9_LIBDIR, "balloon_flight_v9.kicad_sym")
V9_FPTABLE = os.path.join(HERE, "v9_fp-lib-table")
V9_SYMTABLE = os.path.join(HERE, "v9_sym-lib-table")
V9_PROJECT = "v9_flight"
V9_LIBNAME = "balloon_flight_v9"
V9_SRC_PRETTY = os.path.join(REPO, "tracker", "hardware", "hub_board_diy",
                             "custom.pretty")
V9_SX_FP = os.path.join(REPO, "tracker", "hardware", "footprints", "v9",
                        "SX1280_QFN24.kicad_mod")

# --- F33-2G4 18-pad module.  Pad names from docs/DUAL-VARIANT-DESIGN.md (V2
# table) + commit d5a2e47 (the corrected vendor land pattern, in base).
V9_F33_PINS = [
    ("1", "VCC", "power_in"), ("2", "GND", "power_in"),
    ("3", "GND", "power_in"), ("4", "GND", "power_in"),
    ("5", "CE", "input"), ("6", "GND", "power_in"),
    ("7", "GND", "power_in"), ("8", "GND", "power_in"),
    ("9", "ANT", "passive"),
    ("10", "ANT-2G4", "passive"), ("11", "GND", "power_in"),
    ("12", "SCK", "input"), ("13", "NSS", "input"),
    ("14", "BUSY", "output"), ("15", "MOSI", "input"),
    ("16", "MISO", "output"), ("17", "RESET", "input"),
    ("18", "IRQ", "output"),
]

# --- bare LoRa2021 castellated 18-pad module.  Pad names from
# docs/DUAL-VARIANT-DESIGN.md (V1 table: GP2..GP8 wiring + "GND pins 2,8,11,12,18").
V9_BARE_PINS = [
    ("1", "VCC", "power_in"), ("2", "GND", "power_in"),
    ("3", "MISO", "output"), ("4", "MOSI", "input"),
    ("5", "SCK", "input"), ("6", "NSS", "input"),
    ("7", "BUSY", "output"), ("8", "GND", "power_in"),
    ("9", "ANT", "passive"),
    ("10", "2G4_ANT", "passive"), ("11", "GND", "power_in"),
    ("12", "GND", "power_in"), ("13", "PAD13_??", "passive"),
    ("14", "RESET", "input"), ("15", "IRQ_DIO9", "output"),
    ("16", "PAD16_??", "passive"), ("17", "PAD17_??", "passive"),
    ("18", "GND", "power_in"),
]

# --- SX1280.  *** PIN NUMBERS NOT VERIFIED ***  The Semtech SX1280 datasheet is
# unreachable from this host (see PROGRESS.md / REPORT.md).  The *signal names*
# are those the repo's own pin plan and the RadioLib SX1280 module interface
# expose (NSS/SCK/MOSI/MISO/BUSY/NRESET/DIO1-3); the QFN pad NUMBERING is a
# declared-unverified placeholder and MUST be re-done when the datasheet is read.
V9_SX1280_PINS = [
    ("1", "VDD_IN", "power_in"), ("2", "VDD_IO", "power_in"),
    ("3", "GND", "power_in"), ("4", "NRESET", "input"),
    ("5", "BUSY", "output"), ("6", "NSS", "input"),
    ("7", "SCK", "input"), ("8", "MOSI", "input"),
    ("9", "MISO", "output"), ("10", "DIO1", "bidirectional"),
    ("11", "DIO2", "bidirectional"), ("12", "DIO3", "bidirectional"),
    ("13", "ANT_SW", "output"), ("14", "RFIO", "passive"),
    ("15", "GND", "power_in"), ("16", "GND", "power_in"),
    ("17", "GND", "power_in"), ("18", "GND", "power_in"),
    ("19", "GND", "power_in"), ("20", "GND", "power_in"),
    ("21", "GND", "power_in"), ("22", "GND", "power_in"),
    ("23", "GND", "power_in"), ("24", "GND", "power_in"),
    ("25", "GND_EP", "power_in"),
]

# --- TPS7A02 3.3 V ultra-low-Iq LDO, SOT-23-5 (ADR-006).  Pin *names* follow the
# SOT-23-5 LDO convention the repo already uses (Regulator_Linear:TPS7A0533PDBV).
# The TPS7A02 pinout itself is not committed in-repo -> EN/NC treatment is TODO.
V9_TPS7A02_PINS = [
    ("1", "IN", "power_in"), ("2", "GND", "power_in"),
    ("3", "EN", "input"), ("4", "NC", "passive"), ("5", "OUT", "power_out"),
]


def _v9_symbol(libname, name, value, footprint, descr, datasheet, pins):
    """Build a balloon_flight_v9:<name> symbol from [(num, pname, etype), ...].

    Odd-indexed halves are placed left/right exactly like the LR2021F33 custom
    symbol the C3 generator already emits (pins 1..N/2 left, rest right).
    """
    half = (len(pins) + 1) // 2
    left, right = pins[:half], pins[half:]
    n = max(len(left), len(right))
    by = (n - 1) * 2.54 / 2.0 + 2.54
    bx = 12.7
    out = ['(symbol "%s:%s"' % (libname, name)]
    out.append('\t\t(pin_names\n\t\t\t(offset 1.016)\n\t\t\t(hide no)\n\t\t)')
    out.append('\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)')
    out.append('\t\t(property "Reference" "U"\n\t\t\t(at 0 %s 0)\n'
               '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
               '\t\t\t\t)\n\t\t\t)\n\t\t)' % fmt(by + 2.54))
    out.append('\t\t(property "Value" "%s"\n\t\t\t(at 0 %s 0)\n'
               '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
               '\t\t\t\t)\n\t\t\t)\n\t\t)' % (value, fmt(-by - 2.54)))
    out.append('\t\t(property "Footprint" "%s"\n\t\t\t(at 0 0 0)\n'
               '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
               '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)' % footprint)
    out.append('\t\t(property "Datasheet" "%s"\n\t\t\t(at 0 0 0)\n'
               '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
               '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)' % datasheet)
    out.append('\t\t(property "Description" "%s"\n\t\t\t(at 0 0 0)\n'
               '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
               '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)' % descr)
    out.append('\t\t(symbol "%s_0_1"\n\t\t\t(rectangle\n'
               '\t\t\t\t(start %s %s)\n\t\t\t\t(end %s %s)\n'
               '\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n'
               '\t\t\t\t\t(type default)\n\t\t\t\t)\n'
               '\t\t\t\t(fill\n\t\t\t\t\t(type background)\n\t\t\t\t)\n\t\t\t)\n\t\t)'
               % (name, fmt(-bx), fmt(by), fmt(bx), fmt(-by)))
    body = []
    for i, (num, pname, etype) in enumerate(left):
        body.append(_v9_pin(num, pname, etype, -bx - 2.54,
                            by - 2.54 - i * 2.54, 0.0))
    for i, (num, pname, etype) in enumerate(right):
        body.append(_v9_pin(num, pname, etype, bx + 2.54,
                            by - 2.54 - i * 2.54, 180.0))
    out.append('\t\t(symbol "%s_1_1"\n%s\n\t\t)' % (name, "\n".join(body)))
    out.append("\t)")
    return "\n".join(out)


def _v9_pin(num, pname, etype, x, y, ang):
    return ('\t\t\t(pin %s line\n\t\t\t\t(at %s %s %s)\n'
            '\t\t\t\t(length 2.54)\n\t\t\t\t(name "%s"\n'
            '\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n'
            '\t\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t\t)\n'
            '\t\t\t\t\t)\n\t\t\t\t)\n\t\t\t\t(number "%s"\n'
            '\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n'
            '\t\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t\t)\n'
            '\t\t\t\t\t)\n\t\t\t\t)\n\t\t\t)'
            % (etype, fmt(x), fmt(y), fmt(ang), pname, num))


def v9_custom_symbols():
    """The four repo-local symbols the v9 sheet needs (written to v9_lib/)."""
    return {
        "balloon_flight_v9:F33_2G4": _v9_symbol(
            V9_LIBNAME, "F33_2G4", "LoRa2021F33-2G4",
            "balloon_flight_v9:LoRa2021F33_2G4",
            "NiceRF LoRa2021F33-2G4 (SEMTECH LR2021, 18-pad castellated, "
            "built-in +30 dBm PA / 0.5 ppm TCXO). Pad names from "
            "docs/DUAL-VARIANT-DESIGN.md; land pattern from commit d5a2e47.",
            "https://www.nicerf.com/pdf/lora2021f33-2g4-2w-high-power-high-speed-"
            "multi-band-lr2021-wireless-communication-module-v1.1.pdf",
            V9_F33_PINS),
        "balloon_flight_v9:LR2021_BARE": _v9_symbol(
            V9_LIBNAME, "LR2021_BARE", "LoRa2021_Castellated",
            "balloon_flight_v9:LoRa2021_Castellated",
            "NiceRF LoRa2021 castellated (SEMTECH LR2021, 18-pad, "
            "chip-only 2.4 GHz RX under ADR-034 D1). Pad names from "
            "docs/DUAL-VARIANT-DESIGN.md V1 table. Land pattern UNVERIFIED "
            "against the vendor pad file (V9-RADIO-SITE-MATRIX open item 6).",
            "", V9_BARE_PINS),
        "balloon_flight_v9:SX1280": _v9_symbol(
            V9_LIBNAME, "SX1280", "SX1280",
            "balloon_flight_v9:SX1280_QFN24",
            "Semtech SX1280 2.4 GHz ranging transceiver. *** PIN NUMBERING "
            "AND LAND PATTERN NOT VERIFIED - Semtech datasheet unreachable on "
            "this host; see TODO(unverified) notes on the sheet. ***",
            "", V9_SX1280_PINS),
        "balloon_flight_v9:TPS7A0233": _v9_symbol(
            V9_LIBNAME, "TPS7A0233", "TPS7A02",
            "Package_TO_SOT_SMD:SOT-23-5",
            "TI TPS7A02 3.3 V ultra-low-Iq LDO (25 nA), SOT-23-5 - ADR-006 3.3 V "
            "rail. EN/NC tie-off not fixed by any record.",
            "", V9_TPS7A02_PINS),
    }


# --- component table -------------------------------------------------------
# ref, lib_id, value, footprint, dnp, note
V9_COMPONENTS = [
    ("U1", "RF_Module:ESP32-S3-WROOM-1", "ESP32-S3-WROOM-1U-N8R8",
     "RF_Module:ESP32-S3-WROOM-1U", False,
     "ADR-029 D1 / ADR-037 D1: octal-PSRAM -N8R8, U.FL variant."),
    ("U2", "balloon_flight_v9:F33_2G4", "LoRa2021F33-2G4",
     "balloon_flight_v9:LoRa2021F33_2G4", False,
     "ADR-034 D1/D2: 433 MHz TX on the 2 W sub-GHz port (pin 9)."),
    ("U3", "balloon_flight_v9:LR2021_BARE", "LoRa2021_Castellated",
     "balloon_flight_v9:LoRa2021_Castellated", False,
     "ADR-034 D1: separate bare LoRa2021 = the 2.4 GHz RX chip."),
    ("U4", "balloon_flight_v9:SX1280", "SX1280",
     "balloon_flight_v9:SX1280_QFN24", False,
     "ADR-029 D2b + ADR-035: dedicated 2.4 GHz ranging radio."),
    ("U5", "RF_GPS:MAX-M10S", "MAX-M10S", "RF_GPS:ublox_MAX", False,
     "ADR-029 D2b: GNSS L1 position/time; receive-only, continuous (ADR-035 D3)."),
    ("U6", "Sensor_Pressure:MS5611-01BA", "MS5611-01BA",
     "Package_LGA:LGA-8_3x5mm_P1.25mm", False,
     "Barometer, 10-1200 hPa flight profile (ADR-029 pin plan: I2C on GPIO1/2)."),
    ("U7", "balloon_flight_v9:TPS7A0233", "TPS7A02",
     "Package_TO_SOT_SMD:SOT-23-5", False,
     "ADR-006: TPS7A02 3.3 V LDO, solar -> BAT54 -> supercap -> LDO."),
    ("C_CAP1", "Device:C_Polarized", "3.3F 2.7V (AVX SCC)",
     "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", False,
     "ADR-006: 2x 3.3 F 2.7 V in series = 1.65 F @ 5.4 V (cell A)."),
    ("C_CAP2", "Device:C_Polarized", "3.3F 2.7V (AVX SCC)",
     "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", False,
     "ADR-006: supercap bank (cell B). Sized to ONE burst (ADR-036)."),
    ("D1", "Device:D_Schottky", "BAT54", "Diode_SMD:D_SOD-123", False,
     "ADR-006: solar reverse-current Schottky (blocks back-feed into the "
     "solar cells at night)."),
    ("R_DIV1", "Device:R", "1M", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-006: 2x 1 MOhm supercap-rail ADC divider (upper)."),
    ("R_DIV2", "Device:R", "1M", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-006: 2x 1 MOhm supercap-rail ADC divider (lower)."),
    ("R_F1", "Device:R", "100R", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-029 D2(d): dedicated RC/ferrite feed (100 Ohm + 10 uF) into the GNSS "
     "rail."),
    ("C4", "Device:C", "10uF", "Capacitor_SMD:C_0402_1005Metric", False,
     "ADR-029 D2(d): GNSS-rail bulk cap on the filtered feed."),
    ("ANT1", "Connector:Conn_Coaxial", "U.FL_433_TX",
     "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical", False,
     "ADR-029 D3 (sub-GHz U.FL) + ADR-034 D1: 433 MHz TX feed = F33 pin 9."),
    ("ANT2", "Connector:Conn_Coaxial", "U.FL_2G4_TXRX",
     "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical", False,
     "ADR-029 D3 (F33 ANT-2G4 U.FL) : the F33's own 2.4 GHz port."),
    ("ANT3", "Connector:Conn_Coaxial", "U.FL_2G4_RX",
     "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical", False,
     "ADR-034 D1: 2.4 GHz RX feed of the bare LoRa2021 (pin 10). "
     "*** SEE the four-feed conflict TODO on the sheet. ***"),
    ("ANT4", "Connector:Conn_Coaxial", "U.FL_GNSS_L1",
     "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical", False,
     "ADR-029 D3: GNSS L1 feed, +Y sky-facing edge."),
]

# --- nets ------------------------------------------------------------------
# net -> [(ref, pin), ...].  Each entry carries its citation.
V9_NETS = [
    ("+3V3", [("U1", "2"), ("U2", "5"), ("U3", "1"), ("U5", "8"), ("U6", "1"),
              ("U7", "5"), ("R_F1", "1")],
     "ADR-006 3.3 V rail (TPS7A02 OUT); U2 pin 5 CE strapped to 3V3 per the "
     "ADR-029 pin plan (blocker 3: confirm CE vs the purchased revision)."),
    ("GND", [("U1", "1"),
             ("U2", "2"), ("U2", "3"), ("U2", "4"), ("U2", "6"), ("U2", "7"),
             ("U2", "8"), ("U2", "11"),
             ("U3", "2"), ("U3", "8"), ("U3", "11"), ("U3", "12"), ("U3", "18"),
             ("U4", "3"), ("U4", "15"), ("U4", "16"), ("U4", "17"), ("U4", "18"),
             ("U4", "19"), ("U4", "20"), ("U4", "21"), ("U4", "22"), ("U4", "23"),
             ("U4", "24"), ("U4", "25"),
             ("U5", "1"), ("U6", "3"), ("U7", "2"), ("C_CAP2", "2"),
             ("R_DIV2", "2"), ("C4", "2"),
             ("ANT1", "2"), ("ANT2", "2"), ("ANT3", "2"), ("ANT4", "2")],
     "Ground. F33 GND pads 2,3,4,6,7,8,11; bare GND pads 2,8,11,12,18 "
     "(docs/DUAL-VARIANT-DESIGN.md)."),
    ("VSCAP", [("D1", "1"), ("C_CAP1", "1"), ("C_CAP2", "1"), ("U7", "1"),
               ("R_DIV1", "1"), ("R_F1", "1"), ("C4", "1")],
     "ADR-006 chain: BAT54 cathode -> supercap bank -> TPS7A02 IN."),
    ("SOLAR_IN", [("D1", "2")],
     "ADR-006: 4 wings x 3 cells = 6.0 V / ~2.4 W peak. The solar INPUT "
     "connector is not in the v9 component list -> source end TODO(unverified)."),
    ("F33_SCK", [("U1", "4"), ("U2", "12"), ("U3", "5")],
     "SPI2 FSPI SCK on GPIO4; the bare module shares SPI2 data/clock "
     "(V9-RADIO-SITE-MATRIX 3.1)."),
    ("F33_MOSI", [("U1", "5"), ("U2", "15"), ("U3", "4")],
     "SPI2 MOSI on GPIO5 (shared, see 3.1)."),
    ("F33_MISO", [("U1", "6"), ("U2", "16"), ("U3", "3")],
     "SPI2 MISO on GPIO6 (shared, see 3.1)."),
    ("F33_CS_N", [("U1", "7"), ("U2", "13")],
     "F33 NSS on GPIO7 (ADR-029 pin plan, unique CS)."),
    ("F33_BUSY", [("U1", "12"), ("U2", "14")],
     "F33 BUSY polled by GPIO8 (ADR-029 D4 hardware BUSY binding)."),
    ("F33_IRQ", [("U1", "17"), ("U2", "18")],
     "F33 IRQ/DIO1 on GPIO9 (ADR-029 pin plan)."),
    ("F33_RESET_N", [("U1", "18"), ("U2", "17")],
     "F33 RESET on GPIO10 (ADR-029 pin plan)."),
    ("SX1280_SCK", [("U1", "22"), ("U4", "7")],
     "SPI3 clock on GPIO14 (ADR-029 pin plan). SX1280 pad numbers UNVERIFIED."),
    ("SX1280_MOSI", [("U1", "8"), ("U4", "8")],
     "SPI3 MOSI on GPIO15 (ADR-029 pin plan)."),
    ("SX1280_MISO", [("U1", "9"), ("U4", "9")],
     "SPI3 MISO on GPIO16 (ADR-029 pin plan)."),
    ("SX1280_CS_N", [("U1", "10"), ("U4", "6")],
     "SPI3 CS on GPIO17 (ADR-029 pin plan)."),
    ("SX1280_BUSY", [("U1", "31"), ("U4", "5")],
     "SX1280 BUSY on GPIO38 (ADR-029 pin plan)."),
    ("SX1280_RESET_N", [("U1", "32"), ("U4", "4")],
     "SX1280 RESET on GPIO39 - native JTAG MTCK lost (ADR-029 pin plan, "
     "explicit trade-off)."),
    ("SX1280_DIO1", [("U1", "33"), ("U4", "10")],
     "SX1280 DIO1/IRQ on GPIO40 - native MTDO/JTAG lost (pin plan)."),
    ("SX1280_DIO2", [("U1", "11"), ("U4", "11")],
     "SX1280 DIO2 on GPIO18 (pin plan, optional function)."),
    ("SX1280_DIO3", [("U1", "34"), ("U4", "12")],
     "SX1280 DIO3 on GPIO41 - native MTDI/JTAG lost (pin plan)."),
    ("SX1280_ANT_SW", [("U1", "35"), ("U4", "13")],
     "SX1280 antenna-switch control on GPIO42 (pin plan: fit only if the RF "
     "front end proves the switch exists)."),
    ("GNSS_PPS", [("U1", "23"), ("U5", "4")],
     "MAX-M10S TIMEPULSE/PPS on GPIO21 (ADR-029 pin plan)."),
    ("GNSS_TX", [("U1", "36"), ("U5", "2")],
     "MAX-M10S TXD -> S3 RXD0/GPIO43 (pin plan; console mux is a firmware "
     "policy)."),
    ("GNSS_RX", [("U1", "37"), ("U5", "3")],
     "MAX-M10S RXD <- S3 TXD0/GPIO44 (pin plan)."),
    ("I2C_SDA", [("U1", "39"), ("U6", "7")],
     "MS5611 SDI/SDA on GPIO1, external pull-up to 3V3 required (pin plan)."),
    ("I2C_SCL", [("U1", "38"), ("U6", "8")],
     "MS5611 SCLK/SCL on GPIO2, external pull-up to 3V3 required (pin plan)."),
    ("SCAP_ADC", [("R_DIV1", "2"), ("R_DIV2", "1")],
     "ADR-006 supercap ADC divider tap. The ADC GPIO is UNRESOLVED: ADR-006 "
     "says GPIO0, the ADR-029 pin plan reserves IO0 as a boot strap."),
    ("ANT1_433_TX", [("U2", "9"), ("ANT1", "1")],
     "ADR-034 D1/D2 + ADR-029 D3: 433 MHz TX, F33 sub-GHz ANT."),
    ("ANT2_2G4_TXRX", [("U2", "10"), ("ANT2", "1")],
     "ADR-029 D2/D3: F33 ANT-2G4 port."),
    ("ANT3_2G4_RX", [("U3", "10"), ("ANT3", "1")],
     "ADR-034 D1: bare LoRa2021 2.4 GHz feed."),
    ("ANT4_GNSS_L1", [("U5", "11"), ("ANT4", "1")],
     "ADR-029 D3: MAX-M10S RF_IN -> GNSS L1 U.FL."),
]

# --- deliberately unconnected pins, each with the record that says so ------
V9_NC = [
    ("U1", "27", "IO0 boot strap: no radio pull-up/CS (ADR-029 pin plan, "
                 "strapping audit)."),
    ("U1", "15", "IO3 boot strap: no sensor/radio connection (pin plan)."),
    ("U1", "26", "IO45 boot strap: vendor strap level, no external load (pin plan)."),
    ("U1", "16", "IO46 boot strap: vendor strap level, no external load (pin plan)."),
    ("U1", "28", "IO35 = octal-PSRAM connection on -N8R8, not a board GPIO "
                 "(ADR-029 D1.1 / pin plan)."),
    ("U1", "29", "IO36 = octal-PSRAM connection (ADR-029 D1.1 / pin plan)."),
    ("U1", "30", "IO37 = octal-PSRAM connection (ADR-029 D1.1 / pin plan)."),
    ("U5", "5", "MAX-M10S EXTINT unused (carried from the v8i board audit)."),
    ("U5", "13", "MAX-M10S LNA_EN unused (v8i board audit)."),
    ("U5", "14", "MAX-M10S VCC_RF unused (v8i board audit)."),
    ("U5", "16", "MAX-M10S SDA unused - v9 GNSS is UART, not I2C (v8i audit)."),
    ("U5", "17", "MAX-M10S SCL unused - v9 GNSS is UART, not I2C (v8i audit)."),
]

# --- explicit TODO(unverified) open questions, never guessed ---------------
V9_TODO = [
    ("OPEN-1 5 V RAIL (U2 pin 1 VCC)",
     "The F33 reaches 2 W/33 dBm @433 only at 5.0 V. The 5 V rail is an open "
     "operator item (ADR-029 O5, carried into ADR-034). U2 pin 1 is left with "
     "NO net - do not tie a 2 W PA module to 3V3 or to an invented 5 V rail."),
    ("OPEN-2 SX1280 SUPPLY (U4 pins 1,2)",
     "SX1280 VDD_IN/VDD_IO rail not fixed by any record and the Semtech "
     "datasheet is unreachable here. Left open deliberately."),
    ("OPEN-3 SX1280 RF PORT (U4 pin 14 RFIO)",
     "No antenna feed is assigned to the SX1280 RFIO. ADR-029 D3 (as amended) "
     "enumerates the FOUR connectors as {GNSS, F33 sub-GHz, F33 ANT-2G4, "
     "SX1280}, but ADR-034 D1 re-points the 2.4 GHz RX at a SEPARATE bare "
     "LoRa2021 that also needs a feed. Exactly one of the two is left without "
     "a listed feed - resolve before fabricating. No tie-off guessed."),
    ("OPEN-4 BARE-MODULE CONTROL LINES (U3 pins 6,7,14,15)",
     "ADR-034 adds the bare LoRa2021 but NO record assigns its NSS/BUSY/RESET/"
     "IRQ GPIOs (the ADR-029 pin plan predates ADR-034). Left floating - "
     "the +4 GPIO budget in V9-RADIO-SITE-MATRIX 3.1 must be spent first."),
    ("OPEN-5 BARE-MODULE SUB-GHz PORT (U3 pin 9 ANT)",
     "Unused under ADR-034 (U3 is the 2.4 GHz RX). An RF port is not tied off "
     "without a decision - left open."),
    ("OPEN-6 BARE-MODULE PAD FUNCTIONS (U3 pins 13,16,17)",
     "PAD13/PAD16/PAD17 functions are unverified (v8i audit: DECLARED_GAP)."),
    ("OPEN-7 F33 DIO5 (U1 pin 19)",
     "The pin plan assigns F33_DIO5 to GPIO11, but the F33's 18-pad map has no "
     "DIO5 pad. Which F33 pad carries DIO5 is unresolved - left open."),
    ("OPEN-8 MS5611 TIE-OFFS (U6 pins 2,4,6)",
     "MS5611 PS / CSB / SDO tie-off levels (I2C mode) are not in any record."),
    ("OPEN-9 MAX-M10S TIE-OFFS (U5 pins 6,7,9,15,18)",
     "V_BCKP / VCC_IO / ~RESET / VIO_SEL / ~SAFEBOOT tie-offs are not fixed by "
     "a record (VIO_SEL and ~SAFEBOOT were already DECLARED_GAP on v8i)."),
    ("OPEN-10 TPS7A02 EN / NC (U7 pins 3,4)",
     "TPS7A02 EN strap and the pin-4 NC treatment are not in any record."),
    ("OPEN-11 ESP32-S3 EN and USB (U1 pins 3,13,14)",
     "Module EN strap and the USB_D-/USB_D+ pads have no v9 connector or "
     "recorded tie-off."),
    ("OPEN-12 SUPERCAP ADC GPIO",
     "ADR-006 puts the supercap ADC on GPIO0; the ADR-029 pin plan reserves "
     "IO0 as a boot strap. The divider tap net exists but its MCU end is "
     "unresolved."),
    ("OPEN-13 SOLAR INPUT SOURCE",
     "The 4-wing x 3-cell solar array input connector is not in the v9 "
     "component list; SOLAR_IN has only the D1 anode end so far."),
    ("OPEN-14 SX1280 PIN NUMBERS + LAND PATTERN",
     "The Semtech SX1280 datasheet could not be retrieved on this host. The "
     "symbol's QFN pad numbering and SX1280_QFN24.kicad_mod geometry are "
     "PLACEHOLDERS - every SX1280 pin is TODO(unverified)."),
]


def v9_emit():
    sch_path = V9_OUT_SCH
    libdir = V9_LIBDIR
    fplib = V9_FPLIB
    os.makedirs(libdir, exist_ok=True)
    os.makedirs(fplib, exist_ok=True)

    custom = v9_custom_symbols()
    comps = list(V9_COMPONENTS)

    # ---- resolve a lib_symbol block for every component -------------------
    lib_blocks = dict(custom)
    for (ref, lib_id, value, footprint, dnp, note) in comps:
        if lib_id in lib_blocks:
            continue
        lib, name = lib_id.split(":")
        lib_blocks[lib_id] = load_lib_symbol(lib, name)

    # ---- validate: every net endpoint must exist as a symbol pin ----------
    problems = []
    by_ref = {c[0]: c for c in comps}
    for (net, nodes, src) in V9_NETS:
        for (ref, pin) in nodes:
            if ref not in by_ref:
                problems.append("net %s names unknown ref %s" % (net, ref))
                continue
            if pin not in symbol_pins(lib_blocks[by_ref[ref][1]]):
                problems.append("net %s: %s has no pin %s" % (net, ref, pin))
    for (ref, pin, why) in V9_NC:
        if ref not in by_ref:
            problems.append("NC names unknown ref %s" % ref)
        elif pin not in symbol_pins(lib_blocks[by_ref[ref][1]]):
            problems.append("NC: %s has no pin %s" % (ref, pin))
    if problems:
        print("V9 VALIDATION FAILURES:")
        for p in problems:
            print("  -", p)
        sys.exit(3)

    # ---- footprints: hand the .pretty the fixed F33 + bare + the new SX1280
    fp_sources = [
        (os.path.join(V9_SRC_PRETTY, "LoRa2021F33_2G4.kicad_mod"),
         "LoRa2021F33_2G4"),
        (os.path.join(V9_SRC_PRETTY, "LoRa2021_Castellated.kicad_mod"),
         "LoRa2021_Castellated"),
        (V9_SX_FP, "SX1280_QFN24"),
    ]
    written = []
    for src, leaf in fp_sources:
        if not os.path.exists(src):
            sys.exit("v9: missing footprint source %s" % src)
        body = open(src).read()
        body = re.sub(r'\(footprint\s+"[^"]*"',
                      '(footprint "%s:%s"\n\t\t(version 20250114)\n'
                      '\t\t(generator "pcbnew")\n\t\t(generator_version "9.0")'
                      % (V9_LIBNAME, leaf), body, count=1)
        with open(os.path.join(fplib, leaf + ".kicad_mod"), "w") as fh:
            fh.write(clean(body) + "\n")
        written.append(leaf)
    with open(V9_FPTABLE, "w") as fh:
        fh.write('(fp_lib_table\n\t(version 7)\n\t(lib (name "%s")'
                 '(type "KiCad")(uri "${KIPRJMOD}/v9_lib/%s.pretty")'
                 '(options "")(descr "v9 flight board footprints: fixed F33 '
                 'land pattern (d5a2e47) + bare LoRa2021 + SX1280 (UNVERIFIED)"))'
                 '\n)\n' % (V9_LIBNAME, V9_LIBNAME))

    # ---- placement: one component per grid slot, columns left to right ----
    V9_COLUMNS = [
        ["U5", "U6", "U7"],
        ["U1"],
        ["U2"],
        ["U3"],
        ["U4"],
        ["C_CAP1", "C_CAP2", "D1", "R_DIV1", "R_DIV2", "R_F1", "C4"],
        ["ANT1", "ANT2", "ANT3", "ANT4"],
    ]
    V9_COL_TITLES = [
        "GNSS / BARO / POWER",
        "U1 ESP32-S3-WROOM-1U-N8R8",
        "U2 LoRa2021F33-2G4  (433 MHz TX, 5 V - RAIL OPEN)",
        "U3 bare LoRa2021  (2.4 GHz RX)",
        "U4 SX1280  (2.4 GHz ranging)  *** PINOUT UNVERIFIED ***",
        "SUPERCAP BANK / BAT54 / DIVIDER / GNSS RC",
        "U.FL ANTENNAS (see the four-feed conflict)",
    ]
    placed_refs = [r for col in V9_COLUMNS for r in col]
    missing = [c[0] for c in comps if c[0] not in placed_refs]
    if missing:
        sys.exit("v9 layout missing refs: %s" % missing)

    sizes = {}
    for c in comps:
        x0, y0, x1, y1 = symbol_extent(lib_blocks[c[1]])
        sizes[c[0]] = (x1 - x0, y1 - y0)
    col_x, x = [], 30.48
    for col in V9_COLUMNS:
        col_x.append(x)
        x += max(sizes[r][0] for r in col) + 45.72
    pos = {}
    for ci, col in enumerate(V9_COLUMNS):
        y = 50.8
        for ref in col:
            pos[ref] = (round(col_x[ci] / 1.27) * 1.27, round(y / 1.27) * 1.27)
            y += sizes[ref][1] + 25.4

    # ---- body ------------------------------------------------------------
    body = ['\t(text "BALLOON v9 TRI-BAND FLIGHT BOARD - DESIGN-INTENT '
            'schematic from the v9 decision records (ADR-029/034/035/036-043). '
            'NOT derived from a PCB."\n\t\t(exclude_from_sim no)\n'
            '\t\t(at 30.48 20.32 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t'
            '(size 2.54 2.54)\n\t\t\t)\n\t\t\t(justify left bottom)\n\t\t)\n'
            '\t\t(uuid "%s")\n\t)' % uid()]
    for ci, title in enumerate(V9_COL_TITLES):
        body.append('\t(text "%s"\n\t\t(exclude_from_sim no)\n'
                    '\t\t(at %s 43.18 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t'
                    '(size 1.524 1.524)\n\t\t\t)\n\t\t\t(justify left bottom)\n'
                    '\t\t)\n\t\t(uuid "%s")\n\t)'
                    % (title, fmt(round(col_x[ci] / 1.27) * 1.27), uid()))

    todo_x = 30.48
    todo_y = 250.0
    for (title, txt) in V9_TODO:
        body.append('\t(text "TODO(unverified) %s -- %s"\n'
                    '\t\t(exclude_from_sim no)\n\t\t(at %s %s 0)\n'
                    '\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n'
                    '\t\t\t)\n\t\t\t(justify left bottom)\n\t\t)\n'
                    '\t\t(uuid "%s")\n\t)' % (title, txt, fmt(todo_x),
                                              fmt(todo_y), uid()))
        todo_y += 3.81

    net_of = {}
    net_src = {}
    for (net, nodes, src) in V9_NETS:
        net_src[net] = src
        for nd in nodes:
            net_of[nd] = net
    nc_of = {(r, p): why for (r, p, why) in V9_NC}

    power_syms, wires, labels, ncs, notes = [], [], [], [], []
    stats = dict(pins=0, nets=set(), labels=0, power=0, nc=0, todo=0,
                 power_out=set())

    for (ref, lib_id, value, footprint, dnp, note) in comps:
        block = lib_blocks[lib_id]
        sx, sy = pos[ref]
        pins = symbol_pins(block)
        pin_txt = "".join('\t\t(pin "%s"\n\t\t\t(uuid "%s")\n\t\t)\n' % (n, uid())
                          for n in sorted(pins, key=lambda k: (len(k), k)))
        body.append(
            "\t(symbol\n\t\t(lib_id \"%s\")\n\t\t(at %s %s 0)\n\t\t(unit 1)\n"
            "\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n"
            "\t\t(dnp %s)\n\t\t(uuid \"%s\")\n"
            "\t\t(property \"Reference\" \"%s\"\n\t\t\t(at %s %s 0)\n"
            "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t\t)\n\t\t\t\t(justify left)\n\t\t\t)\n\t\t)\n"
            "\t\t(property \"Value\" \"%s\"\n\t\t\t(at %s %s 0)\n"
            "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t\t)\n\t\t\t\t(justify left)\n\t\t\t)\n\t\t)\n"
            "\t\t(property \"Footprint\" \"%s\"\n\t\t\t(at %s %s 0)\n"
            "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n"
            "%s\t\t(instances\n\t\t\t(project \"%s\"\n"
            "\t\t\t\t(path \"/%s\"\n\t\t\t\t\t(reference \"%s\")\n"
            "\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n"
            % (lib_id, fmt(sx), fmt(sy), "no" if not dnp else "yes", uid(),
               ref, fmt(sx + 2.54), fmt(sy - 7.62), value, fmt(sx + 2.54),
               fmt(sy + 2.54), footprint, fmt(sx), fmt(sy), pin_txt,
               V9_PROJECT, uid(), ref))

        for pnum in sorted(pins, key=lambda k: (len(k), k)):
            pin = pins[pnum]
            px, py = pin_point(sx, sy, pin)
            stats["pins"] += 1
            key = (ref, pnum)
            if key in net_of:
                net = net_of[key]
                ex, ey = stub_end(sx, sy, pin, 5.08)
                wires.append((px, py, ex, ey))
                if net in ("+3V3", "GND"):
                    power_syms.append((net, ex, ey))
                    stats["power"] += 1
                else:
                    labels.append((net, ex, ey))
                    stats["labels"] += 1
                stats["nets"].add(net)
                if pin["type"] == "power_out":
                    stats["power_out"].add(net)
            elif key in nc_of:
                ncs.append((px, py))
                stats["nc"] += 1
            # else: deliberately left floating; covered by a V9_TODO note

    # PWR_FLAG on every rail not driven by a real power-output pin
    flag_pts = {}
    for (net, x, y) in power_syms:
        flag_pts.setdefault(net, (x, y))
    for (net, x, y) in labels:
        flag_pts.setdefault(net, (x, y))
    flag_nets = {n for (n, _, _) in power_syms} - stats["power_out"]
    from_lab = {n for (n, _, _) in labels}
    flag_nets |= {n for n in from_lab if n.startswith("V") or n == "SOLAR_IN"}
    flags = []
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
                     '\t\t(instances\n\t\t\t(project "%s"\n'
                     '\t\t\t\t(path \"/%s\"\n\t\t\t\t\t(reference "#PWR")\n'
                     '\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n'
                     % (net, fmt(x), fmt(y), uid(), fmt(x + 2.54),
                        fmt(y + 2.54), net, fmt(x + 2.54), fmt(y - 2.54),
                        fmt(x), fmt(y), uid(), V9_PROJECT, uid()))
                     .replace('#PWR', pref))
    for i, (net, x, y) in enumerate(flags):
        body.append(('\t(symbol\n\t\t(lib_id "power:PWR_FLAG")\n'
                     '\t\t(at %s %s 0)\n\t\t(unit 1)\n'
                     '\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n'
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
                     '\t\t(instances\n\t\t\t(project "%s"\n'
                     '\t\t\t\t(path \"/%s\"\n\t\t\t\t\t(reference "#FLG0%d")\n'
                     '\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n'
                     % (fmt(x), fmt(y), uid(), i + 1, fmt(x + 2.54),
                        fmt(y + 2.54), fmt(x + 2.54), fmt(y - 2.54),
                        fmt(x), fmt(y), uid(), V9_PROJECT, uid(), i + 1)))
    for (x, y) in ncs:
        body.append('\t(no_connect\n\t\t(at %s %s)\n\t\t(uuid "%s")\n\t)\n'
                    % (fmt(x), fmt(y), uid()))

    # power symbol definitions used
    for net in sorted({n for (n, _, _) in power_syms}):
        key = "power:" + net
        if key not in lib_blocks:
            lib_blocks[key] = load_lib_symbol("power", net)
    if flags:
        lib_blocks["power:PWR_FLAG"] = load_lib_symbol("power", "PWR_FLAG")

    libdefs = "\n".join(lib_blocks[k] for k in lib_blocks)
    sch = ('(kicad_sch\n\t(version 20250114)\n\t(generator "eeschema")\n'
           '\t(generator_version "9.0")\n\t(uuid "%s")\n\t(paper "A2")\n'
           '\t(title_block\n\t\t(title "Balloon v9 Tri-Band Flight Board")\n'
           '\t\t(date "2026-10-07")\n\t\t(rev "v9-design-intent")\n'
           '\t\t(company "Balloon Relay")\n'
           '\t\t(comment 1 "DESIGN-INTENT schematic derived from ADR-029/034/035/'
           '036-043. Uncited pins carry TODO(unverified) notes; nothing guessed.")\n'
           '\t)\n\t(lib_symbols\n%s\n\t)\n%s'
           '\t(sheet_instances\n\t\t(path "/"\n\t\t\t(page "1")\n\t\t)\n\t)\n)\n'
           % (uid(), libdefs, "".join(body)))
    with open(sch_path, "w") as fh:
        fh.write(clean(sch))

    # standalone symbol library
    with open(V9_SYMLIB, "w") as fh:
        fh.write('(kicad_symbol_lib\n\t(version 20241209)\n'
                 '\t(generator "kicad_symbol_editor")\n'
                 '\t(generator_version "9.0")\n')
        for k, blk in lib_blocks.items():
            if k.startswith(V9_LIBNAME + ":"):
                fh.write("\t" + blk.replace('(symbol "%s:' % V9_LIBNAME,
                                            '(symbol "', 1) + "\n")
        fh.write(")\n")

    # project file: kicad-cli only resolves the PROJECT-LOCAL library tables when
    # a matching <name>.kicad_pro exists next to the schematic.
    pro_src = os.path.join(HERE, "v_c3_flight.kicad_pro")
    if os.path.exists(pro_src):
        pro = open(pro_src).read().replace("v_c3_flight", V9_PROJECT)
        with open(os.path.join(HERE, V9_PROJECT + ".kicad_pro"), "w") as fh:
            fh.write(pro)

    # KiCad-convention shared tables (union of the C3 + v9 libraries) so that
    # either generator leaves the other's libs resolvable.
    union = sorted({k.split(":")[0] for k in lib_blocks}
                   | {"balloon_flight", "Sensor_Pressure", "Diode"})
    with open(OUT_LIBTABLE, "w") as fh:
        fh.write('(sym_lib_table\n\t(version 7)\n')
        for lib in union:
            uri = (os.path.join(SYMDIR, lib + ".kicad_sym")
                   if lib not in ("balloon_flight", V9_LIBNAME)
                   else ("${KIPRJMOD}/balloon_flight.kicad_sym"
                         if lib == "balloon_flight"
                         else "${KIPRJMOD}/v9_lib/%s.kicad_sym" % V9_LIBNAME))
            fh.write('\t(lib (name "%s")(type "KiCad")(uri "%s")(options "")'
                     '(descr ""))\n' % (lib, uri))
        fh.write(")\n")
    with open(OUT_FPTABLE, "w") as fh:
        fh.write('(fp_lib_table\n\t(version 7)\n'
                 '\t(lib (name "balloon_flight")(type "KiCad")'
                 '(uri "${KIPRJMOD}/balloon_flight.pretty")(options "")'
                 '(descr "Flight board footprints exported from the frozen PCB"))\n'
                 '\t(lib (name "%s")(type "KiCad")'
                 '(uri "${KIPRJMOD}/v9_lib/%s.pretty")(options "")'
                 '(descr "v9 flight board footprints"))\n)\n'
                 % (V9_LIBNAME, V9_LIBNAME))

    libs = sorted({k.split(":")[0] for k in lib_blocks})
    with open(V9_SYMTABLE, "w") as fh:
        fh.write('(sym_lib_table\n\t(version 7)\n')
        for lib in libs:
            uri = (os.path.join(SYMDIR, lib + ".kicad_sym")
                   if lib != V9_LIBNAME
                   else "${KIPRJMOD}/v9_lib/%s.kicad_sym" % V9_LIBNAME)
            fh.write('\t(lib (name "%s")(type "KiCad")(uri "%s")(options "")'
                     '(descr ""))\n' % (lib, uri))
        fh.write(")\n")

    stats["comp"] = len(comps)
    stats["fp"] = written
    return stats


def main_v9():
    print("v9 schematic variant (design-intent, NOT derived from a PCB)")
    print("records  : ADR-029, docs/adr/029-f33-sx1280-pin-plan.md, ADR-034,")
    print("           ADR-035, ADR-036-043, docs/DUAL-VARIANT-DESIGN.md,")
    print("           docs/V9-RADIO-SITE-MATRIX.md")
    stats = v9_emit()
    print("components    :", stats["comp"])
    print("symbol pins   :", stats["pins"])
    print("net labels    :", stats["labels"])
    print("power pins    :", stats["power"])
    print("no_connect    :", stats["nc"])
    print("TODO(unverified) notes:", len(V9_TODO))
    print("distinct nets :", len(stats["nets"]), sorted(stats["nets"]))
    print("footprints    :", stats["fp"])
    print("wrote         :", V9_OUT_SCH)
    print("                ", V9_SYMLIB)
    print("                ", V9_FPLIB)


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
    if len(sys.argv) > 1 and sys.argv[1] == "v9":
        main_v9()
    else:
        main()
