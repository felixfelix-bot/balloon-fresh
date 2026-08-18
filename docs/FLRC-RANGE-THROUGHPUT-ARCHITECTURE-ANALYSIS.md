# FLRC Range-vs-Throughput Characterization: UART Feasibility & Architecture Analysis

**Date:** 2026-08-18  
**Branch:** `feat/e80-stm32-bench`  
**Board:** EBYTE E80-900MBL-02 (STM32F103C8T6 + Semtech LR2021)

---

## Executive Summary

**UART-only (stock firmware) for FLRC throughput measurement: NO — impossible.**  
The stock firmware runs LoRa exclusively; no UART command switches to FLRC mode. The FLRC driver is compiled and linked but never called.

**Custom firmware already exists and is the correct architecture.** The `e80-stm32-bench` firmware (built, 19.5 KB / 30% flash) implements exactly the hybrid approach needed: UART for configuration and stats retrieval, autonomous on-board burst for FLRC data generation and reception. UART bandwidth is irrelevant because packet data never traverses it.

**Blocking issue: SWD access.** The firmware is built but cannot be flashed because SWD fails (physical wiring, not firmware). Two paths forward: (1) fix SWD wiring (continuity beeps on debug header), or (2) use the J2 SPI-bypass approach (hold STM32 in reset, drive LR2021 from an external MCU with our existing RP2040/ESP32-C3 firmware).

---

## 1. Can Stock Firmware UART Commands Be Used for FLRC Throughput Measurement?

### Verdict: NO

**Reasoning (three independent blockers):**

### 1a. Stock firmware is LoRa-only — no FLRC mode exposed

The stock demo firmware (`mbl02demo/E80_DEMO/Core/Src/main.c`) implements a transparent LoRa bridge. The UART command set is:

| Command | Function | Modem |
|---------|----------|-------|
| `C1 00 <freq>` | Set frequency | LoRa |
| `C1 02 00/01` | CW stop/start | LoRa carrier |
| `C1 03 00/01` | Sleep/wake | LoRa |
| `C1 C1 C1` | Auto-TX 20B test payload | LoRa |
| `C2 <params>` | One-shot full config (power/SF/BW/CR/sync/freq) | LoRa |
| `C3 C3 00/01/02 <freq>` | Long-range / 2.4G presets (SF12) | LoRa |
| `C4 C4 00/01 <freq>` | Sensitivity preset (SF9) | LoRa |
| *anything else* | Transparent TX | LoRa |

All commands configure `lr20xx_radio_lora_*` parameters. The FLRC driver (`lr20xx_radio_flrc.c`) is compiled and linked (confirmed by `.map` file) but **no code path calls `lr20xx_radio_common_set_pkt_type(FLRC)` or any `lr20xx_radio_flrc_*` function**. There is no hidden command, no register poke, no escape sequence that activates FLRC.

**Source-verified** from the vendor demo `main.c`, `user_radio.c`, and `user_uart.c` — all radio configuration flows through `radio_inits()` which hardcodes LoRa packet type.

### 1b. Even if FLRC were somehow triggered, UART cannot sustain FLRC data rates

| Parameter | Value |
|-----------|-------|
| UART baud rate | 115200 (current) / max 2 Mbaud (CH340) |
| UART throughput @ 115200 | ~11,520 bytes/s = **~92 kbit/s** |
| FLRC air rate (slowest: 260 kbps) | ~32,500 bytes/s = **~260 kbit/s** |
| FLRC air rate (bench peak: 2600 kbps) | ~325,000 bytes/s = **~2,600 kbit/s** |
| FLRC bench reference: 650 kbps | ~81,250 bytes/s = **~650 kbit/s** |

At 115200 baud, the UART can deliver **14% of FLRC-260's air rate** and **3.5% of FLRC-650's**. Even at CH340's maximum 2 Mbaud (~200 kbit/s effective), it cannot sustain FLRC-650.

