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

These are changes without which the data system cannot guarantee provenance, cannot compare rigs, or cannot attribute results. If any of these are missing from a future session, that session's data enters the system with the same class of gaps that plague the historical data.

### M1: Firmware git hash in a machine-parseable boot banner (ALL RIGS)

**Current state:**
- E80: `ID?` replies `ID E80BENCH v1.2 role=...` -- version string only, no git hash. The T1 task plans to add this.
- C3: boot banner prints `=== LR2021 Range Test v1.0 ===` -- no git hash. The T3 task plans to add a version banner with trailing fw_id.
- RP2040 (planned): `ID?` will reply `ID range-host v1 fw=<hash>` -- this is the best of the three, but still only in the ID? response, not in per-packet output.

**Requirement:**
- Every rig prints a **boot banner line** that includes the full firmware git hash (7-char short hash minimum) in a fixed, parseable format: `FW_HASH=<7+hexchars>`
- This line must appear once at boot, before any data output, and be capturable by the host logging tool
- The host capture tool must parse this line and **refuse to start a session** if it cannot resolve a firmware hash for both TX and RX (see M2 below)
- The hash must be injected at build time, not hand-edited (the repo already has `tools/inject_git_version.py` -- use it or equivalent)

**Motivation:** The walk-test postmortem is the case study. Firmware attribution was unrecoverable because no hash was recorded. The fix is not "remember to write it down" -- it is "the firmware emits it, the capture tool enforces it, and a session literally cannot start without it." This is the single highest-value change.

### M2: Capture tool firmware-hash gate (HOST-SIDE, ALL RIGS)

**Current state:** No capture tool checks or enforces firmware identity. The C3 `rx_capture.py` simply logs whatever the board prints. The E80 `e80_bench_ctl.py` records the `ID?` response in a `#` comment but does not validate it.

**Requirement:**
- The capture tool (whether `rx_capture.py`, `e80_bench_ctl.py`, or the future RP2040 host tool) must, at session start:
  1. Query the board for its firmware hash (parse the boot banner or send `ID?`)
  2. Write a structured session header to the capture file: `# SESSION_START <iso8601> tx_fw=<hash> rx_fw=<hash> operator=<name> rig=<A|B|C>`
  3. **Refuse to proceed** if either hash is missing, empty, or shows `unknown`/`none`
- This gate is the mechanical enforcement layer for M1. Without it, the hash in the boot banner is just "recorded for later" -- which is exactly what failed on July 24.

**Motivation:** This is the "refuse to start a run if provenance can't be established" pattern. It turns a recurring data-quality failure into a build-time error. The operator gets a clear message ("cannot resolve firmware hash on RX -- flash a tagged build and retry") instead of a silent gap that only surfaces in postmortem.

### M3: Per-packet output on ALL rigs (E80 + RP2040 -- C3 already does this)

**Current state:**
- C3: emits one `PKT,...` line per received packet (20 fields). Good.
- V4: emits one `PKT rx=... seq=... rssi=...` line per received packet (11 fields). Good (decommissioned).
- E80: emits **zero per-packet output**. The host only polls `STAT?` after the burst completes and gets one aggregate row per cell. The firmware tracks `rx_first_seq`/`rx_last_seq` internally but never exposes per-packet data.
- RP2040 (planned): same as E80 -- per-cell aggregates only, no per-packet output.

**Requirement:**
- E80 and RP2040 firmware must emit one line per received packet, containing at minimum: sequence number, RSSI, and a timestamp (see M4 for timestamp format)
- This does not require changing the radio receive path -- the firmware already processes each packet (for CRC check, seq extraction, stats accumulation). It only needs to **printf** the per-packet data it already has, before aggregating
- The per-cell aggregate (`STAT?` on E80, equivalent on RP2040) should still be emitted -- it provides the on-board Wilson CI computation that per-packet data alone cannot replicate without the full statistical library

**Motivation:** Per-packet data is the experiment's actual product. Without it, you can never retroactively re-compute PER under a different definition, never see RSSI distribution within a cell, never do fade/timing analysis, never separate CRC-failures from missing packets after the fact. The C3 and V4 rigs have this; the E80 and RP2040 rigs don't, and it's the single biggest structural asymmetry across rigs. The user (data contributor) has confirmed this is within scope to change.

