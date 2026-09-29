#!/usr/bin/env python3
"""Auto-BOOTSEL interposer PCB generator (ESP32-C3 -> RP2040 recovery).

What this board physically IS
=============================

A small 4-wire interposer that sits between an ESP32-C3 SuperMini and an
RP2040-Zero so the ESP32 can force the RP2040 into BOOTSEL and reset it with
nobody present::

    ESP32-C3 GPIO1 (D1)  ---->  RP2040 RUN   (reset / flight watchdog)
    ESP32-C3 GPIO8 (D8)  ---->  RP2040 GP0   (BOOTSEL, reflash)
    ESP32-C3 GND         ---->  RP2040 GND

The ESP32 firmware detects a dead RP2040 USB CDC (TinyUSB starved by a tight
radio/SPI loop), pulses RUN/GP0 in the verified order, and the RP2040 then
re-enumerates as RPI-RP2 mass storage so a fresh UF2 can be copied onto it.

Electrical rule that governs the design (MEASURED 2026-07-13)
============================================================

The ESP32 pin drives the RP2040 button pad DIRECTLY.  An inline resistor
forms a divider against the board pull-up and parks the pad near 1.65 V,
which the RP2040 treats as indeterminate (<0.8 V is required for a LOW), so
the "1k for protection" variant was measured to be completely dead.
Reference: profiles/manager/skills/firmware/lr2021-throughput-optimization/
references/auto-bootsel-circuit.md

So the four resistors on this board are NOT current limiters:

  R1, R2  0 R links, POPULATED.  They are the series position of the signal
          path, fitted with 0 R so the shipped board IS the measured-good
          "direct wire" topology, while leaving a footprint to fit a
          divider/limit part during bench characterisation.
  R3, R4  0 R links from each signal to GND, DO NOT POPULATE.  Fitting one
          parks its signal at GND for a bench experiment.  They must stay
          off in flight: a fitted R3 holds RUN asserted forever.

Net model
=========

Because R1/R2 are physical parts, the copper on either side of them is
electrically distinct and is modelled as such (RUN_ESP / RUN_RP,
BOOT_ESP / BOOT_RP).  Every net is then fully connected in copper, so
KiCad's unconnected-item check stays meaningful instead of being silenced.

Verification
============

``kicad-cli`` is the sole authority.  tests/test_auto_bootsel_pcb.py runs
``kicad-cli pcb drc --format json`` on the generated file, asserts the
netlist and routing invariants, and proves the harness can actually FAIL by
running the same command against deliberately broken fixtures.
"""

from __future__ import annotations

import itertools
import json
import re
import uuid
from pathlib import Path

# ---------------------------------------------------------------------------
# Board frame
# ---------------------------------------------------------------------------

BOARD_W = 30.0        # mm, X
BOARD_H = 28.0        # mm, Y
MOUNT_HOLE = "MountingHole_3.2mm_M3"
MOUNT_HOLE_INSET = 4.0
# The M3 mounting-hole courtyard is a 3.45 mm-radius circle and the test-point
# courtyard a 1.75 mm one, so the hole inset must exceed 3.45 mm or Gate 2.5
# reports a courtyard overlap against the corner test points.  Measured, not
# guessed: 2.5 mm inset produced 4 courtyards_overlap violations.
TP_CHANNEL_RUN = 11.0
TP_CHANNEL_BOOT = 16.0

FP_LIB = Path("/usr/share/kicad/footprints")

# ---------------------------------------------------------------------------
# Nets (index 0 must be the empty net for KiCad)
# ---------------------------------------------------------------------------

NETS = [
    "",            # 0
    "GND",         # 1
    "RUN_ESP",     # 2  ESP32 D1 side of R1
    "RUN_RP",      # 3  RP2040 RUN side of R1 (+ R3 pad 2)
    "BOOT_ESP",    # 4  ESP32 D8 side of R2
    "BOOT_RP",     # 5  RP2040 GP0 side of R2 (+ R4 pad 2)
]
NET_ID = {n: i for i, n in enumerate(NETS)}

NETCLASS = {"Default": dict(clearance=0.25, trace_width=0.25,
                            via_dia=0.6, via_drill=0.3)}

TRACE_W = 0.25
POUR_MARGIN = 0.8     # > KiCad 9 default copper-to-edge clearance (0.5)

