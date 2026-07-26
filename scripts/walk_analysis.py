#!/usr/bin/env python3
"""
Walk Test Packet Corruption Analysis
=====================================
Parses walk-official-rx.txt, decodes raw bytes using firmware logic,
correlates with phone GPS, and identifies root cause of corruption.
"""
import struct
import re
import math
import csv
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
CAPTURE = DATA_DIR / "walk-official-rx.txt"
PHONE_GPS = DATA_DIR / "phone-gps-walk-20260724.csv"

# Home coordinates
HOME_LAT, HOME_LON = 32.6390, -16.9463

def parse_capture():
    """Parse all line types from the capture file."""
    pkts = []          # PKT lines
    time_diffs = []    # TIME_DIFF lines
    raw32_dumps = {}   # FLRC_RAW32: phase -> bytes
    lora_raw = {}      # LORA_RAW: phase -> bytes
    phase_results = [] # PHASE_RESULT lines
    phase_starts = []  # PHASE_START lines

    with open(CAPTURE) as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if line.startswith("PKT "):
                # PKT rx=1 seq=59666 rssi=-53 phase=3 rx_ms=969161 tx_lat=-176.65283 tx_lon=174.68396 sats=40832 fix=74 utc=3551834019
                m = re.match(
                    r'PKT rx=(\d+) seq=(\d+) rssi=(-?\d+) phase=(\d+) rx_ms=(\d+) '
                    r'tx_lat=(-?[\d.]+) tx_lon=(-?[\d.]+) sats=(\d+) fix=(\d+) utc=(\d+)',
                    line)
                if m:
                    pkts.append({
                        'line': line_no,
                        'rx': int(m.group(1)),
                        'seq': int(m.group(2)),
                        'rssi': int(m.group(3)),
                        'phase': int(m.group(4)),
                        'rx_ms': int(m.group(5)),
                        'tx_lat': float(m.group(6)),
                        'tx_lon': float(m.group(7)),
                        'sats': int(m.group(8)),
                        'fix': int(m.group(9)),
                        'utc': int(m.group(10)),
                        'raw_line': line,
                    })
            elif line.startswith("TIME_DIFF "):
                m = re.match(r'TIME_DIFF gps_utc=(\d+) laptop_utc=(\d+)', line)
                if m:
                    time_diffs.append({
                        'line': line_no,
                        'gps_utc': int(m.group(1)),
                        'laptop_utc': int(m.group(2)),
                    })
            elif line.startswith("FLRC_RAW32:"):
                nums = [int(x) for x in line.split(":")[1].split()]
                raw32_dumps[line_no] = nums
            elif line.startswith("LORA_RAW:"):
                nums = [int(x) for x in line.split(":")[1].split()]
                lora_raw[line_no] = nums
            elif line.startswith("PHASE_RESULT"):
                phase_results.append({'line': line_no, 'raw': line})
            elif line.startswith("PHASE_START"):
                m = re.match(r'PHASE_START (\d+) (\S+)', line)
                if m:
                    phase_starts.append({
                        'line': line_no,
                        'phase': int(m.group(1)),
                        'name': m.group(2),
                    })
    return pkts, time_diffs, raw32_dumps, lora_raw, phase_results, phase_starts


def parse_phone_gps():
    """Parse phone GPS CSV."""
    points = []
    with open(PHONE_GPS) as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                ts_ms = int(row['timestamp_ms'])
                lat = float(row['lat'])
                lon = float(row['lon'])
                points.append({
                    'ts_ms': ts_ms,
                    'lat': lat,
                    'lon': lon,
                    'distance': float(row.get('distance', 0)),
                })
            except (ValueError, KeyError):
                continue
    return points


