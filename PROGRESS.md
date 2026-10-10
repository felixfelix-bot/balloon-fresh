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

# PROGRESS — fix/pcb-3d-render-pipeline (appended 2026-10-10)

- [x] Worktree `~/worktrees/bf-render` on `fix/pcb-3d-render-pipeline` off `origin/main`.
- [x] Diagnose: `kicad-packages3d` IS installed (4.6 GB, 14,043 models). Premise wrong.
- [x] Static coverage: wing 0/12 modelled, hub 32/39 modelled.
- [x] Render hub top with env var unset -> bodies present (kills the "unset = flat" causal claim).
- [x] Render all 4 (hub/wing x top/bottom) at `--quality high`.
- [x] Controlled experiment: hub + `KICAD9_3DMODEL_DIR=/nonexistent-bad` -> 1.9 s, 22 KB, exit 0,
      zero warnings, visually flat. Proves the silent-failure mode.
- [x] Found dangling ref: `NiceRF_LoRa2021.wrl` absent from the whole 3D package.
- [x] Verify renders by top-down inspection: hub has bodies+shadows, wing does not.
- [x] Write `docs/analysis/pcb-render-pipeline.md`; append reports; commit + push + PR.

Notes / open follow-ups:
- Wing board needs `(model ...)` added in `build_wing_v9.py` + gate-record regeneration (doc §5).
- LoRa2021 module model must be sourced (project-local) or the ref removed; it silently drops the
  largest part on the hub board.
- Render cost @1600x1200 high: hub top 121 s, hub bottom 60 s, wing top 59 s, wing bottom 34 s.
- `--quality high` is needed for shadows; output PNGs come back ~2 % smaller than requested.

## 2026-10-10 fix wave
- diagnosed the 33 gift-wrap failures: one UnboundLocalError — #32 (t_4c98fbe7) moved keys behind keymaterial.KeyMaterial while folded 9455b07a (t_c4c43d76) still called build_gift_wrap(payload,npub,signer); reconciled both call conventions in nostr_giftwrap.py -> 1103 passed / 9 skipped (was 1070/33) -> commit d339bd5
- added tools/conftest.py: the spec suite's 14 @pytest.mark.asyncio tests never ran (no async plugin declared) -> all 14 now execute -> same commit
- next: run make range-test-host + repo pytest, push pr/e80-cvm-consolidated, open ONE PR, close #26-#31/#33/#34
- 2026-10-10: reconciled the #28/#32 key-interface conflict — `keymaterial.load_keys()` now resolves the ADR §2.3 canonical CVM_* names first, keeps the E80_* aliases, and takes role name-tuples so the TX listener reads CVM_TX_*. Proven: CVM_RX_NSEC+CVM_SERVER_HEX (the RANGE-TEST-GUIDE invocation) previously raised MissingKeyError, now resolves. → commit 5ba7b79 → make range-test-host 413 passed. files: tools/keymaterial.py, tools/cvm_tx_listener.py, tools/test_keymaterial.py, tools/test_cvm_tx_listener.py
