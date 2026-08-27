# DATA INVENTORY FOR V0 INGEST — RF Characterization Campaign

**Date:** 2026-08-19
**From:** Data engineering contributor
**To:** Felix + agent(s)
**Purpose:** Classify existing data on disk for ingest into v0 of the experiment/campaign management system, and flag gaps where more context is needed.

---

## CONTEXT: What we're building and why this inventory matters

We are designing a v0 experiment management system for the LR2021 RF characterization campaign. The system's job is to make every test run **reproducible, attributable to a known hardware/firmware state, and comparable across rigs** -- rather than a pile of incompatible one-off log files.

Before building anything, we want to ingest genuinely useful historical data as a first batch. This gives us real data to validate the schema design against, lets us start visualizing immediately, and ensures we're designing the system around actual data rather than assumptions.

**It is OK to leave some data orphaned.** Not every file on disk is worth ingesting. Debugging artifacts, smoke tests, and superseded intermediate runs have documentary value but no analytical value. We classify everything below and explicitly mark what we want, what we're skipping, and what needs more information from Felix before we can decide.

---

## TERMINOLOGY (locked in for the system)

- **Campaign** -- the overall characterization effort (one campaign, many sessions)
- **Session** -- one physical deployment / data collection outing (boards set up, capture started, data collected, boards packed up)
- **Configuration** -- a specific combination of radio parameters (modulation, band, SF/bitrate, BW, CR, power, pkt_size); the abstract "what we're testing"
- **Test point** -- a specific configuration tested at a specific distance/stop in a specific session; the concrete instance
- **Replicate** -- a repeated run of the same test point under identical conditions to assess variance; colloquially called a "pass"
- **Packet** -- one individual received transmission event (finest grain)

Legacy terms being mapped to the above:
- C3 "window" -> configuration
- V4 "phase" -> configuration
- E80 "cell" -> configuration
- Old bench "test_name" -> configuration

---

## PART 1: DATA CLASSIFIED AS USABLE -- INGEST INTO V0

### Session 1: July 23 indoor bench sweeps (RIG: old C3 bench firmware)

**Files:**
- `data/power-sweep-20260723.csv` (8 data rows: 0-12.5 dBm, 7 power levels)
- `data/power-sweep-raw-p0.txt` through `data/power-sweep-raw-p9.txt` (raw sidecars)
- `data/bitrate-sweep-325-20260723.txt`, `data/bitrate-sweep-650-20260723.txt`, `data/bitrate-sweep-1300-20260723.txt`
- `data/indoor-baseline-20260723.txt`
- `data/range_test_20260723_050511.csv` + `.raw` (old C3 range firmware format)

**What it is:** Indoor bench characterization at close range. Power sweep across 7 PA levels, bitrate sweep across 3 FLRC rates, plus a baseline capture. The `range_test` file is from an older C3 firmware version with a different line format (`PKT 100 seq=... rssi=... uptime=...`) and has a known overflow bug in the `lost` counter (`lost=4278868851` -- a uint32 wrap, not real data).

**Why it's useful:** Small but clean bench data with controlled variables. Power sweep is one of the few datasets that answers "PER vs TX power" directly. The `range_test` file has per-packet RSSI data at 2.4 GHz FLRC-2600.

**Known gaps:**
- Firmware version: unknown (old C3 bench format, no hash in data). The 32-column old bench CSVs (`mesh-stack/flrc-bench-espidf/power_sweep_868.csv`, `flrc_sweep_868.csv`, `pkt_size_sweep.csv`, `power_sweep_2g4.csv`) appear to be from the same era and may share a firmware version.
- Distance: indoor, ~1m bench (inferred from context, not recorded in data)
- Hardware unit IDs: not recorded
- RSSI: uncalibrated (as with all existing data)

