# Workstream Index — Master Coordination Hub

**Last updated:** 2026-07-17
**Maintained by:** balloon-hermes Signal group (top-level coordinator)
**Purpose:** Single source of truth for ALL workstreams — repos, branches, worktrees, remotes,
kanban boards, current state, and integration points. Read THIS FILE FIRST to bootstrap.

> **Repository:** This file lives at `docs/WORKSTREAM-INDEX.md` in
> `https://github.com/c03rad0r/balloon-fresh` (the coordination repo).
> Raw URL:
> `https://raw.githubusercontent.com/c03rad0r/balloon-fresh/master/docs/WORKSTREAM-INDEX.md`

---

## Coordination Architecture

```
                    balloon-hermes (TOP COORDINATOR)
                    ┌─────────────────────────────────────────────────┐
                    │ High-level integration, cross-workstream deps,  │
                    │ sequencing, conflict resolution                 │
                    └───────────────────────┬─────────────────────────┘
                                            │
        ┌───────────┬───────────┬───────────┼───────────┬───────────┐
        │           │           │           │           │           │
   WS1 ESP32   WS2 micro   WS3 Balloon WS4 Router  WS5 Market  WS6 Torii
   TollGate     FIPS       /LR2021     /Backend
        │           │           │           │           │           │
        └───────────┴─────┬─────┴───────────┴───────────┴───────────┘
                          │
                    WS7 Android   WS8 net4sats   WS9 Infra   WS10 Shops
```

**Key principles:**
1. Each workstream is an **async sub-agent** with its own Signal group, kanban board, and worktree.
2. Workstreams work **independently** and report status back to balloon-hermes.
3. **Integration happens in balloon-hermes** — when work from multiple streams needs combining,
   the integration plan is defined and verified here.
4. **Cross-workstream dependencies** are escalated to balloon-hermes, not resolved bilaterally.

### Host Allocation

| Host | Role | Constraint |
|------|------|------------|
| T470 | Manager sessions + Hermes bot | NEVER external automation |
| DQ05 | Builds, Docker tests, hardware | NEVER external automation |
| VPS1 | Continuum, tollgate services | External automation OK |
| VPS2 | Backend services, scraping | ONLY host for Playwright/scraping |

---

## Universal Worktree Discipline (MANDATORY for all workstreams)

1. **ALL git work goes in `~/worktrees/ws-<name>/`** — dedicated worktrees with dedicated branches.
2. **NEVER use `/tmp`** — tmpfs is RAM-backed, cleared on reboot. Your work will be lost.
3. **Done = pushed.** Commit AND push every change. Unpushed work = lost work.
4. **Shared repos** (org repos) → branch + PR. **Own repos** → push to main/master directly.
5. **Conventional commits.** Atomic commits (one concern per commit).
6. **Verify before flashing** hardware — board ports change on every USB replug.
7. **Scrub PII** — No real names, nsec keys, Signal numbers, passwords, or personal info in
   public repos, nsytes, dashboards, or nostr events.

---

## All 10 Workstreams — Master Table

| # | Workstream | Kanban Board | Primary Repo | Worktree | WT Branch |
|---|-----------|-------------|--------------|----------|-----------|
| 1 | ESP32-S3 TollGate | `esp32-tollgate` | `~/esp32-tollgate/` | `~/worktrees/ws-esp32-tollgate/` | `ws-esp32-tollgate` |
| 2 | microFIPS Mesh | `microfips` | `~/repos/microfips/` | `~/worktrees/ws-microfips/` | `ws/microfips` |
| 3 | Balloon/LR2021 | `balloon` | `~/repos/balloon-fresh/` | `~/worktrees/ws-balloon/` | `ws/balloon-lr2021` |
| 4 | TollGate Router/Backend | `tollgate-module-basic-go` | `~/repos/physical-router-test-automation/` | `~/worktrees/ws-tollgate-router/` | `ws/tollgate-router` |
| 5 | Plebeian Market | `market` | `~/repos/market/` | `~/worktrees/ws-plebeian-market/` | `ws/plebeian-market` |
| 6 | Torii Continuum | `continuum-agent` + `continuum-ui` | `~/repos/torii-continuum/` | `~/worktrees/ws-torii-continuum/` | `ws/torii-continuum` |
| 7 | TollGate Android | `tollgate-android` | `~/repos/tollgate-android/` | `~/worktrees/ws-tollgate-android/` | `ws/tollgate-android` |
| 8 | net4sats MVP | `configurationwizzard` | `~/net4sats-wizard-go/` | `~/worktrees/ws-net4sats/` | `ws-net4sats/mvp` |
| 9 | Infrastructure | `devops-infra` + `admin` | `~/.hermes/bot/` | `~/worktrees/ws-infrastructure/` | `ws/infrastructure` |
| 10 | Sovereign Shops | `sovereign-shops` | `~/plebeian-shop/` | `~/worktrees/ws-sovereign-shops/` | `ws/sovereign-shops` |

