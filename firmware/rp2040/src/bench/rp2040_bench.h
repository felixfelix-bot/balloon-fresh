/**
 * @file    rp2040_bench.h
 * @brief   RP2040BENCH console core — host-testable bench firmware (HARM-T5).
 *
 * Implements the BENCH-CONSOLE-SPEC (docs/BENCH-CONSOLE-SPEC.md) minimum set
 * for the RP2040 + LR2021 board: ROLE TX/RX/NONE, ARM TX, MOD, FREQ, PA,
 * START/STOP, SESSION/CONFIG, PRBS, STAT?, ID?, HELP plus the BUF staging
 * extension (vendored buffer.c) and the runtime PA cap (indoor +10 dBm,
 * POWER MODE OUTDOOR 2026 unlock to +22 dBm, spec §2.4).
 *
 * All hardware access is behind two seams so the identical object code runs
 * in the RP2040 firmware and in the host unit tests:
 *   - bench_io_t         console output, clock, binary-phase byte source
 *   - bench_radio_ops_t  raw-SPI radio operations (bench_radio_sx1280.cpp)
 *
 * Reuse policy (harmonization-plan): the raw-SPI layer is lifted verbatim
 * from firmware/rp2040/src/multi_radio_sweep_rx_v4.cpp (rfWriteCmd /
 * rfInitForPhaseRX FLRC branch / rfReadRxFifo / GET_FLRC_PACKET_STATUS);
 * multi_radio_sweep_rx_v4.cpp itself is NOT modified. The FLRC 511-byte lift:
 * SET_FLRC_PACKET_PARAMS (0x0249) payload-length field is the chip's 16-bit
 * field (byte[4..5], big-endian); v4 sent {0x00, len8}. Golden §8 bytes:
 * 0x1E (preamble 32 | sync 4B), 0x7D (CRC-2B ON | FIX_LEN | Match123 | TXSW1).
 */

#ifndef RP2040_BENCH_H
#define RP2040_BENCH_H

#include <stdint.h>
#include <stdbool.h>
#include "bench_cmd.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ---- Board constants (spec §2.4 / §9 — RP2040BENCH) ------------------------ */

#define RP2040_BENCH_BOARD_NAME     "RP2040BENCH"
#define RP2040_BENCH_FW_VERSION     "v1.0"
#define RP2040_BENCH_CHIP_VERSION   "2.1"   /* LR2021 radio fw version (informational) */

#define RP2040_BENCH_BAND_MIN_HZ    863000000UL
#define RP2040_BENCH_BAND_MAX_HZ    870000000UL
#define RP2040_BENCH_FREQ_2440_HZ   2440000000UL

#define RP2040_BENCH_TXPOW_CAP_INDOOR_DBM  10   /* 0..+10 dBm indoor (recommended cap) */
#define RP2040_BENCH_TXPOW_MAX_DBM         22   /* 0..+22 dBm after outdoor unlock     */
#define RP2040_BENCH_OUTDOOR_PIN      2026UL

#define RP2040_BENCH_LEN_MAX_LORA     255
#define RP2040_BENCH_LEN_MAX_FLRC     511

#define RP2040_BENCH_TX_TIMEOUT_US  5000000UL  /* per-packet TX backstop (5 s) */

/* ---- Radio configuration (mirrors E80 radio_bench_cfg_t, portable subset) -- */

typedef struct
{
    uint8_t  mod;        /* BENCH_MOD_LORA / BENCH_MOD_FLRC      */
    uint8_t  sf;         /* LoRa spreading factor 5..12          */
    uint32_t bw_hz;      /* LoRa bandwidth Hz (125k/250k/500k)   */
    uint32_t br_bps;     /* FLRC bitrate bit/s (§8 enum)         */
    uint8_t  cr;         /* LoRa CR denominator 5..8; FLRC 1 (3/4) */
    int8_t   txpow_dbm;  /* TX power dBm (PA-capped)             */
    uint32_t freq_hz;    /* RF frequency Hz                      */
} bench_cfg_t;

