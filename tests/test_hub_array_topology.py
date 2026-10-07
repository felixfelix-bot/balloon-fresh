#!/usr/bin/env python3
"""tests for `scripts/hub_array_topology_check.py` — the ADR-051 hub-array gate.

The gate is FAIL-CLOSED: it exits 0 only when it has *proved* that the hub-mounted
array is an electrically independent string from the four jettisonable wing
strings.  Everything else is non-zero.  These tests therefore do three things:

  1. prove the gate PASSES a deliberately-good fixture (so it is not a no-op that
     always fails, which would be equally useless);
  2. prove the gate FAILS a deliberately-BAD fixture (a hub array tapped onto the
     wing chain) — this is the mutation test that shows the check can fail;
  3. prove the gate never silent-passes: an absent hub array, an unreadable input,
     and a schematic-only label scan all return non-zero.

Fixtures are generated in `tmp_path` as real KiCad-shaped netlists, then the
checker is invoked through `subprocess` so its real exit code is what is asserted
(not an in-process return value).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CHECKER = REPO / "scripts" / "hub_array_topology_check.py"
REAL_V9_NET = REPO / "tracker" / "hardware" / "schematics" / "flight_board" / "v9_flight.net"

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_UNDETERMINED = 2


# --------------------------------------------------------------------------- #
# fixture builders
# --------------------------------------------------------------------------- #

def netlist_text(components, nets) -> str:
    """Render a minimal but valid KiCad netlist s-expression."""
    out = ['(export (version "E")']
    out.append('  (design (source "fixture.kicad_sch") (date "2026-10-07") '
               '(tool "Eeschema 9.0.8")')
    out.append('    (sheet (number "1") (name "/") (tstamps "/") '
               '(title_block (title "ADR-051 fixture"))))')
    out.append("  (components")
    for ref, part in components:
        out.append('    (comp (ref "%s") (value "%s")' % (ref, part))
        out.append('      (libsource (lib "fixture") (part "%s"))' % part)
        out.append('      (tstamps "00000000-0000-0000-0000-000000000000"))')
    out.append("  )")
    out.append("  (nets")
    for i, (name, nodes) in enumerate(nets, start=1):
        out.append('    (net (code "%d") (name "%s") (class "Default")' % (i, name))
        for ref, pin in nodes:
            out.append('      (node (ref "%s") (pin "%s") (pintype "passive"))' % (ref, pin))
        out.append("    )")
    out.append("  ))")
    return "\n".join(out) + "\n"


WING_COMPS = [("J_W%d" % n, "WING_SOCKET_4P") for n in (1, 2, 3, 4)]
CUTTER_AND_HARVESTER_COMPS = [
    ("D1", "BAT54"), ("D_BP1", "BAT54"), ("D_BP2", "BAT54"),
    ("D_BP3", "BAT54"), ("D_BP4", "BAT54"),
    ("HUB_C1", "SolarCell_78x39mm"), ("HUB_C2", "SolarCell_78x39mm"),
    ("U_HARV", "bq25570"), ("U_CVT", "TPS63060"),
    ("M_CUT1", "IRLML2502"), ("M_CUT2", "IRLML2502"),
    ("M_CUT3", "IRLML2502"), ("M_CUT4", "IRLML2502"),
    ("U_MCU", "ESP32-S3-WROOM-1U"),
]

# the wing chain exactly as ADR-046 §2.3 / ADR-048 §2.3 fix it
WING_CHAIN_NETS = [
    ("/W1_SOLAR_P", [("J_W1", "1"), ("D_BP1", "1"), ("D1", "2")]),
    ("/W1_SOLAR_N", [("J_W1", "4"), ("J_W2", "1"), ("D_BP1", "2"), ("D_BP2", "1")]),
    ("/W2_SOLAR_N", [("J_W2", "4"), ("J_W3", "1"), ("D_BP2", "2"), ("D_BP3", "1")]),
    ("/W3_SOLAR_N", [("J_W3", "4"), ("J_W4", "1"), ("D_BP3", "2"), ("D_BP4", "1")]),
]
GND_NET = ("GND", [("J_W1", "2"), ("J_W2", "2"), ("J_W3", "2"), ("J_W4", "2"),
                   ("J_W4", "4"), ("D_BP4", "2"), ("U_HARV", "2"), ("U_CVT", "2"),
                   ("M_CUT1", "2"), ("M_CUT2", "2"), ("M_CUT3", "2"), ("M_CUT4", "2")])

# the ADR-051 hub array: its OWN string, its OWN converter input, and a return
# that touches no wing land at all (fully independent, floating return)
HUB_ARRAY_NETS_INDEPENDENT = [
    ("HUB_PV_P", [("HUB_C1", "1"), ("U_HARV", "1")]),
    ("HUB_PV_MID", [("HUB_C1", "2"), ("HUB_C2", "1")]),
    ("HUB_PV_N", [("HUB_C2", "2"), ("U_HARV", "3")]),
]
CUT_SENSE_NETS = [("CUT_SENSE_W%d" % n, [("J_W%d" % n, "3"), ("U_MCU", str(20 + n))])
                  for n in (1, 2, 3, 4)]


def good_netlist_text(include_cut_sense: bool = False) -> str:
    nets = list(WING_CHAIN_NETS) + [GND_NET] + list(HUB_ARRAY_NETS_INDEPENDENT)
    if include_cut_sense:
        nets += list(CUT_SENSE_NETS)
    return netlist_text(WING_COMPS + CUTTER_AND_HARVESTER_COMPS, nets)


def tapped_netlist_text() -> str:
    """DELIBERATELY BAD: the hub array's hot node is tapped onto the wing chain.

    Only one node differs from the good fixture: the hub array's + terminal and
    the harvester input are placed on `/W3_SOLAR_N` (the W3.<->W4 hub link) instead
    of on their own net.  That is the single wiring mistake ADR-051 exists to
    forbid: cutting wing 3 or 4 takes the hub array's return with it.
    """
    nets = []
    for name, nodes in WING_CHAIN_NETS:
        if name == "/W3_SOLAR_N":
            nodes = nodes + [("HUB_C1", "1"), ("U_HARV", "1"), ("HUB_C2", "1")]
        nets.append((name, nodes))
    nets.append(GND_NET)
    nets.append(("HUB_PV_N", [("HUB_C2", "2"), ("U_HARV", "3")]))
    return netlist_text(WING_COMPS + CUTTER_AND_HARVESTER_COMPS, nets)


def missing_land_netlist_text() -> str:
    """DELIBERATELY BAD: J_W2's SOLAR_P land (pad 1) is absent from the netlist."""
    nets = []
    for name, nodes in WING_CHAIN_NETS:
        if name == "/W1_SOLAR_N":
            nodes = [(r, p) for (r, p) in nodes if (r, p) != ("J_W2", "1")]
        nets.append((name, nodes))
    nets.append(GND_NET)
    nets += HUB_ARRAY_NETS_INDEPENDENT
    return netlist_text(WING_COMPS + CUTTER_AND_HARVESTER_COMPS, nets)