### Standalone Reference Repo

| Repo | Path | Remote | Notes |
|------|------|--------|-------|
| wisp-esp32 | `~/wisp-esp32/` | `origin` → `https://github.com/privkeyio/wisp-esp32.git` | Full NIP-01 Nostr relay for ESP32-S3. Source for balloon Nostr relay track and tollgate wisp_relay component. |

---

## Detailed Workstream Profiles

### WS1 — ESP32-S3 TollGate

ESP32-S3 firmware for the TollGate captive portal WiFi hotspot. On-device Cashu e-cash wallet,
Nostr identity derivation, local NIP-01 relay (:4869), ContextVM MCP server, relay selection with
auto-failover, Stratum mining, and QSPI display.

| Item | Value |
|------|-------|
| Primary repo | `~/esp32-tollgate/` |
| GitHub | `https://github.com/OpenTollGate/tollgate-esp32` (org) |
| ngit | `relay.ngit.dev/esp32-tollgate` |
| Worktree branch base | `master` @ `6d3db7a` |
| Hermes profile | `esp32-tollgate-master` |
| ESP-IDF | `~/esp/esp-idf` (v5.4.1) |
| Hardware | 3× ESP32-S3 boards (A/B/C), 16MB flash, 8MB PSRAM (OCT mode) |
| Unit tests | ✅ 86/86 passing |
| Board verify | ⚠️ BLOCKED (hardware access needed) |

**Submodules:** `nucula_src/` (Cashu wallet + secp256k1), `components/esp_littlefs/`, `components/negentropy/`

**Status:** Operational — worktree ready, unit tests green, board verification blocked.

**Integration points:** wisp-esp32 relay code embedded at `components/wisp_relay/`. Mining components
shared with balloon PoW track. TollGate Android (WS7) consumes same protocol. TollGate Router (WS4)
provides the Go backend that this firmware's architecture is modeled on.

---

### WS2 — microFIPS Mesh

Rust firmware for ESP32-C3 implementing a minimal FIPS (Free Internetworking Peering System) mesh
leaf node. ESP-NOW transport, Wirehair erasure coding, Noise XK handshake, FMP link framing,
FSP session protocol. Embassy async HAL, `no_std`.

| Item | Value |
|------|-------|
| Primary repo | `~/repos/microfips/` |
| Fork (push target) | `https://github.com/c03rad0r/microfips.git` |
| ngit | `relay.ngit.dev/microfips` |
| Primary branch | `feat/fips-v0-compat` |
| Worktree commit | `55b6cd7` ("fix(esp32c3): resolve ESP-NOW binary compilation errors") |
| Fork ahead by | 1 commit (`22360c9` — review fixes, IK simultaneous-open test). Can fast-forward. |

**Active crates:** `microfips-build`, `microfips-core`, `microfips-protocol`, `microfips-esp-common`,
`microfips-esp-transport`, `microfips-esp32c3` (ESP-NOW binary target).

**Disabled crates** (feature conflicts): `microfips-esp32`, `microfips-esp32s3`, `microfips-link`,
`microfips-sim`, others.

**Status:** ESP-NOW binary compiles. Protocol M0-M11 complete (Noise IK/XK, FSP sessions).
Transports proven: UART, BLE GATT, BLE L2CAP, WiFi, host UDP. Focus: ESP-NOW mesh Phases 0-4.

