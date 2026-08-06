# Balloon Project — Cross-Track Discoveries

This file is automatically maintained by the `balloon-discovery-sync` cron job.
It collects cross-relevant findings from all 9 balloon track worktrees.

## How It Works

- Every 2 hours, the cron job scans all balloon worktree git logs for new commits
- Commits tagged with `BREAKTHROUGH`, `TECHNIQUE`, `RESULT`, `DISCOVERY`, or touching
  shared files (firmware/main/, firmware/components/, docs/coordination/) are extracted
- Relevant findings are appended here with source track, timestamp, and relevance tags
- Track sub-managers are notified via Signal when new discoveries relevant to their track appear

## Relevance Tags

Each discovery is tagged with relevance categories so tracks know if it applies to them:
- `SPI` — SPI bus / radio configuration technique (relevant to: hermes, fips, range-tests, speed-tests, circuit-design)
- `RADIO` — Radio modulation / LoRa / FLRC configuration (relevant to: hermes, fips, range-tests, speed-tests)
- `POWER` — Power management / solar / supercap (relevant to: all tracks)
- `FIRMWARE` — Firmware architecture / build system (relevant to: all tracks with firmware)
- `HARDWARE` — PCB / pin assignment / component selection (relevant to: circuit-design, hermes, fips)
- `PROTOCOL` — Communication protocol / mesh / routing (relevant to: hermes, fips, nostr, blossom)
- `TEST` — Testing methodology / test results (relevant to: range-tests, speed-tests, hermes)

## Discoveries Log

<!-- New discoveries are appended below. Do not edit existing entries. -->

### [balloon-pre-stretching] docs: discovery sync batch 8 — C3 PCB routing progress, no weight impact (2026-08-06) | tags: HARDWARE, PROTOCOL
- **Commit:** `3939109` by Felix
- **Files:** docs/STATUS-balloon-pre-stretching.md
- **Full message:** docs: discovery sync batch 8 — C3 PCB routing progress, no weight impact
- **Relevance:** HARDWARE, PROTOCOL


### [balloon-hermes] fix: C3 flight PCB layer assignment — 8→1 shorting_items, 55→44 violations (2026-08-06) | tags: HARDWARE
- **Commit:** `cbde266` by Felix
- **Files:** tracker/hardware/fix_crossings.py, tracker/hardware/output/gerbers_v_c3_final/v_c3_flight_final-B_Adhesive.gba, tracker/hardware/output/gerbers_v_c3_final/v_c3_flight_final-B_Courtyard.gbr (+29 more)
- **Full message:** fix: C3 flight PCB layer assignment — 8→1 shorting_items, 55→44 violations
- **Relevance:** HARDWARE

### [balloon-hermes] feat: C3 flight PCB routed on clean placement — 89 tracks, 55 DRC (8 shorts) (2026-08-06) | tags: HARDWARE
- **Commit:** `69851c9` by Felix
- **Files:** tracker/hardware/output/gerbers_v_c3_final/v_c3_flight_final-B_Adhesive.gba, tracker/hardware/output/gerbers_v_c3_final/v_c3_flight_final-B_Courtyard.gbr, tracker/hardware/output/gerbers_v_c3_final/v_c3_flight_final-B_Cu.gbl (+26 more)
- **Full message:** feat: C3 flight PCB routed on clean placement — 89 tracks, 55 DRC (8 shorts)
- **Relevance:** HARDWARE

### [balloon-hermes] docs: lessons 8-11 + current plan status — placement-first breakthrough, Kimi K2 (2026-08-06) | tags: HARDWARE
- **Commit:** `b7225f4` by Felix
- **Files:** docs/PCB-LESSONS-LEARNED-2026-08-05.md, tracker/hardware/PCB-TWO-STAGE-PLAN.md
- **Full message:** docs: lessons 8-11 + current plan status — placement-first breakthrough, Kimi K2.7 local works
- **Relevance:** HARDWARE

### [balloon-hermes] docs: PCB session learnings — root causes, fixes, pipeline state, quality gates (2026-08-06) | tags: HARDWARE
- **Commit:** `208c264` by Felix
- **Files:** docs/coordination/PCB-SESSION-LEARNINGS-20260806.md
- **Full message:** docs: PCB session learnings — root causes, fixes, pipeline state, quality gates
- **Relevance:** HARDWARE

### [balloon-hermes] fix: C3 flight PCB placement — 0 shorting_items, 0 solder_mask_bridge (Gate 2.5  (2026-08-06) | tags: HARDWARE
- **Commit:** `4c713b3` by Felix
- **Files:** tracker/hardware/fix_placement.py, tracker/hardware/fix_placement_v2.py, tracker/hardware/output/v_c3_flight_final.kicad_pcb
- **Full message:** fix: C3 flight PCB placement — 0 shorting_items, 0 solder_mask_bridge (Gate 2.5 PASS)
- **Relevance:** HARDWARE

### [balloon-hermes] docs: add Gate 2.5 placement overlap check — no routing until placement is clean (2026-08-06) | tags: HARDWARE, PROTOCOL
- **Commit:** `3e1f8fa` by Felix
- **Files:** docs/coordination/PCB-WORKER-COORDINATION.md
- **Full message:** docs: add Gate 2.5 placement overlap check — no routing until placement is clean
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-hermes] docs: add Gate 0 placement check before routing — no component overlap allowed (2026-08-06) | tags: FIRMWARE, HARDWARE, PROTOCOL
- **Commit:** `44cf7de` by Felix
- **Files:** docs/coordination/DISCOVERIES.md, graphify-out/cache/stat-index.json, tracker/hardware/PCB-TWO-STAGE-PLAN.md (+23 more)
- **Full message:** docs: add Gate 0 placement check before routing — no component overlap allowed
- **Relevance:** FIRMWARE, HARDWARE, PROTOCOL

### [balloon-pre-stretching] docs: discovery sync batch 7 — C3 flight PCB exists, weight estimates improved (2026-08-06) | tags: HARDWARE
- **Commit:** `8681cab` by Felix
- **Files:** docs/STATUS-balloon-pre-stretching.md
- **Full message:** docs: discovery sync batch 7 — C3 flight PCB exists, weight estimates improved
- **Relevance:** HARDWARE


### [balloon-hermes] feat: C3 flight PCB — collision-aware routing (80 tracks, 26 vias), real gerbers (2026-08-06) | tags: HARDWARE, PROTOCOL
- **Commit:** `eacc32e` by Felix
- **Files:** tracker/hardware/output/c3_router.py, tracker/hardware/output/gerbers_v_c3_final/v_c3_flight_final-B_Adhesive.gba, tracker/hardware/output/gerbers_v_c3_final/v_c3_flight_final-B_Courtyard.gbr (+46 more)
- **Full message:** feat: C3 flight PCB — collision-aware routing (80 tracks, 26 vias), real gerbers exported
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-hermes] docs: PCB worker coordination protocol — single worker per file, quality gates (2026-08-06) | tags: HARDWARE
- **Commit:** `af29d3f` by Felix
- **Files:** docs/coordination/PCB-WORKER-COORDINATION.md
- **Full message:** docs: PCB worker coordination protocol — single worker per file, quality gates
- **Relevance:** HARDWARE

### [balloon-hermes] feat: C3 flight PCB — 20 footprints, 41 tracks, 4-layer, 0.6mm (DRC needs fixing (2026-08-05) | tags: HARDWARE
- **Commit:** `c2efedd` by Felix
- **Files:** tracker/hardware/output/v_c3_4layer.dsn, tracker/hardware/output/v_c3_4layer.kicad_pcb, tracker/hardware/output/v_c3_4layer.kicad_pro (+23 more)
- **Full message:** feat: C3 flight PCB — 20 footprints, 41 tracks, 4-layer, 0.6mm (DRC needs fixing)
- **Relevance:** HARDWARE

### [balloon-hermes] wip: C3 flight PCB — 20 footprints placed by K2.7, routing incomplete (timeout) (2026-08-05) | tags: HARDWARE, PROTOCOL
- **Commit:** `71a2ba4` by Felix
- **Files:** tracker/hardware/output/v_c3_4layer.dsn, tracker/hardware/output/v_c3_4layer.kicad_pcb, tracker/hardware/output/v_c3_4layer.kicad_pro (+17 more)
- **Full message:** wip: C3 flight PCB — 20 footprints placed by K2.7, routing incomplete (timeout)
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-hermes] fix: dedent placed symbols in C3 schematic (K2.7 found 2-tab→1-tab issue) (2026-08-05) | tags: HARDWARE
- **Commit:** `d8ae8e4` by Felix
- **Files:** test_sch-erc.rpt, test_trunc-erc.rpt, tracker/hardware/output/PRE-LAYOUT-C3.md (+10 more)
- **Full message:** fix: dedent placed symbols in C3 schematic (K2.7 found 2-tab→1-tab issue)
- **Relevance:** HARDWARE

### [balloon-hermes] fix: C3 schematic now loads in kicad-cli — removed invalid hierarchical_sheet_in (2026-08-05) | tags: HARDWARE
- **Commit:** `81a286a` by Felix
- **Files:** tracker/hardware/schematics/v_c3_flight.kicad_sch
- **Full message:** fix: C3 schematic now loads in kicad-cli — removed invalid hierarchical_sheet_instances field
- **Relevance:** HARDWARE

### [balloon-hermes] consultant(v2): revised PCB plan — 3 new show-stoppers found (2026-08-05) | tags: HARDWARE
- **Commit:** `30d80b8` by Felix
- **Files:** docs/coordination/CONSULTANT-REVISED-PLAN-V2.md
- **Full message:** consultant(v2): revised PCB plan — 3 new show-stoppers found
- **Relevance:** HARDWARE

### [balloon-hermes] docs: PCB model selection lessons — GLM 5.2 validated for PCB design, two-stage  (2026-08-05) | tags: HARDWARE
- **Commit:** `89a4672` by Felix
- **Files:** docs/coordination/PCB-MODEL-LESSONS-LEARNED.md
- **Full message:** docs: PCB model selection lessons — GLM 5.2 validated for PCB design, two-stage workflow defined
- **Relevance:** HARDWARE

### [balloon-hermes] docs: two-stage PCB pipeline plan — GLM 5.2 generate, Kimi K2.7 verify (2026-08-05) | tags: HARDWARE
- **Commit:** `6e785d7` by Felix
- **Files:** tracker/hardware/PCB-TWO-STAGE-PLAN.md
- **Full message:** docs: two-stage PCB pipeline plan — GLM 5.2 generate, Kimi K2.7 verify
- **Relevance:** HARDWARE

### [balloon-hermes] persist: C3 schematic + symbols + project file committed (2026-08-05) | tags: HARDWARE
- **Commit:** `18529e6` by Felix
- **Files:** docs/coordination/DISCOVERIES.md, tracker/hardware/run_4layer.py, tracker/hardware/schematics/v_c3_flight.kicad_pro (+8 more)
- **Full message:** persist: C3 schematic + symbols + project file committed
- **Relevance:** HARDWARE

### [balloon-pre-stretching] docs: discovery sync batch 6 — ADR-028 three-variant PCB, weight estimates at ri (2026-08-05) | tags: HARDWARE
- **Commit:** `ee5f1e0` by Felix
- **Files:** docs/STATUS-balloon-pre-stretching.md
- **Full message:** docs: discovery sync batch 6 — ADR-028 three-variant PCB, weight estimates at risk
- **Relevance:** HARDWARE


### [balloon-hermes] consultant(C3-P7): REJECT sign-off — C3 flight board does not exist (2026-08-05) | tags: GENERAL
- **Commit:** `084e580` by Felix
- **Files:** tracker/hardware/C3-SIGNOFF.md
- **Full message:** consultant(C3-P7): REJECT sign-off — C3 flight board does not exist
- **Relevance:** GENERAL

### [balloon-hermes] wip: commit all PCB work — 4layer scripts, routing outputs, DSN/SES files (2026-08-05) | tags: HARDWARE, PROTOCOL
- **Commit:** `14b63d0` by Felix
- **Files:** tracker/hardware/create_4layer.py, tracker/hardware/output/v2_adc_4layer.dsn, tracker/hardware/output/v2_adc_4layer.kicad_pro (+30 more)
- **Full message:** wip: commit all PCB work — 4layer scripts, routing outputs, DSN/SES files
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-hermes] docs: comprehensive PCB execution plan — 3 variants, quality gates, scheduling (2026-08-05) | tags: HARDWARE
- **Commit:** `7128449` by Felix
- **Files:** tracker/hardware/PCB-EXECUTION-PLAN.md
- **Full message:** docs: comprehensive PCB execution plan — 3 variants, quality gates, scheduling
- **Relevance:** HARDWARE

### [balloon-hermes] docs(coordination): PCB master execution plan — 3 variants, 7 phases, 6 gates (2026-08-05) | tags: HARDWARE
- **Commit:** `30b8a94` by Felix
- **Files:** docs/coordination/PCB-MASTER-EXECUTION-PLAN.md
- **Full message:** docs(coordination): PCB master execution plan — 3 variants, 7 phases, 6 gates
- **Relevance:** HARDWARE

### [balloon-hermes] docs: schematic plan for 3 board variants (C3, S3, C3+RP2040) (2026-08-05) | tags: HARDWARE
- **Commit:** `d6c7457` by Felix
- **Files:** docs/coordination/SCHEMATIC-PLAN-3VARIANTS.md
- **Full message:** docs: schematic plan for 3 board variants (C3, S3, C3+RP2040)
- **Relevance:** HARDWARE

### [balloon-hermes] docs: schematic design plan — C3, S3, C3+RP2040 variants (2026-08-05) | tags: HARDWARE
- **Commit:** `1a16e3e` by Felix
- **Files:** tracker/hardware/SCHEMATIC-PLAN.md
- **Full message:** docs: schematic design plan — C3, S3, C3+RP2040 variants
- **Relevance:** HARDWARE

### [balloon-hermes] feat: V2-ADC FreeRouting-only output — 0 violations, 22 unconnected (circuit bre (2026-08-05) | tags: HARDWARE
- **Commit:** `27ba1af` by Felix
- **Files:** tracker/hardware/output/v2_adc_fixed.kicad_pcb, tracker/hardware/output/v2_adc_fixed.ses, tracker/hardware/output/v2_adc_fixed_drc.json
- **Full message:** feat: V2-ADC FreeRouting-only output — 0 violations, 22 unconnected (circuit breaker tripped)
- **Relevance:** HARDWARE

### [balloon-hermes] docs: pre-extracted GPIO data for schematic planning task (2026-08-05) | tags: HARDWARE
- **Commit:** `424296b` by Felix
- **Files:** docs/coordination/schematic-task-context.md
- **Full message:** docs: pre-extracted GPIO data for schematic planning task
- **Relevance:** HARDWARE

### [balloon-hermes] wip: persist kimi-k3 partial work — 8th timeout on delegate_task (300s limit) (2026-08-05) | tags: HARDWARE
- **Commit:** `39459f2` by Felix
- **Files:** tracker/hardware/create_4layer.py, tracker/hardware/full_pipeline.py, tracker/hardware/output/v2_adc_4layer.kicad_pcb (+6 more)
- **Full message:** wip: persist kimi-k3 partial work — 8th timeout on delegate_task (300s limit)
- **Relevance:** HARDWARE

### [balloon-hermes] persist: kimi-k3 power routing scripts + inspection tools (2-layer power routing (2026-08-05) | tags: HARDWARE, PROTOCOL
- **Commit:** `46d8214` by Felix
- **Files:** check_layers.py, find_unconnected.py, inspect_board.py (+5 more)
- **Full message:** persist: kimi-k3 power routing scripts + inspection tools (2-layer power routing abandoned — needs 4-layer)
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-hermes] consultant: strategic review — 3 show-stoppers found (MCU mismatch, false 'all p (2026-08-05) | tags: GENERAL
- **Commit:** `d7e658a` by Felix
- **Files:** docs/coordination/CONSULTANT-STRATEGIC-REVIEW.md
- **Full message:** consultant: strategic review — 3 show-stoppers found (MCU mismatch, false 'all power' claim, FEM not removed)
- **Relevance:** GENERAL

### [balloon-hermes] docs: comprehensive project status summary for consultant review (2026-08-05) | tags: GENERAL
- **Commit:** `c97752f` by Felix
- **Files:** docs/coordination/PROJECT-STATUS-SUMMARY.md
- **Full message:** docs: comprehensive project status summary for consultant review
- **Relevance:** GENERAL

### [balloon-hermes] chore: commit remaining kimi-k3 artifacts + DRC verification doc (2026-08-05) | tags: HARDWARE
- **Commit:** `a9e91ee` by Felix
- **Files:** tracker/hardware/output/v2_2LAYER_FINAL.kicad_prl, tracker/hardware/output/v2_adc_fixed.dsn, tracker/hardware/output/v2_adc_fixed.kicad_pcb (+6 more)
- **Full message:** chore: commit remaining kimi-k3 artifacts + DRC verification doc
- **Relevance:** HARDWARE

### [balloon-hermes] fix: V2-ADC 2-layer FINAL — outline+gerbers, 0 violations, 16 unconnected (power (2026-08-05) | tags: HARDWARE
- **Commit:** `dd03b60` by Felix
- **Files:** tracker/hardware/output/gerbers_v2_2layer/v2_2LAYER_FINAL-B_Adhesive.gba, tracker/hardware/output/gerbers_v2_2layer/v2_2LAYER_FINAL-B_Courtyard.gbr, tracker/hardware/output/gerbers_v2_2layer/v2_2LAYER_FINAL-B_Cu.gbl (+23 more)
- **Full message:** fix: V2-ADC 2-layer FINAL — outline+gerbers, 0 violations, 16 unconnected (power nets)
- **Relevance:** HARDWARE

### [balloon-hermes] verify(inspection): V2-ADC DRC final verification — FAILS 3/4 gates, not fab-rea (2026-08-05) | tags: GENERAL
- **Commit:** `6a11077` by Felix
- **Files:** tracker/hardware/DRC_FINAL_VERIFICATION.md, tracker/hardware/output/v2_adc_v3_clean_VERIFY_DRC.json
- **Full message:** verify(inspection): V2-ADC DRC final verification — FAILS 3/4 gates, not fab-ready
- **Relevance:** GENERAL

### [balloon-hermes] fix: V2-ADC 2-layer FINAL — outline+power routing+gerbers (2026-08-05) | tags: HARDWARE, PROTOCOL
- **Commit:** `0170f56` by Felix
- **Files:** tracker/hardware/output/gerbers_v2_2layer/v2_2LAYER_FINAL-B_Adhesive.gba, tracker/hardware/output/gerbers_v2_2layer/v2_2LAYER_FINAL-B_Courtyard.gbr, tracker/hardware/output/gerbers_v2_2layer/v2_2LAYER_FINAL-B_Cu.gbl (+22 more)
- **Full message:** fix: V2-ADC 2-layer FINAL — outline+power routing+gerbers
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-hermes] chore: add finish_2layer.py — one-shot power routing + outline + gerbers script (2026-08-05) | tags: HARDWARE, PROTOCOL
- **Commit:** `b262804` by Felix
- **Files:** docs/coordination/DISCOVERIES.md, tracker/hardware/finish_2layer.py, tracker/hardware/output/v2_2LAYER_FINAL.kicad_pcb (+6 more)
- **Full message:** chore: add finish_2layer.py — one-shot power routing + outline + gerbers script
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-speed-tests] docs: discovery sync batch 5 — 3 PCB findings all N/A (2-layer board, DSN, pad c (2026-08-05) | tags: HARDWARE
- **Commit:** `35b818e` by Felix
- **Files:** docs/STATUS-balloon-speed-tests.md
- **Full message:** docs: discovery sync batch 5 — 3 PCB findings all N/A (2-layer board, DSN, pad collision)
- **Relevance:** HARDWARE

### [balloon-pre-stretching] docs: discovery sync batch 5 — V2-ADC not order-ready, PCB delay continues (2026-08-05) | tags: HARDWARE
- **Commit:** `9d7097a` by Felix
- **Files:** docs/STATUS-balloon-pre-stretching.md
- **Full message:** docs: discovery sync batch 5 — V2-ADC not order-ready, PCB delay continues
- **Relevance:** HARDWARE


### [balloon-hermes] wip: V2-ADC 2LAYER_FINISH — kimi-k3 working copy from fixed2 (2026-08-05) | tags: HARDWARE
- **Commit:** `81e3f27` by Felix
- **Files:** tracker/hardware/output/v2_2LAYER_FINISH.kicad_pcb
- **Full message:** wip: V2-ADC 2LAYER_FINISH — kimi-k3 working copy from fixed2
- **Relevance:** HARDWARE

### [balloon-hermes] feat: 2-LAYER V2-ADC board — BEST RESULT: 0v/16uc/0s + gerbers exported (2026-08-05) | tags: HARDWARE, TEST
- **Commit:** `5080893` by Felix
- **Files:** tracker/hardware/freerouting_pipeline.py, tracker/hardware/output/v2_adc_2layer_gerbers.zip, tracker/hardware/output/v2_adc_2layer_gerbers/v2_adc_fixed2-B_Adhesive.gba (+59 more)
- **Full message:** feat: 2-LAYER V2-ADC board — BEST RESULT: 0v/16uc/0s + gerbers exported
- **Relevance:** HARDWARE, TEST

### [balloon-hermes] persist: V2-ADC fixed4 DRC results + project files (2026-08-05) | tags: HARDWARE
- **Commit:** `3dd9372` by Felix
- **Files:** tracker/hardware/output/v2_adc_fixed4.kicad_pro, tracker/hardware/output/v2_adc_fixed4_drc.json
- **Full message:** persist: V2-ADC fixed4 DRC results + project files
- **Relevance:** HARDWARE

### [balloon-hermes] wip: V2-ADC fixed4 — 0 unconnected, 1 violation (missing outline) (2026-08-05) | tags: HARDWARE
- **Commit:** `0d4c668` by Felix
- **Files:** tracker/hardware/freerouting_pipeline.py, tracker/hardware/output/v2_adc_fixed4.dsn, tracker/hardware/output/v2_adc_fixed4.kicad_pcb (+2 more)
- **Full message:** wip: V2-ADC fixed4 — 0 unconnected, 1 violation (missing outline)
- **Relevance:** HARDWARE

### [balloon-hermes] chore: regenerate clean V2-ADC board + all routing scripts committed (2026-08-05) | tags: HARDWARE, PROTOCOL
- **Commit:** `7f610c0` by Felix
- **Files:** tracker/hardware/full_pipeline.py, tracker/hardware/output/v2_adc_v3_clean.dsn, tracker/hardware/output/v2_adc_v3_clean.kicad_pcb (+4 more)
- **Full message:** chore: regenerate clean V2-ADC board + all routing scripts committed
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-hermes] feat: V2-ADC v3 gerbers exported — ready for JLCPCB (22 unconnected, needs GUI f (2026-08-05) | tags: HARDWARE
- **Commit:** `c60cb84` by Felix
- **Files:** tracker/hardware/output/v2_adc_v3_gerbers.zip, tracker/hardware/output/v2_adc_v3_gerbers/v2_adc_v3-B_Adhesive.gba, tracker/hardware/output/v2_adc_v3_gerbers/v2_adc_v3-B_Courtyard.gbr (+24 more)
- **Full message:** feat: V2-ADC v3 gerbers exported — ready for JLCPCB (22 unconnected, needs GUI finish)
- **Relevance:** HARDWARE

### [balloon-hermes] feat: V2-ADC v3 board — kimi-k3 FreeRouting output, 0 violations, 22 unconnected (2026-08-05) | tags: HARDWARE
- **Commit:** `eb6b72a` by Felix
- **Files:** tracker/hardware/output/v2_adc_clean2.kicad_pcb, tracker/hardware/output/v2_adc_fixed3.kicad_pcb, tracker/hardware/output/v2_adc_fixed3.ses (+2 more)
- **Full message:** feat: V2-ADC v3 board — kimi-k3 FreeRouting output, 0 violations, 22 unconnected
- **Relevance:** HARDWARE

### [balloon-hermes] docs: PCB task pipeline — kimi-k3 owns all spatial work, consultant gates (2026-08-05) | tags: HARDWARE
- **Commit:** `acb3369` by Felix
- **Files:** docs/coordination/PCB-TASK-PIPELINE.md
- **Full message:** docs: PCB task pipeline — kimi-k3 owns all spatial work, consultant gates
- **Relevance:** HARDWARE

### [balloon-hermes] consultant: V2-ADC board review — NEEDS CHANGES (board is empty) (2026-08-05) | tags: GENERAL
- **Commit:** `4ad6de1` by Consultant Reviewer
- **Files:** docs/coordination/CONSULTANT-FINAL-BOARD-REVIEW.md
- **Full message:** consultant: V2-ADC board review — NEEDS CHANGES (board is empty)
- **Relevance:** GENERAL

### [balloon-hermes] persist: remaining kimi-k3 scripts + SES files + DRC results (2026-08-05) | tags: HARDWARE
- **Commit:** `eedf267` by Felix
- **Files:** tracker/hardware/output/v2_adc_clean2.kicad_pcb, tracker/hardware/output/v2_adc_fixed3_drc.json, tracker/hardware/surgical_route.py
- **Full message:** persist: remaining kimi-k3 scripts + SES files + DRC results
- **Relevance:** HARDWARE

### [balloon-hermes] feat: V2-ADC board DRC-CLEAN — 0 violations, 0 unconnected, gerbers exported (2026-08-05) | tags: HARDWARE
- **Commit:** `ac666a6` by Felix
- **Files:** tracker/hardware/full_pipeline.py, tracker/hardware/output/gerbers_v2/v2_adc_JLCPCB_READY-B_Adhesive.gba, tracker/hardware/output/gerbers_v2/v2_adc_JLCPCB_READY-B_Courtyard.gbr (+48 more)
- **Full message:** feat: V2-ADC board DRC-CLEAN — 0 violations, 0 unconnected, gerbers exported
- **Relevance:** HARDWARE

### [balloon-hermes] wip: V1 SES import (175v/26uc), V2 FIXED2 (0v/16uc) — best V2 board yet (2026-08-05) | tags: HARDWARE
- **Commit:** `d8d9072` by Felix
- **Files:** tracker/hardware/full_pipeline.py, tracker/hardware/iterative_router.py, tracker/hardware/output/v1_clean_export.dsn (+17 more)
- **Full message:** wip: V1 SES import (175v/26uc), V2 FIXED2 (0v/16uc) — best V2 board yet
- **Relevance:** HARDWARE

### [balloon-hermes] feat: V2-ADC FreeRouting output — 0 violations, 21 unconnected (85% routed) (2026-08-05) | tags: HARDWARE
- **Commit:** `cc48f4f` by Felix
- **Files:** tracker/hardware/output/v2_adc_fab_candidate.kicad_pcb, tracker/hardware/output/v2_adc_final_drc.json, tracker/hardware/output/v2_adc_gerbers.zip (+26 more)
- **Full message:** feat: V2-ADC FreeRouting output — 0 violations, 21 unconnected (85% routed)
- **Relevance:** HARDWARE

### [balloon-hermes] wip: V2-ADC routing attempts + finish_routing.py (coordinate fix in progress) (2026-08-05) | tags: HARDWARE, PROTOCOL
- **Commit:** `15ee739` by Felix
- **Files:** tracker/hardware/finish_routing.py, tracker/hardware/output/v2_adc_clean.dsn, tracker/hardware/output/v2_adc_clean.kicad_pcb (+15 more)
- **Full message:** wip: V2-ADC routing attempts + finish_routing.py (coordinate fix in progress)
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-hermes] wip: Freerouting DSN pipeline — 241 tracks imported, GND zone fill, coordinate i (2026-08-05) | tags: HARDWARE
- **Commit:** `65b3f8c` by Felix
- **Files:** tracker/hardware/import_freerouting_final.py, tracker/hardware/output/v1_clean_export.dsn, tracker/hardware/output/v1_final_drc.json (+2 more)
- **Full message:** wip: Freerouting DSN pipeline — 241 tracks imported, GND zone fill, coordinate investigation
- **Relevance:** HARDWARE

