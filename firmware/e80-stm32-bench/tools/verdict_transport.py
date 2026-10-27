#!/usr/bin/env python3
"""verdict_transport.py — NIP-59 gift-wrapped verdict transport w/ relay failover.

Gate1 deliverable for the E80 bench CVM family. ``publish_verdict`` publishes a
completed config-scan VERDICT payload as a NIP-59 **gift-wrapped kind-1059**
event (NIP-44 sealed), addressed to the TX peer, over an ordered relay failover
set. It reuses the transport primitive of ``tools/cvm_board_server.py`` and never
re-implements the wrap or the relay client.

Contract (the Gate1 suite ``test_verdict_transport.py`` is the spec)::

    publish_verdict(payload_serializer, *, transport=None, env=None,
                    created_at=None, log=None) -> PublishResult

Design contract — reuse, don't re-invent
----------------------------------------
* **One wrap primitive.** The outer envelope comes from the SDK free function
  ``nostr_sdk.gift_wrap(signer, recipient_pk, unsigned_event)``; this module never
  hand-rolls a kind-1059 event and never signs anything itself.
* **Client via ClientBuilder + NostrSigner.keys**, exactly as
  ``cvm_board_server.py`` builds it (``nostr_sdk.ClientBuilder().signer(
  nostr_sdk.NostrSigner.keys(keys)).build()``); the relay set is added with
  ``add_relay(nostr_sdk.RelayUrl.parse(url))``.
* **Lazy SDK import.** ``nostr_sdk`` is imported INSIDE the publish path (never
  at module import time), so the module imports cleanly — and the Gate1 suite
  can inject a fake ``nostr_sdk`` via ``sys.modules``.
* **Keys strictly from the environment**, never from a parameter, never
  hardcoded. The client key MUST differ from the server key
  (:class:`KeyCollisionError`, raised before anything is wrapped or sent), and no
  key material ever reaches a log line, an exception message or stdout (masked).
* **HandleNotification-observed publish.** Success is reported from the relay
  ACK observed through the client's ``HandleNotification`` adapter
  (``/``handle_msg``), cross-checked against the SDK's ``SendEventOutput``
  (``success`` / ``failed``) — never fire-and-forget.
* **Failover.** Relays are attempted in ``FAILOVER_RELAYS`` order; a connect or
  publish failure logs a warning and advances to the next relay. It never aborts
  on the first failure; an aggregate error is raised only if every relay fails.

Relay set (EXACT — do not add, remove or reorder)
------------------------------------------------
``nostr.mom`` → ``relay.primal.net`` → ``nos.lol`` → ``relay2.contextvm.org`` →
``relay.nostr.band``. The unnumbered host of the contextvm relay family is DEAD
(verified 2026-08-23) and is filtered out of the active set by
:data:`DEAD_RELAYS`; it is never dialled and never appears in a URL the
transport is handed.

Run::

    P=/opt/miniconda/bin/python
    $P -m pytest firmware/e80-stm32-bench/tools/test_verdict_transport.py \\
        -k "wrap or leak or key or relay" -v
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import logging
import os
import sys
import time
from typing import Any, Mapping, Optional, Sequence

# Sibling imports — same convention as the other tools/ modules.
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

# Single source of truth for the relay failover set (see the module docstring of
# ``verdict_relay_constants``): the canonical list lives there and is re-exported
# below, so the value is never duplicated.
import verdict_relay_constants as _relay_constants  # noqa: E402

__all__ = [
    "KIND_GIFT_WRAP",
    "INNER_KIND",
    "KIND_PLAINTEXT_TALLY",
    "FAILOVER_RELAYS",
    "FAILOVER_RELAY_URLS",
    "DEAD_RELAYS",
    "ENV_CLIENT_NSEC",
    "ENV_CLIENT_HEX",
    "ENV_SERVER_NSEC",
    "ENV_SERVER_HEX",
    "ENV_TX_NPUB",
    "VerdictTransportError",
    "EnvKeyError",
    "KeyCollisionError",
    "PlaintextLeakError",
    "RelayPublishError",
    "RelayOutcome",
    "PublishResult",
    "npub_to_hex",
    "event_view",
    "assert_gift_wrap_kind",
    "assert_recipient_tag",
    "assert_no_plaintext_leak",
    "payload_fingerprints",
    "assert_keys_differ",
    "load_and_check_keys",
    "relay_transport_factory",
    "AckObserver",
    "NostrFailoverTransport",
    "publish_verdict",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: NIP-59 outer envelope kind (gift wrap).
KIND_GIFT_WRAP = 1059

#: Inner (sealed) content kind — the CVM JSON-RPC envelope used by
#: ``cvm_board_server.py``. It only ever travels encrypted inside the wrap.
INNER_KIND = 25910

#: The FORBIDDEN plaintext kind (plaintext tally — the RF recon leak from
#: ``docs/ADR-range-sync-cvm.md`` §Context). Never constructed here: this module
#: has exactly one wrap path and it is kind 1059.
KIND_PLAINTEXT_TALLY = 30315

#: Ordered relay failover set — EXACTLY these five bare hostnames, in order.
#: The unnumbered contextvm relay host is DEAD and must never appear here
#: (see :data:`DEAD_RELAYS`). The value is defined ONCE, in
#: :mod:`verdict_relay_constants`, and re-exported here as the single source of
#: truth (so a source scan of that defining module can prove the dead host is
#: absent from the relay list itself).
FAILOVER_RELAYS = _relay_constants.FAILOVER_RELAYS

#: The same set as ``wss://`` relay URLs (derived — never hand-maintained).
FAILOVER_RELAY_URLS = _relay_constants.FAILOVER_RELAY_URLS

#: Relays known DEAD (verified 2026-08-23). Filtered out of the active set, so a
#: caller cannot re-introduce one by passing it in.
DEAD_RELAYS = ("wss://relay.contextvm.org",)

#: Environment variable names — the ONLY key source (family-documented names).
ENV_CLIENT_NSEC = "CVM_RX_NSEC"
ENV_CLIENT_HEX = "CVM_RX_HEX"
ENV_SERVER_NSEC = "CVM_SERVER_NSEC"
ENV_SERVER_HEX = "CVM_SERVER_HEX"
ENV_TX_NPUB = "CVM_TX_NPUB"

#: Minimum length of a payload leaf value treated as leak-sensitive. Shorter
#: values (bool/int flags, "50m") are not fingerprinted from a Mapping payload:
#: a 3-char string can occur by chance inside a base64 ciphertext, and a false
#: positive would refuse a perfectly sealed envelope.
_LEAK_MIN_LEN = 3

#: Poll interval / default deadline for ACK observation.
_ACK_POLL_S = 0.05
DEFAULT_ACK_TIMEOUT_S = 5.0


class VerdictTransportError(RuntimeError):
    """Base class for every transport-level failure in this module."""


class EnvKeyError(VerdictTransportError, ValueError):
    """A required key/recipient environment variable is missing or malformed."""


class KeyCollisionError(VerdictTransportError):
    """The client key equals the server key — an unwrap-your-own-wraps hazard."""


class PlaintextLeakError(VerdictTransportError, AssertionError):
    """The outbound event would carry plaintext payload content."""


class RelayPublishError(VerdictTransportError):
    """No relay accepted the event (the only abort condition for a fan-out)."""

    def __init__(self, outcomes: Sequence["RelayOutcome"], message: str = ""):
        self.outcomes = list(outcomes)
        detail = "; ".join("%s: %s" % (o.host or o.url, o.reason or "failed")
                           for o in self.outcomes) or "no relay was attempted"
        super().__init__(message or "all %d relay(s) failed: %s"
                         % (len(self.outcomes), detail))


class RelayOutcome:
    """One relay's publish outcome."""

    __slots__ = ("host", "url", "accepted", "reason")

    def __init__(self, host: str, url: str = "", accepted: bool = False,
                 reason: str = ""):
        self.host = host
        self.url = url or host
        self.accepted = bool(accepted)
        self.reason = reason

    def __repr__(self):  # pragma: no cover - debug helper
        return "RelayOutcome(host=%r, accepted=%r, reason=%r)" % (
            self.host, self.accepted, self.reason)


