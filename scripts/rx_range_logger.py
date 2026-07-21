#!/usr/bin/env python3
"""
RX Range Logger Daemon — 24/7 continuous capture with log rotation.

Features:
- Auto-detects RX board (F242D) by serial number
- Auto-reconnects on disconnect/reboot
- Rotates log files at --max-size (default 5MB)
- Cleans up old logs beyond --max-logs (default 500)
- Designed to run as systemd service (never exits)

Usage:
    python3 rx_range_logger.py [--port /dev/ttyACM2] [--baud 115200]
                                [--outdir /var/log/rx-logger]
                                [--max-size-mb 5] [--max-logs 500]

Output files (rotated):
    range_test_YYYYMMDD_HHMMSS.log  — raw serial output with timestamps
    range_test_YYYYMMDD_HHMMSS.csv  — parsed: timestamp,n,seq,rssi
"""
import serial
import time
import sys
import os
import subprocess
import signal
import glob
import logging
from datetime import datetime, timezone

# ─── Config ──────────────────────────────────────────────────────────
RX_SERIAL = "E663B035977F242D"
DEFAULT_OUTDIR = "/var/log/rx-logger"
MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_LOGS = 500

# ─── Logging (stderr → journald) ─────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("rx-logger")

# ─── Board detection ─────────────────────────────────────────────────
def find_rx_port():
    """Find F242D by udev serial number. Returns port path or None."""
    try:
        ports = subprocess.check_output(
            "ls /dev/ttyACM* 2>/dev/null", shell=True, text=True
        ).strip().split()
    except subprocess.CalledProcessError:
        return None

    for port in ports:
        port = port.strip()
        if not port:
            continue
        try:
            info = subprocess.check_output(
                ["udevadm", "info", "-q", "property", port],
                text=True, stderr=subprocess.DEVNULL,
            )
            if RX_SERIAL in info:
                return port
        except subprocess.CalledProcessError:
            pass
    return None


def wait_for_board(timeout_s=0):
    """Block until RX board is found. timeout_s=0 = wait forever."""
    waited = 0
    while True:
        port = find_rx_port()
        if port:
            return port
        if timeout_s > 0 and waited >= timeout_s:
            return None
        if waited % 30 == 0:
            log.info(f"Waiting for RX board ({RX_SERIAL})... ({waited}s)")
        time.sleep(5)
        waited += 5


