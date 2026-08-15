/**
 * @file    console.c
 * @brief   USART1 console for the E80 bench firmware.
 */

#include "console.h"
#include "bench_cmd.h"

#include <stddef.h>

extern UART_HandleTypeDef huart1;

static volatile char    rx_ring[CONSOLE_RX_RING_SIZE];
static volatile uint8_t rx_head = 0; /* ISR writes */
static volatile uint8_t rx_tail = 0; /* main reads  */

static char     line_buf[CONSOLE_LINE_MAX];
static uint16_t line_len = 0;
static volatile uint8_t line_ready = 0;

/* TX staging (console_put* append here, console_flush sends) */
static char     tx_buf[96];
static uint16_t tx_len = 0;

void console_init(void)
{
    /* RX interrupt enable (UART already initialized by bench.c). */
    __HAL_UART_CLEAR_FLAG(&huart1, UART_FLAG_RXNE);
    __HAL_UART_ENABLE_IT(&huart1, UART_IT_RXNE);
}

void console_uart_irq(void)
{
    while (__HAL_UART_GET_FLAG(&huart1, UART_FLAG_RXNE))
    {
        char c = (char)(huart1.Instance->DR & 0xFF);
        uint8_t next = (uint8_t)((rx_head + 1) % CONSOLE_RX_RING_SIZE);
        if (next != rx_tail) /* drop on overflow */
        {
            rx_ring[rx_head] = c;
            rx_head = next;
        }
    }
}

char* console_getline(void)
{
    if (line_ready)
        return NULL; /* caller must consume previous line first (it won't) */

    while (rx_tail != rx_head)
    {
        char c = rx_ring[rx_tail];
        rx_tail = (uint8_t)((rx_tail + 1) % CONSOLE_RX_RING_SIZE);

        if (c == '\r' || c == '\n')
        {
            if (line_len == 0)
                continue; /* skip empty lines / lone CR after LF */
            line_buf[line_len] = '\0';
            line_len = 0;
            line_ready = 1;
            return line_buf;
        }
        if (line_len < CONSOLE_LINE_MAX - 1)
        {
            line_buf[line_len++] = c;
        }
        /* else: overlong line silently truncated */
    }
    return NULL;
}

static void line_consumed(void)
{
    line_ready = 0;
}

void console_put(const char* s)
{
    tx_len = 0;
    while (*s != '\0' && tx_len < sizeof(tx_buf) - 1)
        tx_buf[tx_len++] = *s++;
    if (tx_len)
        HAL_UART_Transmit(&huart1, (uint8_t*)tx_buf, tx_len, 100);
    tx_len = 0;
    line_consumed(); /* a reply marks the line consumed */
}

void console_putln(const char* s)
{
    console_put(s);
    console_put("\r\n");
}

void console_put_u32(uint32_t v)
{
    char tmp[11];
    int i = 0;
    if (v == 0)
    {
        HAL_UART_Transmit(&huart1, (const uint8_t*)"0", 1, 100);
        return;
    }
    while (v > 0 && i < 10)
    {
        tmp[i++] = (char)('0' + (v % 10));
        v /= 10;
    }
    while (i > 0)
        HAL_UART_Transmit(&huart1, (const uint8_t*)&tmp[--i], 1, 100);
}

void console_put_i32(int32_t v)
{
    if (v < 0)
    {
        HAL_UART_Transmit(&huart1, (const uint8_t*)"-", 1, 100);
        console_put_u32((uint32_t)(-v));
    }
    else
    {
        console_put_u32((uint32_t)v);
    }
}

void console_put_u32_hex8(uint32_t v)
{
    static const char hex[] = "0123456789ABCDEF";
    char tmp[8];
    for (int i = 0; i < 8; i++)
        tmp[i] = hex[(v >> ((7 - i) * 4)) & 0xF];
    HAL_UART_Transmit(&huart1, (const uint8_t*)tmp, 8, 100);
}

void console_put_dec1(int32_t value_x10)
{
    if (value_x10 < 0)
    {
        HAL_UART_Transmit(&huart1, (const uint8_t*)"-", 1, 100);
        value_x10 = -value_x10;
    }
    console_put_u32((uint32_t)(value_x10 / 10));
    HAL_UART_Transmit(&huart1, (const uint8_t*)".", 1, 100);
    console_put_u32((uint32_t)(value_x10 % 10));
}
