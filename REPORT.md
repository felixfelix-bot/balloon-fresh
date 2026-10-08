# REPORT — docs/program-gap-analysis

**Deliverable:** `docs/analysis/PROGRAM-GAP-ANALYSIS.md`
**Branch:** `docs/program-gap-analysis`  **Base:** `github/main` @ `09e1b69`

## SHAs

- **Deliverable commit** (`docs/analysis/PROGRAM-GAP-ANALYSIS.md`): `398cc70862a8e13de5e6607a2f2a189de47c0e3f`
- Verified on all three remotes at the time of that push:
  - `git ls-remote github refs/heads/docs/program-gap-analysis` → `398cc70862a8e13de5e6607a2f2a189de47c0e3f`
  - `git ls-remote origin refs/heads/docs/program-gap-analysis` → `398cc70862a8e13de5e6607a2f2a189de47c0e3f`
  - `git ls-remote ngit   refs/heads/docs/program-gap-analysis` → `398cc70862a8e13de5e6607a2f2a189de47c0e3f`

> **Branch tip advances with this file.** REPORT.md is gitignored and force-added, so every edit to it
> is a new commit and moves the tip. The **doc commit** above is stable; the tip after the last report
> commit must be read with `git ls-remote <remote> refs/heads/docs/program-gap-analysis`.
> Pushed **github first, then ngit separately** (no `--atomic`).
> Base: `github/main` @ `09e1b69`.

## What was produced

- §1 plain-language inventory of the whole system + mermaid block diagram.
- §2 status ledger for 14 workstreams with evidence.
- §3a/§3b/§3c end-to-end gap analyses (pre-pressurisation board; RX/TX BOM + assembly plan;
  HIGH/LOW-power flight boards ± wings).
- §4 fifteen numbered decisions with options / recommendation / consequence / what they block.
- §5 consolidation ledger (16 unmerged design branches) + ADR-number collision map.

## Method

Read-only over every other branch (`git show`, `git diff`, `git ls-tree`). No merge. No push to main.
Prices/parts/specs taken only from the in-repo documents that cite URLs; unsourced ⇒ `TODO(unverified)`.
