# TASK-P4-4: LR2021 LoRa Modulation Parameter Encoding

**Date:** 2026-07-23  
**Status:** ✅ DOCUMENTED  
**Method:** Code analysis + cross-reference against RadioLib v7.6.0 LR2021 driver  

---

## Summary

This document specifies the exact byte encoding for SET_LORA_MODULATION_PARAMS
(opcode `0x0220`) on the Semtech LR2021 chip, as used in the proven working firmware.

---

## Command Format

```
Opcode: SET_LORA_MODULATION_PARAMS = 0x0220
SPI frame: [0x02, 0x20, byte0, byte1]
```

| Byte | Bits | Field | Description |
|------|------|-------|-------------|
| byte0 | [7:4] | SF | Spreading factor (direct value: 5–12) |
| byte0 | [3:0] | BW | Bandwidth code |
| byte1 | [7:4] | CR | Coding rate |
| byte1 | [3:0] | LDRO | Low Data Rate Optimize |

### Encoding Formula (from firmware + RadioLib)

From `firmware/rp2040/src/lora_range_tx.cpp` (lines 224–227):
```cpp
uint8_t byte0 = ((sf & 0x0F) << 4) | (bwCode & 0x0F);
uint8_t byte1 = ((cr & 0x0F) << 4) | (ldro & 0x01);
uint8_t cmd[] = { 0x02, 0x20, byte0, byte1 };
```

From RadioLib `LR2021_cmds_lora.cpp` (line 23):
```cpp
uint8_t buff[] = { (uint8_t)(((sf & 0x0F) << 4) | (bw & 0x0F)),
                   (uint8_t)(((cr & 0x0F) << 4) | this->ldrOptimize) };
```

**These are identical.** Our raw firmware matches RadioLib's LR2021 driver exactly.

---

## Field Encodings

### Spreading Factor (SF) — Upper Nibble of byte0

The SF value is placed directly into the upper nibble. No remapping.

| SF | Hex nibble | byte0 contribution |
|----|-----------|-------------------|
| SF5 | 0x5 | 0x5_ |
| SF6 | 0x6 | 0x6_ |
| SF7 | 0x7 | 0x7_ |
| SF8 | 0x8 | 0x8_ |
| SF9 | 0x9 | 0x9_ |
| SF10 | 0xA | 0xA_ |
| SF11 | 0xB | 0xB_ |
| SF12 | 0xC | 0xC_ |

Source: RadioLib `LR2021_commands.h` lines 371–382 (BW codes), and firmware code.

### Bandwidth (BW) — Lower Nibble of byte0

| Bandwidth | BW Code | Source |
|-----------|---------|--------|
| 203.125 kHz | 0x0D | `RADIOLIB_LR2021_LORA_BW_203` |
| 406.25 kHz | 0x0E | `RADIOLIB_LR2021_LORA_BW_406` |
| **812.5 kHz** | **0x0F** | `RADIOLIB_LR2021_LORA_BW_812` |
| 1000 kHz | 0x07 | `RADIOLIB_LR2021_LORA_BW_1000` |
| 500 kHz | 0x06 | `RADIOLIB_LR2021_LORA_BW_500` |
| 250 kHz | 0x05 | `RADIOLIB_LR2021_LORA_BW_250` |
| 125 kHz | 0x04 | `RADIOLIB_LR2021_LORA_BW_125` |
| 62.5 kHz | 0x03 | `RADIOLIB_LR2021_LORA_BW_62` |
| 41.67 kHz | 0x0A | `RADIOLIB_LR2021_LORA_BW_41` |
| 31.25 kHz | 0x02 | `RADIOLIB_LR2021_LORA_BW_31` |

Firmware BW helper (`lora_range_tx.cpp` lines 81–88):
```cpp
static uint8_t bwKhzToCode(int khz) {
    switch (khz) {
        case 203: return 0x0D;
        case 406: return 0x0E;
        case 812: return 0x0F;
        default:  return 0x0F;  // default to 812.5
    }
}
```

### Coding Rate (CR) — Upper Nibble of byte1

| Coding Rate | CR Code | Internal `cfgCr` in firmware |
|-------------|---------|------------------------------|
| **4/5** | **0x01** | **1** |
| 4/6 | 0x02 | 2 |
| 4/7 | 0x03 | 3 |
| 4/8 | 0x04 | 4 |
| 4/5 + long interleaver | 0x05 | — |
| 4/6 + long interleaver | 0x06 | — |
| 4/7 + long interleaver | 0x07 | — |

Source: RadioLib `LR2021_commands.h` lines 383–389.

Note: In the firmware, `cfgCr` is an internal representation (1=4/5, 2=4/6, 3=4/7, 4=4/8).
These happen to match the chip's CR codes exactly, so `(cfgCr & 0x0F) << 4` produces the
correct encoding. The serial command `CR <n>` takes values 5–8 and converts: `cfgCr = n - 4`.

### Low Data Rate Optimize (LDRO) — Lower Nibble of byte1

| Value | Meaning |
|-------|---------|
| 0x00 | LDRO disabled |
| 0x01 | LDRO enabled |

Source: RadioLib `LR2021_commands.h` lines 390–391.

