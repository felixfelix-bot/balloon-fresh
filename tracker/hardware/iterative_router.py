#!/usr/bin/env python3
"""
Iterative DRC-verified router for V2-ADC balloon PCB.

Loads v2_adc_final.kicad_pcb, adds tracks/vias for unconnected nets,
runs DRC after each net, rolls back if violations increase.

Usage:
    /usr/bin/python3.14 iterative_router.py
"""
import sys, os, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pcbnew
from pcbnew import (
    F_Cu, B_Cu, VECTOR2I_MM, FromMM, PCB_TRACK, PCB_VIA, VIATYPE_THROUGH
)

BOARD_PATH = "/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v2_adc_final.kicad_pcb"
DRC_JSON = "/tmp/iter_drc.json"

# Widths (KiCad internal units)
WIDTH_POWER  = FromMM(0.40)
WIDTH_SIGNAL = FromMM(0.25)
WIDTH_RF     = FromMM(0.76)
VIA_SIZE     = FromMM(0.6)
VIA_DRILL    = FromMM(0.3)


# ============================================================
# Helpers
# ============================================================

def get_net_by_name(board, name):
    for code, net in board.GetNetsByNetcode().items():
        if net.GetNetname() == name:
            return net
    raise KeyError(f"Net {name!r} not found")


def run_drc(pcb_path=BOARD_PATH, out=DRC_JSON):
    cmd = ["kicad-cli", "pcb", "drc", "--format", "json", "--output", out, pcb_path]
    subprocess.run(cmd, capture_output=True, text=True)
    if not os.path.exists(out):
        return None
    with open(out) as f:
        return json.load(f)


def count_violations(drc):
    if drc is None:
        return (999, 999, 999)
    v = drc.get('violations', [])
    shorting = [x for x in v if 'short' in x.get('type', '').lower()]
    return (len(v), len(shorting), len(drc.get('unconnected_items', [])))


def add_track(board, net, x1, y1, x2, y2, layer, width=WIDTH_SIGNAL):
    t = PCB_TRACK(board)
    t.SetStart(VECTOR2I_MM(float(x1), float(y1)))
    t.SetEnd(VECTOR2I_MM(float(x2), float(y2)))
    t.SetWidth(width)
    t.SetLayer(layer)
    t.SetNet(net)
    board.Add(t)
    return t


def add_via(board, net, x, y, size=VIA_SIZE, drill=VIA_DRILL):
    v = PCB_VIA(board)
    v.SetPosition(VECTOR2I_MM(float(x), float(y)))
    v.SetDrill(drill)
    v.SetWidth(size)
    v.SetNet(net)
    v.SetViaType(VIATYPE_THROUGH)
    board.Add(v)
    return v


def remove_objects(board, objs):
    for o in objs:
        try:
            board.Remove(o)
        except Exception:
            pass


# ============================================================
# Routing strategies (each returns list of added objects)
# ============================================================

def strategy_direct(board, net, pairs, width):
    out = []
    for (x1, y1, x2, y2) in pairs:
        out.append(add_track(board, net, x1, y1, x2, y2, F_Cu, width))
    return out


def strategy_L(board, net, pairs, width):
    """Horizontal then vertical."""
    out = []
    for (x1, y1, x2, y2) in pairs:
        out.append(add_track(board, net, x1, y1, x2, y1, F_Cu, width))
        out.append(add_track(board, net, x2, y1, x2, y2, F_Cu, width))
    return out


def strategy_L2(board, net, pairs, width):
    """Vertical then horizontal."""
    out = []
    for (x1, y1, x2, y2) in pairs:
        out.append(add_track(board, net, x1, y1, x1, y2, F_Cu, width))
        out.append(add_track(board, net, x1, y2, x2, y2, F_Cu, width))
    return out


def strategy_Z(board, net, pairs, width, mid_frac=0.5):
    """H-V-H with mid x at fraction."""
    out = []
    for (x1, y1, x2, y2) in pairs:
        mx = x1 + mid_frac * (x2 - x1)
        out.append(add_track(board, net, x1, y1, mx, y1, F_Cu, width))
        out.append(add_track(board, net, mx, y1, mx, y2, F_Cu, width))
        out.append(add_track(board, net, mx, y2, x2, y2, F_Cu, width))
    return out


