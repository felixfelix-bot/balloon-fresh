#!/usr/bin/env python3
"""tests for `scripts/bypass_diode_check.py` — the ADR-053 bypass-diode gate.

The gate is FAIL-CLOSED: it exits 0 only when it has *proved* that every solar
series group in the netlist has a correctly polarised, adequately rated Schottky
bypass diode across it.  Everything else is non-zero.  These tests therefore do
three things:

  1. prove the gate PASSES a deliberately-good fixture (so it is not a no-op that
     always fails, which would be equally useless);
  2. prove the gate FAILS deliberately-BAD fixtures — the required mutation test
     is `test_group_with_no_diode_fails`, which removes a group's diode and
     asserts the gate returns exit 1 and names the group;
  3. prove the gate never silent-passes: an unreadable input, a netlist with no
     solar group, an unresolvable diode polarity, and a schematic-only label scan
     all return non-zero.

Fixtures are generated in `tmp_path` as real KiCad-shaped netlists (with pin
functions, which is what carries diode polarity), then the checker is invoked
through `subprocess` so its REAL exit code is what is asserted.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CHECKER = REPO / "scripts" / "bypass_diode_check.py"
REAL_V9_NET = REPO / "tracker" / "hardware" / "schematics" / "flight_board" / "v9_flight.net"
REAL_V9_SCH = REPO / "tracker" / "hardware" / "schematics" / "flight_board" / "v9_flight.kicad_sch"

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_UNDETERMINED = 2


# --------------------------------------------------------------------------- #
# fixture builders
# --------------------------------------------------------------------------- #

def netlist_text(components, nets) -> str:
    """Render a minimal but valid KiCad netlist s-expression.

    `components` is [(ref, part, value, dnp)], `nets` is [(name, [(ref, pin, pinfunc)])].
    """
    out = ['(export (version "E")']
    out.append('  (design (source "fixture.kicad_sch") (date "2026-10-07") '
               '(tool "Eeschema 9.0.8")')
    out.append('    (sheet (number "1") (name "/") (tstamps "/") '
               '(title_block (title "ADR-053 fixture"))))')
    out.append("  (components")
    for ref, part, value, dnp in components:
        out.append('    (comp (ref "%s") (value "%s") (footprint "fp")' % (ref, value))
        out.append('      (libsource (lib "fixture") (part "%s"))' % part)
        if dnp:
            out.append('      (property (name "dnp"))')
        out.append('      (tstamps "00000000-0000-0000-0000-000000000000"))')
    out.append("  )")
    out.append("  (nets")
    for i, (name, nodes) in enumerate(nets, start=1):
        out.append('    (net (code "%d") (name "%s") (class "Default")' % (i, name))
        for ref, pin, func in nodes:
            out.append('      (node (ref "%s") (pin "%s") (pinfunction "%s") '
                       '(pintype "passive"))' % (ref, pin, func))
        out.append("    )")
    out.append("  ))")
    return "\n".join(out) + "\n"


def make_netlist(diodes=None, cells=None, include_wings=(1, 2, 3, 4)) -> str:
    """Build a netlist from a topology description.

    diodes: {wing_n: {"value":..., "polarity_ok":bool, "dnp":bool, "no_pinfunc":bool}}
            a wing key that is absent means "no diode across this wing at all"
    cells : {ref: {"value":..., "part":..., "pos":net, "neg":net,
                   "posfunc":..., "negfunc":..., "diode":bool, "dvalue":...,
                   "no_pinfunc":bool}}
    """
    diodes = diodes or {}
    cells = cells or {}
    comps = []
    netmap: dict[str, list[tuple[str, str, str]]] = {}

    def add(net, ref, pin, func):
        netmap.setdefault(net, []).append((ref, pin, func))

    for n in include_wings:
        ref = "J_W%d" % n
        comps.append((ref, "WING_SOCKET_4P", "WING_SOCKET_4P", False))
        add("W%d_SOLAR_P" % n, ref, "1", "SOLAR_P")
        add("W%d_SOLAR_N" % n, ref, "4", "SOLAR_N")

    for n, spec in sorted(diodes.items()):
        ref = "D_BP%d" % n
        comps.append((ref, "D_Schottky", spec.get("value", "B240"), spec.get("dnp", False)))
        pos, neg = "W%d_SOLAR_P" % n, "W%d_SOLAR_N" % n
        k_net, a_net = (pos, neg) if spec.get("polarity_ok", True) else (neg, pos)
        kfunc = "" if spec.get("no_pinfunc") else "K"
        afunc = "" if spec.get("no_pinfunc") else "A"
        add(k_net, ref, "1", kfunc)
        add(a_net, ref, "2", afunc)

    for ref, spec in sorted(cells.items()):
        comps.append((ref, spec.get("part", "SolarCell_78x39mm"),
                      spec.get("value", "SolarCell"), False))
        add(spec["pos"], ref, "1", spec.get("posfunc", "+"))
        add(spec["neg"], ref, "2", spec.get("negfunc", "-"))
        if spec.get("diode"):
            dref = "D_%s" % ref
            comps.append((dref, "D_Schottky", spec.get("dvalue", "B240"), False))
            add(spec["pos"], dref, "1", "K")
            add(spec["neg"], dref, "2", "A")

    return netlist_text(comps, sorted(netmap.items()))


def good_netlist() -> str:
    """Every wing has a correctly polarised, adequately rated B240 across it."""
    return make_netlist(diodes={n: {"value": "B240"} for n in (1, 2, 3, 4)})


def run_checker(path, *args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CHECKER), str(path), *args],
                          capture_output=True, text=True, cwd=str(REPO))


def write(tmp_path, name, text) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


# --------------------------------------------------------------------------- #
# 1. the gate must PASS a good fixture (it is not a no-op)
# --------------------------------------------------------------------------- #

def test_good_netlist_passes(tmp_path):
    p = write(tmp_path, "good.net", good_netlist())
    r = run_checker(p)
    assert r.returncode == EXIT_PASS, r.stdout + r.stderr
    assert "VERDICT: PASS" in r.stdout


# --------------------------------------------------------------------------- #
# 2. THE MUTATION TESTS — the gate must FAIL deliberately-bad fixtures
# --------------------------------------------------------------------------- #

def test_group_with_no_diode_fails(tmp_path):
    """REQUIRED MUTATION: wing 3 has NO bypass diode across it.

    This is the defect ADR-053 exists to forbid and the check exists to catch:
    without the diode, a cracked cell in wing 3 can open or reverse-stress the
    whole 12-cell series string.
    """
    diodes = {1: {"value": "B240"}, 2: {"value": "B240"}, 4: {"value": "B240"}}  # no wing 3
    p = write(tmp_path, "missing.net", make_netlist(diodes=diodes))
    r = run_checker(p)
    assert r.returncode == EXIT_FAIL, "the gate MUST fail on a group with no diode: " + r.stdout
    assert "B2" in r.stdout
    assert "wing 3" in r.stdout
    assert "NO bypass diode" in r.stdout


def test_wrong_polarity_fails(tmp_path):
    """DELIBERATELY BAD: wing 2's diode is reversed (cathode on the negative node)."""
    diodes: dict = {n: {"value": "B240"} for n in (1, 2, 3, 4)}
    diodes[2] = {"value": "B240", "polarity_ok": False}
    p = write(tmp_path, "reversed.net", make_netlist(diodes=diodes))
    r = run_checker(p)
    assert r.returncode == EXIT_FAIL, r.stdout + r.stderr
    assert "reversed" in r.stdout
    assert "wing 2" in r.stdout


