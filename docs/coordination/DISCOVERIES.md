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
