#!/usr/bin/env python3
"""test_giftwrap_determinism.py — deterministic + idempotent gift-wrap events.

Card t_c4c43d76 (e80-bench). Pins the determinism/idempotency contract of
``tools/nostr_giftwrap.py`` on top of the choke-point built by t_88b2e58f:

  * the derivation path (canonical session bytes, session fingerprint, derived
    ephemeral secret, frozen ``created_at``) is a PURE function of the session
    fields — no randomness, no wall clock;
  * the derived ephemeral secret is a valid secp256k1 scalar;
  * the signed kind-1059 event is cached on the canonical session fingerprint, so
    repeated calls with the same fields return the SAME event object/id without
    re-signing;
  * different session fields produce a different event id;
  * the emitted event still never carries the plaintext payload.

Hermetic: the real ``nostr_sdk`` bindings are NOT required. A fake SDK whose
``gift_wrap`` is deliberately NONDETERMINISTIC (fresh id, pubkey and
``created_at`` on every call — exactly like nostr-sdk 0.44, verified) is
injected, so the tests prove the *cache*, not a deterministic constructor.

Run:  python3 -m pytest test_giftwrap_determinism.py -v
"""

from __future__ import annotations

import ast
import base64
import hashlib
import json
import os
import sys
import types
import unittest

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import nostr_giftwrap as gw  # noqa: E402

SOURCE = os.path.join(_TOOLS_DIR, "nostr_giftwrap.py")

# Real bech32 vector (verifier x-coordinate); see test_nostr_giftwrap.py.
TX_HEX = "79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
TX_NPUB = "npub10xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqpkge6d"
# A second recipient, to prove the fingerprint is scoped by recipient.
OTHER_HEX = "aa" * 32

CIPHERTEXT = base64.b64encode(bytes(range(64))).decode()

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
# Fake nostr_sdk — deliberately nondeterministic (mirrors the real binding)
# ---------------------------------------------------------------------------

class FakeKind:
    def __init__(self, value):
        self._value = int(value)

    def as_u16(self):
        return self._value

    def __int__(self):
        return self._value


class FakeTag:
    """Real ``nostr_sdk.Tag`` is not iterable; elements come out via as_vec()."""

    def __init__(self, values):
        self._values = [str(v) for v in values]

    def as_vec(self):
        return list(self._values)


class _Tags:
    def __init__(self, tags):
        self._tags = [list(t) for t in tags]

    def to_vec(self):
        return [FakeTag(t) for t in self._tags]


class FakeEvent:
    """Mimics nostr_sdk.Event."""

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
        }, sort_keys=True)

    def __repr__(self):
        return "FakeEvent(id=%r)" % (self._id[:12],)


class FakeUnsignedEvent:
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
        return json.dumps(self.data, sort_keys=True)


class FakePublicKey:
    def __init__(self, hex_value):
        self._hex = hex_value

    @classmethod
    def parse(cls, value):
        text = str(value)
        if len(text) != 64 or any(c not in "0123456789abcdef"
                                  for c in text.lower()):
            raise AssertionError("expected 64-char hex, got %r" % (value,))
        return cls(text.lower())

    def to_hex(self):
        return self._hex


class FakeClient:
    def __init__(self):
        self.sent = []

    async def send_event(self, event):
        self.sent.append(event)


class _NondeterministicSdk:
    """Injected fake SDK whose gift_wrap varies on every call.

    Emulates the real binding: nostr-sdk 0.44 draws a fresh outer ephemeral key
    and stamps ``created_at`` from the clock on every ``gift_wrap`` call, so two
    calls with identical inputs yield different ids. Any determinism the tests
    observe therefore comes from nostr_giftwrap's cache, not from this fake.
    """

    def __init__(self):
        self.calls = []

    def install(self):
        calls = self.calls

        async def _fake_gift_wrap(signer, recipient, unsigned_event):
            index = len(calls)
            calls.append({"signer": signer, "recipient": recipient,
                          "unsigned_event": unsigned_event})
            seed = "%s|%s|%d" % (unsigned_event.to_json(),
                                 recipient.to_hex(), index)
            event_id = hashlib.sha256(seed.encode()).hexdigest()
            event = FakeEvent(
                kind=1059,
                tags=[["p", recipient.to_hex()]],
                content=CIPHERTEXT,
                pubkey=hashlib.sha256(("pk%d" % index).encode()).hexdigest(),
                event_id=event_id,
                sig="00" * 64,
                created_at=1_800_000_000 + index,
            )
            return event

        mod = types.ModuleType("nostr_sdk")
        mod.UnsignedEvent = FakeUnsignedEvent
        mod.PublicKey = FakePublicKey
        mod.gift_wrap = _fake_gift_wrap
        self._previous = sys.modules.get("nostr_sdk")
        sys.modules["nostr_sdk"] = mod

    def remove(self):
        if self._previous is None:
            sys.modules.pop("nostr_sdk", None)
        else:
            sys.modules["nostr_sdk"] = self._previous


