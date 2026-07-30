#ifndef RADIO_ADAPTER_H
#define RADIO_ADAPTER_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 * radio_adapter — bridges mesh_service_mux → lr2021_transport.
 *
 * Enables tollgate mesh packets to flow over LR2021 FLRC radio
 * instead of WiFi-only. Uses dependency-injection: registers
 * radio_adapter_send as the tollgate mesh send callback.
 *
 * Send path:  upper layer → radio_adapter_send()
 *               → mesh_service_mux_wrap(SVC_TOLLGATE)
 *               → EspHalLr2021Radio::send_packet()
 *
 * Recv path:  EspHalLr2021Radio::read_packet()
 *               → mesh_service_mux_unwrap()
 *               → tollgate_balloon_on_mesh_frame()
 */

/*
 * Initialize the radio adapter.
 * Configures LR2021 radio, enters RX mode, registers send callback
 * with tollgate_balloon.
 *
 * @param freq_mhz    RF frequency (default 2440.0)
 * @param payload_len FLRC payload length in bytes (default 255)
 * @return 0 on success, negative on error
 */
int radio_adapter_init(float freq_mhz, uint8_t payload_len);

/*
 * Send a mesh frame over LR2021 radio.
 * Wraps with mesh_service_mux (prepends 1-byte service tag),
 * then transmits via EspHalLr2021Radio::send_packet().
 *
 * Called by tollgate_balloon via registered callback.
 *
 * @param data Mesh frame data
 * @param len  Frame length
 */
void radio_adapter_send(const uint8_t *data, uint16_t len);

/*
 * Poll for received packets.
 * Checks LR2021 IRQ, reads packet if available, unwraps service mux,
 * dispatches to appropriate handler.
 *
 * Call from main loop (1Hz or faster).
 */
void radio_adapter_poll(void);

/*
 * Get radio status for debug/reporting.
 * Returns RSSI of last received packet, or 0 if none.
 */
int8_t radio_adapter_last_rssi(void);

#ifdef __cplusplus
}
#endif

#endif /* RADIO_ADAPTER_H */
