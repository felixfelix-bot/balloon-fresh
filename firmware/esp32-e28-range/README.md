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
`E28-RANGE v1.0 fw=<hash> chip="<SX12xx>" ranging_capable=<0|1>` then `ready`.

| Command | Args | Action / reply |
|---------|------|----------------|
| `ID?` | — | `E28-RANGE v1.0 fw=<hash>` |
| `STAT?` | — | `role=<master\|slave\|idle> freq=<MHz> sf=<n> bw=<kHz> pa=<dBm> addr=<0x…> last=<m\|none> err=<code>` |
| `RANGE` | — | master: one ranging exchange → `DIST=<meters>m` or `RANGE TIMEOUT` |
| `RANGE-SLAVE` | — | slave: respond to master's ranging requests → `SLAVE OK` |
| `RANGE?` | — | last distance: `DIST=<meters>m` (or `DIST=none`) |
| `CHIP?` | — | raw silicon probe: 17-byte capture of reg `0x01F0` hex + ascii, at 20/16/8/2 MHz (diagnostic) |
| `FREQ <hz>` | frequency Hz | set carrier (2400–2500 MHz) |
| `SF <n>` | 5–12 | LoRa spreading factor |
| `BW <khz>` | 812.5 | LoRa bandwidth (**812.5 kHz only** — ranging BW) |
| `PA <dbm>` | dBm | TX power, clamped to indoor cap (+10 dBm) |
| `ADDR <hex>` | 32-bit hex | ranging address (both ends must match) |
| `HELP` `/` `?` | — | list commands |

## Silicon identification — SX1280 / SX1281 / SX1282

RadioLib's `findChip()` decides which chip class it is talking to by reading the
16-byte **version string** at register `0x01F0` and comparing the first 6 chars
against a compile-time SKU string (`SX1282` in the original build). The T3S3
carrier is sold both as the plain **SX1280** (+13 dBm) and as the "with PA"
**SX1282** (+22 dBm) variant, so a hard-coded SKU makes the firmware fail on
half the boards with `RADIOLIB_ERR_CHIP_NOT_FOUND` (-2) — indistinguishable
from a dead SPI bus. That is exactly what happened on the first hardware run
(2026-09-23).

The firmware therefore:

1. reads the version string with a **raw SPI burst** before RadioLib init
   (decoded by the host-tested `e28_decode_chip_version()`, which tolerates the
   status byte being absent / leading / interleaved),
2. **adopts** whatever the silicon reports into `chipType` (subclass
   `SX128xRanging`), so one build covers both SKUs,
3. **rejects** anything else — `SX1281` is refused because RadioLib's SX1281
   class has no ranging implementation, and `SX126x` has no ranging engine at
   all. The banner then shows `chip="" ranging_capable=0` plus an explicit
   `ERR unsupported radio` line.

`CHIP?` prints the raw capture (hex + three ASCII alignments) so a dead bus
(all `00`/`FF`) is distinguishable from a working bus carrying the wrong part.

**SPI clock:** `16 MHz` (SX128x datasheet max is 18 MHz; the original 20 MHz was
over spec).

## Bench harness (host side)

`tools/e28_range_bench.py` drives a master/slave ranging exchange over two
boards attached to one host:

```bash
# identifies boards by USB serial (ttyACM numbers change on every replug!)
python3 tools/e28_range_bench.py --iters 5
python3 tools/e28_range_bench.py --iters 3 --pa -18     # near-field saturation test
```

Pitfalls it encodes:

- Boards are identified by **USB serial** (`9C:13:9E:F1:0C:28` = master default,
  `…:0C:60` = slave default), not by `/dev/ttyACMx`.
- Ports are opened with **`dtr=False, rts=False`**. Asserting DTR/RTS on an
  ESP32-S3 resets the board / parks it in the ROM loader.
- The slave must be armed (`RANGE-SLAVE`, blocks up to 10 s answering) *before*
  the master issues `RANGE`.


## Indoor power cap

SX1282 reaches +22 dBm, but indoor bench use is capped at **+10 dBm**
(`E28_RANGE_TXPOW_CAP_INDOOR_DBM = 10`, matching `E80_BENCH_TXPOW_CAP_INDOOR_DBM`).
The cap is enforced in the host-testable console **core** (`e28_range_console.c`),
so it cannot be bypassed by the firmware glue. `PA 22` → `ERR PA capped to 10 dBm`.
Values below the SX1282 floor (−18 dBm) are clamped to −18 dBm
(`E28_RANGE_PA_MIN_DBM`), so an out-of-range negative can never wrap past the cap.

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
against a fake io and drives every command + the indoor cap + the chip-version
decoder.

```bash
make test-unit         # runs the full unit suite including the E28 console test
```

The bench harness has its own pytest suite (also hardware-free):

```bash
python3 -m pytest firmware/esp32-e28-range/tools/test_e28_range_bench.py -v
```

## Host OS setup (Linux) for flashing / talking to the boards

The T3S3 ships with USB-CDC **off** in its factory firmware, so it is
completely invisible on USB until either the application enables USB-CDC (this
firmware sets `ARDUINO_USB_CDC_ON_BOOT=1`) or the ROM loader is entered by
holding **BOOT** while tapping **RST**. Once flashed, it always enumerates as
`303a:1001 Espressif USB JTAG/serial debug unit`.

The device node lands in group `plugdev` by default, which an ordinary
`dialout` user cannot open; install a udev rule:

```bash
echo 'SUBSYSTEM=="tty", ATTRS{idVendor}=="303a", ATTRS{idProduct}=="1001", MODE="0666", GROUP="dialout", SYMLINK+="ttyESP32-%n"' \
  | sudo tee /etc/udev/rules.d/99-espressif-usb-jtag.rules
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=tty
```

Observed on 2026-09-23: the boards did **not** enumerate at all through a
bus-powered USB hub, only when plugged directly into the host.
