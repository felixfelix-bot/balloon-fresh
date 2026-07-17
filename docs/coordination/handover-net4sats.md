# HANDOVER — net4sats MVP Workstream

> **Self-contained: a fresh LLM session can bootstrap from this doc alone.**
> Last updated: 2026-07-17

---

## What This Workstream Is

net4sats turns an OpenWrt router (GL-MT6000 / Flint 2) into a Cashu-powered
payment gateway for internet access — branded, operator-friendly, and
end-to-end deployable. This workstream covers the **onboarding wizard**
(`net4sats-wizard-go`, Go binary serving web UI on `:8099`), the
**router-side admin dashboard + captive portal** (`configurationwizzard`,
Preact PWA), and the **Python onboarder prototype** (`net4sats-onboarder`).

All three repos are **thin UI wrappers** — business logic lives in
`tollgate-module-basic-go` (separate workstream, see
`handover-tollgate-router.md`).

**Coordinator:** balloon-hermes (top-level hub).
**Strategy:** Fork-first. All work goes to `c03rad0r/` forks first, PRs to
`net4sats/` org repos.

---

## Key Paths

| Item | Path / Value |
|------|-------------|
| Wizard repo (primary) | `~/net4sats-wizard-go/` |
| Worktree (this WS) | `~/worktrees/ws-net4sats/` |
| Worktree branch | `ws-net4sats/mvp` (from `main` @ `68785a1`) |
| Admin dashboard + portal | `~/configurationwizzard/` |
| Onboarder prototype (Python) | `~/repos/net4sats-onboarder/` |
| Config wizard (clone) | `~/repos/net4sats-configwiz/` |
| Kanban board | `configurationwizzard` |
| Board DB | `~/.hermes/profiles/manager/kanban/boards/configurationwizzard/kanban.db` |
| Handover doc | `~/coordination/handover-net4sats.md` (this file) |
| AGENTS.md (wizard) | Root of `net4sats-wizard-go` — architecture boundary rules |
| AGENTS.md (configwiz) | Root of `configurationwizzard` — two build targets, port map |

### Git Remotes — Wizard (`net4sats-wizard-go`)

| Remote | URL |
|--------|-----|
| origin | `https://github.com/net4sats/net4sats-wizard-go.git` |
| net4sats | `https://github.com/net4sats/net4sats-wizard-go.git` |
| c03rad0r | `https://github.com/c03rad0r/net4sats-wizard-go.git` (fork) |

### Git Remotes — configurationwizzard

| Remote | URL |
|--------|-----|
| origin | `https://github.com/net4sats/configurationwizzard.git` |
| c03rad0r | `https://github.com/c03rad0r/configurationwizzard.git` (fork) |

### Git Remotes — net4sats-onboarder

| Remote | URL |
|--------|-----|
| origin | `https://github.com/net4sats/net4sats-onboarder.git` |

> **Note:** `net4sats-onboarder` has **zero commits** — the Python prototype
> (`net4sats_onboarder.py` + `index.html`) exists locally but was never
> committed. This is a gap to address.

---

## Board Status (as of 2026-07-17)

**Board:** `configurationwizzard` — **0 tasks**

> **Discrepancy:** The context briefing cited "1 blocked" task, but the
> actual kanban DB at verification time is **completely empty** (0 tasks in
> all statuses). The board was likely created but never populated, or was
> cleared. No actionable items exist on the board. See GitHub issues below
> for the real work backlog.

---

## GitHub Status (as of 2026-07-17)

### net4sats-wizard-go — Open Issues: **0** | Open PRs: **0**

No open issues or PRs. Repo is clean on `main`.

### configurationwizzard — Open Issues: **3**

| Issue | Title |
|-------|-------|
| #19 | NDS redirect shows IP instead of net4sats.lan in captive portal URL bar |
| #18 | PWA Add to Home Screen disabled — needs full implementation |
| #3 | E2E Test Results — Physical Router Playwright + pytest Dashboard |

### configurationwizzard — Open PRs: **3**

| PR | Branch | Title |
|----|--------|-------|
| #21 | `docs/readme` | docs: rewrite README with full admin panel + portal documentation |
| #20 | `feat/postinst-tollgate-feed` | feat(postinst): register tollgate custom feed (opkg + apk) |
| #13 | `chore/cleanup-planning-docs` | chore: add AGENTS.md, remove planning docs, update .gitignore |

