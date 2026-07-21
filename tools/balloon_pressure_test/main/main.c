/*
 * balloon_pressure_test — BMP280 pressure/temperature logger
 *
 * Reads BMP280 via I2C every N seconds, prints to USB serial:
 *   [HH:MM:SS] pressure_mbar temperature_C
 *
 * Hardware: ESP32-C3 (XIAO or Mini_V1)
 *   BMP280 SDA → GPIO8, SCL → GPIO9
 *   VCC → 3.3V, GND → GND
 *
 * Build: source ~/esp/esp-idf/export.sh && idf.py build
 * Flash: idf.py -p /dev/ttyACM0 flash monitor
 */

#include <stdio.h>
#include <stdint.h>
#include <math.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "driver/i2c_master.h"

static const char *TAG = "BMP280";

/* BMP280 registers */
#define BMP280_REG_ID       0xD0
#define BMP280_REG_RESET    0xE0
#define BMP280_REG_CTRL     0xF4
#define BMP280_REG_CONFIG   0xF5
#define BMP280_REG_PRESS    0xF7  /* 3 bytes: MSB, LSB, XLSB */
#define BMP280_REG_TEMP     0xFA  /* 3 bytes: MSB, LSB, XLSB */
#define BMP280_REG_CALIB    0x88  /* 24 bytes calibration data */

#define BMP280_CHIP_ID      0x58
#define BMP280_ADDR_PRIMARY 0x76
#define BMP280_ADDR_SECONDARY 0x77

/* I2C config */
#define I2C_SDA_PIN  8
#define I2C_SCL_PIN  9
#define I2C_FREQ_HZ  100000

/* Measurement interval (seconds) — configurable via menuconfig */
#ifndef CONFIG_MEASUREMENT_INTERVAL
#define MEASUREMENT_INTERVAL 30
#else
#define MEASUREMENT_INTERVAL CONFIG_MEASUREMENT_INTERVAL
#endif

/* Calibration coefficients */
typedef struct {
    uint16_t dig_T1;
    int16_t  dig_T2;
    int16_t  dig_T3;
    uint16_t dig_P1;
    int16_t  dig_P2;
    int16_t  dig_P3;
    int16_t  dig_P4;
    int16_t  dig_P5;
    int16_t  dig_P6;
    int16_t  dig_P7;
    int16_t  dig_P8;
    int16_t  dig_P9;
} bmp280_calib_t;

static bmp280_calib_t calib;
static i2c_master_dev_handle_t i2c_dev;
static uint8_t bmp280_addr;

/* Read single byte from register */
static esp_err_t bmp280_read_reg(uint8_t reg, uint8_t *data, uint8_t len)
{
    i2c_master_write_read_device(i2c_dev, bmp280_addr, &reg, 1, data, len, -1);
    return ESP_OK;
}

/* Write byte to register */
static esp_err_t bmp280_write_reg(uint8_t reg, uint8_t val)
{
    uint8_t buf[2] = {reg, val};
    i2c_master_write_to_device(i2c_dev, bmp280_addr, buf, 2, -1);
    return ESP_OK;
}

/* Read calibration coefficients */
static esp_err_t bmp280_read_calibration(void)
{
    uint8_t calib_data[24];
    esp_err_t ret = bmp280_read_reg(BMP280_REG_CALIB, calib_data, 24);
    if (ret != ESP_OK) return ret;

    calib.dig_T1 = (calib_data[1] << 8)  | calib_data[0];
    calib.dig_T2 = (calib_data[3] << 8)  | calib_data[2];
    calib.dig_T3 = (calib_data[5] << 8)  | calib_data[4];
    calib.dig_P1 = (calib_data[7] << 8)  | calib_data[6];
    calib.dig_P2 = (calib_data[9] << 8)  | calib_data[8];
    calib.dig_P3 = (calib_data[11] << 8) | calib_data[10];
    calib.dig_P4 = (calib_data[13] << 8) | calib_data[12];
    calib.dig_P5 = (calib_data[15] << 8) | calib_data[14];
    calib.dig_P6 = (calib_data[17] << 8) | calib_data[16];
    calib.dig_P7 = (calib_data[19] << 8) | calib_data[18];
    calib.dig_P8 = (calib_data[21] << 8) | calib_data[20];
    calib.dig_P9 = (calib_data[23] << 8) | calib_data[22];

    ESP_LOGI(TAG, "Calibration: T1=%u T2=%d T3=%d P1=%u P2=%d..P9=%d",
             calib.dig_T1, calib.dig_T2, calib.dig_T3,
             calib.dig_P1, calib.dig_P2, calib.dig_P9);
    return ESP_OK;
}

