# DATA CENSUS — Balloon RF Characterization Campaign (2026-08-17)

**Purpose:** input to the handover doc for the incoming data-engineering contributor.
**Method:** every claim below was verified by reading the actual firmware source, host tools, and data files on this bench PC (`~/repos/balloon-e80bench`, `~/worktrees/c3-range-bringup`, `~/worktrees/balloon-range-tests`, `~/repos/balloon-fresh/data`, `~/host-driven-bench-plan.md`). Real headers/lines are quoted as evidence.

**Rigs covered:**
- **A — E80 pair** (STM32F103 + LR2021, 900 MHz SKU, host-driven bench; repo `~/repos/balloon-e80bench`)
- **B — ESP32-C3 pair** (RadioLib autonomous range fw; `~/worktrees/c3-range-bringup/mesh-stack/flrc-bench-espidf/`)
- **C — RP2040 + LR2021 host-driven bench** (BEING BUILT per `~/host-driven-bench-plan.md`)
- **D — historical V4 / walk-test data** (RP2040 multi-radio sweep v4 + 2026-07-24 walk; `~/worktrees/balloon-range-tests` + `~/repos/balloon-fresh/data`)

---

## 1. PER-RIG ATTRIBUTE TABLES

### 1A. E80 pair (STM32+LR2021, host-driven) — READY, no field data yet

**Console protocol** (`firmware/e80-stm32-bench/src/bench.c`, fw "E80BENCH v1.2"): `ID?`, `ROLE TX|RX|NONE`, `ARM TX`, `FREQ <hz>`, `MOD flrc <br> <dbm>` / `MOD loRa <sf> <bw>`, `PA <dbm>`, `START N= LEN= GAP=`, `STAT?`, `STOP`, `BAND OVERRIDE 2026`, `POWER MODE OUTDOOR 2026`.

**STAT? reply (per-session aggregate, quoted from bench.c L684–721):**

```
STAT role= sent= sent_ok= rx= crc_err= per_x1e6= per_ci_x1e6=[lo,hi] elapsed_s= kbps= rssi_avg_dbm= snr_avg_db= drops=
```

**ID? reply (bench.c L391–418):** `ID E80BENCH v1.2 role= armed= mod=… freq= band=863-870MHz|OVERRIDE pa= pcap=+10dBm|+22dBm(OUTDOOR) chip=x.y radio=asleep|awake` — **version string only, no git hash**.

**Per-row attributes (CSV — the campaign output).** Header is fixed in `tools/e80_bench_ctl.py` L53-55 (`CSV_COLUMNS`), identical to the RP2040 plan:

```
site,stop,dist_m,repeat,mod,len,pa,freq_hz,n,sent,recv,per,per_ci_lo,per_ci_hi,rssi,snr,kbps,elapsed_s,timestamp
```

→ **19 columns, one row per cell** (cell = one modulation × N burst at one stop). PER is percent, Wilson 95% CI computed **on-board** (`bench_stats_wilson_ppm`, bench.c L697-707; PER uses the RX seq window `rx_first_seq..rx_last_seq`, not just sent−recv).

| Attribute | Unit | Type | Granularity |
|---|---|---|---|
| site, stop, dist_m, repeat | – / m / – | label | per row (host CLI args) |
| mod | flrc650/flrc2600/sf7/sf12(+anchor) | label | per row |
| len | bytes (51 matrix / 255 anchor) | int | per row |
| pa | dBm | int | per row |
| freq_hz | Hz | int | per row |
| n, sent, recv | packets | int | per row (sent = TX `sent_ok`, recv = RX `rx`) |
| per, per_ci_lo, per_ci_hi | % (6 decimals) | float | per row, on-board Wilson 95% |
| rssi, snr | dBm / dB (session **averages only**) | float | per row |
| kbps, elapsed_s | kbps / s | float | per row |
| timestamp | `%Y-%m-%dT%H:%M:%S` | label | per row (host clock) |

**Metadata (stop-level `#` comment rows**, CsvLog.stop_meta, e80_bench_ctl.py L268-279): `STOP site= stop= dist_m= repeat= freq_hz= dbm= t0=`, `gps_tx= gps_rx= h_tx_agl_m= h_rx_agl_m= ground= weather=`, `id_tx:`, `id_rx:` (full ID? lines), plus `ABORT <reason>` markers. → ~16 metadata keys per stop, **GPS = host-entered lat,lon only**.

**Rate of recording:** burst pacing is GAP-limited: FLRC-650 LEN=51 ≈ 0.7 ms airtime + 5000 µs gap ≈ **~187 pkt/s**; FLRC-2600 ≈ 0.2 ms + 5 ms ≈ 190 pkt/s; LoRa SF7 ≈ 0.1 s/pkt ≈ **9 pkt/s**; SF12 ≈ 2.5 s/pkt ≈ 0.4 pkt/s (time-capped N=10³, plan §3). Rows: **~5 rows per stop** (4 matrix cells + LEN=255 anchor) × 3 repeats. **No per-packet output at all** — the host polls `STAT?` and writes one row per cell.

**Storage:** append-only campaign CSV per site (`--csv range/siteA_S3_r2.csv`), host console transcript. **No data files from this rig exist yet** (plan is PLANNED status; `tests/sweep_*.csv` in the repo are RP2040 legacy data, see 1D).

**CR / FEC:** fixed in firmware — `radio_bench.c` L47 `.cr = LR20XX_RADIO_LORA_CR_4_5`, L55 `.cr = LR20XX_RADIO_FLRC_CR_3_4`. **Not swept.**

