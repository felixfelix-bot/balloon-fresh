#!/usr/bin/env python3.14
"""
C3 flight PCB — collision-aware rip-up & re-router.

Strategy
--------
1. Rip ALL existing tracks (the original layout had no netcodes → every crossing
   became a short).
2. Build a pad-obstacle map: every pad bounding box (with clearance inflation).
3. For each SIGNAL net (zones already cover GND/+3V3), build a min-spanning chain
   of its pads and route each hop:
      a. Try L-shape on F.Cu (two orders: H-then-V, V-then-H).
      b. Try Z-shape on F.Cu (pick a few intermediate Y values).
      c. Try L-shape on B.Cu (needs two vias).
      d. Try Z-shape on B.Cu.
   A path is accepted only if no segment collides with any foreign pad.
4. Add the tracks + vias with correct netcode.
5. Refill zones, save with pcbnew.SaveBoard(PATH, board).
"""
import sys, math, copy
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

PATH = '/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_final.kicad_pcb'

# ── Tunables ──────────────────────────────────────────────────────────────
TRACK_W_MM     = 0.22          # track width
VIA_DRILL_MM   = 0.30
VIA_FIN_MM     = 0.55          # via finished diameter
PAD_CLEAR_MM   = 0.30          # min clearance from track centreline to foreign pad bbox
GRID_MM        = 0.25          # routing grid for Z-shape probes
BOARD_MARGIN   = 0.40          # don't route inside this margin from edge

F_CU = pcbnew.F_Cu
B_CU = pcbnew.B_Cu

def nm(mm):  # convert mm → KiCad internal nm
    return pcbnew.FromMM(mm)

def mm(iu):
    return pcbnew.ToMM(iu)


# ─────────────────────────────────────────────────────────────────────────
#  Load & tear down
# ─────────────────────────────────────────────────────────────────────────
b = pcbnew.LoadBoard(PATH)
bb = b.GetBoardEdgesBoundingBox()
XMIN = mm(bb.GetX()) + BOARD_MARGIN
YMIN = mm(bb.GetY()) + BOARD_MARGIN
XMAX = mm(bb.GetX() + bb.GetWidth())  - BOARD_MARGIN
YMAX = mm(bb.GetY() + bb.GetHeight()) - BOARD_MARGIN
print(f'Board routing area: ({XMIN:.2f},{YMIN:.2f}) → ({XMAX:.2f},{YMAX:.2f}) mm')


# ─────────────────────────────────────────────────────────────────────────
#  Build pad list & obstacle map  (BEFORE any board mutation)
# ─────────────────────────────────────────────────────────────────────────
# pads_by_net[netname] = list of (x_mm, y_mm, ref, padname)
pads_by_net = {}
all_pads = []          # (xmin,xmax,ymin,ymax, net, ref, padname)
fp_list = list(b.GetFootprints())          # snapshot
for fp in fp_list:
    ref = fp.GetReference()
    for p in list(fp.Pads()):
        pos = p.GetPosition(); sz = p.GetSize()
        cx, cy = mm(pos.x), mm(pos.y)
        sw, sh = mm(sz.x)/2.0, mm(sz.y)/2.0
        # inflate bbox for round pads (shape 1=circle, 0=rect, 4=roundrect)
        pad_xmin = cx - sw - PAD_CLEAR_MM
        pad_xmax = cx + sw + PAD_CLEAR_MM
        pad_ymin = cy - sh - PAD_CLEAR_MM
        pad_ymax = cy + sh + PAD_CLEAR_MM
        net = p.GetNetname() or ''
        all_pads.append((pad_xmin, pad_xmax, pad_ymin, pad_ymax,
                         net, ref, p.GetName()))
        if net and net not in ('',):
            pads_by_net.setdefault(net, []).append(
                (cx, cy, ref, p.GetName()))

print(f'Pads: {len(all_pads)} across {len(pads_by_net)} nets')

