# EXTRACTION-LOG — Tollgate Payment Core Extraction

**Date:** 2026-07-29
**Source:** `~/worktrees/balloon-tollgate/` (branch: `balloon-tollgate-c3-port`)
**Target:** `~/worktrees/balloon-tollgate-fresh/mesh-stack/tollgate/`
**Policy:** ADR-024 — source repos are READ-ONLY. Copy only, never modify source.

---

## Files Copied

### 1. components/tollgate_core/ — Radio-Agnostic Business Logic

| Source Path | Target Path | Notes |
|---|---|---|
| `components/tollgate_core/include/tollgate_core.h` | `components/tollgate_core/include/tollgate_core.h` | Main API header |
| `components/tollgate_core/include/tollgate_platform.h` | `components/tollgate_core/include/tollgate_platform.h` | Platform abstraction interface |
| `components/tollgate_core/src/tollgate_core.c` | `components/tollgate_core/src/tollgate_core.c` | Main core logic |
| `components/tollgate_core/src/tollgate_core_cashu.c` | `components/tollgate_core/src/tollgate_core_cashu.c` | Cashu token receive/validate/swap |
| `components/tollgate_core/src/tollgate_core_cashu.h` | `components/tollgate_core/src/tollgate_core_cashu.h` | |
| `components/tollgate_core/src/tollgate_core_session.c` | `components/tollgate_core/src/tollgate_core_session.c` | Payment session management |
| `components/tollgate_core/src/tollgate_core_session.h` | `components/tollgate_core/src/tollgate_core_session.h` | |
| `components/tollgate_core/src/tollgate_core_portal.c` | `components/tollgate_core/src/tollgate_core_portal.c` | Portal logic — payment flow |
| `components/tollgate_core/src/tollgate_core_portal.h` | `components/tollgate_core/src/tollgate_core_portal.h` | |
| `components/tollgate_core/src/tollgate_core_firewall.c` | `components/tollgate_core/src/tollgate_core_firewall.c` | Access control after payment |
| `components/tollgate_core/src/tollgate_core_firewall.h` | `components/tollgate_core/src/tollgate_core_firewall.h` | |
| `components/tollgate_core/src/tollgate_core_mint_health.c` | `components/tollgate_core/src/tollgate_core_mint_health.c` | Mint status checking |
| `components/tollgate_core/src/tollgate_core_mint_health.h` | `components/tollgate_core/src/tollgate_core_mint_health.h` | |
| `components/tollgate_core/src/tollgate_core_beacon.c` | `components/tollgate_core/src/tollgate_core_beacon.c` | Beaconing — discovery |
| `components/tollgate_core/src/tollgate_core_beacon.h` | `components/tollgate_core/src/tollgate_core_beacon.h` | |

**CMakeLists.txt:** Adapted — removed mining, stratum, market, dns, client sources (6 files dropped from SRCS list).

### 2. components/tollgate_esp/ — ESP-IDF Platform Implementation

| Source Path | Target Path | Notes |
|---|---|---|
| `components/tollgate_esp/src/tollgate_esp_platform.c` | `components/tollgate_esp/src/tollgate_esp_platform.c` | Platform impl |
| `components/tollgate_esp/tollgate_esp_platform.h` | `components/tollgate_esp/tollgate_esp_platform.h` | Platform header |
| `components/tollgate_esp/idf_component.yml` | `components/tollgate_esp/idf_component.yml` | Component metadata |

**CMakeLists.txt:** Adapted — `PRIV_INCLUDE_DIRS` path unchanged (`../../main` still resolves correctly within the tollgate/ directory).

### 3. components/nucula_lib/ — Cashu Wallet Library

