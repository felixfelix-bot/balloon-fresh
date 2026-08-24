# Harmonized 23-Field PKT+STAT Implementation Plan

**Date:** 2026-08-24  
**Branch:** `feat/2g4-sweep` (commit `e7a78e9`)  
**Status:** PLANNING — ready for implementation  

---

## 1. Current State Analysis

### 1.1 Firmware (ALREADY harmonized)

`src/bench_pkt.c` line 56-74 emits **exactly** the target format:

```
PKT,session,config,replicate,seq,ts_ms,rssi,snr,crc_ok,bit_err,bytes_bad,freq_hz,mod,sf,bw_khz,cr,power,pkt_size,0,0,0,0,0,0
```

That's 23 data fields + `PKT,` prefix. GPS fields are hardcoded to `0` (no GPS on the STM32 bench board — stitching happens host-side). **No firmware changes needed.**

### 1.2 Python `parse_pkt_line()` (line 933 — STALE)

Parses the firmware PKT line but was written for an older schema. Key gaps:

| Firmware Field | Position | Current parse_pkt_line | Issue |
|---|---|---|---|
| `replicate` | p[3] | **skipped** | Not extracted |
| `bytes_bad` | p[10] | **skipped** (the "?" in docstring) | Not extracted |
| `bw_khz` | p[14] | parsed as `bw` | Field name mismatch only |
| `cr` | p[15] | **skipped** | Not extracted |
| `power_dbm` | p[16] | parsed as `pa_dbm` | Field name mismatch only |
| `pkt_size` | p[17] | parsed as `len` | Field name mismatch only |
| GPS fields p[18]-p[22] | — | **skipped** | Not extracted (all zeros from firmware) |
| `pcrc16` | p[23] (old 24-field) | parsed from p[24] | **WRONG** — firmware now emits 23 data fields, pcrc16 was removed |

### 1.3 RxLogWriter (line 1059)

Writes 16-column CSV with a header row. Missing: `replicate`, `bytes_bad`, `cr`, GPS fields. Uses old field names (`sf_or_br`, `pa_dbm`, `len`, `captured_ts`).

### 1.4 TxLogWriter (line 1029)

Writes per-config summary CSV with 15 columns. No STAT line emission.

### 1.5 gps_stitch.py

Joins on `captured_ts` (wall-clock ISO) or `ts_ms` (firmware uptime + `--t0-epoch`). Appends `gps_lat`, `gps_lon`, `gps_ele`, `gps_time`, `gps_offset_s`, `dist_m` columns. Works on the current 16-column CSV.

### 1.6 Existing CSV Data (rx-single-machine-2608231820.csv)

16-column format. Real data already captured in this format. Must remain readable.

### 1.7 Makefile

Targets `range-tx`, `range-rx`, `range-merge`, `range-stitch`, `range-zip`. No format flag.

---

## 2. Design Decisions

### D1: Replace RxLogWriter/TxLogWriter or add a new writer alongside?

**Decision: Replace both in-place.** Add a `--format` CLI flag with default `harmonized`. The old 16-column CSV is a *derived* artifact, not a separate writer. Rationale:
- The collaborator's doc explicitly says PKT+STAT is the ground-truth capture; the old CSV can be derived from it.
- Two parallel writers doubles maintenance and risks format drift.
- The old CSV is trivially derivable: drop GPS columns + rename fields.

### D2: How to handle `bytes_bad`?

**Decision: Parse it from p[10].** The firmware already emits `evt->bytes_bad` as an unsigned int. The current parser's docstring says "?" for this position — it was a placeholder. Parse as `int(p[10])`.

### D3: How to split `sf_or_br` into `sf` + `bw_khz`?

**Decision: Parse directly from the firmware line.** The firmware already emits separate `sf` (p[13]) and `bw_khz` (p[14]) fields. For LoRa: `sf = int(p[13])`, `bw_khz = int(p[14])`. For FLRC: firmware emits the stored SF value (meaningless) and `bw_khz` = 0. The config preset dict has `cfg["sf"]` and `cfg["bw"]` separately — use those when writing from the config side (TxLogWriter/STAT).

### D4: GPS stitching — populate inline GPS fields or write enriched file?

