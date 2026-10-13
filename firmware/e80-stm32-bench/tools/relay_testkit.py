#!/usr/bin/env python3
"""relay_testkit.py — shared scaffolding for the kind-1059 relay fan-out.

Cards t_588b1d1b (relay-set + first cut of the double) and t_69c76243 (hard-
error split + call-log reset + no-network guarantee).  This module ships the
importable fake relay transport double that the failover publisher tests drive,
and re-exports the single declared source of truth for the failover relay set.

Relay set (EXACT — do not add, remove, reorder, or normalize): the five bare
hostnames of the canonical constant re-exported below.

The canonical value (five BARE hostnames) is DEFINED ONCE in the kind-1059
gift-wrap publishing module (:mod:`cvm_armed_publisher`) and re-exported here
as :data:`FAILOVER_RELAYS` / :data:`FAILOVER_RELAY_URLS` — see card t_7c9268b7.

``relay.contextvm.org`` is DEAD (verified 2026-08-23); it must never appear as
an active host and is named here only as :data:`DEAD_RELAY_HOST`.

Transport double
================
The double is a drop-in for the production injection point
:class:`relay_failover.RelayFailoverPublisher`, whose only transport coupling is
``await transport.send(url, event) -> <NIP-01 frame>``.  It is provided for both
async callers (:class:`FakeRelayTransport`) and sync callers
(:class:`SyncFakeRelayTransport`).

Injection map
-------------
Behaviour is configured per relay URL with a plain dict, and any relay with no
entry defaults to ``ACCEPT``::

    FakeRelayTransport({
        "wss://nostr.mom":            ACCEPT,             # default, may be omitted
        "wss://relay.primal.net":     TIMEOUT,            # never answers
        "wss://nos.lol":              HARD_ERROR_RAISE,   # connection refused
        "wss://relay.nostr.band":     HARD_ERROR_REJECT,  # OK false, "blocked: ..."
    })

Seam note: :class:`relay_failover.RelayFailoverPublisher` signals a relay
refusal by *raising* ``RelayRejected`` — its ``_send_one`` ignores the returned
NIP-01 frame and treats any non-raising return as accepted.  The double still
returns the rejection frame as required (it is the wire shape a transport-layer
caller sees), but to exercise the publisher's reject-aggregation path a caller
must raise ``relay_failover.RelayRejected``.  Both are pinned in
``test_fake_relay_transport.py::TestSeamNuance``.

Behaviours
----------
  * ``ACCEPT`` -> returns the NIP-01 frame ``["OK", <event_id>, true, ""]`` where
    ``<event_id>`` is the 64-char lowercase hex id taken from the event actually
    being published (``event["id"]``) — never a hardcoded constant.
  * ``TIMEOUT`` -> never responds on its own: it awaits an :class:`asyncio.Event`
    that is never set, so the caller's per-relay deadline
    (``asyncio.wait_for``) cancels it.  ``CancelledError`` propagates untouched
    and no task is spawned, so nothing leaks.  (The sync twin has no event loop
    to await and raises :class:`TimeoutError` immediately instead.)
  * ``HARD_ERROR_RAISE`` -> raises :class:`ConnectionRefusedError` (an
    :class:`OSError` subclass), i.e. the relay is down.
  * ``HARD_ERROR_REJECT`` -> returns ``["OK", <event_id>, false, "blocked: ..."]``
    — the relay answered and refused; the reason is prefixed exactly
    ``"blocked: "``.

``HARD_ERROR`` and ``BLOCKED`` are retained as back-compat aliases for
``HARD_ERROR_RAISE`` and ``HARD_ERROR_REJECT`` respectively; the two
hard-error flavours are deliberately kept DISTINCT (a refused connection and a
policy refusal are not the same failure).

Call log
--------
Every attempt is recorded in send order *before* the behaviour runs:

  * ``.calls``    -> ``[(url, event_id), ...]``        (ordered, 2-tuples)
  * ``.attempts`` -> ``[(url, event_id, seq), ...]``   (``seq`` = deterministic
    0-based counter, a timestamp substitute so the log stays reproducible)

``.reset()`` (alias ``.clear()``) empties both logs and restarts ``seq`` at 0 —
use it between tests.

Hard no-network guarantee
-------------------------
This module imports NONE of ``socket``, ``ssl``, ``aiohttp``, ``httpx``,
``urllib3``, ``urllib`` or ``http``, and calls none of ``open_connection``,
``create_connection``, ``getaddrinfo`` or ``gethostbyname``.  Everything is
in-process and deterministic: no sockets, no DNS, no randomness, and no sleeps
other than the intentional never-resolving wait in ``TIMEOUT``.  (Pinned by
``test_fake_relay_transport.py::TestNoNetworkGuarantee`` with an AST scan.)

Example
-------
::

    import asyncio
    import relay_testkit as kit
    import relay_failover as rf

    transport = kit.FakeRelayTransport({
        "wss://relay.primal.net": kit.TIMEOUT,
        "wss://nos.lol":          kit.HARD_ERROR_RAISE,
        "wss://nostr.mom":        kit.HARD_ERROR_REJECT,
    })
    pub = rf.RelayFailoverPublisher(transport, timeout=0.05)
    result = asyncio.run(pub.publish(msg, session_fields))

    assert result.ok                      # 2 of 5 relays accepted
    assert transport.calls[0][0].startswith("wss://")
    transport.reset()                     # ready for the next test

Run its pins with:
    python3 -m pytest firmware/e80-stm32-bench/tools/test_relay_testkit.py -v
    python3 -m pytest firmware/e80-stm32-bench/tools/test_fake_relay_transport.py -v
"""