def test_underrated_bat54_fails(tmp_path):
    """DELIBERATELY BAD: every wing carries the 200 mA / 30 V BAT54 the spec names."""
    p = write(tmp_path, "bat54.net",
              make_netlist(diodes={n: {"value": "BAT54 (DNP)"} for n in (1, 2, 3, 4)}))
    r = run_checker(p)
    assert r.returncode == EXIT_FAIL, r.stdout + r.stderr
    assert "B4" in r.stdout
    assert "under-rated" in r.stdout


def test_solar_cell_with_no_diode_fails(tmp_path):
    """DELIBERATELY BAD: an on-board hub cell (PVA1) has no diode across it."""
    p = write(tmp_path, "hubcell.net", make_netlist(
        diodes={n: {"value": "B240"} for n in (1, 2, 3, 4)},
        cells={"PVA1": {"pos": "HUB_PV_P", "neg": "HUB_PV_MID", "diode": False}},
    ))
    r = run_checker(p)
    assert r.returncode == EXIT_FAIL, r.stdout + r.stderr
    assert "PVA1" in r.stdout
    assert "NO bypass diode" in r.stdout


def test_solar_cell_with_diode_passes(tmp_path):
    """The same hub cell, now with a correctly polarised diode, is accepted."""
    p = write(tmp_path, "hubcell_ok.net", make_netlist(
        diodes={n: {"value": "B240"} for n in (1, 2, 3, 4)},
        cells={"PVA1": {"pos": "HUB_PV_P", "neg": "HUB_PV_MID", "diode": True}},
    ))
    r = run_checker(p)
    assert r.returncode == EXIT_PASS, r.stdout + r.stderr


# --------------------------------------------------------------------------- #
# 3. the gate must NEVER silent-pass (non-zero when it cannot determine)
# --------------------------------------------------------------------------- #

