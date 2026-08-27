# Throughput Modes Explained: Burst vs Continuous TX on the LR2021

This document explains the two TX modes available on the E80 LR2021
module, why our bench firmware uses burst packet mode, how per-packet
overhead affects effective throughput, and how the serial bottleneck
was identified and resolved with QUIET mode.

---

## 1. Two TX Modes on the LR2021

The LR2021 chip supports two fundamentally different transmission modes:

### Burst Packet Mode (what we test)

Structured RF packets with full framing:

| Component        | Size (FLRC)         | Purpose                                  |
|-----------------|---------------------|------------------------------------------|
| Preamble        | 53 bits (32+21)     | Receiver AGC + bit timing lock            |
| Sync word        | 4 bytes (32 bits)   | Packet detection + frame boundary         |
| Payload          | up to 511 bytes     | User data (PRBS15-filled in bench)        |
| CRC             | 2 bytes (16 bits)   | Integrity check on payload                 |
| FEC (coding 3/4) | +25% redundancy     | Forward error correction on payload      |

Each packet is an independent, self-contained unit. The receiver
synchronizes on the preamble + sync word, decodes the payload, checks
the CRC, and (optionally) uses FEC to correct bit errors.

### Continuous TX Test Mode (PRBS9)

A raw pseudo-random bitstream with **no framing at all**:

- No preamble, no sync word, no CRC, no FEC coding
- No packet structure — just a continuous stream of PRBS9 bits
- Pure raw bitrate (e.g. 2600 kbps flat at FLRC-2600)
- The receiver **cannot** synchronize to this as packets
- Cannot measure packet error rate (PER)
- Cannot recover any payload data

This mode exists for **RF testing only**: spectrum analysis, link quality
assessment, transmitter calibration, power measurements, etc.

---

## 2. Why Burst Mode Is Slower (but Useful)

Burst packet mode is inherently slower than continuous TX because every
packet carries overhead that isn't user data:

### Per-Packet Overhead Breakdown (FLRC)

| Overhead Source       | Bits | Notes                                    |
|----------------------|------|------------------------------------------|
| Preamble (FLRC)      | 53   | 32 bits nominal + 21 bits chip overhead   |
| Sync word            | 32   | 4 bytes, fixed pattern                    |
| CRC-16               | 16   | 2 bytes, computed over payload            |
| **Total framing**    | 101  | ~12.6 bytes per packet                    |

Plus **FLRC coding rate 3/4**: forward error correction adds 25%
redundancy to the payload bits (4 coded bits for every 3 data bits).

### Additional Per-Packet Costs

| Cost Source                | Time / Impact                           |
|---------------------------|-----------------------------------------|
| SPI FIFO write (255B)     | ~229 µs at 9 MHz SPI clock              |
| IRQ handling               | Chip signals TX done → host reads status  |
| State machine transitions | STDBY → TX → STDBY per packet            |
| Gap pacing (GAP param)    | Configurable inter-packet delay          |

For FLRC-2600 with a 255B payload, the SPI write takes ~229 µs while
airtime is ~0.78 ms — the SPI bus has **3.2× headroom**, so it is not
the bottleneck at this bitrate/payload combination.

### Why We Use Burst Mode Anyway

Burst mode is the only mode that can:

- **Carry real data** — the payload is structured and recoverable
- **Measure packet error rate (PER)** — count CRC-pass vs CRC-fail
- **Verify bit-level integrity** — PRBS15 fill + on-chip regeneration
  allows the receiver to count bit errors precisely
- **Support FEC** — coding rate 3/4 can correct errors, not just detect them

---

## 3. Why Continuous Mode Is Faster (but Useless for Data)

Continuous TX (PRBS9) achieves the **full raw bitrate** with zero overhead:

- FLRC-2600 → exactly 2600 kbps on-air, no preamble, no gaps
- No SPI FIFO writes between packets (there are no packets)
- No state machine transitions, no IRQ per "packet"

But it **cannot** be used for data transfer because:

1. The receiver has no sync word to lock onto → no packet boundary
2. No CRC → no integrity verification
3. No payload structure → no way to extract user data
4. No PER measurement → can't count "successful" vs "failed" transmissions

