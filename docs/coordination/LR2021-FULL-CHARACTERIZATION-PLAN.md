# LR2021 Full Characterization Plan — Unified Speed + Range Test Matrix

> **Master reference document for the LR2021 Gen 4 characterization campaign.**
> Coordinates the speed-tests and range-tests tracks into a single unified test matrix.
> One walk-around test yields a complete dataset across all modes, bands, and distances.

---

## Table of Contents

1. [Objective](#1-objective)
2. [LR2021 Capability Matrix](#2-lr2021-capability-matrix)
3. [Firmware Status](#3-firmware-status)
4. [Critical Cross-Track Context](#4-critical-cross-track-context)
5. [Unified Test Matrix](#5-unified-test-matrix)
6. [Task Assignment](#6-task-assignment)
7. [Execution Order](#7-execution-order)
8. [Data Output Format](#8-data-output-format)
9. [Risks and Mitigations](#9-risks-and-mitigations)

---

## 1. Objective

Full characterization of the **Semtech LR2021 Gen 4** chip (NiceRF LoRa2021 module) across **all modes, bands, and distances**.

A single unified test matrix ties both sub-manager tracks together. **One physical walk-around test** — carrying the RX board through a series of distance markers while the TX board runs autonomously — produces a complete dataset of every mode/band/bitrate combination at every distance and environment.

**Deliverables:**
- All 14 firmware phases (10 existing + 4 new LF-FLRC) tested and verified.
- ~198 data points across 9 distance/environment positions × 22 mode/band/bitrate combos.
- A single merged CSV with PER, RSSI, SNR, and throughput for every combination.
- A summary matrix (mode × distance) showing max usable range per mode/bitrate.

---

## 2. LR2021 Capability Matrix

### Tested Modes

| Band | Mode | Parameters | Theoretical Bitrate | Tested? | Data Quality |
|------|------|-----------|--------------------|---------|--------------|
| 2.4 GHz (HF) | FLRC | 2600/2080/1300/650/325 kbps | 2600 kbps max | YES (speed-tests) | Good: 0% PER, throughput measured |
| 2.4 GHz (HF) | LoRa | SF7/SF9/SF12, BW 812 kHz | ~31 / 9.7 / 1.5 kbps | YES (speed-tests) | Good: 0% PER, RSSI saturated |
| 868 MHz (LF) | FLRC | 2600/2080/1300/650/325 kbps | 2600 kbps max | ESP-IDF bench only | **Missing RP2040 data** |
| 868 MHz (LF) | LoRa | SF7/SF9/SF12, BW 250 kHz | ~31 / 9.7 / 1.5 kbps | Firmware exists | **NO DATA collected** |

### Untested Modes (Lower Priority)

| Mode | Notes |
|------|-------|
| GFSK | Standard FSK modulation. LR2021 supports it but not needed for balloon telemetry. Low priority. |
| LR-FHSS | LoRa Frequency Hopping Spread Spectrum. Designed for massive-scale IoT satellite uplinks. Not relevant for point-to-point balloon links. Low priority. |
| OOK | On-Off Keying. Simplest modulation, no sync word. Useful only for legacy compatibility. Lowest priority. |

These three modes exist in the chip's register map but are **out of scope** for this characterization campaign unless the primary matrix reveals unexpected results.

---

## 3. Firmware Status

### Existing Firmware

**`multi_radio_sweep.cpp`** (speed-tests worktree) runs a **10-phase sweep**:

| Phase | Mode | Band | Detail |
|-------|------|------|--------|
| 0 | LoRa | HF (2.4 GHz) | SF7, BW 812 kHz |
| 1 | LoRa | HF | SF9, BW 812 kHz |
| 2 | LoRa | HF | SF12, BW 812 kHz |
| 3 | FLRC | HF | 2600 kbps |
| 4 | FLRC | HF | 1300 kbps |
| 5 | FLRC | HF | 650 kbps |
| 6 | FLRC | HF | 325 kbps |
| 7 | LoRa | LF (868 MHz) | SF7, BW 250 kHz |
| 8 | LoRa | LF | SF9, BW 250 kHz |
| 9 | LoRa | LF | SF12, BW 250 kHz |

**MISSING: LF FLRC phases (868 MHz FLRC).** Four new phases must be added (Task S1).

### Firmware Capabilities Already Implemented

- **RF path switching**: `SET_RX_PATH` — HF=1 for 2.4 GHz, LF=0 for 868 MHz. Applied per phase.
- **Frequency switching**: 2440 MHz (HF) / 868.0 MHz (LF), set per phase.
- **Modulation type switching**: per-phase packet type and modulation parameters.

### SPI Initialization Sequences

**FLRC phase init:**
```
SET_PACKET_TYPE(0x05)        // PT_FLRC
SET_FLRC_MOD_PARAMS          // bitrate, coding rate, shaping
SET_FLRC_SYNCWORD            // sync word bytes
SET_FLRC_PACKET_PARAMS       // preamble, payload length, CRC type
```

**LoRa phase init:**
```
SET_PACKET_TYPE(0x00)        // PT_LORA
SET_LORA_MOD_PARAMS          // SF, BW, CR
SET_LORA_PACKET_PARAMS       // preamble, payload length, CRC, header type
```

**MANDATORY before entering RX (every phase):**
```
SET_RX_PATH(0x01 or 0x00)    // 0x01=HF path, 0x00=LF path
CALIB_FE(0x0123)             // Front-end calibration — MANDATORY or CMD_ERROR
CALIBRATE(0x0122, mask 0x5F) // Image/bias calibration, mask 0x5F (NOT 0x6F — bit 5 undefined)
```

### Phase Schedule

- Fixed time budgets per phase — TX and RX stay synchronized.
- `TX_POWER_DBM` is a compile-time constant (currently **12 dBm**, max for LR2021).
- Full cycle (10 phases) ≈ 3 minutes. With 14 phases ≈ 3–4 minutes.

---

## 4. Critical Cross-Track Context

This section captures hard-won knowledge that **both tracks must share**. Ignore any of these at your peril.

### Speed-tests → Range-tests Handoff

| Item | Detail |
|------|--------|
| **SPI Protocol** | Raw 2-byte opcode SPI **WORKS**. RadioLib does **NOT** work. **Never use RadioLib.** |
| **RSSI decoding** | RSSI is **unsigned** — must negate for dBm. `GET_LORA_PACKET_STATUS` (opcode `0x022A`): `buf[2]`=RSSI, `buf[3]`=SNR. `RSSI_raw / 2 = dBm` (negate). `SNR_raw` (signed) `/ 4 = dB`. |
| **CR bug** | `LORA_CR` must be **1** (coding rate 4/5), **NOT 5**. Value 5 encodes an invalid CR → SF12/SF9 RX = 0. |
| **RSSI saturation** | At 1–2 m indoor, RSSI reads **-8 dBm** regardless of TX power (0–12 dBm). **Distance testing is the ONLY way** to see power-vs-range tradeoffs. |
| **FLRC indoor throughput** | 2600 kbps → **602 kbps** sustained; 1300 → **495**; 650 → **318**; 325 → **195** (all 0% PER). |
| **Duplicates** | RX picks up packets across listen windows. Use a **cumulative unique counter**, not raw count. |
| **SET_RX_PATH** | **MANDATORY**: HF=1 for 2.4 GHz, LF=0 for 868 MHz. Without it, the radio listens on the wrong path. |
| **CALIB_FE** | `CALIB_FE(0x0123)` is **MANDATORY** before RX or chip returns `CMD_ERROR`. |
| **USB CDC** | USB CDC dies on RP2040 during TX loops — known behavior, not a bug. **RX side stays responsive.** Capture serial data from the RX board only. |
| **BoardSerial()** | `BoardSerial()` wrapper is **MANDATORY** for all serial access. `serial.Serial()` is blocked by the guard. |
| **Board locking** | Lock **BOTH** boards atomically: `BALLOON_TRACK=<track> python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire both --purpose 'description' --timeout 120` |

### Range-tests → Speed-tests Handoff

| Item | Detail |
|------|--------|
| **CSV template** | `data/range-test-results.csv` — columns: `date, distance_m, bitrate_kbps, tx_power_dbm, payload_bytes, freq_mhz, antenna, orientation, obstacle, environment, tx_sent, rx_received, rx_unique, rx_lost, loss_pct, rssi_avg_dbm, rssi_min_dbm, throughput_kbps, elapsed_ms, verdict, notes` |
| **Unique-counting bug** | Range-tests found that PER showed 100% because the lost count was calculated wrong (4 billion+ "lost" packets). **Cumulative unique count must be maintained correctly.** `lost = expected_sent - unique_received`. |
| **Physical test methodology** | Walk to fixed distances, capture one full firmware cycle (~4 min) at each position. |
| **PCB antenna** | Dev boards use PCB trace antennas (not optimal). Note this for flight hardware comparison. |
| **Environment matters** | Indoor reflections cause multipath. Outdoor LOS gives cleaner data. Test both. |

---

## 5. Unified Test Matrix

### Fixed Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| TX power | **12 dBm** | Max for LR2021 |
| Payload (LoRa) | **127 bytes** | |
| Payload (FLRC) | **255 bytes** | |
| Preamble | **16 bytes** | |
| Packets per phase (FLRC) | **200** | |
| Packets per phase (LoRa) | **50** | SF12: reduced to 20–30 |
| Coding Rate (LoRa) | **4/5 (CR=1)** | NOT 5 — see CR bug above |

### Variable Parameters

| Parameter | Values |
|-----------|--------|
| Band | 2.4 GHz (HF path) / 868 MHz (LF path) |
| Mode | FLRC / LoRa |
| FLRC bitrate | 2600, 1300, 650, 325 kbps |
| LoRa SF | SF7, SF9, SF12 |
| Distance | 1 m, 5 m, 10 m, 25 m, 50 m |
| Environment | indoor LOS, indoor through 1 wall, indoor through 2 walls, outdoor LOS |

### Full Sweep Matrix

**22 mode/band/bitrate combinations per distance position.**

Distance + environment positions: 5 distances + 4 environments = **9 positions**.

**Total: 9 positions × 22 combos = 198 data points.**

### Phase Schedule (with new LF-FLRC phases)

| Phase | Name | Band | Frequency | Mode | Params | Packets | Time Budget |
|-------|------|------|-----------|------|--------|---------|-------------|
| 0 | HF-LoRa-SF7 | HF | 2440 MHz | LoRa | SF7, BW 812 kHz | 50 | 15 s |
| 1 | HF-LoRa-SF9 | HF | 2440 MHz | LoRa | SF9, BW 812 kHz | 50 | 15 s |
| 2 | HF-LoRa-SF12 | HF | 2440 MHz | LoRa | SF12, BW 812 kHz | 30 | 30 s |
| 3 | HF-FLRC-2600 | HF | 2440 MHz | FLRC | 2600 kbps | 200 | 8 s |
| 4 | HF-FLRC-1300 | HF | 2440 MHz | FLRC | 1300 kbps | 200 | 8 s |
| 5 | HF-FLRC-650 | HF | 2440 MHz | FLRC | 650 kbps | 200 | 8 s |
| 6 | HF-FLRC-325 | HF | 2440 MHz | FLRC | 325 kbps | 200 | 8 s |
| 7 | LF-LoRa-SF7 | LF | 868 MHz | LoRa | SF7, BW 250 kHz | 50 | 8 s |
| 8 | LF-LoRa-SF9 | LF | 868 MHz | LoRa | SF9, BW 250 kHz | 50 | 20 s |
| 9 | LF-LoRa-SF12 | LF | 868 MHz | LoRa | SF12, BW 250 kHz | 20 | 50 s |
| 10 | LF-FLRC-2600 | LF | 868 MHz | FLRC | 2600 kbps | 200 | 8 s | **← NEW** |
| 11 | LF-FLRC-1300 | LF | 868 MHz | FLRC | 1300 kbps | 200 | 8 s | **← NEW** |
| 12 | LF-FLRC-650 | LF | 868 MHz | FLRC | 650 kbps | 200 | 8 s | **← NEW** |
| 13 | LF-FLRC-325 | LF | 868 MHz | FLRC | 325 kbps | 200 | 8 s | **← NEW** |

**Full cycle ≈ 3–4 minutes. One cycle per distance position.**

---

## 6. Task Assignment

### Speed-tests Track

#### TASK S1: Add LF-FLRC phases to `multi_radio_sweep.cpp`

- Add **4 new Phase entries** for LF FLRC: 868 MHz, `rfPath=0`, `pktType=PT_FLRC`.
- Use the same FLRC modulation params as HF phases, but with `SET_RX_PATH(0x00)` for LF.
- Frequency: **868.0 MHz**.
- Keep all existing 10 phases unchanged — new phases are appended as 10–13.
- **Acceptance test:** compile successfully, verify total phase count = **14**.

#### TASK S2: Fix RX unique-counting for range data

RX firmware must output a structured result line per phase:

```
PHASE_RESULT <phase_num> <name> rx=<count> unique=<unique> lost=<lost> per=<pct> rssi_avg=<dbm> rssi_min=<dbm> throughput=<kbps>
```

Semantics:
- `unique` = count of **distinct sequence numbers** received.
- `lost` = `expected_sent - unique_received` (**NOT** `total_received - received`).
- `per` = `lost / expected_sent * 100`.

**Acceptance test:** verify with known packet sequences (e.g., inject gaps, confirm PER matches).

#### TASK S3: Add JSON output mode for automated capture

Each phase outputs one JSON line:

```json
{"phase":3,"name":"HF-FLRC-2600","band":"HF","freq":2440,"mode":"FLRC","bitrate":2600,"rx":200,"unique":200,"per":0.0,"rssi_avg":-48.8,"rssi_min":-104,"throughput":602.4}
```

Easy to parse, easy to merge across distances. One line per phase per cycle.

---

### Range-tests Track

#### TASK R1: Prepare distance markers

- Identify **5 distances**: 1 m, 5 m, 10 m, 25 m, 50 m.
- **Indoor:** through walls and around corners.
- **Outdoor:** clear LOS in a park or field.
- **Key metric:** sub-GHz (868 MHz) penetration through walls — this is the primary reason for dual-band testing.

#### TASK R2: Fix data capture pipeline

- Use the CSV template at `data/range-test-results.csv`.
- Parse `PHASE_RESULT` lines (or JSON lines) from RX serial output.
- One file per distance position, named: `data/char_dist_<m>_env_<indoor|outdoor|wall1|wall2>.csv`.
- Calculate PER correctly: `(sent - unique_received) / sent * 100`.

#### TASK R3: Physical walk-around test

1. Flash **BOTH** boards with the updated `multi_radio_sweep` firmware (14 phases).
2. TX board stays at a **fixed position** (battery powered).
3. RX board (laptop connected) walks to each distance marker.
4. At each position: wait for `CYCLE START` message, capture **one full cycle** (~4 min).
5. Record: distance, environment, any obstacles.
6. Move to next position after the full cycle is captured.

---

## 7. Execution Order

| Phase | Track | Tasks | Dependency | Hardware? |
|-------|-------|-------|------------|-----------|
| **A** | Speed-tests | S1 + S2 + S3 | None | No (software only) |
| **B** | Range-tests | R1 + R2 | None | No (prep only) |
| **C** | Joint | R3 | A **AND** B complete | **Yes** (operator + both boards) |
| **D** | Analysis | Aggregate CSVs, generate matrix + charts | C complete | No |

```
Phase A (speed-tests: S1+S2+S3) ──────────────┐
                                                ├──► Phase C (joint: R3) ──► Phase D (analysis)
Phase B (range-tests: R1+R2) ──────────────────┘
```

**Phase A and B run in PARALLEL.**
**Phase C requires both A and B complete.**
**Phase D requires C complete.**

---

## 8. Data Output Format

### Final Deliverable

A **single merged CSV** with all 198+ data points.

**Columns:**

```
date, distance_m, environment, band, freq_mhz, mode, bitrate_kbps, sf, tx_power_dbm,
payload_bytes, tx_sent, rx_received, rx_unique, per_pct, rssi_avg_dbm, rssi_min_dbm,
throughput_kbps, snr_avg_db, verdict, notes
```

**Example rows:**

| date | distance_m | environment | band | freq_mhz | mode | bitrate_kbps | sf | tx_power_dbm | payload_bytes | tx_sent | rx_received | rx_unique | per_pct | rssi_avg_dbm | rssi_min_dbm | throughput_kbps | snr_avg_db | verdict | notes |
|------|-----------|-------------|------|----------|------|-------------|-----|-------------|--------------|---------|------------|-----------|---------|-------------|-------------|----------------|-----------|---------|-------|
| 2026-07-24 | 1 | indoor_los | HF | 2440 | FLRC | 2600 | — | 12 | 255 | 200 | 200 | 200 | 0.0 | -8.0 | -8.0 | 602.4 | 8.5 | PASS | RSSI saturated |
| 2026-07-24 | 25 | wall1 | LF | 868 | LoRa | — | SF12 | 12 | 127 | 20 | 18 | 18 | 10.0 | -95.0 | -102.0 | 1.2 | -7.5 | MARGINAL | Through 1 drywall |

### Summary Table

A **mode × distance grid** showing the maximum usable range (or PER) at each mode/bitrate combination. This is the executive summary of the campaign — one glance tells you which modes work at which distances.

| Mode / Bitrate | 1 m | 5 m | 10 m | 25 m | 50 m |
|----------------|-----|-----|------|------|------|
| HF FLRC 2600 | ? | ? | ? | ? | ? |
| HF FLRC 1300 | ? | ? | ? | ? | ? |
| HF FLRC 650 | ? | ? | ? | ? | ? |
| HF FLRC 325 | ? | ? | ? | ? | ? |
| HF LoRa SF7 | ? | ? | ? | ? | ? |
| HF LoRa SF9 | ? | ? | ? | ? | ? |
| HF LoRa SF12 | ? | ? | ? | ? | ? |
| LF FLRC 2600 | ? | ? | ? | ? | ? |
| LF FLRC 1300 | ? | ? | ? | ? | ? |
| LF FLRC 650 | ? | ? | ? | ? | ? |
| LF FLRC 325 | ? | ? | ? | ? | ? |
| LF LoRa SF7 | ? | ? | ? | ? | ? |
| LF LoRa SF9 | ? | ? | ? | ? | ? |
| LF LoRa SF12 | ? | ? | ? | ? | ? |

> Cells filled with verdict: **PASS** (PER < 5%), **MARGINAL** (5–30%), **FAIL** (> 30%).

---

## 9. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **USB CDC dies during TX** | TX serial output unreliable | Use serial capture on **RX board only**; TX runs autonomously |
| **Board lock conflicts** | Both tracks try to access boards simultaneously | Both tracks use the same `BALLOON_TRACK` for the joint test; lock both boards atomically |
| **Antenna variation** | Results not comparable across tests | Document which antenna is used: PCB trace, wire dipole, or U.FL + external |
| **Multipath indoors** | Erratic RSSI/PER due to reflections | Test **both indoor and outdoor**; compare and note discrepancies |
| **RSSI accuracy** | Wrong dBm readings | Cross-check with known reference: at 1 m, 12 dBm, RSSI should be **> -50 dBm** |
| **Sub-GHz antenna disconnected** | LF path receives nothing | **VERIFY Pin 9 (ANT) has antenna attached** before starting LF phases |

---

## Hardware Reference

| Component | Detail |
|-----------|--------|
| **Chip** | Semtech LR2021 Gen 4 (NiceRF LoRa2021 module) |
| **MCU** | RP2040 (Raspberry Pi Pico) |
| **Bridge** | ESP32-C3 UART bridge for flashing |
| **TX board** | Serial F242D — `/dev/ttyACM0` |
| **RX board** | Serial 8332 — `/dev/ttyACM2` |
| **ESP32 bridges** | `/dev/ttyACM1` and `/dev/ttyACM3` |
| **Protocol** | Raw 2-byte opcode SPI (**NOT RadioLib**) |

## Worktree Locations

| Track | Worktree |
|-------|----------|
| Speed-tests | `~/worktrees/balloon-speed-tests/` |
| Range-tests | `~/worktrees/balloon-range-tests/` |
| Main repo | `~/repos/balloon-fresh/` |

---

*This document is the single source of truth for the LR2021 characterization campaign. Both tracks reference it for firmware details, test methodology, and data format.*
