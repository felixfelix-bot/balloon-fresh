# HANDOVER — Sustained Throughput Testing for Speed Group

> **Paste this into the speed-testing Signal group as the opening prompt.**

---

## You Are

You are an AI assistant (Hermes Agent) continuing work on the **balloon-fresh** project. Your task: **full-spectrum sustained throughput characterization** — measuring maximum continuous RX processing rate across ALL LR2021 modulation modes and bitrates, from fastest FLRC to slowest LoRa.

**Repo:** `~/repos/balloon-fresh` (branch: `range-tests` has latest firmware)
**Worktree:** Create `~/worktrees/balloon-speed-tests/` from `range-tests` branch
**Start here:** Read this document, then `docs/PLAN-speed-optimization.md`, `docs/RANGE-THROUGHPUT-PLAN.md`, and `docs/range-test-comprehensive-plan-2026-07-17.md`

---

## What the Project Is

ESP32-C3 + NiceRF LR2021 (Semtech) pico balloon tracker + mesh internet transport. Solar/supercap powered. Target weight <14g. 2.4 GHz FLRC mode for high-speed data, LoRa for long-range fallback.

Full details: `AGENTS.md` in repo root.

---

## Why This Handover Exists

The range-testing track has achieved a working FLRC link with verified results:

- **TX:** 2500 pkts/s at 2600 kbps FLRC, 127-byte packets, TX FIFO cleared before each packet
- **RX:** 485-495 out of 500 packets per burst window (PER 1-3%)
- **RSSI:** -77 dBm at close range (9-bit readout verified)
- **Burst throughput:** 579 kbps (measured per window)

**BUT:** The 579 kbps is BURST throughput, not SUSTAINED. The TX firmware pauses 2000ms between 500-packet bursts. Sustained throughput is unknown.

**AND:** Only FLRC 2600 kbps has been tested. The LR2021 supports 4 modulations across ~4 orders of magnitude in throughput. We need the FULL dynamic range characterized.

**The speed group's job:** Measure SUSTAINED throughput across ALL modulation modes and bitrates, using log-spaced sampling to cover the full dynamic range efficiently.

---

## How This Fits With What You're Already Doing

You (the speed track) have been working on breaking the 1391 kbps ceiling by optimizing SPI FIFO write time. That work focused on TX-side bottleneck (WRITE_FIFO = 517µs per packet).

**Full-spectrum sustained throughput testing is complementary but different:**

| Your existing work | This sustained throughput sweep |
|---|---|
| TX-side optimization (faster FIFO write) | RX-side capacity across ALL modulations |
| Goal: break 1391 kbps ceiling at FLRC 2600 | Goal: map sustained throughput across 4 orders of magnitude |
| Method: logic analyzer, DMA, PIO | Method: continuous TX flood, measure RX at each mode |
| Bottleneck: WRITE_FIFO 517µs | Bottleneck: RX re-arm time (SPI overhead per packet) |
| Tests 1 modulation (FLRC 2600) | Tests ALL modulations (FLRC × 4, LoRa × 4, GFSK × 2) |

**Key insight:** Your TX optimization and this RX sustained test are independent. If you make TX faster (DMA drops FIFO write to 100µs), TX can send faster, but can RX receive faster? The sustained test answers that — across the FULL spectrum.

**Both numbers matter:**
- TX max send rate (your work) = how fast we can transmit
- RX max receive rate (this test) = how fast we can process
- Real throughput = min(TX max, RX max)

---

## Full-Spectrum Sweep Design

### The Full Dynamic Range

LR2021 supports 4 modulation types. Throughput spans ~4 orders of magnitude:

| Modulation | Config | Air time/pkt | Theoretical throughput | Use case |
|---|---|---|---|---|
| FLRC 2600 | BR=0x00, BT1.0 | 0.39 ms | 2600 kbps | High-speed mesh, close range |
| FLRC 1300 | BR=0x02, BT0.5 | 0.78 ms | 1300 kbps | Medium speed, medium range |
| FLRC 650 | BR=0x04, BT0.5 | 1.56 ms | 650 kbps | Tradeoff speed/range |
| FLRC 325 | BR=0x06, BT0.5 | 3.12 ms | 325 kbps | Max FLRC range |
| LoRa SF5 BW1625 | Fastest LoRa | ~2.5 ms | ~400 kbps | Fast LoRa, medium range |
| LoRa SF7 BW812 | Medium LoRa | ~8 ms | ~125 kbps | Medium range telemetry |
| LoRa SF9 BW406 | Long LoRa | ~40 ms | ~25 kbps | Long range telemetry |
| LoRa SF12 BW203 | Max LoRa | ~2000 ms | ~0.5 kbps | Max range, balloon-to-ground |
| GFSK 1000 | Fast FSK | ~1.0 ms | ~1000 kbps | Alternative to FLRC |
| GFSK 50 | Slow FSK | ~20 ms | ~20 kbps | Low-power fallback |

