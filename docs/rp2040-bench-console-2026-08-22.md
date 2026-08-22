# RP2040BENCH Console Firmware — HARM-T5 Implementation Report

**Date:** 2026-08-22
**Task:** HARM-T5 (kanban `t_b7c38546`)
**Repo:** `balloon-range-tests`, branch `harm/t5-bench-console`
**Spec:** [`BENCH-CONSOLE-SPEC.md`](./BENCH-CONSOLE-SPEC.md) (normative, frozen v1.0)

## What shipped

A three-layer RP2040 firmware for the cross-board bench console:

| Layer | File(s) | Role |
|---|---|---|
| Console core (host-testable C) | `firmware/rp2040/src/bench/{rp2040_bench,bench_cmd,bench_pkt,bench_payload,bench_stats,buffer,prbs}.c/h` | Vendored E80 trio + role/PA/START/STAT/PKT/BUF state machine. Freestanding C, zero Arduino/pico deps. |
| Raw-SPI radio adapter (Arduino) | `firmware/rp2040/src/bench_radio_sx1280.{cpp,h}` | `bench_radio_ops_t` impl + IRQ service pump. **Verbatim lift of the v4 raw-SPI layer** (`multi_radio_sweep_rx_v4.cpp`), unmodified, plus the harmonization golden §8 deltas (below). |
| Firmware main | `firmware/rp2040/src/multi_radio_bench_console.cpp` | `setup()`/`loop()`: USB CDC console pump, `bench_io_t` seams, golden self-test at boot. |
| Build env | `firmware/rp2040/platformio.ini` → `[env:rp2040-bench-console]` | earlephilhower core, `inject_git_version.py` for `FW_GIT_HASH`. |
| Host tests | `firmware/rp2040/tests/run_bench_tests.sh` | gcc, no board. 5/5 PASS. |

## Why a split architecture (vs. the planned single ~350-LOC file)

The task letter proposed one `multi_radio_bench_console.cpp`. During execution the
console logic (role state machine, PA cap, START/STAT/PKT/BUF, Wilson CI, golden
vectors) grew large enough that folding it into an Arduino-only `.cpp` would
(1) make it untestable without hardware and (2) risk drifting from the E80
reference. The vendored C core runs under `gcc` on the host, so the host tests
exercise the exact state machine that ships on the board. The Arduino glue (main
+ adapter) is thin and does not need host tests. This matches spec §11.1 ("vendor
in verbatim … shared with host tests") and §11.2 ("adapt the harness only").

## Raw-SPI lift: faithful to v4, deltas vs. v4 (golden §8)

The adapter copies v4's `rfWaitBusy`/`rfWriteCmd`/`rfReadIrqStatus`/`rfSetRx`/
`rfReadRxFifo`/`rfClearRxFifo`/`rfCalibrate`/`rfResetAndStandby`/`rfInitForPhaseRX`
and the `GET_FLRC_PACKET_STATUS` (0x024B) / `GET_LORA_PACKET_STATUS` (0x022A)
parsers **byte-for-byte**. v4 is the field-proven sweep RX on this board.

Packet-status parsing was cross-checked against the E80 reference vendor driver
(`lr20xx_driver/src/lr20xx_radio_{lora,flrc}.c`) — the adapter matches it
exactly, and matches the fields E80's `radio_bench.c` emits (LoRa: `rssi_pkt`
= sync RSSI; FLRC: `rssi_avg`). v4's telemetry historically read `buf[4]` for
LoRa RSSI (mislabeled "avg"); the vendor driver and E80 use `buf[5]` (rssi_pkt)
— the adapter follows the vendor/E80 convention.

Deltas from v4, all required by the cross-board golden §8 decision (T1) and
documented per spec §11.1 ("any modification = spec deviation, document it"):

| Register | v4 | Adapter (golden §8) | Reason |
|---|---|---|---|
| `SET_FLRC` 0x0248 byte2 | `0x15` | `0x17` (BT 1.0) | spec §8 golden |
| `SET_FLRC` 0x0249 | `{0x0E,0x7C,0x00,len8}` | `{0x1E,0x7D,len_hi,len_lo}` | CRC-2B ON, 16-bit chip len → 511 B max (spec §6/§8) |
| LoRa sync word | `0x12` (private) | `0x34` | E80 cross-board bench value |
| FLRC sync word base | v4 private | `0x12AD101B` | T1 cross-board golden (Match123 = OR of sync words 1/2/3) |

`rfWaitBusy` uses `digitalRead(PIN_BUSY)` (adapter) vs. raw GPIO in (v4) —
functionally identical, chosen for portability.

## Build & test evidence

```
$ bash tests/run_bench_tests.sh
test_crc16: PASS
test_prbs: PASS
test_bench_pkt: PASS
test_bench_stats: PASS
test_rp2040_bench: PASS
bench tests: ALL PASS
```

```
$ pio run -e rp2040-bench-console
… (see commit metadata for the SUCCESS line / UF2 path)
```

(commit message carries the `pio run` tail.)

## Flash policy

Per `AGENTS.md` / `docs/harmonization-plan-20260821.md`, board flashing is
owned by **HARM-T8** (flash queue, orchestrator approval, board mutex). This
task is **build-verify only** — no board was flashed.

## Open items for HARM-T6 (review)

- Confirm the LoRa sync-word choice (`0x34` vs. a harmonized value) against
  the other two implementations — T6 is the cross-family cold review.
- The `boot=power-on` field in `ID?` is currently always `power-on` (no
  watchdog/reset-cause introspection on RP2040 here); spec §2.1 lists
  `boot=<label>` as board-populated. Documented for the reviewer.
