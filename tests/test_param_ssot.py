#!/usr/bin/env python3
"""tests for `scripts/param_ssot_check.py` — the single-source-of-truth gate.

The gate is FAIL-CLOSED: it exits 0 only when it has *proved* that no scanned
record asserts a value conflicting with the registry owner without annotating it
as a correction.  Everything else is non-zero.  These tests do four things:

  1. prove the gate PASSES a deliberately-clean fixture (so it is not a no-op
     that always fails, which would be equally useless);
  2. prove the gate FAILS when a PLANTED CONTRADICTION is introduced — the
     required mutation test is `test_planted_contradiction_fails`, which asserts
     the real exit code and that the offending file:line is named;
  3. prove annotated history does NOT trip it (a line-level marker, or a
     file-level appended CORRECTION block);
  4. prove the gate never silent-passes: an unreadable scanned file, a scan
     pattern matching nothing, a lost owner anchor and a malformed registry all
     return non-zero.

Fixtures are built in `tmp_path` as a real mini-tree plus a real fixture
registry, then the checker is invoked through `subprocess` so its REAL exit code
is what is asserted.  The last test runs the checker against the real repository.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CHECKER = REPO / "scripts" / "param_ssot_check.py"
REAL_REGISTRY = REPO / "docs" / "ssot" / "parameters.json"

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_UNDETERMINED = 2

# The five parameters the registry must carry (the four instances found on
# 2026-10-07 plus the F33 land size that changed the same day).
EXPECTED_PARAMETERS = {
    "esp32s3_flash_size",
    "v9_2g4_rx_radio",
    "wing_plane_orientation",
    "hub_outline",
    "f33_castellation_land_size",
}


# --------------------------------------------------------------------------- #
# fixture builders
# --------------------------------------------------------------------------- #

def fixture_registry(scan=None, anchor_file="docs/good.md", anchor_regex="42 mm",
                     exempt=None, forbid=None) -> dict:
    return {
        "_fixture": True,
        "line_markers": [r"\bwas\b", r"\bnot\b", r"TODO\(unverified\)", r"→|->",
                         r"\bstale\b", r"\bsupersed"],
        "file_markers": ["CORRECTION", "docs/ssot/parameters.json"],
        "parameters": [{
            "id": "fixture_param",
            "name": "Fixture parameter",
            "owner": "docs/good.md",
            "canonical": "42 mm",
            "anchors": [{"file": anchor_file, "regex": anchor_regex}],
            "who_else_asserted": "docs/bad.md historically asserted 22 x 22",
            "scan": scan if scan is not None else ["docs/good.md", "docs/bad.md"],
            "exempt": exempt or [],
            "forbid": forbid or [{"id": "BADVAL", "regex": r"22\s*[x×]\s*22",
                                  "note": "fixture conflict"}],
        }],
    }


def build_tree(tmp_path: Path, good="The value is 42 mm.\n", bad="The value is 42 mm.\n",
               registry: dict | None = None, bad_bytes: bytes | None = None) -> tuple[Path, Path]:
    root = tmp_path / "root"
    (root / "docs" / "ssot").mkdir(parents=True)
    (root / "docs" / "good.md").write_text(good, encoding="utf-8")
    if bad_bytes is not None:
        (root / "docs" / "bad.md").write_bytes(bad_bytes)
    else:
        (root / "docs" / "bad.md").write_text(bad, encoding="utf-8")
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps(registry if registry is not None else fixture_registry(),
                              indent=2), encoding="utf-8")
    return root, reg


def run_checker(root: Path, reg: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CHECKER), "--root", str(root),
                           "--registry", str(reg), *args],
                          capture_output=True, text=True, cwd=str(REPO))


# --------------------------------------------------------------------------- #
# 1. the gate must PASS a clean fixture (it is not a no-op)
# --------------------------------------------------------------------------- #

def test_clean_fixture_passes(tmp_path):
    root, reg = build_tree(tmp_path)
    r = run_checker(root, reg)
    assert r.returncode == EXIT_PASS, r.stdout + r.stderr
    assert "VERDICT: PASS" in r.stdout


def test_annotated_line_mention_passes(tmp_path):
    """A conflicting value marked as history on the same line is NOT a failure."""
    root, reg = build_tree(tmp_path, bad="The old figure was 22 x 22 mm.\n")
    r = run_checker(root, reg)
    assert r.returncode == EXIT_PASS, r.stdout + r.stderr


def test_file_level_correction_block_passes(tmp_path):
    """A file carrying an appended CORRECTION block annotates its own history."""
    bad = ("The hub is 22 x 22 mm.\n\n"
           "> **CORRECTION** — that figure is superseded; see ADR-049.\n")
    root, reg = build_tree(tmp_path, bad=bad)
    r = run_checker(root, reg)
    assert r.returncode == EXIT_PASS, r.stdout + r.stderr


# --------------------------------------------------------------------------- #
# 2. THE MUTATION TEST — a planted contradiction must FAIL, naming file:line
# --------------------------------------------------------------------------- #

def test_planted_contradiction_fails(tmp_path):
    """REQUIRED MUTATION: docs/bad.md asserts 22 x 22 mm, un-annotated.

    This is exactly the class of defect the registry exists to catch (a second
    record asserting a different value for the same parameter, with nothing
    surfacing it).  The gate MUST return exit 1 and name the file and line.
    """
    root, reg = build_tree(tmp_path, bad="The hub is 22 x 22 mm.\n")
    r = run_checker(root, reg)
    assert r.returncode == EXIT_FAIL, (
        "the gate MUST fail on a planted, un-annotated contradiction: "
        + r.stdout + r.stderr)
    assert "docs/bad.md:1" in r.stdout
    assert "BADVAL" in r.stdout


def test_json_report_names_the_violation(tmp_path):
    root, reg = build_tree(tmp_path, bad="x\nThe hub is 22 x 22 mm.\n")
    r = run_checker(root, reg, "--json")
    assert r.returncode == EXIT_FAIL, r.stdout + r.stderr
    data = json.loads(r.stdout)
    assert data["verdict"] == "FAIL"
    assert data["exit_code"] == EXIT_FAIL
    viol = [v for p in data["parameters"] for v in p["violations"]]
    assert viol and viol[0]["file"] == "docs/bad.md" and viol[0]["line"] == 2


# --------------------------------------------------------------------------- #
# 3. the gate must NEVER silent-pass
# --------------------------------------------------------------------------- #

def test_lost_owner_anchor_fails(tmp_path):
    """The owner record no longer asserts the canonical value -> FAIL."""
    root, reg = build_tree(tmp_path, good="The value is unknown.\n")
    r = run_checker(root, reg)
    assert r.returncode == EXIT_FAIL, r.stdout + r.stderr
    assert "ANCHOR LOST" in r.stdout


def test_unreadable_scanned_file_is_undetermined(tmp_path):
    """A scanned file that cannot be decoded must FAIL (never PASS)."""
    root, reg = build_tree(tmp_path, bad_bytes=b"\xff\xfe\x00 this is not utf-8 \xff\n")
    r = run_checker(root, reg)
    assert r.returncode == EXIT_UNDETERMINED, r.stdout + r.stderr
    assert r.returncode != EXIT_PASS


def test_scan_pattern_matching_nothing_is_undetermined(tmp_path):
    root, reg = build_tree(tmp_path, registry=fixture_registry(
        scan=["docs/good.md", "docs/does-not-exist.md"]))
    r = run_checker(root, reg)
    assert r.returncode == EXIT_UNDETERMINED, r.stdout + r.stderr
    assert "matched NO file" in r.stdout


def test_missing_registry_is_undetermined(tmp_path):
    root, _ = build_tree(tmp_path)
    r = run_checker(root, tmp_path / "nope.json")
    assert r.returncode == EXIT_UNDETERMINED, r.stdout + r.stderr


def test_malformed_registry_is_undetermined(tmp_path):
    reg = fixture_registry()
    del reg["parameters"][0]["forbid"]          # registry no longer says what to forbid
    root, regp = build_tree(tmp_path, registry=reg)
    r = run_checker(root, regp)
    assert r.returncode == EXIT_UNDETERMINED, r.stdout + r.stderr
    assert "no non-empty `forbid`" in r.stdout


def test_unreasoned_exemption_is_undetermined(tmp_path):
    """An exemption with no stated reason must not be honoured (fail-closed)."""
    reg = fixture_registry(exempt=[{"glob": "docs/bad.md"}])   # no `reason`
    root, regp = build_tree(tmp_path, bad="The hub is 22 x 22 mm.\n", registry=reg)
    r = run_checker(root, regp)
    assert r.returncode == EXIT_UNDETERMINED, r.stdout + r.stderr
    assert "NO reason" in r.stdout


# --------------------------------------------------------------------------- #
# 4. the real repository, and the registry's own contents
# --------------------------------------------------------------------------- #

def test_real_repo_is_clean():
    """The committed tree passes the gate it carries."""
    assert REAL_REGISTRY.is_file()
    r = subprocess.run([sys.executable, str(CHECKER)], capture_output=True,
                       text=True, cwd=str(REPO))
    assert r.returncode == EXIT_PASS, r.stdout + r.stderr
    assert "VERDICT: PASS" in r.stdout


def test_real_registry_names_the_five_parameters():
    data = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    ids = {p["id"] for p in data["parameters"]}
    assert EXPECTED_PARAMETERS <= ids, "missing: %s" % (EXPECTED_PARAMETERS - ids)
    for p in data["parameters"]:
        # every real entry must carry the schema the checker relies on
        for key in ("owner", "canonical", "anchors", "forbid", "scan", "who_else_asserted"):
            assert p.get(key), "%s is missing %s" % (p["id"], key)


def test_real_registry_owners_are_cited_in_their_rows():
    """Sanity: the registry's canonical values are the ones named in the task."""
    data = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    by_id = {p["id"]: p for p in data["parameters"]}
    assert "8 MB" in by_id["esp32s3_flash_size"]["canonical"]
    assert "bare LoRa2021" in by_id["v9_2g4_rx_radio"]["canonical"]
    assert "VERTICAL" in by_id["wing_plane_orientation"]["canonical"]
    assert "103.0 × 103.0 mm" in by_id["hub_outline"]["canonical"]
    assert "1.30 × 1.30 mm" in by_id["f33_castellation_land_size"]["canonical"]
