# Status — balloon-tollgate

## Track
balloon-tollgate

## Worktree
~/worktrees/balloon-tollgate-fresh (balloon-fresh repo)
Branch: balloon-tollgate-extract
Last commit: bd40a1f

## Current Phase
EXTRACTION COMPLETE — Payment core extracted into balloon-fresh

## What's Done
1. ADR-024 understood: source repos READ-ONLY, extract-only
2. Migrated to balloon-fresh worktree (branch balloon-tollgate-extract)
3. ADR-001 imported: LR2021 radio as transport (per mesh-stack architecture, TollGate sits at L7 over FIPS mesh UDP transport, NOT direct radio)
4. Master pulled + rebased (has speed-tests + circuit-design consolidation)
5. mesh-stack/tollgate/ integration target confirmed by orchestrator
6. EXTRACTION COMPLETE: 156 C/C++ source files extracted from tollgate-esp32
   - tollgate_core: 7 payment modules (core, cashu, session, portal, firewall, mint_health, beacon)
   - tollgate_esp: ESP-IDF platform implementation
   - nucula_lib: Cashu wallet library + vendored sources
   - secp256k1: libsecp256k1 dependency
   - main/: config, identity, nostr_event, mint_health, geohash
7. EXTRACTION-LOG.md written — complete file-by-file record
8. NOT extracted (left in source): display, mining, stratum, market, DNS, client mode

## Architecture (per mesh-stack AGENTS.md)
TollGate sits at L7 (application layer) over FIPS mesh transport:
L7: TollGate + Nostr (Cashu payments + async messaging)
L6: FIPS Noise XK (E2E encryption)
L5: FIPS mesh routing
L4: UDP/IP tunnel over FIPS mesh
L3: Wirehair + fragmentation
L2: TDMA dual-band scheduler
L1: LR2021 radio

TollGate sends payment messages as UDP packets through FIPS mesh.
Does NOT touch LR2021 directly. Uses mesh transport API.

## Blockers
1. Payment protocol over mesh not designed — what does payment grant? (relay time? bandwidth? message quota?)
2. Integration with tracker/firmware ESP-IDF build not started — need to verify extracted components compile as part of balloon firmware
3. Host unit tests need migration (86 tests exist in source repo, need to verify they run against extracted code)

## Next Steps
1. Verify extracted tollgate_core compiles standalone (ESP-IDF component build)
2. Migrate host unit tests from source repo
3. Design payment protocol over FIPS mesh (ADR-002)
4. Write platform adapter for balloon (replace WiFi-specific platform calls with mesh transport)
