# GPS Module Soldering Guide — RP2040 Range Test Board

## Module

Most common 4-pin GPS modules (NEO-6M, ATGM336H, GT-U7) use the same pinout:

```
GPS Module → RP2040
─────────────────────────────
VCC  → 3V3 (pin 36, 3.3V)
GND  → GND (pin 3 or 8, any GND)
TX   → GP21 (UART1 RX, pin 27)
RX   → GP20 (UART1 TX, pin 26)
```

## Why GP20/GP21

- UART0 is used by USB CDC (Serial) — can't share
- UART1 = Serial2 on GP20 (TX) / GP21 (RX)
- GP20/GP21 are safe — not strapping pins, not used by radio SPI
- Radio uses GP2-GP8, USB uses GP0/GP1, UART1 debug on GP12/GP13

## Soldering Steps

1. Cut 4 short jumper wires (~5cm each)
2. Strip 2mm both ends, tin lightly
3. Solder VCC first (3V3) — prevents shorting if board slips
4. Solder GND second
5. Solder TX → GP21 (most important — this carries NMEA data TO the RP2040)
6. Solder RX → GP20 (only needed if configuring GPS module; NMEA works without it)
7. Check continuity with multimeter: each pin, no bridges
8. Check shorts: VCC to GND should be open

## Verification

After soldering, before flashing GPS firmware:

1. Flash regular autonomous TX firmware (no GPS)
2. Power board via USB
3. Check GP21 with logic analyzer or oscilloscope — should see 9600 baud NMEA sentences ($GPGGA, $GPRMC)
4. GPS LED should blink (most modules have onboard LED — 1Hz = searching, solid = fix acquired)

## Cold Start

- First fix: 30-60s outdoors, clear sky
- Indoor: may never acquire (weak signal through walls)
- Warm start (after first fix): 5-10s

## Antenna

Most modules have a small chip antenna or U.FL connector.
- Chip antenna: sufficient for outdoor testing
- For better performance: solder external active antenna to U.FL