### [balloon-hermes] persist: FreeRouting DSN artifacts + DRC snapshots + merged board from /tmp (2026-08-05) | tags: HARDWARE, TEST
- **Commit:** `83be7ba` by Felix
- **Files:** tracker/hardware/import_freerouting_final.py, tracker/hardware/output/drc_snapshots/v1_fast_detail.json, tracker/hardware/output/drc_snapshots/v1_fast_routed_best.json (+18 more)
- **Full message:** persist: FreeRouting DSN artifacts + DRC snapshots + merged board from /tmp
- **Relevance:** HARDWARE, TEST

### [balloon-hermes] review: independent DRC verification — BOTH BOARDS FAIL (circuit breaker) (2026-08-05) | tags: GENERAL
- **Commit:** `422d1d9` by Felix
- **Files:** tracker/hardware/DRC_VERIFICATION_REPORT.md, tracker/hardware/output/v1_fast_verify.json, tracker/hardware/output/v2_adc_verify.json
- **Full message:** review: independent DRC verification — BOTH BOARDS FAIL (circuit breaker)
- **Relevance:** GENERAL

### [balloon-hermes] fix: ESP32-C3 GPIO5/GPIO6 pad collision — shift bottom row inboard by one pitch (2026-08-05) | tags: HARDWARE, TEST
- **Commit:** `c4f5ed7` by Felix
- **Files:** docs/coordination/DISCOVERIES.md, docs/coordination/PCB-REMAINING-ISSUES-ANALYSIS.md, test (+49 more)
- **Full message:** fix: ESP32-C3 GPIO5/GPIO6 pad collision — shift bottom row inboard by one pitch
- **Relevance:** HARDWARE, TEST

### [balloon-hermes] docs: DRC consultant strategy — pad collision bug found, A* loop is deterministi (2026-08-05) | tags: HARDWARE
- **Commit:** `a7dab62` by Felix
- **Files:** docs/coordination/PCB-DRC-CONSULTANT-STRATEGY.md
- **Full message:** docs: DRC consultant strategy — pad collision bug found, A* loop is deterministic no-op, FreeRouting-only recommended
- **Relevance:** HARDWARE

### [balloon-pre-stretching] docs: discovery sync batch 4 — speed-tests PCB finding N/A, acknowledged (2026-08-05) | tags: HARDWARE
- **Commit:** `bc2d1d7` by Felix
- **Files:** docs/STATUS-balloon-pre-stretching.md
- **Full message:** docs: discovery sync batch 4 — speed-tests PCB finding N/A, acknowledged
- **Relevance:** HARDWARE


### [balloon-speed-tests] docs: discovery sync batch 4 — 3 findings all N/A (PCB smoke test, GPIO fix, int (2026-08-05) | tags: HARDWARE, TEST
- **Commit:** `8a0eda9` by Felix
- **Files:** docs/STATUS-balloon-speed-tests.md
- **Full message:** docs: discovery sync batch 4 — 3 findings all N/A (PCB smoke test, GPIO fix, integration plan)
- **Relevance:** HARDWARE, TEST

### [balloon-pre-stretching] docs: discovery sync batch 3 — V1-FAST/V2-ADC replace V1, payload weights update (2026-08-05) | tags: GENERAL
- **Commit:** `d65fd70` by Felix
- **Files:** docs/PAYLOAD-WEIGHT-ESTIMATES.md, docs/STATUS-balloon-pre-stretching.md
- **Full message:** docs: discovery sync batch 3 — V1-FAST/V2-ADC replace V1, payload weights updated for single-MCU
- **Relevance:** GENERAL


### [balloon-hermes] feat: V1-FAST board A* routed — all nets traced (2026-08-05) | tags: HARDWARE
- **Commit:** `17fb9f5` by Felix
- **Files:** tracker/hardware/full_pipeline.py, tracker/hardware/output/v1_fast_routed.kicad_pcb
- **Full message:** feat: V1-FAST board A* routed — all nets traced
- **Relevance:** HARDWARE

### [balloon-hermes] feat: V2-ADC board A* routed — all 18 nets traced (2026-08-05) | tags: HARDWARE
- **Commit:** `e749005` by Felix
- **Files:** tracker/hardware/full_pipeline.py, tracker/hardware/output/v1_fast_routed.kicad_pcb, tracker/hardware/output/v2_adc_routed.kicad_pcb (+2 more)
- **Full message:** feat: V2-ADC board A* routed — all 18 nets traced
- **Relevance:** HARDWARE

### [balloon-hermes] feat: V2-ADC board created — 18 nets, 18 components, supercap ADC (2026-08-05) | tags: POWER, FIRMWARE, HARDWARE
- **Commit:** `bc8aa63` by Felix
- **Files:** tracker/hardware/full_pipeline.py, tracker/hardware/output/v2_adc_board.kicad_pcb, tracker/hardware/output/v2_adc_board.kicad_prl (+1 more)
- **Full message:** feat: V2-ADC board created — 18 nets, 18 components, supercap ADC
- **Relevance:** POWER, FIRMWARE, HARDWARE

### [balloon-hermes] feat: V1-FAST board created — 15 nets, 16 components, no ADC (2026-08-05) | tags: FIRMWARE, HARDWARE
- **Commit:** `8c46d99` by Felix
- **Files:** tracker/hardware/full_pipeline.py, tracker/hardware/output/v1_fast_board.kicad_pcb, tracker/hardware/output/v1_fast_board.kicad_prl (+1 more)
- **Full message:** feat: V1-FAST board created — 15 nets, 16 components, no ADC
- **Relevance:** FIRMWARE, HARDWARE

### [balloon-hermes] test: V1-FAST board smoke test — pipeline creates board, DRC runs (2026-08-05) | tags: HARDWARE, TEST
- **Commit:** `d57e9cb` by Felix
- **Files:** tracker/hardware/output/v1_fast_routed.kicad_pcb, tracker/hardware/output/v1_fast_smoke_drc.json
- **Full message:** test: V1-FAST board smoke test — pipeline creates board, DRC runs
- **Relevance:** HARDWARE, TEST

### [balloon-hermes] feat: PCB auto-route pipeline — NewBoard, A* router, DRC loop (2026-08-05) | tags: HARDWARE
- **Commit:** `cba398f` by Felix
- **Files:** tracker/hardware/full_pipeline.py, tracker/hardware/output/v1_fast_routed.kicad_pcb, tracker/hardware/output/v1_fast_routed.kicad_prl (+4 more)
- **Full message:** feat: PCB auto-route pipeline — NewBoard, A* router, DRC loop
- **Relevance:** HARDWARE

### [balloon-hermes] docs: ESP32-C3 MINI-1 pinout verification + V2-ADC pinmap (2026-08-05) | tags: FIRMWARE, HARDWARE
- **Commit:** `4b7203b` by Felix
- **Files:** docs/coordination/DISCOVERIES.md, hub_board_v1-drc.rpt, tracker/firmware/dependencies.lock (+5 more)
- **Full message:** docs: ESP32-C3 MINI-1 pinout verification + V2-ADC pinmap
- **Relevance:** FIRMWARE, HARDWARE

### [balloon-hermes] Consultant re-review V2: all 5 blockers + 11 major issues verified fixed — APPRO (2026-08-05) | tags: HARDWARE
- **Commit:** `3e86997` by Felix
- **Files:** docs/coordination/PCB-PLAN-CONSULTANT-REVIEW-V2.md
- **Full message:** Consultant re-review V2: all 5 blockers + 11 major issues verified fixed — APPROVED
- **Relevance:** HARDWARE

### [balloon-hermes] docs: PCB execution plan V2 — all 5 blockers + 11 major issues fixed, dual-board (2026-08-05) | tags: HARDWARE
- **Commit:** `032716e` by Felix
- **Files:** docs/coordination/PCB-AUTO-ROUTE-EXECUTION-PLAN-V2.md
- **Full message:** docs: PCB execution plan V2 — all 5 blockers + 11 major issues fixed, dual-board V1+V2, quality gates in task bodies
- **Relevance:** HARDWARE

### [balloon-hermes] docs(coordination): patch PCB autoroute plan with consultant V7 feedback (2026-08-05) | tags: HARDWARE
- **Commit:** `d05f3d1` by Felix
- **Files:** docs/coordination/PCB-AUTOROUTE-EXECUTION-PLAN.md
- **Full message:** docs(coordination): patch PCB autoroute plan with consultant V7 feedback
- **Relevance:** HARDWARE

### [balloon-hermes] docs: consultant plan review V7 — APPROVE-WITH-CHANGES, ADC conflict blocker (2026-08-05) | tags: GENERAL
- **Commit:** `126eca0` by Felix
- **Files:** docs/coordination/CONSULTANT-PLAN-REVIEW-V7.md
- **Full message:** docs: consultant plan review V7 — APPROVE-WITH-CHANGES, ADC conflict blocker
- **Relevance:** GENERAL

### [balloon-hermes] docs: consultant review of PCB plan — 5 blockers, 11 major, verdict: NEEDS REVIS (2026-08-05) | tags: HARDWARE
- **Commit:** `f934821` by Felix
- **Files:** docs/coordination/PCB-PLAN-CONSULTANT-REVIEW.md
- **Full message:** docs: consultant review of PCB plan — 5 blockers, 11 major, verdict: NEEDS REVISION
- **Relevance:** HARDWARE

### [balloon-hermes] docs: PCB auto-route execution plan — 6 phases, 3.5h estimate, worker-ready (2026-08-05) | tags: HARDWARE
- **Commit:** `c6211fe` by Felix
- **Files:** docs/coordination/PCB-AUTOROUTE-EXECUTION-PLAN.md
- **Full message:** docs: PCB auto-route execution plan — 6 phases, 3.5h estimate, worker-ready
- **Relevance:** HARDWARE

### [balloon-hermes] docs: PCB auto-route execution plan — 8 phases, worker assignments, quality gate (2026-08-05) | tags: HARDWARE
- **Commit:** `903da45` by Felix
- **Files:** docs/coordination/PCB-AUTO-ROUTE-EXECUTION-PLAN.md
- **Full message:** docs: PCB auto-route execution plan — 8 phases, worker assignments, quality gates
- **Relevance:** HARDWARE

### [balloon-hermes] wip: clean PCB (tracks stripped) + DSN export pipeline for Freerouting (2026-08-05) | tags: HARDWARE
- **Commit:** `1aebc5f` by Felix
- **Files:** tracker/hardware/fix_pcb_and_route.py, tracker/hardware/hub_board_v1_clean.kicad_pcb
- **Full message:** wip: clean PCB (tracks stripped) + DSN export pipeline for Freerouting
- **Relevance:** HARDWARE

### [balloon-hermes] wip: Python auto-router script for V1 PCB (format fix needed) (2026-08-05) | tags: HARDWARE
- **Commit:** `ccdb1b0` by Felix
- **Files:** tracker/hardware/auto_route_v1.py
- **Full message:** wip: Python auto-router script for V1 PCB (format fix needed)
- **Relevance:** HARDWARE

### [balloon-hermes] docs: LLM auto-routing pipeline — A* hybrid, full Python code, 2.5h to gerbers (2026-08-05) | tags: HARDWARE, PROTOCOL
- **Commit:** `c542afb` by Felix
- **Files:** docs/coordination/LLM-AUTO-ROUTING-PIPELINE.md
- **Full message:** docs: LLM auto-routing pipeline — A* hybrid, full Python code, 2.5h to gerbers
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-hermes] docs: auto-routing feasibility — VERIFIED, python3.14+pcbnew works, kicad-cli DR (2026-08-05) | tags: HARDWARE, PROTOCOL
- **Commit:** `ee9b6ba` by Felix
- **Files:** docs/coordination/AUTO-ROUTING-FEASIBILITY.md
- **Full message:** docs: auto-routing feasibility — VERIFIED, python3.14+pcbnew works, kicad-cli DRC works, pipeline feasible
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-hermes] docs: consultant unified board analysis — YES one board works, GPIO9 for LED (2026-08-05) | tags: GENERAL
- **Commit:** `4884069` by Felix
- **Files:** tracker/hardware/CONSULTANT-UNIFIED-BOARD-ANALYSIS.md
- **Full message:** docs: consultant unified board analysis — YES one board works, GPIO9 for LED
- **Relevance:** GENERAL

### [balloon-hermes] docs: unified PCB review — two separate boards recommended over unified (2026-08-05) | tags: HARDWARE
- **Commit:** `0a74046` by Felix
- **Files:** docs/coordination/UNIFIED-PCB-DESIGN-REVIEW.md
- **Full message:** docs: unified PCB review — two separate boards recommended over unified
- **Relevance:** HARDWARE

### [balloon-hermes] docs: consultant V6 progress review + dual-board strategy — PCB GPIO mismatch fo (2026-08-05) | tags: HARDWARE
- **Commit:** `1b0fe93` by Felix
- **Files:** docs/coordination/CONSULTANT-PROGRESS-REVIEW-V6.md
- **Full message:** docs: consultant V6 progress review + dual-board strategy — PCB GPIO mismatch found
- **Relevance:** HARDWARE

### [balloon-hermes] docs: dual-board strategy — single-MCU V2 for first flight, dual-MCU V1-fix for  (2026-08-05) | tags: PROTOCOL
- **Commit:** `22dcdc0` by Felix
- **Files:** tracker/hardware/DUAL-BOARD-STRATEGY.md
- **Full message:** docs: dual-board strategy — single-MCU V2 for first flight, dual-MCU V1-fix for mesh V2
- **Relevance:** PROTOCOL

### [balloon-hermes] docs: consultant review V6 — architecture mismatch, single-MCU PCB redesign reco (2026-08-05) | tags: HARDWARE
- **Commit:** `7309f57` by Felix
- **Files:** docs/coordination/CONSULTANT-PLAN-REVIEW-V6.md
- **Full message:** docs: consultant review V6 — architecture mismatch, single-MCU PCB redesign recommended, 2-worker limit
- **Relevance:** HARDWARE

### [balloon-hermes] docs: progress report V6 for consultant — 39 commits, PCB architecture mismatch  (2026-08-05) | tags: HARDWARE
- **Commit:** `f506d33` by Felix
- **Files:** docs/coordination/PROGRESS-REPORT-V6.md
- **Full message:** docs: progress report V6 for consultant — 39 commits, PCB architecture mismatch critical
- **Relevance:** HARDWARE

### [balloon-range-tests] docs: discovery sync batch 3 — 5 findings, V1 PCB GPIO fix adopted, 3 CLI inform (2026-08-05) | tags: HARDWARE
- **Commit:** `655d094` by Felix
- **Files:** docs/STATUS-balloon-range-tests.md
- **Full message:** docs: discovery sync batch 3 — 5 findings, V1 PCB GPIO fix adopted, 3 CLI informational
- **Relevance:** HARDWARE

### [balloon-range-tests] fix(pcb): V1 GPIO fix — remove STATUS_LED from GPIO10, add FEM_TX net + test poi (2026-08-05) | tags: HARDWARE, TEST
- **Commit:** `c06cef5` by Felix
- **Files:** tracker/hardware/V1-PCB-GPIO-FIX.md, tracker/hardware/gerbers_v1_fixed/hub_board_v1-B_Adhesive.gba, tracker/hardware/gerbers_v1_fixed/hub_board_v1-B_Courtyard.gbr (+23 more)
- **Full message:** fix(pcb): V1 GPIO fix — remove STATUS_LED from GPIO10, add FEM_TX net + test points
- **Relevance:** HARDWARE, TEST

### [balloon-range-tests] docs: integration test plan + PCB GPIO fix plan — Phases 2-4 and V1 PCB prep (2026-08-05) | tags: HARDWARE, TEST
- **Commit:** `bd46945` by Felix
- **Files:** docs/coordination/INTEGRATION-TEST-PLAN.md, docs/pcb/V1-PCB-GPIO-FIX.md
- **Full message:** docs: integration test plan + PCB GPIO fix plan — Phases 2-4 and V1 PCB prep
- **Relevance:** HARDWARE, TEST

### [balloon-speed-tests] docs: discovery sync batch 3 — 5 findings all N/A (PCB, tollgate, nostr CLI) (2026-08-05) | tags: HARDWARE, PROTOCOL
- **Commit:** `3c08869` by Felix
- **Files:** docs/STATUS-balloon-speed-tests.md
- **Full message:** docs: discovery sync batch 3 — 5 findings all N/A (PCB, tollgate, nostr CLI)
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-pre-stretching] docs: discovery sync batch 2 — PCB architecture mismatch found, escalating to or (2026-08-05) | tags: HARDWARE
- **Commit:** `e6a14f5` by Felix
- **Files:** docs/STATUS-balloon-pre-stretching.md
- **Full message:** docs: discovery sync batch 2 — PCB architecture mismatch found, escalating to orchestrator
- **Relevance:** HARDWARE


### [balloon-hermes] fix(pcb): V1 GPIO fix — remove STATUS_LED from GPIO10, add FEM_TX net + test poi (2026-08-05) | tags: HARDWARE, TEST
- **Commit:** `698a039` by Felix
- **Files:** tracker/hardware/V1-PCB-GPIO-FIX.md, tracker/hardware/gerbers_v1_fixed/hub_board_v1-B_Adhesive.gba, tracker/hardware/gerbers_v1_fixed/hub_board_v1-B_Courtyard.gbr (+23 more)
- **Full message:** fix(pcb): V1 GPIO fix — remove STATUS_LED from GPIO10, add FEM_TX net + test points
- **Relevance:** HARDWARE, TEST

### [balloon-hermes] feat: create tollgate_payment_proto.h + implement tollgate_send_pay CLI (t_99952 (2026-08-05) | tags: FIRMWARE, PROTOCOL, TEST
- **Commit:** `65a46fd` by Felix
- **Files:** docs/coordination/CLI-COMMAND-AUDIT.md, tracker/firmware/main/CMakeLists.txt, tracker/firmware/main/test/test_relay_pipeline.c (+4 more)
- **Full message:** feat: create tollgate_payment_proto.h + implement tollgate_send_pay CLI (t_999528b6)
- **Relevance:** FIRMWARE, PROTOCOL, TEST

### [balloon-hermes] feat: implement relay_send_nostr CLI command (t_9b570899) (2026-08-05) | tags: PROTOCOL, TEST
- **Commit:** `108c2b9` by Felix
- **Files:** docs/coordination/CLI-COMMAND-AUDIT.md, tracker/firmware/main/app_main.cpp, tracker/firmware/main/test/test_relay_send_nostr.c
- **Full message:** feat: implement relay_send_nostr CLI command (t_9b570899)
- **Relevance:** PROTOCOL, TEST

### [balloon-hermes] Implement nostr_dump CLI command (t_c27101f0) (2026-08-05) | tags: TEST
- **Commit:** `b093ac8` by Felix
- **Files:** docs/coordination/CLI-COMMAND-AUDIT.md, tracker/firmware/main/app_main.cpp, tracker/firmware/main/app_task.cpp (+1 more)
- **Full message:** Implement nostr_dump CLI command (t_c27101f0)
- **Relevance:** TEST

### [balloon-hermes] docs: consultant review V5 — tollgate proto found, merge conflict warning, resou (2026-08-05) | tags: GENERAL
- **Commit:** `1e26813` by Felix
- **Files:** docs/coordination/CONSULTANT-PLAN-REVIEW-V5.md
- **Full message:** docs: consultant review V5 — tollgate proto found, merge conflict warning, resource guidance
- **Relevance:** GENERAL

### [balloon-hermes] docs: worker status report + CLI audit findings for consultant review (2026-08-05) | tags: GENERAL
- **Commit:** `aca3f36` by Felix
- **Files:** docs/coordination/WORKER-STATUS-CONSULTANT-REPORT.md
- **Full message:** docs: worker status report + CLI audit findings for consultant review
- **Relevance:** GENERAL

### [balloon-hermes] docs: CLI command audit — 2/5 exist, 3 missing (relay_send_nostr, nostr_dump, to (2026-08-05) | tags: PROTOCOL
- **Commit:** `9b79760` by Felix
- **Files:** docs/coordination/CLI-COMMAND-AUDIT.md
- **Full message:** docs: CLI command audit — 2/5 exist, 3 missing (relay_send_nostr, nostr_dump, tollgate_send_pay)
- **Relevance:** PROTOCOL

### [balloon-hermes] docs: integration plan V3 — PCB first, FIPS second, CLI audit, rollback plan (2026-08-05) | tags: HARDWARE
- **Commit:** `f156ef7` by Felix
- **Files:** docs/coordination/INTEGRATION-PLAN-V3.md
- **Full message:** docs: integration plan V3 — PCB first, FIPS second, CLI audit, rollback plan
- **Relevance:** HARDWARE

### [balloon-hermes] docs: consultant review V4 — 3 plans assessed, PCB priority first (2026-08-05) | tags: HARDWARE
- **Commit:** `6684c26` by Felix
- **Files:** docs/coordination/CONSULTANT-PLAN-REVIEW-V4.md
- **Full message:** docs: consultant review V4 — 3 plans assessed, PCB priority first
- **Relevance:** HARDWARE