| Source Path | Target Path | Notes |
|---|---|---|
| `components/nucula_lib/nucula_wallet.cpp` | `components/nucula_lib/nucula_wallet.cpp` | C++ bridge to nucula::Wallet |
| `components/nucula_lib/nucula_wallet.h` | `components/nucula_lib/nucula_wallet.h` | C API header |
| `nucula_src/main/crypto.c` | `components/nucula_lib/nucula_src_main/crypto.c` | Vendored from nucula submodule |
| `nucula_src/main/crypto.h` | `components/nucula_lib/nucula_src_main/crypto.h` | |
| `nucula_src/main/wallet.cpp` | `components/nucula_lib/nucula_src_main/wallet.cpp` | |
| `nucula_src/main/wallet.hpp` | `components/nucula_lib/nucula_src_main/wallet.hpp` | |
| `nucula_src/main/cashu_json.cpp` | `components/nucula_lib/nucula_src_main/cashu_json.cpp` | |
| `nucula_src/main/cashu_json.hpp` | `components/nucula_lib/nucula_src_main/cashu_json.hpp` | |
| `nucula_src/main/cashu.hpp` | `components/nucula_lib/nucula_src_main/cashu.hpp` | |
| `nucula_src/main/nut10.cpp` | `components/nucula_lib/nucula_src_main/nut10.cpp` | |
| `nucula_src/main/nut10.hpp` | `components/nucula_lib/nucula_src_main/nut10.hpp` | |
| `nucula_src/main/hex.c` | `components/nucula_lib/nucula_src_main/hex.c` | |
| `nucula_src/main/hex.h` | `components/nucula_lib/nucula_src_main/hex.h` | |
| `nucula_src/main/http.c` | `components/nucula_lib/nucula_src_main/http.c` | |
| `nucula_src/main/http.h` | `components/nucula_lib/nucula_src_main/http.h` | |

**CMakeLists.txt:** Adapted — `NUCULA_SRC` path changed from `../../nucula_src/main` to local `nucula_src_main` directory.

### 4. components/secp256k1/ — libsecp256k1 (Dependency of nucula_lib)

| Source Path | Target Path | Notes |
|---|---|---|
| `components/secp256k1/` (symlink → resolved) | `components/secp256k1/` | Full copy including libsecp256k1/ tree |
| `CMakeLists.txt` | `components/secp256k1/CMakeLists.txt` | Unchanged — uses `${CMAKE_CURRENT_SOURCE_DIR}` |
| `libsecp256k1-config.h` | `components/secp256k1/libsecp256k1-config.h` | |
| `libsecp256k1/` (entire tree) | `components/secp256k1/libsecp256k1/` | Removed nested `.git` file |

**Note:** In the source repo this was a symlink to `/home/c03rad0r/esp32-tollgate/nucula_src/components/secp256k1`. Copied as real files for self-containment.

### 5. main/ — Application-Level Extracted Files

| Source Path | Target Path | Notes |
|---|---|---|
| `main/config.c` | `main/config.c` | Config loading, nsec |
| `main/config.h` | `main/config.h` | |
| `main/identity.c` | `main/identity.c` | nsec → identity derivation |
| `main/identity.h` | `main/identity.h` | |
| `main/nostr_event.c` | `main/nostr_event.c` | Nostr event signing |
| `main/nostr_event.h` | `main/nostr_event.h` | |
| `main/mint_health.c` | `main/mint_health.c` | Mint health (main/ version) |
| `main/mint_health.h` | `main/mint_health.h` | |
| `main/geohash.c` | `main/geohash.c` | Location encoding |
| `main/geohash.h` | `main/geohash.h` | |

---

## Files NOT Copied (Left in Source Repo)

### From components/tollgate_core/src/ — Mining/Stratum/Market/DNS/Client

| File | Reason |
|---|---|
| `tollgate_core_mining.c` / `.h` | Balloon-irrelevant (PoW mining) |
| `tollgate_core_stratum_client.c` / `.h` | Balloon-irrelevant (Stratum v2 mining protocol) |
| `tollgate_core_stratum_proxy.c` / `.h` | Balloon-irrelevant (Stratum proxy) |
| `tollgate_core_market.c` / `.h` | Balloon-irrelevant (marketplace) |
| `tollgate_core_dns.c` / `.h` | DNS hijacking — balloon uses different transport (LoRa, not captive portal DNS) |
| `tollgate_core_client.c` / `.h` | Balloon-irrelevant (tollgate-to-tollgate client) |

### From main/ — Display/Hardware/Mining/Marketplace/Client

