# PROGRESS — JLCPCB price-tier record + 102 mm hub outline decision

Branch: `docs/jlcpcb-pricing-and-outline-decision` (off `github/main` @ `716974a`)
Worktree: `/home/c03rad0r/worktrees/bf-jlcdoc`
Gitignored (`.gitignore:67`) — `git add -f` on THIS branch only; never to `main`.

## Cluster 1 — recon + evidence inventory  [DONE]
- Fetched `github`; tip `716974a` confirmed.
- Inventoried `~/quote-scratch/`: 36 per-config JSON + SUMMARY.json (+.txt), `batch*.json/log`,
  `measure*.py`, `probe1..15.py`, `probe10_report.json`. Confirmed the timed-out worker's run.
- Parsed every JSON: built the values/dims/thickness/finish/price table.
- Found the competing remote branch `analysis/jlcpcb-size-tier-quote-salvage` (docs only, no raw
  JSON committed, no ADR). Noted as sibling, not authority.

## Cluster 2 — residual closure  [DONE]
- Wrote `~/quote-scratch/closeout.py`; ran 4 fresh isolated measurements under python3.13+playwright.
- `res_103_4L_06`: 0.6 mm DISABLED at 4 layers → residual closed as "configuration not offered".
- `res_103_4L_16` $31.60 (4th repeat); `res_102_4L_16` $8.00 (decision size reconfirmed);
  `res_102_4L_04_ENIG`: 0.4 mm DISABLED at 4L; fallback 102/4L/1.6/ENIG $25.80 (still cheap class).

## Cluster 3 — salvage raw evidence into repo  [DONE]
- `docs/analysis/jlcpcb-quote-2026-10/` = 41 JSON + 40 TXT + logs + scripts + README (119 files, 604K).

## Cluster 4 — deliverables  [DONE]
- `docs/analysis/jlcpcb-pricing-and-size-tier.md` (findings, method, re-verification, confound,
  invalid configs, residual closure, duty dependency, follow-ups).
- `docs/adr/063-hub-outline-trim.md` (number verified vs `adr_next_number.py` && EVERY ref;
  "For future sessions" subsection; SSOT entry recorded as OWED).
- `docs/adr/INDEX.md` regenerated (74 numbers, no collisions, 063 present).

## Cluster 5 — verify + push  [IN PROGRESS]
- `tests/test_adr_numbering.py`: 3 passed.
- Full suite: **549 passed, 37 skipped, 1 failed** — the failure is `test_board_lock.py::test_lock_status`
  (10 s subprocess timeout under load). Re-run of that file: **2 passed, 6 skipped** → contention, not
  a regression.
- Deliverables committed as `632c6f173d6de8f93083346402b97578fd3608c7`.
- Next: PROGRESS/REPORT `git add -f`, commit, push `github` FIRST then `ngit` separately, verify both.
- `.gitignore:67/68` confirm PROGRESS.md/REPORT.md are ignored → forced in on THIS branch only.
