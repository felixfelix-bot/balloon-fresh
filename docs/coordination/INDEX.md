# Balloon Project — Master Index

**Last updated:** 2026-07-17
**Coordinator:** balloon-hermes Signal group
**Purpose:** Single source of truth for all repos, worktrees, branches, remotes, and tracks.
Future context windows should read THIS FILE FIRST to bootstrap.

---

## Architecture Overview

The Balloon Project builds solar-powered pico balloon nodes using ESP32-C3 + LR2021 LoRa radios.
Development is split across 6 independent tracks, each with its own Signal group, worktree, and
source repo. All tracks report to the balloon-hermes coordinator group.

```
                    balloon-hermes (TOP COORDINATOR)
                                |
        +-----------+-----------+-----------+-----------+-----------+
        |           |           |           |           |           |
   Track 1      Track 2     Track 3     Track 4     Track 5     Track 6
   Radio Link   Nostr Relay Tollgate   PoW/Mining  FIPS Mesh   Blossom
                            +Cashu                              Server
```

### Integration Strategy
1. Each track tests features STANDALONE on ESP32-S3 first (where code already runs)
2. Port each to ESP32-C3 (4MB flash, 400KB RAM — no PSRAM)
3. Final integration happens in balloon-hermes (this repo)
4. NO integration until all tracks pass standalone verification

---

## Track 1 — Radio Link (balloon-hermes)

Proven baseline: 1377 kbps, 0% packet loss, FLRC 2600 kbps, bench distance.

| Item | Value |
|------|-------|
| **Repo (source)** | `~/repos/balloon-fresh/` |
| **Worktree** | (same — works directly in repo) |
| **Branch** | `master` |
| **GitHub** | https://github.com/c03rad0r/balloon-fresh |
| **ngit** | relay.ngit.dev/esp32-balloon-integration-fresh-fork |
| **Framework** | ESP-IDF v5.4.1, RadioLib v7.6.0 |
| **Target** | ESP32-C3_Mini_V1 + RP2040 Pico (for radio testing) |

**Status:** Active. Baseline proven. Next: outdoor range sweep (10m/25m/50m/100m).

**Proven Radio Config:** 2440 MHz, FLRC 2600 kbps, CR=1/0, 255-byte payload, +12 dBm, sync 0x12AD101B
**Hardware:** TX board serial E663B035977F242D, RX board serial E663B035973B8332
**Key lesson:** Arduino per-byte SPI.transfer() is the ONLY working SPI method on RP2040. PIO/DMA all failed. Air time (~803us) dominates, not SPI speed.

---

## Track 2 — Nostr Relay (balloon-nostr)

Full NIP-01 Nostr relay for ESP32. WebSocket server, LittleFS storage, Schnorr validation, NIP-11.

| Item | Value |
|------|-------|
| **Source repo** | `~/wisp-esp32/` |
| **Upstream** | https://github.com/privkeyio/wisp-esp32 |
| **Branch (source)** | `main` |
| **Worktree** | `~/worktrees/balloon-nostr/` |
| **Branch (worktree)** | `balloon-nostr-extraction` |
| **Target** | ESP32-S3 (16MB flash, 8MB PSRAM) → port to ESP32-C3 |

**Components:**
- `components/libnostr-c/` — Nostr event handling
- `components/noscrypt/` — Crypto primitives
- `components/secp256k1-frost/` — Schnorr signature library
- `main/ws_server.c` — WebSocket server
- `main/storage_engine.c` — LittleFS event storage
- `main/sub_manager.c` — Subscription manager
- `main/validator.c` — Event validation (Schnorr + SHA256)
- `main/broadcaster.c` — Event broadcaster
- `main/nip11.c` — NIP-11 relay info
- `main/rate_limiter.c` — Rate limiting
- `main/deletion.c` — NIP-09 deletion handling
- `main/flash_monitor.c` — Flash wear monitoring

**Status:** Ready to start. wisp-esp32 works standalone on S3.
**Also embedded in:** `~/esp32-tollgate/components/wisp_relay/` (same code, integrated)

---

## Track 3 — Tollgate / Cashu (balloon-tollgate)

Captive portal WiFi hotspot with Cashu e-cash payments. Runs on 3 physical ESP32-S3 boards.

| Item | Value |
|------|-------|
| **Source repo** | `~/esp32-tollgate/` |
| **GitHub** | https://github.com/OpenTollGate/tollgate-esp32 |
| **ngit (primary)** | relay.ngit.dev/esp32-tollgate |
| **ngit (secondary)** | ngit.orangesync.tech/esp32-tollgate |
| **Branch (source)** | `master` |
| **Worktree** | `~/worktrees/balloon-tollgate/` |
| **Branch (worktree)** | `balloon-tollgate-c3-port` |
| **Target** | ESP32-S3 (16MB/8MB) → port to ESP32-C3 (4MB/400KB) |

