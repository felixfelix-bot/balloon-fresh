# FLRC Range-vs-Throughput: Dual-Platform Action Plan

**Date:** 2026-08-18  
**Branch:** `feat/e80-stm32-bench` (analysis), `feat/e80-spi-bypass` (RP2040 firmware)  
**Hardware on hand:** 2× E80-900MBL-02 (STM32F103+LR2021), 2× RP2040 Pico + LR2021 (custom rigs)

---

## Executive Summary

**Three viable paths to a range test exist. In priority order:**

1. **FASTEST (zero new wiring, ~30 min):** Flash the two standalone RP2040+LR2021 boards with existing `flrc_range_tx.cpp` / `flrc_range_rx.cpp` and run a 2.4 GHz FLRC range test NOW. One board is already in BOOTSEL mode.

2. **BEST CAPABILITY (~1-2 hrs):** Flash E80 Board B via SWD (move Pico debugprobe from Board A), then run the full 868 MHz range campaign with the STM32 bench firmware + `e80_bench_ctl.py` host tool. Board A is already flashed and working.

3. **CROSS-VALIDATION (~2-3 hrs):** Wire both RP2040s to E80 J2 headers (SPI bypass), flash `e80_flrc_bench.cpp`, run 868 MHz tests using E80 PA/antenna/TCXO but RP2040 as the MCU. No SWD needed.

**Platforms CANNOT be mixed in a single TX→RX link** without firmware modifications (different radio init sequences, PA configs, frequency bands). See §3.

---

## 1. Platform Comparison

| Parameter | E80 STM32 Bench | RP2040 Standalone | E80 SPI Bypass (RP2040) |
|-----------|----------------|-------------------|------------------------|
| **MCU** | STM32F103C8T6 (72 MHz) | RP2040 Pico (125 MHz) | RP2040 Pico (125 MHz) |
| **Radio** | LR2021 (on E80 module) | LR2021 (custom board) | LR2021 (on E80 module) |
| **Clock** | TCXO (module-fitted) | 52 MHz crystal | TCXO (via E80 module) |
| **Freq band** | 850–930 MHz (LF) | 2400–2480 MHz (HF only) | 850–930 MHz (LF) |
| **PA config** | E80 LF PA table, +22 dBm max | Default HF PA, ~12.5 dBm max | E80 LF PA table, +22 dBm max |
| **Antenna** | E80 stock SMA whip (sub-GHz) | Custom board antenna | E80 stock SMA whip |
| **SPI speed** | 9 MHz (on-board) | 20 MHz (direct wiring) | 4 MHz (jumper harness) |
| **Firmware** | `e80_bench.bin` v1.2 (built, 19.5 KB) | `flrc_range_tx/rx.cpp` (source) | `e80_flrc_bench.cpp` (source) |
| **Features** | 8 FLRC bitrates, LoRa SF5-12, PER, Wilson CI, RSSI min/max/avg, autonomous TX/RX, safety interlocks, band enforcement, host orchestration | FLRC only (4 bitrates: 2600/1300/650/325), PER, RSSI avg/min/max, serial config, `range_test_runner.py` | FLRC-650 fixed, PER, RSSI, TX/RX role strap, serial config |
| **Host tool** | `e80_bench_ctl.py` (matrix sweep, CSV, band guard) | `range_test_runner.py` (distance/power/size/freq sweep) | Manual serial commands |
| **Safety** | 3-layer watchdog, TX inhibit, band clamp, power caps | None (raw TX) | None (raw TX) |
| **Ready?** | Board A ✅ Board B ⏳ (SWD flash) | One in BOOTSEL ✅, other needs flash | Needs jumper wiring |

---

## 2. Can We Use the Two RP2040+LR2021 Boards as a Pair?

### YES — this is the fastest path.

**Firmware needed:**
- Board 1 (TX): `flrc_range_tx.cpp` from `feat/e80-spi-bypass` branch, `firmware/rp2040/src/`
- Board 2 (RX): `flrc_range_rx.cpp` from same branch

**What they do:**
- TX: Sends N×Len-byte FLRC packets with sequence numbers, DEADBEEF end marker carrying TX count
- RX: Receives, tracks sequence numbers, computes PER/throughput/RSSI, reports via serial
- Both accept runtime serial commands: `POWER`, `PKTLEN`, `FREQ`, `BITRATE`, `COUNT`, `RUN`, `INIT`, `STATUS`
- Sync word: `0x12AD101B` (must match between TX and RX — it does)

