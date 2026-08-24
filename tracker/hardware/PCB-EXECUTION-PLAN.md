# PCB EXECUTION PLAN — Three-Variant Design (ADR-028)

**Date:** 2026-08-05
**Author:** worker-layout (kimi-k3)
**Task:** t_baf051a8 — PCB-EXEC-PLAN
**Status:** ACTIVE — execution plan for orchestrator conversion to kanban tasks

---

## 1. VARIANT SUMMARY

| Variant | MCU | Purpose | Status | Footprint |
|---------|-----|---------|--------|-----------|
| Balloon-C3 | ESP32-C3-MINI-1 | Immediate testing, breadboard replacement | **PRIORITY 1** | Bare module (not Super Mini) |
| Balloon-S3 | ESP32-S3-MINI-1 | Future production, more GPIO/RAM/PSRAM | **PRIORITY 2** | Bare module |
| Balloon-Dual | ESP32-C3 + RP2040 | Advanced radio architecture (ADR-026) | **PRIORITY 3** | Dual module |

**Shared Peripherals (ALL variants):**
- LR2021F33 dual-band LoRa/FLRC radio (SPI)
- MAX-M10S GPS (UART)
- TPS7A02 LDO + supercap + solar power chain
- 2x U.FL antenna connectors (sub-GHz + 2.4GHz)
- Optional FEM (SKY66112)
- ADC voltage divider for supercap monitoring (GPIO0 on C3, GPIO1 on S3)
- Optional BMP280 (I2C)

**Key Design Constraint:** The ESP32-C3 Super Mini footprint has a GPIO5/GPIO6 pad collision bug. All variants use **bare ESP32-C3-MINI-1 / ESP32-S3-MINI-1 modules** with proper pad spacing (0.5mm pitch on module, routed to 1.27mm or 2.54mm headers on carrier board if needed).

---

## 2. SCHEMATIC DESIGN

### 2.1 Sheet Organization (Common to All Variants)

```
Balloon-XXX.kicad_sch
├── Sheet 1: Top / Power
│   ├── Power chain: SOLAR_IN → D1(BAT54) → VCAP → C_CAP → C1 → U4(TPS7A02) → C2 → 3V3
│   ├── Voltage divider: R_DIV1(100k) → R_DIV2(100k) → VDIV_MID
│   └── Power symbols: 3V3, VCAP, SOLAR_IN, GND
├── Sheet 2: MCU
│   ├── U1: MCU module (C3 or S3 or C3+RP2040)
│   ├── Decoupling: C3, C4 (100nF near VCC)
│   ├── Programming header: J1 (UART0 TX/RX, EN, BOOT, 3V3, GND)
│   ├── Status LED: LED1 + R_LED(330R)
│   └── Optional: BMP280 (I2C) — SDA/SCL pull-ups
├── Sheet 3: Radio (LR2021)
│   ├── U2: LR2021F33 module
│   ├── SPI bus: SCK, MOSI, MISO, NSS
│   ├── Control: BUSY, RST, DIO9
│   └── RF: RF_SUB_868, RF_2G4_2400
├── Sheet 4: GPS
│   ├── U3: MAX-M10S
│   └── UART: GPS_RX, GPS_TX (optional/disabled)
├── Sheet 5: Connectors / Antennas / FEM
│   ├── ANT1: U.FL (sub-GHz)
│   ├── ANT2: U.FL (2.4GHz)
│   ├── SOLAR: 2-pin connector
│   └── FEM: SKY66112 (optional)
└── Sheet 6: Inter-MCU (Dual variant only)
    ├── UART bridge: C3 GPIO18/19 ↔ RP2040 GPIO0/1
    └── Optional SPI bridge (future)
```

### 2.2 Component List — Balloon-C3 (20 components)

