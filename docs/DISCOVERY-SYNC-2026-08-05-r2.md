# Discovery Sync — 2026-08-05 (Round 2)

## Source: balloon-hermes (5 new findings)

### Assessment for balloon-fips

| # | Finding | Tags | FIPS Impact | Action |
|---|---------|------|-------------|--------|
| 1 | radio_task non-blocking loop — recv timeout_ms param (4e7722c) | RADIO, FIRMWARE | **ADOPTED** | API change to shared lr2021_transport. Added `timeout_ms` param to `recv()`. Default preserves backward compat. Patched in this commit. |
| 2 | signature field in nostr_event_t — Schnorr verification (bc3bd5b) | FIRMWARE, TEST | NONE | nostr_store component (tracker app layer). FIPS meshcore uses ed25519, not secp256k1. No dependency. |
| 3 | host-side relay pipeline integration test (4e86174) | PROTOCOL, TEST | REFERENCE | No-hardware test pattern (mock radio → queue → app_task → nostr_store). Useful pattern for FIPS pipeline testing. Informational. |
| 4 | SPI timing comparison status + discovery sync (b6c2146) | SPI | INFORMATIONAL | C3 vs RP2040 SPI gap analysis. FIPS runs on both platforms. Relevant if SPI throughput becomes bottleneck. |
| 5 | Phase 6 — logic analyzer C3 vs RP2040 SPI timing (4d53713) | SPI | INFORMATIONAL | Logic analyzer comparison plan. Results will inform FIPS platform choice if SPI timing is critical. |

## Action Taken

**Finding #1 required code change.** balloon-hermes modified `Lr2021Transport::recv()` to accept a `timeout_ms` parameter (default: `RADIO_TIMEOUT_MS`). This enables non-blocking radio_task loops with short poll intervals instead of 5s blocking waits.

Applied same change to my lr2021_transport copy:
- `lr2021_transport.h`: Added `uint32_t timeout_ms = RADIO_TIMEOUT_MS` param
- `lr2021_transport.cpp`: Updated signature + replaced `RADIO_TIMEOUT_MS` with `timeout_ms` in poll loop

**Backward compatible** — existing 3-arg calls (tests, fips_bridge) use default timeout. No breakage.

## Findings #2-5: No action required
- nostr_event_t signature field: different component, different crypto
- Relay pipeline test: reference pattern only
- SPI timing docs/plan: informational, results pending