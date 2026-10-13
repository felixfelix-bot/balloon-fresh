#!/usr/bin/env bash
# v8j: finish the MS5611 lap deterministically at $0 inference.
#
# Scope = the FIVE nets the salvaged board left broken:
#   GND        U5 pads 2/3/6 (SMD) need a via/track to the In1 GND plane
#   EN         the U5 swap deleted the (18.3,31.9)->(18.3,35.2)->(25.08,42.0)
#              run to J1.3 because the wider MS5611 courtyard crossed it
#   +3V3       U5 pads 1/4/5
#   I2C_SDA    U5 pad 7
#   I2C_SCL    U5 pad 8
#
# Everything else on the v8i-derived board is READ-ONLY (--keep-input-copper),
# so the hand-laid GNSS/RF feed and all v8i routing survive byte-for-byte.
# KRT only DROPS power/ground from a component scope it does not name, so GND is
# named explicitly in --nets.
set -euo pipefail

KRT=${KRT:-$HOME/repos/KiCadRoutingTools}
H=/home/c03rad0r/worktrees/v8j-ms5611-reroute/tracker/hardware
IN=$H/output/v8j_u5net.kicad_pcb
OUT=$H/output/v8j_krt_ms5611.kicad_pcb
FROZEN_DRU=$H/output/v8i_krt_gnss.kicad_dru
FROZEN_PRO=$H/output/v8j_u5net.kicad_pro

cp -f "$FROZEN_DRU" "${OUT%.kicad_pcb}.kicad_dru"
cp -f "$FROZEN_PRO" "${OUT%.kicad_pcb}.kicad_pro"

cd "$KRT"
rc=0
/usr/bin/python3.14 py_router/route.py "$IN" \
    --output "$OUT" \
    --nets GND EN I2C_SDA I2C_SCL +3V3 --keep-input-copper \
    --track-width 0.2 --clearance 0.2 --via-size 0.6 --via-drill 0.3 \
    --power-nets GND +3V3 --power-nets-widths 0.3 0.3 \
    --fab-tier standard --no-fix-drc-settings --write-fill --stats \
    --strict-sizes --same-net-pad-clearance 0.2 \
    --json-out "$H/output/v8j_route_summary.json" || rc=$?
echo "router exit: ${rc:-0}"

cp -f "$FROZEN_DRU" "${OUT%.kicad_pcb}.kicad_dru"
cp -f "$FROZEN_PRO" "${OUT%.kicad_pcb}.kicad_pro"
sha256sum "${OUT%.kicad_pcb}.kicad_dru" "${OUT%.kicad_pcb}.kicad_pro" "$OUT"
