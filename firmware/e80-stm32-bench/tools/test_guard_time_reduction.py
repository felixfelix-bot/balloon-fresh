"""
Tests for guard time reduction: MOD-before-wait_until, removed SWD code,
and reduced default timing parameters.

TDD RED phase — all tests should FAIL against current code.
"""
import pytest
import inspect
import sys
import os

# Ensure tools/ is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e80_bench_ctl


# ---------------------------------------------------------------------------
# Test 1: MOD command must be sent BEFORE wait_until(start)
# ---------------------------------------------------------------------------

def test_tx_mod_command_before_wait_until():
    """TX should send MOD command BEFORE wait_until(start), not after.

    Currently MOD is sent after wait_until, blocking 3-5s for firmware
    self-reset (TCXO startup + calibration). This delays the burst start
    and requires large guard times (>=6s).

    Fix: send MOD (and other config commands) before wait_until so the
    self-reset happens during the inter-config gap, allowing guard=3s.
    """
    source = inspect.getsource(e80_bench_ctl.run_tx_mode)

    # Find positions of "wait_until(start" and "mod_line" in source
    wait_until_pos = source.find("wait_until(start")
    mod_pos = source.find("mod_line")

    assert mod_pos != -1, "mod_line not found in run_tx_mode source"
    assert wait_until_pos != -1, "wait_until(start) not found in run_tx_mode source"

    # MOD should come BEFORE wait_until
    assert mod_pos < wait_until_pos, (
        "MOD command is sent AFTER wait_until(start). This blocks 3-5s "
        "for firmware self-reset, delaying the burst. Move MOD before "
        "wait_until to allow guard=3s instead of 6s."
    )


# ---------------------------------------------------------------------------
# Test 2: SWD close/reopen should be removed from TX loop
# ---------------------------------------------------------------------------

def test_swd_close_reopen_removed_from_tx():
    """SWD close/reopen should be removed from TX loop since firmware
    handles chip reset internally (commit c70f582).

    The dead SWD code (board.close() -> swd_reset_maybe() -> BoardSerial(port))
    adds ~2s overhead per mod-change transition with no benefit.
    """
    source = inspect.getsource(e80_bench_ctl.run_tx_mode)

    # Should NOT contain swd_reset_maybe call or board.close() in run_tx_mode
    has_swd_reset = "swd_reset_maybe" in source
    has_board_close = "board.close()" in source

    assert not (has_swd_reset or has_board_close), (
        "Dead SWD close/reopen code in run_tx_mode adds ~2s overhead. "
        "Firmware self-reset (c70f582) handles this. Remove swd_reset_maybe() "
        "and board.close()/BoardSerial reopen from the TX loop."
    )


# ---------------------------------------------------------------------------
# Test 3: Reduced default timing parameters in argparse
# ---------------------------------------------------------------------------

def test_reduced_default_guard_times():
    """Default timing parameters should be reduced for NTP-synced machines.

    Old defaults (wasteful for online machines with <50ms NTP drift):
      t0_margin=120, guard=20, rx_lead=10, settle=2, swd_reset_s=10

    New defaults (safe for NTP-synced):
      t0_margin=30, guard=5, rx_lead=3, settle=1, swd_reset_s=2
    """
    source = inspect.getsource(e80_bench_ctl)

    # t0_margin: should be 30 (safe) or 20 (aggressive), not 120
    assert 'default=30' in source or 'default=20' in source, (
        "t0_margin default should be 30s (safe) or 20s (aggressive), not 120s"
    )

    # guard: should be 5 or 3, not 20
    assert '"--guard", type=int, default=5' in source or \
           '"--guard", type=int, default=3' in source, (
        "guard default should be 3-5s, not 20s"
    )

    # rx_lead: should be 3 or 2, not 10
    assert 'dest="rx_lead", type=int, default=3' in source or \
           'dest="rx_lead", type=int, default=2' in source, (
        "rx_lead default should be 2-3s, not 10s"
    )


def test_new_defaults_in_parser():
    """Verify argparse defaults match the exact reduced values from the plan.

    Plan specifies: t0_margin=30, guard=5, rx_lead=3, settle=1, swd_reset_s=2
    """
    source = inspect.getsource(e80_bench_ctl)

    # t0_margin default should be exactly 30
    assert 'dest="t0_margin", type=int, default=30' in source, (
        "t0_margin default should be 30 (not 120)"
    )

    # guard default should be exactly 5
    assert '"--guard", type=int, default=5' in source, (
        "guard default should be 5 (not 20)"
    )

    # rx_lead default should be exactly 3
    assert 'dest="rx_lead", type=int, default=3' in source, (
        "rx_lead default should be 3 (not 10)"
    )