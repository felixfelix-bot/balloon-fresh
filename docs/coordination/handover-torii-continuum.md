# HANDOVER — Torii Continuum Workstream

> **Self-contained: a fresh LLM session can bootstrap from this doc alone.**
> Last updated: 2026-07-17

---

## What This Workstream Is

**Torii Continuum** ("The Gateway Project") is a bot-work app builder, project
engine, and marketplace — the front gateway into the Torii ecosystem. It is a
**fork of ChiefmonkeyArt/torii-continuum**, deployed to VPS1 and served at two
hostnames:

- **`https://continuum.orangesync.tech`** — production frontend
- **`https://agent.orangesync.tech`** — agent/backend endpoint

Stack: Vite + vanilla TS, `nostr-tools` for key handling, a Go agent service
(`agent/`), and **Ansible** playbooks for one-click deploys (`ansible/`,
`ops/ansible/`). Test surface: **429 Playwright specs** across 12 files +
vitest unit tests.

Two distinct kanban boards track this work:
1. **`continuum-agent`** — backend/mesh/Go-agent work (ESP-NOW mesh, FIPS Noise,
   Wirehair fountain codes, auth endpoints)
2. **`continuum-ui`** — browser onboarding (KeyVault w/ Web Crypto + IndexedDB,
   backup-phrase flow)

**Coordinator:** balloon-hermes Signal group (top-level hub).
This workstream reports to balloon-hermes; integration happens there.

**Deployment identity:** `npub1vasdjx8jt53dwjat9klrunnk5wfcst4gye229pghqntplf7tn6rseyz3nh`

---

## Key Paths

| Item | Path / Value |
|------|-------------|
| Primary repo | `~/repos/torii-continuum/` |
| Worktree (this WS) | `~/worktrees/ws-torii-continuum/` |
| Worktree branch | `ws/torii-continuum` (from `main` @ `dc4124d`) |
| Kanban boards | `continuum-agent` + `continuum-ui` (`~/.hermes/kanban/boards/`) |
| Handover doc | `~/coordination/handover-torii-continuum.md` (this file) |

### Git Remotes

| Remote | URL | Notes |
|--------|-----|-------|
| `upstream` | `https://github.com/ChiefmonkeyArt/torii-continuum.git` | original (not ours) |
| `github` | `https://github.com/c03rad0r/torii-continuum.git` | our GitHub fork |
| `ngit` | `nostr://npub1xh6njjx.../relay.ngit.dev/torii-continuum` | nostr git (dual-push target) |
| `origin` | same nostr:// as ngit | alias for ngit |

**Dual-push policy:** every push goes to **both `github` and `ngit`**. The
`.githooks/pre-push` hook scans full repo history against `.secret-patterns.txt`
and blocks pushes containing secrets (override: `git push --no-verify`, use with
care).

### Branches

| Branch | Head | Purpose |
|--------|------|---------|
| `main` | `dc4124d` | production line (v0.2.5-alpha) |
| `feat/browser-keygen-onboarding` | `81b4364` | active feature work — **has uncommitted changes** in the primary checkout |
| `feat/ansible-deploy` | — | Ansible one-click deploy track |
| `feat/ansible-one-click-deploy` | — | one-click deploy (mirrored on github) |

> ⚠️ The primary checkout at `~/repos/torii-continuum/` currently sits on
> `feat/browser-keygen-onboarding` with **uncommitted modifications** (ansible
> README/inventory, config template, dist rebuild, docs). Do not clobber it.
> Use the `~/worktrees/ws-torii-continuum/` worktree for new work.

---

## Board Status (as of 2026-07-17)

### `continuum-agent` — 37 tasks total

| Status | Count |
|--------|-------|
| done | 32 |
| blocked | 5 |

All tasks are **p0**.

### Blocked Tasks (continuum-agent)

| Task ID | Title | Assignee | Blocker |
|---------|-------|----------|---------|
| `t_3819bb26` | Phase 5: Integration | worker-base | worker exited cleanly (rc=0) without calling `kanban_complete`/`kanban_block` — **protocol violation** |
| `t_86c21b9b` | 5.2 5-node mesh test (linear + star) | worker-base | pid not alive (worker died mid-run) |
| `t_7207a132` | 2.1 Node ID from npub hash | worker-base | (no error recorded — needs triage) |
| `t_5fee3802` | Create `/api/auth/register-pubkey` endpoint | worker-continuum | (no error recorded — Go agent work, workspace `t_5fee3802/`) |
| `t_03cc3227` | Update auth to accept dynamic admin pubkeys | worker-continuum | (no error recorded — Go agent work, workspace `t_03cc3227/`) |

Two blocked tasks have **protocol-violation / dead-worker** root causes that are
recoverable without code changes (re-run with a live worker that calls the
kanban completion API). The other three (`t_7207a132`, `t_5fee3802`,
`t_03cc3227`) need triage — the agent workspaces live under
`~/.hermes/kanban/boards/continuum-agent/workspaces/<task_id>/`.

### `continuum-ui` — 8 tasks total (all done)

