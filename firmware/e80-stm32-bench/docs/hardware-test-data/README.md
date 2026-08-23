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
