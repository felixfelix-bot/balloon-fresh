# ESP32-C3 MINI-1 Pinout Verification + V2-ADC Pinmap

**Date:** 2026-08-05
**Task:** t_00b20081 (PCB-V2 Phase 2)
**Datasheet:** ESP32-C3-MINI-1 & MINI-1U Datasheet v2.2 (Espressif)
**Source:** https://www.espressif.com/sites/default/files/documentation/esp32-c3-mini-1_datasheet_en.pdf

---

## 1. ESP32-C3 MINI-1 Module — Verified Pinout

The MINI-1 module has 53 pads. Only **15 GPIOs** are broken out (plus EN, 3V3, GND).

### Complete Module Pin Map (Table 3-1, datasheet p.11)

| Module Pin | GPIO | ADC Channel | Strapping | Other Functions | Notes |
|------------|------|-------------|-----------|-----------------|-------|
| 5 | GPIO2 | ADC1_CH2 | YES (floats) | FSPIQ | Boot mode bit |
| 6 | GPIO3 | ADC1_CH3 | no | FSPIHD, MTMS | |
| 8 | EN | — | — | Chip enable | High=on, Low=off. Do not float. |
| 12 | GPIO0 | ADC1_CH0 | NO | XTAL_32K_P | Not strapping on C3 (unlike ESP32) |
| 13 | GPIO1 | ADC1_CH1 | no | XTAL_32K_N | |
| 16 | GPIO10 | — | no | FSPICS0 | |
| 18 | GPIO4 | ADC1_CH4 | no | MTMS | |
| 19 | GPIO5 | ADC2_CH0 | no | FSPIWP, MTDI | ADC2 may be unavailable (errata) |
| 20 | GPIO6 | — | no | FSPICLK, MTCK | |
| 21 | GPIO7 | — | no | FSPID, MTDO | |
| 22 | GPIO8 | **NONE** | YES (floats) | — | Boot mode + ROM print. NO ADC! |
| 23 | GPIO9 | — | YES (weak pull-up) | — | Boot mode bit |
| 26 | GPIO18 | — | no | **USB_D-** | Available as GPIO if USB disabled |
| 27 | GPIO19 | — | no | **USB_D+** | Available as GPIO if USB disabled |
| 30 | GPIO20 | — | no | U0RXD | UART0 RX (console) |
| 31 | GPIO21 | — | no | U0TXD | UART0 TX (console) |

### Pins NOT broken out on MINI-1 module
- GPIO11-GPIO17: not bonded (SPI flash pins, internally connected)
- GPIO18 and GPIO19: **ARE broken out** (contrary to V1-PCB-GPIO-FIX.md claim)

---

## 2. Answers to Verification Questions

### Q1: Which GPIOs are available on ESP32-C3 MINI-1 module?

**15 GPIOs:** GPIO0, GPIO1, GPIO2, GPIO3, GPIO4, GPIO5, GPIO6, GPIO7, GPIO8, GPIO9, GPIO10, GPIO18, GPIO19, GPIO20, GPIO21.

GPIO11-GPIO17 are NOT broken out (used for internal SPI flash).

### Q2: GPIO18/GPIO19 — USB-only? Can they be used as GPIO?

**GPIO18 and GPIO19 ARE broken out on the MINI-1 module** (pins 26 and 27).

They are the USB Serial/JTAG D- and D+ pins. By default, the USB function is enabled and the internal pull-up is controlled by the USB controller. **When the USB function is disabled, these pins can be used as regular GPIOs.**

Quote from ESP32-C3 datasheet: "When the USB function is disabled, USB pins are used as regular GPIOs and the pin's internal weak pull-up and pull-down resistors will be used."

For balloon flight: USB is not used → GPIO18 and GPIO19 are available as regular GPIO. This means:
- **LED on GPIO18: YES, works** (USB disabled in flight)
- **FEM_TX on GPIO19: YES, works** (USB disabled in flight)

**CORRECTION to V1-PCB-GPIO-FIX.md:** That document incorrectly stated "GPIO18/GPIO19 NOT on ESP32-C3 Mini V1 Header." This was based on a custom header footprint that only broke out 16 pads, not the actual MINI-1 module. The MINI-1 module DOES expose GPIO18 (pin 26) and GPIO19 (pin 27).