**Limitations:**
- **2.4 GHz only** — HF path hardcoded (`0x0201` with `0x01`), FREQ clamped to 2400–2480 MHz
- **No TCXO init** — uses 52 MHz crystal (custom boards don't have TCXO)
- **No PA config** — uses default HF PA, max ~12.5 dBm
- **No safety interlocks** — raw TX, no band enforcement, no watchdog
- **4 bitrates only** — 2600, 1300, 650, 325 kbps (firmware parser supports 8 but calibration is HF-only)
- **Fixed CR 1/0 + BT 0.5** — not configurable

**To flash:** One board is already in BOOTSEL mode (mounted at `/mnt/rp2`). Copy the UF2. The second board needs BOOTSEL hold + USB plug, then copy UF2.

**Host orchestration:** `scripts/range_test_runner.py` already exists with:
- Auto-port detection by Pico serial number
- `test`, `sweep-distance`, `sweep-power`, `sweep-pktlen`, `sweep-freq` commands
- Results logged to markdown

### What modifications would be needed for 868 MHz operation?

The `flrc_range_tx/rx.cpp` firmware would need these changes to work at 868 MHz on the standalone boards:

1. Change `SetRxPath` from `0x01` (HF) to `0x00` (LF)
2. Change FREQ range check from `2400-2480` to `850-930`
3. Add `SetPaCfg` for LF PA (3-byte Semtech form: `{0x00, 0x76, 0x10}`)
4. Change default frequency from 2440 to 868 MHz
5. Change calibration front-end bit (remove `0x8000` OR for LF path)
6. Verify LR2021 on custom boards supports LF FLRC (marked "UNTESTED" in `multi_radio_sweep.cpp`)

**This is essentially what `e80_flrc_bench.cpp` already does** — but that firmware is designed for E80 bypass (TCXO init, E80 PA table). The standalone boards use a crystal, not TCXO, so the TCXO init would need to be removed or replaced with crystal standby.

**Verdict: Not worth modifying. Use the E80 path for 868 MHz.**

---

## 3. Can Platforms Be Mixed? (E80 TX → RP2040 RX, or vice versa)

### Technically possible but NOT recommended without firmware changes.

**Common ground:**
- Both use the same LR2021 radio chip with the same SPI command set
- Both use the same sync word: `0x12AD101B`
- Both use FLRC modulation with the same opcode structure

**Blockers for mixing:**

1. **Frequency mismatch:** E80 bench firmware operates at 868 MHz (LF path). RP2040 standalone firmware operates at 2.4 GHz (HF path). They literally cannot hear each other.

2. **PA config mismatch:** E80 uses LF PA config (`{0x00, 0x76, 0x10}`). RP2040 standalone uses default HF PA (no explicit SetPaCfg). Even if frequency were matched, the PA would be misconfigured.

3. **Clock source mismatch:** E80 module has a TCXO (initialized via `0x0120` with 2.2V/64000 steps). RP2040 standalone uses a 52 MHz crystal (no TCXO init). The frequency synthesis divider math (`frf = freq × 2^18 / XTAL`) is the same, but the XTAL frequency differs if the custom boards use a different crystal.

4. **Packet parameter differences:** E80 bench firmware uses Semtech driver types (preamble 32 bits, sync 4 bytes, fixed length, CRC 2 bytes). RP2040 firmware uses raw SPI writes with similar but not necessarily identical parameters. CRC and header type must match exactly.

5. **End-of-burst marker:** E80 STM32 firmware does not send a DEADBEEF end marker — it uses a fixed packet count and reports TX-side stats via `STAT?`. The RP2040 RX firmware relies on the DEADBEEF marker to know the total sent count. Without it, PER calculation uses `lastSeq+1` as the denominator, which works if no packets are lost but underestimates PER at high loss rates.

**To make mixing work, you would need to:**
- Match frequency (both at 868 MHz or both at 2.4 GHz)
- Match PA config (both LF or both HF)
- Match packet params (preamble, sync word, header type, CRC, payload length)
- Add DEADBEEF marker to E80 TX firmware or remove it from RP2040 RX firmware
- Ensure compatible init sequences (TCXO vs crystal)

**Verdict: Not worth the effort. Use matched pairs.**

---

## 4. Fastest Path to a Range Test

### Path A: RP2040 Standalone Pair (2.4 GHz) — ~30 minutes

**Steps:**
1. Build `flrc_range_tx.cpp` and `flrc_range_rx.cpp` as UF2 files
   - Use PlatformIO or pico-sdk with earlephilhower core
   - Or use existing build artifacts if available
2. Flash Board 1 (in BOOTSEL): copy TX UF2 to `/mnt/rp2`
3. Flash Board 2: hold BOOTSEL, plug USB, copy RX UF2
4. Connect both via USB serial, run `range_test_runner.py test --distance 10 --power 12`
5. Walk to different distances, repeat

**Pros:** Zero wiring, zero SWD, immediate
**Cons:** 2.4 GHz only (short range, ~100-300m LOS expected), lower PA power (~12.5 dBm), no safety interlocks, no band enforcement, limited bitrate selection

**Expected range at 2.4 GHz FLRC-650, +12.5 dBm, stock antenna:**
- FLRC-2600: ~20-50m
- FLRC-1300: ~30-80m
- FLRC-650: ~50-150m
- FLRC-325: ~80-200m

### Path B: E80 Pair (868 MHz) — ~1-2 hours

**Steps:**
1. Move Pico debugprobe from E80 Board A to Board B (3 wires: SWDIO, SWCLK, GND)
2. Run continuity check on SWD wiring (3 beeps)
3. Flash Board B with `build-fw/e80_bench.bin` via OpenOCD
4. Move debugprobe back (or leave disconnected — both boards now have bench firmware)
5. Connect both E80 boards via USB-UART (CH340)
6. Run `e80_bench_ctl.py --tx /dev/ttyUSBx --rx /dev/ttyUSBy --freq 868000000 --dbm 10`

**Pros:** Full feature set, 868 MHz (long range), +22 dBm PA, safety interlocks, band enforcement, host orchestration with CSV, Wilson CI
**Cons:** Requires SWD flash of Board B, requires physical debugprobe move

**Expected range at 868 MHz FLRC-650, +22 dBm, stock whip antenna:**
- FLRC-260: ~5-10 km LOS
- FLRC-650: ~2-5 km LOS
- FLRC-1300: ~1-2 km LOS
- FLRC-2600: ~0.3-1 km LOS

### Path C: E80 SPI Bypass (868 MHz, RP2040-driven) — ~2-3 hours

**Steps:**
1. Flash both RP2040s with `e80_flrc_bench.cpp` (PlatformIO build)
2. Wire each RP2040 to an E80 J2 header (7 signals + GND, per wiring guide §6)
3. Hold STM32 in reset on both E80s (tape RESET button)
4. Connect RP2040s via USB, run serial commands

**Pros:** No SWD needed, uses E80 PA/antenna/TCXO, 868 MHz, +22 dBm
**Cons:** Jumper wiring assembly (14 jumpers total), signal integrity risk at 4 MHz over jumpers, less feature-rich firmware (FLRC-650 only, no LoRa, no matrix sweep, no CSV)

---

## 5. Recommended Action Plan

### Phase 1: Immediate Range Test (RP2040 standalone, 2.4 GHz)
**Goal:** Validate test methodology and firmware, get initial data within 30 minutes.

1. Check if UF2 build artifacts exist for `flrc_range_tx/rx.cpp`
2. If not, build via PlatformIO: `cd firmware/rp2040 && pio run -e flrc_range_tx -e flrc_range_rx`
3. Flash Board 1 (BOOTSEL mode, mounted at `/mnt/rp2`): copy TX UF2
4. Flash Board 2: BOOTSEL + USB, copy RX UF2
5. Run `range_test_runner.py test --distance 1 --power 12` (1m baseline)
6. Run at 10m, 25m, 50m, 100m with FLRC-650 and FLRC-2600
7. Record results

### Phase 2: Primary Campaign (E80 pair, 868 MHz)
**Goal:** Full range-vs-throughput characterization with proper PA, antenna, safety.

1. Move Pico debugprobe to E80 Board B
2. Continuity check: Pico GND↔E80 GND, GP2↔SWDIO, GP3↔SWCLK
3. `openocd -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg -c "adapter speed 100" -c "init" -c "stm32f1x unlock 0" -c "halt" -c "flash write_image build-fw/e80_bench.bin 0x08000000" -c "reset run" -c "shutdown"`
4. Verify boot banner on Board B: `ID?` should return `E80 BENCH FW v1.2`
5. Move debugprobe back to Board A (or disconnect — both boards now have bench firmware)
6. Run `e80_bench_ctl.py --tx /dev/ttyUSBx --rx /dev/ttyUSBy --freq 868000000 --dbm 10 --n 1000 --len 255`
7. Verify link at 1m, then run the distance matrix per RANGE-TEST-PLAN.md

### Phase 3: Cross-Validation (optional, if Phase 1 + Phase 2 both work)
**Goal:** Independent validation of results using different MCU platform.

1. Wire RP2040s to E80 J2 headers (per E80-SPI-BYPASS-WIRING.md)
2. Flash `e80_flrc_bench.cpp` to both RP2040s
3. Run at subset of distances where E80 STM32 results exist
4. Compare PER/RSSI between STM32-driven and RP2040-driven E80 modules

---

## 6. E80 Board B SWD Flash — Can We Reuse the Same Pico Debugprobe?

**YES.** The Pico debugprobe is currently wired to Board A (which is already flashed). Steps:

1. **Disconnect from Board A:** Unplug the 3 SWD wires (SWDIO, SWCLK, GND) from Board A's debug header pads
2. **Connect to Board B:** Solder/touch the same 3 wires to Board B's debug header pads (same pinout — both are identical E80 boards)
3. **Flash Board B:** Same OpenOCD command that worked for Board A
4. **Verify:** `ID?` command via UART should return bench firmware banner
5. **Reconnect to Board A (optional):** Only needed if Board A ever needs re-flashing. After first flash, the `FLASH` command enables headless re-flashing via ROM bootloader — no SWD needed for subsequent updates.

**Alternative:** If Board A's SWD wiring is fragile and you don't want to disturb it, a second Pico can be set up as a debugprobe for Board B. But one debugprobe is sufficient — just move it.

---

## 7. Test Methodology

### Distances
Per RANGE-TEST-PLAN.md §2, log-spaced stops:
- S0: 0.5m (near-field/saturation reference)
- S1: 10m (short-link baseline)
- S2: 50m (farthest +10 dBm stop)
- S3: 200m (first +22 dBm cells, E80 only)
- S4: 500m
- S5: 1km (edge/Fresnel probe)

For 2.4 GHz (RP2040 standalone), add closer stops: 1m, 5m, 10m, 25m, 50m, 100m

### FLRC Bitrates
- E80: 260, 650, 1300, 2600 kbps (primary sweep) + LoRa SF7/SF12 (calibration)
- RP2040: 325, 650, 1300, 2600 kbps

### Payload Sizes
- 51 bytes (telemetry-sized, per RANGE-TEST-PLAN)
- 255 bytes (maximum, comparability anchor)

### Measurement
- PER (primary metric): via sequence number span, Wilson 95% CI
- RSSI: per-packet avg/min/max (relative only — uncalibrated)
- Throughput: received_payload_bytes × 8 / elapsed_time
- 3 repeats per stop, reported individually + median

### ETSI Compliance (868 MHz)
Per `frequency-plan-868.md`:
- **Default (indoor):** 863–870 MHz, +10 dBm conducted, 1% duty cycle on h1.5 (868.0–868.6 MHz)
- **High power (outdoor):** h1.7 only (869.4–869.65 MHz), +22 dBm, 10% duty cycle
- **BAND OVERRIDE 2026:** 915 MHz Americas ISM (outside EU SRD, operator's jurisdiction call)
- FLRC duty cycle is negligible: 10,000 × 51B at FLRC-650 = 8.6s airtime/hour = 0.24% (well under 1%)

### 2.4 GHz Compliance
- 2400–2483.5 MHz ISM band, 100 mW EIRP (20 dBm), no duty cycle limit for non-FHSS
- Our 12.5 dBm is well within limits
- No special compliance concerns for short-range testing

---

## 8. Trade-offs Summary

| Factor | RP2040 Standalone (2.4 GHz) | E80 STM32 (868 MHz) | E80 Bypass (868 MHz) |
|--------|---------------------------|---------------------|---------------------|
| **Range** | Short (~100-300m) | Long (~1-10 km) | Long (~1-10 km) |
| **PA power** | ~12.5 dBm | +22 dBm | +22 dBm |
| **Antenna** | Custom (likely small) | E80 stock SMA whip | E80 stock SMA whip |
| **Time to first test** | ~30 min | ~1-2 hrs | ~2-3 hrs |
| **Firmware features** | Basic (FLRC only) | Full (8 FLRC + LoRa, PER, CI, safety) | Basic (FLRC-650 only) |
| **Host tooling** | `range_test_runner.py` | `e80_bench_ctl.py` (matrix, CSV, band guard) | Manual serial |
| **Safety** | None | 3-layer watchdog, band enforcement | None |
| **SWD needed?** | No | Yes (Board B) | No |
| **Wiring needed?** | No | No | Yes (14 jumpers) |
| **Comparable results?** | No (different band/PA/antenna) | Reference platform | Yes (same radio/PA/antenna as STM32) |

---

## 9. Key Files

| File | Location | Purpose |
|------|----------|---------|
| `flrc_range_tx.cpp` | `firmware/rp2040/src/` (feat/e80-spi-bypass) | RP2040 standalone TX firmware |
| `flrc_range_rx.cpp` | `firmware/rp2040/src/` (feat/e80-spi-bypass) | RP2040 standalone RX firmware |
| `e80_flrc_bench.cpp` | `firmware/e80-bypass/rp2040/src/` (feat/e80-spi-bypass) | E80 SPI bypass firmware (RP2040) |
| `e80_lr20xx_raw.h` | `firmware/e80-bypass/common/` (feat/e80-spi-bypass) | Shared LR2021 raw SPI driver (E80) |
| `e80_pinmap.h` | `firmware/e80-bypass/common/` (feat/e80-spi-bypass) | Pin map for E80 bypass |
| `e80_bench.bin` | `firmware/e80-stm32-bench/build-fw/` (feat/e80-stm32-bench) | STM32 bench firmware (built, ready) |
| `e80_bench_ctl.py` | `firmware/e80-stm32-bench/tools/` (feat/e80-stm32-bench) | Host orchestration (matrix sweep, CSV) |
| `range_test_runner.py` | `scripts/` (feat/e80-spi-bypass) | RP2040 range test runner |
| `RANGE-TEST-PLAN.md` | `docs/` (feat/e80-stm32-bench) | Outdoor range campaign plan |
| `E80-SPI-BYPASS-WIRING.md` | `docs/e80-900mbl-02-eval/` (feat/e80-spi-bypass) | J2 bypass wiring guide |
| `frequency-plan-868.md` | `docs/` (feat/e80-stm32-bench) | ETSI 868 MHz compliance |

---

## 10. Decision Matrix

| Question | Answer |
|----------|--------|
| Can RP2040+LR2021 pair do range testing? | **YES** — at 2.4 GHz only, use `flrc_range_tx/rx.cpp` |
| What firmware does each RP2040 need? | TX: `flrc_range_tx.cpp`, RX: `flrc_range_rx.cpp` (different images) |
| Can platforms be mixed (E80 TX → RP2040 RX)? | **NO** — different freq bands, PA configs, init sequences. Not worth modifying. |
| Fastest path to a range test? | **RP2040 standalone pair at 2.4 GHz** — one board in BOOTSEL, flash and go |
| Best path for full characterization? | **E80 STM32 pair at 868 MHz** — full features, safety, host tooling |
| Can we run both pairs in parallel? | **YES** — different frequencies, no interference. Good for methodology validation. |
| Can we reuse the same Pico debugprobe for E80 Board B? | **YES** — disconnect from Board A, connect to Board B, flash, reconnect or leave disconnected |
| Are range results comparable between platforms? | **NO** — different band, PA, antenna, clock source. Each platform's results stand alone. |
| Does RP2040 standalone need firmware modification? | **NO** for 2.4 GHz. **YES** for 868 MHz (not recommended — use E80 path instead) |
| ETSI constraints? | 868 MHz: +10 dBm indoor (1% DC), +22 dBm outdoor in h1.7 only (10% DC). 2.4 GHz: 20 dBm EIRP, no DC limit. FLRC airtime is negligible at all bitrates. |

---

*End of analysis. Generated 2026-08-18 from repository source inspection.*