# SX1280 Related Repositories — Reference & Learnings

Four repositories from earlier experimentation (April 2026) with Semtech SX1280 2.4 GHz radio modules (Ebyte E28-2G4T27SX). These use different hardware than the balloon project (ESP32-C3 + LR2021) but contain valuable methodology, protocol designs, and field test data.

## Repository Overview

| Repo | Clone URL | Language | Maturity |
|------|-----------|----------|----------|
| sx1280-testing | `nostr://npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/relay.ngit.dev/sx1280-testing` | Python | Early experiment |
| sx1280-serial | `nostr://npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/relay.ngit.dev/sx1280-serial` | Rust | Field-tested |
| sx1280-ethernet-adapter | `nostr://npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/relay.ngit.dev/sx1280-ethernet-adapter` | Rust (ESP-IDF) | Pre-alpha scaffold |
| sx1280-correlation-test | `nostr://npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/relay.ngit.dev/sx1280-correlation-test` | Python | Field-tested |

## Common Hardware

All repos use the same hardware platform:
- **Radio**: Ebyte E28-2G4T27SX (2.4 GHz LoRa, 27 dBm, based on Semtech SX1280/SX1281)
- **Interface**: USB dev board (E28-2G4TBH-01) with CH341 USB-serial adapter
- **Host**: Linux PC (no MCU — radios used as transparent UART-to-radio bridges)
- **Connection**: `/dev/ttyUSB0`, `/dev/ttyUSB1` (9600 baud, 8N1)
- **No custom PCBs** — all use commercial USB dev boards

## Per-Repo Summary

### sx1280-testing

Basic bring-up and first link test. Proves two E28 radios can exchange data over USB serial.

**What it does:**
- `sender.py` / `receiver.py` — simple line-based serial packet exchange
- FIPS encrypted link integration (encrypted IPv6 over SX1280 serial via FIPS mesh stack)
- Throughput benchmarking with automated pytest suite

**Key result:** ~1 kbps throughput with FIPS encryption at 512-byte payloads, 2.4-3.9 second RTTs. High packet loss at larger payloads.

**Files of interest:**
- `THROUGHPUT_RESULTS.md` — measured throughput data
- `E28_plan_and_questions.md` — bring-up checklist and open research questions

### sx1280-serial

The most substantial repo. A Rust daemon that provides a complete serial link layer for SX1280 radios, extracted from the FIPS mesh networking project.

**What it does:**
- `sx1280-seriald` daemon process — bridges FIPS mesh nodes to radio hardware
- SLIP-encoded framing with CRC-32, magic bytes `0xF1 0x50`
- Fragmentation (128-byte fragments) and reassembly with timeout
- P2P mode (two nodes, simple) and shared mode (TDMA, multi-node)
- TDMA coordinator election (lowest node ID wins)
- Per-peer warmup: Cold → Probing → Warm state machine
- Datagram ACK/ARQ with retransmission (2 retries, 2.5s timeout)
- Crypto identity: secp256k1 Schnorr-signed radio binding certificates
- Unix domain socket IPC (control = JSON stream, data = binary datagrams)

**Feature branch:** `feature/three-node-ota-antenna-validation`
- Extends to 3 physical radio nodes with 5-slot TDMA
- Hardware debug ladder: L0 (raw serial) → L01 (p2p runtime) → L012 (p2p daemon) → L0123 (3-node shared TDMA)
- Multi-pair hardware test automation (test all pair combinations: A-B, A-C, B-C)
- Daemon observability tools (`daemon_control.py`, `wait_shared_daemon_ready.py`)
- Fix for cross-connection control traffic race condition during 3-node startup
- Soak testing: runs N iterations with pass/fail CSV logging

**Files of interest:**
- `src/link/frag.rs` — SLIP + CRC-32 + fragmentation protocol (564 lines)
- `src/link/mac.rs` — 24-byte MAC header with frame types (326 lines)
- `src/link/tdma.rs` — TDMA scheduling with role-based and superframe modes (199 lines)
- `src/link/coord.rs` — Coordinator election (158 lines)
- `src/serial/shared.rs` — Full shared-mode runtime with peer warmup (1739 lines)
- `tests/hardware_shared_daemon.rs` — Hardware test ladder (185 lines)
- `Makefile` — Comprehensive test/build targets (359 lines on feature branch)

