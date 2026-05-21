#ifndef MICRO_ECC_PLATFORM_H
#define MICRO_ECC_PLATFORM_H

#include "esp_random.h"

#ifdef __cplusplus
extern "C" {
#endif

static inline int micro_ecc_rng(uint8_t *dest, unsigned size) {
    esp_fill_random(dest, size);
    return 1;
}

void micro_ecc_init(void);

#ifdef __cplusplus
}
#endif

#endif
