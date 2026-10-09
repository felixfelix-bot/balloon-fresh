#!/usr/bin/env python3
"""test_relay_failover_publisher.py — RED suite for card t_120db4f6.

Pins the relay failover publisher contract:

  (a) success when only a SUBSET of relays accept;
  (b) a dead/timing-out/hard-erroring relay MUST NOT abort the publish;
  (c) relay.contextvm.org is absent from the active set (runtime + source scan);
  (d) identical session fields yield the SAME event id (deterministic NIP-59
      ephemeral secret) and repeated publishes are deduped in-process.

Everything runs against a FAKE relay transport (accept / timeout / hard error /
reject) — no live network, no nostr_sdk.

Run:  python3 -m pytest tools/test_relay_failover_publisher.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import cvm_armed_publisher as choke  # noqa: E402
import relay_failover as rf  # noqa: E402

DEAD_RELAY = "wss://relay.contextvm.org"
#: The contractual relay set is the CANONICAL constant (single source of
#: truth: ``cvm_armed_publisher.FAILOVER_RELAYS``) — never restated here, so
#: the tools tree keeps exactly one literal definition of the relay list.
REQUIRED_RELAYS = list(choke.FAILOVER_RELAY_URLS)
REQUIRED_HOSTS = list(choke.FAILOVER_RELAYS)

_TX = "a" * 64
_AUTHOR = "b" * 64
_SESSION = {
    "session_id": "2608301320a3f",
    "stop": "50m",
    "t_ready_utc": 1788096000,
    "preset_hash": "abc123",
    "seq": 1,
}


def _armed_msg(**over):
    msg = {
        "type": "ARMED",
        "session_id": _SESSION["session_id"],
        "stop": _SESSION["stop"],
        "t_ready_utc": _SESSION["t_ready_utc"],
        "preset_hash": _SESSION["preset_hash"],
        "seq": _SESSION["seq"],
        "created_at": _SESSION["t_ready_utc"],
    }
    msg.update(over)
    return msg


class FakeRelayTransport:
    """Deterministic in-memory transport: url -> behaviour.

    behaviours: "accept" | "timeout" | "error" | ("reject", "reason").
    """

    def __init__(self, behaviour: dict):
        self.behaviour = behaviour
        self.calls = []  # list[(url, event_id)]

    async def send(self, url: str, event: dict) -> None:
        self.calls.append((url, event.get("id")))
        mode = self.behaviour.get(url, "accept")
        if mode == "accept":
            return
        if mode == "timeout":
            await asyncio.sleep(3600)  # publisher's wait_for must cut this off
        if mode == "error":
            raise RuntimeError("boom: relay down")
        if isinstance(mode, tuple) and mode[0] == "reject":
            raise rf.RelayRejected(mode[1])
        raise AssertionError("unknown behaviour {!r}".format(mode))


# ===========================================================================
# (c) exact relay set + dead-relay absence
# ===========================================================================

class TestRelaySet(unittest.TestCase):

    def test_exact_relay_set_matches_the_contract(self):
        self.assertEqual(rf.failover_relays(), REQUIRED_RELAYS)

    def test_active_hosts_are_exactly_the_five_required(self):
        hosts = {u.split("://", 1)[1] for u in rf.failover_relays()}
        self.assertEqual(hosts, set(REQUIRED_HOSTS))

    def test_dead_relay_absent_from_active_set(self):
        self.assertNotIn(DEAD_RELAY, rf.failover_relays())
        # even when supplied as an extra, it is filtered out
        self.assertNotIn(DEAD_RELAY, rf.failover_relays(extra=[DEAD_RELAY]))

    def test_no_duplicate_relays(self):
        relays = rf.failover_relays(extra=REQUIRED_RELAYS)
        self.assertEqual(len(relays), len(set(relays)))

    def test_bare_dead_host_appears_only_in_dead_declarations(self):
        """Source scan of the PUBLISH PATH: the bare dead host only lives in
        DEAD/absence lines.

        Scope = the modules that define/consume the failover set. Standalone
        live-probe scripts (cvm_relay_test.py) are not the publish path.
        """
        publish_path = ("relay_failover.py", "cvm_armed_publisher.py",
                        "cvm_sync.py")
        offenders = []
        for name in publish_path:
            path = os.path.join(_TOOLS_DIR, name)
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, 1):
                    if "relay.contextvm.org" not in line:
                        continue
                    low = line.lower()
                    if "dead" in low:
                        continue  # a DEAD-relay declaration is allowed
                    offenders.append("{}:{}: {}".format(
                        os.path.basename(path), lineno, line.strip()))
        self.assertEqual(offenders, [], "dead host outside a DEAD declaration")


# ===========================================================================
# (a)+(b) failover: subset accept, dead relay does not abort
# ===========================================================================

class TestFailover(unittest.TestCase):

    def _publisher(self, behaviour, timeout=0.05):
        transport = FakeRelayTransport(behaviour)
        return rf.RelayFailoverPublisher(transport, timeout=timeout), transport

    def test_subset_accept_is_success_with_per_relay_outcomes(self):
        pub, transport = self._publisher({
            "wss://nostr.mom": "accept",
            "wss://relay.primal.net": "timeout",
            "wss://nos.lol": "error",
            "wss://relay2.contextvm.org": "accept",
        })
        result = asyncio.run(pub.publish(_armed_msg(), _SESSION))
        self.assertTrue(result.ok)
        by_url = {o.url: o for o in result.outcomes}
        self.assertEqual(len(result.outcomes), 5)
        self.assertTrue(by_url["wss://nostr.mom"].accepted)
        self.assertEqual(by_url["wss://relay.primal.net"].reason, "timeout")
        self.assertIn("error", by_url["wss://nos.lol"].reason.lower())
        # the relay with no behaviour defaults to accept
        self.assertTrue(by_url["wss://relay.nostr.band"].accepted)
        self.assertEqual({o.url for o in result.accepted},
                         {"wss://nostr.mom", "wss://relay2.contextvm.org",
                          "wss://relay.nostr.band"})

    def test_dead_relay_does_not_abort_publish(self):
        # four of five relays are dead-ish; one accepts -> publish succeeds
        pub, _ = self._publisher({
            "wss://nostr.mom": "error",
            "wss://relay.primal.net": "timeout",
            "wss://nos.lol": "error",
            "wss://relay2.contextvm.org": "timeout",
        })
        result = asyncio.run(pub.publish(_armed_msg(), _SESSION))
        self.assertTrue(result.ok)
        self.assertEqual(len(result.accepted), 1)
        self.assertEqual(len(result.failed), 4)

    def test_rejection_reason_is_aggregated(self):
        pub, _ = self._publisher({
            "wss://nos.lol": ("reject", "blocked: policy"),
        })
        result = asyncio.run(pub.publish(_armed_msg(), _SESSION))
        by_url = {o.url: o for o in result.outcomes}
        self.assertFalse(by_url["wss://nos.lol"].accepted)
        self.assertIn("blocked: policy", by_url["wss://nos.lol"].reason)

    def test_all_relays_fail_raises_publish_failed(self):
        pub, _ = self._publisher(
            {u: "error" for u in REQUIRED_RELAYS})
        with self.assertRaises(rf.PublishFailedError):
            asyncio.run(pub.publish(_armed_msg(), _SESSION))

    def test_per_relay_timeout_is_enforced(self):
        pub, _ = self._publisher(
            {u: "timeout" for u in REQUIRED_RELAYS}, timeout=0.02)
        with self.assertRaises(rf.PublishFailedError) as cm:
            asyncio.run(pub.publish(_armed_msg(), _SESSION))
        outcomes = cm.exception.outcomes
        self.assertEqual(len(outcomes), 5)
        self.assertTrue(all(o.reason == "timeout" for o in outcomes))

    def test_dead_relay_never_receives_the_event(self):
        pub, transport = self._publisher({})
        asyncio.run(pub.publish(_armed_msg(), _SESSION))
        sent = {u for u, _ in transport.calls}
        self.assertNotIn(DEAD_RELAY, sent)
        self.assertEqual(sent, set(REQUIRED_RELAYS))


# ===========================================================================
# (d) deterministic event id + in-process dedupe
# ===========================================================================

class TestIdempotency(unittest.TestCase):

    def test_same_session_fields_yield_the_same_event_id(self):
        a = rf.deterministic_giftwrap(_armed_msg(), _SESSION, tx_pubkey_hex=_TX,
                                      author_pubkey_hex=_AUTHOR)
        b = rf.deterministic_giftwrap(_armed_msg(), _SESSION, tx_pubkey_hex=_TX,
                                      author_pubkey_hex=_AUTHOR)
        self.assertEqual(a["id"], b["id"])
        self.assertEqual(a, b)

    def test_different_seq_yields_a_different_event_id(self):
        a = rf.deterministic_giftwrap(_armed_msg(seq=1), _SESSION, _TX, _AUTHOR)
        b = rf.deterministic_giftwrap(_armed_msg(seq=2), _SESSION, _TX, _AUTHOR)
        self.assertNotEqual(a["id"], b["id"])

    def test_ephemeral_secret_is_deterministic_and_session_derived(self):
        s1 = rf.derive_ephemeral_secret(_SESSION)
        s2 = rf.derive_ephemeral_secret(dict(_SESSION))
        self.assertEqual(s1, s2)
        self.assertEqual(len(s1), 32)
        other = dict(_SESSION, seq=9)
        self.assertNotEqual(s1, rf.derive_ephemeral_secret(other))
        # not the plain session id or any trivially-guessable material
        self.assertNotIn(_SESSION["session_id"].encode(), s1)

    def test_repeated_publish_is_deduped_in_process(self):
        transport = FakeRelayTransport({})
        pub = rf.RelayFailoverPublisher(transport, timeout=0.05)
        r1 = asyncio.run(pub.publish(_armed_msg(), _SESSION))
        calls_after_first = len(transport.calls)
        r2 = asyncio.run(pub.publish(_armed_msg(), _SESSION))
        self.assertTrue(r1.ok and r2.ok)
        # the transport is NOT called again for the same logical event
        self.assertEqual(len(transport.calls), calls_after_first)
        self.assertEqual(r1, r2)


# ===========================================================================
# gift-wrap choke-point only — no plaintext event ever
# ===========================================================================

class TestGiftWrapChokePoint(unittest.TestCase):

    def test_wrapped_event_is_kind_1059(self):
        wrapped = rf.deterministic_giftwrap(_armed_msg(), _SESSION, _TX, _AUTHOR)
        self.assertEqual(wrapped["kind"], 1059)

    def test_inner_event_uses_the_choke_point_builder(self):
        seen = {}
        real = choke.build_inner_event

        def spy(msg, tx_pubkey_hex, author_pubkey_hex=None, created_at=None):
            seen["called"] = True
            return real(msg, tx_pubkey_hex,
                        author_pubkey_hex=author_pubkey_hex,
                        created_at=created_at)

        old = choke.build_inner_event
        try:
            choke.build_inner_event = spy
            rf.deterministic_giftwrap(_armed_msg(), _SESSION, _TX, _AUTHOR)
        finally:
            choke.build_inner_event = old
        self.assertTrue(seen.get("called"),
                        "failover must build the inner event via the choke-point")

    def test_non_giftwrap_event_is_refused(self):
        transport = FakeRelayTransport({})
        pub = rf.RelayFailoverPublisher(transport, timeout=0.05)

        def bad_wrap(msg, session_fields):
            return {"id": "x", "kind": 1, "content": "plaintext!"}

        with self.assertRaises(choke.PlaintextKindError):
            asyncio.run(pub.publish(_armed_msg(), _SESSION, wrap=bad_wrap))
        self.assertEqual(transport.calls, [])

    def test_plaintext_tally_type_is_refused(self):
        transport = FakeRelayTransport({})
        pub = rf.RelayFailoverPublisher(transport, timeout=0.05)
        with self.assertRaises(choke.PlaintextKindError):
            asyncio.run(pub.publish({"type": "TALLY", "session_id": "x"},
                                    _SESSION))
        self.assertEqual(transport.calls, [])


if __name__ == "__main__":
    unittest.main()
