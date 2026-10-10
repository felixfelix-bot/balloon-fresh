"""Regression test: leak-rate temperature compensation must be sign-correct.

Physical model (sealed balloon, constant volume, ideal gas: P/T = const):

    P_leak(t) = p_start - L * t            # pressure with NO temperature change
    P(t)      = P_leak(t) * T(t) / T_start # what the sensor actually sees

so the observed end pressure is

    p_end = (p_start - L * duration) * t_end / t_start

and the leak rate L is recovered EXACTLY by

    L = (p_start - p_end * t_start / t_end) / duration

A temperature RISE makes pressure climb, which MASKS the leak: the naive raw
rate (p_start - p_end)/duration under-reports it. A temperature FALL does the
opposite. The previous implementation subtracted an absolute delta computed
from p_start, which under-reported on warming AND inverted the sign, yielding
a negative ("the balloon is gaining pressure") leak rate.

Runs standalone (`python3 test_leak_temp_comp.py`) because this machine has no
single interpreter carrying numpy + pytest together; the plain-assert +
test_* naming keeps it pytest-collectible where pytest is available.
"""

import os
import sys
import traceback

os.environ.setdefault("MPLBACKEND", "Agg")  # headless

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plot_pressure import calc_leak_rate  # noqa: E402


def approx(value, expected, abs_tol=1e-9):
    """Minimal pytest.approx stand-in so this file needs no pytest import."""
    ok = abs(value - expected) <= abs_tol
    return ok, f"{value!r} != {expected!r} (abs_tol={abs_tol})"


T_START_C = 20.0
T_END_C = 30.0


def _series(p_start, leak, duration_h, t_start_c, t_end_c, n=25):
    """Synthesise (hours, pressures, temps) for a known leak + linear drift."""
    hours = np.linspace(0.0, duration_h, n)
    temps = np.linspace(t_start_c, t_end_c, n)
    t0 = t_start_c + 273.15
    p_leak_only = p_start - leak * hours
    pressures = p_leak_only * (temps + 273.15) / t0
    return hours, pressures, temps


def test_warming_recovers_the_injected_leak_rate():
    """The discriminating case: warming masks the leak, so compensation must
    enlarge the rate. The old code returned a NEGATIVE rate here."""
    hours, pressures, temps = _series(1013.25, leak=1.5, duration_h=24.0,
                                      t_start_c=T_START_C, t_end_c=T_END_C)
    raw, comp, dur = calc_leak_rate(hours, pressures, temps)

    assert abs(dur - 24.0) < 1e-9, f"duration {dur}"
    assert raw < 1.5, f"temperature rise must mask the leak in the raw rate (raw={raw})"
    assert comp > 0, f"a real leak can never compensate to a negative rate (comp={comp})"
    ok, msg = approx(comp, 1.5, 0.02)
    assert ok, f"expected the injected 1.5 mbar/h, got {comp:.3f} (raw {raw:.3f}) [{msg}]"


def test_cooling_recovers_the_injected_leak_rate():
    """Mirror case: cooling amplifies the apparent drop."""
    hours, pressures, temps = _series(1013.25, leak=1.5, duration_h=24.0,
                                      t_start_c=T_END_C, t_end_c=T_START_C)
    raw, comp, dur = calc_leak_rate(hours, pressures, temps)

    assert raw > 1.5, f"temperature fall must exaggerate the raw rate (raw={raw})"
    ok, msg = approx(comp, 1.5, 0.02)
    assert ok, f"got {comp:.3f} [{msg}]"


def test_isothermal_rate_is_unchanged():
    """No temperature drift -> raw and compensated must agree exactly."""
    hours, pressures, temps = _series(1013.25, leak=1.5, duration_h=24.0,
                                      t_start_c=T_START_C, t_end_c=T_START_C)
    raw, comp, _ = calc_leak_rate(hours, pressures, temps)

    ok, msg = approx(comp, raw, 1e-9)
    assert ok, f"isothermal compensation must be a no-op [{msg}]"
    ok, msg = approx(comp, 1.5, 1e-6)
    assert ok, f"got {comp:.6f} [{msg}]"


def test_tight_balloon_is_still_flight_ready():
    """A 0.3 mbar/h balloon across a 10 C swing must pass the 0.5 threshold."""
    hours, pressures, temps = _series(1013.25, leak=0.3, duration_h=24.0,
                                      t_start_c=T_START_C, t_end_c=T_END_C)
    _, comp, _ = calc_leak_rate(hours, pressures, temps)

    ok, msg = approx(comp, 0.3, 0.02)
    assert ok, f"got {comp:.3f} [{msg}]"
    assert comp < 0.5, f"must land in the 'Very good - flight ready' band (comp={comp})"


def _main():
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except Exception:
            failed += 1
            print(f"FAIL  {name}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
