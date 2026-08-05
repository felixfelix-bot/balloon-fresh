#!/usr/bin/env python3
"""
test_nostr_roundtrip.py — Nostr relay pipeline round-trip integration test (Phase 6).

Tests the full relay pipeline: Board A serializes a Nostr event and transmits
it via LR2021 radio, Board B receives it, stores it in its flash-backed
nostr_store, and the test verifies the stored event matches what was sent.

The verification uses the `nostr_dump` CLI command on Board B to read back
stored events and compares them against the original event fields.

PREREQUISITES:
  - Two PCB-V2 boards flashed with balloon-fresh firmware (relay mode enabled)
  - Both boards connected via USB serial (/dev/ttyACM0, /dev/ttyACM1)
  - Board locks must be acquirable (no other track using the boards)
  - pyserial installed: pip install pyserial
  - balloon-board-lock.py and board_serial.py in ~/repos/balloon-fresh/tools/

USAGE:
  # Basic nostr round-trip test (send 1 event, verify storage):
  python3 test_nostr_roundtrip.py

  # Send multiple events:
  python3 test_nostr_roundtrip.py --count 5

  # Custom serial ports:
  python3 test_nostr_roundtrip.py --port-a /dev/ttyACM0 --port-b /dev/ttyACM1

  # Use specific Nostr kind and content:
  python3 test_nostr_roundtrip.py --kind 1 --content "hello from balloon"

  # Show help:
  python3 test_nostr_roundtrip.py --help

WHAT IT VERIFIES:
  - Board A can serialize a Nostr event via relay_send_nostr CLI command
  - The serialized event is transmitted over LR2021 radio
  - Board B receives the radio packet
  - Board B stores the Nostr event in nostr_store (flash-backed)
  - The stored event's kind and content match the original
  - nostr_dump CLI command on Board B shows the event

BOARD CLI COMMANDS USED:
  - relay_send_nostr <kind> <content>  — serialize + queue Nostr event for TX
  - nostr_dump [count]                 — dump stored Nostr events
  - radio_recv <seconds>               — listen for incoming packets (optional)

EXIT CODES:
  0 — event received and stored correctly (content matches)
  1 — event received but content mismatch or partial storage
  2 — event not received at all
  3 — setup error (lock acquisition, serial open, etc.)
"""

import argparse
import re
import sys
import time
import os
import subprocess
import json
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
DEFAULT_TIMEOUT = 45  # seconds for RX + processing
DEFAULT_KIND = 1
DEFAULT_CONTENT = "test_nostr_roundtrip"


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


def parse_nostr_dump(text: str):
    """
    Parse nostr_dump output to extract event details.

    Expected output format from the firmware:
      Event 0:
        kind: 1
        content: hello from balloon
        created_at: 1234567890
        ...

    Returns a list of dicts with event fields.
    """
    events = []
    current_event = {}

    for line in text.split("\n"):
        line = line.strip()

        # New event marker
        if re.match(r"Event\s+\d+", line, re.IGNORECASE):
            if current_event:
                events.append(current_event)
            current_event = {}
            continue

        # Key: value pairs
        match = re.match(r"(kind|content|created_at|pubkey|id|num_tags)\s*[:=]\s*(.+)", line, re.IGNORECASE)
        if match:
            key = match.group(1).lower().strip()
            value = match.group(2).strip()
            current_event[key] = value

    if current_event:
        events.append(current_event)

    return events