### [balloon-range-tests] docs: discovery sync batch 2 — 6 findings, integration plan actionable, radio_ta (2026-08-05) | tags: GENERAL
- **Commit:** `301f414` by Felix
- **Files:** docs/STATUS-balloon-range-tests.md
- **Full message:** docs: discovery sync batch 2 — 6 findings, integration plan actionable, radio_task N/A
- **Relevance:** GENERAL

### [balloon-speed-tests] docs: discovery sync batch 2 — Phase 6 LA comparison is speed-tests scope, CONTI (2026-08-05) | tags: GENERAL
- **Commit:** `ab7c6f0` by Felix
- **Files:** docs/STATUS-balloon-speed-tests.md
- **Full message:** docs: discovery sync batch 2 — Phase 6 LA comparison is speed-tests scope, CONTINUOUS_TX ready
- **Relevance:** GENERAL

### [balloon-pre-stretching] docs: discovery sync — integration test plan + PCB GPIO fix assessed, both infor (2026-08-05) | tags: HARDWARE, TEST
- **Commit:** `1238273` by Felix
- **Files:** docs/STATUS-balloon-pre-stretching.md
- **Full message:** docs: discovery sync — integration test plan + PCB GPIO fix assessed, both informational
- **Relevance:** HARDWARE, TEST

### [balloon-circuit-design] docs: consultant PCB review — V1/F33 DRC analysis, GPIO fix assessment, architec (2026-08-05) | tags: HARDWARE
- **Commit:** `502d33f` by Felix
- **Files:** docs/CONSULTANT-PCB-REVIEW.md, tracker/hardware/drc_f33_fresh.txt, tracker/hardware/drc_v1_fresh.txt
- **Full message:** docs: consultant PCB review — V1/F33 DRC analysis, GPIO fix assessment, architecture mismatch found
- **Relevance:** HARDWARE


### [balloon-hermes] docs: integration test plan + PCB GPIO fix plan — Phases 2-4 and V1 PCB prep (2026-08-05) | tags: HARDWARE, TEST
- **Commit:** `2cbf7cd` by Felix
- **Files:** docs/coordination/INTEGRATION-TEST-PLAN.md, docs/pcb/V1-PCB-GPIO-FIX.md
- **Full message:** docs: integration test plan + PCB GPIO fix plan — Phases 2-4 and V1 PCB prep
- **Relevance:** HARDWARE, TEST

### [balloon-hermes] fix: radio_task non-blocking loop — short recv timeout + tx_queue poll (2026-08-05) | tags: RADIO, FIRMWARE
- **Commit:** `4e7722c` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/include/lr2021_transport.h, tracker/firmware/components/lr2021_transport/src/lr2021_transport.cpp, tracker/firmware/main/radio_task.cpp
- **Full message:** fix: radio_task non-blocking loop — short recv timeout + tx_queue poll
- **Relevance:** RADIO, FIRMWARE

### [balloon-hermes] fix: inverted nostr_event_deserialize return check — events were never stored (2026-08-05) | tags: GENERAL
- **Commit:** `f11ddd6` by Felix
- **Files:** tracker/firmware/main/app_task.cpp
- **Full message:** fix: inverted nostr_event_deserialize return check — events were never stored
- **Relevance:** GENERAL

### [balloon-hermes] docs: consultant review V3 — 5 bugs found, 3 fixed, no-hardware work identified (2026-08-05) | tags: GENERAL
- **Commit:** `c351b26` by Felix
- **Files:** docs/coordination/CONSULTANT-PLAN-REVIEW-V3.md
- **Full message:** docs: consultant review V3 — 5 bugs found, 3 fixed, no-hardware work identified
- **Relevance:** GENERAL

### [balloon-hermes] feat: add signature field to nostr_event_t — enables Schnorr verification (2026-08-05) | tags: FIRMWARE, TEST
- **Commit:** `bc3bd5b` by Felix
- **Files:** tracker/firmware/components/nostr_store/include/nostr_store.h, tracker/firmware/components/nostr_store/nostr_store.c, tracker/firmware/components/nostr_store/test/test_nostr_store.c
- **Full message:** feat: add signature field to nostr_event_t — enables Schnorr verification
- **Relevance:** FIRMWARE, TEST

### [balloon-hermes] fix: tollgate API alignment — correct function names, add Kconfig flag (2026-08-05) | tags: GENERAL
- **Commit:** `cb49869` by Felix
- **Files:** tracker/firmware/main/Kconfig.projbuild, tracker/firmware/main/app_task.cpp
- **Full message:** fix: tollgate API alignment — correct function names, add Kconfig flag
- **Relevance:** GENERAL

### [balloon-hermes] docs: consultant review V3 — 5 code bugs found, 3 no-hardware actions identified (2026-08-05) | tags: GENERAL
- **Commit:** `4f30f5b` by Felix
- **Files:** docs/coordination/CONSULTANT-PLAN-REVIEW-V3.md
- **Full message:** docs: consultant review V3 — 5 code bugs found, 3 no-hardware actions identified
- **Relevance:** GENERAL

### [balloon-hermes] test: host-side relay pipeline integration test — no hardware needed (2026-08-05) | tags: PROTOCOL, TEST
- **Commit:** `4e86174` by Felix
- **Files:** tracker/firmware/main/test/test_relay_pipeline.c
- **Full message:** test: host-side relay pipeline integration test — no hardware needed
- **Relevance:** PROTOCOL, TEST

### [balloon-hermes] docs: SPI timing comparison status + discovery sync updates (2026-08-05) | tags: SPI
- **Commit:** `b6c2146` by Felix
- **Files:** docs/coordination/DISCOVERIES.md
- **Full message:** docs: SPI timing comparison status + discovery sync updates
- **Relevance:** SPI

### [balloon-hermes] plan: add Phase 6 — logic analyzer C3 vs RP2040 SPI timing comparison (2026-08-05) | tags: SPI
- **Commit:** `4d53713` by Felix
- **Files:** docs/coordination/INTEGRATION-PLAN-V2.md
- **Full message:** plan: add Phase 6 — logic analyzer C3 vs RP2040 SPI timing comparison
- **Relevance:** SPI


### [balloon-range-tests] docs: discovery sync — 4 findings assessed, GPIO10 fix adopted, FLRC/secp/mesh i (2026-08-05) | tags: RADIO, PROTOCOL
- **Commit:** `df9982c` by Felix
- **Files:** docs/STATUS-balloon-range-tests.md
- **Full message:** docs: discovery sync — 4 findings assessed, GPIO10 fix adopted, FLRC/secp/mesh informational
- **Relevance:** RADIO, PROTOCOL

### [balloon-range-tests] fix: adopt GPIO10 collision fix (LED→GPIO18, FEM_TX→GPIO19) from balloon-hermes (2026-08-05) | tags: GENERAL
- **Commit:** `311913f` by Felix
- **Files:** tracker/firmware/main/Kconfig.projbuild, tracker/firmware/main/app_main.cpp
- **Full message:** fix: adopt GPIO10 collision fix (LED→GPIO18, FEM_TX→GPIO19) from balloon-hermes
- **Relevance:** GENERAL

### [balloon-speed-tests] docs: discovery sync 2026-08-05 — FLRC fixes synced, GPIO10 N/A, secp informatio (2026-08-05) | tags: RADIO
- **Commit:** `b6b4588` by Felix
- **Files:** docs/STATUS-balloon-speed-tests.md
- **Full message:** docs: discovery sync 2026-08-05 — FLRC fixes synced, GPIO10 N/A, secp informational
- **Relevance:** RADIO


### [balloon-hermes] fix: relay mode build fixes — TransportError scope, API alignment (2026-08-05) | tags: FIRMWARE, PROTOCOL
- **Commit:** `489123b` by Felix
- **Files:** tracker/firmware/components/nostr_store/include/nostr_store.h, tracker/firmware/main/CMakeLists.txt, tracker/firmware/main/app_main.cpp (+3 more)
- **Full message:** fix: relay mode build fixes — TransportError scope, API alignment
- **Relevance:** FIRMWARE, PROTOCOL

### [balloon-hermes] feat: FreeRTOS relay task architecture — radio_task, app_task, queue-based RX (2026-08-05) | tags: PROTOCOL
- **Commit:** `1f4fbef` by Felix
- **Files:** tracker/firmware/main/Kconfig.projbuild, tracker/firmware/main/app_main.cpp, tracker/firmware/main/app_task.cpp (+2 more)
- **Full message:** feat: FreeRTOS relay task architecture — radio_task, app_task, queue-based RX
- **Relevance:** PROTOCOL

### [balloon-hermes] build: add secp256k1 component to tracker firmware (smoke test) (2026-08-05) | tags: FIRMWARE, TEST
- **Commit:** `0829953` by Felix
- **Files:** tracker/firmware/CMakeLists.txt, tracker/firmware/external/secp256k1, tracker/firmware/main/CMakeLists.txt
- **Full message:** build: add secp256k1 component to tracker firmware (smoke test)
- **Relevance:** FIRMWARE, TEST

### [balloon-hermes] docs: FreeRTOS task architecture design — radio_task, app_task, main_task (2026-08-05) | tags: GENERAL
- **Commit:** `ce75512` by Felix
- **Files:** docs/coordination/ARCHITECTURE-FREERTOS-TASKS.md
- **Full message:** docs: FreeRTOS task architecture design — radio_task, app_task, main_task
- **Relevance:** GENERAL

### [balloon-hermes] fix: GPIO10 collision (LED vs LR2021 NSS) + GPS/FEM GPIO1 collision (2026-08-05) | tags: RADIO
- **Commit:** `f926dc9` by Felix
- **Files:** tracker/firmware/main/Kconfig.projbuild, tracker/firmware/main/app_main.cpp
- **Full message:** fix: GPIO10 collision (LED vs LR2021 NSS) + GPS/FEM GPIO1 collision
- **Relevance:** RADIO

### [balloon-hermes] plan: integration plan V2 — consultant corrections applied (2026-08-05) | tags: GENERAL
- **Commit:** `def9fbc` by Felix
- **Files:** docs/coordination/INTEGRATION-PLAN-V2.md
- **Full message:** plan: integration plan V2 — consultant corrections applied
- **Relevance:** GENERAL

### [balloon-hermes] docs: consultant review V2 — 3 critical findings, revised integration plan (2026-08-05) | tags: GENERAL
- **Commit:** `774aff9` by Felix
- **Files:** docs/coordination/CONSULTANT-PLAN-REVIEW-V2.md
- **Full message:** docs: consultant review V2 — 3 critical findings, revised integration plan
- **Relevance:** GENERAL

### [balloon-hermes] plan: integration plan for first unified balloon firmware image (2026-08-05) | tags: GENERAL
- **Commit:** `57acb98` by Felix
- **Files:** docs/coordination/INTEGRATION-PLAN-FIRST-UNIFIED-IMAGE.md
- **Full message:** plan: integration plan for first unified balloon firmware image
- **Relevance:** GENERAL

### [balloon-hermes] chore: commit pending track work — FLRC fixes, board lock tooling, coordination  (2026-08-05) | tags: RADIO
- **Commit:** `0292aec` by Felix
- **Files:** BOARD_LOCK_DELIVERABLES.md, FLRC_RP2040_FIXES_SUMMARY.md, Makefile (+9 more)
- **Full message:** chore: commit pending track work — FLRC fixes, board lock tooling, coordination docs
- **Relevance:** RADIO

### [balloon-hermes] docs: comprehensive consultant review package — all 9 tracks assessed, 210 tests (2026-08-05) | tags: GENERAL
- **Commit:** `c9b92aa` by Felix
- **Files:** docs/coordination/CONSULTANT-PROJECT-REVIEW.md
- **Full message:** docs: comprehensive consultant review package — all 9 tracks assessed, 210 tests, secp measured
- **Relevance:** GENERAL

### [balloon-hermes] feat: mesh baseline build verified + secp measurement test + tollgate payment te (2026-08-05) | tags: FIRMWARE, PROTOCOL, TEST
- **Commit:** `8aaa0bb` by Felix
- **Files:** firmware/blossom-server/partitions.csv, firmware/tests/secp_test/CMakeLists.txt, firmware/tests/secp_test/main/CMakeLists.txt (+5 more)
- **Full message:** feat: mesh baseline build verified + secp measurement test + tollgate payment tests
- **Relevance:** FIRMWARE, PROTOCOL, TEST

### [balloon-hermes] docs: autonomous execution plan v2 — consultant corrections applied, 5 tasks rem (2026-08-05) | tags: GENERAL
- **Commit:** `e5e7a34` by Felix
- **Files:** docs/coordination/PLAN-AUTONOMOUS-EXECUTION.md
- **Full message:** docs: autonomous execution plan v2 — consultant corrections applied, 5 tasks removed/rescoped
- **Relevance:** GENERAL

### [balloon-hermes] docs: consultant review of autonomous execution plan — 5 tasks redundant, condit (2026-08-05) | tags: GENERAL
- **Commit:** `c661f62` by Felix
- **Files:** docs/coordination/CONSULTANT-PLAN-REVIEW.md
- **Full message:** docs: consultant review of autonomous execution plan — 5 tasks redundant, conditional go
- **Relevance:** GENERAL

### [balloon-hermes] docs: autonomous execution plan — host-side work requiring no Felix action (2026-08-05) | tags: GENERAL
- **Commit:** `1ed42ba` by Felix
- **Files:** docs/coordination/PLAN-AUTONOMOUS-EXECUTION.md
- **Full message:** docs: autonomous execution plan — host-side work requiring no Felix action
- **Relevance:** GENERAL


### [balloon-hermes] docs: consultant project review — comprehensive status of all 9 tracks for exter (2026-08-05) | tags: GENERAL
- **Commit:** `ba82e1e` by Felix
- **Files:** docs/coordination/CONSULTANT-PROJECT-REVIEW.md
- **Full message:** docs: consultant project review — comprehensive status of all 9 tracks for external review
- **Relevance:** GENERAL


### [balloon-range-tests] docs: discovery sync — P1B.1-FIX SPI TX debugging assessment [SPI, RADIO, PROTOC (2026-08-01) | tags: SPI
- **Commit:** `49012e2` by Felix
- **Files:** docs/STATUS-balloon-range-tests.md
- **Full message:** docs: discovery sync — P1B.1-FIX SPI TX debugging assessment [SPI, RADIO, PROTOCOL]
- **Relevance:** SPI

### [balloon-speed-tests] docs: acknowledge discovery sync — P1B.1-FIX SPI TX debugging findings assessed (2026-08-01) | tags: SPI
- **Commit:** `a3519bd` by Felix
- **Files:** docs/STATUS-balloon-speed-tests.md
- **Full message:** docs: acknowledge discovery sync — P1B.1-FIX SPI TX debugging findings assessed
- **Relevance:** SPI


### [balloon-hermes] P1B.1-FIX: Add comprehensive SPI TX debugging for raw FLRC transmission (2026-08-01) | tags: SPI, RADIO, PROTOCOL
- **Commit:** `822cdf0` by Felix
- **Files:** docs/SPEED-P0P2P3-HW-VERIFICATION-PLAN.md, docs/coordination/DISCOVERIES.md, graphify-out/cache/stat-index.json (+2 more)
- **Full message:** P1B.1-FIX: Add comprehensive SPI TX debugging for raw FLRC transmission
- **Relevance:** SPI, RADIO, PROTOCOL


### [balloon-range-tests] docs: discovery sync — walk test logs + retry script findings (2026-07-31) (2026-07-31) | tags: TEST
- **Commit:** `59913ee` by Felix
- **Files:** docs/STATUS-balloon-range-tests.md
- **Full message:** docs: discovery sync — walk test logs + retry script findings (2026-07-31)
- **Relevance:** TEST


### [balloon-hermes] chore: state snapshot — walk test logs, retry script, discoveries update (2026-0 (2026-07-31) | tags: TEST
- **Commit:** `66f94a9` by Felix
- **Files:** .gitignore, data/walk-tests/walk-20260727-021153.log, data/walk-tests/walk-20260727-032657.log (+18 more)
- **Full message:** chore: state snapshot — walk test logs, retry script, discoveries update (2026-07-31)
- **Relevance:** TEST


### [balloon-range-tests] docs: discovery sync — V1+F33 PCB routing findings (informational) (2026-07-30) | tags: HARDWARE, PROTOCOL
- **Commit:** `b2b4233` by Felix
- **Files:** docs/STATUS-balloon-range-tests.md
- **Full message:** docs: discovery sync — V1+F33 PCB routing findings (informational)
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-circuit-design] docs(pcb): F33 short analysis + V1 BOM/CPL for JLCPCB — gerbers complete (2026-07-30) | tags: HARDWARE
- **Commit:** `7302dba` by Felix
- **Files:** docs/F33-SHORT-ANALYSIS.md, tracker/hardware/gerbers_v1/bom_v1.csv, tracker/hardware/gerbers_v1/cpl_v1.csv
- **Full message:** docs(pcb): F33 short analysis + V1 BOM/CPL for JLCPCB — gerbers complete
- **Relevance:** HARDWARE

### [balloon-circuit-design] fix(pcb): F33 surgical short fixes — C8 move, lane shifts, CE/GND/RF reroutes —  (2026-07-30) | tags: SPI, HARDWARE
- **Commit:** `8340255` by Felix
- **Files:** tracker/hardware/drc_f33_v7.txt, tracker/hardware/gen_pcb.py, tracker/hardware/hub_board_f33.kicad_pcb (+1 more)
- **Full message:** fix(pcb): F33 surgical short fixes — C8 move, lane shifts, CE/GND/RF reroutes — shorts 15→16 (SPI rt.connect remains)
- **Relevance:** SPI, HARDWARE


### [balloon-hermes] plan: post-merge integration — 5 workstreams with quality gates (2026-07-30) | tags: GENERAL
- **Commit:** `29ad722` by Felix
- **Files:** docs/coordination/PLAN-POST-MERGE-INTEGRATION.md
- **Full message:** plan: post-merge integration — 5 workstreams with quality gates
- **Relevance:** GENERAL

### [balloon-hermes] chore(pcb): commit stale F33 DRC intermediate reports (2026-07-30) | tags: HARDWARE
- **Commit:** `f5aaae5` by Felix
- **Files:** tracker/hardware/drc_f33_v3.txt, tracker/hardware/drc_f33_v4.txt
- **Full message:** chore(pcb): commit stale F33 DRC intermediate reports
- **Relevance:** HARDWARE

### [balloon-hermes] fix(pcb): F33 B.Cu routing for power+UART+I2C — shorts 44→15, crossings 14→15 (2026-07-30) | tags: HARDWARE, PROTOCOL
- **Commit:** `512fb0c` by Felix
- **Files:** tracker/hardware/drc_f33_v5.txt, tracker/hardware/gen_pcb.py, tracker/hardware/hub_board_f33.kicad_pcb (+1 more)
- **Full message:** fix(pcb): F33 B.Cu routing for power+UART+I2C — shorts 44→15, crossings 14→15
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-hermes] fix(pcb): F33 power bus to B.Cu + GND via relocation — shorts 27→19 (2026-07-30) | tags: HARDWARE
- **Commit:** `ac3f1d6` by Felix
- **Files:** tracker/hardware/drc_f33_v2.txt, tracker/hardware/gen_pcb.py, tracker/hardware/hub_board_f33.kicad_pcb (+1 more)
- **Full message:** fix(pcb): F33 power bus to B.Cu + GND via relocation — shorts 27→19
- **Relevance:** HARDWARE

### [balloon-hermes] fix(pcb): F33 Router integration + U1 pad pitch fix — shorts 44→27 (2026-07-30) | tags: HARDWARE
- **Commit:** `24f978f` by Felix
- **Files:** tracker/hardware/drc_f33_fixed.txt, tracker/hardware/gen_pcb.py
- **Full message:** fix(pcb): F33 Router integration + U1 pad pitch fix — shorts 44→27
- **Relevance:** HARDWARE

### [balloon-hermes] chore(pcb): commit DRC V1 final2 report (2026-07-30) | tags: HARDWARE
- **Commit:** `08b474d` by Felix
- **Files:** tracker/hardware/drc_v1_final2.txt
- **Full message:** chore(pcb): commit DRC V1 final2 report
- **Relevance:** HARDWARE

### [balloon-hermes] fix(pcb): V1 clearance-aware routing — shorts 86→59, crossings 65→0 (2026-07-30) | tags: HARDWARE, PROTOCOL
- **Commit:** `9b96c92` by Felix
- **Files:** tracker/hardware/drc_v1_router.txt, tracker/hardware/gen_pcb.py, tracker/hardware/hub_board_f33.kicad_pcb (+1 more)
- **Full message:** fix(pcb): V1 clearance-aware routing — shorts 86→59, crossings 65→0
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-hermes] refactor(pcb): import Router class into gen_pcb.py (2026-07-30) | tags: HARDWARE
- **Commit:** `f11e3fc` by Felix
- **Files:** tracker/hardware/gen_pcb.py
- **Full message:** refactor(pcb): import Router class into gen_pcb.py
- **Relevance:** HARDWARE

### [balloon-hermes] feat(router): clearance-aware Router class — 33/33 tests pass (2026-07-30) | tags: GENERAL
- **Commit:** `b634f47` by Felix
- **Files:** tracker/hardware/router.py, tracker/hardware/test_router.py
- **Full message:** feat(router): clearance-aware Router class — 33/33 tests pass
- **Relevance:** GENERAL

### [balloon-hermes] plan: clearance-aware routing rewrite + DRC analysis tooling (2026-07-30) | tags: PROTOCOL, TEST
- **Commit:** `2222b8f` by Felix
- **Files:** docs/PLAN-ROUTING-REWRITE.md, tracker/hardware/drc_f33_baseline.txt, tracker/hardware/drc_v1_baseline.txt (+3 more)
- **Full message:** plan: clearance-aware routing rewrite + DRC analysis tooling
- **Relevance:** PROTOCOL, TEST

### [balloon-hermes] feat(pcb): Gerbers + JLCPCB order package — both boards DRC clean (2026-07-30) | tags: HARDWARE
- **Commit:** `f473512` by Felix
- **Files:** tracker/hardware/gerbers_f33/hub_board_f33-B_Adhesive.gba, tracker/hardware/gerbers_f33/hub_board_f33-B_Courtyard.gbr, tracker/hardware/gerbers_f33/hub_board_f33-B_Cu.gbl (+45 more)
- **Full message:** feat(pcb): Gerbers + JLCPCB order package — both boards DRC clean
- **Relevance:** HARDWARE

### [balloon-hermes] fix(pcb): both boards 0 unconnected — auto-generated GND mesh + stub bridges (2026-07-30) | tags: HARDWARE, PROTOCOL
- **Commit:** `40f974f` by Felix
- **Files:** tracker/hardware/drc_f33_check.txt, tracker/hardware/drc_v1_check.txt, tracker/hardware/fix_unconnected.py (+2 more)
- **Full message:** fix(pcb): both boards 0 unconnected — auto-generated GND mesh + stub bridges
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-hermes] feat(pcb): V2 F33 full signal routing — SPI/UART/I2C/RF/PA power (2026-07-29) | tags: SPI, HARDWARE, PROTOCOL
- **Commit:** `e6e5a63` by Felix
- **Files:** tracker/hardware/drc_f33.txt, tracker/hardware/gen_pcb.py, tracker/hardware/gerbers_f33/hub_board_f33-B_Adhesive.gba (+24 more)
- **Full message:** feat(pcb): V2 F33 full signal routing — SPI/UART/I2C/RF/PA power
- **Relevance:** SPI, HARDWARE, PROTOCOL

### [balloon-hermes] feat(pcb): V1 local decoupling + GND stubs — 160 traces, 31 unconnected (2026-07-29) | tags: HARDWARE
- **Commit:** `c04001c` by Felix
- **Files:** tracker/hardware/drc_v1.txt, tracker/hardware/gen_pcb.py, tracker/hardware/gerbers_v1/hub_board_v1-B_Adhesive.gba (+23 more)
- **Full message:** feat(pcb): V1 local decoupling + GND stubs — 160 traces, 31 unconnected
- **Relevance:** HARDWARE