| Date | Task ID | Title |
|------|---------|-------|
| 2026-07-10 | `t_899d81f0` | Implement KeyVault class with Web Crypto + IndexedDB storage |
| 2026-07-10 | `t_0ea7856e` | Write unit tests for KeyVault class |
| 2026-07-09 | `t_a11d2a12` | Integrate onboarding into app routing |
| 2026-07-09 | `t_69dca7d4` | Create onboarding complete screen |
| 2026-07-09 | `t_c38bc685` | Write crypto utility functions for KeyVault |
| 2026-07-09 | `t_a27b31a3` | Create backup phrase display screen |
| 2026-07-09 | `t_5c270730` | Create onboarding welcome screen (password input) |
| 2026-07-07 | `t_5011cf1b` | Phase 0: ESP-NOW Basics |

---

## Current Technical State

### Active feature track — Browser Keygen Onboarding

- Branch `feat/browser-keygen-onboarding` @ `81b4364` ("one-click Ansible
  deployment + comprehensive E2E tests").
- Hybrid onboarding: browser-side key generation + bootstrap-signer flow.
  See `.hermes/plans/2026-07-07_browser-keygen-hybrid-onboarding.md` and
  `.hermes/plans/2026-07-07_bootstrap-signer-onboarding.md`.
- Implemented: KeyVault (Web Crypto + IndexedDB), backup-phrase display,
  welcome screen, complete screen, routing integration, unit tests.
- **Uncommitted in primary checkout:** ansible README/inventory edits,
  `config.yaml.j2` template, `dist/` rebuild, DEPLOYMENT docs, pre-push hook.
  Commit + dual-push these before branching further.

### Deploy / Ansible

- One-click deploy: `deploy/continuum-deploy.sh --vps1` (and `--vps2`).
- Ansible playbooks under `ansible/playbooks/`, roles under `ansible/roles/`,
  templates under `ansible/templates/`. Ops roles under `ops/ansible/`.
- VPS1 = `66.92.204.38` (default). Agent URL default
  `https://agent.orangesync.tech`. Frontend served at
  `https://continuum.orangesync.tech`.
- Docs: `docs/DEPLOYMENT.md`, `docs/DEPLOY.md`, `docs/ADMIN-AUTH-DESIGN.md`,
  `docs/ADMIN_KEY_CEREMONY_PLAN.md`, `docs/BROWSER_KEYGEN_PLAN.md`.

### Test Surface

- **429 Playwright tests** across 12 spec files (`tests/playwright/*.spec.ts`).
- Run: `npm test` (invokes `npx playwright test --config=playwright.config.ts`).
- Serial, single-worker, no retries; 30s test timeout; chromium project.
- vitest unit tests: `npm run test:vitest`.

---

## Build / Deploy Commands

```bash
# Frontend
cd ~/worktrees/ws-torii-continuum
npm install          # node_modules may need reinstall in worktree
npm run build        # vite build -> dist/

# Tests
npm test             # Playwright (429 specs)
npm run test:vitest  # unit tests

# Deploy to VPS1 production
./deploy/continuum-deploy.sh --vps1

# Dual-push (GitHub + ngit)
git push github ws/torii-continuum
git push ngit   ws/torii-continuum
```

---

## Integration Points

- **balloon-hermes coordinator:** this workstream escalates cross-workstream
  dependencies here.
- **VPS1 host:** shared with other tollgate services — coordinate deploys.
- **Deployment identity `npub1vasdjx8jt5...`:** used for Continuum nostr
  events/auth; do NOT confuse with the repo's ngit push identity
  (`npub1xh6njjxpze...`).
- **GitHub + ngit mirror:** repo is dual-published; keep both in sync.
- **Upstream sync:** periodically rebase onto `upstream/main`
  (ChiefmonkeyArt) to stay current with the original project.

---

## Coordinator Authority

This workstream reports to **balloon-hermes** (top-level coordination hub).
All work uses proper git worktrees — never `/tmp` (tmpfs = RAM-backed).
Unpushed work = lost work. Commit and push to **both** remotes regularly.
Integration happens at the coordinator level. Scrub all PII (nsec, real names,
Signal numbers) before any push.

---

## Next Steps for a Fresh Session

1. `cd ~/worktrees/ws-torii-continuum/` and read `README.md` + `docs/DEPLOYMENT.md`.
2. Decide branch base: this worktree is on `ws/torii-continuum` from `main`
   (`dc4124d`). For onboarding work, branch off `feat/browser-keygen-onboarding`
   (`81b4364`) — but first commit the uncommitted changes there (see warning
   above).
3. Verify boards (SQLite, read-only):
   ```bash
   python3 -c "import sqlite3; c=sqlite3.connect('/home/c03rad0r/.hermes/kanban/boards/continuum-agent/kanban.db'); [print(r[0],r[1],r[2]) for r in c.execute('SELECT status,id,title FROM tasks ORDER BY status')]"
   ```
4. Triage the 5 blocked `continuum-agent` tasks:
   - **Protocol violations** (`t_3819bb26`, `t_86c21b9b`) — re-run with a worker
     that calls the kanban API on exit.
   - **Auth/mesh tasks** (`t_7207a132`, `t_5fee3802`, `t_03cc3227`) — inspect
     the agent workspaces under
     `~/.hermes/kanban/boards/continuum-agent/workspaces/` and the Go code in
     `agent/`.
5. `continuum-ui` is fully done — no open work there unless new UI tasks land.
6. When ready to deploy: `./deploy/continuum-deploy.sh --vps1` after a green
   `npm test` run.
