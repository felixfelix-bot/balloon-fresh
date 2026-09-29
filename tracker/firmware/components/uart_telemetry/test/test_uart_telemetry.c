/**
 * @file    test_uart_telemetry.c
 * @brief   Host unit tests for the ESP32-C3 <-> RP2040 UART telemetry protocol.
 *
 * Compiles with plain C11 (see Makefile).  Covers CRC golden vectors, payload
 * round-trips, frame size invariants, endianness on the wire, decoder
 * resynchronisation, corruption/truncation handling, sequence-gap accounting
 * and the sanity validators.
 */

#include "uart_telemetry.h"

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static int g_fail = 0;
static int g_pass = 0;

#define CHECK(cond, ...)                                                   \
    do {                                                                   \
        if (cond) {                                                        \
            g_pass++;                                                      \
        } else {                                                           \
            g_fail++;                                                      \
            printf("FAIL %s:%d: ", __FILE__, __LINE__);                    \
            printf(__VA_ARGS__);                                           \
            printf("\n");                                                  \
        }                                                                  \
    } while (0)

/* ── Golden CRC vectors (CCITT-FALSE: poly 0x1021, init 0xFFFF) ─────────── */

static void test_crc_golden(void)
{
    CHECK(uart_tlm_crc16((const uint8_t *)"123456789", 9) == 0x29B1,
          "\"123456789\" -> 0x29B1, got 0x%04X",
          uart_tlm_crc16((const uint8_t *)"123456789", 9));

    uint8_t z[64];
    memset(z, 0, sizeof z);
    CHECK(uart_tlm_crc16(z, 64) == 0xD6DA, "64 x 0x00 -> 0xD6DA, got 0x%04X",
          uart_tlm_crc16(z, 64));

    static uint8_t big[4096];
    for (uint32_t i = 0; i < 4096; i++) big[i] = (uint8_t)(i % 256);
    CHECK(uart_tlm_crc16(big, 4096) == 0x0F69, "4096 x (i%%256) -> 0x0F69, got 0x%04X",
          uart_tlm_crc16(big, 4096));

    /* Empty input must be the init value, not a shifted garbage value. */
    CHECK(uart_tlm_crc16(z, 0) == 0xFFFF, "empty -> 0xFFFF");

    /* NULL must not crash and must be treated as empty. */
    CHECK(uart_tlm_crc16(NULL, 10) == 0xFFFF, "NULL data -> 0xFFFF");
}

/* ── Frame invariants ───────────────────────────────────────────────────── */

static void test_frame_size_and_sof(void)
{
    uart_tlm_telemetry_t t;
    memset(&t, 0, sizeof t);
    t.flags = UART_TLM_F_GPS_VALID;
    t.lat_deg1e7 = 480000000;   /* 48.0 N */
    t.lon_deg1e7 = 110000000;   /* 11.0 E */
    t.alt_mm = 1234000;
    t.battery_mv = 3900;
    t.solar_mv = 5100;
    t.temp_cdeg = 2150;
    t.pressure_hpa10 = 10132;
    t.sats = 9;
    t.hdop_x10 = 8;
    t.tx_mode = UART_TLM_TXMODE_FLRC;

    uint8_t frame[UART_TLM_MAX_FRAME];
    int n = uart_tlm_encode_telemetry(frame, sizeof frame, 42, &t);
    CHECK(n == (int)(UART_TLM_HDR_SIZE + UART_TLM_TELEMETRY_LEN + UART_TLM_CRC_SIZE),
          "TELEMETRY frame is %u bytes, got %d", UART_TLM_HDR_SIZE + UART_TLM_TELEMETRY_LEN + UART_TLM_CRC_SIZE, n);
    CHECK(frame[0] == 0xAA && frame[1] == 0x55, "SOF is 0xAA 0x55, got %02X %02X", frame[0], frame[1]);
    CHECK(frame[2] == UART_TLM_VERSION, "version byte");
    CHECK(frame[3] == UART_TLM_TYPE_TELEMETRY, "type byte");
    CHECK(frame[4] == UART_TLM_TELEMETRY_LEN, "payload length byte");
    CHECK(frame[5] == 42, "seq byte");

    /* CRC must be little-endian on the wire and cover VER..payload. */
    uint16_t crc = uart_tlm_crc16(&frame[2], UART_TLM_TELEMETRY_LEN + 4u);
    CHECK(frame[n - 2] == (uint8_t)(crc & 0xFF), "crc low byte LE");
    CHECK(frame[n - 1] == (uint8_t)(crc >> 8), "crc high byte LE");

    /* A 0xAA/0x55 pair inside the payload must not confuse a decoder: the CRC
     * excludes the SOF so the pattern cannot appear in the covered range. */
    CHECK(uart_tlm_crc16(&frame[0], (uint32_t)n) != crc,
          "CRC must not be taken over the SOF bytes");
}

