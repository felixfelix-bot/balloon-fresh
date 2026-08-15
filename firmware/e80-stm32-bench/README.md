# e80-stm32-bench — LR2021 bench firmware for E80-900MBL-02

Replaces the E80's stock firmware with a packet-error-rate / throughput bench
node. Two boards on USB: one TX, one RX. Packet generation and stats run
on-board, so results are independent of UART speed.

Stack: STM32F103C8T6 (gcc/CMake, bare-metal superloop) + Semtech lr20xx_driver
v1.3.1 (vendored, demo-proven on this exact hardware) + minimal STM32F1 HAL.

## Safety policy (binding, Felix 2026-08-16)

- **EU / Portugal**: TX clamped to **863-870 MHz** (EU SRD). 900 MHz is
  rejected. `BAND OVERRIDE 2026` exists for lab exceptions only and is logged.
- **Indoor power cap +10 dBm** default. `POWER MODE OUTDOOR 2026` lifts to
  +22 dBm for outdoor range sessions (logged).
- **TX inhibited at boot**: radio asleep, TX requires two-step `ROLE TX` then
  `ARM TX`.
- Antennas confirmed attached (SMA ports). Keep TX-inhibit regardless.

## Build

```bash
# host tests (parser, stats math incl. Wilson 95% CI, payload gen)
make test-host          # 3/3 must pass

# cross build (arm-none-eabi-gcc + CMake)
make                    # -> build-fw/e80_bench{.bin,.hex,.map}
arm-none-eabi-size build-fw/e80_bench
```

Size (2026-08-16): text 17704 + data 112 = **17,816 B flash (27% of 64K)**,
bss **2,680 B RAM (13% of 20K)**.

## Console

USART1 over USB (CH340), 115200 8N1 (921600 tolerated). Line-based,
`OK ...` / `ERR <reason>` replies.

| Command | Meaning |
|---|---|
| `ID?` | chip/driver, role, mod, freq, band, PA, power cap |
| `ROLE TX\|RX\|NONE` | set role (TX needs separate ARM) |
| `ARM TX` | second step of TX enable |
| `MOD loRa <sf5-12> <bw125\|250\|500>` | LoRa |
| `MOD flrc <br_kbps 260\|650\|1300\|2600> <dbm>` | FLRC (+dbm optional) |
| `FREQ <hz>` | 863-870 MHz only (else `BAND OVERRIDE 2026` first) |
| `PA <dbm>` | TX power, capped +10 (indoor) |
| `POWER MODE OUTDOOR <pin>` | unlock +22 dBm (outdoor sessions, logged) |
| `START N=<pkts> LEN=<6-511> GAP=<us>` | TX burst / RX expected-length arm |
| `STAT?` | sent/recv/PER + Wilson 95% CI/RSSI/SNR/elapsed/kbps |
| `STOP` | abort run |
| `BAND OVERRIDE <pin>` | out-of-band freq unlock (logged) |

## Bench run (host side)

```bash
tools/e80_bench_ctl.py --dry-run                 # inspect command script
tools/e80_bench_ctl.py --tx /dev/ttyUSB3 --rx /dev/ttyUSB4
python3 -m unittest test_e80_bench_ctl -v        # host tests (no hardware)
```

Default run: FLRC-650, 868.0 MHz, 1000 x 255 B, +10 dBm. Prints
PER/Wilson-CI/throughput table from both boards' `STAT?`.

Range campaign (docs/RANGE-TEST-PLAN.md §5) — single trigger per stop,
schedule-synced from T0, append-only CSV:

```bash
tools/e80_bench_ctl.py --tx /dev/ttyUSB3 --rx /dev/ttyUSB4 \
    --matrix flrc650,flrc2600,sf7,sf12 --csv range/siteA_S3_r2.csv \
    --site siteA --stop S3 --dist-m 200 --repeat 2 \
    --freq 915000000 --dbm 22 --band-override \
    --gps-tx 52.0123,4.0456 --gps-rx 52.0234,4.0123 \
    --h-tx 1.5 --h-rx 1.5 --ground grass --weather "12C clear" \
    --t0 "2026-08-30 14:05:00"            # add --dry-run to rehearse
```

- LEN=51 uniform, GAP 5000 us FLRC / 1000 us LoRa, N per plan §3 regime
  (10^4 when the previous stop's same-mod Wilson ci_hi <= 2 %, else 10^3;
  SF12 capped at 10^3) — read back from the --csv of earlier stops.
- LEN=255 FLRC-650 anchor cell appended per stop (skip: `--no-anchor`).
- `--band-override` unlocks 410-960 MHz (pin 2026) and verifies the
  `band=`/`pcap=` echo via `ID?` before any TX; +dbm above 10 additionally
  issues `POWER MODE OUTDOOR 2026`. Without it, 863-870 MHz is enforced
  host-side (firmware mirrors).
- Ctrl-C mid-run sends STOP to both boards and marks the stop ABORTED in
  the CSV (plan §4 stop-path). Cells that overrun their schedule slot by
  >120 s abort the stop (TX burst stuck = diagnose, don't continue).

## Flashing

See [FLASHING.md](FLASHING.md) — stock dump FIRST, stm32flash over the CH340
UART, BOOT0 manual entry (hold RESET, release on sync). Not yet executed on
hardware; live-probe verification of the entry method still pending.