**Components needed for balloon:**
- `main/captive_portal.c/h` — HTTP :80 portal, captive detection
- `main/dns_server.c/h` — DNS hijack/forward
- `main/cashu.c/h` — Cashu token decode, checkstate
- `main/session.c/h` — Time-based sessions, MAC tracking
- `main/firewall.c/h` — Per-client NAT filter
- `main/identity.c/h` — HMAC-SHA512 derivation from nsec
- `main/nostr_event.c/h` — NIP-01 serialization + Schnorr signing
- `components/nucula_lib/` — Cashu wallet C++ bridge
- `components/wisp_relay/` — Local Nostr relay (same as Track 2)

**Components to STRIP (not needed for balloon):**
- `main/display.c/h`, `main/font.c/h` — TFT display
- `main/cvm_server.c/h`, `main/mcp_handler.c/h` — ContextVM
- `main/wifistr.c/h` — Service discovery (may re-add later)
- Mining components (separate Track 4)

**Boards:**
- Board A: MAC 94:a9:90:2e:37:7c, SSID TollGate-B96D80, IP 10.185.47.1
- Board B: MAC fc:01:2c:c5:50:50, SSID TollGate-C0E9CA, IP 10.192.45.1
- Board C: MAC 20:6e:f1:98:d7:08

**Status:** Ready to start. Works on 3 boards.

---

## Track 4 — PoW / Mining (balloon-pow)

Software SHA256 mining + Stratum v1/v2 client for ESP32.

| Item | Value |
|------|-------|
| **Source repo** | `~/esp32-tollgate/` (mining components) |
| **Worktree** | `~/worktrees/balloon-pow/` |
| **Branch (worktree)** | `balloon-pow-extraction` |
| **Target** | ESP32-S3 → evaluate ESP32-C3 feasibility |

**Mining files:**
- `main/sw_miner.c/h` — Software SHA256 mining (~10-50 kH/s on S3)
- `main/stratum_client.c/h` — Stratum v1 protocol client
- `main/stratum_proxy.c/h` — Stratum proxy (v2 support)
- `main/asic_miner.c/h` — BM1366 ASIC interface (stub)
- `main/remote_miner.c/h` — Remote mining via HTTP

**Status:** Ready to start. User creating dedicated group.

---

## Track 5 — FIPS Mesh (balloon-fips)

Encrypted mesh protocol (Noise IK/XK) with LR2021 LoRa transport.

| Item | Value |
|------|-------|
| **Source repo** | `~/repos/microfips-upstream/` |
| **Branch (source)** | `main` |
| **Worktree** | `~/worktrees/balloon-fips/` |
| **Branch (worktree)** | `balloon-fips-lr2021` |
| **Remote** | None configured (local only — needs remote setup) |
| **Language** | Rust (no_std) |

**Existing protocol:** M0-M11 complete (Noise IK/XK, FSP sessions). Transports: UART, BLE, WiFi, ESPNOW.
**GAP:** No LR2021/LoRa transport layer. This track builds it.

**Status:** Ready to start. Needs git remote configured.

---

## Track 6 — Blossom Server (balloon-blossom)

ESP32 Blossom media server (BUD-01/BUD-02 protocol). Greenfield — no server code exists.

| Item | Value |
|------|-------|
| **Worktree** | `~/worktrees/balloon-blossom/` |
| **Branch** | `main` |
| **Remote** | None yet (new repo, needs GitHub remote) |
| **Reference** | `~/repos/prta-review/lib/blossom_publisher.py` (Python uploader) |

**Status:** Greenfield. Design phase first.

---

## Additional Repos (Reference / Legacy)

| Repo | Path | Notes |
|------|------|-------|
| esp32-tollgate-relay | `~/esp32-tollgate-relay/` | Relay-hardened fork of tollgate. No remotes. |
| esp32-mesh | `~/esp32-mesh/` | Captive portal mesh + ecash. ngit: relay.ngit.dev/esp32-mesh. Branch: feature/redeem-ecash |
| esp32-balloon-integration | `~/esp32-balloon-integration/` | Predecessor to balloon-fresh. Superseded. |
| esp32-balloon-integration-meshcore-pr | `~/esp32-balloon-integration-meshcore-pr/` | MeshCore LR2021 PR prep. |
| meshcore-fork-fix | `~/repos/meshcore-fork-fix/` | Not a git repo. Reference only. |

---

## Hardware Inventory