static void test_wire_endianness(void)
{
    uart_tlm_telemetry_t t;
    memset(&t, 0, sizeof t);
    t.seq = 0x01020304u;
    t.uptime_ms = 0x11223344u;
    t.lat_deg1e7 = -480000000;   /* negative -> two's complement LE */
    t.lon_deg1e7 = 110000000;
    t.alt_mm = -50000;
    t.battery_mv = 0xBEEF;
    t.solar_mv = 0x1234;
    t.temp_cdeg = -2150;
    t.pressure_hpa10 = 0xABCD;

    uint8_t payload[UART_TLM_TELEMETRY_LEN];
    uart_tlm_telemetry_to_bytes(&t, payload);

    CHECK(payload[0] == 0x04 && payload[1] == 0x03 && payload[2] == 0x02 && payload[3] == 0x01,
          "seq is little-endian: %02X %02X %02X %02X", payload[0], payload[1], payload[2], payload[3]);
    CHECK(payload[4] == 0x44 && payload[5] == 0x33 && payload[6] == 0x22 && payload[7] == 0x11,
          "uptime_ms is little-endian");
    CHECK(payload[20] == 0xEF && payload[21] == 0xBE, "battery_mv is little-endian");
    CHECK(payload[24] == 0x9A && payload[25] == 0xF7, "temp_cdeg -2150 is 0xF79A LE (got %02X %02X)",
          payload[24], payload[25]);

    uart_tlm_telemetry_t back;
    memset(&back, 0, sizeof back);
    CHECK(uart_tlm_bytes_to_telemetry(payload, &back), "decode returns true");
    CHECK(back.seq == t.seq, "seq round-trips (%u)", back.seq);
    CHECK(back.uptime_ms == t.uptime_ms, "uptime_ms round-trips");
    CHECK(back.lat_deg1e7 == t.lat_deg1e7, "negative latitude round-trips (%d)", back.lat_deg1e7);
    CHECK(back.alt_mm == t.alt_mm, "negative altitude round-trips (%d)", back.alt_mm);
    CHECK(back.battery_mv == t.battery_mv, "battery_mv round-trips");
    CHECK(back.temp_cdeg == t.temp_cdeg, "negative temperature round-trips (%d)", back.temp_cdeg);
    CHECK(back.pressure_hpa10 == t.pressure_hpa10, "pressure round-trips");
}

