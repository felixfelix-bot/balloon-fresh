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

/* ---- RF front-end switch (SX1280PA variant ONLY) -------------------------
 * LILYGO's own board header for `USING_SX1280PA` defines two extra pins that
 * the plain `USING_SX1280` block does NOT have:
 *     RADIO_RX_PIN 21   RADIO_TX_PIN 10
 * They gate an external PA/LNA (FEM). Leaving them undriven (the reset state
 * is input) disables the RF path entirely: SPI still answers perfectly and the
 * chip reports err=0, but nothing is transmitted or received, so a ranging
 * exchange times out on BOTH ends with RADIOLIB_ERR_RANGING_TIMEOUT (-901) at
 * every power / spreading factor / role assignment — measured 2026-09-23.
 * RadioLib switches these automatically per mode via the RF switch table.
 * Boards without the FEM (plain SX1280 SKU) simply ignore these pins. */
#define RADIO_RX_EN 21
#define RADIO_TX_EN 10

/* ---- radio ---------------------------------------------------------------
 * RadioLib's findChip() picks the chip class by comparing the silicon's
 * 16-byte version string (register 0x01F0) against a hard-coded SKU string.
 * The T3S3 carrier ships with either the SX1280 (+13 dBm) or the "with PA"
 * SX1282 (+22 dBm) part, and this firmware must not care which — the first
 * hardware run on 2026-09-23 failed with RADIOLIB_ERR_CHIP_NOT_FOUND (-2)
 * purely because the build assumed "SX1282" while the silicon reports
 * "SX1280". This subclass adopts whatever the silicon reports.
 * Ranging lives in SX1280 (SX1282 inherits it); SX1281 has NO ranging engine
 * and is explicitly rejected rather than silently accepted.
 */
class SX128xRanging : public SX1280 {
  public:
    explicit SX128xRanging(Module* mod) : SX1280(mod) {}

    /** Adopt the probed silicon version string. `ver` must outlive the radio
     *  object (callers pass a static buffer). Capability gating is done by the
     *  host-tested core. */
    /** SX128x::clearIrqStatus is protected; expose it for the TXPROBE
     *  diagnostic (a derived class may reach protected members). */
    int16_t clearIrqPublic(uint16_t mask = RADIOLIB_SX128X_IRQ_ALL)
    {
        return this->clearIrqStatus(mask);
    }

    bool adoptSilicon(const char* ver)
    {
        if (!e28_chip_supports_ranging(ver)) return false;
        this->chipType = ver;
        return true;
    }
};

static SPIClass spiRf(HSPI);
static Module radioModule(RADIO_NSS, RADIO_DIO1, RADIO_RST, RADIO_BUSY, spiRf);
static SX128xRanging radio(&radioModule);
static char g_chip_ver[17] = { 0 };

/* RF switch table: (RX enable, TX enable). idle = both off, RX = RX_EN only,
 * TX = TX_EN only. RADIOLIB_NC terminates the pin list. */
/* RadioLib takes the pin list as a reference to an array of EXACTLY
 * Module::RFSWITCH_MAX_PINS (5) entries; unused slots are RADIOLIB_NC. */
static const uint32_t rfswitch_pins[] = {
    RADIO_RX_EN, RADIO_TX_EN, RADIOLIB_NC, RADIOLIB_NC, RADIOLIB_NC
};
static const Module::RfSwitchMode_t rfswitch_table[] = {
    { Module::MODE_IDLE, { LOW,  LOW  } },
    { Module::MODE_RX,   { HIGH, LOW  } },
    { Module::MODE_TX,   { LOW,  HIGH } },
    END_OF_MODE_TABLE
};

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

/* Probe commands are handled in the firmware glue, before the host-testable
 * core, because they need raw SPI access that the core's e28_io_t seam does
 * not expose (and must work even when RadioLib init failed). */
static void probe_chip(void);   /* raw CHIP? silicon probe — defined below */
static void probe_rssi(void);   /* receive-only RSSI check — defined below */
static void probe_tx(void);     /* TX-completion vs IRQ-pin discriminator */

static void dispatchLine(const char* line)
{
    if (strncmp(line, "CHIP?", 5) == 0) { probe_chip(); return; }
    if (strncmp(line, "RSSI?", 5) == 0) { probe_rssi(); return; }
    if (strncmp(line, "TXPROBE", 7) == 0) { probe_tx(); return; }
    e28_range_feed_line(line);
}

static void feedConsoleByte(char c)
{
    if(c == '\r') return;
    if(c == '\n') {
        lineBuf[lineLen] = 0;
        dispatchLine(lineBuf);
        lineLen = 0;
        return;
    }
    if(lineLen + 1 < sizeof lineBuf) lineBuf[lineLen++] = c;
    /* overflow: silently drop (host tools must not exceed 127 chars/line) */
}

