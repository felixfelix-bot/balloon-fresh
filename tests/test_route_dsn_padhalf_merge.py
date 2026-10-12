#!/usr/bin/env python3
"""Regression tests for DSN pad-half merge in route_hub_v9_freerouting.

CONTEXT (measured 2026-10-12): KiCad's DSN exporter emits every multi-face
SMD pad of an edge-card socket TWICE -- "J_W1-4" (F.Cu half) and
"J_W1-4@1" (B.Cu half), same net, same XY, opposite copper face. FreeRouting
can NEVER join them (the inserted wing tab bridges them mechanically per
ADR-046), so they stall the router: run 5 made zero progress (18 -> 18
unrouted, board hash unchanged). agentee's router failed the same nets.

FIX: patch_dsn_rules() drops each @N back-half when its front-half is
present in the same (pins ...) span, RESTRICTED to edge-card families
(J_W*, ANT*, CUT_SENSE*) so U1-41@1..12 (12 REAL ESP32 castellation pads at
DIFFERENT XY, all legitimately in the GND net) keep their suffixes.
"""
import importlib.util
import re
import shutil
import sys
import tempfile
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.join(HERE, "..", "tracker", "hardware",
                   "route_hub_v9_freerouting.py")

spec = importlib.util.spec_from_file_location("rt", MOD)
rt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rt)

# real exported DSN fragments (hub_v9_run6.dsn, 2026-10-12)
RULE_BLOCK = """(rule
      (width 200)
      (clearance 200)
      (clearance 50 (type smd_smd))
    )"""
MULTI_LINE_GND = """(net "GND"
   (pins
      U1-41 J_W1-4 J_W1-4@1 J_W2-1 J_W2-1@1
      U1-41@1 U1-41@2 U1-41@3 U1-41@4 U1-41@5 U1-41@6
      U1-41@7 U1-41@8 U1-41@9 U1-41@10 U1-41@11 U1-41@12
      ANT1-2 ANT1-2@1 ANT1-2@2 J_W3-2 J_W3-2@1
   )
)
""" + RULE_BLOCK
SINGLE_LINE = """(net "W1_SOLAR_N"
   (pins D_BP1-2 J_W1-4 J_W1-4@1 D_BP2-1 J_W2-1 J_W2-1@1)
)
""" + RULE_BLOCK
NOT_EDGE = """(net "+3V3"
   (pins U1-41 U4-15 U4-18 U4-20 U4-22 U4-24)
)
""" + RULE_BLOCK


def run_merge(text):
    with tempfile.NamedTemporaryFile("w", suffix=".dsn", delete=False) as f:
        f.write(text)
        path = f.name
    try:
        rt.patch_dsn_rules(path, 200, 200)
        return open(path).read()
    finally:
        os.unlink(path)


def test_multiline_gnd_block_merges_edge_halves():
    out = run_merge(MULTI_LINE_GND)
    # all J_W/ANT @N halves gone
    assert not re.findall(r"J_W\d-\d+@\d|ANT\d-\d+@\d", out), out
    # all 12 U1-41@N REAL pads KEPT
    assert len(re.findall(r"U1-41@\d+", out)) == 12, out
    # front halves kept
    assert "J_W1-4" in out and "ANT1-2" in out
    # parens balanced (the earlier bug: trailing ')' token self-matched)
    assert out.count("(") == out.count(")"), out


def test_single_line_net_merges():
    out = run_merge(SINGLE_LINE)
    assert "J_W1-4@1" not in out
    assert "J_W2-1@1" not in out
    assert "J_W1-4" in out and "J_W2-1" in out
    assert "D_BP1-2" in out and "D_BP2-1" in out
    assert out.count("(") == out.count(")")


def test_non_edge_family_untouched():
    out = run_merge(NOT_EDGE)
    # no @N present at all -> unchanged net
    assert "U4-15" in out and "U1-41" in out
    assert "@1" not in out


def test_full_real_dsn_roundtrip():
    # end-to-end on the actual exported DSN if present
    real = "/tmp/hub_v9_run6.dsn"
    if not os.path.exists(real):
        print("  (skipped: no real DSN on this machine)")
        return
    shutil.copy(real, "/tmp/test_run6.dsn")
    rt.patch_dsn_rules("/tmp/test_run6.dsn", 200, 200)
    txt = open("/tmp/test_run6.dsn").read()
    assert not re.findall(r"J_W\d-\d+@\d|ANT\d-\d+@\d|CUT_SENSE[^ )]*@\d", txt)
    assert len(re.findall(r"U1-41@\d+", txt)) == 12
    assert txt.count("(") == txt.count(")")


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted({k: v for k, v in globals().items()
                             if k.startswith("test_")}.items()):
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {name}: {e}")
    sys.exit(1 if failed else 0)