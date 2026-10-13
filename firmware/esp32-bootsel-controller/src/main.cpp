/*
 * main.cpp — ESP32-C3 test firmware: interactive RP2040 BOOTSEL/RUN controller.
 *
 * Answers the task's acceptance criteria:
 *   1. serial command interface   r=reset  b=bootsel  s=status  (w/h auxiliary)
 *   2. force RP2040 into USB bootloader mode            (b)
 *   3. heartbeat monitoring for automated recovery      (w on + h)
 *
 * The pin sequence, the parser and the watchdog all live in
 * bootsel_controller.cpp / .h and are compiled unchanged into the host test
 * binary (tests/src/ser_io_host.cpp) — what the suite exercises is what runs
 * here. The two control pins come from that header too (GPIO1 RUN, GPIO8 GP0):
 * this file owns only the console wiring.
 *
 * READ THIS BEFORE TRUSTING THE SERIAL PORT:
 * The ESP32-C3 SuperMini "USB JTAG/serial debug unit" (VID 303a:1001) has a
 * broken console. `Serial.print()` produces zero bytes and `Serial.available()`
 * never returns true on that interface — measured across 10+ reflashes and both
 * cores (see the esp32-rp2040-bootsel-control skill). The command interface
 * therefore also accepts the same commands from a hardware UART, which a
 * USB-serial adapter (or the RP2040's own UART bridge) can drive reliably.
 * Nothing here depends on USB CDC being alive:
 *
 *   Serial  = USB CDC/JTAG — opportunistic, may be dead (303a:1001)
 *   Serial1 = hardware UART — the console that actually works
 *
 * PIN CONFLICT — READ BEFORE USING THIS ON THE FLIGHT BOARD:
 * The defaults below (TX=GPIO21, RX=GPIO20) are the ESP32-C3's UART0 pins and
 * are free on the bench dev boards, but docs/FLIGHT-BOARD-AUTO-BOOTSEL.md
 * assigns BOTH to the BMP280 I2C bus. On the flight board either move the
 * console (the budget leaves GPIO0 free as UART TX) or leave the console to the
 * UART bridge and drive commands from there:
 *
 *   pio run -e esp32c3 --build-flag=-DBOOTSEL_UART_TX_PIN=0 \
 *                      --build-flag=-DBOOTSEL_UART_RX_PIN=<free pin>
 *
 * These two pins are the ONLY bench-specific choice in this firmware; the
 * BOOTSEL/RUN behaviour is pin-fixed in bootsel_controller.h because the
 * soldered circuit is wired to GPIO1/GPIO8.
 *
 * Commands (single letter or long alias; a trailing CR/LF is optional):
 *   r | reset    reset the RP2040 (RUN pulse) — flight-critical watchdog action
 *   b | bootsel  force RP2040 USB bootloader mode -> RPI-RP2 appears
 *   s | status   status line
 *   w on | w off heartbeat watchdog (default OFF, see below)
 *   h | hb       note an RP2040 heartbeat (for a host that forwards HB lines)
 * Commands are matched exactly: a line that merely starts with a command letter
 * is an error, because these commands move hardware.
 *
 * The watchdog defaults OFF because the shipped configuration runs the UART
 * bridge on this ESP32 and the RP2040's heartbeat reaches the host directly; a
 * second watchdog on a controller that cannot itself see the heartbeat would
 * reset the RP2040 on no evidence. Enable it when the controller is the node
 * that observes liveness: `w on`, then `h` (or a forwarded heartbeat) keeps it
 * quiet. On silence it pulses RUN only — never BOOTSEL: an RP2040 parked in the
 * bootloader at altitude has no USB host to send it a UF2 and is unrecoverable.
 *
 * Build:  pio run -e esp32c3            (see platformio.ini)
 * Flash:  python3 -m esptool --port /dev/ttyACMX --chip esp32c3 --baud 460800 \
 *           --before default_reset --after hard_reset write_flash 0x0 \
 *           firmware/esp32-bootsel-controller/.pio/build/esp32c3/firmware.bin
 * Do NOT set ARDUINO_USB_MODE / ARDUINO_USB_CDC_ON_BOOT — they break serial.
 */
