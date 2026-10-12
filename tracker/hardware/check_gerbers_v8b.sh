#!/usr/bin/env bash
# Gerber sanity check for the S1b fab candidate (card t_157df236).
# An "empty" gerber is the classic trap: file exists, is > 1 KB, but carries
# no apertures / no draws / no flashes.
set -u
cd "$(dirname "$0")" || exit 1
D=output/gerbers_v8b
printf "%-42s %9s %8s %7s %8s %8s\n" FILE BYTES "D-CODES" DRAWS FLASHES ARCS
for f in F_Cu.gtl B_Cu.gbl In1_Cu.g1 In2_Cu.g2 F_Mask.gts B_Mask.gbs \
         F_Paste.gtp F_Silkscreen.gto B_Silkscreen.gbo Edge_Cuts.gm1; do
  p="$D/v8b_krt_routed-$f"
  [ -f "$p" ] || { printf "%-42s MISSING\n" "$f"; continue; }
  b=$(stat -c%s "$p")
  dc=$(grep -c '^%AD' "$p" || true)
  # Gerber ops are coordinate-prefixed (X123Y456D01*), so match the D-code,
  # not the line start.
  dr=$(grep -c 'D0[12]\*' "$p" || true)
  fl=$(grep -c 'D03\*' "$p" || true)
  ar=$(grep -c '^G0[23]' "$p" || true)
  printf "%-42s %9d %8d %7d %8d %8d\n" "$f" "$b" "$dc" "$dr" "$fl" "$ar"
done
echo
echo "drill holes total: $(grep -c '^X' "$D/v8b_krt_routed.drl" || true)"
echo "drill report:"
grep -E "Total|mm +0" "$D/v8b-drill-report.txt" || true
