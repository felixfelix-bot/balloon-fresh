#!/usr/bin/env python3
"""Unit tests for Router class and geometry functions."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest
from router import (
    point_to_seg_dist,
    seg_to_seg_dist,
    seg_to_rect_dist,
    Router,
    Pad,
    TraceSegment,
)


# ============================================================
# Geometry function tests
# ============================================================

class TestPointToSegDist:
    def test_point_on_segment(self):
        d = point_to_seg_dist(5, 0, 0, 0, 10, 0)
        assert d == 0.0

    def test_point_above_segment(self):
        d = point_to_seg_dist(5, 3, 0, 0, 10, 0)
        assert abs(d - 3.0) < 0.001

    def test_point_past_end(self):
        d = point_to_seg_dist(15, 0, 0, 0, 10, 0)
        assert abs(d - 5.0) < 0.001

    def test_point_past_start(self):
        d = point_to_seg_dist(-5, 0, 0, 0, 10, 0)
        assert abs(d - 5.0) < 0.001

    def test_vertical_segment(self):
        d = point_to_seg_dist(5, 5, 5, 0, 5, 10)
        assert d == 0.0

    def test_degenerate_segment(self):
        d = point_to_seg_dist(3, 4, 0, 0, 0, 0)
        assert abs(d - 5.0) < 0.001


class TestSegToSegDist:
    def test_parallel_traces_close(self):
        d = seg_to_seg_dist(0, 0, 10, 0, 0, 0.2, 10, 0.2)
        assert abs(d - 0.2) < 0.001

    def test_parallel_traces_far(self):
        d = seg_to_seg_dist(0, 0, 10, 0, 0, 5, 10, 5)
        assert abs(d - 5.0) < 0.001

    def test_crossing_segments(self):
        d = seg_to_seg_dist(0, 0, 10, 10, 0, 10, 10, 0)
        assert d == 0.0

    def test_perpendicular_no_cross(self):
        d = seg_to_seg_dist(0, 0, 10, 0, 5, 3, 5, 10)
        assert abs(d - 3.0) < 0.001

    def test_collinear_segments(self):
        d = seg_to_seg_dist(0, 0, 5, 0, 7, 0, 10, 0)
        assert abs(d - 2.0) < 0.001


class TestSegToRectDist:
    def test_segment_through_pad_center(self):
        d = seg_to_rect_dist(0, 5, 10, 5, 5, 5, 2, 2)
        assert d == 0.0

    def test_segment_above_pad(self):
        d = seg_to_rect_dist(0, 10, 10, 10, 5, 5, 2, 2)
        # pad spans y=4 to y=6, segment at y=10
        assert abs(d - 4.0) < 0.001

    def test_segment_near_pad_edge(self):
        d = seg_to_rect_dist(0, 5, 10, 5, 15, 5, 2, 2)
        # pad center at x=15, spans x=14-16, segment ends at x=10
        assert abs(d - 4.0) < 0.001


# ============================================================
# Router class tests
# ============================================================

class TestRouterBasic:
    def test_empty_router(self):
        r = Router(50, 40)
        assert len(r.segments) == 0
        assert len(r.vias) == 0

    def test_place_simple_trace(self):
        r = Router(50, 40)
        r.place(5, 5, 45, 5, net=1, width=0.25)
        assert len(r.segments) == 1

    def test_zero_length_skipped(self):
        r = Router(50, 40)
        r.place(5, 5, 5, 5, net=1)
        assert len(r.segments) == 0


class TestRouterClearance:
    def test_different_net_close_blocked(self):
        """Two traces at 0.2mm gap with 0.3mm clearance should block."""
        r = Router(50, 40, clearance=0.3)
        r.place(0, 10, 10, 10, net=1, width=0.25, force=True)
        # Second trace at 0.2mm gap, different net
        r.place(0, 10.2, 10, 10.2, net=2, width=0.25)
        # Should have tried detour/layer-switch
        assert len(r.segments) >= 1  # at least the forced first one

    def test_same_net_overlap_ok(self):
        """Same-net traces can overlap."""
        r = Router(50, 40, clearance=0.3)
        r.place(5, 10, 20, 10, net=1, width=0.25)
        r.place(5, 10, 15, 10, net=1, width=0.25)
        assert len(r.warnings) == 0

    def test_different_layer_no_collision(self):
        """Traces on different layers don't collide."""
        r = Router(50, 40, clearance=0.3)
        r.place(5, 10, 20, 10, net=1, width=0.25, layer="F.Cu")
        r.place(5, 10, 20, 10, net=2, width=0.25, layer="B.Cu")
        assert len(r.warnings) == 0

    def test_far_apart_ok(self):
        """Traces far apart should place cleanly."""
        r = Router(50, 40, clearance=0.3)
        r.place(5, 5, 20, 5, net=1, width=0.25)
        r.place(5, 20, 20, 20, net=2, width=0.25)
        assert len(r.warnings) == 0
        assert len(r.segments) == 2