| Ref | Component | Part Number | KiCad Symbol | KiCad Footprint | Value | Notes |
|-----|-----------|-------------|--------------|-----------------|-------|-------|
| U1 | MCU | ESP32-C3-MINI-1 | `RF_Module:ESP32-C3-MINI-1` | `RF_Module:ESP32-C3-MINI-1` | - | Bare module, 53 pads |
| U2 | Radio | NiceRF LR2021F33 | Custom (18-pin) | `RF_Module:NiceRF_Lora1276-C1` (proxy) or custom | - | Dual-band LoRa/FLRC |
| U3 | GPS | u-blox MAX-M10S | `RF_GPS:ublox_MAX-M10S` | `RF_GPS:ublox_MAX-M10` | - | UART GPS |
| U4 | LDO | TPS7A0233PDBVR | `Regulator_Linear:TPS7A02` | `Package_TO_SOT_SMD:SOT-23-5` | 3.3V | Low-Iq |
| D1 | Diode | BAT54 | `Diode:BAT54` | `Diode_SMD:D_SOD-123` | - | Schottky, solar OR-ing |
| C_CAP | Supercap | TBD | `Device:CP1_Small` | `Capacitor_THT:CP_Radial_D10.0mm_P5.00mm` | 0.1F 5.5V | Flight power reservoir |
| SOLAR | Connector | 2-pin header | `Connector_Generic:Conn_01x02` | `Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical` | - | Solar input |
| LED1 | LED | Generic | `Device:LED` | `LED_SMD:LED_0603_1608Metric` | Red | Status |
| R_LED | Resistor | Generic | `Device:R` | `Resistor_SMD:R_0402_1005Metric` | 330R | LED current limit |
| R_PD | Resistor | Generic | `Device:R` | `Resistor_SMD:R_0402_1005Metric` | 10k | SPI MISO pull-down (strapping) |
| R_DIV1 | Resistor | Generic | `Device:R` | `Resistor_SMD:R_0402_1005Metric` | 100k | Voltage divider top |
| R_DIV2 | Resistor | Generic | `Device:R` | `Resistor_SMD:R_0402_1005Metric` | 100k | Voltage divider bottom |
| C1 | Capacitor | Generic | `Device:C` | `Capacitor_SMD:C_0603_1608Metric` | 10uF | LDO input |
| C2 | Capacitor | Generic | `Device:C` | `Capacitor_SMD:C_0603_1608Metric` | 10uF | LDO output |
| C3 | Capacitor | Generic | `Device:C` | `Capacitor_SMD:C_0402_1005Metric` | 100nF | MCU decoupling |
| C4 | Capacitor | Generic | `Device:C` | `Capacitor_SMD:C_0402_1005Metric` | 100nF | Radio decoupling |
| ANT1 | U.FL | Molex 73412-0110 | `Connector:U.FL` | `Connector_Coaxial:U.FL_Molex_MCRF_73412-0110` | - | Sub-GHz |
| ANT2 | U.FL | Molex 73412-0110 | `Connector:U.FL` | `Connector_Coaxial:U.FL_Molex_MCRF_73412-0110` | - | 2.4GHz |
| J1 | 6-pin header | Generic | `Connector_Generic:Conn_01x06` | `Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical` | - | Programming (UART0, EN, BOOT, 3V3, GND) |
| FEM | FEM (optional) | SKY66112-11 | Custom | `Package_DFN_QFN:QFN-16-1EP_3x3mm_P0.5mm` | - | PA+LNA, populate if needed |

### 2.3 Complete Net List — Balloon-C3 (24 nets)

