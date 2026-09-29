# PCB Inspector Gate — DRC verification after Phase 2 and Phase 4

**Task:** t_edd80fc8 (worker-inspector)
**Date:** 2026-09-29
**Toolchain:** kicad-cli 9.0.8 (independent re-run — no implementer DRC JSON trusted)
**Repo inspected:** ~/repos/balloon-fresh (worktree ~/worktrees/t_24d9e30c, branch fix/tollgate-payack-seq-whitespace)
**Plan under test:** docs/coordination/PCB-AUTOROUTE-EXECUTION-PLAN.md
**Cold review:** kimi-k3 (Ollama Cloud) — cross-family vs the tier/coding worker. Rounds and verdicts in §9.

---

## VERDICT: BLOCKED — BOTH GATES FAIL

| Gate | Requirement | Measured | Result |
|------|-------------|----------|--------|
| Phase 2 | <50 violations | **405** | FAIL |
| Phase 2 | 0 shorting_items | **15** | FAIL |
| Phase 2 | 0 clearance violations | **8 clearance + 58 copper_edge_clearance = 66** | FAIL |
| Phase 4 | gerbers exist for all layers of the Phase 4 board | **no Phase 4 board, no Phase 4 gerber set** | FAIL |
| Phase 4 | final DRC <50 | not evaluable (no Phase 4 artifact) | FAIL |
| Phase 4 | JLCPCB order-ready | no per-designator PCB-assembly BOM paired with any gerber set | FAIL |

**Downstream tasks must not proceed.** Phases 3, 4 and 6 are `blocked`; Phase 5 is
`ready` and is NOT gated on Phase 4 by any task_link (see §5).

---

## 1. Phase 2 gate — DRC reduction to <50 / 0 shorts / 0 clearance

The board Phase 2 was gated on is `tracker/hardware/hub_board_v1_final.kicad_pcb`.
**It does not exist anywhere.** Absence was verified against **all 292 git refs**
(every local branch, every remote branch, every tag under `refs/tags/backup`), and
against every worktree on this machine:

```
git for-each-ref (292 refs) x cat-file -e <ref>:tracker/hardware/hub_board_v1_final.kicad_pcb
  -> no ref contains it
git for-each-ref (292 refs) x cat-file -e <ref>:tracker/hardware/import_tracks_fixed.py
  -> no ref contains it
ls /home/c03rad0r/worktrees/*/tracker/hardware/hub_board_v1_final.kicad_pcb
ls /home/c03rad0r/repos/*/tracker/hardware/hub_board_v1_final.kicad_pcb
ls /home/c03rad0r/.hermes/.worktrees/*/tracker/hardware/hub_board_v1_final.kicad_pcb
  -> empty
```

Ref census (exact, reconciled — `for-each-ref | wc -l` = 292):
`refs/heads` **64**, `refs/remotes` **177**, `refs/tags` **51** (64 + 177 + 51 = 292).

Scope of the absence claim: it covers all **reachable** refs plus the filesystem. The
repository contains **193 dangling/unreachable git objects** (`git fsck --unreachable
--dangling`). Those are not searched by `for-each-ref` and are not claimable as Phase 2
evidence by any normal workflow; `hub_board_v1_final.kicad_pcb` exists in no reachable
ref, no tag, and no worktree on this machine.

Also confirmed: the repo contains **0 `.kicad_pcb` files outside `tracker/hardware`**, so
the 64-board scan in §3c covers every board in the repository.

### The nearest candidate is byte-identical to its pre-Phase-1 committed state

`hub_board_v1_routed.kicad_pcb` — sha256 `bb30f54300714fea27a0f0a7a286539cc1e56bdf738ab51904994c6d8d186279`:

- file sha256 today == file sha256 at commit `882e635` (2026-08-07) → byte-identical
- `git diff HEAD --stat` and `git status --short` for the file: **empty** — no
  uncommitted change has ever landed on it

### Fresh DRC reproduces the plan's documented pre-Phase-1 baseline EXACTLY

Three consecutive `kicad-cli pcb drc --format json` runs returned identical numbers.

