# TDMA Scheduler Design for Balloon Mesh

## Frame Structure

```
TDMA Frame (2 seconds total)
┌──────────┬──────────┬──────────┬──────────┐
│  Slot 0  │  Slot 1  │  Slot 2  │  Slot 3  │
│  BEACON  │ TX SUB   │ TX 2G4   │ CONTENT  │
│  Sub-GHz │  Sub-GHz │  2.4 GHz │  Sub-GHz │
│ 500ms    │ 500ms    │  500ms   │  500ms   │
│  ┤499.8├  │  ┤499.8├  │  ┤499.8├  │  ┤499.8├  │
│  guard   │  guard   │  guard   │  guard   │
└──────────┴──────────┴──────────┴──────────┘
```

Guard band: 200 us between slots (TX→RX turnaround for LR2021).

## Slot Types

| Type | Purpose | Band | Notes |
|------|---------|------|-------|
| BEACON | Sync + announce presence | Sub-GHz | Coordinator only |
| TX | Transmit data | Sub-GHz or 2.4 GHz | Data slot |
| RX | Receive data | Sub-GHz or 2.4 GHz | Listen slot |
| SLEEP | Power saving | — | Deep sleep or idle |
| CONTENTION | New node join / random access | Sub-GHz | CSMA-like |

## Dual-Band Allocation

| Band | Purpose | Protocol | Slot |
|------|---------|----------|------|
| Sub-GHz (868 MHz) | MeshCore repeater | MeshCore | Slot 1 |
| 2.4 GHz | FIPS transport | FIPS/FSP | Slot 2 |

The balloon alternates between bands within a single TDMA frame.

## Clock Synchronization

### Primary: GPS PPS
- Balloon has GPS with PPS output
- PPS pulse resets the frame timer to 0
- Accuracy: ±1 μs (GPS PPS spec)
- Works in flight (GPS always has sky view)

### Fallback: LoRa Beacon
- Coordinator transmits beacon in Slot 0
- Beacon includes: frame_number, coordinator_id, slot_assignments
- Ground stations sync from beacon (one-way, no ACK needed)
- Accuracy: ±1 ms (LoRa TX time)

### Coordinator Election
- **Balloon is natural coordinator**: visible to all ground stations
- Ground stations can't see each other (over horizon)
- If multiple balloons: higher callsign hash wins
- Coordinator sends beacons; non-coordinators listen

## State Machine Per Slot

```
IDLE → WAITING → ACTIVE → DONE
  ↑                            │
  └────────────────────────────┘
```

- IDLE: Not started yet
- WAITING: In guard band before slot
- ACTIVE: Slot is active, TX/RX happening
- DONE: Slot complete, waiting for next

## Implementation

Component: `tracker/firmware/components/tdma/`

API:
- `tdma_init(frame_us, num_slots)` — configure frame
- `tdma_set_slot(index, type, band, duration)` — set slot parameters
- `tdma_start()` — begin frame cycle
- `tdma_tick(elapsed_us)` — advance timer (called from main loop or timer ISR)
- `tdma_pps_pulse()` — called from GPIO ISR on GPS PPS
- Callbacks: `tx_cb(slot, band)` and `rx_cb(slot, band, data, len)`

Static allocation only. No malloc.

## Host Tests (7/7 passing)

1. Init and slot configuration
2. Slot type configuration (TX, RX, BEACON, CONTENTION)
3. Full frame cycle with TX callbacks
4. Guard bands present in all slots
5. PPS discipline resets frame time
6. Stop halts scheduler
7. Overlap detection (all slots fit in frame)

## Bandwidth Budget

| Mode | Frame | Slots | Payload/slot | Throughput |
|------|-------|-------|-------------|------------|
| Tracker | 120s | 1 TX | 28 B | 1.9 bps |
| Mesh V1 | 2s | 2 TX | 200 B | 1.6 kbps |
| Mesh V2 | 2s | 2 TX | 200 B | 1.6 kbps |

## LR2021 TX→RX Turnaround

- LR2021 datasheet: ~200 us mode switch
- Guard band of 200 us is sufficient
- Total overhead per frame: 4 × 200 us = 800 us (0.04% of 2s frame)
