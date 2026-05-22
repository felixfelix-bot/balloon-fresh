#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <assert.h>

#include "../sky66112.c"

static void test_init_sets_pins(void) {
    gpio_stubs_reset();
    sky66112_init(1, 2);
    assert(s_tx_en == 1);
    assert(s_rx_en == 2);
    assert(last_gpio_levels[1] == 0);
    assert(last_gpio_levels[2] == 0);
    printf("PASS\n");
}

static void test_set_mode_tx(void) {
    gpio_stubs_reset();
    sky66112_init(1, 2);
    sky66112_set_mode(SKY66112_MODE_TX);
    assert(last_gpio_levels[1] == 1);
    assert(last_gpio_levels[2] == 0);
    printf("PASS\n");
}

static void test_set_mode_rx(void) {
    gpio_stubs_reset();
    sky66112_init(1, 2);
    sky66112_set_mode(SKY66112_MODE_RX);
    assert(last_gpio_levels[1] == 0);
    assert(last_gpio_levels[2] == 1);
    printf("PASS\n");
}

static void test_set_mode_bypass(void) {
    gpio_stubs_reset();
    sky66112_init(1, 2);
    sky66112_set_mode(SKY66112_MODE_BYPASS);
    assert(last_gpio_levels[1] == 1);
    assert(last_gpio_levels[2] == 1);
    printf("PASS\n");
}

static void test_set_mode_shutdown(void) {
    gpio_stubs_reset();
    sky66112_init(1, 2);
    sky66112_set_mode(SKY66112_MODE_SHUTDOWN);
    assert(last_gpio_levels[1] == 0);
    assert(last_gpio_levels[2] == 0);
    printf("PASS\n");
}

static void test_tx_enable_wrapper(void) {
    gpio_stubs_reset();
    sky66112_init(1, 2);
    sky66112_tx_enable();
    assert(last_gpio_levels[1] == 1);
    assert(last_gpio_levels[2] == 0);
    printf("PASS\n");
}

static void test_rx_enable_wrapper(void) {
    gpio_stubs_reset();
    sky66112_init(1, 2);
    sky66112_rx_enable();
    assert(last_gpio_levels[1] == 0);
    assert(last_gpio_levels[2] == 1);
    printf("PASS\n");
}

static void test_tx_disable_goes_shutdown(void) {
    gpio_stubs_reset();
    sky66112_init(1, 2);
    sky66112_tx_enable();
    sky66112_tx_disable();
    assert(last_gpio_levels[1] == 0);
    assert(last_gpio_levels[2] == 0);
    printf("PASS\n");
}

static void test_shutdown_wrapper(void) {
    gpio_stubs_reset();
    sky66112_init(1, 2);
    sky66112_tx_enable();
    sky66112_shutdown();
    assert(last_gpio_levels[1] == 0);
    assert(last_gpio_levels[2] == 0);
    printf("PASS\n");
}

int main(void) {
    printf("\n=== SKY66112 FEM Tests ===\n\n");

    printf("TEST 1: init sets pins and shuts down... ");
    test_init_sets_pins();
    printf("TEST 2: set_mode TX... ");
    test_set_mode_tx();
    printf("TEST 3: set_mode RX... ");
    test_set_mode_rx();
    printf("TEST 4: set_mode BYPASS... ");
    test_set_mode_bypass();
    printf("TEST 5: set_mode SHUTDOWN... ");
    test_set_mode_shutdown();
    printf("TEST 6: tx_enable wrapper... ");
    test_tx_enable_wrapper();
    printf("TEST 7: rx_enable wrapper... ");
    test_rx_enable_wrapper();
    printf("TEST 8: tx_disable goes shutdown... ");
    test_tx_disable_goes_shutdown();
    printf("TEST 9: shutdown wrapper... ");
    test_shutdown_wrapper();

    printf("\n=== Results: 9/9 passed ===\n");
    return 0;
}
