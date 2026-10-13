# Data Inventory Q&A Responses

**Date:** 2026-08-20
**Responding to:** `docs/data-handover/DATA-INVENTORY-2026-08-19.md` Part 3, Questions 1–6
**Method:** Git history analysis, file inspection, repo-wide search

---

## Question 1: Old bench CSVs — same session as July 23?

### Finding: NO — different sessions, 6 weeks apart

The 32-column CSVs in `mesh-stack/flrc-bench-espidf/` were committed on **2026-06-11** (commit `c8cd42e`, "LR2021 ESP-IDF benchmarker: comprehensive FLRC/LoRa benchmarks"). The July 23 data files in `data/` were committed on **2026-07-23** (commit `4079c7a`, "data: power sweep — LR2021 PA discontinuity found").

These are **separate sessions** separated by 6 weeks. Key evidence:

| Aspect | Old bench CSVs (`mesh-stack/flrc-bench-espidf/`) | July 23 data (`data/`) |
|--------|--------------------------------------------------|----------------------|
| Commit date | 2026-06-11 10:40 IST | 2026-07-23 16:57 IST |
| Commit hash | `c8cd42e` | `4079c7a` |
| Schema | 32-column (rich: avg_snr, out_of_order, seq_gaps, bit_errors, bits_checked) | 7-column (simple: power_dBm, pkt_count, rssi_avg, rssi_min, rssi_max, uptime_ms, capture_seconds) |
| Test runner | ESP-IDF benchmarker (`run_benchmark.py`) | Old C3 range firmware (serial capture) |
| Power levels | PWR-+22 through PWR--6 (868 MHz), 2G4-PWR-+12 through 2G4-PWR-+0 (2450 MHz) | 0, 3, 6, 9, 12, 12.5 dBm (only 2.4 GHz) |
| Format | Automated bench tool with per-packet BER | Manual serial capture with RSSI only |

The old bench CSVs come from a completely different test rig (ESP-IDF benchmarker with `run_benchmark.py` automated runner) producing rich 32-column output. The July 23 data comes from the old C3 range firmware with a simple 7-column manual capture format. They should be treated as **separate sessions** with `fw_id=null` for both, but the old bench CSVs have richer metadata (mode, freq, bitrate, sf, bw, cr, power, pkt_size all in columns).

**Recommendation:** Ingest as two separate sessions. The old bench CSVs are from a June 11 ESP-IDF benchmarker session. The July 23 data is from a separate July 23 C3 range firmware session.

---

## Question 2: V4 firmware commit mapping for July 24-25 sweeps

### Finding: The July 24 "clean" and "UTC synced" sweeps can be approximately mapped to the pre-channel-sweep era

The `MASTER-ANALYSIS.md` in `data/v4-channel-sweep/` maps the V4 channel sweep captures (July 25-26) to firmware commits. The July 24 indoor sweeps predate all of those commits.

**Filename timestamps (converted IST → UTC):**
- `sweep_clean_20260724_160004` → 16:00:04 IST = **10:30:04 UTC**
- `sweep_utc_synced_20260724_174827` → 17:48:27 IST = **12:18:27 UTC**

**Firmware commit timeline on July 24** (all times IST):
| Time (IST) | Commit | Description |
|-----------|--------|-------------|
| 12:54 | `e17db7c` | GPS coords in payload + FLRC RSSI fix |
| 12:56 | `104e622` | 500ms guard bands at phase transitions |
| 14:26 | `dae34c4` | 4-byte sync header + phase sync fix |
| 14:52 | `271c09b` | TX UTC phase selection + CDC watchdog |
| 15:12 | `4fe615d` | v7 smoke test — ALL LoRa modes working |
| 15:24 | `784af56` | GPS baud 115200→9600 |
| 15:48 | `f56bc10` | GPS baud auto-detection |
| 15:59 | `ce28c5b` | Reduce TX GPS wait to 5s |
| 16:06 | `08e038d` | TX accepts SET_TIME — Unix epoch modulo |
| 16:20 | `99f7705` | NMEA parser fix (u-blox M10) |
| 16:21 | `a3b51b1` | GPS time domain — parse RMC date |
| 16:41 | `be049db` | GPS primary time source + RX CDC watchdog |
| 17:01 | `d93deea` | GPS Unix epoch confirmed working |
| 17:28 | `dd43245` | Watchdog reboot on CDC death |
| 17:48 | `4a8e4cf` | **BREAKING: TX/RX payload byte alignment change** |
| 17:48 | `aaa7ebf` | Align embedGPS/parseGPS byte offsets |

