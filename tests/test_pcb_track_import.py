"""test_pcb_track_import.py — spec for the Freerouting -> KiCad track import (PCB Phase 1).

WHY IT EXISTS
-------------
`hub_board_v1_routed.kicad_pcb` (2026-08-05) shipped 651 traces of which 76 were
exactly zero-length and 334 were sub-0.5 um artifacts, with **1221 of 1302 track
endpoints at negative Y — outside the 0..40 mm board**.  DRC: 405 violations
(181 `track_dangling`) and 68 unconnected items.

Three findings drive this spec, each measured, not assumed:

  F1  Y is inverted.  A Specctra DSN writes Y negated relative to .kicad_pcb.
      Proof is inside the file: the DSN `placement` block has component `U` at
      (12000.0, -12000.0) um while the board has it at (12.000, 12.000) mm —
      all 13 placed components agree on `y_board = -y_dsn`.  The old importer
      used `+y`.

  F2  The DSN is full of exporter stubs.  651 raw segments = 76 exactly zero,
      334 below 0.5 um, **zero** in the 0.5..1.0 um band, 2 real 1.6/1.7 um
      jogs, 239 real.  A 1 um collapse threshold separates artifact from
      geometry with margin, and a non-empty ambiguity band means the threshold
      must be re-derived.

  F3  **The DSN's segment list is not the route.**  Comparing the DSN against
      the SES from the same router run: only 57 of the DSN's 199 real segments
      appear in the SES at all.  A DSN-only import is therefore a strict subset
      of the routing — measured 483 DRC violations including 60 `tracks_crossing`
      on the first DSN, versus **175 violations and zero crossings** for KiCad's
      own `ImportSpecctraSES` on the sibling SES.  `build()` must therefore
      prefer the SES, and the SES path is what the Phase 1 gate is measured on.

Run: /usr/bin/python3 -m pytest tests/test_pcb_track_import.py -v
"""
from __future__ import annotations

import math
import os
import re
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HW_DIR = os.path.join(REPO_ROOT, "tracker", "hardware")
sys.path.insert(0, HW_DIR)

# The routing pair of record.  The plan named `/tmp/routed_output.dsn`, which no
# longer exists; these in-repo twins are the same generation of routing (the
# committed board's 651 traces match `v1_freerouting_output.dsn`'s 651 raw
# segments exactly — see PCB-TRACK-IMPORT.md).
DSN = os.path.join(HW_DIR, "output", "v1_freerouting_output.dsn")
DSN_WITH_SES = os.path.join(HW_DIR, "output", "v1_freerouting_routed.dsn")
SES = os.path.join(HW_DIR, "output", "v1_freerouting_routed.ses")
PCB_CLEAN = os.path.join(HW_DIR, "hub_board_v1_clean.kicad_pcb")

import import_tracks_fixed as itf  # noqa: E402


def _pcbnew():
    """KiCad's python module, or a skip.

    `exc_type=ImportError` matters: without it pytest 9.1 turns the import
    failure into an error, so the spec would break CI on a machine that has no
    KiCad instead of skipping the board-level half.
    """
    sys.path.insert(0, "/usr/lib/python3/dist-packages")
    return pytest.importorskip("pcbnew", exc_type=ImportError,
                               reason="KiCad python module absent")


# ─────────────────────────────────────────────────────────────────────────────
# F1  coordinate transform
# ─────────────────────────────────────────────────────────────────────────────

class TestCoordinateTransform:

    def test_dsn_um_to_kicad_nm_inverts_y(self):
        """DSN Y is negated relative to board Y; X is not."""
        assert itf.dsn_um_to_kicad_nm(12000.0, -12000.0) == (12_000_000, 12_000_000)
        assert itf.dsn_um_to_kicad_nm(0.0, 0.0) == (0, 0)
        assert itf.dsn_um_to_kicad_nm(50000.0, -40000.0) == (50_000_000, 40_000_000)

    def test_transform_reproduces_every_placed_footprint(self):
        """Oracle: the board's own footprint positions must fall out of it.

        With the old `+y` reading this fails for all 13 components at once.
        """
        comps = itf.parse_dsn_placement(DSN)
        assert len(comps) >= 13, "DSN placement block did not parse"

        pcbnew = _pcbnew()
        board = pcbnew.LoadBoard(PCB_CLEAN)
        board_pos = {}
        for fp in board.GetFootprints():
            p = fp.GetPosition()
            board_pos[fp.GetReference()] = (p.x, p.y)

        checked = 0
        for ref, (x_um, y_um, _side) in comps.items():
            if ref not in board_pos:
                continue
            got = itf.dsn_um_to_kicad_nm(x_um, y_um)
            want = board_pos[ref]
            assert abs(got[0] - want[0]) <= 1000, \
                "component %s X mismatch: transform=%s board=%s" % (ref, got, want)
            assert abs(got[1] - want[1]) <= 1000, \
                "component %s Y mismatch: transform=%s board=%s" % (ref, got, want)
            checked += 1
        assert checked >= 13, "expected >=13 comparable components, got %d" % checked