### configurationwizzard — Current Branch

The working tree is on **`net4sats-mvp`** branch (not `main`). This branch
includes merged PR #20 (tollgate feed postinst) and admin identity panel
features. The `main` branch on origin is behind.

---

## Architecture Overview

### Three-Repo Architecture (All Thin UI Wrappers)

```
Operator's Laptop                    Router (GL-MT6000 @ 192.168.1.1)
┌─────────────────────┐              ┌──────────────────────────────────┐
│ net4sats-wizard-go  │  ── SSH ──>  │ tollgate-module-basic-go (:2121) │
│ Go binary :8099     │  ── API ──> │  Identity, Pricing, Payments    │
│ go:embed index.html │              │                                  │
└─────────────────────┘              │ configurationwizzard             │
                                     │  Admin dashboard :8090 (admin)   │
                                     │  Captive portal  :80    (portal) │
                                     │  Nodogsplash gateway :2050       │
                                     └──────────────────────────────────┘
```

### Identity APIs (on router at 192.168.1.1)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/identity` | GET | npub, LAN IPv4, MAC address |
| `/identity/reveal-seed` | POST | BIP39 mnemonic (24 words) |

All derivation happens in `tollgate-module-basic-go/src/identity/`.
Wizard and admin UI only call the API and render results.

### Port Map

| Port | Service | Repo |
|------|---------|------|
| 8099 | Wizard web UI (operator laptop) | net4sats-wizard-go |
| 80 | Captive portal (nodogsplash) | configurationwizzard (portal build) |
| 8090 | Admin dashboard (uhttpd) | configurationwizzard (admin build) |
| 8080 | LuCI (if enabled) | tollgate-module-basic-go |
| 2121 | TollGate API | tollgate-module-basic-go |
| 2050 | Nodogsplash gateway | tollgate-module-basic-go |

---

## net4sats-wizard-go — Technical State

### What It Does

- **Router discovery:** ARP scan + TCP probe on LAN, finds GL-MT6000
- **Web UI:** Single `index.html` served via `go:embed`, operator clicks through onboarding
- **SSH deploy:** Connects to router via SSH, deploys net4sats configuration
- **API client:** Calls TollGate backend REST API for identity/status
- **Cross-platform:** Pre-built binaries for darwin-amd64, darwin-arm64,
  windows-amd64, linux-amd64 (in `dist/`)
- **NIP-34 ops:** Makefile targets for Nostr-based issue tracking via `nak`

### Key Files

| File | Purpose |
|------|---------|
| `main.go` | HTTP server, API handlers, `:8099` listener |
| `embed.go` | `//go:embed index.html` directive |
| `index.html` | Operator-facing web UI (14.9 KB) |
| `discover.go` | Router discovery (ARP scan + TCP probe) |
| `deploy.go` | SSH deployment logic |
| `ssh.go` | SSH client wrapper |
| `Makefile` | NIP-34 Nostr operations (nak key/event/req) |
| `docs/endo-runbook.md` | End-user setup guide (GL-MT6000 walkthrough) |
| `.githooks/` | Pre-commit + pre-push secret detection hooks |

### Build

```bash
cd ~/net4sats-wizard-go

# Build (Linux)
go build -o net4sats-wizard .

# Run locally (serves http://localhost:8099)
./net4sats-wizard

# Cross-compile
GOOS=darwin GOARCH=arm64 go build -o dist/net4sats-wizard-darwin-arm64 .
GOOS=linux GOARCH=amd64 go build -o dist/net4sats-wizard-linux-amd64 .

# Test
go test ./...
```

---

## configurationwizzard — Technical State

### Two Build Targets (Different Applications)

1. **Admin Dashboard** (`src/admin-main.tsx` → `/www/net4sats/` → port 8090)
   - For router operators configuring the device
   - Integrates via ubus JSON-RPC over `/ubus`
   - Routes: dashboard, WiFi, devices, settings, wallet, login
   - Identity panel: npub/IP/MAC display + seed phrase reveal + kind:0 toggle

2. **Captive Portal** (`src/portal-main.tsx` → `/www/` → port 80)
   - For WiFi users paying for internet access
   - Integrates via `:2121` TollGate API (direct HTTP)
   - Routes: Lightning tab, Cashu tab, success/loading/error

