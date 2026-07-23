# Session Summary — Balloon Speed Tests (2026-07-23/24)

**Branch:** speed-sustained-sweep
**Worktree:** ~/worktrees/balloon-speed-tests/
**Remotes:** origin (ngit), github (felixfelix-bot/balloon-fresh)
**Operator:** c08r4d0r number 3

---

## 10 Commits This Session

All pushed to ngit + GitHub. In chronological order:

### Bug Fixes (3)

1. **b32f50b** — `fix(lora): CR encoding bug — LORA_CR 5→1 (invalid SPI value)`
   - LORA_CR=5 was out of range (valid 1-4). SPI encoded (5<<4)=0x50 — invalid.
   - SF7 silently tolerated it. SF9 and SF12 did not.
   - Root cause of all SF9/SF12 RX failures.

2. **dca7a84** — `fix(rssi): swap RSSI/SNR byte indices in LoRa packet status`
   - GET_LORA_PACKET_STATUS (0x022A): buf[2]=RSSI, buf[3]=SNR.
   - Old code read them backwards. "RSSI -127" was actually SNR 31.75. "SNR 4.2" was actually RSSI -8.5 dBm.
   - Verified: SF9 now reads RSSI=-8 dBm, SNR=31.8 dB (realistic for 1-2m indoor).

3. **9352337** — `fix(stats): PER calculation uses cumulative rx count`
   - resetStats() zeroed received count each window but maxSeq kept climbing (global TX seq).
   - PER denominator was wrong. Reported 78% PER when only 2/200 lost.
   - Added cumulativeRx field surviving resetStats(). PER now correct.

### Firmware (2)

4. **8e8d2b8** — `feat(flrc): compile-time bitrate firmware (2600/1300/650/325) TX+RX`
   - 8 PlatformIO environments. Compile-time FLRC_BITRATE macro.
   - USB CDC dies during TX loops — runtime serial commands don't work. Compile-time only.
   - Includes cumulativeRx PER fix in RX firmware.
   - Worker A timed out at 300s. Files created but not built/committed. I finished build+commit.

5. **e1a75c6** — `feat(lora): compile-time TX power selection firmware`
   - 4 envs: pwr0/pwr3/pwr6/pwr12 (TX_POWER_DBM macro).
   - SET_TX_PARAMS opcode 0x0203 confirmed correct (worker verified against RadioLib LR2021 source).
   - Power encoding: powerRaw = (uint8_t)(dBm * 2). 0dBm→0x00, 12dBm→0x18.

### Tools (1)

6. **e14cced** — `feat(tools): automated test runner (flash+capture+parse+sweep)`
   - Python script: tools/test_runner.py
   - Subcommands: flash, capture, sweep, parse.
   - Parses RESULT_TX, RANGE_RESULT_RX, LORA_RX_RESULT lines.
   - JSON output for machine consumption.
   - Worker B timed out. I wrote the script myself.

### Documentation (4)

7. **d051331** — `docs: comprehensive handover + pre-range-testing implementation plan`
   - Handover: 313 lines. All results, bugs, hardware setup, flash procedures, firmware state.
   - Plan: 717 lines. 18 tasks across 5 phases. Each with acceptance criteria + reasoning prompts.

8. **7b6c9fe** — `docs: verify SET_TX_PARAMS opcode + document LoRa modulation param encoding`
   - SET_TX_PARAMS = 0x0203 (confirmed). 0x0216 was wrong — it's SET_TIMESTAMP_SOURCE.
   - LoRa modulation params encoding: full byte-level reference + lookup tables.
   - BW codes differ from SX128x: LR2021 uses 0x0F for 812kHz, SX128x uses 0x18.

9. **fc666aa** — `test: verify PER stats fix (cumulativeRx) with SF12 hardware test`
   - SF12 re-run with fixed firmware: 197/200 received, PER=1.50%.
   - Previous false "78% PER" confirmed gone.

10. **d760ddd** — `test: FLRC bitrate sweep complete — all 4 bitrates 0% PER`
    - All 4 FLRC bitrates verified on hardware.

---

## Verified Results

### FLRC Sweep (1000 pkts, 255-byte payload, indoor 1-2m, 2440 MHz, 12 dBm)

| Bitrate (kbps) | Throughput (kbps) | PER | RSSI Avg (dBm) | Efficiency |
|----------------|-------------------|-----|-----------------|------------|
| 2600 | 602.4 | 0.00% | -48.8 | 23% |
| 1300 | 495.1 | 0.00% | -50.7 | 38% |
| 650 | 317.6 | 0.00% | -57.5 | 49% |
| 325 | 195.4 | 0.00% | -51.2 | 60% |

### LoRa Sweep (200 pkts, 127-byte payload, indoor 1-2m, 2440 MHz, 12 dBm, BW 812 kHz, CR 4/5)

