"""Host tests for the E28 ranging bench harness helpers (no hardware needed).

Run:  /usr/bin/python3 -m pytest firmware/esp32-e28-range/tools/test_e28_range_bench.py -v
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402

from e28_range_bench import (  # noqa: E402
    is_timeout,
    parse_distance,
    parse_stat,
    resolve_port,
)


class TestResolvePort:
    def test_resolves_by_serial_substring(self, tmp_path):
        target = tmp_path / "usb-Espressif_USB_JTAG_serial_debug_unit_9C:13:9E:F1:0C:60-if00"
        target.symlink_to("/dev/ttyACM1")
        (tmp_path / "usb-Espressif_USB_JTAG_serial_debug_unit_9C:13:9E:F1:0C:28-if00").symlink_to(
            "/dev/ttyACM0"
        )
        (tmp_path / "usb-Sierra_Wireless_EM7455-if00-port0").symlink_to("/dev/ttyUSB0")

        got = resolve_port("9C:13:9E:F1:0C:60", by_id_glob=str(tmp_path / "*"))
        assert got == "/dev/ttyACM1"

    def test_missing_board_raises_with_inventory(self, tmp_path):
        (tmp_path / "usb-Sierra_Wireless_EM7455-if00-port0").symlink_to("/dev/ttyUSB0")
        with pytest.raises(LookupError) as e:
            resolve_port("9C:13:9E:F1:0C:60", by_id_glob=str(tmp_path / "*"))
        # the error must list what IS present, so an operator can see the mismatch
        assert "Sierra" in str(e.value)

    def test_port_number_is_not_used_for_identity(self, tmp_path):
        """Two boards swapped between ttyACM0/ttyACM1 must still resolve correctly."""
        a = tmp_path / "usb-Espressif_9C:13:9E:F1:0C:28-if00"
        b = tmp_path / "usb-Espressif_9C:13:9E:F1:0C:60-if00"
        a.symlink_to("/dev/ttyACM1")   # deliberately swapped vs the first run
        b.symlink_to("/dev/ttyACM0")
        assert resolve_port("9C:13:9E:F1:0C:28", by_id_glob=str(tmp_path / "*")) == "/dev/ttyACM1"
        assert resolve_port("9C:13:9E:F1:0C:60", by_id_glob=str(tmp_path / "*")) == "/dev/ttyACM0"


class TestParseDistance:
    def test_plain(self):
        assert parse_distance("DIST=12.75m") == 12.75

    def test_with_rssi_suffix(self):
        assert parse_distance("DIST=0.42m rssi=-101") == 0.42

    def test_negative(self):
        assert parse_distance("DIST=-1.5m") == -1.5

    def test_none(self):
        assert parse_distance("DIST=none") is None

    def test_timeout_line(self):
        assert parse_distance("RANGE TIMEOUT") is None

    def test_garbage(self):
        assert parse_distance("RANGE") is None
        assert parse_distance("") is None


class TestParseStat:
    STAT = ("role=master freq=2440 sf=7 bw=812.5 pa=10 "
            "addr=0xE80E2801 last=12.75 err=0")

    def test_fields(self):
        d = parse_stat(self.STAT)
        assert d["role"] == "master"
        assert d["freq"] == "2440"
        assert d["pa"] == "10"
        assert d["addr"] == "0xE80E2801"
        assert d["last"] == "12.75"
        assert d["err"] == "0"

    def test_absent_fields_are_omitted(self):
        assert parse_stat("role=idle") == {"role": "idle"}

    def test_does_not_capture_errocode_prefix_confusion(self):
        # "err=" must not be matched by a naive "e" prefix search
        d = parse_stat(self.STAT)
        assert set(d) == {"role", "freq", "sf", "bw", "pa", "addr", "last", "err"}


class TestIsTimeout:
    def test_timeout(self):
        assert is_timeout("RANGE TIMEOUT") is True
        assert is_timeout("range timeout") is True

    def test_not_timeout(self):
        assert is_timeout("DIST=3.0m") is False
