#!/usr/bin/env python3
"""
test_integration_parsers.py — host-only regression tests for the Phase 5/6
integration harness log parsers.

No boards, no serial, no locks: this exercises only the log-line parsing in
  tracker/firmware/test/integration/test_raw_ping.py
  tracker/firmware/test/integration/test_nostr_roundtrip.py
feeding the EXACT producer formats printed by the firmware
(main/app_main.cpp, main/app_task.cpp).

Why this exists (cold cross-family review of t_1153953b, 2026-09-29): every
critical finding was a FALSE-GREEN or FALSE-RED path where the harness parser
did not match the firmware's real output:
  * raw_ping counted any line containing the substring "ping" as a received
    packet — including its own echoed `radio_test` command — while its
    RECV_PATTERN never matched the real `RX %d bytes, RSSI: ...` line;
  * nostr_roundtrip parsed an invented multi-line `Event N:` / `kind: 1` block
    that the firmware never prints (`nostr_dump` is ONE line per event), so a
    correctly-stored event always reported FAIL.

Each test below pins a real producer line and asserts the parser's behaviour.

Run:
  python3 test/test_integration_parsers.py     # standalone (exit 0 = pass)
  pytest test/test_integration_parsers.py      # or under pytest
"""

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PING_PATH = HERE / "integration" / "test_raw_ping.py"
NOSTR_PATH = HERE / "integration" / "test_nostr_roundtrip.py"


