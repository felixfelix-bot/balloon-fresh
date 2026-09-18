#!/usr/bin/env python3
"""
test_tollgate_payack_parse.py — host-only regression tests for the PAY→ACK
harness log parser (tracker/firmware/test/integration/test_tollgate_payack.py).

No boards, no serial, no locks: this exercises only the log-line parsing and
the verdict computation, feeding the EXACT log lines the firmware producers
print.

Why this exists (defect D6 from the t_d7f958f8 inventory):
  * every tollgate producer prints `seq=%u` (main/app_main.cpp:648,
    main/app_task.cpp:121,143) but the harness required ':' or whitespace
    after `seq` → pay_seq/ack_seq were always None → the PAY→ACK PASS branch
    was unreachable;
  * the ACK detector matched the substring "ack" inside TAG="TRACKER" and the
    `seq` detector matched the telemetry line "TX %d bytes (seq %d)..."
    (main/app_main.cpp:905) → a non-tollgate counter could be counted as an
    ACK seq;
  * `if ack_seq:` discarded a parsed 0, so a legitimate wrap to seq 0 could
    never match.

The accepted `seq` grammar is the UNION of the pre-D6 forms (`seq: 9`,
`seq 9`) and the producer form (`seq=%u`); the re-widening that restores the
whitespace-only form (cold review of t_3a5cfe25, finding 1) is pinned by
test_seq_whitespace_only_form_is_parsed_without_regressing_d6_scoping, which
also re-asserts the D6 TollGate-line scoping.

The SAME D6 commit narrowed the three sibling ACK-payload patterns
(SESSION_ID_PATTERN / PRICE_PATTERN / EXPIRES_PATTERN) the same way — pre-D6
they read `session[_\s]*id[:\s]+(\d+)`, `price[:\s]+(\d+)\s*sats?`,
`expires?[:\s]+(\d+)` (64b8923:107-109) — so `session_id 5`, `price 10 sats`
and `expires 99` also parsed before D6 and did not after it. They are read on
the live harness path by extract_session_info(), which run_pay_round() calls
for every detected ACK, so the narrowing silently emptied the recorded ACK
session info. All three now carry the same mandatory-separator union, pinned by
test_session_price_expires_accept_the_whitespace_only_forms (both forms, the
glued-field rejection, and the unchanged D6 line gate).

D6 ALSO narrowed the session field NAME: the pattern required the literal `id`
after `session`, while the only log PRODUCER of a session number in the tree
(the vendored libsecp256k1 `#include "session.h"` lines, the C test fixtures and
the ehash-interface-boundary.md JSON samples also hit `git grep -nE '"session'
tracker/ mesh-stack/`, none of them a log line) prints `session=%u`
(`ACK sent (session=%u, price=%u sats)`,
mesh-stack/tollgate/components/tollgate_balloon/src/tollgate_balloon.c:255), so
session_id could not be populated from a real log line in ANY revision (cold
review finding 1 of t_2a65361e, filed as t_388122d0). The name is now the union
`session` / `session_id`, on a leading `\b` like SEQ_PATTERN's, keeping the
mandatory separator and the D6 line gate; pinned by
test_session_name_accepts_the_real_producer_form, which also pins that a glued
(`session7`), embedded (`subsession=7`), plural (`active_sessions: 3`) or
longer (`session_timeout=30`) name is still not a field and that a non-TollGate
line contributes nothing.
`expires` still has no producer anywhere in the tree, so expires_unix is only
recorded if one starts printing it.

Run:
  python3 test/test_tollgate_payack_parse.py     # standalone (exit 0 = pass)
  pytest test/test_tollgate_payack_parse.py      # or under pytest
"""

import importlib.util
import sys
from pathlib import Path

HARNESS_PATH = Path(__file__).resolve().parent / "integration" / "test_tollgate_payack.py"


def _load_harness():
    """Import the harness module by path (it is not an installed package)."""
    spec = importlib.util.spec_from_file_location("test_tollgate_payack", HARNESS_PATH)
    assert spec is not None and spec.loader is not None, HARNESS_PATH
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


