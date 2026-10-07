#!/bin/sh
# Render docs/v9-system-diagram.svg -> docs/v9-system-diagram.png
#
# Preferred order (as specified for this deliverable):
#   1. rsvg-convert   2. inkscape --export-type=png   3. python3 -c 'import cairosvg'
# On this host ALL THREE were absent, so the fallback below is used.  The fallback
# is still a real raster of the same file (headless Chromium, same engine that
# renders it for the layout gate) - nothing is fabricated.  See REPORT.md.
#
# Usage: scripts/render_v9_diagram_png.sh [svg] [png]
set -e
SRC="${1:-docs/v9-system-diagram.svg}"
OUT="${2:-docs/v9-system-diagram.png}"
W=1900
H=1472

if command -v rsvg-convert >/dev/null 2>&1; then
  echo "renderer: rsvg-convert"
  rsvg-convert -w "$W" -h "$H" -o "$OUT" "$SRC"
elif command -v inkscape >/dev/null 2>&1; then
  echo "renderer: inkscape"
  inkscape "$SRC" --export-type=png --export-filename="$OUT" -w "$W" -h "$H"
elif python3 -c 'import cairosvg' >/dev/null 2>&1; then
  echo "renderer: cairosvg"
  python3 -c "import cairosvg,sys; cairosvg.svg2png(url=sys.argv[1], write_to=sys.argv[2], output_width=$W, output_height=$H)" "$SRC" "$OUT"
else
  CHROME="$(command -v chromium || command -v chromium-browser || command -v google-chrome || true)"
  if [ -z "$CHROME" ]; then
    echo "FATAL: none of rsvg-convert / inkscape / cairosvg / chromium available." >&2
    echo "No PNG produced. Do NOT fabricate one." >&2
    exit 1
  fi
  echo "renderer: $CHROME (fallback - the three preferred renderers are not installed)"
  "$CHROME" --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
    --force-device-scale-factor=1 --window-size="$W,$H" \
    --screenshot="$OUT" "file://$(pwd)/$SRC" 2>&1 | tail -1
fi

SIZE=$(wc -c < "$OUT")
echo "wrote $OUT ($SIZE bytes)"
if [ "$SIZE" -lt 10240 ]; then
  echo "FATAL: PNG is suspiciously small (<10 KB) - treat as a failed render." >&2
  exit 1
fi
command -v identify >/dev/null 2>&1 && identify "$OUT"
