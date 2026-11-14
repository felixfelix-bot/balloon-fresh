#!/usr/bin/env python3
"""test_verdict_transport.py — Gate1 contract suite for ``verdict_transport.py``.

Task: author the Gate1 tests for ``firmware/e80-stm32-bench/tools/verdict_transport.py``
BEFORE the implementation lands, pinning the interface fixed by the task spec::

    publish_verdict(payload_serializer, *, transport=None, env=None,
                    created_at=None, log=None) -> PublishResult

The suite is authored RED-first: ``verdict_transport`` does not exist yet, so
pytest collects this file as a ``ModuleNotFoundError`` — the family's
"red first: file absent" evidence state. It is written to pass UNCHANGED once
the module implements the contract pinned here. Nothing in this file is a stub
of the implementation — every network and signing path is replaced by an
in-process double.

Interface the module must expose (this file is the spec for it)
==============================================================

Constants
    ``KIND_GIFT_WRAP == 1059``      NIP-59 outer wrap kind
    ``INNER_KIND == 25910``         CVM JSON-RPC envelope kind (inner rumor)
    ``FAILOVER_RELAYS``             EXACTLY the five BARE hostnames, in order
    ``FAILOVER_RELAY_URLS``         ``["wss://" + h for h in FAILOVER_RELAYS]``
    ``DEAD_RELAYS``                 must include ``wss://relay.contextvm.org``
    ``ENV_CLIENT_NSEC`` / ``ENV_CLIENT_HEX``
    ``ENV_SERVER_NSEC`` / ``ENV_SERVER_HEX`` / ``ENV_TX_NPUB``

Functions
    ``publish_verdict(payload_serializer, transport=None, env=None,
                      created_at=None, log=None)``
        * ``payload_serializer`` — zero-argument callable returning the verdict
          content (a JSON string or a Mapping) that is to travel INSIDE the
          gift wrap. Called exactly once per publish.
        * ``transport`` — the ONLY wire seam: any object with
          ``async send_event(event)``. When ``None``, the module must build the
          relay fan-out from ``relay_transport_factory(urls, env=None)`` and
          pass it the resolved ``FAILOVER_RELAY_URLS``.
        * ``env`` — a Mapping standing in for ``os.environ`` (keys are read from
          the ENVIRONMENT ONLY; never from a parameter).
        * returns an object carrying at least ``.event`` (the outbound
          gift-wrapped event) and ``.relay_results`` (Mapping host -> status).
    ``relay_transport_factory(urls, env=None)``
        the module-level seam ``publish_verdict`` calls when ``transport`` is
        ``None``; tests monkeypatch it to observe the relay set.
    ``assert_keys_differ(...)`` / ``load_and_check_keys(env=None)``
        env-only key loading; ``KeyCollisionError`` when client == server.

Lazy SDK import (mandatory): ``nostr_sdk`` must be imported INSIDE the publish
path (never at module import time) — exactly like the family's
``nostr_giftwrap.build_gift_wrap`` — because the suite injects a fake
``nostr_sdk`` via ``sys.modules`` around each call. A module-level
``import nostr_sdk`` would capture the real SDK and break the hermetic double.

Errors
    ``EnvKeyError``         a required env var is missing
    ``KeyCollisionError``   client key == server key
    ``PlaintextLeakError``  the outbound event would carry plaintext payload

Runs offline: a fake ``nostr_sdk`` is injected into ``sys.modules`` and the
relay fan-out is an in-process recorder, so no socket, no DNS, no Rust binding
and no relay is touched.

Run:
    P=/opt/miniconda/bin/python
    $P -m pytest firmware/e80-stm32-bench/tools/test_verdict_transport.py -v
    $P -m pytest firmware/e80-stm32-bench/tools/test_verdict_transport.py \\
        -k "wrap or leak or key or relay" -v
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import inspect
import io
import json
import logging
import os
import sys
import types
import unittest
from contextlib import redirect_stdout
from typing import Any, Mapping, Optional, Sequence

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

try:  # RED-first: the module is authored by a later card. Until it lands,
    import verdict_transport as vt  # noqa: E402,F401  the whole file collects
    # as `ModuleNotFoundError` — the family's "red first: file absent" state
    # (cf. card t_8b927b22 / t_88b2e58f evidence pattern).
except ImportError:  # pragma: no cover - the RED state
    raise

# ---------------------------------------------------------------------------
# Fixtures — real bech32 strings, fake crypto
# ---------------------------------------------------------------------------

#: Family-verified vector (``test_nostr_giftwrap.py``): secp256k1 generator
#: x-coordinate and its bech32 npub encoding. Re-verified in this suite by
#: ``test_key_env_names_are_the_single_documented_source``'s companion check.
G_HEX = "79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
G_NPUB = "npub10xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqpkge6d"

CLIENT_HEX = "11" * 32
SERVER_HEX = "22" * 32
TX_HEX = "33" * 32

#: Distinctness of the three fixture hexes is load-bearing (a collision would
#: make the KeyCollisionError test vacuous).
assert len({CLIENT_HEX, SERVER_HEX, TX_HEX}) == 3

#: Distinctive canary for the hostile leak case. Never a substring of the
#: ciphertext stand-in or of any derived id (verified below).
CANARY = "VERDICT-CANARY-7c1f9e0a-leak-probe"

#: The verdict payload whose strings must NEVER appear in the outbound event.
LEAK_FRAGMENTS = (
    "2610130435a3f",                  # session_id
    "stop-70km",                      # stop
    "cfg-a-2g4-flrc-655k",            # per_config label
    "cfg-b-lora-sf5",                 # per_config label (THIN)
    "resend-70km-2610130435a3f",      # inlined resend json name
    "GAPS",                           # summary verdict token
    "per_config",                     # payload field name
    "resend_json",                    # payload field name
    "session_id",                     # payload field name
    "summary",                        # payload field name
    "stat_count",                     # payload field name
    "log_gap",                        # payload field name
    "THIN",                           # per-config status
    "VERDICT",                        # message type
    CANARY,                           # hostile marker
)

#: The sensitive "verdict field/value" set asserted absent recursively.
SENSITIVE_FIELD_NAMES = (
    "payload", "serialized", "verdict", "summary", "per_config", "resend_json",
    "session_id", "stat_count", "log_gap",
)


def _verdict_payload(canary: Optional[str] = None) -> dict:
    """The verdict message a completed config scan produces (family shape)."""
    payload = {
        "type": "VERDICT",
        "session_id": "2610130435a3f",
        "stop": "stop-70km",
        "summary": "70km s2610130435a3f: GAPS cfg-b:THIN 3/10 cfg-c:MISS "
                   "(1/3 clean)",
        "per_config": [
            {"idx": 0, "label": "cfg-a-2g4-flrc-655k", "n_pkts": 100,
             "counted": 100, "status": "OK"},
            {"idx": 1, "label": "cfg-b-lora-sf5", "n_pkts": 100,
             "counted": 3, "status": "THIN"},
        ],
        "resend_json": {"name": "resend-70km-2610130435a3f",
                        "configs": [{"idx": 1, "label": "cfg-b-lora-sf5",
                                     "n": 97, "gap_seq": [11, 12, 13]}]},
        "log_gap": False,
        "stat_count": 9,
        "created_at": 1789800000,
        "author": "aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899",
    }
    if canary is not None:
        payload["resend_json"]["note"] = canary
        payload["summary"] = payload["summary"] + " " + canary
    return payload


def _serializer(payload: Any, calls: Optional[list] = None):
    """A payload_serializer the caller owns: it returns the JSON string.

    This is the interface fixed by the spec — the CALLER serializes; the
    transport only ever sees the result. The transport must therefore hand the
    serializer's exact return value to the wrap primitive (pinned by
    ``test_publish_wraps_the_serializer_output_into_the_wrap_rumor``).
    """
    text = payload if isinstance(payload, str) else json.dumps(payload)

    def _ser() -> str:
        if calls is not None:
            calls.append(text)
        return text

    return _ser


#: Fake NIP-44 ciphertext stand-in: base64(sha256("nip44:" + content)). It is
#: what a REAL wrap produces in place of the rumor content (the rumor itself is
#: sealed), and it provably contains none of LEAK_FRAGMENTS. Exported as the
#: outbound event's ``content`` so the leak assertions run against a
#: realistic-but-traceable value, and so the fake WRAPPER can recover the
#: original content for the "rumor wrapper" recursion case.
CIPHER_PREFIX = "nip44:"


def _fake_cipher(blob: str) -> str:
    """Fake NIP-44 ciphertext: base64(sha256(CIPHER_PREFIX + content))."""
    return base64.b64encode(
        hashlib.sha256((CIPHER_PREFIX + blob).encode("utf-8")).digest()
    ).decode("ascii")


# ---------------------------------------------------------------------------
# Fake nostr_sdk — the wrap call shape, no Rust bindings
# ---------------------------------------------------------------------------

class FakeKind:
    """``nostr_sdk.Kind`` is a Rust enum wrapper; compare via ``as_u16()``."""

    def __init__(self, value):
        self._value = int(value)

    def as_u16(self):
        return self._value

    def __int__(self):
        return self._value

    def __eq__(self, other):
        if isinstance(other, FakeKind):
            return self._value == other._value
        if isinstance(other, int):
            return self._value == other
        return NotImplemented

    def __hash__(self):
        return hash(self._value)


class FakeTag:
    """``nostr_sdk.Tag`` is NOT iterable; elements come out via ``as_vec()``."""

    def __init__(self, values):
        self._values = [str(v) for v in values]

    def as_vec(self):
        return list(self._values)

    def __eq__(self, other):
        if isinstance(other, FakeTag):
            return self._values == other._values
        if isinstance(other, (list, tuple)):
            return self._values == [str(v) for v in other]
        return NotImplemented


class _Tags:
    """``TagList``-like: ``.to_vec()`` yields ``Tag`` objects."""

    def __init__(self, tags):
        self._tags = [list(t) for t in tags]

    def to_vec(self):
        return [FakeTag(t) for t in self._tags]


class FakeEvent:
    """Mimics ``nostr_sdk.Event``: kind()/tags()/content()/as_json()."""

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
    """Mimics ``nostr_sdk.UnsignedEvent`` (from_json + content()/tags())."""

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

    def pubkey(self):
        return FakePublicKey(self.data["pubkey"])

    def to_json(self):
        return json.dumps(self.data)

    def __repr__(self):
        return "FakeUnsignedEvent(%r)" % (self.data,)


class FakePublicKey:
    """Strict: ``parse()`` only accepts 64-char hex.

    The npub->hex conversion therefore has to happen inside
    ``verdict_transport``, never in the SDK.
    """

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
    """Minimal relay client: records ``send_event()`` calls."""

    def __init__(self):
        self.sent = []

    async def send_event(self, event):
        self.sent.append(event)

    async def shutdown(self):
        pass


class FakeSdk:
    """Injects a fake ``nostr_sdk`` for the duration of one test.

    ``gift_wrap`` records its arguments and returns a kind-1059 event whose
    ``content`` is the fake ciphertext of the rumor's content — so the suite
    can prove the rumor travelled INSIDE the wrap, and can walk every layer.
    """

    def __init__(self):
        self.calls = []          # [{signer, recipient, unsigned_event}]
        self.events = []         # the wrapped events handed back
        self._previous = None

    def install(self):
        calls = self.calls
        events = self.events

        async def fake_gift_wrap(signer, recipient, unsigned_event):
            calls.append({"signer": signer, "recipient": recipient,
                          "unsigned_event": unsigned_event})
            rumor_content = unsigned_event.content()
            event = FakeEvent(
                kind=1059,
                tags=[["p", recipient.to_hex()]],
                content=_fake_cipher(rumor_content),
                pubkey="ef" * 32,
                event_id=hashlib.sha256(
                    _fake_cipher(rumor_content).encode("utf-8")).hexdigest(),
                created_at=getattr(unsigned_event, "created_at", 0),
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
        mod.Event = FakeEvent
        mod.Filter = lambda *a, **k: None
        mod.Kind = FakeKind
        mod.gift_wrap = fake_gift_wrap
        self._previous = sys.modules.get("nostr_sdk")
        sys.modules["nostr_sdk"] = mod

    def remove(self):
        if self._previous is None:
            sys.modules.pop("nostr_sdk", None)
        else:
            sys.modules["nostr_sdk"] = self._previous

    # --- assertions helpers -------------------------------------------------

    def wrapped_contents(self) -> list:
        """The rumor content handed to ``gift_wrap`` on every call."""
        return [c["unsigned_event"].content() for c in self.calls]

    @property
    def last_wrap(self) -> dict:
        assert self.calls, "nostr_sdk.gift_wrap was never called"
        return self.calls[-1]


# ---------------------------------------------------------------------------
# Fake relay transport — the only wire seam
# ---------------------------------------------------------------------------

class FakeRelayTransport:
    """In-process recorder standing in for the relay fan-out.

    Records the events it is handed and any hosts it was constructed for. It
    never dials anything: no socket, no DNS, no websocket.
    """

    def __init__(self, hosts: Sequence[str] = ()):
        self.hosts = list(hosts)
        self.sent = []
        self.relay_results: dict = {}

    async def send_event(self, event):
        self.sent.append(event)
        for host in self.hosts or ("local-double",):
            self.relay_results[host] = "accepted"
        # Per-host results are offered BOTH as an attribute and as the return
        # value, so an implementation may aggregate from either.
        return {"accepted": len(self.relay_results) or 1,
                "relay_results": dict(self.relay_results),
                "event_id": _event_id(event)}

    def reset(self):
        self.sent.clear()
        self.relay_results.clear()


def _event_id(event) -> str:
    """Deterministic id view of an event double (never a fabricated constant)."""
    try:
        raw = event.as_json()
    except AttributeError:
        raw = json.dumps(event, sort_keys=True)
    return hashlib.sha256(str(raw).encode("utf-8")).hexdigest()


def _event_dict(event) -> dict:
    """Best-effort dict view of an event double (for recursive walking)."""
    if isinstance(event, dict):
        return event
    try:
        return json.loads(event.as_json())
    except (AttributeError, ValueError, TypeError):
        return {"raw": repr(event)}


# ---------------------------------------------------------------------------
# Structural leak walker — recursively covers dict/list/tuple/set/str
# ---------------------------------------------------------------------------

def walk_strings(obj: Any, _depth: int = 0, _seen: Optional[set] = None):
    """Yield every string reachable from ``obj``, at any nesting depth.

    Deliberately structural, not ``json.dumps(obj)``-only: keys AND values of
    dicts, every list/tuple element, every set member, and the raw string of any
    other repr-able leaf are all covered, so a leak cannot hide behind a second
    ``json.dumps`` or inside an unusual container.
    """
    if _seen is None:
        _seen = set()
    if _depth > 25:                      # hostile-input guard
        return
    if isinstance(obj, str):
        yield obj
        return
    if isinstance(obj, (bytes, bytearray)):
        yield obj.decode("utf-8", "replace")
        return
    if isinstance(obj, Mapping):
        oid = id(obj)
        if oid in _seen:
            return
        _seen.add(oid)
        for key, value in obj.items():
            yield from walk_strings(key, _depth + 1, _seen)
            yield from walk_strings(value, _depth + 1, _seen)
        return
    if isinstance(obj, (list, tuple, set, frozenset)):
        oid = id(obj)
        if oid in _seen:
            return
        _seen.add(oid)
        for item in obj:
            yield from walk_strings(item, _depth + 1, _seen)
        return
    if isinstance(obj, (int, float, bool)) or obj is None:
        return
    # Tag-like / event-like objects: ask them for their JSON view.
    as_json = getattr(obj, "as_json", None)
    if callable(as_json):
        try:
            yield from walk_strings(json.loads(as_json()), _depth + 1, _seen)
            return
        except (ValueError, TypeError):
            pass
    as_vec = getattr(obj, "as_vec", None)
    if callable(as_vec):
        try:
            yield from walk_strings(list(as_vec()), _depth + 1, _seen)
            return
        except (TypeError, ValueError):
            pass
    yield repr(obj)


def outbound_strings(result: Any) -> list:
    """Every string reachable from a ``publish_verdict`` result's WIRE surface.

    Covers, recursively: the outbound event (including ``tags`` and
    ``content``), any serialized view of it the module exposes (``outbound`` /
    ``wrapped``), the relay results, and a ``json.dumps`` of each layer.

    Deliberately EXCLUDES the result's ``rumor`` / ``inner`` attribute: the
    pre-wrap rumor is the plaintext payload BY DESIGN — it exists precisely so
    it can be sealed inside the wrap (the wrap tests pin that it reaches the
    wrap primitive). The leak property under test is about the wire artifact:
    what ``send_event`` put on the wire. A nested leak (e.g. a rumor JSON
    parked inside an outer tag or inside the outer content) IS caught, because
    the walk recurses through every string inside the event dict itself.
    """
    chunks = []
    for attr in ("event", "outbound", "wrapped", "relay_results", "result"):
        layer = getattr(result, attr, None)
        if layer is None:
            continue
        chunks.append(layer)
        if not isinstance(layer, (str, bytes, bytearray)):
            try:
                chunks.append(json.dumps(_event_dict(layer), sort_keys=True,
                                         default=repr))
            except (TypeError, ValueError):
                pass
    if isinstance(result, Mapping):
        chunks.append(result)
    elif not any(getattr(result, a, None) is not None
                 for a in ("event", "outbound", "wrapped")):
        chunks.append(result)
    strings = []
    for chunk in chunks:
        if isinstance(chunk, str):
            strings.append(chunk)
        strings.extend(walk_strings(chunk))
    return strings


def leak_hits(result: Any, fragments: Sequence[str]) -> list:
    """Fragments found in the outbound layers (empty list == no leak)."""
    haystack = outbound_strings(result)
    hits = []
    for fragment in fragments:
        for text in haystack:
            if fragment in text:
                hits.append(fragment)
                break
    return hits


# ---------------------------------------------------------------------------
# Log / stdout capture — prove no key material is emitted
# ---------------------------------------------------------------------------

class _Recorder(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(record)

    @property
    def text(self) -> str:
        parts = []
        for record in self.records:
            try:
                parts.append(record.getMessage())
            except Exception:  # pragma: no cover - a broken formatter
                parts.append(repr(record.msg))
            parts.append(str(getattr(record, "args", "")))
            parts.append(str(record.exc_info))
        return "\n".join(parts)


class Capture:
    """Capture every log record (root, DEBUG) plus stdout for one block."""

    def __init__(self):
        self.recorder = _Recorder()
        self.stdout = io.StringIO()
        self._prev_level = None
        self._root = logging.getLogger()
        self._ctx = None

    def __enter__(self):
        self._prev_level = self._root.level
        self._root.addHandler(self.recorder)
        self._root.setLevel(logging.DEBUG)
        self._ctx = redirect_stdout(self.stdout)
        self._ctx.__enter__()
        return self

    def __exit__(self, *exc):
        try:
            self._ctx.__exit__(*exc)
        finally:
            self._root.removeHandler(self.recorder)
            self._root.setLevel(self._prev_level)
        return False

    @property
    def text(self) -> str:
        return self.recorder.text + "\n" + self.stdout.getvalue()


# ---------------------------------------------------------------------------
# Call plumbing — publish_verdict may be sync or async
# ---------------------------------------------------------------------------

def _call(func, *args, **kwargs):
    """Invoke ``func``, awaiting it if it is a coroutine function."""
    out = func(*args, **kwargs)
    if inspect.isawaitable(out):
        return asyncio.run(out)
    return out


def _publish(payload, transport, env=None, serializer_calls=None, **kwargs):
    return _call(vt.publish_verdict, _serializer(payload, serializer_calls),
                 transport=transport, env=env, **kwargs)


@contextlib.contextmanager
def fake_relay_factory(recorded: Optional[dict] = None):
    """Swap ``relay_transport_factory`` for a recorder (hermetic default path).

    The default-transport tests must exercise the module's OWN choice of relay
    set without a socket, so the seam is replaced for the duration of the block
    and the URLs it was handed are recorded.
    """
    recorded = recorded if recorded is not None else {}
    original = vt.relay_transport_factory

    def _factory(urls, env=None):
        recorded["urls"] = list(urls)
        recorded["env"] = env
        transport = FakeRelayTransport(
            hosts=[u.split("://", 1)[-1] for u in urls])
        recorded["transport"] = transport
        return transport

    vt.relay_transport_factory = _factory
    try:
        yield recorded
    finally:
        vt.relay_transport_factory = original


def _base_env(**overrides) -> dict:
    """The documented env-only key source, with every name a secret needs."""
    env = {
        vt.ENV_CLIENT_NSEC: CLIENT_NSEC,
        vt.ENV_SERVER_NSEC: SERVER_NSEC,
        vt.ENV_TX_NPUB: TX_NPUB,
    }
    env.update(overrides)
    return env


# --- real bech32 helpers (the fixtures ARE bech32, not placeholders) --------

_BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def _bech32_polymod(values):
    gen = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3]
    chk = 1
    for value in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ value
        for i in range(5):
            chk ^= gen[i] if ((top >> i) & 1) else 0
    return chk


def _bech32_hrp_expand(hrp):
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def _bech32_checksum(hrp, data):
    values = _bech32_hrp_expand(hrp) + data
    pm = _bech32_polymod(values + [0] * 6) ^ 1
    return [(pm >> 5 * (5 - i)) & 31 for i in range(6)]


def _bech32_convertbits(data, frombits, tobits, pad=True):
    acc = 0
    bits = 0
    ret = []
    maxv = (1 << tobits) - 1
    for value in data:
        if value < 0 or (value >> frombits):
            raise ValueError("invalid value")
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        raise ValueError("invalid padding")
    return ret


def bech32_encode(hrp: str, hex32: str) -> str:
    data = _bech32_convertbits(bytes.fromhex(hex32), 8, 5)
    checksum = _bech32_checksum(hrp, data)
    return hrp + "1" + "".join(_BECH32_CHARSET[d] for d in data + checksum)


CLIENT_NSEC = bech32_encode("nsec", CLIENT_HEX)
SERVER_NSEC = bech32_encode("nsec", SERVER_HEX)
TX_NPUB = bech32_encode("npub", TX_HEX)


# ===========================================================================
# WRAP — the payload is delivered inside a NIP-59 gift wrap, kind 1059
# ===========================================================================

class TestWrapEnvelope(unittest.TestCase):
    """``publish_verdict`` delivers the caller's payload inside kind 1059."""

    def setUp(self):
        self.sdk = FakeSdk()
        self.sdk.install()
        self.addCleanup(self.sdk.remove)
        self.transport = FakeRelayTransport()
        self.payload = _verdict_payload()

    def test_wrap_kind_constant_is_1059(self):
        self.assertEqual(vt.KIND_GIFT_WRAP, 1059)

    def test_wrap_inner_kind_is_the_cvm_envelope(self):
        self.assertEqual(vt.INNER_KIND, 25910)

    def test_publish_wraps_the_payload_and_publishes_kind_1059(self):
        calls = []
        result = _publish(self.payload, self.transport,
                          env=_base_env(), serializer_calls=calls)
        self.assertEqual(len(calls), 1,
                         "payload_serializer must be called exactly once")
        # exactly one wrap happened, and it produced a kind-1059 event
        self.assertEqual(len(self.sdk.calls), 1)
        outbound = result.event
        self.assertEqual(int(outbound.kind().as_u16()), 1059)
        # the event that reached the wire is the kind-1059 wrap
        self.assertEqual(len(self.transport.sent), 1)
        self.assertEqual(int(self.transport.sent[0].kind().as_u16()), 1059)

    def test_publish_wraps_the_serializer_output_into_the_wrap_rumor(self):
        """The rumor handed to the wrap is built by the CALLER's serializer.

        The rumor content travels sealed, so this suite replaces the wrap with
        a deterministic fingerprint of that content: the rumor content must be
        byte-identical to the serializer's return value.
        """
        calls = []
        _publish(self.payload, self.transport, env=_base_env(),
                 serializer_calls=calls)
        rumor_contents = self.sdk.wrapped_contents()
        self.assertEqual(len(rumor_contents), 1, "expected exactly one wrap")
        self.assertEqual(rumor_contents[0], calls[0])

    def test_wrap_published_event_is_the_one_the_sdk_returned(self):
        result = _publish(self.payload, self.transport, env=_base_env())
        self.assertIs(self.transport.sent[0], result.event)
        self.assertIs(self.sdk.events[0], result.event)

    def test_wrap_outer_event_is_addressed_to_the_tx_peer(self):
        _publish(self.payload, self.transport, env=_base_env())
        recipient = self.sdk.last_wrap["recipient"]
        self.assertEqual(recipient.to_hex(), TX_HEX,
                         "outer p tag must address the TX npub")

    def test_wrap_outer_p_tag_names_the_tx_peer_by_hex(self):
        result = _publish(self.payload, self.transport, env=_base_env())
        tags = _event_dict(result.event)["tags"]
        p_values = [t[1] for t in tags if t and t[0] == "p"]
        self.assertIn(TX_HEX, p_values)

    def test_wrap_rumor_kind_is_the_inner_cvm_envelope(self):
        result = _publish(self.payload, self.transport, env=_base_env())
        rumor = getattr(result, "rumor", None) or getattr(result, "inner", None)
        self.assertIsNotNone(
            rumor,
            "the result must expose the wrapped rumor (rumor/inner) so the "
            "outer AND inner layers can be inspected")
        kind = rumor.kind() if callable(getattr(rumor, "kind", None)) else None
        self.assertEqual(int(kind.as_u16()), vt.INNER_KIND)

    def test_wrap_is_not_re_implemented_here_the_sdk_wrap_is_the_only_path(self):
        """No hand-rolled kind-1059 event: the SDK's ``gift_wrap`` is called."""
        _publish(self.payload, self.transport, env=_base_env())
        self.assertEqual(len(self.sdk.calls), 1,
                         "exactly one nostr_sdk.gift_wrap call per publish")
        self.assertIsInstance(self.sdk.last_wrap["unsigned_event"],
                              FakeUnsignedEvent)


