#pragma once

#include <stdint.h>
#include "esp_err.h"

/*
 * Returned by power_manager_read_supercap_mv() when the supercap divider is not
 * populated / monitoring is compiled out. 0xFFFF is outside the divider's
 * physical range (R1=R2=1M => max 6600 mV) and therefore above any low-voltage
 * threshold, so a consumer comparing `mv < LOW_VOLTAGE_MV + 200` sees
 * "not low" rather than a false LOW_POWER, and a ground station can detect
 * "not measured" from the out-of-range value.
 */
#define POWER_MANAGER_MV_INVALID ((uint16_t)0xFFFF)

uint16_t power_manager_read_supercap_mv(void);
esp_err_t power_manager_init(void);
int power_manager_raw_to_mv(int raw, int calibrated_mv);
