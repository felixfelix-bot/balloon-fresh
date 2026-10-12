#!/usr/bin/env bash
# agentee_gate.sh -- ONE command for the agentee second-checker pass on a board.
#
# WHY: this chain was hand-run ~4 times this session (clean sandbox, import,
# silk, tie, fill, drc --json, count severity=="error"). Each repetition
# re-derived the same flags and re-hit the same two traps. Scripted once.
#
# The two traps, both measured 2026-10-12:
#  1. import COLLIDES on a reused sandbox ("footprints/X.fp.toml exists, pass
#     force to overwrite") -- so the sandbox is rebuilt per board, never reused.
#  2. agentee's `drc` JSON has BOTH `diagnostics` (advisory) and errors. Only
#     severity=="error" blocks fab; reporting the total is misleading.
#
# AGENTEE IS A GATE, NOT THE SOURCE OF TRUTH.
#  - no KiCad write-back: every fix agentee applies lives in its TOML only and
#    must be re-applied to the KiCad board by hand
#  - no waiver mechanism: by-design edge-card geometry flags forever
#    (docs/HUB-V9-DRC-EXCLUSIONS.md, upstream draft PR v0l/agentee#15)
#
# USAGE:
#   tracker/hardware/agentee_gate.sh <board.kicad_pcb> [--sandbox DIR] [--json OUT]
set -euo pipefail

BOARD="${1:?usage: agentee_gate.sh <board.kicad_pcb> [--sandbox DIR]}"
shift || true
SANDBOX="${SANDBOX:-/tmp/agentee-$(basename "$BOARD" .kicad_pcb)}"
JSONOUT="${JSONOUT:-/tmp/agentee_drc_$(basename "$BOARD" .kicad_pcb).json}"
AGENTEE="${AGENTEE:-$HOME/.local/bin/agentee}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sandbox) SANDBOX="$2"; shift 2;;
    --json) JSONOUT="$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done

[[ -x "$AGENTEE" ]] || { echo "agentee not installed: $AGENTEE (curl -fsSL https://agentee.sh/install.sh | sh)" >&2; exit 3; }

echo "=== agentee_gate: $(basename "$BOARD")"
echo "    sandbox: $SANDBOX (rebuilt -- reuse collides on footprints/*.fp.toml)"

# 1. fresh sandbox every run (trap 1: never reuse)
rm -rf "$SANDBOX"; mkdir -p "$SANDBOX"
cp "$BOARD" "$SANDBOX/board.kicad_pcb"
cd "$SANDBOX"

# 2. import
"$AGENTEE" import board board.kicad_pcb 2>&1 | tail -2

# 3. deterministic cleanups (each is idempotent; --help if the CLI drifts)
for step in silk tie fill; do
  out=$("$AGENTEE" "$step" board 2>&1 | tail -2 || true)
  echo "  $step: ${out:-<no output>}"
done

# 4. drc -- the gate. Only severity=="error" blocks.
"$AGENTEE" drc board --json > "$JSONOUT" 2>/dev/null || true
python3 - "$JSONOUT" <<'PYEOF'
import json, sys
from collections import Counter
p = sys.argv[1]
try:
    d = json.load(open(p))
except Exception as e:
    print(f"  !! could not read drc json {p}: {e}")
    sys.exit(2)
diags = d.get("diagnostics", [])
errs = [x for x in diags if x.get("severity") == "error"]
print(f"  agentee drc: {len(diags)} diagnostics, {len(errs)} ERRORS")
rc = Counter(x.get("rule", "?") for x in errs)
for rule, n in rc.most_common(12):
    print(f"    {n:3d}  {rule}")
if not errs:
    print("  -> agentee gate PASS (0 errors)")
    sys.exit(0)
print("  -> agentee gate FAIL")
print("  NOTE: by-design families (pad-off-board / copper_edge_clearance on")
print("        J_W*/ANT* / slot Edge.Cuts) are NOT agentee-waivable yet --")
print("        cross-check docs/HUB-V9-DRC-EXCLUSIONS.md before treating them")
print("        as new defects, and NEVER re-apply them to the KiCad board on")
print("        the strength of this report alone (no write-back).")
sys.exit(1)
PYEOF
RC=$?
echo "=== agentee_gate done rc=$RC"
exit $RC