#include <stdio.h>
#include <assert.h>
#include <string.h>

#include "../power_manager.c"

static void test_midrange_raw(void) {
    int mv = power_manager_raw_to_mv(2048, 0);
    assert(mv > 0);
    assert(mv == (2048 * 3300 / 4095) * 2);
    printf("PASS (mv=%d)\n", mv);
}

static void test_max_raw(void) {
    int mv = power_manager_raw_to_mv(4095, 0);
    int expected = (4095 * 3300 / 4095) * 2;
    assert(mv == expected);
    assert(mv == 6600);
    printf("PASS (mv=%d)\n", mv);
}

static void test_zero_raw(void) {
    int mv = power_manager_raw_to_mv(0, 0);
    assert(mv == 0);
    printf("PASS\n");
}

static void test_calibrated_value(void) {
    int mv = power_manager_raw_to_mv(2048, 1650);
    assert(mv == 3300);
    printf("PASS (mv=%d)\n", mv);
}

static void test_calibrated_overrides_raw(void) {
    int mv_raw_only = power_manager_raw_to_mv(1000, 0);
    int mv_calibrated = power_manager_raw_to_mv(1000, 1500);
    assert(mv_calibrated == 3000);
    assert(mv_calibrated != mv_raw_only);
    printf("PASS\n");
}

int main(void) {
    printf("\n=== Power Manager Tests ===\n\n");

    printf("TEST 1: midrange raw ADC... ");
    test_midrange_raw();
    printf("TEST 2: max raw ADC (4095)... ");
    test_max_raw();
    printf("TEST 3: zero raw ADC... ");
    test_zero_raw();
    printf("TEST 4: calibrated value... ");
    test_calibrated_value();
    printf("TEST 5: calibrated overrides raw... ");
    test_calibrated_overrides_raw();

    printf("\n=== Results: 5/5 passed ===\n");
    return 0;
}
