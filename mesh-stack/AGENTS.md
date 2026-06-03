# Mesh Stack - AI Agent Instructions

## Overview
Multi-balloon mesh relay network for internet transport. Balloons at ~12 km altitude relay traffic between ground stations using LR2021 dual-band (Sub-GHz + 2.4 GHz). Stack: FIPS mesh networking + MeshCore community mesh + TollGate payments + Nostr async messaging.

## Architecture (see ADR-012 and INTEGRATION-ARCHITECTURE.md)

| Layer | Protocol | Role |
|-------|----------|------|
| L7 | TollGate + Nostr | Cashu payments + async messaging |
| L6 | FIPS Noise XK | End-to-end encrypted sessions |
| L5 | FIPS mesh routing | Spanning-tree + bloom-filter discovery |
| L4 | UDP/IP tunnel | Transport over FIPS mesh |
| L3 | Wirehair + sx1280-serial fragmentation | Erasure-coded fragmentation |
| L2 | TDMA dual-band scheduler | Sub-GHz (MeshCore) + 2.4 GHz (FIPS) |
| L1 | LR2021 radio | LoRa/FLRC dual-band |

**Dual-band allocation**:
- **Sub-GHz (868 MHz)**: MeshCore repeater (community mesh, coverage mapping)
- **2.4 GHz**: FIPS transport (mesh networking, Nostr events, TollGate relay)

## Key Constraints
- **Not Starlink**: Realistic targets 1-130 kbps per link, 4-520 kbps aggregated
- **UDP not TCP**: RTT too high for TCP congestion control
- **Erasure coding (Wirehair)**: Eliminates per-packet ACKs, works with 30-37% packet loss
- **Balloon = natural TDMA coordinator**: Visible to all ground stations, GS can't see each other
- **No WiFi/BLE on balloon**: All communication over LoRa. Nostr goes over FIPS over LoRa.
- **Night-off mandatory**: Dual-band mesh draws ~134 mW, requires 8-12 solar cells

## Performance Targets

### V1 (Mesh V1, ~11.5g, night-off)
- 2.4 GHz @ +22 dBm: 22 kbps @ 300 km (FIPS)
- Sub-GHz @ +22 dBm: MeshCore repeater to 700+ km
- Net throughput ~40% of air rate: ~9 kbps per FIPS link
- 4x MultiWAN: ~36 kbps @ 300 km
- Avg power: ~134 mW (dual-band TDMA), night-off default

### V2 (Mesh V2, ~18-22g, night-active)
- 2.4 GHz @ +30 dBm with PCB Yagis: 38-87 kbps @ 300 km
- 4x MultiWAN: ~150-350 kbps @ 300 km
- Avg power: ~431 mW, night-active with larger caps

## Key Files
- `docs/adr/012-mesh-networking-strategy.md` — Strategic architecture decision (FIPS + MeshCore + TollGate + Nostr)
- `docs/adr/013-cluster-aware-stratorelay.md` — Cluster-aware stratorelay decision
- `mesh-stack/INTEGRATION-ARCHITECTURE.md` — Detailed technical architecture, dual-band plan, TDMA, Nostr-over-FIPS
- `mesh-stack/ROADMAP.md` — Full plan, link budgets, power analysis, research checklist
- `mesh-stack/research/routing/cluster-aware-bridge.md` — Clustering algorithm analysis + MeshCore hooks
- `mesh-stack/research/routing/meshcore-study.md` — MeshCore architecture + LR2021 port plan
- `mesh-stack/meshcore-lr2021/` — PlatformIO build for LR2021 variant (bench test + upstream PR)
- `docs/adr/009-antenna-strategy-v1-v2.md` — V1 omni + V2 directional decision
- `docs/adr/010-adaptive-tx-power.md` — Adaptive TX per TDMA slot
- `docs/power-budget.md` — Tracker + mesh relay power scenarios

## Key Repos

