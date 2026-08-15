/**
 * @file    bench_safety.h
 * @brief   TX-hang watchdog math: LR2021 chip TX timeout, superloop backstop,
 *          STM32 IWDG prescaler arithmetic.
 *
 * Portable (no STM32/radio dependency): compiled into both the firmware and
 * the host unit tests. All values are worst-case UPPER bounds — a TX hang
 * detector must never fire on a legal packet.
 *
 * Background (consultant finding 2026-08-16): the two-step ROLE TX + ARM TX
 * guards BOOT only. A hang while armed (IRQ lost, BUSY stuck, pacing bug)
 * keys the PA indefinitely. Three layered defenses close that hole:
 *
 *   1. LR2021 chip TX timeout — set_tx(timeout_ms): the RADIO itself leaves
 *      TX (fallback STDBY_RC, PA unkeyed) even if the host MCU is wedged,
 *      and raises the TIMEOUT IRQ.
 *   2. Superloop backstop — if the TX_DONE/TIMEOUT IRQ never arrives (EXTI
 *      lost), bench_micros()-based detector force-aborts the burst.
 *   3. STM32 IWDG — if the superloop itself hangs (e.g. BUSY-stuck spin in
 *      the SPI critical section), the independent LSI watchdog resets the
 *      MCU; the boot banner then prints 'WDG RESET'.
 */

#ifndef E80_BENCH_SAFETY_H
#define E80_BENCH_SAFETY_H

#include <stdint.h>
#include <stdbool.h>

#include "bench_cmd.h" /* bench_mod_t */

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
 * params in radio_bench.c (FIX_LEN, SYNCWORD_LENGTH_4_BYTES, CRC_2_BYTES). */
uint32_t bench_safety_flrc_airtime_us(uint32_t br_bps, uint16_t len);

/* Chip TX timeout in ms for the active config: 2x worst-case airtime + 50 ms
 * ramp/IRQ slack, clamped to [100, 60000] ms. 60 s cap keeps the vendored
 * driver's ms->RTC-step conversion (ms * 32768 / 1000, uint32, overflow at
 * 131,072 ms) and the 24-bit SetTx timeout register (max 512 s) happy.
 * Never fires on a legal packet (100% margin); always fires on a hang. */
uint32_t bench_safety_tx_timeout_ms(bench_mod_t mod, uint8_t sf, uint32_t bw_hz,
                                    uint32_t br_bps, uint16_t len);

/* ---- Defense 2: superloop backstop (host-side TX-hang detector) ------------ */

/* Backstop window in us: chip timeout + 100% + 50 ms. If no TX_DONE/TIMEOUT
 * IRQ is serviced within this window after a packet start, the burst is
 * force-aborted regardless of radio state. */
uint32_t bench_safety_tx_backstop_us(uint32_t tx_timeout_ms);

/* Wraparound-safe elapsed compare against the backstop window. */
bool bench_safety_tx_backstop_fired(uint32_t t_tx_start_us, uint32_t now_us,
                                    uint32_t tx_timeout_ms);

/* ---- Defense 3: STM32 IWDG prescaler math ----------------------------------- */

/* IWDG timeout in ms (ceiling) for PR register value 0..6 (divider 4*2^pr),
 * reload 0..4095 and LSI frequency in Hz:
 *   t = ceil((reload+1) * (4 << pr) * 1000 / lsi_hz)
 * No 64-bit math needed: worst case 4096 * 256 * 1000 < 2^32. */
uint32_t bench_safety_iwdg_timeout_ms(uint8_t iwdg_pr, uint16_t reload,
                                      uint32_t lsi_hz);

/* Bench IWDG choice: PR=4 (HAL IWDG_PRESCALER_64, divider 64), reload 1874.
 * F103 LSI is specified 30-60 kHz (typ. 40 kHz, the HAL default LSI_VALUE):
 *   40 kHz -> 3.000 s nominal window
 *   60 kHz -> 2.000 s (fastest LSI, still above 2 s)
 *   30 kHz -> 4.000 s (slowest LSI, still below 4 s)
 * The superloop is fully non-blocking (no HAL delay waits), so a healthy
 * loop kicks it thousands of times per window. */
#define BENCH_IWDG_PR_REG 4u   /* IWDG_PRESCALER_64 */
#define BENCH_IWDG_RELOAD 1874u

#ifdef __cplusplus
}
#endif

#endif /* E80_BENCH_SAFETY_H */
