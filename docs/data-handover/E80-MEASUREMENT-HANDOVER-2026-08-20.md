# E80 Harmonization Measurement — Handover for Data Processing

**Date:** 2026-08-20
**From:** Felix (c03rad0r) + AI agent team
**To:** [Data processing collaborator]
**Subject:** E80-to-E80 RF measurement with harmonized firmware output — status, data location, and changes since

---

## 1. WHAT MEASUREMENT WAS DONE

On August 20, 2026, we ran an E80-to-E80 RF characterization measurement using two EBYTE E80-900MBl-02 STM32F103 boards (LR2021 Gen4 radio chips at 868 MHz). The measurement was an E80-to-E80 loopback test at close range (indoor bench, ~1m):

- **TX board:** /dev/ttyUSB3 (E80 #1)
- **RX board:** /dev/ttyUSB4 (E80 #2)
- **Config:** LoRa SF8, BW=125kHz, 868 MHz, CR=4/5, +10 dBm, 64-byte payload, 100 packets, 10ms gap
- **Firmware on both boards:** commit 17a6417

A second test was also run with PRBS-15 enabled for bit error rate (BER) verification:
- 100 packets sent, 100 received, 0 CRC errors, 0 bit errors, 0 bad bytes
- RSSI: -37.5 dBm (consistent, close range), SNR: 15-17 dB

### Measurement Results

- **30 PKT lines captured** (16 in initial capture + 14 during STAT? query)
- **All packets:** CRC OK, 0 bit errors, 0 bad bytes
- **RSSI:** constant -37 dBm
- **SNR:** 15 dB (most packets) or 17 dB (some), range 15-17 dB
- **Format:** 23-field harmonized PKT format VERIFIED

### Known Issues in This Measurement

1. **pkt_size discrepancy:** Initial capture shows pkt_size=255 (stale config from prior session), STAT? capture shows pkt_size=64 (correct). The initial 16 packets used a default from a previous CONFIG.
2. **TX sent=10 not 100:** TX stopped early. gap_us=100000 (100ms, not 10ms) suggests firmware interpreted gap differently than intended.
3. **Only 30 packets total captured:** Due to TX stopping early + timing mismatch.

---

## 2. WHAT HARMONIZATION CHANGES WERE IN THE FIRMWARE AT MEASUREMENT TIME

The firmware running during the measurement was commit **17a6417** on the `feat/persist-tx-seq` branch. The following harmonization changes (from the "Firmware Output Harmonization" requirements document) were already implemented in this build:

### MUST-HAVE items (M1-M7) — ALL PRESENT:

| Req | Description | Status | Commit |
|-----|-------------|--------|--------|
| **M1** | FW_HASH in boot banner | DONE | 0ace58d — boot banner emits `fw=FW_HASH=<sha7>` |
| **M2** | Capture tool hash gate | NOT YET (host-side, added after measurement in ed40549) | — |
| **M3** | Per-packet output on E80 | DONE | 5ec1c40 — E80 emits one PKT line per received packet |
| **M4** | Common 23-field PKT format | DONE | 5ec1c40 — full 23-field format: `PKT,session_id,config_id,replicate,seq,ts_ms,rssi_dbm,snr_db,crc_ok,bit_err,bytes_bad,freq_hz,mod,sf,bw_khz,cr,power_dbm,pkt_size,gps_fix,gps_lat,gps_lon,gps_alt,gps_sats,gps_hdop` |
| **M5** | Config in every data line | DONE | 5ec1c40 — freq_hz, mod, sf, bw_khz, cr, power_dbm, pkt_size all in PKT |
| **M6** | Non-resetting uint32 seq | DONE | bae93e3 — tx_seq persists across START commands, uint32 |
| **M7** | CRC-failed packets logged | DONE | 82f5c0e + 04e5b28 — CRC-failed packets emit PKT line with crc_ok=0, RSSI extracted |

### Also present at measurement time:

| Req | Description | Status | Commit |
|-----|-------------|--------|--------|
| **O4** | CONFIG_START markers | DONE | 507d6d2 — `CONFIG_START,<config_id>,<replicate>,<ts_ms>` emitted on config switch |
| **PRBS-15** | Bit error rate test pattern | DONE | 6896223 + 17a6417 — PRBS-15 LFSR fill + verify in RX, bit_err/bytes_bad in PKT |
| **PRBS-9** | Hardware PRBS via chip TX_TEST_MODE | DONE (but broken) | 17a6417 — CONFIG PRBS9 ON accepted, but causes TX timeout (chip diagnostic mode incompatible with packet TX) |
| **N3** | gap_us in STAT reply | NOT YET (added after measurement in ed40549) | — |
| **Baud** | UART baud 115200 → 2,000,000 | DONE | 56063fa + b248a20 |

### What was NOT yet in the firmware during measurement:

- **M2 (hash gate):** The capture tool did NOT enforce firmware hash at session start. This was added in ed40549 (after measurement). The firmware itself emits FW_HASH, but the host tool did not validate it.
- **N1 (SNR on CRC-failed packets):** SNR is zeroed for CRC-failed LoRa packets even though the chip measures it. Bug identified, fix in progress.
- **N3 (gap_us in STAT):** The STAT? reply did not include gap_us. Added in ed40549.
- **N2 (second RSSI field):** Not implemented — only one RSSI field in PKT format (by design).

---

## 3. WHERE THE DATA IS IN THE GIT REPOSITORY

### Measurement results file:
```
tools/e80_harm_measurement_results.txt
```
Path in repo: `tools/e80_harm_measurement_results.txt`
Commit: 4af2cf6

This file contains the raw PKT lines, STAT? output, and analysis notes from the E80-to-E80 measurement.

### PRBS verification test report:
```
docs/E80-PRBS-VERIFY-2026-08-20.md
```
Path in E80 worktree: `docs/E80-PRBS-VERIFY-2026-08-20.md`
Commit: 296ec6d

This file documents the PRBS-15 verification test (100/100 packets, bit_err=0) and PRBS-9 hardware test (failed — TX timeout).

### Repository location:
```
GitHub: https://github.com/felixfelix-bot/balloon-fresh
Branch: feat/c3-harmonization
```

The E80 firmware lives in `firmware/e80-stm32-bench/` within the same repo. The measurement tools are in `tools/`.

### Full PKT format spec (23 fields):
```
PKT,session_id,config_id,replicate,seq,ts_ms,rssi_dbm,snr_db,crc_ok,bit_err,bytes_bad,freq_hz,mod,sf,bw_khz,cr,power_dbm,pkt_size,gps_fix,gps_lat,gps_lon,gps_alt,gps_sats,gps_hdop
```

Field definitions:
1. `session_id` — assigned by capture tool (0 in this measurement)
2. `config_id` — configuration index (0 = first config)
3. `replicate` — pass number within session (0 = first pass)
4. `seq` — packet sequence number (uint32, non-resetting)
5. `ts_ms` — device timestamp in milliseconds (monotonic uptime)
6. `rssi_dbm` — RSSI in dBm (integer, uncalibrated)
7. `snr_db` — SNR in dB (LoRa only, 0 for FLRC)
8. `crc_ok` — 1 = CRC passed, 0 = CRC failed
9. `bit_err` — bit errors from PRBS-15 verify (0 = no errors)
10. `bytes_bad` — bytes that didn't match PRBS pattern (0 = all match)
11. `freq_hz` — TX frequency in Hz (868000000)
12. `mod` — modulation (LORA or FLRC)
13. `sf` — spreading factor (LoRa only, 0 for FLRC)
14. `bw_khz` — bandwidth in kHz (125)
15. `cr` — coding rate (5 = 4/5 for LoRa; for FLRC: 0=1/2, 1=3/4, 2=uncoded)
16. `power_dbm` — configured TX power (10)
17. `pkt_size` — payload size in bytes (64 or 255 — see known issues)
18-23. `gps_fix, gps_lat, gps_lon, gps_alt, gps_sats, gps_hdop` — GPS fields (all 0, no GPS on E80 bench)

---

## 4. CHANGES MADE SINCE THE MEASUREMENT

### E80 firmware (after 17a6417):

| Commit | Date | Description |
|--------|------|-------------|
| ed40549 | Aug 20 16:09 | Added gap_us to STAT? reply (N3) + firmware hash gate to e80_bench_ctl.py (M2) |
| 296ec6d | Aug 20 16:15 | PRBS verification test report (100/100 pkts, bit_err=0, 23-field format confirmed) |

### In progress (background workers dispatched):

1. **E80 SNR fix (N1 bug):** SNR is zeroed for CRC-failed LoRa packets despite the IRQ handler extracting it. Fix: pass through SNR value even on CRC fail. Worker dispatched, not yet committed.

2. **RP2040 TX harmonization:** The RP2040 TX firmware (multi_radio_sweep_gps_v4.cpp) still uses the old 5-field PKT format with uint16_t resetting seq. Worker dispatched to harmonize to 23-field format + uint32 non-resetting seq + CONFIG_START markers.

### Harmonization gap analysis (full audit results):

| Req | E80 | C3 | RP2040 RX | RP2040 TX |
|-----|-----|----|-----------|-----------|
| M1 FW_HASH | DONE | DONE | DONE | DONE |
| M2 Hash gate | DONE (ed40549) | DONE | DONE | — |
| M3 Per-pkt output | DONE | DONE | DONE | MISSING (in progress) |
| M4 23-field format | DONE | DONE | DONE | MISSING (in progress) |
| M5 Config in data | DONE | DONE | DONE | MISSING (in progress) |
| M6 Non-reset seq | DONE | DONE | DONE | MISSING (in progress) |
| M7 CRC-fail logged | DONE | DONE | DONE | N/A (TX) |
| N1 SNR per-pkt | PARTIAL (bug, fixing) | PARTIAL | DONE | MISSING |
| O4 CONFIG_START | DONE | DONE | DONE | MISSING (in progress) |

---

## 5. CURRENT STATUS (AS OF 2026-08-20)

### What works:
- E80-to-E80 measurement completed and data committed
- 23-field harmonized PKT format verified on E80 (all fields present, correct)
- PRBS-15 BER verification working (100/100 packets, 0 bit errors)
- All 7 MUST-HAVE harmonization items (M1-M7) implemented on E80 and C3
- RP2040 RX fully harmonized
- Firmware hash in boot banner on all 3 rigs

### What's still being fixed:
- E80 SNR pass-through on CRC-failed packets (N1 bug)
- RP2040 TX firmware harmonization (M3-M7, O4)
- E80 host tool hash gate was added after measurement (M2 done in ed40549)

### What's NOT yet done:
- E80 boards still running firmware 17a6417 (pre-ed40549). The post-measurement fixes (gap_us, hash gate) are committed but NOT yet flashed to the boards.
- Cross-rig integration test (PRBS-8): blocked on all 3 rigs being harmonized + at bench
- Range measurements (MEAS-1, MEAS-2): blocked on integration test

### Related documents in the repo:
- `docs/data-handover/DATA-INVENTORY-2026-08-19.md` — classification of all historical RF data for v0 ingest
- `docs/data-handover/FIRMWARE-HARMONIZATION-2026-08-19.md` — full harmonization requirements (M1-M7, N1-N5, O1-O4)
- `docs/data-handover/DATA-INVENTORY-RESPONSES.md` — Q&A responses for the data inventory (6 questions answered from git history)
- `docs/e80-harmonization-gap-analysis.md` — detailed M1-M7 gap audit per rig
- `docs/E80-PRBS-VERIFY-2026-08-20.md` — PRBS-15 verification test report

---

## 6. REPRODUCING THE MEASUREMENT

To reproduce this measurement:

1. Flash both E80 boards with firmware 17a6417 (or latest ed40549) via SWD
2. Connect TX board to /dev/ttyUSB3, RX board to /dev/ttyUSB4
3. Serial baud: 2,000,000 (NOT 115200)
4. On RX: `ROLE RX` then `PRBS ON` (enable PRBS-15 verification)
5. On TX: `ROLE TX` then `ARM TX` then `START N=100 LEN=64 GAP=10000`
6. Capture PKT lines from RX serial output
7. Query `STAT?` on both boards for aggregate stats

Build: `cd firmware/e80-stm32-bench && pio run -e e80_bench`
Flash: `openocd -f /tmp/openocd-e80.cfg -c "program build-fw/e80_bench.bin verify reset exit 0x08000000"`

Flash size: 24,972 bytes (38.10% of 64KB flash)

---

*This document was prepared for forwarding to a data processing collaborator. Questions about the data, firmware, or harmonization status can be directed to Felix via the balloon-hermes Signal group.*