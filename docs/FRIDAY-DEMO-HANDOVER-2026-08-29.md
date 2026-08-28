# Field Measurement Handover — Friday 2026-08-29, Funchal (E80 Range Demo)

> Audience: you are joining tomorrow morning's field measurement and have never seen this
> project. This page is self-contained. Read it once tonight, keep it open tomorrow.
> Companion docs (shorter/longer): `docs/FRIDAY-DEMO-CHEATSHEET.md` (operator quick
> reference), `docs/RANGE-TEST-FUNCHAL.md` (full viewpoint survey).

## 1. What this is and why tomorrow matters

This is a pico-balloon mesh project: tiny high-altitude balloons that must talk to each
other over long distances with very little power. The radio under test is the LR2021
chip on the E80 dev boards (STM32 + LR2021), which is **dual-band**: it can run 868 MHz
(sub-GHz, long range) and 2.4 GHz from the same board, with one SMA jack per band.
Tomorrow's question: **what is the maximum throughput achievable at each distance, from
50 m out to ~2.9 km, on both bands?** We answer it by parking one board (RX) at a
sea-facing window in Cowork Funchal and walking the other (TX) to six viewpoints,
running a fixed ladder of modem configs (FLRC + LoRa, several bitrates) at each stop.
This is the **first-ever clean field data** for this radio pair — a boat test on
2026-08-26 produced zero usable packets due to clock drift between the two machines —
and the results are the centrepiece of Friday's demo.

## 2. The kit

| Item | Qty | Notes |
|------|-----|-------|
| E80 STM32+LR2021 board "A" (TX/field) | 1 | debug probe `148757200D2D1425`, firmware `5fa7912`, 115200 baud — walks with Felix |
| E80 STM32+LR2021 board "B" (RX/base) | 1 | debug probe `203584200D2D0D42`, firmware `5fa7912`, 115200 baud — stays at Cowork |
| Raspberry Pi Pico debug probe (SWD) | 1/board | plugs alongside the CH340 serial cable |
| 868 MHz whip antenna | 1/board | SMA, sub-GHz jack = **Pin 9** |
| 2.4 GHz whip antenna (~31 mm) | 1/board | SMA, 2.4 GHz jack = **Pin 10** |
| USB cables (CH340 serial + probe) | 2/board | per cheat sheet: "both USB cables per board" |
| RX laptop (base) | 1 | **TBD** — see §11 |
| TX laptop (field) | 1 | Felix's, with power bank |
| Power bank | 1 | field TX rig |
| Phone with GPS/GPX recorder | 1 | tracking ON all morning — needed to stamp stop coordinates |
| Phones with Signal | all | comms via group `balloon-hermes` |

**Both antennas stay attached to both jacks at all times.** The RF path is picked by
frequency, no mid-run swap. Never transmit into a bare SMA.

## 3. Setup on a fresh machine

```bash
git clone https://github.com/felixfelix-bot/balloon-fresh.git
cd balloon-fresh && git checkout main && cd firmware/e80-stm32-bench
pip install pyserial
```

- **Linux:** your user must be in the `dialout` group (`sudo usermod -aG dialout $USER`,
  then log out/in) or the serial ports will be permission-denied.
- **Mac:** you need the CH340 USB-serial driver (a gist with instructions exists — ask
  Felix for the link; URL TBD).
- **If the machine runs `rx-logger.service`** (check `systemctl list-units | grep
  rx-logger`), stop it first — it holds the serial port.

Verify boards + roles (each board shows port, probe, fw):

```bash
python3 tools/e80_detect.py --dual   # expect TX + RX, correct probes, fw=5fa7912
```

## 4. Exact commands

All commands run from `firmware/e80-stm32-bench/` inside the clone. Ports swap on every
USB replug — run `python3 tools/e80_detect.py` first and pass `PORT=` if auto-detect
grabs the wrong board.

### Base RX (Cowork — start FIRST, before TX walks out)

```bash
cd ~/repos/balloon-e80bench/firmware/e80-stm32-bench   # or your clone path
python3 tools/e80_detect.py            # find current port for probe 203584200D2D0D42
make range-rx DIST=<stop> PROBE=203584200D2D0D42 PORT=<port-from-detect>
```

