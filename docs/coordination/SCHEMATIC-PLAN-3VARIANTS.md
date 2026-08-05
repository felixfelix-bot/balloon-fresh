# SCHEMATIC-PLAN-3VARIANTS.md
## Balloon Board Schematic Netlists — C3, S3, C3+RP2040

Generated: 2026-08-05
Source: docs/coordination/schematic-task-context.md (pre-extracted GPIO data)

---

## VARIANT 1: ESP32-C3 Flight Board (Current)

### Microcontroller
- **U1**: ESP32-C3 Mini-1 module

### Radio
- **U2**: NiceRF LoRa2021 (SMD-18)

### Power Supply
- **U3**: TPS7A02 regulator (SOT-23-5)
- **SC**: 1F 5.5V supercap (radial)
- **D1**: BAT54 diode (SOD-123)

### GPS
- **U4**: MAX-M10S GPS (4-pin header)

### Sensors
- **BMP280** on I2C bus

### Passives
- **C1-C6**: 100nF decoupling (0402)
- **C7**: 10uF bulk (0805)
- **R1, R2**: 4.7k I2C pullups (0402)
- **R3, R4**: 1M voltage divider (0402)
- **R5**: 330R LED resistor (0402)
- **D2**: LED 0603
- **J1**: Solar input (2-pin header)

---

### NETLIST: ESP32-C3 Variant

#### Power Nets
```
VBAT: J1.1 ↔ D1.A ↔ SC.+ ↔ U3.VIN
3V3: U3.VOUT ↔ U1.VCC ↔ U2.VCC ↔ U4.VCC ↔ C1.1 ↔ C2.1 ↔ C3.1 ↔ C4.1 ↔ C5.1 ↔ C6.1 ↔ C7.1
GND: J1.2 ↔ SC.- ↔ U3.GND ↔ U1.GND ↔ U2.GND ↔ U4.GND ↔ C1.2 ↔ C2.2 ↔ C3.2 ↔ C4.2 ↔ C5.2 ↔ C6.2 ↔ C7.2 ↔ R2.2 ↔ R4.2
VDIV_MID: SC.+ ↔ R3.1 ↔ R4.1 ↔ U1.ADC0
```

#### GPS UART
```
GPS_TX: U1.GPIO0 ↔ U4.RX
GPS_RX: U1.GPIO1 ↔ U4.TX
```

#### LR2021 SPI Bus
```
SPI_MISO: U1.GPIO2 ↔ U2.MISO
SPI_SCK:  U1.GPIO6 ↔ U2.SCK
SPI_MOSI: U1.GPIO7 ↔ U2.MOSI
SPI_NSS:  U1.GPIO10 ↔ U2.NSS
```

#### LR2021 Control
```
LR2021_RST:  U1.GPIO3 ↔ U2.RESET
LR2021_BUSY: U1.GPIO4 ↔ U2.BUSY
LR2021_DIO9: U1.GPIO5 ↔ U2.DIO9
```

#### I2C Bus (BMP280)
```
I2C_SDA: U1.GPIO8 ↔ U4.SDA ↔ R1.1
I2C_SCL: U1.GPIO9 ↔ U4.SCL ↔ R2.1
```

#### Status LED
```
LED: U1.GPIO9 ↔ R5.1 ↔ D2.A
LED_GND: D2.K ↔ GND
```

#### Decoupling
```
C1: U1.VCC ↔ U1.GND   (100nF, near U1)
C2: U2.VCC ↔ U2.GND   (100nF, near U2)
C3: U4.VCC ↔ U4.GND   (100nF, near U4)
C4: U3.VIN ↔ U3.GND   (100nF, near U3 input)
C5: U3.VOUT ↔ U3.GND  (100nF, near U3 output)
C6: BMP280.VCC ↔ BMP280.GND (100nF, near BMP280)
C7: U3.VOUT ↔ U3.GND  (10uF bulk, near U3 output)
```

#### Pullups
```
R1: 3V3 ↔ I2C_SDA (4.7k pullup)
R2: 3V3 ↔ I2C_SCL (4.7k pullup)
```

#### Voltage Divider
```
R3: VCAP ↔ VDIV_MID (1M upper)
R4: VDIV_MID ↔ GND (1M lower)
```

---

### NOTES for C3 Variant
- GPIO9 does double duty: I2C SCL + STATUS_LED. On C3 Mini, GPIO8 and GPIO9 are strapping pins. If I2C conflict occurs, move LED to GPIO19 or GPIO20.
- All power pins require 100nF + 10uF decoupling per IC.

---

## VARIANT 2: ESP32-S3 Future Board

### Microcontroller
- **U1**: ESP32-S3-WROOM-1 module

### Differences from C3 Variant
- Same pin assignments work on S3 (same GPIO numbers available).
- S3 has GPIO18+ available for dedicated LED (no strapping pin conflict).
- More RAM, dual core.

### NETLIST: ESP32-S3 Variant

