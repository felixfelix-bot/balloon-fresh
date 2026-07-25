# SDR Investigation Handover — LR2021 Narrow-Bandwidth FLRC Anomaly

**Document ID:** SDR-INVESTIGATION-HANDOVER
**Date:** 2026-07-25
**Prepared by:** Balloon Range-Tests engineering team
**Recipient:** External RF engineer (SDR operator)
**Firmware under test:** `multi_radio_sweep_gps_v4.cpp` (RP2040 TX board)
**Reference protocol doc:** `~/repos/balloon-fresh/docs/lr2021-spi-protocol-reference.md`
**Classification:** Engineering investigation — for RF characterization only

---

## 0. Executive Summary

We operate a custom dual-band telemetry link built around the **Semtech LR2021 Gen 4** RF
chip (marketed by NiceRF as the "LoRa2021" module). The link transmits on both the 2.4 GHz
and EU 868 MHz bands using LoRa and FLRC (Fast LoRa / GFSK-derived) modulations. After
resolving a software-layer firmware-mismatch bug, we are left with a **residual anomaly on
the narrowest FLRC bandwidths (325 kHz)**: packets are detected with healthy RSSI and zero
bit errors on the decoded payloads, yet the packet-error rate (PER) remains high and many
captures report `SYNC_NOT_FOUND` and garbage payloads.

We have exhausted what we can diagnose with our two LR2021 boards alone. We are asking you,
as the SDR operator, to look at the **actual radiated spectrum** to determine whether the
root cause is RF-layer (spurious emissions, AGC settling, adjacent-channel interference,
crystal-clock harmonics) rather than digital. This document gives you the exact on-air
parameters and the SPI register-level configuration so you can correlate what you see on the
waterfall with what the chip is *supposed* to be transmitting.

**The single most important thing we want to know:** *Is there a spurious or harmonic
emission on or near 2440 MHz (±5 MHz) that is not the intended FLRC carrier?*

---

## 1. Hardware Setup

### 1.1 Device Under Test (DUT)

| Subsystem | Part | Notes |
|-----------|------|-------|
| RF chip | **Semtech LR2021 Gen 4** (NiceRF "LoRa2021" module, 18-pin, 19.72×15×2.2 mm) | Dual-band: 2.4 GHz HF path + sub-GHz LF path. Module label "LORA2021-915". |
| MCU | **Raspberry Pi RP2040** (Pico-class board) | Dual-core ARM Cortex-M0+ @ 133 MHz. |
| Reference clock | **52 MHz crystal** (TCXO disabled; `tcxoVoltage = 0`) | Drives the LR2021 PLL. Module uses a passive XTAL, **not** a TCXO. |
| SPI bus clock | **20 MHz**, MODE 0, MSB-first | `#define SPI_FREQ_HZ 20000000UL` |
| GPS | **GEPRC GEP-M10nano** (u-blox M10) on UART0 @ 115200 baud | Provides UTC for phase synchronization between TX and RX boards. |
| Host bridge | **ESP32-C3** UART bridge | USB CDC serial to the operator's laptop. |
| TX power | **+12.5 dBm** (≈18 mW EIRP, no external PA on the test boards) | `powerRaw = 25 (0x19)` — see §5. |

### 1.2 Pin Map (RP2040 → LR2021)

```
SCK  = GP2     MISO = GP4     MOSI = GP3     CS (NSS) = GP5
BUSY = GP6     IRQ (DIO9) = GP7     RST = GP8
GPS_RX = GP1   GPS_TX = GP0   (UART0)
LED   = GP25
```

### 1.3 Antennas

The DUT uses small PCB/wire antennas on each RF path (U.FL / PCB trace). Please treat the
device as **near-field dominated** at <1 m and **far-field** beyond ~2 m. For your SDR
capture, expect the carrier to be **+10 to +20 dB stronger** than the on-board RSSI reported
by our RX board, because your antenna gain and proximity will differ.

### 1.4 Operating Bands

| Band | Path | Center frequencies swept | Purpose |
|------|------|--------------------------|---------|
| 2.4 GHz (HF) | `rfPath=1` | **2412, 2417, 2422, 2427, 2432, 2437, 2442, 2447, 2452, 2457, 2462, 2467, 2472 MHz** (WiFi ch1–13) + 2440 (baseline), 2478, 2483 | Characterize WiFi-adjacent interference |
| EU 868 MHz (LF) | `rfPath=0` | **863, 864, 865, 866, 867, 868, 869, 870 MHz** + 869.5 (high-power sub-band) | Sub-GHz baseline / duty-cycle band |

---

## 2. Observed Symptoms

### 2.1 Primary Anomaly — Narrow-BW FLRC

On the narrowest FLRC bandwidth (**325 kHz**), and to a lesser extent 650 kHz, the receiver
logs:

1. **Bit-error rate (BER) = 0.00e+00** on every packet that *does* decode — payload bytes
   match the known test pattern perfectly, CRC-16 (CCITT) passes, no bit flips.
2. **Packet-error rate (PER) = 60–97 %** — most packets simply never trigger a sync-word
   match. The RX reports `SYNC_NOT_FOUND` for the slot.
