/**
 * @file    stm32f1xx_hal_conf.h
 * @brief   Minimal HAL configuration for the E80 LR2021 bench firmware.
 *
 * Only the modules actually used are enabled to stay inside the
 * STM32F103C8T6 64 KiB flash budget:
 *   RCC (clocks) + FLASH (latency, via macros) + GPIO + SPI (radio bus)
 *   + UART (console) + CORTEX (NVIC helpers).
 * No DMA, no PWR low-power modes, no timers (SysTick tick via core HAL).
 */

#ifndef STM32F1XX_HAL_CONF_H
#define STM32F1XX_HAL_CONF_H

#ifdef __cplusplus
extern "C" {
#endif

/* Module enable switches ---------------------------------------------------*/
#define HAL_MODULE_ENABLED
#define HAL_RCC_MODULE_ENABLED
#define HAL_FLASH_MODULE_ENABLED
#define HAL_GPIO_MODULE_ENABLED
#define HAL_SPI_MODULE_ENABLED
#define HAL_UART_MODULE_ENABLED
#define HAL_DMA_MODULE_ENABLED /* SPI/UART handles embed DMA_HandleTypeDef */
#define HAL_CORTEX_MODULE_ENABLED
#define HAL_IWDG_MODULE_ENABLED /* TX-hang watchdog defense 3 (bench_safety.h) */
/* HAL_EXTI_MODULE_ENABLED not needed: GPIO EXTI handling lives in HAL_GPIO. */

/* Oscillator values in Hz ---------------------------------------------------*/
/* E80 board has an 8 MHz HSE crystal (x9 PLL -> 72 MHz SYSCLK). */
#ifndef HSE_VALUE
#define HSE_VALUE 8000000U
#endif
#ifndef HSE_STARTUP_TIMEOUT
#define HSE_STARTUP_TIMEOUT 100U
#endif
#ifndef HSI_VALUE
#define HSI_VALUE 8000000U
#endif
#ifndef LSI_VALUE
#define LSI_VALUE 40000U
#endif
#ifndef LSE_VALUE
#define LSE_VALUE 32768U
#endif
#ifndef LSE_STARTUP_TIMEOUT
#define LSE_STARTUP_TIMEOUT 5000U
#endif
#ifndef EXTERNAL_SAI1_CLOCK_VALUE
#define EXTERNAL_SAI1_CLOCK_VALUE 2097000U
#endif
#ifndef EXTERNAL_SAI2_CLOCK_VALUE
#define EXTERNAL_SAI2_CLOCK_VALUE 2097000U
#endif

#define VDD_VALUE                    3300U  /*!< mV */
#define TICK_INT_PRIORITY            15U    /*!< SysTick lowest priority */
#define USE_RTOS                     0U
#define PREFETCH_ENABLE              1U
#define USE_SPI_CRC                  0U

/* SysTick: F1 HAL always derives the tick from HCLK (no source select). */

/* Include the enabled modules ------------------------------------------------*/
#ifdef HAL_RCC_MODULE_ENABLED
#include "stm32f1xx_hal_rcc.h"
#endif
#ifdef HAL_FLASH_MODULE_ENABLED
#include "stm32f1xx_hal_flash.h"
#endif
#ifdef HAL_GPIO_MODULE_ENABLED
#include "stm32f1xx_hal_gpio.h"
#endif
#ifdef HAL_DMA_MODULE_ENABLED
#include "stm32f1xx_hal_dma.h"
#endif
#ifdef HAL_SPI_MODULE_ENABLED
#include "stm32f1xx_hal_spi.h"
#endif
#ifdef HAL_UART_MODULE_ENABLED
#include "stm32f1xx_hal_uart.h"
#endif
#ifdef HAL_CORTEX_MODULE_ENABLED
#include "stm32f1xx_hal_cortex.h"
#endif
#ifdef HAL_IWDG_MODULE_ENABLED
#include "stm32f1xx_hal_iwdg.h"
#endif

/* Exported macros ------------------------------------------------------------*/
#define HAL_ENABLE_CYCCYCNT 0

#ifdef USE_FULL_ASSERT
void assert_failed(uint8_t* file, uint32_t line);
#define assert_param(expr) ((expr) ? (void)0U : assert_failed((uint8_t*)__FILE__, __LINE__))
#else
#define assert_param(expr) ((void)0U)
#endif /* USE_FULL_ASSERT */

#ifdef __cplusplus
}
#endif

#endif /* STM32F1XX_HAL_CONF_H */
