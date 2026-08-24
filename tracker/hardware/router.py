#!/usr/bin/env python3
"""Clearance-aware router for text-generated KiCad 9 PCBs.

Provides collision detection between traces, pads, and vias on the same layer.
Finds alternative routes (detours, layer switches) when direct placement
would cause a DRC violation.

Usage:
    router = Router(board_w=50, board_h=40, clearance=0.3)
    router.add_pad(9.46, 3.11, 1.7, 1.7, net_id=1)
    router.route(5, 20, 38, 20, net_id=1, width=0.5, layer="F.Cu")
    router.route(5, 20, 5, 35, net_id=2, width=0.5, layer="F.Cu")  # checked!
    output = router.emit()  # KiCad segment/via text
"""

import math
import uuid as uuid_mod
from dataclasses import dataclass, field
from typing import Optional

# ============================================================
# Geometry functions
# ============================================================

def point_to_seg_dist(px, py, x1, y1, x2, y2):
    """Distance from point (px,py) to segment (x1,y1)-(x2,y2)."""
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.sqrt((px - x1) ** 2 + (py - y1) ** 2)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    cx, cy = x1 + t * dx, y1 + t * dy
    return math.sqrt((px - cx) ** 2 + (py - cy) ** 2)


def seg_to_seg_dist(x1, y1, x2, y2, x3, y3, x4, y4):
    """Minimum distance between two line segments using parametric clamping."""
    # First check if they actually intersect
    if _segments_intersect(x1, y1, x2, y2, x3, y3, x4, y4):
        return 0.0
    d1 = point_to_seg_dist(x1, y1, x3, y3, x4, y4)
    d2 = point_to_seg_dist(x2, y2, x3, y3, x4, y4)
    d3 = point_to_seg_dist(x3, y3, x1, y1, x2, y2)
    d4 = point_to_seg_dist(x4, y4, x1, y1, x2, y2)
    return min(d1, d2, d3, d4)


def seg_to_rect_dist(x1, y1, x2, y2, rx, ry, rw, rh):
    """Distance from segment to axis-aligned rectangle (pad).
    
    Rectangle is centered at (rx, ry) with half-widths rw/2, rh/2.
    Actually rectangle spans from (rx-rw/2, ry-rh/2) to (rx+rw/2, ry+rh/2).
    """
    # Rectangle bounds
    rx_min = rx - rw / 2
    rx_max = rx + rw / 2
    ry_min = ry - rh / 2
    ry_max = ry + rh / 2
    
    # Check if segment intersects rectangle
    # Use Cohen-Sutherland-like approach: check if any segment point is inside,
    # or if segment crosses any rectangle edge
    
    # Check endpoints inside rect
    def inside(x, y):
        return rx_min <= x <= rx_max and ry_min <= y <= ry_max
    
    if inside(x1, y1) or inside(x2, y2):
        return 0.0
    
    # Check intersection with 4 rect edges
    edges = [
        (rx_min, ry_min, rx_max, ry_min),  # bottom
        (rx_max, ry_min, rx_max, ry_max),  # right
        (rx_max, ry_max, rx_min, ry_max),  # top
        (rx_min, ry_max, rx_min, ry_min),  # left
    ]
    for ex1, ey1, ex2, ey2 in edges:
        if _segments_intersect(x1, y1, x2, y2, ex1, ey1, ex2, ey2):
            return 0.0
    
    # Not intersecting — find minimum distance to rect edges
    min_d = float('inf')
    for ex1, ey1, ex2, ey2 in edges:
        d = seg_to_seg_dist(x1, y1, x2, y2, ex1, ey1, ex2, ey2)
        min_d = min(min_d, d)
    return min_d


def _segments_intersect(x1, y1, x2, y2, x3, y3, x4, y4):
    """Check if two segments intersect (proper crossing)."""
    def cross(ox, oy, ax, ay, bx, by):
        return (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)
    
    d1 = cross(x3, y3, x4, y4, x1, y1)
    d2 = cross(x3, y3, x4, y4, x2, y2)
    d3 = cross(x1, y1, x2, y2, x3, y3)
    d4 = cross(x1, y1, x2, y2, x4, y4)
    
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True
    return False


def manhattan_route_points(x1, y1, x2, y2, prefer="H"):
    """Generate L-shaped Manhattan routing waypoints.
    
    prefer="H": horizontal first, then vertical
    prefer="V": vertical first, then horizontal
    """
    if prefer == "H":
        return [(x1, y1), (x2, y1), (x2, y2)]
    else:
        return [(x1, y1), (x1, y2), (x2, y2)]


# ============================================================
# Data classes
# ============================================================

@dataclass
class TraceSegment:
    x1: float
    y1: float
    x2: float
    y2: float
    net: int
    width: float
    layer: str
    uuid: str = field(default_factory=lambda: str(uuid_mod.uuid4()))


