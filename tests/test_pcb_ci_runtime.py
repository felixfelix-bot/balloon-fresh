"""Regression coverage for the PCB pipeline's KiCad runtime in CI.

The real defect, measured: the four behavioural board checks in
tests/test_pcb_pipeline_gates.py SKIPPED on a runner without the distro KiCad
bindings, so the job went GREEN while the pipeline's only end-to-end evidence
was a no-op. (On the PR that introduced the pinned interpreter the same four
checks went red instead, with ModuleNotFoundError: pcbnew from a hardcoded
/usr/bin/python3.14 -- a runner HAS that interpreter but its site-packages carry
no pcbnew. Both outcomes are the same root cause seen from two sides: existence
is not capability, and a skip is not a pass.)

The repair is deliberately narrow:
  * a dedicated CI job that installs KiCad and runs the pipeline suite, so the
    board checks execute for real;
  * the distro interpreter, which is the one that owns the binding;
  * scripts/assert_board_checks_ran.py, which refuses a green tick unless all
    four checks are present AND passed.

Equally important: KiCad must NOT be installed job-wide for the general suites.
The v10 board gates have their own pre-existing board/registry drift, and they
loud-skip without pcbnew; making pcbnew available there would convert unrelated
baseline findings into failures of every PR.

NOTE: PyYAML is imported directly, not with pytest.importorskip. This file exists
to stop a skip being read as a pass, so it must not skip itself.
"""
import importlib.util
import re
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
HOST_TESTS = ROOT / ".github/workflows/ci-host-tests.yml"
GENERAL_TESTS = ROOT / ".github/workflows/test.yml"
SUITE = "tests/test_pcb_pipeline_gates.py"


def _load_pipeline_gates():
    spec = importlib.util.spec_from_file_location(
        "pipeline_gates", ROOT / SUITE
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pipeline_runs_under_the_distro_interpreter(monkeypatch, tmp_path):
    """pcbnew ships for /usr/bin/python3; a pinned minor version may not have it."""
    module = _load_pipeline_gates()
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs: calls.append(args))
    module._run_pipeline("v1-fast", tmp_path / "board.kicad_pcb")
    assert calls[0][0] == "/usr/bin/python3"


def _jobs(text):
    """Split a workflow into {job_name: body} for the `jobs:` mapping."""
    jobs = {}
    current = None
    for line in text.splitlines():
        match = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if match:
            current = match.group(1)
            jobs[current] = []
        elif current:
            jobs[current].append(line)
    return {name: "\n".join(body) for name, body in jobs.items()}


def test_a_dedicated_job_installs_kicad_and_runs_the_pipeline_suite():
    """The four board checks need a job where pcbnew actually resolves."""
    jobs = _jobs(HOST_TESTS.read_text())
    good = [name for name, body in jobs.items() if SUITE in body]
    assert good, "no ci-host-tests job runs the PCB pipeline suite"
    for name in good:
        body = jobs[name]
        assert "--no-install-recommends kicad" in body, (
            f"{name}: the pipeline suite runs without installing KiCad -- "
            "the board checks would fail on a missing module, not on the board"
        )
        assert body.index("kicad") < body.index(SUITE), (
            f"{name}: KiCad must be installed before the suite runs"
        )


def test_general_suite_never_runs_the_pipeline_suite_without_kicad():
    """Running it in a KiCad-less job is the defect this file guards."""
    body = _jobs(GENERAL_TESTS.read_text())["test"]
    if re.search(r"pytest\s+tests/?\s", body):
        assert f"--ignore={SUITE}" in body, (
            "test.yml collects tests/ (which includes the pipeline suite) "
            "without KiCad; ignore that file here so the dedicated job owns it"
        )


@pytest.mark.parametrize("workflow", [HOST_TESTS, GENERAL_TESTS])
def test_workflows_are_parseable_yaml(workflow):
    yaml.safe_load(workflow.read_text())


def _run_blocks(workflow: Path) -> dict[str, str]:
    """{job/step label: shell script} for every `run:` in a workflow."""
    doc = yaml.safe_load(workflow.read_text())
    blocks = {}
    for job_name, job in (doc.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            if "run" in step:
                blocks[f"{job_name}/{step.get('name', '')}"] = step["run"]
    return blocks


@pytest.mark.parametrize("workflow", [HOST_TESTS, GENERAL_TESTS])
def test_run_blocks_are_valid_shell(workflow):
    """A step whose shell does not parse fails the job for the wrong reason."""
    for label, script in _run_blocks(workflow).items():
        proc = subprocess.run(["bash", "-n"], input=script, capture_output=True, text=True)
        assert proc.returncode == 0, f"{workflow.name}:{label} is not valid shell: {proc.stderr}"


@pytest.mark.parametrize("workflow", [HOST_TESTS, GENERAL_TESTS])
def test_no_doubled_backslash_line_continuations(workflow):
    r"""A doubled backslash in a run block is passed to the shell literally.

    Measured on PR #394's first run: a doubled continuation made pip receive `\`
    as a requirement ("Invalid requirement: '\\\\'") and the job failed before any
    test ran -- a CI defect that looks like a product defect.
    """
    for label, script in _run_blocks(workflow).items():
        for line in script.splitlines():
            assert not line.rstrip().endswith("\\\\"), (
                f"{workflow.name}:{label}: doubled backslash continuation: {line!r}"
            )


def test_the_pipeline_step_invokes_pytest_under_the_distro_python():
    """The dedicated job must not fall back to a pcbnew-less interpreter."""
    label, script = next(
        (k, v) for k, v in _run_blocks(HOST_TESTS).items() if SUITE in v
    )
    pytest_lines = [ln for ln in script.splitlines() if "-m pytest" in ln]
    assert pytest_lines, f"{label}: no pytest invocation"
    for line in pytest_lines:
        assert line.strip().startswith("/usr/bin/python3"), (
            f"{label}: pipeline suite invoked with a non-distro interpreter: {line!r}"
        )
