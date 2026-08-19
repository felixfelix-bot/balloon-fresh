#!/usr/bin/env bash
# fw_harm_readiness_check.sh — Pre-integration readiness check for firmware harmonization.
#
# Verifies ALL Wave 1-3 tasks are complete and ready for integration testing.
# Checks:
#   1. All expected git commits exist on correct branches
#   2. All builds pass (E80 firmware, C3 firmware, host tests)
#   3. Outputs a JSON-like summary
#
# If READY=true, prints "INTEGRATION READY — all code tasks complete.
# Flash boards + run fw_harm_measurement.py"
#
# Usage:
#   ./tools/fw_harm_readiness_check.sh
#   ./tools/fw_harm_readiness_check.sh --skip-builds   # check commits only
set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
E80_REPO="$HOME/repos/balloon-e80bench"
C3_REPO="$HOME/repos/balloon-fresh"
HOST_REPO="$HOME/repos/balloon-fresh"
C3_SUBDIR="mesh-stack/flrc-bench-espidf"

E80_BRANCH="feat/persist-tx-seq"
C3_BRANCH="feat/c3-harmonization"

SKIP_BUILDS=false
if [[ "${1:-}" == "--skip-builds" ]]; then
  SKIP_BUILDS=true
fi

# ── Expected tasks (grep patterns for git log) ──────────────────────────────
# E80 tasks checked in E80 repo on feat/persist-tx-seq
declare -A E80_TASKS=(
  ["E80-1"]="FW_HASH.*boot banner|fw=.*FW_HASH|add fw=FW_HASH"
  ["E80-2"]="baud.*2.000.000|UART baud from 115200 to 2.000.000|bump.*baud.*2.000.000"
  ["E80-3"]="enlarge.*tx_buf|tx_buf from 96 to 160"
  ["E80-4"]="cr field to radio_bench|coding rate.*cr.*radio_bench"
  ["E80-5"]="persist.*tx_seq|tx_seq.*non-reset|persist tx_seq across START"
  ["E80-6"]="per-packet.*23-field|23-field.*PKT.*output|per-packet output with 23-field"
  ["E80-7"]="CRC.*failed.*RSSI|CRC-failed.*packet|RSSI on CRC-failed|log CRC-failed packets"
  ["E80-8"]="CONFIG_START.*marker|CONFIG_START transition"
)

# HOST-2 (baud 2M in host tools) is checked in E80 repo (it's the E80 host tool)
declare -A E80_HOST_TASKS=(
  ["HOST-2"]="baud to 2.000.000|host tool baud to 2 Mbps|baud.*2.*Mbps.*host"
)

# C3 tasks checked in C3 repo on feat/c3-harmonization
declare -A C3_TASKS=(
  ["C3-1"]="FW_HASH.*boot banner|FW_GIT_SHA.*boot|FW_HASH.*C3"
  ["C3-2"]="uint32.*sequence|widen.*sequence.*uint32|sequence counter to uint32"
  ["C3-3"]="23-field.*common format|PKT line to 23-field|23-field common format"
  ["C3-4"]="CRC.*failed.*packet|CRC-failed packets|log CRC-failed packets with RSSI"
)

# Host tasks checked in C3 repo on feat/c3-harmonization (same repo, tools/)
declare -A HOST_TASKS=(
  ["HOST-1"]="firmware.hash.gate|firmware-hash gate|FW_HASH.*gate"
  ["HOST-3"]="session_id.*injection|session.id injection"
  ["HOST-4"]="23-field.*PKT.*format|CSV.*23-field|update.*capture.*23-field|harmonized 23-field PKT format"
)

# ── Accumulators ────────────────────────────────────────────────────────────
MISSING_TASKS=()
BLOCKERS=()
BUILD_E80="SKIP"
BUILD_C3="SKIP"
BUILD_HOST="SKIP"
FLASH_SIZE_E80=0
TESTS_HOST_PASSED=0
TESTS_HOST_TOTAL=0

# ── Helper: check a task in a git log ────────────────────────────────────────
check_task() {
  local task_id="$1"
  local pattern="$2"
  local log="$3"
  local repo_label="$4"

  if echo "$log" | grep -qiE "$pattern"; then
    echo "  $task_id: DONE"
    return 0
  else
    echo "  $task_id: MISSING (pattern: '$pattern' in $repo_label)"
    MISSING_TASKS+=("$task_id")
    return 1
  fi
}

# ── 1. Check git commits ────────────────────────────────────────────────────
echo "=== Git Commit Verification ==="
echo ""

