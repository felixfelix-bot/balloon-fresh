# HANDOVER — ESP32-S3 TollGate Workstream

> **Coordinator:** balloon-hermes (top-level coordination hub)
> **Workstream:** ESP32-S3 TollGate (Workstream #1)
> **Created:** 2026-07-17
> **Status:** Operational — worktree ready, unit tests green, board verify BLOCKED

## What This Is

ESP32-S3 firmware for the TollGate captive portal WiFi hotspot. On-device Cashu
e-cash wallet, Nostr identity derivation, local NIP-01 relay (:4869), ContextVM
MCP server, relay selection with auto-failover, Stratum mining, and QSPI display.

**Target hardware:** ESP32-S3, 16MB flash, 8MB PSRAM (OCT mode), 3 boards (A/B/C).
**Framework:** ESP-IDF v5.4.1 (C/C++).

## Repository & Paths

| Item | Path / Value |
|------|-------------|
| **Primary repo** | `~/esp32-tollgate/` |
| **GitHub remote** | `https://github.com/OpenTollGate/tollgate-esp32` (public) |
| **Ngit remote** | `nostr://…relay.ngit.dev/esp32-tollgate` |
| **Worktree** | `~/worktrees/ws-esp32-tollgate/` |
| **Worktree branch** | `ws-esp32-tollgate` (from `master` @ `6d3db7a`) |
| **Hermes profile** | `esp32-tollgate-master` |
| **Kanban board slug** | `esp32-tollgate` |
| **ESP-IDF** | `~/esp/esp-idf` (v5.4.1) |
| **esptool** | `~/.local/bin/esptool.py` (v5.2.0) |

> ⚠️ **MASTER.md path discrepancy:** The coordination MASTER.md lists the primary
> repo as `~/repos/org-scan/tollgate-esp32/` — this path does NOT exist. The actual
> primary repo is `~/esp32-tollgate/`. MASTER.md should be updated.

## Worktree Setup (COMPLETED)

The worktree has been created and verified:

```bash
# Worktree created from master at 6d3db7a
git worktree add ~/worktrees/ws-esp32-tollgate -b ws-esp32-tollgate master

# Submodules initialized (recursive for nucula_src → bitcoin-core/secp256k1)
cd ~/worktrees/ws-esp32-tollgate
git submodule update --init
cd nucula_src && git submodule update --init && cd ..
```

All 3 git submodules are initialized:
- `nucula_src/` — Cashu wallet (zeugmaster/nucula) + nested secp256k1 (bitcoin-core)
- `components/esp_littlefs/` — LittleFS VFS (joltwallet)
- `components/negentropy/` — Set reconciliation (hoytech)

### Unit Tests: ✅ ALL PASS (86/86)

```bash
cd ~/worktrees/ws-esp32-tollgate && make test-unit
# === Results: 86 passed, 0 failed ===
# === ALL UNIT TESTS PASSED ===
```

37 unit test source files covering: geohash, identity, cashu, beacon_price,
cvm_server, deletion, display, faucet_client, firewall, keyboard,
lightning_payout, lnurl_pay, market, mcp_handler, mining, mint_health,
negentropy_adapter, relay_selector, session, and more.

## Board Verification (BLOCKED)

### Kanban Board — CANNOT VERIFY

The GitHub Projects V2 board with slug `esp32-tollgate` could not be verified.
The `gh` CLI token (account `c03rad0r`) is missing the `read:project` scope.

**Current token scopes:** `gist`, `read:org`, `repo`, `workflow`
**Required scope:** `read:project`

**Fix:**
```bash
gh auth refresh -s read:project
```

After refreshing, verify with:
```bash
gh project list
gh project view <NUMBER> --owner c03rad0r  # or OpenTollGate
```

### Physical Boards — NEED REPLUG

Serial devices present but unresponsive (`/dev/ttyACM0-2`, `/dev/ttyUSB0-2`).
`esptool.py chip_id` timed out on all ports — boards likely need physical USB replug.

| Board | Port (nominal) | Factory MAC | SSID | AP IP | Status |
|-------|---------------|-------------|------|-------|--------|
| A | `/dev/ttyACM0` | `94:a9:90:2e:37:7c` | `TollGate-B96D80` | `10.185.47.1` | Unresponsive |
| B | `/dev/ttyACM1` | `fc:01:2c:c5:50:50` | `TollGate-C0E9CA` | `10.192.45.1` | Unresponsive |
| C | `/dev/ttyACM3` | `20:6e:f1:98:d7:08` | (TBD) | (TBD) | Display board |

**Ports change on every USB replug.** Always verify with `esptool chip_id` before flashing.

## Current State (from repo HANDOVER.md — session `curious-nebula`)

### Done
- ✅ Price parsing bug fixed (tag[1] not tag[2])
- ✅ Wallet mutex fixed (RAII WalletLock)
- ✅ Internal RAM stacks fixed
- ✅ Remote miner delay fixed
- ✅ SPIFFS corruption recovery fixed
- ✅ Stack overflow fixed (token_buf to heap)
- ✅ PSRAM mode fixed (CAPS_ALLOC for Board B stability)
- ✅ All 800+ unit test cases pass
- ✅ Clean firmware build
- ✅ Board A flashed and working as upstream
- ✅ Board B flashed and stable 90s+
- ✅ B2B: remote miner shares accepted by Board A
- ✅ B2B: faucet receives ehash through Board A

### Next Steps
- [ ] Unplug + replug ESP32-S3 boards (physical)
- [ ] Verify port assignments (`esptool.py --port <port> chip-id`)
- [ ] Verify B2B: faucet tokens reach wallet (pending keyset load)
- [ ] Verify B2B: ehash payment to Board A for session
- [ ] Run B2B integration test (`node tests/integration/b2b_settlement.mjs`)
- [ ] Refresh gh token scopes and verify kanban board
- [ ] Push `ws-esp32-tollgate` branch to remote

### Architecture Pivot (recent commit `e2fe737`)
GL-E750 is now the primary TollGate gateway; ESP32 serves as client/reseller.
This is a significant architectural change — any new work should account for this.

## Firmware Architecture

### Boot Sequence
```
nvs_flash_init → config_init → identity_init(nsec) → netif/wifi init →
wifi APSTA start → [on STA got IP] start_services:
  sntp, firewall, session, wallet, dns_server, captive_portal,
  tollgate_api (:2121), local_relay (:4869), relay_selector,
  sync_manager, wifistr_publish, cvm_server
```

### Key Subsystems (68 source files in `main/`)

| Subsystem | Files | Description |
|-----------|-------|-------------|
| Entry point | `tollgate_main.c` | WiFi AP+STA, event loop, service lifecycle |
| Config | `config.c/h` | SPIFFS config.json parsing (nsec, wifi, mints) |
| Identity | `identity.c/h` | HMAC-SHA512 from nsec → npub/MAC/SSID/IP |
| Nostr | `nostr_event.c/h`, `nip04.c/h` | NIP-01 events, BIP-340 Schnorr signing |
| Captive portal | `captive_portal.c/h`, `dns_server.c/h` | HTTP :80, DNS hijack, grant/reset |
| Firewall | `firewall.c/h` | Per-client NAT filter (LWIP hook) |
| Sessions | `session.c/h` | Time-based sessions, MAC tracking |
| Cashu | `cashu.c/h` | Token decode, checkstate, allotment |
| API | `tollgate_api.c/h` | HTTP :2121, payment + wallet endpoints |
| CVM Server | `cvm_server.c/h`, `mcp_handler.c/h` | MCP over Nostr, 10 tools |
| Local relay | `local_relay.c/h` | NIP-01 :4869, LittleFS storage |
| Relay selector | `relay_selector.c/h` | NIP-11 probing, scoring, failover |
| Sync | `sync_manager.c/h` | REQ-diff sync (30min primary, 6h fallback) |
| Mining | `asic_miner.c/h`, `beacon_price.c/h` | Stratum, NIP-99 price beacon |
| Display | `display.c/h`, `font.c/h` | QSPI TFT, QR cycling |
| Lightning | `lightning_payout.c/h`, `lnurl_pay.c/h` | LNURL-pay integration |
| Faucet | `faucet_client.c/h` | B2B ehash faucet client |
| Market | `market.c/h` | Plebeian Market integration |
| Mint health | `mint_health.c/h` | Cashu mint monitoring |

### Components (10)

| Component | Purpose |
|-----------|---------|
| `wisp_relay/` | Local Nostr relay (ws_server, storage, sub, broadcaster, rate_limiter) |
| `tollgate_core/` | Shared protocol library |
| `tollgate_esp/` | ESP-specific integration |
| `nucula_lib/` | C++ bridge to nucula::Wallet (Cashu) |
| `secp256k1/` | Symlink → nucula_src/components/secp256k1/ |
| `esp_littlefs/` | LittleFS VFS (relay storage partition) |
| `negentropy/` | Set reconciliation (NIP-77 future) |
| `negentropy_lib/` | Negentropy adapter |
| `axs15231b/` | QSPI TFT display driver (JC3248W535) |
| `qrcode/` | QR code generator |

### Partition Layout
```
nvs         0x9000   24KB
phy_init    0xf000    4KB
factory     0x10000  ~4MB  (application)
storage     0x410000 960KB (SPIFFS config)
relay_store 0x500000 4MB   (LittleFS relay events)
```

## Testing

| Type | Command | Location | Hardware? |
|------|---------|----------|-----------|
| Host unit | `make test-unit` | `tests/unit/` (37 files) | No |
| Integration | `make test-integration` | `tests/integration/` (15 files) | Yes (Board A) |
| E2E | `make test-e2e` | `tests/e2e/` (3 specs) | Yes (Board A) |

**Mandatory rule:** All unit tests must pass before commit. Every new C file needs unit tests.

## Integration Points

| Workstream | Connection |
|-----------|------------|
| TollGate Router (#4) | ESP32 as client to GL-E750 gateway |
| TollGate Android (#7) | Shared protocol, payment flow |
| Balloon/LR2021 (#3) | LoRa telemetry via wifistr events |
| microFIPS Mesh (#2) | Identity derivation shared concepts |
| Infrastructure (#9) | CI/CD, deployment automation |

## Quick Start for New Session

```bash
# Enter worktree
cd ~/worktrees/ws-esp32-tollgate

# Verify environment
source ~/esp/esp-idf/export.sh 2>/dev/null  # ESP-IDF
git branch                    # should show ws-esp32-tollgate
git log --oneline -3          # HEAD at 6d3db7a

# Run tests
make test-unit                # 86 tests, must pass

# Flash board (after USB replug)
esptool.py --port /dev/ttyACM0 chip-id   # verify port first
idf.py -p /dev/ttyACM0 flash monitor

# Push work
git add -A && git commit -m "..."
git push github ws-esp32-tollgate         # GitHub
# or ngit push
```

## Coordinator Authority

This workstream reports to **balloon-hermes**. Cross-workstream dependencies,
integration sequencing, and conflict resolution are decided by the coordinator.
All work goes in the `ws-esp32-tollgate` branch (or feature branches off it).
All commits must be pushed.