**Decision: Populate the GPS fields in the PKT lines directly.** The harmonized format has `gps_fix`, `gps_lat`, `gps_lon`, `gps_alt`, `gps_sats`, `gps_hdop` as inline fields (zero-filled by firmware). `gps_stitch.py` will be updated to:
1. Read PKT-prefixed lines from the capture file
2. Compute wall-clock epoch from `ts_ms` + `--t0-epoch` (or from a `captured_ts` comment if present)
3. Find nearest GPS point
4. **Rewrite the GPS fields in-place** in the PKT line
5. Write the enriched file (same format, PKT lines with GPS populated)

This keeps the output format identical — just with GPS fields filled in. No extra columns.

### D5: Makefile default to harmonized format?

**Decision: Default to harmonized. Add `FORMAT` variable for explicit override.**
```makefile
FORMAT ?= harmonized   # harmonized | legacy
```
All `range-tx`/`range-rx` targets pass `--format $(FORMAT)` to `e80_bench_ctl.py`.

### D6: STAT lines — from firmware or synthesized in Python?

**Decision: Synthesize in Python.** The firmware's `STAT?` command returns key=value pairs (parsed by `parse_stat()`). The Python tool already calls `board.stat()` after each config. We'll format the response as a `STAT,role=RX,...` line and write it to the capture file. This avoids firmware changes and gives us control over the format.

### D7: TX STAT lines?

**Decision: Emit `STAT,role=TX,...` lines from TxLogWriter.** Replace the per-config CSV row with a STAT line. Keep the old CSV as a derived artifact if `--format=legacy` is specified.

### D8: Backward compatibility?

**Decision: Keep the old 16-column CSV as a derived artifact.** Add a `--emit-legacy-csv` flag that generates the old CSV alongside the PKT+STAT file. The `range-merge` target gets a `range-merge-harmonized` variant that works on PKT+STAT files. The old `range-merge` continues to work on legacy CSVs.

---

## 3. File-by-File Change List

### 3.1 `tools/e80_bench_ctl.py`

#### 3.1.1 `parse_pkt_line()` (line 933) — REWRITE

**Current:** Parses 16 fields from 24-field firmware line, returns dict with old names.

**New:** Parse all 23 fields from the firmware line, return dict with harmonized names.

```python
def parse_pkt_line(line):
    """Parse a firmware PKT console line into a dict with 23 harmonized fields.

    Format: PKT,session_id,config_id,replicate,seq,ts_ms,rssi_dbm,snr_db,
    crc_ok,bit_err,bytes_bad,freq_hz,mod,sf,bw_khz,cr,power_dbm,pkt_size,
    gps_fix,gps_lat,gps_lon,gps_alt,gps_sats,gps_hdop

    Returns None if the line is not a valid PKT line.
    """
    if not line or not line.strip().startswith("PKT,"):
        return None
    p = line.strip().split(",")
    if len(p) < 23:  # 23 data fields + "PKT" prefix = 24 elements
        return None
    try:
        return {
            "session_id": int(p[1]),
            "config_id": int(p[2]),
            "replicate": int(p[3]),
            "seq": int(p[4]),
            "ts_ms": int(p[5]),
            "rssi_dbm": float(p[6]),
            "snr_db": float(p[7]),
            "crc_ok": int(p[8]),
            "bit_err": int(p[9]),
            "bytes_bad": int(p[10]),
            "freq_hz": int(p[11]),
            "mod": p[12],
            "sf": int(p[13]),
            "bw_khz": int(p[14]),
            "cr": int(p[15]),
            "power_dbm": int(p[16]),
            "pkt_size": int(p[17]),
            "gps_fix": int(p[18]),
            "gps_lat": float(p[19]),
            "gps_lon": float(p[20]),
            "gps_alt": float(p[21]),
            "gps_sats": int(p[22]),
            "gps_hdop": float(p[23]) if len(p) > 23 else 0.0,
        }
    except (ValueError, IndexError):
        return None
```

**Key changes:**
- `session` → `session_id`, `config` → `config_id`, `pkt_idx` → `seq`
- Added: `replicate`, `bytes_bad`, `cr`, GPS fields (6)
- `sf_or_br` → `sf` (firmware already emits separate `sf`)
- `bw` → `bw_khz`
- `pa_dbm` → `power_dbm`
- `len` → `pkt_size`
- Removed: `pcrc16` (not in harmonized format)
- Removed: `captured_ts` from parsed dict (host adds it as a comment or uses `ts_ms` + t0)

