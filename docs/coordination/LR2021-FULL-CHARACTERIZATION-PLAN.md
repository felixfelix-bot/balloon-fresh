# LR2021 Full Characterization Plan

> **One document, two groups, four radio paths.** Each sub-manager reads this doc + their own AGENTS.md and has everything they need.

---

## 0. TL;DR — Who Does What

| Group | Owns | Delivers |
|-------|------|----------|
| **speed-tests** | HF path firmware (2.4 GHz, pin 10), SPI protocol expertise, bitrate/SF sweeps | Sustained throughput curves, TX bottleneck analysis, runtime bitrate-switch validation |
| **range-tests** | Dual-radio sweep firmware (HF+LF), outdoor test methodology, board recovery | Range-vs-PER curves, RSSI-vs-distance curves, PA characterization |

**Execution order:** Phase 0 (blockers) → Phase 1 (indoor baseline) → Phase 2 (outdoor sweep) → Phase 3 (analysis).

---

## 1. SHARED CONTEXT — Cross-Knowledge Transfer

Each group has expertise the other lacks. This section is the bridge.

### 1.1 What speed-tests knows (range-tests needs this)

#### SPI Protocol — Raw 2-Byte Opcodes

The LR2021 uses **2-byte big-endian SPI opcodes**, NOT RadioLib's 24-bit register addressing. RadioLib's LR2021 driver is DEAD on our hardware (returns -707 or hangs). See ADR-020.

```
Write:  NSS LOW → wait BUSY LOW → send [opcode_hi, opcode_lo, ...payload] → NSS HIGH
Read:   NSS LOW → wait BUSY LOW → send opcode → NSS HIGH → wait BUSY LOW
        → NSS LOW → send NOP → read [status(2) + data] → NSS HIGH
```

**SPI frequency:** 20 MHz maximum. 40 MHz corrupts FIFO writes (verified, reverted in commit `1092c3f`).

#### FLRC Bitrate Configuration

Register `brBw` byte (byte 0 of SET_FLRC_MOD_PARAMS `0x0248`):

| Code | Bitrate | Bandwidth |
|------|---------|-----------|
| 0x00 | 2600 kbps | 2666 kHz |
| 0x01 | 2080 kbps | 2222 kHz |
| 0x02 | 1300 kbps | 1333 kHz |
| 0x03 | 1040 kbps | 1333 kHz |
| 0x04 | 650 kbps | 888 kHz |
| 0x05 | 520 kbps | 769 kHz |
| 0x06 | 325 kbps | 444 kHz |
| 0x07 | 260 kbps | 444 kHz |

Byte 1: `(coding_rate << 4) | pulse_shape`. CR: 0=1/2, 1=3/4, 2=none(uncoded), 3=2/3. Shape: 0x05=BT0.5, 0x07=BT1.0. Working default: `0x25` = CR_None + BT_0.5.

#### TX SPI Bottleneck

Sustained throughput is **TX-limited, not RX-limited**. Per-packet breakdown:
- RF air time: 803 µs (54%) — physics, cannot reduce
- Arduino SPI FIFO write: 535 µs (36%) — only working path
- Loop overhead: 154 µs (10%)
- **Total: ~1492 µs/packet = 1377 kbps ceiling**

All DMA, PIO, direct-register, and batch-SPI acceleration attempts FAILED on real hardware. The LR2021 appears to require Arduino `transfer()` inter-byte timing. A logic analyzer capture ($20, 1 afternoon) is the highest-value untried diagnostic.

RX blind window: ~572 µs per packet (IRQ read + FIFO read + clear + re-arm). At current TX rate there's 920 µs of RX listening between packets, so 0% loss.

#### Power Encoding

```c
uint8_t powerRaw = (uint8_t)(dBm * 2.0f + 0.5f);
// SET_TX_PARAMS: {0x02, 0x03, powerRaw, 0x04}
```
Examples: 0 dBm → 0x00, 6 dBm → 0x0C, 12 dBm → 0x18, 12.5 dBm → 0x19.

#### FLRC Bitrate Sweep Results (VERIFIED, indoor 1-2m, 12 dBm)

All 4 bitrates: **0% PER** at indoor range.

| Bitrate | Sustained Throughput | Efficiency | RSSI |
|---------|---------------------|------------|------|
| 2600 | 1485 kbps | 57.1% | -71 dBm |
| 1300 | 806 kbps | 62.0% | -71 dBm |
| 650 | 420 kbps | 64.6% | -73 dBm |
| 325 | 240 kbps | 73.8% | -73 dBm |

