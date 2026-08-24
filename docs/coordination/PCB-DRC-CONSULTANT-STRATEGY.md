# PCB DRC Consultant Strategy — Why Workers Are Stuck & How to Unblock

**Date:** 2026-08-05
**Author:** PCB Consultant (automated review)
**Audience:** worker-balloon, worker-inspector, orchestrator
**Inputs reviewed:**
- `docs/coordination/PCB-AUTO-ROUTE-EXECUTION-PLAN-V2.md` (execution plan, 1573 lines)
- `tracker/hardware/full_pipeline.py` (A* pipeline, 1377 lines)
- `tracker/hardware/freerouting_pipeline.py` (FreeRouting pipeline, 365 lines)
- `tracker/hardware/output/v1_fast_routed_drc.json` — V1: 2 violations, 43 unconnected
- `tracker/hardware/output/v2_adc_routed2_drc.json` — V2: 4 violations, 19 unconnected
- `tracker/hardware/output/v2_adc_freerouted_drc.json` — V2 FreeRouting: 2 violations, 20 unconnected
- `tracker/hardware/output/v2_adc_routed2.kicad_pcb` (pad geometry inspected directly)
- `DRC_ROOT_CAUSE_ANALYSIS.md` — **does NOT exist yet** (this doc serves as the consultant-side root cause; the worker-side companion file should be written from this)

**TL;DR for the orchestrator:** Workers are stuck because the DRC iteration loop is a no-op placebo — it re-runs the exact same deterministic A*/FreeROUTING strategy every iteration with zero parameter change, so 90 iterations is equivalent to 1 iteration. On top of that, the ESP32-C3 footprint has a pad-layout bug (GPIO5 and GPIO6 pads physically overlap on the module corner) that no router can fix because the violation is in the placement, not the routing. Fixing these two issues + finishing V2 by hand in KiCad GUI is the fastest path to fabrication.

---

## 1. Root-Cause Findings (in priority order)

### 1.1 CRITICAL — The iteration loop does nothing different between iterations

`full_pipeline.py` lines 1312–1369. The loop body:

```python
for iteration in range(1, args.max_iterations + 1):
    router = GridRouter()              # identical config each time
    router.block_all_pads(nets)        # identical blocking
    for net_code in routing_order:     # identical order (sorted by pad count, deterministic)
        ...
    # STEP 5b: Analyze DRC errors for next iteration
    # (simplified — just report and continue to next iteration)
    if iteration < args.max_iterations:
        print("Continuing to next iteration (re-route with same strategy)...")
```

**Evidence the loop is deterministic:**
- `grep -n 'seed\|random\|shuffle\|param.*iter' full_pipeline.py` → **0 results**. No RNG, no perturbation, no strategy change.
- Line 1369 prints the literal string `"re-route with same strategy"`.
- The DRC breakdown at step 5b is collected but never *used* to alter the next pass.
- `freerouting_pipeline.py` (lines 254–362) has the same shape: it recreates the board from scratch and reruns FreeRouting with `--mp 16` every iteration. FreeRouting itself is stochastic, so this loop is *slightly* productive (different seed → different result), but the pipeline around it still changes nothing between passes.

**Conclusion:** The "90 iterations" budget is fictional. For A* it is mathematically equivalent to 1 iteration. For FreeRouting it is at most 90 random restarts of the same problem with no learning. The workers have not been failing to converge — they have been asking the same question 90 times and getting the same answer.

### 1.2 CRITICAL — ESP32-C3 footprint has a pad-collision bug (placement, not routing)

Inspection of `output/v2_adc_routed2.kicad_pcb` confirms the GPIO pad geometry on U1:

| Pad | Net | abs position (mm) |
|-----|-----|--------------------|
| GPIO4 | LR2021_BUSY | (8.50, 14.25) |
| **GPIO5** | **LR2021_DIO9** | **(8.50, 16.25)** |
| **GPIO6** | **SPI_SCK** | **(9.00, 15.50)** |
| GPIO7 | SPI_MOSI | (10.50, 15.50) |