from __future__ import annotations

import asyncio
import os
import re
import sys

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

# --- single source of truth for the failover relay set ---------------------
# The canonical set (five bare hostnames) is DEFINED ONCE in the kind-1059
# gift-wrap publishing module; it is re-exported here, NEVER re-defined, so
# the fake-transport scaffolding and the production publisher can never
# disagree about which relays carry the fan-out (card t_7c9268b7).
import cvm_armed_publisher as _core  # noqa: E402

FAILOVER_RELAYS = list(_core.FAILOVER_RELAYS)
FAILOVER_RELAY_URLS = list(_core.FAILOVER_RELAY_URLS)

# --- per-relay behaviour mode names ---------------------------------------
ACCEPT = "accept"
TIMEOUT = "timeout"
#: The two distinct hard-error flavours — do NOT conflate.
HARD_ERROR_RAISE = "hard_error_raise"    # connection refused -> raise
HARD_ERROR_REJECT = "hard_error_reject"  # relay answers and refuses -> OK false

#: Back-compat aliases (cards before t_69c76243 used these names).
HARD_ERROR = HARD_ERROR_RAISE
BLOCKED = HARD_ERROR_REJECT

#: Raw strings from older behaviour maps, normalised on lookup.
_BEHAVIOUR_ALIASES = {
    "hard_error": HARD_ERROR_RAISE,
    "blocked": HARD_ERROR_REJECT,
}

#: The one dead relay (bare host). DEAD (verified 2026-08-23) — never active.
DEAD_RELAY_HOST = "relay.contextvm.org"

#: Hostname-boundary matcher for the dead host. The lookarounds stop the
#: legitimate ``relay2.contextvm.org`` (and neighbours such as
#: ``xrelay.contextvm.org`` or ``relay.contextvm.org.evil``) from matching:
#: a match requires the literal ``relay.contextvm.org`` to sit on a hostname
#: boundary (adjacent characters may not be ``[a-z0-9.-]``).
DEAD_HOST_RE = re.compile(r"(?<![a-z0-9.-])relay\.contextvm\.org(?![a-z0-9.-])")


def source_contains_dead_host(text: str) -> bool:
    """True iff ``text`` mentions the dead host at a hostname boundary."""
    return DEAD_HOST_RE.search(text) is not None


def normalise_behaviour(mode: str) -> str:
    """Map a legacy behaviour string onto its canonical name (else unchanged)."""
    return _BEHAVIOUR_ALIASES.get(mode, mode)


def nip01_ok(event_id, accepted: bool = True, message: str = "") -> list:
    """NIP-01 ``OK`` frame: ``["OK", <event_id>, <accepted>, <message>]``."""
    return ["OK", event_id, bool(accepted), message]


def blocked_ok(event_id, reason: str = "blocked: relay policy") -> list:
    """NIP-01 ``OK`` frame for a soft refusal (``accepted == False``)."""
    return nip01_ok(event_id, False, reason)


def _event_id(event) -> object:
    """The 64-char lowercase hex id carried by the event being published."""
    return (event or {}).get("id")


