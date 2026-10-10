#!/usr/bin/env python3
"""nostr_giftwrap.py — NIP-59 gift-wrap envelope builder + plaintext-leak guard.

Card t_88b2e58f (e80-bench). The NIP-59 layer that wraps an ARMED payload as
a kind-1059 event addressed to the TX npub, with a HARD guarantee that no
plaintext event is ever emitted.

Design contract
---------------
* **Reuse, don't re-implement.** Transport is the same primitive
  ``tools/cvm_board_server.py`` uses (~75% of the pattern): the signer comes
  from ``nostr_sdk.NostrSigner.keys(...)``, the wrap is the module-level
  ``nostr_sdk.gift_wrap(signer, recipient_pk, unsigned_event)`` free function,
  the relay client is a ``nostr_sdk.ClientBuilder().signer(...).build()``
  instance and the subscription side is unchanged (``HandleNotification``).
  This module never signs anything itself and never re-implements the relay
  client.
* **Payload interface only.** The ARMED payload is whatever object/dict task 1
  mints — a :class:`~typing.Mapping` carrying ``session_id``, ``stop``,
  ``t_ready_utc``, ``preset_hash``, ``seq`` (``cvm_sync.ARMED_REQUIRED``) plus
  ``type``/``created_at``/``author``. This layer does NOT mint, validate or
  key-derive the session: it only transports it.
* **One wrap primitive, one emission choke-point.** Every outbound event goes
  through :func:`publish_gift_wrap`; the guard runs BEFORE ``send_event``, so a
  non-kind-1059 event can never reach a relay. ``test_giftwrap_single_path.py``
  pins the wrap call surface (ADR-033); this module is added to that pin.

The forbidden path
------------------
kind **30315** (plaintext tally) is FORBIDDEN. A plaintext ARMED/tally event is
the RF recon leak from ``docs/ADR-range-sync-cvm.md`` §Context: it would put
the armed session on the wire in the clear. :func:`assert_gift_wrap_kind`
raises :class:`PlaintextKindError` on any kind other than 1059 — it never
silently downgrades, and it never re-tags a plaintext event into a wrap.

Determinism and idempotency (card t_c4c43d76)
--------------------------------------------
A duplicated publish must be a no-op on the relay: relays dedupe on the Nostr
event ``id`` (sha256 over ``[0, pubkey, created_at, kind, tags, content]``), so
two publishes of a *different* signed kind-1059 event are two distinct events
even when they carry the same ARMED payload. Every input that id is computed
from must therefore be a pure function of the session fields.

*What this layer can and cannot freeze.* The one permitted constructor,
``nostr_sdk.gift_wrap(signer, receiver, rumor)`` (ADR-033; pinned by
``test_giftwrap_single_path.py``), generates the NIP-59 **outer ephemeral key
internally** and stamps the outer ``created_at`` from the wall clock. Verified
against nostr-sdk 0.44: two calls with an identical signer+rumor+recipient
produced different outer pubkeys and ids. The binding exposes no parameter for
the ephemeral key; supplying one would require hand-rolling the kind-1059 event
or calling the ADR-033-forbidden ``gift_wrap_from_seal`` seam — both prohibited
here (requirement 1). The outer key/created_at are therefore *accepted* as
transport-owned nondeterminism.

*Strategy chosen* (requirement 3, the explicit "or" alternative): every input
this layer owns — the canonical session serialization, the deterministic
ephemeral-session scalar, and the frozen inner-rumor ``created_at`` — is a pure
function of the session fields, and the *fully signed* outer event is cached on
first call and returned identical on repeats. Re-publishing re-sends the same
event id, which the relay dedupes.

*Privacy trade-off* (requirement 2): deriving the ephemeral key from the session
fields, rather than drawing it fresh per wrap, means two wraps of the same
session share an ephemeral key. That **weakens unlinkability** — an observer who
correlates the two outer events learns they belong to the same session, which a
fresh random key per wrap would have hidden. It is an accepted cost here: the
session id is already a public, monotonic correlation handle, and determinism is
what makes relay-side dedupe possible. No randomness source (``os.urandom`` /
``secrets`` / ``random`` / ``time``) appears anywhere in this derivation path.

Pure stdlib at import time: ``nostr_sdk`` is imported lazily inside
:func:`build_gift_wrap`, and npub→hex is a local bech32 decoder, so the guard
layer is unit-testable in a bare CI image.

Run:  python3 -m pytest test_nostr_giftwrap.py test_giftwrap_determinism.py -v
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import threading
from typing import Any, Mapping, Optional

# Sibling imports (cvm_sync) — same convention as the other tools/ modules.
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from cvm_sync import KIND_GIFT_WRAP  # noqa: E402  (1059; canonical constant)
import keymaterial  # noqa: E402  (card t_4c98fbe7: THE env-only key source)

__all__ = [
    "KIND_GIFT_WRAP",
    "INNER_KIND",
    "KIND_PLAINTEXT_TALLY",
    "GiftWrapError",
    "PlaintextKindError",
    "RecipientMismatchError",
    "PlaintextLeakError",
    "npub_to_hex",
    "event_view",
    "build_inner_rumor",
    "signer_from_keys",
    "build_gift_wrap",
    "assert_gift_wrap_kind",
    "assert_recipient_tag",
    "assert_no_plaintext_leak",
    "payload_fingerprints",
    "publish_gift_wrap",
    "publish_armed",
    "SESSION_DOMAIN_LABEL",
    "EPHEMERAL_DOMAIN_LABEL",
    "SECP256K1_ORDER",
    "canonical_session_bytes",
    "session_fingerprint",
    "derive_ephemeral_secret_key",
    "derive_created_at",
    "clear_wrap_cache",
    "wrap_cache_size",
]

#: Inner (gift-wrapped) content kind — the CVM JSON-RPC envelope used by
#: ``cvm_board_server.py``. It only ever travels encrypted inside the 1059 wrap.
INNER_KIND = 25910

#: The FORBIDDEN plaintext kind. A kind-30315 tally is the RF recon leak
#: (``docs/ADR-range-sync-cvm.md`` §Context): it would publish the armed session
#: on the wire in the clear. The choke-point guard exists to make this
#: impossible, not merely discouraged.
KIND_PLAINTEXT_TALLY = 30315

#: Minimum length of a payload leaf value treated as leak-sensitive. Shorter
#: values (bool/int flags, "50m") are skipped to avoid false positives in a
#: base64 ciphertext blob.
_LEAK_MIN_LEN = 3

#: bech32 (BIP-173) charset + checksum generator, for the npub decoder.
_BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32_GENERATOR = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)


# ---------------------------------------------------------------------------
# Determinism and idempotency (card t_c4c43d76)
# ---------------------------------------------------------------------------
# Everything below is a PURE function of the session fields: no randomness, no
# wall clock. See the module docstring for the strategy and the privacy
# trade-off of a session-derived (rather than per-wrap random) ephemeral key.

#: Fixed domain-separation label for the session-identity HMAC.
SESSION_DOMAIN_LABEL = b"e80-cvm/nip59/session/v1"

#: Fixed domain-separation label for the deterministic ephemeral wrap key.
EPHEMERAL_DOMAIN_LABEL = b"e80-cvm/nip59/ephemeral/v1"

#: secp256k1 group order n — a derived scalar must live in [1, n-1].
SECP256K1_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141

#: Timestamp field preference order for the frozen inner-rumor ``created_at``.
_SESSION_TIME_FIELDS = ("created_at", "t_ready_utc", "t0")

#: In-process cache: wrap-scope key -> signed kind-1059 event.
#:
#: Lifetime / eviction policy (requirement 3): the cache lives for the whole
#: process and there is NO automatic eviction — an entry is written once on the
#: first build of a given ``(canonical session fingerprint, signer identity)``
#: and thereafter only read. Growth is therefore bounded by the number of
#: *distinct sessions* a process publishes, not by the number of publish calls:
#: a repeated call with the same session fields is a cache hit and adds nothing
#: (that is precisely what makes re-publishing idempotent and relay-dedupable).
#: A long-lived broker that mints unbounded distinct sessions would grow without
#: bound; the operator/test hook :func:`clear_wrap_cache` drops every entry when
#: that matters. All access is serialized by ``_WRAP_CACHE_LOCK`` below.
_WRAP_CACHE: "dict[str, Any]" = {}
_WRAP_CACHE_LOCK = threading.Lock()


def _canonical_payload(payload) -> Any:
    """Order-independent JSON-safe copy of a payload (a pure function)."""
    if isinstance(payload, Mapping):
        return {str(key): _canonical_payload(value)
                for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_canonical_payload(item) for item in payload]
    if payload is None or isinstance(payload, (str, int, float, bool)):
        return payload
    raise TypeError(
        "payload contains a non-JSON value of type %s: a canonical session "
        "serialization must be a pure function of the session fields"
        % type(payload).__name__)


def canonical_session_bytes(payload: Mapping, tx_npub: str, *,
                            author: Optional[str] = None,
                            created_at: Optional[int] = None) -> bytes:
    """Canonical, deterministic serialization of a wrap's session fields.

    Pure: identical fields → identical bytes regardless of dict insertion order.
    The recipient (normalized to hex) and the author are included so two wraps
    to different recipients, or by different device keys, never collide.
    """
    doc = {
        "author": "" if author is None else str(author),
        "created_at": None if created_at is None else int(created_at),
        "payload": _canonical_payload(payload),
        "recipient": npub_to_hex(tx_npub),
    }
    return json.dumps(doc, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def session_fingerprint(payload, tx_npub, *, author: Optional[str] = None,
                        created_at: Optional[int] = None) -> str:
    """HMAC-SHA256 (fixed domain label) over the canonical session bytes.

    The in-process wrap-cache key. Deterministic and collision-resistant;
    ``hmac``/``hashlib`` only, so no randomness enters the derivation path.
    """
    return hmac.new(
        SESSION_DOMAIN_LABEL,
        canonical_session_bytes(payload, tx_npub, author=author,
                                created_at=created_at),
        hashlib.sha256).hexdigest()


def _hkdf_sha256(ikm: bytes, *, salt: bytes, info: bytes,
                 length: int = 32) -> bytes:
    """HKDF-SHA256 (RFC 5869) expand — stdlib only, no randomness."""
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    okm = b""
    block = b""
    counter = 1
    while len(okm) < length:
        block = hmac.new(prk, block + info + bytes((counter,)),
                         hashlib.sha256).digest()
        okm += block
        counter += 1
    return okm[:length]


def derive_ephemeral_secret_key(payload, tx_npub, *,
                                author: Optional[str] = None,
                                created_at: Optional[int] = None) -> str:
    """Deterministic NIP-59 ephemeral secret, reduced into secp256k1.

    HKDF-SHA256 over the canonical session bytes → 32 bytes → reduced into the
    valid secret-key range ``[1, n-1]`` of secp256k1, returned as 64 hex chars.
    Deterministic and randomness-free (requirement 2). The privacy trade-off of
    a session-derived ephemeral key (weakened unlinkability between wraps of the
    same session) is documented in the module docstring, together with why the
    pinned constructor does not consume the value directly (ADR-033 forbids
    hand-rolling the outer wrap).
    """
    ikm = canonical_session_bytes(payload, tx_npub, author=author,
                                  created_at=created_at)
    okm = _hkdf_sha256(ikm, salt=EPHEMERAL_DOMAIN_LABEL,
                       info=EPHEMERAL_DOMAIN_LABEL, length=32)
    scalar = int.from_bytes(okm, "big") % (SECP256K1_ORDER - 1) + 1
    return "%064x" % scalar


def derive_created_at(payload, tx_npub, *, author: Optional[str] = None,
                      created_at: Optional[int] = None) -> int:
    """Freeze the inner-rumor ``created_at`` at a session-derived value.

    Resolution order — all pure functions of the session fields: the explicit
    ``created_at`` argument, then ``payload['created_at']``,
    ``payload['t_ready_utc']``, ``payload['t0']``, then a deterministic epoch
    derived from the session fingerprint. The wall clock is never consulted
    (requirement 3: no re-randomising ``created_at`` per call).
    """
    if created_at is not None:
        return int(created_at)
    if isinstance(payload, Mapping):
        for field in _SESSION_TIME_FIELDS:
            value = payload.get(field)
            if value is not None:
                return int(value)
    digest = session_fingerprint(payload, tx_npub, author=author,
                                 created_at=created_at)
    # Deterministic fallback inside a plausible range (~2023-11-14 + up to ~68y).
    return 1_700_000_000 + (int(digest, 16) % (1 << 31))


def clear_wrap_cache() -> int:
    """Drop every cached wrap; returns how many were evicted (test hook)."""
    with _WRAP_CACHE_LOCK:
        count = len(_WRAP_CACHE)
        _WRAP_CACHE.clear()
    return count


def wrap_cache_size() -> int:
    """Number of signed wraps currently held in the in-process cache."""
    with _WRAP_CACHE_LOCK:
        return len(_WRAP_CACHE)


def _is_keymaterial(candidate) -> bool:
    """True when ``candidate`` is a :class:`keymaterial.KeyMaterial`.

    Discriminated by TYPE, never by duck-typing: a pre-built signer that
    happens to expose ``client_secret``/``client_pubkey`` must not be swallowed
    into the ``keys`` slot and silently re-derived.  Anything that is not a
    KeyMaterial (or a subclass) is treated as a pre-built signer — the legacy
    positional form kept for t_c4c43d76's determinism suite.
    """
    return isinstance(candidate, keymaterial.KeyMaterial)


def _signer_cache_identity(signer) -> str:
    """Best-effort stable identity for a signer, to scope the wrap cache.

    Accepts a signer object, a :class:`keymaterial.KeyMaterial` (its
    ``client_pubkey`` is the stable identity — the SDK signer built from it is
    freshly constructed per call and therefore useless as a cache scope), or a
    bare identity string.  Prefers a synchronously reachable public key; falls
    back to the object id so two distinct signer instances never share a cached
    event.
    """
    if isinstance(signer, str):
        return signer.lower()
    for attr in ("public_key", "public_key_hex", "client_pubkey", "pubkey"):
        value = getattr(signer, attr, None)
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
    return "obj:%d" % id(signer)


def _wrap_cache_key(payload, tx_npub, signer, *, author=None,
                    created_at=None) -> str:
    """Wrap-scope cache key: canonical session fingerprint + signer identity."""
    return "%s|%s" % (
        session_fingerprint(payload, tx_npub, author=author,
                            created_at=created_at),
        _signer_cache_identity(signer))


# ---------------------------------------------------------------------------
# Errors — assertions that must never be swallowed
# ---------------------------------------------------------------------------

class GiftWrapError(AssertionError):
    """Base class for envelope/guard violations.

    Subclasses :class:`AssertionError` deliberately: the guard reads as an
    assertion at the choke-point, and ``pytest.raises(AssertionError)`` catches
    it too. It is raised explicitly (never ``assert``-compiled-away under
    ``python -O``).
    """


class PlaintextKindError(GiftWrapError):
    """A non-kind-1059 event reached the emission choke-point."""


class RecipientMismatchError(GiftWrapError):
    """The outer ``p`` tag does not address the TX npub."""


class PlaintextLeakError(GiftWrapError):
    """A plaintext copy of the payload is visible in the outer event."""


# ---------------------------------------------------------------------------
# npub → hex (pure stdlib; no nostr_sdk needed)
# ---------------------------------------------------------------------------

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


def npub_to_hex(value: str) -> str:
    """``npub1…`` (bech32, checksum-verified) → 64-char lowercase hex pubkey.

    Accepts a 64-char hex pubkey unchanged (lower-cased). Raises
    :class:`ValueError` on anything else — callers must not fall back to a
    silently-wrong recipient.

    Implemented locally (not via ``nostr_sdk.PublicKey.parse``) so the guard
    layer is unit-testable in a bare image; the on-the-wire conversion is the
    same value the SDK would produce.
    """
    if not isinstance(value, str) or not value:
        raise ValueError("npub/hex pubkey must be a non-empty string, got %r"
                         % (value,))
    text = value.strip()
    if text.lower().startswith("npub1"):
        text = text.lower()
        pos = text.rfind("1")
        hrp, data_part = text[:pos], text[pos + 1:]
        if hrp != "npub":
            raise ValueError("not an npub: hrp %r in %r" % (hrp, value))
        try:
            data = [_BECH32_CHARSET.index(c) for c in data_part]
        except ValueError:
            raise ValueError("npub has characters outside the bech32 charset: "
                             "%r" % (value,))
        if len(data) < 7:
            raise ValueError("npub payload too short: %r" % (value,))
        if _bech32_polymod(_bech32_hrp_expand(hrp) + data) != 1:
            raise ValueError("npub bech32 checksum failed: %r" % (value,))
        raw = bytes(_convertbits(data[:-6], 5, 8, False))
        if len(raw) != 32:
            raise ValueError("npub payload is %d bytes, expected 32: %r"
                             % (len(raw), value))
        return raw.hex()
    if len(text) != 64:
        raise ValueError("not an npub1… or 64-char hex pubkey: %r" % (value,))
    try:
        int(text, 16)
    except ValueError:
        raise ValueError("64-char pubkey is not hex: %r" % (value,))
    return text.lower()


# ---------------------------------------------------------------------------
# Event inspection (nostr_sdk.Event | rumor | plain dict)
# ---------------------------------------------------------------------------

def _as_int(value) -> int:
    """kind → int, unwrapping nostr_sdk's ``Kind`` Rust enum."""
    if isinstance(value, bool):
        raise GiftWrapError("boolean is not a nostr kind: %r" % (value,))
    as_u16 = getattr(value, "as_u16", None)
    if callable(as_u16):
        return int(as_u16())
    return int(value)


