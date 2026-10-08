# REPORT — docs/program-gap-analysis

**Deliverable:** `docs/analysis/PROGRAM-GAP-ANALYSIS.md`
**Branch:** `docs/program-gap-analysis`  **Base:** `github/main` @ `09e1b69`

## SHAs (git ls-remote on BOTH remotes)

- HEAD (local): `398cc70862a8e13de5e6607a2f2a189de47c0e3f`
- github `docs/program-gap-analysis` (`git ls-remote github`): `398cc70862a8e13de5e6607a2f2a189de47c0e3f`
- origin `docs/program-gap-analysis` (`git ls-remote origin`): `398cc70862a8e13de5e6607a2f2a189de47c0e3f`
- ngit   `docs/program-gap-analysis` (`git ls-remote ngit`):   `398cc70862a8e13de5e6607a2f2a189de47c0e3f`

All three match local HEAD. Pushed **github first, then ngit separately** (no `--atomic`).
Commit: `398cc70` on top of `github/main` `09e1b69`.

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
