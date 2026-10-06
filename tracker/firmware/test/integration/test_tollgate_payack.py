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
  - The ACK payload's session fields are recorded when a producer prints them:
    session / session_id, price (sats) and expires are read off the ACK's
    TollGate log line. The producers on this path print `seq=%u` only
    (main/app_task.cpp:121 `ESP_LOGI(TAG, "TollGate PAY received (seq=%u)")` and
    :143 `ESP_LOGI(TAG, "TollGate ACK queued (seq=%u)")` — no payload fields),
    so `session_info` is normally empty and is reported only when it is not; the
    tollgate_balloon producer that does print them (`ACK sent (session=%u,
    price=%u sats)`, tollgate_balloon.c:255) is readable by the same patterns,
    and no producer in the tree prints `expires` at all.

BOARD CLI COMMANDS USED:
  - tollgate_send_pay [token]  — encode + queue TollGate PAY message for TX
  - radio_recv <seconds>       — listen for incoming packets (for ACK)
  - nostr_dump [count]         — dump stored events (for checking relay pipeline)
  - status                     — system status (check board health)

NOTE: This test is a template. When the V2 boards arrive from JLCPCB, the
exact ACK handling path may need adjustment based on firmware behavior.
The tollgate component on Board B may automatically ACK or may require
firmware changes to process PAY messages and respond with ACK.

LOG PARSING CONTRACT (host-testable, no serial required):
  Every parse goes through parse_tollgate_log_line(), which first requires the
  line to mention "tollgate" (the D6 gate); extract_session_info() is
  line-scoped the same way, so no parse in this module can read a field off a
  non-TollGate line. Inside a TollGate line the harness reads four numeric
  fields — seq, session_id, price (sats) and expires — each accepting the '='
  form used by the producers that print that field, the ':' form, and the
  whitespace-only form (`seq 9`, `session_id 5`, `price 10 sats`, `expires 99`)
  that the pre-D6 harness accepted. One separator is always required, so a
  glued token (`seq9`) is not a field. The session field's NAME is the union
  `session` / `session_id` on a leading word boundary (as SEQ_PATTERN has): the
  only log producer of a session number spells it
  `session` (`ACK sent (session=%u, price=%u sats)`, tollgate_balloon.c:255),
  which the earlier name-literal form could not match in ANY revision (cold
  review finding 1 of t_2a65361e, filed as t_388122d0). A glued name
  (`session7`), a word merely ending in session (`subsession=7`) and a longer or
  plural name (`session_timeout=30`, `active_sessions: 3`) are still not fields.
  No producer prints `expires` at
  all (`expires_unix` occurs only as a struct field, e.g. tollgate_balloon.c:249
  `ack.expires_unix = 0;  /* TODO: real expiry */`), so expires_unix is recorded
  only if some producer starts printing it. That grammar, both separator forms,
  the NAME union, and the re-widening of all four fields (D6 narrowed seq and
  these three siblings at once) are pinned by
  tracker/firmware/test/test_tollgate_payack_parse.py — suite 2c of
  .github/workflows/ci-host-tests.yml and
  .ngit/act/workflows/host-tests.yml.

EXIT CODES (computed by compute_verdict() — single source of truth):
  0 — PASS: every round sent a PAY, got an ACK, and the seq echoed exactly
  1 — PARTIAL: at least one ACK/NACK was seen, but not all rounds matched
  2 — FAIL: no PAY could be sent, or no ACK/NACK was ever received
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

# Ensure we can import BoardSerial from the tools directory.
# NOTE: that import is deferred to load_board_serial() so the log-parsing
# helpers in this module stay importable on a host without pyserial — the
# host-only regression tests (test/test_tollgate_payack_parse.py) import this
# module and must not require serial hardware or pyserial.
TOOLS_DIR = os.path.expanduser("~/repos/balloon-fresh/tools")
sys.path.insert(0, TOOLS_DIR)

BoardSerial = None  # populated lazily by load_board_serial()


