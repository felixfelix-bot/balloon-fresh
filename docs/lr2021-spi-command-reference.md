# LR2021 SPI Command Reference — Cross-Referenced Analysis

## Date: 2026-07-15
## Sources: RadioLib v7.6.0 source, TheClams/lr2021-apps reference, docs.rs/lr2021

---

## CRITICAL BUGS FOUND IN OUR RAW SPI FIRMWARE

### BUG #1 (CRITICAL — ROOT CAUSE OF 0 PACKETS): Missing SET_RX_PATH

**Our code:** No SET_RX_PATH command sent.
**RadioLib:** Calls `setRxPath()` during frequency setting for HF path.
**TheClams:** `lr2021.set_rx_path(RxPath::HfPath, RxBoost::Off)`

At 2.4 GHz, the radio MUST be told to use the HF RX path. Without this,
the radio listens on the LF (sub-GHz) path and will NEVER receive 2.4 GHz FLRC.

**Fix:** Add after frequency set:
```c
// SET_RX_PATH (0x0201): HF path, no boost
{ uint8_t cmd[] = { 0x02, 0x01, 0x01, 0x00 }; rfWriteCmd(cmd, 4); }
// byte0: 0x01 = HF path (0x00 = LF)
// byte1: 0x00 = no boost (0x04 = HF boost)
```

### BUG #2 (CRITICAL): Missing CALIB_FRONT_END

**Our code:** Only sends CALIBRATE (0x0122, all blocks).
**RadioLib:** Calls `calibrateFrontEnd()` EVERY TIME frequency changes >20 MHz.
**TheClams:** `lr2021.calib_fe(&[])`

RadioLib retries up to 10 times. Without front-end calibration, the image
rejection filter is not tuned for 2.4 GHz.

**Fix:** Add CALIB_FRONT_END (0x0123) after frequency set:
```c
// CALIB_FRONT_END (0x0123)
// For 2.4 GHz: freq/4 = 610, set HF_PATH bit (bit 15)
// frequencies[0] = (uint16_t)((2440.0/4.0)+0.5) | 0x8000 = 0x8262
{ uint8_t cmd[] = { 0x01, 0x23, 0x82, 0x62, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 }; rfWriteCmd(cmd, 10); }
```

### BUG #3 (MAJOR): Wrong PA Config for HF

**Our code:** `{0x02, 0x02, 0x01, 0x00, 0x60, 0x07, 0x10}`
**RadioLib:** `setPaConfig(highFreq=true, ...)` — different param layout for HF

For 2.4 GHz, RadioLib sets highFreq=true, which changes PA config byte[0] to 0x01.
Our PA config may be selecting the LF PA (wrong amplifier for 2.4 GHz).

**Fix:** RadioLib's setPaConfig for HF sends:
```c
// SEL_PA (0x020F): Select high-power PA
{ uint8_t cmd[] = { 0x02, 0x0F, 0x01 }; rfWriteCmd(cmd, 3); }
// SET_PA_CONFIG (0x0202): HF PA
{ uint8_t cmd[] = { 0x02, 0x02, 0x01, 0x00, 0x60, 0x07, 0x10 }; rfWriteCmd(cmd, 7); }
// byte0=0x01 = high-power PA selected
```

### BUG #4 (MINOR): Missing Clear Errors Before Init

**Our code:** No clear errors command before calibration.
**RadioLib:** Calls `clearErrors()` before calibration in setTCXO().

**Fix:** Add CLEAR_ERRORS (0x0111) before calibrate:
```c
{ uint8_t cmd[] = { 0x01, 0x11, 0x00, 0x00 }; rfWriteCmd(cmd, 4); }
```

---

## SPI COMMAND VERIFICATION: LR2021 vs SX1280

The user suspected SX1280 commands might be mixed in. Here's the full comparison:

### Confirmed CORRECT LR2021 commands (NOT SX1280):

