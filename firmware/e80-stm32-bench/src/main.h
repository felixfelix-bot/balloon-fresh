/**
 * @file    main.h
 * @brief   E80 (LR2021 module, STM32F103C8T6 host) bench firmware - common defs.
 *
 * Pin map copied verbatim from the vendor E80_DEMO CubeMX project
 * (E80/Core/Inc/main.h) so the vendored radio_hal/lr20xx_hal.c builds
 * unmodified against this header:
 *
 *   PA3  E80_BUSY   (input, radio BUSY)
 *   PA4  RADIO_NSS  (soft NSS, push-pull)
 *   PA5  SPI1_SCK   PA6 SPI1_MISO   PA7 SPI1_MOSI  (~9 MHz: 72/8)
 *   PB0  E80_NRST   (radio hardware reset)
 *   PB1  E80_DIO9   (EXTI1, unused by bench - demo wires it as well)
 *   PB2  E80_DIO8   (EXTI2, radio IRQ pin per demo DIO8-as-IRQ)
 *   PB12 LED2  PB13 LED1 (active low)
 *   PB14 KEY2  PB15 KEY1 (plain GPIO user keys, pull-up)
 */

#ifndef E80_MAIN_H
#define E80_MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

#include "stm32f1xx_hal.h"

/* ---- Radio / board pin defines (names used by third_party radio_hal) ------- */
#define E80_BUSY_Pin       GPIO_PIN_3
#define E80_BUSY_GPIO_Port GPIOA

#define RADIO_NSS_Pin       GPIO_PIN_4
#define RADIO_NSS_GPIO_Port GPIOA

#define E80_NRST_Pin       GPIO_PIN_0
#define E80_NRST_GPIO_Port GPIOB

#define E80_DIO9_Pin       GPIO_PIN_1
#define E80_DIO9_GPIO_Port GPIOB
#define E80_DIO9_EXTI_IRQn EXTI1_IRQn

#define E80_DIO8_Pin       GPIO_PIN_2
#define E80_DIO8_GPIO_Port GPIOB
#define E80_DIO8_EXTI_IRQn EXTI2_IRQn

#define LED2_Pin       GPIO_PIN_12
#define LED2_GPIO_Port GPIOB
#define LED1_Pin       GPIO_PIN_13
#define LED1_GPIO_Port GPIOB

#define KEY2_Pin       GPIO_PIN_14
#define KEY2_GPIO_Port GPIOB
#define KEY1_Pin       GPIO_PIN_15
#define KEY1_GPIO_Port GPIOB

/* ---- Bench app configuration ---------------------------------------------- */

/* Safety: compile-time default state = radio asleep, TX inhibited.
 * TX requires the two-step ROLE TX + ARM TX command sequence at runtime. */
#define E80_BENCH_BOOT_TX_INHIBITED 1

/* Default console: USART1 2,000,000 8N1. CH340 supports 2 Mbps,
 * STM32F103 USART1 supports up to 4.5 Mbps. The RX path is
 * interrupt-driven with a ring buffer. */
#define E80_BENCH_BAUD_DEFAULT 2000000U

/* Radio default: 868.0 MHz (EU SRD 863-870). */
#define E80_BENCH_FREQ_DEFAULT_HZ 868000000UL

/* EU SRD band clamp (safety gate): FREQ only accepts 863-870 MHz unless the
 * operator explicitly runs BAND OVERRIDE <pin>. 900 MHz is NOT license-exempt
 * in the EU — the override exists for lab exceptions only. */
#define E80_BENCH_BAND_MIN_HZ 863000000UL
#define E80_BENCH_BAND_MAX_HZ 870000000UL
#define E80_BENCH_OVERRIDE_PIN 2026
/* With override: sub-GHz LF path of the LR2021 (E80 module is sub-GHz only). */
#define E80_BENCH_OVERRIDE_MIN_HZ 410000000UL
#define E80_BENCH_OVERRIDE_MAX_HZ 960000000UL

/* Indoor TX power cap (safety gate, Felix Aug 16): default max +10 dBm on the
 * desk bench. +22 dBm only after explicit 'POWER MODE OUTDOOR 2026' unlock. */
#define E80_BENCH_TXPOW_CAP_INDOOR_DBM 10
#define E80_BENCH_TXPOW_MAX_DBM 22

/* Max FLRC payload 511 B (LoRa caps at 255). Buffers sized to the max. */
#define E80_BENCH_MAX_PAYLOAD 512

#ifdef __cplusplus
}
#endif

#endif /* E80_MAIN_H */
