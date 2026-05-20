# DIY v0.1 Hub Board — PCB Design Plan

## Board Specification

| Parameter | Value |
|-----------|-------|
| Board name | DIY v0.1 Development Hub |
| Size | ~45 x 38 mm |
| Layers | Single-sided copper (bottom layer) |
| Substrate | Double-sided copper clad FR4 (user-owned stock), top copper unused or ground plane |
| Fabrication | Toner transfer + etching at c-base Berlin |
| Min trace width | 0.4 mm |
| Min clearance | 0.4 mm |
| Min drill | 0.8 mm |
| Pin pitch (LoRa2021) | 1.29 mm (castellated) |
| Pin pitch (headers) | 2.54 mm (through-hole) |

## Components

| Ref | Component | Package | Qty | Note |
|-----|-----------|---------|-----|------|
| U1 | ESP32-C3_Mini_V1 (Maker go) | Through-hole 2x8 pin header 2.54mm | 1 | Dev board, USB-C, U.FL antenna |
| U2 | NiceRF LoRa2021 Gen4 | 18-pin castellated, 19.81x14.98mm | 1 | LoRa + FLRC + 2.4 GHz |
| U3 | BMP280 breakout | 4-pin header 2.54mm | 1 | Optional, pressure/temp |
| C1 | 100nF | 0805 | 1 | Decoupling for ESP32 |
| C2 | 100nF | 0805 | 1 | Decoupling for LoRa2021 |
| C3 | 100nF | 0805 | 1 | Decoupling for LoRa2021 |
| C4 | 10uF ceramic | 0805 | 1 | Bulk cap for LoRa2021 TX bursts |
| AE1 | Sub-GHz antenna pad | Through-hole pad | 1 | Wire dipole, 16.4cm @ 868 MHz |
| AE2 | 2.4 GHz antenna pad | Through-hole pad | 1 | Wire dipole, 3.1cm @ 2.4 GHz |
| J1 | Debug/programming header | 2x3 pin 2.54mm | 1 | Optional, USB-C on ESP32 may suffice |
| SB1 | Solder bridge SCK | 2x 1.5mm pads, 0.5mm gap | 1 | SPI SCK pin swap |
| SB2 | Solder bridge MOSI | 2x 1.5mm pads, 0.5mm gap | 1 | SPI MOSI pin swap |

## ESP32-C3_Mini_V1 Dev Board

### Board Info
- **Manufacturer**: Maker go
- **Chipset**: ESP32-C3 FN4 (RISC-V, 160 MHz, 400KB SRAM, 4MB flash)
- **Size**: 22.52 x 18 mm
- **Connectors**: USB Type-C, U.FL (I-PEX) external antenna
- **Onboard**: Blue LED on GPIO8 (inverted), BOOT button on GPIO9, RESET button
- **Regulator**: ME6211 (3.3V, needs >=4.3V input for stable output)
- **Deep sleep**: ~43 uA
- **Accessories**: U.FL-to-SMA pigtail cable + 3dBi SMA antenna

### Verified Pinout (top view, USB-C on top)

```
         ┌──────────────────────┐
   3V3 ──┤                      ├── 5V
   GND ──┤                      ├── GND
   D0  0 ├── GPIO0              ├── 21  D10
   D1  1 ├── GPIO1              ├── 20  D9
   D2  2 ├── GPIO2              ├── 9   D8
   D3  3 ├── GPIO3              ├── 8   D7
   D4  4 ├── GPIO4              ├── 7   D6
   D5  5 ├── GPIO5              ├── 6   RX
   TX    ├──                    ├──     NC
         ├──  [USB-C]  [U.FL]   ├──     BOOT
         └──────────────────────┘
```

### Complete Pin Table

