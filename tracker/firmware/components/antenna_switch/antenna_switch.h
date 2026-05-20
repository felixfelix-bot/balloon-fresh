#pragma once

#include <stdint.h>
#include "esp_err.h"

esp_err_t antenna_switch_init(int ctrl1_pin, int ctrl2_pin);
esp_err_t antenna_switch_select(uint8_t antenna);
uint8_t antenna_switch_get_current(void);