# ===========================================================================
# LEAK — no plaintext verdict value/field survives into the outbound event
# ===========================================================================

class TestLeakPlaintext(unittest.TestCase):
    """No plaintext verdict content is reachable in the outbound event."""

    def setUp(self):
        self.sdk = FakeSdk()
        self.sdk.install()
        self.addCleanup(self.sdk.remove)
        self.transport = FakeRelayTransport()

    def test_leak_recursive_walk_finds_no_verdict_value_in_outbound_event(self):
        result = _publish(_verdict_payload(), self.transport, env=_base_env())
        # the walker must actually be looking at something
        self.assertTrue(outbound_strings(result),
                        "the outbound layer must be inspectable at all")
        self.assertEqual(leak_hits(result, LEAK_FRAGMENTS), [],
                         "plaintext verdict content leaked on the wire")

    def test_leak_walker_covers_tags_and_content_of_the_wrapped_event(self):
        result = _publish(_verdict_payload(), self.transport, env=_base_env())
        event = _event_dict(result.event)
        self.assertEqual(int(event["kind"]), 1059)
        # tags and content are BOTH part of the walked surface
        self.assertIn("tags", event)
        self.assertNotEqual(event["content"], "",
                            "a wrapped event must carry the sealed content")
        haystack = outbound_strings(result)
        self.assertTrue(any(str(event["content"]) in s for s in haystack),
                        "the walker must include the wrapped content")
        for tag in event["tags"]:
            values = [str(v) for v in tag]
            for value in values:
                self.assertTrue(
                    any(value in s for s in haystack),
                    "the walker must include every tag value (%r missed)"
                    % (value,))

    def test_leak_walker_recurses_into_tags_that_wrap_a_second_json_blob(self):
        """A tag whose value is JSON-encoded must be walked too.

        This is the shape a lazy implementation would produce: the payload
        stuffed into a tag as a JSON string. It must be caught.
        """
        hostile = _verdict_payload()

        class HostileTransport(FakeRelayTransport):
            async def send_event(self, event):
                event._tags.append(
                    ["verdict_json", json.dumps(hostile, sort_keys=True)])
                return await super().send_event(event)

        result = _publish(hostile, HostileTransport(), env=_base_env())
        hits = leak_hits(result, LEAK_FRAGMENTS)
        self.assertNotEqual(
            hits, [],
            "the walker FAILED to detect a plaintext payload parked in a tag "
            "— the leak test is vacuous")

    def test_leak_walker_recurses_into_a_rumor_wrapper_layer(self):
        result = _publish(_verdict_payload(), self.transport, env=_base_env())
        event = _event_dict(result.event)
        wrapped = {
            "outer": event,
            "rumor": {"kind": vt.INNER_KIND, "content": "SECRET-RUMOR-MARKER"},
        }
        hits = leak_hits(wrapped, ["SECRET-RUMOR-MARKER"])
        self.assertEqual(hits, ["SECRET-RUMOR-MARKER"],
                         "the walker must see through a rumor wrapper dict")

    def test_leak_no_sensitive_payload_field_name_appears_in_the_event(self):
        result = _publish(_verdict_payload(), self.transport, env=_base_env())
        haystack = "\n".join(outbound_strings(result))
        for name in SENSITIVE_FIELD_NAMES:
            self.assertNotIn(name, haystack,
                             "verdict field name %r reached the event" % name)

    def test_leak_hostile_canary_never_reaches_json_dumps_of_the_event(self):
        """The canary case: a distinctive token in the payload stays inside."""
        payload = _verdict_payload(canary=CANARY)
        self.assertIn(CANARY, json.dumps(payload),
                      "fixture bug: the canary must be in the payload")
        result = _publish(payload, self.transport, env=_base_env())

        # the outbound event and its gift-wrap layers (the sealed content, the
        # tags, and any wrapper nested INSIDE the event object itself). The
        # pre-wrap rumor input is not an outbound layer — it is what the wrap
        # seals; the wrap tests pin that it reaches the wrap primitive.
        layers = [json.dumps(_event_dict(result.event), sort_keys=True)]
        for attr in ("outbound", "wrapped"):
            layer = getattr(result, attr, None)
            if layer is None:
                continue
            try:
                layers.append(json.dumps(_event_dict(layer), sort_keys=True,
                                         default=repr))
            except (TypeError, ValueError):
                layers.append(repr(layer))
        for name in dir(result.event):
            if name.startswith("_"):
                continue
            nested = getattr(result.event, name)
            if callable(nested):
                continue
            layers.append(repr(nested))
        for index, layer in enumerate(layers):
            self.assertNotIn(CANARY, layer,
                             "canary leaked into gift-wrap layer %d" % index)

        self.assertEqual(leak_hits(result, (CANARY,)), [],
                         "canary reached the outbound surface")

    def test_leak_canary_ciphertext_probe_only(self):
        """Control: the canary WOULD be caught if it reached the content.

        Guards the whole leak class against vacuity — the same assertion
        machinery, pointed at a poisoned event, must fire.
        """
        payload = _verdict_payload(canary=CANARY)

        class PoisoningTransport(FakeRelayTransport):
            async def send_event(self, event):
                event._content = event._content + "|" + CANARY
                return await super().send_event(event)

        result = _publish(payload, PoisoningTransport(), env=_base_env())
        self.assertEqual(leak_hits(result, (CANARY,)), [CANARY],
                         "the leak assertion is vacuous: a poisoned outbound "
                         "event was NOT detected")

    def test_leak_plaintext_kind_is_never_constructed(self):
        """No kind-30315 (plaintext tally) event is ever emitted."""
        result = _publish(_verdict_payload(), self.transport, env=_base_env())
        kinds = {int(_event_dict(result.event)["kind"])}
        derived = getattr(vt, "KIND_PLAINTEXT_TALLY", None)
        if derived is not None:
            self.assertNotIn(derived, kinds)
            self.assertEqual(derived, 30315)
        self.assertNotIn(30315, kinds)
        for sent in self.transport.sent:
            self.assertNotEqual(int(sent.kind().as_u16()), 30315)

    def test_leak_guard_error_type_exists_and_is_a_plaintext_error(self):
        self.assertTrue(issubclass(vt.PlaintextLeakError, Exception))


