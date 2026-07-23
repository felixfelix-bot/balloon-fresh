# LR2021 FLRC — Complete Learnings (2026-07-24, consolidated)

Cross-track knowledge from range-tests + speed-tests sessions. All findings verified on hardware unless marked UNTESTED.

---

## 1. SPI Protocol — Raw 2-Byte Opcodes (NOT RadioLib)

LR2021 Gen 4 uses 2-byte big-endian SPI opcodes: `NSS LOW → wait BUSY LOW → [opcode_hi, opcode_lo, ...payload] → NSS HIGH`.

RadioLib uses 24-bit register addressing. Returns -707 or hangs. DEAD on our hardware. See ADR-020.

Proven implementations: flrc_raw_tx.cpp, flrc_raw_rx.cpp (range-tests), flrc_bitrate_tx/rx.cpp (speed-tests).

---

## 2. FIFO Race Bug — The 8+ Session Killer (FIXED)

RX polled IRQ status via SPI (3-byte read, ~50us). At 2600 kbps, packets arrive every ~400us. During SPI read, chip starts receiving next packet and overwrites FIFO.

Fix: Poll IRQ via GPIO (DIO9=GP7) using `sio_hw->gpio_in`. Nanosecond read. Commit 3dcddaf.

---

## 3. RSSI Measurement (FIXED)

Old sessions used SX1280 register 0x022A. Returns garbage on LR2021.

Correct commands:
- Per-packet RSSI: GET_FLRC_PACKET_STATUS (0x024B). Returns status bytes, RSSI in buf after 2 status bytes.
- Instant/noise floor: GET_RSSI_INST (0x020B). Returns RSSI_INST in response.
- RSSI is unsigned, negate for dBm: raw 60 = -60 dBm.

Verified: -60 dBm signal at 30cm, -103 dBm noise floor. Commit d85b5ea.

---

## 4. PER Calculation (FIXED)

TX sends 500-pkt bursts with DEADBEEF marker (pkt[0:3]=0xDEADBEEF, pkt[4:7]=count). RX sees 3-4 bursts per 12s window.

Bug: Old code used last burst's count (500) as total. Actually 2000+ packets sent.

Fix: Accumulate totalExpected across all DEADBEEF markers in window. PER = lost/totalExpected. Commit 7a3d150.

Speed-tests had similar bug (resetStats zeroed count but seq kept climbing). Their fix: cumulativeRx field.

---

## 5. PA Discontinuity (LR2021 Power Amp)

Register codes 0-24 (0.0-12.0 dBm): PA BYPASSED. All identical ~4% PER. RSSI -103 dBm.
Register code 25 (12.5 dBm): PA ENABLED. 43 dB jump. RSSI -60 dBm.

Power control below 12.5 dBm doesn't reduce RF output proportionally — it disables the PA.

SET_TX_PARAMS (0x0203): powerRaw = dBm * 2. So 12.5 dBm → powerRaw=25.

---

## 6. FLRC Bitrate Efficiency (speed-tests verified)

| Bitrate | Throughput | PER | RSSI (1-2m) | Efficiency |
|---------|-----------|------|-------------|------------|
| 2600    | 602 kbps  | 0%   | -48.8       | 23%        |
| 1300    | 495 kbps  | 0%   | -50.7       | 38%        |
| 650     | 317 kbps  | 0%   | -57.5       | 49%        |
| 325     | 195 kbps  | 0%   | -51.2       | 60%        |

SPI overhead is constant. Lower bitrates = smaller overhead fraction = better efficiency.

---

## 7. LoRa Mode Bugs (from speed-tests, for future ADR-007)

### CR Encoding
LORA_CR valid range is 1-4 (NOT 5). Index encoding: 1=4/5, 2=4/6, 3=4/7, 4=4/8.
CR=5 encodes as (5<<4)=0x50 — invalid. SF7 tolerates silently. SF9/SF12: ZERO packets received.

### RSSI/SNR Byte Swap
GET_LORA_PACKET_STATUS (0x022A) response after 2 status bytes:
- buf[2] = RSSI (rssiSync, dBm = -val/2)
- buf[3] = SNR (signed, dB = val/4)
Speed-tests had them swapped. "-127 dBm" was actually SNR 31.75 dB.

### BW Codes
812 kHz = 0x0F (NOT 0x0A). 203 kHz = 0x0D, 406 kHz = 0x0E.

---

## 8. SET_RX_PATH + CALIB_FRONT_END Mandatory

SET_RX_PATH (0x0201): HF=1 for 2.4 GHz. MUST be called before entering RX mode.
CALIB_FRONT_END (0x0123): MUST be called before RX or chip returns CMD_ERROR.

