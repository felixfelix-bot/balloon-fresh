#!/usr/bin/env python3
"""test_nostr_giftwrap.py — NIP-59 gift-wrap envelope builder + leak guard.

Card: t_88b2e58f (e80-bench). Pins the acceptance criteria of the ARMED
gift-wrap layer:

  * outer event kind == 1059 (NIP-59 outer wrap)
  * outer `p` tag == the TX npub (hex), whatever form the caller passed
  * the ARMED payload is not visible in plaintext in any tag/content field
  * publishing ANY non-1059 kind raises the guard (kind 30315 plaintext
    tally is explicitly forbidden) — it is never silently downgraded

Runs WITHOUT ``nostr_sdk`` (absent from this CI image): a fake ``nostr_sdk``
module is injected into ``sys.modules`` for the duration of each test, so the
wrap *call shape* is pinned but no Rust bindings are required. The real round
trip lives in ``test_cvm_board_server.py`` (``TestGiftWrapRoundTrip``, skipped
when nostr_sdk is missing).

Run:  python3 -m pytest test_nostr_giftwrap.py -v
"""

from __future__ import annotations

import ast
import asyncio
import base64
import json
import os
import sys
import types
import unittest

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import nostr_giftwrap as gw  # noqa: E402

# A real bech32 vector, generated with `nak encode npub <hex>` and verified
# with an independent bech32 decoder. secp256k1 generator x-coordinate.
TX_HEX = "79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
TX_NPUB = "npub10xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqpkge6d"

# Stand-in for keymaterial.KeyMaterial: the builder derives the signer from
# the client secret, so tests inject a KeyMaterial-shaped object, never a raw
# signer (card t_4c98fbe7).
FAKE_KM = types.SimpleNamespace(
    client_secret="fake-client-secret",
    client_pubkey="ef" * 32,
    server_pubkey="cd" * 32,
    server_secret=None,
    relay_auth=None,
)

# Outer ciphertext stand-in: base64 of bytes(range(64)). Contains none of the
# payload fragments below, exactly like a NIP-44 sealed payload.
CIPHERTEXT = base64.b64encode(bytes(range(64))).decode()

# The task-1 ARMED interface object this layer transports (a plain Mapping).
ARMED_PAYLOAD = {
    "type": "ARMED",
    "session_id": "2608301440a3f",
    "stop": "stop-50m",
    "t_ready_utc": 1789000000,
    "preset_hash": "deadbeefcafe0001",
    "seq": 7,
    "created_at": 1788999990,
    "author": "aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899",
}

PAYLOAD_FRAGMENTS = ("2608301440a3f", "deadbeefcafe0001", "stop-50m", "ARMED",
                     "session_id", "preset_hash", "t_ready_utc")


# ---------------------------------------------------------------------------
# Fake nostr_sdk — mirrors the surface cvm_board_server.py calls
# ---------------------------------------------------------------------------

class FakeKind:
    """nostr_sdk Kind is a Rust enum wrapper; compare via as_u16()."""

    def __init__(self, value):
        self._value = int(value)

    def as_u16(self):
        return self._value

    def __int__(self):
        return self._value


class FakeTag:
    """Faithful ``nostr_sdk.Tag``: elements come out via ``.as_vec()``.

    The real Rust binding's ``Tag`` is NOT iterable — ``to_vec()`` yields
    ``Tag`` objects, and every element access goes through ``as_vec()`` (see
    ``cvm_board_server._extract_p_tag``). An earlier version of this fake had
    ``to_vec()`` return plain Python lists, which made the guard look green
    while ``event_view()`` raised ``TypeError`` on every real SDK event.
    """

    def __init__(self, values):
        self._values = [str(v) for v in values]

    def as_vec(self):
        return list(self._values)

    def __eq__(self, other):
        if isinstance(other, FakeTag):
            return self._values == other._values
        return NotImplemented

    def __repr__(self):
        return "FakeTag(%r)" % (self._values,)


