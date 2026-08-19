#!/usr/bin/env python3
"""
capture_rx_sweep.py — Flash verification capture.

Opens RX serial, sends SET_TIME sync every 10s, captures raw output for N seconds.
Also monitors TX serial (optional) for heartbeat confirmation.

Usage:
  python3 capture_rx_sweep.py --rx /dev/ttyACM1 --tx /dev/ttyACM3 --duration 300 \
      --out ~/worktrees/balloon-range-tests/data/v4-channel-sweep/rx_sweep_fixed_HHMMSS.log
"""
import argparse
import serial
import sys
import time
from datetime import datetime


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rx", required=True, help="RX serial port")
    ap.add_argument("--tx", default=None, help="TX serial port (optional monitor)")
    ap.add_argument("--duration", type=int, default=300)
    ap.add_argument("--out", required=True, help="Output .log file path")
    ap.add_argument("--baud", type=int, default=2000000)
    ap.add_argument("--sync-interval", type=float, default=10.0)
    args = ap.parse_args()

    # Open RX serial
    print(f"Opening RX on {args.rx}...", file=sys.stderr, flush=True)
    rx = serial.Serial(args.rx, args.baud, timeout=0.5)
    time.sleep(0.5)
    # Drain any startup output
    startup = rx.read(4096)
    if startup:
        print(f"RX startup banner ({len(startup)} bytes):", file=sys.stderr, flush=True)
        print(startup.decode("ascii", errors="replace")[:500], file=sys.stderr, flush=True)

    # Open TX serial (monitor only)
    tx = None
    if args.tx:
        try:
            print(f"Opening TX on {args.tx} (monitor)...", file=sys.stderr, flush=True)
            tx = serial.Serial(args.tx, args.baud, timeout=0.5)
            time.sleep(0.5)
            tx_startup = tx.read(4096)
            if tx_startup:
                print(f"TX startup ({len(tx_startup)} bytes):", file=sys.stderr, flush=True)
                print(tx_startup.decode("ascii", errors="replace")[:500], file=sys.stderr, flush=True)
        except Exception as e:
            print(f"TX monitor unavailable: {e}", file=sys.stderr, flush=True)
            tx = None

    # Open output file
    with open(args.out, "w") as logf:
        def send_sync():
            ts = int(time.time())
            cmd = f"SET_TIME {ts}\n"
            rx.write(cmd.encode("ascii"))
            logf.write(f"### SENT: {cmd.strip()}\n")
            logf.flush()
            print(f"  [sync] SET_TIME {ts} ({datetime.now().strftime('%H:%M:%S')})", file=sys.stderr, flush=True)

        # Initial sync
        send_sync()
        time.sleep(1.0)

        # Capture loop
        start = time.time()
        last_sync = start
        tx_lines = 0
        rx_lines = 0

        print(f"Capturing for {args.duration}s... (Ctrl-C to stop early)", file=sys.stderr, flush=True)
        print("-" * 60, file=sys.stderr, flush=True)

        try:
            while time.time() - start < args.duration:
                elapsed = time.time() - start

                # Resync
                if time.time() - last_sync >= args.sync_interval:
                    send_sync()
                    last_sync = time.time()

                # Read RX
                data = rx.read(4096)
                if data:
                    text = data.decode("ascii", errors="replace")
                    logf.write(text)
                    logf.flush()
                    for line in text.splitlines():
                        if line.strip():
                            rx_lines += 1
                            if "PHASE_RESULT" in line or "CYCLE" in line:
                                print(f"  [{elapsed:6.1f}s] RX: {line.strip()[:120]}", file=sys.stderr, flush=True)

                # Read TX (monitor)
                if tx:
                    tx_data = tx.read(2048)
                    if tx_data:
                        tx_text = tx_data.decode("ascii", errors="replace")
                        logf.write(f"### TX: {tx_text}")
                        logf.flush()
                        for line in tx_text.splitlines():
                            if line.strip():
                                tx_lines += 1

            elapsed = time.time() - start
            print("-" * 60, file=sys.stderr, flush=True)
            print(f"Capture complete: {elapsed:.1f}s, {rx_lines} RX lines, {tx_lines} TX lines", file=sys.stderr, flush=True)
            print(f"Output: {args.out}", file=sys.stderr, flush=True)

        except KeyboardInterrupt:
            elapsed = time.time() - start
            print(f"\nStopped early: {elapsed:.1f}s, {rx_lines} RX lines", file=sys.stderr, flush=True)

    rx.close()
    if tx:
        tx.close()


if __name__ == "__main__":
    main()
