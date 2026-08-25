#!/usr/bin/env python3
"""test_dual_band_code.py — TDD tests for dual-band code support in e80_bench_ctl.py.

Tests for 4 fixes:
1. OVERRIDE_MAX_HZ is 2483500000 (not 960000000)
2. Band transition detection (is_band_transition) works correctly
3. load_config_preset can find "stop-50m" (resolves to configs/per-stop/stop-50m.json)
4. build_preset_schedule inserts extra delay on band transitions (band_swap_s)

Run:  python3 -m pytest tools/test_dual_band_code.py -v
"""
import os
import sys
import time
import json
import pathlib

# Add tools dir to path so we can import from e80_bench_ctl
TOOLS_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from e80_bench_ctl import (
    OVERRIDE_MAX_HZ,
    is_band_transition,
    load_config_preset,
    build_preset_schedule,
)


# ---------------------------------------------------------------------------
# FIX 1: OVERRIDE_MAX_HZ
# ---------------------------------------------------------------------------

def test_override_max_hz_is_2483500000():
    """OVERRIDE_MAX_HZ must be 2483500000 to match firmware's override window."""
    assert OVERRIDE_MAX_HZ == 2483500000, (
        f"OVERRIDE_MAX_HZ should be 2483500000, got {OVERRIDE_MAX_HZ}"
    )


def test_override_max_hz_not_960000000():
    """OVERRIDE_MAX_HZ must NOT be the old 960000000 value."""
    assert OVERRIDE_MAX_HZ != 960000000, (
        "OVERRIDE_MAX_HZ is still 960000000 — should be 2483500000"
    )


# ---------------------------------------------------------------------------
# FIX 2: is_band_transition
# ---------------------------------------------------------------------------

BAND_THRESHOLD_HZ = 1_600_000_000  # 1.6 GHz


def test_is_band_transition_subghz_to_2g4():
    """Crossing from sub-GHz to 2.4 GHz is a band transition."""
    assert is_band_transition(869525000, 2400000000) is True


def test_is_band_transition_2g4_to_subghz():
    """Crossing from 2.4 GHz to sub-GHz is a band transition."""
    assert is_band_transition(2400000000, 869525000) is True


def test_is_band_transition_same_band_subghz():
    """Two sub-GHz freqs are NOT a band transition."""
    assert is_band_transition(868000000, 869525000) is False


def test_is_band_transition_same_band_2g4():
    """Two 2.4 GHz freqs are NOT a band transition."""
    assert is_band_transition(2400000000, 2483500000) is False


def test_is_band_transition_exact_threshold():
    """Exactly 1.6 GHz is treated as sub-GHz (>= threshold is 2.4 GHz band)."""
    # 1599999999 is sub-GHz, 1600000000 is 2.4 GHz
    assert is_band_transition(1599999999, 1600000000) is True


def test_is_band_transition_none_prev():
    """None as prev_freq should not trigger a transition."""
    assert is_band_transition(None, 2400000000) is False


# ---------------------------------------------------------------------------
# FIX 3: load_config_preset finds per-stop configs by bare name
# ---------------------------------------------------------------------------

def test_load_config_preset_finds_stop_50m_by_bare_name():
    """load_config_preset('stop-50m') should resolve to configs/per-stop/stop-50m.json."""
    cfgs = load_config_preset("stop-50m")
    assert len(cfgs) > 0, "load_config_preset('stop-50m') returned no configs"
    # Check it actually loaded the right file (stop-50m.json has 10 configs)
    assert len(cfgs) == 10, (
        f"stop-50m.json should have 10 configs, got {len(cfgs)}"
    )


def test_load_config_preset_finds_stop_50m_with_json_suffix():
    """load_config_preset('stop-50m.json') should also resolve to per-stop."""
    cfgs = load_config_preset("stop-50m.json")
    assert len(cfgs) == 10


# ---------------------------------------------------------------------------
# FIX 4: build_preset_schedule inserts band_swap_s delay on band transitions
# ---------------------------------------------------------------------------

def _make_test_cfgs():
    """Create a minimal set of preset configs that cross the band boundary."""
    return [
        {
            "idx": 0,
            "label": "subGHz-cfg",
            "mod": "flrc",
            "sf": None,
            "br": 2600,
            "bw": None,
            "pa": 22,
            "freq": 869525000,
            "plen": 511,
            "gap": 5000,
            "n_pkts": 10,
            "airtime_s": 0.1,
            "expected_s": 0.6,
        },
        {
            "idx": 1,
            "label": "2g4-cfg",
            "mod": "flrc",
            "sf": None,
            "br": 2600,
            "bw": None,
            "pa": 12,
            "freq": 2400000000,
            "plen": 511,
            "gap": 5000,
            "n_pkts": 10,
            "airtime_s": 0.1,
            "expected_s": 0.6,
        },
    ]


def test_build_preset_schedule_inserts_band_swap_delay():
    """build_preset_schedule should add band_swap_s between band transitions."""
    cfgs = _make_test_cfgs()
    t0 = 1000000
    band_swap_s = 30

    starts_with_swap = build_preset_schedule(
        cfgs, t0, t0_margin=10, guard=5, settle=1, rx_lead=0,
        swd_reset_s=0, band_swap_s=band_swap_s,
    )
    starts_without_swap = build_preset_schedule(
        cfgs, t0, t0_margin=10, guard=5, settle=1, rx_lead=0,
        swd_reset_s=0, band_swap_s=0,
    )

    # The gap between config 0 and config 1 should be larger with band_swap_s
    gap_with = starts_with_swap[1] - starts_with_swap[0]
    gap_without = starts_without_swap[1] - starts_without_swap[0]
    assert gap_with - gap_without == band_swap_s, (
        f"Gap difference should be {band_swap_s}s, got {gap_with - gap_without}s"
    )


def test_build_preset_schedule_no_band_swap_same_band():
    """build_preset_schedule should NOT add band_swap_s when no band transition."""
    cfgs = [
        {
            "idx": 0, "label": "subGHz-1", "mod": "flrc", "sf": None, "br": 2600,
            "bw": None, "pa": 22, "freq": 868000000, "plen": 511, "gap": 5000,
            "n_pkts": 10, "airtime_s": 0.1, "expected_s": 0.6,
        },
        {
            "idx": 1, "label": "subGHz-2", "mod": "flrc", "sf": None, "br": 1300,
            "bw": None, "pa": 22, "freq": 869525000, "plen": 511, "gap": 5000,
            "n_pkts": 10, "airtime_s": 0.1, "expected_s": 0.6,
        },
    ]
    t0 = 1000000
    starts = build_preset_schedule(
        cfgs, t0, t0_margin=10, guard=5, settle=1, rx_lead=0,
        swd_reset_s=0, band_swap_s=30,
    )
    starts_no_swap = build_preset_schedule(
        cfgs, t0, t0_margin=10, guard=5, settle=1, rx_lead=0,
        swd_reset_s=0, band_swap_s=0,
    )
    # No band transition → no extra delay
    assert starts == starts_no_swap, (
        "Same-band configs should not get band_swap_s delay"
    )


def test_build_preset_schedule_band_swap_default():
    """build_preset_schedule should default band_swap_s to 0 for backward compat."""
    cfgs = _make_test_cfgs()
    t0 = 1000000
    # Call without band_swap_s — should not crash and should work
    starts = build_preset_schedule(cfgs, t0, t0_margin=10, guard=5, settle=1)
    assert len(starts) == 2


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])