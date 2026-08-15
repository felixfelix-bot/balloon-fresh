/**
 * @file    stm32f1xx_it.c
 * @brief   Interrupt vectors for the E80 bench firmware (overrides the weak
 *          handlers in the CMSIS gcc startup file).
 */

#include "main.h"
#include "console.h"
#include "radio_bench.h"

extern UART_HandleTypeDef huart1;
extern SPI_HandleTypeDef hspi1;

/******************************************************************************/
/* Cortex-M3 Processor Exceptions Handlers                                    */
/******************************************************************************/

void NMI_Handler(void) {}

void HardFault_Handler(void)
{
    while (1)
    {
    }
}

void MemManage_Handler(void)
{
    while (1)
    {
    }
}

void BusFault_Handler(void)
{
    while (1)
    {
    }
}

void UsageFault_Handler(void)
{
    while (1)
    {
    }
}

void SVC_Handler(void) {}

void DebugMon_Handler(void) {}

void PendSV_Handler(void) {}

void SysTick_Handler(void)
{
    HAL_IncTick();
}

/******************************************************************************/
/* STM32F1 Peripheral Interrupt Handlers                                      */
/******************************************************************************/

/** Radio IRQ: DIO8 rising edge on PB2 (EXTI line 2). */
void EXTI2_IRQHandler(void)
{
    HAL_GPIO_EXTI_IRQHandler(E80_DIO8_Pin);
}

void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
    if (GPIO_Pin == E80_DIO8_Pin)
    {
        radio_bench_irq();
    }
}

/** Console UART. */
void USART1_IRQHandler(void)
{
    console_uart_irq();
}
