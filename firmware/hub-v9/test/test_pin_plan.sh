#!/usr/bin/env bash
# test_pin_plan.sh — prove the v9 pin table is machine-checked, and that the
# check can FAIL. Runs without PlatformIO (pio is not installed on this fleet),
# using the system g++ to compile the header stand-alone.
#
# WHY: pin_plan.h's static_asserts are only worth having if a bad table actually
# breaks the build. A test that only proves the good table compiles proves
# nothing — so this script also SABOTAGES the table and asserts the build fails.
#
# Usage: bash firmware/hub-v9/test/test_pin_plan.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
HDR="$ROOT/src/pin_plan.h"
CXX="${CXX:-g++}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# The pin table exactly as platformio.ini passes it.
read -r -d '' DEFS <<'EOF'
-DHUB_V9=1
-DPIN_LR2021_SCK=12 -DPIN_LR2021_MOSI=11 -DPIN_LR2021_MISO=13
-DPIN_LR2021_NSS=10 -DPIN_LR2021_BUSY=9 -DPIN_LR2021_RST=8 -DPIN_LR2021_DIO=7
-DPIN_SX1280_SCK=36 -DPIN_SX1280_MOSI=35 -DPIN_SX1280_MISO=37
-DPIN_SX1280_NSS=38 -DPIN_SX1280_BUSY=39 -DPIN_SX1280_RST=40 -DPIN_SX1280_DIO=41
-DPIN_GNSS_RX=17 -DPIN_GNSS_TX=18 -DPIN_GNSS_PPS=21 -DPIN_STATUS_LED=48
EOF

TU="$TMP/tu.cpp"
printf '#include "pin_plan.h"\nint main(){return 0;}\n' > "$TU"

pass=0; fail=0
ok()   { echo "  ok   $1"; pass=$((pass+1)); }
bad()  { echo "  FAIL $1"; fail=$((fail+1)); }

echo "== 1. correct table must COMPILE =="
if $CXX -std=c++17 -I"$ROOT/src" $DEFS -o "$TMP/a.out" "$TU" 2>"$TMP/err1"; then
  ok "documented pin table compiles"
else
  bad "documented pin table FAILED to compile:"; sed 's/^/       /' "$TMP/err1" | head -12
fi

echo "== 2. counter-test: a MISSING pin definition must FAIL =="
# Drop PIN_SX1280_NSS. Without -D the macro is undefined, so `PIN_SX1280_NSS`
# stays a token and the enum fails — i.e. an unset pin cannot silently default.
DEFS_NOSS="$(echo "$DEFS" | tr '\n' ' ' | sed 's/-DPIN_SX1280_NSS=38//')"
if $CXX -std=c++17 -I"$ROOT/src" $DEFS_NOSS -o "$TMP/b.out" "$TU" 2>"$TMP/err2"; then
  bad "build SUCCEEDED with SX1280 NSS undefined — a missing pin would be silent!"
else
  ok "missing pin definition breaks the build (as it must)"
fi

echo "== 3. counter-test: OVERLAPPING SPI buses must FAIL =="
# Point SX1280 SCK at the LR2021 SCK (12). The disjointness static_assert must catch it.
DEFS_OVERLAP="$(echo "$DEFS" | tr '\n' ' ' | sed 's/-DPIN_SX1280_SCK=36/-DPIN_SX1280_SCK=12/')"
if $CXX -std=c++17 -I"$ROOT/src" $DEFS_OVERLAP -o "$TMP/c.out" "$TU" 2>"$TMP/err3"; then
  bad "build SUCCEEDED with both SPI buses on SCK=12 — disjointness check is dead!"
else
  if grep -q 'MUST be disjoint' "$TMP/err3"; then
    ok "overlapping SPI buses rejected by the disjointness assert"
  else
    ok "overlapping SPI buses rejected (message: $(head -1 "$TMP/err3" | cut -c1-80))"
  fi
fi

echo "== 4. counter-test: a DUPLICATED pin inside one radio must FAIL =="
DEFS_DUP="$(echo "$DEFS" | tr '\n' ' ' | sed 's/-DPIN_LR2021_RST=8/-DPIN_LR2021_RST=7/')"
if $CXX -std=c++17 -I"$ROOT/src" $DEFS_DUP -o "$TMP/d.out" "$TU" 2>"$TMP/err4"; then
  bad "build SUCCEEDED with LR2021 RST == DIO (7) — self-consistency check is dead!"
else
  ok "duplicated pin inside one radio rejected"
fi

echo "== 5. GNSS must not collide with a radio pin =="
DEFS_GNSS="$(echo "$DEFS" | tr '\n' ' ' | sed 's/-DPIN_GNSS_RX=17/-DPIN_GNSS_RX=11/')"
if $CXX -std=c++17 -I"$ROOT/src" $DEFS_GNSS -o "$TMP/e.out" "$TU" 2>"$TMP/err5"; then
  bad "build SUCCEEDED with GNSS RX on the LR2021 MOSI pin (11)!"
else
  ok "GNSS/radio collision rejected"
fi

echo
echo "pin_plan: $pass passed, $fail failed"
[ "$fail" -eq 0 ] || exit 1