def haversine(lat1, lon1, lat2, lon2):
    """Distance in meters between two lat/lon points."""
    R = 6371000  # Earth radius meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def decode_firmware_layout(raw_bytes, gps_off):
    """Decode raw FIFO bytes using the RX firmware's parse logic.

    TX packet layout (from embedGPS):
      bytes 0-3:   sync header (0xA5 0x5A 0x42 0x24)
      bytes 4-7:   latE7 (int32 LE)
      bytes 8-11:  lonE7 (int32 LE)
      bytes 12-13: sats (uint16 LE)
      byte  14:    fixQ (uint8)
      bytes 15-18: utcSec (uint32 LE)
      byte  19:    phaseId (uint8)
      bytes 20-21: seq (uint16 BE)

    RX uses gpsOff to skip the sync header:
      latE7 = bytes[gpsOff+0..3]
      lonE7 = bytes[gpsOff+4..7]
      sats  = bytes[gpsOff+8..9]
      fixQ  = bytes[gpsOff+10]
      utc   = bytes[gpsOff+11..14]
      seq   = (bytes[gpsOff+16] << 8) | bytes[gpsOff+17]
    """
    b = raw_bytes
    o = gps_off
    if len(b) < o + 18:
        return None

    lat_e7 = struct.unpack_from('<i', bytes(b[o:o+4]))[0]
    lon_e7 = struct.unpack_from('<i', bytes(b[o+4:o+8]))[0]
    sats = b[o+8] | (b[o+9] << 8)
    fix_q = b[o+10]
    utc = struct.unpack_from('<I', bytes(b[o+11:o+15]))[0]
    seq = (b[o+16] << 8) | b[o+17]

    return {
        'lat': lat_e7 / 1e7,
        'lon': lon_e7 / 1e7,
        'sats': sats,
        'fix': fix_q,
        'utc': utc,
        'seq': seq,
        'latE7': lat_e7,
        'lonE7': lon_e7,
    }


def check_sync_header(raw_bytes):
    """Check if 0xA5 0x5A 0x42 0x24 appears anywhere in first 32 bytes."""
    target = [0xA5, 0x5A, 0x42, 0x24]
    for i in range(len(raw_bytes) - 3):
        if raw_bytes[i:i+4] == target:
            return i
    return -1


def check_fill_pattern(raw_bytes):
    """Check for the TX fill pattern: byte[i] = i ^ 0xA5 for i >= 22."""
    # Try different base offsets (in case FIFO is shifted)
    for base in range(0, 8):
        matches = 0
        total = 0
        for i in range(22, min(len(raw_bytes), 32)):
            fifo_idx = i
            tx_byte_idx = fifo_idx + base  # if FIFO starts at TX byte `base`
            expected = (tx_byte_idx ^ 0xA5) & 0xFF
            if raw_bytes[fifo_idx] == expected:
                matches += 1
            total += 1
        if matches > total * 0.5:
            return base, matches, total
    return -1, 0, 0


def entropy_check(raw_bytes):
    """Estimate randomness of byte values."""
    from collections import Counter
    c = Counter(raw_bytes)
    n = len(raw_bytes)
    # Unique byte count
    unique = len(c)
    # Most common byte frequency
    most_common_pct = c.most_common(1)[0][1] / n * 100
    return unique, most_common_pct


def analyze_seq_numbers(pkts):
    """Analyze sequence number patterns."""
    seqs = [p['seq'] for p in pkts]
    # Check if sequential
    sequential_count = sum(1 for i in range(1, len(seqs))
                          if seqs[i] == seqs[i-1] + 1)
    # Check distribution
    in_range = sum(1 for s in seqs if s < 200)  # valid seq range 0-199
    over_255 = sum(1 for s in seqs if s > 255)
    return {
        'total': len(seqs),
        'min': min(seqs),
        'max': max(seqs),
        'sequential_adjacent': sequential_count,
        'in_valid_range_0_199': in_range,
        'over_255': over_255,
        'first_20': seqs[:20],
    }