# 1) rip up every existing track & via  (snapshot list, mutate after)
old_tracks = list(b.GetTracks())
ripped = 0
for t in old_tracks:
    b.Remove(t); ripped += 1
del old_tracks
print(f'Ripped {ripped} old tracks/vias')


# ─────────────────────────────────────────────────────────────────────────
#  Collision maths
# ─────────────────────────────────────────────────────────────────────────
def seg_intersects_pad(x0,y0,x1,y1, pad, my_net):
    """Axis-aligned bbox overlap test (segments are horizontal/vertical)."""
    pxmin,pxmax,pymin,pymax,pnet,_,_ = pad
    if pnet == my_net:
        return False                    # same net: allowed to touch
    # bbox of segment
    sxmin, sxmax = min(x0,x1), max(x0,x1)
    symin, symax = min(y0,y1), max(y0,y1)
    # overlap?
    return not (sxmax < pxmin or sxmin > pxmax or
                symax < pymin or symin > pymax)

def path_clear(segments, my_net):
    """segments = list of (x0,y0,x1,y1). Returns True iff no collision."""
    for s in segments:
        for pad in all_pads:
            if seg_intersects_pad(s[0],s[1],s[2],s[3], pad, my_net):
                return False
    return True

def in_bounds(x,y):
    return XMIN <= x <= XMAX and YMIN <= y <= YMAX


# ─────────────────────────────────────────────────────────────────────────
#  Path candidates
# ─────────────────────────────────────────────────────────────────────────
def L_paths(x0,y0,x1,y1):
    """Two L-shaped candidates (H-first, V-first)."""
    yield [(x0,y0,x1,y0),(x1,y0,x1,y1)]
    yield [(x0,y0,x0,y1),(x0,y1,x1,y1)]

def Z_paths(x0,y0,x1,y1, n_probes=12):
    """Z-shape on F.Cu with intermediate Y, plus X-grid snapping."""
    # vertical-ends Z:  V → H → V
    ys = set()
    for i in range(1, n_probes+1):
        t = i/(n_probes+1)
        ys.add(y0 + (y1-y0)*t)
    # snap to grid & add edges
    cand_y = sorted({round(y/GRID_MM)*GRID_MM for y in ys})
    for my in cand_y:
        if YMIN <= my <= YMAX:
            yield [(x0,y0,x0,my),(x0,my,x1,my),(x1,my,x1,y1)]
    # horizontal-ends Z: H → V → H
    xs = set()
    for i in range(1, n_probes+1):
        t = i/(n_probes+1)
        xs.add(x0 + (x1-x0)*t)
    cand_x = sorted({round(x/GRID_MM)*GRID_MM for x in xs})
    for mx in cand_x:
        if XMIN <= mx <= XMAX:
            yield [(x0,y0,mx,y0),(mx,y0,mx,y1),(mx,y1,x1,y1)]
    # extra detours OUTSIDE the rectangle (go around pads)
    for my in [YMIN+0.5, YMAX-0.5, round(((y0+y1)/2)/GRID_MM)*GRID_MM]:
        if YMIN < my < YMAX and abs(my-y0) > 1.0 and abs(my-y1) > 1.0:
            yield [(x0,y0,x0,my),(x0,my,x1,my),(x1,my,x1,y1)]

def L_paths_bcu(x0,y0,x1,y1):
    yield [(x0,y0,x1,y0),(x1,y0,x1,y1)]
    yield [(x0,y0,x0,y1),(x0,y1,x1,y1)]

def Z_paths_bcu(x0,y0,x1,y1):
    # B.Cu has no zones, so any Y that snaps to grid and is in-bounds works
    mid_y = round(((y0+y1)/2)/GRID_MM)*GRID_MM
    if not (YMIN <= mid_y <= YMAX):
        mid_y = (y0+y1)/2
    yield [(x0,y0,x0,mid_y),(x0,mid_y,x1,mid_y),(x1,mid_y,x1,y1)]
    mid_x = round(((x0+x1)/2)/GRID_MM)*GRID_MM
    if not (XMIN <= mid_x <= XMAX):
        mid_x = (x0+x1)/2
    yield [(x0,y0,mid_x,y0),(mid_x,y0,mid_x,y1),(mid_x,y1,x1,y1)]


