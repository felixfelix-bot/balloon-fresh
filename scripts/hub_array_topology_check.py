#!/usr/bin/env python3
"""hub_array_topology_check.py — FAIL-CLOSED gate on the ADR-051 hub-array topology.

WHAT THIS GUARDS
================
ADR-051 requires the hub-mounted solar array to be an **electrically independent
series string** from the four jettisonable wing strings, feeding the charge path
through its **own converter input**.  If the hub array is instead wired *in series
with*, or as a *tap on*, the wing chain, then the FIRST wing cut removes the hub
array's return path together with the wing's cells and the vehicle goes dark: the
cut becomes suicide.  This script is the mechanical enforcement of that invariant.

It also enforces the interface bookkeeping the cut ladder depends on: every wing
interface must present its `SOLAR_P` (pad 1) and `SOLAR_N` (pad 4) copper land
**exactly once**, because a missing or duplicated land means the series order —
and therefore the 6.0 / 4.5 / 3.0 V ladder — is not what ADR-046/ADR-048 says it is.

WHAT IT PARSES
==============
* a KiCad **netlist** (`.net`, the authority on connectivity) — full check; or
* a KiCad **schematic** (`.kicad_sch`) — *label-level only*.  In schematic mode the
  script can NEVER return PASS and never returns FAIL either: a label scan sees
  names, not wires, so it cannot prove that two differently-named labels are not
  joined by copper.  Schematic mode therefore returns UNDETERMINED with a pointed
  message and directs the caller to the exported netlist.  This is deliberate: a
  checker that cannot see the answer must not claim one.

EXIT CODES
==========
    0   PASS          — the hub array is present, independent, and the wing lands check out
    1   FAIL          — a VIOLATION was detected (a named rule below fired)
    2   UNDETERMINED  — the answer cannot be established (e.g. ADR-051 is not yet
                        implemented in this schematic).  Non-zero on purpose:
                        never silent-pass.

Anything other than 0 is a failure.  Exit 1 and exit 2 are distinguished so that a
CI caller can tell "the design is wrong" from "the design does not exist yet".

RULES (all fail-closed; the reason string names the rule)
=========================================================
R1  four wing interfaces present                       (else UNDETERMINED)
R2  every wing interface's pad 1 (SOLAR_P) and pad 4 (SOLAR_N) land appears in
    exactly one net; the component declares all four pads       (else FAIL)
R3  a hub-array string is present (canonical `HUB_PV_P` / `HUB_PV_N`) (else UNDETERMINED)
R3b NO hub-array cell component may have a terminal on a wing-chain net — this is
    the tap detected at the source, independent of how the nets are named
                                                                   (else FAIL)
R4  INDEPENDENCE — the hub array's hot net shares NO node with any wing
    `SOLAR_P`/`SOLAR_N` land, and is not a wing-chain net          (else FAIL)
R5  the hub array's return may be `GND` (the one shared reference, in which case it
    is reported) but must not share a MID-STRING wing land         (else FAIL)
R6  the series ladder is intact: W1.N==W2.P, W2.N==W3.P, W3.N==W4.P, top=W1.P,
    bottom=W4.N on GND                                            (else FAIL)
R7  the hub array's hot net is not dangling — it must reach at least one
    non-wing-interface node (the converter/harvester input)        (else FAIL)
R8  optional (`--require-cut-sense`): each interface's pad 3 (`W<n>_RF`) is on a
    `CUT_SENSE_W<n>` net, so firmware can confirm the cut fired    (else FAIL;
    without the flag this is reported as a pending item, not a failure)

Usage
-----
    python3 scripts/hub_array_topology_check.py
    python3 scripts/hub_array_topology_check.py path/to/v9_flight.net
    python3 scripts/hub_array_topology_check.py path/to/v9_flight.kicad_sch --require-cut-sense
    python3 scripts/hub_array_topology_check.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# --------------------------------------------------------------------------- #
# Canonical names fixed by ADR-051
# --------------------------------------------------------------------------- #

#: ADR-051 mandates these two net names for the hub array's own string.
HUB_HOT_NET = "HUB_PV_P"      # + end of the hub string -> converter/harvester input
HUB_RETURN_NET = "HUB_PV_N"   # - end of the hub string

#: Any net whose normalised name matches one of these is treated as a hub-array net.
HUB_NET_PATTERNS = (
    r"^HUB_PV",
    r"^HUB_ARRAY",
    r"^HUBARRAY",
    r"^HUB_SOLAR",
    r"^SOLAR_HUB",
    r"^PVA_",
)

#: Wing interface reference / symbol identification.
WING_REF_RE = re.compile(r"^J_W([1-4])$")
WING_SYMBOL_PART = "WING_SOCKET_4P"

#: Hub-array cell identification (ADR-051 names them `PVA<n>`; the aliases are
#: accepted so an implementation that used `HUB_C<n>` is still checked).
HUB_CELL_REF_RE = re.compile(r"^(?:PVA|HUB_C|HUBPV|HUB_SOLAR)\d+$")
HUB_CELL_PART_HINTS = ("solarcel", "pva", "hub_pv", "hub_cell")

#: Interface pad numbers (ADR-046 §2.1 / ADR-048 §2.3, order MUST match).
PAD_SOLAR_P = "1"
PAD_GND = "2"
PAD_RF = "3"
PAD_SOLAR_N = "4"

#: Cut-sense net name per interface (ADR-051 decision 6).
def cut_sense_net(n: int) -> str:
    return "CUT_SENSE_W%d" % n


DEFAULT_NETLIST = "tracker/hardware/schematics/flight_board/v9_flight.net"

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_UNDETERMINED = 2


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
    """Every child list of `node` whose head is `key`."""
    if not isinstance(node, list):
        return []
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def _first(node, key):
    got = _children(node, key)
    return got[0] if got else None


def _value(node, key):
    """The value of the first child list whose head is `key` (or None)."""
    child = _first(node, key)
    if child is None or len(child) < 2:
        return None
    val = child[1]
    return val if isinstance(val, str) else None


# --------------------------------------------------------------------------- #
# netlist model
# --------------------------------------------------------------------------- #

class Interface:
    def __init__(self, n: int, ref: str):
        self.n = n
        self.ref = ref
        self.pads: dict[str, str | None] = {p: None for p in
                                           (PAD_SOLAR_P, PAD_GND, PAD_RF, PAD_SOLAR_N)}
        self.duplicate_pads: list[str] = []


class Netlist:
    def __init__(self):
        self.components: dict[str, str] = {}      # ref -> part/symbol name
        self.nets: dict[str, list[tuple[str, str]]] = {}   # net name -> [(ref, pad)]
        self.name_by_node: dict[tuple[str, str], str] = {}  # (ref,pad) -> net name
        self.interfaces: dict[int, Interface] = {}

    # -- lookups ---------------------------------------------------------- #
    def nodes_of(self, net: str) -> list[tuple[str, str]]:
        return list(self.nets.get(net, []))

    def net_of(self, ref: str, pad: str) -> str | None:
        return self.name_by_node.get((ref, pad))

    def wing_solar_land_nodes(self) -> set[tuple[str, str]]:
        out: set[tuple[str, str]] = set()
        for itf in self.interfaces.values():
            for pad in (PAD_SOLAR_P, PAD_SOLAR_N):
                out.add((itf.ref, pad))
        return out

    def wing_net_names(self) -> set[str]:
        """Every net name that carries at least one wing solar land."""
        names = set()
        for itf in self.interfaces.values():
            for pad in (PAD_SOLAR_P, PAD_SOLAR_N):
                nm = self.net_of(itf.ref, pad)
                if nm:
                    names.add(nm)
        names.discard("GND")
        return names

    def hub_cell_refs(self) -> list[str]:
        """Components that are hub-array cells (by reference or by symbol hint)."""
        out = []
        for ref, part in self.components.items():
            if part == WING_SYMBOL_PART:
                continue
            low = (part or "").lower()
            if HUB_CELL_REF_RE.match(ref) or any(h in low for h in HUB_CELL_PART_HINTS):
                out.append(ref)
        return sorted(out)

    def hub_net_names(self) -> list[str]:
        out = []
        for name in self.nets:
            norm = name.lstrip("/")
            if any(re.match(p, norm) for p in HUB_NET_PATTERNS):
                out.append(name)
        return sorted(out)


def load_netlist(path: Path) -> Netlist:
    """Parse a KiCad .net file into a Netlist. Raises ValueError on bad input."""
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
        part = None
        libsrc = _first(comp, "libsource")
        if libsrc is not None:
            part = _value(libsrc, "part")
        nl.components[ref] = part or ""

    nets = _first(tree, "nets")
    if nets is None:
        raise ValueError("%s: netlist has no (nets ...) section" % path)
    for net in _children(nets, "net"):
        name = _value(net, "name")
        if name is None:
            continue
        nodes = []
        for node in _children(net, "node"):
            ref = _value(node, "ref")
            pin = _value(node, "pin")
            if ref is not None and pin is not None:
                nodes.append((ref, pin))
        # a net name can appear more than once only in broken exports; merge
        nl.nets.setdefault(name, []).extend(nodes)
        for ref, pin in nodes:
            key = (ref, pin)
            if key in nl.name_by_node and nl.name_by_node[key] != name:
                raise ValueError(
                    "%s: pad %s.%s appears in two nets (%s and %s)"
                    % (path, ref, pin, nl.name_by_node[key], name)
                )
            nl.name_by_node[key] = name

    resolve_interfaces(nl)
    return nl


def resolve_interfaces(nl: Netlist) -> None:
    """Find the wing interfaces by symbol part first, then by reference shape."""
    by_part = [ref for ref, part in nl.components.items() if part == WING_SYMBOL_PART]
    if by_part:
        refs = by_part
    else:
        refs = [ref for ref in nl.components if WING_REF_RE.match(ref)]
    for ref in refs:
        m = WING_REF_RE.match(ref)
        if not m:
            continue
        n = int(m.group(1))
        itf = Interface(n, ref)
        for pad in itf.pads:
            nm = nl.net_of(ref, pad)
            itf.pads[pad] = nm
        nl.interfaces[n] = itf


# --------------------------------------------------------------------------- #
# schematic (label-level) model
# --------------------------------------------------------------------------- #

LABEL_KEYS = ("label", "global_label", "hierarchical_label")


def load_schematic_labels(path: Path) -> tuple[set[str], set[str]]:
    """Return (net_labels, component_refs) from a .kicad_sch. Label-level only."""
    text = path.read_text(encoding="utf-8", errors="replace")
    labels: set[str] = set()
    for m in re.finditer(r'\(\s*(?:%s)\s+"((?:[^"\\]|\\.)*)"' % "|".join(LABEL_KEYS), text):
        labels.add(m.group(1))
    refs: set[str] = set()
    for m in re.finditer(r'\(\s*property\s+"Reference"\s+"((?:[^"\\]|\\.)*)"', text):
        refs.add(m.group(1))
    return labels, refs


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


def check_netlist(nl: Netlist, require_cut_sense: bool = False) -> Report:
    rep = Report()

    # ---- R1  interfaces present ---------------------------------------- #
    expected = {1, 2, 3, 4}
    missing_if = sorted(expected - set(nl.interfaces))
    if missing_if:
        rep.unknown("R1", "wing interface(s) %s not found in the netlist — cannot "
                          "establish the cut topology"
                          % ", ".join("J_W%d" % n for n in missing_if))
        return rep
    rep.ok("R1 four wing interfaces present: %s"
           % ", ".join(nl.interfaces[n].ref for n in sorted(nl.interfaces)))

    # ---- R2  every SOLAR_P / SOLAR_N land present exactly once --------- #
    for n in sorted(nl.interfaces):
        itf = nl.interfaces[n]
        for pad, label in ((PAD_SOLAR_P, "SOLAR_P"), (PAD_SOLAR_N, "SOLAR_N")):
            nm = itf.pads[pad]
            if nm is None:
                count = 0
            else:
                count = sum(1 for (r, p) in nl.nets.get(nm, []) if r == itf.ref and p == pad)
            if count != 1:
                rep.fail("R2", "%s pad %s (%s) appears %d times in the netlist — "
                               "must be exactly once" % (itf.ref, pad, label, count))
            else:
                rep.ok("R2 %s pad %s (%s) -> net %s" % (itf.ref, pad, label, nm))
        if itf.pads[PAD_GND] is None:
            rep.note("%s pad 2 (GND) has no net" % itf.ref)

    # ---- R6  series ladder intact -------------------------------------- #
    pairs = [(nl.interfaces[n].ref, PAD_SOLAR_N, nl.interfaces[n + 1].ref, PAD_SOLAR_P)
             for n in (1, 2, 3)]
    for a_ref, a_pad, b_ref, b_pad in pairs:
        a = nl.net_of(a_ref, a_pad)
        b = nl.net_of(b_ref, b_pad)
        if a is None or b is None:
            rep.unknown("R6", "cannot read the %s.%s <-> %s.%s hub link"
                        % (a_ref, a_pad, b_ref, b_pad))
        elif a != b:
            rep.fail("R6", "hub link broken: %s.%s is on %s but %s.%s is on %s — "
                           "the series ladder is not ADR-046 §2.3"
                    % (a_ref, a_pad, a, b_ref, b_pad, b))
    top = nl.net_of(nl.interfaces[1].ref, PAD_SOLAR_P)
    bottom = nl.net_of(nl.interfaces[4].ref, PAD_SOLAR_N)
    if top is None or bottom is None:
        rep.unknown("R6", "stack top/bottom lands not resolvable")
    else:
        if bottom.lstrip("/") != "GND":
            rep.fail("R6", "stack bottom %s.%s is on net %s, expected GND"
                    % (nl.interfaces[4].ref, PAD_SOLAR_N, bottom))
        rep.ok("R6 stack top %s.%s = %s ; stack bottom %s.%s = %s"
               % (nl.interfaces[1].ref, PAD_SOLAR_P, top,
                  nl.interfaces[4].ref, PAD_SOLAR_N, bottom))

    # ---- R3  hub array present ----------------------------------------- #
    hub_nets = nl.hub_net_names()
    wing_land_nodes = nl.wing_solar_land_nodes()
    wing_nets = nl.wing_net_names()

    # ---- R3b  hub-array cells must not land on a wing-chain net --------- #
    # This detects the tap at its source, independently of net naming: if any
    # terminal of a hub-array cell component sits on a net that carries a wing
    # solar land, the hub array is wired into the wing string.
    hub_cells = nl.hub_cell_refs()
    for cref in hub_cells:
        for (ref, pin), net in sorted(nl.name_by_node.items()):
            if ref != cref:
                continue
            if net in wing_nets:
                rep.fail("R3b", "hub-array cell %s pin %s is on wing-chain net %s — the "
                                "hub array is wired into the wing series string, so the "
                                "first wing cut kills it" % (cref, pin, net))
            elif net in hub_nets or net.lstrip("/") == "GND":
                rep.ok("R3b hub-array cell %s pin %s -> %s" % (cref, pin, net))
            else:
                rep.note("R3b hub-array cell %s pin %s is on unrecognised net %s"
                         % (cref, pin, net))
    if not hub_cells:
        rep.note("R3b no hub-array cell component found (expected refs like PVA1/PVA2 "
                 "or a SolarCell symbol) — the hub array may not be in this netlist")

    hot = None
    for cand in (HUB_HOT_NET, "/" + HUB_HOT_NET):
        if cand in nl.nets:
            hot = cand
            break
    if hot is None:
        # fall back to any hub net that is not obviously the return
        for cand in hub_nets:
            if not cand.lstrip("/").endswith(("_N", "_GND")) and cand.lstrip("/") not in ("GND",):
                hot = cand
                break
    if not hub_nets:
        rep.unknown("R3", "no hub-array net found (looked for %s / patterns %s) — "
                          "ADR-051 is not implemented in this schematic, so its "
                          "electrical independence CANNOT be verified"
                    % (HUB_HOT_NET, ", ".join(HUB_NET_PATTERNS)))
        return rep
    rep.ok("R3 hub-array nets present: %s" % ", ".join(hub_nets))
    if hot is None:
        rep.unknown("R3", "hub-array nets exist but none is identifiable as the hot "
                          "(positive) string terminal")
        return rep

    # ---- R4  INDEPENDENCE ---------------------------------------------- #
    hot_nodes = nl.nodes_of(hot)
    shared_nodes = sorted(set(hot_nodes) & wing_land_nodes)
    if shared_nodes:
        rep.fail("R4", "hub-array hot net %s shares node(s) %s with the wing series "
                       "chain — the hub array is a TAP on (or in series with) the "
                       "wing chain; the first wing cut would kill it"
                % (hot, ", ".join("%s.%s" % rp for rp in shared_nodes)))
    if hot in wing_nets:
        rep.fail("R4", "hub-array hot net %s IS a wing-chain net — hub array and wing "
                       "string are one node" % hot)
    if not shared_nodes and hot not in wing_nets:
        rep.ok("R4 hub-array hot net %s shares no node with the wing series chain" % hot)

    # ---- R5  return path ----------------------------------------------- #
    # Every hub-array net except the hot one is a return/reference node.  Sharing
    # the *stack bottom* wing land (J_W4 pad 4) through a common GND is a shared
    # REFERENCE, not a series link, and is allowed — but reported.  Sharing any
    # MID-STRING wing land puts the hub array's return inside the wing string,
    # which is the tap the ADR forbids.
    stack_bottom = (nl.interfaces[4].ref, PAD_SOLAR_N)
    ret_named = any(c in nl.nets for c in (HUB_RETURN_NET, "/" + HUB_RETURN_NET))
    shared_any = False
    for name in hub_nets:
        if name == hot:
            continue
        shared = sorted(set(nl.nodes_of(name)) & wing_land_nodes)
        if not shared:
            rep.ok("R5 hub-array return net %s carries no wing land" % name)
            continue
        shared_any = True
        mid = [rp for rp in shared if rp != stack_bottom]
        if mid:
            rep.fail("R5", "hub-array net %s shares MID-STRING wing land(s) %s — the "
                           "hub array's return is inside the wing series string"
                    % (name, ", ".join("%s.%s" % rp for rp in mid)))
        else:
            rep.note("R5 hub-array return net %s is the shared GND, which also carries "
                     "the stack bottom %s.%s — allowed (common reference, not a series "
                     "link), and reported rather than hidden"
                     % (name, stack_bottom[0], stack_bottom[1]))
    if not shared_any and not ret_named:
        rep.note("R5 no explicit %s net and no hub-array net carries a wing land — the "
                 "hub string's return is either floating or merged into GND under a "
                 "name this checker did not match; confirm it by hand" % HUB_RETURN_NET)

    # ---- R7  hot net not dangling -------------------------------------- #
    load_nodes = [rp for rp in hot_nodes if not WING_REF_RE.match(rp[0])]
    if not load_nodes:
        rep.fail("R7", "hub-array hot net %s reaches no non-wing-interface node — it "
                       "does not reach its own converter/harvester input" % hot)
    else:
        rep.ok("R7 hub-array hot net %s reaches %s"
               % (hot, ", ".join("%s.%s" % rp for rp in sorted(load_nodes))))

    # ---- R8  cut-sense -------------------------------------------------- #
    cut_sense_present = []
    for n in sorted(nl.interfaces):
        itf = nl.interfaces[n]
        want = cut_sense_net(n)
        got = itf.pads[PAD_RF]
        if got is not None and got.lstrip("/") == want:
            cut_sense_present.append(n)
        elif require_cut_sense:
            rep.fail("R8", "%s pad 3 (RF_FEED) is on net %s, expected %s "
                           "(--require-cut-sense)" % (itf.ref, got, want))
    if cut_sense_present:
        rep.ok("R8 cut-sense wired on interface(s): %s"
               % ", ".join("W%d" % n for n in cut_sense_present))
    elif not require_cut_sense:
        rep.note("R8 no CUT_SENSE_W<n> net yet — ADR-051 decision 6 (reuse the reserved "
                 "W<n>_RF land as the cut-sense line) is still pending in this schematic")

    return rep


def check_schematic(path: Path, require_cut_sense: bool = False) -> Report:
    """Label-level check.  NEVER returns PASS and never returns FAIL: a label scan
    sees names, not wires, so it cannot prove node disjointness.  Always
    UNDETERMINED, with a message that says exactly what is and is not known."""
    rep = Report()
    labels, refs = load_schematic_labels(path)
    if not labels and not refs:
        rep.unknown("S0", "%s: no labels or component references could be read" % path)
        return rep

    hub_labels = sorted(l for l in labels
                        if any(re.match(p, l.lstrip("/")) for p in HUB_NET_PATTERNS))
    wing_labels = sorted(l for l in labels if re.match(r"^W[1-4]_SOLAR_[PN]$", l.lstrip("/")))
    hub_cells = sorted(r for r in refs if HUB_CELL_REF_RE.match(r))

    rep.ok("S0 read %d net label(s) and %d component reference(s) from %s"
           % (len(labels), len(refs), path.name))

    if not hub_labels:
        if hub_cells:
            rep.unknown("S1a", "hub-array cell component(s) %s are present but there is "
                               "NO hub-array net label (looked for %s) — the cells can "
                               "only be on the wing chain or the shared GND as drawn. "
                               "Export the netlist and re-run: a label scan cannot "
                               "decide this" % (", ".join(hub_cells), HUB_HOT_NET))
            return rep
        rep.unknown("S1", "no hub-array net label in the schematic (looked for %s) — "
                          "ADR-051 is not implemented here, so independence CANNOT be "
                          "verified.  Schematic mode is label-level only; run the "
                          "checker on the exported netlist for a connectivity verdict."
                    % HUB_HOT_NET)
        return rep

    # A hub-array label textually identical to a wing label would be a proven
    # violation, because in KiCad one label name is one net.  With the patterns
    # above the two sets cannot overlap, but the guard is kept so a future
    # pattern change cannot silently lose the check.
    collision = sorted(set(hub_labels) & set(wing_labels))
    if collision:
        rep.fail("S2", "hub-array label(s) %s are textually identical to wing net "
                       "label(s) — same net name means same node; the hub array is "
                       "not independent" % ", ".join(collision))

    # even a clean label scan cannot prove node disjointness (a wire can join
    # differently-named labels), so the honest verdict is UNDETERMINED.
    rep.unknown("S3", "label scan found hub-array label(s) %s disjoint from the wing "
                      "labels, but a label scan cannot see wires that join nets — "
                      "run this checker on the exported .net netlist for a real verdict"
                % ", ".join(hub_labels))
    if require_cut_sense:
        cs = [l for l in labels if l.lstrip("/").startswith("CUT_SENSE_W")]
        if len(cs) < 4:
            rep.fail("R8", "--require-cut-sense: found %d CUT_SENSE_W<n> label(s), "
                           "expected 4" % len(cs))
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


def run(path: Path, require_cut_sense: bool = False) -> Report:
    suffix = path.suffix.lower()
    if suffix == ".net":
        return check_netlist(load_netlist(path), require_cut_sense)
    if suffix in (".kicad_sch", ".sch"):
        return check_schematic(path, require_cut_sense)
    # sniff
    head = path.read_text(encoding="utf-8", errors="replace")[:4000]
    if "(export" in head and "(nets" in head:
        return check_netlist(load_netlist(path), require_cut_sense)
    if "kicad_sch" in head or "(symbol" in head:
        return check_schematic(path, require_cut_sense)
    raise ValueError("%s: unrecognised input (expected a KiCad .net or .kicad_sch)" % path)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Fail-closed ADR-051 hub-array topology gate: the hub array must "
                    "be an electrically independent string from the wing chain.")
    ap.add_argument("input", nargs="?", default=None,
                    help="KiCad .net (connectivity) or .kicad_sch (label-level). "
                         "Default: the v9 flight netlist.")
    ap.add_argument("--require-cut-sense", action="store_true",
                    help="treat a missing CUT_SENSE_W<n> provision as a failure")
    ap.add_argument("--json", action="store_true", help="emit a JSON report")
    ap.add_argument("--quiet", action="store_true", help="print only the verdict line")
    args = ap.parse_args(argv)

    path = Path(args.input) if args.input else default_input()
    try:
        rep = run(path, args.require_cut_sense)
    except FileNotFoundError:
        print("hub_array_topology_check: FAIL — input not found: %s" % path, file=sys.stderr)
        return EXIT_UNDETERMINED
    except (ValueError, OSError) as exc:
        print("hub_array_topology_check: UNDETERMINED — %s" % exc, file=sys.stderr)
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
            print("hub_array_topology_check — input: %s (%s)"
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
