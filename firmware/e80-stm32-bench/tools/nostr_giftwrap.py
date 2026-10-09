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

Pure stdlib at import time: ``nostr_sdk`` is imported lazily inside
:func:`build_gift_wrap`, and npub→hex is a local bech32 decoder, so the guard
layer is unit-testable in a bare CI image.

Run:  python3 -m pytest test_nostr_giftwrap.py -v
"""

from __future__ import annotations

import json
import os
import sys
import time
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
    """
    if not isinstance(payload, Mapping):
        raise TypeError("payload must be a Mapping (task-1 ARMED interface), "
                        "got %s" % type(payload).__name__)
    recipient = npub_to_hex(tx_npub)
    body = dict(payload)
    if created_at is None:
        created_at = body.get("created_at")
    if created_at is None:
        created_at = time.time()
    if author is None:
        author = body.get("author") or ""
    return {
        "pubkey": str(author),
        "kind": INNER_KIND,
        "tags": [["p", recipient]],
        "content": json.dumps(body, sort_keys=True, separators=(",", ":")),
        "created_at": int(created_at),
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
                          author: Optional[str] = None,
                          created_at: Optional[int] = None):
    """Wrap an ARMED payload as a signed NIP-59 kind-1059 event for ``tx_npub``.

    Reuses the transport primitive from ``cvm_board_server.py``:
    ``nostr_sdk.UnsignedEvent.from_json`` + ``await nostr_sdk.gift_wrap(...)``.
    ``keys`` is the :class:`keymaterial.KeyMaterial` to sign with; when omitted
    it is obtained from :func:`keymaterial.load_keys`, the single env-only key
    source (card t_4c98fbe7).  This layer never accepts a raw key or a
    pre-built signer from a caller.

    Runs the full guard set on the produced event before returning it, so a
    malformed or plaintext wrap can never be handed to the publisher.
    """
    keys = keys or keymaterial.load_keys()
    recipient = npub_to_hex(tx_npub)
    inner = build_inner_rumor(payload, recipient, author=author,
                              created_at=created_at)
    import nostr_sdk  # lazy: keep the module importable in a bare image

    signer = signer_from_keys(keys)
    unsigned = nostr_sdk.UnsignedEvent.from_json(json.dumps(inner))
    event = await nostr_sdk.gift_wrap(
        signer, nostr_sdk.PublicKey.parse(recipient), unsigned)

    assert_gift_wrap_kind(event, context="build")
    assert_recipient_tag(event, recipient)
    assert_no_plaintext_leak(event, payload, context="build")
    return event


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


async def publish_armed(payload: Mapping, tx_npub: str, client, *,
                        keys: Optional["keymaterial.KeyMaterial"] = None,
                        author: Optional[str] = None,
                        created_at: Optional[int] = None):
    """Failover-layer entry point: build a kind-1059 wrap and publish it.

    The relay-failover layer calls this and nothing else.  ``keys`` (a
    :class:`keymaterial.KeyMaterial`) is the ONLY key input; when omitted it is
    read from the environment via :func:`keymaterial.load_keys`.
    """
    keys = keys or keymaterial.load_keys()
    event = await build_gift_wrap(payload, tx_npub, keys=keys,
                                  author=author, created_at=created_at)
    return await publish_gift_wrap(client, event, payload=payload,
                                   tx_npub=tx_npub)