Efficiency increases at lower bitrates because fixed TX SPI overhead (~680 µs) is a smaller fraction of longer air time.

### 1.2 What range-tests knows (speed-tests needs this)

#### Dual-Radio Sweep Firmware — ALREADY BUILT

`dual_radio_sweep_tx.cpp` + `dual_radio_sweep_rx.cpp` cycle 4 modes in one binary, auto-starting after 3s LED countdown:

| Mode | Duration | Config |
|------|----------|--------|
| 0 | 0-3 min | HF FLRC 2600 kbps @ 2440 MHz (pin 10) |
| 1 | 3-6 min | HF FLRC 325 kbps @ 2440 MHz (pin 10) |
| 2 | 6-9 min | LF LoRa SF7 @ 868 MHz (pin 9) |
| 3 | 9-12 min | LF LoRa SF12 @ 868 MHz (pin 9) |

Also available: `multi_radio_sweep.cpp` (speed-tests worktree) — 10-phase cycle including all 3 LoRa SFs + all 4 FLRC bitrates on HF, plus 3 LoRa SFs on LF. Uses `0x05` for FLRC packet type (vs `0x04` in range-tests — **both work**, likely 0x04/0x05 are aliases).

#### Outdoor Test Methodology — PROVEN

1. Flash both boards (TX + RX). Verify 0% PER at 1m.
2. TX board → USB power bank (needs >50mA dummy load to prevent auto-shutoff).
3. RX board → laptop USB, serial log via `tee`.
4. TX auto-starts 3s after power-on (LED countdown blink).
5. Walk away carrying TX. RX stays put.
6. Phone GPS app records track (GPX export).
7. Dwell 30s at each distance marker.
8. Correlate GPS timestamps with RX `uptime_ms` fields.

#### PA Is BINARY — No Linear Power Control

Register codes 0-24 (0.0-12.0 dBm): **PA bypassed**. All identical ~4% PER. RSSI -103 dBm.
Register code 25 (12.5 dBm): **PA enabled**. ~43 dB RSSI jump. ~0% PER.

There is NO intermediate power level. The SET_TX_PARAMS opcode works, but below code 25 the chip disables the PA entirely. **Only two TX power states exist: PA-off (~0 dBm effective) and PA-on (~12.5 dBm).**

#### Board Recovery Protocol

If USB CDC disappears (radio init hang):
1. Try **1200 baud trigger** — open serial at 1200 baud, close. May reset.
2. If that fails: **ESP32 BOOTSEL pulse** — flash `bootsel_oneshot.cpp` to paired ESP32. It pulses GPIO to RP2040 RUN/BOOOT pins every 5s → board enters BOOTSEL mode.
3. After BOOTSEL recovery: copy `.uf2` via mass storage (RPI-RP2). Board reboots automatically.
4. **ALWAYS** reflash ESP32 with UART bridge firmware after recovery (to stop the BOOTSEL loop).

**Reliable flash method:** UF2 mass storage copy. `picotool` needs `-v -x` flags or silently fails.

#### 868 MHz LF Path Configuration

```
SET_RX_PATH (0x0201): byte0=0x00 (LF path)  [vs 0x01 for HF]
CALIB_FRONT_END (0x0123): NO bit 15 for LF  [bit 15 set for HF]
```

LF CALIB_FRONT_END: `feFreq = (uint16_t)((868.0/4.0) + 0.5)` — do NOT OR with `0x8000`.
HF CALIB_FRONT_END: `feFreq = (uint16_t)((2440.0/4.0) + 0.5) | 0x8000`.

#### RSSI Measurement — FIXED (was broken for 8+ sessions)

**FLRC RSSI:** `GET_FLRC_PACKET_STATUS (0x024B)`, 9-bit assembly:
```c
uint16_t raw = ((uint16_t)buf[4] << 1) | ((buf[6] & 0x04) >> 2);
int16_t rssi = -(int16_t)(raw / 2);  // dBm
```

**LoRa RSSI:** `GET_LORA_PACKET_STATUS (0x022A)`:
```c
int16_t rssi = -(int16_t)(buf[2] / 2);  // dBm
int8_t snr = buf[3] < 128 ? buf[3]/4 : (buf[3]-256)/4;  // dB
```