**Integration points:** Torii Continuum (WS6) agent backend reuses FIPS Noise + Wirehair.
Balloon project Track 5 needs LR2021 LoRa transport adapter built on this protocol stack.
TollGate Android (WS7) uses FIPS-based networking.

---

### WS3 — Balloon / LR2021

ESP32-C3 + NiceRF LoRa2021 (Semtech LR2021 Gen 4) pico balloon tracker AND mesh internet
transport network. Solar/supercap powered. Target weight: <14g (Mesh V1) or <9g (Minimal tracker).
Two tracks: Tracker (`tracker/`) and Mesh Stack (`mesh-stack/`).

| Item | Value |
|------|-------|
| Primary repo | `~/repos/balloon-fresh/` (THIS REPO) |
| GitHub | `https://github.com/c03rad0r/balloon-fresh.git` |
| ngit | `relay.ngit.dev/esp32-balloon-integration-fresh-fork` |
| RF driver | RadioLib v7.6.0 (NOT the deprecated custom driver in `components/lr2021/`) |
| Framework | ESP-IDF v5.4.1 |
| Target hardware | ESP32-C3_Mini_V1 (4MB flash, 400KB RAM, single-core) |

**Proven radio baseline:** 1377 kbps, 0% packet loss, FLRC 2600 kbps, 255-byte payload, +12 dBm.
**Key lesson:** Arduino per-byte `SPI.transfer()` is the ONLY working SPI method on RP2040.
PIO/DMA all failed. Air time (~803µs) dominates, not SPI speed.

**Balloon sub-tracks** (detailed in `docs/coordination/INDEX.md`):

| Sub-Track | Signal Group | Focus |
|-----------|-------------|-------|
| Radio Link | balloon-hermes (direct) | LR2021 FLRC/LoRa baseline testing + range sweeps |
| Nostr Relay | balloon-nostr | Extract wisp-esp32 relay → port to ESP32-C3 |
| Tollgate/Cashu | balloon-tollgate | Extract captive portal + Cashu → port to C3 |
| PoW/Mining | balloon-pow | Extract sw_miner + stratum → eval C3 feasibility |
| FIPS Mesh | balloon-fips | Add LR2021 LoRa transport to microfips protocol |
| Blossom Server | balloon-blossom | Design + build ESP32 Blossom media server (BUD-01/02) |

**Existing sub-track worktrees:** `~/worktrees/balloon-speed-tests/`, `~/worktrees/balloon-range-tests/`,
`~/worktrees/docs-speed-record-results/`, `~/worktrees/track-speed-testing/`,
`~/worktrees/track-range-testing/`. 40+ total worktrees exist. See `git worktree list`.

**Status:** Active. Baseline proven. Next: outdoor range sweep (10m/25m/50m/100m) + speed optimization.

---

### WS4 — TollGate Router / Backend

TollGate turns an OpenWrt router into a Cashu-powered payment gateway for internet access.
Two repos: Go backend (`tollgate-module-basic-go`, API on :2121) and physical router test
automation framework (`physical-router-test-automation`, multi-tier pytest).

| Item | Value |
|------|-------|
| Tests repo (primary) | `~/repos/physical-router-test-automation/` |
| Go backend repo | `~/repos/tollgate-module-basic-go/` |
| Tests GitHub | `https://github.com/OpenTollGate/physical-router-test-automation` (org) |
| Tests ngit | `relay.ngit.dev/physical-router-test-automation` |
| Go backend upstream | `https://github.com/OpenTollGate/tollgate-module-basic-go.git` |
| Go backend fork | `https://github.com/c03rad0r/test-stablechannel-tollgate-module-basic-go.git` |
| Worktree branch base | `main` @ `f769e08` |

**Tests repo remotes:** `origin` → OpenTollGate GitHub, `ngit` → nostr git.
**Go backend remotes:** `origin` → nostr (ngit), `upstream` → OpenTollGate GitHub, `fork` → c03rad0r fork.

**Status:** Operational. pytest framework has API, phone, and browser tiers testing real OpenWrt hardware.