### Q3: GPIO0 — boot strap pin needing pull-up?

**GPIO0 is NOT a strapping pin on the ESP32-C3.** The three strapping pins are GPIO2, GPIO8, and GPIO9.

GPIO0 is ADC1_CH0 and XTAL_32K_P. It does not need a pull-up for boot. It can be used freely for FEM_TX or ADC without boot concerns.

(Note: GPIO0 IS a strapping pin on the original ESP32 and ESP32-S3, but NOT on the ESP32-C3. This was a common misconception.)

### Q4: GPIO2 — boot strap pin needing pull-down? OK for MISO?

**GPIO2 IS a strapping pin.** It floats by default (no internal pull-up or pull-down).

For boot mode selection, GPIO2 must be at the correct logic level at reset. Since it floats, an external pull-down resistor (10kΩ) ensures consistent boot behavior. The current plan already includes R_PD (10kΩ pull-down on GPIO2).

**Using GPIO2 as SPI MISO is OK** with the external pull-down. After boot, the strapping latch stores the value and the pin is freed for regular I/O. The LR2021 MISO line will drive the pin during SPI transactions; the 10kΩ pull-down is weak enough not to interfere with SPI signals but strong enough to keep GPIO2 LOW during boot.

**Risk:** If the LR2021 has an internal pull-up on MISO that is active at boot, it could fight the external pull-down and cause unpredictable boot behavior. The 10kΩ external pull-down should win against a typical 100kΩ+ internal pull-up, but this should be verified with the actual LR2021 module.

---

## 3. Critical Finding: GPIO8 Has NO ADC

**The V2-ADC plan assigns GPIO8 to supercap voltage monitoring (ADC). This does NOT work.**

GPIO8 is listed in the datasheet as simply "GPIO8" — it has **no ADC channel assignment**. The ADC-capable pins on the ESP32-C3 are:

| GPIO | ADC Channel | Notes |
|------|-------------|-------|
| GPIO0 | ADC1_CH0 | Free (GPS TX disabled) |
| GPIO1 | ADC1_CH1 | Used by GPS RX |
| GPIO2 | ADC1_CH2 | Used by SPI MISO (strapping) |
| GPIO3 | ADC1_CH3 | Used by LR2021 RST |
| GPIO4 | ADC1_CH4 | Used by LR2021 BUSY |
| GPIO5 | ADC2_CH0 | Used by LR2021 DIO9. ADC2 may be unavailable (errata) |

**Only GPIO0 is available for ADC** without displacing a required function.

Additionally, GPIO8 is a strapping pin (controls boot mode + ROM message printing). Using it for analog voltage measurement would require careful strap management — another reason to avoid it.

---

## 4. V1-FAST Pinmap (Verified — current pinmap, ADC disabled)

| Function | GPIO | Module Pin | Status | Notes |
|----------|------|------------|--------|-------|
| GPS UART RX | GPIO1 | 13 | OK | NMEA from GPS |
| GPS UART TX | GPIO0 | 12 | Disabled (-1) | Set GPS_UART_TX_PIN=-1 |
| SPI MISO | GPIO2 | 5 | OK | **10kΩ pull-down required (strapping)** |
| LR2021 RST | GPIO3 | 6 | OK | Active-low reset |
| LR2021 BUSY | GPIO4 | 18 | OK | IRQ/handshake |
| LR2021 DIO9 | GPIO5 | 19 | OK | IRQ pin |
| SPI SCK | GPIO6 | 20 | OK | SPI clock |
| SPI MOSI | GPIO7 | 21 | OK | C3 → LR2021 |
| (unused) | GPIO8 | 22 | — | Strapping pin. Leave unconnected. |
| LED | GPIO9 | 23 | OK | Strapping (weak pull-up). LED is fine. |
| SPI NSS | GPIO10 | 16 | OK | Chip select |
| LED (current fw) | GPIO18 | 26 | OK | USB_D- — works as GPIO when USB disabled |
| FEM_TX | GPIO19 | 27 | OK | USB_D+ — works as GPIO when USB disabled |
| UART RX (console) | GPIO20 | 30 | OK | U0RXD — console debug |
| UART TX (console) | GPIO21 | 31 | OK | U0TXD — console debug |