**Mapping:**
- **sweep_clean (16:00 IST / 10:30 UTC):** Captured between `ce28c5b` (15:59) and `08e038d` (16:06). The firmware was in the pre-Unix-epoch era — TX was using SET_TIME sync, GPS baud had just been fixed. The sweep data shows garbage GPS fields (e.g. `lat=9.77952, lon=127.3232, sats=38297`), consistent with the pre-`4a8e4cf` byte alignment layout.
- **sweep_utc_synced (17:48 IST / 12:18 UTC):** Captured at the exact time of the `4a8e4cf` breaking change (17:48 IST). The data shows mixed GPS quality — some rows have valid GPS (`lat=32.63893, lon=-16.94664, sats=6, fix=1`) on LoRa phases but garbage on FLRC phases. This is consistent with a transition-era capture where TX/RX may have been running different builds.

**For the July 25 channel sweep session (Session 4):** The `ANALYSIS-final.md` attributes the firmware to post-`85793c2` (FLRC sync word fix, committed 2026-07-26 03:12 IST). However, the MASTER-ANALYSIS.md maps multiple captures across commits `e303327` through `85793c2`, all from July 25-26. The July 25 data should be attributed as:
- Early July 25 captures: `e303327` era (pre-channel-sweep, "BENCH ERA")
- Late July 25 captures: post-`0562e73` (channel sweep added) through post-`85793c2`

**Recommendation:** Tag the July 24 "clean" sweep as `fw_id=pre-4a8e4cf era` (approximately `ce28c5b`-`08e038d`). Tag the "UTC synced" sweep as `fw_id=4a8e4cf transition` (captured during the breaking payload layout change). Both are pre-channel-sweep and pre-FLRC-reorder. This is approximate — exact commit attribution is unrecoverable because multiple sub-managers were flashing boards independently (see postmortem F1).

---

## Question 3: July 26 overnight session setup

### Finding: STATIONARY setup (not walking). Firmware = V4 RP2040 with tx_fw=unknown.

**1. Were the 336 walk-tests files stationary or walking?**

**STATIONARY.** The walk-test log files contain valid GPS coordinates that barely change across all packets within a file and across files. For example, `walk-20260726-055300.log` shows:
```
PKT rx=1 tx_lat=32.63925 tx_lon=-16.94650 sats=6 fix=1
PKT rx=2 tx_lat=32.63925 tx_lon=-16.94650 sats=6 fix=1
PKT rx=3 tx_lat=32.63925 tx_lon=-16.94650 sats=6 fix=1
```
The coordinates `32.63925, -16.94650` correspond to a fixed location (Madeira, Portugal area). The variation across an entire 30-minute capture is centimeter-level (32.63917 → 32.63925), which is GPS jitter, not walking. A walking test would show kilometer-scale coordinate changes.

**Note on file count:** The DATA-INVENTORY document states "336 walk-tests files." However, git history across all branches shows only **31 unique walk-test files** (10 from July 26, 21 from July 27). The number "336" appears to come from commit `8a66f8c` ("data: walk test capture — **93% decode rate (336/362)**, 7 GPS sats, best capture yet") where 336 is the number of **decoded phases**, not files. The 336 figure in the inventory may be a misinterpretation. **NEEDS FELIX INPUT** to confirm whether additional walk-test files exist on the lab PC that were never committed.

**2. What firmware was running?**

The log files show `tx_fw=unknown` and `rx_fw=unknown` in PHASE_RESULT lines. The firmware was V4 RP2040 sweep firmware (`multi_radio_sweep_gps.cpp` / `multi_radio_sweep_rx_v4.cpp`), but the exact commit is not recorded in the data. One file (`walk-20260726-213315.log`) shows `rx_fw=03d6834`, which maps to commit `03d6834` ("fix(rx-v4): add SET_STANDBY before rfSetRx re-arm — prevents stuck-RX", committed 2026-07-25).

**3. Were rx_captures and walk-tests running simultaneously?**

Only 1 rx_capture file exists in git: `rx_capture_20260726_160940.log` (committed in `ecb05b1`). The walk-test files span 05:53–21:33 UTC. The rx_capture starts at 16:09 UTC. They overlap in time (16:09 is within the walk-test time range). The rx_capture uses a different log format (timestamped ISO lines, rotation=1800s) vs walk-tests (raw PHASE_RESULT lines). **NEEDS FELIX INPUT** on whether these were the same board pair or different rigs.