def wing_only_netlist_text() -> str:
    """The shape the repo is in today: the wing chain and NO hub array at all."""
    nets = list(WING_CHAIN_NETS) + [GND_NET]
    return netlist_text(WING_COMPS + [("D1", "BAT54"), ("D_BP1", "BAT54"),
                                      ("D_BP2", "BAT54"), ("D_BP3", "BAT54"),
                                      ("D_BP4", "BAT54")], nets)


SCHEMATIC_HUB_CELLS_NO_NET = """(kicad_sch (version 20230121) (generator eeschema)
  (symbol (lib_id "fixture:WING_SOCKET_4P") (property "Reference" "J_W1" (at 0 0 0)))
  (symbol (lib_id "fixture:SolarCell") (property "Reference" "HUB_C1" (at 0 0 0)))
  (symbol (lib_id "fixture:SolarCell") (property "Reference" "HUB_C2" (at 0 0 0)))
  (label "W1_SOLAR_P" (at 10 10 0) (effects (font (size 1.27 1.27))))
  (label "W3_SOLAR_N" (at 20 10 0) (effects (font (size 1.27 1.27))))
)
"""

SCHEMATIC_CLEAN_LABELS = """(kicad_sch (version 20230121) (generator eeschema)
  (symbol (lib_id "fixture:WING_SOCKET_4P") (property "Reference" "J_W1" (at 0 0 0)))
  (label "W1_SOLAR_P" (at 10 10 0) (effects (font (size 1.27 1.27))))
  (label "W2_SOLAR_N" (at 20 10 0) (effects (font (size 1.27 1.27))))
  (label "HUB_PV_P" (at 30 10 0) (effects (font (size 1.27 1.27))))
  (label "HUB_PV_N" (at 40 10 0) (effects (font (size 1.27 1.27))))
)
"""

