# HANDOVER — Sustained Throughput Testing for Speed Group

> **Paste this into the speed-testing Signal group as the opening prompt.**

---

## You Are

You are an AI assistant (Hermes Agent) continuing work on the **balloon-fresh** project. Your task: **sustained throughput measurement** — measuring the maximum continuous RX processing rate of the LR2021 FLRC link, separate from burst-mode range testing.

**Repo:** `~/repos/balloon-fresh` (branch: `range-tests` has latest firmware)
**Worktree:** Create `~/worktrees/balloon-speed-tests/` from `range-tests` branch
**Start here:** Read this document, then `docs/PLAN-speed-optimization.md` and `docs/HANDOVER-speed-tests.md`

---

## What the Project Is

ESP32-C3 + NiceRF LR2021 (Semtech) pico balloon tracker + mesh internet transport. Solar/supercap powered. Target weight <14g. Using 2.4 GHz FLRC mode for high-speed data.

Full details: `AGENTS.md` in repo root.

---

## Why This Handover Exists

The range-testing track has achieved a working FLRC link with verified results:

- **TX:** 2500 pkts/s at 2600 kbps FLRC, 127-byte packets, TX FIFO cleared before each packet
- **RX:** 485-495 out of 500 packets per burst window (PER 1-3%)
- **RSSI:** -77 dBm at close range (9-bit readout verified)
- **Burst throughput:** 579 kbps (measured per window)

**BUT:** The 579 kbps is BURST throughput, not SUSTAINED. The TX firmware pauses 2000ms between 500-packet bursts. Sustained throughput is much lower:

- Burst throughput: 579 kbps (500 pkts in 851ms)
- Sustained throughput: ~178 kbps (485 pkts × 127 bytes × 8 / (851ms + 2000ms))
- The 2s TX pause wastes 70% of air time

**The speed group's job:** Measure SUSTAINED throughput — what happens when TX sends continuously with no pause. Can RX keep up? What's the real max processing rate?

---

## How This Fits With What You're Already Doing

You (the speed track) have been working on breaking the 1391 kbps ceiling by optimizing SPI FIFO write time. That work focused on TX-side bottleneck (WRITE_FIFO = 517µs per packet).

**Sustained throughput testing is complementary but different:**

| Your existing work | Sustained throughput test |
|---|---|
| TX-side optimization (faster FIFO write) | RX-side capacity (can RX keep up?) |
| Goal: break 1391 kbps ceiling | Goal: find true max sustained RX rate |
| Method: logic analyzer, DMA, PIO | Method: continuous TX flood, measure RX |
| Bottleneck: WRITE_FIFO 517µs | Bottleneck: RX re-arm time + SPI overhead |

**Key insight:** Your TX optimization and this RX sustained test are independent. If you make TX faster (e.g. DMA drops FIFO write to 100µs), TX can send faster, but can RX receive faster? The sustained test answers that.

**Both numbers matter:**
- TX max send rate (your work) = how fast we can transmit
- RX max receive rate (this test) = how fast we can process
- Real throughput = min(TX max, RX max)

---

## What to Build

### 1. Continuous TX Firmware (NEW)

Modify `flrc_range_tx_auto.cpp` (or create a new `flrc_cont_tx.cpp`) to:

- Remove the 2000ms pause between bursts
- Send packets continuously: `clearIrq → clearTxFifo → writeTxFifo → setTx → waitBusy → loop`
- Serial command interface: `CONT 10000` = send continuously for 10 seconds
- Print TX_DONE count every 1000 packets
- Optional: configurable inter-packet delay (0ms, 1ms, 5ms, 10ms) via serial

### 2. Sustained RX Measurement

The existing RX firmware (`flrc_range_rx_auto.cpp`) already works. It captures windows of 500 packets with throughput. For sustained testing:

- Increase window size to 2000 or 5000 packets (more data per window)
- OR add a time-based mode: capture for 10s/30s/60s continuously
- Print: total received, unique seqs, lost, PER, throughput_kbps, RSSI avg/min/max
- Print per-second breakdown if possible (shows if RX falls behind over time)

### 3. Test Matrix

Run sustained throughput at all 4 bitrates:

| Bitrate (kbps) | Air time/pkt | Expected sustained (if RX keeps up) |
|---|---|---|
| 2600 | 0.39ms | ~2600 kbps |
| 1300 | 0.78ms | ~1300 kbps |
| 650 | 1.56ms | ~650 kbps |
| 325 | 3.12ms | ~325 kbps |

At each bitrate:
1. Start RX in capture mode
2. Start TX in continuous mode for 30s
3. Capture: total received, unique, lost, PER, throughput, RSSI
4. Check: does throughput match link rate? If not, what's the RX bottleneck?

---

## Hardware Setup

### Current Board Mapping (verified 2026-07-23)

| Port | Board | Role | Firmware |
|---|---|---|---|
| /dev/ttyACM0 | ESP32 UART bridge → Pico A | RX | flrc_range_rx_auto |
| /dev/ttyACM1 | Pico A direct USB | — | (same board) |
| /dev/ttyACM2 | ESP32 UART bridge → Pico B | TX | flrc_range_tx_auto |
| /dev/ttyACM3 | Pico B direct USB | — | (same board) |

**IMPORTANT:** ESP32 UART bridges control BOOTSEL. Use the `flrc-firmware-ops` skill for flashing. Do NOT use 1200 baud touch on ACM0/ACM2 — it's unreliable. Use the ESP32 bridge commands instead.

### Build Commands

```bash
# RP2040 firmware (PlatformIO)
cd ~/worktrees/balloon-speed-tests/firmware/rp2040
pio run -e rp2040-range-tx-auto    # TX
pio run -e rp2040-range-rx-auto    # RX

# Flash via ESP32 UART bridge (see flrc-firmware-ops skill)
# TX board: /dev/ttyACM2 (ESP32 bridge → Pico B)
# RX board: /dev/ttyACM0 (ESP32 bridge → Pico A)
```