### sx1280-ethernet-adapter

Rust ESP-IDF firmware for ESP32-S3 + SX1280, intended as a Wi-Fi-managed radio bridge. Despite the name, there is no Ethernet — it uses Wi-Fi AP mode.

**What it does:**
- Wi-Fi Access Point (SSID: `SX1280-Adapter`) with HTTP `/status` endpoint
- Link engine: fragmentation, sliding window ACK, reassembly
- FLRC modulation chosen for throughput (not LoRa)
- IPv6 addressing (`fd00::adapter`) — intended to carry IPv6 frames over radio

**Status: Pre-alpha scaffold. Critical gaps:**
- No real SX1280 SPI driver — only `MockSx1280` for simulation
- No IRQ-driven RX/TX
- No IPv6 frame wiring
- No pin mappings documented
- All testing is against mocks, never ran on real hardware

**Files of interest:**
- `src/link/engine.rs` — Fragmentation + sliding window + reassembly (162 lines)
- `src/radio/sx1280.rs` — Radio abstraction trait + mock (92 lines)
- `src/net/ap.rs` — Wi-Fi AP + HTTP status server (76 lines)
- `docs/design.md` — Architecture and throughput strategy
- `docs/bench.md` — Benchmark plan (goodput, retry, drop, latency at various payloads)

**Architectural relevance to balloon project:** This is the closest design to what a balloon ground station could look like — ESP32 + radio + Wi-Fi AP + HTTP status. The link engine and FLRC mode choice are directly applicable.

### sx1280-correlation-test

Mature field-tested range testing tool with real-world data from lab, boat, and mountain (Pico Ruivo, Madeira).

**What it does:**
- Deterministic bidirectional time-slotted range testing
- Two nodes alternate TX/RX in 20-second cycles (2s guard + 8s TX + 2s guard + 8s TX)
- Pseudo-random payloads: SHA-256 of `(salt|profile|cycle|slot_owner|sender|seq)`, truncated to 8 bytes
- All TX/RX events logged to CSV with Unix timestamps
- Post-run correlation: match TX packets to RX packets by `(sender, profile, cycle, slot_owner, seq)`
- Delivery ratio plotting over time (35 PNG plots)
- E28 config tool: 6-byte UART command protocol for module configuration

**Key results:**
- 35,861 CSV records over 3 test sessions (Apr 15-17, 2026)
- A→B delivery: 37% (4,124 of 11,021 packets)
- B→A delivery: 29% (4,716 of 15,998 packets)
- Air data rate: 1 kbps (ADR1K profile, most robust)
- Radio config automation never worked (26 config logs all "unverified") — manual jumper config used instead

**Files of interest:**
- `range_test_node.py` — Main bidirectional test node (825 lines)
- `scripts/plot_range_correlation.py` — TX/RX correlation + delivery ratio plots (558 lines)
- `RANGE_TEST_DESIGN.md` — Comprehensive test design document (719 lines)
- `MVP_PLAN.md` — Phased implementation plan (273 lines)
- `e28_config.py` — E28 UART config protocol helpers (368 lines)
- `reports/` — 35 correlation plots + throughput report

## Learnings Applicable to Balloon Project

### 1. Range Testing Methodology (from sx1280-correlation-test)

**Adopt directly:** The deterministic payload + CSV logging + correlation analysis pipeline is exactly how we should validate our 868 MHz LoRa link.

- Generate SHA-256-based deterministic payloads with embedded sequence numbers
- Log every TX and RX event to separate CSV files with timestamps
- Post-test: correlate by matching `(sender, cycle, seq)` tuples
- Compute per-cycle and overall delivery ratio
- Plot delivery ratio over time to see link stability patterns

**Implementation:** Adapt `range_test_node.py` to use RadioLib on ESP32-C3 instead of USB serial.

### 2. TDMA for Multi-Balloon Coordination (from sx1280-serial)

