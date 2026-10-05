#!/usr/bin/env python3
"""
test_raw_ping.py — Two-board LoRa raw ping integration test (Phase 5).

Measures packet delivery rate (PDR) and RSSI between two PCB-V2 boards
(V1-FAST or V2-ADC) equipped with LR2021 radio modules. Board A transmits test
packets, Board B listens and reports RSSI; roles are then swapped for
bidirectional verification.

WHAT THE FIRMWARE ACTUALLY DOES (verified against tracker/firmware/main):
  - `radio_test` (main/app_main.cpp:321) IGNORES its arguments and always
    transmits a fixed TELEMETRY_SIZE (28) byte telemetry packet
    (components/telemetry/telemetry.h:6). There is no "send this message"
    path, so this harness verifies PACKET delivery of that telemetry frame —
    not the round-trip of an arbitrary payload string.
  - `radio_recv` (main/app_main.cpp:341) also ignores its argument and listens
    for a hardcoded 30-second window, printing per packet:
        RX <N> bytes, RSSI: <R> dBm, SNR: <S> dB
          HEX: <hex>
        [and, when N == 28 and the CRC validates:]
          Valid telemetry! seq=<seq> voltage=<mv>mV
    and finally `Listen done`.

  Consequently: a received packet is counted ONLY from a real `RX <N> bytes`
  line (optionally corroborated by `Valid telemetry!`). There is NO substring
  / "did the word ping appear" fallback, which would count the TX-side command
  echo as a received packet.

PREREQUISITES:
  - Two PCB-V2 boards flashed with balloon-fresh firmware
  - Both boards connected via USB serial (/dev/ttyACM0, /dev/ttyACM1)
  - Board locks acquirable (no other track using the boards)
  - pyserial installed: pip install pyserial
  - balloon-board-lock.py and board_serial.py in ~/repos/balloon-fresh/tools/

USAGE:
  # Basic ping test (5 packets per direction, 30s RX window):
  python3 test_raw_ping.py

  # Custom packet count:
  python3 test_raw_ping.py --count 10

  # Specify serial ports explicitly:
  python3 test_raw_ping.py --port-a /dev/ttyACM0 --port-b /dev/ttyACM1

  # Swap which board is TX first:
  python3 test_raw_ping.py --tx-first b

  # Show help:
  python3 test_raw_ping.py --help

WHAT IT MEASURES:
  - Packet delivery rate (PDR): received / sent
  - Average / min / max RSSI (dBm) from received packets
  - Sparkline-ish per-packet RSSI list
  - Bidirectional verification (A→B then B→A)

EXIT CODES:
  0 — all packets received bidirectionally (PDR 100%)
  1 — partial success (some packets lost)
  2 — complete failure (no packets received)
  3 — setup error (lock acquisition, serial open, CLI misuse, etc.)

The log parsers below are pure functions so they can be regression-tested on
the host without boards: see tracker/firmware/test/test_integration_parsers.py
"""

import argparse
import os
import re
import statistics
import subprocess
import sys
import time

# Ensure we can import BoardSerial from the tools directory
TOOLS_DIR = os.path.expanduser("~/repos/balloon-fresh/tools")
sys.path.insert(0, TOOLS_DIR)


def load_board_serial():
    """Import BoardSerial lazily.

    Deferred so that `--help` works on a host without pyserial installed
    (board_serial.py imports pyserial at module scope and exits on failure).
    """
    try:
        from board_serial import BoardSerial
    except ImportError:
        print("ERROR: board_serial.py not found in {TOOLS_DIR}".format(TOOLS_DIR=TOOLS_DIR), file=sys.stderr)
        print("       Ensure balloon-fresh repo is cloned at ~/repos/balloon-fresh", file=sys.stderr)
        sys.exit(3)
    return BoardSerial


LOCK_SCRIPT = os.path.join(TOOLS_DIR, "balloon-board-lock.py")
BOARD_A_PORT = "/dev/ttyACM0"
BOARD_B_PORT = "/dev/ttyACM1"
BAUD_RATE = 115200
DEFAULT_PACKET_COUNT = 5
DEFAULT_TIMEOUT = 30  # seconds; matches the firmware's hardcoded listen window
TX_WINDOW_MAX = 30    # firmware hardcodes a 30 s radio_recv window
TX_SPACING = 2.0      # seconds between radio_test transmissions
TELEMETRY_SIZE = 28   # components/telemetry/telemetry.h:6

