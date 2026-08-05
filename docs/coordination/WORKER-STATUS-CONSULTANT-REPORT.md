# Worker Status + Findings Report — For Consultant Review

**Date:** 2026-08-05 13:03
**Author:** Orchestrator (balloon-hermes)

## Active Kanban Tasks (6 running)

| Task | Worker | Status | Findings |
|------|--------|--------|----------|
| P2-retry PCB fix | worker-balloon | dispatched | KiCad files found, kicad-cli available |
| P3 FIPS build fix | worker-fips | running | 3 Rust bugs being fixed |
| P5 relay_send_nostr | worker-balloon | running | Auto-created by P4 audit |
| P5 nostr_dump | worker-balloon | running | Auto-created by P4 audit |
| P6 tollgate_send_pay | worker-balloon | running | Auto-created by P4 audit, needs tollgate_payment_proto.h |

## P4 CLI Audit — COMPLETED (key findings)

### What exists
- radio_test: main/app_main.cpp:315 — sends raw telemetry packet via s_radio->send_packet()
- radio_recv: main/app_main.cpp:335 — 30s RX listener, prints hex + RSSI/SNR

### What's missing (workers implementing now)
1. relay_send_nostr (2-4h, medium) — serialize Nostr event → g_tx_queue. Dependencies met.
2. nostr_dump (1-2h, low) — needs nostr_store_t refactored from app_task local to shared scope.
3. tollgate_send_pay (4-8h, HIGH) — tollgate_payment_proto.h DOESN'T EXIST. app_task.cpp includes it but it was never created. CONFIG_ENABLE_TOLLGATE not set in sdkconfig.

### Critical finding: tollgate_payment_proto.h missing
app_task.cpp:33 includes "tollgate_payment_proto.h" under #ifdef CONFIG_ENABLE_TOLLGATE. This file doesn't exist anywhere in the firmware tree. The host-side relay test (12/12 pass) uses a MOCK protocol. The real protocol needs to be created from the mock's API shape, or ported from mesh-stack/tollgate/.

### Infrastructure discovered
- CLI framework: components/cli/ (custom, not esp_console)
- Relay queues: g_rx_queue (8 slots), g_tx_queue (4 slots)
- Type tags: RELAY_TYPE_NOSTR_EVENT=0x01, TOLLGATE_PAY=0x02, TOLLGATE_ACK=0x03
- radio_test uses direct radio API, NOT relay queue — raw ping works without relay mode

## P2 PCB — First attempt crashed, re-dispatched

### What was found
- KiCad project: ~/repos/balloon-fresh/tracker/hardware/hub_board_v1.kicad_pcb
- kicad-cli installed at /usr/bin/kicad-cli
- Existing gerbers in gerbers_v1/ (pre-fix)
- .kicad_pcb is S-expression text format (can be edited with sed/patch)

### What needs to change
- LED net: GPIO10 → GPIO18
- FEM_TX net: GPIO1 → GPIO19
- Regenerate gerbers + run DRC

## P3 FIPS — In progress

Worker-fips fixing 3 Rust bugs:
1. portable-atomic for RISC-V atomics
2. esp32c3 cfg variants in config.rs
3. esp-println logger for no_std

## Questions for Consultant

1. tollgate_payment_proto.h doesn't exist — should we port from mesh-stack/tollgate/ or write from the mock API shape in the test file? Which is source of truth?

2. nostr_store_t is a local variable in app_task() — needs refactoring to shared scope for nostr_dump CLI. Should it move to app_main.cpp global, or stay in app_task with an accessor function?

3. radio_test uses direct radio API (send_packet), not the relay queue. Should Phase 2 (raw ping) use existing radio_test/radio_recv, or should we add relay-queue-based versions?

4. 3 follow-up CLI tasks auto-created by the worker — should they all run in parallel, or should tollgate_send_pay wait for tollgate_payment_proto.h to be created first?

5. P2 PCB worker crashed on first attempt — is editing .kicad_pcb as text safe, or should Felix make GUI changes manually?