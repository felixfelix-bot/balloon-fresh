# ADR-083 — The 2.4 GHz reflector is a BOUGHT production Ku offset dish (new or used), never a hand-built one

- **Status:** **Proposed** — an engineering recommendation with sourced prices and a computed
  surface budget; the operator has **not** selected a tier and this record **orders nothing** and
  **freezes no BOM**. It changes the *sourcing* of one line item (the 2.4 GHz reflector) and
  **rejects** a construction path; it does not touch link budgets, the positioner class or the
  tier ladder.
- **Date:** 2026-10-08
- **Decision owner:** Felix (operator) — the accessibility goal ("keeping the costs low so that
  this project remains accessible for anyone to replicate") and the DIY-vs-buy question
- **Author:** Hermes subagent (RF-gaps pass), branch `design/rf-gaps-harmonics-diy`, base
  `github/main` @ `09e1b69`
- **Related (stable references):** ADR-071 (design basis), ADR-072 (band-split duplex — the 2.4 GHz
  TX this reflector serves), **ADR-078** (right-size the antenna; **INV-3** "a 2.4 GHz dish is
  justified on interference/polarisation grounds only"; the mesh rule), **ADR-081** (**D1** the
  EIRP-cap invariant / "above ~8 dBi the 2.4 GHz ground gain is inert"; the tier ladder and
  sweet spot (b)), ADR-075 (F33), ADR-076 (stow/wind — the reflector's wind area).
- **Evidence:** `docs/analysis/rf-harmonics-and-diy-dish.md` **§B** +
  `docs/analysis/rf_gaps_model.py` (`part_b()`) +
  `docs/analysis/assets/rf-gaps/ruze-2g4-surface-error.svg`. Prices: the 2.4 GHz assembly lines of
  sweet-spot (b) in `docs/analysis/gain-per-dollar-cliff.md` §8.2 (source branch
  `design/gain-per-dollar-cliff`) and their CONFIRMED vendor pages in
  `docs/analysis/ground-station-bom-candidates.md` (source branch `design/ground-station-bom`).
  Reproduce: `python3 docs/analysis/rf_gaps_model.py`.
- **Independent review:** the Part-B figure was submitted to the vision consultant
  (`scripts/fleet/visual_consult.py`). **Verdict of record: `VERDICT: CONFIRM`, served model
  `gpt-6-astra`** (round 2, corrected figure); the round-1 answer caught a real threshold bug
  (3.30/4.67 mm → 3.37/4.77 mm) which was fixed. Verbatim answers and both rounds:
  `docs/analysis/assets/rf-gaps/consult-verdict.txt`; summary in
  `docs/analysis/rf-harmonics-and-diy-dish.md` §B.7.

**Numbering and collision note.** Numbers **066–082 are claimed on sibling design branches**
(066: `design/ground-station-lowpower-link` + `design/ground-station-flrc-max`; 067:
`design/ground-station-flrc-max` + `design/positioner-lowcost`; 068: `design/gain-per-dollar` +
`design/gain-per-dollar-cliff` + `design/amplifier-substitution`; 069: `design/tier0-accessible`;
070: `design/amplifier-hypothesis-check` + `design/rf-shopping-list`; **071–082**:
`design/adr-set-groundstation`) and are **not reused** here. `scripts/adr_next_number.py` prints
**066** because it is **branch-blind**. This record takes the fresh number **083** — verified
free **prefix-anchored against every `github/*` branch** on 2026-10-08
(`git ls-remote --heads github` → no branch carries a `docs/adr/083-*`; the highest number present
anywhere is 110, and the 066–082 band is fully claimed as listed above). The full table and the
reason no rename is made are in **ADR-071 §Numbering and collision note**.

---

## Context

Sweet-spot (b) (`gain-per-dollar-cliff` §8.2) builds its 2.4 GHz aperture from a **Gibertini 75 SE
0.75 m dish (€94.90)** + an **RF Hamdesign LH-13XL helix feed (€220.00)** + a **CLX1 clamp
(€46.00)** — a **€360.90** assembly. The question this record answers: *can a DIY reflector
(foil / metal tape / welded mesh / 3D-printed / fibreglass / a used dish) beat it?*

Four findings decide it.

**1. At 2.4 GHz the λ/10 rule is a ~6.9 dB tolerance, not a budget.** At the 2.400 GHz band edge
λ = 124.91 mm, so **λ/10 = 12.49 mm**. Ruze's equation
(`G(ε) = g₀ − 685.81·(ε/λ)²` dB, <https://en.wikipedia.org/wiki/Ruze%27s_equation>) puts a
12.49 mm RMS error at **6.86 dB of gain loss**. The real thresholds are far tighter:

| budget | RMS surface error allowed | in λ |
|---|---:|---:|
| < 0.5 dB | **≤ 3.37 mm** | ≈ λ/37 |
| **< 1.0 dB** | **≤ 4.77 mm** | ≈ λ/26 |
| λ/10 "rule" | 12.49 mm | λ/10 (**6.86 dB**) |

So a 2.4 GHz reflector needs **~3.4 mm RMS for <0.5 dB** and **~4.8 mm RMS for <1 dB** — a bar a
**production dish clears by ≥4×** (a Ku DTH dish is built for 10.7–12.75 GHz, i.e. ~λ/100 at
2.4 GHz).

**2. The reflector is only 26 % of the assembly — the feed + clamp are 74 %.** Gibertini €94.90
(26.3 %), LH-13XL €220.00 (61.0 %), CLX1 €46.00 (12.7 %). A DIY reflector can save **at most the
€94.90 dish line**, and it **cannot** save the F/D-matched feed, which a DIY reflector has no
documented f/D to match.

**3. The genuinely-DIY methods do not beat €94.90.** From `rf_gaps_model.part_b()` (RMS values are
**ESTIMATEs** — no measured source exists; the Ruze loss is computed):

| method | RMS (ESTIMATE) | loss @2.4 GHz | <1 dB? |
|---|---:|---:|:--:|
| aluminium foil, hand-formed | 8–25 mm | 2.8–27.5 dB | no |
| metal tape over foam/ribs | 5–15 mm | 1.1–9.9 dB | no |
| welded mesh on DIY ribs | 3–8 mm | 0.4–2.8 dB | borderline |
| 3D-printed petal dish | 1–3 mm | 0.04–0.40 dB | yes |
| fibreglass over a mould | 0.5–1.5 mm | 0.01–0.10 dB | yes |
| **used production Ku DTH dish** | **0.3–1.0 mm** | **0.00–0.04 dB** | **yes** |

Accuracy is clearable by the printed/fibreglass/used options — but the printed and fibreglass
routes need a **rigid backing / a mould** that costs more than the €94.90 dish, and the mesh route
inherits ADR-078's **`TODO(unverified)` measured mesh-vs-solid penalty**. Only the **used
production dish** is both accurate **and** cheaper.

**4. The 2.4 GHz aperture is not link-critical.** ADR-081 **D1** fixes the EIRP-cap invariant:
above ~8 dBi, 2.4 GHz *ground* gain is **inert** for link closure, and ADR-078 **INV-3** says a
2.4 GHz dish is justified on **interference-rejection / polarisation** grounds only. The reflector
is therefore **not bought for dB**; its surface quality governs its **sidelobes and cross-pol** —
which is exactly what the Ruze budget above now bounds.

## Decision

**D1 — The 2.4 GHz reflector is a BOUGHT production solid (or coarse-mesh) parabolic dish of
~0.75–0.9 m with a documented f/D.** The **new Gibertini 75 SE 0.75 m (€94.90, CONFIRMED)** is the
baseline (documented offset feed, priced, in stock); a **used production Ku DTH offset dish
(~€50, ESTIMATE, `TODO(unverified)`) is the preferred lower-cost sourcing** and is usually
**larger and more accurate** than the 0.75 m Gibertini.

**D2 — Hand-built reflectors are REJECTED for this station.** Aluminium foil, metal tape, DIY mesh
on DIY ribs, 3D-printed petal dishes and fibreglass-over-a-DIY-mould are **not** to be used,
because (a) none beats €94.90 once a former/rib set and labour are counted, (b) they carry **no
documented f/D** for the F/D-matched helix feed, and (c) their RMS is **unmeasured**.

**D3 — The surface-accuracy screening criterion is the Ruze budget: RMS ≤ 4.77 mm for <1 dB at
2.4 GHz.** Every candidate production dish clears it by ≥4×, so this is a **screening** gate (a
warped or dented reflector fails it), not a discriminator between candidates.

**D4 — The reflector is bought for interference rejection and polarisation, not gain.** Per
ADR-081 D1 / ADR-078 INV-3, no 2.4 GHz ground aperture is bought for gain above ~8 dBi.

**D5 — Acceptance for a used dish.** On receipt, **verify the surface** (straightedge / string
test; reject dents ≥ a few mm) and, once installed, **measure the S21 / gain against the new-dish
reference** at 2.4 GHz. A used reflector is accepted only with that surface verification.

## Invariants

- **INV-1.** The 2.4 GHz reflector is a **production parabolic dish with a documented f/D**.
- **INV-2.** No hand-built reflector is used without a **measured RMS surface report**.
- **INV-3.** The 2.4 GHz reflector is **not bought for gain above ~8 dBi** (the EIRP-cap
  invariant, ADR-081 D1).
- **INV-4.** A used dish is accepted only with a **surface verification** (D5).

## Consequences

### Positive
- Keeps the 2.4 GHz aperture path **fully purchasable and replicable** (the operator's accessibility
  goal), with a **documented** surface and f/D, and adds a **~€45 cheaper** used-dish sourcing with
  a **larger** aperture.
- Kills a class of work (hand-built reflectors) that would have consumed fabrication time for a
  reflector that is **not** on the link's critical path (ADR-081 D1).
- Replaces the folk **λ/10** yardstick with the **Ruze** budget, so any future reflector proposal
  can be screened numerically.

### Costs / risks
- The **used-dish price is an ESTIMATE** (`TODO(unverified)`; eBay.de 403 to scripted fetch — the
  BOM §8 item 13 flags used-dish searching as manual). The recommendation does **not** depend on
  it: the **CONFIRMED** new Gibertini at €94.90 stands either way.
- A used dish is an **unknown-f/D, unknown-surface** part until D5 is done; the surface accuracy of
  any specific used unit is `TODO(unverified)` until measured.
- This record does **not** re-open the **2.4 GHz uplink legal ceiling** defect (flat 20 dBm vs
  ≈14.26 dBm PSD, ADR-072/ADR-081 Open items) — it is a *reflector sourcing* decision and is
  independent of that ceiling.

## Open items (not assumed)

- **`TODO(unverified)`** the used-Cu-dish price and the local availability (Aachen/DE market).
- **`TODO(unverified)`** the **measured** RMS surface accuracy of a specific used dish.
- **`TODO(unverified)`** the **measured** mesh-vs-solid gain penalty (inherited from ADR-078).
- **`TODO(unverified)`** the Gibertini 75 SE's own f/D (the BOM marks it "f/D + wind TODO"; the
  feed column assumes an offset dish in the OP-series F/D ≈ 0.66 family).

## Relation to other ADRs

- **Refines** ADR-078 D2/D3 and ADR-081's sweet spot (b): the sweet-spot-(b) reflector stays a
  **production Ku offset dish**, now with explicit **new-or-used** sourcing and an explicit
  **rejection of hand-built reflectors**.
- **Depends on** ADR-081 D1 (the EIRP cap) and ADR-078 INV-3 (a 2.4 GHz dish is for interference /
  polarisation only).
- **Supersedes nothing.** It is the first record to own the 2.4 GHz **reflector surface-accuracy**
  question.

## For future sessions

- **One-line rule:** the 2.4 GHz reflector is a **bought production Ku offset dish (new €94.90 or
  used ~€50)** — **never hand-built**; screen it against the **Ruze** budget
  (**RMS ≤ 4.77 mm for <1 dB** at 2.4 GHz), because **λ/10 = 12.49 mm is a 6.86 dB tolerance, not a
  budget**.
- **Check first:** is the dish a **production** part with a **documented f/D**, and (if used) has
  its **surface** been verified (D5)?
- **Reproduce:** `python3 docs/analysis/rf_gaps_model.py`;
  `python3 docs/analysis/render_rf_gaps_figure.py > docs/analysis/assets/rf-gaps/ruze-2g4-surface-error.svg`.
