/**
 * @file    uart_telemetry_rp2040.cpp
 * @brief   RP2040 radio side of the UART telemetry link (reference driver).
 *
 * Consumer role: decodes TELEMETRY frames from the ESP32-C3 and returns
 * MESH_STATUS frames carrying the radio/mesh state the C3 needs to decide
 * whether and how to transmit.
 *
 * Wiring (docs/uart-bridge-pin-verification.md):
 *   RP2040 GP12 (UART0 TX) -> ESP32-C3 GPIO3 (RX)
 *   RP2040 GP13 (UART0 RX) <- ESP32-C3 GPIO2 (TX)
 *
 * Written against the earlephilhower Arduino core, which is what the existing
 * firmware/rp2040/src/uart_echo.cpp uses.  The framing/validation logic is in
 * the portable core; this file is plumbing + the radio-state mapping.
 *
 * Build note: guarded by UART_TLM_RP2040_TARGET so the host suite never sees it.
 */

#ifdef UART_TLM_RP2040_TARGET

#include "uart_telemetry.h"

#include <Arduino.h>

#define TLM_RP_UART       Serial1
#define TLM_RP_PIN_TX     12
#define TLM_RP_PIN_RX     13
#define TLM_MESH_PERIOD_MS 1000u
#define TLM_HOST_STALE_MS  5000u

static uart_tlm_decoder_t    s_dec;
static uart_tlm_telemetry_t  s_last_tlm;
static bool                  s_have_tlm;
static uint32_t              s_last_tlm_ms;
static uint32_t              s_frame_seq;

/* Radio-side counters, kept by the radio driver. */
static uint16_t              s_pkt_rx;
static uint16_t              s_pkt_tx;
static uint16_t              s_crc_err;
static uint32_t              s_mesh_seq;   /* payload seq, monotonic */

/* Radio state machine code reported in MESH_STATUS.state. */
enum {
    RP_STATE_IDLE = 0,
    RP_STATE_RX   = 1,
    RP_STATE_TX   = 2,
    RP_STATE_FAULT = 3,
};

static uint8_t  s_radio_state = RP_STATE_IDLE;
static int16_t  s_rssi_half_dbm = UART_TLM_RSSI_NO_SIGNAL; /* -140.0 dBm, no packet yet */
static int8_t   s_snr_qdb;
static uint8_t  s_chan;
static bool     s_mesh_joined;
static bool     s_pa_enabled;

void uart_tlm_rp_init(void)
{
    TLM_RP_UART.setTX(TLM_RP_PIN_TX);
    TLM_RP_UART.setRX(TLM_RP_PIN_RX);
    TLM_RP_UART.begin(UART_TLM_BAUD);

    uart_tlm_decoder_init(&s_dec);
    s_have_tlm   = false;
    s_frame_seq  = 0;
    s_pkt_rx = s_pkt_tx = s_crc_err = 0;
}

/* ── Radio driver hooks ─────────────────────────────────────────────────── */

void uart_tlm_rp_set_radio_state(uint8_t state, bool joined)
{
    s_radio_state = state;
    s_mesh_joined = joined;
}

void uart_tlm_rp_set_pa(bool enabled)
{
    s_pa_enabled = enabled;
}

void uart_tlm_rp_on_rx_packet(int16_t rssi_half_dbm, int8_t snr_qdb)
{
    s_pkt_rx++;
    s_rssi_half_dbm = rssi_half_dbm;
    s_snr_qdb = snr_qdb;
}

void uart_tlm_rp_on_tx_packet(void)
{
    s_pkt_tx++;
}

void uart_tlm_rp_on_crc_error(void)
{
    s_crc_err++;
}

/* ── Inbound: decode TELEMETRY frames ───────────────────────────────────── */

