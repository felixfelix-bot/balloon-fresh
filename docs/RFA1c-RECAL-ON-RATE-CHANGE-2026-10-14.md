# RFA-1c — LR2021 re-calibration after a rate change (260→650 deafness)

Card: **t_0393892c** (RFA-1c: re-calibrate LR2021 after every bitrate change).
Branch: `feat/rfa1c-recal-on-rate-change`. Parent evidence:
`docs/RFA1b-FOLLOWUP-650KBPS-ZEROS-2026-10-14.md` (PR #163, merged into `main`
by the consolidation commit d604f09e).

Status, up front:

- **Code fix + host tests: DONE, green.** `make test-host` 24/24.
- **Acceptance interleave on the patched binary: NOT RUN — the only flash path
  is SWD and the SWD link is dead** (`Error: Error connecting DP: cannot read
  IDR`, §6, and the FLASH-QUEUE row for t_0393892c).
- **Measured change to the flash plan: the deaf end of the 260→650 interleave
  is the RECEIVER.** Re-running the bring-up on the RX alone takes the
  "650 after 260" cells from 0/3 clean to 2/3 clean (3/3 heard); the same re-run
  on the TX alone does not (1/3). The RX board is on **x280, which has no debug
  probe**, so a TX-only flash cannot produce the acceptance matrix.
- **Emulation of the patched firmware (bring-up forced on both ends) is fully
  clean, twice:** all 7 cells `rx_pkts=200 crc_ok=200 crc_bad=0`, no cell
  regressed (§3, runs 4 and 5) — the acceptance target, obtained without the
  flash.

## 1. The defect (already proven, PR #163)

7-cell interleave `650:64, 260:64, 650:64, 260:128, 650:128, 260:255, 650:255`
at PA22, RX local: every 650 cell that directly follows a 260 cell is deaf at
the receiver (`rx_pkts=0`, RSSI exactly 0.0) while the TX reports
`sent_ok=200`. The reverse direction (650→260) is clean in every cell.

## 2. The fix

`src/radio_bench.c`: `radio_bench_apply_cfg()` re-ran the boot bring-up (chip
reset → DCDC/TCXO/LFCLK → calibrate 0x7F → DIO8 IRQ re-arm → re-apply modem
params / fwd PA / freq) **only when the modulation changed** (`cfg->mod !=
cur_mod`). An intra-FLRC bitrate change therefore kept the previous rate's
calibration.

The trigger is now `modem_params_changed(cfg)`:

| change | re-runs bring-up |
|---|---|
| mod (FLRC↔LoRa) | yes (unchanged behaviour) |
| FLRC `br_bps` (BR *and* BW move together: 260 kbps→BW 0.307 MHz, 650→BW 0.740 MHz) | **yes (new)** |
| LoRa `bw_hz`, LoRa `sf` | **yes (new)** |
| PA (`txpow_dbm`), FREQ, payload length | no (deliberate — §5) |

Both ends run this code path: on the RX the cfg is applied from
`radio_rearm_rx()` (bring-up first, then `radio_bench_rx_arm()`), on the TX from
`ROLE TX` / `START` before the first packet. The card's "CALIB_FRONT_END (0x23)
then CALIBRATE (0x22), then re-arm RX" is met in substance by the proven
bring-up branch: it issues `CALIBRATE(0x7F)` — all blocks, the same value the
init chain uses — and the RX re-arm follows. A separate `CALIB_FRONT_END` op was
**not** added: that command is a per-RF-frequency operation
(`lr20xx_radio_common_calibrate_front_end`: "next frequency multiple of 4 MHz"),
the boot chain in `radio_bench_init()` does not issue it either, and the
measured cure (§3/§4) is the reset+recal branch itself.

Host tests: `tests/test_radio_bench_cfg.c` compiles the real `radio_bench.c`
over a capturing fake lr20xx HAL.

```
./build-host/test_radio_bench_cfg   -> ALL PASS
make test-host                      -> 100% tests passed, 0 failed out of 24
tools/: pytest test_rfa1b_pram_matrix.py -> 16 passed
```

