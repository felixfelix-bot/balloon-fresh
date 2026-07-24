# FLRC Byte Alignment Analysis — Cross-Track Finding

**Date:** 2026-07-24
**Source:** Independent analysis from FIPS cross-track doc + speed-tests firmware review

## The Bug

FLRC packets received correctly at 2600 kbps but byte alignment drifts at 1300 kbps and below. First 2-3 packets per phase decode OK, then GPS struct fields become garbage. CRC reports 0 errors even on corrupted payloads.

## TX Payload Layout (embedGPS in multi_radio_sweep_gps.cpp)

```
Bytes 0-3:   sync header (0xA5 0x5A 0x42 0x24)
Bytes 4-7:   latE7 (int32 LE)
Bytes 8-11:  lonE7 (int32 LE)
Bytes 12-13: sats (uint16 LE)
Byte 14:     fixQ (uint8)
Bytes 15-18: utcSec (uint32 LE)
Byte 19:     phaseId (uint8)
Bytes 20-21: seq (uint16 BE)
Bytes 22+:   fill pattern (i ^ 0xA5)
```

## RX Parsing (multi_radio_sweep_rx.cpp line 525)

```c
int gpsOff = (p.pktType == PT_LORA) ? 4 : 0;
// LoRa: reads from byte 4 (sync header present in FIFO)
// FLRC: reads from byte 0 (ASSUMES sync header stripped by hardware)
```

## Root Cause Hypothesis

The LR2021 does NOT consistently strip the FLRC sync word from the FIFO.

Evidence from FIPS walk test analysis:
- FLRC-2600: raw32 header shows `0xA5 0x5A 0x42 0x24` — sync word IS in FIFO
- But FLRC-2600 "works" — meaning gpsOff=0 happens to land on sync bytes that look like plausible (but wrong) data, OR the behavior differs between 2600 and lower rates

Most likely mechanism:
1. At 2600 kbps (BW 2666 kHz): chip processes packets fast enough that FIFO pointer resets cleanly between packets
2. At 1300 kbps and below (narrower BW): residual bytes from previous packet remain in FIFO buffer, shifting the read pointer. Each subsequent packet drifts further.
3. rfClearRxFifo() (opcode 0x01, 0x20) may not fully flush at lower bitrates

## Why CRC Passes on Garbage

The FLRC CRC is computed by the radio hardware over the received bitstream. If the byte alignment is off in our READ (FIFO pointer shifted), the radio-level CRC was computed on the correctly-received bytes — it passes because the RF link IS clean. The corruption happens at the FIFO read stage, AFTER CRC validation.

This is NOT a CRC bug — it's a FIFO pointer management bug.

## Fix Candidates (for post-walk-test implementation)

### Option A: Explicit FIFO flush before each read
```c
// Before rfReadRxFifo, add:
rfClearRxFifo();  // Flush any residual bytes
delayMicroseconds(10);
rfReadRxFifo(rxBuf, pktSize);
```
Risk: adds latency, may miss packets at high rates.

### Option B: Use packet length to validate alignment
After reading FIFO, check if bytes 0-3 match sync header (0xA5 0x5A 0x42 0x24). If not, shift buffer until aligned or discard.

### Option C: Two-phase FIFO read (status bytes first)
flrc_rx_raw.cpp lines 97-120 uses a two-phase read that accounts for 2 status bytes. This may be the correct approach — the LR2021 may prepend status bytes to FIFO data that our single-phase read ignores.

### Option D: Always assume sync header present
Change gpsOff to 4 for ALL packet types (LoRa + FLRC). If sync header is always in FIFO regardless of modulation, this is the simplest fix.

## Recommendation

Try Option D first (1-line change, trivially testable). If FLRC-2600 still works AND FLRC-1300 starts working, confirmed.

If not, try Option C (two-phase read matching flrc_rx_raw.cpp proven pattern).

## What Works Now (for characterization)

- FLRC-2600: RELIABLE (both HF and LF). Use for throughput benchmarks.
- LoRa SF7/SF9/SF12: RELIABLE. Use for range curves.
- FLRC-1300/650/325: BROKEN until fix applied. Do NOT use for data collection.