#### Power Nets (identical to C3)
```
VBAT: J1.1 ↔ D1.A ↔ SC.+ ↔ U3.VIN
3V3: U3.VOUT ↔ U1.VCC ↔ U2.VCC ↔ U4.VCC ↔ C1.1 ↔ C2.1 ↔ C3.1 ↔ C4.1 ↔ C5.1 ↔ C6.1 ↔ C7.1
GND: J1.2 ↔ SC.- ↔ U3.GND ↔ U1.GND ↔ U2.GND ↔ U4.GND ↔ C1.2 ↔ C2.2 ↔ C3.2 ↔ C4.2 ↔ C5.2 ↔ C6.2 ↔ C7.2 ↔ R2.2 ↔ R4.2
VDIV_MID: SC.+ ↔ R3.1 ↔ R4.1 ↔ U1.ADC0
```

#### GPS UART
```
GPS_TX: U1.GPIO0 ↔ U4.RX
GPS_RX: U1.GPIO1 ↔ U4.TX
```

#### LR2021 SPI Bus
```
SPI_MISO: U1.GPIO2 ↔ U2.MISO
SPI_SCK:  U1.GPIO6 ↔ U2.SCK
SPI_MOSI: U1.GPIO7 ↔ U2.MOSI
SPI_NSS:  U1.GPIO10 ↔ U2.NSS
```

#### LR2021 Control
```
LR2021_RST:  U1.GPIO3 ↔ U2.RESET
LR2021_BUSY: U1.GPIO4 ↔ U2.BUSY
LR2021_DIO9: U1.GPIO5 ↔ U2.DIO9
```

#### I2C Bus (BMP280)
```
I2C_SDA: U1.GPIO8 ↔ U4.SDA ↔ R1.1
I2C_SCL: U1.GPIO9 ↔ U4.SCL ↔ R2.1
```

#### Status LED (dedicated pin on S3)
```
LED: U1.GPIO18 ↔ R5.1 ↔ D2.A
LED_GND: D2.K ↔ GND
```

#### Decoupling
```
C1: U1.VCC ↔ U1.GND   (100nF, near U1)
C2: U2.VCC ↔ U2.GND   (100nF, near U2)
C3: U4.VCC ↔ U4.GND   (100nF, near U4)
C4: U3.VIN ↔ U3.GND   (100nF, near U3 input)
C5: U3.VOUT ↔ U3.GND  (100nF, near U3 output)
C6: BMP280.VCC ↔ BMP280.GND (100nF, near BMP280)
C7: U3.VOUT ↔ U3.GND  (10uF bulk, near U3 output)
```

#### Pullups
```
R1: 3V3 ↔ I2C_SDA (4.7k pullup)
R2: 3V3 ↔ I2C_SCL (4.7k pullup)
```

#### Voltage Divider
```
R3: VCAP ↔ VDIV_MID (1M upper)
R4: VDIV_MID ↔ GND (1M lower)
```

---

### NOTES for S3 Variant
- LED moved to GPIO18 to avoid strapping pin conflict on GPIO9.
- Otherwise pin-compatible with C3 assignments.

---

## VARIANT 3: C3 + RP2040 Dual-MCU Board

### Microcontrollers
- **U1**: ESP32-C3 Mini-1 module (main processor / WiFi-BLE)
- **U5**: RP2040-Zero (radio co-processor, per ADR-026)

### RP2040 Connection Options

Per ADR-026, the RP2040 is the radio processor. Two connection options exist:

**Option A: UART bridge between C3 and RP2040**
- RP2040 UART TX → C3 UART RX (GPIO1 is taken by GPS, so use GPIO19 or GPIO20)
- RP2040 UART RX → C3 UART TX

**Option B: RP2040 directly on LR2021 SPI bus**
- RP2040 connects directly to LR2021 SPI bus as SPI master
- C3 communicates with RP2040 via UART or IPC

### NETLIST: C3+RP2040 Variant (Option A — UART Bridge)

#### Power Nets
```
VBAT: J1.1 ↔ D1.A ↔ SC.+ ↔ U3.VIN
3V3: U3.VOUT ↔ U1.VCC ↔ U2.VCC ↔ U4.VCC ↔ U5.VCC ↔ C1.1 ↔ C2.1 ↔ C3.1 ↔ C4.1 ↔ C5.1 ↔ C6.1 ↔ C7.1
GND: J1.2 ↔ SC.- ↔ U3.GND ↔ U1.GND ↔ U2.GND ↔ U4.GND ↔ U5.GND ↔ C1.2 ↔ C2.2 ↔ C3.2 ↔ C4.2 ↔ C5.2 ↔ C6.2 ↔ C7.2 ↔ R2.2 ↔ R4.2
VDIV_MID: SC.+ ↔ R3.1 ↔ R4.1 ↔ U1.ADC0
```