static void test_mesh_status_roundtrip(void)
{
    uart_tlm_mesh_status_t m;
    memset(&m, 0, sizeof m);
    m.seq = 7;
    m.uptime_ms = 900000;
    m.rssi_half_dbm = -145;      /* -72.5 dBm */
    m.snr_qdb = -12;             /* -3.0 dB */
    m.flags = UART_TLM_M_RADIO_READY | UART_TLM_M_MESH_JOINED | UART_TLM_M_TX_GRANTED;
    m.pkt_rx = 1234;
    m.pkt_tx = 567;
    m.crc_err = 3;
    m.state = 2;
    m.chan = 5;

    uint8_t frame[UART_TLM_MAX_FRAME];
    int n = uart_tlm_encode_mesh_status(frame, sizeof frame, 9, &m);
    CHECK(n == (int)(UART_TLM_HDR_SIZE + UART_TLM_MESH_STATUS_LEN + UART_TLM_CRC_SIZE),
          "MESH_STATUS frame is %u bytes, got %d",
          UART_TLM_HDR_SIZE + UART_TLM_MESH_STATUS_LEN + UART_TLM_CRC_SIZE, n);

    uint8_t type = 0, seq = 0, plen = 0;
    uint8_t payload[UART_TLM_MAX_PAYLOAD];
    memset(payload, 0, sizeof payload);
    int used = uart_tlm_decode_frame(frame, (uint32_t)n, &type, &seq, payload, &plen);
    CHECK(used == n, "decode_frame consumes the whole frame (%d)", used);
    CHECK(type == UART_TLM_TYPE_MESH_STATUS, "decoded type");
    CHECK(seq == 9, "decoded seq");

    uart_tlm_mesh_status_t back;
    memset(&back, 0, sizeof back);
    CHECK(uart_tlm_bytes_to_mesh_status(payload, &back), "mesh payload decodes");
    CHECK(back.rssi_half_dbm == m.rssi_half_dbm, "negative RSSI round-trips (%d)", back.rssi_half_dbm);
    CHECK(back.snr_qdb == m.snr_qdb, "negative SNR round-trips (%d)", back.snr_qdb);
    CHECK(back.pkt_rx == m.pkt_rx && back.pkt_tx == m.pkt_tx, "counters round-trip");
    CHECK(back.crc_err == m.crc_err, "crc_err round-trips");
    CHECK(back.state == m.state && back.chan == m.chan, "state/chan round-trip");
    CHECK(back.flags == m.flags, "flags round-trip");
}

/* ── Encoder rejection paths ────────────────────────────────────────────── */

static void test_encoder_errors(void)
{
    uint8_t frame[UART_TLM_MAX_FRAME];
    uint8_t payload[UART_TLM_MAX_PAYLOAD];
    memset(payload, 0, sizeof payload);

    CHECK(uart_tlm_encode(frame, sizeof frame, 0x7F, 0, payload, 8) == UART_TLM_ERR_TYPE,
          "unknown type is rejected");
    CHECK(uart_tlm_encode(frame, sizeof frame, UART_TLM_TYPE_TELEMETRY, 0, payload, 8) == UART_TLM_ERR_PAYLOAD_SIZE,
          "wrong payload length is rejected");
    CHECK(uart_tlm_encode(frame, sizeof frame, UART_TLM_TYPE_TELEMETRY, 0, NULL, UART_TLM_TELEMETRY_LEN) == UART_TLM_ERR_ARG,
          "NULL payload is rejected");
    CHECK(uart_tlm_encode(frame, 8, UART_TLM_TYPE_TELEMETRY, 0, payload, UART_TLM_TELEMETRY_LEN) == UART_TLM_ERR_OVERFLOW,
          "too-small output buffer is rejected");
    CHECK(uart_tlm_encode(NULL, sizeof frame, UART_TLM_TYPE_TELEMETRY, 0, payload, UART_TLM_TELEMETRY_LEN) == UART_TLM_ERR_ARG,
          "NULL output is rejected");

    uart_tlm_telemetry_t t;
    memset(&t, 0, sizeof t);
    CHECK(uart_tlm_encode_telemetry(frame, sizeof frame, 0, NULL) == UART_TLM_ERR_ARG,
          "NULL telemetry struct is rejected");
}

/* ── Decoder: clean stream, block feed ──────────────────────────────────── */