**Action for v0:** Ingest the power sweep and bitrate sweeps as a session with `provenance=direct_capture`, `fw_id=null`, `fw_id_confidence=unrecoverable`, `distance_m=1` (inferred), `environment=indoor`. Flag the `lost` overflow in `range_test_20260723` as a known data-quality issue in the provenance notes. Ingest the old 32-column bench CSVs if they can be confirmed as same-session (see Question 1 below).

---

### Session 2: July 24 outdoor walk test (RIG: V4 RP2040 autonomous sweep)

**Files:**
- `data/walk-official-rx.txt` (3036 lines, 253 received packets -- the curated "official" capture)
- `data/phone-gps-walk-20260724.csv` (440 GPS points, 25 columns -- phone GPS ground truth)
- `data/phone-gps-walk-20260724.geojson`, `.gpx` (same track in other formats)
- `data/walk-correlation.json` (parsed/correlated data)
- `data/walk-comprehensive-analysis.png`, `data/walk-5km-results.png` (analysis plots)
- `data/walk-analysis-20260724.md` (analysis notes)

**What it is:** The flagship field dataset. TX in a rucksack (GPS + battery), RX on a balcony. Person walked 5.7 km. V4 firmware cycled through 14 modes (6 LoRa + 8 FLRC) across both bands. FLRC reached -55 dBm at 5.7 km with near-zero degradation. LoRa produced 0 packets (radio-config/phase-desync bug, not antenna -- documented in postmortem `docs/WALK-TEST-2026-07-24-POSTMORTEM.md`).

**Why it's useful:** This is the only real outdoor range data in existence. Phone GPS provides true distance ground truth (440 timestamped points). FLRC RSSI-vs-distance curve is the best available data for link-budget slope analysis. The LoRa failure is itself a documented data point (PER=100% across all SF, both bands, at all distances -- attributable to phase desync, not range).

**Known gaps:**
- Firmware version: unknown for both TX and RX. Postmortem says "we don't know which build was on TX/RX during the walk" (multiple sub-managers independently flashed boards, 5 board-lock steals on that day). This is unrecoverable. Ingest with `fw_id=null`, `fw_id_confidence=unrecoverable`, provenance note referencing the postmortem.
- GPS in the packet payloads is garbage (lat=-131, lon=133, sats=60665 -- byte alignment drift bug F2). The phone GPS CSV is the only valid position ground truth. Distance per packet must be computed by joining packet arrival timestamps against the phone GPS track (interpolation, not direct measurement). Mark as `distance_inferred=true` with interpolation method noted.
- CRC field is unreliable (false positives due to byte alignment drift -- postmortem F3). Do not ingest `crc_err` from this session as trustworthy; mark as `crc_err_reliable=false`.
- Antenna orientation: TX in rucksack, RX on balcony -- documented in postmortem but not in a structured field.

**Action for v0:** Ingest as a session with `provenance=direct_capture` for RX log + `provenance=inferred_from_phone_gps` for distance. Flag firmware as unrecoverable. Mark GPS payload fields as unreliable. Mark CRC as unreliable. This is the highest-value historical dataset and worth the ingest effort despite its flaws.

---

### Session 3: July 24 indoor sweeps at 1m (RIG: V4 RP2040, multiple sync approaches)

**Files (the usable variants):**
- `data/sweep_clean_20260724/char_dist_1m_env_indoor_20260724_160004.csv` (per-phase, 32 columns)
- `data/sweep_clean_20260724/char_dist_1m_env_indoor_20260724_160004_packets.csv` (per-packet, 11 columns)
- `data/sweep_utc_synced_20260724/char_dist_1m_env_indoor_20260724_174827.csv` + `_packets.csv`
- `data/sweep_synced_unix_20260724/char_dist_1m_env_indoor_20260724_165007.csv` + `_packets.csv`
- `data/sweep_gps_autonomous_20260724/char_dist_1m_env_indoor_20260724_172947.csv` + `_packets.csv`
- `data/sweep_nojump_20260724/char_dist_1m_env_indoor_20260724_160531.csv` + `_packets.csv`

