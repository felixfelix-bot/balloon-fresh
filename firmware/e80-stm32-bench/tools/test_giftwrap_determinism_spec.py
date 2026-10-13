#!/usr/bin/env python3
"""test_giftwrap_determinism_spec.py — hermetic spec-conformance tests for the
deterministic NIP-59 gift-wrap (kind 1059) choke point.

Card t_412ffb5a (board e80-bench). Written to the SPEC, not to the
implementation: ``tools/GIFTWRAP_DETERMINISM.md`` (branch
``pr/giftwrap-deterministic``, audited revision ``9455b07a``).

Spec items this suite pins (the five the card asked to record verbatim)
----------------------------------------------------------------------
(1) public entry point  : ``build_gift_wrap(payload, tx_npub, signer, *,
    author=None, created_at=None)`` (async) — spec §1 "Construction
    choke-point". Every test drives it. ``publish_gift_wrap`` / ``publish_armed``
    are the emission/failover entry points (§1); no private helper is imported
    and the derivation is never re-implemented here.
(2) module import path  : ``firmware/e80-stm32-bench/tools/nostr_giftwrap.py``,
    imported as ``nostr_giftwrap`` with ``tools/`` on ``sys.path`` — spec §1/§7.
(3) created_at          : session-derived, never the wall clock — spec §5
    order: explicit ``created_at`` kwarg -> ``payload['created_at']`` ->
    ``payload['t_ready_utc']`` -> ``payload['t0']`` -> deterministic fallback
    ``1_700_000_000 + (int(session_fingerprint, 16) % (1 << 31))``.
    §8: the *outer* kind-1059 ``created_at`` is stamped by the pinned
    ``nostr_sdk`` constructor (wall clock) and is NOT part of the contract; the
    frozen value is the inner-rumor one.
(4) payload encoding    : §3.2.6 recipient is bech32-or-hex in, ALWAYS 64-char
    lowercase hex out (two spellings of one recipient MUST give identical
    bytes); §3.2.7 ``author`` is ``str(author)`` verbatim, not normalised; §5
    the derivation serialization uses ``ensure_ascii=False`` while the inner
    rumor *content* uses the json default ``ensure_ascii=True``. The spec is
    SILENT on base64/hex of the plaintext payload (the outer content is NIP-44
    ciphertext); test (c) scans those encodings anyway as a belt-and-braces
    check the spec does not itself require.
(5) sections tested     : §1, §3 (incl. the §3.3 byte-exact vector), §4, §5,
    §6, §8, §9.

Hermetic
--------
No network, no live relays, no sleeps, no skips and no xfails. ``nostr_sdk`` is
not installed in the host CI image, and the pinned constructor is deliberately
non-deterministic per process (spec §8), so a fake constructor is injected via
``sys.modules`` (the module imports it lazily, inside ``build_gift_wrap``):

* ``FakeNostrSdk(nondeterministic=False)`` maps its inputs (unsigned rumor JSON,
  recipient hex, signer identity) 1:1 onto the event id, so an id *collision*
  proves two sessions produced byte-identical constructor inputs. That is what
  makes the sensitivity test (b) meaningful rather than vacuous.
* ``FakeNostrSdk(nondeterministic=True)`` additionally salts the id with a call
  counter, exactly like nostr-sdk 0.44 (fresh outer ephemeral key + wall-clock
  ``created_at`` per call). Any idempotence observed with it therefore comes
  from ``nostr_giftwrap``'s wrap cache, not from the fake.

An autouse fixture fails any test whose code path reaches a banned entropy
source, and inspects the module source (AST) to prove the derivation path
imports neither ``random``/``secrets``/``time`` nor calls ``os.urandom``.

Run:  cd firmware/e80-stm32-bench/tools
      python3 -m pytest -q test_giftwrap_determinism_spec.py
"""

from __future__ import annotations

import ast
import base64
import dataclasses
import hashlib
import inspect
import io
import json
import os
import random
import re
import secrets
import sys
import tokenize
import types
import uuid
from typing import Any, Mapping, Optional

