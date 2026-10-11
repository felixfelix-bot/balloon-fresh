# Progress

- Baseline reconciled with origin/main and imported bd2980c 3D model assets → status: saved → files: generator, board, model assets.
- Added RED-first double-sided acceptance tests (initially 3 failures) → status: fixed and 21 tests green → files: tests/test_wing_double_sided.py, tests/test_3d_models_wing.py.
- Parametrized footprint/cell side and generated SC4-SC6 on B.Cu with mirrored pads/text and parallel-string topology → status: regenerated → files: tracker/hardware/wing_board/build_wing_v9.py, wing_board_v9.kicad_pcb.
- Added face-aware courtyard coverage and refreshed fab outputs → status: 100% coverage, 0 overlaps → files: tracker/hardware/courtyard_coverage.py, tracker/hardware/output/gerbers_wing_v9*, gate record.
