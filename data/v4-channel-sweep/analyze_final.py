#!/usr/bin/env python3
"""Deep analysis of rx_sweep_final_031009.log — POST-FIX capture (all 3 bugs fixed).

Extracts: phase index, mode, size, rx, PER, RSSI, BER, sats, fix for all 113 phases.
Creates decode map, groups by modulation/band/bitrate/size, channel sweep PER, comparison.
"""
import re
import json
from collections import defaultdict, OrderedDict
from pathlib import Path

DIR = Path(__file__).parent
LOG = DIR / "rx_sweep_final_031009.log"

# Parse PHASE_RESULT lines
phase_re = re.compile(
    r"PHASE_RESULT\s+(\d+)\s+(\S+)\s+pktSize=(\d+)\s+rx=(\d+)\s+unique=(\d+)"
    r"\s+lost=(\d+)\s+per=([\d.]+)\s+rssi_avg=(-?\d+)\s+rssi_min=(-?\d+)"
    r"\s+crc_err=(\d+)\s+garbage=(\d+)"
    r"\s+tx_lat=([\d.-]+)\s+tx_lon=([\d.-]+)\s+sats=(\d+)\s+fix=(\d+)\s+utc=(\d+)"
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
                "sats": int(m.group(14)),
                "fix": int(m.group(15)),
                "utc": int(m.group(16)),
            }
            d["decoded"] = d["rx"] > 0
            phases.append(d)

# Parse BER lines
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
failed = [p for p in phases if not p["decoded"]]

print("=" * 70)
print("DEEP ANALYSIS: rx_sweep_final_031009.log (POST-FIX, all 3 bugs fixed)")
print("=" * 70)
print(f"Total PHASE_RESULT lines: {total}")
print(f"Phases decoded (rx>0): {len(decoded)} / {total} ({100*len(decoded)/total:.1f}%)")
print(f"Phases failed (rx=0):   {len(failed)} / {total} ({100*len(failed)/total:.1f}%)")
print()

# Identify capture cycles (phase numbers reset at 0)
# The capture order is: tail of previous cycle → full cycle → start of next cycle
print("=== CAPTURE SEQUENCE (capture order) ===")
print(f"Phases in capture order: {[p['phase'] for p in phases]}")
print()

# Group by name+size to handle duplicates across cycles
# For the decode map, we use the LAST occurrence of each unique phase (most recent cycle)
unique_phases = OrderedDict()
for p in phases:
    key = f"{p['name']}-sz{p['pkt_size']}"
    unique_phases[key] = p  # last occurrence wins

# But actually, for multi-cycle captures we should show ALL instances
# Let's track cycles
print("=== CYCLE DETECTION ===")
cycle_boundaries = []
for i in range(1, len(phases)):
    if phases[i]["phase"] < phases[i-1]["phase"] or phases[i]["phase"] == 0 and phases[i-1]["phase"] > 0:
        cycle_boundaries.append(i)
        
for i, boundary in enumerate(cycle_boundaries):
    print(f"Cycle boundary {i+1}: at index {boundary} (phase {phases[boundary-1]['phase']} → phase {phases[boundary]['phase']})")

cycles = []
start = 0
for b in cycle_boundaries:
    cycles.append(phases[start:b])
    start = b
cycles.append(phases[start:])
for i, cyc in enumerate(cycles):
    dec = sum(1 for p in cyc if p["decoded"])
    print(f"Cycle {i+1}: {len(cyc)} phases ({dec} decoded = {100*dec/max(len(cyc),1):.0f}%), phases {cyc[0]['phase']}–{cyc[-1]['phase']}")
print()

# Full decode map for all 113 phases
print("=" * 70)
print("COMPLETE DECODE MAP (all 113 phases, in capture order)")
print("=" * 70)
print(f"{'Idx':<4} {'Phase':<5} {'Mode':<22} {'Sz':<5} {'RX':<5} {'PER%':<7} {'RSSI':<6} {'CRC':<5} {'Garb':<6} {'Sats':<5} {'Fix':<4} {'Status'}")
print("-" * 95)
for i, p in enumerate(phases):
    status = "✅ DECODE" if p["decoded"] else "❌ FAIL"
    # Mark special cases
    if "SKIP" in p["name"]:
        status = "⏭️ SKIP"
    elif p["name"].startswith("CH-") and int(p["name"].split("-")[1]) >= 2400:
        status = "❌ OOB" if not p["decoded"] else "⚠️ LEAK"
    rssi = f"{p['rssi_avg']}dBm" if p['rssi_avg'] != 0 else "—"
    print(f"{i:<4} {p['phase']:<5} {p['name']:<22} {p['pkt_size']:<5} {p['rx']:<5} {p['per']:<7.1f} {rssi:<6} {p['crc_err']:<5} {p['garbage']:<6} {p['sats']:<5} {p['fix']:<4} {status}")
