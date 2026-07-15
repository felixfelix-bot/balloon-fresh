# FLRC Raw SPI Test Results — 2026-07-15

## Summary

Raw SPI firmware (no RadioLib) successfully initializes LR2021 radio.
TX confirmed sending packets. RX enters RX mode (Status=0x05).
0 packets received during TX→RX test.

## Root Cause of RadioLib -707

RadioLib `beginFLRC()` returns -707 (RADIOLIB_ERR_SPI_CMD_FAILED).

RadioLib's `modSetup()` sequence:
1. `mod->init()` (SPI bus)
2. `findChip()` — calls `reset()` + `getVersion()` in loop (expects FW 1.18)
3. `standby()`
4. `setTCXO()` — skipped when tcxoVoltage=0
5. `config()` — clearIrq, setDioFunction, calibrate, setPacketType

**Missing steps that RadioLib does NOT do:**
- `CLEAR_ERRORS` (0x0111) — must be sent BEFORE any other command after reset
- `SET_RX_PATH` (0x0201, byte=0x01) — mandatory for 2.4 GHz HF path
- `CALIB_FRONT_END` (0x0123) — image rejection calibration for 2.4 GHz

Without CLEAR_ERRORS, the chip has stale error flags from reset and rejects
subsequent commands → status byte reports CMD_FAIL → -707.

The raw SPI firmware sends CLEAR_ERRORS first, then all commands succeed.

## Also: RADIOLIB_ASSERT bug in findChip()

`findChip()` returns `bool` but uses `RADIOLIB_ASSERT(state)` which returns
`int16_t`. If `getVersion()` fails with -707, the assert's `return(STATEVAR)`
inside a `bool` function converts -707 to `true`. So findChip reports "chip found"
even when SPI communication failed. The -707 then propagates from `standby()` or
`config()` in `modSetup()`.

## Verified Test Results

### TX firmware on 8332 (raw SPI, no RadioLib)
```
INIT Status=0x04 IRQ=0x00020000
RADIO_INIT_OK
TX_START count=1000 pktSize=255
TX 0/1000 ... TX 900/1000
TX sent: 1000  Elapsed: 643 ms  TX THROUGHPUT: 3172.6 kbps
RESULT_TX,sent=1000,elapsed_ms=643,throughput_kbps=3172.6
```
Second run: 1507ms, 1353.7 kbps (first run includes cold-start overhead).

### RX firmware on 8332 (raw SPI, no RadioLib)
```
Status=0x05  IRQ=0x00230020
radio: INIT  listen=12000ms  silence=3000ms
```
Radio enters RX mode successfully.

### TX→RX simultaneous test
```
RX_START → 12s listen → RX_DONE timeout
Received: 0 (unique 0, dup 0)
THROUGHPUT: 0.0 kbps
```
**0 packets received.** TX sends, RX listens, nothing arrives.

## Why 0 Packets — Open Questions

1. **Sync word format mismatch?** Both use 0x12AD101B in source, but raw SPI
   sync word command format may encode differently than expected.
2. **F242D TX not emitting RF?** SET_TX command accepted, TX_DONE fires, but
   PA/antenna path may not be configured correctly for 2.4 GHz.
3. **Different LR2021 modules?** 8332 and F242D may have different hardware
   revisions or antenna connections.
4. **DIO9 IRQ mapping?** TX maps TX_DONE (bit 19) to DIO9. RX maps RX_DONE
   (bit 18) to DIO9. If the DIO mapping is wrong, RX never sees the IRQ.
5. **CRC mismatch?** Both set crc=0, but RadioLib's default sync word
   ({0x2D, 0x01, 0x4B, 0x1D}) differs from raw firmware sync (0x12AD101B).
   Since both TX and RX use the same raw sync word, this should match —
   unless one board still has old RadioLib firmware cached.

## Next Debug Steps

1. Flash TX to 8332, RX to F242D — reverse roles to test if F242D can receive
2. Add raw SPI status read AFTER SET_TX to verify TX_DONE actually fires
3. Check antenna: LR2021 pin 10 (2.4G) must have antenna connected on BOTH boards
4. Add GET_RX_BUFFER_STATUS read before FIFO read to check if any bytes arrived
5. Lower frequency to Sub-GHz (868 MHz, pin 9) to test different RF path
6. Try loopback: same board TX→RX to verify radio works at all

## USB Enumeration Warning

RP2040 USB ACM port assignment is NOT stable across reboots.
8332 and F242D swap ACM0/ACM2 positions on every BOOTSEL cycle.
Always check serial number before flashing — never assume ACM position.

## Files
- `firmware/rp2040/src/flrc_raw_rx.cpp` — raw SPI RX (no RadioLib)
- `firmware/rp2040/src/flrc_raw_tx.cpp` — raw SPI TX (no RadioLib)
- `firmware/rp2040/platformio.ini` — envs: rp2040-raw-rx, rp2040-raw-tx
