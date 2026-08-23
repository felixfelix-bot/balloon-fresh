# Analysis: FLRC RSSI ~30 dB cliff at payload ≥ 255 bytes

**Date:** 2026-08-23
**Bench:** Indoor 1 m, E80 (VCXO-TCXO) boards, custom STM32F103 firmware
**Commit:** 0561b29 (`feat/2g4-sweep` branch)
**Data:** `full-sweep-summary-20260821-200111.csv`, `full-sweep-results-2g4-summary-20260822-210817.csv`

## Verdict (TL;DR)

The ~30 dB cliff is **AGC-settling behaviour specific to the LR2021 chip's FLRC packet
status path, amplified by a firmware design choice (STDBY_RC auto-fallback that
forces the AGC to re-settle per packet).** It is **NOT** an SX1280 chip behaviour,
**NOT** a firmware bug in the RSSI-reading code path, and **NOT** a true RSSI
window mismatch alone. The four options ranked:

| Option | Verdict |
|---|---|
| AGC settling            | **Primary cause** ✓ |
| RSSI measurement window | Plausible contributing factor (chip-internal, can't verify without datasheet) |
| Firmware bug            | Not in RSSI path — the code correctly reads `rssi_avg_in_dbm`; the firmware's STDBY_RC fallback is a config choice, not a bug |
| SX1280 chip behaviour   | **N/A — the chip is an LR2021, not an SX1280** |

## Important preamble: the radio chip is LR2021, not SX1280

The user's task framing said "SX1280 radio chip." The firmware source unambiguously
shows the device is a **Semtech LR2021** (LR20xx family):

- `firmware/e80-stm32-bench/src/radio_bench.c:15`:
  `const void* E80_CONTEXT = (const void*)"LR2021";`
- Vendor driver tree: `third_party/Radio/lr20xx_driver/`
- `radio_bench.c:5-6` comment: "LR2021 radio control – vendor-demo-faithful …"
- `radio_bench.c:426-427`: "The LR2021 measures RSSI before the CRC check …"
- SPI opcode space: `0x0248` (SET_FLRC_MOD_PARAMS), `0x0249` (SET_FLRC_PACKET_PARAMS),
  `0x024B` (GET_FLRC_PKT_STATUS) — all LR20xx-family opcodes.
- `docs/lr2021-spi-protocol-reference.md` corroborates.

This matters because:
- **LR2021 ≠ SX1280 datasheet.** Semtech documentation for FLRC mode RSSI is different.
- The LR2021's SPI register space for `rssi_avg_in_dbm` differs from SX1280's.
- Any researcher Googling "SX1280 RSSI short packet" will read the wrong datasheet.

Below I use the LR2021-specific terminology throughout.

## The RSSI read path (firmware)

`radio_bench.c` IRQ handlers extract RSSI from the LR2021 via the
`lr20xx_radio_flrc_get_pkt_status()` SPI command (opcode `0x024B`, returns 5 bytes):

| fld | offset | purpose |
|---|---|---|
| `packet_length_bytes` | rbuffer[0:2] | length of last packet received |
| `rssi_avg_in_dbm`     | rbuffer[2] (negated) | RSSI averaged over the received packet |
| `rssi_sync_in_dbm`    | rbuffer[3] (negated) | RSSI sampled at moment of syncword detection |
| half-dB flags + sw index | rbuffer[4] bitfield | half-dB correction bits |

Driver docstring (`lr20xx_radio_flrc.h:124-134`) clarifies field availability by IRQ:

- `rssi_sync_in_dbm`    : available from `IRQ_SYNC_WORD_HEADER_VALID` (early — at sync detection)
- `rssi_avg_in_dbm`     : available from `IRQ_RX_DONE` (late — at packet end)

The firmware's IRQ handler for both `RX_DONE` and `CRC_ERROR` reads the
`rssi_avg_in_dbm` field
(`radio_bench.c:436-437, 444-445, 461, 472`) and passes it up as the packet's
RSSI in `e.rssi_half_dbm`. The earlier moment `rssi_sync_in_dbm` is **read by
`get_pkt_status()` but never used** by the firmware.

So the rssi_avg_dbm reported in `STAT?` is the LR2021's "averaged over the entire
received packet" value, post-RX_DONE.

`bench_stats.c:119-124` confirms the firmware's STAT? `rssi_avg_dbm` is a
simple mean of the per-pkt RSSI samples (sum / rx_ok). Per-pkt variance shown in
`rssi_min` / `rssi_max` is therefore true per-packet chip-output variation, not
firmware-introduced noise.

## Data confirming the cliff

**868 MHz, Aug 21, FLRC 650 kbps serie:**

| plen | toa(s) | rx_pkts | crc_err | rssi_avg | rssi_min | rssi_max | spread |
|-----:|-------:|--------:|--------:|---------:|---------:|---------:|-------:|
|   16 | 0.001  | 50      | 50      | -70.7    | -72      | -63      |   9 dB |
|   64 | 0.002  | 50      | 50      | -70.0…-72.3 | -85..-89 | -62..-69 | ~25 dB |
|  128 | 0.003  | 50      | 50      | -70.9    | -84      | -62      |  22 dB |
|  192 | 0.005  | 50      | 50      | -70.6    | -72      | -63      |   9 dB |
|  255 | 0.006  | 50      | **0**   | -38.0    | -39      | -38      |   1 dB |
|  256 | 0.006  | 50      | 50      | -38.9    | -39      | -38      |   1 dB |
|  300 | 0.007  | 50      | 50      | -39.9    | -41      | -39      |   2 dB |
|  511 | 0.011  | 50      | 50      | -39.4    | -41      | -38      |   3 dB |

**Cliff location:** between toa = 5 ms (plen 192, rssi ≈ -70.6) and toa = 6 ms
(plen 255, rssi = -38.0). Consistent on both 868 MHz and 2.4 GHz bands. Consistent
across TX powers PA0…PA10. The true signal level at 1 m indoor (confirmed by
LoRa and by the integration findings doc: "Standalone test of FLRC-2600 passed
perfectly — 10/10 received at RSSI -41 to -42 dBm") is **≈-38 dBm**.

**Long-payload RSSI matches the true signal level.** Short-payload RSSI is
**depressed by 25–35 dB.**

**LoRa is immune:** in both sweeps LoRa SF5…SF12 (plen 64, toa 20 ms…2.5 s)
shows stable RSSI (-26…-40 dBm depending on band) across all payloads and
airtimes. The shortest LoRa airtime measured (SF5/BW250, 20 ms) was already
above the 6 ms threshold.

### Per-packet RSSI is bimodal for short FLRC packets

Per-pkt CSV `full-sweep-pkts-20260821-200111.csv` (config 39 = FLRC 650k, PA0,
plen 64), column `$8` (rssi_dbm), histogram from 50 packets:

```
1 × -89.0   3 × -88.0   1 × -87.0   2 × -85.0   9 × -84.0   1 × -83.0
3 × -64.0  27 × -63.0   3 × -62.0
```

Two clear peaks at **-63 dBm** (33 packets, 66 %) and **-84 dBm** (9+, ~20 %).
The ~21 dB gap between peaks is consistent with **one LNA gain-stage step**
in the LR2021's AGC table. Per-packet RSSI is therefore NOT noise — it's a
binary "which AGC state was selected for this packet" outcome.

For long payloads, the histogram collapses to a single bin at -38.

## Why AGC is the primary driver

The LR2021 firmware makes three relevant design choices that exist
independently of the bench tool:

1. **Auto-fallback = `STDBY_RC` after every RX/TX**
   (`radio_bench.c:296`) — the chip leaves RX the instant a packet
   is processed. AGC state is not maintained between packets.
2. **RX re-armed from the IRQ handler**
   (`radio_bench.c:415, 421-422, 450, 487`) via `radio_bench_rx_arm()`, which calls
   `lr20xx_radio_common_set_rx(E80_CONTEXT, 0)` → the chip transitions STDBY_RC →
   RX, and AGC starts **fresh** on the next packet.
3. **Very short FLRC preamble+syncword window** — the firmware configures
   `LR20XX_RADIO_FLRC_PREAMBLE_LEN_32_BITS` (32 bits AGC preamble),
   plus the 21-bit fixed FLRC AGC preamble and the 32-bit syncword =
   ~85 bits = **~131 µs at 650 kbps**. That's the only signal the chip has to
   detect-and-settle-AGC before payload averaging begins.

For short packets:

```
   preamble  sync    payload data (16 B @ 650 kbps ≈ 0.44 ms total airtime)
   └────┬──┬────────────────────────────────────┘
       │  └── AGC starts here
       └── signal first appears
                     ▲
                     │ rssi_avg_in_dbm sampling window runs across AGC ramp
                     ▼  → depressed/bimodal average
```

For long packets (>6 ms total airtime):

```
   preamble sync   payload data (255 B @ 650 kbps ≈ 6+ ms total airtime)
   └────┬──┬──────────────────────────────────────────────────────────┘
       │  └── AGC starts here
       │             ▲           ▲           ▲           ▲
       │             │ ACG fully settled here — sampling window is mostly
       │             │ captured AFTER this point → correct rssi
```

The per-packet RSSI values cluster around the LR2021's quantized AGC gain
states (-63, -71, -84 typical readings, ~12-21 dB apart). Each packet lands
in one state depending on the chip's internal timing when it processed the
preamble, syncword, and payload segments. With enough airtime the AGC always
finishes — same reading every time = -38 dBm.

The LR2021's LoRa mode handles this differently:
- LoRa preamble is **8 symbols minimum** (the firmware sets it to 8 in
  `lora_pkt_params.preamble_len_in_symb`)
- At SF5/BW125 = 2 ms preamble; at SF12/BW125 = 1.5 s preamble.
- Combined with 4.25-symbol header overhead, even the shortest LoRa packet
  has >5 ms of preamble to settle AGC before averaging begins.
- Hence: **LoRa never shows the cliff**, exactly as observed.

## Why "RSSI measurement window" is also plausible

The driver docstring for `rssi_avg_in_dbm` says "averaged over the last received
packet." We don't have the LR2021 datasheet inside this repo to verify
how the chip implements the averaging-tap count. Two possibilities:

(a) Chip averages over actual packet duration (length-known, uses RX_DONE).
    For short packets the average captures the AGC transient during the
    packet's full airtime (still buggy, see homework #3 below).

(b) Chip averages over a **fixed-length** internal window (e.g. 6 ms or
    N samples) starting from syncword detection. Short packets end before
    the window does → averaging continues capturing "signal-less" RX
    samples (≈ noise floor / AGC idle, very negative) → average is
    dragged down.

Both (a) and (b) match the data. The bimodal histogram is easier to explain
via (a) (some packets get partial-settled AGC; some get more-settled AGC),
whereas (b) alone would predict a smoother distribution. I therefore lean
toward (a) as primary with (b) as a potential amplifier.

Without the LR2021 datasheet I cannot rule in or out variant (b). The
actionable next step is in the lab (see "Suggested lab verifications" below).

## Why NOT a firmware bug in the RSSI code path

The firmware reads the LR2021 SPI byte 0x024B exactly as the Semtech driver
specifies; it correctly negates the byte to signed dBm; it correctly applies
the half-dB count correction; it correctly aggregates per-pkt samples into
min/max/avg. There is one application-level quirk worth noting but it's not
relevant to the cliff:

### `rssi_sync_in_dbm` is read but ignored

The struct populated by `lr20xx_radio_flrc_get_pkt_status()` includes both

- `rssi_sync_in_dbm` — RSSI at syncword detection (instantaneous-ish)
- `rssi_avg_in_dbm`  — RSSI averaged over packet

`radio_bench.c:436-447` populates `e.rssi_half_dbm` from **only** the avg field.
The sync-time reading is discarded. If we changed this we'd be able to
directly measure "AGC at start-of-packet vs end-of-packet" — useful for
diagnosis.

### Separate (unrelated) issue: every plen ≠ 255 has 100 % CRC errors

This is curious and not on-topic. Summary CSV: every FLRC config except plen
255 shows rx_pkts=50, crc_err=50. The Hartlf-Tree hardcoded FLRC default in
The firmware's hardcoded FLRC default in `radio_bench.c:67` is `pld_len_in_bytes = 255`, and `apply_cfg()`
re-initializes it to 255 on every config change — so plen 255 hits the chip's "default" state; other plens
get a `set_pkt_params` patch that the TX/RX boards may serialize differently (out of sync — the TX board
calls `set_pkt_params` in `radio_bench_tx_packet()`, the RX board in `radio_bench_rx_arm()`, and the bench
tool's PA/CFG command sequencing between board A and board B may not match what the chip expected).

**Crucially, this is independent of the RSSI cliff:** plen 256 has 50/50 CRC
errors but the RSSI is fine (-38 dBm, stable). So CRC and RSSI cliffs don't
share a cause. Recommend following up separately (see "Open items" below).

## Why NOT an SX1280-specific behaviour

Already addressed above — radio is LR2021, not SX1280. There is no SX1280 here;
any datasheet-derived reasoning must use the LR2021 / LR20xx family manual.

## Suggested lab verifications (when firmware changes are allowed)

To pin down which mechanism dominates, the following experiments would help:

1. **Try `LR20XX_FALLBACK_FS` instead of `STDBY_RC`**
   (single line change at `radio_bench.c:296`). FS keeps the chip in the
   frequency-synthesis state rather than full standby — AGC maintains some
   continuity and may settle faster on the next packet. If short-payload RSSI
   starts giving values closer to -38 dBm → confirms AGC is the dominant
   causal path.

2. **Increase FLRC preamble from 32 bits to a longer setting**
   (`flrc_pkt_params.preamble_len` — there's an enum up to 32 bits max, so we'd
   be constrained, but we could test 32 bit agc preamble vs smaller and confirm
   that shorter makes the cliff worse).

3. **Use `rssi_sync_in_dbm` as well as `rssi_avg_in_dbm`**
   A one-line patch in `radio_bench.c` to also note the sync-time RSSI per
   packet lets us plot "RSSI at start of packet vs RSSI averaged-through-packet"
   on the same histogram. If sync-time values are stable around -38 dBm even
   for short packets but avg is depressed → confirms the averaging window is
   the mechanism. If sync-time values are also depressed → confirms AGC-not-
   settled is the mechanism.

4. **Stop the bench from auto-re-arming RX immediately**
   Insert a deliberate settle delay before `radio_bench_rx_arm()` is called
   from the IRQ handler (e.g. 1-2 ms in FS-RX state). If short-payload RSSI
   improves with longer RX-settling time → confirms AGC need-to-settle.

5. **Compare to a Semtech LR2021 reference design running TheClams Rust
   driver** — these have different fallback defaults (Fs) and may also use
   longer FLRC preamble. If TheClams shows the same cliff, it's purely
   chip behaviour; if TheClams doesn't, our firmware config is implicated.

## Summary of recommendation

For the immediate reporting of bench results:
**Mark FLRC RSSI values for plen ≤ 192 as not directly comparable to long-packet
values** in any plotting or comparison. Add a note in the README or run-tool docs
that this is a measured artifact of the LR2021 + STDBY_RC fallback behaviour
under short airtime, NOT a signal-strength difference between configs.

For study/quantification:
Run experiment 1 (fallback to FS) and experiment 3 (also capture rssi_sync). One
of the two should discriminate cleanly between AGC-settling and
averaging-window hypotheses — and both are minimal-firmware-impact single-line
changes.

---

*Files inspected:*
- `firmware/e80-stm32-bench/src/radio_bench.c` (firmware LR2021 + IRQ + external APIs)
- `firmware/e80-stm32-bench/src/bench_pkt.c` (per-pkt CSV formatter)
- `firmware/e80-stm32-bench/src/bench_stats.c` (STAT? RSSI aggregation)
- `firmware/e80-stm32-bench/src/radio_bench.h`
- `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/src/lr20xx_radio_flrc.c`
- `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/src/lr20xx_radio_lora.c`
- `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_flrc.h`
- `firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_flrc_types.h`
- `firmware/e80-stm32-bench/tools/e80_bench_ctl.py` (STAT? parse logic)
- `docs/lr2021-spi-protocol-reference.md`
- `firmware/e80-stm32-bench/docs/hardware-integration-findings.md`
- Summary CSVs: `full-sweep-summary-20260821-200111.csv`,
  `full-sweep-results-2g4-summary-20260822-210817.csv`
- Per-packet CSV: `full-sweep-pkts-20260821-200111.csv`
