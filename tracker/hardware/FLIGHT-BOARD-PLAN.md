# Flight Board V0.1 + Solar/Wing Carrier — Design & Implementation Plan

## Overview

Two PCB designs for the first pico balloon flight (Minimal variant, ~9g target):

| Board | Size | Purpose | Qty |
|-------|------|---------|-----|
| Hub Board V0.1 | ~50x45mm | MCU + LoRa2021 + GPS + power | 5 |
| Solar/Wing Carrier | 65x28mm | 3x 52x19mm solar cells, optional PCB Yagi for V2 | 20 |

Fabrication: JLCPCB (primary) + toner transfer fallback (0.4mm trace/clearance).

---

## Design Decisions

### MCU: Dual Footprint (Dev + Flight)
- Dev: ESP32-C3_Mini_V1 via 2x8 pin header (4g, USB-C onboard, easy debug)
- Flight: Bare ESP-C3-12F via QFN-56 pads (1g, needs external USB-serial for flash)

### RF: NiceRF LoRa2021 (verified working)
- 18-pin castellated module (19.81x14.98mm)
- SPI bus with solder bridges for pin-swap (SB1, SB2)
- Wire dipoles for V1 (no Yagis, no SP4T, no FEM)

### GPS: Dual Footprint (Dev + Flight)
- Dev: SparkFun MAX-M10S breakout via 4-pin header
- Flight: Bare MAX-M10S LGA + ceramic patch antenna
- Airborne mode required (dynamic model 6, supports up to 80,000m)
- UART1: GPIO0=TX, GPIO1=RX

### Power: USB or Solar+Supercap (jumper select)
- Dev: USB 5V via ESP32 dev board
- Flight: 12x 52x19mm solar cells (4 carriers) → BAT54 → 1.0F 5.5V supercap → TPS7A02 LDO → 3.3V
- Power select solder bridge SB3: USB or solar input

### SX1280: Not Included
- GPS provides position for ground station antenna tracking
- LR2021 has RTToF (untested) for future ranging experiments
- SX1280 adds ~2g + SPI complexity for uncertain benefit at 200+ km
- If ranging needed: test LR2021 RTToF first (raw 2-byte opcode SPI — RadioLib DEPRECATED, see ADR-020)

---

## Hub Board V0.1 Schematic

### Pin Mapping (ESP32-C3)

| ESP32 GPIO | Silkscreen | Function | Destination |
|------------|-----------|----------|-------------|
| GPIO0 | D0 | UART1_TX | MAX-M10S RXD |
| GPIO1 | D1 | UART1_RX | MAX-M10S TXD |
| GPIO2 | D2 | SPI_MISO | LoRa2021 Pin 3 |
| GPIO3 | D3 | LR2021_RST | LoRa2021 Pin 14 |
| GPIO4 | D4 | LR2021_BUSY | LoRa2021 Pin 7 |
| GPIO5 | D5 | LR2021_IRQ | LoRa2021 Pin 15 (DIO9) |
| GPIO6 | D6 | SPI_SCK (via SB1) | LoRa2021 Pin 5 |
| GPIO7 | D7 | SPI_MOSI (via SB2) | LoRa2021 Pin 4 |
| GPIO8 | D8 | ADC | Supercap voltage divider |
| GPIO10 | D10 | SPI_CS | LoRa2021 Pin 6 (NSS) |

### Components

