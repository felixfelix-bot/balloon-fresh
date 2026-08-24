/**
 * @file    test_bench_flash.c
 * @brief   Host unit tests: FLASH command (parser surface) + the bootloader
 *          jump refusal logic (host-testable plan in bench_safety).
 *
 * Safety background (Felix decision 2026-08-16): the IWDG cannot be stopped
 * once started and the STM32F1 ROM bootloader does NOT feed it — a WDG reset
 * mid-write can brick the app unrecoverably. The firmware therefore starts
 * the IWDG only at the FIRST 'ARM TX', and 'FLASH' refuses to jump once the
 * IWDG is running (power-cycle required instead).
 *
 * The refusal decision lives in bench_safety (portable, no STM32
 * dependency): bench_safety_flash_plan(iwdg_started) plus the exact console
 * strings, so the on-wire protocol is pinned by host tests.
 */

#include "bench_cmd.h"
#include "bench_safety.h"

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

/* ---- Parser: FLASH command word ------------------------------------------- */

static void test_flash_parse(void)
{
    bench_cmd_t c;

    c = parse("FLASH");
    CHECK(c.id == BENCH_CMD_FLASH && c.err == BENCH_CMD_OK);

    c = parse("flash"); /* case-insensitive, like every command word */
    CHECK(c.id == BENCH_CMD_FLASH && c.err == BENCH_CMD_OK);

    c = parse("Flash\r\n"); /* trailing CRLF tolerated */
    CHECK(c.id == BENCH_CMD_FLASH && c.err == BENCH_CMD_OK);

    /* No arguments accepted: the jump is unconditional (plan depends only
     * on the IWDG state), so a stray argument is a typo -> SYNTAX. */
    c = parse("FLASH NOW");
    CHECK(c.id == BENCH_CMD_NONE && c.err == BENCH_CMD_E_SYNTAX);

    c = parse("FLASH 2026");
    CHECK(c.err == BENCH_CMD_E_SYNTAX);

    /* Lookalikes must stay unknown. */
    c = parse("FLASH?");
    CHECK(c.err == BENCH_CMD_E_UNKNOWN);

    c = parse("FLASHX");
    CHECK(c.err == BENCH_CMD_E_UNKNOWN);
}

/* ---- Refusal plan: IWDG running -> refuse the jump ------------------------ */

static void test_flash_plan(void)
{
    /* IWDG never started since power-on (no ARM TX yet): safe to jump. */
    CHECK(bench_safety_flash_plan(false) == BENCH_FLASH_JUMP);

    /* IWDG running (some ARM TX happened since power-on): a jump would be
     * reset mid-write by the unfed watchdog -> refuse, power-cycle first. */
    CHECK(bench_safety_flash_plan(true) == BENCH_FLASH_REFUSE_WDG_ACTIVE);
}

/* ---- Exact on-wire reply strings ------------------------------------------ */

static void test_flash_reply_strings(void)
{
    /* Pin the exact console lines: the host flash procedure greps for
     * 'OK JUMPING' before starting stm32flash, and the refusal must be an
     * unambiguous ERR line naming the remedy. */
    CHECK(strcmp(bench_safety_flash_reply(BENCH_FLASH_JUMP),
                 "OK JUMPING TO BOOTLOADER") == 0);
    CHECK(strcmp(bench_safety_flash_reply(BENCH_FLASH_REFUSE_WDG_ACTIVE),
                 "ERR POWER-CYCLE FIRST (WATCHDOG ACTIVE)") == 0);
}

/* ---- ID? 'boot=' field ----------------------------------------------------- */

static void test_id_boot_field(void)
{
    /* ID? tells the operator what FLASH would do right now. */
    CHECK(strcmp(bench_safety_boot_field(false), "boot=jump-ok") == 0);
    CHECK(strcmp(bench_safety_boot_field(true),
                 "boot=powercycle-first(wdg-active)") == 0);
}

int main(void)
{
    test_flash_parse();
    test_flash_plan();
    test_flash_reply_strings();
    test_id_boot_field();

    if (failures == 0)
    {
        printf("test_bench_flash: ALL PASS\n");
        return 0;
    }
    printf("test_bench_flash: %d FAILURES\n", failures);
    return 1;
}
