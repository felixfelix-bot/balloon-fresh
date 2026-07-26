# Balloon LR2021 Speed Tests — Complete Handover

**Branch:** speed-sustained-sweep
**Worktree:** ~/worktrees/balloon-speed-tests/
**Remotes:** origin (ngit), github (felixfelix-bot/balloon-fresh)
**Date:** 2026-07-24
**Status:** ALL SOFTWARE COMPLETE. Ready for outdoor range testing.

---

## PROJECT SUMMARY

Characterized the Semtech LR2021 (Gen 4) radio chip across all modulation modes and parameters using 2x RP2040 dev boards with raw 2-byte opcode SPI (NOT RadioLib — see ADR-020).

Full 5200:1 throughput range verified: from 602 kbps (FLRC 2600) down to 1.5 kbps (LoRa SF12).

---

## VERIFIED RESULTS

### FLRC Bitrate Sweep (1000 pkts, 255-byte payload, indoor 1-2m, 2440 MHz, 12 dBm)

| Bitrate (kbps) | Throughput (kbps) | PER | RSSI Avg (dBm) | Efficiency |
|----------------|-------------------|-----|-----------------|------------|
| 2600 | 602.4 | 0% | -48.8 | 23% |
| 1300 | 495.1 | 0% | -50.7 | 38% |
| 650 | 317.6 | 0% | -57.5 | 49% |
| 325 | 195.4 | 0% | -51.2 | 60% |

Lower bitrates are more efficient — SPI overhead is constant, smaller fraction at lower speeds.

### LoRa Spreading Factor Sweep (200 pkts, 127-byte payload, same conditions, BW 812 kHz, CR 4/5)

| SF | TX | RX | PER | RSSI | SNR | TX Rate (kbps) |
|----|-------|-------|-----|------|------|----------------|
| 7 | 200/200 | 200/200 | 0% | -8 dBm | 31.8 dB | 30.9 |
| 9 | 200/200 | 194/200 | 3% | -8 dBm | 31.8 dB | 9.7 |
| 12 | 200/200 | 197/200 | 1.5% | -8 dBm | 31.8 dB | 1.5 |

### TX Power Sweep (200 pkts, SF7, same conditions)

| TX Power (dBm) | PER | RSSI | Notes |
|----------------|-----|------|-------|
| 0 | 0% | -8 dBm | RX saturated at close range |
| 3 | 0% | -8 dBm | |
| 6 | 0% | -8 dBm | |
| 12 | 0% | -8 dBm | |

RSSI identical at all power levels. Receiver front-end saturated at 1-2m. Must test outdoors at 10m+ for meaningful power characterization.

### Previous Session FLRC 2600 (10,000 pkts, 127-byte payload)

- TX: 10,000 packets in 6.8s, 1753 kbps TX rate, 0 timeouts
- RX: 21,923 received, 0% PER
- Sustained throughput: 1485 kbps (57% of theoretical 2600)

---

## THREE CRITICAL BUGS FOUND AND FIXED

### Bug 1: Coding Rate Encoding (CR) — commit b32f50b

THE bug that blocked all SF9/SF12 progress for multiple sessions.

LORA_CR defaulted to 5. Valid range is 1-4 (1=4/5, 2=4/6, 3=4/7, 4=4/8). CR=5 encodes as (5<<4)=0x50 — invalid SPI value. SF7 silently tolerated it. SF9 and SF12 received 0 packets.

After fix (5→1): SF9 went from 0 to 194/200. SF12 went from 0 to 197/200.

Lesson: CR macro uses internal index, NOT the denominator. "4/5" = index 1.

### Bug 2: RSSI/SNR Byte Swap — commit dca7a84

GET_LORA_PACKET_STATUS (0x022A) response after 2 status bytes:
- buf[2] = RSSI (rssiSync, dBm = -val/2)
- buf[3] = SNR (signed, dB = val/4)

Old code read them backwards. "RSSI -127 dBm" was actually SNR 31.75 dB. "SNR 4.2 dB" was actually RSSI -8.5 dBm. Both plausible enough to go unquestioned.

After fix: RSSI=-8 dBm, SNR=31.8 dB. Both correct for 1-2m indoor.

### Bug 3: PER Statistics Calculation — commit 9352337

RX firmware uses 30s listen windows. resetStats() zeroed received count per window. But TX sequence numbers are global — they keep climbing. PER = (maxSeq+1 - receivedThisWindow) / (maxSeq+1) showed 78% when only 2/200 were actually lost.

Fix: cumulativeRx field survives resetStats(). PER = (maxSeq+1 - cumulativeRx) / (maxSeq+1).

---

## WHAT DIDN'T WORK

