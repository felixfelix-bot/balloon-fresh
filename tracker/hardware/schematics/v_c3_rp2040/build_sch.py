#!/usr/bin/env python3
"""Generate v_c3_rp2040.kicad_sch — C3+RP2040 dual-MCU schematic, Variant 3 (complete).

Single-sheet A3 layout, four functional groups:

  Power chain    X=35..130  Y=35..100
  ESP32-C3 (U1)  X=170..210 Y=30..135
  RP2040 (U2)    X=245..310 Y=45..155
  LR2021 (U3)    X=350..410 Y=60..120
  MAX-M10S (U4)  X=150..210 Y=170..220 (bottom-left)
  BMP280 (U6)    X=235..280 Y=170..220
  Connectors     various
"""

import sys
sys.path.insert(0, "/home/c03rad0r/repos/balloon-fresh/tracker/hardware/schematics/v_c3_rp2040")
from schematic_lib import Schematic, GLIB, load_libraries, symbol_lib_lookup_global, to_schematic

load_libraries()

sch = Schematic()

def pin_at(ref, pnum):
    return sch.pin_at(ref, pnum, symbol_lib_lookup_global)


def stub(ref, pnum, length=5.08):
    """Return (end_x, end_y) — connection wire extends outward from pin in pin's natural direction."""
    sym = next(s for s in sch.symbols if s["ref"] == ref)
    lib_sym = symbol_lib_lookup_global(sym["lib_id"])
    p = lib_sym.pins[pnum]
    px, py = to_schematic(p.x, p.y, sym["x"], sym["y"], sym["rot"])
    effective_angle = (p.angle + sym["rot"]) % 360
    if effective_angle == 0:
        ex, ey = px + length, py
    elif effective_angle == 90:
        ex, ey = px, py - length
    elif effective_angle == 180:
        ex, ey = px - length, py
    else:  # 270
        ex, ey = px, py + length
    sch.add_wire(px, py, ex, ey)
    return (ex, ey)


def nc(ref, pnum):
    px, py = pin_at(ref, pnum)
    sch.add_noconnect(px, py)


# =====================================================================
# SECTION 1: POWER CHAIN
# =====================================================================
sch.add_text("POWER CHAIN — Solar + Supercap + TPS7A02 LDO", 35, 25, 2.5)

# --- J_SOLAR ---
sch.add_symbol(
    "Connector_Generic:Conn_01x02_Pin", "J_SOLAR", "Solar Panel",
    "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
    "~", 40, 40, 0
)
ex, ey = stub("J_SOLAR", "1")
sch.add_label("SOLAR_IN", ex - 5.08, ey, 0)
ex, ey = stub("J_SOLAR", "2")
sch.add_power("GND", ex - 5.08, ey, 0)
sch.add_wire(ex, ey, ex - 5.08, ey)

# --- D1 BAT54 Schottky (rot=180 so K on right) ---
sch.add_symbol("Device:D_Schottky", "D1", "BAT54", "Diode_SMD:D_SOD-123", "~", 65, 40, 180)
ex, ey = stub("D1", "2")  # Anode is the LEFT-facing pin after 180 rotation = pin 2 (A)
sch.add_label("SOLAR_IN", ex - 5.08, ey, 0)
sch.add_wire(ex, ey, ex - 5.08, ey)
ex, ey = stub("D1", "1")  # Cathode on right
sch.add_label("VBAT", ex + 5.08, ey, 0)
sch.add_wire(ex, ey, ex + 5.08, ey)

# --- SC1 supercap ---
sch.add_symbol("balloon_symbols:SuperCap_1F_5V5", "SC1", "1F 5.5V",
              "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", "~", 85, 55, 0)
ex, ey = stub("SC1", "1", 8)
sch.add_label("VBAT", ex, ey, 0)
ex, ey = stub("SC1", "2", 5)
sch.add_power("GND", ex, ey, 0)

# --- C1 10uF LDO input ---
sch.add_symbol("Device:C", "C1", "10uF", "Capacitor_SMD:C_0603_1608Metric", "~", 100, 50, 0)
ex, ey = stub("C1", "1", 5.08)
sch.add_label("VBAT", ex, ey, 0)
ex, ey = stub("C1", "2", 5)
sch.add_power("GND", ex, ey, 0)

