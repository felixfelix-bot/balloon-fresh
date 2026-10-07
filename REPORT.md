# REPORT — ADR-037

## Commit + remotes (observed)
- Commit: `7c052ddf06fafe9a93486e8a5ac6c491392630a8`
- github: `7c052ddf06fafe9a93486e8a5ac6c491392630a8`
- ngit:   `7c052ddf06fafe9a93486e8a5ac6c491392630a8`

## Deliverable
- **ADR-037** at `docs/adr/037-mcu-s3-no-fem.md` — records operator's 2026-10-07 decisions:
  1. v9 MCU = ESP32-S3-WROOM-1U-N8R8 (confirms ADR-029 D1; ADR-001 scoped to bench board).
  2. SKY66112 FEM omitted from v9.

## Link-budget evidence (the number)
- Tool: `tools/link_budget.py`, v9 2.4 GHz receive path @ 300 km slant, ground-station EIRP 37 dBm.
- Observed: EIRP 37.0 dBm, FSPL 149.6 dB, RX power -102.6 dBm.
- Margin **with LNA** (F33 internal, -136 dBm, ADR-029): **+33.4 dB**.
- Margin **without LNA** (-124 dBm, DIO5 bypass, ADR-029): **+21.4 dB**.
- Verdict: adequate without the external FEM → operator's conditional resolves to "not needed".

## Files touched
- `docs/adr/037-mcu-s3-no-fem.md` (new)
- `docs/adr/001-esp32-c3-as-mcu.md` (scope-split pointer)
- `docs/adr/005-sky66112-fem.md` (superseded-in-part pointer)
- `docs/adr/006-supercapacitor-power.md` (stale-load-list pointer)
- `PROGRESS.md`, `REPORT.md` (this worktree root)

## Evidence correction (brief's grep was stale)
- Brief cited `tracker/hardware/output/v8i_krt_gnss.kicad_pcb` (does not exist).
- Board of record (ADR-029) is `v8h_krt_u2_lora2021.kicad_pcb`: SKY66112 count = **0** (verified).
- `tracker/hardware/schematics/v_c3_flight.kicad_sch`: SKY66112 = **2** occurrences, both `SKY66112 (opt)`.
- 19 docs under `docs/` mention SKY66112 (6 in `docs/adr/`).

## Unverified / open items
- F33 module's own receiver noise figure not stated in committed docs → not asserted (cited sensitivity only).
- S3 on-die Wi-Fi/BT as config/telemetry → whether a separate 2.4 GHz RX is still needed (open, undecided).
- ADR-026 dual-MCU unchanged (single S3).
- ADR-006 power-chain re-draw left as follow-up.
