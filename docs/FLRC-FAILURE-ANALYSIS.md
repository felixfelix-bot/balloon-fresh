# FLRC Mode Failure Analysis — 2025-07-25

## Summary

After fixing the ms-precision phase synchronization bug (TX used ms, RX used seconds),
the dual-radio sweep now decodes 36+ phases. However, specific FLRC modes consistently fail.

## Capture Results (GPS locked, 3 sats, balcony→indoor ~5m)

### HF Band (2.4 GHz, 2440 MHz)

| Mode | BW | 32B | 64B | 128B | 255B | Verdict |
|------|-----|-----|-----|------|------|---------|
| FLRC-2600 | 2.4 MHz | FAIL | FAIL | FAIL | FAIL | **ALL FAIL** |
| FLRC-1300 | 1.2 MHz | FAIL | FAIL | FAIL | FAIL | **ALL FAIL** |
| FLRC-650 | 600 kHz | OK 89% | OK 93% | FAIL | FAIL | **PARTIAL** |
| FLRC-325 | 300 kHz | OK 46% | OK 45% | OK 70% | OK 74% | **ALL OK** |
| LoRa-SF7 | 812 kHz | OK 35% | OK 35% | OK 30% | OK 55% | ALL OK |
| LoRa-SF9 | 812 kHz | OK 20% | OK 15% | OK 46% | OK 8% | ALL OK |
| LoRa-SF12 | 812 kHz | OK 50% | OK 0% | OK 0% | FAIL | MOSTLY OK |

### LF Band (868 MHz, sub-GHz)

| Mode | BW | 32B | 64B | 128B | 255B | Verdict |
|------|-----|-----|-----|------|------|---------|
| FLRC-2600 | 2.4 MHz | OK 69% | OK 59% | OK 75% | OK 39% | **ALL OK** |
| FLRC-1300 | 1.2 MHz | OK 62% | OK 81% | OK 90% | OK 55% | **ALL OK** |
| FLRC-650 | 600 kHz | FAIL | FAIL | FAIL | FAIL | **ALL FAIL** |
| FLRC-325 | 300 kHz | FAIL | FAIL | OK 99% | OK 35% | **PARTIAL** |
| LoRa-SF7 | 812 kHz | OK 30% | OK 15% | OK 8% | OK 14% | ALL OK |
| LoRa-SF9 | 812 kHz | OK 14% | FAIL | FAIL | OK 0% | MOSTLY OK |

## Root Cause Analysis

### 1. HF FLRC-2600/1300 Failure: WiFi Interference

**Evidence:**
- 28 WiFi networks detected in vicinity
- Bluetooth active and running
- FLRC-2600 bandwidth = 2.4 MHz — spans 2+ WiFi channels (each 20 MHz, but sidebands overlap)
- FLRC-1300 bandwidth = 1.2 MHz — still wide enough to hit WiFi energy
- FLRC-325 bandwidth = 300 kHz — narrow enough to find quiet spectrum gaps
- LoRa modes work because LoRa has 10+ dB processing gain from chirp spread spectrum

**Why wide BW fails but narrow BW works:**
FLRC is essentially FSK with Gaussian filtering. Unlike LoRa's chirp spread spectrum,
FLRC has NO processing gain against in-band interference. A WiFi beacon or data burst
within the FLRC bandwidth will corrupt the sync word detection, causing SYNC_NOT_FOUND.

**Verification:** LF band (868 MHz) has no WiFi — FLRC-2600/1300 work fine there.

### 2. LF FLRC-650 Failure: Likely Calibration/Aliasing

LF-FLRC-650 failing while LF-FLRC-2600 and LF-FLRC-1300 work is counter-intuitive.
Wider bandwidth should be MORE susceptible to noise, not less.

**Hypotheses:**
- **a) Spurious signal near 868 MHz:** A narrowband signal (e.g., EU 868 SRD duty-cycle
  devices, Zigbee nearby) could fall exactly in the 600 kHz window but not the wider ones.
- **b) Crystal aliasing:** At 650 kbps with 600 kHz BW, a specific harmonic of the
  52 MHz crystal might alias into the passband.
- **c) AGC settling time:** 650 kbps FLRC packets are ~0.5ms. AGC might not settle
  at this specific bandwidth/frequency combination.
- **d) Single-capture artifact:** Only 1-2 phase instances captured per mode due to
  GPS intermittency. Need longer capture to confirm.

### 3. FLRC Coding Rate = None (No FEC)

Current FLRC modulation params byte: `0x25`
- Coding Rate = 0x2 → **None** (no forward error correction)
- Pulse Shape = 0x5 → BT 0.5

With NO coding, FLRC has zero error correction capability. Any bit flip = packet loss.
Changing to CR 3/4 (`0x15`) would add 25% overhead but provide FEC, potentially
salvaging corrupted packets.

## Firmware Config Verification

TX and RX FLRC configuration is **byte-for-byte identical**:
```
SET_FLRC_MODULATION_PARAMS: {0x02, 0x48, brBw, 0x25}  // same brBw, same CR/PS
SET_FLRC_SYNC_WORD:         {0x02, 0x4C, 0x01, 0x12, 0xAD, 0x10, 0x1B}
SET_FLRC_PACKET_PARAMS:     {0x02, 0x49, 0x0C, 0x4C, 0x00, pktSize}
```

brBw codes: 2600→0x00, 1300→0x02, 650→0x04, 325→0x06 (identical in both)

**The failure is NOT a config mismatch.** Both boards configure the radio identically.

## Recommended Fixes (Priority Order)

1. **Walk test will resolve HF interference** — outdoors, away from WiFi, HF FLRC
   modes should work. The walk test IS the interference test.

2. **Add FLRC coding rate CR 3/4** — change `0x25` to `0x15` in modulation params.
   This adds FEC and should improve ALL FLRC modes.

3. **Longer capture (3+ cycles)** — current capture only got 1 full cycle due to
   GPS intermittency. Some "failures" may be GPS dropout, not real RF failures.

4. **LF-FLRC-650 investigation** — check for spurious signals at 868 MHz with
   SDR or spectrum analyzer. May need frequency offset.

## Conclusion

The HF FLRC failures are almost certainly WiFi interference — 28 networks is extreme.
The walk test (outdoors) will definitively answer this. LF-FLRC-650 needs investigation
but is lower priority. Adding CR 3/4 coding would help all modes.
