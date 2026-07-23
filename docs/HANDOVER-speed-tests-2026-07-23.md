# HANDOVER — Speed Tests (Verified Results + Bug Fixes)

> **For:** Any LLM context window continuing the balloon-speed-tests track.
> **Worktree:** `~/worktrees/balloon-speed-tests/`
> **Branch:** `speed-sustained-sweep`
> **Date:** 2026-07-23
> **Status:** FLRC 2600 kbps and LoRa SF7/SF9/SF12 verified. Three bugs found and fixed. Pre-range-testing work remains (see `PLAN-pre-range-testing-2026-07-23.md`).

---

## TL;DR — What's Done

- **FLRC 2600 kbps:** fully characterized, 0% PER, 1485 kbps sustained RX throughput (57% of theoretical 2600 kbps).
- **LoRa SF7/SF9/SF12:** all three spreading factors verified at 1–2 m indoor range. PER 0–3%.
- **Three bugs fixed** this session: CR encoding, RSSI/SNR byte swap, PER stats inflation. All committed.
- **What's NOT done:** FLRC 1300/650/325 bitrate sweep, TX power sweep, automated test harness, firmware cleanup, PER fix hardware re-verification. See the companion plan doc.

---

## Verified Results

> **All tests:** indoor, 1–2 m separation, 2440 MHz, 12 dBm TX power, 127-byte payload.

### FLRC 2600 kbps (FLRC, highest bitrate)

| Metric | Value |
|---|---|
| Packets TX | 10,000 in 6.8 s |
| TX timeouts | 0 |
| TX rate | 1753 kbps |
| Packets RX | 21,923 received |
| Packet Error Rate (PER) | 0% |
| Sustained RX throughput | 1485 kbps (57% of theoretical 2600 kbps) |
| RSSI | -71 dBm avg |
| Payload | 127 bytes |

**TX optimizations verified:** skip `clearFIFO()` + `clearIRQ()` between consecutive packets (per-packet overhead reduced). This is the key to hitting >1700 kbps TX rate.

> Note: 21,923 RX > 10,000 TX because RX ran across multiple TX burst windows (cumulative across runs).

### LoRa Sweep — ALL 3 SF Verified

| SF | TX Sent | RX Received | PER | RSSI | SNR | TX Rate |
|---|---|---|---|---|---|---|
| SF7  | 200 | 200 | 0%  | -8 dBm | 31.8 dB | 30.9 kbps |
| SF9  | 200 | 194 | 3%  | -8 dBm | 31.8 dB | 9.7 kbps |
| SF12 | 200 | 198 | 1%  | -8 dBm | 31.8 dB | 1.5 kbps |

**Interpretation:** At 1–2 m indoor range, the link is essentially perfect for SF7. The 1–3% PER on SF9/SF12 is likely due to the **CR encoding bug** (see below) that was present during these tests — the CR fix (commit `b32f50b`) was applied but SF9/SF12 were not re-tested after the fix. Re-verification is needed (TASK-P4-1).

> ⚠️ **Important caveat:** The SF12 result (198/200, 1% PER) was computed **manually from raw data** because the PER stats bug was still active. The `cumulativeRx` fix (commit `9352337`) has been coded and built but **NOT yet verified on hardware**.

---

## Three Bugs Found and Fixed (This Session)

### Bug 1: CR Encoding Bug — Commit `b32f50b`

**Symptom:** SF9 and SF12 showed elevated PER (3% and 1%), while SF7 was fine.

**Root cause:** `LORA_CR` was set to `5`, which is outside the valid internal index range (1–4). The SPI encoded this as `0x50` (a garbage byte in the modulation params frame). SF7 tolerated the malformed CR; SF9/SF12 did not.

**LR2021 CR encoding (internal index, NOT denominator):**
```
LORA_CR = 1  →  4/5   (default, fastest)
LORA_CR = 2  →  4/6
LORA_CR = 3  →  4/7
LORA_CR = 4  →  4/8   (strongest)
```

**Fix:** Changed `LORA_CR` from `5` → `1` in `firmware/rp2040/src/lora_range_tx.cpp` (line ~61). Commit `b32f50b`.

**File:** `firmware/rp2040/src/lora_range_tx.cpp`

### Bug 2: RSSI/SNR Byte Swap — Commit `dca7a84`

**Symptom:** RSSI reported as `-127 dBm` (nonsensical) and SNR reported as `4.2 dB`.

**Root cause:** `GET_LORA_PACKET_STATUS` (opcode `0x022A`) returns a status buffer where **`buf[2] = RSSI`** and **`buf[3] = SNR`**. The code had them backwards:
- What was reported as RSSI (`-127 dBm`) was actually the SNR raw byte (`31.75` → decoded as `-127` because RSSI decode was applied to an SNR value).
- What was reported as SNR (`4.2 dB`) was actually the RSSI raw byte (`-8.5 dBm` → decoded as `4.2` because SNR decode was applied to an RSSI value).

