# FreeRTOS Task Architecture for Balloon Relay Firmware

**Date:** 2026-08-05
**Status:** DESIGN — awaiting implementation
**Blocker:** This design blocks ALL radio integration work (Phase 2+)

---

## PROBLEM

Current app_main.cpp has two mutually exclusive paths:
- Path A (default): TX-sleep (wake → sensors → TX → deep sleep). Radio OFF 99% of time.
- Path B (MeshCore): blocking `while(true) { mesh.loop(); }`. No RX event processing.

Neither supports store-and-forward relay. A relay must:
1. Continuously listen for incoming messages (always-on RX)
2. Process and verify received messages (Schnorr verify, ~100ms on C3)
3. Store messages for later forwarding (nostr_store)
4. Forward when neighbor available (TX on demand)
5. Still do telemetry and GPS tracking

## SOLUTION: 3 FreeRTOS Tasks

```
┌─────────────────────────────────────────────────────┐
│                   ESP32-C3 (1 core)                   │
│                                                       │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ radio_task  │  │  app_task    │  │  main_task   │ │
│  │ HIGH prio   │  │  MEDIUM prio │  │  MEDIUM prio │ │
│  │ 4KB stack   │  │  8KB stack   │  │  8KB stack   │ │
│  │             │  │              │  │              │ │
│  │ • DIO9 IRQ  │  │ • secp verify│  │ • GPS read   │ │
│  │ • RX packet │──▶│ • nostr_store│  │ • BMP280     │ │
│  │ • TX dispatch│  │ • tollgate   │  │ • telemetry  │ │
│  │ • SPI bus   │  │ • event proc │  │ • CLI        │ │
│  └─────────────┘  └──────────────┘  └──────────────┘ │
│         │                │                           │
│         ▼                ▼                           │
│  ┌──────────────────────────────┐                    │
│  │     FreeRTOS Queues           │                    │
│  │  rx_queue (8 slots × 512B)   │                    │
│  │  tx_queue (4 slots × 512B)   │                    │
│  └──────────────────────────────┘                    │
└─────────────────────────────────────────────────────┘
```

### Task 1: radio_task (HIGH priority, 4KB stack)

```c
void radio_task(void *arg) {
    // Init LR2021, configure DIO9 IRQ for RX_DONE
    // Main loop:
    while (1) {
        // If packet in tx_queue → TX it (blocks ~10ms for FLRC)
        // Else → enter RX mode, wait for DIO9 IRQ (light sleep, IRQ wakes)
        // On RX_DONE → read packet, push to rx_queue
        // If rx_queue full → drop (backpressure)
        xTaskNotifyWait(0, 0, NULL, pdMS_TO_TICKS(100)); // timeout 100ms
    }
}
```

Key points:
- IRQ-driven (DIO9 GPIO5). Not polling.
- TX is priority: if tx_queue has packet, TX first, then return to RX
- Half-duplex: can't TX and RX simultaneously. Accept packet loss during TX.
- SPI bus owned exclusively by this task (no concurrent SPI access)

### Task 2: app_task (MEDIUM priority, 8KB stack)

```c
void app_task(void *arg) {
    secp256k1_context *ctx = secp256k1_context_create(VERIFY);
    
    while (1) {
        // Block on rx_queue until packet arrives
        nostr_packet_t pkt;
        xQueueReceive(rx_queue, &pkt, portMAX_DELAY);
        
        // Deserialize → verify Schnorr sig → store
        if (nostr_event_deserialize(&pkt) == 0) {
            if (secp256k1_schnorrsig_verify(ctx, ...) == 1) {
                nostr_store_add(&event);
            }
        }
        
        // If tollgate PAY → process → queue ACK to tx_queue
        // If relay event → queue to tx_queue for forwarding
    }
}
```

Key points:
- Schnorr verify runs here (~100ms), blocks this task, NOT radio_task
- 8KB stack: verify may use 4-6KB stack depth
- secp context persistent (heap, ~2KB), created once at task start

### Task 3: main_task (existing, repurposed)

```c
void app_main(void) {
    // Init: NVS, SPIFFS, LittleFS, I2C, UART
    // Create rx_queue, tx_queue
    // Create radio_task, app_task
    
    // Main loop (was TX-sleep, now continuous):
    while (1) {
        read_gps();      // if GPS enabled
        read_bmp280();   // if BMP280 enabled
        compose_telemetry();
        
        // Queue telemetry TX (non-blocking)
        xQueueSend(tx_queue, &telemetry_pkt, 0);
        
        // CLI processing (non-blocking check)
        process_cli();
        
        // Light sleep (NOT deep sleep — radio_task needs to stay alive)
        vTaskDelay(pdMS_TO_TICKS(10000)); // 10s telemetry interval
    }
}
```

Key points:
- NO deep sleep (relay must stay alive)
- Light sleep via vTaskDelay (allows other tasks to run)
- Telemetry TX queued to tx_queue, radio_task sends it
- CLI runs here (interactive debug via USB serial)

## RESOURCE BUDGET

| Resource | Allocation |
|----------|-----------|
| rx_queue | 8 × 512B = 4KB heap |
| tx_queue | 4 × 512B = 2KB heap |
| radio_task stack | 4KB |
| app_task stack | 8KB |
| main_task stack | 8KB (existing) |
| secp context | ~2KB heap |
| **Total task overhead** | ~28KB |

With 219KB free heap after components: 219 - 28 = 191KB remaining. Plenty.

## IMPLEMENTATION NOTES

1. Create `radio_task.cpp` in `main/` — handles IRQ setup, RX/TX loop
2. Create `app_task.cpp` in `main/` — handles event processing pipeline
3. Modify `app_main.cpp` — remove TX-sleep path, add task creation
4. Add `#ifdef CONFIG_NODE_ROLE_RELAY` — relay mode uses tasks, tracker-only mode keeps sleep
5. Pin definitions: DIO9 (GPIO5) → GPIO interrupt for RX_DONE

## DECISION POINTS

1. **Light sleep vs no sleep?** Light sleep saves ~30% power vs active. But adds wake latency. For V1 bench testing: no sleep (always active). For flight: light sleep between events.

2. **Queue sizes?** rx_queue=8 handles burst of 8 events. At 22kbps FLRC with 255B packets, that's 8 × ~100ms = 800ms of buffering. Sufficient for single-hop.

3. **Where does MeshCore fit?** If CONFIG_ENABLE_MESHCORE, radio_task runs mesh.loop() instead of raw RX. MeshCore handles its own timing. But this conflicts with raw RX. Decision: for V1, disable MeshCore, use raw RX path. Add MeshCore as Phase 5 polish.
