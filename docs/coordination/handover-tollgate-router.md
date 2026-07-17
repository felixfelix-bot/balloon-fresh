# HANDOVER — TollGate Router/Backend Workstream

> **Self-contained: a fresh LLM session can bootstrap from this doc alone.**
> Last updated: 2026-07-17

---

## What This Workstream Is

TollGate turns an OpenWrt router into a Cashu-powered payment gateway for
internet access. This workstream covers the **Go backend** (`tollgate-module-basic-go`,
serving API on `:2121`) and the **physical router test automation** framework
(`physical-router-test-automation`). Both run against real OpenWrt hardware.

**Two repos:**

1. **`tollgate-module-basic-go`** — Go v1 backend. Cashu ecash processing,
   captive portal CGI, nodogsplash integration, Lightning invoice quotes,
   identity derivation, LuCI admin UI.
2. **`physical-router-test-automation`** — Multi-tier pytest framework (API,
   phone, browser) that tests the Go backend deployed on real routers.

**Coordinator:** balloon-hermes (top-level hub).
**Reviewer:** Amperstrand for OpenTollGate PRs.
**Deploy:** GitHub releases / Nostr NIP-94 events (1063).

---

## Key Paths

| Item | Path / Value |
|------|-------------|
| Tests repo (primary) | `~/repos/physical-router-test-automation/` |
| Go backend repo | `~/repos/tollgate-module-basic-go/` |
| Worktree (this WS) | `~/worktrees/ws-tollgate-router/` |
| Worktree branch | `ws/tollgate-router` (from `main` @ `f769e08`) |
| Kanban board | `tollgate-module-basic-go` |
| Board DB | `~/.hermes/profiles/manager/kanban/boards/tollgate-module-basic-go/kanban.db` |
| Handover doc | `~/coordination/handover-tollgate-router.md` (this file) |
| AGENTS.md (tests) | Root of physical-router-test-automation — full operational guide |
| AGENTS.md (Go) | Root of tollgate-module-basic-go — contribution process, PR rubric |

### Git Remotes — Tests Repo (`physical-router-test-automation`)

| Remote | URL |
|--------|-----|
| origin | `https://github.com/OpenTollGate/physical-router-test-automation.git` |
| ngit | `nostr://...relay.ngit.dev/physical-router-test-automation` |

### Git Remotes — Go Backend (`tollgate-module-basic-go`)

| Remote | URL |
|--------|-----|
| origin | nostr (ngit) |
| upstream | `https://github.com/OpenTollGate/tollgate-module-basic-go.git` |
| fork | `https://github.com/c03rad0r/test-stablechannel-tollgate-module-basic-go.git` |

---

## Board Status (as of 2026-07-17)

**Board:** `tollgate-module-basic-go` — **16 tasks total**

| Status | Count |
|--------|-------|
| archived | 11 |
| todo | 5 |

> **Note:** The context briefing cited "29 blocked, 17 done, 2 todo" but the
> actual kanban DB at the time of verification shows 16 tasks (11 archived,
> 5 todo, 0 blocked/done/in_progress). The discrepancy likely reflects a
> board cleanup or an earlier snapshot. The 5 todo tasks below are the
> actionable items.

### Todo Tasks (5 — actionable now)

| Task ID | Priority | Title |
|---------|----------|-------|
| `github-tollgate-module-basic-go-253` | p1 | PR #253: fix: bump gonuts-tollgate to v0.7.3 for DLEQ keyset fix |
| `github-tollgate-module-basic-go-252` | p1 | PR #252: fix: use fuzzy mint URL matching in calculateAllotment |
| `github-tollgate-module-basic-go-249` | p1 | PR #249: fix: exponential backoff and jitter for lightning quote monitor |
| `github-tollgate-module-basic-go-248` | p1 | PR #248: fix: persist Lightning quotes to disk so they survive restart |
| `github-tollgate-module-basic-go-229` | p2 | Issue #229: DESIGN: Formalize SSID format — remove band suffix |

### Archived (11 — completed/closed)

PRs #168, #180, #181, #182, #185, #186, #187, #188, #189, #190, #227 —
covering profit-share, whoami degradation, LN capability probe, multiple
testnut mints, identity derivation, IPv4/MAC derivation, roadmap docs,
CLI man pages, operator guide, security anti-pattern docs.

---

## GitHub Status (as of 2026-07-17)

