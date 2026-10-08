# REPORT — design/tier0-accessible

**Task:** find and cost an ULTRA-LOW-COST accessible ground-station tier BELOW Tier A, and re-cost
Tier A now that the 2.4 GHz dish is known to be unnecessary. Lead with the EIRP-cap question.

**Branch:** `design/tier0-accessible` off `github/main` @ `09e1b69`.
**Worktree:** `/home/c03rad0r/worktrees/bf-tier0`.

## Deliverables

| Artifact | Path |
|---|---|
| Analysis | `docs/analysis/tier0-accessible-ground-station.md` |
| Repro (stdlib) | `docs/analysis/tier0_accessible_model.py` |
| Figure | `docs/analysis/figures/tier0-eirp-capped-uplink.png` |
| Figure render | `docs/analysis/render_tier0_figure.py` |
| ADR (Proposed) | `docs/adr/069-tier0-accessible-ground-station.md` (+ regenerated `docs/adr/INDEX.md`) |

## The EIRP-cap answer (headline)

**Ground 2.4 GHz uplink antenna gain above ~8 dBi buys nothing, and cannot buy anything**, because
the ground transmitter is EIRP-capped: `EIRP = P_tx + G_ground ≤ 20 dBm`, and the LR2021's 2.4 GHz
PA maxes at **+12 dBm**, so exactly **8 dB** of ground gain reaches the cap. Above that the gain
**cancels out of the uplink link equation**. A **0.6 m dish is 13.4 dB of inert gain; a 1.2 m dish is
19.4 dB**. Max compliant uplink margin **+17.4 dB @300 km / +10.7 dB @650 km**, reached exactly by an
**8 dBi panel**. (Scoped: uplink only; the ground 2.4 GHz antenna is TX-only here; aperture still
buys interference rejection / polarisation / PA back-off — the only honest reason to keep any.)

## The tiers

| Tier | Rig | Parts cost | Handles |
|---|---|---|---|
| **0a** | two omnis, fixed mast, **no pointing, no motors** | **€90–245** | low-power LR2021 in **LoRa** (both directions; 433 +13.7 dB @650 km) |
| **0b** | + **Diamond A-430S10R 13.1 dBi Yagi (€69)** on a **manual pan-tilt** | **€144–304** | everything 0a does **+ F33 FLRC 2.6 Mbps to 650 km (+5.2 dB)**, hand-aimed |
| **A (re-costed)** | Yagi + **8 dBi panel** + tracker, **dish removed** | **€616–685** (DIY) / **€546–615** (Yaesu G-450CDC €359) | Tier 0b **unattended**, +433 margin |
| A (original) | … with the 0.75 m Ku dish + €231 feed | **€927–951** | superseded |

**Saving from removing the dish:** **€266–311** like-for-like (€242–335 cross-endpoint). And, more
importantly, the dish was the **only element needing a tight beam** (1.5° budget) — removing it drops
the tightest element to the 433 Yagi's ~4°, which is *why* a no-tracker Tier 0 can exist at all.

## Honest limits (stated, not hidden)

- **All tiers need the balloon-side 2.4 GHz LNA at 650 km** (Table 1c): the no-LNA case is −7.3 dB
  (omni) / −2.3 dB (panel) and **a ground dish does not fix it** — the LNA does. At 300 km it closes
  (+4.4 dB).
- **Tier 0 cannot carry low-power FLRC at range** (needs +18.9 dBi / ~2.6 m dish). Tier 0 is LoRa
  (+ hand-aimed F33) by design.
- **The new cheap items (2.4 GHz omni/panel, manual pan-tilt, plain mast) are `TODO(unverified)`** —
  search backends were captcha-gated (Brave 429, DDG 202, Mojeek captcha, Ecosia 403, eBay 403).
  None of them changes the structure of the answer.
- **F33 rows depend on the DE amateur / airborne-SRD licence question** (ADR-039 open item (a)) —
  inherited, unresolved here.

## Consultation

`scripts/fleet/visual_consult.py`, served model **`gpt-6-astra`** (read back from the response),
**six rounds**: REFUTE → PASS WITH MINOR REVISION → Minor revision → **NOT YET ACCEPTABLE** →
CONDITIONAL PASS → **PASS**. Verdicts recorded **verbatim** in the doc's §8, with every finding
actioned. Two were substantive, not cosmetic: scoping "inert gain" to the *uplink under the cap*,
and the consultant surfacing a **real arithmetic error** in the dish+feed cost (**€314.90 → €325.90**).
The one partially-applied point (the "balloon→ground receive link" caveat) is explained, not smoothed
over: the ground 2.4 GHz antenna is TX-only in this architecture.

## Git

- `e37909b` — first commit (early, before consulting).
- `b8d4dd2` — round-1/round-2 fixes + Table 1c + figure.
- Pushed **github first, then ngit separately** (never `--atomic`, never `main`).
