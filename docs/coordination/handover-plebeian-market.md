# HANDOVER: Plebeian Market Workstream

**Created:** 2026-07-17
**Coordinator:** balloon-hermes (top-level coordination hub)
**Authority:** This workstream reports to balloon-hermes. Cross-workstream dependencies are escalated there.

---

## WHAT THIS IS

Plebeian Market (`plebeian.market`) is a decentralized Nostr-native marketplace built
on Bitcoin/Lightning payment workflows. The stack is **React + TanStack + Bun** with
Playwright e2e tests. Key areas:

- **`src/`** — React/TanStack marketplace client (UI, queries, store, nostr I/O)
- **`contextvm/`** — ContextVM service (currency conversion, NIP-53 status, independently deployed)
- **`e2e/`** — Playwright end-to-end tests + scenario fixtures
- **`docs/`** — ADRs, issue notes, handover material
- **`scripts/`** — Bun/shell utility scripts
- **`.github/`** — Actions workflows + issue templates

The fork (`c03rad0r/market`) serves as **STAGING** for issues, ADRs, and PRs targeting
upstream (`PlebeianApp/market`). **Reviewer: Franchovy** (also upstream maintainer).

---

## REPOSITORIES & WORKTREE

| Item | Path / URL |
|------|------------|
| Primary repo | `~/repos/market/` |
| Worktree | `~/worktrees/ws-plebeian-market/` |
| Active branch | `ws/plebeian-market` (worktree), `master` (tracking base) |
| Kanban board | `market` (`hermes kanban boards switch market`) |
| Board (alt) | `plebeian-market-e2e-infra` (empty, reserved) |
| Upstream | `PlebeianApp/market` |
| Fork (staging) | `c03rad0r/market` |
| Franchovy's fork | `Franchovy/plebeian-market` |

**Remotes (in primary repo):**
- `upstream` / `plebian` → https://github.com/PlebeianApp/market.git
- `fork` → https://github.com/c03rad0r/market.git
- `franchovy` → https://github.com/Franchovy/plebeian-market.git

**Sync status (as of 2026-07-17):**
- `fork/master` = `b6869d52` ("docs: add relay pruning runbook #1140")
- `upstream/master` = `8706d74a` ("ops: add read-only relay disk report #1143") — **2 commits ahead of fork**
- Worktree `ws/plebeian-market` tracks `fork/master` at `b6869d52`

**Action needed:** Fast-forward fork master to `upstream/master` (2 commits: relay disk
report ops PRs). Requires authorization to push.

---

## WORKSPACE STRUCTURE

**Package:** `plebeian.market` v0.1.0 (Bun, `bun.lock`)
**Package manager:** Bun (no `packageManager` field in package.json — uses system `bun`)

**Key scripts (from `package.json`):**
- `bun run dev` — Hot-reload dev server on `0.0.0.0`
- `bun run build` — Generate routes + build
- `bun run format:check` — `prettier --check .`
- `bun run test:unit` — Unit tests (`contextvm/`, `src/queries/__tests__/`, `src/lib/__tests__/`)
- `bun run test:integration` — Integration tests (`*.integration.test.ts`)
- `bun run test:e2e` — Playwright e2e suite

**Safe checks** (run without authorization):
- `git diff --check` (whitespace/conflict markers)
- `bun run format:check` (prettier)
- `bun run test:unit` (unit tests — fast)

**Commands requiring explicit approval:**
Build, dev server, e2e suite, deploy, seed data, generators, workflow triggers.

---

## BOARD STATUS: `market`

**Summary:** done=23, blocked=6, archived=27 (no active todo/ready/running tasks)

### Blocked Tasks (6)
| ID | Assignee | Task |
|----|----------|------|
| `t_75f2cf69` | worker-base | ISSUE 1046: slow auctions UI — dead relays + query waterfalls |
| `t_35ceebb1` | manager | PR #1019: NIP-53 improvements — stale handling, CVM commentator |
| `t_f7a094c2` | manager | PR #1118: SHA-pin all remaining GitHub Actions |
| `t_456a324` | worker-plebeian | [FEAT] Library Refactor: Applesauce Implementation |
| `t_456a341` | worker-plebeian | Fix: errors when relays go down |
| `t_456a359` | worker-plebeian | [BUG] e2e flakiness — request failing to update UI |

### Alternative Board: `plebeian-market-e2e-infra`
Exists but empty. Reserved for dedicated e2e infrastructure workstream if scope grows.

---

## OPEN PRs (c03rad0r → upstream)

| PR | Title | Status |
|----|-------|--------|
| #1150 | perf(auctions): parallelize auction query waterfall (replaces #1080) | Open |
| #1149 | feat: NIP-53 improvements — stale handling, CVM commentator, chat reactions | Open |
| #1118 | security(ci): SHA-pin all remaining GitHub Actions across deploy + release | Open |
| #1116 | fix(e2e+test): CI prettier, bun test isolation, networkidle elimination, auth/cart/WebLN | Open |
| #1115 | feat(relay): consolidated aggregator relay — Khatru + scraper + app wiring | Open |

