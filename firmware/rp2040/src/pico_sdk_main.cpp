/*
 * pico_sdk_main.cpp — minimal pico-sdk entry point for the PIO+DMA gapless RX
 * engine (SPEED-P6).
 *
 * The Arduino wiring (radio.cpp + main.cpp) builds under the mbed Arduino core
 * via PlatformIO (platformio.ini). This thin main is the pico-sdk CMake build's
 * entry point so that `cmake .. && make` produces a self-contained .uf2 that
 * loads the LR2021 SPI PIO program, claims the DMA channels, and idles in a
 * packet-poll loop — proving the engine links and runs under pico-sdk.
 *
 * Build:
 *   cd firmware/rp2040 && mkdir build && cd build
 *   cmake -DPICO_SDK_PATH=<sdk> ..
 *   make -j
 *   # -> pio_rx_smoketest.uf2
 */

#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/gpio.h"
#include "pio_lr2021_rx.h"

/* Pin map mirrors pins.h (ADR-015). */
#define PIN_SCK   2
#define PIN_MOSI  3
#define PIN_MISO  4
#define PIN_CS    5
#define PIN_IRQ   7
#define PIN_LED   25

int main(void) {
    stdio_init_all();

    gpio_init(PIN_IRQ);
    gpio_set_dir(PIN_IRQ, GPIO_IN);
    gpio_init(PIN_LED);
    gpio_set_dir(PIN_LED, GPIO_OUT);

    int rc = lr2021_rx_init(PIN_SCK, PIN_MOSI, PIN_MISO, PIN_CS,
                            LR2021_RX_DEFAULT_CLK);
    if (rc != 0) {
        printf("PIO_RX init failed rc=%d\n", rc);
        while (true) { tight_loop_contents(); }
    }
    lr2021_rx_set_payload_len(255);
    printf("PIO_RX ready: SCK=%.2f MHz, 2-cycle/bit full-duplex SM, DMA ping-pong\n",
           LR2021_RX_DEFAULT_CLK);

    while (true) {
        /* On a DIO9 rising edge, arm a DMA capture; drain whatever finished. */
        if (gpio_get(PIN_IRQ) && !lr2021_rx_busy()) {
            lr2021_rx_arm();
        }
        const uint8_t *p = NULL;
        size_t n = 0;
        int slot = lr2021_rx_take(&p, &n);
        if (slot >= 0) {
            gpio_put(PIN_LED, 1);
            printf("rx slot=%d len=%u seq=%02X%02X%02X%02X (completed=%lu dropped=%lu)\n",
                   slot, (unsigned)n, p[0], p[1], p[2], p[3],
                   (unsigned long)lr2021_rx_completed_count(),
                   (unsigned long)lr2021_rx_dropped_count());
            gpio_put(PIN_LED, 0);
        }
        tight_loop_contents();
    }
    return 0;
}
