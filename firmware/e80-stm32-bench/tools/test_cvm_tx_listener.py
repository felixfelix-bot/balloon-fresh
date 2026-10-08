#!/usr/bin/env python3
"""test_cvm_tx_listener.py — RED tests for the TX-side ARMED listener.

Scope (kanban t_412706f8, docs/ADR-range-sync-cvm.md §2.2/§2.3/§2.4): the TX
half of the CVM range-sync handshake. ``cvm_sync`` (P1 message layer, already
merged) ships the message schema + a bare ``ArmedSubscriber``; this module adds
the *production TX listener*:

  - BROAD kind-1059 subscribe (no restrictive server-side ``#p`` filter, which
    is unreliable) + a CLIENT-SIDE npub allowlist on receipt — non-allowlisted
    authors are dropped
  - ARMED payload validation against the ADR schema (session_id, stop,
    t_ready_utc, preset_hash, seq); ``session_id`` must be ``%y%m%d%H%M`` +
    3 lowercase-hex nonce
  - events authored by SELF are ignored
  - freshness watchdog: reject any ARMED whose ``created_at`` skews more than
    ``MAX_CREATED_AT_SKEW`` (60 s) from the local clock; ABORT the session when
    no fresh ARMED arrives within ``STALE_ABORT`` (30 s) of the last one (or of
    start-up), logging a clear abort reason
  - relay failover set: nostr.mom, relay.primal.net, nos.lol,
    relay2.contextvm.org, relay.nostr.band — ``relay.contextvm.org`` is DEAD and
    must never be included
  - keys read from ENV VARS ONLY, never CLI args; client key MUST differ from
    the server key (asserted at startup)

Pure-Python: no ``nostr_sdk`` import and no real relays. The transport's
unwrap/send seam is exercised with a fake nostr module.

Run:  python3 -m pytest test_cvm_tx_listener.py -v
"""

from __future__ import annotations

import ast
import asyncio
import json
import os
import sys
import time
import unittest
from pathlib import Path

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

MODULE_PATH = Path(_TOOLS_DIR) / "cvm_tx_listener.py"

REQUIRED_RELAYS = [
    "wss://nostr.mom",
    "wss://relay.primal.net",
    "wss://nos.lol",
    "wss://relay2.contextvm.org",
    "wss://relay.nostr.band",
]
DEAD_RELAY = "wss://relay.contextvm.org"

# Fixture keys (no real key material — 64-hex strings only).
RX_PUB = "aa" * 32          # allowlisted RX publisher
OTHER_PUB = "bb" * 32       # non-allowlisted third party
SELF_PUB = "cc" * 32        # our own TX key
SERVER_PUB = "dd" * 32      # board-server key (must differ from SELF)

SID = "2608301440a3f"       # %y%m%d%H%M + 3-hex nonce


def _run(coro):
    """Run a coroutine to completion (one fresh loop per call)."""
    return asyncio.run(coro)


def _armed(session_id=SID, stop="50m", t_ready_utc=1788096000,
           preset_hash="abc123", seq=1, created_at=None, author=RX_PUB,
           **extra):
    msg = {
        "type": "ARMED",
        "session_id": session_id,
        "stop": stop,
        "t_ready_utc": t_ready_utc,
        "preset_hash": preset_hash,
        "seq": seq,
        "created_at": int(time.time()) if created_at is None else created_at,
        "author": author,
    }
    msg.update(extra)
    return msg


class MockRelayBus:
    """In-memory relay pool: publish() fans out to all subscribers."""

    def __init__(self):
        self.subscribers = []
        self.published = []
        self.subscribed_filters = []

    async def subscribe(self, handler, flt=None):
        self.subscribers.append(handler)
        self.subscribed_filters.append(flt)

    async def publish(self, event: dict):
        self.published.append(event)
        for h in list(self.subscribers):
            await h(event)


# ===========================================================================
# CONSTANTS — the 60 s / 30 s thresholds must be NAMED and asserted
# ===========================================================================

class TestWatchdogConstants(unittest.TestCase):
    def test_max_created_at_skew_is_60(self):
        import cvm_tx_listener as m
        self.assertEqual(m.MAX_CREATED_AT_SKEW, 60.0)

    def test_stale_abort_is_30(self):
        import cvm_tx_listener as m
        self.assertEqual(m.STALE_ABORT, 30.0)

    def test_constants_are_single_canonical_source(self):
        # cvm_sync owns the values; the listener must not fork them.
        import cvm_sync
        import cvm_tx_listener as m
        self.assertEqual(m.MAX_CREATED_AT_SKEW, cvm_sync.MAX_CREATED_AT_SKEW)
        self.assertEqual(m.STALE_ABORT, cvm_sync.STALE_ABORT)


