#!/usr/bin/env python3
"""fake_relay_transport.py — network-free fake relay transport double.

A test double for the relay wire seam used by
``firmware/e80-stm32-bench/tools/verdict_transport.py`` (the NIP-59 kind-1059
gift-wrap verdict publisher). Tests import this module to drive the publisher
through ``publish_verdict(..., transport=<double>)`` — or through the
``relay_transport_factory`` monkeypatch seam — **without touching a socket**:
no DNS, no websocket, no Rust binding, no relay.

Import command (from the ``tools/`` directory, which is on ``sys.path``)::

    python -c "import fake_relay_transport as frt; print(frt.ACCEPT, frt.TIMEOUT, frt.HARD_ERROR)"

or, from elsewhere on the repo::

    python -c "import sys; sys.path.insert(0, 'firmware/e80-stm32-bench/tools'); import fake_relay_transport"

Interface — matched to the sibling suite (EXACTLY)
==================================================

``FakeRelayTransport.send_event(event)`` is ``async`` and returns the same
mapping the live transport returns, so ``verdict_transport``'s
``_coerce_publish_response`` / ``_outcomes_from`` consume it unchanged::

    {"accepted": <int>,                       # relays that ACKed
     "ok": <bool>,                            # >=1 relay accepted
     "event_id": <hex|None>,
     "relay_results": {host: status_str, …},  # per-relay status
     "outcomes": [RelayOutcome, …]}           # optional, when available

The attribute view (``.hosts`` / ``.urls`` / ``.relay_results`` / ``.outcomes``
/ ``.sent``) mirrors ``NostrFailoverTransport`` so a caller may aggregate from
either. ``set_signer(signer)`` is a no-op that returns ``self`` (the live
transport's signer hand-off), so the default-transport path in
``publish_verdict`` works with no SDK.

Per-relay injectable behaviours
===============================

Configure a behaviour **per relay** with a ``{host: behaviour}`` mapping. The
keys are matched against the bare host of the relay URL (``wss://nos.lol`` ->
``nos.lol``); a ``'*'`` key is the default for any host not named.

============================  ============================================
Behaviour                     What the double does for that relay
============================  ============================================
``ACCEPT``                    NIP-01 OK, success:
                              ``["OK", <event_id>, true, ""]``
``HARD_REFUSED``              Connection refused for that relay:
                              raises :class:`ConnectionRefusedError`
                              (the failover path catches it per relay).
``HARD_REJECT``               NIP-01 OK, refusal:
                              ``["OK", <event_id>, false, "blocked: …"]``
``HARD_ERROR``                Alias of ``HARD_REFUSED`` (the default hard mode
                              the failover tests expect).
``TIMEOUT``                   Never responds: ``send_event`` awaits a
                              never-resolving future until the caller cancels
                              (raise :class:`RelayTimeoutError` when
                              ``timeout_s`` is set). The relay is omitted from
                              the result — it never ACKs.
============================  ============================================

The single-response model: ``send_event`` fans the event out to every
configured relay, collects one outcome per relay, and *only the accepting
relays* settle (a refusal settles as ``failed: …``, a refusal-by-exception as
``failed: ConnectionRefusedError``, a timeout stays pending). ``ok`` is True
iff at least one relay accepted — the same rule ``verdict_transport`` applies.

Usage
=====

::

    import asyncio
    import fake_relay_transport as frt

    # 1. Per-relay behaviours: first relay times out, second refuses,
    #    third accepts. The publisher must fail over and land on #3.
    relay = frt.FakeRelayTransport(
        urls=["wss://nostr.mom", "wss://relay.primal.net", "wss://nos.lol"],
        behaviours={"nostr.mom": frt.TIMEOUT,
                    "relay.primal.net": frt.HARD_REFUSED},
        default_behaviour=frt.ACCEPT)

    result = asyncio.run(relay.send_event({"id": "ab" * 32, "kind": 1059}))
    assert result["ok"] is True                       # nos.lol accepted
    assert result["relay_results"]["nostr.mom"] == "timeout (pending)"
    assert result["relay_results"]["relay.primal.net"] == "failed: ConnectionRefusedError"

    # 2. Wire it into the real publisher (hermetic — no socket):
    #
    #      from verdict_transport import publish_verdict
    #      res = publish_verdict(serializer, transport=relay, env=env)
    #
    #    or replace the module seam so the default path is exercised:
    #
    #      import verdict_transport as vt
    #      vt.relay_transport_factory = lambda urls, env=None: frt.FakeRelayTransport(
    #          urls=urls, default_behaviour=frt.ACCEPT)

    # 3. All-relays-fail: the publisher raises RelayPublishError.
    dead = frt.FakeRelayTransport(urls=["wss://nostr.mom"],
                                  default_behaviour=frt.HARD_REJECT)
    out = asyncio.run(dead.send_event({"id": "cd" * 32}))
    assert out["ok"] is False
    assert out["relay_results"]["nostr.mom"] == "failed: blocked: …"

    # 4. Mutation between calls (a relay that heals):
    relay.set_behaviour("nostr.mom", frt.ACCEPT)

Sync callers: :meth:`FakeRelayTransport.send_event_sync` runs the coroutine to
completion with ``asyncio.run`` for tests that are not themselves async.

Run the module's own self-check (no network, no pytest needed)::

    python firmware/e80-stm32-bench/tools/fake_relay_transport.py
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from typing import Any, Mapping, Optional, Sequence

# Sibling import convention — same as the other tools/ modules.
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

__all__ = [
    "ACCEPT",
    "TIMEOUT",
    "HARD_ERROR",
    "HARD_REFUSED",
    "HARD_REJECT",
    "BEHAVIOURS",
    "RelayTimeoutError",
    "RelayOutcome",
    "Nip01Ok",
    "FakeRelayTransport",
    "factories_for",
    "ok_message",
]

# ---------------------------------------------------------------------------
# Behaviour tokens
# ---------------------------------------------------------------------------

#: Responds with a NIP-01 OK success: ``["OK", <event_id>, true, ""]``.
ACCEPT = "accept"

#: Never responds. ``send_event`` awaits a never-resolving future until the
#: caller cancels (or raises :class:`RelayTimeoutError` when ``timeout_s`` set).
TIMEOUT = "timeout"

#: Raises ``ConnectionRefusedError`` for that relay — the per-relay failure the
#: ordered failover path catches and steps over.
HARD_REFUSED = "hard_refused"

#: Responds with a NIP-01 OK refusal:
#: ``["OK", <event_id>, false, "blocked: <detail>"]``.
HARD_REJECT = "hard_reject"

#: Alias of :data:`HARD_REFUSED` — the default "hard error" mode the existing
#: failover tests expect (a refused connection). :data:`HARD_REJECT` is offered
#: as the protocol-level variant (OK false).
HARD_ERROR = HARD_REFUSED

#: Every accepted behaviour token.
BEHAVIOURS = (ACCEPT, TIMEOUT, HARD_REFUSED, HARD_REJECT)

#: Wildcard key: the behaviour for any host not explicitly named.
WILDCARD = "*"

#: Default reason a refusing relay puts in its OK message.
DEFAULT_BLOCKED_REASON = "blocked: refusal injected by FakeRelayTransport"


class RelayTimeoutError(TimeoutError):
    """The injected TIMEOUT behaviour elapsed (only when ``timeout_s`` is set).

    With the default ``timeout_s=None`` a TIMEOUT relay blocks forever and the
    caller's cancellation is the only exit — this error exists so a test can opt
    into a bounded, non-raising-forever variant.
    """


class RelayOutcome:
    """One relay's outcome, mirroring ``verdict_transport.RelayOutcome``.

    ``host``/``url`` identify the relay, ``accepted`` is True only for an
    accepting ACK, ``reason`` carries the refusal/timeout detail, and
    ``status`` is the canonical string that also appears in ``relay_results``.
    """

    __slots__ = ("host", "url", "accepted", "reason", "status", "behaviour")

    def __init__(self, host: str, url: str = "", accepted: bool = False,
                 reason: str = "", status: str = "", behaviour: str = ""):
        self.host = host
        self.url = url or host
        self.accepted = bool(accepted)
        self.reason = reason
        self.status = status or ("accepted" if self.accepted else
                                 "failed: %s" % (reason or "rejected"))
        self.behaviour = behaviour

    def __repr__(self):  # pragma: no cover - debug helper
        return ("RelayOutcome(host=%r, accepted=%r, behaviour=%r, status=%r)"
                % (self.host, self.accepted, self.behaviour, self.status))


class Nip01Ok:
    """A NIP-01 relay message double: ``["OK", <event_id>, <bool>, <msg>]``.

    Exposes the shape ``verdict_transport.AckObserver.handle_msg`` reads: the
    ``as_vec()`` list, the ``is_ok()`` predicate, and the ``event_id`` /
    ``status`` / ``message`` attributes consumed by ``_fields_of``. It is
    therefore usable by any handle-notification style consumer without
    fabricating private SDK types.
    """

    def __init__(self, event_id: Optional[str], status: bool, message: str = ""):
        self.event_id = event_id if event_id is not None else ""
        self.status = bool(status)
        self.message = message or ""

    # --- NIP-01 wire view ------------------------------------------------

    def as_vec(self) -> list:
        """``["OK", event_id, status, message]`` — exactly NIP-01 OK."""
        return ["OK", self.event_id, self.status, self.message]

    def as_json(self) -> str:
        return json.dumps(self.as_vec())

    def to_json(self) -> str:
        return self.as_json()

    def __iter__(self):
        return iter(self.as_vec())

    def __getitem__(self, index):
        return self.as_vec()[index]

    def __len__(self):
        return 4

    # --- AckObserver-facing predicates -----------------------------------

    def is_ok(self) -> bool:
        return True

    def __repr__(self):  # pragma: no cover - debug helper
        return "Nip01Ok(%r)" % (self.as_vec(),)


def ok_message(event_id: Optional[str], accepted: bool = True,
               message: str = "") -> Nip01Ok:
    """Build the NIP-01 OK double for ``event_id`` (success or refusal)."""
    if not accepted and not message:
        message = DEFAULT_BLOCKED_REASON
    return Nip01Ok(event_id, accepted, message)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _host_of(url: Any) -> str:
    """Bare lowercase host of a relay URL or host string ('' when empty).

    Same normalization as ``verdict_transport._host_of`` so behaviour keys
    written either as ``wss://nos.lol`` or ``nos.lol`` match the same relay.
    """
    if url is None:
        return ""
    text = str(url).strip().lower()
    if "://" in text:
        text = text.split("://", 1)[1]
    text = text.split("/", 1)[0]
    return text


def _as_url(value: Any) -> str:
    """Present a host or URL as a URL (``wss://`` prefix added when missing)."""
    text = str(value).strip()
    return text if "://" in text else "wss://" + text


def event_id_of(event: Any) -> Optional[str]:
    """Best-effort lowercase hex id of an event double (None when unreadable).

    Mirrors ``verdict_transport._event_id_hex``: an ``id()`` method (SDK
    ``EventId`` with ``to_hex()``), an ``id`` attribute, or a mapping key.
    """
    if isinstance(event, Mapping):
        value = event.get("id")
        return str(value).lower() if value else None
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
    if isinstance(id_fn, str) and id_fn:
        return id_fn.lower()
    return None


def _event_json(event: Any) -> str:
    """Deterministic JSON view of an event double (never a fabricated id)."""
    for attr in ("as_json", "to_json"):
        fn = getattr(event, attr, None)
        if callable(fn):
            try:
                return str(fn())
            except Exception:
                pass
    if isinstance(event, Mapping):
        return json.dumps(event, sort_keys=True)
    try:
        return json.dumps(event, sort_keys=True)
    except (TypeError, ValueError):
        return repr(event)


# ---------------------------------------------------------------------------
# The double
# ---------------------------------------------------------------------------

class FakeRelayTransport:
    """Network-free relay fan-out with injectable per-relay behaviour.

    Parameters
    ----------
    urls:
        The relay set, bare hosts or ``wss://`` URLs. Defaults to the canonical
        :data:`verdict_transport.FAILOVER_RELAY_URLS` when importable, else an
        empty set. Order is preserved (failover order is significant).
    behaviours:
        ``{host: behaviour}`` — per-relay overrides. Keys match the bare host
        (``wss://nos.lol`` and ``nos.lol`` are equivalent). A ``'*'`` key sets
        the default for unnamed hosts.
    default_behaviour:
        Behaviour for a host with no override (default :data:`ACCEPT`).
    timeout_s:
        When set, a :data:`TIMEOUT` relay raises :class:`RelayTimeoutError`
        after this many seconds instead of awaiting forever.
    log:
        Optional logger. Never emits event content.

    Every attribute the live ``NostrFailoverTransport`` exposes is present, so
    ``publish_verdict`` and its coercion helpers treat the two identically.
    """

    def __init__(self, urls: Optional[Sequence[Any]] = None,
                 behaviours: Optional[Mapping[str, str]] = None, *,
                 default_behaviour: str = ACCEPT,
                 timeout_s: Optional[float] = None,
                 log=None,
                 blocked_reason: str = DEFAULT_BLOCKED_REASON):
        if urls is None:
            urls = _canonical_urls()
        self.urls = [_as_url(u) for u in urls]
        self.hosts = [_host_of(u) for u in self.urls]
        self.behaviours = {_host_of(k): v for k, v in (behaviours or {}).items()}
        self.default_behaviour = _check_behaviour(default_behaviour)
        self.timeout_s = timeout_s
        self.blocked_reason = blocked_reason or DEFAULT_BLOCKED_REASON
        self.log = log

        self.sent: list = []
        self.relay_results: dict = {h: "pending" for h in self.hosts}
        self.outcomes: list = []
        self.connected_relays: list = []
        self.signer: Any = None
        self.client: Any = None
        self.send_calls = 0
        self.messages: list = []   # Nip01Ok doubles produced (wire evidence)
        self._pending: list = []   # never-resolved TIMEOUT futures

    # --- behaviour configuration ----------------------------------------

    def set_behaviour(self, host: Any, behaviour: str) -> "FakeRelayTransport":
        """Set one relay's behaviour (accepts a bare host or a URL). Returns self."""
        self.behaviours[_host_of(host)] = _check_behaviour(behaviour)
        return self

    def behaviour_for(self, host: Any) -> str:
        """The effective behaviour for ``host`` (override, wildcard, default)."""
        bare = _host_of(host)
        if bare in self.behaviours:
            return self.behaviours[bare]
        if WILDCARD in self.behaviours:
            return self.behaviours[WILDCARD]
        return self.default_behaviour

    def set_behaviours(self, behaviours: Mapping[str, str]):
        """Merge ``{host: behaviour}`` into the configuration. Returns self."""
        for host, behaviour in (behaviours or {}).items():
            self.behaviours[_host_of(host)] = _check_behaviour(behaviour)
        return self

    def reset(self):
        """Clear recorded state (keep the behaviour configuration)."""
        self.sent.clear()
        self.messages.clear()
        self.outcomes.clear()
        self.connected_relays.clear()
        self._pending.clear()
        self.send_calls = 0
        self.relay_results = {h: "pending" for h in self.hosts}

    # --- live-transport mirror ------------------------------------------

    def set_signer(self, signer):
        """No-op signer hand-off (the live transport's API). Returns self."""
        self.signer = signer
        return self

    # --- wire -------------------------------------------------------------

    async def send_event(self, event):
        """Fan ``event`` out to every relay and return the aggregate mapping.

        Returns ``{"accepted": int, "ok": bool, "event_id": hex|None,
        "relay_results": {host: status}, "outcomes": [RelayOutcome, …]}``.
        ``ok`` is True iff at least one relay accepted — the rule
        ``verdict_transport`` applies. Never touches the network.
        """
        self.send_calls += 1
        self.sent.append(event)
        event_id = event_id_of(event)
        self.relay_results = {h: "pending" for h in self.hosts}
        self.outcomes = []
        accepted = 0

        for url in self.urls:
            host = _host_of(url)
            behaviour = self.behaviour_for(host)
            if behaviour == ACCEPT:
                message = self._record_ok(host, event_id, True, "")
                if host not in self.connected_relays:
                    self.connected_relays.append(url)
                self.relay_results[host] = "accepted"
                self.outcomes.append(RelayOutcome(
                    host, url, accepted=True, reason="", status="accepted",
                    behaviour=behaviour))
                accepted += 1
            elif behaviour == HARD_REJECT:
                message = self._record_ok(host, event_id, False,
                                          self.blocked_reason)
                reason = message.message
                self.relay_results[host] = "failed: %s" % reason
                self.outcomes.append(RelayOutcome(
                    host, url, accepted=False, reason=reason,
                    status="failed: %s" % reason, behaviour=behaviour))
            elif behaviour == HARD_REFUSED:
                reason = "ConnectionRefusedError"
                if host not in self.connected_relays:
                    self.connected_relays.append(url)
                self.relay_results[host] = "failed: %s" % reason
                self.outcomes.append(RelayOutcome(
                    host, url, accepted=False, reason=reason,
                    status="failed: %s" % reason, behaviour=behaviour))
            elif behaviour == TIMEOUT:
                # Never responds: block until the caller cancels us. Recorded as
                # pending (no ACK) — it is NOT an acceptance and NOT a refusal.
                self.relay_results[host] = "timeout (pending)"
                self.outcomes.append(RelayOutcome(
                    host, url, accepted=False, reason="",
                    status="timeout (pending)", behaviour=behaviour))
                await self._await_forever()
            else:  # pragma: no cover - _check_behaviour rejects unknown tokens
                raise ValueError("unknown behaviour %r for relay %r"
                                 % (behaviour, host))

        return {
            "accepted": accepted,
            "ok": accepted > 0,
            "event_id": event_id,
            "relay_results": dict(self.relay_results),
            "outcomes": list(self.outcomes),
        }

    def send_event_sync(self, event):
        """Run :meth:`send_event` to completion for a non-async caller."""
        return asyncio.run(self.send_event(event))

    # --- internals --------------------------------------------------------

    def _record_ok(self, host: str, event_id: Optional[str], accepted: bool,
                   message: str) -> Nip01Ok:
        """Record and return the NIP-01 OK double for one relay."""
        double = ok_message(event_id, accepted, message)
        self.messages.append((host, double))
        return double

    async def _await_forever(self):
        """Await a never-resolving future (bounded only by ``timeout_s``)."""
        future = asyncio.get_event_loop().create_future()
        self._pending.append(future)
        if self.timeout_s is None:
            await asyncio.shield(future)  # caller cancellation is the only exit
        await asyncio.wait_for(asyncio.shield(future), self.timeout_s)
        raise RelayTimeoutError(
            "TIMEOUT behaviour elapsed after %ss" % (self.timeout_s,))


def _check_behaviour(behaviour: str) -> str:
    """Validate a behaviour token, accepting the ``HARD_ERROR`` alias."""
    token = str(behaviour).strip().lower()
    if token == HARD_ERROR:
        return HARD_REFUSED
    if token not in BEHAVIOURS:
        raise ValueError("unknown relay behaviour %r (expected one of %s)"
                         % (behaviour, ", ".join(BEHAVIOURS)))
    return token


def _canonical_urls() -> list:
    """The canonical failover relay URLs, imported lazily (never hardcoded)."""
    try:
        import verdict_transport as vt  # sibling module
        return list(vt.FAILOVER_RELAY_URLS)
    except Exception:
        return []


def factories_for(behaviours: Mapping[str, str], *, default_behaviour: str = ACCEPT,
                  timeout_s: Optional[float] = None):
    """Return a ``relay_transport_factory``-shaped callable with behaviours baked in.

    Assign it to ``verdict_transport.relay_transport_factory`` to exercise the
    publisher's DEFAULT transport path hermetically::

        import verdict_transport as vt
        vt.relay_transport_factory = factories_for({"nos.lol": ACCEPT})

    The returned callable accepts ``(urls=None, env=None)`` — the seam's exact
    signature — and builds a :class:`FakeRelayTransport` for the URLs it is
    handed.
    """
    def _factory(urls=None, env=None):
        transport = FakeRelayTransport(
            urls=urls, behaviours=behaviours,
            default_behaviour=default_behaviour, timeout_s=timeout_s)
        transport.env = env
        return transport
    return _factory


# ---------------------------------------------------------------------------
# Self-check — no network, no pytest required
# ---------------------------------------------------------------------------

def _self_check() -> int:
    """Exercise every behaviour and assert the aggregate contract."""
    relay = FakeRelayTransport(
        urls=["wss://nostr.mom", "wss://relay.primal.net", "wss://nos.lol"],
        behaviours={"nostr.mom": HARD_REFUSED, "relay.primal.net": HARD_REJECT},
        default_behaviour=ACCEPT)
    out = relay.send_event_sync({"id": "ab" * 32, "kind": 1059})
    assert out["ok"] is True, out
    assert out["accepted"] == 1, out
    assert out["relay_results"]["nostr.mom"] == "failed: ConnectionRefusedError"
    assert out["relay_results"]["relay.primal.net"].startswith("failed: blocked:")
    assert out["relay_results"]["nos.lol"] == "accepted"
    assert out["event_id"] == "ab" * 32

    # The wire evidence really is a NIP-01 OK quadruple. A connection-refused
    # relay emits NO NIP-01 frame at all (the refusal precedes the wire), so
    # only the two relays that answered are recorded here.
    hosts = [h for h, _ in relay.messages]
    assert hosts == ["relay.primal.net", "nos.lol"], hosts
    assert "nostr.mom" not in hosts, "a refused relay must emit no OK frame"
    ok_accept = [m for h, m in relay.messages if h == "nos.lol"][0]
    assert ok_accept.as_vec() == ["OK", "ab" * 32, True, ""], ok_accept.as_vec()
    ok_reject = [m for h, m in relay.messages if h == "relay.primal.net"][0]
    assert ok_reject.as_vec()[:3] == ["OK", "ab" * 32, False], ok_reject.as_vec()

    # All-relays-refuse -> ok False (the publisher's RelayPublishError signal).
    dead = FakeRelayTransport(urls=["wss://nostr.mom"],
                              default_behaviour=HARD_REJECT)
    out = dead.send_event_sync({"id": "cd" * 32})
    assert out["ok"] is False, out
    assert out["accepted"] == 0, out

    # TIMEOUT blocks until cancelled; the relay never ACKs.
    async def _cancel_after_start():
        slow = FakeRelayTransport(urls=["wss://nostr.mom"],
                                  default_behaviour=TIMEOUT)
        task = asyncio.ensure_future(slow.send_event({"id": "ef" * 32}))
        await asyncio.sleep(0.05)
        assert not task.done(), "TIMEOUT relay responded — must never respond"
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        else:  # pragma: no cover
            raise AssertionError("TIMEOUT send_event did not stay pending")

    asyncio.run(_cancel_after_start())

    # Heal mutation: the refused relay accepts on the next call (the rejected
    # one is left as configured, so accepted goes 1 -> 2).
    relay.set_behaviour("nostr.mom", ACCEPT)
    out = relay.send_event_sync({"id": "11" * 32})
    assert out["accepted"] == 2, out
    assert out["relay_results"]["nostr.mom"] == "accepted", out
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_check())
