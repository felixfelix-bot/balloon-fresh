# E80 Distributed Range Test — Merge Report

## Summary

| Metric | Value |
|--------|-------|
| Total expected | 50 |
| Total received | 41 |
| Total lost | 9 |
| Overall PER | 18.0% |
| Foreign packets | 0 |

## Per-Config Results

| Config | Label | N | Received | Lost | PER | RSSI avg | SNR avg |
|--------|-------|---|----------|------|-----|----------|---------|
| 0 | FLRC-650 LEN64 | 10 | 1 | 9 | 90% | -41.0 | 0.0 |
| 1 | FLRC-2600 LEN64 | 10 | 10 | 0 | 0% | -41.8 | 0.0 |
| 2 | LoRa-SF7 BW125 LEN64 | 10 | 10 | 0 | 0% | -42.0 | 14.6 |
| 3 | LoRa-SF12 BW125 LEN64 | 10 | 10 | 0 | 0% | -42.0 | 10.0 |
| 4 | FLRC-650 LEN255 | 10 | 10 | 0 | 0% | -41.8 | 0.0 |

## Files

- `combined.csv` — machine-readable merged data
- `tx-log.csv` — TX-side per-config log
- `rx-log.csv` — RX-side per-packet log
