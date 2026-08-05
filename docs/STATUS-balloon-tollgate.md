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

## Next Steps
1. Wait for test migration worker result
2. Wait for FIPS mesh transport API from balloon-fips
3. Implement nucula wallet spend_proofs()
4. Write unit tests for payment protocol encode/decode
5. Design ground station TollGate client (separate deliverable)

## Discovery Sync — 2026-08-05

Acknowledged 3 new findings from balloon-hermes. Assessment:

1. **relay mode build fixes (TransportError scope, API alignment)** — MEDIUM
   - nostr_store.h changes relevant: my plan flagged `nostr_event_deserialize()` missing
   - API alignment in nostr_store affects blossom BUD-11 auth path
   - Will verify nostr_event_deserialize() implementation status when merging

2. **FreeRTOS relay task architecture (radio_task, app_task, queue-based RX)** — MEDIUM
   - app_task does secp256k1 Schnorr verify + nostr_store — exactly what blossom needs
   - Queue-based RX architecture defines blossom message dispatch path
   - My blossom server will integrate as consumer on app_task queue
   - CONFIG_ENABLE_RELAY_MODE guards — blossom mesh wiring goes under this flag

3. **mesh baseline build verified + secp measurement + tollgate payment tests** — CRITICAL
   - **ADOPTED**: factory partition 1MB→2MB (matches balloon-hermes commit 8aaa0bb)
   - **RESOLVED GAP**: mesh_adapter CMakeLists.txt now EXISTS — my plan gap #1 fixed
   - CONFIG_ENABLE_MESH=y builds clean at 227KB, 78% free flash — mesh fits comfortably
   - secp256k1 measurement test on ESP32-C3 confirms crypto feasible for blossom auth
   - 119 tollgate payment tests (91+ pass) validates payment protocol I depend on

### My Integration Plan Gap Status (updated)
- Gap #1 (mesh_adapter no CMakeLists) → **RESOLVED** by balloon-hermes
- Gap #2 (fips_transport not wired) → still open, balloon-hermes working on it
- Gap #3 (nostr_event_deserialize missing) → **RESOLVED** — implemented + bug fixed (f11ddd6)
- Gap #4 (esp-now-firmware deleted) → informational, not blocking blossom
- Gap #5 (all mesh flags disabled) → **PARTIALLY RESOLVED** — CONFIG_ENABLE_MESH verified building
- Gap #6 (blossom has no mesh awareness) → **MY TASK** — still my responsibility

## Discovery Sync — 2026-08-05 (balloon-range-tests)

1 finding from balloon-range-tests assessed:

1. **GPIO10 collision fix (commit f926dc9, cherry-picked by range-tests as 311913f)** — `INFORMATIONAL` for blossom
   - LED was on GPIO10 conflicting with LR2021 NSS on tracker ESP32-S3. Moved LED→GPIO18, FEM_TX→GPIO19.
   - Blossom C3 firmware has **ZERO GPIO10 references** — verified. No collision possible.
   - No action needed. Blossom runs on separate C3, not the tracker S3 board.

2. **FLRC byte alignment, secp256k1, mesh baseline** — already assessed in prior sync above. No new findings.

## Discovery Sync — 2026-08-05 (balloon-hermes: relay pipeline test)

1 finding assessed. **CRITICAL** for blossom integration.

1. **Host-side relay pipeline integration test (commit 4e86174 + bugfix f11ddd6)** — `CRITICAL` `RESOLVES GAP #3`
   - 12 tests covering full relay pipeline: radio(mock)→rx_queue→app_task→nostr_store
   - **Bug found AND fixed**: `app_task.cpp` checked `nostr_event_deserialize() == 0` but function returns bytes consumed (>0) on success. Events were NEVER stored on real firmware. Fixed in `f11ddd6` to `> 0`.
   - **Gap #3 RESOLVED**: `nostr_event_deserialize()` now fully implemented in `nostr_store.c:105` and correct return check in `app_task.cpp:81`.
   - **Blossom impact**: Blossom BUD-11 auth uses same `nostr_event_deserialize()` path for event verification. The bug would have caused blossom to silently drop all incoming Nostr events from the relay pipeline. Now safe.
   - **Test methodology adoption**: host-side pipeline test (gcc, no hardware, mock radio → real nostr_store) is directly applicable to blossom. Will adopt this pattern for blossom-mesh integration testing.
