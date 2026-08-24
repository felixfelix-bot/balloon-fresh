#!/usr/bin/python3.14
"""Phase 1A: RF 50Ω trace + power routing + thermal vias + GND stitching.

Input: v_c3_flight_p0fixed.kicad_pcb (Phase 0 verified placement)
Output: v_c3_flight_rf_power.kicad_pcb
"""
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew
import math

INPUT  = 'v_c3_flight_p0fixed.kicad_pcb'
OUTPUT = 'v_c3_flight_rf_power.kicad_pcb'

F_CU = pcbnew.F_Cu
B_CU = pcbnew.B_Cu
IN1  = pcbnew.In1_Cu  # GND plane (layer 4)
IN2  = pcbnew.In2_Cu  # +3V3 plane (layer 6)

# Trace widths
RF_WIDTH = 200000       # 0.2mm — ~50Ω microstrip over GND plane (0.1mm dielectric)
POWER_WIDTH = 400000    # 0.4mm — power traces
SIGNAL_WIDTH = 200000   # 0.2mm — signal traces
VIA_SIZE = 550000       # 0.55mm via
VIA_DRILL = 300000      # 0.3mm drill

b = pcbnew.LoadBoard(INPUT)

# Precompute net codes
NET_CODES = {}
for nc, net in b.GetNetsByNetcode().items():
    try: NET_CODES[net.GetNetname()] = nc
    except: pass

def nc(netname):
    return NET_CODES.get(netname, 0)

def add_track(x1, y1, x2, y2, layer, netname, width=SIGNAL_WIDTH):
    t = pcbnew.PCB_TRACK(b)
    t.SetLayer(layer)
    t.SetWidth(width)
    t.SetStart(pcbnew.VECTOR2I(int(x1), int(y1)))
    t.SetEnd(pcbnew.VECTOR2I(int(x2), int(y2)))
    t.SetNetCode(nc(netname))
    b.Add(t)
    return t

def add_via(x, y, netname):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(VIA_SIZE)
    v.SetDrill(VIA_DRILL)
    v.SetNetCode(nc(netname))
    b.Add(v)
    return v

# === STEP 0: Rip ALL existing tracks/vias ===
print("[0] Ripping all existing tracks...")
ripped = 0
# Snapshot tracks first
track_snapshot = list(b.Tracks())
for t in track_snapshot:
    try:
        b.Remove(t)
        ripped += 1
    except:
        pass
print(f"  Ripped {ripped} items")

# === STEP 1: Route RF_OUT (50Ω microstrip) ===
print("\n[1] Routing RF_OUT trace (50Ω)...")
# Source: U2 pad 9 [RF_OUT] at (73.5, 21.0)mm
# Dest: ANT1 pad 1 [RF_OUT] at (38.0, 41.5)mm
# Route as short as possible on F.Cu, Manhattan style
# H-V: go left from U2 to ANT1 x, then down
rf_sx, rf_sy = 73_500_000, 21_000_000
rf_ex, rf_ey = 38_000_000, 41_500_000

# Route: U2 → left → down to ANT1
# Corner at (rf_ex, rf_sy) = (38, 21) — H then V
add_track(rf_sx, rf_sy, rf_ex, rf_sy, F_CU, 'RF_OUT', RF_WIDTH)  # Horizontal
add_track(rf_ex, rf_sy, rf_ex, rf_ey, F_CU, 'RF_OUT', RF_WIDTH)  # Vertical
print(f"  RF_OUT: ({rf_sx/1e6:.1f},{rf_sy/1e6:.1f}) → ({rf_ex/1e6:.1f},{rf_sy/1e6:.1f}) → ({rf_ex/1e6:.1f},{rf_ey/1e6:.1f})")

# GND stitching vias flanking RF feed at ANT1 end
add_via(rf_ex - 2_000_000, rf_ey - 2_000_000, 'GND')  # Left of antenna feed
add_via(rf_ex + 2_000_000, rf_ey - 2_000_000, 'GND')  # Right of antenna feed
print(f"  GND stitching vias at antenna feed: ({(rf_ex-2e6)/1e6:.1f},{(rf_ey-2e6)/1e6:.1f}), ({(rf_ex+2e6)/1e6:.1f},{(rf_ey-2e6)/1e6:.1f})")

# GND stitching via near U2 RF pad
add_via(rf_sx, rf_sy - 2_000_000, 'GND')
print(f"  GND stitching via at U2 RF: ({rf_sx/1e6:.1f},{(rf_sy-2e6)/1e6:.1f})")

# === STEP 2: Route power traces (VCAP, SOLAR_IN) ===
print("\n[2] Routing power traces (0.4mm)...")

# VCAP: U4 pad 1 (8.9,19.1) → D1 pad 2 (19.6,26.0) → C_CAP pad 1 (7.0,38.0)
# These need to be connected on F.Cu
vcap_pads = [
    (8_900_000, 19_100_000),   # U4 VCAP
    (19_600_000, 26_000_000),  # D1 VCAP
    (7_000_000, 38_000_000),   # C_CAP VCAP
]
# Route U4 → D1 (Manhattan)
add_track(vcap_pads[0][0], vcap_pads[0][1], vcap_pads[1][0], vcap_pads[0][1], F_CU, 'VCAP', POWER_WIDTH)
add_track(vcap_pads[1][0], vcap_pads[0][1], vcap_pads[1][0], vcap_pads[1][1], F_CU, 'VCAP', POWER_WIDTH)
print(f"  VCAP: U4 → D1 routed")

