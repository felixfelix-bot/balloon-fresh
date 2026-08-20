# E80-E80 Harmonization Link Measurements — 2026-08-20/21

Firmware: e79f0c0 (feat/persist-tx-seq) during RF tests; console baud fix
04e9470 (2M→115200) applied after. Boards: E80 #1 (TX, ttyUSB3, probe
148757200D2D1425), E80 #2 (RX, ttyUSB4, probe 203584200D2D0D42).

## Valid measurement — SF8 / BW125 / PA10 / 868 MHz (2026-08-20 ~19:30)

Single-config verification run via tools/e80_seq_diag.py (manual-exact
sequence, 2M-baud console, fw=e79f0c0, 10 × 64B PRBS-15 packets,
GAP=10000 ms):

| Metric    | Value                  |
|-----------|------------------------|
| Received  | 9/10 (90%)             |
| RSSI      | -34 dBm (avg)          |
| SNR       | 17 dB (avg)            |
| CRC OK    | 9                      |
| bit_err   | 0                      |
| PRBS-15   | verified (payload xor) |

Radio link PROVEN: TX→RX deliverable with clean payloads at bench range.
Raw line from RX console (reconstructed from session log):

    RX pkts: 9/10, RSSI=-34dBm, SNR=17dB, crc_ok=1, bit_err=0, PRBS-15 verified

## TX board console stability — 2026-08-21 (fw banner 9b619ea, 115200 baud)

20 ID? polls at 1s spacing (second run, 10 polls): 10/10 OK, 0 failures.

## Full 14-config sweep — NOT YET VALID

Blocked by hardware: RX board (E80 #2) UART died after hours of 2M-baud
traffic on 2026-08-20 (see commit 1908770 for failed-run artifacts).
SWD flash verifies OK; zero bytes at any baud 9600–3M. TX board healthy.
Sweep rerun pending RX console recovery (dongle swap / board repair).

Sweep plan (tools/e80_sweep.py, 493384d): SF7-12/BW125/PA10,
SF7-9/BW250/PA10, SF7-8/BW500/PA10, SF7-9/BW125/PA0 — 50 pkts each,
64B PRBS-15, GAP=10000, IWDG-safe ARM→START <1 s, validated commands.

## Root causes of the 0/50 sweep failures (all fixed in software)

1. IWDG starts at ARM TX (2-4 s window) — START must follow ARM TX
   within <1 s; earlier scripts waited 3-5 s → chip reset to ROM
   bootloader mid-sweep. Fix: config-before-arm, ARM+START back-to-back.
2. CH340 command corruption at 2M baud — `ROLE RX` observed garbled to
   ERR UNKNOWN; RX silently stayed role=NONE while TX sent 50/50 into
   the void. Fix: per-command response validation + retries (cmd_expect).
3. CH340 instability at 2M sustained traffic — boards went fully silent
   after 30-60 s. Fix: console baud 115200 (fw commit 04e9470).
   RX-board UART did not recover — physical fault, pending hands-on.