**Integration points:** This is the backend that net4sats (WS8) and ESP32 TollGate (WS1) are thin UI
wrappers around. TollGate Android (WS7) speaks the same TollGate v2 CBOR protocol. Deploy via GitHub
releases / Nostr NIP-94 events (1063).

---

### WS5 — Plebeian Market

Plebeian Market (`plebeian.market`) — decentralized Nostr-native marketplace on Bitcoin/Lightning.
React + TanStack + Bun with Playwright e2e tests.

| Item | Value |
|------|-------|
| Primary repo | `~/repos/market/` |
| Upstream | `https://github.com/PlebeianApp/market.git` |
| Fork (staging) | `https://github.com/c03rad0r/market.git` |
| Worktree branch base | `fork/master` @ `b6869d52` |
| Upstream ahead | 2 commits (relay disk report ops PRs). Fork needs fast-forward. |
| Package | `plebeian.market` v0.1.0 (Bun) |

**Key areas:** `src/` (React/TanStack client), `contextvm/` (currency conversion, NIP-53),
`e2e/` (Playwright tests), `docs/` (ADRs, issue notes), `.github/` (Actions + issue templates).

**Reviewer:** Upstream maintainer (also has their own fork).

**Status:** Active. Fork 2 commits behind upstream. Playwright e2e tests maintained.

**Integration points:** Sovereign Shops (WS10) publishes NIP-99 listings on this marketplace.
ContextVM service embedded in `contextvm/` directory.

---

### WS6 — Torii Continuum

Bot-work app builder, project engine, and marketplace — the front gateway into the Torii ecosystem.
Fork of upstream repo, deployed to VPS1.

| Item | Value |
|------|-------|
| Primary repo | `~/repos/torii-continuum/` |
| Upstream | `https://github.com/ChiefmonkeyArt/torii-continuum.git` |
| GitHub fork | `https://github.com/c03rad0r/torii-continuum.git` |
| ngit | `relay.ngit.dev/torii-continuum` |
| Worktree branch base | `main` @ `dc4124d` |
| Deploy URLs | `https://continuum.orangesync.tech` (frontend), `https://agent.orangesync.tech` (backend) |

**Stack:** Vite + vanilla TS, `nostr-tools`, Go agent service (`agent/`), Ansible playbooks
(`ansible/`, `ops/ansible/`). Test surface: 429 Playwright specs + vitest unit tests.

**Dual-push policy:** Every push goes to BOTH `github` and `ngit`. Pre-push hook scans for secrets
against `.secret-patterns.txt`.

**Kanban boards:** `continuum-agent` (backend/mesh/Go-agent) + `continuum-ui` (browser onboarding).

**Status:** Deployed and operational on VPS1. 429 Playwright specs maintained.

**Integration points:** Agent backend reuses microFIPS (WS2) Noise handshake + Wirehair fountain codes.
FIPS mesh integration for ESP-NOW transport. Nostr identity for deployment.

---

### WS7 — TollGate Android

Native Android TollGate client app. Rust core (`tollgate-mobile`) exposed to Kotlin/Jetpack Compose
via UniFFI. FIPS-based networking. Full native — no Tauri/Flutter/JS wrapper.

| Item | Value |
|------|-------|
| Primary repo | `~/repos/tollgate-android/` |
| GitHub (push target) | `https://github.com/OpenTollGate/tollgate-android.git` (org) |
| ngit | `relay.ngit.dev/tollgate-android` |
| Most active branch | `fix/wifi-scan-discovery` |
| Worktree branch base | `feature/fips-path-dep` |
| Worktree commit | `0b4dfef` ("merge: restore Applesauce Nostr discovery from main") |

**Architecture:** Rust core speaks TollGate v2 CBOR protocol (reusing wire types from `tollgate-rs`).
Includes Applesauce-based Nostr discovery module for finding FIPS exit nodes. Kotlin shell provides
5-screen UI (discover, pay, settings, status, wallet) with Cashu/CDK wallet, multi-mint auto-rebalance,
V1 HTTP gateway (:2121). Modelled on Myco and fips-android.