**4. Do the epoch-timestamped V4 channel-sweep logs overlap with dated files?**

The epoch-timestamped files in `data/v4-channel-sweep/` (committed in `ecb05b1`) decode to:
- `robust_1785032905.log` → July 26 02:28 UTC
- `dawn_1785039726.log` → July 26 04:22 UTC
- `live_1785061013.log` → July 26 10:16 UTC

These overlap with the overnight stability monitor log (`overnight-stability.log`, starting 02:22 UTC) and the early walk-test files (starting 05:53 UTC). They appear to be separate captures from the same overnight session, not duplicates of the dated files.

**5. Physical setup?**

Based on GPS coordinates (32.639, -16.947 = Madeira) and RSSI values (-15 to -58 dBm, typical of close-range indoor), the setup was **indoor bench / close-range stationary**. The strong RSSI (-15 to -46 dBm) indicates the TX and RX were within a few meters of each other.

---

## Question 4: Hardware unit inventory

### Finding: 4x LR2021 modules, 3x EBYTE E28-2G4M27S (SX1281)

Per `docs/inventory.md` (dated 2026-05-21) and `bom/BOM.md`:

| RF Module | Qty | Specification | Source |
|-----------|-----|---------------|--------|
| NiceRF LoRa2021 (LR2021 Gen4) | **4** | Sub-GHz + 2.4GHz, FLRC, RTToF, 19.72×15×2.2mm, 18-pin | NiceRF |
| EBYTE E28-2G4M27S (SX1281) | **3** | 2.4 GHz only, +27 dBm PA, SPI | Amazon |

**1. How many LR2021 modules exist?** → **4** NiceRF LoRa2021 modules.

**2. Are they identifiable?** → No serial numbers or markings are documented. The inventory tracks quantity only. The `FLASH-MANIFEST.csv` in `data/` (listed as an orphaned artifact) may contain board-level tracking, but it is described as empty template/manifest. **NEEDS FELIX INPUT** on whether the boards have any physical identification (labels, markings, revision numbers).

**3. ESP32-S3 board MACs to radio module mapping?** → No mapping exists in the repo. The tollgate system (if implemented) would use ESP32 MACs, but the radio modules are attached via SPI to RP2040 boards in the V4 rig, not directly to ESP32-S3. **NEEDS FELIX INPUT** on whether a board-to-module mapping exists outside the repo.

**4. E80 rig STM32 boards?** → The E80 bench firmware is in a separate repo (`~/repos/balloon-e80bench/`). No STM32 board count is documented in this repo. **NEEDS FELIX INPUT** on how many STM32 boards exist and whether they're identifiable.

---

## Question 5: walk-official-rx.txt vs other walk captures

### Finding: walk-official-rx.txt is the final, most complete capture — selected for completeness

**Git history of walk-official-rx.txt** (6 commits, showing iterative growth):
| Commit | Time (IST) | Lines | Description |
|--------|-----------|-------|-------------|
| `46032a0` | 18:16 | — | Extended walk capture — 4h outdoor test |
| `091218b` | 18:37 | 599 | Walk capture 599 lines — RX board dropped, committing before data loss |
| `67bce34` | 19:04 | 2858 | FINAL walk capture — 2858 lines, 244 packets |
| `af841c1` | 19:05 | — | 5.7km walk test — FLRC signal stable, LoRa phase desync |
| `00d4185` | 19:12 | — | Final walk capture — complete record with ESP32 bridge failover |
| `6658825` | 22:16 | 3036 | Final walk capture complete — 4h, all data preserved |

**Other walk capture files:**
| File | Lines | Notes |
|------|-------|-------|
| `walk-official-rx.txt` | **3036** | The curated final capture. 253 packets. Includes ESP32 bridge failover data. |
| `walk-balcony-rx-20260724.txt` | 189 | Early/short balcony capture. Garbage GPS (sats=20006). Pre-fix. |
| `walk-fix-verified-rx.txt` | 782 | Post-GPS-fix-verified capture. TIME_DIFF lines only, no packets decoded. |
| `walk-out-rx.txt` | 1473 | "Walk out" capture. Has packets but garbage GPS (sats=6, fix=1, lat=126.26 — pre-4a8e4cf layout). |
| `walk_raw_capture.txt` | 199 | Early/raw capture. No packets decoded (all rx=0). |
| `walk-full-rx-20260724.txt` | 4 | Truncated/empty — only 4 lines, corrupted format. |