/* Compute compensated temperature (in 0.01°C units, BMP280 formula) */
static int32_t bmp280_compensate_temperature(int32_t adc_T, int32_t *t_fine)
{
    int32_t var1, var2, T;
    var1 = ((((adc_T >> 3) - ((int32_t)calib.dig_T1 << 1)))
            * ((int32_t)calib.dig_T2)) >> 11;
    var2 = (((((adc_T >> 4) - ((int32_t)calib.dig_T1))
              * ((adc_T >> 4) - ((int32_t)calib.dig_T1)))
             >> 12) * ((int32_t)calib.dig_T3)) >> 14;
    *t_fine = var1 + var2;
    T = (*t_fine * 5 + 128) >> 8;
    return T;  /* in 0.01°C */
}

/* Compute compensated pressure (in Pa) */
static uint32_t bmp280_compensate_pressure(int32_t adc_P, int32_t t_fine)
{
    int64_t var1, var2, p;
    var1 = ((int64_t)t_fine) - 128000;
    var2 = var1 * var1 * (int64_t)calib.dig_P6;
    var2 = var2 + ((var1 * (int64_t)calib.dig_P5) << 17);
    var2 = var2 + (((int64_t)calib.dig_P4) << 35);
    var1 = ((var1 * var1 * (int64_t)calib.dig_P3) >> 8)
           + ((var1 * (int64_t)calib.dig_P2) << 12);
    var1 = (((((int64_t)1) << 47) + var1)) * ((int64_t)calib.dig_P1) >> 33;

    if (var1 == 0) return 0;  /* avoid divide-by-zero */

    p = 1048576 - adc_P;
    p = (((p << 31) - var2) * 3125) / var1;
    var1 = (((int64_t)calib.dig_P9) * (p >> 13) * (p >> 13)) >> 25;
    var2 = (((int64_t)calib.dig_P8) * p) >> 19;
    p = ((p + var1 + var2) >> 8) + (((int64_t)calib.dig_P7) << 4);

    return (uint32_t)(p >> 8);  /* Pa */
}

/* Initialize I2C and BMP280 */
static esp_err_t bmp280_init(void)
{
    /* Configure I2C master bus */
    i2c_master_bus_config_t bus_cfg = {
        .i2c_port = I2C_NUM_0,
        .sda_io_num = I2C_SDA_PIN,
        .scl_io_num = I2C_SCL_PIN,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .intr_priority = 0,
        .trans_queue_depth = 0,
        .flags = { .enable_internal_pullup = true },
    };
    i2c_master_bus_handle_t bus_handle;
    esp_err_t ret = i2c_new_master_bus(&bus_cfg, &bus_handle);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "I2C bus init failed: %s", esp_err_to_name(ret));
        return ret;
    }

    /* Try primary address 0x76 first, then 0x77 */
    bmp280_addr = BMP280_ADDR_PRIMARY;
    i2c_device_config_t dev_cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = bmp280_addr,
        .scl_speed_hz = I2C_FREQ_HZ,
    };
    ret = i2c_master_bus_add_device(bus_handle, &dev_cfg, &i2c_dev);
    if (ret != ESP_OK) return ret;

    /* Check chip ID */
    uint8_t chip_id;
    ret = bmp280_read_reg(BMP280_REG_ID, &chip_id, 1);
    if (ret != ESP_OK || chip_id != BMP280_CHIP_ID) {
        ESP_LOGW(TAG, "No BMP280 at 0x76 (id=0x%02x), trying 0x77", chip_id);
        bmp280_addr = BMP280_ADDR_SECONDARY;
        dev_cfg.device_address = bmp280_addr;
        i2c_master_bus_rm_device(i2c_dev);
        ret = i2c_master_bus_add_device(bus_handle, &dev_cfg, &i2c_dev);
        if (ret != ESP_OK) return ret;
        ret = bmp280_read_reg(BMP280_REG_ID, &chip_id, 1);
        if (ret != ESP_OK || chip_id != BMP280_CHIP_ID) {
            ESP_LOGE(TAG, "BMP280 not found at either address (id=0x%02x)", chip_id);
            return ESP_ERR_NOT_FOUND;
        }
    }

    ESP_LOGI(TAG, "BMP280 found at 0x%02x, chip_id=0x%02x", bmp280_addr, chip_id);

    /* Read calibration */
    ret = bmp280_read_calibration();
    if (ret != ESP_OK) return ret;

    /* Configure: oversampling x1 temp, x1 pressure, normal mode */
    /* ctrl_meas: osrs_t=1 (x1), osrs_p=1 (x1), mode=3 (normal) → 0b001_001_11 = 0x27 */
    bmp280_write_reg(BMP280_REG_CTRL, 0x27);

    /* config: t_sb=1000ms (0b001), filter=off (0b000), spi3w=0 → 0x00 */
    /* t_sb=001 means 500ms standby, but in normal mode it doesn't matter much */
    bmp280_write_reg(BMP280_REG_CONFIG, 0x00);

    return ESP_OK;
}