h = _load_harness()

# ---------------------------------------------------------------------------
# Representative firmware log lines (verbatim printf/ESP_LOGI format strings
# from main/app_main.cpp and main/app_task.cpp, with plausible values).
# ---------------------------------------------------------------------------

L_TELEMETRY = "I (1234) TRACKER: TX 26 bytes (seq 7)..."
L_TELEMETRY_LONG = "I (9876) TRACKER: stack watermark low, heap=123456 (seq 4242)"
L_PAY_SENT = ("I (1300) TRACKER: tollgate_send_pay: queued 20 bytes "
              "(seq=1, payload=11 bytes, enc=8)")
L_PAY_RX = "I (1400) TRACKER: TollGate PAY received (seq=1)"
L_ACK = "I (1410) TRACKER: TollGate ACK queued (seq=1)"
L_PAY_SENT_WRAP = ("I (1500) TRACKER: tollgate_send_pay: queued 20 bytes "
                   "(seq=65535, payload=11 bytes, enc=8)")
L_ACK_WRAP = "I (1510) TRACKER: TollGate ACK queued (seq=65535)"
L_PAY_SENT_ZERO = ("I (1600) TRACKER: tollgate_send_pay: queued 20 bytes "
                   "(seq=0, payload=11 bytes, enc=8)")
L_ACK_ZERO = "I (1610) TRACKER: TollGate ACK queued (seq=0)"
L_NACK = "I (1700) TRACKER: TollGate NACK queued (seq=3, reason=invalid-token)"