### [balloon-hermes] feat(pcb): V1 all signal nets routed — 84 traces, SPI/UART/I2C/RF (2026-07-29) | tags: SPI, HARDWARE
- **Commit:** `d56b6b0` by Felix
- **Files:** tracker/hardware/drc_v1.txt, tracker/hardware/gen_pcb.py, tracker/hardware/gerbers_v1/hub_board_v1-B_Adhesive.gba (+24 more)
- **Full message:** feat(pcb): V1 all signal nets routed — 84 traces, SPI/UART/I2C/RF
- **Relevance:** SPI, HARDWARE

### [balloon-hermes] feat(pcb): pick-and-place files + multi-layer SVG render (2026-07-29) | tags: HARDWARE
- **Commit:** `caede48` by Felix
- **Files:** tracker/hardware/gerbers_f33/pos_f33.csv, tracker/hardware/gerbers_v1/pos_v1.csv, tracker/hardware/hub_board_v1_render.svg
- **Full message:** feat(pcb): pick-and-place files + multi-layer SVG render
- **Relevance:** HARDWARE

### [balloon-hermes] feat(pcb): JLCPCB Gerbers generated for both hub board variants (2026-07-29) | tags: HARDWARE
- **Commit:** `94b6da0` by Felix
- **Files:** tracker/hardware/gen_pcb.py, tracker/hardware/gerbers_f33/hub_board_f33-B_Adhesive.gba, tracker/hardware/gerbers_f33/hub_board_f33-B_Courtyard.gbr (+46 more)
- **Full message:** feat(pcb): JLCPCB Gerbers generated for both hub board variants
- **Relevance:** HARDWARE

### [balloon-pow] docs: acknowledge discovery sync — 56 findings analyzed for PoW relevance (2026-07-30) | tags: GENERAL
- **Commit:** `7553aac` by Felix
- **Files:** docs/STATUS-balloon-pow.md
- **Full message:** docs: acknowledge discovery sync — 56 findings analyzed for PoW relevance
- **Relevance:** GENERAL

### [balloon-range-tests] docs: discovery sync — 47 findings assessed, 2 actionable (RP2040 SPI baseline), (2026-07-30) | tags: SPI, FIRMWARE, TEST
- **Commit:** `02b464d` by Felix
- **Files:** docs/STATUS-balloon-range-tests.md
- **Full message:** docs: discovery sync — 47 findings assessed, 2 actionable (RP2040 SPI baseline), rest ESP-IDF only
- **Relevance:** SPI, FIRMWARE, TEST

### [balloon-range-tests] plan: post-merge integration — 5 workstreams with quality gates (2026-07-30) | tags: GENERAL
- **Commit:** `29ad722` by Felix
- **Files:** docs/coordination/PLAN-POST-MERGE-INTEGRATION.md
- **Full message:** plan: post-merge integration — 5 workstreams with quality gates
- **Relevance:** GENERAL

### [balloon-range-tests] chore(pcb): commit stale F33 DRC intermediate reports (2026-07-30) | tags: HARDWARE
- **Commit:** `f5aaae5` by Felix
- **Files:** tracker/hardware/drc_f33_v3.txt, tracker/hardware/drc_f33_v4.txt
- **Full message:** chore(pcb): commit stale F33 DRC intermediate reports
- **Relevance:** HARDWARE

### [balloon-range-tests] fix(pcb): F33 B.Cu routing for power+UART+I2C — shorts 44→15, crossings 14→15 (2026-07-30) | tags: HARDWARE, PROTOCOL
- **Commit:** `512fb0c` by Felix
- **Files:** tracker/hardware/drc_f33_v5.txt, tracker/hardware/gen_pcb.py, tracker/hardware/hub_board_f33.kicad_pcb (+1 more)
- **Full message:** fix(pcb): F33 B.Cu routing for power+UART+I2C — shorts 44→15, crossings 14→15
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-range-tests] fix(pcb): F33 power bus to B.Cu + GND via relocation — shorts 27→19 (2026-07-30) | tags: HARDWARE
- **Commit:** `ac3f1d6` by Felix
- **Files:** tracker/hardware/drc_f33_v2.txt, tracker/hardware/gen_pcb.py, tracker/hardware/hub_board_f33.kicad_pcb (+1 more)
- **Full message:** fix(pcb): F33 power bus to B.Cu + GND via relocation — shorts 27→19
- **Relevance:** HARDWARE

### [balloon-range-tests] fix(pcb): F33 Router integration + U1 pad pitch fix — shorts 44→27 (2026-07-30) | tags: HARDWARE
- **Commit:** `24f978f` by Felix
- **Files:** tracker/hardware/drc_f33_fixed.txt, tracker/hardware/gen_pcb.py
- **Full message:** fix(pcb): F33 Router integration + U1 pad pitch fix — shorts 44→27
- **Relevance:** HARDWARE

### [balloon-range-tests] chore(pcb): commit DRC V1 final2 report (2026-07-30) | tags: HARDWARE
- **Commit:** `08b474d` by Felix
- **Files:** tracker/hardware/drc_v1_final2.txt
- **Full message:** chore(pcb): commit DRC V1 final2 report
- **Relevance:** HARDWARE

### [balloon-range-tests] fix(pcb): V1 clearance-aware routing — shorts 86→59, crossings 65→0 (2026-07-30) | tags: HARDWARE, PROTOCOL
- **Commit:** `9b96c92` by Felix
- **Files:** tracker/hardware/drc_v1_router.txt, tracker/hardware/gen_pcb.py, tracker/hardware/hub_board_f33.kicad_pcb (+1 more)
- **Full message:** fix(pcb): V1 clearance-aware routing — shorts 86→59, crossings 65→0
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-range-tests] refactor(pcb): import Router class into gen_pcb.py (2026-07-30) | tags: HARDWARE
- **Commit:** `f11e3fc` by Felix
- **Files:** tracker/hardware/gen_pcb.py
- **Full message:** refactor(pcb): import Router class into gen_pcb.py
- **Relevance:** HARDWARE

### [balloon-range-tests] feat(router): clearance-aware Router class — 33/33 tests pass (2026-07-30) | tags: GENERAL
- **Commit:** `b634f47` by Felix
- **Files:** tracker/hardware/router.py, tracker/hardware/test_router.py
- **Full message:** feat(router): clearance-aware Router class — 33/33 tests pass
- **Relevance:** GENERAL

### [balloon-range-tests] plan: clearance-aware routing rewrite + DRC analysis tooling (2026-07-30) | tags: PROTOCOL, TEST
- **Commit:** `2222b8f` by Felix
- **Files:** docs/PLAN-ROUTING-REWRITE.md, tracker/hardware/drc_f33_baseline.txt, tracker/hardware/drc_v1_baseline.txt (+3 more)
- **Full message:** plan: clearance-aware routing rewrite + DRC analysis tooling
- **Relevance:** PROTOCOL, TEST

### [balloon-range-tests] feat(pcb): Gerbers + JLCPCB order package — both boards DRC clean (2026-07-30) | tags: HARDWARE
- **Commit:** `f473512` by Felix
- **Files:** tracker/hardware/gerbers_f33/hub_board_f33-B_Adhesive.gba, tracker/hardware/gerbers_f33/hub_board_f33-B_Courtyard.gbr, tracker/hardware/gerbers_f33/hub_board_f33-B_Cu.gbl (+45 more)
- **Full message:** feat(pcb): Gerbers + JLCPCB order package — both boards DRC clean
- **Relevance:** HARDWARE

### [balloon-range-tests] fix(pcb): both boards 0 unconnected — auto-generated GND mesh + stub bridges (2026-07-30) | tags: HARDWARE, PROTOCOL
- **Commit:** `40f974f` by Felix
- **Files:** tracker/hardware/drc_f33_check.txt, tracker/hardware/drc_v1_check.txt, tracker/hardware/fix_unconnected.py (+2 more)
- **Full message:** fix(pcb): both boards 0 unconnected — auto-generated GND mesh + stub bridges
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-range-tests] feat(pcb): V2 F33 full signal routing — SPI/UART/I2C/RF/PA power (2026-07-29) | tags: SPI, HARDWARE, PROTOCOL
- **Commit:** `e6e5a63` by Felix
- **Files:** tracker/hardware/drc_f33.txt, tracker/hardware/gen_pcb.py, tracker/hardware/gerbers_f33/hub_board_f33-B_Adhesive.gba (+24 more)
- **Full message:** feat(pcb): V2 F33 full signal routing — SPI/UART/I2C/RF/PA power
- **Relevance:** SPI, HARDWARE, PROTOCOL

### [balloon-range-tests] feat(pcb): V1 local decoupling + GND stubs — 160 traces, 31 unconnected (2026-07-29) | tags: HARDWARE
- **Commit:** `c04001c` by Felix
- **Files:** tracker/hardware/drc_v1.txt, tracker/hardware/gen_pcb.py, tracker/hardware/gerbers_v1/hub_board_v1-B_Adhesive.gba (+23 more)
- **Full message:** feat(pcb): V1 local decoupling + GND stubs — 160 traces, 31 unconnected
- **Relevance:** HARDWARE

### [balloon-range-tests] feat(pcb): V1 all signal nets routed — 84 traces, SPI/UART/I2C/RF (2026-07-29) | tags: SPI, HARDWARE
- **Commit:** `d56b6b0` by Felix
- **Files:** tracker/hardware/drc_v1.txt, tracker/hardware/gen_pcb.py, tracker/hardware/gerbers_v1/hub_board_v1-B_Adhesive.gba (+24 more)
- **Full message:** feat(pcb): V1 all signal nets routed — 84 traces, SPI/UART/I2C/RF
- **Relevance:** SPI, HARDWARE

### [balloon-range-tests] feat(pcb): pick-and-place files + multi-layer SVG render (2026-07-29) | tags: HARDWARE
- **Commit:** `caede48` by Felix
- **Files:** tracker/hardware/gerbers_f33/pos_f33.csv, tracker/hardware/gerbers_v1/pos_v1.csv, tracker/hardware/hub_board_v1_render.svg
- **Full message:** feat(pcb): pick-and-place files + multi-layer SVG render
- **Relevance:** HARDWARE

### [balloon-range-tests] feat(pcb): JLCPCB Gerbers generated for both hub board variants (2026-07-29) | tags: HARDWARE
- **Commit:** `94b6da0` by Felix
- **Files:** tracker/hardware/gen_pcb.py, tracker/hardware/gerbers_f33/hub_board_f33-B_Adhesive.gba, tracker/hardware/gerbers_f33/hub_board_f33-B_Courtyard.gbr (+46 more)
- **Full message:** feat(pcb): JLCPCB Gerbers generated for both hub board variants
- **Relevance:** HARDWARE

### [balloon-range-tests] docs: discovery sync ack — board design frozen, weights calculable (2026-07-30) | tags: GENERAL
- **Commit:** `1e8bade` by Felix
- **Files:** docs/STATUS-balloon-pre-stretching.md
- **Full message:** docs: discovery sync ack — board design frozen, weights calculable
- **Relevance:** GENERAL

### [balloon-circuit-design] plan: post-merge integration — 5 workstreams with quality gates (2026-07-30) | tags: GENERAL
- **Commit:** `29ad722` by Felix
- **Files:** docs/coordination/PLAN-POST-MERGE-INTEGRATION.md
- **Full message:** plan: post-merge integration — 5 workstreams with quality gates
- **Relevance:** GENERAL

### [balloon-circuit-design] chore(pcb): commit stale F33 DRC intermediate reports (2026-07-30) | tags: HARDWARE
- **Commit:** `f5aaae5` by Felix
- **Files:** tracker/hardware/drc_f33_v3.txt, tracker/hardware/drc_f33_v4.txt
- **Full message:** chore(pcb): commit stale F33 DRC intermediate reports
- **Relevance:** HARDWARE

### [balloon-circuit-design] fix(pcb): F33 B.Cu routing for power+UART+I2C — shorts 44→15, crossings 14→15 (2026-07-30) | tags: HARDWARE, PROTOCOL
- **Commit:** `512fb0c` by Felix
- **Files:** tracker/hardware/drc_f33_v5.txt, tracker/hardware/gen_pcb.py, tracker/hardware/hub_board_f33.kicad_pcb (+1 more)
- **Full message:** fix(pcb): F33 B.Cu routing for power+UART+I2C — shorts 44→15, crossings 14→15
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-circuit-design] fix(pcb): F33 power bus to B.Cu + GND via relocation — shorts 27→19 (2026-07-30) | tags: HARDWARE
- **Commit:** `ac3f1d6` by Felix
- **Files:** tracker/hardware/drc_f33_v2.txt, tracker/hardware/gen_pcb.py, tracker/hardware/hub_board_f33.kicad_pcb (+1 more)
- **Full message:** fix(pcb): F33 power bus to B.Cu + GND via relocation — shorts 27→19
- **Relevance:** HARDWARE

### [balloon-circuit-design] fix(pcb): F33 Router integration + U1 pad pitch fix — shorts 44→27 (2026-07-30) | tags: HARDWARE
- **Commit:** `24f978f` by Felix
- **Files:** tracker/hardware/drc_f33_fixed.txt, tracker/hardware/gen_pcb.py
- **Full message:** fix(pcb): F33 Router integration + U1 pad pitch fix — shorts 44→27
- **Relevance:** HARDWARE

### [balloon-circuit-design] chore(pcb): commit DRC V1 final2 report (2026-07-30) | tags: HARDWARE
- **Commit:** `08b474d` by Felix
- **Files:** tracker/hardware/drc_v1_final2.txt
- **Full message:** chore(pcb): commit DRC V1 final2 report
- **Relevance:** HARDWARE

### [balloon-circuit-design] fix(pcb): V1 clearance-aware routing — shorts 86→59, crossings 65→0 (2026-07-30) | tags: HARDWARE, PROTOCOL
- **Commit:** `9b96c92` by Felix
- **Files:** tracker/hardware/drc_v1_router.txt, tracker/hardware/gen_pcb.py, tracker/hardware/hub_board_f33.kicad_pcb (+1 more)
- **Full message:** fix(pcb): V1 clearance-aware routing — shorts 86→59, crossings 65→0
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-circuit-design] refactor(pcb): import Router class into gen_pcb.py (2026-07-30) | tags: HARDWARE
- **Commit:** `f11e3fc` by Felix
- **Files:** tracker/hardware/gen_pcb.py
- **Full message:** refactor(pcb): import Router class into gen_pcb.py
- **Relevance:** HARDWARE

### [balloon-circuit-design] feat(router): clearance-aware Router class — 33/33 tests pass (2026-07-30) | tags: GENERAL
- **Commit:** `b634f47` by Felix
- **Files:** tracker/hardware/router.py, tracker/hardware/test_router.py
- **Full message:** feat(router): clearance-aware Router class — 33/33 tests pass
- **Relevance:** GENERAL

### [balloon-circuit-design] plan: clearance-aware routing rewrite + DRC analysis tooling (2026-07-30) | tags: PROTOCOL, TEST
- **Commit:** `2222b8f` by Felix
- **Files:** docs/PLAN-ROUTING-REWRITE.md, tracker/hardware/drc_f33_baseline.txt, tracker/hardware/drc_v1_baseline.txt (+3 more)
- **Full message:** plan: clearance-aware routing rewrite + DRC analysis tooling
- **Relevance:** PROTOCOL, TEST

### [balloon-circuit-design] feat(pcb): Gerbers + JLCPCB order package — both boards DRC clean (2026-07-30) | tags: HARDWARE
- **Commit:** `f473512` by Felix
- **Files:** tracker/hardware/gerbers_f33/hub_board_f33-B_Adhesive.gba, tracker/hardware/gerbers_f33/hub_board_f33-B_Courtyard.gbr, tracker/hardware/gerbers_f33/hub_board_f33-B_Cu.gbl (+45 more)
- **Full message:** feat(pcb): Gerbers + JLCPCB order package — both boards DRC clean
- **Relevance:** HARDWARE

### [balloon-circuit-design] fix(pcb): both boards 0 unconnected — auto-generated GND mesh + stub bridges (2026-07-30) | tags: HARDWARE, PROTOCOL
- **Commit:** `40f974f` by Felix
- **Files:** tracker/hardware/drc_f33_check.txt, tracker/hardware/drc_v1_check.txt, tracker/hardware/fix_unconnected.py (+2 more)
- **Full message:** fix(pcb): both boards 0 unconnected — auto-generated GND mesh + stub bridges
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-circuit-design] feat(pcb): V2 F33 full signal routing — SPI/UART/I2C/RF/PA power (2026-07-29) | tags: SPI, HARDWARE, PROTOCOL
- **Commit:** `e6e5a63` by Felix
- **Files:** tracker/hardware/drc_f33.txt, tracker/hardware/gen_pcb.py, tracker/hardware/gerbers_f33/hub_board_f33-B_Adhesive.gba (+24 more)
- **Full message:** feat(pcb): V2 F33 full signal routing — SPI/UART/I2C/RF/PA power
- **Relevance:** SPI, HARDWARE, PROTOCOL

### [balloon-circuit-design] feat(pcb): V1 local decoupling + GND stubs — 160 traces, 31 unconnected (2026-07-29) | tags: HARDWARE
- **Commit:** `c04001c` by Felix
- **Files:** tracker/hardware/drc_v1.txt, tracker/hardware/gen_pcb.py, tracker/hardware/gerbers_v1/hub_board_v1-B_Adhesive.gba (+23 more)
- **Full message:** feat(pcb): V1 local decoupling + GND stubs — 160 traces, 31 unconnected
- **Relevance:** HARDWARE

### [balloon-circuit-design] feat(pcb): V1 all signal nets routed — 84 traces, SPI/UART/I2C/RF (2026-07-29) | tags: SPI, HARDWARE
- **Commit:** `d56b6b0` by Felix
- **Files:** tracker/hardware/drc_v1.txt, tracker/hardware/gen_pcb.py, tracker/hardware/gerbers_v1/hub_board_v1-B_Adhesive.gba (+24 more)
- **Full message:** feat(pcb): V1 all signal nets routed — 84 traces, SPI/UART/I2C/RF
- **Relevance:** SPI, HARDWARE

### [balloon-circuit-design] feat(pcb): pick-and-place files + multi-layer SVG render (2026-07-29) | tags: HARDWARE
- **Commit:** `caede48` by Felix
- **Files:** tracker/hardware/gerbers_f33/pos_f33.csv, tracker/hardware/gerbers_v1/pos_v1.csv, tracker/hardware/hub_board_v1_render.svg
- **Full message:** feat(pcb): pick-and-place files + multi-layer SVG render
- **Relevance:** HARDWARE

### [balloon-circuit-design] feat(pcb): JLCPCB Gerbers generated for both hub board variants (2026-07-29) | tags: HARDWARE
- **Commit:** `94b6da0` by Felix
- **Files:** tracker/hardware/gen_pcb.py, tracker/hardware/gerbers_f33/hub_board_f33-B_Adhesive.gba, tracker/hardware/gerbers_f33/hub_board_f33-B_Courtyard.gbr (+46 more)
- **Full message:** feat(pcb): JLCPCB Gerbers generated for both hub board variants
- **Relevance:** HARDWARE


### [balloon-hermes] docs: discovery sync ack — board design frozen, weights calculable (2026-07-30) | tags: GENERAL
- **Commit:** `1e8bade` by Felix
- **Files:** docs/STATUS-balloon-pre-stretching.md
- **Full message:** docs: discovery sync ack — board design frozen, weights calculable
- **Relevance:** GENERAL

### [balloon-hermes] docs: discovery sync acknowledgment — circuit-design routing rewrite [informatio (2026-07-30) | tags: PROTOCOL
- **Commit:** `9cc74c0` by Felix
- **Files:** docs/STATUS-balloon-range-tests.md
- **Full message:** docs: discovery sync acknowledgment — circuit-design routing rewrite [informational]
- **Relevance:** PROTOCOL

### [balloon-hermes] chore: update AGENTS.md to balloon-tollgate identity (2026-07-29) | tags: GENERAL
- **Commit:** `b1effd4` by Felix
- **Files:** AGENTS.md
- **Full message:** chore: update AGENTS.md to balloon-tollgate identity
- **Relevance:** GENERAL

### [balloon-hermes] fix: RX watchdog crash + IRQ pin polling for packet reception (2026-07-30) | tags: RADIO, FIRMWARE
- **Commit:** `9bcbf1a` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/src/esp_idf_lr2021_radio.cpp, tracker/firmware/radio_test/main/main.cpp
- **Full message:** fix: RX watchdog crash + IRQ pin polling for packet reception
- **Relevance:** RADIO, FIRMWARE

### [balloon-hermes] fix: combine SPI reads into single CS-low txn + fix watchdog crash (2026-07-30) | tags: SPI, RADIO, FIRMWARE
- **Commit:** `c0a92a9` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/include/esp_idf_lr2021_radio.h, tracker/firmware/components/lr2021_transport/src/esp_idf_lr2021_radio.cpp, tracker/firmware/components/lr2021_transport/src/lr2021_transport.cpp (+1 more)
- **Full message:** fix: combine SPI reads into single CS-low txn + fix watchdog crash
- **Relevance:** SPI, RADIO, FIRMWARE

### [balloon-hermes] fix: port 5 SPI crash fixes from balloon-hermes lr2021_radio.c (5bf933b) (2026-07-30) | tags: SPI, RADIO, FIRMWARE
- **Commit:** `fc386b3` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/src/esp_idf_lr2021_radio.cpp, tracker/firmware/sdkconfig.defaults
- **Full message:** fix: port 5 SPI crash fixes from balloon-hermes lr2021_radio.c (5bf933b)
- **Relevance:** SPI, RADIO, FIRMWARE

### [balloon-hermes] refactor: replace RadioLib with lr2021_transport in firmware (ADR-020) (2026-07-30) | tags: RADIO, FIRMWARE
- **Commit:** `477b6d6` by Felix
- **Files:** tracker/firmware/components/meshcore/esp_idf/EspIdfInterfaces.h, tracker/firmware/main/CMakeLists.txt, tracker/firmware/main/app_main.cpp
- **Full message:** refactor: replace RadioLib with lr2021_transport in firmware (ADR-020)
- **Relevance:** RADIO, FIRMWARE

### [balloon-hermes] feat: EspHalLr2021Radio — ESP-IDF raw SPI adapter for LR2021 (20MHz direct GPIO) (2026-07-30) | tags: SPI, RADIO, FIRMWARE, HARDWARE
- **Commit:** `f4dddd0` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/CMakeLists.txt, tracker/firmware/components/lr2021_transport/include/esp_idf_lr2021_radio.h, tracker/firmware/components/lr2021_transport/src/esp_idf_lr2021_radio.cpp (+1 more)
- **Full message:** feat: EspHalLr2021Radio — ESP-IDF raw SPI adapter for LR2021 (20MHz direct GPIO)
- **Relevance:** SPI, RADIO, FIRMWARE, HARDWARE

### [balloon-hermes] docs: SPI layout constraints for LR2021 at 20MHz (2026-07-30) | tags: SPI, RADIO, FIRMWARE
- **Commit:** `b9712e5` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/SPI-LAYOUT-CONSTRAINTS.md
- **Full message:** docs: SPI layout constraints for LR2021 at 20MHz
- **Relevance:** SPI, RADIO, FIRMWARE

### [balloon-hermes] refactor: remove dead SX1280 opcode namespaces from lr2021_spi.h (ADR-020) (2026-07-29) | tags: RADIO, FIRMWARE
- **Commit:** `a59a758` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/include/lr2021_spi.h
- **Full message:** refactor: remove dead SX1280 opcode namespaces from lr2021_spi.h (ADR-020)
- **Relevance:** RADIO, FIRMWARE

### [balloon-hermes] docs: Phase 2 plan — hardware adapter + cross-track finding resolution (2026-07-29) | tags: GENERAL
- **Commit:** `a416b38` by Felix
- **Files:** docs/PLAN-phase2-hardware-adapter-2026-07-29.md
- **Full message:** docs: Phase 2 plan — hardware adapter + cross-track finding resolution
- **Relevance:** GENERAL

### [balloon-hermes] feat: encrypted multi-frame transport over LR2021 (Phase 3 host test) (2026-07-29) | tags: RADIO, FIRMWARE, TEST
- **Commit:** `4f864b5` by Felix
- **Files:** tracker/firmware/components/fips_radio_bridge/test/Makefile, tracker/firmware/components/fips_radio_bridge/test/test_fips_fragmented.cpp
- **Full message:** feat: encrypted multi-frame transport over LR2021 (Phase 3 host test)
- **Relevance:** RADIO, FIRMWARE, TEST