# ─────────────────────────────────────────────────────────────────────────────
# F2  degenerate-segment collapse
# ─────────────────────────────────────────────────────────────────────────────

class TestDegenerateCollapse:

    @pytest.fixture(scope="class")
    def hist(self):
        return itf.raw_segment_length_histogram(DSN)

    def test_dsn_really_contains_degenerate_geometry(self, hist):
        """Regression guard: if the stubs vanish, this half of the spec is moot."""
        assert hist["zero"] > 0, "DSN no longer contains zero-length segments"
        assert hist["sub_0p5"] > 0, "DSN no longer contains sub-0.5um stubs"

    def test_histogram_partitions_without_overlap(self, hist):
        assert hist["real"] == (hist["total"] - hist["zero"] - hist["sub_0p5"]
                                - hist["ambiguous_0p5_to_1"] - hist["one_to_5"])
        assert hist["total"] == 651, "raw segment count changed: %d" % hist["total"]
        assert hist["one_to_5"] == 2, "the two real 1.6/1.7um jogs vanished"

    def test_collapse_threshold_has_margin(self, hist):
        """Nothing may sit in the 0.5..1.0 um band, or 1 um is not a safe cut."""
        assert hist["ambiguous_0p5_to_1"] == 0, \
            "segments inside the collapse ambiguity band: %d" % hist["ambiguous_0p5_to_1"]

    def test_collapse_drops_stubs_and_keeps_real_vertices(self):
        """651 raw segments -> 241 collapsed -> 228 after the spur clip.

        The 13 lost segments are the export spurs (LR2021_RST/DIO9 walking off
        a 50 mm board) and the single-vertex runs they leave behind.
        """
        assert len(itf.dsn_to_segments(DSN)) == 228


class TestSegments:

    @pytest.fixture(scope="class")
    def segments(self):
        return itf.dsn_to_segments(DSN)

    def test_no_zero_length_segments(self, segments):
        bad = [s for s in segments if s["start"] == s["end"]]
        assert bad == [], "%d zero-length segments survived the import" % len(bad)

    def test_every_segment_meets_minimum_length(self, segments):
        short = [s for s in segments
                 if math.hypot(s["end"][0] - s["start"][0],
                               s["end"][1] - s["start"][1]) < itf.MIN_TRACK_LENGTH_NM]
        assert short == [], "%d segments shorter than %d nm" % (
            len(short), itf.MIN_TRACK_LENGTH_NM)

    def test_every_segment_is_inside_the_board(self, segments):
        """The old +y import put 1221/1302 endpoints outside the outline."""
        outside = [s for s in segments
                   if any(not (0 <= x <= itf.BOARD_X_NM and 0 <= y <= itf.BOARD_Y_NM)
                          for x, y in (s["start"], s["end"]))]
        assert outside == [], "%d segments fall outside the board outline" % len(outside)

    def test_every_segment_has_a_net_and_a_layer(self, segments):
        for s in segments:
            assert s["net_name"], "segment with empty net: %r" % s
            assert s["layer_name"] in ("F.Cu", "B.Cu"), "bad layer %r" % s

    def test_all_dsn_nets_exist_on_the_target_board(self, segments):
        board_nets = set(re.findall(r'\(net \d+ "?([^")]*)"?\)',
                                    open(PCB_CLEAN, errors="replace").read()))
        missing = sorted({s["net_name"] for s in segments} - board_nets)
        assert missing == [], "nets in DSN but not on board: %s" % missing

    def test_off_boundary_export_spurs_are_clipped(self):
        """The DSN walks LR2021_RST to x=53.33mm on a 50mm board and back."""
        assert "53334.9" in open(DSN, errors="replace").read(), \
            "expected the 53.33mm spur in the DSN of record"
        bnd = itf.parse_dsn_boundary(DSN)
        assert bnd["x_max"] == 50100.0 and bnd["x_min"] == -100.0, bnd
        segs = itf.dsn_to_segments(DSN)
        assert not [s for s in segs if s["start"][0] > itf.BOARD_X_NM
                    or s["end"][0] > itf.BOARD_X_NM]


class TestVias:

    def test_dsn_vias_are_parsed(self):
        """14 placed vias — the other three `(via` in the DSN are declarations."""
        vias = itf.parse_dsn_vias(DSN)
        assert len(vias) == 14, "expected 14 placed vias, got %d" % len(vias)
        for v in vias:
            assert v["pad_nm"] == 600_000, v
            assert v["drill_nm"] == 300_000, v
            assert 0 <= v["pos"][0] <= itf.BOARD_X_NM, v
            assert 0 <= v["pos"][1] <= itf.BOARD_Y_NM, v


# ─────────────────────────────────────────────────────────────────────────────
# F3  the SES is the router's route; the DSN is not
# ─────────────────────────────────────────────────────────────────────────────

