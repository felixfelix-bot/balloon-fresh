#!/usr/bin/env python3
"""Host tests for gs_validation.py — log-don't-tune ground-station validation.

The GS compares the measured frequency offset against the cryo-predicted
offset (from the balloon's reported die temp + stored {k, T0} curve) in real
time, and flags anomalies. It NEVER writes a tuned curve back to the balloon.

Run:  python3 -m pytest tools/test_gs_validation.py -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gs_validation as gv  # noqa: E402


class CryoPredictTests(unittest.TestCase):
    """offset = k * (T - T0)."""

    def test_basic_positive_slope(self):
        # k=+2.0 Hz/°C, T0=25°C, T=35°C -> 2*(35-25)=20 Hz
        self.assertAlmostEqual(gv.cryo_predict_offset(35.0, 2.0, 25.0), 20.0)

    def test_zero_at_t0(self):
        self.assertAlmostEqual(gv.cryo_predict_offset(25.0, 2.0, 25.0), 0.0)

    def test_negative_slope(self):
        # k=-1.5 Hz/°C, T0=20°C, T=10°C -> -1.5*(10-20)=+15 Hz
        self.assertAlmostEqual(gv.cryo_predict_offset(10.0, -1.5, 20.0), 15.0)

    def test_cold_side_negative_offset(self):
        # k=+2.0, T0=25, T=5 -> 2*(5-25)=-40
        self.assertAlmostEqual(gv.cryo_predict_offset(5.0, 2.0, 25.0), -40.0)


class GsValidatorTests(unittest.TestCase):
    """Real-time anomaly flagging (log-don't-tune)."""

    def _mk(self, **kw):
        defaults = dict(k_hz_per_c=2.0, t0_c=25.0, curve_ver=3,
                        die_temp_range=(-40.0, 125.0),
                        offset_tol_hz=500.0,
                        frozen_die_temp_delta_c=0.5,
                        frozen_samples=3)
        defaults.update(kw)
        return gv.GsValidator(**defaults)

    def test_ok_sample_no_flags(self):
        v = self._mk()
        # T=35 -> predicted 20 Hz; measured 25 Hz (within 500 Hz tol)
        flags = v.validate_sample(measured_offset_hz=25.0, die_temp_c=35.0)
        self.assertFalse(any(v for k, v in flags.items()
                             if k != "predicted_offset_hz"))
        self.assertAlmostEqual(flags["predicted_offset_hz"], 20.0)

    def test_die_temp_out_of_range(self):
        v = self._mk()
        flags = v.validate_sample(measured_offset_hz=0.0, die_temp_c=200.0)
        self.assertTrue(flags["die_temp_out_of_range"])

    def test_die_temp_frozen_while_offset_changes(self):
        v = self._mk()
        # 3 samples: die temp stuck at 35.0 while measured offset moves
        for off in (25.0, 100.0, 300.0):
            flags = v.validate_sample(measured_offset_hz=off, die_temp_c=35.0)
        self.assertTrue(flags["die_temp_frozen"])

    def test_die_temp_not_frozen_when_temp_moves(self):
        v = self._mk()
        for t, off in ((35.0, 25.0), (36.0, 100.0), (37.0, 300.0)):
            flags = v.validate_sample(measured_offset_hz=off, die_temp_c=t)
        self.assertFalse(flags["die_temp_frozen"])

    def test_gross_curve_error(self):
        v = self._mk(offset_tol_hz=50.0)
        # T=35 -> predicted 20 Hz; measured 5000 Hz -> gross error
        flags = v.validate_sample(measured_offset_hz=5000.0, die_temp_c=35.0)
        self.assertTrue(flags["gross_curve_error"])

    def test_gs_reference_loss(self):
        v = self._mk()
        flags = v.validate_sample(measured_offset_hz=25.0, die_temp_c=35.0,
                                  gs_ref_stable=False)
        self.assertTrue(flags["gs_reference_loss"])

    def test_validate_series_summary(self):
        v = self._mk()
        samples = [
            {"measured_offset_hz": 25.0, "die_temp_c": 35.0},
            {"measured_offset_hz": 25.0, "die_temp_c": 35.0},
            {"measured_offset_hz": 25.0, "die_temp_c": 35.0},
        ]
        out = v.validate_series(samples)
        self.assertEqual(len(out["samples"]), 3)
        self.assertIn("anomaly_count", out)
        self.assertEqual(out["anomaly_count"], 0)

    def test_validate_series_counts_anomalies(self):
        v = self._mk(offset_tol_hz=50.0)
        samples = [
            {"measured_offset_hz": 25.0, "die_temp_c": 35.0},
            {"measured_offset_hz": 5000.0, "die_temp_c": 35.0},  # gross error
        ]
        out = v.validate_series(samples)
        self.assertEqual(out["anomaly_count"], 1)


class FixedPointConversionTests(unittest.TestCase):
    """k/T0 are logged as fixed-point ints (mHz/°C, m°C); host converts."""

    def test_k_fixed_point_to_float(self):
        # k=2000 mHz/°C -> 2.0 Hz/°C
        self.assertAlmostEqual(gv.k_fixed_to_float(2000), 2.0)

    def test_t0_fixed_point_to_float(self):
        # T0=25000 m°C -> 25.0 °C
        self.assertAlmostEqual(gv.t0_fixed_to_float(25000), 25.0)

    def test_float_to_k_fixed_point(self):
        self.assertEqual(gv.k_float_to_fixed(2.0), 2000)

    def test_float_to_t0_fixed_point(self):
        self.assertEqual(gv.t0_float_to_fixed(25.0), 25000)


if __name__ == "__main__":
    unittest.main()