### [balloon-hermes] feat: FIPS Noise IK handshake over LR2021 transport (host integration test) (2026-07-29) | tags: RADIO, FIRMWARE, TEST
- **Commit:** `d0cb398` by Felix
- **Files:** tracker/firmware/components/fips_radio_bridge/CMakeLists.txt, tracker/firmware/components/fips_radio_bridge/include/fips_radio_bridge.h, tracker/firmware/components/fips_radio_bridge/src/fips_radio_bridge.cpp (+3 more)
- **Full message:** feat: FIPS Noise IK handshake over LR2021 transport (host integration test)
- **Relevance:** RADIO, FIRMWARE, TEST

### [balloon-hermes] feat: extract LR2021 transport layer from microfips to balloon-fresh (C++ ESP-ID (2026-07-29) | tags: RADIO, FIRMWARE, TEST
- **Commit:** `75ffda3` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/CMakeLists.txt, tracker/firmware/components/lr2021_transport/include/lr2021_framing.h, tracker/firmware/components/lr2021_transport/include/lr2021_spi.h (+6 more)
- **Full message:** feat: extract LR2021 transport layer from microfips to balloon-fresh (C++ ESP-IDF port)
- **Relevance:** RADIO, FIRMWARE, TEST

### [balloon-hermes] Revert "feat(coordination): add balloon-multiwan-bonding as 10th track" (2026-07-30) | tags: GENERAL
- **Commit:** `dedb5bd` by Felix
- **Files:** docs/coordination/TRACKS-REGISTRY.yaml
- **Full message:** Revert "feat(coordination): add balloon-multiwan-bonding as 10th track"
- **Relevance:** GENERAL

### [balloon-hermes] data: RP2040 baseline capture + results — 1760kbps at 10.40MHz SPI (2026-07-30) | tags: SPI, RADIO, TEST
- **Commit:** `a31f971` by Felix
- **Files:** .gitignore, captures/bench-rp2040.sr, docs/rp2040-baseline-results.md
- **Full message:** data: RP2040 baseline capture + results — 1760kbps at 10.40MHz SPI
- **Relevance:** SPI, RADIO, TEST

### [balloon-hermes] docs+feat: SPI timing findings + payload size sweep targets (2026-07-29) | tags: SPI
- **Commit:** `af2457f` by Felix
- **Files:** Makefile, docs/spi-timing-analysis.md, firmware/rp2040/platformio.ini
- **Full message:** docs+feat: SPI timing findings + payload size sweep targets
- **Relevance:** SPI

### [balloon-range-tests] docs: discovery sync acknowledgment — circuit-design routing rewrite [informatio (2026-07-30) | tags: PROTOCOL
- **Commit:** `9cc74c0` by Felix
- **Files:** docs/STATUS-balloon-range-tests.md
- **Full message:** docs: discovery sync acknowledgment — circuit-design routing rewrite [informational]
- **Relevance:** PROTOCOL

### [balloon-range-tests] chore: update AGENTS.md to balloon-tollgate identity (2026-07-29) | tags: GENERAL
- **Commit:** `b1effd4` by Felix
- **Files:** AGENTS.md
- **Full message:** chore: update AGENTS.md to balloon-tollgate identity
- **Relevance:** GENERAL

### [balloon-range-tests] fix: RX watchdog crash + IRQ pin polling for packet reception (2026-07-30) | tags: RADIO, FIRMWARE
- **Commit:** `9bcbf1a` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/src/esp_idf_lr2021_radio.cpp, tracker/firmware/radio_test/main/main.cpp
- **Full message:** fix: RX watchdog crash + IRQ pin polling for packet reception
- **Relevance:** RADIO, FIRMWARE

### [balloon-range-tests] fix: combine SPI reads into single CS-low txn + fix watchdog crash (2026-07-30) | tags: SPI, RADIO, FIRMWARE
- **Commit:** `c0a92a9` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/include/esp_idf_lr2021_radio.h, tracker/firmware/components/lr2021_transport/src/esp_idf_lr2021_radio.cpp, tracker/firmware/components/lr2021_transport/src/lr2021_transport.cpp (+1 more)
- **Full message:** fix: combine SPI reads into single CS-low txn + fix watchdog crash
- **Relevance:** SPI, RADIO, FIRMWARE

### [balloon-range-tests] fix: port 5 SPI crash fixes from balloon-hermes lr2021_radio.c (5bf933b) (2026-07-30) | tags: SPI, RADIO, FIRMWARE
- **Commit:** `fc386b3` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/src/esp_idf_lr2021_radio.cpp, tracker/firmware/sdkconfig.defaults
- **Full message:** fix: port 5 SPI crash fixes from balloon-hermes lr2021_radio.c (5bf933b)
- **Relevance:** SPI, RADIO, FIRMWARE

### [balloon-range-tests] refactor: replace RadioLib with lr2021_transport in firmware (ADR-020) (2026-07-30) | tags: RADIO, FIRMWARE
- **Commit:** `477b6d6` by Felix
- **Files:** tracker/firmware/components/meshcore/esp_idf/EspIdfInterfaces.h, tracker/firmware/main/CMakeLists.txt, tracker/firmware/main/app_main.cpp
- **Full message:** refactor: replace RadioLib with lr2021_transport in firmware (ADR-020)
- **Relevance:** RADIO, FIRMWARE

### [balloon-range-tests] feat: EspHalLr2021Radio — ESP-IDF raw SPI adapter for LR2021 (20MHz direct GPIO) (2026-07-30) | tags: SPI, RADIO, FIRMWARE, HARDWARE
- **Commit:** `f4dddd0` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/CMakeLists.txt, tracker/firmware/components/lr2021_transport/include/esp_idf_lr2021_radio.h, tracker/firmware/components/lr2021_transport/src/esp_idf_lr2021_radio.cpp (+1 more)
- **Full message:** feat: EspHalLr2021Radio — ESP-IDF raw SPI adapter for LR2021 (20MHz direct GPIO)
- **Relevance:** SPI, RADIO, FIRMWARE, HARDWARE

### [balloon-range-tests] docs: SPI layout constraints for LR2021 at 20MHz (2026-07-30) | tags: SPI, RADIO, FIRMWARE
- **Commit:** `b9712e5` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/SPI-LAYOUT-CONSTRAINTS.md
- **Full message:** docs: SPI layout constraints for LR2021 at 20MHz
- **Relevance:** SPI, RADIO, FIRMWARE

### [balloon-range-tests] refactor: remove dead SX1280 opcode namespaces from lr2021_spi.h (ADR-020) (2026-07-29) | tags: RADIO, FIRMWARE
- **Commit:** `a59a758` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/include/lr2021_spi.h
- **Full message:** refactor: remove dead SX1280 opcode namespaces from lr2021_spi.h (ADR-020)
- **Relevance:** RADIO, FIRMWARE

### [balloon-range-tests] docs: Phase 2 plan — hardware adapter + cross-track finding resolution (2026-07-29) | tags: GENERAL
- **Commit:** `a416b38` by Felix
- **Files:** docs/PLAN-phase2-hardware-adapter-2026-07-29.md
- **Full message:** docs: Phase 2 plan — hardware adapter + cross-track finding resolution
- **Relevance:** GENERAL

### [balloon-range-tests] feat: encrypted multi-frame transport over LR2021 (Phase 3 host test) (2026-07-29) | tags: RADIO, FIRMWARE, TEST
- **Commit:** `4f864b5` by Felix
- **Files:** tracker/firmware/components/fips_radio_bridge/test/Makefile, tracker/firmware/components/fips_radio_bridge/test/test_fips_fragmented.cpp
- **Full message:** feat: encrypted multi-frame transport over LR2021 (Phase 3 host test)
- **Relevance:** RADIO, FIRMWARE, TEST

### [balloon-range-tests] feat: FIPS Noise IK handshake over LR2021 transport (host integration test) (2026-07-29) | tags: RADIO, FIRMWARE, TEST
- **Commit:** `d0cb398` by Felix
- **Files:** tracker/firmware/components/fips_radio_bridge/CMakeLists.txt, tracker/firmware/components/fips_radio_bridge/include/fips_radio_bridge.h, tracker/firmware/components/fips_radio_bridge/src/fips_radio_bridge.cpp (+3 more)
- **Full message:** feat: FIPS Noise IK handshake over LR2021 transport (host integration test)
- **Relevance:** RADIO, FIRMWARE, TEST

### [balloon-range-tests] feat: extract LR2021 transport layer from microfips to balloon-fresh (C++ ESP-ID (2026-07-29) | tags: RADIO, FIRMWARE, TEST
- **Commit:** `75ffda3` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/CMakeLists.txt, tracker/firmware/components/lr2021_transport/include/lr2021_framing.h, tracker/firmware/components/lr2021_transport/include/lr2021_spi.h (+6 more)
- **Full message:** feat: extract LR2021 transport layer from microfips to balloon-fresh (C++ ESP-IDF port)
- **Relevance:** RADIO, FIRMWARE, TEST

### [balloon-range-tests] Revert "feat(coordination): add balloon-multiwan-bonding as 10th track" (2026-07-30) | tags: GENERAL
- **Commit:** `dedb5bd` by Felix
- **Files:** docs/coordination/TRACKS-REGISTRY.yaml
- **Full message:** Revert "feat(coordination): add balloon-multiwan-bonding as 10th track"
- **Relevance:** GENERAL

### [balloon-range-tests] feat(coordination): add balloon-multiwan-bonding as 10th track (2026-07-30) | tags: GENERAL
- **Commit:** `49aff2d` by Felix
- **Files:** docs/coordination/TRACKS-REGISTRY.yaml
- **Full message:** feat(coordination): add balloon-multiwan-bonding as 10th track
- **Relevance:** GENERAL

### [balloon-range-tests] data: RP2040 baseline capture + results — 1760kbps at 10.40MHz SPI (2026-07-30) | tags: SPI, RADIO, TEST
- **Commit:** `a31f971` by Felix
- **Files:** .gitignore, captures/bench-rp2040.sr, docs/rp2040-baseline-results.md
- **Full message:** data: RP2040 baseline capture + results — 1760kbps at 10.40MHz SPI
- **Relevance:** SPI, RADIO, TEST

### [balloon-range-tests] feat(nostr): rewrite nostr_store to flash-backed design (2026-07-29) | tags: FIRMWARE, PROTOCOL, TEST
- **Commit:** `423e1f8` by Felix
- **Files:** tracker/firmware/components/nostr_store/include/nostr_store.h, tracker/firmware/components/nostr_store/nostr_store.c, tracker/firmware/components/nostr_store/test/test_nostr_store.c (+1 more)
- **Full message:** feat(nostr): rewrite nostr_store to flash-backed design
- **Relevance:** FIRMWARE, PROTOCOL, TEST

### [balloon-range-tests] docs(nostr): extraction plan for store-and-forward on ESP32-C3 (2026-07-29) | tags: PROTOCOL
- **Commit:** `041c231` by Felix
- **Files:** AGENTS.md, docs/STATUS-balloon-nostr.md
- **Full message:** docs(nostr): extraction plan for store-and-forward on ESP32-C3
- **Relevance:** PROTOCOL

### [balloon-range-tests] feat(mesh_adapter): wire encrypt/decrypt callbacks for FIPS integration (2026-07-29) | tags: FIRMWARE, TEST
- **Commit:** `5d17114` by Felix
- **Files:** tests/test_c_host.py, tracker/firmware/components/mesh_adapter/include/mesh_adapter.h, tracker/firmware/components/mesh_adapter/mesh_adapter.c (+1 more)
- **Full message:** feat(mesh_adapter): wire encrypt/decrypt callbacks for FIPS integration
- **Relevance:** FIRMWARE, TEST

### [balloon-range-tests] feat(blossom_datagram): new component — bridge mesh datagram to blob storage (2026-07-29) | tags: FIRMWARE, PROTOCOL, TEST
- **Commit:** `7971810` by Felix
- **Files:** tests/test_c_host.py, tracker/firmware/components/blossom_datagram/CMakeLists.txt, tracker/firmware/components/blossom_datagram/blossom_datagram.c (+2 more)
- **Full message:** feat(blossom_datagram): new component — bridge mesh datagram to blob storage
- **Relevance:** FIRMWARE, PROTOCOL, TEST

### [balloon-range-tests] build(mesh_adapter): add CMakeLists.txt — was only mesh component missing one (2026-07-29) | tags: FIRMWARE, PROTOCOL
- **Commit:** `b60c583` by Felix
- **Files:** tracker/firmware/components/mesh_adapter/CMakeLists.txt
- **Full message:** build(mesh_adapter): add CMakeLists.txt — was only mesh component missing one
- **Relevance:** FIRMWARE, PROTOCOL

### [balloon-range-tests] feat(nostr_store): implement nostr_event_deserialize() (2026-07-29) | tags: FIRMWARE, TEST
- **Commit:** `e3c1575` by Felix
- **Files:** tracker/firmware/components/nostr_store/nostr_store.c, tracker/firmware/components/nostr_store/test/test_nostr_store.c
- **Full message:** feat(nostr_store): implement nostr_event_deserialize()
- **Relevance:** FIRMWARE, TEST

### [balloon-range-tests] docs+feat: SPI timing findings + payload size sweep targets (2026-07-29) | tags: SPI
- **Commit:** `af2457f` by Felix
- **Files:** Makefile, docs/spi-timing-analysis.md, firmware/rp2040/platformio.ini
- **Full message:** docs+feat: SPI timing findings + payload size sweep targets
- **Relevance:** SPI

### [balloon-pre-stretching] docs: discovery sync ack — board design frozen, weights calculable (2026-07-30) | tags: GENERAL
- **Commit:** `1e8bade` by Felix
- **Files:** docs/STATUS-balloon-pre-stretching.md
- **Full message:** docs: discovery sync ack — board design frozen, weights calculable
- **Relevance:** GENERAL

### [balloon-pre-stretching] docs: discovery sync acknowledgment — circuit-design routing rewrite [informatio (2026-07-30) | tags: PROTOCOL
- **Commit:** `9cc74c0` by Felix
- **Files:** docs/STATUS-balloon-range-tests.md
- **Full message:** docs: discovery sync acknowledgment — circuit-design routing rewrite [informational]
- **Relevance:** PROTOCOL

### [balloon-pre-stretching] chore: update AGENTS.md to balloon-tollgate identity (2026-07-29) | tags: GENERAL
- **Commit:** `b1effd4` by Felix
- **Files:** AGENTS.md
- **Full message:** chore: update AGENTS.md to balloon-tollgate identity
- **Relevance:** GENERAL

### [balloon-pre-stretching] fix: RX watchdog crash + IRQ pin polling for packet reception (2026-07-30) | tags: RADIO, FIRMWARE
- **Commit:** `9bcbf1a` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/src/esp_idf_lr2021_radio.cpp, tracker/firmware/radio_test/main/main.cpp
- **Full message:** fix: RX watchdog crash + IRQ pin polling for packet reception
- **Relevance:** RADIO, FIRMWARE

### [balloon-pre-stretching] fix: combine SPI reads into single CS-low txn + fix watchdog crash (2026-07-30) | tags: SPI, RADIO, FIRMWARE
- **Commit:** `c0a92a9` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/include/esp_idf_lr2021_radio.h, tracker/firmware/components/lr2021_transport/src/esp_idf_lr2021_radio.cpp, tracker/firmware/components/lr2021_transport/src/lr2021_transport.cpp (+1 more)
- **Full message:** fix: combine SPI reads into single CS-low txn + fix watchdog crash
- **Relevance:** SPI, RADIO, FIRMWARE

### [balloon-pre-stretching] fix: port 5 SPI crash fixes from balloon-hermes lr2021_radio.c (5bf933b) (2026-07-30) | tags: SPI, RADIO, FIRMWARE
- **Commit:** `fc386b3` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/src/esp_idf_lr2021_radio.cpp, tracker/firmware/sdkconfig.defaults
- **Full message:** fix: port 5 SPI crash fixes from balloon-hermes lr2021_radio.c (5bf933b)
- **Relevance:** SPI, RADIO, FIRMWARE

### [balloon-pre-stretching] refactor: replace RadioLib with lr2021_transport in firmware (ADR-020) (2026-07-30) | tags: RADIO, FIRMWARE
- **Commit:** `477b6d6` by Felix
- **Files:** tracker/firmware/components/meshcore/esp_idf/EspIdfInterfaces.h, tracker/firmware/main/CMakeLists.txt, tracker/firmware/main/app_main.cpp
- **Full message:** refactor: replace RadioLib with lr2021_transport in firmware (ADR-020)
- **Relevance:** RADIO, FIRMWARE

### [balloon-pre-stretching] feat: EspHalLr2021Radio — ESP-IDF raw SPI adapter for LR2021 (20MHz direct GPIO) (2026-07-30) | tags: SPI, RADIO, FIRMWARE, HARDWARE
- **Commit:** `f4dddd0` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/CMakeLists.txt, tracker/firmware/components/lr2021_transport/include/esp_idf_lr2021_radio.h, tracker/firmware/components/lr2021_transport/src/esp_idf_lr2021_radio.cpp (+1 more)
- **Full message:** feat: EspHalLr2021Radio — ESP-IDF raw SPI adapter for LR2021 (20MHz direct GPIO)
- **Relevance:** SPI, RADIO, FIRMWARE, HARDWARE

### [balloon-pre-stretching] docs: SPI layout constraints for LR2021 at 20MHz (2026-07-30) | tags: SPI, RADIO, FIRMWARE
- **Commit:** `b9712e5` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/SPI-LAYOUT-CONSTRAINTS.md
- **Full message:** docs: SPI layout constraints for LR2021 at 20MHz
- **Relevance:** SPI, RADIO, FIRMWARE

### [balloon-pre-stretching] refactor: remove dead SX1280 opcode namespaces from lr2021_spi.h (ADR-020) (2026-07-29) | tags: RADIO, FIRMWARE
- **Commit:** `a59a758` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/include/lr2021_spi.h
- **Full message:** refactor: remove dead SX1280 opcode namespaces from lr2021_spi.h (ADR-020)
- **Relevance:** RADIO, FIRMWARE

### [balloon-pre-stretching] docs: Phase 2 plan — hardware adapter + cross-track finding resolution (2026-07-29) | tags: GENERAL
- **Commit:** `a416b38` by Felix
- **Files:** docs/PLAN-phase2-hardware-adapter-2026-07-29.md
- **Full message:** docs: Phase 2 plan — hardware adapter + cross-track finding resolution
- **Relevance:** GENERAL

### [balloon-pre-stretching] feat: encrypted multi-frame transport over LR2021 (Phase 3 host test) (2026-07-29) | tags: RADIO, FIRMWARE, TEST
- **Commit:** `4f864b5` by Felix
- **Files:** tracker/firmware/components/fips_radio_bridge/test/Makefile, tracker/firmware/components/fips_radio_bridge/test/test_fips_fragmented.cpp
- **Full message:** feat: encrypted multi-frame transport over LR2021 (Phase 3 host test)
- **Relevance:** RADIO, FIRMWARE, TEST

### [balloon-pre-stretching] feat: FIPS Noise IK handshake over LR2021 transport (host integration test) (2026-07-29) | tags: RADIO, FIRMWARE, TEST
- **Commit:** `d0cb398` by Felix
- **Files:** tracker/firmware/components/fips_radio_bridge/CMakeLists.txt, tracker/firmware/components/fips_radio_bridge/include/fips_radio_bridge.h, tracker/firmware/components/fips_radio_bridge/src/fips_radio_bridge.cpp (+3 more)
- **Full message:** feat: FIPS Noise IK handshake over LR2021 transport (host integration test)
- **Relevance:** RADIO, FIRMWARE, TEST

### [balloon-pre-stretching] feat: extract LR2021 transport layer from microfips to balloon-fresh (C++ ESP-ID (2026-07-29) | tags: RADIO, FIRMWARE, TEST
- **Commit:** `75ffda3` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/CMakeLists.txt, tracker/firmware/components/lr2021_transport/include/lr2021_framing.h, tracker/firmware/components/lr2021_transport/include/lr2021_spi.h (+6 more)
- **Full message:** feat: extract LR2021 transport layer from microfips to balloon-fresh (C++ ESP-IDF port)
- **Relevance:** RADIO, FIRMWARE, TEST

### [balloon-pre-stretching] Revert "feat(coordination): add balloon-multiwan-bonding as 10th track" (2026-07-30) | tags: GENERAL
- **Commit:** `dedb5bd` by Felix
- **Files:** docs/coordination/TRACKS-REGISTRY.yaml
- **Full message:** Revert "feat(coordination): add balloon-multiwan-bonding as 10th track"
- **Relevance:** GENERAL

### [balloon-pre-stretching] feat(coordination): add balloon-multiwan-bonding as 10th track (2026-07-30) | tags: GENERAL
- **Commit:** `49aff2d` by Felix
- **Files:** docs/coordination/TRACKS-REGISTRY.yaml
- **Full message:** feat(coordination): add balloon-multiwan-bonding as 10th track
- **Relevance:** GENERAL

### [balloon-pre-stretching] data: RP2040 baseline capture + results — 1760kbps at 10.40MHz SPI (2026-07-30) | tags: SPI, RADIO, TEST
- **Commit:** `a31f971` by Felix
- **Files:** .gitignore, captures/bench-rp2040.sr, docs/rp2040-baseline-results.md
- **Full message:** data: RP2040 baseline capture + results — 1760kbps at 10.40MHz SPI
- **Relevance:** SPI, RADIO, TEST

### [balloon-pre-stretching] feat(nostr): rewrite nostr_store to flash-backed design (2026-07-29) | tags: FIRMWARE, PROTOCOL, TEST
- **Commit:** `423e1f8` by Felix
- **Files:** tracker/firmware/components/nostr_store/include/nostr_store.h, tracker/firmware/components/nostr_store/nostr_store.c, tracker/firmware/components/nostr_store/test/test_nostr_store.c (+1 more)
- **Full message:** feat(nostr): rewrite nostr_store to flash-backed design
- **Relevance:** FIRMWARE, PROTOCOL, TEST

### [balloon-pre-stretching] docs(nostr): extraction plan for store-and-forward on ESP32-C3 (2026-07-29) | tags: PROTOCOL
- **Commit:** `041c231` by Felix
- **Files:** AGENTS.md, docs/STATUS-balloon-nostr.md
- **Full message:** docs(nostr): extraction plan for store-and-forward on ESP32-C3
- **Relevance:** PROTOCOL

### [balloon-pre-stretching] feat(mesh_adapter): wire encrypt/decrypt callbacks for FIPS integration (2026-07-29) | tags: FIRMWARE, TEST
- **Commit:** `5d17114` by Felix
- **Files:** tests/test_c_host.py, tracker/firmware/components/mesh_adapter/include/mesh_adapter.h, tracker/firmware/components/mesh_adapter/mesh_adapter.c (+1 more)
- **Full message:** feat(mesh_adapter): wire encrypt/decrypt callbacks for FIPS integration
- **Relevance:** FIRMWARE, TEST

### [balloon-pre-stretching] feat(blossom_datagram): new component — bridge mesh datagram to blob storage (2026-07-29) | tags: FIRMWARE, PROTOCOL, TEST
- **Commit:** `7971810` by Felix
- **Files:** tests/test_c_host.py, tracker/firmware/components/blossom_datagram/CMakeLists.txt, tracker/firmware/components/blossom_datagram/blossom_datagram.c (+2 more)
- **Full message:** feat(blossom_datagram): new component — bridge mesh datagram to blob storage
- **Relevance:** FIRMWARE, PROTOCOL, TEST

### [balloon-pre-stretching] build(mesh_adapter): add CMakeLists.txt — was only mesh component missing one (2026-07-29) | tags: FIRMWARE, PROTOCOL
- **Commit:** `b60c583` by Felix
- **Files:** tracker/firmware/components/mesh_adapter/CMakeLists.txt
- **Full message:** build(mesh_adapter): add CMakeLists.txt — was only mesh component missing one
- **Relevance:** FIRMWARE, PROTOCOL

### [balloon-pre-stretching] feat(nostr_store): implement nostr_event_deserialize() (2026-07-29) | tags: FIRMWARE, TEST
- **Commit:** `e3c1575` by Felix
- **Files:** tracker/firmware/components/nostr_store/nostr_store.c, tracker/firmware/components/nostr_store/test/test_nostr_store.c
- **Full message:** feat(nostr_store): implement nostr_event_deserialize()
- **Relevance:** FIRMWARE, TEST

