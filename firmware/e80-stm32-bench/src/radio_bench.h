/**
 * @file    radio_bench.h
 * @brief   LR2021 (E80 module) radio control for the bench firmware.
 *
 * Init/RX/TX sequences copied EXACTLY from the vendor E80_DEMO
 * (Core/Src/user_radio.c) which is the only reference known to bring the
 * module up correctly:
 *   reset -> clear errors -> DCDC + TCXO 2.2V/64000 steps -> LFCLK RC
 *   -> calibrate 0x7F -> DIO8 as IRQ -> pkt/mod params -> rf freq
 *   -> PA cfg (LF, duty 7, slices 6 for >550 MHz / 7 for 400-550 MHz)
 *   -> rx path LF -> tx_params RAMP_304_US -> fallback STDBY_RC
 */

#ifndef E80_RADIO_BENCH_H
#define E80_RADIO_BENCH_H

#include "main.h"
#include "bench_cmd.h"
#include "bench_stats.h"

#include "lr20xx_hal.h"
#include "lr20xx_system.h"
#include "lr20xx_regmem.h"
#include "lr20xx_radio_common.h"
#include "lr20xx_radio_common_types.h"
#include "lr20xx_radio_lora.h"
#include "lr20xx_radio_lora_types.h"
#include "lr20xx_radio_flrc.h"
#include "lr20xx_radio_flrc_types.h"
#include "lr20xx_radio_fifo.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Demo context string ("LR2021") - kept identical. */
extern const void* E80_CONTEXT;

typedef struct radio_bench_cfg_s
{
    bench_mod_t mod;       /* BENCH_MOD_LORA or BENCH_MOD_FLRC */
    uint8_t    sf;         /* LoRa SF 5..12 (demo default SF8)  */
    uint8_t    cr;         /* Coding rate. LoRa: denominator (5=4/5, 7=4/7). FLRC: register code (0=1/2, 1=3/4, 2=uncoded). */
    uint32_t   bw_hz;      /* LoRa BW (demo default 125 kHz)    */
    uint32_t   br_bps;     /* FLRC bitrate (bench default 650k) */
    int8_t     txpow_dbm;  /* PA setting in dBm (max 22)        */
    uint32_t   freq_hz;    /* RF frequency                      */
} radio_bench_cfg_t;

typedef enum rb_evt_type_e
{
    RB_EVT_NONE = 0,
    RB_EVT_RX_OK,
    RB_EVT_RX_CRC,
    RB_EVT_RX_TIMEOUT,
    RB_EVT_TX_DONE,
    RB_EVT_TX_TIMEOUT, /* LR2021 chip TX timeout: radio already fell back to
                        * STDBY (PA unkeyed); burst must be aborted */
    RB_EVT_RX_OTHER,
} rb_evt_type_t;

typedef struct rb_evt_s
{
    rb_evt_type_t type;
    uint16_t len;
    uint32_t seq;             /* TX sequence header (RX_OK only)  */
    int16_t  rssi_half_dbm;   /* RSSI in 0.5 dBm units (dBm*2)    */
    int8_t   snr_qdb;         /* 0.25 dB units, LoRa only         */
} rb_evt_t;

/** Full demo init sequence. Leaves radio in STDBY_RC, caches chip version.
 *  @return 0 ok, -1 on any driver error. */
int radio_bench_init(void);

/** Apply cfg: packet type + packet/mod params + syncword + freq + PA + tx params.
 *  Radio must be awake. @return 0 ok, -1 driver error. */
int radio_bench_apply_cfg(const radio_bench_cfg_t* cfg);

/** Demo radio_rx() sequence with continuous RX. Radio must be awake. */
int radio_bench_rx_arm(uint16_t rx_pld_len);

/** Demo radio_tx_custom() sequence for one packet, with a chip-level TX
 *  timeout (ms, see bench_safety_tx_timeout_ms). On overrun the LR2021
 *  raises the TIMEOUT IRQ and falls back to STDBY_RC (fallback mode set by
 *  apply_cfg), unkeying the PA even if the host MCU is wedged. Radio must
 *  be awake. */
int radio_bench_tx_packet(const uint8_t* buf, uint16_t len, uint32_t tx_timeout_ms);

/** Demo radio_sleep() (warm sleep, RAM retention). */
void radio_bench_sleep(void);

/** Demo radio_wakeup() (NSS glitch). */
void radio_bench_wakeup(void);

bool radio_bench_is_asleep(void);

/** Called from the DIO8 EXTI handler - demo radio_irq_callback() logic. */
void radio_bench_irq(void);

/** Non-blocking event mailbox poll (drained by the superloop).
 *  @return 1 when *evt was filled. */
int radio_bench_poll_event(rb_evt_t* evt);

/** Last received payload (valid right after RB_EVT_RX_OK) + its length. */
extern uint8_t radio_bench_rx_buf[E80_BENCH_MAX_PAYLOAD];
extern volatile uint16_t radio_bench_rx_buf_len;

/** Cached chip version (valid after radio_bench_init). */
extern volatile uint8_t radio_bench_chip_major;
extern volatile uint8_t radio_bench_chip_minor;

/** Number of IRQ events dropped because the superloop did not drain them. */
uint32_t radio_bench_evt_drops(void);

#ifdef __cplusplus
}
#endif

#endif /* E80_RADIO_BENCH_H */