### Log-Spaced Sampling Strategy

**DO NOT test every possible combination.** The LR2021 has 8 FLRC bitrates, 8 LoRa spreading factors × 5 bandwidths, and many GFSK options. Testing all would take hours.

Instead, use **log-spaced sampling** — pick points that span the full dynamic range with ~factor-2 to factor-4 spacing:

**FLRC sweep (factor-2 steps, 4 points):**
- 2600 → 1300 → 650 → 325 kbps
- Covers 8:1 throughput range
- All use same firmware, just change `RX_BITRATE_KBPS` and `TX_BITRATE_KBPS`

**LoRa sweep (factor-4 steps in airtime, 4 points):**
- SF5 BW1625 (fastest, ~2.5ms/pkt)
- SF7 BW812 (~8ms/pkt)
- SF9 BW406 (~40ms/pkt)
- SF12 BW203 (slowest, ~2000ms/pkt)
- Covers ~800:1 airtime range
- Needs new LoRa firmware (different init sequence from FLRC)

**GFSK sweep (2 points, optional):**
- 1000 kbps (fast)
- 50 kbps (slow)
- Optional — GFSK is not a primary flight mode

**Total: 10 test points (8 required + 2 optional)**

### Time Budget Analysis

**CRITICAL:** Test duration scales inversely with throughput. Slow modes need MUCH longer per packet.

| Mode | Test duration | Packets sent | Packets received (est) | Time justification |
|---|---|---|---|---|
| FLRC 2600 | 30s | ~75,000 | ~73,000 | Enough for statistical confidence |
| FLRC 1300 | 30s | ~38,000 | ~37,000 | Same |
| FLRC 650 | 30s | ~19,000 | ~18,500 | Same |
| FLRC 325 | 30s | ~9,500 | ~9,300 | Same |
| LoRa SF5 BW1625 | 30s | ~12,000 | ~11,500 | Fast LoRa, 30s sufficient |
| LoRa SF7 BW812 | 60s | ~7,500 | ~7,200 | Medium LoRa, need more time |
| LoRa SF9 BW406 | 120s | ~3,000 | ~2,900 | Slow LoRa, 2 min for enough data |
| LoRa SF12 BW203 | 300s | ~150 | ~145 | VERY slow. 5 min for 150 packets. Could reduce to 50 pkts = 100s |
| GFSK 1000 | 30s | ~30,000 | ~29,000 | Fast |
| GFSK 50 | 60s | ~3,000 | ~2,900 | Medium |

**Total time (required 8 points):** ~11 minutes of active testing
**Total time (all 10 points):** ~14 minutes of active testing
**Plus reconfiguration time:** ~2 min per point (reflash or serial command) = ~20 min
**Grand total:** ~35 min for full spectrum sweep

### Adaptive Packet Count

For very slow modes, adapt packet count to keep test reasonable:

| Mode | Packets per test | Duration | Rationale |
|---|---|---|---|
| FLRC (all) | 10,000+ | 30s | High rate, need lots for statistics |
| LoRa SF5 | 5,000 | 30s | Still fast enough |
| LoRa SF7 | 1,000 | 60s | Medium |
| LoRa SF9 | 300 | 120s | Slow but enough for PER stats |
| LoRa SF12 | 50 | 100s | VERY slow. 50 pkts = enough for yes/no link |

**Rule of thumb:** aim for at least 50 packets at each point for meaningful PER. 500+ for meaningful throughput statistics.

---

## What to Build

### 1. Continuous TX Firmware (NEW)

Modify `flrc_range_tx_auto.cpp` or create `flrc_cont_tx.cpp`:

- Remove 2000ms pause between bursts
- Send packets continuously: `clearIrq → clearTxFifo → writeTxFifo → setTx → waitBusy → loop`
- Serial commands:
  - `CONT 30000` = send continuously for 30 seconds
  - `COUNT 500` = send 500 packets then stop
  - `BITRATE 2600` = set FLRC bitrate (re-init radio)
  - `POWER 12` = set TX power
  - `PKTLEN 127` = set packet size
- Print TX_DONE count every 1000 packets (or every 10 for slow modes)

### 2. LoRa TX/RX Firmware (NEW — different init sequence)

LoRa mode needs different SPI init from FLRC. The LR2021 protocol reference (`docs/lr2021-spi-protocol-reference.md`) covers the init sequence:

- SET_PACKET_TYPE: FLRC=0x05, LoRa=0x01 (different!)
- SET_LORA_MODULATION_PARAMS instead of SET_FLRC_MODULATION_PARAMS
- Different packet params structure
- RSSI readback opcode differs (GET_LORA_PACKET_STATUS vs GET_FLRC_PACKET_STATUS)

**Build both TX and RX LoRa firmware.** Same packet structure (seq number + payload + RSSI), different radio init.

Reference: RadioLib v7.6.0 has LoRa init code for LR2021 (`docs/lr2021-reference-2026-07-16.md`). Extract the raw SPI commands from RadioLib's `beginLoRa()` to build raw SPI firmware.

### 3. Sustained RX Measurement

The existing RX firmware already works for FLRC. For sustained testing:

- Increase window size to 2000 or 5000 packets (more data per window)
- OR add time-based mode: capture for 10s/30s/60s continuously
- Print per-second breakdown if possible (shows if RX falls behind over time)
- For LoRa: window size = time-based (100s for SF12, 30s for SF5)

### 4. GFSK Firmware (OPTIONAL — lowest priority)

GFSK uses yet another init sequence. If time permits, add 2 GFSK points. If not, skip — GFSK is not a primary flight mode.

---

## Test Execution Plan

### Phase 1: FLRC Sustained Sweep (4 points, ~15 min)

1. Flash continuous TX + existing RX (FLRC 2600)
2. Start RX capture (30s window)
3. Start TX continuous (30s)
4. Capture: total received, unique, lost, PER, throughput, RSSI
5. Repeat for 1300, 650, 325 (change `TX_BITRATE_KBPS` + `RX_BITRATE_KBPS`, rebuild, reflash)

**Questions to answer:**
- Can RX keep up with continuous TX at 2600 kbps? (PER < 5%?)
- Does PER increase over time? (RX falling behind)
- What's the RX processing bottleneck? (SPI commands? waitBusy? RSSI read?)
- Does throughput match link rate at each bitrate? If not, what's the gap?

### Phase 2: LoRa Sustained Sweep (4 points, ~20 min)

1. Flash LoRa TX + LoRa RX firmware
2. Test SF5 BW1625: 30s continuous, 5000+ packets
3. Test SF7 BW812: 60s continuous, 1000+ packets
4. Test SF9 BW406: 120s continuous, 300+ packets
5. Test SF12 BW203: 100s, 50 packets

**Questions to answer:**
- Does LoRa sustained throughput match theoretical?
- Is RX re-arm time proportionally less significant at low rates? (more air time = more processing margin)
- Any LoRa-specific RX issues? (different FIFO size? different IRQ behavior?)

### Phase 3: Cross-Modulation Analysis (~10 min)

