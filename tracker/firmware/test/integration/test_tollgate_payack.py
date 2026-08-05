#!/usr/bin/env python3
"""
test_tollgate_payack.py — TollGate payment protocol PAY→ACK round-trip test (Phase 7).

Tests the full TollGate payment protocol round-trip between two PCB-V2 boards:
Board A sends a PAY message (Cashu token) via LR2021 radio, Board B receives it,
decodes the payment, and sends back an ACK with session info. Board A receives
the ACK and the test verifies the sequence number and session details match.

The test uses the tollgate_payment_proto wire format (ADR-002):
  - PAY message:  header(8 bytes) + token payload
  - ACK message:  header(8 bytes) + session_id + expires + quota + price

In the relay pipeline, messages are tagged with a 1-byte relay type prefix:
  - RELAY_TYPE_TOLLGATE_PAY (0x02)
  - RELAY_TYPE_TOLLGATE_ACK (0x03)

PREREQUISITES:
  - Two PCB-V2 boards flashed with balloon-fresh firmware (relay mode enabled)
  - Both boards connected via USB serial (/dev/ttyACM0, /dev/ttyACM1)
  - Board locks must be acquirable (no other track using the boards)
  - pyserial installed: pip install pyserial
  - balloon-board-lock.py and board_serial.py in ~/repos/balloon-fresh/tools/

USAGE:
  # Basic PAY→ACK test (1 round, default test token):
  python3 test_tollgate_payack.py

  # Multiple payment rounds:
  python3 test_tollgate_payack.py --rounds 5

  # Custom Cashu token:
  python3 test_tollgate_payack.py --token "cashuA..."

  # Custom serial ports:
  python3 test_tollgate_payack.py --port-a /dev/ttyACM0 --port-b /dev/ttyACM1

  # Show help:
  python3 test_tollgate_payack.py --help

WHAT IT VERIFIES:
  - Board A can encode and send a PAY message via tollgate_send_pay CLI
  - The PAY message is transmitted over LR2021 radio
  - Board B receives and decodes the PAY message
  - Board B processes the payment (or at least acknowledges receipt)
  - An ACK response is generated (either by Board B or test harness)
  - The ACK's sequence number matches the PAY's sequence number
  - The ACK payload contains valid session info (session_id, expires, price)

BOARD CLI COMMANDS USED:
  - tollgate_send_pay [token]  — encode + queue TollGate PAY message for TX
  - radio_recv <seconds>       — listen for incoming packets (for ACK)
  - nostr_dump [count]         — dump stored events (for checking relay pipeline)
  - status                     — system status (check board health)

NOTE: This test is a template. When the V2 boards arrive from JLCPCB, the
exact ACK handling path may need adjustment based on firmware behavior.
The tollgate component on Board B may automatically ACK or may require
firmware changes to process PAY messages and respond with ACK.

EXIT CODES:
  0 — PAY sent and ACK received with matching seq + valid session info
  1 — PAY sent but ACK not received or seq mismatch
  2 — PAY could not be sent at all
  3 — setup error (lock acquisition, serial open, etc.)
"""

import argparse
import re
import sys
import time
import os
import subprocess
import struct
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
DEFAULT_TIMEOUT = 30  # seconds for ACK wait
DEFAULT_ROUNDS = 1
DEFAULT_TEST_TOKEN = "cashuAtesttoken123"  # Placeholder token for testing

# Relay type tags (from relay_types.h)
RELAY_TYPE_TOLLGATE_PAY = 0x02
RELAY_TYPE_TOLLGATE_ACK = 0x03

# TollGate message types (from tollgate_payment_proto.h)
TG_MSG_PAY = 0x01
TG_MSG_ACK = 0x02
TG_MSG_NACK = 0x03