### Per-stop TX (field laptop, walks with Felix) — `PROBE=148757200D2D1425`

| Stop | Command |
|------|---------|
| 50 m | `make range-tx DIST=50m PROBE=148757200D2D1425` |
| 100 m | `make range-tx DIST=100m PROBE=148757200D2D1425` |
| 218 m | `make range-tx DIST=218m PROBE=148757200D2D1425` |
| 436 m | `make range-tx DIST=436m PROBE=148757200D2D1425` |
| 872 m | `make range-tx DIST=872m PROBE=148757200D2D1425` (Jardim Miradouro da Achada) |
| 1744 m | `make range-tx DIST=1744m PROBE=148757200D2D1425` (Monte village) |

Preset sizes (`configs/per-stop/stop-<dist>.json`): 50 m = 10 cfgs (7×868 + 3×2G4) ·
100 m = 11 (7+4) · 218 m = 12 (8+4) · 436/872/1744 m = 9 (6+3) each. ~4–5 min per cycle,
10 packets per config. TX sends N+2 packets per config — the first 2 are warmup and the
RX discards them (`PRIME_DISCARD=2`); this is normal.

### Dry-run rehearsal (serial-free, verified PASS — do this during setup)

```bash
make range-dry-run DIST=50m    # prints the schedule without touching hardware
```

### T0 sync procedure (every stop)

1. **NTP on BOTH machines:** `timedatectl` → `System clock synchronized: yes`; `date -u`
   on both within a few seconds of each other.
2. T0 = **next 5-min epoch boundary**, auto-computed (`BOUNDARY_S=300`). RX always
   starts before TX; both `make` invocations must land in the SAME 5-min window (start
   both within ~4 min of each other).
3. Compare the printed `T0:` / `SESSION_ID:` banners — they must match on both machines.
4. **If a machine can't NTP:** the other operator reads its printed `T0` banner and
   relays the number via Signal; the offline machine then starts with that T0 passed
   explicitly (e.g. `make range-tx DIST=<stop> PROBE=… T0=<value>`; `make range-coord`
   prints the exact copy-paste TX/RX command lines with `T0=`/`SESSION_ID=` filled in).
   The underlying CLI also accepts `--t0 'YYYY-MM-DD HH:MM:SS'`.

### `--loop 1` rule

`--loop 1` ONLY (the default). Never `--loop 0` in the field — a runaway infinite loop
burns the stop's schedule and the PA budget.

### Max power (868 only) — auto, but verify after any reset

868 runs PA22 @ 869.525 MHz; the unlock command is `POWER MODE OUTDOOR 2026`, which the
ctl tool auto-sends and verifies. **A board reset reverts to the +10 dBm indoor cap** —
after ANY reset/power-cycle, check `ID?` shows `pa=22`, or re-run the stop. Indoor-cap
failure signature: `ERR RANGE (INDOOR CAP 0-10 DBM; UNLOCK: POWER MODE OUTDOOR 2026)`.
2.4 GHz runs PA12 @ 2400 MHz (hardware cap, no unlock).

## 5. Data format — the two export schemas

Console `PKT` lines during a run have 25 columns — **ignore them**. The exported CSV
files are the canonical data. There are two formats in the repo; both documented from
actual files:

**A. Distributed range logs (what tomorrow produces).** From
`data/e80-bench/20260826-twomachine-desk/boat-test-rx.csv`, line 1 is a banner comment,
rows are `key=value` pairs:

```
# DISTRIBUTED_RX_MODE t0=2026-08-26T04:05:00 port=/dev/ttyUSB4 probe=203584200D2D0D42 loop=1
STAT,role=RX,sent=0,sent_ok=0,rx=0,crc_err=0,per_x1e6=0,per_ci_x1e6=[0,0],elapsed_s=12.900,kbps=0.000,rssi_avg_dbm=0.000,snr_avg_db=0.000,session=2608252235,config=0,replicate=1,drops=0,gap_us=5000
```

