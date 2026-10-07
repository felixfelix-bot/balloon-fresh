# V9 D2b(b) — LoRa2021F33 + SX1280 pin plan

Status: proposed implementation baseline, pending schematic ERC and module-datasheet
review. This is the pin plan for **ESP32-S3-WROOM-1U-N8R8** (octal PSRAM),
LoRa2021F33-2G4, SX1280, MS5607-02BA03 and MAX-M10S. It supersedes the old
second-SPI sketch that used IO35/IO36/IO37.

## Electrical constraints

The N8R8 module reserves IO35, IO36 and IO37 for octal PSRAM. They are not
available as board GPIOs and must not appear on either radio bus. IO39--IO42
are the native JTAG pins; this plan spends them on SX1280 control and therefore
requires USB-Serial-JTAG (IO19/IO20) or an external debug strategy. IO0, IO3,
IO45 and IO46 are boot strapping pins and are deliberately not assigned below.
All signals are 3.3 V logic; the F33 CE input is tied to 3V3 locally as required
by the module, not treated as an ESP32 output.

## Pin assignment

| ESP32-S3 GPIO | Net / function | Device | Direction / notes |
|---:|---|---|---|
| 4 | F33_SCK / SPI2 FSPI clock | LoRa2021F33 | output |
| 5 | F33_MOSI / SPI2 FSPI MOSI | LoRa2021F33 | output |
| 6 | F33_MISO / SPI2 FSPI MISO | LoRa2021F33 | input |
| 7 | F33_CS_N | LoRa2021F33 | output, idle high |
| 8 | F33_BUSY | LoRa2021F33 | input |
| 9 | F33_IRQ / DIO1 | LoRa2021F33 | input, interrupt |
| 10 | F33_RESET_N | LoRa2021F33 | output, assert low |
| 11 | F33_DIO5 | LoRa2021F33 | input, interrupt/status |
| 12 | F33_CE | LoRa2021F33 | **do not drive from firmware; strap to 3V3** |
| 14 | SX1280_SCK / SPI3 clock | SX1280 | output |
| 15 | SX1280_MOSI / SPI3 MOSI | SX1280 | output |
| 16 | SX1280_MISO / SPI3 MISO | SX1280 | input |
| 17 | SX1280_CS_N | SX1280 | output, idle high |
| 18 | SX1280_DIO2 | SX1280 | input; optional DIO2 function |
| 21 | GNSS_PPS | MAX-M10S | input, timestamp interrupt |
| 38 | SX1280_BUSY | SX1280 | input |
| 39 | SX1280_RESET_N | SX1280 | output, assert low; native MTCK/JTAG lost |
| 40 | SX1280_DIO1 / IRQ | SX1280 | input, interrupt; native MTDO/JTAG lost |
| 41 | SX1280_DIO3 | SX1280 | input/optional; native MTDI/JTAG lost |
| 42 | SX1280_ANT_SW / reserved control | SX1280 FEM/network | output only if fitted; native MTMS/JTAG lost |
| 43 (RXD0) | GPS_TX → S3_RX | MAX-M10S | UART0 RX; shared with console only by explicit mux policy |
| 44 (TXD0) | GPS_RX ← S3_TX | MAX-M10S | UART0 TX; shared with console only by explicit mux policy |
| 1 | I2C_SDA | MS5607-02BA03 | open-drain, external pull-up to 3V3 |
| 2 | I2C_SCL | MS5607-02BA03 | open-drain, external pull-up to 3V3 |
| 19 | USB_D- / console | ESP32-S3 | USB-Serial-JTAG, no external radio use |
| 20 | USB_D+ / console | ESP32-S3 | USB-Serial-JTAG, no external radio use |

SPI2/FSPI and SPI3 are separate ESP-IDF hosts with independent chip selects;
there is no shared radio bus. The exact F33 DIO names are schematic aliases:
map them to the F33 vendor pad names during symbol capture, and do not silently
swap IRQ/BUSY/RESET. SX1280 DIO2/DIO3/ANT_SW are included so a populated
front-end switch does not require a board respin; if the chosen SX1280 module
lacks one of these pins, leave the corresponding test pad NC rather than
reassigning a strapping pin.

## Explicit strapping-pin audit

| Strap | Assignment in this plan | Handling |
|---|---|---|
| IO0 | none | Leave available for boot/download. No radio pull-up, pulldown, or CS. |
| IO3 | none | Leave available for boot strap. No sensor or radio connection. |
| IO45 | none | Leave at module/vendor-required strap level; no external load. |
| IO46 | none | Leave at module/vendor-required strap level; no external load. |

**No strapping pins are touched.** IO35--IO37 are also intentionally unused
because they are octal-PSRAM connections, not spare GPIO. IO39--IO42 are not
straps, but the assignment consumes the native JTAG function; this is an
accepted, explicit debug trade-off, not an accidental conflict.

## Blockers and schematic gates

1. **No pin-plan blocker remains for the four requested strap pins or PSRAM
   pins.** The old IO35/36/37 SPI1 proposal is forbidden.
2. **JTAG conflict is explicit:** if production firmware requires native
   JTAG, this plan is blocked and SX1280 control signals must move to a
   revised GPIO allocation before schematic capture. USB-Serial-JTAG is the
   assumed debug path for this baseline.
3. Confirm the F33 vendor pad names and CE electrical requirement against the
   exact purchased revision before symbol release. CE must be a fixed 3V3 net;
   it must not be a floating MCU-controlled signal.
4. Confirm the selected SX1280 board's DIO2/DIO3/antenna-switch requirements.
   Do not populate an antenna switch net unless the RF module schematic proves
   it exists.
5. GPS UART boot-console multiplexing must be resolved in firmware (GPS is the
   flight owner after boot); it is not a reason to move GPS onto IO0/IO3.

This plan covers both SPI buses, unique CS, radio IRQ/DIO, BUSY, RESET, F33 CE,
MS5607 I2C, MAX-M10S UART/PPS, USB console, and all requested strap conflicts.
