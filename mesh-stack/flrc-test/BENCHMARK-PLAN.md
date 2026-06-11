# LR2021 FLRC Benchmark Plan

Characterize NiceRF LR2021 FLRC and LoRa performance across all bit rates, power levels,
packet sizes, and coding rates. Results feed into mesh V1/V2 throughput projections,
Wirehair erasure coding parameters, and link budget validation.

---

## Hardware Setup

- 2x ESP32-C3 SuperMini V1 (Board 1: `/dev/ttyACM2`, Board 2: `/dev/ttyACM3`)
- 2x NiceRF LoRa2021 (LR2021 Gen4, 18-pin)
- Sub-GHz antenna: wire dipole on Pin 9 (86mm legs, 868 MHz)
- 2.4 GHz antenna: wire dipole on Pin 10 (31mm legs, 2450 MHz)

---

## Phase 0: Bug Fix

- [ ] 0.1 Fix `standby()` bug in FLRC test firmware RX loops
- [ ] 0.2 Rebuild all 12 PlatformIO targets
- [ ] 0.3 Verify build succeeds for all targets

## Phase 1: FLRC Baselines (Bench ~1m)

Flash TX to Board 1, RX to Board 2. Collect serial output.

| ID | TX Env | RX Env | Freq | BR | Power | Pkts | Size | Status |
|----|--------|--------|------|----|-------|------|------|--------|
| F1 | `flrc_tx` | `flrc_rx` | 868 MHz | 325 kbps | +22 dBm | 1000 | 50B | [ ] |
| F2 | `flrc_tx_650` | `flrc_rx_650` | 868 MHz | 650 kbps | +22 dBm | 1000 | 50B | [ ] |
| F3 | `flrc_tx_24` | `flrc_rx_24` | 2.4 GHz | 1300 kbps | +12 dBm | 1000 | 50B | [ ] |
| F4 | `flrc_tx_24_max` | `flrc_rx_24_max` | 2.4 GHz | 2600 kbps | +12 dBm | 1000 | 50B | [ ] |

Results recorded here after execution:

```
F1: sent= received= errors= elapsed= throughput= rssi= snr=
F2: sent= received= errors= elapsed= throughput= rssi= snr=
F3: sent= received= errors= elapsed= throughput= rssi= snr=
F4: sent= received= errors= elapsed= throughput= rssi= snr=
```

## Phase 2: LoRa Baselines (Bench ~1m)

| ID | TX Env | RX Env | Freq | SF/BW | Power | Pkts | Size | Status |
|----|--------|--------|------|-------|-------|------|------|--------|
| L1 | `lora_tx` | `lora_rx` | 868 MHz | SF9/125 | +22 dBm | 100 | 50B | [ ] |
| L2 | `lora_tx_sf8` | `lora_rx_sf8` | 869.618 MHz | SF8/62.5 | +22 dBm | 100 | 50B | [ ] |

```
L1: sent= received= errors= elapsed= throughput= rssi= snr=
L2: sent= received= errors= elapsed= throughput= rssi= snr=
```

## Phase 3: Enhanced Serial-Command Benchmarker

### Firmware Development

- [ ] 3.1 Create `src/prbs.h` — PRBS-15 generator (Tier 2 payload integrity)
- [ ] 3.2 Create `src/config.h` — BenchmarkConfig struct with defaults
- [ ] 3.3 Create `src/bench_rx.h/cpp` — RX logic with seq# tracking (Tier 1) + PRBS verify (Tier 2)
- [ ] 3.4 Create `src/bench_tx.h/cpp` — TX logic with seq# + PRBS payload
- [ ] 3.5 Create `src/main.cpp` — Serial command parser + non-blocking main loop
- [ ] 3.6 Update `platformio.ini` — Add `bench` environment (single unified build)
- [ ] 3.7 Build and verify compilation
- [ ] 3.8 Flash to both boards, verify serial command interface works

### Serial Command Protocol

```
Configuration:  MODE FLRC|LORA, FREQ <MHz>, BR <kbps>, SF <7-12>, BW <kHz>,
                CR <value>, PWR <dBm>, SIZE <bytes>, COUNT <n>, SYNC <hex>
Execution:      ROLE TX|RX, RUN, STOP
Output:         CONFIG, RESULTS, CSVHEADER, STATUS, SEQLOG
```

### Payload Layout

```
Bytes 0-3:   Sequence number (uint32_t, big-endian)
Bytes 4-N:   PRBS-15 pattern seeded from seq# (Tier 2 integrity check)
End marker:  0xDE 0xAD 0xBE 0xEF + uint32_t total_sent
```

## Phase 4: Python Test Runner

- [ ] 4.1 Create `run_benchmark.py` — automated sweep runner
- [ ] 4.2 Define all sweep tables (BR sweep, power sweep, size sweep, CR sweep, SF sweep)
- [ ] 4.3 Test with a single config on hardware
- [ ] 4.4 Verify CSV output format

## Phase 5: Comprehensive Sweeps (Bench ~1m)

### 5A: FLRC Bit Rate Sweep — 2.4 GHz (8 points)

- [ ] 260 kbps @ 2450 MHz, +12 dBm
- [ ] 325 kbps @ 2450 MHz, +12 dBm
- [ ] 520 kbps @ 2450 MHz, +12 dBm
- [ ] 650 kbps @ 2450 MHz, +12 dBm
- [ ] 1040 kbps @ 2450 MHz, +12 dBm
- [ ] 1300 kbps @ 2450 MHz, +12 dBm
- [ ] 2080 kbps @ 2450 MHz, +12 dBm
- [ ] 2600 kbps @ 2450 MHz, +12 dBm

### 5B: FLRC Bit Rate Sweep — 868 MHz (8 points, lab-only)