**Payload:** seq header + xorshift32 LFSR fill (`bench_payload.c`); RX verifies pass/fail only (`bench_payload_verify`). **No BER.**

### 1B. ESP32-C3 pair (RadioLib range fw) — HAS DATA

**16 fixed windows** (`main/range_test.h` L37-54, quoted verbatim):

```
{ "L12-868",     RANGE_LORA, 868.0f,  0,    12, 125.0f, 5,     22, 28,  20, 1000, 8,  2000 },
{ "L9-868",      RANGE_LORA, 868.0f,  0,    9,  125.0f, 5,     22, 28,  20, 1000, 8,  2000 },
{ "L9W-868",     RANGE_LORA, 868.0f,  0,    9,  500.0f, 5,     22, 28,  20,  500,  8,  2000 },
{ "L7-868",      RANGE_LORA, 868.0f,  0,    7,  125.0f, 5,     22, 28,  20, 500,  8,  2000 },
{ "L9CR7-868",   RANGE_LORA, 868.0f,  0,    9,  125.0f, 7,     22, 28,  20, 1000, 8,  2000 },
{ "L12-2G4",     RANGE_LORA, 2450.0f, 0,    12, 125.0f, 5,     12, 28,  20, 1000, 8,  2000 },
{ "L9-2G4",      RANGE_LORA, 2450.0f, 0,    9,  125.0f, 5,     12, 28,  20, 1000, 8,  2000 },
{ "L7-2G4",      RANGE_LORA, 2450.0f, 0,    7,  125.0f, 5,     12, 28,  20, 500,  8,  2000 },
{ "F260-868",    RANGE_FLRC, 868.0f,  260,  0,  0.0f,   0x00,  22, 50,  50, 100,  16, 500  },
{ "F650-868",    RANGE_FLRC, 868.0f,  650,  0,  0.0f,   0x01,  22, 50,  50, 50,   16, 500  },
{ "F1300-868",   RANGE_FLRC, 868.0f,  1300, 0,  0.0f,   0x02,  22, 100, 100, 10,  16, 500  },
{ "F1300C34-868",RANGE_FLRC, 868.0f,  1300, 0,  0.0f,   0x01,  22, 100, 100, 10,  16, 500  },
{ "F2600-868",   RANGE_FLRC, 868.0f,  2600, 0,  0.0f,   0x02,  22, 100, 100, 10,  16, 500  },
{ "F260-2G4",    RANGE_FLRC, 2450.0f, 260,  0,  0.0f,   0x00,  12, 50,  50, 100,  16, 500  },
{ "F1300-2G4",   RANGE_FLRC, 2450.0f, 1300, 0,  0.0f,   0x02,  12, 100, 100, 10,  16, 500  },
{ "F2600-2G4",   RANGE_FLRC, 2450.0f, 2600, 0,  0.0f,   0x02,  12, 100, 100, 10,  16, 500  },
```

Fields per window struct: `name, mode, freq, bitrate, sf, bw, cr, power, pkt_size, pkt_count, tx_delay_ms, preamble, sync_delay_ms`. FLRC CR decode (RadioLib `LR2021_commands.h` L505-508): **0x00 = CR 1/2, 0x01 = CR 3/4, 0x02 = CR 1 (uncoded)**. LoRa cr: 5 = 4/5, 7 = 4/7.

**Per-packet `PKT` line (range_test.cpp L472-478) — 20 fields, one per received packet:**

```
PKT,<loop>,<winId>,<name>,<mode>,<freq>,<bitrate>,<sf>,<bw>,<cr>,<power>,<pkt_size>,<seq>,<rssi>,<gps_fix>,<gps_lat>,<gps_lon>,<gps_alt>,<gps_sats>,<gps_hdop>
```

Note what is **absent**: no per-packet timestamp (no device time in the line at all), **no SNR anywhere in the C3 range fw**, no BER per packet.

**Per-window `RESULT` line (L384-393) — 27 fields, one per window:**

```
RESULT,<loop>,<winId>,<name>,<mode>,<freq>,<bitrate>,<sf>,<bw>,<cr>,<power>,<pkt_size>,<tx_sent>,<rx_recv>,<crc_errors>,<per_pct>,<ber_pct>,<avg_rssi>,<rssi_min>,<rssi_max>,<elapsed_ms>,<tput_kbps>,<gps_fix>,<gps_lat>,<gps_lon>,<gps_alt>,<gps_sats>,<gps_hdop>
```

**BER is real here:** TX fills payload with PRBS15 seeded by seq (`prbs15_fill(buf+4, pkt_size-4, p)`, L150); RX verifies (`prbs15_verify` L465): `bitErrors += popcount(byte^expected)`, `bitsChecked += (len-4)*8`, `payloadCorrupt++` per packet with ≥1 bad byte (prbs.cpp L16-35). This is **post-FEC residual BER** (only CRC-passing packets reach the check; `readData` failure → `rxCrcErrors++` instead).

**NVS logging (RX, survives power loss):** `NvsTestResult` struct (`nvs_results.h`) mirrors the RESULT line incl. `payload_corrupt, bit_errors, bits_checked, gps_*` — max **32 results**, dumped as CSV on request (`nvs_print_all_results`, nvs_results.cpp L106):

```
test_name,role,loop,mode,freq,bitrate,sf,cr,power,pkt_size,tx_sent,rx_received,crc_errors,lost,per_pct,ber_pct,avg_rssi,min_rssi,max_rssi,elapsed_ms,throughput_kbps,payload_corrupt,bit_errors,bits_checked,gps_fix,gps_lat,gps_lon,gps_alt,gps_sats,gps_hdop
```
→ **30 columns.**