- GPIO5 ↔ GPIO6 center-to-center: `sqrt(0.5² + 0.75²) = 0.901 mm`
- Both pads are 1.0 × 0.6 mm → **they physically overlap.**
- This is the source of every `shorting_items` and `solder_mask_bridge` violation in both V1 and V2 DRC outputs (V1: 2/2 violations, V2-FreeRouting: 2/2 violations).

The bug is in `make_esp32c3_pads()` (`full_pipeline.py` lines 105–188). The left-side GPIO column (GPIO0–GPIO5) descends to `dy = -3.75 + 5·1.5 = +3.75`, then the bottom-side row (GPIO6–GPIO10) starts at `dx = -3.0, dy = +3.5`. The left column's last pad and the bottom row's first pad wrap around the same module corner with no gap.

**No router can fix this.** It must be fixed in the footprint layout.

### 1.3 HIGH — The A* router is structurally incomplete

`GridRouter` (`full_pipeline.py` lines 873–1136) has three structural deficits that explain the 43-unconnected V1 result:

1. **Single-layer routing.** `a_star(start, goal, layer, …)` takes a layer argument and never crosses layers for signal nets. GND is special-cased to B.Cu via a rail; everything else is forced to F.Cu. There is no via insertion during signal routing.
2. **Over-aggressive pad blocking.** `block_pad()` uses `margin = pad_half + 1 cell`, and `_block_segment()` uses `margin = 2 cells` (0.5 mm). On a 0.25 mm grid, ESP32-C3 pads (1.0 × 0.6 mm) block ~6 × 5 cells each, and at 1.5 mm pitch (6 cells) the adjacent-pad comment in the source confirms: *"adjacent ESP32 pads leave a 0-cell corridor … A\* must route around the entire pad cluster."* The router paints itself into a corner before any track is laid.
3. **No rip-up-and-retry.** Once a net is routed, its segments block all future nets. Failed pairs are skipped forever — there is no backtracking.

A* is a toy router. FreeROUTING is a production autorouter with rip-up, layer switching, and 30+ years of heuristics. The pivot to FreeRouting was correct; the A* code should be retired for signal routing.

### 1.4 MEDIUM — GND rail strategy creates phantom unconnected items

`route_gnd_on_bcu()` (lines 745–849) lays a single horizontal rail at the median Y of all GND pads and drops a via at every SMD GND pad to reach the rail. The pad-via-net connectivity that KiCad's DRC expects is fragile here: if the via-to-pad geometric overlap is off by even one grid cell, KiCad reports the pad as *unconnected* even though the via is electrically on the same net. This explains why **GND dominates the unconnected counts** (V1: 38 of 43, V2-FreeRouting: 10 of 20). The GND net is being routed in a way that DRC has trouble recognizing as connected.

### 1.5 MEDIUM — Placement ignores routing flow

The 50 × 40 mm board has 16 components occupying maybe 30% of the area, but they were placed by table lookup from the execution plan, not by routing flow analysis:

- **3V3 net pads** are spread across 36 mm: U1 VCC (15.5, 8.25), U2 pin1 (15.1, 17), U3 pin1 (4, 33), U4 pin4 (5.95, 22.75), C2 pin1 (6.5, 24), FEM VCC (40, 25). Daisy-chaining this is hard.
- **GND net pads** (16+ pads including 6 LR2021 GND pins) are scattered across the entire board.
- **SPI bus** (SCK/MOSI/MISO/NSS) must run from U1's bottom-left corner to U2's left side — but GPIO6/SCK starts from the buggy corner pad.
- **VCAP** (LDO-IN, BAT54-K, C_CAP-+, C1-+) has 6 unconnected on V2 because the four pads span (4, 18) → (8.5, 22) → (7.5, 37) → (7.5, 22).

Plenty of board area is free. The layout was not the bottleneck for *space*, it was the bottleneck for *flow*.

---

## 2. Answers to the Six Consultant Questions

### Q1. Is the iteration budget (90) too low for a 15–18 net board? What's realistic?