class DeterminismTestBase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        gw.clear_wrap_cache()
        self.addCleanup(gw.clear_wrap_cache)
        self.sdk = _NondeterministicSdk()
        self.sdk.install()
        self.addCleanup(self.sdk.remove)


# ---------------------------------------------------------------------------
# Requirement 5(a): same session fields -> identical event id / serialization
# ---------------------------------------------------------------------------

class TestIdempotentBuild(DeterminismTestBase):

    async def test_same_session_fields_yield_identical_event_id(self):
        first = await gw.build_gift_wrap(ARMED_PAYLOAD, TX_NPUB, "signer")
        second = await gw.build_gift_wrap(ARMED_PAYLOAD, TX_NPUB, "signer")
        j1 = json.loads(first.as_json())
        j2 = json.loads(second.as_json())
        self.assertEqual(j1["id"], j2["id"])
        self.assertEqual(first.as_json(), second.as_json())

    async def test_same_session_fields_return_the_same_object(self):
        first = await gw.build_gift_wrap(ARMED_PAYLOAD, TX_NPUB, "signer")
        second = await gw.build_gift_wrap(ARMED_PAYLOAD, TX_NPUB, "signer")
        self.assertIs(first, second)

    async def test_repeat_does_not_re_sign(self):
        await gw.build_gift_wrap(ARMED_PAYLOAD, TX_NPUB, "signer")
        await gw.build_gift_wrap(ARMED_PAYLOAD, TX_NPUB, "signer")
        self.assertEqual(len(self.sdk.calls), 1,
                         "the cached event must not be re-signed")

    async def test_dict_insertion_order_does_not_change_the_event(self):
        reordered = {k: ARMED_PAYLOAD[k] for k in reversed(list(ARMED_PAYLOAD))}
        a = await gw.build_gift_wrap(ARMED_PAYLOAD, TX_NPUB, "signer")
        b = await gw.build_gift_wrap(reordered, TX_NPUB, "signer")
        self.assertEqual(a.as_json(), b.as_json())
        self.assertEqual(len(self.sdk.calls), 1)

    async def test_clear_wrap_cache_forces_a_rebuild(self):
        first = await gw.build_gift_wrap(ARMED_PAYLOAD, TX_NPUB, "signer")
        self.assertEqual(gw.wrap_cache_size(), 1)
        self.assertEqual(gw.clear_wrap_cache(), 1)
        self.assertEqual(gw.wrap_cache_size(), 0)
        second = await gw.build_gift_wrap(ARMED_PAYLOAD, TX_NPUB, "signer")
        self.assertEqual(len(self.sdk.calls), 2)
        self.assertIsNot(first, second)

    async def test_constructor_alone_is_nondeterministic(self):
        """Without the cache the (real-shaped) constructor drifts — this is the
        reason the cache exists."""
        first = await gw.build_gift_wrap(ARMED_PAYLOAD, TX_NPUB, "signer")
        gw.clear_wrap_cache()
        second = await gw.build_gift_wrap(ARMED_PAYLOAD, TX_NPUB, "signer")
        self.assertNotEqual(json.loads(first.as_json())["id"],
                            json.loads(second.as_json())["id"])


# ---------------------------------------------------------------------------
# Requirement 5(b): different session fields -> different event id
# ---------------------------------------------------------------------------