| SF | TX | RX | PER | RSSI | SNR | TX Rate (kbps) |
|----|-------|-------|-----|------|------|----------------|
| 7 | 200/200 | 200/200 | 0% | -8 dBm | 31.8 dB | 30.9 |
| 9 | 200/200 | 194/200 | 3% | -8 dBm | 31.8 dB | 9.7 |
| 12 | 200/200 | 197/200 | 1.5% | -8 dBm | 31.8 dB | 1.5 |

### Previous Session FLRC 2600 (10,000 pkts, 127-byte payload)

- TX: 10,000 pkts in 6.8s, 1753 kbps TX rate, 0 timeouts
- RX: 21,923 received, 0% PER
- Sustained throughput: 1485 kbps (57% of theoretical 2600)

---

## What Didn't Work

1. **RadioLib LR2021 driver** — Dead. 24-bit register addressing vs 2-byte big-endian opcodes. Error -707. Raw SPI only.
2. **Batch SPI (FIFO+SET_TX combined)** — LR2021 needs CS HIGH between commands.
3. **Runtime bitrate serial commands** — USB CDC dies during TX loops. Must use compile-time.
4. **Subagent 300s timeout for HW tasks** — 180s capture alone exceeds budget. HW tasks run in main context.
5. **picotool without -v -x** — Silent flash failures look identical to successes.
6. **ESP32 raw flash at 0x0** — Corrupts bootloader. Must flash 3 files (bootloader+partitions+app).

---

## Hardware Setup (Stable)

### Board Mapping (via ESP32 UART bridges)

| Port | Device | Role | Serial # |
|------|--------|------|----------|
| /dev/ttyACM0 | RP2040 #8332 | RX board (direct USB) | E663B035973B8332 |
| /dev/ttyACM1 | ESP32-C3 bridge | Bridge to 8332 | 70:AF:09:13:21:00 |
| /dev/ttyACM2 | RP2040 #F242D | TX board (direct USB) | E663B035977F242D |
| /dev/ttyACM3 | ESP32-C3 bridge | Bridge to F242D | 70:AF:09:21:FB:18 |

Direct ports (ACM0/ACM2) swap on every reset — unreliable. Bridge ports (ACM1/ACM3) are stable.

### Flash Procedure — UF2 Mass Storage (Proven Reliable)

When both RP2040s end up in BOOTSEL simultaneously:

```bash
# Find drives
lsblk | grep RPI

# Flash each
sudo mount /dev/sdX1 /mnt/rp
sudo cp firmware.uf2 /mnt/rp/
sudo umount /mnt/rp
# Board reboots automatically after UF2 copy
```

### Flash Procedure — Single Board via ESP32 Bootsel-Oneshot

```bash
ESPTOOL=~/.platformio/packages/tool-esptoolpy/esptool.py
BOOTSEL=firmware/esp32-c3-bootsel-controller/.pio/build/esp32-c3-bootsel-controller
BRIDGE=firmware/esp32-uart-bridge/.pio/build/esp32-uart-bridge

# 1. Flash bootsel-oneshot to trigger RP2040 BOOTSEL
python3 $ESPTOOL --port /dev/ttyACM1 --chip esp32c3 --baud 460800 write_flash \
  0x0 $BOOTSEL/bootloader.bin 0x8000 $BOOTSEL/partitions.bin 0x10000 $BOOTSEL/firmware.bin

# 2. Wait for BOOTSEL trigger
sleep 5

# 3. Flash RP2040 via picotool or UF2 mass storage
sudo picotool load -v -x firmware.uf2
# OR
sudo mount /dev/sdX1 /mnt/rp && sudo cp firmware.uf2 /mnt/rp/ && sudo umount /mnt/rp

# 4. Restore UART bridge (3 files!)
python3 $ESPTOOL --port /dev/ttyACM1 --chip esp32c3 --baud 460800 write_flash \
  0x0 $BRIDGE/bootloader.bin 0x8000 $BRIDGE/partitions.bin 0x10000 $BRIDGE/firmware.bin
```

---

## Plan Status (18 tasks across 5 phases)

### Phase 1: FLRC Bitrate Sweep — COMPLETE
- P1-1/P1-2/P1-3: Compile-time bitrate firmware (8e8d2b8) ✅
- P1-4: Hardware sweep all 4 bitrates (d760ddd) ✅

### Phase 2: TX Power Sweep — FIRMWARE READY, HARDWARE PENDING
- P2-1: Opcode verification (7b6c9fe) ✅
- P2-2: Power firmware 4 envs (e1a75c6) ✅
- P2-3: Hardware power sweep — **NOT STARTED** (mutex was acquired but session ended)
- P2-4: Power vs PER analysis — blocked on P2-3

### Phase 3: Automated Test Harness — MOSTLY COMPLETE
- P3-1: Python test runner (e14cced) ✅
- P3-2: JSON output — covered by test_runner.py ✅
- P3-3: Sweep mode — covered by test_runner.py ✅

### Phase 4: Firmware Cleanup — MOSTLY COMPLETE
- P4-1: PER fix verified on HW (fc666aa) ✅
- P4-2: RSSI verify on HW — done during FLRC sweep (d760ddd) ✅
- P4-3: Firmware cleanup — UF2 flash method documented ✅
- P4-4: Modulation encoding docs (7b6c9fe) ✅

