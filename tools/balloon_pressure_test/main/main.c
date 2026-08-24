/*
 * balloon_pressure_test — BMP280/MS5611 auto-detect pressure/temperature logger
 *
 * Auto-detects BMP280 or MS5611 via I2C at startup, then reads pressure and
 * temperature every N seconds, printing to USB serial:
 *   [HH:MM:SS] pressure_mbar temperature_C
 *
 * Detection order:
 *   1. BMP280: chip ID register 0xD0 == 0x58 at address 0x76 or 0x77
 *   2. MS5611: PROM coefficient C1 non-zero at address 0x76
 *
 * Hardware: ESP32-C3 (XIAO or Mini_V1)
 *   SDA → GPIO8, SCL → GPIO9
 *   VCC → 3.3V, GND → GND
 *
 * Build: source ~/esp/esp-idf/export.sh && idf.py build
 * Flash: idf.py -p /dev/ttyACM0 flash monitor
 */

#include <stdio.h>
#include <stdint.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "driver/i2c_master.h"

static const char *TAG = "PRES_TEST";

/* ---- Sensor types ---- */
typedef enum {
    SENSOR_NONE = 0,
    SENSOR_BMP280,
    SENSOR_MS5611,
} sensor_type_t;

static sensor_type_t g_sensor = SENSOR_NONE;
static uint8_t       g_dev_addr;

/* ---- I2C config ---- */
#define I2C_SDA_PIN  8
#define I2C_SCL_PIN  9
#define I2C_FREQ_HZ  100000

static i2c_master_bus_handle_t g_bus_handle;
static i2c_master_dev_handle_t g_i2c_dev;

/* ---- Measurement interval (seconds, configurable via menuconfig) ---- */
#ifndef CONFIG_MEASUREMENT_INTERVAL
#define MEASUREMENT_INTERVAL 30
#else
#define MEASUREMENT_INTERVAL CONFIG_MEASUREMENT_INTERVAL
#endif

/* ===== BMP280 definitions ===== */

#define BMP280_REG_ID       0xD0
#define BMP280_REG_RESET    0xE0
#define BMP280_REG_CTRL     0xF4
#define BMP280_REG_CONFIG   0xF5
#define BMP280_REG_PRESS    0xF7  /* 3 bytes: MSB, LSB, XLSB */
#define BMP280_REG_TEMP     0xFA  /* 3 bytes: MSB, LSB, XLSB */
#define BMP280_REG_CALIB    0x88  /* 24 bytes calibration data */
#define BMP280_CHIP_ID      0x58

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

static bmp280_calib_t s_bmp280_calib;

/* ===== MS5611 definitions ===== */

#define MS5611_CMD_RESET    0x1E
#define MS5611_CMD_CONV_D1  0x40  /* D1 pressure conversion, OSR256 */
#define MS5611_CMD_CONV_D2  0x50  /* D2 temperature conversion, OSR256 */
#define MS5611_CMD_ADC_READ 0x00
#define MS5611_CMD_PROM_BASE 0xA0 /* PROM read base: command = PROM_BASE + 2*i */

static uint16_t s_ms5611_coeff[6];  /* C1–C6, big-endian from PROM */

/* ===== I2C helper functions ===== */

/* Read len bytes starting at register addr */
static esp_err_t i2c_read_reg(uint8_t reg, uint8_t *data, uint8_t len)
{
    return i2c_master_write_read_device(g_i2c_dev, g_dev_addr,
                                        &reg, 1, data, len, -1);
}

/* Write a single command byte (for MS5611 commands: reset, conversion) */
static esp_err_t i2c_write_byte(uint8_t val)
{
    return i2c_master_write_to_device(g_i2c_dev, g_dev_addr, &val, 1, -1);
}

/* Write a byte to a register (for BMP280 configuration) */
static esp_err_t i2c_write_reg(uint8_t reg, uint8_t val)
{
    uint8_t buf[2] = {reg, val};
    return i2c_master_write_to_device(g_i2c_dev, g_dev_addr, buf, 2, -1);
}

/* ===== BMP280 functions (compensation math unchanged from original) ===== */

