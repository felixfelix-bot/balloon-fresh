/**
 * @file    uart_telemetry.c
 * @brief   Portable implementation of the ESP32-C3 <-> RP2040 UART telemetry
 *          protocol.  See uart_telemetry.h and docs/uart-telemetry-protocol.md.
 *
 * No target headers: this file is compiled by the ESP-IDF build, the Pico-SDK
 * build and the host unit tests (tests/test_uart_telemetry.c) unchanged.
 */

#include "uart_telemetry.h"

#include <string.h>

/* ── CRC-16/CCITT-FALSE ──────────────────────────────────────────────────── */

uint16_t uart_tlm_crc16(const uint8_t *data, uint32_t len)
{
    uint16_t crc = 0xFFFFu;
    if (data == NULL) {
        return crc;
    }
    for (uint32_t i = 0; i < len; i++) {
        crc ^= (uint16_t)((uint16_t)data[i] << 8);
        for (uint8_t bit = 0; bit < 8; bit++) {
            if (crc & 0x8000u) {
                crc = (uint16_t)((crc << 1) ^ 0x1021u);
            } else {
                crc = (uint16_t)(crc << 1);
            }
        }
    }
    return crc;
}

/* ── Byte helpers (little-endian, alignment-safe) ────────────────────────── */

static void put_u16(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t)(v & 0xFFu);
    p[1] = (uint8_t)((v >> 8) & 0xFFu);
}

static uint16_t get_u16(const uint8_t *p)
{
    return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

static void put_u32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)(v & 0xFFu);
    p[1] = (uint8_t)((v >> 8) & 0xFFu);
    p[2] = (uint8_t)((v >> 16) & 0xFFu);
    p[3] = (uint8_t)((v >> 24) & 0xFFu);
}

static uint32_t get_u32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

/* ── Payload lengths ─────────────────────────────────────────────────────── */

uint8_t uart_tlm_payload_len(uint8_t type)
{
    switch (type) {
        case UART_TLM_TYPE_TELEMETRY:   return UART_TLM_TELEMETRY_LEN;
        case UART_TLM_TYPE_MESH_STATUS: return UART_TLM_MESH_STATUS_LEN;
        default:                        return 0u;
    }
}

/* ── Payload serialisation ───────────────────────────────────────────────── */

void uart_tlm_telemetry_to_bytes(const uart_tlm_telemetry_t *t,
                                 uint8_t payload[UART_TLM_TELEMETRY_LEN])
{
    if (t == NULL || payload == NULL) {
        return;
    }
    put_u32(&payload[0],  t->seq);
    put_u32(&payload[4],  t->uptime_ms);
    put_u32(&payload[8],  (uint32_t)t->lat_deg1e7);
    put_u32(&payload[12], (uint32_t)t->lon_deg1e7);
    put_u32(&payload[16], (uint32_t)t->alt_mm);
    put_u16(&payload[20], t->battery_mv);
    put_u16(&payload[22], t->solar_mv);
    put_u16(&payload[24], (uint16_t)t->temp_cdeg);
    put_u16(&payload[26], t->pressure_hpa10);
    payload[28] = t->sats;
    payload[29] = t->hdop_x10;
    payload[30] = t->flags;
    payload[31] = t->tx_mode;
}

bool uart_tlm_bytes_to_telemetry(const uint8_t payload[UART_TLM_TELEMETRY_LEN],
                                 uart_tlm_telemetry_t *t)
{
    if (payload == NULL || t == NULL) {
        return false;
    }
    t->seq            = get_u32(&payload[0]);
    t->uptime_ms      = get_u32(&payload[4]);
    t->lat_deg1e7     = (int32_t)get_u32(&payload[8]);
    t->lon_deg1e7     = (int32_t)get_u32(&payload[12]);
    t->alt_mm         = (int32_t)get_u32(&payload[16]);
    t->battery_mv     = get_u16(&payload[20]);
    t->solar_mv       = get_u16(&payload[22]);
    t->temp_cdeg      = (int16_t)get_u16(&payload[24]);
    t->pressure_hpa10 = get_u16(&payload[26]);
    t->sats           = payload[28];
    t->hdop_x10       = payload[29];
    t->flags          = payload[30];
    t->tx_mode        = payload[31];
    return true;
}

