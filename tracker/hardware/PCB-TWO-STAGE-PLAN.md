# PCB TWO-STAGE EXECUTION PLAN — GLM 5.2 Generate + Kimi K2.7 Verify

**Date:** 2026-08-05
**Author:** worker-balloon (PCB consultant)
**Supersedes:** `PCB-EXECUTION-PLAN.md` (kimi-k3:cloud author — quota exhausted, model replaced)
**Related:** ADR-028 (Three-Variant PCB Design), ADR-026 (Dual-MCU), `full_pipeline.py`, `tracker/firmware/main/app_main.cpp`

---

## 0. WHY THIS REPLACES THE PRIOR PLAN

The kimi-k3:cloud-backed plan (`PCB-EXECUTION-PLAN.md`) is **non-executable**:

- kimi-k3:cloud quota is exhausted; the model is unreachable for the foreseeable future.
- An empty "4-layer" board was previously committed because kimi-k3:cloud was **silently failing** — this is the failure mode the two-stage pipeline is explicitly designed to catch.
- Research shows **GLM 5.2 is better than Kimi for programmatic PCB design** (Python + pcbnew API): superior mathematical coordinate reasoning, constraint satisfaction, and 1M-token context for full-pin-list reasoning.
- Kimi K2.7 (local ollama, free) is better at **visual verification** of rendered output (MoonViT multimodal).

**Net result:** replace kimi-k3:cloud (which was doing both generation and verification in the prior plan) with a specialization pipeline: GLM 5.2 for generation, Kimi K2.7 for visual QA. **kimi-k3:cloud appears in NO stage of this plan.**

---

## 1. PIPELINE ARCHITECTURE

### 1.1 Two-Stage Workflow

```
                ┌─────────────────────────────────────────────────────┐
                │                 STAGE 1 — GENERATION                │
                │                  GLM 5.2 (worker-balloon)           │
                │                                                     │
   task spec ─► │  DRC PROTECTION SYSTEM PROMPT (mandatory)           │
                │       │                                             │
                │       ▼                                             │
                │  1. Pre-layout coordinate math (in prompt output)   │
                │  2. Python pcbnew API script (.py)                  │
                │  3. Full pin map (no ellipsis)                      │
                │  4. Critical-nets + layer-assignment table          │
                │       │                                             │
                │       ▼                                             │
                │  /usr/bin/python3.14 stage1_<variant>.py            │
                │       │                                             │
                │       ▼                                             │
                │  <variant>.kicad_pcb  (4-layer: F/In1.GND/In2.3V3/B)│
                │       │                                             │
                │       ▼                                             │
                │  kicad-cli drc run --severity-error  (Stage 1 gate) │
                │  kicad-cli pcb export gerber                         │
                └────────────────────────┬────────────────────────────┘
                                         │ handoff: .kicad_pcb + gerbers + drc.rpt
                                         ▼
                ┌─────────────────────────────────────────────────────┐
                │                 STAGE 2 — VISUAL VERIFY             │
                │             Kimi K2.7 Code (worker-layout, local)   │
                │                                                     │
   gerbers ───► │  Render F.Cu, B.Cu, F.Mask, F.Silk as PNG           │
                │       │                                             │
                │       ▼                                             │
                │  Kimi K2.7 (MoonViT vision) inspects each image:   │
                │   • visible shorts between adjacent traces/pads     │
                │   • trace clearance < ~0.2mm by eye                 │
                │   • pad alignment vs silkscreen                     │
                │   • solder-mask openings correct                    │
                │   • silkscreen legible / not overlapping pads       │
                │       │                                             │
                │       ▼                                             │
                │  VISUAL-CHECK-REPORT.md (pass/fail per layer)       │
                └────────────────────────┬────────────────────────────┘
                                         │
                            ┌────────────┴────────────┐
                            ▼                          ▼
                       PASS → Stage 3            FAIL → back to Stage 1
                       (gerbers → JLC)           with tightened constraints
```

### 1.2 Model Role Assignment

| Stage | Model | Provider | Cost | Role |
|-------|-------|----------|------|------|
| 1 — Generation | **GLM 5.2** | z.ai API | $4.40/M out | Python pcbnew scripts, netlists, placement, routing, coordinate math |
| 2 — Verify | **Kimi K2.7 Code** | local ollama (MoonViT) | free | Render gerbers → image, visual inspection, QA report |
| 3 — Admin/docs | **GLM 5.2** | z.ai API | $4.40/M out | JLCPCB BOM, order placement, doc maintenance |