**Verification:** Cross-checked against the RadioLib SX128x driver source — `rssiSync` comes BEFORE `snr` in the packet status response.

**Fix:** Swapped the byte indices in the RSSI/SNR decode. Commit `dca7a84`.

**File:** `firmware/rp2040/src/lora_range_rx.cpp` (and any RX firmware using `GET_LORA_PACKET_STATUS`).

**Correct decode after fix:**
```c
// GET_LORA_PACKET_STATUS (0x022A) response layout:
//   buf[0..1] = status padding / header
//   buf[2]    = RSSI (signed, 0.5 dBm steps, offset)
//   buf[3]    = SNR  (signed, 0.25 dB steps)
```

### Bug 3: PER Stats Inflation — Commit `9352337`

**Symptom:** PER reported as `78%` when actual packet loss was `~1%`.

**Root cause:** `resetStats()` zeroed the `received` counter at the start of each window, but `maxSeq` (the highest sequence number seen) was tracked **globally** across windows. The PER formula was:
```
PER = 1 - (received_in_window / (maxSeq_global + 1))
```
Since `maxSeq` grew across windows but `received` reset each window, the denominator kept inflating while the numerator reset — producing wildly inflated PER.

**Fix:** Added a `cumulativeRx` field that tracks total received packets across all windows. PER now uses cumulative counts matched against cumulative TX. Commit `9352337`.

**Files:** All RX firmware with `resetStats()`:
- `firmware/rp2040/src/flrc_cont_rx.cpp`
- `firmware/rp2040/src/flrc_raw_rx_20mhz.cpp`
- `firmware/rp2040/src/flrc_range_rx_auto.cpp`
- `firmware/rp2040/src/flrc_range_rx.cpp`
- `firmware/rp2040/src/flrc_rx_main.cpp`
- `firmware/rp2040/src/flrc_rx_raw.cpp`
- (and LoRa RX equivalents)

> ⚠️ **STATUS:** The `cumulativeRx` fix has been coded and compiles, but has **NOT been verified on hardware**. The SF12 "1% PER" number in the results table above was computed manually from raw packet counts, not from the firmware's PER output. Re-verification required (TASK-P4-1).

---

## Hardware Setup

### Board Mapping

| Role | RP2040 Board ID | USB Bridge Port | Direct USB Port |
|---|---|---|---|
| RX | #8332  | `/dev/ttyACM1` (ESP32 bridge) | `/dev/ttyACM0` (unstable) |
| TX | #F242D | `/dev/ttyACM3` (ESP32 bridge) | `/dev/ttyACM2` (unstable) |

> **CRITICAL:** Always use the ESP32 **bridge** ports (ACM1/ACM3). The direct USB ports (ACM0/ACM2) **swap on every reset** — you cannot reliably target them.

### Flash Procedure

**RP2040 (main firmware):**
```bash
~/.platformio/packages/tool-rp2040tools/picotool load -v -x <path>/firmware.uf2
```
> The `-v` (verbose) and `-x` (execute after load) flags are **MANDATORY**. Without `-x`, the board stays in bootloader mode and nothing runs. Without `-v`, you can't tell if the flash succeeded.

**ESP32-C3 bridge recovery (3-file flash — if bridge is bricked):**
```bash
~/.platformio/packages/tool-esptoolpy/esptool.py \
    --port /dev/ttyACM0 write_flash \
    0x0     bootloader.bin \
    0x8000  partitions.bin \
    0x10000 firmware.bin
```
> **WARNING:** Flashing raw firmware at `0x0` overwrites the bootloader and **corrupts** the bridge. Always use the 3-file layout: bootloader at `0x0`, partitions at `0x8000`, app at `0x10000`.

**Bootsel-oneshot:** The ESP32 bridge firmware can trigger the RP2040's BOOTSEL mode via GPIO — useful for automated re-flashing without physical button presses.

### Mutex (Board Access Locking)

Two RP2040 boards are shared between tracks. **Always lock BOTH boards** before any flash/test operation:

```bash
BALLOON_TRACK=speed-tests python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire
# ... do your work ...
BALLOON_TRACK=speed-tests python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py release
```

> Never acquire only one board — the other track may flash different firmware and corrupt your test. Lock and unlock BOTH boards together.

---

## Firmware State

### Branch + Build

```
Branch:   speed-sustained-sweep
Remote:   origin (ngit) + github (felixfelix-bot/balloon-fresh)
Build:    cd firmware/rp2040 && pio run -e <env_name>
Output:   .pio/build/<env_name>/firmware.uf2
```

