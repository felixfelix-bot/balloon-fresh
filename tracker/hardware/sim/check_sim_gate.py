#!/usr/bin/env python3
"""SIMULATION GATE -- run ngspice testbenches headless and ASSERT MEASURED NUMBERS.

WHY THIS EXISTS
The campaign's #1 failure mode is a check that reports nothing and reads as a pass. The obvious
version of this gate greps ngspice stdout for a string like "v(out) < 4.9" -- which can NEVER match,
because ngspice prints VALUES, not expressions. That would be a gate that always passes.

So this gate:
  1. runs the testbench with -b (batch, headless)
  2. PARSES the printed numeric vectors into floats
  3. compares them against limits declared IN THE TESTBENCH METADATA (JSON sidecar)
  4. exits non-zero with the measured value and the failed limit when anything is out of range

DESIGN RULE: every assertion must be able to FAIL. A testbench whose criteria cannot be violated is
not a gate. test_sim_gate.py proves that by injecting values that must trip each criterion.

USAGE
    python3 check_sim_gate.py                 # all testbenches
    python3 check_sim_gate.py tb_foo.cir      # one
Exit codes: 0 = all pass, 1 = at least one FAIL, 2 = harness error (missing ngspice etc.)
"""
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NGSPICE = shutil.which("ngspice")


def run_tb(cir):
    """Run one testbench, return (ok, stdout, stderr).

    A deck that produces a CURVE FILE rather than print statements is handled by post_run below --
    this stays a plain run so the "no numeric output parsed" rule keeps its teeth for the print-style
    decks, where an unparseable run must never read as a pass.
    """
    p = subprocess.run([NGSPICE, "-b", cir], capture_output=True, text=True,
                       timeout=180, cwd=HERE)
    return p.returncode == 0, p.stdout, p.stderr


# Decks that emit an ARTIFACT rather than print statements. The artifact path is relative to HERE.
CURVE_DECKS = {"tb_rf_filter.cir": "rf_filter_curve.txt"}


def post_run(tb):
    """After running a curve-producing deck, refresh its artifact cache.

    Returns an error string if the artifact is absent or suspiciously small -- treated as a HARNESS
    ERROR, never a pass.
    """
    art = CURVE_DECKS.get(tb)
    if not art:
        return None
    path = os.path.join(HERE, art)
    if not os.path.exists(path):
        return f"artifact {art} not produced"
    rows = rf_load_curve(force=True)
    if len(rows) < 10:
        return f"artifact {art} has only {len(rows)} usable samples"
    return None


def parse_prints(out):
    """Parse ngspice 'print name = value' lines into a list of dicts (one per analysis run).

    ngspice batch output looks like:
        tk_c = -4.00000e+01
        v(tap) = 3.165761e+00
    Groups are separated by 'Reset re-loads circuit'/'Circuit:' markers.
    """
    runs = []
    cur = {}
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Circuit:") or line.startswith("Reset re-loads"):
            if cur:
                runs.append(cur)
                cur = {}
            continue
        m = re.match(r"^([A-Za-z_][\w()\[\].]*)\s*=\s*([-\d.eE+]+)$", line)
        if m:
            try:
                cur[m.group(1)] = float(m.group(2))
            except ValueError:
                pass
    if cur:
        runs.append(cur)
    return runs


def get_metric(runs, metric, when_key=None, when_val=None, tol=0.5):
    """Return the value of `metric` from the run where when_key ~= when_val.

    Raises LookupError if no run matches, which the caller treats as a HARNESS error, never a pass.
    """
    for r in runs:
        if metric not in r:
            continue
        if when_key is None:
            return r[metric]
        if when_key in r and abs(r[when_key] - when_val) <= tol:
            return r[metric]
    raise LookupError(f"metric {metric!r} not found"
                      + (f" at {when_key}={when_val}" if when_key else ""))


# ---------------------------------------------------------------------------------------------
# CRITERIA -- each is (testbench, id, human description, function(runs) -> (ok, measured, limit))
# Every function MUST be able to return ok=False. test_sim_gate.py verifies that by perturbation.
# ---------------------------------------------------------------------------------------------

def c_tap_25C(runs):
    """At +25 C an NTC matched to its top leg sits at half the rail: 1.65 V. Accept +/-0.05 V."""
    v = get_metric(runs, "v(tap)", "tk_c", 25.0)
    return (abs(v - 1.65) <= 0.05, v, "1.65 +/- 0.05 V")


