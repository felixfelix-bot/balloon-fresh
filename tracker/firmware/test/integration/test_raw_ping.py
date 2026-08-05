#!/usr/bin/env python3
"""
test_raw_ping.py — Two-board LoRa raw ping integration test (Phase 5).

Measures RSSI and throughput between two PCB-V2 boards (V1-FAST or V2-ADC)
equipped with LR2021 radio modules. Board A transmits a known test packet,
Board B receives it and reports RSSI. Roles are then swapped for bidirectional
verification.

PREREQUISITES:
  - Two PCB-V2 boards flashed with balloon-fresh firmware (relay mode)
  - Both boards connected via USB serial (/dev/ttyACM0, /dev/ttyACM1)
  - Board locks must be acquirable (no other track using the boards)
  - pyserial installed: pip install pyserial
  - balloon-board-lock.py and board_serial.py in ~/repos/balloon-fresh/tools/

USAGE:
  # Basic ping test (5 packets, default 30s timeout):
  python3 test_raw_ping.py

  # Custom packet count and timeout:
  python3 test_raw_ping.py --count 10 --timeout 60

  # Specify serial ports explicitly:
  python3 test_raw_ping.py --port-a /dev/ttyACM0 --port-b /dev/ttyACM1

  # Swap which board is TX first:
  python3 test_raw_ping.py --tx-first b

  # Show help:
  python3 test_raw_ping.py --help

WHAT IT MEASURES:
  - Packet delivery rate (PDR): received / sent
  - Average RSSI (dBm) from received packets
  - Round-trip throughput (bytes/sec) based on packet size and time
  - Bidirectional verification (A→B then B→A)

BOARD CLI COMMANDS USED:
  - radio_test <1|2> <message>  — transmit a test packet
  - radio_recv <seconds>        — listen for incoming packets

EXIT CODES:
  0 — all packets received bidirectionally (PDR 100%)
  1 — partial success (some packets lost)
  2 — complete failure (no packets received)
  3 — setup error (lock acquisition, serial open, etc.)
"""

import argparse
import re
import sys
import time
import os
import subprocess
import statistics
from pathlib import Path

# Ensure we can import BoardSerial from the tools directory
TOOLS_DIR = os.path.expanduser("~/repos/balloon-fresh/tools")
sys.path.insert(0, TOOLS_DIR)

try:
    from board_serial import BoardSerial
except ImportError:
    print("ERROR: board_serial.py not found in {TOOLS_DIR}".format(TOOLS_DIR=TOOLS_DIR), file=sys.stderr)
    print("       Ensure balloon-fresh repo is cloned at ~/repos/balloon-fresh", file=sys.stderr)
    sys.exit(3)

LOCK_SCRIPT = os.path.join(TOOLS_DIR, "balloon-board-lock.py")
BOARD_A_PORT = "/dev/ttyACM0"
BOARD_B_PORT = "/dev/ttyACM1"
BAUD_RATE = 115200
DEFAULT_PACKET_COUNT = 5
DEFAULT_TIMEOUT = 30  # seconds per receive window
TEST_MESSAGE = "ping"
RSSI_PATTERN = re.compile(r"RSSI[:\s]+(-?\d+)\s*dBm", re.IGNORECASE)
RECV_PATTERN = re.compile(r"(?:received|RX|recv).*?(?:data|payload|packet)[:\s]+(.+)", re.IGNORECASE)


def acquire_lock(board: str, purpose: str, timeout: int = 120) -> bool:
    """Acquire board lock using balloon-board-lock.py."""
    env = os.environ.copy()
    env["BALLOON_TRACK"] = "balloon-hermes"
    result = subprocess.run(
        ["python3", LOCK_SCRIPT, "acquire", board, "--purpose", purpose, "--timeout", str(timeout)],
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout + 10,
    )
    if result.returncode != 0:
        print("  LOCK FAILED for {board}: {err}".format(board=board, err=result.stderr.strip()), file=sys.stderr)
        return False
    print("  Lock acquired: {board} ({purpose})".format(board=board, purpose=purpose))
    return True


