#pragma once

#include <stdint.h>
#include <stddef.h>

#define RANGE_WINDOW_COUNT 16
#define RANGE_SYNC_COUNT 5
#define RANGE_END_COUNT 3
#define RANGE_SYNC_PKT_LEN 20
#define RANGE_GAP_MS 10000
#define RANGE_SCAN_TIMEOUT_MS 5000
#define RANGE_RX_TIMEOUT_MS 120000

#define RANGE_MAGIC_0 0xAA
#define RANGE_MAGIC_1 0x55
#define RANGE_TYPE_START 0x01
#define RANGE_TYPE_END 0x02

enum RangeMode { RANGE_LORA = 0, RANGE_FLRC = 1 };

struct RangeWindow {
    const char *name;
    RangeMode mode;
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
    uint16_t sync_delay_ms;
};

static const RangeWindow range_windows[] = {
    { "L12-868",     RANGE_LORA, 868.0f,  0,    12, 125.0f, 5,     22, 28,  20, 1000, 8,  2000 },
    { "L9-868",      RANGE_LORA, 868.0f,  0,    9,  125.0f, 5,     22, 28,  20, 1000, 8,  2000 },
    { "L9W-868",     RANGE_LORA, 868.0f,  0,    9,  500.0f, 5,     22, 28,  20, 500,  8,  2000 },
    { "L7-868",      RANGE_LORA, 868.0f,  0,    7,  125.0f, 5,     22, 28,  20, 500,  8,  2000 },
    { "L9CR7-868",   RANGE_LORA, 868.0f,  0,    9,  125.0f, 7,     22, 28,  20, 1000, 8,  2000 },
    { "L12-2G4",     RANGE_LORA, 2450.0f, 0,    12, 125.0f, 5,     12, 28,  20, 1000, 8,  2000 },
    { "L9-2G4",      RANGE_LORA, 2450.0f, 0,    9,  125.0f, 5,     12, 28,  20, 1000, 8,  2000 },
    { "L7-2G4",      RANGE_LORA, 2450.0f, 0,    7,  125.0f, 5,     12, 28,  20, 500,  8,  2000 },
    { "F260-868",    RANGE_FLRC, 868.0f,  260,  0,  0.0f,   0x00,  22, 50,  50, 100,  16, 500  },
    { "F650-868",    RANGE_FLRC, 868.0f,  650,  0,  0.0f,   0x01,  22, 50,  50, 50,   16, 500  },
    { "F1300-868",   RANGE_FLRC, 868.0f,  1300, 0,  0.0f,   0x02,  22, 100, 100, 10,  16, 500  },
    { "F1300C34-868",RANGE_FLRC, 868.0f,  1300, 0,  0.0f,   0x01,  22, 100, 100, 10,  16, 500  },
    { "F2600-868",   RANGE_FLRC, 868.0f,  2600, 0,  0.0f,   0x02,  22, 100, 100, 10,  16, 500  },
    { "F260-2G4",    RANGE_FLRC, 2450.0f, 260,  0,  0.0f,   0x00,  12, 50,  50, 100,  16, 500  },
    { "F1300-2G4",   RANGE_FLRC, 2450.0f, 1300, 0,  0.0f,   0x02,  12, 100, 100, 10,  16, 500  },
    { "F2600-2G4",   RANGE_FLRC, 2450.0f, 2600, 0,  0.0f,   0x02,  12, 100, 100, 10,  16, 500  },
};

