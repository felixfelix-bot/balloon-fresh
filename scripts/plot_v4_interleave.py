#!/usr/bin/env python3
"""Analyze V4 interleave sweep data and generate proof plots.

Parses PHASE_RESULT lines from RX capture log.
Generates: PER vs size, throughput vs size, reception heatmap.
"""
import re
import sys
import glob
import os
from collections import defaultdict

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

def parse_phase_result(line):
    """Parse a PHASE_RESULT line into structured data."""
    # PHASE_RESULT 31 LF-LoRa-SF7-255 pktSize=255 rx=0 unique=0 lost=7 per=100.0 rssi_avg=0 rssi_min=0 crc_err=0 garbage=0 tx_lat=0.00000 tx_lon=0.00000 sats=0 fix=0 utc=0 tx_fw=none rx_fw=unknown
    m = re.match(
        r'PHASE_RESULT\s+(\d+)\s+(\S+)\s+pktSize=(\d+)\s+rx=(\d+)\s+unique=(\d+)'
        r'\s+lost=(\d+)\s+per=([\d.]+)\s+rssi_avg=(-?\d+)\s+rssi_min=(-?\d+)'
        r'\s+crc_err=(\d+)\s+garbage=(\d+)',
        line
    )
    if not m:
        return None
    d = {
        'phase_idx': int(m.group(1)),
        'phase_name': m.group(2),
        'pktSize': int(m.group(3)),
        'rx': int(m.group(4)),
        'unique': int(m.group(5)),
        'lost': int(m.group(6)),
        'per': float(m.group(7)),
        'rssi_avg': int(m.group(8)),
        'rssi_min': int(m.group(9)),
        'crc_err': int(m.group(10)),
        'garbage': int(m.group(11)),
    }
    # Parse mode/band/sf from name (e.g. HF-LoRa-SF7-32, LF-FLRC-1300-64)
    parts = d['phase_name'].rsplit('-', 1)  # split off size suffix
    prefix = parts[0]
    sub = prefix.split('-')
    d['band'] = sub[0]  # HF or LF
    d['mode'] = sub[1]  # LoRa or FLRC
    d['sf_bw'] = sub[2] if len(sub) > 2 else '?'  # SF7, SF9, SF12, 1300, 260, 86
    return d

def parse_pkd_lines(lines):
    """Count PKT lines per phase for BER/reception analysis."""
    pkt_counts = defaultdict(int)
    for line in lines:
        m = re.match(r'PKT\s+seq=(\d+)\s+rssi=(-?\d+)\s+phase=(\d+)\s+pktSize=(\d+)', line)
        if m:
            phase = int(m.group(3))
            pktSize = int(m.group(4))
            pkt_counts[(phase, pktSize)] += 1
    return pkt_counts

def load_data(filepath):
    """Load and parse capture file."""
    with open(filepath) as f:
        lines = f.readlines()
    
    phases = []
    pkts = []
    for line in lines:
        if 'PHASE_RESULT' in line:
            d = parse_phase_result(line.strip())
            if d:
                phases.append(d)
        elif line.startswith('PKT '):
            pkts.append(line.strip())
    
    return phases, pkts

