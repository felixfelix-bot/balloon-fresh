"""
Hub Board Schematic - ESP32-C3 + LR2021 + GPS + Power
Central electronics board for pico balloon tracker.

Uses validated pin mapping from DIY v0.1 soldering setup.
Connector-based approach: dev board modules as connectors, custom inline parts for ICs.

Generates KiCad netlist via SKiDL.
Run: python hub_schematic.py
Output: hub_board.net (import into KiCad for layout)
"""

import os
os.environ['KICAD9_SYMBOL_DIR'] = '/usr/share/kicad/symbols'
os.environ['KICAD_SYMBOL_DIR'] = '/usr/share/kicad/symbols'

from skidl import *

# ============================================================
# Custom Part Templates (for parts not in KiCad v9 libraries)
# ============================================================

def make_tps7a02():
    """TPS7A0233DBVR LDO - 3.3V, SOT-23-5, custom inline part."""
    p = Part(name='TPS7A0233DBVR', tool='skidl', dest=TEMPLATE,
             ref_prefix='U', footprint='Package_TO_SOT_SMD:SOT-23-5')
    p += Pin(num='1', name='IN',   func=Pin.types.PWRIN)
    p += Pin(num='2', name='GND',  func=Pin.types.PWRIN)
    p += Pin(num='3', name='EN',   func=Pin.types.INPUT)
    p += Pin(num='4', name='NC',   func=Pin.types.NOCONNECT)
    p += Pin(num='5', name='OUT',  func=Pin.types.PWROUT)
    return p()

def make_bat54():
    """BAT54 Schottky diode - 2-pin SOD-123, custom inline part."""
    p = Part(name='BAT54', tool='skidl', dest=TEMPLATE,
             ref_prefix='D', footprint='Diode_SMD:D_SOD-123')
    p += Pin(num='1', name='A', func=Pin.types.PASSIVE)
    p += Pin(num='2', name='K', func=Pin.types.PASSIVE)
    return p()

# ============================================================
# Schematic: Hub Board V0.1
# ============================================================