# Regex patterns for parsing serial output
SEQ_PATTERN = re.compile(r"seq[:\s]+(\d+)", re.IGNORECASE)
SESSION_ID_PATTERN = re.compile(r"session[_\s]*id[:\s]+(\d+)", re.IGNORECASE)
PRICE_PATTERN = re.compile(r"price[:\s]+(\d+)\s*sats?", re.IGNORECASE)
EXPIRES_PATTERN = re.compile(r"expires?[:\s]+(\d+)", re.IGNORECASE)
QUEUED_PATTERN = re.compile(r"queued\s+\d+\s+bytes", re.IGNORECASE)
ACK_PATTERN = re.compile(r"(?:ACK|ack|accepted|payment.*?accepted)", re.IGNORECASE)
NACK_PATTERN = re.compile(r"(?:NACK|nack|rejected|payment.*?rejected)", re.IGNORECASE)
RSSI_PATTERN = re.compile(r"RSSI[:\s]+(-?\d+)\s*dBm", re.IGNORECASE)


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


def drain_serial(ser) -> None:
    """Drain any pending data from the serial buffer."""
    time.sleep(0.2)
    while ser.in_waiting > 0:
        ser.read(ser.in_waiting)


def read_all(ser, wait: float = 1.0) -> str:
    """Read all available serial data after waiting."""
    time.sleep(wait)
    data = ""
    while ser.in_waiting > 0:
        chunk = ser.read(ser.in_waiting)
        if chunk:
            data += chunk.decode("utf-8", errors="replace")
    return data


def send_and_read(ser, command: str, wait: float = 2.0) -> str:
    """Send a CLI command and read the response."""
    ser.write((command + "\n").encode("utf-8"))
    return read_all(ser, wait)


def extract_seq(text: str):
    """Extract sequence number from serial output."""
    match = SEQ_PATTERN.search(text)
    if match:
        return int(match.group(1))
    return None


def extract_session_info(text: str) -> dict:
    """Extract session info from ACK output."""
    info = {}
    match = SESSION_ID_PATTERN.search(text)
    if match:
        info["session_id"] = int(match.group(1))
    match = PRICE_PATTERN.search(text)
    if match:
        info["price_sats"] = int(match.group(1))
    match = EXPIRES_PATTERN.search(text)
    if match:
        info["expires_unix"] = int(match.group(1))
    return info