| Net Name | Source Pin(s) | Destination Pin(s) | Type | Track Width |
|----------|---------------|-------------------|------|-------------|
| 3V3 | U4.4(OUT), C2.1 | U1.VCC, U2.1, U3.1, C3.1, C4.1, FEM.VCC, J1.VCC | POWER | plane (In2.Cu) |
| GND | U4.2, C2.2, C_CAP.2, C1.2, C3.2, C4.2, R_DIV2.2, R_PD.1, LED1.K | U1.GND, U2.2/8/10/11/16/17, U3.2, ANT1.GND, ANT2.GND, FEM.GND, J1.GND | GROUND | plane (In1.Cu) |
| VCAP | D1.K, C_CAP.1, C1.1, U4.1, U4.3 | R_DIV1.1 | POWER | 0.40mm |
| SOLAR_IN | SOLAR.1 | D1.A | POWER | 0.40mm |
| VDIV_MID | R_DIV1.2, R_DIV2.1 | U1.GPIO0 | SIGNAL (ADC) | 0.25mm |
| SPI_SCK | U1.GPIO6 | U2.5 | SIGNAL | 0.25mm |
| SPI_MOSI | U1.GPIO7 | U2.4 | SIGNAL | 0.25mm |
| SPI_MISO | U2.3, R_PD.2 | U1.GPIO2 | SIGNAL | 0.25mm |
| SPI_NSS | U1.GPIO10 | U2.6 | SIGNAL | 0.25mm |
| LR2021_BUSY | U2.7 | U1.GPIO4 | SIGNAL | 0.25mm |
| LR2021_RST | U1.GPIO3 | U2.14 | SIGNAL | 0.25mm |
| LR2021_DIO9 | U2.13 | U1.GPIO5 | SIGNAL (IRQ) | 0.25mm |
| GPS_RX | U3.3 | U1.GPIO1 | SIGNAL (UART) | 0.25mm |
| GPS_TX | U1.GPIO0 (if not ADC) or NC | U3.4 | SIGNAL (UART, optional) | 0.25mm |
| STATUS_LED | U1.GPIO9 | R_LED.1 | SIGNAL | 0.25mm |
| LED_ANODE | R_LED.2 | LED1.A | SIGNAL | 0.25mm |
| FEM_TX | U1.GPIO19 | FEM.TX_EN | SIGNAL (optional) | 0.25mm |
| FEM_RX | U1.GPIO0 (if not ADC) or NC | FEM.RX_EN | SIGNAL (optional) | 0.25mm |
| I2C_SDA | U1.GPIO20 | U5.SDA (optional) | SIGNAL | 0.25mm |
| I2C_SCL | U1.GPIO21 | U5.SCL (optional) | SIGNAL | 0.25mm |
| RF_SUB_868 | U2.9 | ANT1.1 | RF | 0.76mm (50Ω) |
| RF_2G4_2400 | U2.18 | ANT2.1 | RF | 0.76mm (50Ω) |
| UART_TX | U1.U0TXD | J1.TX | SIGNAL (programming) | 0.25mm |
| UART_RX | U1.U0RXD | J1.RX | SIGNAL (programming) | 0.25mm |
| EN | J1.EN | U1.EN | SIGNAL | 0.25mm |
| BOOT | J1.BOOT | U1.GPIO9 | SIGNAL (strapping) | 0.25mm |

### 2.4 Pin Assignments — Balloon-C3

| Function | GPIO | Module Pin | ADC | Strapping | Notes |
|----------|------|------------|-----|-----------|-------|
| ADC (supercap VDIV) | GPIO0 | 12 | ADC1_CH0 | no | Voltage divider midpoint |
| GPS UART RX | GPIO1 | 13 | ADC1_CH1 | no | NMEA from GPS |
| SPI MISO | GPIO2 | 5 | ADC1_CH2 | YES | 10kΩ pull-down required |
| LR2021 RST | GPIO3 | 6 | ADC1_CH3 | no | Active-low reset |
| LR2021 BUSY | GPIO4 | 18 | ADC1_CH4 | no | Radio busy indicator |
| LR2021 DIO9 | GPIO5 | 19 | ADC2_CH0 | no | IRQ pin |
| SPI SCK | GPIO6 | 20 | — | no | SPI clock |
| SPI MOSI | GPIO7 | 21 | — | no | SPI data out |
| (unused) | GPIO8 | 22 | NONE | YES | Strapping. Leave unconnected. |
| STATUS_LED | GPIO9 | 23 | — | YES (pull-up) | LED + 330R to GND |
| SPI NSS | GPIO10 | 16 | — | no | Chip select |
| (unused/USB) | GPIO18 | 26 | — | no | USB_D- — available if USB disabled |
| FEM_TX | GPIO19 | 27 | — | no | USB_D+ — available if USB disabled |
| UART RX (console) | GPIO20 | 30 | — | no | U0RXD |
| UART TX (console) | GPIO21 | 31 | — | no | U0TXD |

### 2.5 Pin Assignments — Balloon-S3 (Migration Mapping)

