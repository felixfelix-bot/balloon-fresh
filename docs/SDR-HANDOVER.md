# SDR Investigation Handover — LR2021 FLRC Anomalies

## To: SDR Operator
## From: Balloon Range Test Track (Felix/Hermes)
## Date: 2025-07-25
## Priority: MEDIUM (walk test can proceed without this, but needed for full characterization)

---

## Equipment Under Test

- **Chip**: Semtech LR2021 (Gen 4) — dual-band LoRa/FLRC transceiver
- **Module**: NiceRF LoRa2021 (19.72×15mm, 18-pin, XTAL not TCXO)
- **MCU**: RP2040 (Raspberry Pi Pico)
- **Antennas**: HF = 2.4 GHz chip antenna on PCB, LF = 868 MHz wire dipole
- **Frequency**: HF = 2440 MHz, LF = 868.0 MHz
- **Protocol**: Raw 2-byte opcode SPI (NOT RadioLib — see ADR-020)

## What We Need Investigated

### 1. LF-FLRC-650 Complete Failure (HIGH PRIORITY)

**Symptom**: At 868 MHz, FLRC at 650 kbps (600 kHz BW) NEVER decodes. But FLRC at 2600 kbps (2.4 MHz BW) and 325 kbps (300 kHz BW) both work fine.

This is counter-intuitive: wider bandwidth modes work but mid-range doesn't.

**Test setup needed**:
- SDR tuned to 868.0 MHz
- TX board transmitting FLRC-650 (send `SET_TIME` via USB serial, then `PKT_FIXED` mode at FLRC-650)
- Capture spectrum: what does the TX signal look like at 650 kbps?
- Check for spurious signals near 868 MHz

**Specific questions**:
1. Is there a narrowband interferer (Zigbee, LoRaWAN, other SRD device) within the 600 kHz window at 868.0 MHz?
2. Does the FLRC-650 TX spectrum look different from FLRC-2600 or FLRC-325?
3. Is there a spurious emission from the LR2021 module itself at a specific frequency?
4. Is the crystal oscillator producing a spur that aliases into the 650 kbps IF filter?

**LR2021 FLRC bandwidth codes**:
- 2600 kbps → code 0x00 (widest BW ~2.4 MHz)
- 1300 kbps → code 0x02 (~1.2 MHz)
- 650 kbps → code 0x04 (~600 kHz) ← FAILS on LF
- 325 kbps → code 0x06 (~300 kHz)

### 2. HF-FLRC Wide Bandwidth Failure (MEDIUM — likely WiFi)

**Symptom**: At 2440 MHz (2.4 GHz), FLRC-2600 and FLRC-1300 never decode. FLRC-325 works. LoRa works at all spreading factors.

**Likely cause**: WiFi interference (28 networks detected). FLRC has no processing gain unlike LoRa's chirp spread spectrum. Wide FLRC bandwidth captures more WiFi energy.

**What SDR can confirm**:
- Spectrum scan at 2440 MHz: how much WiFi energy is present?
- Check if WiFi beacons/data bursts correlate with FLRC sync failures
- Measure noise floor at different 2.4 GHz frequencies

### 3. Crystal Frequency Accuracy (LOW — baseline check)

**Question**: How accurate is the 52 MHz crystal on the NiceRF module?

The LR2021 uses a 52 MHz XTAL (not TCXO). If crystal frequency error is >100 ppm (5.2 kHz at 52 MHz), it translates to:
- At 868 MHz: ~86.8 kHz error (significant for FLRC-325's 300 kHz BW)
- At 2440 MHz: ~244 kHz error (critical for FLRC-325)

**Test**: Compare TX carrier frequency vs nominal using SDR frequency counter mode.

---

## Full Capture Data

Live capture data available at:
```
~/repos/balloon-fresh/data/range-tests/20260725/forwarded-165613.log
```

Key results summary:

### HF Band (2440 MHz, 2.4 GHz)
| Mode | 32B | 64B | 128B | 255B |
|------|-----|-----|------|------|
| FLRC-2600 | FAIL | FAIL | FAIL | FAIL |
| FLRC-1300 | FAIL | FAIL | FAIL | FAIL |
| FLRC-650 | OK 89% | OK 93% | FAIL | FAIL |
| FLRC-325 | OK 46% | OK 45% | OK 70% | OK 74% |
| LoRa-SF7 | OK 35% | OK 35% | OK 30% | OK 55% |
| LoRa-SF9 | OK 20% | OK 15% | OK 46% | OK 8% |

### LF Band (868 MHz)
| Mode | 32B | 64B | 128B | 255B |
|------|-----|-----|------|------|
| FLRC-2600 | OK 69% | OK 59% | OK 75% | OK 39% |
| FLRC-1300 | OK 62% | OK 81% | OK 90% | OK 55% |
| FLRC-650 | FAIL | FAIL | FAIL | FAIL |
| FLRC-325 | FAIL | FAIL | OK 99% | OK 35% |
| LoRa-SF7 | OK 30% | OK 15% | OK 8% | OK 14% |
| LoRa-SF9 | OK 14% | FAIL | FAIL | OK 0% |

(PER = Packet Error Rate, lower is better. FAIL = 0 packets decoded.)

---

## How to Trigger Specific Modes on TX Board

Connect TX board via USB. It listens for serial commands:

```
# Enter fixed mode (stop sweep)
PKT_FIXED

# Set FLRC-650 at 868 MHz (LF)
# (Use SET_INTERLEAVE 0 first to exit sweep mode)
SET_INTERLEAVE 0

# Then the board will sweep normally. To isolate one mode,
# the fastest approach is to let the sweep run and capture
# the specific phase with the SDR.
```

The sweep prints `PHASE_START <phase_num> <mode_name>` on serial.
When you see the target phase, trigger SDR capture.

Phase numbers (current firmware, narrow→wide order):
- Phase 8: HF-FLRC-325, Phase 12: HF-FLRC-2600
- Phase 48: LF-FLRC-650 (the failing one)

---

## Firmware Source

- TX: `~/worktrees/balloon-range-tests/firmware/rp2040/src/multi_radio_sweep_gps_v4.cpp`
- RX: `~/worktrees/balloon-range-tests/firmware/rp2040/src/multi_radio_sweep_rx_v4.cpp`
- Protocol: `~/repos/balloon-fresh/docs/lr2021-spi-protocol-reference.md`

## Contact

Felix (c03rad0r) — balloon project operator
Hermes Agent — autonomous orchestrator, reachable via this Signal group
