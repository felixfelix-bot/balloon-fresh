/*
 * Host-side test for the supercap-monitoring compile-time guard.
 *
 * WHY THIS EXISTS (Gate 1 / RED before the fix in this branch):
 *   - V1 compiles the ADC path OUT. Before this test the `#else` stub returned
 *     literal 0, and the code comment claimed the low-voltage check became "a
 *     no-op" — it does not: `0 < CONFIG_LOW_VOLTAGE_MV + 200` is TRUE, so any
 *     consumer that is not itself compiled out reports LOW_POWER against an
 *     unpopulated divider, and telemetry broadcasts a believable "0 mV".
 *     (RED evidence, pre-fix stub: read = 0 mV and `0 < 3500` = TRUE.)
 *   - The guarded branch latched `adc_ready = true` unconditionally and ignored
 *     the return of adc_cali_create_scheme_curve_fitting(), so a failed init was
 *     never retried.
 *
 * Build (both sides of the #ifdef are asserted):
 *   gcc -Wall -Wextra -O2 -I . -I <shared stubs> -I test/stubs \
 *       -o /tmp/t_v1 test/test_power_manager_guard.c && /tmp/t_v1
 *   gcc -Wall -Wextra -O2 -DSUPERCAP_MONITORING -DTESTING_SUPERCAP_MONITORING \
 *       -I . -I <shared stubs> -I test/stubs -o /tmp/t_v2 \
 *       test/test_power_manager_guard.c && /tmp/t_v2
 */
#define TESTING_SUPERCAP_MONITORING 1   /* enables the scriptable adc doubles */

#include <stdio.h>
#include <stdarg.h>
#include <stdbool.h>
#include <string.h>

/* esp_err.h / esp_log.h come from the SHARED host stubs (tests/host_stubs), which
 * the other suites use. Only the esp_adc headers are overridden by test/stubs,
 * because the shared ones are read-only inlines and this suite has to script the
 * failure paths. */
#include "power_manager.h"

#ifdef SUPERCAP_MONITORING
/* Minimal driver double. Behaviour is scripted from the test via these globals. */
#include "esp_adc/adc_oneshot.h"
#include "esp_adc/adc_cali.h"

/* The shared esp_err.h stub has no name table; the monitored build logs errors. */
#define esp_err_to_name(code) ("TEST_ERR")

int  g_stub_new_unit_rc     = 0;
int  g_stub_config_chan_rc  = 0;
int  g_stub_cali_rc         = 0;
int  g_stub_read_rc         = 0;
int  g_stub_raw             = 2048;
int  g_stub_raw_to_voltage_rc = 0;

esp_err_t adc_oneshot_new_unit(const adc_oneshot_unit_init_cfg_t *cfg,
                               adc_oneshot_unit_handle_t *out)
{
    (void)cfg;
    if (g_stub_new_unit_rc == 0) { *out = (adc_oneshot_unit_handle_t)(void *)1; }
    return (esp_err_t)g_stub_new_unit_rc;
}

esp_err_t adc_oneshot_config_channel(adc_oneshot_unit_handle_t h,
                                     adc_channel_t ch,
                                     const adc_oneshot_chan_cfg_t *cfg)
{
    (void)h; (void)ch; (void)cfg;
    return (esp_err_t)g_stub_config_chan_rc;
}

esp_err_t adc_oneshot_read(adc_oneshot_unit_handle_t h, adc_channel_t ch, int *out)
{
    (void)h; (void)ch;
    if (g_stub_read_rc == 0) { *out = g_stub_raw; }
    return (esp_err_t)g_stub_read_rc;
}

esp_err_t adc_cali_create_scheme_curve_fitting(const adc_cali_curve_fitting_config_t *cfg,
                                               adc_cali_handle_t *out)
{
    (void)cfg;
    if (g_stub_cali_rc == 0) { *out = (adc_cali_handle_t)(void *)1; }
    return (esp_err_t)g_stub_cali_rc;
}

esp_err_t adc_cali_raw_to_voltage(adc_cali_handle_t h, int raw, int *out_mv)
{
    (void)h;
    if (g_stub_raw_to_voltage_rc == 0) { *out_mv = raw * 3300 / 4095; }
    return (esp_err_t)g_stub_raw_to_voltage_rc;
}
#endif /* SUPERCAP_MONITORING */

/* power_manager.c is not a header; include it so this TU owns its state. */
#include "../power_manager.c"

static int failures = 0;

#define CHECK(cond, msg) do {                                   \
    if (cond) { printf("PASS: %s\n", msg); }                    \
    else      { printf("FAIL: %s\n", msg); failures++; }        \
} while (0)

