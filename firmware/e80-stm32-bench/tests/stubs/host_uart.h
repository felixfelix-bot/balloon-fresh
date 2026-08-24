/**
 * @file    host_uart.h
 * @brief   Host test harness helper: RX byte injection + TX capture for tests
 *          that drive console.c (BUF binary receive framing, task BUF-T1).
 *
 * Include ONCE per test TU — this header DEFINES the HAL UART stub functions
 * and huart1 (console.c declares them extern).
 *
 * RX injection model: the queue holds bytes the "host" sent. Each
 * __HAL_UART_GET_FLAG(RXNE) that finds the queue non-empty loads the next
 * byte into Instance->DR and reports RXNE=1 — console.c reads DR right
 * after, exactly like real hardware (reading DR clears RXNE).
 *
 * TX capture: HAL_UART_Transmit appends every byte the firmware prints, so
 * tests can assert the full on-wire transcript byte-exactly.
 */

#ifndef HOST_STUB_HOST_UART_H
#define HOST_STUB_HOST_UART_H

#include "stm32f1xx_hal.h" /* host stub HAL header (tests/stubs/) */

#include <stddef.h>
#include <string.h>

/* ---- RX injection queue -------------------------------------------------- */

#define HOST_INJ_CAP 1024
static uint8_t  host_inj_q[HOST_INJ_CAP];
static volatile unsigned host_inj_head = 0; /* producer (test) writes */
static volatile unsigned host_inj_tail = 0; /* consumer (GET_FLAG) reads */

/* ---- TX capture ----------------------------------------------------------- */

#define HOST_TX_CAP 1024
static char   host_tx_cap[HOST_TX_CAP];
static size_t host_tx_len = 0;

static USART_TypeDef host_usart1;
UART_HandleTypeDef huart1 = {0}; /* console.c: extern UART_HandleTypeDef huart1 */

static void host_uart_reset(void)
{
    host_inj_head = host_inj_tail = 0;
    host_tx_len = 0;
    memset(&host_usart1, 0, sizeof(host_usart1));
    huart1.Instance = &host_usart1;
}

static void host_inject_bytes(const void* p, size_t n)
{
    const uint8_t* b = (const uint8_t*)p;
    for (size_t i = 0; i < n; i++)
    {
        unsigned next = (host_inj_head + 1) % HOST_INJ_CAP;
        if (next == (unsigned)host_inj_tail)
            break; /* queue full: test bug */
        host_inj_q[host_inj_head] = b[i];
        host_inj_head = next;
    }
}

static void host_inject_str(const char* s) { host_inject_bytes(s, strlen(s)); }

/** NUL-terminated capture of everything transmitted since reset. */
static const char* host_tx(void)
{
    host_tx_cap[host_tx_len < HOST_TX_CAP ? host_tx_len : HOST_TX_CAP - 1] = '\0';
    return host_tx_cap;
}

/* ---- HAL function definitions (stub; extern-linkage per stm32f1xx_hal.h) -- */

uint32_t __HAL_UART_GET_FLAG(UART_HandleTypeDef* huart, uint32_t flag)
{
    if (flag == UART_FLAG_RXNE && host_inj_tail != host_inj_head)
    {
        /* Load the next injected byte into DR; console.c reads it right
         * after this call returns 1 (hardware: DR read clears RXNE). */
        huart->Instance->DR = host_inj_q[host_inj_tail];
        host_inj_tail = (host_inj_tail + 1) % HOST_INJ_CAP;
        return 1;
    }
    return 0; /* RXNE empty; ORE never raised in host tests */
}

void __HAL_UART_CLEAR_FLAG(UART_HandleTypeDef* huart, uint32_t flag)
{
    (void)huart;
    (void)flag;
}

void __HAL_UART_ENABLE_IT(UART_HandleTypeDef* huart, uint32_t it)
{
    (void)huart;
    (void)it;
}

void __HAL_UART_CLEAR_OREFLAG(UART_HandleTypeDef* huart)
{
    (void)huart;
}

void HAL_UART_Transmit(UART_HandleTypeDef* huart, const uint8_t* data,
                       uint16_t len, uint32_t timeout)
{
    (void)huart;
    (void)timeout;
    for (uint16_t i = 0; i < len; i++)
    {
        if (host_tx_len < HOST_TX_CAP - 1)
            host_tx_cap[host_tx_len++] = (char)data[i];
    }
}

#endif /* HOST_STUB_HOST_UART_H */
