# 025-balloon-stratum-relay-e-hash

## Status

Proposed

## Date

2026-07-29

## Related

- ADR-012 (mesh-networking-strategy) — master mesh architecture
- ADR-013 (cluster-aware-stratorelay) — cluster-head election, relay filtering
- ADR-007 (adaptive-protocol) — FLRC/LoRa mode switching by distance
- ADR-008 (telemetry-protocol) — 28-byte packet format reference
- ADR-020 (deprecate-radiolib) — raw 2-byte opcode SPI mandate
- `mesh-stack/INTEGRATION-ARCHITECTURE.md` — ground station bridge, Nostr-over-FIPS protocol
- `mesh-stack/protocol/SPEC.md` — 7-layer protocol stack, fragmentation, FIPS transport
- `mesh-stack/ROADMAP.md` — throughput targets, MultiWAN bonding

## Context

The balloon mesh network provides internet transport over LR2021 LoRa/FLRC.
Ground stations in remote areas (no direct internet) can already receive
Nostr events and tunnel UDP/IP traffic through the FIPS mesh.

Felix has identified a use case: the balloon can relay Bitcoin mining data,
acting as a **stratum bridge** for ground-based ASIC miners (Bitaxe,
NerdMiner, or any stratum-compatible device). The concept is called
**E-Hash**: customers pay Ecash for the bandwidth required to relay block
templates (downlink) and nonce submissions (uplink) over the LR2021 link.

The balloon does NOT hash. It never computes SHA256. It is a thin relay
within the existing 7-layer mesh stack.

### System Topology

```
  Mining Pool (Internet)
         ↕  Stratum V1 (TCP)
    ┌────────────────────┐
    │   BALLOON          │  ESP32-C3 + LR2021 (in sky)
    │  - L7 stratum client (upstream TCP to pool)
    │  - L7 block template broadcaster (downlink)
    │  - L7 nonce relay (uplink → pool)
    │  - Cashu payment gateway (E-Hash metering)
    └────────┬───────────┘
             ↕  LR2021 (LoRa sub-GHz or FLRC 2.4GHz)
    ┌────────┴───────────┐
    │ GROUND BASE        │  Full ground station (Pi + LR2021, or ESP32-C3 + LR2021)
    │ STATION            │  - Existing FIPS mesh node + Nostr relay bridge
    │                    │  - NEW: local Stratum V1 server (serves ASIC miner)
    │                    │  - NEW: template decoder → mining.notify
    │                    │  - NEW: share filter + uplink queue
    └────────┬───────────┘
             ↕  USB / serial / local network
    ┌────────┴───────────┐
    │ BITAXE / ASIC      │  Stock firmware, unmodified
    │ MINER              │  Connects to local stratum server on ground station
    └────────────────────┘
```

This extends the existing ground station bridge architecture from
`INTEGRATION-ARCHITECTURE.md` §"Ground Station Bridge" — the ground station
already bridges LoRa ↔ Internet. Stratum relay adds a local stratum server
as a new L7 service on the ground station.

### Bandwidth Budget (LR2021 at 300 km)

| Modulation | Air Rate | Net (~40%) | Block Template (~2 KB) TX Time |
|-----------|----------|------------|-------------------------------|
| FLRC 1300 kbps | 1300 kbps | ~520 kbps | ~31 ms (short range only) |
| LoRa SF9/1625 kHz | 22 kbps | ~9 kbps | ~1.8 s |
| LoRa SF10/1625 kHz | 12 kbps | ~5 kbps | ~3.2 s |
| LoRa SF10/125 kHz | 1.0 kbps | ~0.4 kbps | ~40 s |
| LoRa SF12/125 kHz | 0.25 kbps | ~0.1 kbps | ~160 s |

At V1 (omni, +22 dBm, 300 km): **~9 kbps net** → 2 KB template in ~1.8 s.
With 4× MultiWAN bonding: **~36 kbps** → ~0.45 s.

Template broadcast is one-to-many (downlink broadcast). All paying ground
stations in range receive it simultaneously. Nonce submissions are one-to-one
uplink, ~20 bytes each.

### Payload Size Challenge

Stratum V1 `mining.notify` contains: job_id, prevhash, coinbase1, coinbase2,
merkle_branch[], version, nbits, ntime, clean_jobs. Typical size: **~1-4 KB**.

The existing Nostr-over-FIPS protocol (`SPEC.md` §10) limits events to 500
bytes and rejects larger with `TOO_LARGE`. However, the fragment layer (L3)
supports up to **~15 KB** per block (242 bytes/fragment × 64 fragments).
The stratum relay does NOT use Nostr events — it defines a new L7 message
type that rides the existing L3 fragmentation layer directly.

## Decision

### 1. New L7 Application: Stratum Relay Service

Define new L7 message types alongside the existing Nostr-over-FIPS types
(EVENT, REQ, REPLY, etc.):