#### 3.1.2 Add `format_pkt_line()` — NEW FUNCTION

Inverse of `parse_pkt_line()`: formats a parsed dict back to a PKT, CSV line. Used by gps_stitch.py when rewriting lines with GPS data.

```python
PKT_FIELD_ORDER = [
    "session_id", "config_id", "replicate", "seq", "ts_ms",
    "rssi_dbm", "snr_db", "crc_ok", "bit_err", "bytes_bad",
    "freq_hz", "mod", "sf", "bw_khz", "cr", "power_dbm", "pkt_size",
    "gps_fix", "gps_lat", "gps_lon", "gps_alt", "gps_sats", "gps_hdop",
]

def format_pkt_line(d):
    """Format a parsed PKT dict back to a PKT, CSV line."""
    vals = []
    for f in PKT_FIELD_ORDER:
        v = d.get(f, 0)
        vals.append(str(v))
    return "PKT," + ",".join(vals)
```

#### 3.1.3 Add `format_stat_line()` — NEW FUNCTION

Formats a `parse_stat()` dict as a `STAT,role=...` line.

```python
STAT_RX_FIELDS = [
    "role", "sent", "sent_ok", "rx", "crc_err", "per_x1e6",
    "per_ci_x1e6", "elapsed_s", "kbps", "rssi_avg_dbm",
    "rssi_min_dbm", "rssi_max_dbm", "snr_avg_db", "snr_min_db",
    "ber_pct", "bit_errors", "bits_checked", "cr",
    "session", "config", "replicate", "drops", "gap_us",
]

def format_stat_line(role, stat, session, config, replicate=1):
    """Format a stat dict as a STAT,role=... line."""
    parts = ["STAT,role={}".format(role)]
    # Map parse_stat() output keys to STAT line keys
    parts.append("sent={}".format(stat.get("sent", 0)))
    parts.append("sent_ok={}".format(stat.get("sent_ok", 0)))
    parts.append("rx={}".format(stat.get("recv", 0)))
    parts.append("crc_err={}".format(stat.get("crc_err", 0)))
    per = stat.get("per_pct")
    parts.append("per_x1e6={}".format(int(per * 1e4) if per is not None else 0))
    # ... etc for all fields
    parts.append("session={}".format(session))
    parts.append("config={}".format(config))
    parts.append("replicate={}".format(replicate))
    parts.append("drops={}".format(stat.get("drops", 0)))
    parts.append("gap_us={}".format(stat.get("gap_us", 0)))
    return ",".join(parts)
```

#### 3.1.4 `RxLogWriter` (line 1059) — REWRITE as `HarmonizedRxLogWriter`

Replace the CSV-based writer with one that writes PKT, lines directly. The file is a text file with PKT/STAT lines, not a CSV with a header row.

```python
class HarmonizedRxLogWriter:
    """rx-log.pkt: PKT + STAT lines in harmonized format. Incremental flush."""

    def __init__(self, path):
        self.path = path
        # No header row — PKT/STAT lines are self-describing

    def pkt_line(self, pkt_dict):
        """Write a PKT line from a parsed packet dict."""
        line = format_pkt_line(pkt_dict)
        with open(self.path, "a") as f:
            f.write(line + "\n")
            f.flush()

    def stat_line(self, role, stat, session, config, replicate=1):
        """Write a STAT line from a parse_stat() dict."""
        line = format_stat_line(role, stat, session, config, replicate)
        with open(self.path, "a") as f:
            f.write(line + "\n")
            f.flush()

    def comment(self, text):
        with open(self.path, "a") as f:
            f.write("# {}\n".format(text))
            f.flush()
```

#### 3.1.5 `TxLogWriter` (line 1029) — REWRITE as `HarmonizedTxLogWriter`

Emits `STAT,role=TX,...` lines instead of CSV rows.