**The budget number is irrelevant because the loop is deterministic.** 90 iterations of the current A* loop produces output identical to 1 iteration — confirmed by code inspection (no RNG, no perturbation, see §1.1). For a 17-net board with two layers and no congestion, a *real* iterative router (FreeRouting with rip-up) converges in **3–8 passes**. The right answer is not "raise the budget" — it is "make each iteration different."

For FreeRouting specifically: `--mp 16` (max passes) is fine. The bottleneck is not FreeRouting's pass count; it is the buggy pad layout (§1.2) and the lack of between-iteration strategy changes in the wrapper script.

### Q2. Should we switch to FreeROUTING exclusively?

**Yes for signal routing. No for the surrounding pipeline.**

- Retire `GridRouter` / `route_net` / `route_gnd_on_bcu` for any net that has more than 2 pads. The A* router is structurally incomplete (§1.3) and is the primary source of the V1 disaster (43 unconnected, 38 of them GND).
- Keep `freerouting_pipeline.py` as the only routing pipeline.
- The FreeROUTING result on V2 (4 violations, 19 unconnected) is **dramatically better** than A* on V1 (2 violations, 43 unconnected) even with the same buggy placement — that is the strongest evidence FreeROUTING is the right tool.
- Note: FreeRouting's DSN export requires the KiCad board's design rules to be set correctly (`set_board_design_rules()` already does this in `freerouting_pipeline.py` line 39 — keep that).

### Q3. Is V2-ADC at 4 violations / 19 unconnected close enough to manually fix?

**Yes — it is the fastest path to fabrication, but only after the GPIO5/GPIO6 pad bug is fixed.** Breakdown of the 4 violations:

| # | Type | Cause | Fix |
|---|------|-------|-----|
| 1–3 | `copper_edge_clearance` | SOLAR_IN track runs within 0.237 mm of board edge (DRC needs 0.5 mm) | **Trivial.** Move the SOLAR_IN track inboard by 0.3 mm in the GUI, or restrict the router's edge margin. |
| 4 | `clearance` (0.15 mm actual vs 0.20 mm required) | GPIO5/GPIO6 pad overlap (§1.2) | **Requires footprint fix**, then re-route. ~30 min of code change. |

The 19 unconnected items break down as: 6 × 3V3, 6 × GND, 6 × VCAP, 2 × each SPI line, 2 × RF, 2 × VDIV_MID, 1 × STATUS_LED. All are short point-to-point connections on a nearly-empty 50 × 40 mm board. **Estimate: 45–75 minutes of manual routing in KiCad GUI** to finish V2 from the current FreeROUTING output, *after* the pad bug is fixed.

### Q4. Should we change the approach — place components better before routing?

**Yes. This is the single highest-leverage change after killing the fake iteration loop.** Specific placement changes that will help:

1. **Cluster power nets.** Move C1, C2, U4 (LDO), and D1 (BAT54) into a tight ~10 × 10 mm power island. Currently 3V3 and VCAP pads are spread across 30+ mm.
2. **Rotate U2 (LR2021) so its left-side pin 1 (3V3) faces U1's VCC pad.** Currently the 3V3 connection has to cross the board.
3. **Move GPS (U3) close to U1's GPIO1** (currently 24 mm apart for a single UART wire).
4. **Put both antenna pads on the same board edge** so RF traces don't cross.
5. **Group the SPI bus pads.** The SPI pins on U1 (GPIO6, 7, 10) are split by the GPIO8/GPIO9 pads. Consider whether the boot-strap GPIO2 pull-down (R_PD) can be placed under U1 to free corridor.

The 50 × 40 mm board is way oversized. If the layout were redone from scratch with routing flow in mind, FreeROUTING would likely hit 0/0 in a single pass.

### Q5. Is it realistic to get 0/0 headless, or should we accept some unconnected non-critical nets?

**Realistic for V2-ADC after the two critical fixes; not realistic for V1-FAST as currently structured.**