print()

# Now analyze using LAST occurrence of each unique mode+size
print("=" * 70)
print("DECODE MAP BY UNIQUE MODE (last cycle occurrence)")
print("=" * 70)

# Group by mode family
def classify(name):
    """Return (band, modulation, bitrate_or_sf, is_channel_sweep, freq)."""
    if name.startswith("CH-"):
        parts = name.split("-")
        freq = int(parts[1])
        mode = parts[2]  # FLRC1300
        return ("CH", "FLRC", mode, True, freq)
    parts = name.split("-")
    band = parts[0]  # HF or LF
    if "FLRC" in name:
        bitrate = parts[2]
        return (band, "FLRC", bitrate, False, None)
    elif "LoRa" in name:
        sf = parts[2] if len(parts) > 2 else "?"
        return (band, "LoRa", sf, False, None)
    return (band, "?", "?", False, None)

# Use latest occurrence for each unique mode+size
latest = OrderedDict()
for p in phases:
    key = f"{p['name']}-sz{p['pkt_size']}"
    latest[key] = p

print(f"\n{'Mode':<24} {'Size':<5} {'RX':<5} {'PER%':<7} {'RSSI':<8} {'CRC':<5} {'Garb':<6} {'Status'}")
print("-" * 75)
for key, p in latest.items():
    status = "✅" if p["decoded"] else "❌"
    if "SKIP" in p["name"]:
        status = "⏭️"
    rssi = f"{p['rssi_avg']}/{p['rssi_min']}" if p['rssi_avg'] != 0 else "—"
    print(f"{p['name']:<24} {p['pkt_size']:<5} {p['rx']:<5} {p['per']:<7.1f} {rssi:<8} {p['crc_err']:<5} {p['garbage']:<6} {status}")
print()

# GROUP ANALYSIS
print("=" * 70)
print("GROUP ANALYSIS (using latest cycle data)")
print("=" * 70)

# 1. By modulation type
print("\n--- 1. BY MODULATION TYPE ---")
mod_groups = defaultdict(list)
for p in latest.values():
    if "SKIP" in p["name"]:
        continue
    _, mod, _, is_ch, _ = classify(p["name"])
    if is_ch:
        continue  # channel sweep separate
    mod_groups[mod].append(p)

for mod in sorted(mod_groups.keys()):
    ps = mod_groups[mod]
    dec = [p for p in ps if p["decoded"]]
    avg_per = sum(p["per"] for p in ps) / len(ps)
    total_rx = sum(p["rx"] for p in ps)
    print(f"  {mod:<6}: {len(dec)}/{len(ps)} decoded ({100*len(dec)/len(ps):.0f}%), avg PER={avg_per:.1f}%, total RX={total_rx}")

# 2. By band
print("\n--- 2. BY BAND (HF vs LF) ---")
band_groups = defaultdict(list)
for p in latest.values():
    if "SKIP" in p["name"]:
        continue
    band, _, _, is_ch, _ = classify(p["name"])
    if is_ch:
        continue
    band_groups[band].append(p)

for band in sorted(band_groups.keys()):
    ps = band_groups[band]
    dec = [p for p in ps if p["decoded"]]
    avg_per = sum(p["per"] for p in ps) / len(ps)
    total_rx = sum(p["rx"] for p in ps)
    print(f"  {band}: {len(dec)}/{len(ps)} decoded ({100*len(dec)/len(ps):.0f}%), avg PER={avg_per:.1f}%, total RX={total_rx}")

# 3. By bitrate (FLRC only)
print("\n--- 3. BY FLRC BITRATE ---")
br_groups = defaultdict(list)
for p in latest.values():
    if "SKIP" in p["name"]:
        continue
    band, mod, br, is_ch, _ = classify(p["name"])
    if mod != "FLRC" or is_ch:
        continue
    br_groups[f"{band}-FLRC-{br}"].append(p)

for br in sorted(br_groups.keys()):
    ps = br_groups[br]
    dec = [p for p in ps if p["decoded"]]
    avg_per = sum(p["per"] for p in ps) / len(ps)
    total_rx = sum(p["rx"] for p in ps)
    sizes = sorted(p["pkt_size"] for p in ps)
    print(f"  {br:<16}: {len(dec)}/{len(ps)} decoded ({100*len(dec)/len(ps):.0f}%), avg PER={avg_per:.1f}%, total RX={total_rx}, sizes={sizes}")