**Branch landscape:** Significant divergence. `main` has Phase 1+2 merged (5 screens, JNI bootstrap)
but Nostr discovery was reverted. `feature/fips-path-dep` has FIPS dep + Applesauce discovery but
simpler UI (3 Kotlin screens).

**Status:** Active development. Branch divergence needs resolution before merge.

**Integration points:** Uses FIPS-based networking from microFIPS (WS2). Speaks same protocol as
TollGate Router backend (WS4). Applesauce Nostr discovery module for finding exit nodes.

---

### WS8 — net4sats MVP

Turns an OpenWrt router (GL-MT6000 / Flint 2) into a Cashu-powered payment gateway for internet
access. Covers the onboarding wizard (Go, :8099), router-side admin dashboard + captive portal
(Preact PWA), and Python onboarder prototype.

| Item | Value |
|------|-------|
| Wizard repo (primary) | `~/net4sats-wizard-go/` |
| Admin dashboard + portal | `~/configurationwizzard/` |
| Onboarder prototype | `~/repos/net4sats-onboarder/` |
| Worktree branch base | `main` @ `68785a1` |

**Wizard remotes:** `origin`/`net4sats` → `https://github.com/net4sats/net4sats-wizard-go.git`,
`c03rad0r` → `https://github.com/c03rad0r/net4sats-wizard-go.git` (fork).
**configurationwizzard remotes:** `origin` → `https://github.com/net4sats/configurationwizzard.git`,
`c03rad0r` → fork.

**Strategy:** Fork-first. All work goes to `c03rad0r/` forks first, PRs to `net4sats/` org repos.

**Status:** Active. All three repos are thin UI wrappers — business logic lives in
`tollgate-module-basic-go` (WS4).

**Integration points:** Depends on TollGate Router backend (WS4) for all business logic.
Wizard and dashboard are UI layers over the Go backend API.

---

### WS9 — Infrastructure

Infrastructure backbone keeping all Hermes workstreams operational: z.ai API proxy (key rotation +
fallback), burn-rate prediction (Kalman filter), rate limiting, resource monitoring, Ansible
deployment roles, cron orchestration, and kanban board infrastructure.

| Item | Value |
|------|-------|
| Primary repo | `~/.hermes/bot/` |
| GitHub | `https://github.com/c03rad0r/hermes-bot.git` |
| Primary branch | `master` |
| Worktree commit | `8f3acda` ("fix: log key decisions for fallback providers") |
| Helper scripts | `~/scripts/` (resource-monitor.py, dashboards, etc.) |

**Core services:**
- **z.ai Proxy** (`zai_proxy.py`, :9099) — auto-rotates two API keys based on quota windows.
  Falls back to Ollama Cloud when both near limit.
- **Burn Predictor** (`burn_predictor.py`) — 2-state Kalman filter tracking token volume + velocity.
- **Kanban infrastructure** — all workstream boards run on this system.

**Status:** Operational. Proxy healthy, key rotation working, burn prediction active.

**Integration points:** ALL other workstreams depend on this for LLM API access, cost control,
and task dispatch. Critical foundational dependency.

---

### WS10 — Sovereign Shops

India→EU arbitrage business across a federation of Nostr-native marketplace shops on Plebeian Market.
All shops publish NIP-99 (kind:30402) classified listings, accept Lightning payments, fulfill via
DHL shipping from Berlin.

| Item | Value |
|------|-------|
| Primary repo | `~/plebeian-shop/` |
| GitHub | `https://github.com/c03rad0r/plebeian-shop.git` |
| Optics shop code | `~/nostr-glasses/` (separate repo, ngit remote) |
| Worktree commit | `a1167c5` (security: secret-detection hooks) |

**Shops (3 live npubs, 15 listings):**
- Sovereign Optics (5 listings) — prescription lens arbitrage
- Sovereign Services (6 listings) — guides, translation, firmware services
- Sovereign Imports (4 listings) — saffron, Boswellia, incense, tea

**Strategy:** Professor Günter Faltin's "Kopf schlägt Kapital" — pre-order → pre-pay → direct
import → 3PL fulfill. Zero inventory, zero working capital. Price intelligence via Kalman
prediction pipeline tracking market bottoms.

