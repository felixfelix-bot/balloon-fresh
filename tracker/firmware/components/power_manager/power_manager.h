#pragma once

#include <stdint.h>
#include "esp_err.h"

uint16_t power_manager_read_supercap_mv(void);
esp_err_t power_manager_init(void);
int power_manager_raw_to_mv(int raw, int calibrated_mv);