class _BehaviourMixin:
    """Shared behaviour-map handling for the async and sync doubles."""

    #: Default behaviour for a relay with no explicit entry.
    _default = ACCEPT

    def __init__(self, behaviour=None):
        self.behaviour = dict(behaviour or {})
        self.calls = []      # [(url, event_id), ...] in send order
        self.attempts = []   # [(url, event_id, seq), ...] in send order
        self._seq = 0

    def mode(self, url: str) -> str:
        """Canonical behaviour for ``url`` (defaults to :data:`ACCEPT`)."""
        return normalise_behaviour(self.behaviour.get(url, self._default))

    def _record(self, url: str, event_id) -> None:
        """Log an attempt before its behaviour runs (ordered, deterministic)."""
        self.calls.append((url, event_id))
        self.attempts.append((url, event_id, self._seq))
        self._seq += 1

    def reset(self) -> None:
        """Clear both call logs and restart the sequence counter at 0."""
        self.calls.clear()
        self.attempts.clear()
        self._seq = 0

    #: Alias kept for readability at call sites.
    clear = reset


class FakeRelayTransport(_BehaviourMixin):
    """Deterministic in-memory relay transport with per-relay behaviour.

    ``behaviour`` maps a relay URL to one of :data:`ACCEPT`, :data:`TIMEOUT`,
    :data:`HARD_ERROR_RAISE` or :data:`HARD_ERROR_REJECT`. Relays with no entry
    default to ``ACCEPT``. ``calls`` records every ``(url, event_id)`` in send
    order so a test can assert which relays were (and were not) contacted.

    ``send`` is a coroutine so it drops straight into the async failover
    publisher's ``transport`` seam; it never opens a socket.
    """

    def __init__(self, behaviour=None):
        super().__init__(behaviour)
        #: Never set by the double; ``TIMEOUT`` awaits it forever so the
        #: caller's ``asyncio.wait_for`` deadline is what ends the attempt.
        #: ``release_timeouts()`` exists only so a test can unblock it on
        #: purpose. (An unbound Event is fine on Python >= 3.10.)
        self._timeout_gate = asyncio.Event()

    def release_timeouts(self) -> None:
        """Let any in-flight ``TIMEOUT`` attempt complete (test convenience)."""
        self._timeout_gate.set()

    async def send(self, url: str, event: dict) -> list:
        """Deliver ``event`` to ``url`` and return the relay's NIP-01 frame."""
        event_id = _event_id(event)
        self._record(url, event_id)
        mode = self.mode(url)
        if mode == ACCEPT:
            return nip01_ok(event_id, True, "")
        if mode == HARD_ERROR_REJECT:
            return blocked_ok(
                event_id, "blocked: relay policy for {}".format(url))
        if mode == TIMEOUT:
            # Never resolves on its own; cancellation (the caller's deadline)
            # propagates as CancelledError — nothing is swallowed, no task is
            # spawned, so nothing leaks.
            await self._timeout_gate.wait()
            return nip01_ok(event_id, True, "")  # pragma: no cover
        if mode == HARD_ERROR_RAISE:
            raise ConnectionRefusedError("relay unreachable: {}".format(url))
        raise AssertionError("unknown behaviour {!r} for {}".format(mode, url))


class SyncFakeRelayTransport(_BehaviourMixin):
    """Blocking twin of :class:`FakeRelayTransport` for synchronous callers.

    ``TIMEOUT`` raises :class:`TimeoutError` immediately (a sync caller has no
    event loop to cancel); ``ACCEPT`` / ``HARD_ERROR_REJECT`` /
    ``HARD_ERROR_RAISE`` behave as in the async twin.
    """

    def send(self, url: str, event: dict) -> list:
        event_id = _event_id(event)
        self._record(url, event_id)
        mode = self.mode(url)
        if mode == ACCEPT:
            return nip01_ok(event_id, True, "")
        if mode == HARD_ERROR_REJECT:
            return blocked_ok(
                event_id, "blocked: relay policy for {}".format(url))
        if mode == TIMEOUT:
            raise TimeoutError("relay timed out: {}".format(url))
        if mode == HARD_ERROR_RAISE:
            raise ConnectionRefusedError("relay unreachable: {}".format(url))
        raise AssertionError("unknown behaviour {!r} for {}".format(mode, url))


__all__ = [
    "ACCEPT",
    "TIMEOUT",
    "HARD_ERROR_RAISE",
    "HARD_ERROR_REJECT",
    "HARD_ERROR",
    "BLOCKED",
    "FAILOVER_RELAYS",
    "DEAD_RELAY_HOST",
    "FAILOVER_RELAY_URLS",
    "DEAD_HOST_RE",
    "source_contains_dead_host",
    "normalise_behaviour",
    "nip01_ok",
    "blocked_ok",
    "FakeRelayTransport",
    "SyncFakeRelayTransport",
]