def strategy_Zv(board, net, pairs, width, mid_frac=0.5):
    """V-H-V with mid y at fraction."""
    out = []
    for (x1, y1, x2, y2) in pairs:
        my = y1 + mid_frac * (y2 - y1)
        out.append(add_track(board, net, x1, y1, x1, my, F_Cu, width))
        out.append(add_track(board, net, x1, my, x2, my, F_Cu, width))
        out.append(add_track(board, net, x2, my, x2, y2, F_Cu, width))
    return out


def strategy_via_direct(board, net, pairs, width):
    """Drop via at each pad, straight B.Cu track between."""
    out = []
    for (x1, y1, x2, y2) in pairs:
        out.append(add_via(board, net, x1, y1))
        out.append(add_via(board, net, x2, y2))
        out.append(add_track(board, net, x1, y1, x2, y2, B_Cu, width))
    return out


def strategy_via_L(board, net, pairs, width):
    """Via at each pad, L-path on B.Cu."""
    out = []
    for (x1, y1, x2, y2) in pairs:
        out.append(add_via(board, net, x1, y1))
        out.append(add_via(board, net, x2, y2))
        out.append(add_track(board, net, x1, y1, x2, y1, B_Cu, width))
        out.append(add_track(board, net, x2, y1, x2, y2, B_Cu, width))
    return out


def strategy_via_L2(board, net, pairs, width):
    """Via at each pad, L-path V-then-H on B.Cu."""
    out = []
    for (x1, y1, x2, y2) in pairs:
        out.append(add_via(board, net, x1, y1))
        out.append(add_via(board, net, x2, y2))
        out.append(add_track(board, net, x1, y1, x1, y2, B_Cu, width))
        out.append(add_track(board, net, x1, y2, x2, y2, B_Cu, width))
    return out


def strategy_via_Z(board, net, pairs, width, mid_frac=0.5):
    out = []
    for (x1, y1, x2, y2) in pairs:
        mx = x1 + mid_frac * (x2 - x1)
        out.append(add_via(board, net, x1, y1))
        out.append(add_via(board, net, x2, y2))
        out.append(add_track(board, net, x1, y1, mx, y1, B_Cu, width))
        out.append(add_track(board, net, mx, y1, mx, y2, B_Cu, width))
        out.append(add_track(board, net, mx, y2, x2, y2, B_Cu, width))
    return out


# Strategy list (in priority order)
STRATEGIES = [
    ('direct',      strategy_direct),
    ('L',           strategy_L),
    ('L2',          strategy_L2),
    ('Z_50',        lambda b,n,p,w: strategy_Z(b,n,p,w,0.5)),
    ('Z_70',        lambda b,n,p,w: strategy_Z(b,n,p,w,0.7)),
    ('Z_30',        lambda b,n,p,w: strategy_Z(b,n,p,w,0.3)),
    ('Zv_50',       lambda b,n,p,w: strategy_Zv(b,n,p,w,0.5)),
    ('Zv_70',       lambda b,n,p,w: strategy_Zv(b,n,p,w,0.7)),
    ('Zv_30',       lambda b,n,p,w: strategy_Zv(b,n,p,w,0.3)),
    ('via_direct',  strategy_via_direct),
    ('via_L',       strategy_via_L),
    ('via_L2',      strategy_via_L2),
    ('via_Z_50',    lambda b,n,p,w: strategy_via_Z(b,n,p,w,0.5)),
    ('via_Z_70',    lambda b,n,p,w: strategy_via_Z(b,n,p,w,0.7)),
    ('via_Z_30',    lambda b,n,p,w: strategy_via_Z(b,n,p,w,0.3)),
]


def route_one_net(board, net_name, pairs, width, verbose=False):
    """Try strategies until one doesn't increase violations or shorts."""
    net = get_net_by_name(board, net_name)

    # Baseline
    pcbnew.SaveBoard(BOARD_PATH, board)
    drc = run_drc()
    base_v, base_s, _ = count_violations(drc)
    if verbose:
        print(f"  baseline: V={base_v} S={base_s}")

    for strat_name, strat_fn in STRATEGIES:
        if verbose:
            print(f"  try {strat_name}...")
        added = []
        try:
            added = strat_fn(board, net, pairs, width)
        except Exception as e:
            if verbose:
                print(f"    exception: {e}")
            added = []
        if not added:
            continue
        pcbnew.SaveBoard(BOARD_PATH, board)
        drc = run_drc()
        new_v, new_s, _ = count_violations(drc)
        if verbose:
            print(f"    -> V={new_v} (was {base_v}) S={new_s} (was {base_s})")
        if new_s == 0 and new_v <= base_v:
            return True, strat_name, added
        # Reject: rollback
        remove_objects(board, added)
        pcbnew.SaveBoard(BOARD_PATH, board)

    return False, None, []


# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    print("=" * 60)
    print("Iterative DRC-verified router")
    print("=" * 60)
    board = pcbnew.LoadBoard(BOARD_PATH)
    print(f"Loaded: {len(list(board.Tracks()))} tracks, {len(list(board.Footprints()))} footprints")

    # Initial baseline
    drc = run_drc()
    v, s, u = count_violations(drc)
    print(f"Initial: V={v} S={s} U={u}")

    # Routing plan: ordered for best results (small/short nets first,
    # then big fanouts like GND)
    routing_plan = [
        # name,           [(x1,y1,x2,y2), ...],             width
        ('VDIV_MID',      [(2.5, 32.0, 3.5, 30.0)],          WIDTH_SIGNAL),
        ('STATUS_LED',    [(15.0, 15.5, 18.5, 4.0)],         WIDTH_SIGNAL),
        ('SOLAR_IN',      [(1.73, 37.0, 3.0, 18.0)],         WIDTH_POWER),
        ('VCAP',          [(4.05, 21.25, 7.5, 37.0)],        WIDTH_POWER),
        ('GPS_RX',        [(8.5, 9.75, 6.7, 33.0)],          WIDTH_SIGNAL),
        ('SPI_MOSI',      [(12.0, 15.5, 15.1, 23.0)],        WIDTH_SIGNAL),
        ('LR2021_BUSY',   [(8.5, 14.25, 15.1, 29.0)],        WIDTH_SIGNAL),
        ('LR2021_DIO9',   [(8.5, 15.75, 34.9, 23.0)],        WIDTH_SIGNAL),
        ('3V3_pair1',     [(15.5, 8.25, 4.0, 33.0)],         WIDTH_POWER),
        ('3V3_pair2',     [(15.5, 8.25, 40.0, 25.0)],        WIDTH_POWER),
        # GND: connect all 6 GND pads pairwise to U1 GND pad at (15.5, 9.75)
        ('GND_pair1',     [(15.5, 9.75, 5.0, 21.25)],        WIDTH_POWER),
        ('GND_pair2',     [(15.5, 9.75, 3.5, 32.0)],         WIDTH_POWER),
        ('GND_pair3',     [(15.5, 9.75, 9.5, 14.0)],         WIDTH_POWER),
        ('GND_pair4',     [(15.5, 9.75, 16.5, 4.0)],         WIDTH_POWER),
        ('RF_SUB_868',    [(15.1, 33.0, 46.0, 25.0)],        WIDTH_RF),
        ('RF_2G4_2400',   [(34.9, 33.0, 46.0, 30.0)],        WIDTH_RF),
    ]

    # Map aliases to real net names
    NET_ALIASES = {
        '3V3_pair1':   '3V3',
        '3V3_pair2':   '3V3',
        'GND_pair1':   'GND',
        'GND_pair2':   'GND',
        'GND_pair3':   'GND',
        'GND_pair4':   'GND',
    }

    summary = []
    skip_streak = 0
    for label, pairs, width in routing_plan:
        net_name = NET_ALIASES.get(label, label)
        print(f"\n--- {label} (net={net_name}) ---")
        success, strategy, added = route_one_net(board, net_name, pairs, width, verbose=True)
        if success:
            print(f"  ✓ {label} -> {strategy}, +{len(added)} objects")
            summary.append((label, net_name, 'OK', strategy, len(added)))
            skip_streak = 0
        else:
            print(f"  ✗ {label} FAILED all strategies")
            summary.append((label, net_name, 'FAIL', None, 0))
            skip_streak += 1
            if skip_streak >= 3:
                print("\n!! CIRCUIT BREAKER: 3 consecutive failures, stopping routing.")
                break

    # Final DRC report
    pcbnew.SaveBoard(BOARD_PATH, board)
    drc = run_drc()
    v, s, u = count_violations(drc)
    print("\n" + "=" * 60)
    print("FINAL STATE")
    print("=" * 60)
    print(f"Violations: {v} | Shorts: {s} | Unconnected: {u}")
    print("\nRouting summary:")
    for label, net, status, strat, count in summary:
        print(f"  {label:18s} {net:14s} {status:5s} strat={strat} +{count}")