static void test_decoder_stream(void)
{
    /* Build three telemetry frames back to back and feed them as one block. */
    uint8_t stream[3 * UART_TLM_MAX_FRAME];
    uint32_t total = 0;
    for (uint8_t i = 0; i < 3; i++) {
        uart_tlm_telemetry_t t;
        memset(&t, 0, sizeof t);
        t.seq = i;
        t.flags = UART_TLM_F_GPS_VALID;
        t.lat_deg1e7 = 480000000 + i;
        t.lon_deg1e7 = 110000000;
        t.sats = 5 + i;
        int n = uart_tlm_encode_telemetry(&stream[total], sizeof stream - total, i, &t);
        CHECK(n > 0, "encode frame %u", i);
        total += (uint32_t)n;
    }

    uart_tlm_decoder_t d;
    uart_tlm_decoder_init(&d);
    uint8_t type = 0, seq = 0, plen = 0;
    uint8_t payload[UART_TLM_MAX_PAYLOAD];
    memset(payload, 0, sizeof payload);
    uint32_t frames = uart_tlm_decoder_feed_block(&d, stream, total, &type, &seq, payload, &plen);
    CHECK(frames == 3, "3 frames decoded from a block, got %u", frames);
    CHECK(d.frames_ok == 3, "frames_ok == 3");
    CHECK(d.crc_errors == 0 && d.len_errors == 0, "no errors on a clean stream");
    CHECK(d.seq_valid && d.last_seq == 2, "last seq is 2 (got %u)", d.last_seq);

    /* Byte-at-a-time feed must agree. */
    uart_tlm_decoder_t d2;
    uart_tlm_decoder_init(&d2);
    uint32_t frames2 = 0;
    for (uint32_t i = 0; i < total; i++) {
        const uint32_t before = d2.frames_ok;
        (void)uart_tlm_decoder_feed(&d2, stream[i], &type, &seq, payload, &plen);
        if (d2.frames_ok != before) frames2++;
    }
    CHECK(frames2 == 3, "3 frames decoded byte-at-a-time, got %u", frames2);
    CHECK(d2.seq_drops == 0, "no sequence drops in a clean ordered stream");
}

/* ── Decoder: resynchronisation after leading noise ─────────────────────── */

static void test_decoder_resync_noise(void)
{
    uint8_t frame[UART_TLM_MAX_FRAME];
    uart_tlm_telemetry_t t;
    memset(&t, 0, sizeof t);
    t.flags = UART_TLM_F_GPS_VALID;
    t.lat_deg1e7 = 123456789;
    t.lon_deg1e7 = -987654321;
    t.sats = 11;
    int n = uart_tlm_encode_telemetry(frame, sizeof frame, 3, &t);
    CHECK(n > 0, "encode reference frame");

    /* Leading garbage, including a lone 0xAA and an 0xAA 0x54 near-miss. */
    const uint8_t noise[] = { 0x00, 0xFF, 0xAA, 0x54, 0x13, 0xAA, 0xAA };
    uint8_t stream[sizeof noise + UART_TLM_MAX_FRAME];
    memcpy(stream, noise, sizeof noise);
    memcpy(stream + sizeof noise, frame, (size_t)n);

    uart_tlm_decoder_t d;
    uart_tlm_decoder_init(&d);
    uint8_t type = 0, seq = 0, plen = 0;
    uint8_t payload[UART_TLM_MAX_PAYLOAD];
    memset(payload, 0, sizeof payload);
    uint32_t frames = uart_tlm_decoder_feed_block(&d, stream, (uint32_t)(sizeof noise + n),
                                                  &type, &seq, payload, &plen);
    CHECK(frames == 1, "exactly one frame survives leading noise, got %u", frames);
    CHECK(type == UART_TLM_TYPE_TELEMETRY, "decoded type after resync");

    uart_tlm_telemetry_t back;
    memset(&back, 0, sizeof back);
    uart_tlm_bytes_to_telemetry(payload, &back);
    CHECK(back.lat_deg1e7 == t.lat_deg1e7 && back.lon_deg1e7 == t.lon_deg1e7,
          "payload intact after resync (%d / %d)", back.lat_deg1e7, back.lon_deg1e7);
}

