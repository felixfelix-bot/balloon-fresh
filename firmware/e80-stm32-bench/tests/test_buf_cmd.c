/**
 * @file    test_buf_cmd.c
 * @brief   Host unit tests: BUF command parser surface (task BUF-T1, TDD RED).
 *
 * Protocol surface (docs/plans/tx-buffer-spec.md):
 *   BUF CLEAR                     -> BENCH_CMD_BUF_CLEAR
 *   BUF STATUS                    -> BENCH_CMD_BUF_STATUS
 *   BUF LOAD <n> <crc16_hex>      -> BENCH_CMD_BUF_LOAD, 1 <= n <= 4096
 *
 * n==0 and n>4096 are rejected AT PARSE TIME (E_RANGE) so the binary phase
 * is never entered with an impossible byte count ("pre-binary" cells of the
 * reject matrix). CRC field: 1-4 hex digits, case-insensitive, no 0x prefix.
 *
 * TDD: these tests fail against the current parser (BUF parses as
 * E_UNKNOWN) — RED. Task BUF-T2 implements the parsing (GREEN).
 */

#include "bench_cmd.h"

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

static bench_cmd_t parse(const char* line)
{
    bench_cmd_t c;
    memset(&c, 0, sizeof(c));
    bench_cmd_parse(line, &c);
    return c;
}

/* ---- BUF CLEAR / BUF STATUS ------------------------------------------------ */

static void test_buf_clear_parse(void)
{
    bench_cmd_t c;

    c = parse("BUF CLEAR");
    CHECK(c.id == BENCH_CMD_BUF_CLEAR && c.err == BENCH_CMD_OK);

    c = parse("buf clear"); /* case-insensitive, like every command word */
    CHECK(c.id == BENCH_CMD_BUF_CLEAR && c.err == BENCH_CMD_OK);

    c = parse("Buf Clear\r\n"); /* trailing CRLF tolerated */
    CHECK(c.id == BENCH_CMD_BUF_CLEAR && c.err == BENCH_CMD_OK);

    c = parse("BUF CLEAR X"); /* no arguments accepted */
    CHECK(c.id == BENCH_CMD_NONE && c.err == BENCH_CMD_E_SYNTAX);
}

static void test_buf_status_parse(void)
{
    bench_cmd_t c;

    c = parse("BUF STATUS");
    CHECK(c.id == BENCH_CMD_BUF_STATUS && c.err == BENCH_CMD_OK);

    c = parse("buf status");
    CHECK(c.id == BENCH_CMD_BUF_STATUS && c.err == BENCH_CMD_OK);

    c = parse("BUF STATUS 1");
    CHECK(c.err == BENCH_CMD_E_SYNTAX);
}

/* ---- BUF LOAD happy path --------------------------------------------------- */

static void test_buf_load_parse(void)
{
    bench_cmd_t c;

    c = parse("BUF LOAD 64 29B1");
    CHECK(c.id == BENCH_CMD_BUF_LOAD && c.err == BENCH_CMD_OK);
    CHECK(c.buf_load_n == 64);
    CHECK(c.buf_load_crc == 0x29B1);

    c = parse("buf load 4096 bffa"); /* lowercase hex, capacity max n */
    CHECK(c.id == BENCH_CMD_BUF_LOAD && c.err == BENCH_CMD_OK);
    CHECK(c.buf_load_n == 4096);
    CHECK(c.buf_load_crc == 0xBFFA);

    c = parse("BUF LOAD 1 B1"); /* short hex (1-4 digits) tolerated */
    CHECK(c.id == BENCH_CMD_BUF_LOAD && c.err == BENCH_CMD_OK);
    CHECK(c.buf_load_n == 1);
    CHECK(c.buf_load_crc == 0x00B1);

    c = parse("Buf Load 9 29b1\r\n");
    CHECK(c.id == BENCH_CMD_BUF_LOAD && c.err == BENCH_CMD_OK);
    CHECK(c.buf_load_n == 9);
    CHECK(c.buf_load_crc == 0x29B1);
}

/* ---- BUF LOAD range rejects (PRE-binary: never enter the binary phase) ---- */

static void test_buf_load_range_rejects(void)
{
    bench_cmd_t c;

    c = parse("BUF LOAD 0 29B1"); /* n==0 impossible -> reject before ack */
    CHECK(c.err == BENCH_CMD_E_RANGE);
    CHECK(c.id == BENCH_CMD_NONE);

    c = parse("BUF LOAD 4097 29B1"); /* over capacity */
    CHECK(c.err == BENCH_CMD_E_RANGE);

    c = parse("BUF LOAD 999999 29B1");
    CHECK(c.err == BENCH_CMD_E_RANGE);

    c = parse("BUF LOAD 4294967296 29B1"); /* u32 overflow -> bad arg */
    CHECK(c.err == BENCH_CMD_E_ARG);
}

/* ---- BUF LOAD syntax / arg rejects ----------------------------------------- */

static void test_buf_load_syntax_rejects(void)
{
    bench_cmd_t c;

    c = parse("BUF"); /* missing subcommand -> malformed line */
    CHECK(c.err == BENCH_CMD_E_SYNTAX);

    c = parse("BUF FOO"); /* unknown subcommand -> bad argument */
    CHECK(c.err == BENCH_CMD_E_ARG);

    c = parse("BUF LOAD"); /* missing n and crc */
    CHECK(c.err == BENCH_CMD_E_SYNTAX);

    c = parse("BUF LOAD 64"); /* missing crc */
    CHECK(c.err == BENCH_CMD_E_SYNTAX);

    c = parse("BUF LOAD 64 29B1 X"); /* extra token */
    CHECK(c.err == BENCH_CMD_E_SYNTAX);

    c = parse("BUF LOAD six 29B1"); /* non-numeric n */
    CHECK(c.err == BENCH_CMD_E_ARG);

    c = parse("BUF LOAD -4 29B1"); /* negative n */
    CHECK(c.err == BENCH_CMD_E_ARG);

    c = parse("BUF LOAD 64 29G1"); /* non-hex crc */
    CHECK(c.err == BENCH_CMD_E_ARG);

    c = parse("BUF LOAD 64 0x29B1"); /* no 0x prefix allowed */
    CHECK(c.err == BENCH_CMD_E_ARG);

    c = parse("BUF LOAD 64 12345"); /* >4 hex digits */
    CHECK(c.err == BENCH_CMD_E_ARG);
}

/* ---- Lookalikes stay unknown ----------------------------------------------- */

static void test_buf_lookalikes_unknown(void)
{
    CHECK(parse("BUFLOAD").err == BENCH_CMD_E_UNKNOWN);
    CHECK(parse("BUFFER").err == BENCH_CMD_E_UNKNOWN);
    CHECK(parse("BUF?").err == BENCH_CMD_E_UNKNOWN);
}

int main(void)
{
    test_buf_clear_parse();
    test_buf_status_parse();
    test_buf_load_parse();
    test_buf_load_range_rejects();
    test_buf_load_syntax_rejects();
    test_buf_lookalikes_unknown();

    if (failures == 0)
    {
        printf("test_buf_cmd: ALL PASS\n");
        return 0;
    }
    printf("test_buf_cmd: %d FAILURES\n", failures);
    return 1;
}
