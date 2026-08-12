BALLOON FLIGHT BOARD — MANUAL ROUTING HANDOVER
==============================================

BOARD: v_c3_flight_v7_routed.kicad_pcb
Size: 80x60mm, 4-layer, 0.6mm thickness
Layers: F.Cu / In1.Cu (GND zone) / In2.Cu (+3V3 zone) / B.Cu
20 components, 42 track segments routed, 36 vias placed

STATUS: 14/16 signal nets routed. 6 unrouted. GND/+3V3 via copper zones.

6 UNROUTED NETS — ROUTE THESE:
1. SPI_MOSI   U2.3 (66,14)  -> U1.6 (40,25)   28mm  SPI bus, route around U1
2. LR_BUSY    U2.12 (74,15) -> U1.3 (40,25)   35mm  IRQ line, longest diagonal
3. LR_DIO0    U2.14 (66,14) -> U1.13 (49,27)  21mm  Shortest unrouted
4. I2C_SCL    U5.4 (38,50)  -> U1.8 (40,25)   25mm  Vertical route, south to center
5. UART0_TX   U1.12 (49,28) -> J1.4 (9,52)    46mm  Longest, route to edge
6. UART0_RX   U1.11 (49,30) -> J1.5 (7,52)    48mm  Parallel to UART0_TX

Components:
  U1 = ESP32-C3-WROOM-02 (center, 40,25) — 31 pads
  U2 = HOPERF RFM9XW / LR2021 radio (66,14) — 16 pads
  U3 = uBlox MAX GPS (65,40) — 18 pads
  U5 = Bosch BMP280 sensor (38,50) — 8 pads
  J1 = 6-pin header (17,52) — UART/debug
  J2 = 4-pin header (48,54) — I2C breakout

ROUTING RULES:
- Track widths: 0.2mm signal, 0.4mm power
- Via: 0.55mm outer / 0.3mm drill
- Layers for routing: F.Cu and B.Cu (inner layers are zone fills)
- Use vias to transition between F.Cu and B.Cu
- KEEPOUT ZONE: Rectangle (26,6.9) to (54,17.9) — above U1, do NOT route through on F.Cu

Suggested routing order (hardest first):
  1. UART0_TX + UART0_RX (46-48mm, route together along board edge to J1)
  2. LR_BUSY (35mm, diagonal across board)
  3. SPI_MOSI (28mm, around U1)
  4. I2C_SCL (25mm, vertical south to center)
  5. LR_DIO0 (21mm, shortest)

After routing: Run DRC in KiCad (Inspect -> Design Rules Checker).
Then generate Gerbers (File -> Fabrication Outputs -> Gerbers).