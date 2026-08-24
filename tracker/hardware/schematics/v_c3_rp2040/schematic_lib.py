#!/usr/bin/env python3
"""Generate v_c3_rp2040.kicad_sch — parses symbol libraries for accurate pin coords."""

import re
import sys
import uuid
from pathlib import Path

def uid(seed):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"balloon.c3rp2040.v2.{seed}"))


# ---------- Symbol library parser ----------
class SymbolLib:
    def __init__(self):
        self.libs = {}  # name -> Symbol

    def load(self, lib_name, filepath):
        """Parse a .kicad_sym file and extract all symbols."""
        text = Path(filepath).read_text()
        # Find each top-level (symbol "NAME" ...) block (balance-parens)
        for m in self._top_level_symbols(text):
            name, body = m
            self.libs[name] = Symbol(name, body, lib_name)

    def _top_level_symbols(self, text):
        """Yield (name, body) for each top-level symbol declaration."""
        # Find any (symbol "NAME" at indent level 1 (tab or 2-space)
        pattern = re.compile(r'^[ \t]+\(symbol "([^"\\]+)"', re.M)
        matches = list(pattern.finditer(text))
        for i, m in enumerate(matches):
            # Skip sub-symbols (those with _N_M suffix used for units like _0_1, _1_1)
            if re.search(r'_\d+_\d+$', m.group(1)):
                continue
            start = m.start()
            depth = 0
            end = start
            while end < len(text):
                if text[end] == '(':
                    depth += 1
                elif text[end] == ')':
                    depth -= 1
                    if depth == 0:
                        end += 1
                        break
                end += 1
            yield m.group(1), text[start:end]

    def get(self, lib_id):
        """lib_id like 'Device:C' or 'RF_Module:ESP32-C3-WROOM-02'."""
        name = lib_id.split(":", 1)[1]
        return self.libs.get(name)


class Pin:
    def __init__(self, name, number, x, y, angle, ptype):
        self.name = name
        self.number = number
        self.x = x
        self.y = y
        self.angle = angle  # 0=right, 90=up, 180=left, 270=down
        self.ptype = ptype


class Symbol:
    def __init__(self, name, body, lib_name):
        self.name = name
        self.lib = lib_name
        self.pins = {}  # number -> Pin
        self._parse(body)

    def _parse(self, body):
        # Find all (pin TYPE SHAPE (at X Y ANGLE) (length L) (name ...) (number ...))
        # The pattern needs to handle nested parens inside the pin.
        pin_re = re.compile(r'\(pin\s+(\w+)\s+(\w+)\s+(.*?)(?=\n\s*\(pin|\Z)', re.S)
        for m in pin_re.finditer(body):
            ptype, pshape, rest = m.group(1), m.group(2), m.group(3)
            # Extract (at X Y ANGLE)
            at_m = re.search(r'\(at\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\)', rest)
            if not at_m:
                continue
            x, y, angle = float(at_m.group(1)), float(at_m.group(2)), float(at_m.group(3))
            # Extract name
            name_m = re.search(r'\(name\s+"([^"]*)"', rest)
            pname = name_m.group(1) if name_m else ""
            number_m = re.search(r'\(number\s+"([^"]*)"', rest)
            pnum = number_m.group(1) if number_m else ""
            # KiCad Y axis in lib: positive=up. The pin position is the BODY-side end;
            # line extends OUT from the body at `angle`. The connection point on schematic = position.
            self.pins[pnum] = Pin(pname, pnum, x, y, int(angle), ptype)


# ---------- Schematic coordinate transform ----------
def to_schematic(sym_x, sym_y, inst_x, inst_y, rotation):
    """Transform symbol coordinate to schematic coordinate.
    Symbol Y is 'up-positive'; schematic Y is 'down-positive'. So schematic_y = inst_y - sym_y.
    Then apply rotation around instance origin.
    """
    sx, sy = sym_x, -sym_y  # invert Y
    if rotation == 0:
        dx, dy = sx, sy
    elif rotation == 90:
        dx, dy = -sy, sx
    elif rotation == 180:
        dx, dy = -sx, -sy
    elif rotation == 270:
        dx, dy = sy, -sx
    else:
        dx, dy = sx, sy
    return (inst_x + dx, inst_y + dy)