def load_board_serial():
    """Import the mandated serial wrapper (board_serial.py) on first use.

    Exits 3 with a clear message when the wrapper or pyserial is unavailable,
    preserving the harness's documented setup-error exit code.
    """
    global BoardSerial
    if BoardSerial is not None:
        return BoardSerial
    try:
        from board_serial import BoardSerial as _BoardSerial
    except (ImportError, SystemExit) as exc:
        print("ERROR: board_serial.py not usable ({e})".format(e=exc), file=sys.stderr)
        print("       Ensure balloon-fresh repo is cloned at ~/repos/balloon-fresh", file=sys.stderr)
        print("       and pyserial is installed: pip install pyserial", file=sys.stderr)
        sys.exit(3)
    BoardSerial = _BoardSerial
    return BoardSerial

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

# ---------------------------------------------------------------------------
# Log parsing — host-testable, no serial required
# ---------------------------------------------------------------------------
#
# Two things make the raw patterns unsafe on their own, so every parse goes
# through parse_tollgate_log_line(), which scopes a line to the TollGate
# subsystem first:
#
#   1. Every TollGate producer prints `seq=%u` (main/app_main.cpp:648,
#      main/app_task.cpp:121,143), so the sequence pattern must accept '=' as
#      well as ':' and the whitespace-only form `seq 9` the harness accepted
#      before the D6 fix (that narrowing was an unintended side effect of the
#      card's "accept '='" wording, not a contract change: no producer prints
#      it, but a future producer that does would have parsed as None). One of
#      the three separators is REQUIRED, so a bare `seq9` token is not a seq
#      field.
#   2. The tracker log tag is "TRACKER" (main/app_main.cpp:83) — it CONTAINS
#      the substring "ack" — and the telemetry line
#      `TX %d bytes (seq %d)...` (main/app_main.cpp:905) has a `seq` field of
#      its own. Neither may be counted as a TollGate ACK/sequence; both are
#      whitespace-form `seq` lines, so they are excluded by the TollGate
#      line-scoping in parse_tollgate_log_line(), NOT by the seq pattern.
#   3. The three ACK-payload patterns lost the SAME whitespace-only form in the
#      SAME commit: pre-D6 they read `session[_\s]*id[:\s]+(\d+)`,
#      `price[:\s]+(\d+)\s*sats?`, `expires?[:\s]+(\d+)` (64b8923:107-109), so
#      `session_id 5` / `price 10 sats` / `expires 99` parsed and now do not.
#      They are read on the live path by extract_session_info() below (called
#      by run_pay_round() for every detected ACK), so the narrowing silently
#      emptied the recorded ACK session info. All three carry the same
#      mandatory-separator union as seq here. Producer scan at this commit: the
#      only log producers for these fields print a separator — `Price: %u sats /
#      %ld ms` (tollgate_balloon.c:163) and `ACK sent (session=%u, price=%u
#      sats)` (tollgate_balloon.c:255) — nothing prints `expires`, and nothing
#      prints the whitespace-only form, so the re-widening is zero-cost today
#      and restores the pre-D6 grammar instead of inventing a new one.
#   4. The NAME of the session field was narrowed by the same D6 spelling: the
#      pattern required the literal `id` after `session`, while the ONLY
#      producer of a session number in the tree prints `session=%u`
#      (tollgate_balloon.c:255 — the only log PRODUCER of a session number:
#      `git grep -nE '"session' tracker/ mesh-stack/` also hits the C test
#      fixtures, the vendored libsecp256k1 `#include "session.h"` lines and the
#      ehash-interface-boundary.md JSON samples, none of which is a log line),
#      so session_id was unreachable from a real log line in ANY revision (cold
#      review finding 1 of t_2a65361e, filed as t_388122d0). The pattern now
#      accepts the name union `session` / `session_id`, keeping the mandatory
#      separator and the D6 line gate; the leading `\b` (as SEQ_PATTERN has)
#      keeps a longer word ending in `session` (`subsession=7`) from matching.
#      Collision scan over every non-vendored tracked line carrying a `session`
#      string literal (evidence:
#      /home/c03rad0r/reports/balloon/t_388122d0/evidence/collision_scan.log):
#      no TollGate-gated PRODUCER is newly matched except that one (the only
#      other newly-matched TollGate-tagged lines are this test's own literals),
#      and no TollGate-gated line has `session` followed by a number without a
#      separator (`session7`, `subsession=7`, `active_sessions: 3`,
#      `session_timeout=30` and `3 sessions active` all stay unmatched — pinned
#      in suite 2c). `expires` still has no producer at all (see the contract in
#      the module docstring).

