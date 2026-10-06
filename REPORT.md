# REPORT — MS5611 balloon flight board variant (v8j) salvage

Branch: `pr/ms5611-baro` · Worktree: `/home/c03rad0r/worktrees/bf-ms5611` · Tip at start: `ba73bb9`

## Verdict

**pcb_order_gate: FAIL** (exit 1). The v8j MS5611 variant is an honest **WIP** — it
correctly carries the MS5611-01BA pressure sensor but is not yet fab-clean.

```
ORDER GATE: FAIL board=v8j_krt_ms5611.kicad_pcb board_sha256=cb6e61094455 fab_sha256=ae1bae58dee7 errors=170 unconnected=11 warnings=15 excluded=0 kicad=9.0.8
```

Worst violation rules:
| rule | count |
|---|---|
| violations:clearance | 138 |
| violations:drill_out_of_range | 12 |
| unconnected_items:unconnected_items | 11 |
| violations:hole_clearance | 9 |
| violations:track_dangling | 4 |
| violations:silk_overlap | 3 |

## Step-by-step completion

1. ✅ git status/tip — tip confirmed `ba73bb9`; exactly 3 untracked files present.
2. ✅ Board contents verified on disk: `ms5611` = 3 matches, `bmp280` = 0, footprints = 28.
   U5 = `MS5611-01BA`, footprint `Package_LGA:LGA-8_3x5mm_P1.25mm`. Board is genuinely the MS5611 variant.
3. ✅ Gerbers + drill plotted to `tracker/hardware/output/gerbers_v8j/` (28 gerbers + .drl + .gbrjob).
4. ✅ Order gate run → **FAIL** (quoted above). Verdict bound to sha256 of board (`cb6e61094455…`) and fab package (`ae1bae58dee7…`) in `tracker/hardware/v8j-GATE-RECORD.json`.
5. ⏭️ No targeted fix attempted — 138 clearance + 12 drill + 11 unconnected + 9 hole_clearance + 4 dangling is a broad WIP state, not a single-fix situation. Per instructions, kept as honest WIP variant (coexists with v8i, not overwritten).
6. ⏭️ `--verify` not run (gate FAILed; verify step only applies to PASS).
7. ✅ Committed explicit paths only (no `-A`/`.`/`-a`); `.kicad_prl` excluded.
8. ✅ Pushed `pr/ms5611-baro` to github + ngit; verified both remote SHAs.
9. ✅ PROGRESS.md appended (M2 milestone); this REPORT.md written.

## Artifacts

- `tracker/hardware/output/v8j_krt_ms5611.kicad_pcb` (board)
- `tracker/hardware/output/v8j_krt_ms5611.kicad_pro` (project)
- `tracker/hardware/output/gerbers_v8j/` (fab package)
- `tracker/hardware/v8j-GATE-RECORD.json` (artifact-bound gate verdict)

## Remaining violations (for the next routing pass)

clearance=138, drill_out_of_range=12, unconnected=11, hole_clearance=9,
track_dangling=4, silk_overlap=3, silk_over_copper=3, lib_footprint_mismatch=1,
silk_edge_clearance=3, via_dangling=1.
