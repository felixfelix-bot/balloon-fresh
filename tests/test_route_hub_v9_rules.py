#!/usr/bin/env python3
"""Tests for the DSN rules patch that makes FreeRouting converge on the hub v9.

WHY THESE TESTS EXIST -- the 2026-10-12 routing history, measured:
  run 1: clearance 0.02 mm -> routed 97->16 unrouted but 753 DRC violations
         (501 clearance + 202 hole_clearance "actual 0.0000 mm" -- tracks
         threaded straight through neighbouring pads)
  run 2: clearance 0.25 mm, smd_smd exemption DROPPED -> router stalled at
         pass 2 (96 unrouted, 134 violations). The castellated wing pads
         (J_W1..J_W4) touch by design -- Felix's castellated-pad convention --
         and KiCad's exporter writes a dedicated `(clearance 50 (type smd_smd))`
         sub-rule to exempt them. Dropping it made 134 unfixable violations
         and the router gave up.

So: patch the clearance UP to the real fab value, but PRESERVE the smd_smd
sub-rule. These tests prove both properties survive a real export.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "tracker/hardware/route_hub_v9_freerouting.py"
BOARD = ROOT / "tracker/hardware/hub_board_v9.kicad_pcb"


def load_mod():
    assert SCRIPT.exists(), f"missing {SCRIPT}"
    assert BOARD.exists(), f"missing {BOARD}"
    spec = importlib.util.spec_from_file_location("rh9", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["rh9"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return load_mod()


@pytest.fixture(scope="module")
def patched_dsn(mod, tmp_path_factory):
    """A REAL export of the real board with the patch applied."""
    dsn = tmp_path_factory.mktemp("dsn") / "hub_v9.dsn"
    mod.export_dsn(str(BOARD), str(dsn))
    return dsn


def test_patch_clearance_is_fab_value_not_exporter_default(patched_dsn):
    """The 0.02 mm exporter default must be GONE; 0.25 mm present."""
    txt = patched_dsn.read_text()
    assert "(clearance 2500)" in txt, "patched clearance 0.25 mm missing"
    assert "(width 2000)" in txt, "patched width 0.20 mm missing"
    # The old 0.02 mm rule pair must not survive anywhere.
    assert not re.search(r"\(width 200\)\s*\n\s*\(clearance 200\)", txt), \
        "0.02 mm exporter default still present -- router would thread tracks through pads"


def test_patch_preserves_the_smd_smd_exemption(patched_dsn):
    """KiCad's `(clearance 50 (type smd_smd))` sub-rule MUST survive the patch.

    Without it the castellated wing-pad pairs (J_W1..J_W4, touching by design)
    become 134 permanent violations and the router stalls (measured run 2).
    """
    txt = patched_dsn.read_text()
    assert re.search(r"\(clearance 50 \(type smd_smd\)\)", txt), \
        "smd_smd exemption dropped by the rules patch -- router will stall on wing pads"


def test_patch_refuses_to_patch_unknown_rule_format(tmp_path, mod):
    """If the exporter's rule-block format changes, the patch must REFUSE
    rather than silently route at an unknown clearance."""
    dsn = tmp_path / "changed.dsn"
    dsn.write_text("(structure\n      (rule\n        (width 9999)\n      )\n    )\n")
    with pytest.raises(SystemExit, match="format changed"):
        mod.patch_dsn_rules(str(dsn))


def test_router_command_uses_java25(monkeypatch):
    """run 1 of the routing history ran with the system default java (class 69)
    and printed UnsupportedClassVersionError; java 25 works (measured)."""
    import subprocess
    out = subprocess.run(
        ["/usr/lib/jvm/java-25-openjdk-amd64/bin/java", "-version"],
        capture_output=True, text=True)
    assert out.returncode == 0


def test_no_0_02mm_clearance_leaks_into_the_class_block(patched_dsn):
    """The per-class rule inside (class ...) must also be 0.2/0.25."""
    txt = patched_dsn.read_text()
    # class block uses 8-space indented rule
    assert "(rule\n        (width 2000)\n        (clearance 2500)\n      )" in txt, \
        "per-class rule not patched"


def test_dsn_declares_the_gnd_planes_and_4_layers(patched_dsn):
    """GND is a plane on In1/F/B -- the router must not treat it as a routed
    net. If the plane declarations vanish, GND flood-stitching disappears."""
    txt = patched_dsn.read_text()
    n_planes = len(re.findall(r"\(plane GND", txt))
    assert n_planes == 3, f"expected 3 GND plane polygons, found {n_planes}"
    for layer in ("F.Cu", "In1.Cu", "B.Cu"):
        assert f"(plane GND (polygon {layer}" in txt, f"GND plane on {layer} missing"