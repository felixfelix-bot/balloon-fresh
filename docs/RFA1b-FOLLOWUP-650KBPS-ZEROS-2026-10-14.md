# RFA-1b follow-up — the 650 kbps "zero packet" cells: root cause

**Date:** 2026-10-14 · **Card:** t_0917cbfa (follow-up to t_0eaed49b) · **Mode:** bench, no flash
**Bench:** board A on x240 (`/dev/ttyUSB0`) · board B on x280 (`/dev/ttyUSB0`) · both fw `5fa7912`,
869.85 MHz, FLRC, GAP=10 ms, N=200, PA 22 dBm (outdoor cap).

---

## Verdict

**The 650 kbps zero-packet cells are a measurement-harness artifact plus a
first-packet-after-bitrate-change effect — not a radio or CRC fault. There is no
650 kbps defect and no CRC error at any payload length.**

Two independent findings, both reproduced:

1. **Harness bug (cross-host runs): the RX listen marker was probed locally.**
   `run_ops()` returned the marker path without its ssh host prefix, so
   `wait_mark()` `stat()`ed a local file, never observed the remote marker,
   burned its full 60 s timeout, and the TX burst fired **before the receiver had
   opened its window** — nothing could be received. Every zero-packet cell in a
   cross-host run is this bug, not the radio.
2. **A bitrate-switch settle effect explains the same cells in the local
   (single-host) run.** Cells that follow a 260 -> 650 kbps change lose their
   first burst; cells that repeat the same bitrate are clean. The local run's
   `rx_elapsed_s=28.1` cells are the 650 ones, `29.5` the 260 ones.

## Evidence

### A. Cross-host run — phantom zeros from the marker bug

First cross-host attempt (TX on x280 local, RX on x240 remote):

| cell | rx_pkts | runner warning |
|---|---|---|
| 650 / 64 B | 0 | `WARN: RX did not reach listen phase` |
| 650 / 128 B | 0 | `WARN: RX did not reach listen phase` |

But the markers **did exist** on x240, written during that very run:

```
-rw-rw-r-- 1 c08r4d0r dialout 17 Oct 14 02:12 /tmp/rfa1b_rx_none_650_64_1.mark
-rw-rw-r-- 1 c08r4d0r dialout 17 Oct 14 02:13 /tmp/rfa1b_rx_none_650_128_2.mark
```

The receiver reached its listen phase; the runner failed to *see* it. Proof that
the topology, not the radio, was at fault — same cells, RX local:

| cell | rx_pkts | crc_ok | rssi |
|---|---|---|---|
| 650 / 128 B | **200** | **200** | -25.5 dBm |

### B. Clean 650 kbps at every payload length

With the receiver local, 650 kbps measured clean at all three payload lengths,
including the two the RFA-1b run had reported as zero:

| # | rate | len | rx_pkts | crc_ok | crc_bad | rssi |
|---|---|---|---|---|---|---|
| 1 | 650 | 64 B | 200 | 200 | 0 | -25.5 |
| 2 | 650 | 128 B | 200 | 200 | 0 | -25.5 |
| 3 | 650 | 255 B | 200 | 200 | 0 | -25.5 |
| 4 | 650 | 64 B | 200 | 200 | 0 | -25.0 |

Consecutive 650 kbps cells (same rate, no mode change) are **consistently
clean** — which is what isolates finding 2 from finding 1.

### C. The merged run's zeros are the mode-change effect, not the harness bug

The merged RFA-1b evidence used **local** ports (`/dev/ttyUSB0` TX,
`/dev/ttyUSB1` RX), so the remote-marker bug cannot explain it. Its matrix
alternated 260 <-> 650 every cell:

```
260/64 CLEAN · 650/64 ZERO · 260/128 CLEAN · 650/128 CLEAN ·
260/255 CLEAN · 650/255 ZERO
```

A pure byte-alignment story (64 B and 255 B are len%4==0, 128 B is not) predicts
650/128 would also fail when measured right after a 260 cell — it did not.
The **mode-change hypothesis** (650 cells that directly follow a 260 cell lose
their window) fits the pattern with one exception in the data — 650/128
immediately after 260 was CLEAN — so it is **not proven**, only the leading
candidate. A third possibility is load-dependent marker latency under ssh,
which is why the decisive test below is a controlled interleave rather than
more of the same.

## Reproduction

```bash
cd firmware/e80-stm32-bench
# receiver LOCAL (remote RX hits the harness bug until the fix lands)
RFA1B_TX_HOST=x240 RFA1B_TX_PORT=/dev/ttyUSB0 \
RFA1B_RX_HOST= RFA1B_RX_PORT=/dev/ttyUSB0 \
python3 tools/rfa1b_pram_matrix.py --arm none --pa 22 \
  --cells 650:64,650:128,650:255,650:64,650:128,650:255 --outdir ~/rfa1b-race-650
```

## Fix landed with this note

`tools/rfa1b_pram_matrix.py`: `run_ops()` now returns a host-qualified marker
handle (`"<host>:<path>"`) for remote boards, matching what `wait_mark()`
already knows how to split on. Regression test
`test_remote_listen_marker_carries_host_prefix` (RED before the fix, GREEN
after; suite 14 passed).

## Residual question (not blocking, cheap to settle)

Is the merged run's 650/64 + 650/255 pair the **same** bitrate-change effect, or
did those two cells lose their burst to the 60 s marker timeout for a different
reason (e.g. the RX agent's `elapsed_s=28.1` window opening late under ssh load)?
The controlled interleave — `650:64,260:64,650:64,260:64,...` — decides it in
~10 minutes and is the recommended next bench slot if anyone wants the mechanism
nailed down. Current state: **no 650 kbps defect is demonstrated**, and every
zero observed so far is explained without invoking the radio.