RED before the fix (6 assertions across the 3 "must recalibrate" cases; the four
control cases were green on the unfixed binary), GREEN after. New cases:
`test_flrc_bitrate_change_recalibrates`,
`test_flrc_same_bitrate_does_not_recalibrate`,
`test_mod_change_still_recalibrates`,
`test_pa_only_change_does_not_recalibrate`,
`test_lora_bandwidth_change_recalibrates`,
`test_lora_sf_change_recalibrates`,
`test_freq_only_change_does_not_recalibrate`.

Built binary: `build-fw/e80_bench.bin`, `fw=77b2663` (commit 77b26638), sha256
`ae4b589f68f8fad070ab2b05a9f51183b29b5b9443b8e178a4508131e452d9c4`.

## 3. Bench runs (pre-flash, stock fw 5fa7912)

The patched binary could not be flashed (§6), so the fix was **emulated cell by
cell**: `RFA1C_TX_RATE_DETOUR=1` / `RFA1C_RX_RATE_DETOUR=1` prefix a cell whose
bitrate differs from its predecessor with a LoRa hop + `ROLE <role>` on that
board, which re-enters exactly the same bring-up branch the fix triggers on a
rate change (the new tool change is committed on this branch, with tests).

Cells `rx_pkts / crc_bad`; raw JSON + per-cell captures in
`docs/evidence/rfa1c-recal-on-rate-change-2026-10-14/`:

| cell | predecessor | run3 control | run1 TX detour | run2 RX detour | run4 both | run5 both |
|---|---|---|---|---|---|---|
| 650/64 | 650 (prev run) | 200 / 0 | 200 / 0 | **0 / 0** | 200 / 0 | 200 / 0 |
| 260/64 | 650 | 200 / 0 | 200 / 0 | 200 / 0 | 200 / 0 | 200 / 0 |
| 650/64 | 260 | **0 / 0** | **0 / 0** | 199 / 1 | 200 / 0 | 200 / 0 |
| 260/128 | 650 | 200 / 0 | 200 / 0 | 200 / 0 | 200 / 0 | 200 / 0 |
| 650/128 | 260 | **0 / 0** | 200 / 0 | 200 / 0 | 200 / 0 | 200 / 0 |
| 260/255 | 650 | 200 / 0 | 200 / 0 | 201 / 1 | 200 / 0 | 200 / 0 |
| 650/255 | 260 | 201 / 1 | **0 / 0** | 200 / 0 | 200 / 0 | 200 / 0 |

Clean (`200 / 0`) 650-after-260 cells per arm: **control 0/3, TX detour 1/3,
RX detour 2/3, both ends 3/3 + 3/3**. All 260 cells are `200 / 0` in every arm,
so the interleave itself is sound; only the 650 cells move.

Findings:

1. **The control reproduces the published defect on this pair today:** the
   650-after-260 cells read `rx=0, RSSI=0.0` (2 of 3 fully deaf; the third cell
   was heard with a single CRC error, so the defect is not perfectly
   deterministic at the cell level — see 4).
2. **A TX-side bring-up re-run is not the cure** (1/3 clean).
3. **An RX-side bring-up re-run is the cure direction:** 3/3 heard, 2/3 fully
   clean — with the TX left completely stock and un-detoured. The RX's bring-up
   cannot affect the TX, so the deaf end is the **receiver's demodulator
   running on the previous rate's calibration**. (A stale 260-derived
   configuration at the RX hears nothing at all from a 650 burst — RSSI exactly
   0.0 — while the TX's TX-complete IRQ still fires, which is why the failure was
   invisible to TX-side statistics.)
4. **With the bring-up re-run on BOTH ends the matrix is completely clean, twice
   in a row** (runs 4 and 5: all seven cells `200/200/0`, no regression). That is
   the acceptance target, reached by emulating the fix — it is not the acceptance
   run, which needs the patched binary (§6).