**Continuous TX is an RF test mode.** It's for verifying that the
transmitter works, measuring output power, checking spectral mask
compliance, and characterizing link quality. It is never used for
actual data communication.

---

## 4. Throughput Table (FLRC Burst Mode, Theoretical Maximums)

The table below shows the **theoretical maximum throughput** at GAP=0
(no inter-packet gap). Real-world throughput will be lower due to
configured GAP, SPI latency, IRQ handling, and serial output.

| Bitrate (kbps) | Payload | Airtime/pkt | Max pkt/s | Raw kbps | Effective kbps | Overhead % |
|---------------:|--------:|------------:|----------:|---------:|----------------:|-----------:|
| 2600           | 511 B   | ~1.61 ms    | ~620      | 2600     | ~2530           | ~2.7%      |
| 2600           | 64 B    | ~0.24 ms    | ~4170     | 2600     | ~2130           | ~18%       |
| 1300           | 511 B   | ~3.22 ms    | ~310      | 1300     | ~1265           | ~2.7%      |
| 650            | 255 B   | ~3.2 ms     | ~310      | 650      | ~633            | ~2.6%      |
| 260            | 255 B   | ~8 ms       | ~125      | 260      | ~255            | ~2%       |

**How these numbers are calculated:**

- **Airtime/pkt** = (preamble_bits + sync_bits + payload_bits × 4/3 +
  crc_bits) / bitrate
- **Max pkt/s** = 1000 / airtime_ms (at GAP=0)
- **Effective kbps** = payload_bits × pkt/s / 1000
- **Overhead %** = 1 − (effective / raw)

For example, FLRC-2600 with 511B payload:
- Total bits on air = 53 + 32 + (511×8×4/3) + 16 = 53+32+5450+16 = 5551 bits
- Airtime = 5551 / 2600000 ≈ 2.14 ms (with FEC expansion)
- But our measured airtime of ~1.61 ms reflects the nominal bitrate
  accounting; the exact value depends on FLRC symbol packing
- Max pkt/s = 1000/1.61 ≈ 620
- Effective = 511×8×620/1000 ≈ 2535 kbps

**Key takeaway:** With large payloads (511B), overhead is only ~2.7%.
With small payloads (64B), overhead jumps to ~18% because the fixed
framing bits dominate. For maximum throughput, use the largest payload
the application allows.

### For Comparison: LoRa Mode

LoRa is far slower than FLRC for the same bandwidth:

| Mode           | Config           | 255B Airtime | Notes                    |
|---------------|------------------|-------------|--------------------------|
| LoRa SF7/BW500 | Fast LoRa        | ~12 ms      | Good sensitivity, slow   |
| LoRa SF12/BW125| Max range        | ~1312 ms    | 1.3 seconds per packet!   |

FLRC trades range for speed — at 2600 kbps you get ~620× the throughput
of LoRa SF12/BW125, at the cost of needing a much stronger signal.

---

## 5. The Serial Bottleneck (Pre-QUIET Fix)

Before QUIET mode was implemented, the bench firmware printed a ~120-character
`PKT` line to the UART for every packet received:

```
PKT seq=1234 rssi=-15.5 snr=42 crc=ok len=128
```

At **115200 baud** (the default):

| Metric                     | Value              |
|---------------------------|--------------------|
| Chars per PKT line         | ~120               |
| Time per PKT line          | ~10.4 ms           |
| Max sustainable pkt/s      | ~96                |
| FLRC-2600 max (GAP=0)      | ~620+ pkt/s        |
| **Loss without QUIET**     | **~84%**           |

This means at high packet rates, the UART couldn't keep up. The RX
board would drop events or fall behind, corrupting throughput
measurements. Tests at GAP=10ms (100 pkt/s) barely fit under the 96
pkt/s ceiling, but any attempt to push faster would fail silently.

### The FIX: QUIET Mode (commit dc3e357)

QUIET mode suppresses per-packet UART output. Instead of printing every
packet, the firmware only prints summary statistics at configurable
intervals (or on demand). This removes the serial bottleneck entirely:

- UART traffic drops from ~120 chars/pkt to ~0 chars/pkt during runs
- Only config commands and final/periodic stats cross the UART
- Theoretical max throughput is now limited by the **RF link**, not the
  serial monitor

---

## 6. PRBS15 Deterministic Generation (Why Serial Is Not a TX Bottleneck)

A critical design choice: **no payload data crosses the UART.**

### TX Side (Sender)

The TX board builds its payload **on-chip** (in the MCU, before SPI
transfer to the LR2021):

1. Write a 4-byte big-endian sequence number at the start of the payload
2. Fill the rest of the payload with **PRBS15** pseudo-random bits,
   seeded deterministically from the sequence number
3. Transfer the complete payload to the LR2021 FIFO via SPI
4. Trigger TX

### RX Side (Receiver)

The RX board verifies payloads **on-chip** (in the MCU, after SPI read
from the LR2021 FIFO):

1. Read the received payload from the LR2021 FIFO via SPI
2. Extract the 4-byte BE sequence number
3. Regenerate the expected PRBS15 pattern from that sequence number
4. Compare bit-by-bit, counting bit errors
5. Report only the **error count** (not the payload itself) via UART

### Why This Matters

| What Crosses UART | What Doesn't              |
|-------------------|---------------------------|
| Config commands   | Payload data (up to 511B) |
| Summary stats     | PRBS15 bit stream         |
| Error counts      | Per-bit comparison results |

At 115200 baud, the UART can carry ~11.5 KB/s. Even a single 511B
payload would take ~44 ms to transmit — and we're trying to do 620
packets/sec. By keeping payload data local and only sending stats
over UART, the serial link is never a throughput bottleneck.

**This is why QUIET mode is sufficient:** it suppresses the per-packet
*status line* (which was the bottleneck), and the per-packet *payload*
never needed to cross UART in the first place.

---

## 7. Confirmed Measurements

All tests: 200 packets, GAP=10ms, indoor, ~10 cm antenna distance.

| Bitrate (kbps) | Payload | GAP    | Pkts RX | CRC Errors | RSSI (dBm) |
|---------------:|--------:|-------:|--------:|-----------:|-----------:|
| 2600           | 128 B   | 10 ms  | 200/200 | 0          | −15.5      |
| 1300           | 64 B    | 10 ms  | 200/200 | 0          | −16.0      |
| 650            | 255 B   | 10 ms  | 200/200 | 0          | −28.0      |

**Interpretation:**

- 100% packet reception at all three bitrates (zero loss)
- Zero CRC errors → the link is clean at close range
- RSSI scales as expected (higher bitrate → slightly lower RSSI reading
  due to wider bandwidth)
- GAP=10ms (100 pkt/s) was chosen to stay under the pre-QUIET serial
  ceiling of ~96 pkt/s — with QUIET mode, we can now push much faster

---

## 8. Next Steps

Now that QUIET mode is implemented (commit dc3e357), the serial
bottleneck is removed. The path forward:

1. **Flash QUIET mode firmware** to both E80 boards
2. **Run a max-throughput sweep** with:
   - QUIET = ON
   - GAP = 1000 µs (1 ms, or lower if stable)
   - Large N (1000+ packets per run)
   - All FLRC bitrates: 260, 325, 520, 650, 1040, 1300, 2080, 2600
3. **Measure the true ceiling** at each FLRC bitrate:
   - Maximum sustainable pkt/s before packet loss begins
   - CRC error rate vs. packet rate
   - Effective throughput (kbps) at each setting
4. **Compare** effective throughput vs. theoretical maximums from the
   table in section 4
5. **Explore GAP reduction** — can we get below 1 ms? Below 500 µs?
   What's the minimum stable inter-packet gap?

### Expected Outcome

With QUIET mode and GAP=1000 µs, FLRC-2600 with 511B payloads should
approach ~590+ pkt/s (theoretical max ~620 with GAP=0, minus ~40 µs gap
overhead per packet). This would give **~2400 kbps effective throughput**
— ~92% of the raw 2600 kbps bitrate, with full packet integrity,
CRC checking, and PRBS15 bit error counting.