# ---------------------------------------------------------------------------
# bech32 (BIP-173) — pure stdlib, so npub/nsec handling needs no SDK
# ---------------------------------------------------------------------------

_BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32_GENERATOR = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)


def _bech32_polymod(values):
    chk = 1
    for value in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ value
        for i in range(5):
            if (top >> i) & 1:
                chk ^= _BECH32_GENERATOR[i]
    return chk


def _bech32_hrp_expand(hrp):
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def _convertbits(data, frombits, tobits, pad=True):
    acc = 0
    bits = 0
    ret = []
    maxv = (1 << tobits) - 1
    for value in data:
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad and bits:
        ret.append((acc << (tobits - bits)) & maxv)
    return ret


def _bech32_decode_hex(hrp: str, value: str) -> str:
    """Decode a ``hrp1…`` bech32 string to 32-byte hex (checksum verified).

    Raises :class:`ValueError` — never returns a silently-wrong value — on a bad
    hrp, a character outside the charset, or a failed checksum. The offending
    value is NOT included in the message (it may be key material).
    """
    text = value.strip().lower()
    pos = text.rfind("1")
    if pos < 1:
        raise ValueError("bech32 string has no separator")
    if text[:pos] != hrp:
        raise ValueError("bech32 hrp is not %r" % (hrp,))
    try:
        data = [_BECH32_CHARSET.index(c) for c in text[pos + 1:]]
    except ValueError:
        raise ValueError("bech32 string has characters outside the charset")
    if len(data) < 7:
        raise ValueError("bech32 payload too short")
    if _bech32_polymod(_bech32_hrp_expand(hrp) + data) != 1:
        raise ValueError("bech32 checksum failed")
    raw = bytes(_convertbits(data[:-6], 5, 8, False))
    if len(raw) != 32:
        raise ValueError("bech32 payload is %d bytes, expected 32" % len(raw))
    return raw.hex()


def npub_to_hex(value: str) -> str:
    """``npub1…`` (bech32, checksum-verified) → 64-char lowercase hex pubkey.

    A 64-char hex pubkey is accepted unchanged (lower-cased). Implemented
    locally rather than via ``nostr_sdk.PublicKey.parse`` so the transport stays
    unit-testable without the SDK — the value produced is identical to what the
    SDK would produce (the Gate1 suite's fake ``PublicKey.parse`` is hex-strict
    precisely to pin this).
    """
    if not isinstance(value, str) or not value:
        raise EnvKeyError("recipient pubkey must be a non-empty string")
    text = value.strip()
    if text.lower().startswith("npub1"):
        try:
            return _bech32_decode_hex("npub", text)
        except ValueError as exc:
            raise EnvKeyError("recipient %s is not a valid npub: %s"
                              % (ENV_TX_NPUB, exc)) from None
    if len(text) != 64:
        raise EnvKeyError("%s is neither an npub1… nor a 64-char hex pubkey"
                          % (ENV_TX_NPUB,))
    try:
        int(text, 16)
    except ValueError:
        raise EnvKeyError("%s is not hex" % (ENV_TX_NPUB,)) from None
    return text.lower()


# ---------------------------------------------------------------------------
# Event inspection (nostr_sdk.Event | rumor | plain dict)
# ---------------------------------------------------------------------------

def _as_int(value) -> int:
    """kind → int, unwrapping the SDK's ``Kind`` Rust enum (``as_u16()``)."""
    if isinstance(value, bool):
        raise VerdictTransportError("boolean is not a nostr kind")
    as_u16 = getattr(value, "as_u16", None)
    if callable(as_u16):
        return int(as_u16())
    return int(value)


