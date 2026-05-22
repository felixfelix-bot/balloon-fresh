#pragma once

#include <stdint.h>

typedef int esp_err_t;
#define ESP_OK 0

typedef enum { ADC_CHANNEL_0 = 0 } adc_channel_t;
typedef enum { ADC_UNIT_1 = 0 } adc_unit_t;
typedef enum { ADC_ATTEN_DB_12 = 0 } adc_atten_t;
typedef enum { ADC_BITWIDTH_12 = 0 } adc_bitwidth_t;

typedef struct adc_oneshot_unit *adc_oneshot_unit_handle_t;
typedef struct adc_cali *adc_cali_handle_t;

typedef struct {
    adc_unit_t unit_id;
} adc_oneshot_unit_init_cfg_t;

typedef struct {
    adc_atten_t atten;
    adc_bitwidth_t bitwidth;
} adc_oneshot_chan_cfg_t;

static inline esp_err_t adc_oneshot_new_unit(const adc_oneshot_unit_init_cfg_t *cfg, adc_oneshot_unit_handle_t *handle) {
    (void)cfg; (void)handle; return ESP_OK;
}
static inline esp_err_t adc_oneshot_config_channel(adc_oneshot_unit_handle_t handle, adc_channel_t chan, const adc_oneshot_chan_cfg_t *cfg) {
    (void)handle; (void)chan; (void)cfg; return ESP_OK;
}
static inline esp_err_t adc_oneshot_read(adc_oneshot_unit_handle_t handle, adc_channel_t chan, int *out) {
    (void)handle; (void)chan; *out = 0; return ESP_OK;
}