/* ── Decoder: corruption and truncation ─────────────────────────────────── */

static void test_decoder_corruption(void)
{
    uint8_t frame[UART_TLM_MAX_FRAME];
    uart_tlm_telemetry_t t;
    memset(&t, 0, sizeof t);
    t.flags = UART_TLM_F_GPS_VALID;
    t.lat_deg1e7 = 480000000;
    t.lon_deg1e7 = 110000000;
    int n = uart_tlm_encode_telemetry(frame, sizeof frame, 1, &t);
    CHECK(n > 0, "encode reference frame");

    /* Flip one payload bit -> CRC must reject. */
    uint8_t bad[UART_TLM_MAX_FRAME];
    memcpy(bad, frame, (size_t)n);
    bad[UART_TLM_HDR_SIZE + 4] ^= 0x01;

    uart_tlm_decoder_t d;
    uart_tlm_decoder_init(&d);
    uint8_t type = 0, seq = 0, plen = 0xFF;
    uint8_t payload[UART_TLM_MAX_PAYLOAD];
    memset(payload, 0xA5, sizeof payload);
    uint32_t frames = uart_tlm_decoder_feed_block(&d, bad, (uint32_t)n, &type, &seq, payload, &plen);
    CHECK(frames == 0, "corrupted frame yields no output");
    CHECK(d.crc_errors == 1, "corrupted frame counted as a CRC error (got %u)", d.crc_errors);
    CHECK(plen == 0xFF, "payload buffer untouched on a bad frame");

    /* A good frame after the bad one still decodes. */
    uart_tlm_decoder_t d2;
    uart_tlm_decoder_init(&d2);
    uint8_t both[2 * UART_TLM_MAX_FRAME];
    memcpy(both, bad, (size_t)n);
    memcpy(both + n, frame, (size_t)n);
    uint32_t f2 = uart_tlm_decoder_feed_block(&d2, both, (uint32_t)(2 * n), &type, &seq, payload, &plen);
    CHECK(f2 == 1, "good frame after a bad frame decodes (got %u)", f2);
    CHECK(d2.crc_errors == 1 && d2.frames_ok == 1, "error and success both counted");

    /* Truncated frame: decoder must not emit, and must not overrun. */
    uart_tlm_decoder_t d3;
    uart_tlm_decoder_init(&d3);
    uint32_t f3 = uart_tlm_decoder_feed_block(&d3, frame, (uint32_t)(n - 1), &type, &seq, payload, &plen);
    CHECK(f3 == 0, "truncated frame yields no output");
    CHECK(d3.crc_errors == 0 && d3.frames_ok == 0, "truncated frame is neither success nor CRC error");

    /* Declared length of 0 -> rejected, no overrun. */
    uart_tlm_decoder_t d4;
    uart_tlm_decoder_init(&d4);
    uint8_t zerolen[UART_TLM_HDR_SIZE + UART_TLM_CRC_SIZE];
    memcpy(zerolen, frame, UART_TLM_HDR_SIZE);
    zerolen[4] = 0;
    zerolen[6] = 0; zerolen[7] = 0;
    uint32_t f4 = uart_tlm_decoder_feed_block(&d4, zerolen, sizeof zerolen, &type, &seq, payload, &plen);
    CHECK(f4 == 0, "zero-length frame yields no output");
    CHECK(d4.len_errors == 1, "zero-length frame counted as a length error (got %u)", d4.len_errors);

    /* Declared length above the protocol maximum -> rejected. */
    uart_tlm_decoder_t d5;
    uart_tlm_decoder_init(&d5);
    uint8_t biglen[UART_TLM_HDR_SIZE + 8];
    memcpy(biglen, frame, UART_TLM_HDR_SIZE);
    biglen[4] = UART_TLM_MAX_PAYLOAD + 1;
    memset(biglen + UART_TLM_HDR_SIZE, 0, 8);
    (void)uart_tlm_decoder_feed_block(&d5, biglen, sizeof biglen, &type, &seq, payload, &plen);
    CHECK(d5.len_errors == 1, "oversized length counted as a length error (got %u)", d5.len_errors);
    CHECK(d5.frames_ok == 0, "oversized length produces no frame");

    /* Wrong version byte -> rejected without emitting. */
    uart_tlm_decoder_t d6;
    uart_tlm_decoder_init(&d6);
    uint8_t badver[UART_TLM_MAX_FRAME];
    memcpy(badver, frame, (size_t)n);
    badver[2] = 0x7E;
    (void)uart_tlm_decoder_feed_block(&d6, badver, (uint32_t)n, &type, &seq, payload, &plen);
    CHECK(d6.frames_ok == 0, "unknown version produces no frame");
}