The stock firmware's transparent mode pipes UART bytes directly to the radio FIFO. At FLRC-650, a 255-byte packet takes ~3.1 ms on-air but UART needs ~22 ms to deliver 255 bytes — the radio would transmit 7× slower than its air rate, measuring UART throughput, not radio throughput.

### 1c. Stock firmware discards per-packet statistics

The capability report confirms: `lr20xx_radio_lora_get_packet_status` is called internally but RSSI/SNR values are **discarded**. RX only counts packets via the event system and prints raw bytes to UART. No PER calculation, no RSSI logging, no sequence number tracking — none of the instrumentation needed for range-vs-throughput characterization exists.

---

## 2. If We Had Custom Firmware, Can UART Sustain FLRC Throughput Testing?

### Verdict: YES — because the correct architecture avoids streaming data over UART entirely

The key insight is that **UART bandwidth is irrelevant** when the STM32 generates packets on-board and only reports aggregate statistics. This is the architecture already implemented in `e80-stm32-bench`:

```
Host (e80_bench_ctl.py)                    STM32F103 (e80_bench firmware)
    │                                          │
    │── UART: "MOD flrc 650 10\r\n" ──────────►│  configure FLRC 650 kbps, +10 dBm
    │── UART: "FREQ 868000000\r\n" ───────────►│  set frequency
    │── UART: "ROLE TX\r\n" ──────────────────►│  set role
    │── UART: "ARM TX\r\n" ───────────────────►│  arm TX (safety interlock)
    │── UART: "START N=1000 LEN=255 GAP=5000\r\n" ►│  begin burst
    │                                          │  ┌─────────────────────────┐
    │                                          │  │  autonomous TX loop:    │
    │                                          │  │  for i in 0..999:       │
    │                                          │  │    load payload[i]      │
    │                                          │  │    SPI → LR2021 FIFO    │
    │                                          │  │    set_tx(timeout)      │
    │                                          │  │    wait TX_DONE IRQ     │
    │                                          │  │    delay(GAP us)        │
    │                                          │  └─────────────────────────┘
    │◄──── UART: "TX DONE (RADIO ASLEEP)" ─────│  burst complete
    │── UART: "STAT?\r\n" ────────────────────►│
    │◄──── UART: "OK tx=1000 done=1000 ..." ──│  stats over UART
```

**UART traffic per test run:** ~6 command lines in + 2 response lines out = ~200 bytes total. At 115200 baud this takes <20 ms — negligible compared to the burst duration (1000 × 255B at FLRC-650 with 5 ms gap ≈ 8.1 s).

