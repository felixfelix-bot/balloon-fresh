# LR2021 Status Byte + SPI Command Root Cause Analysis

## Date: 2026-07-15 (late session)

## FINDING 1: Status Byte is 16-bit, Not 8-bit

RadioLib source (`LR2021.cpp` line 620):
```cpp
this->mod->spiConfig.widths[RADIOLIB_MODULE_SPI_WIDTH_STATUS] = Module::BITS_16;
```

Our `rfReadStatus()` reads only 1 byte. LR2021 returns 16-bit status.
We've been seeing only the MSB (0x05). The full 16-bit status would tell us:
- Chip mode (upper byte bits 7-4)
- Command status (upper byte bits 3-0) 
- Device errors (lower byte)

**Impact**: `St=0x05` we've been reporting is incomplete. Upper nibble 5 means
FS mode per SX1280 convention. But with 16-bit we'd see the full picture.

## FINDING 2: SET_RX Format — 5 Bytes Not 6

RadioLib `setRx()` (`LR2021_cmds_chip_control.cpp` line 88):
```cpp
int16_t LR2021::setRx(uint32_t timeout) {
  uint8_t buff[] = {
    (uint8_t)((timeout >> 16) & 0xFF),
    (uint8_t)((timeout >> 8) & 0xFF),
    (uint8_t)(timeout & 0xFF),
  };
  return(this->SPIcommand(RADIOLIB_LR2021_CMD_SET_RX, true, buff, sizeof(buff)));
}
```

SET_RX = opcode (2 bytes: 0x02, 0x0C) + 3-byte timeout = **5 bytes total**.

Our code sends: `{0x02, 0x0C, 0x00, 0xFF, 0xFF, 0xFF}` = **6 bytes** (extra byte!).
The extra 0xFF is being interpreted as the start of the next command, causing CMD_ERROR.

**FIX**: `{0x02, 0x0C, 0xFF, 0xFF, 0xFF}` (3-byte timeout = 0xFFFFFF = RX continuous).

## FINDING 3: SET_TX Format — Same Issue

RadioLib `setTx()`:
```cpp
int16_t LR2021::setTx(uint32_t timeout) {
  uint8_t buff[] = {
    (uint8_t)((timeout >> 16) & 0xFF),
    (uint8_t)((timeout >> 8) & 0xFF),
    (uint8_t)(timeout & 0xFF),
  };
  return(this->SPIcommand(RADIOLIB_LR2021_CMD_SET_TX, true, buff, sizeof(buff)));
}
```

SET_TX = opcode (2 bytes: 0x02, 0x0D) + 3-byte timeout = **5 bytes total**.

Our code sends: `{0x02, 0x0D, 0x00, 0x00, 0x00, 0x00}` = **6 bytes**.
Same bug — extra trailing byte causes CMD_ERROR on every TX.

**FIX**: `{0x02, 0x0D, 0x00, 0x00, 0x00}` (timeout=0 = no timeout).

## FINDING 4: CALIBRATE_ALL = 0x6F (Correct)

RadioLib confirms `RADIOLIB_LR2021_CALIBRATE_ALL = 0x6F`.
Our code uses 0x2F (missing bits 5 and 6).
Bit 5 = CALIBRATE_PA_OFF, bit 6 = CALIBRATE_MU.

**FIX**: Use 0x6F to match RadioLib.

## FINDING 5: CALIB_FRONT_END Format

CALIB_FRONT_END takes 2-byte frequency param + HF_PATH bit (bit 15):
```
bits 15: HF path select (1=HF, 0=LF)
bits 14-0: calibration frequency (freq/4 in MHz)
```

Our code computes `feFreq = (2440/4 + 0.5) | 0x8000` = `610 | 0x8000` = `0xA62`.
That seems correct.

But RadioLib sends 10 bytes for this command while only 2 are documented.
The extra 8 bytes may be reserved/calibration config.

## FINDING 6: RX Fallback Mode Should Be STDBY_RC

RadioLib `config()`:
```cpp
state = this->setRxTxFallbackMode(RADIOLIB_LR2021_FALLBACK_MODE_STBY_RC);
```

`STDBY_RC = 0x00`. Our code uses `FS mode = 0x03`.
STDBY_RC is lower power and the correct fallback per RadioLib.

**FIX**: `{0x02, 0x06, 0x00}` (STDBY_RC, not 0x03).

## FINDING 7: RadioLib RX Entry Sequence (stageMode)

Before entering RX, RadioLib does:
1. `getPacketType()` — verify FLRC mode active
2. `setRxPath(HF, gainMode)` — set HF path + gain
3. `setDioIrqConfig(dioNum, irqMask)` — map RX_DONE to DIO
4. `clearIrqState(ALL)` — clear all IRQs
5. `setRx(timeout)` — enter RX

Our code does setRxPath in init (step 2 OK) but never re-calls it before RX.
This may be OK if the path persists.

## FINDING 8: RadioLib TX Entry Sequence (launchMode)

Before TX, RadioLib does:
1. `setRfSwitchState(MODE_TX)` — hardware RF switch (we don't have one)
2. `setTx(TIMEOUT_NONE)` — start TX
3. Wait for BUSY to go low (PA ramp up done)

Our code doesn't wait for BUSY after SET_TX. We wait for IRQ (DIO9).
The BUSY-low wait happens after SET_TX, before the chip starts transmitting.

## SUMMARY OF BUGS

| Bug | Our Code | Correct (RadioLib) | Impact |
|-----|----------|-------------------|--------|
| SET_RX length | 6 bytes | 5 bytes | CMD_ERROR, never enters RX |
| SET_TX length | 6 bytes | 5 bytes | CMD_ERROR, TX may not emit RF |
| CALIBRATE bitmask | 0x2F | 0x6F | Incomplete calibration |
| Fallback mode | 0x03 (FS) | 0x00 (STDBY_RC) | Wrong power state |
| Status byte width | 8-bit | 16-bit | Wrong status decoding |

## ROOT CAUSE

**SET_RX and SET_TX are 5-byte commands, not 6.** The extra trailing byte in our
implementation is parsed as the start of a new command, triggering CMD_ERROR (bit 17).
This is why IRQ shows 0x00020000 on every packet.

For RX: the extra byte prevents entering RX mode → 0 packets received.
For TX: the extra byte triggers CMD_ERROR but TX may still partially work via
the BUSY pin going low, explaining the inconsistent "fired" counts.
