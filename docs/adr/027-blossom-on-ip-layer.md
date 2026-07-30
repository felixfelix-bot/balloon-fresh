# ADR-027: Blossom Server Stacks on IP Layer — Not Raw Mesh Datagram

**Date:** 2026-07-30
**Status:** ACCEPTED
**Decision Maker:** Felix (operator)

## Context

A `blossom_datagram` component (commit `7971810`, balloon-range-tests track)
was introduced on master. It defines a compact binary protocol for
PUT/GET/RESPONSE/ERROR blob operations directly over mesh datagram transport,
using injected function pointers for storage/auth/load backends.

This created an architectural question: should the Blossom server
(Track 6, balloon-blossom) adopt `blossom_datagram` as an alternative
transport, bypassing the IP stack to operate directly over LR2021 mesh
datagrams?

## Decision

**Blossom stays on IP. Do not adopt blossom_datagram.**

The Blossom server (BUD-01/02/11) runs over HTTP on the IP layer provided
by the FIPS mesh stack. The `blossom_datagram` component is informational
only — not integrated into the blossom track.

## Rationale

1. **Interoperability.** Blossom (BUD-01/02/11) is an HTTP-based protocol.
   Standard Nostr clients and Blossom servers communicate over HTTP.
   Bypassing IP with a custom binary datagram protocol makes balloon nodes
   non-interoperable with the broader Blossom ecosystem.

2. **Layer separation.** The balloon mesh stack is a 7-layer architecture:
   L1-L2 radio, L3 datalink, L4 network, L5 transport, L6 session, L7
   application. Blossom is an L7 application protocol. It belongs on top
   of IP (L4) + TCP/HTTP (L5-L6), not wedged into the transport layer.

3. **Collapse prevention.** Allowing application protocols to bypass the
   network stack creates tightly coupled, non-portable code. Each new
   application would need its own datagram protocol. This is the anti-pattern
   that layered architectures exist to prevent.

## Dependency Chain (Unchanged)

```
FIPS mesh (Phase 5: two-node test)
  → IP connectivity over LR2021
    → HTTP server (esp_http_server on port 80)
      → Blossom BUD-01/02/11 endpoints
```

Blossom Phase 3 (hardware test) remains blocked on FIPS providing IP layer.

## Status of blossom_datagram Component

- Remains on master (authored by balloon-range-tests track)
- Not compiled into blossom-server firmware
- Not referenced by blossom-server CMakeLists.txt
- May be used by other tracks for non-Blossom blob relay scenarios

## Related ADRs

- ADR-026: Dual MCU Radio Architecture (defines the radio transport boundary)
- ADR-024: Extract-only source repository policy

## Related Artifacts

- `firmware/blossom-server/` — Blossom HTTP server (Phase 2A-2D complete)
- `tracker/firmware/components/blossom_datagram/` — mesh datagram bridge (not adopted)
- `docs/blossom-design.md` — Blossom server design document
