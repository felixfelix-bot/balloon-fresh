# RANGE-TEST-PLAN — E80-900MBL-02 outdoor range campaign (sub-GHz)

Status: PLANNED. Docs only — no hardware touched. Operator decision (Felix,
2026-08-16): range tests run OUTSIDE EU SRD constraints. This plan supersedes
the D1 deferral in `docs/e80-900mbl-02-eval/PLAN-CHARACTERIZATION-GATED.md`
for range sessions only; the default policy (863–870 MHz clamp, +10 dBm
indoor cap, TX two-step) stays binding everywhere else — see
`firmware/e80-stm32-bench/README.md` §Safety policy.

## 1. Jurisdiction switch — what changes

Firmware gates (src/bench.c) and how the switch is exercised:

| Item | Indoor default | Range session (this plan) |
|---|---|---|
| Band | 863–870 MHz (EU SRD) only | Per destination region (below). Out-of-EU freq needs `BAND OVERRIDE 2026` on each board (logged; window 410–960 MHz) |
| Power | +10 dBm cap | +22 dBm via `POWER MODE OUTDOOR 2026` (logged); ramp rule §4 |
| Unlock lifetime | n/a | Per board, per boot — volatile RAM flags. Re-issue after ANY reboot/power glitch |

Destination-region band table (SKU E80-900M2212S is tuned 902–928 MHz):

| Region | Band | Center | Console | Caveat |
|---|---|---|---|---|
| Americas ISM | 902–928 | 915.0 MHz | `BAND OVERRIDE 2026`, `FREQ 915000000` | SKU-native tuning — reference campaign |
| EU SRD | 863–870 | 868.0 MHz | none | outside this plan (default policy) |
| India exempt | 865–867 | 866.0 MHz | `BAND OVERRIDE 2026` | off-SKU tuning — flag results, not comparable |

Legality/exposure per site remains the operator's call (D1); this plan
records gates and logging, not legal clearance.

### Pre-flight checklist (BOTH boards, EVERY site, before first TX)

1. Antennas finger-tight on sub-GHz SMA both boards (dummy load or antenna
   on the 2.4 GHz port — never a bare PA).
2. Console up; `ID?` — save the full reply line into the site log.
3. Verify `band=` and `pcap=` match the site row above (915 MHz site ⇒
   `band=OVERRIDE`; PA-22 stops ⇒ `pcap=+22dBm(OUTDOOR)` after unlock).
4. Issue unlocks: `BAND OVERRIDE 2026`, then `POWER MODE OUTDOOR 2026`
   (only where PA 22 is planned). Re-`ID?` to prove acceptance — both
   unlocks are firmware-logged; keep the host log too.
5. `FREQ <site center>` must reply OK. An ERR means a gate is still
   engaged: STOP, diagnose, do not TX.
6. First burst of the site at PA 0 (link check), then PA 10 (§4 ramp).
7. Confirm the STOP path works on both hosts before leaving the boards.

## 2. Distance matrix

Fixed stops, ~log ladder, 3 repeats per distance. No continuous-walk
sampling, no extrapolation between stops.

| Stop | Distance | Geometry | PA plan | Purpose |
|---|---|---|---|---|
| S0 | 0.5 m | shielded cage (attenuated) | 0 → 10 | near-field / saturation reference |
| S1 | 10 m | tripods, LOS | 0 → 10 | short-link baseline |
| S2 | 50 m | tripods, LOS | 10 | farthest +10 dBm stop (ramp rule) |
| S3 | 200 m | tripods, LOS | 10 → 22 | first +22 dBm cells |
| S4 | 500 m | tripods, LOS | 22 | mid-range |
| S5 | 1 km | tripods, LOS, grazing Fresnel | 22 | edge / PER-floor probe |

Fixed geometry: same stock whips, vertical polarization, 1.5 m AGL tripods
both ends, identical rig packing at every stop. Per stop, log to CSV
metadata: GPS lat/lon of TX and RX, antenna height AGL (both), ground type,
weather. At 868/915 MHz over 1 km the first Fresnel radius mid-path is
≈ 9 m — ground intrusion at S5 is expected and part of the result (record
terrain profile).

## 3. Per-cell protocol