### Build

```bash
cd ~/configurationwizzard

# Admin dashboard IPK
./packaging/build-ipk-admin.sh

# Captive portal (output to dist/)
npm run build
scp dist/* root@192.168.1.1:/www/
```

---

## Critical Rules for Agents

1. **Do NOT add derivation logic to wizard or configurationwizzard.** All
   crypto, identity, payments belong in `tollgate-module-basic-go`.
2. **Do NOT ship uci-defaults scripts from these repos.** Those belong in
   the Go backend's packaging directory.
3. **Backward compatibility is paramount.** Wizard must work with older
   tollgate-module-basic-go (v0.5.0-alpha3). Graceful degradation if
   endpoints don't exist.
4. **Fork-first strategy.** Push to `c03rad0r/` fork, PR to `net4sats/` org.
5. **Unpushed work = lost work.** Commit and push regularly.
6. **Do NOT SSH hotfix the router.** Deploy via GitHub releases.

---

## Key Issues & Priorities

### P1 — configurationwizzard Issue #19: NDS URL shows IP not domain

Captive portal URL bar shows `http://192.168.1.1:2050/splash.html` instead
of `http://net4sats.lan:2050/splash.html`. NDS generates the 307 redirect
using the gateway IP, not the configured domain name. Needs DNS/DNAT fix.

### P2 — configurationwizzard Issue #18: PWA incomplete

PWA modal was removed (commit 599aaae). Needs proper service worker
caching, offline fallback, correct icons, installation testing.

### P2 — configurationwizzard Issue #3: E2E test gaps

Physical router Playwright tests: 5/8 passed on both routers (Alpha
10.47.41.1, Beta 192.168.244.1). Dashboard E2E has gaps.

### Open PRs to Review/Unblock

| PR | Status | Action |
|----|--------|--------|
| #21 (README rewrite) | Open since Jul 15 | Review and merge — documentation |
| #20 (tollgate feed postinst) | Open since Jul 1 | Already merged into net4sats-mvp locally; close or rebase |
| #13 (AGENTS.md cleanup) | Open since Jun 4 | Review and merge — housekeeping |

---

## Physical Hardware

| Item | Value |
|------|-------|
| Router | GL-MT6000 (Flint 2) |
| IP | `192.168.1.1` |
| SSH | Open (port 22) |
| Firmware | OpenWrt 25.12.0 |
| Backend port | `:2121` (TollGate API) |
| Portal port | `:2050` (nodogsplash CGI) |
| Admin UI | `:8090` (configurationwizzard admin) |

---

## Integration Points

- **balloon-hermes coordinator:** Cross-workstream dependencies escalate here.
- **tollgate-module-basic-go:** All business logic (separate workstream).
- **conwrt (`~/repos/conwrt/`):** Router flashing/configuration automation
  (safety-critical — see its AGENTS.md for sysupgrade rules).
- **net4sats-feed / net4sats-onboarder:** Supporting repos.
- **Nostr/git:** Wizard-go mirrored on GitHub only; configurationwizzard on GitHub.

---

## Coordinator Authority

This workstream reports to **balloon-hermes** (top-level coordination hub).
All work uses proper git worktrees. The coordinator handles integration
across workstreams (tollgate-router, esp32-tollgate, etc.).

---

## Next Steps for a Fresh Session

1. `cd ~/worktrees/ws-net4sats/` and read `AGENTS.md` (architecture boundaries)
2. `cd ~/configurationwizzard/` and read `AGENTS.md` (two build targets)
3. Check board: query `~/.hermes/profiles/manager/kanban/boards/configurationwizzard/kanban.db`
   (currently empty — populate from GitHub issues if needed)
4. **P1:** Address Issue #19 (NDS redirect shows IP not domain) — DNS/DNAT fix
5. **P2:** Review open PRs #21 (README), #20 (tollgate feed), #13 (cleanup)
6. **P2:** Address Issue #18 (PWA implementation) — service worker + offline
7. Verify router reachability: `ping 192.168.1.1`
8. Test wizard locally: `cd ~/worktrees/ws-net4sats/ && go build && ./net4sats-wizard`
9. Check if `net4sats-onboarder` Python prototype should be committed and merged
   into wizard-go or kept as a separate project
10. **Do NOT SSH hotfix the router.** Deploy via GitHub releases only.
