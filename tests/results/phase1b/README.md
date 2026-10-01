# Phase 1B A/B Comparison — RadioLib vs Raw SPI (P1B.3)

Sweep of FLRC bitrate, payload size, and TX inter-packet delay, comparing the
RadioLib TX path (`RUN` → `radio->transmit()`) against the raw SPI TX bypass
(`RAWTX` → WriteBuffer/SetTx direct SPI, see `runRawTx()` in
`mesh-stack/flrc-bench-espidf/main/bench_main.cpp`). RX side always uses the
RadioLib IRQ loop, so the A/B isolates the TX-side cost.

- Baseline (Phase 1): 20.8 kbps FLRC 2600 kbps / 255 B / 10 ms delay — see
  `docs/PHASE1-RESULTS.md`.
- Known RadioLib RX-side bottleneck (P1B.0): readData()+startReceive() cycle
  ~5 ms drops every other packet at inter-packet delays ≤5 ms (50% PER).

## Hardware

| Role | Device | Port (task card mapping) |
|------|--------|--------------------------|
| ESP32-A | ESP32-C3 + LR2021 | /dev/ttyACM2 |
| ESP32-B | ESP32-C3 + LR2021 | /dev/ttyACM3 |
| RP2040 | RP2040 + LR2021 (not used by A/B) | /dev/ttyACM1 |

2.4 GHz only (2450 MHz), PWR 12 dBm. Port numbers re-enumerate — the runner
auto-detects ttyACM2..9 and keeps TX/RX identity via /dev/serial/by-id.

## Run

```bash
python3 -u tests/p1b_ab_test.py --reset-between-tests 2>&1 | tee ab_sweep_console.log
# variant without group-boundary resets (CDC stress comparison):
python3 -u tests/p1b_ab_test.py --no-reset-between-tests
# subset of bitrates only:
python3 -u tests/p1b_ab_test.py --br 2600,1300,650 --reset-between-tests
```

Outputs: `ab_comparison.json` (all groups) and the console summary
(DELAY / BITRATE comparison tables + best result) in this directory.

## Groups

1. RadioLib DELAY sweep — FLRC 2600, 255 B, delay 10/5/2/1/0 ms
2. RawSPI DELAY sweep — same, `RAWTX` trigger
3. RadioLib bitrate sweep — delay 0, 255 B, BR 2600/1300/650/325 (`--br`)
4. RawSPI bitrate sweep — same, `RAWTX` trigger
5. Payload size sweep — BR 2600, delay 0, size 20/64/128/255, both modes

## Offline verification (no hardware needed)

```bash
python3 -m pytest tests/test_p1b_ab_runner.py -q
```

Covers CLI flag forms, `--br` parsing, RX result parsing, and port-identity
resolution across CDC re-enumeration.
