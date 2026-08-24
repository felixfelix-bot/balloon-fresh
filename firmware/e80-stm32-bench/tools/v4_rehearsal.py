#!/usr/bin/env python3
"""V4 REHEARSAL — host dry-run validation of adaptive campaign controller.

No hardware access. Exercises:
  1. Branch logic: all probe verdict combinations → correct campaign mode
  2. Crash-resume: kill mid-stop, restart, state consistent
  3. Carry-forward: both walk directions (near→far AND far→near)
  4. Full campaign dry-run: config building, SPRT decisions, cliff search
  5. State DB integrity: commit, reload, partial-write recovery

Run: python3 v4_rehearsal.py
"""
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e80_campaign as camp

PASS = 0
FAIL = 0

def check(name, cond, detail=""):
    global PASS, FAIL
    status = "PASS" if cond else "FAIL"
    if cond:
        PASS += 1
    else:
        FAIL += 1
    print(f"  [{status}] {name}" + (f" — {detail}" if detail and not cond else ""))

def section(title):
    print(f"\n=== {title} ===")

# ---- 1. Branch logic ----
section("1. Branch logic — probe verdicts → campaign mode")

# SF7 CLEAN → GOOD regardless of FLRC
v = camp.branch(camp.SprtResult("CLEAN", 0, 15), camp.SprtResult("CLEAN", 0, 15))
check("both CLEAN → GOOD", v == "GOOD", f"got {v}")

v = camp.branch(camp.SprtResult("CLEAN", 0, 15), camp.SprtResult("DEAD", 10, 10))
check("SF7 CLEAN, FLRC DEAD → GOOD", v == "GOOD", f"got {v}")

# SF7 DEAD → DEGRADED
v = camp.branch(camp.SprtResult("DEAD", 10, 10), camp.SprtResult("CLEAN", 0, 15))
check("SF7 DEAD → DEGRADED", v == "DEGRADED", f"got {v}")

v = camp.branch(camp.SprtResult("DEAD", 10, 10), camp.SprtResult("DEAD", 10, 10))
check("both DEAD → DEGRADED", v == "DEGRADED", f"got {v}")

# SF7 EDGE → EDGE
v = camp.branch(camp.SprtResult("EDGE", 2, 20), camp.SprtResult("CLEAN", 0, 15))
check("SF7 EDGE → EDGE", v == "EDGE", f"got {v}")

v = camp.branch(camp.SprtResult("EDGE", 2, 20), camp.SprtResult("EDGE", 2, 20))
check("both EDGE → EDGE", v == "EDGE", f"got {v}")

# ---- 2. Crash-resume ----
section("2. Crash-resume — state DB survives interruption")

tmpdir = tempfile.mkdtemp()
state_path = os.path.join(tmpdir, "campaign_state.json")

# Simulate: stop S1 completes, state committed
st = camp.CampaignState(state_path)
st.record_verdict("S1", d=50, config_label="FLRC-650", verdict="CLEAN", k=0, n=15)
st.record_verdict("S1", d=50, config_label="SF7", verdict="CLEAN", k=0, n=15)
st.commit()

# Simulate: stop S2 starts, records one verdict, then CRASH (no commit)
st.record_verdict("S2", d=100, config_label="FLRC-650", verdict="DEAD", k=10, n=10)
# NO commit() — crash happens here

# Recovery: new process loads from disk
st2 = camp.CampaignState(state_path)
s1_data = st2.get_stop_data("S1")
check("S1 data survived crash", s1_data is not None and "FLRC-650" in s1_data)
check("S1 has 2 configs", s1_data is not None and len(s1_data) == 2)

s2_data = st2.get_stop_data("S2")
check("S2 lost (no commit before crash)", s2_data is None,
      f"got {s2_data}")

# Resume: re-run S2 from scratch
st2.record_verdict("S2", d=100, config_label="FLRC-650", verdict="DEAD", k=10, n=10)
st2.record_verdict("S2", d=100, config_label="SF7", verdict="EDGE", k=2, n=20)
st2.commit()

