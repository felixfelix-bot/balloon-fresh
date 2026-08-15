/*
 * e80_chip_diag.cpp — LR2021 chip diagnostic on E80-900MBL-02 (RP2040 host)
 *
 * Minimal bring-up tool: holds the radio in reset, releases it, reads chip
 * identity + status + errors over raw 2-byte-opcode SPI at a conservative
 * 1 MHz (jumper-harness guidance, wiring doc §6/§7.5), and loops on serial
 * commands. Original scripts/chip_diagnostic.cpp is absent from the repo, so
 * this is the minimal equivalent built on the proven opcode layer
 * (multi_radio_sweep.cpp / ADR-020) plus the E80 TCXO bring-up.
 *
 * Pins (wiring doc §6 host1, asserted against common/e80_pinmap.h):
 *   SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7(DIO8) RST=GP8
 *
 * Serial 115200 on USB CDC + UART1 GP12/13 (dual output, proven pattern).
 * Commands: V=version  S=status/irq  E=errors  T=TCXO+cal  H=help
 */

#include <Arduino.h>
#include <SPI.h>
#include <stdarg.h>

#define E80_HOST_RP2040
#include "../common/e80_pinmap.h"

#ifndef E80_SPI_HZ
#define E80_SPI_HZ 1000000UL
#endif

// ─── Dual serial output (USB CDC + UART1 bridge — proven pattern) ────────
static void dualPrintf(const char* fmt, ...) {
    char buf[300];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    Serial.print(buf);
    Serial1.print(buf);
}

// ─── Host glue for the shared opcode layer ───────────────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(E80_SPI_HZ, MSBFIRST, SPI_MODE0);

#define E80_CS_LOW()      do { spiRf.beginTransaction(spiSettings); digitalWrite(PIN_CS, LOW); } while (0)
#define E80_CS_HIGH()     do { digitalWrite(PIN_CS, HIGH); spiRf.endTransaction(); } while (0)
#define E80_SPI_TX(b, n)  spiRf.transfer(const_cast<uint8_t*>(b), nullptr, n)
#define E80_SPI_RX(b, n)  spiRf.transfer(b, n)   // in-place: sends old, keeps rx
#define E80_BUSY_READ()   (digitalRead(PIN_BUSY) == HIGH)
#define E80_IRQ_READ()    (digitalRead(PIN_IRQ) == HIGH)
#define E80_DELAY_US(us)  delayMicroseconds(us)
#define E80_DELAY_MS(ms)  delay(ms)

#include "../common/e80_lr20xx_raw.h"

// ─── Hard reset (wiring doc §6 bring-up order: RST low → high → settle) ──
static void rfHardReset() {
    digitalWrite(PIN_RST, LOW);
    delay(20);                       // ≥10 ms per demo hal_reset
    digitalWrite(PIN_RST, HIGH);
    delay(50);                       // TCXO/clock settle before first command
}

// ─── Report helpers ──────────────────────────────────────────────────────
static void reportVersion() {
    uint8_t raw[4] = {0};
    uint16_t ver = rfGetVersion(raw);
    bool allZero = raw[0] == 0 && raw[1] == 0 && raw[2] == 0 && raw[3] == 0;
    bool allFF   = raw[0] == 0xFF && raw[1] == 0xFF && raw[2] == 0xFF && raw[3] == 0xFF;
    dualPrintf("VERSION raw=[%02X %02X %02X %02X] major=0x%02X minor=0x%02X : %s\n",
               raw[0], raw[1], raw[2], raw[3], ver >> 8, ver & 0xFF,
               allZero ? "ALL-ZERO (MISO stuck low / no supply?)" :
               allFF   ? "ALL-FF (MISO stuck high / NSS-BUSY swapped?)" :
               "CHIP_RESPONDING");
}

static void reportIrqStatus() {
    uint32_t irq = rfGetIrqStatus();
    dualPrintf("IRQ_STATUS=0x%08lX BUSY=%d DIO8_PIN=%d\n",
               (unsigned long)irq, (int)rfBusy(), (int)rfIrq());
}

static void reportErrors() {
    uint16_t e = rfGetErrors();
    dualPrintf("ERRORS=0x%04X (%s)\n", e, e == 0 ? "none" : "see LR20xx error bits");
}

static void doTcxoInit() {
    uint8_t ver[4]; uint16_t ie;
    int rc = rfInitE80Flrc(868000000UL, 650, 25 /*12.5 dBm*/,
                           IRQ_RX_DONE | IRQ_TX_DONE, ver, &ie);
    dualPrintf("TCXO_INIT rc=%d init_errors=0x%04X (demo prints-but-clears; "
               "nonzero is informational)\n", rc, ie);
}

// ─── Setup / loop ────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    Serial1.setTX(12);               // GP12 → ESP32 bridge (optional)
    Serial1.setRX(13);               // GP13 ← ESP32 bridge
    Serial1.begin(115200);
    delay(2000);

    pinMode(PIN_CS, OUTPUT);
    pinMode(PIN_RST, OUTPUT);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    digitalWrite(PIN_RST, LOW);      // radio held in reset while SPI comes up
    digitalWrite(PIN_LED, LOW);

    spiRf.begin();
    delay(10);

    dualPrintf("\n=== E80 CHIP DIAG — %s @ %lu Hz SPI ===\n",
               E80_HOST_NAME, (unsigned long)E80_SPI_HZ);
    dualPrintf("Pins: SCK=GP%d MOSI=GP%d MISO=GP%d CS=GP%d BUSY=GP%d IRQ(DIO8)=GP%d RST=GP%d\n",
               PIN_SCK, PIN_MOSI, PIN_MISO, PIN_CS, PIN_BUSY, PIN_IRQ, PIN_RST);
    dualPrintf("(static_asserts vs wiring doc passed at build time)\n");

    rfHardReset();
    if (!rfWaitBusy(200000)) {
        dualPrintf("BUSY stuck HIGH after reset — check wiring/power (J2-7, GND jumper)\n");
    } else {
        dualPrintf("BUSY low after reset — radio awake\n");
    }

    reportVersion();
    reportIrqStatus();
    reportErrors();
    dualPrintf("Type V (version)  S (status)  E (errors)  T (TCXO+cal init)  H (help)\n");
}

void loop() {
    if (Serial.available()) {
        char c = Serial.read();
        while (Serial.available()) Serial.read();
        switch (c) {
            case 'V': case 'v': reportVersion();   break;
            case 'S': case 's': reportIrqStatus(); break;
            case 'E': case 'e': reportErrors();    break;
            case 'T': case 't': doTcxoInit();      break;
            case 'H': case 'h':
                dualPrintf("V=version S=status E=errors T=TCXO init\n");
                break;
            default: break;
        }
    }
    if (Serial1.available()) {
        char c = Serial1.read();
        if (c == 'V' || c == 'v') reportVersion();
        else if (c == 'S' || c == 's') reportIrqStatus();
        else if (c == 'E' || c == 'e') reportErrors();
    }
    digitalWrite(PIN_LED, rfBusy() ? HIGH : LOW);
    delay(10);
}