3. **"Garbage" captures** — when the RX *does* latch onto a packet that was not ours (e.g.
   during a firmware-mismatch bug now fixed), it reports plausible RSSI but payload bytes
   that do not match the expected test pattern. These are **synchronous to our TX slots**
   (they appear only during our FLRC phase windows), which suggests an in-band emitter that
   is time-correlated with our activity.
4. The anomaly is **bandwidth-correlated**: FLRC 2600/1300 kHz decode cleanly with PER ≈ 0;
   the problem grows as bandwidth narrows (650 → 325 kHz).

### 2.2 Secondary Observations

| Observation | Detail |
|-------------|--------|
| **FLRC RSSI is remarkably stable** | On the fixed-firmware walk test, FLRC RSSI across 0.1–5.7 km was a tight −53 to −58 dBm with <2 dB jitter. This is *not* thermal noise (which would swing ±10 dBm). |
| **LoRa phases frequently got zero packets** | On the walk test (GPS in a rucksack lost lock), LoRa SF7/SF9/SF12 captured nothing while FLRC captured real signal. This is a GPS-phase-sync issue, not an RF issue — but worth noting because it means our LoRa spectral signature is under-characterized. |
| **One mode/size combination fails deterministically** | Phase 12 (HF-FLRC-2600-32B) fails *only* when it immediately follows the longest SF12 transmission. This is a **radio reconfiguration-timing bug** (RX not ready when TX starts), not RF. Documented in `data/v4-interleave-bench/ANALYSIS.md`. |
| **HF-FLRC-1300 spike to −40 dBm** | A single 14 dB RSSI spike observed once during a walk — consistent with brief line-of-sight proximity, not interference. |

### 2.3 What We Have Already Ruled Out (Software Layer)

- **Firmware mismatch (FIXED):** A historical bug where TX and RX ran incompatible packet
  layouts caused 100 % garbage. Fixed by commit `4a8e4cf` + git-hash fingerprinting in every
  packet. The residual narrow-BW PER anomaly survives this fix → it is **not** a packet-format bug.
- **GPS UTC garbage → bad phase calc (FIXED):** GPS date parsing was unreliable; fixed with
  pattern-matching date extraction. Phase alignment is now bounded to <0.3 s.
- **TX/RX clock truncation drift (FIXED):** Phase computation switched from truncated
  seconds to millisecond precision (commit `e303327`).

The remaining narrow-BW FLRC anomaly is therefore the prime candidate for an **RF-layer**
root cause — which is why your SDR is needed.

---

## 3. Hypotheses Under Investigation

These are the four leading hypotheses, in priority order. Each predicts a *distinct* SDR
observable — please design your captures to falsify them one at a time.

### 3.1 H1 — Wi-Fi / Bluetooth Adjacent-Channel Interference (HIGH priority)

- **Rationale:** The baseline test frequency **2440 MHz** sits **2 MHz below Wi-Fi channel 7
  (2442 MHz)** and within the 20 MHz-wide energy lobe of any active ch7 AP. Our 325 kHz FLRC
  channel is only ~13 % of a Wi-Fi 20 MHz channel width, so even low-level Wi-Fi energy that
  broadband 2600 kHz FLRC tolerates can overwhelm a 325 kHz receiver's narrower AGC/sync
  detector. Zigbee (2.4 GHz, 2 MHz channels, 250 kbps O-QPSK) is also a suspect.
- **SDR falsification:** Capture the **2422–2462 MHz** span at high RBW during a TX-off
  baseline. If you see Wi-Fi beacons / data bursts at ch7 (2442) or Zigbee hops, H1 is
  supported. Compare TX-on vs TX-off at 2440 ± 1 MHz.
- **Prediction:** The anomaly should **disappear or weaken** when we move to clean spots
  (2478, 2483 MHz) — confirm this on the waterfall.

### 3.2 H2 — AGC Settling / Burst-On Transient (MEDIUM-HIGH priority)

- **Rationale:** FLRC is a bursty modulation with a short preamble. The LR2021's internal AGC
  must settle within the preamble window (4–32 bytes; see §5 — our firmware uses 16-byte AGC
  preamble). On narrow bandwidths the loop has less signal energy per symbol to integrate,
  and a mistuned AGC can either (a) desensitize sync-word correlation or (b) generate
  spurious "ghost" detections. The fact that **BER=0 but PER is high** is the classic
  fingerprint of an AGC/sync problem: when sync *does* lock, the data is perfect; when it
  misses, the whole packet is lost.
- **SDR falsification:** Capture the **full preamble + sync-word + payload** of a single
  FLRC-325 burst at high time resolution. Look for (a) amplitude droop/ringing in the first
  50–100 µs (AGC transient), (b) whether the preamble amplitude is stable before sync, and
  (c) whether the carrier is on-frequency immediately at burst onset or sweeps in.
- **Prediction:** Narrow-BW bursts will show a longer/ringier AGC transient than wide-BW bursts.

### 3.3 H3 — Crystal & Digital-Clock Harmonics (MEDIUM priority, but easy to check)

