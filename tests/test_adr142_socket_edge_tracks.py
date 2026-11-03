"""Gate tests for ADR-142: no copper track may cross a wing-socket cavity edge.

ADR-142 (Accepted 2026-11-03) rules that the `J_W` edge exemption is pad-only,
because a track over the cavity is copper physically cut by a board edge. These
tests exist so that ruling is enforced mechanically rather than remembered.

WHY A TEST AND NOT JUST A SCRIPT: the failure mode this prevents is not "DRC
missed it". DRC reports these correctly — measured, the 4 crossing tracks survive
even a conditionless `edge_clearance (min 0.00mm)` waiver, which removes all 16
pad items (20 -> 4). The real failure mode is a human or agent reading "16 pad
items, all intentional" and treating the 4 track items as the same class of noise.
A gate that can say NO, wired into CI, is the only thing that survives that.

pcbnew lives in the distro interpreter, so the checker runs as a SUBPROCESS —
importing it in-process has segfaulted a pytest run on this host before.
"""
import pathlib
import subprocess

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
CHECKER = REPO / "tracker" / "hardware" / "check_socket_edge_tracks.py"
BOARDS = REPO / "docs" / "analysis" / "hub-solar-route" / "output"


def run(board, *extra):
    return subprocess.run(["/usr/bin/python3", str(CHECKER), str(board), *extra],
                          capture_output=True, text=True)


def test_checker_refuses_on_missing_board():
    """A gate that cannot run must REFUSE, never report clean."""
    r = run("/nonexistent/board.kicad_pcb")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "REFUSE" in r.stdout


@pytest.mark.skipif(not (BOARDS / "after" / "hub_board_v10_lora1280_7of9.kicad_pcb").exists(),
                    reason="shipped board not present in this checkout")
def test_shipped_board_has_no_crossing_tracks():
    """The 5-pair board that ships must pass this gate."""
    r = run(BOARDS / "after" / "hub_board_v10_lora1280_7of9.kicad_pcb")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS" in r.stdout


@pytest.mark.skipif(not (BOARDS / "before" / "hub_board_v10_lora1280_7of9.kicad_pcb").exists(),
                    reason="source board not present in this checkout")
def test_source_board_has_no_crossing_tracks():
    """The untouched board had no tracks at the sockets at all — it is the baseline
    the gate must not flag, and if it ever does, the checker is wrong, not the board."""
    r = run(BOARDS / "before" / "hub_board_v10_lora1280_7of9.kicad_pcb")
    assert r.returncode == 0, r.stdout + r.stderr


def test_gate_can_say_no():
    """A positive control: prove the checker FAILS a board that does cross an edge.

    Without this, a checker that always prints PASS would satisfy every other test
    here. The board is synthesised in /tmp by adding one track straight across a
    `J_W1` cavity (the cavity is x 0..6, y 39.75..40.25), so the assertion does not
    depend on any stored artefact.
    """
    src = BOARDS / "before" / "hub_board_v10_lora1280_7of9.kicad_pcb"
    if not src.exists():
        pytest.skip("source board not present in this checkout")
    import shutil
    import tempfile

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="adr142-"))
    try:
        for f in src.parent.glob(src.stem + ".kicad_*"):
            shutil.copy(f, tmp / f.name)
        board = tmp / src.name
        shutil.copy(src, board)

        add = tmp / "add_crossing.py"
        add.write_text(
            "import sys, pcbnew\n"
            "b = pcbnew.LoadBoard(sys.argv[1])\n"
            "net = b.FindNet('/W1_SOLAR_N')\n"
            "t = pcbnew.PCB_TRACK(b)\n"
            "t.SetStart(pcbnew.VECTOR2I(3000000, 43000000))\n"
            "t.SetEnd(pcbnew.VECTOR2I(3000000, 36000000))\n"
            "t.SetWidth(200000)\n"
            "t.SetLayer(b.GetLayerID('B.Cu'))\n"
            "t.SetNet(net)\n"
            "b.Add(t)\n"
            "pcbnew.SaveBoard(sys.argv[1], b)\n")
        r = subprocess.run(["/usr/bin/python3", str(add), str(board)],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-500:]

        res = run(board)
        assert res.returncode == 1, (
            "the gate PASSED a board carrying a track across a J_W1 cavity — it cannot "
            f"refuse, so it proves nothing. rc={res.returncode}\n{res.stdout}")
        assert "CROSSES EDGE" in res.stdout, res.stdout
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