### [balloon-pre-stretching] docs+feat: SPI timing findings + payload size sweep targets (2026-07-29) | tags: SPI
- **Commit:** `af2457f` by Felix
- **Files:** Makefile, docs/spi-timing-analysis.md, firmware/rp2040/platformio.ini
- **Full message:** docs+feat: SPI timing findings + payload size sweep targets
- **Relevance:** SPI

### [balloon-circuit-design] chore(pcb): commit stale F33 DRC intermediate reports (2026-07-30) | tags: HARDWARE
- **Commit:** `51d1aa6` by Felix
- **Files:** tracker/hardware/drc_f33_v3.txt, tracker/hardware/drc_f33_v4.txt
- **Full message:** chore(pcb): commit stale F33 DRC intermediate reports
- **Relevance:** HARDWARE

### [balloon-circuit-design] fix(pcb): F33 B.Cu routing for power+UART+I2C — shorts 44→15, crossings 14→15 (2026-07-30) | tags: HARDWARE, PROTOCOL
- **Commit:** `7b5f46e` by Felix
- **Files:** tracker/hardware/drc_f33_v5.txt, tracker/hardware/gen_pcb.py, tracker/hardware/hub_board_f33.kicad_pcb (+1 more)
- **Full message:** fix(pcb): F33 B.Cu routing for power+UART+I2C — shorts 44→15, crossings 14→15
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-circuit-design] fix(pcb): F33 power bus to B.Cu + GND via relocation — shorts 27→19 (2026-07-30) | tags: HARDWARE
- **Commit:** `b511ef7` by Felix
- **Files:** tracker/hardware/drc_f33_v2.txt, tracker/hardware/gen_pcb.py, tracker/hardware/hub_board_f33.kicad_pcb (+1 more)
- **Full message:** fix(pcb): F33 power bus to B.Cu + GND via relocation — shorts 27→19
- **Relevance:** HARDWARE

### [balloon-circuit-design] fix(pcb): F33 Router integration + U1 pad pitch fix — shorts 44→27 (2026-07-30) | tags: HARDWARE
- **Commit:** `95eafe6` by Felix
- **Files:** tracker/hardware/drc_f33_fixed.txt, tracker/hardware/gen_pcb.py
- **Full message:** fix(pcb): F33 Router integration + U1 pad pitch fix — shorts 44→27
- **Relevance:** HARDWARE

### [balloon-circuit-design] chore(pcb): commit DRC V1 final2 report (2026-07-30) | tags: HARDWARE
- **Commit:** `6e53882` by Felix
- **Files:** tracker/hardware/drc_v1_final2.txt
- **Full message:** chore(pcb): commit DRC V1 final2 report
- **Relevance:** HARDWARE

### [balloon-circuit-design] fix(pcb): V1 clearance-aware routing — shorts 86→59, crossings 65→0 (2026-07-30) | tags: HARDWARE, PROTOCOL
- **Commit:** `a22662a` by Felix
- **Files:** tracker/hardware/drc_v1_router.txt, tracker/hardware/gen_pcb.py, tracker/hardware/hub_board_f33.kicad_pcb (+1 more)
- **Full message:** fix(pcb): V1 clearance-aware routing — shorts 86→59, crossings 65→0
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-circuit-design] refactor(pcb): import Router class into gen_pcb.py (2026-07-30) | tags: HARDWARE
- **Commit:** `1e876b3` by Felix
- **Files:** tracker/hardware/gen_pcb.py
- **Full message:** refactor(pcb): import Router class into gen_pcb.py
- **Relevance:** HARDWARE

### [balloon-circuit-design] feat(router): clearance-aware Router class — 33/33 tests pass (2026-07-30) | tags: GENERAL
- **Commit:** `e3b5464` by Felix
- **Files:** tracker/hardware/router.py, tracker/hardware/test_router.py
- **Full message:** feat(router): clearance-aware Router class — 33/33 tests pass
- **Relevance:** GENERAL

### [balloon-circuit-design] plan: clearance-aware routing rewrite + DRC analysis tooling (2026-07-30) | tags: PROTOCOL, TEST
- **Commit:** `75fb76e` by Felix
- **Files:** docs/PLAN-ROUTING-REWRITE.md, tracker/hardware/drc_f33_baseline.txt, tracker/hardware/drc_v1_baseline.txt (+3 more)
- **Full message:** plan: clearance-aware routing rewrite + DRC analysis tooling
- **Relevance:** PROTOCOL, TEST

### [balloon-circuit-design] feat(pcb): Gerbers + JLCPCB order package — both boards DRC clean (2026-07-30) | tags: HARDWARE
- **Commit:** `e5f960a` by Felix
- **Files:** tracker/hardware/gerbers_f33/hub_board_f33-B_Adhesive.gba, tracker/hardware/gerbers_f33/hub_board_f33-B_Courtyard.gbr, tracker/hardware/gerbers_f33/hub_board_f33-B_Cu.gbl (+45 more)
- **Full message:** feat(pcb): Gerbers + JLCPCB order package — both boards DRC clean
- **Relevance:** HARDWARE

### [balloon-circuit-design] fix(pcb): both boards 0 unconnected — auto-generated GND mesh + stub bridges (2026-07-30) | tags: HARDWARE, PROTOCOL
- **Commit:** `bfb9bc5` by Felix
- **Files:** tracker/hardware/drc_f33_check.txt, tracker/hardware/drc_v1_check.txt, tracker/hardware/fix_unconnected.py (+2 more)
- **Full message:** fix(pcb): both boards 0 unconnected — auto-generated GND mesh + stub bridges
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-circuit-design] feat(pcb): V2 F33 full signal routing — SPI/UART/I2C/RF/PA power (2026-07-29) | tags: SPI, HARDWARE, PROTOCOL
- **Commit:** `9b80dfc` by Felix
- **Files:** tracker/hardware/drc_f33.txt, tracker/hardware/gen_pcb.py, tracker/hardware/gerbers_f33/hub_board_f33-B_Adhesive.gba (+24 more)
- **Full message:** feat(pcb): V2 F33 full signal routing — SPI/UART/I2C/RF/PA power
- **Relevance:** SPI, HARDWARE, PROTOCOL

### [balloon-circuit-design] feat(pcb): V1 local decoupling + GND stubs — 160 traces, 31 unconnected (2026-07-29) | tags: HARDWARE
- **Commit:** `fb7a7e2` by Felix
- **Files:** tracker/hardware/drc_v1.txt, tracker/hardware/gen_pcb.py, tracker/hardware/gerbers_v1/hub_board_v1-B_Adhesive.gba (+23 more)
- **Full message:** feat(pcb): V1 local decoupling + GND stubs — 160 traces, 31 unconnected
- **Relevance:** HARDWARE

### [balloon-circuit-design] feat(pcb): V1 all signal nets routed — 84 traces, SPI/UART/I2C/RF (2026-07-29) | tags: SPI, HARDWARE
- **Commit:** `f37f443` by Felix
- **Files:** tracker/hardware/drc_v1.txt, tracker/hardware/gen_pcb.py, tracker/hardware/gerbers_v1/hub_board_v1-B_Adhesive.gba (+24 more)
- **Full message:** feat(pcb): V1 all signal nets routed — 84 traces, SPI/UART/I2C/RF
- **Relevance:** SPI, HARDWARE

### [balloon-circuit-design] feat(pcb): pick-and-place files + multi-layer SVG render (2026-07-29) | tags: HARDWARE
- **Commit:** `b4ea9b6` by Felix
- **Files:** tracker/hardware/gerbers_f33/pos_f33.csv, tracker/hardware/gerbers_v1/pos_v1.csv, tracker/hardware/hub_board_v1_render.svg
- **Full message:** feat(pcb): pick-and-place files + multi-layer SVG render
- **Relevance:** HARDWARE

### [balloon-circuit-design] feat(pcb): JLCPCB Gerbers generated for both hub board variants (2026-07-29) | tags: HARDWARE
- **Commit:** `9e4e121` by Felix
- **Files:** tracker/hardware/gen_pcb.py, tracker/hardware/gerbers_f33/hub_board_f33-B_Adhesive.gba, tracker/hardware/gerbers_f33/hub_board_f33-B_Courtyard.gbr (+46 more)
- **Full message:** feat(pcb): JLCPCB Gerbers generated for both hub board variants
- **Relevance:** HARDWARE

### [balloon-circuit-design] docs: discovery sync ack — board design frozen, weights calculable (2026-07-30) | tags: GENERAL
- **Commit:** `1e8bade` by Felix
- **Files:** docs/STATUS-balloon-pre-stretching.md
- **Full message:** docs: discovery sync ack — board design frozen, weights calculable
- **Relevance:** GENERAL

### [balloon-circuit-design] docs: discovery sync acknowledgment — circuit-design routing rewrite [informatio (2026-07-30) | tags: PROTOCOL
- **Commit:** `9cc74c0` by Felix
- **Files:** docs/STATUS-balloon-range-tests.md
- **Full message:** docs: discovery sync acknowledgment — circuit-design routing rewrite [informational]
- **Relevance:** PROTOCOL

### [balloon-circuit-design] chore: update AGENTS.md to balloon-tollgate identity (2026-07-29) | tags: GENERAL
- **Commit:** `b1effd4` by Felix
- **Files:** AGENTS.md
- **Full message:** chore: update AGENTS.md to balloon-tollgate identity
- **Relevance:** GENERAL

### [balloon-circuit-design] fix: RX watchdog crash + IRQ pin polling for packet reception (2026-07-30) | tags: RADIO, FIRMWARE
- **Commit:** `9bcbf1a` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/src/esp_idf_lr2021_radio.cpp, tracker/firmware/radio_test/main/main.cpp
- **Full message:** fix: RX watchdog crash + IRQ pin polling for packet reception
- **Relevance:** RADIO, FIRMWARE

### [balloon-circuit-design] fix: combine SPI reads into single CS-low txn + fix watchdog crash (2026-07-30) | tags: SPI, RADIO, FIRMWARE
- **Commit:** `c0a92a9` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/include/esp_idf_lr2021_radio.h, tracker/firmware/components/lr2021_transport/src/esp_idf_lr2021_radio.cpp, tracker/firmware/components/lr2021_transport/src/lr2021_transport.cpp (+1 more)
- **Full message:** fix: combine SPI reads into single CS-low txn + fix watchdog crash
- **Relevance:** SPI, RADIO, FIRMWARE

### [balloon-circuit-design] fix: port 5 SPI crash fixes from balloon-hermes lr2021_radio.c (5bf933b) (2026-07-30) | tags: SPI, RADIO, FIRMWARE
- **Commit:** `fc386b3` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/src/esp_idf_lr2021_radio.cpp, tracker/firmware/sdkconfig.defaults
- **Full message:** fix: port 5 SPI crash fixes from balloon-hermes lr2021_radio.c (5bf933b)
- **Relevance:** SPI, RADIO, FIRMWARE

### [balloon-circuit-design] refactor: replace RadioLib with lr2021_transport in firmware (ADR-020) (2026-07-30) | tags: RADIO, FIRMWARE
- **Commit:** `477b6d6` by Felix
- **Files:** tracker/firmware/components/meshcore/esp_idf/EspIdfInterfaces.h, tracker/firmware/main/CMakeLists.txt, tracker/firmware/main/app_main.cpp
- **Full message:** refactor: replace RadioLib with lr2021_transport in firmware (ADR-020)
- **Relevance:** RADIO, FIRMWARE

### [balloon-circuit-design] feat: EspHalLr2021Radio — ESP-IDF raw SPI adapter for LR2021 (20MHz direct GPIO) (2026-07-30) | tags: SPI, RADIO, FIRMWARE, HARDWARE
- **Commit:** `f4dddd0` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/CMakeLists.txt, tracker/firmware/components/lr2021_transport/include/esp_idf_lr2021_radio.h, tracker/firmware/components/lr2021_transport/src/esp_idf_lr2021_radio.cpp (+1 more)
- **Full message:** feat: EspHalLr2021Radio — ESP-IDF raw SPI adapter for LR2021 (20MHz direct GPIO)
- **Relevance:** SPI, RADIO, FIRMWARE, HARDWARE

### [balloon-circuit-design] docs: SPI layout constraints for LR2021 at 20MHz (2026-07-30) | tags: SPI, RADIO, FIRMWARE
- **Commit:** `b9712e5` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/SPI-LAYOUT-CONSTRAINTS.md
- **Full message:** docs: SPI layout constraints for LR2021 at 20MHz
- **Relevance:** SPI, RADIO, FIRMWARE

### [balloon-circuit-design] refactor: remove dead SX1280 opcode namespaces from lr2021_spi.h (ADR-020) (2026-07-29) | tags: RADIO, FIRMWARE
- **Commit:** `a59a758` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/include/lr2021_spi.h
- **Full message:** refactor: remove dead SX1280 opcode namespaces from lr2021_spi.h (ADR-020)
- **Relevance:** RADIO, FIRMWARE

### [balloon-circuit-design] docs: Phase 2 plan — hardware adapter + cross-track finding resolution (2026-07-29) | tags: GENERAL
- **Commit:** `a416b38` by Felix
- **Files:** docs/PLAN-phase2-hardware-adapter-2026-07-29.md
- **Full message:** docs: Phase 2 plan — hardware adapter + cross-track finding resolution
- **Relevance:** GENERAL

### [balloon-circuit-design] feat: encrypted multi-frame transport over LR2021 (Phase 3 host test) (2026-07-29) | tags: RADIO, FIRMWARE, TEST
- **Commit:** `4f864b5` by Felix
- **Files:** tracker/firmware/components/fips_radio_bridge/test/Makefile, tracker/firmware/components/fips_radio_bridge/test/test_fips_fragmented.cpp
- **Full message:** feat: encrypted multi-frame transport over LR2021 (Phase 3 host test)
- **Relevance:** RADIO, FIRMWARE, TEST

### [balloon-circuit-design] feat: FIPS Noise IK handshake over LR2021 transport (host integration test) (2026-07-29) | tags: RADIO, FIRMWARE, TEST
- **Commit:** `d0cb398` by Felix
- **Files:** tracker/firmware/components/fips_radio_bridge/CMakeLists.txt, tracker/firmware/components/fips_radio_bridge/include/fips_radio_bridge.h, tracker/firmware/components/fips_radio_bridge/src/fips_radio_bridge.cpp (+3 more)
- **Full message:** feat: FIPS Noise IK handshake over LR2021 transport (host integration test)
- **Relevance:** RADIO, FIRMWARE, TEST

### [balloon-circuit-design] feat: extract LR2021 transport layer from microfips to balloon-fresh (C++ ESP-ID (2026-07-29) | tags: RADIO, FIRMWARE, TEST
- **Commit:** `75ffda3` by Felix
- **Files:** tracker/firmware/components/lr2021_transport/CMakeLists.txt, tracker/firmware/components/lr2021_transport/include/lr2021_framing.h, tracker/firmware/components/lr2021_transport/include/lr2021_spi.h (+6 more)
- **Full message:** feat: extract LR2021 transport layer from microfips to balloon-fresh (C++ ESP-IDF port)
- **Relevance:** RADIO, FIRMWARE, TEST

### [balloon-circuit-design] Revert "feat(coordination): add balloon-multiwan-bonding as 10th track" (2026-07-30) | tags: GENERAL
- **Commit:** `dedb5bd` by Felix
- **Files:** docs/coordination/TRACKS-REGISTRY.yaml
- **Full message:** Revert "feat(coordination): add balloon-multiwan-bonding as 10th track"
- **Relevance:** GENERAL

### [balloon-circuit-design] feat(coordination): add balloon-multiwan-bonding as 10th track (2026-07-30) | tags: GENERAL
- **Commit:** `49aff2d` by Felix
- **Files:** docs/coordination/TRACKS-REGISTRY.yaml
- **Full message:** feat(coordination): add balloon-multiwan-bonding as 10th track
- **Relevance:** GENERAL

### [balloon-circuit-design] data: RP2040 baseline capture + results — 1760kbps at 10.40MHz SPI (2026-07-30) | tags: SPI, RADIO, TEST
- **Commit:** `a31f971` by Felix
- **Files:** .gitignore, captures/bench-rp2040.sr, docs/rp2040-baseline-results.md
- **Full message:** data: RP2040 baseline capture + results — 1760kbps at 10.40MHz SPI
- **Relevance:** SPI, RADIO, TEST

### [balloon-circuit-design] feat(nostr): rewrite nostr_store to flash-backed design (2026-07-29) | tags: FIRMWARE, PROTOCOL, TEST
- **Commit:** `423e1f8` by Felix
- **Files:** tracker/firmware/components/nostr_store/include/nostr_store.h, tracker/firmware/components/nostr_store/nostr_store.c, tracker/firmware/components/nostr_store/test/test_nostr_store.c (+1 more)
- **Full message:** feat(nostr): rewrite nostr_store to flash-backed design
- **Relevance:** FIRMWARE, PROTOCOL, TEST

### [balloon-circuit-design] docs(nostr): extraction plan for store-and-forward on ESP32-C3 (2026-07-29) | tags: PROTOCOL
- **Commit:** `041c231` by Felix
- **Files:** AGENTS.md, docs/STATUS-balloon-nostr.md
- **Full message:** docs(nostr): extraction plan for store-and-forward on ESP32-C3
- **Relevance:** PROTOCOL

### [balloon-circuit-design] feat(mesh_adapter): wire encrypt/decrypt callbacks for FIPS integration (2026-07-29) | tags: FIRMWARE, TEST
- **Commit:** `5d17114` by Felix
- **Files:** tests/test_c_host.py, tracker/firmware/components/mesh_adapter/include/mesh_adapter.h, tracker/firmware/components/mesh_adapter/mesh_adapter.c (+1 more)
- **Full message:** feat(mesh_adapter): wire encrypt/decrypt callbacks for FIPS integration
- **Relevance:** FIRMWARE, TEST

### [balloon-circuit-design] feat(blossom_datagram): new component — bridge mesh datagram to blob storage (2026-07-29) | tags: FIRMWARE, PROTOCOL, TEST
- **Commit:** `7971810` by Felix
- **Files:** tests/test_c_host.py, tracker/firmware/components/blossom_datagram/CMakeLists.txt, tracker/firmware/components/blossom_datagram/blossom_datagram.c (+2 more)
- **Full message:** feat(blossom_datagram): new component — bridge mesh datagram to blob storage
- **Relevance:** FIRMWARE, PROTOCOL, TEST

### [balloon-circuit-design] build(mesh_adapter): add CMakeLists.txt — was only mesh component missing one (2026-07-29) | tags: FIRMWARE, PROTOCOL
- **Commit:** `b60c583` by Felix
- **Files:** tracker/firmware/components/mesh_adapter/CMakeLists.txt
- **Full message:** build(mesh_adapter): add CMakeLists.txt — was only mesh component missing one
- **Relevance:** FIRMWARE, PROTOCOL

### [balloon-circuit-design] feat(nostr_store): implement nostr_event_deserialize() (2026-07-29) | tags: FIRMWARE, TEST
- **Commit:** `e3c1575` by Felix
- **Files:** tracker/firmware/components/nostr_store/nostr_store.c, tracker/firmware/components/nostr_store/test/test_nostr_store.c
- **Full message:** feat(nostr_store): implement nostr_event_deserialize()
- **Relevance:** FIRMWARE, TEST

### [balloon-circuit-design] docs+feat: SPI timing findings + payload size sweep targets (2026-07-29) | tags: SPI
- **Commit:** `af2457f` by Felix
- **Files:** Makefile, docs/spi-timing-analysis.md, firmware/rp2040/platformio.ini
- **Full message:** docs+feat: SPI timing findings + payload size sweep targets
- **Relevance:** SPI


### [balloon-hermes] feat(coordination): add balloon-multiwan-bonding as 10th track (2026-07-30) | tags: GENERAL
- **Commit:** `49aff2d` by Felix
- **Files:** docs/coordination/TRACKS-REGISTRY.yaml
- **Full message:** feat(coordination): add balloon-multiwan-bonding as 10th track
- **Relevance:** GENERAL

### [balloon-hermes] feat(nostr): rewrite nostr_store to flash-backed design (2026-07-29) | tags: FIRMWARE, PROTOCOL, TEST
- **Commit:** `423e1f8` by Felix
- **Files:** tracker/firmware/components/nostr_store/include/nostr_store.h, tracker/firmware/components/nostr_store/nostr_store.c, tracker/firmware/components/nostr_store/test/test_nostr_store.c (+1 more)
- **Full message:** feat(nostr): rewrite nostr_store to flash-backed design
- **Relevance:** FIRMWARE, PROTOCOL, TEST

### [balloon-hermes] docs(nostr): extraction plan for store-and-forward on ESP32-C3 (2026-07-29) | tags: PROTOCOL
- **Commit:** `041c231` by Felix
- **Files:** AGENTS.md, docs/STATUS-balloon-nostr.md
- **Full message:** docs(nostr): extraction plan for store-and-forward on ESP32-C3
- **Relevance:** PROTOCOL

### [balloon-circuit-design] chore(pcb): commit stale F33 DRC intermediate reports (2026-07-30) | tags: HARDWARE
- **Commit:** `60db9f0` by Felix
- **Files:** tracker/hardware/drc_f33_v3.txt, tracker/hardware/drc_f33_v4.txt
- **Full message:** chore(pcb): commit stale F33 DRC intermediate reports
- **Relevance:** HARDWARE

### [balloon-circuit-design] fix(pcb): F33 B.Cu routing for power+UART+I2C — shorts 44→15, crossings 14→15 (2026-07-30) | tags: HARDWARE, PROTOCOL
- **Commit:** `32aaefa` by Felix
- **Files:** tracker/hardware/drc_f33_v5.txt, tracker/hardware/gen_pcb.py, tracker/hardware/hub_board_f33.kicad_pcb (+1 more)
- **Full message:** fix(pcb): F33 B.Cu routing for power+UART+I2C — shorts 44→15, crossings 14→15
- **Relevance:** HARDWARE, PROTOCOL

### [balloon-circuit-design] fix(pcb): F33 power bus to B.Cu + GND via relocation — shorts 27→19 (2026-07-30) | tags: HARDWARE
- **Commit:** `d8fecdd` by Felix
- **Files:** tracker/hardware/drc_f33_v2.txt, tracker/hardware/gen_pcb.py, tracker/hardware/hub_board_f33.kicad_pcb (+1 more)
- **Full message:** fix(pcb): F33 power bus to B.Cu + GND via relocation — shorts 27→19
- **Relevance:** HARDWARE

### [balloon-circuit-design] fix(pcb): F33 Router integration + U1 pad pitch fix — shorts 44→27 (2026-07-30) | tags: HARDWARE
- **Commit:** `5df08e6` by Felix
- **Files:** tracker/hardware/drc_f33_fixed.txt, tracker/hardware/gen_pcb.py
- **Full message:** fix(pcb): F33 Router integration + U1 pad pitch fix — shorts 44→27
- **Relevance:** HARDWARE

### [balloon-circuit-design] chore(pcb): commit DRC V1 final2 report (2026-07-30) | tags: HARDWARE
- **Commit:** `5418d25` by Felix
- **Files:** tracker/hardware/drc_v1_final2.txt
- **Full message:** chore(pcb): commit DRC V1 final2 report
- **Relevance:** HARDWARE


### [balloon-circuit-design] feat(schematic): dual-variant hub board — non-PA + F33 2W PA (2026-07-29) | tags: HARDWARE
- **Commit:** `2ce15d5` by Felix
- **Files:** docs/DUAL-VARIANT-DESIGN.md, tracker/hardware/hub_board/hub_board_f33.net, tracker/hardware/hub_board/hub_schematic.log (+5 more)
- **Full message:** feat(schematic): dual-variant hub board — non-PA + F33 2W PA
- **Relevance:** HARDWARE


### [balloon-hermes] docs: consolidation execution plan + Makefile updates + discoveries sync (2026-07-26) | tags: GENERAL
- **Commit:** `c03dbb8` by Felix
- **Files:** Makefile, docs/coordination/DISCOVERIES.md, docs/plans/CONSOLIDATION-EXECUTION.md
- **Full message:** docs: consolidation execution plan + Makefile updates + discoveries sync
- **Relevance:** GENERAL

### [balloon-tollgate] docs: discovery sync review 2026-07-26 — both findings informational only (2026-07-26) | tags: GENERAL
- **Commit:** `5b1518f` by Felix
- **Files:** docs/STATUS-balloon-tollgate.md
- **Full message:** docs: discovery sync review 2026-07-26 — both findings informational only
- **Relevance:** GENERAL

