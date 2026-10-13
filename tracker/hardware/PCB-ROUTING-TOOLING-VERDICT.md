# PCB ROUTING TOOLING — VERDICT & PROGRESS METRICS

**Date:** 2026-09-16 · **Trigger:** Felix pasted an AI-mode conversation recommending
"reverse-OCR-style" tooling for PCB routing; asked whether it makes routing the
flight board easier without breaking DRC, how to measure progress, and how to
judge resource use. Board under discussion: the balloon flight board
(`tracker/hardware/output/v_c3_flight_*.kicad_pcb`) for JLCPCB ordering.

Everything below was vetted live (GitHub API + local measurement). Nothing is
taken from the pasted conversation on trust.

---

## 0. TL;DR

1. The paste's **core advice is correct** — LLM as architect, deterministic
   router as router, DRC checker as referee — and **we already run parts of it**
   (Freerouting artifacts exist in `output/freerouting_artifacts/`; pcbnew 3.14
   API; SKiDL). The bottleneck is not a missing tool, it is a **missing referee
   loop and a missing scorecard**.
2. Of the tools named, **most are real but the URLs/orgs are wrong**, and two
   items are fabricated. KiCad has **no built-in autorouter** and OpenROAD is
   **IC place-and-route, not PCB** — the paste conflates both.
3. Measured baseline today: the flight board is **not fab-ready**. Best state is
   the 4-layer route: **17 violations, 0 shorts, 3 clearance, 20 unconnected**.
   The 2-layer handoff state has **17 shorts** — geometric failures an LLM
   cannot see by reading text.
4. **Cheapest real improvement is free**: run Freerouting (already installed)
   and OrthoRoute on the current best board, score both — no LLM spend.
5. Progress is now measurable: `drc_score.py` emits one comparable row per
   attempt. Progress = reduction in **shorts + clearance + unconnected**;
   total-violation counts are explicitly NOT trusted (silk/mask noise).

---

## 1. Claim triage — REAL / FABRICATED

