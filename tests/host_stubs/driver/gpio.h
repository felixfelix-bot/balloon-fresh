#pragma once

#include <stdint.h>
#include <string.h>

typedef struct { uint32_t pin_bit_mask; int mode; int pull_up_en; int pull_down_en; int intr_type; } gpio_config_t;

#define GPIO_MODE_OUTPUT 1
#define GPIO_PULLUP_DISABLE 0
#define GPIO_PULLDOWN_DISABLE 0
#define GPIO_INTR_DISABLE 0
#define GPIO_PULLUP_ENABLE 1

static int last_gpio_levels[64];
static int gpio_config_called;

static inline void gpio_config(gpio_config_t *c) { (void)c; gpio_config_called = 1; }
static inline void gpio_set_level(int pin, int level) {
    if (pin >= 0 && pin < 64) last_gpio_levels[pin] = level;
}

static inline void gpio_stubs_reset(void) {
    memset(last_gpio_levels, 0, sizeof(last_gpio_levels));
    gpio_config_called = 0;
}
