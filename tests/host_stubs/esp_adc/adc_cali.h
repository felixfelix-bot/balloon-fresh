#pragma once

#include "adc_oneshot.h"

typedef struct {
    int unit_id;
    int chan;
    int atten;
    int bitwidth;
} adc_cali_curve_fitting_config_t;

static inline esp_err_t adc_cali_create_scheme_curve_fitting(const adc_cali_curve_fitting_config_t *cfg, adc_cali_handle_t *handle) {
    (void)cfg; (void)handle; return ESP_OK;
}
static inline esp_err_t adc_cali_raw_to_voltage(adc_cali_handle_t handle, int raw, int *voltage) {
    (void)handle; (void)raw; *voltage = 0; return ESP_OK;
}
