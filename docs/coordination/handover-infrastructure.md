# HANDOVER: Infrastructure Workstream

**Created:** 2026-07-17
**Coordinator:** balloon-hermes (top-level coordination hub)
**Authority:** This workstream reports to balloon-hermes. Cross-workstream dependencies are escalated there.

---

## WHAT THIS IS

The infrastructure backbone that keeps all Hermes workstreams operational. This
includes the z.ai API proxy (key rotation + fallback), burn-rate prediction
(Kalman filter), rate limiting, resource monitoring, Ansible deployment roles,
cron orchestration, and the kanban board infrastructure itself.

All other workstreams depend on this infrastructure for LLM API access, cost
control, and task dispatch.

---

## REPOSITORIES & WORKTREE

| Item | Path |
|------|------|
| Primary repo | `~/.hermes/bot/` |
| Worktree | `~/worktrees/ws-infrastructure/` |
| Active branch | `ws/infrastructure` (worktree), `master` (primary) |
| Kanban boards | `devops-infra` + `admin` (`hermes kanban --board <slug>`) |
| Helper scripts | `~/scripts/` (resource-monitor.py, dashboards, etc.) |

**Remote:** `origin` → https://github.com/c03rad0r/hermes-bot.git

**Worktree status:** Clean, branch `ws/infrastructure` at commit `8f3acda`
("fix: log key decisions for fallback providers (ollama/ppq/openrouter)").
Primary repo is on `master` at the same commit.

> **Note:** `~/repos/hermes-orchestration/` is not a git repo (only `llms.txt`
> + `plans/`). `~/scripts/` is also not a git repo. The actual infrastructure
> code lives in `~/.hermes/bot/` per MASTER.md row 9.

---

## CORE SERVICES

### z.ai Proxy (`zai_proxy.py` — :9099)

Local reverse proxy for z.ai API. Auto-rotates between two API keys ("ours" and
"friend") based on quota windows. Falls back to Ollama Cloud when both keys are
near limit.

**Current state (live):**
- Health: **ok** (`GET /health` → "ok")
- Active key: **ours** (2% on 5h window, 1% weekly, 0% monthly)
- Friend key: 21% monthly, 17% on 5h window
- State file: `zai_proxy_state.json` (updated every request)
- Usage DB: `zai_usage.db` (~86 MB, SQLite WAL)

### Burn Predictor (`burn_predictor.py`)

2-state Kalman filter tracking token volume (tokens/hour) and velocity (rate of
change). Replaces old EWMA predictor. Feeds into rate_limit_gate and off-peak
dispatch decisions.

### Rate Limit Gate (`rate_limit_gate.py` — every 5 min cron)

Enforces per-window lock thresholds. Blocks requests when quota usage exceeds
configured thresholds. Logs to `rate_limit_gate.log`.

### API Burn Collector (`api_burn_collector.py` — every 5 min cron)

Collects spend data from PPQ and z.ai APIs. Stores in `api_burn.db`.
Analyzer (`api_burn_analyzer.py` — every 15 min cron) produces trend reports.

### Resource Monitor (`resource-monitor.py` — DQ05 :9100)

Runs on DQ05, exposes system stats (CPU, memory, disk) via HTTP :9100.
Currently **unreachable** from T470 (DQ05 ContextVM offline — LAN + Netbird
both down).

### Kalman Subsystem

- `kalman_health.py` — health check / convergence report
- `kalman_query.py` — query predictions
- `kalman_retune.py` — retune filter parameters
- `kalman_tuning.json` — current tuning state

---

## ACTIVE CRON JOBS

| Frequency | Script | Purpose |
|-----------|--------|---------|
| */5 min | `scripts/run_burn_collector.sh` | Collect API spend data |
| */5 min | `rate_limit_gate.py` | Enforce quota thresholds |
| */15 min | `api_burn_analyzer.py` | Analyze burn trends |

---

## ANSIBLE DEPLOYMENT

Location: `~/.hermes/bot/ansible/`
- `playbook-hermes-patches.yml` — Main deployment playbook
- `roles/` — Reusable roles (75-remote-proxy, 76-remote-bootstrap, etc.)

Deployed phases (all done — see admin board):
- P1: State sync, cron fixes, zai_proxy window patches
- P2: State sync audit, per-window lock thresholds, Ansible roles
- P3: Proactive key switching, multi-host playbook, remote deployment
- P4: Remote worker dispatch (E2E verified), bare-metal restore (blocked)

---

## BOARD STATUS

### `devops-infra` Board

**Summary:** done=4, blocked=5, archived=0

**Done (4):**
| ID | Task | Assignee |
|----|------|----------|
| t_1f2c5be8 | Investigate VPS2 Daily Maintenance cron (never ran) | worker-plebeian |
| t_3a40dd5a | Fix: run cron tick for worker-plebeian (VPS cleanup orphaned) | worker-plebeian |
| t_a7f4ac2e | Build kanban-dashboard nsite (board overview with task counts) | worker-base |
| t_ebcf080c | Build unified service dashboard (kanban, ContextVM, API keys, cron) | worker-plebeian |