| Ref | Dev Config | Flight Config | Package |
|-----|-----------|---------------|---------|
| U1a | ESP32-C3_Mini_V1 (header) | — | 2x8 pin 2.54mm |
| U1b | — | ESP-C3-12F bare | QFN-56 7x7mm |
| U2 | NiceRF LoRa2021 | NiceRF LoRa2021 | 18-pin castellated |
| U3a | MAX-M10S breakout (header) | — | 4-pin 2.54mm |
| U3b | — | MAX-M10S bare + patch | LGA 9.7x10.1mm |
| U4 | TPS7A0233DBVR | TPS7A0233DBVR | SOT-23-5 |
| D1 | BAT54 | BAT54 | SOD-123 |
| C1 | 100nF (ESP32 decouple) | 100nF | 0402 |
| C2 | 100nF (LoRa VCC) | 100nF | 0402 |
| C3 | 100nF (LoRa VTCXO) | 100nF | 0402 |
| C4 | 10uF (LoRa TX burst) | 10uF | 0402 |
| C5 | 100nF (GPS decouple) | 100nF | 0402 |
| C6 | 10uF (GPS decouple) | 10uF | 0402 |
| C7 | 100nF (LDO output) | 100nF | 0402 |
| SC1 | — | 1.0F 5.5V supercap | THT 2-pin |
| SB1 | Solder bridge SCK | Solder bridge | 4-pad cross |
| SB2 | Solder bridge MOSI | Solder bridge | 4-pad cross |
| SB3 | Power select jumper | Power select | 3-pad |
| AE1 | Sub-GHz antenna pad | Wire dipole 16.4cm | THT pad |
| AE2 | 2.4 GHz antenna pad | Wire dipole 3.1cm | THT pad |
| J1 | Debug header | — | 2x3 pin 2.54mm |
| J2 | — | Solar input pads | 2-pad |

### Power Jumper SB3

```
[USB 3V3]──(A)  (B)──[3V3 net → all ICs]
              (C)──[Solar via BAT54 → TPS7A02]

Dev: bridge A-B (USB power)
Flight: bridge A-C (solar power)
```

### LoRa2021 Netlist

```
ESP32-C3_Mini_V1          Solder Bridges       NiceRF LoRa2021
┌─────────────────┐      ┌───────────┐       ┌──────────────────┐
│  D7 (GPIO7)  ─────── SB2 ┤A2)   (B2├ ─────── Pin 4 (MOSI)    │
│  D6 (GPIO6)  ─────── SB1 ┤A1)   (B1├ ─────── Pin 5 (SCK)     │
│                      └───┴─── X ───┘        │                  │
│  D2 (GPIO2)  ──────────────────────────────── Pin 3 (MISO)    │
│  D10 (GPIO10)──────────────────────────────── Pin 6 (NSS)     │
│  D4 (GPIO4)  ──────────────────────────────── Pin 7 (BUSY)    │
│  D3 (GPIO3)  ──────────────────────────────── Pin 14 (RST)    │
│  D5 (GPIO5)  ──────────────────────────────── Pin 15 (DIO9)   │
│  3V3         ──────────────────────────────── Pin 1 (VCC)     │
│  GND         ──────────────────────────────── Pin 2,8,11,12,18│
└─────────────────┘                            └──────────────────┘
                                                    │
                                               Pin 9 (ANT)  ── 16.4cm wire (868 MHz)
                                               Pin 10 (2.4G)── 3.1cm wire (2.4 GHz)
```

### GPS Netlist

```
ESP32-C3_Mini_V1          MAX-M10S (breakout or bare)
┌─────────────────┐       ┌──────────────┐
│  D0 (GPIO0)  ──────────── RXD          │  (ESP TX → GPS RX)
│  D1 (GPIO1)  ──────────── TXD          │  (ESP RX ← GPS TX)
│  3V3         ──────────── VCC          │
│  GND         ──────────── GND          │
└─────────────────┘       └──────────────┘
```

### Solder Bridge Design (SB1, SB2)

```
  ESP32 D6 pad ──(A1)  (B1)── Net SCK (to LoRa2021 Pin 5)
                       X
  ESP32 D7 pad ──(A2)  (B2)── Net MOSI (to LoRa2021 Pin 4)

Config A (D6=GPIO6=SCK, D7=GPIO7=MOSI — expected):
  Bridge SB1: A1-B1 (straight), SB2: A2-B2 (straight)

Config B (swapped):
  Bridge SB1: A1-B2 (crossed), SB2: A2-B1 (crossed)

Pad: 1.5mm x 1.5mm, gap 0.5mm
```

