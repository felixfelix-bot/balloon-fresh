#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <assert.h>

#include "../antenna_switch.c"

static void test_init_sets_pins(void) {
    antenna_switch_init(21, 20);
    assert(s_ctrl1 == 21);
    assert(s_ctrl2 == 20);
    assert(s_current == 0);
    printf("PASS\n");
}

static void test_select_antenna_0(void) {
    antenna_switch_init(21, 20);
    antenna_switch_select(0);
    assert(s_current == 0);
    assert(last_gpio_levels[21] == 0);
    assert(last_gpio_levels[20] == 0);
    printf("PASS\n");
}

static void test_select_antenna_1(void) {
    antenna_switch_init(21, 20);
    antenna_switch_select(1);
    assert(s_current == 1);
    assert(last_gpio_levels[21] == 1);
    assert(last_gpio_levels[20] == 0);
    printf("PASS\n");
}

static void test_select_antenna_2(void) {
    antenna_switch_init(21, 20);
    antenna_switch_select(2);
    assert(s_current == 2);
    assert(last_gpio_levels[21] == 0);
    assert(last_gpio_levels[20] == 1);
    printf("PASS\n");
}

static void test_select_antenna_3(void) {
    antenna_switch_init(21, 20);
    antenna_switch_select(3);
    assert(s_current == 3);
    assert(last_gpio_levels[21] == 1);
    assert(last_gpio_levels[20] == 1);
    printf("PASS\n");
}

static void test_select_invalid_clamps(void) {
    antenna_switch_init(21, 20);
    antenna_switch_select(255);
    assert(s_current == 3);
    assert(last_gpio_levels[21] == 1);
    assert(last_gpio_levels[20] == 1);
    printf("PASS\n");
}

static void test_get_current(void) {
    antenna_switch_init(21, 20);
    antenna_switch_select(2);
    assert(antenna_switch_get_current() == 2);
    antenna_switch_select(0);
    assert(antenna_switch_get_current() == 0);
    printf("PASS\n");
}

int main(void) {
    printf("\n=== Antenna Switch Tests ===\n\n");

    printf("TEST 1: init sets pins... ");
    test_init_sets_pins();
    printf("TEST 2: select antenna 0 (00)... ");
    test_select_antenna_0();
    printf("TEST 3: select antenna 1 (10)... ");
    test_select_antenna_1();
    printf("TEST 4: select antenna 2 (01)... ");
    test_select_antenna_2();
    printf("TEST 5: select antenna 3 (11)... ");
    test_select_antenna_3();
    printf("TEST 6: invalid antenna clamps to 3... ");
    test_select_invalid_clamps();
    printf("TEST 7: get_current tracks selection... ");
    test_get_current();

    printf("\n=== Results: 7/7 passed ===\n");
    return 0;
}