void uart_tlm_mesh_status_to_bytes(const uart_tlm_mesh_status_t *m,
                                   uint8_t payload[UART_TLM_MESH_STATUS_LEN])
{
    if (m == NULL || payload == NULL) {
        return;
    }
    put_u32(&payload[0],  m->seq);
    put_u32(&payload[4],  m->uptime_ms);
    put_u16(&payload[8],  (uint16_t)m->rssi_half_dbm);
    payload[10] = (uint8_t)m->snr_qdb;
    payload[11] = m->flags;
    put_u16(&payload[12], m->pkt_rx);
    put_u16(&payload[14], m->pkt_tx);
    put_u16(&payload[16], m->crc_err);
    payload[18] = m->state;
    payload[19] = m->chan;
}

bool uart_tlm_bytes_to_mesh_status(const uint8_t payload[UART_TLM_MESH_STATUS_LEN],
                                   uart_tlm_mesh_status_t *m)
{
    if (payload == NULL || m == NULL) {
        return false;
    }
    m->seq          = get_u32(&payload[0]);
    m->uptime_ms    = get_u32(&payload[4]);
    m->rssi_half_dbm = (int16_t)get_u16(&payload[8]);
    m->snr_qdb      = (int8_t)payload[10];
    m->flags        = payload[11];
    m->pkt_rx       = get_u16(&payload[12]);
    m->pkt_tx       = get_u16(&payload[14]);
    m->crc_err      = get_u16(&payload[16]);
    m->state        = payload[18];
    m->chan         = payload[19];
    return true;
}

/* ── Validation ──────────────────────────────────────────────────────────── */

bool uart_tlm_telemetry_valid(const uart_tlm_telemetry_t *t)
{
    if (t == NULL) {
        return false;
    }
    /* Latitude/longitude are only meaningful when the fix flag is set; when it
     * is, they must be inside the physical range.  A 0/0 position is the
     * "no fix" sentinel and is rejected explicitly rather than trusted. */
    if (t->flags & UART_TLM_F_GPS_VALID) {
        if (t->lat_deg1e7 < -900000000 || t->lat_deg1e7 > 900000000) {
            return false;
        }
        if (t->lon_deg1e7 < -1800000000 || t->lon_deg1e7 > 1800000000) {
            return false;
        }
        if (t->lat_deg1e7 == 0 && t->lon_deg1e7 == 0) {
            return false;
        }
    }
    if (t->tx_mode > UART_TLM_TXMODE_IDLE) {
        return false;
    }
    /* Altitude: -500 m .. 50 km covers every balloon flight regime. */
    if (t->alt_mm < -500000 || t->alt_mm > 50000000) {
        return false;
    }
    return true;
}

bool uart_tlm_mesh_status_valid(const uart_tlm_mesh_status_t *m)
{
    if (m == NULL) {
        return false;
    }
    /* rssi_half_dbm is dBm*2 in an int16; a real radio never reports outside
     * -140..0 dBm.  Anything else is a decode/endianness bug. */
    if (m->rssi_half_dbm < -280 || m->rssi_half_dbm > 0) {
        return false;
    }
    /* snr_qdb is an int8 in 0.25 dB steps, so every bit pattern is a value in
     * -32.0..31.75 dB — there is no out-of-range case to reject. */
    return true;
}

/* ── Encoding ────────────────────────────────────────────────────────────── */

int uart_tlm_encode(uint8_t *out, uint32_t out_size, uint8_t type, uint8_t seq,
                    const uint8_t *payload, uint8_t len)
{
    uint8_t want;

    if (out == NULL) {
        return UART_TLM_ERR_ARG;
    }
    want = uart_tlm_payload_len(type);
    if (want == 0u) {
        return UART_TLM_ERR_TYPE;
    }
    if (len != want) {
        return UART_TLM_ERR_PAYLOAD_SIZE;
    }
    if (payload == NULL) {
        return UART_TLM_ERR_ARG;
    }
    if (out_size < (uint32_t)(UART_TLM_HDR_SIZE + len + UART_TLM_CRC_SIZE)) {
        return UART_TLM_ERR_OVERFLOW;
    }

    out[0] = UART_TLM_SOF0;
    out[1] = UART_TLM_SOF1;
    out[2] = UART_TLM_VERSION;
    out[3] = type;
    out[4] = len;
    out[5] = seq;
    memcpy(&out[UART_TLM_HDR_SIZE], payload, len);

    /* CRC covers VER..payload — SOF is excluded so the pattern can never
     * appear inside the covered bytes. */
    uint16_t crc = uart_tlm_crc16(&out[2], (uint32_t)(len + 4u));
    out[UART_TLM_HDR_SIZE + len]     = (uint8_t)(crc & 0xFFu);
    out[UART_TLM_HDR_SIZE + len + 1] = (uint8_t)((crc >> 8) & 0xFFu);

    return (int)(UART_TLM_HDR_SIZE + len + UART_TLM_CRC_SIZE);
}