CALIBRATE mask is 0x5F (bit 5 undefined — do NOT use 0x6F).

---

## 9. Opcode Reference (Verified Against Working Firmware)

| Command | Opcode | Notes |
|---------|--------|-------|
| SET_STANDBY | 0x0200 | 0x01=STDBY_RC |
| SET_PACKET_TYPE | 0x0207 | LoRa=0x00, FLRC=0x04 |
| SET_TX_PARAMS | 0x0203 | powerRaw=dBm*2, ramp=0x04 |
| SET_FLRC_MOD_PARAMS | 0x0248 | [brBw, crBt] |
| SET_LORA_MOD_PARAMS | 0x0220 | byte0=SF/BW, byte1=CR/LDRO |
| GET_FLRC_PACKET_STATUS | 0x024B | per-packet RSSI |
| GET_LORA_PACKET_STATUS | 0x022A | buf[2]=RSSI, buf[3]=SNR |
| GET_RSSI_INST | 0x020B | instant RSSI (noise floor) |
| SET_RX_PATH | 0x0201 | HF=1 for 2.4 GHz |
| CALIB_FRONT_END | 0x0123 | mandatory before RX |
| CALIBRATE | 0x0122 | mask 0x5F |
| CLEAR_IRQ | 0x020B | 0x02 = clear all |
| SET_RX | 0x0208 | 0x00=continuous |

---

## 10. Runtime Bitrate Switching (UNTESTED — #1 RISK)

rfSwitchBitrate() sequence: STDBY_RC → SET_FLRC_MOD_PARAMS → CALIBRATE → CLEAR_IRQ.

Speed-tests group AVOIDED runtime bitrate changes. Quote: "Compile-time only. USB CDC dies during TX loops."

Our sweep firmware switches between bursts (not during TX). Different approach. Whether the radio actually changes operating parameters without full re-init of all registers (frequency, sync word, packet params) is UNTESTED.

**Verification**: Flash sweep firmware, confirm RSSI/PER differs between bitrate windows at same distance.

---

## 11. Board Management

### USB Port Swaps
RP2040 direct USB ports (ACM0/ACM2) swap on every reboot/reflash. ESP32 UART bridge ports (ACM1/ACM3) are stable but ESP32 needs its own flash procedure.

### BOOTSEL Recovery
1200 baud trigger unreliable. ESP32 loop trigger (flash bootsel-controller firmware to ESP32, it pulses GPIO to RP2040 RUN/BOOTO pins every 5s) is the reliable path.

After BOOTSEL flash, ALWAYS reflash ESP32 with UART bridge firmware to stop the loop.

### Flash Method (Most Reliable)
UF2 mass storage: mount RPI-RP2 partition, copy .uf2, unmount. Board reboots automatically.

picotool needs -v -x flags or silent failure.

### Board Mutex
flock-based. ALWAYS acquire/release BOTH boards atomically. Partial lock is a bug.
```bash
BALLOON_TRACK=range-tests python3 balloon-board-lock.py acquire both
BALLOON_TRACK=range-tests python3 balloon-board-lock.py release both
```

---

## 12. Adaptive Sweep Architecture (ADR-007 precursor)

### Schedule
4 bitrates (2600/1300/650/325 kbps), 3 min each, 12-min cycle.

### Time Sync
- GPS locked: UTC-anchored via NMEA + PPS. Both boards switch at exact same UTC boundary. Zero drift.
- No GPS: millis()-anchored. ~5s boot skew acceptable. Mid-cycle boot support.

### GPS Pins (RP2040)
- GP0 = UART0 TX (to GPS RX, for config)
- GP1 = UART0 RX (from GPS TX, NMEA data)
- GP9 = PPS interrupt

### Evolution Path
Same codebase → flight firmware. GPS sync → multi-balloon TDMA. Adaptive bitrate → ADR-007 full implementation.

---

## 13. What Didn't Work (Complete List)

1. RadioLib LR2021 driver — protocol mismatch, -707 errors
2. SPI IRQ polling during high-rate RX — FIFO race
3. SX1280 RSSI register on LR2021 — garbage values
4. Batch SPI (FIFO+SET_TX combined) — needs CS HIGH between commands
5. Runtime serial commands during TX — USB CDC dies
6. picotool without -v -x — silent flash failures
7. ESP32 flash at 0x0 only — corrupts bootloader, must flash 3 files
8. picotool dual-device targeting — --address flag broken
9. Direct USB port mapping — swaps on every reboot
10. Subagent delegation for HW tasks — 300s timeout too short for captures
11. CR=5 in LoRa — invalid, SF9/SF12 get zero packets
12. RSSI/SNR byte swap — plausible but wrong numbers
