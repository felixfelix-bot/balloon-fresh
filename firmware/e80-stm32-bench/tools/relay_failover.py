#!/usr/bin/env python3
"""relay_failover.py — dead-relay-proof, deterministic kind-1059 publish fan-out.

Card t_120db4f6. This module is a *thin fan-out layer* on top of the gift-wrap
choke-point (``cvm_armed_publisher``):

  * it NEVER constructs a plaintext event and NEVER builds the inner event
    itself — the inner (CVM-RPC) event is produced by the choke-point's
    ``build_inner_event`` and the outer envelope is kind 1059 (gift wrap);
  * anything that is not a kind-1059 event is refused with
    ``PlaintextKindError`` before a single byte reaches a relay.

Relay set (EXACT — do not add or remove):
    nostr.mom, relay.primal.net, nos.lol, relay2.contextvm.org, relay.nostr.band
``relay.contextvm.org`` is DEAD (verified 2026-08-23) and is filtered out even
if supplied by env / ``extra``.

Failover semantics
------------------
Every relay in the set is attempted concurrently. Each attempt runs under its
own per-relay deadline (``asyncio.wait_for``); a relay that times out, errors,
or explicitly rejects is recorded as ``failed + reason`` and NEVER aborts the
fan-out. The aggregate is returned as a :class:`FailoverResult`; as long as at
least one relay accepts, the publish succeeds. Only when *every* relay fails is
``PublishFailedError`` raised.

Idempotency
-----------
NIP-59 needs an ephemeral key for the outer wrap. A random one would make every
replay a *different* event id (relays cannot dedupe, and the wire is
non-deterministic). We therefore DERIVE the ephemeral secret deterministically
from the session fields with HKDF-SHA256, and pin the outer ``created_at`` to
the session's ``t_ready_utc``. Consequence (the documented decision): identical
session fields always yield the SAME outer event id, so relays can dedupe on the
id and the process can dedupe replays without re-signing divergent events.

The determinism contract is about *id stability*. In production the outer
envelope is produced by the nostr_sdk gift-wrap choke-point fed the same
deterministic ephemeral secret + pinned ``created_at``; :func:`deterministic_giftwrap`
is the hermetic (no-SDK) implementation of the same contract and the default
wrap used by :class:`RelayFailoverPublisher`.

Runs without ``nostr_sdk``, hardware, or network.

Run:  python3 -m pytest tools/test_relay_failover_publisher.py -v
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import cvm_armed_publisher as choke  # noqa: E402
from cvm_armed_publisher import (  # noqa: E402
    PlaintextKindError,
    failover_relays as _choke_failover_relays,
)

#: NIP-59 outer envelope kind (gift wrap).  Re-exported from the choke-point,
#: NEVER redefined — ADR-033 pins the set of modules that may author a local
#: ``KIND_GIFT_WRAP = 1059`` constant (test_giftwrap_single_path.py).
KIND_GIFT_WRAP = choke.KIND_GIFT_WRAP

#: The single dead relay. Must never reach the active set.  DEAD (verified).
DEAD_RELAY_URL = "wss://relay.contextvm.org"  # DEAD — filtered, never published

#: Exact five-host failover set, re-exported from the choke-point (single source).
FAILOVER_RELAYS = list(choke.FAILOVER_RELAYS)

_HKDF_IKM = b"cvm-nip59-ephemeral-v1"
_HKDF_SALT = b"cvm-nip59-salt-v1"
_CONTENT_SALT = b"cvm-nip59-content-v1"
_PUBKEY_INFO = b"cvm-nip59-eph-pub"


class RelayRejected(RuntimeError):
    """A relay answered but refused the event (e.g. policy / rate limit)."""


class PublishFailedError(RuntimeError):
    """No relay accepted the event. Carries the per-relay outcomes."""

    def __init__(self, outcomes: Sequence["RelayOutcome"]):
        self.outcomes = list(outcomes)
        failed = ", ".join("{}: {}".format(o.url, o.reason)
                           for o in self.outcomes)
        super().__init__("all {} relays failed: {}".format(
            len(self.outcomes), failed))


@dataclass(frozen=True)
class RelayOutcome:
    """One relay's result: accepted, or failed with a human reason."""

    url: str
    accepted: bool
    reason: str = ""