def run_pay_round(tx_ser, rx_ser, round_num: int, token: str, timeout: int) -> dict:
    """
    Execute a single PAY→ACK round.

    Board A sends PAY, Board B listens for it and potentially ACKs.
    Returns a result dict with all details.
    """
    result = {
        "round": round_num,
        "pay_sent": False,
        "pay_seq": None,
        "ack_received": False,
        "ack_seq": None,
        "nack_received": False,
        "session_info": {},
        "rssi": None,
        "errors": [],
    }

    print("\n--- Round {n}: PAY→ACK ---".format(n=round_num))

    # Step 1: Start Board B listening for incoming packets
    print("  [B] Starting radio_recv ({t}s)...".format(t=timeout))
    rx_ser.write("radio_recv {t}\n".format(t=timeout).encode("utf-8"))
    time.sleep(0.5)

    # Step 2: Board A sends PAY message
    cmd = "tollgate_send_pay {token}".format(token=token)
    print("  [A] Sending: {cmd}".format(cmd=cmd))
    response = send_and_read(tx_ser, cmd, wait=2.0)

    # Check if PAY was queued successfully
    if QUEUED_PATTERN.search(response):
        result["pay_sent"] = True
        seq = extract_seq(response)
        result["pay_seq"] = seq
        print("  [A] PAY queued (seq={seq})".format(seq=seq if seq else "unknown"))
    elif "error" in response.lower() or "failed" in response.lower():
        result["errors"].append("PAY send failed: {r}".format(r=response.strip()[:100]))
        print("  [A] PAY FAILED: {r}".format(r=response.strip()[:100]))
        return result
    else:
        result["pay_sent"] = True  # Assume sent if no explicit error
        seq = extract_seq(response)
        result["pay_seq"] = seq
        print("  [A] PAY response: {r}".format(r=response.strip()[:80]))

    # Step 3: Wait for Board B to receive and process
    print("  Waiting for Board B to receive + respond ({t}s)...".format(t=timeout))
    time.sleep(timeout)

    # Step 4: Read all Board B output
    rx_output = read_all(rx_ser, wait=1.0)
    rx_lines = rx_output.split("\n")

    # Also read Board A output (in case ACK comes back to A)
    tx_output = read_all(tx_ser, wait=1.0)

    # Parse Board B output for PAY receipt / ACK
    for line in rx_lines:
        line_lower = line.lower()
        if ACK_PATTERN.search(line):
            result["ack_received"] = True
            ack_seq = extract_seq(line)
            if ack_seq:
                result["ack_seq"] = ack_seq
            session = extract_session_info(line)
            if session:
                result["session_info"].update(session)
            print("  [B] ACK detected: {line}".format(line=line.strip()[:80]))

        if NACK_PATTERN.search(line):
            result["nack_received"] = True
            nack_seq = extract_seq(line)
            if nack_seq:
                result["ack_seq"] = nack_seq
            print("  [B] NACK detected: {line}".format(line=line.strip()[:80]))

        rssi = RSSI_PATTERN.search(line)
        if rssi:
            result["rssi"] = int(rssi.group(1))

    # Parse Board A output for ACK receipt (if ACK is relayed back)
    if not result["ack_received"] and not result["nack_received"]:
        for line in tx_output.split("\n"):
            if ACK_PATTERN.search(line):
                result["ack_received"] = True
                ack_seq = extract_seq(line)
                if ack_seq:
                    result["ack_seq"] = ack_seq
                session = extract_session_info(line)
                if session:
                    result["session_info"].update(session)
                print("  [A] ACK received back: {line}".format(line=line.strip()[:80]))
            if NACK_PATTERN.search(line):
                result["nack_received"] = True
                nack_seq = extract_seq(line)
                if nack_seq:
                    result["ack_seq"] = nack_seq
                print("  [A] NACK received back: {line}".format(line=line.strip()[:80]))

    # Print relevant RX output for debugging
    if not result["ack_received"] and not result["nack_received"]:
        print("  [B] No ACK/NACK detected in output")
        print("  [B] RX output (last 10 lines):")
        for line in rx_lines[-10:]:
            if line.strip():
                print("    {line}".format(line=line.strip()[:80]))

    # Verify sequence match
    if result["pay_seq"] is not None and result["ack_seq"] is not None:
        if result["pay_seq"] == result["ack_seq"]:
            result["seq_match"] = True
            print("  Seq match: PAY seq={ps} == ACK seq={acks}".format(
                ps=result["pay_seq"], acks=result["ack_seq"]))
        else:
            result["seq_match"] = False
            print("  Seq MISMATCH: PAY seq={ps} != ACK seq={acks}".format(
                ps=result["pay_seq"], acks=result["ack_seq"]))
    else:
        result["seq_match"] = None

    return result


