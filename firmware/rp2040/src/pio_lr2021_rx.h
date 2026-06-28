/*
 * pio_lr2021_rx.h — PIO + DMA gapless SPI RX for the LR2021 radio on RP2040
 * ============================================================================
 * (SPEED-P6 / ADR-015 RP2040 coprocessor)
 *
 * Replaces the CPU-polled MbedSPI FIFO read in radio.cpp with a single PIO
 * state machine that clocks the LR2021 SPI itself, drained/fed by two DMA
 * channels, double-buffered in SRAM.  The CPU only arms a capture on the
 * DIO9 "packet received" edge and reacts to the DMA-completion IRQ — zero
 * cycles spent on bit-banging the SPI clock.
 *
 * Transaction (matches the proven mesh-stack/flrc-bench-espidf fast_rx.cpp):
 *
 *     NSS low → TX DMA sends READ_RX_FIFO [0x00,0x01] + N dummy bytes
 *             → RX DMA captures 2+N bytes (2 cmd-echo + N payload)
 *     NSS high (in the DMA-completion ISR)
 *
 * Gapless / double-buffering
 * --------------------------
 * Two payload buffers live in SRAM (slot 0 and slot 1).  lr2021_rx_arm()
 * always fills the slot the CPU is NOT currently holding, so the CPU can
 * parse/log slot N while slot N+1 is already being captured.  The contract
 * is "consume (lr2021_rx_take) before the next arm" — satisfied by the
 * existing synchronous main-loop style in main.cpp.  (A free-running
 * DMA chain was rejected: LR2021 RX is packet-triggered by DIO9 and needs
 * per-packet NSS framing, so a continuously-clocked ring would not frame
 * packets correctly.  See pio_lr2021_rx.cpp "Double-buffer design".)
 *
 * Build
 * -----
 * The PIO program is in pio_lr2021_rx.pio (assembled form committed as
 * pio_lr2021_rx.pio.h).  Works under pico-sdk (CMake, pico_generate_pio_header)
 * or any RP2040 Arduino core that ships the hardware/pio.h + hardware/dma.h
 * headers — the C++ only needs the generated program struct.
 */

#ifndef PIO_LR2021_RX_H
#define PIO_LR2021_RX_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* LR2021 fixed-packet-length mode caps a FIFO read at 255 payload bytes. */
#define LR2021_RX_MAX_PAYLOAD   255u
/* READ_RX_FIFO command = 0x0001, sent MSB-first as [0x00, 0x01] (2 bytes). */
#define LR2021_RX_CMD_BYTES     2u
/* Default SCK (MHz).  SCK = sysclk / (2 * div); at 125 MHz sysclk and div=3
 * this is 20.83 MHz — well above the 18 MHz ESP32 baseline and fast enough
 * that a 255-byte read is ~99 us (<< 785 us on-air at 2.6 Mbps). */
#define LR2021_RX_DEFAULT_CLK   20.83f

/*
 * Load the PIO program, claim one state machine + two DMA channels, configure
 * pins and the DMA-completion IRQ.
 *   sck, mosi, miso, cs : RP2040 GPIO numbers (pins.h: 2, 3, 4, 5)
 *   clk_mhz             : desired SCK; clamped to the RP2040 ceiling.
 * Returns 0 on success, -1 if no free SM, -2 if no free DMA channel.
 */
int  lr2021_rx_init(uint8_t sck, uint8_t mosi, uint8_t miso,
                    uint8_t cs, float clk_mhz);

/* Release the SM, DMA channels and IRQ. */
void lr2021_rx_deinit(void);

/*
 * Set the payload length (bytes) the radio will deliver per packet
 * (1..LR2021_RX_MAX_PAYLOAD).  Stored and used by the next lr2021_rx_arm().
 */
void lr2021_rx_set_payload_len(size_t len);

/*
 * Arm one capture into the next ping-pong slot.
 *   - Forces SCK low (SPI Mode 0 idle), asserts NSS low.
 *   - Starts the TX DMA (cmd + dummy clocks) and RX DMA (payload capture);
 *     both run lockstep, paced by the PIO's TX/RX DREQs.
 * Returns the slot index (0 or 1) that WILL be filled, or -1 if a capture is
 * already in flight.  Call this when the LR2021 raises DIO9.
 */
int  lr2021_rx_arm(void);

/* True while a capture is in flight (between arm and DMA-completion IRQ). */
bool lr2021_rx_busy(void);

/*
 * Hand the most recently completed capture to the caller.
 *   *payload : set to the payload bytes (past the 2-byte command echo)
 *   *plen    : set to the payload length in bytes
 * Returns the slot index (0 or 1), or -1 if no completed frame is pending.
 * The pointer stays valid until the NEXT lr2021_rx_arm() reuses this slot —
 * copy/consume it before arming again.
 */
int  lr2021_rx_take(const uint8_t **payload, size_t *plen);

/* Deassert NSS (high).  Called automatically after each capture; exposed for
 * an explicit abort. */
void lr2021_rx_cs_high(void);

/* ---- diagnostics ------------------------------------------------------- */

/* Number of captures completed since init. */
uint32_t lr2021_rx_completed_count(void);
/* Number of arm() calls that were refused because a capture was in flight. */
uint32_t lr2021_rx_dropped_count(void);

#ifdef __cplusplus
}
#endif

#endif /* PIO_LR2021_RX_H */
