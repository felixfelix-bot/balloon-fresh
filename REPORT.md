# REPORT — adr/variant-b-design-basis

## Deliverable
`docs/adr/062-variant-b-design-basis.md` — the Variant B **design basis** (ADR-first; no board
laid out or built, and no Variant A artefact — board, schematic, netlist, placement — modified).

## Branch / commits
- Branch: `adr/variant-b-design-basis` (from `github/main` tip `8032cb4`). **Never main.**
- ADR + regenerated index commit: `42120b2b019dc18de59dde1a2cd08a72e3a5faa9`

## Files created / modified
- **NEW** `docs/adr/062-variant-b-design-basis.md`
- **MOD** `docs/adr/INDEX.md` (regenerated with `scripts/gen_adr_index.py` — one new row,
  72→73 counts, next-free 062→063)
- **NEW (gitignored, force-added on this branch only)** `PROGRESS.md`, `REPORT.md`
  — `.gitignore:67/68` ignore them by repo convention; the task required them on this branch,
  so they are committed here with `git add -f` and are **not** on main.

## Numbering
- `scripts/adr_next_number.py` → **62** (exit 0); `--number 62` → exit 0 (free).
- `git log --all --name-only --pretty=format: | grep -c 'docs/adr/062'` → **0**. Free on every ref.
- `python3 -m pytest tests/test_adr_numbering.py -q` → **3 passed**.

## Headline numbers (all arithmetic printed in the ADR)
- B total mass **≈ 17.2 g** (own board, 0.47 F store) → **margin ≈ 2.8 g**;
  ≈ 18.2 g with the Accepted 2 × AVX bank → margin ≈ 1.8 g.
- Pessimistic case: **FAILS** (cells-alone 26.2 g; S3+cells 28.7 g; all-three 30.0 g).
- B average draw **≈ 0.203 W** (0.522 × A's 0.388 W); **peak ≈ 1.28 W** (A: 6.15 W).
- Array: factor **0.186530** (horizontal, ADR-055 D1/D2) — **NOT** 0.305107 (B has no wings) →
  B minimum **55.4 cm²** (built 61.2 cm²), vs A's 106.1 cm².
- Outline: **B's own ≈ 61 cm² (~78 × 78 mm)**; on A's 103 × 103 mm plate B fails (21.06/25.58 g).
- Verdict: **B is a SEPARATE BOARD.** Thickness target **0.4 mm** (−2.60 g).

## Push verification
All three SHAs equal — **`e2ee2c43d66b98bcf5f7614a176245fe48d026b5`** (local HEAD = github = ngit):
```
local:  e2ee2c43d66b98bcf5f7614a176245fe48d026b5
github: e2ee2c43d66b98bcf5f7614a176245fe48d026b5   (felixfelix-bot/balloon-fresh)
ngit:   e2ee2c43d66b98bcf5f7614a176245fe48d026b5   (nostr://...relay.ngit.dev/balloon-fresh)
```
Pushed to `github` first, then `ngit` separately. One ngit relay (`relay.damus.io`,
`nos.lol`) failed to publish a state event; the ngit push itself succeeded and the
branch SHA verifies equal via `git ls-remote ngit`.

## Blockers / caveats
- `docs/analysis/hub-thickness-deflection.md` (concurrent worker) **absent** from all refs —
  not waited for, per the task.
- All soft numbers are named in the ADR as ESTIMATE / `TODO(unverified)`; nothing invented.
  The < 20 g wall is recorded as the operator's design target, **not** a legal threshold.
