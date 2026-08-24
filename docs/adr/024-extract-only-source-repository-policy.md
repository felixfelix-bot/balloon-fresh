# ADR-024: Extract-Only Source Repository Policy

**Date:** 2026-07-29
**Status:** ACCEPTED
**Decision Maker:** Felix (operator)

## Context

The balloon project draws components from multiple ESP32 repositories that were built for OTHER contexts (tollgate payment terminals, microfips mesh, wisp nostr relay, blossom storage). These source repos contain valuable work that serves purposes beyond balloons:

- **tollgate repo:** ESP32-S3 captive portal, Cashu payment, WiFi/ESP-NOW, display UI, stratum v2, proof of work — designed for physical payment terminals (bidax etc.)
- **microfips repo:** FIPS mesh transport, ESP-NOW, Noise handshake, BLE L2CAP — designed for general mesh networking
- **wisp repo:** ESP32 nostr relay — designed for standalone relay nodes
- **blossom repo:** BUD-02 media upload — designed for general Blossom servers

During early development, sub-managers caused confusion by treating these source repos as balloon-exclusive. Some attempted to modify, strip, or repurpose source repos for balloon needs, risking the integrity of work valuable in other contexts.

## Decision

**All source repositories are READ-ONLY for balloon sub-managers.** The policy is EXTRACT-ONLY:

1. **DO NOT modify, delete, strip, or repurpose any source repository.** Source repos serve multiple contexts beyond balloons.

2. **PORT only balloon-relevant components** into the balloon repo (`~/repos/balloon-fresh/`). Copy the needed code, adapt it, commit it to the balloon repo.

3. **LEAVE everything balloon-irrelevant in the source repo.** If a component isn't needed for balloon flight, don't bring it. Don't remove it from the source either.

4. **What belongs on a balloon** (balloon-relevant):
   - LR2021 radio transport (raw 2-byte opcode SPI)
   - Lightweight Cashu payment processing (no display)
   - Captive portal (payment collection)
   - Nostr event relay (lightweight, for balloon telemetry)
   - Blossom media upload (for balloon imagery/data)
   - GPS position reporting
   - Solar/supercap power management

5. **What does NOT belong on a balloon** (leave in source repo):
   - Display drivers / UI components
   - Stratum v2 / proof of work / mining
   - ESP-NOW (unless needed for balloon mesh specifically)
   - bidax-specific features
   - Any component requiring hardware not present on a balloon

## Rationale

- Source repos represent significant development effort for non-balloon products
- Modifying source repos to be balloon-only destroys their value in other contexts
- The balloon repo should be a clean, self-contained project with only what it needs
- This separation prevents scope creep and keeps both balloon and non-balloon work healthy

## Consequences

- Sub-managers must COPY code into the balloon repo, not reference source repos as dependencies
- The balloon repo may have some code duplication with source repos — this is acceptable
- Source repos remain available for their original purposes without balloon-specific contamination
- Git history in source repos is preserved exactly as-is

## Enforcement

- Any pull request or commit that modifies a source repo (tollgate, microfips, wisp, blossom) from a balloon worktree MUST be rejected
- Sub-manager AGENTS.md files must reference this ADR
- The orchestrator will not delegate tasks that require source repo modification

## Affected Repositories

| Source Repo | Balloon-Relevant Components to Extract | Leave in Source |
|-------------|---------------------------------------|-----------------|
| tollgate (ESP32-S3) | Captive portal, Cashu payment | Display, stratum v2, PoW, bidax UI |
| microfips | LR2021 transport layer | ESP-NOW-only, BLE-only features |
| wisp (nostr relay) | Lightweight event relay | Full relay features, admin UI |
| blossom | Media upload/storage | Server admin, quota management UI |