The RP2040 system has three strong periodic clocks whose **high-order harmonics land inside
the 2.4 GHz band**. This is the hypothesis most directly testable with a spectrum analyzer /
waterfall, and the math is striking:

| Clock source | Frequency | Harmonic | Landing freq | Offset from 2440 MHz TX | Offset from Wi-Fi ch7 (2442) |
|--------------|-----------|----------|--------------|--------------------------|------------------------------|
| **LR2021 reference crystal** | 52 MHz | **×47** | **2444 MHz** | +4 MHz | **+2 MHz** |
| **SPI bus clock (SCK)** | 20 MHz | **×122** | **2440 MHz** | **0 MHz (EXACT)** | −2 MHz |
| RP2040 USB clock | 48 MHz | ×51 | 2448 MHz | +8 MHz | +6 MHz |
| RP2040 core clock | 133 MHz | ×18 / ×19 | 2394 / 2527 MHz | −46 / +87 MHz | — |

> **⚠️ Note:** The **20 MHz SPI clock's 122nd harmonic lands *exactly* on our 2440 MHz test
> frequency**, and the **52 MHz reference crystal's 47th harmonic lands at 2444 MHz — only
> 2 MHz from Wi-Fi channel 7.** Either of these could produce a narrow spurious spur that a
> 325 kHz FLRC receiver (which has a tight channel filter) would be far more sensitive to
> than a 2600 kHz receiver. This is the cleanest explanation we have for *why the anomaly is
> bandwidth-correlated*.
>
> The 52 MHz ×47 spur at 2444 MHz is especially concerning because it would masquerade as a
> Wi-Fi-channel-7 interferer — explaining why the symptom looks like "WiFi interference"
> even in environments where Wi-Fi may not be the actual culprit.

- **SDR falsification:** With the DUT **TX disabled but MCU powered and SPI idle**, scan
  **2435–2450 MHz** at very fine RBW (≤1 kHz) for narrow spurs at exactly **2440.000 MHz**
  (SPI ×122) and **2444.000 MHz** (crystal ×47). Then toggle SPI activity (have the MCU run
  SPI transactions without keying the PA) and watch whether the 2440 spur modulates. A spur
  that tracks the SPI bus clock confirms H3.
- **Prediction:** If H3 holds, the 2440 MHz spur will be present whenever the RP2040 is
  powered, independent of PA state, and will narrow/strengthen with SPI bus activity.

### 3.4 H4 — Image / Front-End Calibration Artifacts (LOWER priority)

- **Rationale:** Our early RX code omitted the mandatory `CALIB_FE` (0x0123) front-end
  calibration (image rejection, ADC offset) — see §5.5. Even though the current TX firmware
  calls it, the RX side historically did not, which can produce image responses ~offset by
  the IF. This is an RX-side artifact, but an SDR can reveal it by showing energy at the
  image frequency that the LR2021 RX was correlating on.
- **SDR falsification:** Look for a mirror-image carrier offset symmetrically about the LO.
  Report the exact image offset if seen.

---

## 4. SDR Test Plan

The DUT runs a **GPS-synchronized phase schedule**. In interleave mode (the default for
characterization) it cycles through 14 base modes × 4 packet sizes = 56 phases plus a
channel-sweep tail, totaling roughly **2.5–3 minutes per full cycle**. Each phase is a
~3–15 s window of continuous TX. This is convenient for you: you can let the device run and
capture each modulation/bandwidth in turn without reconfiguring anything.

### 4.1 Frequencies to Scan (Priority Order)

| Priority | Center freq | Span | Why |
|----------|-------------|------|-----|
| **P0** | 2440 MHz | 2435–2445 MHz (10 MHz) | Baseline test frequency. Look for SPI ×122 (2440.000) and crystal ×47 (2444.000) spurs. |
| **P0** | 2440 MHz | 2420–2460 MHz (40 MHz) | Full Wi-Fi ch5–ch9 context. Identify any active APs / Zigbee. |
| **P1** | 2442 MHz (Wi-Fi ch7) | ±5 MHz | Worst-case overlap. Characterize AP energy shape. |
| **P1** | 2478 & 2483 MHz | ±3 MHz each | **Clean control frequencies.** If the anomaly is Wi-Fi/spur-related, these should show clean FLRC. |
| **P2** | 2412 / 2462 MHz (Wi-Fi ch1 / ch11 edges) | ±5 MHz | Channel-edge behavior. |
| **P2** | 868 MHz | 862–870 MHz | Sub-GHz baseline. Compare FLRC-325 morphology to the HF path. |
| **P3** | 863, 865, 867, 869.5 MHz | ±1 MHz each | EU sub-band characterization. |

### 4.2 What to Capture — Per Frequency

For **each** frequency above, please record:

1. **Wide waterfall** (the full span in §4.1) — at least 60 s, to catch one full phase
   cycle. RBW ≤ 10 kHz. This shows Wi-Fi/Zigbee context and any broadband spurs.
2. **Narrow waterfall** around the carrier (±500 kHz for FLRC, ±250 kHz for LoRa), RBW
   ≤ 1 kHz, ≥10 s. This resolves the modulation shape and any narrow spurs.