#include <Arduino.h>

#include "bootsel_controller.h"

/* Console UART pins. Overridable per build (see the PIN CONFLICT note above);
 * bench defaults are the ESP32-C3's UART0 pins. */
#ifndef BOOTSEL_UART_TX_PIN
#define BOOTSEL_UART_TX_PIN 21
#endif
#ifndef BOOTSEL_UART_RX_PIN
#define BOOTSEL_UART_RX_PIN 20
#endif

#define UART_BAUD     115200
#define USB_BAUD      115200
#define HB_TICK_MS    1000   /* status/heartbeat cadence                          */
#define LINE_MAX      32

static bootsel_state_t g_state;
static char  g_line[LINE_MAX];
static size_t g_len = 0;
static uint32_t g_last_tick = 0;

/* ---- platform hooks (the only hardware-facing code in this firmware) --- */

void bootsel_platform_delay_ms(uint32_t ms) { delay(ms); }

void bootsel_platform_write_run(bool high)
{
    digitalWrite(BOOTSEL_GPIO_RUN, high ? HIGH : LOW);
}

void bootsel_platform_write_bootsel(bool high)
{
    digitalWrite(BOOTSEL_GPIO_BOOTSEL, high ? HIGH : LOW);
}

void bootsel_platform_print(const char *text)   /* not used: output is serial */
{
    (void)text;
}

/* ---- helpers ---------------------------------------------------------- */

static void say(const char *text)
{
    /* Best effort on both consoles: on a 303a:1001 board the USB CDC half of
     * this is a no-op, the UART half is what the host actually sees. */
    Serial.print(text);
    Serial.flush();
}

/* Drain one console into the command line. Returns true when a full line
 * (terminated by CR or LF) was assembled. */
static bool read_line_from(Stream &in)
{
    while (in.available() > 0) {
        int c = in.read();
        if (c < 0) break;
        if (c == '\r' || c == '\n') {
            if (g_len == 0) continue;   /* swallow bare CRLF */
            g_line[g_len] = '\0';
            g_len = 0;
            return true;
        }
        if (g_len + 1 < LINE_MAX) g_line[g_len++] = (char)c;
        /* An over-long line is truncated rather than dropped: for one-character
         * commands the first byte is the whole command, and dropping it would
         * leave the host waiting for an ack that never comes. */
    }
    return false;
}

static void handle_line(const char *line, uint32_t now)
{
    if (line[0] == '\0') return;
    const char *out = bootsel_apply_line(&g_state, line, now);
    if (out && out[0]) say(out);
}

void setup()
{
    /* Console first, so the board is talkative even if a GPIO change misbehaves
     * on this particular harness. */
    Serial.begin(USB_BAUD);
    Serial1.begin(UART_BAUD, SERIAL_8N1, BOOTSEL_UART_RX_PIN, BOOTSEL_UART_TX_PIN);

    bootsel_init(&g_state);

    char banner[160];
    snprintf(banner, sizeof banner,
             "\nBOOTSEL_CTRL_READY gpio_run=%u gpio_bootsel=%u uart_tx=%d uart_rx=%d baud=%d\n",
             (unsigned)BOOTSEL_GPIO_RUN, (unsigned)BOOTSEL_GPIO_BOOTSEL,
             (int)BOOTSEL_UART_TX_PIN, (int)BOOTSEL_UART_RX_PIN, UART_BAUD);
    say(banner);
    say("cmds: r=reset b=bootsel s=status w=watchdog h=hb\n");
}

void loop()
{
    const uint32_t now = millis();

    if (read_line_from(Serial))  handle_line(g_line, now);
    if (read_line_from(Serial1)) handle_line(g_line, now);

    if (bootsel_watchdog_tick(&g_state, now)) {
        char st[192];
        bootsel_status_line(&g_state, now, st, sizeof st);
        say("WATCHDOG_RESET rp2040 silent -> RUN pulse\n");
        say(st);
        say("\n");
    }

    if (now - g_last_tick >= HB_TICK_MS) {
        g_last_tick = now;
        char st[192];
        bootsel_status_line(&g_state, now, st, sizeof st);
        say(st);
        say("\n");
    }
}