**GPS:** optional MAX-M10S on UART1 behind compile flag `CONFIG_RANGE_TEST_GPS` (L240-244: "GPS initialized on UART1" / "GPS disabled (compile flag)"). `gps_data_t` = `{fix, latitude, longitude, altitude_m, sats, hdop}` — **sats + hdop quality fields ARE recorded**, both per-packet and per-window.

**Rate:** TX sends 5 sync pkts, then pkt_count packets at tx_delay_ms spacing, then 3 END pkts; windows loop forever with 10 s gap (`RANGE_GAP_MS 10000`). Effective burst rates: F2600 100×10 ms = **100 pkt/s**; F650 50×50 ms = 20 pkt/s; L7 20×500 ms = 2 pkt/s; L12 20×1000 ms = **0.02 pkt/s**. RX emits one PKT line per received packet (printf + fflush, unbuffered).

**Power:** fixed per window (+22 dBm 868, +12 dBm 2450 — `initRadio` clamps HF to 12: `if (w->freq > 1500.0f && pwr > 12) pwr = 12;`).

**Existing data files** (`~/repos/balloon-fresh/data/`, mirrored to all worktrees):
- `range_test_20260723_050511.csv` (16 lines) + `.raw` (13 PKT, 0 RESULT) — from an **older firmware** with different line format: raw `PKT 100 seq=1020039395 rssi=-106 uptime=466550ms` / `RANGE_RESULT_RX,window=16,rx=167,unique=167,lost=4278868851,total=4278869018,per=100.00,elapsed_ms=30000,throughput_kbps=11.4,rssi_avg=-105.7,rssi_min=-107,freq=2440.0,bitrate=2600,pktSize=255,uptime_ms=450739`. Host CSV header: `timestamp,type,seq,rssi,burst,rx,unique,lost,per,throughput_kbps,rssi_avg,rssi_min,bitrate,raw` (14 cols; host adds wall-clock timestamp per line).
- `power-sweep-20260723.csv` (9 lines): `power_dBm,pkt_count,rssi_avg,rssi_min,rssi_max,uptime_ms,capture_seconds` — a 0–9 dBm manual PA sweep from the same older fw (raw sidecars `power-sweep-raw-p*.txt`).
- `range-test-results.csv`: header-only **manual** template, 21 cols: `date,distance_m,bitrate_kbps,tx_power_dbm,payload_bytes,freq_mhz,antenna,orientation,obstacle,environment,tx_sent,rx_received,rx_unique,rx_lost,loss_pct,rssi_avg_dbm,rssi_min_dbm,throughput_kbps,elapsed_ms,verdict,notes` — never filled.
- Old C3 bench (bench_main.cpp / test_suite, command-driven `MODE/FREQ/BR/SF/BW/CR/PWR/SIZE/...`): 32-col CSVs in `~/repos/balloon-e80bench/mesh-stack/flrc-bench-espidf/`: `power_sweep_868.csv` (rows `PWR-+22`, `PWR-+18`, …), `power_sweep_2g4.csv` (`2G4-PWR-+12`, `+8`…), `flrc_sweep_868.csv` (F-260/F-325/…), `pkt_size_sweep.csv` (SIZE-20/50/…). Header (32 cols):
  `test_name,mode,freq,bitrate,sf,bw,cr,power,pkt_size,tx_delay,preamble,tx_sent,tx_errors,tx_elapsed_ms,tx_throughput_kbps,rx_received,rx_crc_errors,rx_lost,rx_total_sent,rx_elapsed_ms,rx_throughput_kbps,per_pct,ber_pct,avg_rssi,min_rssi,max_rssi,avg_snr,payload_corrupt,bit_errors,bits_checked,out_of_order,seq_gaps` — note this old bench **did** record `avg_snr` and `out_of_order/seq_gaps`, which the current range fw dropped.

### 1C. RP2040 + LR2021 host-driven bench (PLANNED — per ~/host-driven-bench-plan.md)

- **CSV columns fixed** (plan §HS-2): `site,stop,dist_m,repeat,mod,len,pa,freq_hz,n,sent,recv,per,per_ci_lo,per_ci_hi,rssi,snr,kbps,elapsed_s,timestamp` — **19 columns, same as E80** (deliberate, E80 `parse_stat()` port stays ~verbatim).
- Wilson 95% CI computed **on-board** (integer port of `bench_stats.c`); `STAT?` line (plan §1): `STAT role= mod= br_hz= freq_hz= dbm= len= n= gap_us= sent= sent_ok= rx= crc_err= per_x1e6= per_ci_x1e6=[lo,hi] rssi_avg_dbm= rssi_min_dbm= snr_avg_db= kbps= elapsed_s= state=`.
- `ID?` → `ID range-host v1 fw=<hash> role=<r>` — **fw hash per session (in ID?, not per row)**.
- FREQ hard-clamped 863–870 MHz (EU SRD, LF path only v1); PA −18..+22 (>10 needs `POWER MODE OUTDOOR 2026`); GAP 100 µs–100 s (→ up to ~200 pkt/s at 5 ms gap, ~3 000 pkt/s at the 100 µs floor for FLRC-2600); N up to 10⁶.
- **RSSI marked UNCALIBRATED in CSV** (plan REV-2 minors: "RSSI marked UNCALIBRATED in CSV; HW-B3 adds cage calibration (known PA + attenuator)").
- **Known RSSI gap:** the radio backend being ported reads RSSI only via FLRC packet-status opcode — `flrc_range_rx_sweep.cpp` L158-175: "RSSI readback via GET_FLRC_PACKET_STATUS (0x024B) — 9-bit assembly" (`raw = (buf[4]<<1) | ((buf[6]&0x04)>>2)`, `return -(int8_t)(raw/2)`); noise floor via `GET_RSSI_INST 0x020B` (L177-201). Plan REV-2 M4 therefore adds **FW-5b "RX + RSSI both mods incl LoRa packet status read"** — i.e., LoRa RSSI is a missing opcode path today.
- No GPS, no BER in v1 (CSV has no BER column; FW-8 = pattern-verify for PER only).
- Payload: bytes 0–3 big-endian seq + incrementing pattern, end marker `DE AD BE EF` + 4B count (plan §1).

