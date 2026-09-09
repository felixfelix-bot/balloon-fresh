/**
 * @file    e28_range_console.h
 * @brief   E28-2G4M27S (SX1282) ranging console core — host-testable.
 *
 * Implements the E28 ranging bridge console command set (E80-bench style,
 * case-insensitive) for the LILYGO T3S3 (ESP32-S3 + SX1282) board:
 *
 *   ID?  STAT?  RANGE  RANGE-SLAVE  RANGE?  FREQ  SF  BW  PA  ADDR  HELP
 *
 * All radio hardware access is behind an e28_io_t seam so the identical
 * object code runs in the ESP32-S3 firmware (SX1282 RadioLib ops) and in the
 * host unit tests (fake io). The indoor +10 dBm TX power cap is enforced
 * here, in the core, so it cannot be bypassed by the firmware glue.
 *
 * Ranging uses SX1282 natively: RadioLib 7.6.0's SX1282 : public SX1280,
 * and SX1280 already declares+implements range()/startRanging()/
 * finishRanging()/getRangingResult(). No subclass is needed.
 */

#ifndef E28_RANGE_CONSOLE_H
#define E28_RANGE_CONSOLE_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ---- Board constants ---------------------------------------------------- */

#define E28_RANGE_BOARD_NAME      "E28-RANGE"
#define E28_RANGE_FW_VERSION      "v1.0"
#define E28_RANGE_TXPOW_CAP_INDOOR_DBM  10   /* EU indoor cap (matches E80) */
#define E28_RANGE_DEFAULT_ADDR    0xE80E2801ul
#define E28_RANGE_FREQ_MIN_HZ     2400000000ul
#define E28_RANGE_FREQ_MAX_HZ     2500000000ul
#define E28_RANGE_SF_MIN          5
#define E28_RANGE_SF_MAX          12
#define E28_RANGE_BW_DEFAULT_KHZ  812.5f   /* ranging-valid mid row */

/* ---- Radio operations seam ---------------------------------------------- */

typedef struct e28_io_s
{
    /** Append a NUL-terminated string to the console. */
    void (*put)(const char* s);

    /** (Re)configure the radio to the current freq/sf/bw/pa. Returns a
     *  RadioLib status code (0 = RADIOLIB_ERR_NONE). */
    int (*radioBegin)(void);

    /** Run one ranging exchange. master=true initiates (master role),
     *  master=false responds (slave role). addr is the shared 32-bit
     *  ranging address. Returns a RadioLib status code. */
    int (*radioRange)(bool master, uint32_t addr);

    /** Last ranging result in meters (valid after radioRange returns 0). */
    float (*radioRangingResult)(void);
} e28_io_t;

/* ---- Core API ------------------------------------------------------------ */

/** Bind seams + reset to power-on state (role idle, indoor PA cap, default
 *  freq 2440 MHz / SF 7 / BW 812.5 kHz / addr 0xE80E2801). Emits nothing;
 *  the caller prints the boot banner. */
void e28_range_init(const e28_io_t* io, const char* fw_sha7);

/** Feed one console line (no CRLF; case-insensitive parser strips blanks). */
void e28_range_feed_line(const char* line);

/** Current config (introspection for firmware glue / tests). */
uint32_t e28_range_freq_hz(void);
uint8_t  e28_range_sf(void);
float    e28_range_bw_khz(void);
int8_t   e28_range_pa_dbm(void);
uint32_t e28_range_addr(void);
bool     e28_range_has_result(void);
float    e28_range_last_m(void);

#ifdef __cplusplus
}
#endif

#endif /* E28_RANGE_CONSOLE_H */
