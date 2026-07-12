# Hardware Connections: ESP32-C3 to RP2040

> **VERIFIED WORKING (2026-07-13)** — Direct wire, NO resistors.

## Per Board Connections

| ESP32-C3 Pin | Via | RP2040 Button Pad | External Resistors |
|-------------|-----|-------------------|-------------------|
| GPIO1 (D1) | DIRECT WIRE | RESET button (3V3 side) | NONE |
| GPIO8 (D8) | DIRECT WIRE | BOOTSEL button (3V3 side) | NONE |
| GND | DIRECT WIRE | GND | NONE |

## Parts Needed Per Board

- 3x hookup wire (for D1, D8, GND)
- NO resistors of any kind

## Why No Resistors

The RP2040 button pads have internal pull-up resistors to 3V3. Previous designs
used 1kOhm series resistors, which created a voltage divider:
3.3V x (1kOhm / (1kOhm_pullup + 1kOhm_series)) = 1.65V — not low enough for
the RP2040 to register logic LOW (needs < 0.8V). Direct wire lets the ESP32
output driver sink straight to the pad, overpowering the internal pull-up and
pulling it to true 0V.

## Connection Diagram

```
ESP32-C3                      RP2040
+-------+                    +-------------------+
|       |                    |                   |
| GPIO1 +--------------------+ RESET button pad  | (3V3 signal side)
|  (D1) |   direct wire      |                   |
+-------+                    +-------------------+
    |
    |
+-------+                    +-------------------+
|       |                    |                   |
| GPIO8 +--------------------+ BOOTSEL button pad| (3V3 signal side)
|  (D8) |   direct wire      |                   |
+-------+                    +-------------------+
    |
    |
+-------+                    +-------------------+
|       |                    |                   |
| GND   +--------------------+ GND               |
|       |   direct wire      |                   |
+-------+                    +-------------------+
```

## CRITICAL: Which Button Pad to Solder

Each button on the RP2040 has TWO pads. You MUST solder to the correct one.

### How to Identify the Signal Pad (Multimeter Test)

1. Keep RP2040 powered (USB plugged in)
2. Multimeter: DC volts mode
3. Black probe -> RP2040 GND
4. Red probe -> touch one pad of the button, note reading
5. Move red probe -> touch the other pad, note reading

Results:
- ~3.3V = Signal side (CORRECT — solder ESP32 wire here)
- ~0.0V = GND side (WRONG — driving LOW does nothing)

Verify: Press the button while measuring the 3.3V pad — voltage should
drop to 0V. This confirms you're on the signal side.

### What Goes Wrong If You Pick the Wrong Pad

- Wire on GND side -> ESP32 driving LOW has NO effect (already at GND)
- The wire appears connected (continuity beeps) but is functionally dead
- You will spend hours debugging with zero response from the RP2040

## Soldering Instructions

### Step 1: Prepare Wires
Cut 3 pieces of hookup wire, ~10cm each. Strip ~3mm from each end.

### Step 2: Identify Pads
Use the multimeter test above to find the 3V3 signal side of BOTH buttons:
- RESET button signal pad (reads ~3.3V)
- BOOTSEL button signal pad (reads ~3.3V)

### Step 3: Solder D1 Wire
1. Tin the RESET button signal pad with a small amount of solder
2. Tin one end of a wire
3. Solder wire to the pad
4. Connect other end to ESP32 D1 pad

### Step 4: Solder D8 Wire
1. Tin the BOOTSEL button signal pad
2. Tin one end of a wire
3. Solder wire to the pad
4. Connect other end to ESP32 D8 pad

### Step 5: Solder GND Wire
1. Connect any GND pad on ESP32 to any GND pad on RP2040

### Step 6: Verify Connections
1. Multimeter continuity: beep from ESP32 D1 pad to RESET button signal pad
2. Multimeter continuity: beep from ESP32 D8 pad to BOOTSEL button signal pad
3. Multimeter continuity: beep from ESP32 GND to RP2040 GND
4. Power on: verify RP2040 boots normally (LED blink, serial output)

## Testing the Connections

1. Flash ESP32 with BOOTSEL controller firmware
2. ESP32 auto-triggers BOOTSEL sequence on boot (3s delay)
3. Check: RP2040 should appear as RPI-RP2 drive (PID 0003)
4. Copy UF2 firmware to RPI-RP2 drive
5. RP2040 should reboot with new firmware

## Safety Notes

- Always disconnect power before soldering
- Double-check which button pad is the signal side (3V3) vs GND side
- No series resistors needed — ESP32 drives one direction only
- No external pull-up resistors needed — RP2040 has internal pull-ups
- Keep wires as short as possible to reduce noise
- Use color-coded wires if possible (e.g., red for 3V3, black for GND)
