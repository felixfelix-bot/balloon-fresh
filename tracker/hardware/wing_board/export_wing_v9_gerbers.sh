#!/usr/bin/env bash
# JLCPCB order package for the v9 WING board (tracker/hardware/wing_board/wing_board_v9.kicad_pcb).
# Mirrors the v8f/v8h/v8i/v8j package convention (same layer naming, same zip layout,
# same empty-gerber sanity table) but for a 2-layer 0.6 mm board.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/../output"
mkdir -p "$OUT"
cd "$OUT"
B=wing_board_v9
SRC="$HERE/wing_board_v9.kicad_pcb"
D=gerbers_wing_v9
rm -rf "$D"; mkdir -p "$D"

kicad-cli pcb export gerbers --output "$D/" \
  --layers "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts" \
  "$SRC"
kicad-cli pcb export drill --output "$D/" --format excellon --drill-origin absolute \
  --excellon-separate-th "$SRC"
kicad-cli pcb export pos --format csv --units mm --output "$D/pos_wing_v9.csv" "$SRC"

( cd "$D" && zip -q -r "../${D}_jlcpcb.zip" . )

echo "=== package ==="
ls -la "${D}_jlcpcb.zip"
sha256sum "${D}_jlcpcb.zip"
echo "=== layer sanity (a >1KB file with no D-codes is the classic empty-gerber trap) ==="
printf "%-40s %9s %8s %7s %8s\n" FILE BYTES D-CODES DRAWS FLASHES
for f in "$D"/*; do
  case "$f" in
    *.gbr|*.g1|*.g2|*.gtl|*.gbl|*.gts|*.gbs|*.gto|*.gbo|*.gtp|*.gbp|*.gm1)
      printf "%-40s %9d %8d %7d %8d\n" "$(basename "$f")" "$(stat -c%s "$f")" \
        "$(grep -c '^%AD' "$f" || true)" "$(grep -c 'D0[12]\*' "$f" || true)" "$(grep -c 'D03\*' "$f" || true)" ;;
  esac
done
echo "drill files:"
for d in "$D"/*.drl; do [ -f "$d" ] && echo "  $(basename "$d"): $(grep -c '^X' "$d" || true) holes"; done
echo "CPL rows: $(($(wc -l < "$D/pos_wing_v9.csv") - 1))"
