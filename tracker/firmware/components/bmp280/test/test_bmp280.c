#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <math.h>

#include "../bmp280.c"

static void test_compensate_temp_25c(void) {
    bmp280_t dev;
    memset(&dev, 0, sizeof(dev));
    dev.dig_T1 = 27504;
    dev.dig_T2 = 26435;
    dev.dig_T3 = -1000;

    int32_t adc_T = 519888;
    int32_t t_fine = compensate_temp(&dev, adc_T);
    double temp_c = t_fine / 5120.0;

    assert(temp_c > 20.0 && temp_c < 30.0);
    printf("PASS (t_fine=%d, temp=%.2f C)\n", t_fine, temp_c);
}

static void test_compensate_temp_negative(void) {
    bmp280_t dev;
    memset(&dev, 0, sizeof(dev));
    dev.dig_T1 = 27504;
    dev.dig_T2 = 26435;
    dev.dig_T3 = -1000;

    int32_t adc_T = 400000;
    int32_t t_fine = compensate_temp(&dev, adc_T);
    double temp_c = t_fine / 5120.0;

    assert(temp_c < 0.0);
    printf("PASS (t_fine=%d, temp=%.2f C)\n", t_fine, temp_c);
}

static void test_compensate_press_sea_level(void) {
    bmp280_t dev;
    memset(&dev, 0, sizeof(dev));
    dev.dig_T1 = 27504;
    dev.dig_T2 = 26435;
    dev.dig_T3 = -1000;
    dev.dig_P1 = 36477;
    dev.dig_P2 = -10685;
    dev.dig_P3 = 3024;
    dev.dig_P4 = 6324;
    dev.dig_P5 = -202;
    dev.dig_P6 = -1073;
    dev.dig_P7 = 3270;
    dev.dig_P8 = -3683;
    dev.dig_P9 = 2247;

    int32_t adc_T = 519888;
    int32_t t_fine = compensate_temp(&dev, adc_T);

    int32_t adc_P = 415148;
    uint32_t comp_P = compensate_press(&dev, adc_P, t_fine);
    double pressure_hpa = comp_P / 25600.0;

    assert(pressure_hpa > 900.0 && pressure_hpa < 1100.0);
    printf("PASS (comp_P=%u, pressure=%.2f hPa)\n", comp_P, pressure_hpa);
}

static void test_compensate_press_zero_adc(void) {
    bmp280_t dev;
    memset(&dev, 0, sizeof(dev));
    dev.dig_T1 = 27504;
    dev.dig_T2 = 26435;
    dev.dig_T3 = -1000;
    dev.dig_P1 = 36477;
    dev.dig_P2 = -10685;
    dev.dig_P3 = 3024;
    dev.dig_P4 = 6324;
    dev.dig_P5 = -202;
    dev.dig_P6 = -1073;
    dev.dig_P7 = 3270;
    dev.dig_P8 = -3683;
    dev.dig_P9 = 2247;

    int32_t t_fine = 128000;
    uint32_t comp_P = compensate_press(&dev, 0, t_fine);

    assert(comp_P > 0);
    printf("PASS (comp_P=%u)\n", comp_P);
}

static void test_compensate_temp_deterministic(void) {
    bmp280_t dev;
    memset(&dev, 0, sizeof(dev));
    dev.dig_T1 = 27504;
    dev.dig_T2 = 26435;
    dev.dig_T3 = -1000;

    int32_t adc_T = 519888;
    int32_t t1 = compensate_temp(&dev, adc_T);
    int32_t t2 = compensate_temp(&dev, adc_T);
    assert(t1 == t2);
    printf("PASS\n");
}

static void test_compensate_press_deterministic(void) {
    bmp280_t dev;
    memset(&dev, 0, sizeof(dev));
    dev.dig_T1 = 27504;
    dev.dig_T2 = 26435;
    dev.dig_T3 = -1000;
    dev.dig_P1 = 36477;
    dev.dig_P2 = -10685;

    int32_t t_fine = 128000;
    uint32_t p1 = compensate_press(&dev, 415148, t_fine);
    uint32_t p2 = compensate_press(&dev, 415148, t_fine);
    assert(p1 == p2);
    printf("PASS\n");
}

int main(void) {
    printf("\n=== BMP280 Compensation Tests ===\n\n");

    printf("TEST 1: compensate_temp ~25C... ");
    test_compensate_temp_25c();

    printf("TEST 2: compensate_temp negative... ");
    test_compensate_temp_negative();

    printf("TEST 3: compensate_press sea level... ");
    test_compensate_press_sea_level();

    printf("TEST 4: compensate_press zero ADC... ");
    test_compensate_press_zero_adc();

    printf("TEST 5: compensate_temp deterministic... ");
    test_compensate_temp_deterministic();

    printf("TEST 6: compensate_press deterministic... ");
    test_compensate_press_deterministic();

    printf("\n=== Results: 6/6 passed ===\n");
    return 0;
}
