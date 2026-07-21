#!/usr/bin/env python3
"""
plot_pressure.py — Balloon leak rate analysis

Reads serial log from BMP280 pressure test rig, calculates temperature-compensated
leak rate, and generates plots.

Usage:
    python3 plot_pressure.py <logfile> [--output plot.png]

Log format (one reading per line):
    [HH:MM:SS] pressure_mbar temperature_C
    [00:00:00] 1050.2 22.3
    [00:00:30] 1050.1 22.3

Lines starting with 'ERROR' or 'ESP' are skipped.
"""

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt


def parse_log(filepath: str):
    """Parse serial log file. Returns (hours, pressures, temperatures)."""
    pattern = re.compile(
        r"\[(\d{2}):(\d{2}):(\d{2})\]\s+([\d.]+)\s+([\d.-]+)"
    )
    hours = []
    pressures = []
    temps = []

    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("ERROR") or line.startswith("ESP"):
                continue
            m = pattern.match(line)
            if not m:
                continue
            h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
            total_hours = h + mi / 60.0 + s / 3600.0
            p = float(m.group(4))
            t = float(m.group(5))
            hours.append(total_hours)
            pressures.append(p)
            temps.append(t)

    return np.array(hours), np.array(pressures), np.array(temps)


def calc_leak_rate(hours, pressures, temps):
    """Calculate temperature-compensated leak rate in mbar/h."""
    if len(hours) < 2:
        return None, None, None

    p_start = pressures[0]
    p_end = pressures[-1]
    t_start = temps[0] + 273.15  # Kelvin
    t_end = temps[-1] + 273.15
    duration_h = hours[-1] - hours[0]

    if duration_h == 0:
        return None, None, None

    # Raw leak rate (no temp compensation)
    raw_rate = (p_start - p_end) / duration_h

    # Temperature compensation: ΔP_temp = P_start × (T_end - T_start) / T_start
    delta_p_temp = p_start * (t_end - t_start) / t_start

    # Compensated leak rate
    compensated_rate = (p_start - p_end - delta_p_temp) / duration_h

    return raw_rate, compensated_rate, duration_h


def verdict(rate: float) -> str:
    """Return verdict string based on leak rate."""
    if rate < 0.5:
        return "Very good — flight ready"
    elif rate < 2.0:
        return "OK — flight ready with reserve"
    elif rate < 5.0:
        return "Marginal — restricted use only"
    else:
        return "Poor — reject balloon"


def plot_data(hours, pressures, temps, output_path: str):
    """Generate and save pressure/temperature plot."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    # Pressure plot
    ax1.plot(hours, pressures, "b-", linewidth=1.5, label="Pressure")
    # Linear fit
    if len(hours) > 2:
        z = np.polyfit(hours, pressures, 1)
        fit = np.polyval(z, hours)
        ax1.plot(hours, fit, "r--", alpha=0.7, label=f"Trend: {z[0]:.2f} mbar/h")
    ax1.set_ylabel("Pressure (mbar)")
    ax1.set_title("Balloon Pressure Test")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Temperature plot
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
    args = parser.parse_args()

    if not Path(args.logfile).exists():
        print(f"Error: file not found: {args.logfile}", file=sys.stderr)
        sys.exit(1)

    hours, pressures, temps = parse_log(args.logfile)

    if len(hours) == 0:
        print("Error: no valid data points found in log", file=sys.stderr)
        sys.exit(1)

    print(f"Data points: {len(hours)}")
    print(f"Duration: {hours[-1]:.2f} hours")
    print(f"Start: {pressures[0]:.1f} mbar, {temps[0]:.1f}°C")
    print(f"End:   {pressures[-1]:.1f} mbar, {temps[-1]:.1f}°C")
    print()

    raw_rate, comp_rate, duration = calc_leak_rate(hours, pressures, temps)

    if raw_rate is None:
        print("Insufficient data for leak rate calculation", file=sys.stderr)
        sys.exit(1)

    print(f"Raw leak rate:         {raw_rate:.3f} mbar/h")
    print(f"Temp-compensated rate: {comp_rate:.3f} mbar/h")
    print(f"Temp correction:       {raw_rate - comp_rate:.3f} mbar/h")
    print()
    print(f"Verdict: {verdict(abs(comp_rate))}")

    plot_data(hours, pressures, temps, args.output)


if __name__ == "__main__":
    main()