**What it is:** A series of indoor 1m characterization sweeps, each testing a different time-sync approach between TX and RX (unix epoch, UTC, GPS autonomous, "nojump"). The host capture script (`scripts/sweep_capture.py`) produced both per-phase and per-packet CSVs with 32 and 11 columns respectively. The "clean" and "UTC synced" variants are the most usable.

**Why it's useful:** Controlled indoor baseline at 1m with per-packet data. The 32-column per-phase schema includes `avg_snr`, `out_of_order`, `seq_gaps` -- fields the current C3 range firmware dropped. These are the only existing datasets with SNR for FLRC modes. Multiple sync approaches in one day means we can see how sync method affects decode rate, which is itself a useful characterization of the firmware's reliability.

**Known gaps:**
- Firmware version: V4-era, but exact commit unknown. The `MASTER-ANALYSIS.md` in `data/v4-channel-sweep/` maps some captures to commit hashes (e.g. "e303327 era", "0562e73", "85793c2") -- see Question 2.
- Distance: 1m indoor (in filename, not in data rows -- the `distance_m` column is empty/-1 in the per-packet files)
- Multiple variants of the same session: unclear which is canonical. The "clean" variant appears to be a filtered/corrected version; the others are raw captures with different sync approaches.

**Action for v0:** Ingest the "clean" and "UTC synced" variants as separate sessions (or as replicates within one session if we can confirm they ran the same configurations). Ingest per-packet data where available. Flag `distance_m=1` as inferred from filename. Try to pin firmware version via the MASTER-ANALYSIS commit timeline (Question 2).

---

### Session 4: July 25 indoor sweep analysis + channel sweep (RIG: V4 RP2040)

**Files:**
- `data/range-tests/20260725/analysis/sweep-summary.csv` (73 data rows, 14 columns -- per-phase summary across 3 sweep cycles)
- `data/range-tests/20260725/analysis/merged-3sweep.csv` (16 columns -- merged across 3 sweeps with RSSI min, sats, fix)
- Analysis PNGs (7 plots in `data/range-tests/20260725/analysis/`)

**What it is:** Three sweep cycles run on July 25, merged and analyzed. The `sweep-summary.csv` includes channel-sweep phases (CH-2412 through CH-870 -- 2.4 GHz channels at 5 MHz steps and 868 MHz channels at 1 MHz steps), which is the only existing channel-selectivity data. The merged file adds `rssi_min`, `sats`, `fix` columns.

**Why it's useful:** The channel sweep data is unique -- no other session swept channels. It shows PER and RSSI variation across 12 HF channels and 8 LF channels at FLRC-1300/64B. Even though the channel sweep was "fundamentally broken" per the analysis docs (WiFi out of band, EU868 TX/RX mismatch), the data itself is real and the pattern of which channels worked and which didn't is informative.

**Known gaps:**
- Firmware version: post-`85793c2` (FLRC sync word fix) per `ANALYSIS-final.md`. This is the best-attributed historical dataset.
- The 3 sweeps are labeled 1, 2, 3 in the `sweep` column -- unclear if these are replicates (same configs, same conditions) or sequential runs with changes between them.
- Channel sweep phases show `tx_fw=none` and `rx_fw=unknown` in some rows -- firmware attribution is present in the V4 format but the values are missing.

**Action for v0:** Ingest `sweep-summary.csv` and `merged-3sweep.csv` as a session. Map channel-sweep phases as distinct configurations (channel as a new dimension or encoded in the configuration name). Flag `fw_id=85793c2-era` (inferred from analysis doc, not from data itself).

---

### Session 5: July 26 overnight automated captures (RIG: V4 RP2040)

