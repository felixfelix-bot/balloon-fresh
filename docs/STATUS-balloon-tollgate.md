# Status — balloon-tollgate

## Track
balloon-tollgate

## Worktree
~/worktrees/balloon-tollgate-fresh (balloon-fresh repo)
Branch: balloon-tollgate-extract
Last commit: c0274b4

## Current Phase
EXTRACTION — Per ADR-024, extracting Cashu payment + captive portal logic from tollgate-esp32 (READ-ONLY source) into balloon-fresh.

## What's Done
1. ADR-024 understood: source repos READ-ONLY, extract-only into balloon-fresh
2. Migrated to new worktree: balloon-tollgate-fresh
3. Master pulled (has speed-tests + circuit-design consolidation)
4. ADR-001 imported: LR2021 radio as transport, NOT WiFi captive portal
5. Scope decisions imported: 11 files to extract, 23 dropped (display/mining/marketplace)
6. tollgate-esp32 branch balloon-tollgate-c3-port has working C3 build proof (1.26MB binary, flashed, WiFi AP confirmed)
7. AP-first boot fix committed (services start without upstream STA)

## Architecture Decision (ADR-001)
Balloon TollGate = LR2021 radio transport + Cashu business logic.
- KEEP: Cashu wallet (nucula), identity, Nostr signing, mint health, geohash
- SWAP: WiFi AP/STA → LR2021 radio, captive portal HTML → radio payment protocol
- DROP: display, mining, stratum, PoW, DNS server, HTTP server

## Cashu Model
Online: nucula wallet swaps tokens against real mint. No blind acceptance.
Offline roadmap: R1 free relay, R2 npub-locked notes, R3 local mint.

## Next Steps
1. Survey balloon-fresh for existing tollgate/payment directory structure
2. Extract Cashu payment core (tollgate_core component) into balloon-fresh
3. Extract captive portal payment logic (adapt for radio transport)
4. Design radio payment protocol (ADR-002 candidate)
5. Coordinate with balloon-range-tests for LR2021 driver API

## Blockers
1. Need LR2021 driver API from balloon-range-tests/balloon-firmware — what's the TX/RX interface?
2. Radio payment protocol not designed yet — what does payment grant? (relay time? bandwidth? message quota?)
3. Felix confirmed: assume online for now, keep simple

## Previous Work (tollgate-esp32, preserved as reference)
- Tag v-balloon-pre-strip at 5b1518f
- C3 build: be0fc3d, binary 1.26MB, 50% flash free
- AP-first fix: 23533e0
- Commit c0274b4 in balloon-fresh imports the decisions as reference docs