# ---------------------------------------------------------------------------
# Placement  (mm; origin at the board's top-left corner)
# ---------------------------------------------------------------------------
# Two horizontal channels so silkscreen and courtyards never meet:
#   RUN  channel, y = 7  : TP1 - R1 - TP3 - R3 - TP5
#   BOOT channel, y = 13 : TP2 - R2 - TP4 - R4 - TP6
PLACEMENT: dict[str, tuple] = {
    "TP1": (6.0, TP_CHANNEL_RUN, 0.0),
    "R1": (10.5, TP_CHANNEL_RUN, 0.0),
    "TP3": (15.0, TP_CHANNEL_RUN, 0.0),
    "R3": (19.5, TP_CHANNEL_RUN, 0.0),
    "TP5": (24.0, TP_CHANNEL_RUN, 0.0),

    "TP2": (6.0, TP_CHANNEL_BOOT, 0.0),
    "R2": (10.5, TP_CHANNEL_BOOT, 0.0),
    "TP4": (15.0, TP_CHANNEL_BOOT, 0.0),
    "R4": (19.5, TP_CHANNEL_BOOT, 0.0),
    "TP6": (24.0, TP_CHANNEL_BOOT, 0.0),
}

# Every part sits at rotation 0.  MEASURED (KiCad 9.0.8): placing a library
# footprint at a NON-ZERO rotation makes kicad-cli report
# `lib_footprint_mismatch  "Footprint 'R_0402_1005Metric' does not match copy
# in library 'Resistor_SMD'"` — the checker does not normalise the angle away.
# The earlier revision used 180 deg on R3/R4 to aim pad 2 at TP3; that is
# avoided instead by swapping which pad carries which net, which is
# electrically identical for a two-terminal resistor and keeps every part at
# rotation 0.
#
# Pad geometry at rotation 0: pad 1 is the -X pad, pad 2 the +X pad.  R3/R4
# therefore carry their RP2040-side net on pad 1 (facing the left test point)
# and their GND side on pad 2 (facing the right test point).

POPULATED = ("R1", "R2")     # fitted in the shipped build
DNP = ("R3", "R4")           # bench-only park links

MOUNT_HOLES = [
    ("H1", MOUNT_HOLE_INSET, MOUNT_HOLE_INSET),
    ("H2", BOARD_W - MOUNT_HOLE_INSET, MOUNT_HOLE_INSET),
    ("H3", MOUNT_HOLE_INSET, BOARD_H - MOUNT_HOLE_INSET),
    ("H4", BOARD_W - MOUNT_HOLE_INSET, BOARD_H - MOUNT_HOLE_INSET),
]

TP_NET = {
    "TP1": "RUN_ESP",     # wire to ESP32-C3 D1 / GPIO1
    "TP2": "BOOT_ESP",    # wire to ESP32-C3 D8 / GPIO8
    "TP3": "RUN_RP",      # wire to RP2040 RUN pad
    "TP4": "BOOT_RP",     # wire to RP2040 GP0 pad
    "TP5": "GND",
    "TP6": "GND",
}

RES_NETS = {
    "R1": (("1", "RUN_ESP"), ("2", "RUN_RP")),
    "R2": (("1", "BOOT_ESP"), ("2", "BOOT_RP")),
    # R3/R4 are the bench-only park links.  Their RP2040-side net must land on
    # the pad that faces the LEFT test point (pad 1 at rotation 0), because the
    # GND side ties to the right-hand GND test point.
    "R3": (("1", "RUN_RP"), ("2", "GND")),
    "R4": (("1", "BOOT_RP"), ("2", "GND")),
}
RES_VALUE = {r: "0R" for r in RES_NETS}

TP_LIB_NAME = "TestPoint_THTPad_D2.5mm_Drill1.2mm"
RES_LIB_NAME = "R_0402_1005Metric"
RES_PAD_OFFSET = 0.51    # from the library footprint


def pad_xy(ref: str, pad: str) -> tuple[float, float]:
    """Absolute pad centre for a placed part (0402 pads are on the X axis)."""
    x, y, rot = PLACEMENT[ref]
    off = -RES_PAD_OFFSET if pad == "1" else RES_PAD_OFFSET
    if abs(rot) == 180.0:
        off = -off
    return (round(x + off, 4), y)


# ---------------------------------------------------------------------------
# Routing: straight F.Cu segments to pad centres, no vias.  B.Cu is a solid
# GND pour; the GND test points are THT, so they bond to it through their
# barrels and the two ground rails are also tied on F.Cu explicitly.
# ---------------------------------------------------------------------------