def main():
    print("=" * 80)
    print("WALK TEST PACKET CORRUPTION ANALYSIS")
    print("=" * 80)

    pkts, time_diffs, raw32_dumps, lora_raw, phase_results, phase_starts = parse_capture()
    phone_points = parse_phone_gps()

    print(f"\n--- PARSE SUMMARY ---")
    print(f"PKT lines:          {len(pkts)}")
    print(f"TIME_DIFF lines:    {len(time_diffs)}")
    print(f"FLRC_RAW32 dumps:   {len(raw32_dumps)}")
    print(f"LORA_RAW dumps:     {len(lora_raw)}")
    print(f"PHASE_RESULT lines: {len(phase_results)}")
    print(f"PHASE_START lines:  {len(phase_starts)}")
    print(f"Phone GPS points:   {len(phone_points)}")

    # ── SEQ ANALYSIS ──
    print(f"\n--- SEQ NUMBER ANALYSIS ---")
    seq_info = analyze_seq_numbers(pkts)
    print(f"Total PKTs:     {seq_info['total']}")
    print(f"Seq range:      {seq_info['min']} - {seq_info['max']}")
    print(f"Sequential adjacent pairs: {seq_info['sequential_adjacent']}/{seq_info['total']-1}")
    print(f"Seq in valid range (0-199): {seq_info['in_valid_range_0_199']}/{seq_info['total']}")
    print(f"Seq over 255 (bitmap miss): {seq_info['over_255']}/{seq_info['total']}")
    print(f"First 20 seqs:  {seq_info['first_20']}")

    # ── SYNC HEADER CHECK ──
    print(f"\n--- SYNC HEADER 0xA5 0x5A 0x42 0x24 SEARCH ---")
    sync_found = 0
    for line_no, raw in raw32_dumps.items():
        pos = check_sync_header(raw)
        if pos >= 0:
            sync_found += 1
            print(f"  Line {line_no}: FOUND at byte {pos}")
    print(f"  Sync header found in {sync_found}/{len(raw32_dumps)} FLRC_RAW32 dumps")

    # ── FILL PATTERN CHECK ──
    print(f"\n--- FILL PATTERN (i ^ 0xA5) SEARCH ---")
    fill_found = 0
    for line_no, raw in raw32_dumps.items():
        base, matches, total = check_fill_pattern(raw)
        if base >= 0:
            fill_found += 1
            print(f"  Line {line_no}: FOUND at base offset {base} ({matches}/{total} match)")
    print(f"  Fill pattern found in {fill_found}/{len(raw32_dumps)} FLRC_RAW32 dumps")

    # ── ENTROPY / RANDOMNESS ──
    print(f"\n--- BYTE RANDOMNESS (FLRC_RAW32 dumps) ---")
    all_raw = []
    for line_no, raw in sorted(raw32_dumps.items()):
        unique, pct = entropy_check(raw)
        all_raw.extend(raw)
        if line_no <= 60:  # first few
            print(f"  Line {line_no}: {unique}/32 unique bytes, most common={pct:.0f}%")
    overall_unique, overall_pct = entropy_check(all_raw)
    print(f"  ALL DUMPS COMBINED: {overall_unique}/256 unique byte values (uniform={overall_unique>=200})")

    # ── SAMPLE PACKET DECODE: 5 packets ──
    print(f"\n--- 5 SAMPLE PACKET BYTE-BY-BYTE DECODE ---")

    # Get 5 sample FLRC_RAW32 dumps with corresponding PKT lines
    # They appear at specific line numbers; find pairs
    samples = []
    raw_lines = sorted(raw32_dumps.keys())
    for rl in raw_lines[:5]:
        # Find the PKT line right after this RAW32 dump
        for p in pkts:
            if p['line'] > rl and p['line'] < rl + 10:
                samples.append((rl, raw32_dumps[rl], p))
                break

    # Expected values from ground truth
    expected_lat_e7 = int(HOME_LAT * 1e7)
    expected_lon_e7 = int(HOME_LON * 1e7)
    print(f"\nExpected (ground truth): lat={HOME_LAT} lon={HOME_LON}")
    print(f"  latE7={expected_lat_e7} bytes LE={list(struct.pack('<i', expected_lat_e7))}")
    print(f"  lonE7={expected_lon_e7} bytes LE={list(struct.pack('<i', expected_lon_e7))}")
    print(f"  sync header: [165, 90, 66, 36]")
    print()

    for idx, (rl, raw, pkt) in enumerate(samples):
        print(f"\n{'='*60}")
        print(f"SAMPLE {idx+1}: Line {rl} (Phase {pkt['phase']})")
        print(f"  RAW32: {' '.join(str(b) for b in raw)}")
        print(f"  PKT decoded: seq={pkt['seq']} rssi={pkt['rssi']} lat={pkt['tx_lat']:.5f} "
              f"lon={pkt['tx_lon']:.5f} sats={pkt['sats']} fix={pkt['fix']} utc={pkt['utc']}")

        # Decode with gpsOff=4 (current firmware)
        d4 = decode_firmware_layout(raw, 4)
        # Decode with gpsOff=0 (older firmware)
        d0 = decode_firmware_layout(raw, 0)
        # Decode with gpsOff=8
        d8 = decode_firmware_layout(raw, 8)

        print(f"\n  Decode with gpsOff=4 (current RX code):")
        print(f"    lat={d4['lat']:.5f} lon={d4['lon']:.5f} sats={d4['sats']} "
              f"fix={d4['fix']} utc={d4['utc']} seq={d4['seq']}")
        print(f"  Decode with gpsOff=0:")
        print(f"    lat={d0['lat']:.5f} lon={d0['lon']:.5f} sats={d0['sats']} "
              f"fix={d0['fix']} utc={d0['utc']} seq={d0['seq']}")
        print(f"  Decode with gpsOff=8:")
        print(f"    lat={d8['lat']:.5f} lon={d8['lon']:.5f} sats={d8['sats']} "
              f"fix={d8['fix']} utc={d8['utc']} seq={d8['seq']}")

        # Show what bytes 0-21 SHOULD look like vs what we got
        print(f"\n  BYTE-BYTE COMPARISON (TX expected vs FIFO actual):")
        print(f"    {'Byte':>4} {'TX_Expected':>12} {'FIFO_Actual':>12} {'Match':>6}")
        expected_tx = [0xA5, 0x5A, 0x42, 0x24]  # sync header
        expected_tx += list(struct.pack('<i', expected_lat_e7))  # lat
        expected_tx += list(struct.pack('<i', expected_lon_e7))  # lon
        expected_tx += [15, 0]  # sats ~15
        expected_tx += [1]  # fix=1
        expected_tx += list(struct.pack('<I', 1784897108))  # utc (approx)
        expected_tx += [pkt['phase']]  # phaseId
        expected_tx += [0, 0]  # seq=0 (first packet of phase)

        for i in range(min(22, len(raw))):
            exp = expected_tx[i] if i < len(expected_tx) else '?'
            act = raw[i]
            match = '✓' if str(exp) == str(act) else '✗'
            print(f"    {i:>4} {str(exp):>12} {act:>12} {match:>6}")

    # ── TIME DIFF ANALYSIS ──
    print(f"\n{'='*60}")
    print(f"--- TIME_DIFF ANALYSIS ---")
    laptop_utcs = [td['laptop_utc'] for td in time_diffs]
    gps_utcs = [td['gps_utc'] for td in time_diffs]
    print(f"  laptop_utc range: {min(laptop_utcs)} - {max(laptop_utcs)}")
    print(f"  gps_utc range:    {min(gps_utcs)} - {max(gps_utcs)}")
    print(f"  laptop_utc span:  {max(laptop_utcs) - min(laptop_utcs)}s")
    print(f"  gps_utc values are {'RANDOM' if max(gps_utcs) - min(gps_utcs) > 4_000_000_000 // 2 else 'consistent'}")
    print(f"  Expected utc:     ~1784897108 (2026-07-24)")
    print(f"  gps_utc values: {' '.join(str(u) for u in gps_utcs[:10])}...")
    unique_gps = len(set(gps_utcs))
    print(f"  Unique gps_utc values: {unique_gps}/{len(gps_utcs)}")

    # ── DISTANCE vs RSSI (using laptop_utc for time correlation) ──
    print(f"\n{'='*60}")
    print(f"--- DISTANCE vs RSSI (from phone GPS ground truth) ---")
    print(f"  Using laptop_utc timestamps to find phone GPS position at RX time")
    print()

    # For each PKT, estimate distance from home using phone GPS
    # RX time in epoch seconds = laptop_utc at nearest TIME_DIFF
    # Phone GPS has timestamp_ms

    # Build interpolated laptop_utc per packet
    td_lines = sorted(time_diffs, key=lambda x: x['line'])
    results = []
    for pkt in pkts:
        # Find nearest TIME_DIFF before this PKT line
        best_td = None
        for td in td_lines:
            if td['line'] <= pkt['line']:
                best_td = td
            else:
                break
        if best_td is None:
            continue

        laptop_epoch = best_td['laptop_utc']
        laptop_ms = laptop_epoch * 1000

        # Find nearest phone GPS point
        best_point = None
        best_diff = float('inf')
        for pt in phone_points:
            diff = abs(pt['ts_ms'] - laptop_ms)
            if diff < best_diff:
                best_diff = diff
                best_point = pt

        if best_point is not None and best_diff < 60000:  # within 60s
            dist = haversine(HOME_LAT, HOME_LON, best_point['lat'], best_point['lon'])
            results.append({
                'phase': pkt['phase'],
                'rssi': pkt['rssi'],
                'dist_m': dist,
                'time_diff_s': best_diff / 1000,
                'rx_ms': pkt['rx_ms'],
            })

    if results:
        print(f"  Correlated {len(results)}/{len(pkts)} packets with phone GPS")
        print(f"  Distance range: {min(r['dist_m'] for r in results):.0f}m - "
              f"{max(r['dist_m'] for r in results):.0f}m")
        print(f"  RSSI range: {min(r['rssi'] for r in results)} - "
              f"{max(r['rssi'] for r in results)} dBm")

        # Bin by distance
        bins = [(0, 500), (500, 1000), (1000, 2000), (2000, 3000),
                (3000, 4000), (4000, 6000)]
        print(f"\n  {'Distance':>12} {'Count':>6} {'RSSI_avg':>9} {'RSSI_min':>9} {'RSSI_max':>9}")
        for lo, hi in bins:
            subset = [r for r in results if lo <= r['dist_m'] < hi]
            if subset:
                rssis = [r['rssi'] for r in subset]
                print(f"  {lo:>5}-{hi:<5}m {len(subset):>6} "
                      f"{sum(rssis)/len(rssis):>9.1f} {min(rssis):>9} {max(rssis):>9}")
            else:
                print(f"  {lo:>5}-{hi:<5}m {'(no data)':>6}")

    # ── PER-PHASE SUMMARY ──
    print(f"\n{'='*60}")
    print(f"--- PER-PHASE PACKET COUNTS ---")
    phase_names = {
        0: "HF-LoRa-SF7", 1: "HF-LoRa-SF9", 2: "HF-LoRa-SF12",
        3: "HF-FLRC-2600", 4: "HF-FLRC-1300", 5: "HF-FLRC-650", 6: "HF-FLRC-325",
        7: "LF-LoRa-SF7", 8: "LF-LoRa-SF9", 9: "LF-LoRa-SF12",
        10: "LF-FLRC-2600", 11: "LF-FLRC-1300", 12: "LF-FLRC-650", 13: "LF-FLRC-325",
    }
    print(f"  {'Phase':>5} {'Name':>16} {'PKTs':>5} {'Avg_RSSI':>9}")
    for ph in range(14):
        subset = [p for p in pkts if p['phase'] == ph]
        if subset:
            avg_rssi = sum(p['rssi'] for p in subset) / len(subset)
            print(f"  {ph:>5} {phase_names[ph]:>16} {len(subset):>5} {avg_rssi:>9.1f}")
        else:
            print(f"  {ph:>5} {phase_names[ph]:>16} {'0':>5} {'-':>9}")

    # ── ROOT CAUSE DIAGNOSIS ──
    print(f"\n{'='*60}")
    print(f"--- ROOT CAUSE DIAGNOSIS ---")

    findings = []

    # Check 1: sync header present?
    sync_count = sum(1 for raw in raw32_dumps.values() if check_sync_header(raw) >= 0)
    findings.append(f"Sync header 0xA5 0x5A 0x42 0x24 found: {sync_count}/{len(raw32_dumps)} dumps")

    # Check 2: fill pattern present?
    fill_count = sum(1 for raw in raw32_dumps.values() if check_fill_pattern(raw)[0] >= 0)
    findings.append(f"Fill pattern (i^0xA5) found: {fill_count}/{len(raw32_dumps)} dumps")

    # Check 3: seq sequential?
    findings.append(f"Sequential seq pairs: {seq_info['sequential_adjacent']}/{seq_info['total']-1}")
    findings.append(f"Seq values > 255 (out of bitmap): {seq_info['over_255']}/{seq_info['total']}")

    # Check 4: utc values random?
    findings.append(f"Unique gps_utc values: {unique_gps}/{len(gps_utcs)} (should be ~1 per second)")

    # Check 5: lat/lon valid?
    valid_lat = sum(1 for p in pkts if -90 <= p['tx_lat'] <= 90)
    valid_lon = sum(1 for p in pkts if -180 <= p['tx_lon'] <= 180)
    findings.append(f"Valid lat (-90..90): {valid_lat}/{len(pkts)}")
    findings.append(f"Valid lon (-180..180): {valid_lon}/{len(pkts)}")

    for f in findings:
        print(f"  • {f}")

    return pkts, time_diffs, raw32_dumps, results


if __name__ == "__main__":
    main()