Fields per `STAT` row: `role, sent, sent_ok, rx, crc_err, per_x1e6, per_ci_x1e6,
elapsed_s, kbps, rssi_avg_dbm, snr_avg_db, session, config, replicate, drops, gap_us`
(no separate header line; parse `key=value`).

**B. Desk sweep summary.** From
`data/e80-bench/20260828-022408-maxthroughput-quiet/sweep.csv` — a real 15-column header
(CRLF line endings):

```
br_kbps,len,gap_us,n,tx_sent,tx_ok,rx_ok,crc_err,per_x1e6,rx_elapsed_s,tx_elapsed_s,rx_kbps,tx_kbps,rssi_avg,drops
2600,255,5000,500,500,500,500,0,0,18.6,4.9,54,207,-32.0,0
```

## 6. Data handling

Logs land in `firmware/e80-stm32-bench/{tx,rx}-log.csv` on each laptop. **Never delete
any log.** After EACH stop, from the repo root of whichever laptop has files:

```bash
mkdir -p data/e80-bench/20260829-funchal-<stop>       # e.g. 20260829-funchal-872m
cp firmware/e80-stm32-bench/tx-log.csv data/e80-bench/20260829-funchal-<stop>/   # TX laptop
cp firmware/e80-stm32-bench/rx-log.csv data/e80-bench/20260829-funchal-<stop>/   # RX laptop
git add data/e80-bench/20260829-funchal-<stop>/ && \
git commit -m "data(range): 20260829 funchal <stop> stop logs" && git push origin main
```

- Session skeleton + `session-meta.json` are already committed under
  `data/e80-bench/20260829-funchal/`; per-stop data goes in sibling
  `20260829-funchal-<stop>/` dirs.
- **GPS-stamp every stop:** the session-meta `lat/lon` fields are `null` for the street
  stops — fill them from the phone's GPX track (or stitch later with
  `make range-stitch RX=… GPS=track.gpx`).
- Pushed data is browsable at
  `https://github.com/felixfelix-bot/balloon-fresh/tree/main/data/e80-bench/...`
  (e.g. `.../tree/main/data/e80-bench/20260829-funchal-872m`).
- Merge/report later: `make range-merge TX=… RX=…`.

## 7. Traps and recovery

| # | Trap | DO | DON'T |
|---|------|----|-------|
| 1 | Radio asleep | Check `ID?`; if `radio=asleep`, wake it (e.g. `ROLE RX`) first | **Never send `STOP` to a sleeping radio** — wedges the console (SPI hang) |
| 2 | IWDG after first armed TX | If you see `WDG RESET`, **power-cycle the board** — that's the ONLY fix | Don't expect SWD/openocd reset to clear it; don't chase it with commands |
| 3 | Firmware | Boards stay on `5fa7912` for comparability | **No flashing tomorrow** — no `make flash`, no firmware changes in the field |
| 4 | PA after any reset | Verify `ID?` shows `pa=22`; re-run the stop if not | Assume the unlock survived a reset — it reverts to +10 dBm |
| 5 | Late RX join | RX running **before** T0, every stop | Join late — first configs are lost |
| 6 | Band transition 868→2.4G | With both antennas pre-attached, the "⚠️ BAND TRANSITION" prompt is a no-op | Hot-fix if 2G4 configs are missing from a stop's logs — rerun the whole stop as a second cycle (new T0, same DIST), keep both runs, note in commit |
| 7 | Port conflicts | Stop `rx-logger.service` first if the machine runs it | Let two processes hold the CH340 port |
| 8 | Looping | `--loop 1` | `--loop 0` (infinite) in the field |
| 9 | Antennas | Both whips attached, finger-tight, vertical | TX into a bare SMA; swap antennas mid-run |
| 10 | Warmup packets | Expect N+2 sent, 2 discarded | Panic about the +2 |

**Recovery ladder** (try in order, stop when the board responds):
1. **SWD reset** via the Pico debug probe (openocd) — for ordinary console wedges.
2. **USB replug** (port may renumber — re-run `e80_detect.py`).
3. **Full power cycle** (unplug everything) — required for sticky IWDG.
After ANY of these: re-verify PA (`pa=22`, §4) before resuming.

