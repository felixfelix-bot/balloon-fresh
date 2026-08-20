/**
 * @file    test_console_binary.c
 * @brief   Host unit tests: console binary receive framing (task BUF-T1, RED).
 *
 * Drives the REAL console.c over an injected UART (stubs/host_uart.h):
 * host "sends" bytes, the console assembles lines / consumes binary payload,
 * and every transmitted byte is captured so the on-wire transcript can be
 * asserted exactly.
 *
 * Covered (tx-buffer-spec):
 *   - 'OK BINARY <n>' ack, then exactly n raw payload bytes consumed,
 *     final 'OK BUF <n> <crc_ok>' with crc_ok=1
 *   - off-by-2 guard: the command line's trailing CR/LF is consumed BEFORE
 *     counting payload bytes (CRLF and LF-only line endings)
 *   - SILENT between ack and final reply (byte-exact transcript)
 *   - 'ERR CRC' on CRC mismatch (and len=0 afterwards)
 *   - 1.0 s idle timeout: 'ERR TIMEOUT', partial discarded, previously
 *     committed buffer survives, console returns to line mode
 *
 * The IWDG feed during the wait loop is firmware-side (bench.c superloop
 * calls poll() between feeds) — not observable here by design.
 *
 * TDD: fails against the RED stubs in console.c/buffer.c. BUF-T2 turns it
 * green.
 */

#include "host_uart.h" /* defines HAL stubs + huart1 + RX inject + TX capture */

/* Include the real console.c to reach its static RX ring / line state. */
#include "../src/console.c"

#include "buffer.h"

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

/* crc16("123456789") == 0x29B1 (golden vector, test_buffer.c / python side) */
#define CRC_123456789 0x29B1u
/* crc16("ABCD") == 0xBFFA */
#define CRC_ABCD 0xBFFAu

/** Pull one line through the console (injected beforehand) and hand it to the
 *  "handler": gate OK assumed; enter binary with n/crc taken by the caller. */
static void get_line(const char* expect)
{
    char* line = console_getline();
    CHECK(line != NULL);
    if (line)
        CHECK(strcmp(line, expect) == 0);
}

/* ---- ack + complete happy path; CRLF line ending (off-by-2 guard) ---------- */

static void test_ack_complete_crlf(void)
{
    uint8_t tmp[8];

    host_uart_reset();
    /* Everything pre-injected, exactly as the host tool would send it:
     * line + CRLF terminator, then the raw payload. console_getline returns
     * at the '\r' and leaves the '\n' in the ring — the binary phase must
     * swallow it WITHOUT counting it (else the payload shifts by up to 2). */
    host_inject_str("BUF LOAD 4 BFFA\r\nABCD");

    get_line("BUF LOAD 4 BFFA");

    console_binary_start(4, CRC_ABCD, 0);
    CHECK(console_binary_active() == true);

    /* Ack is out before any payload byte is consumed. */
    CHECK(strcmp(host_tx(), "OK BINARY 4\r\n") == 0);

    CHECK(console_binary_poll(1) == CONSOLE_BIN_DONE);
    CHECK(console_binary_active() == false);

    /* Exact transcript: ack + final reply, NOTHING between (silence). */
    CHECK(strcmp(host_tx(), "OK BINARY 4\r\nOK BUF 4 1\r\n") == 0);

    /* Payload staged, byte-exact. */
    CHECK(buf_len() == 4);
    CHECK(buf_crc16() == CRC_ABCD);
    CHECK(buf_read(0, tmp, 4) == 4);
    CHECK(memcmp(tmp, "ABCD", 4) == 0);
}

/* ---- LF-only line ending (nothing pending in the ring — must still work) --- */

static void test_ack_complete_lf_only(void)
{
    host_uart_reset();
    host_inject_str("BUF LOAD 4 BFFA\nABCD");

    get_line("BUF LOAD 4 BFFA");
    console_binary_start(4, CRC_ABCD, 0);
    CHECK(console_binary_poll(1) == CONSOLE_BIN_DONE);
    CHECK(strcmp(host_tx(), "OK BINARY 4\r\nOK BUF 4 1\r\n") == 0);
    CHECK(buf_len() == 4);
}

/* ---- Silence mid-transfer, completion in a second batch -------------------- */