class _Tags:
    """nostr_sdk TagList-like: ``.to_vec()`` → list of ``Tag`` objects."""

    def __init__(self, tags):
        self._tags = [list(t) for t in tags]

    def to_vec(self):
        return [FakeTag(t) for t in self._tags]


class FakeEvent:
    """Mimics nostr_sdk.Event: kind()/tags()/content()/as_json()."""

    def __init__(self, kind, tags, content, pubkey="", event_id="", sig="",
                 created_at=0):
        self._kind = int(kind)
        self._tags = [list(t) for t in tags]
        self._content = content
        self._pubkey = pubkey
        self._id = event_id
        self._sig = sig
        self._created_at = created_at

    def kind(self):
        return FakeKind(self._kind)

    def tags(self):
        return _Tags(self._tags)

    def content(self):
        return self._content

    def as_json(self):
        return json.dumps({
            "id": self._id, "pubkey": self._pubkey, "kind": self._kind,
            "tags": self._tags, "content": self._content,
            "created_at": self._created_at, "sig": self._sig,
        })


class FakeUnsignedEvent:
    """Mimics nostr_sdk.UnsignedEvent (from_json + content())."""

    def __init__(self, data):
        self.data = data

    @classmethod
    def from_json(cls, text):
        return cls(json.loads(text))

    def kind(self):
        return FakeKind(self.data["kind"])

    def content(self):
        return self.data["content"]

    def tags(self):
        return _Tags(self.data["tags"])

    def to_json(self):
        return json.dumps(self.data)


class FakePublicKey:
    """Strict: parse() only accepts 64-char hex, so the npub→hex conversion
    must have happened in nostr_giftwrap, not in the SDK."""

    def __init__(self, hex_value):
        self._hex = hex_value

    @classmethod
    def parse(cls, value):
        text = str(value)
        if len(text) != 64 or any(c not in "0123456789abcdef"
                                  for c in text.lower()):
            raise AssertionError(
                "FakePublicKey.parse expected 64-char hex, got %r" % (value,))
        return cls(text.lower())

    def to_hex(self):
        return self._hex


class FakeClient:
    """Minimal relay client: records send_event() calls."""

    def __init__(self):
        self.sent = []

    async def send_event(self, event):
        self.sent.append(event)


class _FakeSdk:
    """Install / remove the fake nostr_sdk module around a test."""

    def __init__(self):
        self.calls = []
        self.events = []

    def install(self):
        calls = self.calls
        events = self.events

        async def fake_gift_wrap(signer, recipient, unsigned_event):
            calls.append({"signer": signer, "recipient": recipient,
                          "unsigned_event": unsigned_event})
            event = FakeEvent(
                kind=1059,
                tags=[["p", recipient.to_hex()]],
                content=CIPHERTEXT,
                pubkey="ef" * 32,
                event_id="12" * 32,
            )
            events.append(event)
            return event

        class _FakeKeys:
            @staticmethod
            def parse(secret):
                return {"keys_secret": secret}

        class _FakeNostrSigner:
            @staticmethod
            def keys(keys):
                return {"signer_from": keys}

        mod = types.ModuleType("nostr_sdk")
        mod.UnsignedEvent = FakeUnsignedEvent
        mod.PublicKey = FakePublicKey
        mod.Keys = _FakeKeys
        mod.NostrSigner = _FakeNostrSigner
        mod.gift_wrap = fake_gift_wrap
        self._previous = sys.modules.get("nostr_sdk")
        sys.modules["nostr_sdk"] = mod

    def remove(self):
        if self._previous is None:
            sys.modules.pop("nostr_sdk", None)
        else:
            sys.modules["nostr_sdk"] = self._previous