# ===========================================================================
# KEY — env-only key material, missing/collision errors, no log emission
# ===========================================================================

class TestKeyHandling(unittest.TestCase):
    """Keys come from the environment only, and never reach a log."""

    def setUp(self):
        self.sdk = FakeSdk()
        self.sdk.install()
        self.addCleanup(self.sdk.remove)
        self.transport = FakeRelayTransport()

    def test_key_env_names_are_the_single_documented_source(self):
        self.assertEqual(vt.ENV_CLIENT_NSEC, "CVM_RX_NSEC")
        self.assertEqual(vt.ENV_CLIENT_HEX, "CVM_RX_HEX")
        self.assertEqual(vt.ENV_SERVER_NSEC, "CVM_SERVER_NSEC")
        self.assertEqual(vt.ENV_SERVER_HEX, "CVM_SERVER_HEX")
        self.assertEqual(vt.ENV_TX_NPUB, "CVM_TX_NPUB")

    def test_key_interface_takes_no_key_parameter(self):
        """The interface is fixed: no key/secret may be passed as an argument."""
        signature = inspect.signature(vt.publish_verdict)
        names = list(signature.parameters)
        self.assertIn("payload_serializer", names)
        for name in names:
            lowered = name.lower()
            for forbidden in ("key", "nsec", "secret", "priv"):
                self.assertNotIn(
                    forbidden, lowered,
                    "publish_verdict exposes a key-bearing parameter %r — keys "
                    "are read from the environment only" % (name,))

    def test_key_reads_from_env_only_ignoring_process_environ(self):
        """The ``env`` mapping is the authority; a real env var cannot override.

        ``os.environ`` is cleared of every documented key name for the call, so
        a successful publish proves the ``env=`` mapping was used.
        """
        saved = {name: os.environ.pop(name, None) for name in (
            vt.ENV_CLIENT_NSEC, vt.ENV_CLIENT_HEX, vt.ENV_SERVER_NSEC,
            vt.ENV_SERVER_HEX, vt.ENV_TX_NPUB)}
        try:
            result = _publish(_verdict_payload(), self.transport,
                              env=_base_env())
            self.assertIsNotNone(result.event)
        finally:
            for name, value in saved.items():
                if value is not None:
                    os.environ[name] = value

    def test_key_env_hex_alternative_is_accepted(self):
        env = {
            vt.ENV_CLIENT_HEX: CLIENT_HEX,
            vt.ENV_SERVER_HEX: SERVER_HEX,
            vt.ENV_TX_NPUB: TX_NPUB,
        }
        result = _publish(_verdict_payload(), self.transport, env=env)
        self.assertEqual(int(result.event.kind().as_u16()), 1059)

    def test_key_missing_client_env_raises_a_clear_error(self):
        env = {vt.ENV_SERVER_NSEC: SERVER_NSEC, vt.ENV_TX_NPUB: TX_NPUB}
        with self.assertRaises(vt.EnvKeyError) as ctx:
            _publish(_verdict_payload(), self.transport, env=env)
        message = str(ctx.exception)
        self.assertIn(vt.ENV_CLIENT_NSEC, message,
                      "the error must name the missing variable")
        self.assertEqual(self.transport.sent, [],
                         "nothing may be published without keys")

    def test_key_missing_server_env_raises_a_clear_error(self):
        env = {vt.ENV_CLIENT_NSEC: CLIENT_NSEC, vt.ENV_TX_NPUB: TX_NPUB}
        with self.assertRaises(vt.EnvKeyError) as ctx:
            _publish(_verdict_payload(), self.transport, env=env)
        self.assertIn(vt.ENV_SERVER_NSEC, str(ctx.exception))
        self.assertEqual(self.transport.sent, [])

    def test_key_missing_tx_npub_env_raises_a_clear_error(self):
        env = {vt.ENV_CLIENT_NSEC: CLIENT_NSEC,
               vt.ENV_SERVER_NSEC: SERVER_NSEC}
        with self.assertRaises(vt.EnvKeyError) as ctx:
            _publish(_verdict_payload(), self.transport, env=env)
        self.assertIn(vt.ENV_TX_NPUB, str(ctx.exception))
        self.assertEqual(self.transport.sent, [])

    def test_key_empty_env_raises_the_env_error_not_a_crash(self):
        with self.assertRaises(vt.EnvKeyError):
            _publish(_verdict_payload(), self.transport, env={})

    def test_key_client_equal_to_server_raises_a_collision_error(self):
        """A shared key would make the client unwrap its own gift wraps."""
        env = {
            vt.ENV_CLIENT_NSEC: CLIENT_NSEC,
            vt.ENV_SERVER_NSEC: CLIENT_NSEC,     # SAME key on both sides
            vt.ENV_TX_NPUB: TX_NPUB,
        }
        with self.assertRaises(vt.KeyCollisionError) as ctx:
            _publish(_verdict_payload(), self.transport, env=env)
        self.assertEqual(self.transport.sent, [],
                         "nothing may be published with a key collision")
        self.assertEqual(self.sdk.calls, [],
                         "no wrap may be attempted with a key collision")
        self.assertNotIn(CLIENT_NSEC, str(ctx.exception))
        self.assertNotIn(CLIENT_HEX, str(ctx.exception))

    def test_key_client_equal_to_server_hex_also_collides(self):
        env = {
            vt.ENV_CLIENT_HEX: SERVER_HEX,
            vt.ENV_SERVER_HEX: SERVER_HEX,
            vt.ENV_TX_NPUB: TX_NPUB,
        }
        with self.assertRaises(vt.KeyCollisionError):
            _publish(_verdict_payload(), self.transport, env=env)

    def test_key_collision_error_is_distinct_from_env_key_error(self):
        self.assertFalse(issubclass(vt.KeyCollisionError, vt.EnvKeyError),
                         "a key collision is not a missing variable")
        self.assertFalse(issubclass(vt.EnvKeyError, vt.KeyCollisionError))

    def test_key_material_is_never_emitted_via_logging_or_stdout(self):
        with Capture() as capture:
            # capture self-check: the recorder must actually record
            logging.getLogger("gate1.selfcheck").debug(
                "recorder-selfcheck-%s", "alive")
            result = _publish(_verdict_payload(), self.transport,
                              env=_base_env())
        text = capture.text
        self.assertIn("recorder-selfcheck-alive", text,
                      "the log capture is broken — absence assertions would be "
                      "vacuous")
        for secret in (CLIENT_NSEC, SERVER_NSEC, CLIENT_HEX, SERVER_HEX,
                       CLIENT_HEX.upper(), SERVER_HEX.upper()):
            self.assertNotIn(secret, text,
                             "key material reached a log/stdout sink")
        self.assertIsNotNone(result.event)

    def test_key_missing_env_error_message_never_echoes_key_material(self):
        env = {vt.ENV_SERVER_NSEC: SERVER_NSEC, vt.ENV_TX_NPUB: TX_NPUB,
               vt.ENV_CLIENT_NSEC: ""}
        with Capture() as capture:
            with self.assertRaises(vt.EnvKeyError) as ctx:
                _publish(_verdict_payload(), self.transport, env=env)
        self.assertNotIn(SERVER_NSEC, str(ctx.exception))
        self.assertNotIn(SERVER_NSEC, capture.text)

    def test_key_collision_error_message_never_echoes_key_material(self):
        env = {
            vt.ENV_CLIENT_NSEC: CLIENT_NSEC,
            vt.ENV_SERVER_NSEC: CLIENT_NSEC,
            vt.ENV_TX_NPUB: TX_NPUB,
        }
        with Capture() as capture:
            with self.assertRaises(vt.KeyCollisionError) as ctx:
                _publish(_verdict_payload(), self.transport, env=env)
        self.assertNotIn(CLIENT_NSEC, str(ctx.exception))
        self.assertNotIn(CLIENT_NSEC, capture.text)

    def test_key_helpers_expose_a_distinct_keys_assertion(self):
        """``assert_keys_differ`` must be the single collision predicate."""
        self.assertTrue(callable(vt.assert_keys_differ))
        with self.assertRaises(vt.KeyCollisionError):
            vt.assert_keys_differ(CLIENT_HEX, CLIENT_HEX)
        vt.assert_keys_differ(CLIENT_HEX, SERVER_HEX)   # must not raise


