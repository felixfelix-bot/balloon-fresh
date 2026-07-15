# LR2021 SPI Protocol — Authoritative Reference

Sources: LR2021 Rust driver v0.12.0 (TheClams), TheClams/lr2021-apps FLRC example,
RadioLib v7.6.0. All opcodes verified against working reference implementations.

## SPI Wire Format

LR2021 uses 2-byte big-endian opcodes: `[opcode_hi, opcode_lo, ...payload]`.

Write commands: NSS LOW → wait BUSY LOW → send [opcode + payload] → NSS HIGH
Read commands: NSS LOW → wait BUSY LOW → send opcode → NSS HIGH → wait BUSY LOW
              → NSS LOW → send NOP → read [status(2) + data] → NSS HIGH

## CRITICAL: Missing Steps in Our Firmware

Our flrc_rx_raw.cpp is MISSING two MANDATORY commands that TheClams reference
calls before entering RX mode:

### 1. SET_RX_PATH (0x0201) — MISSING
For 2.4 GHz, MUST select HF path:
```
{ 0x02, 0x01, 0x01 }  // RxPath::HfPath = 1
```
Without this, radio uses default LF path → cannot receive 2.4 GHz signals.
For sub-GHz: `{ 0x02, 0x01, 0x00 }` (LfPath).

### 2. CALIB_FE (0x0123) — MISSING  
Front-end calibration (image rejection, ADC offset). REQUIRED before RX.
Datasheet: "If image rejection calibration was not done for current RF
frequency, error RXFREQ_NO_CAL_ERR is generated."
```
{ 0x01, 0x23, freq1_hi, freq1_lo, freq2_hi, freq2_lo, freq3_hi, freq3_lo }
```
TheClams calls `calib_fe(&[])` with empty freqs (uses defaults).

## Correct FLRC Init Sequence (from TheClams reference)

1. SET_RF_FREQUENCY (0x0200): freq in Hz, big-endian 32-bit
   - 2440 MHz → 0x91680000 → `{0x02, 0x00, 0x91, 0x68, 0x00, 0x00}`
2. SET_RX_PATH (0x0201): LF=0, HF=1
   - 2.4 GHz → `{0x02, 0x01, 0x01}`
3. CALIB_FE (0x0123): front-end calibration at 3 frequencies
   - `{0x01, 0x23, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00}` (defaults)
4. CALIBRATE (0x0122): calibrate all blocks
   - All defined bits = 0x5F (NOT 0x6F — bit 5 is UNDEFINED)
   - `{0x01, 0x22, 0x5F}`
5. SET_PACKET_TYPE (0x0207): FLRC=5
   - `{0x02, 0x07, 0x05}`
6. SET_FLRC_MODULATION_PARAMS (0x0248):
   - byte2 = bitrate (Br2600=0, Br2080=1, ...)
   - byte3 = (coding_rate << 4) | pulse_shape
   - CR: Cr12=0, Cr34=1, None=2, Cr23=3
   - PulseShape: None=0, Bt0p3=4, Bt0p5=5, Bt0p7=6, Bt1p0=7
   - Br2600 + None + Bt1p0 → `{0x02, 0x48, 0x00, 0x27}`
   - Br2600 + None + Bt0p5 → `{0x02, 0x48, 0x00, 0x25}`
7. SET_FLRC_SYNCWORD (0x024C): up to 3 sync words, 32-bit each
   - `{0x02, 0x4C, sw_num, sync_hi, sync_mid_hi, sync_mid_lo, sync_lo}`
   - TheClams: sw1=0xCD05CAFE, sw2=0x12345678, sw3=0x9ABCDEF0
   - 16-bit mode: send only 5 bytes (sw << 16)
8. SET_FLRC_PACKET_PARAMS (0x0249): 6 bytes
   - byte2 = (agc_pbl_len << 2) | sw_len
     - AgcPblLen: 4b=0, 8b=1, 12b=2, 16b=3, 20b=4, 24b=5, 28b=6, 32b=7
     - SwLen: None=0, 16b=1, 32b=2
   - byte3 = (sw_tx << 6) | (sw_match << 3) | (pkt_format << 2) | crc
     - SwTx: None=0, Sw1=1, Sw2=2, Sw3=3
     - SwMatch: None=0, Match1=1...Match123=7
     - PktFormat: Dynamic=0, Fixed=1
     - Crc: Off=0, CRC16=1, CRC24=2, CRC32=3
   - byte4-5 = pld_len (big-endian u16, max 511)
   - TheClams: 16b preamble, 32b syncword, SwTx=1, Match123, Dynamic, CRC24, PLD=255
     → `{0x02, 0x49, 0x0E, 0x7A, 0x00, 0xFF}`
9. SET_RX_TX_FALLBACK_MODE (0x0206): StandbyRc=1, StandbyXosc=2, Fs=3
   - TheClams uses Fs → `{0x02, 0x06, 0x03}`
10. SET_RX (0x020C): enter RX mode
    - Basic: `{0x02, 0x0C}` (2 bytes)
    - With timeout: `{0x02, 0x0C, timeout_hi, timeout_mid, timeout_lo}`
