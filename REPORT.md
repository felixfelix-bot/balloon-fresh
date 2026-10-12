# REPORT — hub array carrier

Task: t_35cffc06, branch pr/hub-array-carrier.

Implemented the ADR-063 acceptance record dated 2026-10-11. The accepted direction is limited to a separate overhanging carrier; rib pitch, maximum overhang, array area, hub outline, placement, routing, BOM, and fabrication remain unfrozen.

Materialized and updated the existing hub overhang analysis/model. The model now prints `RIB_PITCH = TODO(bench)`, a repeatable end-only coupon procedure (1 g/2 g, cold soak near -55 C, thermal cycles), and the post-measurement rule `pitch <= S_crack` with margin. It prints ADR-051's 64.9 cm² vertical-plane and 106.1 cm² horizontal-hub figures and shows 106.1 / 30.5559 = 3.47, therefore 4 LARGE cells = 122.2 cm² minimum.

Corrected harvest language: ADR-065's 2x claim applies to a vertical wing; the horizontal hub under-face sees albedo/undercast, not a second full sun. Back-face contribution is explicitly TODO(measurement), not assumed.

Fresh verification: `python3 docs/analysis/hub_array_overhang_model.py` passed; `python3 -m py_compile docs/analysis/hub_array_overhang_model.py` passed. Full `python3 -m pytest -q` collected 257 tests but was blocked during collection by five pre-existing checkout/environment errors: three missing conftest loader imports and two missing ESP-IDF openocd binaries. No test failure reached the changed model. Evidence is recorded in PROGRESS.md.

Commit 714bd10 plus verification-evidence commit 4ac6429 were pushed to GitHub and ngit. PR: https://github.com/felixfelix-bot/balloon-fresh/pull/151
