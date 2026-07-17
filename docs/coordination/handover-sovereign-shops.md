# HANDOVER: Sovereign Shops / Arbitrage Workstream

**Created:** 2026-07-17
**Coordinator:** balloon-hermes (top-level coordination hub)
**Authority:** This workstream reports to balloon-hermes. Cross-workstream dependencies are escalated there.

---

## WHAT THIS IS

The **Sovereign Shops** workstream runs an India→EU arbitrage business across a
federation of Nostr-native marketplace shops on Plebeian Market. All shops publish
**NIP-99 (kind:30402)** classified listings, accept **Lightning payments** via CoinOS /
Wallet of Satoshi, and fulfill via DHL shipping from Berlin.

The strategic framework is **Professor Günter Faltin's "Kopf schlägt Kapital"** (Brains
Beat Capital) — the Teekampagne model: pre-order → pre-pay → direct import → 3PL fulfill.
Zero inventory, zero working capital, customers fund the purchase.

**Business model:** IndiaMART wholesale sourcing → Berlin fulfillment → EU retail margin
(60–95% depending on product). Price intelligence powered by a Kalman prediction pipeline
that tracks market bottoms and triggers buy signals.

**Shops (3 live npubs, 15 listings):**

| Shop | Npub | Listings | Focus |
|------|------|----------|-------|
| **Sovereign Optics** | `npub1ux9p69c6t8v8fmw...` | 5 (optical lenses) | Prescription lens arbitrage |
| **Sovereign Services** | `npub1qrzl2ee8dsm4p4cw...` | 6 (digital + consulting) | Guides, translation, firmware services |
| **Sovereign Imports** | `npub1cap6z24l0hs6twjrt...` | 4 (physical products) | Saffron, Boswellia, incense, tea |

> **Note:** The master plan references 4 shops (Optics, Trade, Guides, Engineering), but the
> actual implementation consolidated into 3 npubs (Optics, Services, Imports). The Sovereign
> Optics shop code lives in a separate repo (`~/nostr-glasses/`).

---

## REPOSITORIES & WORKTREE

| Item | Path / URL |
|------|------------|
| Primary repo | `~/plebeian-shop/` |
| Worktree | `~/worktrees/ws-sovereign-shops/` |
| Active branch | `ws/sovereign-shops` (worktree), `master` (primary) |
| Kanban board | `sovereign-shops` (`hermes kanban --board sovereign-shops list`) |
| Remote | `origin` → https://github.com/c03rad0r/plebeian-shop.git |
| Optics shop code | `~/nostr-glasses/` (separate repo, ngit remote) |
| Worktree (optics) | `~/worktrees/feature-multi-shop-scaffold/` (existing) |

**Git status:**
- `~/plebeian-shop/` — branch `master` at `a1167c5` (security: secret-detection hooks)
- `~/nostr-glasses/` — branch `master` at `983f8e0` (security: secret-detection hooks), remote `ngit` (nostr git)
- Worktree `ws-sovereign-shops` created from `plebeian-shop/master` at `a1167c5`

**Important:** `~/nostr-glasses/` uses **ngit** (Nostr-native git) as its primary remote, not
GitHub. It also has an `origin` pointing to the same ngit relay. Push/pull requires ngit tooling.

---

## WORKSPACE STRUCTURE

### `~/plebeian-shop/` (primary)

| Path | Purpose |
|------|---------|
| `unified-catalog.yaml` | Master catalog — all products/services with prices, margins, IndiaMART intel |
| `sovereign-shops-master-plan.md` | Strategic plan — Faltin framework, product strategy, roadmap |
| `shop-npubs.txt` | Shop npub identities, hex keys, key file locations |
| `published-events.json` | NIP-99 publish status tracker (currently all `failed` — see issues) |
| `listings/` | Listing markdown bodies (saffron, translation) |
| `products/` | Digital product content (Berlin guide, OpenWRT pack, self-hosting guide) |
| `services/` | Backend scripts — ContextVM server, price monitor, DHL tracker, translator |
| `tools/` | JS utilities (DHL shipping tracker) |
| `secrets/` | Shop env files with nsec keys (gitignored, in KeePass) |
| `.githooks/` | Pre-commit + pre-push secret detection hooks |

