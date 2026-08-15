# E80-900MBL-02 Evaluation Kit — Capability Report

**Consultant A deliverable · Source set: 3 PDFs + unpacked E80_DEMO STM32 reference**
**Author:** Hermes Agent (Consultant A) · **Date:** 2026-08-15

---

## 0. Sources Consulted

| # | File | Type | Extracted via | Useful content |
|---|------|------|---------------|---------------|
| 1 | `pdfs/e80-900mbl-02-manual-id4396.pdf` (1.1 MB, 11 pp, v1.7) | User Manual | `pdftotext` (389 lines) | ✅ Full text — kit intro, pinout, command list, FAQ |
| 2 | `pdfs/e80-900mbl-02-spec-id4397.pdf` (108 KB, 1 p, v1.7) | Board Schematic | `pdftoppm`+`tesseract` OCR (76 lines) | ⚠️ Garbled OCR; readable: MCU = STM32F103**CB**T6, CH340 USB↔UART, E80-400/900M2212S module, SUB-1G + 2.4G ANT paths, TCXO 32M / 32.768k, LEDs PWR/LINK/Data, SWD |
| 3 | `pdfs/ebyte-doc-id1373.pdf` (2.2 MB, 21 pp, v1.5) | EBYTE Company Brochure | `pdftoppm`+`tesseract` OCR (365 lines) | ❌ Marketing/company profile only — no technical data on this kit |
| 4 | `pdfs/id4393-unpacked/E80_DEMO/` | STM32 reference source | direct read | ✅ Full Keil MDK + CubeMX project, Semtech LR20xx driver v1.3.1 |