### Open PRs (7)

| PR | Branch | Title |
|----|--------|-------|
| #253 | `fix/bump-gonuts-v0.7.3` | fix: bump gonuts-tollgate to v0.7.3 for DLEQ keyset fix |
| #252 | `fix/mint-url-fuzzy-match-250` | fix: use fuzzy mint URL matching in calculateAllotment |
| #249 | `fix/lightning-monitor-rate-limiting` | fix: exponential backoff and jitter for lightning quote monitor |
| #248 | `fix/ln-quote-persistence-247` | fix: persist Lightning quotes to disk so they survive restart |
| #246 | `chore/upgrade-x-crypto-x-net` | chore: upgrade golang.org/x/crypto + x/net |
| #241 | `feat/unified-identity` | feat(identity): unified NIP-06 + password derivation |
| #235 | `feat/wgm-vendor-ie-discovery` | feat(wgm): re-implement vendor IE discovery from wire format |

### Open Issues (13 — key ones)

| Issue | Labels | Title |
|-------|--------|-------|
| #251 | bug | calculateAllotment uses == for mint URL matching instead of mintURLMatches() |
| #250 | — | Mint URL exact string match rejects valid tokens on trailing slash/case |
| #247 | bug | Lightning invoice quotes lost on restart — payment success not detected |
| #239 | enhancement | Reseller Bootstrap: Zero-Float Mesh Formation |
| #226 | enhancement | Architecture: move port 2121 to loopback-only |
| #225 | enhancement | Use HKDF instead of raw SHA-256 for identity derivation |
| #212 | bug | #88: updated status — temporary workaround is live |
| #177 | documentation | Security audit findings — v0.5.0 pre-release |
| #88 | bug, area: payments | Router-to-router autopay depends on nodogsplash client registration |
| #85 | documentation, area: nostr | Nostr router discovery and fleet announcement |

### Recently Merged PRs (30+)

Key recent merges: #245 (TOCTOU-safe SSRF), #244 (Go 1.25 bump),
#240 (protocol compliance codes), #234 (RFC 1918 isolation),
#232 (12-word NIP-06 mnemonic), #223 (security dep bumps).

---

## Current Technical State

### Active Bug Cluster: DLEQ + Mint URL Matching (P0)

Two related issues blocking Cashu payments from modern wallets:

- **Issue #250/#251:** `calculateAllotment()` uses `==` for mint URL matching
  instead of `mintURLMatches()`. Tokens with trailing slashes or case
  differences are rejected. Fix in PR #252.