import pytest

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import nostr_giftwrap as gw  # noqa: E402

SPEC = "GIFTWRAP_DETERMINISM.md"
MODULE_SOURCE = os.path.join(_TOOLS_DIR, "nostr_giftwrap.py")

# ---------------------------------------------------------------------------
# Spec §3.1 canonical fixture + §3.3 byte-exact vector (all literals, pinned)
# ---------------------------------------------------------------------------

TX_HEX = "79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
TX_NPUB = "npub10xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqpkge6d"
OTHER_TX_HEX = "aa" * 32
OTHER_TX_NPUB = "aa" * 32  # the module accepts 64-char hex in place of bech32

AUTHOR = "aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899"
OTHER_AUTHOR = "bb" * 32

#: The five hard-coded session fields the spec's canonical fixture uses (§3.1),
#: plus the two wrap-level fields (author / created_at) and the recipient.
SPEC_PAYLOAD = {
    "type": "ARMED",
    "session_id": "2608301440a3f",
    "stop": "stop-50m",
    "t_ready_utc": 1789000000,
    "preset_hash": "deadbeefcafe0001",
    "seq": 7,
    "created_at": 1788999990,
    "author": AUTHOR,
}

SPEC_CANONICAL_LEN = 414
SPEC_CANONICAL_SHA256 = (
    "bde5824afeda55bde22f34f9249ddfad31fefebf60e0651e285e4d91fe89051b")
SPEC_CANONICAL_BYTES = (
    '{"author":"aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899",'
    '"created_at":null,"payload":{"author":"aabbccddeeff00112233445566778899aabbccddeeff'
    '00112233445566778899","created_at":1788999990,"preset_hash":"deadbeefcafe0001",'
    '"seq":7,"session_id":"2608301440a3f","stop":"stop-50m","t_ready_utc":1789000000,'
    '"type":"ARMED"},"recipient":"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f'
    '2815b16f81798"}'
)
SPEC_SESSION_FINGERPRINT = (
    "e04d9c9a4f682f0dc3113de669783e4f70a6d2ca2f31ee316acd9af0a179d219")
SPEC_EPHEMERAL_SECRET = (
    "528eb7d6b7acb25bcf91cb2f1f7a39cd34b2cfc5b03826d9980673afd099e7b1")
SPEC_CREATED_AT = 1788999990

#: Spec §4 — the labels must not be renamed or swapped (HMAC key vs HKDF salt).
SPEC_SESSION_DOMAIN_LABEL = b"e80-cvm/nip59/session/v1"
SPEC_EPHEMERAL_DOMAIN_LABEL = b"e80-cvm/nip59/ephemeral/v1"

#: Outer ciphertext the fake constructor puts in ``content`` (base64, like the
#: real NIP-44 blob). Contains no plaintext fragment from SPEC_PAYLOAD.
CIPHERTEXT = base64.b64encode(bytes(range(64))).decode("ascii")

#: Outer event stamp the fake constructor applies, standing in for the pinned
#: constructor's wall clock (spec §8: the *outer* kind-1059 ``created_at`` is
#: minted by ``nostr_sdk.gift_wrap``, NOT by the session derivation). A fixed
#: literal keeps the double hermetic; in nondeterministic mode it advances per
#: call exactly like the real per-call stamp.
ENVELOPE_CREATED_AT = 1_800_000_000


# ---------------------------------------------------------------------------
# Fake nostr_sdk — hermetic double for the pinned FFI primitive
# ---------------------------------------------------------------------------

class FakeKind:
    def __init__(self, value: int) -> None:
        self._value = int(value)

    def as_u16(self) -> int:
        return self._value

    def __int__(self) -> int:
        return self._value


class FakeTag:
    """Real ``nostr_sdk.Tag`` is not iterable; elements come out via as_vec()."""

    def __init__(self, values) -> None:
        self._values = [str(v) for v in values]

    def as_vec(self):
        return list(self._values)


