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
    esp_err_t err = adc_oneshot_new_unit(&init_cfg, &adc_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "adc_oneshot_new_unit failed: %s", esp_err_to_name(err));
        adc_handle = NULL;
        adc_ready = false;
        return err;
    }

    adc_oneshot_chan_cfg_t chan_cfg = {
        .atten = ADC_ATTEN_DB_12,
        .bitwidth = ADC_BITWIDTH_12,
    };
    err = adc_oneshot_config_channel(adc_handle, SUPERCAP_ADC_CHANNEL, &chan_cfg);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "adc_oneshot_config_channel failed: %s", esp_err_to_name(err));
        adc_ready = false;
        return err;
    }

    adc_cali_curve_fitting_config_t cali_cfg = {
        .unit_id = SUPERCAP_ADC_UNIT,
        .chan = SUPERCAP_ADC_CHANNEL,
        .atten = ADC_ATTEN_DB_12,
        .bitwidth = ADC_BITWIDTH_12,
    };
    /* Curve fitting is optional: the read path falls back to the raw scaling
     * below when calibration is unavailable, so a failure here must NOT set
     * adc_ready (that would latch a half-initialised unit as ready). */
    esp_err_t cali_err = adc_cali_create_scheme_curve_fitting(&cali_cfg, &cali_handle);
    if (cali_err != ESP_OK) {
        cali_handle = NULL;
        ESP_LOGW(TAG, "ADC calibration unavailable (%s), using raw scaling",
                 esp_err_to_name(cali_err));
    }

    adc_ready = true;
    ESP_LOGI(TAG, "Power manager initialized (ADC ch0)");
    return ESP_OK;
}

uint16_t power_manager_read_supercap_mv(void)
{
    /* Retry init on every read while the unit is not ready — a failed
     * adc_oneshot_new_unit()/config_channel() must not be latched forever. */
    if (!adc_ready && power_manager_init() != ESP_OK) {
        return POWER_MANAGER_MV_INVALID;
    }
    if (adc_handle == NULL) {
        return POWER_MANAGER_MV_INVALID;
    }

    int raw = 0;
    if (adc_oneshot_read(adc_handle, SUPERCAP_ADC_CHANNEL, &raw) != ESP_OK) {
        return POWER_MANAGER_MV_INVALID;
    }

    int voltage_mv = 0;
    if (cali_handle) {
        if (adc_cali_raw_to_voltage(cali_handle, raw, &voltage_mv) != ESP_OK) {
            voltage_mv = raw * 3300 / 4095;
        }
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
    /*
     * No supercap ADC on V1 (the only ADC-capable pins are already taken, and
     * ADC1_CH0 is GPIO0 = GPS TX), so there is no measurement to report.
     * Return the out-of-range sentinel rather than 0:
     *  - `mv < CONFIG_LOW_VOLTAGE_MV + 200` is FALSE for 0xFFFF, so a caller that
     *    is not compiled out itself cannot report a false LOW_POWER / flat cap;
     *  - telemetry carries 0xFFFF ("not measured") instead of broadcasting a
     *    believable-but-wrong "0 mV" that a ground station would alarm on.
     */
    return POWER_MANAGER_MV_INVALID;
}

#endif /* SUPERCAP_MONITORING */

int power_manager_raw_to_mv(int raw, int calibrated_mv) {
    int voltage_mv = calibrated_mv;
    if (voltage_mv == 0) {
        voltage_mv = raw * 3300 / 4095;
    }
    return voltage_mv * 2;
}