| Function | C3 GPIO | S3 GPIO | Notes |
|----------|---------|---------|-------|
| ADC (supercap) | GPIO0 | GPIO1 | S3 ADC1_CH0. GPIO0 is boot strapping on S3. |
| GPS UART RX | GPIO1 | GPIO4 | S3 has more UART-capable pins. |
| SPI MISO | GPIO2 | GPIO12 | S3 SPI2 MISO. |
| LR2021 RST | GPIO3 | GPIO13 | |
| LR2021 BUSY | GPIO4 | GPIO14 | |
| LR2021 DIO9 | GPIO5 | GPIO15 | |
| SPI SCK | GPIO6 | GPIO16 | S3 SPI2 SCK. |
| SPI MOSI | GPIO7 | GPIO17 | S3 SPI2 MOSI. |
| (unused) | GPIO8 | GPIO18 | USB_D- on S3 (native USB). |
| STATUS_LED | GPIO9 | GPIO8 | S3 has no strapping on GPIO8. |
| SPI NSS | GPIO10 | GPIO10 | |
| (unused) | GPIO18 | GPIO19 | USB_D+ on S3. |
| FEM_TX | GPIO19 | GPIO20 | |
| I2C_SDA | GPIO20 | GPIO21 | S3 I2C0 SDA. |
| I2C_SCL | GPIO21 | GPIO47 | S3 I2C0 SCL (or GPIO48). |

### 2.6 Pin Assignments — Balloon-Dual (C3 + RP2040)

**ESP32-C3 (Application MCU):**
- Same as Balloon-C3, EXCEPT:
  - GPIO18 → UART1_TX to RP2040 GPIO0 (RX)
  - GPIO19 → UART1_RX from RP2040 GPIO1 (TX)
  - FEM_TX moves to GPIO20 (shared with I2C_SDA, use jumper/select)

**RP2040 (Radio MCU):**
| Function | RP2040 GPIO | Notes |
|----------|-------------|-------|
| UART0 RX | GPIO0 | From C3 GPIO18 |
| UART0 TX | GPIO1 | To C3 GPIO19 |
| SPI0 SCK | GPIO2 | To LR2021 Pin5 |
| SPI0 MOSI | GPIO3 | To LR2021 Pin4 |
| SPI0 MISO | GPIO4 | To LR2021 Pin3 |
| SPI0 CS | GPIO5 | To LR2021 Pin6 |
| BUSY | GPIO6 | From LR2021 Pin7 |
| IRQ | GPIO7 | From LR2021 Pin13 |
| RST | GPIO8 | To LR2021 Pin14 |
| STATUS_LED | GPIO25 | On-board LED (RP2040-Zero style) |

### 2.7 ERC Rules to Enforce

**Pin Type Assignments:**
- Power output: U4.OUT(3V3), U4.EN(VCAP), U4.IN(VCAP)
- Power input: All VCC pins (U1, U2, U3, FEM, J1)
- Passive: All R, C pins
- Input: U1 GPIO1, GPIO2, GPIO4, GPIO5, GPIO18(Dual), GPIO19(Dual)
- Output: U1 GPIO3, GPIO6, GPIO7, GPIO9, GPIO10, GPIO19/20(FEM_TX), GPIO20/21(I2C on S3)
- Bidirectional: U1 GPIO0 (ADC + strapping on C3)
- NC: U2.12, U2.15, U3.4 (if GPS_TX disabled)

**ERC Checklist:**
- [ ] No unconnected pins (except explicitly NC)
- [ ] No power output shorted to power output
- [ ] No input shorted to input without driver
- [ ] All power inputs have decoupling caps within 5mm
- [ ] No conflicting drivers on same net
- [ ] Strapping pins have correct default states:
  - C3: GPIO2 pull-down 10k, GPIO8 floating, GPIO9 pull-up via LED+330R
  - S3: GPIO0, GPIO3, GPIO45, GPIO46 reviewed
- [ ] RF nets annotated with 50Ω impedance width (0.76mm)
- [ ] GPS TX output high-impedance or unpowered during C3 boot
- [ ] Voltage divider impedance (200k) well above strapping threshold
- [ ] RP2040 UART baud rate >= 2Mbps if Dual variant (per ADR-026)

### 2.8 Estimated Time per Variant (Schematic)

| Variant | Components | Nets | Sheets | Est. Time |
|---------|-----------|------|--------|-----------|
| Balloon-C3 | 20 | 24 | 5 | 120 min |
| Balloon-S3 | 20 | 24 | 5 | 90 min (reuse C3 sheets, remap pins) |
| Balloon-Dual | 24 | 28 | 6 | 150 min (add RP2040 + inter-MCU) |

---

## 3. BOARD LAYOUT

### 3.1 4-Layer Stackup (ALL variants)