@dataclass
class Via:
    x: float
    y: float
    net: int
    size: float = 0.6
    drill: float = 0.3
    uuid: str = field(default_factory=lambda: str(uuid_mod.uuid4()))


@dataclass
class Pad:
    x: float
    y: float
    w: float
    h: float
    net: int
    layer: str = "F.Cu"


# ============================================================
# Router
# ============================================================

class Router:
    """Clearance-aware router for text-generated KiCad PCBs.
    
    Tracks all placed copper (traces, vias, pads) and checks clearance
    before placing new traces. When blocked, attempts detours or
    layer switches.
    """

    def __init__(self, board_w, board_h, clearance=0.3, grid=0.5):
        self.w = board_w
        self.h = board_h
        self.clearance = clearance
        self.grid = grid
        self.segments: list[TraceSegment] = []
        self.vias: list[Via] = []
        self.pads: list[Pad] = []
        self.warnings: list[str] = []

    def add_pad(self, x, y, w, h, net, layer="F.Cu"):
        """Register a component pad."""
        self.pads.append(Pad(x, y, w, h, net, layer))

    def add_pads_from_footprint(self, fp_x, fp_y, pads_list, net_map):
        """Bulk-register pads from a footprint definition.
        
        pads_list: [(pin_num, dx, dy, w, h, net_name, layer), ...]
        net_map: {net_name: net_id}
        """
        for pin, dx, dy, w, h, net_name, layer in pads_list:
            if net_name and net_name in net_map:
                self.add_pad(fp_x + dx, fp_y + dy, w, h, net_map[net_name], layer)

    def _check_clearance(self, x1, y1, x2, y2, net, width, layer):
        """Check if trace can be placed. Returns (ok, reason)."""
        trace_half = width / 2
        
        # Check against existing segments (same layer, different net)
        for seg in self.segments:
            if seg.layer != layer:
                continue
            if seg.net == net:
                continue
            min_gap = self.clearance + trace_half + seg.width / 2
            dist = seg_to_seg_dist(x1, y1, x2, y2, seg.x1, seg.y1, seg.x2, seg.y2)
            if dist < min_gap:
                return False, f"trace {seg.net} dist={dist:.3f} need={min_gap:.3f}"
        
        # Check against pads (same layer, different net)
        for pad in self.pads:
            if pad.layer != layer and pad.layer not in ("*.Cu",):
                continue
            if pad.net == net:
                continue
            min_gap = self.clearance + trace_half
            dist = seg_to_rect_dist(x1, y1, x2, y2, pad.x, pad.y, pad.w, pad.h)
            if dist < min_gap:
                return False, f"pad net={pad.net} dist={dist:.3f}"
        
        # Check against vias (all layers — vias pass through both)
        for via in self.vias:
            if via.net == net:
                continue
            min_gap = self.clearance + trace_half + via.size / 2
            dist = point_to_seg_dist(via.x, via.y, x1, y1, x2, y2)
            if dist < min_gap:
                return False, f"via net={via.net} dist={dist:.3f}"
        
        # Check board bounds
        margin = trace_half + self.clearance
        for px, py in [(x1, y1), (x2, y2)]:
            if px < margin or px > self.w - margin:
                return False, f"out of bounds X={px:.2f}"
            if py < margin or py > self.h - margin:
                return False, f"out of bounds Y={py:.2f}"
        
        return True, None

    def _commit_segment(self, x1, y1, x2, y2, net, width, layer):
        """Place a trace segment without clearance check."""
        seg = TraceSegment(x1, y1, x2, y2, net, width, layer)
        self.segments.append(seg)
        return seg

    def place(self, x1, y1, x2, y2, net, width=0.25, layer="F.Cu", force=False):
        """Place a trace. Returns True if placed cleanly.
        
        If blocked and force=False, tries detour/layer-switch.
        If blocked and force=True, places anyway with warning.
        """
        # Skip zero-length
        if abs(x2 - x1) < 0.01 and abs(y2 - y1) < 0.01:
            return True
        
        ok, reason = self._check_clearance(x1, y1, x2, y2, net, width, layer)
        if ok:
            self._commit_segment(x1, y1, x2, y2, net, width, layer)
            return True
        
        if force:
            self._commit_segment(x1, y1, x2, y2, net, width, layer)
            self.warnings.append(
                f"FORCED: net={net} ({x1:.1f},{y1:.1f})->({x2:.1f},{y2:.1f}) "
                f"layer={layer}: {reason}"
            )
            return True
        
        # Try detour
        if self._try_detour(x1, y1, x2, y2, net, width, layer):
            return True
        
        # Try opposite layer
        alt_layer = "B.Cu" if layer == "F.Cu" else "F.Cu"
        ok2, reason2 = self._check_clearance(x1, y1, x2, y2, net, width, alt_layer)
        if ok2:
            self.via(x1, y1, net)
            self._commit_segment(x1, y1, x2, y2, net, width, alt_layer)
            self.via(x2, y2, net)
            return True
        
        # Last resort: force it
        self._commit_segment(x1, y1, x2, y2, net, width, layer)
        self.warnings.append(
            f"BLOCKED: net={net} ({x1:.1f},{y1:.1f})->({x2:.1f},{y2:.1f}) "
            f"layer={layer}: {reason} (forced, no alternatives)"
        )
        return True

    def _try_detour(self, x1, y1, x2, y2, net, width, layer):
        """Try L-shaped detour around obstacle."""
        is_horizontal = abs(x2 - x1) >= abs(y2 - y1)
        offsets = [0.7, -0.7, 1.0, -1.0, 1.5, -1.5]
        
        for offset in offsets:
            if is_horizontal:
                # Detour vertically
                mid_y = (y1 + y2) / 2 + offset
                waypoints = [(x1, y1), (x2, y1), (x2, mid_y), (x2, y2)]
            else:
                mid_x = (x1 + x2) / 2 + offset
                waypoints = [(x1, y1), (mid_x, y1), (mid_x, y2), (x2, y2)]
            
            # Check all segments of the detour
            all_ok = True
            for i in range(len(waypoints) - 1):
                wx1, wy1 = waypoints[i]
                wx2, wy2 = waypoints[i + 1]
                ok, _ = self._check_clearance(wx1, wy1, wx2, wy2, net, width, layer)
                if not ok:
                    all_ok = False
                    break
            
            if all_ok:
                for i in range(len(waypoints) - 1):
                    wx1, wy1 = waypoints[i]
                    wx2, wy2 = waypoints[i + 1]
                    if abs(wx2 - wx1) > 0.01 or abs(wy2 - wy1) > 0.01:
                        self._commit_segment(wx1, wy1, wx2, wy2, net, width, layer)
                return True
        
        return False

    def route_path(self, waypoints, net, width=0.25, layer="F.Cu", force=False):
        """Route through a list of (x, y) waypoints.
        
        Each consecutive pair becomes a trace segment.
        """
        for i in range(len(waypoints) - 1):
            x1, y1 = waypoints[i]
            x2, y2 = waypoints[i + 1]
            self.place(x1, y1, x2, y2, net, width, layer, force=force)

    def via(self, x, y, net, size=0.6, drill=0.3):
        """Place a via."""
        v = Via(x, y, net, size, drill)
        self.vias.append(v)
        return v

    def connect(self, x1, y1, x2, y2, net, width=0.25, layer="F.Cu"):
        """Connect two points. Tries direct, then Manhattan, then layer switch."""
        # Try direct
        ok, _ = self._check_clearance(x1, y1, x2, y2, net, width, layer)
        if ok:
            self._commit_segment(x1, y1, x2, y2, net, width, layer)
            return True
        
        # Try Manhattan L-route (horizontal first)
        for prefer in ["H", "V"]:
            pts = manhattan_route_points(x1, y1, x2, y2, prefer)
            all_ok = True
            for i in range(len(pts) - 1):
                ok, _ = self._check_clearance(
                    pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1],
                    net, width, layer
                )
                if not ok:
                    all_ok = False
                    break
            if all_ok:
                self.route_path(pts, net, width, layer)
                return True
        
        # Try detour
        if self._try_detour(x1, y1, x2, y2, net, width, layer):
            return True
        
        # Try opposite layer
        alt = "B.Cu" if layer == "F.Cu" else "F.Cu"
        ok, _ = self._check_clearance(x1, y1, x2, y2, net, width, alt)
        if ok:
            self.via(x1, y1, net)
            self._commit_segment(x1, y1, x2, y2, net, width, alt)
            self.via(x2, y2, net)
            return True
        
        # Force
        self.place(x1, y1, x2, y2, net, width, layer, force=True)
        return True

    def emit(self):
        """Generate KiCad text for all segments and vias."""
        out = ""
        for seg in self.segments:
            out += (
                f'  (segment (start {seg.x1:.4f} {seg.y1:.4f}) '
                f'(end {seg.x2:.4f} {seg.y2:.4f}) '
                f'(width {seg.width}) (layer "{seg.layer}") '
                f'(net {seg.net}) (uuid "{seg.uuid}"))\n'
            )
        for via in self.vias:
            out += (
                f'  (via (at {via.x:.4f} {via.y:.4f}) '
                f'(size {via.size}) (drill {via.drill}) '
                f'(layers "F.Cu" "B.Cu") (net {via.net}) '
                f'(uuid "{via.uuid}"))\n'
            )
        return out

    def summary(self):
        """Return summary statistics."""
        return {
            'segments': len(self.segments),
            'vias': len(self.vias),
            'pads': len(self.pads),
            'warnings': len(self.warnings),
            'forced_count': sum(1 for w in self.warnings if w.startswith('FORCED')),
            'blocked_count': sum(1 for w in self.warnings if w.startswith('BLOCKED')),
        }
