# Balloon Project — Consultant Review Package
## "Pico Balloon + Tollgate + FIPS Mesh = Decentralized Starlink"

**Generated:** 2026-08-05
**Prepared by:** balloon-hermes orchestrator (9 sub-manager tracks investigated)
**Purpose:** Comprehensive project status for consultant review. What worked, what didn't, what's next, lessons learned, lowest-hanging fruit.

---

## EXECUTIVE SUMMARY

The balloon project aims to build solar-powered pico balloon nodes using ESP32-C3 + LR2021 LoRa radios that form a mesh network providing internet transport, Cashu payment gating, Nostr relay, and Blossom media storage — a decentralized, balloon-borne alternative to StarLink.

**Current state: strong software foundation, bench-proven RF link, but hardware-blocked for flight.**

The mesh transport layer (FIPS over LR2021) is the single blocking dependency for 3 of 4 software tracks. One hardware fix (RP2040 MCU swap) gates all outdoor testing. Payload weight targets are achievable with thin-film solar cells.

**Timeline estimates:**
- Shakedown flight (DecoGlee + party He): 1-2 weeks after MCU swap
- Long-duration flight (Yokohama + He 4.6): 3-4 weeks after MCU swap + procurement

---

## 1. WHAT WORKS (Proven, Tested, Committed)

### RF & Radio Link
- **FLRC baseline link PROVEN**: 1377 kbps end-to-end, 1000/1000 packets, 0% loss, 2440 MHz, +12 dBm
- **TX throughput ceiling**: 1749 kbps (TX-only, 500/500, 0 timeouts)
- **FLRC sweep**: 1485/806/420/240 kbps across 4 bitrate configs
- **RP2040 LR2021 baseline v1.0.0**: SPI 10.40 MHz, documented (commit 9054967)
- **Raw 2-byte opcode SPI protocol** — the ONLY working LR2021 driver. RadioLib v7.6.0 is BROKEN (ADR-020)
- **V4 sweep firmware**: Ready, sweeps all 14 LR2021 modes, GPS embedded, GPS fix gate (ADR-018)
- **DMA-chaining zero-copy FLRC TX**: commit 7b08833 (P4.1, RP2040)

### FIPS Mesh (Encrypted Transport)
- **Noise IK handshake**: 13/13 host tests pass, 4/4 pipeline integration
- **Encrypted multi-frame transport**: 1KB payloads split→encrypt→LR2021→decrypt→reassemble, 5/5 tests
- **LR2021 transport extraction**: 1,865 lines Rust→C++ (commit 88b9f8b), 36 host tests pass
- **FIPS × Tollgate bridge**: radio_adapter.cpp committed (Workstream 1 DONE, commit 931b6c8)
- **MeshCore on ESP-IDF**: 330 KB binary, 70+ Berlin nodes discovered
- ADR-025 (hardware mutex), ADR-020 (raw SPI only), ADR-016 (C++ ESP-IDF for V1)

### PCB / Circuit Design
- **V1 board: ORDERABLE** — 0 electrical shorts, 0 clearance issues, 0 crossings
  - 524 DRC violations but ALL solder-mask bridge (cosmetic, JLCPCB ignores)
  - Gerbers + BOM + CPL exist at tracker/hardware/gerbers_v1/
- **Router class**: 33/33 tests pass, integrated into gen_pcb.py
- **F33 board**: shorts reduced 86→15 (still needs fix — U1 pad pitch issue)

### Tollgate / Cashu (Payment Layer)
- **Works fully on ESP32-S3**: Captive portal, Cashu wallet, B2B settlement tested (32 ehash, 43s)
- **800+ unit tests** pass on S3
- **ESP32-C3 extraction**: 309 KB binary, 49.5 KB DRAM (84% headroom). BUILDS CLEAN.
- **Cashu protocol encode/decode** verified on C3
- **nucula C++ wallet** compiles on C3 (12.4 KB flash)
- **23 modules stripped** (display, mining, marketplace, CVM) → 34→11 source files

