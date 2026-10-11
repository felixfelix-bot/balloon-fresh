"""Acceptance tests for scripts/model_resolution_census.py.

Why this exists
===============

The spatial-review gate says "an LLM with good spatial reasoning reviews the
render before the board is done".  That gate is only real if the parts the
reviewer is asked to judge are actually *in* the render.  A `kicad-cli pcb
render` whose footprints reference 3D models that do not resolve prints
"Successfully created 3D render image" and silently omits those parts -- so the
reviewer judges the placement of a board with invisible radios.

This module asserts the census tool reports that condition as a number:

  resolution     a reference under ${KIPRJMOD} resolves against the board's own
                 directory, and ${KICAD<n>_3DMODEL_DIR} against the *compiled-in*
                 default (/usr/share/kicad/3dmodels).  Not the shell environment:
                 that variable is unset in the shell and the renderer does not
                 read it from there, so expanding from os.environ would report a
                 part missing that the renderer draws, or vice versa.
  block walking  a footprint block nests arbitrarily deep (pads, models,
                 graphics).  A regex-based split truncates at the first inner
                 ')' and mis-attributes the NEXT footprint's models to the
                 previous one -- so the census would excuse the very part it
                 should flag.
  omission       "no (model ...) block at all" is a *different* defect from "the
                 model file is not there", and is reported separately.
  exit code      `--check` must exit 1 when a reference does not resolve, and
                 when a --require-refs designator carries no model at all.
  CAN FAIL       TestHarnessCanFail mutates the module under test (renames a
                 KiCad variable it must expand) and asserts the suite REJECTS
                 the mutant.  A test that passes against a broken tool has not
                 tested anything.

No `pcbnew` import here: this is a text parse, so it runs under the 3.11 pytest
interpreter (pcbnew only loads under /usr/bin/python3.14).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/model_resolution_census.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def mod():
    return _load("model_resolution_census_under_test", SCRIPT)


# --------------------------------------------------------------------------
# synthetic board fixtures
# --------------------------------------------------------------------------

def _fp(ref: str, models: list[str], *, inner: str = "") -> str:
    """One footprint block.  `inner` injects extra nesting (pads/graphics)."""
    body = "".join(f'\n    (model "{m}"\n      (offset (xyz 0 0 0))\n    )' for m in models)
    return (
        f'  (footprint "Lib:Part_{ref}"\n'
        f'    (layer "F.Cu")\n'
        f'    {inner}\n'
        f'    (property "Reference" "{ref}"\n      (at 0 0 0)\n    ){body}\n'
        f'  )'
    )


def _board(*footprints: str) -> str:
    return "(kicad_pcb (version 20241229) (generator pcbnew)\n" + "\n".join(footprints) + "\n)\n"


def write_board(tmp_path: Path, name: str, *footprints: str) -> Path:
    p = tmp_path / name
    p.write_text(_board(*footprints))
    return p


def touch_model(board_dir: Path, rel: str) -> Path:
    f = board_dir / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("# a 3D model\n")
    return f


# --------------------------------------------------------------------------
# resolution
# --------------------------------------------------------------------------

def test_kiprjmod_expands_to_the_boards_own_directory(mod, tmp_path):
    touch_model(tmp_path, "models/U1.wrl")
    board = write_board(tmp_path, "b.kicad_pcb", _fp("U1", ["${KIPRJMOD}/models/U1.wrl"]))

    r = mod.census(str(board))

    assert r["resolved"] == 1, r
    assert r["unresolved_refs"] == []


def test_kiprjmod_model_that_is_absent_is_unresolved(mod, tmp_path):
    board = write_board(tmp_path, "b.kicad_pcb", _fp("U1", ["${KIPRJMOD}/models/nope.wrl"]))

    r = mod.census(str(board))

    assert r["resolved"] == 0
    assert r["unresolved_refs"] == ["${KIPRJMOD}/models/nope.wrl"]
    assert "U1" not in r["footprints_without_model"], "U1 HAS a block; it just does not resolve"


def test_kicadN_3dmodel_dir_expands_to_the_compiled_in_default(mod, tmp_path):
    """The renderer uses KiCad's built-in default, not the shell environment."""
    target = Path(mod.KICAD_3DMODEL_DIR)
    if not target.is_dir():
        pytest.skip(f"{target} not installed on this machine")

    # Pick any real model in the package so the assertion is about expansion.
    real = next(target.rglob("*.wrl"), None)
    if real is None:
        pytest.skip("no .wrl files in the 3D model package")

    ref = "${KICAD9_3DMODEL_DIR}/" + real.relative_to(target).as_posix()
    board = write_board(tmp_path, "b.kicad_pcb", _fp("U1", [ref]))

    r = mod.census(str(board))

    assert r["unresolved_refs"] == [], r
    assert r["resolved"] == 1


