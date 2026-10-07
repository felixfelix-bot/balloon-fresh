#!/usr/bin/env python3
"""bypass_diode_check.py — FAIL-CLOSED gate on the ADR-053 bypass-diode provision.

WHAT THIS GUARDS
================
ADR-053 requires that **every cell, or every series group of cells, in a solar
series string has a Schottky bypass diode across it**, cathode to the group's
positive terminal and anode to its negative terminal.  Without it, one cell that
goes OPEN, is SHORTED / reverse-stressed, or is merely SHADED takes the whole
6.0 V / 12-cell series string with it (ADR-006, ADR-049, ADR-051 §1.1).  With it,
a failure costs one cell (per-cell) or one group (per-group) instead of the array.

It also enforces the ADR-053 §2.2 sizing rule at the level a netlist can see: a
bypass position held by a **known under-rated part** (the 200 mA / 30 V BAT54
family the socket spec still names) is a defect, because the bypass path is a
**permanent continuous** 1.2 A path, not a shading transient, and the reverse
rating must clear the ≈9.58 V cold open-circuit stack (ADR-050 §3.2, ADR-051 §2.7).

WHAT IT PARSES
==============
* a KiCad **netlist** (`.net`, the authority on connectivity) — full check; or
* a KiCad **schematic** (`.kicad_sch`) — *label-level only*.  In schematic mode the
  script can NEVER return PASS and never returns FAIL either: a label scan sees
  names, not wires, so it cannot prove which nodes a diode's pins sit on.
  Schematic mode therefore returns UNDETERMINED with a pointed message and directs
  the caller to the exported netlist.  A checker that cannot see the answer must
  not claim one.

WHICH BOARD
===========
Run this on **each board's** netlist.  On the **hub** netlist the solar groups are
the four wing interfaces (`J_W1..J_W4`), each carrying one wing's 3-cell series
group, plus any hub-mounted cells (`PVA<n>`).  A **per-cell** arrangement puts three
diodes on each **wing** board — check those by running this on the wing netlist.
The invariant is the same on either board: no cell / group without a diode.

EXIT CODES
==========
    0   PASS          — every solar group has a correctly polarised, adequately rated diode
    1   FAIL          — a VIOLATION was detected (a named rule below fired)
    2   UNDETERMINED  — the answer cannot be established (unreadable input, no solar
                        group found, a diode polarity that cannot be resolved).
                        Non-zero on purpose: never silent-pass.

Anything other than 0 is a failure.  Exit 1 and exit 2 are distinguished so a CI
caller can tell "the design is wrong" from "the design does not exist / cannot be read".

RULES (all fail-closed; the reason string names the rule)
=========================================================
B1  at least one solar series group is present                    (else UNDETERMINED)
    a group = a wing interface (J_W<n>, pad 1 = + / pad 4 = -) or a solar
    cell component (its two pins, polarity by pin function)
B2  every group has a bypass diode ACROSS it — a diode whose cathode node is the
    group's positive node and whose anode node is the group's negative node
                                                                  (else FAIL)
B3  a diode's polarity must be resolvable from its pin functions (K / A).  A diode
    with no readable polarity CANNOT be credited as a bypass       (else UNDETERMINED)
B4  a bypass diode must not be a KNOWN UNDER-RATED part.  The BAT54 family
    (200 mA / 30 V) is disqualified against the ≥2 A / 40 V requirement (else FAIL)
B5  a DNP bypass diode is reported as a note; with `--require-populated` it is a
    FAIL (ADR-051 §2.4 decision 4.2 mandates population on a cutter flight)

Usage
-----
    python3 scripts/bypass_diode_check.py
    python3 scripts/bypass_diode_check.py path/to/v9_flight.net
    python3 scripts/bypass_diode_check.py path/to/v9_flight.kicad_sch
    python3 scripts/bypass_diode_check.py path/to/x.net --require-populated
    python3 scripts/bypass_diode_check.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# --------------------------------------------------------------------------- #
# Names / identification (all fixed by ADR-046 §2.1, ADR-048, ADR-051, ADR-053)
# --------------------------------------------------------------------------- #

#: Wing interface reference; the four 4-pad hub-edge sockets.
WING_IFACE_RE = re.compile(r"^J_W([1-4])$")

#: Interface pad numbers (ADR-046 §2.1 / ADR-048 §2.3, order MUST match).
PAD_SOLAR_P = "1"   # the wing's solar POSITIVE terminal (the group's + node)
PAD_SOLAR_N = "4"   # the wing's solar NEGATIVE terminal (the group's - node)

#: On-board solar cell identification (ADR-051 names hub cells `PVA<n>`).
CELL_REF_RE = re.compile(r"^(?:PVA|HUB_C|HUBPV|HUB_SOLAR)\d+$")
CELL_PART_HINTS = ("solarcell", "solar_cell", "solar_cel", "pva", "hub_pv", "hub_cell",
                   "photovolt")

#: A component is treated as a diode if its symbol/part hints at one.
DIODE_PART_HINTS = ("d_schottky", "d_schotkky", "schottky", "diode")

#: Pin functions that name a diode's cathode / anode.
CATHODE_FUNCS = {"k", "c", "cathode"}
ANODE_FUNCS = {"a", "anode"}

#: Pin functions that name a solar cell's positive / negative terminal.
CELL_POS_FUNCS = {"+", "p", "pos", "positive"}
CELL_NEG_FUNCS = {"-", "n", "neg", "negative"}

#: ADR-053 §2.2 requirement: ≥2 A continuous, ≥40 V reverse.
REQUIRED_CURRENT_A = 2.0
REQUIRED_VOLTAGE_V = 40.0

#: Known part ratings, (continuous forward current A, reverse voltage V).  ONLY
#: parts listed here are judged; an unknown part produces a note, never a verdict,
#: so this table can never manufacture a failure it cannot justify.  The BAT54
#: entries are the disqualification ADR-053 §2.2 item 3 records.
KNOWN_RATINGS: dict[str, tuple[float, float]] = {
    "bat54": (0.200, 30.0),
    "bat54a": (0.200, 30.0),
    "bat54c": (0.200, 30.0),
    "bat54s": (0.200, 30.0),
    "bat54w": (0.200, 30.0),
    "1n5817": (1.0, 20.0),
    "1n5819": (1.0, 40.0),
    "sk14": (1.0, 40.0),
    "sk16": (1.0, 60.0),
    "b240": (2.0, 40.0),
    "b240a": (2.0, 40.0),
    "b250": (2.0, 50.0),
    "b260": (2.0, 60.0),
    "ss24": (2.0, 40.0),
    "ss26": (2.0, 60.0),
    "pmeg4020er": (2.0, 40.0),
    "pmeg4020e": (2.0, 40.0),
}

DEFAULT_NETLIST = "tracker/hardware/schematics/flight_board/v9_flight.net"

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_UNDETERMINED = 2


def normalise_part(value: str | None) -> str:
    """`"BAT54 (DNP)"` -> `"bat54"`; `"PMEG4020ER"` -> `"pmeg4020er"`."""
    if not value:
        return ""
    head = value.split("(")[0]          # drop any "(DNP)" / "(note)" suffix
    return re.sub(r"[^a-z0-9]", "", head.lower())


def rating_of(value: str | None) -> tuple[float, float] | None:
    """Return (I_cont, V_R) for a KNOWN part, else None (unknown -> no verdict)."""
    key = normalise_part(value)
    if not key:
        return None
    if key in KNOWN_RATINGS:
        return KNOWN_RATINGS[key]
    # try progressively shorter prefixes ("b240a" -> "b240", "bat54s" -> "bat54")
    for cut in range(len(key) - 1, 3, -1):
        if key[:cut] in KNOWN_RATINGS:
            return KNOWN_RATINGS[key[:cut]]
    return None


# --------------------------------------------------------------------------- #
# minimal s-expression reader (KiCad .net and .kicad_sch are both sexps)
# --------------------------------------------------------------------------- #

_TOKEN_RE = re.compile(r'"(?:[^"\\]|\\.)*"|\(|\)|[^\s()"]+')


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def parse_sexp(text: str):
    """Parse the first top-level s-expression in `text`. Raises ValueError."""
    tokens = _tokenize(text)
    pos = 0

    def parse():
        nonlocal pos
        if pos >= len(tokens):
            raise ValueError("unexpected end of input")
        tok = tokens[pos]
        pos += 1
        if tok == "(":
            out = []
            while True:
                if pos >= len(tokens):
                    raise ValueError("unbalanced '(' in s-expression")
                if tokens[pos] == ")":
                    pos += 1
                    return out
                out.append(parse())
        if tok == ")":
            raise ValueError("unexpected ')'")
        if tok.startswith('"') and tok.endswith('"') and len(tok) >= 2:
            return tok[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        return tok

    while pos < len(tokens) and tokens[pos] != "(":
        pos += 1
    return parse()


def _children(node, key):
    if not isinstance(node, list):
        return []
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def _first(node, key):
    got = _children(node, key)
    return got[0] if got else None


def _value(node, key):
    child = _first(node, key)
    if child is None or len(child) < 2:
        return None
    val = child[1]
    return val if isinstance(val, str) else None


# --------------------------------------------------------------------------- #
# netlist model
# --------------------------------------------------------------------------- #

class Component:
    def __init__(self, ref: str):
        self.ref = ref
        self.part = ""
        self.value = ""
        self.footprint = ""
        self.dnp = False
        self.pins: dict[str, str | None] = {}          # pin -> net name
        self.pinfunc: dict[str, str] = {}              # pin -> pinfunction string


class Group:
    """A series group of cells that needs a bypass diode across it."""

    def __init__(self, label: str, pos_net: str | None, neg_net: str | None,
                 kind: str, ref: str):
        self.label = label          # human name for messages
        self.pos_net = pos_net      # the group's + node
        self.neg_net = neg_net      # the group's - node
        self.kind = kind            # "wing-interface" | "solar-cell"
        self.ref = ref


class Netlist:
    def __init__(self):
        self.components: dict[str, Component] = {}
        self.nets: dict[str, list[tuple[str, str, str]]] = {}   # net -> [(ref, pin, func)]

    def net_of(self, ref: str, pin: str) -> str | None:
        comp = self.components.get(ref)
        if comp is None:
            return None
        return comp.pins.get(pin)

    def is_diode(self, comp: Component) -> bool:
        low = (comp.part or "").lower()
        if any(h in low for h in DIODE_PART_HINTS):
            return True
        vlow = (comp.value or "").lower()
        return any(h in vlow for h in ("schottky", "schotkky"))

    def cells(self) -> list[str]:
        out = []
        for ref, comp in self.components.items():
            if WING_IFACE_RE.match(ref):
                continue
            low = (comp.part or "").lower()
            if CELL_REF_RE.match(ref) or any(h in low for h in CELL_PART_HINTS):
                out.append(ref)
        return sorted(out)


def load_netlist(path: Path) -> Netlist:
    tree = parse_sexp(path.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(tree, list) or not tree or tree[0] != "export":
        raise ValueError("%s: not a KiCad netlist (no top-level 'export')" % path)

    nl = Netlist()

    comps = _first(tree, "components")
    if comps is None:
        raise ValueError("%s: netlist has no (components ...) section" % path)
    for comp in _children(comps, "comp"):
        ref = _value(comp, "ref")
        if ref is None:
            continue
        c = Component(ref)
        c.value = _value(comp, "value") or ""
        c.footprint = _value(comp, "footprint") or ""
        libsrc = _first(comp, "libsource")
        if libsrc is not None:
            c.part = _value(libsrc, "part") or ""
        # DNP lives either as a `(property (name "dnp"))` flag or in the value text.
        for prop in _children(comp, "property"):
            if (_value(prop, "name") or "").lower() == "dnp":
                c.dnp = True
        if "dnp" in c.value.lower():
            c.dnp = True
        nl.components[ref] = c

    nets = _first(tree, "nets")
    if nets is None:
        raise ValueError("%s: netlist has no (nets ...) section" % path)
    for net in _children(nets, "net"):
        name = _value(net, "name")
        if name is None:
            continue
        for node in _children(net, "node"):
            ref = _value(node, "ref")
            pin = _value(node, "pin")
            func = _value(node, "pinfunction") or ""
            if ref is None or pin is None:
                continue
            nl.nets.setdefault(name, []).append((ref, pin, func))
            comp = nl.components.get(ref)
            if comp is None:
                comp = nl.components[ref] = Component(ref)
            previous = comp.pins.get(pin)
            if previous is not None and previous != name:
                raise ValueError(
                    "%s: pad %s.%s appears in two nets (%s and %s)"
                    % (path, ref, pin, previous, name))
            comp.pins[pin] = name
            comp.pinfunc[pin] = func

    return nl


# --------------------------------------------------------------------------- #
# the checks
# --------------------------------------------------------------------------- #

class Report:
    def __init__(self):
        self.failures: list[str] = []
        self.undetermined: list[str] = []
        self.notes: list[str] = []
        self.checked: list[str] = []

    def fail(self, rule: str, msg: str) -> None:
        self.failures.append("%s: %s" % (rule, msg))

    def unknown(self, rule: str, msg: str) -> None:
        self.undetermined.append("%s: %s" % (rule, msg))

    def note(self, msg: str) -> None:
        self.notes.append(msg)

    def ok(self, msg: str) -> None:
        self.checked.append(msg)

    @property
    def exit_code(self) -> int:
        if self.failures:
            return EXIT_FAIL
        if self.undetermined:
            return EXIT_UNDETERMINED
        return EXIT_PASS


def solar_groups(nl: Netlist, rep: Report) -> list[Group]:
    """Every series group in the solar path that must carry a bypass diode.

    A wing interface J_W<n> is a group of that wing's 3 cells (its + is pad 1,
    its - is pad 4).  An on-board solar cell is a group of 1."""
    groups: list[Group] = []

    for ref in sorted(nl.components):
        m = WING_IFACE_RE.match(ref)
        if not m:
            continue
        n = int(m.group(1))
        pos = nl.net_of(ref, PAD_SOLAR_P)
        neg = nl.net_of(ref, PAD_SOLAR_N)
        groups.append(Group("wing %d (%s)" % (n, ref), pos, neg, "wing-interface", ref))

    for ref in nl.cells():
        c = nl.components[ref]
        pos = neg = None
        for pin, func in sorted(c.pinfunc.items()):
            f = func.strip().lower()
            net = c.pins.get(pin)
            if f in CELL_POS_FUNCS:
                pos = net
            elif f in CELL_NEG_FUNCS:
                neg = net
        groups.append(Group("solar cell %s" % ref, pos, neg, "solar-cell", ref))

    return groups


def diode_endpoints(comp: Component) -> tuple[str | None, str | None, bool]:
    """Return (cathode_net, anode_net, polarity_known) for a diode component."""
    cath = anode = None
    for pin, func in comp.pinfunc.items():
        f = func.strip().lower()
        if f in CATHODE_FUNCS:
            cath = comp.pins.get(pin)
        elif f in ANODE_FUNCS:
            anode = comp.pins.get(pin)
    return cath, anode, (cath is not None and anode is not None)


def check_netlist(nl: Netlist, require_populated: bool = False) -> Report:
    rep = Report()

    groups = solar_groups(nl, rep)
    if not groups:
        rep.unknown("B1", "no solar series group found — no wing interface (J_W1..J_W4) "
                          "and no solar cell component (PVA<n>) is present, so the "
                          "bypass provision CANNOT be verified in this netlist")
        return rep
    rep.ok("B1 %d solar series group(s): %s"
           % (len(groups), ", ".join(g.label for g in groups)))

    # Every diode component, with its endpoints resolved once.
    diodes: list[tuple[str, Component, str | None, str | None]] = []
    unresolved: list[str] = []
    for ref, comp in sorted(nl.components.items()):
        if not nl.is_diode(comp):
            continue
        cath, anode, known = diode_endpoints(comp)
        if not known:
            unresolved.append(ref)
        diodes.append((ref, comp, cath, anode))

    for g in groups:
        if g.pos_net is None or g.neg_net is None:
            rep.unknown("B2", "group %s: its positive/negative node cannot be resolved "
                              "(pad(s) absent from the netlist) — cannot tell whether a "
                              "diode is across it" % g.label)
            continue

        covering = None
        polarity_unknown = False
        for ref, comp, cath, anode in diodes:
            if cath == g.pos_net and anode == g.neg_net:
                covering = (ref, comp)
                break
        if covering is None:
            # Is a diode present across the group but with the WRONG polarity?
            wrong = [(ref, comp) for ref, comp, cath, anode in diodes
                     if {cath, anode} == {g.pos_net, g.neg_net}]
            if wrong:
                rep.fail("B2", "group %s: diode %s spans the group but is reversed — its "
                               "cathode must sit on %s and its anode on %s"
                        % (g.label, ", ".join(r for r, _ in wrong), g.pos_net, g.neg_net))
                continue
            # Is a diode present across the group whose polarity could not be read?
            if unresolved:
                for ref, comp, cath, anode in diodes:
                    if ref not in unresolved:
                        continue
                    nets = {n for n in comp.pins.values() if n is not None}
                    if nets == {g.pos_net, g.neg_net}:
                        polarity_unknown = True
                        break
                if polarity_unknown:
                    rep.unknown("B3", "group %s: diode(s) sit across it but their polarity "
                                      "cannot be read (no K/A pin function); a diode whose "
                                      "orientation is unknown cannot be credited as a "
                                      "bypass" % g.label)
                    continue
            rep.fail("B2", "group %s: NO bypass diode across it (%s <-> %s) — a failure "
                           "in this group is not contained; it can open or reverse-stress "
                           "the whole series string"
                    % (g.label, g.pos_net, g.neg_net))
            continue

        ref, comp = covering
        rep.ok("B2 group %s has bypass diode %s (%s)" % (g.label, ref, comp.value or comp.part))

        # ---- B4  known under-rated part in a bypass position --------------- #
        rating = rating_of(comp.value)
        if rating is not None:
            i_cont, v_rev = rating
            if i_cont < REQUIRED_CURRENT_A or v_rev < REQUIRED_VOLTAGE_V:
                rep.fail("B4", "group %s: bypass diode %s is a %s (%.3g A / %.3g V) — "
                               "under-rated against the permanent-continuous ≥%.3g A / "
                               "≥%.3g V requirement (ADR-053 §2.2); the bypass path "
                               "carries the FULL string current continuously"
                        % (g.label, ref, comp.value, i_cont, v_rev,
                           REQUIRED_CURRENT_A, REQUIRED_VOLTAGE_V))
        else:
            rep.note("B4 bypass diode %s (%s) has no rating in the known table — "
                     "rating not judged" % (ref, comp.value or comp.part))

        # ---- B5  DNP ------------------------------------------------------- #
        if comp.dnp:
            if require_populated:
                rep.fail("B5", "group %s: bypass diode %s is DNP — ADR-051 §2.4 "
                               "decision 4.2 mandates it POPULATED on a cutter flight "
                               "(--require-populated)" % (g.label, ref))
            else:
                rep.note("B5 bypass diode %s for group %s is DNP (a provision only); "
                         "ADR-051 §2.4 decision 4.2 requires it populated on a cutter "
                         "flight" % (ref, g.label))

    return rep


def check_schematic(path: Path) -> Report:
    """Label-level check.  NEVER returns PASS and never returns FAIL: a label scan
    sees names, not wires, so it cannot prove which nodes a diode's pins sit on.
    Always UNDETERMINED, saying exactly what is and is not known."""
    rep = Report()
    text = path.read_text(encoding="utf-8", errors="replace")
    labels = set(re.findall(r'\(\s*(?:label|global_label|hierarchical_label)\s+"((?:[^"\\]|\\.)*)"',
                            text))
    refs = set(re.findall(r'\(\s*property\s+"Reference"\s+"((?:[^"\\]|\\.)*)"', text))
    if not labels and not refs:
        rep.unknown("S0", "%s: no labels or component references could be read" % path)
        return rep
    rep.ok("S0 read %d net label(s) and %d component reference(s) from %s"
           % (len(labels), len(refs), path.name))
    rep.unknown("S3", "label scan only: a .kicad_sch shows net NAMES, not wires, so it "
                      "cannot prove a diode's pins sit across a group — run this checker "
                      "on the exported .net netlist for a connectivity verdict")
    return rep


# --------------------------------------------------------------------------- #
# driver
# --------------------------------------------------------------------------- #

def default_input() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / DEFAULT_NETLIST
        if cand.is_file():
            return cand
    return Path(DEFAULT_NETLIST)


def run(path: Path, require_populated: bool = False) -> Report:
    suffix = path.suffix.lower()
    if suffix == ".net":
        return check_netlist(load_netlist(path), require_populated)
    if suffix in (".kicad_sch", ".sch"):
        return check_schematic(path)
    head = path.read_text(encoding="utf-8", errors="replace")[:4000]
    if "(export" in head and "(nets" in head:
        return check_netlist(load_netlist(path), require_populated)
    if "kicad_sch" in head or "(symbol" in head:
        return check_schematic(path)
    raise ValueError("%s: unrecognised input (expected a KiCad .net or .kicad_sch)" % path)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Fail-closed ADR-053 bypass-diode gate: every cell or series group "
                    "in the solar path must have a correctly polarised, adequately rated "
                    "Schottky bypass diode across it.")
    ap.add_argument("input", nargs="?", default=None,
                    help="KiCad .net (connectivity) or .kicad_sch (label-level). "
                         "Default: the v9 flight netlist.")
    ap.add_argument("--require-populated", action="store_true",
                    help="treat a DNP bypass diode as a failure (cutter flight)")
    ap.add_argument("--json", action="store_true", help="emit a JSON report")
    ap.add_argument("--quiet", action="store_true", help="print only the verdict line")
    args = ap.parse_args(argv)

    path = Path(args.input) if args.input else default_input()
    try:
        rep = run(path, args.require_populated)
    except FileNotFoundError:
        print("bypass_diode_check: FAIL — input not found: %s" % path, file=sys.stderr)
        return EXIT_UNDETERMINED
    except (ValueError, OSError) as exc:
        print("bypass_diode_check: UNDETERMINED — %s" % exc, file=sys.stderr)
        return EXIT_UNDETERMINED

    verdict = ("PASS" if rep.exit_code == EXIT_PASS
               else "FAIL" if rep.exit_code == EXIT_FAIL else "UNDETERMINED")

    if args.json:
        print(json.dumps({
            "input": str(path),
            "mode": "netlist" if path.suffix.lower() == ".net" else "schematic-labels",
            "verdict": verdict,
            "exit_code": rep.exit_code,
            "failures": rep.failures,
            "undetermined": rep.undetermined,
            "notes": rep.notes,
            "checks": rep.checked,
        }, indent=2))
    else:
        if not args.quiet:
            print("bypass_diode_check — input: %s (%s)"
                  % (path, "netlist" if path.suffix.lower() == ".net"
                     else "schematic labels — label-level only"))
            for line in rep.checked:
                print("  ok   %s" % line)
            for line in rep.notes:
                print("  note %s" % line)
            for line in rep.undetermined:
                print("  ??   %s" % line)
            for line in rep.failures:
                print("  FAIL %s" % line)
        print("VERDICT: %s (exit %d)" % (verdict, rep.exit_code))

    return rep.exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