**Files:**
- `data/rx_captures/rx_capture_20260726_*.log` (12 files, 30-min intervals, 16:09-21:06 UTC)
- `data/walk-tests/walk-20260726-*.log` (336 files at ~1-minute intervals, 05:53-21:33 UTC)
- `data/v4-channel-sweep/*.log` (20+ files, including epoch-timestamped logs decoded to July 26 02:28-10:16 UTC)
- `data/v4-interleave-bench/*.log` (7 files)

**What it is:** A long-duration automated capture session. The 12 `rx_captures` are 30-minute rotation segments (the capture script logs `rotation=1800s`). The 336 `walk-tests` files at 1-minute intervals appear to be a continuous automated capture (likely stationary or slowly moving, not a person walking -- the density and duration suggest an automated script). V4 channel sweep logs span the early morning hours (02:28-10:16 UTC).

**Why it's potentially useful:** Long-duration data is valuable for stability analysis (does PER drift over hours? does RSSI degrade with temperature? are there intermittent decode failures?). The channel sweep logs have detailed analysis docs (`MASTER-ANALYSIS.md`, `ANALYSIS-final.md`) that map decode rates to firmware commits.

**Known gaps -- NEEDS INFO FROM FELIX (Question 3):**
- Were the 336 `walk-tests` files from a stationary setup or an actual walk? The 1-minute file spacing and 15+ hour span suggest automated/stationary, but "walk" in the name suggests movement.
- What firmware was running? The `rx_captures` logs show `rx_fw=unknown` and `tx_fw=none` in PHASE_RESULT lines.
- Were the rx_captures and walk-tests running simultaneously on the same boards, or different boards?
- Do the epoch-timestamped V4 channel-sweep logs (dawn_*, live_*, robust_*) overlap with the dated files, or are they separate runs?

**Action for v0:** Pending answers to Question 3. If firmware can be pinned and the setup understood, ingest as a long-duration session with `session_type=automated_soak`. If not, inventory and defer.

---

## PART 2: DATA CLASSIFIED AS LIKELY ORPHANED -- INVENTORY ONLY

These files document the process of getting firmware working, not radio performance. We do not plan to ingest them as characterization data. We list them here for completeness and so Felix can tell us if any have unexpected value.

### July 24 smoke tests (bring-up debugging)
- `data/smoke-test-rx-20260724.txt`, `data/smoke-test-tx-20260724.txt`
- `data/smoke-test-v2-20260724.txt` through `data/smoke-test-v7-20260724.txt`
- `data/smoke-test-v3-rx-20260724.txt`, `data/smoke-test-v3-tx-20260724.txt`
- `data/smoke-test-v4-rx-20260724.txt`, `data/smoke-test-v4-tx-20260724.txt`
- `data/smoke-test-v5-rx-20260724.txt`, `data/smoke-test-v5-tx-20260724.txt`
- `data/smoke-test-set-time-fix-20260724.txt`, `data/smoke-test-rx-rawdump-20260724.txt`

**Why orphaned:** At least 7 firmware versions tested in rapid succession on July 24. These document the debugging process (time-sync fixes, radio init, packet format iterations). No controlled variables, no clean characterization.

### July 24 intermediate sweep variants (superseded by "clean" and "UTC synced")
- `data/sweep_full_20260724.txt/` (directory containing 2 incomplete sweep captures)
- `data/sweep_raw_nojump_20260724.txt` (raw version of the nojump sweep)
- `data/sweep-rx-debug-20260724.txt`, `data/sweep-rx-fixed-20260724.txt`, `data/sweep-rx-log-20260724.txt`, `data/sweep-rx-pa-on-20260724.txt`
- `data/full-sweep-rx-20260724.txt`, `data/full-sweep-tx-20260724.txt`
- `data/final-sweep-rx-20260724.txt`, `data/final-sweep-tx-20260724.txt`
- `data/synced-sweep-rx-20260724.txt`, `data/synced-sweep-tx-20260724.txt`, `data/synced2-rx-20260724.txt`, `data/synced2-tx-20260724.txt`

