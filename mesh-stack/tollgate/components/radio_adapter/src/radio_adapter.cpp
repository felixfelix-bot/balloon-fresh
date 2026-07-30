/*
 * radio_adapter.cpp — bridges mesh_service_mux → lr2021_transport.
 *
 * Wire format on air:
 *   Byte 0      : service ID (MESH_SVC_TOLLGATE / NOSTR / BLOSSOM)
 *   Bytes 1..N  : service payload (opaque)
 *
 * Integration:
 *   radio_adapter_init() → configures radio + registers as tollgate mesh sender
 *   radio_adapter_send() → called by tollgate_balloon via callback
 *   radio_adapter_poll() → called from main loop, dispatches to tollgate_balloon_on_mesh_frame
 */

#include "radio_adapter.h"
#include "mesh_service_mux.h"

#ifdef ESP_PLATFORM

// ── ESP-IDF build: use real hardware ────────────────────────────────
#include "esp_idf_lr2021_radio.h"
#include "tollgate_balloon.h"
#include "esp_log.h"

static const char *TAG = "radio_adapter";

static EspHalLr2021Radio s_radio;
static bool s_initialized = false;
static int8_t s_last_rssi = 0;

// Mesh send callback (registered into tollgate_balloon)
static void mesh_send_handler(const uint8_t *data, uint16_t len) {
    radio_adapter_send(data, len);
}

int radio_adapter_init(float freq_mhz, uint8_t payload_len) {
    if (s_initialized) {
        ESP_LOGW(TAG, "already initialized");
        return 0;
    }

    Lr2021Config config;
    config.freq_mhz = freq_mhz > 0 ? freq_mhz : 2440.0f;
    config.payload_length = payload_len > 0 ? payload_len : 255;
    config.tx_power_dbm = 12;

    Lr2021Error err = s_radio.init(config);
    if (err != Lr2021Error::Ok) {
        ESP_LOGE(TAG, "LR2021 init failed: %d", (int)err);
        return -(int)err;
    }

    // Register as tollgate mesh sender (dependency injection)
    tollgate_balloon_register_mesh(mesh_send_handler);

    // Enter RX mode
    err = s_radio.start_rx();
    if (err != Lr2021Error::Ok) {
        ESP_LOGE(TAG, "start_rx failed: %d", (int)err);
        return -(int)err;
    }

    s_initialized = true;
    ESP_LOGI(TAG, "radio adapter ready (%.1f MHz, %d-byte payload)",
             config.freq_mhz, (int)config.payload_length);
    return 0;
}

void radio_adapter_send(const uint8_t *data, uint16_t len) {
    if (!s_initialized || !data || len == 0) return;

    // Wrap with service mux: prepend 1-byte service tag
    uint8_t wrapped[512];  // max FLRC payload + 1 byte service tag
    if (len + 1 > sizeof(wrapped)) {
        ESP_LOGE(TAG, "frame too large: %u", len);
        return;
    }

    // Use TOLLGATE service by default. Upper layers can set the tag
    // themselves if they want to send NOSTR/BLOSSOM frames.
    int wrapped_len = mesh_service_mux_wrap(MESH_SVC_TOLLGATE, data, len,
                                              wrapped, sizeof(wrapped));
    if (wrapped_len < 0) {
        ESP_LOGE(TAG, "mux_wrap failed: %d", wrapped_len);
        return;
    }

    Lr2021Error err = s_radio.send_packet(wrapped, (size_t)wrapped_len);
    if (err != Lr2021Error::Ok) {
        ESP_LOGE(TAG, "send_packet failed: %d", (int)err);
        return;
    }

    // Re-arm RX after TX
    s_radio.clear_irq();
    s_radio.start_rx();
}

void radio_adapter_poll(void) {
    if (!s_initialized) return;

    // Check for received packet via IRQ status
    uint32_t flags = 0;
    Lr2021Error err = s_radio.get_irq_status(flags);
    if (err != Lr2021Error::Ok || flags == 0) return;

    // Check RX_DONE (bit 18)
    if (flags & (1U << 18)) {
        uint8_t buf[512];
        PacketStatus status;
        err = s_radio.read_packet(buf, sizeof(buf), status);
        s_last_rssi = (int8_t)(-status.rssi_dbm);

        if (err == Lr2021Error::Ok && status.length > 1) {
            // Unwrap service mux
            uint8_t svc = 0;
            const uint8_t *payload = nullptr;
            uint16_t payload_len = 0;

            int rc = mesh_service_mux_unwrap(buf, (uint16_t)status.length,
                                              &svc, &payload, &payload_len);
            if (rc == MESH_MUX_OK && payload && payload_len > 0) {
                // Dispatch based on service ID
                // For TOLLGATE: route to tollgate_balloon handler
                if (svc == MESH_SVC_TOLLGATE) {
                    tollgate_balloon_on_mesh_frame("unknown", payload, payload_len);
                }
                // NOSTR and BLOSSOM services would be handled by their respective components
            }
        }

        // Clear IRQ + re-arm RX
        s_radio.clear_irq();
        s_radio.start_rx();
    } else {
        // Other IRQ source — clear it
        s_radio.clear_irq();
    }
}

int8_t radio_adapter_last_rssi(void) {
    return s_last_rssi;
}

#else  // !ESP_PLATFORM — host stub for unit tests

// ── Host build: stubs (no hardware) ─────────────────────────────────

int radio_adapter_init(float freq_mhz, uint8_t payload_len) {
    (void)freq_mhz; (void)payload_len;
    return 0;
}

void radio_adapter_send(const uint8_t *data, uint16_t len) {
    (void)data; (void)len;
}

void radio_adapter_poll(void) {}

int8_t radio_adapter_last_rssi(void) { return 0; }

#endif // ESP_PLATFORM
