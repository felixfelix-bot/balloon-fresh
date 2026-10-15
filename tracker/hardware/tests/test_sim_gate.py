#!/usr/bin/env python3
"""SIMULATION GATE REGRESSION SUITE -- proves the sim gate can FAIL, and covers every block.

The rest of this repo's gates are standalone scripts with __main__ + exit code, not pytest, so this
follows the same convention and runs identically:

    python3 tracker/hardware/tests/test_sim_gate.py

Exit 0 = all regression checks pass. Exit 1 = the sim gate is NOT trustworthy.

THIS IS THE DIFFERENCE BETWEEN A GATE AND DECORATION
A gate that cannot fail is not a gate. The campaign's worst failure mode is precisely that -- a check
that reports nothing and reads as a pass (fabricated-green, three times). So these tests never ask
"does the gate pass?". They ask "can I MAKE it fail, and does the gate then say so?"

CLASSES GUARDED
  A. HARNESS TRUTH       -- the parser returns real floats; empty output must never read as success.
  B. CRITERION CAN FAIL  -- each criterion is violated with synthetic data and must return FAIL.
  C. NOMINAL PASSES      -- each criterion must ACCEPT correct data, or it is a false alarm.
  D. NO ORPHANS          -- every tb_*.cir on disk must be registered in CRITERIA.
  E. NO DANGLING REFS    -- every registered testbench must exist on disk.
  F. CLAIM MATCHES CODE  -- blocks the ADR says are simulated must actually have a testbench, so the
                            ADR cannot drift away from the code (same class as a stale board package).
  G. UNIQUE IDS          -- no duplicate criterion ids.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.join(os.path.dirname(HERE), "sim")
sys.path.insert(0, SIM)

import check_sim_gate as gate  # noqa: E402

fails = []
checks = 0


def check(cid, desc, cond, detail=""):
    global checks
    checks += 1
    if cond:
        print(f"  [{cid:<9}] PASS  {desc}")
    else:
        print(f"  [{cid:<9}] FAIL  {desc}" + (f"  -- {detail}" if detail else ""))
        fails.append(cid)


def nominal_runs(cold=3.165761, at25=1.65, hot=0.429661, vdd=3.3,
                 bal_top=2.70, bal_idiv=2.7e-4, bal_half=1.35,
                 mon_tap=2.70, mon_30=1.50, mon_42=2.10, mon_ua=2.70):
    """One synthetic run set carrying every metric any criterion reads.

    Real values, transcribed from an observed gate run, so a criterion accepting them is a real
    acceptance -- not a tautology against made-up numbers.
    """
    return [
        {"tk_c": -40.0, "v(tap)": cold, "v(vdd)": vdd},
        {"tk_c": 25.0, "v(tap)": at25, "v(vdd)": vdd},
        {"tk_c": 85.0, "v(tap)": hot, "v(vdd)": vdd},
        {"v_top": bal_top, "i_div": bal_idiv, "v_half": bal_half},
        {"v_tap": mon_tap, "v_at_3v0": mon_30, "v_at_4v2": mon_42, "i_ua": mon_ua},
    ]


print("=== A. HARNESS TRUTH ===")
check("A1", "ngspice is present (cannot run, must not silently skip)",
      bool(gate.NGSPICE), "ngspice not on PATH")

tb = os.path.join(SIM, "tb_ntc_divider.cir")
if gate.NGSPICE and os.path.exists(tb):
    p = subprocess.run([gate.NGSPICE, "-b", tb], capture_output=True, text=True, cwd=SIM)
    runs = gate.parse_prints(p.stdout)
    check("A2", "parser returns real runs, not an empty dict", bool(runs),
          "unparseable output must NEVER be treated as a pass")
    vals = [r["v(tap)"] for r in runs if "v(tap)" in r]
    check("A3", "parser returns 3 tap values as floats",
          len(vals) == 3 and all(isinstance(v, float) for v in vals), f"got {vals}")
else:
    check("A2", "testbench present", False, f"missing {tb}")
    check("A3", "parser returns values", False)

try:
    gate.get_metric([{"tk_c": 25.0}], "v(does_not_exist)")
    check("A4", "absent metric RAISES instead of defaulting", False,
          "silently returning a default is how a gate becomes a rubber stamp")
except LookupError:
    check("A4", "absent metric RAISES instead of defaulting", True)

print("\n=== B/C. EACH CRITERION CAN FAIL, AND ACCEPTS NOMINAL DATA ===")
# Each perturbation CONTRADICTS the criterion it targets. A criterion with no perturbation here
# cannot be shown to work, and the suite fails it as unproven.
perturbations = {
    "NTC-25C":  nominal_runs(at25=2.00),
    "NTC-MONO": nominal_runs(cold=0.429661, at25=1.65, hot=3.165761),  # upside-down divider
    "NTC-COLD": nominal_runs(cold=3.29),
    "NTC-HOT":  nominal_runs(hot=0.01),
    "RAIL":     nominal_runs(vdd=5.0),
    # supercap balance: midpoint off-half, wrong divider current, non-linear response
    "BAL-HALF": nominal_runs(bal_top=2.90),
    "BAL-CURR": nominal_runs(bal_idiv=1.0e-3),
    "BAL-LINR": nominal_runs(bal_half=1.00),
    # VSCAP monitor: wrong tap, over-ADC tap, flat response, greedy divider
    "MON-TAP":  nominal_runs(mon_tap=3.00),
    "MON-ADC":  nominal_runs(mon_tap=3.40),
    "MON-MONO": nominal_runs(mon_30=1.50, mon_42=2.10, mon_tap=1.50),
    "MON-NIGHT": nominal_runs(mon_ua=50.0),
}
by_id = {}
for _tbn, crits in gate.CRITERIA.items():
    for cid, desc, fn in crits:
        by_id[cid] = (desc, fn)

for cid, (desc, fn) in by_id.items():
    good, m, lim = fn(nominal_runs())
    check(f"{cid}-N", f"{cid} ACCEPTS correct data ({desc[:38]})",
          good is True, f"false alarm on nominal data: measured={m} limit={lim}")
    if cid in perturbations:
        bad, m2, lim2 = fn(perturbations[cid])
        check(f"{cid}-F", f"{cid} REJECTS perturbed data",
              bad is False, f"gate did NOT catch the perturbation; measured={m2} limit={lim2}")
    else:
        check(f"{cid}-F", f"{cid} has a perturbation defined", False,
              "no perturbation means this criterion is unproven")

    check(f"{cid}-L", f"{cid} states a limit", bool(lim), "a criterion with no limit states nothing")

print("\n=== D/E. TESTBENCH REGISTRATION ===")
on_disk = {f for f in os.listdir(SIM) if f.startswith("tb_") and f.endswith(".cir")}
registered = set(gate.CRITERIA)
check("D1", "no orphan testbench (every .cir asserts something)",
      not (on_disk - registered), f"orphans: {sorted(on_disk - registered)}")
check("E1", "no dangling registration", not (registered - on_disk),
      f"registered but absent: {sorted(registered - on_disk)}")

print("\n=== F. ADR CLAIMS MATCH THE CODE ===")
claimed = {
    "NTC temperature divider": "tb_ntc_divider.cir",
    "supercap balance divider": "tb_scap_balance.cir",
    "VSCAP monitor divider": "tb_vscap_monitor.cir",
}
for block, tbf in claimed.items():
    check(f"F-{tbf[:14]}", f"ADR-claimed block {block!r} has {tbf}", tbf in on_disk,
          "the ADR would drift away from the code -- same class as a stale board package")

print("\n=== G. IDS UNIQUE ===")
seen = set()
dupes = []
for _tbn, crits in gate.CRITERIA.items():
    for cid, _d, _f in crits:
        if cid in seen:
            dupes.append(cid)
        seen.add(cid)
check("G1", "criterion ids unique", not dupes, f"duplicates: {dupes}")

print(f"\n=== {checks - len(fails)}/{checks} regression checks pass ===")
if fails:
    print(f"FAILED: {fails}")
    print("\nThe simulation gate is NOT trustworthy until these pass.")
    sys.exit(1)
print("The simulation gate is trustworthy: every criterion can fail and none is orphaned.")
sys.exit(0)