**DO NOT use:** SX1280 register 0x0104 (returns garbage), SX1280 register 0x022A for FLRC (returns -127 or -8 regardless of signal). The old RSSI bug was: raw firmware used SX1280's GET_PACKET_STATUS (0x0104) instead of LR2021's GET_FLRC_PACKET_STATUS (0x024B).

#### LoRa Modulation Parameter Encoding

`SET_LORA_MOD_PARAMS (0x0220)`: `[0x02, 0x20, byte0, byte1]`
- byte0: `((sf & 0x0F) << 4) | (bwCode & 0x0F)` — SF is direct value (7-12), BW codes below
- byte1: `((cr & 0x0F) << 4) | (ldro & 0x01)` — CR: 1=4/5, 2=4/6, 3=4/7, 4=4/8. **CR=5 is INVALID** (causes 0 packets at SF9/SF12).

| BW | Code | 
|----|------|
| 812.5 kHz | 0x0F |
| 406.25 kHz | 0x0E |
| 203.125 kHz | 0x0D |
| 250 kHz | 0x05 |

LDRO auto-enable: `symTimeMs > 16.0` → enable. Only SF12 @ 203 kHz triggers this in practice.

**Common LoRa configs (CR=4/5, LDRO=off → byte1=0x10):**

| SF | BW | byte0 | SPI Frame |
|----|-----|-------|-----------|
| SF7 | 812 kHz | 0x7F | `{0x02, 0x20, 0x7F, 0x10}` |
| SF9 | 812 kHz | 0x9F | `{0x02, 0x20, 0x9F, 0x10}` |
| SF12 | 812 kHz | 0xCF | `{0x02, 0x20, 0xCF, 0x10}` |

### 1.3 Knowledge Both Groups Share

#### Mandatory Init Sequence (ALL modes)

```
1. SET_STANDBY (0x0200, STDBY_RC=0x01)     — known state
2. SET_PACKET_TYPE (0x0207)                 — LoRa=0x00, FLRC=0x04 (or 0x05)
3. SET_RF_FREQUENCY (0x0200)                — freq in Hz, 3-byte big-endian
4. SET_RX_PATH (0x0201)                     — HF=0x01, LF=0x00 [MANDATORY]
5. CALIB_FRONT_END (0x0123)                 — HF: bit15 set, LF: no bit15 [MANDATORY]
6. CALIBRATE (0x0122)                       — mask 0x5F [NOT 0x6F — bit 5 undefined]
7. SET_MOD_PARAMS (0x0248 FLRC / 0x0220 LoRa)
8. SET_PACKET_PARAMS (0x0249 FLRC / 0x0221 LoRa)
9. SET_PA_CONFIG (0x0202)                   — {0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10}
10. SET_TX_PARAMS (0x0203)                  — powerRaw = dBm*2, ramp=0x04
11. SET_RX_TX_FALLBACK (0x0206)             — FS=0x03
12. SET_DIO_FUNCTION (0x0112)               — DIO9=IRQ: {0x01, 0x12, 0x09, 0x11}
13. SET_DIO_IRQ_CONFIG (0x0115)             — RX_DONE=bit18, TX_DONE=bit19
14. CLEAR_IRQ (0x0116)                      — all: {0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF}
```

#### IRQ Bits (32-bit, NOT 16-bit like SX1280)

| Bit | Name | Value |
|-----|------|-------|
| 16 | ERROR | 0x00010000 |
| 17 | CMD_ERROR | 0x00020000 |
| 18 | RX_DONE | 0x00040000 |
| 19 | TX_DONE | 0x00080000 |
| 21 | TIMEOUT | 0x00200000 |
| 22 | CRC_ERROR | 0x00400000 |

#### FIFO Race Bug — SOLVED

RX must poll IRQ via GPIO (`sio_hw->gpio_in` on GP7/DIO9), NOT via SPI read. SPI IRQ polling takes ~50µs during which the chip starts receiving the next packet and overwrites the FIFO. GPIO polling is nanosecond latency. Commit `3dcddaf`.

#### BoardSerial Wrapper — MANDATORY

ALL serial access MUST go through `BoardSerial()`, not `serial.Serial()`:
```python
from board_serial import BoardSerial
ser = BoardSerial('/dev/ttyACM0', 115200)  # checks flock before opening
```
Raw `serial.Serial()` on `/dev/ttyACM*` is a BUG. The wrapper refuses to open ports if the calling track doesn't hold the flock.

---

