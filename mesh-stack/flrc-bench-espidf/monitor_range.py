#!/usr/bin/env python3
"""Range test serial monitor with dual CSV logging (harmonized 23-field PKT format).

Reads serial output, parses 23-field PKT lines via shared pkt_parser module,
and writes per-packet and summary CSVs.

Output files in script directory:
  - range_packets_<ts>.csv (per-packet data)
  - range_summary_<ts>.csv (RESULT windows)
"""

import serial
import serial.tools.list_ports
import sys
import os
import time
import argparse
import signal
import csv
from datetime import datetime, timezone
from pathlib import Path

# Shared PKT parser from tools/
TOOLS_DIR = Path(__file__).resolve().parent.parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))
from pkt_parser import parse_pkt_line, PKT_FIELDS  # noqa: E402

PKT_CSV_COLUMNS = ['timestamp_iso'] + PKT_FIELDS + ['raw_line']


def auto_detect_port():
    candidates = []
    for port in serial.tools.list_ports.comports():
        if 'Espressif' in (port.manufacturer or '') or '303a:1001' in (port.hwid or ''):
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
    parser = argparse.ArgumentParser(description="Range test monitor (23-field PKT)")
    parser.add_argument("--port", help="Serial port (auto-detect if omitted)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate")
    args = parser.parse_args()

    port = find_port(args.port)
    ser = serial.Serial(port, args.baud, timeout=0.5)

    ts = time.strftime("%Y%m%d_%H%M%S")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    pkt_path = os.path.join(base_dir, f"range_packets_{ts}.csv")
    sum_path = os.path.join(base_dir, f"range_summary_{ts}.csv")

    pkt_file = open(pkt_path, "w", newline='')
    sum_file = open(sum_path, "w", newline='')
    pkt_writer = csv.writer(pkt_file)
    sum_writer = csv.writer(sum_file)

    # Write headers
    pkt_writer.writerow(PKT_CSV_COLUMNS)
    sum_writer.writerow([
        'timestamp', 'loop', 'window_id', 'window_name', 'mode',
        'freq_mhz', 'bitrate_kbps', 'sf', 'bw_khz', 'cr', 'power_dbm',
        'pkt_size', 'tx_sent', 'rx_received', 'crc_errors', 'per_pct',
        'ber_pct', 'avg_rssi', 'min_rssi', 'max_rssi', 'elapsed_ms',
        'throughput_kbps', 'gps_fix', 'gps_lat', 'gps_lon', 'gps_alt_m',
        'gps_sats', 'gps_hdop',
    ])
    pkt_file.flush()
    sum_file.flush()

    pkt_count = 0
    sum_count = 0

    def cleanup(signum=None, frame=None):
        ser.close()
        pkt_file.close()
        sum_file.close()
        print(f"\n=== {pkt_count} packets, {sum_count} windows logged ===", file=sys.stderr)
        print(f"  PKT CSV: {pkt_path}", file=sys.stderr)
        print(f"  SUM CSV: {sum_path}", file=sys.stderr)
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print(f"Logging to {pkt_path} and {sum_path}", file=sys.stderr)
    print("Press Ctrl+C to stop\n", file=sys.stderr)

    while True:
        try:
            while ser.in_waiting:
                line = ser.readline().decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                print(line)

                if line.startswith("PKT,"):
                    now = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
                    pkt = parse_pkt_line(line)
                    if pkt:
                        row = [now] + [str(pkt[f]) for f in PKT_FIELDS] + [line]
                        pkt_writer.writerow(row)
                        pkt_count += 1

                elif line.startswith("RESULT,"):
                    now = time.strftime("%H:%M:%S")
                    fields = line[7:]
                    sum_writer.writerow([now] + fields.split(','))
                    sum_file.flush()
                    sum_count += 1

                    parts = fields.split(",")
                    if len(parts) >= 15:
                        name = parts[2]
                        recv = parts[13]
                        per = parts[15]
                        rssi = parts[17]
                        status = "OK" if float(per) == 0 else "DEGRADED" if float(per) < 50 else "FAIL"
                        print(f"  >> {name}: {recv} rx, PER={per}%, RSSI={rssi} [{status}]", file=sys.stderr)

        except OSError:
            print("Serial disconnected!", file=sys.stderr)
            cleanup()


if __name__ == "__main__":
    main()