/**
 * @file    flrc_range_host_types.h
 * @brief   Shared modem-type enum for the host-driven range bench.
 *
 * Minimal types header so pure modules (safety, stats, cmd) can reference
 * the modem type without pulling in Arduino or radio headers.
 *
 * Adapts E80 bench_cmd.h bench_mod_t for the LR2021 RP2040 bench.
 */

#ifndef FLRC_RANGE_HOST_TYPES_H
#define FLRC_RANGE_HOST_TYPES_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum
{
    BENCH_MOD_LORA = 0,
    BENCH_MOD_FLRC,
} bench_mod_t;

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* FLRC_RANGE_HOST_TYPES_H */