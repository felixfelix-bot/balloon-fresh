"""
Wing Board Schematic - Solar Cells + PCB Yagi Antenna (V2 optional)
4 identical wing boards, soldered to hub board at 90-degree angles.

Each wing has:
- 3x 52x19mm solar cells in series (1.5V, 400mA)
- RF feed pad (connects to hub SP4T switch output for V2, or direct for V1)
- Solder pads for mechanical + electrical connection to hub

Run: python wing_schematic.py
Output: wing_board.net
"""

import os
os.environ['KICAD9_SYMBOL_DIR'] = '/usr/share/kicad/symbols'
os.environ['KICAD_SYMBOL_DIR'] = '/usr/share/kicad/symbols'

from skidl import *

def generate_wing_schematic():
    # --- Components ---

    # 3x Solar cells (52x19mm, 0.5V 400mA each, series = 1.5V)
    sc1 = Part("Device", "Solar_Cell", ref="SC", value="52x19mm_0.5V",
               footprint="TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm")
    sc2 = Part("Device", "Solar_Cell", ref="SC", value="52x19mm_0.5V",
               footprint="TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm")
    sc3 = Part("Device", "Solar_Cell", ref="SC", value="52x19mm_0.5V",
               footprint="TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm")

    # 3-pin tab connector (V_OUT, GND, V_CHAIN_IN)
    # Soldered to hub board
    tab = Part("Connector_Generic", "Conn_01x03", ref="J",
               value="Wing_Tab",
               footprint="Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical")

    # RF feed pad (for V2 PCB Yagi, or NC for V1)
    rf_feed = Part("Connector_Generic", "Conn_01x01", ref="J",
                   value="RF_Feed",
                   footprint="TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm")

    # Optional ferrite bead (V2 only, isolates solar from antenna area)
    # Ferrite bead (V2 optional — use custom inline part since Device:Ferrite_Bead not in KiCad v9)
    fb1 = Part(name="Ferrite_Bead", tool='skidl', dest=TEMPLATE,
               ref_prefix="FB", footprint="Inductor_SMD:L_0402_1005Metric")
    fb1 += Pin(num='1', name='A', func=Pin.types.PASSIVE)
    fb1 += Pin(num='2', name='B', func=Pin.types.PASSIVE)
    fb1 = fb1()

    # PCB Yagi antenna elements (V2 only — represented as antenna pads)
    # Driven element
    yagi_driven = Part("Connector_Generic", "Conn_01x02", ref="AE",
                       value="Yagi_Driven_2.4G",
                       footprint="TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm")
    # Director elements (single pad, no electrical connection for V1)
    yagi_dir1 = Part("Connector_Generic", "Conn_01x01", ref="AE",
                     value="Yagi_Dir1_2.4G",
                     footprint="TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm")
    yagi_dir2 = Part("Connector_Generic", "Conn_01x01", ref="AE",
                     value="Yagi_Dir2_2.4G",
                     footprint="TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm")

    # --- Nets ---

    gnd = Net("GND")
    solar_out = Net("SOLAR_OUT")     # 1.5V from 3 cells in series
    solar_mid1 = Net("SOLAR_MID1")   # Between cell 1 and 2
    solar_mid2 = Net("SOLAR_MID2")   # Between cell 2 and 3
    rf_signal = Net("RF_SIGNAL")      # RF feed for V2 Yagi

    # --- Solar cell series connection ---
    # SC1(+) ── SC1(-) → SC2(+) ── SC2(-) → SC3(+) ── SC3(-) → SOLAR_OUT
    # Device:Solar_Cell pins: 1=+, 2=-

    # SC1
    solar_out += sc1.p[1]    # SC1 + = output (series start, most positive)
    solar_mid1 += sc1.p[2]   # SC1 - = mid1

    # SC2
    solar_mid1 += sc2.p[1]   # SC2 + = mid1 (connects to SC1 -)
    solar_mid2 += sc2.p[2]   # SC2 - = mid2

    # SC3
    solar_mid2 += sc3.p[1]   # SC3 + = mid2 (connects to SC2 -)
    gnd         += sc3.p[2]   # SC3 - = GND (series end, most negative)

    # --- Tab connector ---
    # Pin 1 = V_OUT (solar output to hub power chain)
    # Pin 2 = GND
    # Pin 3 = V_CHAIN_IN (for chaining multiple carriers)
    solar_out += tab.p[1]
    gnd       += tab.p[2]
    # Pin 3 = V_CHAIN_IN (connects to previous carrier's V_OUT for parallel/series chaining)
    # For single carrier: NC. For chained: connects to next carrier V_OUT.

    # --- RF feed (V2 only) ---
    rf_signal += rf_feed.p[1]
    # Yagi driven element connects to RF feed
    rf_signal += yagi_driven.p[1]
    gnd       += yagi_driven.p[2]  # Driven element ground side

    # Director elements (V2 only — no electrical connection for V1, just copper pattern)
    # These are passive copper elements, no net connection needed

    # --- Ferrite bead (V2 optional, in series with solar output) ---
    # FB1 isolates solar traces from V2 Yagi area
    # In V1: bypass with 0-ohm or solder bridge
    # Not connecting in netlist — placed on PCB only as optional component

    # --- Generate netlist ---
    netlist_path = "wing_board.net"
    generate_netlist(filepath=netlist_path)

    # Print summary
    import skidl
    parts = list(skidl.SKIDL)
    print(f"Netlist generated: {netlist_path}")
    print(f"  Parts: {len(parts)}")

if __name__ == "__main__":
    generate_wing_schematic()