```python
class HarmonizedTxLogWriter:
    """tx-log.pkt: STAT lines for TX side. Incremental flush."""

    def __init__(self, path, session_id):
        self.path = path
        self.session_id = session_id

    def stat_line(self, config_idx, stat_dict, replicate=1):
        """Write a STAT,role=TX line."""
        stat_dict["session"] = self.session_id
        stat_dict["config"] = config_idx
        stat_dict["replicate"] = replicate
        line = format_stat_line("TX", stat_dict, self.session_id, config_idx, replicate)
        with open(self.path, "a") as f:
            f.write(line + "\n")
            f.flush()

    def comment(self, text):
        with open(self.path, "a") as f:
            f.write("# {}\n".format(text))
            f.flush()
```

#### 3.1.6 `run_rx_mode()` (line 1307) — MODIFY

Changes in the RX capture loop (around line 1490):

1. Replace `RxLogWriter(args.rx_log)` with `HarmonizedRxLogWriter(args.rx_log)`
2. Replace the `log.pkt_row(session=..., config=..., ...)` call with `log.pkt_line(p)` (the parsed dict `p` is already in harmonized format from the new `parse_pkt_line`)
3. After each config, emit a STAT line:
   ```python
   log.stat_line("RX", rx_stat, args.session_id, cfg["idx"], replicate=1)
   ```
4. Update the comment format (no change needed — `# ...` lines are passthrough)

#### 3.1.7 `run_tx_mode()` (line 1089) — MODIFY

Changes in the TX burst loop (around line 1272):

1. Replace `TxLogWriter(args.tx_log, ...)` with `HarmonizedTxLogWriter(args.tx_log, ...)`
2. Replace `log.config_row(...)` with building a stat dict and calling `log.stat_line(...)`:
   ```python
   tx_stat = {
       "sent": tx_total,
       "sent_ok": sent_ok,
       "recv": 0, "crc_err": 0, "per_pct": 0,
       "elapsed_s": cfg["expected_s"],
       # ... other fields from parse_stat output shape
   }
   log.stat_line(cfg["idx"], tx_stat, replicate=1)
   ```

#### 3.1.8 `discard_prime_pkts()` (line 189) — MODIFY

Update field name from `pkt_idx` to `seq`:
```python
return [p for p in pkts if p.get("seq", 0) >= prime_discard]
```

#### 3.1.9 CLI args — ADD `--format` flag

In the argparse section (not shown but exists at the end of the file), add:
```python
parser.add_argument("--format", choices=["harmonized", "legacy"],
                    default="harmonized",
                    help="Output format (default: harmonized)")
```

When `--format legacy`, use the old RxLogWriter/TxLogWriter and old parse_pkt_line (keep as `parse_pkt_line_legacy` for backward compat). When `--format harmonized` (default), use the new writers.

#### 3.1.10 Add `--emit-legacy-csv` flag

Optional: when set, also generate the old 16-column CSV alongside the PKT+STAT file. This is a post-processing step, not a second writer.

### 3.2 `tools/gps_stitch.py`

#### 3.2.1 `load_rx_log()` — MODIFY

Currently loads CSV with `csv.DictReader`. Must handle two formats:
- **Legacy:** CSV with header row (current behavior)
- **Harmonized:** PKT/STAT/comment lines, no header

Add format detection:

```python
def load_rx_log(path):
    """Load RX log. Auto-detects harmonized (PKT-prefixed) vs legacy CSV."""
    with open(path, newline="", errors="replace") as f:
        first_line = f.readline()
        # Detect harmonized format
        if first_line.startswith("PKT,") or first_line.startswith("#"):
            return load_harmonized_rx(path)
        # Legacy CSV
        f.seek(0)
        reader = csv.DictReader(ln for ln in f if not ln.lstrip().startswith("#"))
        return list(reader), "legacy"
```

#### 3.2.2 Add `load_harmonized_rx()` — NEW FUNCTION

```python
def load_harmonized_rx(path):
    """Load a harmonized PKT/STAT file. Returns (pkt_dicts, 'harmonized')."""
    pkts = []
    with open(path, errors="replace") as f:
        for line in f:
            line = line.strip()
            if line.startswith("PKT,"):
                p = parse_pkt_line(line)
                if p is not None:
                    pkts.append(p)
    return pkts, "harmonized"
```

#### 3.2.3 `pick_rx_ts_col()` — MODIFY

For harmonized format, there is no `captured_ts` column. The timestamp is `ts_ms` (firmware uptime). The stitcher must use `--t0-epoch` to map to wall-clock.

