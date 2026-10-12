/*
 * radio_adapter.cpp — Concrete bridge: mesh_service_mux ↔ lr2021_transport.
 *
 * Implements the callbacks that mesh_adapter and tollgate_balloon expect,
 * backed by actual LR2021 SPI radio calls via Lr2021Transport.
 *
 * See radio_adapter.h for the full data-flow diagram.
 *
 * Design follows blossom_datagram's dependency-injection pattern:
 *   - mesh_adapter_config_t.send_fn → our mesh_to_radio_send_fn
 *   - tollgate_mesh_send_fn         → our tollgate_to_mesh_send_fn
 *   - RX task: transport.recv() → mesh_adapter_receive_frame() → mux → tollgate
 */
#include "radio_adapter.h"

#include "lr2021_transport.h"   // Lr2021Transport, TransportError
#include "esp_idf_lr2021_radio.h" // EspHalLr2021Radio
#include "mesh_adapter.h"        // mesh_adapter_init/send/receive_frame
#include "mesh_service_mux.h"    // mesh_service_mux_wrap/unwrap
#include "tollgate_balloon.h"    // tollgate_balloon_register_mesh/on_mesh_frame

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <string.h>

static const char *TAG = "radio_adapter";

// ── Static instances (own the radio + transport for program lifetime) ──
static EspHalLr2021Radio *s_radio     = nullptr;
static Lr2021Transport   *s_transport  = nullptr;

// Frame queue for mesh_adapter (tracks outbound fragments for inspection)
static mesh_frame_queue_t s_tx_queue;

// ── Buffer sizes ──
// A mesh frame fragment ≤ 128 bytes (frag_size). With 2-byte length prefix,
// a complete framed unit ≤ 130 bytes. We allow headroom for coalesced frames.
#define RA_STREAM_CAP     1200   // RX stream accumulation buffer
#define RA_RECV_CHUNK     300    // Single transport.recv() call buffer
#define RA_MAX_FRAME      600    // Max single frame before length prefix
#define RA_REASM_BUF      512    // mesh_adapter_receive_frame output

// ═══════════════════════════════════════════════════════════════════════
// SEND PATH: mesh_adapter → lr2021_transport
// ═══════════════════════════════════════════════════════════════════════

/*
 * mesh_frame_send_fn callback — called by mesh_adapter for each fragment.
 *
 * Adds a 2-byte LE length prefix (per transport framing convention) and
 * pushes the framed unit through the transport stream. flush_tx() ensures
 * the radio transmits immediately rather than buffering for coalescing.
 */
static void mesh_to_radio_send_fn(const uint8_t *frame, uint16_t len)
{
    if (!s_transport || !frame || len == 0)
        return;

    // 2-byte LE length prefix — the stream is self-delimiting
    uint8_t hdr[2] = {
        (uint8_t)(len & 0xFF),
        (uint8_t)((len >> 8) & 0xFF),
    };

    s_transport->send(hdr, 2);
    s_transport->send(frame, len);
    s_transport->flush_tx();
}

// ═══════════════════════════════════════════════════════════════════════
// SEND PATH: tollgate_balloon → mesh_adapter
// ═══════════════════════════════════════════════════════════════════════

/*
 * tollgate_mesh_send_fn callback — called by tollgate_balloon when it has
 * a response (ACK/NACK/INFO) to send over the mesh.
 *
 * Wraps the tollgate payload with a 1-byte SVC_TOLLGATE mux tag, then hands
 * it to mesh_adapter_send() which fragments, optionally encrypts, and calls
 * mesh_to_radio_send_fn for each fragment.
 */
static void tollgate_to_mesh_send_fn(const uint8_t *data, uint16_t len)
{
    if (!data || len == 0)
        return;

    // Wrap with service mux: 1-byte tag + payload
    uint8_t wrapped[1 + RA_MAX_FRAME];
    if ((size_t)len + 1 > sizeof(wrapped)) {
        ESP_LOGW(TAG, "tollgate payload %u exceeds mux buffer", len);
        return;
    }

    int wlen = mesh_service_mux_wrap(MESH_SVC_TOLLGATE, data, len,
                                      wrapped, sizeof(wrapped));
    if (wlen < 0) {
        ESP_LOGW(TAG, "mux_wrap failed: %d", wlen);
        return;
    }

    // Send through mesh_adapter (fragments → mesh_to_radio_send_fn per fragment)
    mesh_result_t r = mesh_adapter_send(wrapped, (uint16_t)wlen,
                                         /*frag_size=*/128,
                                         /*redundancy=*/1);
    if (r != MESH_OK) {
        ESP_LOGW(TAG, "mesh_adapter_send failed: %d", (int)r);
    }
}

// ═══════════════════════════════════════════════════════════════════════
// RECV PATH: lr2021_transport → mesh_adapter → mux → tollgate_balloon
// ═══════════════════════════════════════════════════════════════════════

/*
 * RX task — continuously polls the transport for incoming stream data,
 * parses 2-byte LE length-prefixed frames, feeds complete frames to
 * mesh_adapter_receive_frame(), and routes reassembled messages to
 * tollgate_balloon_on_mesh_frame() via the service mux.
 *
 * The transport's recv() blocks for up to RADIO_TIMEOUT_MS (5s) waiting
 * for data, polling the IRQ pin internally. On timeout it returns
 * TransportError::Timeout with n_out=0, and we simply loop again.
 */