# --- U5 TPS7A0233PDBVR LDO ---
sch.add_symbol("balloon_symbols:TPS7A0233PDBVR", "U5", "TPS7A0233PDBVR",
              "Package_TO_SOT_SMD:SOT-23-5", "~", 122, 55, 0)
ex, ey = stub("U5", "1", 5)
sch.add_label("VBAT", ex, ey, 0)
ex, ey = stub("U5", "2", 5)
sch.add_power("GND", ex, ey, 0)
ex, ey = stub("U5", "3", 5)
sch.add_label("VBAT", ex, ey, 0)  # EN pulled to VBAT (always-on)
ex, ey = stub("U5", "4", 5)
sch.add_label("3V3", ex, ey, 0)
nc("U5", "5")

# --- C2 10uF LDO output ---
sch.add_symbol("Device:C", "C2", "10uF", "Capacitor_SMD:C_0603_1608Metric", "~", 145, 50, 0)
ex, ey = stub("C2", "1", 5.08)
sch.add_label("3V3", ex, ey, 0)
ex, ey = stub("C2", "2", 5)
sch.add_power("GND", ex, ey, 0)

# --- Voltage divider ---
sch.add_symbol("Device:R", "R_DIV1", "100k", "Resistor_SMD:R_0402_1005Metric", "~", 95, 80, 0)
ex, ey = stub("R_DIV1", "1", 5.08)
sch.add_label("VBAT", ex, ey, 0)
ex1, ey1 = stub("R_DIV1", "2", 5)

# VDIV_MID tap point
vdiv_y = ey1 + 3
sch.add_wire(ex1, ey1, 95, vdiv_y)
sch.add_junction(95, vdiv_y)
sch.add_wire(95, vdiv_y, 88, vdiv_y)
sch.add_label("VDIV_MID", 88, vdiv_y, 0)

sch.add_symbol("Device:R", "R_DIV2", "100k", "Resistor_SMD:R_0402_1005Metric", "~", 95, vdiv_y + 8.81, 0)
# R_DIV2 pin 1 connects up to VDIV_MID junction
r2_top_x, r2_top_y = pin_at("R_DIV2", "1")
sch.add_wire(95, vdiv_y, 95, r2_top_y)
ex, ey = stub("R_DIV2", "2", 5)
sch.add_power("GND", ex, ey, 0)

# =====================================================================
# SECTION 2: ESP32-C3 (U1) — App MCU
# =====================================================================
sch.add_text("ESP32-C3 App MCU (U1)", 175, 30, 2.5)

sch.add_symbol("RF_Module:ESP32-C3-WROOM-02", "U1", "ESP32-C3-WROOM-02",
              "RF_Module:ESP32-C3-WROOM-02", "~", 180, 65, 0)

# 3V3 (pin 1, top)
ex, ey = stub("U1", "1", 5)
sch.add_label("3V3", ex, ey, 0)

# GND pins 9 and 19 (bottom)
ex, ey = stub("U1", "9", 5)
sch.add_power("GND", ex, ey, 0)
ex, ey = stub("U1", "19", 5)
sch.add_power("GND", ex, ey, 0)

# EN — pulled up via 10k external + button to GND from J1 → use net C3_EN
ex, ey = stub("U1", "2", 5)
sch.add_label("C3_EN", ex, ey, 0)

# IO0 (pin 18) — VDIV_MID
ex, ey = stub("U1", "18", 5)
sch.add_label("VDIV_MID", ex, ey, 0)

# IO1 (pin 17) — GPS_RX
ex, ey = stub("U1", "17", 5)
sch.add_label("GPS_RX", ex, ey, 0)

# IO2..IO10 (excluding IO9): unused
for pnum in ["16", "15", "3", "4", "5", "6", "7"]:
    nc("U1", pnum)

# IO9 (pin 8) — STATUS_LED + BOOT strapping. Combine into a single label
# (Boot button on J1 also pulls this to GND via R_BOOT_C3 to make BOOT mode accessible)
ex, ey = stub("U1", "8", 5)
sch.add_label("STATUS_LED", ex, ey, 0)

# IO10 (pin 10) — unused
nc("U1", "10")

# IO18 (pin 13) — UART_C3_TX (to RP2040)
ex, ey = stub("U1", "13", 5)
sch.add_label("UART_C3_TX", ex, ey, 0)

