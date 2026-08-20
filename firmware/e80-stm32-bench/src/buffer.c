/**
 * @file    buffer.c
 * @brief   TDD RED STUBS - deliberately wrong/no-op bodies so the T1 host
 *          test suite links and FAILS (RED). Task BUF-T2 replaces every
 *          function below with the real implementation (GREEN).
 *
 *          This file intentionally contains ZERO real logic.
 */

#include "buffer.h"

#include <stddef.h>

uint16_t crc16_ccitt_false(const uint8_t* data, uint32_t len)
{
    (void)data;
    (void)len;
    return 0x0000; /* RED stub */
}

buf_load_gate_t buf_load_gate(bool role_is_rx, bool burst_active, bool tx_armed)
{
    (void)role_is_rx;
    (void)burst_active;
    (void)tx_armed;
    return (buf_load_gate_t)-1; /* RED stub: not a valid gate result */
}

const char* buf_load_gate_reply(buf_load_gate_t g)
{
    (void)g;
    return ""; /* RED stub (empty: string checks fail cleanly, never crash) */
}

void buf_clear(void) { /* RED stub: no-op */ }

uint16_t buf_len(void) { return 0xFFFF; /* RED stub */ }

uint16_t buf_crc16(void) { return 0xFFFF; /* RED stub */ }

uint32_t buf_drops(void) { return 0xFFFFFFFFu; /* RED stub */ }

bool buf_load_begin(uint16_t n)
{
    (void)n;
    return false; /* RED stub */
}

void buf_load_byte(uint8_t b) { (void)b; /* RED stub */ }

bool buf_load_commit(uint16_t expected_crc)
{
    (void)expected_crc;
    return false; /* RED stub */
}

void buf_load_abort(void) { /* RED stub */ }

bool buf_loading(void) { return false; /* RED stub */ }

uint16_t buf_read(uint32_t offset, uint8_t* out, uint16_t n)
{
    (void)offset;
    if (out != 0)
        out[0] = 0xEE; /* RED stub: poison first byte */
    return 0;          /* RED stub: wrong return */
}