## 2. UNIFIED TEST MATRIX

Four radio paths × modulation parameters × distances × power levels.

### 2.1 Radio Paths

| # | Path | Freq | Antenna Pin | Modulation | Status |
|---|------|------|-------------|------------|--------|
| A | HF FLRC | 2440 MHz | Pin 10 (2.4G) | FLRC | ✅ VERIFIED |
| B | HF LoRa | 2440 MHz | Pin 10 (2.4G) | LoRa | ✅ VERIFIED |
| C | LF LoRa | 868 MHz | Pin 9 (ANT) | LoRa | ✅ VERIFIED |
| D | LF FLRC | 868 MHz | Pin 9 (ANT) | FLRC | ⚠️ UNTESTED — may not be supported |

### 2.2 Modulation Parameters per Path

**FLRC paths (A, D):** 4 bitrates × {PA-off, PA-on} = 8 configs per path

| Bitrate (kbps) | brBw Code | Air time/pkt |
|----------------|-----------|-------------|
| 2600 | 0x00 | ~0.39 ms |
| 1300 | 0x02 | ~0.78 ms |
| 650 | 0x04 | ~1.56 ms |
| 325 | 0x06 | ~3.12 ms |

**LoRa paths (B, C):** 3 spreading factors × {PA-off, PA-on} = 6 configs per path

| SF | BW | CR | Time/pkt (127B) |
|----|----|----|-----------------|
| SF7 | 812 kHz | 4/5 | ~6 ms |
| SF9 | 812 kHz | 4/5 | ~25 ms |
| SF12 | 812 kHz | 4/5 | ~800 ms |

> **Note:** Range-tests used BW=250 kHz (code 0x05) for LF LoRa in sweep firmware. Speed-tests used BW=812 kHz (0x0F). For the unified matrix, standardize on **BW=812 kHz for HF** and **BW=250 kHz for LF** (better sub-GHz sensitivity). Document which BW was used in every CSV row.

### 2.3 Distance Points

| Environment | Distances |
|-------------|-----------|
| Indoor (baseline) | 0.3m, 1m, 2m |
| Outdoor LOS | 10m, 25m, 50m, 100m, 200m, 500m |
| Outdoor LOS (stretch) | 1000m+ (if 500m still 0% PER) |

> Dwell time: 30s minimum per point (ensures ≥1 full burst capture). For LoRa SF12, dwell 60s (packets are slow).

### 2.4 Power Levels

Only **two** meaningful states (PA is binary):

| State | powerRaw | dBm | PER (indoor) |
|-------|----------|-----|-------------|
| PA-off | 0x00 | ~0 effective | ~4% |
| PA-on | 0x19 | 12.5 | ~0% |

> For the full matrix, test BOTH states at each distance. PA-off gives us a "weaker TX" for free — useful for indoor/close-range where PA-on saturates the receiver.

### 2.5 Full Matrix Size

| Path | Configs | Distances | Power | Total Points |
|------|---------|-----------|-------|-------------|
| HF FLRC | 4 bitrates | 9 | 2 | 72 |
| HF LoRa | 3 SFs | 9 | 2 | 54 |
| LF LoRa | 3 SFs | 9 | 2 | 54 |
| LF FLRC | 4 bitrates | 9 | 2 | 72 |
| **Total** | | | | **252** (if LF FLRC works) |

Reality: ~180 points if LF FLRC is unsupported. Prioritize by value (see execution order).

---

## 3. UNIFIED CSV OUTPUT FORMAT

ALL test results use this single CSV schema. Both groups' firmware outputs this format.

### 3.1 Per-Burst Result Line

```
LR2021_RESULT,timestamp_iso,path={HF_FLRC|HF_LORA|LF_LORA|LF_FLRC},freq_mhz={2440|868},modulation={FLRC|LORA},bitrate_kbps={2600|1300|650|325|0},spreading_factor={0|7|9|12},bandwidth_khz={812|406|250|203},coding_rate={45|46|47|48|0},tx_power_dbm={0.0|12.5},pa_state={OFF|ON},distance_m={0.3|1|2|10|25|50|100|200|500|1000},los={Y|N},packets_sent={N},packets_rx={N},packets_unique={N},per_percent={F},throughput_kbps={F},rssi_avg_dbm={I},rssi_min_dbm={I},rssi_max_dbm={I},snr_avg_db={F|NA},pkt_size_bytes={127|255},uptime_ms={N},notes={free_text}
```

