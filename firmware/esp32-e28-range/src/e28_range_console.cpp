/**
 * @file    e28_range_console.cpp
 * @brief   E28-2G4M27S (SX1282) ranging bridge firmware main — LILYGO T3S3.
 *
 * Host = ESP32-S3, radio = SX1282 (SX128x family, ranges identically to
 * SX1280; RadioLib SX1282 native). Exposes the E28 as an E80-style serial
 * console with master/slave ToF ranging.
 *
 * Pins (verified from sx1280-flrc-kiss-tnc, runs on this exact board):
 *   RADIO_SCK=5  RADIO_MISO=3  RADIO_MOSI=6  RADIO_NSS=7
 *   RADIO_RST=8  RADIO_BUSY=36 RADIO_DIO1=9
 *
 * RadioLib Module(nss=7, irq=9, rst=8, gpio=36) — gpio is the BUSY pin.
 * SPI 20 MHz, mode 0.
 *
 * Console commands: ID? STAT? RANGE RANGE-SLAVE RANGE? FREQ SF BW PA ADDR
 * HELP. Indoor TX power cap +10 dBm (E28_RANGE_TXPOW_CAP_INDOOR_DBM).
 * Ranging BW 812.5 kHz only.
 *
 * Build:  pio run -e esp32-e28-range
 * Flash:  pio run -e esp32-e28-range -t upload
 * Monitor: pio device monitor -p /dev/ttyACM0 -b 115200
 */

#include <Arduino.h>
#include <SPI.h>

#include <RadioLib.h>

#include "e28_range_console.h"

#ifndef SERIAL_BAUD
#define SERIAL_BAUD 115200
#endif
#ifndef FW_GIT_HASH
#define FW_GIT_HASH "0000000"
#endif

/* ---- pins (LILYGO T3S3 V1.3) --------------------------------------------- */
#define RADIO_SCK   5
#define RADIO_MISO  3
#define RADIO_MOSI  6
#define RADIO_NSS   7
#define RADIO_RST   8
#define RADIO_BUSY  36
#define RADIO_DIO1  9

/* ---- radio --------------------------------------------------------------- */
static SPIClass spiRf(HSPI);
static Module radioModule(RADIO_NSS, RADIO_DIO1, RADIO_RST, RADIO_BUSY, spiRf);
static SX1282 radio(&radioModule);

/* ---- e28_io_t seams ------------------------------------------------------ */

static void io_put(const char* s) { Serial.write(s); }

static int io_radio_begin(void)
{
    int st = radio.begin(
        (float)e28_range_freq_hz() / 1000000.0f,   /* MHz */
        e28_range_bw_khz(),                        /* kHz */
        e28_range_sf(),                            /* SF */
        7,                                         /* CR 4/7 */
        RADIOLIB_SX128X_SYNC_WORD_PRIVATE,
        e28_range_pa_dbm(),                        /* dBm (capped) */
        12);                                       /* preamble symbols */
    return st;
}

static int io_radio_range(bool master, uint32_t addr)
{
    return radio.range(master, addr);
}

static float io_radio_ranging_result(void)
{
    return radio.getRangingResult();
}

static const e28_io_t e28_io = {
    io_put,
    io_radio_begin,
    io_radio_range,
    io_radio_ranging_result,
};

/* ---- console line pump --------------------------------------------------- */

static char lineBuf[128];
static size_t lineLen = 0;

static void feedConsoleByte(char c)
{
    if(c == '\r') return;
    if(c == '\n') {
        lineBuf[lineLen] = 0;
        e28_range_feed_line(lineBuf);
        lineLen = 0;
        return;
    }
    if(lineLen + 1 < sizeof lineBuf) lineBuf[lineLen++] = c;
    /* overflow: silently drop (host tools must not exceed 127 chars/line) */
}

/* ---- Arduino entry points ------------------------------------------------ */

void setup()
{
    Serial.begin(SERIAL_BAUD);
    const uint32_t t0 = millis();
    while(!Serial && millis() - t0 < 3000) delay(10);

    /* SPI bus: 20 MHz, mode 0 */
    spiRf.begin(RADIO_SCK, RADIO_MISO, RADIO_MOSI, RADIO_NSS);
    spiRf.setFrequency(20000000);
    spiRf.setDataMode(SPI_MODE0);

    e28_range_init(&e28_io, FW_GIT_HASH);

    Serial.write("\r\n" E28_RANGE_BOARD_NAME " " E28_RANGE_FW_VERSION
                 " fw=" FW_GIT_HASH "\r\n");
    Serial.write("ready\r\n");
}

void loop()
{
    while(Serial.available())
        feedConsoleByte((char)Serial.read());
}