### Nostr Relay
- **Ground-station bridge**: pytest suite, real Schnorr signing via coincurve, kind-30023 events published to relay
- **nostr_store component**: Bloom-filter dedup (7/7 tests), FIFO ring buffer, event find by ID
- **StratoRelay cluster layer**: 11/11 tests pass (bloom, union-find, cluster-head election)
- **Detailed extraction plan**: 261-line status document with C3 resource budget

### Blossom Server
- **Runs on real ESP32-C3 hardware** (WiFi/HTTP mode)
- **1,353 lines of C**: GET/HEAD/OPTIONS/PUT handlers, LittleFS storage, BUD-11 auth, secp256k1 verification
- **4 commits of incremental build** (Phase 2A through 2D)

### PoW / Mining (E-Hash Relay)
- **Design complete** (ADR-025, D1-D10 locked)
- **ehash-bridge (Python, ground)**: Stratum V1 server, 35 codec round-trip tests
- **ehash-relay (C, balloon)**: 8/8 unit tests pass
- **Balloon NEVER hashes** (D1) — pure transport relay. Zero SHA256 cost.

### Mesh Infrastructure
- **Erasure coding**: PRBS23-XOR, 5/5 tests
- **Fragmentation layer**: 3/3 tests
- **TDMA scheduler**: 12/12 host tests
- **Tracker firmware v0.2**: 17/17 unit tests, deep sleep, configurable SF/power/freq

### Physical Preparation
- **Pre-stretching protocol**: Complete (260 lines, validated from 80+ community flights)
- **Leak test methodology**: BMP280/MS5611 + ESP32-C3 rig, temp compensation formula
- **Pressure test rig firmware**: Built (dual BMP280/MS5611 auto-detect)
- **Payload weight estimates**: Calculated — both targets achievable with thin-film solar
- **First flight checklist**: Complete (pre-flight through post-launch)

---

## 2. WHAT DOESN'T WORK (Blockers, Failures, Gaps)

### Critical Hardware Blockers
| # | Blocker | Impact | Resolution |
|---|---------|--------|------------|
| 1 | **2W LR2021+PA board: dead USB PHY** | Only 1 of 2 radio boards operational; can't do TX+RX simultaneously | **MCU swap** (RP2040). #1 GATE. |
| 2 | **No helium** | Can't inflate any balloon | Procure: party He (shakedown), He 4.6 (long-duration) |
| 3 | **BMP280 not wired** | Can't run electronic leak tests | Wire to GPIO8 SDA, GPIO9 SCL |
| 4 | **Standard solar cells too heavy** (2g each) | Weight targets unreachable | Source thin-film (~0.4g/cell) |

### Software Blockers (Cross-Cutting)
| # | Blocker | Affects | Resolution |
|---|---------|---------|------------|
| 1 | **FIPS mesh transport not wired into main build** | Nostr, Blossom, PoW | Consume radio_adapter (already committed for Tollgate) |
| 2 | **`nostr_event_deserialize()` missing** | Nostr, Blossom | Implement (declared in header, never defined) |
| 3 | **`mesh_adapter` has no CMakeLists.txt** | All mesh tracks | Create + wire into build |
| 4 | **secp256k1 flash footprint unmeasured on C3** | Nostr validation, Blossom auth | Measure — gates full Schnorr vs ground-deferred decision |
| 5 | **FIPS test crate broken** (20 errors) | FIPS verification | Needs balloon-hermes SPI protocol in test crate |
| 6 | **FIPS never tested over real radio** | All mesh | Host mock only — needs 2 boards + Phase 5 |
| 7 | **Payment not proven end-to-end on balloon** | Tollgate | `nucula_wallet.spend_proofs()` stubbed; needs FIPS transport |

### What Was Tried and FAILED
| Approach | Why It Failed |
|----------|--------------|
| RadioLib v7.6.0 for LR2021 | Protocol mismatch — 24-bit addressing vs 2-byte opcodes. Always returns error -707 or hangs. |
| PIO/DMA SPI on RP2040 | All variants failed. Arduino per-byte `SPI.transfer()` is the ONLY working method. |
| Glue/epoxy for balloon sealing | ALL glues, UV epoxy, E6000, model glue, TPU clamps FAILED in community testing. Heat seal + Kapton tape ONLY. |
| Party helium for long-duration | 0% circumnavigation rate (0/9 flights). Must use He 4.6 (99.999%). |
| fix_unconnected.py for PCB | Made routing worse — reverted. |
| ADR-017 (RadioLib approach) | SUPERSEDED by ADR-020 (raw SPI). |
| F33 pad pitch 1.5mm | 14 adjacent shorts. Needs 2.54mm pitch redesign. |