5. Per-cell outcomes have a residual nondeterministic component: in the control
   the 650/255 cell was heard once (201 rx, 1 CRC error) where the published run
   had it deaf, and run2's first cell (whose predecessor state was a stale 650
   inherited from run1's deaf cells) was deaf even without a preceding 260 cell.
   The staleness is a property of the chip's *current configuration*, not of a
   single cell boundary — which is exactly why the fix has to fire on the rate
   change itself, and why the acceptance run on the flashed binary remains the
   decisive test.

## 4. Manager's bench A/B (stock fw, console-driven, 2026-10-14 13:19)

Recorded on the card: "CONTROL TX 260->650 direct = DEAF (rx=0). TREATMENT TX
260->lora->650 with ROLE applies = HEALTHY (rx=100 crc_err=1 RSSI -57dBm)".
Consistent with §3 as a single sample; §3.2 shows a TX-only bring-up is not
sufficient in general, so that treatment's health most likely came from the RX
also being re-applied in the session, and the result must not be generalised to
a TX-only flash plan.

## 5. Why PA / FREQ / payload-length changes do not re-run the bring-up

- The LR2021 front-end calibration is per RF frequency, not per rate
  (`lr20xx_radio_common_calibrate_front_end`), and `freq_hz` changes already
  re-apply the cfg through `BENCH_CMD_FREQ` (TX) / `radio_rearm_rx` (RX).
- A chip reset on every `PA`/`FREQ`/`START` re-apply would invalidate the
  12/12-clean continuous-rate baseline and add a reset to every in-band sweep.
- The four "must not recalibrate" host tests pin this.

## 6. Flash path — blocked, physical action required

```
$ ssh x240 'openocd -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg \
    -c "adapter speed 1000; transport select swd; init; mdw 0x08000000 4; resume; exit"'
Info : Using CMSIS-DAPv2 interface with VID:PID=0x2e8a:0x000c, serial=148757200D2D1425
Info : CMSIS-DAP: Interface ready
Info : clock speed 1000 kHz
Error: Error connecting DP: cannot read IDR
```

Same at 100/200/500/1000 kHz and with `reset_config srst_only srst_nogate`. The
probe enumerates and initialises SWD; the target DP never answers — the same
3-wire-link failure as the RFA-1b flash-queue row. The fallback (UART ROM-ISP
through the CH340) is architected dead, and the TX board is IWDG-active so
`FLASH` is refused until a power cycle. No write was attempted.

**To finish the card:** re-seat SWDIO/SWCLK/GND and power-cycle the boards, then
flash `e80_bench.bin` (fw=77b2663) on **both** ends — in particular on the RX
(x280 needs the probe moved to it, or the RX board brought to the probe) — and
run the interleave twice, expecting 7/7 `rx_pkts=200 crc_ok=200 crc_bad=0`.

## 7. Reproduction

```bash
cd firmware/e80-stm32-bench
make test-host                                        # 24/24
RFA1B_RX_PORT=/dev/ttyUSB0 python3 tools/rfa1b_pram_matrix.py \
    --arm none --pa 22 --outdir ~/rfa1c-control \
    --cells 650:64,260:64,650:64,260:128,650:128,260:255,650:255
# emulated fix (bring-up forced on every rate change, both ends):
RFA1B_RX_PORT=/dev/ttyUSB0 RFA1C_TX_RATE_DETOUR=1 RFA1C_RX_RATE_DETOUR=1 \
    python3 tools/rfa1b_pram_matrix.py --arm none --pa 22 --outdir ~/rfa1c-fixed \
    --cells 650:64,260:64,650:64,260:128,650:128,260:255,650:255
```

TX = x240 `/dev/ttyUSB0` (CH340), RX = x280 `/dev/ttyUSB0` (CH340, **115200
baud** on this firmware — not the 2 Mbaud of the older board notes). x280's
`/dev/ttyUSB1` is an unrelated FT232 console (an OpenWrt/Tollgate shell) — never
touch it.