class _Tags:
    def __init__(self, tags) -> None:
        self._tags = [list(t) for t in tags]

    def to_vec(self):
        return [FakeTag(t) for t in self._tags]


class FakeEvent:
    """Mimics ``nostr_sdk.Event``; ``as_json`` is the byte-serialization source."""

    def __init__(self, kind, tags, content, pubkey="", event_id="", sig="",
                 created_at=0) -> None:
        self._kind = int(kind)
        self._tags = [list(t) for t in tags]
        self._content = content
        self._pubkey = pubkey
        self._id = event_id
        self._sig = sig
        self._created_at = int(created_at)

    def kind(self):
        return FakeKind(self._kind)

    def tags(self):
        return _Tags(self._tags)

    def content(self):
        return self._content

    def id(self):
        return self._id

    def sig(self):
        return self._sig

    def pubkey(self):
        return self._pubkey

    def created_at(self):
        return self._created_at

    def as_json(self):
        return json.dumps({
            "id": self._id, "pubkey": self._pubkey, "kind": self._kind,
            "tags": self._tags, "content": self._content,
            "created_at": self._created_at, "sig": self._sig,
        }, sort_keys=True, separators=(",", ":"))

    def __repr__(self) -> str:
        return "FakeEvent(id=%r)" % (self._id[:12],)


class FakeUnsignedEvent:
    def __init__(self, data) -> None:
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
        return json.dumps(self.data, sort_keys=True, separators=(",", ":"))


class FakePublicKey:
    def __init__(self, hex_value: str) -> None:
        self._hex = hex_value

    @classmethod
    def parse(cls, value):
        text = str(value)
        if len(text) != 64 or any(c not in "0123456789abcdef"
                                  for c in text.lower()):
            raise AssertionError("expected 64-char hex, got %r" % (value,))
        return cls(text.lower())

    def to_hex(self) -> str:
        return self._hex


class FakeSigner:
    """Signer double; ``pubkey`` is what the wrap cache keys on."""

    def __init__(self, pubkey: str) -> None:
        self.pubkey = pubkey


DEFAULT_SIGNER = FakeSigner(AUTHOR)
OTHER_SIGNER = FakeSigner(OTHER_AUTHOR)


def signer_identity(signer) -> str:
    return str(getattr(signer, "pubkey", "")).lower()


class FakeNostrSdk:
    """Input-deterministic (default) or per-call-randomised fake constructor.

    ``gift_wrap`` records every call and returns a kind-1059 ``FakeEvent``.
    Faithful to spec §8: the outer ``pubkey`` is an *ephemeral* key (never the
    signer's), and the outer ``created_at`` is the constructor's own stamp
    (here :data:`ENVELOPE_CREATED_AT`, advancing per call when
    ``nondeterministic=True``) rather than the session-derived value. The
    session-derived ``created_at`` the choke point fed in stays observable on
    the recorded unsigned rumor.
    """

    def __init__(self, *, nondeterministic: bool = False) -> None:
        self.nondeterministic = nondeterministic
        self.calls: list = []

    async def _fake_gift_wrap(self, signer, recipient, unsigned_event):
        identity = signer_identity(signer)
        recipient_hex = recipient.to_hex()
        record: dict = {
            "signer": signer,
            "signer_identity": identity,
            "recipient": recipient_hex,
            "unsigned_json": unsigned_event.to_json(),
            "unsigned_event": unsigned_event,
        }
        self.calls.append(record)
        seed = "%s|%s|%s" % (record["unsigned_json"], recipient_hex, identity)
        if self.nondeterministic:
            seed += "|call%d" % len(self.calls)
        data = json.loads(record["unsigned_json"])
        # NIP-59 outer pubkey is the ephemeral wrap key, never the signer's.
        ephemeral_pubkey = hashlib.sha256(
            ("ephemeral|" + identity).encode("utf-8")).hexdigest()
        created_at = ENVELOPE_CREATED_AT
        if self.nondeterministic:
            created_at += len(self.calls)  # per-call wall-clock stamp (§8)
        event = FakeEvent(
            kind=1059,
            tags=[["p", recipient_hex]],
            content=CIPHERTEXT,
            pubkey=ephemeral_pubkey,
            event_id=hashlib.sha256(seed.encode("utf-8")).hexdigest(),
            sig=hashlib.sha256(("sig|" + seed).encode("utf-8")).hexdigest(),
            created_at=created_at,
        )
        record["event"] = event
        return event

    def module(self) -> types.ModuleType:
        mod = types.ModuleType("nostr_sdk")
        mod.UnsignedEvent = FakeUnsignedEvent
        mod.PublicKey = FakePublicKey
        # NOTE: the module attribute must be spelled ``gift_wrap`` (the SDK
        # primitive name), but the function must NOT be *named* gift_wrap:
        # test_giftwrap_single_path.py::test_no_local_wrap_wrapper bans a local
        # wrapper of that name anywhere under tools/ (ADR-033).
        mod.gift_wrap = self._fake_gift_wrap
        return mod


