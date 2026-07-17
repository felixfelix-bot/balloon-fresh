# HANDOVER: TollGate Android Workstream

**Created:** 2026-07-17
**Coordinator:** balloon-hermes (top-level coordination hub)
**Authority:** This workstream reports to balloon-hermes. Cross-workstream dependencies are escalated there.

---

## WHAT THIS IS

Native Android TollGate client app. Rust core (`tollgate-mobile`) exposed to
Kotlin/Jetpack Compose via UniFFI. FIPS-based networking (no traditional IP
firewall / VPN service approach). No Tauri, no Flutter, no JavaScript web
wrapper — full native only.

The Rust core speaks the TollGate v2 CBOR protocol (reusing wire types from
`tollgate-rs`) and also includes an Applesauce-based Nostr discovery module for
finding FIPS exit nodes. The Kotlin shell provides a 5-screen UI (discover, pay,
settings, status, wallet) with Cashu/CDK wallet integration, multi-mint
auto-rebalance, and V1 HTTP gateway support (:2121).

Architecture modelled on Myco (Origami74/myco) and fips-android (Michael Malmi).

---

## REPOSITORIES & WORKTREE

| Item | Path |
|------|------|
| Primary repo | `~/repos/tollgate-android/` |
| Worktree | `~/worktrees/ws-tollgate-android/` |
| Primary repo branch | `fix/wifi-scan-discovery` (most active development) |
| Worktree branch | `ws/tollgate-android` (created from `feature/fips-path-dep`) |
| Kanban board | `tollgate-android` (`hermes kanban --board tollgate-android`) |
| Master plan | `~/plans/tollgate-android-master-plan.md` |

**Remotes:**
- `github` → https://github.com/OpenTollGate/tollgate-android.git (GitHub, primary push target)
- `ngit` → nostr://npub1xh6...sk3xqw3/relay.ngit.dev/tollgate-android
- `origin` → nostr://npub1xh6...sk3xqw3/relay.ngit.dev/tollgate-android (same as ngit)

> **Note:** ngit remotes are configured but context indicated "no ngit remote yet"
> — likely means no successful ngit push has been performed. Verify before relying on it.

**Worktree status:** Clean, branch `ws/tollgate-android` at commit `0b4dfef`
("merge: restore Applesauce Nostr discovery from main"). Based on
`feature/fips-path-dep` (4 commits) which adds FIPS path dep + Nostr discovery
atop the initial scaffold.

---

## BRANCH LANDSCAPE

The repo has diverged significantly across branches. Understanding the split is
critical before any work:

| Branch | State | Description |
|--------|-------|-------------|
| `main` | Phase 1 + Phase 2 | 5 screens merged, JNI bootstrap (PR #8). Nostr discovery **reverted** (commit `85dfc03`). |
| `feature/fips-path-dep` | 4 commits | FIPS path dep + Applesauce Nostr discovery. Simpler UI (3 Kotlin screens). Has `nostr_discovery.rs`. |
| `fix/wifi-scan-discovery` | Most active | Full 5-screen app, multi-mint CDK wallet, WiFi scanning, V1GatewayClient, FakeWallet. **No `nostr_discovery.rs`**. |
| `phase1/*` (7 branches) | Merged | Individual screen PRs, consolidated into main. |
| `phase2/jni-bootstrap` | Merged | JNI embedder layer (PR #8). |

**Key divergence:** `fix/wifi-scan-discovery` is the most production-ready branch
(full wallet, gateway integration, CI-tested) but **lacks** Nostr discovery.
`feature/fips-path-dep` has Nostr discovery but only a basic 3-screen scaffold.
These branches need to be reconciled — likely by porting `nostr_discovery.rs`
into the `fix/wifi-scan-discovery` codebase.

---

## KNOWN ISSUES

### 1. Nostr Discovery Async Bug (BLOCKING)

File: `tollgate-mobile/src/nostr_discovery.rs` (exists on `feature/fips-path-dep`)

The `discover_exit_nodes()` method (line ~230) is declared as **synchronous**
(`fn`, not `async fn`) but calls `self.fetch_from_nostr().await?` on line 258.
Similarly, `fetch_from_nostr()` is sync but called with `.await`. **This will not
compile.** The background sync path (line 389) also calls `.await` on the sync
method.

**Fix:** Either mark both methods `async fn` (and handle the tokio runtime
correctly within UniFFI), or use `self.runtime.block_on()` to bridge the sync
UniFFI boundary to async internally.

### 2. Nostr Discovery Uses MOCK DATA

`fetch_from_nostr()` returns 3 hardcoded fake exit nodes instead of querying
real Nostr relays:

| # | Mock Pubkey (prefix) | Endpoint | Bandwidth | Uptime |
|---|---------------------|----------|-----------|--------|
| 1 | `020a6d98d5...` | `66.92.204.38:51820` | 100 Mbps | 7 days |
| 2 | `021b7e89f6...` | `95.217.184.52:51820` | 50 Mbps | 2 days |
| 3 | `022c8f9a7f...` | `138.68.1.234:51820` | 25 Mbps | 1 day |

All use `"mock_signature"` — signature verification is not implemented.

**What exists:** `DiscoveryConfig` with 5 relay URLs configured, scoring
algorithm (bandwidth/uptime/features/recency), cache with TTL, background sync
loop. The infrastructure is ready; only the actual Nostr query is stubbed.

### 3. Branch Reconciliation Needed

`fix/wifi-scan-discovery` (production app) and `feature/fips-path-dep` (Nostr
discovery) have diverged by ~71 files / 13,718 insertions. The Nostr discovery
module needs to be ported into the production branch. Simple cherry-pick won't
work — the surrounding code structure is too different.

---

## WORKSPACE STRUCTURE

### Rust Core (`tollgate-mobile/`)
```
tollgate-mobile/
├── src/
│   ├── lib.rs              — TollgateMobileNode (UniFFI), detect/pay/consume, wallet facade
│   ├── nostr_discovery.rs  — Applesauce Nostr FIPS exit node discovery (MOCK + async bug)
│   ├── jni.rs              — JNI bootstrap layer (Phase 2, on main only)
│   ├── jni_tests.rs        — JNI tests
│   └── wallet.rs           — CDK wallet ops (on fix/wifi-scan-discovery only)
├── tests/
│   ├── mock_gateway.rs     — Mock gateway for testing
│   ├── wallet_e2e.rs       — Wallet end-to-end tests
│   ├── wallet_facade_e2e.rs
│   └── wallet_ops_e2e.rs
├── examples/
│   ├── test_mint.rs        — Manual mint testing
│   └── test_cdk_quote.rs   — CDK quote testing
└── build.rs
```

### Kotlin Shell (`android/app/src/main/kotlin/org/opentollgate/android/`)
On `fix/wifi-scan-discovery` (most complete):
```
MainActivity.kt           — Entry point, Compose host
TollGateApp.kt            — Navigation scaffold (5 screens)
TollgateViewModel.kt      — ViewModel: bridges UI to Rust core + wallet ops
DiscoverScreen.kt         — WiFi/network discovery
PayScreen.kt              — Cashu bootstrap-token payment
SettingsScreen.kt         — Identity, FIPS config, about
StatusScreen.kt           — Live session telemetry
WalletScreen.kt           — Balance, mints, token history
WalletOnlyScreen.kt       — Standalone wallet (mint + swap)
V1GatewayClient.kt        — HTTP :2121 protocol client
WifiTollGateScanner.kt    — SSID scan for TollGate networks
WifiNetworkConnector.kt   — WiFi connect + active network binding
FipsConnectionManager.kt  — FIPS session management
TollGateVpnService.kt     — VPN service (TUN fd handoff)
NativeCore.kt             — JNI declarations (Phase 2)
UdpTransport.kt           — DatagramSocket byte-bridge
model/UiState.kt          — Centralized UI state (Cashu, wallet, gateway)
model/DiscoveredPeer.kt   — Peer discovery model
model/Wallet.kt           — Wallet state, transactions, mints
util/CashuToken.kt        — Cashu token parsing
util/Format.kt            — Formatting utilities
```

### Key Dependencies (path deps in Cargo.toml)
- `tollgate-protocol` from `~/repos/tollgate-rs/crates/tollgate-protocol`
- `tollgate-core` from `~/repos/tollgate-rs/crates/tollgate-core`
- `fips` from `reference/fips` (local gitignored checkout — clone with `git clone --depth 1 https://github.com/k0sti/fips.git reference/fips`)
- `cashu` (CDK) from git rev `63866dc` (matched to tollgate-rs for cache warmth)
- `uniffi` 0.28, `tokio` 1.x, `reqwest` 0.12 (rustls-tls), `secp256k1` 0.30

---

## BUILD NOTES

```bash
# Set warm cache (shared with tollgate-rs)
export CARGO_TARGET_DIR=/home/c03rad0r/repos/tollgate-rs/target

# Host tests (from repo root)
cd ~/repos/tollgate-android  # or ~/worktrees/ws-tollgate-android
cargo test -p tollgate-mobile

# Cross-compile Rust for Android arm64
export ANDROID_NDK_HOME=~/Android/Sdk/ndk/27.2.12479018
cargo ndk -t arm64-v8a build -p tollgate-mobile --release

# Build APK
cd android && ./gradlew assembleDebug

# Install on device
cd android && ./gradlew installDebug
```

- Use **rustls** (not native-tls) — avoids OpenSSL/NDK issues.
- Match dependency versions to `tollgate-rs` for cache warmth.
- `reference/fips` must be cloned before building on `feature/fips-path-dep`.

---

## BOARD STATUS: `tollgate-android`

**Verified 2026-07-17:**

| Status | Count |
|--------|-------|
| done | 30 |
| archived | 2 |
| triage | 0 |
| todo | 0 |
| ready | 0 |
| running | 0 |
| blocked | 0 |

**Assignees:** manager (5 done), worker-base (9 done), worker-tollgate (16 done)

**Archived (2):**
- `t_7d7b45ff` — PR #2: StatusScreen (superseded by consolidated PR)
- `t_56075922` — PR #4: WalletScreen (superseded by consolidated PR)

**Completed milestones:**
- Phase 0: FIPS path dependency ✅
- Phase 1: All 5 screens (discover/pay/settings/status/wallet) + consolidated PR ✅
- Phase 1 validation: Full test suite + APK build + CI pipeline ✅
- Phase 2: JNI bootstrap layer (OnLoad, channel bridge, TUN fd, peer/advert views, VPN service, retry loop, UDP transport) ✅
- WiFi scan discovery + multi-mint CDK wallet (on `fix/wifi-scan-discovery`) ✅

**No open tasks** — board is clear. New work needs new tasks.

---

## NOSTR DISCOVERY DETAILS

The Applesauce Nostr discovery module (`nostr_discovery.rs`) is designed to find
FIPS exit nodes via Nostr relay queries using NIP kind 31213 announcements.
It was added in commit `6f1d255`, merged into `feature/fips-path-dep` in
`0b4dfef`, but **reverted on `main`** in commit `85dfc03`.

**What works:**
- `FipsExitNodeAnnouncement` struct with validation (pubkey format, addr presence, version format, timestamp freshness)
- Scoring algorithm: FIPS version (50pts) + mobile support (30pts) + tollgate support (20pts) + bandwidth (up to 50pts) + uptime (up to 20pts) + recency (up to 30pts)
- `FipsExitNodeInfo` UniFFI Record for Kotlin consumption
- `DiscoveryConfig` with 5 relay URLs: damus.io, nos.lol, nostr.mom, orangesync.tech x2
- Cache with configurable TTL (default 5 min)
- Background sync loop (60s interval)
- Best-node selection (score + latency)
- Unit tests (validation, scoring, conversion)

**What doesn't work:**
- `fetch_from_nostr()` — returns hardcoded mock data, not real relay queries
- Async compilation — `.await` on sync functions (won't compile)
- Signature verification — all mock nodes use "mock_signature"
- Latency probing — always returns -1ms

**UniFFI boundary:** `TollgateMobileNode` exposes `new`, `pubkey_hex`, `detect`,
`pay`, `start_consume`, `poll_event`, `stop_consume`, `auto_mint`, `swap_tokens`,
`receive_token`, `request_mint_quote`, `check_mint_quote`, `mint_tokens`.

---

## WALLET INTEGRATION (fix/wifi-scan-discovery)

On the most active branch, the app has full Cashu/CDK wallet integration:

- **Multi-mint auto-topup:** 5 mints auto-minted to 2121 sats on startup
  - FakeWallet (192.168.2.33:4444) — instant settle, dev only
  - coinos.io, minibits, nofee testnut, lnwallet.app — 120s settle via LN
- **Payment flow:** Request LN invoice → pay → poll quote → mint tokens → pay gateway
- **V1 gateway protocol:** HTTP :2121 — detect, pay (POST Cashu token), balance, whoami
- **WiFi integration:** SSID scan + connect + active-network binding for gateway routing
- **Session monitoring:** Live /balance polling with uptime, usage, remaining data

---

## INTEGRATION POINTS

1. **tollgate-rs** (`~/repos/tollgate-rs/`) — Protocol wire types + core logic (path deps)
2. **microFIPS** (`~/repos/microfips/`) — P4.1 exit node integration (ESP-NOW mesh → WiFi → FIPS VPS)
3. **FIPS reference** (`reference/fips`) — k0sti/fips git checkout for FIPS mesh protocol
4. **tollgate-router** (`~/repos/tollgate-router/`) — OpenWrt gateway that the app connects to
5. **FakeWallet** — Dev mint at 192.168.2.33:4444 (must be on TollGate WiFi subnet)
6. **FIPS VPS** — Exit node at 66.92.204.38:2121 (referenced in mock Nostr data)

---

## NEXT ACTIONS

1. **Fix Nostr discovery async bug** — Mark `discover_exit_nodes()` and
   `fetch_from_nostr()` as `async fn` or use `block_on()` for the UniFFI sync
   boundary. Verify compilation.
2. **Reconcile branches** — Port `nostr_discovery.rs` from `feature/fips-path-dep`
   into `fix/wifi-scan-discovery` (the production branch with full 5-screen app).
3. **Implement real Nostr queries** — Replace mock data in `fetch_from_nostr()`
   with actual relay connections using Applesauce or `nostr-sdk`.
4. **Add signature verification** — Verify `FipsExitNodeAnnouncement` signatures
   against the announced pubkey.
5. **Add latency probing** — TCP/UDP ping to exit node endpoints, update
   `FipsExitNodeInfo.latency_ms`.
6. **Verify ngit push** — Confirm ngit remote works or remove if non-functional.
7. **Create new kanban tasks** for the above — board is currently clear (0 open tasks).

---

## COORDINATION PROTOCOL

- Report status + blockers to balloon-hermes Signal group
- Cross-workstream dependencies → escalate to balloon-hermes
- All code as PRs — never push directly to main
- Push to `github` remote for shared visibility; `ngit` as mirror if working
- Worktree at `~/worktrees/ws-tollgate-android/` — never use `/tmp`
- Scrub PII from all public artifacts