static void radio_rx_task(void *arg)
{
    (void)arg;

    // Stream accumulation buffer — holds partial + complete framed units
    uint8_t stream_buf[RA_STREAM_CAP];
    size_t  stream_len = 0;

    // Per-iteration recv buffer
    uint8_t recv_buf[RA_RECV_CHUNK];

    // Reassembled output from mesh_adapter
    uint8_t  out_data[RA_REASM_BUF];

    ESP_LOGI(TAG, "RX task started");

    while (true) {
        size_t n = 0;
        TransportError err = s_transport->recv(recv_buf, sizeof(recv_buf), &n);

        if (err != TransportError::Ok || n == 0)
            continue;  // Timeout or error — just loop

        // Append received bytes to stream buffer
        if (stream_len + n > sizeof(stream_buf)) {
            ESP_LOGW(TAG, "stream buffer overflow (%zu + %zu > %zu), resetting",
                     stream_len, n, sizeof(stream_buf));
            stream_len = 0;
        }
        memcpy(stream_buf + stream_len, recv_buf, n);
        stream_len += n;

        // Parse length-prefixed frames from the accumulated stream
        size_t pos = 0;
        while (pos + 2 <= stream_len) {
            uint16_t frame_len = (uint16_t)stream_buf[pos]
                               | ((uint16_t)stream_buf[pos + 1] << 8);

            // Sanity check — reject absurd frame sizes
            if (frame_len == 0 || frame_len > RA_MAX_FRAME) {
                ESP_LOGW(TAG, "invalid frame_len %u at pos %zu, resetting stream",
                         frame_len, pos);
                stream_len = 0;
                break;
            }

            // Need more bytes to complete this frame
            if (pos + 2 + (size_t)frame_len > stream_len)
                break;

            // Complete frame — feed to mesh_adapter for reassembly
            uint16_t  out_len = 0;
            mesh_result_t r = mesh_adapter_receive_frame(
                stream_buf + pos + 2, frame_len,
                out_data, &out_len, sizeof(out_data));

            if (r == MESH_OK && out_len > 0) {
                // Reassembly complete — unwrap service mux and route
                uint8_t         svc = 0;
                const uint8_t  *payload = nullptr;
                uint16_t        payload_len = 0;

                int mr = mesh_service_mux_unwrap(out_data, out_len,
                                                  &svc, &payload, &payload_len);
                if (mr == MESH_MUX_OK && payload && payload_len > 0) {
                    if (svc == MESH_SVC_TOLLGATE) {
                        tollgate_balloon_on_mesh_frame(
                            "unknown", payload, payload_len);
                    }
                    // Other services (NOSTR, BLOSSOM) silently ignored —
                    // routed by their respective handlers when integrated.
                }
            }

            pos += 2 + (size_t)frame_len;
        }

        // Compact unconsumed bytes to the front of the buffer
        if (pos > 0) {
            size_t remaining = stream_len - pos;
            if (remaining > 0)
                memmove(stream_buf, stream_buf + pos, remaining);
            stream_len = remaining;
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════
// INIT — wire the entire stack
// ═══════════════════════════════════════════════════════════════════════

esp_err_t radio_adapter_init(void)
{
    ESP_LOGI(TAG, "initializing radio adapter");

    // 1. Create radio hardware driver + transport wrapper
    s_radio = new EspHalLr2021Radio();  // default pin config (proven firmware)
    s_transport = new Lr2021Transport(s_radio);

    // 2. Init radio: init_hardware() → 17-step FLRC config → start_rx()
    //    (EspHalLr2021Radio::init() calls init_hardware() internally)
    Lr2021Config config;  // defaults: 2440 MHz, 2600 kbps, +12 dBm, 255-byte payload
    TransportError terr = s_transport->init(config);
    if (terr != TransportError::Ok) {
        ESP_LOGE(TAG, "transport init failed (err=%d) — radio not present?", (int)terr);
        // Non-fatal: tollgate works without mesh radio. Caller may continue.
        delete s_transport;
        delete s_radio;
        s_transport = nullptr;
        s_radio = nullptr;
        return ESP_FAIL;
    }

    // 3. Init mesh_adapter with our radio-backed send callback
    memset(&s_tx_queue, 0, sizeof(s_tx_queue));
    mesh_adapter_config_t macfg = {};
    macfg.send_fn      = mesh_to_radio_send_fn;
    macfg.tx_queue     = &s_tx_queue;
    macfg.encrypt_fn   = nullptr;  // No FIPS encryption yet (plaintext passthrough)
    macfg.decrypt_fn   = nullptr;
    macfg.encrypt_ctx  = nullptr;
    macfg.decrypt_ctx  = nullptr;
    mesh_adapter_init(&macfg);

    // 4. Register mesh send callback with tollgate_balloon
    //    (tollgate_balloon_init() must have been called first)
    tollgate_balloon_register_mesh(tollgate_to_mesh_send_fn);

    // 5. Start RX task
    //    6 KB stack: stream_buf(1200) + recv_buf(300) + out_data(512) +
    //    mesh_adapter stack frames (reasm_buf 512) + FreeRTOS overhead
    xTaskCreate(radio_rx_task, "radio_rx", 6144, nullptr, 5, nullptr);

    ESP_LOGI(TAG, "radio adapter ready (FLRC 2440 MHz, 2600 kbps, +12 dBm)");
    return ESP_OK;
}
