# Integration Assessment — balloon-pow (E-Hash Mining Relay)

**Date:** 2026-08-05
**Assessor:** balloon-hermes orchestrator (delegated)
**Track scope:** Proof-of-work mining relay over LoRa mesh (e-hash transport layer)

---

## Track Scope and Components

Deliver a **balloon-side e-hash relay** that transports Bitcoin mining work
templates (downlink) and nonce submissions (uplink) over the FIPS/LoRa mesh
stack. The balloon is a pure L7 transport node — it **never hashes** (ADR-025 D1).

**Components:**
- `mesh-stack/ehash-bridge/` — Python codec (`ehash_codec.py`) for stratum proxy ↔ binary
- `mesh-stack/ehash-relay/` — C component (ESP-IDF + host testable)
  - `ehash_relay.c` / `ehash_relay.h` — main relay logic
  - `ehash_crypto.c` / `ehash_crypto.h` — template encryption (D8)
  - `ehash_messages.c` — binary message encode/decode (reuses `ehash_messages.h`)
  - `ehash_upstream.c` / `ehash_upstream.h` — proxy connection (mock TCP/stratum)
  - `ehash_radio_stub.c` — radio abstraction for host testing
  - `test/test_ehash_relay.c` — host unit tests (gcc)
- `mesh-stack/protocol/ehash-spec.md` — binary wire format spec (ADR-025 Phase A)
- `mesh-stack/protocol/ehash_messages.h` — packed message structs

## What Works (Proven, Tested)

- ✅ Binary wire format fully specified (ADR-025, 4 message types: TEMPLATE, NONCE, RESULT, CREDIT)
- ✅ Little-endian encoding, 1-byte L7 type tag envelope
- ✅ Radio layer abstracted behind callbacks (`ehash_radio_tx/rx`) — builds on both ESP-IDF and host
- ✅ Host unit tests compile and run with gcc (`test_ehash_relay.c`)
- ✅ Message sizes are small: NONCE=21B, RESULT=7B, CREDIT=16B, TEMPLATE=55–823B
- ✅ Template encryption (D8), per-nonce credit issuance (D10), TTL tracking (D9) designed

## What Doesn't Work (Blockers)

- ❌ **Not integrated with real LR2021 driver.** Uses `ehash_radio_stub.c` — a
     mock. Needs wiring to the proven raw SPI 2-byte opcode driver.
- ❌ **No stratum proxy implementation.** `ehash_upstream.c` uses mock TCP.
     Needs a real stratum `mining.notify`/`mining.submit` bridge.
- ❌ **No hardware validation.** No end-to-end test (proxy → balloon → miner →
     nonce → credit) on actual ESP32-C3 + LR2021 hardware.
- ⚠️ **Template broadcast scheduling not designed.** 823B templates need
     Wirehair fragmentation (L3). Timing/TDMA slot allocation TBD.

## C3 Portability Assessment

**✅ GOOD — fits comfortably on ESP32-C3:**

- All messages are small (7–823 bytes), well within LoRa packet limits
- Relay is L7 transport only — no hashing, minimal CPU/memory
- Radio abstraction means same code runs on host (test) and C3 (deploy)
- Binary format uses native C3 little-endian byte order (no conversion)
- Estimated RAM footprint: <4 KB working set (session state + message buffers)

**Concern:** 823-byte template at the top of the range needs fragmentation. The
L3 Wirehair layer must be available before e-hash can transport full templates.

## What's Next

1. Replace `ehash_radio_stub.c` with real LR2021 driver integration
2. Implement stratum proxy (Python or Go) with `mining.notify` → e-hash TEMPLATE
3. Flash e-hash relay to ESP32-C3, verify message round-trip over LoRa
4. End-to-end test: proxy → balloon → miner → nonce → credit
5. Design TDMA slot allocation for template broadcast vs nonce uplink
6. Validate Wirehair fragmentation with 823B templates