**Blocked (5):**
| ID | Task | Assignee | Blocker |
|----|------|----------|---------|
| t_758fcb1c | Clean up paused cron jobs (lr2021-upkeep, worker-idle-edge, etc.) | worker-admin | Paused jobs need manual review |
| t_b0e13271 | Set up DQ05 Firecracker warm pool for task offloading | worker-base | DQ05 currently unreachable |
| t_f13800e9 | Fix nostr-kanban-sync cron (hanging on relay connection) | worker-tollgate | Relay timeout issue |
| t_b9500312 | Build TP-Link smart home MCP tool | worker-base | Hardware dependency |
| t_2d7d2726 | Build Reolink E330 camera MCP tool | worker-admin | Hardware dependency |

### `admin` Board

**Summary:** done=41, blocked=7, archived=47

**Blocked (7):**
| ID | Task | Assignee | Priority |
|----|------|----------|----------|
| t_dd46f9b9 | Make DQ05 a real worker node (Phases 1-4) | worker-admin | High |
| t_5c56550a | KALMAN-VIZ: nsite dashboard for Kalman data | worker-admin | Medium |
| t_3537481c | KALMAN: Task duration prediction system | worker-plebeian | Medium |
| t_wot_sync_902914 | WOT-SYNC: Kind-3 follow list → Blossom auto-sync | worker-admin | Low |
| t_d7bfe502 | Fix HIGH-risk: GitHub webhook PR titles unsanitized | worker-admin | **HIGH (security)** |
| t_b616c06a | Fix HIGH-risk: browser/scraping output unsanitized | worker-admin | **HIGH (security)** |
| t_d7d74315 | [P4-A5] Bare-metal restore script + test | worker-plebeian | Medium |

---

## HOST ALLOCATION

| Host | Role | Constraint | Status |
|------|------|-----------|--------|
| T470 | Manager + Hermes bot + z.ai proxy | NEVER external automation | ✅ Online (this host) |
| DQ05 | Builds, Docker tests, resource-monitor :9100 | NEVER external automation | ⚠️ Unreachable (LAN + Netbird down) |
| VPS1 | Continuum, tollgate services | External automation OK | (TBD) |
| VPS2 | Backend services, scraping, Playwright | ONLY host for Playwright | (TBD) |

---

## KEY FILES

### Proxy & Quota Management
- `zai_proxy.py` — z.ai reverse proxy with key rotation (:9099)
- `burn_predictor.py` — Kalman filter burn-rate predictor
- `rate_limit_gate.py` — quota enforcement gate
- `api_burn_collector.py` — spend data collector (PPQ + z.ai)
- `api_burn_analyzer.py` — burn trend analysis
- `off_peak_dispatch.py` — off-peak task dispatch logic
- `dispatch_quota_gate.py` — pre-dispatch quota check

### Kalman Subsystem
- `kalman_health.py` — convergence health check
- `kalman_query.py` — prediction queries
- `kalman_retune.py` — parameter retuning
- `kalman_price_retune.py` — price model retuning
- `multi_resource_kalman.py` — multi-resource tracking

### Model & Key Management
- `model_selector.py` — model routing logic
- `model_matrix.py` / `model_matrix.json` — model capability matrix
- `intelligent_key_selector.py` — API key selection
- `key_rotate.py` — key rotation utility

### Deployment
- `ansible/playbook-hermes-patches.yml` — main deployment playbook
- `ansible/roles/` — 75-remote-proxy, 76-remote-bootstrap, etc.
- `~/scripts/resource-monitor.py` — DQ05 resource monitor service

### State & Data
- `zai_usage.db` — proxy usage log (~86 MB SQLite)
- `api_burn.db` — spend tracking DB
- `key_selector.db` — key selection state
- `worker_metrics.db` — worker performance metrics
- `session_registry.json` — active session registry

---

## SECURITY CONCERNS

Two HIGH-risk prompt injection vulnerabilities are **blocked and unaddressed**:
1. `t_d7bfe502` — GitHub webhook PR titles unsanitized
2. `t_b616c06a` — Browser/scraping output unsanitized

These should be prioritized for the next work session.

---

## INTEGRATION POINTS

1. **All workstreams** — Depend on z.ai proxy (:9099) for LLM API access
2. **All worker profiles** — Depend on rate_limit_gate and dispatch_quota_gate
   for quota-aware task dispatch
3. **DQ05-hosted workstreams** — Depend on DQ05 for builds (currently down)
4. **balloon-fresh** — Shares kalman/telemetry patterns and ContextVM approach
5. **VPS1/VPS2 services** — Managed via Ansible roles from this repo

---

## NEXT ACTIONS

1. **t_d7bfe502 + t_b616c06a** (HIGH security): Fix prompt injection vulnerabilities
   in GitHub webhook and browser/scraping pipelines
2. **t_758fcb1c**: Clean up paused cron jobs — review and resume or remove
3. **t_f13800e9**: Fix nostr-kanban-sync cron hanging on relay connection
4. **DQ05 recovery**: Diagnose why DQ05 is unreachable (check Netbird, LAN,
   power state) — blocks t_b0e13271 and all DQ05-dependent workstreams
5. **t_dd46f9b9**: Make DQ05 a real worker node once connectivity restored
6. **t_5c56550a**: Build Kalman visualization nsite dashboard
7. Push worktree branch `ws/infrastructure` to origin when changes are committed

---

## COORDINATION PROTOCOL

- Report status + blockers to balloon-hermes Signal group
- Cross-workstream dependencies → escalate to balloon-hermes
- All work committed + pushed to origin (github.com/c03rad0r/hermes-bot.git)
- Worktree at `~/worktrees/ws-infrastructure/` — never use `/tmp`
- Scrub PII from all public artifacts (no nsec keys, Signal numbers, real names)
