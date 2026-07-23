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

## 3. RSSI Measurement (SOLVED)

### Root Cause of -127 dBm Bug
Previous sessions used SX1280 register 0x022A. The LR2021 uses a completely
different opcode space. The SX1280 register returns garbage (always -127 dBm)
on LR2021.

### Fix
Use LR2021 FLRC command 0x024B (GET_FLRC_PACKET_STATUS):
```
CS LOW → send 0x02 0x4B → CS HIGH → wait BUSY → CS LOW → read 7 bytes → CS HIGH
Response: [stat_msb][stat_lsb][pktLen_msb][pktLen_lsb][rssiAvg][rssiSync][flags]
9-bit RSSI: raw = (buf[4] << 1) | ((buf[6] & 0x04) >> 2)
dBm = -(raw / 2)
```

Also added GET_RSSI_INST (0x020B) for noise floor measurement:
```
CS LOW → send 0x02 0x0B → CS HIGH → wait BUSY → CS LOW → read 2 bytes → CS HIGH
9-bit RSSI: raw = (buf[0] << 1) | (buf[1] >> 7)
dBm = -(raw / 2)
```

### Verified Results (Bench, ~30cm, 12.5 dBm TX)
- Signal RSSI: -60 dBm (stable across 2500+ packets)
- Noise floor: -103 to -105 dBm (TX off)
- SNR: 43 dB (excellent link margin)
- Noise floor matches theory: thermal noise at 2.6 MHz BW (-174 + 10log(2.6e6) = -110 dBm) + 7 dB NF = -103 dBm

### RSSI Calibration
SET_RSSI_CALIBRATION (0x0205) is NOT needed. The chip ships with default OTP
calibration applied on reset. Our CALIBRATE + CALIB_FRONT_END commands
sufficiently calibrate the analog front-end. Adding 0x0205 would require
per-module factory calibration data we don't have. Accuracy: ±2-3 dBm.

Commit: d85b5ea

## 3b. PER Calculation Fix

### Bug
TX sends 500-pkt bursts with 2s pause. RX listens for 12s windows (sees ~3-4
bursts). Old code used DEADBEEF marker's count field (= 500, last burst only)
or maxSeq+1 (but seq restarts at 0 each burst). Result: always reported 100% PER.

### Fix
- DEADBEEF no longer breaks out of receive loop — continues listening
- Tracks burstCount and accumulates totalExpected across all bursts
- PER = lost / totalExpected (correct)
- Added bursts=N to RESULT line

## 3c. Auto Noise Floor at Boot

RX firmware now measures noise floor at boot (before first RX window) using
GET_RSSI_INST, 10 samples averaged. Printed as NOISE_FLOOR=X dBm. Included in
RESULT line as noise_floor=X.

## 3d. Packet Size Consistency Fix

rp2040-range-rx-auto (flrc_range_rx_auto.cpp) used 144B while TX used 127B.
Fixed to 127B with #ifndef guard. Both now match.

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
