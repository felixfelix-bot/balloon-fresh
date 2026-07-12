# Auto-BOOTSEL Recovery: ESP32-C3 → RP2040 Flight Board Design

> **STATUS: VERIFIED WORKING (2026-07-13)**
> Full pipeline tested: ESP32 GPIO pulse → RP2040 bootloader → UF2 flash → reboot.
> Commit e9102be. Direct wire connection, zero resistors.

## Problem
The RP2040's USB CDC interface dies when firmware uses tight SPI loops without
calling `yield()`. Once USB CDC is dead, the only recovery is pressing the
physical BOOTSEL button — impossible during a balloon flight at 10km altitude.

## Solution: ESP32 GPIO-Controlled BOOTSEL

The RP2040 has two critical pins for boot mode selection:

| Pin | RP2040 Pin | Pico Label | Function |
|-----|-----------|------------|----------|
| RUN | Pin 30 | TP6 / RUN | Active-low global reset. Pulling LOW for >=1us resets the chip. |
| BOOTSEL | GP0 (Pin 12) | BOOTSEL button | Sampled at boot. LOW during reset -> USB bootloader mode. |

### Circuit Design (VERIFIED — DIRECT WIRE, NO RESISTORS)

```
ESP32-C3                    RP2040
---------                   ------
GPIO1 (D1) ───────────────── RUN button pad (3V3 signal side)
                             (RP2040 internal pull-up keeps HIGH when idle)

GPIO8 (D8) ───────────────── BOOTSEL button pad (3V3 signal side)
                             (RP2040 internal pull-up keeps HIGH when idle)

GND ──────────────────────── GND
```

**NO series resistors. NO external pull-up resistors.**

The RP2040 button pads have their own internal pull-up resistors to 3V3.
The ESP32 output driver can safely sink ~40mA — it overpowers the internal
pull-up when connected directly, pulling the pad to true 0V.

**Why no resistors work:**
- Previous design used 1kΩ series resistors "for protection"
- These created a voltage divider: 3.3V × (1kΩ / (1kΩ_pullup + 1kΩ_series)) = 1.65V
- RP2040 needs < 0.8V for guaranteed logic LOW — 1.65V is undefined no-man's-land
- Direct connection: ESP32 drives to 0V, internal pull-up overpowered, RP2040 sees true LOW

**Total weight added:** ~0g (wire only on flight board, copper traces)

### Wiring: Which Button Pad to Use (CRITICAL)

Each tactile button on the RP2040 has TWO pads:
- **Signal side (3V3)**: reads ~3.3V idle, drops to 0V when pressed. SOLDER HERE.
- **GND side (0V)**: reads 0V always. NEVER solder here.

Identify the correct pad with a multimeter:
1. RP2040 powered (USB plugged in)
2. Multimeter in DC volts mode
3. Black probe to RP2040 GND
4. Red probe to each button pad
5. The pad reading ~3.3V is the signal side — connect ESP32 wire here
6. Verify: press button, voltage should drop to 0V

### Per Board Connections (Verified Working)

| ESP32-C3 Pin | Via | RP2040 Button Pad | External Resistors |
|-------------|-----|-------------------|-------------------|
| GPIO1 (D1) | DIRECT WIRE | RESET button (3V3 side) | NONE |
| GPIO8 (D8) | DIRECT WIRE | BOOTSEL button (3V3 side) | NONE |
| GND | DIRECT WIRE | GND | NONE |

**Parts Needed Per Board:**
- 3× hookup wire (D1, D8, GND)
- NO resistors of any kind

**Priority Order:**
1. RX Board (8332) - This enables automated throughput testing
2. TX Board (F242D) - Optional for now (tx_fast is stable enough)

### BOOTSEL Trigger Sequence (ESP32 Firmware — Verified Working)

```cpp
// Auto-BOOTSEL recovery: ESP32-C3 forces RP2040 into USB bootloader mode
// No physical button needed — works from software at any altitude.
// VERIFIED WORKING 2026-07-13: direct wire, no resistors.

#define PIN_RESET   1   // ESP32 GPIO1 / D1 -> RP2040 RESET button pad
#define PIN_BOOTSEL 8   // ESP32 GPIO8 / D8 -> RP2040 BOOTSEL button pad

void force_rp2040_bootsel() {
    // 1. Hold BOOTSEL LOW (GP0 low during boot = bootloader mode)
    digitalWrite(PIN_BOOTSEL, LOW);
    delay(50);

    // 2. Pulse RESET LOW (reset the RP2040 while BOOTSEL is held low)
    digitalWrite(PIN_RESET, LOW);
    delay(100);
    digitalWrite(PIN_RESET, HIGH);

    // 3. Hold BOOTSEL LOW while RP2040 boots (samples BOOTSEL during boot)
    delay(500);

    // 4. Release BOOTSEL
    digitalWrite(PIN_BOOTSEL, HIGH);

    // RP2040 now appears as RPI-RP2 mass storage device (USB VID 2e8a, PID 0003)
    // Host can flash new firmware via UF2 file copy
}
```

### When to Trigger Auto-BOOTSEL

1. **Watchdog timeout**: ESP32 monitors RP2040 heartbeat. If no heartbeat
   for 30 seconds -> force BOOTSEL + reflash.

