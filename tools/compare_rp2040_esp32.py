#!/usr/bin/env python3
"""compare_rp2040_esp32.py — RP2040 vs ESP32-C3 LR2021 throughput comparison."""
import argparse, csv, re, sys
from pathlib import Path
from datetime import datetime

RP2040_BASELINE = {"spi_freq_mhz": 10.40, "throughput_kbps": 1760, "per_pct": 0.0, "rssi_dbm": -60}

def parse_esp32_log(logfile):
    results = []
    for line in logfile:
        parts = {}
        for token in line.strip().split():
            if "=" in token:
                k, v = token.split("=", 1)
                try: parts[k] = float(v) if "." in v else int(v)
                except ValueError: parts[k] = v
        if "throughput_kbps" in parts or "tput_kbps" in parts:
            results.append(parts)
    return results

def main():
    p = argparse.ArgumentParser(description="RP2040 vs ESP32-C3 throughput")
    p.add_argument("--esp32-log", help="ESP32 serial log")
    p.add_argument("--esp32-throughput", type=int, help="Manual kbps")
    p.add_argument("--esp32-spi-mhz", type=float, default=20.0)
    p.add_argument("--rp2040-throughput", type=int, default=1760)
    p.add_argument("--rp2040-spi-mhz", type=float, default=10.40)
    p.add_argument("--output", default="data/")
    args = p.parse_args()

    rp2040 = {"throughput_kbps": args.rp2040_throughput, "spi_freq_mhz": args.rp2040_spi_mhz}
    esp32 = {"spi_freq_mhz": args.esp32_spi_mhz}

    if args.esp32_log:
        with open(args.esp32_log) as f:
            results = parse_esp32_log(f)
        if results:
            last = results[-1]
            esp32["throughput_kbps"] = last.get("throughput_kbps", last.get("tput_kbps", 0))
            esp32["per_pct"] = last.get("per", 0)
            esp32["rssi_dbm"] = last.get("rssi_avg", -127)
    elif args.esp32_throughput:
        esp32["throughput_kbps"] = args.esp32_throughput
    else:
        print("ERROR: --esp32-log or --esp32-throughput required"); sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    csv_path = out / f"mcu_comparison_{ts}.csv"

    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "rp2040", "esp32_c3", "delta_pct"])
        for key in ["throughput_kbps", "spi_freq_mhz"]:
            rp = rp2040.get(key, 0); es = esp32.get(key, 0)
            delta = ((es - rp) / rp * 100) if rp else 0
            w.writerow([key, rp, es, f"{delta:.1f}%"])

    rp_t = rp2040["throughput_kbps"]
    es_t = esp32.get("throughput_kbps", 0)
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, figsize=(8, 5))
        mcus = ["RP2040", "ESP32-C3"]
        bars = ax.bar(mcus, [rp_t, es_t], color=["#2196F3", "#FF9800"])
        ax.set_ylabel("Throughput (kbps)")
        ax.set_title("LR2021 FLRC: RP2040 vs ESP32-C3")
        for bar, val in zip(bars, [rp_t, es_t]):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 20,
                    f"{val}", ha="center", va="bottom", fontweight="bold")
        ax.set_ylim(0, max(rp_t, es_t) * 1.3)
        plt.tight_layout()
        png_path = out / f"mcu_comparison_{ts}.png"
        plt.savefig(png_path, dpi=150, bbox_inches="tight")
        print(f"Plot: {png_path}")
    except ImportError:
        print("matplotlib not installed — CSV only")

    print(f"CSV: {csv_path}")
    winner = "RP2040" if rp_t > es_t else "ESP32-C3"
    margin = abs(rp_t - es_t) / max(rp_t, es_t) * 100
    print(f"\nRP2040: {rp_t} kbps @ {rp2040['spi_freq_mhz']:.1f} MHz")
    print(f"ESP32:  {es_t} kbps @ {esp32['spi_freq_mhz']:.1f} MHz")
    print(f"Winner: {winner} ({margin:.1f}% faster)")

if __name__ == "__main__":
    main()
