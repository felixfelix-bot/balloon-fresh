# Progress: ground-station dish mechanical study

Branch: design/ground-station-dish
Worktree: /home/c03rad0r/worktrees/bf-dish

## 2026-10-08 (session)

- [x] Created worktree from github/main @ 09e1b69.
- [x] OpenSCAD 2021.01 found at /usr/bin/openscad.
- [x] Wrote parametric `hardware/ground-station/dish/dish.scad` with
      shell / petal / ribs modes and export parameters.
- [x] Rendered STLs headlessly:
  - `export/dish_shell_D{600,900,1200,1500}.stl`
  - `export/dish_petal_D1200.stl` (single petal)
  - `export/dish_ribs_D{900,1200}.stl`
  - Triangle counts / bboxes computed by `docs/analysis/ground_station_dish_model.py`.
- [x] Wrote `docs/analysis/ground_station_dish_model.py` (geometry,
      surface budget, wind/torque, print feasibility, STL summary).
- [ ] Write `docs/analysis/ground-station-dish.md`.
- [ ] Commit and push after each milestone.
- [ ] Verify pytest green; verify github/ngit SHAs.