def c_monotonic(runs):
    """The tap must FALL monotonically as temperature rises (NTC resistance falls).

    This is the assertion that catches a divider wired upside-down -- the single most likely
    schematic error, and one that a netlist-connectivity check cannot see.
    """
    v_cold = get_metric(runs, "v(tap)", "tk_c", -40.0)
    v_25 = get_metric(runs, "v(tap)", "tk_c", 25.0)
    v_hot = get_metric(runs, "v(tap)", "tk_c", 85.0)
    ok = v_cold > v_25 > v_hot
    return (ok, [v_cold, v_25, v_hot], "strictly decreasing with temperature")


def c_cold_headroom(runs):
    """At -40 C the tap must stay below 3.25 V so it is not railed to the 3.3 V rail."""
    v = get_metric(runs, "v(tap)", "tk_c", -40.0)
    return (v < 3.25, v, "< 3.25 V")


def c_hot_floor(runs):
    """At +85 C the tap must stay above 0.05 V so it is not railed to ground."""
    v = get_metric(runs, "v(tap)", "tk_c", 85.0)
    return (v > 0.05, v, "> 0.05 V")


def c_supply_sanity(runs):
    """The 3.3 V rail must BE 3.3 V. A gate that cannot see the rail is not measuring anything."""
    v = get_metric(runs, "v(vdd)")
    return (abs(v - 3.3) <= 1e-6, v, "3.3 V")


# ---- RF harmonic filter (tb_rf_filter.cir) ----------------------------------------------------------
#
# This deck writes a SWEEP CURVE file instead of print statements, and the arithmetic happens here in
# Python. Reason: every deck that used ngspice's control language (alterparam in a foreach, scalar
# `let` across runs, vector indexing) produced IDENTICAL readings -- three times -- which is the tell
# that the sweep was not being applied. Indexing vectors in Python is reliable.

RF_CURVE = os.path.join(HERE, "rf_filter_curve.txt")

# INJECTABLE CURVE. The criteria read this module-level variable, not the file directly, so a test can
# substitute a synthetic curve and PROVE the criterion can fail. Without this seam the criteria were
# untestable, and test_sim_gate.py correctly refused to certify them (RF-LOSS-F, RF-REJ2-F, ... all
# failed as "unproven"). A criterion that cannot be made to fail is not a gate.
_RF_CURVE_CACHE = None


def rf_load_curve(force=False):
    """Read the AC sweep curve: list of (freq_Hz, db) samples.

    Returns [] on any problem, and the caller treats empty as a HARNESS ERROR -- never as a pass.
    """
    global _RF_CURVE_CACHE
    if _RF_CURVE_CACHE is not None and not force:
        return _RF_CURVE_CACHE
    rows = []
    if os.path.exists(RF_CURVE):
        for line in open(RF_CURVE, encoding="utf-8", errors="replace"):
            parts = line.split()
            if len(parts) == 2:
                try:
                    rows.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    pass
    _RF_CURVE_CACHE = rows
    return rows


def rf_at(rows, f):
    """Sample nearest a target frequency."""
    return min(rows, key=lambda r: abs(r[0] - f))


# A 1 V source behind a 50 ohm source impedance driving a 50 ohm load gives v_load = 0.5 V for a
# PERFECT match. In dB that is -6.0206 dB, which is a BASELINE, not a loss. Reporting db(v(load))
# directly as "insertion loss" is how this deck first appeared to show an impossible 6.5 dB of loss in
# a lossless reactive network. All insertion-loss criteria below subtract this baseline explicitly.
SOURCE_DIVIDER_DB = -6.0206


def c_rf_ins_loss(runs):
    """Insertion loss at the 2.4 GHz centre must be small.

    Measured value is the raw dB reading minus the 50 ohm source/load divider baseline.
    """
    rows = rf_load_curve()
    if not rows:
        raise LookupError("rf curve file missing")
    _, g = rf_at(rows, 2.4e9)
    # A PERFECT match reads exactly SOURCE_DIVIDER_DB (-6.02 dB). Any real network reads BELOW it, so
    # insertion loss is BASELINE - g and is POSITIVE for a loss. (An earlier version wrote `g -
    # SOURCE_DIVIDER_DB`, which turns a real 3 dB loss into -3 dB and silently PASSES the <1 dB
    # limit. The perturbation test in test_sim_gate.py caught exactly that.)
    loss = SOURCE_DIVIDER_DB - g
    return (loss < 1.0, round(loss, 3), "< 1.0 dB insertion loss at 2.4 GHz")