# ===========================================================================
# SESSION ID + PAYLOAD VALIDATION (ADR schema)
# ===========================================================================

class TestSessionIdValidation(unittest.TestCase):
    def test_accepts_10_digits_plus_3_hex(self):
        from cvm_tx_listener import validate_session_id
        self.assertTrue(validate_session_id("2608301440a3f"))
        self.assertTrue(validate_session_id("2608301440000"))

    def test_rejects_bad_lengths(self):
        from cvm_tx_listener import validate_session_id
        self.assertFalse(validate_session_id("260830144a3f"))     # 12 chars
        self.assertFalse(validate_session_id("2608301440a3ff"))   # 14 chars
        self.assertFalse(validate_session_id("26083014a3f"))      # 12 chars

    def test_rejects_non_hex_nonce_and_uppercase(self):
        from cvm_tx_listener import validate_session_id
        self.assertFalse(validate_session_id("2608301440A3F"))    # uppercase
        self.assertFalse(validate_session_id("2608301440g3f"))    # non-hex
        self.assertFalse(validate_session_id("2608301440z3f"))

    def test_rejects_non_digit_timestamp(self):
        from cvm_tx_listener import validate_session_id
        self.assertFalse(validate_session_id("26083a1440a3f"))


class TestPayloadValidation(unittest.TestCase):
    def test_valid_armed_passes(self):
        from cvm_tx_listener import parse_armed
        ok, reason = parse_armed(_armed(), now=int(time.time()),
                                 allowed_npubs={RX_PUB}, self_pubkey=SELF_PUB)
        self.assertTrue(ok, reason)
        self.assertEqual(reason, "")

    def test_missing_each_required_field_rejected(self):
        from cvm_tx_listener import parse_armed
        for field in ("session_id", "stop", "t_ready_utc", "preset_hash", "seq"):
            msg = _armed()
            del msg[field]
            ok, reason = parse_armed(msg)
            self.assertFalse(ok, field)
            self.assertIn(field, reason)

    def test_non_armed_type_rejected(self):
        from cvm_tx_listener import parse_armed
        ok, reason = parse_armed({"type": "STARTED", "session_id": SID})
        self.assertFalse(ok)

    def test_bad_session_id_rejected(self):
        from cvm_tx_listener import parse_armed
        ok, reason = parse_armed(_armed(session_id="nope"))
        self.assertFalse(ok)
        self.assertIn("session_id", reason)

    def test_bad_seq_rejected(self):
        from cvm_tx_listener import parse_armed
        ok, reason = parse_armed(_armed(seq="not-a-number"))
        self.assertFalse(ok)
        self.assertIn("seq", reason)


# ===========================================================================
# ALLOWLIST + SELF FILTER
# ===========================================================================

class TestAllowlistFiltering(unittest.TestCase):
    def test_non_allowlisted_author_dropped(self):
        from cvm_tx_listener import parse_armed
        ok, reason = parse_armed(_armed(author=OTHER_PUB), now=int(time.time()),
                                 allowed_npubs={RX_PUB}, self_pubkey=SELF_PUB)
        self.assertFalse(ok)
        self.assertIn("allowlist", reason)

    def test_allowlisted_author_accepted(self):
        from cvm_tx_listener import parse_armed
        ok, _ = parse_armed(_armed(author=RX_PUB), now=int(time.time()),
                            allowed_npubs={RX_PUB}, self_pubkey=SELF_PUB)
        self.assertTrue(ok)

    def test_no_allowlist_accepts_any_author(self):
        from cvm_tx_listener import parse_armed
        ok, _ = parse_armed(_armed(author=OTHER_PUB), now=int(time.time()),
                            allowed_npubs=None, self_pubkey=SELF_PUB)
        self.assertTrue(ok)

    def test_empty_author_rejected_when_allowlist_defined(self):
        from cvm_tx_listener import parse_armed
        ok, reason = parse_armed(_armed(author=""), now=int(time.time()),
                                 allowed_npubs={RX_PUB}, self_pubkey=SELF_PUB)
        self.assertFalse(ok)


