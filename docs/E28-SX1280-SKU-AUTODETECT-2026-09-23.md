# E28 (SX1280) ranging bring-up — SKU autodetect + first hardware run (2026-09-23)

Hardware: 2 × LILYGO T3S3 V1.3 (ESP32-S3 + **SX1280**, plain +13 dBm SKU, no PA),
plugged directly into CobradorWave. USB serials `9C:13:9E:F1:0C:28` and
`9C:13:9E:F1:0C:60`.

Firmware: `firmware/esp32-e28-range` (was built against the "with PA" **SX1282**
SKU per the 2026-09-09 plan).

## Symptom

Both boards flashed clean, console answered every command, but ranging failed:

```
master: ERR range=-20
slave : ERR slave=-20
STAT?  -> role=master freq=2440 sf=7 bw=812.5 pa=10 addr=0xE80E2801 last=none err=-20
```

`err=-2` was already present from boot.

## Root cause

| code | RadioLib name | meaning here |
|------|---------------|--------------|
| -2 | `RADIOLIB_ERR_CHIP_NOT_FOUND` | `SX128x::modSetup()` → `findChip()` failed during `radio.begin()` at boot |
| -20 | `RADIOLIB_ERR_WRONG_MODEM` | ranging was attempted with the modem never configured — a *consequence*, not a second fault |

`findChip()` reads the 16-byte **version string** at register `0x01F0` and
`strncmp`s the first 6 chars against the compile-time SKU string. The build
hard-coded `SX1282`; the silicon reports `SX1280`. Nothing was wrong with SPI,
wiring, or the pins — the firmware simply refused to recognise the part.

This is a class of failure that *looks* like broken hardware. Two independent
confirmations that it was not:

- the read succeeded (the board was found, the string decoded), where a dead bus
  returns all `00`/`FF`;
- the customer-facing silkscreen on the radio can reads `SX1280`.

## Fix

1. **SKU autodetect.** Read the version string with a raw SPI burst *before*
   RadioLib init; decode it in the host-tested core; adopt whatever the silicon
   reports into `chipType` (`SX128xRanging : public SX1280` subclass). One build
   now covers both the SX1280 and SX1282 T3S3 SKUs.
2. **Capability gate.** `e28_chip_supports_ranging()` accepts `SX1280`/`SX1282`
   only. `SX1281` is rejected (RadioLib's SX1281 class has no ranging methods)
   and `SX126x` (sub-GHz, no ranging engine) is rejected; the boot banner states
   this explicitly instead of failing later with an opaque error code.
3. **SPI clock 20 MHz → 16 MHz.** SX128x datasheet max is 18 MHz; the previous
   value was over spec.
4. **`CHIP?` diagnostic command** (firmware glue): raw 17-byte capture of
   `0x01F0` in hex plus three ASCII alignments, at 20/16/8/2 MHz — distinguishes
   "dead bus" from "wrong part" in one command.
5. **Bench harness** `tools/e28_range_bench.py` (+ pytest): drives a
   master/slave exchange, resolves boards by USB serial (ttyACM numbers are
   reassigned per replug), and opens ports with `dtr=False, rts=False` because
   asserting DTR/RTS on an ESP32-S3 resets the board into the ROM loader.

## Tests

- `tests/src/e28_range/test_e28_range_console.cpp` — extended with the
  chip-version decoder: no-status / leading-status-byte / interleaved-status-byte
  layouts, dead bus `0xFF` and `0x00` (must not claim an SX1xx), NUL padding
  trimming, and the ranging capability gate (`SX1280`/`SX1282` accepted,
  `SX1281`/`SX1262`/NULL rejected). Observed RED first (compile failure against
  the pre-change core, then 3 failing checks against the first implementation —
  NUL padding was decoded as printable dots), then GREEN:
  `E28 range console: ALL CHECKS PASSED`.
- `firmware/esp32-e28-range/tools/test_e28_range_bench.py` — 14 tests for the
  harness helpers (serial-based port resolution incl. swapped tty numbers,
  `DIST=` parsing, `STAT?` parsing, timeout detection).

## Host / OS notes

- The T3S3 factory firmware has USB-CDC off, so the board is **invisible on USB**
  (`lsusb` empty, no `/dev/ttyACM*`) while powered and running. It appears once
  the app enables `ARDUINO_USB_CDC_ON_BOOT=1`, or by holding **BOOT** and tapping
  **RST** to enter the ROM loader (`303a:1001`).
- Through a bus-powered USB hub the boards did **not** enumerate at all; direct
  connection to the host works.
- The node is created as group `plugdev`; a `dialout` user needs the udev rule
  documented in the firmware README.

## Measurement status (end of 2026-09-23 session)

**Radio init: FIXED and proven on hardware.** Both boards boot
`chip="SX1280 V3B A9B7" ranging_capable=1`, `STAT? … err=0`. The raw probe reads
the same 17 bytes at 20/16/8/2 MHz:

```
47 53 58 31 32 38 30 20 56 33 42 20 41 39 42 37 00   ascii="SX1280 V3B A9B7."
```

**Ranging: still 0 valid measurements — `RADIOLIB_ERR_RANGING_TIMEOUT` (-901)
on both ends, invariant across a 4-way matrix:**

| variant | master | slave |
|---------|--------|-------|
| default (+10 dBm, SF7) | `RANGE TIMEOUT` | `ERR slave=-901` |
| PA -18 dBm | `RANGE TIMEOUT` | `ERR slave=-901` |
| PA -18 dBm, roles swapped | `RANGE TIMEOUT` | `ERR slave=-901` |
| PA -18 dBm, SF 10 | `RANGE TIMEOUT` | `ERR slave=-901` |

What the invariance rules OUT: near-field receiver saturation (power sweep
changed nothing), a single faulty board (swapping master/slave changed nothing),
low SNR / preamble (SF change did nothing), and modem misconfiguration (that
error was `-20`, now gone).

What it points AT (both would produce a symmetric, power-independent timeout):
1. **DIO1 / IRQ mapping.** `SX1280::range()` polls `digitalRead(irq)` for up to
   10 s. Register reads need no IRQ, so SPI can be perfect while ranging times
   out. The pinout in use (`DIO1=GPIO9`, `BUSY=GPIO36`) came from a third-party
   board file, not from the LILYGO schematic for this SKU.
2. **RF switch / antenna path not enabled.** If the carrier gates the RF front
   end on a GPIO the vendor firmware drives, SPI and ranging-setup succeed while
   no RF leaves or arrives. The sibling SX1262 T3S3 variant enables
   `SX126X_DIO2_AS_RF_SWITCH`; the equivalent for this SKU is unverified.

Next test (not yet run): a plain LoRa TX/RX pair between the two boards — that
separates "DIO1/RF path broken" (plain packets also fail) from "ranging-specific"
(plain packets pass). Needs two new console commands, then the same bench
harness.

Also unconfirmed and requested from the operator: antenna(s) attached, and more
physical separation than the ~10 cm both-boards-on-one-laptop bench imposes.
