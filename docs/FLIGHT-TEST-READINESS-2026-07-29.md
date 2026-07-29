# Balloon Project — Flight Test Readiness Assessment
**Date:** 2026-07-29
**Author:** balloon-hermes (coordinator)
**Purpose:** Consolidated status for planning session + MCU replacement day

---

## 1. HARDWARE SITUATION

| Board | Status | Current Firmware | Notes |
|-------|--------|-----------------|-------|
| 2W LR2021 + PA board | **DEAF** — dead USB PHY on RP2040 | N/A | Felix replacing MCU today |
| F242D (second RP2040) | Working | RX firmware (flrc_range_rx_auto) | Currently the only reachable board |

**After MCU swap:** Both boards usable simultaneously for first time since USB PHY died.

## 2. FIRMWARE READINESS

### Proven on Hardware (prior sessions)
- **1377 kbps baseline:** End-to-end TX+RX, 1000/1000 packets, 0% loss. FLRC 2600 kbps, 2440 MHz.
- **1749 kbps TX-only:** nullptr fix verified. 500/500 packets, 0 timeouts. TX throughput ceiling confirmed.
- **Single-batch SPI port:** Committed (596e837), compiles green. NOT yet validated end-to-end (RX side).

### Recommended Firmware Pair for Combined Range+Throughput+GPS Flight

**TX:** `rp2040-sweep-tx-v4` (`multi_radio_sweep_gps_v4.cpp`, 1408 lines)
- Sweeps all 14 LR2021 modes (HF/LF × FLRC/LoRa × 4 bitrates)
- GPS position (lat/lon/sats/fix/UTC) embedded in every packet
- GPS FIX GATE (ADR-018) — won't transmit without satellite lock
- Autonomous — runs on battery, no laptop needed
- Firmware git hash embedded in packets for compatibility tracking

**RX:** `rp2040-sweep-rx-v4` (`multi_radio_sweep_rx_v4.cpp`, 1221 lines)
- Extracts TX GPS position from packets
- Reports RSSI/PER/BER per mode, per phase
- Closed-loop phase sync from TX packet UTC
- Needs laptop for SET_TIME + serial data capture (ground station)
- Output: `PHASE_RESULT` CSV + per-packet `PKT` lines

**Both are the DEFAULT build environments** in platformio.ini.

### Known Firmware Gaps (pre-flight fixes needed)
1. TX FIFO write is per-byte SPI (not single-batch) — functional but ~20% below max throughput
2. V4 interleave mode has 56 phases — full cycle ~3+ minutes at altitude (SF12 phases auto-skipped for large packets)
3. TX power set to 12.5 dBm in firmware — verify this matches the 2W amplifier board after MCU swap
4. No bench re-verification done yet after nullptr fix + single-batch SPI port (both compile, never flashed together)