### Franchovy's Open PRs (upstream, relevant context)
| PR | Title |
|----|-------|
| #1161 | Fixed stylesheet import |
| #1144 | Feat/settlement steps |
| #1138 | Auctions V1 |

---

## UPSTREAM ISSUES (open, recent — high priority)

| # | Title | Labels |
|---|-------|--------|
| 1135 | Security Fix PR Chain: Relay Query Aggregation Vulnerability | security |
| 1130 | [FEAT] Add NIP-60 Wallet in mobile view | enhancement, RFD, auctions |
| 1125 | [FEAT] Small Auctions UI Fixes | enhancement, RFD, auctions |
| 1124 | [BUG] Auctions - Live Events messages not sending | bug, auctions |
| 1123 | [BUG] Shipping options inconsistencies - needs ADR | bug |
| 1122 | [BUG] Gamma Markets spec inconsistency: digital product vs digital delivery | bug |
| 1114 | [SECURITY][HIGH] Anti-snipe floor uses bidder-controlled created_at | auctions, security |
| 1113 | [SECURITY][HIGH] Bid amount parsing is non-strict | auctions, security |
| 1112 | [SECURITY][CRITICAL] No relay-level bid validation | auctions, security |

---

## ACCEPTED ADRs (`docs/adr/`)

- `ADR-0001` — Hierarchical AGENTS.md and ADR docs
- `ADR-0002` — Nostr I/O migration: NDK to Applesauce
- `ADR-0013` — NIP-17 order message transport
- `ADR-0014` — NIP-17 order transport migration
- `ADR-add-product-workflow-boundaries` — Product workflow boundaries
- `ADR-payment-lifecycle-state-machine` — Payment lifecycle state machine (uncommitted)
- `ADR-store-layer-dependency-rules` — Store layer dependency rules (uncommitted)

---

## ACTIVE WORKSTREAMS & THEMES

### 1. NDK → Applesauce Migration (Wave 0)
- New relay I/O routes through `src/lib/nostr/io.ts`
- NDK footprint guard tracks `@nostr-dev-kit` usage under `src/` and `contextvm/`
- NDK remains default adapter; incremental migration strategy
- Related ADR: `ADR-0002`

### 2. Auctions Security Remediation
- 3 critical/high security issues filed (bid validation, anti-snipe, parseInt)
- PR #1118 (SHA-pin CI) in review
- Requires relay-level validation work

### 3. E2E Test Infrastructure
- PR #1116 (test infra + e2e reliability) in review
- NIP-17 order read integration helper (#1136 upstream)
- Separate board `plebeian-market-e2e-infra` reserved

### 4. Aggregator Relay
- PR #1115 (Khatru + scraper + app wiring) in review
- Market aggregator relay consolidation

### 5. NIP-53 Improvements
- PR #1149 (stale handling, CVM commentator, chat reactions) in review
- Blocked by upstream review (Franchovy)

---

## KEY FILES

- `AGENTS.md` — Repo-level agent operating guidance (read before changes)
- `docs/adr/` — Accepted architecture decisions
- `src/lib/nostr/io.ts` — Nostr I/O abstraction (Wave 0 target)
- `contextvm/` — ContextVM service (currency, NIP-53 status)
- `e2e/playwright.config.ts` — Playwright configuration
- `package.json` — Scripts and dependencies

---

## INTEGRATION POINTS

1. **Upstream (PlebeianApp/market)** — PRs target here; reviewer = Franchovy
2. **Fork (c03rad0r/market)** — Staging area for issues + ADRs; all work pushes here first
3. **ContextVM service** — Independently deployed; currency conversion + NIP-53
4. **Applesauce library** — Migration target for NDK relay I/O
5. **Playwright** — E2e test runner; CI integration via GitHub Actions

---

## NEXT ACTIONS

1. **Fast-forward** `fork/master` to `upstream/master` (2 commits behind — ops relay disk report)
2. **Address blocked board tasks** — 6 tasks waiting (auctions perf, NIP-53, CI security, Applesauce refactor, relay resilience, e2e flakiness)
3. **Monitor open PRs** — 5 PRs awaiting Franchovy review on upstream
4. **Auctions security** — Critical/high issues (#1112, #1113, #1114) need relay-level validation work
5. **Uncommitted ADRs** — Payment lifecycle + store layer rules ADRs need commit + push to fork

---

## COORDINATION PROTOCOL

- Report status + blockers to balloon-hermes Signal group
- Cross-workstream dependencies → escalate to balloon-hermes
- All work committed + pushed to fork first; PRs target upstream
- **Reviewer: Franchovy** — all PRs need his approval for upstream merge
- Worktree at `~/worktrees/ws-plebeian-market/` — never use `/tmp`
- Fork = STAGING for issues/ADRs — draft work lives here before upstream PR
- Scrub PII from all public artifacts
- Do NOT commit, push, deploy, or trigger workflows without explicit authorization
