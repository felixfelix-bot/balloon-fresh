#!/usr/bin/env bash
# hub_v9_cycle.sh -- ONE command for the whole hub v9 route→refill→DRC→gate cycle.
#
# WHY: this exact sequence was hand-run ~6 times this session (export DSN,
# route with FreeRouting, import SES, refill zones, run KiCad DRC, run
# fab_preflight, append the scorecard row). Every repetition burned tokens
# re-deriving the same flags and the same java/venv incantations. Script it
# once, call it with one argument.
#
# USAGE:
#   tracker/hardware/hub_v9_cycle.sh <board.kicad_pcb> [--passes N] [--skip-route]
#
# BOARD defaults to the stitched hub. Outputs land next to the board as
# <stem>_routed.kicad_pcb plus artefacts in $WORK (/tmp by default), and one
# row is appended to tracker/hardware/drc_snapshots/history.jsonl.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HWDIR="$REPO/tracker/hardware"
PY=/usr/bin/python3.14
export JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64
WORK="${WORK:-/tmp}"
PASSES=12
THREADS=3
SKIP_ROUTE=0

BOARD="${1:-$HWDIR/hub_board_v9_routed_stitched.kicad_pcb}"
shift || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --passes) PASSES="$2"; shift 2;;
    --threads) THREADS="$2"; shift 2;;
    --skip-route) SKIP_ROUTE=1; shift;;
    --work) WORK="$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done

STEM="$(basename "$BOARD" .kicad_pcb)"
ROUTED="$HWDIR/${STEM}_routed.kicad_pcb"
DSN="$WORK/${STEM}.dsn"
SES="$WORK/${STEM}.ses"
FRLOG="$WORK/fr_${STEM}.log"

echo "=== hub_v9_cycle: $STEM (passes=$PASSES threads=$THREADS skip_route=$SKIP_ROUTE)"

# 0. guard: no stale routers competing for CPU (the 2026-10-12 trap -- a
#    leftover session halved throughput and looked like a stall). NEVER kill a
#    router that is making progress: only reap ones older than $STALE_MIN min.
STALE_MIN="${STALE_MIN:-45}"
for pid in $(pgrep -f "freerouting.jar" || true); do
  age_min=$(( ( $(date +%s) - $(stat -c %Y "/proc/$pid" 2>/dev/null || echo 0) ) / 60 ))
  etime=$(ps -o etimes= -p "$pid" 2>/dev/null | tr -d ' ' || echo 0)
  age_min=$(( ${etime:-0} / 60 ))
  if [[ "${age_min:-0}" -ge "$STALE_MIN" ]]; then
    echo "  reaping STALE router pid=$pid (age ${age_min}m >= ${STALE_MIN}m)"
    kill "$pid" 2>/dev/null || true
  else
    echo "  router pid=$pid is live (age ${age_min}m) -- NOT killing" >&2
  fi
done
sleep 2

# 1. export DSN (also merges the unjoinable wing-socket pad-halves)
if [[ $SKIP_ROUTE -eq 0 ]]; then
  "$PY" "$HWDIR/route_hub_v9_freerouting.py" "$BOARD" \
      --out "$ROUTED" --workdir "$WORK" --passes "$PASSES" --threads "$THREADS" \
      2>&1 | grep -vE "Debug|^$" | tail -8
else
  echo "--- skip-route: reusing existing SES/ROUTED if present"
fi

# 2. refill zones (stitching/route invalidate fill -- the 753->55 trap)
"$PY" - "$ROUTED" <<'PYEOF'
import sys
sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew
p = sys.argv[1]
b = pcbnew.LoadBoard(p)
ok = pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(p, b)
print(f"  refill ok: {ok}")
PYEOF

# 3. KiCad DRC -> JSON
DRCJSON="$WORK/drc_${STEM}.json"
kicad-cli pcb drc --severity-error --format json -o "$DRCJSON" "$ROUTED" 2>&1 | tail -1

# 4. fab gate (waived vs real)
GATE_RC=0
"$PY" "$HWDIR/fab_preflight.py" "$DRCJSON" || GATE_RC=$?

# 5. scorecard row (drc_score.py runs its own DRC; label pins the attempt)
"$PY" "$HWDIR/drc_score.py" "$ROUTED" --label "cycle-$(date +%H%M)" 2>&1 | tail -4

echo "=== DONE gate_rc=$GATE_RC"
exit $GATE_RC