**Firmware change needed:** `LED_GPIO` in app_main.cpp is already 18, which is correct and available on MINI-1. No change needed.

**FEM_TX:** Kconfig default is 19 (GPIO19), which is available on MINI-1. No change needed.

**V1-FAST verdict: All current pin assignments are valid on the MINI-1 module.** The V1-PCB-GPIO-FIX.md was based on a custom header footprint that didn't break out GPIO18/19, but the actual MINI-1 module has them.

---

## 5. V2-ADC Pinmap (Corrected — frees GPIO0 for ADC)

### Problem with original V2-ADC plan
The execution plan V2 proposed moving FEM_TX to GPIO0 and using GPIO8 for ADC. **This is wrong because GPIO8 has no ADC channel.** The corrected approach frees GPIO0 (which IS ADC1_CH0) for the voltage divider and keeps FEM_TX on GPIO19.

### Corrected V2-ADC Pinmap

| Function | GPIO | Module Pin | ADC | Strapping | Notes |
|----------|------|------------|-----|-----------|-------|
| **ADC (supercap VDIV)** | **GPIO0** | **12** | **ADC1_CH0** | no | **Freed for voltage divider** |
| GPS UART RX | GPIO1 | 13 | ADC1_CH1 | no | NMEA from GPS |
| GPS UART TX | — | — | — | — | Disabled (-1 in Kconfig). Was GPIO0, now freed. |
| SPI MISO | GPIO2 | 5 | ADC1_CH2 | YES | 10kΩ pull-down required |
| LR2021 RST | GPIO3 | 6 | ADC1_CH3 | no | Active-low reset |
| LR2021 BUSY | GPIO4 | 18 | ADC1_CH4 | no | IRQ/handshake |
| LR2021 DIO9 | GPIO5 | 19 | ADC2_CH0 | no | IRQ pin |
| SPI SCK | GPIO6 | 20 | — | no | SPI clock |
| SPI MOSI | GPIO7 | 21 | — | no | C3 → LR2021 |
| (unused) | GPIO8 | 22 | **NONE** | YES | Strapping. Leave unconnected. |
| LED | GPIO9 | 23 | — | YES (pull-up) | Debug LED |
| SPI NSS | GPIO10 | 16 | — | no | Chip select |
| (unused/USB) | GPIO18 | 26 | — | no | USB_D- — available if USB disabled |
| FEM_TX | GPIO19 | 27 | — | no | USB_D+ — available if USB disabled |
| UART RX | GPIO20 | 30 | — | no | Console |
| UART TX | GPIO21 | 31 | — | no | Console |

### Changes from V1-FAST → V2-ADC
1. **GPIO0:** was GPS UART TX (disabled) → now ADC supercap voltage divider (ADC1_CH0)
2. **Add components:** R_DIV1 (100kΩ), R_DIV2 (100kΩ) for voltage divider on GPIO0
3. **FEM_TX stays on GPIO19** (does NOT move to GPIO0 as the original plan proposed)
4. **GPIO8 stays unused** (strapping pin, no ADC — do not use for analog)

### Firmware changes for V2-ADC
- Kconfig: `GPS_UART_TX_PIN` already defaults to -1 (disabled) — no change needed
- Kconfig: `FEM_TX_PIN` stays at 19 — no change needed
- New: ADC read on GPIO0 (ADC1_CH0) for supercap voltage monitoring
- `LED_GPIO` stays at 18 — available on MINI-1

### Voltage Divider Design
```
3V3 ──[R_DIV1 100kΩ]──┬── GPIO0 (ADC1_CH0)
                       │
                    [R_DIV2 100kΩ]
                       │
                      GND
```
With 100kΩ/100kΩ divider: V_GPIO0 = V_supercap / 2.
Supercap max ~5.5V → ADC reads ~2.75V (within 0-3.3V ADC range).
ADC1_CH0 on ESP32-C3 is 12-bit (0-4095), attenuable to 0-3.3V with `ADC_ATTEN_DB_11`.

---

## 6. Flagged Pins — Do NOT Exist or Cannot Use

