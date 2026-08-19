#!/usr/bin/env python3
"""rx_range_logger.py — C3/ESP32 serial RX logger for harmonized 23-field PKT format

Reads serial output from C3 range test firmware, logs PKT lines to CSV.
Parses the harmonized 23-field PKT format via the shared pkt_parser module.

Usage:
    python3 scripts/rx_range_logger.py /dev/ttyACM0 [--baud 2000000] [--out ../data/]
"""

import argparse
import csv
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial", file=sys.stderr)
    sys.exit(1)

# Shared PKT parser from tools/
TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))
from pkt_parser import parse_pkt_line, PKT_FIELDS, PKT_CSV_HEADER  # noqa: E402

# Additional columns appended after PKT fields
EXTRA_COLUMNS = ['raw_line']
CSV_COLUMNS = ['timestamp_iso'] + PKT_FIELDS + EXTRA_COLUMNS


def auto_detect_port():
    candidates = []
    for port in serial.tools.list_ports.comports():
        if '303a:1001' in (port.hwid or '') or 'Espressif' in (port.manufacturer or ''):
            candidates.append(port.device)
    for p in sorted(candidates):
        return p
    return None


def find_port(arg_port):
    if arg_port:
        return arg_port
    port = auto_detect_port()
    if port:
        print(f"Auto-detected: {port}", file=sys.stderr)
        return port
    print("No Espressif device found. Use --port /dev/ttyACMx", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='C3/ESP32 RX logger for harmonized 23-field PKT format')
    parser.add_argument('--port', help='Serial port (auto-detect if omitted)')
    parser.add_argument('--baud', type=int, default=2000000,
                        help='Baud rate (default: 2000000 for C3)')
    parser.add_argument('--out', default='data',
                        help='Output directory (default: data/)')
    parser.add_argument('--duration', type=int, default=0,
                        help='Stop after N seconds (0=forever)')
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = out_dir / f'range_packets_{ts}.csv'
    raw_path = out_dir / f'range_raw_{ts}.txt'

    port = find_port(args.port)
    ser = serial.Serial(port, args.baud, timeout=0.5)

    pkt_count = 0
    start_time = time.time()

    with open(csv_path, 'w', newline='') as csvfile, open(raw_path, 'w') as rawfile:
        writer = csv.writer(csvfile)
        writer.writerow(CSV_COLUMNS)

        print(f"Logging {port} -> {csv_path}", file=sys.stderr)
        print(f"Raw output -> {raw_path}", file=sys.stderr)
        print(f"Duration: {'forever' if args.duration == 0 else f'{args.duration}s'}",
              file=sys.stderr)
        print("Press Ctrl+C to stop\n", file=sys.stderr)

        buf = ''
        while True:
            if args.duration > 0 and (time.time() - start_time) > args.duration:
                print(f"\nDuration reached ({args.duration}s)", file=sys.stderr)
                break

            try:
                data = ser.read(4096)
                if not data:
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

                    # Harmonized 23-field PKT line
                    pkt = parse_pkt_line(line)
                    if pkt:
                        row = [now] + [str(pkt[f]) for f in PKT_FIELDS] + [line]
                        writer.writerow(row)
                        pkt_count += 1
                        if pkt_count % 100 == 0:
                            print(f"  PKT {pkt_count} seq={pkt['seq']} "
                                  f"rssi={pkt['rssi_dbm']}", file=sys.stderr)
                        continue

                    # Pass non-PKT lines through to terminal
                    print(line)

            except serial.SerialException:
                print("Serial disconnected!", file=sys.stderr)
                break

    elapsed = time.time() - start_time
    print(f"\n=== {pkt_count} PKT lines logged in {elapsed:.0f}s ===", file=sys.stderr)
    print(f"CSV: {csv_path}", file=sys.stderr)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.", file=sys.stderr)