### 1D. Historical V4 / walk-test data (RP2040 multi-radio sweep v4)

**V4 phase table** (`multi_radio_sweep_gps_v4.cpp` L130-153): 14 modes, **fixed frequencies 868.0 / 2440.0 MHz only** — 6 LoRa (HF SF7/SF9/SF12 BW-code 0x0F, LF SF7/SF9/SF12 BW-code 0x05, LoRa cr=1 in table) + 8 FLRC (325/650/1300/2600 on each band). Interleave mode: **14 modes × 4 sizes (32/64/128/255) = 56 phases**, `phase = (unix_time % cycle) / slot`, LF-LoRa-SF12 >32 B auto-skipped (V4-FIRMWARE-STATUS.md).

**TX packet layout** (V4-FIRMWARE-STATUS.md §CRC-16): `0-3 sync (A5 5A 42 24) | 4-18 GPS (lat,lon,sats,fixQ,utcSec) | 19 phase | 20-21 seq | 22-28 fw git hash (7 ASCII) | 29-252 BER fill (byte[i]=i&0xFF) | 253-254 CRC-16-CCITT`.

**RX per-packet line** (rx_v4 L1031): `PKT rx=%d seq=%u rssi=%d phase=%d rx_ms=%lu tx_lat=%.5f tx_lon=%.5f sats=%u fix=%u utc=%lu tx_fw=%s` → **11 attributes, per packet, with ms-resolution device time and TX-side GPS + fw hash embedded in-packet.**

**RX per-phase line** (rx_v4 L701): `PHASE_RESULT %d %s pktSize=%d rx=%u unique=%d lost=%d per=%.1f rssi_avg=%.0f rssi_min=%.0f crc_err=%u garbage=%u tx_lat=%.5f tx_lon=%.5f sats=%u fix=%u utc=%lu tx_fw=%s rx_fw=%s` → **18 attributes incl. crc_err, garbage, both fw hashes.**

**Host-captured sweep CSVs** (`scripts/sweep_capture.py`, files `char_dist_1m_env_indoor_*.csv`) — **32 columns**:
`timestamp_iso,cycle,phase,name,freq_mhz,modulation,bitrate_kbps,spreading_factor,bandwidth_khz,tx_sent,rx_received,rx_unique,lost,per_pct,rssi_avg_dbm,rssi_min_dbm,crc_errors,lat,lon,sats,fix_quality,utc_sec,distance_m,throughput_kbps,goodput_kbps,goodput_efficiency_pct,effective_throughput_kbps,theoretical_max_kbps,throughput_efficiency_pct,gps_time_delta_ms,environment,notes`
…plus per-packet CSVs — **11 columns**: `timestamp_iso,phase,seq,rssi_dbm,rx_ms,tx_lat,tx_lon,sats,fix_quality,utc_sec,distance_m`.

**Legacy unified CSV** (`tools/parse_unified_csv.py` CSV_FIELDS; `~/repos/balloon-e80bench/tests/sweep_pa_on_indoor_1m.csv`) — 24 cols: `timestamp_iso,path,freq_mhz,modulation,bitrate_kbps,spreading_factor,bandwidth_khz,coding_rate,tx_power_dbm,pa_state,distance_m,los,packets_sent,packets_rx,packets_unique,per_percent,throughput_kbps,rssi_avg_dbm,rssi_min_dbm,rssi_max_dbm,snr_avg_db,pkt_size_bytes,uptime_ms,notes`.

**Walk test (2026-07-24, 5.7 km)** data preserved (postmortem §DATA PRESERVED + data/ dir): `walk-official-rx.txt` (raw RX capture; first lines `RESUME 2026-07-24T12:45:06Z`, `PHASE_RESULT 2 HF-LoRa-SF12 rx=0 … per=100.0`), `phone-gps-walk-20260724.csv` — **440 points, 25 cols** (`time,lat,lon,elevation,accuracy,bearing,speed,satellites,provider,hdop,vdop,pdop,geoidheight,ageofdgpsdata,dgpsid,activity,battery,annotation,timestamp_ms,time_offset,distance,starttimestamp_ms,profile_name,battery_charging`), `walk-correlation.json`, analysis PNGs. Per-stop metadata convention (`data/README.md`): capture files start with `# CAPTURE START`, `# RX_FIRMWARE FW_BOOT hash=…`, `# TX_FIRMWARE`, `# OPERATOR`, `# ENV`, … then CSV; `metadata.json` from `metadata-template.json` (`tx_firmware/rx_firmware {hash,tag,built}`, `firmware_match`, `verified_before_walk`). 20260725 analysis outputs: `sweep-summary.csv` (13 cols: `phase,mode,band,modulation,detail,pktSize,rx,unique,lost,per,rssi_avg,crc_err,garbage,sweep`) and `merged-3sweep.csv` (16 cols, adds `rssi_min,sats,fix`).

**Attribute counts (recorded fields, per granularity):**