### Our Implementations
- sx1280-serial (TDMA + fragmentation + crypto): `nostr://npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/relay.ngit.dev/sx1280-serial`
- ESP32 TollGate + Nostr: `https://gitworkshop.dev/npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/git.orangesync.tech/esp32-tollgate`
- sx1280-correlation-test: `nostr://npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/relay.ngit.dev/sx1280-correlation-test`

### External Dependencies
- FIPS: `https://github.com/jmcorgan/fips` — mesh networking, Nostr identity, Noise encryption
- microfips: `https://github.com/Amperstrand/microfips` — FIPS leaf node (STM32 + ESP32)
- MeshCore: `https://github.com/meshcore-dev/MeshCore` — LoRa mesh, repeater firmware
- TollGate protocol: `https://github.com/OpenTollGate/tollgate` — payment specs
- TollGate OpenWRT: `https://github.com/OpenTollGate/tollgate-module-basic-go` — reference implementation
- Wirehair: `https://github.com/catid/wirehair` — fountain codes
- RadioLib: `https://github.com/jgromes/RadioLib` — LR2021 driver (v7.6.0)

## Phased Plan
1. **Phase 1**: Balloon tracker (single balloon, 28-byte telemetry, GPS) — **DONE**
2. **Phase 2**: FIPS over LoRa + MeshCore repeater (bench + first dual-band flight) — Research
3. **Phase 3**: Nostr store-and-forward + TollGate ground station — Not started
4. **Phase 4**: Multi-balloon mesh + full internet transport — Not started
5. **Phase 5**: Multi-balloon reliability research — Not started (requires 3 Phase 2 flights)

## Current Status
- Phase 1 tracker firmware v0.2 complete (17/17 tests pass)
- ADR-012: FIPS + MeshCore + TollGate + Nostr strategy decided
- ADR-013: Cluster-Aware Stratorelay decision proposed
- INTEGRATION-ARCHITECTURE.md: detailed technical architecture documented
- Link budget, throughput, power budget analyses complete
- ADR-009, ADR-010, ADR-011, ADR-012, ADR-013 written
- MeshCore LR2021 PlatformIO port: patches ready, needs hardware testing
- Cluster-aware bridge: research complete, algorithm designed, implementation pending
- **Not started**: FIPS Transport for LoRa, MeshCore LR2021 bench test, Wirehair integration, Nostr-over-FIPS

## StratoRelay (Cluster-Aware MeshCore Bridge)

The balloon runs a smart MeshCore relay (`StratoRelayMesh`) that identifies ground node clusters via union-find on observed flood paths, elects one cluster head per cluster, and only bridges messages between clusters. Ground nodes remain completely stock.

**See**: `docs/adr/013-cluster-aware-stratorelay.md`, `mesh-stack/research/routing/cluster-aware-bridge.md`

**Key files** (to be created):
- `tracker/firmware/components/meshcore/` — extracted MeshCore core (ESP-IDF)
- `tracker/firmware/components/stratorelay/` — StratoRelayMesh + NodeTable + UnionFind + StaticBloomFilter

**Build system**: Flight firmware = ESP-IDF (single MCU). Bench testing = PlatformIO (`mesh-stack/meshcore-lr2021/`).

**Memory budget**: ~6.5 KB static DRAM for clustering layer (256 nodes, 32 clusters). ESP32-C3 has 258 KB free after tracker.

**MeshCore version**: Pinned to `companion-v1.15.0` release tag for reproducibility.

**Upstream PRs**: (1) LR2021 variant, (2) StratoRelayMesh example — two separate tightly-scoped PRs.

## Firmware Language
Decision deferred. Options documented in INTEGRATION-ARCHITECTURE.md:
- C++ / ESP-IDF: consistent with tracker, RadioLib native
- Rust / esp-rs: consistent with microfips, FIPS, sx1280-serial
- Hybrid: tracker in C++, mesh in Rust

## Night-Off Default
Balloons sleep at night (~15 uA deep sleep). Ground stations estimate position from wind data.
Multiple balloons at different longitudes provide 24h coverage.
Configurable night-active mode with larger caps for special missions.
