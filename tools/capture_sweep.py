#!/usr/bin/env python3
"""
capture_sweep.py — Live capture + parse LR2021 sweep data from serial port.

Reads RX board serial output, parses result lines in real-time,
appends to unified CSV. Supports GPS time correlation.

Usage:
    # Basic capture (5 min, distance=1m, indoor)
    python3 capture_sweep.py --port /dev/ttyACM3 --distance 1 --los N \\
        --duration 300 --output results.csv

    # With GPS time injection (from u-blox GPS on TX board)
    python3 capture_sweep.py --port /dev/ttyACM3 --distance 50 --los Y \\
        --gps-port /dev/ttyUSB0 --output outdoor_50m.csv

    # Append to existing CSV
    python3 capture_sweep.py --port /dev/ttyACM3 --distance 100 --los Y \\
        --output outdoor_sweep.csv --append
"""

import sys
import os
import time
import serial
import csv
import argparse
import subprocess
from datetime import datetime, timezone

# Add tools dir to path for parser
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_unified_csv import parse_line, CSV_FIELDS


def get_gps_time(gps_port):
    """Try to read GPS time from u-blox module."""
    try:
        # Use gpsd if available
        result = subprocess.run(
            ['gpspipe', '-w', '-n', '1', '-x', '2'],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0 and result.stdout:
            import json
            for line in result.stdout.strip().split('\n'):
                try:
                    data = json.loads(line)
                    if data.get('class') == 'TP':
                        return datetime.fromtimestamp(
                            data.get('real_sec', time.time()),
                            tz=timezone.utc
                        ).isoformat()
                except (json.JSONDecodeError, KeyError):
                    continue
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: try direct NMEA parse
    try:
        s = serial.Serial(gps_port, 9600, timeout=2)
        for _ in range(20):  # Read up to 20 NMEA sentences
            line = s.readline().decode('ascii', errors='ignore').strip()
            if line.startswith('$GPRMC') or line.startswith('$GNRMC'):
                # $GPRMC,hhmmss.ss,A,...
                parts = line.split(',')
                if len(parts) > 1 and parts[1]:
                    hh = int(parts[1][0:2])
                    mm = int(parts[1][2:4])
                    ss = int(parts[1][4:6])
                    now = datetime.now(timezone.utc)
                    return now.replace(hour=hh, minute=mm, second=ss).isoformat()
        s.close()
    except (serial.SerialException, ValueError, IndexError):
        pass

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Live capture + parse LR2021 sweep data from serial port",
    )
    parser.add_argument("--port", "-p", required=True, help="Serial port (e.g. /dev/ttyACM3)")
    parser.add_argument("--output", "-o", required=True, help="Output CSV file")
    parser.add_argument("--duration", type=int, default=300, help="Capture duration in seconds (default: 300)")
    parser.add_argument("--distance", type=float, required=True, help="TX-RX distance in meters")
    parser.add_argument("--los", default="N", choices=["Y", "N"], help="Line of sight")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--append", "-a", action="store_true", help="Append to existing CSV")
    parser.add_argument("--rx-only", action="store_true", help="Only capture RX-side results")
    parser.add_argument("--gps-port", default="", help="GPS serial port for time correlation")
    parser.add_argument("--gps-time", default="", help="Manual GPS time ISO 8601 (overrides auto)")
    args = parser.parse_args()

    # Set up serial port
    try:
        ser = serial.Serial(args.port, args.baud, timeout=1)
    except serial.SerialException as e:
        print(f"ERROR: Cannot open {args.port}: {e}", file=sys.stderr)
        sys.exit(1)

    # Set up output
    write_header = True
    if args.append and os.path.exists(args.output):
        write_header = False

    outfile = open(args.output, "a" if args.append else "w", newline="")
    writer = csv.DictWriter(outfile, fieldnames=CSV_FIELDS, extrasaction="ignore")
    if write_header:
        writer.writeheader()

    # Get GPS time if available
    gps_time = args.gps_time
    if not gps_time and args.gps_port:
        gps_time = get_gps_time(args.gps_port)
        if gps_time:
            print(f"GPS time: {gps_time}", file=sys.stderr)
        else:
            print("GPS time: unavailable, using system time", file=sys.stderr)

    print(f"Capturing from {args.port} for {args.duration}s...", file=sys.stderr)
    print(f"Distance: {args.distance}m, LOS: {args.los}", file=sys.stderr)
    print(f"Output: {args.output}", file=sys.stderr)
    print("Press Ctrl-C to stop early.", file=sys.stderr)
    print("-" * 40, file=sys.stderr)

    count = 0
    start = time.time()

    try:
        while time.time() - start < args.duration:
            raw = ser.readline()
            if not raw:
                continue

            line = raw.decode('ascii', errors='ignore').strip()
            if not line:
                continue

            # Print all lines for visibility
            print(line, file=sys.stderr)

            # Try to parse
            row = parse_line(line)
            if row is None:
                continue

            # Skip TX rows if rx-only
            if args.rx_only:
                notes = row.get("notes", "")
                if "tx_side" in notes:
                    continue
                if row.get("packets_rx") in ("0", "") and row.get("packets_sent", "0") not in ("0", ""):
                    continue

            # Apply metadata
            row["distance_m"] = args.distance
            row["los"] = args.los
            if gps_time:
                row["timestamp_iso"] = gps_time

            writer.writerow(row)
            outfile.flush()
            count += 1
            print(f"  >>> Parsed row {count}: {row['path']} rx={row.get('packets_rx', '?')}", file=sys.stderr)

    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)

    ser.close()
    outfile.close()

    elapsed = time.time() - start
    print("-" * 40, file=sys.stderr)
    print(f"Captured {count} result rows in {elapsed:.0f}s → {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