| Silkscreen | GPIO | Function | ADC | Strapping | JTAG | Onboard | Our Use |
|------------|------|----------|-----|-----------|------|---------|---------|
| D0 | GPIO0 | Digital I/O | ADC1_CH0 | | | | unused |
| D1 | GPIO1 | Digital I/O | ADC1_CH1 | | | | unused |
| D2 | GPIO2 | Digital I/O | ADC1_CH2 | **Yes** | | | SPI_MISO |
| D3 | GPIO3 | Digital I/O | ADC1_CH3 | | | | LR2021 RST |
| D4 | GPIO4 | Digital I/O | ADC1_CH4 | | Yes | | LR2021 BUSY |
| D5 | GPIO5 | Digital I/O | | | Yes | | LR2021 DIO9 (IRQ) |
| D6 | GPIO6 | Digital I/O | | | Yes | | SPI_SCK |
| D7 | GPIO7 | Digital I/O | | | Yes | | SPI_MOSI |
| D8 | GPIO8 | Digital I/O | | **Yes** | | LED (inv) | I2C SDA + LED |
| D9 | GPIO9 | Digital I/O | | **Yes** | | BOOT btn | I2C SCL |
| D10 | GPIO10 | Digital I/O | | | | | SPI_CS |
| D9_alt | GPIO20 | UART RX | | | | | USB console |
| D10_alt | GPIO21 | UART TX | | | | | USB console |

### Strapping Pin Behavior

| Pin | Default | SPI Boot (normal) | UART Download |
|-----|---------|-------------------|---------------|
| GPIO2 | Floating | HIGH or floating | Any |
| GPIO8 | Floating | Any | HIGH |
| GPIO9 | Pull-up | HIGH (default) | LOW (hold BOOT) |

### Key Notes
- **GPIO4-7 are usable as general-purpose GPIO** despite "JTAG" silkscreen labels. JTAG is only active when explicitly enabled in firmware. When JTAG is off, these are regular GPIOs.
- **GPIO6/7 (SPI_SCK/SPI_MOSI)** are fully accessible on header pins D6/D7.
- **GPIO8 (I2C SDA)** shares with onboard LED (inverted). LED will flicker during I2C traffic — cosmetic only.
- **GPIO9 (I2C SCL)** shares with BOOT button. Internal pullup keeps it HIGH at boot (required). I2C pullup is compatible.
- **GPIO2 (SPI_MISO)** is strapping pin. As an input from LoRa2021, it won't interfere with boot (LoRa2021 MISO is high-Z until SPI transaction).
- **Using GPIO4-7 means no JTAG debug** — use UART/printf via USB-C.
- **U.FL connector** allows external antenna for Sub-GHz (via LoRa2021 ANT pin) or WiFi.

## Netlist

### SPI Bus (ESP32-C3 -> LoRa2021, via solder bridges)

| ESP32-C3 GPIO | Silkscreen | Solder Bridge | LoRa2021 Pin | Function |
|---------------|------------|---------------|-------------|----------|
| GPIO6 | D6 | SB1 | Pin 5 (SCK) | SPI clock (Config A) |
| GPIO7 | D7 | SB2 | Pin 4 (MOSI) | SPI data in (Config A) |
| GPIO2 | D2 | direct | Pin 3 (MISO) | SPI data out from LoRa |
| GPIO10 | D10 | direct | Pin 6 (NSS) | SPI chip select (active low) |

### Solder Bridge Design (SB1, SB2)

The SCK and MOSI lines pass through solder bridges so the PCB works regardless
of whether D6=GPIO6/D7=GPIO7 or D6=GPIO7/D7=GPIO6 (pinout uncertainty).

**Pattern (4 solder pads forming a cross):**

```
  ESP32 D6 pad ──(A1)  (B1)── Net SCK (to LoRa2021 Pin 5)
                       X
  ESP32 D7 pad ──(A2)  (B2)── Net MOSI (to LoRa2021 Pin 4)
```

**Config A** (D6=GPIO6=SCK, D7=GPIO7=MOSI — expected pinout):
- Bridge SB1: solder A1-B1 (straight)
- Bridge SB2: solder A2-B2 (straight)
- Firmware: `#define LR2021_SCK 6` / `#define LR2021_MOSI 7`

**Config B** (D6=GPIO7=MOSI, D7=GPIO6=SCK — swapped pinout):
- Bridge SB1: solder A1-B2 (crossed)
- Bridge SB2: solder A2-B1 (crossed)
- Firmware: `#define LR2021_SCK 7` / `#define LR2021_MOSI 6`

