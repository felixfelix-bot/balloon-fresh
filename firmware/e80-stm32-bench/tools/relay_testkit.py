#!/usr/bin/env python3
"""relay_testkit.py — shared scaffolding for the kind-1059 relay fan-out.

Card t_588b1d1b. This module is the single declared source of truth for the
failover relay set, and ships the importable fake relay transport double that
the failover publisher tests drive.

Relay set (EXACT — do not add, remove, reorder, or normalize):

    nostr.mom, relay.primal.net, nos.lol, relay2.contextvm.org, relay.nostr.band

``relay.contextvm.org`` is DEAD (verified 2026-08-23); it must never appear as
an active host and is named here only as :data:`DEAD_RELAY_HOST`.

Everything is in-process and deterministic: no sockets, no live network. The
transport double is implemented for both async callers
(:class:`FakeRelayTransport`) and sync callers (:class:`SyncFakeRelayTransport`)
with per-relay injectable behaviour:

  * ``ACCEPT``     -> returns the NIP-01 frame ``["OK", <event_id>, true, ""]``
  * ``TIMEOUT``    -> never responds on its own (async twin awaits forever; a
                      per-relay deadline must cancel it; the sync twin raises)
  * ``HARD_ERROR`` -> raises ``ConnectionRefusedError`` (the relay is down)
  * ``BLOCKED``    -> returns ``["OK", <event_id>, false, "blocked: ..."]``

Run its pins with:
    python3 -m pytest firmware/e80-stm32-bench/tools/test_relay_testkit.py -v
"""

from __future__ import annotations

import asyncio
import re

# --- per-relay behaviour mode names ---------------------------------------
ACCEPT = "accept"
TIMEOUT = "timeout"
HARD_ERROR = "hard_error"
BLOCKED = "blocked"

#: Canonical failover relay set as bare hostnames, in the exact contractual
#: order. THE single source of truth for *which* relays carry the fan-out.
FAILOVER_RELAYS = [
    "nostr.mom",
    "relay.primal.net",
    "nos.lol",
    "relay2.contextvm.org",
    "relay.nostr.band",
]

#: The one dead relay (bare host). DEAD (verified 2026-08-23) — never active.
DEAD_RELAY_HOST = "relay.contextvm.org"

#: The same set as ``wss://`` relay URLs, DERIVED (never hand-maintained) from
#: :data:`FAILOVER_RELAYS` so the host and URL views can never drift apart.
FAILOVER_RELAY_URLS = ["wss://{}".format(host) for host in FAILOVER_RELAYS]

#: Hostname-boundary matcher for the dead host. The lookarounds stop the
#: legitimate ``relay2.contextvm.org`` (and neighbours such as
#: ``xrelay.contextvm.org`` or ``relay.contextvm.org.evil``) from matching:
#: a match requires the literal ``relay.contextvm.org`` to sit on a hostname
#: boundary (adjacent characters may not be ``[a-z0-9.-]``).
DEAD_HOST_RE = re.compile(r"(?<![a-z0-9.-])relay\.contextvm\.org(?![a-z0-9.-])")


def source_contains_dead_host(text: str) -> bool:
    """True iff ``text`` mentions the dead host at a hostname boundary."""
    return DEAD_HOST_RE.search(text) is not None


def nip01_ok(event_id, accepted: bool = True, message: str = "") -> list:
    """NIP-01 ``OK`` frame: ``["OK", <event_id>, <accepted>, <message>]``."""
    return ["OK", event_id, bool(accepted), message]


def blocked_ok(event_id, reason: str = "blocked: relay policy") -> list:
    """NIP-01 ``OK`` frame for a soft refusal (``accepted == False``)."""
    return nip01_ok(event_id, False, reason)


class FakeRelayTransport:
    """Deterministic in-memory relay transport with per-relay behaviour.

    ``behaviour`` maps a relay URL to one of :data:`ACCEPT`, :data:`TIMEOUT`,
    :data:`HARD_ERROR`, or :data:`BLOCKED`. Relays with no entry default to
    ``ACCEPT``. ``calls`` records every ``(url, event_id)`` in send order so a
    test can assert which relays were (and were not) contacted.

    ``send`` is a coroutine so it drops straight into the async failover
    publisher's ``transport`` seam; it never opens a socket.
    """

    def __init__(self, behaviour=None):
        self.behaviour = dict(behaviour or {})
        self.calls = []

    def mode(self, url: str) -> str:
        return self.behaviour.get(url, ACCEPT)

    async def send(self, url: str, event: dict) -> list:
        """Deliver ``event`` to ``url`` and return the relay's NIP-01 frame."""
        event_id = (event or {}).get("id")
        self.calls.append((url, event_id))
        mode = self.mode(url)
        if mode == ACCEPT:
            return nip01_ok(event_id, True, "")
        if mode == BLOCKED:
            return blocked_ok(event_id)
        if mode == TIMEOUT:
            # Must be cancelled by the caller's per-relay deadline.
            await asyncio.sleep(3600)
            return nip01_ok(event_id, True, "")  # pragma: no cover
        if mode == HARD_ERROR:
            raise ConnectionRefusedError("relay unreachable: {}".format(url))
        raise AssertionError("unknown behaviour {!r} for {}".format(mode, url))


class SyncFakeRelayTransport:
    """Blocking twin of :class:`FakeRelayTransport` for synchronous callers.

    ``TIMEOUT`` raises :class:`TimeoutError` immediately (a sync caller has no
    event loop to cancel); ``ACCEPT`` / ``BLOCKED`` / ``HARD_ERROR`` behave as
    in the async twin.
    """

    def __init__(self, behaviour=None):
        self.behaviour = dict(behaviour or {})
        self.calls = []

    def mode(self, url: str) -> str:
        return self.behaviour.get(url, ACCEPT)

    def send(self, url: str, event: dict) -> list:
        event_id = (event or {}).get("id")
        self.calls.append((url, event_id))
        mode = self.mode(url)
        if mode == ACCEPT:
            return nip01_ok(event_id, True, "")
        if mode == BLOCKED:
            return blocked_ok(event_id)
        if mode == TIMEOUT:
            raise TimeoutError("relay timed out: {}".format(url))
        if mode == HARD_ERROR:
            raise ConnectionRefusedError("relay unreachable: {}".format(url))
        raise AssertionError("unknown behaviour {!r} for {}".format(mode, url))


__all__ = [
    "ACCEPT",
    "TIMEOUT",
    "HARD_ERROR",
    "BLOCKED",
    "FAILOVER_RELAYS",
    "DEAD_RELAY_HOST",
    "FAILOVER_RELAY_URLS",
    "DEAD_HOST_RE",
    "source_contains_dead_host",
    "nip01_ok",
    "blocked_ok",
    "FakeRelayTransport",
    "SyncFakeRelayTransport",
]
