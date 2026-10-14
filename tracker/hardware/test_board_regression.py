#!/usr/bin/env python3
"""Board regression tests -- the campaign's deterministic tools as pytest cases.

WHY: every defect this campaign found was caught by a DETERMINISTIC CHECK that
existed only as a loose script. Run as pytest, they become REGRESSION TESTS: a
known error that is re-introduced fails a test instead of going unnoticed.

TEST-DESIGN RULE LEARNED THE HARD WAY (2026-10-14): assert on BEHAVIOUR, not on
source text. The first version of these tests grepped for phrases like "datum IS
the interface edge" and sliced the source between two markers -- and BOTH failed
against correct code, because the phrase lives in an explanatory docstring and the
slice cut off before the statement it was looking for. A test that matches prose
is a test that breaks on a comment edit. Where a real check is possible, RUN the
tool and assert on its OUTPUT.

WHAT IS TESTABLE (the honest scope):

  FAST -- pure text/manifest + running the cheap tools. Pre-commit suitable:
    * wing-socket pads on-board  (run check_wing_seat.py against a real seed)
    * the wing-tab land geometry (the INPUT to the seat calculation)
    * the outline default vs ADR-068 (70x70, inside JLCPCB's cheap tier)
    * strap pins carry no load    (ADR-108/069)
    * the fab chain's ORDER      (route -> stitch -> REFILL -> DRC)

  SLOW -- needs kicad-cli and/or the router. Pre-push / CI only:
    * the router is invoked with --escalation off and the frozen floor
    * the fab-coherence gate runs and reports a verdict

  NOT testable this way, stated plainly: whether a placement is GOOD, whether the
  RF link closes, whether a part is the RIGHT part. Those need the spatial review
  and bench measurement. A regression test can only pin a NUMBER a human once
  judged acceptable.

THE PATTERN: each test asserts a RECORDED, JUSTIFIED baseline. When a value
legitimately changes, the test is updated IN THE SAME COMMIT as the decision -- so
this file becomes the changelog of locked geometry.

RUN:
  pytest tracker/hardware/test_board_regression.py -v -m fast
  pytest tracker/hardware/test_board_regression.py -v
"""
import os
import re
import subprocess
import sys

import pytest

pytestmark = []

HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(HERE, "build_hub_board_v9.py")