# ---------- Schematic builder ----------
class Schematic:
    def __init__(self):
        self.symbols = []     # list of dicts
        self.wires = []
        self.labels = []      # local labels
        self.glabels = []     # global labels
        self.junctions = []
        self.noconnects = []
        self.texts = []
        self.powers = []      # power symbol instances

    def add_symbol(self, lib_id, ref, value, footprint, datasheet, x, y, rotation=0):
        self.symbols.append({
            "lib_id": lib_id,
            "ref": ref,
            "value": value,
            "footprint": footprint,
            "datasheet": datasheet,
            "x": x, "y": y, "rot": rotation,
        })

    def add_wire(self, x1, y1, x2, y2):
        self.wires.append((x1, y1, x2, y2))

    def add_label(self, name, x, y, angle=0):
        self.labels.append((name, x, y, angle))

    def add_glabel(self, name, x, y, angle=0, shape="bidirectional"):
        self.glabels.append((name, x, y, angle, shape))

    def add_junction(self, x, y):
        self.junctions.append((x, y))

    def add_noconnect(self, x, y):
        self.noconnects.append((x, y))

    def add_text(self, text, x, y, size=2.0):
        self.texts.append((text, x, y, size))

    def add_power(self, net, x, y, angle=0):
        self.powers.append((net, x, y, angle))

    def pin_at(self, ref, pin_num, sym_lib_lookup):
        """Return (x, y) in schematic space for the given instance reference & pin number."""
        sym_inst = next(s for s in self.symbols if s["ref"] == ref)
        lib_sym = sym_lib_lookup(sym_inst["lib_id"])
        if lib_sym is None:
            raise ValueError(f"Library symbol not found: {sym_inst['lib_id']}")
        pin = lib_sym.pins.get(pin_num)
        if pin is None:
            raise ValueError(f"Pin {pin_num} not found on {ref} ({lib_sym.name})")
        return to_schematic(pin.x, pin.y, sym_inst["x"], sym_inst["y"], sym_inst["rot"])

    def emit(self):
        """Render the schematic to KiCad 20250114 format."""
        out = []
        out.append('(kicad_sch')
        out.append('  (version 20250114)')
        out.append('  (generator "eeschema")')
        out.append('  (generator_version "9.0")')
        out.append(f'  (uuid "{uid("root")}")')
        out.append('  (paper "A3")')
        out.append('  (title_block')
        out.append('    (title "Balloon Relay Board - C3+RP2040 Dual-MCU (Variant 3)")')
        out.append('    (date "2026-08-05")')
        out.append('    (rev "0.1")')
        out.append('    (company "balloon-tracker")')
        out.append('    (comment 1 "Variant 3 from SCHEMATIC-PLAN.md")')
        out.append('    (comment 2 "App MCU: ESP32-C3 (WiFi/BLE/GPS/Sensors); Radio MCU: RP2040 (LR2021 SPI)")')
        out.append('  )')

        # lib_symbols: empty — let KiCad resolve via global lib + project sym-lib-table
        # (this is what hub_board_diy.kicad_sch uses successfully)
        out.append('  (lib_symbols)')

        # Symbols
        for s in self.symbols:
            lib_sym = symbol_lib_lookup_global(s["lib_id"])
            out.append(f'  (symbol (lib_id "{s["lib_id"]}") (at {s["x"]} {s["y"]} {s["rot"]}) (unit 1)')
            out.append('    (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)')
            out.append(f'    (uuid "{uid("sym." + s["ref"])}")')
            out.append(f'    (property "Reference" "{s["ref"]}" (at {s["x"]} {s["y"]-6} 0) (effects (font (size 1.27 1.27))))')
            out.append(f'    (property "Value" "{s["value"]}" (at {s["x"]} {s["y"]+6} 0) (effects (font (size 1.27 1.27))))')
            out.append(f'    (property "Footprint" "{s["footprint"]}" (at {s["x"]} {s["y"]} 0) (effects (font (size 1.27 1.27)) hide))')
            out.append(f'    (property "Datasheet" "{s["datasheet"]}" (at {s["x"]} {s["y"]} 0) (effects (font (size 1.27 1.27)) hide))')
            if lib_sym:
                for pnum in sorted(lib_sym.pins.keys(), key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else x)):
                    pin_uuid = uid("sym." + s["ref"] + ".pin" + str(pnum))
                    out.append(f'    (pin "{pnum}" (uuid "{pin_uuid}"))')
            out.append('  )')

        # Power symbols
        for net, x, y, ang in self.powers:
            pwr_lib_id = "power:GND" if net == "GND" else ("power:+3.3V" if net == "3V3" else "power:+5V")
            pwr_sym = symbol_lib_lookup_global(pwr_lib_id)
            out.append(f'  (symbol (lib_id "{pwr_lib_id}") (at {x} {y} {ang}) (unit 1)')
            out.append('    (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)')
            out.append(f'    (uuid "{uid(f"pwr.{net}.{x}.{y}")}")')
            out.append(f'    (property "Reference" "#PWR?" (at {x} {y-3} 0) (effects (font (size 1.27 1.27)) hide))')
            out.append(f'    (property "Value" "{net}" (at {x} {y+3} 0) (effects (font (size 1.27 1.27))))')
            out.append(f'    (property "Footprint" "" (at {x} {y} 0) (effects (font (size 1.27 1.27)) hide))')
            out.append(f'    (property "Datasheet" "" (at {x} {y} 0) (effects (font (size 1.27 1.27)) hide))')
            if pwr_sym:
                for pnum in pwr_sym.pins.keys():
                    out.append(f'    (pin "{pnum}" (uuid "{uid(f"pwr.{net}.{x}.{y}.pin{pnum}")}"))')
            out.append('  )')

        # Wires
        for x1, y1, x2, y2 in self.wires:
            out.append(f'  (wire (pts (xy {x1} {y1}) (xy {x2} {y2})) (stroke (width 0) (type default)) (uuid "{uid(f"w.{x1}.{y1}.{x2}.{y2}")}"))')

        # Junctions
        for x, y in self.junctions:
            out.append(f'  (junction (at {x} {y}) (diameter 0) (color 0 0 0 0) (uuid "{uid(f"j.{x}.{y}")}"))')

        # No-connects
        for x, y in self.noconnects:
            out.append(f'  (no_connect (at {x} {y}) (uuid "{uid(f"nc.{x}.{y}")}"))')

        # Labels
        for name, x, y, ang in self.labels:
            out.append(f'  (label "{name}" (at {x} {y} {ang}) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid "{uid(f"l.{name}.{x}.{y}")}") (fields_autoplaced yes))')

        # Global labels
        for name, x, y, ang, shape in self.glabels:
            out.append(f'  (global_label "{name}" (shape {shape}) (at {x} {y} {ang}) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid "{uid(f"g.{name}.{x}.{y}")}") (fields_autoplaced yes)')
            out.append(f'    (property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {x} {y} 0) (effects (font (size 1.27 1.27)) (justify left bottom) hide yes)))')
            out.append('  )')

        # Texts
        for text, x, y, size in self.texts:
            # escape quotes
            esc = text.replace('"', '\\"')
            out.append(f'  (text "{esc}" (exclude_from_sim no) (at {x} {y} 0) (effects (font (size {size} {size}) bold yes) (justify left bottom)) (uuid "{uid(f"t.{x}.{y}")}"))')

        # Sheet instances (single sheet — required by ERC in 9.0)
        out.append('  (sheet_instances')
        out.append('    (path "/" (page "1"))')
        out.append('  )')

        out.append(')')
        return "\n".join(out)