**Auto-enable logic** (from firmware lines 219–222):
```cpp
uint8_t ldro = 0;
float symTimeMs = (float)(1UL << sf) / (float)(bwCode == 0x0D ? 203125 :
                            bwCode == 0x0E ? 406250 : 812500) * 1000.0f;
if (symTimeMs > 16.0f) ldro = 1;
```

LDRO is enabled when symbol time exceeds 16 ms (per Semtech datasheet / RadioLib `ldroAuto` logic).

---

## Lookup Table: Common Configurations

### CR=4/5 (0x01), LDRO=off (0x00) → byte1 = 0x10

| SF | BW | byte0 | byte1 | Full SPI frame |
|----|-----|-------|-------|----------------|
| SF7 | 812 kHz | `0x7F` | `0x10` | `{0x02, 0x20, 0x7F, 0x10}` |
| SF7 | 406 kHz | `0x7E` | `0x10` | `{0x02, 0x20, 0x7E, 0x10}` |
| SF7 | 203 kHz | `0x7D` | `0x10` | `{0x02, 0x20, 0x7D, 0x10}` |
| SF9 | 812 kHz | `0x9F` | `0x10` | `{0x02, 0x20, 0x9F, 0x10}` |
| SF9 | 406 kHz | `0x9E` | `0x10` | `{0x02, 0x20, 0x9E, 0x10}` |
| SF9 | 203 kHz | `0x9D` | `0x10` | `{0x02, 0x20, 0x9D, 0x10}` |
| SF12 | 812 kHz | `0xCF` | `0x10` | `{0x02, 0x20, 0xCF, 0x10}` |
| SF12 | 406 kHz | `0xCE` | `0x11` | `{0x02, 0x20, 0xCE, 0x11}` |
| SF12 | 203 kHz | `0xCD` | `0x11` | `{0x02, 0x20, 0xCD, 0x11}` |

### LDRO Threshold Analysis

| SF | BW | Symbol Time | LDRO |
|----|-----|-------------|------|
| SF7 | 812 kHz | 0.158 ms | off |
| SF9 | 812 kHz | 0.630 ms | off |
| SF12 | 812 kHz | 5.04 ms | off |
| SF12 | 406 kHz | 10.08 ms | off |
| **SF12** | **203 kHz** | **20.17 ms** | **on** |
| SF11 | 203 kHz | 10.09 ms | off |
| SF10 | 203 kHz | 5.04 ms | off |

LDRO is only required when symbol time > 16 ms, which in practice means **SF12 @ 203 kHz**
(or lower SF at narrower bandwidths not available on this chip).

---

## CR=4/8 (Maximum Robustness) Variants

When CR=4/8 (code 0x04), byte1 = `(0x04 << 4) | ldro = 0x40` (LDRO off) or `0x41` (LDRO on).

| SF | BW | byte0 | byte1 | Full SPI frame |
|----|-----|-------|-------|----------------|
| SF7 | 812 kHz | `0x7F` | `0x40` | `{0x02, 0x20, 0x7F, 0x40}` |
| SF9 | 812 kHz | `0x9F` | `0x40` | `{0x02, 0x20, 0x9F, 0x40}` |
| SF12 | 812 kHz | `0xCF` | `0x40` | `{0x02, 0x20, 0xCF, 0x40}` |
| SF12 | 203 kHz | `0xCD` | `0x41` | `{0x02, 0x20, 0xCD, 0x41}` |

---

## Comparison: LR2021 vs SX128x Encoding

| Aspect | LR2021 | SX128x |
|--------|--------|--------|
| **Opcode** | `0x0220` (2-byte) | `0x8B` (1-byte) |
| **Payload** | 2 bytes (combined nibbles) | 3 bytes (separate fields) |
| **SF encoding** | `(sf & 0x0F) << 4` in byte0 upper nibble | Same: `sf << 4` as byte 0 |
| **BW encoding** | Nibble in byte0 lower nibble: 812kHz=`0x0F` | Separate byte: 812.5kHz=`0x18` |
| **CR encoding** | Nibble in byte1 upper nibble: 4/5=`0x01` | Separate byte: 4/5=`0x01` |
| **LDRO** | Nibble in byte1 lower nibble | Not in modulation params (register write instead) |

**Key difference:** BW codes are completely different between chips despite the same nominal bandwidth.
The LR2021 uses compact nibble-friendly codes (0x0D–0x0F for 203–812 kHz), while the SX128x
uses non-contiguous byte values (0x0A–0x34). **Do not interchange.**

---

## Default Configuration Used in Working Firmware

The LoRa range test firmware defaults to:
```
SF=7, BW=812 kHz, CR=4/5, LDRO=off
→ SPI frame: {0x02, 0x20, 0x7F, 0x10}
```

This was verified to produce working LoRa TX/RX with RSSI readback.

---

## Source Files Referenced

| File | Role |
|------|------|
| `firmware/rp2040/src/lora_range_tx.cpp` | LoRa TX (proven working) |
| `firmware/rp2040/src/lora_range_rx.cpp` | LoRa RX (proven working) |
| RadioLib `LR2021_commands.h` | Opcode + field constant definitions |
| RadioLib `LR2021_cmds_lora.cpp` | Reference implementation of `setLoRaModulationParams()` |
| RadioLib `SX128x.h` | SX128x comparison (different chip family) |
| RadioLib `SX128x.cpp` | SX128x `setModulationParams()` for comparison |