---

## GPS/RF Antenna Isolation Rules

1. GPS ceramic patch at TOP of board, LoRa2021 at BOTTOM — maximum physical separation
2. Solid ground plane on bottom layer under GPS patch area
3. Keep-out zone: no copper, no traces, no components under 2.4 GHz antenna wire pad
4. GPS patch faces UP (toward sky), wire antennas hang DOWN
5. 100nF + 10uF decoupling directly at GPS VCC pin
6. Firmware time-multiplex: read GPS → sleep GPS → TX via LoRa (prevents TX bursts desensitizing GPS LNA)
7. ESP32 placed centrally, far from both antenna feed points
8. 10uF + 100pF filter caps on ESP32 VCC near the chip

---

## Solar/Wing Carrier Board

### Layout (65x28mm)

```
┌────────────────────────────────────────────────────────────┐
│ PCB-YAGI AREA (V2 only — unpopulated copper for V1)        │
│                                                            │
│ ┌────────────┐ ┌────────────┐ ┌────────────┐             │
│ │ 52x19mm    │ │ 52x19mm    │ │ 52x19mm    │             │
│ │ solder pads│ │ solder pads│ │ solder pads│             │
│ │ 2 bus bars │ │ 2 bus bars │ │ 2 bus bars │             │
│ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘             │
│       └────── Series ─┘──── Series ─┘                     │
│              = 1.5V, 400mA                                 │
│                                                            │
│ ╔════╗                                                     │
│ ║TAB ║                                                     │
│ ╚════╝  Pin 1: V_OUT  Pin 2: GND  Pin 3: V_CHAIN_IN      │
└────────────────────────────────────────────────────────────┘
```

### Components

| Ref | Component | Package | Note |
|-----|-----------|---------|------|
| SC1-SC3 | 52x19mm solar cell pads | Solder pads, 2 bus bars each | Cells soldered directly to pads |
| FB1 | Ferrite bead (optional) | 0402 | Isolates solar traces from V2 Yagi area |
| J1 | 3-pin tab connector | Solder pads | V_OUT, GND, V_CHAIN_IN |

### Solar Configuration for First Flight (12 cells, 4 carriers)

```
String A: Carrier 1 (3 series, 1.5V) + Carrier 2 (3 series, 1.5V) = 3.0V, 400mA
String B: Carrier 3 (3 series, 1.5V) + Carrier 4 (3 series, 1.5V) = 3.0V, 400mA
Strings A + B in parallel = 3.0V, 800mA

3.0V → BAT54 → 1.0F 5.5V supercap → TPS7A02 (3.3V) → MCU + radio + GPS
```

### V2 Upgrade Path

Same PCB, populate additionally:
- PCB Yagi copper etching (2.4 GHz, 6-9 dBi)
- Ferrite bead FB1 between solar and antenna areas
- Connect V_OUT to SP4T switch on hub instead of direct to power

---

## Board Layout (Hub V0.1, top view)

