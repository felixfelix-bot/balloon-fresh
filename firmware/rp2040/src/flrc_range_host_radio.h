/**
 * @file    flrc_range_host_radio.h
 * @brief   FW-5a: LR2021 radio backend TX — band matrix + init/reinit
 *          command sequences + chip TX timeout ticks.
 *          FW-5b: RX side — continuous-RX arm sequence, FIX-3 IRQ
 *          classification, packet read, and FLRC/LoRa packet-status
 *          RSSI/SNR assembly with the minor-2 int8-wrap fix.
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
 * FW-5b RX provenance (task t_41b23f6c):
 *   - startReceive / SET_RX ... src/flrc_range_rx_sweep.cpp rfSetRx()
 *                              ({02 0C FF FF FF} — 5 bytes, extra byte is
 *                              a CMD_ERROR) + runReceive() pre-arm
 *   - FIX-3 IRQ discipline .... src/flrc_range_rx_v2.cpp L388-445: read +
 *                              classify IRQ status, and on EVERY path
 *                              (RX_DONE / CRC error / other) drain the
 *                              FIFO + clear IRQ + re-arm SET_RX
 *   - RX DIO wiring ........... src/flrc_range_rx_v2.cpp L316
 *                              ({01 15 09 00 04 00 00} = RX_DONE bit18
 *                              -> DIO9; full_init wires TX_DONE bit19)
 *   - FLRC packet status ...... src/flrc_range_rx_sweep.cpp L158-180:
 *                              GET_FLRC_PACKET_STATUS 0x024B, 7 phase-2
 *                              bytes, 9-bit raw = (b[4]<<1)|(b[6].bit2)
 *   - LoRa packet status ...... GET_PACKET_STATUS 0x022A — NOT in the
 *                              raw-SPI corpus; bound to the vendored
 *                              lr20xx_driver lr20xx_radio_lora_get_packet_
 *                              status() (+ E80 radio_bench.c L387-396): 8
 *                              phase-2 bytes, rssi = -(int16)b[5], snr =
 *                              signed b[4] quarter-dB, len = b[3]. Driver
 *                              rbuffer = phase-2 read minus the 2 status
 *                              bytes (verified against the FLRC 0x024B
 *                              mapping above).
 *   - Instantaneous RSSI ...... src/flrc_range_rx_sweep.cpp L182-204:
 *                              GET_RSSI_INST 0x020B, 2 phase-2 bytes,
 *                              9-bit raw = (b[0]<<1)|(b[1]>>7)
 *
 * Known provenance delta (deliberate, REV-2 minor-2): rx_sweep/v2 return
 * -(int8_t)(raw/2), which WRAPS POSITIVE once raw/2 > 127 (9-bit RSSI
 * reaches -255.5 dBm). This module computes in int16 and clamps to
 * [-127, 0] so BENCH_RADIO_RSSI_INVALID (-128) stays a clean sentinel.
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

/* ---- RX frames + packet-status assembly (FW-5b, pure) --------------------- */

/* SET_RX {02 0C t23..16 t15..8 t7..0} — 5 bytes total, NOT 6 (an extra
 * byte is a CMD_ERROR; rx_sweep rfSetRx). startReceive provenance is the
 * continuous listen: 0xFFFFFF timeout, host STOP ends the session. */
#define BENCH_RADIO_RX_CONTINUOUS_TICKS 0xFFFFFFUL
void bench_radio_set_rx_bytes(uint32_t timeout_ticks, uint8_t out[5]);

/* CLEAR_RX_FIFO {01 1E} (TX counterpart 0x011F — rfClearTxFifo). */
void bench_radio_clear_rx_fifo_bytes(uint8_t out[2]);

/* DIO9 line wiring via CFG_DIO_IRQ: RX maps RX_DONE (bit 18), TX maps
 * TX_DONE (bit 19). full_init/reinit leave the line on TX_DONE, so an RX
 * session must re-map on entry (and TX must restore it — done lazily in
 * bench_radio_send_packet). */
void bench_radio_rx_dio_irq_bytes(uint8_t out[7]);
void bench_radio_tx_dio_irq_bytes(uint8_t out[7]);

/* startReceive arm sequence (v2 FIX-3 pre-arm + RX DIO remap):
 *   DIO remap -> CLEAR_IRQ -> CLEAR_RX_FIFO -> SET_RX continuous
 * (4 frames). */
void bench_radio_emit_start_rx(bench_radio_cmd_sink_t sink, void *user);