/* ---- Radio operations seam --------------------------------------------------
 * Implemented on-target by bench_radio_sx1280 (v4 raw-SPI lift); faked in the
 * host tests. The core never touches SPI directly.
 */
typedef struct bench_radio_ops_s
{
    /** Full v4-style reconfigure: reset, standby, pkt type, freq, RX path,
     *  calibrate, mod params, sync word, packet params (FIX_LEN = len),
     *  PA config, TX params, IRQ mask. Used on ROLE/MOD/FREQ/START. */
    void (*reset_configure)(const bench_cfg_t* cfg, uint16_t len);

    /** Rewrite the FLRC/LoRa packet-params length window and re-arm RX
     *  (STANDBY -> 0x0249 len -> CLEAR_FIFO -> SET_RX continuous). */
    void (*rearm_rx)(const bench_cfg_t* cfg, uint16_t len);

    /** Blocking TX of one packet: CLEAR_ERRORS/IRQ/TXFIFO -> WRITE_TX_FIFO
     *  -> SET_TX -> wait BUSY-low (TX_DONE). Returns true on TX_DONE,
     *  false on the 500 ms air-time guard timeout. */
    bool (*tx_packet)(const uint8_t* payload, uint16_t len);

    /** Standby RC (park the radio, PA unkeyed). */
    void (*standby_rc)(void);

    /** Cold sleep (wake only via hardware reset / reconfigure). */
    void (*sleep_now)(void);

    /** True after sleep_now() until the next reconfigure. */
    bool (*is_asleep)(void);
} bench_radio_ops_t;

/* ---- Console / clock / binary-phase seam ----------------------------------- */

typedef struct bench_io_s
{
    /** Append a NUL-terminated string to the console (chunk-sized writes). */
    void (*put)(const char* s);
    /** Monotonic microseconds (wraps at 2^32). */
    uint32_t (*micros)(void);
    /** Binary BUF LOAD phase byte source: one byte 0..255, or -1 when none
     *  arrives within @p timeout_ms. Drives the 1.0 s idle-timeout rule. */
    int (*getchar_ms)(uint16_t timeout_ms);
    /** Radio operations (never NULL after bench_rp2040_init). */
    const bench_radio_ops_t* radio;
} bench_io_t;

/* ---- Core API --------------------------------------------------------------- */

/** Bind seams + reset to power-on state (role NONE, indoor PA cap, PRBS ON).
 *  Emits nothing; the caller prints the boot banner. */
void bench_rp2040_init(const bench_io_t* io, const char* fw_sha7);

/** Feed one console line (no CRLF; case-insensitive parser strips blanks). */
void bench_rp2040_feed_line(const char* line);

/** Poll: TX burst pacing (gap_us), TX timeout backstop, binary-phase timeout.
 *  Call from the main loop with the radio events already serviced. */
void bench_rp2040_poll(void);

/** Feed one RX radio event (per packet, CRC-failed or not). Emits the PKT
 *  line and folds the packet into the STAT? accumulators.
 *  rssi_half_dbm: RSSI in 0.5 dBm units (dBm*2). snr_qdb: 0.25 dB units
 *  (0 for FLRC). payload may be NULL when crc_ok == 0 (nothing is read). */
void bench_rp2040_rx_event(const uint8_t* payload, uint16_t len,
                           int16_t rssi_half_dbm, int8_t snr_qdb, bool crc_ok);

/** Golden self-test (spec §4/§5 vectors: PRBS fill bytes, 32-B pcrc16 pairs,
 *  CRC-16/CCITT-FALSE triples). Returns true when all vectors pass; the
 *  caller reports the result at boot / on SELFTEST? (currently boot only). */
bool bench_rp2040_selftest_golden(void);

/* Introspection for the firmware glue / tests. */
const bench_cfg_t* bench_rp2040_cfg(void);
bool bench_rp2040_role_is_rx(void);
uint16_t bench_rp2040_rx_len(void);
bool bench_rp2040_binary_active(void);

#ifdef __cplusplus
}
#endif

#endif /* RP2040_BENCH_H */
