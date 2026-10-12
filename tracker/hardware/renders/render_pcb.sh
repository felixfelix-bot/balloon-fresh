#!/usr/bin/env bash
# PCB 3D render pipeline — balloon-fresh tracker boards.
#
# Produces raytraced 3D PNG renders (top + bottom) with component bodies.
# See docs/analysis/pcb-render-pipeline.md for the full explanation.
#
# Usage:
#   tracker/hardware/renders/render_pcb.sh                 # both boards, top+bottom
#   tracker/hardware/renders/render_pcb.sh hub_board_v9    # one board (short name)
#   WIDTH=3200 HEIGHT=2400 QUALITY=high tracker/hardware/renders/render_pcb.sh
#
# Env vars honoured: WIDTH, HEIGHT, QUALITY, RENDER_DIR
set -euo pipefail

# ---- REQUIRED: point KiCad at the official 3D model packages -------------
# Without these, ${KICAD9_3DMODEL_DIR} / ${KICAD8_3DMODEL_DIR} in the board file
# templates resolve to a package default (Debian: /usr/share/kicad/3dmodels).
# That default is an accident of packaging — pin it explicitly so the pipeline
# is reproducible on any host.
: "${KICAD9_3DMODEL_DIR:=/usr/share/kicad/3dmodels}"
: "${KICAD8_3DMODEL_DIR:=/usr/share/kicad/3dmodels}"
export KICAD9_3DMODEL_DIR KICAD8_3DMODEL_DIR

if [ ! -d "$KICAD9_3DMODEL_DIR" ]; then
  echo "ERROR: KICAD9_3DMODEL_DIR=$KICAD9_3DMODEL_DIR does not exist." >&2
  echo "Install it:  sudo apt-get install -y kicad-packages3d" >&2
  exit 2
fi

# ---- locate repo root (script lives in tracker/hardware/renders/) --------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"

WIDTH="${WIDTH:-1600}"
HEIGHT="${HEIGHT:-1200}"
QUALITY="${QUALITY:-high}"
RENDER_DIR="${RENDER_DIR:-tracker/hardware/renders}"
mkdir -p "$RENDER_DIR"

# short-name -> board path
declare -A BOARDS=(
  [wing_board_v9]="tracker/hardware/wing_board/wing_board_v9.kicad_pcb"
  [hub_board_v9]="tracker/hardware/hub_board_v9.kicad_pcb"
)

if [ "$#" -gt 0 ]; then
  WANT=("$@")
else
  WANT=(wing_board_v9 hub_board_v9)
fi

for name in "${WANT[@]}"; do
  board="${BOARDS[$name]:-}"
  if [ -z "$board" ]; then
    echo "ERROR: unknown board '$name' (known: ${!BOARDS[*]})" >&2
    exit 2
  fi
  for side in top bottom; do
    out="$RENDER_DIR/${name}_${side}.png"
    echo ">>> rendering $name ($side) -> $out"
    kicad-cli pcb render \
      --output "$out" \
      --side "$side" \
      --zoom 1 \
      --quality "$QUALITY" \
      --width "$WIDTH" \
      --height "$HEIGHT" \
      "$board"
  done
done

# ---- model-coverage report (kicad-cli does NOT warn; we must) -----------
echo
echo "=== 3D model coverage warning check ==="
echo "kicad-cli pcb render exits 0 and prints NO warning for missing 3D models."
echo "Verify coverage statically instead:"
python3 - "$REPO_ROOT" <<'PY'
import re, sys, os
root = sys.argv[1]
for board in ("tracker/hardware/wing_board/wing_board_v9.kicad_pcb",
              "tracker/hardware/hub_board_v9.kicad_pcb"):
    p = os.path.join(root, board)
    s = open(p).read()
    parts = re.split(r'\n[\t ]*\(footprint ', s)
    total = len(parts) - 1
    withm = sum(1 for b in parts[1:] if '(model ' in b)
    print(f"  {board}: {withm}/{total} footprints have a (model ...) block")
PY

echo "done."