| Rig | Per-packet | Per-window/cell | Per-session/meta | Total distinct |
|---|---|---|---|---|
| E80 (A) | 0 (no per-packet output) | 19 CSV + (12 STAT keys) | ~16 stop-meta keys + ID? line | **~19 row attrs (35 incl. STAT/meta)** |
| C3 range (B) | 20 (PKT) | 27 (RESULT) / 30 (NVS dump) | window table (13/line) | **~50 distinct (20+27+3 NVS-only)** |
| RP2040 host v1 (C, planned) | 0 | 19 CSV + 20 STAT keys | ID? fw hash, T0 | **~19 row attrs** |
| V4/walk (D) | 11 (PKT) | 18 (PHASE_RESULT) / 32 (host CSV) | `#` capture header + metadata.json | **~32 host + 18 fw-line** |

---

## 2. FACT-CHECK of Felix's claims

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 1 | "We record PER" | **CONFIRMED** — on every rig, as the primary metric | E80: `per_x1e6` + on-board Wilson CI (bench.c L695-707). C3: `perPct` in RESULT (L374) + `per_pct` in NVS. V4: `per=` in PHASE_RESULT (rx_v4 L701). RP2040 v1: `per,per_ci_lo,per_ci_hi` CSV cols. **Caveat:** V4 *walk* LoRa PER rows are all 100% loss / 0 rx due to phase desync (postmortem F4) — recorded but meaningless for LoRa. |
| 2 | "We sweep power" | **PARTIALLY CORRECTED** | Dedicated PA-sweep datasets exist only from the **old C3 bench**: `power_sweep_868.csv` rows `PWR-+22, PWR-+18…`, `power_sweep_2g4.csv` rows `2G4-PWR-+12, 2G4-PWR-+8…`, plus manual `power-sweep-20260723.csv` (0–9 dBm). The **current C3 range fw does NOT sweep power** — power is a fixed window field (`22` LF / `12` HF, clamped in `initRadio`). **V4 phase table has no power field at all.** E80 varies PA **between stops** per the ramp rule (RANGE-TEST-PLAN §2/§4: S0 "0 → 10", S3 "10 → 22") — `pa` is a CSV column, not an in-run sweep. RP2040 v1: PA host-set per cell (`pa` column), sweep possible via host scripting. |
| 3 | "FLRC vs LoRa" | **CONFIRMED** — everywhere | C3: 8 FLRC + 8 LoRa windows (quoted table). V4: 8 FLRC + 6 LoRa phases. E80 matrix: `flrc650,flrc2600,sf7,sf12` (MOD_DEFS). RP2040 plan: `MOD FLRC <br>` / `MOD LORA <sf> <bw>`. Old bench: `flrc_sweep_868.csv` + LoRa tests. |
| 4 | "We sweep channels" | **CORRECTED — no firmware sweeps channels** | C3 windows hardcode `868.0f`/`2450.0f` (range_test.h). V4 phases hardcode `868.0`/`2440.0` (gps_v4 L133-151). E80: `FREQ <hz>` is a **per-session host argument** (one center freq per run; EU-clamped 863–870 unless override 410–960) — a channel sweep would require manual re-runs, no tool automates it. RP2040 v1: same, FREQ host-set, hard-clamped, `freq_hz` column. **What exists is dual-band (LF vs HF), not a channel sweep.** |
| 5 | "Carrier LF vs HF" | **CONFIRMED** | C3: 868 vs 2450 windows. V4: 868 vs 2440 with a real per-band init matrix (`dual_radio_gps_sweep_tx.cpp` L505-530: `SET_RX_PATH (HF=0x01 for 2.4GHz, LF=0x00)`, `CALIB_FRONT_END — HF path sets bit 15 (feFreq |= 0x8000)`). Old bench: `power_sweep_868.csv` vs `power_sweep_2g4.csv`. E80 is 900 MHz-only (SKU E80-900M2212S, 902–928 tuning, plan §1). |
| 6 | "We record BER" | **CORRECTED — C3 family only** | **C3: YES** — PRBS15-based: `bitErrors/bitsChecked` via `prbs15_verify` (range_test.cpp L465-468, prbs.cpp L16-35); `ber_pct, payload_corrupt, bit_errors, bits_checked` in RESULT/NVS (quoted headers). This is **BER after FEC/CRC** (only packets passing radio CRC are checked). Old C3 bench CSVs also had `ber_pct, bit_errors, bits_checked`. **E80: NO** — `bench_stats_t` has no bit counters (tx_attempted, tx_done, rx_ok, rx_crc_err, rssi_sum_half, snr_sum_qdb only); payload verify is pass/fail (`bench_payload_verify`). **RP2040 v1: NO** — CSV has no BER column; FW-8 does pattern-verify for PER only. **V4: designed but not delivered** — TX fills a BER pattern (byte[i]=i&0xFF) but RX emits only a `garbage=` packet count in PHASE_RESULT, no bit counts. |
| 7 | "No error correction is used" | **WRONG — CORRECTED** | Error correction is present **and swept** on the C3: FLRC windows use FEC CR **1/2** (F260: cr 0x00), **3/4** (F650, F1300C34: 0x01), and **uncoded CR 1** (F1300, F2600: 0x02) — decode per RadioLib `LR2021_commands.h` L505-508; the F1300 vs F1300C34 pair is a controlled CR experiment. LoRa windows use CR **4/5** (cr=5) vs **4/7** (L9CR7, cr=7). E80 firmware fixes LoRa CR 4/5 and FLRC CR 3/4 (`radio_bench.c` L47/L55) — FEC on, not swept. **Consequence for data:** FEC-corrected bit errors are invisible to PER (packet delivered = success), so PER alone understates channel error; the residual **post-FEC BER is still measurable via PRBS on the C3** (claim 6), giving the FEC-coding-gain analysis its two halves. |
| 8 | "GPS" | **PARTIALLY CORRECTED** | **C3: yes, when wired AND compiled in** — `CONFIG_RANGE_TEST_GPS` flag, MAX-M10S on UART1; records `fix/lat/lon/alt/sats/hdop` per packet AND per window (quoted lines). **E80: no on-board GPS** — lat,lon of each rig entered by operator as stop metadata (`--gps-tx/--gps-rx` → `# gps_tx= gps_rx=` comment rows). **RP2040 v1: off** (no GPS in protocol or CSV). **V4 walk: TX GPS embedded in payload but garbage** (postmortem F1/F2: "All GPS payload data from walk is unreliable"); the phone CSV is the only ground truth. |