---

## Reasoning Prompts for You

Work through these questions before starting:

1. **Can RX keep up with continuous TX at 2600 kbps?**
   - RX re-arm sequence: readFifo → clearRxFifo → clearErrors → clearIrq → setRx → waitBusy → readRSSI
   - Each SPI command: ~14µs (clearIrq) to ~50µs (setRx + waitBusy)
   - Total re-arm overhead: ~100-200µs per packet
   - At 2600 kbps, packets arrive every ~0.39ms (390µs)
   - If re-arm takes 200µs, RX has 190µs margin — should keep up
   - But if re-arm takes 300µs, RX misses packets. Measure to find out.

2. **Where is the RX bottleneck?**
   - Is it the SPI commands (clearRxFifo, clearErrors, clearIrq, setRx)?
   - Is it the waitBusy() call after setRx?
   - Is it the RSSI read?
   - Is it the FIFO read itself?
   - Profile: add micros() timestamps around each operation, print to serial

3. **Does PER increase over time?**
   - If RX falls behind, FIFO fills with stale data → garbage seq numbers
   - Watch for: PER increasing in later windows vs early windows
   - Watch for: seq numbers going backwards or jumping (FIFO corruption)

4. **What's the optimal inter-packet delay?**
   - 0ms: maximum throughput, but RX may miss packets
   - 1ms: gives RX 1ms to process, should be enough at 2600 kbps
   - 5ms: very safe, but throughput drops to ~200 kbps
   - Find the minimum delay where PER stays <1%

5. **How does this compare to burst throughput?**
   - Burst: 579 kbps (with 2s TX pause)
   - Sustained: ??? kbps (continuous TX)
   - If sustained < burst, RX is the bottleneck (can't process fast enough)
   - If sustained ≈ burst, TX pause was the only bottleneck (RX is fine)

---

## What the Range Track Is Doing

The range-testing track (separate Signal group) is working on:
- Distance vs PER vs RSSI measurements at 4 bitrates
- Each distance point: ~1.5 min cycle (burst mode, 500 pkts × 4 bitrates)
- Range test already captures throughput per window (free metric)
- Sustained throughput is NOT measured in range test — that's YOUR job

**Board sharing:** Both tracks use the same RP2040 boards. Coordinate access. Do NOT flash simultaneously.

---

## Key Documents

| Document | Purpose |
|---|---|
| `docs/PLAN-speed-optimization.md` | TX optimization plan (your existing work) |
| `docs/HANDOVER-speed-tests.md` | Original speed track handover |
| `docs/flrc-timing-profile-2026-07-16.md` | Real TX timing data from hardware |
| `docs/lr2021-spi-protocol-reference.md` | SPI protocol reference |
| `docs/lr2021-spi-command-reference.md` | SPI command reference |
| `firmware/rp2040/src/flrc_range_tx_auto.cpp` | Current TX firmware (burst mode) |
| `firmware/rp2040/src/flrc_range_rx_auto.cpp` | Current RX firmware (working, verified) |
| `AGENTS.md` | Full project context, pin maps, inventory |

---

## Latest Fixes Applied (range-tests branch, 2026-07-23)

10 bugs fixed in RX firmware, all committed and pushed:

1. RSSI opcode: SX1280 0x0104 → LR2021 0x024B (9-bit)
2. FLRC bitrate codes: wrong register values corrected
3. Serial-command variants: same dual bug fixed
4. SPI clock: 16→20 MHz (RX, match TX)
5. LED delay: 1000µs → 50µs (was blocking 85% of CPU)
6. Packet size: 255 → 127 bytes (FIFO safety)
7. IRQ detection: SPI register read → hardware pin poll
8. TX FIFO clear: added clearTxFifo() before each packet write
9. RSSI read moved after re-arm (THE breakthrough — chip listens while RSSI read)
10. waitBusy after setRx (ensure chip re-armed before polling)

**Key RX loop sequence (proven working):**
```
IRQ HIGH → readFifo → clearRxFifo → clearErrors → clearIrq → setRx → waitBusy → readRSSI → loop
```

This sequence gives 485-495/500 packets (PER 1-3%). Your job: test if it holds up under continuous TX.

---

## Theoretical Bounds (updated with verified data)

| Scenario | Measured | Theoretical |
|---|---|---|
| Burst throughput (current) | 579 kbps | ~692 kbps (500pkts × 127B × 8 / 851ms) |
| Sustained (continuous TX) | ??? | min(TX rate, RX rate) |
| Air-time limited (2600 kbps) | — | 2600 kbps |
| Air-time limited (1300 kbps) | — | 1300 kbps |
| Previous ceiling (old firmware) | 1391 kbps | — |

---

## Questions to Answer

After running the sustained throughput test, report back to the range-testing group:

1. What sustained throughput did you measure at each bitrate?
2. Can RX keep up with continuous TX at 2600 kbps? (PER < 5%?)
3. What's the RX processing bottleneck? (SPI commands? waitBusy? RSSI read?)
4. What inter-packet delay gives PER < 1% at each bitrate?
5. Should the range test use continuous TX instead of burst mode? (if RX can keep up, continuous gives better throughput numbers)
6. Does the existing 1391 kbps ceiling still apply, or has the RX firmware change (RSSI-after-rearm) changed the equation?

---

## Anti-Collapse Guardrails

- You are the SPEED track. Do NOT do range testing.
- You do NOT coordinate with other tracks. Use findings independently.
- Your scope: sustained throughput measurement only.
- Report results to the range-testing Signal group when done.