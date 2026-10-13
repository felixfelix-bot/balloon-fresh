#!/usr/bin/env bash
# JLCPCB order package for the v8h board: U2 = custom:LoRa2021_Castellated (18-pad),
# nets remapped to the flight plan, RF_OUT widened 0.39mm. Mirrors the v8f package layout.
set -eu
cd "$(dirname "$0")/output"
B=v8h_krt_u2_lora2021
D=gerbers_v8h
rm -rf "$D"; mkdir -p "$D"

kicad-cli pcb export gerbers --output "$D/" --layers "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts" "$B.kicad_pcb"
kicad-cli pcb export drill --output "$D/" --format excellon --drill-origin absolute --excellon-separate-th "$B.kicad_pcb"
kicad-cli pcb export pos --format csv --units mm --output "$D/pos_v8h.csv" "$B.kicad_pcb"
kicad-cli pcb export ipc2581 --output "$D/$B.ipc2581" "$B.kicad_pcb" >/dev/null 2>&1 || true

# JLCPCB wants a single zip named <board>_gerbers.zip-ish; keep the same convention as v8f
( cd "$D" && zip -q -r "../${D}_jlcpcb.zip" . )

echo "=== package ==="
ls -la "../${D}_jlcpcb.zip"
echo "=== layer sanity (a >1KB file with no D-codes is the classic empty-gerber trap) ==="
printf "%-34s %9s %8s %7s %8s\n" FILE BYTES D-CODES DRAWS FLASHES
for f in "$D"/*; do
  case "$f" in
    *.gbr|*.g1|*.g2|*.gtl|*.gbl|*.gts|*.gbs|*.gto|*.gbo|*.gtp|*.gbp|*.gm1)
      printf "%-34s %9d %8d %7d %8d\n" "$(basename "$f")" "$(stat -c%s "$f")" \
        "$(grep -c '^%AD' "$f" || true)" "$(grep -c 'D0[12]\*' "$f" || true)" "$(grep -c 'D03\*' "$f" || true)" ;;
  esac
done
echo "drill files:"; ls "$D"/*.drl 2>/dev/null || echo "  (none — check excellon output)"
for d in "$D"/*.drl; do [ -f "$d" ] && echo "  $(basename "$d"): $(grep -c '^X' "$d" || true) holes"; done
