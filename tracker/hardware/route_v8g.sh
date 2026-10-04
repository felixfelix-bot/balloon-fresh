#!/usr/bin/env bash
# Re-route the v8g board (U2 = NiceRF LoRa2021 18-pin land pattern) from the
# copper-free placement input, deterministically, at $0 inference.
#
# Card t_f48320db.  Recipe = PCB-S1-ROUTING.md S1b flags (the ones that produced
# the v8b/v8e/v8f family) PLUS:
#   --strict-sizes + --same-net-pad-clearance 0.2   (the v8e/v8f margin recipe)
#   RF_OUT routed at 0.39 mm                        (card step 4: 50 ohm on the
#                                                    JLCPCB 4-layer stackup,
#                                                    h ~ 0.21 mm, Er ~ 4.4)
set -euo pipefail

KRT=${KRT:-$HOME/repos/KiCadRoutingTools}
H=/home/c03rad0r/repos/balloon-fresh/.worktrees/t_f48320db/tracker/hardware
IN=$H/output/.placement/v8g_placement_input.kicad_pcb
OUT=$H/output/v8g_krt_routed.kicad_pcb
FROZEN_DRU=$H/jlcpcb-s1-frozen.kicad_dru
FROZEN_PRO=$H/output/v8f_krt_margin_escaped.kicad_pro

# The router and the zone filler both resolve rules from the SIBLING files of the
# board path, so the output gets byte-identical frozen siblings BEFORE the run.
cp -f "$FROZEN_DRU" "${OUT%.kicad_pcb}.kicad_dru"
cp -f "$FROZEN_PRO" "${OUT%.kicad_pcb}.kicad_pro"

cd "$KRT"
/usr/bin/python3.14 py_router/route.py "$IN" "$OUT" '*' \
    --track-width 0.2 --clearance 0.2 --via-size 0.6 --via-drill 0.3 \
    --power-nets GND +3V3 RF_OUT --power-nets-widths 0.3 0.3 0.39 \
    --fab-tier standard --no-fix-drc-settings --write-fill --stats \
    --strict-sizes --same-net-pad-clearance 0.2 \
    --json-out "$H/output/s1b/v8g_route_summary.json" || rc=$?
echo "router exit: ${rc:-0}"

# The router rewrites the sibling .kicad_pro's DRC floor unless told not to; the
# frozen bytes are restored regardless, and verified by hash before any scoring.
cp -f "$FROZEN_DRU" "${OUT%.kicad_pcb}.kicad_dru"
cp -f "$FROZEN_PRO" "${OUT%.kicad_pcb}.kicad_pro"
sha256sum "${OUT%.kicad_pcb}.kicad_dru" "${OUT%.kicad_pcb}.kicad_pro"
sha256sum "$OUT"
