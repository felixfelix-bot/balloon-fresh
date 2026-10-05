#!/usr/bin/env bash
# JLCPCB order package for the v8i board (card t_3c28ba1f):
#   v8h + GNSS U.FL (ANT2) + computed pi pads + 4x M2 NPTH mounting holes.
# Mirrors the v8f / v8h package layout exactly (same layers, same zip convention).
set -eu
cd "$(dirname "$0")/output"
B=v8i_krt_gnss
D=gerbers_v8i
rm -rf "$D"; mkdir -p "$D"

kicad-cli pcb export gerbers --output "$D/" --layers "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts" "$B.kicad_pcb"
kicad-cli pcb export drill --output "$D/" --format excellon --drill-origin absolute --excellon-separate-th "$B.kicad_pcb"
kicad-cli pcb export pos --format csv --units mm --output "$D/pos_v8i.csv" "$B.kicad_pcb"
kicad-cli pcb export ipc2581 --output "$D/$B.ipc2581" "$B.kicad_pcb" >/dev/null 2>&1 || true

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
echo "CPL rows: $(($(wc -l < "$D/pos_v8i.csv") - 1))"
