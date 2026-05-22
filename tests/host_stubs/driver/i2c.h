#pragma once

#include <stdint.h>
#include <stddef.h>

typedef int i2c_port_t;
#define I2C_NUM_0 0
#define I2C_MODE_MASTER 0
#define GPIO_PULLUP_ENABLE 1
#define GPIO_PULLUP_DISABLE 0

typedef int esp_err_t;
#define ESP_OK 0
#define ESP_ERR_NOT_FOUND (-2)
#define ESP_ERROR_CHECK(x) do { esp_err_t _rc = (x); (void)_rc; } while(0)

typedef struct {
    int mode;
    int sda_io_num;
    int scl_io_num;
    int sda_pullup_en;
    int scl_pullup_en;
    struct { uint32_t clk_speed; } master;
} i2c_config_t;

static inline esp_err_t i2c_param_config(i2c_port_t p, const i2c_config_t *c) { (void)p;(void)c; return 0; }
static inline esp_err_t i2c_driver_install(i2c_port_t p, int m, int sl, int rl, int q) { (void)p;(void)m;(void)sl;(void)rl;(void)q; return 0; }
static inline esp_err_t i2c_master_write_to_device(i2c_port_t p, uint8_t a, const uint8_t *w, size_t wl, int t) { (void)p;(void)a;(void)w;(void)wl;(void)t; return 0; }
static inline esp_err_t i2c_master_write_read_device(i2c_port_t p, uint8_t a, const uint8_t *w, size_t wl, uint8_t *r, size_t rl, int t) { (void)p;(void)a;(void)w;(void)wl;(void)r;(void)rl;(void)t; return 0; }