# ─── Log rotation ────────────────────────────────────────────────────
class RotatingLogger:
    def __init__(self, outdir, max_bytes, max_files):
        self.outdir = outdir
        self.max_bytes = max_bytes
        self.max_files = max_files
        self.log_file = None
        self.csv_file = None
        self.log_path = None
        self.csv_path = None
        self.current_size = 0
        os.makedirs(outdir, exist_ok=True)
        self._new_files()

    def _new_files(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = os.path.join(self.outdir, f"range_test_{ts}.log")
        self.csv_path = os.path.join(self.outdir, f"range_test_{ts}.csv")
        self.log_file = open(self.log_path, "a")
        self.csv_file = open(self.csv_path, "a")
        self.csv_file.write("timestamp_iso,n,seq,rssi_dbm\n")
        self.csv_file.flush()
        self.current_size = 0
        log.info(f"New log: {self.log_path}")

    def _rotate(self):
        """Close current files, clean up old, open new."""
        if self.log_file:
            self.log_file.close()
        if self.csv_file:
            self.csv_file.close()
        self._cleanup_old()
        self._new_files()

    def _cleanup_old(self):
        """Keep only the most recent max_files log/csv pairs."""
        log_files = sorted(
            glob.glob(os.path.join(self.outdir, "range_test_*.log")),
            key=os.path.getmtime,
        )
        while len(log_files) > self.max_files:
            oldest = log_files.pop(0)
            try:
                os.remove(oldest)
                # Also remove matching csv
                csv = oldest.replace(".log", ".csv")
                if os.path.exists(csv):
                    os.remove(csv)
                log.info(f"Cleaned old: {os.path.basename(oldest)}")
            except OSError:
                pass

    def write(self, line_text, is_packet=False, n=0, seq=0, rssi=0):
        """Write a line. Rotates if exceeding max size."""
        ts = datetime.now(timezone.utc)
        ts_iso = ts.isoformat(timespec="milliseconds")

        # Raw log line
        log_line = f"{ts_iso} | {line_text}\n"
        self.log_file.write(log_line)
        self.log_file.flush()
        self.current_size += len(log_line)

        # CSV for packets
        if is_packet:
            self.csv_file.write(f"{ts_iso},{n},{seq},{rssi}\n")
            self.csv_file.flush()
            self.current_size += len(ts_iso) + 30  # approx

        # Check rotation
        if self.current_size >= self.max_bytes:
            log.info(
                f"Rotating at {self.current_size / 1024 / 1024:.1f} MB"
            )
            self._rotate()


# ─── Main daemon loop ────────────────────────────────────────────────
def run(port, baud, outdir, max_bytes, max_files):
    """Connect to board and log forever. Reconnects on failure."""
    logger = RotatingLogger(outdir, max_bytes, max_files)

    pkt_count = 0
    rssi_sum = 0
    rssi_min = 0
    rssi_max = -128
    last_report = time.time()
    pkts_last_report = 0
    buf = b""

    log.info(f"Connecting to {port} @ {baud} baud")
    try:
        ser = serial.Serial(port, baud, timeout=0.5)
    except Exception as e:
        log.error(f"Failed to open {port}: {e}")
        return False  # caller retries

    log.info(f"Connected. Logging to {outdir}")

    while True:
        try:
            data = ser.read(4096)
            if not data:
                # Check if port still exists
                if not os.path.exists(port):
                    log.warning(f"Port {port} disappeared")
                    ser.close()
                    return False
                continue

            buf += data

            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip(b"\r").decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                is_pkt = line.startswith("PKT,")
                n = seq = rssi = 0

                if is_pkt:
                    parts = line.split(",")
                    if len(parts) >= 4:
                        try:
                            n = int(parts[1])
                            seq = int(parts[2])
                            rssi = int(parts[3])
                            pkt_count += 1
                            rssi_sum += rssi
                            if rssi < rssi_min:
                                rssi_min = rssi
                            if rssi > rssi_max:
                                rssi_max = rssi
                        except ValueError:
                            is_pkt = False

                logger.write(line, is_pkt, n, seq, rssi)

                # Periodic console (→ journald)
                current = time.time()
                if current - last_report >= 10.0:
                    delta = pkt_count - pkts_last_report
                    rate = delta / (current - last_report)
                    rssi_avg = rssi_sum / pkt_count if pkt_count > 0 else 0
                    log.info(
                        f"total={pkt_count} rate={rate:.1f}/s "
                        f"rssi_avg={rssi_avg:.0f}dBm "
                        f"min={rssi_min} max={rssi_max}"
                    )
                    last_report = current
                    pkts_last_report = pkt_count

        except serial.SerialException as e:
            log.error(f"Serial error: {e}")
            try:
                ser.close()
            except Exception:
                pass
            return False
        except OSError as e:
            log.error(f"OS error: {e}")
            try:
                ser.close()
            except Exception:
                pass
            return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description="RX Range Logger Daemon")
    parser.add_argument("--port", help="Serial port (auto-detect if not given)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--outdir", default=DEFAULT_OUTDIR)
    parser.add_argument("--max-size-mb", type=float, default=5.0)
    parser.add_argument("--max-logs", type=int, default=MAX_LOGS)
    args = parser.parse_args()

    max_bytes = int(args.max_size_mb * 1024 * 1024)

    log.info(f"RX Logger Daemon starting")
    log.info(f"outdir={args.outdir} max_size={args.max_size_mb}MB max_logs={args.max_logs}")

    # Signal handler for clean shutdown
    def handle_signal(sig, frame):
        log.info("Received signal — stopping")
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Main reconnect loop — runs forever
    while True:
        port = args.port or wait_for_board()
        if not port:
            log.warning("Board not found, retrying in 10s...")
            time.sleep(10)
            continue

        ok = run(port, args.baud, args.outdir, max_bytes, args.max_logs)
        if not ok:
            log.info("Reconnecting in 5s...")
            time.sleep(5)


if __name__ == "__main__":
    main()
