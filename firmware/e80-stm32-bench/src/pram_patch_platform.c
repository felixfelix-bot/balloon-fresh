/**
 * @file    pram_patch_platform.c
 * @brief   STM32 side of the PRAM patch: the settle delay.
 */

#include "pram_patch.h"

#include "main.h"

void pram_patch_platform_delay_ms(uint32_t ms)
{
    HAL_Delay(ms);
}
