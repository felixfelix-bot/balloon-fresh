#!/usr/bin/env python3
"""Tests for the ADR-045 antenna solder-access checker.

Run:  /usr/bin/python3 -m pytest tracker/hardware/tools/test_antenna_access_check.py -q

The fixture is a synthetic `.kicad_pcb` generated here with pcbnew (no
committed binary fixture): one RF module footprint plus one neighbour whose
courtyard distance is the variable under test.

Requires the system pcbnew python module (KiCad 9), i.e. run under
/usr/bin/python3, not the user venv.
"""

import json
import os
import sys

import pytest

pytest.importorskip("pcbnew")
import pcbnew  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import antenna_access_check as chk  # noqa: E402

MM = 1_000_000


def _v(x, y):
    return pcbnew.VECTOR2I(int(round(x * MM)), int(round(y * MM)))


def _rect(fp, layer, x1, y1, x2, y2):
    s = pcbnew.PCB_SHAPE(fp)
    s.SetShape(pcbnew.SHAPE_T_RECT)
    s.SetStart(_v(x1, y1))
    s.SetEnd(_v(x2, y2))
    s.SetLayer(layer)
    s.SetWidth(int(0.05 * MM))
    fp.Add(s)


def _smd_lset():
    ls = pcbnew.LSET()
    for lay in (pcbnew.F_Cu, pcbnew.F_Paste, pcbnew.F_Mask):
        ls.AddLayer(lay)
    return ls


def _pad(fp, origin, number, local_x, local_y, sx=2.0, sy=0.7):
    p = pcbnew.PAD(fp)
    p.SetNumber(number)
    p.SetShape(pcbnew.PAD_SHAPE_RECT)
    p.SetSize(pcbnew.VECTOR2I(int(sx * MM), int(sy * MM)))
    p.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    p.SetLayerSet(_smd_lset())
    p.SetPosition(_v(origin[0] + local_x, origin[1] + local_y))
    p.SetFPRelativePosition(_v(local_x, local_y))
    fp.Add(p)
    return p


def build_board(path, pad_local, neighbour_courtyard_y0=None, module_libid="LoRa2021_Castellated"):
    """Synthetic board.

    U2  = RF module, body 20 x 15 mm, courtyard 20.6 x 15.6 mm, centred at (50, 50).
          Antenna pins 9 and 10 are placed per `pad_local` (local mm offsets).
    R1  = neighbour footprint with a courtyard whose +y edge is
          `neighbour_courtyard_y0` (absolute mm); omitted when None.
    """
    board = pcbnew.BOARD()
    ox, oy = 50.0, 50.0

    fp = pcbnew.FOOTPRINT(board)
    fp.SetFPID(pcbnew.LIB_ID("fixture", module_libid))
    fp.SetReference("U2")
    fp.SetPosition(_v(ox, oy))
    _rect(fp, pcbnew.F_Fab, ox - 10, oy - 7.5, ox + 10, oy + 7.5)
    _rect(fp, pcbnew.F_CrtYd, ox - 10.3, oy - 7.8, ox + 10.3, oy + 7.8)
    for number, (lx, ly) in pad_local.items():
        _pad(fp, (ox, oy), number, lx, ly)
    board.Add(fp)

    if neighbour_courtyard_y0 is not None:
        # The neighbour sits directly over pin 9 (at x = ox + 10), so the gap
        # under test is purely the y clearance to pin 9's copper.
        nb = pcbnew.FOOTPRINT(board)
        nb.SetFPID(pcbnew.LIB_ID("fixture", "TEST_NEIGHBOUR"))
        nb.SetReference("R1")
        nb.SetPosition(_v(ox + 10.0, neighbour_courtyard_y0 + 1.0))
        _rect(nb, pcbnew.F_CrtYd, ox + 7.0, neighbour_courtyard_y0,
              ox + 13.0, neighbour_courtyard_y0 + 2.0)
        board.Add(nb)

    pcbnew.SaveBoard(str(path), board)
    return str(path)


