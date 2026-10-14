#!/usr/bin/env python3
"""COUNTER-TEST: prove test_spec_transcription.py can actually FAIL.

A test that only ever passes proves nothing. Sabotage the spec in memory and confirm the
verifier goes red -- the discipline this campaign uses for every check.
"""
import json
import subprocess
import shutil
import tempfile

SPEC = "/home/c08r4d0r/worktrees/v9-route/tracker/hardware/base_station/spec.json"
TST = "/home/c08r4d0r/worktrees/v9-route/tracker/hardware/base_station/test_spec_transcription.py"

# run the real one first
r = subprocess.run(["python3", TST], capture_output=True, text=True)
print("baseline exit:", r.returncode, "(expect 0)")
assert r.returncode == 0, "baseline should pass"

# now sabotage: drop a verification gate and mangle the rail name
orig = open(SPEC).read()
s = json.loads(orig)
s["gates_not_yet_passed"] = s["gates_not_yet_passed"][:3]          # lose one gate
s["rails"]["plus5V_LNA_SW"]["load"] = "ZX60, 9 mA"                  # wrong number
open(SPEC, "w").write(json.dumps(s, indent=2))
try:
    r2 = subprocess.run(["python3", TST], capture_output=True, text=True)
    print("sabotaged exit:", r2.returncode, "(expect 1)")
    red = [l for l in r2.stdout.splitlines() if "FAIL" in l]
    print(f"  failures detected: {len(red)}")
    for l in red[:4]:
        print("   ", l.strip())
    assert r2.returncode == 1, "sabotaged spec MUST fail the verifier"
    print()
    print("COUNTER-TEST PASSED: the verifier detects a dropped gate and a changed number.")
finally:
    open(SPEC, "w").write(orig)
    r3 = subprocess.run(["python3", TST], capture_output=True, text=True)
    print("restored exit:", r3.returncode, "(expect 0)")