class TestSesIsTheRouteOfRecord:
    """These pin the evidence behind preferring the SES.  Failure means the
    documented reasoning no longer matches the artifacts — re-derive it."""

    def test_dsn_segments_are_not_the_route(self):
        """Only 60 of the DSN's 193 segments appear in the SES, and 60 of the
        SES's 160.

        Measured by exact segment-endpoint match (SES is 0.1 um, DSN 1 um, both
        y-inverted into board space).  So a DSN-only import reconstructs a
        strict subset of the router's route — 60 of 160 segments — which is why
        it scores 483 DRC violations (60 `tracks_crossing`) versus 175.
        """
        assert os.path.isfile(SES), "expected the SES twin at %s" % SES
        t = itf.ses_vs_dsn_segment_overlap(DSN_WITH_SES, SES)
        assert t["dsn_real_segments"] == 193, t
        assert t["ses_segments"] == 160, t
        assert t["dsn_real_segments_in_ses"] == 60, t
        assert t["ses_segments_covered_by_dsn"] == 60, t


class TestSesBuild:

    @pytest.fixture(scope="class")
    def board_file(self, tmp_path_factory):
        _pcbnew()
        out = tmp_path_factory.mktemp("pcb") / "ses.kicad_pcb"
        itf.build(DSN_WITH_SES, PCB_CLEAN, str(out), ses_path=SES)
        return out

    def test_build_reports_ses_as_its_source(self, board_file):
        """build() must not silently fall back to the DSN parser."""
        _pcbnew()
        out = "/tmp/t877_src_probe.kicad_pcb"
        stats = itf.build(DSN_WITH_SES, PCB_CLEAN, out, ses_path=SES)
        assert stats["source"] == "ses"
        assert stats["zero_length"] == 0 and stats["sub_1um"] == 0
        assert stats["outside"] == 0

    def test_board_builds_and_loads(self, board_file):
        pcbnew = _pcbnew()
        b = pcbnew.LoadBoard(str(board_file))
        assert b is not None
        assert len(list(b.GetTracks())) == 174  # 160 tracks + 14 vias

    def test_board_has_no_degenerate_tracks(self, board_file):
        pcbnew = _pcbnew()
        b = pcbnew.LoadBoard(str(board_file))
        trk = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T]
        zero = [t for t in trk if t.GetStart() == t.GetEnd()]
        short = [t for t in trk
                 if math.hypot(t.GetEnd().x - t.GetStart().x,
                               t.GetEnd().y - t.GetStart().y) < itf.MIN_TRACK_LENGTH_NM]
        assert zero == [], "%d zero-length tracks" % len(zero)
        assert short == [], "%d sub-1um tracks" % len(short)

    def test_board_has_14_vias(self, board_file):
        pcbnew = _pcbnew()
        b = pcbnew.LoadBoard(str(board_file))
        assert len([t for t in b.GetTracks()
                    if t.Type() == pcbnew.PCB_VIA_T]) == 14

    def test_board_tracks_are_inside_the_outline(self, board_file):
        pcbnew = _pcbnew()
        b = pcbnew.LoadBoard(str(board_file))
        bad = [t for t in b.GetTracks()
               if any(not (0 <= p.x <= itf.BOARD_X_NM and 0 <= p.y <= itf.BOARD_Y_NM)
                      for p in (t.GetStart(), t.GetEnd()))]
        assert bad == [], "%d tracks outside the board outline" % len(bad)

    def test_board_tracks_do_not_cross_each_other(self, board_file):
        """`tracks_crossing` was 60 on the DSN-only import and 0 here."""
        import json
        import subprocess
        rpt = "/tmp/t877_crossing_drc.json"
        subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json",
                        "--output", rpt, str(board_file)],
                       check=True, capture_output=True, timeout=300)
        v = json.load(open(rpt)).get("violations", [])
        cross = [x for x in v if x.get("type") == "tracks_crossing"]
        assert cross == [], "%d tracks_crossing violations" % len(cross)

    def test_board_placement_is_frozen(self, board_file):
        pcbnew = _pcbnew()

        def fpmap(p):
            b = pcbnew.LoadBoard(p)
            out = {}
            for fp in b.GetFootprints():
                q = fp.GetPosition()
                out[fp.GetReference()] = (q.x, q.y,
                                          round(fp.GetOrientationDegrees(), 6),
                                          fp.GetLayer())
            return out

        before, after = fpmap(PCB_CLEAN), fpmap(str(board_file))
        assert before.keys() == after.keys()
        moved = [r for r in before if before[r] != after[r]]
        assert moved == [], "footprints moved during import: %s" % moved

    def test_board_zone_is_preserved(self, board_file):
        pcbnew = _pcbnew()
        b = pcbnew.LoadBoard(str(board_file))
        zones = [(z.GetNetname(), sorted(b.GetLayerName(l)
                                         for l in z.GetLayerSet().Seq()))
                 for z in b.Zones()]
        assert zones == [("GND", ["B.Cu"])], zones
