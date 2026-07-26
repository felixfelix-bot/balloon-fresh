#!/usr/bin/env python3
"""
plot_full_characterization.py — Comprehensive plot showing ALL 14 phases
from sweep test data. Shows HF (2.4 GHz) and LF (868 MHz) side by side,
both LoRa and FLRC, with PA=ON and PA=OFF where available.

Usage:
    python3 plot_full_characterization.py data/sweep-rx-*.txt --out data/full_characterization.png
"""

import re
import sys
import os
from pathlib import Path
from collections import defaultdict

def parse_phase_results(filepath):
    """Parse PHASE_RESULT lines from a capture file."""
    results = []
    with open(filepath) as f:
        for line in f:
            m = re.match(
                r'PHASE_RESULT\s+(\d+)\s+(\S+)\s+path=(\S+)\s+pa=(\S+)\s+'
                r'rx=(\d+)\s+crc_err=(\d+)\s+per=([\d.]+)\s+'
                r'rssi_avg=([\d.\-]+)\s+expected=(\d+)',
                line.strip()
            )
            if m:
                results.append({
                    'idx': int(m.group(1)),
                    'name': m.group(2),
                    'path': m.group(3),
                    'pa': m.group(4),
                    'rx': int(m.group(5)),
                    'crc_err': int(m.group(6)),
                    'per': float(m.group(7)),
                    'rssi_avg': float(m.group(8)),
                    'expected': int(m.group(9)),
                })
    return results