class TestSelfIgnore(unittest.TestCase):
    def test_event_from_self_is_ignored(self):
        from cvm_tx_listener import parse_armed
        ok, reason = parse_armed(_armed(author=SELF_PUB), now=int(time.time()),
                                 allowed_npubs={SELF_PUB}, self_pubkey=SELF_PUB)
        self.assertFalse(ok)
        self.assertIn("self", reason.lower())


class TestListenerDropsNonAllowlistedEvents(unittest.TestCase):
    def test_listener_keeps_only_allowlisted(self):
        from cvm_tx_listener import TxArmedListener
        bus = MockRelayBus()
        listener = TxArmedListener(bus, allowed_npubs={RX_PUB},
                                   self_pubkey=SELF_PUB)
        _run(listener.start())
        _run(listener._on_event(_armed(author=OTHER_PUB)))
        self.assertIsNone(listener.last_armed)
        _run(listener._on_event(_armed(author=RX_PUB)))
        self.assertIsNotNone(listener.last_armed)
        self.assertEqual(listener.last_armed["author"], RX_PUB)


# ===========================================================================
# FRESHNESS WATCHDOG — clock skew (>60 s) and stale abort (>30 s)
# ===========================================================================

class TestClockSkewRejection(unittest.TestCase):
    def test_skew_above_60s_rejected(self):
        from cvm_tx_listener import parse_armed
        now = 2000000000
        ok, reason = parse_armed(_armed(created_at=now - 61), now=now)
        self.assertFalse(ok)
        self.assertIn("skew", reason)

    def test_skew_just_under_60s_accepted(self):
        from cvm_tx_listener import parse_armed
        now = 2000000000
        ok, _ = parse_armed(_armed(created_at=now - 59), now=now)
        self.assertTrue(ok)

    def test_skew_exactly_60s_accepted(self):
        # threshold is a STRICT '>' — exactly the named constant passes
        from cvm_tx_listener import parse_armed, MAX_CREATED_AT_SKEW
        now = 2000000000
        ok, _ = parse_armed(_armed(created_at=now - int(MAX_CREATED_AT_SKEW)),
                            now=now)
        self.assertTrue(ok)

    def test_future_skew_rejected(self):
        from cvm_tx_listener import parse_armed
        now = 2000000000
        ok, reason = parse_armed(_armed(created_at=now + 90), now=now)
        self.assertFalse(ok)
        self.assertIn("skew", reason)


class TestStaleAbort(unittest.TestCase):
    def test_not_stale_without_any_armed(self):
        from cvm_tx_listener import TxArmedListener
        bus = MockRelayBus()
        listener = TxArmedListener(bus, allowed_npubs={RX_PUB},
                                   self_pubkey=SELF_PUB, now_fn=lambda: 1000.0)
        self.assertFalse(listener.check_stale(now=1000.0))

    def test_stale_after_30s_from_last_good(self):
        from cvm_tx_listener import TxArmedListener
        bus = MockRelayBus()
        clock = {"t": 1000.0}
        listener = TxArmedListener(bus, allowed_npubs={RX_PUB},
                                   self_pubkey=SELF_PUB,
                                   now_fn=lambda: clock["t"])
        _run(
            listener._on_event(_armed(created_at=1000)))
        listener.last_armed_at = 1000.0
        self.assertFalse(listener.check_stale(now=1029.0))
        self.assertTrue(listener.check_stale(now=1031.0))

    def test_boundary_exactly_30s_is_not_stale(self):
        from cvm_tx_listener import TxArmedListener, STALE_ABORT
        bus = MockRelayBus()
        listener = TxArmedListener(bus, allowed_npubs={RX_PUB},
                                   self_pubkey=SELF_PUB, now_fn=lambda: 1000.0)
        listener.last_armed_at = 1000.0
        self.assertFalse(listener.check_stale(now=1000.0 + STALE_ABORT))

    def test_tick_aborts_with_clear_reason(self):
        from cvm_tx_listener import TxArmedListener
        bus = MockRelayBus()
        logged = []
        listener = TxArmedListener(bus, allowed_npubs={RX_PUB},
                                   self_pubkey=SELF_PUB,
                                   now_fn=lambda: 1000.0, log=logged.append)
        listener.last_armed_at = 1000.0
        aborted = listener.tick(now=1040.0)
        self.assertTrue(aborted)
        self.assertTrue(listener.aborted)
        self.assertIn("30", listener.abort_reason)
        self.assertIn("stale", listener.abort_reason.lower())
        self.assertTrue(any("stale" in line.lower() for line in logged))

    def test_tick_not_aborted_when_fresh(self):
        from cvm_tx_listener import TxArmedListener
        bus = MockRelayBus()
        listener = TxArmedListener(bus, allowed_npubs={RX_PUB},
                                   self_pubkey=SELF_PUB, now_fn=lambda: 1000.0)
        listener.last_armed_at = 1000.0
        self.assertFalse(listener.tick(now=1005.0))
        self.assertFalse(listener.aborted)

    def test_abort_when_no_armed_ever_within_30s_of_start(self):
        from cvm_tx_listener import TxArmedListener
        bus = MockRelayBus()
        listener = TxArmedListener(bus, allowed_npubs={RX_PUB},
                                   self_pubkey=SELF_PUB, now_fn=lambda: 1000.0)
        # started_at defaults to now_fn() at construction == 1000.0
        self.assertFalse(listener.tick(now=1025.0))
        self.assertTrue(listener.tick(now=1035.0))
        self.assertIn("30", listener.abort_reason)