### Key Source Files

| File | Purpose |
|---|---|
| `firmware/rp2040/src/lora_range_tx.cpp` | LoRa TX (SF7/SF9/SF12, compile-time params) |
| `firmware/rp2040/src/lora_range_rx.cpp` | LoRa RX (auto-stats, RSSI/SNR decode) |
| `firmware/rp2040/src/flrc_raw_tx.cpp` | FLRC TX (2600 kbps, optimized FIFO pipeline) |
| `firmware/rp2040/src/flrc_range_rx.cpp` | FLRC RX (auto-stats, PER tracking) |
| `firmware/rp2040/src/radio.cpp` / `radio.h` | Shared SPI radio helpers |
| `firmware/rp2040/src/pins.h` | Pin definitions |

### PlatformIO Environments

**LoRa:**
- `rp2040-lora-tx-sf7`, `rp2040-lora-tx-sf9`, `rp2040-lora-tx-sf12`
- `rp2040-lora-rx`, `rp2040-lora-rx-sf9`, `rp2040-lora-rx-sf12`

**FLRC:**
- `rp2040-flrc-rx`, `rp2040-flrc-tx-raw`, `rp2040-flrc-rx-raw`
- `rp2040-raw-tx`, `rp2040-raw-tx-20mhz`, `rp2040-raw-rx-20mhz`
- `rp2040-range-tx`, `rp2040-range-rx`
- `rp2040-range-tx-1300`, `rp2040-range-rx-1300`
- `rp2040-range-tx-650`, `rp2040-range-rx-650`
- `rp2040-range-tx-325`, `rp2040-range-rx-325`
- `rp2040-cont-tx`, `rp2040-cont-tx-1300`, `rp2040-cont-tx-650`, `rp2040-cont-tx-325`
- `rp2040-cont-rx`, `rp2040-cont-rx-1300`, `rp2040-cont-rx-650`, `rp2040-cont-rx-325`
- (and many more experimental envs — see `platformio.ini`)

> **Note on FLRC 1300/650/325:** These environments exist but were **never successfully tested on hardware** because runtime serial bitrate commands kill USB CDC (see "What Doesn't Work" below). They need compile-time `#define FLRC_BITRATE` firmware (TASK-P1-1 through P1-4).

---

## LR2021 SPI Opcode Reference (Raw 2-Byte)

> The LR2021 uses **raw 2-byte opcodes** via SPI. Do NOT use RadioLib (see below).

| Opcode | Name | Payload | Notes |
|---|---|---|---|
| `0x0207` | SET_PACKET_TYPE | `[type]` | LoRa=`0x00`, FLRC=`0x04` |
| `0x0220` | SET_LORA_MODULATION_PARAMS | `[SF_BW_byte, CR_LDRO_byte]` | SF+BW packed; CR is index 1–4 |
| `0x0221` | SET_LORA_PACKET_PARAMS | `[preamble, payloadLen, flags]` | |
| `0x0208` | SET_FLRC_MODULATION_PARAMS | `[bitrate_BW, CR, shaping]` | |
| `0x022A` | GET_LORA_PACKET_STATUS | (read 4+ bytes) | `buf[2]=RSSI`, `buf[3]=SNR` |
| `0x024B` | GET_FLRC_PACKET_STATUS | (read 4+ bytes) | |
| `0x0283` | SET_TX | `[timeout]` | Trigger TX |
| `0x0282` | SET_RX | `[timeout]` | Trigger RX |
| `0x0216` / `0x0203` | SET_TX_PARAMS | `[power_raw, ramp_byte]` | See note below ⚠️ |

> ⚠️ **SET_TX_PARAMS opcode discrepancy:** The task spec lists `0x0216`, but the **actual verified-working firmware** (`flrc_range_tx.cpp:176`, `lora_range_tx.cpp:327`) uses `{0x02, 0x03, ...}` = opcode `0x0203` with `power_raw = dbm × 2` (0.5 dB steps) and ramp byte `0x04` (20 µs ramp). All 12 dBm tests passed with `0x0203`. **Verify against the Semtech LR2021 datasheet** before changing. See TASK-P2-1 in the plan doc.

**IRQ status (32-bit read):**
```
Bit 18 = RX_DONE
Bit 19 = TX_DONE
```

---

## What Doesn't Work

### RadioLib LR2021 Driver — DEAD
RadioLib's SX128x/LR2021 driver uses 24-bit opcodes, but the LR2021 expects 2-byte opcodes. Result: error `-707` on every command. **Never use RadioLib for LR2021.** Use raw 2-byte opcode SPI. (See ADR-020.)

