#!/usr/bin/env python3
"""
RX Range Logger — Captures received packets with timestamps + RSSI for GPS correlation.

Usage:
    python3 rx_range_logger.py [--port /dev/ttyACM2] [--bridge /dev/ttyACM1]
                                [--baud 115200] [--outdir .]

Auto-detects RX board (F242D) by serial number if --port not given.
Logs every received packet with millisecond timestamps.
Saves both raw log and parsed CSV.

Output files:
    range_test_YYYYMMDD_HHMMSS.log  — raw serial output with timestamps
    range_test_YYYYMMDD_HHMMSS.csv  — parsed: timestamp,n,seq,rssi

For GPS correlation:
    After the walk, merge this CSV with your phone GPX track by timestamp.
    Each packet gets a distance from the RX base station at that moment.
"""
import serial
import time
import sys
import os
import subprocess
import signal
from datetime import datetime, timezone

def find_rx_port():
    """Find F242D by serial number."""
    try:
        out = subprocess.check_output("ls /dev/ttyACM*", shell=True, text=True).strip().split()
    except subprocess.CalledProcessError:
        return None
    for port in out:
        try:
            info = subprocess.check_output(
                ["udevadm", "info", "-q", "property", port],
                text=True, stderr=subprocess.DEVNULL
            )
            if "E663B035977F242D" in info:
                return port.strip()
        except subprocess.CalledProcessError:
            pass
    return None

def main():
    import argparse
    parser = argparse.ArgumentParser(description="RX Range Logger")
    parser.add_argument("--port", help="Serial port (auto-detect F242D if not given)")
    parser.add_argument("--bridge", help="ESP32 UART bridge port (fallback if CDC dies)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate")
    parser.add_argument("--outdir", default=".", help="Output directory")
    args = parser.parse_args()

    # Determine port
    port = args.port or args.bridge
    if not port:
        port = find_rx_port()
        if port:
            print(f"Auto-detected RX board: {port}")
        else:
            # Fall back to trying bridge
            for p in ["/dev/ttyACM1", "/dev/ttyACM2", "/dev/ttyACM3"]:
                if os.path.exists(p):
                    port = p
                    print(f"No F242D found, trying: {port}")
                    break
    if not port:
        print("ERROR: No serial port found")
        sys.exit(1)

    # Open serial
    try:
        ser = serial.Serial(port, args.baud, timeout=0.1)
    except Exception as e:
        print(f"ERROR opening {port}: {e}")
        sys.exit(1)

    # Create output files
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(args.outdir, exist_ok=True)
    log_path = os.path.join(args.outdir, f"range_test_{timestamp_str}.log")
    csv_path = os.path.join(args.outdir, f"range_test_{timestamp_str}.csv")

    log_file = open(log_path, "w")
    csv_file = open(csv_path, "w")
    csv_file.write("timestamp_iso,n,seq,rssi_dbm\n")
    csv_file.flush()

    print(f"Logging to: {log_path}")
    print(f"CSV:        {csv_path}")
    print(f"Port: {port} @ {args.baud} baud")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")
    print()
    print("Waiting for packets... (Ctrl+C to stop)")
    print()

    # Stats
    pkt_count = 0
    rssi_sum = 0
    rssi_min = 0
    rssi_max = -128
    last_report = time.time()
    pkts_last_report = 0

    def print_summary():
        if pkt_count == 0:
            return
        rssi_avg = rssi_sum / pkt_count if pkt_count > 0 else 0
        elapsed = time.time() - start_time
        rate = pkt_count / elapsed if elapsed > 0 else 0
        print(f"\n{'='*60}")
        print(f"SUMMARY")
        print(f"  Total packets: {pkt_count}")
        print(f"  Duration:      {elapsed:.1f}s")
        print(f"  Avg rate:      {rate:.1f} pkt/s")
        print(f"  RSSI avg/min/max: {rssi_avg:.1f} / {rssi_min} / {rssi_max} dBm")
        print(f"  Log: {log_path}")
        print(f"  CSV: {csv_path}")
        print(f"{'='*60}")

    def signal_handler(sig, frame):
        print("\n\nStopping...")
        log_file.close()
        csv_file.close()
        ser.close()
        print_summary()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    start_time = time.time()
    buf = b""

    while True:
        data = ser.read(4096)
        if not data:
            continue

        buf += data

        # Process complete lines
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            line = line.strip(b"\r").decode("utf-8", errors="replace").strip()
            if not line:
                continue

            # Millisecond-precision UTC timestamp
            now = datetime.now(timezone.utc)
            ts_iso = now.isoformat(timespec="milliseconds")
            ts_epoch = now.timestamp()

            # Write raw log
            log_file.write(f"{ts_iso} | {line}\n")
            log_file.flush()

            # Parse PKT lines: PKT,n,seq,rssi
            if line.startswith("PKT,"):
                parts = line.split(",")
                if len(parts) >= 4:
                    try:
                        n = int(parts[1])
                        seq = int(parts[2])
                        rssi = int(parts[3])

                        csv_file.write(f"{ts_iso},{n},{seq},{rssi}\n")
                        csv_file.flush()

                        pkt_count += 1
                        rssi_sum += rssi
                        if rssi < rssi_min:
                            rssi_min = rssi
                        if rssi > rssi_max:
                            rssi_max = rssi
                    except ValueError:
                        pass

            # Periodic console output
            current = time.time()
            if current - last_report >= 2.0:
                pkts_this_interval = pkt_count - pkts_last_report
                rate = pkts_this_interval / (current - last_report)
                rssi_recent = (
                    rssi_sum / pkt_count if pkt_count > 0 else 0
                )
                print(
                    f"[{ts_iso.split('T')[1]}] "
                    f"total={pkt_count} "
                    f"rate={rate:.1f}/s "
                    f"rssi_avg={rssi_recent:.0f}dBm "
                    f"last={line[:60]}"
                )
                last_report = current
                pkts_last_report = pkt_count

            # Also print burst markers
            if line.startswith("BURST_") or line.startswith("RX_LISTEN") or line.startswith("STATS"):
                print(f"[{ts_iso.split('T')[1]}] {line}")


if __name__ == "__main__":
    main()
