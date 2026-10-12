# REPORT — hub array carrier

Task: t_35cffc06, branch pr/hub-array-carrier.

Implemented the ADR-063 acceptance record dated 2026-10-11. The accepted direction is limited to a separate overhanging carrier; rib pitch, maximum overhang, array area, hub outline, placement, routing, BOM, and fabrication remain unfrozen.

Materialized and updated the existing hub overhang analysis/model. The model now prints `RIB_PITCH = TODO(bench)`, a repeatable end-only coupon procedure (1 g/2 g, cold soak near -55 C, thermal cycles), and the post-measurement rule `pitch <= S_crack` with margin. It prints ADR-051's 64.9 cm² vertical-plane and 106.1 cm² horizontal-hub figures and shows 106.1 / 30.5559 = 3.47, therefore 4 LARGE cells = 122.2 cm² minimum.

Corrected harvest language: ADR-065's 2x claim applies to a vertical wing; the horizontal hub under-face sees albedo/undercast, not a second full sun. Back-face contribution is explicitly TODO(measurement), not assumed.

Verification: `python3 docs/analysis/hub_array_overhang_model.py` passed and printed the new figures. `python3 -m pytest tests/test_adr_numbering.py -q` could not run because that path is absent in this checkout (pytest exit 4, no tests collected). No PCB files, gerbers, or footprints were changed.

Remaining: commit, dual-push github and ngit, and open exactly one PR with card ID and CI/n/a evidence in the body.
