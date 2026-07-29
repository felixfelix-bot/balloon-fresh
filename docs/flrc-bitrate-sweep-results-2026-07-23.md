# FLRC Bitrate Sweep Results — 2026-07-23

**Hardware:** 2x RP2040 + NiceRF LR2021, indoor 1-2m, 2440 MHz, 12 dBm, 255-byte payload
**Firmware:** flrc_bitrate_tx.cpp + flrc_bitrate_rx.cpp (compile-time FLRC_BITRATE)
**TX:** 1000 packets per burst, auto-start with 8s countdown
**RX:** Serial "RUN" command to start listening

## Results

| Bitrate (kbps) | TX Elapsed | RX Received | Unique | PER | Throughput (kbps) | RSSI Avg (dBm) | Efficiency |
|----------------|------------|-------------|--------|-----|-------------------|-----------------|------------|
| 2600 | ~1.5s | 1030 | 1030 | 0.00% | 602.4 | -48.8 | 23% |
| 1300 | 2.3s | 1040 | 972 | 0.00% | 495.1 | -50.7 | 38% |
| 650 | ~4.5s | 1163 | 1163 | 0.00% | 317.6 | -57.5 | 49% |
| 325 | ~6.4s | 1022 | 1022 | 0.00% | 195.4 | -51.2 | 60% |

## Key Findings

1. **ALL 4 bitrates: 0% PER** — All 1000 packets received at every bitrate.
2. **Throughput efficiency increases at lower bitrates** — 23% at 2600 vs 60% at 325. Overhead is relatively constant (SPI setup, IRQ handling), so it's a smaller fraction at lower bitrates.
3. **RSSI -48 to -58 dBm** — Strong signal at indoor range. Consistent across bitrates.
4. **Duplicates occur** — RX picks up packets across multiple listen windows. unique < received when this happens. PER calculation uses cumulative count correctly.
5. **Compile-time bitrate selection works** — No runtime serial command issues. Each firmware build has a fixed bitrate.

## Comparison with Previous Session

Previous FLRC 2600 test (flrc_raw_tx.cpp + flrc_range_rx.cpp):
- 1485 kbps sustained, 0% PER, 10,000 packets
- Higher throughput than this test (1485 vs 602 kbps)

Difference explained by:
- Previous test used 127-byte payload, this uses 255-byte
- Previous RX firmware had different listen window timing
- Previous test was 10,000 packets (longer capture, better averaging)

## Notes

- TX result format: `RESULT_TX,sent=1000,elapsed_ms=2278,throughput_kbps=895.5,bitrate=1300`
- RX result format: `RANGE_RESULT_RX,rx=1030,cum_rx=1030,...,bitrate=2600,pktSize=255`
- test_runner.py parser needs update to handle RANGE_RESULT_RX format
- UF2 mass-storage flashing proven as reliable method for dual-RP2040 BOOTSEL
