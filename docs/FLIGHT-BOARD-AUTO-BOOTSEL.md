# Auto-BOOTSEL Recovery: ESP32-C3 → RP2040 Flight Board Design

## Problem
The RP2040's USB CDC interface dies when firmware uses tight SPI loops without
calling `yield()`. Once USB CDC is dead, the only recovery is pressing the
physical BOOTSEL button — impossible during a balloon flight at 10km altitude.

## Solution: ESP32 GPIO-Controlled BOOTSEL

The RP2040 has two critical pins for boot mode selection:

| Pin | RP2040 Pin | Pico Label | Function |
|-----|-----------|------------|----------|
| RUN | Pin 30 | TP6 / RUN | Active-low global reset. Pulling LOW for ≥1µs resets the chip. |
| BOOTSEL | GP0 (Pin 12) | BOOTSEL button | Sampled at boot. LOW during reset → USB bootloader mode. |

### Circuit Design

```
ESP32-C3                    RP2040
─────────                   ───────
GPIO1 ──────[1kΩ]────────── RUN (pin 30)
                             │
                         [10kΩ pull-up to 3V3]
                             │
                            GND (when GPIO1 drives LOW)

GPIO8 ──────[1kΩ]────────── GP0 / BOOTSEL (pin 12)
                             │
                         [10kΩ pull-up to 3V3]
                             │
                            GND (when GPIO8 drives LOW)
```

**Components:**
- 2× 1kΩ series resistor (0402 SMD) — protects against drive contention
- 2× 10kΩ pull-up resistor (0402 SMD) — ensures pins float HIGH when ESP32 is in reset
- 4 PCB traces — zero weight (copper on existing board)

**Total weight added:** <0.01g (4× 0402 resistors ≈ 0.002g each)

### Per Board Connections (Legacy Design)

> **⚠️ Pin Conflict Warning**: This design uses GPIO1 for RUN, but GPIO1 is also UART RX.  
> See **BALLOON-FLIGHT-TEST-GUIDE.md** for the updated design using GPIO3 for RUN.

| ESP32-C3 Pin | Via | RP2040 Pin | Pull-up |
|-------------|-----|------------|---------|
| GPIO1 (D1) | 1kΩ | RUN (pin 30) | 10kΩ to 3V3 |
| GPIO8 (D8) | 1kΩ | GP0/BOOTSEL (pin 1) | 10kΩ to 3V3 |
| GND | — | GND | — |

**Parts Needed Per Board:**
- 2× 1kΩ resistors  
- 2× 10kΩ resistors
- Hookup wire

**Priority Order:**
1. RX Board (8332) - This enables automated throughput testing
2. TX Board (F242D) - Optional for now (tx_fast is stable enough)

### BOOTSEL Trigger Sequence (ESP32 Firmware)

```cpp
// Auto-BOOTSEL recovery: ESP32-C3 forces RP2040 into USB bootloader mode
// No physical button needed — works from software at any altitude.

#define RP2040_RUN_PIN    1   // ESP32 GPIO1 → RP2040 RUN
#define RP2040_BOOTSEL_PIN 8  // ESP32 GPIO8 → RP2040 GP0/BOOTSEL

void force_rp2040_bootsel() {
    // 1. Pull BOOTSEL LOW (GP0 low during boot = bootloader mode)
    pinMode(RP2040_BOOTSEL_PIN, OUTPUT);
    digitalWrite(RP2040_BOOTSEL_PIN, LOW);

    // 2. Pulse RUN LOW (reset the RP2040 while BOOTSEL is held low)
    pinMode(RP2040_RUN_PIN, OUTPUT);
    digitalWrite(RP2040_RUN_PIN, LOW);
    delayMicroseconds(50);     // Hold reset for 50µs (min 1µs, 50µs is safe)

    // 3. Release RUN — RP2040 boots, sees BOOTSEL=LOW, enters USB bootloader
    digitalWrite(RP2040_RUN_PIN, HIGH);
    pinMode(RP2040_RUN_PIN, INPUT);   // Float (pull-up takes over)

    // 4. Wait for boot to sample BOOTSEL pin
    delay(100);                 // RP2040 samples BOOTSEL within ~10ms

    // 5. Release BOOTSEL — RP2040 is now in bootloader mode
    digitalWrite(RP2040_BOOTSEL_PIN, HIGH);
    pinMode(RP2040_BOOTSEL_PIN, INPUT);  // Float (pull-up takes over)

    // RP2040 now appears as RPI-RP2 mass storage device on USB
    // Host can flash new firmware via UF2 file copy
}
```

