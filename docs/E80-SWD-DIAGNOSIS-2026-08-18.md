# E80 SWD Diagnosis & UART Control — 2026-08-18

Status: ACTIVE (supersedes the SWD-disable theory in `HANDOFF-SWD-NEXT-STEPS.md` and parts of `E80-FLASH-ACCESS-FINDINGS.md`).

Repo: github.com/felixfelix-bot/balloon-e80bench, branch `feat/e80-stm32-bench`.
Vendor sources: `~/research/e80/mbl02demo/` (mirror of EBYTE demo doc id 4393; PDFs + extracted sources also under `docs/e80-900mbl-02-eval/`).

## 1. Result snapshot

| Item | Status | Evidence |
|---|---|---|
| STM32F103C8T6 (board A) | **ALIVE, running firmware** | UART response `stop tx cw` on ttyUSB3 |
| LR2021 radio | **ALIVE, SPI path OK** | UART reply `LR2021 Version major:1 minor:18` |
| Stock fw config state | 869.85 MHz, SF12/BW125/CR4-5/LDRO, sync 0x12 | verified echo `c3 c3 00 33 d8 db 90` |
| SWD via Pico debugprobe | **FAILS both pin orders** | `Error connecting DP: cannot read IDR` @ 100k–2MHz (true 100k confirmed) |
| Firmware-disables-SWD theory | **DISPROVEN** | source grep below |
| Power-cycle catch (pc-catch.sh, 900 tries) | no catch — consistent with theory being dead | log `~/e80-swd/pc-catch-20260818-003931.log` |

## 2. The theory flip (the important part)

Previous theory: vendor firmware disables SWD after boot → catch it in reset.

Disproven by reading the actual vendor demo source (`mbl02demo/E80_DEMO/E80/Core/Src/stm32f1xx_hal_msp.c:77`):

```c
__HAL_AFIO_REMAP_SWJ_NOJTAG();   // the ONLY SWJ call in the entire firmware
```

`SWJ_NOJTAG` = JTAG off, **SW-DP stays enabled**. No `SWJ_DISABLE`, no GPIO reconfig of PA13/PA14, no RDP. An external LLM's claim that the firmware calls `GPIO_Remap_SWJ_Disable` was a hallucination — verified against the real source.

Corollary: a provably-alive chip running SWD-enabled firmware, failing identically with BOTH pad orders at true 100 kHz → **the SWD signals never reach the MCU. Physical layer problem.**

RESET-hold and power-cycle catching are dead ends. Do not re-run pc-catch.sh.

## 3. Physical suspects (ordered)

1. **GND wire cold joint** (Pico GND ↔ E80 pad 3). Explains both-orders-fail; UART unaffected because CH340 has its own USB ground path. THE critical beep.
2. Cold joints on GP2↔pad1 / GP3↔pad2 (either end).
3. Wrong physical Pico pins — GP2 = left row pin 4 from USB end, GP3 = pin 5. Miscount by one row = this exact failure.
4. Pads 1/2 not actually SWD → plan C: tap 33Ω series-R pads (R2 = SWCLK per schematic OCR; R4/R? = SWDIO, designator uncertain) or MCU pins directly: PA13/SWDIO = pin 34, PA14/SWCLK = pin 37, NRST = pin 7 (LQFP48).

Bench check (3 beeps, continuity mode, assembled rig): Pico GND↔pad3, Pico GP2↔pad1 (square), Pico GP3↔pad2.

## 4. UART control — no flashing needed

`tools/e80ctl.py` (commit 3764fa1) drives stock firmware over the CH340 (board A = `/dev/ttyUSB3`, 115200 8N1). Protocol source-verified from `main.c`:

- `alive` — RF-silent, prints ALIVE on `stop tx cw` reply
- `freq <mhz>` / `longrange <mhz>` / `sens <mhz>` — RF-silent config, echo-verified
- `sleep` / `wake` / `cw-stop` — RF-silent
- `cw-start`, `tx <hex>` — RF emitters, gated behind `--antenna-on`
- `listen [s]` — print RX packets
- ETSI guardrail: refuses non-863–870 without `--force`

HAZARD: any non-command bytes on the UART are TRANSMITTED over LoRa at current power. Never `echo`/type into ttyUSB3; use e80ctl only.

NOTE: config is RAM-only. Power cycle reverts to 850 MHz/SF8/+22 dBm (illegal-EU default) — re-run e80ctl after every replug.

## 5. Zero-flash range test (ready, waiting on board B cable)

- A = TX: `e80ctl.py longrange 869.85` then `e80ctl.py --antenna-on tx <hex>`
- B = RX: `e80ctl.py longrange 869.85` then `e80ctl.py listen 600`
- Both on vendor SF12/BW125 preset, sync 0x12. Antennas required for TX.
- Board B CH340 currently off-USB (its cable powers a Pico) — replug needed.

## 6. Still-planned SWD path (after beeps pass)

Probe: Pico running our swapped-pin debugprobe build (SWCLK=GP3, SWDIO=GP2; UF2 at `tools/debugprobe_swap_pins.uf2`, source github.com/felixfelix-bot/debugprobe-e80swap branch `e80-swap-build`). Wiring as-soldered: GP2→pad1, GP3→pad2, GND→pad3, NO 3V3.

1. Continuity beeps pass → retry `openocd -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg -c "adapter speed 100"` (speed AFTER target cfg — stm32f1x.cfg forces 1000 kHz).
2. Connect → STOCK DUMP FIRST: `~/e80-swd/e80-dump.sh` (dump-only).
3. Then bench fw v1.2+ (RadioLib LR2021 path).

## 7. Corrections to earlier docs

- `E80-FLASH-ACCESS-FINDINGS.md`: "R2/R6 = BOOT0 pulldown" → wrong (R6 = NRST pullup; see `E80-HARDWARE-CLAIMS-AUDIT.md` a076a90). Pad-order claims remain unverified-by-vendor; schematic PDF has no text layer.
- `HANDOFF-SWD-NEXT-STEPS.md` RESET-hold/under-reset sections: moot while firmware keeps SWD enabled — physical fix first. GP1/NRST wiring + `e80-under-reset.cfg` remain valid as fallback if a future bench fw DOES disable SWD.
- Google-LLM memo (2026-08-18): pad order [SWDIO, SWCLK, GND, 3V3] matches our current probe build; SWJ-disable claim = hallucination; UART-ISP/BOOT0-lift = last resort only.
