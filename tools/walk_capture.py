#!/usr/bin/env python3
"""walk_capture.py — Structured PKT walk-capture tool with 23-field CSV output.

Replaces walk_capture.sh with proper PKT line parsing. Captures serial output
from RX firmware, parses harmonized 23-field PKT lines, and writes structured
CSV. Non-PKT lines go to a raw text log.

Usage:
    python3 tools/walk_capture.py /dev/ttyACM0 [--baud 2000000] [--out data/walk-<date>/]
    python3 tools/walk_capture.py /dev/ttyACM0 --duration 3600
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
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial", file=sys.stderr)
    sys.exit(1)

# Shared PKT parser from tools/
TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
from pkt_parser import parse_pkt_line, PKT_FIELDS  # noqa: E402

PKT_CSV_COLUMNS = ['timestamp_iso'] + PKT_FIELDS + ['raw_line']


class RobustSerial:
    """Serial wrapper with auto-reconnect for walk tests."""

    def __init__(self, port: str, baud: int, timeout: float = 1.0):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self._ser: serial.Serial | None = None
        self._connect()

    def _connect(self):
        attempt = 0
        while True:
            try:
                self._ser = serial.Serial(self.port, self.baud, timeout=self.timeout)
                if attempt > 0:
                    print(f"  [serial] Reconnected to {self.port} after {attempt} attempt(s)",
                          file=sys.stderr)
                return
            except Exception as e:
                attempt += 1
                if attempt <= 3:
                    time.sleep(2)
                else:
                    time.sleep(5)
                if attempt % 10 == 0:
                    print(f"  [serial] Still retrying ({attempt} attempts)...", file=sys.stderr)

    def read(self, size: int = 4096) -> bytes:
        if self._ser is None:
            self._connect()
            return b""
        try:
            data = self._ser.read(size)
            if not data and not self._ser.is_open:
                print(f"  [serial] Port {self.port} disconnected. Reconnecting...",
                      file=sys.stderr)
                self._ser = None
                self._connect()
                return b""
            return data
        except Exception as e:
            print(f"  [serial] Read error: {e}. Reconnecting...", file=sys.stderr)
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None
            time.sleep(2)
            self._connect()
            return b""

    def close(self):
        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None


def main():
    parser = argparse.ArgumentParser(
        description='Structured PKT walk-capture tool with 23-field CSV output')
    parser.add_argument('port', nargs='?', default='/dev/ttyACM0',
                        help='Serial port (default: /dev/ttyACM0)')
    parser.add_argument('--baud', type=int, default=2000000,
                        help='Baud rate (default: 2000000)')
    parser.add_argument('--out', help='Output directory (default: data/walk-<DATE>/)')
    parser.add_argument('--duration', type=int, default=3600,
                        help='Capture duration in seconds (default: 3600)')
    parser.add_argument('--label', default='walk',
                        help='Build/test label for filenames')
    args = parser.parse_args()

    # Output directory
    date_str = datetime.now().strftime('%Y%m%d')
    if args.out:
        out_dir = Path(args.out)
    else:
        out_dir = Path('data') / f'walk-{date_str}'
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime('%H%M%S')
    csv_path = out_dir / f'{args.label}-{date_str}-{ts}.csv'
    raw_path = out_dir / f'{args.label}-{date_str}-{ts}.raw'
    meta_path = out_dir / f'{args.label}-{date_str}-{ts}-meta.txt'

    # Write metadata
    with open(meta_path, 'w') as f:
        f.write(f"# Walk capture metadata\n")
        f.write(f"date={date_str}\n")
        f.write(f"duration_s={args.duration}\n")
        f.write(f"port={args.port}\n")
        f.write(f"baud={args.baud}\n")
        f.write(f"label={args.label}\n")
        f.write(f"started={datetime.now().isoformat()}\n")
        f.write(f"host={os.uname().nodename}\n")

    ser = RobustSerial(args.port, args.baud)

    pkt_count = 0
    start_time = time.time()

    with open(csv_path, 'w', newline='') as csvfile, open(raw_path, 'w') as rawfile:
        writer = csv.writer(csvfile)
        writer.writerow(PKT_CSV_COLUMNS)

        print(f"Walk capture started:")
        print(f"  Port:      {args.port} @ {args.baud} baud")
        print(f"  Duration:  {args.duration}s")
        print(f"  PKT CSV:   {csv_path}")
        print(f"  Raw:       {raw_path}")
        print(f"Press Ctrl+C to stop early.\n")

        buf = ''
        while True:
            elapsed = time.time() - start_time
            if elapsed >= args.duration:
                print(f"\nDuration reached ({args.duration}s)")
                break

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

                # Parse harmonized 23-field PKT line
                pkt = parse_pkt_line(line)
                if pkt:
                    row = [now] + [str(pkt[f]) for f in PKT_FIELDS] + [line]
                    writer.writerow(row)
                    pkt_count += 1
                    if pkt_count % 500 == 0:
                        print(f"  PKT {pkt_count} seq={pkt['seq']} "
                              f"rssi={pkt['rssi_dbm']}dBm")
                else:
                    # Non-PKT lines echo to terminal
                    print(line)

    elapsed = time.time() - start_time
    print(f"\n=== Capture complete ===")
    print(f"  Duration: {elapsed:.0f}s")
    print(f"  PKT lines: {pkt_count}")
    print(f"  CSV: {csv_path}")
    print(f"  RAW: {raw_path}")

    # Update metadata
    with open(meta_path, 'a') as f:
        f.write(f"stopped={datetime.now().isoformat()}\n")
        f.write(f"pkt_lines={pkt_count}\n")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.")