TOLLGATE_LINE_PATTERN = re.compile(r"tollgate", re.IGNORECASE)

# Every field accepts `[:=]` (the producer form), the ':' form, and the
# whitespace-only form; the separator is REQUIRED in all cases (a glued `seq9`
# is not a field). See the note above. The session field's NAME is likewise a
# union — `session` (the only producer's spelling) and `session_id` — because
# D6's name-literal form could not match the one real producer. See item 4 of
# the note above.
SEQ_PATTERN = re.compile(r"\bseq\s*(?:[:=]\s*|\s+)(\d+)", re.IGNORECASE)
SESSION_ID_PATTERN = re.compile(r"\bsession(?:[_\s]*id)?\s*(?:[:=]\s*|\s+)(\d+)", re.IGNORECASE)
PRICE_PATTERN = re.compile(r"price\s*(?:[:=]\s*|\s+)(\d+)\s*sats?", re.IGNORECASE)
EXPIRES_PATTERN = re.compile(r"expires?\s*(?:[:=]\s*|\s+)(\d+)", re.IGNORECASE)
QUEUED_PATTERN = re.compile(r"queued\s+\d+\s+bytes", re.IGNORECASE)
# \b stops "NACK" (and words like "stack"/"feedback") from matching as an ACK.
ACK_PATTERN = re.compile(r"(?:\bACK\b|\baccepted\b)", re.IGNORECASE)
NACK_PATTERN = re.compile(r"(?:\bNACK\b|\brejected\b)", re.IGNORECASE)
PAY_PATTERN = re.compile(r"(?:\bPAY\b|send_pay)", re.IGNORECASE)
RSSI_PATTERN = re.compile(r"RSSI[:\s]+(-?\d+)\s*dBm", re.IGNORECASE)


def parse_tollgate_log_line(line: str):
    """Parse one firmware log line into a TollGate record, or None.

    None means "not a TollGate line" (e.g. the TRACKER telemetry line). The
    returned dict has: kind ("pay"|"ack"|"nack"|"other"), the raw line, and
    any of seq/session_id/price_sats/expires_unix that the line carries.

    A parsed seq of 0 is a legitimate value: test for it with `is not None`,
    never with truthiness (u16 wrap reaches 0).
    """
    if not TOLLGATE_LINE_PATTERN.search(line):
        return None

    if NACK_PATTERN.search(line):
        kind = "nack"
    elif ACK_PATTERN.search(line):
        kind = "ack"
    elif PAY_PATTERN.search(line):
        kind = "pay"
    else:
        kind = "other"

    rec = {"kind": kind, "line": line, "seq": None}

    match = SEQ_PATTERN.search(line)
    if match:
        rec["seq"] = int(match.group(1))
    match = SESSION_ID_PATTERN.search(line)
    if match:
        rec["session_id"] = int(match.group(1))
    match = PRICE_PATTERN.search(line)
    if match:
        rec["price_sats"] = int(match.group(1))
    match = EXPIRES_PATTERN.search(line)
    if match:
        rec["expires_unix"] = int(match.group(1))
    return rec


def classify_tollgate_output(text: str) -> dict:
    """Split a block of serial output into TollGate records, grouped by kind."""
    out = {"pay": [], "ack": [], "nack": [], "other": []}
    for rec in parse_tollgate_output(text):
        out[rec["kind"]].append(rec)
    return out


def parse_tollgate_output(text: str) -> list:
    """Flat list of TollGate records found in a block of serial output."""
    recs = []
    for line in (text or "").split("\n"):
        rec = parse_tollgate_log_line(line)
        if rec is not None:
            recs.append(rec)
    return recs


def extract_seq(text: str):
    """Sequence number of the first TollGate log line that carries one."""
    for line in (text or "").split("\n"):
        rec = parse_tollgate_log_line(line)
        if rec is not None and rec["seq"] is not None:
            return rec["seq"]
    return None