# ===========================================================================
# RELAY — the exact five-host failover set, in order, dead host absent
# ===========================================================================

EXPECTED_RELAY_HOSTS = [
    "nostr.mom",
    "relay.primal.net",
    "nos.lol",
    "relay2.contextvm.org",
    "relay.nostr.band",
]


class TestRelaySet(unittest.TestCase):
    """The relay set is exactly the five ordered bare hostnames."""

    def setUp(self):
        # Hermeticity: the default-transport path reaches nostr_sdk, so the
        # fake SDK must be installed for these tests too (never the real one).
        self.sdk = FakeSdk()
        self.sdk.install()
        self.addCleanup(self.sdk.remove)
        self.payload = _verdict_payload()

    def test_relay_set_is_exactly_the_five_ordered_hosts(self):
        self.assertEqual(list(vt.FAILOVER_RELAYS), EXPECTED_RELAY_HOSTS)

    def test_relay_order_is_significant_and_pinned_by_sha256(self):
        digest = hashlib.sha256(json.dumps(
            list(vt.FAILOVER_RELAYS), separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        expected = hashlib.sha256(json.dumps(
            EXPECTED_RELAY_HOSTS, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        self.assertEqual(digest, expected,
                         "FAILOVER_RELAYS changed in value or order")

    def test_relay_set_has_no_duplicates(self):
        hosts = list(vt.FAILOVER_RELAYS)
        self.assertEqual(len(hosts), len(set(hosts)))

    def test_relay_membership_matches_one_by_one_in_order(self):
        hosts = list(vt.FAILOVER_RELAYS)
        for index, expected in enumerate(EXPECTED_RELAY_HOSTS):
            self.assertEqual(hosts[index], expected,
                             "relay %d drifted" % index)

    def test_relay_first_choice_is_nostr_mom(self):
        self.assertEqual(list(vt.FAILOVER_RELAYS)[0], "nostr.mom")

    def test_relay_urls_are_derived_from_the_bare_hosts(self):
        self.assertEqual(list(vt.FAILOVER_RELAY_URLS),
                         ["wss://" + host for host in vt.FAILOVER_RELAYS])

    def test_relay_entries_are_bare_hostnames(self):
        for host in vt.FAILOVER_RELAYS:
            self.assertIsInstance(host, str)
            self.assertTrue(host)
            self.assertNotIn("://", host, "scheme leaked into a bare host")
            self.assertNotIn("/", host, "path leaked into a bare host")
            self.assertNotIn(":", host, "port leaked into a bare host")
            self.assertEqual(host, host.strip())
            self.assertEqual(host, host.lower())

    def test_relay_dead_contextvm_host_is_not_a_member(self):
        hosts = list(vt.FAILOVER_RELAYS)
        urls = list(vt.FAILOVER_RELAY_URLS)
        self.assertNotIn("relay.contextvm.org", hosts)
        self.assertNotIn("wss://relay.contextvm.org", urls)
        for host in hosts:
            self.assertNotEqual(host, "relay.contextvm.org")

    def test_relay_dead_host_is_named_as_dead(self):
        dead = [str(entry) for entry in vt.DEAD_RELAYS]
        self.assertIn("wss://relay.contextvm.org", dead)

    def test_relay_live_contextvm_host_is_the_numbered_one(self):
        """``relay2.contextvm.org`` is alive; only the unnumbered one is dead."""
        hosts = list(vt.FAILOVER_RELAYS)
        self.assertIn("relay2.contextvm.org", hosts)
        self.assertEqual(hosts.index("relay2.contextvm.org"), 3)

    def test_relay_publish_default_transport_uses_the_canonical_set(self):
        """The default fan-out is built from the canonical URL view."""
        with fake_relay_factory() as seen:
            result = _publish(self.payload, None, env=_base_env())
        self.assertIsNotNone(getattr(result, "event", None),
                             "publish must succeed through the default path")
        self.assertEqual(seen.get("urls"), list(vt.FAILOVER_RELAY_URLS),
                         "publish_verdict did not use the canonical relay set")
        for host in seen["urls"]:
            bare = host.split("://", 1)[-1]
            self.assertIn(bare, EXPECTED_RELAY_HOSTS)
            self.assertNotEqual(bare, "relay.contextvm.org")

    def test_relay_publish_records_a_result_per_canonical_host(self):
        """Every canonical host gets a relay result entry (no host skipped)."""
        with fake_relay_factory():
            result = _publish(_verdict_payload(), None, env=_base_env())
        results = result.relay_results
        self.assertTrue(hasattr(results, "__iter__"),
                        "relay_results must be an iterable of host results")
        hosts = list(results) if isinstance(results, Mapping) else [
            (row[0] if isinstance(row, (list, tuple)) else
             getattr(row, "host", None)) for row in results]
        for expected in EXPECTED_RELAY_HOSTS:
            self.assertIn(expected, hosts,
                          "no relay result recorded for %r" % expected)
        self.assertNotIn("relay.contextvm.org", hosts)


# ===========================================================================
# Self-pin: the -k selection contract
# ===========================================================================

class TestKSelectorContract(unittest.TestCase):
    """``pytest -k "wrap or leak or key or relay"`` selects the whole suite."""

    TOKENS = ("wrap", "leak", "key", "relay")

    def _test_method_names(self):
        names = []
        module = sys.modules[__name__]
        for attr in vars(module).values():
            if (isinstance(attr, type) and issubclass(attr, unittest.TestCase)
                    and attr is not unittest.TestCase):
                for name in dir(attr):
                    if name.startswith("test_"):
                        names.append(name)
        return names

    def test_every_test_name_carries_a_wrap_leak_key_relay_token(self):
        names = self._test_method_names()
        self.assertGreaterEqual(len(names), 30,
                                "expected a substantial Gate1 suite")
        uncovered = [n for n in names
                     if not any(token in n for token in self.TOKENS)]
        self.assertEqual(
            uncovered, [],
            "these tests would be MISSED by "
            "`-k \"wrap or leak or key or relay\"`: %r" % (uncovered,))

    def test_name_tokens_cover_wrap_leak_key_relay_areas(self):
        names = " ".join(self._test_method_names())
        for token in self.TOKENS:
            self.assertIn(token, names)


# ===========================================================================
# Fixture integrity
# ===========================================================================

class TestFixtureIntegrity(unittest.TestCase):
    """The fixtures this suite leans on are real encodings, not placeholders."""

    def test_key_fixture_bech32_encoder_matches_the_family_npub_vector(self):
        """The local bech32 encoder reproduces the family-verified vector.

        ``G_NPUB`` came from ``test_nostr_giftwrap.py`` (generated with
        ``nak encode npub`` and verified with an independent decoder), so
        reproducing it here proves the encoder that builds ``CLIENT_NSEC`` /
        ``SERVER_NSEC`` / ``TX_NPUB`` emits valid bech32.
        """
        self.assertEqual(bech32_encode("npub", G_HEX), G_NPUB)

    def test_key_fixture_secrets_are_distinct_and_wellformed(self):
        for secret, hex32 in ((CLIENT_NSEC, CLIENT_HEX),
                              (SERVER_NSEC, SERVER_HEX)):
            self.assertTrue(secret.startswith("nsec1"))
            self.assertEqual(len(CLIENT_HEX), 64)
            self.assertNotEqual(secret, CLIENT_NSEC if hex32 is SERVER_HEX
                                else SERVER_NSEC)
        self.assertTrue(TX_NPUB.startswith("npub1"))

    def test_wrap_fixture_ciphertext_holds_no_leak_fragment(self):
        """The fake ciphertext stand-in cannot collide with a leak fragment.

        If a fragment ever appeared inside the stand-in, every leak assertion
        would be vacuously red (or, worse, silently un-satisfiable).
        """
        cipher = _fake_cipher(json.dumps(_verdict_payload(canary=CANARY)))
        for fragment in LEAK_FRAGMENTS:
            self.assertNotIn(fragment, cipher)


if __name__ == "__main__":
    unittest.main()