### Flight Platform
- 20x ESP32-C3_Mini_V1 (22.52x18mm, USB-C, U.FL antenna) — balloon flight target
- 2x XIAO ESP32-C5 — alternative MCU
- 4x NiceRF LoRa2021 modules (19.72x15x2.2mm, LR2021 Gen 4)
- 3x EBYTE E28-2G4M27S (SX1281, 2.4 GHz, +27 dBm PA)

### Dev Platform (Track 2-4 current)
- 3x ESP32-S3 boards (Board A/B/C from tollgate) — 16MB flash, 8MB PSRAM

### Test Equipment
- 2x RP2040 Pico (for radio TX/RX testing via Arduino)
- 1x Cyclone IV FPGA + USB Blaster (bench-only)
- 1x Xilinx DLC9LP (bench-only)
- 1x Red Pitaya
- 1x Saleae-compatible logic analyzer (3MHz bare, 50MHz with external)

### Power / Mechanical
- 100x Solar cells 52x19mm (0.5V 400mA)
- 50x Solar cells 78x39mm (0.54W 0.5V)
- 30x DecoGlee 18" foil party balloons
- ~43x Neodymium magnets 10x2mm (~1.21g test weights)
- 1x Pressure sensor + pump (balloon testing)
- 1x MS300 jewelry scale
- 1x Digital calipers

---

## ESP32-C3 Flight Constraints

All tracks must port to this target for balloon integration:

| Parameter | ESP32-C3 (flight) | ESP32-S3 (dev) |
|-----------|-------------------|----------------|
| Flash | 4MB | 16MB |
| RAM | 400KB (no PSRAM) | 8MB PSRAM |
| Cores | 1 (single-core) | 2 (dual-core) |
| Clock | 160 MHz | 240 MHz |
| WiFi | Yes (b/g/n) | Yes |
| BT | BLE 5.0 | BLE 5.0 |
| USB | USB-C (CDC) | USB-C |

**Strapping pins to avoid:** GPIO8 (HIGH at boot), GPIO9 (LOW at boot = download mode)
**Safe I2C:** GPIO20/GPIO21 (not GPIO8/GPIO9)
**JTAG pins (GPIO4-7):** Usable as GPIO when JTAG not enabled

---

## Coordination Documents

All in `~/balloon-coordination/` (mirrored in this repo at `docs/coordination/`):

- `README.md` — Track overview, integration strategy
- `kanban-board.md` — Task-level tracking for all 6 tracks
- `handover-balloon-nostr.md` — Paste-ready prompt for Track 2
- `handover-balloon-tollgate.md` — Paste-ready prompt for Track 3
- `handover-balloon-pow.md` — Paste-ready prompt for Track 4
- `handover-balloon-fips.md` — Paste-ready prompt for Track 5
- `handover-balloon-blossom.md` — Paste-ready prompt for Track 6

---

## Pin Mapping (ESP32-C3 + LR2021)

```
LR2021 Pin   ESP32 GPIO  Function
Pin 3        GPIO2       MISO (strapping, OK as input)
Pin 4        GPIO7       MOSI
Pin 5        GPIO6       SCK
Pin 6        GPIO10      CS (NSS)
Pin 7        GPIO4       BUSY
Pin 9        ---         ANT (Sub-GHz, 50 Ohm)
Pin 10       ---         2.4G (50 Ohm)
Pin 14       GPIO3       RST
Pin 15       GPIO5       DIO9 (IRQ)
Pin 16       GPIO1       DIO8
Pin 17       GPIO0       DIO7
```

RadioLib: `radio.irqDioNum = 9`, call `setDioFunction()`.

---

## Build Environment

```bash
# ESP-IDF (C/C++ firmware)
source ~/esp/esp-idf/export.sh
cd <project> && idf.py build
idf.py -p /dev/ttyACM0 flash monitor

# Rust (microfips)
cargo build --target riscv32imc-unknown-none-elf

# Verify board port before flashing (ports change on replug)
esptool.py --port /dev/ttyACM0 chip_id
```

---

## Cross-Track Dependencies

- Track 5 (FIPS) depends on Track 1 (radio link proven) for LR2021 transport
- Track 6 (Blossom) depends on Track 2 (Nostr relay) for NIP-94 events
- Final integration depends on ALL tracks passing standalone tests
- Track 3 (Tollgate) and Track 2 (Nostr) share wisp_relay component

---

## How to Bootstrap a New Session

1. Read THIS file (docs/coordination/INDEX.md)
2. Check `~/balloon-coordination/kanban-board.md` for current task status
3. Read the relevant handover doc for your track
4. cd to the correct worktree
5. Check `git status` and `git log --oneline -5` in the worktree
6. Start working

**All worktrees are in `~/worktrees/`. NEVER create worktrees in /tmp.**
**Done = pushed. Commit and push ALL changes before ending a session.**
