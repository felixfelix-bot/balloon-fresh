# ADR-002: TollGate Payment Messages Transport Over FIPS Mesh UDP

**Date:** 2026-07-29
**Status:** ACCEPTED
**Decision Maker:** Felix (operator)
**Related:** ADR-001 (LR2021 as data link), ADR-012 (mesh networking strategy)

## Context

ADR-001 established that the balloon TollGate uses LR2021 radio, not WiFi.
Initial assumption was that TollGate would talk directly to the LR2021 driver.

Reading the mesh-stack architecture (AGENTS.md, INTEGRATION-ARCHITECTURE.md,
ADR-012) revealed that the balloon has a full network stack:

```
L7: TollGate + Nostr  (Cashu payments + async messaging)
L6: FIPS Noise XK     (end-to-end encrypted sessions)
L5: FIPS mesh routing (spanning-tree + bloom-filter discovery)
L4: UDP/IP tunnel     (transport over FIPS mesh)
L3: Wirehair + sx1280-serial fragmentation (erasure coding)
L2: TDMA dual-band    (Sub-GHz + 2.4 GHz scheduler)
L1: LR2021 radio      (LoRa/FLRC dual-band)
```

TollGate is an L7 application. It does NOT touch LR2021 directly.
It sends payment messages as UDP packets through the FIPS mesh network.

## Decision

**TollGate communicates via UDP over the FIPS mesh transport layer, not
via direct LR2021 radio access.**

This means:
1. TollGate needs a UDP socket interface (standard ESP-IDF `esp_http_client`
   or lwIP UDP sockets), NOT an LR2021 driver API.
2. Payment messages are packaged as UDP datagrams, routed by FIPS mesh
   to ground stations or other balloons.
3. The FIPS mesh handles fragmentation (Wirehair), encryption (Noise XK),
   routing, and TDMA scheduling. TollGate is unaware of radio details.
4. TollGate's existing HTTP API endpoints (POST / for payment, GET /mints,
   GET /wallet) can be adapted to serve over the mesh UDP path instead of
   a WiFi HTTP server.

## Implications

### What This Simplifies
- No need to design a custom LR2021 payment protocol — reuse UDP/IP
- TollGate code stays close to original (HTTP/UDP based, just different transport)
- Standard socket programming, no radio driver coupling
- FIPS handles reliability (Wirehair erasure coding handles 30-37% packet loss)

### What This Changes
- Captive portal HTML page no longer served over WiFi — clients connect
  to the mesh and access TollGate via UDP. Payment UI moves to client app.
- The DNS hijack and WiFi AP code is truly unnecessary for balloon TollGate
- Identity derivation (nsec → MAC/SSID/IP) adapts: SSID/IP become mesh address

### What Stays Unchanged
- Cashu token processing (nucula wallet) — transport agnostic
- Session management — same logic, different transport
- Mint health checking — HTTP to mint URL over internet (when balloon has uplink)
- Nostr event signing — same crypto

## Consequences

1. The tollgate_esp platform adapter needs to expose a UDP socket interface,
   not WiFi AP/HTTP server. The platform abstraction (tollgate_platform.h)
   was designed for exactly this — we implement new platform functions for
   mesh transport.
2. The captive_portal.c and dns_server.c files are NOT needed for balloon
   (confirmed: they were already not extracted). Payment flow becomes a
   UDP message handler, not an HTTP form handler.
3. Ground station software needs a TollGate client that speaks the UDP
   payment protocol — this is a separate deliverable.
4. Integration testing requires a running FIPS mesh (dependency on
   balloon-fips/balloon-firmware tracks).

## Open Questions

1. What UDP port does TollGate listen on? (Propose: 2121, matching the
   existing tollgate_api HTTP port)
2. Payment message format: JSON over UDP? CBOR? Protocol buffers?
   (Propose: JSON initially — matches existing tollgate_api format)
3. Does TollGate need to handle message ordering/retries, or does FIPS
   mesh guarantee delivery? (Wirehair handles loss, but ordering TBD)

## Related

- ADR-001: LR2021 as data link (supersedes WiFi)
- ADR-012: FIPS + MeshCore + TollGate + Nostr mesh strategy
- mesh-stack/INTEGRATION-ARCHITECTURE.md: full network stack definition
- ADR-024: extract-only source repository policy