# IO19 (pin 14) — UART_C3_RX (from RP2040)
ex, ey = stub("U1", "14", 5)
sch.add_label("UART_C3_RX", ex, ey, 0)

# IO20/RXD (pin 11) — I2C_SDA
ex, ey = stub("U1", "11", 5)
sch.add_label("I2C_SDA", ex, ey, 0)

# IO21/TXD (pin 12) — I2C_SCL
ex, ey = stub("U1", "12", 5)
sch.add_label("I2C_SCL", ex, ey, 0)

# EN pull-up resistor (10k to 3V3) — required so C3_EN doesn't float
sch.add_symbol("Device:R", "R_EN", "10k", "Resistor_SMD:R_0402_1005Metric", "~", 160, 35, 0)
ex, ey = stub("R_EN", "1", 5.08)
sch.add_label("3V3", ex, ey, 0)
ex, ey = stub("R_EN", "2", 5)
sch.add_label("C3_EN", ex, ey, 0)

# C3, C4 — decoupling for U1
sch.add_symbol("Device:C", "C3", "100nF", "Capacitor_SMD:C_0402_1005Metric", "~", 200, 40, 0)
ex, ey = stub("C3", "1", 5.08)
sch.add_label("3V3", ex, ey, 0)
ex, ey = stub("C3", "2", 5)
sch.add_power("GND", ex, ey, 0)

sch.add_symbol("Device:C", "C4", "100nF", "Capacitor_SMD:C_0402_1005Metric", "~", 210, 40, 0)
ex, ey = stub("C4", "1", 5.08)
sch.add_label("3V3", ex, ey, 0)
ex, ey = stub("C4", "2", 5)
sch.add_power("GND", ex, ey, 0)

# --- Status LED: STATUS_LED → R_LED → LED_ANODE → LED1 → GND ---
sch.add_text("Status LED", 215, 110, 1.5)
sch.add_symbol("Device:R", "R_LED", "330R", "Resistor_SMD:R_0402_1005Metric", "~", 220, 115, 0)
ex, ey = stub("R_LED", "1", 5)
sch.add_label("STATUS_LED", ex, ey, 0)
ex_r2, ey_r2 = stub("R_LED", "2", 5)

# LED1 (rotate 180 so anode is on top, cathode on bottom)
sch.add_symbol("Device:LED", "LED1", "LED_0603", "LED_SMD:LED_0603_1608Metric", "~", 220, ey_r2 + 11.43, 180)
led_top_x, led_top_y = pin_at("LED1", "2")  # after 180 rotation, pin 2 (A) is on TOP
led_bot_x, led_bot_y = pin_at("LED1", "1")  # pin 1 (K) is on BOTTOM
sch.add_wire(ex_r2, ey_r2, led_top_x, led_top_y)
ex, ey = stub("LED1", "1", 5)
sch.add_power("GND", ex, ey, 0)


# =====================================================================
# SECTION 3: RP2040 (U2) — Radio MCU
# =====================================================================
sch.add_text("RP2040 Radio MCU (U2)", 270, 35, 2.5)

sch.add_symbol("MCU_RaspberryPi:RP2040", "U2", "RP2040",
              "Package_DFN_QFN:QFN-56-1EP_7x7mm_P0.4mm", "~", 275, 115, 0)

# Pin map (RP2040 symbol):
# TOP (angle=270, pointing up): IOVDD (1,10,22,33,49), DVDD (23,50), USB_VDD(48), ADC_AVDD(43), VREG_VIN(44), VREG_VOUT(45)
# BOTTOM (angle=90): GND (57, central EP)
# LEFT side (angle=0): TESTEN(19), RUN(26), SWCLK(24), SWDIO(25), USB_DM(46), USB_DP(47),
#                       QSPI_SD0..3 (53,55,54,51), QSPI_SCLK(52), ~QSPI_SS(56), XIN(20), XOUT(21)
# RIGHT side (angle=180): GPIO0..GPIO29 in order

# ---- Power pins ----
# IOVDD, USB_VDD, ADC_AVDD, VREG_VIN — all 3V3
# DVDD — comes from VREG_VOUT (internal 1.1V regulator output, but we tie decoupling cap)
# VREG_VOUT — needs 1uF to GND (per RP2040 datasheet)

