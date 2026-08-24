# BALLOON PROJECT — COMPREHENSIVE STATUS SUMMARY
**Date:** 2026-08-05
**Prepared for:** Consultant review
**Goal:** Pico balloon + tollgate + FIPS mesh = DIY Starlink

---

## 1. WHAT WORKED

### Firmware
- **Radio task refactor** (commit 94bfe4c): blocking 5000ms recv() → 100ms poll. TX queue now serviced in 100ms vs 5000ms. Build succeeded.
- **Mesh build**: `CONFIG_ENABLE_MESH=y` compiles. balloon-tracker.bin = 227KB, 78% flash free.
- **Tollgate unit tests**: 119 passed, 0 failed (test_payment_proto.c).
- **FreeRTOS architecture design**: 3-task relay mode designed (radio_task, app_task, telemetry). Partially implemented.

### PCB Pipeline (toolchain proven)
- **Freerouting pipeline**: `ExportSpecctraDSN → Freerouting → ImportSpecctraSES` = WORKS. Coordinates handled automatically by SES import. NEVER parse DSN manually.
- **V2-ADC best board**: v2_adc_fixed2 = 0 violations, 16 unconnected (ALL power nets). Gerbers exported.
- **DRC verification**: kicad-cli pcb drc works reliably for headless DRC checks.
- **GPIO fix**: LED→GPIO9, FEM removed, ADC disabled for V1. Verified correct.

### Infrastructure
- **worker-layout profile created**: kimi-k3:cloud model for PCB spatial work. SOUL.md with proven toolchain.
- **Pipeline scripts committed**: freerouting_pipeline.py, finish_2layer.py, import scripts.
- **All work pushed** to github/felixfelix-bot/balloon-fresh, branch autonomous/mesh-baseline.

---

## 2. WHAT DIDN'T WORK

### PCB Design (the main struggle)
- **2-layer power routing**: Every attempt to route 3V3/GND/VCAP on 2 layers created shorts (straight tracks through signal pads). Nearest-neighbor chains cut through other pads. This is a fundamental placement problem, not a routing problem.
- **4-layer spec**: NEVER WRITTEN. 5 timeout failures (kimi-k3 ×3, glm-5.2 ×2). Task too complex for 300s subagent limit.
- **Manual DSN track import**: Y-axis negation bug — DSN uses negative Y, KiCad uses positive. Abandoned in favor of SES import.
- **Empty board bugs**: SaveBoard() sometimes produced empty boards (0 footprints). Concurrent file access (worker-balloon) caused races. Worker correctly refused to commit corrupted output.
- **kimi-k3 timeouts**: 300s limit too short. kimi-k3 takes ~30-40s per API call. 8-10 calls = timeout on every spatial task.

### Firmware
- **FreeRTOS task implementation** (deleg_96fba835): Timed out. Architecture designed but relay_task/app_task not fully implemented.
- **FIPS firmware**: critical-section API mismatch. Deeper dependency version issue. Parked.
- **secp256k1 build**: API mismatch between repo's secp version and expected function signatures.

### Process Issues
- **No physical boards**: ESP32-S3 boards don't have LR2021 radios wired. RP2040 boards have LR2021 but different firmware (PlatformIO). Can't bench-test relay firmware.
- **Context pollution**: Manager did too much mechanical PCB work directly (violating delegation rules).

---

## 3. WHAT STILL NEEDS DOING

### Critical Path (blocking flight)
1. **4-layer PCB design** — spec not written. Need compact 45x35mm board with GND+3V3 internal planes.
2. **Order boards from JLCPCB** — 2-week lead time. Nothing ordered yet.
3. **Bench test** — need LR2021 connected to ESP32 for radio testing.
4. **Relay firmware** — FreeRTOS tasks need completion. Design exists, implementation partial.

### Important (for tollgate integration)
5. **Tollgate + balloon integration** — Cashu payment on balloon relay nodes.
6. **Nostr store** — secp256k1 verify on received packets.

### Future (for FIPS mesh)
7. **FIPS firmware** — dependency issue needs resolution.
8. **Mesh relay protocol** — define packet format for multi-hop.

---

## 4. LESSONS LEARNED

1. **kimi-k3 for ALL spatial work** — proven superior to glm-5.2 on PCB routing. glm-5.2 created shorts every time.
2. **300s timeout = too short for PCB tasks** — use kanban (1800s) or pre-write scripts.
3. **ImportSpecctraSES** handles coordinates. NEVER manual DSN parsing.
4. **Power routing needs placement fix OR 4-layer** — can't route power on 2-layer with scattered pads.
5. **Pre-write scripts, delegate run-only** — avoids timeout on reasoning-heavy tasks.
6. **Verify footprint count > 0** after every SaveBoard().
7. **No concurrent file access** — worker-balloon collision caused corrupted boards.

---

## 5. LOWEST HANGING FRUIT

1. **Order 2-layer board NOW** (v2_adc_fixed2, 16 unconnected power pads). Felix finishes power routing in KiCad GUI (15 min). Order from JLCPCB. 2-week lead time starts today.
2. **Wire LR2021 to S3 board on breadboard** — enables bench testing relay firmware while waiting for PCB.
3. **Complete FreeRTOS relay tasks** — architecture designed, just needs implementation + build.
4. **4-layer spec as kanban task** — kimi-k3 via kanban (1800s timeout) instead of delegate_task (300s).

## 6. IMMEDIATELY ACTIONABLE STEPS

1. Felix: open v2_2LAYER_FINAL.kicad_pcb in KiCad, manually route 16 power pads, order from JLCPCB
2. Felix: wire LR2021 module to ESP32-S3 on breadboard for radio testing
3. Dispatch: FreeRTOS relay task completion as kanban task (firmware, not PCB)
4. Dispatch: 4-layer spec as kanban task to worker-layout (kimi-k3, 1800s timeout)
