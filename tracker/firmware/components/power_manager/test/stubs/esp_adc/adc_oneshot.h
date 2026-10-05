#pragma once
/*
 * Scriptable host double for ESP-IDF's esp_adc/adc_oneshot.h — types + prototypes
 * only (no `static inline` bodies), so test_power_manager_guard.c can drive the
 * NEGATIVE paths (failed init / failed read / failed calibration) that the shared
 * read-only stub in tests/host_stubs cannot express. Type names and the
 * ADC_CHANNEL_0 / ADC_UNIT_1 / ADC_ATTEN_DB_12 / ADC_BITWIDTH_12 enumerators
 * mirror both the real header and tests/host_stubs/esp_adc/adc_oneshot.h.
 *
 * Only this suite uses this directory (-I test/stubs), and it is placed FIRST on
 * the include path. Everything else (esp_err.h, esp_log.h, driver, freertos) still
 * resolves to the shared tests/host_stubs.
 */
#include <stdint.h>

typedef int esp_err_t;

typedef enum { ADC_CHANNEL_0 = 0 } adc_channel_t;
typedef enum { ADC_UNIT_1 = 0 } adc_unit_t;
typedef enum { ADC_ATTEN_DB_12 = 0 } adc_atten_t;
typedef enum { ADC_BITWIDTH_12 = 0 } adc_bitwidth_t;

typedef struct adc_oneshot_unit *adc_oneshot_unit_handle_t;

typedef struct {
    adc_unit_t unit_id;
} adc_oneshot_unit_init_cfg_t;

typedef struct {
    adc_atten_t    atten;
    adc_bitwidth_t bitwidth;
} adc_oneshot_chan_cfg_t;

esp_err_t adc_oneshot_new_unit(const adc_oneshot_unit_init_cfg_t *cfg,
                               adc_oneshot_unit_handle_t *handle);
esp_err_t adc_oneshot_config_channel(adc_oneshot_unit_handle_t handle,
                                     adc_channel_t chan,
                                     const adc_oneshot_chan_cfg_t *cfg);
esp_err_t adc_oneshot_read(adc_oneshot_unit_handle_t handle,
                           adc_channel_t chan, int *out);