@pytest.mark.parametrize("var", ["KICAD8_3DMODEL_DIR", "KICAD7_3DMODEL_DIR"])
def test_previous_major_variables_also_expand(mod, tmp_path, var):
    """A board generated under an older KiCad still names that release's var."""
    board = write_board(tmp_path, "b.kicad_pcb", _fp("U1", [f"${{{var}}}/does/not/exist.wrl"]))

    r = mod.census(str(board))

    assert r["unresolved_refs"] == [f"${{{var}}}/does/not/exist.wrl"]
    assert "/usr/share/kicad/3dmodels/does/not/exist.wrl" in mod._expand(
        f"${{{var}}}/does/not/exist.wrl", str(tmp_path)
    )


def test_environment_variable_does_not_change_resolution(mod, tmp_path, monkeypatch):
    """KICAD9_3DMODEL_DIR in the shell must NOT be consulted.

    Guarding this explicitly: an implementation that read os.environ would pass
    on a machine where the variable happens to be exported and silently diverge
    from the renderer everywhere else.
    """
    monkeypatch.setenv("KICAD9_3DMODEL_DIR", str(tmp_path / "decoy"))
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    (decoy / "m.wrl").write_text("# decoy\n")

    board = write_board(tmp_path, "b.kicad_pcb", _fp("U1", ["${KICAD9_3DMODEL_DIR}/m.wrl"]))
    r = mod.census(str(board))

    assert r["unresolved_refs"] == ["${KICAD9_3DMODEL_DIR}/m.wrl"], "decoy was consulted"


# --------------------------------------------------------------------------
# block walking
# --------------------------------------------------------------------------

def test_nested_parens_do_not_mis_attribute_the_next_footprint(mod, tmp_path):
    """The defect a regex split would produce: U2's model counted as U1's."""
    deep = (
        '(pad "1"\n      (at 0 0 0)\n      (net 1 "GND")\n'
        '      (model (offset (xyz 0 0 0)) (scale (xyz 1 1 1)))\n    )'
    )
    b = write_board(
        tmp_path,
        "b.kicad_pcb",
        _fp("U1", ["${KIPRJMOD}/u1.wrl"], inner=deep),
        _fp("U2", ["${KIPRJMOD}/u2.wrl"]),
    )

    r = mod.census(str(b))

    assert r["footprints"] == 2, r
    assert r["refs_by_footprint"]["U1"] == ["${KIPRJMOD}/u1.wrl"], r["refs_by_footprint"]
    assert r["refs_by_footprint"]["U2"] == ["${KIPRJMOD}/u2.wrl"], r["refs_by_footprint"]


def test_footprint_without_any_model_block_is_reported_separately(mod, tmp_path):
    touch_model(tmp_path, "u1.wrl")
    b = write_board(
        tmp_path,
        "b.kicad_pcb",
        _fp("U1", ["${KIPRJMOD}/u1.wrl"]),
        _fp("H1", []),
        _fp("U2", []),
    )

    r = mod.census(str(b))

    assert r["footprints"] == 3
    assert r["footprints_without_model"] == ["H1", "U2"]
    assert r["unresolved_refs"] == [], "an omission is not an unresolvable reference"
    assert r["resolved"] == 1


def test_multiple_model_references_on_one_footprint_are_all_counted(mod, tmp_path):
    touch_model(tmp_path, "a.wrl")
    b = write_board(tmp_path, "b.kicad_pcb", _fp("U1", ["${KIPRJMOD}/a.wrl", "${KIPRJMOD}/b.wrl"]))

    r = mod.census(str(b))

    assert r["model_refs"] == 2
    assert r["resolved"] == 1
    assert r["unresolved_refs"] == ["${KIPRJMOD}/b.wrl"]