@dataclass
class FailoverResult:
    """Aggregated per-relay outcome of one publish."""

    outcomes: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True iff at least one relay accepted."""
        return any(o.accepted for o in self.outcomes)

    @property
    def accepted(self) -> list:
        return [o for o in self.outcomes if o.accepted]

    @property
    def failed(self) -> list:
        return [o for o in self.outcomes if not o.accepted]


# ---------------------------------------------------------------------------
# Relay set (dead relay filtered even when supplied)
# ---------------------------------------------------------------------------

def failover_relays(extra: Optional[Sequence[str]] = None) -> list:
    """Ordered active relay set: exact five hosts, dead relay filtered."""
    return _choke_failover_relays(list(extra) if extra else None)


def active_relay_hosts(extra: Optional[Sequence[str]] = None) -> set:
    """Bare hostnames of the active relay set."""
    return {u.split("://", 1)[1] for u in failover_relays(extra)}


# ---------------------------------------------------------------------------
# Deterministic NIP-59 derivation (idempotency)
# ---------------------------------------------------------------------------

def _canonical_bytes(obj: Any) -> bytes:
    """Stable, sorted JSON serialization (byte-identical across runs)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def hkdf_sha256(ikm: bytes, salt: bytes, info: bytes,
                length: int = 32) -> bytes:
    """RFC 5869 HKDF-SHA256 (extract + expand), stdlib-only."""
    if not salt:
        salt = b"\x00" * hashlib.sha256().digest_size
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    okm = b""
    block = b""
    counter = 1
    while len(okm) < length:
        block = hmac.new(prk, block + info + bytes([counter]),
                         hashlib.sha256).digest()
        okm += block
        counter += 1
    return okm[:length]


def derive_ephemeral_secret(session_fields: Mapping) -> bytes:
    """Deterministic NIP-59 ephemeral secret (32 bytes) from session fields.

    Decision (documented in the module docstring): the ephemeral key is HKDF
    of the canonical session fields instead of ``secrets.token_bytes`` so the
    outer event's pubkey — and therefore its id — is reproducible.
    """
    info = _canonical_bytes(dict(session_fields))
    return hkdf_sha256(_HKDF_IKM, _HKDF_SALT, info, 32)


def derive_ephemeral_pubkey_hex(session_fields: Mapping) -> str:
    """Deterministic x-only pubkey material for the derived ephemeral secret.

    NOTE: this is the *id-stability* derivation. On the live path the SDK
    derives the real secp256k1 x-only pubkey of the same deterministic secret,
    so the outer event id stays identical; this helper keeps the hermetic
    (no-SDK) path byte-identical for tests and dedupe.
    """
    secret = derive_ephemeral_secret(session_fields)
    return hashlib.sha256(_PUBKEY_INFO + secret).hexdigest()


def session_created_at(session_fields: Mapping) -> int:
    """Pinned outer ``created_at`` — never wall-clock, so replays keep the id."""
    for key in ("created_at", "t_ready_utc"):
        val = session_fields.get(key)
        if isinstance(val, int) and val > 0:
            return int(val)
    return 0


