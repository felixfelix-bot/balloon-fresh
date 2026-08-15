# E80-900MBL-02 — Flash Access Investigation (2026-08-16)

**Verdict: UART ISP is impossible on stock hardware. SWD is the only flash path.**

Investigated live at the bench with Felix pressing RESET while sync-spam
(0x7F) ran on both CH340 ports (`tools/e80_isp_dump.py`, 150 s window,
multiple presses per board) → NO-SYNC on both boards. Root cause is a
hardware design lockout, not operator timing.

## Evidence

1. **Schematic** (`lr2021-eval/pdfs/e80-900mbl-02-spec-id4397.pdf`, OCR + vision):
   - STM32F103CBT6 BOOT0 pin → 10 k pull-down → GND (R2/R6 designation
     varied between passes; value 10 k consistent).
   - No BOOT0 breakout: no header pin, no test point, no jumper anywhere
     on any schematic sheet.
   - No CH340 DTR/RTS → BOOT0/NRST auto-download circuit.
   - SWCLK/SWDIO go through 33 Ω series resistors (R2, R4) to a 4-pin
     connector (J1 on sheet, GND/3V3/SWDIO/SWCLK per best read — pin
     ORDER UNVERIFIED).
2. **Manual** (`e80-900mbl-02-manual-id4396.pdf`): pin tables for J1/J2
   contain no BOOT0, no PA13/PA14. Component #10 "Debug Interface" has no
   documented pin table.
3. **Photos (front + back, Felix 2026-08-16)**: back side shows **four
   unlabeled plated through-holes** in a 2×2 cluster near the USB
   connector / under the STM32 area — separate from the radio pad grid
   and the GPIO edge headers. This matches the unpopulated pads seen in
   the front photo near the MCU. Best candidate for the SWD header.
   Silk labels: NONE on these pads.

## Board map (verified against manual + photos)

| Interface | Contents | Notes |
|-----------|----------|-------|
| J1 header (GPIO) | PA0/1/2/8/11/12/15/PB3 + PB4–PB9/PB11/PC13, 3V3 pin 9 both columns | no BOOT0, no SWD |
| J2 header (radio) | VIN, 3V3, NRST(radio!), BUSY, MISO/MOSI/SCK/NSS, DIO5–DIO11, MCU_TXD/MCU_RXD | NRST = LR2021 radio reset, NOT STM32 |
| 4 unlabeled pads (back, near USB) | presumed GND/3V3/SWDIO/SWCLK | **order unverified** |

Trap: the back-side pad grid labeled NSS/SCK/MOSI/MISO/NRST/DIOx is the
radio module SPI header (J2). It is NOT a debug port. Connecting a probe
there talks to nothing useful (those nets are STM32 SPI1 → LR2021).

## Stock firmware hazards

Demo fw = transparent LoRa bridge: any unrecognized UART bytes are
**transmitted over the air at 850 MHz, +22 dBm** (default `radio_init`:
850 MHz / SF8 / BW125 / sync 0x34). Consequences:

- Never sync-spam / write random bytes to ttyUSB3/4 while stock fw runs.
- Portugal bench rule: TX only 863–870 MHz — stock default 850 MHz is
  out of band; keep bench sessions caged/off-antenna until bench fw
  (TX-inhibited boot) is installed.
- No banner observed on UART at 115200 after RESET (fw is silent until
  it receives bytes).

## Flash path decision

| Path | Status |
|------|--------|
| UART ROM ISP (stm32flash) | DEAD — BOOT0 welded low |
| BOOT0 jumper | DEAD — no such pad |
| **SWD via RP2040 debugprobe** | **CHOSEN** |
| Solder directly to MCU PA13/PA14 | plan C (fine-pitch, avoidable) |

### Prepared (host side)

- `openocd` installed (~/.local/bin).
- `debugprobe_on_pico.uf2` v2.3.1 (official RPi debugprobe) downloaded to
  /tmp — flash onto spare RP2040 (was /dev/ttyACM1, 2e8a:000a) via
  BOOTSEL UF2 copy.
- RP2040 probe wiring (debugprobe "on pico" build): **GP2 = SWCLK,
  GP3 = SWDIO**, any GND. Do NOT connect probe 3V3 to target — both
  boards stay USB-powered (avoid ground-loop/dual-power).

### Pad identification procedure (before soldering, needs multimeter)

4 unlabeled pads, unknown order:
1. Continuity beep each pad vs J1/J2 header GND pin → the beeping pad = GND.
2. Continuity vs header 3V3 pin → that pad = 3V3 (may also beep weakly to GND via rail caps — use the strongest/zero-ohm reading for GND first).
3. Remaining two = SWCLK + SWDIO in unknown order. Solder both, run
   openocd; if no target IDCODE, swap the two signal wires. Swapping the
   two SIGNAL lines is harmless; swapping power is not — hence steps 1–2
   are mandatory.
4. If NO pad beeps to GND → the 4 holes are not the SWD header (possibly
   USB shell mounts) → plan C: solder to R2/R4 (33 Ω) resistor pads, or
   MCU pins 34 (PA13/SWDIO) / 37 (PA14/SWCLK).

### Flash sequence (once wired)

1. Stock dump via SWD first (64 KB) → `E80_stock_dump_<port>.bin`
   (mandatory restore artifact, keep off-host copy).
2. Flash `build-fw/e80_bench.bin` via openocd.
3. After first SWD flash, bench fw ≥ v1.2 jumps to ROM bootloader on its
   own `FLASH` console command → all future re-flashes headless over
   UART, no probe needed (watchdog rule: power-cycle before FLASH if
   `ARM TX` was ever used).

## Related files

- `firmware/e80-stm32-bench/FLASHING.md` — original procedure doc
  (UART section now known dead on stock hw; kept for bench-fw re-flash)
- `tools/e80_isp_dump.py` — working ISP protocol implementation (sync
  spam + GET/GET-ID/READ); useless on stock hw, reusable if a BOOT0
  strap is ever modded in
- `~/repos/lr2021-eval/E80-900MBL-02_CAPABILITY_REPORT.md` — full hw/fw
  capability report
