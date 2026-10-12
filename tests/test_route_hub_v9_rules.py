#!/usr/bin/env python3
"""Tests for the DSN rules assertion that makes FreeRouting converge on the hub v9.

WHY THESE TESTS EXIST -- the 2026-10-12 routing history, all measured:

  run 1 (KiCad exporter default): routed 97 -> 16 unrouted in 12 passes. The
    753 DRC violations that followed were 501 "Track/ia vs Zone GND_PLANE"
    + 202 hole_clearance against the board's STORED PRE-ROUTE zone fill --
    fixed by ZONE_FILLER refill (753 -> 55), NOT by re-routing.

  runs 2-4 (the bug these tests now guard): `patch_dsn_rules` scaled the rule
    scalars by 10000 because it misread `(resolution um 10)` as applying to
    rule values. The rules are RAW MICRONS: 200 = 0.2 mm. The patch demanded
    2.0/2.5 mm clearance and the router stalled identically at pass 2 every
    time (96/95 unrouted, 134/121 violations).

So the correct export is: keep KiCad's own 200/200 (raw um = 0.2 mm = the
board's netclass, verified by `kicad-cli pcb drc` reporting "clearance
0.2000 mm"), keep the smd_smd exemption, keep the plane declarations.
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
def exported_dsn(mod, tmp_path_factory):
    """A REAL export of the real board."""
    dsn = tmp_path_factory.mktemp("dsn") / "hub_v9.dsn"
    mod.export_dsn(str(BOARD), str(dsn))
    return dsn


def test_rules_are_raw_microns_not_resolution_scaled(exported_dsn):
    """THE regression test for runs 2-4. The rule scalars must be 200 (raw um
    = 0.2 mm = the board's own netclass). The x10000 unit bug demanded 2.0 mm
    and stalled the router three times -- this must never happen again."""
    txt = exported_dsn.read_text()
    # Global rule block: exactly width 200 / clearance 200.
    assert re.search(r"\(rule\s*\n\s*\(width 200\)\s*\n\s*\(clearance 200\)", txt), (
        "global rule is not the board's own 0.2 mm pair (200 raw um) -- "
        "if the exporter changed, re-derive before routing"
    )
    # And the monster values must be absent.
    assert "(width 2000)" not in txt and "(clearance 2000)" not in txt, \
        "x10000 unit bug present: 2000 raw um = 2.0 mm clearance -- stalls the router"


def test_rules_assertion_is_a_noop_on_the_exporter_output(exported_dsn, tmp_path):
    """patch_dsn_rules(200, 200) on an already-correct DSN changes nothing."""
    src = exported_dsn.read_text()
    dst = tmp_path / "again.dsn"
    dst.write_text(src)
    mod = load_mod()
    mod.patch_dsn_rules(str(dst), width_um=200, clearance_um=200)
    assert dst.read_text() == src, "assertion rewrite is not idempotent at 200/200"


def test_patch_preserves_the_smd_smd_exemption(exported_dsn):
    """KiCad's `(clearance 50 (type smd_smd))` sub-rule MUST survive.

    Without it the castellated wing-pad pairs (J_W1..J_W4, touching by design)
    become 134 permanent violations and the router stalls (measured run 2).
    """
    txt = exported_dsn.read_text()
    assert re.search(r"\(clearance 50 \(type smd_smd\)\)", txt), \
        "smd_smd exemption dropped by the rules assertion -- router will stall on wing pads"


def test_patch_refuses_unknown_rule_format(tmp_path, mod):
    """If the exporter's rule-block format changes, the assertion must REFUSE
    rather than silently route at an unknown clearance."""
    dsn = tmp_path / "changed.dsn"
    dsn.write_text("(structure\n      (rule\n        (width 9999)\n      )\n    )\n")
    with pytest.raises(SystemExit, match="format changed"):
        mod.patch_dsn_rules(str(dsn))


def test_dsn_declares_the_gnd_planes_and_4_layers(exported_dsn):
    """GND is a plane on In1/F/B -- the router must not treat it as a routed
    net. If the plane declarations vanish, GND flood-stitching disappears."""
    txt = exported_dsn.read_text()
    n_planes = len(re.findall(r"\(plane GND", txt))
    assert n_planes == 3, f"expected 3 GND plane polygons, found {n_planes}"
    for layer in ("F.Cu", "In1.Cu", "B.Cu"):
        assert f"(plane GND (polygon {layer}" in txt, f"GND plane on {layer} missing"


def test_router_command_uses_java25():
    """FreeRouting v2.2.4 is class-file 69 (Java 25); the system default java
    is 17 and dies with UnsupportedClassVersionError. Measured run 1."""
    import subprocess
    out = subprocess.run(
        ["/usr/lib/jvm/java-25-openjdk-amd64/bin/java", "-version"],
        capture_output=True, text=True)
    assert out.returncode == 0