st3 = camp.CampaignState(state_path)
s2_data = st3.get_stop_data("S2")
check("S2 recovered after resume", s2_data is not None and len(s2_data) == 2)

# Carry-forward still works with recovered state
skips = st3.get_skips("S3", d=200)
check("DEAD@S2 skips S3 (d=200>100)", "FLRC-650" in skips)

# ---- 3. Carry-forward both walk directions ----
section("3. Carry-forward — symmetric walk directions (D4)")

# Near→far: DEAD@50 skips d=100
st_nf = camp.CampaignState(os.path.join(tmpdir, "nf.json"))
st_nf.record_verdict("S1", d=50, config_label="SF7", verdict="DEAD", k=10, n=10)
st_nf.commit()
skips = st_nf.get_skips("S2", d=100)
check("near→far: DEAD@50 skips d=100", "SF7" in skips)

# Far→near: CLEAN@200 skips d=100
st_fn = camp.CampaignState(os.path.join(tmpdir, "fn.json"))
st_fn.record_verdict("S3", d=200, config_label="SF7", verdict="CLEAN", k=0, n=15)
st_fn.commit()
skips = st_fn.get_skips("S2", d=100)
check("far→near: CLEAN@200 skips d=100", "SF7" in skips)

# Near→far: CLEAN@50 does NOT skip d=100
st_nf2 = camp.CampaignState(os.path.join(tmpdir, "nf2.json"))
st_nf2.record_verdict("S1", d=50, config_label="SF7", verdict="CLEAN", k=0, n=15)
st_nf2.commit()
skips = st_nf2.get_skips("S2", d=100)
check("near→far: CLEAN@50 does NOT skip d=100", "SF7" not in skips)

# Far→near: DEAD@200 does NOT skip d=100
st_fn2 = camp.CampaignState(os.path.join(tmpdir, "fn2.json"))
st_fn2.record_verdict("S3", d=200, config_label="SF7", verdict="DEAD", k=10, n=10)
st_fn2.commit()
skips = st_fn2.get_skips("S2", d=100)
check("far→near: DEAD@200 does NOT skip d=100", "SF7" not in skips)

# Anchor contradiction
st_ac = camp.CampaignState(os.path.join(tmpdir, "ac.json"))
st_ac.record_verdict("S2", d=100, config_label="SF7", verdict="DEAD", k=10, n=10)
st_ac.commit()
st_ac.record_verdict("S3", d=200, config_label="SF7", verdict="CLEAN", k=0, n=15, is_anchor=True)
st_ac.commit()
skips = st_ac.get_skips("S4", d=300)
check("anchor contradiction invalidates skips", "SF7" not in skips)

# ---- 4. Full campaign dry-run ----
section("4. Campaign config building (dry-run)")

for mode in ("probe", "good", "degraded", "cliff"):
    cfgs = camp.build_campaign_configs(mode)
    check(f"{mode}: {len(cfgs)} configs", len(cfgs) > 0, f"got {len(cfgs)}")
    # Every config has required keys
    ok = all(all(k in c for k in ("mod", "pa", "freq", "plen", "gap", "label"))
             for c in cfgs)
    check(f"{mode}: all configs have required keys", ok)

# Probe = 2 canaries
cfgs = camp.build_campaign_configs("probe")
check("probe has exactly 2 configs", len(cfgs) == 2, f"got {len(cfgs)}")
mods = [c["mod"] for c in cfgs]
check("probe has FLRC + LoRa", "flrc" in mods and "lora" in mods)

# Dual-band probe
cfgs = camp.build_campaign_configs("probe", band="both")
check("dual-band probe = 4 configs", len(cfgs) == 4, f"got {len(cfgs)}")

# Good ≈ 25
cfgs = camp.build_campaign_configs("good")
check("good 23-30 configs", 23 <= len(cfgs) <= 30, f"got {len(cfgs)}")

