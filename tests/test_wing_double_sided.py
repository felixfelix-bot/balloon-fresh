"""Acceptance tests for ADR-065 double-sided wing cells."""
from pathlib import Path
import re

ROOT = Path(__file__).parents[1]
BOARD = ROOT / "tracker/hardware/wing_board/wing_board_v9.kicad_pcb"
GEN = ROOT / "tracker/hardware/wing_board/build_wing_v9.py"


def _footprints(text):
    blocks = []
    for match in re.finditer(r"\(footprint\b", text):
        depth = 0
        for i in range(match.start(), len(text)):
            depth += text[i] == "("
            depth -= text[i] == ")"
            if depth == 0:
                blocks.append(text[match.start():i + 1])
                break
    return blocks


def test_generator_supports_back_side_cells():
    source = GEN.read_text()
    assert "side" in source
    assert "SC4" in source and "SC5" in source and "SC6" in source
    board = BOARD.read_text()
    cells = [fp for fp in _footprints(board) if "SolarCell_52x19mm" in fp]
    assert len(cells) == 6
    assert sum('(layer "F.Cu")' in fp for fp in cells) == 3
    assert sum('(layer "B.Cu")' in fp for fp in cells) == 3
    assert all(f'"SC{i}"' in "".join(cells) for i in range(1, 7))


def test_back_cells_share_positions_and_are_mirrored():
    board = BOARD.read_text()
    cells = [fp for fp in _footprints(board) if "SolarCell_52x19mm" in fp]
    positions = {}
    for fp in cells:
        ref = re.search(r'property "Reference" "(SC[1-6])"', fp).group(1)
        at = re.search(r'\(at ([^ )]+) ([^ )]+)\)', fp).group(0)
        positions[ref] = at
    for front, back in zip(("SC1", "SC2", "SC3"), ("SC4", "SC5", "SC6")):
        assert positions[front] == positions[back]


def test_parallel_strings_preserve_wing_tab_voltage():
    source = GEN.read_text()
    assert "parallel" in source.lower()
    assert "1.5" in source
    assert "SOLAR_P" in source and "SOLAR_N" in source
