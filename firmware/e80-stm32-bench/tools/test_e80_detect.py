#!/usr/bin/env python3
"""test_e80_detect.py — tests for E80 board auto-detection (Linux + macOS).

Run:  python3 -m pytest tools/test_e80_detect.py -v

Tests are designed to run on any platform.  Platform-specific code paths are
exercised by monkey-patching ``platform.system`` and mocking subprocess calls.
"""

from __future__ import annotations

import platform
from unittest import mock

import pytest

import e80_detect


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

class FakeSubprocessResult:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


MAC_IODEV = "cu.usbserial-1420"
MAC_IODEV2 = "cu.usbserial-1440"


# ---------------------------------------------------------------------------
# IS_MAC constant
# ---------------------------------------------------------------------------

class TestPlatformConstant:
    """Verify the module exposes an IS_MAC flag."""

    def test_is_mac_exists(self):
        assert hasattr(e80_detect, "IS_MAC")

    def test_is_mac_is_bool(self):
        assert isinstance(e80_detect.IS_MAC, bool)

    def test_is_mac_matches_platform(self):
        assert e80_detect.IS_MAC == (platform.system() == "Darwin")


# ---------------------------------------------------------------------------
# find_ch340_ports — macOS
# ---------------------------------------------------------------------------

class TestFindCh340Mac:
    """Mac CH340 port discovery via /dev/cu.usbserial-* + ioreg."""

    def test_mac_finds_cu_usbserial_ports(self):
        """Glob /dev/cu.usbserial-* returns all matches on Mac."""
        # ioreg output with two CH340 devices, serials matching port suffixes
        ioreg_output = (
            "+-o CH340  @14000000  <class AppleUSBDevice, id 0x100012345>\n"
            "    {\n"
            "      \"idVendor\" = 6790\n"
            "      \"idProduct\" = 29987\n"
            "      \"USB Serial Number\" = \"1420\"\n"
            "    }\n"
            "\n"
            "+-o CH340  @13000000  <class AppleUSBDevice, id 0x100012346>\n"
            "    {\n"
            "      \"idVendor\" = 6790\n"
            "      \"idProduct\" = 29987\n"
            "      \"USB Serial Number\" = \"1440\"\n"
            "    }\n"
        )
        with mock.patch.object(e80_detect, "IS_MAC", True), \
             mock.patch("glob.glob", return_value=[
                 f"/dev/{MAC_IODEV}", f"/dev/{MAC_IODEV2}",
             ]), \
             mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = FakeSubprocessResult(stdout=ioreg_output)
            result = e80_detect.find_ch340_ports()
            assert sorted(result) == sorted([
                f"/dev/{MAC_IODEV}", f"/dev/{MAC_IODEV2}",
            ])

    def test_mac_filters_non_ch340_ports(self):
        """Ports where ioreg doesn't show CH340 vendor ID are excluded."""
        # ioreg output showing one CH340 with serial "1420" and one
        # FTDI device with serial "FTFOO"
        ioreg_output = (
            "+-o CH340  @14000000  <class AppleUSBDevice, id 0x100012345>\n"
            "    {\n"
            "      \"USB Product Name\" = \"CH340\"\n"
            "      \"idVendor\" = 6790\n"
            "      \"idProduct\" = 29987\n"
            "      \"USB Serial Number\" = \"1420\"\n"
            "    }\n"
            "\n"
            "+-o FTDI  @13000000  <class AppleUSBDevice, id 0x100012346>\n"
            "    {\n"
            "      \"USB Product Name\" = \"FT232R\"\n"
            "      \"idVendor\" = 1027\n"
            "      \"idProduct\" = 24577\n"
            "      \"USB Serial Number\" = \"FTFOO\"\n"
            "    }\n"
        )
        with mock.patch.object(e80_detect, "IS_MAC", True), \
             mock.patch("glob.glob", return_value=[
                 f"/dev/{MAC_IODEV}", f"/dev/cu.usbserial-FTFOO",
             ]), \
             mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = FakeSubprocessResult(stdout=ioreg_output)
            result = e80_detect.find_ch340_ports()
            assert result == [f"/dev/{MAC_IODEV}"]

    def test_mac_no_ports_returns_empty(self):
        """No cu.usbserial-* devices → empty list."""
        with mock.patch.object(e80_detect, "IS_MAC", True), \
             mock.patch("glob.glob", return_value=[]):
            result = e80_detect.find_ch340_ports()
            assert result == []

    def test_mac_ioreg_failure_falls_back_to_glob(self):
        """If ioreg fails, still return cu.usbserial-* ports as best effort."""
        with mock.patch.object(e80_detect, "IS_MAC", True), \
             mock.patch("glob.glob", return_value=[f"/dev/{MAC_IODEV}"]), \
             mock.patch("subprocess.run", side_effect=Exception("timeout")):
            result = e80_detect.find_ch340_ports()
            # Should fall back to returning the glob results
            assert result == [f"/dev/{MAC_IODEV}"]