| Pin | Issue | Severity | Resolution |
|-----|-------|----------|------------|
| GPIO8 (ADC) | **No ADC channel on GPIO8.** Plan V2-ADC used it for supercap monitoring. | **CRITICAL** | Use GPIO0 (ADC1_CH0) instead. See corrected pinmap above. |
| GPIO11-17 | Not broken out on MINI-1 module (internal SPI flash) | Info | Do not reference in netlist. |
| GPIO18 (LED) | Was flagged as "not available" in V1-PCB-GPIO-FIX.md | **RESOLVED** | GPIO18 IS broken out (pin 26). Available as GPIO when USB disabled. |
| GPIO19 (FEM_TX) | Was flagged as "not available" in V1-PCB-GPIO-FIX.md | **RESOLVED** | GPIO19 IS broken out (pin 27). Available as GPIO when USB disabled. |
| GPIO0 (strap) | Task body asked if it needs pull-up for boot | **RESOLVED** | GPIO0 is NOT a strapping pin on C3. No pull-up needed for boot. |

---

## 7. Strapping Pin Summary

| GPIO | Module Pin | Default | What it Controls | Our Use | Safe? |
|------|------------|---------|-------------------|---------|-------|
| GPIO2 | 5 | Floating | Boot mode bit | SPI MISO + 10kΩ pull-down | YES — pull-down ensures LOW at boot, freed after reset |
| GPIO8 | 22 | Floating | Boot mode bit + ROM print | Unused (leave floating) | YES — floating is the default, safe |
| GPIO9 | 23 | Weak pull-up | Boot mode bit | LED | YES — LED is output, pull-up keeps it HIGH at boot (LED off), freed after reset |

---

## 8. V1-PCB-GPIO-FIX.md Correction

The V1-PCB-GPIO-FIX.md document (written during task t_2c801d32) contains incorrect information:

> "The ESP32-C3 Mini V1 module exposes: GPIO0-10, GPIO20, GPIO21 only. GPIO18 = USB D-, GPIO19 = USB D+ (dedicated USB pins, not available as GPIO)."

This is **incorrect**. Per the official ESP32-C3-MINI-1 datasheet (v2.2, Table 3-1):
- GPIO18 is broken out on **module pin 26** as "GPIO18, USB_D-"
- GPIO19 is broken out on **module pin 27** as "GPIO19, USB_D+"
- Both can be used as regular GPIO when the USB function is disabled

The confusion likely arose from a custom "ESP32-C3_Mini_V1_Header" footprint that only broke out 16 pads and omitted GPIO18/GPIO19. The actual MINI-1 module has 53 pads and does expose these pins.

**Impact:** The V1-PCB-GPIO-FIX.md workaround (test point pads TP5/TP6 for hand-wiring) was unnecessary if using the full MINI-1 module footprint. For the V2 board redesign, use the correct MINI-1 module footprint with all 53 pads.

---

## 9. Netlist Corrections for V2-ADC

The execution plan's V2-ADC net list has these errors that must be corrected before board creation:

1. **FEM_TX net:** Plan connects FEM_TX to C3:GPIO0. **Correct: C3:GPIO19** (keep original assignment).
2. **VDIV_MID net:** Plan connects VDIV_MID to C3:GPIO8. **Correct: C3:GPIO0** (GPIO0 = ADC1_CH0).
3. **GPS TX:** Already disabled (-1). GPIO0 was GPS TX in V1, now repurposed for ADC. No conflict.

### Corrected V2-ADC Additional Nets
- **VDIV_MID:** C3:GPIO0 (pin 12), R_DIV1:2, R_DIV2:1 — voltage divider midpoint
- **FEM_TX:** C3:GPIO19 (pin 27), FEM:TX — same as V1-FAST (unchanged)

---

## Summary

| Gate | Status | Details |
|------|--------|---------|
| Gate 1: Document verified pinout | ✅ | This file: tracker/hardware/PINOUT_VERIFICATION.md |
| Gate 2: Flag pins not on MINI-1 | ✅ | GPIO8 has no ADC (CRITICAL). GPIO11-17 not broken out. GPIO18/19 ARE broken out (corrects V1-PCB-GPIO-FIX.md). |
| Gate 3: V2-ADC pinmap with freed ADC pin | ✅ | GPIO0 (ADC1_CH0) freed for supercap VDIV. FEM_TX stays on GPIO19. |
| Gate 4: Git commit + push | ⏳ | Pending commit |