static inline void range_build_sync(uint8_t *buf, uint8_t type, uint8_t win_id,
                                     const RangeWindow *w, uint16_t tx_sent) {
    buf[0] = RANGE_MAGIC_0;
    buf[1] = RANGE_MAGIC_1;
    buf[2] = type;
    buf[3] = win_id;
    buf[4] = (uint8_t)w->mode;
    uint32_t freq_hz = (uint32_t)(w->freq * 1000000.0f);
    buf[5] = (freq_hz >> 24) & 0xFF;
    buf[6] = (freq_hz >> 16) & 0xFF;
    buf[7] = (freq_hz >> 8) & 0xFF;
    buf[8] = freq_hz & 0xFF;
    buf[9] = (w->bitrate >> 8) & 0xFF;
    buf[10] = w->bitrate & 0xFF;
    buf[11] = w->sf;
    buf[12] = w->cr;
    buf[13] = (uint8_t)w->power;
    buf[14] = (w->pkt_size >> 8) & 0xFF;
    buf[15] = w->pkt_size & 0xFF;
    buf[16] = (w->pkt_count >> 8) & 0xFF;
    buf[17] = w->pkt_count & 0xFF;
    buf[18] = (tx_sent >> 8) & 0xFF;
    buf[19] = tx_sent & 0xFF;
}

static inline bool range_parse_sync(const uint8_t *buf, size_t len, uint8_t *type,
                                     uint8_t *win_id, RangeWindow *w, uint16_t *tx_sent) {
    if (len < RANGE_SYNC_PKT_LEN) return false;
    if (buf[0] != RANGE_MAGIC_0 || buf[1] != RANGE_MAGIC_1) return false;
    *type = buf[2];
    *win_id = buf[3];
    if (w) {
        w->mode = (RangeMode)buf[4];
        uint32_t freq_hz = ((uint32_t)buf[5] << 24) | ((uint32_t)buf[6] << 16) |
                           ((uint32_t)buf[7] << 8) | (uint32_t)buf[8];
        w->freq = freq_hz / 1000000.0f;
        w->bitrate = ((uint16_t)buf[9] << 8) | (uint16_t)buf[10];
        w->sf = buf[11];
        w->cr = buf[12];
        w->power = (int8_t)buf[13];
        w->pkt_size = ((uint16_t)buf[14] << 8) | (uint16_t)buf[15];
        w->pkt_count = ((uint16_t)buf[16] << 8) | (uint16_t)buf[17];
        w->tx_delay_ms = 0;
        w->preamble = 16;
        w->sync_delay_ms = 500;
        w->name = "remote";
    }
    if (tx_sent) {
        *tx_sent = ((uint16_t)buf[18] << 8) | (uint16_t)buf[19];
    }
    return true;
}

struct RangeScanMode {
    RangeMode mode;
    float freq;
    uint16_t bitrate;
    uint8_t sf;
    float bw;
    uint8_t cr;
    int8_t power;
};

static const RangeScanMode range_scan_modes[] = {
    { RANGE_FLRC, 868.0f,  2600, 0, 0.0f,   0x02, 22 },
    { RANGE_FLRC, 868.0f,  1300, 0, 0.0f,   0x02, 22 },
    { RANGE_FLRC, 868.0f,  650,  0, 0.0f,   0x01, 22 },
    { RANGE_FLRC, 868.0f,  260,  0, 0.0f,   0x00, 22 },
    { RANGE_FLRC, 2450.0f, 2600, 0, 0.0f,   0x02, 12 },
    { RANGE_FLRC, 2450.0f, 1300, 0, 0.0f,   0x02, 12 },
    { RANGE_FLRC, 2450.0f, 260,  0, 0.0f,   0x00, 12 },
    { RANGE_LORA, 868.0f,  0,    9, 125.0f, 5,    22 },
    { RANGE_LORA, 868.0f,  0,    12, 125.0f, 5,    22 },
    { RANGE_LORA, 868.0f,  0,    7,  125.0f, 5,    22 },
    { RANGE_LORA, 2450.0f, 0,    9,  125.0f, 5,    12 },
    { RANGE_LORA, 2450.0f, 0,    12, 125.0f, 5,    12 },
    { RANGE_LORA, 2450.0f, 0,    7,  125.0f, 5,    12 },
};

#define RANGE_SCAN_MODE_COUNT (sizeof(range_scan_modes) / sizeof(range_scan_modes[0]))