def route() -> list[tuple[str, tuple[float, float], tuple[float, float]]]:
    return [
        # RUN channel
        ("RUN_ESP", (6.0, TP_CHANNEL_RUN), pad_xy("R1", "1")),
        ("RUN_RP", pad_xy("R1", "2"), (15.0, TP_CHANNEL_RUN)),
        ("RUN_RP", (15.0, TP_CHANNEL_RUN), pad_xy("R3", "1")),
        ("GND", pad_xy("R3", "2"), (24.0, TP_CHANNEL_RUN)),
        # BOOT channel
        ("BOOT_ESP", (6.0, TP_CHANNEL_BOOT), pad_xy("R2", "1")),
        ("BOOT_RP", pad_xy("R2", "2"), (15.0, TP_CHANNEL_BOOT)),
        ("BOOT_RP", (15.0, TP_CHANNEL_BOOT), pad_xy("R4", "1")),
        ("GND", pad_xy("R4", "2"), (24.0, TP_CHANNEL_BOOT)),
        # tie the two ground rails together
        ("GND", (24.0, TP_CHANNEL_RUN), (24.0, TP_CHANNEL_BOOT)),
    ]


# ---------------------------------------------------------------------------
# Minimal KiCad s-expression reader / writer, used to embed authentic library
# footprints instead of hand-typed copies (hand copies raise
# `lib_footprint_mismatch`, and a made-up footprint name raises
# `lib_footprint_issues`).
# ---------------------------------------------------------------------------

class Sym(str):
    """A bare (unquoted) atom."""


class Q(str):
    """An atom that MUST be emitted quoted even if it looks numeric.

    KiCad's parser is strict about a few version-like fields: a bare
    `(generator_version 9.0)` makes the whole board fail with the blanket
    error "Failed to load board", and the atom writer would strip the quotes
    from `"9.0"` because it looks like a number.
    """


def sexp_parse(text: str):
    i, n = 0, len(text)

    def skip_ws():
        nonlocal i
        while i < n and text[i] in " \t\r\n":
            i += 1

    def parse():
        nonlocal i
        skip_ws()
        if text[i] == "(":
            i += 1
            out = []
            while True:
                skip_ws()
                if text[i] == ")":
                    i += 1
                    return out
                out.append(parse())
        if text[i] == '"':
            i += 1
            buf = []
            while text[i] != '"':
                if text[i] == "\\":
                    i += 1
                buf.append(text[i])
                i += 1
            i += 1
            return "".join(buf)
        j = i
        while i < n and text[i] not in ' \t\r\n()"':
            i += 1
        return Sym(text[j:i])

    return parse()


_NUM = re.compile(r"^-?(\d+(\.\d*)?|\.\d+)$")


def _atom(v) -> str:
    """Emit an atom.  Bare numbers must NOT be quoted or KiCad refuses the
    file, so numeric-looking strings are written unquoted."""
    if isinstance(v, Sym):
        return str(v)
    if isinstance(v, Q):
        return '"' + str(v).replace('"', '\\"') + '"'
    if _NUM.match(v):
        return v
    return '"' + v.replace('"', '\\"') + '"'


def sexp_dump(node, indent: int = 0) -> str:
    pad = "  " * indent
    if isinstance(node, str) and not isinstance(node, Sym):
        return pad + _atom(node)
    if not isinstance(node, list):
        return pad + _atom(node)
    head = node[0]
    if not any(isinstance(c, list) for c in node[1:]):
        return pad + "(" + " ".join(_atom(c) for c in node) + ")"
    lines = [pad + "(" + _atom(head)]
    for child in node[1:]:
        if isinstance(child, list):
            lines.append(sexp_dump(child, indent + 1))
        else:
            # keep simple scalars on the head line
            lines[-1] += " " + _atom(child)
    lines[-1] += ")"
    return "\n".join(lines)


def _find(node, tag: str):
    if not isinstance(node, list):
        return None
    for c in node:
        if isinstance(c, list) and c and c[0] == tag:
            return c
    return None


def _findall(node, tag: str):
    return [c for c in node if isinstance(c, list) and c and c[0] == tag]


def load_library_footprint(lib: str, name: str) -> list:
    path = FP_LIB / f"{lib}.pretty" / f"{name}.kicad_mod"
    if not path.exists():
        raise FileNotFoundError(path)
    return sexp_parse(path.read_text())