**Future consideration:** If we ever fly multiple balloons on the same frequency, the TDMA protocol in `sx1280-serial` provides a proven design:
- 5-slot superframe with configurable period (1000ms) and guard time (80ms)
- Coordinator election via lowest node ID
- Beacon/Join/SlotMap control frames
- Per-peer warmup probing before data exchange

### 3. Fragmentation and Retransmission (from sx1280-serial)

**Relevant for FLRC mode:** When we test LR2021 FLRC (high-rate) mode, the fragmentation protocol is directly applicable:
- 128-byte fragments with 13-byte header (magic + version + msg_id + frag_idx + frag_count + payload_len)
- CRC-32 per fragment
- SLIP encoding for serial/UART links
- Sliding window ACK with configurable window size
- Datagram-level ARQ with retransmit

Our current 24-byte telemetry fits in a single fragment, but larger payloads (GPS traces, firmware updates) would need this.

### 4. Throughput Expectations (from sx1280-testing + correlation-test)

**Set realistic expectations:**
- 2.4 GHz LoRa at longest range: ~1 kbps with high loss
- Our 868 MHz Sub-GHz LoRa should do better (better propagation, +22 dBm)
- At SF9 / 125 kHz we expect ~1.7 kbps data rate, but delivery ratio will depend on range
- For the balloon (line-of-sight at altitude), range should be much better than ground-level testing

### 5. FLRC Mode for High-Rate (from sx1280-ethernet-adapter)

**Applicable to LR2021:** The LR2021 also supports FLRC mode. The sx1280-ethernet-adapter chose FLRC over LoRa for throughput reasons. For the balloon:
- LoRa (SF9, 125 kHz) for long-range telemetry (primary mode)
- FLRC could be used for short-range high-rate data transfer (e.g., when ground station is nearby)
- The adapter's link engine design (fragmentation + sliding window) would apply

### 6. Hardware Debug Ladder (from sx1280-serial feature branch)

**Adopt the staged testing approach:**
- L0: Raw SPI communication (verify LR2021 responds to SPI reads)
- L01: Basic TX/RX (send a packet, verify it arrives)
- L012: Full protocol (telemetry encoding, CRC, 60-second cycle)
- L0123: Range test (at increasing distances)

This is essentially what our `implementation-plan.md` already follows with Phase 1 (breadboard) through Phase 4 (integration test).

### 7. Radio Config Automation Lessons (from sx1280-correlation-test)

**Warning:** The E28 config protocol (6-byte UART commands) never worked reliably — 26 out of 26 config attempts failed in the field. The radios had to be configured manually via jumpers.

**For our project:** We configure the LR2021 directly via SPI registers (RadioLib), not through a vendor firmware command protocol. This is more reliable since we control the register writes directly.

### 8. Ground Station Architecture (from sx1280-ethernet-adapter)

**Design reference:** The adapter's architecture (Wi-Fi AP + HTTP status + radio bridge) maps directly to what a balloon ground station needs:
- ESP32 runs Wi-Fi AP mode
- HTTP endpoint for status monitoring (radio state, counters, uptime)
- Radio bridge sends/receives telemetry over the air
- Phone/laptop connects to AP to monitor status

This could inform the design of a portable ground station using ESP32 + LR2021.

### 9. Cross-Connection Race Conditions (from sx1280-serial feature branch)

**For future multi-node setups:** When 3+ radios start simultaneously, their control traffic can race and cause unreliable session establishment. Fix: gate higher-layer actions on lower-layer readiness confirmation.

### 10. E28 Module Documentation Gaps

The `SEARCH_ANSWERS.md` and `E28_plan_and_questions.md` files document the difficulty of getting reliable documentation for Chinese radio modules. This parallels our experience with the NiceRF LoRa2021 — sparse documentation, pin mappings that need empirical verification.

## What These Repos Do NOT Cover

- No Sub-GHz testing (all 2.4 GHz)
- No RadioLib usage (all use Ebyte vendor firmware over USB serial)
- No ESP32-C3 firmware (adapter uses ESP32-S3, others use Linux host)
- No solar/supercap power design
- No PCB design (all use commercial USB dev boards)
- No RTToF ranging (SX1280 supports it but it was never tested)
- No antenna design (no PCB Yagis, wire dipoles, or RF matching)
- No balloon or aviation-related work
