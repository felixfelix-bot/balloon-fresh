# PROGRESS — analysis/array-overhang-support

Task: work out + record what the operator's "panels may overhang the board" decision
implies (ADR-055 amendment + mechanical analysis), without re-placing the board.

Branch: `analysis/array-overhang-support` · worktree `/home/c03rad0r/worktrees/bf-arrayover`
Base: `github/main` @ `716974a` (fetched fresh).

## Cluster 1 — recon (DONE)

Read in full on this branch: ADR-049, 051, 052, 054, 055 (+ its 2026-10-07 append), 062;
`docs/analysis/hub-thickness-deflection.md` (+model), `docs/analysis/hub-outline-authority.md`,
`docs/analysis/wing-mass-shape.md`, `tracker/hardware/PLACEMENT-S0-FREEZE-v9-hub.md`,
`docs/analysis/jlcpcb-size-tier-quote.md` (salvage branch — the concurrent pricing doc's source),
the `pcb-fab-readiness-gating` skill reference `solar-cell-and-array-selection.md`.

Key evidence located:
- component courtyard demand **2582 mm²** measured (PLACEMENT-S0-FREEZE-v9-hub §3);
  55×45 = 2475 mm², usable interior 2279 mm², needs **96.7 %** packing → the rejection.
- no Si flexural strength / modulus of rupture anywhere in repo or datasheets → the
  unsupported-span ALLOWABLE is `TODO(unverified)`.
- Si modulus 170 GPa is carried as "standard" in hub-thickness-deflection.md §3 (only property used).
- ADR-049 Open items: "whether spine-and-ribs leaves unsupported silicon spans that crack;
  the frame's rib pitch is set by that answer" → explicitly unresolved.
- ADR-055 §8 append: verdict `cannot be settled from the record`; one coupon bend test closes it.

## Cluster 2 — arithmetic model (DONE)

`docs/analysis/hub_array_overhang_model.py` (committed with the analysis). Findings:

1. **Tiling in 103×103 mm:** LARGE 78.55×38.90 → **max 2 cells = 61.11 cm²** (58 % of 106.1).
   SMALL 52.07×19.65 → max 8 = 81.85 cm² (77 %). Neither reaches 106.1 cm².
   → the "~2 LARGE cells tile inside 103 mm (~61 cm²)" claim is **CORRECT**; and it exposes
   that ADR-055 D5's own 103 mm board **cannot hold the ≥4 LARGE cells its 106.1 cm² target needs**.
2. **Unsupported-span demand** (0.21 mm Si, self-weight): σ = 3ρgL²/(4t), δ = 5ρgL⁴/(32Et²).
   78.55 mm span @1 g → **0.504 MPa, 18.1 µm sag**; @2 g → 1.007 MPa, 36 µm.
   Cantilever (one end uncarried) = 4× σ (2.01 MPa) / 9.6× δ (174 µm).
   103 mm span @1 g → 0.866 MPa. **Allowable: unsourced → TODO(unverified).**
3. **Array area with overhang:** decoupled from board. 60 mm board + 21.5 mm overhang/side →
   103 mm footprint = 106.1 cm² (100 % duty); 4 LARGE = 122.2 cm² (115 %); 6 LARGE = 183.3 (173 %).
   → overhang **buys duty margin**, not only board saving.
4. **Mass per option** (122.2 cm² of cells = 5.980 g): full carrier 0.6 mm 19.523 g / 0.4 mm
   15.009 g; skeletonised 28.4 % board 10.408 / 8.932 g; spine+ribs (measured) 12.460 g;
   cells+harness + separate electronics board 10.904 g.
5. **Component floor:** 25.82 cm² @72 % packing → **≥ 59.9 mm square**; candidate **60 × 60 mm
   = 36.0 cm²**, 0.4 mm = 3.064 g. Longest side 60 mm ≤ 102 mm cheap-tier (measured boundary).
6. **Thickness lever re-quantified:** 103×103 saves 4.514 g; 60×60 saves only **1.532 g** →
   ADR-055 D4's prize shrinks 3× → D4 amended.
7. **Price tier:** measured cliff at 102/102.5 mm (103 mm 4L = $31.60; 102 mm = $8.00). A 60 mm
   outline is far inside the cheap class; the 103 mm board is just over the cliff.

## Cluster 3 — writes (IN PROGRESS)

- [ ] `docs/analysis/hub-array-overhang-and-support.md`
- [ ] ADR-055 amendment (appended section only)
- [ ] ADR-063 (allocator: next free = 063; verified across all refs)
- [ ] `docs/adr/INDEX.md` regenerated
- [ ] `python3 -m pytest tests/ -q --continue-on-collection-errors`
- [ ] push github, then ngit (separately); verify both with `git ls-remote`