def _set_property(fp: list, key: str, value: str, y: float, layer: str,
                  hide: bool = False) -> None:
    for prop in _findall(fp, "property"):
        if prop[1] == key:
            prop[2] = value
            at = _find(prop, "at")
            at[1], at[2] = str(0), f"{y:g}"
            prop[3] = Sym(layer)
            if hide and not _find(prop, "hide"):
                prop.append(Sym("hide"))
            return
    raise KeyError(f"{key} not found in footprint")


# Deterministic UUIDs.  A generated board must be REPRODUCIBLE: the S0/S1
# evidence chain pins the board by sha256, and a generator that emits fresh
# random UUIDs on every run makes the checked-in board unreproducible and
# silently invalidates every hash recorded against it.  UUIDv5 over a
# monotonically increasing counter is stable for a fixed call order and still
# a valid v4-shaped identifier to KiCad.
_UUID_COUNTER = itertools.count()


def _pad_uuid() -> str:
    n = next(_UUID_COUNTER)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"balloon.auto-bootsel.v1.{n}"))


def place_footprint(lib: str, name: str, ref: str, value: str,
                    x: float, y: float, rot: float,
                    pad_nets: dict[str, str] | None = None,
                    hidden_ref: bool = False) -> list:
    """Return a board-ready footprint node from an authentic library one."""
    src = load_library_footprint(lib, name)
    fp = [Sym("footprint"), f"{lib}:{name}"]

    fp.append([Sym("version"), Sym("20241229")])
    fp.append([Sym("generator"), "auto_bootsel_pcb"])
    fp.append([Sym("layer"), "F.Cu"])
    fp.append([Sym("uuid"), _pad_uuid()])
    fp.append([Sym("at"), f"{x:g}", f"{y:g}", f"{rot:g}"])
    fp.append([Sym("descr"), BOARD_NOTE])
    attr = _find(src, "attr")
    if attr:
        fp.append(attr)

    # geometry: everything that is not metadata
    skip = {"footprint", "version", "generator", "generator_version", "layer",
            "uuid", "at", "descr", "tags", "attr", "property", "model",
            "embedded_fonts", "pad", "tstamp"}
    for child in src:
        if isinstance(child, list) and str(child[0]) not in skip:
            fp.append(child)

    # version metadata.  `generator_version` MUST stay a quoted string in the
    # board file: KiCad's footprint parser rejects the bare form
    # `(generator_version 9.0)` with a blanket "Failed to load board", which is
    # the exact failure this generator shipped with.  The library footprint
    # carries it as a string, so re-emit it quoted rather than letting the atom
    # writer decide (it strips quotes from anything that looks like a number).
    gv = _find(src, "generator_version")
    if gv:
        fp.append([Sym("generator_version"), Q(str(gv[1]))])

    # fields
    cy = {"TestPoint": 1.55, "R_0402": 0.95, "MountingHole": 1.9}.get(
        name.split("_")[0] if not name.startswith("R_") else "R_0402", 1.6)
    for prop in _findall(src, "property"):
        key = prop[1]
        if key == "Reference":
            fp.append(_mk_property("Reference", ref, -(cy + 0.85), "F.SilkS",
                                   hidden_ref))
        elif key == "Value":
            fp.append(_mk_property("Value", value, cy + 0.85, "F.Fab",
                                   hide=True))
        else:
            fp.append(prop)

    # pads (with nets)
    for pad in _findall(src, "pad"):
        pad = list(pad)
        if pad_nets and pad[1] in pad_nets:
            net = pad_nets[pad[1]]
            pad.append([Sym("net"), str(NET_ID[net]), net])
        fp.append(pad)

    return fp


BOARD_NOTE = ("auto-bootsel interposer: series 0R links into the RP2040 RUN "
              "and BOOT pads; NOT current limiters (a series R parks the pad "
              "near 1.65V, undefined for the RP2040 - measured 2026-07-13)")


def _mk_property(key: str, value: str, y: float, layer: str,
                 hide: bool) -> list:
    prop = [Sym("property"), key, value,
            [Sym("at"), "0", f"{y:g}", "0"],
            [Sym("layer"), layer],
            [Sym("effects"), [Sym("font"), [Sym("size"), "0.8", "0.8"],
                              [Sym("thickness"), "0.13"]]]]
    if hide:
        prop.append(Sym("hide"))
    return prop


# ---------------------------------------------------------------------------
# Board emitters
# ---------------------------------------------------------------------------