def _tag_view(tag) -> list:
    """Normalize one tag to a flat list of elements.

    The SDK's Rust ``Tag`` is NOT iterable: elements are reachable only through
    ``as_vec()`` (the same accessor ``cvm_board_server._extract_p_tag`` uses).
    Plain lists/tuples (unit-test fakes, dict events) pass through unchanged.
    """
    as_vec = getattr(tag, "as_vec", None)
    if callable(as_vec):
        return [str(element) for element in as_vec()]
    if isinstance(tag, (list, tuple)):
        return list(tag)
    try:
        return list(tag)
    except TypeError as exc:
        raise VerdictTransportError(
            "unsupported tag shape %r: a tag must be a list/tuple or expose "
            "as_vec() (nostr_sdk.Tag)" % (tag,)) from exc


def event_view(event) -> dict:
    """Normalize an event into ``{"kind": int, "tags": [[str, …]], "content": str}``.

    Accepts a ``nostr_sdk.Event`` (``kind()``/``tags()``/``content()``), any
    rumor-like object exposing the same methods, or a plain mapping. Every guard
    reads only this view, so it is SDK-agnostic and testable.
    """
    if isinstance(event, Mapping):
        view = dict(event)
        if "kind" in view:
            view["kind"] = _as_int(view["kind"])
        view["tags"] = [_tag_view(t) for t in view.get("tags", [])]
        view["content"] = view.get("content", "") or ""
        return view

    view: dict = {}
    kind_fn = getattr(event, "kind", None)
    view["kind"] = _as_int(kind_fn()) if callable(kind_fn) else None
    tags_fn = getattr(event, "tags", None)
    tags = []
    if callable(tags_fn):
        raw = tags_fn()
        if hasattr(raw, "to_vec"):
            raw = raw.to_vec()
        tags = [_tag_view(t) for t in raw]
    view["tags"] = tags
    content_fn = getattr(event, "content", None)
    view["content"] = str(content_fn()) if callable(content_fn) else ""
    return view


def _tag_strings(view: Mapping) -> list:
    strings = []
    for tag in view.get("tags", []):
        for element in tag:
            strings.append(str(element))
    return strings


# ---------------------------------------------------------------------------
# Guards — the hard guarantee that only a sealed kind-1059 event goes out
# ---------------------------------------------------------------------------

def assert_gift_wrap_kind(event, *, context: str = "emit") -> dict:
    """HARD GUARD: only kind 1059 may pass. Raise — never downgrade.

    Any other kind raises :class:`PlaintextLeakError` with the offending kind
    named, so a caller cannot mistake a rejected plaintext event for a delivered
    one. Returns the normalized event view.
    """
    view = event_view(event)
    kind = view.get("kind")
    if kind != KIND_GIFT_WRAP:
        raise PlaintextLeakError(
            "refusing to {context} a non-NIP-59 event: got kind {kind!r}, "
            "expected kind {wrap} (KIND_GIFT_WRAP). A plaintext kind "
            "({plain}) must never be emitted (ADR-range-sync-cvm.md context)."
            .format(context=context, kind=kind, wrap=KIND_GIFT_WRAP,
                    plain=KIND_PLAINTEXT_TALLY))
    return view


def assert_recipient_tag(event, tx_npub: str) -> str:
    """Assert the outer ``p`` tag addresses ``tx_npub``; returns hex pubkey.

    A missing ``p`` tag or a mismatch raises :class:`PlaintextLeakError` — the
    event must never be emitted to the wrong recipient.
    """
    expected = npub_to_hex(tx_npub)
    ptags = [tag[1] for tag in event_view(event).get("tags", [])
             if len(tag) > 1 and str(tag[0]) == "p"]
    if not ptags:
        raise PlaintextLeakError(
            "outer gift wrap carries no 'p' tag: expected p=%s (TX npub)"
            % expected)
    for tag_value in ptags:
        if str(tag_value).lower() != expected:
            raise PlaintextLeakError(
                "outer gift wrap 'p' tag does not address the TX npub — "
                "refusing to emit to the wrong recipient")
    return expected


def _leaf_values(obj):
    if isinstance(obj, Mapping):
        for value in obj.values():
            yield from _leaf_values(value)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for item in obj:
            yield from _leaf_values(item)
    else:
        yield obj


def payload_fingerprints(payload) -> tuple:
    """Every string that must NOT appear in plaintext in the outer event.

    For a Mapping payload: the full JSON serialization (in each spelling a
    caller might have produced) plus every leaf value of at least
    :data:`_LEAK_MIN_LEN` characters. Counter-proof of the wrap is the job of
    the wrap tests (the payload reaches the wrap primitive): the property here
    is about the WIRE artifact, which must carry only NIP-44 ciphertext.

    For a payload the caller already serialized (the documented interface —
    ``payload_serializer`` returns the payload), only whole-payload variants are
    fingerprinted; a short arbitrary substring of the payload is not a
    meaningful leak signature and would false-positive inside a base64 blob.
    """
    fingerprints = set()
    if isinstance(payload, str):
        if len(payload) >= _LEAK_MIN_LEN:
            fingerprints.add(payload)
        return tuple(sorted(fingerprints))
    for kwargs in ({}, {"sort_keys": True},
                   {"sort_keys": True, "separators": (",", ":")},
                   {"separators": (",", ":")}):
        try:
            fingerprints.add(json.dumps(payload, **kwargs))
        except (TypeError, ValueError):
            pass
    for leaf in _leaf_values(payload):
        text = str(leaf)
        if len(text) >= _LEAK_MIN_LEN:
            fingerprints.add(text)
    return tuple(sorted(fingerprints))


def assert_no_plaintext_leak(event, payload, *, context: str = "emit") -> bool:
    """Assert no plaintext payload fragment is visible in the outer event.

    Scans every tag value and the content field. A hit raises
    :class:`PlaintextLeakError`: a kind-1059 envelope must carry only NIP-44
    ciphertext. The fragment itself is named (it is payload data the operator
    must be able to diagnose); no key material passes through here.
    """
    view = event_view(event)
    haystacks = [("content", str(view.get("content", "")))]
    haystacks += [("tag", text) for text in _tag_strings(view)]
    for fingerprint in payload_fingerprints(payload):
        for where, haystack in haystacks:
            if fingerprint in haystack:
                raise PlaintextLeakError(
                    "plaintext payload leak in the outer gift wrap ({0}): a "
                    "payload fragment of {1} chars appears in {2} — a kind-1059 "
                    "envelope must carry only NIP-44 ciphertext"
                    .format(context, len(fingerprint), where))
    return True


