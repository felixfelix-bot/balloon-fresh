# HANDOFF — E80 bench: next steps from here (2026-08-16)

> **SUPERSEDED (2026-08-18):** the SWD-disable theory below is disproven — vendor
> firmware calls only `__HAL_AFIO_REMAP_SWJ_NOJTAG()` (SWD stays enabled). Current
> state of play: `docs/E80-SWD-DIAGNOSIS-2026-08-18.md`. UART control tool: `tools/e80ctl.py`.

Read `docs/E80-FLASH-ACCESS-FINDINGS.md` first (why we're here).
State: investigation DONE, SWD path CHOSEN, host tools READY.
Blocked ONLY on: identifying + wiring the 4 unlabeled debug pads.

## Who does what next

| Step | Actor | Action |
|------|-------|--------|
| 1 | Bench (Felix) | Multimeter beep-test on 4 unlabeled pads (back side, 2x2 cluster near USB) |
| 2 | Bench | Solder 4 wires or 4-pin header into pads |
| 3 | Bench | Wire RP2040 probe: GP2→SWCLK, GP3→SWDIO, GND→GND. NO 3V3 link |
| 4 | Host | Flash debugprobe onto RP2040, run openocd dump + flash (below) |

## Step 1 — pad identification (MANDATORY before solder)

Pads are unlabeled; order unknown. Power ID must precede wiring:

1. DMM continuity, black probe on any header GND pin (J1/J2 "GND").
2. Red probe on each of the 4 pads → the one that beeps = **GND**.
3. Black probe on a header 3V3 pin; red probe on remaining 3 pads →
   the beeper = **3V3** (weak beep through regulator caps is normal;
   GND beep in step 2 is the strong one).
4. Remaining 2 = SWCLK + SWDIO, order unknown → resolved in software
   (swap if openocd sees no target; swapping SIGNALS is harmless).
5. If NO pad beeps to GND → pads are not the SWD header → plan C:
   solder to R2/R4 (33 Ω) pads feeding SWCLK/SWDIO (schematic sheet 1,
   near MCU right side).

## Step 3 — probe wiring (RP2040 = debugprobe "on pico" build)

```
RP2040 GP2  ──► E80 SWCLK   (through 33 Ω on-board, fine)
RP2040 GP3  ──► E80 SWDIO    (33 Ω on-board, fine)
RP2040 GND  ──► E80 GND
RP2040 3V3  ──✖ NOT CONNECTED (both USB-powered; no dual-power)
```
Both E80 and RP2040 stay plugged into the bench PC USB.

## Step 4 — host procedure (commands verified-ready)

### 4a. Flash the probe firmware onto RP2040

```
# hold BOOTSEL on the RP2040 while plugging USB → mounts as RPI-RP2
cp tools/debugprobe_on_pico.uf2 /media/$USER/RPI-RP2/
# board re-enumerates as a CMSIS-DAP probe (lsusb: 2e8a:000c)
```
UF2 = official raspberrypi/debugprobe v2.3.1, `debugprobe_on_pico`
build (GP2/GP3 SWD pins). Kept in repo at tools/debugprobe_on_pico.uf2.

### 4b. Stock dump FIRST (restore artifact — do not skip)

```
openocd -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg \
  -c "adapter speed 2000" \
  -c 'init' \
  -c 'dump_image E80_stock_dump_A.bin 0x08000000 0x10000' \
  -c 'reset run' -c 'shutdown'
```
Expect log: "target voltage" + IDCODE (0x1ba01477 for F1).
64 KB = full flash of F103CBT6. Copy dumps off-host.
Repeat for board B → E80_stock_dump_B.bin.

If "DP initialisation failed" / no IDCODE → swap the two signal wires
on the E80 end, retry (step 1.4).

### 4c. Flash bench firmware

```
openocd -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg \
  -c "adapter speed 2000" \
  -c 'init' \
  -c 'program firmware/e80-stm32-bench/build-fw/e80_bench.bin 0x08000000 verify' \
  -c 'reset run' -c 'shutdown'
```
Then serial console on the board's ttyUSB (115200) — bench fw ≥ v1.2
supports `FLASH` cmd → all future re-flashes headless over UART, no
probe needed (FLASHING.md).

## Port map (bench, 2026-08-16)

| Device | Port |
|--------|------|
| E80 board A (CH340) | /dev/ttyUSB3 |
| E80 board B (CH340) | /dev/ttyUSB4 |
| RP2040 → probe after 4a | new /dev/ttyACM* + CMSIS-DAP USB |

## RF safety (until bench fw installed)

Stock fw = transparent bridge: unknown UART bytes → LoRa TX at
850 MHz +22 dBm (out of PT 863–870 band). No random writes to
ttyUSB3/4. Keep antennas off / caged. Bench fw boots TX-inhibited.

## Artifacts in this repo

- `docs/E80-FLASH-ACCESS-FINDINGS.md` — full investigation + evidence
- `tools/e80_isp_dump.py` — STM32 UART ISP protocol (dead on stock hw,
  reusable post-mod)
- `tools/debugprobe_on_pico.uf2` — probe firmware (v2.3.1 official)
- `firmware/e80-stm32-bench/FLASHING.md` — re-flash procedure (v1.2+)
- Related: `~/repos/lr2021-eval` (vendor PDFs, demo src, capability
  report; its own git repo)