#### GPS UART
```
GPS_TX: U1.GPIO0 ↔ U4.RX
GPS_RX: U1.GPIO1 ↔ U4.TX
```

#### LR2021 SPI Bus
```
SPI_MISO: U1.GPIO2 ↔ U2.MISO
SPI_SCK:  U1.GPIO6 ↔ U2.SCK
SPI_MOSI: U1.GPIO7 ↔ U2.MOSI
SPI_NSS:  U1.GPIO10 ↔ U2.NSS
```

#### LR2021 Control
```
LR2021_RST:  U1.GPIO3 ↔ U2.RESET
LR2021_BUSY: U1.GPIO4 ↔ U2.BUSY
LR2021_DIO9: U1.GPIO5 ↔ U2.DIO9
```

#### I2C Bus (BMP280)
```
I2C_SDA: U1.GPIO8 ↔ U4.SDA ↔ R1.1
I2C_SCL: U1.GPIO9 ↔ U4.SCL ↔ R2.1
```

#### Status LED
```
LED: U1.GPIO9 ↔ R5.1 ↔ D2.A
LED_GND: D2.K ↔ GND
```

#### RP2040 UART Bridge (Option A)
```
RP_TX: U5.GPIO0 (UART0 TX) ↔ U1.GPIO19 (UART RX)
RP_RX: U5.GPIO1 (UART0 RX) ↔ U1.GPIO20 (UART TX)
```

#### Decoupling (add U5)
```
C1: U1.VCC ↔ U1.GND   (100nF, near U1)
C2: U2.VCC ↔ U2.GND   (100nF, near U2)
C3: U4.VCC ↔ U4.GND   (100nF, near U4)
C4: U3.VIN ↔ U3.GND   (100nF, near U3 input)
C5: U3.VOUT ↔ U3.GND  (100nF, near U3 output)
C6: BMP280.VCC ↔ BMP280.GND (100nF, near BMP280)
C7: U3.VOUT ↔ U3.GND  (10uF bulk, near U3 output)
C8: U5.VCC ↔ U5.GND   (100nF, near U5 — RP2040-Zero has onboard caps but add for margin)
```

#### Pullups
```
R1: 3V3 ↔ I2C_SDA (4.7k pullup)
R2: 3V3 ↔ I2C_SCL (4.7k pullup)
```

#### Voltage Divider
```
R3: VCAP ↔ VDIV_MID (1M upper)
R4: VDIV_MID ↔ GND (1M lower)
```

---

### NOTES for C3+RP2040 Variant
- **Option A (UART bridge)**: C3 remains SPI master for LR2021; RP2040 handles radio protocol stack and communicates with C3 over UART. Uses GPIO19 (RX) and GPIO20 (TX) on C3 since GPIO1 is occupied by GPS.
- **Option B (RP2040 as SPI master)**: RP2040 connects directly to LR2021 SPI bus. C3 communicates with RP2040 via UART or other IPC. This option per ADR-026 makes RP2040 the radio processor.
- RP2040-Zero requires 3V3 power and GND. It has onboard USB and crystal.

---

## POWER ARCHITECTURE (All Variants)

```
Solar Panel (+) → J1.1 → D1 (BAT54) → SC.+ (1F 5.5V supercap)
                                    ↓
                              U3 (TPS7A02) VIN
                                    ↓
                              U3 VOUT → 3V3 rail
                                    ↓
         U1.VCC ← C1/C7 ← U2.VCC ← C2 ← U4.VCC ← C3 ← [U5.VCC ← C8]
                                    ↓
                              GND rail ← all GND pins

Voltage divider:
SC.+ → R3 (1M) → VDIV_MID → U1.ADC0
         ↓
      R4 (1M) → GND
```

## COMPONENT FOOTPRINT SUMMARY

| Ref | Part | Footprint | Qty | Variants |
|-----|------|-----------|-----|----------|
| U1 | ESP32-C3 Mini-1 / ESP32-S3-WROOM-1 | module | 1 | All |
| U2 | NiceRF LoRa2021 | SMD-18 | 1 | All |
| U3 | TPS7A02 regulator | SOT-23-5 | 1 | All |
| U4 | MAX-M10S GPS | 4-pin header | 1 | All |
| U5 | RP2040-Zero | 13-pin header | 1 | V3 only |
| SC | 1F 5.5V supercap | radial | 1 | All |
| D1 | BAT54 diode | SOD-123 | 1 | All |
| D2 | LED 0603 | 0603 | 1 | All |
| J1 | Solar input | 2-pin header | 1 | All |
| C1-C6 | 100nF decoupling | 0402 | 6 | All (V3 adds C8) |
| C7 | 10uF bulk | 0805 | 1 | All |
| R1,R2 | 4.7k I2C pullup | 0402 | 2 | All |
| R3,R4 | 1M voltage divider | 0402 | 2 | All |
| R5 | 330R LED resistor | 0402 | 1 | All |

---

*End of SCHEMATIC-PLAN-3VARIANTS.md*