---

## 3. WHAT'S MISSING / GAPS (each with analysis impact)

1. **RSSI calibration — none anywhere.** RANGE-TEST-PLAN §3: *"LR2021 RSSI is uncalibrated in absolute terms. Use it only for slope (dB per distance decade) and cross-modulation deltas — never for absolute sensitivity claims. PER is the only absolute metric."* RP2040 plan: "RSSI marked UNCALIBRATED in CSV; HW-B3 adds cage calibration (known PA + attenuator)". **Impact:** no absolute received-power axis; fade margin and sensitivity thresholds can only be stated in PER terms, RSSI only as relative slope.
2. **Per-packet RSSI availability is rig-dependent.** C3: yes (`PKT … rssi`, plus min/max/avg per window). V4: yes (`PKT … rssi=`). E80: **no** — session average only (`rssi_avg_dbm`; no min/max). RP2040 v1: aggregates only (avg/min in STAT). **Impact:** per-packet RSSI distribution/fade statistics exist only for C3/V4 datasets.
3. **LoRa RSSI opcode gap (RP2040).** The RX backend being ported reads packet status only via `GET_FLRC_PACKET_STATUS 0x024B` with FLRC response layout (`flrc_range_rx_sweep.cpp` L158-175); LoRa needs a different packet-status path — plan adds FW-5b "RX + RSSI both mods incl LoRa packet status read". **Impact:** until FW-5b lands, LoRa cells would have empty/wrong `rssi` in the new bench CSV.
4. **Voltage / temperature — never recorded.** `grep -ri "volt|temp|adc|battery"` over E80 bench sources, C3 range_test.cpp, V4 rx: no hits (only GPS/`payloadCorrupt` false-positives). The phone GPS CSV is the only file with a `battery` column. **Impact:** PA output vs spec drift, battery sag during walks, and radio temperature behavior cannot be corrected or correlated.
5. **Antenna orientation — prose discipline, not data.** RANGE-TEST-PLAN §2: "same stock whips, vertical polarization, 1.5 m AGL tripods" (protocol constant); the manual template `range-test-results.csv` has `antenna,orientation,obstacle` columns but is header-only/never filled. **Impact:** orientation/LOS claims rely on operator compliance; nothing in the data proves it per row.
6. **Duty-cycle context not in the CSVs.** E80/RP2040 CSVs have **no `gap_us` column** (gap implied by mod defaults: 5000 µs FLRC / 1000 µs LoRa per MOD_DEFS; duty only stated in plan §4 "Duty ≤ 15% on 51 B cells"); C3 `tx_delay_ms` lives in the window table, not in PKT/RESULT lines; V4 `slotMs` not in PHASE_RESULT. **Impact:** duty-cycle/thermal effects on PER cannot be isolated from the recorded data alone.
7. **No sub-ms (or, on C3, any per-packet device) timestamps.** C3 PKT lines carry **no timestamp field at all** (host logger stamps wall-clock on arrival, as in the 20260723 CSV); V4 PKT has `rx_ms` (ms uptime); E80/RP2040 none. **Impact:** inter-arrival jitter, burst timing, and fine fade time-series on C3 data are only as good as host-side line-arrival times; no µs-resolution channel dynamics anywhere.
8. **GPS quality fields — C3 yes, others no.** C3 records `sats` + `hdop` (gps_data_t; in PKT, RESULT, NVS). E80 metadata = plain lat/lon strings. V4 recorded `sats/fix` but walk values were garbage (F1). Phone CSV is rich (`hdop,vdop,pdop,accuracy`). **Impact:** position-confidence weighting is possible only for C3 and the phone track.
9. **Firmware hash per row vs per session.** E80 ID? = "E80BENCH v1.2", **no hash** (bench.c L391); logged once per stop as `# id_tx:/id_rx:` comments. C3 range fw prints **no fw id in its data lines at all** (only boot banner "LR2021 Range Test v1.0"). V4 embedded `tx_fw`/`rx_fw` per line but real captures show `tx_fw=none rx_fw=unknown` (20260725 log). RP2040 v1 will have `fw=<hash>` in ID? (per session). **Impact:** the exact postmortem-F1 failure ("we don't know which build was on TX/RX") remains possible on B/A; rows cannot be attributed to a build from the data alone.
10. **Environment / attenuator step not systematically recorded.** V4 host CSVs have an `environment` column (values like `indoor`, filenames `char_dist_1m_env_indoor_*`); E80 has `ground`/`weather` stop metadata; **no attenuator-dB column anywhere** (the RP2040 cage/attenuator work in HW-B2/B3 has no CSV field planned). **Impact:** S0 "shielded cage" attenuation unknown → cannot anchor an absolute path-loss reference point.
11. **SNR gaps.** E80: `snr_avg_db` per session. C3 range fw: **no SNR at all** (not in PKT/RESULT/NVS) — regression vs the old bench CSV (`avg_snr` column existed). V4: none. **Impact:** BER-vs-SNR and per-packet SNR histograms are impossible on C3/V4; SNR-based sensitivity curves only exist as session averages on E80.