- V2-ADC: After (a) fixing the GPIO5/GPIO6 pad collision, (b) fixing the 3 copper-edge-clearance violations (move SOLAR_IN), and (c) one FreeRouting re-run, the unconnected count should drop from 19 to ≤ 5. The remaining (if any) will be power-net daisy-chain fragments that are easy to finish by hand. **Target: 0/0 is achievable**, fallback: ≤ 3 non-critical unconnected is acceptable for prototype fabrication (JLCPCB will manufacture regardless of DRC).
- V1-FAST: 43 unconnected with 38 of them GND indicates the GND routing strategy itself is broken (§1.4). Recommend **de-prioritizing V1-FAST** until V2-ADC is at fab. If both must ship, hand-route V1-FAST in GUI from the current artifact (estimate 90–120 min).

For a balloon prototype, **a board with 0 violations and 1–2 unconnected non-critical nets (e.g., FEM_TX, GPS_TX) is acceptable to order**. Critical nets are: 3V3, GND, SPI_*, LR2021_RST/BUSY/DIO9, GPS_RX, VCAP, SOLAR_IN. Everything else (STATUS_LED, FEM_TX, VDIV_MID, RF_*) is desirable but not launch-blocking.

### Q6. Specific worker instructions for the next attempt

See §3 below.

---

## 3. Worker Instructions — What to Do DIFFERENTLY Than the Last 3 Runs

The last 3 runs all did the same thing: invoked the pipeline with `--max-iterations N`, watched the deterministic loop fail to converge, and reported blocked. **None of the following actions were tried.** Do them in order.

### Step 0 — Verify this file exists and you have read it

```bash
test -f ~/repos/balloon-fresh/docs/coordination/PCB-DRC-CONSULTANT-STRATEGY.md && echo OK
```

If OK is not printed, **stop and ask the orchestrator** before proceeding.

### Step 1 — Fix the GPIO5/GPIO6 pad collision (CRITICAL, blocks everything)

File: `~/repos/balloon-fresh/tracker/hardware/full_pipeline.py`, function `make_esp32c3_pads()` (around line 105).

The bug: the left-side GPIO column ends at GPIO5 with `dy = -3.75 + 5·1.5 = +3.75` (or +4.25 in the actual PCB), and the bottom-side GPIO row starts at GPIO6 with `dx = -3.0, dy = +3.5`. The two pads wrap around the same corner.

**Fix option A (preferred): pull the bottom row inboard so it starts after the corner.**

Change the bottom-side loop start so GPIO6 begins at `dx = -1.5` instead of `dx = -3.0`:

```python
# Bottom side (y = +3.5), GPIO6-GPIO10
bottom_gpio = [6, 7, 8, 9, 10]
for i, gpio in enumerate(bottom_gpio):
    net = gpio_nets.get(gpio, "")
    if net:
        pads.append(PadDef(
            number=f"GPIO{gpio}",
            net=net,
            dx=-1.5 + i * pitch,   # was -3.0 + i * pitch  ← shift inboard by one pitch
            dy=3.5,
            w=pad_w, h=pad_h,
            layer=F_CU,
        ))
```

**Fix option B: shrink the pad height on the bottom row to 0.4 mm** so the left-column pad and bottom-row pad do not overlap at the corner. Less clean; only use if option A breaks some other constraint.

**Verification gate after Step 1** (mandatory, do not skip):

```bash
cd ~/repos/balloon-fresh/tracker/hardware
/usr/bin/python3.14 full_pipeline.py --board-type v2-adc \
    --output output/v2_adc_step1.kicad_pcb --create-only
kicad-cli pcb drc --format json --output /tmp/v2_step1_drc.json output/v2_adc_step1.kicad_pcb
python3 -c "
import json
d = json.load(open('/tmp/v2_step1_drc.json'))
v = d.get('violations', [])
shorts = [x for x in v if 'shorting_items' in x.get('type','') or 'solder_mask_bridge' in x.get('type','')]
print(f'shorts/solder_mask violations after pad fix: {len(shorts)}')
assert len(shorts) == 0, 'PAD FIX FAILED — GPIO5/GPIO6 still colliding'
print('PAD FIX OK')
"
```

