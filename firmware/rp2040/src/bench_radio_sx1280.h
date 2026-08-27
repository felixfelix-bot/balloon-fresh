/**
 * @file    bench_radio_sx1280.h
 * @brief   bench_radio_ops_t implementation for RP2040 + LR2021 (HARM-T5).
 *
 * Raw-SPI radio ops for the RP2040BENCH console core (see rp2040_bench.h)
 * plus the IRQ->event service pump the firmware main loop must call.
 */

#ifndef BENCH_RADIO_SX1280_H
#define BENCH_RADIO_SX1280_H

#include "bench/rp2040_bench.h"

#ifdef __cplusplus
extern "C" {
#endif

/** Radio ops bound into bench_io_t at boot (single LR2021 on spi0). */
extern const bench_radio_ops_t bench_radio_sx1280_ops;

/** SPI bring-up (pins, bus). Call once from setup() before bench_rp2040_init. */
void bench_radio_sx1280_begin(void);

/**
 * Poll the radio IRQ status once and fold events into the console core:
 * RX_DONE -> bench_rp2040_rx_event(payload) + re-arm continuous RX,
 * CRC_ERROR -> bench_rp2040_rx_event(NULL, ...) + re-arm,
 * TX_DONE/TIMEOUT -> cleared (tx_packet() is a synchronous BUSY-wait).
 * Non-RX roles only clear pending IRQs. Call from loop().
 */
void bench_radio_sx1280_service(void);

#ifdef __cplusplus
}
#endif

#endif /* BENCH_RADIO_SX1280_H */