class GiftWrapTestBase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # build_gift_wrap now caches the signed wrap per canonical session
        # fingerprint (idempotency, card t_c4c43d76); drop it so every test
        # observes its own fake-SDK call.
        gw.clear_wrap_cache()
        self.addCleanup(gw.clear_wrap_cache)
        self.sdk = _FakeSdk()
        self.sdk.install()
        self.addCleanup(self.sdk.remove)


# ---------------------------------------------------------------------------
# Acceptance: build a gift wrap and inspect the emitted event
# ---------------------------------------------------------------------------

class TestBuildGiftWrap(GiftWrapTestBase):

    async def test_outer_kind_is_1059(self):
        event = await gw.build_gift_wrap(ARMED_PAYLOAD, TX_NPUB, keys=FAKE_KM)
        self.assertEqual(gw.event_view(event)["kind"], 1059)
        self.assertEqual(gw.event_view(event)["kind"], gw.KIND_GIFT_WRAP)

    async def test_ptag_equals_tx_npub(self):
        event = await gw.build_gift_wrap(ARMED_PAYLOAD, TX_NPUB, keys=FAKE_KM)
        self.assertEqual(gw.assert_recipient_tag(event, TX_NPUB), TX_HEX)

    async def test_ptag_equals_tx_npub_when_input_already_hex(self):
        event = await gw.build_gift_wrap(ARMED_PAYLOAD, TX_HEX, keys=FAKE_KM)
        self.assertEqual(gw.assert_recipient_tag(event, TX_NPUB), TX_HEX)

    async def test_payload_not_visible_in_plaintext_anywhere(self):
        event = await gw.build_gift_wrap(ARMED_PAYLOAD, TX_NPUB, keys=FAKE_KM)
        self.assertTrue(gw.assert_no_plaintext_leak(event, ARMED_PAYLOAD))
        haystack = json.dumps(gw.event_view(event))
        for fragment in PAYLOAD_FRAGMENTS:
            self.assertNotIn(fragment, haystack,
                             "payload fragment %r leaked into outer event"
                             % fragment)
        self.assertNotIn(json.dumps(ARMED_PAYLOAD), haystack)

    async def test_inner_rumor_carries_armed_payload(self):
        inner = gw.build_inner_rumor(ARMED_PAYLOAD, TX_NPUB)
        self.assertEqual(inner["kind"], gw.INNER_KIND)
        self.assertEqual(inner["tags"], [["p", TX_HEX]])
        self.assertEqual(json.loads(inner["content"]), ARMED_PAYLOAD)

    async def test_wrap_receives_the_inner_rumor(self):
        await gw.build_gift_wrap(ARMED_PAYLOAD, TX_NPUB, keys=FAKE_KM)
        (call,) = self.sdk.calls
        ue = call["unsigned_event"]
        self.assertEqual(int(ue.kind()), gw.INNER_KIND)
        self.assertEqual(json.loads(ue.content()), ARMED_PAYLOAD)
        self.assertEqual([t.as_vec() for t in ue.tags().to_vec()],
                         [["p", TX_HEX]])

    async def test_signer_is_derived_from_keymaterial(self):
        await gw.build_gift_wrap(ARMED_PAYLOAD, TX_NPUB, keys=FAKE_KM)
        (call,) = self.sdk.calls
        self.assertEqual(call["signer"],
                         {"signer_from": {"keys_secret": FAKE_KM.client_secret}})


# ---------------------------------------------------------------------------
# Acceptance: the emission choke-point guard
# ---------------------------------------------------------------------------

