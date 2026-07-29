#!/usr/bin/env python3
"""
Hub Board Schematic — F33 2W PA Variant
=======================================
ESP32-C3 + RP2040 Coprocessor + NiceRF LoRa2021F33-2G4 (2W PA) + GPS + MS5611

This is the 2W amplifier variant of the hub board. The F33 module has a
built-in 2W PA + LNA, runs on 5V VCC, and has TWO SMA antenna connectors
(sub-GHz + 2.4GHz). Felix wants BOTH boards (non-PA + F33 PA) orderable
from JLCPCB.

ARCHITECTURE DECISION (why two MCUs on a pico-balloon board)
------------------------------------------------------------

Same dual-MCU architecture as the non-PA variant:

  1. **ESP32-C3-MINI-1** — application processor / logger.
     Runs the full stack: GPS NMEA parsing, MS5611 baro reads, supercap
     power management, telemetry framing, and the inter-MCU UART link.

  2. **RP2040-Zero** (Waveshare castellated board) — dedicated radio
     coprocessor.  Owns the F33 SPI bus exclusively.  Dual Cortex-M0+
     cores, hardware SPI0, single UART pair to the ESP32.

  3. **NiceRF LoRa2021F33-2G4** — dual-band radio with BUILT-IN 2W PA.
     Sub-GHz (433/868/915 MHz) + 2.4 GHz.  18-pin castellated module,
     39 × 21 mm, 2.0 mm pitch.  Built-in TCXO 0.5ppm, PA (2W sub-GHz),
     LNA on 2.4GHz.  This is the 2W amplifier version.

  4. **MS5611** — high-altitude barometric pressure sensor (I²C).

  5. **u-blox MAX-M10S** (GEPRC GEP-M10nano breakout) — multi-GNSS GPS.

  Power chain:  Solar cells → BAT54 Schottky → 1 F / 5.5 V supercap
                → TPS7A02 LDO (25 nA IQ) → 3V3 rail (ESP, RP2040, GPS, MS5611)
                → VRAW (5V from supercap bus) → F33 VCC (2W TX needs 5V!)

KEY DIFFERENCES from hub_schematic.py (non-PA):
  1. F33 VCC uses VRAW (supercap bus, 5.4V max), NOT 3V3.
     The supercap bus is 5.4V max — well within F33's 3.0-5.5V range.
     100µF + 10µF + 100nF bulk decoupling at VCC pin for 1.2A TX bursts.
  2. F33 pin 5 (CE) needs an RP2040 GPIO (GP9) for sleep control.
     Drive HIGH or float for operation, pull LOW for <20µA sleep.
  3. SMA edge-mount bulkhead connectors instead of wire antenna pads.
     Felix wants "big tail cable" adapters for external antennas.
  4. F33 has 7 GND pins (2,3,4,6,7,8,11) — all must be grounded.
  5. No external FEM/PA chips needed — built into F33.
  6. F33 pin map is DIFFERENT from bare LR2021:
       SPI pins are on the right side (12-18), not left side (3-7).

F33 Pin Map (NiceRF LoRa2021F33-2G4 datasheet V1.1):
    Pin 1:  VCC (3.0-5.5V, USE 5V for full 2W)
    Pin 2:  GND
    Pin 3:  GND
    Pin 4:  GND
    Pin 5:  CE (LDO enable — HIGH/float=on, LOW=sleep)
    Pin 6:  GND
    Pin 7:  GND
    Pin 8:  GND
    Pin 9:  ANT (sub-GHz 433/868/915MHz, 50Ω)
    Pin 10: ANT-2G4 (2.4GHz, 50Ω)
    Pin 11: GND
    Pin 12: SCK  (SPI, 0-3.3V logic, internal level shift)
    Pin 13: NSS  (SPI CS, active low)
    Pin 14: BUSY (status output)
    Pin 15: MOSI (SPI data input)
    Pin 16: MISO (SPI data output)
    Pin 17: RESET
    Pin 18: IRQ  (multipurpose digital)

RP2040-Zero Pin Map (SPI0 to F33, SAME SPI pins proven from firmware):
    GP2  = SPI0 SCK   → F33 Pin 12
    GP3  = SPI0 MOSI  → F33 Pin 15
    GP4  = SPI0 MISO  ← F33 Pin 16
    GP5  = GPIO CS    → F33 Pin 13 (NSS)
    GP6  = GPIO input ← F33 Pin 14 (BUSY)
    GP7  = GPIO IRQ   ← F33 Pin 18 (IRQ)
    GP8  = GPIO RST   → F33 Pin 17 (RESET)
    GP9  = GPIO CE    → F33 Pin 5  (CE — NEW: sleep control)
    GP20 = UART1 TX   → ESP GPIO1 (RX)
    GP21 = UART1 RX   ← ESP GPIO0 (TX)

ESP32-C3 ↔ RP2040 UART (SAME as non-PA):
    GPIO0 (TX) → RP2040 GP21 (RX)
    GPIO1 (RX) ← RP2040 GP20 (TX)
    GPIO2 ← GPS TX

Netlist: writes ``hub_board_f33.net`` (KiCad format, import for PCB layout).

Run:
    python hub_schematic_f33.py
Output:
    hub_board_f33.net   (import into KiCad for PCB layout)
"""

