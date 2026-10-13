#!/usr/bin/env python3
"""
test_nostr_roundtrip.py — Nostr relay pipeline round-trip integration test (Phase 6).

Tests the full relay pipeline: Board A serializes a Nostr event and transmits
it via LR2021 radio; Board B receives it, stores it in its flash-backed
nostr_store; the harness then reads the store back with `nostr_dump` and checks
that the stored event matches what was sent.

WHAT THE FIRMWARE ACTUALLY DOES (verified against tracker/firmware/main):
  - `relay_send_nostr <kind> <content>` (main/app_main.cpp:403) serializes a
    Nostr event and queues it for radio TX, printing:
        relay_send_nostr: queued <N> bytes (kind=<K>, content=<C> bytes, serialized=<S>)
    Its failure paths print `relay_send_nostr: relay mode not active`,
    `serialize failed (content too big for relay packet)` and
    `TX queue full (dropped N bytes)` — none contain the word "error", so the
    harness matches those exact strings rather than guessing.
  - Board B logs the store write via ESP_LOGI with TAG="APP_TASK"
    (main/app_task.cpp:106):
        <L> (t) APP_TASK: Nostr event stored (kind=<K>)
  - `nostr_dump [count]` (main/app_main.cpp:511) prints ONE line per event:
        === Nostr Store: <total> events (showing <limit>) ===
        [<i>] kind=<K> ts=<created_at> len=<content_len> pub=<16 hex chars> <content preview>[...]
    Content is truncated to 80 chars and non-printables become '.', so a match
    must be done against that preview (an over-long content will not compare
    equal — the harness reports a MISMATCH, which is the honest verdict).

  The old parser expected an invented multi-line `Event N:` / `kind: 1` /
  `content: ...` block that the firmware never prints, which made every run
  report FAIL even when events were stored. That format is gone.

PREREQUISITES:
  - Two PCB-V2 boards flashed with balloon-fresh firmware (relay mode enabled)
  - Both boards connected via USB serial (/dev/ttyACM0, /dev/ttyACM1)
  - Board locks acquirable (no other track using the boards)
  - pyserial installed: pip install pyserial
  - balloon-board-lock.py and board_serial.py in ~/repos/balloon-fresh/tools/

USAGE:
  # Basic nostr round-trip test (send 1 event, verify storage):
  python3 test_nostr_roundtrip.py

  # Send multiple events:
  python3 test_nostr_roundtrip.py --count 5

  # Custom serial ports:
  python3 test_nostr_roundtrip.py --port-a /dev/ttyACM0 --port-b /dev/ttyACM1

  # Use a specific Nostr kind and content:
  python3 test_nostr_roundtrip.py --kind 1 --content "hello from balloon"

  # Show help:
  python3 test_nostr_roundtrip.py --help

WHAT IT VERIFIES:
  - Board A queues the event (relay_send_nostr printed its `queued ...` line)
  - Board B logs `Nostr event stored (kind=...)` for each event
  - Board B's nostr_dump shows the new events with matching kind + content
  - A mismatch (e.g. content truncated past 80 chars) is reported, not hidden

EXIT CODES:
  0 — every sent event received and stored correctly (content matches)
  1 — event received but content mismatch or partial storage
  2 — event not received at all
  3 — setup error (lock acquisition, serial open, CLI misuse, etc.)

The log parsers below are pure functions so they can be regression-tested on
the host without boards: see tracker/firmware/test/test_integration_parsers.py
"""

import argparse
import os
import re
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
DEFAULT_TIMEOUT = 45  # seconds to wait for reception + store writes
DEFAULT_KIND = 1
DEFAULT_CONTENT = "test_nostr_roundtrip"
NOSTR_DUMP_MAX_PREVIEW = 80  # firmware truncates content preview to 80 chars

