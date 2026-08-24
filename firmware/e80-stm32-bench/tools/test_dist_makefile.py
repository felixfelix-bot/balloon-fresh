#!/usr/bin/env python3
"""
Test DIST parameter normalization for the Makefile.

Verifies that:
  1. DIST values normalize correctly to per-stop config filenames.
  2. All 9 valid DIST values resolve to existing files under configs/per-stop/.
  3. Invalid DIST values are rejected.

The normalization logic mirrors the Makefile's DIST handling:
  - Bare number (e.g. "100") → stop-100m.json (meters)
  - Alphanumeric (e.g. "50m", "70km") → stop-<DIST>.json
"""

import os
import subprocess
import sys
import pytest

# Paths
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
E80_DIR = os.path.dirname(TOOLS_DIR)
REPO_ROOT = os.path.abspath(os.path.join(E80_DIR, "..", ".."))
CONFIGS_DIR = os.path.join(REPO_ROOT, "configs")
PER_STOP_DIR = os.path.join(CONFIGS_DIR, "per-stop")
MAKEFILE = os.path.join(E80_DIR, "Makefile")

VALID_DISTS = ["50m", "100m", "218m", "436m", "872m", "1744m", "5km", "11km", "70km"]


def normalize_dist(dist):
    """
    Mirror the Makefile normalization:
      bare number → <n>m
      otherwise   → as-is
    Returns the bare stop name (e.g. "stop-50m") without path or .json.
    """
    if dist.isdigit():
        return f"stop-{dist}m"
    return f"stop-{dist}"


def dist_to_filepath(dist):
    """Full path to the per-stop config file for a given DIST value."""
    return os.path.join(PER_STOP_DIR, normalize_dist(dist) + ".json")


# ── 1. Normalization tests ────────────────────────────────────────────

@pytest.mark.parametrize("dist,expected", [
    ("50m", "stop-50m.json"),
    ("100m", "stop-100m.json"),
    ("218m", "stop-218m.json"),
    ("436m", "stop-436m.json"),
    ("872m", "stop-872m.json"),
    ("1744m", "stop-1744m.json"),
    ("5km", "stop-5km.json"),
    ("11km", "stop-11km.json"),
    ("70km", "stop-70km.json"),
    # Bare numbers = meters
    ("50", "stop-50m.json"),
    ("100", "stop-100m.json"),
    ("1744", "stop-1744m.json"),
])
def test_dist_normalization(dist, expected):
    """DIST value normalizes to the expected filename."""
    result = normalize_dist(dist) + ".json"
    assert result == expected, f"DIST={dist!r} → {result}, expected {expected}"


# ── 2. All valid DISTs resolve to existing files ───────────────────────

@pytest.mark.parametrize("dist", VALID_DISTS)
def test_valid_dist_files_exist(dist):
    """Every valid DIST value maps to an existing per-stop config file."""
    path = dist_to_filepath(dist)
    assert os.path.isfile(path), f"Missing config file for DIST={dist}: {path}"


@pytest.mark.parametrize("dist", ["50", "100", "218", "436", "872", "1744"])
def test_bare_number_dist_files_exist(dist):
    """Bare-number DIST values (meters) also resolve to existing files."""
    path = dist_to_filepath(dist)
    assert os.path.isfile(path), f"Missing config file for DIST={dist}: {path}"


# ── 3. Invalid DIST values ─────────────────────────────────────────────

@pytest.mark.parametrize("invalid_dist", ["99m", "200m", "1km", "abc", "0", ""])
def test_invalid_dist_not_a_file(invalid_dist):
    """Invalid DIST values should NOT resolve to an existing file."""
    if invalid_dist == "":
        return  # empty DIST means "not set" — skip
    path = dist_to_filepath(invalid_dist)
    assert not os.path.isfile(path), f"Unexpected file exists for invalid DIST={invalid_dist}: {path}"


def test_invalid_dist_makefile_errors():
    """
    `make range-dry-run DIST=99m` should fail (non-zero exit) and mention
    valid values in the error message.
    """
    result = subprocess.run(
        ["make", "range-dry-run", "DIST=99m"],
        capture_output=True, text=True,
        cwd=E80_DIR,
        timeout=30,
    )
    assert result.returncode != 0, "make should fail on invalid DIST"
    # Error message should mention valid values
    combined = result.stdout + result.stderr
    assert "50m" in combined or "valid" in combined.lower(), \
        f"Error output should list valid DIST values, got: {combined}"


# ── 4. Makefile dry-run with valid DIST ────────────────────────────────

@pytest.mark.parametrize("dist", ["50m", "70km"])
def test_makefile_dry_run_with_dist(dist):
    """
    `make range-dry-run DIST=<dist>` should succeed and reference the
    correct per-stop config in its output.
    """
    result = subprocess.run(
        ["make", "range-dry-run", f"DIST={dist}"],
        capture_output=True, text=True,
        cwd=E80_DIR,
        timeout=30,
    )
    expected_config = f"stop-{dist}.json"
    combined = result.stdout + result.stderr
    assert result.returncode == 0, \
        f"make range-dry-run DIST={dist} failed: {combined}"
    assert expected_config in combined, \
        f"Output should reference {expected_config}, got: {combined}"


def test_makefile_dry_run_bare_number():
    """
    `make range-dry-run DIST=100` should succeed and reference stop-100m.json.
    """
    result = subprocess.run(
        ["make", "range-dry-run", "DIST=100"],
        capture_output=True, text=True,
        cwd=E80_DIR,
        timeout=30,
    )
    combined = result.stdout + result.stderr
    assert result.returncode == 0, \
        f"make range-dry-run DIST=100 failed: {combined}"
    assert "stop-100m.json" in combined, \
        f"Output should reference stop-100m.json, got: {combined}"


# ── 5. DIST not set → existing behavior ────────────────────────────────

def test_no_dist_uses_default_configs():
    """
    `make range-dry-run` without DIST should use the default CONFIGS
    (envelope-4cfg-max.json).
    """
    result = subprocess.run(
        ["make", "range-dry-run"],
        capture_output=True, text=True,
        cwd=E80_DIR,
        timeout=30,
    )
    combined = result.stdout + result.stderr
    assert result.returncode == 0, \
        f"make range-dry-run without DIST failed: {combined}"
    assert "envelope-4cfg-max.json" in combined, \
        f"Output should reference default config, got: {combined}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))