#!/usr/bin/env python3
"""test_relay_testkit.py — pins for the relay fan-out scaffolding (t_588b1d1b).

Verifies, with no live network anywhere:

  (a) the exact five-host failover set is defined once and exported;
  (b) ``relay.contextvm.org`` is absent at runtime AND in the publish-path
      sources, using a hostname-boundary scan that does not false-positive on
      the legitimate ``relay2.contextvm.org``;
  (c) the fake relay transport double is importable and its ``ACCEPT`` /
      ``TIMEOUT`` / ``HARD_ERROR`` behaviours drive the real failover publisher
      end to end (the smoke test).

Run:  python3 -m pytest firmware/e80-stm32-bench/tools/test_relay_testkit.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import relay_testkit as kit  # noqa: E402
import relay_failover as rf  # noqa: E402

#: The contractual relay set, restated here in bare-host form so the test fails
#: if the constant is ever silently edited.
EXPECTED_HOSTS = [
    "nostr.mom",
    "relay.primal.net",
    "nos.lol",
    "relay2.contextvm.org",
    "relay.nostr.band",
]
EXPECTED_URLS = ["wss://" + host for host in EXPECTED_HOSTS]
DEAD_HOST = "relay.contextvm.org"

#: Modules that define/consume the failover set (the publish path). Standalone
#: live-probe scripts (cvm_relay_test.py) are deliberately out of scope.
PUBLISH_PATH = ("relay_failover.py", "cvm_armed_publisher.py", "cvm_sync.py")

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


class TestRelaySetConstant(unittest.TestCase):
    """(a) ONE exported constant, exact order, no normalisation."""

    def test_exact_bare_host_set_matches_the_contract(self):
        self.assertEqual(kit.FAILOVER_RELAYS, EXPECTED_HOSTS)

    def test_url_set_is_derived_from_the_host_set(self):
        self.assertEqual(kit.FAILOVER_RELAY_URLS, EXPECTED_URLS)

    def test_publisher_relay_set_matches_the_constant(self):
        self.assertEqual(rf.failover_relays(), EXPECTED_URLS)
        hosts = {u.split("://", 1)[1] for u in rf.failover_relays()}
        self.assertEqual(hosts, set(EXPECTED_HOSTS))


class TestDeadHostAbsence(unittest.TestCase):
    """(b) ``relay.contextvm.org`` absent at runtime and in the sources."""

    def test_dead_host_not_in_runtime_set(self):
        self.assertNotIn(DEAD_HOST, kit.FAILOVER_RELAYS)
        self.assertNotIn(DEAD_HOST, kit.FAILOVER_RELAY_URLS)
        hosts = {u.split("://", 1)[1] for u in rf.failover_relays()}
        self.assertNotIn(DEAD_HOST, hosts)
        # even when injected as an extra relay, it is filtered out
        self.assertNotIn("wss://" + DEAD_HOST,
                         rf.failover_relays(["wss://" + DEAD_HOST]))

    def test_boundary_regex_matches_dead_host_only_on_a_boundary(self):
        self.assertTrue(kit.source_contains_dead_host("wss://relay.contextvm.org"))
        self.assertTrue(kit.source_contains_dead_host('"relay.contextvm.org"'))
        # the legitimate relay and its neighbours must NOT match
        for legit in (
            "wss://relay2.contextvm.org",
            "wss://relay.contextvm.org.evil.example",
            "wss://xrelay.contextvm.org",
            "wss://not-relay.contextvm.org",
        ):
            self.assertFalse(kit.source_contains_dead_host(legit), legit)

    def test_publish_path_sources_have_no_active_dead_host(self):
        offenders = []
        for name in PUBLISH_PATH:
            path = os.path.join(_TOOLS_DIR, name)
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, 1):
                    if not kit.source_contains_dead_host(line):
                        continue
                    if "dead" in line.lower():
                        continue  # a DEAD-relay declaration is allowed
                    offenders.append(
                        "{}:{}: {}".format(name, lineno, line.strip()))
        self.assertEqual(offenders, [], "dead host outside a DEAD declaration")


class TestFakeRelayTransport(unittest.TestCase):
    """(c) the importable double and its three named behaviours."""

    def test_accept_returns_nip01_ok_true(self):
        transport = kit.FakeRelayTransport()
        out = asyncio.run(transport.send("wss://nos.lol", {"id": "e1"}))
        self.assertEqual(out, ["OK", "e1", True, ""])
        self.assertEqual(transport.calls, [("wss://nos.lol", "e1")])

    def test_blocked_returns_nip01_ok_false(self):
        transport = kit.FakeRelayTransport({"wss://nos.lol": kit.BLOCKED})
        out = asyncio.run(transport.send("wss://nos.lol", {"id": "e2"}))
        self.assertEqual(out[0], "OK")
        self.assertIs(out[2], False)
        self.assertTrue(out[3].startswith("blocked:"))

    def test_timeout_never_responds_until_cancelled(self):
        transport = kit.FakeRelayTransport({"wss://nos.lol": kit.TIMEOUT})
        with self.assertRaises(asyncio.TimeoutError):
            asyncio.run(asyncio.wait_for(
                transport.send("wss://nos.lol", {"id": "e3"}), timeout=0.02))

    def test_hard_error_raises_connection_refused(self):
        transport = kit.FakeRelayTransport({"wss://nos.lol": kit.HARD_ERROR})
        with self.assertRaises(ConnectionRefusedError):
            asyncio.run(transport.send("wss://nos.lol", {"id": "e4"}))

    def test_sync_twin_behaviours(self):
        transport = kit.SyncFakeRelayTransport({
            "wss://nos.lol": kit.HARD_ERROR,
            "wss://nostr.mom": kit.TIMEOUT,
        })
        self.assertEqual(transport.send("wss://relay.primal.net", {"id": "s1"}),
                         ["OK", "s1", True, ""])
        with self.assertRaises(ConnectionRefusedError):
            transport.send("wss://nos.lol", {"id": "s2"})
        with self.assertRaises(TimeoutError):
            transport.send("wss://nostr.mom", {"id": "s3"})


class TestSmokePublishersWithFakeTransport(unittest.TestCase):
    """End-to-end smoke: the double drives the real failover publisher."""

    def test_accept_only_succeeds_and_hits_every_relay(self):
        transport = kit.FakeRelayTransport()
        pub = rf.RelayFailoverPublisher(transport, timeout=0.05)
        result = asyncio.run(pub.publish(_armed_msg(), _SESSION))
        self.assertTrue(result.ok)
        self.assertEqual(len(result.accepted), 5)
        self.assertEqual({url for url, _ in transport.calls},
                         set(EXPECTED_URLS))

    def test_timeout_and_hard_error_do_not_abort_when_a_relay_accepts(self):
        transport = kit.FakeRelayTransport({
            "wss://relay.primal.net": kit.TIMEOUT,
            "wss://nos.lol": kit.HARD_ERROR,
        })
        pub = rf.RelayFailoverPublisher(transport, timeout=0.05)
        result = asyncio.run(pub.publish(_armed_msg(), _SESSION))
        self.assertTrue(result.ok)
        by_url = {o.url: o for o in result.outcomes}
        self.assertEqual(by_url["wss://relay.primal.net"].reason, "timeout")
        self.assertIn("connectionrefused",
                      by_url["wss://nos.lol"].reason.replace(" ", "").lower())
        self.assertEqual(len(result.accepted), 3)
        self.assertEqual(len(result.failed), 2)


if __name__ == "__main__":
    unittest.main()