**Why walk-official-rx.txt was selected:**
It is the **longest and most complete** capture (3036 lines vs 189–1473 for others). It was committed incrementally across 6 commits as the capture grew, with the final commit (`6658825`) explicitly labeled "final walk capture complete — 4h, all data preserved." It includes the ESP32 bridge failover segment (after the Pico USB dropped at 12:53 UTC), which the other captures lack.

The other files are **earlier, shorter, or broken captures** from the same walk test:
- `walk_raw_capture.txt` and `walk-balcony-rx-20260724.txt` are early captures before fixes
- `walk-out-rx.txt` is a mid-walk capture with pre-fix GPS layout
- `walk-fix-verified-rx.txt` is a sync-verification capture (no actual packet data)
- `walk-full-rx-20260724.txt` is truncated/corrupted

**None of the other files are worth ingesting.** They are superseded by walk-official-rx.txt in every dimension (length, completeness, data quality).

---

## Question 6: Data not in repo

### Finding: NEEDS FELIX INPUT — no explicit "lab PC data" reference found in any handover document

The DATA-INVENTORY document itself states: *"The handover doc says 'multi-GB artifacts stay on the lab PC.'"* However, searching all handover documents in the repo (`docs/HANDOVER-*.md`, `docs/*handover*`, `docs/SDR-HANDOVER.md`, `docs/MORNING-HANDOVER-V4.md`) found **no mention** of "multi-GB artifacts," "lab PC," or data left on a local machine. The quote appears to be self-referential within the DATA-INVENTORY document itself or references a verbal/Signal handover not captured in the repo.

**What was found:**
- `docs/SDR-HANDOVER.md` references live capture data at `~/repos/balloon-fresh/data/range-tests/20260725/forwarded-165613.log` — this path is in the repo.
- `docs/HANDOVER-PROMPT.md` states "All code as PRs/commits — nothing unpushed in worktrees" — suggesting everything was pushed.
- The `.gitignore` excludes only build artifacts (`.pio/`, `build/`, `*.elf`, `*.bin`) — no data files are gitignored.

**What might exist on the lab PC but not in the repo:**
1. **The "missing" walk-test files** — the inventory claims 336 files, but only 31 exist in git. If 300+ additional files exist on the lab PC, they would constitute significant uncommitted data.
2. **Logic analyzer / SDR captures** — the SDR-HANDOVER.md requests SDR investigation, but no SDR capture data is in the repo. If SDR captures were made, they would be multi-GB and likely not committed.
3. **Raw binary/ELF files** — `.gitignore` excludes `*.elf` and `*.bin`, so firmware binaries exist locally but not in git.

**NEEDS FELIX INPUT:**
- Does a file listing of uncommitted lab PC data exist?
- Were SDR captures ever performed (the SDR-HANDOVER.md was written, but were results received)?
- Are the "missing" ~300 walk-test files on the lab PC?
- Were any logic analyzer traces captured during the bench testing?

---

## Summary Table

| Question | Status | Answer |
|----------|--------|--------|
| Q1: Old bench CSVs same session? | **ANSWERED** | No — June 11 ESP-IDF benchmarker session, not July 23 |
| Q2: V4 firmware commit mapping | **PARTIALLY ANSWERED** | July 24 sweeps are pre-channel-sweep era (~`ce28c5b`–`08e038d` for clean, `4a8e4cf` transition for UTC synced) |
| Q3: July 26 overnight setup | **PARTIALLY ANSWERED** | Stationary (GPS barely changes). Only 31 files in git, not 336. Firmware = V4 RP2040, exact commit mostly unknown except one file shows `03d6834` |
| Q4: Hardware unit inventory | **PARTIALLY ANSWERED** | 4× LR2021, 3× E28-2G4M27S. No serial numbers or board-to-module mapping documented. NEEDS FELIX INPUT on identifiability and E80 STM32 count |
| Q5: walk-official-rx.txt selection | **ANSWERED** | Selected for completeness (3036 lines, 253 packets, includes ESP32 bridge failover). Others are shorter/broken/earlier captures. |
| Q6: Data not in repo | **NEEDS FELIX INPUT** | No explicit "lab PC" reference found in handover docs. Possible uncommitted data: missing walk-test files, SDR captures, logic analyzer traces |

---

*Generated by agent investigation of git history, file contents, and repo documentation. Questions requiring Felix's direct knowledge are marked NEEDS FELIX INPUT.*