### `~/nostr-glasses/` (Optics shop)

| Path | Purpose |
|------|---------|
| `config/catalog.yaml` | Source of truth for 5 optical lens SKUs |
| `lib/` | Render + publish scripts (`publish.sh`, `render_listing.sh`, `unpublish.sh`) |
| `catalog/*.md` | Listing body templates per SKU |
| `secrets/.env` | Sovereign Optics nsec key |
| `AGENTS.md` | Agent operating rules (never commit keys, medical disclaimers) |
| `profile.manifest.yaml` | Hermes profile package registration |

### `~/plebeian-shop/services/` (key backend scripts)

| Script | Purpose |
|--------|---------|
| `contextvm-server.py` | ContextVM Marketplace API server — :8080 on VPS2 |
| `contextvm-translate.py` | AI translation module (DE/EN/HI via z.ai proxy) |
| `run-price-monitor.sh` | IndiaMART scraper cron wrapper (runs on VPS2) |
| `dhl-shipping-tracker.py` | DHL shipping cost calculator + tracking |
| `publish-listings.py` | NIP-99 listing publisher (nak-based) |
| `translate.py` | Core translation engine |
| `price-intelligence-latest.md` | Latest IndiaMART price report (auto-generated) |
| `shipping-report.md` | DHL cost analysis from India→Germany |

---

## INFRASTRUCTURE

### VPS2 (23.182.128.51 — Dallas, TX)

| Service | Port | Status |
|---------|------|--------|
| **ContextVM Marketplace API** | :8080 (task spec says :9090) | `contextvm-server.py` — serves `/api/catalog`, `/api/translate`, `/api/price-intel` |
| z.ai Proxy | :9099 | LLM API proxy with key rotation + fallback |
| IndiaMART Price Scraper | cron (every 6h) | `run-price-monitor.sh` → `price-intel-latest.json` |
| Relays | — | tollgate-strfry-agg, tollgate-strfry-market-agg |
| Blossom | — | tollgate-blossom (file/media hosting) |

> **⚠️ Port discrepancy:** The task specification says ContextVM is on VPS2:9090, but the
> server code (`contextvm-server.py`) configures `PORT = 8080`. The code docstring says
> "port 8080, behind Caddy reverse proxy for HTTPS." If Caddy maps :9090 → :8080, the
> discrepancy is explained. **Action: verify Caddy config on VPS2.**

### Price Intelligence Pipeline

- **Scraper:** `run-price-monitor.sh` on VPS2 cron (every 6h per master plan; script
  comment says every 12h — **verify actual cron interval**)
- **Output:** `/home/c03rad0r/automation/price-intel-latest.json` on VPS2
- **Report:** `~/plebeian-shop/services/price-intelligence-latest.md` (last: 2026-07-06)
- **Products tracked:** Kashmiri saffron, Boswellia serrata, Darjeeling tea, premium incense, pashmina
- **Exchange rate source:** exchangerate-api.com

**Latest prices (2026-07-06):**

| Product | IndiaMART Median (EUR) | EU Retail | Margin |
|---------|----------------------|-----------|--------|
| Saffron | €3.78/g | €8–15/g | 50–75% |
| Boswellia | €10.33/kg | €25–50/kg | 60–80% |
| Darjeeling tea | €3.89/kg | €35–45/kg | ~60% |
| Incense | €1.19/pack | €5–15/pack | 75–95% |

### Kalman Price Prediction

- Dashboard built and deployed (board task `t_f2e7ebad` — done)
- Tracks price trends + generates buy signals
- Planned: integrate with ContextVM `/api/price-intel/predictions`

---

## BOARD STATUS: `sovereign-shops`

**Summary:** done=20, blocked=19, archived=2 (no active todo/ready/running tasks)

### Done Tasks (20)

Key completed work includes:
- **Shop infrastructure:** 3 shop npubs created, profiles updated with CoinOS LN addresses
- **Listings published:** 15 NIP-99 listings across 3 shops (5 optical, 6 digital/services, 4 physical)
- **E2E order flow:** Buyer test order placed, NIP-17 DM verified, Lightning invoice confirmed
- **Compliance:** India-EU import compliance checklist, Bürgeramt legal analysis, EORI application research
- **Strategy:** Faltin-inspired master plan, Darjeeling tea pre-order campaign design
- **Kalman dashboard:** Price prediction pipeline + HTML dashboard
- **3PL:** German fulfillment partner sourced
- **PRs:** 6 upstream PRs merged (tollgate, torii-continuum, etc.)

