# E80 Friday Field Demo — Cheat Sheet (2026-08-29, Funchal)

> Repo: `~/repos/balloon-e80bench` (branch `main`, fw `5fa7912`).
> RX = base (Board B, probe `203584200D2D0D42`) · TX = field (Board A, probe `148757200D2D1425`).
> Full context: `docs/RANGE-TEST-FUNCHAL.md`, `docs/RANGE-TEST-PLAN-MINIMAL.md`.

## A. Pre-departure checklist

- [ ] **NTP on BOTH machines:** `timedatectl` → `System clock synchronized: yes`; `date -u` on both within a few seconds of each other.
- [ ] **Boards detected + roles verified:** `python3 tools/e80_detect.py --dual` shows TX + RX with correct probes and `fw=5fa7912`.
- [ ] **Antennas attached to BOTH jacks of each board:** 868 whip → sub-GHz jack (Pin 9), 2.4 G whip (~31 mm) → 2.4 GHz jack (Pin 10). Finger-tight. Never TX into a bare SMA. Dual-attach = the mid-run "⚠️ BAND TRANSITION" swap prompt becomes a no-op.
- [ ] **Power:** laptops charged, power bank for field TX rig, both USB cables per board (CH340 serial + Pico debug probe).
- [ ] **GPS phone tracking ON** (GPX recorder) — needed for stitch: `make range-stitch RX=… GPS=track.gpx`.
- [ ] Cowork window plan: 50 m–436 m → south window · 872 m Achada → west · 1744 m Monte → north.

## B. Base RX setup (Cowork, 3rd floor — do FIRST, before TX walks out)

```bash
cd ~/repos/balloon-e80bench/firmware/e80-stm32-bench
python3 tools/e80_detect.py            # find current port for probe 203584200D2D0D42
make range-rx DIST=<stop> PROBE=203584200D2D0D42 PORT=<port-from-detect>
```

**Join-before-T0 rule:** RX always starts before TX. T0 = next 5-min epoch boundary
(auto-computed, `BOUNDARY_S=300`). Both `make` invocations must land in the SAME
5-min window (start both within ~4 min of each other). Compare the printed
`T0:`/`SESSION_ID:` banners — they must match on both machines.

> **Root-of-repo shortcut (proxy targets):** `tx`, `rx`, `range-tx`, `range-rx`,
> `range-merge`, `range-stitch`, `range-dry-run`, `boat-tx`, `boat-rx` now work
> from the repo ROOT `~/repos/balloon-e80bench` too — they proxy to
> `firmware/e80-stm32-bench/Makefile` and pass `PORT PROBE DIST T0 SESSION_ID
> TX RX GPS` through. So `cd ~/repos/balloon-e80bench && make range-rx DIST=50m
> PROBE=203584200D2D0D42` is equivalent. (Working dir convention stays
> `firmware/e80-stm32-bench/`; the proxy is a convenience.)

## C. Per-stop TX commands (field laptop)

Ports swap on every replug — run `python3 tools/e80_detect.py` first, add `PORT=` if
auto-detect grabs the wrong board. Always `PROBE=148757200D2D1425`.

| Stop | Command (from `firmware/e80-stm32-bench/`) |
|------|--------------------------------------------|
| 50 m  | `make range-tx DIST=50m PROBE=148757200D2D1425` |
| 100 m | `make range-tx DIST=100m PROBE=148757200D2D1425` |
| 218 m | `make range-tx DIST=218m PROBE=148757200D2D1425` |
| 436 m | `make range-tx DIST=436m PROBE=148757200D2D1425` |
| 872 m | `make range-tx DIST=872m PROBE=148757200D2D1425` (Jardim Miradouro da Achada) |
| 1744 m | `make range-tx DIST=1744m PROBE=148757200D2D1425` (Monte village) |

Preset sizes: 50 m=10 cfg (7×868 + 3×2G4) · 100 m=11 (7+4) · 218 m=12 (8+4) · 436/872/1744 m=9 (6+3) each.

## D. T0 procedure (every stop)

1. Arrive, detect ports, position antennas vertical.
2. TX signals readiness via **Signal** → RX starts `make range-rx …` → TX starts `make range-tx …`.
3. **Explicit T0 relay:** when the banner prints `T0: <epoch>`, message that number to
   the other operator via Signal; both confirm identical T0/SESSION_ID before the countdown ends.
4. **`--loop 1` only** (CLI default when invoked directly). Never `--loop 0` in the field —
   a runaway infinite loop burns the stop's schedule and the PA budget.
   Note: the per-stop single pass (default `loop=1`) is fully counted by
   `range-check`; warmup exclusion applies only to multi-cycle runs.

## E. Band-transition fallback

Per-stop presets run all 868 configs first, then the 2G4 group (indices vary per stop —
see §C). With both antennas pre-attached the "⚠️ BAND TRANSITION … SWAP ANTENNA" prompt
(and its 30 s pause) needs no action. **If the 2G4 group is missing from a stop's logs**
(crash, abort, wrong preset loaded): do NOT hot-fix mid-run — rerun the whole stop as a
second cycle (new 5-min T0, same DIST) and keep both runs; note it in the commit message.

## F. Traps — read twice

- **Never STOP a sleeping radio.** If `ID?` says `radio=asleep`, wake it (e.g. `ROLE RX`)
  before sending `STOP`. STOP-while-asleep wedges the console.
- **IWDG sticky reset = power-cycle ONLY.** If the board hits `WDG RESET`, unplug/replug
  USB. SWD/openocd resets do not clear it.
- **NEVER flash tomorrow.** No `make flash`, no FLASH-QUEUE entries, no firmware changes
  in the field. Both boards stay on `5fa7912` or the session is not comparable.
- **After ANY board reset/power-cycle, verify PA armed:** `ID?` must show `pa=22`
  (unlock is `POWER MODE OUTDOOR 2026`; the ctl tool auto-issues + verifies — re-check
  manually if you power-cycled). Indoors/no-unlock caps at +10 dBm:
  `ERR RANGE (INDOOR CAP 0-10 DBM; UNLOCK: POWER MODE OUTDOOR 2026)`.

## G. Per-stop data commit (from repo root, after each stop)

```bash
mkdir -p data/e80-bench/20260829-funchal-<stop>       # e.g. 20260829-funchal-872m
cp firmware/e80-stm32-bench/tx-log.csv data/e80-bench/20260829-funchal-<stop>/   # TX laptop
cp firmware/e80-stm32-bench/rx-log.csv data/e80-bench/20260829-funchal-<stop>/   # RX laptop
git add data/e80-bench/20260829-funchal-<stop>/ && \
git commit -m "data(range): 20260829 funchal <stop> stop logs" && git push origin main
```

Session metadata template: `data/e80-bench/20260829-funchal/session-meta.json`.
Merge/report later: `make range-merge TX=… RX=…` · GPS stitch: `make range-stitch RX=… GPS=track.gpx`.