/** Drain the UART.  @return valid TELEMETRY frames consumed. */
uint32_t uart_tlm_rp_poll(void)
{
    uint32_t got = 0;

    while (TLM_RP_UART.available()) {
        uint8_t type = 0, seq = 0, plen = 0, payload[UART_TLM_MAX_PAYLOAD];
        const uint32_t before = s_dec.frames_ok;
        uint8_t byte = (uint8_t)TLM_RP_UART.read();

        int rc = uart_tlm_decoder_feed(&s_dec, byte, &type, &seq, payload, &plen);
        if (rc != UART_TLM_OK || s_dec.frames_ok == before) {
            continue;
        }
        if (type == UART_TLM_TYPE_TELEMETRY && plen == UART_TLM_TELEMETRY_LEN) {
            uart_tlm_telemetry_t t;
            if (uart_tlm_bytes_to_telemetry(payload, &t) && uart_tlm_telemetry_valid(&t)) {
                s_last_tlm = t;
                s_have_tlm = true;
                s_last_tlm_ms = millis();
                got++;
            }
        }
    }
    return got;
}

bool uart_tlm_rp_has_telemetry(uint32_t max_age_ms)
{
    if (!s_have_tlm) {
        return false;
    }
    return (millis() - s_last_tlm_ms) <= max_age_ms;
}

const uart_tlm_telemetry_t *uart_tlm_rp_last_telemetry(void)
{
    return uart_tlm_rp_has_telemetry(TLM_HOST_STALE_MS) ? &s_last_tlm : NULL;
}

/* ── Outbound: MESH_STATUS back-channel ─────────────────────────────────── */

/**
 * Build and send one MESH_STATUS frame.
 *
 * The grant decision lives here: the radio tells the C3 to transmit only when
 * it is ready, joined to the mesh and not currently mid-TX.  Everything else
 * (idle / fault) is a refusal, and the C3 will park in TXMODE_IDLE.
 */
void uart_tlm_rp_send_mesh_status(void)
{
    uart_tlm_mesh_status_t m;
    uint8_t flags = 0;
    uint8_t frame[UART_TLM_MAX_FRAME];

    if (s_radio_state != RP_STATE_FAULT) {
        flags |= UART_TLM_M_RADIO_READY;
    }
    if (s_mesh_joined) {
        flags |= UART_TLM_M_MESH_JOINED;
    }
    if (s_radio_state == RP_STATE_IDLE && s_mesh_joined) {
        flags |= UART_TLM_M_TX_GRANTED;
    }
    if (s_pa_enabled) {
        flags |= UART_TLM_M_PA_ENABLED;
    }
    if (s_dec.have > 0u) {
        /* A frame was mid-flight when we last looked -> the C3 is overrunning us. */
        flags |= UART_TLM_M_RX_OVERRUN;
    }

    /* Monotonic frame counter, not a clock — see the C3 driver for why a
     * seconds counter is wrong here (it collides above 1 Hz). */
    m.seq           = s_mesh_seq++;
    m.uptime_ms     = millis();
    m.rssi_half_dbm = s_rssi_half_dbm;
    m.snr_qdb       = s_snr_qdb;
    m.flags         = flags;
    m.pkt_rx        = s_pkt_rx;
    m.pkt_tx        = s_pkt_tx;
    m.crc_err       = s_crc_err;
    m.state         = s_radio_state;
    m.chan          = s_chan;

    int n = uart_tlm_encode_mesh_status(frame, sizeof frame, s_frame_seq++, &m);
    if (n > 0) {
        TLM_RP_UART.write(frame, (size_t)n);
    }
}

/* ── Reference 1 Hz loop body ───────────────────────────────────────────── */

void uart_tlm_rp_task_step(void)
{
    static uint32_t last_mesh = 0;

    (void)uart_tlm_rp_poll();

    if (millis() - last_mesh >= TLM_MESH_PERIOD_MS) {
        last_mesh = millis();
        uart_tlm_rp_send_mesh_status();
    }
}

#endif /* UART_TLM_RP2040_TARGET */
