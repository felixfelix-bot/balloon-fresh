#!/usr/bin/env python3.14
"""
Route 3V3 and GND power nets on balloon tracker boards using explicit
nearest-neighbor chain tracks on F.Cu.

Strategy: for each power net, gather all pads, order them by nearest-neighbor
greedy walk from the first pad, and connect each consecutive pair with an
L-shaped (Manhattan) track. Use a thick width for current capacity.

Also for V1: nudge U1.GPIO5 (LR2021_DIO9) down 0.5 mm to clear the U1.GPIO6
(SPI_SCK) corner-pad overlap that creates a solder_mask_bridge / shorting_items
DRC violation.
"""
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew
import math

POWER_NETS = ('3V3', 'GND')
TRACK_WIDTH_NM = int(0.6e6)   # 0.6 mm power track
CLEARANCE_PAD  = int(0.2e6)   # approach pad center to its edge by this offset
NM = 1_000_000                # 1 mm in nm

def v2i(x_mm, y_mm):
    return pcbnew.VECTOR2I(int(x_mm * NM), int(y_mm * NM))

def dist(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])

def collect_pads(board, netname):
    """Return list of (ref, padname, x_mm, y_mm, pad_obj) for all pads on net."""
    out = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == netname:
                pos = p.GetPosition()
                out.append((fp.GetReference(), p.GetName(),
                            pos.x / NM, pos.y / NM, p))
    return out

def nearest_neighbor_chain(pads):
    """Order pads by greedy nearest-neighbor walk. Returns ordered list."""
    if not pads:
        return []
    remaining = list(pads)
    ordered = [remaining.pop(0)]
    while remaining:
        last = ordered[-1]
        last_xy = (last[2], last[3])
        best_i = min(range(len(remaining)),
                     key=lambda i: dist(last_xy, (remaining[i][2], remaining[i][3])))
        ordered.append(remaining.pop(best_i))
    return ordered

def add_l_track(board, net, layer, x1, y1, x2, y2, width_nm=TRACK_WIDTH_NM):
    """Add an L-shaped track (horizontal then vertical) from p1 to p2."""
    # Corner point: route horizontally first, then vertically
    cx, cy = x2, y1
    segs = []
    # Horizontal segment (if non-zero)
    if abs(x2 - x1) > 1e-3:
        t = pcbnew.PCB_TRACK(board)
        t.SetNet(net)
        t.SetLayer(layer)
        t.SetWidth(width_nm)
        t.SetStart(v2i(x1, y1))
        t.SetEnd(v2i(cx, cy))
        board.Add(t)
        segs.append(t)
    # Vertical segment (if non-zero)
    if abs(y2 - y1) > 1e-3:
        t = pcbnew.PCB_TRACK(board)
        t.SetNet(net)
        t.SetLayer(layer)
        t.SetWidth(width_nm)
        t.SetStart(v2i(cx, cy))
        t.SetEnd(v2i(x2, y2))
        board.Add(t)
        segs.append(t)
    return segs

def route_power_net(board, netname, layer=pcbnew.F_Cu):
    """Route all pads of netname as nearest-neighbor chain with L-tracks."""
    net = board.FindNet(netname)
    if not net:
        print(f'  [WARN] net {netname!r} not found on board')
        return 0
    pads = collect_pads(board, netname)
    print(f'  {netname}: {len(pads)} pads')
    for ref, pn, x, y, _ in pads:
        print(f'    {ref}.{pn} @ ({x:.2f},{y:.2f})')
    if len(pads) < 2:
        return 0
    chain = nearest_neighbor_chain(pads)
    n_added = 0
    for i in range(len(chain) - 1):
        a = chain[i]
        b = chain[i+1]
        segs = add_l_track(board, net, layer, a[2], a[3], b[2], b[3])
        n_added += len(segs)
    return n_added

def fix_v1_short(board):
    """Nudge U1.GPIO5 pad down to eliminate overlap with U1.GPIO6."""
    for fp in board.GetFootprints():
        if fp.GetReference() != 'U1':
            continue
        for p in fp.Pads():
            if p.GetName() == 'GPIO5':
                pos = p.GetPosition()
                old = (pos.x / NM, pos.y / NM)
                # Move down by 0.5 mm to clear GPIO6 corner pad
                new_pos = v2i(old[0], old[1] + 0.5)
                p.SetPosition(new_pos)
                # Also need to update the pad's position in the footprint
                # local coords. SetPosition sets board-absolute; the
                # footprint handles relative coords via SetLocalCoord where
                # available.
                try:
                    rel = pcbnew.VECTOR2I(int((old[0]) * NM), int((old[1] + 0.5) * NM))
                    # Compute local: position relative to footprint origin
                    fp_pos = fp.GetPosition()
                    local_x = int(old[0] * NM) - fp_pos.x
                    local_y = int((old[1] + 0.5) * NM) - fp_pos.y
                    p.SetLocalCoord(pcbnew.VECTOR2I(local_x, local_y))
                    print(f'  GPIO5 local coord set to ({local_x/NM:.2f},{local_y/NM:.2f})')
                except Exception as ex:
                    print(f'  GPIO5 SetLocalCoord failed (will rely on SetPosition): {ex}')
                new = (p.GetPosition().x / NM, p.GetPosition().y / NM)
                print(f'  U1.GPIO5 (LR2021_DIO9) moved {old} -> {new}')
                return True
    return False

def process_board(path, label, do_short_fix=False):
    print(f'\n{"="*70}\nProcessing {label}: {path}\n{"="*70}')
    board = pcbnew.LoadBoard(path)

    if do_short_fix:
        print('Fixing V1 GPIO5/GPIO6 pad overlap...')
        if fix_v1_short(board):
            print('  OK')
        else:
            print('  U1 not found!')

    for netname in POWER_NETS:
        print(f'\nRouting {netname}...')
        n = route_power_net(board, netname)
        print(f'  Added {n} track segments')

    # Save
    pcbnew.SaveBoard(path, board)
    print(f'\nSaved: {path}')

    # Report track counts
    tracks = list(board.GetTracks())
    from collections import Counter
    cnt = Counter(t.GetNetname() for t in tracks)
    print(f'Total tracks on board: {len(tracks)}')
    for n, c in sorted(cnt.items(), key=lambda x: -x[1]):
        print(f'  {c:4d}  {n}')

if __name__ == '__main__':
    base = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output'

    # V2-ADC first (simpler — already has partial routing)
    process_board(f'{base}/v2_adc_routed.kicad_pcb', 'V2-ADC', do_short_fix=False)

    # V1-FAST (also needs the short fix)
    process_board(f'{base}/v1_fast_routed.kicad_pcb', 'V1-FAST', do_short_fix=True)

    print('\n\nDONE. Run DRC to verify.')
