#!/usr/bin/env bash
# ============================================================================
# fab_grade.sh -- THE v9 HUB FAB-GRADE CHAIN, as one reproducible command.
#
# This exists because the campaign kept losing findings to hand-run commands, and
# because THREE of its defects were the same class: an artifact and its DERIVED
# state drifting apart (a stale DRC report, a stale gerber ZIP, and a stale ZONE
# FILL). Every step below exists to stop that drift.
#
# ORDER MATTERS. Each stage invalidates the next stage's inputs, so a refill MUST
# come after all copper edits, and DRC MUST come after the refill.
#
#   route (strict, no narrowing)
#     -> stitch GND pads to the plane (SAFE: rejects a via that would short)
#       -> REFILL ZONES          (stale fill reads as 0.0000 mm clearance)
#         -> DRC against the FROZEN ruleset
#
# USAGE:
#   tracker/hardware/fab_grade.sh <board.kicad_pcb> [outdir]
#
# Env: KRT=/path/to/KiCadRoutingTools  (default ~/tools/KiCadRoutingTools)
# ============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOARD="${1:?usage: fab_grade.sh <board.kicad_pcb> [outdir]}"
OUT="${2:-$HERE/output/fabgrade}"
KRT="${KRT:-$HOME/tools/KiCadRoutingTools}"
if [ ! -d "$KRT/py_router" ]; then KRT="$HOME/repos/KiCadRoutingTools"; fi
PY="$KRT/.venv/bin/python"
[ -x "$PY" ] || PY=python3

# The FROZEN ruleset, and the project the board must be graded against.
RULES="$HERE/jlcpcb-s1-frozen.kicad_dru"
PROJ="$HERE/hub_board_v9.kicad_pro"

mkdir -p "$OUT"
STEM="$(basename "$BOARD" .kicad_pcb)"

echo "=== fab_grade chain: $STEM"
echo "    KRT   : $KRT"
echo "    rules : $RULES"
echo

# --- 0. preflight -----------------------------------------------------------
for f in "$RULES" "$PROJ"; do
  [ -f "$f" ] || { echo "MISSING: $f"; exit 1; }
done
command -v kicad-cli >/dev/null || { echo "MISSING: kicad-cli"; exit 1; }
echo "[0] preflight ok"

# --- 1. route: STRICT fab floor, escalation OFF -----------------------------
# --escalation off  =>  "sizes and clearances are exact; a net that cannot
# complete at them FAILS AND IS REPORTED; nothing is narrowed or shrunk."
# This is the whole point: a board that 'passes' at 0.0889 mm is a lie.
echo "[1] routing at the FROZEN floor (0.20 track / 0.20 clr / 0.60 via / 0.30 drill), escalation off"
"$PY" "$KRT/py_router/route.py" "$BOARD" "$OUT/${STEM}_strict.kicad_pcb" \
    --track-width 0.2 --clearance 0.2 --via-size 0.6 --via-drill 0.3 \
    --escalation off --json-out "$OUT/${STEM}_strict_route.json" 2>&1 \
  | grep -E 'Single-ended|Multi-point|escalat' || true
ROUTED="$OUT/${STEM}_strict.kicad_pcb"
[ -f "$ROUTED" ] || { echo "ROUTE FAILED to produce $ROUTED"; exit 1; }

# --- 2. stitch GND pads to the plane (v2: safe, rejects shorts) -------------
echo "[2] stitching GND pads (safe mode)"
python3 "$HERE/stitch_gnd_planes.py" "$ROUTED" "$OUT/${STEM}_stitched.kicad_pcb" \
  | sed 's/^/    /'
STITCHED="$OUT/${STEM}_stitched.kicad_pcb"

# --- 3. REFILL ZONES -- without this, DRC reads a stale fill ----------------
# Measured: 504 'clearance ... actual 0.0000 mm' violations were ALL stale fill.
echo "[3] refilling zones (REQUIRED after any copper edit)"
python3 "$HERE/refill_zones.py" "$STITCHED" "$OUT/${STEM}_filled.kicad_pcb" | sed 's/^/    /'
FILLED="$OUT/${STEM}_filled.kicad_pcb"

# --- 4. grade against the FROZEN ruleset -----------------------------------
# Copy the FROZEN project so the router's own relaxed .kicad_pro cannot be used
# to grade itself.
echo "[4] DRC against the FROZEN rules"
cp "$PROJ" "${FILLED%.kicad_pcb}.kicad_pro"
cp "$RULES" "${FILLED%.kicad_pcb}.kicad_dru"
kicad-cli pcb drc --format json --severity-all \
    --output "$OUT/${STEM}_drc.json" "$FILLED" 2>&1 | tail -2

python3 - "$OUT/${STEM}_drc.json" <<'PY'
import json, sys
from collections import Counter
d = json.load(open(sys.argv[1]))
v = d.get("violations", []); u = d.get("unconnected_items", [])
sev = Counter(x.get("severity") for x in v)
typ = Counter(x.get("type") for x in v)
print()
print(f"  unconnected : {len(u)}")
print(f"  violations  : {len(v)}   {dict(sev)}")
for t, n in typ.most_common():
    print(f"      {t:26} {n}")
print()
print("  VERDICT:", "CLEAN" if not v and not u else "NOT ORDERABLE")
PY
echo
echo "chain artifacts in $OUT"
