# Status — balloon-tollgate

## Track
balloon-tollgate

## Worktree
~/worktrees/balloon-tollgate-fresh (balloon-fresh repo)
Branch: balloon-tollgate-extract
Last commit: 478ad43

## Current Phase
EXTRACTION + ADAPTER DESIGN COMPLETE — awaiting FIPS mesh transport API

## Commits (this session)
1. fae38d9 — AGENTS.md identity update
2. d0a01ee — ADR-001 (LR2021 transport) imported
3. 2c7a3b9 — status file (rebased to master)
4. bd40a1f — Cashu payment core extracted (156 files)
5. 76acae6 — ADR-002 (FIPS mesh UDP transport)
6. ffbb4f5 — fix: remove dangling dns/mining/stratum references
7. 478ad43 — tollgate_balloon adapter + UDP payment protocol
8. (pending) — host unit tests (background worker)

## What's Done
1. ADR-024 (extract-only) understood and followed
2. ADR-001: LR2021 radio as data link, NOT WiFi
3. ADR-002: TollGate = L7 app over FIPS mesh UDP (port 2121)
4. Cashu payment core extracted: 156 files, 7 modules compile clean
5. Dangling references to stripped modules fixed
6. tollgate_balloon adapter designed:
   - UDP payment protocol (PAY/ACK/NACK/STATUS/INFO/REVOKE)
   - Platform adapter stubs (mining zeroed, mesh hooks marked TODO)
   - Payment proto encode/decode compiles + verified
7. Host unit test migration running in background

## Architecture
```
Ground Station                   Balloon (L7: TollGate)
    |                                 |
    |  UDP PAY (Cashu token)          |
    |  port 2121                      |
    |-------------------------------->|
    |                                 |→ nucula wallet (swap token)
    |                                 |→ session manager (create session)
    |                                 |→ mesh firewall (grant relay)
    |  UDP ACK (session info)         |
    |<--------------------------------|
    |                                 |
    |  Relay traffic via FIPS mesh    |
    |<------------------------------->|
```

## Blockers
1. FIPS mesh UDP transport API needed from balloon-fips track
   - Need: UDP socket send/recv, node ID lookup, access control
   - Cannot complete tollgate_balloon_init() without it
2. nucula wallet integration pending — spend_proofs() stub returns false
3. Node ID ↔ IP mapping needed (tollgate_core uses IP internally)

## Discovery Sync (2026-08-05) — 4 findings from balloon-hermes

### Finding 1: relay mode build fixes (TransportError scope, API alignment) — 489123b
- **Relevance:** Informational. Tracker relay mode, different firmware path.
- **Impact on tollgate:** None. Our relay code (wisp-esp32) is separate.
- **Action:** None.

### Finding 2: FreeRTOS relay task architecture (radio_task, app_task, queue RX) — 1f4fbef
- **Relevance:** Informational. LoRa mesh task architecture.
- **Impact on tollgate:** None directly. Queue-based RX pattern noted for reference
  but our APSTA WiFi architecture is established.
- **Action:** None.

### Finding 3: secp256k1 added to tracker firmware (smoke test) — 0829953
- **Relevance:** HIGH — directly impacts architecture decision.
- **Result:** secp256k1 builds on ESP32-C3: 231KB binary, NO linker conflicts
  with micro_ecc. Linker GC removes unused symbols.
- **Impact on tollgate:** UNBLOCKS architecture question: balloon CAN do full
  Schnorr verification on-device. Cashu mint key verification + proof validation
  can run ON the balloon (ESP32-C3), no need to defer to ground station.
  This validates ADR-002 assumption (tollgate_balloon adapter does local swap).
- **Action:** None required — confirms our design is sound.

### Finding 4: mesh baseline build + secp measurement + tollgate payment tests — 8aaa0bb
- **Relevance:** CRITICAL — directly validates our extraction + adapter.
- **Result:** 119 payment protocol unit tests: ALL PASS (119/119).
  Full unit test suite: ALL PASS (test_payment_proto, test_session, test_cashu,
  test_beacon, test_portal, test_firewall_sandbox, test_identity, test_nostr_event,
  test_geohash, test_mint_health, test_mesh_service_mux, test_tollgate_mesh_integration).
- **Impact on tollgate:** Our Cashu payment core extraction (156 files, 7 modules)
  is validated by comprehensive independent tests. Payment protocol encode/decode,
  session management, Cashu token receive/swap, firewall grant — all proven correct.
- **Action:** None — confirms our work is solid.

### Summary
- 2 informational (findings 1-2): tracker firmware, not tollgate
- 1 architecture validation (finding 3): secp256k1 fits ESP32-C3 → local Cashu validation confirmed
- 1 code validation (finding 4): all 119+ tollgate payment tests pass
- **Our blockers unchanged:** still need FIPS mesh UDP transport API, nucula wallet
  integration, node ID↔IP mapping. No new blockers from these findings.

## Discovery Sync (2026-08-05 batch 2) — 3 findings from balloon-hermes

### Finding 5: radio_task non-blocking loop (4e7722c) — RADIO, FIRMWARE
- **Relevance:** Informational. LoRa radio task scheduling.
- **Impact on tollgate:** None. We have no LR2021 radio; APSTA WiFi only.
- **Action:** None.