# ---------------------------------------------------------------------------
# Keys — environment only, collision-checked, never logged
# ---------------------------------------------------------------------------

def _mask(value: str) -> str:
    """Redact a secret for any diag string (never emit key material)."""
    if not isinstance(value, str) or not value:
        return "<unset>"
    if len(value) <= 8:
        return "<redacted>"
    return "%s…%s (%d chars)" % (value[:3], value[-2:], len(value))


def _env_lookup(env: Optional[Mapping[str, str]], name: str):
    source = os.environ if env is None else env
    value = source.get(name)
    if isinstance(value, str):
        value = value.strip()
    return value


def _secret_hex(name: str, raw: str) -> str:
    """Normalize an nsec1… or 64-char hex secret to lowercase hex.

    Raises :class:`EnvKeyError` naming the variable — the value is never echoed.
    """
    text = raw.strip()
    if text.lower().startswith("nsec1"):
        try:
            return _bech32_decode_hex("nsec", text)
        except ValueError as exc:
            raise EnvKeyError("environment variable %s is not a valid nsec (%s)"
                              % (name, exc)) from None
    if len(text) == 64:
        try:
            int(text, 16)
        except ValueError:
            pass
        else:
            return text.lower()
    raise EnvKeyError("environment variable %s is neither a 64-char hex nor an "
                      "nsec1… secret" % (name,))


def _resolve_secret(env: Optional[Mapping[str, str]],
                    names: Sequence[str], label: str) -> tuple:
    """First present+non-empty var among ``names`` → ``(env_name, hex_secret)``."""
    for name in names:
        raw = _env_lookup(env, name)
        if raw:
            return name, _secret_hex(name, raw)
    raise EnvKeyError(
        "missing required environment variable: %s (%s secret is not set). "
        "Keys come from the environment only — no CLI argument and no fallback "
        "is accepted." % (names[0], label))


def assert_keys_differ(client_secret, server_secret) -> bool:
    """The single collision predicate: client key MUST differ from server key.

    Raises :class:`KeyCollisionError` when the two secrets are the same key.
    The message names the ROLE, never the material.
    """
    same = (str(client_secret).strip().lower() == str(server_secret).strip()
            .lower())
    if same:
        raise KeyCollisionError(
            "client key equals the server key: the RX client key (%s) and the "
            "board server key (%s) must be distinct identities, otherwise the "
            "client unwraps its own gift wraps. Refusing to publish."
            % (ENV_CLIENT_NSEC, ENV_SERVER_NSEC))
    return True


def _resolve_key_pair(env: Optional[Mapping[str, str]]) -> dict:
    """Resolve the client/server/tx identity triple from the environment only.

    Returns ``{"client_hex", "client_env", "server_hex", "server_env",
    "tx_hex", "tx_env"}``. Raises :class:`EnvKeyError` (missing) or
    :class:`KeyCollisionError` (client == server) BEFORE anything is wrapped.
    """
    client_env, client_hex = _resolve_secret(
        env, (ENV_CLIENT_NSEC, ENV_CLIENT_HEX), "client")
    server_env, server_hex = _resolve_secret(
        env, (ENV_SERVER_NSEC, ENV_SERVER_HEX), "server")
    assert_keys_differ(client_hex, server_hex)
    tx_env, tx_raw = None, None
    for name in (ENV_TX_NPUB,):
        raw = _env_lookup(env, name)
        if raw:
            tx_env, tx_raw = name, raw
            break
    if not tx_raw:
        raise EnvKeyError(
            "missing required environment variable: %s (TX recipient npub is "
            "not set). Keys come from the environment only." % (ENV_TX_NPUB,))
    return {
        "client_hex": client_hex,
        "client_env": client_env,
        "server_hex": server_hex,
        "server_env": server_env,
        "tx_env": tx_env,
        "tx_hex": npub_to_hex(tx_raw),
    }


def load_and_check_keys(env: Optional[Mapping[str, str]] = None) -> tuple:
    """Env-only key loading + collision check → ``(client_hex, server_hex)``.

    The CLI exposes no key-bearing option by design: this is the one entry point
    that reads key material, and it reads it from the environment alone.
    """
    resolved = _resolve_key_pair(env)
    return resolved["client_hex"], resolved["server_hex"]


# ---------------------------------------------------------------------------
# Wrap payload construction
# ---------------------------------------------------------------------------

def _import_nostr_sdk():
    """Import ``nostr_sdk`` lazily, inside the publish path.

    Never a module-level import: the suite injects a fake module via
    ``sys.modules``, and the module must import cleanly in a bare image.
    """
    return importlib.import_module("nostr_sdk")


def _keys_pubkey_hex(keys) -> str:
    """Best-effort hex pubkey of a keys object (real SDK or a test double).

    The real path is ``keys.public_key().to_hex()``. A double that cannot expose
    a pubkey (the Gate1 fake's ``Keys.parse`` returns a plain dict) yields ``""``
    rather than crashing the publish.
    """
    for attr in ("public_key", "public_key_hex"):
        value = getattr(keys, attr, None)
        if value is None:
            continue
        if isinstance(value, str):
            return value.lower()
        if callable(value):
            try:
                got = value()
            except Exception:
                continue
            if isinstance(got, str):
                return got.lower()
            to_hex = getattr(got, "to_hex", None)
            if callable(to_hex):
                try:
                    return str(to_hex()).lower()
                except Exception:
                    continue
    return ""


def _content_str(serialized: Any) -> str:
    """The serialized payload as the rumor content string.

    ``payload_serializer`` returns the payload; a ``str`` return travels verbatim
    (the caller owns serialization — pinned by the wrap tests), any other JSON
    value is serialized here as the last resort.
    """
    if isinstance(serialized, str):
        return serialized
    if isinstance(serialized, (bytes, bytearray)):
        return serialized.decode("utf-8")
    return json.dumps(serialized)


