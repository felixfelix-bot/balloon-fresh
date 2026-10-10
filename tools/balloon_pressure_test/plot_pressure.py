#!/usr/bin/env python3
"""
plot_pressure.py — Balloon leak-rate analysis (pre-stretch bench)

Reads the serial log from the ESP32-C3 pressure rig, computes the leak rate, and
renders a plot.  Two deliberate corrections over the first version are marked
'FIX' below; both were identified in the round-1 review of the pre-stretch rig:

  FIX 1 — leak rate is taken from a LEAST-SQUARES FIT over every sample, not from
          the two endpoints.  Endpoint-only rates let one bad first/last sample
          decide the verdict while the plotted trend line is never used.
  FIX 2 — the verdict is SIGN-AWARE and NOISE-AWARE.  A pressure *rise* is not a
          leak, and a rate smaller than the fit's own standard error is reported
          as INDETERMINATE instead of being scored as a pass/fail.

The `analyze()` function is pure Python (no numpy/matplotlib) so it is unit-tested
on the host by tools/balloon_pressure_test/test/test_plot_pressure.py.

Sensor class: the bench should use the SAME part the balloon flies — MS5611 — so
the calibration transfers.  BMP280 is 300–1100 mbar (ground only) and cannot
measure flight altitude.  Pass --sensor to record which part produced the log.

Usage:
    python3 plot_pressure.py <logfile> [--output plot.png] [--sensor auto|bmp280|ms5611] [--json]

Log format (one reading per line):
    [HH:MM:SS] pressure_mbar temperature_C
    [00:00:00] 1050.2 22.3
Lines starting with 'ERROR' or 'ESP' are skipped.
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

# Sensor class -> (pressure range mbar, whether it can fly)
SENSOR_CLASS = {
    "bmp280": ("300-1100 mbar (ground only)", False, "MS5611"),
    "ms5611": ("10-1200 mbar (full altitude)", True, None),
    "auto":   ("unknown — the rig auto-detects at boot", None, None),
}


def parse_log(filepath: str):
    """Parse serial log. Returns (hours, pressures, temperatures) as lists."""
    pattern = re.compile(r"\[(\d{2}):(\d{2}):(\d{2})\]\s+([\d.]+)\s+([\d.-]+)")
    hours, pressures, temps = [], [], []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("ERROR") or line.startswith("ESP"):
                continue
            m = pattern.match(line)
            if not m:
                continue
            h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
            hours.append(h + mi / 60.0 + s / 3600.0)
            pressures.append(float(m.group(4)))
            temps.append(float(m.group(5)))
    return hours, pressures, temps


def _ols_fit(hours, pressures):
    """Ordinary least squares p = a + b*t. Returns (slope_mbar_per_h, intercept,
    slope_std_error, residual_std_mbar, n)."""
    n = len(hours)
    if n < 2:
        return None
    mt = sum(hours) / n
    mp = sum(pressures) / n
    sxx = sum((t - mt) ** 2 for t in hours)
    if sxx == 0:
        return None
    sxy = sum((t - mt) * (p - mp) for t, p in zip(hours, pressures))
    slope = sxy / sxx
    intercept = mp - slope * mt
    resid = [p - (intercept + slope * t) for t, p in zip(hours, pressures)]
    sse = sum(r * r for r in resid)
    resid_std = math.sqrt(sse / n) if n > 0 else 0.0
    if n > 2:
        slope_se = math.sqrt((sse / (n - 2)) / sxx)
    else:
        slope_se = float("nan")
    return slope, intercept, slope_se, resid_std, n


def analyze(hours, pressures, temps, sensor="auto"):
    """Return a dict of derived quantities. Pure Python — unit-testable."""
    out = {"n": len(hours), "sensor": sensor}
    if len(hours) < 2:
        out["error"] = "insufficient data points"
        return out

    duration_h = hours[-1] - hours[0]
    out["duration_h"] = duration_h
    if duration_h <= 0:
        out["error"] = "zero duration"
        return out

    # ---- FIX 1: least-squares slope is the primary number -------------------
    fit = _ols_fit(hours, pressures)
    if fit is None:
        out["error"] = "degenerate time base"
        return out
    slope, _intercept, slope_se, resid_std, _n = fit
    leak_rate_fit = -slope                      # +ve == losing pressure
    out["slope_mbar_per_h"] = slope
    out["leak_rate_fit_mbar_per_h"] = leak_rate_fit
    out["leak_rate_se_mbar_per_h"] = slope_se
    out["residual_std_mbar"] = resid_std

    # endpoint rate kept only for comparison/back-compat
    out["leak_rate_endpoints_mbar_per_h"] = (pressures[0] - pressures[-1]) / duration_h

    # ---- temperature compensation (constant-volume approximation) -----------
    # Sealed balloon, constant volume, ideal gas: P/T = const, so P/T is the
    # leak-carrying quantity — it is invariant to temperature.  We therefore
    # normalise EVERY sample back to the start temperature and fit THAT, which
    # is the least-squares generalisation of the endpoint correction
    #     rate = (P_start - P_end * T_start / T_end) / duration
    #
    # The previous form, delta_P_temp = P_start * dT / T_start subtracted from
    # the fit, was derived from P_start and so (a) inverted the sign and
    # (b) produced negative — physically impossible — leak rates whenever the
    # balloon warmed up.  Because verdict() tests `rate < 0.5` first, a balloon
    # that leaked faster as it warmed could be waved through as flight-ready.
    #
    # Valid for a RIGID (constant-volume) envelope ONLY.  A pre-stretch
    # envelope changes volume, so this is reported, not silently trusted.
    kelvin = [t + 273.15 for t in temps]
    t_ref = kelvin[0]
    p_norm = [p * (t_ref / tk) if tk else p for p, tk in zip(pressures, kelvin)]
    fit_norm = _ols_fit(hours, p_norm)
    slope_norm = fit_norm[0] if fit_norm is not None else float("nan")
    leak_rate_temp_comp = -slope_norm
    out["delta_p_temp_mbar"] = (
        pressures[-1] - pressures[-1] * (t_ref / kelvin[-1]) if kelvin[-1] else 0.0
    )
    out["temp_correction_mbar_per_h"] = (
        leak_rate_fit - leak_rate_temp_comp if slope_norm == slope_norm else 0.0
    )
    out["leak_rate_temp_comp_mbar_per_h"] = leak_rate_temp_comp

    # Noise floor: the smallest rate the log can resolve.  max of the fit's
    # slope standard error and the residual σ expressed as a rate over the
    # observation span (the latter is the more physical, conservative bound).
    from_resid = resid_std / duration_h
    from_se = slope_se if slope_se == slope_se else 0.0   # NaN-safe
    out["noise_floor_mbar_per_h"] = max(from_resid, from_se)
    # Verdict is taken from the temperature-COMPENSATED rate: judging the raw
    # fit lets a warm-up mask a real leak.  With a constant-temperature log the
    # normalised fit is identical to the raw fit, so this is a no-op there.
    out["verdict"] = verdict(leak_rate_temp_comp, out["noise_floor_mbar_per_h"])

    rng, can_fly, replacement = SENSOR_CLASS.get(sensor, SENSOR_CLASS["auto"])
    out["sensor_range"] = rng
    out["sensor_can_fly"] = can_fly
    out["sensor_replacement"] = replacement
    return out


def verdict(leak_rate, noise_floor):
    """Sign- and noise-aware verdict (FIX 2).  Noise floor is checked FIRST, so a
    tiny drift inside the noise band is reported as INDETERMINATE rather than
    being mislabelled a 'rise' or scored as a pass."""
    if noise_floor > 0 and abs(leak_rate) <= noise_floor:
        return "INDETERMINATE — rate is at/below the fit noise floor; extend the run"
    if leak_rate < 0:
        return "PRESSURE RISE — not a leak (check cooling / gas ingress / sensor)"
    if leak_rate < 0.5:
        return "Very good — flight ready"
    if leak_rate < 2.0:
        return "OK — flight ready with reserve"
    if leak_rate < 5.0:
        return "Marginal — restricted use only"
    return "Poor — reject balloon"


def plot_data(hours, pressures, temps, output_path: str):
    """Render the pressure/temperature plot. Requires numpy + matplotlib."""
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    ax1.plot(hours, pressures, "b-", linewidth=1.5, label="Pressure")
    if len(hours) > 2:
        z = np.polyfit(hours, pressures, 1)
        fit = np.polyval(z, hours)
        ax1.plot(hours, fit, "r--", alpha=0.7, label=f"Fit: {-z[0]:.3f} mbar/h leak")
    ax1.set_ylabel("Pressure (mbar)")
    ax1.set_title("Balloon Pressure Test")
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax2.plot(hours, temps, "g-", linewidth=1.5, label="Temperature")
    ax2.set_xlabel("Time (hours)")
    ax2.set_ylabel("Temperature (°C)")
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    print(f"Plot saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Balloon leak rate analysis")
    parser.add_argument("logfile", help="Path to serial log file")
    parser.add_argument("--output", "-o", default="pressure_plot.png",
                        help="Output plot filename (default: pressure_plot.png)")
    parser.add_argument("--sensor", choices=list(SENSOR_CLASS), default="auto",
                        help="Sensor class that produced the log (default: auto)")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    parser.add_argument("--no-plot", action="store_true", help="Skip plot rendering")
    args = parser.parse_args()

    if not Path(args.logfile).exists():
        print(f"Error: file not found: {args.logfile}", file=sys.stderr)
        sys.exit(1)

    hours, pressures, temps = parse_log(args.logfile)
    res = analyze(hours, pressures, temps, sensor=args.sensor)
    if "error" in res:
        print(f"Error: {res['error']}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"Data points: {res['n']}")
        print(f"Duration:    {res['duration_h']:.2f} hours")
        print(f"Sensor:      {res['sensor']}  [{res['sensor_range']}]")
        if res.get("sensor_can_fly") is False:
            print(f"             ⚠ ground-only part — bench calibration does NOT transfer "
                  f"to the flight board (use {res['sensor_replacement']})")
        print()
        print(f"Leak rate (least-squares fit, PRIMARY): {res['leak_rate_fit_mbar_per_h']:.3f} mbar/h"
              f"  ±{res['leak_rate_se_mbar_per_h']:.3f} (1σ)")
        print(f"Leak rate (endpoints, for comparison):  {res['leak_rate_endpoints_mbar_per_h']:.3f} mbar/h")
        print(f"Fit residual σ (noise floor):           {res['residual_std_mbar']:.3f} mbar")
        print(f"Noise floor (smallest resolvable rate): {res['noise_floor_mbar_per_h']:.3f} mbar/h")
        print(f"Temp correction (const-V approx):       {res['temp_correction_mbar_per_h']:.3f} mbar/h")
        print()
        print(f"Verdict: {res['verdict']}")

    if not args.no_plot:
        try:
            plot_data(hours, pressures, temps, args.output)
        except ImportError as e:
            print(f"(plot skipped: {e})", file=sys.stderr)


if __name__ == "__main__":
    main()