/* ── Sequence gap accounting ────────────────────────────────────────────── */

static void test_sequence_gaps(void)
{
    uart_tlm_decoder_t d;
    uart_tlm_decoder_init(&d);
    uint8_t type = 0, seq = 0, plen = 0;
    uint8_t payload[UART_TLM_MAX_PAYLOAD];

    /* seq 1, 2, 4 -> exactly one gap. */
    const uint8_t seqs[] = { 1, 2, 4 };
    for (uint32_t i = 0; i < sizeof seqs; i++) {
        uint8_t frame[UART_TLM_MAX_FRAME];
        uart_tlm_telemetry_t t;
        memset(&t, 0, sizeof t);
        int n = uart_tlm_encode_telemetry(frame, sizeof frame, seqs[i], &t);
        CHECK(n > 0, "encode seq %u", seqs[i]);
        (void)uart_tlm_decoder_feed_block(&d, frame, (uint32_t)n, &type, &seq, payload, &plen);
    }
    CHECK(d.frames_ok == 3, "3 frames accepted (got %u)", d.frames_ok);
    CHECK(d.seq_drops == 1, "exactly one sequence gap detected (got %u)", d.seq_drops);

    /* The very first frame must not be counted as a drop. */
    uart_tlm_decoder_t d2;
    uart_tlm_decoder_init(&d2);
    uint8_t frame[UART_TLM_MAX_FRAME];
    uart_tlm_telemetry_t t;
    memset(&t, 0, sizeof t);
    int n = uart_tlm_encode_telemetry(frame, sizeof frame, 200, &t);
    (void)uart_tlm_decoder_feed_block(&d2, frame, (uint32_t)n, &type, &seq, payload, &plen);
    CHECK(d2.seq_drops == 0, "first frame never counts as a gap");
}

/* ── Validators ─────────────────────────────────────────────────────────── */

