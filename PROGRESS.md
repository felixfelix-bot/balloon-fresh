# PROGRESS

# PROGRESS — docs/program-gap-analysis

**Task:** Produce a blog-readable PROGRAM GAP ANALYSIS for the balloon project.
**Branch:** `docs/program-gap-analysis` (base `github/main` @ `09e1b69`)
**Worktree:** `/home/c03rad0r/worktrees/bf-gap`

## Milestones

- [x] Worktree created off `github/main`; `github`, `ngit`, `origin` remotes confirmed.
- [x] Read the ground-station design set from 16 unmerged `design/*` branches (read-only via `git show`/`git diff`).
- [x] Read ADR-071…084 decisions; `docs/analysis/plan-review-consultant.md`.
- [x] Read the 18-row `docs/BASE-STATION-BOARD-CHECKLIST.md` (+ totals €274.58 / €441.57 / 4 owned).
- [x] Read `docs/REGULATORY-AMATEUR-LICENCE.md` (433 + 2.4 GHz both licensed; cross-border OPEN).
- [x] Read pre-pressurisation protocol + pressure-test plan + `tools/balloon_pressure_test/`.
- [x] Measured branch consolidation state (16 unmerged design branches, 62 commits, 136 files).
- [x] Measured the ADR-number collision map (066/067/068×3/070 / 071–082 / 083 / 084).
- [x] **WROTE `docs/analysis/PROGRAM-GAP-ANALYSIS.md`** (§1–§5 + appendix).
- [ ] Commit + push github, then ngit; record SHAs in REPORT.md.

## Notes / honesty

- Kanban card `t_c561ea2d` (pre-pressurisation board, prio 8) **could not be located** in any readable
  kanban store (8,555 task JSONs + readable `kanban.db`s); `hermes kanban` refuses in a delegated
  subagent context. Recorded as `TODO(unverified)`; the gap is derived from repo documents.
- No `S_crack` value, no control/bias/telemetry-board schematic, and no assembly-plan doc exist
  anywhere — those are reported as gaps, not invented.
- Nothing merged; `main` untouched.

---

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


---

# PROGRESS t_588b1d1b (relay scaffolding)

- Sibling failover suite GREEN (19), not RED -> documented honestly in REPORT.md.
- Added relay_testkit.py + test_relay_testkit.py -> RED (ModuleNotFoundError, exit 2) then GREEN (13).
- Regression: sibling suite 19 passed; ADR-033 gift-wrap guard 4 passed.
- Commit f6e7681a on pr/relay-scaffold-testkit; pushed; PR base=pr/relay-failover-publisher.

---

# PROGRESS t_69c76243 (fake relay transport double)

- Deliverable: EXTENDED `firmware/e80-stm32-bench/tools/relay_testkit.py` (found the double already
  existed from t_588b1d1b; duplicated it would have created a 2nd source of truth) + new pins
  `tools/test_fake_relay_transport.py`.
- Matched signature: `async def send(url, event) -> list`; publisher awaits it under `wait_for`.
- Added split `HARD_ERROR_RAISE` (ConnectionRefusedError) / `HARD_ERROR_REJECT` (OK-false
  "blocked: ..."), keeping `HARD_ERROR`/`BLOCKED` aliases; TIMEOUT now awaits a never-set
  asyncio.Event (was sleep(3600)); `.attempts` + `.reset()`/`.clear()`; docstring guarantee+example;
  AST-scan no-network pin.
- Finding: `RelayFailoverPublisher._send_one` ignores the returned frame (refusal = raise
  `RelayRejected`), so the REJECT envelope is not honoured end-to-end. Did NOT edit
  relay_failover.py (other card's deliverable) — flagged in REPORT-t_69c76243.md.
- RED (8 failed/3 passed) -> GREEN 13; sibling relay_testkit 13; relay-failover suite 19; whole
  tools/ 885 passed / 1 skipped. No live network.