/* IRQ status bits (flrc_range_rx_v2.cpp FIX-3 classification). */
#define BENCH_RADIO_IRQ_RX_DONE 0x00040000UL
#define BENCH_RADIO_IRQ_CRC_ERR 0x00200000UL

/* No-reading sentinel: -128 = none / UNCALIBRATED (REV-2 minor-2). */
#define BENCH_RADIO_RSSI_INVALID ((int8_t)-128)

typedef enum {
    BENCH_RX_IRQ_NONE = 0,
    BENCH_RX_IRQ_PKT_OK,  /* RX_DONE without CRC error */
    BENCH_RX_IRQ_CRC_ERR, /* CRC error — wins over RX_DONE (v2 order) */
    BENCH_RX_IRQ_OTHER,   /* anything else: timeout, spurious, ... */
} bench_rx_irq_class_t;

/* FIX-3 classification order: CRC error first, then RX_DONE, else OTHER. */
bench_rx_irq_class_t bench_radio_classify_rx_irq(uint32_t irq_status);

/* FLRC GET_FLRC_PACKET_STATUS 0x024B — the full 7 phase-2 bytes
 * [stat_msb stat_lsb len_msb len_lsb rssiAvg rssiSync flags].
 * 9-bit assembly: raw9 = (b[4]<<1) | b[6].bit2, rssi = -raw9/2 computed
 * in int16 and clamped to [-127, 0] (minor-2 wrap fix). len = 16-bit
 * pktLen field. */
int8_t bench_radio_flrc_rssi_dbm(const uint8_t pkt_status[7]);
uint16_t bench_radio_flrc_pkt_len(const uint8_t pkt_status[7]);

/* LoRa GET_PACKET_STATUS 0x022A — the full 8 phase-2 bytes
 * [stat_msb stat_lsb crc/cr len snr rssi rssi_signal flags].
 * rssi = -(int16)b[5] clamped to [-127, 0]; snr = signed b[4] in
 * quarter-dB; len = b[3] (explicit-header payload length). */
int8_t bench_radio_lora_rssi_dbm(const uint8_t pkt_status[8]);
int8_t bench_radio_lora_snr_qdb(const uint8_t pkt_status[8]);
uint8_t bench_radio_lora_pkt_len(const uint8_t pkt_status[8]);

/* GET_RSSI_INST 0x020B — [rssiMsb rssiLsb], 9-bit raw9 = (b[0]<<1) |
 * (b[1]>>7), rssi = -raw9/2 with the same wrap fix. */
int8_t bench_radio_rssi_inst_dbm(const uint8_t resp[2]);

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
 * line fired within the spin budget. If the last operation was RX, the
 * DIO9 map is lazily restored to TX_DONE first. */
bool bench_radio_send_packet(const bench_radio_cfg_t *cfg,
                             const uint8_t *pkt, uint16_t len);

/* ---- RX hardware (FW-5b) -------------------------------------------------- */

/* One serviced RX event: len = payload bytes copied into the caller's
 * buffer (PKT_OK only), rssi_dbm = BENCH_RADIO_RSSI_INVALID when not
 * read, snr_qdb LoRa-only (0 for FLRC). */
typedef struct {
    bench_rx_irq_class_t irq_class;
    uint16_t len;
    int8_t   rssi_dbm;
    int8_t   snr_qdb;
} bench_rx_event_t;

/* Arm continuous RX: emit_start_rx over SPI (re-maps DIO9 to RX_DONE). */
void bench_radio_start_rx(void);

/* STOP semantics (REV-2): leave RX -> STDBY_RC {02 00 01}. */
void bench_radio_standby(void);

/* Instantaneous RSSI (noise-floor sampling; no packet needed). */
int8_t bench_radio_read_rssi_inst(void);

/* One RX service step for the FW-8 poll loop — call when the IRQ line is
 * high, or on a tick to self-heal. Reads+clears IRQ status, classifies
 * (FIX-3 order), and on PKT_OK reads packet status (FLRC 0x024B / LoRa
 * 0x022A per cfg->mod) then READ_RX_FIFO(len). On EVERY path (PKT_OK /
 * CRC_ERR / OTHER) it ends with CLEAR_RX_FIFO + CLEAR_IRQ + SET_RX
 * re-arm, so a serviced-but-undrained FIFO can never stall the chain. */
bench_rx_event_t bench_radio_rx_service(const bench_radio_cfg_t *cfg,
                                        uint8_t *buf, uint16_t buf_cap);

#endif /* !BENCH_RADIO_HOST_TEST */

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* FLRC_RANGE_HOST_RADIO_H */