def build_verdict_rumor(serialized: Any, tx_hex: str, *,
                        author_hex: str = "",
                        created_at: Optional[int] = None,
                        nostr_sdk=None) -> Any:
    """Build the sealed inner rumor (``UnsignedEvent``) carrying the payload.

    Content is the serializer's exact return value; the inner kind is
    :data:`INNER_KIND`; the rumor is addressed to the TX peer by ``p`` tag.
    """
    module = nostr_sdk or _import_nostr_sdk()
    content = _content_str(serialized)
    if created_at is None:
        created_at = int(time.time())
    inner = {
        "pubkey": str(author_hex or ""),
        "kind": INNER_KIND,
        "tags": [["p", str(tx_hex)]],
        "content": content,
        "created_at": int(created_at),
    }
    return module.UnsignedEvent.from_json(json.dumps(inner))


def signer_from_keys(keys, *, nostr_sdk=None):
    """``NostrSigner.keys(keys)`` — the ``cvm_board_server`` shape.

    ``keys`` may be a ``nostr_sdk.Keys`` object (preferred — the exact
    ``cvm_board_server.CVMBoardServer`` construction) or the raw secret the SDK
    ``Keys.parse`` accepts. A parse failure of the raw secret is an env-key
    problem and raises :class:`EnvKeyError` (no material echoed).
    """
    module = nostr_sdk or _import_nostr_sdk()
    if not isinstance(keys, type) and hasattr(keys, "public_key"):
        return module.NostrSigner.keys(keys)
    try:
        keys_obj = module.Keys.parse(keys)
    except Exception as exc:
        raise EnvKeyError("the configured secret is not a usable nostr key "
                          "(%s) — check the key environment variables"
                          % type(exc).__name__) from None
    return module.NostrSigner.keys(keys_obj)


def _keys_to_object(keys, module):
    """``keys`` → a Keys object (parse when handed a raw secret)."""
    if not isinstance(keys, type) and hasattr(keys, "public_key"):
        return keys
    try:
        return module.Keys.parse(keys)
    except Exception as exc:
        raise EnvKeyError("the configured secret is not a usable nostr key "
                          "(%s) — check the key environment variables"
                          % type(exc).__name__) from None


async def build_gift_wrap(serialized: Any, tx_npub: str, keys: str,
                          *, created_at: Optional[int] = None,
                          nostr_sdk=None):
    """Wrap a serialized verdict payload as a signed NIP-59 kind-1059 event.

    Reuses the ``cvm_board_server.py`` primitive verbatim:
    ``UnsignedEvent.from_json`` + ``await nostr_sdk.gift_wrap(signer, recipient,
    unsigned)``. The guard set runs on the produced event before it is returned,
    so a plaintext or mis-addressed wrap can never reach the publisher.
    """
    module = nostr_sdk or _import_nostr_sdk()
    recipient_hex = npub_to_hex(tx_npub)
    keys_obj = _keys_to_object(keys, module)
    signer = module.NostrSigner.keys(keys_obj)
    rumor = build_verdict_rumor(serialized, recipient_hex,
                                author_hex=_keys_pubkey_hex(keys_obj),
                                created_at=created_at, nostr_sdk=module)
    recipient = module.PublicKey.parse(recipient_hex)
    event = module.gift_wrap(signer, recipient, rumor)
    if inspect.isawaitable(event):
        event = await event
    assert_gift_wrap_kind(event, context="build")
    assert_recipient_tag(event, recipient_hex)
    assert_no_plaintext_leak(event, serialized, context="build")
    return event, rumor, signer


# ---------------------------------------------------------------------------
# HandleNotification — observe the publish ACK
# ---------------------------------------------------------------------------

def _event_id_hex(event) -> Optional[str]:
    """Hex id of an event double, or None when it cannot be read."""
    id_fn = getattr(event, "id", None)
    if callable(id_fn):
        try:
            got = id_fn()
        except Exception:
            return None
        to_hex = getattr(got, "to_hex", None)
        if callable(to_hex):
            try:
                return str(to_hex()).lower()
            except Exception:
                return None
        return str(got).lower() if got is not None else None
    if isinstance(event, Mapping):
        value = event.get("id")
        return str(value).lower() if value else None
    return None


def _host_of(url: Any) -> str:
    """Bare lowercase host of a relay URL or host string ('' when empty)."""
    if url is None:
        return ""
    text = str(url).strip().lower()
    if "://" in text:
        text = text.split("://", 1)[1]
    text = text.split("/", 1)[0]
    return text


def _relay_message_fields(message) -> tuple:
    """Normalize a RelayMessage/RelayMessageEnum double → ``(variant, fields)``.

    ``variant`` is a lowercase token (``ok``/``closed``/``notice``/``event``…),
    ``fields`` the variant's mapping when readable.
    """
    if message is None:
        return "", {}
    if isinstance(message, Mapping):
        variant = str(message.get("type") or message.get("variant") or "").lower()
        return variant, dict(message)
    as_enum = getattr(message, "as_enum", None)
    if callable(as_enum):
        try:
            message = as_enum()
        except Exception:
            pass
    is_ok = getattr(message, "is_ok", None)
    if callable(is_ok):
        try:
            if is_ok():
                return "ok", _fields_of(message)
        except Exception:
            pass
    for variant in ("closed", "notice", "event", "auth", "count",
                    "end_of_stored_events"):
        predicate = getattr(message, "is_%s" % variant, None)
        if callable(predicate):
            try:
                if predicate():
                    return variant, _fields_of(message)
            except Exception:
                continue
    return "", _fields_of(message)


def _fields_of(message) -> dict:
    fields = {}
    for name in ("event_id", "status", "message", "content", "subscription_id"):
        value = getattr(message, name, None)
        if value is None or callable(value):
            continue
        fields[name] = value
    if isinstance(message, Mapping):
        fields.update(message)
    return fields


