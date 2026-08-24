# E80 Bench — Data Handover for Collaborator
2026-08-21 · Felix's E80/STM32 FLRC+LoRa bench · prepared by Hermes (balloon-hermes)

## Where everything lives

Repo: https://github.com/felixfelix-bot/balloon-fresh
Branch: `feat/e80-sweep-results`
(Any file path below resolves as
https://github.com/felixfelix-bot/balloon-fresh/blob/feat/e80-sweep-results/<path>)

Firmware on both boards during ALL datasets below: commit `88a00cf`
(prbs15 payloads + per-packet pcrc16 + console NVIC fix). Boards: 2x E80
(STM32F103 + LR2021-class module), TX/RX roles, SMA antennas ~30 cm apart.
Band: 868 MHz (sub-GHz). Sweep driven by host script over USB serial —
fully reproducible (see Tools).

## Dataset 1 (main) — FLRC large-packet sweep, 2026-08-21 17:56

13 configs x 50 packets = 651 packet rows. FLRC CR3/4, PA 5 dBm, 868 MHz:
LEN {16,64,128,192,255,256,300,384,448,511} @ 650 kbps
+ LEN {384,511} @ 1300 kbps + LEN 511 @ 2600 kbps. GAP 40 ms.

- Report (read first — includes analysis + throughput table):
  full-sweep-report-20260821-175612.md
- Per-config summary: full-sweep-summary-20260821-175612.csv
- Per-packet rows: full-sweep-pkts-20260821-175612.csv  ← the data
- Commits: 70a6e27 (data), 6ff1292 (throughput table appended)

Headline: 100% delivery all 13 configs; PRBS-15 bit errors = 0 on all 651
packets (payload integrity perfect end-to-end at every LEN incl. 511 B).
Throughput: delivered 89.5 kbps max (gap-limited), raw air rate 1.92 Mbps
@ 2.6 Mbps/511B.

## Dataset 2 — full 48-config parameter sweep, 2026-08-21 16:21

LoRa SF5-12 (BW125), PA 0-10 dBm, FREQ 863-870 MHz, FLRC all 8 bitrates
(260-2600 kbps), LEN 64 fixed. 46/48 configs clean; anomalies documented
in-report:
- full-sweep-report-20260821-162143.md
- full-sweep-summary-20260821-162143.csv
- full-sweep-pkts-20260821-162143.csv (~2300 packets)
- Commits: ed63659, corrected 8c11f79

Key numbers: LoRa SNR +~3 dB per SF step (SF5 10.1 → SF8 16.8 → SF12 14.0
dB at this range); PA monotonic -41/-38/-35/-32 dBm @ PA 0/3/6/10; band
RSSI -37.7 @ 863 MHz → -32.2 @ 870 MHz; SF11/SF12 need GAP >= 1.2x ToA.

## Dataset 3 — early 14-config sweep, 14:58 (superseded)

sweep-results-20260821-151147.md/.csv — smaller predecessor; some configs
ran with too-small GAP. Use Dataset 2 instead; kept for history.

## CSV schemas (verified against actual file headers, both datasets)

Per-packet CSV (one row per received packet) — 12 named columns:
idx, label, pkt_idx, session, config, replicate, ts_ms, rssi_dbm, snr_db,
crc_ok, bit_err, pcrc16
- label: human config id, e.g. "FLRC 650k pa5 L511" (mod, bitrate, PA, LEN)
- pkt_idx: packet sequence number within the burst (dedupe key; join with
  session+config)
- ts_ms: host-receive timestamp (ms) — basis of the throughput table
- rssi_dbm: per-packet RSSI (see caveat 2 for the FLRC LEN>=255 step)
- snr_db: LoRa only; 0.0 in FLRC by design (chip exposes no FLRC SNR)
- crc_ok: chip-hardware CRC verdict — see caveat 1, unreliable in FLRC
  on this firmware
- bit_err: PRBS-15 payload bit-error count — THE reliable integrity signal
- pcrc16: app-layer CRC16 of received payload; populated only when the
  chip CRC passed on this fw (0 otherwise — see caveat 3)

Per-config summary CSV — 21 named columns:
idx, label, mod, sf, bw, br, pa, freq, plen, gap_us, toa_s, rx_pkts,
crc_err, rssi_avg, rssi_min, rssi_max, snr_avg, snr_min, bit_err_total,
tx_done, error
(toa_s = computed time-on-air; rx_pkts vs 50 = delivery count;
bit_err_total sums PRBS errors — 0 everywhere in Dataset 1)

## Caveats (know before analyzing)

1. FLRC chip-CRC verdict is unreliable on this pre-fix firmware (root
   cause found: RX sync-match mode Match1; fix under review). In Dataset 1
   most FLRC rows show crc_err=50 despite PRBS bit_err=0. TRUST bit_err.
2. RSSI has a reproducible +~32 dB readout step at LEN>=255 in FLRC
   (-71 -> -39 dBm regime). Compare RSSI only within one regime.
3. pcrc16 = 0 means "chip CRC failed so not populated", not zero CRC.
4. Dataset 1 L511@650k has 51/50 rows (one stray duplicate) — dedupe on
   pkt_idx.
5. FLRC SNR=0.0 everywhere: by design (no FLRC SNR in chip API).

## Tools (reproducibility)

- firmware/e80-stm32-bench/tools/e80_sweep_full.py — the sweep driver:
  auto port detect, role handshake, LEN caps (LoRa 255 / FLRC 511),
  adaptive gap, PRBS verify, emits the exact CSV/MD above. Supports
  --only <substring> to rerun a subset (e.g. --only "k pa5 L").
- Firmware source: firmware/e80-stm32-bench/src/ (console bench_cmd.c,
  prbs.c, bench_pkt.c are the protocol reference).

## What's coming next (don't block on it)

- Post-fix re-run: chip-CRC fix (Match123 + RX FIFO clear) in review;
  after flash, definitive sweep where crc_err should be 0 everywhere —
  supersedes Dataset 1 CRC columns only (RSSI/PRBS/throughput stay valid).
- Cross-board data: harmonization plan (docs/harmonization-plan-20260821.md)
  will add ESP32-C3 and RP2040 boards running the SAME protocol/sweeps;
  CSVs joinable on session,config,pkt_idx.

## Questions / provenance

Every file above is on the branch named above; commit history:
https://github.com/felixfelix-bot/balloon-fresh/commits/feat/e80-sweep-results
Raw per-packet CSVs are the ground truth; reports are derived. Ask Felix
to relay analysis requests — we can rerun any config subset on demand.