# Degraded ≈ 8
cfgs = camp.build_campaign_configs("degraded")
check("degraded 7-12 configs", 7 <= len(cfgs) <= 12, f"got {len(cfgs)}")

# Cliff = SF5-SF12
cfgs = camp.build_campaign_configs("cliff")
sfs = [c.get("sf") for c in cfgs if c["mod"] == "lora"]
check("cliff has SF5-SF12", 5 in sfs and 12 in sfs, f"got {sfs}")

# ---- 5. SPRT decision table ----
section("5. SPRT decision table (plan §3)")

# 0 errors → CLEAN at n=15
check("0 err n=15 → CLEAN", camp.sprt_decide(0, 15).verdict == "CLEAN")
# 0 errors at n=14 → UNDECIDED
check("0 err n=14 → UNDECIDED", camp.sprt_decide(0, 14).verdict == "UNDECIDED")
# All errors → DEAD at n=10 (n_min floor)
check("10 err n=10 → DEAD", camp.sprt_decide(10, 10).verdict == "DEAD")
# All errors at n=9 → UNDECIDED (below n_min)
check("9 err n=9 → UNDECIDED", camp.sprt_decide(9, 9).verdict == "UNDECIDED")
# 1 error at n=20 → EDGE
check("1 err n=20 → EDGE", camp.sprt_decide(1, 20).verdict == "EDGE")
# 2 errors at n=20 → EDGE
check("2 err n=20 → EDGE", camp.sprt_decide(2, 20).verdict == "EDGE")
# 4 errors at n=10 → DEAD
check("4 err n=10 → DEAD", camp.sprt_decide(4, 10).verdict == "DEAD")

# ---- 6. Wilson CI ----
section("6. Wilson CI (plan §5 table)")

lo, hi = camp.wilson_ci(0, 50)
check("50/0 → [0, 7.1%]", abs(lo - 0) < 0.001 and abs(hi - 0.071) < 0.01,
      f"got [{lo:.4f}, {hi:.4f}]")

lo, hi = camp.wilson_ci(0, 15)
check("15/0 → [0, 20.4%]", abs(lo - 0) < 0.001 and abs(hi - 0.204) < 0.01,
      f"got [{lo:.4f}, {hi:.4f}]")

lo, hi = camp.wilson_ci(10, 10)
check("10/10 → [72.3, 100%]", abs(lo - 0.723) < 0.01 and abs(hi - 1.0) < 0.001,
      f"got [{lo:.4f}, {hi:.4f}]")

# ---- 7. Cliff search dry-run ----
section("7. Cliff search — sentinel + bisect + validation")

SF_AXIS = [5, 6, 7, 8, 9, 10, 11, 12]

# SF5 clean → whole axis clean
def sprt_all_clean(sf_label, n_cap=20):
    return camp.SprtResult("CLEAN", 0, 15)
r = camp.cliff_search(SF_AXIS, sprt_all_clean, d=100)
check("SF5 CLEAN → whole axis clean", r.boundary_lo == 5 and r.boundary_hi == 12)

# SF12 dead → all dead
def sprt_all_dead(sf_label, n_cap=20):
    return camp.SprtResult("DEAD", 10, 10)
r = camp.cliff_search(SF_AXIS, sprt_all_dead, d=100)
check("SF12 DEAD → all dead", r.boundary_lo is None and r.boundary_hi is None)

# Bisect: SF5-7 dead, SF8-12 clean
def sprt_bisect(sf_label, n_cap=20):
    sf = int(sf_label.replace("SF", ""))
    if sf <= 7:
        return camp.SprtResult("DEAD", 10, 10)
    return camp.SprtResult("CLEAN", 0, 15)
r = camp.cliff_search(SF_AXIS, sprt_bisect, d=100)
check("bisect finds SF7/SF8 boundary", r.boundary_lo == 7 and r.boundary_hi == 8,
      f"got lo={r.boundary_lo} hi={r.boundary_hi}")