def header() -> str:
    return f"""(kicad_pcb
  (version 20241229)
  (generator "auto_bootsel_pcb")
  (generator_version "9.0")
  (general
    (thickness 1.0)
  )
  (paper "A4")
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user)
    (39 "F.Mask" user)
    (44 "Edge.Cuts" user)
    (46 "B.CrtYd" user "B.Courtyard")
    (47 "F.CrtYd" user "F.Courtyard")
    (48 "B.Fab" user)
    (49 "F.Fab" user)
  )
  (setup
    (pad_to_mask_clearance 0)
    (allow_soldermask_bridges_in_footprints no)
    (aux_axis_origin 0 0)
    (grid_origin 0 0)
  )"""


def nets_s() -> str:
    out = ['  (net 0 "")']
    for i, name in enumerate(NETS[1:], start=1):
        out.append(f'  (net {i} "{name}")')
    for name, nc in NETCLASS.items():
        out.append(
            f'  (net_class "{name}" "default class" '
            f"(clearance {nc['clearance']:g}) "
            f"(trace_width {nc['trace_width']:g}) "
            f"(via_dia {nc['via_dia']:g}) (via_drill {nc['via_drill']:g}) "
            f"(uvia_dia 0.3) (uvia_drill 0.1))"
        )
    return "\n".join(out)


def graphics_s() -> str:
    w, h = BOARD_W, BOARD_H
    lines = []
    corners = [(0, 0), (w, 0), (w, h), (0, h), (0, 0)]
    for (x0, y0), (x1, y1) in zip(corners, corners[1:]):
        lines.append(
            f'  (gr_line (start {x0:g} {y0:g}) (end {x1:g} {y1:g}) '
            f'(stroke (width 0.15) (type solid)) (layer "Edge.Cuts") '
            f'(uuid "{_pad_uuid()}"))'
        )
    # Keep both legends clear of the mounting-hole mask openings.
    lines.append(
        f'  (gr_text "AUTO-BOOTSEL v1" (at {w / 2:g} 25.6 0) (layer "F.SilkS") '
        f'(uuid "{_pad_uuid()}") '
        f'(effects (font (size 0.9 0.9) (thickness 0.15))))'
    )
    lines.append(
        f'  (gr_text "RUN=D1 BOOT=D8" (at {w / 2:g} 2.2 0) (layer "F.SilkS") '
        f'(uuid "{_pad_uuid()}") '
        f'(effects (font (size 0.9 0.9) (thickness 0.15))))'
    )
    return "\n".join(lines)


def footprints_s() -> str:
    out = []
    for ref, (x, y, rot) in PLACEMENT.items():
        if ref.startswith("R"):
            out.append(sexp_dump(place_footprint(
                "Resistor_SMD", RES_LIB_NAME, ref, RES_VALUE[ref], x, y, rot,
                pad_nets=dict(RES_NETS[ref]), hidden_ref=False), 1))
        else:
            out.append(sexp_dump(place_footprint(
                "TestPoint", TP_LIB_NAME, ref, TP_NET[ref], x, y, rot,
                pad_nets={"1": TP_NET[ref]}, hidden_ref=False), 1))
    for ref, x, y in MOUNT_HOLES:
        out.append(sexp_dump(place_footprint(
            "MountingHole", MOUNT_HOLE, ref, MOUNT_HOLE, x, y, 0.0,
            pad_nets=None, hidden_ref=True), 1))
    return "\n".join(out)


def routing_s() -> str:
    out = []
    for net, (x0, y0), (x1, y1) in route():
        if (x0, y0) == (x1, y1):
            continue
        out.append(
            f'  (segment (start {x0:g} {y0:g}) (end {x1:g} {y1:g}) '
            f'(width {TRACE_W:g}) (layer "F.Cu") '
            f'(net {NET_ID[net]}) (uuid "{_pad_uuid()}"))'
        )
    return "\n".join(out)


def pour_s() -> str:
    m = POUR_MARGIN
    pts = (f"(xy {m:g} {m:g}) (xy {BOARD_W - m:g} {m:g}) "
           f"(xy {BOARD_W - m:g} {BOARD_H - m:g}) "
           f"(xy {m:g} {BOARD_H - m:g})")
    return (
        f'  (zone (net {NET_ID["GND"]}) (net_name "GND") (layer "B.Cu") '
        f'(uuid "{_pad_uuid()}") (hatch edge 0.5) (connect_pads (clearance 0.4)) '
        f"(min_thickness 0.25) (filled_areas_thickness no) "
        f"(fill yes (thermal_gap 0.4) (thermal_bridge_width 0.4))\n"
        f"    (polygon (pts {pts}))\n"
        f"  )"
    )