SCHEMATIC_NO_HUB = """(kicad_sch (version 20230121) (generator eeschema)
  (symbol (lib_id "fixture:WING_SOCKET_4P") (property "Reference" "J_W1" (at 0 0 0)))
  (label "W1_SOLAR_P" (at 10 10 0) (effects (font (size 1.27 1.27))))
  (label "W1_SOLAR_N" (at 20 10 0) (effects (font (size 1.27 1.27))))
)
"""


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def run_checker(path: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECKER), str(path), *extra],
        capture_output=True, text=True, timeout=120,
    )


# --------------------------------------------------------------------------- #
# 1. the gate PASSES a good fixture  (it is not a no-op)
# --------------------------------------------------------------------------- #

def test_good_fixture_passes(tmp_path):
    p = write(tmp_path, "good.net", good_netlist_text())
    r = run_checker(p)
    assert r.returncode == EXIT_PASS, r.stdout + r.stderr
    assert "VERDICT: PASS" in r.stdout
    # and it really did examine the topology, not just the file
    assert "R4 hub-array hot net HUB_PV_P shares no node with the wing series chain" \
        in r.stdout


def test_good_fixture_with_gnd_referenced_return_passes(tmp_path):
    """A hub return merged into the shared GND is allowed — and reported."""
    nets = list(WING_CHAIN_NETS) + [GND_NET]
    nets.append(("HUB_PV_P", [("HUB_C1", "1"), ("U_HARV", "1")]))
    text = netlist_text(WING_COMPS + CUTTER_AND_HARVESTER_COMPS, nets)
    # the hub string's return lands on the existing GND net
    text = text.replace('      (node (ref "U_CVT") (pin "2") (pintype "passive"))',
                        '      (node (ref "U_CVT") (pin "2") (pintype "passive"))\n'
                        '      (node (ref "HUB_C1") (pin "2") (pintype "passive"))')
    p = write(tmp_path, "gnd-return.net", text)
    r = run_checker(p)
    assert r.returncode == EXIT_PASS, r.stdout + r.stderr
    assert "R4 hub-array hot net HUB_PV_P shares no node with the wing series chain" \
        in r.stdout


def test_good_fixture_with_cut_sense_passes_and_satisfies_the_flag(tmp_path):
    p = write(tmp_path, "good-cs.net", good_netlist_text(include_cut_sense=True))
    r = run_checker(p, "--require-cut-sense")
    assert r.returncode == EXIT_PASS, r.stdout + r.stderr
    assert "R8 cut-sense wired on interface(s): W1, W2, W3, W4" in r.stdout


# --------------------------------------------------------------------------- #
# 2. the gate FAILS a deliberately-bad fixture  (prove the check can fail)
# --------------------------------------------------------------------------- #

def test_tapped_hub_array_fails(tmp_path):
    """MUTATION TEST: move one node of the hub array onto the wing chain."""
    good = write(tmp_path, "good.net", good_netlist_text())
    bad = write(tmp_path, "tapped.net", tapped_netlist_text())
    assert run_checker(good).returncode == EXIT_PASS  # the same fixture, unmutated
    r = run_checker(bad)
    assert r.returncode == EXIT_FAIL, "checker did not fail on a tapped hub array"
    assert "R3b" in r.stdout
    assert "the hub array is wired into the wing series string" in r.stdout
    assert "VERDICT: FAIL" in r.stdout