int uart_tlm_encode_telemetry(uint8_t *out, uint32_t out_size, uint8_t seq,
                              const uart_tlm_telemetry_t *t)
{
    uint8_t payload[UART_TLM_TELEMETRY_LEN];
    if (t == NULL) {
        return UART_TLM_ERR_ARG;
    }
    uart_tlm_telemetry_to_bytes(t, payload);
    return uart_tlm_encode(out, out_size, UART_TLM_TYPE_TELEMETRY, seq,
                           payload, UART_TLM_TELEMETRY_LEN);
}

int uart_tlm_encode_mesh_status(uint8_t *out, uint32_t out_size, uint8_t seq,
                                const uart_tlm_mesh_status_t *m)
{
    uint8_t payload[UART_TLM_MESH_STATUS_LEN];
    if (m == NULL) {
        return UART_TLM_ERR_ARG;
    }
    uart_tlm_mesh_status_to_bytes(m, payload);
    return uart_tlm_encode(out, out_size, UART_TLM_TYPE_MESH_STATUS, seq,
                           payload, UART_TLM_MESH_STATUS_LEN);
}

/* ── Decoding ────────────────────────────────────────────────────────────── */

void uart_tlm_decoder_init(uart_tlm_decoder_t *d)
{
    if (d == NULL) {
        return;
    }
    memset(d, 0, sizeof(*d));
}

/* Push a byte into the frame buffer, preserving the tail so a SOF that already
 * arrived cannot be lost when we resynchronise. */
static void resync(uart_tlm_decoder_t *d)
{
    /* Look for a SOF pair in the bytes we have; keep the trailing byte if it is
     * a possible SOF0, drop everything else. */
    uint16_t keep = 0;
    if (d->have >= 1u && d->buf[d->have - 1u] == UART_TLM_SOF0) {
        d->buf[0] = UART_TLM_SOF0;
        keep = 1u;
    }
    d->have = keep;
    d->expect = 0u;
    d->resyncs++;
}

static int finish_frame(uart_tlm_decoder_t *d, uint8_t *type_out, uint8_t *seq_out,
                        uint8_t *payload_out, uint8_t *payload_len_out)
{
    const uint8_t len = d->buf[4];
    const uint16_t crc_rx = get_u16(&d->buf[UART_TLM_HDR_SIZE + len]);
    const uint16_t crc_calc = uart_tlm_crc16(&d->buf[2], (uint32_t)len + 4u);

    if (crc_rx != crc_calc) {
        d->crc_errors++;
        resync(d);
        return UART_TLM_ERR_CRC;
    }

    if (type_out)        { *type_out = d->buf[3]; }
    if (seq_out)         { *seq_out = d->buf[5]; }
    if (payload_len_out) { *payload_len_out = len; }
    if (payload_out)     { memcpy(payload_out, &d->buf[UART_TLM_HDR_SIZE], len); }

    /* Frame-level sequence gap accounting (mod-256 link counter). */
    if (d->seq_valid) {
        uint8_t expected = (uint8_t)(d->last_seq + 1u);
        if (d->buf[5] != expected) {
            d->seq_drops++;
        }
    }
    d->last_seq = d->buf[5];
    d->seq_valid = true;
    d->frames_ok++;

    d->have = 0u;
    d->expect = 0u;
    return UART_TLM_OK;
}