def plot_per_vs_size(phases, outdir):
    """Plot PER vs packet size for each mode."""
    if not phases:
        print("No PHASE_RESULT data to plot")
        return
    
    # Group by mode (band-mode-sf_bw)
    groups = defaultdict(list)
    for p in phases:
        key = f"{p['band']}-{p['mode']}-{p['sf_bw']}"
        groups[key].append(p)
    
    fig, ax = plt.subplots(figsize=(14, 8))
    
    sizes = [32, 64, 128, 255]
    colors = plt.cm.tab10(np.linspace(0, 1, len(groups)))
    
    for (key, data), color in zip(sorted(groups.items()), colors):
        x_vals = []
        y_vals = []
        for s in sizes:
            matches = [d for d in data if d['pktSize'] == s]
            if matches:
                avg_per = np.mean([d['per'] for d in matches])
                x_vals.append(s)
                y_vals.append(avg_per)
        
        if x_vals:
            marker = 's' if 'FLRC' in key else 'o'
            ls = '--' if 'LF' in key else '-'
            ax.plot(x_vals, y_vals, marker=marker, linestyle=ls, linewidth=2,
                    markersize=8, label=key, color=color)
    
    ax.set_xlabel('Packet Size (bytes)', fontsize=14)
    ax.set_ylabel('Packet Error Rate (%)', fontsize=14)
    ax.set_title('V4 Interleave Sweep: PER vs Packet Size (Bench Test)', fontsize=16)
    ax.set_xticks(sizes)
    ax.set_xticklabels([f'{s}B' for s in sizes])
    ax.set_ylim(-5, 105)
    ax.axhline(y=50, color='gray', linestyle=':', alpha=0.5, label='50% threshold')
    ax.legend(fontsize=10, ncol=2, loc='upper left')
    ax.grid(True, alpha=0.3)
    
    outpath = os.path.join(outdir, 'per_vs_size.png')
    fig.savefig(outpath, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved: {outpath}")

def plot_reception_heatmap(phases, outdir):
    """Heatmap: modes (rows) × sizes (cols), color = rx count."""
    if not phases:
        return
    
    # Get unique mode names preserving order
    mode_order = []
    seen = set()
    for p in phases:
        key = f"{p['band']}-{p['mode']}-{p['sf_bw']}"
        if key not in seen:
            mode_order.append(key)
            seen.add(key)
    
    sizes = [32, 64, 128, 255]
    matrix = np.full((len(mode_order), len(sizes)), np.nan)
    
    for i, mode in enumerate(mode_order):
        for j, sz in enumerate(sizes):
            for p in phases:
                key = f"{p['band']}-{p['mode']}-{p['sf_bw']}"
                if key == mode and p['pktSize'] == sz:
                    matrix[i, j] = p['unique']
                    break
    
    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(matrix, aspect='auto', cmap='RdYlGn', interpolation='nearest')
    
    ax.set_xticks(range(len(sizes)))
    ax.set_xticklabels([f'{s}B' for s in sizes])
    ax.set_yticks(range(len(mode_order)))
    ax.set_yticklabels(mode_order, fontsize=10)
    
    # Add count annotations
    for i in range(len(mode_order)):
        for j in range(len(sizes)):
            val = matrix[i, j]
            if not np.isnan(val):
                color = 'white' if val < matrix[~np.isnan(matrix)].max() / 2 else 'black'
                ax.text(j, i, f'{int(val)}', ha='center', va='center', color=color, fontsize=12, fontweight='bold')
            else:
                ax.text(j, i, 'SKIP', ha='center', va='center', color='gray', fontsize=9)
    
    ax.set_title('V4 Interleave: Packets Received (unique) per Mode × Size', fontsize=14)
    fig.colorbar(im, ax=ax, label='Unique packets received')
    
    outpath = os.path.join(outdir, 'reception_heatmap.png')
    fig.savefig(outpath, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved: {outpath}")

def plot_throughput_vs_size(phases, outdir):
    """Estimated throughput (bytes received per second) vs packet size."""
    if not phases:
        return
    
    groups = defaultdict(list)
    for p in phases:
        key = f"{p['band']}-{p['mode']}-{p['sf_bw']}"
        groups[key].append(p)
    
    fig, ax = plt.subplots(figsize=(14, 8))
    sizes = [32, 64, 128, 255]
    colors = plt.cm.tab10(np.linspace(0, 1, len(groups)))
    
    for (key, data), color in zip(sorted(groups.items()), colors):
        x_vals = []
        y_vals = []
        for s in sizes:
            matches = [d for d in data if d['pktSize'] == s]
            if matches:
                total_bytes = sum(dm['unique'] * dm['pktSize'] for dm in matches)
                total_pkts = sum(dm['lost'] + dm['unique'] for dm in matches)
                if total_pkts > 0 and s > 0:
                    # Rough throughput: bytes received / estimated air time
                    throughput = total_bytes / (total_pkts * s / 1000.0)
                    x_vals.append(s)
                    y_vals.append(throughput)
        
        if x_vals:
            marker = 's' if 'FLRC' in key else 'o'
            ls = '--' if 'LF' in key else '-'
            ax.plot(x_vals, y_vals, marker=marker, linestyle=ls, linewidth=2,
                    markersize=8, label=key, color=color)
    
    ax.set_xlabel('Packet Size (bytes)', fontsize=14)
    ax.set_ylabel('Throughput (bytes/s)', fontsize=14)
    ax.set_title('V4 Interleave: Throughput vs Packet Size (Bench Test)', fontsize=16)
    ax.set_xticks(sizes)
    ax.set_xticklabels([f'{s}B' for s in sizes])
    ax.legend(fontsize=10, ncol=2, loc='upper left')
    ax.grid(True, alpha=0.3)
    
    outpath = os.path.join(outdir, 'throughput_vs_size.png')
    fig.savefig(outpath, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved: {outpath}")

def print_summary(phases):
    """Print text summary table."""
    print("\n" + "=" * 100)
    print("V4 INTERLEAVE SWEEP — BENCH TEST SUMMARY")
    print("=" * 100)
    print(f"{'Mode':<20} {'Size':>5} {'RX':>5} {'Lost':>5} {'PER%':>7} {'RSSI':>6} {'CRC_E':>5} {'Garb':>5}")
    print("-" * 100)
    
    for p in sorted(phases, key=lambda x: (x['band'], x['mode'], x['sf_bw'], x['pktSize'])):
        key = f"{p['band']}-{p['mode']}-{p['sf_bw']}"
        print(f"{key:<20} {p['pktSize']:>5} {p['rx']:>5} {p['lost']:>5} {p['per']:>7.1f} {p['rssi_avg']:>6} {p['crc_err']:>5} {p['garbage']:>5}")
    
    print("=" * 100)

def main():
    # Find most recent capture file
    datadir = os.path.expanduser('~/worktrees/balloon-range-tests/data/v4-interleave-bench')
    files = sorted(glob.glob(os.path.join(datadir, 'rx_interleave_*.log')))
    
    if not files:
        print("No capture files found in", datadir)
        sys.exit(1)
    
    filepath = files[-1]
    print(f"Analyzing: {filepath}")
    
    phases, pkts = load_data(filepath)
    print(f"Parsed: {len(phases)} PHASE_RESULT lines, {len(pkts)} PKT lines")
    
    if not phases:
        print("WARNING: No PHASE_RESULT data found. Capture may still be running.")
        print("Raw PKT count:", len(pkts))
        sys.exit(1)
    
    print_summary(phases)
    
    plotdir = datadir
    plot_per_vs_size(phases, plotdir)
    plot_reception_heatmap(phases, plotdir)
    plot_throughput_vs_size(phases, plotdir)
    
    print(f"\nAll plots saved to: {plotdir}")

if __name__ == '__main__':
    main()
