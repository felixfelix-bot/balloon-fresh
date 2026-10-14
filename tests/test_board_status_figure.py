"""Acceptance tests for the machine-checked board-status figure.

Why this exists
===============

The board-status figure answers "what is actually routed, per layer, on which
side?"  A figure is only evidence if a command can tell a faithful rendering
from a wrong one, so this module asserts:

  faithfulness   ``board_status_figure_check.py`` re-reads the produced SVG and
                 confirms every data-* value, every bar geometry, every pad bar
                 and every label matches the census the figure was drawn from;
  completeness   every board, layer and pad side in the census appears in the
                 figure -- nothing silently dropped;
  layout         no two text labels collide (the first version of this figure
                 drew a 100-char detail line straight through the layer labels,
                 which is exactly the defect this check catches);
  CAN FAIL       ``TestHarnessCanFail`` re-runs the checks against a TAMPERED
                 census and asserts the checker REJECTS it.  A checker that only
                 ever sees consistent input cannot distinguish "figure is
                 correct" from "checker never fires".

The figure/generator tools are imported by path and `pcbnew` is never imported
here: `pcbnew` only loads under /usr/bin/python3.14 and SEGFAULTS the 3.11 pytest
interpreter, so the census step is exercised from its JSON contract instead.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
HW = ROOT / "tracker/hardware"
FIG_PY = HW / "board_status_figure.py"
CHECK_PY = HW / "board_status_figure_check.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def fig():
    return _load("board_status_figure", FIG_PY)


def census_fixture() -> list[dict]:
    """A census with one board of every verdict class.

    Shaped exactly like board_status_census.py output so the figure and the
    checker are exercised against the real contract.
    """
    def layers(**kw):
        base = {n: {"segments": 0, "length_mm": 0.0, "vias": 0,
                    "zones": 0, "zones_filled": 0}
                for n in ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")}
        for name, vals in kw.items():
            base[name].update(vals)
        return base

    def board(name, cl, fp, pads, lay, unconn):
        totals = {
            "segments": sum(v["segments"] for v in lay.values()),
            "vias": sum(v["vias"] for v in lay.values()),
            "zones": sum(v["zones"] for v in lay.values()),
            "zones_filled": sum(v["zones_filled"] for v in lay.values()),
        }
        if totals["segments"] == 0 and totals["vias"] == 0 and totals["zones"] == 0:
            verdict = "placed_only"
        elif totals["segments"] == 0 and totals["vias"] == 0:
            verdict = "plane_only"
        elif unconn == 0:
            verdict = "routed"
        else:
            verdict = "partial"
        return {"file": f"/x/{name}.kicad_pcb", "name": name, "copper_layers": cl,
                "footprints": fp, "pads": pads, "layers": lay,
                "totals": totals, "drc_unconnected": unconn, "verdict": verdict}

    return [
        board("wing_board_v9", 2, 15,
              {"front": 16, "back": 6, "through": 0, "npth": 3},
              layers(**{"F.Cu": {"segments": 10, "length_mm": 218.0, "vias": 8},
                        "B.Cu": {"segments": 10, "length_mm": 218.0}}),
              0),
        board("hub_board_v9", 4, 39,
              {"front": 210, "back": 16, "through": 16, "npth": 0},
              layers(**{"F.Cu": {"zones": 1, "zones_filled": 1},
                        "In1.Cu": {"zones": 1, "zones_filled": 1},
                        "B.Cu": {"zones": 1, "zones_filled": 1}}),
              101),
        board("empty_board", 2, 4,
              {"front": 0, "back": 0, "through": 2, "npth": 0},
              layers(), 12),
    ]


def _write(tmp_path, boards):
    census = tmp_path / "census.json"
    census.write_text(json.dumps(boards))
    svg = tmp_path / "status.svg"
    return census, svg


def _render(fig, boards, tmp_path):
    census, svg = _write(tmp_path, boards)
    svg.write_text(fig.render(boards))
    return census, svg


def test_verdict_classes_are_distinguished():
    """The census contract must separate plane_only from placed_only/routed."""
    verdicts = {b["name"]: b["verdict"] for b in census_fixture()}
    assert verdicts == {"wing_board_v9": "routed",
                        "hub_board_v9": "plane_only",
                        "empty_board": "placed_only"}


def test_figure_passes_its_own_check(fig, tmp_path):
    census, svg = _render(fig, census_fixture(), tmp_path)
    proc = subprocess.run([sys.executable, str(CHECK_PY), str(svg), str(census)],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS" in proc.stdout
    assert "FAIL" not in proc.stdout


def test_figure_is_wellformed_xml_with_every_board_label(fig, tmp_path):
    import xml.etree.ElementTree as ET
    boards = census_fixture()
    _, svg = _render(fig, boards, tmp_path)
    root = ET.parse(svg).getroot()
    ns = "{http://www.w3.org/2000/svg}"
    labels = "\n".join("".join(t.itertext()) for t in root.iter(f"{ns}text"))
    for b in boards:
        assert b["name"] in labels
        assert b["verdict"] in labels


def test_back_string_layer_split_is_visible_not_just_totalled(fig, tmp_path):
    """F.Cu and B.Cu must each be drawn with their own segment count.

    A total-only figure hid the original defect (the back string was isolated
    while the front carried every segment), so both layers must appear.
    """
    import xml.etree.ElementTree as ET
    boards = census_fixture()
    _, svg = _render(fig, boards, tmp_path)
    root = ET.parse(svg).getroot()
    ns = "{http://www.w3.org/2000/svg}"
    wing = [g for g in root.iter(f"{ns}g") if g.get("data-board") == "wing_board_v9"]
    assert len(wing) == 1
    seen = {}
    for lg in wing[0].iter(f"{ns}g"):
        if lg.get("data-layer"):
            seen[lg.get("data-layer")] = int(lg.get("data-segments"))
    assert seen["F.Cu"] == 10 and seen["B.Cu"] == 10, seen


class TestHarnessCanFail:
    """Negative controls: the checker must REJECT wrong figures."""

    def test_detects_tampered_census(self, fig, tmp_path):
        census, svg = _render(fig, census_fixture(), tmp_path)
        boards = json.loads(census.read_text())
        for b in boards:
            if b["name"] == "hub_board_v9":
                b["layers"]["In1.Cu"]["segments"] = 42
        bad = tmp_path / "tampered.json"
        bad.write_text(json.dumps(boards))
        proc = subprocess.run([sys.executable, str(CHECK_PY), str(svg), str(bad)],
                              capture_output=True, text=True)
        assert proc.returncode != 0, "checker accepted a tampered census"
        assert "segments 0 != 42" in proc.stdout

    def test_detects_dropped_label(self, fig, tmp_path):
        """Stripping a board's text labels must fail the completeness check."""
        census, svg = _render(fig, census_fixture(), tmp_path)
        text = svg.read_text().replace(">B.Cu<", "><")
        svg.write_text(text)
        proc = subprocess.run([sys.executable, str(CHECK_PY), str(svg), str(census)],
                              capture_output=True, text=True)
        assert proc.returncode != 0, "checker accepted a figure with a dropped label"
        assert "label missing" in proc.stdout

    def test_detects_wrong_bar_height(self, fig, tmp_path):
        """A visually wrong bar (geometry != declared scale) must be caught."""
        import re
        census, svg = _render(fig, census_fixture(), tmp_path)
        text = svg.read_text()
        before = text
        # rewrite the height of the whole segments-bar rect tag (data-role is
        # emitted AFTER height, so anchor on the full tag, not on the role attr)
        text = re.sub(r'(<rect [^>]*?)height="[0-9.]+"([^>]*?data-role="segments-bar")',
                      r'\g<1>height="9.0"\g<2>', text, count=1)
        assert text != before, "tamper did not change the bar height"
        svg.write_text(text)
        proc = subprocess.run([sys.executable, str(CHECK_PY), str(svg), str(census)],
                              capture_output=True, text=True)
        assert proc.returncode != 0, "checker accepted a wrong bar height"
        assert "bar height" in proc.stdout


def test_layout_budget_invariant_holds():
    """The left column must not reach the copper stack (real collision defect)."""
    fig = _load("board_status_figure", FIG_PY)
    assert fig.LEFT_X + fig.LEFT_W < fig.STACK_X
    assert fig.STACK_X + fig.STACK_W < fig.PAD_X
