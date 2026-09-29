/**
 * @file    uart_telemetry_c3.cpp
 * @brief   ESP32-C3 tracker side of the UART telemetry link (reference driver).
 *
 * Producer role: emits TELEMETRY frames to the RP2040 at 1 Hz and consumes the
 * MESH_STATUS back-channel.  The framing/validation logic lives entirely in the
 * portable core (uart_telemetry.c); this file is only the ESP-IDF plumbing.
 *
 * Verified wiring (docs/uart-bridge-pin-verification.md — bidirectional CONFIRMED):
 *   ESP32-C3 GPIO3 (UART1 RX) <- RP2040 GP12 (UART0 TX)
 *   ESP32-C3 GPIO2 (UART1 TX) -> RP2040 GP13 (UART0 RX)
 *   GND shared
 *
 * Build note: this translation unit needs the ESP-IDF UART driver.  It is
 * guarded by UART_TLM_C3_TARGET so the host test build never sees it; the
 * portable core is what the host suite exercises.
 */

#ifdef UART_TLM_C3_TARGET

#include "uart_telemetry.h"

#include "driver/uart.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"

/* Real sensor components from this repository. */
#include "gps.h"          /* components/gps/gps.h */
#include "bmp280.h"       /* components/bmp280/bmp280.h */
#include "power_manager.h"/* components/power_manager/power_manager.h */

#include <string.h>

static const char *TAG = "UART_TLM";

#define TLM_UART_PORT       UART_NUM_1
#define TLM_PIN_RX          GPIO_NUM_3
#define TLM_PIN_TX          GPIO_NUM_2
#define TLM_RX_BUF          512
#define TLM_MESH_STALE_MS   5000u

static uart_tlm_decoder_t     s_dec;
static uint8_t                s_frame_seq;
static uart_tlm_mesh_status_t s_mesh;
static bool                   s_mesh_fresh;
static uint32_t               s_last_mesh_ms;

/* Cached sensor state, refreshed once per second by uart_tlm_c3_sample(). */
static gps_data_t      s_gps;
static uint16_t        s_battery_mv;
static uint16_t        s_solar_mv;
static int16_t         s_temp_cdeg;
static uint16_t        s_pressure_hpa10;

static inline uint32_t now_ms(void)
{
    return (uint32_t)(esp_timer_get_time() / 1000);
}

esp_err_t uart_tlm_c3_init(void)
{
    const uart_config_t cfg = {
        .baud_rate  = UART_TLM_BAUD,
        .data_bits  = UART_DATA_8_BITS,
        .parity     = UART_PARITY_DISABLE,
        .stop_bits  = UART_STOP_BITS_1,
        .flow_ctrl  = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };

    esp_err_t err = uart_driver_install(TLM_UART_PORT, TLM_RX_BUF, 0, 0, NULL, 0);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "uart_driver_install: %s", esp_err_to_name(err));
        return err;
    }
    if ((err = uart_param_config(TLM_UART_PORT, &cfg)) != ESP_OK) {
        ESP_LOGE(TAG, "uart_param_config: %s", esp_err_to_name(err));
        return err;
    }
    if ((err = uart_set_pin(TLM_UART_PORT, TLM_PIN_TX, TLM_PIN_RX,
                            UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE)) != ESP_OK) {
        ESP_LOGE(TAG, "uart_set_pin: %s", esp_err_to_name(err));
        return err;
    }
    uart_tlm_decoder_init(&s_dec);
    s_frame_seq  = 0;
    s_mesh_fresh = false;
    memset(&s_gps, 0, sizeof s_gps);
    return ESP_OK;
}

/* ── Sensor sampling (once per second) ─────────────────────────────────── */

/**
 * Refresh the cached sensor readings.  Uses the repository's existing
 * components; a missing/failed read leaves the previous cached value in place
 * and clears the corresponding flag rather than reporting a fake zero.
 */
void uart_tlm_c3_sample(bmp280_t *baro, uint8_t *flags_io)
{
    gps_data_t g;
    if (gps_read(&g)) {
        s_gps = g;
        if (g.fix) {
            *flags_io |= UART_TLM_F_GPS_VALID;
        }
    }

    if (baro != NULL) {
        float temperature = 0.0f, pressure = 0.0f, altitude = 0.0f;
        if (bmp280_read(baro, &temperature, &pressure, &altitude) == ESP_OK) {
            s_temp_cdeg      = (int16_t)(temperature * 100.0f);
            s_pressure_hpa10 = (uint16_t)(pressure * 10.0f);
        }
    }

    s_battery_mv = power_manager_read_supercap_mv();
    s_solar_mv   = 0;   /* solar rail is not instrumented on the current board */
}

/* ── Outbound ───────────────────────────────────────────────────────────── */