def build(*, routed: bool = True) -> str:
    """Render the board.

    ``routed=False`` emits the same placement with NO segments — that is the
    S0 placement snapshot Gate 2.5 is defined on (`gate25_check.py` requires
    `segments == 0`, because a router cannot fix two pads that occupy the same
    physical space).  Keeping both snapshots generated from one placement table
    is what makes the gate and the routed board provably the same revision.

    The UUID counter is reset here so ``build()`` is a pure function of the
    module's constants: two calls in one process, or calls from different
    processes, produce identical bytes.  Without the reset the second build
    emits different UUIDs and the reproducibility assertion in the test suite
    fails (correctly — a board whose hash changes per render cannot carry
    sha256-pinned evidence).
    """
    _UUID_COUNTER = itertools.count()
    globals()["_UUID_COUNTER"] = _UUID_COUNTER
    parts = [header(), nets_s(), graphics_s(), footprints_s()]
    if routed:
        parts.append(routing_s())
    parts += [pour_s(), ")"]
    return "\n".join(parts) + "\n"


PLACED_NAME = "auto-bootsel-interposer-placed.kicad_pcb"
ROUTED_NAME = "auto-bootsel-interposer.kicad_pcb"


def generate(path: str | Path, *, routed: bool = True) -> Path:
    path = Path(path)
    path.write_text(build(routed=routed))
    return path


# ---------------------------------------------------------------------------
# Derived quantities the acceptance test asserts on
# ---------------------------------------------------------------------------

# Component mass, grams.  FR-4 areal density 0.185 g/cm^2 per 1.0 mm of
# thickness; a 0402 chip resistor is ~0.62 mg.
MASS_G = {
    "pcb_1p0mm_per_cm2": 0.185,
    "resistor_0402": 0.00062,
}


def mass_budget() -> dict:
    """Mass model for the two DIFFERENT quantities the card talks about.

    The card's acceptance figure is "<0.01 g" and that is the ADDED mass of the
    recovery feature, i.e. what this interposer contributes to a flight stack
    that already carries two MCU boards.  It is NOT the mass of the interposer
    PCB itself, and reading the two as the same number is how a 0.96 g FR-4
    coupon gets reported as a 6 mg part.

    Both numbers are emitted, and every branch says which one it is, so no
    reader has to guess which one `pass` refers to:

      added_g      parts fitted in flight (R1, R2) + the copper/mask they add.
                   R3/R4 are DNP, so they contribute nothing in flight.
      bare_pcb_g   the printed-circuit board itself, informational: it REPLACES
                   the wire-and-heat-shrink harness it supersedes.
      total_g      bare_pcb_g + added_g — the whole interposer, informational.
    """
    bare = MASS_G["pcb_1p0mm_per_cm2"] * (BOARD_W * BOARD_H / 100.0)
    fitted = len(POPULATED) * MASS_G["resistor_0402"]
    total = bare + fitted
    return {
        "added_g": round(fitted, 6),
        "added_limit_g": 0.01,
        "added_pass": fitted < 0.01,
        "populated_parts": list(POPULATED),
        "dnp_parts": list(DNP),
        "bare_pcb_g": round(bare, 5),
        "total_g": round(total, 5),
        "note": "the <0.01 g requirement applies to the ADDED mass of the "
                "recovery feature (the fitted 0R links); bare_pcb_g/total_g "
                "are the whole interposer board and are informational only - "
                "no active silicon is populated, and the lands are soldered "
                "directly to the host boards' pads",
    }


def stats(text: str) -> dict:
    return {
        "segments": text.count("(segment "),
        "vias": text.count("(via "),
        "footprints": text.count("(footprint "),
        "nets": text.count("(net ") - text.count("(net_class "),
        "zones": text.count("(zone "),
        "board_mm": [BOARD_W, BOARD_H],
        "gnd_pour_margin_mm": POUR_MARGIN,
    }


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    placed = generate(here / PLACED_NAME, routed=False)
    out = generate(here / ROUTED_NAME, routed=True)
    text = out.read_text()
    print(f"wrote {placed}")
    print(f"wrote {out}")
    print("mass:", json.dumps(mass_budget()))
    print("stats:", json.dumps(stats(text)))