# ---------------------------------------------------------------------------
# find_ch340_ports — Linux (regression)
# ---------------------------------------------------------------------------

class TestFindCh340Linux:
    """Ensure existing Linux behaviour is preserved."""

    def test_linux_uses_ttyusb_and_udevadm(self):
        with mock.patch.object(e80_detect, "IS_MAC", False), \
             mock.patch("glob.glob", return_value=["/dev/ttyUSB0"]), \
             mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = FakeSubprocessResult(
                stdout="ID_VENDOR_ID=1a86\nID_MODEL_ID=7523\n"
            )
            result = e80_detect.find_ch340_ports()
            assert result == ["/dev/ttyUSB0"]
            # Verify udevadm was called, not ioreg
            args = mock_run.call_args[0][0]
            assert "udevadm" in args


# ---------------------------------------------------------------------------
# find_swd_probes — macOS
# ---------------------------------------------------------------------------

class TestFindSwdProbesMac:
    """Mac SWD probe discovery via ioreg."""

    # Sample ioreg output containing both TX and RX probes
    IODEV_TX = MAC_IODEV
    IODEV_RX = MAC_IODEV2

    def _make_ioreg_output(self):
        """Return a realistic ioreg -p IOUSB -l -w 0 output snippet."""
        return (
            "+-o Pico  @14000000  <class AppleUSBDevice, id 0x100012345, registered, matched, active, busy 0 (7 ms), retain 13>\n"
            "    {\n"
            "      \"USB Product Name\" = \"Pico\"\n"
            "      \"USB Vendor Name\" = \"Raspberry Pi\"\n"
            "      \"idVendor\" = 11850\n"
            "      \"idProduct\" = 11888\n"
            "      \"USB Serial Number\" = \"" + e80_detect.PROBE_TX + "\"\n"
            "    }\n"
            "\n"
            "+-o Pico  @13000000  <class AppleUSBDevice, id 0x100012346, registered, matched, active, busy 0 (5 ms), retain 13>\n"
            "    {\n"
            "      \"USB Product Name\" = \"Pico\"\n"
            "      \"USB Vendor Name\" = \"Raspberry Pi\"\n"
            "      \"idVendor\" = 11850\n"
            "      \"idProduct\" = 11888\n"
            "      \"USB Serial Number\" = \"" + e80_detect.PROBE_RX + "\"\n"
            "    }\n"
        )

    def test_mac_finds_probes_from_ioreg(self):
        """Both known probe serials are found in ioreg output."""
        ioreg = self._make_ioreg_output()
        with mock.patch.object(e80_detect, "IS_MAC", True), \
             mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = FakeSubprocessResult(stdout=ioreg)
            result = e80_detect.find_swd_probes()
        assert e80_detect.PROBE_TX in result
        assert e80_detect.PROBE_RX in result
        assert result[e80_detect.PROBE_TX]["role"] == "TX"
        assert result[e80_detect.PROBE_RX]["role"] == "RX"

    def test_mac_single_probe(self):
        """Only TX probe present in ioreg output."""
        ioreg = (
            "+-o Pico  @14000000  <class AppleUSBDevice>\n"
            "    {\n"
            "      \"USB Serial Number\" = \"" + e80_detect.PROBE_TX + "\"\n"
            "      \"USB Product Name\" = \"Pico\"\n"
            "    }\n"
        )
        with mock.patch.object(e80_detect, "IS_MAC", True), \
             mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = FakeSubprocessResult(stdout=ioreg)
            result = e80_detect.find_swd_probes()
        assert len(result) == 1
        assert e80_detect.PROBE_TX in result
        assert e80_detect.PROBE_RX not in result

    def test_mac_no_probes_returns_empty(self):
        """ioreg with no matching serials → empty dict."""
        ioreg = (
            "+-o SomeDevice  @14000000  <class AppleUSBDevice>\n"
            "    {\n"
            "      \"USB Serial Number\" = \"SOMEOTHERSERIAL1234\"\n"
            "    }\n"
        )
        with mock.patch.object(e80_detect, "IS_MAC", True), \
             mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = FakeSubprocessResult(stdout=ioreg)
            result = e80_detect.find_swd_probes()
        assert result == {}

    def test_mac_ioreg_exception_returns_empty(self):
        """If ioreg fails entirely, return empty dict."""
        with mock.patch.object(e80_detect, "IS_MAC", True), \
             mock.patch("subprocess.run", side_effect=Exception("fail")):
            result = e80_detect.find_swd_probes()
        assert result == {}

    def test_mac_probe_has_product_field(self):
        """Probe entries include a 'product' field."""
        ioreg = (
            "+-o Pico  @14000000  <class AppleUSBDevice>\n"
            "    {\n"
            "      \"USB Serial Number\" = \"" + e80_detect.PROBE_TX + "\"\n"
            "      \"USB Product Name\" = \"Pico\"\n"
            "    }\n"
        )
        with mock.patch.object(e80_detect, "IS_MAC", True), \
             mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = FakeSubprocessResult(stdout=ioreg)
            result = e80_detect.find_swd_probes()
        assert result[e80_detect.PROBE_TX]["product"] == "Pico"


