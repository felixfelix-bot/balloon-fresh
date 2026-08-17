#!/usr/bin/env python3
"""Capture ESP32-C3 range-test RX serial output to a raw log file.

Uses BoardSerial (repo mandate) — honors the balloon board hard-lock sentinel.
Logs every line with a wall-clock + monotonic timestamp prefix so window
timing can be reconstructed later.

Usage: rx_capture.py PORT OUTFILE DURATION_SEC [BAUD]
"""
import sys
import time
import datetime

sys.path.insert(0, "/home/c03rad0r/repos/balloon-fresh/tools")
from board_serial import BoardSerial  # noqa: E402


def main():
    port = sys.argv[1]
    outfile = sys.argv[2]
    duration = float(sys.argv[3])
    baud = int(sys.argv[4]) if len(sys.argv) > 4 else 115200

    ser = BoardSerial(port, baud, timeout=1)
    t_end = time.monotonic() + duration
    n_lines = 0
    with open(outfile, "ab", buffering=0) as f:
        while time.monotonic() < t_end:
            try:
                line = ser.readline()
            except Exception as e:  # serial drop etc.
                f.write(f"[capture] read error: {e!r}\n".encode())
                time.sleep(1)
                continue
            if not line:
                continue
            ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            mono = time.monotonic()
            f.write(f"[{ts} {mono:10.2f}] ".encode() + line)
            n_lines += 1
    ser.close()
    print(f"captured {n_lines} lines in {duration:.0f}s -> {outfile}")


if __name__ == "__main__":
    main()