3. **I/Q baseband recording** of at least 5 full FLRC-325 bursts and 5 full FLRC-2600 bursts
   for side-by-side comparison. Sample rate ≥ 5 MS/s to capture the full occupied bandwidth
   of FLRC-2600.
4. **TX-off baseline** at each P0/P1 frequency (≥30 s) — to separate DUT emissions from
   ambient.
5. **MCU-on / PA-off capture** at 2440 MHz (≥30 s) — power the RP2040 and have it idle (or
   run SPI traffic) **without** keying the LR2021 PA. Any spur present here is digital-clock
   leakage (H3), not the intended carrier.

### 4.3 Recommended Capture Modes

- **GNU Radio flowgraph** saving I/Q to file for post-hoc EVM/spectral analysis.
- **IQ.wav** (complex float32) preferred over power-only recordings.
- Tag every file with: `freq_MHz`, `span_MHz`, `phase_name` (if known), `pa_state`
  (on/off), `mcu_state` (on/idle-spi/off).

### 4.4 Phase-Identification Cheatsheet

If you want to know *which* modulation the DUT is currently emitting, the phase order in
interleave mode begins:

```
0..3   HF-LoRa-SF7    (255/32/64/128 byte)   — chirp spectrum, 812.5 kHz BW
4..7   HF-LoRa-SF9
8..11  HF-LoRa-SF12
13..16 HF-FLRC-2600   (32/64/128/255 byte)   — GFSK-like, 2.6 MHz BW
17..20 HF-FLRC-1300                          — 1.3 MHz BW
21..24 HF-FLRC-650                           — 650 kHz BW   ← anomaly band
25..28 HF-FLRC-325                           — 325 kHz BW   ← ANOMALY PRIMARY
...then LF (868 MHz) repeats the same structure...
```

FLRC phases are the "flat-top" GFSK-looking bursts; LoRa phases are the characteristic
chirp sweeps. FLRC bursts are short (<7 ms air time even for 255 bytes), so set your trigger
accordingly.

---

## 5. LR2021 SPI Command Reference (Exact Values from Firmware)

> All values below are extracted **directly** from
> `firmware/rp2040/src/multi_radio_sweep_gps_v4.cpp`. The LR2021 uses a **2-byte big-endian
> opcode** SPI protocol (NOT the 1-byte SX1280 opcodes, and NOT RadioLib's 24-bit register
> addressing). Wire sequence for a write:
> `NSS LOW → wait BUSY LOW → send [opcode_hi, opcode_lo, payload…] → NSS HIGH`.

### 5.1 Bus & Timing Constants

| Constant | Value |
|----------|-------|
| SPI clock | **20 MHz** (`SPI_FREQ_HZ 20000000UL`) |
| SPI mode | MODE 0, MSB-first |
| Reference crystal | **52.000 MHz** (`XTAL_MHZ 52.0f`) |
| TCXO voltage | **0 V** (passive crystal — no TCXO) |
| TX power | **+12.5 dBm** (`powerRaw = 25 = 0x19`) |

### 5.2 Core Command Opcodes (as sent on the wire)

| Command | Opcode (hex bytes) | Payload | Notes |
|---------|--------------------|---------|-------|
| `SET_STANDBY` | `01 28` | `[01]` = STDBY_XOSC | Used for abort/recovery. |
| `SET_RF_FREQUENCY` | `02 00` | `[frf_hi, frf_mid, frf_lo]` (3 bytes) | See §5.3. |
| `SET_PA_CONFIG` | `02 02` | `80 00 60 07 10` | Fixed value, all phases. |
| `SET_TX_PARAMS` (power) | `02 03` | `[powerRaw, 04]` | `powerRaw = round(dbm*2)`. 12.5 dBm → `0x19`. Ramp byte `0x04`. |
| `SET_RX_TX_FALLBACK_MODE` | `02 06` | `03` = **Fs** (frequency synth) | Radio returns to FS after TX. |
| `SET_PACKET_TYPE` | `02 07` | `00` = LoRa, `05` = FLRC | |
| `SET_RX_PATH` | `02 01` | `[rfPath, 00]` | **MANDATORY.** `00`=LF/868, `01`=HF/2.4G. |
| `SET_LORA_MODULATION_PARAMS` | `02 20` | `[byte0, byte1]` | See §5.4. |
| `SET_LORA_PACKET_PARAMS` | `02 21` | `00 08 [pktSize] 04` | Preamble=8, explicit header, CRC on. |
| `SET_LORA_SYNCWORD` | `02 23` | `12` = private network | |
| `SET_FLRC_MODULATION_PARAMS` | `02 48` | `[brBw, 15]` | See §5.4. `0x15` = CR 3/4 + BT 0.5. |
| `SET_FLRC_PACKET_PARAMS` | `02 49` | `0C 4C 00 [pktSize]` | See §5.4. Fixed len, CRC **off** (app-layer CRC used). |
| `SET_FLRC_SYNC_WORD` | `02 4C` | `01 12 AD 10 1B` | 1 syncword = `0x12AD101B`. |
| `SET_TX` | `02 0D` | `00 00 00` | No timeout (continuous). |
| `SET_DIO_FUNCTION` | `01 12` | `09 11` | DIO9 = IRQ. |
| `SET_DIO_IRQ_CONFIG` | `01 15` | `09 00 08 00 00` | IRQ mask = TX_DONE (bit 19). |
| `CLEAR_IRQ` | `01 16` | `FF FF FF FF` | Clear all IRQ bits. |
| `WRITE_TX_FIFO` | `00 02` | `[data…]` | Sent as opcode then payload bytes. |
| `CLEAR_TX_FIFO` | `01 1F` | — | |
| `CALIB_FE` (front-end) | `01 23` | `[feFreq_hi, feFreq_lo, 0,0, 0,0, 0,0]` | `feFreq = round(f_MHz/4)`, HF sets bit 15. See §5.5. |
| `CALIBRATE` | `01 22` | `5F` | **0x5F** (bit 5 is undefined — do NOT use 0x6F). |