def generate_hub_schematic():
    # --- Components ---

    # U1: ESP32-C3_Mini_V1 dev board (16-pin 2x8 header)
    # Pin mapping: top row = left side of dev board, bottom row = right side
    # Conn_02x08_Odd_Even: pins 1-8 top (left), 9-16 bottom (right)
    mcu = Part("Connector_Generic", "Conn_02x08_Odd_Even", ref="U",
               value="ESP32-C3_Mini_V1",
               footprint="Connector_PinHeader_2.54mm:PinHeader_2x08_P2.54mm_Vertical")

    # U2: NiceRF LoRa2021 (18-pin castellated module)
    # Use two Conn_01x09 to represent 18 pins (left side + right side)
    lora_l = Part("Connector_Generic", "Conn_01x09", ref="U",
                  value="LoRa2021_Left",
                  footprint="Connector_PinHeader_2.54mm:PinHeader_1x09_P2.54mm_Vertical")
    lora_r = Part("Connector_Generic", "Conn_01x09", ref="U",
                  value="LoRa2021_Right",
                  footprint="Connector_PinHeader_2.54mm:PinHeader_1x09_P2.54mm_Vertical")

    # U3: MAX-M10S GPS breakout (4-pin header)
    gps = Part("Connector_Generic", "Conn_01x04", ref="U",
               value="MAX-M10S",
               footprint="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical")

    # U4: TPS7A02 LDO (custom)
    ldo = make_tps7a02()

    # D1: BAT54 Schottky diode (custom)
    diode = make_bat54()

    # Decoupling capacitors
    c1 = Part("Device", "C", ref="C", value="100nF", footprint="Capacitor_SMD:C_0402_1005Metric")  # ESP32 decouple
    c2 = Part("Device", "C", ref="C", value="100nF", footprint="Capacitor_SMD:C_0402_1005Metric")  # LoRa VCC
    c3 = Part("Device", "C", ref="C", value="100nF", footprint="Capacitor_SMD:C_0402_1005Metric")  # LoRa VTCXO
    c4 = Part("Device", "C", ref="C", value="10uF",  footprint="Capacitor_SMD:C_0402_1005Metric")  # LoRa TX burst
    c5 = Part("Device", "C", ref="C", value="100nF", footprint="Capacitor_SMD:C_0402_1005Metric")  # GPS decouple
    c6 = Part("Device", "C", ref="C", value="10uF",  footprint="Capacitor_SMD:C_0402_1005Metric")  # GPS decouple
    c7 = Part("Device", "C", ref="C", value="100nF", footprint="Capacitor_SMD:C_0402_1005Metric")  # LDO output

    # Supercapacitor
    sc1 = Part("Device", "C_Polarized", ref="SC", value="1.0F 5.5V",
               footprint="Capacitor_THT:CP_Radial_D8.0mm_P3.50mm")

    # Solder bridges for SPI pin-swap
    sb1 = Part("Jumper", "SolderJumper_2_Bridged", ref="SB",
               value="SCK",  footprint="Jumper:SolderJumper_2_Open")
    sb2 = Part("Jumper", "SolderJumper_2_Bridged", ref="SB",
               value="MOSI", footprint="Jumper:SolderJumper_2_Open")

    # Power select jumper (3-pad)
    sb3 = Part("Jumper", "SolderJumper_3_Bridged12", ref="SB",
               value="PWR_SEL", footprint="Jumper:SolderJumper_3_Open")

    # Antenna pads
    ae1 = Part("Connector_Generic", "Conn_01x01", ref="AE",
               value="SubGHz_868", footprint="TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm")
    ae2 = Part("Connector_Generic", "Conn_01x01", ref="AE",
               value="2G4_2400", footprint="TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm")

    # Debug header
    j1 = Part("Connector_Generic", "Conn_02x03_Odd_Even", ref="J",
              value="Debug", footprint="Connector_PinHeader_2.54mm:PinHeader_2x03_P2.54mm_Vertical")

    # Solar input pads
    j2 = Part("Connector_Generic", "Conn_01x02", ref="J",
              value="Solar_In", footprint="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical")

    # Voltage divider for ADC (supercap monitoring)
    r_div1 = Part("Device", "R", ref="R", value="1M", footprint="Resistor_SMD:R_0402_1005Metric")
    r_div2 = Part("Device", "R", ref="R", value="1M", footprint="Resistor_SMD:R_0402_1005Metric")

    # --- Nets ---

    # Power nets
    vcc_3v3 = Net("VCC_3V3")
    gnd = Net("GND")
    solar_in = Net("SOLAR_IN")
    vcap = Net("VCAP")       # supercap positive node
    vdiv_mid = Net("VDIV_MID")  # ADC voltage divider midpoint

    # SPI bus
    spi_mosi = Net("SPI_MOSI")
    spi_miso = Net("SPI_MISO")
    spi_sck  = Net("SPI_SCK")
    spi_cs   = Net("SPI_CS")

    # LoRa2021 control
    lora_rst  = Net("LORA_RST")
    lora_busy = Net("LORA_BUSY")
    lora_irq  = Net("LORA_IRQ")

    # UART1 (GPS)
    uart_tx = Net("UART1_TX")  # ESP TX → GPS RX
    uart_rx = Net("UART1_RX")  # ESP RX ← GPS TX

    # ADC
    adc_vcap = Net("ADC_VCAP")

    # RF antenna
    rf_subghz = Net("RF_SUBGHZ")
    rf_2g4    = Net("RF_2G4")

    # Solder bridge intermediate nets
    sb1_in  = Net("SB1_IN")   # ESP32 D6 → SB1 pad A
    sb1_out = Net("SB1_OUT")  # SB1 pad B → LoRa SCK
    sb2_in  = Net("SB2_IN")   # ESP32 D7 → SB2 pad A
    sb2_out = Net("SB2_OUT")  # SB2 pad B → LoRa MOSI

    # --- ESP32-C3_Mini_V1 pin assignments ---
    # Conn_02x08_Odd_Even: pin 1-8 = top row, 9-16 = bottom row
    # Mapping per validated DIY setup:
    #   Pin 1  = 3V3      Pin 9  = GND
    #   Pin 2  = D0/GPIO0  Pin 10 = D1/GPIO1
    #   Pin 3  = D2/GPIO2  Pin 11 = D3/GPIO3
    #   Pin 4  = D4/GPIO4  Pin 12 = D5/GPIO5
    #   Pin 5  = D6/GPIO6  Pin 13 = D7/GPIO7
    #   Pin 6  = D8/GPIO8  Pin 14 = D9/GPIO9
    #   Pin 7  = D10/GPIO10 Pin 15 = 3V3 (or NC)
    #   Pin 8  = GND       Pin 16 = GND

    # Power
    vcc_3v3 += mcu.p[1]      # 3V3
    gnd     += mcu.p[9]      # GND
    gnd     += mcu.p[8]      # GND
    gnd     += mcu.p[16]     # GND

    # UART1 (GPS)
    uart_tx += mcu.p[2]      # D0/GPIO0 = UART1_TX
    uart_rx += mcu.p[10]     # D1/GPIO1 = UART1_RX

    # SPI MISO (direct, no solder bridge)
    spi_miso += mcu.p[3]     # D2/GPIO2 = SPI_MISO

    # SPI SCK (via solder bridge SB1)
    sb1_in += mcu.p[5]       # D6/GPIO6 → SB1 input

    # SPI MOSI (via solder bridge SB2)
    sb2_in += mcu.p[13]      # D7/GPIO7 → SB2 input

    # LoRa control signals
    lora_busy += mcu.p[4]    # D4/GPIO4 = LR2021_BUSY
    lora_rst  += mcu.p[11]   # D3/GPIO3 = LR2021_RST
    lora_irq  += mcu.p[12]   # D5/GPIO5 = LR2021_IRQ (DIO9)

    # SPI CS
    spi_cs += mcu.p[7]       # D10/GPIO10 = SPI_CS

    # ADC (supercap voltage monitoring)
    adc_vcap += mcu.p[6]     # D8/GPIO8 = ADC

    # --- NiceRF LoRa2021 pin assignments ---
    # Left side (pins 1-9): Conn_01x09 pins 1-9
    #   Pin 1 = VCC        → 3V3
    #   Pin 2 = GND
    #   Pin 3 = MISO       → SPI_MISO
    #   Pin 4 = MOSI       → SB2_OUT (via solder bridge)
    #   Pin 5 = SCK        → SB1_OUT (via solder bridge)
    #   Pin 6 = NSS        → SPI_CS
    #   Pin 7 = BUSY       → LORA_BUSY
    #   Pin 8 = GND
    #   Pin 9 = ANT (Sub-GHz)
    # Right side (pins 10-18): Conn_01x09 pins 1-9
    #   Pin 10 = 2.4G antenna
    #   Pin 11 = GND
    #   Pin 12 = GND
    #   Pin 13 = NC
    #   Pin 14 = RST       → LORA_RST
    #   Pin 15 = DIO9/IRQ  → LORA_IRQ
    #   Pin 16 = DIO8      → NC
    #   Pin 17 = DIO7      → NC
    #   Pin 18 = GND

    vcc_3v3    += lora_l.p[1]   # Pin 1 = VCC
    gnd        += lora_l.p[2]   # Pin 2 = GND
    spi_miso   += lora_l.p[3]   # Pin 3 = MISO
    sb2_out    += lora_l.p[4]   # Pin 4 = MOSI (from SB2)
    sb1_out    += lora_l.p[5]   # Pin 5 = SCK (from SB1)
    spi_cs     += lora_l.p[6]   # Pin 6 = NSS
    lora_busy  += lora_l.p[7]   # Pin 7 = BUSY
    gnd        += lora_l.p[8]   # Pin 8 = GND
    rf_subghz  += lora_l.p[9]   # Pin 9 = ANT (Sub-GHz)

    rf_2g4     += lora_r.p[1]   # Pin 10 = 2.4G
    gnd        += lora_r.p[2]   # Pin 11 = GND
    gnd        += lora_r.p[3]   # Pin 12 = GND
    # Pin 13 = NC (no connection)
    lora_rst   += lora_r.p[4]   # Pin 14 = RST
    lora_irq   += lora_r.p[5]   # Pin 15 = DIO9/IRQ
    # Pin 16 = DIO8 (NC for now)
    # Pin 17 = DIO7 (NC for now)
    gnd        += lora_r.p[8]   # Pin 18 = GND

    # --- Solder bridges ---
    # SB1: ESP32 D6 ↔ LoRa SCK
    sb1_in  += sb1.p[1]     # SB1 pad A
    sb1_out += sb1.p[2]     # SB1 pad B

    # SB2: ESP32 D7 ↔ LoRa MOSI
    sb2_in  += sb2.p[1]     # SB2 pad A
    sb2_out += sb2.p[2]     # SB2 pad B

    # --- MAX-M10S GPS ---
    # Conn_01x04: pin 1=VCC, 2=GND, 3=RXD, 4=TXD
    vcc_3v3 += gps.p[1]     # VCC
    gnd     += gps.p[2]     # GND
    uart_tx += gps.p[3]     # RXD (ESP TX → GPS RX)
    uart_rx += gps.p[4]     # TXD (GPS TX → ESP RX)

    # --- Power chain ---
    # Solar input → BAT54 → supercap → TPS7A02 → 3V3
    # SB3 selects between USB 3V3 and solar power
    # SolderJumper_3_Bridged12: pins A=1, C=3, B=2 (default bridges A-C)

    solar_in += j2.p[1]     # Solar input +
    gnd      += j2.p[2]     # Solar input -

    # BAT54: solar → diode → supercap
    solar_in += diode.p[1]  # Anode
    vcap     += diode.p[2]  # Cathode (after diode, before supercap)

    # Supercap
    vcap += sc1.p[1]        # Supercap +
    gnd  += sc1.p[2]        # Supercap -

    # TPS7A02 LDO
    vcap     += ldo.p[1]    # IN (from supercap)
    gnd      += ldo.p[2]    # GND
    vcc_3v3  += ldo.p[5]    # OUT (3.3V)
    # EN tied to IN (always on when power present)
    vcap     += ldo.p[3]    # EN = IN (always enabled)
    # Pin 4 = NC

    # SB3: power select (USB vs solar)
    # Pin A = USB 3V3 (from dev board USB), Pin B = 3V3 net, Pin C = solar/LDO output
    # Default: bridge A-B (USB power)
    # Flight: bridge B-C (solar power via LDO)
    # For now, LDO output goes to SB3 pin C, USB 3V3 to pin A, 3V3 net to pin B
    vcc_3v3 += sb3.p[1]     # A = 3V3 net (output to ICs)
    # USB 3V3 would connect here in dev config — represented by leaving A-B bridged
    # Solar/LDO output connects to C
    # (In flight config, bridge B-C)

    # --- Decoupling capacitors ---
    # C1: ESP32 VCC decouple
    vcc_3v3 += c1.p[1]
    gnd     += c1.p[2]

    # C2: LoRa VCC decouple (close to Pin 1)
    vcc_3v3 += c2.p[1]
    gnd     += c2.p[2]

    # C3: LoRa VTCXO decouple
    vcc_3v3 += c3.p[1]
    gnd     += c3.p[2]

    # C4: LoRa TX burst cap (10uF)
    vcc_3v3 += c4.p[1]
    gnd     += c4.p[2]

    # C5: GPS decouple (100nF)
    vcc_3v3 += c5.p[1]
    gnd     += c5.p[2]

    # C6: GPS decouple (10uF)
    vcc_3v3 += c6.p[1]
    gnd     += c6.p[2]

    # C7: LDO output cap (100nF)
    vcc_3v3 += c7.p[1]
    gnd     += c7.p[2]

    # --- Voltage divider for ADC ---
    # VCAP ── R1(1M) ── VDIV_MID ── R2(1M) ── GND
    # ADC reads VDIV_MID = VCAP/2
    vcap     += r_div1.p[1]
    vdiv_mid += r_div1.p[2]
    vdiv_mid += r_div2.p[1]
    gnd      += r_div2.p[2]
    adc_vcap += vdiv_mid    # ADC pin reads midpoint

    # --- Antenna pads ---
    rf_subghz += ae1.p[1]   # Sub-GHz antenna pad (868 MHz, 16.4cm wire)
    rf_2g4    += ae2.p[1]   # 2.4 GHz antenna pad (3.1cm wire)

    # --- Debug header J1 ---
    # Conn_02x03: pins 1-3 top, 4-6 bottom
    # Pin 1 = 3V3, Pin 2 = GND, Pin 3 = TX, Pin 4 = RX, Pin 5 = GPIO10, Pin 6 = EN
    vcc_3v3 += j1.p[1]
    gnd     += j1.p[2]
    uart_tx += j1.p[3]
    uart_rx += j1.p[4]
    spi_cs  += j1.p[5]
    # Pin 6 = NC or EN

    # --- Generate netlist ---
    netlist_path = "hub_board.net"
    generate_netlist(filepath=netlist_path)

    # Print summary
    import skidl
    parts = list(skidl.SKIDL)
    print(f"Netlist generated: {netlist_path}")
    print(f"  Parts: {len(parts)}")

if __name__ == "__main__":
    generate_hub_schematic()