# ===========================================================================
# RELAY FAILOVER SET
# ===========================================================================

class TestRelayFailover(unittest.TestCase):
    def test_default_set_is_exactly_the_adr_five(self):
        from cvm_tx_listener import failover_relays
        self.assertEqual(failover_relays(), REQUIRED_RELAYS)

    def test_dead_relay_never_included_even_if_supplied(self):
        from cvm_tx_listener import failover_relays
        got = failover_relays([DEAD_RELAY])
        self.assertNotIn(DEAD_RELAY, got)
        self.assertEqual(got, REQUIRED_RELAYS)

    def test_extra_relays_appended_and_deduped(self):
        from cvm_tx_listener import failover_relays
        got = failover_relays(["wss://my.relay", "wss://nostr.mom"])
        self.assertEqual(got[-1], "wss://my.relay")
        self.assertEqual(got.count("wss://nostr.mom"), 1)


# ===========================================================================
# ENV-ONLY KEYS + client != server
# ===========================================================================

class TestEnvOnlyKeys(unittest.TestCase):
    def test_load_env_secrets_reads_client_and_server(self):
        from cvm_tx_listener import load_env_secrets
        env = {"CVM_TX_NSEC": "nsec1tx", "CVM_SERVER_NSEC": "nsec1srv"}
        sec = load_env_secrets(env)
        self.assertEqual(sec["client"], "nsec1tx")
        self.assertEqual(sec["server"], "nsec1srv")

    def test_alias_client_names_accepted(self):
        from cvm_tx_listener import load_env_secrets
        env = {"CVM_CLIENT_HEX": "ab" * 32, "CVM_SERVER_HEX": "cd" * 32}
        sec = load_env_secrets(env)
        self.assertEqual(sec["client"], "ab" * 32)

    def test_missing_client_raises(self):
        from cvm_tx_listener import load_env_secrets, EnvKeyError
        with self.assertRaises(EnvKeyError):
            load_env_secrets({"CVM_SERVER_NSEC": "nsec1srv"})

    def test_missing_server_raises(self):
        from cvm_tx_listener import load_env_secrets, EnvKeyError
        with self.assertRaises(EnvKeyError):
            load_env_secrets({"CVM_TX_NSEC": "nsec1tx"})

    def test_assert_keys_differ_raises_on_equal(self):
        from cvm_tx_listener import assert_keys_differ, KeyCollisionError
        with self.assertRaises(KeyCollisionError):
            assert_keys_differ(SELF_PUB, SELF_PUB)

    def test_assert_keys_differ_ok_on_distinct(self):
        from cvm_tx_listener import assert_keys_differ
        assert_keys_differ(SELF_PUB, SERVER_PUB)  # must not raise

    def test_cli_exposes_no_key_bearing_option(self):
        src = MODULE_PATH.read_text()
        opts = _argparse_option_strings(src)
        bad = [o for o in opts
               if any(tok in o.lower() for tok in ("nsec", "hex", "secret"))]
        self.assertEqual(bad, [], "key-bearing CLI options: {}".format(bad))