**Status:** 3 shops live with 15 listings. Secret-detection hooks installed on both repos.

**Integration points:** Publishes on Plebeian Market (WS5). Uses Kalman pipeline related to
Infrastructure (WS9) burn predictor pattern.

---

## Cross-Workstream Dependency Map

```
WS9 Infrastructure ◄── ALL workstreams depend on this (API access, cost control, kanban)
     │
     ├── WS1 ESP32 TollGate ──► WS4 Router Backend (protocol model)
     │         │                 WS7 Android (same protocol)
     │         │                 wisp-esp32 (relay component)
     │         └──► Balloon sub-tracks (tollgate/cashu port)
     │
     ├── WS2 microFIPS ──► Balloon sub-track 5 (LR2021 transport adapter)
     │         │            WS6 Torii (Noise + Wirehair reuse)
     │         │            WS7 Android (FIPS networking)
     │
     ├── WS3 Balloon ──► Balloon sub-tracks 1-6 (all depend on radio baseline)
     │         │         wisp-esp32 (Nostr relay source)
     │         │         WS1 ESP32 TollGate (tollgate component extraction)
     │
     ├── WS4 Router/Backend ──► WS8 net4sats (business logic provider)
     │                        WS7 Android (protocol consumer)
     │
     ├── WS5 Plebeian Market ──► WS10 Sovereign Shops (listing platform)
     │                          ContextVM (embedded service)
     │
     └── WS6 Torii Continuum ──► WS2 microFIPS (mesh integration)
```

---

## Handover Document Locations

Each workstream has a self-contained handover document at `~/coordination/handover-<name>.md`.
A fresh LLM session can bootstrap from these without conversation history.

| Workstream | Handover Doc |
|-----------|-------------|
| WS1 ESP32 TollGate | `~/coordination/handover-esp32-tollgate.md` |
| WS2 microFIPS | `~/coordination/handover-microfips.md` |
| WS3 Balloon/LR2021 | `~/coordination/handover-balloon.md` |
| WS4 TollGate Router | `~/coordination/handover-tollgate-router.md` |
| WS5 Plebeian Market | `~/coordination/handover-plebeian-market.md` |
| WS6 Torii Continuum | `~/coordination/handover-torii-continuum.md` |
| WS7 TollGate Android | `~/coordination/handover-tollgate-android.md` |
| WS8 net4sats | `~/coordination/handover-net4sats.md` |
| WS9 Infrastructure | `~/coordination/handover-infrastructure.md` |
| WS10 Sovereign Shops | `~/coordination/handover-sovereign-shops.md` |

**Balloon sub-track handovers** (in this repo at `docs/coordination/`):
- `handover-balloon-nostr.md` — Nostr relay extraction
- `handover-balloon-tollgate.md` — Tollgate/Cashu extraction
- `handover-balloon-pow.md` — PoW/Mining extraction
- `handover-balloon-fips.md` — FIPS mesh LR2021 transport
- `handover-balloon-blossom.md` — Blossom server design

---

## Coordination Protocol

1. **Workstream needs help:** Post status + blocker in their dedicated Signal group.
2. **Cross-workstream dependency:** Escalate to balloon-hermes.
3. **balloon-hermes** creates/links kanban tasks to track resolution.
4. **Resolution verified** before marking complete.

When escalating, include:
- Workstream name + Signal group
- What's blocked and why
- What you need from which other workstream
- Your current kanban task ID (if applicable)

---

## How to Bootstrap a New Session

1. Read **this file** (`docs/WORKSTREAM-INDEX.md`).
2. Read the **universal handover prompt** (`docs/UNIVERSAL-HANDOVER-PROMPT.md`) — or just paste it
   into your Signal group.
3. Read your workstream's **handover doc** at `~/coordination/handover-<name>.md`.
4. `cd` to your **worktree** under `~/worktrees/ws-<name>/`.
5. Check `git status` and `git log --oneline -5` in the worktree.
6. Check your **kanban board**: `hermes kanban --board <slug> list`.
7. Start working. Report initial findings to balloon-hermes.