### 5.3 `SET_RF_FREQUENCY` Computed Bytes (formula: `frf = freq_Hz × 2^18 / 52 MHz`)

The firmware computes the 24-bit frequency register as
`(uint32_t)((mhz * 1e6 * (1<<18)) / (52.0e6))` and sends it big-endian. Pre-computed values
for every frequency in our sweep:

| Frequency | `frf` (dec) | `frf` (hex) | Wire bytes after `02 00` |
|-----------|-------------|-------------|--------------------------|
| **2412 MHz** (Wi-Fi ch1) | 12,159,448 | `0xB989D8` | `B9 89 D8` |
| **2422 MHz** | 12,209,860 | `0xBA4EC4` | `BA 4E C4` |
| **2437 MHz** (Wi-Fi ch6) | 12,285,479 | `0xBB7627` | `BB 76 27` |
| **2440 MHz** (baseline) | 12,300,603 | `0xBBB13B` | `BB B1 3B` |
| **2442 MHz** (Wi-Fi ch7) | 12,310,685 | `0xBBD89D` | `BB D8 9D` |
| **2452 MHz** | 12,361,097 | `0xBC9D89` | `BC 9D 89` |
| **2462 MHz** (Wi-Fi ch11) | 12,411,510 | `0xBD6276` | `BD 62 76` |
| **2472 MHz** (Wi-Fi ch13) | 12,461,922 | `0xBE2762` | `BE 27 62` |
| **2478 MHz** (clean) | 12,492,169 | `0xBE9D89` | `BE 9D 89` |
| **2483 MHz** (HF max) | 12,517,376 | `0xBF0000` | `BF 00 00` |
| **868 MHz** (LF baseline) | 4,375,788 | `0x42C4EC` | `42 C4 EC` |
| **863 MHz** | 4,350,582 | `0x426276` | `42 62 76` |
| **865 MHz** | 4,360,664 | `0x4289D8` | `42 89 D8` |
| **867 MHz** | 4,370,747 | `0x42B13B` | `42 B1 3B` |
| **869.5 MHz** (hi-power sub-band) | 4,383,350 | `0x42E276` | `42 E2 76` |

> ⚠️ **Note for the SDR operator:** These are the *commanded* frequencies. Please measure
> the *actual* carrier on the waterfall and report any offset from the commanded value. A
> consistent offset would implicate crystal frequency error (the 52 MHz crystal is passive
> and uncalibrated); a jittery/phase-noisy carrier would implicate PLL settling.

### 5.4 Modulation Parameter Bytes (exact per mode)

#### 5.4.1 LoRa (`SET_LORA_MODULATION_PARAMS` `02 20 [byte0] [byte1]`)

- `byte0 = (sf << 4) | bwCode`
- `byte1 = (cr << 4) | ldro`  (LDRO auto-enabled when symbol time > 16 ms)
- Coding rate `cr = 1` (4/5) in all phases.

| Bandwidth code | Actual BW | Used on |
|----------------|-----------|---------|
| `0x0F` | 812.5 kHz | HF (2.4 GHz) LoRa |
| `0x05` | 250 kHz | LF (868 MHz) LoRa |
| `0x06` | 500 kHz | (available, unused) |
| `0x0D` | 203.125 kHz | (available, unused) |
| `0x0E` | 406.25 kHz | (available, unused) |

| Phase | SF | BW | `byte0` | `byte1` (LDRO) | Full bytes after `02 20` |
|-------|----|----|---------|----------------|--------------------------|
| HF-LoRa-SF7 | 7 | 812.5 kHz | `0x7F` | `0x10` (off) | `7F 10` |
| HF-LoRa-SF9 | 9 | 812.5 kHz | `0x9F` | `0x10` (off) | `9F 10` |
| HF-LoRa-SF12 | 12 | 812.5 kHz | `0xCF` | `0x11` (on) | `CF 11` |
| LF-LoRa-SF7 | 7 | 250 kHz | `0x75` | `0x10` (off) | `75 10` |
| LF-LoRa-SF9 | 9 | 250 kHz | `0x95` | `0x10` (off) | `95 10` |
| LF-LoRa-SF12 | 12 | 250 kHz | `0xC5` | `0x11` (on) | `C5 11` |