def test_netlist_with_no_solar_group_is_undetermined(tmp_path):
    p = write(tmp_path, "nosolar.net",
              netlist_text([("U1", "TPS7A02", "LDO", False)],
                           [("+3V3", [("U1", "2", "")])]))
    r = run_checker(p)
    assert r.returncode == EXIT_UNDETERMINED, r.stdout + r.stderr
    assert r.returncode != EXIT_PASS
    assert "B1" in r.stdout


def test_unresolvable_polarity_is_undetermined(tmp_path):
    """A diode sits across the group but its K/A polarity cannot be read."""
    p = write(tmp_path, "nopol.net",
              make_netlist(diodes={n: {"value": "B240", "no_pinfunc": True}
                                   for n in (1, 2, 3, 4)}))
    r = run_checker(p)
    assert r.returncode == EXIT_UNDETERMINED, r.stdout + r.stderr
    assert "B3" in r.stdout


def test_unreadable_input_is_nonzero(tmp_path):
    p = write(tmp_path, "garbage.net", "this is not a kiCad netlist at all\n")
    r = run_checker(p)
    assert r.returncode == EXIT_UNDETERMINED, r.stdout + r.stderr
    assert r.returncode != EXIT_PASS


def test_missing_file_is_nonzero(tmp_path):
    r = run_checker(tmp_path / "does-not-exist.net")
    assert r.returncode == EXIT_UNDETERMINED
    assert r.returncode != EXIT_PASS


def test_schematic_mode_never_passes(tmp_path):
    """A .kicad_sch is label-level only — it must never return PASS."""
    sch = write(tmp_path, "x.kicad_sch", """
(kicad_sch (version 20230121) (generator eeschema)
  (symbol (lib_id "fixture:WING_SOCKET_4P") (property "Reference" "J_W1" (at 0 0 0)))
  (label "W1_SOLAR_P" (at 10 10 0) (effects (font (size 1.27 1.27))))
)
""")
    r = run_checker(sch)
    assert r.returncode == EXIT_UNDETERMINED, r.stdout + r.stderr
    assert r.returncode != EXIT_PASS


# --------------------------------------------------------------------------- #
# 4. DNP handling
# --------------------------------------------------------------------------- #

def test_dnp_is_a_note_by_default_and_a_failure_with_the_flag(tmp_path):
    p = write(tmp_path, "dnp.net",
              make_netlist(diodes={n: {"value": "B240", "dnp": True} for n in (1, 2, 3, 4)}))
    r = run_checker(p)
    assert r.returncode == EXIT_PASS, r.stdout + r.stderr          # DNP is a note by default
    assert "DNP" in r.stdout
    r2 = run_checker(p, "--require-populated")
    assert r2.returncode == EXIT_FAIL, r2.stdout + r2.stderr        # ...a failure on a cutter flight
    assert "B5" in r2.stdout


# --------------------------------------------------------------------------- #
# 5. the real repo netlist, and the JSON interface
# --------------------------------------------------------------------------- #

def test_real_v9_netlist_is_populated_and_rerated():
    """The shipped v9 netlist's bypass diodes are now POPULATED and >= 2 A / 40 V.

    This test used to assert FAIL and to look for "BAT54", because the shipped
    design carried the DNP BAT54 the socket spec named.  ADR-051 §2.7 and
    ADR-053 §2.2 (as amended by ADR-054 §3.2) re-rate them off the disqualified
    200 mA / 30 V part, and ADR-054 §6.3 directs the change into the v9
    generator.  So the gate must now PASS the shipped netlist - and PASS on
    evidence: every group covered, every part in the >= 2 A / 40 V class, none
    DNP.  The strict cutter-flight flag is asserted too, so the population
    requirement cannot regress silently.
    """
    if not REAL_V9_NET.is_file():
        pytest.skip("v9 netlist not present in this worktree")
    r = run_checker(REAL_V9_NET)
    assert r.returncode == EXIT_PASS, r.stdout + r.stderr
    assert "SS24" in r.stdout
    assert "BAT54" not in r.stdout
    # ADR-051 §2.4 decision 4.2: a cutter flight needs them FITTED, not provided
    r2 = run_checker(REAL_V9_NET, "--require-populated")
    assert r2.returncode == EXIT_PASS, r2.stdout + r2.stderr


def test_json_report_shape(tmp_path):
    p = write(tmp_path, "good.net", good_netlist())
    r = run_checker(p, "--json")
    assert r.returncode == EXIT_PASS, r.stdout + r.stderr
    data = json.loads(r.stdout)
    assert data["verdict"] == "PASS"
    assert data["exit_code"] == EXIT_PASS
    assert data["failures"] == []
    assert any("B2" in c for c in data["checks"])