---

## 4. WHAT THE DATA SUPPORTS vs NOT

**Supported (with current + planned data):**
- **PER-vs-distance link-budget curves per modulation**, with rigorous uncertainty: E80/RP2040 campaigns give Wilson CI on every cell; 3 repeats/stop; log-ladder stops S0–S5 (plan §2).
- **PER vs PA (TX power)** with Wilson CI: old-bench `power_sweep_868/2g4.csv`, `power-sweep-20260723.csv`, E80 per-stop PA ramp, RP2040 `pa` column.
- **FLRC vs LoRa family curves** and **FLRC bitrate ladder** (260/650/1300/2600) at both bands.
- **FEC coding-gain comparisons** (C3): F1300 vs F1300C34 (CR 1 vs 3/4), L9 vs L9CR7 (4/5 vs 4/7), plus post-FEC residual BER vs RSSI proxy from PRBS (`ber_pct` vs `avg_rssi`).
- **RSSI-vs-distance fits** for slope only (dB/decade): per-packet data on C3/V4-walk + phone-GPS distance ground truth.
- **Dual-band LF/HF comparison panels** (same mod across bands, PA difference noted: +22 vs +12 dBm).
- **Airtime-normalized throughput/goodput**: C3 `tput`, V4 `goodput_kbps, effective_throughput_kbps, theoretical_max_kbps, throughput_efficiency_pct` columns.
- **Cage/near-field reference** (S0) once RP2040 Stage B runs.

**NOT supported — be honest with the data person:**
- **Absolute sensitivity or fade margin in dBm** — RSSI uncalibrated on all rigs (gap 1).
- **Pre-FEC BER** — the chip corrects internally; PRBS sees only post-FEC residuals.
- **Time-series fade analysis where per-packet timestamps are absent** — E80 and RP2040 v1 have *no* per-packet records at all; C3 PKT lines have no device timestamp (host arrival time only); V4 is ms-resolution. Sub-ms fading, Doppler, inter-arrival statistics: not available.
- **Channel/frequency-selectivity within a band** — no channel sweep ever ran (fact-check 4).
- **Cross-rig absolute RSSI comparison** — three different readback chains: C3 = RadioLib `getRSSI()`, RP2040 = raw `0x024B` 9-bit assembly, E80 = vendored lr20xx driver half-dBm accumulators; all uncalibrated. Compare PER across rigs, or RSSI deltas *within* one rig only.
- **LoRa RSSI on the RP2040 bench before FW-5b** (gap 3).
- **Duty-cycle/thermal and battery/voltage/temperature effects** (gaps 4, 6).
- **Walk-test V4 GPS payload analyses** — invalid per postmortem F1-F3 (garbage fields, CRC false-positives); use phone CSV + RSSI only.
- **Any C3 range-firmware SNR analysis** — SNR not recorded (gap 11).
- **Per-row firmware attribution** on E80/C3 (gap 9) — session metadata only.

---

## 5. VISUALIZATION RECOMMENDATIONS (5–8 plots; Felix = visual thinker, wants log-scale Y)

1. **PER vs distance, per modulation** — log-scale Y (PER %, 10⁻³–10²), one curve per mod (FLRC-650/2600, SF7, SF12) + LEN-255 anchor dashed; **Wilson 95% CI ribbons**; 3 repeat points shown + median line; facet LF | HF. Source: E80/RP2040 campaign CSVs. *(The core campaign deliverable.)*
2. **PER vs PA (dBm)** — log-Y PER, CI ribbons, curves per band (868 vs 2.4G) at fixed mod; marks the +10 indoor cap and +22 unlock. Source: power_sweep CSVs + campaign `pa` column.
3. **RSSI vs distance scatter + fit** — per-packet dots (C3 PKT / V4 walk), colored by mod, fitted dB/decade lines per mod; big "UNCALIBRATED — slope only" watermark; optional phone-GPS distance overlay for the walk.
4. **Dual-band comparison panel (slopegraph)** — same modulation LF vs HF: PER at matched stops as connected pairs, second panel RSSI deltas; honest PA-offset annotation (+22 vs +12 dBm).
5. **Airtime-normalized throughput vs distance** — kbps per mod on log-Y (or % of theoretical max from V4 `throughput_efficiency_pct`), showing goodput collapse before PER=100%; per-band facets.
6. **Sweep heatmap: power × modulation** — PER (or RSSI) as color in a PA (rows) × mod (cols) matrix, one panel per band; cells annotated with N. Source: old-bench sweeps now, RP2040 host matrix later.
7. **BER vs RSSI proxy (C3 only)** — post-FEC residual `ber_pct` (log-Y) vs `avg_rssi`, `payload_corrupt` rate as secondary series; shows the FEC residual floor.
8. **FEC coding-gain panel** — paired comparisons at matched conditions: F1300 vs F1300C34 and L9 vs L9CR7 PER deltas (log-Y, CI ribbons) — turns fact-check 7 into the "error correction works" figure for stakeholders.

Plot hygiene: every PER axis log-scale with CI ribbons; every RSSI axis labeled "dBm (uncalibrated)"; annotate N per point (10³ vs 10⁴ regime switches per plan §3); distance axis log-scale to match the S0–S5 ladder.