---

## 3. WHAT'S NEXT (Prioritized)

### Priority 0: Unblock the Critical Path (FELIX — THIS WEEK)
1. **MCU swap on 2W board** — replaces dead RP2040. Everything depends on this.
2. **Bench re-verification** — flash v4 TX+RX, verify at 1m baseline (both boards for first time)
3. **Wire dipole antennas** — 30 AWG wire, 868 MHz, 8.6 cm legs

### Priority 1: First Real Data (1-2 WEEKS)
4. **Walk test** — range vs throughput at 10m/25m/50m/100m
5. **Wire BMP280 to ESP32-C3** — unlock leak testing
6. **Procure party helium** — for shakedown flights

### Priority 2: Software Integration (PARALLEL, NO HARDWARE NEEDED)
7. **Wire FIPS into main build** — create mesh_adapter/CMakeLists.txt, enable CONFIG_ENABLE_MESH
8. **Implement `nostr_event_deserialize()`** — shared blocker for Nostr + Blossom
9. **Measure secp256k1 on C3** — flash cost measurement, gates validation strategy
10. **Wire ehash_radio_stub → LR2021** — unblocks PoW relay
11. **Expand Blossom flash partition** 1MB→2MB for mesh components

### Priority 3: Flight Preparation (2-3 WEEKS)
12. **DecoGlee batch leak test** — 30 balloons available
13. **Yokohama pre-stretch** — 24-48h process
14. **Weight verification** — assemble payload, verify <9g / <14g

### Priority 4: Flight Hardware (3-4 WEEKS)
15. **JLCPCB V1 order** — gerbers ready, BOM/CPL ready
16. **Source thin-film solar cells** — critical weight lever
17. **F33 board fix** — pad pitch redesign, or skip for V1

---

## 4. KEY LESSONS LEARNED

### RF/Radio
1. **Raw SPI with 2-byte opcodes is the ONLY working LR2021 driver.** RadioLib is a dead end. Documented in ADR-020.
2. **Air time (~803µs) dominates, not SPI speed.** Optimizing SPI is diminishing returns.
3. **FLRC 2600 kbps is the ceiling.** Real-world throughput: 1377-1749 kbps.
4. **SET_RX_PATH (0x0201) and CALIB_FRONT_END (0x0123) are MANDATORY** before RX mode.
5. **IRQ status is 32-bit** (not 16-bit like SX1280). RX_DONE=bit18, TX_DONE=bit19.

### Architecture / Software
6. **The balloon is NOT a WebSocket relay.** All communication over LoRa datagram. 8 of 13 wisp-esp32 modules are irrelevant.
7. **The balloon NEVER hashes (D1).** Pure transport relay. Zero SHA256 cost by design.
8. **Extract-only policy (ADR-024)** — source repos are READ-ONLY. Prevents fork divergence.
9. **C++ on C3 is viable** — nucula + libstdc++ = 22 KB combined. No need for C rewrite.
10. **"90% built, 0% wired"** — all 7 Blossom protocol components exist and pass tests individually. Gap is integration, not development.
11. **nostr_store CANNOT fit on C3 as-is** — 606 KB RAM (235% of heap). Planned extract ~20-30 KB fits.

### PCB/Hardware
12. **V1 board is orderable** — 0 electrical shorts. JLCPCB ignores solder-mask bridge warnings.
13. **F33 pad pitch issue** — 1.5mm pitch with 1.7mm pads = shorts. Needs 2.54mm redesign.
14. **Standard solar cells (2g) are too heavy.** Thin-film (0.4g) is mandatory for weight targets.