```
BLOCK_TEMPLATE  (0x10) — Binary block template (downlink, broadcast)
NONCE_SUBMIT    (0x11) — Binary nonce submission (uplink, unicast)
SHARE_RESULT    (0x12) — Pool response to nonce submission (downlink, unicast)
EHASH_PAYMENT   (0x13) — Cashu token for bandwidth payment (uplink, unicast)
TEMPLATE_KEY    (0x14) — Per-session decryption key for template (downlink, unicast)
```

These ride the existing L3-L6 stack (fragmentation → FIPS encryption →
TDMA scheduling → LR2021 radio). No changes to L1-L6.

### 2. BLOCK_TEMPLATE Encoding (Downlink)

Binary-packed mining.notify fields, NOT JSON:

```
Offset  Size  Field
0       1     Version (protocol version byte = 0x01)
1       4     job_id (uint32, assigned by balloon)
5       32    prevhash (block header hash)
37      4     version (BTC block version field)
41      4     nbits (difficulty target)
45      4     ntime (BTC network time, may be 0 = use current)
49      2     coinbase1_len
51      N     coinbase1 (variable, typically ~20-40 bytes)
51+N    2     coinbase2_len
53+N    M     coinbase2 (variable, typically ~20-40 bytes)
53+N+M  1     merkle_branch_count
54+N+M  32*K  merkle_branch hashes
54+N+M+32*K  1  clean_jobs (bool)
```

Typical total: ~120-200 bytes. Fits in **1-2 fragments** (242 bytes each).
At LoRa SF9/1625 kHz net: ~0.02-0.04 seconds airtime.

This is MUCH smaller than raw JSON stratum. The ground station reconstructs
the JSON `mining.notify` message for the Bitaxe.

### 3. NONCE_SUBMIT Encoding (Uplink)

```
Offset  Size  Field
0       1     Version (0x01)
1       4     job_id (uint32)
5       4     worker_id (uint16 from balloon-assigned station ID, padded)
9       4     extranonce2 (uint32, assigned by ground station)
13      4     ntime (uint32)
17      4     nonce (uint32)
```

Total: 21 bytes. Fits in **single fragment** with room to spare. At LoRa
SF9: <1 ms airtime. Negligible bandwidth cost.

### 4. E-Hash Payment Gateway

Reuse Cashu/TollGate payment model at L7:

- Ground station submits `EHASH_PAYMENT` (0x13) with Cashu token to balloon
- Balloon validates token via existing Cashu infrastructure
- On success, balloon issues `TEMPLATE_KEY` (0x14) — per-session AES key
- Block templates are XOR-encrypted with session key before broadcast
- Only paying stations can decode templates
- Balloon tracks per-station credit balance (block count remaining)

This follows the TollGate captive-portal model: no payment → no access.
Templates are broadcast to all, but only paying stations hold the key.

### 5. Ground Base Station: Local Stratum Server

The ground station runs a new component: **stratum-bridge**:

1. Receives `BLOCK_TEMPLATE` via LR2021 → FIPS mesh → L7 handler
2. Decrypts with session key
3. Constructs standard Stratum V1 JSON `mining.notify`
4. Serves via local TCP socket (default: `localhost:3333`)
5. Bitaxe connects to `stratum+tcp://localhost:3333` — stock firmware, no changes

On nonce submission:
1. Bitaxe submits share via standard `mining.submit` JSON
2. Ground station encodes as `NONCE_SUBMIT` (21 bytes)
3. Applies local difficulty filter (see O3 below)
4. Queues for next TDMA uplink slot
5. Balloon receives, forwards to pool as standard `mining.submit`
6. Pool response → `SHARE_RESULT` back to ground station → JSON to Bitaxe

### 6. Balloon Internet Connection

The balloon needs internet to reach the mining pool. Two options:

- **A) STA WiFi** (if balloon passes over populated area with WiFi)
- **B) Satellite/satellite-IP modem** (future, not in current BOM)

For initial design: the balloon uses whatever upstream connection the mesh
stack already provides (the balloon already bridges LoRa ↔ Internet in the
mesh architecture per `INTEGRATION-ARCHITECTURE.md`).

## Invariants

1. **Balloon never hashes.** No SHA256 computation. Pure relay.
2. **Bitaxe runs unmodified firmware.** All intelligence in ground station + balloon.
3. **Template is broadcast, not unicast.** One LR2021 TX serves all stations.
4. **No template without Ecash payment.** Cashu credit required for decryption key.
5. **Stratum relay is a new L7 app.** No changes to L1-L6 protocol stack.
6. **Binary encoding, not JSON.** Template/nonce use compact binary format over LoRa.
Ground station translates binary ↔ JSON for Bitaxe compatibility.

## Consequences

### Positive

- **Fits existing stack.** Stratum relay rides L3-L6 unchanged. Only new L7
  message types + ground station stratum server component.