class AckObserver:
    """``HandleNotification`` adapter that observes relay ACKs for one publish.

    Copy of the ``cvm_board_server._NotificationHandler`` shape (the uniffi trait
    calls ``handle(relay_url, subscription_id, event)`` and ``handle_msg(relay_url,
    msg)``): every notification is recorded, and an ``OK`` message for the
    published event id settles that relay's outcome. The task never awaits the
    trait call's slow work, so the notification loop keeps draining.
    """

    def __init__(self, event_id: Optional[str] = None, *, log=None):
        self.event_id = (str(event_id).lower() if event_id else None)
        self.log = log or _default_log()
        self.relay_acks: dict = {}       # host -> True (accepted)
        self.relay_messages: dict = {}   # host -> ack/refusal text
        self.messages_seen = 0
        self.events_seen = 0
        self.errors = []

    # --- Helpers ---------------------------------------------------------

    def _own_event(self, event_id) -> bool:
        if not self.event_id:
            return True
        text = str(event_id).lower() if event_id is not None else ""
        to_hex = getattr(event_id, "to_hex", None)
        if callable(to_hex):
            try:
                text = str(to_hex()).lower()
            except Exception:
                pass
        return text == self.event_id

    def accepted_hosts(self) -> list:
        return [host for host, ok in self.relay_acks.items() if ok]

    def rejected_hosts(self) -> list:
        return [host for host, ok in self.relay_acks.items() if not ok]

    def settled(self, hosts: Sequence[str]) -> bool:
        """True when every candidate host has answered (or there are none)."""
        wanted = {_host_of(h) for h in hosts}
        wanted.discard("")
        if not wanted:
            return bool(self.relay_acks)
        return wanted.issubset(set(self.relay_acks))

    # --- HandleNotification trait ---------------------------------------

    async def handle(self, relay_url, subscription_id, event):
        """An incoming EVENT_MSG. Not an ACK — recorded for completeness."""
        self.events_seen += 1
        return None

    async def handle_msg(self, relay_url, msg):
        """An incoming relay message (OK / CLOSED / NOTICE / …)."""
        host = _host_of(relay_url)
        variant, fields = _relay_message_fields(msg)
        self.messages_seen += 1
        if variant == "ok":
            if not self._own_event(fields.get("event_id")):
                return None
            accepted = bool(fields.get("status", True))
            self.relay_acks[host] = accepted
            self.relay_messages[host] = str(fields.get("message") or "")
        elif variant in ("closed", "notice"):
            text = str(fields.get("message") or "")
            if host and host not in self.relay_acks:
                self.relay_acks[host] = False
                self.relay_messages[host] = "%s: %s" % (variant, text)
            self.log.warning("[verdict-transport] relay %s %s: %s",
                             host or "?", variant, text or "no detail")
        return None


# ---------------------------------------------------------------------------
# Failover transport — ordered connect + publish, per-relay isolation
# ---------------------------------------------------------------------------

def _default_log() -> logging.Logger:
    """Module logger. Messages never contain key material or payload data."""
    return logging.getLogger("verdict_transport")


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


class _RecordingTransport:
    """Typed in-process transport used when the SDK client is unavailable.

    It is NOT a dead end: it records the wrap and reports the canonical hosts as
    sent, so the caller still gets a truthful ``relay_results`` view. The live
    path is :class:`NostrFailoverTransport`.
    """

    def __init__(self, urls, *, log=None):
        self.urls = list(urls)
        self.log = log or _default_log()
        self.sent = []
        self.relay_results = {_host_of(u): "not-sent" for u in self.urls}

    async def send_event(self, event):
        self.sent.append(event)
        return {"accepted": 0, "relay_results": dict(self.relay_results),
                "event_id": _event_id_hex(event), "ok": False}


