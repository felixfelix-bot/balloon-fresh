# Radio Config Comparison: RP2040 vs ESP32 (LR2021)

> **Phase 1.0 prerequisite** — blocks all Phase 1 interop testing.
> Task: `t_edfe9eda` (branch `lr2021/p1-config-compare`)

## TL;DR (read this first)

**The two platforms CANNOT interoperate as-is.** The ESP32-C3 fully configures the
LR2021 via RadioLib (`LR2021::begin(...)`). The RP2040 coprocessor firmware uses a
**raw register-level SPI driver that configures ZERO modulation parameters** — it only
resets the chip, sets RX mode, and reads the FIFO. Every LoRa parameter (frequency,
modem type, BW, SF, CR, sync word, preamble, CRC, IQ, TCXO) is left at the chip's
power-on reset defaults, which do **not** match the ESP32.

Result: an ESP32-transmitted LoRa packet @ 868 MHz / SF9 / BW125 will **not** be
received by the current RP2040 firmware. The recommended fix is to port the RP2040
onto RadioLib (already declared as a `lib_deps` dependency) so both sides call the
identical `begin()` sequence. See [Recommended Fix](#recommended-fix).

## Sources inspected

| Platform | File | Driver |
|---|---|---|
| ESP32-C3 (tracker/TX) | `tracker/firmware/main/app_main.cpp` (`init_radio()`, L129–159) | RadioLib `LR2021` v7.6.0 |
| ESP32 config defaults | `tracker/firmware/main/Kconfig.projbuild` (L91–107), `tracker/firmware/sdkconfig.defaults` | Kconfig |
| RadioLib `begin()` impl | `components/RadioLib/src/modules/LR2021/LR2021.cpp` (L23–53) | — |
| RadioLib sync-word constant | `components/RadioLib/src/modules/LR2021/LR2021_commands.h` (L404) | — |
| RP2040 (coprocessor/RX) | `firmware/rp2040/src/radio.cpp`, `radio.h`, `main.cpp`, `pins.h`, `platformio.ini` | **Custom raw SPI** (NOT RadioLib) |

Note: `docs/HARDWARE-TEST-PLAN.md` (referenced by the task) does not yet exist in the
repo; this document is the P1.0 prerequisite that plan will consume.

## Side-by-side comparison

| Parameter | ESP32-C3 (tracker, TX) | RP2040 (coprocessor, RX) | Match? | Source |
|---|---|---|---|---|
| **Driver** | RadioLib `LR2021::begin()` | Raw SPI opcodes (`0x02`/`0x01` register access) | ✗ architectural | app_main L134; radio.cpp L20–64 |
| **Modulation / modem** | LoRa (`RADIOLIB_LR2021_PACKET_TYPE_LORA`) | **NOT SET** — chip reset default | ✗ | LR2021.cpp L25; radio.cpp `radio_init()` |
| **Frequency** | **868.0 MHz** (`CONFIG_RADIO_FREQ_MHZ_X10=8680`) | **NOT SET** | ✗ | app_main L144–146; Kconfig L91–95 |
| **Bandwidth** | **125.0 kHz** | **NOT SET** | ✗ | app_main L146; LR2021.cpp L29 |
| **Spreading factor** | **SF9** (`CONFIG_RADIO_SF=9`) | **NOT SET** | ✗ | app_main L147; Kconfig L97–101 |
| **Coding rate** | **4/7** (cr=7) | **NOT SET** | ✗ | app_main L147; LR2021.cpp L35 |
| **Sync word** | **0x12** (private network) | **NOT SET** | ✗ | app_main L148; LR2021_commands.h L404 |
| **Preamble length** | **8 symbols** | **NOT SET** | ✗ | app_main L148; LR2021.cpp L44 |
| **CRC** | **Enabled, 2 bytes** (`setCRC(2)`) | **NOT SET** | ✗ | LR2021.cpp L48 |
| **IQ inversion** | **Off** (`invertIQ(false)`) | **NOT SET** | ✗ | LR2021.cpp L51 |
| **TX power** | **+22 dBm** (`CONFIG_RADIO_TX_POWER_DBM=22`, sub-GHz PA max) | **N/A — RX only (no TX path in driver)** | — | app_main L148; Kconfig L103–107 |
| **TCXO voltage** | **0.0 V (disabled → 32 MHz XTAL)** | **NOT SET** | ✗ | app_main L149 (8th `begin()` arg) |
| **SPI clock** | ESP-IDF SPI master (HAL `EspHalC3`) | **18 MHz** (`SPI_FREQ_HZ`) | — | radio.cpp L10 |
| **Direction** | TX (telemetry) + RX (CLI `radio_recv`) | **RX only** | — | app_main L570; radio.cpp |
| **Packet type expected** | 24-byte telemetry (`TELEMETRY_SIZE`, CRC-16 app layer) | 255-byte raw frames (speed-test) | ✗ size/semantics | app_main L524; main.cpp L15 |

### What the RP2040 driver actually does

`firmware/rp2040/src/radio.cpp` contains only:
- `radio_init()` — pin setup, hardware reset pulse (RST low→high), wait-for-BUSY. **No register writes for modulation.**
- `raw_set_rx()` — issues opcode `0x02 0x0C …` (set RX). No modem/channel config precedes it.
- `raw_read_fifo()` — opcode `0x02 0x00 …`.
- `read_irq_status()` / `radio_get_rssi()` — register reads.
- IRQ is wired on DIO9 rising edge; `radio_read_packet()` times the IRQ→FIFO read path (this is a **SPI/IRQ latency benchmark**, not a comm link).

There is **no TX function** anywhere in the RP2040 driver. `main.cpp` confirms the role:
"RP2040 coprocessor firmware for **LR2021 speed test**" — it runs a 500-packet / 12 s
RX throughput benchmark and emits CSV.

## Flagged mismatches (severity)

1. **CRITICAL — RP2040 configures no modulation at all.** Every LoRa parameter is at
   chip power-on reset default. The LR2021/LR11x0 family does **not** wake up as a
   configured LoRa modem on the EU ISM band; reset defaults are unspecified for a
   working link. Packets from the ESP32 will not demodulate. **Blocks all Phase 1 RF tests.**

2. **HIGH — Modem type never selected on RP2040.** Even the LoRa packet type is not
   programmed. RadioLib's `modSetup(..., RADIOLIB_LR2021_PACKET_TYPE_LORA)` is the
   step that selects LoRa; the RP2040 never does this.

3. **HIGH — TCXO/XTAL disagreement.** ESP32 passes `tcxoVoltage=0.0` (drives the 32 MHz
   XTAL). RP2040 never touches the oscillator config. Mismatched/uncalibrated reference
   clocks cause frequency offset → RX sensitivity collapse, especially at SF9/BW125.

4. **MEDIUM — Role asymmetry (RX-only sniffer).** RP2040 cannot originate traffic, so
   any bidirectional / round-trip test in the (future) test plan must TX from ESP32.
   Throughput tests can only measure ESP32→RP2040 direction.

5. **MEDIUM — Packet semantics differ.** ESP32 sends 24-byte telemetry frames with an
   application-layer CRC-16; RP2040 expects 255-byte raw frames keyed on a 4-byte big-endian
   sequence number. The RP2040 speed test will "receive" but its seq/dedup logic won't
   match telemetry framing unless the test uses raw identical payloads.

6. **LOW — Sync word private (0x12).** Not a mismatch between the two (ESP32 uses 0x12),
   but worth recording: 0x12 = private network, **not** LoRaWAN public (0x34). Anyone
   pointing a LoRaWAN gateway at this traffic will see nothing.

## Canonical / recommended interop config

Standardize **both** platforms on these exact values (this is the "golden config" the
test plan should pin):

```
Modulation : LoRa
Frequency  : 868.0 MHz          (EU 868 ISM; alt 433.0 for sub-GHz long range)
Bandwidth  : 125.0 kHz
SF         : 9                  (balance: SF7 fast, SF12 long range)
CR         : 4/7  (cr = 7)
Sync word  : 0x12   (private)
Preamble   : 8 symbols
CRC        : 2 bytes (RadioLib default)
IQ invert  : off
TX power   : +22 dBm (sub-GHz PA max; TX side only)
TCXO       : 0.0 V  → 32 MHz XTAL (matches ESP32; keep both identical)
```

RadioLib call both sides should use:

```cpp
radio->begin(868.0, 125.0, 9, 7, 0x12, 22, 8, 0.0f);
// begin() also sets CRC=2 bytes and invertIQ(false) implicitly
```

## Recommended fix

**Option A (recommended): port RP2040 onto RadioLib.** RadioLib `^7.6.0` is already
listed in `firmware/rp2040/platformio.ini` `lib_deps` but unused. Replace the raw
register driver with:

```cpp
#include <RadioLib.h>
// ... SPI/pin setup via RadioLib's RP2040 HAL ...
radio->begin(868.0, 125.0, 9, 7, 0x12, /*rx: power N/A*/ 10, 8, 0.0f);
radio->startReceive();
```

This guarantees byte-identical modem config and removes the entire class of mismatch.
The raw SPI latency benchmark (`PacketTiming` in `radio.h`) can be preserved by timing
around `radio->readData()` if the benchmark is still wanted.

**Option B (not recommended): hand-port the config to raw opcodes.** Mirror each
`setBandwidth/setSpreadingFactor/...` write from `LR2021_config.cpp` into `radio_init()`.
Slow, error-prone, and must be re-synced whenever RadioLib updates. Only choose this if
there is a hard reason the RP2040 cannot use RadioLib (e.g. a conflict with the existing
Arduino-mbed SPI path).

Either way, **the RP2040 firmware must be changed before Phase 1 RF testing can run.**
This is filed as the actionable follow-up; the comparison itself is complete.

## Environment notes

- ESP32-C3_Mini_V1 dev board: SPI pins SCK=6/MISO=2/MOSI=7/NSS=10/BUSY=4/RST=3/DIO9=5.
- RP2040-Zero coprocessor (Board B / ADR-015): SPI0 SCK=2/MOSI=3/MISO=4/CS=5/BUSY=6/IRQ(DIO9)=7/RST=8.
- Both drive the same NiceRF LoRa2021 module (Semtech LR2021 Gen 4), so the silicon is
  identical — only the firmware configuration diverges.