import os

# KiCad symbol libraries must be on the search path BEFORE importing skidl
# so that standard parts (Device:C, Device:R, Connector_Generic:*) resolve.
_DEFAULT_SYMBOL_DIR = "/usr/share/kicad/symbols"
os.environ.setdefault("KICAD9_SYMBOL_DIR", _DEFAULT_SYMBOL_DIR)
os.environ.setdefault("KICAD_SYMBOL_DIR", _DEFAULT_SYMBOL_DIR)

from skidl import *  # noqa: E402


# ============================================================
# Custom part templates (parts not present as single symbols in
# the stock KiCad libraries are built inline with skidl).
# ============================================================

def make_tps7a02():
    """TPS7A0233DBVR — 3.3V LDO, SOT-23-5.

    IN=1, GND=2, EN=3, NC=4, OUT=5.
    """
    p = Part(name="TPS7A0233DBVR", tool=SKIDL, dest=TEMPLATE,
             ref_prefix="U", footprint="Package_TO_SOT_SMD:SOT-23-5")
    p += Pin(num="1", name="IN",  func=Pin.types.PWRIN)
    p += Pin(num="2", name="GND", func=Pin.types.PWRIN)
    p += Pin(num="3", name="EN",  func=Pin.types.INPUT)
    p += Pin(num="4", name="NC",  func=Pin.types.NOCONNECT)
    p += Pin(num="5", name="OUT", func=Pin.types.PWROUT)
    return p()


def make_bat54():
    """BAT54 Schottky diode — SOD-123. A=1 (anode), K=2 (cathode)."""
    p = Part(name="BAT54", tool=SKIDL, dest=TEMPLATE,
             ref_prefix="D", footprint="Diode_SMD:D_SOD-123")
    p += Pin(num="1", name="A", func=Pin.types.PASSIVE)
    p += Pin(num="2", name="K", func=Pin.types.PASSIVE)
    return p()


# ============================================================
# Hub Board F33 (2W PA) Schematic
# ============================================================