### M4: Common per-packet line format (ALL RIGS)

**Current state:**
- C3: `PKT,<loop>,<winId>,<name>,<mode>,<freq>,<bitrate>,<sf>,<bw>,<cr>,<power>,<pkt_size>,<seq>,<rssi>,<gps_fix>,<gps_lat>,<gps_lon>,<gps_alt>,<gps_sats>,<gps_hdop>`
- V4: `PKT rx=<n> seq=<n> rssi=<n> phase=<n> rx_ms=<n> tx_lat=<f> tx_lon=<f> sats=<n> fix=<n> utc=<n> tx_fw=<s>`
- E80: (no per-packet output)
- RP2040 (planned): (no per-packet output)

These differ in: field delimiter (comma vs space vs key=value), field order, field names, endianness of seq (C3 = big-endian, E80 = little-endian), timestamp source (C3 = none, V4 = device ms, E80 = none), GPS source (C3 = local GPS, V4 = TX-embedded GPS), and which radio parameters are included.

**Requirement:**
All rigs emit per-packet lines in this common format:

```
PKT,<session_id>,<config_id>,<replicate>,<seq>,<ts_ms>,<rssi_dbm>,<snr_db>,<crc_ok>,<bit_err>,<bytes_bad>,<freq_hz>,<mod>,<sf>,<bw_khz>,<cr>,<power_dbm>,<pkt_size>,<gps_fix>,<gps_lat>,<gps_lon>,<gps_alt>,<gps_sats>,<gps_hdop>
```

Field definitions:
- `session_id` -- unique session identifier (assigned by capture tool at session start, written into the SESSION_START header; firmware echoes it if the host passes it, or the capture tool injects it at ingest time)
- `config_id` -- identifier for the configuration being tested (see M5); can be an index or a short name like `F2600-868`
- `replicate` -- pass/replicate number within this session (incremented per loop through the config table)
- `seq` -- sequence number within this replicate (starts at 0, monotonically increasing, uint32, **does not reset across replicates** -- see M6)
- `ts_ms` -- device timestamp in milliseconds (from `esp_timer` / `uptime_ms` / equivalent). Must be monotonic within a session. For rigs without a realtime clock, device uptime is fine -- the capture tool provides wall-clock correlation.
- `rssi_dbm` -- RSSI in dBm (integer; the raw chip value, uncalibrated). For LoRa, use `rssi_pkt` from `GetLoraPacketStatus`. For FLRC, use `rssi_avg` from `GetFlrcPacketStatus`.
- `snr_db` -- SNR in dB (LoRa only; FLRC has no SNR. Print 0 or empty for FLRC -- but DO print it, so the column always exists)
- `crc_ok` -- 1 if CRC passed, 0 if CRC failed (and the packet was still logged -- see M7)
- `bit_err` -- number of bit errors from PRBS verify (if the rig does PRBS; empty/0 if not)
- `bytes_bad` -- number of bytes that didn't match expected pattern (if the rig does payload verify; empty/0 if not)
- `freq_hz` -- actual TX frequency in Hz (e.g. 868000000)
- `mod` -- modulation: `LORA` or `FLRC`
- `sf` -- spreading factor (LoRa only; 0 for FLRC)
- `bw_khz` -- bandwidth in kHz (e.g. 125, 500, 0 for FLRC)
- `cr` -- coding rate. For LoRa: denominator form (5 = 4/5, 7 = 4/7). For FLRC: raw register code (0 = 1/2, 1 = 3/4, 2 = uncoded). Document which form in a comment, not in the data line.
- `power_dbm` -- configured TX power in dBm
- `pkt_size` -- payload size in bytes
- `gps_fix`, `gps_lat`, `gps_lon`, `gps_alt`, `gps_sats`, `gps_hdop` -- GPS fields (empty/0 if no GPS on this rig)

**Motivation:** A single parser handles all three rigs. No per-rig field mapping, no endianness confusion, no "which field is rssi in this format" lookup. The capture tool writes exactly what the firmware emits, and the ingest pipeline reads exactly one format. This is the change that eliminates the entire class of per-rig converter complexity.

### M5: Configuration identifier in every data line (ALL RIGS)