### 3.2 Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `timestamp_iso` | ISO 8601 | Wall-clock time of burst start (GPS-correlated) |
| `path` | enum | HF_FLRC, HF_LORA, LF_LORA, LF_FLRC |
| `freq_mhz` | int | 2440 or 868 |
| `modulation` | enum | FLRC or LORA |
| `bitrate_kbps` | int | FLRC only; 0 for LoRa |
| `spreading_factor` | int | LoRa only; 0 for FLRC |
| `bandwidth_khz` | int | Actual BW used |
| `coding_rate` | int | 45=4/5, 46=4/6, etc.; 0 for FLRC uncoded |
| `tx_power_dbm` | float | Requested power (0.0 or 12.5) |
| `pa_state` | enum | OFF (codes 0-24) or ON (code 25) |
| `distance_m` | float | TX-RX separation (GPS or measured) |
| `los` | bool | Y = clear line-of-sight, N = obstructed |
| `packets_sent` | int | From TX DEADBEEF marker |
| `packets_rx` | int | Total received (including dups) |
| `packets_unique` | int | Unique sequence numbers |
| `per_percent` | float | (sent - unique) / sent × 100 |
| `throughput_kbps` | float | Measured goodput |
| `rssi_avg_dbm` | int | Average RSSI across received packets |
| `rssi_min_dbm` | int | Worst (most negative) RSSI |
| `rssi_max_dbm` | int | Best RSSI |
| `snr_avg_db` | float | LoRa only; NA for FLRC |
| `pkt_size_bytes` | int | 127 (LoRa) or 255 (FLRC) |
| `uptime_ms` | int | RX board uptime (for GPS correlation) |
| `notes` | string | Free text (e.g., "multipath suspected", "antenna orientation: vertical") |

### 3.3 Firmware Output Convention

Both sweep firmwares already output structured lines (`SWEEP_TX_RESULT`, `RANGE_RESULT_RX`). The unified format above is a **superset**. Migration path:
1. Add `path`, `pa_state`, `los`, `distance_m` fields to existing firmware output.
2. `distance_m` and `los` are filled post-test from GPS correlation (not in firmware output).
3. `pa_state` is derived from `tx_power_dbm >= 12.5 ? ON : OFF`.

---

## 4. TASK ASSIGNMENTS

### 4.1 speed-tests Tasks

| ID | Task | Deliverable | Depends On |
|----|------|-------------|------------|
| S1 | **Validate runtime bitrate switching** — flash dual_radio_sweep, confirm RSSI/PER differs between 2600 and 325 windows at same distance | Test report confirming mode-switch works mid-cycle | Phase 0 |
| S2 | **Complete LoRa sustained sweep** — SF7/SF9/SF12 at HF 2440 MHz, sustained throughput | 3 data rows filling Phase 2 of sustained-throughput doc | ESP32 bridge recovery |
| S3 | **HF LoRa power sweep** — repeat power sweep at SF7/SF9/SF12 (verify PA binary behavior in LoRa mode) | 6 data points (3 SFs × 2 PA states) | S2 |
| S4 | **Add unified CSV fields to multi_radio_sweep.cpp** — add `path`, `pa_state` to SWEEP_TX_RESULT output | Patched firmware | S1 |
| S5 | **TX bottleneck logic analyzer capture** — capture working vs failing SPI transactions | Diagnostic data, root cause for PIO/DMA failures | Hardware ($20 analyzer) |

### 4.2 range-tests Tasks

| ID | Task | Deliverable | Depends On |
|----|------|-------------|------------|
| R1 | **Extend dual_radio_sweep to full matrix** — add HF LoRa SF7/SF9/SF12 modes, add LF FLRC mode (test if supported) | Updated firmware with 10+ modes | Phase 0 |
| R2 | **Indoor baseline at all distances (0.3/1/2m)** — run full sweep at desk-top range | CSV with ~20 baseline rows | R1 |
| R3 | **Outdoor LOS sweep** — 10/25/50/100/200/500m, HF FLRC + LF LoRa | CSV with ~100+ outdoor rows | R2 |
| R4 | **RSSI validation at distance** — confirm RSSI follows free-space path loss curve | Validation report (RSSI vs expected curve) | R3 |
| R5 | **LF FLRC feasibility test** — attempt FLRC on 868 MHz path, report if chip supports it | Go/no-go for Path D | R1 |
| R6 | **Powerbank dummy load fix** — ensure TX runs >30 min on battery without auto-shutoff | Working battery-powered TX setup | None |

