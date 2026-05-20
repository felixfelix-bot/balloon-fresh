#include "power_manager.h"
#include "esp_log.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"

static const char *TAG = "POWER";

#define SUPERCAP_ADC_CHANNEL ADC_CHANNEL_0
#define SUPERCAP_ADC_UNIT ADC_UNIT_1
#define VOLTAGE_DIVIDER_R1 1000000
#define VOLTAGE_DIVIDER_R2 1000000

static adc_oneshot_unit_handle_t adc_handle = NULL;
static adc_cali_handle_t cali_handle = NULL;

esp_err_t power_manager_init(void)
{
    adc_oneshot_unit_init_cfg_t init_cfg = {
        .unit_id = SUPERCAP_ADC_UNIT,
    };
    adc_oneshot_new_unit(&init_cfg, &adc_handle);

    adc_oneshot_chan_cfg_t chan_cfg = {
        .atten = ADC_ATTEN_DB_12,
        .bitwidth = ADC_BITWIDTH_12,
    };
    adc_oneshot_config_channel(adc_handle, SUPERCAP_ADC_CHANNEL, &chan_cfg);

    adc_cali_curve_fitting_config_t cali_cfg = {
        .unit_id = SUPERCAP_ADC_UNIT,
        .chan = SUPERCAP_ADC_CHANNEL,
        .atten = ADC_ATTEN_DB_12,
        .bitwidth = ADC_BITWIDTH_12,
    };
    adc_cali_create_scheme_curve_fitting(&cali_cfg, &cali_handle);

    ESP_LOGI(TAG, "Power manager initialized (ADC ch0)");
    return ESP_OK;
}

uint16_t power_manager_read_supercap_mv(void)
{
    if (!adc_handle) {
        power_manager_init();
    }

    int raw = 0;
    adc_oneshot_read(adc_handle, SUPERCAP_ADC_CHANNEL, &raw);

    int voltage_mv = 0;
    if (cali_handle) {
        adc_cali_raw_to_voltage(cali_handle, raw, &voltage_mv);
    } else {
        voltage_mv = raw * 3300 / 4095;
    }

    uint16_t cap_mv = (uint16_t)(voltage_mv * 2);
    return cap_mv;
}
