#pragma once

#include <stdint.h>

typedef struct { uint32_t pin_bit_mask; int mode; int pull_up_en; int pull_down_en; int intr_type; } gpio_config_t;
static inline void gpio_config(gpio_config_t *c) { (void)c; }
static inline void gpio_set_level(int pin, int level) { (void)pin;(void)level; }

#define GPIO_MODE_OUTPUT 1
#define GPIO_PULLUP_DISABLE 0
#define GPIO_PULLDOWN_DISABLE 0
#define GPIO_INTR_DISABLE 0