### Balloon Physics (from 80+ community flights)
15. **Gas purity is THE #1 success factor.** Party He: 0% circumnavigation. He 4.6: 67%.
16. **Control circumference, NOT pressure.** Ruthroff confused mbar with PSI → overpressured → failures.
17. **Heat seal + Kapton ONLY.** Every adhesive failed at altitude.
18. **5-7g free lift is optimal.** <5g = obstacles risk. >8g = burst risk.
19. **Batteries don't work at altitude.** Cold kills them. Solar + supercapacitor is proven.
20. **Night loss is most common failure.** Usually balloon-related (gas contraction), not electronics.

---

## 5. PAYLOAD WEIGHT ANALYSIS

| Config | Solar | Est. Weight | Target | Verdict |
|--------|-------|-------------|--------|---------|
| A: Minimal tracker (battery-only) | None | **~8.0g** | <9g | ✅ PASS (1.0g margin) |
| C: Mesh V1 (thin-film solar) | 4 thin-film | **~11.6g** | <14g | ✅ PASS (2.4g margin) |
| D: Mesh V1 (standard cells) | 2 standard | ~14.0g | <14g | ⚠️ AT LIMIT |

**Critical insight: thin-film solar cells (0.4g vs 2g) are the single biggest weight lever.** Without them, no configuration passes.

Weight breakdown (Mesh V1, 11.6g):
```
ESP32-C3-Mini-1   ████████████████████  2.5g (21.6%)
V1 PCB             ██████████████████    2.5g (21.6%)
Supercap 1F        ██████████████        1.8g (15.5%)
Solar (4 thin-film)█████████████         1.6g (13.8%)
LR2021 radio       ██████████            1.2g (10.3%)
RP2040-Zero        ██████████            1.2g (10.3%)
GPS+baro+antenna   ████                  0.63g (5.4%)
SMD + solder       █                     0.19g (1.6%)
```

---

## 6. CRITICAL PATH DIAGRAM

```
                    ┌─────────────────────┐
                    │  MCU SWAP (2W board) │ ◄── #1 BLOCKER
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Bench Re-Verification│  (v4 TX+RX, 1m)
                    │ Wire Dipole Antennas │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                 ▼
    ┌─────────────┐  ┌──────────────┐  ┌────────────────┐
    │  Walk Test  │  │ Leak Testing │  │ Software Mesh  │
    │ (range data)│  │ (BMP280+He)  │  │ Integration    │
    └──────┬──────┘  └──────┬───────┘  └───────┬────────┘
           │                │                  │
           ▼                ▼                  │
    ┌─────────────┐  ┌──────────────┐          │
    │ Tethered    │  │ SHAKEDOWN    │◄─────────┘
    │ Test        │  │ FLIGHT       │
    └──────┬──────┘  │ (DecoGlee)   │
           │         └──────────────┘
           ▼
    ┌─────────────────────────────────────────┐
    │ FREE FLIGHT (Yokohama 32" + He 4.6)     │
    │ Requires: He 4.6, pre-stretch, flight   │
    │ PCB, thin-film solar, mesh firmware     │
    └─────────────────────────────────────────┘
```

**Parallel track (no hardware needed):** Software mesh integration (Priority 2) can proceed NOW. Wiring FIPS into the main build, implementing nostr_event_deserialize(), and measuring secp256k1 on C3 are all host-side work.

---

## 7. ESP32-C3 RESOURCE BUDGET

| Component | Flash | DRAM | Status |
|-----------|-------|------|--------|
| Tracker baseline | ~250 KB | ~6.5 KB | ✅ |
| Tollgate (payment core) | 309 KB | 49.5 KB | ✅ Measured |
| Nostr store (planned) | ~50-70 KB | ~20-30 KB | Designed |
| Blossom (WiFi mode) | ~1 MB | ~Large | ⚠️ Tight |
| Blossom (mesh datagram) | TBD | TBD | Not built |
| PoW e-hash relay | ~5-10 KB | ~2-4 KB | ✅ |
| secp256k1 (shared) | ~40-60 KB | ~2-4 KB | Unmeasured |
| **TOTAL** | **~1.6-1.8 MB** | **~80-95 KB** | **✅ Fits 4MB/312KB** |

---

