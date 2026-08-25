#!/usr/bin/env python3
"""test_range_test_guide.py — TDD tests for the RANGE-TEST-GUIDE.md update.

Task 11 of the guard-time/config/CVM plan: update the operator guide
(firmware/e80-stm32-bench/docs/RANGE-TEST-GUIDE.md) to document:

1. The reduced guard-time timing table (t0_margin=30s, guard=5s,
   rx_lead=3s, settle=1s, swd_reset_s=2s).
2. The 4-config envelope preset (envelope-4cfg-max: FLRC-650 511B,
   FLRC-2600 511B, LoRa-SF7 255B, LoRa-SF12 255B).
3. The 70 km distance matrix (6 stops: 218m/436m/872m/1744m/5km/11km/70km).
4. The CVM config provider section (set_config tool, range-cvm-server /
   range-adaptive usage).
5. The NTP sync verification step (run `date -u +%s` on both machines).

RED phase: these tests are written BEFORE the guide is updated. They should
FAIL against the current guide.

Run:  python3 -m pytest tools/test_range_test_guide.py -v
"""

from __future__ import annotations

import pathlib
import unittest

# Guide is two levels up from tools/ (tools/ -> e80-stm32-bench/)
GUIDE = pathlib.Path(__file__).resolve().parent.parent / "docs" / "RANGE-TEST-GUIDE.md"


def _read_guide() -> str:
    assert GUIDE.exists(), f"RANGE-TEST-GUIDE.md not found at {GUIDE}"
    return GUIDE.read_text()


class TestTimingTable(unittest.TestCase):
    """The guide must document the reduced guard-time defaults."""

    @classmethod
    def setUpClass(cls):
        cls.guide = _read_guide()

    def test_timing_table_present(self):
        self.assertIn("Timing", self.guide,
                      "guide should have a timing section")

    def test_t0_margin_30(self):
        self.assertIn("t0_margin=30", self.guide,
                      "guide should document t0_margin=30s")

    def test_guard_5(self):
        self.assertIn("guard=5", self.guide,
                      "guide should document guard=5s")

    def test_rx_lead_3(self):
        self.assertIn("rx_lead=3", self.guide,
                      "guide should document rx_lead=3s")

    def test_settle_1(self):
        self.assertIn("settle=1", self.guide,
                      "guide should document settle=1s")

    def test_swd_reset_2(self):
        self.assertIn("swd_reset_s=2", self.guide,
                      "guide should document swd_reset_s=2s")


class TestEnvelope4CfgPreset(unittest.TestCase):
    """The guide must document the envelope-4cfg-max preset."""

    @classmethod
    def setUpClass(cls):
        cls.guide = _read_guide()

    def test_preset_section_present(self):
        self.assertIn("envelope-4cfg-max", self.guide,
                      "guide should document the envelope-4cfg-max preset")

    def test_flrc650_511(self):
        self.assertIn("FLRC-650", self.guide)
        self.assertIn("511", self.guide,
                      "guide should show FLRC-650 at 511B max payload")

    def test_flrc2600_kept(self):
        self.assertIn("FLRC-2600", self.guide,
                      "guide should keep FLRC-2600 (high data rate)")

    def test_lora_sf7_255(self):
        self.assertIn("SF7", self.guide)
        self.assertIn("255", self.guide,
                      "guide should show LoRa-SF7 at 255B max payload")

    def test_lora_sf12_255(self):
        self.assertIn("SF12", self.guide,
                      "guide should show LoRa-SF12 at 255B max payload")


class TestDistanceMatrix(unittest.TestCase):
    """The guide must document the 70 km distance matrix."""

    @classmethod
    def setUpClass(cls):
        cls.guide = _read_guide()

    def test_distance_matrix_present(self):
        self.assertIn("70 km", self.guide,
                      "guide should document the 70 km distance matrix")

    def test_all_six_stops(self):
        for stop in ("218m", "436m", "872m", "1744m", "5km", "11km", "70km"):
            self.assertIn(stop, self.guide,
                          f"distance matrix should include stop {stop}")

    def test_mission_reference(self):
        self.assertIn("Madeira", self.guide,
                      "guide should reference the Madeira-Porto Santo 70 km mission")


class TestCvmConfigProvider(unittest.TestCase):
    """The guide must document the CVM config provider mode."""

    @classmethod
    def setUpClass(cls):
        cls.guide = _read_guide()

    def test_cvm_section_present(self):
        self.assertIn("CVM Config Provider", self.guide,
                      "guide should have a CVM config provider section")

    def test_set_config_tool(self):
        self.assertIn("set_config", self.guide,
                      "guide should document the set_config MCP tool")

    def test_range_cvm_server(self):
        self.assertIn("range-cvm-server", self.guide,
                      "guide should document range-cvm-server usage")

    def test_range_adaptive(self):
        self.assertIn("range-adaptive", self.guide,
                      "guide should document range-adaptive usage")


class TestNtpSyncStep(unittest.TestCase):
    """The guide must document the NTP sync verification step."""

    @classmethod
    def setUpClass(cls):
        cls.guide = _read_guide()

    def test_ntp_sync_step(self):
        self.assertIn("date -u +%s", self.guide,
                      "guide should tell operators to run `date -u +%s` on both machines")

    def test_ntp_mentioned(self):
        self.assertIn("NTP", self.guide,
                      "guide should mention NTP sync")


if __name__ == "__main__":
    unittest.main(verbosity=2)