# 4. By packet size (FLRC only)
print("\n--- 4. BY PACKET SIZE (FLRC only) ---")
size_groups = defaultdict(list)
for p in latest.values():
    if "SKIP" in p["name"]:
        continue
    _, mod, _, is_ch, _ = classify(p["name"])
    if mod != "FLRC" or is_ch:
        continue
    size_groups[p["pkt_size"]].append(p)

for sz in sorted(size_groups.keys()):
    ps = size_groups[sz]
    dec = [p for p in ps if p["decoded"]]
    avg_per = sum(p["per"] for p in ps) / len(ps)
    total_rx = sum(p["rx"] for p in ps)
    print(f"  Size {sz:<4}: {len(dec)}/{len(ps)} decoded ({100*len(dec)/len(ps):.0f}%), avg PER={avg_per:.1f}%, total RX={total_rx}")

# 5. Channel sweep PER per frequency
print("\n--- 5. CHANNEL SWEEP — PER PER FREQUENCY ---")
ch_phases = [p for p in latest.values() if p["name"].startswith("CH-")]
ch_phases.sort(key=lambda p: int(p["name"].split("-")[1]))
print(f"  {'Freq':<10} {'RX':<5} {'PER%':<7} {'RSSI':<8} {'CRC':<5} {'Garb':<6} {'Status'}")
for p in ch_phases:
    freq = int(p["name"].split("-")[1])
    band_label = "WiFi" if freq >= 2400 else "EU868"
    status = "✅ decode" if p["decoded"] else "❌ fail"
    if freq >= 2400 and not p["decoded"]:
        status = "❌ OUT OF BAND"
    rssi = f"{p['rssi_avg']}dBm" if p['rssi_avg'] != 0 else "—"
    print(f"  {freq} ({band_label}) {p['rx']:<5} {p['per']:<7.1f} {rssi:<8} {p['crc_err']:<5} {p['garbage']:<6} {status}")

wifi_chs = [p for p in ch_phases if int(p["name"].split("-")[1]) >= 2400]
eu868_chs = [p for p in ch_phases if int(p["name"].split("-")[1]) < 900]
wifi_dec = sum(1 for p in wifi_chs if p["decoded"])
eu868_dec = sum(1 for p in eu868_chs if p["decoded"])
print(f"\n  WiFi 2.4 GHz: {wifi_dec}/{len(wifi_chs)} decoded")
print(f"  EU868 (863-870): {eu868_dec}/{len(eu868_chs)} decoded")
print()

# BER analysis
print("=" * 70)
print("BER ANALYSIS")
print("=" * 70)
total_bits = sum(b["bits"] for b in ber_lines)
total_errs = sum(b["errs"] for b in ber_lines)
ber_nonzero = [b for b in ber_lines if b["ber"] > 0]
print(f"Total BER measurements: {len(ber_lines)}")
print(f"BER > 0 packets: {len(ber_nonzero)}")
print(f"Total bits measured: {total_bits:,}")
print(f"Total bit errors: {total_errs}")
if total_bits > 0:
    print(f"Overall BER: {total_errs/total_bits:.2e}")
print()

# Missing phases analysis
print("=" * 70)
print("CAPTURE COMPLETENESS ANALYSIS")
print("=" * 70)
# Full cycle is phases 0-76 (77 phases)
full_cycle_phases = set(range(77))
captured_phases = set(p["phase"] for p in phases)
# Get phase set from last full cycle
# Find the longest cycle
longest = max(cycles, key=len)
longest_phases = set(p["phase"] for p in longest)
missing_from_full = full_cycle_phases - longest_phases
print(f"Full cycle = 77 phases (0–76)")
print(f"Longest cycle captured: {len(longest)} phases")
print(f"Missing from full cycle: {sorted(missing_from_full)}")
if missing_from_full:
    for ph in sorted(missing_from_full):
        print(f"  Phase {ph}: missing")
print()

# Dump all parsed data as JSON for reference
output = {
    "capture": "rx_sweep_final_031009.log",
    "total_phases": total,
    "decoded": len(decoded),
    "failed": len(failed),
    "decode_rate": round(100 * len(decoded) / total, 1),
    "phases": phases,
    "ber_total_bits": total_bits,
    "ber_total_errs": total_errs,
}
with open(DIR / "final_analysis.json", "w") as f:
    json.dump(output, f, indent=2)
print(f"Raw data written to final_analysis.json")
