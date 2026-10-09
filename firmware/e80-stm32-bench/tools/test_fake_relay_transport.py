#!/usr/bin/env python3
"""test_fake_relay_transport.py — contract pins for the fake relay transport double.

Card t_69c76243. Pins the EXACT contract of the importable, zero-network fake
relay transport double in :mod:`relay_testkit`:

  * the four behaviours ``ACCEPT`` / ``TIMEOUT`` / ``HARD_ERROR_RAISE`` /
    ``HARD_ERROR_REJECT`` (the two hard-error flavours kept DISTINCT);
  * ``ACCEPT`` returns the NIP-01 frame ``["OK", <id>, true, ""]`` where ``<id>``
    is the 64-char lowercase hex id parsed from the event actually published;
  * ``TIMEOUT`` hangs forever, is cancelled cleanly, and leaks no pending tasks;
  * ``HARD_ERROR_RAISE`` raises ``ConnectionRefusedError``;
  * ``HARD_ERROR_REJECT`` returns ``["OK", <id>, false, "blocked: ..."]``;
  * the ordered call log plus its reset/clear method;
  * the double really is a drop-in for ``RelayFailoverPublisher``;
  * the module imports/calls NO real socket/DNS API.

Run:  python3 -m pytest firmware/e80-stm32-bench/tools/test_fake_relay_transport.py -v
"""

from __future__ import annotations

import ast
import asyncio
import os
import sys
import unittest

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import relay_testkit as kit  # noqa: E402
import relay_failover as rf  # noqa: E402

RELAY = "wss://nos.lol"
OTHER = "wss://nostr.mom"
#: A realistic 64-char lowercase hex event id (as produced by NIP-01).  The
#: double must ECHO the id it is handed, never a hardcoded constant.
EVENT_ID = "f0e1d2c3b4a5968778695a4b3c2d1e0f" * 2
EVENT = {"id": EVENT_ID, "kind": 1059}

_SESSION = {
    "session_id": "2608301320a3f",
    "stop": "50m",
    "t_ready_utc": 1788096000,
    "preset_hash": "abc123",
    "seq": 1,
    "created_at": 1788096000,
}
_MSG = {
    "type": "ARMED",
    "session_id": _SESSION["session_id"],
    "stop": _SESSION["stop"],
    "t_ready_utc": _SESSION["t_ready_utc"],
    "preset_hash": _SESSION["preset_hash"],
    "seq": _SESSION["seq"],
    "created_at": _SESSION["t_ready_utc"],
}

#: Documentation tokens that must legitimately appear in the module docstring:
#: the no-network guarantee NAMES the APIs it refuses to use.  The AST scan
#: below ignores strings so that naming them in prose is not a violation.
_BANNED_IMPORT_ROOTS = {"socket", "ssl", "aiohttp", "httpx", "urllib3",
                        "urllib", "http", "requests", "dns", "anyio"}
_BANNED_CALL_NAMES = {"open_connection", "getaddrinfo", "create_connection",
                      "gethostbyname"}


class TestBehaviourNames(unittest.TestCase):
    def test_four_behaviour_names_are_exported_and_distinct(self):
        names = {
            "ACCEPT": kit.ACCEPT,
            "TIMEOUT": kit.TIMEOUT,
            "HARD_ERROR_RAISE": kit.HARD_ERROR_RAISE,
            "HARD_ERROR_REJECT": kit.HARD_ERROR_REJECT,
        }
        self.assertEqual(len(set(names.values())), 4, names)

    def test_back_compat_aliases(self):
        # HARD_ERROR was the raise flavour; BLOCKED the reject flavour.
        self.assertEqual(kit.HARD_ERROR, kit.HARD_ERROR_RAISE)
        self.assertEqual(kit.BLOCKED, kit.HARD_ERROR_REJECT)


class TestAccept(unittest.TestCase):
    def test_accept_returns_nip01_ok_with_the_real_event_id(self):
        t = kit.FakeRelayTransport()
        out = asyncio.run(t.send(RELAY, EVENT))
        self.assertEqual(out, ["OK", EVENT_ID, True, ""])
        self.assertEqual(len(out[1]), 64)
        self.assertEqual(out[1], EVENT_ID.lower())
        self.assertIs(out[2], True)

    def test_accept_default_is_accept_for_unmapped_relays(self):
        t = kit.FakeRelayTransport({OTHER: kit.HARD_ERROR_REJECT})
        self.assertEqual(asyncio.run(t.send(RELAY, EVENT)),
                         ["OK", EVENT_ID, True, ""])


class TestHardErrorRaise(unittest.TestCase):
    def test_raise_flavour_raises_connection_refused(self):
        t = kit.FakeRelayTransport({RELAY: kit.HARD_ERROR_RAISE})
        with self.assertRaises(ConnectionRefusedError):
            asyncio.run(t.send(RELAY, EVENT))
        self.assertTrue(issubclass(ConnectionRefusedError, OSError))


class TestHardErrorReject(unittest.TestCase):
    def test_reject_flavour_returns_blocked_envelope(self):
        t = kit.FakeRelayTransport({RELAY: kit.HARD_ERROR_REJECT})
        out = asyncio.run(t.send(RELAY, EVENT))
        self.assertEqual(out[0], "OK")
        self.assertEqual(out[1], EVENT_ID)
        self.assertIs(out[2], False)
        self.assertTrue(out[3].startswith("blocked: "), out[3])


