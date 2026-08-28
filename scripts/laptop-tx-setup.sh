#!/usr/bin/env bash
# ============================================================================
# laptop-tx-setup.sh — one-command bootstrap for E80 range-test TX laptop
#
# Installs: python3 + git + make checks, pyserial, repo clone, board detect,
# and prints the exact per-stop make commands for the Funchal demo.
#
# Works on macOS (brew) and Linux (apt/dnf/pacman/pip).
# Idempotent: safe to re-run.  Does NOT flash firmware.
#
# Usage (curl|bash one-liner):
#   curl -fsSL https://raw.githubusercontent.com/felixfelix-bot/balloon-fresh/main/scripts/laptop-tx-setup.sh | bash
#
# Or after clone:
#   bash scripts/laptop-tx-setup.sh
# ============================================================================
set -euo pipefail

# ── Constants ────────────────────────────────────────────────────────────
REPO_URL="https://github.com/felixfelix-bot/balloon-fresh.git"
REPO_DIR="$HOME/repos/balloon-e80bench"
BRANCH="main"
TX_PROBE="148757200D2D1425"          # Board A — TX for this demo
BENCH_DIR="firmware/e80-stm32-bench"
DEMO_STOPS=("50m" "100m" "218m" "436m" "872m" "1744m")
STOP_LABELS=("50 m" "100 m" "218 m" "436 m" "872 m (Achada)" "1744 m (Monte)")

# ── Helpers ──────────────────────────────────────────────────────────────
banner() {
  echo ""
  echo "══════════════════════════════════════════════════════════════"
  echo "  $1"
  echo "══════════════════════════════════════════════════════════════"
}

info() { echo "  [INFO] $*"; }
warn() { echo "  [WARN] $*" >&2; }
fail() { echo "  [FAIL] $*" >&2; exit 1; }