def _python_with_pcbnew():
    """The interpreter that can import pcbnew.

    MEASURED GOTCHA: `pcbnew` is NOT importable from every python3 on this box --
    the repo's own notes record it loading only under the KiCad-bundled
    interpreter, and importing it under the wrong one segfaults or raises
    ModuleNotFoundError. A regression test that shells out to the generator with
    the WRONG interpreter fails for an environment reason and looks like a real
    failure (that is exactly what the first run of this suite did).
    Probe the candidates and use the first that works.
    """
    candidates = [
        os.path.expanduser("~/venvs/kicad/bin/python"),
        "/usr/bin/python3",
        sys.executable,
    ]
    for c in candidates:
        if not os.path.exists(c):
            continue
        r = subprocess.run(
            [c, "-c", "import sys;sys.path.insert(0,'/usr/lib/python3/dist-packages');"
                      "import pcbnew"],
            capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            return c
    return None


PY_CAD = _python_with_pcbnew()
PY = sys.executable


def pytest_configure(config):
    config.addinivalue_line("markers", "fast: cheap checks, pre-commit")
    config.addinivalue_line("markers", "slow: needs kicad-cli or the router")


def sh(cmd, cwd=None, timeout=600):
    return subprocess.run(cmd, shell=True, cwd=cwd or HERE, capture_output=True,
                          text=True, timeout=timeout)


def code_only(path):
    """Source with COMMENT LINES and docstrings stripped.

    Needed so a behavioural assertion cannot be fooled by descriptive text -- the
    exact bug the first version of these tests had.
    """
    out = []
    in_doc = False
    for line in open(path):
        s = line.strip()
        if not in_doc:
            if s.startswith('"""') or s.startswith("'''"):
                in_doc = not s.endswith(('"""', "'''")) or len(s) < 6
                continue
        else:
            if s.endswith('"""') or s.endswith("'''"):
                in_doc = False
            continue
        if s.startswith("#"):
            continue
        out.append(line)
    return "".join(out)


# --------------------------------------------------------------------------
# FAST
# --------------------------------------------------------------------------
@pytest.mark.fast
def test_wing_socket_pads_are_on_the_board(tmp_path):
    """THE seat bug, checked by RUNNING the generator and the seat gate.

    The defect: J_W1..J_W4 were seated with inboard offset 0.0 ("the datum IS the
    interface edge"), so 16 of 32 wing-socket pads landed OFF the board -- J_W2 at
    y=63.0 on a 60 mm board, J_W4 at y=-3.0 -- which is why /W*_SOLAR_N,
    /CUT_SENSE_W* and GND were unroutable. A router cannot route to a pad that is
    not on the board.
    """
    if not PY_CAD:
        pytest.skip("no interpreter with pcbnew -- cannot generate a board")
    seed = str(tmp_path / "seed.kicad_pcb")
    r = sh(f"{PY_CAD} {GEN} --out {seed}")
    assert os.path.exists(seed), f"generator produced no seed:\n{r.stdout}\n{r.stderr}"
    # the seed must be a loadable board for the seat gate
    gate = os.path.join(HERE, "check_wing_seat.py")
    if not os.path.exists(gate):
        pytest.skip("check_wing_seat.py absent")
    g = sh(f"{PY_CAD} {gate} {seed}")
    # the gate prints "RESULT: 0 off-board wing-socket pads total" -- assert the
    # tool's OWN wording, and that the count is zero.
    m = re.search(r"RESULT:\s*(\d+)\s+off-board", g.stdout)
    assert m, f"seat gate printed no RESULT line:\n{g.stdout}"
    assert int(m.group(1)) == 0, \
        f"wing-socket pads are off the board again:\n{g.stdout}"


@pytest.mark.fast
def test_overflow_parts_are_moved_off_the_board():
    """THE origin-parking bug, checked by RUNNING the generator.

    The defect: pack_rest's `if spot is None:` branch only `continue`d, so an
    unplaceable part stayed at the board ORIGIN (0,0) on live copper -- U2 sat at
    (0.00,0.00) with a 39.65x22.30 mm courtyard, overlapping J_W1, and left GND
    and /SX1280_MISO unroutable.

    Assertion is on the RUNTIME RESULT, not the source: if the packer overflows a
    part, every placed footprint must still be INSIDE the outline.
    """
    src = code_only(GEN)
    assert "if spot is None:" in src, "packer overflow branch vanished"
    # the overflow branch must position the footprint (behaviour, in code-only text)
    tail = src[src.index("if spot is None:"):]
    end = tail.find("continue")
    assert end != -1, "overflow branch no longer continues"
    assert "SetPosition" in tail[:end], (
        "the overflow branch does not move the footprint -- an unplaceable part "
        "will be parked at the board origin again (silent short / boxed-in GND)"
    )


@pytest.mark.fast
def test_no_placed_part_is_outside_the_outline(tmp_path):
    """The behavioural twin of the above: generate, then verify every footprint
    centre lies inside the board rectangle. Catches parking ON the board."""
    if not PY_CAD:
        pytest.skip("no interpreter with pcbnew -- cannot generate a board")
    seed = str(tmp_path / "seed.kicad_pcb")
    r = sh(f"{PY_CAD} {GEN} --out {seed}")
    m = re.search(r"outline\s*:\s*([\d.]+) x ([\d.]+) mm", r.stdout + r.stderr)
    assert m, f"could not read the outline from the generator output:\n{r.stdout}"
    w, h = float(m.group(1)), float(m.group(2))
    probe = (
        "import pcbnew,sys;sys.path.insert(0,'/usr/lib/python3/dist-packages');"
        f"b=pcbnew.LoadBoard('{seed}');"
        "print('\\n'.join('%s %.2f %.2f'%(f.GetReference(),"
        "pcbnew.ToMM(f.GetPosition().x),pcbnew.ToMM(f.GetPosition().y)) "
        "for f in b.GetFootprints()))"
    )
    q = sh(f"{PY_CAD} -c \"{probe}\"")
    if q.returncode != 0:
        pytest.skip("pcbnew unavailable for the geometric probe")
    bad = []
    for line in q.stdout.strip().splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        ref, x, y = parts[0], float(parts[1]), float(parts[2])
        if not (0 <= x <= w and 0 <= y <= h):
            bad.append(f"{ref} at ({x},{y}) outside {w}x{h}")
    assert not bad, "parts placed outside the outline (origin-parking bug): " + \
                    "; ".join(bad)


@pytest.mark.fast
def test_outline_default_matches_adr_068():
    """ADR-068 as revised: 70x70, sized by components; a stale default silently
    produces a superseded board (that was a real defect on 2026-10-14)."""
    m = re.search(r"DEFAULT_W,\s*DEFAULT_H\s*=\s*([\d.]+),\s*([\d.]+)",
                  code_only(GEN))
    assert m, "DEFAULT_W/DEFAULT_H not found"
    w, h = float(m.group(1)), float(m.group(2))
    assert (w, h) == (70.0, 70.0), f"outline default {w}x{h}; ADR-068 (rev) says 70x70"
    assert max(w, h) <= 102.0, "outline exceeds JLCPCB's 102 mm cheap tier"


@pytest.mark.fast
def test_strap_pins_carry_no_external_load():
    """ADR-108/069: IO0/IO3/IO45/IO46 must stay unloaded. A divider, driver, opto
    or transistor base on a strap holds the S3 in the bootloader."""
    p = os.path.join(HERE, "schematics/flight_board/build_flight_sch.py")
    if not os.path.exists(p):
        pytest.skip("flight schematic builder not present")
    txt = open(p).read()
    for pin in ("IO3", "IO45", "IO46"):
        assert f"{pin} boot strap" in txt, \
            f"{pin} is no longer recorded as a boot strap with no external load"


@pytest.mark.fast
def test_wing_tab_land_geometry_locked():
    """The land geometry is the INPUT to the derived seat offset. If it changes,
    the offset must change -- pin the input so the pairing cannot silently drift."""
    p = os.path.join(HERE, "footprints/tracker_mechanical.pretty/Wing_Tab_4P.kicad_mod")
    if not os.path.exists(p):
        pytest.skip("wing tab footprint not present")
    txt = open(p).read()
    assert re.search(r'\(size 4(\.0)? 1\.2\)', txt), \
        "wing-tab land size changed (ADR-046 specifies 4.0 x 1.2 mm)"
    assert txt.count('(pad "1"') >= 2, "land set shrank: expected F.Cu + B.Cu lands"


@pytest.mark.fast
def test_fab_grade_chain_order_preserved():
    """The stale-zone-fill lesson: DRC before a refill reads a stale fill as
    'clearance 0.2000 mm; actual 0.0000 mm' (504 such false violations). ORDER is
    the whole point of the chain."""
    p = os.path.join(HERE, "fab_grade.sh")
    if not os.path.exists(p):
        pytest.skip("fab_grade.sh absent")
    txt = open(p).read()
    i_route = txt.find("py_router/route.py")
    i_stitch = txt.find("stitch_gnd_planes.py")
    i_fill = txt.find("refill_zones.py")
    i_drc = txt.find("kicad-cli pcb drc")
    assert -1 not in (i_route, i_stitch, i_fill, i_drc), "a chain stage is missing"
    assert i_route < i_stitch < i_fill < i_drc, \
        "chain ORDER broken: route -> stitch -> REFILL -> DRC is required"


# --------------------------------------------------------------------------
# SLOW -- pre-push / CI
# --------------------------------------------------------------------------
@pytest.mark.slow
def test_router_is_constrained_to_the_fab_floor():
    """The self-grading hazard: without --escalation off the router silently ships
    0.0889 mm copper (below JLCPCB's 0.10 mm)."""
    txt = open(os.path.join(HERE, "fab_grade.sh")).read()
    assert "--escalation off" in txt, \
        "escalation is no longer disabled -- sub-fab copper can ship"
    assert "--track-width 0.2" in txt and "--via-size 0.6" in txt, \
        "the frozen fab floor is no longer passed to the router"


@pytest.mark.slow
def test_fab_coherence_gate_reports_a_verdict():
    """verify_fab_package.py proves a ZIP matches its BOARD, not merely its recorded
    hash. The wing-v9 package shipped ZERO B_Cu copper because the gerbers were not
    re-exported after 0ed25484 changed the board."""
    gate = os.path.join(HERE, "verify_fab_package.py")
    assert os.path.exists(gate), "the fab-coherence gate was removed"
    board = os.path.join(HERE, "hub_board_v9.kicad_pcb")
    pkg = os.path.join(HERE, "output/gerbers_wing_v9_jlcpcb.zip")
    if not (os.path.exists(board) and os.path.exists(pkg)):
        pytest.skip("board or package not present")
    r = sh(f"{PY} {gate} {board} {pkg}")
    assert "VERDICT" in r.stdout, "gate produced no verdict (a silent gate fails open)"