# ---------------------------------------------------------------------------
# Fixtures / helpers (fixed literals so a test can differ in exactly one field)
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Session:
    payload: dict
    recipient: str
    author: Optional[str]
    created_at: Optional[int]
    signer: Any


def make_session(**overrides) -> Session:
    """A fully-pinned session; every field has a hard-coded literal default."""
    payload = dict(SPEC_PAYLOAD)
    wrap: dict = {"recipient": TX_NPUB, "author": AUTHOR, "created_at": None,
                  "signer": DEFAULT_SIGNER}
    for name, value in overrides.items():
        if name in wrap:
            wrap[name] = value
            if name == "author":
                # One logical field: the signing key IS the author identity.
                payload["author"] = value
        elif name in payload:
            payload[name] = value
        else:
            raise KeyError("unknown session field %r" % (name,))
    return Session(payload=payload, **wrap)


def session_fields(session: Session) -> dict:
    """The observable session fields (used to prove a one-field difference)."""
    fields = dict(session.payload)
    fields["recipient"] = session.recipient
    fields["signer"] = signer_identity(session.signer)
    return fields


def session_fingerprint(session: Session) -> str:
    return gw.session_fingerprint(session.payload, session.recipient,
                                  author=session.author,
                                  created_at=session.created_at)


async def write_session(session: Session):
    """Drive the public choke point (spec §1) for one session."""
    return await gw.build_gift_wrap(session.payload, session.recipient,
                                    session.signer, author=session.author,
                                    created_at=session.created_at)


def canonical_event_json(event) -> bytes:
    """Stable byte serialization of an event, for byte-identity assertions.

    Prefers the object's own ``as_json()`` (what the real SDK exposes) and falls
    back to the module's public ``event_view`` for plain mappings.
    """
    if isinstance(event, Mapping):
        payload = dict(event)
    else:
        as_json = getattr(event, "as_json", None)
        payload = json.loads(as_json()) if callable(as_json) else gw.event_view(event)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def event_field(event, name):
    getter = getattr(event, name, None)
    if callable(getter):
        return getter()
    if isinstance(event, Mapping):
        return event.get(name)
    return json.loads(event.as_json())[name]


def event_id(event) -> str:
    return str(event_field(event, "id"))


def event_sig(event) -> str:
    return str(event_field(event, "sig"))


def _leaf_values(obj):
    if isinstance(obj, Mapping):
        for value in obj.values():
            yield from _leaf_values(value)
    elif isinstance(obj, (list, tuple, set)):
        for item in obj:
            yield from _leaf_values(item)
    else:
        yield obj