`SET_LORA_PACKET_PARAMS` is always `02 21 00 08 [pktSize] 04` (preamble 8 symbols, explicit
header, CRC on). Syncword is private (`02 23 12`).

#### 5.4.2 FLRC (`SET_FLRC_MODULATION_PARAMS` `02 48 [brBw] [0x15]`)

- `brBw` = bitrate/bandwidth code (see table).
- `0x15` = `(CR=3/4 [1] << 4) | (BT=0.5 [5])` = `0x15`.
  - **Note:** This differs from the TheClams reference driver, which uses `0x27` (CR=None, BT=1.0). Our firmware deliberately enables **3/4 FEC** for error correction.

| Bitrate (kbps) | Occupied BW | `brBw` code | Full bytes after `02 48` |
|----------------|-------------|-------------|--------------------------|
| 2600 | 2.6 MHz | `0x00` | `00 15` |
| 2080 | 2.08 MHz | `0x01` | `01 15` |
| 1300 | 1.3 MHz | `0x02` | `02 15` |
| 1040 | 1.04 MHz | `0x03` | `03 15` |
| **650** | **650 kHz** | **`0x04`** | **`04 15`** ← anomaly band |
| 520 | 520 kHz | `0x05` | `05 15` |
| **325** | **325 kHz** | **`0x06`** | **`06 15`** ← **ANOMALY PRIMARY** |
| 260 | 260 kHz | `0x07` | `07 15` |

> **Note on the 162 kHz BW mentioned in planning:** The current firmware does **not**
> configure a 162 kHz FLRC mode — 325 kHz (`brBw=0x06`) is the narrowest available in the
> LR2021 bitrate table as implemented. If a 162 kHz mode is desired it would require a
> different chip configuration; please flag this as "not currently emitted" rather than
> searching for it on the waterfall.

`SET_FLRC_PACKET_PARAMS` is always `02 49 0C 4C 00 [pktSize]`:

- `0x0C` → AGC preamble length = 16 bytes (`0x0C >> 2 = 3`), sync-word length field = 0.
- `0x4C` → decode per the reference layout: `(sw_tx=1 << 6) | (sw_match=1 << 3) |
  (pkt_format=Fixed=1 << 2) | (crc=Off=0)` = `0x4C`. **Hardware CRC is OFF** — integrity is
  enforced by an application-layer CRC-16/CCITT over the payload.
- `0x00 [pktSize]` → payload length big-endian (pktSize = 32, 64, 128, or 255).

`SET_FLRC_SYNC_WORD` = `02 4C 01 12 AD 10 1B` → one syncword, value **`0x12AD101B`**.
> The SDR operator should be able to see this 32-bit sync pattern in the burst preamble if
> demodulating the GFSK stream.

### 5.5 Calibration Sequence (sent at every phase change)

The TX firmware calls calibration correctly; **historically the RX firmware did not**, which
is documented as a known issue:

```
CALIB_FE (01 23):  feFreq = round(freq_MHz / 4); HF path sets bit 15.
                    e.g. 2440 MHz → feFreq = 610 | 0x8000 = 0x8262
                    bytes: 01 23 82 62 00 00 00 00 00 00
                    868 MHz  → feFreq = 217 = 0x00D9
                    bytes: 01 23 00 D9 00 00 00 00 00 00
CALIBRATE (01 22): mask = 0x5F  (bit 5 UNDEFINED — never 0x6F)
                    bytes: 01 22 5F
```

> Per the Semtech datasheet: *"If image rejection calibration was not done for current RF
> frequency, error RXFREQ_NO_CAL_ERR is generated."* If you observe an image response in the
> SDR, this is the most likely cause on the RX side.

### 5.6 Per-Phase Init Order (full sequence)

For reference, `rfInitForPhase()` issues commands in this exact order at every phase
boundary:

1. Hardware reset (RST low 200 µs, high, 50 ms)
2. `01 11 00 00` (reset regulator)
3. `01 28 01` (SET_STANDBY STDBY_XOSC)
4. `02 07 [pktType]` (SET_PACKET_TYPE)
5. `02 00 [frf]` (SET_RF_FREQUENCY)
6. `02 01 [rfPath] 00` (SET_RX_PATH)
7. `01 23 [feFreq]` (CALIB_FE) + `01 22 5F` (CALIBRATE)
8. Modulation params (LoRa `02 20`/`02 21`/`02 23` **or** FLRC `02 48`/`02 49`/`02 4C`)
9. `02 02 80 00 60 07 10` (SET_PA_CONFIG)
10. `02 03 19 04` (SET_TX_PARAMS, +12.5 dBm)
11. `02 06 03` (SET_RX_TX_FALLBACK_MODE = Fs)
12. `01 12 09 11` (SET_DIO_FUNCTION: DIO9 = IRQ)
13. `01 15 09 00 08 00 00` (SET_DIO_IRQ_CONFIG: TX_DONE)
14. `01 16 FF FF FF FF` (CLEAR_IRQ)