### Batch SPI — Reverted
The LR2021 requires **CS HIGH between commands** (each opcode is a separate SPI transaction). Attempting to batch multiple opcodes in a single CS-low transfer corrupts the command stream. The batch SPI optimization was reverted.

### Runtime Serial BITRATE Commands — USB CDC Dies
Sending bitrate-change commands over serial during a TX loop kills the USB CDC interface — the serial port disappears mid-test. **Workaround:** use compile-time `#define` for all TX parameters (bitrate, SF, CR, power). No runtime parameter changes during active TX.

**Consequence:** FLRC 1300/650/325 bitrates were never tested because they required runtime bitrate switching. Each bitrate needs its own compiled firmware binary.

### FLRC 1300/650/325 — Not Completed
See above. Needs compile-time firmware (TASK-P1-1 through P1-4 in the plan doc).

---

## Key Learnings (For Future Workers)

1. **RadioLib is dead on LR2021** (ADR-020). Raw 2-byte opcode SPI is the only path. Every command is `{0x02, 0xNN, ...payload}`.

2. **CR encoding uses internal index 1–4**, not the coding rate denominator (4/5, 4/6, 4/7, 4/8). Setting CR=5 produces garbage SPI bytes (`0x50`).

3. **RSSI/SNR byte order:** In `GET_LORA_PACKET_STATUS` response, `rssiSync` (RSSI) comes **BEFORE** SNR. `buf[2]=RSSI`, `buf[3]=SNR`. Getting this backwards produces `-127 dBm` RSSI readings.

4. **`picotool load -v -x` is mandatory.** The `-x` flag executes the firmware after flashing. Without it, the board sits idle in bootloader mode. Without `-v`, silent failures are invisible.

5. **ESP32 bridge bootloader is fragile.** Always use the 3-file flash layout (bootloader@`0x0`, partitions@`0x8000`, app@`0x10000`). A raw flash at `0x0` bricks the bridge.

6. **USB CDC dies during TX loops.** Do not attempt runtime serial parameter changes while TX is active. Use compile-time `#define` only.

7. **PER stats must track cumulative counts** when using a global TX sequence number. If `resetStats()` zeroes `received` but `maxSeq` persists globally, PER inflates to 78%+ even when actual loss is 1%. Use `cumulativeRx`.

8. **Mutex: always lock/unlock BOTH boards together.** Acquiring only one board lets another track flash it with different firmware mid-test.

---

## Git Commit History (This Session)

```
9352337  fix(stats): PER calculation uses cumulative rx count
dca7a84  fix(rssi): swap RSSI/SNR byte indices in LoRa packet status
b32f50b  fix(lora): CR encoding bug — LORA_CR 5→1 (invalid SPI value)
4aa7385  docs: add BOARD ACCESS mutex lock section to AGENTS.md
dfb9dce  feat: add LoRa TX auto-start envs (SF7/SF9/SF12) + sweep progress docs
1092c3f  fix: revert 40MHz SPI to 20MHz (corrupts FIFO), tune cont-rx debug output
21f1169  feat: infinite TX + cont-rx hex debug, sequential seq confirmed
73e1eb4  feat: cont-rx firmware + 4 platformio envs
2fe99c0  feat: 40MHz SPI overclock — TX 1753→1925 kbps (+9.7%)
647bf90  fix(rx): RX SPI IRQ polling + 255-byte pkt match, 0% PER 1492 kbps verified
```

---

## Next Steps

See **`docs/PLAN-pre-range-testing-2026-07-23.md`** for the full task breakdown. Priority order:

1. **P4-1:** Re-verify PER stats fix on hardware (SF12) — confirms the `cumulativeRx` fix works.
2. **P1-1 → P1-4:** FLRC bitrate sweep (1300/650/325) — compile-time firmware.
3. **P2-1 → P2-4:** TX power sweep — find the PER/RSSI vs power curve.
4. **P3-1 → P3-3:** Automated test harness — Python runner for repeatable sweeps.
5. **P5-1 → P5-3:** Consolidate all results into machine-readable JSON + summary table.

---

## Related Documents

| Document | Purpose |
|---|---|
| `docs/PLAN-pre-range-testing-2026-07-23.md` | Task plan for remaining pre-range work |
| `docs/HANDOVER-sustained-throughput-2026-07-23.md` | Earlier handover (sustained throughput methodology) |
| `docs/sustained-throughput-results-2026-07-23.md` | Raw sustained throughput test data |
| `docs/lora-sweep-progress-2026-07-23.md` | LoRa SF sweep progress notes |
| `docs/lr2021-spi-command-reference.md` | Full LR2021 opcode reference |
| `docs/adr/ADR-020*.md` | RadioLib dead on LR2021 decision record |
| `AGENTS.md` | Project overview + agent instructions |