### 1.3 Stage Handoff Artifacts

Stage 1 → Stage 2 passes:
- `output/<variant>.kicad_pcb` — the board file
- `output/<variant>-F_Cu.gbr`, `…-B_Cu.gbr`, `…-F_Mask.gbr`, `…-F_Silk.gbr`, `…-Edge_Cuts.gbr` — gerbers for rendering
- `output/<variant>-drc.rpt` — DRC report (Stage 1 gate evidence)
- `output/<variant>-PRE-LAYOUT.md` — the pre-layout coordinate math (proof the model reasoned, not hallucinated)

Stage 2 → Stage 3 (JLC) passes only on PASS:
- `output/<variant>-VISUAL-CHECK.md` — Kimi's per-layer pass/fail

---

## 2. DRC PROTECTION SYSTEM PROMPT

**This prompt is the system prompt for EVERY Stage 1 task.** It exists to prevent the documented failure modes (80+ shorts from naive L-routing, empty pin lists, hidden collisions). It is mandatory — a Stage 1 task without it is invalid.

```
You are a PCB design engineer generating KiCad boards via the Python pcbnew API
(version 9.0.8). Your output will be FABRICATED by JLCPCB. Errors cost real money.
You MUST follow these rules. Violating any rule is a critical bug.

RUNTIME: /usr/bin/python3.14 ONLY. Never python3 or python3.11 (they segfault on pcbnew).
IMPORT:  sys.path.insert(0, '/usr/lib/python3/dist-packages') then import pcbnew.
BOARD:   pcbnew.NewBoard() — NEVER the board loader (it needs wxApp, fails headless).

═══════════════════════════════════════════════════════════════
PRE-LAYOUT MATH (MANDATORY — do this BEFORE any code)
═══════════════════════════════════════════════════════════════
Before writing any Python, you MUST emit a "PRE-LAYOUT CHECK" block containing:

1. COMPONENT TABLE — every component with its (X, Y) center in mm, footprint,
   and bounding box (min_x, min_y, max_x, max_y) computed from pad offsets.

2. PAD COLLISION CHECK — for every pair of components, verify:
     |center_A − center_B| > bbox_A/2 + bbox_B/2 + 0.5mm guard
   List any pair that violates this. Re-position until zero violations.

3. NET TABLE — every net, its layer assignment (F.Cu=0, B.Cu=31, In1.Cu=1, In2.Cu=2),
   track width, and the ordered list of (component, pad) it connects.

4. COORDINATE BOUNDARY CHECK — every pad X,Y must satisfy:
     0.5mm ≤ X ≤ BOARD_WIDTH − 0.5mm
     0.5mm ≤ Y ≤ BOARD_HEIGHT − 0.5mm
   (0.5mm edge clearance, JLCPCB minimum.)

If you cannot produce the pre-layout check, STOP and say so. Do not write code.

═══════════════════════════════════════════════════════════════
CLEARANCE RULES (DRC — 0 violations is the only acceptable count)
═══════════════════════════════════════════════════════════════
- Minimum clearance between any two different nets: 0.20 mm.
- Via-to-pad minimum distance: 0.25 mm.
- Track-to-board-edge minimum: 0.50 mm.
- Hole-to-hole minimum wall: 0.25 mm.
- No same-layer crossing for different nets. If two nets would cross on the
  same layer, one MUST via to the other signal layer (F.Cu↔B.Cu).
- Power nets (GND, 3V3) are INTERNAL PLANES — never route them as tracks.
  GND = In1.Cu zone (entire layer). 3V3 = In2.Cu zone (entire layer).
  Any pad needing GND or 3V3 gets a via to that plane.

═══════════════════════════════════════════════════════════════
PIN LIST INTEGRITY
═══════════════════════════════════════════════════════════════
- NEVER use ellipsis (...) in pad/pin lists. Every pad is listed explicitly.
- Pin assignments MUST match the firmware source (app_main.cpp lines 85-94).
  The firmware is ground truth. If the board disagrees with the firmware, the
  board is wrong.
- ESP32-C3 strapping pins (GPIO2, GPIO8, GPIO9) — do not assign to active-high
  loads. GPIO0 is also strapping; FEM_RX moves to GPIO8 per the brief.

═══════════════════════════════════════════════════════════════
OUTPUT CONTRACT
═══════════════════════════════════════════════════════════════
Your final output is a single self-contained Python script that:
1. Calls pcbnew.NewBoard()
2. Sets 4 layers (F.Cu, In1.Cu, In2.Cu, B.Cu) + the standard KiCad layer set
3. Adds a board outline (pcbnew.SHAPE_T_RECT) at BOARD_WIDTH × BOARD_HEIGHT
4. Creates all nets with correct names
5. Places every footprint with explicit (X, Y) from the pre-layout table
6. Adds GND zone on In1.Cu and 3V3 zone on In2.Cu (full-board copper pour)
7. Routes signal tracks on F.Cu and B.Cu only
8. Saves the board with board.Save("<variant>.kicad_pcb")
9. Prints "BOARD_SAVED: <path>" as the last line (gate signal)

Do not route power nets as tracks. Do not skip the pre-layout check.
Do not leave any pad unconnected unless explicitly marked NC in the net table.
```