class TestDistinctSessions(DeterminismTestBase):

    async def test_different_session_fields_yield_different_event_id(self):
        a = await gw.build_gift_wrap(ARMED_PAYLOAD, TX_NPUB, "signer")
        b = await gw.build_gift_wrap(
            dict(ARMED_PAYLOAD, session_id="2608301440a40", seq=8),
            TX_NPUB, "signer")
        self.assertNotEqual(json.loads(a.as_json())["id"],
                            json.loads(b.as_json())["id"])
        self.assertEqual(len(self.sdk.calls), 2)

    async def test_different_recipient_yields_different_event_id(self):
        a = await gw.build_gift_wrap(ARMED_PAYLOAD, TX_NPUB, "signer")
        b = await gw.build_gift_wrap(ARMED_PAYLOAD, OTHER_HEX, "signer")
        self.assertNotEqual(json.loads(a.as_json())["id"],
                            json.loads(b.as_json())["id"])

    async def test_fingerprint_is_scoped_by_recipient_and_author(self):
        base = gw.session_fingerprint(ARMED_PAYLOAD, TX_NPUB, author="aa" * 32)
        self.assertNotEqual(
            base, gw.session_fingerprint(ARMED_PAYLOAD, OTHER_HEX, author="aa" * 32))
        self.assertNotEqual(
            base, gw.session_fingerprint(ARMED_PAYLOAD, TX_NPUB, author="bb" * 32))
        self.assertEqual(
            base, gw.session_fingerprint(ARMED_PAYLOAD, TX_NPUB, author="aa" * 32))


# ---------------------------------------------------------------------------
# Requirement 5(c): the emitted event is the choke-point output, no plaintext
# ---------------------------------------------------------------------------

class TestChokePointOutput(DeterminismTestBase):

    async def test_emitted_event_carries_no_plaintext_fragment(self):
        event = await gw.build_gift_wrap(ARMED_PAYLOAD, TX_NPUB, "signer")
        view = gw.event_view(event)
        haystack = json.dumps(view)
        for fragment in PAYLOAD_FRAGMENTS:
            self.assertNotIn(fragment, haystack,
                             "payload fragment %r leaked into the outer event"
                             % fragment)
        self.assertNotIn(json.dumps(ARMED_PAYLOAD), haystack)
        self.assertTrue(gw.assert_no_plaintext_leak(event, ARMED_PAYLOAD))

    async def test_emitted_event_is_kind_1059_for_the_tx_npub(self):
        event = await gw.build_gift_wrap(ARMED_PAYLOAD, TX_NPUB, "signer")
        self.assertEqual(gw.event_view(event)["kind"], gw.KIND_GIFT_WRAP)
        self.assertEqual(gw.assert_recipient_tag(event, TX_NPUB), TX_HEX)

    def test_module_has_exactly_one_wrap_and_one_send_call(self):
        with open(SOURCE, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        wrap_calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                      and isinstance(n.func, ast.Attribute)
                      and n.func.attr == "gift_wrap"]
        send_calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                      and isinstance(n.func, ast.Attribute)
                      and n.func.attr == "send_event"]
        self.assertEqual(len(wrap_calls), 1,
                         "the NIP-59 wrap primitive must have one call site")
        self.assertEqual(len(send_calls), 1,
                         "emission must stay a single choke-point")

    async def test_publish_armed_repeat_publishes_the_identical_event(self):
        client = FakeClient()
        first = await gw.publish_armed(ARMED_PAYLOAD, TX_NPUB, "signer", client)
        second = await gw.publish_armed(ARMED_PAYLOAD, TX_NPUB, "signer", client)
        self.assertEqual(len(self.sdk.calls), 1)
        self.assertIs(first, second)
        self.assertEqual(2, len(client.sent))
        self.assertEqual(json.loads(client.sent[0].as_json())["id"],
                         json.loads(client.sent[1].as_json())["id"])


# ---------------------------------------------------------------------------
# Requirement 2: deterministic, randomness-free ephemeral key derivation
# ---------------------------------------------------------------------------

