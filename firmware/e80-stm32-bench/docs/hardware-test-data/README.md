# Hardware Test Data

Real captured data from E80 bench tests. Each file is from a specific test session.

## Session Index

### 2608231820 — Single-machine TX+RX (first success with AGC fix)

| File | Role | Machine | Notes |
|------|------|---------|-------|
| `tx-single-machine-2608231820.csv` | TX | T470 (Linux) | All 5 configs, 12/12 sent each, 0 errors |
| `tx-single-machine-2608231820-output.txt` | TX | T470 (Linux) | Raw terminal output |
| `rx-single-machine-2608231820.csv` | RX | T470 (Linux) | 50/50 packets, 0% PER, 0 bit errors. RSSI -20 to -24 dBm. First successful TX+RX with AGC fix firmware. |

- **Firmware hash:** `fd3ef66` (AGC fix — continuous RX mode, commit `058b54f`)
- **Distance:** ~0 (same machine, boards 10cm apart)
- **GPS:** None (indoor bench test)
- **Format:** Legacy 16-column CSV
- **Configs tested:** FLRC-650 L64, FLRC-2600 L64, LoRa-SF7 L64, LoRa-SF12 L64, FLRC-650 L255

### 2608232130 — Cross-machine TX+RX (first harmonized format test)

| File | Role | Machine | Notes |
|------|------|---------|-------|
| `tx-cross-machine-2608232130.csv` | TX | T14 Gen5 (Linux) | All 5 configs, 12/12 sent each, 0 errors |
| `rx-cross-machine-2608232130.csv` | RX | MacBook | 30/30 FLRC packets received, 0 bit errors. LoRa 0/20 (no SWD probe on Mac, can't reset between configs). |

- **Firmware hash:** `3bc6d0d` (AGC fix + harmonized PKT+STAT format)
- **Distance:** ~0 (same room, boards on same table)
- **GPS:** None (indoor bench test)
- **Format:** Harmonized 23-field PKT+STAT format
- **Configs tested:** FLRC-650 L64 (10/10), FLRC-2600 L64 (10/10), LoRa-SF7 L64 (0/10), LoRa-SF12 L64 (0/10), FLRC-650 L255 (10/10)
- **Known issue:** LoRa configs 2+3 received 0 packets. Root cause: Mac had no SWD probe connected. The LR2021 chip cannot hot-switch from FLRC to LoRa without an SWD reset between modulation changes. FLRC-only configs work without SWD probe.

### 2608232205 — First real range test (TX moving, RX stationary)

| File | Role | Machine | Notes |
|------|------|---------|-------|
| `tx-range-2608232205.csv` | TX | T14 Gen5 (Linux) | All 5 configs, 12/12 sent_ok each, 0 errors |
| `rx-range-2608232205.csv` | RX | MacBook | Config 0: 10/10 FLRC-650, RSSI -91.5 dBm, 0 bit errors. Configs 1-4: 0/10 (see notes) |
| `gps-tx-2608232205.kml` | GPS | TX side | 926 trackpoints, 32m movement during test |
| `rx-position-2608232205.md` | GPS | RX side | Stationary at lat 32.6420447, lon -16.9556977 (Madeira, Portugal) |

- **Firmware hash:** `3bc6d0d` (AGC fix, pre self-reset fix — LoRa modulation switching still broken without SWD probe)
- **Distance:** Real outdoor range test — RSSI -91.5 dBm (40 dB below bench test)
- **GPS:** TX track (KML, moving) + RX position (stationary)
- **Format:** Harmonized 23-field PKT+STAT
- **Configs tested:** FLRC-650 L64 (10/10 ✅), FLRC-2600 L64 (0/10), LoRa-SF7 L64 (0/10), LoRa-SF12 L64 (0/10), FLRC-650 L255 (0/10)
- **Known issues:**
  - Config 1 (FLRC-2600): 0/10 — higher bitrate has ~8-10 dB worse sensitivity, -91 dBm too weak
  - Configs 2-3 (LoRa): 0/10 — firmware didn't have self-reset fix yet (commit c70f582). Chip stuck in FLRC mode, couldn't switch to LoRa without SWD probe
  - Config 4 (FLRC-650 L255): 0/10 — cascading from stuck modulation state after failed LoRa switch at config 2
  - Fix: reflash both boards with latest firmware (c70f582+) which adds chip self-reset on modulation change

### Earlier sweep data

| File | Notes |
|------|-------|
| `rx-quick.csv`, `tx-quick.csv` | Quick test runs |
| `rx-2pc.csv`, `tx-2pc.csv` | Two-computer test runs |
| `rx-final.csv`, `tx-final.csv` | Final test runs before AGC fix |
| `combined-range-report.md` | Merged TX+RX analysis report |
| `combined-range-report-2pc.md` | Merged two-computer analysis report |

## Format Notes

- **Legacy format** (sessions before 2608232130): 16-column CSV with header row. Fields: `session,config,pkt_idx,ts_ms,rssi_dbm,snr_db,crc_ok,bit_err,freq_hz,mod,sf_or_br,bw,pa_dbm,len,pcrc16,captured_ts`
- **Harmonized format** (session 2608232130+): PKT+STAT lines with 23 fields per packet. Lines prefixed with `PKT,` (per-packet) or `STAT,` (per-config aggregate). The collaborator's visualization system ingests this format directly.

## Config Presets

All tests use `configs/outdoor-10.json` unless otherwise noted:
1. FLRC BR=650kHz, payload=64 bytes, gap=5000µs
2. FLRC BR=2600kHz, payload=64 bytes, gap=5000µs
3. LoRa SF=7, BW=125kHz, payload=64 bytes, gap=10000µs
4. LoRa SF=12, BW=125kHz, payload=64 bytes, gap=10000µs
5. FLRC BR=650kHz, payload=255 bytes, gap=5000µs

Each config sends 12 packets (10 measured + 2 prime-discard for AGC warmup).
