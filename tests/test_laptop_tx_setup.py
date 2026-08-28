"""Unit tests for E80 bench TX-laptop setup: port parsing + root make proxies.

Regression for the Funchal demo field bug: `laptop-tx-setup.sh` re-grepped
/dev/ttyACM* for the SWD probe serial and picked the Pico debugprobe CDC
(ttyACM0) as the console PORT, generating broken per-stop commands.

The fix: a single source of truth (scripts/e80_detect_port.py) that reads the
`port:` field from e80_detect.py output — never re-greps /dev/ttyACM* — and
hard-aborts if the resolved console port is a ttyACM device (Pico probe CDC).
"""
import os
import re
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DETECT_PORT_MODULE = os.path.join(REPO_ROOT, "scripts", "e80_detect_port.py")

# Sample e80_detect.py output (non-JSON), single-board TX, port on CH340.
DETECT_OK_TX = """  role: TX
  port: /dev/ttyUSB0
  probe_serial: 148757200D2D1425
  id_reply: ID E80BENCH v1.2 fw=5fa7912 role=TX armed=1 mod=lora pa=22
  id_parsed: {'board': 'E80BENCH', 'fw': '5fa7912', 'role': 'TX', 'armed': '1', 'mod': 'lora', 'pa': '22'}
  fw_hash: 5fa7912
  openocd: /usr/local/bin/openocd
"""

# Same machine with BOTH a Pico debugprobe CDC (ttyACM0) AND the CH340 console.
# The detect `port:` field must still resolve to the CH340 console (ttyUSB0).
DETECT_OK_TX_WITH_ACM = """  role: TX
  port: /dev/ttyUSB1
  probe_serial: 148757200D2D1425
  id_reply: ID E80BENCH v1.2 fw=5fa7912 role=TX armed=1 mod=lora pa=22
  id_parsed: {'board': 'E80BENCH', 'fw': '5fa7912', 'role': 'TX', 'armed': '1', 'mod': 'lora', 'pa': '22'}
  fw_hash: 5fa7912
  openocd: /usr/local/bin/openocd
"""

# A (buggy/forbidden) detect output that resolved to ttyACM0 — the Pico probe CDC.
DETECT_BAD_ACM = """  role: TX
  port: /dev/ttyACM0
  probe_serial: 148757200D2D1425
  id_reply: None
  fw_hash: None
  openocd: /usr/local/bin/openocd
"""

# Detect output with no port field (detection failed / board not connected).
DETECT_NO_PORT = """  role: TX
  error: no SWD probe found. Ensure the E80 board is plugged in
"""


def _load_module():
    """Import scripts/e80_detect_port.py as a module (it may not be on sys.path)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("e80_detect_port", DETECT_PORT_MODULE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["e80_detect_port"] = mod
    spec.loader.exec_module(mod)
    return mod


# ── Port-parsing function tests ─────────────────────────────────────────

class TestPortParsing:
    def test_parses_ttyusb_port_from_detect_field(self):
        mod = _load_module()
        assert mod.parse_detect_port(DETECT_OK_TX) == "/dev/ttyUSB0"

    def test_picks_ttyusb_from_detect_field_even_when_acm_present(self):
        """Regression: the detect `port:` field names the CH340 console (ttyUSB),
        NOT the Pico probe CDC (ttyACM). ttyACM must never win."""
        mod = _load_module()
        assert mod.parse_detect_port(DETECT_OK_TX_WITH_ACM) == "/dev/ttyUSB1"

    def test_rejects_ttyacm_console_port(self):
        """ttyACM is the Pico debugprobe CDC UART — never a valid E80 console port."""
        mod = _load_module()
        with pytest.raises(SystemExit) as exc:
            mod.parse_detect_port(DETECT_BAD_ACM)
        assert exc.value.code != 0

    def test_missing_port_raises(self):
        mod = _load_module()
        with pytest.raises(SystemExit):
            mod.parse_detect_port(DETECT_NO_PORT)

    def test_detect_port_script_prints_port_only(self):
        """Running the helper against mock detect output yields the port on stdout."""
        # Use --port-from-output with a fixture string: parse only, no subprocess.
        proc = subprocess.run(
            [sys.executable, DETECT_PORT_MODULE, "--port-from-output", DETECT_OK_TX_WITH_ACM],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0
        assert proc.stdout.strip() == "/dev/ttyUSB1"

    def test_detect_port_script_aborts_on_acm(self):
        proc = subprocess.run(
            [sys.executable, DETECT_PORT_MODULE, "--port-from-output", DETECT_BAD_ACM],
            capture_output=True, text=True,
        )
        assert proc.returncode != 0
        assert "ttyACM" in proc.stderr


# ── Root Makefile proxy smoke tests ─────────────────────────────────────

def _run_make(*args, cwd=None):
    cwd = cwd or REPO_ROOT
    return subprocess.run(["make", "-n", *args], capture_output=True, text=True, cwd=cwd)


class TestRootMakeProxies:
    def test_root_make_tx_resolves(self):
        """`make -n tx` from repo root must resolve (no 'No rule to make target')."""
        proc = _run_make("tx")
        assert proc.returncode == 0, proc.stderr
        assert "No rule to make target" not in proc.stdout + proc.stderr

    def test_root_make_rx_resolves(self):
        proc = _run_make("rx")
        assert proc.returncode == 0, proc.stderr
        assert "No rule to make target" not in proc.stdout + proc.stderr

    def test_root_make_range_dry_run_with_dist(self):
        """`make -n range-dry-run DIST=50m` from root passes DIST through."""
        proc = _run_make("range-dry-run", "DIST=50m")
        assert proc.returncode == 0, proc.stderr
        assert "No rule to make target" not in proc.stdout + proc.stderr
        # The sub-make must actually recurse into firmware/e80-stm32-bench.
        assert "-C" in proc.stdout

    def test_root_make_boat_proxies_resolve(self):
        for target in ("boat-tx", "boat-rx", "range-merge", "range-stitch", "range-rx"):
            proc = _run_make(target, "DIST=50m")
            assert proc.returncode == 0, f"{target}: {proc.stderr}"
            assert "No rule to make target" not in proc.stdout + proc.stderr, f"{target}"

    def test_root_make_hint_when_no_target(self):
        """Running bare `make` from root prints the proxy hint."""
        proc = subprocess.run(
            ["make", "-n"], capture_output=True, text=True, cwd=REPO_ROOT
        )
        # help is default goal; hint should mention tx/rx at root.
        assert proc.returncode == 0
        assert "tx" in proc.stdout or "make" in proc.stdout