class TestDeterministicDerivation(unittest.TestCase):

    def test_ephemeral_secret_key_is_deterministic(self):
        a = gw.derive_ephemeral_secret_key(ARMED_PAYLOAD, TX_NPUB)
        b = gw.derive_ephemeral_secret_key(ARMED_PAYLOAD, TX_NPUB)
        self.assertEqual(a, b)

    def test_ephemeral_secret_key_changes_with_the_session(self):
        a = gw.derive_ephemeral_secret_key(ARMED_PAYLOAD, TX_NPUB)
        b = gw.derive_ephemeral_secret_key(
            dict(ARMED_PAYLOAD, session_id="2608301440a41"), TX_NPUB)
        self.assertNotEqual(a, b)

    def test_ephemeral_secret_key_is_a_valid_secp256k1_scalar(self):
        key = gw.derive_ephemeral_secret_key(ARMED_PAYLOAD, TX_NPUB)
        self.assertEqual(len(key), 64)
        self.assertEqual(key, key.lower())
        scalar = int(key, 16)
        self.assertGreater(scalar, 0)
        self.assertLess(scalar, gw.SECP256K1_ORDER)

    def test_hkdf_sha256_matches_rfc5869_test_case_1(self):
        # RFC 5869, Appendix A.1 (SHA-256, L=42).
        ikm = b"\x0b" * 22
        salt = bytes(range(0x00, 0x0d))
        info = bytes(range(0xf0, 0xfa))
        okm = gw._hkdf_sha256(ikm, salt=salt, info=info, length=42)
        self.assertEqual(
            okm.hex(),
            "3cb25f25faacd57a90434f64d0362f2a"
            "2d2d0a90cf1a5a4c5db02d56ecc4c5bf"
            "34007208d5b887185865")

    def test_session_fingerprint_is_stable_and_hex(self):
        fp = gw.session_fingerprint(ARMED_PAYLOAD, TX_NPUB)
        self.assertEqual(len(fp), 64)
        self.assertEqual(fp, gw.session_fingerprint(ARMED_PAYLOAD, TX_NPUB))
        self.assertEqual(fp, gw.session_fingerprint(
            {k: ARMED_PAYLOAD[k] for k in reversed(list(ARMED_PAYLOAD))},
            TX_NPUB))

    def test_canonical_bytes_are_pure(self):
        a = gw.canonical_session_bytes(ARMED_PAYLOAD, TX_NPUB)
        b = gw.canonical_session_bytes(ARMED_PAYLOAD, TX_NPUB)
        self.assertEqual(a, b)
        self.assertIsInstance(a, bytes)

    def test_canonical_bytes_reject_non_json_payload(self):
        with self.assertRaises(TypeError):
            gw.canonical_session_bytes({"bad": object()}, TX_NPUB)

    def test_created_at_is_session_derived_not_wall_clock(self):
        self.assertEqual(
            gw.derive_created_at(ARMED_PAYLOAD, TX_NPUB),
            ARMED_PAYLOAD["created_at"])
        # t_ready_utc is the next preference when created_at is absent.
        self.assertEqual(
            gw.derive_created_at({"t_ready_utc": 1789000000, "seq": 1, "session_id": "s"},
                                 TX_NPUB),
            1789000000)
        # No timestamp anywhere -> still deterministic (never the clock).
        bare = {"session_id": "s", "seq": 1}
        self.assertEqual(gw.derive_created_at(bare, TX_NPUB),
                         gw.derive_created_at(bare, TX_NPUB))

    def test_inner_rumor_created_at_is_frozen(self):
        a = gw.build_inner_rumor(ARMED_PAYLOAD, TX_NPUB)
        b = gw.build_inner_rumor(ARMED_PAYLOAD, TX_NPUB)
        self.assertEqual(a["created_at"], b["created_at"])
        self.assertEqual(a["created_at"], ARMED_PAYLOAD["created_at"])

    def test_no_randomness_or_wall_clock_in_the_derivation_path(self):
        with open(SOURCE, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())

        banned_modules = {"random", "secrets", "time"}
        banned_calls = {"urandom", "random", "randint", "randbytes", "token_bytes",
                        "time"}

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(alias.name.split(".")[0], banned_modules,
                                     "banned import %s" % alias.name)
            elif isinstance(node, ast.ImportFrom):
                self.assertNotIn((node.module or "").split(".")[0], banned_modules,
                                 "banned import-from %s" % node.module)
            elif isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else (
                    func.id if isinstance(func, ast.Name) else "")
                self.assertNotIn(name, banned_calls,
                                 "banned call %s() on the derivation path" % name)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in (
                    "session_fingerprint", "derive_ephemeral_secret_key",
                    "derive_created_at", "canonical_session_bytes",
                    "_canonical_payload", "_hkdf_sha256", "_wrap_cache_key"):
                for inner in ast.walk(node):
                    if isinstance(inner, ast.Call):
                        func = inner.func
                        name = func.attr if isinstance(func, ast.Attribute) else (
                            func.id if isinstance(func, ast.Name) else "")
                        self.assertNotIn(
                            name, banned_calls,
                            "%s calls banned %s()" % (node.name, name))
                    elif isinstance(inner, ast.Attribute):
                        self.assertNotIn(
                            inner.attr, banned_calls,
                            "%s references banned attribute .%s"
                            % (node.name, inner.attr))


if __name__ == "__main__":
    unittest.main()