### Blocked Tasks (19) — Critical Path

These are all **blocked on operator/human action or external dependencies**:

**Legal/Regulatory (5):**
| ID | Task |
|----|------|
| `t_16f0de94` | Register Gewerbe (trade license) at Berlin Bürgeramt |
| `t_86c91ca7` / `t_400bffe9` / `t_ad9534df` | Apply for EORI number at Hauptzollamt (3 duplicate tasks — consolidate) |
| `t_4575d913` | (done) Find German 3PL — completed |

**Payments (2):**
| ID | Task |
|----|------|
| `t_fb36d061` | Create 4 WoS Lightning accounts (sovereignoptics/trade/guides/eng) |
| `t_d6489215` | Wire CoinOS LN + WoS payment flows for pre-order campaigns |

**Sourcing (1):**
| ID | Task |
|----|------|
| `t_679c7604` | Source first batch of Kashmiri saffron (500g) from IndiaMART |

**Infrastructure (3):**
| ID | Task |
|----|------|
| `t_ecfa70c0` | Wire ContextVM payment gate to CDK Cashu mint on VPS2 |
| `t_3f72bb2f` | Configure HTTPS reverse proxy for VPS2 ContextVM endpoints |
| `t_efff3746` | Add 2 Namecheap DNS A records → 23.182.128.51 |

**Automation (5):**
| ID | Task |
|----|------|
| `t_a89d854c` / `t_52cccdf6` | Build DM listener for shop npubs (2 duplicates — consolidate) |
| `t_7cbeb28b` | Set up CoinOS fund monitoring (poll every 5min, alert via Signal) |
| `t_48a19a52` | Register Signal number on VPS2 for DM order alerts |
| `t_fdb8ef0c` | Schedule E2E smoke test cron on VPS2 (Playwright every 6h) |
| `t_4beff177` | Set up IndiaMART price alert notifications |

**Pre-Order Campaign (3):**
| ID | Task |
|----|------|
| `t_6a5c067b` | [TEA-PREORDER-2] Source verification — Darjeeling tea suppliers |
| `t_5dab4946` | [TEA-PREORDER-4] Create Plebeian Market pre-order listing |
| `t_a31aeb4e` | Create Printful account + API key for POD designs |

---

## KEY ISSUES

### 1. Published Events Show All `failed`
`published-events.json` shows all 6 digital/service listings with status `"failed"` and
empty error strings. However, `shop-npubs.txt` claims 15 listings are live. **Action:**
Verify which listings are actually published to relays; the JSON may be stale from the
initial publish attempt before the secret-detection hooks were added.

### 2. Duplicate Board Tasks
Several tasks are duplicated:
- EORI application: `t_86c91ca7`, `t_400bffe9`, `t_ad9534df` — consolidate to one
- DM listener: `t_a89d854c`, `t_52cccdf6` — consolidate to one
**Action:** Archive duplicates to clean up the board.

### 3. Port Discrepancy
ContextVM server code uses port 8080; task spec says 9090. Likely Caddy proxy maps
:9090→:8080 but needs verification.

### 4. Cron Interval Uncertainty
Master plan says IndiaMART scraper runs every 6h; script comment says every 12h.
**Action:** Check actual crontab on VPS2.

### 5. ngit Remote for Optics
`~/nostr-glasses/` uses ngit (Nostr git) as its primary remote. Push/pull requires
ngit tooling, not standard git over HTTPS.

---

## INTEGRATION POINTS

### → Plebeian Market Workstream (`ws-plebeian-market`)
- Shops publish to Plebeian Market's relay infrastructure
- NIP-99 listings render in the Plebeian Market client
- Order flow uses NIP-17 DMs (kind:14/kind:4)
- Payment via WebLN / Lightning
- Auction feature evaluated for Bürgeramt service (task done, feature available)
- **Escalate to balloon-hermes** if Plebeian Market relay/client changes affect shop listings