for pnum in ["1", "10", "22", "33", "49"]:  # IOVDD
    ex, ey = stub("U2", pnum, 3)
    sch.add_label("3V3", ex, ey, 0)
ex, ey = stub("U2", "48", 3)
sch.add_label("3V3", ex, ey, 0)
ex, ey = stub("U2", "43", 3)
sch.add_label("3V3", ex, ey, 0)
ex, ey = stub("U2", "44", 3)
sch.add_label("3V3", ex, ey, 0)

# VREG_VOUT → 1uF to GND
ex, ey = stub("U2", "45", 3)
sch.add_label("VREG_VOUT", ex, ey, 0)

# DVDD pins — connect to VREG_VOUT is NOT standard; RP2040 datasheet:
# DVDD is supplied from internal regulator. Each DVDD pin needs 100nF to GND.
# Connect them to 1V1 net (per datasheet reference design: VREG_VOUT → DVDD via ferrite or direct)
# For simplicity: label "1V1" for both
for pnum in ["23", "50"]:
    ex, ey = stub("U2", pnum, 3)
    sch.add_label("1V1", ex, ey, 0)

# GND EP
ex, ey = stub("U2", "57", 5)
sch.add_power("GND", ex, ey, 0)

# ---- Right-side GPIO: SPI + control ----
# RP2040 SPI0 default pins: GPIO16=RX(MISO), GPIO17=CSn, GPIO18=SCK, GPIO19=TX(MOSI)
ex, ey = stub("U2", "27", 5)
sch.add_label("SPI_MISO", ex, ey, 0)
ex, ey = stub("U2", "28", 5)
sch.add_label("SPI_NSS", ex, ey, 0)
ex, ey = stub("U2", "29", 5)
sch.add_label("SPI_SCK", ex, ey, 0)
ex, ey = stub("U2", "30", 5)
sch.add_label("SPI_MOSI", ex, ey, 0)

# Control lines: GPIO20=BUSY, GPIO21=RST, GPIO22=DIO9
ex, ey = stub("U2", "31", 5)
sch.add_label("LR2021_BUSY", ex, ey, 0)
ex, ey = stub("U2", "32", 5)
sch.add_label("LR2021_RST", ex, ey, 0)
ex, ey = stub("U2", "34", 5)
sch.add_label("LR2021_DIO9", ex, ey, 0)

# UART0: GPIO0=TX, GPIO1=RX (to C3)
ex, ey = stub("U2", "2", 5)
sch.add_label("UART_C3_RX", ex, ey, 0)  # RP2040 TX = C3 RX
ex, ey = stub("U2", "3", 5)
sch.add_label("UART_C3_TX", ex, ey, 0)  # RP2040 RX = C3 TX

# Unused right-side GPIOs (GPIO2..15, GPIO23..29)
unused_right = [4,5,6,7,8,9,10,11,12,13,14,15,16,17,18, 35,36,37,38,39,40,41,42]
for pnum in unused_right:
    if str(pnum) in GLIB.libs["RP2040"].pins:
        nc("U2", str(pnum))

# ---- Left side pins ----
# SWCLK, SWDIO — to debug header J2
ex, ey = stub("U2", "24", 5)
sch.add_label("RP_SWCLK", ex, ey, 0)
ex, ey = stub("U2", "25", 5)
sch.add_label("RP_SWDIO", ex, ey, 0)

# RUN — reset (pull-up + button to GND, simplified: tie to 3V3 via label)
ex, ey = stub("U2", "26", 5)
sch.add_label("3V3", ex, ey, 0)

# TESTEN — NC
nc("U2", "19")

# USB_DM, USB_DP — NC for now (could route to USB-C later)
nc("U2", "46")
nc("U2", "47")

# QSPI pins — plan uses RP2040-Zero approach (external flash via QSPI), but flash chip is
# not in scope for this variant drawing. QSPI_SS gets BOOTSEL pull-down; other QSPI pins
# marked NC (will be flagged in ERC review).
ex, ey = stub("U2", "56", 5)
sch.add_label("RP_QSPI_SS", ex, ey, 0)
for pnum in ["51", "52", "53", "54", "55"]:
    nc("U2", pnum)

