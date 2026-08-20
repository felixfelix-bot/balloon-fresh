/**
 * @file    console.h
 * @brief   USART1 console: interrupt-driven RX line assembly, blocking TX,
 *          tiny integer formatting (no newlib printf - flash budget).
 */

#ifndef E80_CONSOLE_H
#define E80_CONSOLE_H

#include <stdint.h>
#include <stdbool.h>

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

/* ---- Binary payload receive phase (BUF LOAD; tx-buffer-spec) --------------- */

typedef enum
{
    CONSOLE_BIN_IDLE = 0, /* not in a binary phase */
    CONSOLE_BIN_WAITING,  /* consuming payload bytes */
    CONSOLE_BIN_DONE,     /* n bytes in, CRC matched, 'OK BUF <n> 1' printed */
    CONSOLE_BIN_CRC,      /* n bytes in, CRC mismatch, 'ERR CRC' printed */
    CONSOLE_BIN_TIMEOUT,  /* idle > BUF_IDLE_TIMEOUT_MS, 'ERR TIMEOUT' printed */
} console_bin_state_t;

/** Enter the binary phase (called by the command handler after the BUF LOAD
 *  gate returned OK). Prints the 'OK BINARY <n>' ack, then swallows the
 *  command line's pending trailing CR/LF WITHOUT counting it as payload.
 *  The next n raw RX bytes are routed to the staging buffer (no escape,
 *  no echo). The console is SILENT between the ack and the final reply.
 *  @param now_ms  idle-timeout baseline (HAL_GetTick() in firmware). */
void console_binary_start(uint16_t n, uint16_t expected_crc, uint32_t now_ms);

/** True while a binary receive is in progress (superloop: poll + feed IWDG). */
bool console_binary_active(void);

/** Drive the binary phase from the superloop: moves pending RX bytes into the
 *  staging buffer and checks the idle timeout (no payload byte for
 *  BUF_IDLE_TIMEOUT_MS -> abort + discard). Prints the final reply
 *  ('OK BUF <n> 1' / 'ERR CRC' / 'ERR TIMEOUT') and leaves binary mode.
 *  While binary is active, line assembly is suspended. */
console_bin_state_t console_binary_poll(uint32_t now_ms);

/** Current phase state (CONSOLE_BIN_IDLE when none). */
console_bin_state_t console_binary_state(void);

#ifdef __cplusplus
}
#endif

#endif /* E80_CONSOLE_H */