```
Layer 1: F.Cu    — Signals, RF, power traces
Layer 2: In1.Cu  — GND plane (solid, >90% coverage)
Layer 3: In2.Cu  — 3V3 plane (solid, >90% coverage)
Layer 4: B.Cu    — Signals, ground fill (if needed)
```

**Design Rules:**
- Track width (signal): 0.25mm
- Track width (power): 0.40mm
- Track width (RF): 0.76mm (50Ω controlled impedance)
- Clearance: 0.30mm
- Via: 0.3mm drill / 0.6mm diameter
- Edge clearance: 0.50mm copper-to-board-edge

### 3.2 Board Dimensions

| Variant | Width x Height | Area | Notes |
|---------|---------------|------|-------|
| Balloon-C3 | 50mm x 40mm | 2000mm² | Compact, proven from full_pipeline.py |
| Balloon-S3 | 50mm x 40mm | 2000mm² | Same peripherals, same size |
| Balloon-Dual | 60mm x 45mm | 2700mm² | +10mm width for RP2040 module |

### 3.3 Component Placement Strategy

**Zone 1: Power Island (bottom-left, 15mm x 15mm)**
- SOLAR connector (edge)
- D1 (BAT54)
- C_CAP (supercap, THT)
- C1, C2 (LDO caps)
- U4 (TPS7A02)
- R_DIV1, R_DIV2 (voltage divider)

**Zone 2: MCU Cluster (center, 15mm x 15mm)**
- U1 (MCU module)
- C3, C4 (decoupling, within 3mm of VCC pins)
- LED1 + R_LED (status)
- J1 (programming header, board edge for access)
- R_PD (pull-down, under MCU corner)

**Zone 3: Radio Cluster (right side, 20mm x 20mm)**
- U2 (LR2021F33)
- ANT1, ANT2 (U.FL, board edge, 50Ω traces)
- FEM (optional, between U2 and ANT2)

**Zone 4: GPS (top-left, 10mm x 10mm)**
- U3 (MAX-M10S)

**Zone 5: Inter-MCU (Dual only, top-right, 15mm x 15mm)**
- RP2040 module
- UART bridge traces (short, direct)

### 3.4 FreeRouting Strategy

1. **Strip all tracks** from board (keep footprints, keep planes)
2. **Export DSN** via `pcbnew.ExportSpecctraDSN()`
3. **Run FreeRouting** with `-mp 20` (20 passes)
4. **Import SES** via `pcbnew.ImportSpecctraSES()` — NEVER manual DSN parsing
5. **Fill GND zone** via `ZONE_FILLER` on In1.Cu
6. **Fill 3V3 zone** via `ZONE_FILLER` on In2.Cu
7. **Route power nets** (VCAP, SOLAR_IN) as explicit traces on F.Cu (planes only for GND/3V3)

**Expected DRC Result:** 0 violations, 0 unconnected after FreeRouting + zone fill.

### 3.5 Expected DRC Results per Variant

| Variant | Signal Nets | Power Nets | RF Nets | Est. DRC |
|---------|-------------|------------|---------|----------|
| Balloon-C3 | 16 | 3 | 2 | 0/0 |
| Balloon-S3 | 16 | 3 | 2 | 0/0 |
| Balloon-Dual | 20 | 3 | 2 | 0/0 |

---

## 4. GERBER + JLCPCB

### 4.1 Gerber Export Checklist

- [ ] F.Cu (top copper)
- [ ] In1.Cu (GND plane)
- [ ] In2.Cu (3V3 plane)
- [ ] B.Cu (bottom copper)
- [ ] F.Mask (top solder mask)
- [ ] B.Mask (bottom solder mask)
- [ ] F.SilkS (top silkscreen)
- [ ] B.SilkS (bottom silkscreen)
- [ ] F.Paste (top paste, if SMD assembly)
- [ ] B.Paste (bottom paste, if SMD assembly)
- [ ] Edge.Cuts (board outline)
- [ ] Drill file (PTH + NPTH)
- [ ] Drill map (optional but recommended)
- [ ] Gerber job file (`.gbrjob`)

### 4.2 JLCPCB Order Specs