static esp_err_t bmp280_read_calibration(void)
{
    uint8_t calib_data[24];
    esp_err_t ret = i2c_read_reg(BMP280_REG_CALIB, calib_data, 24);
    if (ret != ESP_OK) return ret;

    s_bmp280_calib.dig_T1 = (calib_data[1] << 8)  | calib_data[0];
    s_bmp280_calib.dig_T2 = (calib_data[3] << 8)  | calib_data[2];
    s_bmp280_calib.dig_T3 = (calib_data[5] << 8)  | calib_data[4];
    s_bmp280_calib.dig_P1 = (calib_data[7] << 8)  | calib_data[6];
    s_bmp280_calib.dig_P2 = (calib_data[9] << 8)  | calib_data[8];
    s_bmp280_calib.dig_P3 = (calib_data[11] << 8) | calib_data[10];
    s_bmp280_calib.dig_P4 = (calib_data[13] << 8) | calib_data[12];
    s_bmp280_calib.dig_P5 = (calib_data[15] << 8) | calib_data[14];
    s_bmp280_calib.dig_P6 = (calib_data[17] << 8) | calib_data[16];
    s_bmp280_calib.dig_P7 = (calib_data[19] << 8) | calib_data[18];
    s_bmp280_calib.dig_P8 = (calib_data[21] << 8) | calib_data[20];
    s_bmp280_calib.dig_P9 = (calib_data[23] << 8) | calib_data[22];

    ESP_LOGI(TAG, "BMP280 calibration: T1=%u T2=%d T3=%d P1=%u P2=%d..P9=%d",
             s_bmp280_calib.dig_T1, s_bmp280_calib.dig_T2, s_bmp280_calib.dig_T3,
             s_bmp280_calib.dig_P1, s_bmp280_calib.dig_P2, s_bmp280_calib.dig_P9);
    return ESP_OK;
}

/* Compute compensated temperature (in 0.01°C units, BMP280 formula) */
static int32_t bmp280_compensate_temperature(int32_t adc_T, int32_t *t_fine)
{
    int32_t var1, var2, T;
    var1 = ((((adc_T >> 3) - ((int32_t)s_bmp280_calib.dig_T1 << 1)))
            * ((int32_t)s_bmp280_calib.dig_T2)) >> 11;
    var2 = (((((adc_T >> 4) - ((int32_t)s_bmp280_calib.dig_T1))
              * ((adc_T >> 4) - ((int32_t)s_bmp280_calib.dig_T1)))
             >> 12) * ((int32_t)s_bmp280_calib.dig_T3)) >> 14;
    *t_fine = var1 + var2;
    T = (*t_fine * 5 + 128) >> 8;
    return T;  /* in 0.01°C */
}

/* Compute compensated pressure (in Pa) */
static uint32_t bmp280_compensate_pressure(int32_t adc_P, int32_t t_fine)
{
    int64_t var1, var2, p;
    var1 = ((int64_t)t_fine) - 128000;
    var2 = var1 * var1 * (int64_t)s_bmp280_calib.dig_P6;
    var2 = var2 + ((var1 * (int64_t)s_bmp280_calib.dig_P5) << 17);
    var2 = var2 + (((int64_t)s_bmp280_calib.dig_P4) << 35);
    var1 = ((var1 * var1 * (int64_t)s_bmp280_calib.dig_P3) >> 8)
           + ((var1 * (int64_t)s_bmp280_calib.dig_P2) << 12);
    var1 = (((((int64_t)1) << 47) + var1)) * ((int64_t)s_bmp280_calib.dig_P1) >> 33;

    if (var1 == 0) return 0;  /* avoid divide-by-zero */

    p = 1048576 - adc_P;
    p = (((p << 31) - var2) * 3125) / var1;
    var1 = (((int64_t)s_bmp280_calib.dig_P9) * (p >> 13) * (p >> 13)) >> 25;
    var2 = (((int64_t)s_bmp280_calib.dig_P8) * p) >> 19;
    p = ((p + var1 + var2) >> 8) + (((int64_t)s_bmp280_calib.dig_P7) << 4);

    return (uint32_t)(p >> 8);  /* Pa */
}

/* Configure BMP280 after detection */
static esp_err_t bmp280_configure(void)
{
    esp_err_t ret = bmp280_read_calibration();
    if (ret != ESP_OK) return ret;

    /* ctrl_meas: osrs_t=1 (x1), osrs_p=1 (x1), mode=3 (normal) → 0x27 */
    i2c_write_reg(BMP280_REG_CTRL, 0x27);
    /* config: t_sb=500ms, filter=off → 0x00 */
    i2c_write_reg(BMP280_REG_CONFIG, 0x00);
    return ESP_OK;
}

