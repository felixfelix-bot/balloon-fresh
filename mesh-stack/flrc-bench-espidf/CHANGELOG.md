# Changelog

All notable changes to `flrc-bench-espidf` will be documented in this file.

## [Unreleased]

### Fixed
- **ESP32-C3 SPI clock brought inside the LR2021 datasheet maximum (40 MHz → 16 MHz).**
  `EspHalC3.h` drives GPSPI2 from `ESPHAL_C3_SPI_HZ`, which was `(40 * 1000 * 1000)` —
  2.5× the 16 MHz datasheet maximum. It is now `(16 * 1000 * 1000)`, and
  `dev_cfg.clock_speed_hz` (plus the boot banner) reads the same macro, so the
  flashed firmware self-reports the clock it configured. 40 MHz ran fine at ~1 m
  bench distance but left no timing margin at operational range / across
  temperature; the non-GDMA branch had the same problem at 18 MHz (fixed in
  `02108f5`, the GDMA define in `8fd3d4e`).
  - Regression gate: `tests/test_c3_spi_clock.py` (host-only, 8 tests) fails on the
    historical 40 MHz / 18 MHz values and passes at 16 MHz.
  - Build: clean ESP-IDF v5.4.1 `esp32c3` builds for both RAW_TX and RAW_RX
    (`CONFIG_BENCH_MODE_RAW_TX` / `RAW_RX`), 1054/1054 steps, 80% partition free.
  - Artifact check: the compiled call-site constant for `spi_bus_add_device()` is
    16 000 000 and no 40 MHz / 18 MHz constant remains in either ELF.
  - Throughput: modelled at **−8.0%** (1781.7 → 1639 kbps, 255 B payload, 2600 kbps
    FLRC), inside the 20% investigation budget — the link is RF-bound (air time is
    69% of the packet period). See
    `docs/lr2021-p04-spi-clock-16mhz-2026-09-11.md`.
  - **Not yet measured on air:** the 1000-packet hardware run is outstanding — no
    LR2021/C3 boards were connected on 2026-09-11. Procedure + pass criteria are in
    §5 of the doc above.
