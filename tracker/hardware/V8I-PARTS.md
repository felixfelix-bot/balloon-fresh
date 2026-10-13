# v8i flight board — parts list and open findings

Extracted directly from the artifact, not from memory:

- board: `tracker/hardware/output/v8i_krt_gnss.kicad_pcb` (sha256 `638de5638772…`)
- schematic: `tracker/hardware/schematics/flight_board/v_c3_flight.kicad_sch`
- netlist: `tracker/hardware/schematics/flight_board/v_c3_flight.net`
- 4-layer, 45 × 55 mm, kicad-cli 9.0.8, DRC PASS (0 errors / 0 unconnected / 8 silk warnings)

## What is actually on the board (28 footprints)

| Ref | Value | Role |
|---|---|---|
| U1 | ESP32-C3-WROOM-02 | MCU (**C3, not S3**) |
| U2 | LoRa2021_Gen4 | radio — schematic value says `LR2021F33` (see finding 3) |
| U3 | MAX-M10S | GNSS receiver |
| U4 | TPS7A02 | LDO regulator |
| U5 | **BMP280** | barometer — superseded by the MS5611 respin |
| ANT1 | U.FL | radio antenna |
| ANT2 | U.FL_GNSS | GNSS antenna |
| J1 | Prog_Header | programming header |
| J2 | Debug_Header | debug header |
| SOLAR | Solar_In | solar input |
| C_CAP | 1F_5.5V | supercap (peak-current buffer) |
| C1, C2 | 10uF | decoupling |
| C3, C4 | 100nF | decoupling |
| C_SH1, C_SH2 | DNP | unpopulated shunt caps |
| D1 | BAT54 | Schottky (solar/back-feed path) |
| R_DIV1, R_DIV2 | 100k | divider |
| R_PD | 10k | pull-down |
| R_LED | 330R | LED resistor |
| R_SER | 0R | series link |
| LED1 | LED_RED | status LED |
| MNT1–MNT4 | MountingHole | mechanical |

**Not on this board:** SX1280 (0 occurrences — it exists only in `FLIGHT-BOARD-PLAN.md`),
SX1262 (0), a second LR2021 (only one, U2), ESP32-S3 (0), RP2040 (0), MS5611 (0).

## Open findings (must be resolved before ordering)

1. **Schematic ≠ board.** Netlist has 20 components, the board has 28. The schematic is
   missing **ANT2** (the GNSS antenna connector, physically present), R_SER, C_SH1/C_SH2
   and the mounting holes. The board is ahead of the drawing.
2. **The schematic annotates its own gaps**, including literally *"no GPS antenna feed on
   this board"* at U3.11 RF_IN, plus floating pins — U2.7/11/15/16 ("unmodelled RF module" /
   "probable GND tab left floating"), U3.9 ~RESET, U3.15 VIO_SEL, U3.18 ~SAFEBOOT.
   The GNSS RF path is unproven by the drawing's own admission.
3. **U2 naming is contradictory.** Footprint value `LoRa2021_Gen4` vs schematic value
   `LR2021F33` (the 2 W PA variant). There is **no RP2040** on this board. The F33-class PA
   draws amp-level peaks, which would explain the 1 F supercap — one of the two labels is
   wrong, and it decides both the antenna and the current budget.

## Renders

- `renders/v8i-schematic.png` — schematic (A2, 3041×2150)
- `renders/v8i-board-front.png` — F.Cu + F.SilkS + Edge.Cuts (1754×1241)
- `renders/v8i-board-4layer.png` — F.Cu + In1.Cu + In2.Cu + B.Cu + F.SilkS + Edge.Cuts

Reproduce with `tools/render_board.py` and `tools/extract_parts.py`.