/* Read compensated pressure (mbar) and temperature (°C) from BMP280 */
static esp_err_t bmp280_read(double *pressure_mbar, double *temp_c)
{
    uint8_t data[6];
    esp_err_t ret = i2c_read_reg(BMP280_REG_PRESS, data, 6);
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

/* ===== MS5611 functions (per TE Connectivity MS5611-01BA03 datasheet) ===== */

/* Reset: write 0x1E, wait 3ms */
static esp_err_t ms5611_reset(void)
{
    esp_err_t ret = i2c_write_byte(MS5611_CMD_RESET);
    if (ret != ESP_OK) return ret;
    vTaskDelay(pdMS_TO_TICKS(3));
    return ESP_OK;
}

/* Read 6 PROM coefficients C1–C6 from addresses 0xA2,0xA4,...,0xAC */
static esp_err_t ms5611_read_prom(void)
{
    for (int i = 0; i < 6; i++) {
        uint8_t cmd = MS5611_CMD_PROM_BASE + 2 * (i + 1); /* 0xA2, 0xA4, ..., 0xAC */
        uint8_t buf[2] = {0};
        esp_err_t ret = i2c_read_reg(cmd, buf, 2);
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "MS5611 PROM read C%d (cmd=0x%02x) failed: %s",
                     i + 1, cmd, esp_err_to_name(ret));
            return ret;
        }
        s_ms5611_coeff[i] = ((uint16_t)buf[0] << 8) | buf[1]; /* big-endian */
    }

    ESP_LOGI(TAG, "MS5611 coefficients: C1=%u C2=%u C3=%u C4=%u C5=%u C6=%u",
             s_ms5611_coeff[0], s_ms5611_coeff[1], s_ms5611_coeff[2],
             s_ms5611_coeff[3], s_ms5611_coeff[4], s_ms5611_coeff[5]);
    return ESP_OK;
}

/* Read 24-bit ADC result from register 0x00 */
static esp_err_t ms5611_read_adc(uint32_t *value)
{
    uint8_t buf[3] = {0};
    esp_err_t ret = i2c_read_reg(MS5611_CMD_ADC_READ, buf, 3);
    if (ret != ESP_OK) return ret;
    *value = ((uint32_t)buf[0] << 16) | ((uint32_t)buf[1] << 8) | buf[2];
    return ESP_OK;
}

/*
 * Read compensated pressure (mbar) and temperature (°C) from MS5611.
 *
 * Per MS5611-01BA03 datasheet first-order integer compensation:
 *   dT  = D2 - C5 * 2^8
 *   T   = 2000 + dT * C6 / 2^23          (0.01°C)
 *   OFF  = C2 * 2^16 + C4 * dT / 2^7
 *   SENS = C1 * 2^15 + C3 * dT / 2^8
 *   P   = (D1 * SENS / 2^21 - OFF) / 2^15 (0.01 mbar)
 *
 * All intermediate math uses int64_t to prevent overflow.
 */
static esp_err_t ms5611_read(double *pressure_mbar, double *temp_c)
{
    /* D1 — pressure conversion */
    esp_err_t ret = i2c_write_byte(MS5611_CMD_CONV_D1);
    if (ret != ESP_OK) return ret;
    vTaskDelay(pdMS_TO_TICKS(1));
    uint32_t D1 = 0;
    ret = ms5611_read_adc(&D1);
    if (ret != ESP_OK) return ret;

    /* D2 — temperature conversion */
    ret = i2c_write_byte(MS5611_CMD_CONV_D2);
    if (ret != ESP_OK) return ret;
    vTaskDelay(pdMS_TO_TICKS(1));
    uint32_t D2 = 0;
    ret = ms5611_read_adc(&D2);
    if (ret != ESP_OK) return ret;

    /* Load coefficients */
    uint16_t C1 = s_ms5611_coeff[0];  /* pressure sensitivity       */
    uint16_t C2 = s_ms5611_coeff[1];  /* pressure offset            */
    uint16_t C3 = s_ms5611_coeff[2];  /* TC of pressure sensitivity */
    uint16_t C4 = s_ms5611_coeff[3];  /* TC of pressure offset      */
    uint16_t C5 = s_ms5611_coeff[4];  /* reference temperature      */
    uint16_t C6 = s_ms5611_coeff[5];  /* TC of temperature          */

    /* First-order compensation (int64_t throughout) */
    int64_t dT   = (int64_t)D2 - ((int64_t)C5 << 8);
    int64_t T    = 2000 + ((dT * (int64_t)C6) >> 23);               /* 0.01 °C  */
    int64_t OFF  = ((int64_t)C2 << 16) + (((int64_t)C4 * dT) >> 7);
    int64_t SENS = ((int64_t)C1 << 15) + (((int64_t)C3 * dT) >> 8);
    int64_t P    = ((((int64_t)D1 * SENS) >> 21) - OFF) >> 15;       /* 0.01 mbar */

    *temp_c        = (double)T / 100.0;
    *pressure_mbar = (double)P / 100.0;
    return ESP_OK;
}

/* ===== Sensor detection and initialization ===== */

