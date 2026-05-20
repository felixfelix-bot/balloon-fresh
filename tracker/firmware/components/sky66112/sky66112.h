#pragma once

#include <stdint.h>
#include <stdbool.h>
#include "esp_err.h"

typedef enum {
    SKY66112_MODE_RX = 0,
    SKY66112_MODE_TX = 1,
    SKY66112_MODE_BYPASS = 2,
    SKY66112_MODE_SHUTDOWN = 3,
} sky66112_mode_t;

esp_err_t sky66112_init(int tx_en_pin, int rx_en_pin);
esp_err_t sky66112_set_mode(sky66112_mode_t mode);
esp_err_t sky66112_tx_enable(void);
esp_err_t sky66112_tx_disable(void);
esp_err_t sky66112_rx_enable(void);
esp_err_t sky66112_shutdown(void);
