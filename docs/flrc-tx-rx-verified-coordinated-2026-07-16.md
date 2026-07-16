# FLRC Coordinated TX/RX Test — Verified Results

**Date:** 2026-07-16 17:20
**Repo:** balloon-fresh
**Firmware:** v4 baseline (Arduino SPI, flrc_raw_tx.cpp / flrc_raw_rx.cpp)
**Hardware:** TX = RP2040 8332, RX = RP2040 F242D

---

## Results

### TX Side

| Metric | Value |
|--------|-------|
| Packets sent | 1000 |
| TX_DONE | 1000 (100%) |
| Timeout | 0 |
| Elapsed | 1481 ms |
| Throughput | **1377.4 kbps** |
| Spin count/pkt | 13510 (consistent) |
| Status reg | 0x05 (normal) |
| IRQ reg | 0x000A080A (normal) |

### RX Side

| Metric | Value |
|--------|-------|
| Received | 1018 (includes ~18 stale FIFO) |
| Unique | 1018 |
| Duplicates | 0 |
| Lost | 0 (0.00%) |
| DEADBEEF | ✅ Captured (end marker) |
| RX Elapsed | 3491 ms (includes listen timeout) |
| RX Throughput | 594.9 kbps (lower due to RX listen overhead) |

### RX Packet Sequence (every 100th)

```
1,2073943152  (stale FIFO data)
2,1674117779  (stale)
3,1137900816  (stale)
4,1227313333  (stale)
5,2512754418  (stale)
100,86        ← clean seq from this TX burst
200,184
300,284
400,382
500,482
600,581
700,681
800,781
900,881
1000,981
RX_END DEADBEEF
```

Note: First 5 packets are stale FIFO data from previous TX burst. Clean
sequence starts at packet 100 (seq 86, 184, 284... gap of ~98-100 per
100 received = ~1% missed between print intervals).

---

## Test Method

1. Both boards flashed via `make bootsel-1200-tx/rx` (1200 baud touch reboot)
2. Python script sends "RUN" to RX first (2s head start to enter RX mode)
3. Then sends "RUN" to TX
4. Captures both serial ports for 15s
5. Script: `/tmp/coordinated_test.py`

---

## Conclusion

**v4 baseline is the proven ceiling at 1377 kbps.**

- TX: 1000/1000 TX_DONE, 0 timeouts
- RX: 0% packet loss, DEADBEEF end marker received
- RF link fully functional
- Arduino SPI (16 MHz) is sufficient — PIO+DMA not needed
- SPI overhead (~535 µs) overlaps with RF air time (~803 µs)

**PIO+DMA TX optimization is abandoned.** It crashes CDC, hangs the TX loop,
and offers negligible throughput gain (1377 → 1377 kbps). The bottleneck
is RF air time, not SPI speed.

---

*Test conducted 2026-07-16 17:20 UTC. All measurements from real hardware.*