# --- E80 repo ---
echo "--- E80 Repo ($E80_REPO, $E80_BRANCH) ---"
cd "$E80_REPO" 2>/dev/null || {
  echo "  ERROR: E80 repo not found at $E80_REPO"
  BLOCKERS+=("E80_REPO_NOT_FOUND")
  MISSING_TASKS+=("E80-1" "E80-2" "E80-3" "E80-4" "E80-5" "E80-6" "E80-7" "E80-8" "HOST-2")
  E80_LOG=""
}
if [[ -d "$E80_REPO" ]]; then
  git fetch github "$E80_BRANCH" 2>/dev/null || true
  E80_LOG=$(git log --oneline "github/$E80_BRANCH" 2>/dev/null || git log --oneline "$E80_BRANCH" 2>/dev/null || echo "")
  for task in E80-1 E80-2 E80-3 E80-4 E80-5 E80-6 E80-7 E80-8; do
    check_task "$task" "${E80_TASKS[$task]}" "$E80_LOG" "E80/$E80_BRANCH" || true
  done
  # HOST-2 is in E80 repo (host tool baud change)
  check_task "HOST-2" "${E80_HOST_TASKS[HOST-2]}" "$E80_LOG" "E80/$E80_BRANCH" || true
fi
echo ""

# --- C3 repo ---
echo "--- C3 Repo ($C3_REPO, $C3_BRANCH) ---"
cd "$C3_REPO" 2>/dev/null || {
  echo "  ERROR: C3 repo not found at $C3_REPO"
  BLOCKERS+=("C3_REPO_NOT_FOUND")
  MISSING_TASKS+=("C3-1" "C3-2" "C3-3" "C3-4")
  C3_LOG=""
}
if [[ -d "$C3_REPO" ]]; then
  git fetch github "$C3_BRANCH" 2>/dev/null || true
  C3_LOG=$(git log --oneline "github/$C3_BRANCH" 2>/dev/null || git log --oneline "$C3_BRANCH" 2>/dev/null || echo "")
  for task in C3-1 C3-2 C3-3 C3-4; do
    check_task "$task" "${C3_TASKS[$task]}" "$C3_LOG" "C3/$C3_BRANCH" || true
  done
  echo ""

  # --- Host tools (same repo, same branch) ---
  echo "--- Host Tools ($HOST_REPO, $C3_BRANCH) ---"
  HOST_LOG="$C3_LOG"
  for task in HOST-1 HOST-3 HOST-4; do
    check_task "$task" "${HOST_TASKS[$task]}" "$HOST_LOG" "Host/$C3_BRANCH" || true
  done
fi
echo ""

# ── 2. Check builds ─────────────────────────────────────────────────────────
if [[ "$SKIP_BUILDS" == "true" ]]; then
  echo "=== Builds (SKIPPED via --skip-builds) ==="
