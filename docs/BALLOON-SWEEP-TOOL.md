# balloon_sweep.py — cross-board host sweep tool (HARM-T2)

`tools/balloon_sweep.py` generalizes `firmware/e80-stm32-bench/tools/e80_sweep_full.py`
to all three bench board families, implementing the host-side duties of
[`BENCH-CONSOLE-SPEC.md`](BENCH-CONSOLE-SPEC.md) v1.0 (§6 LEN caps, §7 GAP
floor, §9 frequency plan, §11.6 pre-hardware enforcement).

## Board families

| family  | tag          | console          | reset                          |
|---------|--------------|------------------|--------------------------------|
| `e80`   | `E80BENCH`   | CH340 `/dev/ttyUSB*` | openocd SWD `reset halt; resume` |
| `esp32` | `ESP32BENCH` | USB-CDC `/dev/ttyACM*` | `esptool` hard reset |
| `rp2040`| `RP2040BENCH`| USB-CDC `/dev/ttyACM*` | `picotool reboot -f` |

ttyACM boards open through `BoardSerial` (`tools/board-serial.py`), so the
BALLOON board lock and tracking stay enforced. The E80 CH340 bridge is not
lock-managed and opens as a plain pyserial port (as in `e80_sweep_full.py`).

## Spec enforcement happens BEFORE hardware

`--dry-run` (and the automatic pre-flight inside every real run) plans the
pair and refuses anything the spec forbids, before a single port is opened:

* **LEN** ≤ 255 (LoRa) / ≤ 511 (FLRC) — spec §6
* **GAP** ≥ 40 ms whenever LEN > 256 — spec §7
* **FREQ** inside the per-board plan and the *pair intersection* — spec §9:
  * `E80BENCH`: 863–870 MHz
  * `ESP32BENCH`: 863–870 MHz + 2400–2480 MHz
  * `RP2040BENCH`: 863–870 MHz + 2440 MHz (point)

Invalid requests exit with `REFUSED (pre-hardware, spec enforcement): ...`
listing every reason (labels `LEN`/`GAP`/`FREQ`).

```console
$ tools/balloon_sweep.py --tx e80 --rx esp32 --session 2608212000 \
    --only 0 --dry-run   # config 0 = SF5 BW125 @ 868 MHz — allowed
plan OK: PlannedPair(tx=e80/E80BENCH, rx=esp32/ESP32BENCH, session=2608212000, configs=1)
```

A genuinely refused pair (E80 has no 2.4 GHz radio — §9):

```console
$ python3 - <<'EOF'
import sys; sys.path.insert(0, "tools")
import balloon_sweep as bs
cfg = [dict(mod="flrc", br=650, pa=5, freq=2_440_000_000, plen=16, gap=10000, label="2G4 try")]
try:
    bs.plan_pairs("e80", "rp2040", cfg)
except bs.ConfigError as e:
    print("REFUSED:", e)
EOF
REFUSED: [2G4 try] FREQ 2440000000 not allowed for pair E80BENCH<->RP2040BENCH (spec S9)
```

## Handshake

Each board is opened, then `ID?` is sent; the reply tag must match the
requested family (`E80BENCH`/`ESP32BENCH`/`RP2040BENCH`, spec §2.1/§10).
A board answering with a *different* tag is a hard error — the tool never
radio-probes a foreign board.

## Data products

Identical shape to the e80 tool, plus `<prefix>-meta.json`:

* `<prefix>-summary.csv` — one row per config (`SUMMARY_FIELDS`)
* `<prefix>-pkts.csv` — one row per received packet (`PKT_FIELDS`; the 25th
  PKT column `pcrc16` stays empty when a board emits the older 24-column
  rows — spec §3 tolerance)
* `<prefix>-report.md` — human summary table
* `<prefix>-meta.json` — tx/rx family+tag, session id, tool/spec version

**Join keys** for cross-run analysis: `session`, `config`, `pkt_idx`
(`replicate` disambiguates re-runs of one config).

## Tests

```console
$ python3 -m pytest tools/test_balloon_sweep.py -q        # 24 tests
$ cd firmware/e80-stm32-bench && make test-host           # ctest incl. test_balloon_sweep_python
```

Golden transcripts live in `tests/golden/`; their provenance (real t5a
formatter output, recorded PRBS-doc lines, recorded STAT lines from the
e80_bench_ctl suite) is documented in the test module docstring.