esp_err_t uart_tlm_c3_send_telemetry(const uart_tlm_telemetry_t *t)
{
    uint8_t frame[UART_TLM_MAX_FRAME];
    if (t == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    int n = uart_tlm_encode_telemetry(frame, sizeof frame, s_frame_seq, t);
    if (n <= 0) {
        ESP_LOGW(TAG, "encode refused (%d)", n);
        return ESP_ERR_INVALID_ARG;
    }
    s_frame_seq++;

    int written = uart_write_bytes(TLM_UART_PORT, frame, (size_t)n);
    if (written != n) {
        ESP_LOGW(TAG, "short write: %d of %d", written, n);
        return ESP_FAIL;
    }
    return ESP_OK;
}

/* Build the outgoing struct from the cached sensor state. */
void uart_tlm_c3_build(uart_tlm_telemetry_t *t, uint8_t flags)
{
    if (t == NULL) {
        return;
    }
    memset(t, 0, sizeof(*t));
    t->seq            = now_ms() / 1000u;   /* 1 Hz frame rate */
    t->uptime_ms      = now_ms();
    t->lat_deg1e7     = s_gps.latitude;
    t->lon_deg1e7     = s_gps.longitude;
    t->alt_mm         = (int32_t)s_gps.altitude_m * 1000;
    t->battery_mv     = s_battery_mv;
    t->solar_mv       = s_solar_mv;
    t->temp_cdeg      = s_temp_cdeg;
    t->pressure_hpa10 = s_pressure_hpa10;
    t->sats           = s_gps.sats;
    t->hdop_x10       = (uint8_t)(s_gps.hdop * 10.0f);
    t->flags          = flags;
    t->tx_mode        = uart_tlm_c3_tx_granted() ? UART_TLM_TXMODE_FLRC
                                                 : UART_TLM_TXMODE_IDLE;
}

/* ── Inbound ────────────────────────────────────────────────────────────── */

/** Drain the UART.  @return valid MESH_STATUS frames consumed. */
uint32_t uart_tlm_c3_poll(void)
{
    uint8_t buf[128];
    uint32_t got = 0;

    for (;;) {
        int r = uart_read_bytes(TLM_UART_PORT, buf, sizeof buf, 0);
        if (r <= 0) {
            break;
        }
        for (int i = 0; i < r; i++) {
            uint8_t type = 0, seq = 0, plen = 0, payload[UART_TLM_MAX_PAYLOAD];
            const uint32_t before = s_dec.frames_ok;

            int rc = uart_tlm_decoder_feed(&s_dec, buf[i], &type, &seq, payload, &plen);
            if (rc != UART_TLM_OK || s_dec.frames_ok == before) {
                continue;
            }
            if (type == UART_TLM_TYPE_MESH_STATUS && plen == UART_TLM_MESH_STATUS_LEN) {
                uart_tlm_mesh_status_t m;
                if (uart_tlm_bytes_to_mesh_status(payload, &m) &&
                    uart_tlm_mesh_status_valid(&m)) {
                    s_mesh = m;
                    s_mesh_fresh = true;
                    s_last_mesh_ms = now_ms();
                    got++;
                }
            }
        }
    }
    if (s_mesh_fresh && (now_ms() - s_last_mesh_ms) > TLM_MESH_STALE_MS) {
        s_mesh_fresh = false;
    }
    return got;
}

bool uart_tlm_c3_mesh_joined(void)
{
    return s_mesh_fresh && ((s_mesh.flags & UART_TLM_M_MESH_JOINED) != 0u);
}

bool uart_tlm_c3_tx_granted(void)
{
    if (!s_mesh_fresh) {
        return false;
    }
    return (s_mesh.flags & (UART_TLM_M_RADIO_READY | UART_TLM_M_TX_GRANTED)) ==
           (UART_TLM_M_RADIO_READY | UART_TLM_M_TX_GRANTED);
}

const uart_tlm_mesh_status_t *uart_tlm_c3_last_mesh(void)
{
    return s_mesh_fresh ? &s_mesh : NULL;
}

/* ── Reference 1 Hz task body ───────────────────────────────────────────── */

void uart_tlm_c3_task_step(bmp280_t *baro)
{
    uint8_t flags = 0;
    uart_tlm_telemetry_t t;

    uart_tlm_c3_sample(baro, &flags);
    if (uart_tlm_c3_mesh_joined()) {
        flags |= UART_TLM_F_MESH_JOINED;
    }
    uart_tlm_c3_build(&t, flags);

    if (!uart_tlm_telemetry_valid(&t)) {
        ESP_LOGW(TAG, "telemetry failed the sanity check (flags=%02X)", flags);
    }
    (void)uart_tlm_c3_send_telemetry(&t);
    (void)uart_tlm_c3_poll();
}

#endif /* UART_TLM_C3_TARGET */