---

## 3. PER-VARIANT TASK BREAKDOWN

All three variants share:
- 4-layer stackup: **F.Cu / In1.Cu=GND plane / In2.Cu=3V3 plane / B.Cu**
- Board size: 50mm × 40mm (matches `full_pipeline.py` constants)
- 17 components (16 if FEM omitted as no-fit; net still defined)
- Component placement table from `full_pipeline.py` `get_v1_fast_components()` as starting reference

### 3.1 Variant 1 — Balloon-C3 (ESP32-C3 single-MCU)

**MCU:** ESP32-C3-MINI-1 (bare module, not Super Mini dev board)

#### C3 Pin Map (ground truth — `app_main.cpp:85-94`)

| Function | GPIO | Net name |
|----------|------|----------|
| LR2021 SCK | 6 | SPI_SCK |
| LR2021 MISO | 2 | SPI_MISO |
| LR2021 MOSI | 7 | SPI_MOSI |
| LR2021 NSS | 10 | SPI_NSS |
| LR2021 BUSY | 4 | LR2021_BUSY |
| LR2021 RST | 3 | LR2021_RST |
| LR2021 DIO9 | 5 | LR2021_DIO9 |
| Status LED | 18 | STATUS_LED |
| GPS UART RX | 1 | GPS_RX |
| GPS UART TX | 0 | GPS_TX (optional) |
| FEM TX | 19 | FEM_TX |
| FEM RX | 8 | FEM_RX (moved from GPIO0 — strapping) |
| VCAP ADC | 0 | VDIV_MID (ADC1_CH0) |

**⚠ GPIO0 conflict:** GPIO0 is BOTH the ADC input (VDIV_MID) and a strapping pin.
On C3 the ADC on GPIO0 (ADC1_CH0) is usable; the strapping concern only matters at boot
if the pin is pulled hard. R_DIV is a 100k/100k divider → high impedance → safe. Keep FEM_RX off GPIO0.

#### Stage 1 Task — C3

| Field | Value |
|-------|-------|
| Worker | worker-balloon |
| Model | GLM 5.2 |
| System prompt | DRC PROTECTION SYSTEM PROMPT (§2) |
| Inputs | C3 pin map (above), `full_pipeline.py` component defs, 4-layer spec |
| Output | `output/stage1_c3.py`, then run it → `output/balloon-c3.kicad_pcb` |
| DRC gate | `kicad-cli drc run -o output/c3-drc.rpt output/balloon-c3.kicad_pcb` → 0 errors |
| Est. time | 1 GLM round (~15 min) + DRC iteration (~20 min) = **~35 min** |

#### Stage 2 Task — C3

| Field | Value |
|-------|-------|
| Worker | worker-layout |
| Model | Kimi K2.7 Code (local ollama) |
| Inputs | `balloon-c3.kicad_pcb` + gerbers from Stage 1 |
| Process | `gerbv`/`kicad-cli` render F.Cu, B.Cu, F.Mask, F.Silk → PNG; feed to Kimi MoonViT |
| Output | `output/c3-VISUAL-CHECK.md` |
| Est. time | **~15 min** (rendering is the bottleneck) |

#### C3 Quality Gates

See §4 (all gates apply). Variant-specific: pin map must match table above exactly.

---

### 3.2 Variant 2 — Balloon-S3 (ESP32-S3 single-MCU)