def extract_session_info(text: str) -> dict:
    """Extract session info (session_id / price_sats / expires_unix) from ACK output.

    Line-scoped like parse_tollgate_log_line(): a line that does not mention
    "tollgate" is skipped, and for each field the FIRST hit on a TollGate line
    wins (the same ordering the unscoped version had, now restricted to TollGate
    lines). This closes the last unscoped parse in this module — the D6 defect
    class was exactly a pattern reading a non-TollGate line (TAG="TRACKER"
    telemetry), and re-widening the three field patterns to accept the
    whitespace-only form makes that class reachable again for a caller that
    passes raw captures.

    No behaviour change on the live path: both call sites are run_pay_round()'s
    ACK branches, and each one runs this on the same single line it has just
    resolved through `rec = parse_tollgate_log_line(line)` /
    `if rec is None: continue`, so the string handed in here is a
    TollGate-scoped line by construction and the per-line gate above is a no-op
    for it. Verified against this file, not just against a diff of it: the two
    call sites are the rx loop (parse gate, then `if rec["kind"] == "ack"`) and
    the tx fallback loop (`if not result["ack_received"] and not
    result["nack_received"]`), and both pass the very `line` they gated.
    Producer scan at this commit: no non-TollGate producer line in this tree
    prints session/price/expires at all (only the two TollGate producers noted
    above do).

    session_id is read with the NAME union `session` / `session_id` (anchored on
    a word boundary), so the one real producer (`ACK sent (session=%u, price=%u
    sats)`) now fills the field; expires_unix still has no producer in the tree,
    so it is only recorded if one appears. Recording the field is kept
    deliberately: it is the only place this harness reports ACK payload fields,
    it is printed only when non-empty (see the run summary), and on the
    tracker↔tracker producers (main/app_task.cpp:121,143 print `seq=%u` only) it
    stays `{}`.
    """
    info = {}
    for line in (text or "").split("\n"):
        if not TOLLGATE_LINE_PATTERN.search(line):
            continue
        for pattern, key in ((SESSION_ID_PATTERN, "session_id"),
                             (PRICE_PATTERN, "price_sats"),
                             (EXPIRES_PATTERN, "expires_unix")):
            if key in info:
                continue
            match = pattern.search(line)
            if match:
                info[key] = int(match.group(1))
    return info


def seq_match_of(result: dict):
    """True/False if both sequences are known, else None.

    Single source of truth for the PAY/ACK echo check: an exact u16 equality
    (seq is an opaque echo token — see the contract in
    main/tollgate_payment_proto.h). `is not None` keeps a legal seq of 0 in
    play instead of treating it as "missing".
    """
    if result.get("pay_seq") is None or result.get("ack_seq") is None:
        return None
    return result["pay_seq"] == result["ack_seq"]


def summarize_results(all_results) -> dict:
    """Counts used for the run summary and the verdict."""
    return {
        "rounds": len(all_results),
        "pays_sent": sum(1 for r in all_results if r["pay_sent"]),
        "acks_received": sum(1 for r in all_results if r["ack_received"]),
        "nacks_received": sum(1 for r in all_results if r["nack_received"]),
        "seq_matches": sum(1 for r in all_results if seq_match_of(r) is True),
        "seq_mismatches": sum(1 for r in all_results if seq_match_of(r) is False),
    }