# --------------------------------------------------------------------------
# exit codes
# --------------------------------------------------------------------------

def test_check_exits_zero_when_everything_resolves(mod, tmp_path, capsys):
    touch_model(tmp_path, "u1.wrl")
    b = write_board(tmp_path, "b.kicad_pcb", _fp("U1", ["${KIPRJMOD}/u1.wrl"]))

    rc = mod.main(["--check", str(b)])

    assert rc == 0
    assert "OK" in capsys.readouterr().out


def test_check_exits_one_when_a_reference_does_not_resolve(mod, tmp_path, capsys):
    b = write_board(tmp_path, "b.kicad_pcb", _fp("U2", ["${KIPRJMOD}/missing.wrl"]))

    rc = mod.main(["--check", str(b)])

    assert rc == 1
    out = capsys.readouterr()
    assert "FAIL" in out.out
    assert "MISSING" in out.out
    assert "not ready for a spatial review" in out.err.lower()


def test_without_check_a_bad_board_still_exits_zero(mod, tmp_path):
    """--check is the gate; a bare census is a report, so it must not fail a run."""
    b = write_board(tmp_path, "b.kicad_pcb", _fp("U2", ["${KIPRJMOD}/missing.wrl"]))

    assert mod.main([str(b)]) == 0


def test_require_refs_fails_on_a_designator_with_no_model(mod, tmp_path, capsys):
    b = write_board(tmp_path, "b.kicad_pcb", _fp("U1", []), _fp("U2", []))

    rc = mod.main(["--check", "--require-refs", "U1,U2", str(b)])

    assert rc == 1
    assert "REQUIRED but has no model: U1, U2" in capsys.readouterr().out


def test_require_refs_passes_when_the_designator_carries_a_resolvable_model(mod, tmp_path):
    touch_model(tmp_path, "u1.wrl")
    b = write_board(tmp_path, "b.kicad_pcb", _fp("U1", ["${KIPRJMOD}/u1.wrl"]), _fp("H1", []))

    assert mod.main(["--check", "--require-refs", "U1", str(b)]) == 0


def test_require_refs_ignores_designators_absent_from_the_board(mod, tmp_path):
    """Asking a board to require a part it does not carry is a caller error, not a board defect."""
    b = write_board(tmp_path, "b.kicad_pcb", _fp("U1", []))

    assert mod.main(["--check", "--require-refs", "U9", str(b)]) == 0


def test_several_boards_are_reported_and_any_failure_fails_the_run(mod, tmp_path, capsys):
    touch_model(tmp_path, "ok.wrl")
    good = write_board(tmp_path, "good.kicad_pcb", _fp("U1", ["${KIPRJMOD}/ok.wrl"]))
    bad = write_board(tmp_path, "bad.kicad_pcb", _fp("U2", ["${KIPRJMOD}/gone.wrl"]))

    rc = mod.main(["--check", str(good), str(bad)])

    out = capsys.readouterr()
    assert rc == 1
    assert "2 board(s) NOT ready" in out.err
    assert f"{bad.name}" in out.out


def test_json_report_is_written(mod, tmp_path):
    touch_model(tmp_path, "u1.wrl")
    b = write_board(tmp_path, "b.kicad_pcb", _fp("U1", ["${KIPRJMOD}/u1.wrl"]))
    out = tmp_path / "report.json"

    assert mod.main(["--json", str(out), str(b)]) == 0

    payload = json.loads(out.read_text())
    assert isinstance(payload, list) and len(payload) == 1
    assert payload[0]["resolved"] == 1
    assert payload[0]["board"].endswith("b.kicad_pcb")


# --------------------------------------------------------------------------
# the real boards
# --------------------------------------------------------------------------

WING = ROOT / "tracker/hardware/wing_board/wing_board_v9.kicad_pcb"
HUB = ROOT / "tracker/hardware/hub_board_v9.kicad_pcb"


def test_the_repo_boards_are_censused(mod):
    for board in (WING, HUB):
        if not board.is_file():
            pytest.skip(f"{board} not present")
        r = mod.census(str(board))
        assert r["footprints"] > 0
        assert r["resolved"] + r["unresolved"] == r["model_refs"]