- **DLEQ proof failure:** When a Cashu mint rotates keysets, tokens minted
  under a now-inactive keyset fail DLEQ verification. Fix requires bumping
  `gonuts-tollgate` to v0.7.3 (PR #253). Detailed analysis in
  `~/repos/tollgate-module-basic-go/handover-dleq-fix.md`.

### Active Bug Cluster: Lightning Quotes (P1)

- **Issue #247:** Lightning invoice quotes lost on restart — captive portal
  cannot detect payment success after a reboot. Two PRs in flight:
  - PR #248: Persist quotes to disk
  - PR #249: Add exponential backoff/jitter for quote monitoring

### User Preference

> **PREF: Fix the wizard/backend code, NOT the router.**
> Deploy fixes via GitHub releases → Nostr NIP-94 events → router auto-update.
> Do not SSH into the router to apply hotfixes unless explicitly directed.

### Physical Hardware

| Item | Value |
|------|-------|
| Router | GL-MT6000 (Flint 2) |
| IP | `192.168.1.1` |
| SSH | Open (port 22) |
| Firmware | OpenWrt 25.12.0 |
| Backend port | `:2121` (TollGate API) |
| Portal port | `:2050` (nodogsplash CGI) |
| Admin UI | `:8080` (LuCI, Go v1 only) |

---

## Build Commands

### Go Backend (`tollgate-module-basic-go`)

```bash
cd ~/repos/tollgate-module-basic-go/src

# Lint and test (run before opening PRs)
gofmt -l .          # must print nothing
go vet ./...
go build ./...
go test -race -count=1 -tags testenv ./...

# Contract tests (if config schema changed)
cd ~/repos/tollgate-module-basic-go
node tests/contract/js-schema-lint.mjs
bash tests/contract/build-purity.sh
```

### Test Framework (`physical-router-test-automation`)

```bash
cd ~/repos/physical-router-test-automation

# API tests (SSH to router, no phone needed)
pytest tests/api/ --backend=go

# Browser tests (Playwright, LuCI admin UI)
npx playwright test tests/browser/

# Physical provider (real hardware, never publishes)
TOLLGATE_VM_PROVIDER=physical pytest tests/api/
```

### Fetching Builds via Nostr (No GitHub Access Needed)

```bash
# Latest stable build for GL-MT6000 (aarch64_cortex-a53)
nak req -k 1063 \
  -a 5075e61f0b048148b60105c1dd72bbeae1957336ae5824087e52efa374f8416a \
  --tag n=tollgate-wrt --tag c=stable --tag A=aarch64_cortex-a53 \
  --limit 10 wss://relay.damus.io wss://nos.lol
```

Publisher npub: `npub12p67v8ctqjq53dspqhqa6u4matse2uek4evzgzr72th6xa8cg94qxks7ks`

---

## PR Review Requirements

Before opening any PR to `OpenTollGate/tollgate-module-basic-go`:

1. **One logical change per PR** — no drive-by fixes, no scope creep.
2. Run the full lint/build/test suite from `src/`.
3. **No coding-assistant attribution** in commits or PR bodies.
4. Add a `CHANGELOG.md` entry under `[Unreleased]`.
5. Review against the 13-criteria checklist in `PR-REVIEW.md`.
6. PRs are squash-merged; maintainer rewrites the final commit message.
7. **Reviewer:** Amperstrand reviews OpenTollGate PRs.

---

## Key Documentation

| Doc | Location | Purpose |
|-----|----------|---------|
| AGENTS.md (tests) | `physical-router-test-automation/` | Test framework ops, test tiers, provider abstraction |
| AGENTS.md (Go) | `tollgate-module-basic-go/` | Contribution process, PR rubric, changelog rules |
| PR-REVIEW.md | `tollgate-module-basic-go/` | 13-criteria PR review checklist |
| DLEQ-FIX-PLAN.md | `tollgate-module-basic-go/` | Detailed DLEQ proof verification fix plan |
| handover-dleq-fix.md | `tollgate-module-basic-go/` | DLEQ root cause analysis and code path |
| CHANGELOG.md | `tollgate-module-basic-go/` | All user-visible changes |
| CONTRIBUTING.md | `tollgate-module-basic-go/` | Detailed contribution guide |

---

## Integration Points

- **balloon-hermes coordinator:** Cross-workstream dependencies escalate here.
- **Amperstrand:** Reviews OpenTollGate PRs.
- **gonuts-tollgate:** Upstream Cashu library (OpenTollGate fork on v0.7.x).
  DLEQ keyset fix pending v0.7.3 release.
- **Nostr/git:** Both repos mirrored on ngit (nostr) + GitHub.
- **tollgate-rs:** Rust v1 alternative backend (Amperstrand repo). Same package
  name (`tollgate-wrt`), same API endpoints. Not the focus of this workstream.

---

## Coordinator Authority

This workstream reports to **balloon-hermes** (top-level coordination hub).
All work uses proper git worktrees. Unpushed work = lost work.
Commit and push to remote regularly. Integration happens at the coordinator level.

**Critical user preference:** Fix wizard/backend code, NOT the router.
Deploy via GitHub releases. Do not SSH hotfix the router.

---

## Next Steps for a Fresh Session

1. `cd ~/worktrees/ws-tollgate-router/` and read `AGENTS.md` (test framework ops)
2. `cd ~/repos/tollgate-module-basic-go/` and read `AGENTS.md` + `PR-REVIEW.md`
3. Check board: query `~/.hermes/profiles/manager/kanban/boards/tollgate-module-basic-go/kanban.db`
4. **P0:** Review PR #252 (mint URL fuzzy match) and PR #253 (DLEQ gonuts bump)
   — these unblock Cashu payments from modern wallets.
5. **P1:** Review PR #248 (LN quote persistence) and #249 (backoff) — issue #247.
6. Read `handover-dleq-fix.md` in the Go repo for full DLEQ root cause analysis.
7. Check `gh pr list --state open` in the Go repo for the latest PR status.
8. Verify router reachability: `ping 192.168.1.1` and `ssh root@192.168.1.1`.
9. **Do NOT SSH hotfix the router.** Deploy via GitHub releases only.
