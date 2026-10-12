#!/usr/bin/env python3
"""param_ssot_check.py — FAIL-CLOSED gate on the single-source-of-truth parameter registry.

WHAT THIS GUARDS
================
This repo has repeatedly carried **two records asserting DIFFERENT values for the
same physical parameter, with nothing surfacing the disagreement** — four cases
found in a single day (2026-10-07):

  * hub outline     22 x 22 mm stale prose   vs  the generated v9 hub board 103 x 103 mm
  * ESP32-S3 flash  16 MB claim              vs  the fitted -N8R8 part's 8 MB
  * 2.4 GHz RX      "RX on the F33"          vs  the bare LoRa2021 (ADR-034)
  * wing plane      "wings 1-2 horizontal"   vs  the ADR-049 VERTICAL blade
  * F33 land size   2.0 x 1.0 mm guess       vs  1.30 x 1.30 mm (D + 2 x 0.25)

`docs/ssot/parameters.json` is the ONE machine-readable list of contested
parameters: for each parameter it names the **single record that OWNS** it, the
canonical value, an anchor that proves the owner still asserts that value, the
records that historically asserted something else, and a regex for the
conflicting value.  This script enforces the registry mechanically.

HOW IT DECIDES
==============
For every parameter entry it:

  1. verifies every `anchors[]` location still asserts the canonical value
     (no anchor match -> FAIL: the owner record no longer asserts it);
  2. expands the entry's `scan[]` file set (the owner plus the records that
     speak to the parameter) and, for each scanned file, looks for the entry's
     `forbid[]` regexes;
  3. a match is a **VIOLATION** unless the *matched line* carries a line-level
     annotation (``was``, ``stale``, ``superseded``, ``TODO(unverified)``,
     ``was``/``->``/``before`` …) or the *file* carries a file-level
     annotation — the repo's appended ``CORRECTION`` block convention, a
     citation of ``docs/ssot/parameters.json``, or a statement that the value
     is ``inherited``/``RESOLVED``.  Annotated mentions are the history that
     keeps a record legible; an UN-annotated conflicting assertion is the
     defect this gate exists to catch.

FAIL-CLOSED
===========
Anything the script cannot establish is non-zero, never a pass:

  * a registry that cannot be read/parsed, or is malformed (missing owner,
    canonical, anchors, forbid, or an un-reasoned `exempt` entry) -> exit 2;
  * a scanned file that cannot be read/decoded -> exit 2;
  * a `scan[]` entry that matches NO file -> exit 2 (the evidence is missing,
    so nothing was actually checked);
  * a detected conflicting assertion -> exit 1.

Exit 1 and exit 2 are distinguished so a caller can tell "a record contradicts
the registry" (the design record is wrong) from "the checker cannot see the
answer" (the checker/inputs are wrong).  Both are failures.

Usage
-----
    python3 scripts/param_ssot_check.py                     # whole repo
    python3 scripts/param_ssot_check.py --list              # show the registry
    python3 scripts/param_ssot_check.py --json              # machine-readable
    python3 scripts/param_ssot_check.py --root /tmp/copy    # check another tree
    python3 scripts/param_ssot_check.py --registry other.json

Owner of the registry: docs/ssot/parameters.json.  Add an entry there the
moment a second record is found asserting a different value for a parameter.
"""

from __future__ import annotations

import argparse
import glob as globlib
import json
import re
import sys
from pathlib import Path

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_UNDETERMINED = 2

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPO_ROOT / "docs" / "ssot" / "parameters.json"


# --------------------------------------------------------------------------- #
# registry validation — a malformed registry is UNDETERMINED, never a pass
# --------------------------------------------------------------------------- #

