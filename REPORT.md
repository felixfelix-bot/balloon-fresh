# PCBPROG-0c report

Merged `feat/3d-models-hub`, `feat/3d-models-wing`, and `feat/board-view-renderer` into `kanban/t_74f49709`.
Replaced all `${KICAD9_3DMODEL_DIR}` references in the hub board with committed `${KIPRJMOD}` VRML models; zero external model references remain.
Verified `/usr/bin/python3.14` imports pcbnew (KiCad 9.0.8).
Rendered hub board with:
`kicad-cli pcb render -D KIPRJMOD=$PWD -o tracker/hardware/hub_board/renders/hub_v9_iso.png --rotate '-45,0,45' --width 1600 --height 1000 tracker/hardware/hub_board_v9.kicad_pcb`
Render exists, is a 1568x984 RGBA PNG, sha256 `6bce44b94b170d05e6eca834e7d2af2af141f2df124426792f986024b09d06dd`.
Push observed to `origin/kanban/t_74f49709`.
