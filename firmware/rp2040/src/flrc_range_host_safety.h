/**
 * @file    flrc_range_host_safety.h
 * @brief   TX-hang watchdog math: LR2021 chip TX timeout, superloop backstop,
 *          RP2040 SDK watchdog budget, EU-band check, PA-cap check.
 *
 * Portable (no Arduino/RP2040 SDK dependency): compiled into both the
 * firmware and the host unit tests. All airtime/timeout values are
 * worst-case UPPER bounds — a TX hang detector must never fire on a legal
 * packet.
 *
 * Three layered defenses (B3 resolution — REV-2 binding):
 *
 *   1. LR2021 chip TX timeout — set_tx(timeout_ms): the RADIO itself leaves
 *      TX (fallback STDBY_RC, PA unkeyed) even if the host MCU is wedged,
 *      and raises the TIMEOUT IRQ.
 *   2. SDK watchdog budget — RP2040 SDK watchdog_enable(ms) caps at 8388 ms
 *      internally; we clamp to 8000 ms.  This is a SUPERLOOP-WEDGE catcher
 *      ONLY: it is fed between packets (watchdog_update() on IRQ).  Long
 *      airtimes (e.g. SF12 BW125 LEN=255 ~9s) are covered by defense-1,
 *      NOT by this watchdog.  wdt_budget = min(requested, 8000).
 *   3. Superloop backstop — if the TX_DONE/TIMEOUT IRQ never arrives, a
 *      micros()-based detector force-aborts the burst.
 *
 * Port provenance: ~/repos/balloon-e80bench/firmware/e80-stm32-bench/src/bench_safety.h
 * Changes vs E80:
 *   - DROPPED: STM32 IWDG prescaler math (RP2040 uses SDK watchdog_enable
 *     directly — no prescaler/reload arithmetic).
 *   - DROPPED: FLASH bootloader-jump plan (RP2040 has picotool BOOTSEL).
 *   - ADDED:   bench_safety_wdt_budget_ms (SDK 8388 cap, clamp to 8000).
 *   - ADDED:   bench_safety_freq_in_eu_band (EU SRD 863-870 MHz, hard clamp).
 *   - ADDED:   bench_safety_pa_allowed (LF cap +10 indoor / +22 outdoor-unlocked).
 */

#ifndef FLRC_RANGE_HOST_SAFETY_H
#define FLRC_RANGE_HOST_SAFETY_H

#include <stdint.h>
#include <stdbool.h>

#include "flrc_range_host_types.h" /* bench_mod_t */

#ifdef __cplusplus
extern "C" {
#endif

/* ---- Defense 1: LR2021 chip TX timeout (ms argument of set_tx) ------------- */

/* Worst-case LoRa airtime in us: Semtech AN1200.24 symbol formula for the
 * bench modem config (CR4/5, explicit header, CRC16, 8-symbol preamble).
 * The LR2021 LDRO setting is not explicitly controlled by this firmware, so
 * the LONGER of the LDRO on/off variants is used (safe upper bound).
 * Integer math in quarter-symbols, all divisions ceiling. */
uint32_t bench_safety_lora_airtime_us(uint8_t sf, uint32_t bw_hz, uint16_t len);

/* Worst-case FLRC airtime in us: 32-bit preamble + 32-bit syncword + payload
 * + 16-bit CRC, CR3/4-coded (x4/3), at br_bps. Matches the bench FLRC packet
 * params in the sweep firmware (FIX_LEN, SYNCWORD_LENGTH_4_BYTES, CRC_2_BYTES). */
uint32_t bench_safety_flrc_airtime_us(uint32_t br_bps, uint16_t len);

/* Chip TX timeout in ms for the active config: 2x worst-case airtime + 50 ms
 * ramp/IRQ slack, clamped to [100, 60000] ms. 60 s cap keeps the vendored
 * driver's ms->RTC-step conversion (ms * 32768 / 1000, uint32, overflow at
 * 131,072 ms) and the 24-bit SetTx timeout register (max 512 s) happy.
 * Never fires on a legal packet (100% margin); always fires on a hang. */
uint32_t bench_safety_tx_timeout_ms(bench_mod_t mod, uint8_t sf, uint32_t bw_hz,
                                    uint32_t br_bps, uint16_t len);

/* ---- Defense 2: SDK watchdog budget (superloop-wedge catcher) -------------- */

/* RP2040 SDK watchdog_enable() caps internally at 8388 ms.  We stay under
 * at 8000 ms.  This function returns min(requested_ms, 8000), so callers
 * can pass the chip TX timeout and get a safe wdt budget.  The watchdog is
 * FED between packets — it catches a wedged superloop, NOT a long packet. */
#define BENCH_WDT_BUDGET_CAP_MS 8000U
uint32_t bench_safety_wdt_budget_ms(uint32_t requested_ms);

/* ---- Defense 3: superloop backstop (host-side TX-hang detector) ------------ */

/* Backstop window in us: chip timeout + 100% + 50 ms. If no TX_DONE/TIMEOUT
 * IRQ is serviced within this window after a packet start, the burst is
 * force-aborted regardless of radio state. */
uint32_t bench_safety_tx_backstop_us(uint32_t tx_timeout_ms);

/* Wraparound-safe elapsed compare against the backstop window. */
bool bench_safety_tx_backstop_fired(uint32_t t_tx_start_us, uint32_t now_us,
                                    uint32_t tx_timeout_ms);

/* ---- EU SRD band check ----------------------------------------------------- */

/* EU SRD LF band: 863_000_000 .. 870_000_000 Hz (inclusive).  Hard clamp v1
 * — no override.  The protocol FREQ command rejects out-of-band with
 * ERR RANGE. */
#define BENCH_EU_BAND_LO_HZ  863000000U
#define BENCH_EU_BAND_HI_HZ 870000000U
bool bench_safety_freq_in_eu_band(uint32_t freq_hz);

/* ---- PA power-cap check ---------------------------------------------------- */

/* LF path PA limits: +10 dBm indoor (default), +22 dBm outdoor (unlocked).
 * The unlock requires prior `POWER MODE OUTDOOR 2026` (pin==2026).
 * dbm range: -18..+22 (protocol rejects < -18 with ERR RANGE).
 * This function checks only the power-cap given the unlock state. */
#define BENCH_PA_MIN_DBM       (-18)
#define BENCH_PA_INDOOR_CAP_DBM  10
#define BENCH_PA_OUTDOOR_CAP_DBM 22
bool bench_safety_pa_allowed(int8_t dbm, bool outdoor_unlocked);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* FLRC_RANGE_HOST_SAFETY_H */