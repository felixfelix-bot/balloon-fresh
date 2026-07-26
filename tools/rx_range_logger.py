#!/usr/bin/env python3
"""
rx_range_logger.py — Serial RX logger for LR2021 FLRC range tests

Reads serial output from rp2040-range-rx-auto firmware, logs to CSV.
Validates RSSI values — flags phantom data (constant 36, 0, or -127).

Usage:
    python3 rx_range_logger.py /dev/ttyACM0 [--baud 115200] [--out data/]

Output: data/range_test_<timestamp>.csv with columns:
    timestamp, line_type, seq, rssi, raw_line
"""

import argparse
import csv
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial", file=sys.stderr)
    sys.exit(1)

# BoardSerial wrapper for flock enforcement
BOARD_SERIAL_PATH = os.path.expanduser("~/repos/balloon-fresh/tools")
if BOARD_SERIAL_PATH not in sys.path:
    sys.path.insert(0, BOARD_SERIAL_PATH)
try:
    from board_serial import BoardSerial as Serial
except ImportError:
    # Fall back to raw serial if board_serial not available
    Serial = serial.Serial

# Phantom RSSI values from old SX1280 opcode bug
PHANTOM_RSSI = {0, 36, -127}

# Regex patterns
PKT_PATTERN = re.compile(r'PKT (\d+) seq=(\d+) rssi=(-?\d+)')
RESULT_PATTERN = re.compile(r'RANGE_RESULT_RX,(.+)')


def parse_result_fields(kv_str):
    """Parse RANGE_RESULT_RX key=val,key=val line"""
    fields = {}
    for pair in kv_str.split(','):
        if '=' in pair:
            k, v = pair.split('=', 1)
            fields[k.strip()] = v.strip()
    return fields


def is_phantom_rssi(rssi):
    """Check if RSSI value is phantom (SX1280 bug artifact)"""
    return rssi in PHANTOM_RSSI


def main():
    parser = argparse.ArgumentParser(description='LR2021 FLRC range test RX logger')
    parser.add_argument('port', help='Serial port (e.g. /dev/ttyACM0)')
    parser.add_argument('--baud', type=int, default=115200)
    parser.add_argument('--out', default='data', help='Output directory')
    parser.add_argument('--duration', type=int, default=0, help='Stop after N seconds (0=forever)')
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = out_dir / f'range_test_{timestamp}.csv'
    raw_path = out_dir / f'range_test_{timestamp}.raw'

    ser = Serial(args.port, args.baud, timeout=1.0)
    print(f"Logging {args.port} -> {csv_path}")
    print(f"Raw output -> {raw_path}")
    print(f"Duration: {'forever' if args.duration == 0 else f'{args.duration}s'}")
    print("Ctrl+C to stop\n")

    pkt_count = 0
    result_count = 0
    phantom_count = 0
    start_time = time.time()

    with open(csv_path, 'w', newline='') as csvfile, open(raw_path, 'w') as rawfile:
        writer = csv.writer(csvfile)
        writer.writerow(['timestamp', 'type', 'seq', 'rssi', 'burst', 'rx',
                         'unique', 'lost', 'per', 'throughput_kbps',
                         'rssi_avg', 'rssi_min', 'bitrate', 'raw'])

        buf = ''
        while True:
            if args.duration > 0 and (time.time() - start_time) > args.duration:
                print(f"\nDuration reached ({args.duration}s)")
                break

            data = ser.read(256)
            if not data:
                continue

            text = data.decode('ascii', errors='replace')
            rawfile.write(text)
            buf += text

            while '\n' in buf:
                line, buf = buf.split('\n', 1)
                line = line.strip()
                if not line:
                    continue

                now = datetime.now().isoformat(timespec='milliseconds')

                # Per-packet line
                m = PKT_PATTERN.search(line)
                if m:
                    pkt_num = int(m.group(1))
                    seq = int(m.group(2))
                    rssi = int(m.group(3))

                    if is_phantom_rssi(rssi):
                        phantom_count += 1
                        if phantom_count <= 5 or phantom_count % 100 == 0:
                            print(f"  [WARN] Phantom RSSI={rssi} on pkt {pkt_num} "
                                  f"(count={phantom_count}) — firmware bug?")

                    writer.writerow([now, 'PKT', seq, rssi, '', '', '', '',
                                     '', '', '', '', '', line])
                    pkt_count += 1
                    if pkt_count % 100 == 0:
                        print(f"  PKT {pkt_count} seq={seq} rssi={rssi}")
                    continue

                # Result summary line
                m = RESULT_PATTERN.search(line)
                if m:
                    fields = parse_result_fields(m.group(1))
                    rssi_avg = float(fields.get('rssi_avg', 0))

                    if is_phantom_rssi(int(rssi_avg)):
                        print(f"  [WARN] Phantom rssi_avg={rssi_avg} in RESULT "
                              f"— RSSI still broken!")

                    writer.writerow([
                        now, 'RESULT', '',
                        int(rssi_avg) if rssi_avg else '',
                        fields.get('burst', fields.get('window', '')),
                        fields.get('rx', ''),
                        fields.get('unique', ''),
                        fields.get('lost', ''),
                        fields.get('per', ''),
                        fields.get('throughput_kbps', ''),
                        rssi_avg,
                        fields.get('rssi_min', ''),
                        fields.get('bitrate', ''),
                        line
                    ])
                    result_count += 1
                    print(f"\n  RESULT #{result_count}: rx={fields.get('rx', '?')} "
                          f"unique={fields.get('unique', '?')} "
                          f"per={fields.get('per', '?')} "
                          f"rssi_avg={rssi_avg} "
                          f"tput={fields.get('throughput_kbps', '?')}")
                    continue

    elapsed = time.time() - start_time
    print(f"\n=== Session complete ===")
    print(f"Duration: {elapsed:.0f}s")
    print(f"Packets logged: {pkt_count}")
    print(f"Result summaries: {result_count}")
    print(f"Phantom RSSI warnings: {phantom_count}")
    print(f"CSV: {csv_path}")
    print(f"Raw: {raw_path}")

    if phantom_count > 0:
        print(f"\n[!] {phantom_count} phantom RSSI values detected!")
        print("    RSSI firmware fix may not be applied. Check build env.")
    elif pkt_count > 0:
        print("\n[OK] No phantom RSSI values — fix verified working.")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.")
    except serial.SerialException as e:
        print(f"Serial error: {e}", file=sys.stderr)
        sys.exit(1)