11. SET_DIO_FUNCTION (0x0112): configure DIO pin
    - `{0x01, 0x12, dio_num, (func << 4) | pull}`
    - Func: None=0, IRQ=1, RfSwitch=2, ...
    - Pull: None=0, Down=1, Up=2, Auto=3
    - DIO9 IRQ: `{0x01, 0x12, 0x09, 0x11}`
12. SET_DIO_IRQ_CONFIG (0x0115): map IRQ to DIO
    - `{0x01, 0x15, dio_num, irq[4]}`
    - RX_DONE = bit 18 = 0x00040000
    - TX_DONE = bit 19 = 0x00080000
    - DIO9 RX+TX: `{0x01, 0x15, 0x09, 0x00, 0x0C, 0x00, 0x00}`

## FIFO Access

TX FIFO write: opcode `{0x00, 0x02}` + data bytes
RX FIFO read: opcode `{0x00, 0x01}`, then read data bytes

## IRQ Bits (from Rust status.rs)
```
Bit  Name              Value
15   TIMESTAMP_STAT    0x00008000
16   ERROR             0x00010000
17   CMD_ERROR         0x00020000
18   RX_DONE           0x00040000
19   TX_DONE           0x00080000
```

## CLEAR_IRQ (0x0116): 6 bytes
`{0x01, 0x16, irq[4]}` — clear ALL = `{0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF}`

## GET_STATUS (0x0100): 2-byte request, 6-byte response
Response: [status_hi, status_lo, intr[4]]
Status byte: bits[7:4]=cmd_status, bits[3:0]=chip_mode
Chip modes: STDBY_RC=0x02, STDBY_XOSC=0x03, FS=0x04, RX=0x05, TX=0x06

## GET_AND_CLEAR_IRQ (0x0117): 2-byte request, 6-byte response
Response: [status(2), irq(4)]

## GET_ERRORS (0x0110): check calibration errors
Response includes: hf_xosc_start, lf_xosc_start, pll_lock, *calib errors,
rxfreq_no_fe_cal (no front-end calibration for this frequency)

## Comparison: Our Code vs Reference

| Step | Our Code | Reference | Match? |
|------|----------|-----------|--------|
| SET_RF_FREQUENCY | 2440e6 Hz ✓ | freq in Hz ✓ | ✓ |
| SET_RX_PATH | **MISSING** | HfPath for 2.4G | ❌ BUG |
| CALIB_FE | **MISSING** | Required for RX | ❌ BUG |
| CALIBRATE | 0x6F (bit 5 undefined) | 0x5F (defined bits only) | ⚠️ MAYBE |
| SET_STANDBY | Called (0x0128) | NOT called by reference | ⚠️ EXTRA |
| SET_PACKET_TYPE | FLRC=5 ✓ | FLRC=5 ✓ | ✓ |
| FLRC_MOD_PARAMS | 0x25 (CR_None, Bt0p5) | 0x27 (CR_None, Bt1p0) | ⚠️ DIFFERENT |
| FLRC_PACKET_PARAMS | Fixed, CRC Off | Dynamic, CRC24 | ⚠️ DIFFERENT |
| FLRC_SYNCWORD | Not verified | 0xCD05CAFE slot 1 | ⚠️ CHECK |
| SET_FALLBACK | STBY_RC=1 | Fs=3 | ⚠️ DIFFERENT |
| SET_DIO_FUNCTION | Correct format ✓ | ✓ | ✓ |
| SET_DIO_IRQ | Correct format ✓ | ✓ | ✓ |
| CLEAR_IRQ | Need to verify format | 6 bytes {opcode, irq[4]} | ⚠️ CHECK |
| SET_RX | Need to verify format | {0x02, 0x0C} | ⚠️ CHECK |

## ROOT CAUSE ANALYSIS

The CMD_ERROR (IRQ bit 17 = 0x00020000) is almost certainly caused by:

1. **MISSING SET_RX_PATH** — radio can't process 2.4 GHz commands without HF path selected
2. **MISSING CALIB_FE** — chip firmware may reject RX without front-end calibration
3. **CALIBRATE 0x6F vs 0x5F** — undefined bit 5 may trigger CMD_ERROR
4. **Wrong init order** — SET_PACKET_TYPE before SET_RF_FREQUENCY may fail

## FIX PLAN

Rewrite rawInitRadio() to match TheClams exact sequence:
1. Reset
2. SET_RF_FREQUENCY (2440 MHz)
3. SET_RX_PATH (HF=1)
4. CALIBRATE (0x5F, not 0x6F)
5. CALIB_FE (defaults)
6. SET_PACKET_TYPE (FLRC=5)
7. SET_FLRC_MODULATION (Br2600, None, Bt1p0 → 0x27)
8. SET_FLRC_SYNCWORD (sw1=0xCD05CAFE)
9. SET_FLRC_PACKET (16b preamble, 32b SW, SwTx=1, Match1, Dynamic, CRC24)
10. SET_RX_TX_FALLBACK (Fs=3)
11. SET_DIO_FUNCTION (DIO9=IRQ)
12. SET_DIO_IRQ (RX_DONE+TX_DONE)
13. CLEAR_IRQ (all)
14. SET_RX
