#include "bmp280.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <math.h>

static const char *TAG = "BMP280";

#define BMP280_ADDR 0x76
#define BMP280_REG_ID 0xD0
#define BMP280_REG_RESET 0xE0
#define BMP280_REG_CTRL_MEAS 0xF4
#define BMP280_REG_CONFIG 0xF5
#define BMP280_REG_PRESS 0xF7
#define BMP280_REG_DIG_T1 0x88
#define BMP280_REG_DIG_P1 0x8E

static esp_err_t i2c_write(bmp280_t *dev, uint8_t reg, uint8_t val)
{
    uint8_t buf[2] = {reg, val};
    return i2c_master_write_to_device(dev->port, dev->addr, buf, 2, pdMS_TO_TICKS(100));
}

static esp_err_t i2c_read(bmp280_t *dev, uint8_t reg, uint8_t *data, uint8_t len)
{
    return i2c_master_write_read_device(dev->port, dev->addr, &reg, 1, data, len, pdMS_TO_TICKS(100));
}

esp_err_t bmp280_init(bmp280_t *dev, i2c_port_t port, int sda, int scl, uint32_t clk_speed)
{
    dev->port = port;
    dev->addr = BMP280_ADDR;
    dev->sda_pin = sda;
    dev->scl_pin = scl;
    dev->clk_speed = clk_speed;

    i2c_config_t conf = {
        .mode = I2C_MODE_MASTER,
        .sda_io_num = sda,
        .scl_io_num = scl,
        .sda_pullup_en = GPIO_PULLUP_ENABLE,
        .scl_pullup_en = GPIO_PULLUP_ENABLE,
        .master.clk_speed = clk_speed,
    };
    ESP_ERROR_CHECK(i2c_param_config(port, &conf));
    ESP_ERROR_CHECK(i2c_driver_install(port, I2C_MODE_MASTER, 0, 0, 0));

    uint8_t id = 0;
    i2c_read(dev, BMP280_REG_ID, &id, 1);
    if (id != 0x58) {
        ESP_LOGE(TAG, "Wrong chip ID: 0x%02X (expected 0x58)", id);
        return ESP_ERR_NOT_FOUND;
    }

    i2c_write(dev, BMP280_REG_RESET, 0xB6);
    vTaskDelay(pdMS_TO_TICKS(100));

    uint8_t calib[24];
    i2c_read(dev, BMP280_REG_DIG_T1, calib, 24);
    dev->dig_T1 = (calib[1] << 8) | calib[0];
    dev->dig_T2 = (int16_t)((calib[3] << 8) | calib[2]);
    dev->dig_T3 = (int16_t)((calib[5] << 8) | calib[4]);
    dev->dig_P1 = (calib[7] << 8) | calib[6];
    dev->dig_P2 = (int16_t)((calib[9] << 8) | calib[8]);
    dev->dig_P3 = (int16_t)((calib[11] << 8) | calib[10]);
    dev->dig_P4 = (int16_t)((calib[13] << 8) | calib[12]);
    dev->dig_P5 = (int16_t)((calib[15] << 8) | calib[14]);
    dev->dig_P6 = (int16_t)((calib[17] << 8) | calib[16]);
    dev->dig_P7 = (int16_t)((calib[19] << 8) | calib[18]);
    dev->dig_P8 = (int16_t)((calib[21] << 8) | calib[20]);
    dev->dig_P9 = (int16_t)((calib[23] << 8) | calib[22]);

    i2c_write(dev, BMP280_REG_CONFIG, 0x90);
    i2c_write(dev, BMP280_REG_CTRL_MEAS, 0x27);

    ESP_LOGI(TAG, "BMP280 initialized, ID=0x%02X", id);
    return ESP_OK;
}

static int32_t compensate_temp(bmp280_t *dev, int32_t adc_T)
{
    int32_t var1 = ((((adc_T >> 3) - ((int32_t)dev->dig_T1 << 1))) * ((int32_t)dev->dig_T2)) >> 11;
    int32_t var2 = (((((adc_T >> 4) - ((int32_t)dev->dig_T1)) * ((adc_T >> 4) - ((int32_t)dev->dig_T1))) >> 12) * ((int32_t)dev->dig_T3)) >> 14;
    return var1 + var2;
}

static uint32_t compensate_press(bmp280_t *dev, int32_t adc_P, int32_t t_fine)
{
    int64_t var1 = ((int64_t)t_fine) - 128000;
    int64_t var2 = var1 * var1 * (int64_t)dev->dig_P6;
    var2 = var2 + ((var1 * (int64_t)dev->dig_P5) << 17);
    var2 = var2 + (((int64_t)dev->dig_P4) << 35);
    var1 = ((var1 * var1 * (int64_t)dev->dig_P3) >> 8) + ((var1 * (int64_t)dev->dig_P2) << 12);
    var1 = (((((int64_t)1) << 47) + var1)) * ((int64_t)dev->dig_P1) >> 33;
    if (var1 == 0) return 0;
    uint64_t p = 1048576 - adc_P;
    p = (((p << 31) - var2) * 3125) / var1;
    var1 = (((int64_t)dev->dig_P9) * (p >> 13) * (p >> 13)) >> 25;
    var2 = (((int64_t)dev->dig_P8) * p) >> 19;
    p = ((p + var1 + var2) >> 8) + (((int64_t)dev->dig_P7) << 4);
    return (uint32_t)p;
}

esp_err_t bmp280_read(bmp280_t *dev, float *temperature, float *pressure, float *altitude)
{
    uint8_t data[6];
    esp_err_t ret = i2c_read(dev, BMP280_REG_PRESS, data, 6);
    if (ret != ESP_OK) return ret;

    int32_t adc_P = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4);
    int32_t adc_T = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4);

    int32_t t_fine = compensate_temp(dev, adc_T);
    *temperature = (float)(t_fine / 5120.0);

    uint32_t comp_P = compensate_press(dev, adc_P, t_fine);
    *pressure = (float)comp_P / 25600.0;

    *altitude = 44330.0 * (1.0 - powf(*pressure / 1013.25, 0.1903));

    return ESP_OK;
}

esp_err_t bmp280_sleep(bmp280_t *dev)
{
    return i2c_write(dev, BMP280_REG_CTRL_MEAS, 0x00);
}

esp_err_t bmp280_wakeup(bmp280_t *dev)
{
    return i2c_write(dev, BMP280_REG_CTRL_MEAS, 0x27);
}