class TestTimeout(unittest.TestCase):
    def test_timeout_hangs_then_cancels_cleanly_with_no_pending_tasks(self):
        async def probe():
            t = kit.FakeRelayTransport({RELAY: kit.TIMEOUT})
            task = asyncio.create_task(t.send(RELAY, EVENT))
            await asyncio.sleep(0)  # let the send start and block
            self.assertFalse(task.done(), "TIMEOUT must not return on its own")
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            await asyncio.sleep(0)  # let cancellation settle
            current = asyncio.current_task()
            pending = [x for x in asyncio.all_tasks()
                       if x is not current and not x.done()]
            self.assertEqual(pending, [], "leaked/pending tasks: %r" % pending)
            # the attempt is still logged even though it never answered
            self.assertEqual(t.calls, [(RELAY, EVENT_ID)])

        asyncio.run(probe())


class TestCallLog(unittest.TestCase):
    def test_calls_are_ordered_and_reset_clears_them(self):
        t = kit.FakeRelayTransport({OTHER: kit.HARD_ERROR_REJECT})
        asyncio.run(t.send(RELAY, {"id": "a" * 64}))
        asyncio.run(t.send(OTHER, {"id": "b" * 64}))
        self.assertEqual(t.calls, [(RELAY, "a" * 64), (OTHER, "b" * 64)])
        self.assertEqual(len(t.attempts), 2)
        t.reset()
        self.assertEqual(t.calls, [])
        self.assertEqual(t.attempts, [])
        t.clear()  # idempotent alias
        self.assertEqual(t.calls, [])

    def test_sync_twin_shares_the_contract(self):
        t = kit.SyncFakeRelayTransport({RELAY: kit.HARD_ERROR_REJECT})
        out = t.send(RELAY, EVENT)
        self.assertEqual(out, ["OK", EVENT_ID, False,
                               out[3]])
        self.assertTrue(out[3].startswith("blocked: "))
        self.assertEqual(t.calls, [(RELAY, EVENT_ID)])
        t.reset()
        self.assertEqual(t.calls, [])


class TestSeamNuance(unittest.TestCase):
    """The double returns the NIP-01 frame; the *publisher* seam is raise-based.

    ``RelayFailoverPublisher._send_one`` ignores the returned frame and treats
    any non-raising return as accepted, so the way to make the publisher record
    a refusal is to *raise* ``RelayRejected`` (which the sibling
    ``test_relay_failover_publisher.py`` transport does).  The envelope form is
    what the double must produce (card contract); this test pins BOTH so the
    distinction cannot be lost.
    """

    def test_reject_envelope_is_returned_by_the_double(self):
        t = kit.FakeRelayTransport({RELAY: kit.HARD_ERROR_REJECT})
        frame = asyncio.run(t.send(RELAY, EVENT))
        self.assertEqual(frame, ["OK", EVENT_ID, False,
                                 "blocked: relay policy for " + RELAY])

    def test_publisher_records_a_raised_relay_rejected_as_failed(self):
        class _RaisingTransport:
            def __init__(self):
                self.calls = []

            async def send(self, url, event):
                self.calls.append((url, event["id"]))
                if url == RELAY:
                    raise rf.RelayRejected("blocked: policy")
                return ["OK", event["id"], True, ""]

        pub = rf.RelayFailoverPublisher(_RaisingTransport(), timeout=0.05)
        result = asyncio.run(pub.publish(_MSG, _SESSION))
        self.assertTrue(result.ok)
        by_url = {o.url: o for o in result.outcomes}
        self.assertFalse(by_url[RELAY].accepted)
        self.assertIn("rejected", by_url[RELAY].reason.lower())


class TestDropInForPublisher(unittest.TestCase):
    def test_double_drives_the_real_failover_publisher(self):
        t = kit.FakeRelayTransport({
            "wss://relay.primal.net": kit.TIMEOUT,
            "wss://nos.lol": kit.HARD_ERROR_RAISE,
            "wss://nostr.mom": kit.HARD_ERROR_REJECT,
        })
        pub = rf.RelayFailoverPublisher(t, timeout=0.05)
        result = asyncio.run(pub.publish(_MSG, _SESSION))
        self.assertTrue(result.ok)  # the ACCEPT relays carry the fan-out
        by_url = {o.url: o for o in result.outcomes}
        self.assertEqual(by_url["wss://relay.primal.net"].reason, "timeout")
        self.assertIn("connectionrefused",
                      by_url["wss://nos.lol"].reason.replace(" ", "").lower())
        # NOTE: HARD_ERROR_REJECT returns a frame; the publisher seam is
        # raise-based, so it counts that relay as accepted (see
        # TestSeamNuance).  Using TIMEOUT + HARD_ERROR_RAISE leaves 3 accepts.
        self.assertEqual(len(result.accepted), 3)
        self.assertEqual(len(result.failed), 2)


class TestNoNetworkGuarantee(unittest.TestCase):
    def test_module_imports_and_calls_no_real_socket_api(self):
        path = os.path.join(_TOOLS_DIR, "relay_testkit.py")
        with open(path, "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in _BANNED_IMPORT_ROOTS:
                        bad.append("import %s" % alias.name)
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                if root in _BANNED_IMPORT_ROOTS:
                    bad.append("from %s import ..." % node.module)
            elif isinstance(node, ast.Call):
                name = getattr(node.func, "attr", None) or getattr(
                    node.func, "id", None)
                if name in _BANNED_CALL_NAMES:
                    bad.append("call %s()" % name)
        self.assertEqual(bad, [], "banned socket/DNS API in module: %r" % bad)


if __name__ == "__main__":
    unittest.main()