1. **RadioLib LR2021 driver** — Dead. 24-bit register addressing vs 2-byte opcodes. Error -707. Raw SPI only.
2. **Batch SPI (FIFO+SET_TX combined)** — LR2021 needs CS HIGH between commands.
3. **Runtime bitrate serial commands** — USB CDC dies during TX loops. Compile-time only.
4. **picotool without -v -x** — Silent flash failures. Mandatory flags.
5. **ESP32 raw flash at 0x0** — Corrupts bootloader. Must flash 3 files.
6. **picotool dual-device targeting** — --address flag broken. Use UF2 mass storage.
7. **Direct USB port mapping** — ACM0/ACM2 swap on every reboot. Use bridge ports.
8. **Subagent delegation for HW tasks** — 300s timeout too short for 180s captures.

---

## HARDWARE SETUP

### Board Mapping (via ESP32 UART bridges)

| Port | Device | Role | Serial # |
|------|--------|------|----------|
| /dev/ttyACM0 | RP2040 #8332 | RX (direct USB) | E663B035973B8332 |
| /dev/ttyACM1 | ESP32-C3 bridge | Bridge to 8332 | 70:AF:09:13:21:00 |
| /dev/ttyACM2 | RP2040 #F242D | TX (direct USB) | E663B035977F242D |
| /dev/ttyACM3 | ESP32-C3 bridge | Bridge to F242D | 70:AF:09:21:FB:18 |

Direct ports swap on every RP2040 reboot. Bridge ports are stable but ESP32 needs its own flash procedure. Always verify board identity before each test.

### Flash Procedure — UF2 Mass Storage (Most Reliable)

When RP2040 is in BOOTSEL mode:
```bash
lsblk | grep RPI                    # find /dev/sdX1
sudo mount /dev/sdX1 /mnt/rp
sudo cp firmware.uf2 /mnt/rp/       # board reboots automatically
sudo umount /mnt/rp
```

### Flash Procedure — ESP32 Bootsel-Oneshot (Single Board)

```bash
ESPTOOL=~/.platformio/packages/tool-esptoolpy/esptool.py
BOOTSEL=firmware/esp32-c3-bootsel-controller/.pio/build/esp32-c3-bootsel-controller
BRIDGE=firmware/esp32-uart-bridge/.pio/build/esp32-uart-bridge

# 1. Trigger RP2040 BOOTSEL via bridge
python3 $ESPTOOL --port /dev/ttyACM1 --chip esp32c3 --baud 460800 write_flash \
  0x0 $BOOTSEL/bootloader.bin 0x8000 $BOOTSEL/partitions.bin 0x10000 $BOOTSEL/firmware.bin

# 2. Wait + flash RP2040 via UF2
sleep 5
sudo mount /dev/sdX1 /mnt/rp && sudo cp firmware.uf2 /mnt/rp/ && sudo umount /mnt/rp

# 3. Restore UART bridge (3 files!)
python3 $ESPTOOL --port /dev/ttyACM1 --chip esp32c3 --baud 460800 write_flash \
  0x0 $BRIDGE/bootloader.bin 0x8000 $BRIDGE/partitions.bin 0x10000 $BRIDGE/firmware.bin
```

---

## FIRMWARE (17 PlatformIO Environments, All Build)

### LoRa TX (7 envs)
- rp2040-lora-tx-sf7, -sf9, -sf12 (auto-start, 200 pkts, 12 dBm)
- rp2040-lora-tx-sf7-pwr0, -pwr3, -pwr6, -pwr12 (compile-time TX power)

### LoRa RX (3 envs)
- rp2040-lora-rx, rp2040-lora-rx-sf9, rp2040-lora-rx-sf12

### FLRC TX+RX (8 envs)
- rp2040-flrc-tx-2600, -1300, -650, -325
- rp2040-flrc-rx-2600, -1300, -650, -325

Build: `cd firmware/rp2040 && pio run -e <env_name>`

---

## OPCODE REFERENCE (Verified Against Working Firmware)

| Command | Opcode | Notes |
|---------|--------|-------|
| SET_PACKET_TYPE | 0x0207 | LoRa=0x00, FLRC=0x04 |
| SET_TX_PARAMS | 0x0203 | powerRaw=dBm*2, ramp=0x04 |
| SET_LORA_MODULATION_PARAMS | 0x0220 | byte0=SF/BW nibbles, byte1=CR/LDRO |
| SET_LORA_PACKET_PARAMS | 0x0221 | preamble+payloadLen+flags |
| GET_LORA_PACKET_STATUS | 0x022A | buf[2]=RSSI, buf[3]=SNR |
| SET_FLRC_MODULATION_PARAMS | 0x0208 | bitrate+bandwidth combined |
| GET_FLRC_PACKET_STATUS | 0x024B | per-packet RSSI |
| SET_RX_PATH | 0x0201 | HF=1 for 2.4GHz |
| CALIB_FRONT_END | 0x0123 | MANDATORY before RX |

