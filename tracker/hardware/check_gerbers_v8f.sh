#!/usr/bin/env bash
set -u
cd /home/c03rad0r/worktrees/t_157df236/tracker/hardware/output
D=gerbers_v8f
echo "zip: $(ls -la gerbers_v8f_jlcpcb.zip 2>/dev/null | awk '{print $5" bytes"}')"
printf "%-42s %9s %8s %7s %8s\n" FILE BYTES D-CODES DRAWS FLASHES
for f in "$D"/*.gtl "$D"/*.gbl "$D"/*.g1 "$D"/*.g2 "$D"/*.gts "$D"/*.gbs "$D"/*.gto "$D"/*.gbo "$D"/*.gtp "$D"/*.gbp "$D"/*.gm1; do
  [ -f "$f" ] || continue
  printf "%-42s %9d %8d %7d %8d\n" "$(basename "$f")" "$(stat -c%s "$f")" \
    "$(grep -c '^%AD' "$f")" "$(grep -c 'D0[12]\*' "$f")" "$(grep -c 'D03\*' "$f")"
done
echo "drill:"
for d in "$D"/*.drl; do
  [ -f "$d" ] || continue
  echo "  $(basename "$d"): $(grep -c '^X' "$d") holes"
done
echo "pos rows: $(wc -l < "$D/pos_v8f.csv")"
echo "files: $(ls "$D" | wc -l)"
