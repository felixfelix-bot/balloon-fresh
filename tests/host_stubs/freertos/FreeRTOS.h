#pragma once

#define pdMS_TO_TICKS(ms) (ms)
static inline void vTaskDelay(int ticks) { (void)ticks; }