**Pad dimensions:**
- Pad size: 1.5mm x 1.5mm (square or round)
- Gap between pads: 0.5mm (easy to bridge with solder blob)
- Label on silkscreen: "SK" near B1, "MO" near B2
- Default configuration marked with silkscreen line: straight = Config A

**Routing note:** On single-sided copper, the crossed traces are achieved by
routing A1->B2 around the outside of the 4-pad cluster, and A2->B1 through
the inside. This avoids actual trace crossings on one layer.

### Control Signals

| ESP32-C3 GPIO | Silkscreen | LoRa2021 Pin | Function |
|---------------|------------|-------------|----------|
| GPIO4 | D4 | Pin 7 (BUSY) | Busy status output |
| GPIO3 | D3 | Pin 14 (RST) | Hardware reset (active low) |
| GPIO5 | D5 | Pin 15 (DIO9) | IRQ interrupt |

### I2C Bus (ESP32-C3 → BMP280)

| ESP32-C3 GPIO | Silkscreen | BMP280 Pin | Function |
|---------------|------------|-----------|----------|
| GPIO8 | D8 | SDA | I2C data (shared with LED) |
| GPIO9 | D9 | SCL | I2C clock (shared with BOOT) |

### Power

| Net | Source | Destinations |
|-----|--------|-------------|
| VCC_3V3 | ESP32 3V3 pin | LoRa2021 Pin 1 (VCC), BMP280 VCC |
| GND | ESP32 GND pins | LoRa2021 Pins 2,8,11,12,18, BMP280 GND, all cap GND pads |

### RF

| Net | LoRa2021 Pin | Destination |
|-----|-------------|-------------|
| RF_SUBGHZ | Pin 9 (ANT) | Wire antenna pad AE1 (16.4cm wire) |
| RF_24GHZ | Pin 10 (2.4G) | Wire antenna pad AE2 (3.1cm wire) |

### Decoupling

| Cap | Placement | Connected |
|-----|-----------|-----------|
| C1 (100nF) | Near ESP32 VCC pin | VCC_3V3 -- GND |
| C2 (100nF) | Near LoRa2021 Pin 1 (VCC) | VCC_3V3 -- GND |
| C3 (100nF) | Near LoRa2021 Pin 13 (VTCXO) | VCC_3V3 -- GND |
| C4 (10uF) | Near LoRa2021 Pin 1 (VCC) | VCC_3V3 -- GND |

## Board Layout (ASCII, bottom copper view)

```
┌─────────────────────────────────────────────────┐
│                                                  │
│  ┌──────────────┐ [SB1][SB2] ┌────────────────┐ │
│  │  ESP32-C3    │  SCK/MOSI   │ NiceRF LoRa2021│ │
│  │  Mini V1     │  solder     │ 19.81x14.98mm  │ │
│  │  (header)    │  bridges    │ (castellated)   │ │
│  │              │             │                 │ │
│  └──────────────┘             └────────────────┘ │
│                                                  │
│  [C1] [C2] [C3] [C4]                            │
│                                                  │
│  ┌──────┐      ANT_pad ←──── 16.4cm wire        │
│  │BMP280│      2.4G_pad ←──── 3.1cm wire        │
│  │(hdr) │                                         │
│  └──────┘                                        │
│                                                  │
└─────────────────────────────────────────────────┘
   ~45mm wide x ~38mm tall
```

## Wiring Reference

Complete wiring table saved as CSV: `hardware/footprints/wiring-dev-board.csv`

### Quick Wiring Diagram