| File | Reason |
|---|---|
| `display.c` / `.h` | Hardware-specific (QSPI TFT) |
| `font.c` / `.h` | Display dependency |
| `touch.c` / `.h` | Hardware-specific (touch panel) |
| `keyboard.c` / `.h` | Hardware-specific (keypad) |
| `asic_miner.c` / `.h` | Balloon-irrelevant (ASIC mining) |
| `sw_miner.c` / `.h` | Balloon-irrelevant (software mining) |
| `stratum_client.c` / `.h` | Balloon-irrelevant (Stratum v2) |
| `stratum_proxy.c` / `.h` | Balloon-irrelevant (Stratum proxy) |
| `remote_miner.c` / `.h` | Balloon-irrelevant (remote mining) |
| `market.c` / `.h` | Balloon-irrelevant (marketplace) |
| `beacon_price.c` / `.h` | Balloon-irrelevant (price beacon) |
| `cvm_server.c` / `.h` | Balloon-irrelevant (ContextVM/MCP server) |
| `mcp_handler.c` / `.h` | Balloon-irrelevant (MCP tool handlers) |
| `tollgate_client.c` / `.h` | Balloon-irrelevant (tollgate client) |
| `wifistr.c` / `.h` | Balloon-irrelevant (WiFi service discovery — balloon uses LoRa) |
| `negentropy_adapter.c` / `.h` | Balloon-irrelevant (NIP-77 set reconciliation) |
| `relay_selector.c` / `.h` | Balloon-irrelevant (NIP-11 relay selection) |
| `sync_manager.c` / `.h` | Balloon-irrelevant (REQ-diff sync) |
| `lightning_payout.c` / `.h` | Balloon-irrelevant (Lightning payout) |
| `lnurl_pay.c` / `.h` | Balloon-irrelevant (LNURL pay) |
| `wifi_setup.c` / `.h` | Balloon-irrelevant (WiFi setup wizard) |
| `nip04.c` / `.h` | Balloon-irrelevant (NIP-04 DM encryption) |
| `tls_worker.c` / `.h` | Balloon-irrelevant (TLS worker) |
| `captive_portal.c` / `.h` | WiFi captive portal — balloon uses LoRa transport, not captive portal |
| `dns_server.c` / `.h` | DNS hijack — balloon uses different transport |
| `tollgate_api.c` / `.h` | HTTP API server — balloon uses different transport |
| `tollgate_main.c` | Entry point — balloon will have its own app_main |
| `faucet_client.c` / `.h` | Balloon-irrelevant (faucet client) |
| `local_relay.c` / `.h` | Balloon-irrelevant (local Nostr relay on WiFi) |

### From nucula_src/main/ — Non-Wallet nucula App Files

| File | Reason |
|---|---|
| `bip39.c` / `.h` / `bip39_english.h` | BIP39 mnemonic — not needed for Cashu wallet bridge |
| `cashu_cbor.cpp` / `.hpp` | CBOR format — not used by wallet bridge (uses JSON) |
| `console.cpp` / `.h` | REPL console — not needed |
| `crypto_test.c` / `.h` | Test files — not needed for build |
| `display.cpp` / `.h` | nucula display — hardware-specific |
| `keypad.c` / `.h` | Keypad input — hardware-specific |
| `ndef.cpp` / `.hpp` | NFC NDEF — hardware-specific |
| `nfc.cpp` / `.hpp` | NFC — hardware-specific |
| `nucula.cpp` | nucula app main — not needed for wallet bridge |
| `wifi.c` / `.h` | WiFi config — hardware-specific |
| `wifi_config.example.h` | Example config — not needed |

### Other Source Components NOT Copied

| Component | Reason |
|---|---|
| `components/esp_littlefs/` | LittleFS for relay storage — not needed for payment core |
| `components/qrcode/` | QR code generator — display dependency |
| `components/wisp_relay/` | Local Nostr relay — not needed for payment core |

---

## CMakeLists.txt Adaptations Summary

1. **tollgate_core/CMakeLists.txt**: Removed 6 SRCS entries (mining, stratum_client, stratum_proxy, market, dns, client). Kept 7 payment-relevant sources.
2. **tollgate_esp/CMakeLists.txt**: No SRCS change. PRIV_INCLUDE_DIRS `../../main` path still resolves correctly within the tollgate/ tree.
3. **nucula_lib/CMakeLists.txt**: Changed `NUCULA_SRC` from `${CMAKE_CURRENT_SOURCE_DIR}/../../nucula_src/main` to `${CMAKE_CURRENT_SOURCE_DIR}/nucula_src_main`.
4. **secp256k1/CMakeLists.txt**: Unchanged — uses `${CMAKE_CURRENT_SOURCE_DIR}` (self-contained).

---

## Build Notes

- No main/CMakeLists.txt created — the balloon mesh firmware will integrate these components with its own build system.
- The `secp256k1` component was originally a symlink in the source repo; copied as real files for portability.
- Nested `.git` file in `libsecp256k1/` removed (was a submodule gitlink, not needed).
- No compilation performed — per task instructions, build will happen during firmware integration.
