#!/usr/bin/env python3
"""Fail closed unless the four PCB pipeline board checks actually RAN and passed.

WHY THIS EXISTS
    The four behavioural checks in ``tests/test_pcb_pipeline_gates.py`` build a
    real board with pcbnew. When the binding is absent they SKIP, so CI reports a
    green tick while the pipeline's only end-to-end evidence is a no-op. That is
    exactly what happened on master before the ``pcb-pipeline`` job existed: the
    job was green and four board checks were skipped. A skip is a missing check,
    not a pass.

    This reads the JUnit XML that the CI job writes and exits non-zero if any of
    the required cases is absent, skipped, errored or failed. It deliberately does
    NOT care how the job invoked pytest: ``-k``, ``--deselect``, a stray skip
    marker, or an early exit all show up as "absent" or "skipped" here.

WHAT IT CANNOT SEE, AND THE GUARD FOR IT
    A non-strict ``xfail`` that unexpectedly passes emits a bare ``<testcase>``,
    which is indistinguishable from a genuine pass. The invocation therefore runs
    with ``-o xfail_strict=true`` (also pinned in pyproject), which turns an xpass
    into a ``<failure>`` that this script refuses. Do not "fix" an xpass by
    removing that flag.

Usage:
    python3 scripts/assert_board_checks_ran.py <junit.xml> [--require NAME ...]

    ``--require`` EXTENDS the built-in four checks; it never replaces them.
"""
from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET

# The module that must contain the checks. Keying on the name alone would let a
# same-named testcase in any other file satisfy the gate.
SUITE_CLASS = "tests.test_pcb_pipeline_gates"

REQUIRED = (
    "test_pipeline_creates_board_headless[v1-fast-15-17]",
    "test_pipeline_creates_board_headless[v2-adc-17-18]",
    "test_v2_adc_board_has_vdiv_mid_net",
    "test_board_outline_is_50x40mm",
)


def required_for(extra: list[str] | None = None) -> tuple[str, ...]:
    """The four board checks plus any extra names. Extras never replace them."""
    return REQUIRED + tuple(n for n in (extra or []) if n not in REQUIRED)


def outcomes(xml_path: str) -> dict[str, str]:
    """Map "classname::name" -> passed | failed | skipped."""
    root = ET.parse(xml_path).getroot()
    result: dict[str, str] = {}
    for case in root.iter("testcase"):
        key = f"{case.get('classname') or ''}::{case.get('name') or ''}"
        if case.find("skipped") is not None:
            state = "skipped"
        elif case.find("failure") is not None or case.find("error") is not None:
            state = "failed"
        else:
            state = "passed"
        # A test appears once; if a rerun duplicated it, a non-pass must win.
        if key not in result or (result[key] == "passed" and state != "passed"):
            result[key] = state
    return result


def check(xml_path: str, required=REQUIRED, suite_class: str = SUITE_CLASS) -> dict[str, str]:
    """Return {name: state} for every required case that is not a pass."""
    seen = outcomes(xml_path)
    bad: dict[str, str] = {}
    for name in required:
        state = seen.get(f"{suite_class}::{name}", "absent")
        if state != "passed":
            bad[name] = state
    return bad


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("junit_xml")
    parser.add_argument("--require", action="append", default=None,
                        help="extra testcase name that must have passed "
                             "(extends the built-in four; does not replace them)")
    args = parser.parse_args(argv)

    required = required_for(args.require)
    try:
        bad = check(args.junit_xml, required)
    except (OSError, ET.ParseError) as exc:
        print(f"REFUSING: cannot read a JUnit report at {args.junit_xml}: {exc}",
              file=sys.stderr)
        return 2
    if bad:
        for name, state in bad.items():
            print(f"NOT RUN: {state:<8} {name}", file=sys.stderr)
        print("REFUSING: the board checks did not execute for real. A skip is not a pass.",
              file=sys.stderr)
        return 1
    print(f"{len(required)}/{len(required)} board checks ran and passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