1. Plot throughput vs air-time-per-packet across ALL modes
2. Identify: is there a universal RX processing ceiling? (e.g. max 2000 pkts/s regardless of mode?)
3. Identify: at what air-time does RX overhead become negligible? (re-arm time << air time)
4. Compare: FLRC 325 vs LoRa SF5 — which gives better sustained throughput? (similar air time, different modulation)

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
pio run -e rp2040-range-tx-auto    # TX (FLRC)
pio run -e rp2040-range-rx-auto    # RX (FLRC)
# LoRa firmware: new environments (needs creating)
```

---

## Reasoning Prompts — Work Through These Before Starting

### 1. Sweep Design Reasoning

- Why log-spaced and not linear? Linear sampling over 4 orders of magnitude = 99% of points at the slow end. Log-spaced gives equal coverage across the range.
- Is factor-2 spacing for FLRC fine enough? Could miss non-linear behavior (e.g. RX fails at 1000 kbps but works at 1300 and 650). If so, add 1000 kbps as an extra point.
- Is factor-4 spacing for LoRa fine enough? SF7→SF9 is a big jump. Could add SF8 BW406 as intermediate if results are non-monotonic.
- What about bandwidth? LoRa BW affects both sensitivity and throughput. Should we test SF7 at multiple BWs (203, 406, 812, 1625)? That's 4 more points but reveals BW vs SF tradeoff.

### 2. RX Bottleneck Reasoning

- RX re-arm sequence: readFifo → clearRxFifo → clearErrors → clearIrq → setRx → waitBusy → readRSSI
- Total re-arm overhead: ~100-200µs per packet
- At FLRC 2600 (0.39ms air time): re-arm = 25-50% of air time → significant
- At FLRC 325 (3.12ms air time): re-arm = 3-6% of air time → negligible
- At LoRa SF12 (2000ms air time): re-arm = 0.01% → completely negligible
- **Hypothesis:** RX overhead is proportional to packet rate, not throughput. At high packet rates, RX may be the bottleneck. At low rates, TX air time dominates.
- **Test:** Plot sustained throughput as fraction of theoretical vs packet rate. Where does the curve cross 90%? 95%? 99%?

### 3. PER Over Time Reasoning

- If RX falls behind, FIFO fills with stale data → garbage seq numbers
- Watch for: PER increasing in later windows vs early windows
- Watch for: seq numbers going backwards or jumping (FIFO corruption)
- At slow modes (LoRa SF12), PER should be ~0% — if it's not, something is fundamentally wrong
- At fast modes (FLRC 2600), some PER is acceptable (<5%) — but should it increase over time?

### 4. Cross-Modulation Comparison

- FLRC 325 kbps (3.12ms/pkt) vs LoRa SF5 BW1625 (~2.5ms/pkt): similar air time, different modulation
- Which has lower PER? FLRC has forward error correction (CR), LoRa has spreading gain
- Which has better sustained throughput? FLRC is simpler, LoRa has processing gain
- This comparison informs the adaptive protocol: at what distance do we switch from FLRC to LoRa?

### 5. Time Budget Optimization

- Total test time: ~35 min for full sweep (8 points + reflash)
- Can we reduce? Serial command bitrate change (no reflash) = saves 2 min per point × 8 = 16 min saved
- Can we parallelize? No — only 2 boards, both needed for one test
- Is 30s enough for FLRC? 30s × 75,000 pkts = massive sample. 10s would suffice (25,000 pkts). Saves 20s × 4 = 80s.
- Is 300s needed for LoRa SF12? 50 packets in 100s is enough for PER yes/no. Could reduce to 50s if link is clearly working.
- **Optimized budget:** 4×10s (FLRC) + 4×30-120s (LoRa) + reflash = ~20 min total

### 6. How This Informs the Adaptive Protocol

The LR2021 adaptive protocol (ADR-007) switches modulation based on distance:
- FLRC 2600 for close range (high speed)
- FLRC 650 for medium range
- LoRa SF7 for long range
- LoRa SF12 for max range

The sustained throughput sweep tells us:
1. What throughput to expect at each mode (for link budget calculations)
2. Whether RX can keep up at each mode (for firmware design — does RX need optimization for slow modes too?)
3. The crossover points where switching to a slower mode doesn't hurt throughput much but improves reliability

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

**Key RX loop sequence (proven working for FLRC):**
```
IRQ HIGH → readFifo → clearRxFifo → clearErrors → clearIrq → setRx → waitBusy → readRSSI → loop
```

This sequence gives 485-495/500 packets (PER 1-3%) at FLRC 2600.

**IMPORTANT for LoRa:** The RX loop will need adaptation:
- Different IRQ flags (LoRa uses different IRQ status bits)
- Different RSSI readback opcode (GET_LORA_PACKET_STATUS, not GET_FLRC_PACKET_STATUS)
- Different FIFO behavior (LoRa may have variable-length packets)
- Longer air time = more processing margin, but also longer waitBusy calls

---

## LR2021 Modulation Parameters Reference

### FLRC Bitrate Codes (SET_FLRC_MODULATION_PARAMS 0x0248)
```
Br2600 = 0x00  Br2080 = 0x01  Br1300 = 0x02  Br1040 = 0x03
Br650  = 0x04  Br520  = 0x05  Br325  = 0x06  Br260  = 0x07
```
- byte3 = (coding_rate << 4) | pulse_shape
- CR: Cr12=0, Cr34=1, None=2, Cr23=3
- PulseShape: None=0, Bt0p3=4, Bt0p5=5, Bt0p7=6, Bt1p0=7
- Proven working: Br2600 + None + Bt1.0 → `{0x02, 0x48, 0x00, 0x27}`

### LoRa Parameters (SET_LORA_MODULATION_PARAMS)
- SpreadingFactor: SF5-SF12
- Bandwidth: BW203, BW406, BW812, BW1625, BW3250 (kHz)
- CodingRate: CR 4/5 through 4/8
- HeaderType: Explicit or Implicit

### Packet Types (SET_PACKET_TYPE 0x0207)
- FLRC = 0x05 (current, working)
- LoRa = 0x01 (needs implementation)
- GFSK = 0x02 (optional)
- LR-FHSS = 0x03 (not needed — extreme long range, very slow)

### RSSI Readback Per Modulation
- FLRC: GET_FLRC_PACKET_STATUS (0x024B) — 9-bit unsigned, negate for dBm
- LoRa: GET_LORA_PACKET_STATUS (different opcode — check protocol reference)
- GFSK: GET_GFSK_PACKET_STATUS (different again)

See: `docs/lr2021-spi-protocol-reference.md` and `docs/lr2021-spi-command-reference.md`

---

## Key Documents

| Document | Purpose |
|---|---|
| `docs/PLAN-speed-optimization.md` | TX optimization plan (your existing work) |
| `docs/RANGE-THROUGHPUT-PLAN.md` | Range+throughput plan with modulation comparison |
| `docs/range-test-comprehensive-plan-2026-07-17.md` | Full 9-axis sweep plan (Axis 4 = modulation) |
| `docs/lr2021-spi-protocol-reference.md` | SPI protocol reference (init sequences per modulation) |
| `docs/lr2021-spi-command-reference.md` | SPI command reference (opcodes) |
| `docs/flrc-timing-profile-2026-07-16.md` | Real TX timing data from hardware |
| `docs/adr/007-adaptive-protocol.md` | Adaptive protocol design (why we need full spectrum) |
| `firmware/rp2040/src/flrc_range_tx_auto.cpp` | Current TX firmware (FLRC burst mode) |
| `firmware/rp2040/src/flrc_range_rx_auto.cpp` | Current RX firmware (FLRC, working, verified) |
| `AGENTS.md` | Full project context, pin maps, inventory |

---

## What the Range Track Is Doing

The range-testing track (separate Signal group) is working on:
- Distance vs PER vs RSSI measurements at 4 FLRC bitrates
- Each distance point: ~1.5 min cycle (burst mode, 500 pkts × 4 bitrates)
- Range test already captures burst throughput per window (free metric)
- Sustained throughput across full modulation spectrum is YOUR job

**Board sharing:** Both tracks use the same RP2040 boards. Coordinate access. Do NOT flash simultaneously.

---

## Questions to Answer — Report Back to Range Group

After running the full-spectrum sustained throughput sweep, report:

1. What sustained throughput did you measure at each of the 8-10 test points?
2. Can RX keep up with continuous TX at FLRC 2600 kbps? (PER < 5%?)
3. What's the RX processing bottleneck? Is it the same across all modulations?
4. Does PER increase over time at any mode? (RX falling behind)
5. What's the throughput as fraction of theoretical at each point? (efficiency curve)
6. FLRC 325 vs LoRa SF5: which gives better sustained throughput at similar air time?
7. Should the range test use continuous TX instead of burst mode for any modes?
8. At what air-time-per-packet does RX overhead become negligible? (<1% of air time)
9. Does the existing 1391 kbps ceiling still apply, or has the RX firmware change (RSSI-after-rearm) changed the equation?
10. What modulation should the adaptive protocol use as the FLRC→LoRa crossover point?

---

## Anti-Collapse Guardrails

- You are the SPEED track. Do NOT do range testing (distance sweeps).
- You do NOT coordinate with other tracks. Use findings independently.
- Your scope: sustained throughput measurement across all modulations.
- Report results to the range-testing Signal group when done.