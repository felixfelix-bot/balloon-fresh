/*
 * bootsel_controller.h — ESP32-C3 -> RP2040 BOOTSEL / RUN control core.
 *
 * Pure logic, no Arduino headers: the same object code is compiled for the
 * ESP32-C3 (firmware/esp32-bootsel-controller) and for the host unit tests
 * (test/ser_io_host.cpp), so the pin sequence and the command parser that ship
 * to the board are the ones under test.
 *
 * Wiring (DIRECT WIRE, NO SERIES RESISTORS — see the
 * esp32-rp2040-bootsel-control skill for why 1k series resistors put the pad in
 * the 1.65 V no-man's-land):
 *
 *   ESP32-C3 GPIO1 (D1) --> RP2040 RUN  button pad (3V3 signal side)
 *   ESP32-C3 GPIO8 (D8) --> RP2040 GP0  button pad (3V3 signal side)
 *   ESP32-C3 GND        --> RP2040 GND
 *
 * RP2040 boot pin truth (get this backwards and nothing works):
 *   RUN LOW  = hold the RP2040 in reset (active LOW), needs >= 1 us, 100 ms proven
 *   GP0  LOW = "boot from USB bootloader" selected, sampled during early boot
 *
 * Verified entry sequence (all four steps, in this order):
 *   1. GP0 LOW            bootloader mode selected
 *   2. hold  BOOTSEL_DELAY_SETTLE_MS
 *   3. RUN LOW            reset the RP2040 while GP0 is held LOW
 *   4. hold  BOOTSEL_DELAY_RUN_LOW_MS
 *   5. RUN HIGH           release reset -> RP2040 boots into BOOTSEL
 *   6. hold  BOOTSEL_DELAY_SAMPLE_MS  (RP2040 samples GP0 in early boot)
 *   7. GP0 HIGH           internal pull-up keeps it HIGH
 * -> RP2040 enumerates as RPI-RP2 mass storage (USB 2e8a:0003)
 */
#ifndef BOOTSEL_CONTROLLER_H
#define BOOTSEL_CONTROLLER_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ---- pin map ---------------------------------------------------------- */
#define BOOTSEL_GPIO_RUN     1u  /* GPIO1 / D1 -> RP2040 RUN  (reset, active LOW) */
#define BOOTSEL_GPIO_BOOTSEL 8u  /* GPIO8 / D8 -> RP2040 GP0  (BOOTSEL, active LOW) */

/* GPIO8 is an ESP32-C3 strapping pin: it is sampled at power-on, so the target
 * must not hold it LOW while the ESP32 itself is booting. On the flight board
 * GP0 idles HIGH (internal pull-up), which is the safe level. */
#define BOOTSEL_STRAPPING_PIN_NOTE "GPIO8 is an ESP32-C3 strapping pin; target must idle HIGH at ESP32 power-on"

/* ---- sequence timing (milliseconds) ----------------------------------- */
#define BOOTSEL_DELAY_SETTLE_MS  50u   /* GP0 LOW -> RUN LOW                        */
#define BOOTSEL_DELAY_RUN_LOW_MS 100u  /* RUN held LOW                              */
#define BOOTSEL_DELAY_SAMPLE_MS  500u  /* GP0 held LOW through the RP2040's early boot */

/* ---- watchdog --------------------------------------------------------- */
#define BOOTSEL_WD_DEFAULT_MS 8000u    /* RP2040 silent for this long -> reset it   */
#define BOOTSEL_WD_MIN_MS     1000u

/* ---- state ------------------------------------------------------------ */
typedef struct {
    bool     run_high;          /* last commanded RUN level (true = HIGH = 3V3)     */
    bool     bootsel_high;      /* last commanded GP0 level                         */
    uint32_t bootsel_events;    /* completed force-entry sequences                  */
    uint32_t run_pulses;        /* completed RUN pulses                             */
    bool     watchdog_enabled;  /* default OFF: the shipped UART bridge is separate  */
    uint32_t watchdog_ms;       /* silence threshold                                */
    uint32_t last_rp_hb_ms;     /* last RP2040 heartbeat (virtual/real millis)       */
    bool     have_rp_hb;        /* false = no liveness evidence yet, watchdog idles  */
    bool     wd_fired;          /* one recovery per loss-of-liveness episode        */
    uint32_t wd_triggers;       /* completed automatic recoveries                   */
} bootsel_state_t;

/* ---- platform hooks (implemented per target, recorded on host) -------- */
void bootsel_platform_delay_ms(uint32_t ms);
void bootsel_platform_write_run(bool high);
void bootsel_platform_write_bootsel(bool high);
void bootsel_platform_print(const char *text);

/* ---- API -------------------------------------------------------------- */
/* Initialise: both pins are driven HIGH before anything else, so the RP2040 is
 * out of reset and booting from flash while the ESP32 comes up. */
void bootsel_init(bootsel_state_t *s);

/* RUN LOW for BOOTSEL_DELAY_RUN_LOW_MS, then HIGH. RP2040 restarts with its
 * existing flash image — this is the flight-critical hardware watchdog action. */
void bootsel_pulse_run(bootsel_state_t *s);

/* Full verified sequence above: RP2040 ends up in USB bootloader mode. */
void bootsel_force_entry(bootsel_state_t *s);

/* RP2040 liveness: called for every heartbeat line the bridge/host forwards. */
void bootsel_note_rp_heartbeat(bootsel_state_t *s, uint32_t now_ms);

/* True when the RP2040 has gone silent past the threshold and the latch is armed. */
bool bootsel_watchdog_due(const bootsel_state_t *s, uint32_t now_ms);

/* Run the watchdog: on silence, pulse RUN (reset, not BOOTSEL — an RP2040 in
 * bootloader mode at altitude is unrecoverable) and latch until the next HB. */
bool bootsel_watchdog_tick(bootsel_state_t *s, uint32_t now_ms);

/* One-line status for the `s` command / host watcher. */
void bootsel_status_line(const bootsel_state_t *s, uint32_t now_ms,
                         char *out, size_t out_len);

/* Execute one command line. Returns the ack/echo text to print ("" = silent).
 * The returned pointer is a module-static buffer, valid until the next call.
 *
 *   r | reset            reset the RP2040 (RUN pulse)
 *   b | bootsel          force RP2040 USB bootloader mode
 *   s | status           status line
 *   w | watchdog on|off  enable/disable the heartbeat watchdog
 *   h | hb               note an RP2040 heartbeat at now_ms
 *   anything else        "ERR unknown command"
 */
const char *bootsel_apply_line(bootsel_state_t *s, const char *line, uint32_t now_ms);

#ifdef __cplusplus
}
#endif
#endif /* BOOTSEL_CONTROLLER_H */
