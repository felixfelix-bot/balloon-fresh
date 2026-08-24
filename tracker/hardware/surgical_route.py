#!/usr/bin/python3.14
"""
Surgical routing: connect ONLY the 26 specific unconnected pairs.
Most are short distances — add straight tracks, check DRC in batches.
"""
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew
import json, re, math, subprocess

MM = 1000000

board_path = 'output/v2_adc_clean2.kicad_pcb'
board = pcbnew.LoadBoard(board_path)
initial_tracks = len(board.GetTracks())
print(f"Loaded. Initial tracks: {initial_tracks}")

def add_track(net_name, x1, y1, x2, y2, layer=pcbnew.F_Cu, w=0.25):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pcbnew.VECTOR2I(int(x1*MM), int(y1*MM)))
    t.SetEnd(pcbnew.VECTOR2I(int(x2*MM), int(y2*MM)))
    t.SetWidth(int(w*MM))
    t.SetLayer(layer)
    n = board.FindNet(net_name)
    if n:
        t.SetNet(n)
    board.Add(t)

def add_via(net_name, x, y):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(int(x*MM), int(y*MM)))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(int(0.6*MM))
    v.SetDrill(int(0.3*MM))
    n = board.FindNet(net_name)
    if n:
        v.SetNet(n)
    board.Add(v)

def run_drc():
    pcbnew.SaveBoard(board_path, board)
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', 
                    '--output', '/tmp/surgical_drc.json', board_path],
                   capture_output=True, timeout=30)
    with open('/tmp/surgical_drc.json') as f:
        drc = json.load(f)
    v = drc.get('violations', [])
    u = drc.get('unconnected_items', [])
    shorts = [x for x in v if 'shorting' in x.get('type', '').lower()]
    return len(v), len(u), len(shorts)

# The 26 unconnected pairs, grouped by distance
# Format: (net, x1, y1, x2, y2, layer, width)
# F_Cu = top, B_Cu = bottom

routes = [
    # SHORT pairs (<5mm) — connect directly, lowest risk
    ('3V3',      8.9, 18.8,  9.5, 22.0, pcbnew.F_Cu, 0.40),  # U4->C2, 3.2mm
    ('GND',     10.5, 20.0, 10.5, 22.0, pcbnew.F_Cu, 0.25),  # C1->C2, 2.0mm (vertical!)
    ('GND',     10.1, 14.0,  8.0, 17.2, pcbnew.F_Cu, 0.25),  # U2->U4, 3.8mm
    ('VCAP',     9.5, 20.0,  8.9, 17.2, pcbnew.F_Cu, 0.40),  # C1->U4, 2.9mm
    ('VCAP',     8.9, 17.2,  7.0, 17.3, pcbnew.F_Cu, 0.40),  # U4->track, 1.9mm
    ('VDIV_MID', 1.9, 32.6,  3.5, 30.0, pcbnew.F_Cu, 0.25),  # track->R_DIV1, 2.4mm
    ('GND',      5.0, 31.4,  3.3, 28.0, pcbnew.F_Cu, 0.25),  # track->U3, 3.5mm
    ('SPI_SCK', 10.1, 20.0, 10.5, 15.5, pcbnew.F_Cu, 0.25),  # U2->U1, 4.5mm (mostly vertical)
    ('SPI_MISO',10.1, 16.0, 11.0, 13.0, pcbnew.F_Cu, 0.25),  # U2->R_PD, 3.2mm
    ('SPI_MISO',11.0, 13.0,  8.5, 11.2, pcbnew.F_Cu, 0.25),  # R_PD->U1, 3.0mm
]