```
┌────────────────────────────────────────────────────────────┐
│                                                            │
│  [GPS Patch Area]         [Keep-Out: no copper under AE2]  │
│  ┌──────────────┐                                     AE2──┤── 3.1cm wire (2.4G)
│  │ MAX-M10S     │                                           │
│  │ (bare/hdr)   │                                           │
│  └──────────────┘                                           │
│                                                            │
│  [C5] [C6]     [C7]                                        │
│  GPS decouple   LDO out                                     │
│                                                            │
│  ┌─────────┐ [SB3]  ┌────┐  ┌────┐                        │
│  │ Solar   │ power  │BAT54│  │TPS │                        │
│  │ input   │ select │     │  │7A02│                        │
│  │ J2      │        └────┘  └────┘                        │
│  └────┬────┘                                                │
│       │                                                     │
│  ┌────┴─────────┐   [SB1][SB2]   ┌──────────────────────┐ │
│  │              │   SPI bridges   │ NiceRF LoRa2021      │ │
│  │  ESP32-C3    │                 │ 19.81x14.98mm        │ │
│  │  Mini V1     │                 │ (castellated)        │ │
│  │  (header)    │                 │                      │ │
│  │  OR          │                 └──────────────────────┘ │
│  │  ESP-C3-12F  │                                 AE1──┤──┤── 16.4cm wire (868)
│  │  (bare pads) │                                      │  │
│  └──────────────┘                                      │  │
│                                                        │  │
│  [C1] [C2] [C3] [C4]                                  │  │
│  decoupling                                            │  │
│                                                        │  │
│  [SC1 supercap pads]     [J1 debug hdr]                │  │
│  1.0F 5.5V                                             │  │
│                                                        GND──┘
└────────────────────────────────────────────────────────────┘
  ~50mm wide x ~45mm tall
```

---

## Fabrication

### JLCPCB Order

| Board | Size | Qty | Cost |
|-------|------|-----|------|
| Hub V0.1 | 50x45mm | 5 | ~$3 |
| Solar/Wing Carrier | 65x28mm | 20 | ~$5 |
| Shipping | | | ~$8 |
| **Total** | | | **~$16** |

### Design Rules (toner-transfer compatible)

| Rule | Value |
|------|-------|
| Min trace width | 0.4mm (16mil) |
| Min clearance | 0.4mm (16mil) |
| Min pad size | 1.5mm dia |
| Drill (headers) | 0.8mm |
| Drill (antenna pads) | 1.0mm |
| Vias | Minimize (provide single-layer alternative) |
| Layers | 2 (top: signal, bottom: GND plane) |

---

## BOM (Parts to Order)

| Item | Source | Cost |
|------|--------|------|
| SparkFun MAX-M10S breakout | sparkfun.com / digikey | ~EUR 15-20 |
| 1.0F 5.5V supercap (x2 spares) | digikey | ~EUR 2-3 each |
| TPS7A02 LDO (x5 spares) | digikey | ~EUR 1 each |
| BAT54 Schottky (x10) | digikey | ~EUR 0.30 each |
| 0402 caps kit (100nF + 10uF) | digikey | ~EUR 5 |
| **Total** | | **~EUR 30-35** |

Already owned: ESP32-C3_Mini_V1 (20x), NiceRF LoRa2021 (4x), solar cells (100x 52x19mm), FR4 copper clad.

---

## Implementation Checklist

### Phase 1: Project Setup
- [ ] 1.1 Create `tracker/hardware/flight-board-v0.1/` directory structure
- [ ] 1.2 Create `tracker/hardware/solar-wing-carrier/` directory structure
- [ ] 1.3 Create KiCad project files for hub board
- [ ] 1.4 Create KiCad project files for solar carrier

### Phase 2: Custom Footprints
- [ ] 2.1 LoRa2021 castellated footprint (from `footprints/nicerf-lora2021.json`)
- [ ] 2.2 ESP32-C3_Mini_V1 header footprint (from `footprints/esp32c3-mini-v1.json`)
- [ ] 2.3 ESP-C3-12F bare QFN-56 footprint
- [ ] 2.4 MAX-M10S bare LGA footprint
- [ ] 2.5 MAX-M10S breakout header footprint (SparkFun standard)
- [ ] 2.6 Solar cell 52x19mm solder pad footprint (2 bus bars)
- [ ] 2.7 Wing tab 3-pin connector footprint
- [ ] 2.8 Solder bridge 4-pad cross footprint
- [ ] 2.9 Power select 3-pad jumper footprint