4 modulation cells per repeat, LEN=51 uniform (telemetry-sized, no payload
confound across mods, worst cell ≤ 45 min):

| Mod | Console | ~airtime/pkt (51 B) | N low-PER | N edge |
|---|---|---|---|---|
| FLRC-650 | `MOD flrc 650` | 0.7 ms | 10^4 | 10^3 |
| FLRC-2600 | `MOD flrc 2600` | 0.2 ms | 10^4 | 10^3 |
| LoRa SF7 | `MOD loRa 7 125` | 0.1 s | 10^4 | 10^3 |
| LoRa SF12 | `MOD loRa 12 125` | 2.5 s | 10^3 (time-capped) | 10^3 |

PA per cell via `PA <dbm>` (or `MOD flrc <br> <dbm>`). GAP=5000 µs on FLRC,
1000 µs on LoRa. Plus one comparability anchor per stop: FLRC-650, LEN=255,
N=10^4 (~90 s) — ties this campaign to the indoor 255 B bench baseline.

- N rule: N=10^4 when expected PER < 1 % — taken from the previous stop,
  same mod, Wilson ci_hi ≤ 2 %. N=10^3 at the high-PER edge (ci_hi > 2 %).
  S0 starts at 10^4 (PER ≈ 0 expected). SF12 is time-capped at 10^3 even
  when PER < 1 % (10^4 ⇒ ~7 h/cell).
- Statistics: PER is primary. Record `STAT?` sent/recv/per plus the
  firmware Wilson 95 % CI (per_ci_lo/per_ci_hi) per cell. A "PER < 1 %"
  claim requires ci_hi < 1 %. The 3 repeats per stop are reported
  individually plus median; a stop is valid only if all 3 repeats ran at
  identical PA and geometry.
- RSSI/SNR caveat: LR2021 RSSI is uncalibrated in absolute terms. Use it
  only for slope (dB per distance decade) and cross-modulation deltas —
  never for absolute sensitivity claims. PER is the only absolute metric.

## 4. Safety

1. Antennas on before ARM — both boards, every power-up (§1 checklist).
   TX into an open SMA destroys the PA.
2. PA ramp per site: first burst PA 0, then PA 10. PA 22 only past 50 m
   (S3+). Never jump 0 → 22.
3. STOP-on-people-near: any person within 5 m of either antenna mid-run ⇒
   STOP on both hosts immediately; mark the cell ABORTED (invalid), re-run
   after clear. Every operator keeps a one-keystroke STOP path at all times.
4. +22 dBm ≈ 160 mW conducted: bodies ≥ 2 m from antennas during cells.
   Duty ≤ 15 % on 51 B cells; ≤ 40 % on the 255 B anchor (thermal + RF
   exposure bound).
5. Power glitch ⇒ reboot ⇒ unlocks cleared ⇒ re-run §1 steps 2–5 before
   continuing (`ID?` catches it in seconds).

## 5. Logistics

- Single trigger per stop: ONE host command per board runs the full 4-mod
  matrix + anchor back-to-back; operators touch nothing until the stop
  completes. Requires extending `tools/e80_bench_ctl.py` with
  `--matrix flrc650,flrc2600,sf7,sf12 --csv <file>` and a
  `--band-override` passthrough (the current tool gates freq to 863–870
  host-side and runs FLRC-650 single-shot only) — follow-up task before
  field day.
- Sync: T0 exchanged by phone at each stop; the cell schedule is
  time-driven on both hosts from T0; RX arms LEN/N per cell from schedule.
- Auto-CSV: append-only per site, one row per cell:
  `site,stop,dist_m,repeat,mod,len,pa,freq_hz,n,sent,recv,per,per_ci_lo,per_ci_hi,rssi,snr,kbps,elapsed_s,timestamp`
  Metadata header rows: GPS TX/RX, heights, ground, weather, `ID?` lines.
  No manual transcription in the field; copy CSVs + logs off daily.
- Walk discipline: TX rig powered down (`ROLE NONE`) between stops; power
  up at stop, checklist, single trigger, wait, power down, walk.

## Verification gates (this document)

- Committed on `feat/e80-stm32-bench`, pushed, ls-remote == HEAD.
- No hardware access, no /dev/ttyUSB*, no firmware changes.