static esp_err_t add_device(uint8_t addr)
{
    i2c_device_config_t dev_cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address  = addr,
        .scl_speed_hz    = I2C_FREQ_HZ,
    };
    return i2c_master_bus_add_device(g_bus_handle, &dev_cfg, &g_i2c_dev);
}

/*
 * Probe I2C addresses 0x76 then 0x77.
 * At each address try BMP280 (chip ID) first, then MS5611 (PROM C1 non-zero).
 */
static esp_err_t sensor_init(void)
{
    /* Configure I2C master bus */
    i2c_master_bus_config_t bus_cfg = {
        .i2c_port           = I2C_NUM_0,
        .sda_io_num         = I2C_SDA_PIN,
        .scl_io_num         = I2C_SCL_PIN,
        .clk_source         = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt  = 7,
        .intr_priority      = 0,
        .trans_queue_depth  = 0,
        .flags              = { .enable_internal_pullup = true },
    };
    esp_err_t ret = i2c_new_master_bus(&bus_cfg, &g_bus_handle);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "I2C bus init failed: %s", esp_err_to_name(ret));
        return ret;
    }

    const uint8_t addrs[] = {0x76, 0x77};

    for (int i = 0; i < 2; i++) {
        uint8_t addr = addrs[i];

        ret = add_device(addr);
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "Cannot add I2C device at 0x%02x: %s",
                     addr, esp_err_to_name(ret));
            continue;
        }
        g_dev_addr = addr;

        /* --- Try BMP280: check chip ID register 0xD0 == 0x58 --- */
        uint8_t chip_id = 0;
        ret = i2c_read_reg(BMP280_REG_ID, &chip_id, 1);
        if (ret == ESP_OK && chip_id == BMP280_CHIP_ID) {
            ESP_LOGI(TAG, "BMP280 found at 0x%02x (chip_id=0x%02x)",
                     addr, chip_id);
            g_sensor = SENSOR_BMP280;
            printf("SENSOR: BMP280\n");
            fflush(stdout);
            return bmp280_configure();
        }

        /* --- Try MS5611: reset then read PROM --- */
        ret = ms5611_reset();
        if (ret == ESP_OK) {
            ret = ms5611_read_prom();
            if (ret == ESP_OK && s_ms5611_coeff[0] != 0) {
                ESP_LOGI(TAG, "MS5611 found at 0x%02x (C1=%u)",
                         addr, s_ms5611_coeff[0]);
                g_sensor = SENSOR_MS5611;
                printf("SENSOR: MS5611\n");
                fflush(stdout);
                return ESP_OK;  /* already reset + PROM loaded during probe */
            }
        }

        /* No recognized sensor at this address — try next */
        ESP_LOGD(TAG, "No sensor at 0x%02x (BMP280 id=0x%02x)", addr, chip_id);
        i2c_master_bus_rm_device(g_i2c_dev);
        g_i2c_dev = NULL;
    }

    ESP_LOGE(TAG, "No supported sensor found (tried BMP280 + MS5611 at 0x76/0x77)");
    return ESP_ERR_NOT_FOUND;
}

/* ===== Output formatting ===== */

static void format_uptime(int64_t uptime_us, char *buf, size_t buf_len)
{
    int total_sec = (int)(uptime_us / 1000000);
    int h = total_sec / 3600;
    int m = (total_sec % 3600) / 60;
    int s = total_sec % 60;
    snprintf(buf, buf_len, "[%02d:%02d:%02d]", h, m, s);
}

/* ===== Main ===== */

void app_main(void)
{
    ESP_LOGI(TAG, "Balloon Pressure Test Rig starting...");
    ESP_LOGI(TAG, "Measurement interval: %d seconds", MEASUREMENT_INTERVAL);

    esp_err_t ret = sensor_init();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Sensor init failed: %s — check wiring", esp_err_to_name(ret));
        while (1) {
            char ts[16];
            format_uptime(esp_timer_get_time(), ts, sizeof(ts));
            printf("%s ERROR SENSOR_NOT_FOUND\n", ts);
            fflush(stdout);
            vTaskDelay(pdMS_TO_TICKS(MEASUREMENT_INTERVAL * 1000));
        }
    }

    ESP_LOGI(TAG, "Starting measurements (interval %ds)...", MEASUREMENT_INTERVAL);

    while (1) {
        double pressure = 0.0, temp = 0.0;

        switch (g_sensor) {
        case SENSOR_BMP280:
            ret = bmp280_read(&pressure, &temp);
            break;
        case SENSOR_MS5611:
            ret = ms5611_read(&pressure, &temp);
            break;
        default:
            ret = ESP_ERR_NOT_SUPPORTED;
            break;
        }

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