Add handling:
```python
if fmt == "harmonized":
    # No captured_ts — must use ts_ms + t0_epoch
    if t0_epoch is None:
        raise ValueError("Harmonized PKT format requires --t0-epoch for GPS stitching")
    return "ts_ms"
```

#### 3.2.4 `rx_timestamp_epoch()` — MODIFY

No change needed — it already handles `ts_ms` + `t0_epoch`.

#### 3.2.5 `stitch()` — MODIFY for harmonized format

For harmonized format, instead of appending extra columns, **populate the inline GPS fields** in the PKT dict:

```python
if fmt == "harmonized":
    # Populate inline GPS fields
    new["gps_fix"] = 1 if pt is not None else 0
    new["gps_lat"] = pt.lat if pt is not None else 0.0
    new["gps_lon"] = pt.lon if pt is not None else 0.0
    new["gps_alt"] = pt.ele if pt is not None else 0.0
    new["gps_sats"] = 0  # not available from GPX/CSV tracks
    new["gps_hdop"] = 0.0  # not available from GPX/CSV tracks
    # Still compute distance if TX ref given
    if tx_lat is not None and pt is not None:
        new["_dist_m"] = haversine(tx_lat, tx_lon, pt.lat, pt.lon)
```

#### 3.2.6 `write_combined_csv()` — ADD `write_harmonized_output()`

For harmonized format, write PKT lines with GPS fields populated:

```python
def write_harmonized_output(pkts, out_path, tx_lat=None, tx_lon=None):
    """Write harmonized PKT lines with GPS fields populated."""
    with open(out_path, "w") as f:
        for p in pkts:
            f.write(format_pkt_line(p) + "\n")
        # Optionally append a dist_m summary comment
        if tx_lat is not None:
            dists = [haversine(tx_lat, tx_lon, p["gps_lat"], p["gps_lon"])
                     for p in pkts if p.get("gps_fix")]
            if dists:
                f.write("# dist_m: min={:.0f} max={:.0f} mean={:.0f}\n".format(
                    min(dists), max(dists), sum(dists)/len(dists)))
```

#### 3.2.7 `main()` — MODIFY

Branch on detected format:
- Legacy: current behavior (append GPS columns)
- Harmonized: populate inline GPS fields, write PKT lines

### 3.3 `tools/merge_csvs.py`

#### 3.3.1 Add harmonized format support

The merge logic currently joins on `(session, config, pkt_idx)`. For harmonized PKT+STAT files:
- Load PKT lines (via `parse_pkt_line`)
- Load STAT lines (via new `parse_stat_line`)
- Join PKT lines with TX STAT to compute PER
- Output combined report

Add a `--format` flag or auto-detect (same sniffing as gps_stitch.py).

### 3.4 `Makefile`

#### 3.4.1 Add `FORMAT` variable

```makefile
FORMAT ?= harmonized   # harmonized | legacy
```

#### 3.4.2 Update `range-tx` target

Add `--format $(FORMAT)` to the `e80_bench_ctl.py` invocation:

```makefile
cd $(TOOLDIR) && $(E80_CTL) --mode tx \
    --t0 $(T0) \
    --session-id $(SESSION_ID) \
    --configs "$(CONFIGS)" \
    --tx-log "$(TX_LOG)" \
    --prime-discard $(PRIME_DISCARD) \
    --format $(FORMAT) \
    --skip-fw-check
```

#### 3.4.3 Update `range-rx` target

Same: add `--format $(FORMAT)`.

#### 3.4.4 Update `range-stitch` target

Add `--t0-epoch $(T0)` for harmonized format (GPS stitching needs wall-clock mapping):

```makefile
@$(GPS_STITCH) \
    --rx "$(RX)" \
    --gps "$(GPS)" \
    --t0-epoch $(T0) \
    $$( [ -n "$(TX_GPS)" ] && echo "--tx-gps $(TX_GPS)" ) \
    $$( [ -n "$(OUT)" ] && echo "--out $(OUT)" )
```

#### 3.4.5 Update `range-merge` target

Add format detection or `--format $(FORMAT)` flag to `merge_csvs.py`.

#### 3.4.6 Update `range-zip` target

Update the header grep pattern to also match `PKT,` lines:

```makefile
head -n 5 "$(RX)" 2>/dev/null | grep -E '^(#|PKT,|session,)' || true;
```

#### 3.4.7 Update default file extensions