### DEPRECATED / BROKEN Firmware (do NOT use)
- `flrc_range_tx_gps.cpp` / `flrc_range_rx_gps.cpp` — unresolved merge conflicts, will not compile
- `flrc_throughput_tx.cpp` / `flrc_throughput_rx.cpp` — deprecated, use wrong SX1280 opcodes (0x0104 vs LR2021's 0x024B)
- All `rp2040-flrc-max/` RadioLib-based firmware — never worked on our hardware (protocol mismatch, ADR-020)

## 3. PHYSICAL FLIGHT READINESS

### Test Options

| Option | Description | Ready When | Blockers |
|--------|------------|-----------|----------|
| **Tethered** | TX on balloon on a line, 10-50m altitude | Hours after MCU swap | Battery, wire antenna |
| **Walk test** | TX carried by person, varying distance | Hours after MCU swap | Wire antenna, powerbank fix |
| **Free flight** | Pico balloon circumnavigation | 2-4 weeks | See procurement list below |

### Procurement Blockers (for free flight)
| Item | Status | Source | ETA |
|------|--------|--------|-----|
| Yokohama 36" balloons | NOT OWNED | Japan (€10.60 ea) | Weeks |
| Industrial He 4.6 | NOT OWNED | Air Liquide ALbee Fly (~€40) | Days |
| GPS module (MAX-M10S) | NOT OWNED | Amazon/electronics | Days |
| Supercapacitors (1F 5.5V) | NOT OWNED | Amazon | Days |
| Heat sealer | NOT OWNED | Amazon (~€15) | Days |
| Kapton tape | NOT OWNED | Amazon (~€5) | Days |

### What We DO Have
- 30x DecoGlee 18" foil balloons (test-only, 4.8g lift each, 0% circumnavigation with party He)
- 4x NiceRF LoRa2021 modules (+13 dBm)
- 3x EBYTE E28-2G4M27S (SX1281, +27 dBm PA built-in)
- 20x ESP32-C3 Mini V1
- 100x solar cells (52x19mm)
- Pressure sensor + pump (for balloon testing)

## 4. TRACK STATUS SUMMARY

| Track | Phase | Last Known Status | Blockers |
|-------|-------|-------------------|----------|
| balloon-hermes (RF link) | Execution | Baseline 1377 kbps proven, v4 firmware ready | TX board MCU replacement |
| balloon-range-tests | Assessment pending | Firmware ready, walk test plan approved | TX board, wire antennas |
| balloon-speed-tests | Assessment pending | Single-batch SPI breakthrough (1733 kbps TX-only) | End-to-end RX validation |
| balloon-fips | Assessment complete | LR2021 transport modules written (1134 lines), test crate broken (20 errors) | Needs balloon-hermes SPI protocol |
| balloon-tollgate | Assessment complete | 86/86 unit tests pass on S3, C3 port NOT verified | Display hard-blocks C3 |
| balloon-pow | Assessment pending | Phase 1 done (crypto mining on S3), Phase 2 blocked | D-001: S3 board allocation |
| balloon-nostr | Assessment pending | Docs committed, C3 build not verified | None |
| balloon-blossom | Assessment complete | 7 questions surfaced, repo created | D-003 resolved |
| balloon-pre-stretching | NOT STARTED | Bootstrap plan written, worktree never created | Needs bootstrap |
| balloon-circuit-design | Assessment complete | Decision: maintain both DIY + SKiDL designs | 5 KiCad symbols missing |

## 5. OPEN DECISIONS

### D-001: ESP32-S3 Board Allocation — NEEDS CLARIFICATION
**The question is NOT about flight boards.** It's about which SOFTWARE TRACK gets the 3 physical ESP32-S3 dev boards (Board A/B/C) for their testing.

- balloon-tollgate needs them: captive portal + Cashu payment testing currently runs on S3
- balloon-pow needs them: SHA256 mining / stratum extraction testing needs S3

Both tracks need the same 3 boards. Options: tollgate first, pow first, or time-share.

**Felix's input needed:** Can we standardize on C3 for everything and retire the S3 boards? Or does the mining track genuinely need S3?

### D-002: microfips Git Remote — RESOLVING
Felix said: create one. Action in progress (gh repo create).

### D-003: Blossom Repo — RESOLVED
GitHub repo c03rad0r/balloon-blossom was created. No further action needed from Felix.

## 6. CRITICAL PATH

```
MCU swap today
  → bench re-verification (both boards, 1m baseline)
    → walk test (range vs throughput curve)
      → tethered balloon test (altitude vs range)
        → free flight (once procurement done)
```

**The single most important next step is the MCU swap.** Everything downstream depends on having two working boards.

## 7. IMMEDIATE NEXT ACTIONS

1. Felix: Replace RP2040 on 2W board
2. range-tests: Flash v4 TX+RX, bench verify at 1m
3. range-tests: Wire dipole antennas (30 AWG wire)
4. Felix: Decide on D-001 (S3 board allocation)
5. Felix: Order procurement items for free flight (Yokohama, He 4.6, GPS, supercaps)
