# ADR: E-Hash Relay Transport — LOCKED DECISIONS LOG

## RESOLVED DECISIONS (locked)

### D1. Balloon = relay/transport node only
Balloon never computes SHA256. No mining code on balloon. Pure L7 relay
within existing 7-layer mesh stack. ADR-024 compliant.
(Felix, 2026-07-29)

### D2. Architecture: pool → e-hash proxy → balloon → tollgate customer
E-hash proxy (upstream, NOT on balloon) handles pool connection + share
validation + reward collection + credit accounting. Balloon only relays.
(Felix, 2026-07-29)

### D3. E-hash = bidirectional Ecash economy at every hop
Every participant earns and spends e-hash (Ecash tokens). Miner earns e-hash
for nonces, spends on internet access. Balloon earns e-hash from proxy for
nonces, pays proxy e-hash for templates, earns spread on both legs. Proxy
buys nonces with e-hash, sells templates for e-hash, collects BTC from pool.
(Felix, 2026-07-29, corrected after two iterations)

### D4. Correct repo = balloon-fresh
ADR belongs in balloon-fresh (ESP32-C3 + LR2021 pico balloon project).
Tollgate-esp32 repo is source (READ-ONLY per ADR-024). Relay code extracts
into balloon-fresh only.
(Felix, 2026-07-29)

### D5. New L7 message types, not Nostr events
EHASH_TEMPLATE (0x10), EHASH_NONCE (0x11), EHASH_RESULT (0x12), EHASH_CREDIT (0x13).
Ride L3-L6 unchanged. Bypass 500-byte Nostr event limit.
(Design decision, 2026-07-29)

## RESOLVED (locked 2026-07-29 — Felix answered all)

### D6. Stratum V1 first
V1 = JSON text, Bitaxe-native. Start with V1. LoRa binary encoding is
protocol-agnostic — V2 can layer later without touching radio format.
(Felix, 2026-07-29)

### D7. Local difficulty filter on ground
Ground station runs local higher-difficulty filter. Ground station PAYS for
all its traffic, so filtering reduces its own bandwidth cost. Self-incentivized.
(Felix, 2026-07-29)

### D8. Template encrypted, per-session key after payment
Templates encrypted with per-session key. Miner gets decryption key only after
paying for the connection (e-hash balance check). No payment = no decryption.
(Felix, 2026-07-29)

### D9. TTL pause on internet loss + free local relay access
When balloon loses upstream connection: template TTL expiry, ground station
pauses mining. During outage, ground station gets free access to the local
relay (existing mesh services still work, just no upstream pool connectivity).
(Felix, 2026-07-29)

### D10. Per-nonce e-hash issuance, mint tracks unspent proofs
Balloon gives ground station e-hash token every time it receives a valid nonce.
The Cashu MINT (not the balloon) is responsible for tracking unspent proofs /
double-spend prevention. Per-station worker IDs in EHASH_NONCE for attribution.
(Felix, 2026-07-29)

## STILL OPEN

None. All questions resolved.
