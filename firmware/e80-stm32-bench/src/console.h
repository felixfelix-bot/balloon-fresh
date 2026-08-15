/**
 * @file    console.h
 * @brief   USART1 console: interrupt-driven RX line assembly, blocking TX,
 *          tiny integer formatting (no newlib printf - flash budget).
 */

#ifndef E80_CONSOLE_H
#define E80_CONSOLE_H

#include <stdint.h>

#include "main.h"

#ifdef __cplusplus
extern "C" {
#endif

#define CONSOLE_RX_RING_SIZE 128
#define CONSOLE_LINE_MAX (E80_CMD_MAX_CHARS + 8)

void console_init(void);

/** Call from USART1_IRQHandler: drains RXNE into the ring buffer. */
void console_uart_irq(void);

/** Returns a NUL-terminated line (without \r\n) when one is complete, else NULL. */
char* console_getline(void);

/** Blocking transmit of a NUL-terminated string. */
void console_put(const char* s);

void console_putln(const char* s);

/* Tiny formatters (append to internal line buffer, then console_flush()). */
void console_put_u32(uint32_t v);
void console_put_i32(int32_t v);
void console_put_u32_hex8(uint32_t v);

/** "value/10 . value%10" fixed-point print for 1-decimal values
 *  scaled by 10 (e.g. 123 -> "12.3"); handles negatives. */
void console_put_dec1(int32_t value_x10);

#ifdef __cplusplus
}
#endif

#endif /* E80_CONSOLE_H */
