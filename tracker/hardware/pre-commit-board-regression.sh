# ============================================================================
# BOARD REGRESSION HOOK
#
# The operator's question (2026-10-14): "would it make sense to put these tools
# in pytests that get triggered as pre-commit or pre-push hooks so that we can be
# sure that our work is always good quality? My intention is to make something
# like regression tests for circuit boards so that we can catch known errors if
# they are re-introduced. To what extent can this be done?"
#
# YES -- and this is the split:
#
#   FAST checks (pre-commit, ~5 s): the tools that need no CAD kernel and no
#     kicad-cli. They catch the campaign's LOUDEST real bugs by re-deriving from
#     source:
#       - wing-socket pads on the board        (16 pads were off-board)
#       - no placed part outside the outline   (an unplaceable part sat at (0,0))
#       - outline default matches ADR-068      (was silently stale at 103x103)
#       - strap pins carry no load             (boot-loop class)
#       - the fab chain's ORDER                (stale zone fill read as 0.000 mm)
#
#   SLOW checks (pre-push, ~30-60 s): need kicad-cli and/or the router.
#       - the router is invoked with --escalation off and the frozen floor
#       - the fab-coherence gate runs and reports a verdict
#
#   NOT COVERED, and no hook can cover it: whether a placement is GOOD, whether
#     the RF link closes, whether a part is the RIGHT part. Those need the
#     spatial review (Astra) and bench measurement. A regression test can only
#     pin a NUMBER a human once judged acceptable.
#
# INSTALL (from the repo root):
#   ln -sf ../../tracker/hardware/pre-commit-board-regression.sh \
#          .git/hooks/pre-commit
# ============================================================================

REPO="$(git rev-parse --show-toplevel)"
PYTEST_BIN="${BOARD_PYTEST:-$HOME/venvs/ho-test/bin/python}"
TESTS="$REPO/tracker/hardware/test_board_regression.py"

# only run when board-related files are touched
CHANGED="$(git diff --cached --name-only)"
if ! echo "$CHANGED" | grep -qE 'tracker/hardware/|firmware/.*pin_plan|docs/adr/0(6[89]|7[0-9])'; then
    exit 0
fi

if [ ! -x "$PYTEST_BIN" ]; then
    echo "board-regression: $PYTEST_BIN not found -- skipping (set BOARD_PYTEST)"
    exit 0
fi
if [ ! -f "$TESTS" ]; then
    echo "board-regression: $TESTS not found -- skipping"
    exit 0
fi

echo "board-regression: running FAST board checks..."
if ! "$PYTEST_BIN" -m pytest "$TESTS" -q -m fast --no-header 2>&1 | tail -12; then
    echo
    echo "board-regression: FAILED -- a known board error may have been re-introduced."
    echo "  see tracker/hardware/test_board_regression.py for what each check guards"
    echo "  bypass (deliberate only): git commit --no-verify"
    exit 1
fi
echo "board-regression: OK"