| Spec | Value |
|------|-------|
| Layers | 4 |
| Thickness | 1.6mm |
| Surface Finish | ENIG (gold, better for castellated modules) |
| Soldermask | Green |
| Silkscreen | White |
| Min. Track/Space | 0.1mm / 0.1mm (JLCPCB minimum) |
| Min. Hole | 0.2mm |
| Impedance Control | Not required (50Ω approximated by 0.76mm width on 1.6mm FR4) |
| Quantity | 5 boards per variant (JLCPCB minimum) |

### 4.3 What to Order

| Variant | Qty | Purpose |
|---------|-----|---------|
| Balloon-C3 | 5 | Immediate testing, 2 for bench, 1 for flight, 2 spare |
| Balloon-S3 | 5 | Future production validation |
| Balloon-Dual | 5 | Advanced architecture testing |

**Recommendation:** Order all 3 variants in **one batch** to save shipping ($8 vs $24 for 3 separate shipments).

---

## 5. WORKER ASSIGNMENTS

| Task ID | Task | Worker | Model | Est. Minutes | Dependencies |
|---------|------|--------|-------|--------------|--------------|
| T1 | Draw Balloon-C3 schematic + ERC | worker-layout | kimi-k3:cloud | 120 | This plan approved |
| T2 | Draw Balloon-S3 schematic + ERC | worker-layout | kimi-k3:cloud | 90 | T1 complete (reuse sheets) |
| T3 | Draw Balloon-Dual schematic + ERC | worker-layout | kimi-k3:cloud | 150 | T1 complete (reuse C3 + add RP2040) |
| T4 | Create Balloon-C3 4-layer board | worker-layout | kimi-k3:cloud | 60 | T1 complete |
| T5 | Create Balloon-S3 4-layer board | worker-layout | kimi-k3:cloud | 45 | T2 complete |
| T6 | Create Balloon-Dual 4-layer board | worker-layout | kimi-k3:cloud | 75 | T3 complete |
| T7 | Place components + FreeRoute C3 | worker-layout | kimi-k3:cloud | 45 | T4 complete |
| T8 | Place components + FreeRoute S3 | worker-layout | kimi-k3:cloud | 35 | T5 complete |
| T9 | Place components + FreeRoute Dual | worker-layout | kimi-k3:cloud | 55 | T6 complete |
| T10 | Fill zones + DRC + fix C3 | worker-layout | kimi-k3:cloud | 30 | T7 complete |
| T11 | Fill zones + DRC + fix S3 | worker-layout | kimi-k3:cloud | 25 | T8 complete |
| T12 | Fill zones + DRC + fix Dual | worker-layout | kimi-k3:cloud | 35 | T9 complete |
| T13 | Export gerbers + JLCPCB zip C3 | worker-layout | kimi-k3:cloud | 15 | T10 complete |
| T14 | Export gerbers + JLCPCB zip S3 | worker-layout | kimi-k3:cloud | 12 | T11 complete |
| T15 | Export gerbers + JLCPCB zip Dual | worker-layout | kimi-k3:cloud | 15 | T12 complete |
| T16 | Git commit + push all files | worker-layout | kimi-k3:cloud | 10 | T13,T14,T15 complete |
| T17 | Write test scripts (power, continuity) | worker-admin | glm-5.2:cloud | 45 | T10,T11,T12 complete |
| T18 | Update CI with DRC checks | worker-admin | glm-5.2:cloud | 30 | T16 complete |
| T19 | Documentation (assembly notes) | worker-admin | glm-5.2:cloud | 30 | T10,T11,T12 complete |

**TOTAL CRITICAL PATH:** T1 → T4 → T7 → T10 → T13 → T16 = **300 minutes** (5 hours)

**Parallel Opportunities:**
- T2, T3 can start after T1 (sheet reuse)
- T5, T6 can start after T2, T3
- T8, T9 can start after T5, T6
- T11, T12 can start after T8, T9
- T17, T18, T19 can start after T10/T11/T12

**With full parallelism:** ~300 min critical path, ~180 min with 3 parallel workers (but we have 1 worker-layout, so sequential).

**Realistic sequential estimate:** ~400 minutes (6.7 hours) for all 3 variants.

---

## 6. QUALITY GATES

### Schematic Phase Gate
- [ ] ERC: 0 errors, 0 warnings
- [ ] All pins assigned (no NC except intentional)
- [ ] All nets connected (no dangling net labels)
- [ ] Strapping pins verified against datasheet
- [ ] Pin assignments match firmware Kconfig expectations
- [ ] Git commit + push before proceeding to board