/* Read pressure and temperature */
static esp_err_t bmp280_read(double *pressure_mbar, double *temp_c)
{
    uint8_t data[6];
    esp_err_t ret = bmp280_read_reg(BMP280_REG_PRESS, data, 6);
    if (ret != ESP_OK) return ret;

    int32_t adc_P = (int32_t)((data[0] << 12) | (data[1] << 4) | (data[2] >> 4));
    int32_t adc_T = (int32_t)((data[3] << 12) | (data[4] << 4) | (data[5] >> 4));

    int32_t t_fine;
    int32_t T = bmp280_compensate_temperature(adc_T, &t_fine);
    uint32_t P = bmp280_compensate_pressure(adc_P, t_fine);

    *temp_c = T / 100.0;
    *pressure_mbar = P / 100.0;  /* Pa → mbar (1 Pa = 0.01 mbar) */

    return ESP_OK;
}

/* Format uptime as [HH:MM:SS] */
static void format_uptime(int64_t uptime_us, char *buf, size_t buf_len)
{
    int total_sec = (int)(uptime_us / 1000000);
    int h = total_sec / 3600;
    int m = (total_sec % 3600) / 60;
    int s = total_sec % 60;
    snprintf(buf, buf_len, "[%02d:%02d:%02d]", h, m, s);
}

void app_main(void)
{
    ESP_LOGI(TAG, "Balloon Pressure Test Rig starting...");
    ESP_LOGI(TAG, "Measurement interval: %d seconds", MEASUREMENT_INTERVAL);

    esp_err_t ret = bmp280_init();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "BMP280 init failed: %s — check wiring", esp_err_to_name(ret));
        /* Print error line every interval so user knows it's not working */
        while (1) {
            char ts[16];
            format_uptime(esp_timer_get_time(), ts, sizeof(ts));
            printf("%s ERROR BMP280_NOT_FOUND\n", ts);
            fflush(stdout);
            vTaskDelay(pdMS_TO_TICKS(MEASUREMENT_INTERVAL * 1000));
        }
    }

    ESP_LOGI(TAG, "BMP280 initialized. Starting measurements...");

    while (1) {
        double pressure, temp;
        ret = bmp280_read(&pressure, &temp);

        char ts[16];
        format_uptime(esp_timer_get_time(), ts, sizeof(ts));

        if (ret == ESP_OK) {
            printf("%s %.1f %.1f\n", ts, pressure, temp);
        } else {
            printf("%s ERROR READ_FAILED\n", ts);
        }
        fflush(stdout);

        vTaskDelay(pdMS_TO_TICKS(MEASUREMENT_INTERVAL * 1000));
    }
}