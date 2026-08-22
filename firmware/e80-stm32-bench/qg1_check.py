#!/usr/bin/env python3
"""QG1 for t_92c3910f: import sweep script, verify config counts + 2G4 coverage."""
import importlib.util
spec = importlib.util.spec_from_file_location(
    "e80_sweep_full",
    "/home/c03rad0r/repos/balloon-e80bench/firmware/e80-stm32-bench/tools/e80_sweep_full.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

cfgs = m.build_configs()
b868 = [c for c in cfgs if c["freq"] <= 870_000_000]
b2g4 = [c for c in cfgs if c["freq"] >= 2_400_000_000]
print(f"total configs: {len(cfgs)}  (868 MHz: {len(b868)}, 2.4 GHz: {len(b2g4)})")
print(f"BAUD={m.BAUD}  OUT_STEM={m.OUT_STEM}")
assert m.BAUD == 2000000
assert all(c["freq"] <= 870_000_000 or 2_400_000_000 <= c["freq"] <= 2_483_500_000 for c in cfgs), \
    "config outside allowed bands"
labels = [c["label"] for c in b2g4]
print("2G4 labels sample:", labels[:3], "...", labels[-2:])
freqs = sorted({c["freq"] for c in b2g4})
print("2G4 distinct freqs (MHz):", [f / 1e6 for f in freqs])
# every 2G4 config must trigger the override path check in run_config
for c in b2g4:
    assert not (m.BAND_MIN_HZ <= c["freq"] <= m.BAND_MAX_HZ), "2G4 config wrongly in-band"
print("QG1 PASS")
