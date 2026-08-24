# ADR 020: Deprecate RadioLib LR2021 Driver — Adopt Raw 2-Byte Opcode Protocol

## Status
Accepted (2026-07-23)
**Supersedes ADR-017** (which incorrectly banned SX1280 and mandated RadioLib).

## Context

### History of the Problem

1. **ESP32 era**: We wrote a custom raw SPI driver using LR2021 native 2-byte opcodes
   (e.g., `0x0207` for SET_PACKET_TYPE). This WORKED perfectly. Source:
   `firmware/esp32-c3-flrc/main/main.cpp`.

2. **RP2040 era**: Ported the same raw SPI code to RP2040 Arduino core.
   Also WORKED. Achieved 1377 kbps end-to-end verified throughput.
   Source: `firmware/rp2040/src/flrc_raw_tx.cpp`.

3. **RadioLib attempt**: Someone introduced `rp2040-flrc-max` using RadioLib's
   LR2021 driver (`radio.beginFLRC()`). This NEVER WORKED:
   - `findChip()` expects firmware version 1.24 (0x01, 0x18)
   - Our chip returns different version bytes
   - RadioLib uses 24-bit register addressing (different from our chip's 2-byte opcode protocol)
   - Always returns error -707 or hangs indefinitely
   - The firmware was marked "UNTESTED" — because it was never successfully run

4. **Misdiagnosis**: A diagnostic was run using SX1280-style 1-byte commands
   (e.g., `0xC0` for GetStatus). The chip returned 0x21, which was interpreted
   as a valid SX1280 status. This was WRONG — the chip was responding to
   wrong-protocol commands with garbage. ADR-017 was written based on this
   incorrect diagnosis, banning SX1280 commands and mandating RadioLib.

5. **Root cause confirmed**: The chip IS an LR2021 (confirmed by module label
   "LORA2021-915", FCC ID "2RAD6S-LORA2021-915"). It speaks a 2-byte big-endian
   opcode protocol. RadioLib's LR2021 driver uses a DIFFERENT protocol
   (24-bit register addressing) that this chip does not implement.

### Why RadioLib LR2021 Fails

RadioLib v7.6.0 `modules/LR2021/LR2021.cpp`:
- `findChip()` calls `getVersion()` which uses `readRegister()` with 24-bit addresses
- Our chip does not respond to 24-bit register reads — it uses 2-byte opcodes
- `getVersion()` returns garbage → version check fails → initialization aborts
- This is a **protocol mismatch**, not a chip identification problem

### What Actually Works

The 2-byte opcode protocol, documented in:
- `docs/lr2021-spi-protocol-reference.md` (verified against TheClams Rust driver)
- `docs/lr2021-spi-command-reference.md` (verified against RadioLib source)

All opcodes verified correct. The raw SPI code achieves full functionality:
- FLRC modulation (all 8 bitrates)
- LoRa modulation (all spreading factors)
- GFSK modulation
- Sub-GHz (915 MHz) and 2.4 GHz dual-band
- TX/RX/FIFO operations
- IRQ handling (32-bit IRQ status)
- RSSI reading

## Decision

**Adopt a custom raw LR2021 SPI library** using the proven 2-byte opcode protocol.

1. **Deprecate RadioLib** for LR2021 communication on ALL platforms (ESP32, RP2040)
2. **Build a reusable `LR2021Raw` library** extracted from the proven `flrc_raw_tx.cpp` code
3. The library will expose: init, setMode (FLRC/LoRa/GFSK), setFrequency,
   setBitrate, transmit, receive, getRSSI, IRQ handling
4. Once stable, consider upstreaming fixes to RadioLib

## Protocol Specification

LR2021 uses **2-byte big-endian opcodes** (NOT 1-byte like SX1280, NOT 24-bit
register addresses like RadioLib expects):

```
Write command:  NSS LOW → wait BUSY LOW → send [opcode_hi, opcode_lo, ...payload] → NSS HIGH
Read command:   NSS LOW → wait BUSY LOW → send [opcode_hi, opcode_lo] → NSS HIGH
                → wait BUSY LOW → NSS LOW → send NOP → read [status(2) + data] → NSS HIGH
```

Key opcodes (all verified against TheClams Rust driver v0.12.0):
- `0x0200` SET_RF_FREQUENCY
- `0x0201` SET_RX_PATH (HF=1 for 2.4GHz, LF=0 for sub-GHz)
- `0x0207` SET_PACKET_TYPE (FLRC=5, LoRa=1, GFSK=2)
- `0x0248` SET_FLRC_MOD_PARAMS
- `0x0249` SET_FLRC_PACKET_PARAMS
- `0x024C` SET_FLRC_SYNCWORD
- `0x020C` SET_RX
- `0x020D` SET_TX
- `0x0122` CALIBRATE
- `0x0123` CALIB_FRONT_END (mandatory before RX)
- `0x0117` GET_AND_CLEAR_IRQ_STATUS (32-bit IRQ)
- `0x0001` READ_RX_FIFO
- `0x0002` WRITE_TX_FIFO

## Consequences

- **Pro**: Full control over SPI protocol, no dependency on broken RadioLib driver
- **Pro**: Access to ALL chip features (sub-GHz, LoRa, GFSK, FLRC, ranging)
- **Pro**: Proven working at 1377 kbps with 0% packet loss
- **Con**: Must maintain our own driver code (no upstream RadioLib updates)
- **Con**: More complex than calling `radio.beginFLRC()` — but it actually works

## For Future LLM Sessions

**DO NOT** use RadioLib for the LR2021. It does not work on our hardware.
RadioLib's LR2021 driver uses a different SPI protocol than our chip implements.

**DO NOT** write SX1280 1-byte opcodes (0x80, 0x83, 0x8A, 0x8B, etc.).
The LR2021 uses 2-byte opcodes. See the protocol reference docs.

**DO** use the `LR2021Raw` library (or raw SPI calls matching the 2-byte protocol).

**DO** reference these docs for the correct protocol:
- `docs/lr2021-spi-protocol-reference.md`
- `docs/lr2021-spi-command-reference.md`