class NostrFailoverTransport:
    """Publish one gift-wrapped event over the ordered relay set, failover-safe.

    Connects with the ``cvm_board_server`` client construction
    (``ClientBuilder().signer(NostrSigner.keys(keys)).build()``) and adds every
    relay by iterating :data:`FAILOVER_RELAYS` order: a relay that fails to add
    or connect logs a warning and the fan-out advances to the next one — the
    first failure never aborts. The publish result is observed through a
    :class:`AckObserver` (``HandleNotification``) and cross-checked against the
    SDK's ``SendEventOutput``, so success is reported from an ACK, never from a
    fire-and-forget send.
    """

    def __init__(self, urls=None, *, env: Optional[Mapping[str, str]] = None,
                 log=None, signer=None, client_factory=None,
                 ack_timeout: float = DEFAULT_ACK_TIMEOUT_S):
        self.urls = _active_urls(urls)
        self.env = env
        self.log = log or _default_log()
        self.signer = signer
        self.client_factory = client_factory
        self.ack_timeout = ack_timeout
        self.relay_results = {_host_of(u): "pending" for u in self.urls}
        self.connected_relays: list = []
        self.outcomes: list = []
        self.ack_observer: Optional[AckObserver] = None
        self.client: Any = None

    # --- wiring ----------------------------------------------------------

    def set_signer(self, signer):
        """Hand the already-built signer to the transport (reuse, not re-derive)."""
        self.signer = signer
        return self

    # --- client ----------------------------------------------------------

    async def _ensure_client(self):
        if self.client is not None:
            return self.client
        if self.client_factory is not None:
            self.client = await _maybe_await(self.client_factory(self))
            return self.client
        nostr_sdk = _import_nostr_sdk()
        builder = nostr_sdk.ClientBuilder()
        signer_fn = getattr(builder, "signer", None)
        if self.signer is not None and callable(signer_fn):
            builder = signer_fn(self.signer)
        client = builder.build()
        for url in self.urls:
            host = _host_of(url)
            try:
                added = await _maybe_await(
                    client.add_relay(nostr_sdk.RelayUrl.parse(url)))
            except Exception as exc:  # per-relay isolation: never abort
                self.relay_results[host] = "add-failed: %s" % type(exc).__name__
                self.log.warning(
                    "[verdict-transport] relay %s add failed (%s) — trying the "
                    "next relay", host, type(exc).__name__)
                continue
            if added is False:
                self.relay_results[host] = "add-rejected"
                self.log.warning(
                    "[verdict-transport] relay %s was not added by the client — "
                    "trying the next relay", host)
                continue
            self.connected_relays.append(url)
            self.relay_results[host] = "connected"
        try:
            await _maybe_await(client.connect())
        except Exception as exc:  # the pool still holds whatever connected
            self.log.warning("[verdict-transport] connect() error (%s) — "
                             "continuing with %d relay(s)",
                             type(exc).__name__, len(self.connected_relays))
        self.client = client
        return client

    async def _start_observer(self, client, observer):
        """Start the notification loop (never fatal to the publish)."""
        handle_notifications = getattr(client, "handle_notifications", None)
        if not callable(handle_notifications):
            return None
        try:
            task = asyncio.ensure_future(
                _maybe_await(handle_notifications(observer)))
        except Exception as exc:
            self.log.warning("[verdict-transport] could not start the "
                             "notification observer (%s)", type(exc).__name__)
            return None
        return task

    async def _stop_observer(self, client, task):
        if task is not None:
            task.cancel()
            try:
                await task  # retrieve the outcome: cancelled OR already failed
            except (asyncio.CancelledError, Exception):
                pass
        shutdown = getattr(client, "shutdown", None)
        if callable(shutdown):
            try:
                await _maybe_await(shutdown())
            except Exception:
                pass
        self.client = None

    # --- publish ---------------------------------------------------------

    async def _collect_acks(self, observer: AckObserver) -> None:
        """Wait (bounded) for relay ACKs — an ACK is the success evidence."""
        deadline = time.monotonic() + self.ack_timeout
        while time.monotonic() < deadline:
            if observer.accepted_hosts():
                return
            if observer.settled(self.urls):
                return
            await asyncio.sleep(_ACK_POLL_S)

    def _record(self, output, observer: AckObserver) -> None:
        """Fold the SDK output + observed ACKs into per-relay outcomes."""
        accepted: dict = {}
        failed: dict = {}
        if output is not None:
            success = getattr(output, "success", None)
            if success is None and isinstance(output, Mapping):
                success = output.get("success")
            for url in success or []:
                accepted[_host_of(url)] = ""
            raw_failed = getattr(output, "failed", None)
            if raw_failed is None and isinstance(output, Mapping):
                raw_failed = output.get("failed")
            if isinstance(raw_failed, Mapping):
                for url, reason in raw_failed.items():
                    failed[_host_of(url)] = str(reason or "rejected")
            elif raw_failed:
                for url in raw_failed:
                    failed[_host_of(url)] = "rejected"
        for host, ok in observer.relay_acks.items():
            if ok:
                accepted.setdefault(host, observer.relay_messages.get(host, ""))
            elif host not in accepted:
                failed.setdefault(host, observer.relay_messages.get(host)
                                  or "refused")
        no_evidence = not accepted and not failed
        for url in self.urls:
            host = _host_of(url)
            if host in accepted:
                self.relay_results[host] = "accepted"
            elif host in failed:
                self.relay_results[host] = "failed: %s" % failed[host]
            elif no_evidence:
                # Nothing to disprove the send; report it as sent, not accepted.
                self.relay_results[host] = "sent (no ack observed)"
        self.outcomes = [
            RelayOutcome(host=_host_of(url), url=url,
                         accepted=(_host_of(url) in accepted),
                         reason="" if _host_of(url) in accepted
                         else failed.get(_host_of(url), ""))
            for url in self.urls]

    async def send_event(self, event):
        """Publish ``event`` and return the per-relay result mapping.

        Returns ``{"accepted": n, "relay_results": {host: status}, "ok": bool,
        "event_id": hex, "outcomes": [RelayOutcome, …]}`` — ``ok`` is True iff at
        least one relay ACKed (or the SDK reported at least one success).
        """
        client = await self._ensure_client()
        observer = AckObserver(_event_id_hex(event), log=self.log)
        self.ack_observer = observer
        task = await self._start_observer(client, observer)
        send_error = ""
        output = None
        try:
            send_event = getattr(client, "send_event", None)
            if not callable(send_event):
                send_error = "client exposes no send_event()"
            else:
                output = await _maybe_await(send_event(event))
            await self._collect_acks(observer)
        except Exception as exc:
            send_error = "%s: %s" % (type(exc).__name__, exc)
            self.log.warning("[verdict-transport] publish error over the relay "
                             "pool (%s)", type(exc).__name__)
        finally:
            await self._stop_observer(client, task)
        self._record(output, observer)
        ok = bool(observer.accepted_hosts()) or any(
            o.accepted for o in self.outcomes)
        if send_error and not ok:
            self.outcomes = [RelayOutcome(host=_host_of(u), url=u,
                                          accepted=False, reason=send_error)
                             for u in self.urls]
            self.relay_results = {_host_of(u): "failed: %s" % send_error
                                  for u in self.urls}
        return {
            "accepted": len([o for o in self.outcomes if o.accepted]),
            "relay_results": dict(self.relay_results),
            "ok": ok,
            "event_id": _event_id_hex(event),
            "outcomes": list(self.outcomes),
        }


def _active_urls(urls=None) -> list:
    """The ordered active relay URLs — canonical set minus any DEAD relay.

    The canonical :data:`FAILOVER_RELAY_URLS` is used when ``urls`` is None.
    Whatever is supplied keeps its order; only DEAD relays are dropped, so a
    caller can neither re-introduce the dead host nor lose a live one.
    """
    candidates = list(FAILOVER_RELAY_URLS if urls is None else urls)
    dead = {_host_of(u) for u in DEAD_RELAYS}
    active = []
    for url in candidates:
        host = _host_of(url)
        if not host or host in dead or host in active:
            continue
        active.append(url if "://" in str(url) else "wss://" + str(url))
    return active


def relay_transport_factory(urls=None, env: Optional[Mapping[str, str]] = None):
    """Build the module's default relay fan-out (the documented seam).

    ``publish_verdict`` calls this when no ``transport`` is injected; the tests
    monkeypatch it to observe the relay set without a socket. Falls back to the
    in-process recorder when the SDK is unavailable, so the module stays usable
    (and importable) offline.
    """
    active = _active_urls(urls)
    try:
        _import_nostr_sdk()
    except Exception as exc:  # pragma: no cover - optional dependency
        _default_log().warning(
            "[verdict-transport] nostr_sdk unavailable (%s); using the "
            "in-process transport", type(exc).__name__)
        return _RecordingTransport(active)
    return NostrFailoverTransport(active, env=env)