static void test_silence_during_binary(void)
{
    host_uart_reset();
    host_inject_str("BUF LOAD 9 29B1\r\n");
    get_line("BUF LOAD 9 29B1");
    console_binary_start(9, CRC_123456789, 0);

    host_inject_str("1234"); /* first 4 of 9 payload bytes */
    CHECK(console_binary_poll(5) == CONSOLE_BIN_WAITING);
    CHECK(console_binary_active() == true);
    /* Nothing beyond the ack has been printed. */
    CHECK(strcmp(host_tx(), "OK BINARY 9\r\n") == 0);

    host_inject_str("56789"); /* rest */
    CHECK(console_binary_poll(10) == CONSOLE_BIN_DONE);
    CHECK(strcmp(host_tx(), "OK BINARY 9\r\nOK BUF 9 1\r\n") == 0);
    CHECK(buf_len() == 9);
}

/* ---- CRC mismatch: 'ERR CRC', buffer cleared (len=0) ------------------------ */

static void test_err_crc(void)
{
    host_uart_reset();
    host_inject_str("BUF LOAD 4 29B1\r\nABCD"); /* crc belongs to "123456789" */
    get_line("BUF LOAD 4 29B1");
    console_binary_start(4, CRC_123456789, 0);
    CHECK(console_binary_poll(1) == CONSOLE_BIN_CRC);
    CHECK(console_binary_active() == false);
    CHECK(strcmp(host_tx(), "OK BINARY 4\r\nERR CRC\r\n") == 0);
    CHECK(buf_len() == 0); /* stale-partial forbidden (rule 5) */
}

/* ---- 1.0 s idle timeout: abort, discard, previous buffer survives ----------- */

static void test_idle_timeout(void)
{
    uint8_t tmp[8];

    /* Pre-stage a committed buffer that must SURVIVE the timeout (rule 3:
     * abort discards only the partial in-flight load). */
    buf_clear();
    CHECK(buf_load_begin(4) == true);
    buf_load_byte('A');
    buf_load_byte('B');
    buf_load_byte('C');
    buf_load_byte('D');
    CHECK(buf_load_commit(CRC_ABCD) == true);

    host_uart_reset();
    host_inject_str("BUF LOAD 8 DEAD\r\n12"); /* only 2 of 8 payload bytes */
    get_line("BUF LOAD 8 DEAD");
    console_binary_start(8, 0xDEAD, 0);

    CHECK(console_binary_poll(500) == CONSOLE_BIN_WAITING); /* 2 bytes in */
    CHECK(console_binary_poll(999) == CONSOLE_BIN_WAITING); /* 499 ms idle */
    CHECK(console_binary_poll(1500) == CONSOLE_BIN_TIMEOUT); /* 1000 ms idle */
    CHECK(console_binary_active() == false);
    CHECK(buf_loading() == false);

    CHECK(strcmp(host_tx(), "OK BINARY 8\r\nERR TIMEOUT\r\n") == 0);

    /* Previous committed buffer untouched. */
    CHECK(buf_len() == 4);
    CHECK(buf_read(0, tmp, 4) == 4);
    CHECK(memcmp(tmp, "ABCD", 4) == 0);

    /* Console is back in line mode: the next line parses as a line. */
    host_inject_str("STAT?\r\n");
    char* line = console_getline();
    CHECK(line != NULL);
    if (line)
        CHECK(strcmp(line, "STAT?") == 0);
}

/* ---- Idle timeout with zero bytes ever received ------------------------------ */

static void test_idle_timeout_no_bytes(void)
{
    host_uart_reset();
    host_inject_str("BUF LOAD 4 BFFA\r\n");
    get_line("BUF LOAD 4 BFFA");
    console_binary_start(4, CRC_ABCD, 0);

    CHECK(console_binary_poll(999) == CONSOLE_BIN_WAITING);
    CHECK(strcmp(host_tx(), "OK BINARY 4\r\n") == 0);
    CHECK(console_binary_poll(1000) == CONSOLE_BIN_TIMEOUT); /* exactly 1.0 s */
    CHECK(strcmp(host_tx(), "OK BINARY 4\r\nERR TIMEOUT\r\n") == 0);
}

/* ---- Without binary mode the console is a plain line console ---------------- */

static void test_line_mode_untouched(void)
{
    host_uart_reset();
    CHECK(console_binary_active() == false);
    CHECK(console_binary_state() == CONSOLE_BIN_IDLE);

    host_inject_str("STAT?\r\n");
    char* line = console_getline();
    CHECK(line != NULL);
    if (line)
        CHECK(strcmp(line, "STAT?") == 0);
}

int main(void)
{
    test_line_mode_untouched(); /* fresh console first */
    test_ack_complete_crlf();
    test_ack_complete_lf_only();
    test_silence_during_binary();
    test_err_crc();
    test_idle_timeout();
    test_idle_timeout_no_bytes();

    if (failures == 0)
    {
        printf("test_console_binary: ALL PASS\n");
        return 0;
    }
    printf("test_console_binary: %d FAILURES\n", failures);
    return 1;
}