int uart_tlm_decoder_feed(uart_tlm_decoder_t *d, uint8_t byte,
                          uint8_t *type_out, uint8_t *seq_out,
                          uint8_t *payload_out, uint8_t *payload_len_out)
{
    if (d == NULL) {
        return UART_TLM_ERR_ARG;
    }

    if (d->have == 0u) {
        /* Hunting for SOF0 */
        if (byte != UART_TLM_SOF0) {
            return UART_TLM_OK;
        }
        d->buf[0] = byte;
        d->have = 1u;
        return UART_TLM_OK;
    }

    if (d->have == 1u) {
        if (byte != UART_TLM_SOF1) {
            /* Not a header after all.  A 0xAA that is really the start of a
             * genuine frame would be followed by 0x55, so drop and re-hunt;
             * but if this byte is itself 0xAA keep it as the new SOF0. */
            if (byte == UART_TLM_SOF0) {
                d->buf[0] = byte;
                d->have = 1u;
            } else {
                d->have = 0u;
            }
            return UART_TLM_OK;
        }
        d->buf[1] = byte;
        d->have = 2u;
        return UART_TLM_OK;
    }

    /* Inside a frame: accumulate. */
    if (d->have >= (uint16_t)UART_TLM_MAX_FRAME) {
        d->len_errors++;
        resync(d);
        return UART_TLM_ERR_LEN;
    }
    d->buf[d->have++] = byte;

    /* Once the length byte has arrived the total frame size is known. */
    if (d->have == 5u) {
        const uint8_t len = d->buf[4];
        if (len == 0u || len > UART_TLM_MAX_PAYLOAD) {
            d->len_errors++;
            resync(d);
            return UART_TLM_ERR_LEN;
        }
        d->expect = (uint16_t)(UART_TLM_HDR_SIZE + len + UART_TLM_CRC_SIZE);
    }

    if (d->have >= 6u && d->buf[2] != UART_TLM_VERSION) {
        /* Unknown version: cannot trust the framing, drop and re-hunt. */
        resync(d);
        return UART_TLM_ERR_TYPE;
    }

    if (d->expect != 0u && d->have == d->expect) {
        return finish_frame(d, type_out, seq_out, payload_out, payload_len_out);
    }

    return UART_TLM_OK;
}

uint32_t uart_tlm_decoder_feed_block(uart_tlm_decoder_t *d,
                                     const uint8_t *data, uint32_t len,
                                     uint8_t *type_out, uint8_t *seq_out,
                                     uint8_t *payload_out, uint8_t *payload_len_out)
{
    uint32_t frames = 0;
    if (d == NULL || data == NULL) {
        return 0u;
    }
    for (uint32_t i = 0; i < len; i++) {
        const uint32_t before = d->frames_ok;
        (void)uart_tlm_decoder_feed(d, data[i], type_out, seq_out,
                                    payload_out, payload_len_out);
        if (d->frames_ok != before) {
            frames++;
        }
    }
    return frames;
}

int uart_tlm_decode_frame(const uint8_t *data, uint32_t len,
                          uint8_t *type_out, uint8_t *seq_out,
                          uint8_t *payload_out, uint8_t *payload_len_out)
{
    if (data == NULL) {
        return UART_TLM_ERR_ARG;
    }
    if (len < UART_TLM_HDR_SIZE + UART_TLM_CRC_SIZE) {
        return UART_TLM_ERR_LEN;
    }
    if (data[0] != UART_TLM_SOF0 || data[1] != UART_TLM_SOF1) {
        return UART_TLM_ERR_TYPE;
    }
    if (data[2] != UART_TLM_VERSION) {
        return UART_TLM_ERR_TYPE;
    }
    const uint8_t plen = data[4];
    if (plen == 0u || plen > UART_TLM_MAX_PAYLOAD) {
        return UART_TLM_ERR_LEN;
    }
    const uint32_t total = (uint32_t)UART_TLM_HDR_SIZE + plen + UART_TLM_CRC_SIZE;
    if (len < total) {
        return UART_TLM_ERR_LEN;
    }
    const uint16_t crc_rx = get_u16(&data[UART_TLM_HDR_SIZE + plen]);
    const uint16_t crc_calc = uart_tlm_crc16(&data[2], (uint32_t)plen + 4u);
    if (crc_rx != crc_calc) {
        return UART_TLM_ERR_CRC;
    }
    if (type_out)        { *type_out = data[3]; }
    if (seq_out)         { *seq_out = data[5]; }
    if (payload_len_out) { *payload_len_out = plen; }
    if (payload_out)     { memcpy(payload_out, &data[UART_TLM_HDR_SIZE], plen); }
    return (int)total;
}
