# PLAN — Flight board routing to JLCPCB (agent + human-in-the-loop)

**Date:** 2026-09-16 · **Board:** `tracker/hardware/output/v_c3_flight_4layer_routed.kicad_pcb`
(55×45 mm, 4-layer, 20 footprints) · **Goal:** fab-ready gerbers for JLCPCB, with a
measurable, adversarially-checkable definition of "ready".

Operator decision (2026-09-16): willing to act as human-in-the-loop where it
**lowers cost or raises quality** — and requires (a) strict quality gates on the
agent's work, (b) explicit, tested instructions for every human step.

---

## 0. Tool decisions (verified live, this session)

| Tool | Role here | Verified constraint |
|---|---|---|
| **KRT** — `drandyhaas/KiCadRoutingTools` (MIT, ★437, pushed 2026-09-16) | placement-for-routability (`py_placer/place_optimize.py`), A* octilinear multi-layer routing, `--refill-zones` cross-check, `py_tools/fill_for_delivery.py` | README: "Compatible with **KiCad 9 and KiCad 10**", CLI + plugin. Limitations: no push-and-shove, no blind/buried vias, no per-region rules. Needs Rust core build or binary (Python 3.9+, abi3-py39) |
| **Freerouting 2.4.1** (local jar) | second opinion / baseline route | `java -jar freerouting.jar -de X.dsn -do X.ses -mp 10 -mt 4`; DSN via pcbnew `ExportSpecctraDSN` |
| **kicad-cli 9.0.8** | DRC referee + gerber/drill export | `pcb drc --format json`; no autorouter built in |
| **`drc_score.py`** | the scorecard — one row per attempt | progress = `shorts+clearance+unconnected` falls |
| **Konnect** ★693 | **excluded** | KiCad **10 only** (we run 9.0.8) |
| OpenROAD / "Glana" / PDF-form tooling | **excluded** | IC place-and-route / nonexistent / irrelevant |

**Division of labour that the evidence supports:** deterministic geometry (place,
route, referee) is done by tools; the LLM decides *what* to place and *which*
constraints apply. Inference is never spent on coordinates.

---

## 1. Stages, owners, and hard gates

Gate rule: **a stage is done only when its evidence artifact exists and a second
party re-runs the verifier command on the frozen `sha256`.** No prose claims.

### S0 — Placement to zero overlap · **AGENT, $0**
- Do: audit netlist (27 pads currently carry **no net** — confirm intentional/mechanical),
  run `py_placer/place_optimize.py <board> --max-displacement 3` (KRT) and/or explicit
  grid coordinates; freeze the placement; rip all tracks.
- **GATE S0:** `0` pad-overlap pairs (0.2 mm margin, 0.2 mm margin script), `courtyards_overlap = 0`,
  zero segments on the board, footprint count `>= 10`, **and `python3 placement_guard.py` exits 0**
  (no R1/R2 violations — one writer per board, no unregistered coordinate tables).
- Placement is done by the **dedicated tool** (`py_placer/place_optimize.py --max-displacement 3`,
  KRT, already cloned at `~/tools/KiCadRoutingTools`), with the LLM supplying constraints only
  (design brief + floorplan intent). A homegrown solver is fallback-only, with the failure documented.
  Measured context: 37.5 % occupancy, offenders need 0.16 mm / 0.45 mm shifts → **do not enlarge the outline**.
- The work list is `placement-source-of-truth.json`: 11 unregistered coordinate tables + 3 boards with
  two writers. Name the single canonical source there and archive the rest; do not add a 13th script.
- Evidence: `gate25_check.py` JSON + board `sha256` + committed `*_placed.kicad_pcb`.
- Why it blocks everything: every routed variant today carries the **same 2 overlap pairs
  (`U2/C4`, `D1/U1`)**. No router can fix two pads in the same space — this is the
  ceiling the old attempts asymptoted to.

### S1 — Route under ONE rule set · **AGENT, $0**
- Do: pick one design-rule file (JLCPCB-legal: 0.2 mm width/clearance, 0.6/0.3 vias) and use
  it for **every** attempt; route with KRT A* and with Freerouting; **refill zones after import**;
  DRC; emit one `drc_score.py` row per attempt.