class TestEmissionGuard(unittest.IsolatedAsyncioTestCase):

    async def test_publishing_kind_30315_raises(self):
        client = FakeClient()
        plaintext = FakeEvent(kind=30315, tags=[["p", TX_HEX]],
                              content=json.dumps(ARMED_PAYLOAD))
        with self.assertRaises(gw.PlaintextKindError) as ctx:
            await gw.publish_gift_wrap(client, plaintext)
        self.assertEqual(client.sent, [], "nothing may reach the relay")
        message = str(ctx.exception)
        self.assertIn("30315", message)
        self.assertIn("FORBIDDEN", message)
        self.assertIn("1059", message)

    async def test_publishing_any_other_kind_raises(self):
        for bad_kind in (1, 25910, 30023, 30315, 20000):
            with self.subTest(kind=bad_kind):
                client = FakeClient()
                with self.assertRaises(gw.PlaintextKindError):
                    await gw.publish_gift_wrap(
                        client, FakeEvent(kind=bad_kind, tags=[], content=""))
                self.assertEqual(client.sent, [])

    def test_guard_is_not_a_silent_downgrade(self):
        # PlaintextKindError must be an AssertionError subclass so an
        # assert-style guard and pytest.raises(AssertionError) both catch it.
        self.assertTrue(issubclass(gw.PlaintextKindError, AssertionError))

    async def test_publish_gift_wrap_sends_the_wrapped_event(self):
        client = FakeClient()
        good = FakeEvent(kind=1059, tags=[["p", TX_HEX]], content=CIPHERTEXT)
        await gw.publish_gift_wrap(client, good, tx_npub=TX_NPUB)
        self.assertEqual(client.sent, [good])

    async def test_publish_rejects_wrong_recipient(self):
        client = FakeClient()
        wrong = FakeEvent(kind=1059, tags=[["p", "aa" * 32]],
                          content=CIPHERTEXT)
        with self.assertRaises(gw.RecipientMismatchError):
            await gw.publish_gift_wrap(client, wrong, tx_npub=TX_NPUB)
        self.assertEqual(client.sent, [])

    async def test_publish_rejects_missing_ptag(self):
        client = FakeClient()
        no_tag = FakeEvent(kind=1059, tags=[], content=CIPHERTEXT)
        with self.assertRaises(gw.RecipientMismatchError):
            await gw.publish_gift_wrap(client, no_tag, tx_npub=TX_NPUB)
        self.assertEqual(client.sent, [])

    async def test_publish_rejects_plaintext_leak(self):
        client = FakeClient()
        leaky = FakeEvent(kind=1059, tags=[["p", TX_HEX]],
                          content=json.dumps(ARMED_PAYLOAD))
        with self.assertRaises(gw.PlaintextLeakError):
            await gw.publish_gift_wrap(client, leaky, payload=ARMED_PAYLOAD)
        self.assertEqual(client.sent, [])


# ---------------------------------------------------------------------------
# Failover-layer entry point
# ---------------------------------------------------------------------------

class TestPublishArmed(GiftWrapTestBase):

    async def test_publish_armed_builds_and_sends_exactly_one_event(self):
        client = FakeClient()
        event = await gw.publish_armed(ARMED_PAYLOAD, TX_NPUB, client, keys=FAKE_KM)
        self.assertEqual(len(client.sent), 1)
        self.assertIs(client.sent[0], event)
        self.assertEqual(gw.event_view(event)["kind"], 1059)

    async def test_publish_armed_refuses_non_mapping_payload(self):
        client = FakeClient()
        with self.assertRaises(TypeError):
            await gw.publish_armed("not-a-mapping", TX_NPUB, client, keys=FAKE_KM)
        self.assertEqual(client.sent, [])


# ---------------------------------------------------------------------------
# Real-SDK event shape (the fake above must stay faithful to it)
# ---------------------------------------------------------------------------