# ---------------------------------------------------------------------------
# The published result
# ---------------------------------------------------------------------------

class PublishResult:
    """What ``publish_verdict`` returns.

    ``event``   the outbound kind-1059 gift wrap (what reached the wire),
    ``rumor``   the sealed inner event (plaintext BY DESIGN — it is what the
                wrap seals; it must never be inspected as an outbound layer),
    ``relay_results`` per-relay outcome view (host → status).
    """

    def __init__(self, event, rumor, relay_results, *, relay_urls=(),
                 outcomes=(), serializer_output=None, log=None):
        self.event = event
        self.rumor = rumor
        self.inner = rumor
        self.relay_results = dict(relay_results or {})
        self.relay_urls = list(relay_urls or ())
        self.outcomes = list(outcomes or ())
        self.serializer_output = serializer_output
        self.log = log

    @property
    def event_id(self) -> Optional[str]:
        return _event_id_hex(self.event)

    @property
    def accepted_relays(self) -> list:
        return [h for h, status in self.relay_results.items()
                if status == "accepted"]

    def as_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "kind": KIND_GIFT_WRAP,
            "inner_kind": INNER_KIND,
            "relay_results": dict(self.relay_results),
            "relay_urls": list(self.relay_urls),
        }

    def __repr__(self):  # pragma: no cover - debug helper
        return "PublishResult(event_id=%r, relays=%r)" % (
            self.event_id, self.relay_results)


def _coerce_publish_response(raw, transport, urls) -> tuple:
    """Normalize a transport's send response → ``(relay_results, ok_or_None)``."""
    relay_results = None
    ok = None
    if isinstance(raw, Mapping):
        inner = raw.get("relay_results")
        if isinstance(inner, Mapping) and inner:
            relay_results = dict(inner)
        if "ok" in raw:
            ok = bool(raw["ok"])
    if relay_results is None:
        attr = getattr(transport, "relay_results", None)
        if isinstance(attr, Mapping) and attr:
            relay_results = dict(attr)
    if relay_results is None and isinstance(raw, Mapping):
        relay_results = {str(k): str(v) for k, v in raw.items()
                         if not isinstance(v, (list, tuple, dict))}
    if relay_results is None:
        relay_results = {_host_of(u): "unknown" for u in _active_urls(urls)}
    return relay_results, ok


def _outcomes_from(raw, transport) -> list:
    if isinstance(raw, Mapping) and raw.get("outcomes"):
        return list(raw["outcomes"])
    return list(getattr(transport, "outcomes", []) or [])


def _mask_env_report(resolved: Mapping, env) -> str:
    """A safe one-line identity report — roles and ENV NAMES only, no material."""
    return ("client=%s server=%s recipient=%s (keys from the environment only)"
            % (resolved["client_env"], resolved["server_env"],
               resolved["tx_env"]))


# ---------------------------------------------------------------------------
# publish_verdict — the documented entry point
# ---------------------------------------------------------------------------

def publish_verdict(payload_serializer, *, transport=None, env=None,
                    created_at=None, log=None):
    """Publish a verdict payload as a gift-wrapped kind-1059 event (failover).

    ``payload_serializer`` is a zero-argument callable the CALLER owns: its exact
    return value becomes the sealed rumor content. Keys are read from the
    environment (client key ≠ server key), and the event is sent over
    ``transport`` — or, when ``transport`` is None, over the module's own
    failover fan-out built from :data:`FAILOVER_RELAY_URLS` by
    :func:`relay_transport_factory`.

    Returns a :class:`PublishResult`; raises :class:`EnvKeyError` (missing/
    malformed key or recipient), :class:`KeyCollisionError` (client == server)
    or :class:`RelayPublishError` (every relay failed).

    May be awaited or called synchronously — the asynchronous publish is run to
    completion when no event loop is running.
    """
    coro = _publish_verdict_async(payload_serializer, transport=transport,
                                  env=env, created_at=created_at, log=log)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    return coro


async def _publish_verdict_async(payload_serializer, *, transport=None,
                                 env=None, created_at=None, log=None):
    logger = log if log is not None and hasattr(log, "warning") \
        else _default_log()
    if not callable(payload_serializer):
        raise EnvKeyError("payload_serializer must be a zero-argument callable "
                          "returning the verdict payload")

    # 1. Keys/recipient — environment only, collision checked BEFORE any wrap.
    resolved = _resolve_key_pair(env)

    # 2. Serialize the payload (exactly once — the caller owns serialization).
    serialized = payload_serializer()
    if serialized is None:
        raise PlaintextLeakError("payload_serializer returned None: refusing to "
                                 "publish an empty verdict")

    # 3. Wrap: the SDK gift_wrap primitive is the ONLY kind-1059 construction.
    nostr_sdk = _import_nostr_sdk()
    event, rumor, signer = await build_gift_wrap(
        serialized, resolved["tx_hex"], resolved["client_hex"],
        created_at=created_at, nostr_sdk=nostr_sdk)

    # 4. Failover transport (module default when none was injected).
    fanout = transport
    if fanout is None:
        urls = _active_urls(None)
        fanout = relay_transport_factory(urls, env=env)
        setter = getattr(fanout, "set_signer", None)
        if callable(setter):
            setter(signer)
    urls = list(getattr(fanout, "urls", None) or _active_urls(None))

    logger.info("[verdict-transport] publishing verdict %s over %d relay(s): "
                "%s", _mask_env_report(resolved, env), len(urls),
                ", ".join(_host_of(u) for u in urls))

    raw = await _maybe_await(fanout.send_event(event))
    relay_results, ok = _coerce_publish_response(raw, fanout, urls)
    if ok is False:
        outcomes = _outcomes_from(raw, fanout)
        raise RelayPublishError(outcomes)
    return PublishResult(event, rumor, relay_results, relay_urls=urls,
                         outcomes=_outcomes_from(raw, fanout),
                         serializer_output=serialized, log=logger)
