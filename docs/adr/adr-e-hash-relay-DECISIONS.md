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

### D3. Hash rate IS the payment
Customer mines to EARN balloon internet access. Not Ecash-for-templates.
Hash rate/nonces are the currency. Inverts the Cashu model.
(Felix, 2026-07-29)

### D4. Correct repo = balloon-fresh
ADR belongs in balloon-fresh (ESP32-C3 + LR2021 pico balloon project).
Tollgate-esp32 repo is source (READ-ONLY per ADR-024). Relay code extracts
into balloon-fresh only.
(Felix, 2026-07-29)

### D5. New L7 message types, not Nostr events
EHASH_TEMPLATE (0x10), EHASH_NONCE (0x11), EHASH_RESULT (0x12), EHASH_CREDIT (0x13).
Ride L3-L6 unchanged. Bypass 500-byte Nostr event limit.
(Design decision, 2026-07-29)

## STILL OPEN (awaiting decision)

### O1. Stratum V1 vs V2?
Recommendation: V1 (Bitaxe-compatible, simpler).

### O2. Share difficulty filtering on ground?
Recommendation: Local 10× difficulty filter to conserve LoRa bandwidth.

### O3. Template encryption?
Recommendation: Per-session key, gated by earned credit.

### O4. Balloon internet loss behavior?
Recommendation: TTL-based template expiry, ground station pauses mining.

### O5. Multi-customer credit attribution?
Per-station worker IDs. Standard stratum multi-worker pattern.