### 4.3 Shared Tasks (either group, coordinate via board lock)

| ID | Task | Deliverable |
|----|------|-------------|
| X1 | **Unify CSV parser** — single Python script that parses both `SWEEP_TX_RESULT` and `RANGE_RESULT_RX` into unified CSV | `tools/parse_unified_csv.py` |
| X2 | **Plotting script** — PER vs distance, RSSI vs distance, throughput vs bitrate, one PNG per radio path | `tools/plot_characterization.py` |
| X3 | **Sync `board_serial.py` to both worktrees** — ensure both have latest wrapper | Symlink or copy |

---

## 5. EXECUTION ORDER

```
Phase 0: BLOCKERS (both groups, parallel)
├── [S2] Recover ESP32 bridge (physical USB reconnect)
├── [R6] Fix powerbank auto-shutoff (dummy load)
├── [X3] Sync board_serial.py to both worktrees
└── [R5] LF FLRC feasibility quick-test (10 min, determines if Path D exists)
         │
         ▼
Phase 1: INDOOR BASELINE (range-tests leads, speed-tests supports)
├── [S1] Validate runtime bitrate switching
├── [R1] Extend sweep firmware to full mode list
├── [R2] Indoor baseline sweep (0.3/1/2m, all configs)
├── [S2] Complete LoRa sustained sweep (if bridge recovered)
└── [S3] LoRa power sweep
         │
         ▼
Phase 2: OUTDOOR SWEEP (range-tests executes, speed-tests analyzes)
├── [R3] Outdoor LOS sweep (10→500m)
│   ├── Day 1: HF FLRC all bitrates, PA-on + PA-off
│   ├── Day 2: HF LoRa all SFs, PA-on + PA-off
│   └── Day 3: LF LoRa all SFs (if LF FLRC works, add it)
├── [R4] RSSI validation at distance
├── [S5] Logic analyzer capture (independent, indoor)
└── [X1][X2] Build parser + plotter (can start during Phase 1)
         │
         ▼
Phase 3: ANALYSIS & DELIVERY
├── Merge all CSVs into unified dataset
├── Generate characterization report:
│   ├── Range-vs-PER curves (4 paths overlaid)
│   ├── RSSI-vs-distance curves (validation against FSPL)
│   ├── Throughput-vs-bitrate curves (FLRC)
│   ├── Sensitivity comparison (SF7 vs SF9 vs SF12)
│   └── PA impact quantification (on vs off, dB improvement)
└── Define adaptive protocol thresholds for flight firmware
```

### Dependency Graph (visual)

```
Phase 0                    Phase 1                 Phase 2              Phase 3
───────                    ────────                ────────             ────────
ESP32 bridge ──────────► LoRa sustained ───────► Outdoor LoRa ──────► Report
                     ┌──► sweep (S2)          (R3 Day 2)
Powerbank fix (R6) ──┤
                     ├──► Indoor baseline ────► Outdoor FLRC ──────► Report
LF FLRC test (R5) ───┘    (R2)               (R3 Day 1)
                          
Bitrate switch (S1) ─────► Firmware patch ───► Outdoor sweep uses
                           (S4, R1)           unified CSV
```

---

## 6. BOARD ACCESS COORDINATION PROTOCOL

### 6.1 Hardware Inventory

| Board | Serial | Role | Port (typical) |
|-------|--------|------|----------------|
| RP2040 #1 | E663B035973B8332 | RX | /dev/ttyACM2 (via ESP32 bridge) |
| RP2040 #2 | E663B035977F242D | TX | /dev/ttyACM0 (via ESP32 bridge) |
| ESP32 bridge A | — | UART bridge for 8332 | paired with ACM2 |
| ESP32 bridge B | — | UART bridge for F242D | paired with ACM0 |

> **Port assignments swap on every reboot/reflash.** Always verify with `ls /dev/ttyACM*` and `udevadm info -q property -n /dev/ttyACM*`.

### 6.2 Lock Acquisition — MANDATORY

```bash
# Acquire BOTH boards atomically
BALLOON_TRACK=speed-tests python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire both --purpose "LoRa sustained sweep"

# Check who holds the lock
python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py status

# Release when done
BALLOON_TRACK=speed-tests python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py release both
```

### 6.3 Rules

