# PCB Worker Profile Architecture — Dedicated Spatial-Reasoning Pipeline

> **Status:** Supersedes the ad-hoc `delegate_task` workflow that produced v7.
> **Parent plan:** `PCB-ROUTING-PLAN-v7.md` (board context, KiCad 9 API gotchas, net classification).
> **Mandate (Felix):** Dedicated worker profiles for PCB work using spatial-reasoning
> models. Placement and routing MUST be separate tasks with quality gates between them.
> The **manager** profile does NOT do mechanical PCB work — it delegates everything.

---

## 0. Why This Document Exists

The v7 routing plan was correct *in content* (gates, net classes, trace widths) but
wrong in *execution*. Every prior attempt was an ad-hoc `delegate_task` to `glm-5.2`
with a **300s timeout**, and kimi-class spatial models were never used. The result:

- Repeated 300s timeouts mid-routing → half-written boards, lost work.
- `glm-5.2` is a strong code model but a **weak spatial-reasoning model**. It routed
  blindly, then we spent more turns fixing its crossings/shorts than routing took.
- No quality gate between placement and routing → garbage placement propagated into
  the router, producing DRC lists 100KB long (see `drc_v5_routed.txt`).
- The `output/` directory now contains 30+ intermediate `.kicad_pcb` files with no
  clear lineage — a symptom of un-profiled, un-gated work.

This document fixes all four problems with a **dedicated `worker-pcb` profile** that
runs a **5-task pipeline**, each task isolated, gated, and dispatched to the right model.

---

## 1. Worker Profile Design

### 1.1 Profile Specification

| Field | Value | Rationale |
|-------|-------|-----------|
| **Profile name** | `worker-pcb` | Dedicated profile dir: `~/.hermes/profiles/worker-pcb/` |
| **Primary model (spatial)** | `kimi-k2.7-code` (ollama, local, free) | Placement + routing need geometric reasoning. Kimi has it; GLM does not. |
| **Secondary model (non-spatial)** | `glm-5.2` (z.ai) | DRC parsing, gerber export, JSON/text transforms. GLM is faster + cheaper for these. |
| **Fallback model (spatial)** | `kimi-k3` if/when available on ollama | Same family, larger context. Use only if k2.7 fails a gate twice. |
| **Cheap scratch model** | `glm-4.5-flash` (z.ai) | NOT for board work. Only for parsing DRC text into summaries. |
| **Timeout** | **1800s (30 min)** | Kimi models are slower than GLM. 300s killed every prior kimi attempt. |
| **Role** | `leaf` | Worker never delegates further — it IS the leaf. |
| **Toolsets** | `['terminal', 'file']` ONLY | No web, no MCP servers, no applesauce. Minimizes context, maximizes focus on board ops. |
| **Background** | `true` | Each task runs 10-30 min. Background + `notify_on_complete` so manager is free. |
| **Workdir** | `/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/` | Single source-of-truth for board files. |

### 1.2 Profile Directory Layout

```
~/.hermes/profiles/worker-pcb/
├── SOUL.md            # Identity: "You are a PCB layout worker. Read input board, do ONE task, write output board, report pass/fail."
├── AGENTS.md          # KiCad 9 API gotchas + board constraints + net lists (see §1.3)
└── (no skills, no plugins, no cron — this is a leaf worker)
```

### 1.3 AGENTS.md Content (Worker Knowledge Base)

The worker's `AGENTS.md` MUST contain these three sections verbatim, sourced from
`PCB-ROUTING-PLAN-v7.md`. This is the worker's entire domain knowledge — it has no
memory of prior sessions, so everything it needs must be in this one file.

**A. KiCad 9 API Gotchas** (from v7 plan §"KiCad 9 API Gotchas"):
- `b.Zones()` NOT `b.GetZones()`
- `b.Tracks()` iterator INVALIDATES after `b.Add()`/`b.Remove()` — snapshot upfront
- `SaveBoard(PATH, b)` NOT `b.Save()`
- Zone keepout flags NOT persisted by `SaveBoard` — sed the `.kicad_pcb` directly
- `python3.14` mandatory; `sys.path.insert(0, '/usr/lib/python3/dist-packages')`
- Precompute net codes via `b.GetNetsByNetcode()` before modifications
- `kicad-cli pcb drc --output <file> <board>` for batch DRC (no GUI needed)