else
  echo "=== Build Verification ==="
  echo ""

  # --- E80 build ---
  echo "--- E80 Build ---"
  cd "$E80_REPO" 2>/dev/null || {
    echo "  ERROR: Cannot build E80 — repo not found"
    BUILD_E80="FAIL"
    BLOCKERS+=("E80_BUILD_REPO_MISSING")
  }
  if [[ -d "$E80_REPO" ]]; then
    E80_BUILD_OUT=$(make firmware 2>&1 || true)
    E80_BUILD_TAIL=$(echo "$E80_BUILD_OUT" | tail -5)
    echo "  Last 5 lines:"
    echo "$E80_BUILD_TAIL" | sed 's/^/    /'

    # Check for successful build
    if echo "$E80_BUILD_OUT" | grep -qiE "error|Error|failed|FAILED"; then
      BUILD_E80="FAIL"
      BLOCKERS+=("E80_BUILD_FAILED")
      echo "  Status: FAIL (errors in build output)"
    else
      # Extract flash size from arm-none-eabi-size output
      # Format: text data bss dec hex filename
      FLASH_SIZE_E80=$(echo "$E80_BUILD_OUT" | grep -oE '[0-9]+\s+[0-9]+\s+[0-9]+\s+[0-9]+\s+[0-9a-fA-F]+' | head -1 | awk '{print $1+$2}')
      if [[ -z "$FLASH_SIZE_E80" ]]; then
        # Try alternative: look for .bin size
        BIN_PATH="$E80_REPO/firmware/e80-stm32-bench/build-fw/e80_bench.bin"
        if [[ -f "$BIN_PATH" ]]; then
          FLASH_SIZE_E80=$(stat -c%s "$BIN_PATH" 2>/dev/null || echo "0")
        else
          FLASH_SIZE_E80=0
        fi
      fi

      if [[ "$FLASH_SIZE_E80" -gt 0 ]]; then
        if [[ "$FLASH_SIZE_E80" -lt 35000 ]]; then
          BUILD_E80="PASS"
          echo "  Status: PASS (flash: ${FLASH_SIZE_E80} bytes < 35K)"
        else
          BUILD_E80="FAIL"
          BLOCKERS+=("E80_FLASH_TOO_LARGE")
          echo "  Status: FAIL (flash: ${FLASH_SIZE_E80} bytes >= 35K)"
        fi
      else
        BUILD_E80="PASS"  # Build succeeded but couldn't extract size
        echo "  Status: PASS (build OK, flash size unknown)"
      fi
    fi
  fi
  echo ""

  # --- C3 build ---
  echo "--- C3 Build ---"
  if [[ -d "$C3_REPO/$C3_SUBDIR" ]]; then
    C3_BUILD_OUT=$(bash -c "source ~/esp/esp-idf/export.sh 2>/dev/null; cd '$C3_REPO/$C3_SUBDIR' && idf.py build 2>&1" || true)
    C3_BUILD_TAIL=$(echo "$C3_BUILD_OUT" | tail -5)
    echo "  Last 5 lines:"
    echo "$C3_BUILD_TAIL" | sed 's/^/    /'

    if echo "$C3_BUILD_OUT" | grep -qi "Project build complete"; then
      BUILD_C3="PASS"
      echo "  Status: PASS"
    else
      BUILD_C3="FAIL"
      BLOCKERS+=("C3_BUILD_FAILED")
      echo "  Status: FAIL (no 'Project build complete' in output)"
    fi
  else
    BUILD_C3="FAIL"
    BLOCKERS+=("C3_SUBDIR_NOT_FOUND")
    echo "  ERROR: C3 build dir not found at $C3_REPO/$C3_SUBDIR"
  fi
  echo ""

  # --- Host tests ---
  echo "--- Host Tests ---"
  cd "$C3_REPO" 2>/dev/null || {
    echo "  ERROR: Cannot run host tests — repo not found"
    BUILD_HOST="FAIL"
    BLOCKERS+=("HOST_TESTS_REPO_MISSING")
  }
  if [[ -d "$C3_REPO" ]]; then
    HOST_TEST_OUT=$(python -m pytest tests/ -v 2>&1 || true)
    HOST_TEST_TAIL=$(echo "$HOST_TEST_OUT" | tail -10)
    echo "  Last 10 lines:"
    echo "$HOST_TEST_TAIL" | sed 's/^/    /'

    # Parse passed/total from pytest summary line
    # e.g. "===== 30 passed in 5.2s =====" or "===== 28 passed, 2 failed in 5.2s ====="
    TESTS_HOST_TOTAL=$(echo "$HOST_TEST_OUT" | grep -oE '[0-9]+ (passed|failed)' | grep -oE '[0-9]+' | paste -sd+ | bc 2>/dev/null || echo "0")
    TESTS_HOST_PASSED=$(echo "$HOST_TEST_OUT" | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+' || echo "0")

    # Check for "failed" in summary
    if echo "$HOST_TEST_OUT" | grep -qE "[0-9]+ failed" || echo "$HOST_TEST_OUT" | grep -qiE "error"; then
      BUILD_HOST="FAIL"
      BLOCKERS+=("HOST_TESTS_FAILED")
      echo "  Status: FAIL (${TESTS_HOST_PASSED:-0}/${TESTS_HOST_TOTAL:-0} tests passed)"
    elif echo "$HOST_TEST_OUT" | grep -qE "[0-9]+ passed"; then
      BUILD_HOST="PASS"
      echo "  Status: PASS (${TESTS_HOST_PASSED}/${TESTS_HOST_TOTAL} tests passed)"
    else
      BUILD_HOST="FAIL"
      BLOCKERS+=("HOST_TESTS_NO_RESULTS")
      echo "  Status: FAIL (no test results found)"
    fi
  fi
  echo ""
fi

# ── 3. Summary ──────────────────────────────────────────────────────────────
echo "=== Summary ==="
echo ""

# Deduplicate missing tasks
if [[ ${#MISSING_TASKS[@]} -gt 0 ]]; then
  # Deduplicate while preserving order
  MISSING_DEDUPED=()
  for t in "${MISSING_TASKS[@]}"; do
    skip=false
    for s in "${MISSING_DEDUPED[@]:-()}"; do
      if [[ "$s" == "$t" ]]; then
        skip=true
        break
      fi
    done
    if [[ "$skip" == "false" ]]; then
      MISSING_DEDUPED+=("$t")
    fi
  done
  MISSING_STR=$(IFS=,; echo "${MISSING_DEDUPED[*]}")
else
  MISSING_STR=""
fi

# Determine readiness
READY=true
if [[ -n "$MISSING_STR" ]]; then
  READY=false
fi
if [[ "$SKIP_BUILDS" == "false" ]]; then
  if [[ "$BUILD_E80" != "PASS" ]]; then READY=false; fi
  if [[ "$BUILD_C3" != "PASS" ]]; then READY=false; fi
  if [[ "$BUILD_HOST" != "PASS" ]]; then READY=false; fi
fi

# Build status string
BUILD_STATUS="E80:$BUILD_E80,C3:$BUILD_C3,HOST:$BUILD_HOST"

# Blockers string
BLOCKERS_STR=""
if [[ ${#BLOCKERS[@]} -gt 0 ]]; then
  BLOCKERS_STR=$(IFS=,; echo "${BLOCKERS[*]}")
fi

# Output JSON-like summary
echo "READY=$READY"
echo "MISSING_TASKS=$MISSING_STR"
echo "BUILD_STATUS=$BUILD_STATUS"
echo "FLASH_SIZE_E80=$FLASH_SIZE_E80"
echo "TESTS_HOST=${TESTS_HOST_PASSED:-0}/${TESTS_HOST_TOTAL:-0}"
echo "BLOCKERS=$BLOCKERS_STR"
echo ""

if [[ "$READY" == "true" ]]; then
  echo "INTEGRATION READY — all code tasks complete. Flash boards + run fw_harm_measurement.py"
  exit 0
else
  echo "NOT READY — see issues above."
  exit 1
fi