# XIN, XOUT — external crystal optional; plan says "internal ROSC acceptable"
# For ERC: leave NC
nc("U2", "20")
nc("U2", "21")

# ---- Decoupling caps RP2040 ----
sch.add_symbol("Device:C", "C5", "100nF", "Capacitor_SMD:C_0402_1005Metric", "~", 245, 60, 0)
ex, ey = stub("C5", "1", 5.08)
sch.add_label("3V3", ex, ey, 0)
ex, ey = stub("C5", "2", 5)
sch.add_power("GND", ex, ey, 0)

sch.add_symbol("Device:C", "C6", "100nF", "Capacitor_SMD:C_0402_1005Metric", "~", 245, 80, 0)
ex, ey = stub("C6", "1", 5.08)
sch.add_label("3V3", ex, ey, 0)
ex, ey = stub("C6", "2", 5)
sch.add_power("GND", ex, ey, 0)

# VREG_VOUT filter cap (1uF, per RP2040 datasheet)
sch.add_symbol("Device:C", "C_VREG", "1uF", "Capacitor_SMD:C_0402_1005Metric", "~", 285, 60, 0)
ex, ey = stub("C_VREG", "1", 5.08)
sch.add_label("VREG_VOUT", ex, ey, 0)
ex, ey = stub("C_VREG", "2", 5)
sch.add_power("GND", ex, ey, 0)

# 1V1 decoupling cap
sch.add_symbol("Device:C", "C_DVDD", "100nF", "Capacitor_SMD:C_0402_1005Metric", "~", 295, 60, 0)
ex, ey = stub("C_DVDD", "1", 5.08)
sch.add_label("1V1", ex, ey, 0)
ex, ey = stub("C_DVDD", "2", 5)
sch.add_power("GND", ex, ey, 0)

# BOOTSEL pull-down (10k from ~QSPI_SS to GND for normal boot)
sch.add_symbol("Device:R", "R_BOOT", "10k", "Resistor_SMD:R_0402_1005Metric", "~", 245, 130, 0)
ex, ey = stub("R_BOOT", "1", 5.08)
# Wire to U2 pin 56 (~QSPI_SS)
u2_qs_x, u2_qs_y = pin_at("U2", "56")
# Draw wire connecting R_BOOT.1 net to U2.56 net via label
sch.add_label("RP_QSPI_SS", ex, ey, 0)
ex, ey = stub("R_BOOT", "2", 5)
sch.add_power("GND", ex, ey, 0)


# =====================================================================
# SECTION 4: LR2021 (U3) — Radio module
# =====================================================================
sch.add_text("LR2021F33 Radio (U3)", 360, 35, 2.5)

sch.add_symbol("balloon_symbols:LR2021F33", "U3", "LR2021F33",
              "RF_Module:NiceRF_LoRa2021F33", "~", 375, 70, 0)

# Pin 1: 3V3
ex, ey = stub("U3", "1", 5)
sch.add_label("3V3", ex, ey, 0)
# Pin 2: GND
ex, ey = stub("U3", "2", 5)
sch.add_power("GND", ex, ey, 0)
# Pin 3: MISO
ex, ey = stub("U3", "3", 5)
sch.add_label("SPI_MISO", ex, ey, 0)
# Pin 4: MOSI
ex, ey = stub("U3", "4", 5)
sch.add_label("SPI_MOSI", ex, ey, 0)
# Pin 5: SCK
ex, ey = stub("U3", "5", 5)
sch.add_label("SPI_SCK", ex, ey, 0)
# Pin 6: NSS
ex, ey = stub("U3", "6", 5)
sch.add_label("SPI_NSS", ex, ey, 0)
# Pin 7: BUSY
ex, ey = stub("U3", "7", 5)
sch.add_label("LR2021_BUSY", ex, ey, 0)
# Pin 8: GND
ex, ey = stub("U3", "8", 5)
sch.add_power("GND", ex, ey, 0)
# Pin 9: RF_SUB
ex, ey = stub("U3", "9", 5)
sch.add_label("RF_SUB_868", ex, ey, 0)