- [ ] 260 kbps @ 868 MHz, +22 dBm
- [ ] 325 kbps @ 868 MHz, +22 dBm
- [ ] 520 kbps @ 868 MHz, +22 dBm
- [ ] 650 kbps @ 868 MHz, +22 dBm
- [ ] 1040 kbps @ 868 MHz, +22 dBm
- [ ] 1300 kbps @ 868 MHz, +22 dBm
- [ ] 2080 kbps @ 868 MHz, +22 dBm
- [ ] 2600 kbps @ 868 MHz, +22 dBm

### 5C: TX Power Sweep — 2.4 GHz FLRC 1300 kbps (7 points)

- [ ] 0 dBm
- [ ] 2 dBm
- [ ] 4 dBm
- [ ] 6 dBm
- [ ] 8 dBm
- [ ] 10 dBm
- [ ] 12 dBm

### 5D: TX Power Sweep — 868 MHz FLRC 650 kbps (6 points)

- [ ] 0 dBm
- [ ] 5 dBm
- [ ] 10 dBm
- [ ] 15 dBm
- [ ] 20 dBm
- [ ] 22 dBm

### 5E: Packet Size Sweep — 2.4 GHz FLRC 1300 kbps (9 points)

- [ ] 10 bytes
- [ ] 20 bytes
- [ ] 30 bytes
- [ ] 50 bytes
- [ ] 75 bytes
- [ ] 100 bytes
- [ ] 150 bytes
- [ ] 200 bytes
- [ ] 255 bytes

### 5F: Coding Rate Sweep — 2.4 GHz FLRC 1300 kbps (4 points)

- [ ] CR 1/2
- [ ] CR 2/3
- [ ] CR 3/4
- [ ] CR 1/0 (uncoded)

### 5G: LoRa SF Sweep — 868 MHz BW125 (6 points)

- [ ] SF7
- [ ] SF8
- [ ] SF9
- [ ] SF10
- [ ] SF11
- [ ] SF12

**Total: 48 bench test points**

## Phase 6: Range Testing

### 6A: Freifunk Berlin High Viewpoints

- [ ] Schedule with Freifunk contacts
- [ ] R1: Roof (~30m) to street level, ~0.5-1 km
- [ ] R2: Roof to park, ~2 km
- [ ] R3: High point to distant roof, ~5-10 km
- [ ] R4: Maximum urban, ~10-30 km

Test at each distance: FLRC 1300k @ 2.4G, FLRC 650k @ 868M, FLRC 325k @ 868M, LoRa SF9, LoRa SF7

### 6B: Mountaintop Test — Madeira to Porto Santo (~40 km)

- [ ] Plan trip logistics
- [ ] Prepare battery-powered auto-run setup
- [ ] Test configs: LoRa SF12/SF9/SF7, FLRC 325k/650k @ 868M, LoRa SF10 @ 2.4G, FLRC 1300k @ 2.4G
- [ ] Record GPS coordinates + altitude at both endpoints

## Phase 7: Analysis & Documentation

- [ ] 7.1 Generate `RESULTS.md` with all test data
- [ ] 7.2 Plot throughput vs bit rate curve
- [ ] 7.3 Plot PER vs TX power curve (sensitivity floor)
- [ ] 7.4 Plot throughput vs packet size curve
- [ ] 7.5 Plot RSSI vs distance (validate FSPL model)
- [ ] 7.6 Analyze burst loss distribution for Wirehair tuning
- [ ] 7.7 Update `docs/link-budget.md` with measured data
- [ ] 7.8 Update `docs/adr/010-adaptive-tx-power.md` with real throughput
- [ ] 7.9 Update `mesh-stack/ROADMAP.md` — mark FLRC characterization complete
- [ ] 7.10 Update `AGENTS.md` with benchmark status

### Key Questions To Answer

1. What is the real FLRC throughput at each bit rate? (efficiency % vs theoretical)
2. How far can FLRC 1300 kbps @ 2.4 GHz reach? (FIPS mesh viability)
3. What is the LR2021 FLRC sensitivity floor per bit rate?
4. Does payload integrity hold under CRC? (Tier 2 — expect 0 bit errors)
5. What PER does Wirehair need to handle? (burst loss patterns from Tier 1)
6. Is 868 MHz FLRC viable for medium-range links?
7. What packet size maximizes throughput?

---

## Timeline Summary

| Phase | Description | Time | When |
|-------|-------------|------|------|
| 0 | Bug fix + rebuild | 15 min | Session 1 |
| 1-2 | FLRC + LoRa baselines | 40 min | Session 1 |
| 3 | Enhanced firmware | 2-3 hours | Session 1-2 |
| 4 | Python runner | 1 hour | Session 2 |
| 5 | Comprehensive sweeps (48 tests) | 1 hour | Session 2 |
| 6A | Freifunk range testing | Half day | Schedule |
| 6B | Madeira mountaintop (40 km) | Full day | Trip |
| 7 | Analysis + docs | 1 hour | After all data |

## CSV Output Format

```csv
test_id,label,timestamp,mode,freq_mhz,br_kbps,sf,bw_khz,cr,pwr_dbm,pkt_size,pkt_count,
tx_sent,tx_errors,tx_elapsed_ms,tx_throughput_kbps,tx_time_per_pkt_ms,
rx_received,rx_crc_errors,rx_lost,rx_elapsed_ms,rx_throughput_kbps,
per_pct,ber_estimate_pct,
avg_rssi,min_rssi,max_rssi,avg_snr,min_snr,max_snr,
payload_corrupt_count,bit_errors_total,bits_checked_total,
burst_loss_max,burst_loss_avg,out_of_order_count,
distance_m,notes
```
