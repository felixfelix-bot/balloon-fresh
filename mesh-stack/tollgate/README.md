# Balloon Tollgate — Payment Layer for Internet Transport

Captive portal + Cashu payment processing for balloon-based internet access.

## Architecture (per ADR-024)

Extract ONLY balloon-relevant components from tollgate-esp32 source repo.
Source repo (`~/worktrees/balloon-tollgate/`, branch `balloon-tollgate-c3-port`) is READ-ONLY.

## Directory Structure

```
mesh-stack/tollgate/
  README.md                ← this file
  EXTRACTION-LOG.md        ← complete extraction record (what was copied, what was not)
  components/
    tollgate_core/         ← radio-agnostic payment business logic
      include/
        tollgate_core.h        — main API
        tollgate_platform.h    — platform abstraction interface
      src/
        tollgate_core.c            — init, lifecycle
        tollgate_core_cashu.c/h    — Cashu token receive/validate/swap
        tollgate_core_session.c/h  — payment session management
        tollgate_core_portal.c/h   — portal logic, payment flow
        tollgate_core_firewall.c/h — access control after payment
        tollgate_core_mint_health.c/h — mint status checking
        tollgate_core_beacon.c/h   — beaconing for discovery
      CMakeLists.txt
    tollgate_esp/          ← ESP-IDF platform implementation
      src/
        tollgate_esp_platform.c    — implements tollgate_platform.h for ESP-IDF
      tollgate_esp_platform.h
      idf_component.yml
      CMakeLists.txt
    nucula_lib/            ← Cashu wallet library (C++ bridge)
      nucula_wallet.cpp/h      — C API wrapping nucula::Wallet
      nucula_src_main/         — vendored nucula source (wallet-relevant files only)
        crypto.c/h, wallet.cpp/hpp, cashu_json.cpp/hpp, cashu.hpp,
        nut10.cpp/hpp, hex.c/h, http.c/h
      CMakeLists.txt
    secp256k1/             ← libsecp256k1 (dependency of nucula_lib)
      CMakeLists.txt
      libsecp256k1-config.h
      libsecp256k1/            — full upstream source
  main/                    ← application-level extracted files
    config.c/h             — config.json loading, nsec
    identity.c/h           — nsec → MAC/SSID/IP derivation (HMAC-SHA512)
    nostr_event.c/h        — NIP-01 event serialization + BIP-340 Schnorr signing
    mint_health.c/h        — mint health checking (HTTP probe)
    geohash.c/h            — lat/lon → geohash encoding
```

## What Was Extracted

- **Payment core:** Cashu token processing, session management, portal logic, firewall, mint health
- **Identity:** nsec → Nostr identity derivation, event signing
- **Config:** SPIFFS config.json loading
- **Wallet:** nucula Cashu wallet with secp256k1 crypto
- **Discovery:** beaconing
- **Location:** geohash encoding

## What Was NOT Extracted (Left in Source Repo)

- Display/font/touch/keyboard (hardware UI)
- ASIC/software mining, Stratum v2 client/proxy, remote miner
- Marketplace, price beacon
- ContextVM/MCP server
- WiFi captive portal, DNS server, HTTP API server (balloon uses LoRa, not WiFi captive portal)
- wifistr, relay selector, sync manager (WiFi/relay infrastructure)
- Lightning payout, LNURL pay, WiFi setup, NIP-04, TLS worker
- Local Nostr relay (wisp_relay)

See EXTRACTION-LOG.md for the complete file-by-file record.

## Build

This extraction is source-only. Build integration will happen when the balloon
mesh firmware project (`mesh-stack/firmware/`) adds these components to its
ESP-IDF build. No CMakeLists.txt is provided for `main/` — the balloon firmware
will provide its own `app_main` and source list.

## Worktree

- Source: `~/worktrees/balloon-tollgate/` (READ-ONLY, branch `balloon-tollgate-c3-port`)
- Target: `~/worktrees/balloon-tollgate-fresh/mesh-stack/tollgate/` (branch `balloon-tollgate-extract`)
