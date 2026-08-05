# Consultant Revised Plan V2 — Post Model-Selection Learnings

**Reviewer:** Senior systems consultant (subagent)
**Date:** 2026-08-05
**Branch reviewed:** `autonomous/mesh-baseline` @ `89a4672`
**Supersedes:** `CONSULTANT-STRATEGIC-REVIEW.md` (model-agnostic) and the
worker-assignment section of `PCB-MASTER-EXECUTION-PLAN.md`
**Informs:** `PCB-MODEL-LESSONS-LEARNED.md` (companion — correct on model
selection, but its "C3 schematic exists" claim is the new show-stopper)

**Method:** Read all five context docs. Independently verified against the
repo: ran `kicad-cli sch erc` on the supposed-working C3 schematic, queried
the kanban DB for the actual status of tasks `t_157df236` / `t_10ec390b` /
`t_e2842b80`, diffed `worker-layout/config.yaml` against `profile.yaml` and
`MEMORY.md`, audited the hardware directory (39 `.kicad_pcb`, 3 `.kicad_sch`),
and walked the last 20 commits.

---

## TL;DR — THE BRUTALLY HONEST VERSION

**The model-selection pivot was correct in direction and is being executed on
a broken artifact.** GLM 5.2 is the right tool and the two-stage workflow is
the right design. But the "C3 schematic exists, 121KB, 113 symbols" claim —
the single piece of evidence cited as proof that the new approach is working —
**does not load in kicad-cli 9.0.8.** I ran the same ERC command the master
plan specifies as Gate 1:

```
$ kicad-cli sch erc --format json -o /tmp/c3_erc.json \
    tracker/hardware/schematics/v_c3_flight.kicad_sch
Failed to load schematic
$ echo $?
3
```

This is the *exact same failure mode* as the 33 script-generated PCBs: a large
text file that looks like a KiCad artifact and is not. The header claims
`(generator_version "9.0")` and the bytes are syntactically S-expression, but
KiCad's loader rejects it. Until this is fixed, **the two-stage workflow has
no Stage 1 input.** Every task downstream of "schematic exists" is building on
sand.

Two other findings below materially change the plan. Read all three before
re-dispatching anything.

---

## THE THREE NEW SHOW-STOPPERS

### 🚨 #1 — The "Working" C3 Schematic Does Not Load

- File: `tracker/hardware/schematics/v_c3_flight.kicad_sch` (121,539 bytes,
  4,477 lines, committed at `18529e6`)
- `kicad-cli sch erc` → `Failed to load schematic`, exit 3
- `kicad-cli sch export netlist` → also fails (verified in the
  `t_157df236` log)
- The `PCB-MODEL-LESSONS-LEARNED.md` doc and the kanban task descriptions both
  treat this file as a validated input. It is not.