def plaintext_fragments(payload) -> list:
    """Every string that must not survive into the outer kind-1059 event."""
    fragments = set()
    for kwargs in ({}, {"sort_keys": True},
                   {"sort_keys": True, "separators": (",", ":")},
                   {"separators": (",", ":")}):
        try:
            fragments.add(json.dumps(payload, **kwargs))
        except (TypeError, ValueError):
            pass
    for leaf in _leaf_values(payload):
        text = str(leaf)
        if len(text) >= 3:
            fragments.add(text)
    return sorted(fragments)


@pytest.fixture
def install_sdk(monkeypatch):
    """Install a fake ``nostr_sdk`` and reset the wrap cache around the test."""
    def _install(*, nondeterministic: bool = False) -> FakeNostrSdk:
        sdk = FakeNostrSdk(nondeterministic=nondeterministic)
        monkeypatch.setitem(sys.modules, "nostr_sdk", sdk.module())
        return sdk

    gw.clear_wrap_cache()
    yield _install
    gw.clear_wrap_cache()


# ---------------------------------------------------------------------------
# Autouse: no hidden clock / entropy source is ever "needed"
# ---------------------------------------------------------------------------

BANNED_MODULES = frozenset({"time", "datetime", "random", "secrets", "uuid"})
BANNED_ATTRS = frozenset({
    "urandom", "random", "randint", "randrange", "randbytes", "getrandbits",
    "choice", "uniform", "token_bytes", "token_hex", "token_urlsafe",
    "randbits", "randbelow", "uuid4",
    # wall clock
    "time", "monotonic", "perf_counter", "process_time", "now", "utcnow",
    "today",
})
DERIVATION_FUNCTIONS = (
    "_canonical_payload", "canonical_session_bytes", "session_fingerprint",
    "_hkdf_sha256", "derive_ephemeral_secret_key", "derive_created_at",
    "build_inner_rumor", "_wrap_cache_key",
)

ENTROPY_TARGETS = (
    (os, "urandom"),
    (secrets, "token_bytes"), (secrets, "token_hex"),
    (secrets, "token_urlsafe"), (secrets, "randbits"),
    (secrets, "randbelow"), (secrets, "choice"),
    (random, "random"), (random, "randint"), (random, "randrange"),
    (random, "randbytes"), (random, "uniform"), (random, "choice"),
    (random, "getrandbits"), (random, "Random"),
    (uuid, "uuid4"),
)


def _boom(label: str):
    def _raise(*_args, **_kwargs):
        raise AssertionError(
            "%s() was called on the gift-wrap derivation path - any entropy or "
            "wall-clock source in the derivation path breaks determinism "
            "(spec %s §5/§6)" % (label, SPEC))
    return _raise


def install_entropy_guard(monkeypatch) -> None:
    """Make every known entropy source raise if the derivation path reaches it."""
    for module, attr in ENTROPY_TARGETS:
        if hasattr(module, attr):
            monkeypatch.setattr(module, attr, _boom("%s.%s" % (module.__name__, attr)))


def _strip_comments_and_strings(source: str) -> str:
    """Source with COMMENT and STRING tokens removed (so docstrings cannot hit)."""
    pieces = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            pieces.append(token.string)
    except tokenize.TokenError:
        return source
    return " ".join(pieces)


def assert_no_clock_or_entropy_in_derivation_source() -> bool:
    """AST-proof: the module imports no clock/entropy module and the derivation
    functions reference no banned entropy/clock symbol."""
    with open(MODULE_SOURCE, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=MODULE_SOURCE)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                assert root not in BANNED_MODULES, (
                    "nostr_giftwrap.py imports %s - entropy in the derivation "
                    "path breaks determinism (spec %s §6)"
                    % (alias.name, SPEC))
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            assert root not in BANNED_MODULES, (
                "nostr_giftwrap.py imports from %s - entropy in the derivation "
                "path breaks determinism (spec %s §6)" % (node.module, SPEC))

    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name not in DERIVATION_FUNCTIONS:
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Attribute):
                assert inner.attr not in BANNED_ATTRS, (
                    "%s references .%s - any entropy or wall-clock source in the "
                    "derivation path breaks determinism (spec %s §5/§6)"
                    % (node.name, inner.attr, SPEC))
            elif isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name):
                assert inner.func.id not in BANNED_ATTRS, (
                    "%s calls %s() - any entropy or wall-clock source in the "
                    "derivation path breaks determinism (spec %s §5/§6)"
                    % (node.name, inner.func.id, SPEC))
    return True


