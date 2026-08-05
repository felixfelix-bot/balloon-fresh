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

### Summary (Batch 1)
- Finding 3 most actionable: mesh baseline builds + fits relay
- Finding 2 future relevance for credit signing
- Finding 1 not applicable to e-hash transport
- No blockers, no cross-track coordination needed

---

## Discovery Sync Acknowledgment (2026-08-05, Batch 2)

### 2 New Findings Analyzed

**1. [balloon-hermes] radio_task non-blocking loop — short recv timeout + tx_queue poll [RADIO, FIRMWARE]**
- Commit: 4e7722c
- Relevance: HIGH
- `lr2021_transport::recv()` now accepts `timeout_ms` parameter (was hardcoded 5000ms)
- radio_task loop: TX queue poll (non-blocking, priority) → RX recv with 100ms timeout → no vTaskDelay needed
- **Direct impact on e-hash relay:**
  - My ehash_radio_stub.c mock will be replaced with real LR2021 driver. The recv() timeout API change affects my radio abstraction interface.
  - The TX-priority-then-RX-short-timeout pattern is exactly what e-hash relay needs: nonce uplink (TX) should preempt template downlink (RX)
  - When I wire ehash_radio_rx() to real driver, I should use short timeout (100ms) not block indefinitely
- Action: Update ehash_radio_stub.h recv signature to include timeout_ms parameter. Mirror the tx_queue priority pattern in e-hash relay task loop.

**2. [balloon-hermes] signature field added to nostr_event_t — Schnorr verification [FIRMWARE, TEST]**
- Commit: bc3bd5b
- Relevance: MODERATE
- nostr_event_t now carries `sig[64]` (BIP-340 Schnorr). Serialize header: 72→136 bytes.
- Tests verify byte-exact sig roundtrip with recognizable fill pattern.
- **Impact on e-hash relay:**
  - Per ADR-025 D1: balloon never hashes, never verifies signatures. So sig field doesn't change e-hash relay logic.
  - BUT: if e-hash CREDIT messages are later wrapped as Nostr events for store-and-forward, the sig field is now available in the serialization format.
  - Test pattern (fill sig with `id_byte ^ (i & 0xFF)`, assert byte-exact roundtrip) is directly reusable for e-hash message tests.
  - Serialization approach (fixed-size field in header, update min header size) is a pattern to follow if adding optional sig to e-hash CREDIT messages.
- Action: No code change now. Reference test pattern for e-hash credit message tests. Note sig field availability if credits go over Nostr store-and-forward.

### Summary (Batch 2)
- Finding 1 (radio_task non-blocking): HIGH — directly affects e-hash radio abstraction interface design
- Finding 2 (nostr sig field): MODERATE — future credit signing path + test pattern reference
- No blockers created
- No cross-track coordination needed — findings used independently

---

## Discovery Sync Acknowledgment (2026-08-05, Batch 3)

### 1 New Finding Analyzed

**1. [balloon-hermes] tollgate_payment_proto.h + tollgate_send_pay CLI [FIRMWARE, PROTOCOL, TEST]**
- Commit: 65a46fd
- Relevance: HIGH
- Standalone tollgate payment protocol header created: 8-byte packed header (version, type, seq, payload_len, reserved), 6 message types (PAY/ACK/NACK/STATUS/INFO/REVOKE)
- Self-contained, no ESP-IDF deps, host-testable with gcc
- Wire-compatible with mesh-stack/tollgate/components/tollgate_balloon/ (ADR-002)
- Test migrated from mock encode/decode to REAL protocol functions
- **Direct impact on e-hash relay:**
  - TollGate PAY/ACK/NACK pattern is structurally parallel to e-hash CREDIT system
  - My e-hash messages use 1-byte L7 type tag envelope (per ehash-spec.md) vs tollgate 8-byte packed header. Both are L7 protocols over the same relay pipeline.
  - The relay_pipeline test pattern (mock → real proto migration) is exactly what I need when replacing ehash_radio_stub.c with real LR2021 driver
  - `tollgate_proto_encode/decode` API design (buf + buf_len + type + seq + payload) is a good reference for `ehash_msg_encode/decode` consistency
  - The 1-byte relay type tag prefix (RELAY_TYPE_TOLLGATE_PAY etc.) means e-hash messages need their own relay type tags (RELAY_TYPE_EHASH_TEMPLATE, RELAY_TYPE_EHASH_NONCE, etc.) — must coordinate relay type enum space
  - Packed struct + `__attribute__((packed))` pattern matches my ehash_messages.h approach
- Action: (a) Review tollgate_payment_proto.h encode/decode API for consistency with ehash_messages.c. (b) Ensure e-hash relay type tags don't collide with tollgate tags in relay pipeline. (c) Follow mock→real test migration pattern when wiring real LR2021 driver.

### Summary (Batch 3)
- Finding 1 (tollgate payment proto): HIGH — parallel L7 protocol, shared relay pipeline, test pattern reference
- Potential concern: relay type tag enum space needs e-hash entries — flag to orchestrator if integration conflict arises
- No blockers created
- No cross-track coordination needed — findings used independently

---

## Discovery Sync Acknowledgment (2026-08-05, Batch 4)

### 3 New Findings Analyzed

**1. [balloon-hermes] V2-ADC board created — supercap ADC [POWER, FIRMWARE, HARDWARE]**
- Commit: bc8aa63
- Relevance: LOW
- V2-ADC board adds supercap monitoring via ADC. e-hash relay is pure L7 software — no GPIO/ADC dependency.
- Confirms ESP32-C3 as deployment target (already assumed in assessment).
- No action.

**2. [balloon-hermes] V1-FAST board created — minimal, no ADC [FIRMWARE, HARDWARE]**
- Commit: 8c46d99
- Relevance: LOW
- V1-FAST is the stripped production board. Same as V2-ADC — hardware design, no impact on e-hash software.
- No action.

**3. [balloon-hermes] ESP32-C3 MINI-1 pinout verification + V2-ADC pinmap [FIRMWARE, HARDWARE]**
- Commit: 4b7203b
- Relevance: MODERATE
- Critical corrections to C3 MINI-1 understanding:
  - GPIO8 has NO ADC channel (V2-ADC plan was broken, corrected to GPIO0/ADC1_CH0)
  - GPIO18/GPIO19 ARE broken out on MINI-1 (pins 26/27) — usable when USB disabled
  - GPIO0 is NOT a strapping pin on C3 (unlike ESP32/S3) — safe for ADC/GPIO
  - Strapping pins: GPIO2 (float), GPIO8 (float), GPIO9 (weak pull-up)
- **Impact on e-hash relay:**
  - e-hash relay is L7 software, no direct GPIO dependency. But if relay needs a status LED or debug pin in future, this pinout is the reference.
  - SPI pins for LR2021 are already allocated by tracker firmware. e-hash relay uses radio via transport abstraction — no pin awareness needed.
  - Confirms C3 MINI-1 as module — my assessment's C3 portability analysis (78% free, <4KB RAM) applies to this exact module.
- Action: Note pinout for future hardware reference. No code change.

### Summary (Batch 4)
- All 3 findings are hardware/PCB focused — LOW to MODERATE relevance to e-hash software relay
- Key takeaway: ESP32-C3 MINI-1 pinout verified, confirms deployment platform assumptions
- No blockers, no code changes needed
- No cross-track coordination needed
