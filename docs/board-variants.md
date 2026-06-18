# Board Variants — Hardware Comparison

## Overview
Three board variants sharing ESP32-C3 + LR2021 core, with progressive coprocessor upgrades.

## Quick Comparison

| | Board A | Board B | Board C |
|---|---------|---------|---------|
| **Coprocessor** | None | RP2040 | iCE40 UP5K |
| **Throughput** | 500-1000 kbps | 2000+ kbps | 2600 kbps × N |
| **Cost added** | $0 | +$1 | +$6 |
| **Weight added** | 0g | +1.3g | +0.8-2.8g |
| **Status** | Prototype (2 boards) | RP2040 ordered | Design phase |

---

## Board A: ESP32-C3 Solo

### Checklist
- [ ] Fix 868 MHz frequency (0-packet issue at 2.4 GHz)
- [ ] Implement inline SPI (bypass RadioLib)
- [ ] Run Phase C test (6 optimization configs)
- [ ] Debug 2.4 GHz RX path (setRxPath HF)
- [ ] Benchmark sustained throughput
- [ ] Document results

### Pin Assignment (unchanged from current)
```
LR2021 → ESP32-C3 (direct SPI)
  MISO → GPIO2, MOSI → GPIO7, SCK → GPIO6
  CS → GPIO10, BUSY → GPIO4, RST → GPIO3, IRQ → GPIO5
```

---

## Board B: ESP32-C3 + RP2040 Coprocessor

### Checklist
- [ ] RP2040-Zero arrives from Amazon
- [ ] Wire RP2040 to LR2021 (SPI0)
- [ ] Wire RP2040 to ESP32-C3 (UART or SPI1)
- [ ] Write PIO SPI master program
- [ ] Write RP2040 firmware (Core 0: radio, Core 1: protocol)
- [ ] Write ESP32-C3 interface firmware
- [ ] Test throughput
- [ ] Measure power consumption
- [ ] Design custom PCB (optional, for flight)

### Pin Assignment
```
LR2021 → RP2040 SPI0:
  MISO → GP4, MOSI → GP3, SCK → GP2, CS → GP5
  BUSY → GP6, IRQ → GP7, RST → GP8

RP2040 → ESP32-C3 (UART):
  GP20 (TX) → ESP32 GPIO1 (RX)
  GP21 (RX) → ESP32 GPIO0 (TX)
  GP9 → ESP32 GPIO2 (power gate control)
```

### RP2040 PIO State Machines
```
PIO 0: IRQ pin monitor (instant wake on packet received)
PIO 1: SPI clock + MOSI (hardware-driven TX)
PIO 2: SPI MISO read → DMA → SRAM (hardware-driven RX)
PIO 3: CS + standby control (auto-restart RX)
```

### Bill of Materials
| Part | Source | Price |
|------|--------|-------|
| RP2040-Zero | Amazon (already ordered) | €10.95 |
| Dupont wires | (have) | — |
| Breadboard | (have) | — |
| Custom PCB (flight) | JLCPCB (future) | ~$5-8/board |

---

## Board C: ESP32-C3 + iCE40 UP5K FPGA

### Checklist
- [ ] Design schematic in KiCad
- [ ] Design PCB layout (4-layer recommended)
- [ ] Generate BOM with JLCPCB part numbers
- [ ] Order 5 boards from JLCPCB
- [ ] Write Verilog: SPI master for LR2021
- [ ] Write Verilog: packet queue in SPRAM
- [ ] Write Verilog: N×N crossbar (for multi-radio)
- [ ] Write ESP32-C3 interface firmware
- [ ] Assemble and test
- [ ] Benchmark throughput

### FPGA Configuration
```
Toolchain: yosys (synthesis) + nextpnr-ice40 (place & route)
Flash: W25Q32JV (32Mbit SPI flash for bitstream)
Programming: via SPI from ESP32-C3 or USB (during development)
```

### Pin Assignment (single-radio prototype)
```
LR2021 → iCE40:
  MISO → IO_12, MOSI → IO_11, SCK → IO_10, CS → IO_13
  BUSY → IO_14, IRQ → IO_15, RST → IO_16

iCE40 → ESP32-C3 (SPI slave):
  MISO → IO_25, MOSI → IO_24, SCK → IO_23, CS → IO_22

iCE40 config flash → iCE40:
  SPI dedicated pins (IO_0-IO_3)

Power gate: ESP32-C3 GPIO → MOSFET → iCE40 VCC
```

### Multi-Radio Pin Assignment (2× LR2021)
```
LR2021 #1: IO_10-IO_16 (7 pins)
LR2021 #2: IO_17-IO_23 (7 pins)
ESP32-C3:  IO_24-IO_27 (4 pins)
Config:    IO_0-IO_3   (4 pins, dedicated SPI flash)
Remaining: 16 I/O free (for 3-4 more radios or GPIO)
```

### Bill of Materials (JLCPCB)
| Part | JLCPCB Part # | Price | Notes |
|------|-------------|-------|-------|
| iCE40UP5K-SG48I | C2678152 | $6.06 @ qty 100 | Extended library (+$3 fee) |
| W25Q32JVSSIQ | check LCSC | ~$0.50 | 32Mbit config flash |
| ESP32-C3 | existing | ~$1 | MCU |
| PCB (5×, 4-layer) | JLCPCB | ~$5 total | 0.6mm FR-4 |
| Assembly | JLCPCB | ~$7/board | SMT assembly |
| **Total per board** | | **~$15-20** | qty 5 |

### JLCPCB Ordering Notes
- iCE40UP5K is **Extended library** ($3 loading fee per order)
- MSL Level 3 (baking may be needed)
- QFN-48 package (7×7mm) — standard for JLCPCB assembly
- PCB assembly fixture needed for this part