@pytest.fixture(autouse=True)
def no_hidden_nondeterminism(monkeypatch):
    """Autouse: fail the test if the code under test needs any entropy or
    wall-clock source beyond what the spec defines (the spec defines none)."""
    install_entropy_guard(monkeypatch)
    assert_no_clock_or_entropy_in_derivation_source()
    yield


# ---------------------------------------------------------------------------
# (a) idempotence in-process: same session -> byte-identical event
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_idempotence_same_process(install_sdk):
    sdk = install_sdk(nondeterministic=True)  # like the real binding, per call
    session = make_session()

    first = await write_session(session)
    second = await write_session(session)
    # An unrelated second session must neither evict nor mutate the first.
    unrelated = make_session(session_id="2608301440b00", seq=99,
                             preset_hash="0badc0de00000001")
    await write_session(unrelated)
    third = await write_session(session)

    ids = [event_id(first), event_id(second), event_id(third)]
    assert ids[0] == ids[1] == ids[2], (
        "the same session produced different kind-1059 event ids %r - the wrap "
        "is not idempotent in-process (spec %s §8/§9.1)" % (ids, SPEC))
    assert canonical_event_json(first) == canonical_event_json(third), (
        "canonical_event_json drifted between two calls for one session")
    assert canonical_event_json(second) == canonical_event_json(third)

    same_object = first is second is third
    same_bytes = (ids[0] == ids[1] == ids[2]
                  and event_sig(first) == event_sig(second) == event_sig(third))
    assert same_object or same_bytes, (
        "repeat calls must return the same event object OR an equal id AND sig "
        "(got ids %r)" % (ids,))
    assert first is third, (
        "a call after an unrelated session must return the cached event object")
    assert len(sdk.calls) == 2, (
        "the cached wrap must not be re-signed: expected 2 constructor calls "
        "(session + unrelated), got %d" % len(sdk.calls))


# ---------------------------------------------------------------------------
# (b) sensitivity: differing in exactly one session field -> different id
# ---------------------------------------------------------------------------

SENSITIVE_FIELDS = (
    # (field, other value, does the canonical fingerprint change too?)
    ("session_id", "2608301440a40", True),
    ("seq", 8, True),
    ("preset_hash", "deadbeefcafe0002", True),
    ("stop", "stop-75m", True),
    ("t_ready_utc", 1789000060, True),
    ("type", "STARTED", True),
    ("recipient", OTHER_TX_NPUB, True),
    ("author", OTHER_AUTHOR, True),
    ("signer", OTHER_SIGNER, False),  # scopes the cache, not the canonical bytes
)


@pytest.mark.parametrize("field,other,fingerprint_changes", SENSITIVE_FIELDS,
                         ids=[entry[0] for entry in SENSITIVE_FIELDS])
@pytest.mark.asyncio
async def test_sensitivity_single_field_differs(install_sdk, field, other,
                                                fingerprint_changes):
    sdk = install_sdk()  # input-deterministic fake: ids differ iff inputs differ
    base = make_session()
    variant = make_session(**{field: other})

    base_fields, variant_fields = session_fields(base), session_fields(variant)
    differing = sorted(k for k in base_fields if base_fields[k] != variant_fields[k])
    assert differing == [field], (
        "fixture defect: the two sessions must differ in exactly %r, differ in %r"
        % (field, differing))

    first = await write_session(base)
    second = await write_session(variant)
    assert event_id(first) != event_id(second), (
        "session field %r did not change the kind-1059 event id - both %s "
        "(the wrap is insensitive to that field; spec %s §3/§9)"
        % (field, event_id(first), SPEC))

    if fingerprint_changes:
        assert session_fingerprint(base) != session_fingerprint(variant), (
            "session field %r did not change the canonical session fingerprint "
            "(spec %s §3.4)" % (field, SPEC))
    else:
        assert (sdk.calls[0]["signer_identity"]
                != sdk.calls[1]["signer_identity"]), (
            "session field %r must scope the wrap cache through the signer "
            "identity (spec %s §9.1)" % (field, SPEC))