def c_rf_reject_h2(runs):
    """2nd-harmonic rejection referenced to the passband must exceed 15 dB.

    A REJECTION IS A RATIO, so the +6.02 dB baseline cancels and cannot fabricate this figure.
    """
    rows = rf_load_curve()
    if not rows:
        raise LookupError("rf curve file missing")
    _, gp = rf_at(rows, 2.4e9)
    _, gh = rf_at(rows, 4.8e9)
    rej = gp - gh
    return (rej > 15.0, round(rej, 2), "> 15 dB rejection at 4.8 GHz")


def c_rf_reject_h3(runs):
    """3rd-harmonic rejection must also exceed 15 dB."""
    rows = rf_load_curve()
    if not rows:
        raise LookupError("rf curve file missing")
    _, gp = rf_at(rows, 2.4e9)
    _, gh = rf_at(rows, 7.2e9)
    rej = gp - gh
    return (rej > 15.0, round(rej, 2), "> 15 dB rejection at 7.2 GHz")


def c_rf_curve_is_real(runs):
    """The sweep must contain MANY DISTINCT samples spanning the intended band.

    THIS IS THE ANTI-FABRICATION CRITERION. Three separate decks this session returned identical
    readings from a sweep that was not actually being applied; a curve that is flat, tiny, or
    single-valued would sail past a spot check. This asserts the instrument itself is live.
    """
    rows = rf_load_curve()
    if not rows:
        raise LookupError("rf curve file missing")
    n = len(rows)
    span = rows[-1][0] - rows[0][0]
    distinct = len({round(g, 6) for _, g in rows})
    ok = n > 100 and span > 1e9 and distinct > 50
    return (ok, f"n={n} span={span / 1e9:.2f}GHz distinct={distinct}",
            ">100 samples, >1 GHz span, >50 distinct values")


# ---- supercap balance divider (tb_scap_balance.cir) -------------------------------------------------

def c_bal_half(runs):
    """Supercap midpoint must sit at exactly half the stack when the resistors are equal."""
    v = get_metric(runs, "v_top")
    return (abs(v - 2.70) <= 0.01, v, "2.70 V +/- 0.01 V")


def c_bal_current(runs):
    """Balance divider current at 5.4 V. R_BAL1+R_BAL2 = 20k, so 270 uA.

    This is a NIGHT-BUDGET number: the divider draws continuously from the supercap, so a value
    change here must be a deliberate decision, not a side effect.
    """
    i = get_metric(runs, "i_div")
    return (abs(i - 2.7e-4) <= 1e-5, i, "2.70e-4 A +/-1e-5 (270 uA)")


def c_bal_linear(runs):
    """Halving the stack must halve the midpoint -- the divider must be linear, not clipped."""
    v = get_metric(runs, "v_half")
    return (abs(v - 1.35) <= 0.01, v, "1.35 V +/- 0.01 V")


# ---- VSCAP monitor divider (tb_vscap_monitor.cir) ---------------------------------------------------

def c_mon_tap(runs):
    """VSCAP monitor tap at a 5.4 V stack must be 2.70 V -- the 1:2 divider ratio."""
    v = get_metric(runs, "v_tap")
    return (abs(v - 2.70) <= 0.03, v, "2.70 V +/- 0.03 V")


def c_mon_adc_limit(runs):
    """THE SAFETY CRITERION: the tap must stay under the ADC reference at max stack voltage.

    If this fails, the MCU's ADC pin sees an over-voltage. That is a dead part, and it is the one
    failure in this block that a firmware change cannot recover.
    """
    v = get_metric(runs, "v_tap")
    return (v < 3.30, v, "< 3.30 V (ADC reference)")


def c_mon_monotonic(runs):
    """The tap must rise with the stack. A flat or falling response means the divider is wrong."""
    a = get_metric(runs, "v_at_3v0")
    b = get_metric(runs, "v_at_4v2")
    c = get_metric(runs, "v_tap")
    ok = a < b < c
    return (ok, [a, b, c], "strictly increasing with stack voltage")