def compute_verdict(all_results):
    """Single source of truth for the harness exit verdict.

    Returns (exit_code, label) using the exit codes documented at the top of
    this file: 0 = PASS, 1 = PARTIAL, 2 = FAIL.
    """
    s = summarize_results(all_results)
    if s["pays_sent"] == 0:
        return 2, "FAIL (no PAY messages could be sent)"
    if s["rounds"] > 0 and s["acks_received"] == s["rounds"] and s["seq_matches"] == s["rounds"]:
        return 0, "PASS (all PAY\u2192ACK rounds successful)"
    if s["acks_received"] > 0 or s["nacks_received"] > 0:
        return 1, "PARTIAL (some rounds succeeded)"
    return 2, "FAIL (no ACKs received)"


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
        "nack_seq": None,
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
        print("  [A] PAY queued (seq={seq})".format(
            seq=seq if seq is not None else "unknown"))
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

    # Parse Board B output. Only TollGate log lines are considered — the
    # TRACKER tag itself contains "ack" and the telemetry line carries its own
    # `seq`, so unscoped matching produced phantom ACKs (defect D6).
    for line in rx_lines:
        rssi = RSSI_PATTERN.search(line)
        if rssi:
            result["rssi"] = int(rssi.group(1))

        rec = parse_tollgate_log_line(line)
        if rec is None:
            continue

        if rec["kind"] == "ack":
            result["ack_received"] = True
            if rec["seq"] is not None:  # seq 0 is valid — no truthiness
                result["ack_seq"] = rec["seq"]
            session = extract_session_info(line)
            if session:
                result["session_info"].update(session)
            print("  [B] ACK detected: {line}".format(line=line.strip()[:80]))
        elif rec["kind"] == "nack":
            result["nack_received"] = True
            if rec["seq"] is not None:
                result["nack_seq"] = rec["seq"]  # kept separate from ack_seq
            print("  [B] NACK detected: {line}".format(line=line.strip()[:80]))

    # Parse Board A output for ACK receipt (if ACK is relayed back)
    if not result["ack_received"] and not result["nack_received"]:
        for line in tx_output.split("\n"):
            rec = parse_tollgate_log_line(line)
            if rec is None:
                continue
            if rec["kind"] == "ack":
                result["ack_received"] = True
                if rec["seq"] is not None:
                    result["ack_seq"] = rec["seq"]
                session = extract_session_info(line)
                if session:
                    result["session_info"].update(session)
                print("  [A] ACK received back: {line}".format(line=line.strip()[:80]))
            elif rec["kind"] == "nack":
                result["nack_received"] = True
                if rec["seq"] is not None:
                    result["nack_seq"] = rec["seq"]
                print("  [A] NACK received back: {line}".format(line=line.strip()[:80]))

    # Print relevant RX output for debugging
    if not result["ack_received"] and not result["nack_received"]:
        print("  [B] No ACK/NACK detected in output")
        print("  [B] RX output (last 10 lines):")
        for line in rx_lines[-10:]:
            if line.strip():
                print("    {line}".format(line=line.strip()[:80]))

    # Verify sequence match (exact u16 echo equality; seq 0 is a valid value)
    result["seq_match"] = seq_match_of(result)
    if result["seq_match"] is True:
        print("  Seq match: PAY seq={ps} == ACK seq={acks}".format(
            ps=result["pay_seq"], acks=result["ack_seq"]))
    elif result["seq_match"] is False:
        print("  Seq MISMATCH: PAY seq={ps} != ACK seq={acks}".format(
            ps=result["pay_seq"], acks=result["ack_seq"]))

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
        BoardSerialCls = load_board_serial()
        try:
            tx_ser = BoardSerialCls(args.port_a, BAUD_RATE, timeout=1)
            rx_ser = BoardSerialCls(args.port_b, BAUD_RATE, timeout=1)
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

    summary = summarize_results(all_results)

    print("  Rounds executed: {n}".format(n=summary["rounds"]))
    print("  PAY messages sent: {n}".format(n=summary["pays_sent"]))
    print("  ACK received: {n}".format(n=summary["acks_received"]))
    print("  NACK received: {n}".format(n=summary["nacks_received"]))
    print("  Seq matches: {n}".format(n=summary["seq_matches"]))
    print("  Seq mismatches: {n}".format(n=summary["seq_mismatches"]))

    # Per-round detail (NACK seqs are reported separately from ACK seqs)
    for r in all_results:
        if r["session_info"]:
            print("  Round {n} session: {info}".format(
                n=r["round"], info=r["session_info"]))
        if r["nack_seq"] is not None:
            print("  Round {n} NACK seq: {s}".format(n=r["round"], s=r["nack_seq"]))
        if r["rssi"] is not None:
            print("  Round {n} RSSI: {rssi} dBm".format(
                n=r["round"], rssi=r["rssi"]))

    # Exit code determination — single source of truth is compute_verdict()
    exit_code, label = compute_verdict(all_results)
    print("\n  RESULT: {label}".format(label=label))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()