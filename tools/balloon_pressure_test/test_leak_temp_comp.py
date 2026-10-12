#!/usr/bin/env python3
"""Regression test: leak-rate temperature compensation must be sign-correct.

Physical model — sealed balloon, constant volume, ideal gas (P/T = const):

    P_ref(t) = P0 - L * t                      # leak-carrying quantity
    P_meas(t) = P_ref(t) * T_k(t) / T_k(0)     # what the sensor sees

`P_ref` is invariant to temperature, so a correct analyser normalises each
sample back to the start temperature and recovers L exactly.

The BUG this guards against (found 2026-10-10, fixed in the same file):

    delta_p_temp = P_start * (T_end - T_start) / T_start
    compensated  = leak_rate_fit - delta_p_temp / duration

derived the correction from P_start instead of P_end.  Consequences:

  * warming  -> compensation is subtracted in the wrong direction and the true
    leak is under-reported, driving the rate NEGATIVE (physically impossible);
  * because verdict() tests `rate < 0.5` first, a balloon that leaked FASTER as
    it warmed could be reported "Very good — flight ready".

This test injects a KNOWN leak plus a KNOWN temperature drift and asserts the
recovered rate equals the injected one.  Under the old formula these assertions
fail (that was the RED state).

Run:  python3 tools/balloon_pressure_test/test_leak_temp_comp.py
No numpy / matplotlib / pytest required — pure stdlib.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plot_pressure as pp  # noqa: E402

FAIL = 0
PASS = 0


def expect(cond, msg):
    global FAIL, PASS
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {msg}")


def synth(n=21, p0=800.0, leak_mbar_per_h=1.5, dt_h=0.5, t_start=20.0, t_end=None):
    """Samples with a KNOWN leak and a KNOWN linear temperature drift."""
    hours = [i * dt_h for i in range(n)]
    tk0 = t_start + 273.15
    if t_end is None:
        t_end = t_start
    temps = [t_start + (t_end - t_start) * (i / (n - 1)) for i in range(n)]
    pressures = []
    for h, tc in zip(hours, temps):
        p_ref = p0 - leak_mbar_per_h * h
        pressures.append(p_ref * ((tc + 273.15) / tk0))
    return hours, pressures, temps


def test_warming_recovers_true_leak():
    """Warming masks the leak -> the raw rate is too low; compensation fixes it."""
    h, p, t = synth(leak_mbar_per_h=1.5, t_start=20.0, t_end=30.0)
    r = pp.analyze(h, p, t, sensor="ms5611")
    comp = r["leak_rate_temp_comp_mbar_per_h"]
    raw = r["leak_rate_fit_mbar_per_h"]
    expect(abs(comp - 1.5) < 1e-6, f"compensated rate == 1.5, got {comp:.6f}")
    expect(raw < comp, f"raw ({raw:.4f}) under-reports vs compensated ({comp:.4f})")
    expect(comp > 0, f"compensated rate must be positive, got {comp:.6f}")
    expect(not r["verdict"].startswith("PRESSURE RISE"),
           f"a real leak must not be called a rise: {r['verdict']}")


def test_cooling_recovers_true_leak():
    """Cooling exaggerates the leak -> compensation must still recover 1.5."""
    h, p, t = synth(leak_mbar_per_h=1.5, t_start=30.0, t_end=20.0)
    r = pp.analyze(h, p, t, sensor="ms5611")
    comp = r["leak_rate_temp_comp_mbar_per_h"]
    raw = r["leak_rate_fit_mbar_per_h"]
    expect(abs(comp - 1.5) < 1e-6, f"compensated rate == 1.5, got {comp:.6f}")
    expect(raw > comp, f"raw ({raw:.4f}) over-reports vs compensated ({comp:.4f})")


def test_temperature_invariance():
    """Same leak, opposite drift -> same compensated answer."""
    cases = [synth(t_start=20.0, t_end=30.0), synth(t_start=30.0, t_end=20.0),
             synth(t_start=20.0, t_end=20.0)]
    vals = [pp.analyze(*c, sensor="ms5611")["leak_rate_temp_comp_mbar_per_h"] for c in cases]
    expect(max(vals) - min(vals) < 1e-6, f"drift-invariant, got spread {vals}")


def test_flight_ready_balloon_not_inverted_under_warmup():
    """A genuinely flight-ready 0.3 mbar/h balloon warming up must stay flight-ready."""
    h, p, t = synth(leak_mbar_per_h=0.3, t_start=15.0, t_end=35.0)
    r = pp.analyze(h, p, t, sensor="ms5611")
    comp = r["leak_rate_temp_comp_mbar_per_h"]
    expect(abs(comp - 0.3) < 1e-6, f"compensated rate == 0.3, got {comp:.6f}")
    expect(comp > 0, "0.3 mbar/h balloon must not report a negative rate")
    expect(r["verdict"].startswith("Very good"),
           f"expected flight-ready verdict, got: {r['verdict']}")


def test_no_drift_is_unchanged():
    """With no temperature change, compensation must not alter the raw fit."""
    h, p, t = synth(leak_mbar_per_h=1.0, t_start=20.0, t_end=20.0)
    r = pp.analyze(h, p, t, sensor="ms5611")
    expect(abs(r["leak_rate_temp_comp_mbar_per_h"] - r["leak_rate_fit_mbar_per_h"]) < 1e-9,
           "isothermal: compensated == raw fit")


if __name__ == "__main__":
    print("test_leak_temp_comp: leak-rate temperature compensation (sign-correctness)")
    for fn in (test_warming_recovers_true_leak, test_cooling_recovers_true_leak,
               test_temperature_invariance,
               test_flight_ready_balloon_not_inverted_under_warmup,
               test_no_drift_is_unchanged):
        print(f"- {fn.__name__}")
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            expect(False, f"{fn.__name__} raised {exc!r}")
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