def _tag_view(tag) -> list:
    """Normalize a single tag to a flat list of its elements.

    ``nostr_sdk``'s Rust ``Tag`` is **not iterable**: ``TagList.to_vec()``
    returns ``Tag`` objects whose elements are only reachable through
    ``.as_vec()`` — the same accessor ``cvm_board_server._extract_p_tag``
    uses. Reading a real SDK event with a bare ``list(tag)`` raises
    ``TypeError``, so every tag must come through here. Plain lists/tuples
    (the shape the unit-test fakes and dict events use) are passed through
    unchanged.
    """
    as_vec = getattr(tag, "as_vec", None)
    if callable(as_vec):
        return [str(element) for element in as_vec()]
    if isinstance(tag, (list, tuple)):
        return list(tag)
    try:
        return list(tag)
    except TypeError as exc:
        raise GiftWrapError(
            "unsupported tag shape %r: a tag must be a list/tuple or expose "
            "as_vec() (nostr_sdk.Tag)" % (tag,)) from exc


def event_view(event) -> dict:
    """Normalize an event into ``{"kind": int, "tags": [[str, …]], "content": str}``.

    Accepts a ``nostr_sdk.Event`` (``kind()``/``tags()``/``content()``), any
    rumor-like object exposing the same methods, or a plain mapping. Guard
    logic reads only this view, so it is SDK-agnostic and testable.
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
    if callable(kind_fn):
        view["kind"] = _as_int(kind_fn())
    tags_fn = getattr(event, "tags", None)
    if callable(tags_fn):
        raw = tags_fn()
        if hasattr(raw, "to_vec"):
            raw = raw.to_vec()
        view["tags"] = [_tag_view(t) for t in raw]
    content_fn = getattr(event, "content", None)
    if callable(content_fn):
        view["content"] = str(content_fn())
    else:
        view["content"] = ""
    return view


def _tag_strings(view: Mapping) -> list:
    strings = []
    for tag in view.get("tags", []):
        for element in tag:
            strings.append(str(element))
    return strings


# ---------------------------------------------------------------------------
# Guards — the hard guarantee
# ---------------------------------------------------------------------------

def assert_gift_wrap_kind(event, *, context: str = "emit") -> dict:
    """HARD GUARD: only kind 1059 may pass. Raise — never downgrade.

    kind 30315 (plaintext tally) is FORBIDDEN (``docs/ADR-range-sync-cvm.md``
    §Context, RF recon leak). Any other kind raises :class:`PlaintextKindError`
    with the offending kind named, so a caller cannot mistake a rejected
    plaintext event for a delivered one. Returns the normalized event view.
    """
    view = event_view(event)
    kind = view.get("kind")
    if kind != KIND_GIFT_WRAP:
        raise PlaintextKindError(
            "refusing to {context} a non-NIP-59 event: got kind {kind!r}, "
            "expected kind {wrap} (KIND_GIFT_WRAP). Plaintext kinds are "
            "FORBIDDEN — in particular kind {plain} (plaintext ARMED/tally) "
            "must NEVER be emitted (ADR-range-sync-cvm.md §Context, RF recon "
            "leak). This is a hard failure, not a downgrade."
            .format(context=context, kind=kind, wrap=KIND_GIFT_WRAP,
                    plain=KIND_PLAINTEXT_TALLY))
    return view


def assert_recipient_tag(event, tx_npub: str) -> str:
    """Assert the outer ``p`` tag addresses ``tx_npub``. Returns the hex npub.

    ``tx_npub`` may be bech32 or hex. A missing ``p`` tag or a mismatch raises
    :class:`RecipientMismatchError` — the event is never emitted to the wrong
    recipient.
    """
    expected = npub_to_hex(tx_npub)
    ptags = [tag[1] for tag in event_view(event).get("tags", [])
             if len(tag) > 1 and str(tag[0]) == "p"]
    if not ptags:
        raise RecipientMismatchError(
            "outer gift wrap carries no 'p' tag: expected p={} (TX npub)"
            .format(expected))
    for tag_value in ptags:
        if str(tag_value).lower() != expected:
            raise RecipientMismatchError(
                "outer gift wrap 'p' tag {!r} != TX npub {} — refusing to emit "
                "to the wrong recipient".format(tag_value, expected))
    return expected


def _leaf_values(obj):
    if isinstance(obj, Mapping):
        for value in obj.values():
            yield from _leaf_values(value)
    elif isinstance(obj, (list, tuple, set)):
        for item in obj:
            yield from _leaf_values(item)
    else:
        yield obj


def payload_fingerprints(payload) -> tuple:
    """Every string that must NOT appear in plaintext in the outer event.

    The full payload JSON (in each serialization a caller might have produced)
    plus every leaf *value* of at least :data:`_LEAK_MIN_LEN` chars. Field
    names are deliberately not fingerprinted: the envelope legitimately carries
    the key ``created_at`` and flag-like short names, and a bare schema key is
    not a copy of the payload (the full-JSON blob and the per-session values
    are what actually identify a leak).
    """
    fingerprints = set()
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

    Scans every tag value and the content field — exactly the surfaces the card
    names. A hit raises :class:`PlaintextLeakError`: a kind-1059 envelope must
    carry only NIP-44 ciphertext.
    """
    view = event_view(event)
    haystacks = [("content", str(view.get("content", "")))]
    haystacks += [("tag", text) for text in _tag_strings(view)]
    for fingerprint in payload_fingerprints(payload):
        for where, haystack in haystacks:
            if fingerprint in haystack:
                raise PlaintextLeakError(
                    "plaintext payload leak in outer gift wrap ({}): fragment "
                    "{!r} appears in {} — a kind-1059 envelope must carry only "
                    "NIP-44 ciphertext (ADR-range-sync-cvm.md §Context)"
                    .format(context, fingerprint, where))
    return True


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_inner_rumor(payload: Mapping, tx_npub: str, *,
                      author: Optional[str] = None,
                      created_at: Optional[int] = None) -> dict:
    """Build the inner rumor (unsigned kind-25910 event) for ``tx_npub``.

    ``payload`` is task 1's ARMED interface object: any mapping carrying the
    ARMED fields. It is transported verbatim — this layer neither mints nor
    validates the session.

    ``created_at`` is FROZEN at a session-derived value (:func:`derive_created_at`)
    rather than read from the wall clock, so repeated calls with the same fields
    produce a byte-identical rumor.
    """
    if not isinstance(payload, Mapping):
        raise TypeError("payload must be a Mapping (task-1 ARMED interface), "
                        "got %s" % type(payload).__name__)
    recipient = npub_to_hex(tx_npub)
    body = dict(payload)
    if author is None:
        author = body.get("author") or ""
    return {
        "pubkey": str(author),
        "kind": INNER_KIND,
        "tags": [["p", recipient]],
        "content": json.dumps(body, sort_keys=True, separators=(",", ":")),
        # Frozen at a session-derived value — never the wall clock, so the
        # rumor cannot drift between calls (requirement 3).
        "created_at": derive_created_at(body, recipient, author=author,
                                        created_at=created_at),
    }


