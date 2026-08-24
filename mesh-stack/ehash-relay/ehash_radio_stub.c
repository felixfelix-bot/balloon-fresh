/**
 * @file ehash_radio_stub.c
 * @brief Stubs for LR2021 TX/RX (Phase D integration point).
 *
 * The real LR2021 driver (firmware/esp32-c3-flrc/main/main.cpp) uses
 * raw 2-byte opcode SPI. This stub provides the callback interface so
 * the relay component builds and tests on host (gcc) without hardware.
 *
 * In Phase D, replace these with calls to:
 *   rf_write_tx_fifo(data, len) → SET_TX (downlink broadcast)
 *   rf_read_rx_fifo(buf, len) ← SET_RX IRQ (uplink nonce receive)
 *
 * The stub records TX calls into a capture buffer for test verification.
 */

#include "ehash_relay.h"
#include <string.h>

/* ========================================================================
 *  TX Broadcast Stub — records last broadcast for test inspection
 * ======================================================================== */

/** Capture buffer for the last broadcast message. */
typedef struct {
    uint8_t  data[EHASH_RELAY_MAX_PAYLOAD];
    size_t   len;
    int      call_count;
} ehash_radio_broadcast_capture_t;

static ehash_radio_broadcast_capture_t s_broadcast_cap;

int ehash_radio_stub_broadcast(const uint8_t *data, size_t len, void *ctx) {
    (void)ctx;
    if (!data || len > EHASH_RELAY_MAX_PAYLOAD) return -1;
    memcpy(s_broadcast_cap.data, data, len);
    s_broadcast_cap.len = len;
    s_broadcast_cap.call_count++;
    return 0;
}

const uint8_t *ehash_radio_stub_get_last_broadcast(size_t *out_len) {
    if (out_len) *out_len = s_broadcast_cap.len;
    return s_broadcast_cap.data;
}

int ehash_radio_stub_get_broadcast_count(void) {
    return s_broadcast_cap.call_count;
}

void ehash_radio_stub_reset(void) {
    memset(&s_broadcast_cap, 0, sizeof(s_broadcast_cap));
}

/* ========================================================================
 *  TX Unicast Stub — records last unicast (credit/result) for inspection
 * ======================================================================== */

typedef struct {
    uint32_t station_id;
    uint8_t  data[64];  /* CREDIT is 17 bytes, RESULT is 8 bytes */
    size_t   len;
    int      call_count;
} ehash_radio_unicast_capture_t;

static ehash_radio_unicast_capture_t s_unicast_cap;

int ehash_radio_stub_unicast(uint32_t station_id,
                              const uint8_t *data, size_t len, void *ctx)
{
    (void)ctx;
    if (!data || len > sizeof(s_unicast_cap.data)) return -1;
    s_unicast_cap.station_id = station_id;
    memcpy(s_unicast_cap.data, data, len);
    s_unicast_cap.len = len;
    s_unicast_cap.call_count++;
    return 0;
}

const uint8_t *ehash_radio_stub_get_last_unicast(uint32_t *out_station, size_t *out_len) {
    if (out_station) *out_station = s_unicast_cap.station_id;
    if (out_len)     *out_len     = s_unicast_cap.len;
    return s_unicast_cap.data;
}

int ehash_radio_stub_get_unicast_count(void) {
    return s_unicast_cap.call_count;
}

/* ========================================================================
 *  RX Stub — simulate receiving a nonce from a ground station
 * ========================================================================
 *  In tests, you encode a nonce and pass it to ehash_relay_on_nonce()
 *  directly. In Phase D, the real RX path will be an interrupt-driven
 *  callback that reads the LR2021 RX FIFO and calls ehash_relay_on_nonce().
 */

/* ========================================================================
 *  ESP-IDF Integration Hook (compiled only on target)
 * ======================================================================== */

#ifdef ESP_PLATFORM

/*
 * On the real ESP32-C3, the radio callbacks will wrap the proven LR2021
 * raw SPI driver. The integration is straightforward:
 *
 *   int ehash_radio_tx_real(const uint8_t *data, size_t len, void *ctx) {
 *       rf_write_tx_fifo(data, len);
 *       uint8_t set_tx[] = { 0x02, 0x0D, 0x00, 0x00, 0x00 };
 *       rf_write_cmd(set_tx, 5);
 *       // wait for TX_DONE IRQ
 *       return 0;
 *   }
 *
 * The stubs above are for host-side unit tests. The CMakeLists.txt
 * conditionally compiles this file only when NOT on target.
 */

#endif /* ESP_PLATFORM */
