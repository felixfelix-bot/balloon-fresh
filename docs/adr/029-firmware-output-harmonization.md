# ADR-029: Firmware Output Harmonization

**Date:** 2026-08-19
**Status:** APPROVED
**Decision Maker:** Felix
**Supersedes:** T1/T2/T3 and N2/N3 from decode-gaps-plan-2026-08-17.md

## Context

The three data-producing rigs (E80/STM32, ESP32-C3, RP2040) currently emit data in three completely different formats with different field sets, granularity, field names, and units. This has caused:

- **Unrecoverable firmware attribution** (Jul 24 walk test — flagship outdoor dataset has no known firmware version)
- **Silent schema drift** (C3 bench firmware recorded SNR/seq-gaps/bit-errors; current C3 range firmware dropped all of them, nobody noticed)
- **Per-packet data rig-dependent** (C3/V4 have per-packet; E80/RP2040 only have per-cell aggregates)
- **Ambiguous packet identity** (seq resets per window/phase, same seq=5 in loop 1 and loop 2)
- **Configuration not in data** (radio params in firmware headers or CLI args, not in per-packet output)

Two handover documents from the data engineering contributor define the problem space:
1. `DATA-INVENTORY-2026-08-19.md` — classifies existing historical data for v0 ingest
2. `FIRMWARE-HARMONIZATION-2026-08-19.md` — defines firmware changes to prevent future data gaps

## Decision

### 1. Approve all 7 MUST-HAVE items (M1-M7)

| ID | Requirement | Applies To |
|----|-------------|------------|
| M1 | Firmware git hash in machine-parseable boot banner (`FW_HASH=<7+hexchars>`) | ALL RIGS |
| M2 | Capture tool refuses to start session if firmware hash unresolved for TX or RX | ALL RIGS (host-side) |
| M3 | Per-packet output (one line per received packet with seq, RSSI, timestamp) | E80 + RP2040 (C3 already does this) |
| M4 | Common 23-field per-packet line format across all rigs | ALL RIGS |
| M5 | Full radio config in every data line (freq, mod, sf, bw, cr, power, pkt_size + config_id) | ALL RIGS |
| M6 | Non-resetting uint32_t sequence counter (starts at boot, never resets) | ALL RIGS |
| M7 | Log CRC-failed packets individually (crc_ok=0, with RSSI + seq if extractable) | ALL RIGS |

### 2. E80 UART baud rate bump

Bump E80 STM32 UART from 115200 to **2000000 (2 Mbps)**. 

**Rationale:** FLRC bursts up to 190 pkt/s. With M3+M4+M5, each PKT line is ~120-150 bytes → ~23-28 KB/s. At 115200 baud, max throughput is ~11.5 KB/s — insufficient. At 2 Mbps, max throughput is ~200 KB/s — ample headroom. CH340 supports up to 2 Mbps; STM32F103 UART1 supports up to 4.5 Mbps. Both hardware components support this rate.

**Also:** Enlarge `tx_buf[96]` to `tx_buf[160]` in `console.c` to accommodate the 23-field PKT line format (~102 chars worst case).

### 3. session_id injection — capture tool is the source

- **Capture tool** generates `session_id` at session start (UUID or timestamp-based)
- Capture tool passes `session_id` to firmware via a session-start command
- Firmware includes `session_id` in every PKT line
- If firmware doesn't receive a session_id, it prints empty field
- This is mandated for all hardware rigs: E80 (STM32), RP2040, ESP32-C3

### 4. v0 canonical schema — BOTH per-packet and per-cell

- **Per-packet (23-field):** Primary analytical grain. One row per received packet. This is where cross-rig comparison happens.
- **Per-cell (19-col + nullable extensions):** Derived summary. One row per configuration per replicate. Contains on-board Wilson CI, aggregate stats.
- Ingest pipeline stores both. Per-packet is primary; per-cell is derived view.
- The M4 common format supersedes the 19-col canonical as the ingest target for future data. Historical data ingests with the 19-col format and is converted.

### 5. Reconcile with decode-gaps plan (Aug 17)

The harmonization document replaces these overlapping tasks:
- **T1** (E80 fw version banner) → subsumed by M1
- **T2** (capture tool version recording) → subsumed by M2
- **T3** (C3 fw version banner) → subsumed by M1
- **N2** (C3 per-packet SNR/observability) → subsumed by M4 + N1 (harmonization)
- **N3** (schema unification + C3→canonical converter) → superseded by M4; converter target changes from 19-col to 23-field

No duplicate work. The decode-gaps tasks that remain relevant (those not overlapping with harmonization) continue as scheduled.

### 6. Phasing approved

| Phase | Items | Trigger | Dependency |
|-------|-------|---------|------------|
| Phase 1 | M1, M2, M3, M4, M5, M6, M7 + O4 (config transition markers) | Before next board session | E80 baud bump is critical gate for M3/M4/M5 |
| Phase 2 | N1, N2, N3 | After Phase 1 complete | M4 format must be in place (these are additional fields in same line) |
| Phase 3 | N4, N5 | When hardware allows | RP2040 ADC wiring (N4); cage hardware (N5) |
| Phase 4 | O1, O2, O3 | Opportunistic | Not blocking |

**O4 (config transition markers) pulled into Phase 1** — one printf per config switch, high robustness value, very low cost.

### 7. Commit and push documentation

Both handover documents and this ADR committed to the repo at:
- `docs/data-handover/DATA-INVENTORY-2026-08-19.md`
- `docs/data-handover/FIRMWARE-HARMONIZATION-2026-08-19.md`
- `docs/adr/029-firmware-output-harmonization.md`

## Consequences

- **Breaking change for C3 tooling:** Existing `rx_capture.py` and analysis tools must be updated to handle the new 23-field format. Must be done in the same session as the firmware change.
- **E80 baud rate change:** Host-side capture tools must also be updated to open the serial port at 2 Mbps instead of 115200. CH340 driver auto-detects baud.
- **M6 payload format change:** TX and RX firmware on each rig must be coordinated — the payload seq field changes from uint16 to uint32. Not a one-sided edit.
- **~20 hours of firmware engineering** total, fully parallelizable across 3 rigs.
- **RP2040 (Rig C) gets harmonized format built in from start** — cheapest path since firmware isn't written yet.

## Open Questions Requiring Felix (not blocking Phase 1)

- **Q4:** Hardware unit inventory — how many LR2021 modules exist, are they identifiable? For v0, ingest with hw_id=null. Future sessions need labeling convention.
- **Q6:** Data on lab PC not in repo — file listing needed. Not blocking for v0 ingest.