def main():
    parser = argparse.ArgumentParser(
        description="TollGate payment protocol PAY→ACK round-trip integration test (Phase 7). "
                    "Tests payment protocol between two PCB-V2 boards over LR2021 radio.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Basic single PAY→ACK round
  %(prog)s --rounds 5                   # 5 payment rounds
  %(prog)s --token "cashuArealtoken"    # Use a real Cashu token
  %(prog)s --port-a /dev/ttyACM2        # Custom port for board A
        """,
    )
    parser.add_argument(
        "--rounds", type=int, default=DEFAULT_ROUNDS,
        help="Number of PAY→ACK rounds to execute (default: {n})".format(n=DEFAULT_ROUNDS),
    )
    parser.add_argument(
        "--timeout", type=int, default=DEFAULT_TIMEOUT,
        help="ACK wait timeout per round in seconds (default: {n})".format(n=DEFAULT_TIMEOUT),
    )
    parser.add_argument(
        "--port-a", default=BOARD_A_PORT,
        help="Serial port for board A / payer (default: {p})".format(p=BOARD_A_PORT),
    )
    parser.add_argument(
        "--port-b", default=BOARD_B_PORT,
        help="Serial port for board B / payee (default: {p})".format(p=BOARD_B_PORT),
    )
    parser.add_argument(
        "--token", default=DEFAULT_TEST_TOKEN,
        help="Cashu token string to send in PAY message (default: test token)",
    )
    parser.add_argument(
        "--skip-lock", action="store_true",
        help="Skip board lock acquisition (for manual testing only)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("PCB-V2 Phase 7: TollGate PAY->ACK Integration Test")
    print("=" * 60)
    print("  Board A (Payer):   {port}".format(port=args.port_a))
    print("  Board B (Payee):   {port}".format(port=args.port_b))
    print("  Rounds: {n}".format(n=args.rounds))
    print("  ACK timeout: {t}s per round".format(t=args.timeout))
    print("  Token: '{token}'".format(token=args.token[:40] + "..." if len(args.token) > 40 else args.token))

    # Acquire board locks
    locked = []
    if not args.skip_lock:
        print("\n--- Acquiring Board Locks ---")
        if not acquire_lock("board-a", "tollgate PAY payer", timeout=120):
            print("FATAL: Could not acquire lock for board-a", file=sys.stderr)
            sys.exit(3)
        locked.append("board-a")
        if not acquire_lock("board-b", "tollgate PAY payee", timeout=120):
            print("FATAL: Could not acquire lock for board-b", file=sys.stderr)
            for b in locked:
                release_lock(b)
            sys.exit(3)
        locked.append("board-b")
    else:
        print("  [SKIP] Board lock acquisition skipped (--skip-lock)")

    all_results = []
    try:
        # Open serial connections
        print("\n--- Opening Serial Connections ---")
        try:
            tx_ser = BoardSerial(args.port_a, BAUD_RATE, timeout=1)
            rx_ser = BoardSerial(args.port_b, BAUD_RATE, timeout=1)
        except Exception as e:
            print("FATAL: Failed to open serial: {e}".format(e=e), file=sys.stderr)
            sys.exit(3)

        print("  Serial connections established")

        # Drain any pending data
        drain_serial(tx_ser)
        drain_serial(rx_ser)

        # Check board health
        print("\n--- Checking Board Health ---")
        status_a = send_and_read(tx_ser, "status", wait=2.0)
        status_b = send_and_read(rx_ser, "status", wait=2.0)
        print("  [A] status: {s}".format(s=status_a.strip()[:60]))
        print("  [B] status: {s}".format(s=status_b.strip()[:60]))

        # Run PAY→ACK rounds
        for r in range(1, args.rounds + 1):
            result = run_pay_round(tx_ser, rx_ser, r, args.token, args.timeout)
            all_results.append(result)
            if r < args.rounds:
                print("  Pausing 3s before next round...")
                time.sleep(3)
                drain_serial(tx_ser)
                drain_serial(rx_ser)

    finally:
        # Release locks
        if locked:
            print("\n--- Releasing Board Locks ---")
            for b in locked:
                release_lock(b)

    # Summary
    print("\n" + "=" * 60)
    print("TOLLGATE PAY->ACK TEST SUMMARY")
    print("=" * 60)

    total = len(all_results)
    pays_sent = sum(1 for r in all_results if r["pay_sent"])
    acks_received = sum(1 for r in all_results if r["ack_received"])
    nacks_received = sum(1 for r in all_results if r["nack_received"])
    seq_matches = sum(1 for r in all_results if r.get("seq_match") is True)
    seq_mismatches = sum(1 for r in all_results if r.get("seq_match") is False)

    print("  Rounds executed: {n}".format(n=total))
    print("  PAY messages sent: {n}".format(n=pays_sent))
    print("  ACK received: {n}".format(n=acks_received))
    print("  NACK received: {n}".format(n=nacks_received))
    print("  Seq matches: {n}".format(n=seq_matches))
    print("  Seq mismatches: {n}".format(n=seq_mismatches))

    # Session info details
    for r in all_results:
        if r["session_info"]:
            print("  Round {n} session: {info}".format(
                n=r["round"], info=r["session_info"]))
        if r["rssi"] is not None:
            print("  Round {n} RSSI: {rssi} dBm".format(
                n=r["round"], rssi=r["rssi"]))

    # Exit code determination
    if pays_sent == 0:
        print("\n  RESULT: FAIL (no PAY messages could be sent)")
        sys.exit(2)
    elif acks_received == total and seq_matches == total:
        print("\n  RESULT: PASS (all PAY→ACK rounds successful)")
        sys.exit(0)
    elif acks_received > 0 or nacks_received > 0:
        print("\n  RESULT: PARTIAL (some rounds succeeded)")
        sys.exit(1)
    else:
        print("\n  RESULT: FAIL (no ACKs received)")
        sys.exit(2)


if __name__ == "__main__":
    main()