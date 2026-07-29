# 025-e-hash-relay-transport-layer

## Status

Proposed

## Date

2026-07-29 (corrected scope 2026-07-29)

## Related

- ADR-012 (mesh-networking-strategy) — master mesh architecture, 7-layer stack
- ADR-013 (cluster-aware-stratorelay) — cluster-head election, relay filtering
- ADR-007 (adaptive-protocol) — FLRC/LoRa mode switching by distance
- ADR-008 (telemetry-protocol) — 28-byte packet format reference
- ADR-020 (deprecate-radiolib) — raw 2-byte opcode SPI mandate
- ADR-024 (extract-only-source-repository-policy) — defines balloon scope; this ADR is COMPLIANT (relay transport, NOT mining)
- `mesh-stack/INTEGRATION-ARCHITECTURE.md` — ground station bridge, Nostr-over-FIPS protocol
- `mesh-stack/protocol/SPEC.md` — 7-layer protocol stack, fragmentation, FIPS transport
- `mesh-stack/ROADMAP.md` — throughput targets, MultiWAN bonding

## Context

The balloon mesh network transports internet traffic over LR2021 LoRa/FLRC.
Ground stations without direct internet can already receive Nostr events
and tunnel UDP/IP through the FIPS mesh.

Felix has defined an additional use case: **E-Hash relay transport**. The
balloon relays Bitcoin stratum data between an upstream e-hash proxy and
ground-based tollgate customers. The customer's hash rate (nonce submissions)
IS the payment for balloon internet access — hash power is the currency,
not Ecash.

**The balloon never hashes.** No SHA256 computation. No mining code.
The balloon is a pure transport node within the existing 7-layer mesh stack.
This is ADR-024 compliant — relay/transport is explicitly a balloon function,
mining is explicitly NOT.

### Architecture: Where the Balloon Sits

```
  Mining Pool (Internet)
         ↕  Stratum V1 (TCP)
  ┌──────────────────┐
  │  E-HASH PROXY     │  (ground-side or cloud, handles pool connection)
  │  - stratum client │  - converts hash rate to value
  │  - validates nonces│ - tracks per-customer credits
  └────────┬─────────┘
           ↕  Internet (TCP/WSS)
  ┌────────┴─────────┐
  │  BALLOON          │  ESP32-C3 + LR2021 (in sky)
  │  - L7 relay: template DOWN, nonces UP
  │  - L7 credit check: has customer earned access?
  │  - NO hashing, NO mining code
  │  - Rides existing L1-L6 mesh stack unchanged
  └────────┬─────────┘
           ↕  LR2021 (LoRa sub-GHz or FLRC 2.4GHz)
  ┌────────┴─────────┐
  │  TOLLGATE         │  Ground station (ESP32-C3 or Pi + LR2021)
  │  CUSTOMER         │  + Bitaxe/ASIC miner
  │  - mines against  │  - provides hash rate as payment
  │    relayed template│ - submits nonces up via balloon
  └──────────────────┘
```

The customer wants internet access from the balloon. They pay by mining —
their hash rate funds the balloon's internet relay service via the e-hash
proxy. Block templates flow DOWN so the customer can mine. Nonces flow UP
as proof of work (payment).

### Bandwidth Budget (LR2021 at 300 km)

| Modulation | Air Rate | Net (~40%) | Template (~120-200B) TX Time |
|-----------|----------|------------|------------------------------|
| FLRC 1300 kbps | 1300 kbps | ~520 kbps | <1 ms (short range) |
| LoRa SF9/1625 kHz | 22 kbps | ~9 kbps | ~0.02-0.04 s |
| LoRa SF10/1625 kHz | 12 kbps | ~5 kbps | ~0.04-0.08 s |
| LoRa SF10/125 kHz | 1.0 kbps | ~0.4 kbps | ~0.4-0.5 s |

Template broadcast is one-to-many (downlink). Nonce submissions are
one-to-one uplink, ~21 bytes each.

### Payload Size Fit

