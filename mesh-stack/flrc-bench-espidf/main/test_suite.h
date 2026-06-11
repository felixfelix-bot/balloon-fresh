#pragma once

#include <stdint.h>
#include <stddef.h>

#define MARKER_MAGIC_0 0xAA
#define MARKER_MAGIC_1 0x55
#define MARKER_TYPE_START 0x01
#define MARKER_TYPE_END 0x02
#define MARKER_PKT_LEN 20
#define AUTONOMOUS_TEST_COUNT 6
#define AUTONOMOUS_RX_TIMEOUT_MS 120000

enum AutoMode { AUTO_FLRC, AUTO_LORA };

struct AutoTest {
    const char *name;
    AutoMode mode;
    float freq;
    uint16_t bitrate;
    uint8_t sf;
    float bw;
    uint8_t cr;
    int8_t power;
    uint16_t pkt_size;
    uint16_t pkt_count;
    uint16_t tx_delay_ms;
    uint16_t preamble;
};

static const AutoTest auto_tests[] = {
    { "F2-868",   AUTO_FLRC, 868.0f,  2600, 0, 0.0f,   0x02,  22, 100, 100, 10,   16 },
    { "F1-868",   AUTO_FLRC, 868.0f,  1300, 0, 0.0f,   0x02,  22, 100, 100, 10,   16 },
    { "2G4-F1",   AUTO_FLRC, 2450.0f, 1300, 0, 0.0f,   0x02,  12, 100, 100, 10,   16 },
    { "2G4-F2",   AUTO_FLRC, 2450.0f, 2600, 0, 0.0f,   0x02,  12, 100, 100, 10,   16 },
    { "BURST",    AUTO_FLRC, 868.0f,  2600, 0, 0.0f,   0x02,  22, 200, 200, 0,    16 },
    { "L1-868",   AUTO_LORA, 868.0f,  0,    9, 125.0f, 7,     22, 28,  10, 1000, 8 },
};

static inline void build_marker(uint8_t *buf, uint8_t type, uint8_t test_id,
                                 const AutoTest *t, uint32_t tx_sent) {
    buf[0] = MARKER_MAGIC_0;
    buf[1] = MARKER_MAGIC_1;
    buf[2] = type;
    buf[3] = test_id;
    buf[4] = (uint8_t)t->mode;
    uint32_t freq_hz = (uint32_t)(t->freq * 1000000.0f);
    buf[5] = (freq_hz >> 24) & 0xFF;
    buf[6] = (freq_hz >> 16) & 0xFF;
    buf[7] = (freq_hz >> 8) & 0xFF;
    buf[8] = freq_hz & 0xFF;
    buf[9] = (t->bitrate >> 8) & 0xFF;
    buf[10] = t->bitrate & 0xFF;
    buf[11] = t->sf;
    buf[12] = t->cr;
    buf[13] = (uint8_t)t->power;
    buf[14] = (t->pkt_size >> 8) & 0xFF;
    buf[15] = t->pkt_size & 0xFF;
    buf[16] = (t->pkt_count >> 8) & 0xFF;
    buf[17] = t->pkt_count & 0xFF;
    if (type == MARKER_TYPE_END) {
        buf[18] = (tx_sent >> 8) & 0xFF;
        buf[19] = tx_sent & 0xFF;
    } else {
        buf[18] = 0;
        buf[19] = 0;
    }
}

static inline bool parse_marker(const uint8_t *buf, size_t len, uint8_t *type,
                                 uint8_t *test_id, AutoTest *t, uint32_t *tx_sent) {
    if (len < MARKER_PKT_LEN) return false;
    if (buf[0] != MARKER_MAGIC_0 || buf[1] != MARKER_MAGIC_1) return false;
    *type = buf[2];
    *test_id = buf[3];
    if (t) {
        t->mode = (AutoMode)buf[4];
        uint32_t freq_hz = ((uint32_t)buf[5] << 24) | ((uint32_t)buf[6] << 16) |
                           ((uint32_t)buf[7] << 8) | (uint32_t)buf[8];
        t->freq = freq_hz / 1000000.0f;
        t->bitrate = ((uint16_t)buf[9] << 8) | (uint16_t)buf[10];
        t->sf = buf[11];
        t->cr = buf[12];
        t->power = (int8_t)buf[13];
        t->pkt_size = ((uint16_t)buf[14] << 8) | (uint16_t)buf[15];
        t->pkt_count = ((uint16_t)buf[16] << 8) | (uint16_t)buf[17];
        t->tx_delay_ms = 0;
        t->preamble = 16;
        t->name = "remote";
    }
    if (tx_sent) {
        *tx_sent = ((uint32_t)buf[18] << 8) | (uint32_t)buf[19];
    }
    return true;
}