def generate_hub_schematic_f33():
    """Build the full F33 hub-board netlist and write hub_board_f33.net."""

    # --------------------------------------------------------
    # 1. Components
    # --------------------------------------------------------

    # --- U1: ESP32-C3-MINI-1 (castellated WiFi module) ---
    # Modelled as a 10-pin connector carrying only the signals actually used.
    # Physical module has many more castellated pads; unused pads tie to NC/GND
    # at layout time. Pin numbers below are LOGICAL (1..10) and map to the
    # GPIO numbers noted in the comments.
    esp = Part("Connector_Generic", "Conn_01x10", ref="U",
               value="ESP32-C3-MINI-1",
               footprint="RF_Module:ESP32-C3-MINI-1")

    # --- U2: RP2040-Zero (Waveshare castellated coprocessor board) ---
    # 14 used signals (added GP9 for F33 CE pin). Pin numbers are logical (1..14).
    rp2040 = Part("Connector_Generic", "Conn_01x14", ref="U",
                  value="RP2040-Zero",
                  footprint="Module:Waveshare_RP2040-Zero")

    # --- U3: NiceRF LoRa2021F33-2G4 (18-pin castellated 2W PA radio module) ---
    # Pin numbers 1..18 match the NiceRF F33 datasheet V1.1 EXACTLY.
    # This is the 2W PA variant — different pin map from the bare LR2021!
    f33 = Part("Connector_Generic", "Conn_01x18", ref="U",
               value="NiceRF-LoRa2021F33-2G4",
               footprint="custom:LoRa2021F33_2G4")

    # --- U4: u-blox MAX-M10S GPS breakout ---
    # 1=VCC, 2=GND, 3=TX→ESP, 4=RX (NC for telemetry-only firmware)
    gps = Part("Connector_Generic", "Conn_01x04", ref="U",
               value="MAX-M10S",
               footprint="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical")

    # --- U5: MS5611 high-altitude pressure sensor (I2C, 10-1200 hPa) ---
    ms5611 = Part("Connector_Generic", "Conn_01x04", ref="U",
                  value="MS5611",
                  footprint="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical")

    # --- Power supply: BAT54 Schottky + TPS7A02 LDO + supercap ---
    diode = make_bat54()                       # D1 — solar input reverse-protection
    ldo = make_tps7a02()                       # U6 — 3.3V LDO
    supercap = Part("Device", "C_Polarized", ref="SC", value="1.0F 5.5V",
                    footprint="Capacitor_THT:CP_Radial_D8.0mm_P3.50mm")

    # --- Decoupling / bulk capacitors ---
    # 3V3 rail decoupling (ESP, RP2040, GPS, MS5611)
    c_esp    = Part("Device", "C", ref="C", value="100nF",
                    footprint="Capacitor_SMD:C_0402_1005Metric")   # C1 — ESP32 decouple
    c_rp     = Part("Device", "C", ref="C", value="100nF",
                    footprint="Capacitor_SMD:C_0402_1005Metric")   # C2 — RP2040 decouple
    c_gps    = Part("Device", "C", ref="C", value="100nF",
                    footprint="Capacitor_SMD:C_0402_1005Metric")   # C3 — GPS decouple
    c_baro   = Part("Device", "C", ref="C", value="100nF",
                    footprint="Capacitor_SMD:C_0402_1005Metric")   # C4 — MS5611 decouple
    c_ldo    = Part("Device", "C", ref="C", value="10uF",
                    footprint="Capacitor_SMD:C_0805_2012Metric")   # C5 — LDO output bulk

    # F33 VCC bulk decoupling (VRAW rail, 5V — for 1.2A TX bursts!)
    # 100µF bulk + 10µF mid + 100nF high-freq at the VCC pin.
    c_f33_bulk = Part("Device", "C", ref="C", value="100uF",
                      footprint="Capacitor_SMD:C_1206_3216Metric")  # C6 — F33 VCC bulk (1.2A TX)
    c_f33_mid  = Part("Device", "C", ref="C", value="10uF",
                      footprint="Capacitor_SMD:C_0805_2012Metric")  # C7 — F33 VCC mid
    c_f33_dec  = Part("Device", "C", ref="C", value="100nF",
                      footprint="Capacitor_SMD:C_0402_1005Metric")  # C8 — F33 VCC HF decouple

    # --- I2C pull-ups (4.7k each on SDA/SCL) ---
    r_sda = Part("Device", "R", ref="R", value="4.7k",
                 footprint="Resistor_SMD:R_0402_1005Metric")       # R1
    r_scl = Part("Device", "R", ref="R", value="4.7k",
                 footprint="Resistor_SMD:R_0402_1005Metric")       # R2

    # --- Supercap voltage divider (1M/1M → ADC reads Vcap/2) ---
    r_div_hi = Part("Device", "R", ref="R", value="1M",
                    footprint="Resistor_SMD:R_0402_1005Metric")    # R3 — Vcap→mid
    r_div_lo = Part("Device", "R", ref="R", value="1M",
                    footprint="Resistor_SMD:R_0402_1005Metric")    # R4 — mid→GND

    # --- Status LED on ESP32 GPIO10 ---
    led = Part("Device", "LED", ref="D", value="STATUS",
               footprint="LED_SMD:LED_0603_1608Metric")            # D2
    r_led = Part("Device", "R", ref="R", value="330R",
                 footprint="Resistor_SMD:R_0402_1005Metric")       # R5 — LED current limit

    # --- SMA bulkhead connectors (edge-mount for "big tail cable" adapters) ---
    # Pin 1 = signal (50Ω), Pin 2 = GND (shield).
    # Felix wants external antenna cables via SMA bulkheads on both bands.
    sma_sub = Part("Connector_Generic", "Conn_01x02", ref="J",
                   value="SMA_SUB_50OHM",
                   footprint="Connector_Coax:TEConnectivity_292304-3")   # J1 — sub-GHz SMA
    sma_2g4 = Part("Connector_Generic", "Conn_01x02", ref="J",
                   value="SMA_2G4_50OHM",
                   footprint="Connector_Coax:TEConnectivity_292304-3")   # J2 — 2.4GHz SMA

    # --- Solar input pads ---
    solar_j = Part("Connector_Generic", "Conn_01x02", ref="J",
                   value="SOLAR_IN",
                   footprint="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical")

    # --- Debug test points (1mm round SMD pads for scope/logic-analyzer probes) ---
    # Placed on key nets for bring-up debugging.
    _tp_fp = "TestPoint:TestPoint_Pad_D1.0mm"   # 1mm round SMD pad
    tp_sck   = Part("Connector_Generic", "Conn_01x01", ref="TP",
                    value="TP_SPI_SCK",   footprint=_tp_fp)
    tp_mosi  = Part("Connector_Generic", "Conn_01x01", ref="TP",
                    value="TP_SPI_MOSI",  footprint=_tp_fp)
    tp_3v3   = Part("Connector_Generic", "Conn_01x01", ref="TP",
                    value="TP_VCC_3V3",   footprint=_tp_fp)
    tp_vraw  = Part("Connector_Generic", "Conn_01x01", ref="TP",
                    value="TP_VRAW_5V",   footprint=_tp_fp)
    tp_gnd   = Part("Connector_Generic", "Conn_01x01", ref="TP",
                    value="TP_GND",       footprint=_tp_fp)

    # --------------------------------------------------------
    # 2. Nets
    # --------------------------------------------------------

    # --- Power rails ---
    v3v3     = Net("3V3")        # regulated 3.3V rail — ESP, RP2040, GPS, MS5611
    vraw     = Net("VRAW")       # supercap bus (5.4V max) → F33 VCC (5V for 2W TX)
    gnd      = Net("GND")
    solar_in = Net("SOLAR_IN")   # raw solar array output
    vcap     = Net("VCAP")       # supercap node (between BAT54 and LDO input)
    vdiv_mid = Net("VDIV_MID")   # ADC voltage-divider midpoint (→ ESP32 ADC pin)

    # --- ESP32 ↔ RP2040 UART link ---
    esp_tx_rp_rx = Net("ESP_TX_RP2040_RX")  # ESP GPIO0 (TX) → RP2040 GP21 (RX)
    rp_tx_esp_rx = Net("RP2040_TX_ESP_RX")  # RP2040 GP20 (TX) → ESP GPIO1 (RX)

    # --- GPS UART (ESP RX only — one-way telemetry) ---
    gps_tx_esp_rx = Net("GPS_TX_ESP_RX")    # M10S TX → ESP GPIO2

    # --- RP2040 ↔ F33 SPI bus (SPI0) ---
    spi_sck   = Net("SPI0_SCK")    # RP2040 GP2  → F33 Pin 12
    spi_mosi  = Net("SPI0_MOSI")   # RP2040 GP3  → F33 Pin 15
    spi_miso  = Net("SPI0_MISO")   # RP2040 GP4 ← F33 Pin 16
    spi_nss   = Net("SPI0_NSS")    # RP2040 GP5  → F33 Pin 13
    f33_busy  = Net("F33_BUSY")    # RP2040 GP6 ← F33 Pin 14
    f33_irq   = Net("F33_IRQ")     # RP2040 GP7 ← F33 Pin 18
    f33_rst   = Net("F33_RST")     # RP2040 GP8  → F33 Pin 17
    f33_ce    = Net("F33_CE")      # RP2040 GP9  → F33 Pin 5 (sleep control)

    # --- I2C bus (ESP32 ↔ MS5611) ---
    i2c_sda = Net("I2C_SDA")  # ESP GPIO8
    i2c_scl = Net("I2C_SCL")  # ESP GPIO9

    # --- Status LED ---
    led_drive = Net("STATUS_LED")  # ESP GPIO10 → R5 → LED → GND

    # --- RF antennas (SMA connectors) ---
    rf_subghz = Net("RF_SUB_SMA")    # F33 ANT (pin 9) → SMA sub-GHz
    rf_2g4    = Net("RF_2G4_SMA")    # F33 ANT-2G4 (pin 10) → SMA 2.4GHz

    # --------------------------------------------------------
    # 3. Wiring
    # --------------------------------------------------------

    # --- U1: ESP32-C3-MINI-1 (logical pin map) ---
    #   1=3V3, 2=GND, 3=GPIO0(TX), 4=GPIO1(RX), 5=GPIO2(GPS RX),
    #   6=GPIO4(ADC), 7=GPIO8(SDA), 8=GPIO9(SCL), 9=GPIO10(LED), 10=EN
    v3v3          += esp["1"]      # 3V3
    gnd           += esp["2"]      # GND
    esp_tx_rp_rx  += esp["3"]      # GPIO0 = UART1 TX  → RP2040 GP21
    rp_tx_esp_rx  += esp["4"]      # GPIO1 = UART1 RX  ← RP2040 GP20
    gps_tx_esp_rx += esp["5"]      # GPIO2 = GPS UART RX ← M10S TX
    vdiv_mid      += esp["6"]      # GPIO4 = ADC1_CH4 (supercap monitor via divider)
    i2c_sda       += esp["7"]      # GPIO8 = I2C SDA
    i2c_scl       += esp["8"]      # GPIO9 = I2C SCL
    led_drive     += esp["9"]      # GPIO10 = status LED drive
    # Pin 10 = EN: leave floating (onboard RC/pullup handles boot) — NC

    # --- U2: RP2040-Zero (logical pin map) ---
    #   1=3V3, 2=GND, 3=GP2(SCK), 4=GP3(MOSI), 5=GP4(MISO),
    #   6=GP5(NSS), 7=GP6(BUSY), 8=GP7(IRQ), 9=GP8(RST), 10=GP9(CE),
    #   11=GP16(LED onboard — unused), 12=GP20(UART1 TX), 13=GP21(UART1 RX), 14=GND
    v3v3       += rp2040["1"]     # 3V3
    gnd        += rp2040["2"]     # GND
    spi_sck    += rp2040["3"]     # GP2  = SPI0 SCK  → F33 Pin 12
    spi_mosi   += rp2040["4"]     # GP3  = SPI0 MOSI → F33 Pin 15
    spi_miso   += rp2040["5"]     # GP4  = SPI0 MISO ← F33 Pin 16
    spi_nss    += rp2040["6"]     # GP5  = NSS (CS)  → F33 Pin 13
    f33_busy   += rp2040["7"]     # GP6  = BUSY input ← F33 Pin 14
    f33_irq    += rp2040["8"]     # GP7  = IRQ input ← F33 Pin 18
    f33_rst    += rp2040["9"]     # GP8  = RST output → F33 Pin 17
    f33_ce     += rp2040["10"]    # GP9  = CE output → F33 Pin 5 (sleep control — NEW)
    # Pin 11 = GP16 onboard LED — no external wiring (RP2040-Zero has it built-in)
    rp_tx_esp_rx += rp2040["12"]  # GP20 = UART1 TX → ESP GPIO1
    esp_tx_rp_rx += rp2040["13"]  # GP21 = UART1 RX ← ESP GPIO0
    gnd        += rp2040["14"]    # GND

    # --- U3: NiceRF LoRa2021F33-2G4 (datasheet pin numbers 1..18) ---
    # F33 PIN MAP IS DIFFERENT FROM BARE LR2021!
    #   Pin 1=VCC | 2,3,4,6,7,8,11=GND (7 GND pins!) | 5=CE
    #   9=ANT sub-GHz | 10=ANT 2.4GHz
    #   12=SCK | 13=NSS | 14=BUSY | 15=MOSI | 16=MISO | 17=RESET | 18=IRQ
    vraw      += f33["1"]        # Pin 1  = VCC (5V from supercap bus)
    gnd       += f33["2"]        # Pin 2  = GND
    gnd       += f33["3"]        # Pin 3  = GND
    gnd       += f33["4"]        # Pin 4  = GND
    f33_ce    += f33["5"]        # Pin 5  = CE (sleep control) → RP2040 GP9
    gnd       += f33["6"]        # Pin 6  = GND
    gnd       += f33["7"]        # Pin 7  = GND
    gnd       += f33["8"]        # Pin 8  = GND
    rf_subghz += f33["9"]        # Pin 9  = ANT sub-GHz → SMA J1
    rf_2g4    += f33["10"]       # Pin 10 = ANT 2.4GHz → SMA J2
    gnd       += f33["11"]       # Pin 11 = GND
    spi_sck   += f33["12"]       # Pin 12 = SCK  → RP2040 GP2
    spi_nss   += f33["13"]       # Pin 13 = NSS  → RP2040 GP5
    f33_busy  += f33["14"]       # Pin 14 = BUSY → RP2040 GP6
    spi_mosi  += f33["15"]       # Pin 15 = MOSI → RP2040 GP3
    spi_miso  += f33["16"]       # Pin 16 = MISO ← RP2040 GP4
    f33_rst   += f33["17"]       # Pin 17 = RESET → RP2040 GP8
    f33_irq   += f33["18"]       # Pin 18 = IRQ → RP2040 GP7

    # --- U4: MAX-M10S GPS ---
    v3v3          += gps["1"]     # VCC
    gnd           += gps["2"]     # GND
    gps_tx_esp_rx += gps["3"]     # GPS TX → ESP32 GPIO2
    # Pin 4 = GPS RX — NC for telemetry-only firmware (no config commands sent)

    # --- U5: MS5611 (I2C) ---
    v3v3    += ms5611["1"]        # VCC
    gnd     += ms5611["2"]        # GND
    i2c_sda += ms5611["3"]        # SDA
    i2c_scl += ms5611["4"]        # SCL

    # --------------------------------------------------------
    # 4. Power chain
    #    Solar → BAT54 → supercap(VCAP) → TPS7A02 → 3V3 rail
    #                                ↘ VRAW → F33 VCC (5V for 2W)
    # --------------------------------------------------------

    # Solar input pads
    solar_in += solar_j["1"]      # Solar +
    gnd      += solar_j["2"]      # Solar −

    # BAT54 reverse-protection diode: solar → Vcap
    solar_in += diode["1"]        # Anode
    vcap     += diode["2"]        # Cathode

    # Supercap on the LDO input side
    vcap += supercap["1"]         # Supercap +
    gnd  += supercap["2"]         # Supercap −

    # TPS7A02 LDO: Vcap → 3V3
    v3v3 += ldo["5"]              # OUT (3.3V)
    vcap += ldo["1"]              # IN
    gnd  += ldo["2"]              # GND
    vcap += ldo["3"]              # EN = IN (always on while power present)
    # Pin 4 = NC

    # VRAW tap from supercap bus → F33 VCC (5V for full 2W output)
    # The supercap bus is 5.4V max — well within F33's 3.0-5.5V range.
    # SPI pins are still 0-3.3V (F33 has internal level shifting).
    vcap += vraw                  # VRAW = VCAP (supercap bus, ~5.4V max)

    # --------------------------------------------------------
    # 5. Decoupling & bulk capacitors
    # --------------------------------------------------------

    # 3V3 rail decoupling (ESP, RP2040, GPS, MS5611, LDO output)
    for cap in (c_esp, c_rp, c_gps, c_baro, c_ldo):
        v3v3 += cap["1"]
        gnd  += cap["2"]

    # F33 VCC bulk decoupling on VRAW rail (5V, 1.2A TX bursts)
    # 100µF + 10µF + 100nF — handles the 1.2A current spikes at 433MHz 2W TX.
    for cap in (c_f33_bulk, c_f33_mid, c_f33_dec):
        vraw += cap["1"]
        gnd  += cap["2"]

    # --------------------------------------------------------
    # 6. I2C pull-ups (4.7k to 3V3)
    # --------------------------------------------------------
    v3v3    += r_sda["1"]
    i2c_sda += r_sda["2"]
    v3v3    += r_scl["1"]
    i2c_scl += r_scl["2"]

    # --------------------------------------------------------
    # 7. Supercap voltage divider (1M / 1M → ADC reads Vcap/2)
    #    Vcap ──R3(1M)── VDIV_MID ──R4(1M)── GND
    #    ESP32 ADC (GPIO4) taps VDIV_MID.
    # --------------------------------------------------------
    vcap     += r_div_hi["1"]
    vdiv_mid += r_div_hi["2"]
    vdiv_mid += r_div_lo["1"]
    gnd      += r_div_lo["2"]
    # ESP32 ADC (GPIO4) already connected to vdiv_mid at esp["6"] — no alias needed.

    # --------------------------------------------------------
    # 8. Status LED (ESP32 GPIO10, active low)
    #    GPIO10 ──R5(330R)── LED anode ── LED cathode ── GND
    # --------------------------------------------------------
    led_anode = Net("LED_ANODE")  # named net between R5 and LED anode
    led_drive += r_led["1"]
    led_anode += r_led["2"]        # R5 output → LED anode
    led_anode += led["2"]          # LED anode
    gnd        += led["1"]        # LED cathode
    # NOTE: Device:LED symbol pin orientation — pin 1 = anode (A), pin 2 = cathode (K).
    # Adjust at layout if your library differs.

    # --------------------------------------------------------
    # 9. SMA bulkhead connectors (2x edge-mount, signal + GND)
    #    F33 ANT (pin 9)  → J1 SMA sub-GHz signal, GND → shield
    #    F33 ANT-2G4 (10) → J2 SMA 2.4GHz signal, GND → shield
    #    Felix wants "big tail cable" adapters for external antennas.
    # --------------------------------------------------------
    rf_subghz += sma_sub["1"]     # Sub-GHz antenna signal (50Ω)
    gnd       += sma_sub["2"]     # SMA shield / GND
    rf_2g4    += sma_2g4["1"]     # 2.4GHz antenna signal (50Ω)
    gnd       += sma_2g4["2"]     # SMA shield / GND

    # --------------------------------------------------------
    # 10. Test points (bring-up debugging)
    # --------------------------------------------------------
    spi_sck  += tp_sck["1"]       # TP_SPI_SCK
    spi_mosi += tp_mosi["1"]      # TP_SPI_MOSI
    v3v3     += tp_3v3["1"]       # TP_VCC_3V3
    vraw     += tp_vraw["1"]      # TP_VRAW_5V (NEW — F33 power rail)
    gnd      += tp_gnd["1"]       # TP_GND

    # --------------------------------------------------------
    # 11. Netlist output
    # --------------------------------------------------------
    # NOTE: SKiDL's generate_netlist() uses file_= (or file=), NOT filepath=.
    # If the wrong kwarg is passed, it silently falls back to <script>.net.
    # We explicitly write to hub_board_f33.net for deterministic output naming.
    netlist_dir = os.path.dirname(os.path.abspath(__file__))
    netlist_filename = "hub_board_f33.net"
    netlist_filepath = os.path.join(netlist_dir, netlist_filename)

    netlist_str = generate_netlist(file_=netlist_filepath)

    # generate_netlist() returns the netlist STRING, not a path.
    # Verify the file was actually written (belt-and-suspenders check).
    if not os.path.exists(netlist_filepath):
        # Fallback: write the returned string explicitly
        with open(netlist_filepath, "w") as f:
            f.write(netlist_str or "")

    # Count parts/nets from the SKiDL context for the summary.
    try:
        from skidl import builtins
        n_parts = len([p for p in Part.get(".*") if p is not None])
        n_nets = len([n for n in Net.get(".*") if n is not None])
    except Exception:
        n_parts = "see netlist"
        n_nets = "see netlist"

    print("Hub board F33 (2W PA) schematic generated.")
    print(f"  Netlist : {netlist_filepath}")
    print(f"  Parts   : {n_parts}")
    print(f"  Nets    : {n_nets}")
    return netlist_filepath


if __name__ == "__main__":
    generate_hub_schematic_f33()