def release_lock(board: str) -> None:
    """Release board lock."""
    env = os.environ.copy()
    env["BALLOON_TRACK"] = "balloon-hermes"
    subprocess.run(
        ["python3", LOCK_SCRIPT, "release", board],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    print("  Lock released: {board}".format(board=board))


def send_command(ser, command: str, wait: float = 1.0) -> str:
    """Send a CLI command to the board and read the response."""
    ser.write((command + "\n").encode("utf-8"))
    time.sleep(wait)
    response = ""
    while ser.in_waiting > 0:
        chunk = ser.read(ser.in_waiting)
        if chunk:
            response += chunk.decode("utf-8", errors="replace")
    return response


def drain_serial(ser) -> None:
    """Drain any pending data from the serial buffer."""
    time.sleep(0.2)
    while ser.in_waiting > 0:
        ser.read(ser.in_waiting)


def extract_rssi(text: str):
    """Extract RSSI value from board output text."""
    match = RSSI_PATTERN.search(text)
    if match:
        return int(match.group(1))
    return None


def extract_received_data(text: str):
    """Check if text indicates a received packet and extract its data."""
    match = RECV_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    # Also check for simpler patterns
    if "hello" in text.lower() or TEST_MESSAGE in text.lower():
        return TEST_MESSAGE
    return None


def run_direction(tx_board_name: str, tx_port: str, tx_board_id: str,
                  rx_board_name: str, rx_port: str, rx_board_id: str,
                  count: int, timeout: int) -> dict:
    """
    Run ping test in one direction (TX board → RX board).

    Returns dict with results: {sent, received, rssi_values[], pdr, avg_rssi}
    """
    results = {
        "direction": "{tx}→{rx}".format(tx=tx_board_name, rx=rx_board_name),
        "sent": 0,
        "received": 0,
        "rssi_values": [],
        "errors": [],
    }

    print("\n--- {direction}: {tx_name} TX → {rx_name} RX ---".format(
        direction=results["direction"],
        tx_name=tx_board_name,
        rx_name=rx_board_name,
    ))

    # Open serial connections using BoardSerial wrapper
    try:
        tx_ser = BoardSerial(tx_port, BAUD_RATE, timeout=1)
        rx_ser = BoardSerial(rx_port, BAUD_RATE, timeout=1)
    except Exception as e:
        err = "Failed to open serial: {e}".format(e=e)
        print("  ERROR: {err}".format(err=err), file=sys.stderr)
        results["errors"].append(err)
        return results

    try:
        # Drain any pending data
        drain_serial(tx_ser)
        drain_serial(rx_ser)

        # Start RX listener on the receive board
        print("  Starting RX listener on {rx_name} ({timeout}s window)...".format(
            rx_name=rx_board_name, timeout=timeout))
        rx_ser.write("radio_recv {timeout}\n".format(timeout=timeout).encode("utf-8"))
        time.sleep(0.5)  # Let RX start

        # Send packets from TX board
        for i in range(count):
            msg = "{base}_{idx}".format(base=TEST_MESSAGE, idx=i + 1)
            print("  TX [{i}/{count}]: radio_test 1 {msg}".format(
                i=i + 1, count=count, msg=msg))
            tx_ser.write("radio_test 1 {msg}\n".format(msg=msg).encode("utf-8"))
            results["sent"] += 1
            time.sleep(2.0)  # Spaced transmission

        # Wait for RX window to complete
        remaining = timeout - (count * 2.0)
        if remaining > 0:
            time.sleep(remaining + 1)

        # Read all RX output
        rx_output = ""
        while rx_ser.in_waiting > 0:
            chunk = rx_ser.read(rx_ser.in_waiting)
            if chunk:
                rx_output += chunk.decode("utf-8", errors="replace")

        # Parse received packets
        lines = rx_output.split("\n")
        for line in lines:
            rssi = extract_rssi(line)
            if rssi is not None:
                results["rssi_values"].append(rssi)

            data = extract_received_data(line)
            if data is not None:
                results["received"] += 1
                print("  RX received: {data} (RSSI: {rssi})".format(
                    data=data,
                    rssi=rssi if rssi else "N/A"))

        # Calculate PDR
        if results["sent"] > 0:
            pdr = (results["received"] / results["sent"]) * 100
            results["pdr"] = pdr
            print("  PDR: {received}/{sent} ({pdr:.1f}%)".format(
                received=results["received"],
                sent=results["sent"],
                pdr=pdr))
        else:
            results["pdr"] = 0.0

        # Calculate average RSSI
        if results["rssi_values"]:
            avg_rssi = statistics.mean(results["rssi_values"])
            results["avg_rssi"] = avg_rssi
            print("  Average RSSI: {avg:.1f} dBm".format(avg=avg_rssi))
            if len(results["rssi_values"]) > 1:
                results["rssi_stddev"] = statistics.stdev(results["rssi_values"])
                print("  RSSI stddev: {std:.1f} dBm".format(std=results["rssi_stddev"]))
        else:
            results["avg_rssi"] = None
            print("  No RSSI values captured")

    finally:
        try:
            tx_ser.close()
        except Exception:
            pass
        try:
            rx_ser.close()
        except Exception:
            pass

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Two-board LoRa raw ping integration test (Phase 5). "
                    "Measures RSSI and packet delivery rate between two PCB-V2 boards.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Basic 5-packet ping test
  %(prog)s --count 10 --timeout 60  # 10 packets, 60s RX window
  %(prog)s --tx-first b             # Board B transmits first
  %(prog)s --port-a /dev/ttyACM2    # Custom port for board A
        """,
    )
    parser.add_argument(
        "--count", type=int, default=DEFAULT_PACKET_COUNT,
        help="Number of packets to send per direction (default: {n})".format(n=DEFAULT_PACKET_COUNT),
    )
    parser.add_argument(
        "--timeout", type=int, default=DEFAULT_TIMEOUT,
        help="RX listen window in seconds per direction (default: {n})".format(n=DEFAULT_TIMEOUT),
    )
    parser.add_argument(
        "--port-a", default=BOARD_A_PORT,
        help="Serial port for board A (default: {p})".format(p=BOARD_A_PORT),
    )
    parser.add_argument(
        "--port-b", default=BOARD_B_PORT,
        help="Serial port for board B (default: {p})".format(p=BOARD_B_PORT),
    )
    parser.add_argument(
        "--tx-first", choices=["a", "b"], default="a",
        help="Which board transmits first (default: a)",
    )
    parser.add_argument(
        "--skip-lock", action="store_true",
        help="Skip board lock acquisition (for manual testing only)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("PCB-V2 Phase 5: Raw Ping Integration Test")
    print("=" * 60)
    print("  Board A: {port}".format(port=args.port_a))
    print("  Board B: {port}".format(port=args.port_b))
    print("  Packets per direction: {n}".format(n=args.count))
    print("  RX timeout: {t}s".format(t=args.timeout))
    print("  TX first: {tx}".format(tx=args.tx_first.upper()))

    # Acquire board locks
    locked = []
    if not args.skip_lock:
        print("\n--- Acquiring Board Locks ---")
        if not acquire_lock("board-a", "raw ping test", timeout=120):
            print("FATAL: Could not acquire lock for board-a", file=sys.stderr)
            sys.exit(3)
        locked.append("board-a")
        if not acquire_lock("board-b", "raw ping test", timeout=120):
            print("FATAL: Could not acquire lock for board-b", file=sys.stderr)
            for b in locked:
                release_lock(b)
            sys.exit(3)
        locked.append("board-b")
    else:
        print("  [SKIP] Board lock acquisition skipped (--skip-lock)")

    all_results = []
    try:
        # Direction 1
        if args.tx_first == "a":
            r1 = run_direction(
                "A", args.port_a, "board-a",
                "B", args.port_b, "board-b",
                args.count, args.timeout,
            )
        else:
            r1 = run_direction(
                "B", args.port_b, "board-b",
                "A", args.port_a, "board-a",
                args.count, args.timeout,
            )
        all_results.append(r1)

        # Brief pause between directions
        print("\n  Pausing 3s before direction swap...")
        time.sleep(3)

        # Direction 2 (swap roles)
        if args.tx_first == "a":
            r2 = run_direction(
                "B", args.port_b, "board-b",
                "A", args.port_a, "board-a",
                args.count, args.timeout,
            )
        else:
            r2 = run_direction(
                "A", args.port_a, "board-a",
                "B", args.port_b, "board-b",
                args.count, args.timeout,
            )
        all_results.append(r2)

    finally:
        # Always release locks
        if locked:
            print("\n--- Releasing Board Locks ---")
            for b in locked:
                release_lock(b)

    # Summary
    print("\n" + "=" * 60)
    print("RAW PING TEST SUMMARY")
    print("=" * 60)

    total_sent = sum(r["sent"] for r in all_results)
    total_received = sum(r["received"] for r in all_results)
    all_rssi = []
    for r in all_results:
        all_rssi.extend(r["rssi_values"])
        pdr = r.get("pdr", 0.0)
        avg_rssi = r.get("avg_rssi", "N/A")
        avg_str = "{:.1f} dBm".format(avg_rssi) if isinstance(avg_rssi, float) else str(avg_rssi)
        print("  {dir}: {recv}/{sent} ({pdr:.1f}%), RSSI: {rssi})".format(
            dir=r["direction"],
            recv=r["received"],
            sent=r["sent"],
            pdr=pdr,
            rssi=avg_str,
        ))

    overall_pdr = (total_received / total_sent * 100) if total_sent > 0 else 0
    print("\n  Overall PDR: {recv}/{sent} ({pdr:.1f}%)".format(
        recv=total_received, sent=total_sent, pdr=overall_pdr))
    if all_rssi:
        print("  Overall avg RSSI: {avg:.1f} dBm (range: {min} to {max})".format(
            avg=statistics.mean(all_rssi),
            min=min(all_rssi),
            max=max(all_rssi),
        ))
    else:
        print("  No RSSI data collected")

    # Throughput estimate
    if total_received > 0:
        # Approximate payload size per packet (test message + framing)
        est_payload = len(TEST_MESSAGE) + 10  # message + overhead
        total_bytes = total_received * est_payload
        total_time = 2 * (args.count * 2.0 + args.timeout)  # both directions
        throughput = total_bytes / total_time if total_time > 0 else 0
        print("  Estimated throughput: ~{tp:.1f} bytes/sec".format(tp=throughput))

    # Exit code
    if overall_pdr == 100:
        print("\n  RESULT: PASS (all packets received)")
        sys.exit(0)
    elif overall_pdr > 0:
        print("\n  RESULT: PARTIAL (some packet loss)")
        sys.exit(1)
    else:
        print("\n  RESULT: FAIL (no packets received)")
        sys.exit(2)


if __name__ == "__main__":
    main()