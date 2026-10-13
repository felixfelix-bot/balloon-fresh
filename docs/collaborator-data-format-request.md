# Data Format Alignment -- Action Needed Before Range Campaign

## Situation

We've been ingesting every data drop from Felix's bench into our visualization system. So far we've successfully ingested 9 sessions across 5 different data formats:

1. July 23-25 legacy V4 logs (4 formats: walk-test, sweep CSVs, channel sweep, C3 bench)
2. Aug 20 E80 PRBS-15 verification (harmonized 23-field PKT format)
3. Aug 21 FLRC large-packet sweep (2-CSV: summary + per-packet)
4. Aug 21 48-config parameter sweep (same 2-CSV format, different labels)
5. Aug 22 dual-band sweep (same 2-CSV format, 2.4 GHz configs added)
6. Aug 21 868 MHz re-run on new firmware (same 2-CSV format)

The Aug 20 PRBS verification data was the only drop that came in the harmonized format we agreed on earlier. It ingested cleanly with zero adapter changes -- the data went straight through to storage and visualization with no custom parsing logic needed on our side.

Every other drop has come in a different format. Each one required us to build or modify a custom parser ("adapter") on our end to handle it. This has real costs that are getting worse as the project accelerates:

## What goes wrong when the format drifts

1. **Delayed turnaround.** Every new format means 2-8 hours of parser development, test writing, and verification before the data appears in our dashboards. The Aug 22 dual-band sweep took an extra day purely because the filenames changed (`full-sweep-results-2g4-*` instead of `full-sweep-*`), the firmware hash was different, and we had to verify nothing silently broke.

2. **Silent data corruption risk.** When formats change subtly -- a column shifts position, a field name changes, a new prefix appears in labels -- the parser might not crash. It might just misinterpret the data. We already caught one case where a `config` field in the per-packet CSV contained a session timestamp (`2608211756`) instead of a config_id. The parser silently accepted it. If we hadn't been checking manually, that data would have been stored wrong and every downstream chart would have been incorrect. With 11,000+ packets now ingested, manual checking doesn't scale.

3. **Adapter proliferation.** We now have 6 separate parsers, each with its own test suite, its own edge cases, and its own bugs. When Felix changes the sweep tool (new columns, new label formats, new file naming), we have to find the right parser, understand its assumptions, update it, update its tests, and re-verify. This is fragile. The parsers are the single point of failure between the bench data and the dashboards Felix sees.

4. **Blocked analysis.** While we're building parsers, we're not building analysis. The time spent adapting to format changes is time not spent on RSSI-vs-distance plots, PER heatmaps, and modulation comparison tools -- the visualizations Felix actually needs for the range campaign.

5. **Compounding fragility.** The range campaign will produce data from a NEW tool (`e80_campaign.py`) that doesn't exist yet. If it emits yet another CSV format, we need ANOTHER parser. And the outdoor data has per-stop metadata (distance, GPS) that the bench sweeps don't. Every new field, every new file, every new mode column is another integration point that can break silently.

## What we need

The firmware already emits data in the harmonized 23-field PKT format for the PRBS verification path. We know this works -- the Aug 20 data ingested flawlessly. The sweep tools (`e80_sweep_full.py`, the upcoming `e80_campaign.py`) need to emit data in this same format instead of their own CSV schemas.

### Per-packet data

One line per received packet, comma-separated:

    PKT,session_id,config_id,replicate,seq,ts_ms,rssi_dbm,snr_db,crc_ok,bit_err,bytes_bad,freq_hz,mod,sf,bw_khz,cr,power_dbm,pkt_size,gps_fix,gps_lat,gps_lon,gps_alt,gps_sats,gps_hdop

Field definitions:

| Field | Type | Description |
|-------|------|-------------|
| session_id | int | Session ID (e.g. 2608222108) |
| config_id | int | Config index, matches summary CSV idx (0-112 for dual-band) |
| replicate | int | Replicate number (always 1 in current sweeps) |
| seq | int | Packet sequence within config (0-indexed, resets per config) |
| ts_ms | int | Host-receive timestamp in milliseconds |
| rssi_dbm | float | Per-packet RSSI |
| snr_db | float | LoRa SNR; 0.0 for FLRC (by design, chip exposes no FLRC SNR) |
| crc_ok | 0 or 1 | Chip CRC verdict (known unreliable for FLRC on pre-fix firmware) |
| bit_err | int | PRBS-15 bit error count (the reliable integrity signal) |
| bytes_bad | int | Bad byte count |
| freq_hz | int | Frequency in Hz (868000000, 2440000000, etc.) |
| mod | string | "LORA" or "FLRC" |
| sf | int | LoRa spreading factor (5-12); 0 for FLRC |
| bw_khz | int | LoRa bandwidth in kHz (125, 250, 500); 0 for FLRC |
| cr | int | Coding rate (4/5 = 5, 4/6 = 6, 4/7 = 7, 4/8 = 8); 0 if not reported |
| power_dbm | int | PA setting in dBm |
| pkt_size | int | Payload length in bytes |
| gps_fix | 0 or 1 | 0 = no fix, 1 = fix acquired |
| gps_lat | float | Latitude (0.0 if no GPS) |
| gps_lon | float | Longitude (0.0 if no GPS) |
| gps_alt | float | Altitude in meters (0.0 if no GPS) |
| gps_sats | int | Number of satellites (0 if no GPS) |
| gps_hdop | float | Horizontal dilution of precision (0.0 if no GPS) |

### Per-config aggregate

One line per config, key=value pairs:

    STAT,role=RX,sent=N,sent_ok=N,rx=N,crc_err=N,per_x1e6=N,per_ci_x1e6=[lo,hi],elapsed_s=F,kbps=F,rssi_avg_dbm=F,rssi_min_dbm=F,rssi_max_dbm=F,snr_avg_db=F,snr_min_db=F,ber_pct=F,bit_errors=N,bits_checked=N,cr=N,session=N,config=N,replicate=N,drops=N,gap_us=N

Both PKT and STAT lines go in the SAME capture file, one line per event. The file can also contain any commentary/headers the tool currently emits -- we only parse lines that start with `PKT,` or `STAT,`.

### Session metadata

The existing session-meta JSON sidecar is fine. We read `fw_flashed_on_boards`, `operator`, `started`, `tx.port`, `rx.port` from it. Keep that as-is.

## What this fixes

- **One parser, not seven.** All bench sweeps, range campaigns, and PRBS verifications go through the same ingest path. No new parser needed when Felix adds a config, changes a label, or runs a new campaign mode.
- **Instant turnaround.** Data drops go straight to dashboards with zero adapter development. Felix sees results the same day, not the next day.
- **No silent corruption.** The format is positional and well-defined. If a field is missing or malformed, the parser catches it and flags a data quality warning -- it doesn't silently accept wrong data.
- **Unblocks the range campaign.** The upcoming `e80_campaign.py` can emit PKT+STAT lines with `gps_fix`/`gps_lat`/`gps_lon` populated for outdoor stops. The `mode=` column question (section 6a of the handover) becomes moot -- the mode can go in the STAT line as `mode=PROBE` or similar. No schema changes needed on our end.

## What about the summary CSV?

The summary CSV is fine as a DERIVED artifact for quick human inspection. Keep generating it. But the ground truth capture -- the file our system ingests -- must be PKT+STAT lines. The summary CSV can be generated FROM the PKT+STAT data after the fact.

## What about the TX log?

The distributed range test (Aug 23 handover) splits TX and RX into separate files. The TX log can emit STAT lines too:

    STAT,role=TX,sent=N,sent_ok=N,rx=0,crc_err=0,per_x1e6=0,elapsed_s=F,kbps=0,session=N,config=N,replicate=N,drops=N,gap_us=N

Our parser already handles both `role=RX` and `role=TX` STAT lines. The TX STAT provides the actual sent count (how many packets the TX board confirmed sending), which we need to compute PER correctly. Currently we infer `sent` from the CONFIG line's `count` field, which is the configured count, not the actual sent count -- these can differ (e.g. TX sent 10 but CONFIG said 100).

## Concrete ask

1. Update `e80_sweep_full.py` to emit PKT+STAT lines as the primary output (alongside or instead of the current CSVs).
2. Build `e80_campaign.py` to emit PKT+STAT lines from the start.
3. For the distributed range test, have both TX and RX emit STAT lines (with `role=TX` and `role=RX` respectively). PKT lines come from RX only.
4. The per-packet `config` field issue: in the current CSV it contains a session timestamp. In the PKT format, `config_id` (field [2]) must be the config index (0-112) matching the summary CSV's `idx` column.

This is a one-time investment that eliminates the adapter maintenance tax for every future data drop. The firmware already has the PKT+STAT emission code for the PRBS path -- the sweep tools just need to use it instead of reformatting into custom CSV schemas.