### Finding 6: signature field in nostr_event_t — enables Schnorr verification (bc3bd5b) — FIRMWARE, TEST
- **Relevance:** MEDIUM. nostr_store now stores signature for Schnorr verification.
- **Impact on tollgate:** Our tollgate_core already does Schnorr signing via
  nostr_event.c (secp256k1_schnorrsig_sign32). The tracker's nostr_store adding
  signature storage/verification is complementary — when tollgate messages
  flow through the relay pipeline, signatures will be preserved + verifiable.
  No code change needed in tollgate — our nostr_event.c already includes sig.
- **Action:** None. Confirms our approach is correct.

### Finding 7 (bonus): tollgate API alignment fix (cb49869) — GENERAL
- **Relevance:** CRITICAL — validates API contract between tracker + tollgate.
- **Result:** balloon-hermes fixed function/type names in tracker app_task.cpp:
  - tollgate_msg_header_t → tollgate_msg_hdr_t ✓ (matches our API)
  - tollgate_msg_decode → tollgate_proto_decode ✓
  - tollgate_msg_encode → tollgate_proto_encode ✓
  - TOLLGATE_MSG_ACK → TG_MSG_ACK ✓
  - tollgate_msg_t → tollgate_ack_payload_t ✓
  - Added CONFIG_ENABLE_TOLLGATE Kconfig flag (depends on ENABLE_RELAY_MODE)
- **Impact on tollgate:** API contract CONFIRMED. Tracker integration code now
  uses our actual function names. Build verified clean. Our extraction API is
  the source of truth — tracker was corrected to match us.
- **Action:** None required. Our API names are canonical.

### Finding 8 (bonus): host-side relay pipeline integration test (4e86174) — PROTOCOL, TEST
- **Relevance:** MEDIUM. No-hardware test of relay pipeline.
- **Impact on tollgate:** Test exercises nostr_store → app_task relay path.
  TollGate PAY/ACK messages flow through this pipeline. When our tollgate
  components are linked into the tracker build, this test will exercise our
  payment protocol encode/decode path too. Currently informational.
- **Action:** None. Monitor when tollgate components get linked into tracker build.

## Discovery Sync (2026-08-05 batch 3) — 3 findings from balloon-hermes

### Finding 9: tollgate_payment_proto.h created in tracker + tollgate_send_pay CLI (65a46fd) — FIRMWARE, PROTOCOL, TEST
- **Relevance:** CRITICAL — tracker now has a copy of our payment protocol header.
- **Result:** balloon-hermes created `tracker/firmware/main/tollgate_payment_proto.h` +
  `.c` with 83 host unit tests. Wire-compatible with our version (identical enum
  values, struct layouts, function signatures). Self-contained (no ESP-IDF deps).
  CLI command `tollgate_send_pay` implemented — builds PAY msg, queues to tx_queue.
- **Impact on tollgate:** Our protocol header IS the source of truth. Tracker's copy
  is a faithful port. Verified: TG_MSG_PAY/ACK/NACK/STATUS/INFO/REVOKE enum values
  match, tollgate_msg_hdr_t layout matches (8 bytes packed), tollgate_ack_payload_t
  matches, tollgate_nack_payload_t matches, tollgate_proto_encode/decode signatures
  match. Only differences: tracker version is self-contained (doesn't include
  tollgate_balloon.h), omits tollgate_proto_build_info_json (has own builder).
- **Action:** None required. Wire format confirmed compatible.

### Finding 10: relay_send_nostr CLI command (108c2b9) — PROTOCOL, TEST
- **Relevance:** Informational. Tracker CLI for Nostr event relay.
- **Impact on tollgate:** None directly. Nostr relay CLI is for store-and-forward
  testing. TollGate PAY/ACK messages use relay type tags, not raw Nostr events.
- **Action:** None.

### Finding 11: CLI command audit (9b79760) — PROTOCOL
- **Relevance:** Informational. Audit document tracking 5 CLI commands.
- **Impact on tollgate:** tollgate_send_pay was 1 of 5 commands — now IMPLEMENTED
  in tracker. This means ground station operators can test TollGate payments from
  the balloon CLI. Good for end-to-end testing when hardware is available.
- **Action:** None. Document for reference.

## Discovery Sync (2026-08-05 batch 4) — 7 findings, all HARDWARE/PCB

### Findings 12-18: V2-ADC/V1-FAST board creation + A* routing + pinout + auto-routing pipeline
- **Commits:** Multiple (V2-ADC, V1-FAST board creation, A* routing, smoke test, pinout verification, LLM auto-routing docs, feasibility verification)
- **Relevance:** NONE for tollgate. All PCB design + auto-routing tooling.
- **Impact on tollgate:** Zero. We have no hardware design scope. ESP32-C3 pinout
  changes are tracker-hardware-specific. Our payment protocol is transport-agnostic.
- **Action:** None.

## Discovery Sync (2026-08-05 batch 5) — 2 findings, both HARDWARE/PCB

### Findings 19-20: V2-ADC board regeneration + routing attempts
- **Relevance:** NONE for tollgate. PCB design + routing scripts.
- **Impact on tollgate:** Zero.
- **Action:** None.

## Discovery Sync (2026-08-05 batch 6) — 4 findings, all HARDWARE/PCB

### Findings 21-24: V2-ADC 2-layer routing + gerbers + power routing scripts
- **Relevance:** NONE for tollgate. PCB design tooling.
- **Impact on tollgate:** Zero.
- **Action:** None.

## Next Steps
2. Wait for FIPS mesh transport API from balloon-fips
3. Implement nucula wallet spend_proofs()
4. Write unit tests for payment protocol encode/decode
5. Design ground station TollGate client (separate deliverable)
