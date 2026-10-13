/**
 * @file    bench_banner.h
 * @brief   Boot banner string for the E80 bench firmware.
 *          Refactored into a header so host tests can verify the format
 *          independently of the STM32 hardware layer.
 *
 * FW_GIT_SHA is stamped at firmware-build time via -DFW_GIT_SHA=<sha7>.
 * When compiled standalone (e.g. host test), it defaults to "unknown".
 */
#ifndef BENCH_BANNER_H
#define BENCH_BANNER_H

#ifndef FW_GIT_SHA
#define FW_GIT_SHA unknown
#endif

/* Stringification macro (kept local to avoid coupling with bench.c's E80_STR). */
#define BENCH_BANNER_STR_(x) #x
#define BENCH_BANNER_STR(x)  BENCH_BANNER_STR_(x)

/* Boot banner, printed on startup.  Reports the 7-char git build hash
 * as fw=FW_HASH=<sha7>, matching the ID? reply format. */
#define BENCH_BOOT_BANNER \
    "E80 BENCH FW v1.2 (STM32F103C8 + LR2021) fw=FW_HASH=" \
    BENCH_BANNER_STR(FW_GIT_SHA) " - 'HELP' for commands"

#endif /* BENCH_BANNER_H */