# With validation at n=50
val_calls = []
def validate_fn(sf_label, n=50):
    val_calls.append((sf_label, n))
    sf = int(sf_label.replace("SF", ""))
    if sf <= 7:
        return camp.SprtResult("DEAD", 40, 50)
    return camp.SprtResult("CLEAN", 0, 50)
r = camp.cliff_search(SF_AXIS, sprt_bisect, d=100, validate_fn=validate_fn)
check("validation at n=50 on boundary cells", len(val_calls) == 2,
      f"got {len(val_calls)} calls")
check("validation at SF7 and SF8",
      set(c[0] for c in val_calls) == {"SF7", "SF8"},
      f"got {val_calls}")
check("all validations at n=50", all(c[1] == 50 for c in val_calls))

# ---- 8. Reset policy dry-run ----
section("8. Reset policy gate")

# Mod change → reset
prev = {"mod": "lora", "band": "868", "pa": 10, "error": False, "stop_id": "S1"}
cur = {"mod": "flrc", "band": "868", "pa": 5, "error": False, "stop_id": "S1"}
check("mod change → reset", camp.maybe_reset(prev, cur, "strict") == True)

# Same mod, strict → reset
cur2 = {"mod": "lora", "band": "868", "pa": 7, "error": False, "stop_id": "S1"}
check("same mod strict → reset", camp.maybe_reset(prev, cur2, "strict") == True)

# Same mod, gated → skip
check("same mod gated → skip", camp.maybe_reset(prev, cur2, "gated") == False)

# Band change → reset (even gated)
cur3 = {"mod": "lora", "band": "2g4", "pa": 10, "error": False, "stop_id": "S1"}
check("band change → reset (gated)", camp.maybe_reset(prev, cur3, "gated") == True)

# Error → reset (even gated)
cur4 = {"mod": "lora", "band": "868", "pa": 10, "error": True, "stop_id": "S1"}
check("error → reset (gated)", camp.maybe_reset(prev, cur4, "gated") == True)

# PA22 → reset (even gated)
cur5 = {"mod": "lora", "band": "868", "pa": 22, "error": False, "stop_id": "S1"}
check("PA22 → reset (gated)", camp.maybe_reset(prev, cur5, "gated") == True)

# Stop change → reset (even gated)
cur6 = {"mod": "lora", "band": "868", "pa": 10, "error": False, "stop_id": "S2"}
check("stop change → reset (gated)", camp.maybe_reset(prev, cur6, "gated") == True)

# ---- 9. State DB integrity ----
section("9. State DB integrity — corrupt JSON recovery")

# Corrupt JSON → fresh start
corrupt_path = os.path.join(tmpdir, "corrupt.json")
with open(corrupt_path, "w") as f:
    f.write('{"partial": broken')
st = camp.CampaignState(corrupt_path)
check("corrupt JSON → fresh start (no crash)", st.get_skips("S1", 50) == set())

# Empty file → fresh start
empty_path = os.path.join(tmpdir, "empty.json")
with open(empty_path, "w") as f:
    f.write("")
st = camp.CampaignState(empty_path)
check("empty file → fresh start", st.get_skips("S1", 50) == set())

# Idempotent commit
st = camp.CampaignState(os.path.join(tmpdir, "idem.json"))
st.record_verdict("S1", d=50, config_label="SF7", verdict="CLEAN", k=0, n=15)
st.commit()
st.commit()  # double
st2 = camp.CampaignState(os.path.join(tmpdir, "idem.json"))
data = st2.get_stop_data("S1")
check("double commit no duplication", data and len(data["SF7"]) == 1,
      f"got {data}")

# ---- Summary ----
print(f"\n{'='*60}")
print(f"V4 REHEARSAL: {PASS} passed, {FAIL} failed")
print(f"{'='*60}")
sys.exit(1 if FAIL > 0 else 0)