# ---------------------------------------------------------------------------
# (c) the choke point emits kind 1059 and never the plaintext payload
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_choke_point_no_leakage(install_sdk):
    sdk = install_sdk()
    session = make_session()
    event = await write_session(session)

    view = gw.event_view(event)
    assert view["kind"] == 1059, (
        "the choke point must emit kind 1059, got %r" % (view["kind"],))
    assert view["kind"] == gw.KIND_GIFT_WRAP
    assert view["kind"] != 1, "the choke point must never emit a kind-1 event"
    assert view["kind"] != gw.KIND_PLAINTEXT_TALLY

    # no private/other construction ran: exactly one wrap, and it is the event.
    assert len(sdk.calls) == 1, "expected exactly one gift_wrap constructor call"
    assert sdk.calls[0]["event"] is event
    assert int(sdk.calls[0]["unsigned_event"].data["kind"]) == gw.INNER_KIND, (
        "the inner rumor kind must be INNER_KIND (%d), not a plaintext kind"
        % gw.INNER_KIND)

    content = str(view["content"])
    tag_text = " ".join(str(element) for tag in view["tags"] for element in tag)
    blob = canonical_event_json(event).decode("utf-8")

    for fragment in plaintext_fragments(session.payload):
        assert fragment not in content, (
            "plaintext payload fragment %r leaked into event content" % (fragment,))
        assert fragment not in tag_text, (
            "plaintext payload fragment %r leaked into a tag" % (fragment,))
        assert not re.search(re.escape(fragment), blob), (
            "plaintext payload fragment %r appears in the canonical event"
            % (fragment,))

    compact = json.dumps(session.payload, sort_keys=True, separators=(",", ":"))
    encoded = (
        ("hex", compact.encode("utf-8").hex()),
        ("base64", base64.b64encode(compact.encode("utf-8")).decode("ascii")),
        ("base64-unpadded", base64.b64encode(
            compact.encode("utf-8")).decode("ascii").rstrip("=")),
    )
    for label, needle in encoded:
        assert needle not in blob and needle not in content, (
            "the %s encoding of the plaintext payload leaked into the event "
            "(spec %s is silent on this; scanned as belt-and-braces)"
            % (label, SPEC))

    # cross-check with the module's own public leak guard
    assert gw.assert_no_plaintext_leak(event, session.payload) is True


# ---------------------------------------------------------------------------
# (d) no entropy anywhere on the derivation path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_entropy_in_derivation_path(install_sdk, monkeypatch):
    # Explicitly monkeypatch the sources the card names to raise, then prove the
    # choke point still returns successfully.
    install_entropy_guard(monkeypatch)
    sdk = install_sdk()
    event = await write_session(make_session())
    assert event is not None
    assert gw.event_view(event)["kind"] == 1059
    assert len(sdk.calls) == 1

    # Belt-and-braces: inspect the derivation functions named by the spec.
    for func in (gw.derive_ephemeral_secret_key, gw.derive_created_at,
                 gw.session_fingerprint, gw.canonical_session_bytes):
        source = _strip_comments_and_strings(inspect.getsource(func))
        for banned in ("os.urandom", "urandom", "secrets", "random"):
            assert banned not in source, (
                "%s references %r - any entropy in the derivation path breaks "
                "determinism (spec %s §6)" % (func.__name__, banned, SPEC))


