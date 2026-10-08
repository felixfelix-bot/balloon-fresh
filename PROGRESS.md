# PROGRESS — level-control cluster (`design/level-control-architecture`)

Base: `github/main` @ `09e1b69`. Worktree `/home/c03rad0r/worktrees/bf-levelctrl`.

## Milestones

- [x] **M1 — branch + doc skeleton.** Worktree created, sibling branches read
      (`design/rf-shopping-list` @ `eea1cbc00702`, `design/adr-set-groundstation` @ `c07bd868776a`,
      `design/rf-gaps-harmonics-diy` @ `3dbcdb8c0224`, `design/amplifier-hypothesis-check` @ `148578c`).
      Part numbers verified against live datasheets before writing.
- [x] **M2 — numeric model.** `docs/analysis/level_control_model.py` reproduces the Friis comparison,
      the 433 path-loss / dynamic-range budget, the TX range→attenuation LUT, the ISM ceiling and the
      loop-dynamics timescales.
- [x] **M3 — figures.** `receive-agc-chain.*` and `dynamic-range-budget.*` under
      `docs/analysis/assets/level-control/`.
- [x] **M4 — design doc.** `docs/analysis/ground-station-level-control-design.md`.
- [x] **M5 — checklist.** `docs/BASE-STATION-BOARD-CHECKLIST.md` (OWNED / TO-BUY / TODO(unverified)
      statuses; TO-BUY + OWNED subtotals; spec-dispute verify notes).
- [x] **M6 — ADR-084.** `docs/adr/084-ground-station-automatic-level-control.md`; INDEX regenerated
      (`scripts/gen_adr_index.py`); `tests/test_adr_numbering.py` green. Number 084 verified free
      prefix-anchored against every `github/*` branch (083 lives on `design/rf-gaps-harmonics-diy`).
- [x] **M7 — consultant.** `scripts/fleet/visual_consult.py` run twice on the figures. **Round 1**
      (served model **`gpt-6-astra`**): model's own line **`VERDICT: REFUTE`**, structured field
      `UNPARSED` (CONFIRM/REFUTE is not the parser's vocabulary). Twelve findings accepted/acted on.
      **Round 2** (corrected figures, parser vocabulary): served **`gpt-6-astra`**, parser verdict
      **`CHANGES_REQUESTED`**; its remaining findings (frame-latency budget, pre-LNA preselection,
      TX→RX blocking row, figure annotations) all acted on, and a real label collision it caught was
      fixed. Both rounds recorded verbatim in `docs/analysis/assets/level-control/consult-verdict.txt`.
- [x] **M8 — refine from consult, final push.** §9 of the design doc carries the two-round consult
      record; figures re-rendered and re-verified.

## Verified external facts (this session, 2026-10-08)

- Datasheets fetched HTTP 200 (`curl --compressed`, browser UA):
  ADL5240 / ADL5243 / ADL5330 / AD8318 / AD8317 / ADL5513 / HMC425A at
  `analog.com/media/en/technical-documentation/data-sheets/*.pdf`.
- `psemi.com/products/digital-step-attenuators/pe43711` → 200 (redirects); specs CONFIRMED.
- `analog.com/en/products/*.html` product pages → HTTP 000 to this fleet (fleet-wide trap, same as
  the sibling shopping list). Datasheet paths work.
- AliExpress German search listings → 200; prices quoted as **"from"** (item pages JS-rendered).

## Traps hit / avoided

- **ADR allocator is branch-blind** — did NOT trust `scripts/adr_next_number.py`; scanned all
  `github/*` branches for `docs/adr/08[3-9]-*` → only 083 exists; took **084**.
- `analog.com` HTML product pages return HTTP 000; the **PDF** datasheet path is the working,
  quotable source.
- Bare `curl` vs browser UA: the sibling list's rule holds; browser UA needed for AliExpress and
  psemi redirects.
- `/opt/miniconda/bin/python3` used for matplotlib (default python3 lacks it).

## Next

M7 consult → M8 refinement. Push github first, then ngit, separately.