| Command | Our Opcode | RadioLib Opcode | Match? |
|---------|-----------|-----------------|--------|
| SET_STANDBY | 0x0128 | 0x0128 | ✅ |
| SET_FS | — | 0x0129 | (not used) |
| SET_RX | 0x020C | 0x020C | ✅ |
| SET_TX | 0x020D | 0x020D | ✅ |
| CALIBRATE | 0x0122 | 0x0122 | ✅ |
| SET_PACKET_TYPE | 0x0207 | 0x0207 | ✅ |
| SET_RF_FREQUENCY | 0x0200 | 0x0200 | ✅ |
| SET_FLRC_MOD_PARAMS | 0x0248 | 0x0248 | ✅ |
| SET_FLRC_PACKET_PARAMS | 0x0249 | 0x0249 | ✅ |
| SET_FLRC_SYNCWORD | 0x024C | 0x024C | ✅ |
| SET_PA_CONFIG | 0x0202 | 0x0202 | ✅ |
| SET_TX_PARAMS | 0x0203 | 0x0203 | ✅ |
| SET_DIO_FUNCTION | 0x0112 | 0x0112 | ✅ |
| SET_DIO_IRQ_CONFIG | 0x0115 | 0x0115 | ✅ |
| CLEAR_IRQ | 0x0116 | 0x0116 | ✅ |
| GET_AND_CLEAR_IRQ_STATUS | 0x0117 | 0x0117 | ✅ |
| WRITE_TX_FIFO | 0x0002 | 0x0002 | ✅ |
| READ_RX_FIFO | 0x0001 | 0x0001 | ✅ |
| CLEAR_TX_FIFO | 0x011F | 0x011F | ✅ |
| CLEAR_RX_FIFO | 0x011E | 0x011E | ✅ |
| SET_RX_TX_FALLBACK | 0x0206 | 0x0206 | ✅ |

### SX1280 vs LR2021 comparison (different chips!):

| Function | SX1280 | LR2021 | Same? |
|----------|--------|--------|-------|
| SET_TX | 0x0083 | 0x020D | ❌ DIFFERENT |
| SET_RX | 0x0082 | 0x020C | ❌ DIFFERENT |
| SET_PACKET_TYPE | 0x008A | 0x0207 | ❌ DIFFERENT |
| SET_MODULATION | 0x008B | 0x0248 | ❌ DIFFERENT |
| SET_PACKET_PARAMS | 0x008C | 0x0249 | ❌ DIFFERENT |
| GET_RX_STATUS | 0x0089 | 0x024B | ❌ DIFFERENT |
| IRQ bits | 16-bit | 32-bit | ❌ DIFFERENT |
| SPI status width | 8-bit | 16-bit | ❌ DIFFERENT |

**VERDICT: No SX1280 command contamination.** All our opcodes match LR2021 correctly.
The SPI opcodes were right all along — the missing init steps were the problem.

---

## CORRECT INIT SEQUENCE (from TheClams reference + RadioLib source)

### TheClams flrc_txrx.rs init (for 900 MHz, adapted for 2.4 GHz):

```
1. set_rf(2_400_000_000)          → SET_RF_FREQUENCY with freq_Hz
2. set_rx_path(HfPath, Off)       → SET_RX_PATH: HF for 2.4 GHz  ← WE MISSED THIS
3. calib_fe()                     → CALIB_FRONT_END              ← WE MISSED THIS
4. set_pa_hf()                    → SEL_PA + SET_PA_CONFIG for HF ← WRONG IN OURS
5. set_tx_params(0, Ramp16u)      → SET_TX_PARAMS: power + ramp
6. set_packet_type(Flrc)          → SET_PACKET_TYPE: 0x05
7. set_flrc_modulation(Br2600, None, Bt1p0) → SET_FLRC_MOD_PARAMS
8. set_flrc_syncword(1, 0xCD05CAFE, true) → SET_FLRC_SYNCWORD
9. set_flrc_packet(params)        → SET_FLRC_PACKET_PARAMS
10. set_fallback(Fs)              → SET_RX_TX_FALLBACK: 0x03 (FS mode)
11. set_rx(0xFFFFFFFF, true)      → SET_RX: continuous
12. set_dio_irq(Dio7, TX_DONE|RX_DONE) → SET_DIO_IRQ_CONFIG
```

### Key differences from TheClams vs our code:

| Setting | TheClams | Our Code | Issue |
|---------|----------|----------|-------|
| Frequency | 900 MHz | 2440 MHz | Different band |
| RX Path | LFPath (for 900M) | NONE SET | **MUST set HFPath** |
| PA | PA LF (for 900M) | Hardcoded | **MUST use PA HF** |
| Coding Rate | None (0x00) | CR_1_0 (0x02) | Different — both valid |
| Pulse Shape | Bt1p0 (0x07) | Bt0_5 (0x05) | Different — both valid |
| CRC | Crc24 | Disabled | Different — both valid |
| Fallback | Fs (0x03) | STBY_RC (0x01) | Minor — Fs better for throughput |
| DIO pin | DIO7 | DIO9 | Both valid if wiring matches |
| Sync word | 0xCD05CAFE | 0x12AD101B | **Must match between TX/RX** |
| Front-end cal | YES | NO | **CRITICAL — must add** |

---

## IRQ BIT MAP (32-bit, from RadioLib LR2021_commands.h)

| Bit | Name | Description |
|-----|------|-------------|
| 0 | RX_FIFO | Rx FIFO threshold reached |
| 1 | TX_FIFO | Tx FIFO threshold reached |
| 5 | PREAMBLE_DETECTED | Preamble detected |
| 6 | SYNCWORD_VALID | Sync word valid |
| 16 | ERROR | Error other than command error |
| 17 | CMD_ERROR | Command error |
| 18 | RX_DONE | Packet received |
| 19 | TX_DONE | Packet transmitted |
| 21 | TIMEOUT | Rx or Tx timeout |
| 22 | CRC_ERROR | CRC error |
| 23 | LEN_ERROR | Length error |

Our observed IRQ=0x00230000 = bits 17+18+21 = CMD_ERROR + RX_DONE + TIMEOUT
This means the radio is getting command errors (from missing init steps).

---

## FLRC MODULATION PARAMS BYTE FORMAT

```
Opcode: 0x0248
Byte 0: brBw (bitrate/bandwidth)
  0x00 = 2600 kbps / 2666 kHz
  0x01 = 2080 kbps / 2222 kHz
  0x02 = 1300 kbps / 1333 kHz
  etc.
Byte 1: (cr << 4) | (pulseShape & 0x0F)
  CR:     0x00=1/2, 0x01=3/4, 0x02=1(uncoded), 0x03=2/3
  Shape:  0x05=BT0.5, 0x07=BT1.0, 0x03=RRC0.4

Our value: 0x25 = CR_1_0 (0x02<<4) | BT_0_5 (0x05) ✅ CORRECT
```

## FLRC PACKET PARAMS BYTE FORMAT

```
Opcode: 0x0249
Byte 0: ((agcPreambleLen & 0x0F) << 2) | (syncWordLen / 2)
Byte 1: ((syncWordTx & 0x03) << 6) | ((syncMatch & 0x07) << 3) | (fixedLen << 2) | (crc & 0x03)
Byte 2-3: payloadLen (big-endian)
```

## FLRC SYNCWORD FORMAT

```
Opcode: 0x024C
Byte 0: syncWordNum (1-3)
Byte 1-4: 32-bit sync word (MSB first)
```

Note: TheClams Rust crate sends an extra "enable" byte. RadioLib does NOT.
Our format matches RadioLib (5 bytes data). This may cause issues if the
LR2021 firmware expects the enable byte.

---

## SUMMARY OF REQUIRED FIXES (priority order)

1. **ADD SET_RX_PATH (0x0201)** — HF path for 2.4 GHz. Without this, RX never works.
2. **ADD CALIB_FRONT_END (0x0123)** — Image rejection calibration for 2.4 GHz.
3. **FIX PA CONFIG** — Ensure HF PA is selected, not LF.
4. **ADD CLEAR_ERRORS (0x0111)** — Before calibration.
5. **CHANGE FALLBACK MODE** — Use FS (0x03) instead of STBY_RC (0x01).
6. **VERIFY SYNC WORD** — Both TX and RX MUST use same sync word.
7. **ADD SEL_PA (0x020F)** — Explicitly select high-power PA before PA config.

All SPI opcodes are verified correct for LR2021. No SX1280 contamination.