# ---------------------------------------------------------------------------
# (e) created_at is the documented session-derived value, never the clock
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_created_at_derivation(install_sdk):
    sdk = install_sdk()
    session = make_session()

    # The spec §3.3 / §5 documented value for the canonical fixture.
    assert gw.derive_created_at(SPEC_PAYLOAD, TX_NPUB, author=AUTHOR,
                                created_at=None) == SPEC_CREATED_AT
    assert gw.build_inner_rumor(SPEC_PAYLOAD, TX_NPUB,
                                author=AUTHOR)["created_at"] == SPEC_CREATED_AT

    first = await write_session(session)
    second = await write_session(make_session())  # fresh objects, same fields
    assert len(sdk.calls) == 1, "the same session must not be re-signed"

    # Observed through the public choke point: the created_at it feeds the wrap
    # is the session-derived value, identical across two invocations.
    fed = [int(record["unsigned_event"].data["created_at"])
           for record in sdk.calls]
    assert fed == [SPEC_CREATED_AT], (
        "the choke point must feed the session-derived created_at %d into the "
        "wrap, got %r" % (SPEC_CREATED_AT, fed))

    # Spec §8 caveat: the *outer* kind-1059 created_at is minted by the pinned
    # nostr_sdk constructor, not by this derivation - so it is only asserted to
    # be stable here because the fake stands in for that constructor.
    assert event_field(first, "created_at") == event_field(second, "created_at"), (
        "two invocations of one session must agree on the outer created_at")
    assert int(event_field(first, "created_at")) == ENVELOPE_CREATED_AT, (
        "per spec %s §8 the outer created_at is the constructor's stamp, not the "
        "session-derived value" % SPEC)
    assert gw.derive_created_at(SPEC_PAYLOAD, TX_NPUB, author=AUTHOR,
                                created_at=None) == gw.derive_created_at(
        dict(reversed(list(SPEC_PAYLOAD.items()))), TX_NPUB, author=AUTHOR,
        created_at=None)


# ---------------------------------------------------------------------------
# Extra: the §3.3 byte-exact vector and the §4 labels (observed through the
# public choke point as well, so every test drives build_gift_wrap).
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_spec_3_3_byte_vector_and_labels(install_sdk):
    install_sdk()
    event = await write_session(make_session())
    assert gw.event_view(event)["kind"] == 1059

    canonical = gw.canonical_session_bytes(SPEC_PAYLOAD, TX_NPUB, author=AUTHOR,
                                           created_at=None)
    assert len(canonical) == SPEC_CANONICAL_LEN, (
        "canonical_session_bytes length must be %d, got %d"
        % (SPEC_CANONICAL_LEN, len(canonical)))
    assert canonical.decode("utf-8") == SPEC_CANONICAL_BYTES, (
        "canonical session serialization drifted from the spec §3.3 vector")
    assert hashlib.sha256(canonical).hexdigest() == SPEC_CANONICAL_SHA256

    assert gw.session_fingerprint(SPEC_PAYLOAD, TX_NPUB, author=AUTHOR,
                                  created_at=None) == SPEC_SESSION_FINGERPRINT
    assert gw.derive_ephemeral_secret_key(
        SPEC_PAYLOAD, TX_NPUB, author=AUTHOR,
        created_at=None) == SPEC_EPHEMERAL_SECRET

    assert gw.SESSION_DOMAIN_LABEL == SPEC_SESSION_DOMAIN_LABEL, (
        "the HMAC domain label was renamed or swapped (spec §4)")
    assert gw.EPHEMERAL_DOMAIN_LABEL == SPEC_EPHEMERAL_DOMAIN_LABEL, (
        "the HKDF domain label was renamed or swapped (spec §4)")

    # §3.3: dict insertion order is irrelevant; §3.2.6: npub and hex agree.
    reordered = {key: SPEC_PAYLOAD[key] for key in reversed(list(SPEC_PAYLOAD))}
    assert gw.canonical_session_bytes(reordered, TX_NPUB,
                                      author=AUTHOR) == canonical
    assert gw.canonical_session_bytes(SPEC_PAYLOAD, TX_HEX,
                                      author=AUTHOR) == canonical
