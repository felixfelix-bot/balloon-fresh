# Worktree Notes — feat/host-driven-bench

> **This file supersedes the tracked `AGENTS.md` FOR THIS WORKTREE ONLY.**
> The tracked `AGENTS.md` belongs to the tollgate track (ESP32-S3 board map,
> esptool flash flow, Cashu wallet, captive portal). Nothing in that file
> applies to this worktree. Do **not** modify `AGENTS.md` — it is shared
> across tracks. Read this file instead.

## Branch & Base

- **Branch:** `feat/host-driven-bench`
- **Base:** `range-tests@655d094` (NOT main — LR2021 raw-SPI radio code to
  port lives only on `range-tests`)
- **Worktree path:** `~/worktrees/host-driven-bench`
- **Remote:** `github` → `felixfelix-bot/balloon-fresh`

## Boards in This Worktree

| Role | Board | Identification | Notes |
|------|-------|----------------|-------|
| DUT | Raspberry Pi Pico (RP2040) | `/dev/serial/by-id/usb-Raspberry_Pi_Pico_E663977F242D-if00` | Serial ID suffix `E663977F242D` — referred to as "F242D" |
| Bridge | ESP32 (Espressif JTAG-serial ACM) | `ttyACMx` (port changes on replug) | Banner: `=== ESP32 UART Bridge v7 ===` |

**Port resolution:** Always use the `/dev/serial/by-id/` path for the Pico.
Bridge port must be re-census'd after every BOOTSEL cycle (ports move on
replug). Do NOT edit `tools/board_serial.py` `PORT_TO_RESOURCE` — re-verify
and re-census instead (per plan gotcha #2 and REV-2 minor).

## What NOT to Do Here

- **Never use `idf.py` or `esptool`** — there are no ESP32-S3 targets in this
  worktree. The ESP32 here is a UART bridge, not a build target.
- **Never flash via `idf.py -p /dev/ttyACMx flash`** — the ESP32 bridge firmware
  is already flashed (v7 pass-through). It is NOT re-flashed from this worktree.
- **Do not modify the tracked `AGENTS.md`** — it is shared with the tollgate
  track. This file (`docs/WORKTREE-NOTES.md`) is the override for this worktree.
- **Never edit these files** (committed conflict markers — untouchable):
  - `firmware/rp2040/src/flrc_range_tx_auto.cpp`
  - `firmware/rp2040/src/flrc_range_rx_auto.cpp`
  - `firmware/rp2040/src/flrc_range_rx_gps.cpp`

## How to Flash the Pico

The RP2040 is flashed via the ESP32 bridge's BOOTSEL command or directly via
`picotool`. The build environment `[env:rp2040-range-host]` uses the
earlephilhower RP2040 Arduino core with picotool upload protocol.

```bash
# Build + upload via PlatformIO (uses picotool through the bridge):
pio run -e rp2040-range-host -t upload

# Or flash a .uf2 directly via picotool:
picotool load firmware/rp2040/.pio/build/rp2040-range-host/firmware.uf2
```

If the bridge is unresponsive, hold the Pico BOOTSEL button, plug USB, and
copy the `.uf2` to the mass-storage device that appears.

## ESP32 Bridge Watchdog (Gotcha)

The ESP32 bridge v7 auto-resets the RP2040 after **30 s of UART silence**.
Firmware running on the Pico MUST print a heartbeat line on `Serial1`
(≤10 s period) or long RX listens / idle waits get the board reset out from
under the host. This is a hard requirement baked into the plan (FW-9).

## Build & Test

```bash
# Firmware host-side unit tests (pure C++ modules, no Arduino, no hardware):
make -C firmware/rp2040/host-tests

# Host script tests (Python, no hardware):
python3 -m pytest tools/test_range_bench_ctl.py -q

# Firmware build check:
pio run -e rp2040-range-host
```

## Reference

- **Plan + grill resolutions:** `/home/c03rad0r/host-driven-bench-plan.md`
  (REV-2 section is binding)
- **Protocol spec:** Plan §1 (Console Protocol v1)
- **Parent task:** Kanban `t_c22bdaa9` on board `host-driven-bench`