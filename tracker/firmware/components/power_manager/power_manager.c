#include "power_manager.h"
#include "esp_log.h"
#ifdef SUPERCAP_MONITORING
#include "esp_adc/adc_oneshot.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#endif

static const char *TAG = "POWER";

/*
 * Supercap voltage monitoring is DISABLED for PCB V1.
 *
 * The supercap divider taps ADC1_CH0, which is GPIO0 on the ESP32-C3 — the same
 * pin as GPS UART TX. There is no free ADC-capable GPIO left on the V1 pinout,
 * so enabling this would fight the GPS transmitter for GPIO0.
 *
 * Define SUPERCAP_MONITORING to compile the ADC path back in (V2, once a free
 * ADC pin exists). Undefined for V1 — see docs/coordination/PCB-AUTOROUTE-EXECUTION-PLAN.md Phase 5.
 */
#ifdef SUPERCAP_MONITORING

#define SUPERCAP_ADC_CHANNEL ADC_CHANNEL_0
#define SUPERCAP_ADC_UNIT ADC_UNIT_1
#define VOLTAGE_DIVIDER_R1 1000000
#define VOLTAGE_DIVIDER_R2 1000000

static adc_oneshot_unit_handle_t adc_handle = NULL;
static adc_cali_handle_t cali_handle = NULL;
static bool adc_ready = false;

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

    adc_ready = true;
    ESP_LOGI(TAG, "Power manager initialized (ADC ch0)");
    return ESP_OK;
}

uint16_t power_manager_read_supercap_mv(void)
{
    if (!adc_ready) {
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

#else /* !SUPERCAP_MONITORING — V1 flight: ADC path compiled out (GPIO0 = GPS TX) */

esp_err_t power_manager_init(void)
{
    ESP_LOGI(TAG, "Power manager: supercap monitoring disabled for V1 (no free ADC pin; ADC1_CH0=GPIO0=GPS TX)");
    return ESP_OK;
}

uint16_t power_manager_read_supercap_mv(void)
{
    /* No supercap ADC in V1 — report 0 mV and let the low-voltage check be a no-op. */
    return 0;
}

#endif /* SUPERCAP_MONITORING */

int power_manager_raw_to_mv(int raw, int calibrated_mv) {
    int voltage_mv = calibrated_mv;
    if (voltage_mv == 0) {
        voltage_mv = raw * 3300 / 4095;
    }
    return voltage_mv * 2;
}
