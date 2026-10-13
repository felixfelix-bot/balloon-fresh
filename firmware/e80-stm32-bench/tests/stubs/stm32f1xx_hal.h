/**
 * @file    stm32f1xx_hal.h
 * @brief   Host stub — replaces STM32 HAL headers for PC unit tests.
 *
 * Provides enough of the STM32F1 HAL surface so that console.c (and any
 * other portable module with trivial HAL dependencies) compiles with gcc.
 */
#ifndef HOST_STUB_STM32F1XX_HAL_H
#define HOST_STUB_STM32F1XX_HAL_H

#include <stdint.h>

/* Type renames that CubeMX/HAL headers define via CMSIS. */
typedef uint32_t HAL_StatusTypeDef;
#define HAL_OK      0
#define HAL_ERROR   1
#define HAL_BUSY    2
#define HAL_TIMEOUT 3

/* Minimal GPIO types (enough for main.h to compile). */
typedef uint16_t GPIO_PinState;
#define GPIO_PIN_RESET 0
#define GPIO_PIN_SET   1

#define GPIO_PIN_0   ((uint16_t)0x0001)
#define GPIO_PIN_1   ((uint16_t)0x0002)
#define GPIO_PIN_2   ((uint16_t)0x0004)
#define GPIO_PIN_3   ((uint16_t)0x0008)
#define GPIO_PIN_4   ((uint16_t)0x0010)
#define GPIO_PIN_12  ((uint16_t)0x1000)
#define GPIO_PIN_13  ((uint16_t)0x2000)
#define GPIO_PIN_14  ((uint16_t)0x4000)
#define GPIO_PIN_15  ((uint16_t)0x8000)

typedef struct { uint32_t dummy; } GPIO_TypeDef;
#define GPIOA ((GPIO_TypeDef*)0x40010800)
#define GPIOB ((GPIO_TypeDef*)0x40010C00)

/* IRQ numbers. */
typedef enum { EXTI1_IRQn = 23, EXTI2_IRQn = 24, USART1_IRQn = 37 } IRQn_Type;

/* UART types — enough for console.c to compile. */
typedef struct
{
    volatile uint32_t DR;       /* data register at offset 0x00 */
    uint32_t _reserved[8];      /* pad to cover SR, CR1, etc. */
} USART_TypeDef;

typedef struct
{
    USART_TypeDef* Instance;
    /* … other fields ignored by host stubs … */
} UART_HandleTypeDef;

/* USART flags (bare minimum). */
#define UART_FLAG_RXNE ((uint32_t)0x00000020)
#define UART_FLAG_ORE  ((uint32_t)0x00000008)

/* USART interrupt enable bits. */
#define UART_IT_RXNE   ((uint32_t)0x00000020)

/* Stub HAL functions — defined in test_console.c or left as weak. */
extern void   HAL_UART_Transmit(UART_HandleTypeDef*, const uint8_t*, uint16_t, uint32_t);
extern void   __HAL_UART_CLEAR_FLAG(UART_HandleTypeDef*, uint32_t);
extern void   __HAL_UART_ENABLE_IT(UART_HandleTypeDef*, uint32_t);
extern uint32_t __HAL_UART_GET_FLAG(UART_HandleTypeDef*, uint32_t);
extern void   __HAL_UART_CLEAR_OREFLAG(UART_HandleTypeDef*);

/* NVIC stubs — no-op on host. */
static inline void HAL_NVIC_DisableIRQ(IRQn_Type irq) { (void)irq; }
static inline void HAL_NVIC_EnableIRQ(IRQn_Type irq)  { (void)irq; }

#endif /* HOST_STUB_STM32F1XX_HAL_H */