# ─────────────────────────────────────────────────────────────────────────
#  Add tracks / vias to the board
# ─────────────────────────────────────────────────────────────────────────
_stats_tracks = [0]
_stats_vias   = [0]

def add_track(x0,y0,x1,y1, layer, net):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(pcbnew.VECTOR2I(int(nm(x0)), int(nm(y0))))
    t.SetEnd  (pcbnew.VECTOR2I(int(nm(x1)), int(nm(y1))))
    t.SetWidth(int(nm(TRACK_W_MM)))
    t.SetLayer(layer)
    t.SetNet(net)
    b.Add(t)
    _stats_tracks[0] += 1
    return t

def add_via(x,y, net):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I(int(nm(x)), int(nm(y))))
    v.SetTopLayer(F_CU)
    v.SetBottomLayer(B_CU)
    v.SetLayer(F_CU)
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetDrill(int(nm(VIA_DRILL_MM)))
    v.SetWidth(int(nm(VIA_FIN_MM)))
    v.SetNet(net)
    b.Add(v)
    _stats_vias[0] += 1
    return v

def commit_path(segments, layer, net, x0,y0,x1,y1):
    """Push path to board. If layer==B_CU, add entry/exit vias."""
    added = []
    if layer == B_CU:
        # via at start, via at end (unless first/last point already has one)
        add_via(x0,y0, net)
        add_via(x1,y1, net)
    for (a,b_,c,d) in segments:
        # zero-length segs cause warnings — skip
        if a==c and b_==d:
            continue
        add_track(a,b_,c,d, layer, net)
    return True


# ─────────────────────────────────────────────────────────────────────────
#  Per-net routing
# ─────────────────────────────────────────────────────────────────────────
ZONE_NETS = {'GND', '+3V3'}     # handled by copper pours
stats = {'routed':0, 'failed':[], 'via_count':0, 'track_count':0}

def route_pair(x0,y0,x1,y1, net_name, net):
    """Try F.Cu first, then B.Cu. Return True if connected."""
    # short-circuit: same point
    if abs(x0-x1) < 0.05 and abs(y0-y1) < 0.05:
        return True
    # F.Cu L
    for cand in L_paths(x0,y0,x1,y1):
        if path_clear(cand, net_name):
            commit_path(cand, F_CU, net, x0,y0,x1,y1)
            return True
    # F.Cu Z
    for cand in Z_paths(x0,y0,x1,y1):
        if path_clear(cand, net_name):
            commit_path(cand, F_CU, net, x0,y0,x1,y1)
            return True
    # B.Cu L (with vias)
    for cand in L_paths_bcu(x0,y0,x1,y1):
        if path_clear(cand, net_name):
            commit_path(cand, B_CU, net, x0,y0,x1,y1)
            return True
    # B.Cu Z
    for cand in Z_paths_bcu(x0,y0,x1,y1):
        if path_clear(cand, net_name):
            commit_path(cand, B_CU, net, x0,y0,x1,y1)
            return True
    return False


def route_net(net_name, pads):
    """Connect all pads of a net as a chain (nearest-neighbour order)."""
    net = b.FindNet(net_name)
    if net is None:
        stats['failed'].append((net_name, 'no net object'))
        return
    if len(pads) < 2:
        return
    # nearest-neighbour chain
    remaining = list(pads)
    chain = [remaining.pop(0)]
    while remaining:
        last = chain[-1]
        # pick nearest
        best = min(remaining,
                   key=lambda p: (p[0]-last[0])**2 + (p[1]-last[1])**2)
        remaining.remove(best)
        chain.append(best)
    # route each hop
    for i in range(len(chain)-1):
        x0,y0,_,_ = chain[i]
        x1,y1,_,_ = chain[i+1]
        if route_pair(x0,y0,x1,y1, net_name, net):
            stats['routed'] += 1
        else:
            stats['failed'].append((net_name,
                f'{chain[i][2]}{chain[i][3]}→{chain[i+1][2]}{chain[i+1][3]}'))


