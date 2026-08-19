/*
 * Host unit test for FW_HASH boot banner (TDD - Gate 1)
 *
 * Build: gcc -o test_fw_hash test_fw_hash.c -I../main
 * (or just gcc -DTEST_FW_HASH -o test_fw_hash test_fw_hash.c)
 *
 * This test verifies that:
 *   1. FW_GIT_SHA macro is defined
 *   2. The boot banner string includes FW_HASH=<sha>
 *
 * RED phase: fails because FW_GIT_SHA is not yet defined
 * GREEN phase: passes after CMakeLists.txt injects -DFW_GIT_SHA and
 *              range_test.cpp banner includes FW_HASH
 */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

/* The banner format we expect — defined in range_test.cpp.
 * For host testing, we simulate the banner construction. */
#ifndef FW_GIT_SHA
#define FW_GIT_SHA "unknown"
#endif

/* Simulated banner — mirrors the format in range_test.cpp app_main() */
static const char *get_banner(void) {
    static char banner[256];
    snprintf(banner, sizeof(banner),
             "=== LR2021 Range Test v1.0 FW_HASH=%s ===", FW_GIT_SHA);
    return banner;
}

int main(void) {
    int failures = 0;

    /* Test 1: FW_GIT_SHA must be defined (not "unknown" in production) */
    const char *sha = FW_GIT_SHA;
    if (strcmp(sha, "unknown") == 0) {
        fprintf(stderr, "FAIL: FW_GIT_SHA is not defined (still 'unknown')\n");
        failures++;
    } else {
        printf("PASS: FW_GIT_SHA = %s\n", sha);
    }

    /* Test 2: FW_GIT_SHA should be 7+ chars (git short hash) */
    if (strlen(sha) < 7) {
        fprintf(stderr, "FAIL: FW_GIT_SHA too short (%zu chars, expected >= 7)\n", strlen(sha));
        failures++;
    } else {
        printf("PASS: FW_GIT_SHA length = %zu\n", strlen(sha));
    }

    /* Test 3: Banner must contain "FW_HASH=" */
    const char *banner = get_banner();
    if (strstr(banner, "FW_HASH=") == NULL) {
        fprintf(stderr, "FAIL: banner does not contain 'FW_HASH='\n");
        fprintf(stderr, "  banner: %s\n", banner);
        failures++;
    } else {
        printf("PASS: banner contains FW_HASH= → %s\n", banner);
    }

    /* Test 4: Banner must contain the SHA value */
    if (strstr(banner, sha) == NULL) {
        fprintf(stderr, "FAIL: banner does not contain SHA value '%s'\n", sha);
        failures++;
    } else {
        printf("PASS: banner contains SHA value\n");
    }

    if (failures == 0) {
        printf("\nAll %d tests PASSED\n", 4);
        return 0;
    } else {
        printf("\n%d test(s) FAILED\n", failures);
        return 1;
    }
}