def test_hub_array_in_series_with_the_wing_chain_fails(tmp_path):
    """MUTATION TEST 2: the hub array is spliced INTO the wing chain between W2 and W3.

    This is the 'in series with' half of the invariant.  On a real board the FIRST
    cut would then open the path through the hub array as well.
    """
    nets = [
        ("/W1_SOLAR_P", [("J_W1", "1"), ("D_BP1", "1"), ("D1", "2")]),
        ("/W1_SOLAR_N", [("J_W1", "4"), ("J_W2", "1"), ("D_BP1", "2"), ("D_BP2", "1")]),
        # W2.N no longer goes to W3.P: it goes into the hub array's + terminal
        ("/W2_SOLAR_N", [("J_W2", "4"), ("D_BP2", "2"), ("HUB_C1", "1")]),
        ("HUB_PV_MID", [("HUB_C1", "2"), ("HUB_C2", "1")]),
        # ... and the hub array's - terminal feeds W3's + terminal
        ("HUB_PV_N", [("HUB_C2", "2"), ("J_W3", "1"), ("D_BP3", "1")]),
        ("/W3_SOLAR_N", [("J_W3", "4"), ("J_W4", "1"), ("D_BP3", "2"), ("D_BP4", "1")]),
        GND_NET,
    ]
    p = write(tmp_path, "series.net",
              netlist_text(WING_COMPS + CUTTER_AND_HARVESTER_COMPS, nets))
    r = run_checker(p)
    assert r.returncode == EXIT_FAIL, r.stdout + r.stderr
    assert "R3b" in r.stdout
    assert "wired into the wing series string" in r.stdout
    assert "R6" in r.stdout           # the hub link is broken, and that is also caught


def test_hub_return_inside_the_wing_string_fails(tmp_path):
    """MUTATION TEST 3: the hub array's RETURN is a mid-string wing node."""
    nets = []
    for name, nodes in WING_CHAIN_NETS:
        if name == "/W2_SOLAR_N":
            nodes = nodes + [("HUB_C2", "2"), ("U_HARV", "3")]
        nets.append((name, nodes))
    nets.append(GND_NET)
    nets.append(("HUB_PV_P", [("HUB_C1", "1"), ("U_HARV", "1")]))
    p = write(tmp_path, "return-tap.net",
              netlist_text(WING_COMPS + CUTTER_AND_HARVESTER_COMPS, nets))
    r = run_checker(p)
    assert r.returncode == EXIT_FAIL, r.stdout + r.stderr
    assert "R3b" in r.stdout or "R5" in r.stdout


def test_missing_wing_land_fails(tmp_path):
    r = run_checker(write(tmp_path, "missing.net", missing_land_netlist_text()))
    assert r.returncode == EXIT_FAIL, r.stdout + r.stderr
    assert "R2" in r.stdout
    assert "J_W2 pad 1 (SOLAR_P) appears 0 times" in r.stdout


def test_cut_sense_required_flags_its_absence(tmp_path):
    p = write(tmp_path, "good.net", good_netlist_text(include_cut_sense=False))
    assert run_checker(p).returncode == EXIT_PASS          # optional by default
    r = run_checker(p, "--require-cut-sense")
    assert r.returncode == EXIT_FAIL, r.stdout + r.stderr
    assert "R8" in r.stdout


def test_schematic_hub_cells_without_a_hub_net_is_non_zero(tmp_path):
    """Hub cells drawn but no hub-array net label: at best a tap, at worst nothing."""
    p = write(tmp_path, "cells-no-net.kicad_sch", SCHEMATIC_HUB_CELLS_NO_NET)
    r = run_checker(p)
    assert r.returncode == EXIT_UNDETERMINED, r.stdout + r.stderr
    assert "NO hub-array net label" in r.stdout
    assert r.returncode != EXIT_PASS


# --------------------------------------------------------------------------- #
# 3. the gate never silent-passes
# --------------------------------------------------------------------------- #

def test_absent_hub_array_is_undetermined_not_pass(tmp_path):
    r = run_checker(write(tmp_path, "wing-only.net", wing_only_netlist_text()))
    assert r.returncode == EXIT_UNDETERMINED, r.stdout + r.stderr
    assert r.returncode != EXIT_PASS
    assert "ADR-051 is not implemented" in r.stdout


def test_schematic_mode_never_returns_pass(tmp_path):
    """A clean label scan still cannot prove node disjointness -> UNDETERMINED."""
    p = write(tmp_path, "clean.kicad_sch", SCHEMATIC_CLEAN_LABELS)
    r = run_checker(p)
    assert r.returncode == EXIT_UNDETERMINED, r.stdout + r.stderr
    assert "label scan cannot see wires" in r.stdout