# Right side
# Pin 10: GND
ex, ey = stub("U3", "10", 5)
sch.add_power("GND", ex, ey, 0)
# Pin 11: GND
ex, ey = stub("U3", "11", 5)
sch.add_power("GND", ex, ey, 0)
# Pin 12: NC
nc("U3", "12")
# Pin 13: DIO9
ex, ey = stub("U3", "13", 5)
sch.add_label("LR2021_DIO9", ex, ey, 0)
# Pin 14: RST
ex, ey = stub("U3", "14", 5)
sch.add_label("LR2021_RST", ex, ey, 0)
# Pin 15: NC
nc("U3", "15")
# Pin 16: GND
ex, ey = stub("U3", "16", 5)
sch.add_power("GND", ex, ey, 0)
# Pin 17: GND
ex, ey = stub("U3", "17", 5)
sch.add_power("GND", ex, ey, 0)
# Pin 18: RF_2G4
ex, ey = stub("U3", "18", 5)
sch.add_label("RF_2G4_2400", ex, ey, 0)

# SPI MISO pull-down (R_PD = 10k to GND)
sch.add_symbol("Device:R", "R_PD", "10k", "Resistor_SMD:R_0402_1005Metric", "~", 360, 95, 0)
ex, ey = stub("R_PD", "1", 5.08)
sch.add_label("SPI_MISO", ex, ey, 0)
ex, ey = stub("R_PD", "2", 5)
sch.add_power("GND", ex, ey, 0)

# C7 — LR2021 decoupling
sch.add_symbol("Device:C", "C7", "100nF", "Capacitor_SMD:C_0402_1005Metric", "~", 400, 50, 0)
ex, ey = stub("C7", "1", 5.08)
sch.add_label("3V3", ex, ey, 0)
ex, ey = stub("C7", "2", 5)
sch.add_power("GND", ex, ey, 0)

# Antenna connectors (U.FL)
sch.add_symbol("Connector:Conn_Coaxial", "ANT1", "U.FL_Sub-GHz",
              "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110", "~", 400, 90, 0)
ex, ey = stub("ANT1", "1", 5)
sch.add_label("RF_SUB_868", ex, ey, 0)
# Conn_Coaxial has 2 pins: signal + shield
pin_list = list(symbol_lib_lookup_global("Connector:Conn_Coaxial").pins.keys())
print(f"Conn_Coaxial pins: {pin_list}")
if "2" in pin_list:
    ex, ey = stub("ANT1", "2", 5)
    sch.add_power("GND", ex, ey, 0)

sch.add_symbol("Connector:Conn_Coaxial", "ANT2", "U.FL_2.4GHz",
              "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110", "~", 400, 110, 0)
ex, ey = stub("ANT2", "1", 5)
sch.add_label("RF_2G4_2400", ex, ey, 0)
if "2" in pin_list:
    ex, ey = stub("ANT2", "2", 5)
    sch.add_power("GND", ex, ey, 0)


# =====================================================================
# SECTION 5: MAX-M10S GPS (U4)
# =====================================================================
sch.add_text("MAX-M10S GPS (U4)", 155, 170, 2.5)

sch.add_symbol("RF_GPS:MAX-M10S", "U4", "MAX-M10S",
              "RF_GPS:u-blox_MAX-M10", "~", 175, 195, 0)

# Pin 1 GND
ex, ey = stub("U4", "1", 5)
sch.add_power("GND", ex, ey, 0)
# Pin 2 TXD → GPS_RX (to C3 GPIO1)
ex, ey = stub("U4", "2", 5)
sch.add_label("GPS_RX", ex, ey, 0)
# Pin 3 RXD — NC (plan: not used)
nc("U4", "3")
# Pin 4 TIMEPULSE — NC
nc("U4", "4")
# Pin 5 EXTINT — NC
nc("U4", "5")
# Pin 6 V_BCKP — tie to 3V3
ex, ey = stub("U4", "6", 5)
sch.add_label("3V3", ex, ey, 0)
# Pin 7 VCC_IO — 3V3
ex, ey = stub("U4", "7", 5)
sch.add_label("3V3", ex, ey, 0)
# Pin 8 VCC — 3V3
ex, ey = stub("U4", "8", 5)
sch.add_label("3V3", ex, ey, 0)
# Pin 9 ~RESET — pull up via 10k (or tie to 3V3)
ex, ey = stub("U4", "9", 5)
sch.add_label("3V3", ex, ey, 0)
# Pins 10, 12 GND
for pnum in ["10", "12"]:
    ex, ey = stub("U4", pnum, 5)
    sch.add_power("GND", ex, ey, 0)