**MCU:** ESP32-S3-MINI-1 (more GPIO, more RAM, PSRAM-capable)

#### S3 Pin Map (remapped from C3 — S3 has different GPIO matrix)

| Function | GPIO | Net name | Notes |
|----------|------|----------|-------|
| LR2021 SCK | 36 | SPI_SCK | S3 SPI-capable |
| LR2021 MISO | 37 | SPI_MISO | |
| LR2021 MOSI | 35 | SPI_MOSI | |
| LR2021 NSS | 34 | SPI_NSS | |
| LR2021 BUSY | 33 | LR2021_BUSY | |
| LR2021 RST | 38 | LR2021_RST | |
| LR2021 DIO9 | 39 | LR2021_DIO9 | |
| Status LED | 21 | STATUS_LED | |
| GPS UART RX | 9 | GPS_RX | UART1 |
| GPS UART TX | 8 | GPS_TX | |
| FEM TX | 17 | FEM_TX | |
| FEM RX | 18 | FEM_RX | |
| VCAP ADC | 1 | VDIV_MID | ADC1_CH0 on S3 |

**⚠ S3 strapping pins (AVOID):** GPIO0, GPIO3, GPIO45, GPIO46. None of the assignments above touch them.

#### Stage 1 Task — S3

| Field | Value |
|-------|-------|
| Worker | worker-balloon |
| Model | GLM 5.2 |
| System prompt | DRC PROTECTION SYSTEM PROMPT (§2) |
| Inputs | S3 pin map (above), same component set as C3, 4-layer spec |
| Output | `output/stage1_s3.py` → `output/balloon-s3.kicad_pcb` |
| DRC gate | 0 errors |
| Est. time | **~35 min** |

#### Stage 2 Task — S3

Same as C3 Stage 2, different board file. **~15 min.**

#### S3 Quality Gates

Same as C3. Pin map must match S3 table. **Extra check:** confirm no strapping pin (0/3/45/46) is assigned.

---

### 3.3 Variant 3 — Balloon-Dual (ESP32-C3 + RP2040)

**MCUs:** ESP32-C3-MINI-1 (WiFi/BT/Nostr/app) + RP2040 (radio SPI real-time)
**Architecture:** per ADR-026 — RP2040 owns LR2021 SPI; C3 owns everything else.
**Inter-MCU bus:** UART (C3 GPIO0↔RP2040 GP0/1) — simpler than SPI for this use case.

#### Dual Pin Map

**ESP32-C3 side:**

| Function | GPIO | Net |
|----------|------|-----|
| GPS RX | 1 | GPS_RX |
| Status LED | 18 | STATUS_LED |
| FEM TX | 19 | FEM_TX |
| FEM RX | 8 | FEM_RX |
| VCAP ADC | 0 | VDIV_MID |
| RP2040 UART TX | 2 | MCU_TX (to RP2040 GP1) |
| RP2040 UART RX | 3 | MCU_RX (from RP2040 GP0) |

**RP2040 side:**

| Function | GP | Net |
|----------|----|-----|
| LR2021 SCK | 2 | SPI_SCK |
| LR2021 MISO | 0 | SPI_MISO |
| LR2021 MOSI | 3 | SPI_MOSI |
| LR2021 NSS | 5 | SPI_NSS |
| LR2021 BUSY | 4 | LR2021_BUSY |
| LR2021 RST | 6 | LR2021_RST |
| LR2021 DIO9 | 7 | LR2021_DIO9 |
| C3 UART RX | 0 | MCU_RX |
| C3 UART TX | 1 | MCU_TX |

**⚠ RP2040 pin note:** GP0 is used for SPI_MISO and is also the MCU_RX line.
This is a conflict — resolve by moving MCU_RX to GP8 and MCU_TX to GP9 (RP2040 has 30 GPIO).

#### Stage 1 Task — Dual

| Field | Value |
|-------|-------|
| Worker | worker-balloon |
| Model | GLM 5.2 |
| System prompt | DRC PROTECTION SYSTEM PROMPT (§2) |
| Inputs | Dual pin map (above), adds RP2040 footprint (~7×7mm QFN), inter-MCU UART |
| Output | `output/stage1_dual.py` → `output/balloon-dual.kicad_pcb` |
| DRC gate | 0 errors |
| Est. time | **~50 min** (dual MCU = more pads, more nets) |

#### Stage 2 Task — Dual