---

## 6. Expected Signal Characteristics

Use this section as a sanity check that you are looking at *our* signal and not an
interferer.

### 6.1 FLRC Bursts (the anomaly modes)

| Property | FLRC-2600 | FLRC-1300 | FLRC-650 | **FLRC-325** |
|----------|-----------|-----------|----------|--------------|
| Bitrate | 2600 kbps | 1300 kbps | 650 kbps | **325 kbps** |
| Occupied BW | ≈2.6 MHz | ≈1.3 MHz | ≈650 kHz | **≈325 kHz** |
| Modulation | 4-GFSK (FLRC), BT=0.5, CR 3/4 FEC | same | same | same |
| Symbol rate | 1300 ksym/s | 650 | 325 | **162.5 ksym/s** |
| Air time (64 B) | <0.5 ms | <1 ms | <2 ms | **<4 ms** |
| Air time (255 B) | <1.5 ms | <3 ms | <6 ms | **<11 ms** |
| Preamble | 16-byte AGC preamble + 32-bit syncword `0x12AD101B` | same | same | same |
| Spectral shape | Flat-top GFSK, ~4 frequency levels | narrower flat-top | narrower | **narrowest — most vulnerable to in-band spurs** |

- **Carrier:** Should be at the commanded frequency ±(crystal error). Watch for drift.
- **Power:** +12.5 dBm conducted; expect roughly **−20 to −50 dBm** at your SDR antenna
  depending on distance/gain.
- **Burstiness:** FLRC is packet-on / packet-off. Between packets the carrier disappears
  (radio returns to Fs mode). You should see **discrete flat-topped bursts**, not a CW tone.

### 6.2 LoRa Bursts

| Property | HF LoRa (BW812) | LF LoRa (BW250) |
|----------|-----------------|-----------------|
| Spreading factor | SF7 / SF9 / SF12 | SF7 / SF9 / SF12 |
| Bandwidth | 812.5 kHz | 250 kHz |
| Modulation | CSS chirp spread spectrum | CSS |
| Air time (255 B, SF12) | ~7.9 s | — (skipped, impractical) |
| Air time (32 B, SF12) | — | ~13.1 s |
| Spectral shape | Linear chirp sweeping ±BW/2 about carrier | same, narrower |

- **Diagnostic value:** LoRa chirps are easy to spot on a waterfall (sawtooth sweep). Use
  them as a beacon to confirm you have the right device and the right frequency reference.
- **Caveat:** Because LoRa phases were under-captured in our walk test (GPS-sync loss), we
  have less ground truth on LoRa RF quality. If you see anomalies on LoRa too, that broadens
  the suspect set beyond FLRC-specific AGC.

### 6.3 What a "Healthy" Capture Looks Like

- Discrete bursts at the commanded frequency with the bandwidth in §6.1/§6.2.
- No continuous carrier between bursts.
- No spurs within ±10 MHz outside the burst windows.
- FLRC bursts show ~4 levels in the instantaneous-frequency plot (4-GFSK).

### 6.4 What a "Sick" Capture Would Look Like (supporting our hypotheses)

- A **narrow CW-like spur at 2440.000 MHz** that is present even when the PA is off → H3
  (SPI clock ×122 harmonic).
- A **narrow spur at 2444.000 MHz** present whenever the MCU is powered → H3 (52 MHz crystal
  ×47).
- **Wi-Fi/Zigbee energy** overlapping the 2440 ± 2 MHz region during the TX-on windows → H1.
- **Amplitude droop or ringing** in the first 50–100 µs of each FLRC-325 burst, absent in
  FLRC-2600 bursts → H2 (AGC settling).
- A **mirror-image carrier** offset symmetrically about the LO → H4 (front-end image).

---

## 7. Specific Requests for the SDR Operator

Please prioritize the following deliverables. Each maps directly to falsifying one or more
hypotheses in §3.

### 7.1 Waterfall Plots (Required)

1. **Wide waterfall, 2420–2460 MHz, ≥60 s, TX-on.** Annotate Wi-Fi channels 5–9. Mark our
   2440 MHz baseline. (Tests H1.)
2. **Wide waterfall, 2420–2460 MHz, ≥30 s, TX-off / ambient.** Subtracted from #1 if
   possible. (Isolates DUT from ambient.)
3. **Narrow waterfall, 2438–2446 MHz, RBW ≤ 1 kHz, MCU-on / PA-off.** Look for spurs at
   **2440.000 MHz** (SPI ×122) and **2444.000 MHz** (crystal ×47). (Tests H3 — **this is the
   single highest-value capture**.)
4. **Narrow waterfall per clean frequency (2478 MHz, 2483 MHz), ≥30 s each.** Compare
   morphology to 2440 MHz. (Tests H1/H3 — if clean here, supports spur/Wi-Fi origin.)
5. **Sub-GHz waterfall, 862–870 MHz, ≥60 s.** Baseline for the LF path. (Cross-check.)

Export as PNG with frequency/time axes labeled in MHz and seconds, and include the RBW /
sample-rate in the title.

