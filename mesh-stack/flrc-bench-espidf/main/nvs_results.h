#pragma once

#include <stdint.h>
#include <stddef.h>

#define NVS_NAMESPACE "bench"
#define NVS_MAX_RESULTS 32
#define NVS_KEY_COUNT "count"

struct NvsTestResult {
    char name[16];
    uint8_t mode;
    float freq;
    uint16_t bitrate;
    uint8_t sf;
    uint8_t cr;
    int8_t power;
    uint16_t pkt_size;
    uint16_t tx_sent;
    uint16_t rx_received;
    uint16_t crc_errors;
    uint16_t lost;
    float per_pct;
    float ber_pct;
    int16_t avg_rssi;
    int16_t min_rssi;
    int16_t max_rssi;
    uint32_t elapsed_ms;
    float throughput_kbps;
    uint16_t payload_corrupt;
    uint16_t bit_errors;
    uint32_t bits_checked;
};

int nvs_init();
int nvs_save_result(uint8_t index, const NvsTestResult *result);
int nvs_load_result(uint8_t index, NvsTestResult *result);
int nvs_get_count(uint8_t *count);
int nvs_set_count(uint8_t count);
int nvs_clear_all();
void nvs_print_all_results();
