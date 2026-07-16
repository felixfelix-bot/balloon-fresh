# PIO TX v2 — CDC Dies During TX Loop (2026-07-16)

## Summary

PIO TX v2 (hybrid approach) successfully fixes CDC during init, but CDC output
is corrupted when PIO+DMA is active during the TX hot loop. Board survives
(doesn't crash to BOOTSEL like v1), but no TX results appear on USB CDC.

## What Was Tested

### PIO TX v1 (commit a7be8ba)
- PIO+DMA init in setup() before radio init
- **Result: CDC dead immediately.** Board crashed to BOOTSEL.
- Root cause: pico-sdk peripheral access (PIO, DMA, IRQ) before TinyUSB initialized

### PIO TX v2 (commit ea0aead)
- Arduino SPI for radio init (CDC-safe)
- spiRf.end() after init
- PIO+DMA init AFTER 8-second WAIT window (CDC confirmed alive)
- **Result: CDC alive through init + WAIT + PIO init.** "PIO INIT OK" printed.
- TX_START printed. Then CDC goes silent during TX loop.
- Board survives TX (PID 000a maintained).
- Sending "RUN" after PIO active → board crashes to BOOTSEL.

## Root Cause

PIO+DMA operations during the TX hot loop corrupt TinyUSB CDC state:
1. `dualPrintf()` calls `Serial.println()` while PIO SM is running and DMA channels are active
2. The PIO state machine drives SCK/MOSI via GPIO mux, which may conflict with TinyUSB's USB interrupt timing
3. DMA IRQ handler (`pio_dma_isr`) shares `DMA_IRQ_0` with TinyUSB's internal DMA — IRQ contention corrupts CDC state
4. The `while (!g_dma_done)` tight poll in `pioSpiXfer()` blocks the CPU, preventing TinyUSB from servicing USB interrupts

## Key Finding

**PIO+DMA and TinyUSB CDC are fundamentally incompatible on RP2040 when both
are active simultaneously.** The hybrid approach delays the conflict but cannot
eliminate it — any `Serial.print()` during PIO+DMA operations fails.

## Fix: UART-Only Output During PIO Mode

The solution is to redirect ALL output to Serial1 (UART GP12/GP13) during
PIO+DMA mode. Never touch Serial (CDC) once PIO is initialized:

```cpp
// Before PIO init: use dualPrintf (Serial + Serial1)
// After PIO init: use uartPrintf (Serial1 ONLY)
static void uartPrintf(const char *fmt, ...) {
    char buf[256];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    Serial1.println(buf);
}
```

This completely isolates CDC from PIO/DMA. UART hardware is separate from
both the SPI peripheral and TinyUSB, so it's unaffected by PIO/DMA operations.

## Test Results

| Version | Init CDC | TX Loop CDC | Board Survives | TX Results |
|---------|----------|-------------|----------------|------------|
| v1 (PIO-only) | DEAD | N/A | NO (BOOTSEL) | N/A |
| v2 (hybrid) | ALIVE ✓ | DEAD ✗ | YES ✓ | NOT CAPTURED |

## Board Recovery

8332 was recovered multiple times via 1200 baud BOOTSEL:
- v1 crash → 1200 baud → RPI-RP2 → flash v4 → OK
- v2 CDC silence → 1200 baud → RPI-RP2 → flash v4 → OK
- v2 RUN crash → 1200 baud → RPI-RP2 → flash v4 → OK

**1200 baud BOOTSEL remains the reliable recovery method** for earlephilhower
core (PID 000a). Works every time, 3-4 seconds to RPI-RP2 disk.

## Next Steps

1. Create `flrc_pio_tx_v3.cpp` — UART-only output during PIO mode
2. Flash to 8332, capture UART output via ESP32 bridge or direct USB
3. Check spin count (must be >0 for real RF) and throughput
4. If real: compare to 1377 kbps baseline
5. If fake: accept ceiling, move on