# FW-5a — Radio backend TX + band matrix (t_75a5ad0e)

Module: `firmware/rp2040/src/flrc_range_host_radio.{h,cpp}`
Tests: `firmware/rp2040/host-tests/test_radio.cpp` (TDD: RED → GREEN)
Plan: `host-driven-bench-plan.md` REV-2 §B1

## What shipped

The LR2021 TX backend for the host-driven firmware, rebuilt from the proven
range-test backends but **band-parameterized** instead of HF-hardwired:

1. **Band matrix** — `bench_radio_band_for_freq()`. `is_hf = freq_hz > 1.5 GHz`
   drives every band-dependent wire byte:

   | field | LF | HF | provenance |
   |---|---|---|---|
   | `rx_path` (0x0201) | 0x00 | 0x01 | dual_radio_gps_sweep_tx.cpp step 4 |
   | `fe_freq` bit 15 (0x0123) | 0 | 1 (HF-only) | dual_radio step 5 |
   | `tx_path` (0x0202 3B) | 0x00 | 0x01 | multi_radio_sweep_gps_v4.cpp L786 |
   | `pa_sel` (0x0202 7B byte2) | 0x00 | 0x80 | multi_radio v4 L791 [LR2021Raw setPaConfig(LF)] |

2. **Full cold init** — `bench_radio_emit_full_init()`: sweep backbone
   (reset → `{01 11 00 00}` → `{01 28 01}`) + dual_radio matrix
   (pkt type → RF freq → RX_PATH → CALIB_FRONT_END → CALIBRATE → MOD/PKT
   block → TX_PATH → PA select → TX_PARAMS → fallback → DIO routing → IRQ
   mask → CLEAR_IRQ). 17 frames, byte-exact per source files.

3. **Band-aware reinit** — `bench_radio_emit_reinit()`: REV-2 B1 replaces
   `rfSwitchBitrate()` (which was "INSUFFICIENT"): STDBY_RC → RX_PATH →
   CALIB_FRONT_END → MOD/PKT block → CALIBRATE → TX_PATH → PA select →
   TX_PARAMS → `{02 0B 02}`. 11 frames. CALIB_FRONT_END is re-applied on
   every reinit because a FREQ change with a stale front-end calib is the
   core B1 hazard.

4. **set_tx carries the FW-4 chip timeout** — `bench_radio_tx_timeout_ticks()`:
   `ticks = ms * 32768 / 1000` (vendored lr20xx_driver
   `convert_time_in_ms_to_rtc_step`), clamped to the 24-bit SetTx register.
   The sweep backend's `rfSetTx()` hardcoded `{02 0D 00 00 00}` (continuous);
   the new `rfSetTx(ticks)` takes ticks from `bench_safety_tx_timeout_ms()`
   — FW-4 outputs [100, 60000] ms map to [3276, 1966080] ticks, never 0.

5. **Burst spin** — `bench_radio_send_packet()`: CLEAR_IRQ → CLEAR_TX_FIFO →
   WRITE_TX_FIFO (single-batch) → SET_TX(ticks) → poll IRQ pin, 500k budget
   (flrc_range_tx_sweep.cpp L378-398, verbatim).

6. **Transport** — SPI0 @ 20 MHz, CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8, all
   single-batch transfers; copied from the proven sweep backend.

## Testable seam

The init/reinit sequences are **pure**: they emit frames to a
`bench_radio_cmd_sink_t` (frame + provenance inter-command delay). The
firmware sink writes SPI + delays; `test_radio.cpp` records and asserts the
exact 17/11-frame sequences, band bytes for LF (868 MHz) and HF (2440 MHz),
LDRO bytes for SF7/250k vs SF12/125k, the tick conversion, and an invariant
that LF sequences never contain HF-hardwired bytes. 15 test groups, all
green; FW-4 TU is linked into the test so ticks are verified against real
`bench_safety_tx_timeout_ms()` outputs.

## Deliberate deltas vs provenance (flag for HW-B2)

- **Packet type**: sweep TX/RX pair uses FLRC=0x05; dual_radio pair uses
  FLRC=0x04 ("proven" per in-file comment). B1 binds the matrix to
  dual_radio → **0x04**. Both ends of the bench run this backend, so the
  pair stays self-consistent.
- **PA select on LF**: lora_868_tx.cpp uses 0x80 at 868 MHz; B1 binds v4
  semantics (**LF=0x00**). One-line change in `bench_radio_band_for_freq`
  if HW-B2 loopback disagrees.
- **TX power byte**: sweep helper `(uint8_t)(dbm*2.0f+0.5f)` is a half-dB
  off for negative integer dBm; this module uses exact `dbm*2`
  two's-complement (-18 dBm → 0xDC).
- **FLRC rate sentinel**: sweep `rfSetBitrate` silently defaulted unknown
  rates to 0x00 (2600 kbps); the parameterized table returns
  `BENCH_RADIO_FLRC_BR_INVALID` and `bench_radio_cfg_valid()` rejects it —
  the protocol accepts exactly the 8 rates.

## Verification

- `make -C firmware/rp2040/host-tests` → test_stats/test_safety/test_cmd/
  test_bw_codes/test_radio ALL PASS (g++ -Wall -Wextra -Werror)
- `python3 -m pytest tools/test_range_bench_ctl.py -q` → 88 passed
- `pio run -e rp2040-range-host` → SUCCESS (hardware TU compiles under
  Arduino; module not yet called by the main loop — that wiring is FW-6)

## Next

FW-6 wires the radio into the command dispatcher (MOD/FREQ/PA/LEN →
reinit; per-packet SET_TX/STOP/RST), FW-7 is the engine layer.
