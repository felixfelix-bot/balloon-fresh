"""Hardening for the fail-closed board-check gate.

WHY: `scripts/assert_board_checks_ran.py` exists to refuse a green tick when the
four board checks did not really run. A gate with that job must not itself have a
way to read "not run" as "passed". A cold review found three:

  * ``--require`` REPLACED the built-in list, so one flag in CI would silently
    drop the other three checks;
  * outcomes were keyed on the testcase NAME alone, so a same-named case in a
    different class satisfied the requirement;
  * a non-strict ``xfail`` that unexpectedly passes emits a bare ``<testcase>``,
    which is indistinguishable from a genuine pass.

Also fixed here: the guards below shipped with ``pytest.importorskip("yaml")``,
which is a SKIP -- i.e. a silent green -- in the very file whose subject is that
a skip is not a pass.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "assert_board_checks_ran.py"
PIPELINE_CLASS = "tests.test_pcb_pipeline_gates"
REQUIRED = (
    "test_pipeline_creates_board_headless[v1-fast-15-17]",
    "test_pipeline_creates_board_headless[v2-adc-17-18]",
    "test_v2_adc_board_has_vdiv_mid_net",
    "test_board_outline_is_50x40mm",
)


def _load():
    spec = importlib.util.spec_from_file_location("assert_board_checks_ran", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _case(name: str, state: str, classname: str = PIPELINE_CLASS) -> str:
    body = {
        "passed": "",
        "failed": '<failure message="boom"/>',
        "error": '<error message="boom"/>',
        "skipped": '<skipped message="no pcbnew"/>',
        # A non-strict xfail that XPASSED: pytest emits a bare testcase.
        "bare": None,
    }[state]
    if body is None:
        return f'<testcase classname="{classname}" name="{name}" time="0.001" />'
    return f'<testcase classname="{classname}" name="{name}">{body}</testcase>'


def _xml(path: Path, cases) -> Path:
    """cases: dict[str,str] | list[(name, state, classname)]."""
    if isinstance(cases, dict):
        cases = [(n, s, PIPELINE_CLASS) for n, s in cases.items()]
    path.write_text(
        '<?xml version="1.0"?><testsuites><testsuite name="pytest">'
        + "".join(_case(n, s, c) for n, s, c in cases)
        + "</testsuite></testsuites>"
    )
    return path


def test_accepts_a_report_where_all_four_passed(tmp_path):
    module = _load()
    xml = _xml(tmp_path / "ok.xml", {name: "passed" for name in REQUIRED})
    assert module.check(str(xml)) == {}
    assert module.main([str(xml)]) == 0


@pytest.mark.parametrize("state", ["skipped", "failed", "error"])
def test_refuses_when_a_required_check_did_not_pass(tmp_path, state):
    module = _load()
    cases = {name: "passed" for name in REQUIRED}
    cases[REQUIRED[2]] = state
    xml = _xml(tmp_path / f"{state}.xml", cases)
    assert module.check(str(xml)) == {REQUIRED[2]: state if state != "error" else "failed"}
    assert module.main([str(xml)]) == 1


def test_refuses_when_a_required_check_is_absent(tmp_path):
    """`-k`, `--deselect` or an early exit must not read as success."""
    module = _load()
    cases = {name: "passed" for name in REQUIRED[:-1]}
    xml = _xml(tmp_path / "absent.xml", cases)
    assert module.check(str(xml)) == {REQUIRED[-1]: "absent"}
    assert module.main([str(xml)]) == 1


def test_refuses_an_unreadable_or_missing_report(tmp_path):
    module = _load()
    assert module.main([str(tmp_path / "nope.xml")]) == 2
    broken = tmp_path / "broken.xml"
    broken.write_text("<testsuite><testcase>")
    assert module.main([str(broken)]) == 2


def test_reports_every_offending_check_not_just_the_first(tmp_path, capsys):
    module = _load()
    cases = {name: "passed" for name in REQUIRED}
    cases[REQUIRED[0]] = "skipped"
    cases[REQUIRED[3]] = "failed"
    xml = _xml(tmp_path / "multi.xml", cases)
    assert module.main([str(xml)]) == 1
    err = capsys.readouterr().err
    assert REQUIRED[0] in err and REQUIRED[3] in err


def test_runs_as_a_script_like_ci_invokes_it(tmp_path):
    xml = _xml(tmp_path / "cli.xml", {name: "passed" for name in REQUIRED})
    proc = subprocess.run([sys.executable, str(SCRIPT), str(xml)],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "4/4 board checks ran and passed" in proc.stdout


# ---------------------------------------------------------------------------
# HARDENING: ways the gate could read "not run" as "passed"
# ---------------------------------------------------------------------------

def test_require_extends_the_default_set_instead_of_replacing_it(tmp_path):
    """One `--require` in CI must not quietly drop the other three checks."""
    module = _load()
    extra = "test_some_extra_check"

    # Sanity: default four + a passing extra is accepted.
    allpass = {name: "passed" for name in REQUIRED}
    allpass[extra] = "passed"
    assert module.main([str(_xml(tmp_path / "all.xml", allpass)), "--require", extra]) == 0

    # The catch: extra passes, but a DEFAULT check was skipped. If --require
    # replaced the defaults, this would be a green tick.
    cases = {name: "passed" for name in REQUIRED}
    cases[REQUIRED[1]] = "skipped"
    cases[extra] = "passed"
    xml = _xml(tmp_path / "replaced.xml", cases)
    assert module.main([str(xml), "--require", extra]) == 1
    assert module.check(str(xml), module.required_for([extra])) == {REQUIRED[1]: "skipped"}


def test_a_same_named_testcase_in_another_module_does_not_count(tmp_path):
    """Outcomes must be keyed by class too, or any file can satisfy the gate."""
    module = _load()
    cases = [(name, "passed", "tests.test_unrelated") for name in REQUIRED]
    xml = _xml(tmp_path / "wrongclass.xml", cases)
    bad = module.check(str(xml))
    assert set(bad) == set(REQUIRED), bad
    assert module.main([str(xml)]) == 1


def test_a_bare_testcase_from_an_xpass_is_not_accepted_as_a_pass(tmp_path):
    """An xpass emits a bare <testcase>; without xf_strict that reads as green.

    The script cannot tell a bare pass from an xpass, so the invocation must run
    with xfail_strict, which turns a non-strict xpass into a <failure>. This test
    pins that the repository actually sets it.
    """
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert "xfail_strict" in pyproject, (
        "pyproject must set xfail_strict so an xpass cannot masquerade as a pass"
    )
    assert "true" in pyproject.split("xfail_strict", 1)[1][:20].lower()


def test_the_ci_invocation_pins_xfail_strict(tmp_path):
    """Belt and braces: the pcb-pipeline step itself must not rely on defaults."""
    workflow = (ROOT / ".github/workflows/ci-host-tests.yml").read_text()
    assert "xfail_strict" in workflow, (
        "the pcb-pipeline invocation must pass -o xfail_strict=true"
    )