Same process, more layers to inspect. **~20 min.**

#### Dual Quality Gates

Same base gates + **inter-MCU net check:** every C3↔RP2040 net must appear on both MCU pad lists.

---

## 4. QUALITY GATES

Gates are **hard stops.** A variant does not advance to the next stage until its gate passes. Evidence (the report file) is committed to git.

### 4.1 Stage 1 Gates (per variant)

| # | Gate | Check command | Pass criterion |
|---|------|---------------|----------------|
| 1.1 | Footprint count | `kicad-cli …` or grep `.kicad_pcb` | ≥ 17 footprints |
| 1.2 | Layer count | board has F.Cu, In1.Cu, In2.Cu, B.Cu | exactly 4 copper layers |
| 1.3 | Pin map match | script diff vs firmware pin table | 0 mismatches |
| 1.4 | DRC shorts | `kicad-cli drc run` | `shorting_items: 0` |
| 1.5 | DRC unconnected | same | `unconnected_items: 0` |
| 1.6 | F.Cu non-empty | gerber aperture analysis | >10 aperture draws on F_Cu.gbr |
| 1.7 | Pre-layout doc exists | `ls output/<variant>-PRE-LAYOUT.md` | file present, non-empty |
| 1.8 | Internal planes exist | grep `.kicad_pcb` for In1/In2 zones | GND zone on In1, 3V3 zone on In2 |

**Circuit breaker:** if gate 1.4 or 1.5 fails after 3 DRC iterations, escalate to tighter-constraint re-run (§7.1).

### 4.2 Stage 2 Gates (per variant)

| # | Gate | Method | Pass criterion |
|---|------|--------|----------------|
| 2.1 | No visible shorts | Kimi MoonViT on F.Cu render | "no shorts detected" |
| 2.2 | Trace clearance | Kimi MoonViT on F.Cu render | "clearance appears adequate" |
| 2.3 | Pad alignment | Kimi MoonViT on F.Silk + F.Mask overlay | "pads aligned with silkscreen" |
| 2.4 | Solder mask | Kimi MoonViT on F.Mask render | "openings correct" |
| 2.5 | Silkscreen | Kimi MoonViT on F.Silk render | "legible, no pad overlap" |
| 2.6 | B.Cu sanity | Kimi MoonViT on B.Cu render | "no unexpected features" |

**Circuit breaker:** if Kimi returns "inconclusive" on any gate, route to human review (§7.2). Do NOT auto-pass.

---

## 5. WORKER ASSIGNMENTS

| Worker | Profile/Model | Role | Models used |
|--------|---------------|------|-------------|
| **worker-balloon** | GLM 5.2 (z.ai) | Stage 1: programmatic board generation, all 3 variants | GLM 5.2 only |
| **worker-layout** | Kimi K2.7 Code (local ollama) | Stage 2: gerber rendering + visual verification | Kimi K2.7 + MoonViT only |
| **worker-admin** | GLM 5.2 (z.ai) | Stage 3: JLCPCB BOM, gerber packaging, ordering, docs | GLM 5.2 only |

**Forbidden anywhere in this plan:** `kimi-k3:cloud`. Do not assign it. Do not fall back to it. If a task would "need" kimi-k3:cloud, it is blocked until quota restores — escalate instead.

---

## 6. SCHEDULING

### 6.1 Dependency Graph

```
                    ┌──────────────────────────────────┐
                    │ Stage 1-C3 (GLM 5.2)             │  ~35 min
                    │   └─► DRC gate ─┬─PASS─► gerbers  │
                    │                 └─FAIL─► retry   │
                    └──────────┬───────────────────────┘
                               │ (C3 gerbers ready)
                               ▼
                    ┌──────────────────────────────────┐
                    │ Stage 2-C3 (Kimi K2.7)           │  ~15 min
                    │   └─► visual gate ─┬─PASS─► DONE │
                    │                    └─FAIL─► S1   │
                    └──────────────────────────────────┘

   (S3 and Dual run IDENTICAL structure, in parallel with C3 once Stage 1 is validated)
```

### 6.2 Parallelism

**Stage 1 (GLM 5.2) is the bottleneck** — single model, single worker. Recommended serial order:

1. **C3 first** (highest priority — immediate testing platform, simplest, validates the pipeline end-to-end)
2. **S3 second** (same component set, pin remap only — fast once C3 template works)
3. **Dual last** (most complex — benefits from C3/S3 learnings)