def _argparse_option_strings(src: str):
    opts = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call):
            continue
        name = node.func
        if not isinstance(name, ast.Attribute) or name.attr != "add_argument":
            continue
        for a in node.args:
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                opts.append(a.value)
    return opts


# ===========================================================================
# TRANSPORT — broad subscribe + client-side unwrap
# ===========================================================================

class _FakeKind:
    def __init__(self, k):
        self.k = k


class _FakeFilter:
    def __init__(self):
        self.kinds_arg = None
        self.tags = {}

    def kinds(self, ks):
        self.kinds_arg = list(ks)
        return self

    def tag(self, name, values):  # a restrictive #p filter must NOT be used
        self.tags[name] = list(values)
        return self


class _FakeRumor:
    def __init__(self, content, author_hex):
        self._content = content
        self._author = author_hex

    def content(self):
        return self._content

    def author(self):
        return _FakeAuthor(self._author)


class _FakeAuthor:
    def __init__(self, hex_):
        self._hex = hex_

    def to_hex(self):
        return self._hex


async def _fake_from_gift_wrap(signer, event):
    return event.unwrapped


class _FakeUnwrappedGift:
    from_gift_wrap = staticmethod(_fake_from_gift_wrap)


class _FakeEvent:
    def __init__(self, p_tag, inner_msg, author_hex):
        self._p_tag = p_tag
        rumor = _FakeRumor(json.dumps(inner_msg), author_hex)
        self.unwrapped = type("U", (), {"rumor": lambda self_: rumor})()

    def tags(self):
        outer = self

        class _T:
            def to_vec(self):
                if outer._p_tag is None:
                    return []
                return [_FakeTag(["p", outer._p_tag])]

        return _T()


class _FakeTag:
    def __init__(self, vals):
        self._vals = vals

    def as_vec(self):
        return self._vals


class _FakeNostr:
    Kind = _FakeKind
    Filter = _FakeFilter
    UnwrappedGift = _FakeUnwrappedGift


class TestTransportBroadSubscribe(unittest.TestCase):
    def _transport(self, handler_calls):
        from cvm_tx_listener import NostrRxTransport

        async def handler(msg):
            handler_calls.append(msg)

        t = NostrRxTransport(_FakeNostr, signer=object(), client=None,
                             client_pubkey_hex=SELF_PUB)
        return t, handler

    def test_subscribe_is_broad_no_p_tag_filter(self):
        from cvm_tx_listener import NostrRxTransport
        flt_holder = {}

        class _Client:
            async def subscribe(self, flt, opts):
                flt_holder["flt"] = flt

        async def handler(msg):
            pass

        t = NostrRxTransport(_FakeNostr, signer=object(), client=_Client(),
                             client_pubkey_hex=SELF_PUB)
        _run(t.subscribe(handler))
        flt = flt_holder["flt"]
        self.assertEqual([k.k for k in flt.kinds_arg], [1059])
        self.assertEqual(flt.tags, {}, "server-side #p filter must not be used")

    def test_handle_gift_wrap_feeds_inner_msg_with_rumor_author(self):
        calls = []
        t, handler = self._transport(calls)
        t._handler = handler
        # inner payload claims a spoofed author; the UNWRAPPED (rumor) author
        # is authoritative and must overwrite it.
        ev = _FakeEvent(SELF_PUB, _armed(author=OTHER_PUB), RX_PUB)
        _run(t.handle_gift_wrap(ev))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["session_id"], SID)
        # allowlist must key off the UNWRAPPED (rumor) author
        self.assertEqual(calls[0]["author"], RX_PUB)

    def test_handle_gift_wrap_ignores_wrong_p_tag(self):
        calls = []
        t, handler = self._transport(calls)
        t._handler = handler
        ev = _FakeEvent(OTHER_PUB, _armed(author=RX_PUB), RX_PUB)
        _run(t.handle_gift_wrap(ev))
        self.assertEqual(calls, [])

    def test_notification_adapter_forwards_to_transport(self):
        from cvm_tx_listener import TxHandleNotification
        seen = []

        class _T:
            async def handle_gift_wrap(self, event):
                seen.append(event)

        adapter = TxHandleNotification(_T())
        _run(
            adapter.handle("wss://r", "sub", "EVENT"))
        self.assertEqual(seen, ["EVENT"])
        # non-event messages are ignored without error
        _run(
            adapter.handle_msg("wss://r", {"type": "EOSE"}))