# SOLAR_IN: SOLAR pad 1 (8.0,8.0) → D1 pad 1 (16.4,26.0)
add_track(8_000_000, 8_000_000, 8_000_000, 26_000_000, F_CU, 'SOLAR_IN', POWER_WIDTH)
add_track(8_000_000, 26_000_000, 16_400_000, 26_000_000, F_CU, 'SOLAR_IN', POWER_WIDTH)
print(f"  SOLAR_IN: SOLAR → D1 routed")

# === STEP 3: Thermal vias for regulator (U4) ===
print("\n[3] Adding thermal vias for U4 regulator...")
# U4 at (10.0,20.0), GND pad at (8.9,20.0)
# Add 4 thermal vias near U4 GND pad
u4_gnd_x, u4_gnd_y = 8_900_000, 20_000_000
for dx, dy in [(-2_000_000, -1_500_000), (-2_000_000, 1_500_000),
               (2_000_000, -1_500_000), (2_000_000, 1_500_000)]:
    add_via(u4_gnd_x + dx, u4_gnd_y + dy, 'GND')
    print(f"  Thermal via at ({(u4_gnd_x+dx)/1e6:.1f},{(u4_gnd_y+dy)/1e6:.1f})")

# === STEP 4: GND stitching vias at signal endpoints ===
print("\n[4] Adding GND stitching vias at signal endpoints...")
# Near U1 (ESP32) signal pads — GND via for return path
# U1 GND pad at (31.2,31.0) — add stitching vias near SPI pins
add_via(45_000_000, 20_000_000, 'GND')  # Near U1 right side
add_via(45_000_000, 28_000_000, 'GND')  # Near U1 bottom right

# Near U2 (LoRa) signal pads
add_via(58_500_000, 5_000_000, 'GND')   # Near U2 top
add_via(73_500_000, 5_000_000, 'GND')   # Near U2 top-right

# Near U3 signal pads
add_via(65_000_000, 36_000_000, 'GND')  # Near U3

# Near U5 (flash) signal pads
add_via(40_000_000, 50_000_000, 'GND')  # Near U5
print(f"  GND stitching vias placed (6 total)")

# === STEP 5: Power plane thermal vias ===
print("\n[5] Adding power thermal vias for +3V3 pads...")
# +3V3 pads that need thermal vias to In2.Cu plane:
# U1 pad 1 +3V3 at (31.2,19.0)
add_via(28_000_000, 19_000_000, '+3V3')
print(f"  +3V3 thermal via near U1")

# U2 pad 13 +3V3 at (73.5,13.0) — already has C3 nearby
add_via(76_000_000, 13_000_000, '+3V3')
print(f"  +3V3 thermal via near U2")

# U3 pad 7 +3V3 at (60.2,42.2)
add_via(57_000_000, 42_000_000, '+3V3')
print(f"  +3V3 thermal via near U3")

# U5 pad 2 +3V3 at (37.7,49.0)
add_via(35_500_000, 50_000_000, '+3V3')
print(f"  +3V3 thermal via near U5")

# GND thermal vias for ICs (connect to In1.Cu GND plane)
# U1 GND pads at (31.2,31.0) and thermal pad cluster ~41,25
add_via(31_200_000, 33_000_000, 'GND')  # Near U1 bottom GND
add_via(43_000_000, 25_000_000, 'GND')  # Near U1 thermal pad
print(f"  GND thermal vias near U1")

# U2 GND pads at (58.5,7.0) and (58.5,21.0)
add_via(55_000_000, 7_000_000, 'GND')
add_via(55_000_000, 21_000_000, 'GND')
print(f"  GND thermal vias near U2")

# U3 GND pad at (60.2,35.6)
add_via(57_000_000, 36_000_000, 'GND')
print(f"  GND thermal via near U3")

# === STEP 6: Connect EN (signal, not power — corrected per consultant) ===
print("\n[6] Routing EN signal...")
# U1 pad 2 EN at (31.2,20.5) → J1 pad 3 EN at (22.1,52.0)
# Route as signal on F.Cu with V-H Manhattan
add_track(31_200_000, 20_500_000, 31_200_000, 52_000_000, F_CU, 'EN', SIGNAL_WIDTH)
add_track(31_200_000, 52_000_000, 22_100_000, 52_000_000, F_CU, 'EN', SIGNAL_WIDTH)
print(f"  EN: U1 → J1 routed")

# === STEP 7: Fill zones + save ===
print("\n[7] Filling zones + connectivity...")
b.BuildConnectivity()
zones = list(b.Zones())
filler = pcbnew.ZONE_FILLER(b)
filler.Fill(zones)
print(f"  Filled {len(zones)} zones")

pcbnew.SaveBoard(OUTPUT, b)
print(f"\nSaved: {OUTPUT}")

# Count what we created
tracks = 0
vias = 0
for t in b.Tracks():
    if t.GetClass() == 'PCB_VIA':
        vias += 1
    else:
        tracks += 1
print(f"Tracks: {tracks}, Vias: {vias}")
print("\n=== PHASE 1A DONE ===")
