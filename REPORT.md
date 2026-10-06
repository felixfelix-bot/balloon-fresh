# Task report — ADR impact audit for ADR-034/035, 2026-10-07

## What was done

Audited the two new Architecture Decision Records (`ADR-034` band split,
`ADR-035` TDM schedule) on branch `adr/radioband-tdm` for collisions with
standing decisions. Added a `## Relationship to standing decisions` section
to each record, then committed and pushed to `github` and `ngit`.

The existing one-line supersede pointer in `ADR-029`
(`docs/adr/029-dual-band-flight-board.md`) was already present from the prior
commit and correctly records that ADR-034/035 supersede parts of ADR-029.

## Modified files

- `docs/adr/034-radio-band-split-433-tx-2g4-rx.md` — added relationship section.
- `docs/adr/035-tdm-radio-schedule.md` — added relationship section.
- `PROGRESS.md` — updated with audit step.
- `REPORT.md` — this file.

## ADR status table

| ADR | Path | Status (quoted) | Affected by ADR-034/035? | Action taken |
|---|---|---|---|---|
| ADR-001 | `docs/adr/001-esp32-c3-as-mcu.md` | "Akzeptiert" | Yes — C3 vs S3 conflict for v9 already resolved by ADR-029; ADR-001 remains in force for non-v9 | Stated as open fork, not silently resolved |
| ADR-002 (LR2021) | `docs/adr/002-lr2021-as-rf-chip.md` | "Akzeptiert" | No — both radios remain LR2021 family | Listed as unaffected |
| ADR-005 | `docs/adr/005-sky66112-fem.md` | "Akzeptiert" | Yes — unamplified 2.4 GHz RX in v9 supersedes SKY66112 for v9 | Stated as superseded in part for v9 |
| ADR-006 | `docs/adr/006-supercapacitor-power.md` | "Akzeptiert" | Yes — 3.3 V rail / single LR2021 / SKY66112 conflicts with 5 V F33 + dual LR2021 | Open conflict left unresolved |
| ADR-017 (ban) | `docs/adr/017-lr2021-only-ban-sx1280.md` | "SUPERSEDED by ADR-020" | Yes — ADR-035 uses SX1280; no live ban exists | ADR-035 states this explicitly |
| ADR-020 | `docs/adr/020-deprecate-radiolib-adopt-raw-lr2021-spi.md` | "Accepted (2026-07-23)" | No — raw 2-byte protocol still applies | Listed as unaffected |
| ADR-029 | `docs/adr/029-dual-band-flight-board.md` | "Proposed" | Yes — D2 single-module collapse and §3 slot table superseded | Supersede pointer already present in file header; relationship section in ADR-034/035 references it |
| ADR-026 | `docs/adr/026-dual-mcu-radio-architecture.md` | "ACCEPTED" | Yes — v9 assumes single S3 host; dual-MCU not adopted for v9 | Stated as open architectural fork |
| ADR-022 | `docs/adr/022-mandatory-test-coverage.md` | "Accepted" | No — coverage gate still applies | Listed as unaffected |
| ADR-024 | `docs/adr/024-extract-only-source-repository-policy.md` | "ACCEPTED" | No — source-only policy still applies | Listed as unaffected |
| ADR-030/031/032 | `docs/adr/030-deterministic-zero-inference-pcb-pipeline.md`, `031-...`, `032-...` | "Proposed" / "Accepted" / "Accepted" | No — downstream methods remain in force | Listed as unaffected |

## Open conflicts / unresolved items

- **ADR-006 power architecture**: 3.3 V rail, single LR2021, SKY66112 FEM vs.
  ADR-034's 5 V / dual LR2021 / no SKY66112. Requires a new power ADR or
  explicit ADR-006 amendment.
- **ADR-026 dual-MCU architecture**: not adopted for v9, not formally
  superseded. Operator must decide whether v9 stays single-S3 or re-adopts
  RP2040 radio processor.
- **433 MHz TX power legality in DE**: unresolved in both ADR-034 and
  ADR-035.
- **ADR-006 storage element / ADR-035 energy-opportunistic TX**: whether a
  supercap is kept is an operator question left open.

## Branch and commit

- Local branch: `adr/radioband-tdm`
- New commit SHA: `<to be observed after commit>`
- Remote `github`: `<to be observed after push>`
- Remote `ngit`: `<to be observed after push>`

## What was NOT done

No decision substance was re-decided. All conflicts are stated as open items,
not silently resolved. No schematic, placement, routing, or firmware code was
changed.

## Blockers

None encountered.
