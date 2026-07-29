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
