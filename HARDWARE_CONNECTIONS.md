# Hardware Connections: ESP32-C3 to RP2040

This document details the hardware connections needed between ESP32-C3 and RP2040 for the balloon board interface.

## Per Board Connections

| ESP32-C3 Pin | Via | RP2040 Pin | Pull-up |
|-------------|-----|------------|---------|
| GPIO1 (D1) | 1kΩ | RUN (pin 30) | 10kΩ to 3V3 |
| GPIO8 (D8) | 1kΩ | GP0/BOOTSEL (pin 1) | 10kΩ to 3V3 |
| GND | — | GND | — |

## Parts Needed Per Board

- 2× 1kΩ resistors  
- 2× 10kΩ resistors
- Hookup wire

## Connection Diagram

```
ESP32-C3                      RP2040
+-------+                    +-------+
|       |                    |       |
| GPIO1 +----[1kΩ]-----------+ RUN   | (pin 30)
|   D1  |                    |       |
+-------+                    +-------+
    |                           |
    |                           |
+-------+                    +-------+
|       |                    |       |
| GPIO8 +----[1kΩ]-----------+ GP0   | (pin 1)
|   D8  |                    |BOOTSEL|
+-------+                    +-------+
    |                           |
    |                           |
    |        +-------+           |
    +--------+ GND   +-----------+
             |       |           |
             +-------+           |
                 |               |
                 |           +-------+
                 +-----------+ 3V3   |
                             |       |
                             +-------+
                                |
                                |
                    +-----------+-----------+
                    |                       |
                [10kΩ]                 [10kΩ]
                    |                       |
                    +-----------+-----------+
                                |
                               GND

Detailed View:
─────────────────────────────────────────────────────────────────────

ESP32-C3 Side:
┌─────────────────┐
│ GPIO1 (D1)      ├─────[1kΩ resistor]─────┐
└─────────────────┘                         │
                                              │
┌─────────────────┐                         │
│ GPIO8 (D8)      ├─────[1kΩ resistor]─────┤
└─────────────────┘                         │
                                              │
┌─────────────────┐                         │
│ GND             ├─────────────────────────┘
└─────────────────┘

RP2040 Side:
┌─────────────────┐
│ RUN (pin 30)    ◄─────┐
└─────────────────┘      │
                         │
┌─────────────────┐      │
│ GP0 (pin 1)     ◄──────┤
│ BOOTSEL         │      │
└─────────────────┘      │
                         │
┌─────────────────┐      │
│ GND             ◄──────┘
└─────────────────┘

Pull-up Resistors:
┌─────────────────┐
│ 3V3             ◄─────┐
└─────────────────┘      │
                         │
                    [10kΩ resistor]◄─────┐
                         │              │
                    [10kΩ resistor]◄─────┤
                         │              │
┌─────────────────┐      │              │
│ GND             ◄──────┘              │
└─────────────────┘                     │
                                            │
┌─────────────────┐                        │
│ RUN (pin 30)    ◄────────────────────────┘
└─────────────────┘

┌─────────────────┐
│ GP0 (pin 1)     ◄────────────────────────┐
│ BOOTSEL         │                        │
└─────────────────┘                        │
                                            │
┌─────────────────┐                        │
│ GND             ◄────────────────────────┘
└─────────────────┘
```

## Explanation of Connections

### What Each Connection Does:

1. **GPIO1 (D1) to RUN (pin 30) via 1kΩ resistor**: 
   - This allows the ESP32-C3 to reset the RP2040 by pulling the RUN pin low
   - The 1kΩ resistor limits current and prevents damage

2. **GPIO8 (D8) to GP0/BOOTSEL (pin 1) via 1kΩ resistor**:
   - This allows the ESP32-C3 to put the RP2040 into bootloader mode
   - The 1kΩ resistor protects both pins

3. **Pull-up resistors (10kΩ to 3V3)**:
   - Both RUN and BOOTSEL pins need pull-up resistors to ensure they stay high (inactive) when not being driven low
   - Without pull-ups, these pins could float and cause unpredictable behavior

### Where to Place Components:

**For the 1kΩ resistors:**
- Place them in series between the ESP32-C3 GPIO pins and the RP2040 pins
- One resistor per connection line

**For the 10kΩ pull-up resistors:**
- Connect one end to 3V3 power
- Connect the other end to the RP2040 pin (RUN or BOOTSEL)
- These can be placed close to the RP2040 pins for best effect

**For the ground connection:**
- Connect any GND pin on ESP32-C3 to any GND pin on RP2040
- This provides a common ground reference

### Physical Layout Tips:

1. Keep wires as short as possible to reduce noise
2. Place the 10kΩ pull-up resistors close to the RP2040
3. Use color-coded wires if possible (e.g., red for 3V3, black for GND, different colors for signal lines)
4. Double-check all connections before powering on

## Testing the Connections

Before final assembly:
1. Use a multimeter to check for shorts between 3V3 and GND
2. Verify that pull-up resistors are properly connected (3V3 → 10kΩ → RP2040 pin)
3. Check continuity between ESP32-C3 and RP2040 pins through the 1kΩ resistors
4. Verify GND connection between both boards

## Safety Notes

- Always disconnect power before making or changing connections
- Double-check pinouts - wrong connections can damage the microcontrollers
- Start with testing before final assembly
- Use appropriate wire gauge for the current requirements