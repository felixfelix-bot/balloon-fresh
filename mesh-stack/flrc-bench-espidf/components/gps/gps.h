#pragma once

#include <stdint.h>
#include <stdbool.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    bool fix;
    int32_t latitude;
    int32_t longitude;
    uint16_t altitude_m;
    uint8_t sats;
    float hdop;
} gps_data_t;

esp_err_t gps_init(void);
bool gps_read(gps_data_t *data);
void gps_sleep(void);
void gps_wakeup(void);

#ifdef __cplusplus
}
#endif