def c_mon_night_budget(runs):
    """Divider current must stay under 5 uA. 1Meg+1Meg draws 2.7 uA.

    A milliamp-class divider would flatten the supercap overnight, and this payload cannot recharge
    until sunrise.
    """
    i = get_metric(runs, "i_ua")
    return (i < 5.0, i, "< 5.0 uA")


CRITERIA = {
    # The RF deck writes a CURVE FILE rather than print statements, so it is run and parsed
    # separately -- but it is registered here so the no-orphan rule (D1) still covers it.
    "tb_rf_filter.cir": [
        ("RF-CURVE", "sweep is real: many distinct samples over a wide band", c_rf_curve_is_real),
        ("RF-LOSS", "insertion loss < 1 dB at the 2.4 GHz centre", c_rf_ins_loss),
        ("RF-REJ2", "> 15 dB rejection at the 2nd harmonic", c_rf_reject_h2),
        ("RF-REJ3", "> 15 dB rejection at the 3rd harmonic", c_rf_reject_h3),
    ],
    "tb_scap_balance.cir": [
        ("BAL-HALF", "supercap midpoint at exactly half the stack", c_bal_half),
        ("BAL-CURR", "balance divider current = 270 uA", c_bal_current),
        ("BAL-LINR", "divider is linear, not clipped", c_bal_linear),
    ],
    "tb_vscap_monitor.cir": [
        ("MON-TAP", "monitor tap = 2.70 V at a 5.4 V stack", c_mon_tap),
        ("MON-ADC", "SAFETY: tap under the ADC reference at max stack", c_mon_adc_limit),
        ("MON-MONO", "tap rises monotonically with stack voltage", c_mon_monotonic),
        ("MON-NIGHT", "divider current under the 5 uA night budget", c_mon_night_budget),
    ],
    "tb_ntc_divider.cir": [
        ("NTC-25C", "tap at half rail when thermistor matches top leg", c_tap_25C),
        ("NTC-MONO", "tap falls monotonically with temperature", c_monotonic),
        ("NTC-COLD", "cold-end headroom, not railed high", c_cold_headroom),
        ("NTC-HOT", "hot-end floor, not railed low", c_hot_floor),
        ("RAIL", "supply rail measures 3.3 V", c_supply_sanity),
    ],
}


def main(argv):
    if not NGSPICE:
        print("HARNESS ERROR: ngspice not found on PATH")
        return 2

    only = argv[1] if len(argv) > 1 else None
    tbs = [only] if only else sorted(CRITERIA)
    total = fails = 0
    ver = subprocess.run([NGSPICE, "--version"], capture_output=True, text=True).stdout
    ver = ver.split("ngspice-")[-1].split()[0] if "ngspice-" in ver else "?"
    print(f"=== SIMULATION GATE (ngspice {ver}) ===")

    for tb in tbs:
        cir = os.path.join(HERE, tb)
        if not os.path.exists(cir):
            print(f"\n{tb}: MISSING FILE")
            fails += 1
            continue
        ok, out, err = run_tb(cir)
        runs = parse_prints(out)
        print(f"\n{tb}  ({len(runs)} analysis run(s), ngspice rc={0 if ok else 1})")

        # Curve-producing decks emit an ARTIFACT instead of parsed prints. Refresh it and report a
        # HARNESS ERROR if it is missing or too small -- never a pass.
        perr = post_run(tb)
        if perr:
            print(f"  HARNESS ERROR: {perr} -- cannot grade. An absent artifact is not a pass.")
            fails += 1
            continue

        if not runs and tb not in CURVE_DECKS:
            print("  HARNESS ERROR: no numeric output parsed -- cannot grade. "
                  "An unparseable run is NOT a pass.")
            fails += 1
            continue

        for cid, desc, fn in CRITERIA[tb]:
            total += 1
            try:
                good, measured, limit = fn(runs)
            except LookupError as e:
                print(f"  [{cid:<9}] HARNESS ERROR: {e}")
                fails += 1
                continue
            mark = "PASS" if good else "FAIL"
            if not good:
                fails += 1
            print(f"  [{cid:<9}] {mark}  measured={measured}  limit={limit}  ({desc})")

    print(f"\n=== {total - fails}/{total} criteria pass ===")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
