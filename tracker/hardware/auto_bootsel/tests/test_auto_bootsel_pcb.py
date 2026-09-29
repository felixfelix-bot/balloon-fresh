"""Acceptance tests for the auto-BOOTSEL interposer PCB (t_48a0fa82).

The board's job
===============

A 4-wire interposer between an ESP32-C3 and an RP2040 so the ESP32 can reset
the RP2040 and force it into BOOTSEL with nobody present::

    ESP32-C3 GPIO1 (D1) ---> RP2040 RUN   (reset)
    ESP32-C3 GPIO8 (D8) ---> RP2040 GP0   (BOOTSEL / reflash)
    ESP32-C3 GND        ---> RP2040 GND

What these tests are FOR
========================

Every claim the board makes has to be checkable by a command, not by reading
the generator.  So this module asserts, from the GENERATED FILES:

  netlist       the signal chain is GPIO -> series link -> RP2040 pad, and the
                bench-only park links sit between signal and GND;
  electrical    each 0 R link is a real 2-pad part with both pads on distinct
                nets (a link with both pads on one net is a short, not a link);
  DRC           ``kicad-cli pcb drc`` reports 0 violations and 0 unconnected
                items on the routed snapshot  (the fab gate);
  Gate 2.5      the UNROUTED snapshot has 0 pad-overlap pairs, 0 courtyard
                overlaps and >= 10 footprints;
  orientation   every footprint is at rotation 0;
  mass          the <0.01 g figure is asserted on the ADDED mass and the test
                fails if the model ever conflates it with the bare PCB mass.

and, crucially,

  the harness can FAIL.  ``TestHarnessCanFail`` re-runs the same checks against
  deliberately broken boards and asserts they are REJECTED.  A DRC test that
  only ever sees a good board cannot distinguish "board is correct" from
  "checker never fires" — that failure mode is exactly how a board with a
  blanket "Failed to load board" was previously reported as complete, so the
  negative controls are part of the deliverable, not decoration.

The generator is the single source of truth for the board: tests import it and
regenerate into ``tmp_path`` rather than trusting the checked-in copies.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
# The tests live in a tests/ subdir; both the generator and the Gate 2.5
# checker are one and two levels up.
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent))

import auto_bootsel_pcb as gen  # noqa: E402

KICAD_CLI = shutil.which("kicad-cli")
needs_kicad = pytest.mark.skipif(KICAD_CLI is None,
                                 reason="kicad-cli not installed")

# Gate 2.5 lives next door to the board tooling.  Import it rather than
# re-implementing a courtyard test, so the test and the gate cannot drift.
HW = HERE.parent.parent
sys.path.insert(0, str(HW))
gate25_check = pytest.importorskip("gate25_check")


# ---------------------------------------------------------------------------
# fixtures: regenerate the board from the generator into a scratch dir
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def routed(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("ab")
    return gen.generate(d / gen.ROUTED_NAME, routed=True)


@pytest.fixture(scope="module")
def placed(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("ab")
    return gen.generate(d / gen.PLACED_NAME, routed=False)


@pytest.fixture(scope="module")
def checked_in_routed() -> Path:
    return HERE.parent / gen.ROUTED_NAME


@pytest.fixture(scope="module")
def checked_in_placed() -> Path:
    return HERE.parent / gen.PLACED_NAME


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def drc(board: Path, out_dir: Path) -> dict:
    """Run the authoritative check.  A board that will not parse is a failure
    with its own message, never a silently empty violation list."""
    out = out_dir / (board.stem + "-drc.json")
    proc = subprocess.run(
        [KICAD_CLI, "pcb", "drc", "--format", "json", "--output", str(out), str(board)],
        capture_output=True, text=True, timeout=300)
    text = (proc.stdout or "") + (proc.stderr or "")
    assert "Failed to load" not in text, (
        f"kicad-cli could not PARSE {board.name}: {text.strip()[:400]}")
    assert out.exists(), f"no DRC report written for {board.name}: {text.strip()[:400]}"
    return json.loads(out.read_text())


def block(text: str, ref: str) -> str:
    """Raw text of one ``(footprint ...)`` block, by reference designator."""
    for m in re.finditer(r"\(footprint ", text):
        depth, j = 0, m.start()
        while j < len(text):
            if text[j] == '"':
                j += 1
                while j < len(text) and text[j] != '"':
                    if text[j] == "\\":
                        j += 1
                    j += 1
            elif text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        chunk = text[m.start():j + 1]
        if re.search(r'\(property "Reference" "%s"' % re.escape(ref), chunk):
            return chunk
    raise AssertionError(f"no footprint named {ref} in the board text")


def pad_blocks(blk: str) -> list[str]:
    """Raw text of every ``(pad ...)`` block inside a footprint block.

    NOT ``gate25_check.s_expr_blocks(blk, "pad ")``: that helper searches for
    the literal ``"(pad "`` (with a trailing space) and then rejects the match
    when the very next character is alphanumeric.  A named pad is written
    ``(pad 1 smd ...)``, so the character after the terminator IS the pad
    number and EVERY numbered pad is silently skipped — only anonymous pads
    (``(pad "" np_thru_hole``) come back.  Measured on this board: 14 pads
    across 14 footprints, of which the helper returns the 4 mounting-hole
    barrels and none of the 10 signal pads.

    That is a defect in the shared Gate 2.5 tool (reported, not fixed here:
    changing it changes the rule file recorded with the flight board's S0
    evidence).  These tests therefore parse the pads themselves, and
    ``TestHarnessCanFail`` proves the parser is not vacuous.
    """
    out = []
    for m in re.finditer(r"\(pad[ \t]", blk):
        depth, j = 0, m.start()
        while j < len(blk):
            if blk[j] == '"':
                j += 1
                while j < len(blk) and blk[j] != '"':
                    if blk[j] == "\\":
                        j += 1
                    j += 1
            elif blk[j] == "(":
                depth += 1
            elif blk[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append(blk[m.start():j + 1])
    return out


def pad_nets(text: str, ref: str) -> dict[str, str]:
    """``{"1": "RUN_ESP", "2": "RUN_RP"}`` for a footprint."""
    out = {}
    for pb in pad_blocks(block(text, ref)):
        num = re.match(r'\(pad\s+"?([^"\s]*)"?', pb)
        net = re.search(r'\(net (\d+)\s*(?:"([^"]*)")?\)', pb)
        if num and net:
            out[num.group(1)] = net.group(2) or ""
    return out


def footprint_rotations(text: str) -> dict[str, float]:
    rots = {}
    for ref in re.findall(r'\(property "Reference" "([^"]+)"', text):
        if ref.startswith("#"):
            continue
        at = re.search(r"\n\s*\(at ([-.\d]+) ([-.\d]+)(?:\s+([-.\d]+))?\)",
                       block(text, ref))
        if at:
            rots[ref] = float(at.group(3) or 0.0)
    return rots


# ---------------------------------------------------------------------------
# 1. netlist / topology
# ---------------------------------------------------------------------------

class TestNetlist:
    def test_signal_chain_spans_a_series_link(self, routed):
        """GPIO reaches its RP2040 pad THROUGH the 0 R link, not around it.

        The board models the two sides of every series part as DISTINCT nets
        (RUN_ESP/RUN_RP, BOOT_ESP/BOOT_RP).  If a generator change ever tied
        both sides to one net, the link would be shorted and this fails.
        """
        text = routed.read_text()
        assert pad_nets(text, "R1") == {"1": "RUN_ESP", "2": "RUN_RP"}
        assert pad_nets(text, "R2") == {"1": "BOOT_ESP", "2": "BOOT_RP"}

    def test_esp_side_lands_are_the_esp_pins(self, routed):
        text = routed.read_text()
        assert pad_nets(text, "TP1") == {"1": "RUN_ESP"}    # -> ESP32-C3 D1
        assert pad_nets(text, "TP2") == {"1": "BOOT_ESP"}   # -> ESP32-C3 D8

    def test_rp2040_side_lands_are_the_rp_pads(self, routed):
        text = routed.read_text()
        assert pad_nets(text, "TP3") == {"1": "RUN_RP"}     # -> RP2040 RUN
        assert pad_nets(text, "TP4") == {"1": "BOOT_RP"}    # -> RP2040 GP0

    def test_park_links_straddle_signal_and_ground(self, routed):
        """R3/R4 exist to park a signal at GND on the bench, so one pad is the
        signal and the other is GND — and their RP-side pad is the one facing
        the left test point (pad 1 at rotation 0)."""
        text = routed.read_text()
        assert pad_nets(text, "R3") == {"1": "RUN_RP", "2": "GND"}
        assert pad_nets(text, "R4") == {"1": "BOOT_RP", "2": "GND"}

    def test_both_ground_rails_tie_together(self, routed):
        text = routed.read_text()
        assert pad_nets(text, "TP5") == {"1": "GND"}
        assert pad_nets(text, "TP6") == {"1": "GND"}
        tie = [s for s in gate25_check.s_expr_blocks(text, "segment")
               if "(net 1)" in s]
        assert tie, "the two GND rails are not tied by any copper"

    def test_all_net_bearing_pads_are_connected(self, routed, tmp_path):
        """The only netless pads may be the mounting holes' NPTH barrels."""
        d = drc(routed, tmp_path)
        assert d.get("unconnected_items", []) == []

    def test_mounting_holes_are_the_only_netless_pads(self, routed):
        """Guards against a real pad silently losing its net (which would show
        up as an 'unconnected' item rather than as a netlist error).

        Parsed here rather than via ``gate25_check``: that tool's pad helper
        returns only anonymous pads (see ``pad_blocks``), so its
        ``pads_with_no_net`` says nothing about this board.
        """
        text = routed.read_text()
        netless = {}
        for ref in ("TP1", "TP2", "TP3", "TP4", "TP5", "TP6", "R1", "R2", "R3", "R4"):
            for pb in pad_blocks(block(text, ref)):
                num = re.match(r'\(pad\s+"?([^"\s]*)"?', pb)
                if num and "(net " not in pb:
                    netless.setdefault(ref, []).append(num.group(1))
        assert netless == {}, f"signal part has a netless pad: {netless}"

        holes = {}
        for ref in ("H1", "H2", "H3", "H4"):
            blocks = pad_blocks(block(text, ref))
            assert len(blocks) == 1
            holes[ref] = "np_thru_hole" if "np_thru_hole" in blocks[0] else "?"
        assert set(holes.values()) == {"np_thru_hole"}


# ---------------------------------------------------------------------------
# 2. orientation
# ---------------------------------------------------------------------------

class TestOrientation:
    def test_every_footprint_is_at_rotation_zero(self, routed, placed):
        """MEASURED (KiCad 9.0.8): a library footprint placed at a non-zero
        angle makes kicad-cli report ``lib_footprint_mismatch``; the checker
        does not normalise the angle away.  R3/R4 used to sit at 180 deg, which
        is what produced that violation; they are now at 0 with swapped nets.

        This is asserted on BOTH snapshots because the rotation is a placement
        property and the DRC test below would otherwise only catch it on the
        routed one.
        """
        for board in (routed, placed):
            rots = footprint_rotations(board.read_text())
            assert set(rots.values()) == {0.0}, f"{board.name}: {rots}"


# ---------------------------------------------------------------------------
# 3. the fab gate
# ---------------------------------------------------------------------------

@needs_kicad
class TestDrc:
    def test_routed_snapshot_is_fab_ready(self, routed, tmp_path):
        """The card's fab gate: no shorts, no clearance problems, nothing
        unconnected, and enough parts that the result means something."""
        d = drc(routed, tmp_path)
        viol = d.get("violations", [])
        assert viol == [], "routed board has DRC violations: " + json.dumps(
            [v.get("type") for v in viol])
        assert d.get("unconnected_items", []) == [], "routed board has open nets"

    def test_placed_snapshot_passes_gate_25(self, placed, tmp_path):
        """Gate 2.5 precedes any routing row: a router cannot separate two pads
        that occupy the same physical space."""
        r = gate25_check.gate25(
            str(placed), drc_out=str(tmp_path / "g25.json"))
        assert r["pad_overlap_pairs_0.2mm"] == 0, r["pad_overlap_examples"]
        assert r["exact_pad_overlap_pairs_0.2mm"] == 0, r["exact_pad_overlap_examples"]
        assert r["courtyards_overlap"] == 0
        assert r["segments"] == 0, "Gate 2.5 is measured on the UNROUTED board"
        assert r["footprints"] >= 10
        assert r["placement_gate"] == "PASS", json.dumps(r, indent=2)

    def test_placement_is_identical_across_the_two_snapshots(self, placed, routed):
        """The gate and the fab board must be the same placement revision, or
        the gate proves nothing about the board that ships."""
        assert footprint_rotations(placed.read_text()) == \
               footprint_rotations(routed.read_text())
        rp = gate25_check.parse_board(str(placed))
        rr = gate25_check.parse_board(str(routed))
        assert [(f["ref"], f["x"], f["y"]) for f in rp["fps"]] == \
               [(f["ref"], f["x"], f["y"]) for f in rr["fps"]]


# ---------------------------------------------------------------------------
# 4. mass budget
# ---------------------------------------------------------------------------

class TestMass:
    def test_added_mass_is_under_the_requirement(self):
        m = gen.mass_budget()
        assert m["added_pass"] is True
        assert m["added_g"] < 0.01

    def test_added_mass_counts_only_flight_fitted_parts(self):
        """R3/R4 are DNP, so they may not appear in the fitted set."""
        m = gen.mass_budget()
        assert set(m["populated_parts"]) == {"R1", "R2"}
        assert set(m["dnp_parts"]) == {"R3", "R4"}

    def test_the_two_masses_are_not_conflated(self):
        """The <0.01 g requirement is about the ADDED mass of the recovery
        feature.  The bare interposer PCB is ~1.5 g; a model that reports the
        PCB mass as the 'added' figure would read as a 150x miss, and a model
        that reports the added figure as `total_g` would hide the board.  Both
        numbers must exist, be distinct, and be named for what they are."""
        m = gen.mass_budget()
        assert m["added_g"] < 0.01 < m["bare_pcb_g"]
        assert m["bare_pcb_g"] > 100 * m["added_g"]
        assert abs(m["total_g"] - (m["bare_pcb_g"] + m["added_g"])) < 1e-6

    def test_board_area_matches_the_edge_cut_outline(self, routed):
        text = routed.read_text()
        xs = [float(x) for x in re.findall(r"\(gr_line \(start ([\d.]+)", text)]
        ys = [float(y) for y in re.findall(r"\(gr_line \(start [\d.]+ ([\d.]+)\)",
                                           text)]
        area_cm2 = (max(xs) - min(xs)) * (max(ys) - min(ys)) / 100.0
        m = gen.mass_budget()
        assert abs(m["bare_pcb_g"] - 0.185 * area_cm2) < 1e-3


# ---------------------------------------------------------------------------
# 5. does the harness actually fire?
# ---------------------------------------------------------------------------

@needs_kicad
class TestHarnessCanFail:
    """Negative controls.  Each test takes the GOOD board, applies one defect,
    and asserts the corresponding checker REJECTS it.  If any of these start
    passing (i.e. the broken board is accepted), the positive tests above have
    stopped meaning anything.
    """

    @staticmethod
    def _mutate(src: Path, dst: Path, old: str, new: str) -> Path:
        text = src.read_text()
        assert old in text, f"mutation anchor missing: {old!r}"
        dst.write_text(text.replace(old, new, 1))
        return dst

    def test_nonzero_rotation_is_detected(self, routed, tmp_path):
        """Re-introduce the exact defect that shipped: a rotated R3."""
        bad = self._mutate(routed, tmp_path / "rot.kicad_pcb",
                           '(at 19.5 11 0)', '(at 19.5 11 180)')
        rots = footprint_rotations(bad.read_text())
        assert rots["R3"] == 180.0
        assert set(rots.values()) != {0.0}, "the rotation check cannot fail"

    def test_the_drc_gate_rejects_a_short(self, routed, tmp_path):
        """Tie RUN_ESP and RUN_RP onto one pad pair: a real short across R1."""
        text = routed.read_text()
        # make R1 pad 2 carry pad 1's net -> both pads same net, plus the
        # copper between them is then same-net copper over two pads
        bad = self._mutate(routed, tmp_path / "short.kicad_pcb",
                           '      (net 3 "RUN_RP")', '      (net 2 "RUN_ESP")')
        d = drc(bad, tmp_path)
        assert d.get("violations") or d.get("unconnected_items"), \
            "the DRC gate accepted a board with a shorted series link"

    def test_gate_25_rejects_a_pad_overlap(self, routed, tmp_path):
        """Move R1 onto R3's pads: two footprints in the same physical space,
        exactly the failure mode Gate 2.5 exists to catch."""
        bad = self._mutate(routed, tmp_path / "overlap.kicad_pcb",
                           '(at 10.5 11 0)', '(at 19.5 11 0)')
        r = gate25_check.gate25(str(bad), drc_out=str(tmp_path / "o.json"))
        assert r["placement_gate"] == "FAIL"
        assert r["courtyards_overlap"] != 0 or r["pad_overlap_pairs_0.2mm"] != 0

    def test_unconnected_net_is_detected(self, routed, tmp_path):
        """Delete the copper that ties TP4 to R2: the net goes open."""
        text = routed.read_text()
        segs = gate25_check.s_expr_blocks(text, "segment")
        target = next(s for s in segs if '(net 5)' in s)
        assert target in text
        bad = (tmp_path / "open.kicad_pcb")
        bad.write_text(text.replace(target, "", 1))
        d = drc(bad, tmp_path)
        assert d.get("unconnected_items"), "an open net was not detected"

    def test_parse_failure_is_reported_not_swallowed(self, routed, tmp_path):
        """The defect that was actually shipped: the board did not parse, and
        'DRC ran' was reported anyway.  A non-parsing board must raise, never
        yield an empty violation list."""
        text = routed.read_text()
        bad = tmp_path / "broken.kicad_pcb"
        # bare generator_version in a footprint -> "Failed to load board"
        bad.write_text(text.replace('(generator_version "9.0")',
                                    '(generator_version 9.0)'))
        with pytest.raises(AssertionError, match="could not PARSE"):
            drc(bad, tmp_path)

    def test_netlist_check_rejects_a_shorted_link(self, routed):
        """The netlist assertion is not vacuous: with both R1 pads on one net,
        the expected mapping no longer matches."""
        text = routed.read_text()
        broken = text.replace('      (net 3 "RUN_RP")', '      (net 2 "RUN_ESP")')
        assert pad_nets(broken, "R1") != {"1": "RUN_ESP", "2": "RUN_RP"}

    def test_pad_parser_sees_numbered_pads(self, routed):
        """The pad parser must not be the vacuous kind that returns only
        anonymous pads — that is the defect in the shared Gate 2.5 helper, and
        a test built on top of it would assert nothing about signal pads.
        """
        text = routed.read_text()
        assert len(pad_blocks(block(text, "R1"))) == 2
        assert len(pad_blocks(block(text, "TP1"))) == 1
        assert sorted(pad_nets(text, "R1")) == ["1", "2"]

    def test_gate25_pad_helper_is_known_to_skip_numbered_pads(self, routed):
        """Pins the upstream tool's behaviour so the impact stays visible.

        ``gate25_check.s_expr_blocks(text, "pad ")`` yields ONLY anonymous
        pads, so the tool's own ``pads_with_no_net`` metric and its ``pad_box``
        proxy are computed from mounting-hole barrels alone.  If the shared
        tool is ever fixed, this test fails loudly and whoever fixes it should
        also re-run the S0 Gate 2.5 evidence, which was recorded with the buggy
        version.
        """
        text = routed.read_text()
        via_tool = gate25_check.s_expr_blocks(text, "pad ")
        assert len(via_tool) == 4, (
            "gate25_check's pad helper now sees named pads - re-run the S0/S1 "
            "evidence for the flight board, which was recorded with it")
        assert all('(pad ""' in b for b in via_tool)


# ---------------------------------------------------------------------------
# 6. the checked-in artifacts match the generator
# ---------------------------------------------------------------------------

class TestCheckedInArtifacts:
    """The repo copies are what a fabricator and the gate actually read, so a
    stale copy is a defect even when the generator is correct."""

    def test_routed_copy_is_regenerated_byte_for_byte(self, checked_in_routed):
        assert checked_in_routed.read_text() == gen.build(routed=True), (
            "tracker/hardware/auto_bootsel/"
            "auto-bootsel-interposer.kicad_pcb is stale - re-run "
            "auto_bootsel_pcb.py")

    def test_placed_copy_is_regenerated_byte_for_byte(self, checked_in_placed):
        assert checked_in_placed.read_text() == gen.build(routed=False), (
            "auto-bootsel-interposer-placed.kicad_pcb is stale")
