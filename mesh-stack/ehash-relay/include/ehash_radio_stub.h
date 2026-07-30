/**
 * @file ehash_radio_stub.h
 * @brief Test stubs for LR2021 radio TX/RX (host test only).
 *
 * Provides capture-buffer callbacks for unit testing the relay module
 * without real radio hardware.
 */

#ifndef EHASH_RADIO_STUB_H
#define EHASH_RADIO_STUB_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* --- TX callbacks (match ehash_radio_tx_fn / ehash_radio_tx_unicast_fn) --- */

int ehash_radio_stub_broadcast(const uint8_t *data, size_t len, void *ctx);

int ehash_radio_stub_unicast(uint32_t station_id,
                              const uint8_t *data, size_t len, void *ctx);

/* --- Capture buffer accessors for test verification --- */

const uint8_t *ehash_radio_stub_get_last_broadcast(size_t *out_len);

int ehash_radio_stub_get_broadcast_count(void);

const uint8_t *ehash_radio_stub_get_last_unicast(uint32_t *out_station,
                                                  size_t *out_len);

int ehash_radio_stub_get_unicast_count(void);

void ehash_radio_stub_reset(void);

#ifdef __cplusplus
}
#endif

#endif /* EHASH_RADIO_STUB_H */