### [balloon-pow] docs: track status + discovery sync acknowledgment — Phase 1 extraction in progr (2026-07-26) | tags: GENERAL
- **Commit:** `9685bc4` by Felix
- **Files:** docs/STATUS-balloon-pow.md
- **Full message:** docs: track status + discovery sync acknowledgment — Phase 1 extraction in progress
- **Relevance:** GENERAL


### [balloon-hermes] docs: multi-level delegation hierarchy — sub-managers delegate too (2026-07-25) | tags: GENERAL
- **Commit:** `4566437` by Felix
- **Files:** AGENTS.md
- **Full message:** docs: multi-level delegation hierarchy — sub-managers delegate too
- **Relevance:** GENERAL

### [balloon-hermes] docs: anti-pattern warning + SDR handover (2026-07-25) | tags: GENERAL
- **Commit:** `fdbe634` by Felix
- **Files:** AGENTS.md
- **Full message:** docs: anti-pattern warning + SDR handover
- **Relevance:** GENERAL

### [balloon-hermes] docs: add Board Access Protocol — MANDATORY enforcement section (2026-07-24) | tags: GENERAL
- **Commit:** `a256fe0` by Felix
- **Files:** AGENTS.md
- **Full message:** docs: add Board Access Protocol — MANDATORY enforcement section
- **Relevance:** GENERAL

### [balloon-hermes] fix: FLRC byte alignment + app-layer CRC-16 + FIFO clear + sync search (2026-07-24) | tags: RADIO, FIRMWARE
- **Commit:** `9b740aa` by Felix
- **Files:** docs/coordination/FLASH-QUEUE.md, firmware/BUILD_COUNTER.txt, firmware/BUILD_MAP.md (+5 more)
- **Full message:** fix: FLRC byte alignment + app-layer CRC-16 + FIFO clear + sync search
- **Relevance:** RADIO, FIRMWARE

### [balloon-hermes] data: walk test results — FLRC packets received but CRC/byte alignment still off (2026-07-24) | tags: RADIO, TEST
- **Commit:** `b182b81` by Felix
- **Files:** data/walk-balcony-rx-20260724.txt, data/walk-test-results.png, data/walk_test_20260724/capture_env_outdoor_20260724_180347.csv (+3 more)
- **Full message:** data: walk test results — FLRC packets received but CRC/byte alignment still off
- **Relevance:** RADIO, TEST

### [balloon-hermes] data: walk test capture — GPS payload verified on LoRa phases (2026-07-24) | tags: RADIO, FIRMWARE, TEST
- **Commit:** `be354b0` by Felix
- **Files:** AGENTS.md, data/walk-fix-verified-rx.txt, firmware/rp2040/platformio.ini (+1 more)
- **Full message:** data: walk test capture — GPS payload verified on LoRa phases
- **Relevance:** RADIO, FIRMWARE, TEST

### [balloon-hermes] docs: upgrade guardrails — 3 communication channels (status + task + escalation) (2026-07-24) | tags: GENERAL
- **Commit:** `9b2fc5f` by Felix
- **Files:** AGENTS.md
- **Full message:** docs: upgrade guardrails — 3 communication channels (status + task + escalation)
- **Relevance:** GENERAL

### [balloon-hermes] data: comprehensive plot + autonomous GPS sweep results (2026-07-24) | tags: TEST
- **Commit:** `980263f` by Felix
- **Files:** data/box-mounted-rx-20260724.txt, data/comprehensive_plot_20260724.png, data/generate_summary_plot.py (+8 more)
- **Full message:** data: comprehensive plot + autonomous GPS sweep results
- **Relevance:** TEST

### [balloon-hermes] data: save all test captures + results plot to git repo (not /tmp) (2026-07-24) | tags: TEST
- **Commit:** `72cbd77` by Felix
- **Files:** data/rx-capture-20260723.txt, data/sweep-rx-debug-20260724.txt, data/sweep-rx-fixed-20260724.txt (+4 more)
- **Full message:** data: save all test captures + results plot to git repo (not /tmp)
- **Relevance:** TEST

### [balloon-hermes] docs: mandate BoardSerial wrapper — no raw serial.Serial() on board ports (2026-07-24) | tags: GENERAL
- **Commit:** `171387d` by Felix
- **Files:** AGENTS.md
- **Full message:** docs: mandate BoardSerial wrapper — no raw serial.Serial() on board ports
- **Relevance:** GENERAL

### [balloon-hermes] docs: add BOARD ACCESS mutex lock section to AGENTS.md (2026-07-23) | tags: GENERAL
- **Commit:** `34eadfe` by Felix
- **Files:** AGENTS.md
- **Full message:** docs: add BOARD ACCESS mutex lock section to AGENTS.md
- **Relevance:** GENERAL

### [balloon-hermes] docs: add anti-coordination guardrails to AGENTS.md (2026-07-18) | tags: GENERAL
- **Commit:** `5cc537e` by c03rad0r
- **Files:** AGENTS.md
- **Full message:** docs: add anti-coordination guardrails to AGENTS.md
- **Relevance:** GENERAL

### [balloon-hermes] chore(data): add range-test-results.csv template (2026-07-18) | tags: TEST
- **Commit:** `f39fdb9` by c03rad0r
- **Files:** data/range-test-results.csv
- **Full message:** chore(data): add range-test-results.csv template
- **Relevance:** TEST

### [balloon-circuit-design] feat(enclosure): oversized Variant B — guarantee fit without calipers (2026-07-26) | tags: GENERAL
- **Commit:** `a7e599a` by Felix
- **Files:** tracker/hardware/enclosure/balloon_dev_case_big.scad, tracker/hardware/enclosure/bottom_big_oversize.stl, tracker/hardware/enclosure/lid_big_oversize.stl (+1 more)
- **Full message:** feat(enclosure): oversized Variant B — guarantee fit without calipers
- **Relevance:** GENERAL


### [balloon-circuit-design] feat(enclosure): Variant B — big LR2021 dev board with SMA pass-through (2026-07-26) | tags: RADIO
- **Commit:** `72b7727` by Felix
- **Files:** tracker/hardware/enclosure/README_big.md, tracker/hardware/enclosure/balloon_dev_case_big.scad, tracker/hardware/enclosure/bottom_big.stl (+2 more)
- **Full message:** feat(enclosure): Variant B — big LR2021 dev board with SMA pass-through
- **Relevance:** RADIO

### [balloon-circuit-design] feat(enclosure): oversized GPS slot — fits all M10S breakouts (2026-07-26) | tags: GENERAL
- **Commit:** `2efbe9d` by Felix
- **Files:** tracker/hardware/enclosure/balloon_dev_case.scad, tracker/hardware/enclosure/bottom_v2_generic.stl, tracker/hardware/enclosure/lid_v2_generic.stl (+1 more)
- **Full message:** feat(enclosure): oversized GPS slot — fits all M10S breakouts
- **Relevance:** GENERAL

### [balloon-circuit-design] feat(enclosure): v2 — 4-board design with GPS + RP2040 (2026-07-26) | tags: GENERAL
- **Commit:** `553606e` by Felix
- **Files:** tracker/hardware/enclosure/README.md, tracker/hardware/enclosure/balloon_dev_case.scad, tracker/hardware/enclosure/bottom_v2.stl (+2 more)
- **Full message:** feat(enclosure): v2 — 4-board design with GPS + RP2040
- **Relevance:** GENERAL

### [balloon-circuit-design] feat(enclosure): parametric waterproof dev board case (2026-07-26) | tags: GENERAL
- **Commit:** `a8f509e` by Felix
- **Files:** tracker/hardware/enclosure/README.md, tracker/hardware/enclosure/balloon_dev_case.scad, tracker/hardware/enclosure/bottom.stl (+4 more)
- **Full message:** feat(enclosure): parametric waterproof dev board case
- **Relevance:** GENERAL


### [balloon-range-tests] docs: multi-level delegation hierarchy — sub-managers delegate too (2026-07-25) | tags: GENERAL
- **Commit:** `4566437` by Felix
- **Files:** AGENTS.md
- **Full message:** docs: multi-level delegation hierarchy — sub-managers delegate too
- **Relevance:** GENERAL

### [balloon-range-tests] docs: anti-pattern warning + SDR handover (2026-07-25) | tags: GENERAL
- **Commit:** `fdbe634` by Felix
- **Files:** AGENTS.md
- **Full message:** docs: anti-pattern warning + SDR handover
- **Relevance:** GENERAL


### [balloon-tollgate] docs: adopt hard board locking v3 + flash queue + serial wrapper from discovery  (2026-07-24) | tags: FIRMWARE
- **Commit:** `a785c70` by Felix
- **Files:** AGENTS.md, docs/STATUS-balloon-tollgate.md
- **Full message:** docs: adopt hard board locking v3 + flash queue + serial wrapper from discovery sync
- **Relevance:** FIRMWARE


### [balloon-hermes] docs: comprehensive next walk test plan — 6 phases with sub-manager dispatch mat (2026-07-24) | tags: TEST
- **Commit:** `655e458` by Felix
- **Files:** docs/coordination/PLAN-NEXT-WALK-TEST.md
- **Full message:** docs: comprehensive next walk test plan — 6 phases with sub-manager dispatch matrix
- **Relevance:** TEST

### [balloon-hermes] fix(tools): Phase 2 — hard board locking + flash queue (2026-07-24) | tags: FIRMWARE
- **Commit:** `35b292c` by Felix
- **Files:** docs/coordination/DISCOVERIES.md, docs/coordination/FLASH-QUEUE.md, tools/balloon-board-lock.py (+1 more)
- **Full message:** fix(tools): Phase 2 — hard board locking + flash queue
- **Relevance:** FIRMWARE

### [balloon-hermes] docs: comprehensive FLRC alignment fix plan — 3 bugs, 8 phases, ~3hr effort (2026-07-24) | tags: RADIO
- **Commit:** `568a742` by Felix
- **Files:** docs/coordination/PLAN-FLRC-ALIGNMENT-FIX.md
- **Full message:** docs: comprehensive FLRC alignment fix plan — 3 bugs, 8 phases, ~3hr effort
- **Relevance:** RADIO

### [balloon-range-tests] docs: add Board Access Protocol — MANDATORY enforcement section (2026-07-24) | tags: GENERAL
- **Commit:** `a256fe0` by Felix
- **Files:** AGENTS.md
- **Full message:** docs: add Board Access Protocol — MANDATORY enforcement section
- **Relevance:** GENERAL

### [balloon-range-tests] fix: FLRC byte alignment + app-layer CRC-16 + FIFO clear + sync search (2026-07-24) | tags: RADIO, FIRMWARE
- **Commit:** `9b740aa` by Felix
- **Files:** docs/coordination/FLASH-QUEUE.md, firmware/BUILD_COUNTER.txt, firmware/BUILD_MAP.md (+5 more)
- **Full message:** fix: FLRC byte alignment + app-layer CRC-16 + FIFO clear + sync search
- **Relevance:** RADIO, FIRMWARE

### [balloon-speed-tests] docs: add Board Access Protocol — MANDATORY enforcement section (2026-07-24) | tags: GENERAL
- **Commit:** `373c230` by Felix
- **Files:** AGENTS.md
- **Full message:** docs: add Board Access Protocol — MANDATORY enforcement section
- **Relevance:** GENERAL

### [balloon-speed-tests] fix: board lock chmod enforcement + pio upload guard shim (2026-07-24) | tags: FIRMWARE
- **Commit:** `ef60a51` by Felix
- **Files:** docs/coordination/FLASH-QUEUE.md, tools/balloon-board-lock.py, tools/pio-flash.sh (+1 more)
- **Full message:** fix: board lock chmod enforcement + pio upload guard shim
- **Relevance:** FIRMWARE


### [balloon-hermes] docs: firmware integrity plan — 5-layer binary control system (2026-07-24) | tags: GENERAL
- **Commit:** `b7edcee` by Felix
- **Files:** docs/coordination/PLAN-FIRMWARE-INTEGRITY.md
- **Full message:** docs: firmware integrity plan — 5-layer binary control system
- **Relevance:** GENERAL

### [balloon-fips] docs: cross-track analysis — FLRC byte alignment + GPS payload findings from ran (2026-07-24) | tags: RADIO
- **Commit:** `2e2ff78` by Felix
- **Files:** docs/CROSS-TRACK-ANALYSIS-FLRC-ALIGNMENT.md
- **Full message:** docs: cross-track analysis — FLRC byte alignment + GPS payload findings from range-tests
- **Relevance:** RADIO


### [balloon-hermes] checkpoint: main repo committed before walk test freeze (2026-07-24) | tags: TEST
- **Commit:** `54500a1` by Felix
- **Files:** docs/HANDOVER-KEY-ROTATION.md, docs/coordination/DISCOVERIES.md
- **Full message:** checkpoint: main repo committed before walk test freeze
- **Relevance:** TEST

### [balloon-hermes] docs: add DELEGATION-PROMPT.md — orchestrator task push template (2026-07-24) | tags: GENERAL
- **Commit:** `eee5bcb` by Felix
- **Files:** docs/coordination/DELEGATION-PROMPT.md
- **Full message:** docs: add DELEGATION-PROMPT.md — orchestrator task push template
- **Relevance:** GENERAL

### [balloon-tollgate] Add DELEGATION EXPECTATIONS (POSITIVE COLLABORATION) block to AGENTS.md (2026-07-24) | tags: GENERAL
- **Commit:** `74d7350` by Felix
- **Files:** AGENTS.md
- **Full message:** Add DELEGATION EXPECTATIONS (POSITIVE COLLABORATION) block to AGENTS.md
- **Relevance:** GENERAL

### [balloon-fips] Add DELEGATION EXPECTATIONS (POSITIVE COLLABORATION) block to AGENTS.md (2026-07-24) | tags: GENERAL
- **Commit:** `1e811c0` by Felix
- **Files:** AGENTS.md
- **Full message:** Add DELEGATION EXPECTATIONS (POSITIVE COLLABORATION) block to AGENTS.md
- **Relevance:** GENERAL

### [balloon-range-tests] data: walk test results — FLRC packets received but CRC/byte alignment still off (2026-07-24) | tags: RADIO, TEST
- **Commit:** `b182b81` by Felix
- **Files:** data/walk-balcony-rx-20260724.txt, data/walk-test-results.png, data/walk_test_20260724/capture_env_outdoor_20260724_180347.csv (+3 more)
- **Full message:** data: walk test results — FLRC packets received but CRC/byte alignment still off
- **Relevance:** RADIO, TEST

### [balloon-range-tests] data: walk test capture — GPS payload verified on LoRa phases (2026-07-24) | tags: RADIO, FIRMWARE, TEST
- **Commit:** `be354b0` by Felix
- **Files:** AGENTS.md, data/walk-fix-verified-rx.txt, firmware/rp2040/platformio.ini (+1 more)
- **Full message:** data: walk test capture — GPS payload verified on LoRa phases
- **Relevance:** RADIO, FIRMWARE, TEST

### [balloon-range-tests] docs: upgrade guardrails — 3 communication channels (status + task + escalation) (2026-07-24) | tags: GENERAL
- **Commit:** `9b2fc5f` by Felix
- **Files:** AGENTS.md
- **Full message:** docs: upgrade guardrails — 3 communication channels (status + task + escalation)
- **Relevance:** GENERAL

### [balloon-range-tests] data: comprehensive plot + autonomous GPS sweep results (2026-07-24) | tags: TEST
- **Commit:** `980263f` by Felix
- **Files:** data/box-mounted-rx-20260724.txt, data/comprehensive_plot_20260724.png, data/generate_summary_plot.py (+8 more)
- **Full message:** data: comprehensive plot + autonomous GPS sweep results
- **Relevance:** TEST

### [balloon-speed-tests] Add DELEGATION EXPECTATIONS (POSITIVE COLLABORATION) block to AGENTS.md (2026-07-24) | tags: GENERAL
- **Commit:** `c849bd4` by Felix
- **Files:** AGENTS.md
- **Full message:** Add DELEGATION EXPECTATIONS (POSITIVE COLLABORATION) block to AGENTS.md
- **Relevance:** GENERAL

### [balloon-speed-tests] docs: upgrade guardrails + fix copy-paste name bug (2026-07-24) | tags: GENERAL
- **Commit:** `2ea0017` by Felix
- **Files:** AGENTS.md
- **Full message:** docs: upgrade guardrails + fix copy-paste name bug
- **Relevance:** GENERAL

### [balloon-circuit-design] wip: F33 module footprint + schematic updates before walk test freeze (2026-07-24) | tags: HARDWARE, TEST
- **Commit:** `246616e` by Felix
- **Files:** docs/F33-MODULE-PLAN.md, tracker/hardware/footprints/nicerf-lora2021f33-2g4.json, tracker/hardware/hub_board/hub_schematic.py (+2 more)
- **Full message:** wip: F33 module footprint + schematic updates before walk test freeze
- **Relevance:** HARDWARE, TEST

### [balloon-circuit-design] Add DELEGATION EXPECTATIONS (POSITIVE COLLABORATION) block to AGENTS.md (2026-07-24) | tags: GENERAL
- **Commit:** `af3674e` by Felix
- **Files:** AGENTS.md
- **Full message:** Add DELEGATION EXPECTATIONS (POSITIVE COLLABORATION) block to AGENTS.md
- **Relevance:** GENERAL


### [balloon-hermes] docs: update discoveries sync (2026-07-24) | tags: GENERAL
- **Commit:** `698a8b8` by Felix
- **Files:** docs/coordination/DISCOVERIES.md
- **Full message:** docs: update discoveries sync
- **Relevance:** GENERAL

### [balloon-range-tests] data: save all test captures + results plot to git repo (not /tmp) (2026-07-24) | tags: TEST
- **Commit:** `72cbd77` by Felix
- **Files:** data/rx-capture-20260723.txt, data/sweep-rx-debug-20260724.txt, data/sweep-rx-fixed-20260724.txt (+4 more)
- **Full message:** data: save all test captures + results plot to git repo (not /tmp)
- **Relevance:** TEST


### [balloon-hermes] plan: LR2021 full characterization — coordinates speed-tests + range-tests (2026-07-24) | tags: RADIO
- **Commit:** `44f50d2` by Felix
- **Files:** docs/coordination/LR2021-FULL-CHARACTERIZATION-PLAN.md
- **Full message:** plan: LR2021 full characterization — coordinates speed-tests + range-tests
- **Relevance:** RADIO

### [balloon-hermes] docs: LR2021 full characterization plan — unified speed+range test matrix (2026-07-24) | tags: RADIO, TEST
- **Commit:** `4835477` by Felix
- **Files:** docs/coordination/LR2021-FULL-CHARACTERIZATION-PLAN.md
- **Full message:** docs: LR2021 full characterization plan — unified speed+range test matrix
- **Relevance:** RADIO, TEST

### [balloon-hermes] feat: anti-theft lock improvements for balloon-board-lock.py (2026-07-24) | tags: GENERAL
- **Commit:** `3b5025a` by Felix
- **Files:** docs/coordination/DISCOVERIES.md, firmware/esp32-uart-bridge/src/main.cpp, tools/balloon-board-lock.py
- **Full message:** feat: anti-theft lock improvements for balloon-board-lock.py
- **Relevance:** GENERAL

### [balloon-hermes] docs: update enforcement plan status — layers 1-5 done (2026-07-24) | tags: GENERAL
- **Commit:** `b49318c` by Felix
- **Files:** docs/coordination/BOARD-MUTEX-ENFORCEMENT-PLAN.md
- **Full message:** docs: update enforcement plan status — layers 1-5 done
- **Relevance:** GENERAL

### [balloon-hermes] feat: enforce board mutex with serial wrapper + assertion + monitor (2026-07-24) | tags: GENERAL
- **Commit:** `4e4956b` by Felix
- **Files:** docs/coordination/BOARD-MUTEX-ENFORCEMENT-PLAN.md, tools/board-lock-assert.py, tools/board-serial.py (+1 more)
- **Full message:** feat: enforce board mutex with serial wrapper + assertion + monitor
- **Relevance:** GENERAL

### [balloon-range-tests] docs: mandate BoardSerial wrapper — no raw serial.Serial() on board ports (2026-07-24) | tags: GENERAL
- **Commit:** `171387d` by Felix
- **Files:** AGENTS.md
- **Full message:** docs: mandate BoardSerial wrapper — no raw serial.Serial() on board ports
- **Relevance:** GENERAL

### [balloon-speed-tests] docs: multi-radio sweep characterization results (2026-07-24) | tags: GENERAL
- **Commit:** `343342e` by Felix
- **Files:** docs/SWEEP-RESULTS.md
- **Full message:** docs: multi-radio sweep characterization results
- **Relevance:** GENERAL

### [balloon-speed-tests] docs: mandate BoardSerial wrapper — no raw serial.Serial() on board ports (2026-07-24) | tags: GENERAL
- **Commit:** `d7bfc78` by Felix
- **Files:** AGENTS.md
- **Full message:** docs: mandate BoardSerial wrapper — no raw serial.Serial() on board ports
- **Relevance:** GENERAL


### [balloon-speed-tests] docs: complete handover for range testing group — all results, bugs, setup, plan (2026-07-24) | tags: GENERAL
- **Commit:** `0fe824e` by Felix
- **Files:** docs/HANDOVER-COMPLETE-2026-07-24.md
- **Full message:** docs: complete handover for range testing group — all results, bugs, setup, plan
- **Relevance:** GENERAL

### [balloon-speed-tests] docs: power sweep results + master JSON + range testing handover (2026-07-24) | tags: GENERAL
- **Commit:** `c1c1811` by Felix
- **Files:** docs/master-results.json, docs/power-sweep-results-2026-07-24.md, docs/range-testing-handover.md
- **Full message:** docs: power sweep results + master JSON + range testing handover
- **Relevance:** GENERAL


### [balloon-speed-tests] docs: comprehensive session summary — 10 commits, all results, plan status (2026-07-24) | tags: GENERAL
- **Commit:** `2be0010` by Felix
- **Files:** docs/SESSION-SUMMARY-2026-07-24.md
- **Full message:** docs: comprehensive session summary — 10 commits, all results, plan status
- **Relevance:** GENERAL


### [balloon-range-tests] docs: add BOARD ACCESS mutex lock section to AGENTS.md (2026-07-23) | tags: GENERAL
- **Commit:** `34eadfe` by Felix
- **Files:** AGENTS.md
- **Full message:** docs: add BOARD ACCESS mutex lock section to AGENTS.md
- **Relevance:** GENERAL

### [balloon-speed-tests] docs: add BOARD ACCESS mutex lock section to AGENTS.md (2026-07-23) | tags: GENERAL
- **Commit:** `4aa7385` by Felix
- **Files:** AGENTS.md
- **Full message:** docs: add BOARD ACCESS mutex lock section to AGENTS.md
- **Relevance:** GENERAL


### [balloon-hermes] chore(data): adopt range-test-results.csv template from speed-tests track (2026-07-23) | tags: TEST
- **Commit:** `51cb97d` by Felix
- **Files:** data/range-test-results.csv
- **Full message:** chore(data): adopt range-test-results.csv template from speed-tests track
- **Relevance:** TEST


### [balloon-speed-tests] docs: add anti-coordination guardrails to AGENTS.md (2026-07-18) | tags: GENERAL
- **Commit:** `5cc537e` by c03rad0r
- **Files:** AGENTS.md
- **Full message:** docs: add anti-coordination guardrails to AGENTS.md
- **Relevance:** GENERAL

### [balloon-speed-tests] chore(data): add range-test-results.csv template (2026-07-18) | tags: TEST
- **Commit:** `f39fdb9` by c03rad0r
- **Files:** data/range-test-results.csv
- **Full message:** chore(data): add range-test-results.csv template
- **Relevance:** TEST


### [balloon-hermes] docs: purge RadioLib references from circuit-design hardware docs (2026-07-23) | tags: RADIO, HARDWARE
- **Commit:** `1c3e089` by Felix
- **Files:** tracker/hardware/FLIGHT-BOARD-PLAN.md, tracker/hardware/footprints/nicerf-lora2021.json, tracker/hardware/hub_board_diy/implementation-plan.md
- **Full message:** docs: purge RadioLib references from circuit-design hardware docs
- **Relevance:** RADIO, HARDWARE


### [balloon-hermes] fix: deprecate RadioLib LR2021, adopt raw 2-byte opcode protocol (2026-07-23) | tags: SPI, RADIO
- **Commit:** `811a156` by Felix
- **Files:** AGENTS.md, docs/adr/017-lr2021-only-ban-sx1280.md, docs/adr/020-deprecate-radiolib-adopt-raw-lr2021-spi.md (+8 more)
- **Full message:** fix: deprecate RadioLib LR2021, adopt raw 2-byte opcode protocol
- **Relevance:** SPI, RADIO