# ---------- Global symbol library ----------
GLIB = SymbolLib()
GLIB_RAW = {}  # raw bodies

def load_libraries():
    std = Path("/usr/share/kicad/symbols")
    custom = Path("/home/c03rad0r/repos/balloon-fresh/tracker/hardware/schematics/v_c3_rp2040/balloon_symbols.kicad_sym")

    for lib_id, lib_file in [
        ("Device", std / "Device.kicad_sym"),
        ("Connector", std / "Connector.kicad_sym"),
        ("Connector_Generic", std / "Connector_Generic.kicad_sym"),
        ("Diode", std / "Diode.kicad_sym"),
        ("MCU_RaspberryPi", std / "MCU_RaspberryPi.kicad_sym"),
        ("RF_Module", std / "RF_Module.kicad_sym"),
        ("RF_GPS", std / "RF_GPS.kicad_sym"),
        ("Sensor_Pressure", std / "Sensor_Pressure.kicad_sym"),
        ("power", std / "power.kicad_sym"),
        ("balloon_symbols", custom),
    ]:
        if lib_file.exists():
            GLIB.load(lib_id, lib_file)

def symbol_lib_lookup_global(lib_id):
    libname, symname = lib_id.split(":", 1)
    return GLIB.libs.get(symname)


# Cache raw text bodies so we can emit them in lib_symbols
class SymbolWithRaw(Symbol):
    def __init__(self, name, body, lib_name):
        super().__init__(name, body, lib_name)
        self.raw_body = body