def load_registry(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit2("registry unreadable: %s (%s)" % (path, exc))
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit2("registry is not valid JSON: %s (%s)" % (path, exc))
    if not isinstance(data, dict) or "parameters" not in data:
        raise SystemExit2("registry has no `parameters` list: %s" % path)
    return data


class SystemExit2(Exception):
    """A fail-closed UNDETERMINED condition (exit 2)."""


def validate_registry(data: dict, root: Path) -> list[str]:
    """Structural validation.  Returns a list of problems (empty == ok)."""
    problems: list[str] = []
    params = data.get("parameters")
    if not isinstance(params, list) or not params:
        return ["`parameters` must be a non-empty list"]
    seen: set[str] = set()
    for i, entry in enumerate(params):
        where = "parameters[%d]" % i
        if not isinstance(entry, dict):
            problems.append("%s is not an object" % where)
            continue
        pid = entry.get("id")
        if not pid or not isinstance(pid, str):
            problems.append("%s has no `id`" % where)
            pid = where
        else:
            if pid in seen:
                problems.append("duplicate parameter id %r" % pid)
            seen.add(pid)
            where = "parameter %r" % pid
        for key in ("name", "owner", "canonical"):
            if not entry.get(key) or not isinstance(entry[key], str):
                problems.append("%s has no `%s` string" % (where, key))
        anchors = entry.get("anchors")
        if not isinstance(anchors, list) or not anchors:
            problems.append("%s has no non-empty `anchors` list" % where)
        else:
            for a in anchors:
                if not isinstance(a, dict) or not a.get("file") or not a.get("regex"):
                    problems.append("%s has a malformed anchor (needs file+regex)" % where)
                else:
                    try:
                        re.compile(a["regex"])
                    except re.error as exc:
                        problems.append("%s anchor regex does not compile: %s" % (where, exc))
        forbid = entry.get("forbid")
        if not isinstance(forbid, list) or not forbid:
            problems.append("%s has no non-empty `forbid` list" % where)
        else:
            for f in forbid:
                if not isinstance(f, dict) or not f.get("id") or not f.get("regex"):
                    problems.append("%s has a malformed forbid rule (needs id+regex)" % where)
                else:
                    try:
                        re.compile(f["regex"])
                    except re.error as exc:
                        problems.append("%s forbid regex does not compile: %s" % (where, exc))
        scan = entry.get("scan")
        if not isinstance(scan, list) or not scan:
            problems.append("%s has no non-empty `scan` list" % where)
        exempts = entry.get("exempt", [])
        if not isinstance(exempts, list):
            problems.append("%s `exempt` must be a list" % where)
        else:
            for e in exempts:
                if not isinstance(e, dict) or not e.get("glob"):
                    problems.append("%s has an exempt entry with no `glob`" % where)
                elif not e.get("reason"):
                    problems.append(
                        "%s exempt %r has NO reason — an exemption must be justified"
                        % (where, e.get("glob")))
    # the registry's global annotation vocabularies must exist and compile
    for key in ("line_markers", "file_markers"):
        val = data.get(key)
        if not isinstance(val, list) or not val:
            problems.append("registry has no `%s` list" % key)
            continue
        for pat in val:
            try:
                re.compile(pat)
            except re.error as exc:
                problems.append("registry %s %r does not compile: %s" % (key, pat, exc))
    return problems


# --------------------------------------------------------------------------- #
# scanning
# --------------------------------------------------------------------------- #

def expand_scan(root: Path, patterns: list[str]) -> tuple[list[Path], list[str]]:
    """Expand scan globs to existing files.  Returns (files, missing_patterns)."""
    files: list[Path] = []
    missing: list[str] = []
    for pat in patterns:
        if any(ch in pat for ch in "*?["):
            hits = sorted(p for p in root.glob(pat) if p.is_file())
        else:
            p = root / pat
            hits = [p] if p.is_file() else []
        if not hits:
            missing.append(pat)
        files.extend(hits)
    # de-dup, keep order
    out: list[Path] = []
    seen: set[Path] = set()
    for f in files:
        rp = f.resolve()
        if rp not in seen:
            seen.add(rp)
            out.append(f)
    return out, missing


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def check(root: Path, registry: dict) -> dict:
    """Run the whole gate.  Returns a report dict; never raises for content."""
    line_markers = registry["line_markers"]
    file_markers = registry["file_markers"]
    file_markers_re = re.compile("|".join("(?:%s)" % m for m in file_markers),
                                 re.IGNORECASE)
    line_markers_re = re.compile("|".join("(?:%s)" % m for m in line_markers),
                                 re.IGNORECASE)

    report = {"verdict": "PASS", "exit_code": EXIT_PASS,
              "failures": [], "undetermined": [], "checks": [], "parameters": []}

    for entry in registry["parameters"]:
        pid = entry["id"]
        per = {"id": pid, "owner": entry["owner"], "canonical": entry["canonical"],
               "anchors_ok": [], "scanned": [], "violations": []}

        # --- 1. anchors: the owner (and any co-authoritative file) must still
        #        assert the canonical value.
        for a in entry["anchors"]:
            apath = root / a["file"]
            atext = read_text(apath)
            if atext is None:
                msg = ("[%s] anchor file unreadable: %s — the owner record cannot "
                       "be verified" % (pid, a["file"]))
                report["undetermined"].append(msg)
                per["anchors_ok"].append({"file": a["file"], "ok": False})
                continue
            ok = re.search(a["regex"], atext, re.IGNORECASE) is not None
            per["anchors_ok"].append({"file": a["file"], "ok": ok})
            if ok:
                report["checks"].append(
                    "[%s] anchor ok: %s asserts %r" % (pid, a["file"], a["regex"]))
            else:
                report["failures"].append(
                    "[%s] ANCHOR LOST: %s no longer matches /%s/ — the owner record "
                    "does not assert the canonical value %r"
                    % (pid, a["file"], a["regex"], entry["canonical"]))

        # --- 2. the declared exclusions (each already carries a mandatory reason)
        exempt_globs = [e["glob"] for e in entry.get("exempt", [])]
        exempt_resolved: set[Path] = set()
        for g in exempt_globs:
            for p in (root.glob(g) if any(c in g for c in "*?[") else [root / g]):
                if p.is_file():
                    exempt_resolved.add(p.resolve())

        # --- 3. expand the scan set
        files, missing = expand_scan(root, entry["scan"])
        for m in missing:
            report["undetermined"].append(
                "[%s] scan pattern matched NO file: %r — nothing was checked for "
                "this pattern (fail-closed)" % (pid, m))
        if not files:
            report["undetermined"].append(
                "[%s] the entire scan set is empty — no evidence was examined" % pid)
        per["scanned"] = [str(f.relative_to(root)) if f.is_relative_to(root) else str(f)
                          for f in files]

        for f in files:
            rel = str(f.relative_to(root)) if f.is_relative_to(root) else str(f)
            text = read_text(f)
            if text is None:
                report["undetermined"].append(
                    "[%s] scanned file unreadable/undecodable: %s (fail-closed)" % (pid, rel))
                continue
            if f.resolve() in exempt_resolved:
                report["checks"].append("[%s] exempt (reasoned): %s" % (pid, rel))
                continue
            file_annotated = file_markers_re.search(text) is not None
            lines = text.splitlines()
            for rule in entry["forbid"]:
                for m in re.finditer(rule["regex"], text, re.IGNORECASE):
                    ln = line_of(text, m.start())
                    line_text = lines[ln - 1] if 0 <= ln - 1 < len(lines) else ""
                    annotated = file_annotated or (line_markers_re.search(line_text) is not None)
                    if annotated:
                        continue
                    viol = {
                        "parameter": pid, "file": rel, "line": ln, "rule": rule["id"],
                        "match": m.group(0)[:120], "note": rule.get("note", ""),
                    }
                    per["violations"].append(viol)
                    report["failures"].append(
                        "[%s] CONFLICT %s:%d matches %s (%r) but is NOT annotated as a "
                        "correction. Owner: %s. Canonical: %s"
                        % (pid, rel, ln, rule["id"], m.group(0)[:40],
                           entry["owner"], entry["canonical"]))

        # de-dup failure strings per parameter (same rule may fire twice on one line)
        report["parameters"].append(per)

    # de-dup failures while keeping order
    seen: set[str] = set()
    deduped: list[str] = []
    for f in report["failures"]:
        if f not in seen:
            seen.add(f)
            deduped.append(f)
    report["failures"] = deduped

    if report["undetermined"]:
        report["verdict"] = "UNDETERMINED"
        report["exit_code"] = EXIT_UNDETERMINED
    if report["failures"]:
        # a real conflict is the louder signal: report FAIL for it
        report["verdict"] = "FAIL"
        report["exit_code"] = EXIT_FAIL
    return report


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(REPO_ROOT),
                    help="tree to check (default: this repo)")
    ap.add_argument("--registry", default=str(DEFAULT_REGISTRY),
                    help="registry JSON (default: docs/ssot/parameters.json)")
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    ap.add_argument("--list", action="store_true", help="print the registry and exit")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    reg_path = Path(args.registry)
    if not reg_path.is_absolute():
        reg_path = root / reg_path

    try:
        data = load_registry(reg_path)
        problems = validate_registry(data, root)
    except SystemExit2 as exc:
        rep = {"verdict": "UNDETERMINED", "exit_code": EXIT_UNDETERMINED,
               "failures": [], "undetermined": [str(exc)], "checks": [], "parameters": []}
        _emit(rep, args)
        return EXIT_UNDETERMINED
    if problems:
        rep = {"verdict": "UNDETERMINED", "exit_code": EXIT_UNDETERMINED,
               "failures": [], "undetermined": ["malformed registry: " + p for p in problems],
               "checks": [], "parameters": []}
        _emit(rep, args)
        return EXIT_UNDETERMINED

    if args.list:
        for e in data["parameters"]:
            print("%-26s owner=%s" % (e["id"], e["owner"]))
            print("    canonical: %s" % e["canonical"])
        return EXIT_PASS

    rep = check(root, data)
    _emit(rep, args)
    return rep["exit_code"]


def _emit(rep: dict, args) -> None:
    if args.json:
        print(json.dumps(rep, indent=2))
        return
    if args.quiet:
        if rep["exit_code"] != EXIT_PASS:
            for m in rep["undetermined"] + rep["failures"]:
                print(m)
        return
    print("param_ssot_check — registry: docs/ssot/parameters.json")
    for c in rep["checks"]:
        print("  ok   %s" % c)
    for u in rep["undetermined"]:
        print("  ??   %s" % u)
    for f in rep["failures"]:
        print("  FAIL %s" % f)
    print("VERDICT: %s (exit %d)" % (rep["verdict"], rep["exit_code"]))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