# Firmware producer formats (main/app_main.cpp cli_cmd_radio_recv, :341):
#   "RX 28 bytes, RSSI: -45 dBm, SNR: 9 dB"
#   "  Valid telemetry! seq=7 voltage=4100mV"
#   "TX test packet (28 bytes)... OK" | "... TIMEOUT"
#   "Listening for 30s...", "Listen done"
RX_LINE_PATTERN = re.compile(
    r"\bRX\s+(\d+)\s+bytes,\s*RSSI:\s*(-?\d+)\s*dBm,\s*SNR:\s*(-?\d+)\s*dB",
    re.IGNORECASE,
)
VALID_TELEMETRY_PATTERN = re.compile(
    r"Valid telemetry!\s*seq=(\d+)\s*voltage=(\d+)mV",
    re.IGNORECASE,
)
TX_RESULT_PATTERN = re.compile(
    r"TX test packet\s*\((\d+)\s*bytes\)\.\.\.\s*(OK|TIMEOUT)",
    re.IGNORECASE,
)


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
    """Release board lock, reporting a failure instead of assuming success."""
    env = os.environ.copy()
    env["BALLOON_TRACK"] = "balloon-hermes"
    try:
        result = subprocess.run(
            ["python3", LOCK_SCRIPT, "release", board],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as e:  # noqa: BLE001 - surfaced, never swallowed
        print("  LOCK RELEASE ERROR for {board}: {e}".format(board=board, e=e), file=sys.stderr)
        return
    if result.returncode != 0:
        print("  LOCK RELEASE FAILED for {board}: {err}".format(
            board=board, err=(result.stderr or result.stdout).strip()), file=sys.stderr)
        return
    print("  Lock released: {board}".format(board=board))


def drain_serial(ser) -> None:
    """Drain any pending data from the serial buffer."""
    time.sleep(0.2)
    while ser.in_waiting > 0:
        ser.read(ser.in_waiting)


def read_until(ser, deadline: float) -> str:
    """Accumulate serial output until `deadline` (monotonic seconds)."""
    out = ""
    while True:
        while ser.in_waiting > 0:
            chunk = ser.read(ser.in_waiting)
            if chunk:
                out += chunk.decode("utf-8", errors="replace")
        if time.monotonic() >= deadline:
            return out
        time.sleep(0.1)


def parse_rx_line(line: str):
    """Return {'len','rssi','snr'} for a real RX announcement, else None.

    Only the firmware's `RX <N> bytes, RSSI: <R> dBm, SNR: <S> dB` line counts.
    A benign substring such as the echoed `radio_test` command is NOT a packet.
    """
    m = RX_LINE_PATTERN.search(line or "")
    if not m:
        return None
    return {"len": int(m.group(1)), "rssi": int(m.group(2)), "snr": int(m.group(3))}


def parse_valid_telemetry(line: str):
    """Return {'seq','voltage_mv'} for a validated telemetry decode, else None."""
    m = VALID_TELEMETRY_PATTERN.search(line or "")
    if not m:
        return None
    return {"seq": int(m.group(1)), "voltage_mv": int(m.group(2))}


def parse_tx_result(line: str):
    """Return (bytes, 'OK'|'TIMEOUT') for a radio_test result line, else None."""
    m = TX_RESULT_PATTERN.search(line or "")
    if not m:
        return None
    return int(m.group(1)), m.group(2).upper()


def run_direction(tx_board_name: str, tx_port: str, rx_board_name: str,
                  rx_port: str, count: int, window: int) -> dict:
    """
    Run the ping test in one direction (TX board → RX board).

    Returns dict with {direction, sent, received, rssi_values[], pdr, avg_rssi}.
    """
    results = {
        "direction": "{tx}\u2192{rx}".format(tx=tx_board_name, rx=rx_board_name),
        "sent": 0,
        "received": 0,
        "telemetry_valid": 0,
        "rssi_values": [],
        "snr_values": [],
        "errors": [],
    }

    print("\n--- {direction}: {tx_name} TX \u2192 {rx_name} RX ---".format(
        direction=results["direction"],
        tx_name=tx_board_name,
        rx_name=rx_board_name,
    ))

    BoardSerial = load_board_serial()
    try:
        tx_ser = BoardSerial(tx_port, BAUD_RATE, timeout=1)
        rx_ser = BoardSerial(rx_port, BAUD_RATE, timeout=1)
    except Exception as e:  # noqa: BLE001 - reported, not fatal to the run
        err = "Failed to open serial: {e}".format(e=e)
        print("  ERROR: {err}".format(err=err), file=sys.stderr)
        results["errors"].append(err)
        return results

    try:
        drain_serial(tx_ser)
        drain_serial(rx_ser)

        # Start the RX listener. The firmware listens for a hardcoded 30 s.
        print("  Starting RX listener on {rx_name} ({w}s firmware window)...".format(
            rx_name=rx_board_name, w=window))
        rx_ser.write(b"radio_recv\n")
        time.sleep(0.5)  # let "Listening for 30s..." arrive

        deadline = time.monotonic() + window
        for i in range(count):
            if time.monotonic() >= deadline:
                print("  WARNING: {w}s RX window elapsed before all {n} packets were sent; "
                      "decrease --count or move the boards closer".format(w=window, n=count))
                break
            print("  TX [{i}/{count}]: radio_test".format(i=i + 1, count=count))
            tx_ser.write(b"radio_test\n")
            results["sent"] += 1
            time.sleep(TX_SPACING)

        rx_output = read_until(rx_ser, deadline)

        # Parse TX-side confirmations (radio_test OK/TIMEOUT).
        tx_confirmations = read_until(tx_ser, time.monotonic() + 0.5)
        for line in tx_confirmations.split("\n"):
            if parse_tx_result(line) is not None:
                size, verdict = parse_tx_result(line)
                if verdict != "OK":
                    results["errors"].append("radio_test reported {v}".format(v=verdict))

        # Parse RX output — only real RX announcements count.
        for line in rx_output.split("\n"):
            rx = parse_rx_line(line)
            if rx is not None:
                results["received"] += 1
                results["rssi_values"].append(rx["rssi"])
                results["snr_values"].append(rx["snr"])
                print("    RX #{n}: {size} bytes, RSSI {rssi} dBm, SNR {snr} dB".format(
                    n=results["received"], size=rx["len"], rssi=rx["rssi"], snr=rx["snr"]))
                continue
            tel = parse_valid_telemetry(line)
            if tel is not None:
                results["telemetry_valid"] += 1

        if "Listen done" not in rx_output:
            results["errors"].append("RX board never printed 'Listen done' — window may "
                                     "have been cut short")

        # Calculate PDR
        if results["sent"] > 0:
            pdr = (results["received"] / results["sent"]) * 100
            results["pdr"] = pdr
            print("  PDR: {received}/{sent} ({pdr:.1f}%)".format(
                received=results["received"],
                sent=results["sent"],
                pdr=pdr))
            if results["telemetry_valid"] != results["received"]:
                print("  NOTE: {v}/{r} received packets validated as telemetry (CRC)".format(
                    v=results["telemetry_valid"], r=results["received"]))
        else:
            results["pdr"] = 0.0

        # Calculate RSSI statistics
        if results["rssi_values"]:
            results["avg_rssi"] = statistics.mean(results["rssi_values"])
            results["min_rssi"] = min(results["rssi_values"])
            results["max_rssi"] = max(results["rssi_values"])
            print("  Average RSSI: {avg:.1f} dBm (range {lo} to {hi})".format(
                avg=results["avg_rssi"],
                lo=results["min_rssi"],
                hi=results["max_rssi"]))
            if len(results["rssi_values"]) > 1:
                results["rssi_stddev"] = statistics.stdev(results["rssi_values"])
                print("  RSSI stddev: {std:.1f} dBm".format(std=results["rssi_stddev"]))
        else:
            results["avg_rssi"] = None
            print("  No RSSI values captured")

    finally:
        for ser in (tx_ser, rx_ser):
            try:
                ser.close()
            except Exception:  # noqa: BLE001 - close best-effort
                pass

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Two-board LoRa raw ping integration test (Phase 5). "
                    "Measures packet delivery rate and RSSI between two PCB-V2 boards. "
                    "The firmware's radio_test sends a fixed {n}-byte telemetry packet, so this "
                    "verifies packet delivery of that frame (not an arbitrary message).".format(
                        n=TELEMETRY_SIZE),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Basic 5-packet ping test
  %(prog)s --count 10               # 10 packets per direction
  %(prog)s --tx-first b             # Board B transmits first
  %(prog)s --port-a /dev/ttyACM2    # Custom port for board A

Note: the RX listen window is fixed at 30 s in the firmware
(main/app_main.cpp cli_cmd_radio_recv), so --timeout is clamped to 30.
        """,
    )
    parser.add_argument(
        "--count", type=int, default=DEFAULT_PACKET_COUNT,
        help="Number of packets to send per direction (default: {n})".format(n=DEFAULT_PACKET_COUNT),
    )
    parser.add_argument(
        "--timeout", type=int, default=DEFAULT_TIMEOUT,
        help="RX listen window in seconds; clamped to the firmware's {w}s cap "
             "(default: {n})".format(w=TX_WINDOW_MAX, n=DEFAULT_TIMEOUT),
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

    # The firmware hardcodes the listen window; be honest about the clamp
    # instead of waiting 60 s for a window the board closes after 30 s.
    window = args.timeout
    if window > TX_WINDOW_MAX:
        print("  WARNING: firmware listens for a hardcoded {w}s (--timeout {t} ignored); "
              "using {w}s".format(w=TX_WINDOW_MAX, t=args.timeout))
        window = TX_WINDOW_MAX
    if args.count < 1:
        print("ERROR: --count must be >= 1", file=sys.stderr)
        sys.exit(3)
    if args.count * TX_SPACING > window:
        print("  WARNING: {n} packets at {s}s spacing exceed the {w}s window; "
              "only the first ~{m} will be sent".format(
                  n=args.count, s=TX_SPACING, w=window, m=int(window // TX_SPACING)))

    print("=" * 60)
    print("PCB-V2 Phase 5: Raw Ping Integration Test")
    print("=" * 60)
    print("  Board A: {port}".format(port=args.port_a))
    print("  Board B: {port}".format(port=args.port_b))
    print("  Packets per direction: {n}".format(n=args.count))
    print("  RX window: {t}s (firmware hardcoded)".format(t=window))
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
        if args.tx_first == "a":
            pairs = [("A", args.port_a, "B", args.port_b), ("B", args.port_b, "A", args.port_a)]
        else:
            pairs = [("B", args.port_b, "A", args.port_a), ("A", args.port_a, "B", args.port_b)]

        for idx, (txn, txp, rxn, rxp) in enumerate(pairs):
            if idx:
                print("\n  Pausing 3s before direction swap...")
                time.sleep(3)
            all_results.append(run_direction(txn, txp, rxn, rxp, args.count, window))
    finally:
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
        avg_rssi = r.get("avg_rssi")
        avg_str = "{:.1f} dBm".format(avg_rssi) if isinstance(avg_rssi, float) else "N/A"
        print("  {dir}: {recv}/{sent} ({pdr:.1f}%), avg RSSI: {rssi}".format(
            dir=r["direction"],
            recv=r["received"],
            sent=r["sent"],
            pdr=pdr,
            rssi=avg_str,
        ))
        for err in r["errors"]:
            print("    ! {err}".format(err=err))

    overall_pdr = (total_received / total_sent * 100) if total_sent > 0 else 0
    print("\n  Overall PDR: {recv}/{sent} ({pdr:.1f}%)".format(
        recv=total_received, sent=total_sent, pdr=overall_pdr))
    if all_rssi:
        print("  Overall RSSI: avg {avg:.1f} dBm (min {min}, max {max})".format(
            avg=statistics.mean(all_rssi), min=min(all_rssi), max=max(all_rssi)))
    else:
        print("  No RSSI data collected")

    # Goodput estimate from real packet bytes actually received (28 B payload).
    if total_received > 0 and total_sent > 0:
        measured = args.count * TX_SPACING  # seconds of known transmission schedule
        total_bytes = total_received * TELEMETRY_SIZE
        throughput = total_bytes / measured if measured > 0 else 0
        print("  Estimated goodput: ~{tp:.1f} bytes/sec "
              "({b} bytes over {t:.0f}s per direction)".format(
                  tp=throughput, b=total_bytes, t=measured))

    # Exit code
    if overall_pdr == 100:
        print("\n  RESULT: PASS (all packets received)")
        sys.exit(0)
    elif overall_pdr > 0:
        print("\n  RESULT: PARTIAL (some packet loss)")
        sys.exit(1)
    print("\n  RESULT: FAIL (no packets received)")
    sys.exit(2)


if __name__ == "__main__":
    main()
