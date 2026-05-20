"""
Wing Board Schematic - PCB Yagi Antenna + Solar Cells
4 identical wing boards, soldered to hub board at 90-degree angles.

Each wing has:
- 3-element PCB Yagi antenna (2.4 GHz)
- 3x 52x19mm solar cells in series
- Feed point connects to hub SP4T switch output
- Solder pads for mechanical + electrical connection to hub

Run: python wing_schematic.py
Output: wing_board.net
"""

from skidl import *

@SubCircuit
def pcb_yagi_antenna():
    driven = Part("Mechanical", "Antenna_Driven", ref="AE",
                  footprint="balloon:PCB_Yagi_Driven_2.4GHz")
    director1 = Part("Mechanical", "Antenna_Director", ref="AE",
                     footprint="balloon:PCB_Yagi_Director1_2.4GHz")
    director2 = Part("Mechanical", "Antenna_Director", ref="AE",
                     footprint="balloon:PCB_Yagi_Director2_2.4GHz")
    return [driven, director1, director2]

@SubCircuit
def solar_cell_chain():
    cells = []
    for i in range(3):
        cell = Part("Device", "Solar_Cell", ref="SC",
                    value="52x19mm_0.5V_400mA",
                    footprint="balloon:SolarCell_52x19mm")
        cells.append(cell)
    return cells

@SubCircuit
def wing_connectors():
    pad_feed = Part("Connector", "Conn_01x01", ref="J",
                    footprint="balloon:Wing_Feed_Pad")
    pad_gnd = Part("Connector", "Conn_01x01", ref="J",
                   footprint="balloon:Wing_GND_Pad")
    pad_vcc = Part("Connector", "Conn_01x01", ref="J",
                   footprint="balloon:Wing_VCC_Pad")
    pad_mech = Part("Connector", "Conn_01x02", ref="J",
                    footprint="balloon:Wing_Mech_Pad")
    return {
        "feed": pad_feed,
        "gnd": pad_gnd,
        "vcc": pad_vcc,
        "mech": pad_mech,
    }

def generate_wing_schematic():
    antenna = pcb_yagi_antenna()
    solar = solar_cell_chain()
    connectors = wing_connectors()

    rf_feed = Net("RF_FEED", stub=True)
    gnd = Net("GND", stub=True)
    solar_out = Net("SOLAR_OUT", stub=True)

    netlist_path = "wing_board.net"
    generate_netlist(netlist_path)
    print(f"Netlist generated: {netlist_path}")

if __name__ == "__main__":
    generate_wing_schematic()