class TestRealSdkTagShape(unittest.TestCase):
    """``event_view`` must read REAL nostr_sdk events, whose ``tags()``
    returns a TagList of NON-iterable ``Tag`` objects (``.as_vec()`` only).

    Regression test for the real-SDK TypeError found by running the builder
    against nostr-sdk 0.44 in a venv: the guard layer could not normalize a
    genuine event, so ``build_gift_wrap`` raised TypeError instead of
    returning the checked 1059 wrap.
    """

    def test_faketag_is_not_iterable_like_the_real_binding(self):
        with self.assertRaises(TypeError):
            list(FakeTag(["p", TX_HEX]))
        with self.assertRaises(TypeError):
            iter(FakeTag(["p", TX_HEX]))

    def test_event_view_normalizes_tag_objects(self):
        event = FakeEvent(kind=1059, tags=[["p", TX_HEX], ["t", "cvm"]],
                          content=CIPHERTEXT)
        view = gw.event_view(event)
        self.assertEqual(view["kind"], 1059)
        self.assertEqual(view["tags"], [["p", TX_HEX], ["t", "cvm"]])
        self.assertEqual(view["content"], CIPHERTEXT)

    def test_guards_work_on_real_shaped_event(self):
        event = FakeEvent(kind=1059, tags=[["p", TX_HEX]],
                          content=CIPHERTEXT)
        gw.assert_gift_wrap_kind(event)
        self.assertEqual(gw.assert_recipient_tag(event, TX_NPUB), TX_HEX)
        self.assertTrue(gw.assert_no_plaintext_leak(event, ARMED_PAYLOAD))

    def test_publish_accepts_real_shaped_event(self):
        client = FakeClient()
        event = FakeEvent(kind=1059, tags=[["p", TX_HEX]],
                          content=CIPHERTEXT)
        asyncio.run(gw.publish_gift_wrap(client, event, payload=ARMED_PAYLOAD,
                                         tx_npub=TX_NPUB))
        self.assertEqual(client.sent, [event])

    def test_mapping_events_with_tag_objects_are_normalized(self):
        # A dict-shaped event whose tags were already materialized as Tag
        # objects (e.g. from ``event.as_json()`` round-trips through a
        # TagList) must not crash the guard either.
        event = {"kind": 1059, "tags": [FakeTag(["p", TX_HEX])],
                 "content": CIPHERTEXT}
        self.assertEqual(gw.event_view(event)["tags"], [["p", TX_HEX]])


# ---------------------------------------------------------------------------
# npub → hex (pure stdlib; the module must not need nostr_sdk for this)
# ---------------------------------------------------------------------------

class TestNpubToHex(unittest.TestCase):

    def test_known_vector(self):
        self.assertEqual(gw.npub_to_hex(TX_NPUB), TX_HEX)

    def test_hex_passthrough_is_lowercased(self):
        self.assertEqual(gw.npub_to_hex(TX_HEX.upper()), TX_HEX)

    def test_rejects_garbage(self):
        for bad in ("", "npub1", "npub1qqqqqqqq", TX_HEX + "00", "x" * 64,
                    "npub10xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqpkge6e"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    gw.npub_to_hex(bad)

    def test_rejects_non_string(self):
        with self.assertRaises(ValueError):
            gw.npub_to_hex(None)


# ---------------------------------------------------------------------------
# Structural pins: ONE wrap primitive, ONE emission choke-point
# ---------------------------------------------------------------------------

class TestSinglePathPins(unittest.TestCase):

    SOURCE = os.path.join(_TOOLS_DIR, "nostr_giftwrap.py")

    def _tree(self):
        with open(self.SOURCE, encoding="utf-8") as fh:
            return ast.parse(fh.read())

    def _attr_calls(self, attr):
        return [n for n in ast.walk(self._tree())
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr == attr]

    def test_exactly_one_gift_wrap_call(self):
        self.assertEqual(len(self._attr_calls("gift_wrap")), 1,
                         "the NIP-59 wrap primitive must have one call site")

    def test_exactly_one_send_event_call(self):
        self.assertEqual(len(self._attr_calls("send_event")), 1,
                         "emission must have a single choke-point")

    def test_no_local_gift_wrap_wrapper(self):
        for node in ast.walk(self._tree()):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.assertNotIn(node.name, ("gift_wrap", "from_gift_wrap"))


if __name__ == "__main__":
    unittest.main()