Binary-packed block template: ~120-200 bytes. Fits in 1-2 fragments
(242 bytes/fragment max per SPEC.md §6.3). Well within the ~15 KB
fragment layer ceiling.

Nonce submission: 21 bytes. Single fragment, minimal airtime.

The existing Nostr-over-FIPS protocol caps events at 500 bytes, but the
e-hash relay uses dedicated L7 message types that ride the L3 fragment
layer directly — not Nostr events. No size conflict.

## Decision

### 1. New L7 Application: E-Hash Relay Transport

New L7 message types alongside existing Nostr-over-FIPS types:

```
EHASH_TEMPLATE  (0x10) — Binary block template (downlink, broadcast)
EHASH_NONCE     (0x11) — Binary nonce submission (uplink, unicast)
EHASH_RESULT    (0x12) — Proxy response: share accepted/rejected (downlink, unicast)
EHASH_CREDIT    (0x13) — Credit balance update (downlink, unicast)
```

These ride the existing L3-L6 stack (fragmentation → FIPS encryption →
TDMA scheduling → LR2021 radio). NO changes to L1-L6.

### 2. EHASH_TEMPLATE Encoding (Downlink, ~120-200 bytes)

Binary-packed mining.notify fields:

```
Offset  Size  Field
0       1     Protocol version (0x01)
1       4     job_id (uint32, assigned by e-hash proxy)
5       32    prevhash (block header hash)
37      4     version (BTC block version field)
41      4     nbits (difficulty target)
45      4     ntime (BTC network time, 0 = use current)
49      2     coinbase1_len
51      N     coinbase1 (typically ~20-40 bytes)
51+N    2     coinbase2_len
53+N    M     coinbase2 (typically ~20-40 bytes)
53+N+M  1     merkle_branch_count
54+N+M  32*K  merkle_branch hashes
54+N+M+32*K  1  clean_jobs (bool)
```

Fits 1-2 fragments. Ground station reconstructs JSON mining.notify for ASIC.

### 3. EHASH_NONCE Encoding (Uplink, 21 bytes)

```
Offset  Size  Field
0       1     Protocol version (0x01)
1       4     job_id (uint32)
5       4     worker_id (uint16 station ID, padded)
9       4     extranonce2 (uint32, ground-assigned)
13      4     ntime (uint32)
17      4     nonce (uint32)
```

Single fragment. Negligible airtime even at LoRa SF12.

### 4. Credit Model: Hash Rate = Internet Access

The customer mines to EARN balloon internet access. The e-hash proxy
tracks credits:

- Customer submits valid nonce → proxy validates against pool
- Valid share → customer earns credit (internet bytes or time)
- Balloon relays EHASH_CREDIT updates to ground station
- Credit balance gates template delivery: zero credit = no new templates

This inverts the original Cashu model: instead of paying Ecash for access,
the customer PAYS IN HASH RATE. The balloon's role is purely transport —
it relays templates down, nonces up, and credit updates back.

The e-hash proxy (upstream, NOT on balloon) handles:
- Pool stratum connection
- Share validation
- Bitcoin reward collection
- Credit accounting per customer

The balloon only needs to:
- Relay template messages down
- Relay nonce messages up
- Relay credit messages down
- Gate template delivery on credit > 0

### 5. Ground Station: Stratum Bridge Component

The ground station runs a new L7 component alongside existing Nostr relay:

1. Receives EHASH_TEMPLATE via LR2021 → FIPS → L7 handler
2. Reconstructs standard Stratum V1 JSON mining.notify
3. Serves via local TCP socket (localhost:3333)
4. Bitaxe/ASIC connects with stock firmware — no modifications
5. Bitaxe submits shares → ground station encodes as EHASH_NONCE (21 bytes)
6. Queues for next TDMA uplink slot
7. Balloon forwards nonce to e-hash proxy
8. EHASH_RESULT comes back → ground station sends JSON response to Bitaxe

## Invariants

