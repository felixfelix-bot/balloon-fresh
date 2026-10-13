#!/usr/bin/env bash
# Report work that is NOT on the default branch and has NO open PR.
#
# WHY THIS EXISTS
# ---------------
# balloon-fresh's GitHub default branch is `master`, but that branch froze on
# 2026-08-05 — every push, every PR base and every merge for the last two months
# went to `main` instead. Nothing consolidates the two, so:
#
#   * GitHub's default branch checkout showed month-old (often pre-fork) code;
#   * `.github/workflows/test.yml` triggered on `master` ONLY, so the Python test
#     suite never ran on any push or PR in that window — `ci: success` on those
#     PRs meant "did not run", not "passed";
#   * branches whose work was never merged (or which were merged to a base that
#     is not the default branch) were invisible in the repo UI, because the UI
#     lists "N commits behind <default>".
#
# This script is the alarm for that class. Run it before claiming work is landed.
#
# USAGE
#   scripts/git/check-main-consolidation.sh [repo-path] [pr-base-branch]
# Exit 0 always (it is a report, not a gate); prints nothing when clean.

set -uo pipefail
trap 'exit 0' EXIT

REPO="${1:-$(git rev-parse --show-toplevel 2>/dev/null)}"
PR_BASE="${2:-main}"

[ -d "$REPO/.git" ] || [ -f "$REPO/.git" ] || { echo "not a git repo: $REPO"; exit 0; }
cd "$REPO" || exit 0

git fetch --all --prune -q 2>/dev/null || true

REMOTE_BASE="origin/$PR_BASE"
git rev-parse --verify -q "$REMOTE_BASE" >/dev/null 2>&1 || {
    echo "no $REMOTE_BASE — cannot judge consolidation"; exit 0; }

# The branch GitHub actually considers default. If it differs from PR_BASE, that
# divergence is itself the bug: say so once, loudly, and stop.
GH_DEFAULT=$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name 2>/dev/null || echo "")
if [ -n "$GH_DEFAULT" ] && [ "$GH_DEFAULT" != "$PR_BASE" ]; then
    behind=$(git rev-list --count "origin/$GH_DEFAULT..$REMOTE_BASE" 2>/dev/null || echo "?")
    echo "CONSOLIDATION DESYNC: GitHub default branch is '$GH_DEFAULT' but PRs merge to '$PR_BASE'"
    echo "  '$PR_BASE' is $behind commits ahead of '$GH_DEFAULT' — a default checkout shows stale code."
    echo "  Fix by fast-forwarding '$GH_DEFAULT' (it is an ancestor) or renaming the default branch."
fi

# Open PR heads, so we only report branches that have no PR to land them.
PR_HEADS=$(gh pr list --state open --limit 400 --json headRefName -q '.[].headRefName' 2>/dev/null || true)

# Branches that GitHub itself says have an open PR for this head.
count=0
while read -r ref; do
    [ -n "$ref" ] || continue
    name="${ref#refs/heads/}"
    # skip the base branches themselves
    case "$name" in
        "$PR_BASE"|master|main|archive/*|maintenance|dependabot/*|copilot/*|ci/*|release/*|hotfix/*) continue ;;
    esac

    ahead=$(git rev-list --count "$REMOTE_BASE..$ref" 2>/dev/null || echo 0)
    [ "${ahead:-0}" -gt 0 ] || continue

    # has an open GitHub PR? (exact head match)
    if printf '%s\n' "$PR_HEADS" | grep -qxF "$name"; then continue; fi

    # merged via a merge commit? (tip reachable from base)
    if git merge-base --is-ancestor "$ref" "$REMOTE_BASE" 2>/dev/null; then continue; fi

    # find a closed/merged PR for this head, to distinguish "merged elsewhere"
    pr=$(gh pr list --state all --limit 400 --head "$name" \
         --json number,baseRefName,state \
         -q '.[0] | "PR#\(.number) \(.state) base=\(.baseRefName)"' 2>/dev/null || true)

    printf '%5s unmerged  %-58s %s\n' "$ahead" "$name" "${pr:-no PR ever opened}"
    count=$((count + 1))
done < <(git for-each-ref --format='%(refname)' refs/remotes/origin refs/heads 2>/dev/null | grep -v 'refs/remotes/origin/HEAD')

[ "$count" -eq 0 ] || {
    echo
    echo "$count branch(es) carry commits not on $PR_BASE and have no open PR to land them."
    echo "Consolidate (merge) or delete them — an unmerged branch with no PR is lost work (D-128)."
}
exit 0