def test_schematic_without_hub_labels_is_undetermined(tmp_path):
    r = run_checker(write(tmp_path, "nohub.kicad_sch", SCHEMATIC_NO_HUB))
    assert r.returncode == EXIT_UNDETERMINED
    assert "no hub-array net label" in r.stdout


def test_missing_input_file_is_non_zero(tmp_path):
    r = run_checker(tmp_path / "does-not-exist.net")
    assert r.returncode == EXIT_UNDETERMINED
    assert "not found" in (r.stdout + r.stderr)


def test_unparseable_input_is_non_zero(tmp_path):
    p = write(tmp_path, "junk.net", "this is not a netlist at all\n")
    r = run_checker(p)
    assert r.returncode != EXIT_PASS
    assert r.returncode in (EXIT_FAIL, EXIT_UNDETERMINED)


def test_real_v9_netlist_is_not_a_silent_pass():
    """ADR-051 is now IMPLEMENTED on the shipped v9 sheet, so the gate must be PASS.

    This test used to assert UNDETERMINED (exit 2) with "ADR-051 is not
    implemented", because the shipped netlist carried no hub array.  ADR-051 §6.3
    and ADR-054 §6.3 direct the array into the v9 generator, so the shipped
    netlist now carries HUB_PV_P / HUB_PV_MID<n> / HUB_PV_N on their own
    converter input.  The gate must therefore reach a DETERMINATE answer - and it
    must be PASS on the independence EVIDENCE, not on the absence of a finding.
    A silent pass stays forbidden: every asserted string below is a rule that
    actually fired.
    """
    if not REAL_V9_NET.is_file():
        pytest.skip("v9 netlist not present")
    r = run_checker(REAL_V9_NET)
    assert r.returncode == EXIT_PASS, r.stdout + r.stderr
    assert "ADR-051 is not implemented" not in r.stdout
    # it read the wing interfaces AND the hub array, and it proved independence
    assert "R1 four wing interfaces present" in r.stdout
    assert "R4 hub-array hot net /HUB_PV_P shares no node with the wing series chain" \
        in r.stdout
    # ADR-051 §2.6: the reserved RF_FEED lands carry the cut-sense lines
    assert "R8 cut-sense wired on interface(s): W1, W2, W3, W4" in r.stdout


def test_real_v9_netlist_wing_lands_are_exactly_once():
    """On the shipped board the 8 wing solar lands must be exactly once, and the
    hub array must now be independently present (ADR-051 §2.1 implemented)."""
    if not REAL_V9_NET.is_file():
        pytest.skip("v9 netlist not present")
    r = run_checker(REAL_V9_NET, "--json")
    report = json.loads(r.stdout)
    assert report["verdict"] == "PASS", report
    r2_hits = [c for c in report["checks"] if c.startswith("R2")]
    assert len(r2_hits) == 8, r2_hits
    assert not [f for f in report["failures"] if f.startswith("R2")], report["failures"]
    assert not [f for f in report["failures"] if f.startswith("R6")], report["failures"]
    # ADR-051: the hub array is present, independent and reaches its own converter
    assert any(c.startswith("R3 hub-array nets present") for c in report["checks"])
    assert any(c.startswith("R7 hub-array hot net") for c in report["checks"])


# --------------------------------------------------------------------------- #
# 4. CLI contract
# --------------------------------------------------------------------------- #

def test_json_report_shape(tmp_path):
    p = write(tmp_path, "good.net", good_netlist_text())
    r = run_checker(p, "--json")
    assert r.returncode == EXIT_PASS
    report = json.loads(r.stdout)
    assert report["verdict"] == "PASS"
    assert report["exit_code"] == EXIT_PASS
    assert report["mode"] == "netlist"
    assert report["failures"] == []
    assert report["checks"]


def test_quiet_prints_only_the_verdict(tmp_path):
    p = write(tmp_path, "good.net", good_netlist_text())
    r = run_checker(p, "--quiet")
    assert r.returncode == EXIT_PASS
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1 and lines[0].startswith("VERDICT: PASS")
