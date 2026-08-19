/**
 * @file    test_console.c
 * @brief   Host unit tests: console TX buffer sizing.
 *
 * The 23-field PKT line format needs ~128 bytes of TX buffer.
 * tx_buf must be enlarged from 96 to 160. This test asserts the
 * new minimum and verifies no silent truncation of long lines.
 *
 * TDD: Write BEFORE changing tx_buf — test fails at 96 (RED),
 * passes at 160 (GREEN).
 */

#include "stm32f1xx_hal.h"     /* host stub — replaces real HAL */

/* ---- HAL function implementations (stub) ---- */
void HAL_UART_Transmit(UART_HandleTypeDef* huart, const uint8_t* data,
                       uint16_t len, uint32_t timeout) { (void)huart; (void)data; (void)len; (void)timeout; }
void __HAL_UART_CLEAR_FLAG(UART_HandleTypeDef* huart, uint32_t flag) { (void)huart; (void)flag; }
void __HAL_UART_ENABLE_IT(UART_HandleTypeDef* huart, uint32_t flag)  { (void)huart; (void)flag; }
uint32_t __HAL_UART_GET_FLAG(UART_HandleTypeDef* huart, uint32_t flag) { (void)huart; (void)flag; return 0; }
void __HAL_UART_CLEAR_OREFLAG(UART_HandleTypeDef* huart) { (void)huart; }

/* Declare huart1 — console.c uses it as extern */
UART_HandleTypeDef huart1;

/* Include the real console.c to access its static tx_buf. */
#include "../src/console.c"

#include <stdio.h>
#include <string.h>

static int failures = 0;

#define CHECK(cond)                                                              \
    do                                                                           \
    {                                                                            \
        if (!(cond))                                                             \
        {                                                                        \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);               \
            failures++;                                                          \
        }                                                                        \
    } while (0)

/** Test that tx_buf is big enough for the 23-field PKT line. */
static void test_tx_buf_has_capacity(void)
{
    /* 23 fields × up to 5 chars each + spaces + header ≈ 128 chars.
     * Buffer must be at least 160 bytes to accommodate the longest
     * PKT line plus a safety margin. */
    CHECK(sizeof(tx_buf) >= 160);
}

/** Test that console_put() does not silently truncate a 120-char line. */
static void test_console_put_does_not_truncate_long_line(void)
{
    char longstr[121];
    memset(longstr, 'A', sizeof(longstr) - 1);
    longstr[sizeof(longstr) - 1] = '\0';

    /* console_put resets tx_len = 0, copies into tx_buf, then resets tx_len = 0
     * again after HAL_UART_Transmit.  Verify by checking tx_buf content directly:
     * every byte up to 120 should be 'A', and tx_buf[120] should be unmodified
     * (still NUL from the previous reset or 'A' if truncated past 95). */
    console_put(longstr);
    CHECK(tx_buf[119] == 'A');         /* 120th byte was written */
    CHECK(tx_buf[120] == '\0');        /* 121st byte is NUL due to \0 terminator copy */
}

static void test_tx_buf_exact_size(void)
{
    CHECK(sizeof(tx_buf) == 160);
}

int main(void)
{
    test_tx_buf_has_capacity();
    test_console_put_does_not_truncate_long_line();
    test_tx_buf_exact_size();

    if (failures == 0)
    {
        printf("test_console: ALL PASS\n");
        return 0;
    }
    printf("test_console: %d FAILURES\n", failures);
    return 1;
}