### Board Phase Gate
- [ ] DRC: 0 violations, 0 unconnected
- [ ] GND plane coverage >90% on In1.Cu
- [ ] 3V3 plane coverage >90% on In2.Cu
- [ ] All RF traces 0.76mm width, direct path to U.FL
- [ ] No silkscreen over copper
- [ ] No silkscreen over board edge
- [ ] Git commit + push before proceeding to gerber

### Gerber Phase Gate
- [ ] All 12 gerber files present (F.Cu, In1.Cu, In2.Cu, B.Cu, F.Mask, B.Mask, F.SilkS, B.SilkS, F.Paste, B.Paste, Edge.Cuts, drill)
- [ ] Drill file present and non-zero
- [ ] Zip archive created with all files
- [ ] Git commit + push before proceeding to order

### Git Phase Gate
- [ ] All schematic files committed
- [ ] All board files committed
- [ ] All gerber files committed (or ignored if >100MB)
- [ ] Branch pushed to `autonomous/mesh-baseline`
- [ ] No uncommitted changes before ordering

---

## 7. SCHEDULING

### Dependency Graph

```
                    ┌─────────────┐
                    │     T1      │
                    │  C3 Schematic│
                    │  (120 min)  │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │     T2      │ │     T3      │ │     T4      │
    │  S3 Schematic│ │ Dual Schematic│ │  C3 Board  │
    │   (90 min)  │ │  (150 min)  │ │  (60 min)  │
    └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
           │               │               │
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │     T5      │ │     T6      │ │     T7      │
    │  S3 Board   │ │ Dual Board  │ │ C3 Place+Route│
    │   (45 min)  │ │  (75 min)   │ │  (45 min)   │
    └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
           │               │               │
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │     T8      │ │     T9      │ │    T10      │
    │ S3 Place+Route│ │Dual Place+Route│ │ C3 Zones+DRC│
    │   (35 min)   │ │  (55 min)   │ │  (30 min)   │
    └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
           │               │               │
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │    T11      │ │    T12      │ │    T13      │
    │ S3 Zones+DRC│ │Dual Zones+DRC│ │ C3 Gerbers  │
    │   (25 min)  │ │  (35 min)   │ │  (15 min)   │
    └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
           │               │               │
           │               │               ▼
           │               │        ┌─────────────┐
           │               │        │    T14      │
           │               │        │ S3 Gerbers  │
           │               │        │  (12 min)   │
           │               │        └──────┬──────┘
           │               │               │
           │               │               ▼
           │               │        ┌─────────────┐
           │               │        │    T15      │
           │               │        │ Dual Gerbers│
           │               │        │  (15 min)   │
           │               │        └──────┬──────┘
           │               │               │
           └───────────────┴───────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │    T16      │
                    │  Git Push   │
                    │  (10 min)   │
                    └─────────────┘
```

### Critical Path

**Sequential (single worker):** T1 → T4 → T7 → T10 → T13 → T14 → T15 → T16 = **317 minutes** (~5.3 hours)

**With parallelism (ideal):** T1 → T4 → T7 → T10 → T13 → T16 = **300 minutes** (5 hours)

**Realistic with breaks:** ~6-8 hours total for all 3 variants.

---

## 8. RISKS + MITIGATIONS

| Risk | Probability | Impact | Mitigation | Circuit Breaker |
|------|-------------|--------|------------|---------------|
| FreeRouting fails to converge | Medium | High | Use pcbnew manual routing for stubborn nets; reduce board size | If >20 unconnected after 20 passes, manual route remaining |
| S3 pin remapping causes firmware mismatch | Medium | High | Cross-check Kconfig BEFORE schematic; use #ifdef in pin headers | ERC fails if pins don't match firmware |
| Dual variant UART bridge too slow | Low | Medium | Use 2Mbps UART per ADR-026; add flow control if needed | Fallback to SPI bridge if UART insufficient |
| JLCPCB rejects gerbers | Low | High | Use JLCPCB's online gerber viewer before ordering; check drill file | If rejected, fix and re-export within 1 hour |
| Component placement too dense | Medium | Medium | Use 4-layer stackup; move to 60x45mm if needed | If DRC fails after 3 iterations, enlarge board |
| Super Mini footprint bug on C3 | Low (avoided) | High | Already using bare MINI-1 module, not Super Mini | N/A |
| GPIO8 has no ADC (V2-ADC bug) | Low (fixed) | High | Already corrected: using GPIO0 for ADC | ERC catches if GPIO8 used for analog |
| Time overrun (>8 hours) | Medium | Medium | Order C3 first, stagger S3+Dual | If >6 hours, drop Dual variant to next sprint |

