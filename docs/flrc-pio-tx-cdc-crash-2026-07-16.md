# PIO+DMA SPI TX — CDC Crash Analysis (2026-07-16)

## What Happened

Built `flrc_pio_tx.cpp` (commit a7be8ba) using PIO state machine + DMA for SPI transfers instead of Arduino per-byte SPI. Build succeeded. Flashed to 8332.

**Result: CDC dead.** Zero output on USB serial. RP2040 crashed during `pioSpiInit()` or `rawInitRadio()`. Same symptom as the direct HW SPI crash from earlier — TinyUSB CDC killed by hardware peripheral access.

Board recovered via 1200 baud BOOTSEL, v4 baseline restored. Board confirmed functional (spin=13512, TX_DONE working).

## Root Cause Analysis

The PIO TX firmware calls `pioSpiInit()` in `setup()` BEFORE `rawInitRadio()`. This function:

1. Claims PIO state machine (`pio_claim_unused_sm`)
2. Loads PIO program (`pio_add_program`)
3. Configures DMA channels (`dma_claim_unused_channel`)
4. Registers DMA IRQ handler (`irq_add_shared_handler(DMA_IRQ_0, ...)`)
5. Enables DMA IRQ (`irq_set_enabled(DMA_IRQ_0, true)`)
6. Starts the PIO SM (`pio_sm_set_enabled`)

Any of these steps can crash TinyUSB CDC:
- **DMA_IRQ_0 registration** — TinyUSB may use this IRQ internally
- **PIO SM start with empty TX FIFO** — SM stalls on `out` but SCK is being driven by PIO, conflicting with Arduino SPI which also uses SCK pin (GP2)
- **Pin conflict** — PIO claims GP2 (SCK), GP3 (MOSI), GP4 (MISO) via `pio_gpio_init()`, but Arduino SPI (`SPIClassRP2040`) also claims these pins via `spiRf.begin()`. The PIO firmware does NOT call `spiRf.begin()` — but it does call `pio_gpio_init()` which changes the GPIO mux to PIO function, which may conflict with TinyUSB's GPIO usage.

## The Fundamental Problem

**Same pattern as direct HW SPI:** Any pico-sdk hardware peripheral access (PIO, DMA, IRQ registration) during or before TinyUSB CDC initialization risks crashing CDC. The Arduino SPI class is the ONLY CDC-safe SPI path.

## Fix: Hybrid Approach

Use Arduino SPI for radio init (CDC-safe), then switch to PIO+DMA only inside the TX hot loop (after CDC is established and all init output printed):

```
setup():
  1. Serial.begin() + Serial1.begin()  // CDC starts
  2. spiRf.begin()                     // Arduino SPI (CDC-safe)
  3. rawInitRadio() via Arduino SPI    // Radio init (CDC-safe)
  4. Print INIT + WAIT messages         // CDC output verified
  5. spiRf.end()                       // Release Arduino SPI
  6. pioSpiInit()                       // PIO+DMA init (CDC already alive)
  7. runTransmit()                     // PIO SPI hot loop
```

This ensures CDC is fully operational before any pico-sdk peripheral access.

**Alternative fix:** Don't use PIO at all. Accept 1377 kbps as the Arduino SPI ceiling.

## Board Recovery Log

1. 8332 flashed with PIO TX firmware → CDC dead, board crashed to BOOTSEL
2. 1200 baud triggered BOOTSEL → RPI-RP2 appeared after 4s
3. v4 baseline UF2 copied → 8332 rebooted
4. v4 confirmed working: spin=13512, TX_DONE 1000/1000, 1377 kbps
5. Board fully functional, no hardware damage

## Lesson

PIO+DMA is NOT automatically CDC-safe just because it avoids `spi0_hw` registers. The PIO subsystem, DMA channels, and IRQ registration all touch pico-sdk hardware that can conflict with TinyUSB. The safe sequence is: **all Arduino SPI for init, swap to PIO only after CDC is confirmed alive.**