- **GATE S1:** `shorts = 0`, `clearance = 0`, `unconnected = 0` with `fp >= 10`,
  measured under the single frozen rule file and frozen placement hash.
- Evidence: ≥2 `drc_score.py` rows + DRC JSON + rule file committed.
- Note: today's freeroute already proves the class moves — `unconnected 20 → 1` at $0,
  shorts held at 0; the 121 "clearance" was a **rule-strictness artifact** and the 33
  `hole_clearance` are **stale zone fill after SES import** (via vs In1.Cu GND pour), so
  refill + single-rule-set is the expected fix, not a rewrite.

### S2 — Adjudicate what remains · **AGENT + MANAGER, $0**
- Do: classify every residual violation `real | cosmetic` with a reason; suppress cosmetics
  only via the committed `.kicad_dru`, never silently; run the trap suite (T1 empty-board
  zero-violation, T2 cosmetic-masking, T3 stale DRC report, T4 edit-between-score-and-export,
  T5 sha256 mismatch, T6 unfilled-zone false positives, T7 frozen-placement violation,
  T8 rule-file drift).
- **GATE S2:** every remaining class is real-or-justified; `drc_traps.py` (T1–T8) green;
  `REGRESSED` rows counted as waste.
- Evidence: `PROTOCOL-PCB-ROUTING.md` (supersedes verdict §4–§5) + trap runner output + scorecard.

### S3 — Human verification before ordering · **FELIX, 15–20 min** (cards: below)
- **GATE S3:** operator signs the gerber preview + the S1/S2 scorecard row. Only then order.
- Why human: a fab mistake costs a 5–7 day cycle plus money — this is irreducibly a
  judgement call on a physical artifact, and it is exactly the "cheap insurance" case.

### S4 — Policy · **MANAGER, $0**
- **GATE S4:** every PCB card's definition of done includes a `drc_score.py` row;
  "DRC clean" in prose no longer closes a card. Record in the board/skill.

---

## 2. Human-in-the-loop: exactly where you are needed (and where you are not)

| Step | Owner | Time | Trigger |
|---|---|---|---|
| Placement fix, routing, zone refill, DRC, scoring, docs, commits, CI evidence | **agent** | — | always |
| Netlist audit (27 no-net pads) | **agent** | — | always |
| Final gerber/board eyeball + sign-off | **Felix** | 15–20 min | after S2 |
| Fallback finisher (KiCad GUI push-and-shove) | **Felix** | 30–60 min | **only if** S1 plateaus with ≤ small, localized real conflicts |
| JLCPCB order click | **Felix** | 2 min | after S3 |
| RF path confirmation (50 Ω, solid GND beneath, stitching) | **agent checks → Felix confirms** | 5 min | after S1 |

Everything else is agent work. You are *not* the router; you are the verifier and the
exception path.

---

## 3. Resource rules (how we judge we are using resources well)

- **$0 inference budget for S0–S2.** Deterministic tools attack our exact failure classes
  for free; past paid attempts produced boards with 17 shorts.
- Any paid attempt must be scored against the **$0 row** (`usd/dViol`); if it cannot beat
  the free row, it does not get funded.
- **Stop rule:** 3 attempts with no monotone decrease in `shorts+clearance+unconnected`
  → change **method**, not model.
- `REGRESSED` rows are counted as waste and investigated before the next attempt.
- Human time is reserved for verification and finishing — never for work a $0 script can do.

---

## 4. What is still open / depends on consultant returns

- Consultant A (tooling, live-verified): KRT is the substantive addition — KiCad 9 + 10,
  CLI, placement optimiser, `--refill-zones`. Its own convergence claims are still
  `CLAIM` until we run it on our board (that is S1's job).
- Consultant B (protocol): proposes `PROTOCOL-PCB-ROUTING.md` + `drc_traps.py` (T1–T8)
  and an extended `drc_score.py` row schema — adopted as the S2 evidence artifacts.
- Known non-PCB blockers: `balloon-*` clones still have **no `ngit` remote** (push-policy
  violation for public repos); `skidl` (any interpreter) and `pcbnew` (python3.14 only)
  remain split.
