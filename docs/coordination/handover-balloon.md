# HANDOVER — Balloon/LR2021 Workstream

> **Self-contained: a fresh LLM session can bootstrap from this doc alone.**
> Last updated: 2026-07-17

---

## What This Workstream Is

ESP32-C3 + NiceRF LoRa2021 (Semtech LR2021 Gen 4) pico balloon tracker AND mesh
internet transport network. Solar/supercap powered. Target weight: <14g (Mesh V1)
or <9g (Minimal tracker). Two tracks:

1. **Tracker** (`tracker/`) — Single balloon telemetry, position reporting
2. **Mesh Stack** (`mesh-stack/`) — Multi-balloon relay network for internet transport

RF driver: **RadioLib v7.6.0** (NOT the deprecated custom driver in `components/lr2021/`).
Supports LoRa, FLRC, GFSK, OOK, LR-FHSS, O-QPSK, RTToF ranging.

**Coordinator:** balloon-hermes Signal group (top-level hub).
This workstream has dedicated sub-groups for speed and range testing.

---

## Key Paths

| Item | Path / Value |
|------|-------------|
| Primary repo | `~/repos/balloon-fresh/` |
| Worktree (this WS) | `~/worktrees/ws-balloon/` |
| Worktree branch | `ws/balloon-lr2021` (from master @ `8581ec0`) |
| Kanban board | `balloon` (`~/.hermes/kanban/boards/balloon/`) |
| Handover doc | `~/coordination/handover-balloon.md` (this file) |
| Board lock tool | `tools/balloon-board-lock.py` (hardware TX/RX mutex) |
| AGENTS.md | Root of repo — full project instructions |

### Git Remotes

| Remote | URL |
|--------|-----|
| origin | ngit (nostr) |
| fork | ngit (nostr) |
| github | `https://github.com/c03rad0r/balloon-fresh.git` |

### Sub-Track Worktrees (Existing)

| Track | Worktree | Branch |
|-------|----------|--------|
| Speed tests | `~/worktrees/balloon-speed-tests/` | `speed-optimization` |
| Range tests | `~/worktrees/balloon-range-tests/` | `range-tests` |
| Speed docs | `~/worktrees/docs-speed-record-results/` | `docs/speed-record-results` |
| Speed plan | `~/worktrees/track-speed-testing/` | `track/speed-testing` |
| Range plan | `~/worktrees/track-range-testing/` | `track/range-testing` |

Many additional feature worktrees exist (40+ total). See `git worktree list`.

---

## Board Status (as of 2026-07-17)

**Board:** `balloon` — 26 tasks total

| Status | Count |
|--------|-------|
| done | 12 |
| blocked | 12 |
| in_progress | 1 |
| archived | 1 |

### In Progress

| Task | Title |
|------|-------|
| `t_9b6720c6` | LR2021 maximum throughput validation test (p0, assignee: worker-tollgate) |

### Key Blocked Tasks

| Task | Title | Priority |
|------|-------|----------|
| `t_a27c1ba7` | Mark PR #2739 as ready for review (exit draft) — **protocol violation on last run** | p1 |
| `t_7f612ece` | Wire second LR2021 module to second ESP32-C3 SuperMini (~30 min soldering) | p2 |
| `t_64b504c5` | 2-device test: PHY exchange, reverse direction, encrypted chat, repeater mode, RSSI/SNR | p2 |
| `t_09240250` | Post PR #2739 in MeshCore Discord #general with 2-device test evidence | p2 |
| `t_9e0bae37` | StratoRelayMesh unit tests — 8 tests from cluster-aware-bridge.md | p3 |
| `t_560edf5c` | 2-node StratoRelayMesh integration test | p3 |
| `t_cddac37c` | StratoRelayMesh memory profiling — confirm 6.5 KB DRAM budget | p3 |
| `t_603efd64` | Integrate StratoRelay into RP2040 PlatformIO build | p3 |
| `t_0b8e1e6c` | ESP32-C3 firmware refactor — remove LR2021 SPI code, add UART mesh client | p3 |
| `t_fb27bdc1` | RP2040+LR2021 MeshCore variant — follow-up PR after #2739 | p4 |
| `t_e5adbc8f` | Build-verify RP2040+LR2021 MeshCore variant — all 7 targets | p4 |
| `t_e7bddec1` | Basic repeater flight — dumb MeshCore repeater on short balloon flight | p5 |

### Recently Completed