1. **ALWAYS acquire before ANY serial access.** The `BoardSerial()` wrapper enforces this at the Python level.
2. **Acquire BOTH boards atomically.** Partial lock (TX only or RX only) is a bug.
3. **Release immediately after test completes.** Don't hold locks idle.
4. **Set `BALLOON_TRACK` env var** before any board operation:
   - `export BALLOON_TRACK=speed-tests`
   - `export BALLOON_TRACK=range-tests`
5. **Monitor cron runs every 60s** checking `fuser /dev/ttyACM*` against flock holders. Violations are reported to orchestrator.
6. **If a board is stuck/unresponsive:** do NOT force-access. Post in your status report. The other group may have context on recovery.

### 6.4 Outdoor Test Board Protocol

During outdoor tests, the TX board runs on battery (no USB to host). The RX board stays on laptop. **Only the RX board needs the serial lock** during outdoor testing. The TX board is flashed and locked BEFORE going outside, then unplugged from USB and connected to power bank. The lock is released for TX after unplugging.

```
1. Acquire both locks (BALLOON_TRACK=range-tests)
2. Flash TX + RX firmware
3. Verify 1m baseline
4. Unplug TX from USB → connect power bank
5. Release TX lock (TX is now autonomous, no serial needed)
6. Keep RX lock (laptop monitoring)
7. Go outside, run test
8. Return, release RX lock
```

---

## 7. KNOWN ISSUES & MITIGATIONS

### 7.1 RSSI Saturation at Close Range

At 1-2m indoor, RSSI reads constant (-8 dBm) regardless of TX power. Receiver front-end is saturated. **Mitigation:** All meaningful RSSI data must come from outdoor tests at ≥10m. Use PA-off mode for close-range baseline (weaker signal, may avoid saturation).

### 7.2 Timing Drift Between Free-Running Boards

Two RP2040s drift 5-10s per ~100s cycle. Sweep firmware phases misalign. **Mitigation:**
- Short cycles (12 min) with 3-min phases are worst case
- **Preferred fix:** Use compile-time single-config firmware for critical measurements (one bitrate/SF per flash). Eliminates sync entirely.
- Sweep firmware is for quick characterization only, not precision measurement.

### 7.3 ESP32 Bridge WDT Crash

Rapid pyserial open/close cycles crash the ESP32 UART bridge (watchdog timeout). **Mitigation:**
- Use persistent serial connections (`dsrdtr=False`)
- Use `BoardSerial()` wrapper (keeps connection alive)
- Physical USB reconnect to recover
- Flash `bootsel_oneshot.cpp` to recover stuck RP2040

### 7.4 RP2040 USB CDC Output Unreliable

RP2040 direct USB CDC (Serial.print) is unreliable with earlephilhower core. Output doesn't appear. **Mitigation:** UART bridge via ESP32 (GP12/GP13 → ESP32 → USB CDC) is the only reliable serial path. All sweep firmware uses `dualPrint()` (both Serial + Serial1).

### 7.5 4% PER at PA-Off

Consistent ~4% PER at all non-PA power levels. Likely indoor multipath + no CRC + SPI bus contention. **Mitigation:** Enable CRC in FLRC packet params to distinguish corrupted packets from truly lost. Expected to drop to ~0% outdoors with LOS.

---

## 8. QUICK REFERENCE — Opcodes & Configs

### Verified SPI Opcodes

| Command | Opcode | Payload |
|---------|--------|---------|
| SET_STANDBY | 0x0200 | 0x01 = STDBY_RC |
| SET_PACKET_TYPE | 0x0207 | LoRa=0x00, FLRC=0x04 |
| SET_RF_FREQUENCY | 0x0200 | 3-byte freq (big-endian) |
| SET_RX_PATH | 0x0201 | HF=0x01, LF=0x00 |
| CALIB_FRONT_END | 0x0123 | HF: freq\|0x8000, LF: freq only |
| CALIBRATE | 0x0122 | 0x5F (NOT 0x6F) |
| SET_FLRC_MOD_PARAMS | 0x0248 | [brBw, crBt] |
| SET_LORA_MOD_PARAMS | 0x0220 | [sfBw, crLdro] |
| SET_PA_CONFIG | 0x0202 | {0x80, 0x00, 0x60, 0x07, 0x10} |
| SET_TX_PARAMS | 0x0203 | [powerRaw, 0x04] |
| SET_RX | 0x020C | [0xFF, 0xFF, 0xFF] = continuous |
| SET_TX | 0x020D | [0x00, 0x00, 0x00] |
| WRITE_TX_FIFO | 0x0002 | + data bytes |
| READ_RX_FIFO | 0x0001 | → data bytes |
| GET_FLRC_PACKET_STATUS | 0x024B | → 9-bit RSSI |
| GET_LORA_PACKET_STATUS | 0x022A | → RSSI + SNR |
| GET_AND_CLEAR_IRQ | 0x0117 | → 32-bit IRQ |
| CLEAR_IRQ | 0x0116 | {0xFF, 0xFF, 0xFF, 0xFF} |
| SET_DIO_FUNCTION | 0x0112 | DIO9 IRQ: {0x09, 0x11} |
| SET_DIO_IRQ_CONFIG | 0x0115 | DIO9 RX+TX: {0x09, 0x00, 0x0C, 0x00, 0x00} |