### → Infrastructure Workstream (`ws-infrastructure`)
- **ContextVM server** depends on the z.ai proxy (:9099) for translation API
- **Kalman burn predictor** shares the same z.ai quota monitoring
- **VPS2** is shared infrastructure (price scraper, ContextVM, relays, Blossom)
- **Cron orchestration** — IndiaMART scraper + planned E2E smoke tests run via VPS2 cron
- **HTTPS/TLS** — Caddy reverse proxy for ContextVM endpoints (blocked task `t_3f72bb2f`)
- **DNS** — Namecheap records for contextvm/proxy.sovereignengineering.io (blocked task `t_efff3746`)

### → External Dependencies
- **CoinOS** (coinos.io) — Lightning payment addresses
- **Wallet of Satoshi** (WoS) — Lightning payment accounts
- **IndiaMART** — Price intelligence source (anti-bot risk)
- **DHL** — Shipping calculator + tracking
- **Printful** — POD merchandise (planned)
- **German 3PL** — Fulfillment partner (sourced)

---

## STRATEGIC CONTEXT

### Faltin Framework Summary

The business follows Günter Faltin's "Kopf schlägt Kapital" model:

1. **Kalman Track Prices** → predict market bottom (timing signal)
2. **Pre-Order Campaign Live** → collect payments (customer = bank)
3. **Direct Buy at Predicted Low** → use customer money (zero working capital)
4. **3PL Fulfill** → ship to buyer (never touch inventory)

**Lead product:** Darjeeling tea (Faltin's own Teekampagne proof).
**Secondary:** Saffron, Boswellia, incense, pashmina (Kalman-tracked).

**Unit economics (Darjeeling tea, per kg):**
- IndiaMART wholesale: ₹360 (€3.31)
- Total landed cost (freight + customs + 3PL + DHL): ~€14.11
- Selling price: €35–45/kg
- **Margin: ~60–70%**

**Campaign math:** 1 LCL pallet (~500 kg) at €35/kg = €17,500 revenue, ~€10,000 gross profit.

---

## NEXT ACTIONS

### Immediate (can do without external authorization)
1. **Verify published listings** — check which NIP-99 events are actually live on relays
2. **Consolidate duplicate board tasks** — archive EORI + DM listener duplicates
3. **Verify VPS2 cron interval** — confirm IndiaMART scraper runs every 6h
4. **Verify Caddy config** — confirm :9090→:8080 proxy mapping for ContextVM
5. **Review price-intelligence-latest.md** — last report is 2026-07-06 (11 days stale)

### Requires Operator/Human Action
1. **Register Gewerbe** at Berlin Bürgeramt (task `t_16f0de94`)
2. **Apply for EORI** at Hauptzollamt (task `t_86c91ca7`)
3. **Create WoS accounts** for all shop npubs (task `t_fb36d061`)
4. **DNS records** on Namecheap (task `t_efff3746`)
5. **Source saffron batch** from IndiaMART verified supplier (task `t_679c7604`)

### Development Tasks (once blockers cleared)
1. **DM listener** — NIP-17 monitor for all shop npubs, Signal alerts on orders
2. **CoinOS fund monitoring** — poll API every 5min, payment alerts
3. **HTTPS reverse proxy** — Caddy config for ContextVM endpoints
4. **Cashu payment gate** — wire ContextVM to CDK Cashu mint
5. **Tea pre-order listing** — create Plebeian Market campaign listing

---

## COORDINATION PROTOCOL

- Report status + blockers to **balloon-hermes** Signal group
- Cross-workstream dependencies → escalate to balloon-hermes
  - Plebeian Market relay/client changes → `ws-plebeian-market`
  - ContextVM/z.ai/VPS2 infrastructure → `ws-infrastructure`
- All work committed + pushed; shop repos use GitHub + ngit (Nostr)
- Worktree at `~/worktrees/ws-sovereign-shops/` — never use `/tmp`
- **Scrub PII** — never commit nsec keys, real names, Signal numbers in public artifacts
- Do NOT publish listings, deploy services, or trigger payments without explicit authorization
- **Secrets:** Shop nsec keys in KeePass at `~/.hermes/profiles/manager/secrets/nostr-shops.kdbx`
- CoinOS credentials in KeePass 'CoinOS' group
