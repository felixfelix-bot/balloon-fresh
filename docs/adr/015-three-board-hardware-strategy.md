# ADR 015: Three-Board Hardware Strategy

## Status

Proposed

## Context

Throughput testing revealed that the LR2021 radio can sustain 2,600 kbps air rate, but the ESP32-C3's single-core processing pipeline limits end-to-end throughput to 80 kbps (Phase 2 proved SPI reads at 10.46 Mbps — not the bottleneck). Three levels of optimization are possible, each requiring different hardware:

1. **Software-only** (free): Skip PRBS, inline SPI, batch reads → 500-1000 kbps
2. **RP2040 coprocessor** (~$1): PIO hardware SPI master, dual-core → 2000+ kbps
3. **FPGA coprocessor** (~$6): Hardware crossbar, multi-radio → 2600 kbps × N radios

We need to design and test all three paths to determine the optimal balloon hardware for different use cases (tracker, single-radio mesh, multi-radio mesh).

## Decision

Design **three board variants**, sharing the same ESP32-C3 + LR2021 core but with different coprocessor configurations:

### Board A: ESP32-C3 Solo (Baseline / Tracker / Mesh V1)

```
[ESP32-C3] ←SPI→ [LR2021] ←→ Antenna
```

- **Coprocessor**: None
- **Optimization**: Inline SPI (bypass RadioLib), skip PRBS, fixed 255B packets
- **Throughput target**: 500-1000 kbps
- **Weight**: 14-22g (existing tracker/mesh weight)
- **Power**: 134-431 mW (existing budget)
- **Deep sleep**: 5 µA (ESP32-C3 native)
- **Use case**: Tracker, Mesh V1 single-balloon, Minimal variant flights
- **Status**: Prototype exists (2 boards), firmware optimization in progress

### Board B: ESP32-C3 + RP2040 Coprocessor (Mesh V2)

```
[ESP32-C3] ←UART/SPI→ [RP2040] ←SPI0→ [LR2021]
                         ↑ PIO
                    (hardware SPI master)
```

- **Coprocessor**: RP2040-Zero (~$1, 0.3g)
- **RP2040 role**: PIO-based hardware SPI master, packet queue in 264KB SRAM, dual-core radio management
- **ESP32-C3 role**: Power management, deep sleep (5µA), GPS, sensors, FIPS routing
- **Power gating**: RP2040 powered OFF at night via MOSFET controlled by ESP32-C3
- **Throughput target**: 2000+ kbps per radio
- **Weight**: +1.3g over Board A (RP2040 + flash + passives)
- **Power**: +15-25mA daytime only (RP2040 power-gated at night)
- **Use case**: High-throughput single-radio mesh relay
- **Status**: RP2040-Zero ordered, prototype pending

### Board C: ESP32-C3 + Lattice iCE40 UP5K FPGA (Mesh V3)

```
                    ┌─── iCE40 UP5K ───┐
[LR2021 #1] ←SPI0→  │  N×N Crossbar   │  ←SPI→ [ESP32-C3]
[LR2021 #2] ←SPI1→  │  Packet Queue   │
[LR2021 #N] ←SPIn→  │  (128KB SPRAM)  │
                    └─────────────────┘
```

- **Coprocessor**: Lattice iCE40 UP5K (JLCPCB part C2678152, ~$6, 0.3g)
- **FPGA role**: Hardware SPI masters for all radios, N×N crossbar switching, packet queue in 128KB SPRAM, sub-µs bent-pipe relay
- **ESP32-C3 role**: Power management, deep sleep (5µA), FIPS routing decisions, GPS, sensors
- **Power gating**: FPGA powered OFF at night via MOSFET
- **Throughput target**: 2600 kbps per radio × N radios (full air rate)
- **Multi-radio**: 2-6 LR2021 modules on one board (frequency diversity)
- **Weight**: +0.8g (FPGA+flash) + 0.5g per additional LR2021
- **Power**: +3-5mA for FPGA (lowest coprocessor power)
- **Configuration flash**: W25Q32JV (~$0.50) for FPGA bitstream
- **Use case**: Multi-radio bent-pipe mesh relay, maximum throughput
- **Status**: Design phase — PCB to be ordered from JLCPCB

### Comparison Matrix

| Feature | Board A (Solo) | Board B (RP2040) | Board C (FPGA) |
|---------|---------------|-----------------|----------------|
| Coprocessor | None | RP2040-Zero | iCE40 UP5K |
| Cost added | $0 | +$1 | +$6 (FPGA) + $0.50 (flash) |
| Weight added | 0g | +1.3g | +0.8-2.8g |
| Max throughput | ~1000 kbps | ~2000+ kbps | ~2600 kbps × N |
| Max radios | 1 | 1-2 | 1-6 |
| Bent-pipe relay | No (MCU too slow) | Limited (~5µs) | Yes (~1µs, hardware) |
| Development | C/C++ (ESP-IDF) | C/C++ (Pico SDK) | Verilog (yosys) |
| Power (day) | 134-431 mW | +50-83 mW | +10-17 mW |
| Power (night) | 5 µA | 5 µA (RP2040 off) | 5 µA (FPGA off) |
| Toolchain | ESP-IDF | Pico SDK + PIO | yosys + nextpnr |
| JLCPCB part | (existing) | RP2040: ~$1 | iCE40UP5K-SG48I: C2678152 |

### Implementation Priority

```
Phase 1 (NOW, free):     Board A software optimization → 500-1000 kbps
Phase 2 (RP2040 arrives): Board B prototype → 2000+ kbps  
Phase 3 (JLCPCB order):  Board C PCB design + fabrication → full air rate
```

### Board C JLCPCB Ordering Guide

| Part | JLCPCB Part # | Price | Notes |
|------|-------------|-------|-------|
| iCE40UP5K-SG48I | C2678152 | ~$6 (Extended library, +$3 loading fee) | FPGA, QFN-48 |
| W25Q32JVSSIQ | (check LCSC) | ~$0.50 | Config flash for FPGA |
| ESP32-C3 | (existing) | ~$1 | MCU, already in design |
| LR2021 module | (NiceRF) | ~$8 | Radio, hand-soldered |
| PCB (5 boards) | JLCPCB | ~$2-5 | 4-layer, 0.6mm |

## Consequences

### Positive
- **Progressive upgrade path**: A → B → C, each step validated before next
- **Shared ESP32-C3 core**: Same firmware base, same sleep behavior, same sensors
- **Right tool for each job**: ESP32-C3 for sleep, RP2040 for I/O, FPGA for crossbar
- **Cost scales with capability**: $0 → $1 → $6 coprocessor

### Negative
- **Three designs to maintain**: Firmware for each variant
- **Board C complexity**: FPGA PCB design + Verilog development
- **JLCPCB lead time**: 2-3 weeks for Board C fabrication

### Risk Mitigation
- Board A works TODAY (proven TX/RX at 868 MHz)
- Board B uses off-the-shelf RP2040-Zero (no custom PCB needed for prototype)
- Board C only needed for multi-radio — months away
- All three share ESP32-C3 firmware base (only coprocessor interface differs)