def main():
    parser = argparse.ArgumentParser(
        description="Nostr relay pipeline round-trip integration test (Phase 6). "
                    "Sends a Nostr event from Board A, verifies storage on Board B.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                       # Basic single event test
  %(prog)s --count 5                             # Send 5 events
  %(prog)s --kind 1 --content "hello balloon"    # Custom event
  %(prog)s --port-a /dev/ttyACM2                 # Custom port for board A
        """,
    )
    parser.add_argument(
        "--count", type=int, default=1,
        help="Number of Nostr events to send (default: 1)",
    )
    parser.add_argument(
        "--timeout", type=int, default=DEFAULT_TIMEOUT,
        help="RX listen window in seconds (default: {n})".format(n=DEFAULT_TIMEOUT),
    )
    parser.add_argument(
        "--port-a", default=BOARD_A_PORT,
        help="Serial port for board A / TX (default: {p})".format(p=BOARD_A_PORT),
    )
    parser.add_argument(
        "--port-b", default=BOARD_B_PORT,
        help="Serial port for board B / RX (default: {p})".format(p=BOARD_B_PORT),
    )
    parser.add_argument(
        "--kind", type=int, default=DEFAULT_KIND,
        help="Nostr event kind (default: {k})".format(k=DEFAULT_KIND),
    )
    parser.add_argument(
        "--content", default=DEFAULT_CONTENT,
        help="Content string for the Nostr event (default: '{c}')".format(c=DEFAULT_CONTENT),
    )
    parser.add_argument(
        "--skip-lock", action="store_true",
        help="Skip board lock acquisition (for manual testing only)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("PCB-V2 Phase 6: Nostr Relay Round-Trip Integration Test")
    print("=" * 60)
    print("  Board A (TX): {port}".format(port=args.port_a))
    print("  Board B (RX): {port}".format(port=args.port_b))
    print("  Events to send: {n}".format(n=args.count))
    print("  Event kind: {kind}".format(kind=args.kind))
    print("  Event content: '{content}'".format(content=args.content))
    print("  RX timeout: {t}s".format(t=args.timeout))

    # Acquire board locks
    locked = []
    if not args.skip_lock:
        print("\n--- Acquiring Board Locks ---")
        if not acquire_lock("board-a", "nostr roundtrip TX", timeout=120):
            print("FATAL: Could not acquire lock for board-a", file=sys.stderr)
            sys.exit(3)
        locked.append("board-a")
        if not acquire_lock("board-b", "nostr roundtrip RX", timeout=120):
            print("FATAL: Could not acquire lock for board-b", file=sys.stderr)
            for b in locked:
                release_lock(b)
            sys.exit(3)
        locked.append("board-b")
    else:
        print("  [SKIP] Board lock acquisition skipped (--skip-lock)")

    sent_events = []
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

        # Step 1: Capture initial nostr_store state on Board B
        print("\n--- Step 1: Baseline nostr_dump on Board B ---")
        baseline_output = send_and_read(rx_ser, "nostr_dump 50", wait=2.0)
        baseline_events = parse_nostr_dump(baseline_output)
        baseline_count = len(baseline_events)
        print("  Board B has {n} events before test".format(n=baseline_count))

        # Step 2: Send Nostr events from Board A
        print("\n--- Step 2: Sending Nostr Events from Board A ---")
        for i in range(args.count):
            content = "{base}_{idx}".format(base=args.content, idx=i + 1)
            cmd = "relay_send_nostr {kind} {content}".format(kind=args.kind, content=content)
            print("  [{i}/{count}] Sending: {cmd}".format(i=i + 1, count=args.count, cmd=cmd))
            response = send_and_read(tx_ser, cmd, wait=2.0)
            sent_events.append({"kind": args.kind, "content": content})

            # Check for TX queue confirmation
            if "queued" in response.lower():
                print("    TX: Event queued for radio transmission")
            elif "error" in response.lower() or "failed" in response.lower():
                print("    TX: WARNING - {resp}".format(resp=response.strip()[:100]))
            else:
                print("    TX: {resp}".format(resp=response.strip()[:100]))

            # Wait between sends to avoid queue overflow
            time.sleep(3.0)

        # Step 3: Wait for Board B to receive and store events
        print("\n--- Step 3: Waiting for Board B to Receive + Store ({t}s) ---".format(t=args.timeout))
        time.sleep(args.timeout)

        # Drain RX serial to see any RX notifications
        rx_notifications = read_all(rx_ser, wait=1.0)
        if rx_notifications.strip():
            print("  Board B serial output during wait:")
            for line in rx_notifications.strip().split("\n")[:10]:
                print("    {line}".format(line=line))

        # Step 4: Dump nostr_store on Board B to verify storage
        print("\n--- Step 4: Post-test nostr_dump on Board B ---")
        post_output = send_and_read(rx_ser, "nostr_dump 50", wait=3.0)
        post_events = parse_nostr_dump(post_output)
        post_count = len(post_events)
        print("  Board B has {n} events after test (was {before})".format(
            n=post_count, before=baseline_count))

        # Step 5: Verify events match
        print("\n--- Step 5: Verifying Stored Events ---")
        new_events = post_events[baseline_count:] if post_count > baseline_count else []
        matches = 0
        mismatches = 0

        for sent in sent_events:
            found = False
            for stored in new_events:
                stored_content = stored.get("content", "").strip()
                stored_kind = stored.get("kind", "").strip()
                if sent["content"] in stored_content and str(sent["kind"]) == stored_kind:
                    found = True
                    matches += 1
                    print("  MATCH: kind={kind}, content='{content}'".format(
                        kind=sent["kind"], content=sent["content"]))
                    break
            if not found:
                mismatches += 1
                print("  MISS: kind={kind}, content='{content}' not found in store".format(
                    kind=sent["kind"], content=sent["content"]))

        # Print raw nostr_dump output for debugging
        print("\n--- Raw nostr_dump output (last 20 lines) ---")
        dump_lines = post_output.strip().split("\n")
        for line in dump_lines[-20:]:
            print("  {line}".format(line=line))

    finally:
        # Release locks
        if locked:
            print("\n--- Releasing Board Locks ---")
            for b in locked:
                release_lock(b)

    # Summary
    print("\n" + "=" * 60)
    print("NOSTR ROUND-TRIP TEST SUMMARY")
    print("=" * 60)
    print("  Events sent: {n}".format(n=len(sent_events)))
    print("  Events matched in store: {m}".format(m=matches))
    print("  Events missed: {mism}".format(mism=mismatches))
    print("  New events in store: {new}".format(new=len(new_events)))

    if matches == len(sent_events) and matches > 0:
        print("\n  RESULT: PASS (all events received and stored correctly)")
        sys.exit(0)
    elif matches > 0:
        print("\n  RESULT: PARTIAL (some events missing)")
        sys.exit(1)
    else:
        print("\n  RESULT: FAIL (no events received)")
        sys.exit(2)


if __name__ == "__main__":
    main()