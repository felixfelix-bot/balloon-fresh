# FW-5b — Radio backend RX (t_41b23f6c)

Module: `firmware/rp2040/src/flrc_range_host_radio.{h,cpp}`
Tests: `firmware/rp2040/host-tests/test_radio.cpp` (TDD: RED → GREEN)
Plan: `host-driven-bench-plan.md` REV-2 §FW-5 (FW-5b split)

## What shipped

The LR2021 RX side of the host-driven firmware backend, bound to the proven
range-test RX firmware (sweep + v2) and the vendored lr20xx_driver:

1. **Continuous RX arm** — `bench_radio_emit_start_rx()` (4 frames):

   | # | frame | bytes | provenance |
   |---|---|---|---|
   | 0 | DIO remap RX_DONE→DIO9 | `01 15 09 00 04 00 00` | flrc_range_rx_v2.cpp L316 |
   | 1 | CLEAR_IRQ | `01 16 FF FF FF FF` | v2 FIX-3 pre-arm |
   | 2 | CLEAR_RX_FIFO | `01 1E` | rfClearRxFifo (TX twin 0x011F) |
   | 3 | SET_RX continuous | `02 0C FF FF FF` | rx_sweep rfSetRx (5 bytes — an extra byte is a CMD_ERROR) |

   `bench_radio_set_rx_bytes(ticks, out)` generalizes frame 3 for any 24-bit
   timeout; `BENCH_RADIO_RX_CONTINUOUS_TICKS = 0xFFFFFF` is the startReceive
   form. Host STOP ends a session (REV-2 STOP semantics → `bench_radio_standby()`
   = STBY_RC `02 00 01`, reinit frame 0).

2. **FIX-3 IRQ discipline** — `bench_radio_rx_service()` + pure classifier
   `bench_radio_classify_rx_irq()`. Classification order per
   flrc_range_rx_v2.cpp L388-445: CRC error (bit 21, `0x00200000`) first, then
   RX_DONE (bit 18, `0x00040000`), else OTHER. On **every** serviced IRQ —
   PKT_OK, CRC_ERR, OTHER — the service step ends with CLEAR_RX_FIFO +
   CLEAR_IRQ + SET_RX re-arm: a serviced-but-undrained FIFO stalls the RX
   chain (the V2 lesson; flrc_range_rx_auto.cpp is frozen, the discipline is
   re-expressed here instead of edited).

3. **Packet read** — `rfReadFifo()` (rx_sweep L110-121): READ_RX_FIFO
   `{00 01}` + payload in ONE CS-low window, no toggle, no status bytes.
   FLRC length = fixed `cfg->pkt_len` unless the chip status reports a sane
   nonzero length at or below it (all corpus RX fw are fixed-len FLRC);
   LoRa length = packet-status byte (explicit header).

4. **Packet-status RSSI, both mods**:
   - FLRC `GET_FLRC_PACKET_STATUS 0x024B` — 7 phase-2 bytes
     `[stat stat len len rssiAvg rssiSync flags]`, 9-bit assembly per
     rx_sweep L158-180: `raw9 = (b[4]<<1) | b[6].bit2`, rssi = −raw9/2.
   - LoRa `GET_PACKET_STATUS 0x022A` — **not in the raw-SPI corpus**; bound
     to the vendored lr20xx_driver `lr20xx_radio_lora_get_packet_status()`
     (+ E80 radio_bench.c L387-396 usage). 8 phase-2 bytes
     `[stat stat crc/cr len snr rssi rssi_signal flags]`; rssi = `-(int16)b[5]`,
     snr = signed `b[4]` in quarter-dB, len = `b[3]`.
   - Mapping derivation: the driver rbuffer equals the raw phase-2 read minus
     the 2 status bytes — verified by aligning the driver's FLRC
     `lr20xx_radio_flrc_get_pkt_status()` field indices against rx_sweep's
     raw 7-byte indexing (identical wire response, two framings).
   - GET_RSSI_INST `0x020B` also wrapped (rx_sweep L182-204): 2 phase-2
     bytes, `raw9 = (b[0]<<1) | (b[1]>>7)` → `bench_radio_read_rssi_inst()`
     for noise-floor sampling.

5. **minor-2 int8 wrap fix** — rx_sweep/v2 compute `-(int8_t)(raw/2)`, which
   wraps POSITIVE once raw/2 > 127 (9-bit RSSI spans 0..−255.5 dBm):
   raw9 = 0x139 → the sweep returns **+100 dBm**. All FW-5b assemblies
   compute in int16 and clamp to **[-127, 0]**, so
   `BENCH_RADIO_RSSI_INVALID (-128)` stays a clean no-reading sentinel
   (REV-2: RSSI marked UNCALIBRATED in the CSV; cage calibration is HW-B3).

6. **Dual-role DIO wiring** — full_init/reinit leave DIO9 mapped to TX_DONE
   (bit 19). `bench_radio_start_rx()` re-maps RX_DONE (bit 18);
   `bench_radio_send_packet()` lazily restores TX_DONE if the last op was RX,
   so a TX burst after an RX session can never spin on a dead line.
   `bench_radio_rx_service()` is called by the FW-8 poll loop on IRQ-line
   rise (or on a tick to self-heal a spurious IRQ).

## Test vectors of record (test_radio.cpp §7-9)

- SET_RX continuous + explicit ticks `01 02 03` pass-through
- CLEAR_RX_FIFO `01 1E`; RX/TX DIO maps `04`/`08` in byte 4
- start_rx 4-frame order + delays (1,1,1,2)
- classify: `0x00040000`→PKT_OK, `0x00200000`→CRC, `0x00240000`→CRC
  (priority), `0x00080000`/`0`→OTHER
- FLRC: rssiAvg 70 → −70; raw9 wrap vector `0x9C`+bit2 → **−127** (sweep
  gave +100); half-dB bit on even byte truncates to the byte; pktLen 51
- LoRa: rssi 70 → −70, snr `0xF2` → −14 qdB, len 51; wrap 156 → −127
- RSSI_INST: 70 → −70; `0x9C 0x80` → −127
- sentinel: `BENCH_RADIO_RSSI_INVALID == -128` distinct from clamp floor

## Gates

- TDD: RED observed (10+ undeclared-symbol errors on the new API), then GREEN.
- Host suite: `make -C firmware/rp2040/host-tests` — 6/6 binaries ALL PASS
  (`-Wall -Wextra -Werror`): test_stats, test_safety, test_cmd, test_bw_codes,
  test_radio (25 tests), test_dispatch (FW-6 WIP, untouched, still green).
- Tools: `python3 -m pytest tools/ -q` — **97 passed**.
- Firmware: `pio run -e rp2040-range-host` clean rebuild — **SUCCESS**
  (17.7 s; HW layer incl. rfReadReg2Phase/rfReadFifo/rx_service compiles
  for RP2040).

## Frozen-file rule honored

`flrc_range_tx_auto.cpp`, `flrc_range_rx_auto.cpp`, `flrc_range_rx_gps.cpp`
untouched (read-only provenance). FW-6's uncommitted dispatch WIP in the
shared worktree untouched and excluded from this commit.
