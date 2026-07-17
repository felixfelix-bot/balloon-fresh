# Balloon Project — Track Coordination Hub

## Coordinator
**balloon-hermes Signal group** = top-level coordinator for ALL balloon workstreams.
This is where integration decisions are made and cross-track coordination happens.
All track groups report progress here.

## Track Overview

| Track | Signal Group | Worktree | Source Repo | Status |
|-------|-------------|----------|-------------|--------|
| 1 — Radio Link | balloon-hermes (this group) | ~/repos/balloon-fresh/ | (same) | Active — baseline proven |
| 2 — Nostr Relay | balloon-nostr | ~/worktrees/balloon-nostr | ~/wisp-esp32/ (upstream: privkeyio/wisp-esp32) | Ready to start |
| 3 — Tollgate/Cashu | balloon-tollgate | ~/worktrees/balloon-tollgate | ~/esp32-tollgate/ (OpenTollGate/tollgate-esp32) | Ready to start |
| 4 — PoW/Mining | balloon-pow | ~/worktrees/balloon-pow | ~/esp32-tollgate/main/ (mining components) | Ready to start |
| 5 — FIPS Mesh | balloon-fips | ~/worktrees/balloon-fips | ~/repos/microfips-upstream/ | Ready to start |
| 6 — Blossom Server | balloon-blossom | ~/worktrees/balloon-blossom | (new project) | Ready to start |

## Integration Strategy
1. Each track tests features STANDALONE on ESP32-S3 first (where code already runs)
2. Port each to ESP32-C3 (4MB flash, 400KB RAM — tighter constraints)
3. Final integration into balloon firmware happens HERE in balloon-hermes
4. NO integration work until standalone tests pass per track

## Worktree Rules (MANDATORY)
- ALL worktrees go in ~/worktrees/ — NEVER /tmp (tmpfs = RAM, cleared on reboot)
- Each track has a dedicated worktree with its own branch
- Commit + push ALL changes. Done = pushed. No exceptions.
- Use conventional commit messages. Atomic commits (one concern per commit).

## Handover Documents
- Track 2 (Nostr):      ~/balloon-coordination/handover-balloon-nostr.md
- Track 3 (Tollgate):   ~/balloon-coordination/handover-balloon-tollgate.md
- Track 4 (PoW):        ~/balloon-coordination/handover-balloon-pow.md
- Track 5 (FIPS):       ~/balloon-coordination/handover-balloon-fips.md
- Track 6 (Blossom):    ~/balloon-coordination/handover-balloon-blossom.md

## Kanban Tracking
See ~/balloon-coordination/kanban-board.md for task-level tracking.

## Hardware Inventory
- 20x ESP32-C3_Mini_V1 (USB-C, U.FL antenna) — target platform for balloon
- 3x ESP32-S3 boards — current dev platform for tollgate/nostr/mining
- 4x NiceRF LoRa2021 modules (LR2021 Gen 4) — radio link
- 3x EBYTE E28-2G4M27S (SX1281, 2.4 GHz) — alternative radio
- 2x RP2040 Pico boards (for radio testing)

## Target: ESP32-C3 Constraints (Balloon Flight Hardware)
- Flash: 4MB (vs 16MB on S3)
- RAM: 400KB (vs 8MB PSRAM on S3)
- No PSRAM — all heap allocation must fit in 400KB
- USB-C connector for flashing
- U.FL antenna connector
- Solar + supercap power system