| Date | Task | Title |
|------|------|-------|
| 2026-07-13 | `t_33db8c37` | Test ESP32-C3 to RP2040 auto-BOOTSEL circuit functionality |
| 2026-07-09 | `t_325de0f8` | Balloon board JLCPCB design integration |
| 2026-07-09 | `t_98950ddf` | Madeira balloon testing project coordination |
| 2026-07-09 | `t_4a0f222f` | ESP32-C3 auto-BOOTSEL test firmware development |
| 2026-07-09 | `t_42ed6803` | Solder auto-BOOTSEL circuit on RP2040 Pico dev boards |
| 2026-07-08 | `t_7c5e5cb1` | Write StratoRelayMesh.h — subclass mesh::Mesh |
| 2026-07-08 | `t_79ae3ee7` | Define UART protocol ESP32-C3 to RP2040 |
| 2026-07-07 | `t_58581101` | Topology data collection — flash LR2021 as MeshCore repeater |
| 2026-07-07 | `t_48a0fa82` | Design & fab auto-BOOTSEL circuit board |

---

## Current Technical State

### FLRC Throughput Optimization (Active — `t_9b6720c6`)

- **Measured ceiling:** 1391 kbps (RP2040, Arduino SPI)
- **Theoretical max:** 2540 kbps (air-time limited)
- **Bottleneck:** `WRITE_FIFO` = 517 µs (35% of packet time), `TX_DONE_WAIT` = 919 µs (63%)
- **TX_DONE_WAIT is RF air time — NOT reducible.** Focus is SPI write optimization.
- **ESP32-C3 DMA SPI** test firmware built but not yet validated
- **Logic analyzer** capture scripts ready, hardware not yet probed

See: `docs/PLAN-speed-optimization.md`, `docs/HANDOVER-speed-tests.md`

### MeshCore Integration (Blocked on PR #2739)

- PR #2739 submitted to MeshCore upstream (EspIdfHal moved to `src/helpers/radiolib`)
- 4 review items resolved, waiting to exit draft mode
- StratoRelayMesh.h written and committed
- UART protocol defined (ESP32-C3 ↔ RP2040 telemetry frame format)
- Next: 2-device physical tests, StratoRelay unit/integration tests, RP2040 build integration

### Hardware

| Port | Board | Role |
|------|-------|------|
| `/dev/ttyACM0` | RP2040 Pico (S/N 8332) | TX |
| `/dev/ttyACM1` | ESP32-C3 #1 (MAC ...FB:18) | Testing |
| `/dev/ttyACM2` | ESP32-C3 #2 (MAC ...21:00) | Testing |

- **Board locks:** TX and RX both stale (held since 2026-07-16 by speed-tests track PID 4173653)
- **Lock tool:** `BALLOON_TRACK=<track> python3 tools/balloon-board-lock.py acquire|release|status`
- 4x NiceRF LoRa2021 modules, 20x ESP32-C3_Mini_V1 in inventory
- Auto-BOOTSEL circuit soldered and tested on RP2040 dev boards

---

## Build Commands

```bash
# ESP-IDF firmware (requires ESP-IDF v5.4.1)
source ~/esp/esp-idf/export.sh
cd tracker/firmware && idf.py build
idf.py -p /dev/ttyACM0 flash monitor    # ESP32-C3_Mini_V1 (USB-C)

# Hardware schematics (SKiDL + KiCad)
cd tracker/hardware && python hub_board/hub_schematic.py

# Lint
ruff check tracker/hardware/
```

---

## Key Documentation

| Doc | Purpose |
|-----|---------|
| `AGENTS.md` | Full project instructions, pin mappings, inventory |
| `IMPLEMENTATION-PLAN.md` | Master implementation plan with checklists |
| `docs/adr/` | 11 Architecture Decision Records |
| `docs/HANDOVER-speed-tests.md` | FLRC speed optimization track handover |
| `docs/HANDOVER-range-tests.md` | Range testing track handover |
| `docs/PLAN-speed-optimization.md` | 7-phase throughput optimization plan |
| `mesh-stack/ROADMAP.md` | Mesh plan, link budgets, research checklist |
| `docs/plan-variants.md` | DIY / Minimal / Mittel / Komfort / Mesh V1 / Mesh V2 |

---

## Integration Points

- **MeshCore upstream:** PR #2739 pending — blocks all StratoRelayMesh work
- **balloon-hermes coordinator:** Cross-workstream dependencies escalate here
- **Speed/range Signal groups:** Dedicated groups for each test track
- **Nostr/git:** Repo mirrored on ngit (nostr) + GitHub

---

## Coordinator Authority

This workstream reports to **balloon-hermes** (top-level coordination hub).
All work uses proper git worktrees. Unpushed work = lost work.
Commit and push to remote regularly. Integration happens at the coordinator level.

## Next Steps for a Fresh Session

1. `cd ~/worktrees/ws-balloon/` and read `AGENTS.md`
2. Check board: `python3 -c "import sqlite3; ..."` or use Hermes kanban CLI
3. Check board locks: `python3 tools/balloon-board-lock.py status`
4. Review `t_9b6720c6` (in_progress) — throughput validation
5. Review blocked tasks — many are blocked on PR #2739 or hardware soldering
6. Read `docs/HANDOVER-speed-tests.md` for FLRC optimization context
