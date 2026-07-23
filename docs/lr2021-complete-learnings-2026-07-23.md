# LR2021 FLRC Complete Learnings — 2026-07-23

This document captures all technical learnings from the LR2021 FLRC range-testing
effort. It supersedes earlier learning docs dated 2026-07-16.

## 1. The FIFO Race Bug (SOLVED)

### Symptom
RX received packets but sequence numbers were garbage. TX sends seq 0, 1, 2, 3...
RX read random 32-bit values (824152753, 2611017220, etc.). Persisted across 8+
debugging sessions.

### Root Cause
RX polled IRQ status via SPI (`rfReadIrqStatus()`). This is a 3-byte SPI
transaction taking ~50 microseconds. At 2600 kbps FLRC, packets arrive every
~400 microseconds. During the SPI IRQ read, the chip would start receiving the
next packet and overwrite the FIFO buffer before firmware finished reading.

### Diagnosis Method
Added hex dump of first 16 bytes of each received packet (`RX_DEBUG_HEX` build flag).
Result:
- PKT[2] had VALID data: `00 00 00 00 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F`
  (seq=0, payload bytes incrementing from 4)
- PKT[0,1] had garbage (FIFO already overwritten)
- PKT[3,4] showed mid-buffer reads (same issue)

### Fix
Replace SPI IRQ polling with GPIO register read:
```cpp
// OLD (slow, ~50us): SPI transaction
uint32_t irq = rfReadIrqStatus();
if (!(irq & 0x00040000)) continue;

// NEW (fast, nanoseconds): GPIO register read
uint32_t irqMask = 1UL << PIN_IRQ;
if (!(sio_hw->gpio_in & irqMask)) continue;
```

TX firmware already used GPIO polling successfully. RX was the only holdout.

### Result
- 0% PER at 12.5 dBm
- 622 packets received (from 500 sent + adjacent burst bleed)
- Correct sequence numbers 0-499
- DEADBEEF end marker caught correctly
- 260 kbps throughput

Commit: 3dcddaf

### Lesson
**Never poll radio IRQ via SPI in a high-throughput RX loop.** The SPI transaction
itself takes long enough for the next packet to arrive and overwrite the FIFO.
Always use GPIO pin polling (DIO9 → RP2040 GPIO register). This is a fundamental
timing constraint of the LR2021 at 2600 kbps.

## 2. PA Discontinuity (LR2021 Power Amplifier)

### Finding
The LR2021 power amplifier is binary, not proportional:

| Register Code | Requested Power | Actual RF Behavior |
|---------------|----------------|-------------------|
| 0-24          | 0.0-12.0 dBm   | PA bypassed. Direct output. All identical. |
| 25            | 12.5 dBm       | PA enabled. ~43 dB RSSI jump. |

### Evidence (Indoor, ~30cm)
- 0.0 dBm: 481/500 rx, 3.8% PER, 1463 kbps
- 3.0 dBm: 477/500 rx, 4.6% PER, 1457 kbps
- 6.0 dBm: 481/500 rx, 3.8% PER, 1463 kbps
- 9.0 dBm: 478/500 rx, 4.0% PER, 1458 kbps
- 12.0 dBm: 478/500 rx, 4.2% PER, 1457 kbps
- 12.5 dBm: 622/500 rx, ~0% PER, 260 kbps (continuous mode)

PER is flat across 0-12 dBm because the PA is off. Requesting lower power just
attenuates the baseband, not the RF output.

### Implication
For balloon use: always use 12.5 dBm (PA on) for maximum range. There is no
benefit to lower power settings — they just waste the PA opportunity. For power
saving, use TX duty cycling (burst + sleep) instead of power reduction.

### Power Register Code
```cpp
// rfSetTxPower implementation
uint8_t powerRaw = (uint8_t)(dbm * 2);  // 0.5 dBm steps
uint8_t cmd[] = { 0x02, 0x03, powerRaw, 0x04 };
// dbm=12.5 → powerRaw=25 → PA enabled
// dbm=12.0 → powerRaw=24 → PA bypassed
```

