/**
 * @file    multi_radio_bench_console.cpp
 * @brief   RP2040BENCH console firmware main (HARM-T5).
 *
 * Wires the host-testable console core (src/bench/rp2040_bench.c — vendored
 * E80 trio + role state machine, BENCH-CONSOLE-SPEC §11) to the board:
 *
 *   - USB CDC console line pump (line buffer 128 >= 104 chars, spec §11.4)
 *   - bench_io_t seams: put() -> Serial (chunk-sized writes already),
 *     micros(), BUF LOAD binary-phase byte source (core owns the 1.0 s rule)
 *   - bench_radio_sx1280 ops + IRQ service pump (v4 raw-SPI lift, NOT
 *     modified: rfWriteCmd/rfSetRx/rfReadRxFifo/GET_*_PACKET_STATUS; FLRC
 *     511 B + Match123 0x7C + 16-bit chip len per harmonization golden §8)
 *
 * loop(): console -> radio IRQ service -> core poll (TX pacing, TX-TIMEOUT
 * backstop, binary-phase timeout). BOOT: golden self-test result printed
 * (spec §11.3 requires the vectors to pass on-target).
 *
 * Flash policy: HARM-T8 owns board flashing — build-verify only.
 */

#include <Arduino.h>

#include "bench/rp2040_bench.h"
#include "bench_radio_sx1280.h"

#ifndef SERIAL_BAUD
#define SERIAL_BAUD 115200
#endif
#ifndef FW_GIT_HASH
#define FW_GIT_HASH "0000000"
#endif
#ifndef FW_BUILD_TIME
#define FW_BUILD_TIME "1970-01-01T00:00Z"
#endif

/* ---- bench_io_t seams ------------------------------------------------------- */

static void io_put(const char* s) { Serial.write(s); }

static uint32_t io_micros(void) { return micros(); }

/** Binary-phase byte source. Blocks up to timeout_ms (core passes its own
 *  1.0 s idle rule); used only during BUF LOAD so loop() stalling is fine. */
static int io_getchar_ms(uint16_t timeout_ms)
{
    const uint32_t deadline = millis() + timeout_ms;
    for (;;) {
        const int c = Serial.read();     /* -1 when empty */
        if (c >= 0) return c;
        if ((int32_t)(millis() - deadline) >= 0) return -1;
        delayMicroseconds(100);
    }
}

static const bench_io_t bench_io = {
    io_put,
    io_micros,
    io_getchar_ms,
    &bench_radio_sx1280_ops,
};

/* ---- Console line pump ------------------------------------------------------ */

static char lineBuf[128];   /* spec §11.4: >= 104 chars */
static size_t lineLen = 0;

static void feedConsoleByte(char c)
{
    if (c == '\r') return;
    if (c == '\n') {
        lineBuf[lineLen] = 0;
        bench_rp2040_feed_line(lineBuf);
        lineLen = 0;
        return;
    }
    if (lineLen + 1 < sizeof lineBuf) lineBuf[lineLen++] = c;
    /* Overflow: silently drop (host tools must not exceed 104 chars/line). */
}

/* ---- Arduino entry points --------------------------------------------------- */

void setup()
{
    Serial.begin(SERIAL_BAUD);
    /* CDC enumeration can take ~2 s; host tools wait for the banner, but
     * never hang forever on a bench rig powered without USB. */
    const uint32_t t0 = millis();
    while (!Serial && millis() - t0 < 3000) delay(10);

    bench_radio_sx1280_begin();          /* pins + SPI bus               */
    bench_rp2040_init(&bench_io, FW_GIT_HASH);

    Serial.write("\r\n" RP2040_BENCH_BOARD_NAME " console "
                 RP2040_BENCH_FW_VERSION " fw=" FW_GIT_HASH
                 " build=" FW_BUILD_TIME "\r\n");
    Serial.write(bench_rp2040_selftest_golden()
                     ? "GOLDEN SELFTEST PASS (prbs + pcrc16 + crc16, spec 4/5)\r\n"
                     : "GOLDEN SELFTEST FAIL\r\n");
    Serial.write("ready\r\n");
}

void loop()
{
    while (Serial.available())
        feedConsoleByte((char)Serial.read());

    bench_radio_sx1280_service();        /* IRQ -> bench_rp2040_rx_event */
    bench_rp2040_poll();                 /* TX pacing + backstops        */
}