### 7.2 EVM / Modulation-Quality Measurements (Required)

For **FLRC-325** and **FLRC-2600** bursts (minimum 5 of each), capture and report:

1. **Error-Vector-Magnitude (EVM)** — RMS % and dB. Compare 325 vs 2600. If 325 EVM is
   dramatically worse, that supports H2 (AGC/settling). If both are clean, the modem is fine
   and the problem is interference/spurs (H1/H3).
2. **Constellation diagram** (4-GFSK → 4 points + their spread). Report whether the points
   are tight or smeared.
3. **Eye diagram** of the I/Q baseband across a full burst.
4. **Preamble amplitude envelope** — first 100 µs of the burst, to detect AGC transient
   (H2). Specifically: time from burst onset to amplitude-stable, in µs.
5. **Instantaneous-frequency vs time** trace over one full burst — to confirm 4-level FSK
   and detect any frequency drift / PLL pull-in.
6. **Occupied bandwidth** measurement (99 % power BW) — confirm it matches the commanded BW
   (325 kHz / 2600 kHz).

### 7.3 Spur Survey (Required — directly tests H3)

With the **PA disabled but the RP2040 running** (ideally alternating between SPI-idle and
SPI-active), perform a max-hold spur survey across:

- 2435–2445 MHz at RBW ≤ 1 kHz
- 2440 ± 100 kHz at RBW ≤ 100 Hz (resolve exact 2440.000 spur)

Report any spur within 10 dB of the noise floor that sits at a mathematically "round"
multiple of 20 MHz (SPI), 52 MHz (crystal), 48 MHz (USB), or 133 MHz (core). The two
frequencies of greatest interest are **2440.000 MHz** and **2444.000 MHz**.

### 7.4 Wi-Fi / Zigbee Context Survey (Required — directly tests H1)

During a TX-on capture window, simultaneously log:

- Active Wi-Fi APs and their channel occupancy (ch1–ch13) with RSSI.
- Any Zigbee / 802.15.4 activity (channels 11–26, i.e. 2405–2480 MHz).
- Bluetooth low-energy advertising if visible.

Report whether ch7 (2442 MHz) is occupied and at what level.

### 7.5 Carrier Accuracy (Quick check)

For the first burst at each commanded frequency in §5.3, report the **measured carrier
center frequency** and the **offset from commanded**. A consistent offset → crystal error
(passive 52 MHz XTAL); jitter/phase noise → PLL issue.

---

## 8. Logistics & Coordination

- **DUT control:** The DUT auto-cycles phases from GPS UTC. To force a specific phase, the
  operator can send `SET_TIME <unix>` over USB to set a known phase, or
  `SET_INTERLEAVE 0` to drop into the simpler 14-phase schedule. We can provide a capture
  script that logs `PHASE_START` lines so you can time-align your waterfall to the exact
  mode on air.
- **Triggering:** FLRC-2600 bursts are <1.5 ms — use a triggered/power capture, not a slow
  sweep, or you will miss them.
- **Safety:** TX power is +12.5 dBm (18 mW) — no RF safety concern, but keep your SDR input
  attenuated / use a limiter within 10 cm to avoid front-end overload.
- **Deliverables format:** PNG waterfalls, CSV/tabulated EVM + spur tables, and IQ.wav
  files named per §4.3. Please include RBW, sample rate, gain, and antenna type in each
  file's metadata or accompanying README.

---

## Appendix A — Key Numerical Relationships (Quick Reference)

- 52 MHz × **47** = **2444 MHz** (2 MHz from Wi-Fi ch7, 4 MHz from 2440 TX)
- 20 MHz × **122** = **2440 MHz** (**EXACTLY** the TX frequency)
- 48 MHz × 51 = 2448 MHz (USB clock)
- 133 MHz × 18 = 2394 MHz (RP2040 core)
- Wi-Fi channels: ch1=2412, ch6=2437, ch7=**2442**, ch11=2462, ch13=2472, ch14=2484 MHz
- LR2021 HF range: 2400–2483.5 MHz; LF range: 150–960 MHz (EU 863–870 MHz used)
- FLRC occupied BW ≈ bitrate (325 kbps → 325 kHz); 4-GFSK, BT=0.5, CR 3/4

## Appendix B — Source Files Referenced

| File | Purpose |
|------|---------|
| `firmware/rp2040/src/multi_radio_sweep_gps_v4.cpp` | TX firmware — all SPI values in §5 extracted from here |
| `data/v4-interleave-bench/ANALYSIS.md` | Phase coverage / BER=0 findings |
| `data/walk-analysis-20260724.md` | 5.7 km walk RSSI/PER data |
| `~/repos/balloon-fresh/docs/lr2021-spi-protocol-reference.md` | Authoritative SPI protocol (TheClams/RadioLib cross-reference) |

---

*End of handover document. Please direct questions to the balloon-range-tests engineering
team. The single most valuable capture you can produce is the **MCU-on / PA-off narrow
waterfall at 2440 MHz** (§7.1 #3) — it directly tests whether the 20 MHz SPI clock's 122nd
harmonic is polluting our own test frequency.*
