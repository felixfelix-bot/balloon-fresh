#!/usr/bin/env python3
"""
plot_range_sweep.py — Generate range-vs-rate tradeoff plots from test CSVs

Reads CSV files produced by rx_range_logger.py, generates:
  1. RSSI vs distance (per bitrate)
  2. Packet loss vs distance (per bitrate)
  3. Throughput vs distance (per bitrate)

Usage:
    python3 plot_range_sweep.py data/range_test_*.csv --bitrate 2600 --distance 1m,5m,10m,50m,100m
    python3 plot_range_sweep.py data/ --auto  # auto-group by bitrate field in CSV

Output: data/plots/*.png
"""

import argparse
import glob
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

def parse_args():
    parser = argparse.ArgumentParser(description='Plot LR2021 FLRC range test results')
    parser.add_argument('inputs', nargs='+', help='CSV files or directories')
    parser.add_argument('--out', default='data/plots', help='Output directory for PNGs')
    parser.add_argument('--bitrate', type=int, default=0, help='Filter by bitrate kbps (0=all)')
    parser.add_argument('--auto', action='store_true', help='Auto-group files by bitrate from CSV data')
    return parser.parse_args()


def read_csv(path):
    """Read range test CSV, return list of RESULT dicts"""
    import csv
    results = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['type'] != 'RESULT':
                continue
            try:
                results.append({
                    'rssi_avg': float(row['rssi_avg']) if row['rssi_avg'] else None,
                    'rssi_min': int(row['rssi_min']) if row['rssi_min'] else None,
                    'per': float(row['per']) if row['per'] else None,
                    'throughput_kbps': float(row['throughput_kbps']) if row['throughput_kbps'] else None,
                    'bitrate': int(row['bitrate']) if row['bitrate'] else None,
                    'rx': int(row['rx']) if row['rx'] else None,
                    'unique': int(row['unique']) if row['unique'] else None,
                })
            except (ValueError, KeyError):
                continue
    return results


def aggregate(results):
    """Average across all RESULT lines for a single test point"""
    if not results:
        return None
    return {
        'rssi_avg': sum(r['rssi_avg'] for r in results if r['rssi_avg'] is not None) /
                    max(1, sum(1 for r in results if r['rssi_avg'] is not None)),
        'per': sum(r['per'] for r in results if r['per'] is not None) /
               max(1, sum(1 for r in results if r['per'] is not None)),
        'throughput': sum(r['throughput_kbps'] for r in results if r['throughput_kbps'] is not None) /
                      max(1, sum(1 for r in results if r['throughput_kbps'] is not None)),
    }


def main():
    args = parse_args()

    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print("ERROR: matplotlib not installed. pip install matplotlib")
        sys.exit(1)

    # Gather CSV files
    csv_files = []
    for inp in args.inputs:
        if os.path.isdir(inp):
            csv_files.extend(glob.glob(os.path.join(inp, 'range_test_*.csv')))
        else:
            csv_files.append(inp)

    if not csv_files:
        print("No CSV files found.")
        sys.exit(1)

    # Group by bitrate
    by_bitrate = defaultdict(list)
    for f in csv_files:
        results = read_csv(f)
        for r in results:
            br = r['bitrate'] or args.bitrate
            if args.bitrate and br != args.bitrate:
                continue
            by_bitrate[br].append(r)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Plot RSSI vs test number (proxy for distance if no GPS data)
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 12))

    colors = {2600: '#e74c3c', 1300: '#3498db', 650: '#2ecc71', 325: '#f39c12'}

    for br in sorted(by_bitrate.keys()):
        data = by_bitrate[br]
        if not data:
            continue
        x = range(len(data))
        color = colors.get(br, '#999')

        rssi_vals = [r['rssi_avg'] for r in data if r['rssi_avg'] is not None]
        per_vals = [r['per'] for r in data if r['per'] is not None]
        tput_vals = [r['throughput_kbps'] for r in data if r['throughput_kbps'] is not None]

        ax1.plot(range(len(rssi_vals)), rssi_vals, '.-', label=f'{br} kbps', color=color)
        ax2.plot(range(len(per_vals)), per_vals, '.-', label=f'{br} kbps', color=color)
        ax3.plot(range(len(tput_vals)), tput_vals, '.-', label=f'{br} kbps', color=color)

    ax1.set_ylabel('RSSI (dBm)')
    ax1.set_title('RSSI vs Test Point')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.set_ylabel('Packet Error Rate')
    ax2.set_title('PER vs Test Point')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    ax3.set_ylabel('Throughput (kbps)')
    ax3.set_xlabel('Test Point Index')
    ax3.set_title('Throughput vs Test Point')
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    plot_path = out_dir / 'range_sweep.png'
    plt.savefig(plot_path, dpi=150)
    print(f"Plot saved: {plot_path}")

    # Print summary table
    print(f"\n{'Bitrate':>8} {'Avg RSSI':>10} {'Avg PER':>10} {'Avg Tput':>10} {'Points':>7}")
    print("-" * 50)
    for br in sorted(by_bitrate.keys()):
        agg = aggregate(by_bitrate[br])
        if agg:
            print(f"{br:>7}k {agg['rssi_avg']:>9.1f}dBm {agg['per']*100:>9.1f}% "
                  f"{agg['throughput']:>9.0f}kbps {len(by_bitrate[br]):>7}")


if __name__ == '__main__':
    main()