static void test_validators(void)
{
    uart_tlm_telemetry_t t;

    /* No fix, all zeroes -> the GPS fields are simply not checked. */
    memset(&t, 0, sizeof t);
    CHECK(uart_tlm_telemetry_valid(&t), "no-fix packet with zero GPS is acceptable");

    /* Claimed fix with 0/0 position -> rejected (the classic NaN island). */
    memset(&t, 0, sizeof t);
    t.flags = UART_TLM_F_GPS_VALID;
    CHECK(!uart_tlm_telemetry_valid(&t), "GPS_VALID with 0/0 position is rejected");

    /* Claimed fix with an out-of-range latitude -> rejected. */
    memset(&t, 0, sizeof t);
    t.flags = UART_TLM_F_GPS_VALID;
    t.lat_deg1e7 = 910000000;
    t.lon_deg1e7 = 110000000;
    CHECK(!uart_tlm_telemetry_valid(&t), "latitude beyond 90 deg is rejected");

    memset(&t, 0, sizeof t);
    t.flags = UART_TLM_F_GPS_VALID;
    t.lat_deg1e7 = 480000000;
    t.lon_deg1e7 = 1800000001;
    CHECK(!uart_tlm_telemetry_valid(&t), "longitude beyond 180 deg is rejected");

    /* Boundary values are accepted. */
    memset(&t, 0, sizeof t);
    t.flags = UART_TLM_F_GPS_VALID;
    t.lat_deg1e7 = -900000000;
    t.lon_deg1e7 = -1800000000;
    CHECK(uart_tlm_telemetry_valid(&t), "exact boundary lat/lon is accepted");

    /* Bad tx_mode -> rejected. */
    memset(&t, 0, sizeof t);
    t.tx_mode = 99;
    CHECK(!uart_tlm_telemetry_valid(&t), "unknown tx_mode is rejected");

    /* Absurd altitude -> rejected. */
    memset(&t, 0, sizeof t);
    t.alt_mm = 60000000;
    CHECK(!uart_tlm_telemetry_valid(&t), "altitude above 50 km is rejected");
    memset(&t, 0, sizeof t);
    t.alt_mm = -600000;
    CHECK(!uart_tlm_telemetry_valid(&t), "altitude below -500 m is rejected");

    /* NULL is not valid. */
    CHECK(!uart_tlm_telemetry_valid(NULL), "NULL telemetry is not valid");

    /* Mesh status: plausible RSSI accepted, impossible RSSI rejected. */
    uart_tlm_mesh_status_t m;
    memset(&m, 0, sizeof m);
    m.rssi_half_dbm = -140;
    CHECK(uart_tlm_mesh_status_valid(&m), "-70.0 dBm is acceptable");
    memset(&m, 0, sizeof m);
    m.rssi_half_dbm = -400;
    CHECK(!uart_tlm_mesh_status_valid(&m), "impossible RSSI is rejected");
    CHECK(!uart_tlm_mesh_status_valid(NULL), "NULL mesh status is not valid");
}

/* ── Whole-buffer decode: truncation and tolerance to trailing bytes ────── */

static void test_decode_frame_buffer(void)
{
    uint8_t frame[UART_TLM_MAX_FRAME];
    uart_tlm_telemetry_t t;
    memset(&t, 0, sizeof t);
    t.flags = UART_TLM_F_GPS_VALID;
    t.lat_deg1e7 = 1;
    t.lon_deg1e7 = 2;
    int n = uart_tlm_encode_telemetry(frame, sizeof frame, 5, &t);

    uint8_t type = 0, seq = 0, plen = 0;
    uint8_t payload[UART_TLM_MAX_PAYLOAD];

    /* Short input -> LEN error. */
    CHECK(uart_tlm_decode_frame(frame, 4, &type, &seq, payload, &plen) == UART_TLM_ERR_LEN,
          "input shorter than a header+CRC is a length error");

    /* Bad SOF -> TYPE error. */
    uint8_t badsof[UART_TLM_MAX_FRAME];
    memcpy(badsof, frame, (size_t)n);
    badsof[1] = 0x54;
    CHECK(uart_tlm_decode_frame(badsof, (uint32_t)n, &type, &seq, payload, &plen) == UART_TLM_ERR_TYPE,
          "bad SOF is a type error");

    /* Truncated body -> LEN error. */
    CHECK(uart_tlm_decode_frame(frame, (uint32_t)(n - 1), &type, &seq, payload, &plen) == UART_TLM_ERR_LEN,
          "truncated frame is a length error");

    /* Trailing bytes are tolerated: exactly the frame is consumed. */
    uint8_t padded[UART_TLM_MAX_FRAME + 8];
    memcpy(padded, frame, (size_t)n);
    memset(padded + n, 0x00, 8);
    CHECK(uart_tlm_decode_frame(padded, sizeof padded, &type, &seq, payload, &plen) == n,
          "trailing bytes do not change the consumed length");

    /* NULL is rejected, not crashed on. */
    CHECK(uart_tlm_decode_frame(NULL, 10, &type, &seq, payload, &plen) == UART_TLM_ERR_ARG,
          "NULL input is rejected");
}

/* ── Determinism / no hidden state ──────────────────────────────────────── */