### Phase 3: Hub Board Schematic
- [ ] 3.1 ESP32-C3_Mini_V1 dev board symbol + connections
- [ ] 3.2 ESP-C3-12F bare module symbol + connections (alternative)
- [ ] 3.3 NiceRF LoRa2021 symbol with all 18 pins
- [ ] 3.4 SPI bus with solder bridges SB1, SB2
- [ ] 3.5 Control signals (RST, BUSY, IRQ/DIO9)
- [ ] 3.6 MAX-M10S GPS symbol (breakout + bare options)
- [ ] 3.7 UART1 connection (GPIO0, GPIO1)
- [ ] 3.8 Power chain: solar input → BAT54 → TPS7A02 → 3V3
- [ ] 3.9 Supercap connection (SC1)
- [ ] 3.10 Power select jumper SB3
- [ ] 3.11 Decoupling caps (C1-C7)
- [ ] 3.12 Antenna pads (AE1 Sub-GHz, AE2 2.4 GHz)
- [ ] 3.13 ADC voltage divider for supercap monitoring
- [ ] 3.14 Debug header J1
- [ ] 3.15 Solar input pads J2
- [ ] 3.16 Electrical rules check (ERC)

### Phase 4: Hub Board PCB Layout
- [ ] 4.1 Import netlist from schematic
- [ ] 4.2 Place GPS at top, LoRa2021 at bottom (max separation)
- [ ] 4.3 Place ESP32 centrally between GPS and LoRa2021
- [ ] 4.4 Place power components (BAT54, TPS7A02, supercap pads) on one side
- [ ] 4.5 Route SPI bus (short, parallel traces to LoRa2021)
- [ ] 4.6 Route UART to GPS
- [ ] 4.7 Route 50-ohm RF traces from LoRa2021 to antenna pads
- [ ] 4.8 Route power traces (wider for current carrying)
- [ ] 4.9 Bottom layer: solid GND plane (with cutout under AE2 keep-out)
- [ ] 4.10 GND plane cutout under 2.4 GHz antenna pad (keep-out zone)
- [ ] 4.11 Solid GND plane under GPS patch area
- [ ] 4.12 Place decoupling caps close to IC VCC pins
- [ ] 4.13 Route ADC voltage divider
- [ ] 4.14 Place debug header
- [ ] 4.15 Design rule check (DRC)

### Phase 5: Solar/Wing Carrier Schematic
- [ ] 5.1 Three solar cell pad symbols (SC1, SC2, SC3)
- [ ] 5.2 Series interconnect traces
- [ ] 5.3 3-pin tab connector (V_OUT, GND, V_CHAIN_IN)
- [ ] 5.4 Optional ferrite bead FB1
- [ ] 5.5 Optional PCB Yagi driven element (for V2)
- [ ] 5.6 ERC

### Phase 6: Solar/Wing Carrier PCB Layout
- [ ] 6.1 Import netlist
- [ ] 6.2 Place 3x solar cell pads (52x19mm each, correct spacing)
- [ ] 6.3 Route series interconnects between cells
- [ ] 6.4 Place tab connector pads at bottom edge
- [ ] 6.5 Optional: PCB Yagi copper pattern in antenna area
- [ ] 6.6 Place ferrite bead pad (optional)
- [ ] 6.7 Bottom layer: GND pour (except under antenna area for V2)
- [ ] 6.8 DRC

### Phase 7: Export & Order
- [ ] 7.1 Export hub board gerbers (JLCPCB format)
- [ ] 7.2 Export solar carrier gerbers (JLCPCB format)
- [ ] 7.3 Export hub board mirrored bottom copper PDF (toner transfer)
- [ ] 7.4 Export solar carrier mirrored bottom copper PDF (toner transfer)
- [ ] 7.5 Export drill guides for both boards
- [ ] 7.6 Submit JLCPCB order