**Current state:**
- C3: the `loop` and `winId`/`name` fields in the PKT line identify the configuration, but the actual radio parameters (freq, SF, BW, CR, power) are only in the RESULT line, not the PKT line
- V4: the `phase` field maps to a configuration via a lookup table that lives in firmware source code, not in the data
- E80: configuration is set by host-tool CLI arguments, not in the per-cell CSV row (the `mod` column is there, but freq/power/CR are in `#` comment metadata, not in the row)

**Requirement:**
- Every PKT line and every summary line includes the full set of independent variables: `freq_hz, mod, sf, bw_khz, cr, power_dbm, pkt_size`
- Additionally, a short `config_id` (name or index) is included for human readability and for joining against a configuration registry
- This means a single PKT line is **self-describing**: you know exactly what configuration produced it without joining against anything external

**Motivation:** Today, to know that a packet with `seq=42` was received under FLRC-2600 at 868 MHz, +22 dBm, CR=1/2, you have to: parse the RESULT line for the same window to get the radio params, OR look up the window name in the firmware header, OR parse the host-tool CLI arguments. Every one of these is a fragile join that breaks when firmware changes. Putting the config in every line makes each row independently interpretable.

### M6: Non-resetting sequence numbers (ALL RIGS)

**Current state:**
- C3: `seq` is a `uint16_t` that resets to 0 at the start of each window. Packet `seq=5` in loop 1 is indistinguishable from `seq=5` in loop 2.
- V4: `seqInPhase` is a `uint16_t` that resets to 0 at the start of each phase.
- E80: `tx_seq` is a `uint32_t` that resets to 0 on each `START` command.

**Requirement:**
- The TX sequence counter is `uint32_t`, starts at 0 at firmware boot (or session start), and **never resets** for the lifetime of the session
- The counter wraps at 2^32 (4 billion) -- sufficient for any conceivable session length
- The RX logs this counter as-is from the packet payload
- The `(config_id, replicate, seq)` triple is still emitted for human readability, but `seq` is globally unique within the session by construction

**Motivation:** Packet identity must be unambiguous. Today, distinguishing packets across replicates requires constructing a composite key from multiple fields -- and if any of those fields is missing or wrong (as happened in the walk test), identity is lost. A monotonically increasing counter makes each packet globally unique within the session, period. This is a one-line firmware change (`uint16_t p = 0` -> `static uint32_t globalSeq = 0` in the TX loop) with disproportionate data-integrity value.

### M7: Log CRC-failed packets, not just count them (ALL RIGS)

**Current state:**
- C3: `rxCrcErrors` is incremented when `readData != ERR_NONE`, but no per-packet record is emitted for the failed packet. The packet is invisible -- you know *how many* failed but not *when* or *which seq neighborhood*.
- E80: `rx_crc_err` is counted in stats and reported in `STAT?`, but no per-packet record.
- V4: `crc_err` is counted per-phase in `PHASE_RESULT`, but individual CRC failures are not logged per-packet.

**Requirement:**
- When a packet arrives but fails CRC, emit a PKT line with `crc_ok=0`, the seq (if extractable from the partially-received payload), the RSSI (the chip still measures signal strength even on a failed CRC), and the timestamp
- This makes CRC-failed packets visible as individual events, not just a count
- Separates "packet never arrived" (no PKT line at all) from "packet arrived but was corrupted" (PKT line with `crc_ok=0`) -- two different failure modes that are currently conflated

**Motivation:** The walk-test postmortem (F3) showed that CRC false positives can mask corruption -- `crc_err=0` on all packets, but payloads were garbage. If CRC-failed packets were logged individually, the pattern "CRC says OK but payload says garbage" would have been visible per-packet, not just in aggregate. Even without that specific bug, separating "lost" from "corrupted" is fundamental diagnostic information that the current firmware throws away.

---

## NICE-TO-HAVE: Changes that significantly improve data quality

### N1: Per-packet SNR for LoRa on all rigs (C3 FIX IN FLIGHT as N2/T2)

**Current state:** C3 range firmware never calls `getSNR()`. E80 records `snr_avg_db` (session average only). V4 did not record SNR. The old C3 bench firmware DID record `avg_snr` -- this was a regression.

