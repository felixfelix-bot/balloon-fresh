#!/usr/bin/env python3
"""verdict_relay_constants.py — the single source of truth for the verdict
transport's relay failover set.

This module exists so that the canonical relay list lives in **exactly one
place**. It is deliberately tiny and contains nothing but the ordered relay
set and its derived ``wss://`` URL view — no transport code, no SDK import, no
dead-host bookkeeping.

Why a separate module (and why this matters for the regression test)
--------------------------------------------------------------------
``verdict_transport.py`` must *name* the DEAD unnumbered contextvm host in
:data:`verdict_transport.DEAD_RELAYS` in order to filter it out of the active
set. If the canonical relay list lived in that same file, a source-level scan
for the forbidden hostname would always hit the legitimate ``DEAD_RELAYS``
literal and could never be a clean "the wrong host is absent from the relay
source" assertion. By putting the list here — in the file that *defines* the
relay set — the defining source file provably contains **no occurrence** of the
unnumbered contextvm hostname at a hostname boundary.

Relay set (EXACT — do not add, remove, reorder, normalize, lowercase or strip)
-----------------------------------------------------------------------------
``nostr.mom`` → ``relay.primal.net`` → ``nos.lol`` → ``relay2.contextvm.org`` →
``relay.nostr.band``.

The numbered ``relay2.contextvm.org`` is the live member of the contextvm relay
family; the unnumbered host of that same family (the bare family host, with no
``2``) is DEAD (verified 2026-08-23) and must never appear in this set.
"""

from __future__ import annotations

__all__ = [
    "FAILOVER_RELAYS",
    "FAILOVER_RELAY_URLS",
]

#: Ordered relay failover set — EXACTLY these five bare hostnames, in order.
#: The unnumbered contextvm relay host is DEAD and must never appear here
#: (see :data:`verdict_transport.DEAD_RELAYS`).
FAILOVER_RELAYS = [
    "nostr.mom",
    "relay.primal.net",
    "nos.lol",
    "relay2.contextvm.org",
    "relay.nostr.band",
]

#: The same set as ``wss://`` relay URLs (derived — never hand-maintained).
FAILOVER_RELAY_URLS = ["wss://" + host for host in FAILOVER_RELAYS]