1. **Balloon never hashes.** No SHA256. No mining code. Pure relay.
2. **ADR-024 compliant.** Relay/transport is a balloon function. Mining is NOT.
3. **Rides existing L1-L6 stack.** No radio, fragmentation, FIPS, or routing changes.
4. **Binary encoding over LoRa.** Not JSON. Ground station translates binary ↔ JSON.
5. **Hash rate is the currency.** Customer earns internet by mining, not by paying Ecash.
6. **E-hash proxy handles pool logic.** Balloon does NOT connect to pool directly.

## Consequences

### Positive

- **Fits existing stack.** New L7 message types only. L1-L6 untouched.
- **Tiny payloads.** Template ~120-200B (1-2 fragments), nonce 21B (1 fragment).
- **Customer has skin in the game.** Must mine to maintain access. No freeloading.
- **Balloon stays simple.** Relay logic only. No pool protocol complexity on balloon.
- **Scalable.** Template is broadcast (one TX serves all). Uplink is per-station.

### Costs

- **Latency.** TDMA frame (2s) + LoRa airtime + FIPS overhead. Total RTT: 2-6s.
  Acceptable for pooled mining. Not for low-latency stratum variants.
- **Uplink contention.** Multiple stations submitting nonces compete for TDMA slots.
  Mitigated by local difficulty filter on ground (only high-value shares go up).
- **Credit dependency.** If proxy goes offline, no credits, no templates. Balloon
  should cache last template for a TTL window.
- **Ground station complexity.** Needs stratum-bridge component (~300-500 lines).

## Open Questions

### O1. Stratum V1 vs V2?

V1 = JSON text, Bitaxe-native. V2 = binary, better distribution.
Recommendation: V1. LoRa encoding is protocol-agnostic.

### O2. Share difficulty filtering?

Pool sets difficulty. At LoRa bandwidth, can't relay every share.
Recommendation: Ground station filters to 10× pool difficulty. Fewer shares,
each more valuable.

### O3. Template encryption?

Should templates be plaintext (freeloader sees but can't submit nonces
without relay) or encrypted (no template without earned credit)?
Recommendation: Encrypted with per-session key. Credit check before key delivery.

### O4. Balloon internet loss?

When balloon loses upstream connection to e-hash proxy:
Recommendation: TTL-based expiry. Template carries timestamp. Ground station
pauses mining after configurable TTL without new template.

### O5. Multi-customer credit accounting?

Multiple ground stations mining under one balloon. How does proxy attribute
hash rate to specific customers? Per-station worker IDs in nonce submissions.
Proxy tracks per-worker credits. Standard stratum multi-worker pattern.

## Rollout / Implementation Phases

TBD — awaiting O1-O5 decisions. Proposed:

- **Phase A**: Binary encoding spec (EHASH_TEMPLATE + EHASH_NONCE format)
- **Phase B**: Ground station stratum-bridge prototype (Python on Pi)
- **Phase C**: Balloon relay module (L7 handler: template relay + nonce relay + credit gate)
- **Phase D**: Integration test (e-hash proxy + balloon relay + ground station + Bitaxe)

## Notes

- This ADR was initially written in the wrong repo (tollgate-esp32), deleted,
  then restored here with corrected scope. Original commit: 464d962 on
  tollgate-esp32 balloon-pow-extraction branch (reference only).
- The e-hash proxy is NOT on the balloon. It lives upstream (ground-side or
  cloud) and handles the actual pool connection. The balloon is dumb relay.
- ADR-024 §4 lists "Cashu payment processing" and "captive portal" as
  balloon-relevant. E-Hash relay extends this: instead of Cashu tokens,
  the payment medium is hash rate. The captive portal concept applies —
  customer connects, must mine to earn access.
- StratoRelay cluster-head election (ADR-013) can be reused: only cluster
  heads receive e-hash templates, preventing flood storms.
- ADR-007 adaptive protocol determines LoRa mode. Template delivery time
  depends on active mode. Ground stations track mode and adjust expectations.
