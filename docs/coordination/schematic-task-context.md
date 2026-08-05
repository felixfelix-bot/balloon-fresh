Write SCHEMATIC-PLAN-3VARIANTS.md to ~/repos/balloon-fresh/docs/coordination/.

ALL GPIO data is provided below. Do NOT read firmware files. Just write the doc with complete netlists for all 3 variants, then commit and push.

## GPIO ASSIGNMENTS (from firmware — already extracted)

### ESP32-C3 Variant (current flight board)
Pin | Function | Net Name
0 | GPS UART TX (to GPS config) | GPS_TX
1 | GPS UART RX (NMEA from GPS) | GPS_RX
2 | LR2021 SPI MISO | SPI_MISO
3 | LR2021 RESET | LR2021_RST
4 | LR2021 BUSY | LR2021_BUSY
5 | LR2021 DIO9 (IRQ) | LR2021_DIO9
6 | LR2021 SPI SCK | SPI_SCK
7 | LR2021 SPI MOSI | SPI_MOSI
8 | I2C SDA (BMP280) | I2C_SDA
9 | I2C SCL (BMP280) + STATUS_LED | I2C_SCL
10 | LR2021 SPI NSS (CS) | SPI_NSS
ADC0 | VCAP voltage divider monitor | VDIV_MID

NOTE: GPIO9 does double duty (I2C SCL + LED). On C3 Mini, GPIO8 and GPIO9 are strapping pins. LED may need to move to GPIO19 or GPIO20 if I2C conflict.

### ESP32-S3 Variant (future custom board)
Same pin assignments work on S3 (it has the same GPIO numbers available). S3 also has GPIO18+ available for LED, more RAM, dual core.

### C3+RP2040 Variant
Same C3 pins as above PLUS:
RP2040 UART TX → C3 UART RX (GPIO1 is taken by GPS, so use GPIO19 or GPIO20)
RP2040 UART RX → C3 UART TX (same issue)
OR: RP2040 connects directly to LR2021 SPI bus (per ADR-026 — RP2040 is radio processor)

## POWER ARCHITECTURE (same for all variants)
Solar Panel (+) → BAT54 diode → Supercap VCAP (+) → TPS7A02 VIN
TPS7A02 VOUT → 3V3 rail
Supercap GND → GND
Voltage divider: VCAP → R1(1M) → VDIV_MID → R2(1M) → GND → ADC0
Decoupling: 100nF + 10uF on each IC VCC pin

## COMPONENT LIST (all variants)
Ref | Part | Footprint | Qty
U1 | ESP32-C3 Mini-1 / ESP32-S3-WROOM-1 | module | 1
U2 | NiceRF LoRa2021 | SMD-18 | 1
U3 | TPS7A02 regulator | SOT-23-5 | 1
U4 | MAX-M10S GPS | 4-pin header | 1
U5 | RP2040-Zero (variant 3 only) | 13-pin header | 1
SC | 1F 5.5V supercap | radial | 1
D1 | BAT54 diode | SOD-123 | 1
D2 | LED 0603 | 0603 | 1
J1 | Solar input | 2-pin header | 1
C1-C6 | 100nF decoupling | 0402 | 6
C7 | 10uF bulk | 0805 | 1
R1,R2 | 4.7k I2C pullup | 0402 | 2
R3,R4 | 1M voltage divider | 0402 | 2
R5 | 330R LED resistor | 0402 | 1

## NETLIST FORMAT
For each variant, list EVERY net with format:
NET_NAME: Component1.Pin1 ↔ Component2.Pin2

Example:
3V3: U1.VCC ↔ C1.1 ↔ C2.1 ↔ U3.VOUT
GND: U1.GND ↔ C1.2 ↔ C2.2 ↔ U3.GND ↔ SC.-

## OUTPUT FILE
~/repos/balloon-fresh/docs/coordination/SCHEMATIC-PLAN-3VARIANTS.md

## AFTER WRITING
git add docs/coordination/SCHEMATIC-PLAN-3VARIANTS.md
git commit -m "docs: schematic plan for 3 board variants (C3, S3, C3+RP2040)"
git push github autonomous/mesh-baseline