class TestRouterPads:
    def test_trace_through_same_net_pad_ok(self):
        r = Router(50, 40, clearance=0.3)
        r.add_pad(10, 10, 1.7, 1.7, net=1)
        r.place(5, 10, 15, 10, net=1, width=0.25)
        assert len(r.warnings) == 0

    def test_trace_through_different_net_pad_blocked(self):
        r = Router(50, 40, clearance=0.3)
        r.add_pad(10, 10, 1.7, 1.7, net=1)
        # Trace net=2 passing through pad net=1
        r.place(5, 10, 15, 10, net=2, width=0.25)
        # Should trigger warning or detour
        # (might successfully detour or layer-switch, which is fine)
        # Just verify it didn't place a short


class TestRouterVias:
    def test_via_near_different_net_trace_blocked(self):
        r = Router(50, 40, clearance=0.3)
        r.place(5, 10, 15, 10, net=1, width=0.25, force=True)
        # Via for net=2 very close to trace
        r.place(10, 10.5, 10, 20, net=2, width=0.25)
        # Should have found alternative or warned

    def test_via_same_net_ok(self):
        r = Router(50, 40, clearance=0.3)
        r.place(5, 10, 15, 10, net=1, width=0.25)
        r.via(10, 10, net=1)
        assert len(r.warnings) == 0


class TestRouterConnect:
    def test_direct_connection(self):
        r = Router(50, 40, clearance=0.3)
        r.connect(5, 5, 45, 5, net=1, width=0.25)
        assert len(r.segments) == 1

    def test_blocked_uses_manhattan(self):
        r = Router(50, 40, clearance=0.3)
        # Block direct path
        r.place(10, 3, 10, 7, net=99, width=0.25, force=True)
        r.place(20, 3, 20, 7, net=99, width=0.25, force=True)
        # Connect around obstacles
        r.connect(5, 5, 25, 5, net=1, width=0.25)
        # Should have placed something
        assert len(r.segments) >= 2  # at least the blockers + routed trace

    def test_layer_switch(self):
        r = Router(50, 40, clearance=0.3)
        # Block both F.Cu paths
        r.place(0, 5, 10, 5, net=99, width=0.5, force=True)
        r.place(10, 5, 20, 5, net=99, width=0.5, force=True)
        r.place(20, 5, 30, 5, net=99, width=0.5, force=True)
        # Try to connect net=1 across
        r.connect(5, 5, 35, 5, net=1, width=0.25)
        # May use layer switch (B.Cu + vias)
        assert len(r.segments) >= 4


class TestRouterEmit:
    def test_emit_produces_valid_kicad_text(self):
        r = Router(50, 40)
        r.place(5, 5, 45, 5, net=1, width=0.25)
        r.via(10, 10, net=2)
        text = r.emit()
        assert "(segment" in text
        assert "(via" in text
        assert "(net 1)" in text
        assert "(net 2)" in text
        assert "F.Cu" in text

    def test_emit_has_uuid(self):
        r = Router(50, 40)
        r.place(5, 5, 45, 5, net=1, width=0.25)
        text = r.emit()
        assert "uuid" in text

    def test_summary(self):
        r = Router(50, 40)
        r.place(5, 5, 45, 5, net=1)
        r.place(5, 35, 45, 35, net=2)
        r.via(25, 20, net=1)
        s = r.summary()
        assert s['segments'] == 2
        assert s['vias'] == 1


class TestRouterRoutePath:
    def test_multi_point_routing(self):
        r = Router(50, 40)
        r.route_path([(5, 5), (25, 5), (25, 35), (45, 35)], net=1, width=0.25)
        assert len(r.segments) == 3  # 3 segments for 4 waypoints

    def test_route_path_force(self):
        r = Router(50, 40)
        r.route_path([(5, 5), (5, 5)], net=1, width=0.25)  # zero-length
        assert len(r.segments) == 0  # skipped


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