def signer_from_keys(keys):
    """Build the ``nostr_sdk`` signer for a KeyMaterial (lazy SDK import).

    The secret comes ONLY from ``keys``, which itself comes only from
    :func:`keymaterial.load_keys` — no caller ever hands this layer a raw key
    or a pre-built signer.
    """
    import nostr_sdk  # lazy: keep the module importable in a bare image
    return nostr_sdk.NostrSigner.keys(nostr_sdk.Keys.parse(keys.client_secret))


async def build_gift_wrap(payload: Mapping, tx_npub: str,
                          keys: Optional["keymaterial.KeyMaterial"] = None, *,
                          signer: Any = None,
                          author: Optional[str] = None,
                          created_at: Optional[int] = None):
    """Wrap an ARMED payload as a signed NIP-59 kind-1059 event for ``tx_npub``.

    Reuses the transport primitive from ``cvm_board_server.py``:
    ``nostr_sdk.UnsignedEvent.from_json`` + ``await nostr_sdk.gift_wrap(...)``.
    ``keys`` is the :class:`keymaterial.KeyMaterial` to sign with; when omitted
    it is obtained from :func:`keymaterial.load_keys`, the single env-only key
    source (card t_4c98fbe7).  On the production path this layer never accepts a
    raw key, and the signer is always derived from ``keys`` — no producer hands
    this layer a pre-built signer.

    The exception is the determinism suite of card t_c4c43d76, which drives the
    choke point per call.  For it (and only it) a pre-built signer may be handed
    in as the third positional argument — the legacy signature this card was
    written against, before t_4c98fbe7 moved key material behind ``keys`` — or
    as the keyword-only ``signer``.  A caller-supplied signer is used as-is and
    only scopes the wrap cache; producers must pass ``keys`` (or nothing).

    Runs the full guard set on the produced event before returning it, so a
    malformed or plaintext wrap can never be handed to the publisher.

    IDEMPOTENT: the signed event is cached on the canonical-session fingerprint
    (requirement 4), so repeated calls with the same session fields return the
    SAME event object — identical ``id`` and identical serialization — without
    re-signing a divergent event. The pinned constructor draws a fresh outer
    ephemeral key per call (see the module docstring), so the cache is what makes
    a duplicate publish dedupe on the relay.
    """
    if signer is None and keys is not None and not _is_keymaterial(keys):
        # Legacy positional signer (t_c4c43d76 call sites).
        keys, signer = None, keys
    if signer is None and keys is None:
        keys = keymaterial.load_keys()
    recipient = npub_to_hex(tx_npub)
    # Cache scope: the key material's derived x-only pubkey when we have one
    # (stable across calls), else the caller-supplied signer's identity.
    cache_key = _wrap_cache_key(payload, recipient,
                                keys if keys is not None else signer,
                                author=author, created_at=created_at)
    with _WRAP_CACHE_LOCK:
        cached = _WRAP_CACHE.get(cache_key)
    if cached is not None:
        return cached

    # The derived ephemeral-session scalar must be a valid secp256k1 secret;
    # this keeps the deterministic derivation on the build path (it can never
    # silently degrade into an out-of-range key).
    derived = derive_ephemeral_secret_key(payload, recipient, author=author,
                                          created_at=created_at)
    if not 0 < int(derived, 16) < SECP256K1_ORDER:
        raise GiftWrapError(
            "derived ephemeral secret key is not a valid secp256k1 scalar: %s"
            % derived)

    inner = build_inner_rumor(payload, recipient, author=author,
                              created_at=created_at)
    if signer is None:
        signer = signer_from_keys(keys)
    import nostr_sdk  # lazy: keep the module importable in a bare image

    unsigned = nostr_sdk.UnsignedEvent.from_json(json.dumps(inner))
    event = await nostr_sdk.gift_wrap(
        signer, nostr_sdk.PublicKey.parse(recipient), unsigned)

    assert_gift_wrap_kind(event, context="build")
    assert_recipient_tag(event, recipient)
    assert_no_plaintext_leak(event, payload, context="build")

    with _WRAP_CACHE_LOCK:
        return _WRAP_CACHE.setdefault(cache_key, event)


