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
    """Run one testbench, return (ok, stdout, stderr)."""
    p = subprocess.run([NGSPICE, "-b", cir], capture_output=True, text=True,
                       timeout=180, cwd=HERE)
    return p.returncode == 0, p.stdout, p.stderr


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
        if not runs:
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