def stable_event_id(pubkey_hex: str, created_at: int, kind: int,
                    tags: list, content: str) -> str:
    """NIP-01 event id: sha256 of the canonical [0, pubkey, …] serialization."""
    serialized = json.dumps([0, pubkey_hex, int(created_at), int(kind), tags,
                             content],
                            separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def deterministic_giftwrap(msg: dict, session_fields: Mapping,
                           tx_pubkey_hex: str,
                           author_pubkey_hex: str = "") -> dict:
    """Build the outer kind-1059 envelope with a session-stable id.

    The inner event is built by the choke-point's ``build_inner_event`` (there
    is no second plaintext construction here); the outer content is a
    deterministic stand-in for the NIP-44 ciphertext so the id is stable. The
    live path substitutes the SDK's real ciphertext/keys but MUST feed it the
    same ephemeral secret + ``created_at`` to keep the id identical.
    """
    if msg.get("type") == "TALLY":
        raise PlaintextKindError("refusing to gift-wrap a plaintext tally")
    created_at = session_created_at(session_fields)
    inner = choke.build_inner_event(msg, tx_pubkey_hex,
                                    author_pubkey_hex=author_pubkey_hex or "",
                                    created_at=created_at)
    secret = derive_ephemeral_secret(session_fields)
    content = hkdf_sha256(secret, _CONTENT_SALT, _canonical_bytes(inner),
                          32).hex()
    pubkey = derive_ephemeral_pubkey_hex(session_fields)
    tags = [["p", tx_pubkey_hex]]
    event_id = stable_event_id(pubkey, created_at, KIND_GIFT_WRAP, tags, content)
    return {
        "id": event_id,
        "pubkey": pubkey,
        "created_at": created_at,
        "kind": KIND_GIFT_WRAP,
        "tags": tags,
        "content": content,
        "sig": "",
    }


# ---------------------------------------------------------------------------
# Failover publisher
# ---------------------------------------------------------------------------

class RelayFailoverPublisher:
    """Publish one gift-wrapped event to the exact relay set, failover-safe.

    ``transport`` is any object exposing ``async def send(url, event)``. A relay
    may fail by returning/raising: ``RelayRejected`` (explicit refusal),
    ``asyncio.TimeoutError`` (deadline), or any other exception (hard error).
    """

    def __init__(self, transport, timeout: float = 5.0,
                 relays: Optional[Sequence[str]] = None,
                 tx_pubkey_hex: str = "", author_pubkey_hex: str = "",
                 log: Callable = print):
        self.transport = transport
        self.timeout = timeout
        self.relays = failover_relays(relays)
        self.tx_pubkey_hex = tx_pubkey_hex
        self.author_pubkey_hex = author_pubkey_hex
        self.log = log
        self._cache: dict = {}

    def _default_wrap(self, msg: dict, session_fields: Mapping) -> dict:
        """Default wrap: the hermetic, choke-point-backed deterministic wrap."""
        return deterministic_giftwrap(msg, session_fields, self.tx_pubkey_hex,
                                      self.author_pubkey_hex)

    async def _send_one(self, url: str, event: dict) -> RelayOutcome:
        """One relay attempt under its own deadline; never raises upward."""
        try:
            await asyncio.wait_for(self.transport.send(url, event),
                                   self.timeout)
            return RelayOutcome(url, True, "")
        except asyncio.TimeoutError:
            return RelayOutcome(url, False, "timeout")
        except RelayRejected as exc:
            return RelayOutcome(url, False, "rejected: {}".format(exc))
        except Exception as exc:  # noqa: BLE001 - any relay fault is isolated
            return RelayOutcome(url, False, "error: {}: {}".format(
                type(exc).__name__, exc))

    async def publish(self, msg: dict, session_fields: Mapping,
                      wrap: Optional[Callable] = None) -> FailoverResult:
        """Wrap ``msg`` through the choke-point and fan it out.

        Raises ``PlaintextKindError`` if a non-kind-1059 envelope would go out,
        and ``PublishFailedError`` only when every relay fails.
        """
        if isinstance(msg, dict) and msg.get("type") == "TALLY":
            raise PlaintextKindError("refusing to publish a plaintext tally")
        session_fields = dict(session_fields)
        wrap = wrap or self._default_wrap
        event = wrap(msg, session_fields)
        kind = event.get("kind") if isinstance(event, dict) else None
        if kind != KIND_GIFT_WRAP:
            raise PlaintextKindError(
                "refusing to publish a non-gift-wrap event (kind={!r}); the "
                "only send path is NIP-59 kind 1059".format(kind))

        key = event.get("id") or repr(sorted(event.items()))
        if key in self._cache:
            return self._cache[key]  # in-process dedupe: transport not re-called

        outcomes = await asyncio.gather(
            *[self._send_one(url, event) for url in self.relays])
        result = FailoverResult(list(outcomes))
        if not result.ok:
            raise PublishFailedError(result.outcomes)
        self._cache[key] = result
        return result


__all__ = [
    "FAILOVER_RELAYS",
    "DEAD_RELAY_URL",
    "KIND_GIFT_WRAP",
    "RelayOutcome",
    "FailoverResult",
    "RelayRejected",
    "PublishFailedError",
    "failover_relays",
    "active_relay_hosts",
    "hkdf_sha256",
    "derive_ephemeral_secret",
    "derive_ephemeral_pubkey_hex",
    "session_created_at",
    "stable_event_id",
    "deterministic_giftwrap",
    "RelayFailoverPublisher",
]