### Phase 5: Consolidation — NOT STARTED
- P5-1: Master results JSON
- P5-2: Summary comparison table
- P5-3: Range testing handover doc

### Remaining Work Summary

**Hardware tasks (need mutex, ~30 min each):**
- P2-3: TX power sweep (flash pwr0/3/6/12, capture RSSI/PER at each level)

**Software-only tasks (no mutex, can delegate):**
- P2-4: Power vs PER analysis (after P2-3)
- P5-1: Master results JSON (combine all test data)
- P5-2: Summary comparison table
- P5-3: Range testing handover doc

**After all plan tasks:**
- Range testing (outdoor, increasing distances)
- Antenna testing (dipole vs Yagi)
- Interference testing (WiFi/BLE coexistence)

These 3 are interactive with operator — do AFTER all software/tooling is ready.

---

## Key Lessons Learned

1. **RadioLib is dead on LR2021.** 24-bit register addressing vs 2-byte big-endian opcodes. Always error -707. Raw SPI only. ADR-020 documents this.

2. **CR encoding is NOT intuitive.** Macro uses internal index 1-4, not the denominator. CR=5 is invalid. SF7 tolerated it, higher SF did not. This was THE bug blocking SF9/SF12.

3. **RSSI/SNR byte order matters.** GET_LORA_PACKET_STATUS puts rssiSync first (buf[2]), then SNR (buf[3]). Swapping them produces plausible-looking but completely wrong numbers.

4. **picotool requires -v -x.** Silent flash failures look identical to successes without these flags.

5. **ESP32 bridge bootloader is fragile.** Raw flash at 0x0 corrupts bootloader. Always flash 3 files.

6. **USB CDC dies during TX burst loops.** Can't receive serial commands mid-transmission. Compile-time parameters beat runtime commands.

7. **Synchronized capture is the hard part.** Port swaps, bridge crashes, and timing windows consumed more debugging time than firmware development.

8. **PER stats must track cumulative counts.** When TX uses global sequence numbers and RX resets per window, the denominator inflates.

9. **Mutex: always lock/unlock BOTH boards together.** Partial locks are a bug. Use balloon-board-lock.py with BALLOON_TRACK env var.

10. **Binary/exponential sweep steps work.** 8 points cover 5200:1 throughput range (1485 kbps FLRC down to 1.5 kbps SF12 LoRa).

11. **Subagent 300s timeout too short for HW tasks.** 180s capture alone exceeds budget. HW tasks run better in main context. SW tasks (builds, docs, scripts) delegate fine.

12. **UF2 mass-storage flashing is the most reliable method** when both RP2040s are in BOOTSEL simultaneously. No need for picotool address targeting.

---

## Firmware Environments (platformio.ini)

### LoRa TX (6 envs)
- rp2040-lora-tx-sf7, -sf9, -sf12 (auto-start, 200 pkts, 12 dBm)
- rp2040-lora-tx-sf7-pwr0, -pwr3, -pwr6, -pwr12 (compile-time TX power)

### LoRa RX (3 envs)
- rp2040-lora-rx-sf7, -sf9, -sf12 (cumulativeRx PER fix)

### FLRC TX (4 envs)
- rp2040-flrc-tx-2600, -1300, -650, -325 (compile-time bitrate)

### FLRC RX (4 envs)
- rp2040-flrc-rx-2600, -1300, -650, -325 (compile-time bitrate, cumulativeRx)

**Total: 17 environments, all build successfully.**

---

## Opcode Reference (Verified)

| Command | Opcode | Notes |
|---------|--------|-------|
| SET_PACKET_TYPE | 0x0207 | LoRa=0x00, FLRC=0x04 |
| SET_TX_PARAMS | 0x0203 | powerRaw=dBm*2, ramp=0x04 |
| SET_LORA_MODULATION_PARAMS | 0x0220 | byte0=SF/BW, byte1=CR/LDRO |
| SET_LORA_PACKET_PARAMS | 0x0221 | preamble+payloadLen+flags |
| GET_LORA_PACKET_STATUS | 0x022A | buf[2]=RSSI, buf[3]=SNR |
| SET_FLRC_MODULATION_PARAMS | 0x0208 | bitrate+bandwidth combined |
| GET_FLRC_PACKET_STATUS | 0x024B | per-packet RSSI |
| SET_RX_PATH | 0x0201 | HF=1 for 2.4GHz |
| CALIB_FRONT_END | 0x0123 | MANDATORY before RX |

---

## Contact / Continuity

- **Next session:** Read this doc + docs/HANDOVER-speed-tests-2026-07-23.md + docs/PLAN-pre-range-testing-2026-07-23.md
- **Mutex:** RELEASED. Both boards free.
- **Session notes:** ~/.hermes/profiles/manager/state/session-notes.md updated.
- **Memory:** Updated with final LoRa results. FLRC sweep results in docs/flrc-bitrate-sweep-results-2026-07-23.md.