**Requirement:** Call `radio->getSNR()` for every LoRa packet and include it in the PKT line. FLRC has no SNR (the chip doesn't expose it for FLRC modulation) -- print 0 or empty.

**Motivation:** SNR is the second axis of link-budget analysis (alongside RSSI). Without it, you can't build BER-vs-SNR or PER-vs-SNR curves. The C3 fix is already scheduled (N2); the E80 and RP2040 rigs should adopt the same pattern.

### N2: Both LoRa RSSI fields from GetLoraPacketStatus

**Current state:** All rigs read only one RSSI value from the LoRa packet status. The LR2021 datasheet (Section 7.3.3, `GetLoraPacketStatus`) exposes two:
- `rssi_pkt` -- average total received power
- `rssi_signal_pkt` -- RSSI of the LoRa signal after despreading (strips out same-channel interference/noise)

**Requirement:** Emit both in the PKT line. The common format has one `rssi_dbm` field; add `rssi_signal_dbm` as an additional field (or extend the format -- this is why the format is defined as a base set, not a closed set).

**Motivation:** In an interference-heavy outdoor environment (other radios, WiFi, etc.), `rssi_pkt` (total power) and `rssi_signal_pkt` (signal-only power) can differ significantly. The gap between them tells you how much noise/interference is present on-channel. Without both, "weak signal" and "strong signal drowned by noise" are indistinguishable. This is a cheap addition -- the opcode is already being called, the data is in the response struct.

### N3: Gap/duty-cycle column in summary output (ALL RIGS)

**Current state:** Inter-packet gap (the idle time between transmissions) is configured but not recorded in the data. The E80 host tool knows GAP (it's a CLI argument) but doesn't write it to the CSV. The C3 firmware has `tx_delay_ms` in the window table but not in the PKT/RESULT lines.

**Requirement:** Include `gap_us` (inter-packet gap in microseconds) in every summary line and in the session header. This is a configuration parameter, not a measurement, but it's essential context for interpreting throughput and duty-cycle.

**Motivation:** Duty cycle affects thermal behavior, regulatory compliance, and potentially PER (a radio that's been transmitting continuously may behave differently than one with long gaps). Without `gap_us` in the data, this variable is invisible at analysis time. The N3 schema extension already includes this column -- the firmware just needs to emit it.

### N4: Voltage and temperature recording (WHERE FEASIBLE)

**Current state:** Never recorded on any rig. The RP2040 has a free ADC that could measure supply voltage and board temperature. E80 and C3 would need wiring.

**Requirement:** If the RP2040 ADC is available, read supply voltage and chip temperature at session start and periodically (e.g. once per replicate) during the session. Emit as `VBAT=<mv> TEMP=<celsius>` in a periodic status line. E80/C3: defer until hardware is wired, but plan the data format now.

**Motivation:** PA output drifts with voltage and temperature. Battery sag during long walks affects TX power. Without these, a PER change between start and end of a session could be attributed to distance when it was actually battery drain. Even sparse sampling (once per replicate) is better than nothing.

### N5: Attenuator-dB column for cage/calibration sessions

**Current state:** No attenuator value is recorded in any data. The HW-B3 cage calibration session will use a known attenuator, but there's no field for it.

**Requirement:** When running in a cage/calibration setup, the host tool or firmware emits `atten_db=<value>` in the session header and/or per-cell summary. This is the known attenuation between TX and RX in the cage (e.g. 40 dB fixed attenuator + 30 dB step attenuator = 70 dB).

**Motivation:** Cage sessions are the reference point for absolute RSSI calibration. Without the attenuator value in the data, the calibration result can't be joined to the raw RSSI readings at analysis time -- you'd have to track it externally.

---

## OPTIONAL: Changes that add capability but are not blocking

### O1: Unified configuration table emitted at session start

**Requirement:** At session start, the firmware prints a configuration table -- one line per configuration it will test -- in a parseable format:
```
CONFIG,<config_id>,<mod>,<freq_hz>,<sf>,<bw_khz>,<cr>,<power_dbm>,<pkt_size>,<pkt_count>,<gap_us>,<sync_delay_ms>
```
This is the firmware's "experiment plan" -- it declares what configurations will be tested, in what order, before any data is collected.

**Motivation:** Lets the data system know the full expected test matrix upfront, so it can flag missing configurations at session end ("you planned 16 configs but only 14 produced data -- configs L9W-868 and F1300C34-868 have zero packets"). Today, missing configurations are silent -- you only notice when you try to plot and a cell is empty.

### O2: TX-side per-packet log (for debugging and bidirectional analysis)

**Requirement:** The TX firmware emits a line for every packet it transmits: `TX_PKT,<seq>,<ts_ms>,<config_id>`. This is captured on the TX-side serial port (which is connected to a host during bench sessions, but not during walk tests).

**Motivation:** Lets you compute true PER as `1 - (RX PKT count / TX PKT count)` per configuration, without relying on the TX-reported `sent` count (which can be wrong if the radio fails to transmit but the firmware increments the counter anyway). Also enables out-of-order detection and exact latency measurement when both sides are timestamped. Only practical for bench sessions where TX is connected to a host -- not for walk tests where TX is in a rucksack.

### O3: RSSI calibration table emission

**Requirement:** After running `SetRssiCalibration`, the firmware emits the calibration table it received: `RSSI_CAL,<path>,<gain_stage>,<gain_value>,<nf_value>`. This lets the data system record exactly what calibration was applied to this radio instance, and when.

**Motivation:** If calibration is written into the chip (via `SetRssiCalibration`), the raw RSSI values coming out of the radio are already corrected -- but the data system doesn't know what correction was applied. Emitting the table makes the correction reproducible and auditable. If calibration is done host-side (the recommended approach -- raw stays raw, correction applied at query time), this is unnecessary.

### O4: Explicit phase/config transition markers

**Requirement:** When the firmware switches from one configuration to the next, emit a transition marker: `CONFIG_START,<config_id>,<replicate>,<ts_ms>`. This clearly delineates where one test point ends and the next begins, even in a continuous capture stream.

**Motivation:** In the C3 autonomous firmware, configuration boundaries are implicit -- you have to infer them from changes in the PKT line fields. An explicit marker makes parsing robust against missing RESULT lines, partial captures, and firmware crashes mid-session.

---

## IMPLEMENTATION PRIORITY AND SEQUENCING

**Phase 1 (before next session with boards):** M1, M2, M3, M4, M5, M6, M7
These are the minimum for trustworthy data ingest. If the next session runs without these, the data it produces will have the same class of provenance and granularity gaps as the historical data. The total firmware effort is modest -- most of these are printf additions or counter-type changes, not algorithmic changes.

**Phase 2 (as soon as feasible):** N1, N2, N3
These add significant analytical value (SNR, interference separation, duty-cycle context) and are cheap once M4's common format is in place (they're just additional fields in the same line).

**Phase 3 (when hardware allows):** N4, N5
Voltage/temperature requires ADC wiring on E80/C3. Attenuator recording requires cage hardware. Plan the data format now, implement when hardware is ready.

**Phase 4 (nice to have):** O1-O4
These add automation and robustness but are not blocking. Implement opportunistically.

---

## COMPATIBILITY NOTE

The common per-packet format (M4) is designed as a **superset** of all three existing formats. No existing analytical capability is lost. The mapping from each legacy format to the common format is straightforward:

- C3 `PKT` line: all 20 fields map directly; add `ts_ms` (from `esp_timer`), `snr_db` (call `getSNR()`), `crc_ok` (derive from `readData` result), `bit_err`/`bytes_bad` (from `prbs15_verify` outputs already computed), and the radio params (from the window struct, already in scope)
- V4 `PKT` line: all 11 fields map; add the missing radio params (from the phase config table), `crc_ok` (from CRC check), `bit_err`/`bytes_bad` (V4 doesn't do PRBS -- empty)
- E80 (new): add a printf in the RX packet handler that emits the common format using data already in scope (`e.seq`, `rssi`, `snr`, CRC status)

The per-cell summary format (E80 `STAT?` / C3 `RESULT` / V4 `PHASE_RESULT`) should also be harmonized, but that is a separate task and less urgent -- the per-packet format is the priority because it's the grain at which cross-rig comparison happens.

---

*This document can be committed to the repo as `docs/data-handover/FIRMWARE-HARMONIZATION-2026-08-19.md` or kept as a working document. The MUST-HAVE items (M1-M7) are the priority for the next firmware session. Feedback welcome on feasibility, priorities, and anything we've missed.*