# --- fixture variants -------------------------------------------------------

def _pads_edge():
    # pin 9 on the +x perimeter, pin 10 on the -x perimeter, pin 5 interior
    return {"9": (10.0, 0.0), "10": (-10.0, 0.0), "5": (0.0, 0.0)}


def _pads_pin9_under_body():
    return {"9": (0.0, 3.0), "10": (-10.0, 0.0), "5": (0.0, -3.0)}


# --- tests ------------------------------------------------------------------

def test_all_antenna_ports_edge_and_clear_is_pass(tmp_path):
    pcb = build_board(tmp_path / "pass.kicad_pcb", _pads_edge(),
                      neighbour_courtyard_y0=52.0)  # gap 1.65 mm
    rc = chk.main([pcb, "--json"])
    assert rc == 0, "expected PASS (exit 0)"


def test_under_body_antenna_pad_fails(tmp_path, capsys):
    pcb = build_board(tmp_path / "under.kicad_pcb", _pads_pin9_under_body(),
                      neighbour_courtyard_y0=56.0)  # far: isolate the edge test
    rc = chk.main([pcb, "--json"])
    out = capsys.readouterr().out
    assert rc == 1, "an antenna pad under the module body must FAIL (exit 1)"
    assert "9" in out


def test_occluding_neighbour_within_min_gap_fails(tmp_path, capsys):
    pcb = build_board(tmp_path / "occ.kicad_pcb", _pads_edge(),
                      neighbour_courtyard_y0=51.0)  # gap 0.65 mm < 1.0 default
    rc = chk.main([pcb, "--json"])
    out = capsys.readouterr().out
    assert rc == 1, "a neighbour courtyard inside the min access gap must FAIL"
    assert "R1" in out


def test_min_gap_is_configurable(tmp_path):
    pcb = build_board(tmp_path / "occ.kicad_pcb", _pads_edge(),
                      neighbour_courtyard_y0=51.0)  # gap 0.65 mm
    assert chk.main([pcb, "--json"]) == 1                        # default 1.0 mm
    assert chk.main([pcb, "--json", "--min-gap", "0.5"]) == 0    # relaxed


def test_unreadable_board_exits_2(tmp_path):
    rc = chk.main([str(tmp_path / "does-not-exist.kicad_pcb"), "--json"])
    assert rc == 2


def test_unknown_antenna_pin_set_exits_2(tmp_path):
    pcb = build_board(tmp_path / "sx.kicad_pcb", _pads_edge(),
                      neighbour_courtyard_y0=None, module_libid="SX1280_dummy")
    rc = chk.main([pcb, "--json"])
    assert rc == 2, "an RF part with an unknown antenna pin set must be CANNOT-VERIFY"


def test_report_contains_pad_number_edge_flag_and_gap(tmp_path, capsys):
    pcb = build_board(tmp_path / "report.kicad_pcb", _pads_edge(),
                      neighbour_courtyard_y0=52.0)
    chk.main([pcb, "--json"])
    data = json.loads(capsys.readouterr().out)
    mod = next(m for m in data["modules"] if m["ref"] == "U2")
    by_num = {p["pad"]: p for p in mod["pads"]}
    assert set(by_num) >= {"9", "10", "5"}
    assert by_num["9"]["edge_accessible"] is True
    assert by_num["5"]["edge_accessible"] is False
    assert by_num["9"]["nearest_gap_mm"] == pytest.approx(1.65, abs=0.05)
    assert by_num["9"]["nearest_other_ref"] == "R1"


def test_unknown_antenna_pins_override_makes_it_checkable(tmp_path):
    pcb = build_board(tmp_path / "sx.kicad_pcb", _pads_edge(),
                      neighbour_courtyard_y0=52.0, module_libid="SX1280_dummy")
    assert chk.main([pcb, "--json"]) == 2
    assert chk.main([pcb, "--json", "--antenna-pins", "U2:9,10"]) == 0
