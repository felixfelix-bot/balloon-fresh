/*
 * radio_adapter.h — Bridge between mesh_service_mux and lr2021_transport.
 *
 * This is the "glue" that connects the abstract mesh layer (mesh_adapter +
 * mesh_service_mux + tollgate_balloon) to the physical LR2021 FLRC radio.
 *
 * Data flow:
 *
 *   SEND (tollgate → radio):
 *     tollgate_balloon → tollgate_mesh_send_fn (our callback)
 *       → mesh_service_mux_wrap(SVC_TOLLGATE, ...)
 *       → mesh_adapter_send() → pipeline fragmentation
 *       → mesh_frame_send_fn (our callback)
 *       → [2-byte LE length prefix] + lr2021_transport.send() + flush_tx()
 *
 *   RECV (radio → tollgate):
 *     lr2021_transport.recv() → stream bytes
 *       → parse 2-byte LE length-prefixed frames
 *       → mesh_adapter_receive_frame() → pipeline reassembly
 *       → mesh_service_mux_unwrap() → demux by service ID
 *       → tollgate_balloon_on_mesh_frame() for SVC_TOLLGATE
 *
 * The length-prefix framing is required because lr2021_transport provides
 * a raw byte stream (the framing layer chunks into FLRC packets but adds
 * no delimiters). Per the transport's own documentation: "The upper-layer
 * FrameWriter already wraps payloads with a 2-byte LE length prefix, so
 * the stream is self-delimiting." radio_adapter IS that upper layer.
 *
 * Follows the dependency-injection pattern from blossom_datagram:
 * callbacks are wired at init time, no hard coupling between layers.
 */
#ifndef RADIO_ADAPTER_H
#define RADIO_ADAPTER_H

#include "esp_err.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Initialize the radio adapter — wires the entire mesh stack:
 *   1. Create + init EspHalLr2021Radio (SPI bus + GPIO + 17-step FLRC config)
 *   2. Create Lr2021Transport wrapping the radio
 *   3. Init mesh_adapter with our radio-backed send callback
 *   4. Register mesh send callback with tollgate_balloon
 *   5. Spawn RX task that polls the radio and feeds frames up the stack
 *
 * Must be called AFTER tollgate_balloon_init().
 *
 * @return ESP_OK on success, ESP_FAIL if radio hardware is not present
 *         (non-fatal — tollgate continues without mesh transport).
 */
esp_err_t radio_adapter_init(void);

#ifdef __cplusplus
}
#endif

#endif /* RADIO_ADAPTER_H */
