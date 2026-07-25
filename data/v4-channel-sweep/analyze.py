#!/usr/bin/env python3
"""Parse rx_sweep capture log and emit analysis summary."""
import re
import sys
from collections import defaultdict
from pathlib import Path

LOG = Path(__file__).parent / "rx_sweep_201758.log"

phase_re = re.compile(
    r"PHASE_RESULT\s+(\d+)\s+(\S+)\s+pktSize=(\d+)\s+rx=(\d+)\s+unique=(\d+)"
    r"\s+lost=(\d+)\s+per=([\d.]+)\s+rssi_avg=(-?\d+)\s+rssi_min=(-?\d+)"
    r"\s+crc_err=(\d+)\s+garbage=(\d+)"
)

phases = []
with open(LOG) as f:
    for line in f:
        m = phase_re.search(line)
        if m:
            d = {
                "phase": int(m.group(1)),
                "name": m.group(2),
                "pkt_size": int(m.group(3)),
                "rx": int(m.group(4)),
                "unique": int(m.group(5)),
                "lost": int(m.group(6)),
                "per": float(m.group(7)),
                "rssi_avg": int(m.group(8)),
                "rssi_min": int(m.group(9)),
                "crc_err": int(m.group(10)),
                "garbage": int(m.group(11)),
            }
            d["decoded"] = d["rx"] > 0
            phases.append(d)

# Also count BER lines
ber_lines = []
ber_re = re.compile(r"BER\s+seq=(\d+)\s+bits=(\d+)\s+errs=(\d+)\s+ber=([\d.e+E-]+)")
with open(LOG) as f:
    for line in f:
        m = ber_re.search(line)
        if m:
            ber_lines.append({
                "seq": int(m.group(1)),
                "bits": int(m.group(2)),
                "errs": int(m.group(3)),
                "ber": float(m.group(4)),
            })

total = len(phases)
decoded = [p for p in phases if p["decoded"]]
not_decoded = [p for p in phases if not p["decoded"]]

print(f"=== CAPTURE ANALYSIS: {LOG.name} ===")
print(f"Total lines: {sum(1 for _ in open(LOG))}")
print(f"Total PHASE_RESULT lines: {total}")
print(f"Phases decoded (rx>0): {len(decoded)} / {total}")
print(f"Phases NOT decoded (rx=0): {len(not_decoded)} / {total}")
print()

# Group by mode (extract mode from name: HF-LoRa-SF7, HF-FLRC-325, etc.)
# Mode = everything before the pktSize suffix
mode_re = re.compile(r"^(HF|LF|CH-\d+)-(.+?)-(\d+|SKIP)$")
modes = defaultdict(list)
for p in phases:
    name = p["name"]
    # Extract mode family: HF-LoRa-SF7, HF-FLRC-325, LF-LoRa-SF7, etc.
    parts = name.split("-")
    if name.startswith("CH-"):
        # Channel sweep phase like CH-869-FLRC1300-64
        freq = parts[1]
        mode_family = f"CH-{freq}"
    elif "FLRC" in name:
        band = parts[0]  # HF or LF
        flrc_type = parts[1]  # FLRC
        bitrate = parts[2]  # 325, 650, etc.
        mode_family = f"{band}-{flrc_type}-{bitrate}"
    elif "LoRa" in name:
        band = parts[0]
        sf = parts[2] if len(parts) > 2 else "SF?"
        mode_family = f"{band}-LoRa-{sf}"
    else:
        mode_family = name
    modes[mode_family].append(p)

print("=== PER-MODE BREAKDOWN ===")
print(f"{'Mode':<20} {'Total':>5} {'Decoded':>7} {'Avg PER':>8} {'Avg RSSI':>9} {'Total RX':>8}")
print("-" * 60)
for mode in sorted(modes.keys()):
    ps = modes[mode]
    dec = [p for p in ps if p["decoded"]]
    avg_per = sum(p["per"] for p in ps) / len(ps)
    # Avg RSSI only for decoded phases (non-zero RSSI)
    rssi_vals = [p["rssi_avg"] for p in ps if p["rssi_avg"] != 0]
    avg_rssi = sum(rssi_vals) / len(rssi_vals) if rssi_vals else 0
    total_rx = sum(p["rx"] for p in ps)
    print(f"{mode:<20} {len(ps):>5} {len(dec):>7} {avg_per:>7.1f}% {avg_rssi:>8.1f}dB {total_rx:>8}")

print()
print("=== CHANNEL SWEEP PHASES ===")
ch_phases = [p for p in phases if p["name"].startswith("CH-")]
if ch_phases:
    print(f"{'Phase':>5} {'Frequency':>12} {'PER':>8} {'RX':>5} {'RSSI':>8} {'CRC_Err':>7} {'Garbage':>8}")
    for p in ch_phases:
        freq = p["name"].split("-")[1]
        print(f"{p['phase']:>5} {freq+' MHz':>12} {p['per']:>7.1f}% {p['rx']:>5} {p['rssi_avg']:>7}dB {p['crc_err']:>7} {p['garbage']:>8}")
else:
    print("NO channel sweep phases captured (WiFi channels not reached)")
    print("Only EU868 tail phases (75-76) from previous cycle were captured")

# Identify WiFi vs EU868
wifi_chs = [p for p in ch_phases if int(p["name"].split("-")[1]) >= 2400]
eu868_chs = [p for p in ch_phases if int(p["name"].split("-")[1]) < 900]
print()
if wifi_chs:
    high_per_wifi = [p for p in wifi_chs if p["per"] > 50]
    print(f"WiFi channels with HIGH PER (>50%): {len(high_per_wifi)}")
    for p in high_per_wifi:
        freq = p["name"].split("-")[1]
        print(f"  CH-{freq} MHz: PER={p['per']:.1f}%")
else:
    print("WiFi channel sweep phases were NOT captured (firmware cycle incomplete)")

print()
print("=== BER ANALYSIS ===")
print(f"Total BER measurement lines: {len(ber_lines)}")
ber_nonzero = [b for b in ber_lines if b["ber"] > 0]
if ber_nonzero:
    print(f"BER > 0 packets: {len(ber_nonzero)}")
    for b in ber_nonzero:
        print(f"  seq={b['seq']} bits={b['bits']} errs={b['errs']} ber={b['ber']:.2e}")
else:
    print("BER > 0 packets: 0 (all BER measurements were perfect, ber=0.00e+00)")
total_bits = sum(b["bits"] for b in ber_lines)
total_errs = sum(b["errs"] for b in ber_lines)
print(f"Total bits measured: {total_bits}, Total errors: {total_errs}")
if total_bits > 0:
    print(f"Overall BER: {total_errs/total_bits:.2e}")

print()
print("=== DUPLICATE PHASE NOTE ===")
phase_counts = defaultdict(int)
for p in phases:
    key = f"{p['phase']}-{p['name']}-{p['pkt_size']}"
    phase_counts[key] += 1
dups = {k: v for k, v in phase_counts.items() if v > 1}
if dups:
    print(f"Duplicate phase entries (restart/retry): {len(dups)}")
    for k, v in dups.items():
        print(f"  {k}: appeared {v}x")
