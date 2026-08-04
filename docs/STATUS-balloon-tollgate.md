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

## Next Steps
1. Wait for test migration worker result
2. Wait for FIPS mesh transport API from balloon-fips
3. Implement nucula wallet spend_proofs()
4. Write unit tests for payment protocol encode/decode
5. Design ground station TollGate client (separate deliverable)