detect_os() {
  if [[ "$(uname)" == "Darwin" ]]; then
    echo "macos"
  elif [[ -f /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    echo "${ID:-linux}"
  else
    echo "linux"
  fi
}

# ── 1. Preflight: python3 + git + make ──────────────────────────────────
banner "STEP 1/5 — Preflight: checking python3, git, make"

command -v python3 >/dev/null 2>&1 || fail "python3 not found. Install Python 3.8+ first."
info "python3: $(python3 --version 2>&1)"

command -v git >/dev/null 2>&1 || fail "git not found. Install git first."
info "git: $(git --version)"

command -v make >/dev/null 2>&1 || fail "make not found. Install build-essential / Xcode CLT first."
info "make: $(make --version 2>&1 | head -1)"

echo "  ✅ All core tools present."

# ── 2. Install pyserial ─────────────────────────────────────────────────
banner "STEP 2/5 — Installing pyserial (user-level)"

install_pyserial() {
  # Try user-level first, fall back to --break-system-packages on Debian 12+
  if python3 -c "import serial; print(serial.__version__)" 2>/dev/null; then
    info "pyserial already installed: $(python3 -c 'import serial; print(serial.__version__)')"
    return 0
  fi

  info "Installing pyserial via pip (user-level)..."
  if pip3 install --user pyserial 2>/dev/null; then
    info "pyserial installed (user-level)."
    return 0
  fi

  info "user-level failed, trying --break-system-packages (Debian 12+)..."
  if pip3 install --user --break-system-packages pyserial 2>/dev/null; then
    info "pyserial installed (--break-system-packages)."
    return 0
  fi

  # Last resort: pip3 without --user
  info "Falling back to pip3 install pyserial (system)..."
  if pip3 install pyserial 2>/dev/null; then
    info "pyserial installed (system)."
    return 0
  fi

  fail "Could not install pyserial. Try manually: pip3 install pyserial"
}

install_pyserial

# Verify
python3 -c "import serial; print('  pyserial version:', serial.__version__)" || \
  fail "pyserial import failed after install."

echo "  ✅ pyserial ready."

# ── 3. Clone or update the repo ──────────────────────────────────────────
banner "STEP 3/5 — Clone / update repo"

if [[ -e "$REPO_DIR/.git" ]]; then
  info "Repo already cloned at $REPO_DIR — pulling latest..."
  git -C "$REPO_DIR" fetch origin "$BRANCH" 2>/dev/null || warn "git fetch failed (offline? continuing with local copy)"
  git -C "$REPO_DIR" checkout "$BRANCH" 2>/dev/null || true
  git -C "$REPO_DIR" pull origin "$BRANCH" 2>/dev/null || warn "git pull failed (offline? continuing with local copy)"
else
  info "Cloning $REPO_URL → $REPO_DIR ..."
  mkdir -p "$(dirname "$REPO_DIR")"
  git clone --depth 50 "$REPO_URL" "$REPO_DIR" || \
    fail "git clone failed. Check network and repo URL: $REPO_URL"
  git -C "$REPO_DIR" checkout "$BRANCH" 2>/dev/null || true
fi

info "Repo HEAD: $(git -C "$REPO_DIR" log --oneline -1)"
echo "  ✅ Repo ready at $REPO_DIR."

# ── 4. Detect the E80 board ─────────────────────────────────────────────
banner "STEP 4/5 — Detect E80 board"

BENCH_FULL="$REPO_DIR/$BENCH_DIR"
DETECT_SCRIPT="$BENCH_FULL/tools/e80_detect.py"

if [[ ! -f "$DETECT_SCRIPT" ]]; then
  fail "e80_detect.py not found at $DETECT_SCRIPT. Repo may be incomplete."
fi

info "Running board detection (--role TX asserts Board A, probe $TX_PROBE)..."
echo ""
DETECT_OUT=""
DETECT_OUT="$( cd "$BENCH_FULL" && python3 tools/e80_detect.py --role TX 2>&1 )" || {
  warn "e80_detect.py exited non-zero — board may not be connected yet."
  warn "Plug in the E80 board via USB (both CH340 serial + Pico probe cables)."
  warn "Then re-run this script."
}
echo "$DETECT_OUT"
echo ""

# Extract the CH340 console port straight from e80_detect.py output.
# NEVER guess via udevadm probe-serial match: the probe serial (e.g. 1487…)
# shows up on the RP2040 CDC port (ttyACMx), but make range-tx talks to the
# CH340 console (ttyUSBx on Linux, cu.usbserial* on macOS).
# Text mode prints: "  port: /dev/ttyUSB0"
DETECTED_PORT="$(printf '%s\n' "$DETECT_OUT" | sed -nE 's/^[[:space:]]*port:[[:space:]]*(\/dev\/[^[:space:]]+).*$/\1/p' | head -1)"

if [[ -n "$DETECTED_PORT" ]]; then
  info "TX board console port: $DETECTED_PORT (probe $TX_PROBE)"
else
  warn "Could not auto-detect the TX board port."
  warn "Run manually after plugging in:  cd $BENCH_FULL && python3 tools/e80_detect.py --role TX"
  warn "Then note the PORT= value and add it to the make commands below."
fi

# ── 5. Print per-stop make commands ─────────────────────────────────────
banner "STEP 5/5 — Per-stop TX commands (Funchal demo)"

echo ""
echo "  All commands run from:  $BENCH_FULL"
echo "  TX probe serial:        $TX_PROBE (Board A)"
echo "  Firmware:               5fa7912 (DO NOT FLASH — no make flash)"
echo ""

# Build PORT arg if we have a detected port
PORT_ARG=""
if [[ -n "$DETECTED_PORT" ]]; then
  PORT_ARG="PORT=$DETECTED_PORT"
fi

echo "  ┌──────────────────────────────────────────────────────────────────────┐"
echo "  │  STOP     │  COMMAND                                              │"
echo "  ├──────────────────────────────────────────────────────────────────────┤"

for i in "${!DEMO_STOPS[@]}"; do
  dist="${DEMO_STOPS[$i]}"
  label="${STOP_LABELS[$i]}"
  printf "  │  %-8s │  make range-tx DIST=%-7s PROBE=%s %s\n" "$label" "$dist" "$TX_PROBE" "$PORT_ARG"
  printf "  │           │                                                        \n"
done

echo "  └──────────────────────────────────────────────────────────────────────┘"
echo ""
echo "  NOTES:"
echo "    • Ports swap on every USB replug — re-run e80_detect.py if unsure."
echo "    • --loop 1 only (default). Never --loop 0 in the field."
echo "    • After any board reset, verify PA: ID? must show pa=22."
echo "    • NTP sync before starting: timedatectl → 'System clock synchronized: yes'"
echo "    • T0 = next 5-min boundary (auto). RX must start BEFORE TX."
echo "    • TX sends N+2 packets (2 warmup discarded) — this is normal."
echo ""
echo "  QUICK START (copy-paste after plugging in board + NTP sync):"
echo ""
echo "    cd $BENCH_FULL"
echo "    python3 tools/e80_detect.py"
echo ""

for dist in "${DEMO_STOPS[@]}"; do
  if [[ -n "$PORT_ARG" ]]; then
    echo "    # ${dist}: make range-tx DIST=${dist} PROBE=$TX_PROBE $PORT_ARG"
  else
    echo "    # ${dist}: make range-tx DIST=${dist} PROBE=$TX_PROBE PORT=<from-detect>"
  fi
done

echo ""
echo "  DATA COMMIT (after each stop, from repo root $REPO_DIR):"
echo "    mkdir -p data/e80-bench/20260829-funchal-${dist}"
echo "    cp firmware/e80-stm32-bench/tx-log.csv data/e80-bench/20260829-funchal-${dist}/"
echo "    git add data/e80-bench/20260829-funchal-${dist}/ && \\"
echo "    git commit -m \"data(range): 20260829 funchal ${dist} stop logs\" && git push"
echo ""

banner "SETUP COMPLETE — ready for the field"
echo ""
echo "  Cheatsheet:  $REPO_DIR/docs/FRIDAY-DEMO-CHEATSHEET.md"
echo "  Handover:    $REPO_DIR/docs/FRIDAY-DEMO-HANDOVER-2026-08-29.md"
echo "  Signal:      balloon-hermes group for all coordination"
echo ""