### [balloon-hermes] ban SX1280 from codebase: ADR-017 + AGENTS.md warning + deprecate 5 source files (2026-07-23) | tags: RADIO
- **Commit:** `d8a7187` by Felix
- **Files:** AGENTS.md, docs/adr/017-lr2021-only-ban-sx1280.md, docs/coordination/DISCOVERIES.md (+6 more)
- **Full message:** ban SX1280 from codebase: ADR-017 + AGENTS.md warning + deprecate 5 source files
- **Relevance:** RADIO


### [balloon-hermes] docs: forward speed-tests learnings to range-tests via DISCOVERIES.md (2026-07-22) | tags: GENERAL
- **Commit:** `f07c812` by Felix
- **Files:** docs/coordination/DISCOVERIES.md
- **Full message:** docs: forward speed-tests learnings to range-tests via DISCOVERIES.md
- **Relevance:** GENERAL


### [balloon-hermes] docs: hierarchy upgrade notification template for sub-managers (2026-07-18) | tags: GENERAL
- **Commit:** `bc4b512` by c03rad0r
- **Files:** docs/coordination/HIERARCHY-UPGRADE-NOTIFICATION.md
- **Full message:** docs: hierarchy upgrade notification template for sub-managers
- **Relevance:** GENERAL

### [balloon-hermes] docs: hierarchy upgrade announcement for sub-track groups (2026-07-18) | tags: GENERAL
- **Commit:** `de6c0a5` by c03rad0r
- **Files:** docs/coordination/HIERARCHY-UPGRADE-ANNOUNCEMENT.md
- **Full message:** docs: hierarchy upgrade announcement for sub-track groups
- **Relevance:** GENERAL

### [balloon-hermes] docs: hierarchy update prompt for sub-manager tracks (2026-07-18) | tags: GENERAL
- **Commit:** `2841a9a` by c03rad0r
- **Files:** docs/coordination/HIERARCHY-UPDATE.md
- **Full message:** docs: hierarchy update prompt for sub-manager tracks
- **Relevance:** GENERAL

### [balloon-hermes] docs: reconcile coordinator tracking + index to 10-track hierarchy (2026-07-18) | tags: GENERAL
- **Commit:** `2da7af5` by c03rad0r
- **Files:** docs/coordination/COORDINATOR-TRACKING.md, docs/coordination/INDEX.md
- **Full message:** docs: reconcile coordinator tracking + index to 10-track hierarchy
- **Relevance:** GENERAL

### [balloon-hermes] docs: bootstrap prompts for 2 new tracks + status request template + registry (2026-07-18) | tags: GENERAL
- **Commit:** `594f5a0` by c03rad0r
- **Files:** docs/coordination/BOOTSTRAP-circuit-design.md, docs/coordination/BOOTSTRAP-pre-stretching.md
- **Full message:** docs: bootstrap prompts for 2 new tracks + status request template + registry
- **Relevance:** GENERAL

### [balloon-hermes] docs: bootstrap prompts for 2 new tracks (pre-stretching, circuit-design) (2026-07-18) | tags: GENERAL
- **Commit:** `a343a0a` by c03rad0r
- **Files:** docs/coordination/BOOTSTRAP-circuit-design.md, docs/coordination/BOOTSTRAP-pre-stretching.md
- **Full message:** docs: bootstrap prompts for 2 new tracks (pre-stretching, circuit-design)
- **Relevance:** GENERAL

### [balloon-hermes] feat: add balloon-pre-stretching and balloon-circuit-design tracks to registry (2026-07-18) | tags: GENERAL
- **Commit:** `efc0a87` by c03rad0r
- **Files:** docs/coordination/TRACKS-REGISTRY.yaml
- **Full message:** feat: add balloon-pre-stretching and balloon-circuit-design tracks to registry
- **Relevance:** GENERAL

### [balloon-hermes] feat: orchestrator infrastructure — track registry, status prompt, pulse script (2026-07-18) | tags: GENERAL
- **Commit:** `8cd69d0` by c03rad0r
- **Files:** docs/coordination/STATUS-REQUEST-PROMPT.md, docs/coordination/TRACKS-REGISTRY.yaml, docs/coordination/orchestrator-pulse.py
- **Full message:** feat: orchestrator infrastructure — track registry, status prompt, pulse script
- **Relevance:** GENERAL

### [balloon-hermes] docs: mark balloon-blossom assessment done (2026-07-18) | tags: PROTOCOL
- **Commit:** `b092570` by c03rad0r
- **Files:** docs/coordination/COORDINATOR-TRACKING.md
- **Full message:** docs: mark balloon-blossom assessment done
- **Relevance:** PROTOCOL

### [balloon-hermes] docs: add do-not-forward notice to assessment nudge (2026-07-18) | tags: GENERAL
- **Commit:** `1da6809` by c03rad0r
- **Files:** docs/coordination/ASSESSMENT-NUDGE.md
- **Full message:** docs: add do-not-forward notice to assessment nudge
- **Relevance:** GENERAL

### [balloon-hermes] docs: update coordinator tracking — 2 submitted, 5 nudged, 2 no Signal group (2026-07-18) | tags: GENERAL
- **Commit:** `6a691c1` by c03rad0r
- **Files:** docs/coordination/COORDINATOR-TRACKING.md
- **Full message:** docs: update coordinator tracking — 2 submitted, 5 nudged, 2 no Signal group
- **Relevance:** GENERAL

### [balloon-hermes] docs: assessment nudge message for forwarding to track groups (2026-07-18) | tags: GENERAL
- **Commit:** `070836c` by c03rad0r
- **Files:** docs/coordination/ASSESSMENT-NUDGE.md
- **Full message:** docs: assessment nudge message for forwarding to track groups
- **Relevance:** GENERAL

### [balloon-hermes] docs: add decisions/blockers sections to assessment prompt + coordinator trackin (2026-07-18) | tags: GENERAL
- **Commit:** `f39bf4e` by c03rad0r
- **Files:** docs/ASSESSMENT-PROMPT.md, docs/coordination/COORDINATOR-TRACKING.md
- **Full message:** docs: add decisions/blockers sections to assessment prompt + coordinator tracking
- **Relevance:** GENERAL

### [balloon-hermes] docs: add decisions and blockers tracking log for coordinator (2026-07-18) | tags: GENERAL
- **Commit:** `1c82b37` by c03rad0r
- **Files:** docs/coordination/DECISIONS-AND-BLOCKERS.md
- **Full message:** docs: add decisions and blockers tracking log for coordinator
- **Relevance:** GENERAL

### [balloon-hermes] docs: add integration readiness assessment prompt for all tracks (2026-07-18) | tags: GENERAL
- **Commit:** `c4fcc21` by c03rad0r
- **Files:** docs/coordination/ASSESSMENT-PROMPT.md
- **Full message:** docs: add integration readiness assessment prompt for all tracks
- **Relevance:** GENERAL

### [balloon-hermes] docs: balloon-only universal handover prompt, remove non-balloon docs (2026-07-18) | tags: GENERAL
- **Commit:** `e68e2a3` by c03rad0r
- **Files:** docs/coordination/COORDINATION-README.md, docs/coordination/MASTER.md, docs/coordination/UNIVERSAL-HANDOVER-PROMPT.md (+12 more)
- **Full message:** docs: balloon-only universal handover prompt, remove non-balloon docs
- **Relevance:** GENERAL

### [balloon-tollgate] docs: add board mutex requirement to AGENTS.md (2026-07-21) | tags: GENERAL
- **Commit:** `7dfb120` by Felix
- **Files:** AGENTS.md
- **Full message:** docs: add board mutex requirement to AGENTS.md
- **Relevance:** GENERAL

### [balloon-circuit-design] feat: extend DIY v0.1 schematic with GPS, power chain, learnings notes (2026-07-21) | tags: HARDWARE
- **Commit:** `177136c` by Felix
- **Files:** tracker/hardware/hub_board_diy/hub_board_diy.kicad_sch
- **Full message:** feat: extend DIY v0.1 schematic with GPS, power chain, learnings notes
- **Relevance:** HARDWARE

### [balloon-circuit-design] feat: rewrite SKiDL schematics with validated pin connections — both netlists ge (2026-07-21) | tags: HARDWARE
- **Commit:** `7e238ed` by Felix
- **Files:** .gitignore, tracker/hardware/hub_board/hub_schematic.erc, tracker/hardware/hub_board/hub_schematic.log (+6 more)
- **Full message:** feat: rewrite SKiDL schematics with validated pin connections — both netlists generate
- **Relevance:** HARDWARE

### [balloon-circuit-design] docs: add SPI speed discovery constraints to assessment — 20MHz SPI layout rules (2026-07-21) | tags: SPI
- **Commit:** `937f72e` by Felix
- **Files:** docs/INTEGRATION-ASSESSMENT.md
- **Full message:** docs: add SPI speed discovery constraints to assessment — 20MHz SPI layout rules
- **Relevance:** SPI


### [balloon-blossom] docs: add anti-coordination guardrails to AGENTS.md (2026-07-18) | tags: GENERAL
- **Commit:** `1c777a1` by c03rad0r
- **Files:** AGENTS.md
- **Full message:** docs: add anti-coordination guardrails to AGENTS.md
- **Relevance:** GENERAL

### [balloon-circuit-design] docs: add anti-coordination guardrails + JLCPCB circuit design mission to AGENTS (2026-07-18) | tags: HARDWARE
- **Commit:** `4ef1fee` by c03rad0r
- **Files:** AGENTS.md
- **Full message:** docs: add anti-coordination guardrails + JLCPCB circuit design mission to AGENTS.md
- **Relevance:** HARDWARE

### [balloon-circuit-design] feat: orchestrator infrastructure — track registry, status prompt, pulse script (2026-07-18) | tags: GENERAL
- **Commit:** `8cd69d0` by c03rad0r
- **Files:** docs/coordination/STATUS-REQUEST-PROMPT.md, docs/coordination/TRACKS-REGISTRY.yaml, docs/coordination/orchestrator-pulse.py
- **Full message:** feat: orchestrator infrastructure — track registry, status prompt, pulse script
- **Relevance:** GENERAL

### [balloon-circuit-design] docs: mark balloon-blossom assessment done (2026-07-18) | tags: PROTOCOL
- **Commit:** `b092570` by c03rad0r
- **Files:** docs/coordination/COORDINATOR-TRACKING.md
- **Full message:** docs: mark balloon-blossom assessment done
- **Relevance:** PROTOCOL

### [balloon-circuit-design] docs: add do-not-forward notice to assessment nudge (2026-07-18) | tags: GENERAL
- **Commit:** `1da6809` by c03rad0r
- **Files:** docs/coordination/ASSESSMENT-NUDGE.md
- **Full message:** docs: add do-not-forward notice to assessment nudge
- **Relevance:** GENERAL

### [balloon-circuit-design] docs: update coordinator tracking — 2 submitted, 5 nudged, 2 no Signal group (2026-07-18) | tags: GENERAL
- **Commit:** `6a691c1` by c03rad0r
- **Files:** docs/coordination/COORDINATOR-TRACKING.md
- **Full message:** docs: update coordinator tracking — 2 submitted, 5 nudged, 2 no Signal group
- **Relevance:** GENERAL

### [balloon-circuit-design] docs: assessment nudge message for forwarding to track groups (2026-07-18) | tags: GENERAL
- **Commit:** `070836c` by c03rad0r
- **Files:** docs/coordination/ASSESSMENT-NUDGE.md
- **Full message:** docs: assessment nudge message for forwarding to track groups
- **Relevance:** GENERAL

### [balloon-circuit-design] docs: add decisions/blockers sections to assessment prompt + coordinator trackin (2026-07-18) | tags: GENERAL
- **Commit:** `f39bf4e` by c03rad0r
- **Files:** docs/ASSESSMENT-PROMPT.md, docs/coordination/COORDINATOR-TRACKING.md
- **Full message:** docs: add decisions/blockers sections to assessment prompt + coordinator tracking
- **Relevance:** GENERAL

### [balloon-circuit-design] docs: add decisions and blockers tracking log for coordinator (2026-07-18) | tags: GENERAL
- **Commit:** `1c82b37` by c03rad0r
- **Files:** docs/coordination/DECISIONS-AND-BLOCKERS.md
- **Full message:** docs: add decisions and blockers tracking log for coordinator
- **Relevance:** GENERAL

### [balloon-circuit-design] docs: add integration readiness assessment prompt for all tracks (2026-07-18) | tags: GENERAL
- **Commit:** `c4fcc21` by c03rad0r
- **Files:** docs/coordination/ASSESSMENT-PROMPT.md
- **Full message:** docs: add integration readiness assessment prompt for all tracks
- **Relevance:** GENERAL

### [balloon-circuit-design] docs: balloon-only universal handover prompt, remove non-balloon docs (2026-07-18) | tags: GENERAL
- **Commit:** `e68e2a3` by c03rad0r
- **Files:** docs/coordination/COORDINATION-README.md, docs/coordination/MASTER.md, docs/coordination/UNIVERSAL-HANDOVER-PROMPT.md (+12 more)
- **Full message:** docs: balloon-only universal handover prompt, remove non-balloon docs
- **Relevance:** GENERAL

### [balloon-circuit-design] docs: add workstream handover documents for all 10 workstreams (2026-07-17) | tags: GENERAL
- **Commit:** `e4ee30b` by c03rad0r
- **Files:** docs/coordination/MASTER.md, docs/coordination/handover-balloon.md, docs/coordination/handover-esp32-tollgate.md (+8 more)
- **Full message:** docs: add workstream handover documents for all 10 workstreams
- **Relevance:** GENERAL

### [balloon-circuit-design] docs: unified single-paste handover prompt for all balloon Signal groups (2026-07-17) | tags: GENERAL
- **Commit:** `de15a04` by c03rad0r
- **Files:** docs/coordination/unified-handover-prompt.md
- **Full message:** docs: unified single-paste handover prompt for all balloon Signal groups
- **Relevance:** GENERAL

### [balloon-circuit-design] docs: add paste-ready handover prompts for all 5 Signal group tracks (2026-07-17) | tags: GENERAL
- **Commit:** `8eab332` by c03rad0r
- **Files:** docs/coordination/handover-prompts.md
- **Full message:** docs: add paste-ready handover prompts for all 5 Signal group tracks
- **Relevance:** GENERAL

### [balloon-fips] docs: add anti-coordination guardrails to AGENTS.md (2026-07-18) | tags: GENERAL
- **Commit:** `48c031f` by c03rad0r
- **Files:** AGENTS.md
- **Full message:** docs: add anti-coordination guardrails to AGENTS.md
- **Relevance:** GENERAL

### [balloon-nostr] docs: add anti-coordination guardrails to AGENTS.md (2026-07-18) | tags: GENERAL
- **Commit:** `cecee37` by c03rad0r
- **Files:** AGENTS.md
- **Full message:** docs: add anti-coordination guardrails to AGENTS.md
- **Relevance:** GENERAL

### [balloon-pow] docs: add anti-coordination guardrails to AGENTS.md (2026-07-18) | tags: GENERAL
- **Commit:** `4084e8e` by c03rad0r
- **Files:** AGENTS.md
- **Full message:** docs: add anti-coordination guardrails to AGENTS.md
- **Relevance:** GENERAL

### [balloon-pre-stretching] docs: add anti-coordination guardrails + pre-stretching mission to AGENTS.md (2026-07-18) | tags: GENERAL
- **Commit:** `c96f6a8` by c03rad0r
- **Files:** AGENTS.md
- **Full message:** docs: add anti-coordination guardrails + pre-stretching mission to AGENTS.md
- **Relevance:** GENERAL

### [balloon-pre-stretching] feat: orchestrator infrastructure — track registry, status prompt, pulse script (2026-07-18) | tags: GENERAL
- **Commit:** `8cd69d0` by c03rad0r
- **Files:** docs/coordination/STATUS-REQUEST-PROMPT.md, docs/coordination/TRACKS-REGISTRY.yaml, docs/coordination/orchestrator-pulse.py
- **Full message:** feat: orchestrator infrastructure — track registry, status prompt, pulse script
- **Relevance:** GENERAL

### [balloon-pre-stretching] docs: mark balloon-blossom assessment done (2026-07-18) | tags: PROTOCOL
- **Commit:** `b092570` by c03rad0r
- **Files:** docs/coordination/COORDINATOR-TRACKING.md
- **Full message:** docs: mark balloon-blossom assessment done
- **Relevance:** PROTOCOL

### [balloon-pre-stretching] docs: add do-not-forward notice to assessment nudge (2026-07-18) | tags: GENERAL
- **Commit:** `1da6809` by c03rad0r
- **Files:** docs/coordination/ASSESSMENT-NUDGE.md
- **Full message:** docs: add do-not-forward notice to assessment nudge
- **Relevance:** GENERAL

### [balloon-pre-stretching] docs: update coordinator tracking — 2 submitted, 5 nudged, 2 no Signal group (2026-07-18) | tags: GENERAL
- **Commit:** `6a691c1` by c03rad0r
- **Files:** docs/coordination/COORDINATOR-TRACKING.md
- **Full message:** docs: update coordinator tracking — 2 submitted, 5 nudged, 2 no Signal group
- **Relevance:** GENERAL

### [balloon-pre-stretching] docs: assessment nudge message for forwarding to track groups (2026-07-18) | tags: GENERAL
- **Commit:** `070836c` by c03rad0r
- **Files:** docs/coordination/ASSESSMENT-NUDGE.md
- **Full message:** docs: assessment nudge message for forwarding to track groups
- **Relevance:** GENERAL

### [balloon-pre-stretching] docs: add decisions/blockers sections to assessment prompt + coordinator trackin (2026-07-18) | tags: GENERAL
- **Commit:** `f39bf4e` by c03rad0r
- **Files:** docs/ASSESSMENT-PROMPT.md, docs/coordination/COORDINATOR-TRACKING.md
- **Full message:** docs: add decisions/blockers sections to assessment prompt + coordinator tracking
- **Relevance:** GENERAL

### [balloon-pre-stretching] docs: add decisions and blockers tracking log for coordinator (2026-07-18) | tags: GENERAL
- **Commit:** `1c82b37` by c03rad0r
- **Files:** docs/coordination/DECISIONS-AND-BLOCKERS.md
- **Full message:** docs: add decisions and blockers tracking log for coordinator
- **Relevance:** GENERAL

### [balloon-pre-stretching] docs: add integration readiness assessment prompt for all tracks (2026-07-18) | tags: GENERAL
- **Commit:** `c4fcc21` by c03rad0r
- **Files:** docs/coordination/ASSESSMENT-PROMPT.md
- **Full message:** docs: add integration readiness assessment prompt for all tracks
- **Relevance:** GENERAL

### [balloon-pre-stretching] docs: balloon-only universal handover prompt, remove non-balloon docs (2026-07-18) | tags: GENERAL
- **Commit:** `e68e2a3` by c03rad0r
- **Files:** docs/coordination/COORDINATION-README.md, docs/coordination/MASTER.md, docs/coordination/UNIVERSAL-HANDOVER-PROMPT.md (+12 more)
- **Full message:** docs: balloon-only universal handover prompt, remove non-balloon docs
- **Relevance:** GENERAL

### [balloon-pre-stretching] docs: add workstream handover documents for all 10 workstreams (2026-07-17) | tags: GENERAL
- **Commit:** `e4ee30b` by c03rad0r
- **Files:** docs/coordination/MASTER.md, docs/coordination/handover-balloon.md, docs/coordination/handover-esp32-tollgate.md (+8 more)
- **Full message:** docs: add workstream handover documents for all 10 workstreams
- **Relevance:** GENERAL

### [balloon-pre-stretching] docs: unified single-paste handover prompt for all balloon Signal groups (2026-07-17) | tags: GENERAL
- **Commit:** `de15a04` by c03rad0r
- **Files:** docs/coordination/unified-handover-prompt.md
- **Full message:** docs: unified single-paste handover prompt for all balloon Signal groups
- **Relevance:** GENERAL

### [balloon-pre-stretching] docs: add paste-ready handover prompts for all 5 Signal group tracks (2026-07-17) | tags: GENERAL
- **Commit:** `8eab332` by c03rad0r
- **Files:** docs/coordination/handover-prompts.md
- **Full message:** docs: add paste-ready handover prompts for all 5 Signal group tracks
- **Relevance:** GENERAL

### [balloon-pre-stretching] docs: add balloon project master index, coordination docs, and handover prompts (2026-07-17) | tags: PROTOCOL
- **Commit:** `1c79846` by c03rad0r
- **Files:** docs/coordination/COORDINATION-README.md, docs/coordination/INDEX.md, docs/coordination/handover-balloon-blossom.md (+5 more)
- **Full message:** docs: add balloon project master index, coordination docs, and handover prompts
- **Relevance:** PROTOCOL

### [balloon-range-tests] docs: add anti-coordination guardrails to AGENTS.md (2026-07-18) | tags: GENERAL
- **Commit:** `5cc537e` by c03rad0r
- **Files:** AGENTS.md
- **Full message:** docs: add anti-coordination guardrails to AGENTS.md
- **Relevance:** GENERAL

### [balloon-range-tests] chore(data): add range-test-results.csv template (2026-07-18) | tags: TEST
- **Commit:** `f39fdb9` by c03rad0r
- **Files:** data/range-test-results.csv
- **Full message:** chore(data): add range-test-results.csv template
- **Relevance:** TEST

### [balloon-speed-tests] docs: add anti-coordination guardrails to AGENTS.md (2026-07-18) | tags: GENERAL
- **Commit:** `ad9888e` by c03rad0r
- **Files:** AGENTS.md
- **Full message:** docs: add anti-coordination guardrails to AGENTS.md
- **Relevance:** GENERAL

### [balloon-speed-tests] feat: SINGLE-BATCH SPI BREAKTHROUGH — 1733 kbps, TX_DONE=1000/1000 (2026-07-18) | tags: SPI, RADIO, TEST
- **Commit:** `9514610` by c03rad0r
- **Files:** docs/speed-test-results-single-batch-2026-07-18.md
- **Full message:** feat: SINGLE-BATCH SPI BREAKTHROUGH — 1733 kbps, TX_DONE=1000/1000
- **Relevance:** SPI, RADIO, TEST

### [balloon-speed-tests] docs: SPI timing diagnostic results — batch 2.44x faster, SCK gap theory wrong (2026-07-18) | tags: SPI, TEST
- **Commit:** `3d42fc6` by c03rad0r
- **Files:** docs/speed-test-results-timing-diag-2026-07-18.md
- **Full message:** docs: SPI timing diagnostic results — batch 2.44x faster, SCK gap theory wrong
- **Relevance:** SPI, TEST

### [balloon-tollgate] docs: add anti-coordination guardrails to AGENTS.md (2026-07-18) | tags: GENERAL
- **Commit:** `58e65a3` by c03rad0r
- **Files:** AGENTS.md
- **Full message:** docs: add anti-coordination guardrails to AGENTS.md
- **Relevance:** GENERAL

<!-- Format: ### [TRACK] Title (DATE) | tags: tag1,tag2 -->

*(No discoveries logged yet — file initialized 2026-07-21)*
### [balloon-speed-tests → balloon-range-tests] SPEED-TESTS LEARNINGS FORWARD (2026-07-22) | tags: RADIO, SPI, TEST
- **Verified end-to-end:** 1377 kbps, 0% packet loss, 1000/1000 TX, 1018 RX
- **Single-batch SPI "1733 kbps" is SUSPECT** — spi_write_blocking produces fake TX_DONE, 0 RX
- **5 SPI alternatives tested, all failed** on real hardware (DMA, PIO, batch, registers, runtime clock change)
- **Per-packet breakdown:** RF 803us (54%), SPI 535us (36%), overhead 154us (10%)
- **Raw firmware was using SX1280 commands, NOT LR2021 commands** — running at 650 kbps not 2600
- **rp2040-flrc-max uses RadioLib LR2021 driver** — 2600 kbps target, builds OK, UNTESTED
- **RSSI negation fix applied** — was showing +36 instead of -36 dBm
- **FLRC bitrate options:** 2600/2080/1300/1040/650/520/325/260 kbps
- **Files:** firmware/rp2040-flrc-max/, docs/speed-test-results-single-batch-2026-07-18.md, docs/flrc-throughput-final-conclusion-2026-07-16.md
- **Relevance:** RADIO, SPI, TEST
