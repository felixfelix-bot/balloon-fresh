# V4 Firmware Plan — Dynamic Packet Size Sweep

**Date:** 2025-07-25
**Status:** SUB-MANAGER CONSENSUS
**Goal:** Sweep packet SIZE as a dimension alongside radio mode — find optimal
PER/throughput/range tradeoff across {32, 64, 128, 255} byte packets.

---

## Operator's Core Question

> "Can we make it a dynamic byte size and sweep the byte size as well?
> I want to know what an optimistic PER looks like, what a pessimistic PER
> looks like, and find a reasonable middle ground."

---

## Sub-Manager Consensus Design

### Architecture: Dual-Mode Operation

**MODE 1 — Fixed Size (PKT_SIZE command):**
- Serial command `PKT_SIZE 32|64|128|255` sets runtime packet size
- All 14 phases run at that size
- Full 202s cycle, hundreds of packets per mode
- Run 4 walks (one per size) for complete tradeoff map
- Simplest, most statistically robust

**MODE 2 — Interleave (PKT_INTERLEAVE command):**
- Each phase slot divided into 4 time-based sub-slots
- Sub-slot 0: 32B, Sub-slot 1: 64B, Sub-slot 2: 128B, Sub-slot 3: 255B
- TX and RX both compute expected size from UTC time within phase
- All 4 sizes sampled within same phase = near-identical distance
- Fair A/B/C/D comparison without multiple walks

### Why Dual-Mode (Sub-Manager Consensus)

- **SM1 (Architecture):** Recommends serial command as primary — best PER
  statistics (300-500 pkt/mode/walk). Auto-rotate option for unattended.
- **SM2 (Field Ops):** Recommends burst-interleave — all sizes at same
  distance, zero cycle penalty. Critical insight: at 1.2 m/s, >17s between
  same-mode different-size samples confounds distance with size.
- **SM3 (Code):** Approved pktSize in Phase struct. 4 mechanical changes.
  Sync cache arrays must scale from 14 to NUM_PHASES.

**Orchestrator synthesis:** Offer BOTH modes. Fixed for walk tests (one size
per out-and-back). Interleave for stationary or slow-walk comparison.

---

## Implementation: V4 Changes (from V3)

### Change 1: Runtime Packet Size Variable

Replace compile-time `#define` with runtime variable:

```cpp
// V3 (compile-time):
#define LORA_PKT_SIZE  255
#define FLRC_PKT_SIZE  255

// V4 (runtime):
static uint16_t g_pktSize = 255;  // default, changed via serial command
```

### Change 2: Serial Command Parser

```
PKT_SIZE 32    → set g_pktSize = 32
PKT_SIZE 64    → set g_pktSize = 64
PKT_SIZE 128   → set g_pktSize = 128
PKT_SIZE 255   → set g_pktSize = 255
PKT_INTERLEAVE → enable interleave mode (size cycles per sub-slot)
PKT_FIXED      → disable interleave (use g_pktSize for all)
```

### Change 3: rfInitForPhase Uses Runtime Size

```cpp
// V3:
{0x02, 0x21, 0x00, 0x08, LORA_PKT_SIZE, flags}    // LoRa
{0x02, 0x49, 0x0C, 0x4C, 0x00, FLRC_PKT_SIZE}     // FLRC

// V4:
{0x02, 0x21, 0x00, 0x08, (uint8_t)currentPktSize, flags}
{0x02, 0x49, 0x0C, 0x4C, 0x00, (uint8_t)currentPktSize}
```

Where `currentPktSize` is computed per-packet (interleave) or per-command (fixed).

### Change 4: Interleave Size Computation

```cpp
static const uint16_t SIZE_TABLE[4] = {32, 64, 128, 255};

uint16_t computePktSize(bool interleave, uint32_t phaseElapsedMs, uint32_t slotMs) {
    if (!interleave) return g_pktSize;
    uint32_t subSlot = (phaseElapsedMs * 4) / slotMs;  // 0-3
    if (subSlot > 3) subSlot = 3;
    return SIZE_TABLE[subSlot];
}
```

Both TX and RX compute this independently from UTC-synchronized phase clock.

### Change 5: RX Size Tracking

RX needs to know expected packet size BEFORE the chip receives (chip's
SET_PACKET_PARAMS sets exact byte count for RX_DONE).

Solution: RX calls SET_PACKET_PARAMS with the expected size at each
sub-slot boundary, same as TX. Both compute from UTC → phase → sub-slot.

If RX misses the boundary transition, it re-arms with the new size on
next IRQ cycle. Lost packets during transition are expected (same as
phase boundary losses in current sweep).

### Change 6: PHASE_RESULT Reports Per-Size Statistics

When in interleave mode, RX tracks separate counters per size:

```
PHASE_RESULT 5 HF-FLRC-650
  size=32  rx=48 unique=48 lost=2 per=4.0 rssi=-42
  size=64  rx=47 unique=47 lost=3 per=6.0 rssi=-43
  size=128 rx=45 unique=45 lost=5 per=10.0 rssi=-43
  size=255 rx=42 unique=42 lost=8 per=16.0 rssi=-44
```

### Change 7: Embed pktSize in TX Header

Byte 14 (currently `fixQ`) gets a new field alongside — or repurpose the
high nibble. RX reads it to verify expected size matches actual.

Actually simpler: use seqInPhase % 4 as implicit size indicator. RX
already parses seq, so it knows which size each packet should be.

---

## Cycle Time Impact

| Mode | Fixed (per walk) | Interleave |
|------|-----------------|------------|
| FLRC phases | 8s each, unchanged | 8s each, 4 sub-slots of 2s |
| LoRa SF7 | 15s, unchanged | 15s, 4 sub-slots of 3.75s |
| LoRa SF12 | 50s, 10pkts | 50s, ~2-3 pkts per sub-slot |
| Total cycle | 202s | 202s (same!) |

Interleave mode has ZERO cycle time penalty. Each sub-slot is 1/4 of the
original phase slot.

---

## Packet Sizes: 32 / 64 / 128 / 255

Log-spaced 8× range:
- 32B: minimum viable telemetry payload (current proven sweep)
- 64B: mid-range, doubles throughput
- 128B: standard mesh packet
- 255B: maximum, tests throughput ceiling

---

## What Does NOT Change (from proven sweep)

- GPS parser (talker-ID agnostic)
- CDC watchdog (battery-safe)
- RSSI formula (int16_t tenths of dBm)
- FIFO clear opcode (0x20, correct)
- CRC-16 (CCITT 0x1021 over fixed 18-byte window)
- Firmware hash embedding
- Phase sync (SET_TIME + GPS primary)
- All 3 alignment fixes from commit 9b740aa
- Duplicate tracking bitmap
- Sync header search