# Firmware producer formats (tracker/firmware/main):
#   app_main.cpp cli_cmd_relay_send_nostr (:472)
RELAY_QUEUED_PATTERN = re.compile(
    r"relay_send_nostr:\s*queued\s+\d+\s+bytes\s*\(kind=(\d+),\s*content=(\d+)\s+bytes",
    re.IGNORECASE,
)
RELAY_FAILURE_PATTERN = re.compile(
    r"relay_send_nostr:\s*(relay mode not active|serialize failed|TX queue full)[^\n]*",
    re.IGNORECASE,
)
#   app_task.cpp (:106)
STORED_PATTERN = re.compile(r"Nostr event stored\s*\(kind=(\d+)\)", re.IGNORECASE)
#   app_main.cpp cli_cmd_nostr_dump (:566)
DUMP_HEADER_PATTERN = re.compile(
    r"===\s*Nostr Store:\s*(\d+)\s+events\s*\(showing\s+(\d+)\)\s*===",
    re.IGNORECASE,
)
DUMP_EVENT_PATTERN = re.compile(
    r"^\[(\d+)\]\s+kind=(\d+)\s+ts=(\d+)\s+len=(\d+)\s+pub=([0-9a-f]+)\s+(.*)$"
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


def parse_relay_queued(text: str):
    """Return {'kind','content_len'} from a relay_send_nostr success line, else None."""
    m = RELAY_QUEUED_PATTERN.search(text or "")
    if not m:
        return None
    return {"kind": int(m.group(1)), "content_len": int(m.group(2))}


def parse_relay_failure(text: str):
    """Return the firmware's own failure string, else None."""
    m = RELAY_FAILURE_PATTERN.search(text or "")
    return m.group(1) if m else None


def parse_stored_kinds(text: str):
    """Return the list of kinds from `Nostr event stored (kind=K)` lines."""
    return [int(k) for k in STORED_PATTERN.findall(text or "")]


def parse_nostr_dump(text: str):
    """Parse `nostr_dump` output into a list of event dicts.

    Matches the firmware's real one-line-per-event format
    (main/app_main.cpp:566):
        [0] kind=1 ts=1234567890 len=51 pub=abababababababab some content

    Ignores the `=== Nostr Store: N events (showing M) ===` header, the
    `Nostr store: 0 events` empty case, and `[N] READ ERROR` lines.

    Returns a list of: {index, kind, created_at, content_len, pubkey, content}.
    `content` is the 80-char preview the firmware printed (with a trailing
    '...' when it truncated); callers must compare against that preview.
    """
    events = []
    for raw in (text or "").split("\n"):
        line = raw.strip()
        m = DUMP_EVENT_PATTERN.match(line)
        if not m:
            continue
        content = m.group(6)
        truncated = content.endswith("...")
        if truncated:
            content = content[:-3]
        events.append({
            "index": int(m.group(1)),
            "kind": int(m.group(2)),
            "created_at": int(m.group(3)),
            "content_len": int(m.group(4)),
            "pubkey": m.group(5),
            "content": content,
            "truncated": truncated,
        })
    return events


def parse_dump_count(text: str):
    """Return the total event count from the dump header, or None."""
    m = DUMP_HEADER_PATTERN.search(text or "")
    return int(m.group(1)) if m else None


def main():
    parser = argparse.ArgumentParser(
        description="Nostr relay pipeline round-trip integration test (Phase 6). "
                    "Sends Nostr events from Board A and verifies storage on Board B via "
                    "the firmware's nostr_dump CLI command.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                       # Basic single event test
  %(prog)s --count 5                             # Send 5 events
  %(prog)s --kind 1 --content "hello balloon"    # Custom event
  %(prog)s --port-a /dev/ttyACM2                 # Custom port for board A

Note: nostr_dump previews at most 80 content chars, so keep --content under
80 chars for an exact match (a longer one is reported as a MISMATCH).
        """,
    )
    parser.add_argument(
        "--count", type=int, default=1,
        help="Number of Nostr events to send (default: 1)",
    )
    parser.add_argument(
        "--timeout", type=int, default=DEFAULT_TIMEOUT,
        help="Seconds to wait for Board B to receive + store the events "
             "(default: {n})".format(n=DEFAULT_TIMEOUT),
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

    if args.count < 1:
        print("ERROR: --count must be >= 1", file=sys.stderr)
        sys.exit(3)

    print("=" * 60)
    print("PCB-V2 Phase 6: Nostr Relay Round-Trip Integration Test")
    print("=" * 60)
    print("  Board A (TX): {port}".format(port=args.port_a))
    print("  Board B (RX): {port}".format(port=args.port_b))
    print("  Events to send: {n}".format(n=args.count))
    print("  Event kind: {kind}".format(kind=args.kind))
    print("  Event content: '{content}'".format(content=args.content))
    print("  RX wait: {t}s".format(t=args.timeout))

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
    baseline_count = 0
    post_events = []
    post_output = ""
    stored_kinds = []

    try:
        print("\n--- Opening Serial Connections ---")
        BoardSerial = load_board_serial()
        try:
            tx_ser = BoardSerial(args.port_a, BAUD_RATE, timeout=1)
            rx_ser = BoardSerial(args.port_b, BAUD_RATE, timeout=1)
        except Exception as e:  # noqa: BLE001 - hard setup failure
            print("FATAL: Failed to open serial: {e}".format(e=e), file=sys.stderr)
            sys.exit(3)

        print("  Serial connections established")
        drain_serial(tx_ser)
        drain_serial(rx_ser)

        # Step 1: baseline store state on Board B
        print("\n--- Step 1: Baseline nostr_dump on Board B ---")
        baseline_output = send_and_read(rx_ser, "nostr_dump 50", wait=2.0)
        baseline_events = parse_nostr_dump(baseline_output)
        baseline_count = parse_dump_count(baseline_output)
        if baseline_count is None:
            baseline_count = len(baseline_events)
        print("  Board B has {n} stored events before test".format(n=baseline_count))

        # Step 2: send events from Board A
        print("\n--- Step 2: Sending Nostr Events from Board A ---")
        for i in range(args.count):
            content = "{base}_{idx}".format(base=args.content, idx=i + 1)
            cmd = "relay_send_nostr {kind} {content}".format(kind=args.kind, content=content)
            print("  [{i}/{count}] Sending: {cmd}".format(i=i + 1, count=args.count, cmd=cmd))
            response = send_and_read(tx_ser, cmd, wait=2.0)
            sent_events.append({"kind": args.kind, "content": content})

            queued = parse_relay_queued(response)
            failure = parse_relay_failure(response)
            if queued is not None:
                print("    TX: queued (kind={k}, content={c} bytes)".format(
                    k=queued["kind"], c=queued["content_len"]))
            elif failure is not None:
                print("    TX: FAILED — relay_send_nostr: {f}".format(f=failure))
            else:
                print("    TX: no firmware confirmation seen; raw: {r}".format(
                    r=response.strip()[:100]))

            time.sleep(3.0)  # avoid queue overflow between events

        # Step 3: wait for Board B to receive + store
        print("\n--- Step 3: Waiting for Board B to receive + store ({t}s) ---".format(t=args.timeout))
        rx_notifications = read_all(rx_ser, wait=float(args.timeout))

        stored_kinds = parse_stored_kinds(rx_notifications)
        if stored_kinds:
            print("  Board B stored-event log lines: {n} {kinds}".format(
                n=len(stored_kinds), kinds=stored_kinds))
        else:
            print("  Board B printed no 'Nostr event stored' line during the wait")
        if rx_notifications.strip():
            print("  Board B serial output (last 10 lines):")
            for line in rx_notifications.strip().split("\n")[-10:]:
                print("    {line}".format(line=line))

        if not stored_kinds:
            print("  WARNING: Board B logged no store writes — the radio link or store path "
                  "may be broken. nostr_dump below is the authority.")

        # Step 4: post-test dump on Board B
        print("\n--- Step 4: Post-test nostr_dump on Board B ---")
        drain_serial(rx_ser)
        post_output = send_and_read(rx_ser, "nostr_dump 50", wait=3.0)
        post_events = parse_nostr_dump(post_output)
        post_count = parse_dump_count(post_output)
        if post_count is None:
            post_count = len(post_events)
        print("  Board B has {n} stored events after test (was {before})".format(
            n=post_count, before=baseline_count))

        # Step 5: verify events match
        print("\n--- Step 5: Verifying Stored Events ---")
        # Search ALL post events, not just a slice after the baseline: the store
        # may evict/wrap and the index base is not guaranteed to be stable.
        def store_contains(content, kind):
            for stored in post_events:
                if stored["kind"] == kind and stored["content"] == content:
                    return True
            return False

        matches = 0
        mismatches = 0
        for sent in sent_events:
            if store_contains(sent["content"], sent["kind"]):
                matches += 1
                print("  MATCH: kind={kind}, content='{content}'".format(
                    kind=sent["kind"], content=sent["content"]))
            else:
                mismatches += 1
                print("  MISS: kind={kind}, content='{content}' not found in store".format(
                    kind=sent["kind"], content=sent["content"]))

        print("\n--- Raw nostr_dump output (last 20 lines) ---")
        for line in post_output.strip().split("\n")[-20:]:
            print("  {line}".format(line=line))

    finally:
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
    print("  'Nostr event stored' log lines seen: {n}".format(n=len(stored_kinds)))

    if matches == len(sent_events) and matches > 0:
        print("\n  RESULT: PASS (all events received and stored correctly)")
        sys.exit(0)
    elif matches > 0:
        print("\n  RESULT: PARTIAL (some events missing)")
        sys.exit(1)
    print("\n  RESULT: FAIL (no events received)")
    sys.exit(2)


if __name__ == "__main__":
    main()
