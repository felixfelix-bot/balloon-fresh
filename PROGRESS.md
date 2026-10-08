# PROGRESS — design/433-lna-and-licence

Task: find a 433 MHz-specific LNA with a PUBLISHED NF to replace the disputed wideband
TQP3M9037; verify the German amateur power + airborne rules; source the Wilkinson combiner for a
2-bay Yagi upgrade; decide ONE LNA; resolve ADR-079; update the shopping list + base-station
checklist.

Worktree: `/home/c03rad0r/worktrees/bf-433lna` (branch `design/433-lna-and-licence`, base
`github/main` @ `09e1b69`).

## Cluster 1 — main analysis document + repro model  [DONE]
- `docs/analysis/433-lna-substitution-and-amateur-licence.md` — the deliverable.
- `docs/analysis/433_lna_licence_model.py` — stdlib-only, runs clean (`exit 0`), prints every
  table quoted in the doc.
- Key results: TQP3M9037 vendor LF edge **0.7 GHz** (3 Wayback snapshots) → **excludes 433.92 MHz**
  → ADR-079's D5 defect closes AGAINST the record. Recommended LNA = **SSB Electronic LNA ISM 433**
  (€257.00, NF 0.7 dB) = **+9.73 dB T_sys = €26.41/needed dB**.

## Cluster 2 — ADR-079 resolution + new ADR-085  [IN PROGRESS]
- `docs/adr/085-433-mhz-specific-masthead-lna.md` (Proposed) — adopts the SSB LNA and **supersedes ADR-079**.
- `docs/adr/079-…` carried from `design/adr-set-groundstation` and status flipped to **SUPERSEDED**.
- ADR number check: numbers 066–084 are claimed across `github/*`; **085 verified free** by listing
  `docs/adr/0[0-9][0-9]` on **every** `github/*` head (the allocator `scripts/adr_next_number.py` is
  branch-blind).

## Cluster 3 — artefact updates  [IN PROGRESS]
- `docs/BASE-STATION-BOARD-CHECKLIST.md` carried from `design/level-control-architecture` and updated
  (LNA row, splitter row, licence-compliance rows, totals recomputed).
- `docs/analysis/rf-shopping-list-and-duplex-architecture.md` carried from `design/rf-shopping-list`
  and updated (owned-LNA row, LNA-purchase rows, licence note).
- Both carried files are annotated in-place that they were taken onto this branch from their design
  branch on 2026-10-08 and patched here.

## Notes
- `PROGRESS.md` and `REPORT.md` are gitignored in balloon-fresh; staged with `git add -f` **on this
  branch only**.
- `AGENTS.md` / `.hermes/AGENTS.md` NOT touched.
- No internet-facing search engine usable (captcha after the first queries) — all sourcing done by
  direct vendor fetch with a browser User-Agent + `--compressed`, plus Wayback (`id_` raw fetch) for
  Qorvo and Kuhne.
- Blocked vendors recorded honestly: **Qorvo live product page HTTP 429** (solved via Wayback);
  **Kuhne Electronic domains parked / TLS-broken** (2007 archived catalogue only, price
  `TODO(unverified)`); **RF Bay Cloudflare challenge** (no figure taken); **ssb-electronic.de** empty
  to curl (all SSB figures read from the WiMo listings instead).
