# FIRMWARE OUTPUT HARMONIZATION — Requirements for Future Sessions

**Date:** 2026-08-19
**From:** Data engineering contributor
**To:** Felix + agent(s)
**Purpose:** Define changes to firmware output across all three rigs so that future experimental data is captured in a unified, machine-parseable format, radically reducing the need for per-rig reconciliation, inference, and manual provenance reconstruction.

---

## CONTEXT: Why this matters

The three data-producing rigs (E80/STM32, ESP32-C3, RP2040) currently produce data in **three completely different formats**, with different field sets, different granularity, different field names, different units, and different levels of per-packet detail. The historical cost of this is visible in the existing data:

- **Firmware attribution is broken.** The July 24 walk test -- the flagship outdoor dataset -- cannot be attributed to a specific firmware build. Multiple agents flashed boards independently, nobody recorded which build was running, and the postmortem explicitly says "we don't know which build was on TX/RX during the walk." Every packet of data from that session is permanently questionable as a result.
- **Schema drift is silent.** The old C3 bench firmware recorded `avg_snr`, `out_of_order`, `seq_gaps`, and `bit_errors` in 32 columns. The current C3 range firmware dropped all of those -- no SNR at all, no seq-gap tracking. Nobody noticed until an audit weeks later. There is no schema version field, no "breaking change" flag, just silent regression.
- **Per-packet data is rig-dependent.** The C3 and V4 rigs log one line per received packet (the richest, most useful grain). The E80 and planned RP2040 rigs log only per-cell aggregates. This means cross-rig comparison requires either downgrading the rich rigs or accepting that two rigs can never be compared at the same granularity.
- **Packet identity is ambiguous.** Sequence numbers reset to 0 per window/phase. The same `seq=5` appears in loop 1 and loop 2 of the same window. Distinguishing them requires parsing the loop counter separately and constructing a composite key -- something the data consumer shouldn't have to do.
- **Configuration is not in the data.** Radio parameters (modulation, frequency, SF, BW, CR, power, packet size) are encoded in firmware header files or host-tool arguments, not in the per-packet output. A single PKT line doesn't tell you what configuration it was received under -- you have to join against a separate config table or infer from context.

The data system we're building can work around all of these, but each workaround adds complexity, fragility, and a permanent maintenance burden. Fixing them at the source -- in firmware output -- makes the data system roughly half as complex to build and maintain, and makes the data itself trustworthy by construction rather than trustworthy by reconstruction.

**The guiding principle:** every line of data the firmware emits should be **self-describing** -- a consumer should be able to understand what it means, what configuration produced it, what firmware generated it, and how to identify it, without referring to any external document, header file, or tribal knowledge.

---

## MUST-HAVE: Changes that block trustworthy data ingest

### M1: Firmware git hash in a machine-parseable boot banner (ALL RIGS)

**Requirement:**
- Every rig prints a **boot banner line** that includes the full firmware git hash (7-char short hash minimum) in a fixed, parseable format: `FW_HASH=<7+hexchars>`
- This line must appear once at boot, before any data output, and be capturable by the host logging tool
- The host capture tool must parse this line and **refuse to start a session** if it cannot resolve a firmware hash for both TX and RX (see M2 below)
- The hash must be injected at build time, not hand-edited (the repo already has `tools/inject_git_version.py` -- use it or equivalent)

### M2: Capture tool firmware-hash gate (HOST-SIDE, ALL RIGS)

**Requirement:**
- The capture tool must, at session start:
  1. Query the board for its firmware hash (parse the boot banner or send `ID?`)
  2. Write a structured session header to the capture file: `# SESSION_START <iso8601> tx_fw=<hash> rx_fw=<hash> operator=<name> rig=<A|B|C>`
  3. **Refuse to proceed** if either hash is missing, empty, or shows `unknown`/`none`

### M3: Per-packet output on ALL rigs (E80 + RP2040 -- C3 already does this)

**Requirement:**
- E80 and RP2040 firmware must emit one line per received packet, containing at minimum: sequence number, RSSI, and a timestamp (see M4 for timestamp format)
- This does not require changing the radio receive path -- the firmware already processes each packet (for CRC check, seq extraction, stats accumulation). It only needs to **printf** the per-packet data it already has, before aggregating

### M4: Common per-packet line format (ALL RIGS)

**Requirement:**
All rigs emit per-packet lines in this common format:

```
PKT,<session_id>,<config_id>,<replicate>,<seq>,<ts_ms>,<rssi_dbm>,<snr_db>,<crc_ok>,<bit_err>,<bytes_bad>,<freq_hz>,<mod>,<sf>,<bw_khz>,<cr>,<power_dbm>,<pkt_size>,<gps_fix>,<gps_lat>,<gps_lon>,<gps_alt>,<gps_sats>,<gps_hdop>
```

### M5: Configuration identifier in every data line (ALL RIGS)

**Requirement:**
- Every PKT line and every summary line includes the full set of independent variables: `freq_hz, mod, sf, bw_khz, cr, power_dbm, pkt_size`
- Additionally, a short `config_id` (name or index) is included for human readability and for joining against a configuration registry

### M6: Non-resetting sequence numbers (ALL RIGS)

**Requirement:**
- The TX sequence counter is `uint32_t`, starts at 0 at firmware boot (or session start), and **never resets** for the lifetime of the session
- The counter wraps at 2^32 (4 billion)
- The RX logs this counter as-is from the packet payload

### M7: Log CRC-failed packets, not just count them (ALL RIGS)

**Requirement:**
- When a packet arrives but fails CRC, emit a PKT line with `crc_ok=0`, the seq (if extractable), the RSSI, and the timestamp
- Separates "packet never arrived" (no PKT line) from "packet arrived but was corrupted" (PKT line with `crc_ok=0`)

---

## NICE-TO-HAVE: Changes that significantly improve data quality

### N1: Per-packet SNR for LoRa on all rigs
### N2: Both LoRa RSSI fields from GetLoraPacketStatus
### N3: Gap/duty-cycle column in summary output (ALL RIGS)
### N4: Voltage and temperature recording (WHERE FEASIBLE)
### N5: Attenuator-dB column for cage/calibration sessions

---

## OPTIONAL: Changes that add capability but are not blocking

### O1: Unified configuration table emitted at session start
### O2: TX-side per-packet log (for debugging and bidirectional analysis)
### O3: RSSI calibration table emission
### O4: Explicit phase/config transition markers

---

## IMPLEMENTATION PRIORITY AND SEQUENCING

**Phase 1 (before next session with boards):** M1, M2, M3, M4, M5, M6, M7
**Phase 2 (as soon as feasible):** N1, N2, N3
**Phase 3 (when hardware allows):** N4, N5
**Phase 4 (nice to have):** O1-O4

---

*This document can be committed to the repo as `docs/data-handover/FIRMWARE-HARMONIZATION-2026-08-19.md`. The MUST-HAVE items (M1-M7) are the priority for the next firmware session.*