**B. Board Constraints** (v3 flight board):
- Board: `v_c3_flight_v5.kicad_pcb` — **80×60mm, 4-layer** (F.Cu / In1.Cu / In2.Cu / B.Cu)
- Stackup: F.Cu → In1.Cu (GND plane) → In2.Cu (+3V3 plane) → B.Cu
- Manufacturer: JLCPCB standard — min drill 0.2mm, min trace 0.127mm
- +3V3 and GND are PLANE nets on In1.Cu/In2.Cu, accessed only via thermal vias
- RF_OUT is HAND-ROUTED microstrip — never autorouted

**C. Net Classification** (from v7 plan §"Net Classification"):

| Category | Nets | Width | Clearance |
|----------|------|-------|-----------|
| Power planes | +3V3, GND | (plane) | thermal vias to In1/In2.Cu |
| Routed power | VCAP, SOLAR_IN | 0.40mm | 0.30mm |
| RF (50Ω) | RF_OUT | 0.35mm* | 0.50mm |
| Signal | SPI_SCK/MISO/MOSI/NSS, I2C_SCL/SDA, GPS_TX/RX, UART0_TX/RX, LED_A, LED_DRIVE, LR_RST, LR_BUSY, LR_DIO0, EN, VDIV_MID | 0.20mm | 0.22mm |
| Power plane vias | — | 0.55mm / 0.30mm drill | thermal relief |

> *RF width must be calculated from stackup, not assumed. Formula:
> `W = (7.48 × h) / (Z₀ × √(εr + 1.41))` — for 0.2mm dielectric, εr=4.4 → ~0.35mm.

---

## 2. Task Decomposition — 5-Task Pipeline

**Hard rule:** Each task is a SEPARATE `delegate_task` dispatch. Each task has:
1. A clearly named **input board** (read-only)
2. A clearly named **output board** (write target)
3. A **pass/fail gate** the worker reports back

The manager dispatches Task N+1 ONLY after Task N's gate passes. If a gate fails,
the manager re-dispatches the SAME task (up to 2 retries) before escalating.

### Pipeline Overview

```
                    Gate A           Gate B           Gate C           Gate D           Gate E
input ─► [Task A] ──PASS──► [Task B] ──PASS──► [Task C] ──PASS──► [Task D] ──PASS──► [Task E] ──PASS──► DONE
  placement         zones+           RF+power        signal           DRC +
  verify            vias             routing         routing          gerbers
   │ FAIL            │ FAIL           │ FAIL          │ FAIL            │ FAIL
   └─ retry x2       └─ retry x2     └─ retry x2     └─ retry x2       └─ escalate
```

### Task A — Placement Verification (kimi-k2.7-code)

| | |
|---|---|
| **Goal** | Verify placement is mechanically AND electrically correct before anything is routed. |
| **Model** | `kimi-k2.7-code` (spatial reasoning for overlap/cap-proximity checks) |
| **Input** | `v_c3_flight_placed.kicad_pcb` (placement-only, no tracks) |
| **Output** | `v_c3_flight_a_verified.kicad_pcb` (placement possibly nudged) |
| **Timeout** | 1800s |
| **What it does** | Runs 7 checks (see Gate A). Moves decoupling caps closer to ICs if proximity fails. Does NOT route. |

### Task B — Zone + Via Placement (kimi-k2.7-code)

| | |
|---|---|
| **Goal** | Add copper zones (GND pour on F.Cu/B.Cu, planes already exist on In1/In2.Cu). Place ALL vias: thermal vias under regulator, GND stitching vias at signal endpoints, RF feed vias. NO trace routing yet. |
| **Model** | `kimi-k2.7-code` (via placement is pure geometry — where to drop a via relative to a pad) |
| **Input** | `v_c3_flight_a_verified.kicad_pcb` |
| **Output** | `v_c3_flight_b_zones_vias.kicad_pcb` |
| **Timeout** | 1800s |
| **What it does** | Adds zones, places vias. Verifies via-to-pad clearance. Does NOT draw traces. |
| **Why split from Task C** | Zones and vias are *placement decisions* that constrain routing. Doing them first lets the router (Task C/D) treat vias as fixed targets. Mixing via-placement into routing is what produced v7's chaos. |

### Task C — RF + Power Routing (kimi-k2.7-code)

| | |
|---|---|
| **Goal** | Hand-route RF_OUT at 50Ω. Route VCAP + SOLAR_IN at 0.4mm. Vias already placed by Task B are targets, not new geometry. |
| **Model** | `kimi-k2.7-code` (microstrip geometry + shortest-path reasoning) |
| **Input** | `v_c3_flight_b_zones_vias.kicad_pcb` |
| **Output** | `v_c3_flight_c_rf_power.kicad_pcb` |
| **Timeout** | 1800s |
| **What it does** | Routes ~5 nets by hand. Verifies widths. Leaves signal nets unrouted (Task D). |

