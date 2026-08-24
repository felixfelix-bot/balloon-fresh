#!/usr/bin/env python3
"""TDD tests for LoRa L511 config filtering in e80_sweep_full.py.

The LR2021 chip's LoRa mode uses an 8-bit payload length field → max 255
bytes. L511 configs are untestable in LoRa and produce misleading 100%
PER. These tests verify that build_configs() skips LoRa configs with
plen > 255, and that the docstring documents the cap.

Run:  python3 -m pytest test_e80_sweep_lora_filter.py -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import e80_sweep_full as sf  # noqa: E402


class TestLoRaLenCap(unittest.TestCase):
    """build_configs() must not emit LoRa configs with plen > 255."""

    def test_no_lora_above_255(self):
        """No LoRa config in the full sweep exceeds 255 bytes."""
        cfgs = sf.build_configs()
        for cfg in cfgs:
            if cfg["mod"] == "lora":
                self.assertLessEqual(
                    cfg["plen"], 255,
                    f"LoRa config '{cfg['label']}' has plen={cfg['plen']} "
                    f"> 255 (LR2021 LoRa 8-bit length cap)")

    def test_flrc_above_255_still_present(self):
        """FLRC configs with plen > 255 are still in the sweep (FLRC
        supports 511 bytes — only LoRa is capped at 255)."""
        cfgs = sf.build_configs()
        flrc_long = [c for c in cfgs if c["mod"] == "flrc" and c["plen"] > 255]
        self.assertGreater(
            len(flrc_long), 0,
            "FLRC configs with plen > 255 should still be present")

    def test_lora_511_not_in_configs(self):
        """Explicitly check: no LoRa config has plen == 511."""
        cfgs = sf.build_configs()
        lora_511 = [c for c in cfgs if c["mod"] == "lora" and c["plen"] == 511]
        self.assertEqual(
            len(lora_511), 0,
            "LoRa L511 config should be filtered out (LR2021 LoRa max = 255)")

    def test_flrc_511_present(self):
        """FLRC L511 is present (it's the FLRC maximum, legal in FLRC)."""
        cfgs = sf.build_configs()
        flrc_511 = [c for c in cfgs if c["mod"] == "flrc" and c["plen"] == 511]
        self.assertGreater(len(flrc_511), 0,
                           "FLRC L511 should still be present")

    def test_lora_255_present(self):
        """LoRa L255 is the maximum legal LoRa payload — should be present."""
        cfgs = sf.build_configs()
        lora_255 = [c for c in cfgs if c["mod"] == "lora" and c["plen"] == 255]
        self.assertGreater(len(lora_255), 0,
                           "LoRa L255 should be present (at the cap)")

    def test_2g4_lora_511_filtered(self):
        """2.4 GHz LoRa configs also filter L511 (same chip restriction)."""
        cfgs = sf.build_configs()
        lora_2g4_511 = [c for c in cfgs
                        if c["mod"] == "lora" and c["plen"] == 511
                        and c["freq"] >= 2400000000]
        self.assertEqual(len(lora_2g4_511), 0,
                         "2.4 GHz LoRa L511 should be filtered")


class TestDocstringUpdated(unittest.TestCase):
    """The module docstring documents the LoRa 255 / FLRC 511 cap."""

    def test_docstring_mentions_lora_255(self):
        self.assertIn("6-255", sf.__doc__)
        self.assertIn("LoRa", sf.__doc__)

    def test_docstring_mentions_flrc_511(self):
        self.assertIn("511", sf.__doc__)
        self.assertIn("FLRC", sf.__doc__)

    def test_docstring_not_old_text(self):
        """Old docstring said 'LEN: 6-511 bytes' — should be gone."""
        self.assertNotIn("LEN: 6-511 bytes", sf.__doc__)


if __name__ == "__main__":
    unittest.main()
