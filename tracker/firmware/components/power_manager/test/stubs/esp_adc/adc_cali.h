#pragma once
/*
 * Scriptable host double for ESP-IDF's esp_adc/adc_cali.h — config struct +
 * prototypes only. See adc_oneshot.h in this directory for why the suite carries
 * its own adc stubs instead of the read-only shared ones.
 */
#include <stdint.h>
#include "esp_adc/adc_oneshot.h"

typedef struct adc_cali *adc_cali_handle_t;

typedef struct {
    adc_unit_t     unit_id;
    adc_channel_t  chan;
    adc_atten_t    atten;
    adc_bitwidth_t bitwidth;
} adc_cali_curve_fitting_config_t;

esp_err_t adc_cali_create_scheme_curve_fitting(
    const adc_cali_curve_fitting_config_t *cfg, adc_cali_handle_t *handle);
esp_err_t adc_cali_raw_to_voltage(adc_cali_handle_t handle, int raw, int *voltage);