/* ---- CHIP? raw silicon probe (diagnostic) --------------------------------
 * Reads the 16-byte version string at SX128x register 0x01F0 directly over
 * SPI (READ_REGISTER 0x19, 16-bit addr), at several SCK rates. This is what
 * RadioLib findChip() compares against the chipType string ("SX1282"), so it
 * answers three questions at once:
 *   - is the silicon a SX128x at all, or a sub-GHz SX126x,
 *   - does the SPI bus work on this pinout,
 *   - does 20 MHz (over the 18 MHz SX128x datasheet max) break the read.
 * Output is plain ASCII on the console, no RadioLib state required.
 */
static char printable_or_dot(uint8_t b)
{
    return (b >= 32 && b < 127) ? (char)b : '.';
}

/* Read the 16-byte version string at reg 0x01F0 with a raw SPI sequence and
 * decode it into `out` (NUL-terminated). The layout/alignment logic lives in
 * the host-tested core (e28_decode_chip_version) so a decode bug cannot hide
 * as a hardware fault. Safe to call before RadioLib is initialised — that is
 * the whole point, since findChip() is what needs this string. */
static void rawChipVersion(char out[17])
{
    uint8_t raw[17] = { 0 };
    pinMode(RADIO_RST, OUTPUT);
    digitalWrite(RADIO_RST, HIGH);      /* never leave the radio in reset */
    pinMode(RADIO_NSS, OUTPUT);
    digitalWrite(RADIO_NSS, HIGH);
    spiRf.begin(RADIO_SCK, RADIO_MISO, RADIO_MOSI, RADIO_NSS);
    spiRf.setFrequency(4000000);        /* conservative: well under the 18 MHz max */
    spiRf.setDataMode(SPI_MODE0);
    delay(2);

    digitalWrite(RADIO_NSS, LOW);
    delayMicroseconds(20);
    spiRf.transfer(RADIOLIB_SX128X_CMD_READ_REGISTER);
    spiRf.transfer((uint8_t)((RADIOLIB_SX128X_REG_VERSION_STRING >> 8) & 0xFF));
    spiRf.transfer((uint8_t)(RADIOLIB_SX128X_REG_VERSION_STRING & 0xFF));
    for (uint8_t i = 0; i < 17; i++) raw[i] = spiRf.transfer(0x00);
    digitalWrite(RADIO_NSS, HIGH);

    e28_decode_chip_version(raw, out);
}

static void probe_at(uint32_t hz)
{
    pinMode(RADIO_NSS, OUTPUT);
    digitalWrite(RADIO_NSS, HIGH);
    spiRf.begin(RADIO_SCK, RADIO_MISO, RADIO_MOSI, RADIO_NSS);
    spiRf.setFrequency(hz);
    spiRf.setDataMode(SPI_MODE0);
    delay(2);

    uint8_t raw[17];
    digitalWrite(RADIO_NSS, LOW);
    delayMicroseconds(20);
    spiRf.transfer(RADIOLIB_SX128X_CMD_READ_REGISTER);
    spiRf.transfer((uint8_t)((RADIOLIB_SX128X_REG_VERSION_STRING >> 8) & 0xFF));
    spiRf.transfer((uint8_t)(RADIOLIB_SX128X_REG_VERSION_STRING & 0xFF));
    for (uint8_t i = 0; i < 17; i++) raw[i] = spiRf.transfer(0x00);
    digitalWrite(RADIO_NSS, HIGH);

    char hex[3 * 17 + 1];
    size_t p = 0;
    for (uint8_t i = 0; i < 17; i++)
        p += snprintf(hex + p, sizeof hex - p, "%02X ", raw[i]);

    char straight[18];
    for (uint8_t i = 0; i < 16; i++) straight[i] = printable_or_dot(raw[i + 1]);
    straight[16] = 0;

    char even[9], odd[9];   /* in case a status byte is interleaved per word */
    for (uint8_t i = 0; i < 8; i++) {
        even[i] = printable_or_dot(raw[1 + 2 * i]);
        odd[i]  = printable_or_dot(raw[2 + 2 * i]);
    }
    even[8] = 0;
    odd[8] = 0;

    char line[160];
    snprintf(line, sizeof line, "CHIP? %luHz raw=%s ascii=\"%s\" even=\"%s\" odd=\"%s\"\r\n",
             (unsigned long)hz, hex, straight, even, odd);
    Serial.write(line);
}

static void probe_chip(void)
{
    pinMode(RADIO_RST, OUTPUT);
    digitalWrite(RADIO_RST, HIGH);   /* never leave the radio held in reset */
    delay(5);
    probe_at(20000000);
    probe_at(16000000);
    probe_at(8000000);
    probe_at(2000000);
    Serial.write("CHIP? done\r\n");
}

/* RSSI? — RECEIVE-ONLY channel scan. Transmits nothing (no PA keying, no RF
 * output), so it is safe to run with the antenna port open, and it is the
 * non-destructive way to tell whether an antenna is actually attached to the
 * port the SX1280 is wired to: a real 2.4 GHz antenna picks up ambient energy
 * (roughly -95..-85 dBm indoors) while a floating/open port sits at the chip
 * noise floor (about -110 dBm). LILYGO's own reference firmware uses
 * scanChannel() the same way for listen-before-talk. */