Consider changing default log names:
```makefile
TX_LOG ?= tx-log.pkt   # was tx-log.csv
RX_LOG ?= rx-log.pkt   # was rx-log.csv
```

**However**, this breaks existing workflows. **Decision: Keep `.csv` extension** — the file is still comma-separated, just with PKT/STAT prefixes. The collaborator's parser already handles this.

---

## 4. Test Cases (TDD)

### 4.1 New test file: `tools/test_harmonized_format.py`

### 4.2 `parse_pkt_line()` tests

| Test ID | Description | Input | Expected |
|---|---|---|---|
| T1 | Valid 23-field PKT line | `PKT,42,7,1,0,123456,-24.0,0.0,1,0,0,868000000,FLRC,8,0,3,10,64,0,0,0,0,0,0` | dict with all 23 fields, `bytes_bad=0`, `cr=3`, `gps_fix=0` |
| T2 | LoRa PKT line | `PKT,42,3,1,5,344300,-80.0,7.5,1,12,2,868000000,LORA,7,125,5,10,64,0,0.0,0.0,0.0,0,0.0` | `sf=7, bw_khz=125, cr=5, bytes_bad=2` |
| T3 | Short line (too few fields) | `PKT,42,7,1,0` | `None` |
| T4 | Non-PKT line | `STAT,role=RX,sent=100` | `None` |
| T5 | Empty line | `""` | `None` |
| T6 | Garbled RSSI | `PKT,42,7,1,0,123,abc,0.0,1,0,0,868M,FLRC,8,0,3,10,64,0,0,0,0,0,0` | `None` |
| T7 | Negative RSSI | `PKT,42,7,1,0,123,-120.5,-15.0,0,128,10,868000000,LORA,12,125,8,10,64,0,0,0,0,0,0` | `rssi_dbm=-120.5, snr_db=-15.0` |
| T8 | Real firmware line from bench_pkt.c test | `PKT,42,7,3,1234,-50,7,1,0,0,868000000,LORA,7,125,5,10,64,0,0,0,0,0,0` | All fields parsed correctly |

### 4.3 `format_pkt_line()` tests

| Test ID | Description | Input | Expected |
|---|---|---|---|
| T9 | Round-trip parse → format → parse | Parse T1 output, format, parse again | Both dicts equal |
| T10 | GPS fields populated | dict with `gps_lat=52.0, gps_lon=4.0, gps_fix=1` | Line contains `...,1,52.0,4.0,...` |

### 4.4 `format_stat_line()` tests

| Test ID | Description | Input | Expected |
|---|---|---|---|
| T11 | RX STAT line | `stat={"sent":100,"sent_ok":100,"recv":98,...}` | Line starts with `STAT,role=RX,sent=100,...` |
| T12 | TX STAT line | `stat={"sent":100,"sent_ok":100,"recv":0,...}` | Line starts with `STAT,role=TX,...` |

### 4.5 RxLogWriter/TxLogWriter tests

| Test ID | Description | Validation |
|---|---|---|
| T13 | Write 5 PKT lines to temp file | File contains 5 lines starting with `PKT,` |
| T14 | Write STAT line after PKTs | File contains PKT lines followed by STAT line |
| T15 | Comment lines preserved | `# comment` lines in file |
| T16 | TxLogWriter writes STAT,role=TX | File contains only STAT and comment lines |

### 4.6 gps_stitch.py tests

| Test ID | Description | Input | Expected |
|---|---|---|---|
| T17 | Stitch harmonized PKT file with GPX | PKT file with `ts_ms` + `--t0-epoch` | Output PKT lines with GPS fields populated |
| T18 | Stitch legacy CSV (backward compat) | Current 16-column CSV + `captured_ts` | Output CSV with appended GPS columns (unchanged behavior) |
| T19 | Auto-detect harmonized format | PKT-prefixed file | Uses harmonized path, not legacy |
| T20 | Auto-detect legacy format | CSV with header row | Uses legacy path, not harmonized |
| T21 | Missing `--t0-epoch` for harmonized | PKT file, no `--t0-epoch` | Error: "Harmonized PKT format requires --t0-epoch" |
| T22 | GPS gap warning | GPS track 60s from nearest packet | Warning printed, GPS fields still populated |

### 4.7 Integration test