### Task D — Signal Routing (kimi-k2.7-code primary, FreeROUTING fallback)

| | |
|---|---|
| **Goal** | Route all 17 signal nets collision-free. |
| **Model** | `kimi-k2.7-code` (Strategy A: Python collision-aware router). If >2 unconnected remain, fall back to FreeROUTING (Java) — model switches to script-writer mode. |
| **Input** | `v_c3_flight_c_rf_power.kicad_pcb` |
| **Output** | `v_c3_flight_d_routed.kicad_pcb` |
| **Timeout** | 1800s per attempt |
| **What it does** | Strategy A: Python Manhattan router with layer-hopping. Strategy B fallback: export DSN → FreeROUTING → import SES. Fills zones, rebuilds connectivity. |
| **Gate** | Zero crossings, zero shorts, zero unconnected. |

### Task E — DRC Verification + Gerber Export (glm-5.2)

| | |
|---|---|
| **Goal** | Clean DRC, generate gerbers + drill + BOM + step. |
| **Model** | `glm-5.2` (text parsing, CLI orchestration — NOT spatial) |
| **Input** | `v_c3_flight_d_routed.kicad_pcb` |
| **Output** | `v_c3_flight_e_final.kicad_pcb` + `gerbers_v3/` + `v3_board.step` |
| **Timeout** | 900s (GLM is faster; DRC + export is bounded work) |
| **What it does** | Runs `kicad-cli pcb drc`, parses violations. If ANY electrical error → reports FAIL (manager routes back to Task D). If ≤3 cosmetic → accepts. Exports gerbers, drill, step. |
| **Why not kimi** | DRC parsing and gerber export are text/CLI operations. No geometry reasoning needed. GLM does this faster and cheaper. |

---

## 3. Quality Gates (one per task — MUST PASS before next task)

| Gate | After Task | Criteria (ALL must hold) | Fail action |
|------|-----------|--------------------------|-------------|
| **A** | Placement | 1. Zero bbox overlaps between any footprint pair (>0.1mm² = FAIL) · 2. All footprints inside outline with 2mm margin · 3. All different-net pad pairs ≥1.0mm apart · 4. No drill <0.2mm · 5. Every IC (U1-U5) has a decoupling cap within 5mm on its VCC net · 6. Polarized parts oriented correctly (LED, diode, electrolytic band, IC pin-1) · 7. J1/J2/SOLAR reach board edge correctly | Re-dispatch Task A (move caps closer). Max 2 retries. |
| **B** | Zones+Vias | 1. GND zones filled on F.Cu + B.Cu · 2. ≥4 thermal vias under regulator (U4) to In1.Cu · 3. ≥2 GND stitching vias flanking RF_OUT feed point within 1mm · 4. GND stitching via at each SPI/I2C/UART endpoint pad · 5. All vias clear of pads by ≥0.2mm · 6. Zone fill has no islands | Re-dispatch Task B. Max 2 retries. |
| **C** | RF+Power | 1. RF_OUT trace width = calculated 50Ω value (not default) · 2. VCAP/SOLAR_IN traces ≥0.4mm · 3. ≥4 thermal vias confirmed under regulator · 4. RF feed vias confirmed flanking · 5. No power trace crosses an existing via | Re-dispatch Task C. Max 2 retries. |
| **D** | Signal routing | 1. Zero `tracks_crossing` · 2. Zero `shorting_items` · 3. Zero `solder_mask_bridge` · 4. Zero `unconnected_items` (tightened — NO "hand-route later") · 5. ≤3 dangling power vias acceptable (if zone fill connects them) | Re-dispatch Task D, then escalate to FreeROUTING fallback. Max 2 retries on Strategy A. |
| **E** | DRC + gerbers | 1. Zero electrical DRC errors · 2. ≤3 cosmetic warnings (silk/courtyard OK) · 3. Zero unconnected · 4. Gerbers generated (`*.gtl`, `*.gbl`, `*.drl` present) · 5. Step file generated for enclosure fit check | If electrical error → back to Task D. If export error → fix CLI args (Task E retry). |

**Gate enforcement is the manager's job, not the worker's.** The worker reports
PASS/FAIL with evidence (DRC counts, via counts). The manager reads the report and
either dispatches the next task or retries.

---

## 4. Model Selection Rationale

### 4.1 Why `kimi-k2.7-code` for Spatial Tasks (A, B, C, D)