# Pin 11 RF_IN — to antenna
ex, ey = stub("U4", "11", 5)
sch.add_label("RF_GPS_IN", ex, ey, 0)
# Pin 13 LNA_EN — 3V3 (LNA always on for passive antenna config)
ex, ey = stub("U4", "13", 5)
sch.add_label("3V3", ex, ey, 0)
# Pin 14 VCC_RF — 3V3
ex, ey = stub("U4", "14", 5)
sch.add_label("3V3", ex, ey, 0)
# Pin 15 VIO_SEL — GND (use VCC_IO for IO levels)
ex, ey = stub("U4", "15", 5)
sch.add_power("GND", ex, ey, 0)
# Pin 16 SDA — NC (no I2C config)
nc("U4", "16")
# Pin 17 SCL — NC
nc("U4", "17")
# Pin 18 ~SAFEBOOT — pull up to 3V3
ex, ey = stub("U4", "18", 5)
sch.add_label("3V3", ex, ey, 0)

# GPS antenna connector
sch.add_symbol("Connector:Conn_Coaxial", "ANT3", "U.FL_GPS",
              "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110", "~", 220, 195, 0)
ex, ey = stub("ANT3", "1", 5)
sch.add_label("RF_GPS_IN", ex, ey, 0)
if "2" in pin_list:
    ex, ey = stub("ANT3", "2", 5)
    sch.add_power("GND", ex, ey, 0)

# GPS decoupling cap
sch.add_symbol("Device:C", "C8", "100nF", "Capacitor_SMD:C_0402_1005Metric", "~", 175, 220, 0)
ex, ey = stub("C8", "1", 5.08)
sch.add_label("3V3", ex, ey, 0)
ex, ey = stub("C8", "2", 5)
sch.add_power("GND", ex, ey, 0)


# =====================================================================
# SECTION 6: BMP280 (U6) — I2C sensor
# =====================================================================
sch.add_text("BMP280 Pressure Sensor (U6)", 240, 170, 2.5)

# Use 4-pin breakout-style connector for BMP280 (like existing hub_board_diy pattern) —
# plan says BMP280 is on a module/breakout. Use Sensor_Pressure:BMP280 symbol directly.
sch.add_symbol("Sensor_Pressure:BMP280", "U6", "BMP280",
              "Package_LGA:Bosch_LGA-8_2.5x2.0mm_P0.65mm", "~", 260, 195, 0)

# BMP280 pins (typical):
# 1=GND, 2=CSB, 3=SDA, 4=SDO, 5=SCL, 6=SDI, 7=VDDIO, 8=VDD
bmp_sym = GLIB.libs["BMP280"]
print("BMP280 pins:")
for pn, p in sorted(bmp_sym.pins.items()):
    print(f"  {pn}: {p.name}")

# Wire after we see actual pinout
for pnum, p in bmp_sym.pins.items():
    name = p.name
    ex, ey = stub("U6", pnum, 5)
    if "VDD" in name or "VDDIO" in name:
        sch.add_label("3V3", ex, ey, 0)
    elif "GND" in name:
        sch.add_power("GND", ex, ey, 0)
    elif name == "SDA" or name == "SDDI" or name == "SDI":
        sch.add_label("I2C_SDA", ex, ey, 0)
    elif name == "SCL" or name == "SCK":
        sch.add_label("I2C_SCL", ex, ey, 0)
    else:
        # CSB, SDO, etc — leave NC or pull-up appropriately
        if name == "CSB":
            sch.add_label("3V3", ex, ey, 0)  # CSB pulled high for I2C mode
        elif name == "SDO":
            sch.add_power("GND", ex, ey, 0)  # SDO pulled low -> I2C addr 0x76
        else:
            sch.add_noconnect(ex, ey)

# I2C pull-ups
sch.add_symbol("Device:R", "R_SDA", "4.7k", "Resistor_SMD:R_0402_1005Metric", "~", 240, 220, 0)
ex, ey = stub("R_SDA", "1", 5.08)
sch.add_label("3V3", ex, ey, 0)
ex, ey = stub("R_SDA", "2", 5)
sch.add_label("I2C_SDA", ex, ey, 0)