static void test_encoder_determinism(void)
{
    uart_tlm_telemetry_t t;
    memset(&t, 0, sizeof t);
    t.seq = 99;
    t.flags = UART_TLM_F_GPS_VALID;
    t.lat_deg1e7 = 515000000;
    t.lon_deg1e7 = -1;
    t.alt_mm = 35000;
    t.battery_mv = 3721;
    t.solar_mv = 0;
    t.temp_cdeg = -1234;
    t.pressure_hpa10 = 9987;
    t.sats = 6;
    t.hdop_x10 = 12;
    t.tx_mode = UART_TLM_TXMODE_LORA;

    uint8_t a[UART_TLM_MAX_FRAME], b[UART_TLM_MAX_FRAME];
    int na = uart_tlm_encode_telemetry(a, sizeof a, 77, &t);
    int nb = uart_tlm_encode_telemetry(b, sizeof b, 77, &t);
    CHECK(na == nb && na > 0, "encode is stable in length");
    CHECK(memcmp(a, b, (size_t)na) == 0, "encode is byte-for-byte deterministic");

    /* Different payload -> different CRC. */
    t.sats = 7;
    uint8_t c[UART_TLM_MAX_FRAME];
    int nc = uart_tlm_encode_telemetry(c, sizeof c, 77, &t);
    CHECK(nc == na && memcmp(a, c, (size_t)(nc - 2)) != 0, "payload change alters the frame");

    /* Round-trip through the decoder must reproduce every field. */
    uint8_t type = 0, seq = 0, plen = 0, payload[UART_TLM_MAX_PAYLOAD];
    t.sats = 6;
    int n = uart_tlm_encode_telemetry(a, sizeof a, 77, &t);
    CHECK(uart_tlm_decode_frame(a, (uint32_t)n, &type, &seq, payload, &plen) == n, "frame decodes");
    uart_tlm_telemetry_t back;
    memset(&back, 0, sizeof back);
    CHECK(uart_tlm_bytes_to_telemetry(payload, &back), "payload decodes");
    CHECK(memcmp(&back, &t, sizeof t) == 0, "every telemetry field round-trips exactly");
    CHECK(seq == 77, "frame seq round-trips");
}

/* ── Payload-length table ───────────────────────────────────────────────── */

static void test_payload_len_table(void)
{
    CHECK(uart_tlm_payload_len(UART_TLM_TYPE_TELEMETRY) == UART_TLM_TELEMETRY_LEN, "TELEMETRY length");
    CHECK(uart_tlm_payload_len(UART_TLM_TYPE_MESH_STATUS) == UART_TLM_MESH_STATUS_LEN, "MESH_STATUS length");
    CHECK(uart_tlm_payload_len(0x00) == 0, "unknown type has no length");
    CHECK(uart_tlm_payload_len(0xFF) == 0, "unknown type has no length");

    /* Both fixed sizes must fit the protocol maximum. */
    CHECK(UART_TLM_TELEMETRY_LEN <= UART_TLM_MAX_PAYLOAD, "TELEMETRY fits MAX_PAYLOAD");
    CHECK(UART_TLM_MESH_STATUS_LEN <= UART_TLM_MAX_PAYLOAD, "MESH_STATUS fits MAX_PAYLOAD");
}

int main(void)
{
    test_crc_golden();
    test_frame_size_and_sof();
    test_wire_endianness();
    test_mesh_status_roundtrip();
    test_encoder_errors();
    test_decoder_stream();
    test_decoder_resync_noise();
    test_decoder_corruption();
    test_sequence_gaps();
    test_validators();
    test_decode_frame_buffer();
    test_encoder_determinism();
    test_payload_len_table();

    printf("test_uart_telemetry: %d passed, %d failed\n", g_pass, g_fail);
    if (g_fail == 0) {
        printf("RESULT: ALL PASS\n");
        return 0;
    }
    printf("RESULT: FAILURES PRESENT\n");
    return 1;
}