---

## 6. ONE-PAGE SUMMARY TABLE

| Rig | Status | Attr count (per-packet / per-cell) | Recording rate | Format & storage | GPS | BER | FEC/CR | RSSI calibrated? |
|---|---|---|---|---|---|---|---|---|
| **E80 pair** (STM32+LR2021, host) | tool ready, no field data | 0 / 19 CSV cols (+12 STAT keys, +16 stop-meta) | FLRC ~190 pkt/s, SF7 ~9/s, SF12 ~0.4/s; 1 CSV row per cell; ~5 rows/stop ×3 repeats | append-only CSV + `#` metadata + console transcript; `~/repos/balloon-e80bench`, campaign CSVs TBD | ✗ on-board; operator lat/lon stop-meta | ✗ packet-only | fixed: LoRa 4/5, FLRC 3/4 | ✗ (avg only, uncalibrated) |
| **C3 pair** (RadioLib range fw) | active, has data | 20 (PKT) / 27 (RESULT) / 30 (NVS dump) | up to 100 pkt/s bursts (F2600), 0.02/s (L12); 1 PKT line/pkt, 1 RESULT/16 windows/loop | printf lines → host capture; NVS (32 results) → CSV dump; `~/repos/balloon-fresh/data/` | ✓ when wired + compiled (fix/lat/lon/alt/**sats/hdop**) | ✓ PRBS15 post-FEC (bitErrors/bitsChecked/payloadCorrupt) | swept: FLRC 1/2, 3/4, uncoded; LoRa 4/5, 4/7 | ✗ (per-packet RSSI, uncalibrated; no SNR) |
| **RP2040+LR2021 host-driven v1** | being built (plan 2026-08-17) | 0 / 19 CSV cols (+20 STAT keys) | GAP-paced, ~200 pkt/s @5 ms gap (3 000/s floor); 1 CSV row per cell | append-only CSV, Wilson CI on-board; `~/worktrees/host-driven-bench` (future) | ✗ v1 off | ✗ v1 packet-only | MOD FLRC/LORA; CR not a v1 CLI arg | ✗ marked UNCALIBRATED; LoRa RSSI opcode gap → FW-5b |
| **V4 / walk (historical)** | decommissioned, data preserved | 11 (PKT) / 18 (PHASE_RESULT) / 32 (host CSV) | ~25 pkt/s bursts; PHASE_RESULT per phase (8–50 s slots); walk: 253 pkts + 440 phone pts | text log + host CSVs + `#` headers + metadata.json; `~/repos/balloon-fresh/data/` | designed (in-payload) but garbage on walk; phone CSV = truth | designed (BER fill) but only `garbage` count recorded | LoRa cr fixed; FLRC CR not varied | ✗ (per-packet RSSI, uncalibrated) |

**One-line takeaway for the data engineer:** PER with Wilson CI is the only rigorously comparable metric across all rigs; BER exists only on the C3 family (post-FEC, PRBS-based); RSSI is per-packet only on C3/V4 and uncalibrated everywhere; no channel sweep has ever run (LF/HF dual-band is what "channels" actually means); error correction is on and even swept on the C3 — Felix's "no FEC" belief is wrong and matters for interpretation.

---

### Evidence index (primary sources)
- E80 host tool + schema: `~/repos/balloon-e80bench/firmware/e80-stm32-bench/tools/e80_bench_ctl.py` (CSV_COLUMNS L53-55, MOD_DEFS L58-67, CsvLog L249-300, parse_stat L193-237)
- E80 firmware: `src/bench.c` (STAT L684-721, ID L391-418), `src/bench_stats.h`, `src/radio_bench.c` (CR fixed L47/L55), `src/bench_payload.c`
- E80 plan: `~/repos/balloon-e80bench/docs/RANGE-TEST-PLAN.md` (§2 stops, §3 cells/N-rule/CI, §3 RSSI caveat), `docs/HANDOFF-SWD-NEXT-STEPS.md`
- C3 fw: `~/worktrees/c3-range-bringup/mesh-stack/flrc-bench-espidf/main/range_test.h` (16 windows), `range_test.cpp` (PKT L472, RESULT L384, PRBS L465, GPS L226-245), `prbs.cpp`, `nvs_results.h/.cpp` (dump L106), `components/gps/gps.h`, RadioLib `LR2021_commands.h` L505-508 (FLRC CR codes)
- RP2040 plan: `~/host-driven-bench-plan.md` (§1 protocol/STAT, REV-2 M4 FW-5b, minors RSSI-uncalibrated)
- V4: `~/worktrees/balloon-range-tests/firmware/rp2040/src/multi_radio_sweep_gps_v4.cpp` (phase table L130-153), `multi_radio_sweep_rx_v4.cpp` (PHASE_RESULT L701, PKT L1031), `flrc_range_rx_sweep.cpp` (RSSI 0x024B L158-201), `docs/V4-FIRMWARE-STATUS.md`, `dual_radio_gps_sweep_tx.cpp` (band matrix L505-560)
- Data: `~/repos/balloon-fresh/data/` (range_test_20260723_050511.csv/.raw, power-sweep-20260723.csv, range-test-template.csv, metadata-template.json, README.md, phone-gps-walk-20260724.csv, sweep_clean_20260724/*, walk_test_20260724/*, range-tests/20260725/*), `~/repos/balloon-e80bench/mesh-stack/flrc-bench-espidf/*.csv`, `~/repos/balloon-fresh/docs/WALK-TEST-2026-07-24-POSTMORTEM.md`