- **Geometric reasoning.** Placement and routing require reasoning about 2D
  coordinates, bounding-box intersection, clearance distances, and shortest paths.
  Kimi (Moonshot) was trained with strong spatial/visual priors; GLM was not.
  Prior v7 attempts used GLM for routing and produced 100KB DRC error files full of
  crossings — a direct failure of geometric reasoning.
- **Free + local (ollama).** No token cost, no rate limit. The only cost is wall-time,
  which the 1800s timeout accommodates.
- **Code-fluent.** The `-code` variant writes correct KiCad `pcbnew` Python. It can
  both reason about geometry AND emit the script to implement it.

### 4.2 Why `glm-5.2` for Non-Spatial Tasks (E, and reviews)

- **No geometry needed.** DRC parsing (`grep` over `drc.txt`), gerber export
  (`kicad-cli pcb export gerbers`), BOM generation — these are text/CLI tasks. Spatial
  reasoning is wasted compute here.
- **Faster + cheaper.** GLM completes a DRC parse + gerber export in 60-120s vs
  kimi's 10-20 min. Use the right tool for the job.
- **Better at structured text.** GLM reliably produces well-formed JSON DRC summaries
  and parses `kicad-cli` stderr correctly.

### 4.3 Cross-Family Review (Defense in Depth)

**Never let a model self-approve its own work.** After each spatial task (kimi) passes
its gate, the manager dispatches a **lightweight GLM review**; after each non-spatial
task (GLM) passes, a **lightweight kimi review**.

| Work done by | Reviewed by | What the reviewer checks |
|--------------|-------------|--------------------------|
| Kimi (Tasks A-D) | GLM (review dispatch) | Parses DRC output, counts vias from file, verifies width values numerically. Catches "kimi said PASS but DRC shows 12 shorts." |
| GLM (Task E) | Kimi (review dispatch) | Visually/geometrically verifies gerber layer count, drill file via count matches board via count. Catches "GLM exported gerbers but skipped In2.Cu." |

These reviews are **read-only** (model reviews, does not write). They run at 900s
timeout and cost only one extra dispatch per task. The cost of shipping a bad board
to JLCPCB dwarfs it.

---

## 5. How to Dispatch (Manager → Worker)

### 5.1 Dispatch Signature

```python
delegate_task(
    model='kimi-k2.7-code',        # or 'glm-5.2' for Task E
    role='leaf',
    toolsets=['terminal', 'file'], # NOTHING else — no web, no mcp, no applesauce
    background=True,               # 1800s tasks MUST be background
    notify_on_complete=True,       # manager freed until notified
    profile='worker-pcb',          # dedicated profile with AGENTS.md
    timeout=1800,                  # 30 min for kimi; 900 for GLM Task E
    workdir='/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output',
    prompt="""<task-specific prompt — see §5.2>"""
)
```

### 5.2 Task Prompt Template (each dispatch fills this in)

```
TASK: <Task A | B | C | D | E>

INPUT BOARD (read-only): <input_filename>.kicad_pcb
OUTPUT BOARD (write):    <output_filename>.kicad_pcb

YOUR JOB:
<2-3 sentences describing exactly what to do>

CONSTRAINTS:
- Use python3.14 with sys.path.insert(0, '/usr/lib/python3/dist-packages')
- Load with pcbnew.LoadBoard(), save with pcbnew.SaveBoard(PATH, b)
- Snapshot b.Tracks() before any Add/Remove (iterator invalidates)
- <net-specific constraints for this task>

PASS CRITERIA (report each as PASS/FAIL with a number):
1. <gate criterion 1>
2. <gate criterion 2>
3. ...

REPORT BACK:
- Overall: PASS or FAIL
- If FAIL: which criterion failed and the count
- Output board path (must exist and be loadable)
- Do NOT proceed to the next task. Stop after writing the output board and reporting.
```

### 5.3 Manager Workflow (the ONLY thing manager does for PCB)

```
1. Dispatch Task A (kimi, bg) → wait for notify
2. Read Task A report
   - PASS → dispatch Gate A review (GLM, read-only, bg) → wait
     - review confirms → dispatch Task B
     - review disputes → re-dispatch Task A (retry 1/2)
   - FAIL → re-dispatch Task A (retry 1/2)
3. [repeat for B, C, D]
4. Dispatch Task E (GLM, bg) → wait
5. Read Task E report
   - PASS → dispatch Gate E review (kimi, read-only, bg) → wait
     - review confirms → board is DONE, gerbers ready
     - review disputes → re-dispatch Task E or route back to D
6. If any task fails 3x (2 retries + 1 review dispute) → STOP, escalate to Felix.
```

