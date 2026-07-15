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

## ROOT CAUSE #3 — CMD_ERROR on Every TX/RX: Wrong Command Lengths (FOUND + FIXED)

After PA fix reduced CMD_ERROR rate, deeper investigation of RadioLib source
revealed three SPI command format bugs:

### Bug 4: SET_RX was 6 bytes, should be 5
```
Our code:    { 0x02, 0x0C, 0x00, 0xFF, 0xFF, 0xFF }  // 6 bytes
RadioLib:    { 0x02, 0x0C, 0xFF, 0xFF, 0xFF }         // 5 bytes
```
Extra trailing byte (0xFF) parsed as start of next command → CMD_ERROR every
time SET_RX was called → radio never entered true RX mode → 0 packets.

### Bug 5: SET_TX was 6 bytes, should be 5
```
Our code:    { 0x02, 0x0D, 0x00, 0x00, 0x00, 0x00 }  // 6 bytes
RadioLib:    { 0x02, 0x0D, 0x00, 0x00, 0x00 }         // 5 bytes
```
Same bug on TX side. Extra byte → CMD_ERROR → TX_DONE never fired.
IRQ showed 0x00020000 (CMD_ERROR) instead of 0x00080000 (TX_DONE).

### Bug 6: CALIBRATE bitmask 0x2F → 0x6F
```
Our code:    0x2F (missing bit 5 = MU + PA_OFF calibration)
RadioLib:    0x6F (CALIBRATE_ALL = all blocks)
```
Incomplete calibration. Not fatal but degraded radio performance.

### Fix Applied (commit 5b108b4)
- SET_RX: 6→5 bytes (removed trailing 0xFF)
- SET_TX: 6→5 bytes (removed trailing 0x00)
- CALIBRATE: 0x2F→0x6F on both TX and RX

## ROOT CAUSE #2 — 0 Packets: Wrong PA Select Bit (FOUND + FIXED)

TX diagnostic firmware added per-packet status/IRQ reads. Results:

```
PKT 0: preSt=0x05 irqPin=1 postSt=0x04 IRQ=0x00020000
PKT 1: preSt=0x05 irqPin=1 postSt=0x04 IRQ=0x00020000
...
TX_DONE_STATS: fired=18 timeout=982
```

- IRQ=0x00020000 = CMD_ERROR (bit 17), NOT TX_DONE (bit 19 = 0x00080000)
- 982/1000 packets failed with CMD_ERROR
- Radio accepted SET_TX but couldn't execute — wrong PA selected

Three bugs in raw TX PA config (found by comparing with RadioLib source):

### Bug 1: SET_PA_CONFIG byte0 — PA select bit WRONG
```
Our code:    0x01 (bit 0) → selects LF PA
RadioLib:    0x80 (bit 7) → selects HF PA for 2.4 GHz
```
LF PA cannot operate at 2.4 GHz. Every SET_TX command failed with CMD_ERROR.

RadioLib source: `setPaConfig()` sends `(pa << 7)` where pa=1 for highFreq.
Our code sent raw `0x01` instead of `0x80`.

### Bug 2: SET_TX_PARAMS power — not multiplied by 2
```
Our code:    TX_POWER_DBM (13)
RadioLib:    TX_POWER_DBM * 2 (26)
```
RadioLib: `setTxParams()` sends `(uint8_t)(txPower * 2)`.

### Bug 3: SEL_PA called unnecessarily
```
Our code:    SET 0x020F 0x01  (SEL_PA)
RadioLib:    does NOT call SEL_PA — SET_PA_CONFIG alone handles selection
```

### Fix Applied (commit 14be375)
- Removed SEL_PA call entirely
- Fixed PA config byte0: 0x01 → 0x80
- Fixed TX params: TX_POWER_DBM → TX_POWER_DBM * 2
- Status: BUILT, NOT YET TESTED on hardware

## Remaining Suspects (if PA fix doesn't solve 0 packets)

1. **Sync word SPI encoding** — both use 0x12AD101B, but raw SPI command
   byte ordering may differ from what chip expects
2. **RX_DONE IRQ mapping** — RX maps bit 18 to DIO9, may need verification
3. **SET_RX_PATH on both boards** — HF path config must be confirmed on RX side too

## USB Enumeration Warning

RP2040 USB ACM port assignment is NOT stable across reboots.
8332 and F242D swap ACM0/ACM2 positions on every BOOTSEL cycle.
Always check serial number before flashing — never assume ACM position.

## Files
- `firmware/rp2040/src/flrc_raw_rx.cpp` — raw SPI RX (no RadioLib)
- `firmware/rp2040/src/flrc_raw_tx.cpp` — raw SPI TX (no RadioLib)
- `firmware/rp2040/platformio.ini` — envs: rp2040-raw-rx, rp2040-raw-tx