## 8. Schedule + viewpoints

Setup at Cowork at T−30 min (boards, antennas, NTP check, `e80_detect --dual`,
`range-dry-run`). Base = Cowork Funchal, Rua das Mercês 41, 3rd floor sea-facing,
32.6513123, −16.9116552, roof ~35 m. RX window moves: south for 50–436 m, west for
Achada, north for Monte. ~30 min slack is built in.

| Time | Stop | DIST preset | Actual dist | Location (coords) | Elev | LOS verdict | Travel |
|------|------|-------------|-------------|-------------------|------|-------------|--------|
| 0:00 | 1 | 50 m | 50 m | Avenida do Mar, outside building (GPS TBD) | ~30 m | Trivial/short-range, south window | Walk out front door |
| 0:06 | 2 | 100 m | 100 m | Av. do Mar, past marina (GPS TBD) | ~30 m | Short-range, south window | Continue along seafront |
| 0:14 | 3 | 218 m | 218 m | Av. do Mar / Rua do Gomes, port area (GPS TBD) | ~30 m | Short-range, south window | ~500 m total seafront walk |
| 0:24 | 4 | 436 m | 436 m | Parque da Avenida do Mar (GPS TBD) | ~30 m | Short-range, south window | 4 street stops ≈ 20–30 min total |
| 0:45 | 5 | 872 m | ~1.0 km | Jardim Miradouro da Achada (32.6573, −16.9196) | 100 m | **CLEAR LOS**, −3.7° depression onto base | ~15 min walk / short ride; RX → west window |
| 1:20 | 6 | 1744 m | ~2.87 km | Monte village (32.6763, −16.9038) | 550 m | **CLEAR LOS**, −10.2°, looks down into Funchal bowl | Taxi ~10 min or cable car up; **cable car back**; RX → north window |

Desk-validated priors for context: 574 kbps goodput (FLRC 2600/L511), FLRC-650
sensitivity −91.5 dBm, FLRC-260 predicted ~1.4 km @ PA22; 2.4 GHz link budget ~19 dB
worse than 868 — expect 2.4 G to fall off first as distance grows.

## 9. Comms + roles

- **Signal group `balloon-hermes`** is the single channel. All coordination, T0 relays,
  and go/no-go calls happen there.
- **Felix** — hardware, hands, and walking; physically carries the TX board to each
  viewpoint.
- **Felix's AI agent (on the TX laptop)** — runs the actual TX commands; talk to it via
  the Signal group.
- **You (helper)** — primary assignment: **base RX station operator at Cowork** (run
  `range-rx` per stop, watch banners, commit data), or second pair of hands on the TX
  side if that's where you're needed. Confirm your assignment in Signal tonight.

## 10. Links

- GitHub repo: https://github.com/felixfelix-bot/balloon-fresh
- Operator cheat sheet: `docs/FRIDAY-DEMO-CHEATSHEET.md` →
  https://github.com/felixfelix-bot/balloon-fresh/blob/main/docs/FRIDAY-DEMO-CHEATSHEET.md
- Viewpoint survey: `docs/RANGE-TEST-FUNCHAL.md` →
  https://github.com/felixfelix-bot/balloon-fresh/blob/main/docs/RANGE-TEST-FUNCHAL.md
- Session metadata: `data/e80-bench/20260829-funchal/session-meta.json` →
  https://github.com/felixfelix-bot/balloon-fresh/blob/main/data/e80-bench/20260829-funchal/session-meta.json
- This handover (after push):
  https://github.com/felixfelix-bot/balloon-fresh/blob/main/docs/FRIDAY-DEMO-HANDOVER-2026-08-29.md

## 11. Open items (as of writing)

- **Base machine TBD.** DQ05 (the usual base laptop) is currently offline. Fallback: any
  laptop with `python3` + `pyserial` + a repo clone (§3). Mac needs the CH340 driver
  gist — link TBD, ask Felix.
- **Monte inclusion TBD.** Stop 6 (~2.87 km, cable car) is schedule-dependent — decide
  on the morning based on time and weather. Everything through Achada is the safe
  minimum.
