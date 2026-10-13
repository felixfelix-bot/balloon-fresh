#!/usr/bin/env python3
"""test_gs_validation_docs.py — TDD tests for the RANGE-TEST-GUIDE.md interp
logging + GS validation documentation (e80-interp-logging).

RED phase: these tests assert the guide documents the new log fields /
validation comparison BEFORE the guide was updated. They failed against the
pre-update guide and pass after the update lands.

Run:  python3 -m pytest tools/test_gs_validation_docs.py -v
"""
from __future__ import annotations

import pathlib
import unittest

GUIDE = pathlib.Path(__file__).resolve().parent.parent / "docs" / "RANGE-TEST-GUIDE.md"


def _read_guide() -> str:
    assert GUIDE.exists(), f"RANGE-TEST-GUIDE.md not found at {GUIDE}"
    return GUIDE.read_text()


class TestInterpLoggingDocs(unittest.TestCase):
    """The guide must document the balloon-side interp log fields + GS
    observation line and the log-don't-tune command constraints."""

    @classmethod
    def setUpClass(cls):
        cls.guide = _read_guide()

    def test_extended_temp_fields_documented(self):
        for f in ("offset_hz", "curve_ver", "k_mhz_per_c", "t0_mc",
                  "vcc_mv", "gps_alt_m", "gps_temp_c", "sync_epoch_ms"):
            self.assertIn(f, self.guide,
                          f"guide should document {f} interp field")

    def test_vcc_mv_is_plain_mv_not_raw_13bit(self):
        """vcc_mv is the LR2021 supply voltage in real mV (UNIT format from
        the radio). It must NOT be described as a raw 13-bit count that the
        host converts — the host parser consumes the wire value as mV with
        no scaling, and the canonical test line uses 3300 for a 3.3 V
        supply. (Regression: firmware initially logged VALUE_FORMAT_RAW
        counts (~5643 @ 3.3 V) into the mV field.)"""
        # The field row / prose must state mV semantics.
        self.assertIn("Supply voltage in mV", self.guide)
        # No "raw 13-bit ... host converts" wording for the supply field.
        self.assertNotIn("raw 13-bit Vbat converted host-side", self.guide)

    def test_gs_obs_line_documented(self):
        self.assertIn("GSOBS", self.guide,
                      "guide should document the GSOBS observation line")


class TestValidationDocs(unittest.TestCase):
    """The guide must state the validation-only constraint (never tune in
    flight) and document the anomaly flags."""

    @classmethod
    def setUpClass(cls):
        cls.guide = _read_guide()

    def test_log_dont_tune_constraint_stated(self):
        self.assertIn("never writes a tuned curve back", self.guide)
        self.assertIn("log-don't-tune", self.guide)

    def test_gross_curve_error_flag(self):
        self.assertIn("gross_curve_error", self.guide)

    def test_frozen_die_temp_flag(self):
        self.assertIn("die_temp_frozen", self.guide)

    def test_gs_reference_loss_flag(self):
        self.assertIn("gs_reference_loss", self.guide)

    def test_gs_validation_module_cited(self):
        self.assertIn("gs_validation.py", self.guide)


if __name__ == "__main__":
    unittest.main()