**Stage 2 (Kimi K2.7) can run in parallel** across variants IF Kimi is given the gerbers — local ollama is not rate-limited the same way.

### 6.3 Critical Path to Gerbers

```
C3 Stage 1 (35m) → C3 Stage 2 (15m) → C3 gerbers ready:  ~50 min from start
S3 Stage 1 (35m) → S3 Stage 2 (15m):                      +50 min (serial after C3 S1)
Dual Stage 1 (50m) → Dual Stage 2 (20m):                  +70 min

Total critical path: ~3 hours for all 3 variants at full DRC convergence.
Budget 1 full day for DRC iteration + visual review loops.
```

### 6.4 Milestones

| Milestone | Target |
|-----------|--------|
| C3 gerbers ready + visual PASS | End of Day 1 |
| S3 gerbers ready + visual PASS | Day 2 morning |
| Dual gerbers ready + visual PASS | Day 2 afternoon |
| JLCPCB order placed | End of Day 2 |
| Boards delivered | ~Day 16 (2-week lead) |

---

## 7. RISK MITIGATIONS

### 7.1 GLM 5.2 produces shorts (DRC > 0)

**Likelihood:** Medium (documented: naive L-routing made 80+ shorts — but this plan forbids L-routing; uses programmatic pcbnew API + pre-layout math).

**Mitigation ladder:**
1. **First DRC failure:** feed the DRC error report back to GLM 5.2 as a follow-up prompt: "Fix these N shorting_items. For each, compute the conflicting coordinates and reroute." (1 iteration)
2. **Second failure (same net):** tighten the clearance rule in the system prompt from 0.20mm → 0.25mm and re-run. The pre-layout collision check should catch spatial overlaps.
3. **Third failure:** **circuit breaker.** Route the failing net manually in the `.py` script (explicit `pcbnew.PCB_TRACK` with hand-computed coordinates from the pre-layout table). Commit the manual route as `stage1_<variant>_v2.py`.
4. **Persistent failure on a power net:** this should be impossible (GND/3V3 are planes). If it happens, the plane zone is malformed — regenerate In1.Cu/In2.Cu zones from scratch.

### 7.2 Kimi K2.7 visual check is inconclusive

**Likelihood:** Medium (MoonViT is good but not perfect on dense PCB renders).

**Mitigation:**
1. Re-render at higher DPI (2× zoom on the suspect region).
2. Ask Kimi a more specific question: "Is there copper connecting pad X to pad Y within 0.2mm?"
3. **Circuit breaker:** escalate to **human review.** Post the rendered image + the DRC report. If DRC says 0 shorts AND human says "looks fine," proceed. DRC is authoritative; visual is a sanity check.

### 7.3 FreeRouting fails / produces bad routes

**Likelihood:** Low (this plan uses programmatic GLM routing first; FreeRouting is a fallback).

**Mitigation:**
- FreeRouting is invoked ONLY if GLM's programmatic routing leaves unconnected items after 3 iterations.
- The DSN/SES pipeline (`ExportSpecctraDSN` → FreeRouting → `ImportSpecctraSES`) is the fallback.
- **Final fallback:** with 4-layer (GND + 3V3 as planes), only signal nets need routing on F.Cu + B.Cu. Two clear layers for ~15 signal nets is trivial — manual routing in the `.py` script always converges.

### 7.4 GLM 5.2 API quota / rate limit

**Likelihood:** Low (z.ai quota monitored — see `dq05_quota` tool).

**Mitigation:**
- Stage 1 tasks are batched (one variant per API session, not per-net).
- If GLM 5.2 quota is exhausted mid-variant: checkpoint the `.py` script so far, resume when quota resets.
- **No fallback model for Stage 1.** GLM 5.2 is the chosen generator. Do not substitute.

### 7.5 Silent model failure (the kimi-k3:cloud lesson)

**This is the #1 risk.** The prior plan committed an empty board because the model failed silently.

**Mitigation — gate 1.6 (F.Cu non-empty) is the explicit anti-silent-failure check:**
- A board with 0 aperture draws on F_Cu.gbr is an empty board. Gate 1.6 fails.
- The "BOARD_SAVED:" final-line contract in the system prompt detects truncated output.
- Stage 2 (visual) is a second line of defense: Kimi will report "I see no traces" on an empty render.

---

## 8. JLCPCB ORDER STRATEGY