2. **Remote command**: Ground station sends "reflash RP2040" via LoRa ->
   ESP32 triggers BOOTSEL -> new firmware uploaded via USB or OTA.

3. **Boot-time verification**: On power-up, ESP32 pings RP2040. If no
   response -> BOOTSEL + flash known-good firmware from SPI flash.

### Integration into Flight Board

The flight board has a dual-MCU architecture:

```
+---------------------------------------------------+
|                 FLIGHT BOARD                       |
|                                                    |
|  +-----------+         +-------------------+      |
|  | ESP32-C3  | D1------| RP2040 RESET btn  |      |
|  |           | D8------| RP2040 BOOTSEL btn|      |
|  | Primary   | SPI-----| LR2021 (shared)   |      |
|  | MCU       | I2C-----| BMP280            |      |
|  +-----+-----+         +-------------------+      |
|        |                                            |
|   USB-C|<-- shared USB bus for flashing both ----- |
|        |                                            |
|  +-----+-----+                                    |
|  |  Solar -> |                                    |
|  |  Caps ->  |                                    |
|  |  LDO 3V3  |                                    |
|  +-----------+                                    |
+---------------------------------------------------+
```

### ESP32-C3 Pin Budget (Updated)

| GPIO | Function | Notes |
|------|----------|-------|
| GPIO0 | ADC (Supercap voltage) | Also UART TX to RP2040 GP21 |
| GPIO1 | RP2040 RESET (direct wire) | Active LOW pulse = reset |
| GPIO2 | SPI MISO (LR2021) | Existing |
| GPIO3 | LR2021 RESET | Existing |
| GPIO4 | LR2021 BUSY | Existing |
| GPIO5 | LR2021 DIO9 (IRQ) | Existing |
| GPIO6 | SPI SCLK (LR2021) | Existing |
| GPIO7 | SPI MOSI (LR2021) | Existing |
| GPIO8 | RP2040 BOOTSEL/GP0 (direct wire) | Active LOW during reset = bootloader |
| GPIO9 | BOOT button (ESP32) | Strapping — do NOT repurpose |
| GPIO10 | SPI CS (LR2021 NSS) | Existing |
| GPIO20 | I2C SDA (BMP280) | Existing |
| GPIO21 | I2C SCL (BMP280) | Existing |

### Alternative: RP2040 Solo (No ESP32 Needed)

If the RP2040 is the only MCU (no ESP32), auto-BOOTSEL can use:

1. **External watchdog IC** (e.g., TPS3823): resets RP2040 on heartbeat timeout.
   - Weight: 0.03g (SOT-23)
   - Cannot force BOOTSEL — only resets. Firmware must handle its own recovery.

2. **Self-watching via PIO**: A PIO state machine monitors the main core.
   If it stops toggling a heartbeat pin, the PIO asserts RUN + BOOTSEL.
   - Weight: 0g (software only)
   - Requires RP2040 to not be fully dead (PIO must still run)

3. **External flip-flop circuit**: RC timer + logic gate that triggers
   BOOTSEL+RUN after a timeout. Fully hardware, no firmware dependency.
   - Weight: ~0.1g (3 SMD components)
   - Most reliable, but fires even during normal sleep modes

### Recommendation

For the balloon flight board (ESP32-C3 + RP2040 dual-MCU):

**Use the ESP32 GPIO approach** (2 GPIOs + 3 wires, ~0g). It is:
- Zero additional components beyond wire/PCB traces
- Software-controlled (can trigger on specific conditions)
- Bidirectional (ESP32 can also read RP2040 status)
- Works from any altitude, no physical access needed
- **VERIFIED WORKING** (2026-07-13, commit e9102be)

### Implementation Checklist

- [x] Connect GPIO1 to RP2040 RESET button pad (direct wire)
- [x] Connect GPIO8 to RP2040 BOOTSEL button pad (direct wire)
- [x] Connect GND between ESP32 and RP2040
- [x] Write ESP32 firmware BOOTSEL trigger function
- [x] Test on dev boards — FULL PIPELINE VERIFIED
- [ ] Add watchdog: ESP32 monitors RP2040 heartbeat via UART
- [ ] Add recovery: on watchdog timeout, trigger BOOTSEL + flash
- [ ] Route direct traces on flight board PCB (no resistors)
- [ ] Document in ADR-012: Dual-MCU auto-BOOTSEL recovery

### Dev Board Testing (VERIFIED 2026-07-13)

The current dev boards (RP2040 Zero + ESP32-C3 SuperMini) have been tested:

1. ESP32 D1 (GPIO1) -> RP2040 RESET button pad (direct wire) — VERIFIED
2. ESP32 D8 (GPIO8) -> RP2040 BOOTSEL button pad (direct wire) — VERIFIED
3. GND -> GND (direct wire) — VERIFIED
4. ESP32 firmware flashes BOOTSEL sequence on boot — VERIFIED
5. RP2040 enters bootloader mode (PID 0003, RPI-RP2 drive mounts) — VERIFIED
6. UF2 firmware copied successfully — VERIFIED
7. RP2040 reboots with new firmware — VERIFIED

This eliminates ALL physical button presses for the entire development cycle.