### When to Trigger Auto-BOOTSEL

1. **Watchdog timeout**: ESP32 monitors RP2040 heartbeat. If no heartbeat
   for 30 seconds → force BOOTSEL + reflash.

2. **Remote command**: Ground station sends "reflash RP2040" via LoRa →
   ESP32 triggers BOOTSEL → new firmware uploaded via USB or OTA.

3. **Boot-time verification**: On power-up, ESP32 pings RP2040. If no
   response → BOOTSEL + flash known-good firmware from SPI flash.

### Integration into Flight Board

The flight board has a dual-MCU architecture:

```
┌─────────────────────────────────────────────────┐
│                 FLIGHT BOARD                     │
│                                                  │
│  ┌───────────┐         ┌───────────────────┐    │
│  │ ESP32-C3  │ GPIO1──│ RP2040 RUN         │    │
│  │           │ GPIO8──│ RP2040 BOOTSEL/GP0 │    │
│  │ Primary   │ SPI────│ LR2021 (shared)    │    │
│  │ MCU       │ I2C────│ BMP280             │    │
│  └─────┬─────┘        └───────────────────┘    │
│        │                                         │
│   USB-C│←── shared USB bus for flashing both ── │
│        │                                         │
│  ┌─────┴─────┐                                  │
│  │  Solar →  │                                  │
│  │  Caps →   │                                  │
│  │  LDO 3V3  │                                  │
│  └───────────┘                                  │
└─────────────────────────────────────────────────┘
```

### ESP32-C3 Pin Budget (Updated)

| GPIO | Function | Notes |
|------|----------|-------|
| GPIO0 | ADC (Supercap voltage) | Also UART TX to RP2040 GP21 |
| GPIO1 | UART RX (config 2) **or** RP2040 RUN (config 1) | See note below |
| GPIO2 | SPI MISO (LR2021) | Existing |
| GPIO3 | LR2021 RESET | Existing |
| GPIO4 | LR2021 BUSY | Existing |
| GPIO5 | LR2021 DIO9 (IRQ) | Existing |
| GPIO6 | SPI SCLK (LR2021) | Existing |
| GPIO7 | SPI MOSI (LR2021) | Existing |
| GPIO8 | **RP2040 BOOTSEL/GP0** | **Boot mode + RX/TX mode select** |
| GPIO9 | BOOT button (ESP32) | Strapping — do NOT repurpose |
| GPIO10 | SPI CS (LR2021 NSS) | Existing |
| GPIO20 | I2C SDA (BMP280) | Existing |
| GPIO21 | I2C SCL (BMP280) | Existing |

**Available GPIOs after this allocation:** None on ESP32-C3 (all 22 pins used).
If more GPIOs are needed, use an I2C GPIO expander (PCF8574, +0.1g).

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

**Use the ESP32 GPIO approach** (2 GPIOs + 4 resistors, <0.01g). It is:
- Zero additional components beyond traces and 0402 resistors
- Software-controlled (can trigger on specific conditions)
- Bidirectional (ESP32 can also read RP2040 status)
- Works from any altitude, no physical access needed
- Tested concept (standard for remote MCU programming)

### Implementation Checklist

- [ ] Add GPIO1 and GPIO8 connections to hub board schematic
- [ ] Add 1kΩ series resistors on both lines
- [ ] Add 10kΩ pull-ups on RP2040 side
- [ ] Route to RP2040 RUN (pin 30) and GP0 (pin 12)
- [ ] Write ESP32 firmware `force_rp2040_bootsel()` function
- [ ] Add watchdog: ESP32 monitors RP2040 heartbeat via UART or GPIO
- [ ] Add recovery: on watchdog timeout, trigger BOOTSEL + flash
- [ ] Test on dev boards before flight board fabrication
- [ ] Document in ADR-012: Dual-MCU auto-BOOTSEL recovery

### Dev Board Testing (Current Setup)

The current dev boards (Pico + ESP32-C3 Mini) can test this immediately:

1. Connect ESP32 GPIO1 → Pico RUN (TP6 test point)
2. Connect ESP32 GPIO8 → Pico GP0 (pin 12 / BOOTSEL pad)
3. Add 10kΩ pull-ups on both
4. Flash ESP32 with the trigger function
5. Verify: ESP32 can force Pico into BOOTSEL from software

This eliminates ALL physical button presses for the entire development cycle.
