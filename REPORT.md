# Task report: V9 barometer

Implemented and pushed commit 8425fe2 on branch task/t_c5287075.

Changes:
- Replaced all `BMP280` references in `tracker/hardware/SCHEMATIC-PLAN.md` with the selected `MS5607-02BA03` cost-pick part.
- Kept the I2C mapping on GPIO20/GPIO21.
- Added custom footprint `balloon:MS56xx_LGA-8_5.0x3.0mm_P0.8mm` under `tracker/hardware/custom.pretty/` with 8 pads, 5.0 x 3.0 mm body, and 0.8 mm pitch.
- Added PROGRESS.md.

Fresh verification run:
- Structural Python check: PASS (8 pads, expected footprint name, 5.0 x 3.0 mm descriptor).
- `kicad-cli fp export svg --fp MS56xx_LGA-8_5.0x3.0mm_P0.8mm --output /tmp/ms56xx-svg tracker/hardware/custom.pretty`: PASS; KiCad parsed and exported the footprint SVG.
- `git diff --check`: PASS.

Scope limitations:
- No instantiated v9 KiCad schematic/PCB exists in this checkout, so full board ERC/DRC cannot yet be run.
- No live JLCPCB API re-verification was run: the referenced `jlc_parts_probe.py` tool is not present in this checkout.

Publication:
- GitHub: origin/task/t_c5287075 pushed successfully.
- ngit: task/t_c5287075 pushed successfully; relay.ngit.dev accepted the branch (nos.lol also reported as unavailable during relay publication).

Remaining gate work:
1. Apply the plan to the actual v9 KiCad schematic/PCB when that artifact exists.
2. Run KiCad ERC/DRC against the instantiated footprint and verify pad numbering against the selected vendor datasheet.
3. Re-run the live JLCPCB stock probe for MS5607-02BA03 and record the returned stock/price evidence.