static void probe_rssi(void)
{
    char line[160];
    const int16_t st = radio.scanChannel();
    /* NOTE: the two successful scan outcomes are NEGATIVE constants --
     * RADIOLIB_PREAMBLE_DETECTED (-14) and RADIOLIB_CHANNEL_FREE (-15). Only
     * anything else is a failure (first version of this function treated every
     * negative value as an error and threw the RSSI away). */
    const char* verdict = (st == RADIOLIB_PREAMBLE_DETECTED) ? "lora-preamble"
                        : (st == RADIOLIB_CHANNEL_FREE)     ? "channel-free"
                        : "scan-error";
    /* getRSSI() with no argument reads the PACKET STATUS register, which is 0
     * until a packet is received -- that produced a bogus "-0.0 dBm". The
     * instantaneous-RSSI accessor (packet=false) reads the RssiInst register
     * and is the real ambient-energy reading we want here. */
    snprintf(line, sizeof line, "RSSI %.1f dBm inst=%.1f dBm state=%d (%s)\r\n",
             (double)radio.getRSSI(), (double)radio.getRSSI(false), (int)st, verdict);
    Serial.write(line);
}

/* TXPROBE — transmit ONE short packet at the current (minimum) power, then
 * compare two independent signals that must agree:
 *   (a) the radio's own IRQ status register  -> did the chip finish the TX?
 *   (b) the level of the DIO1 GPIO           -> did that IRQ reach the host?
 * RadioLib's range()/transmit() block on (b) for up to 10 s, so if (a) says
 * done while (b) stays low, every interrupt-driven operation times out even
 * though the radio is perfectly healthy -- exactly the signature measured on
 * 2026-09-23 (all register reads fine, everything IRQ-driven returns -901).
 * Deliberately does NOT wait on the IRQ line. */
static void probe_tx(void)
{
    static const uint8_t payload[12] = {
        'E','2','8','P','R','O','B','E','0','1','0','1'
    };
    radio.clearIrqPublic();
    const int16_t st = radio.startTransmit(payload, sizeof payload);

    /* let the TX play out; poll the wall clock, not the IRQ line */
    const uint32_t t0 = millis();
    while (millis() - t0 < 400) delay(5);

    const int dio1 = digitalRead(RADIO_DIO1);
    const uint16_t irq = radio.getIrqStatus();
    radio.finishTransmit();

    char line[192];
    snprintf(line, sizeof line,
             "TXPROBE start=%d txdone_irqbit=%d dio1_pin=%d irqstatus=0x%04X\r\n",
             (int)st, (irq & RADIOLIB_SX128X_IRQ_TX_DONE) ? 1 : 0, dio1, (unsigned)irq);
    Serial.write(line);
}

/* ---- Arduino entry points ------------------------------------------------ */

void setup()
{
    Serial.begin(SERIAL_BAUD);
    const uint32_t t0 = millis();
    while(!Serial && millis() - t0 < 3000) delay(10);

    /* SPI bus: 16 MHz, mode 0 (SX128x datasheet max is 18 MHz; the original
     * 20 MHz was over spec and is not needed for either build or ranging). */
    spiRf.begin(RADIO_SCK, RADIO_MISO, RADIO_MOSI, RADIO_NSS);
    spiRf.setFrequency(16000000);
    spiRf.setDataMode(SPI_MODE0);

    /* Identify the silicon BEFORE RadioLib init and adopt it, so the firmware
     * works on both the SX1280 and the "with PA" SX1282 T3S3 SKUs. */
    rawChipVersion(g_chip_ver);
    const bool chipOk = radio.adoptSilicon(g_chip_ver);

    /* Enable the external PA/LNA front end (SX1280PA). Must be set before
     * begin(): RadioLib applies the table whenever the radio changes mode. */
    radio.setRfSwitchTable(rfswitch_pins, rfswitch_table);

    e28_range_init(&e28_io, FW_GIT_HASH);

    /* Ranging on the PA variant must stay low power: LILYGO's own ranging
     * example for this board pins RangingTXPower at 3 dBm with the comment
     * "Cannot be greater than 3 dbm". Set that through the tested PA handler
     * (which clamps to the +10 dBm indoor cap regardless). */
    e28_range_feed_line("PA 3");

    char banner[128];
    snprintf(banner, sizeof banner,
             "\r\n" E28_RANGE_BOARD_NAME " " E28_RANGE_FW_VERSION
             " fw=" FW_GIT_HASH " chip=\"%s\" ranging_capable=%d\r\n",
             g_chip_ver, chipOk ? 1 : 0);
    Serial.write(banner);
    if (!chipOk) {
        Serial.write("ERR unsupported radio: ranging needs SX1280/SX1282 "
                     "(SX1281 has no ranging engine)\r\n");
    }
    Serial.write("ready\r\n");
}

void loop()
{
    while(Serial.available())
        feedConsoleByte((char)Serial.read());
}