/* A representative low-voltage threshold from Kconfig (CONFIG_LOW_VOLTAGE_MV). */
#define TEST_LOW_VOLTAGE_MV 3300
#define TEST_LOW_POWER_LIMIT (TEST_LOW_VOLTAGE_MV + 200)

int main(void)
{
    printf("\n=== Power manager supercap-monitoring guard tests ===\n\n");

    uint16_t mv = power_manager_read_supercap_mv();

#ifndef SUPERCAP_MONITORING
    /* ── V1 build: ADC path compiled out ─────────────────────────────── */
    printf("-- V1 (SUPERCAP_MONITORING undefined) --\n");

    CHECK(mv == POWER_MANAGER_MV_INVALID,
          "stub returns POWER_MANAGER_MV_INVALID, not a fake 0 mV");

    /* The regression this test was written for: a 0 here is BELOW the limit and
     * therefore asserts LOW_POWER; the sentinel must not. */
    CHECK(!(mv < TEST_LOW_POWER_LIMIT),
          "sentinel does not trip the low-voltage comparison (0 would)");
    CHECK((uint16_t)0 < TEST_LOW_POWER_LIMIT,
          "control: a literal 0 WOULD trip the comparison (the bug being fixed)");

    CHECK(power_manager_init() == ESP_OK, "init succeeds (no-op) on V1");

    /* Repeating the read must stay stable — no state is latched on V1. */
    CHECK(power_manager_read_supercap_mv() == POWER_MANAGER_MV_INVALID,
          "repeat read stays POWER_MANAGER_MV_INVALID");

    /* ABI: the un-guarded helper is still compiled on V1. */
    CHECK(power_manager_raw_to_mv(4095, 0) == 6600,
          "power_manager_raw_to_mv() still available and correct on V1");
#else
    /* ── V2 build: ADC path compiled in ──────────────────────────────── */
    printf("-- V2 (SUPERCAP_MONITORING defined) --\n");

    /* 1. Happy path: calibrated read of 2048 raw -> ~3300 mV at the divider. */
    CHECK(power_manager_init() == ESP_OK, "init returns ESP_OK on success");
    mv = power_manager_read_supercap_mv();
    CHECK(mv > 3000 && mv < 3600, "calibrated happy-path read is in range");

    /* 2. Failed read reports "no measurement", never a fake 0 mV. */
    adc_ready = true; adc_handle = (adc_oneshot_unit_handle_t)(void *)1;
    cali_handle = (adc_cali_handle_t)(void *)1;
    g_stub_read_rc = -1;
    CHECK(power_manager_read_supercap_mv() == POWER_MANAGER_MV_INVALID,
          "failed adc_oneshot_read() returns the sentinel");
    g_stub_read_rc = 0;

    /* 3. Failed calibration falls back to raw scaling (does not latch ready). */
    cali_handle = NULL;
    mv = power_manager_read_supercap_mv();
    CHECK(mv == (uint16_t)((2048 * 3300 / 4095) * 2),
          "uncalibrated path falls back to raw scaling");

    /* 4. REGRESSION: a failed init must NOT latch readiness — the next read
     *    retries init instead of calling into a NULL unit. */
    adc_ready = false; adc_handle = NULL; cali_handle = NULL;
    g_stub_new_unit_rc = -1;
    CHECK(power_manager_read_supercap_mv() == POWER_MANAGER_MV_INVALID,
          "read after failed init returns the sentinel (no NULL deref)");
    CHECK(adc_ready == false, "failed init leaves adc_ready == false (retry possible)");

    g_stub_new_unit_rc = 0;      /* init recovers */
    mv = power_manager_read_supercap_mv();
    CHECK(mv > 3000 && mv < 3600, "next read retries init and succeeds");

    /* 5. Failed channel config is also not latched as ready. */
    adc_ready = false; adc_handle = NULL; cali_handle = NULL;
    g_stub_config_chan_rc = -1;
    CHECK(power_manager_read_supercap_mv() == POWER_MANAGER_MV_INVALID,
          "failed channel config returns the sentinel");
    CHECK(adc_ready == false, "failed channel config leaves adc_ready == false");
    g_stub_config_chan_rc = 0;

    /* 6. Failed calibration must not be latched as ready either. */
    adc_ready = false; adc_handle = NULL; cali_handle = NULL;
    g_stub_cali_rc = -1;
    CHECK(power_manager_init() == ESP_OK,
          "init succeeds when calibration is unavailable (raw fallback)");
    CHECK(cali_handle == NULL, "failed calibration leaves cali_handle == NULL");
    g_stub_cali_rc = 0;
#endif

    if (failures) {
        printf("\n=== Results: %d FAILED ===\n", failures);
        return 1;
    }
    printf("\n=== Results: all passed ===\n");
    return 0;
}