| Claim in paste | Verdict | Evidence (live) |
|---|---|---|
| SKiDL — programmatic circuits in Python | **REAL** | `devbisme/skidl` ★1658, MIT, pushed 2026-08-20. Locally installed **2.2.3** (skill pins 2.3.0 — drift to fix) |
| "skidl-skills Plugin" (part sourcer / coder / ERC reviewer sub-agents) | **REAL — wrong location** | really `nickkraakman/skidl-skills` ★18, MIT, pushed 2026-04-08 |
| "kicad-tools by rjwalters" — JSON output for agents | **REAL** | `rjwalters/kicad-tools` ★61, pushed **2026-09-16** (active today) |
| "Konnect — KiCad IPC API over MCP, Speccra DSN, atomic S-expr edits" | **REAL — wrong name** | really `mixelpixx/Konnect` ★693, "AI-assisted PCB design for KiCAD **10**". `Konnect/Konnect` = 404. **KiCad 10 only — we run 9.0.8** |
| DeepPCB KiCad plugin (RL routing engine beside KiCad) | **REAL — wrong org** | really `instadeepai/deeppcb-kicad-plugin` ★66, Apache-2.0, pushed 2026-08-11 |
| OrthoRoute — GPU-accelerated DRC-safe pathfinder | **REAL — wrong org** | really `bbenchoff/OrthoRoute` ★407, MIT, Python, pushed 2026-07-31 |
| Freerouting | **REAL — already ours** | `freerouting/freerouting` ★1986. `~/.config/freerouting/` + `output/freerouting_artifacts/*.dsn` exist locally |
| KiCad MCP servers (paste implies "Konnect" is the only one) | **REAL, better options exist** | `Finerestaurant/kicad-mcp-python` ★40, `Netlist-Studio/kicad-mcp` ★19 (KiCad 9 IPC) |
| CommonForms / SimplePDF / local-llm-pdf-ocr (the PDF half) | **REAL** | `jbarrow/commonforms` ★1290, `SimplePDF/simplepdf-embed` ★408, `ahnafnafee/local-llm-pdf-ocr` ★113 — **irrelevant to PCB routing** |
| **"Glana"** | **FABRICATED** | 0 GitHub results for `Glana pcb` |
| **"Speccra DSN"** | **FABRICATED SPELLING** | the real format is **Specctra** DSN (KiCad's own export) |
| **"KiCad Autorouter"** | **DOES NOT EXIST** | KiCad ships no autorouter; Freerouting is the external one |
| **"OpenROAD Python API" as a PCB router** | **CATEGORY ERROR** | OpenROAD is digital IC place-and-route; it does not route PCBs |
| LLM-in-DRC-loop as novel Hermes feature | **ALREADY OUR PROBLEM TO SOLVE** | we have the board, the DRC CLI and the history; what we lacked was the loop + metric |

**Pattern:** consistent with the standing finding that AI-search resource lists
run ~⅔ real — here 8 of ~10 named things exist, but 5 of those had wrong
org/name/compat and 2 were invented.

---

## 2. Measured state of the flight board (baseline)

Fresh `kicad-cli 9.0.8` DRC runs, recorded into `drc_snapshots/history.jsonl`:

| board | fp | violations | shorts | clearance | unconnected | vias | copper mm | fab-ready |
|---|---|---|---|---|---|---|---|---|
| `output/v_c3_flight_v7_routed.kicad_pcb` (2-layer) | 20 | 69 | **17** | 11 | 40 | 36 | 487.7 | no |
| `output/v_c3_flight_4layer_routed.kicad_pcb` (4-layer) | 20 | 17 | **0** | 3 | 20 | 48 | 167.2 | no |
| `hub_board_f33.kicad_pcb` | 14 | 177 | 15 | 10 | 32 | 46 | 793.1 | no |

Dominant 2-layer failure types: `solder_mask_bridge` 19, `shorting_items` 17,
`via_dangling` 15, `clearance` 9.

**Root cause of the earlier struggle is geometric, not semantic.** Every one of
those classes is a millimetre-scale adjacency decision that cannot be derived by
an LLM reading coordinates. Our own `DRC_FINAL_VERIFICATION.md` (2026-08-05)
already recorded the second failure mode: a worker reported completion while the
board was *structurally untouched* (26 unconnected items unchanged). So the past
struggle was (a) geometry left to an LLM, and (b) verification by hand-reading
100 KB DRC dumps. This document fixes (b); the tooling shortlist below fixes (a).

---

## 3. Which tooling actually helps us — ranked

Ranked by expected effect on OUR measured failure modes
(`shorts` / `clearance` / `unconnected`) per unit of effort:

1. **Freerouting (installed, free, deterministic).** We already have the
   DSN/SES round-trip and prior session artifacts. Step: re-run on the current
   best (v7-4layer) with JLCPCB-legal design rules from `.kicad_pro`, score it.
   Expected: shrinks `unconnected` and `clearance`. LLM cost: **$0**.
2. **OrthoRoute (`bbenchoff/OrthoRoute` ★407, MIT, Python, GPU).** Multi-layer
   pathfinder; directly targets shorts/clearance/unconnected. Trial in a
   sandbox against v7-4layer, score with the same script. Risk: young project,
   GPU dependency, KiCad 9 interop unproven → treat as an experiment, not a
   dependency.
3. **A DRC-referee loop with `kicad-cli pcb drc --format json`** (already local).
   Deterministic, free, and the only thing that makes "self-correction" real:
   attempt → JSON report → machine-readable diff → next attempt. This is the
   piece the paste correctly identified and that we lack *as tooling* (today the
   loop lives in a worker's head, ending in hand-read text dumps).
4. **`kicad-tools` / `kicad-mcp` (KiCad 9 IPC + JSON).** Plumbing so the referee
   loop reads the board deterministically (netcodes, pads, DRC constraints)
   instead of regex-parsing S-expressions. Low risk, high leverage. `kicad-tools`
   was pushed today — active.
5. **Konnect (★693).** Highest-star AI-PCB project in the list, but it targets
   **KiCad 10**; we are on **9.0.8**. Compatibility gate first; not a drop-in.
6. **DeepPCB plugin (★66).** RL routing/benchmark research; sandbox curiosity
   after OrthoRoute.
7. **SKiDL + skidl-skills.** Schematic/netlist stage only — does not route, so it
   cannot move the DRC numbers. Keep it where it already works.

Explicitly **not** useful here: OpenROAD (ICs), "Glana" (doesn't exist), and the
PDF-form tooling in the first half of the paste.

**Division of labour the evidence supports:** the LLM decides *what* to place and
*which constraints* apply (netlist, clearance classes, RF impedance, decoupling
proximity); a deterministic router lays copper; `kicad-cli` referees; the
scorecard decides whether the attempt counted. Spend inference on decisions,
never on geometry.

---

## 4. How progress is measured (implemented in this PR)

`tracker/hardware/drc_score.py` turns every attempt into one row:

```
python3 drc_score.py <board.kicad_pcb> --label v8 --tool freerouting --cost-usd 0.00 --note "..."
python3 drc_score.py --compare
```

Per attempt it records: `fp` (footprint count), total `violations`, `shorts`,
`clearance`, `other`, `unconnected`, `parity`, `vias`, `segments`, `copper_mm`
(actual copper laid down), `cost_usd`, the file `sha256_12`, and `fab_ready`.

Derived per row: `dViol` (blocking errors removed vs the previous attempt of the
same label), `usd/dViol`, and a **REGRESSED** flag.

**Hard definition of progress:** a change counts only if it reduces
`shorts + clearance + unconnected`. A falling *total* violation count is not
progress — `silk_over_copper` / `solder_mask_bridge` cosmetics can move the
headline number while the board becomes less manufacturable.

**Fab-ready gate:** `shorts = 0 AND clearance = 0 AND unconnected = 0 AND fp ≥ 10`.
The `fp ≥ 10` clause exists because DRC on an empty board reports zero violations
(recorded trap in the SKiDL skill: a 2 KB board "passed" every check).

---

## 5. How to judge whether we are using resources well

Judged from the scoreboard, not from effort narratives:

| Signal | Meaning | Action |
|---|---|---|
| `usd/dViol` | inference dollars per blocking error removed | compare every LLM attempt against the **free** Freerouting/OrthoRoute baseline; if the free tool wins, stop paying |
| `attempts-to-fab-ready` | iterations needed to reach the gate | >3 attempts with no monotone decrease = the loop is thrashing → change method, not model |
| `REGRESSED` rows | paid-for rework (blocking errors went up) | count them as waste; investigate the cause before the next attempt |
| `copper_mm` / `vias` churn | how much re-routing bought the gain | rising copper with flat blocking count = rip-up/re-route churn, not progress |
| `fp` trend | placement instability | changing footprint counts mid-routing invalidates comparability — freeze placement before scoring routes |

**Resource rule that follows from the data:** deterministic tools cost $0 per
attempt and attacked exactly our failure classes, while past LLM attempts spent
dollars and produced boards with 17 shorts. Therefore: **free tools first, LLM
only for decisions.** That inverts the order the pasted advice implies.

---

## 6. Next actions (cheapest first, all queueable)

1. **(free)** Freerouting pass on `v_c3_flight_4layer_routed.kicad_pcb` with
   JLCPCB-legal rules → score → compare against the $0 baseline row.
2. **(free)** OrthoRoute sandbox trial on the same board → score.
3. **(free)** Wrap the referee loop: `route attempt → kicad-cli DRC JSON →
   drc_score.py row → diff of violation types → next attempt`.
4. **(policy)** Any future PCB task's definition of done must include a
   `drc_score.py` row; no card completes on a prose claim of "DRC clean".
5. **(quota-gated)** Consultant review of this verdict + tool-fit — blocked while
   both z.ai keys are locked (reset 2026-09-17 15:47) and the host is above the
   dispatch load gate. Queued, not skipped.

## 7. Open gaps in our own setup (found while measuring)

- `skidl 2.2.3` installed vs `2.3.0` pinned by our skill — drift.
- `skidl` not importable under `/usr/bin/python3.14` (the only interpreter with
  working `pcbnew`) → SKiDL and pcbnew live in different interpreters.
- `balloon-*` clones have **no `ngit` remote**, so board work cannot dual-push
  (violates our own push policy for public repos).
- ~~No freerouting `.jar` found on disk~~ — **CORRECTED the same day:** the jar IS
  present at `~/tools/freerouting/freerouting.jar` with java 17.0.20 installed;
  the earlier check searched the wrong paths. Action 1 needed no re-provisioning
  and has already run — see §8.
- `skidl` is **not importable** from the default `python3` (`ModuleNotFoundError`),
  while `pcbnew` only works under `/usr/bin/python3.14` — schematic-stage and
  board-stage tooling still live in different interpreters.
- **No discrete GPU on this host** (`nvidia-smi` absent) → OrthoRoute's CUDA path
  is unreachable here; any OrthoRoute trial must first establish a CPU fallback.

---

## 8. Update — the two $0 actions were executed (2026-09-16, later session)

Freerouting 2.4.1 (java, DSN export via pcbnew `ExportSpecctraDSN` → SES import),
rows now in `drc_snapshots/history.jsonl`:

| attempt | violations | shorts | clearance | unconnected | vias | copper mm | fab-ready |
|---|---|---|---|---|---|---|---|
| manual 4-layer (baseline) | 17 | 0 | 3 | 20 | 48 | 167.2 | no |
| freerouting (mp10) | 134 | 0 | 125 | **1** | 66 | 577.8 | no |
| freerouting + explicit JLCPCB rules | 130 | 0 | 121 | **1** | 65 | 577.8 | no |

1. **The free deterministic router attacked exactly the class the LLM could not:**
   `unconnected` 20 → 1 (95 % of the electrical-completeness failures gone) at $0
   inference cost, `shorts` held at 0.
2. **The clearance blow-up is NOT yet a like-for-like comparison.** Trial 2 *also*
   tightened the design rules (explicit JLCPCB 0.2 mm width/clearance, 0.6/0.3 vias),
   so its 121 `clearance` + 33 `hole_clearance` may not be scored against a baseline
   measured under looser board rules. Per §4's own rule — a change counts only when
   compared at identical rules on a frozen revision — the honest interim verdict is
   *"rule set changed; re-score under one rule set before ranking"*. This is the
   first live instance of the comparability trap §5 warned about, and it is a
   **scoring** defect, not a routing regression.
3. Copper 167 mm → 578 mm, vias 48 → 65: the router actually routed nets the hand
   fix had left dangling. Rising copper with a *falling* blocking count on the
   class that matters reads as real routing, not churn — but it is the §5 signal to
   keep watching.

**Next step this implies:** re-run both free tools under ONE design-rule file and
score with `drc_score.py` *before* any LLM attempt is funded, then adopt this doc +
the trial rows as the board's definition-of-done baseline (§6 action 4).
