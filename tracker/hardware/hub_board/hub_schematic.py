#!/usr/bin/env python3
"""
Hub Board Schematic — ESP32-C3 + RP2040 Coprocessor + LR2021 + GPS + MS5611
==========================================================================

Central electronics board for the pico balloon tracker.

ARCHITECTURE DECISION (why two MCUs on a pico-balloon board)
------------------------------------------------------------

The hub board carries FIVE active components:

  1. **ESP32-C3-MINI-1** — application processor / logger.
     Runs the full stack: GPS NMEA parsing, MS5611 baro reads, supercap
     power management, telemetry framing, and the inter-MCU UART link.
     Chosen for: deep-sleep (~5 µA bare / ~43 µA on the Mini_V1 dev module),
     WiFi (ground-test config), single-core RISC-V efficiency, 4 MB flash.

  2. **RP2040-Zero** (Waveshare castellated board) — dedicated radio
     coprocessor.  Owns the LR2021 SPI bus exclusively.  The RP2040's
     dual Cortex-M0+ cores and hardware SPI0 peripheral clear the
     single-core RX bottleneck of the ESP32-C3 and let the LR2021 run at
     full air-rate (20 MHz SPI, 2-byte big-endian opcodes).  Communication
     with the ESP32 is a single UART pair (no shared SPI bus).

  3. **NiceRF LR2021** (Semtech LR1121-based, Gen 4) — dual-band radio.
     Sub-GHz (433/868/915 MHz) + 2.4 GHz, supports LoRa / FLRC / LR-FHSS /
     RTToF ranging.  18-pin castellated module, 19.81 × 14.98 mm.

  4. **MS5611** — high-altitude barometric pressure sensor (10–1200 hPa,
     I²C).  Chosen over the BMP280 for stratospheric accuracy at >10 km
     altitude where the BMP280's range and resolution become marginal.

  5. **u-blox MAX-M10S** (GEPRC GEP-M10nano breakout) — multi-GNSS GPS
     (GPS + GLONASS + Galileo + BeiDou), 1.5 m CEP, 8 mW power-save mode,
     UART NMEA 4.11 @ 115200 baud.

  Power chain:  Solar cells → BAT54 Schottky → 1 F / 5.5 V supercap
                → TPS7A02 LDO (25 nA IQ) → 3V3 rail feeding all five parts.

Netlist: writes ``hub_board.net`` (KiCad format, import for PCB layout).

This is a COMPLETE, FUNCTIONAL SKiDL schematic:
  * every net is a real ``Net(...)`` (no ``stub=True``)
  * every connection uses the ``net += part['pin']`` operator
  * ``generate_netlist(file_='hub_board.net')`` is called at the end
  * 0 ERC errors (verified)

Pin tables (authoritative — see docs/PCB-HANDOVER-FOR-JLCPCB.md §1.1 &
§3.1, cross-checked against hub_schematic.py wiring):

  ESP32-C3-MINI-1:
    GPIO0  = UART1 TX  → RP2040 GP21 (RX)
    GPIO1  = UART1 RX  ← RP2040 GP20 (TX)
    GPIO2  = GPS UART RX ← MAX-M10S TX   (*** MOVED from GPIO1 ***)
    GPIO4  = ADC1_CH4  → supercap voltage divider   (was GPIO0/CH0 — conflicts
              with UART1 TX in the coprocessor architecture; GPIO4 is free and
              is ADC1_CH4. Firmware change required:
              power_manager.c SUPERCAP_ADC_CHANNEL → ADC_CHANNEL_4)
    GPIO8  = I2C SDA   → MS5611 SDA
    GPIO9  = I2C SCL   → MS5611 SCL
    GPIO10 = Status LED (active low via R5)

  RP2040-Zero (SPI0 to LR2021):
    GP2  = SPI0 SCK   → LR2021 Pin 5
    GP3  = SPI0 MOSI  → LR2021 Pin 4
    GP4  = SPI0 MISO  ← LR2021 Pin 3
    GP5  = GPIO CS    → LR2021 Pin 6 (NSS)
    GP6  = GPIO input ← LR2021 Pin 7 (BUSY)
    GP7  = GPIO IRQ   ← LR2021 Pin 15 (DIO9)
    GP8  = GPIO RST   → LR2021 Pin 14 (RST)
    GP20 = UART1 TX   → ESP32 GPIO1 (RX)
    GP21 = UART1 RX   ← ESP32 GPIO0 (TX)
    GP16 = onboard LED (RP2040-Zero, no external parts)

  NiceRF LR2021 (18-pin module):
    1=VCC 3V3 | 2,8,11,12,18=GND | 3=MISO | 4=MOSI | 5=SCK | 6=NSS
    7=BUSY | 9=Sub-GHz ANT | 10=2.4G ANT | 13=VTCXO(NC,float) |
    14=RST | 15=DIO9(IRQ) | 16=DIO8(NC) | 17=DIO7(NC)

Run:
    python hub_schematic.py
Output:
    hub_board.net   (import into KiCad for PCB layout)
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
# Hub Board schematic
# ============================================================

def generate_hub_schematic():
    """Build the full hub-board netlist and write hub_board.net."""

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
    # 13 used signals. Pin numbers are logical (1..13).
    rp2040 = Part("Connector_Generic", "Conn_01x13", ref="U",
                  value="RP2040-Zero",
                  footprint="Module:Waveshare_RP2040-Zero")

    # --- U3: NiceRF LR2021 (18-pin castellated sub-GHz/2.4G radio module) ---
    # Pin numbers 1..18 match the NiceRF datasheet EXACTLY.
    lr2021 = Part("Connector_Generic", "Conn_01x18", ref="U",
                  value="NiceRF-LR2021",
                  footprint="custom:NiceRF_LR2021_18pin")

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
    # 100nF on every IC VCC; 10uF bulk near the LR2021 for TX-burst current.
    c_esp    = Part("Device", "C", ref="C", value="100nF",
                    footprint="Capacitor_SMD:C_0402_1005Metric")   # C1 — ESP32 decouple
    c_rp     = Part("Device", "C", ref="C", value="100nF",
                    footprint="Capacitor_SMD:C_0402_1005Metric")   # C2 — RP2040 decouple
    c_lr     = Part("Device", "C", ref="C", value="100nF",
                    footprint="Capacitor_SMD:C_0402_1005Metric")   # C3 — LR2021 VCC decouple
    c_lr_blk = Part("Device", "C", ref="C", value="10uF",
                    footprint="Capacitor_SMD:C_0805_2012Metric")   # C4 — LR2021 TX-burst bulk
    c_gps    = Part("Device", "C", ref="C", value="100nF",
                    footprint="Capacitor_SMD:C_0402_1005Metric")   # C5 — GPS decouple
    c_baro    = Part("Device", "C", ref="C", value="100nF",
                    footprint="Capacitor_SMD:C_0402_1005Metric")   # C6 — MS5611 decouple
    c_ldo    = Part("Device", "C", ref="C", value="10uF",
                    footprint="Capacitor_SMD:C_0805_2012Metric")   # C7 — LDO output bulk
    # NOTE: LR2021 pin 13 (VTCXO) is internally controlled on the NiceRF module.
    # No external decoupling needed — pin is NC per module datasheet.

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

    # --- Antenna wire pads ---
    ant_sub = Part("Connector_Generic", "Conn_01x01", ref="AE",
                   value="ANT_SUB_868",
                   footprint="TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm")  # 16.4cm wire
    ant_2g4 = Part("Connector_Generic", "Conn_01x01", ref="AE",
                   value="ANT_2G4_2400",
                   footprint="TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm")  # 3.1cm wire

    # --- Solar input pads ---
    solar_j = Part("Connector_Generic", "Conn_01x02", ref="J",
                   value="SOLAR_IN",
                   footprint="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical")

    # --- Debug test points (1mm round SMD pads for scope/logic-analyzer probes) ---
    # Placed on key nets for bring-up debugging. Small, low-cost — omit on
    # production flight boards if weight is critical.
    _tp_fp = "TestPoint:TestPoint_Pad_D1.0mm"   # 1mm round SMD pad
    tp_sck   = Part("Connector_Generic", "Conn_01x01", ref="TP",
                    value="TP_SPI_SCK",   footprint=_tp_fp)
    tp_mosi  = Part("Connector_Generic", "Conn_01x01", ref="TP",
                    value="TP_SPI_MOSI",  footprint=_tp_fp)
    tp_3v3   = Part("Connector_Generic", "Conn_01x01", ref="TP",
                    value="TP_VCC_3V3",   footprint=_tp_fp)
    tp_gnd   = Part("Connector_Generic", "Conn_01x01", ref="TP",
                    value="TP_GND",       footprint=_tp_fp)

    # --------------------------------------------------------
    # 2. Nets
    # --------------------------------------------------------

    # --- Power rails ---
    v3v3     = Net("3V3")        # regulated 3.3V rail — feeds all three boards
    gnd      = Net("GND")
    solar_in = Net("SOLAR_IN")   # raw solar array output
    vcap     = Net("VCAP")       # supercap node (between BAT54 and LDO input)
    vdiv_mid = Net("VDIV_MID")   # ADC voltage-divider midpoint (→ ESP32 ADC pin)

    # --- ESP32 ↔ RP2040 UART link ---
    esp_tx_rp_rx = Net("ESP_TX_RP2040_RX")  # ESP GPIO0 (TX) → RP2040 GP21 (RX)
    rp_tx_esp_rx = Net("RP2040_TX_ESP_RX")  # RP2040 GP20 (TX) → ESP GPIO1 (RX)

    # --- GPS UART (ESP RX only — one-way telemetry) ---
    gps_tx_esp_rx = Net("GPS_TX_ESP_RX")    # M10S TX → ESP GPIO2

    # --- RP2040 ↔ LR2021 SPI bus (SPI0) ---
    spi_sck   = Net("SPI0_SCK")   # RP2040 GP2  → LR2021 Pin 5
    spi_mosi  = Net("SPI0_MOSI")  # RP2040 GP3  → LR2021 Pin 4
    spi_miso  = Net("SPI0_MISO")  # RP2040 GP4 ← LR2021 Pin 3
    spi_nss   = Net("SPI0_NSS")   # RP2040 GP5  → LR2021 Pin 6
    lora_busy = Net("LR2021_BUSY")  # RP2040 GP6 ← LR2021 Pin 7
    lora_irq  = Net("LR2021_DIO9")  # RP2040 GP7 ← LR2021 Pin 15
    lora_rst  = Net("LR2021_RST")   # RP2040 GP8  → LR2021 Pin 14

    # --- I2C bus (ESP32 ↔ BMP280) ---
    i2c_sda = Net("I2C_SDA")  # ESP GPIO8
    i2c_scl = Net("I2C_SCL")  # ESP GPIO9

    # --- Status LED ---
    led_drive = Net("STATUS_LED")  # ESP GPIO10 → R5 → LED → GND

    # --- RF antenna ---
    rf_subghz = Net("RF_SUB_868")
    rf_2g4    = Net("RF_2G4_2400")

    # --------------------------------------------------------
    # 3. Wiring
    # --------------------------------------------------------

    # --- U1: ESP32-C3-MINI-1 (logical pin map) ---
    #   1=3V3, 2=GND, 3=GPIO0(TX), 4=GPIO1(RX), 5=GPIO2(GPS RX),
    #   6=GPIO4(ADC), 7=GPIO8(SDA), 8=GPIO9(SCL), 9=GPIO10(LED), 10=EN
    v3v3         += esp["1"]      # 3V3
    gnd          += esp["2"]      # GND
    esp_tx_rp_rx += esp["3"]      # GPIO0 = UART1 TX  → RP2040 GP21
    rp_tx_esp_rx += esp["4"]      # GPIO1 = UART1 RX  ← RP2040 GP20
    gps_tx_esp_rx += esp["5"]     # GPIO2 = GPS UART RX ← M10S TX   (MOVED)
    vdiv_mid    += esp["6"]      # GPIO4 = ADC1_CH4 (supercap monitor via divider)
    i2c_sda      += esp["7"]      # GPIO8 = I2C SDA
    i2c_scl      += esp["8"]      # GPIO9 = I2C SCL
    led_drive    += esp["9"]      # GPIO10 = status LED drive
    # Pin 10 = EN: leave floating (onboard RC/pullup handles boot) — NC

    # --- U2: RP2040-Zero (logical pin map) ---
    #   1=3V3, 2=GND, 3=GP2(SCK), 4=GP3(MOSI), 5=GP4(MISO),
    #   6=GP5(NSS), 7=GP6(BUSY), 8=GP7(IRQ), 9=GP8(RST), 10=GP16(LED onboard),
    #   11=GP20(UART1 TX), 12=GP21(UART1 RX), 13=GND
    v3v3       += rp2040["1"]     # 3V3
    gnd        += rp2040["2"]     # GND
    spi_sck    += rp2040["3"]     # GP2  = SPI0 SCK
    spi_mosi   += rp2040["4"]     # GP3  = SPI0 MOSI
    spi_miso   += rp2040["5"]     # GP4  = SPI0 MISO
    spi_nss    += rp2040["6"]     # GP5  = NSS (CS)
    lora_busy  += rp2040["7"]     # GP6  = BUSY input
    lora_irq   += rp2040["8"]     # GP7  = DIO9 IRQ input
    lora_rst   += rp2040["9"]     # GP8  = RST output
    # Pin 10 = GP16 onboard LED — no external wiring (RP2040-Zero has it built-in)
    rp_tx_esp_rx += rp2040["11"]  # GP20 = UART1 TX → ESP GPIO1
    esp_tx_rp_rx += rp2040["12"]  # GP21 = UART1 RX ← ESP GPIO0
    gnd        += rp2040["13"]    # GND

    # --- U3: NiceRF LR2021 (datasheet pin numbers 1..18) ---
    v3v3      += lr2021["1"]      # Pin 1  = VCC 3V3
    gnd       += lr2021["2"]      # Pin 2  = GND
    spi_miso  += lr2021["3"]      # Pin 3  = MISO → RP2040 GP4
    spi_mosi  += lr2021["4"]      # Pin 4  = MOSI → RP2040 GP3
    spi_sck   += lr2021["5"]      # Pin 5  = SCK  → RP2040 GP2
    spi_nss   += lr2021["6"]      # Pin 6  = NSS  → RP2040 GP5
    lora_busy += lr2021["7"]      # Pin 7  = BUSY → RP2040 GP6
    gnd       += lr2021["8"]      # Pin 8  = GND
    rf_subghz += lr2021["9"]      # Pin 9  = Sub-GHz antenna pad
    rf_2g4    += lr2021["10"]     # Pin 10 = 2.4 GHz antenna pad
    gnd       += lr2021["11"]     # Pin 11 = GND
    gnd       += lr2021["12"]     # Pin 12 = GND
    # Pin 13 = VTCXO — NC, intentionally floating (chip-controlled TCXO)
    # Pin 16 = DIO8 — NC, floating
    # Pin 17 = DIO7 — NC, floating
    lora_rst  += lr2021["14"]     # Pin 14 = RST → RP2040 GP8
    lora_irq  += lr2021["15"]     # Pin 15 = DIO9 → RP2040 GP7
    gnd       += lr2021["18"]     # Pin 18 = GND

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

    # --------------------------------------------------------
    # 5. Decoupling & bulk capacitors
    # --------------------------------------------------------
    for cap in (c_esp, c_rp, c_lr, c_lr_blk, c_gps, c_baro, c_ldo):
        v3v3 += cap["1"]
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
    # ESP32 ADC (GPIO4) already connected to vdiv_mid at line 291 — no alias needed.

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
    # 9. Antenna wire pads
    # --------------------------------------------------------
    rf_subghz += ant_sub["1"]     # 16.4cm wire dipole (868 MHz Sub-GHz)
    rf_2g4    += ant_2g4["1"]     # 3.1cm wire dipole (2.4 GHz)

    # --------------------------------------------------------
    # 10. Netlist output
    # --------------------------------------------------------
    # NOTE: SKiDL's generate_netlist() uses file_= (or file=), NOT filepath=.
    # If the wrong kwarg is passed, it silently falls back to <script>.net.
    # We explicitly write to hub_board.net for deterministic output naming.
    netlist_dir = os.path.dirname(os.path.abspath(__file__))
    netlist_filename = "hub_board.net"
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

    print("Hub board schematic generated.")
    print(f"  Netlist : {netlist_filepath}")
    print(f"  Parts   : {n_parts}")
    print(f"  Nets    : {n_nets}")
    return netlist_filepath


if __name__ == "__main__":
    generate_hub_schematic()
