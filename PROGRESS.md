# Progress — dualband single-dish analysis

- Worktree created at /home/c03rad0r/worktrees/bf-dualband, branch design/dualband-single-dish, base 09e1b69.
- ADR allocator says next free number is 066; no 066+ files found on in-flight github branches.
- Drafted docs/analysis/dualband-single-dish.md §§1–3: surface-accuracy margin + gain-vs-diameter tables.
- Drafted §§4–5: feed illumination half-angle, electrical size at 433 MHz, positioning tolerance.
- Drafted §§6–8: options ranking, mechanical counter-argument, verdict.
- Added repro script docs/analysis/dualband_dish_arithmetic.py; caught and fixed a formula error in the D-for-target-gain inversion (λ/π factor) — doc table corrected to exact values (2.97 m / 2.73 m for 20 dBi at η=0.55/0.65).
- Key findings:
  - Ku dish at 2.4 GHz: fully suitable, huge surface-accuracy margin, 25–27 dBi for 0.9–1.2 m.
  - Ku dish at 433 MHz: too small; 1.2 m gives ~12.5 dBi theoretical, likely 0–6 dBi practical.
  - Two feeds near focus: mechanically viable, ~0.1–0.2 dB penalty at 433, ≤1 dB at 2.4.
  - Best single-positioner option: 2.4 GHz dish + 433 Yagi boresighted on the dish structure.
- ADR decision: NOT reachable yet — the 433 MHz single-reflector gain is a TODO estimate (feed mismatch unverified by measurement or simulation). Analysis states exactly what closes it. ADR number 066 remains unallocated for this topic.
- Remaining: run test suite, final commit + push both remotes, verify with ls-remote, write REPORT.md.
