/**
 * @file    flrc_range_host_radio.h
 * @brief   FW-5a: LR2021 radio backend TX — band matrix + init/reinit
 *          command sequences + chip TX timeout ticks.
 *
 * Split design so the SAME sequence code runs in firmware and in host
 * unit tests:
 *
 *   - PURE (host-testable): band matrix lookup, FW-4 ms -> SetTx RTC-step
 *     ticks, FLRC bitrate table, TX power byte, and the two command-
 *     sequence builders (`bench_radio_emit_full_init` / `_reinit`).
 *     Builders write SPI command frames to a caller-supplied sink, so the
 *     tests assert exact wire bytes without hardware.
 *   - HARDWARE (compiled out under BENCH_RADIO_HOST_TEST): SPI transport,
 *     reset pulse, status verification, and the burst-spin TX path.
 *
 * Provenance (binding per REV-2 B1 / task t_75a5ad0e):
 *   - Cold-init backbone ..... src/flrc_range_tx_sweep.cpp rawInitRadio()
 *                              (reset pulse, 0x0111/0x0128 preamble,
 *                               clear-irq, status check)
 *   - Per-band init matrix ... src/dual_radio_gps_sweep_tx.cpp L497-602:
 *                              pkt type (FLRC=0x04 / LoRa=0x00), RX_PATH,
 *                              CALIB_FRONT_END (fe freq, |0x8000 HF-only),
 *                              CALIBRATE, MOD/PKT block, band matrix steps
 *   - SET_TX_PATH + PA select  src/multi_radio_sweep_gps_v4.cpp L786-793:
 *                              TX_PATH {02 02 <path> 00} and PA select byte
 *                              HF=0x80 / LF=0x00 [LR2021Raw.h
 *                              setPaConfig/setPaConfigLF]
 *   - Reinit skeleton ......... src/flrc_range_tx_sweep.cpp rfSwitchBitrate()
 *                              (STDBY -> MOD_PARAMS -> CALIBRATE -> CLEAR)
 *                              extended band-aware per REV-2 B1: "rfSwitch-
 *                              Bitrate() alone is INSUFFICIENT"
 *   - Burst spin .............. src/flrc_range_tx_sweep.cpp L378-398
 *   - ms->ticks ............... vendored lr20xx_driver
 *                              lr20xx_radio_common_convert_time_in_ms_to_
 *                              rtc_step(): ticks = ms * 32768 / 1000
 *
 * Band rule (B1): is_hf = freq_hz > 1.5 GHz. The sweep backend hardwires
 * the HF values (RX_PATH 0x01, FE|0x8000, PA select 0x80); every band-
 * dependent byte is parameterized here instead.
 *
 * Known provenance deltas (deliberate, see docs/evidence/stage-a/
 * fw5a-radio-band-matrix.md):
 *   - Packet type: sweep TX/RX pair uses FLRC=0x05; dual_radio pair uses
 *     FLRC=0x04 ("proven" per in-file comment). B1 binds the matrix to
 *     dual_radio -> 0x04. TX/RX both run this backend, so the pair stays
 *     self-consistent.
 *   - PA select on LF: lora_868_tx.cpp uses 0x80 at 868 MHz, but B1 binds
 *     the v4 semantics (LF=0x00). Single-line change if HW-B2 disagrees.
 *   - TX power byte: sweep helper (uint8_t)(dbm*2.0f+0.5f) is a half-dB
 *     off for NEGATIVE integer dBm; this module uses exact dbm*2.
 */

#ifndef FLRC_RANGE_HOST_RADIO_H
#define FLRC_RANGE_HOST_RADIO_H

#include <stddef.h>
#include <stdint.h>

#include "flrc_range_host_types.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ---- Band matrix --------------------------------------------------------- */

/* HF threshold per B1: freq > 1.5 GHz means the 2.4 GHz front end. */
#define BENCH_RADIO_HF_THRESHOLD_HZ 1500000000UL

typedef struct
{
    uint8_t  is_hf;    /* 1 if freq_hz > threshold */
    uint8_t  rx_path;  /* SET_RX_PATH payload:  HF=0x01, LF=0x00 */
    uint8_t  tx_path;  /* SET_TX_PATH payload:  HF=0x01, LF=0x00 */
    uint8_t  pa_sel;   /* SET_PA_CONFIG byte2:  HF=0x80, LF=0x00 */
    uint16_t fe_freq;  /* CALIB_FRONT_END param: (freq_mhz/4)+0.5,
                          |0x8000 iff HF */
} bench_radio_band_params_t;

/* Band matrix lookup for an RF frequency in Hz. */
bench_radio_band_params_t bench_radio_band_for_freq(uint32_t freq_hz);

/* ---- Chip TX timeout (FW-4 integration) ---------------------------------- */

/* SetTx 24-bit timeout register cap (max ~512 s at 32768 Hz). */
#define BENCH_RADIO_TX_TIMEOUT_TICKS_MAX 0xFFFFFFUL

