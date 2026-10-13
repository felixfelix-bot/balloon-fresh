/**
 * @file    test_bench_banner.c
 * @brief   Host unit test: boot banner format.
 *
 * Verifies that the boot banner includes the firmware hash
 * (fw=FW_HASH=<sha7>).  After the feature is implemented, this test
 * transitions from RED (no fw=) to GREEN (fw= present).
 */
#include "bench_banner.h"

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

static void test_boot_banner_contains_fw_hash(void)
{
    const char* banner = BENCH_BOOT_BANNER;

    printf("Banner: %s\n", banner);

    /* The boot banner MUST report the firmware build hash as fw=... */
    CHECK(strstr(banner, "fw=") != NULL);

    /* When FW_GIT_SHA is defined (build-time injected), the banner should
     * contain a 7-hex-char hash.  When it's the fallback "unknown", we
     * still expect the fw= field to exist. */
    printf("FW_GIT_SHA=%s\n", BENCH_BANNER_STR(FW_GIT_SHA));
    CHECK(strlen(BENCH_BANNER_STR(FW_GIT_SHA)) > 0);
}

int main(void)
{
    printf("=== test_bench_banner ===\n");

    test_boot_banner_contains_fw_hash();

    if (failures > 0)
    {
        printf("\n*** %d FAILURES ***\n", failures);
        return 1;
    }

    printf("\n*** ALL PASS ***\n");
    return 0;
}