# Re-wire Symbol class to keep raw
Symbol.raw_body = property(lambda self: self._raw)
_orig_init = Symbol.__init__
def _new_init(self, name, body, lib_name):
    _orig_init(self, name, body, lib_name)
    self._raw = body
Symbol.__init__ = _new_init


if __name__ == "__main__":
    load_libraries()
    # Sanity check: print ESP32-C3 pin positions
    s = GLIB.libs.get("ESP32-C3-WROOM-02")
    if s:
        print("ESP32-C3-WROOM-02 pins:")
        for pnum, p in sorted(s.pins.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
            print(f"  {pnum}: {p.name} @ ({p.x}, {p.y}) angle={p.angle}")
    s2 = GLIB.libs.get("RP2040")
    if s2:
        print("\nRP2040 pins (first 10):")
        for pnum, p in list(sorted(s2.pins.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999))[:10]:
            print(f"  {pnum}: {p.name} @ ({p.x}, {p.y}) angle={p.angle}")
    s3 = GLIB.libs.get("TPS7A0233PDBVR")
    if s3:
        print("\nTPS7A0233PDBVR pins:")
        for pnum, p in sorted(s3.pins.items()):
            print(f"  {pnum}: {p.name} @ ({p.x}, {p.y}) angle={p.angle}")
    s4 = GLIB.libs.get("LR2021F33")
    if s4:
        print("\nLR2021F33 pins:")
        for pnum, p in sorted(s4.pins.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
            print(f"  {pnum}: {p.name} @ ({p.x}, {p.y}) angle={p.angle}")
    s5 = GLIB.libs.get("C")
    if s5:
        print("\nDevice:C pins:")
        for pnum, p in sorted(s5.pins.items()):
            print(f"  {pnum}: {p.name} @ ({p.x}, {p.y}) angle={p.angle}")
    s6 = GLIB.libs.get("R")
    if s6:
        print("\nDevice:R pins:")
        for pnum, p in sorted(s6.pins.items()):
            print(f"  {pnum}: {p.name} @ ({p.x}, {p.y}) angle={p.angle}")
    s7 = GLIB.libs.get("GND")
    if s7:
        print("\npower:GND pins:")
        for pnum, p in sorted(s7.pins.items()):
            print(f"  {pnum}: {p.name} @ ({p.x}, {p.y}) angle={p.angle}")
    s8 = GLIB.libs.get("MAX-M10S")
    if s8:
        print("\nMAX-M10S pins:")
        for pnum, p in sorted(s8.pins.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
            print(f"  {pnum}: {p.name} @ ({p.x}, {p.y}) angle={p.angle}")
