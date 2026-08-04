# Status — balloon-pow (E-Hash Mining Relay)

## Track
balloon-pow

## Worktree
~/worktrees/balloon-pow (balloon-fresh repo)
Branch: balloon-pow/dev
Last commit: 41369a5

## Current Phase
E-HASH RELAY PROTOTYPED — integration assessment done, awaiting mesh radio integration

## What's Done
1. ADR-025 E-Hash mining relay design (balloon = L7 transport, never hashes)
2. Binary wire format: 4 message types (TEMPLATE, NONCE, RESULT, CREDIT)
3. `mesh-stack/ehash-bridge/` — Python stratum proxy codec + mock template
4. `mesh-stack/ehash-relay/` — C relay component (ESP-IDF + host testable)
5. `mesh-stack/protocol/ehash-spec.md` — wire format spec
6. Host unit tests compile + run (gcc)
7. C3 portability assessment: GOOD (<4KB RAM, fits 78% free mesh baseline)
8. Integration assessment written + committed (41369a5)

## Blockers
1. ehash_radio_stub.c is a mock — needs real LR2021 driver wiring
2. No stratum proxy implementation (ehash_upstream.c uses mock TCP)
3. No hardware validation (no end-to-end on actual ESP32-C3)
4. Template encryption is XOR placeholder — needs AES-128 CTR
5. TDMA slot allocation for template broadcast TBD

## Next Steps
1. Replace ehash_radio_stub with real LR2021 driver callbacks
2. Implement Python stratum proxy (mining.notify → e-hash TEMPLATE)
3. Integrate AES-128 CTR for template encryption (ESP-IDF mbedTLS)
4. Flash to ESP32-C3, verify message round-trip
5. End-to-end: proxy → balloon → miner → nonce → credit

## Discovery Sync Acknowledgment (2026-08-05)

### 3 New Findings Analyzed

**1. [balloon-hermes] relay mode build fixes — TransportError scope, API alignment [FIRMWARE, PROTOCOL]**
- Relevance: LOW
- nostr_store TransportError scope is in tracker firmware relay mode. My e-hash relay uses its own message format (TEMPLATE/NONCE/RESULT/CREDIT), not Nostr events. Different transport stack.
- No action needed.

**2. [balloon-hermes] secp256k1 component added to tracker firmware (smoke test) [FIRMWARE, TEST]**
- Relevance: MODERATE
- secp256k1 now available as ESP-IDF component for ESP32 builds. My ehash_crypto.c currently uses XOR placeholder — needs AES-128 CTR (mbedTLS), NOT secp256k1 (asymmetric). However:
  - If per-nonce credits (D10) later use Schnorr signatures, secp256k1 is now available
  - Component build methodology (CMakeLists.txt pattern) is reusable for ehash-relay component integration
- Action: Reference secp256k1 component CMakeLists pattern when integrating ehash-relay into tracker firmware build

**3. [balloon-hermes] mesh baseline build verified + secp measurement test + tollgate [FIRMWARE, PROTOCOL, TEST]**
- Relevance: HIGH
- **"mesh baseline build verified (227KB, 78% free)"** — confirms mesh stack builds on ESP32-C3 with 78% flash free. My e-hash relay (<4KB RAM) fits comfortably. Removes a deployment uncertainty.
- **"secp measurement test"** — secp256k1 Schnorr verify flash/RAM cost measured on C3. Relevant for future credit signing if using Schnorr. Not blocking — my relay is L7 transport, no signature verification needed on balloon per ADR-025.
- **"119 tollgate payment tests (91+ pass)"** — tollgate payment protocol parallel to my e-hash credit system. Test patterns (encode/decode round-trip, edge cases) are reusable.
- Action: (a) Verify e-hash relay integrates cleanly into 227KB mesh baseline. (b) Study tollgate payment test patterns for e-hash credit test design.

### Summary
- Finding 3 is most actionable: mesh baseline builds + fits my relay
- Finding 2 has future relevance for credit signing
- Finding 1 not applicable to e-hash transport
- No blockers created by these findings
- No cross-track coordination needed — findings used independently
