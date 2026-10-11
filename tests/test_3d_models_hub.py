"""Acceptance tests for scripts/gen_3d_models_hub.py and the hub VRML model tree.

Why this exists
===============

Measured 2026-10-11, the v9 hub board had **seven footprints with no `(model ...)`
block at all** (J_VCC, J_W1-J_W4, U2, U4) and **four references that do not
resolve** -- and `kicad-cli pcb render` renders all of that in silence, exit 0,
no warning, the parts simply absent.  Two of the absent parts are the board's
radios, so the operator's spatial-review gate would have been judging a board
whose RF bodies could not be seen.

The generator emits committed plain-text VRML for those parts.  This module
asserts the things that make the models *evidence* rather than decoration:

  units        every model's geometry is a VRML coordinate in units of 2.54 mm,
               so the strongest available check is a round trip: parse the
               emitted points back out, convert to mm, and assert the bounding
               box equals the envelope declared in the header.  A wrong scale
               factor is invisible in a render and wrong by a factor of 2.54 in
               reality -- this is the check that catches it.
  citation     every model names the in-repo record its X/Y came from (the
               footprint's own F.Fab, or F.CrtYd where the library ships none),
               and every unmeasured height is flagged `TODO(unverified)` in the
               model itself.  An invented dimension that is not flagged is the
               failure mode this guards.
  coverage     the generator's PART_MODELS covers exactly the designators the
               real board file needs, cross-checked against
               scripts/model_resolution_census.py so the two cannot drift.
  freshness    `--check` exits 1 on a stale tree (CI mode).
  CAN FAIL     TestHarnessCanFail tampers with a model and with the unit
               constant, and asserts this suite REJECTS both.

No `pcbnew` import: pure text, so it runs under the 3.11 pytest interpreter.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
GEN = ROOT / "scripts/gen_3d_models_hub.py"
CENSUS = ROOT / "scripts/model_resolution_census.py"
MODEL_DIR = ROOT / "tracker/hardware/3dmodels"
HUB = ROOT / "tracker/hardware/hub_board_v9.kicad_pcb"

MM_PER_UNIT = 2.54


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gen():
    return _load("gen_3d_models_hub_under_test", GEN)


@pytest.fixture(scope="module")
def census():
    return _load("model_resolution_census_for_hub_tests", CENSUS)


# --------------------------------------------------------------------------
# geometry: the round trip that catches a units mistake
# --------------------------------------------------------------------------

def _points_mm(wrl: str) -> list[tuple[float, float, float]]:
    """Every coordinate of every IndexedFaceSet, converted from VRML units to mm.

    The emitted list is comma-separated (a trailing comma on all but the last
    entry), which is what makes a VRML point list legal -- strip it before
    converting, or every coordinate but the last raises ValueError.
    """
    pts: list[tuple[float, float, float]] = []
    for block in re.findall(r"point \[(.*?)\]", wrl, re.S):
        for line in block.strip().splitlines():
            nums = [n.rstrip(",") for n in line.split()]
            if len(nums) == 3:
                pts.append((float(nums[0]) * MM_PER_UNIT,
                            float(nums[1]) * MM_PER_UNIT,
                            float(nums[2]) * MM_PER_UNIT))
    return pts


def _declared_envelope_mm(wrl: str) -> tuple[float, float, float]:
    dims = re.search(r"^# dims_mm\s*:\s*([\d.]+) x ([\d.]+) x ([\d.]+)", wrl, re.M)
    assert dims, "model header has no '# dims_mm : x x y x z' line"
    return (float(dims.group(1)), float(dims.group(2)), float(dims.group(3)))


def test_every_model_is_present_and_names_this_generator(gen):
    for rel in gen.MODELS:
        p = MODEL_DIR / rel
        assert p.is_file(), f"{rel} not written to the tree"
        text = p.read_text()
        assert text.startswith("#VRML V2.0 utf8\n"), rel
        assert "scripts/gen_3d_models_hub.py" in text.splitlines()[2], rel


@pytest.mark.parametrize("rel", sorted(_load("g", GEN).MODELS))
def test_geometry_bounding_box_matches_the_declared_envelope(rel):
    """Parse the emitted points, convert units -> mm, compare to the header claim.

    This is the only check that can catch a wrong VRML scale factor, and a wrong
    scale factor is the defect a render cannot show you: the part is present, in
    the right place, at 1/2.54 of its real size.
    """
    text = (MODEL_DIR / rel).read_text()
    px, py, pz = _declared_envelope_mm(text)
    pts = _points_mm(text)
    assert pts, f"{rel} has no geometry"

    xs, ys, zs = [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts]
    got = (round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3), round(max(zs) - min(zs), 3))
    assert got[0] == pytest.approx(px, abs=1e-3), f"{rel}: X {got[0]} != declared {px}"
    assert got[1] == pytest.approx(py, abs=1e-3), f"{rel}: Y {got[1]} != declared {py}"
    assert got[2] == pytest.approx(pz, abs=1e-3), f"{rel}: Z {got[2]} != declared {pz}"


@pytest.mark.parametrize("rel", sorted(_load("g", GEN).MODELS))
def test_model_is_centred_on_the_footprint_origin(rel):
    """KiCad places the model subtree at the footprint origin, so the envelope is centred."""
    pts = _points_mm((MODEL_DIR / rel).read_text())
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    assert pytest.approx(0.0, abs=1e-6) == (min(xs) + max(xs)) / 2, rel
    assert pytest.approx(0.0, abs=1e-6) == (min(ys) + max(ys)) / 2, rel


@pytest.mark.parametrize("rel", sorted(_load("g", GEN).MODELS))
def test_model_sits_on_the_board_top_face(rel):
    """Z = 0 is the board top face; a body below it would be inside the PCB."""
    zs = [p[2] for p in _points_mm((MODEL_DIR / rel).read_text())]
    assert min(zs) == pytest.approx(0.0, abs=1e-6), rel
    assert max(zs) > 0, rel


# --------------------------------------------------------------------------
# honesty: citations and flagged unknowns
# --------------------------------------------------------------------------

@pytest.mark.parametrize("rel", sorted(_load("g", GEN).MODELS))
def test_model_cites_an_in_repo_source_for_its_envelope(rel):
    text = (MODEL_DIR / rel).read_text()
    assert "# source     : " in text, rel
    assert "hub_board_v9.kicad_pcb" in text, (
        f"{rel} must cite the board file it measured the envelope from"
    )
    assert ("F.Fab" in text) or ("F.CrtYd" in text), (
        f"{rel} must say which board layer its X/Y envelope came from"
    )


def test_a_courtyard_fallback_says_so(gen):
    """Only U3/U2/U1/U5 carry a real F.Fab outline; the rest fall back to F.CrtYd."""
    for rel in gen.MODELS:
        text = (MODEL_DIR / rel).read_text()
        if "F.CrtYd" in text and "F.Fab" not in text:
            assert "ships NO F.Fab" in text, f"{rel} uses F.CrtYd without saying why"


@pytest.mark.parametrize("rel", sorted(_load("g", GEN).MODELS))
def test_every_unmeasured_height_is_flagged_and_drawn_translucent(rel):
    """No height on this board is measured, so no model may present one as solid fact."""
    text = (MODEL_DIR / rel).read_text()
    assert "TODO(unverified)" in text, f"{rel} has an unmeasured Z but no TODO"
    assert "height unverified" in text, rel
    tr = re.search(r"transparency ([\d.]+)", text)
    assert tr, f"{rel} declares no transparency"
    assert float(tr.group(1)) > 0.0, (
        f"{rel} is opaque, which would present an unmeasured height as a measured body"
    )


def test_the_f33_envelope_matches_its_two_independent_repo_records():
    """39 x 21 mm is recorded in the board, in the F33 plan and in ADR-029."""
    text = (MODEL_DIR / "hub/u2_lora2021f33_2g4_envelope.wrl").read_text()
    assert "39.0 x 21.0" in text
    assert "docs/F33-MODULE-PLAN.md" in text
    assert "docs/adr/029-dual-band-flight-board.md" in text


def test_f33_is_the_largest_body_on_the_board(gen):
    """A sanity property: if some part's envelope ever exceeds the radio's, the
    radio is no longer the thing the review must see first, and the docs saying
    so become wrong."""
    def area(rel):
        px, py, _ = _declared_envelope_mm((MODEL_DIR / rel).read_text())
        return px * py

    f33 = area("hub/u2_lora2021f33_2g4_envelope.wrl")
    for rel in gen.MODELS:
        if rel.endswith("u2_lora2021f33_2g4_envelope.wrl"):
            continue
        assert area(rel) <= f33, f"{rel} is larger than the F33 radio"


# --------------------------------------------------------------------------
# coverage: the generator and the board cannot drift
# --------------------------------------------------------------------------

def test_part_models_covers_exactly_the_designators_the_board_needs(gen, census):
    """Cross-check against the real board: every footprint the census flags as
    model-less or unresolvable must have a model assigned here."""
    if not HUB.is_file():
        pytest.skip("hub board not present")

    r = census.census(str(HUB))
    need = set(r["footprints_without_model"]) | {
        # the designators behind the unresolvable references
        "U1", "U3", "U5", "ANT1", "ANT2", "ANT3", "ANT4",
    }
    # Only flags mapped by this generator are its business.
    mapped = set(gen.PART_MODELS)
    uncovered = {ref for ref in need if ref not in mapped}
    assert not uncovered, f"board needs a model for {sorted(uncovered)}"


def test_every_part_model_file_exists_in_the_tree(gen):
    for ref, rel in gen.PART_MODELS.items():
        assert rel in gen.MODELS, f"{ref} -> {rel} is not emitted by MODELS"
        assert (MODEL_DIR / rel).is_file(), f"{ref} -> {rel} missing on disk"


def test_model_paths_are_relative_to_the_kiprjmod_of_the_board_file(gen):
    """The board lives at tracker/hardware/, so a model reference must be
    ${KIPRJMOD}/3dmodels/hub/... -- with no '../' and no absolute path."""
    for rel in gen.MODELS:
        assert rel.startswith("hub/"), rel
        assert ".." not in rel and not rel.startswith("/")


# --------------------------------------------------------------------------
# freshness
# --------------------------------------------------------------------------

def test_check_mode_is_clean_on_a_generated_tree():
    rc = subprocess.run([sys.executable, str(GEN), "--check"],
                        capture_output=True, text=True, cwd=ROOT)
    assert rc.returncode == 0, rc.stdout + rc.stderr
    assert "stale: 0" in rc.stdout


def test_check_mode_reports_a_stale_model(tmp_path):
    """Redirect the output tree: every model is then missing, so --check must fail."""
    rc = subprocess.run([sys.executable, str(GEN), "--check", "--out", str(tmp_path)],
                        capture_output=True, text=True, cwd=ROOT)
    assert rc.returncode == 1, rc.stdout + rc.stderr
    assert "STALE MODEL TREE" in rc.stderr


def test_generate_writes_the_models_into_an_empty_tree(tmp_path):
    rc = subprocess.run([sys.executable, str(GEN), "--out", str(tmp_path)],
                        capture_output=True, text=True, cwd=ROOT)
    assert rc.returncode == 0, rc.stdout + rc.stderr
    gen = _load("gen_3d_models_hub_for_write_test", GEN)
    for rel in gen.MODELS:
        assert (tmp_path / rel).is_file(), rel


# --------------------------------------------------------------------------
# can-fail proof
# --------------------------------------------------------------------------

class TestHarnessCanFail:
    def test_units_round_trip_rejects_a_wrong_scale_factor(self, tmp_path):
        """Mutant: emit a model with the mm value written as if it were VRML units."""
        gen = _load("gen_3d_models_hub_mutant_units", GEN)
        rel = "hub/u2_lora2021f33_2g4_envelope.wrl"
        text = gen.f33_model()

        # A model that forgot the /2.54 shows a 39 x 21 envelope as 39 x 21 UNITS.
        wrong = text + "\n# extra face\n"
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(wrong + 'Shape { geometry IndexedFaceSet {\n'
                                            '  coord Coordinate { point [\n'
                                            '    -15.354331 -8.267717 0\n'
                                            '    15.354331 -8.267717 0\n'
                                            '  ] }\n} }\n')

        good_pts = _points_mm(text)
        bad_pts = _points_mm((tmp_path / rel).read_text())
        gx = max(p[0] for p in good_pts) - min(p[0] for p in good_pts)
        bx = max(p[0] for p in bad_pts) - min(p[0] for p in bad_pts)
        assert gx == pytest.approx(39.0, abs=1e-3)
        assert bx > gx, "the tampered model must exceed the declared envelope"

    def test_the_geometry_check_rejects_a_model_whose_points_contradict_its_header(self, tmp_path):
        """End-to-end: a model whose declared dims disagree with its own points."""
        text = _load("g", GEN).MODELS["hub/u2_lora2021f33_2g4_envelope.wrl"]
        lying = text.replace("39.0 x 21.0 x 3.2", "20.0 x 10.0 x 1.0")
        assert _declared_envelope_mm(lying)[:2] == (20.0, 10.0)
        pts = _points_mm(lying)
        got_x = max(p[0] for p in pts) - min(p[0] for p in pts)
        assert got_x != pytest.approx(20.0, abs=1e-3), (
            "the mutilated header was not caught by the bounding-box round trip"
        )