def _load(path: Path, name: str):
    """Import a harness module by path (they are not installed packages)."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ping = _load(PING_PATH, "test_raw_ping")
nostr = _load(NOSTR_PATH, "test_nostr_roundtrip")

# ---------------------------------------------------------------------------
# Verbatim firmware producer lines
#   main/app_main.cpp cli_cmd_radio_test (:321) / cli_cmd_radio_recv (:341)
#   main/app_main.cpp cli_cmd_relay_send_nostr (:403) / cli_cmd_nostr_dump (:511)
#   main/app_task.cpp (:106)
# ---------------------------------------------------------------------------

L_TX_ECHO = "radio_test"                       # the shell-echoed command
L_TX_ECHO_WITH_ARGS = "radio_test 1 ping_1"    # what the old harness sent
L_TX_OK = "TX test packet (28 bytes)... OK"
L_TX_TIMEOUT = "TX test packet (28 bytes)... TIMEOUT"
L_RX = "RX 28 bytes, RSSI: -45 dBm, SNR: 9 dB"
L_RX_WEAK = "RX 28 bytes, RSSI: -118 dBm, SNR: -3 dB"
L_RX_NEG_SNR = "RX 5 bytes, RSSI: -60 dBm, SNR: -12 dB"
L_VALID_TEL = "  Valid telemetry! seq=7 voltage=4100mV"
L_LISTEN_START = "Listening for 30s..."
L_LISTEN_DONE = "Listen done"
L_RX_HEX = "  HEX: 1a2b3c4d"

L_RELAY_QUEUED = ("relay_send_nostr: queued 85 bytes "
                  "(kind=1, content=22 bytes, serialized=84)")
L_RELAY_NOT_ACTIVE = "relay_send_nostr: relay mode not active (g_tx_queue NULL)"
L_RELAY_TOO_BIG = "relay_send_nostr: serialize failed (content too big for relay packet)"
L_RELAY_QUEUE_FULL = "relay_send_nostr: TX queue full (dropped 512 bytes)"
L_STORED = "I (1400) APP_TASK: Nostr event stored (kind=1)"
L_DUMP_HEADER = "=== Nostr Store: 3 events (showing 3) ==="
L_DUMP_HEADER_LIMITED = "=== Nostr Store: 40 events (showing 50) ==="
L_DUMP_EVENT = "[0] kind=1 ts=1234567890 len=22 pub=abababababababab test_nostr_roundtrip_1"
L_DUMP_EVENT_TRUNC = "[1] kind=1 ts=99 len=120 pub=cdcdcdcdcdcdcdcd " + ("x" * 80) + "..."
L_DUMP_EMPTY = "Nostr store: 0 events"
L_DUMP_READERR = "[2] READ ERROR"


# ---------------------------------------------------------------------------
# raw_ping: RX detection must key off the real RX line, never a substring
# ---------------------------------------------------------------------------

def test_ping_rx_line_is_parsed_with_rssi_and_snr():
    rx = ping.parse_rx_line(L_RX)
    assert rx is not None, L_RX
    assert rx["len"] == 28 and rx["rssi"] == -45 and rx["snr"] == 9


def test_ping_rx_line_parses_negative_rssi_and_snr():
    rx = ping.parse_rx_line(L_RX_WEAK)
    assert rx is not None and rx["rssi"] == -118 and rx["snr"] == -3
    rx = ping.parse_rx_line(L_RX_NEG_SNR)
    assert rx is not None and rx["len"] == 5 and rx["snr"] == -12


def test_ping_tx_echo_is_not_a_received_packet():
    """The regression that mattered: the echoed command is NOT a packet."""
    assert ping.parse_rx_line(L_TX_ECHO) is None
    assert ping.parse_rx_line(L_TX_ECHO_WITH_ARGS) is None


def test_ping_old_substring_fallback_would_have_false_greened():
    """A line containing the word 'ping' must never count as a received packet.

    The old extract_received_data() returned TEST_MESSAGE whenever 'ping'
    appeared anywhere in the text — so the TX-side command echo (which the
    harness itself sent) was counted as an RX. There is no such fallback now:
    only a real RX announcement yields a packet.
    """
    for line in (L_TX_ECHO_WITH_ARGS, "some ping log line", L_LISTEN_START):
        assert ping.parse_rx_line(line) is None, line


def test_ping_valid_telemetry_line_is_parsed():
    tel = ping.parse_valid_telemetry(L_VALID_TEL)
    assert tel is not None and tel["seq"] == 7 and tel["voltage_mv"] == 4100


def test_ping_tx_result_ok_and_timeout():
    assert ping.parse_tx_result(L_TX_OK) == (28, "OK")
    assert ping.parse_tx_result(L_TX_TIMEOUT) == (28, "TIMEOUT")
    assert ping.parse_tx_result("no tx result here") is None


def test_ping_listen_markers_are_not_packets():
    for line in (L_LISTEN_START, L_LISTEN_DONE, L_RX_HEX):
        assert ping.parse_rx_line(line) is None, line


def test_ping_full_window_counts_only_real_rx_lines():
    """A realistic captured window: exactly 2 packets, no echo/hex counted."""
    window = "\n".join([
        L_LISTEN_START,
        L_TX_ECHO_WITH_ARGS,   # TX-side echo leaking into the RX buffer
        L_RX,
        L_VALID_TEL,
        L_RX_HEX,
        L_RX_WEAK,
        L_LISTEN_DONE,
    ])
    packets = [ping.parse_rx_line(ln) for ln in window.split("\n")]
    packets = [p for p in packets if p is not None]
    assert len(packets) == 2
    assert [p["rssi"] for p in packets] == [-45, -118]


# ---------------------------------------------------------------------------
# nostr_roundtrip: dump/queued/stored parsing must match the real formats
# ---------------------------------------------------------------------------

def test_nostr_relay_queued_line_is_parsed():
    q = nostr.parse_relay_queued(L_RELAY_QUEUED)
    assert q is not None and q["kind"] == 1 and q["content_len"] == 22


def test_nostr_relay_failures_are_detected():
    """Every failure path must be recognised (none prints 'error')."""
    assert nostr.parse_relay_failure(L_RELAY_NOT_ACTIVE) == "relay mode not active"
    assert nostr.parse_relay_failure(L_RELAY_TOO_BIG) == "serialize failed"
    assert nostr.parse_relay_failure(L_RELAY_QUEUE_FULL) == "TX queue full"
    assert nostr.parse_relay_failure(L_RELAY_QUEUED) is None


def test_nostr_stored_kinds_are_parsed():
    block = L_STORED + "\n" + L_STORED.replace("kind=1", "kind=30078") + "\n"
    assert nostr.parse_stored_kinds(block) == [1, 30078]
    assert nostr.parse_stored_kinds(L_DUMP_HEADER) == []


def test_nostr_dump_one_line_event_format_is_parsed():
    """The firmware prints ONE line per event; the old parser wanted a block."""
    events = nostr.parse_nostr_dump("\n".join([L_DUMP_HEADER, L_DUMP_EVENT]))
    assert len(events) == 1
    ev = events[0]
    assert ev["index"] == 0
    assert ev["kind"] == 1
    assert ev["created_at"] == 1234567890
    assert ev["content_len"] == 22
    assert ev["pubkey"] == "abababababababab"
    assert ev["content"] == "test_nostr_roundtrip_1"
    assert ev["truncated"] is False


def test_nostr_dump_truncated_preview_is_flagged():
    events = nostr.parse_nostr_dump("\n".join([L_DUMP_HEADER, L_DUMP_EVENT_TRUNC]))
    assert len(events) == 1
    assert events[0]["truncated"] is True
    assert len(events[0]["content"]) == 80   # the 80-char preview, no '...'


def test_nostr_dump_ignores_header_and_read_error_and_empty():
    assert nostr.parse_nostr_dump(L_DUMP_EMPTY) == []
    assert nostr.parse_nostr_dump(L_DUMP_READERR) == []
    assert nostr.parse_nostr_dump(L_DUMP_HEADER) == []


def test_nostr_dump_count_from_header():
    assert nostr.parse_dump_count(L_DUMP_HEADER) == 3
    assert nostr.parse_dump_count(L_DUMP_HEADER_LIMITED) == 40
    assert nostr.parse_dump_count(L_DUMP_EMPTY) is None


def test_nostr_no_event_lost_when_only_parse_used():
    """A correctly stored event must be findable — the old parser lost it."""
    dump = "\n".join([L_DUMP_HEADER, L_DUMP_EVENT])
    events = nostr.parse_nostr_dump(dump)
    found = any(e["kind"] == 1 and e["content"] == "test_nostr_roundtrip_1"
                for e in events)
    assert found, "a stored event must survive parsing"


# ---------------------------------------------------------------------------
# Standalone runner (also works when collected by pytest)
# ---------------------------------------------------------------------------

def main():
    tests = [(name, obj) for name, obj in sorted(globals().items())
             if name.startswith("test_") and callable(obj)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print("PASS: {n}".format(n=name))
        except AssertionError as exc:
            failed += 1
            print("FAIL: {n}: {e}".format(n=name, e=exc))
        except Exception as exc:  # missing API / unexpected error
            failed += 1
            print("FAIL: {n}: {t}: {e}".format(n=name, t=type(exc).__name__, e=exc))
    print("\n=== {p}/{t} passed, {f} failed ===".format(
        p=len(tests) - failed, t=len(tests), f=failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