```
ESP32-C3_Mini_V1          Solder Bridges       NiceRF LoRa2021
┌─────────────────┐      ┌───────────┐       ┌──────────────────┐
│  D7 (GPIO7)  ─────── SB2 ┤A2)   (B2├ ────────── Pin 4 (MOSI)  │
│  D6 (GPIO6)  ─────── SB1 ┤A1)   (B1├ ────────── Pin 5 (SCK)   │
│                      └───┴─── X ───┘        │                  │
│  D2 (GPIO2)  ──────────────────────────────── Pin 3 (MISO)     │
│  D10 (GPIO10)──────────────────────────────── Pin 6 (NSS)      │
│  D4 (GPIO4)  ──────────────────────────────── Pin 7 (BUSY)     │
│  D3 (GPIO3)  ──────────────────────────────── Pin 14 (RST)     │
│  D5 (GPIO5)  ──────────────────────────────── Pin 15 (DIO9)    │
│  3V3         ──────────────────────────────── Pin 1 (VCC)      │
│  GND         ──────────────────────────────── Pin 2,8,11,12,18 │
└─────────────────┘                            └──────────────────┘
                                                    │
                                               Pin 9 (ANT) ── 16.4cm wire
                                               Pin 10 (2.4G) ── 3.1cm wire

ESP32-C3_Mini_V1          BMP280 Breakout
┌─────────────────┐       ┌──────────────┐
│  D8 (GPIO8)  ──────────── SDA          │
│  D9 (GPIO9)  ──────────── SCL          │
│  3V3         ──────────── VCC          │
│  GND         ──────────── GND          │
└─────────────────┘       └──────────────┘
```

## Fabrication Steps at c-base

### Phase 1: Design (at home)
1. Install KiCad: `sudo apt install kicad`
2. Create KiCad project: `hardware/hub_board_diy/`
3. Create custom LoRa2021 footprint from `hardware/footprints/nicerf-lora2021.json`
4. Create/find ESP32-C3_Mini_V1 footprint
5. Design schematic with all nets above
6. Layout PCB (single-sided bottom copper)
7. DRC check (0.4mm traces, 0.4mm clearance)

### Phase 2: Export files
8. Export **bottom copper layer** as mirrored B&W PDF -> toner transfer print
9. Export **board outline** as SVG -> for cutting FR4
10. Export **drill guide** as PDF -> for Platinenbohrmaschine
11. Optional: export **solder paste stencil SVG** for Schneidplotter

### Phase 3: Fabrication (at c-base)
12. Cut FR4 board to ~45x38mm using shear or saw
13. Print copper pattern on **laser printer** (glossy/transfer paper)
14. Iron pattern onto bottom copper (Bügelrpresse, ~2 min)
15. Etch in Ätzbad (~10-15 min, ferric chloride or sodium persulfate)
16. Clean off toner with acetone
17. Drill holes (Platinenbohrmaschine): header holes 0.8mm, castellated pads no drill needed
18. Solder components:
    - ESP32-C3_Mini_V1: through-hole headers, board plugs in from top
    - LoRa2021: solder castellated pads flat on board surface
    - BMP280 breakout: through-hole header
    - Caps: 0805 SMD, hand-solder
    - Antenna wires: solder to pads
    - Solder bridges SB1+SB2: bridge straight (Config A) for D6=SCK, D7=MOSI
      - If SPI fails on first test, desolder bridges and re-solder crossed (Config B)

### Phase 4: Test
19. Flash firmware: `idf.py -p /dev/ttyACM0 flash monitor`
20. Verify SPI communication (LR2021 chip ID)
21. Test LoRa TX/RX between 2 boards
22. Test BMP280 readings

## KiCad Project Structure

```
hardware/hub_board_diy/
├── hub_board_diy.kicad_pro
├── hub_board_diy.kicad_sch
├── hub_board_diy.kicad_pcb
└── export/
    ├── hub_board_diy_bottom_mirrored.pdf   (toner transfer)
    ├── hub_board_diy_outline.svg           (board cutting)
    ├── hub_board_diy_drill_guide.pdf       (hole drilling)
    └── hub_board_diy_gerbers/              (JLCPCB, future)
```

## Design Rules for Toner Transfer

| Rule | Value | Reason |
|------|-------|--------|
| Min trace width | 0.4 mm | Toner transfer resolution limit |
| Min clearance | 0.4 mm | Prevent solder bridges |
| Min pad size | 1.5 mm dia | Hand-soldering |
| Drill size (headers) | 0.8 mm | Standard 2.54mm header pins |
| Drill size (antenna pads) | 1.0 mm | Thicker wire |
| No vias | — | Can't plate through-holes with toner transfer |
| All traces on bottom | — | Single-sided design |