def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    data_dir = Path('/home/c03rad0r/worktrees/balloon-range-tests/data')
    out_path = data_dir / 'full_characterization.png'

    # Parse all sweep-rx files
    all_results = []
    for f in sorted(data_dir.glob('sweep-rx-*.txt')):
        results = parse_phase_results(f)
        all_results.extend(results)
        print(f"Parsed {len(results)} phases from {f.name}")

    # Deduplicate: keep PA=ON and PA=OFF separately, prefer latest
    seen = {}
    for r in all_results:
        key = (r['idx'], r['pa'])
        seen[key] = r  # later files overwrite earlier

    # Group by band
    hf_phases = sorted([r for r in seen.values() if 'HF' in r['name']], key=lambda x: x['idx'])
    lf_phases = sorted([r for r in seen.values() if 'LF' in r['name']], key=lambda x: x['idx'])

    # Also get PA=OFF data for LF
    lf_pa_off = {}
    lf_pa_on = {}
    for r in seen.values():
        if 'LF' in r['name']:
            if r['pa'] == 'OFF':
                lf_pa_off[r['idx']] = r
            else:
                lf_pa_on[r['idx']] = r

    hf_pa_off = {}
    hf_pa_on = {}
    for r in seen.values():
        if 'HF' in r['name']:
            if r['pa'] == 'OFF':
                hf_pa_off[r['idx']] = r
            else:
                hf_pa_on[r['idx']] = r

    # 14 phase definitions
    phase_defs = [
        (0, "HF-LoRa-SF7", "HF", "LoRa", "SF7", 2440),
        (1, "HF-LoRa-SF9", "HF", "LoRa", "SF9", 2440),
        (2, "HF-LoRa-SF12", "HF", "LoRa", "SF12", 2440),
        (3, "HF-FLRC-2600", "HF", "FLRC", "2600k", 2440),
        (4, "HF-FLRC-1300", "HF", "FLRC", "1300k", 2440),
        (5, "HF-FLRC-650", "HF", "FLRC", "650k", 2440),
        (6, "HF-FLRC-325", "HF", "FLRC", "325k", 2440),
        (7, "LF-LoRa-SF7", "LF", "LoRa", "SF7", 868),
        (8, "LF-LoRa-SF9", "LF", "LoRa", "SF9", 868),
        (9, "LF-LoRa-SF12", "LF", "LoRa", "SF12", 868),
        (10, "LF-FLRC-2600", "LF", "FLRC", "2600k", 868),
        (11, "LF-FLRC-1300", "LF", "FLRC", "1300k", 868),
        (12, "LF-FLRC-650", "LF", "FLRC", "650k", 868),
        (13, "LF-FLRC-325", "LF", "FLRC", "325k", 868),
    ]

    # Build data arrays
    labels = []
    per_on = []
    rssi_on = []
    rx_on = []
    per_off = []
    rssi_off = []
    rx_off = []
    colors = []
    bands = []

    color_map = {
        ('HF', 'LoRa'): '#e74c3c',   # red
        ('HF', 'FLRC'): '#3498db',   # blue
        ('LF', 'LoRa'): '#2ecc71',   # green
        ('LF', 'FLRC'): '#f39c12',   # orange
    }

    for idx, name, band, mode, param, freq in phase_defs:
        labels.append(f"{band}\n{mode}\n{param}")

        r_on = hf_pa_on.get(idx) if band == 'HF' else lf_pa_on.get(idx)
        r_off = hf_pa_off.get(idx) if band == 'HF' else lf_pa_off.get(idx)

        per_on.append(r_on['per'] if r_on else None)
        rssi_on.append(r_on['rssi_avg'] if r_on else None)
        rx_on.append(r_on['rx'] if r_on else 0)

        per_off.append(r_off['per'] if r_off else None)
        rssi_off.append(r_off['rssi_avg'] if r_off else None)
        rx_off.append(r_off['rx'] if r_off else 0)

        colors.append(color_map.get((band, mode), '#999'))
        bands.append(band)

    # Create figure with 3 subplots
    fig, axes = plt.subplots(3, 1, figsize=(16, 14))
    fig.suptitle('LR2021 Full Characterization — All 14 Phases\n(1m indoor, same room)',
                 fontsize=14, fontweight='bold')

    x = np.arange(len(labels))
    width = 0.35

    # --- Plot 1: Packet Error Rate ---
    ax1 = axes[0]
    # Convert None to NaN for plotting
    per_on_arr = [p if p is not None else float('nan') for p in per_on]
    per_off_arr = [p if p is not None else float('nan') for p in per_off]

    bars_on = ax1.bar(x - width/2, per_on_arr, width, label='PA=ON',
                       color=[c if p is not None else '#ddd' for c, p in zip(colors, per_on)],
                       edgecolor='black', linewidth=0.5, alpha=0.8)
    bars_off = ax1.bar(x + width/2, per_off_arr, width, label='PA=OFF',
                        color=[c if p is not None else '#ddd' for c, p in zip(colors, per_off)],
                        edgecolor='black', linewidth=0.5, alpha=0.4, hatch='//')

    ax1.set_ylabel('Packet Error Rate (%)', fontsize=11)
    ax1.set_title('Packet Error Rate — PA=ON vs PA=OFF', fontsize=12)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=8)
    ax1.set_ylim(0, 105)
    ax1.axhline(y=50, color='gray', linestyle='--', alpha=0.3, label='50% threshold')
    ax1.legend(loc='upper right', fontsize=9)
    ax1.grid(True, alpha=0.2, axis='y')

    # Add value labels on bars
    for i, (v_on, v_off) in enumerate(zip(per_on, per_off)):
        if v_on is not None and v_on > 0:
            ax1.text(i - width/2, v_on + 1, f'{v_on:.0f}%', ha='center', va='bottom', fontsize=7)
        if v_off is not None and v_off > 0:
            ax1.text(i + width/2, v_off + 1, f'{v_off:.0f}%', ha='center', va='bottom', fontsize=7)

    # Mark missing data
    for i, (v_on, v_off) in enumerate(zip(per_on, per_off)):
        if v_on is None:
            ax1.text(i - width/2, 50, 'N/A', ha='center', va='center', fontsize=7, color='gray')
        if v_off is None:
            ax1.text(i + width/2, 50, 'N/A', ha='center', va='center', fontsize=7, color='gray')

    # --- Plot 2: RSSI ---
    ax2 = axes[1]
    rssi_on_arr = [r if r is not None and r != 0 else float('nan') for r in rssi_on]
    rssi_off_arr = [r if r is not None and r != 0 else float('nan') for r in rssi_off]

    bars_r_on = ax2.bar(x - width/2, rssi_on_arr, width, label='PA=ON',
                         color=[c if r is not None and r != 0 else '#ddd' for c, r in zip(colors, rssi_on)],
                         edgecolor='black', linewidth=0.5, alpha=0.8)
    bars_r_off = ax2.bar(x + width/2, rssi_off_arr, width, label='PA=OFF',
                          color=[c if r is not None and r != 0 else '#ddd' for c, r in zip(colors, rssi_off)],
                          edgecolor='black', linewidth=0.5, alpha=0.4, hatch='//')

    ax2.set_ylabel('RSSI (dBm)', fontsize=11)
    ax2.set_title('Average RSSI — PA=ON vs PA=OFF', fontsize=12)
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, fontsize=8)
    ax2.axhline(y=-80, color='red', linestyle='--', alpha=0.3, label='Sensitivity limit (~-80 dBm)')
    ax2.legend(loc='lower right', fontsize=9)
    ax2.grid(True, alpha=0.2, axis='y')

    # Add value labels
    for i, (v_on, v_off) in enumerate(zip(rssi_on, rssi_off)):
        if v_on is not None and v_on != 0:
            ax2.text(i - width/2, v_on + 1, f'{v_on:.0f}', ha='center', va='bottom', fontsize=7)
        if v_off is not None and v_off != 0:
            ax2.text(i + width/2, v_off + 1, f'{v_off:.0f}', ha='center', va='bottom', fontsize=7)

    # --- Plot 3: Packets Received ---
    ax3 = axes[2]
    rx_on_arr = [r if r is not None else 0 for r in rx_on]
    rx_off_arr = [r if r is not None else 0 for r in rx_off]

    # Also show expected as line
    expected_vals = [50, 50, 30, 200, 200, 200, 200, 50, 50, 20, 200, 200, 200, 200]

    bars_rx_on = ax3.bar(x - width/2, rx_on_arr, width, label='PA=ON (received)',
                          color=[c if r > 0 else '#ddd' for c, r in zip(colors, rx_on_arr)],
                          edgecolor='black', linewidth=0.5, alpha=0.8)
    bars_rx_off = ax3.bar(x + width/2, rx_off_arr, width, label='PA=OFF (received)',
                           color=[c if r > 0 else '#ddd' for c, r in zip(colors, rx_off_arr)],
                           edgecolor='black', linewidth=0.5, alpha=0.4, hatch='//')

    # Expected line
    ax3.plot(x, expected_vals, 'k--', alpha=0.3, linewidth=1, label='Expected')

    ax3.set_ylabel('Packets Received', fontsize=11)
    ax3.set_title('Packets Received vs Expected — PA=ON vs PA=OFF', fontsize=12)
    ax3.set_xticks(x)
    ax3.set_xticklabels(labels, fontsize=8)
    ax3.legend(loc='upper right', fontsize=9)
    ax3.grid(True, alpha=0.2, axis='y')

    # Add value labels
    for i, (v_on, v_off) in enumerate(zip(rx_on, rx_off)):
        if v_on and v_on > 0:
            ax3.text(i - width/2, v_on + 2, str(v_on), ha='center', va='bottom', fontsize=7)
        if v_off and v_off > 0:
            ax3.text(i + width/2, v_off + 2, str(v_off), ha='center', va='bottom', fontsize=7)

    # Add band separator
    for ax in axes:
        ax.axvline(x=6.5, color='gray', linestyle=':', alpha=0.5, linewidth=1.5)
        ax.text(3, ax.get_ylim()[1] * 0.95 if ax.get_ylim()[1] > 0 else 100,
                'HF (2.4 GHz)', ha='center', fontsize=10, fontweight='bold', alpha=0.5)
        ax.text(10, ax.get_ylim()[1] * 0.95 if ax.get_ylim()[1] > 0 else 100,
                'LF (868 MHz)', ha='center', fontsize=10, fontweight='bold', alpha=0.5)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    print(f"\nPlot saved: {out_path}")

    # Print summary table
    print(f"\n{'Idx':>3} {'Name':>16} {'PA':>4} {'RX':>5}/{'':>4} {'PER':>7} {'RSSI':>8}")
    print("-" * 55)
    for idx, name, band, mode, param, freq in phase_defs:
        r_on = hf_pa_on.get(idx) if band == 'HF' else lf_pa_on.get(idx)
        r_off = hf_pa_off.get(idx) if band == 'HF' else lf_pa_off.get(idx)
        if r_on:
            print(f"{idx:>3} {name:>16} {'ON':>4} {r_on['rx']:>5}/{r_on['expected']:<4} {r_on['per']:>6.1f}% {r_on['rssi_avg']:>7.1f}")
        if r_off:
            print(f"{idx:>3} {name:>16} {'OFF':>4} {r_off['rx']:>5}/{r_off['expected']:<4} {r_off['per']:>6.1f}% {r_off['rssi_avg']:>7.1f}")
        if not r_on and not r_off:
            print(f"{idx:>3} {name:>16} {'---':>4}  NO DATA")


if __name__ == '__main__':
    main()