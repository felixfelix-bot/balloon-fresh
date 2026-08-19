#!/usr/bin/env python3
"""capture_sweep.py — Sweep-mode capture tool with harmonized 23-field PKT parsing.

Captures LR2021 multi-radio sweep data from RX board over serial. Parses
23-field PKT lines via the shared pkt_parser module and writes structured CSV.
Supports stop-and-capture and walk-mode (with GPS distance).

Two modes:
  1. STOP-AND-CAPTURE (default): operator places TX at fixed distance
  2. WALK MODE (--walk): operator walks with TX; distance from GPS coords

Usage:
  # Walk mode — continuous capture with GPS distance
  python3 tools/capture_sweep.py --port /dev/ttyACM0 --walk --env outdoor_los
  python3 tools/capture_sweep.py --port /dev/ttyACM0 --distance 10 --env outdoor_los
"""

import argparse
import csv
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial", file=sys.stderr)
    sys.exit(1)

# Shared PKT parser from tools/
TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
from pkt_parser import parse_pkt_line, PKT_FIELDS  # noqa: E402

# Session manager (HOST-3)
from session_manager import generate_session_id, format_session_start, inject_session_id_into_pkt, send_session_command  # noqa: E402

PKT_CSV_COLUMNS = ['timestamp_iso'] + PKT_FIELDS + [
    'distance_m', 'environment', 'notes', 'raw_line',
]

# Haversine distance
def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def parse_cycle_start(line: str) -> int | None:
    """Parse: === CYCLE <n> START uptime=<ms> ==="""
    import re
    m = re.search(r"CYCLE (\d+) START", line)
    return int(m.group(1)) if m else None


def main():
    parser = argparse.ArgumentParser(
        description='Sweep-mode capture with 23-field PKT parsing')
    parser.add_argument('--port', default='/dev/ttyACM0',
                        help='Serial port (default: /dev/ttyACM0)')
    parser.add_argument('--baud', type=int, default=2000000,
                        help='Baud rate (default: 2000000)')
    parser.add_argument('--out', default='data/sweep',
                        help='Output directory')
    parser.add_argument('--duration', type=int, default=0,
                        help='Capture duration in seconds (0=forever)')
    parser.add_argument('--distance', type=float, default=0,
                        help='Fixed TX-RX distance in meters (stop mode)')
    parser.add_argument('--walk', action='store_true',
                        help='Walk mode — compute distance from GPS')
    parser.add_argument('--base-lat', type=float,
                        help='Base station latitude (walk mode)')
    parser.add_argument('--base-lon', type=float,
                        help='Base station longitude (walk mode)')
    parser.add_argument('--env', default='indoor',
                        help='Environment label (indoor/outdoor_los/urban)')
    parser.add_argument('--notes', default='', help='Custom notes for CSV')
    args = parser.parse_args()

    # Validate args
    if args.walk and args.distance > 0:
        print("ERROR: --walk and --distance are mutually exclusive", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = out_dir / f'sweep_capture_{ts}.csv'
    raw_path = out_dir / f'sweep_capture_{ts}.raw'

    try:
        ser = serial.Serial(args.port, args.baud, timeout=1.0)
    except serial.SerialException as e:
        print(f"ERROR: Cannot open {args.port}: {e}", file=sys.stderr)
        sys.exit(1)

    # ── HOST-3: Session ID injection ────────────────────────────────
    # Generate a unique session_id, send it to firmware via SESSION command,
    # and inject it into all PKT lines and output metadata.
    session_id = generate_session_id()
    session_header = format_session_start(session_id)
    print(f"[SESSION] {session_id}")

    # Send SESSION command to firmware so it includes the session_id in PKT lines
    if not send_session_command(ser, session_id):
        print("[SESSION] WARNING: Failed to send SESSION command to firmware")
    else:
        print("[SESSION] SESSION command sent to firmware")

    pkt_count = 0
    cycle_count = 0
    start_time = time.time()

    with open(csv_path, 'w', newline='') as csvfile, open(raw_path, 'w') as rawfile:
        writer = csv.writer(csvfile)
        # Write SESSION_START header before the CSV column header
        csvfile.write(f"# {session_header}")
        writer.writerow(PKT_CSV_COLUMNS)

        mode_label = f"WALK (base={args.base_lat},{args.base_lon})" if args.walk \
                     else f"STOP (d={args.distance}m)"
        print(f"Sweep capture started:")
        print(f"  Port:     {args.port} @ {args.baud} baud")
        print(f"  Mode:     {mode_label}")
        print(f"  Env:      {args.env}")
        print(f"  Duration: {'forever' if args.duration == 0 else f'{args.duration}s'}")
        print(f"  PKT CSV:  {csv_path}")
        print(f"Press Ctrl+C to stop.\n")

        buf = ''
        while True:
            if args.duration > 0 and (time.time() - start_time) > args.duration:
                print(f"\nDuration reached ({args.duration}s)")
                break

            try:
                data = ser.read(4096)
                if not data:
                    time.sleep(0.01)
                    continue

                text = data.decode('utf-8', errors='replace')
                rawfile.write(text)
                buf += text

                while '\n' in buf:
                    line, buf = buf.split('\n', 1)
                    line = line.strip()
                    if not line:
                        continue

                    now = datetime.now(timezone.utc).isoformat(timespec='milliseconds')

                    # Detect cycle starts for walk-mode distance tracking
                    cycle = parse_cycle_start(line)
                    if cycle is not None:
                        cycle_count += 1
                        print(f"  CYCLE {cycle} START at +{time.time() - start_time:.0f}s")

                    # Harmonized 23-field PKT line
                    pkt = parse_pkt_line(line)
                    if pkt:
                        # HOST-3: Inject session_id into PKT line and parsed dict
                        line = inject_session_id_into_pkt(line, session_id)
                        pkt['session_id'] = session_id

                        # Compute distance
                        distance_m = args.distance
                        if args.walk and args.base_lat is not None and args.base_lon is not None:
                            lat = pkt.get('gps_lat')
                            lon = pkt.get('gps_lon')
                            if lat and lon and isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                                distance_m = round(haversine(args.base_lat, args.base_lon, lat, lon), 1)

                        row = [now] + [str(pkt[f]) for f in PKT_FIELDS] + [
                            distance_m, args.env, args.notes, line,
                        ]
                        writer.writerow(row)
                        pkt_count += 1
                        if pkt_count % 100 == 0:
                            print(f"  PKT {pkt_count} seq={pkt['seq']} "
                                  f"rssi={pkt['rssi_dbm']}dBm d={distance_m}m",
                                  file=sys.stderr)
                        continue

                    # Non-PKT lines echo
                    if line.strip():
                        print(line)

            except serial.SerialException as e:
                print(f"Serial error: {e}", file=sys.stderr)
                break

    elapsed = time.time() - start_time
    print(f"\n=== Sweep capture complete ===")
    print(f"  Duration:  {elapsed:.0f}s")
    print(f"  PKT lines: {pkt_count}")
    print(f"  Cycles:    {cycle_count}")
    print(f"  CSV:       {csv_path}")
    print(f"  RAW:       {raw_path}")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.")