def test_the_wing_generator_emits_only_resolvable_references(mod):
    """Property, not a fingerprint: a generator that points at files it never
    writes leaves the reviewer blind.  (The hub does NOT hold this property yet:
    it has model-less radios U2/U4 -- a separate, carded defect.)"""
    if not WING.is_file():
        pytest.skip("wing board not present")

    r = mod.census(str(WING))

    assert r["unresolved_refs"] == [], r["unresolved_refs"]
    assert r["resolved"] > 0


# --------------------------------------------------------------------------
# can-fail proof
# --------------------------------------------------------------------------

class TestHarnessCanFail:
    """Mutation checks: each test asserts the suite rejects a broken tool.

    Without these, a green run only proves the assertions are self-consistent.
    """

    def test_suite_rejects_a_tool_that_ignores_the_kicad_directory_variable(self, tmp_path, monkeypatch):
        """Mutant: stop expanding ${KICAD<n>_3DMODEL_DIR}."""
        target = Path("/usr/share/kicad/3dmodels")
        if not target.is_dir():
            pytest.skip("3D model package not installed")

        real = next(target.rglob("*.wrl"), None)
        if real is None:
            pytest.skip("no .wrl in package")
        ref = "${KICAD9_3DMODEL_DIR}/" + real.relative_to(target).as_posix()
        board = write_board(tmp_path, "b.kicad_pcb", _fp("U1", [ref]))

        # The un-mutated tool resolves it; the mutant must not.
        assert _load("census_reference_impl", SCRIPT).census(str(board))["unresolved_refs"] == []

        mut = _load("census_mutant_kicadvar", SCRIPT)
        monkeypatch.setattr(mut, "_expand", lambda ref, d: ref.replace("${KIPRJMOD}", d))
        assert mut.census(str(board))["unresolved_refs"] == [ref]

    def test_suite_rejects_a_regex_based_footprint_splitter(self, tmp_path, monkeypatch):
        """Mutant: split footprint blocks with a regex instead of a depth counter.

        This is the defect the block-walking test exists to catch: the split
        truncates at the first nested ')' and the next footprint's models are
        attributed to the previous one.
        """
        import re as _re

        deep = '(pad "1"\n      (at 0 0 0)\n      (net 1 "GND")\n    )'
        b = write_board(
            tmp_path,
            "b.kicad_pcb",
            _fp("U1", ["${KIPRJMOD}/u1.wrl"], inner=deep),
            _fp("U2", ["${KIPRJMOD}/u2.wrl"]),
        )

        good = _load("census_good_splitter", SCRIPT).census(str(b))
        assert good["refs_by_footprint"]["U1"] == ["${KIPRJMOD}/u1.wrl"]
        assert good["refs_by_footprint"]["U2"] == ["${KIPRJMOD}/u2.wrl"]

        mut = _load("census_mutant_splitter", SCRIPT)

        def naive(text):
            # The classic mistake: non-greedy up to the FIRST ')', which sits
            # inside the block, long before the Reference property and models.
            for blk in _re.findall(r"\(footprint.*?\)", text, _re.S):
                yield blk

        monkeypatch.setattr(mut, "_iter_footprint_blocks", naive)
        bad = mut.census(str(b))

        assert bad["refs_by_footprint"] != good["refs_by_footprint"], (
            "the naive splitter produced the same attribution as the depth counter, "
            "so this mutation test proves nothing"
        )
        # The consequence that matters: a model the depth counter sees is lost,
        # i.e. the census would report a populated board as model-less.
        lost = {r for rs in good["refs_by_footprint"].values() for r in rs} - {
            r for rs in bad["refs_by_footprint"].values() for r in rs
        }
        assert lost, bad

    def test_a_tampered_board_makes_the_gate_fail(self, tmp_path):
        """End-to-end negative control: real board, one reference broken."""
        touch_model(tmp_path, "u1.wrl")
        good = write_board(tmp_path, "t.kicad_pcb", _fp("U1", ["${KIPRJMOD}/u1.wrl"]), _fp("U2", ["${KIPRJMOD}/u2.wrl"]))
        m = _load("census_tamper", SCRIPT)
        assert m.main(["--check", str(good)]) == 1

        good.write_text(good.read_text().replace("${KIPRJMOD}/u2.wrl", "${KIPRJMOD}/u1.wrl"))
        assert m.main(["--check", str(good)]) == 0