def _round(pay_seq, ack_seq, nack_seq=None, session=None):
    """Build a run_pay_round-shaped result dict the way the harness does."""
    return {
        "round": 1,
        "pay_sent": True,
        "pay_seq": pay_seq,
        "ack_received": ack_seq is not None,
        "ack_seq": ack_seq,
        "nack_received": nack_seq is not None,
        "nack_seq": nack_seq,
        "session_info": session or {},
        "rssi": None,
        "errors": [],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_seq_equals_form_is_parsed():
    """`seq=%u` (the form every producer prints) must parse."""
    assert h.extract_seq(L_PAY_SENT) == 1
    assert h.extract_seq(L_PAY_RX) == 1
    assert h.extract_seq(L_ACK) == 1


def test_seq_colon_and_space_forms_still_parse():
    assert h.extract_seq("I (1) TRACKER: TollGate PAY received (seq: 9)") == 9
    assert h.extract_seq("I (1) TRACKER: TollGate ACK queued seq=10") == 10


def test_seq_whitespace_only_form_is_parsed_without_regressing_d6_scoping():
    """The pre-D6 form `seq 9` (no `:`/`=`) must not silently become None.

    The D6 fix narrowed SEQ_PATTERN to a mandatory `[:=]` separator, which
    dropped the whitespace-only form the harness accepted before it — a silent
    narrowing of the accepted log grammar (cold review of t_3a5cfe25, finding
    1; the comment above SEQ_PATTERN still claimed whitespace was accepted, and
    test_seq_colon_and_space_forms_still_parse was named as if it covered the
    form too). The form is accepted again; this test pins BOTH halves of the
    contract: `seq 9` parses to 9, AND the D6 line-scoping (TollGate-prefixed
    lines only) still excludes the TRACKER-tagged telemetry lines that carry a
    whitespace `seq` field of their own.
    """
    ws_ack = "I (1) TRACKER: TollGate ACK queued (seq 9)"
    ws_pay = "I (1) TRACKER: TollGate PAY received (seq 9)"
    assert h.extract_seq(ws_ack) == 9
    assert h.extract_seq(ws_pay) == 9
    rec = h.parse_tollgate_log_line(ws_ack)
    assert rec is not None and rec["kind"] == "ack" and rec["seq"] == 9

    # D6 scoping must not regress: `TX %d bytes (seq %d)...` and the long
    # telemetry form carry whitespace-form `seq` fields of their own and are
    # NOT TollGate lines, so the re-widened pattern must not reach them.
    assert h.parse_tollgate_log_line(L_TELEMETRY) is None
    assert h.parse_tollgate_log_line(L_TELEMETRY_LONG) is None
    assert h.extract_seq(L_TELEMETRY) is None
    assert h.extract_seq(L_TELEMETRY_LONG) is None
    classified = h.classify_tollgate_output(
        L_TELEMETRY + "\n" + L_TELEMETRY_LONG + "\n" + ws_pay + "\n" + ws_ack + "\n")
    assert [r["seq"] for r in classified["ack"]] == [9]
    assert [r["seq"] for r in classified["pay"]] == [9]
    assert classified["nack"] == []

    # ...and the whitespace form is a complete round: it reaches PASS.
    code, label = h.compute_verdict([_round(h.extract_seq(ws_pay), h.extract_seq(ws_ack))])
    assert code == 0, label

    # The separator requirement is deliberate: a glued `seq9` token is not a
    # seq field. Accepted: `seq=%u` (all producers), `seq: 9`, `seq 9`.
    assert h.extract_seq("I (1) TRACKER: TollGate ACK queued (seq9)") is None


def test_session_price_expires_accept_the_whitespace_only_forms():
    """The three sibling patterns lost the same whitespace-only form in D6.

    D6 (6099487) narrowed SESSION_ID_PATTERN / PRICE_PATTERN / EXPIRES_PATTERN
    from the pre-D6 `[:\s]+` separator (64b8923:107-109) to a mandatory `[:=]`,
    so `session_id 5` / `price 10 sats` / `expires 99` silently became None.
    All three are read on the LIVE harness path by extract_session_info(), which
    run_pay_round() calls for every detected ACK, so the narrowing silently
    emptied the recorded ACK session info. Both separator forms are pinned here;
    the separator itself stays REQUIRED, so a glued field (`session_id5`,
    `price5 sats`, `expires99`) is still not a field.
    """
    eq = ("I (1) TRACKER: TollGate ACK queued "
          "(seq=1, session_id=5, price=10 sats, expires=99)")
    colon = ("I (1) TRACKER: TollGate ACK queued "
             "(seq: 1, session_id: 5, price: 10 sats, expires: 99)")
    spaced = ("I (1) TRACKER: TollGate ACK queued (seq 1) "
              "session_id 5 price 10 sats expires 99")
    expected = {"session_id": 5, "price_sats": 10, "expires_unix": 99}

    for line in (eq, colon, spaced):
        rec = h.parse_tollgate_log_line(line)
        assert rec is not None and rec["kind"] == "ack", line
        assert rec["seq"] == 1, line
        assert rec["session_id"] == 5, line
        assert rec["price_sats"] == 10, line
        assert rec["expires_unix"] == 99, line
        assert h.extract_session_info(line) == expected, line

    # One separator is still mandatory: a glued field is not a field.
    glued = ("I (1) TRACKER: TollGate ACK queued "
             "(session_id5, price5 sats, expires99)")
    assert h.extract_session_info(glued) == {}
    rec = h.parse_tollgate_log_line(glued)
    assert rec is not None and rec["kind"] == "ack"
    assert "session_id" not in rec and "price_sats" not in rec
    assert "expires_unix" not in rec

    # The widening must not weaken the D6 line gate: a NON-TollGate line
    # carrying all three field names is still not a TollGate record, and
    # extract_session_info() is line-scoped too, so it must not read the
    # fields off that line either (widening the three patterns made the
    # unscoped version of the helper reachable for exactly this input).
    telemetry = ("I (1) TRACKER: TX 26 bytes (seq 7) "
                 "session_id 5 price 10 sats expires 99")
    assert h.parse_tollgate_log_line(telemetry) is None
    assert h.classify_tollgate_output(telemetry) == {
        "pay": [], "ack": [], "nack": [], "other": []}
    assert h.extract_session_info(telemetry) == {}

    # ...and a block where only the non-TollGate lines carry the fields still
    # yields nothing, while a TollGate ACK line in the same block does.
    block = telemetry + "\nI (2) TRACKER: TollGate ACK queued (seq=1)\n"
    assert h.extract_session_info(block) == {}
    block += "I (3) TRACKER: TollGate ACK queued expires 99\n"
    assert h.extract_session_info(block) == {"expires_unix": 99}


def test_session_name_accepts_the_real_producer_form():
    """The only producer of a session number prints `session=%u`, not `session_id`.

    mesh-stack/tollgate/components/tollgate_balloon/src/tollgate_balloon.c:255
      ESP_LOGI(TAG, "ACK sent (session=%u, price=%u sats)", ...)
    is the ONLY log producer of a session number, and SESSION_ID_PATTERN
    required the literal `id` after `session`, so that line could not populate
    session_id in ANY revision (pre- or post-D6) — the field was unreachable by
    construction (cold review finding 1 of t_2a65361e, filed as t_388122d0). The
    accepted NAME is now `session` with an optional `_id` suffix, anchored on a
    word boundary; the mandatory separator and the D6 TollGate-line gate are
    unchanged. A tree-wide producer/collision scan at this commit found no
    TollGate-gated line the widened name newly matches except this producer, and
    no TollGate-gated line whose `session` is followed by a number without the
    separator (evidence: collision_scan.log).
    """
    real = "I (12345) tollgate_balloon: ACK sent (session=7, price=10 sats)"
    assert h.extract_session_info(real) == {"session_id": 7, "price_sats": 10}
    rec = h.parse_tollgate_log_line(real)
    assert rec is not None and rec["kind"] == "ack", rec
    assert rec["session_id"] == 7 and rec["price_sats"] == 10, rec

    # Same name, every accepted separator, plus the `_id` spelling of the name.
    for line in (
            "I (1) tollgate_balloon: ACK sent (session: 7, price=10 sats)",
            "I (1) tollgate_balloon: ACK sent (session 7, price=10 sats)",
            "I (1) TRACKER: TollGate ACK queued (session_id=7)",
            "I (1) TRACKER: TollGate ACK queued (session_id: 7)",
            "I (1) TRACKER: TollGate ACK queued (session_id 7)",
            "I (1) TRACKER: TollGate ACK queued (session id 7)",
    ):
        assert h.extract_session_info(line)["session_id"] == 7, line

    # The separator stays REQUIRED and the name stays whole: a glued `session7`,
    # a word that merely ENDS in session (`subsession=7`), a plural
    # (`active_sessions: 3`) and a longer name (`session_timeout=30`) are not
    # fields, and prose ("3 sessions active") is not either.
    assert h.extract_session_info("I (1) TRACKER: TollGate ACK queued (session7)") == {}
    assert h.extract_session_info("I (1) TRACKER: TollGate ACK queued (subsession=7)") == {}
    assert h.extract_session_info("I (1) TRACKER: TollGate ACK queued (xsession 7)") == {}
    assert h.extract_session_info('I (1) tollgate_balloon: active_sessions: 3') == {}
    assert h.extract_session_info("I (1) tollgate_balloon: session_timeout=30") == {}
    assert h.extract_session_info("I (1) tollgate_balloon: 3 sessions active") == {}

    # `expires` has NO producer in this tree (`grep -rn '"expires' tracker/
    # mesh-stack/` matches only struct fields and C test fixtures, never a log
    # line), so expires_unix is only filled if some producer starts printing it.
    # The extraction stays (pinned by
    # test_session_price_expires_accept_the_whitespace_only_forms) and must not
    # invent a value off the session producer.
    assert "expires_unix" not in h.extract_session_info(real)

    # D6 gate unchanged: the same fields on a NON-TollGate line are still not a
    # TollGate record, and extract_session_info() is line-scoped too.
    telemetry = "I (1) TRACKER: TX 26 bytes (seq 7) session=7 price=10 sats"
    assert h.parse_tollgate_log_line(telemetry) is None
    assert h.extract_session_info(telemetry) == {}


def test_wrapped_seq_is_parsed_both_directions():
    """u16 wrap: 65535 is a legal wire value and must survive parsing."""
    assert h.extract_seq(L_PAY_SENT_WRAP) == 65535
    assert h.extract_seq(L_ACK_WRAP) == 65535


def test_telemetry_line_is_not_a_tollgate_line():
    """TAG="TRACKER" telemetry must not be treated as a tollgate message."""
    assert h.parse_tollgate_log_line(L_TELEMETRY) is None
    assert h.parse_tollgate_log_line(L_TELEMETRY_LONG) is None
    assert h.parse_tollgate_output(L_TELEMETRY) == []
    assert h.extract_seq(L_TELEMETRY) is None
    assert h.extract_seq(L_TELEMETRY_LONG) is None


def test_tracker_tag_is_not_an_ack():
    """The old ACK pattern matched "ack" inside TAG="TRACKER" (false positive)."""
    assert h.parse_tollgate_log_line(L_TELEMETRY) is None
    classified = h.classify_tollgate_output(L_TELEMETRY + "\n" + L_TELEMETRY_LONG + "\n")
    assert classified["ack"] == []
    assert classified["nack"] == []
    assert classified["pay"] == []


def test_ack_and_nack_are_distinguished():
    """NACK contains "ack"; it must classify as nack, never as ack."""
    ack = h.parse_tollgate_log_line(L_ACK)
    nack = h.parse_tollgate_log_line(L_NACK)
    assert ack is not None and ack["kind"] == "ack"
    assert nack is not None and nack["kind"] == "nack"
    assert nack["seq"] == 3
    classified = h.classify_tollgate_output(L_NACK + "\n" + L_ACK + "\n")
    assert [r["seq"] for r in classified["ack"]] == [1]
    assert [r["seq"] for r in classified["nack"]] == [3]


def test_pay_line_classifies_as_pay():
    assert h.parse_tollgate_log_line(L_PAY_SENT)["kind"] == "pay"
    assert h.parse_tollgate_log_line(L_PAY_RX)["kind"] == "pay"


def test_seq_zero_is_preserved_not_dropped():
    """`if ack_seq:` truthiness dropped a parsed 0 — the wrap target value."""
    rec = h.parse_tollgate_log_line(L_ACK_ZERO)
    assert rec is not None
    assert rec["seq"] == 0
    assert h.extract_seq(L_ACK_ZERO) == 0
    assert h.extract_seq(L_PAY_SENT_ZERO) == 0


def test_verdict_pass_on_matching_seq_including_zero():
    code, label = h.compute_verdict([_round(0, 0)])
    assert code == 0, label
    code, label = h.compute_verdict([_round(1, 1)])
    assert code == 0, label
    code, label = h.compute_verdict([_round(65535, 65535)])
    assert code == 0, label


def test_verdict_partial_on_seq_mismatch():
    code, label = h.compute_verdict([_round(1, 2)])
    assert code == 1, label


def test_verdict_fail_when_no_ack():
    code, label = h.compute_verdict([_round(1, None)])
    assert code == 2, label


def test_verdict_partial_on_nack_only():
    r = _round(1, None, nack_seq=1)
    code, label = h.compute_verdict([r])
    assert code == 1, label


def test_verdict_fail_when_nothing_sent():
    r = _round(None, None)
    r["pay_sent"] = False
    code, label = h.compute_verdict([r])
    assert code == 2, label


def test_end_to_end_round_parse_from_log_block():
    """Full round: board A's queued line + board B's ACK line → PASS verdict."""
    a_response = L_PAY_SENT_ZERO
    rx_output = L_PAY_RX + "\n" + L_ACK_ZERO + "\n" + L_TELEMETRY + "\n"

    pay_recs = h.classify_tollgate_output(a_response)["pay"]
    assert len(pay_recs) == 1 and pay_recs[0]["seq"] == 0

    classified = h.classify_tollgate_output(rx_output)
    assert len(classified["ack"]) == 1
    assert classified["ack"][0]["seq"] == 0
    assert classified["nack"] == []

    result = _round(pay_recs[0]["seq"], classified["ack"][0]["seq"])
    assert result["ack_seq"] is not None  # seq 0 must not be treated as "missing"
    code, label = h.compute_verdict([result])
    assert code == 0, label


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