- **Tiny payloads.** Binary template (~120-200 bytes) + nonce (21 bytes) fit
  easily in 1-2 fragments. Negligible bandwidth vs telemetry.
- **Bitaxe-compatible.** Stock firmware. Any stratum V1 ASIC works.
- **Revenue model.** Balloon operator earns Ecash for bandwidth. Miners get
  internet-free pool access.
- **Broadcast efficiency.** Template is one-to-many. Uplink is the only
  per-station cost, and nonces are 21 bytes.

### Costs

- **Latency.** TDMA frame (2s) + LoRa airtime (0.04-1.8s) + FIPS overhead.
  Total relay RTT: 2-6 seconds. Acceptable for pooled mining (Bitaxe at
  ~1-3 TH/s mines for minutes between shares). Unacceptable for
  low-latency GBT/stratum V2.
- **Uplink contention.** Multiple ground stations submitting shares compete
  for TDMA uplink slots. Need TDM scheduling or ALOHA backoff. Mitigated by
  local difficulty filter (fewer shares submitted).
- **Pool account centralization.** All miners under balloon's pool account.
  Balloon operator must distribute earnings. Cashu provides accounting trail.
- **Ground station complexity.** Needs stratum-bridge component (binary decoder
  + JSON stratum server). Estimated ~300-500 lines C++ or Python.
- **Template staleness.** LoRa relay adds latency. By the time template arrives,
  it may be 2-6 seconds old. For small miners this is negligible (probability
  of finding a block in that window is near-zero). For large farms it matters.

## Open Questions (for design session)

### O1. Stratum V1 vs V2 upstream?

V1 = JSON text, Bitaxe-native, simpler. V2 = binary, better template
distribution, but adds protocol complexity.
Recommendation: **V1 for initial implementation.** Binary LoRa encoding is
protocol-agnostic — V2 can be layered later by changing the balloon's upstream
connection without touching the LoRa relay format.

### O2. Pool account / revenue distribution?

Multi-worker pass-through (balloon uses `<pool_user>.<station_id>` worker
naming) vs single operator account with Ecash redistribution?
Recommendation: **Multi-worker pass-through.** Standard stratum feature,
cleaner accounting.

### O3. Share difficulty filtering on ground?

Pool sets share difficulty. At LoRa bandwidth, we cannot relay every share.
Options: ground station runs higher difficulty filter (fewer shares up),
or relay all pool-difficulty shares and accept TDMA contention.
Recommendation: **Local difficulty filter.** Only shares meeting a local
threshold (e.g. 10× pool difficulty) go up. Conserves bandwidth.

### O4. Template access control method?

Plaintext broadcast + payment-gated uplink (weak — freeloader mines for own
pool), or encrypted broadcast + payment-gated decryption key (strong)?
Recommendation: **Encrypted.** XOR/AES with per-session key. Cashu payment
unlocks key delivery. Reuses existing FIPS crypto primitives.

### O5. Balloon loses internet (no upstream)?

When balloon STA WiFi drops, no new templates arrive. Options: TTL-based
template expiry (ground station pauses after TTL without new template),
or keep mining stale and hope.
Recommendation: **TTL pause.** Template carries `ntime` timestamp. Ground
station stops after configurable TTL (default 15 min) without new template.

## Rollout / Implementation Phases

TBD — implementation not yet started. Awaiting decisions on O1-O5.

Proposed phases:

- **Phase A**: Binary encoding spec (BLOCK_TEMPLATE + NONCE_SUBMIT format
  definition, ground station reference decoder)
- **Phase B**: Ground station stratum-bridge prototype (Python on Pi: LR2021
  RX → binary decode → JSON mining.notify → TCP server → Bitaxe)
- **Phase C**: Balloon stratum relay module (L7 handler: upstream stratum
  client → binary encode → LR2021 broadcast → Cashu payment gate)
- **Phase D**: Integration test (balloon + ground station + Bitaxe, end-to-end)

## Notes

- This ADR extends the existing mesh stack architecture (ADR-012). The stratum
  relay is a new L7 application — it does not change the radio, fragmentation,
  FIPS, or routing layers.
- The existing ground station bridge (`INTEGRATION-ARCHITECTURE.md`) already
  connects LR2021 ↔ Internet via FIPS mesh. The stratum-bridge component is
  an additional L7 service on the ground station, parallel to the existing
  Nostr relay bridge.
- StratoRelay cluster-head election (ADR-013) can be reused: only cluster
  heads act as stratum ground stations, preventing template flood storms.
- ADR-007 adaptive protocol determines which LoRa mode is active. Template
  delivery time depends on the active mode (FLRC = instant, LoRa SF12 = 160s).
  Ground stations should track mode and adjust TTL accordingly.
- Felix's vision: E-Hash = Ecash + hashpower. Balloon provides infrastructure
  (internet relay) as metered Ecash service. Ground miners provide hashpower
  and pay for uplink bandwidth.