# MEDIUM pairs (5-15mm) — try direct, may need detour
medium_routes = [
    ('3V3',      1.6, 28.4,  9.5, 22.0, pcbnew.F_Cu, 0.40),  # track->C2, 9.5mm
    ('3V3',      8.9, 18.8, 10.9, 12.0, pcbnew.F_Cu, 0.40),  # U4->track, 7.1mm
    ('GND',     10.5, 22.0, 12.1, 26.0, pcbnew.F_Cu, 0.25),  # C2->track, 4.5mm
    ('GND',     15.5,  9.8, 10.0, 13.9, pcbnew.F_Cu, 0.25),  # U1->track, 6.6mm
    ('SPI_NSS', 10.1, 22.0, 16.5, 15.5, pcbnew.F_Cu, 0.25),  # U2->U1, 9.0mm
    ('LR2021_BUSY',8.5,14.2,10.1,24.0, pcbnew.F_Cu, 0.25),  # U1->U2, 10.1mm
    ('STATUS_LED',15.0,15.5,19.5,6.0, pcbnew.F_Cu, 0.25),   # U1->R_LED, 11.0mm
    ('RF_2G4_2400',29.9,28.0,46.0,30.0, pcbnew.F_Cu, 0.76), # U2->ANT2, 16.2mm
]

# LONG pairs (>15mm) — highest risk, add last and check individually
long_routes = [
    ('LR2021_DIO9',8.5,15.8,29.9,18.0, pcbnew.F_Cu, 0.25),  # U1->U2, 21.5mm
    ('RF_SUB_868',10.1,28.0,46.0,25.0, pcbnew.F_Cu, 0.76),  # U2->ANT1, 36.1mm
    ('VCAP',     7.5, 37.0,  9.5, 20.0, pcbnew.F_Cu, 0.40),  # C_CAP->C1, 17.4mm
    ('3V3',     15.5,  8.2, 40.0, 25.0, pcbnew.F_Cu, 0.40),  # U1->FEM, 30mm
    ('GND',     10.0, 31.1, 12.5, 37.0, pcbnew.F_Cu, 0.25),  # track->C_CAP, 6.3mm
    ('GND',     41.5, 25.0, 29.9, 24.0, pcbnew.F_Cu, 0.25),  # FEM->track, 11.6mm
    ('GND',     44.5, 30.0, 41.5, 25.0, pcbnew.B_Cu, 0.25),  # B.Cu track->FEM GND, 5.8mm
]

# Baseline DRC
v0, u0, s0 = run_drc()
print(f"Baseline: V={v0} U={u0} S={s0}")

# Phase 1: Add SHORT routes
print("\n--- Phase 1: SHORT routes ---")
for r in routes:
    add_track(*r)
    print(f"  Added: {r[0]} ({r[1]:.1f},{r[2]:.1f})->({r[3]:.1f},{r[4]:.1f})")

v1, u1, s1 = run_drc()
print(f"After SHORT: V={v1} U={u1} S={s1} (delta V={v1-v0} U={u1-u0} S={s1-s0})")

if s1 > s0:
    print("WARNING: Shorts increased! Saving for analysis but continuing...")

# Phase 2: Add MEDIUM routes
print("\n--- Phase 2: MEDIUM routes ---")
for r in medium_routes:
    add_track(*r)
    print(f"  Added: {r[0]} ({r[1]:.1f},{r[2]:.1f})->({r[3]:.1f},{r[4]:.1f})")

v2, u2, s2 = run_drc()
print(f"After MEDIUM: V={v2} U={u2} S={s2} (delta V={v2-v0} U={u2-u0} S={s2-s0})")

# Phase 3: Add LONG routes one at a time, check after each
print("\n--- Phase 3: LONG routes (one at a time) ---")
for i, r in enumerate(long_routes):
    tracks_before = len(board.GetTracks())
    add_track(*r)
    
    # Save and check
    v3, u3, s3 = run_drc()
    delta_s = s3 - s2 if i == 0 else s3 - s_prev
    
    if delta_s > 0:
        print(f"  [{r[0]}] ADDED SHORT ({delta_s} new shorts)! Reverting...")
        # Remove last track
        tracks = board.GetTracks()
        board.Remove(tracks[-1])
        s_prev = s2 if i == 0 else s_prev
    else:
        print(f"  [{r[0]}] OK ({r[1]:.1f},{r[2]:.1f})->({r[3]:.1f},{r[4]:.1f}) — V={v3} U={u3} S={s3}")
        s_prev = s3

# Save final
pcbnew.SaveBoard(board_path, board)
print(f"\n=== FINAL ===")
print(f"Tracks: {len(board.GetTracks())} (was {initial_tracks})")

# Final DRC
vf, uf, sf = run_drc()
print(f"Final DRC: V={vf} U={uf} S={sf}")