### 8.1 Order Timing: All 3 at once (batched)

**Rationale:**
- JLCPCB charges a flat setup fee per order. 3 boards in 1 order = 1 setup fee.
- Shipping is flat-rate per order — 1 shipment for 3 boards.
- All 3 variants share the same 4-layer / 1.6mm / green spec → same production line.

**Exception:** if C3 passes all gates first and S3/Dual are still iterating, **order C3 alone immediately.** C3 is the immediate testing platform — don't delay it for S3/Dual. S3/Dual go in a second order when ready.

### 8.2 Cost Breakdown

| Item | Per order | Qty | Cost |
|------|-----------|-----|------|
| 4-layer PCB, 1.6mm, ENIG, 50×40mm | ~$8 / 5 boards | 3 variants × 5 | $24 |
| Shipping (DHL, ~5 days) | ~$20 | 1 (or 2 if split) | $20–40 |
| **Total (all 3 batched)** | | | **~$44–64** |

**HASL vs ENIG:** ENIG (+~$2) for the U.FL pads and QFN — HASL can cause uneven pad heights on fine-pitch. Use ENIG.

### 8.3 JLCPCB Specs (identical for all 3)

| Spec | Value |
|------|-------|
| Layers | 4 |
| Thickness | 1.6 mm |
| Surface finish | ENIG |
| Solder mask | Green |
| Silkscreen | White |
| Copper weight | 1 oz (35µm) |
| Min track | 0.20 mm |
| Min clearance | 0.20 mm |
| Min via drill | 0.30 mm |
| Impedance control | No (short traces, not high-speed) |

### 8.4 Lead Time

- Fabrication: 3–5 business days (4-layer)
- DHL shipping: 3–5 days
- **Total: ~2 weeks from order to door**

---

## 9. TOOLING REFERENCE

| Tool | Path / Command | Use |
|------|----------------|-----|
| Python (pcbnew API) | `/usr/bin/python3.14` | Stage 1 board generation (NEVER python3/python3.11) |
| pcbnew import | `sys.path.insert(0,'/usr/lib/python3/dist-packages')` | then `import pcbnew` |
| KiCad CLI | `kicad-cli` | DRC + gerber export |
| FreeRouting | `java -jar freerouting.jar` | Fallback signal auto-routing |
| DSN export | `kicad-cli pcb export specctra` | FreeRouting input |
| Kimi K2.7 | `ollama run kimi-k2.7` | Stage 2 visual model |
| gerbv | `gerbv` or kicad-cli render | Gerber → PNG for Kimi |

---

## 10. LESSONS LEARNED → DESIGN DECISIONS

| Lesson (what went wrong) | Decision in this plan |
|--------------------------|----------------------|
| 33 board variants generated by scripts without schematics — no ERC ever run | Pre-layout coordinate math is mandatory (§2); schematic-first remains the ADR-028 ideal, but this plan generates board + validates pin map programmatically as a pragmatic path |
| 2-layer boards can't converge: power nets = 50% of routing failures | **4-layer mandatory** (In1=GND plane, In2=3V3 plane). Power routing eliminated entirely |
| Empty "4-layer" board committed because kimi-k3:cloud silently failing | Gate 1.6 (F.Cu >10 apertures) + Stage 2 visual check are explicit anti-silent-failure measures |
| GLM 5.2 manual routing created 80+ shorts on 2-layer (naive L-routing) | This plan uses **programmatic pcbnew API** (not manual L-routing) + pre-layout collision check + 0.20mm clearance enforcement |
| FreeRouting works for signal but needs clean power planes | 4-layer gives clean planes; FreeRouting is fallback-only, not primary |

---

## 11. SUCCESS CRITERIA

This plan succeeds when ALL of the following are true:

- [ ] 3 `.kicad_pcb` files committed (balloon-c3, balloon-s3, balloon-dual), each 4-layer
- [ ] Each passes DRC with 0 shorting_items, 0 unconnected_items
- [ ] Each passes Kimi K2.7 visual inspection (no visible shorts, adequate clearance)
- [ ] Each pin map matches the firmware (C3) or the remapped firmware (S3, Dual)
- [ ] Gerbers exported and packaged for JLCPCB
- [ ] JLCPCB order placed (C3 first if staggered)
- [ ] Zero use of kimi-k3:cloud anywhere in the pipeline

**End of plan.**
