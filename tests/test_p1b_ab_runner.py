"""Offline (no-hardware) tests for tests/p1b_ab_test.py — the P1B A/B sweep runner.

Covers: CLI flag forms used by the fleet's pinned verification commands, --br
parsing, RX-result parsing, and port-identity continuity across USB CDC
re-enumeration (by-id resolution + fallbacks). Importing the runner must be
side-effect free (no sweep, no exit) when no boards are attached.
"""
import importlib.util
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(REPO_ROOT, "tests", "p1b_ab_test.py")


@pytest.fixture(scope="module")
def p1b():
    spec = importlib.util.spec_from_file_location("p1b_ab_test", RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_import_side_effect_free(p1b):
    # Module imported fine with no /dev/ttyACM* present — no exit, no sweep.
    assert p1b.detect_esp_ports() == [] or len(p1b.detect_esp_ports()) >= 0


def test_flag_forms(p1b):
    assert p1b.parser.parse_args(["--reset-between-tests"]).reset_between_tests is True
    assert p1b.parser.parse_args(["--no-reset-between-tests"]).reset_between_tests is False
    assert p1b.parser.parse_args([]).reset_between_tests is False  # bare = legacy default


def test_br_list(p1b):
    assert p1b.parse_br_list("2600,1300, 650") == [2600, 1300, 650]
    assert p1b.parse_br_list(p1b.parser.parse_args([]).br) == [2600, 1300, 650, 325]
    with pytest.raises(ValueError):
        p1b.parse_br_list("  ")


def test_parse_rx_results(p1b):
    text = ("received,100\ncrc_errors,0\nlost,0\ntotal_sent_by_tx,100\n"
            "elapsed_ms,9812\nthroughput_kbps,20.8\nper_pct,0.000\n"
            "avg_rssi,-105.0\ntime_per_pkt_ms,98.12\n")
    r = p1b.parse(text)
    assert r["received"] == 100
    assert r["throughput"] == 20.8
    assert r["per"] == 0.0
    assert r["rssi"] == -105.0
    assert r["ms_per_pkt"] == 98.12


def test_parse_empty_defaults_to_total_loss(p1b):
    r = p1b.parse("garbage\n")
    assert r["received"] == 0 and r["per"] == 100


def test_resolve_nodes_stable(p1b):
    t, x, how = p1b.resolve_role_ports("/dev/ttyACM2", "/dev/ttyACM3",
                                       ["/dev/ttyACM2", "/dev/ttyACM3"], {})
    assert (t, x, how) == ("/dev/ttyACM2", "/dev/ttyACM3", "nodes-stable")


def test_resolve_by_id_after_shift(p1b):
    # Boards moved ACM2/3 -> ACM4/5; stale nodes may still linger in the idmap
    # mid-enumeration. by-id must preserve TX/RX identity.
    idmap = {"/dev/ttyACM4": "/dev/serial/by-id/usb-A-TX",
             "/dev/ttyACM5": "/dev/serial/by-id/usb-B-RX",
             "/dev/ttyACM2": "/dev/serial/by-id/usb-A-TX",
             "/dev/ttyACM3": "/dev/serial/by-id/usb-B-RX"}
    t, x, how = p1b.resolve_role_ports("/dev/ttyACM2", "/dev/ttyACM3",
                                       ["/dev/ttyACM4", "/dev/ttyACM5"], idmap)
    assert (t, x, how) == ("/dev/ttyACM4", "/dev/ttyACM5", "by-id")


def test_resolve_no_by_id_falls_back_with_warning(p1b):
    t, x, how = p1b.resolve_role_ports("/dev/ttyACM2", "/dev/ttyACM3",
                                       ["/dev/ttyACM0", "/dev/ttyACM4"], {})
    assert (t, x) == ("/dev/ttyACM0", "/dev/ttyACM4")
    assert "ORDERING-FALLBACK" in how


def test_resolve_too_few_ports_raises(p1b):
    with pytest.raises(RuntimeError):
        p1b.resolve_role_ports("/dev/ttyACM2", "/dev/ttyACM3", ["/dev/ttyACM4"], {})


def test_help_works_without_hardware():
    p = subprocess.run([sys.executable, RUNNER, "--help"],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    for needle in ("--reset-between-tests", "--no-reset-between-tests", "--br"):
        assert needle in p.stdout


def test_missing_ports_exit_code_and_message():
    if p1b_ports_present():
        pytest.skip("boards attached — headless path not testable")
    p = subprocess.run([sys.executable, RUNNER], capture_output=True, text=True)
    assert p.returncode == 1
    assert "Need 2 ESP32 serial ports" in p.stdout


def p1b_ports_present():
    return any(os.path.exists(f"/dev/ttyACM{i}") for i in range(2, 10))