| Test ID | Description |
|---|---|
| T23 | End-to-end: simulate firmware PKT lines → parse → write to file → gps_stitch → verify GPS fields populated |
| T24 | End-to-end: simulate TX + RX → merge → verify PER computation |

---

## 5. Migration Strategy

### 5.1 Phase 1: Core Parser + Writer (no behavior change)

1. Add `parse_pkt_line_harmonized()` alongside existing `parse_pkt_line()`
2. Add `format_pkt_line()`, `format_stat_line()`
3. Add `HarmonizedRxLogWriter`, `HarmonizedTxLogWriter`
4. Add `--format` flag (default: `legacy` initially to avoid breaking existing workflows)
5. Write all tests (T1-T16)
6. **Quality gate:** All tests pass, existing behavior unchanged

### 5.2 Phase 2: Wire up harmonized format

1. Update `run_rx_mode()` and `run_tx_mode()` to use harmonized writers when `--format harmonized`
2. Update `discard_prime_pkts()` field name
3. Update Makefile targets with `FORMAT` variable
4. **Quality gate:** Dry-run with `--format harmonized` produces correct PKT/STAT lines

### 5.3 Phase 3: GPS stitch migration

1. Add harmonized format support to `gps_stitch.py`
2. Update `range-stitch` Makefile target with `--t0-epoch`
3. Write GPS stitch tests (T17-T22)
4. **Quality gate:** Stitch harmonized file → GPS fields populated correctly

### 5.4 Phase 4: Merge + legacy compatibility

1. Update `merge_csvs.py` for harmonized format
2. Add legacy CSV derivation if `--emit-legacy-csv` requested
3. Integration tests (T23-T24)
4. Flip default `FORMAT` from `legacy` to `harmonized`
5. **Quality gate:** Full end-to-end test, backward compat with existing CSVs

### 5.5 Phase 5: Cleanup

1. Remove `--format legacy` code path (or keep as maintenance mode)
2. Update documentation
3. Remove old `parse_pkt_line()` (keep as `parse_pkt_line_legacy` if still referenced)
4. **Quality gate:** No references to old field names in active code paths

---

## 6. Quality Gate Checklist

### Pre-merge

- [ ] All 24 test cases pass (`pytest tools/test_harmonized_format.py -v`)
- [ ] `parse_pkt_line()` correctly parses the real firmware output from `bench_pkt.c` test (T8)
- [ ] `format_pkt_line()` round-trips through `parse_pkt_line()` (T9)
- [ ] `HarmonizedRxLogWriter` produces file with only `PKT,`, `STAT,`, and `# ` lines
- [ ] `HarmonizedTxLogWriter` produces file with only `STAT,role=TX,` and `# ` lines
- [ ] `gps_stitch.py` auto-detects harmonized vs legacy format
- [ ] `gps_stitch.py` populates inline GPS fields for harmonized format (not appending columns)
- [ ] `gps_stitch.py` legacy mode unchanged (backward compat with existing CSVs)
- [ ] `merge_csvs.py` handles both harmonized and legacy formats
- [ ] Makefile `FORMAT` variable defaults to `harmonized`
- [ ] `make range-dry-run FORMAT=harmonized` works
- [ ] `make range-stitch RX=... GPS=...` works with harmonized format (passes `--t0-epoch`)
- [ ] No field name references to `sf_or_br`, `pa_dbm`, `pkt_idx`, `captured_ts` in harmonized code paths
- [ ] Existing `rx-single-machine-2608231820.csv` still parseable by `gps_stitch.py` in legacy mode

### Post-merge (field validation)

- [ ] Capture a real test with `make rx FORMAT=harmonized` — verify file contains PKT/STAT lines
- [ ] Stitch with GPS track — verify GPS fields populated
- [ ] Send to collaborator — verify clean ingest

### Code quality

- [ ] `python3 -m py_compile tools/e80_bench_ctl.py` passes
- [ ] `python3 -m py_compile tools/gps_stitch.py` passes
- [ ] `python3 -m py_compile tools/merge_csvs.py` passes
- [ ] No new dependencies added (stdlib only)
- [ ] Docstrings updated for all modified functions
- [ ] Type hints added for new functions

---

