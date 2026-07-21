# Integration Assessment: balloon-circuit-design

**Date:** 2026-07-21
**Phase:** assessment → ready for execution

## Current State of Hardware Design Files

### 1. SKiDL Flight Board Schematics (hub_board, wing_board) — BROKEN

**hub_schematic.py:** Defines 6 subcircuits (ESP32-C3, LR2021, SKY66112, SP4T, BMP280, power supply) but:
- **Zero net connections** — all 22 nets declared as stubs, no component pins wired
- **4 of 5 key parts missing from KiCad v9 libraries:**
  - ESP32-C3-MINI-1 → NOT in RF_Module (only DevKitM-1, WROOM-02 exist)
  - SKY66112-11 → NOT in RF_Amplifier
  - SKY13351-378LF → NOT in RF_Switch
  - TPS7A0233DBVR → NOT in Regulator_Linear
  - BMP280 → EXISTS (8 pins)
- **LR2021** → NOT in RF_Module (custom module)

**wing_schematic.py:** Defines PCB Yagi + solar cells but:
- "Mechanical:Antenna_Driven" → NOT a real KiCad library part
- Same zero-connection problem as hub

### 2. DIY v0.1 Hub Board (hub_board_diy/) — MOST COMPLETE

- Has real KiCad files: `.kicad_sch` (251 lines), `.kicad_pcb` (86 lines), `.kicad_pro`
- Uses generic connectors (Conn_02x08 for ESP32 dev board, Conn_01x09 for LoRa2021, Conn_01x04 for GPS)
- Has custom footprints for ESP32-C3_Mini_V1 header and LoRa2021 castellated module
- Has solder jumpers for pin-swap (matches FLIGHT-BOARD-PLAN.md design)
- PCB is 2-layer, 1.6mm FR4, standard stackup
- **But:** Only 4 nets defined (VCC_3V3, GND, + 2 more). Layout appears minimal — just layer/stackup setup, no traces/components placed yet.

### 3. FLIGHT-BOARD-PLAN.md — DESIGN SOURCE OF TRUTH

Detailed plan exists with:
- Complete pin mapping (ESP32-C3 ↔ LoRa2021 ↔ GPS)
- Dual-footprint approach: dev board headers + bare chip pads
- Component list with packages (0402 caps, SOT-23-5 LDO, SOD-123 diode)
- Power architecture (solar → BAT54 → supercap → TPS7A02 → 3.3V)
- JLCPCB fabrication notes (2-layer, 6mil min trace)

## Blockers for JLCPCB Manufacturing

| Blocker | Severity | Fix |
|---------|----------|-----|
| Custom KiCad symbols missing (ESP32-C3-MINI-1, SKY66112, SKY13351, TPS7A02, LR2021) | CRITICAL | Create .kicad_sym library or use connector-based approach from DIY board |
| SKiDL schematics have no net connections | CRITICAL | Rewrite with pin-level wiring per FLIGHT-BOARD-PLAN.md pin mapping |
| No PCB layout exists (only empty layer setup) | CRITICAL | Import netlist → KiCad → place + route |
| No DRC run | HIGH | Run kicad-cli DRC after layout |
| No Gerber output | HIGH | Generate after DRC passes |
| KICAD_SYMBOL_DIR env var not set | LOW | `export KICAD_SYMBOL_DIR=/usr/share/kicad/symbols` |

## Recommended Path Forward

**Option A (fastest, recommended):** Extend DIY v0.1 board
- Already has real KiCad project structure
- Uses connector-based approach (no custom symbols needed for dev board modules)
- Add components, wire nets, route traces in KiCad GUI
- Prototype on dev boards first, validate, then add bare-chip footprints

**Option B:** Fix SKiDL schematics
- Create custom KiCad symbol library for missing parts
- Rewrite hub_schematic.py + wing_schematic.py with actual pin connections
- Generate netlist → import to KiCad → layout
- More work but reproducible/version-controlled

## Cross-Track Discovery: SPI Speed (from balloon-speed-tests)

- Single-batch SPI at 20 MHz confirmed working with LR2021 (1733 kbps, 1000/1000 TX_DONE)
- Continuous SCK (spi_write_blocking) — no gaps needed
- **PCB layout implication:** SPI traces (MOSI/MISO/SCK/CS) ESP32-C3 ↔ LR2021 must be:
  - Short (<30mm ideal for 20 MHz on 2-layer FR4)
  - Length-matched within ~5mm (SCK vs MOSI/MISO)
  - No sharp corners (45° or rounded traces preferred)
  - Ground plane under SPI bus (minimize loop area)
  - Decoupling cap close to LR2021 VCC pin (100nF + 10µF per existing plan)

## Environment Status
- KiCad v9.0.8 installed ✓
- kicad-cli available ✓
- SKiDL v2.2.3 installed ✓
- KICAD_SYMBOL_DIR=/usr/share/kicad/symbols (223 libraries available)
- 5 of 9 referenced libraries found ✓ (parts within them incomplete)
