# REPORT — ground-station gain-per-dollar metric (cluster: gain-per-dollar)

**Date:** 2026-10-08 · **Branch:** `design/gain-per-dollar` (off `github/main` @ `09e1b69`)
**Worktree:** `/home/c03rad0r/worktrees/bf-gainperdollar`
**Status:** design analysis complete; pushed to github + ngit; consultant §10 pending (or
recorded) at the time of this report.

## What was asked and what was delivered

| Task | Deliverable | Where |
|---|---|---|
| **1. Metric incl. the rig, applied to every candidate** | M1 avg €/dB, M1m marginal €/dB, **M2 €/(kbps·km)** (primary), M3 €/km; rationale + stated bias + margin-immunity proof; Tables A–D; non-monotonicity enumerated | doc §1, §2 |
| **2. Metal manufacturing, real services + prices** | 9 services with published terms (min order, lead time, price evidence) + metal-vs-printed table + part split + indicative part costs | doc §3 |
| **3. Closed-loop / position-aware motors** | Yes for pointing error, NO for back-driving; correct combination; sourced options with prices | doc §5 |
| **4. Consultant challenge to the metric and ranking** | `visual_consult.py`, verdict verbatim + served model named | doc §10 |
| **DELIVERABLE** | recommendation + reasoning + choice table A–E; **ADR-068 Proposed** | doc §6, §7; `docs/adr/068-*` |

## Files created / modified

- `docs/analysis/ground-station-gain-per-dollar.md` (NEW, ~66 KB) — the deliverable.
- `docs/analysis/ground_station_gain_per_dollar_model.py` (NEW) — prints every table; single source of truth for §1.6, §2.0–§2.7.
- `docs/analysis/render_gain_per_dollar_figure.py` (NEW) + `docs/analysis/assets/gain-per-dollar-challenge.png` (NEW) — the artifact put to the consultant.
- `docs/analysis/assets/consult-verdict-gain-per-dollar.txt` (NEW) — the consultant's verbatim answer.
- `docs/adr/068-ground-station-gain-per-dollar.md` (NEW, Proposed).
- `docs/adr/INDEX.md` (REGENERATED via `scripts/gen_adr_index.py` — it is a generated file).
- `PROGRESS.md` (NEW, gitignored → committed with `-f`).
- `REPORT.md` (this file; gitignored).

**`AGENTS.md` untouched. Nothing ordered. No board/schematic change.**

## Headline results

1. **Metric:** `M2 = EUR_total / max_R(R · d_max(R))` [€ per (kbps·km)], `EUR_total` =
   antenna + feed + coax + connectors + **positioner/rotator or the whole DIY tracker**
   (motors, reducers, encoders, drivers, controller, anemometer) + mast + build allowance.
   M2 is the primary metric; M1m (marginal €/dB) is the most diagnostic. **The ratio of any
   two candidates is exactly independent of the fade-margin assumption.**
2. **Ranking:** a **70 cm Yagi beats every purchasable 433 dish** on €/(kbps·km), €/km and
   marginal €/dB. Best: **Diamond A-430S15R (14.8 dBi, €74.50) on the DIY P2 tracker →
   €735 all-in, 0.0019 €/(kbps·km)**, 2.6 Mbps to 150 km on the worst-case board (532 km
   with the F33). Best marginal: **Diamond A-430S10R → €5.3/dB** for the first 13.1 dB.
3. **Non-monotonicity (the operator's insight):** the same **0.90 m dish is €785 mesh /
   €2,081 solid at identical 10.35 dBi**, because the solid dish's 0.636 m² projected area
   exceeds the Yaesu G-5500DC's **0.50 m² mast rating** → forces a SPID BIG-RAS (€1,775).
   **Mesh is a positioner-class saving, not a reflector saving.** Marginal €/dB is **€5–69
   on the Yagi+DIY ladder** and **€127–598 on the dish ladder**; the cliffs are at the
   positioner class boundaries. The 1.90 m mesh dish's €598/dB step is **59 % rotator**.
4. **Metal fab:** online sheet metal ships to DE at retail scale — Xometry (**no minimum,
   3 business days**), Protolabs (**as fast as 1 day**), Schaeffer AG Berlin (**5–8 working
   days**, 10/20/30 % quantity discounts), 247TailorSteel, Laserhub, Cutworks (same-day if
   ordered by 09:30), Blechking, SendCutSend (US, published example **$37.49/part**).
   Metal for the load path, printed for covers, **gearing bought**. Indicative metal part set
   **€250–470** (ESTIMATE).
5. **Closed-loop:** fixes **pointing error** (and is what keeps the €429 DIY tracker viable);
   does **NOT** fix **back-driving**. Correct combination = self-locking worm + closed-loop
   feedback + fail-safe brake + anemometer stow. Sourced: closed-loop driver $46.64–48.04,
   NEMA 17 CL motor $77.40, **17-bit absolute-encoder AC servo kit $98.43**.
6. **Highest-leverage euro: the ~$8 F33 module** — it multiplies every ground candidate's
   range by **3.55** (+11 dB for ~$8). No ground purchase can match it.

## Git evidence

| milestone | commit | github | ngit |
|---|---|---|---|
| doc + model + PROGRESS | `6849a16257e3c488f7cbf778f68b3d02803be417` | ✓ | ✓ |
| ADR-068 + figure + INDEX regen | `0ea36b4899bf9e684f432ac7eb365c49639e1104` | ✓ | ✓ |

`main` untouched at `09e1b69e1264074d87e61dc9bf3e448c2d602afb` (verified by `git ls-remote`).
Pushed github **first**, then ngit **separately** (no `--atomic`); never force-pushed.

## Issues encountered (honest)

1. **The consultant's default 180 s HTTP timeout was too short** for a large multimodal prompt
   on `gpt-6-astra` — the first retry loop exited 3 ("router unreachable: timed out") while the
   same model answered an instant **text** probe in ~2 s. Diagnosed and re-run with
   `--timeout 900`. **Recorded because it is a reusable measurement for the next consult.**
2. **`gpt-6-astra` is served by the router but is absent from its `/v1/models` list** — a
   `/v1/models`-based availability check would wrongly conclude the lane is down. Verify with a
   text probe instead.
3. **ADR number collision across branches:** `scripts/adr_next_number.py` prints `66`, but
   `066` exists on `design/ground-station-lowpower-link` and `067` on
   `design/positioner-lowcost` (neither in this worktree's history). Used **068** after
   checking every remote branch; the ADR carries a numbering note. This is the repo's
   documented cross-branch defect class.
4. **Repo contradiction flagged, not resolved:** SPX-06 (€5,487, 716 N·m rated) vs SPID
   BIG-RAS (€1,775, 2,712 N·m brake) — price and rating orderings disagree. No winner named.
5. **`PCBWay` / `JLCPCB` sheet-metal pages returned HTTP 404** → not cited as a metal service.
   Search engines (DDG 202, Mojeek captcha) and DigiKey/Mouser (403) were blocked; all web
   work used direct vendor fetches with a browser UA.
6. **One doc correction made after the first commit:** a dish/Yagi €-per-unit ratio range was
   stated as 1.7–2.2× and is 1.8–3.1×, and a "every one under €1,000" claim was wrong for the
   FX 7073 (€1,315.50). Both fixed before the final push.