If the assertion fails, do not proceed. Re-examine the pad geometry and try option B.

### Step 2 — Delete the deterministic A* iteration loop

The loop in `full_pipeline.py` lines 1312–1374 is a no-op (§1.1). Either:

- **(Recommended)** Stop using `full_pipeline.py`'s `main()` for routing. Use `freerouting_pipeline.py` exclusively. Keep `full_pipeline.py` only for `create_board_v1_fast` / `create_board_v2_adc` (board creation) and `parse_board`, `run_drc`, `export_gerbers` (utilities).
- **(Alternative)** Add real perturbation to the loop: shuffle `routing_order` with a per-iteration seed, vary `GRID_RESOLUTION_MM` between 0.20/0.25/0.30, and vary the net-blocking margin. But this is wasted effort — the A* router is structurally inferior to FreeROUTING (§1.3).

**Do not "try more iterations" of the existing pipeline.** That is what the last 3 runs did.

### Step 3 — FreeRouting-only run on V2-ADC with the fixed placement

```bash
cd ~/repos/balloon-fresh/tracker/hardware
/usr/bin/python3.14 freerouting_pipeline.py \
    --board-type v2-adc \
    --output output/v2_adc_fixed.kicad_pcb \
    --max-passes 32 \
    --max-iterations 3
```

Notes:
- `--max-passes 32` (was 16) gives FreeRouting more rip-up retries internally.
- `--max-iterations 3` is plenty because each iteration is a fresh FreeRouting invocation (FreeRouting is internally stochastic, so the iterations are not identical — this is the only pipeline where >1 iteration makes sense).
- Verify the output: `violations ≤ 4` and `unconnected ≤ 10` after this step.

### Step 4 — Tighten placement if Step 3 still has > 10 unconnected

Edit component positions in `get_v1_fast_components()` and the V2 equivalent in `full_pipeline.py`. Specifically:

| Component | Current (x, y) | Suggested (x, y) | Why |
|-----------|---------------|------------------|-----|
| U4 (LDO) | (5, 22) | (8, 18) | Cluster with D1 and C_CAP |
| D1 (BAT54) | (4, 18) | (6, 18) | Move next to U4 |
| C1 | (8, 22) | (10, 20) | Tighter to U4 IN pin |
| C2 | (7, 24) | (10, 22) | Tighter to U4 OUT pin |
| U3 (GPS) | (6, 33) | (4, 28) | Closer to U1 GPIO1, shorter GPS_RX |
| R_PD | (10, 14) | (10.5, 13) | Tuck under U1 corner |
| R_LED, LED1 | (19,4), (16,4) | (20, 6), (22, 6) | Move out of F.Cu routing corridor |

Re-run Step 3 after each placement change. **Change one cluster at a time** so regressions are attributable.

### Step 5 — Manual finish in KiCad GUI (only if Step 3+4 leave > 0 unconnected)

The worker cannot run KiCad GUI headless. This step is for **Felix** (the human) or for the worker to escalate to the orchestrator with a request for human-in-the-loop time. Tasks:

1. Open `output/v2_adc_fixed.kicad_pcb` in `kicad` (GUI).
2. Run DRC interactively (`Inspect → Design Rules Checker`).
3. For each unconnected item, use the route tool (`X`) to lay a track. Power nets use 0.40 mm, signals 0.25 mm, RF 0.76 mm.
4. Re-run DRC until 0/0 or until only non-critical nets remain.
5. Save, then run `kicad-cli pcb export gerbers` headlessly for the JLCPCB upload.

**Quality gate before declaring V2 ready for fab:**
- 0 shorting_items violations
- 0 copper_edge_clearance violations
- 0 unconnected on critical nets (3V3, GND, SPI_*, LR2021_RST/BUSY/DIO9, GPS_RX, VCAP, SOLAR_IN)
- ≤ 2 unconnected on non-critical nets (STATUS_LED, FEM_TX, VDIV_MID, RF_*) is acceptable for prototype