## 3. RSSI Register Unreliable

Register 0x022A always returns -127 dBm at indoor range. The RSSI value is
either not populated in FLRC mode or requires a different read sequence.

Previous sessions reported -60 dBm at 12.5 dBm and -103 dBm at lower power,
but these measurements may have been from a different register or a corrupted
SPI read. Current status: **RSSI measurement does not work.**

Needs investigation: Semtech datasheet references RSSI at different register
addresses for different modes. May need to read during RX (not after), or use
a packet status read instead.

## 4. SPI Interface

### Working Configuration
- SPI frequency: 20 MHz (works fine for TX FIFO write)
- SPI frequency: 10 MHz (tested for RX, same results as 20 MHz)
- Mode: SPI_MODE0, MSBFIRST
- FIFO write: single-batch transfer (CS held low for entire packet)
- FIFO read: same, opcode 0x0001 followed by data bytes

### Not a Bottleneck
SPI frequency was suspected as cause of seq corruption. Reduced to 10 MHz
with no change. The real bottleneck was the IRQ polling method, not SPI speed.

## 5. Packet Size

- 127 bytes: max reliable FLRC payload. Matches proven throughput firmware.
- 144 bytes: caused issues in earlier sessions (not the root cause, but abandoned).
- 255 bytes: proven TX firmware used 255B TX with 127B RX. Chip handles mismatch
  by truncating. Works but wasteful.

Current standard: 127 bytes for both TX and RX.

## 6. FLRC Modem Configuration (Verified Working)

```
Packet type:    FLRC (0x05)
Frequency:      2440.0 MHz
Bitrate:        2600 kbps (brBw=0x00)
Coding rate:    4/5 (CR field=0x02, BT=0x05 → modParam byte=0x25)
Preamble:       8 symbols (index 2)
Sync word:      0x12 0xAD 0x10 0x1B (4 bytes, match=1, tx=1)
Packet type:    Fixed length, no CRC, no header
Payload size:   127 bytes
```

All init parameters identical between TX and RX. Verified byte-by-byte.

## 7. Board Recovery

### BOOTSEL Trigger Methods (in order of preference)
1. **1200 baud serial**: Open port at 1200 baud, close. Works ~60% of time.
2. **ESP32 GPIO loop trigger**: Flash loop firmware to paired ESP32, it pulses
   RUN pin every 5s. Works when 1200 baud fails.
3. **Physical BOOTSEL button**: Hold BOOTSEL while plugging USB. Always works
   but requires physical access.

### Port Swapping
Ports (ttyACM0/2) swap when boards enter BOOTSEL mode and reboot. ALWAYS verify
board identity by serial number:
```bash
udevadm info -q property /dev/ttyACMX | grep ID_SERIAL_SHORT
```

### CDC Port Death
If radio init hangs (BUSY pin stuck), TinyUSB never gets CPU time → no CDC port.
Recovery: BOOTSEL trigger → reflash with working firmware.

## 8. Init Sequence Pitfalls

### Mandatory for 2.4 GHz
1. SET_RX_PATH (0x0201) with HF path — without this, no reception at 2.4 GHz
2. CALIB_FRONT_END (0x0123) — image rejection calibration
3. CLEAR_ERRORS (0x0111) before calibration — clear stale error flags

### Calibration
- CALIBRATE bitmask 0x5F (per TheClams reference). Earlier used 0x6F but bit 5
  is undefined in datasheet.
- After bitrate change, recalibrate (bandwidth changes with bitrate).

### DIO Configuration
- DIO9 = IRQ output (physical pin → GP7 on RP2040)
- IRQ mapping: RX_DONE (bit 18 = 0x00040000) → DIO9
- Must poll DIO9 via GPIO, NOT via SPI GET_IRQ_STATUS