## 7. Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Field position mismatch between firmware and parser | Medium | High | T8 uses real firmware test output; cross-check against `bench_pkt.c` line 57 |
| `pcrc16` removal breaks downstream consumers | Low | Medium | Keep `pcrc16` as optional derived field if needed; old CSV still available via `--format legacy` |
| GPS stitch wall-clock alignment off by timezone | Medium | High | `ts_ms` is firmware uptime from boot; `t0_epoch` must be the boot epoch. Document clearly. |
| `merge_csvs.py` PER computation breaks on STAT-based sent count | Medium | High | T24 integration test covers this; STAT `sent` field is the actual sent count (better than old CSV `n_pkts`) |
| Existing `.csv` files not recognized | Low | Low | Auto-detection by first-line sniff (PKT, vs header row) |
| Config preset has no `cr` field | Medium | Low | Default `cr=0` in parser; firmware emits its own `cr` value in PKT line, so Python doesn't need the config value |

---

## 8. Appendix: Field Mapping Table

| Firmware PKT Position | Harmonized Field | Old parse_pkt_line | Old RxLogWriter Column | Config Preset Key |
|---|---|---|---|---|
| p[1] | `session_id` | `session` | `session` | — (from CLI `--session-id`) |
| p[2] | `config_id` | `config` | `config` | `cfg["idx"]` |
| p[3] | `replicate` | — | — | — (always 1) |
| p[4] | `seq` | `pkt_idx` | `pkt_idx` | — (from firmware) |
| p[5] | `ts_ms` | `ts_ms` | `ts_ms` | — (from firmware) |
| p[6] | `rssi_dbm` | `rssi_dbm` | `rssi_dbm` | — (from firmware) |
| p[7] | `snr_db` | `snr_db` | `snr_db` | — (from firmware) |
| p[8] | `crc_ok` | `crc_ok` | `crc_ok` | — (from firmware) |
| p[9] | `bit_err` | `bit_err` | `bit_err` | — (from firmware) |
| p[10] | `bytes_bad` | — | — | — (from firmware) |
| p[11] | `freq_hz` | `freq_hz` | `freq_hz` | `cfg["freq"]` |
| p[12] | `mod` | `mod` | `mod` | `cfg["mod"]` |
| p[13] | `sf` | `sf_or_br` | `sf_or_br` | `cfg["sf"]` / `cfg["br"]` |
| p[14] | `bw_khz` | `bw` | `bw` | `cfg["bw"]` |
| p[15] | `cr` | — | — | — (from firmware, not in config) |
| p[16] | `power_dbm` | `pa_dbm` | `pa_dbm` | `cfg["pa"]` |
| p[17] | `pkt_size` | `len` | `len` | `cfg["plen"]` |
| p[18] | `gps_fix` | — | — | — (zero from firmware, populated by stitch) |
| p[19] | `gps_lat` | — | — | — (zero from firmware, populated by stitch) |
| p[20] | `gps_lon` | — | — | — (zero from firmware, populated by stitch) |
| p[21] | `gps_alt` | — | — | — (zero from firmware, populated by stitch) |
| p[22] | `gps_sats` | — | — | — (zero from firmware, populated by stitch) |
| p[23] | `gps_hdop` | — | — | — (zero from firmware, populated by stitch) |
| — (removed) | — | `pcrc16` | `pcrc16` | — |
| — (host-generated) | — | — | `captured_ts` | — (replaced by ts_ms + t0_epoch for stitch) |

---

## 9. Summary of Design Answers

**Q1: Replace or add new writer?** → Replace in-place with `--format` flag. Old CSV is derived.

**Q2: bytes_bad field?** → Parse from p[10]. Firmware already emits `evt->bytes_bad`.

**Q3: Split sf_or_br?** → No split needed — firmware already emits separate `sf` (p[13]) and `bw_khz` (p[14]).

**Q4: GPS stitching?** → Populate inline GPS fields in PKT lines directly. No extra columns.

**Q5: Makefile default?** → Default to harmonized. `FORMAT` variable for override.

**Q6: STAT lines?** → Synthesize in Python from `parse_stat()` output. No firmware changes.

**Q7: TX STAT lines?** → Replace per-config CSV rows with `STAT,role=TX,...` lines.

**Q8: Backward compatibility?** → Keep `--format legacy` and old CSV readers. Auto-detect in gps_stitch.py and merge_csvs.py.