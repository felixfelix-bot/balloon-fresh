# E28-2G4M27S (SX1282) Ranging Bridge — LILYGO T3S3

Firmware that exposes the E28-2G4M27S 2.4 GHz radio as an E80-style serial
console with master/slave time-of-flight (ToF) ranging, so a balloon RX and TX
bundle can measure their physical separation without GPS.

- **Host:** ESP32-S3 (LILYGO T3S3 V1.3)
- **Radio:** SX1282 (SX128x family — ranges identically to SX1280; RadioLib
  `SX1282` native, no subclass needed). The E28-2G4M27S module is wired
  directly via SPI (all onboard, no soldering beyond the SPI header).
- **Build:** PlatformIO, `espressif32` platform, `lilygo-t3-s3` board.

## Pinout (verified from sx1280-flrc-kiss-tnc, runs on this exact board)

| Signal | ESP32-S3 GPIO |
|--------|---------------|
| RADIO_SCK  | 5  |
| RADIO_MISO | 3  |
| RADIO_MOSI | 6  |
| RADIO_NSS  | 7  |
| RADIO_RST  | 8  |
| RADIO_BUSY | 36 |
| RADIO_DIO1 | 9  |

RadioLib `Module(RADIO_NSS, RADIO_DIO1, RADIO_RST, RADIO_BUSY, spiRf)` =
`Module(7, 9, 8, 36, spi)`. SPI 20 MHz, mode 0.

## Build, flash, monitor

```bash
pio run -e esp32-e28-range                       # build
pio run -e esp32-e28-range -t upload             # flash over USB
pio device monitor -p /dev/ttyACM0 -b 115200     # console
```

## Serial console command set

Case-insensitive, `\n`-terminated, one command per line. Boot prints
`E28-RANGE v1.0 fw=<hash>` then `ready`.

| Command | Args | Action / reply |
|---------|------|----------------|
| `ID?` | — | `E28-RANGE v1.0 fw=<hash>` |
| `STAT?` | — | `role=<master\|slave\|idle> freq=<MHz> sf=<n> bw=<kHz> pa=<dBm> addr=<0x…> last=<m\|none> err=<code>` |
| `RANGE` | — | master: one ranging exchange → `DIST=<meters>m` or `RANGE TIMEOUT` |
| `RANGE-SLAVE` | — | slave: respond to master's ranging requests → `SLAVE OK` |
| `RANGE?` | — | last distance: `DIST=<meters>m` (or `DIST=none`) |
| `FREQ <hz>` | frequency Hz | set carrier (2400–2500 MHz) |
| `SF <n>` | 5–12 | LoRa spreading factor |
| `BW <khz>` | 406.25 / 812.5 / 1625 | LoRa bandwidth (ranging-valid only; **812.5 kHz default**) |
| `PA <dbm>` | dBm | TX power, clamped to indoor cap (+10 dBm) |
| `ADDR <hex>` | 32-bit hex | ranging address (both ends must match) |
| `HELP` `/` `?` | — | list commands |

## Indoor power cap

SX1282 reaches +22 dBm, but indoor bench use is capped at **+10 dBm**
(`E28_RANGE_TXPOW_CAP_INDOOR_DBM = 10`, matching `E80_BENCH_TXPOW_CAP_INDOOR_DBM`).
The cap is enforced in the host-testable console **core** (`e28_range_console.c`),
so it cannot be bypassed by the firmware glue. `PA 22` → `ERR PA capped to 10 dBm`.

## Ranging configuration

Ranging only supports LoRa bandwidths 406.25 / 812.5 / 1625 kHz
(`RADIOLIB_ERR_INVALID_BANDWIDTH` otherwise). **Use 812.5 kHz.** Other params
(freq, SF, coding rate) must match on both ends. The default AN1200.29
calibration table gives relative precision; absolute distance needs a
per-module calibration pass at a known distance (`CAL` command is a planned
extension).

Default config on boot: freq 2440 MHz, SF 7, BW 812.5 kHz, PA +10 dBm,
addr `0xE80E2801`.

## Host tests (no hardware)

The console core (`src/e28_range_console.c`) is host-testable behind an
`e28_io_t` radio seam. The test suite (`tests/src/e28_range/`) compiles it
against a fake io and drives every command + the indoor cap.

```bash
make test-unit         # runs the full unit suite including the E28 console test
```