**Fallback Plans:**
1. If FreeRouting fails on all variants: Manual route C3 only, order as 2-layer with jumper wires for power (proven from V2-ADC board).
2. If S3 schematic delayed: Order C3 first, S3 in next batch (2-week lead time acceptable).
3. If Dual variant too complex: Split into two tasks — C3 board + RP2040 breakout (wire together for testing).

---

## 9. JLCPCB ORDER STRATEGY

### Decision: ONE BATCH, ALL THREE VARIANTS

**Rationale:**
- Shipping cost of $8 is same whether 1 or 3 designs (up to 10 designs per batch at JLCPCB)
- 2-week lead time applies to all; staggering saves no time on S3/Dual
- C3 boards arrive same time as S3/Dual — testing can proceed in parallel
- If C3 has a design flaw, S3/Dual likely share it (same peripheral set) — better to discover together

### Cost Breakdown (Estimated)

| Item | Qty | Unit Cost | Total |
|------|-----|-----------|-------|
| Balloon-C3 4-layer 50x40mm ENIG | 5 | ~$8.00 | ~$40 |
| Balloon-S3 4-layer 50x40mm ENIG | 5 | ~$8.00 | ~$40 |
| Balloon-Dual 4-layer 60x45mm ENIG | 5 | ~$10.00 | ~$50 |
| Shipping (DHL/FedEx, 3 designs) | 1 | ~$8.00 | ~$8 |
| **TOTAL** | | | **~$138** |

**Alternative (staggered):**
- Batch 1: C3 only = $40 + $8 shipping = $48, arrives week 2
- Batch 2: S3 + Dual = $90 + $8 shipping = $98, arrives week 4
- **Total: $146, +2 weeks delay on S3/Dual**

**Recommendation:** ONE BATCH. The $8 savings is not worth 2 weeks delay.

---

## APPENDIX A: Custom Symbols Needed

1. **LR2021F33** — 18-pin custom symbol (left 1-9, right 10-18)
   - Left: 3V3, GND, MISO, MOSI, SCK, NSS, BUSY, GND, RF_SUB
   - Right: GND, GND, NC, DIO9, RST, NC, GND, GND, RF_2G4

2. **RP2040** — Use `MCU_RaspberryPi:RP2040` if available in KiCad 9, else custom

## APPENDIX B: Firmware Pin Verification Commands

```bash
# Verify C3 pins match firmware
cat tracker/firmware/components/lr2021_transport/include/lr2021_spi.h | grep -E "LR2021_PIN_"

# Verify Kconfig defaults
cat tracker/firmware/main/Kconfig.projbuild | grep -E "GPS_UART|FEM_TX|ANTENNA_SWITCH"

# Verify S3 target
cat tracker/firmware/sdkconfig.defaults.esp32s3 | grep -E "IDF_TARGET|FLASHSIZE|SPIRAM"
```

## APPENDIX C: Proven FreeRouting Pipeline (from V2-ADC)

```python
import sys; sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

# 1. Strip tracks
b = pcbnew.LoadBoard('input.kicad_pcb')
for track in b.GetTracks():
    b.Delete(track)

# 2. Export DSN
pcbnew.ExportSpecctraDSN(b, 'output.dsn')

# 3. Run FreeRouting (bash)
# export JAVA_HOME=/usr/lib/jvm/java-1.25.0-openjdk-amd64
# xvfb-run -a $JAVA_HOME/bin/java -jar /tmp/freerouting.jar -de input.dsn -do routed.dsn -mp 20

# 4. Import SES (NOT manual DSN parsing)
pcbnew.ImportSpecctraSES(b, 'routed.ses')

# 5. Fill zones
filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())

# 6. Save
pcbnew.SaveBoard('output.kicad_pcb', b)
```

---

**END OF PLAN**

**Next Step:** Orchestrator converts this plan into kanban tasks T1-T19, dispatches worker-layout for T1 (Balloon-C3 schematic).