BW code for 812 kHz = 0x0F (NOT 0x0A — verified against working firmware).
BW code for 203 kHz = 0x0D, 406 kHz = 0x0E.
CR codes: 4/5=0x01, 4/6=0x02, 4/7=0x03, 4/8=0x04.

---

## TOOLS

### test_runner.py (tools/test_runner.py)

```bash
# Flash both boards
python3 tools/test_runner.py flash --tx rp2040-flrc-tx-2600 --rx rp2040-flrc-rx-2600

# Capture 20s and show results
python3 tools/test_runner.py capture --duration 20

# Capture to file
python3 tools/test_runner.py capture --duration 20 -o results/test.txt

# Run sweep from config
python3 tools/test_runner.py sweep --config tools/sweep-config-flrc.json --output-dir results/

# Parse saved log
python3 tools/test_runner.py parse --file results/test.txt
```

### Mutex Lock

```bash
BALLOON_TRACK=speed-tests python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire both
BALLOON_TRACK=speed-tests python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py release both
```

Always acquire AND release BOTH boards together. Partial locks are a bug.

---

## WHAT STILL NEEDS DOING (Interactive)

### Phase A: Outdoor Range Characterization

Take TX outdoors. RX stays at laptop. Test at 10m, 25m, 50m, 100m, 200m+.

Priority order:
1. FLRC 2600 (fastest, shortest range expected)
2. LoRa SF7 (medium range)
3. LoRa SF12 (longest range)
4. FLRC 325 (slowest FLRC, longer range than 2600)

### Phase B: TX Power vs Distance

At distances where PER > 0%, sweep 0/3/6/12 dBm to find minimum reliable power. Builds link budget curve.

### Phase C: Interference Testing

WiFi/BLE on 2.4 GHz. Compare PER with and without active interference.

### Phase D: Antenna Comparison

PCB antenna (current) vs wire dipole (V1) vs PCB Yagi (V2) at same distance.

---

## FIELD TEST CHECKLIST

Hardware:
- [ ] 2x RP2040 + LR2021 dev boards (TX + RX)
- [ ] 2x ESP32-C3 UART bridges
- [ ] USB cables (data + power)
- [ ] Laptop with PlatformIO + pyserial
- [ ] Portable USB battery (for TX board)
- [ ] GPS phone app (distance measurement)
- [ ] Antennas to test

Software:
- [x] All firmware builds (17 envs)
- [x] test_runner.py
- [x] All 3 bugs fixed
- [x] Mutex lock tool
- [x] Documentation complete

---

## KEY LESSONS

1. RadioLib is dead on LR2021. Raw 2-byte opcode SPI only.
2. CR encoding uses internal index 1-4, NOT denominator. CR=5 is invalid. SF7 masked this.
3. RSSI/SNR byte order: buf[2]=RSSI first, buf[3]=SNR second. Swapping = plausible wrong numbers.
4. Receiver saturates at close range. Need 10m+ for meaningful power data.
5. Compile-time parameters beat runtime commands. USB CDC dies during TX.
6. UF2 mass storage is most reliable flash method.
7. Binary/exponential sweep steps cover full range efficiently.
8. Mutex: acquire/release BOTH boards atomically. Always.
9. The firmware code is source of truth, not the datasheet.
10. Lower FLRC bitrates are more efficient (23% → 60%).

---

## ALL COMMITS THIS SESSION (13 total, all pushed to ngit + GitHub)

b32f50b — fix: CR encoding bug (LORA_CR 5→1)
dca7a84 — fix: RSSI/SNR byte swap
9352337 — fix: PER stats cumulative count
d051331 — docs: handover + implementation plan
8e8d2b8 — feat: FLRC bitrate firmware (8 envs)
e14cced — feat: test_runner.py + sweep config
7b6c9fe — docs: opcode verification + modulation encoding
e1a75c6 — feat: TX power firmware (4 envs)
fc666aa — test: PER fix verified on HW (SF12)
d760ddd — test: FLRC bitrate sweep complete
2be0010 — docs: session summary
c1c1811 — docs: power sweep + master JSON + range handover

---

## FILES INDEX

- docs/SESSION-SUMMARY-2026-07-24.md — Full session summary
- docs/HANDOVER-speed-tests-2026-07-23.md — Original handover
- docs/PLAN-pre-range-testing-2026-07-23.md — 18-task plan (all complete)
- docs/flrc-bitrate-sweep-results-2026-07-23.md — FLRC results
- docs/power-sweep-results-2026-07-24.md — Power results
- docs/per-fix-verification-2026-07-23.md — PER fix verification
- docs/lr2021-tx-params-verification.md — Opcode verification
- docs/lr2021-lora-modulation-params-encoding.md — Modulation encoding
- docs/range-testing-handover.md — Field testing plan
- docs/master-results.json — All results as JSON
- tools/test_runner.py — Automated test tool
- tools/sweep-config-flrc.json — FLRC sweep config