**Implication:** The currently-running task `t_10ec390b` ("C3-STAGE1: Build
4-layer ESP32-C3 board (GLM 5.2 + DRC protection prompt)") is consuming a
schematic that cannot be netlisted. It will either (a) hand-parse the S-expr
and reconstruct the netlist itself — recreating the exact failure mode that
produced 33 broken PCBs — or (b) fail. **There is no path from this schematic
to a loadable PCB without first fixing or regenerating the schematic.**

**Root cause hypothesis (not yet confirmed):** GLM 5.2 can emit KiCad-shaped
text but is missing something the loader requires — most likely a malformed
`symbol`/`lib_symbols` block, a dangling UUID reference, or a missing
`.kicad_pro`/sheet linkage. The file is 121KB of *plausible-looking* content
that fails strict parsing. This is the text-model failure mode the
lessons-learned doc warned about for *PCBs* — it has now shown up in
*schematics*.

**This does not invalidate the GLM 5.2 finding.** It means GLM 5.2 needs the
same kind of guardrail for schematics that the DRC-protection prompt provides
for PCBs: a "load-or-die" gate that runs `kicad-cli sch erc` and refuses to
proceed on a non-zero exit.

### 🚨 #2 — Role Configuration Is Contradictory Across Three Sources

Three different documents disagree on which profile does what:

| Source | worker-layout model | worker-layout role |
|--------|---------------------|--------------------|
| `profile.yaml` | `kimi-k3:cloud` | "PCB Layout Worker (kimi-k3)" |
| `config.yaml` | `glm-5.2` (zai) | (active runtime config) |
| `MEMORY.md` entry 1 | — | "S2=Kimi K2.7 (worker-layout, local) visual verify" |
| `MEMORY.md` entry 2 | — | "worker-layout=Kimi K2.7 verify" |
| Kanban `t_10ec390b` | — | worker-layout doing GLM 5.2 *generation* |

The runtime is using `config.yaml` (GLM 5.2 generation on worker-layout), but
`profile.yaml` still advertises kimi-k3:cloud and `MEMORY.md` says
worker-layout is the *visual verifier*. Meanwhile `worker-balloon` is named in
`MEMORY.md` as the GLM 5.2 generator but is not assigned any active task.

**Implication:** If Felix (or the manager, or a future agent) reads any of the
stale sources, they will dispatch work to the wrong profile or the wrong model.
The kimi-k3:cloud entry in `profile.yaml` is a landmine — anyone who copies
that profile as a template inherits a dead model.

### 🚨 #3 — Task `t_157df236` Was Marked "done" Without Producing a PCB

- Status in kanban DB: `done`
- Summary field: empty
- Workspace dir: does not exist (`workspaces/t_157df236/` — No such file)
- Log shows the agent struggling to export a netlist, hitting spurious
  `write_file` errors, and falling back to hand-parsing the S-expr
- No new `.kicad_pcb` was committed as a result of this task

**Implication:** "Done" in the kanban currently means "the agent stopped
running," not "the deliverable was produced and verified." This is the same
measurement failure that let the team report "DRC clean, fabrication ready" on
empty boards. The gate definitions in `PCB-MASTER-EXECUTION-PLAN.md` are
correct on paper; they are not being enforced at task-close time.

---

## WHAT THE MODEL-SELECTION WORK GOT RIGHT

To be fair — and this is important, because the previous strategic review was
skeptical of the model-routing pivot — several things are genuinely better now
than 24 hours ago:

1. **Direction is correct.** GLM 5.2 is cheaper, available, and
   text/math-strong. Kimi K3 was down and overpriced for the actual workload.
   The cost table in `PCB-MODEL-LESSONS-LEARNED.md` is accurate.
2. **The two-stage workflow design is sound.** Generate-with-GLM →
   verify-with-vision is a legitimate industry pattern (separation of authoring
   and review). The Kanban already reflects this: `t_10ec390b` (Stage 1 GLM
   gen) → `t_e2842b80` (Stage 2 Kimi verify) is queued as a dependency chain.
3. **The DRC-protection system prompt in `worker-layout/SOUL.md` is the right
   kind of intervention.** It forces coordinate math before code emission. This
   is exactly the "constraint-based generation" approach that works for
   non-multimodal models.
4. **The pre-dispatch model-health checklist is correct and was missing
   before.** (`curl /v1/chat/completions` with a trivial payload before
   dispatching.) This alone would have saved the 8 hours.
5. **The cost-aware fallback hierarchy (GLM 5.2 → DeepSeek V4 Pro → Kimi K2.7
   for review) is well-reasoned.**

The model story is good. The *execution* of the model story is not, because
the artifact being fed in is broken and the verification gates are not
enforced.

---

## THE REVISED TWO-STAGE WORKFLOW

The lessons-learned doc sketches this; below is the **enforced** version with
the missing "Stage 0" and the gate that closes the measurement loophole.

```
┌─────────────────────────────────────────────────────────────────────┐
│ STAGE 0 — Schematic Integrity (NEW, MANDATORY)                      │
│   owner: worker-layout (GLM 5.2)                                    │
│   input: GPIO netlist from schematic-task-context.md                │
│   output: v_c3_flight.kicad_sch that LOADS in kicad-cli             │
│   GATE 0: `kicad-cli sch erc` exits 0 (file parses)                 │
│           AND `kicad-cli sch export netlist` produces non-empty .net│
│   This gate did not exist before. The current schematic fails it.   │
└─────────────────────────────────────────────────────────────────────┘
                              │ (gate must pass)
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STAGE 1 — Generate PCB (GLM 5.2)                                    │
│   owner: worker-layout (GLM 5.2, DRC-protection prompt active)      │
│   input: validated .kicad_sch + .kicad_pro + .net                   │
│   output: v_c3_4layer.kicad_pcb with >10 footprints                 │
│   GATE 3: footprint count > 10 (catches empty-PCB regression)       │
│   GATE 4: `kicad-cli pcb drc` = 0 violations, 0 unconnected         │
│   tool: pcbnew Python API + Freerouting SES import (per SOUL.md)    │
└─────────────────────────────────────────────────────────────────────┘
                              │ (gate must pass)
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STAGE 2 — Visual Review (Kimi K2.7, when available)                 │
│   owner: worker-layout (or a dedicated worker-reviewer profile)     │
│   model: kimi-k2.7 local (NOT k3:cloud — overkill, $15/M vs $4/M)   │
│   input: rendered gerber PNGs from Stage 1 output                   │
│   output: SIGNOFF-c3.md with PASS/FAIL + issue list                 │
│   GATE 5: gerbers exist, F_Cu + B_Cu > 1KB                          │
│   GATE 6: 0.6mm thickness present in PCB file                       │
│   note: Stage 2 is advisory — if Kimi is down, Stage 1 gates still  │
│         unblock ordering. Do NOT block on visual review.            │
└─────────────────────────────────────────────────────────────────────┘
```

**Key changes from the lessons-learned version:**

1. **Stage 0 is new and mandatory.** It exists solely to catch the failure I
   found: a schematic that looks done but won't load. No Stage 1 task may be
   dispatched until Stage 0 passes. The current `t_10ec390b` should be
   cancelled and re-dispatched as a Stage 0 task.
2. **Stage 2 is advisory, not blocking.** Kimi availability is intermittent.
   The hard quality gates (ERC load, DRC clean, gerbers non-empty) are all
   deterministic and CLI-checkable. Visual review adds value but must not be
   on the critical path.
3. **One profile, one model, one role.** worker-layout = GLM 5.2 =
   generation + integrity gates. Visual review can be a separate dispatch to
   the same profile with a different model override, or a new
   `worker-reviewer` profile. Stop the role flip-flopping.

---

## DIRECT ANSWERS TO FELIX'S EIGHT QUESTIONS

### Q1. What is the revised lowest-hanging fruit now that we know GLM 5.2 works?

**Fix or regenerate the C3 schematic so it loads in kicad-cli.** This is 30
minutes of work and unblocks everything else. Until `kicad-cli sch erc` exits
0 on `v_c3_flight.kicad_sch`, the GLM 5.2 validation is theoretical — no
loadable schematic has ever been produced by any model on this project.

Concretely, in priority order:

1. **Run `kicad-cli sch erc` on the current schematic and capture the actual
   parse error.** (The CLI says "Failed to load schematic" but KiCad's stderr
   in verbose mode usually names the offending token. Get that string.)
2. **Either patch the offending block by hand, or regenerate the schematic
   from scratch with GLM 5.2** using a tighter prompt: "Emit a KiCad 9.0
   schematic. After writing, run `kicad-cli sch erc` yourself. If it fails,
   read the error and fix the file. Do not return until exit code is 0."
3. **Update `PCB-MODEL-LESSONS-LEARNED.md` to retract the "C3 schematic
   exists" claim** until Stage 0 passes. Right now that doc is misleading.

This is *lower*-hanging than the breadboard validation from the previous
review because it's a single file fix, not a hardware session. But the
breadboard validation (Q6) remains the highest-*leverage* action for actually
flying.

### Q2. What are the immediately actionable steps?

**Today (no hardware, ~2 hours):**

| Step | Owner | Time | Why |
|------|-------|------|-----|
| 1. Diagnose why `v_c3_flight.kicad_sch` fails to load | Felix or worker-layout | 20 min | Establishes whether GLM 5.2 can produce loadable schematics at all |
| 2. Cancel `t_10ec390b`; re-dispatch as Stage 0 (schematic integrity) | manager | 5 min | Stops burning GLM tokens on a broken input |
| 3. Reconcile `profile.yaml` / `config.yaml` / `MEMORY.md` on worker-layout's role | Felix | 10 min | Removes the dispatch landmine |
| 4. Add Gate 0 (`kicad-cli sch erc` exit 0) to the master execution plan | manager | 10 min | Prevents the next "done with no deliverable" |
| 5. Add task-close verification: a task is not `done` until its declared output file exists and passes its gate | Felix (process) | 30 min | Closes the measurement loophole from show-stopper #3 |

**This week:**

| Step | Owner | Time |
|------|-------|------|
| 6. Breadboard: LR2021 ↔ ESP32-S3 (per previous review — still the highest-leverage hardware action) | Felix | 30 min |
| 7. Flash tracker firmware, confirm SPI chip ID over a real LR2021 | Felix | 1 hr |
| 8. Once Stage 0 passes: dispatch Stage 1 (PCB generation) on GLM 5.2 | manager | background |
| 9. Once Stage 1 passes Gate 4: export gerbers, eyeball in a gerber viewer | Felix | 15 min |

### Q3. How should the PCB pipeline change given the model findings?

Five concrete changes, in order of importance:

1. **Add Stage 0 (schematic integrity gate).** Described above. This is the
   single most important change — it would have caught today's failure
   instantly.
2. **Enforce task-close verification.** A kanban task moving to `done` must
   have its declared output artifact present and gate-passing. Today
   `t_157df236` is `done` with no output and no workspace — that should be
   impossible. Add a `verify_on_close` field to task templates that runs the
   gate command.
3. **Lock worker-layout to one model and document it everywhere.** Update
   `profile.yaml` to match `config.yaml` (glm-5.2). Delete the kimi-k3:cloud
   reference — it's a dead model and a stale advertisement. Update the two
   contradictory `MEMORY.md` entries to a single canonical line.
4. **Make Stage 2 (visual review) advisory and optional.** Do not gate
   ordering on Kimi availability. Kimi K2.7 local is a nice-to-have review
   pass; the deterministic gates do the real work.
5. **Stop generating board variants in parallel.** The master plan's
   strict-serial 3-variant chain (C3 → S3 → C3+RP2040) is correct. Do not let
   a worker start S3 until C3 passes Gate 6. The 33-variant mess came from
   uncontrolled parallel generation.

### Q4. Is the C3 PCB task running on glm-5.2 likely to succeed now?

**No. Not as currently scoped.** The running task `t_10ec390b` is consuming
the non-loadable schematic. It will either:

- Hand-parse the S-expr to reconstruct the netlist (recreating the
  script-generated-netlist failure mode that produced 33 broken boards), or
- Fail to netlist and produce an empty/partial PCB.

**It is likely to succeed after Stage 0 passes.** GLM 5.2 with the
DRC-protection prompt and a *loadable* schematic input is a reasonable bet —
but it has not yet been proven end-to-end on this project. The honest answer
is: we have validated the *approach* (model + prompt + toolchain) but not the
*artifact* (a Stage-1-passing PCB). Cancel `t_10ec390b`, fix the schematic,
then re-dispatch.

### Q5. Should we abandon the schematic-first approach or continue it?

**Continue it. Emphatically.** Schematic-first is correct and was the right
call in ADR-028. The problem is not the approach — it's that the schematic was
never verified to load. The fix is Gate 0, not a different approach.

The one nuance: "schematic-first" means *a schematic that passes ERC*, not "a
file with a `.kicad_sch` extension." The previous workflow failed because it
skipped the schematic entirely (script-generated PCBs). The current workflow
is failing because it has a schematic-shaped file that isn't a schematic. Both
are the same underlying bug: **no integrity gate between "file exists" and
"file is valid."**

Do not abandon schematic-first. Add Gate 0 and enforce it.

### Q6. What's blocking a real flight test?

In order of severity, updated from the previous review:

1. **No validated radio link on hardware.** (Unchanged from previous review,
   still #1.) 22K lines of firmware, zero confirmed packets over a real
   LR2021. Breadboard it. This is independent of the PCB pipeline — you can do
   it today with dev boards you already own.
2. **No loadable schematic → no PCB.** (New, was implicit before.) Even with
   the model pivot, no PCB can be ordered until a schematic passes Gate 0 and
   a PCB passes Gate 4. Current ETA: depends on Stage 0 fix (hours) + Stage 1
   generation (1–3 worker attempts).
3. **MCU decision drift.** (Unchanged.) The firmware is S3; the schematic is
   C3; ADR-028 says C3 is P0. Either commit to C3-and-port-the-firmware or
   commit to S3-and-redesign-the-board. The previous review recommended S3
   because the firmware investment is in S3. That recommendation stands
   unless Felix has a strong reason for C3 (weight, power). **Decide this
   week.**
4. **JLCPCB lead time (2 weeks).** Starts the day a Gate-5-passing gerber set
   exists. Every day of delay = +1 day to flight.
5. **No GPS / solar / supercap bench time.** (Unchanged.) Lower risk than
   radio but shouldn't be first-flighted cold.

Notably **not** on the blocker list, same as before: 4-layer vs 2-layer
optimization, FIPS mesh, Cashu integration, secp256k1 on RX, the C3+RP2040
dual-MCU variant. All V2+.

### Q7. What would a realistic timeline look like now?

The previous review estimated 7–10 weeks to first flight assuming a pivot to
breadboard validation. That estimate **still holds** and is not improved by
the model-selection pivot, because the model pivot has not yet produced a
usable artifact. GLM 5.2 *might* shorten the PCB-generation portion of the
timeline once Stage 0 is fixed — but the PCB was never the long pole. The
radio validation and the JLCPCB lead time are the long poles, and neither is
affected by model choice.

Revised timeline, assuming Felix acts on this review **today**:

| Week | Milestone | Deliverable | Confidence |
|------|-----------|-------------|------------|
| **1** (now) | Schematic fixed + radio validated | Stage 0 passes; LR2021 wired to S3, SPI chip ID confirmed; MCU decision committed in writing | High |
| **2** | PCB generated + ordered | Stage 1 passes Gate 4 (DRC clean); gerbers exported; JLCPCB order placed (~$12–16). Breadboard relay-mode testing in parallel. | Medium — depends on GLM 5.2 producing a loadable PCB on first or second attempt |
| **3–4** | JLCPCB lead time (parallel) | Breadboard: GPS fix, solar→supercap→LDO chain, telemetry format, neighborhood range test | High |
| **4–5** | PCB arrives, assemble, bench test | Solder, power up, confirm radio + GPS + power on flight board | Medium |
| **5–6** | Integration + ground range test | Full system: GPS → LoRa TX → ground RX. km-scale range test. Weight check (<9g). | Medium |
| **6–8** | First flight | Balloon prep, leak test, He fill, launch | Medium-low (weather-dependent) |

**Realistic: 7–10 weeks to first flight.** This is unchanged from the previous
review. The model pivot is a process improvement, not a schedule accelerant —
do not let the "GLM 5.2 works!" narrative create a false sense of velocity.
The schedule is gated by hardware lead times and hardware validation, neither
of which a model choice changes.

### Q8. Should we use DeepSeek V4 Pro as a budget option?

**Not yet. Not as the primary generator.** Reasoning:

- DeepSeek V4 Pro at $0.87/M output is ~5× cheaper than GLM 5.2 ($4.40/M).
  For a high-volume production pipeline this matters.
- But you are generating **one board, three times** (C3, S3, C3+RP2040). The
  total token cost difference between GLM 5.2 and DeepSeek for three boards is
  on the order of $1–3. That is rounding error relative to the JLCPCB order
  and the value of your time.
- GLM 5.2 is *validated in direction* (per the lessons-learned research).
  DeepSeek V4 Pro is not yet validated on this project at all. Switching to an
  unvalidated cheaper model to save $2 is a false economy if it produces a
  broken board and costs you a 2-week lead time.

**Use DeepSeek V4 Pro as a fallback only**, in this priority:

1. GLM 5.2 (primary — validated direction, available now)
2. DeepSeek V4 Pro (fallback if GLM 5.2 quota exhausts or degrades)
3. Kimi K2.7 local (visual review only — not for generation)

Revisit DeepSeek as primary **only after** you have a proven Stage-0→Stage-1
pipeline on GLM 5.2 and want to cost-optimize for volume. You are not at
volume. You are at one board.

---

## PROCESS CORRECTIONS (CARRY FORWARD FROM PREVIOUS REVIEW)

These remain in force and are not negated by the model pivot:

1. **Schematic-first, always.** (ADR-028 — correct. Add Gate 0.)
2. **One board file at a time.** Delete the other 38 `.kicad_pcb` variants.
   Keep git history. (Previous review said delete 32; the count is now 39.)
3. **Hand-route small boards if automation fails.** 17 components is an
   evening's work in the KiCad GUI. Automation is a bonus, not a dependency.
4. **Breadboard before PCB.** Still the highest-leverage validation action.
5. **One MCU. One firmware. One board.** For V1. Decide this week.
6. **Verify, don't narrate.** The "C3 schematic exists" claim in
   `PCB-MODEL-LESSONS-LEARNED.md` was not verified against `kicad-cli`. The
   "DRC clean, fabrication ready" claims on empty boards were not verified
   against footprint counts. Same failure mode, twice. **Every status claim
   must be backed by a CLI exit code or a file inspection, not an agent's
   self-report.**

---

## THE BOTTOM LINE

The model-selection pivot was the right call. GLM 5.2 is cheaper, available,
and theoretically better-suited to constraint-based PCB generation than the
dead kimi-k3:cloud. The two-stage workflow is a sound design. Felix's research
was good.

**But the pivot is being executed on a broken artifact, and the verification
gates that would have caught it are not enforced.** The "C3 schematic exists"
claim is false in the only way that matters — it does not load. The
"done" task produced no PCB. The profile configuration contradicts itself
across three files.

These are all the same disease: **status is being narrated rather than
verified.** The fix is not another model. The fix is Gate 0 (schematic loads),
task-close verification (output exists), and configuration reconciliation
(one profile, one model, one documented role).

Fix the schematic today. Breadboard the radio this week. The PCB pipeline
becomes real the moment a GLM-5.2-produced artifact passes a deterministic
gate for the first time. Until then, the model pivot is a hypothesis — a good
hypothesis, but unproven on this project.

**7–10 weeks to first flight, unchanged. The bottleneck is hardware
validation and lead time, not model selection.**

---

*Review prepared by independent consultant subagent. All claims verified
against repository contents at commit `89a4672` on 2026-08-05. Schematic ERC
run live via `kicad-cli 9.0.8` (exit 3). Kanban task status queried directly
from `~/.hermes/kanban/boards/balloon/kanban.db` via sqlite3 Python binding.
Profile configuration cross-checked across `profile.yaml`, `config.yaml`, and
`MEMORY.md`. No claims derived from agent self-reports without independent
verification.*