### Phase 8: Parts Ordering
- [ ] 8.1 Order SparkFun MAX-M10S breakout (digikey or sparkfun)
- [ ] 8.2 Order 1.0F 5.5V supercapacitors (x2-3)
- [ ] 8.3 Order TPS7A02 LDO (x5 spares)
- [ ] 8.4 Order BAT54 Schottky diodes (x10)
- [ ] 8.5 Order 0402 cap kit if needed

### Phase 9: Assembly & Test
- [ ] 9.1 Assemble hub board (dev config: ESP32 header + LoRa2021 + GPS breakout)
- [ ] 9.2 Flash firmware: `idf.py -p /dev/ttyACM0 flash monitor`
- [ ] 9.3 Verify SPI communication (LR2021 chip ID read)
- [ ] 9.4 Test LoRa TX/RX between 2 boards
- [ ] 9.5 Test GPS fix (NMEA output on UART1)
- [ ] 9.6 Test GPS/RF coexistence (GPS fix + LoRa TX simultaneously)
- [ ] 9.7 Solder solar cells to 4 carrier boards
- [ ] 9.8 Wire carriers in 2S2P configuration (3.0V, 800mA)
- [ ] 9.9 Test solar charging: supercap voltage under sunlight
- [ ] 9.10 Test full power chain: solar → supercap → LDO → radio TX
- [ ] 9.11 Range test with ground station

### Phase 10: First Flight Prep
- [ ] 10.1 Final weight check (target: <9g flight config)
- [ ] 10.2 Pre-stretch Yokohama 32" balloon
- [ ] 10.3 Leak test balloon
- [ ] 10.4 Fill with He 4.6, measure free lift
- [ ] 10.5 Heat seal + Kapton tape
- [ ] 10.6 Launch!

---

## File Structure

```
tracker/hardware/
├── flight-board-v0.1/
│   ├── flight-board-v0.1.kicad_pro
│   ├── flight-board-v0.1.kicad_sch
│   ├── flight-board-v0.1.kicad_pcb
│   ├── flight-board-v0.1.kicad_prl
│   ├── fp-lib-table
│   ├── sym-lib-table
│   ├── footprints/
│   │   ├── LoRa2021_castellated.kicad_mod
│   │   ├── ESP32-C3-Mini-V1-header.kicad_mod
│   │   ├── ESP-C3-12F-bare.kicad_mod
│   │   ├── MAX-M10S-bare.kicad_mod
│   │   ├── MAX-M10S-breakout-header.kicad_mod
│   │   ├── SolarCell_52x19mm.kicad_mod
│   │   ├── SolderBridge_4pad.kicad_mod
│   │   └── PowerSelect_3pad.kicad_mod
│   ├── symbols/
│   │   └── flight-board.kicad_sym
│   └── export/
│       ├── gerbers/
│       └── flight-board_bottom_mirrored.pdf
├── solar-wing-carrier/
│   ├── solar-wing-carrier.kicad_pro
│   ├── solar-wing-carrier.kicad_sch
│   ├── solar-wing-carrier.kicad_pcb
│   ├── solar-wing-carrier.kicad_prl
│   ├── fp-lib-table
│   ├── sym-lib-table
│   ├── footprints/
│   │   ├── SolarCell_52x19mm.kicad_mod
│   │   ├── Wing_Tab_3pin.kicad_mod
│   │   └── PCB_Yagi_2.4GHz.kicad_mod
│   ├── symbols/
│   │   └── solar-carrier.kicad_sym
│   └── export/
│       ├── gerbers/
│       └── solar-wing_bottom_mirrored.pdf
├── footprints/              ← existing shared data
│   ├── esp32c3-mini-v1.json
│   ├── esp32c3-mini-v1.csv
│   ├── nicerf-lora2021.json
│   └── wiring-dev-board.csv
├── hub_board/               ← existing Komfort scaffold (SKiDL)
├── hub_board_diy/           ← existing DIY toner transfer plan
└── wing_board/              ← existing wing board scaffold (SKiDL)
```
