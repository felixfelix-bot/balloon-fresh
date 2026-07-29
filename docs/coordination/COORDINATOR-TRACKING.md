# Balloon Project — Coordinator Tracking

**Purpose:** Track decisions, blockers, and assessment status across all balloon tracks.
Maintained by balloon-hermes orchestrator. Updated as assessments arrive.

**Hierarchy:** 4-layer identity system deployed 2026-07-18.
See TRACKS-REGISTRY.yaml for the single source of truth (10 tracks).

## Assessment Status

| Track | Assessment | Status File | Decisions Surfaced | User Blockers |
|---|---|---|---|---|
| balloon-hermes | N/A (orchestrator) | — | — | — |
| balloon-nostr | MISSING — nudged | — | — | — |
| balloon-tollgate | SUBMITTED (111 lines) | — | — | — |
| balloon-pow | MISSING — nudged | — | — | D-001 (S3 boards) |
| balloon-fips | SUBMITTED (155 lines) | — | — | D-002 (git remote) |
| balloon-blossom | SUBMITTED | — | 7 questions surfaced | See assessment Q1-Q7 |
| balloon-range-tests | MISSING — misnamed file, nudged | — | — | — |
| balloon-speed-tests | MISSING — misnamed file, nudged | — | — | — |
| balloon-pre-stretching | NOT STARTED — needs bootstrap | — | — | — |
| balloon-circuit-design | NOT STARTED — needs bootstrap | — | — | Needs radio pins from balloon-hermes |

## Decisions Needed From Human

(Collected from track assessments as they arrive. Presented to user in batches.)

- D-001: Hardware allocation — 3 S3 boards shared between tollgate + pow. OPEN.
- D-002: microfips git remote — no remote configured. OPEN.

## User Blockers

(Things only the human can resolve. Purchasing, soldering, regulatory, etc.)

- (none yet — waiting for assessments)

## Integration Plan

(Critical path plan built after all assessments arrive.)

- NOT STARTED — waiting for assessments from 5 tracks

## Bootstrap Queue

Tracks that need bootstrapping before they can produce assessments:

1. balloon-pre-stretching — no deps, can start immediately
2. balloon-circuit-design — depends on balloon-hermes radio pin assignments (available in AGENTS.md)