The UART baud rate could even be **raised to 921600** (the firmware's USART1 IRQ-driven RX supports it per the README: "115200 8N1 (921600 tolerated)"), but there's no need — the command protocol is tiny.

---

## 3. Proposed Firmware Architecture for FLRC Throughput Testing

### Already Built: `e80-stm32-bench`

The firmware exists, compiles, and is ready to flash (pending SWD fix). Here's its architecture:

### 3.1 Software Stack

| Layer | Component | Status |
|-------|-----------|--------|
| MCU | STM32F103C8T6 (72 MHz Cortex-M3, 64K flash, 20K RAM) | ✅ |
| HAL | STM32F1 HAL (SPI1, USART1, GPIO, EXTI, IWDG) | ✅ |
| Radio driver | Semtech LR20xx v1.3.1 (vendored from vendor demo) | ✅ |
| Radio HAL | `lr20xx_hal.c` (board-specific SPI/GPIO/BUSY) | ✅ |
| Bench logic | `bench.c`, `radio_bench.c`, `bench_cmd.c`, `bench_stats.c`, `bench_safety.c` | ✅ |
| Host tool | `e80_bench_ctl.py` (Python, drives both TX+RX boards) | ✅ |

**Build output:** text=19,340 + data=116 = **19,456 B flash (30% of 64K)**, bss=**2,700 B RAM (13.5% of 20K)**. Comfortable headroom for both flash and RAM.

### 3.2 FLRC Support in Firmware

The firmware uses the LR20xx driver's FLRC API directly (`radio_bench.c`):

```c
// FLRC modulation params (patched per test config)
static lr20xx_radio_flrc_mod_params_t flrc_mod_params = {
    .br_bw = LR20XX_RADIO_FLRC_BR_0_650_BW_0_740,  // configurable
    .cr    = LR20XX_RADIO_FLRC_CR_3_4,              // fixed at 3/4
    .shape = LR20XX_RADIO_FLRC_PULSE_SHAPE_BT_1,
};

// FLRC packet params
static lr20xx_radio_flrc_pkt_params_t flrc_pkt_params = {
    .preamble_len    = 32_BITS,
    .sync_word_len   = 4_BYTES,
    .header_type     = FIX_LEN,
    .pld_len_in_bytes = 255,  // patched per START command
    .crc_type        = 2_BYTES,
};
```

**Supported FLRC bitrates** (from `bench_cmd.c` parser):
| Command | Air rate | BW |
|---------|----------|----|
| `MOD flrc 260 <dbm>` | 260 kbps | 307 kHz |
| `MOD flrc 325 <dbm>` | 325 kbps | 357 kHz |
| `MOD flrc 520 <dbm>` | 520 kbps | 571 kHz |
| `MOD flrc 650 <dbm>` | 650 kbps | 740 kHz |
| `MOD flrc 1040 <dbm>` | 1040 kbps | 1.33 MHz |
| `MOD flrc 1300 <dbm>` | 1300 kbps | 1.33 MHz |
| `MOD flrc 2080 <dbm>` | 2080 kbps | 2.22 MHz |
| `MOD flrc 2600 <dbm>` | 2600 kbps | 2.67 MHz |

### 3.3 Autonomous TX Burst Architecture

The TX burst state machine runs entirely on the STM32:

1. Host sends `START N=<count> LEN=<bytes> GAP=<us>`
2. Firmware generates a payload buffer (sequential bytes with 4-byte sequence number prefix)
3. For each packet:
   - Set FLRC packet length via SPI
   - Write payload to LR2021 TX FIFO via SPI
   - Issue `set_tx()` with chip-level TX timeout (2× worst-case airtime + 50 ms)
   - Wait for TX_DONE IRQ (DIO8 rising edge → EXTI2 → `radio_bench_irq()`)
   - Delay for GAP microseconds
4. On completion: radio goes to sleep (PA unkeyed), prints `TX DONE (RADIO ASLEEP)`

**On the RX side:**
1. Host sends `ROLE RX` then `START N=<expected> LEN=<bytes> GAP=<us>`
2. Firmware arms RX continuously (re-arms after each IRQ)
3. For each received packet:
   - IRQ → read packet status (RSSI, length) → read FIFO → extract sequence number
   - Accumulate: rx_ok, rx_crc_err, RSSI min/max/sum, sequence span
4. On `STAT?`: reports PER (via sequence span), Wilson 95% CI, throughput (kbps), RSSI avg/min/max, SNR (LoRa only), elapsed time

### 3.4 Safety Architecture (Already Implemented)

| Layer | Mechanism | Implementation |
|-------|-----------|----------------|
| TX inhibit at boot | Radio asleep, requires `ROLE TX` + `ARM TX` | `bench.c` state machine |
| Chip TX timeout | LR2021 hardware timeout per packet | `radio_bench_tx_packet()` |
| Superloop backstop | Software watchdog (2× chip timeout + 50 ms) | `bench_safety.c` |
| IWDG | STM32 independent watchdog (2-4 s window) | Starts at first `ARM TX` |
| EU band enforcement | 863-870 MHz only unless `BAND OVERRIDE <pin>` | `bench_cmd.c` |
| Power cap | +10 dBm indoor default, +22 dBm requires `POWER MODE OUTDOOR <pin>` | `bench.c` |
| Headless re-flash | `FLASH` command → jump to ROM bootloader | `bench.c` |

---

## 4. SPI Bandwidth Analysis: Can STM32F103 Sustain FLRC Packet Rates?

### Verdict: YES — SPI is 3.4× to 13× faster than air time, not the bottleneck

### Current SPI Configuration

| Parameter | Value |
|-----------|-------|
| SPI peripheral | SPI1 (APB2 = 72 MHz) |
| Prescaler | /8 → **9 MHz SCK** |
| Mode | Mode 0 (CPOL=0, CPHA=0), MSB first |
| NSS | Software GPIO (PA4) |
| Data size | 8-bit |

### Per-Packet SPI Transfer Budget

For a 255-byte FLRC packet, the SPI transactions per TX are:

| Transaction | Bytes | SPI time @ 9 MHz |
|-------------|-------|-------------------|
| Set packet params (FLRC) | ~6 cmd + data | ~5 µs |
| Write TX FIFO (255B payload) | 3 cmd + 255 data = 258 | **229 µs** |
| Set TX (trigger) | ~3 | ~3 µs |
| Clear IRQ status | ~3 | ~3 µs |
| **Total SPI per packet** | ~270 | **~240 µs** |

### Air Time vs SPI Time

| FLRC bitrate | 255B air time | SPI time | SPI/air ratio | Headroom |
|--------------|---------------|----------|---------------|----------|
| 260 kbps | 7.85 ms | 0.24 ms | 3.1% | 32× |
| 650 kbps | 3.14 ms | 0.24 ms | 7.6% | 13× |
| 1300 kbps | 1.57 ms | 0.24 ms | 15.3% | 6.5× |
| 2600 kbps | 0.78 ms | 0.24 ms | 30.8% | 3.2× |

Even at FLRC-2600 (the fastest), SPI transfer takes only 31% of air time. The **real bottleneck** is the TX_DONE → re-arm cycle: BUSY pin polling, IRQ latency, and the GAP delay (minimum 100 µs per the parser, typically 5000 µs for bench tests).

### SPI Clock Headroom

The STM32F103 SPI1 can run at up to **18 MHz** (prescaler /4, APB2=72 MHz). At 18 MHz:
- 255B FIFO write: **114 µs** (vs 229 µs at 9 MHz)
- This would support FLRC-2600 with 6.8× headroom

The vendor demo uses 9 MHz; our bench firmware inherits this. Raising to 18 MHz (prescaler /4) is a one-line change in `MX_SPI1_Init()` and would double SPI throughput if needed. No evidence exists that 9 MHz is insufficient — the gap between packets is dominated by the configurable GAP delay and TX turnaround, not SPI.

### Packet Framing Overhead

FLRC packet overhead per the driver types:
- Preamble: 32 bits (4 bytes) — configurable down to 4 bits
- Sync word: 4 bytes — configurable down to 2 or off
- CRC: 2 bytes — configurable up to 4 or off
- Total overhead: ~10 bytes for the default config

For a 255-byte payload, overhead is 3.9% — negligible. For a 51-byte payload (range test default), overhead is 19.6% — more significant but accounted for in throughput calculations (firmware reports goodput = payload bytes × 8 / elapsed time).

---

## 5. Test Methodology Outline

### 5.1 Test Matrix

The firmware supports a comprehensive parameter space. The recommended test matrix for FLRC range-vs-throughput characterization:

**Primary sweep (FLRC modes × distances):**

| FLRC bitrate | BW (kHz) | Payload sizes | Distances |
|-------------|----------|---------------|-----------|
| 260 kbps | 307 | 51, 255 | 1m, 10m, 50m, 100m, 250m, 500m, 1km, 2km, 5km+ |
| 650 kbps | 740 | 51, 255 | same |
| 1300 kbps | 1333 | 51, 255 | same |
| 2600 kbps | 2666 | 51, 255 | same |

**Cross-reference (LoRa modes for calibration):**

| LoRa mode | SF | BW | Payload | Distances |
|-----------|-----|-----|---------|-----------|
| SF7/BW125 | 7 | 125 kHz | 51 | subset |
| SF12/BW125 | 12 | 125 kHz | 51 | subset |

**Parameters held constant:**
- Frequency: 868.0 MHz (EU SRD band) or 915 MHz with `BAND OVERRIDE`
- TX power: +22 dBm outdoor, +10 dBm indoor (per regulatory constraints)
- Coding rate: 3/4 (FLRC), 4/5 (LoRa) — driver defaults
- Packet count: 10,000 (when prior PER < 2%), 1,000 (when PER ≥ 2%), per the range test plan
- GAP: 5000 µs (FLRC), 1000 µs (LoRa)

**Per test cell, collect:**
- PER (packet error rate) via sequence number span
- Wilson 95% confidence interval
- Goodput (kbps) = received_payload_bytes × 8 / elapsed_time
- RSSI avg, min, max (per-packet, FLRC has no SNR)
- Elapsed time
- TX board's sent count (for TX-side verification)

### 5.2 Test Procedure (per distance stop)

```bash
# One trigger per distance stop (host-side):
tools/e80_bench_ctl.py --tx /dev/ttyUSB3 --rx /dev/ttyUSB4 \
    --matrix flrc260,flrc650,flrc1300,flrc2600,sf7,sf12 \
    --csv range/siteA_S3_r2.csv \
    --site siteA --stop S3 --dist-m 200 --repeat 2 \
    --freq 868000000 --dbm 22 --band-override \
    --gps-tx <lat,lon> --gps-rx <lat,lon> \
    --h-tx 1.5 --h-rx 1.5 --ground grass --weather "12C clear" \
    --t0 "2026-08-30 14:05:00"
```

The host tool:
1. Configures both boards (MOD, FREQ, PA)
2. TX board: `ROLE TX`, `ARM TX`, `START N=... LEN=... GAP=...`
3. RX board: `ROLE RX`, `START N=... LEN=...` (arms continuous RX)
4. Waits for TX completion
5. Reads `STAT?` from both boards
6. Appends results to CSV with metadata (site, distance, GPS, weather)
7. Repeats for each mode in the matrix

### 5.3 Expected Range Behavior (Theoretical Framework)

| FLRC bitrate | Sensitivity (est.) | Max range @ +22 dBm, 868 MHz |
|-------------|---------------------|------------------------------|
| 260 kbps | ~-115 dBm | ~5-10 km LOS |
| 650 kbps | ~-108 dBm | ~2-5 km LOS |
| 1300 kbps | ~-102 dBm | ~1-2 km LOS |
| 2600 kbps | ~-96 dBm | ~0.3-1 km LOS |

*Estimates based on FLRC sensitivity being ~6-9 dB worse than LoRa SF12 for equivalent BW, scaling with bandwidth expansion. Actual numbers to be determined empirically.*

The characterization curve will show throughput vs distance, with the FLRC bitrate as the parameter. The key finding is the distance at which each FLRC mode's PER exceeds a usability threshold (e.g., 1% or 10%).

---

## 6. Creative Approaches That Avoid SWD

### 6.1 J2 SPI Bypass (PRIMARY ALTERNATIVE — fully documented, no SWD needed)

The repo contains a complete wiring guide (`docs/e80-900mbl-02-eval/E80-SPI-BYPASS-WIRING.md`) for bypassing the STM32 entirely:

**Method:** Hold the STM32 in reset (tape the RESET button down) → all STM32 GPIOs go Hi-Z → an external MCU drives the LR2021 radio directly via the J2 header pins.

**J2 provides direct access to:**
- SPI: SCK (J2-13), MISO (J2-9), MOSI (J2-11), NSS (J2-15)
- Control: BUSY (J2-7), DIO8/IRQ (J2-10), radio NRST (J2-5)
- Power: 3V3 (J2-2, J2-6), VIN (J2-1) — board self-powered via USB

**External MCU options (both with proven firmware in the balloon project):**
1. **RP2040 Pico** — existing `multi_radio_sweep.cpp` firmware, 20 MHz SPI, proven 1377 kbps E2E FLRC-650
2. **ESP32-C3** — existing `esp32_raw_tx.cpp` / `esp32_raw_rx.cpp` firmware, validated GPIO map

**Advantages:**
- No SWD needed at all — completely bypasses the STM32
- Uses our proven FLRC firmware from the balloon project (already tested at 1377 kbps)
- Non-destructive: release RESET button → stock firmware restored
- J2 is a labeled 2.54mm header — no soldering required for the STM32 side

**Disadvantages:**
- Requires jumper wires (7 signals + GND per board, ~15 cm)
- Two external MCUs needed (one per E80 board)
- STM32's UART/LED path is dead while bypassed (fine for testing)
- SPI signal integrity over jumpers may limit clock to 1-2 MHz initially (vs 9 MHz on-board)
- Does not use the E80's +22 dBm PA cal tables (our firmware would need the PA config)

**Status:** Wiring guide complete with verified pin maps for both RP2040 and ESP32-C3. Ready to execute — only needs physical jumper assembly.

### 6.2 Can FLRC Be Triggered via UART Passthrough to SPI?

**No.** The stock firmware's UART handler (`user_uart.c`) routes bytes through a fixed command parser. There is no "raw SPI passthrough" mode. The command bytes either match a known prefix (C1/C2/C3/C4/C0) and execute a hardcoded radio function, or they're treated as transparent LoRa payload and sent via `radio_tx_custom()` which always uses LoRa packet type.

There is no mechanism to:
- Send arbitrary SPI commands to the LR2021 through the UART
- Change the packet type to FLRC
- Access LR2021 registers directly

The STM32 firmware is a closed binary loop: UART → command parser → LoRa radio functions → SPI. No escape hatch exists.

### 6.3 UART ISP (ROM Bootloader) — Also Dead

The STM32F103 ROM bootloader (0x1FFFF000) is accessible over USART1, but entry requires BOOT0=HIGH at reset. The E80 board has BOOT0 hardwired to GND via a pull-down resistor with no breakout pad. Extensive testing (150s sync spam + RESET on both boards) confirmed ISP entry is impossible without a hardware modification (lifting the BOOT0 pad or finding the pull-down resistor and temporarily driving it high).

The `E80-HARDWARE-CLAIMS-AUDIT.md` documents a plan to locate the BOOT0 pull-down by DMM and temporarily drive it to 3V3, but this is invasive and ranked as a last resort.

### 6.4 SWD Fix (RECOMMENDED — closest to ready)

The diagnosis (`E80-SWD-DIAGNOSIS-2026-08-18.md`) proves SWD is **not** firmware-disabled (the only SWJ call is `__HAL_AFIO_REMAP_SWJ_NOJTAG()` which keeps SW-DP enabled). The failure is physical:

**Most likely cause:** Cold joint on the GND wire (Pico GND ↔ E80 pad 3).

**Required action:** 3 continuity beeps with a multimeter:
1. Pico GND ↔ E80 pad 3 (GND) — **critical**
2. Pico GP2 ↔ E80 pad 1 (SWDIO)
3. Pico GP3 ↔ E80 pad 2 (SWCLK)

If beeps pass, retry `openocd -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg -c "adapter speed 100"`. Once SWD connects: stock dump first (`e80-dump.sh`), then flash `build-fw/e80_bench.bin`.

After first flash, all future re-flashes are headless via the `FLASH` command (jumps to ROM bootloader from firmware).

---

## 7. Minimum Viable Firmware Feature Set

The built firmware (`e80-stm32-bench`) already implements the complete minimum viable feature set:

| Feature | Status | Implementation |
|---------|--------|----------------|
| FLRC mode selection (8 bitrates) | ✅ | `MOD flrc <br_kbps> <dbm>` command |
| LoRa mode (SF5-12, BW 125/250/500) | ✅ | `MOD loRa <sf> <bw>` command |
| Frequency configuration | ✅ | `FREQ <hz>` with EU band enforcement |
| TX power control | ✅ | `PA <dbm>` with indoor/outdoor caps |
| Autonomous TX burst | ✅ | `START N= LEN= GAP=` with IRQ-driven pacing |
| RX continuous with stats | ✅ | `ROLE RX` + `START` arms continuous RX |
| PER calculation | ✅ | Sequence-number span method in `bench_stats.c` |
| Wilson 95% CI | ✅ | `bench_stats_wilson_ppm()` |
| Goodput (kbps) | ✅ | `bench_stats_kbps()` |
| Per-packet RSSI (avg/min/max) | ✅ | `bench_stats_note_rssi()` |
| TX-hang watchdog (3 layers) | ✅ | Chip timeout + superloop backstop + IWDG |
| Headless re-flash | ✅ | `FLASH` → ROM bootloader jump |
| Host-side orchestration | ✅ | `e80_bench_ctl.py` with matrix sweep + CSV |
| FLRC coding rate selection | ❌ | Fixed at CR 3/4 (driver default) |
| FLRC pulse shape selection | ❌ | Fixed at BT_1 (driver default) |

**Missing but non-blocking:**
- FLRC coding rate is hardcoded to 3/4. The driver supports 1/2, 2/3, 3/4, and none (no FEC). Adding CR selection would require a parser extension and a `cr` field in `radio_bench_cfg_t`. This is a ~20-line change across `bench_cmd.c`, `radio_bench.h`, and `radio_bench.c`. Not needed for initial characterization — CR 3/4 is a reasonable default that balances FEC gain and throughput.
- FLRC pulse shape is hardcoded to BT_1. The driver supports OFF, BT_05, BT_07, BT_1. BT_1 provides the best spectral efficiency. No change needed.

---

## 8. Summary Decision Matrix

| Approach | FLRC capable? | UART bottleneck? | SWD needed? | Ready now? | Effort |
|----------|--------------|-------------------|-------------|------------|--------|
| Stock fw + e80ctl.py | ❌ No | N/A | N/A | N/A | — |
| Custom fw (e80-stm32-bench) via SWD | ✅ Yes | ❌ No (UART = config only) | ✅ Yes (fix wiring) | ⏳ SWD fix | Low (beeps + reflash) |
| J2 SPI bypass + RP2040/ESP32-C3 | ✅ Yes | ❌ No (external MCU drives SPI) | ❌ No | ✅ Wiring guide ready | Medium (jumper assembly) |
| UART ISP + custom fw | ✅ Yes | ❌ No | ❌ No (but need BOOT0 mod) | ❌ Needs hw mod | High (board modification) |

### Recommended Path

1. **Immediate (zero new hardware):** Fix SWD wiring — 3 continuity beeps, then reflash. The firmware is built and ready. This is the lowest-effort path to FLRC characterization.
2. **Fallback (if SWD still fails):** J2 SPI bypass with RP2040 Picos. Wiring guide is complete. Uses our proven FLRC firmware. Requires jumper wires but no board modification.
3. **Not recommended:** UART ISP (BOOT0 hardware modification) — invasive, last resort only.

---

## 9. Key Files

| File | Role |
|------|------|
| `tools/e80ctl.py` | Stock firmware UART controller (LoRa only) |
| `firmware/e80-stm32-bench/build-fw/e80_bench.bin` | Built custom bench firmware (FLRC capable) |
| `firmware/e80-stm32-bench/src/radio_bench.c` | FLRC radio control implementation |
| `firmware/e80-stm32-bench/src/bench.c` | Main firmware (TX burst state machine, RX accumulation) |
| `firmware/e80-stm32-bench/src/bench_cmd.c` | UART command parser (MOD flrc, START, STAT?) |
| `firmware/e80-stm32-bench/src/bench_stats.c` | PER/Wilson-CI/throughput/RSSI statistics |
| `firmware/e80-stm32-bench/tools/e80_bench_ctl.py` | Host-side test orchestration |
| `docs/E80-SWD-DIAGNOSIS-2026-08-18.md` | SWD failure analysis (physical, not firmware) |
| `docs/e80-900mbl-02-eval/E80-SPI-BYPASS-WIRING.md` | J2 SPI bypass wiring guide |
| `docs/E80-HARDWARE-CLAIMS-AUDIT.md` | Hardware verification + probe plan |
| `docs/PLAN-E80-LR2021-EVAL-2026-08-15.md` | Original evaluation plan |

---

*End of analysis.*