**The manager never opens `pcbnew`, never writes a `.kicad_pcb`, never runs a router
script.** It only reads worker reports and dispatches the next task.

---

## 6. Current State + Resume Plan

As of this writing, the board lineage under ad-hoc v7 is:

| v7 phase | Status | Equivalent in new pipeline |
|----------|--------|---------------------------|
| Phase 0 (placement) | DONE | = **Task A passed** (cap proximity was the v7 fix that made it pass) |
| Phase 1A (RF+power+thermal vias) | DONE | ≈ **Task B + Task C** combined — but zones and vias were not cleanly separated |
| Phase 1B (signal routing) | In progress (dispatched to glm-5.2, likely to timeout at 300s) | = **Task D** |

**Resume recommendation:** Do NOT continue the ad-hoc Phase 1B dispatch. Instead:

1. Take `v_c3_flight_rf_power.kicad_pcb` (the current best, with placement + RF/power
   + thermal vias) as the **input to Task D** (signal routing), since Tasks A-C are
   effectively already done.
2. Copy it to `v_c3_flight_d_routed_input.kicad_pcb` and dispatch Task D with kimi at
   1800s timeout.
3. If Task D's gate (zero crossings/shorts/unconnected) passes → proceed to Task E.
4. For the **next board revision** (or if Task D reveals placement problems), run the
   full 5-task pipeline from scratch with proper `worker-pcb` profiling.

This gets a clean board to gerber stage fastest while not repeating the
ad-hoc-on-ad-hoc pattern that created the fragmented `output/` directory.

---

## 7. Quick Reference — Dispatch Cheat Sheet

```python
# Task A: Placement verification
delegate_task(model='kimi-k2.7-code', role='leaf', profile='worker-pcb',
    toolsets=['terminal','file'], background=True, notify_on_complete=True,
    timeout=1800, workdir='.../output',
    prompt="TASK A: verify placement of v_c3_flight_placed.kicad_pcb → "
           "v_c3_flight_a_verified.kicad_pcb. <gate A criteria>. Report PASS/FAIL.")

# Task B: Zones + vias
delegate_task(model='kimi-k2.7-code', ..., timeout=1800,
    prompt="TASK B: add zones + place all vias on v_c3_flight_a_verified.kicad_pcb → "
           "v_c3_flight_b_zones_vias.kicad_pcb. NO traces. <gate B criteria>.")

# Task C: RF + power routing
delegate_task(model='kimi-k2.7-code', ..., timeout=1800,
    prompt="TASK C: route RF_OUT (50Ω) + VCAP/SOLAR_IN (0.4mm) on "
           "v_c3_flight_b_zones_vias.kicad_pcb → v_c3_flight_c_rf_power.kicad_pcb. "
           "<gate C criteria>.")

# Task D: Signal routing
delegate_task(model='kimi-k2.7-code', ..., timeout=1800,
    prompt="TASK D: route all 17 signal nets on v_c3_flight_c_rf_power.kicad_pcb → "
           "v_c3_flight_d_routed.kicad_pcb. Strategy A: Python Manhattan router. "
           "Fallback: FreeROUTING DSN→SES. <gate D criteria>.")

# Task E: DRC + gerbers (GLM, shorter timeout)
delegate_task(model='glm-5.2', role='leaf', profile='worker-pcb',
    toolsets=['terminal','file'], background=True, notify_on_complete=True,
    timeout=900, workdir='.../output',
    prompt="TASK E: run DRC + export gerbers on v_c3_flight_d_routed.kicad_pcb → "
           "v_c3_flight_e_final.kicad_pcb + gerbers_v3/ + v3_board.step. "
           "<gate E criteria>.")
```

---

## 8. Failure Modes This Prevents

| Old ad-hoc failure | How this architecture prevents it |
|--------------------|-----------------------------------|
| 300s timeout mid-routing | 1800s timeout + background + notify_on_complete |
| GLM routes blindly → 100KB DRC errors | Kimi does spatial tasks; GLM only does text/CLI |
| No gate between placement and routing | 5 gates, manager-enforced, each task isolated |
| 30+ fragmented board files in `output/` | Strict input→output naming per task; manager tracks lineage |
| Half-written boards from killed dispatches | Each task is self-contained: read one board, write one board, report |
| Model self-approves its own mistakes | Cross-family review: kimi↔GLM checks |
| Manager wastes context on mechanical PCB work | Manager only reads reports + dispatches; never touches pcbnew |