**Why orphaned:** Intermediate sync-fix iterations, superseded by the "clean" and "UTC synced" versions in Part 1. The raw TX-side captures may have marginal value (TX-side statistics), but the RX side is what matters and the clean versions have that.

### July 24 box-mounted captures
- `data/box-mounted-rx-20260724.txt`, `data/box-mounted-tx-20260724.txt`

**Why orphaned:** Different physical setup (box-mounted, not tripod or rucksack). No accompanying metadata or analysis. Unclear methodology. Could be promoted if Felix can describe the setup.

### July 24/25 miscellaneous
- `data/post-solder-rx-20260724.txt`, `data/post-solder-tx-20260724.txt` (post-GPS-soldering smoke test)
- `data/watchdog-test-rx.txt`, `data/watchdog-test-tx.txt` (watchdog timer test, not characterization)
- `data/tx_serial_capture_20260724_135332.txt` (TX-side serial capture, debugging)
- `data/gps_lock_monitor.log`, `data/gps_watcher2.log` (GPS fix monitoring, not radio data)
- `data/walk-balcony-rx-20260724.txt`, `data/walk-out-rx-20260724.txt`, `data/walk-fix-verified-rx.txt` (intermediate walk captures, superseded by `walk-official-rx.txt`)
- `data/walk_raw_capture.txt` (199 lines -- raw/early capture, likely superseded)
- `data/walk-full-rx-20260724.txt` (4 lines -- truncated/empty)

### July 25 individual logs (superseded by analysis CSVs)
- `data/range-tests/20260725/*.log` (30+ individual capture logs -- the analysis CSVs in Part 1 are the derived, usable form)

### Templates and manifests (not data)
- `data/metadata-template.json` (empty template)
- `data/range-test-template.csv` (empty template, 21 columns)
- `data/range-test-results.csv` (empty template, 15 columns -- different schema from the template above)
- `data/FLASH-MANIFEST.csv` (board tracking artifact)

---

## PART 3: QUESTIONS FOR FELIX / AGENT(S)

### Question 1: Old bench CSVs -- same session as July 23?

The 32-column CSVs in `mesh-stack/flrc-bench-espidf/` have a richer schema than the `data/` files from the same date:
- `power_sweep_868.csv` (8 rows: PWR-+22 through PWR--2, FLRC-1300 at 868 MHz)
- `power_sweep_2g4.csv` (rows: 2G4-PWR-+12 through 2G4-PWR-+8, FLRC-1300 at 2450 MHz)
- `flrc_sweep_868.csv` (8 rows: F-260 through F-2600)
- `pkt_size_sweep.csv` (6 rows: SIZE-20 through SIZE-255)

These include `avg_snr`, `out_of_order`, `seq_gaps`, `bit_errors`, `bits_checked` -- fields no current firmware produces. Were these produced by the same old C3 bench firmware as the July 23 `data/` files, in the same session? If so, we ingest them together. If they're from a separate session, we need a date and setup description.

### Question 2: V4 firmware commit mapping for July 24-25 sweeps

The `MASTER-ANALYSIS.md` in `data/v4-channel-sweep/` maps captures to V4 firmware commits:
- `e303327` -- "BENCH ERA, all FLRC modes work"
- `0a9fa51` -- reorder FLRC + CR=3/4
- `0562e73` -- channel sweep feature added
- `7700e22` -- FLRC-1300 index fix
- `536b418` -- RX channelSweepMode fix
- `85793c2` -- FLRC sync word length fix

Can the July 24 "clean" and "UTC synced" sweeps (Session 3 above) be mapped to specific commits in this timeline? The analysis doc maps the channel-sweep captures but not the earlier indoor sweeps. Even an approximate mapping ("these were before the channel sweep feature was added") would let us attribute firmware versions.

### Question 3: July 26 overnight session setup