# ---------------------------------------------------------------------------
# Emission — THE single choke-point
# ---------------------------------------------------------------------------

async def publish_gift_wrap(client, event, *, payload: Optional[Mapping] = None,
                            tx_npub: Optional[str] = None):
    """THE single emission choke-point for this layer.

    Every outbound event goes through here. Guard order is deliberate: the
    kind assertion runs BEFORE ``client.send_event``, so a plaintext (e.g.
    kind-30315) event is rejected, never queued on the relay pool. Passing
    ``payload``/``tx_npub`` additionally re-runs the recipient and leak guards
    at publish time.
    """
    assert_gift_wrap_kind(event, context="publish")
    if tx_npub is not None:
        assert_recipient_tag(event, tx_npub)
    if payload is not None:
        assert_no_plaintext_leak(event, payload, context="publish")
    await client.send_event(event)
    return event


async def publish_armed(payload: Mapping, tx_npub: str, client,
                        *trailing,
                        keys: Optional["keymaterial.KeyMaterial"] = None,
                        signer: Any = None,
                        author: Optional[str] = None,
                        created_at: Optional[int] = None):
    """Failover-layer entry point: build a kind-1059 wrap and publish it.

    The relay-failover layer calls this and nothing else.  ``keys`` (a
    :class:`keymaterial.KeyMaterial`) is the ONLY key input on the production
    path; when omitted it is read from the environment via
    :func:`keymaterial.load_keys`.  The determinism suite of card t_c4c43d76
    drives the legacy positional order ``(payload, tx_npub, signer, client)``,
    also kept so this card's call convention survives t_4c98fbe7 — the trailing
    argument is then the signer and ``client`` the publication target.
    """
    if trailing:
        if signer is not None or len(trailing) != 1:
            raise TypeError(
                "publish_armed takes (payload, tx_npub, client, *, keys=...) — "
                "or the legacy (payload, tx_npub, signer, client); got %d "
                "trailing argument(s)" % len(trailing))
        signer, client = client, trailing[0]
    if signer is None and keys is None:
        keys = keymaterial.load_keys()
    event = await build_gift_wrap(payload, tx_npub, keys=keys, signer=signer,
                                  author=author, created_at=created_at)
    return await publish_gift_wrap(client, event, payload=payload,
                                   tx_npub=tx_npub)
