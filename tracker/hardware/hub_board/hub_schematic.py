"""
Hub Board Schematic - ESP32-C3 + LR2021 + SKY66112 + SP4T Switch
Central electronics board for pico balloon tracker.

Generates KiCad netlist via SKiDL.
Run: python hub_schematic.py
Output: hub_board.net (import into KiCad for layout)
"""

from skidl import *

@SubCircuit
def esp32_c3():
    mcu = Part("RF_Module", "ESP32-C3-MINI-1", ref="U", footprint="RF_Module:ESP32-C3-MINI-1")
    return mcu

@SubCircuit
def lr2021_module():
    lora = Part("RF_Module", "LR2021", ref="U", footprint="RF_Module:LR2021_Module")
    return lora

@SubCircuit
def sky66112_fem():
    fem = Part("RF_Amplifier", "SKY66112-11", ref="U", footprint="Package_DFN_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.8x1.8mm")
    return fem

@SubCircuit
def sp4t_switch():
    sw = Part("RF_Switch", "SKY13351-378LF", ref="U", footprint="Package_DFN_QFN:QFN-12-1EP_3x3mm_P0.5mm")
    return sw

@SubCircuit
def bmp280_sensor():
    sensor = Part("Sensor_Pressure", "BMP280", ref="U", footprint="Package_LGA:Bosch_LGA-8_2x2.5mm_P0.65mm_ClockwisePinNumbering")
    return sensor

@SubCircuit
def power_supply():
    bat54 = Part("Diode", "BAT54", ref="D", footprint="Diode_SMD:D_SOD-123")
    tps7a02 = Part("Regulator_Linear", "TPS7A0233DBVR", ref="U", footprint="Package_TO_SOT_SMD:SOT-23-5")
    cap1 = Part("Device", "C", ref="C", value="3.3F", footprint="Capacitor_THT:CP_Radial_D8.0mm_P3.50mm")
    cap2 = Part("Device", "C", ref="C", value="3.3F", footprint="Capacitor_THT:CP_Radial_D8.0mm_P3.50mm")
    bal_r1 = Part("Device", "R", ref="R", value="10k", footprint="Resistor_SMD:R_0402_1005Metric")
    bal_r2 = Part("Device", "R", ref="R", value="10k", footprint="Resistor_SMD:R_0402_1005Metric")

    return {
        "bat54": bat54,
        "tps7a02": tps7a02,
        "cap1": cap1,
        "cap2": cap2,
        "bal_r1": bal_r1,
        "bal_r2": bal_r2,
    }

@SubCircuit
def decoupling_caps(prefix, count):
    caps = []
    for i in range(count):
        c = Part("Device", "C", ref=f"C_{prefix}", value="100nF", footprint="Capacitor_SMD:C_0402_1005Metric")
        caps.append(c)
    return caps

def generate_hub_schematic():
    mcu = esp32_c3()
    lora = lr2021_module()
    fem = sky66112_fem()
    ant_sw = sp4t_switch()
    bmp = bmp280_sensor()
    pwr = power_supply()

    decoupling_caps("mcu", 3)
    decoupling_caps("lora", 2)
    decoupling_caps("fem", 1)

    spi_mosi = Net("SPI_MOSI", stub=True)
    spi_miso = Net("SPI_MISO", stub=True)
    spi_sclk = Net("SPI_SCLK", stub=True)
    spi_cs = Net("SPI_CS_LORA", stub=True)
    lora_reset = Net("LORA_RESET", stub=True)
    lora_dio1 = Net("LORA_DIO1", stub=True)
    lora_busy = Net("LORA_BUSY", stub=True)
    i2c_sda = Net("I2C_SDA", stub=True)
    i2c_scl = Net("I2C_SCL", stub=True)
    fem_tx_en = Net("FEM_TX_EN", stub=True)
    ant_ctrl1 = Net("ANT_CTRL1", stub=True)
    ant_ctrl2 = Net("ANT_CTRL2", stub=True)
    rf_out = Net("RF_OUT", stub=True)
    rf_ant1 = Net("RF_ANT1", stub=True)
    rf_ant2 = Net("RF_ANT2", stub=True)
    rf_ant3 = Net("RF_ANT3", stub=True)
    rf_ant4 = Net("RF_ANT4", stub=True)
    vcc_3v3 = Net("VCC_3V3", stub=True)
    gnd = Net("GND", stub=True)
    solar_in = Net("SOLAR_IN", stub=True)
    adc_vcap = Net("ADC_VCAP", stub=True)

    netlist_path = "hub_board.net"
    generate_netlist(netlist_path)
    print(f"Netlist generated: {netlist_path}")

if __name__ == "__main__":
    generate_hub_schematic()
