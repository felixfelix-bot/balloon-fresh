"""Tests for HOST-2: E80 host tools baud rate updated to 2,000,000.

Validates that all E80-facing host capture tools default to 2,000,000 baud
to match the E80 firmware bump (E80-2).  C3/RP2040 tools remain at 115200
since they use USB CDC where baud is cosmetic.

Some tools use a --board arg with default=None + auto-select logic:
  --board e80  → 2000000 (default)
  --board c3   → 115200
Others have a hardcoded default=2000000.
"""

import importlib.util
import os
import re
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
MESH_DIR = os.path.join(REPO_ROOT, "mesh-stack", "flrc-bench-espidf")


def _load_module_from_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None, f"Could not load spec for {path}"
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _get_default_baud(filepath):
    """Extract the effective default baud rate from an argparse-based CLI tool.

    Handles two patterns:
    1. Hardcoded: default=2000000 in --baud argument
    2. Auto-select: default=None in --baud, then board-based auto-select logic
       where board=e80 (default) → 2000000

    Returns the effective default baud for E80 board.
    """
    with open(filepath) as f:
        source = f.read()

    # Pattern 1: Hardcoded default=N in --baud argument
    m = re.search(
        r"add_argument\(\s*['\"]--baud['\"].*?default\s*=\s*(\d+)", source, re.DOTALL
    )
    if m:
        val = int(m.group(1))
        if val != 0:  # 0 could be a sentinel
            return val

    # Pattern 2: default=None with auto-select logic
    if "default=None" in source or "default = None" in source:
        # Check for auto-select: board == 'e80' → 2000000
        if re.search(r"['\"]e80['\"].*?2000000", source, re.DOTALL):
            return 2000000
        if re.search(r"2000000.*?['\"]e80['\"]", source, re.DOTALL):
            return 2000000

    return None


class TestE80HostBaud:
    """All E80-facing host tools must default to 2,000,000 baud."""

    def test_rx_range_logger_baud(self):
        """rx_range_logger.py — E80 range logger must default to 2,000,000 baud."""
        path = os.path.join(TOOLS_DIR, "rx_range_logger.py")
        baud = _get_default_baud(path)
        assert baud == 2000000, f"rx_range_logger.py baud default is {baud}, expected 2000000"

    def test_capture_sweep_baud(self):
        """capture_sweep.py — sweep capture must default to 2,000,000 baud."""
        path = os.path.join(TOOLS_DIR, "capture_sweep.py")
        baud = _get_default_baud(path)
        assert baud == 2000000, f"capture_sweep.py baud default is {baud}, expected 2000000"

    def test_walk_capture_baud(self):
        """walk_capture.py — walk capture must default to 2,000,000 baud."""
        path = os.path.join(TOOLS_DIR, "walk_capture.py")
        baud = _get_default_baud(path)
        assert baud == 2000000, f"walk_capture.py baud default is {baud}, expected 2000000"

    def test_monitor_range_baud(self):
        """monitor_range.py — E80 range monitor must default to 2,000,000 baud."""
        path = os.path.join(MESH_DIR, "monitor_range.py")
        baud = _get_default_baud(path)
        assert baud == 2000000, f"monitor_range.py baud default is {baud}, expected 2000000"

    def test_fw_harm_measurement_e80_baud(self):
        """fw_harm_measurement.py — E80 rig must use 2,000,000 baud."""
        path = os.path.join(TOOLS_DIR, "fw_harm_measurement.py")
        mod = _load_module_from_path("fw_harm_measurement", path)
        import inspect
        source = inspect.getsource(mod)
        assert "2000000" in source, "fw_harm_measurement.py should reference 2000000 for E80 baud"
        assert "e80" in source.lower() and "115200" in source, \
            "fw_harm_measurement.py should have rig-based baud selection"