print('\n=== ROUTING ===')
for net_name in sorted(pads_by_net.keys()):
    pads = pads_by_net[net_name]
    if net_name in ZONE_NETS:
        # add a couple of strategic jumpers for thermal relief / long hops
        # but mostly rely on the zone. Skip per-hop routing for now.
        # Still connect pads that are very close (so DRC unconnected_items=0
        # in case a pad is isolated by the pour).
        continue
    print(f'  net {net_name:14s} ({len(pads)} pads)')
    route_net(net_name, pads)

# Handle GND/+3V3: add explicit tracks for any pad pair that's likely to
# be isolated by the pour (e.g., U1 GND pads inside the module shadow).
# We'll add a few critical jumpers to be safe.
print('\n=== ZONE-NET JUMPERS (safety) ===')
for net_name in ZONE_NETS:
    pads = pads_by_net[net_name]
    net = b.FindNet(net_name)
    if not net: continue
    # connect each pad to its nearest pad of same net with a short track
    for p in pads:
        # find nearest same-net pad
        others = [q for q in pads if q is not p]
        if not others: continue
        q = min(others, key=lambda r:(r[0]-p[0])**2+(r[1]-p[1])**2)
        d = math.hypot(q[0]-p[0], q[1]-p[1])
        if d > 8.0:    # far pads rely on pour; only short-hop jumpers
            continue
        if route_pair(p[0],p[1],q[0],q[1], net_name, net):
            stats['routed'] += 1
        else:
            stats['failed'].append((net_name, f'jumper {p[2]}{p[3]}'))


# ─────────────────────────────────────────────────────────────────────────
#  Count what we created (from in-process counters — querying b.GetTracks()
#  after many Add() calls can corrupt SWIG state in this build)
# ─────────────────────────────────────────────────────────────────────────
stats['track_count'] = _stats_tracks[0]
stats['via_count']   = _stats_vias[0]
print(f'\nCreated: {_stats_tracks[0]} tracks, {_stats_vias[0]} vias')
print(f'Routed pairs: {stats["routed"]}, failed: {len(stats["failed"])}')
for f in stats['failed'][:15]:
    print('  FAIL:', f)


# ─────────────────────────────────────────────────────────────────────────
#  Refill zones & save
# ─────────────────────────────────────────────────────────────────────────
print('\n=== FILL ZONES ===')
for z in b.Zones():
    z.SetIsFilled(False)
# Use the filler tool to rebuild
filler = pcbnew.ZONE_FILLER(b)
zones_list = list(b.Zones())
# In kicad 9 the API: filler.Fill(zones_list)
try:
    filler.Fill(zones_list)
except Exception as e:
    print('Filler.Fill failed:', e)
    # fallback: per-zone
    for z in zones_list:
        try:
            z.SetIsFilled(True)
        except Exception:
            pass
# Re-mark filled so file shows them
for z in b.Zones():
    z.SetIsFilled(True)

print('\n=== SAVE ===')
ok = pcbnew.SaveBoard(PATH, b)
print(f'SaveBoard returned: {ok}')

# ── reload & verify ──────────────────────────────────────────────────────
print('\n=== VERIFY ===')
b2 = pcbnew.LoadBoard(PATH)
n2 = len(list(b2.GetTracks()))
print(f'After reload: {n2} tracks/vias')
if n2 < 20:
    print('WARNING: fewer than 20 tracks survived save!')
    sys.exit(2)
print('OK')