sch.add_symbol("Device:R", "R_SCL", "4.7k", "Resistor_SMD:R_0402_1005Metric", "~", 250, 220, 0)
ex, ey = stub("R_SCL", "1", 5.08)
sch.add_label("3V3", ex, ey, 0)
ex, ey = stub("R_SCL", "2", 5)
sch.add_label("I2C_SCL", ex, ey, 0)

# BMP280 decoupling
sch.add_symbol("Device:C", "C9", "100nF", "Capacitor_SMD:C_0402_1005Metric", "~", 275, 220, 0)
ex, ey = stub("C9", "1", 5.08)
sch.add_label("3V3", ex, ey, 0)
ex, ey = stub("C9", "2", 5)
sch.add_power("GND", ex, ey, 0)


# =====================================================================
# SECTION 7: Programming headers
# =====================================================================
sch.add_text("Programming Headers", 320, 170, 2.5)

# J1 — C3 programming (6-pin: 3V3, GND, EN, IO9[BOOT], TXD0, RXD0)
# NOTE: ESP32-C3 UART0 is on dedicated U0TXD/U0RXD pins which are NOT exposed as GPIO on the WROOM-02 module
# In WROOM-02, U0RXD=GPIO20, U0TXD=GPIO21 (the same pins we use for I2C). That conflicts.
# For programming header, expose 3V3, GND, EN, IO9(BOOT). User can program via USB-on-chip.
# Actually on ESP32-C3 the ROM bootloader uses GPIO20/21 (U0RXD/U0TXD) OR USB-CDC (GPIO18/19).
# Since we use GPIO20/21 as I2C, programming will use USB-CDC or SWD/JTAG.
# For J1, expose: 3V3, GND, EN, IO9, IO18(USB-D-), IO19(USB-D+) — USB programming
sch.add_symbol("Connector_Generic:Conn_01x06_Pin", "J1", "C3 USB Prog",
              "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical",
              "~", 325, 195, 0)
# Pin 1=3V3, 2=GND, 3=EN, 4=IO9(BOOT), 5=IO18(USB-D-), 6=IO19(USB-D+)
ex, ey = stub("J1", "1", 5)
sch.add_label("3V3", ex, ey, 0)
ex, ey = stub("J1", "2", 5)
sch.add_power("GND", ex, ey, 0)
ex, ey = stub("J1", "3", 5)
sch.add_label("C3_EN", ex, ey, 0)
ex, ey = stub("J1", "4", 5)
sch.add_label("STATUS_LED", ex, ey, 0)  # IO9/BOOT shared net
# Pins 5,6 of J1 — could be spare UART or USB. Per plan (Variant 3), GPIO18/19 on C3 are
# consumed by the inter-MCU UART bridge. Expose them as test points here.
ex, ey = stub("J1", "5", 5)
sch.add_label("UART_C3_TX", ex, ey, 0)
ex, ey = stub("J1", "6", 5)
sch.add_label("UART_C3_RX", ex, ey, 0)

# J2 — RP2040 SWD programming (4-pin: 3V3, GND, SWCLK, SWDIO)
sch.add_symbol("Connector_Generic:Conn_01x04_Pin", "J2", "RP2040 SWD",
              "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
              "~", 355, 195, 0)
ex, ey = stub("J2", "1", 5)
sch.add_label("3V3", ex, ey, 0)
ex, ey = stub("J2", "2", 5)
sch.add_power("GND", ex, ey, 0)
ex, ey = stub("J2", "3", 5)
sch.add_label("RP_SWCLK", ex, ey, 0)
ex, ey = stub("J2", "4", 5)
sch.add_label("RP_SWDIO", ex, ey, 0)


# =====================================================================
# Output
# =====================================================================
out_path = "/home/c03rad0r/repos/balloon-fresh/tracker/hardware/schematics/v_c3_rp2040/v_c3_rp2040.kicad_sch"
with open(out_path, "w") as f:
    f.write(sch.emit())

print(f"\nWrote {out_path}")
print(f"Symbols: {len(sch.symbols)}, wires: {len(sch.wires)}, labels: {len(sch.labels)}, junctions: {len(sch.junctions)}, powers: {len(sch.powers)}, NCs: {len(sch.noconnects)}")