# ---------------------------------------------------------------------------
# find_swd_probes — Linux (regression)
# ---------------------------------------------------------------------------

class TestFindSwdProbesLinux:
    """Ensure existing Linux sysfs behaviour is preserved."""

    def test_linux_uses_sysfs(self):
        """Linux path still scans /sys/bus/usb/devices/*."""
        with mock.patch.object(e80_detect, "IS_MAC", False), \
             mock.patch("glob.glob", return_value=["/sys/bus/usb/devices/1-1"]), \
             mock.patch("os.path.isfile", return_value=True), \
             mock.patch("builtins.open", mock.mock_open(
                 read_data=e80_detect.PROBE_TX + "\n")):
            result = e80_detect.find_swd_probes()
        assert e80_detect.PROBE_TX in result
        assert result[e80_detect.PROBE_TX]["role"] == "TX"


# ---------------------------------------------------------------------------
# check_deps — macOS hints
# ---------------------------------------------------------------------------

class TestCheckDepsMac:
    """On Mac, install hints should mention brew, not apt."""

    def test_mac_openocd_hint_mentions_brew(self):
        with mock.patch.object(e80_detect, "IS_MAC", True), \
             mock.patch.object(e80_detect, "find_openocd", return_value=None), \
             mock.patch.object(e80_detect, "find_pyserial", return_value=True):
            deps = e80_detect.check_deps()
        assert deps["all_ok"] is False
        combined = " ".join(deps["issues"])
        assert "brew" in combined.lower()
        assert "apt" not in combined.lower()


# ---------------------------------------------------------------------------
# find_openocd — macOS path
# ---------------------------------------------------------------------------

class TestFindOpenocdMac:
    """find_openocd should check brew paths on Mac."""

    def test_mac_checks_brew_path(self):
        with mock.patch.object(e80_detect, "IS_MAC", True), \
             mock.patch("os.path.isfile") as mock_isfile, \
             mock.patch("os.access", return_value=True):
            # Make /opt/homebrew/bin/openocd exist
            def isfile_side(path):
                return path == "/opt/homebrew/bin/openocd"
            mock_isfile.side_effect = isfile_side
            result = e80_detect.find_openocd()
        assert result == "/opt/homebrew/bin/openocd"