### Step 6 — V1-FAST decision

After V2-ADC is at fab-ready state, decide on V1-FAST:

- **Recommended:** Skip V1-FAST fabrication. V2-ADC covers all V1-FAST functionality (ADC can be left unused in firmware). Saves a board slot in the JLCPCB order and 2+ hours of worker time.
- **If Felix insists on both boards:** Hand-route V1-FAST in KiCad GUI from the current `output/v1_fast_routed.kicad_pcb`. Estimated 90–120 min human time. Do not spend more worker cycles on auto-routing V1 — its 43 unconnected are dominated by the broken GND rail strategy (§1.4) and the A* router's structural deficits (§1.3).

---

## 4. What the Workers Did Wrong (Process Lessons for the Orchestrator)

1. **They trusted the iteration loop.** The loop's print statements say "ITERATION N/90" and "Continuing to next iteration" — that *looks* like progress but is not. Workers should have noticed that the violation counts did not change between iterations and escalated after iteration 2–3, not iteration 90.
2. **They pivoted tools mid-task without diagnosing why the first tool failed.** The pivot from A* to FreeRouting was correct, but it was done without first identifying the GPIO5/GPIO6 placement bug — so FreeRouting inherited the same unfixable violation.
3. **They did not read their own DRC JSON.** The `shorting_items` violation explicitly names GPIO5 and GPIO6 as the items shorting two different nets. That is a fingerprint of a placement bug. A 5-minute read of the DRC output on iteration 1 would have caught this.
4. **They did not inspect the `.kicad_pcb` pad geometry.** The pad positions are written in plaintext in the file. The collision is visible to the naked eye.

**Recommended circuit breaker for future PCB tasks:** "If violation count does not decrease for 3 consecutive iterations, STOP and write a failure analysis before iteration N+1." Add this to the kanban card body text.

---

## 5. File Hand-Off Summary

| File | Action | Owner |
|------|--------|-------|
| `tracker/hardware/full_pipeline.py` | Fix `make_esp32c3_pads()` (Step 1). Retire `main()`'s A* routing loop (Step 2). Keep board-creation + utility functions. | worker-balloon |
| `tracker/hardware/freerouting_pipeline.py` | Use as the only routing pipeline. No changes needed beyond passing `--max-passes 32`. | worker-balloon |
| `tracker/hardware/DRC_ROOT_CAUSE_ANALYSIS.md` | **Does not exist.** Create from §1 of this document (worker-facing version, may be more concise). | worker-balloon |
| `tracker/hardware/output/v2_adc_fixed.kicad_pcb` | Produce via Step 3. This is the V2 candidate for fab. | worker-balloon |
| `tracker/hardware/output/v1_fast_*` | Freeze. Do not spend more auto-route cycles on V1 until V2 is at fab. | orchestrator decision |
| `docs/coordination/PCB-DRC-CONSULTANT-STRATEGY.md` | This file. Source of truth for the unblocking plan. | PCB consultant |

---

## 6. One-Paragraph Summary for the Orchestrator's Status Report

Workers have been stuck at the DRC iteration budget because the iteration loop in `full_pipeline.py` is deterministic — it re-runs the same A* strategy with no parameter change, so 90 iterations produces the same output as 1. On top of that, the ESP32-C3 footprint has a pad-layout bug where the GPIO5 and GPIO6 pads (different nets) physically overlap on the module corner (0.901 mm center-to-center, 1.0 × 0.6 mm pads) — this is the source of every `shorting_items` violation and cannot be fixed by any router; it must be fixed in `make_esp32c3_pads()`. The recommended unblocking sequence is: (1) fix the pad collision, (2) stop using the A* loop — use `freerouting_pipeline.py` exclusively, (3) re-run FreeRouting on V2-ADC with the fixed placement, (4) hand-finish the remaining ≤ 10 unconnected items in KiCad GUI by Felix. V1-FAST should be de-prioritized; V2-ADC subsumes its functionality. Target: V2-ADC at fab-ready (0 critical unconnected) in one worker shift after the pad fix.