The July 26 data has the largest volume (350+ files) but the least context:
1. Were the 336 `walk-tests/walk-20260726-*.log` files from a **stationary board** or an **actual walk**? The 1-minute file spacing and 15+ hour span (05:53-21:33 UTC) suggest automated/stationary, but "walk" in the naming convention suggests movement.
2. What **firmware** was running on TX and RX? The capture logs show `tx_fw=none`, `rx_fw=unknown` in PHASE_RESULT lines.
3. Were the `rx_captures/` logs (12 files, 16:09-21:06) and `walk-tests/` logs (336 files, 05:53-21:33) running **simultaneously on the same boards**, or on **different board pairs**?
4. Do the epoch-timestamped V4 channel-sweep logs (`dawn_1785039726.log` = July 26 04:22 UTC, `live_1785061013.log` = July 26 10:16 UTC, `robust_1785032905.log` = July 26 02:28 UTC) overlap with the dated files, or are they **separate runs**?
5. What was the **physical setup**? Indoor bench? Outdoor? What distance between TX and RX?

### Question 4: Hardware unit inventory

No data file records which physical LR2021 module / board was used as TX or RX in any session. For v0 we'll ingest with `tx_hw_id=null` and `rx_hw_id=null` for all historical data. But for future sessions, we need a way to identify hardware units. Questions:
1. How many physical LR2021 radio modules exist in total?
2. Are they identifiable (serial number, markings, board revision)?
3. Is there a mapping between the ESP32-S3 board MACs in the tollgate system and the radio modules attached to them?
4. For the E80 rig: the STM32 boards are a separate set -- how many, and are they identifiable?

### Question 5: `walk-official-rx.txt` vs other walk captures

The postmortem says `walk-official-rx.txt` (3036 lines, 253 packets) is the curated "official" capture. Other walk-related files exist:
- `walk-balcony-rx-20260724.txt`
- `walk-out-rx-20260724.txt`
- `walk-fix-verified-rx.txt`
- `walk-full-rx-20260724.txt` (4 lines -- appears truncated)
- `walk_raw_capture.txt` (199 lines)

Was `walk-official-rx.txt` selected from these, or is it a separate capture? What was excluded and why? Are any of the others worth ingesting?

### Question 6: Data not in the repo

Is there any data that lives on the lab PC but was NOT committed to the repo? The handover doc says "multi-GB artifacts stay on the lab PC." Are there capture logs, logic analyzer traces, SDR captures, or other data that exist physically but were never pushed? If so, a file listing (even just filenames and sizes) would help us assess whether any of it is ingestable.

---

## SUMMARY

| Session | Date | Rig | Data volume | Ingest into v0? | Key value |
|---|---|---|---|---|---|
| 1: Indoor bench sweeps | Jul 23 | Old C3 bench | ~15 files, small | YES | PER vs power, FLRC bitrate sweep |
| 2: Outdoor walk test | Jul 24 | V4 RP2040 | ~6 files, 253 pkts | YES (flagship) | Only outdoor range data; phone GPS truth |
| 3: Indoor sweeps at 1m | Jul 24 | V4 RP2040 | ~12 CSV files | YES | Controlled baseline, per-packet, SNR data |
| 4: Sweep analysis + channel sweep | Jul 25 | V4 RP2040 | ~3 CSV files | YES | Only channel-selectivity data in existence |
| 5: Overnight automated captures | Jul 26 | V4 RP2040 | 350+ files | MAYBE (needs Q3) | Long-duration stability (if context provided) |
| Orphaned | Jul 24-25 | Various | ~50 files | NO | Debugging artifacts, superseded runs |

Total ingestable: approximately 4-5 sessions, ~40 primary files, ~300 packets, plus phone GPS (440 points) and derived analysis CSVs. This is a manageable first batch -- small enough to validate the schema against, rich enough to test the visualization layer.

---

*This document is itself a deliverable -- it can be committed to the repo as `docs/data-handover/DATA-INVENTORY-2026-08-19.md` or kept as a working document. Feedback welcome on any classification or question.*