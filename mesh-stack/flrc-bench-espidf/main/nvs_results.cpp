#include "nvs_results.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "nvs.h"
#include <stdio.h>
#include <string.h>

static const char *TAG = "NVS";

int nvs_init() {
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_LOGW(TAG, "NVS partition needs erase, erasing...");
        nvs_flash_erase();
        err = nvs_flash_init();
    }
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "NVS init failed: %s", esp_err_to_name(err));
        return -1;
    }
    return 0;
}

static nvs_handle_t open_nvs(nvs_open_mode_t mode) {
    nvs_handle_t handle;
    esp_err_t err = nvs_open(NVS_NAMESPACE, mode, &handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "NVS open failed: %s", esp_err_to_name(err));
        return 0;
    }
    return handle;
}

int nvs_get_count(uint8_t *count) {
    nvs_handle_t h = open_nvs(NVS_READONLY);
    if (!h) { *count = 0; return 0; }
    esp_err_t err = nvs_get_u8(h, NVS_KEY_COUNT, count);
    nvs_close(h);
    if (err == ESP_ERR_NVS_NOT_FOUND) { *count = 0; return 0; }
    if (err != ESP_OK) { ESP_LOGE(TAG, "get count failed"); return -1; }
    return 0;
}

int nvs_set_count(uint8_t count) {
    nvs_handle_t h = open_nvs(NVS_READWRITE);
    if (!h) return -1;
    esp_err_t err = nvs_set_u8(h, NVS_KEY_COUNT, count);
    if (err != ESP_OK) { nvs_close(h); return -1; }
    err = nvs_commit(h);
    nvs_close(h);
    return err == ESP_OK ? 0 : -1;
}

static char key_buf[16];

static const char *result_key(uint8_t index) {
    snprintf(key_buf, sizeof(key_buf), "test_%u", index);
    return key_buf;
}

int nvs_save_result(uint8_t index, const NvsTestResult *result) {
    if (index >= NVS_MAX_RESULTS) return -1;
    nvs_handle_t h = open_nvs(NVS_READWRITE);
    if (!h) return -1;
    esp_err_t err = nvs_set_blob(h, result_key(index), result, sizeof(NvsTestResult));
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "save test_%u failed: %s", index, esp_err_to_name(err));
        nvs_close(h);
        return -1;
    }
    err = nvs_commit(h);
    nvs_close(h);
    return err == ESP_OK ? 0 : -1;
}

int nvs_load_result(uint8_t index, NvsTestResult *result) {
    if (index >= NVS_MAX_RESULTS) return -1;
    nvs_handle_t h = open_nvs(NVS_READONLY);
    if (!h) return -1;
    size_t required_size = sizeof(NvsTestResult);
    esp_err_t err = nvs_get_blob(h, result_key(index), result, &required_size);
    nvs_close(h);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "load test_%u failed: %s", index, esp_err_to_name(err));
        return -1;
    }
    return 0;
}

int nvs_clear_all() {
    nvs_handle_t h = open_nvs(NVS_READWRITE);
    if (!h) return -1;
    nvs_set_u8(h, NVS_KEY_COUNT, 0);
    nvs_commit(h);
    nvs_close(h);
    return 0;
}

void nvs_print_all_results() {
    uint8_t count = 0;
    nvs_get_count(&count);
    if (count == 0) {
        printf("No results stored\n");
        return;
    }
    printf("test_name,mode,freq,bitrate,sf,cr,power,pkt_size,tx_sent,rx_received,crc_errors,lost,per_pct,ber_pct,avg_rssi,min_rssi,max_rssi,elapsed_ms,throughput_kbps,payload_corrupt,bit_errors,bits_checked\n");
    for (uint8_t i = 0; i < count; i++) {
        NvsTestResult r;
        if (nvs_load_result(i, &r) != 0) {
            printf("ERR,test_%u,,,,,,,,,,,,,,,,,,,,,\n", i);
            continue;
        }
        printf("%.15s,%s,%.1f,%u,%u,0x%02X,%d,%u,%u,%u,%u,%u,%.3f,%.6f,%d,%d,%d,%lu,%.1f,%u,%u,%lu\n",
               r.name,
               r.mode == 0 ? "FLRC" : "LORA",
               r.freq,
               r.bitrate,
               r.sf,
               r.cr,
               r.power,
               r.pkt_size,
               r.tx_sent,
               r.rx_received,
               r.crc_errors,
               r.lost,
               r.per_pct,
               r.ber_pct,
               r.avg_rssi,
               r.min_rssi,
               r.max_rssi,
               (unsigned long)r.elapsed_ms,
               r.throughput_kbps,
               r.payload_corrupt,
               r.bit_errors,
               (unsigned long)r.bits_checked);
    }
    printf("(%u results)\n", count);
}
