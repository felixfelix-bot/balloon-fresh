# MASTER COORDINATION DOCUMENT
# balloon-hermes Signal Group — Top-Level Coordinator
# Created: 2026-07-17

## PURPOSE

This group (balloon-hermes) is the **top-level coordination hub** for all
workstreams. It is NOT a workstream itself. It coordinates, integrates,
and resolves cross-workstream dependencies.

All workstream groups answer to this session. Integration happens here.

## WORKSTREAM MAP

| # | Workstream | Signal Group | Kanban Board | Primary Repo | Worktree |
|---|-----------|-------------|-------------|-------------|----------|
| 1 | ESP32-S3 TollGate | (TBD) | `esp32-tollgate` | ~/repos/org-scan/tollgate-esp32/ | ~/worktrees/ws-esp32-tollgate/ |
| 2 | microFIPS Mesh | (TBD) | `microfips` | ~/repos/microfips/ | ~/worktrees/ws-microfips/ |
| 3 | Balloon/LR2021 | (dedicated groups exist) | `balloon` | ~/repos/balloon-fresh/ | ~/worktrees/ws-balloon/ |
| 4 | TollGate Router | (TBD) | `tollgate-module-basic-go` | ~/repos/physical-router-test-automation/ | ~/worktrees/ws-tollgate-router/ |
| 5 | Plebeian Market | (TBD) | `plebeian-market-e2e-infra` | ~/repos/market/ | ~/worktrees/ws-plebeian-market/ |
| 6 | Torii Continuum | (TBD) | `continuum-agent` | ~/repos/torii-continuum/ | ~/worktrees/ws-torii-continuum/ |
| 7 | TollGate Android | (TBD) | `tollgate-android` | ~/repos/tollgate-android/ | ~/worktrees/ws-tollgate-android/ |
| 8 | net4sats MVP | (TBD) | `configurationwizzard` | ~/net4sats-wizard-go/ | ~/worktrees/ws-net4sats/ |
| 9 | Infrastructure | (TBD) | `devops-infra` | ~/.hermes/bot/ | ~/worktrees/ws-infrastructure/ |
| 10 | Sovereign Shops | (TBD) | `sovereign-shops` | ~/plebeian-shop/ | ~/worktrees/ws-sovereign-shops/ |

## INTEGRATION MANDATE

All workstreams MUST:

1. **Use proper worktrees** — All git work goes in `~/worktrees/ws-<name>/`.
   NEVER use `/tmp` (tmpfs = RAM-backed, cleared on reboot).
   Worktrees are created from the primary repo with dedicated branches.

2. **Push all work** — Unpushed work = lost work. Commit + push to remote.
   Shared repos = branch + PR. Own repos = push to main.

3. **Report to balloon-hermes** — Each workstream group reports status,
   blockers, and integration needs to THIS session. balloon-hermes resolves
   cross-workstream dependencies and sequences integration.

4. **Integration happens here** — When work from multiple workstreams needs
   to be combined (e.g., ESP32 firmware + router backend + Android app),
   the integration plan is defined and verified in this group.

5. **Scrub PII** — No real names, nsec keys, Signal numbers, or personal
   info in public repos, nsytes, dashboards, or nostr events.

## COORDINATION PROTOCOL

When a workstream needs help:
1. Post status + blocker in their dedicated Signal group
2. If cross-workstream dependency: escalate to balloon-hermes
3. balloon-hermes creates/links kanban tasks to track resolution
4. Resolution verified before marking complete

## HOST ALLOCATION

| Host | Role | Constraint |
|------|------|-----------|
| T470 | Manager + Hermes bot | NEVER external automation |
| DQ05 | Builds, Docker tests | NEVER external automation |
| VPS1 | Continuum, tollgate services | External automation OK |
| VPS2 | Backend services, scraping | ONLY host for Playwright/scraping |

## HANDOVER DOCS

Each workstream has a handover document at:
`~/coordination/handover-<workstream>.md`

These are self-contained — a fresh LLM session can bootstrap from them
without conversation history. Each contains:
- What the workstream is
- Current state (done, in-progress, blocked)
- Key files and repos
- Integration points with other workstreams
- Coordinator authority statement
