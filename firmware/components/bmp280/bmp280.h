#pragma once

#include <stdint.h>
#include "esp_err.h"
#include "driver/i2c.h"

typedef struct {
    i2c_port_t port;
    uint8_t addr;
    int sda_pin;
    int scl_pin;
    uint32_t clk_speed;
    uint16_t dig_T1;
    int16_t dig_T2, dig_T3;
    uint16_t dig_P1;
    int16_t dig_P2, dig_P3, dig_P4, dig_P5, dig_P6, dig_P7, dig_P8, dig_P9;
} bmp280_t;

esp_err_t bmp280_init(bmp280_t *dev, i2c_port_t port, int sda, int scl, uint32_t clk_speed);
esp_err_t bmp280_read(bmp280_t *dev, float *temperature, float *pressure, float *altitude);
esp_err_t bmp280_sleep(bmp280_t *dev);
esp_err_t bmp280_wakeup(bmp280_t *dev);
