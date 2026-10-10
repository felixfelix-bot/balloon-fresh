#!/usr/bin/env python3
"""
test_plot_pressure.py — host unit test for the leak-rate analysis (pure Python).

Run:  python3 tools/balloon_pressure_test/test/test_plot_pressure.py
      (or: make -C tools/balloon_pressure_test/test check-analysis)

No numpy/matplotlib required — it exercises analyze() only, with synthetic logs.
No hardware and no real balloon data are involved.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import plot_pressure as pp  # noqa: E402

FAIL = 0
PASS = 0


def expect(cond, msg):
    global FAIL, PASS
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {msg}")


def mk(n, p0, dp_per_h, dt_h=0.5, t0=20.0):
    """n samples, linear pressure, constant temperature."""
    hours = [i * dt_h for i in range(n)]
    pressures = [p0 + dp_per_h * h for h in hours]
    temps = [t0] * n
    return hours, pressures, temps


def test_clean_leak():
    # 1000 -> 990 mbar over 10 h = 1.0 mbar/h leak (rate == -dp_per_h)
    h, p, t = mk(21, 1000.0, -1.0, dt_h=0.5)
    r = pp.analyze(h, p, t, sensor="ms5611")
    expect(abs(r["leak_rate_fit_mbar_per_h"] - 1.0) < 1e-6, "fit recovers 1.0 mbar/h leak")
    expect(r["verdict"].startswith("OK"), "1.0 mbar/h -> OK verdict")


def test_endpoint_outlier_does_not_decide():
    # A single bad loud first sample must not flip the verdict now that the fit
    # (not the endpoints) is the primary number.
    h, p, t = mk(21, 1000.0, -0.2, dt_h=0.5)
    p_bad = list(p)
    p_bad[0] += 8.0                       # one spurious high first sample
    r_fit = pp.analyze(h, p_bad, t, sensor="ms5611")
    r_end = r_fit["leak_rate_endpoints_mbar_per_h"]
    expect(r_fit["leak_rate_fit_mbar_per_h"] < 0.5,
           "fit rate stays <0.5 despite an endpoint outlier")
    expect(abs(r_end) > 0.5,
           "endpoint rate is materially worse (shows why the fit is used)")


def test_pressure_rise_is_not_a_leak():
    h, p, t = mk(21, 1000.0, +0.3, dt_h=0.5)   # pressure rising
    r = pp.analyze(h, p, t, sensor="ms5611")
    expect(r["leak_rate_fit_mbar_per_h"] < 0, "rise gives a negative leak rate")
    expect("RISE" in r["verdict"], "rise reported as PRESSURE RISE, not a pass/fail")


def test_noise_floor_flags_indeterminate():
    # Tiny alternating noise, no trend: the rate is inside the fit noise floor.
    n = 60
    hours = [i * 0.1 for i in range(n)]
    pressures = [1000.0 + (0.05 if i % 2 else -0.05) for i in range(n)]
    temps = [20.0] * n
    r = pp.analyze(hours, pressures, temps, sensor="ms5611")
    expect(abs(r["leak_rate_fit_mbar_per_h"]) <= r["noise_floor_mbar_per_h"] + 1e-12,
           "noise-only log has |rate| <= 1σ")
    expect("INDETERMINATE" in r["verdict"], "noise-only log -> INDETERMINATE")


def test_sensor_class_warning():
    h, p, t = mk(21, 1000.0, -0.1, dt_h=0.5)
    r_bmp = pp.analyze(h, p, t, sensor="bmp280")
    expect(r_bmp["sensor_can_fly"] is False, "BMP280 flagged as ground-only")
    expect(r_bmp["sensor_replacement"] == "MS5611", "BMP280 suggests MS5611 for transfer")
    r_ms = pp.analyze(h, p, t, sensor="ms5611")
    expect(r_ms["sensor_can_fly"] is True, "MS5611 flagged as flight-capable")


def test_insufficient_data():
    r = pp.analyze([0.0], [1000.0], [20.0])
    expect("error" in r, "single sample -> error")


def main():
    test_clean_leak()
    test_endpoint_outlier_does_not_decide()
    test_pressure_rise_is_not_a_leak()
    test_noise_floor_flags_indeterminate()
    test_sensor_class_warning()
    test_insufficient_data()
    print(f"test_plot_pressure: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
