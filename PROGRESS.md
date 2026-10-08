# PROGRESS — cluster: ground-station gain-per-dollar metric

Branch: `design/gain-per-dollar` (off `github/main` @ `09e1b69`)
Worktree: `/home/c03rad0r/worktrees/bf-gainperdollar`

## Deliverable
`docs/analysis/ground-station-gain-per-dollar.md` + `docs/analysis/ground_station_gain_per_dollar_model.py`
+ ADR `docs/adr/068-ground-station-gain-per-dollar.md` (Proposed).

## Milestones
- [x] M1 — read prior art (`ground-station-bom`, `ground-station-lowpower-link`,
      `positioner-lowcost`, `ground-station-flrc-max`); prices/gains/wind/back-driving absorbed, not re-derived.
- [x] M2 — metric defined (M1 avg €/dB, M1m marginal €/dB, M2 €/(kbps·km), M3 €/km@rate) with rationale
      ("M2 is most useful; M1m is most diagnostic"); margin-immunity of the ratio stated.
- [x] M3 — model script written + run; tables A (worst-case low-power), B (licence-exempt),
      C (F33), D (marginal over shared rig), monotonicity, wind/torque classification.
- [x] M4 — metal-fabrication research with URLs (Xometry, Protolabs, SendCutSend, Schaeffer AG,
      247TailorSteel, Laserhub, Cutworks, Blechking, metal-market.eu); metal-vs-printed table;
      metal/printed part split; indicated costs (ESTIMATE, anchored on SendCutSend's published example).
- [x] M5 — closed-loop answer (fixes pointing, NOT back-driving; correct combo = self-locking worm +
      closed-loop + brake + stow), with sourced options/prices (StepperOnline CL drivers/motors,
      17-bit absolute-encoder AC servo kit $98.43, AS5600 class).
- [x] M6 — doc written + committed early.
- [ ] M7 — visual consultant engaged; verdict recorded VERBATIM with the served model named.
- [ ] M8 — ADR 068 drafted (next free number checked = 068; 066 and 067 are taken on
      `design/ground-station-lowpower-link` and `design/positioner-lowcost`).
- [ ] M9 — push github THEN ngit separately; `git ls-remote` verification pasted.

## Key results (for a later reader)
- Best M2: **Diamond A-430S15R 14.8 dBi, €74.50, on DIY P2 tracker → €735 all-in, 0.0019 €/(kbps·km)**.
- Best marginal gain-per-dollar: **Diamond A-430S10R → €5.3/dB** for the first 13.1 dB; the dish
  ladder costs **€127–145/dB** → 26× worse past the Yagi rung.
- **Non-monotonicity (the insight):** the same 0.90 m dish is **€785 mesh / €2,081 solid at
  identical 10.35 dBi** — mesh is a *positioner-class* saving (0.50 m² Yaesu mast rating), not a
  reflector saving.
- **F33 (~$8) multiplies every ground candidate's range by 3.55** → best gain-per-euro in the system.
- FLRC at 650 km on the low-power board needs a 3.0–3.5 m dish whose former no vendor sells.

## Allowed scope (hard rules honoured)
- Never push main/master, never force-push; github first, then ngit separately (no `--atomic`).
- `AGENTS.md` untouched. Nothing ordered. Design only.