## 8. TRACK STATUS MATRIX

| Track | Phase | Key Deliverable | Proven on C3? |
|-------|-------|-----------------|---------------|
| Radio Link (hermes) | EXECUTION | 1377 kbps, 0% loss | ✅ Bench |
| FIPS Mesh | ASSESSMENT-COMPLETE | Phases 1,3 done (host). 2,4,5,6 blocked on DQ05. | ❌ Host only |
| PCB Design | EXECUTION | V1 orderable, F33 15 shorts | N/A |
| Tollgate | ASSESSMENT-COMPLETE | 309 KB binary, 84% headroom | ✅ Builds |
| Nostr | ASSESSMENT-PENDING | Plan complete (261 lines), impl NOT started | ❌ Doesn't fit yet |
| Blossom | ASSESSMENT-COMPLETE | 1353 lines, runs on C3 (WiFi) | ⚠️ WiFi only |
| PoW | ASSESSMENT-PENDING | 8+35 tests, radio is stub | ✅ Design fits |
| Range Tests | ASSESSMENT-PENDING | V5 sweep firmware ready | ✅ Firmware |
| Speed Tests | ASSESSMENT-PENDING | Goodput scripts, bench targets | ✅ |
| Pre-Stretching | EXECUTION | Protocol + rig + weight estimates | N/A |

---

## 9. CONSULTANT QUESTIONS

The following strategic questions need the consultant's guidance:

1. **Architecture:** Should we build the mesh stack on the TRACKER firmware (current plan) or on the BLOSSOM-SERVER firmware as the base? Tracker has more mesh scaffolding; Blossom has more protocol handlers.

2. **Schnorr validation tradeoff:** Should the balloon do full Schnorr signature validation (requires secp256k1, ~50 KB flash) or defer to ground station (lighter, but accepts unsigned events)? This is the key C3 resource decision.

3. **FIPS vs MeshCore priority:** FIPS has stronger crypto (Noise IK) but is blocked on DQ05 build server. MeshCore is already running on ESP-IDF (330 KB, 70+ Berlin nodes discovered). Should we ship V1 with MeshCore and add FIPS as V2 upgrade?

4. **V1 scope:** Given the weight targets and resource budget, what's the minimum viable payload for a first circumnavigation attempt? Tracker-only (<9g) vs full mesh (<14g)?

5. **Monetization model:** The Tollgate payment layer and PoW e-hash relay are both designed but not proven over radio. Which should be prioritized for the "balloon StarLink" value proposition — pay-per-relay (Tollgate) or mine-and-relay (e-hash)?

6. **Single vs dual MCU:** Current design uses ESP32-C3 + RP2040 (dual MCU, ~11.6g). Could a single ESP32-C3 handle both radio SPI and application logic, saving the RP2040 weight (1.2g)?

7. **Deployment strategy:** Should we aim for many short-duration DecoGlee flights (validate electronics) or one long-duration Yokohama flight (prove the concept) first?

---

## 10. LOWEST HANGING FRUIT

### Can be done RIGHT NOW (no hardware, no procurement):
1. Wire FIPS into main build (create mesh_adapter/CMakeLists.txt)
2. Implement `nostr_event_deserialize()` (1 function, blocks 2 tracks)
3. Measure secp256k1 flash on C3 (flash a test binary, read partition map)
4. Write payment protocol unit tests for Tollgate C3 extraction
5. Wire ehash_radio_stub → LR2021 transport
6. Expand Blossom partition table (1MB→2MB)
7. Update stale status files for 4 tracks missing assessments

### Needs Felix's hands (1-2 hours):
8. MCU swap on 2W board (#1 blocker)
9. Wire BMP280 to ESP32-C3 (GPIO8/GPIO9)
10. Solder wire dipole antennas (30 AWG, 868 MHz)

### Needs procurement (days):
11. Party helium (for shakedown)
12. Thin-film solar cells (weight-critical)
13. JLCPCB V1 board order (gerbers ready)

---

*This document was compiled from parallel investigations of all 9 sub-manager tracks, reading git logs, assessment files, status files, ADRs, and hardware inventory across 10+ worktrees and source repositories.*