| Type | Measured (this run) | Plan §1.3 baseline |
|------|--------------------|--------------------|
| track_dangling | 181 | 181 |
| copper_edge_clearance | 58 | 58 |
| solder_mask_bridge | 33 | 33 |
| lib_footprint_mismatch | 28 | 28 |
| text_height | 25 | 25 |
| text_thickness | 18 | 18 |
| silk_over_copper | **17** | *(omitted from the plan's list)* |
| shorting_items | 15 | 15 |
| silk_overlap | 14 | 14 |
| clearance | 8 | 8 |
| silk_edge_clearance | 5 | 5 |
| lib_footprint_issues | 2 | 2 |
| hole_to_hole | 1 | 1 |
| **TOTAL** | **405** | **405** |
| unconnected | 68 | 68 |

The plan's itemized rows sum to 388, not its stated 405 — the 17-violation gap is
exactly `silk_over_copper`, the one category the plan's list omits (388 + 17 = 405).
That defect *strengthens* the match: with `silk_over_copper` restored, the measurement
reproduces the baseline category-for-category, with no residual.

**Conclusion: Phase 2 performed no work.** The 181 `track_dangling` violations are
precisely the Phase 1 defect (`import_tracks_fixed.py`'s zero-length-track filter) that
Phase 1 existed to fix — and `import_tracks_fixed.py` is absent from all 292 refs too.
Phases 1 and 2 both produced no artifact.

## 2. Phase 4 gate — gerbers + JLCPCB readiness

`PCB_FINAL=hub_board_v1_final.kicad_pcb` and `GERBER_DIR=gerbers_v1_final` are both
absent, in the worktree **and in all 292 refs**:

```
cat-file -e <any of 292 refs>:tracker/hardware/gerbers_v1_final/hub_board_v1_final-F_Cu.gbr
  -> no ref contains it
```

No gerber set in the tree is paired with a PCB-assembly BOM:

- **Whole-repo BOM search** (`find . -iname '*bom*' -o -iname '*.bom'`, excluding `.git`)
  returns exactly **one** hit: `./bom/BOM.md`. That file is a German-language hand-sourcing
  shopping list ("Vorhandene Komponente" / "Noch zu beschaffen - Nach Prioritaet", rows for
  AliExpress/Amazon/LCSC purchases: XIAO ESP32C3 ×20, solar cells ×100, BMP280 breakout,
  protoboard, 30 AWG wire, 100nF caps). It is **not** a per-designator PCB assembly BOM.
- Inside `tracker/hardware`, a BOM search returns **empty**.
- Position/CPL CSVs exist (`gerbers_v1/pos_v1.csv`, `gerbers_f33/pos_f33.csv`,
  `gerbers_v1_fixed/pos_v1_{fixed,orig}.csv`) but no BOM accompanies any of them.

Twelve gerber directories and seven zip sets exist, all from other lanes (V1 / F33 /
V2-ADC / C3), none from this pipeline.

## 3. FALSE-PASS HAZARD — the raw DRC gate is meaningless as specified

This is the most important finding for the board's process, because the gate as written
**passes** on boards that must never be fabricated.

### 3a. A blank board passes the gate with a clean DRC

`tracker/hardware/output/v2_adc_JLCPCB_READY.kicad_pcb` (sha256 `0bccf59f79d897a4…`)
returns, on a fresh `kicad-cli pcb drc` run:

```
violations 0,  unconnected 0
```

and ships a cached sidecar asserting the same. Direct structural inspection:

| Property | Value |
|---|---|
| file size | 2377 bytes |
| footprints | **0** |
| segments / vias / zones | 0 / 0 / 0 |
| declared nets | 1 |
| graphic items | 1 `gr_rect` (Edge.Cuts 50×40) + 1 `gr_text` "Balloon V2-ADC — JLCPCB 2-layer 0.6mm" |

There is nothing to check, so nothing is reported. A `<50 violations, 0 shorts,
0 clearance` gate **PASSES** this file.

### 3b. Worse — the blank board has a full 25-file "JLCPCB-ready" gerber set

`output/gerbers_v2/` contains `v2_adc_JLCPCB_READY-*` gerbers plus a `.gbrjob`:

| File | Size | Apertures | `X`/`Y` draw lines | `D01` draw ops |
|---|---|---|---|---|
| `…-F_Cu.gtl` (top copper) | 480 B | **0** | **0** | **0** |
| `…-B_Cu.gbl` (bottom copper) | 480 B | **0** | **0** | **0** |
| `…-Edge_Cuts.gm1` | 581 B | outline only | — | — |
| `…-F_Silkscreen.gto` | **14561 B** | the title text — the largest file in the set |
| `…-job.gbrjob` | 4320 B | |

The whole body of `…-F_Cu.gtl` between its header and its `M02*` terminator is two lines:

```
G01*
M02*
```

Compare against real copper layers in the same tree:

| Layer | Bytes | Apertures | `X`/`Y` lines | `D01` ops |
|---|---|---|---|---|
| blank `…JLCPCB_READY-F_Cu.gtl` | 480 | 0 | 0 | 0 |
| real `output/gerbers_v_c3/…-F_Cu.gtl` | 11941 | 21 | 228 | 56 |
| real `gerbers_v1/…-F_Cu.gtl` | 15019 | 15 | 419 | 137 |
| real `output/v2_adc_v3_gerbers/…-F_Cu.gtl` | 9767 | 22 | 230 | 78 |

A file set named "JLCPCB_READY", with every manufacturing layer present, an empty
copper stack (no apertures, no coordinates, no draw operations) and a silkscreen
dominated by the board's own name. Anyone validating "are the gerbers present and
non-empty?" would sign this off. Aperture-count and draw-op count are the discriminators;
raw file size is not, because the silkscreen alone is 30× the empty copper layer.

### 3c. Six more boards pass the raw gate while electrically incomplete

Exhaustive scan of all 64 `.kicad_pcb` files in `tracker/hardware` with fresh DRC each —
boards satisfying `<50 violations, 0 shorting_items, 0 clearance-class, fp≥10`:

| Board | fp | viol | shorts | clearance | **unconnected** |
|---|---|---|---|---|---|
| output/v2_2LAYER_FINAL.kicad_pcb | 17 | 1 | 0 | 0 | **16** |
| output/v2_2LAYER_FINISH.kicad_pcb | 17 | 0 | 0 | 0 | **16** |
| output/v2_adc_fixed.kicad_pcb | 17 | 0 | 0 | 0 | **22** |
| output/v2_adc_fixed2.kicad_pcb | 17 | 0 | 0 | 0 | **16** |
| output/v2_adc_routed.kicad_pcb | 17 | 2 | 0 | 0 | **19** |
| output/v2_adc_step1.kicad_pcb | 17 | 0 | 0 | 0 | **47** |

Boards that are **fab-ready** (0 shorts AND 0 clearance-class AND 0 unconnected AND
fp≥10): **NONE**.

**Required guard set for any board gate on this project:** footprint count ≥ 10
(`drc_score.py` already implements this as the `fp < 10 → fab_ready 0` rule with an
`EMPTY/NEAR-EMPTY BOARD` warning) **plus** `unconnected == 0` **plus** non-trivial copper
drawing-command count before any gerber set is called order-ready. The violation count
alone is not a gate. The board's own S4 policy card (t_51d1d219) was written for exactly
this failure mode.

## 4. Task-graph state

- `t_877751ec` (Phase 1) — `ready`; 3 crashed runs (2026-08-05); no artifact in any ref.
- `t_e6dfe4e2` (Phase 2) — `blocked`; marked `completed` 2026-08-05 17:46 with
  `result_len 0`, `summary null` (no gate evidence).
- `t_cca6e387` (Phase 3) — `blocked`.
- `t_745016d5` (Phase 4) — `blocked`; also `completed` 2026-08-05 17:46 with
  `result_len 0`, `summary null`.
- `t_807f52d4` (Phase 5, firmware GPIO) — `ready`, **not linked** to Phase 4. The chain is
  1→2→3→4→6 only.
- `t_e72667d2` (Phase 6, commit/push) — `blocked`.

Every PCB card carries a `gate-tick: BLOCKED (completion-pending)` comment dated
2026-09-28 23:39 naming missing gates: tests_green, pushed_or_consolidated, ci_evidence,
cold_cross_family_review, review_artifact, consolidated, secrets_clean, no_live_drift.

## 5. The pipeline cannot be resumed as written

- Phase 1's input `DSN_ROUTED=/tmp/routed_output.dsn` **no longer exists** (tmp cleared
  after 2026-08-05).
- The manager recorded on both Phase 2 and Phase 4 at 2026-08-05 17:23 — 23 minutes before
  their no-evidence "completion":
  > BLOCKED: superseded by fresh C3 PCB build from schematic

The replacement lane (C3 build from schematic) is itself not fab-ready: the best measured
C3 candidate, `output/v_c3_flight_4layer_routed.kicad_pcb` (sha256 `874cf608c65a`, fp 20),
scores 17 violations / 0 shorts / 3 clearance-class / **20 unconnected** — fab_ready 0.

## 6. Reproduction

```bash
cd ~/worktrees/t_24d9e30c/tracker/hardware
kicad-cli pcb drc --format json --output /tmp/g.json hub_board_v1_routed.kicad_pcb
python3 -c "import json,collections;d=json.load(open('/tmp/g.json'));\
print(len(d['violations']),len(d['unconnected_items']),\
collections.Counter(v['type'] for v in d['violations']))"
# -> 405 68 Counter({'track_dangling': 181, ..., 'shorting_items': 15, 'clearance': 8})

grep -c '(footprint' output/v2_adc_JLCPCB_READY.kicad_pcb   # -> 0 (blank board)
cat output/gerbers_v2/v2_adc_JLCPCB_READY-F_Cu.gtl | grep -c '^X'   # -> 0 (no copper)
sha256sum hub_board_v1_routed.kicad_pcb                      # -> bb30f54300714fea...

# absence across all 292 refs:
cd ~/repos/balloon-fresh
git for-each-ref --format='%(refname)' | while read r; do \
  git cat-file -e "$r:tracker/hardware/hub_board_v1_final.kicad_pcb" 2>/dev/null && echo "PRESENT $r"; done
# -> no output
```

## 7. Scoresheet (drc_score.py metric definition)

| board | sha256 (12) | fp | viol | short | clr | unconn | fab_ready |
|-------|-------------|----|------|-------|-----|--------|-----------|
| hub_board_v1_routed.kicad_pcb | bb30f5430071 | 30 | 405 | 15 | 67 | 68 | 0 |
| hub_board_v1_routed_clean.kicad_pcb | 81390eeee4ee | 30 | 428 | 34 | 124 | 28 | 0 |
| output/v2_adc_JLCPCB_READY.kicad_pcb | 0bccf59f79d8 | **0** | 0 | 0 | 0 | 0 | 0 (EMPTY BOARD) |
| output/v_c3_flight_4layer_routed.kicad_pcb | 874cf608c65a | 20 | 17 | 0 | 3 | 20 | 0 |
| output/v2_adc_v3_clean.kicad_pcb | f96d4a68c240 | 17 | 10 | 5 | 0 | 26 | 0 |
| output/v_c3_flight_v7_routed.kicad_pcb | 347c56a3cfea | 20 | 68 | 17 | 10 | 40 | 0 |

## 8. Recommendations

1. **Do not proceed to Phase 3/4/6 and do not order any board from this pipeline.**
2. **Do not re-run the autoroute pipeline as written** — `/tmp/routed_output.dsn` is gone
   and the plan is superseded by the C3-from-schematic lane.
3. **Operator decision needed:** archive/close the superseded chain (t_877751ec,
   t_e6dfe4e2, t_cca6e387, t_745016d5, t_e72667d2) rather than retrying it.
4. **Wire Phase 5** (`t_807f52d4`) into the graph or archive it — it is `ready` with no
   parent and could fire against a board that does not exist.
5. **Harden the gate spec project-wide.** Replace "violations < 50" with the fab-ready
   conjunction: `fp >= 10 AND shorts == 0 AND clearance-class == 0 AND unconnected == 0`,
   and require a non-empty copper gerber (drawing-command count > 0) plus a per-designator
   assembly BOM before any set is called JLCPCB order-ready.
6. **Quarantine `v2_adc_JLCPCB_READY`.** Its name and its complete gerber set actively
   invite an order for a board with no components and no copper.

## 9. Cold review (Gate 2.5)

Worker family: `tier/coding` (zai proxy). Reviewer pinned to **kimi-k3** — opposite family.
Router and both direct platform keys were down (§10), so the review ran against Ollama
Cloud (`ollama.com/v1`, model `kimi-k3`, `finish_reason: stop`), with all evidence inlined
because that endpoint gives the reviewer no tools.

- **Round 1** — verdict `PARTIAL`. Substantively confirmed all three claims but flagged two
  majors: (a) claim A's "does not exist anywhere" was proven only for two branches;
  (b) claim B's "no gerber set carries a BOM+CPL pair" had no supporting evidence in the
  prompt. Both were legitimate overclaims in the round-1 prompt, not defects in the
  underlying finding. It also raised minors: the plan's itemized baseline sums to 388 vs
  its stated 405; "byte-for-byte" was verified on only 5 metrics; no pre-Phase-1 hash.
- **Round 2** — verdict **`CONFIRMED`** (`gate/ollama_verdict_r2.json`). All three claims
  survived re-attack; every round-1 major is closed by evidence now in §1–§3:
  - absence proven across **all 292 refs** (not two branches) plus the filesystem;
  - **byte-identity** proven — file sha256 == sha256 at commit `882e635` (2026-08-07),
    with `git diff HEAD` / `git status` empty, so the candidate board has not changed
    since before Phase 1;
  - the plan's 388-vs-405 gap arithmetically reconciled: 388 + 17 = 405, where 17 is
    exactly the omitted `silk_over_copper` row — the omission **strengthens** the match
    (reviewer: "a drifted or fabricated baseline would not leave a precisely 17-shaped
    hole");
  - full 13-category breakdown compared, not 5 metrics;
  - blank-board and empty-copper-gerber claims quantified per layer;
  - 64-board scan shown exhaustive (0 boards outside `tracker/hardware`).
  Round 2 left only minors, all now closed in the report: census reconciled
  (64 + 177 + 51 = 292); unreachable-object gap disclosed (193 dangling objects, not
  searchable by ref); board-scan scope proven exhaustive; the `^X` regex criticised as
  possibly evading modal draws — replaced by an aperture/`X`-`Y`/`D01` count that is
  0/0/0, against 15–22 apertures and 228–419 coordinate lines for real boards; and the
  `order-ready` definition tied explicitly to PCBA (per-designator BOM required —
  JLCPCB's tooling cannot synthesise one from a CPL alone, which carries no LCSC part
  numbers).
  Round 2's own residual caveats, stated plainly: `order-ready` is proven under the
  PCBA reading (gerbers + CPL + assembly BOM); under a bare-board-only reading the
  copper/drill validity of the 11 non-blank gerber sets was not individually validated.

**Reviewer model evidence:** `model: kimi-k3`, `finish_reason: stop`,
`usage.completion_tokens` 9457 (round 1) and 15442 (round 2). Raw responses in
`gate/ollama_verdict.json` and `gate/ollama_verdict_r2.json`; prompts in
`gate/review_prompt_grounded.txt` and `gate/review_prompt_round2.txt`; verbatim evidence
bundles in `gate/evidence_*.json`.

Verdicts and raw API responses are preserved in
`gate/ollama_verdict.json` and `gate/ollama_verdict_r2.json`.

## 10. Model routing note (why the reviewer ran off-router)

| Route | Result |
|---|---|
| `hermes --profile kimi-consultant chat -q` (pinned profile) | refused — `active session limit (1/1)`, held by this worker's CLI session |
| local router :9099 `kimi-k3` / `glm-5.2` / `deepseek` | HTTP 200 (router alive) but returns tool-calls, unusable for a tool-less review |
| Chutes `moonshotai/Kimi-K3-TEE` | **402 Payment Required** |
| Moonshot direct (`KIMI_PLATFORM_API_KEY`) | **429** account suspended — insufficient balance |
| z.ai direct (`ZAI_OUR_KEY`) | **429** insufficient balance |
| Ollama Cloud key 2 | **403** subscription past due |
| **Ollama Cloud key 1, `kimi-k3`** | **200 OK — used** |

Disclosure: the reviewer family (Kimi/moonshot) is genuinely opposite to the worker's
tier/coding family, but it did **not** run through the project's normal pinned-profile
route. The verdict is cross-family; it is not profile-pinned.