/* FW-4 chip-timeout ms -> SetTx RTC steps: ms * 32768 / 1000, clamped to
 * the 24-bit register. FW-4 outputs [100, 60000] ms always map non-zero —
 * set_tx therefore NEVER carries the sweep-fw continuous-TX 0x000000. */
uint32_t bench_radio_tx_timeout_ticks(uint32_t tx_timeout_ms);

/* SET_TX wire frame for a tick value: {02 0D t23..16 t15..8 t7..0}. */
void bench_radio_set_tx_bytes(uint32_t timeout_ticks, uint8_t out[5]);

/* ---- Small tables / helpers ---------------------------------------------- */

/* FLRC br_bw wire code for the 8 protocol rates (dual_radio table).
 * Sentinel for anything else — the protocol accepts no other rate. */
#define BENCH_RADIO_FLRC_BR_INVALID 0xFF
uint8_t bench_radio_flrc_br_to_code(uint16_t kbps);

/* SET_TX_PARAMS power byte: exact half-dB math for integer dBm
 * (two's-complement signed byte, e.g. -18 dBm -> 0xDC). */
uint8_t bench_radio_tx_power_byte(int8_t dbm);

/* ---- Radio configuration -------------------------------------------------- */

typedef struct
{
    bench_mod_t mod;          /* BENCH_MOD_FLRC / BENCH_MOD_LORA */
    uint32_t    freq_hz;      /* e.g. 868000000 (EU SRD only in protocol v1) */
    uint16_t    flrc_br_kbps; /* FLRC only: one of the 8 rates */
    uint8_t     lora_sf;      /* LoRa only: 5..12 */
    uint8_t     lora_bw_code; /* LoRa only: lr2021_bw_codes.h code */
    uint8_t     lora_cr;      /* LoRa only: 1..4 (CR4/5..4/8) */
    int8_t      dbm;          /* TX power (cap policy is FW-4's job) */
    uint16_t    pkt_len;      /* 1..255 */
    uint32_t    tx_timeout_ms;/* from bench_safety_tx_timeout_ms() (FW-4) */
} bench_radio_cfg_t;

/* Config sanity (FW-6 calls this before touching the radio):
 * FLRC needs a known rate; LoRa needs SF 5..12 + known BW code + CR 1..4;
 * both need pkt_len 1..255. */
bool bench_radio_cfg_valid(const bench_radio_cfg_t *cfg);

/* ---- Command sequence builders (pure; the testable seam) ------------------ */

/* SPI command sink: hand the frame to the transport; delay_ms_after is the
 * provenance inter-command delay the sweep firmware uses (hardware sink:
 * rfWriteCmd + delay(); test sink: record and assert). */
typedef void (*bench_radio_cmd_sink_t)(void *user, const uint8_t *cmd,
                                       size_t len, uint32_t delay_ms_after);

/* Cold full init: sweep backbone + dual_radio per-band matrix, ending in
 * CLEAR_IRQ (17 frames; hardware wrapper adds the reset pulse and the
 * status verification read). */
void bench_radio_emit_full_init(const bench_radio_cfg_t *cfg,
                                bench_radio_cmd_sink_t sink, void *user);

/* Band-aware reinit (REV-2 B1 replaces rfSwitchBitrate): STDBY ->
 * RX_PATH -> CALIB_FRONT_END (freq may have changed) -> MOD/PKT block ->
 * CALIBRATE -> TX_PATH -> PA select -> TX_PARAMS -> CLEAR (11 frames). */
void bench_radio_emit_reinit(const bench_radio_cfg_t *cfg,
                             bench_radio_cmd_sink_t sink, void *user);

/* ---- Hardware layer (firmware only) --------------------------------------- */

#ifndef BENCH_RADIO_HOST_TEST

/* SPI pins + transport (flrc_range_tx_sweep.cpp pin map). */
void bench_radio_hardware_begin(void);

/* Cold init with reset pulse + emit_full_init + status verify.
 * Returns the rawInitRadio() verdict: chip status/IRQ say the radio is
 * alive (STDBY/XOSC or any pending IRQ bit). */
bool bench_radio_full_init(const bench_radio_cfg_t *cfg);

/* Band-aware reinit of an already-initialized radio (no reset, no read). */
void bench_radio_reinit(const bench_radio_cfg_t *cfg);

/* Burst-spin TX of one packet (flrc_range_tx_sweep.cpp L378-398):
 * CLEAR_IRQ -> CLEAR_TX_FIFO -> WRITE_TX_FIFO -> SET_TX(ticks from
 * cfg->tx_timeout_ms) -> spin on the IRQ pin. Returns true if the IRQ
 * line fired within the spin budget. */
bool bench_radio_send_packet(const bench_radio_cfg_t *cfg,
                             const uint8_t *pkt, uint16_t len);

#endif /* !BENCH_RADIO_HOST_TEST */

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* FLRC_RANGE_HOST_RADIO_H */