> Note on naming: `lr2021-datasheet-id4393.pdf` is actually a **ZIP archive** (not a PDF) that unpacks to `E80_DEMO/`. The two image-only PDFs (#2, #3) had no text layer and were OCR'd at 200 dpi.

---

## 1. Kit Identity

| Field | Value |
|-------|-------|
| Product family | **E80-xxxMBL-02 Series** — Sub-GHz / 2.4 GHz LoRa **Dual-Band** Wireless Module Evaluation Kit |
| Vendor | Chengdu Ebyte Electronic Technology Co., Ltd. (EBYTE) |
| Manual rev. | v1.00, 2026-03-06 (author: Hao) |
| Supported module SKUs | **E80-400M2212S** (LR2021, 400 MHz band) and **E80-900M2212S** (LR2021, 900 MHz band) |
| RF IC | **Semtech LR2021** — "4th-generation LoRa® Plus" dual-band Sub-GHz + 2.4 GHz SoC |
| On-board MCU | STMicroelectronics **STM32F103C8T6** (project target: STM32F103C8; schematic shows CBT6 package) |
| MCU clock | HSE 8 MHz × PLL9 = **72 MHz**; APB1 = 36 MHz, APB2 = 72 MHz |
| Toolchain | Keil MDK-ARM (uVision V5.38), DFP `Keil.STM32F1xx_DFP.2.3.0` |
| Demo driver | Semtech **LR20xx driver v1.3.1** (BSD, © Semtech 2024) — full multi-modem stack |

---

## 2. Hardware / Board Capabilities

### 2.1 On-board Components
- **E80-M series module** (LR2021-based SMD, 22 dBm Sub-GHz PA / 12 dBm 2.4 GHz PA)
- **Dual SMA-K antenna jacks** — one for 2.4 GHz, one for Sub-1 GHz (both SMA female)
- **USB Type-C** — power + firmware flash + UART bridge (on-board **CH340** USB↔UART)
- **3 LEDs** — PWR (power), LED1/LINK, LED2/DATA
- **2 user keys** — KEY1, KEY2 + RESET button
- **SWD debug header**
- **Two 2.54 mm pin headers** (J1, J2) — all free GPIO broken out

### 2.2 Module ↔ MCU Pin Map (from `main.h` + manual + schematic OCR)

| Signal | MCU pin | Direction / Role |
|--------|---------|------------------|
| E80_BUSY | PA3 | Input — radio BUSY (SPI flow control) |
| RADIO_NSS | PA4 | Output — SPI NSS (manual GPIO, not hardware NSS) |
| E80_NRST | PB0 | Output — radio hardware reset |
| E80_DIO9 | PB1 | EXTI1 rising — radio IRQ (secondary) |
| E80_DIO8 | PB2 | EXTI2 rising — radio IRQ (**primary**, wired to `radio_irq_callback`) |
| E80_DIO7 | PB10 | Input — radio DIO (unused in demo) |
| LED2 (DATA) | PB12 | Output, active-low |
| LED1 (LINK) | PB13 | Output, active-low |
| KEY2 | PB14 | Input, pull-up, active-low |
| KEY1 | PB15 | Input, pull-up, active-low |
| SPI1 SCK / MISO / MOSI | PA5 / PA6 / PA7 | SPI master → radio |
| USART1 TX/RX | PA9 / PA10 | 115200 8N1 ↔ CH340 ↔ USB |

> Module exposes DIO5–DIO11; only DIO8 (IRQ) and DIO9 are wired on the kit. DIO8 is configured in firmware as `LR20XX_SYSTEM_DIO_FUNC_IRQ` with pull-down drive.

### 2.3 SPI Configuration
- SPI1 master, 8-bit, Mode 0 (CPOL=0, CPHA=0), MSB first, prescaler 8 → **9 MHz SCK** (72/8)
- NSS is software-controlled GPIO (manual set/reset around each transaction)
- HAL implements the **LR20xx SPI protocol**: write = cmd+cdata; read = cmd, then dummy 2 bytes, then payload; BUSY pin polled between phases; NSS-glitch wakeup from sleep (BUSY is HIGH in sleep)

---

## 3. RF / Modem Capabilities (LR2021 via LR20xx driver v1.3.1)

### 3.1 Frequency Coverage (dual-band, runtime-switchable)
| Band | Range (from demo clamping logic) | PA path | Max TX power |
|------|---------------------------------|---------|--------------|
| **Sub-GHz LF** | ~400–960 MHz (demo clamps >950 MHz; separate 400–550 MHz tuning) | `PA_SEL_LF` | **+22 dBm** (0x2C) |
| **2.4 GHz HF** | 2400–2500 MHz (demo enforces ≥2400 MHz) | `PA_SEL_HF` | **+12 dBm** (0x18) |

> Switching is **automatic in firmware**: if `freq >= 2400000000`, HF PA + HF RX path; else LF PA + LF RX path. The 400–550 MHz sub-range uses a different `pa_lf_slices` tuning (7 vs 6).

### 3.2 PA Power Tables (`lr20xx_pa_pwr_cfg.h`)
- **LF table:** 33 entries, **−10 dBm … +22 dBm** in 1 dB steps (half_power / pa_duty_cycle / pa_lf_slices triplets)
- **HF table:** 30 entries, **−17 dBm … +12 dBm** in 1 dB steps (marked TODO — values still preliminary)
- Ramp time used by demo: `LR20XX_RADIO_COMMON_RAMP_304_US`
- PA mode: `PA_LF_MODE_FSM` (LF), DC-DC regulator mode when TCXO fitted

### 3.3 Modulations Available in Driver (all linked into build per `.map`)
The LR20xx driver is a **multi-protocol** stack. Demo firmware only exercises **LoRa**, but the full driver (compiled + linked) supports:

| Modem | Driver file | Notes |
|-------|-------------|-------|
| **LoRa** | `lr20xx_radio_lora.c` | Used by demo — SF5–SF12, BW 125/203/500 kHz (and more), CR 4/5–4/8, LDRO (ppm) on/off, explicit/implicit, CRC, IQ inversion, syncword |
| **FSK** | `lr20xx_radio_fsk.c` | GFSK/FSK packet modes |
| **OOK** | `lr20xx_radio_ook.c` | On-Off Keying |
| **BPSK** | `lr20xx_radio_bpsk.c` | Binary Phase Shift Keying |
| **FLRC** | `lr20xx_radio_flrc.c` | Fast LoRa (FLRC) — high data rate |
| **LR-FHSS** | `lr20xx_radio_lr_fhss.c` | LoRa Alliance LR-FHSS (satellite/IoT) |
| **IEEE 802.15.4 OQPSK** | `lr20xx_radio_oqpsk_15_4.c` | 2.4 GHz 802.15.4 PHY |
| **Wi-SUN** | `lr20xx_radio_wi_sun.c` | Wi-SUN FAN PHY |
| **Wireless M-Bus** | `lr20xx_radio_wm_bus.c` | WM-Bus modes (T/C/S/R/N/F) |
| **Z-Wave** | `lr20xx_radio_z_wave.c` | Z-Wave PHY |
| **BLE** | `lr20xx_radio_bluetooth_le.c` | Bluetooth Low Energy PHY |
| **RTToF** | `lr20xx_rttof.c` | **Round-Trip Time-of-Flight** ranging |

> This is a remarkably broad PHY set for a single SoC — the LR2021 chip is essentially a universal Sub-GHz + 2.4 GHz multi-protocol radio. Only LoRa is exercised by the Ebyte demo; all others are dormant-but-linked and could be activated by adding the appropriate `set_pkt_type` + modem config calls.

### 3.4 LoRa Modulation Parameters (demo defaults in `user_radio.c`)
| Parameter | Default | Configurable via `radio_inits()` |
|-----------|---------|----------------------------------|
| Spreading Factor | **SF8** | SF5–SF12 (enum `lr20xx_radio_lora_sf_t`) |
| Bandwidth | **125 kHz** | 7.8–2000 kHz range (BW_125/203/500 used in test cmds) |
| Coding Rate | **4/5** | 4/5, 4/6, 4/7, 4/8 |
| Preamble | **8 symbols** | — |
| Packet type | **Explicit** | Explicit / Implicit |
| Payload | **255 bytes** (max) | 1–255 |
| CRC | **On** | On/Off |
| IQ inversion | **Off** | On/Off |
| Sync word | **0x34** (default) then **0x12** in test cmds | 1 byte, per-packet configurable |
| LDRO (ppm) | **Off** (NO_PPM) | On/Off — low-data-rate optimization |
| RX/TX fallback | `STDBY_RC` | auto-return to standby after TX |

### 3.5 Sleep / Low-Power
- `radio_sleep()` → `lr20xx_system_set_sleep_mode()` with **RAM retention enabled**, 32 kHz clock disabled
- Manual states sleep current ≈ **2 µA** (code comment says 7.6 µA — likely the module-vs-chip distinction)
- MCU can additionally enter `HAL_PWR_EnterSLEEPMode` (WFI) — demo uses SLEEP, not STOP
- Wakeup: NSS glitch (pull NSS low 5–10 ms, release, wait BUSY low) — implemented in `lr20xx_hal_wakeup` / `check_device_ready`

### 3.6 TCXO / Crystal
- Demo defaults to **TCXO** (`TXCO = true`): DC-DC regulator mode, TCXO control voltage **2.2 V**, startup timeout 64000 (≈2 ms)
- Crystal (XOSC) path also supported: standby-RC mode, load cap configure (`0x1C, 0x1C, 0xFF`)
- LF clock: RC internal (`LR20XX_SYSTEM_LFCLK_RC`)
- Calibration: `lr20xx_system_calibrate(0x7F)` — all blocks

---

## 4. Demo Firmware Architecture

### 4.1 Software Layers (per manual §3.1)
```
Application layer  → Core/Src/main.c, user_radio.c, user_uart.c, event.c, fifo.c
MCU HAL            → STM32Cube HAL (stm32f1xx_hal_*.c)
RF driver          → Radio/lr20xx_driver/ (Semtech LR20xx v1.3.1)
RF HAL (BSP)       → Radio/radio_hal/lr20xx_hal.c, radio_utilities.c
```

### 4.2 Event System (`event.c/h`)
Simple bitmask event flags (volatile uint32):
- `EVENT_UART_RX_DONE` (0x01) — UART frame received (2 ms idle timeout)
- `EVENT_UART_TX_DONE` (0x02)
- `EVENT_RADIO_RX_DONE` (0x04) — LoRa packet received
- `EVENT_MODE_SWITCH` (0x08), `EVENT_RADIO_RESET` (0x10) — defined but unused in demo
- Main loop polls `event_check()` → handles UART or radio events

### 4.3 UART Subsystem (`user_uart.c/h`, `fifo.c/h`)
- **115200 baud, 8N1**, interrupt-driven TX/RX with software FIFOs
- RX framing: **2 ms inter-byte idle timeout** → sets `EVENT_UART_RX_DONE`
- Blocking `HAL_UART_Transmit` used for printf + command echoes
- `printf` retargeted to USART1 via `fputc`

### 4.4 Radio IRQ Path (`user_radio.c`)
- DIO8 EXTI2 rising-edge → `HAL_GPIO_EXTI_Callback` → `radio_irq_callback()`
- IRQ status read via `lr20xx_system_get_and_clear_irq_status`
- Handled: **RX_DONE** (read FIFO, set event, re-enter RX), **TX_DONE** (re-enter RX), **TIMEOUT**, **HEADER_ERROR**, **CRC_ERROR** (all → re-enter RX)
- RX IRQ mask: `RX_DONE | CRC_ERROR`
- TX IRQ mask: `TX_DONE`

### 4.5 UART Command Protocol (transparent mode + hex commands)

The demo is a **serial-to-LoRa transparent transceiver** with special hex command prefixes:

| Command (hex) | Length | Function |
|---------------|--------|----------|
| `C1 00 + freq[4]` | 6 | **Set RF frequency** (4-byte big-endian Hz); auto-switches LF/HF PA & TX params; re-enters RX |
| `C1 02 00` / `C1 02 01` | 3 | **CW carrier** stop / start (`TX_TEST_MODE_CONTINUOUS_WAVE`) |
| `C1 03 00` / `C1 03 01` | 3 | **RF sleep** exit / enter (MCU also enters WFI sleep) |
| `C1 C1 C1` | 3 | **Auto-transmit** built-in 20-byte test payload `{0,1,2,…,9,0,1,…,9}` |
| `C2 [?][power][SF][BW][CR][ppm][syncword][freq×4]` | 12 | **One-shot RF param config** via `radio_inits()` — sets power, SF, BW, CR, LDRO, syncword, frequency in one frame |
| `C0 00 01` | 3 | **Factory test mode** ON — echoes `C0 01 01`; RX data is **looped back via RF** instead of printed to UART |
| `C3 C3 00 + freq[4]` | 7 | **Long-range test (Sub-G):** SF12 / BW125 / CR4-5 / LDRO-on / sync 0x12 (~0.292 kbps) |
| `C3 C3 01 + freq[4]` | 7 | **Long-range test (2.4G):** SF12 / BW203 / CR4-5 / LDRO-on (~0.476 kbps) |
| `C3 C3 02 + freq[4]` | 7 | **2.4K comparison test:** SF11 / BW500 / CR4-5 / LDRO-on |
| `C4 C4 00 + freq[4]` | 7 | **Sensitivity test (Sub-G):** SF9 / BW125 / CR4-5 / LDRO-off / sync 0x12 |
| `C4 C4 01 + freq[4]` | 7 | **Sensitivity test (2.4G):** SF9 / BW125 / CR4-5 / LDRO-off |
| *anything else* | any | **Transparent TX** — data sent over LoRa as-is via `radio_tx_custom()` |

> Default boot: `radio_init(0x2C, 850000000)` → **850 MHz, +22 dBm, SF8, BW125, CR4-5, sync 0x34**, then enters RX. Any non-command UART data is immediately transmitted over LoRa.

---

## 5. Key Observations & Findings

### 5.1 Strengths
1. **True dual-band operation** — Sub-GHz (400–960 MHz) and 2.4 GHz from a single LR2021 SoC, with automatic PA/RX-path switching in firmware. Both antenna jacks are populated.
2. **Full Semtech LR20xx v1.3.1 driver linked** — all 12 modems (LoRa, FSK, OOK, BPSK, FLRC, LR-FHSS, 802.15.4, Wi-SUN, WM-Bus, Z-Wave, BLE, RTToF) are compiled in. Only LoRa is exercised; the rest are available at zero incremental integration cost.
3. **High TX power** — +22 dBm Sub-GHz, +12 dBm 2.4 GHz, with 1-dB-resolution PA calibration tables.
4. **Low sleep current** — ~2 µA (radio) with RAM retention; MCU sleep also demonstrated.
5. **Clean event-driven architecture** — simple but effective; UART + radio events polled in main loop, interrupt-driven I/O with FIFOs.
6. **Rich command interface** — frequency, CW, sleep, one-shot param config, factory loopback, long-range and sensitivity test presets — all over a simple hex UART protocol.

### 5.2 Limitations & Gaps
1. **No LoRaWAN stack** — demo is raw LoRa P2P only. No MAC layer, no join, no encryption beyond LoRa CRC. LoRaWAN would require porting a separate stack (e.g., LoRaMac-node, Semtech's `smtc_modem`).
2. **Command protocol is brittle** — fixed-length frames, no checksum/ACK, magic-byte prefixes (`C1`/`C2`/`C3`/`C4`/`C0`) can collide with payload data in transparent mode. No framing escape mechanism.
3. **No CAD (Channel Activity Detection)** mode implemented, no duty-cycle management, no frequency hopping.
4. **DIO9 wired but unused** — only DIO8 is configured as IRQ. DIO7 and DIO9 are available on the pin header but not driven.
5. **`radio_utilities.c`** exposes only a TX power offset getter/setter — minimal; no real utility layer (no RSSI reporting, no SNR, no packet stats to UART, though `lr20xx_radio_lora_get_packet_status` is called internally but the status is discarded).
6. **HF PA table marked TODO** — 2.4 GHz power calibration values are preliminary per Semtech's own comment.
7. **BLE/802.15.4/RTToF not demonstrated** — despite being linked. These would need protocol-stack-level code (LL/FH/MAC) that is not present.
8. **STM32F103C8** — 64 KB Flash / 20 KB RAM. The full LR20xx driver + demo fits, but adding a LoRaWAN MAC + application on top will be tight on Flash.
9. **No acknowledgment/retry logic** — TX is fire-and-forget; no retransmission, no ARQ.

### 5.3 Security Posture
- **No encryption** at application layer — LoRa CRC only (detects corruption, not tampering).
- **No authentication** — any module with matching syncword + frequency can inject/intercept traffic.
- For balloon / critical telemetry, an application-layer AEAD (e.g., AES-CCM with sequence numbers) must be added on top.

---

## 6. Suitability Assessment for Balloon Telemetry

| Requirement | E80-900M2212S / E80-400M2212S capability |
|-------------|------------------------------------------|
| **Long range (100+ km LOS at altitude)** | ✅ Excellent — SF12/BW125 Sub-GHz at +22 dBm; LR-FHSS also available for ultra-narrowband |
| **Dual-band backup (2.4 GHz)** | ✅ 2.4 GHz LoRa available (lower power +12 dBm, but 2.4 GHz antenna path present) |
| **Low power for long flight** | ✅ 2 µA sleep; can duty-cycle RX |
| **Small packet telemetry** | ✅ Up to 255 bytes/packet, transparent mode |
| **Frequency agility / hopping** | ⚠️ Frequency settable per-command, but no built-in hopping — must implement in app layer |
| **Encryption / authentication** | ❌ Must add at application layer |
| **ACK / retry** | ❌ Must add at application layer |
| **RTToF ranging (balloon distance)** | ⚠️ Driver present but not demonstrated — requires bilateral ranging firmware |
| **Regulatory compliance** | ⚠️ Sub-GHz regional bands must be respected; 2.4 GHz is global ISM |

---

## 7. Files Created/Modified

| File | Action |
|------|--------|
| `E80-900MBL-02_CAPABILITY_REPORT.md` (this file) | **Created** at `/home/c03rad0r/repos/lr2021-eval/` |
| `/tmp/pdftxt/e80-900mbl-02-manual-id4396.txt` | Extracted via `pdftotext` (pre-existing) |
| `/tmp/pdftxt/e80-900mbl-02-spec-ocr.txt` | Extracted via `pdftoppm`+`tesseract` OCR |
| `/tmp/pdftxt/ebyte-doc-id1373-ocr.txt` | Extracted via `pdftoppm`+`tesseract` OCR |
| `/tmp/pdftxt/ocr/*.png` | Intermediate OCR page images (temp) |

No source-tree files were modified.

---

## 8. Issues Encountered

1. **`lr2021-datasheet-id4393.pdf` is a ZIP, not a PDF** — `pdftotext` failed with "couldn't find trailer dictionary". Already unpacked to `id4393-unpacked/E80_DEMO/` — used the unpacked source directly.
2. **Spec sheet and company-brochure PDFs are image-only** (no text layer) — required OCR at 200 dpi. The spec (schematic) OCR is partially garbled due to dense schematic graphics, but pin/signal names were cross-validated against `main.h` and the manual.
3. **`ebyte-doc-id1373.pdf` is an EBYTE corporate brochure**, not a technical datasheet — no useful technical content for this kit. The actual module datasheet (E80-xxxM2212S) is referenced but not included in the provided PDF set.
4. **`rg` (ripgrep) not installed** — used `grep`/`tr`/`sed` instead for build-file parsing.
5. **No LR2021 chip datasheet** in the provided set — capabilities inferred from the driver source (v1.3.1), PA tables, and the manual. Power/sensitivity numbers should be confirmed against the Semtech LR2021 datasheet when available.

---

*End of report.*