### Frequency Encoding

```c
uint32_t frf = (uint32_t)((freq_MHz * 1e6 * (1ULL << 18)) / (XTAL_MHz * 1e6));
// XTAL_MHz = 52.0 for NiceRF LoRa2021 module (XTAL, not TCXO — tcxoVoltage=0)
// 2440 MHz → frf = 0x916800
// 868 MHz  → frf = 0x337000
```

### Expected RSSI vs Distance (Free-Space, 2440 MHz, 12.5 dBm TX)

| Distance | Path Loss | Expected RSSI |
|----------|-----------|---------------|
| 1m | 40 dB | -27 dBm |
| 10m | 60 dB | -47 dBm |
| 50m | 74 dB | -61 dBm |
| 100m | 80 dB | -67 dBm |
| 500m | 94 dB | -81 dBm |
| 1000m | 100 dB | -87 dBm |

Formula: `RSSI = TX_power - 20*log10(d) - 20*log10(f_MHz) + 27.55`

At 868 MHz: subtract 9 dB less path loss than 2440 MHz at same distance.

---

## 9. REFERENCE FILES

| File | Location | What It Contains |
|------|----------|------------------|
| SPI Protocol Reference | `docs/lr2021-spi-protocol-reference.md` | Full init sequence, all opcodes |
| SPI Command Reference | `docs/lr2021-spi-command-reference.md` | Opcode cross-ref, bug analysis |
| LoRa Mod Params Encoding | `docs/lr2021-lora-modulation-params-encoding.md` | Byte-level LoRa config |
| SPI Bottleneck Analysis | `docs/lr2021-spi-bottleneck-analysis-2026-07-16.md` | Why acceleration failed |
| Complete Learnings | `docs/lr2021-complete-learnings-2026-07-23.md` | All consolidated knowledge |
| RSSI Fix Plan | `docs/RSSI-FIX-PLAN.md` | RSSI bug root cause + fix |
| Bitrate Sweep Results | `docs/flrc-bitrate-sweep-results-2026-07-23.md` | 4-bitrate FLRC data |
| Sustained Throughput | `docs/sustained-throughput-results-2026-07-23.md` | 50K-packet sustained data |
| Power Sweep Results | `docs/power-sweep-results-2026-07-24.md` | PA binary behavior data |
| Multi-Radio Sweep Results | `docs/SWEEP-RESULTS.md` | All 10-phase dual-band data |
| Power Sweep v2 | `tests/power-sweep-v2-results.md` | 6-level power sweep data |
| Outdoor Test Procedure | `docs/OUTDOOR-TEST-PROCEDURE.md` | Step-by-step outdoor guide |
| Board Mutex Plan | `docs/coordination/BOARD-MUTEX-ENFORCEMENT-PLAN.md` | Lock system architecture |
| Dual Radio Sweep TX | `firmware/rp2040/src/dual_radio_sweep_tx.cpp` | Range-tests sweep TX |
| Dual Radio Sweep RX | `firmware/rp2040/src/dual_radio_sweep_rx.cpp` | Range-tests sweep RX |
| Multi-Radio Sweep | `firmware/rp2040/src/multi_radio_sweep.cpp` | Speed-tests 10-phase sweep |
| BoardSerial Wrapper | `tools/board_serial.py` | Mandatory serial wrapper |

> Files without a worktree prefix exist in BOTH worktrees (shared via git). Check your local copy.

---

*Document version: 1.0 — 2026-07-24*
*Owner: balloon-hermes orchestrator*
*Read by: speed-tests sub-manager, range-tests sub-manager*
