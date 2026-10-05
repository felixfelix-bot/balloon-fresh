/*
 * e80_flrc_bench.cpp — FLRC-650 sustained TX/RX bench on E80-900MBL-02 (RP2040)
 *
 * Single image, two roles:
 *   ROLE PIN GP15 (input pullup): open/floating = TX, strapped to GND = RX
 *   Serial override during the 5 s boot window: "TX" / "RX"
 *
 * TX role: waits 10 s (RX gets ready — proven flrc_raw_tx pattern), then sends
 *   1000 x 255 B FLRC-650 packets + DEADBEEF end marker carrying the TX count,
 *   then reports RESULT_TX (sent, tx_done, timeouts, kbps).
 * RX role: SET_RX, on DIO8 (J2-10) IRQ reads FLRC packet status (RSSI) then
 *   FIFO, re-arms; on DEADBEEF marker or 30 s silence reports RESULT_RX
 *   (rx, unique, dup, lost, PER %, kbps, rssi avg/min/max).
 *
 * Hot-loop gotchas carried over from the proven firmware (tag
 * rp2040-baseline-1377kbps / esp32_raw_tx.cpp):
 *   - CLEAR_ERRORS + CLEAR_IRQ + CLEAR_TX_FIFO before every TX cycle
 *     (PA_OCP_OVP error accumulates otherwise)
 *   - DIO IRQ pin polling for TX_DONE/RX_DONE (not SPI flag polling)
 *   - SET_RX re-arm after every RX_DONE, RX FIFO clear each packet
 *   - single CS-low transaction per SPI read (multi-CS reads corrupt)
 * Radio config: FLRC 650 kbps / BW 740 k, 255 B fixed payload, sync 0x12AD101B,
 *   LF path 868 MHz (E80-900MBL is a Sub-GHz module), PA per E80 demo LF table,
 *   default +12.5 dBm. TCXO init via rfInitE80Flrc (E80-module-specific).
 *
 * Serial 115200 (USB CDC + UART1 GP12/13). Commands (role idle window):
 *   RUN | STATUS | POWER <dbm> | FREQ <mhz> | HELP
 */

#include <Arduino.h>
#include <SPI.h>
#include <stdarg.h>

#define E80_HOST_RP2040
#include "e80_pinmap.h"

#ifndef E80_SPI_HZ
#define E80_SPI_HZ 4000000UL     // default bench clock (raise after clean run)
#endif

#define BENCH_FREQ_MHZ_DEFAULT  868.0f
#define BENCH_KBPS_DEFAULT      650
#define BENCH_POWER_DBM_DEFAULT 12.5f
#define BENCH_PKT_COUNT         1000
#define BENCH_AUTO_START_MS     10000
#define BENCH_ROLE_WINDOW_MS    5000
#define RX_SILENCE_MS           30000
#define RX_LISTEN_MS            300000
#define TX_TIMEOUT_MS           500

// Sync word bytes (TX and RX must match; proven value)
#define SYNC_W0 0x12
#define SYNC_W1 0xAD
#define SYNC_W2 0x10
#define SYNC_W3 0x1B

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

#include "e80_lr20xx_raw.h"

// ─── Runtime config ──────────────────────────────────────────────────────
static float    gFreqMHz  = BENCH_FREQ_MHZ_DEFAULT;
static uint32_t gKbps     = BENCH_KBPS_DEFAULT;
static float    gPowerDbm = BENCH_POWER_DBM_DEFAULT;
static bool     gIsTxRole = true;
static bool     gRadioOk  = false;

static void rfHardReset() {
    digitalWrite(PIN_RST, LOW);
    delay(20);
    digitalWrite(PIN_RST, HIGH);
    delay(50);
}

static uint8_t powerDbmToHalfDb(float dbm) {
    if (dbm < -10.0f) dbm = -10.0f;      // LF PA table floor (−10 dBm)
    if (dbm > 22.0f)  dbm = 22.0f;       // LF PA table ceiling (+22 dBm)
    return (uint8_t)(dbm * 2.0f + 0.5f);
}

static bool initRadio() {
    rfHardReset();
    if (!rfWaitBusy(200000)) {
        dualPrintf("INIT_FAIL: BUSY stuck high (wiring/power)\n");
        return false;
    }
    uint8_t ver[4]; uint16_t ie;
    int rc = rfInitE80Flrc((uint32_t)(gFreqMHz * 1e6f), gKbps,
                           powerDbmToHalfDb(gPowerDbm),
                           IRQ_TX_DONE | IRQ_RX_DONE | IRQ_CRC_ERROR,
                           ver, &ie);
    if (rc != 0) {
        dualPrintf("INIT_FAIL rc=%d ver=[%02X %02X %02X %02X] init_errors=0x%04X\n",
                   rc, ver[0], ver[1], ver[2], ver[3], ie);
        return false;
    }
    dualPrintf("INIT_OK ver=0x%02X%02X TCXO=2.2V/64000 freq=%.1fMHz br=%lukbps "
               "pwr=%.1fdBm spi=%luHz\n",
               ver[0], ver[1], gFreqMHz, (unsigned long)gKbps, gPowerDbm,
               (unsigned long)E80_SPI_HZ);
    return true;
}

// ─── TX burst (proven hot-loop pattern) ──────────────────────────────────
static void runTxBurst() {
    uint8_t txBuf[FLRC_PAYLOAD_SZ];
    for (int i = 0; i < FLRC_PAYLOAD_SZ; i++) txBuf[i] = (uint8_t)(i ^ 0xA5);

    rfClearRxFifo();
    rfClearTxFifo();
    rfClearIrq();

    uint32_t startMs = millis();
    uint32_t sent = 0, txDone = 0, timeouts = 0;

    dualPrintf("TX_START count=%d size=%d\n", BENCH_PKT_COUNT, FLRC_PAYLOAD_SZ);

    for (uint32_t i = 0; i < BENCH_PKT_COUNT; i++) {
        txBuf[0] = (uint8_t)(i >> 24); txBuf[1] = (uint8_t)(i >> 16);
        txBuf[2] = (uint8_t)(i >> 8);  txBuf[3] = (uint8_t)(i & 0xFF);
        txBuf[4] = 'E'; txBuf[5] = '8'; txBuf[6] = '0'; txBuf[7] = 'B';

        // per-cycle hygiene (proven): errors + irq + tx fifo before every TX
        rfClearErrors();
        rfClearIrq();
        rfClearTxFifo();
        rfWriteTxFifo(txBuf, FLRC_PAYLOAD_SZ);
        rfSetTx();
        sent++;

        // wait TX_DONE on DIO8 pin (proven spin-poll)
        uint32_t t0 = millis();
        bool done = false;
        while ((millis() - t0) < TX_TIMEOUT_MS) {
            if (rfIrq()) { done = true; break; }
        }
        if (done) txDone++; else timeouts++;

        digitalWrite(PIN_LED, (i & 1) ? HIGH : LOW);

        if (timeouts >= 20) {  // radio wedged — stop early, report
            dualPrintf("TX_ABORT: %lu consecutive timeouts\n",
                       (unsigned long)timeouts);
            break;
        }
    }

    // end marker: DEADBEEF + total count (proven pattern)
    txBuf[0] = 0xDE; txBuf[1] = 0xAD; txBuf[2] = 0xBE; txBuf[3] = 0xEF;
    txBuf[4] = (uint8_t)(sent >> 24); txBuf[5] = (uint8_t)(sent >> 16);
    txBuf[6] = (uint8_t)(sent >> 8);  txBuf[7] = (uint8_t)(sent & 0xFF);
    rfClearErrors();
    rfClearIrq();
    rfClearTxFifo();
    rfWriteTxFifo(txBuf, FLRC_PAYLOAD_SZ);
    rfSetTx();
    { uint32_t t0 = millis();
      while ((millis() - t0) < TX_TIMEOUT_MS) { if (rfIrq()) break; } }
    rfClearIrq();

    uint32_t elapsedMs = millis() - startMs;
    float kbps = elapsedMs ? ((float)txDone * FLRC_PAYLOAD_SZ * 8.0f) / (float)elapsedMs : 0.0f;
    dualPrintf("RESULT_TX,sent=%lu,tx_done=%lu,timeout=%lu,elapsed_ms=%lu,"
               "throughput_kbps=%.1f,pkt_bytes=%d,freq_mhz=%.1f,bitrate_kbps=%lu,"
               "tx_power_dbm=%.1f\n",
               (unsigned long)sent, (unsigned long)txDone, (unsigned long)timeouts,
               (unsigned long)elapsedMs, kbps, FLRC_PAYLOAD_SZ, gFreqMHz,
               (unsigned long)gKbps, gPowerDbm);
    digitalWrite(PIN_LED, LOW);
}

// ─── RX session ──────────────────────────────────────────────────────────
struct RxStats {
    uint32_t received, duplicates, crcErrors, totalFromTx, lastSeq;
    int32_t  rssiSum; uint32_t rssiCount; int16_t rssiMin, rssiMax;
};

static void runRxSession() {
    RxStats st = {};
    st.lastSeq = 0xFFFFFFFF;
    st.rssiMin = 0; st.rssiMax = -200;

    rfClearRxFifo();
    rfClearIrq();
    rfSetRx();                       // armed with max timeout
    delay(2);

    uint32_t startMs = millis(), lastPktMs = startMs;
    uint8_t buf[FLRC_PAYLOAD_SZ];
    bool ended = false;

    dualPrintf("RX_START listening (silence timeout %ds)\n", RX_SILENCE_MS / 1000);

    while (!ended) {
        uint32_t now = millis();
        if ((now - startMs) > RX_LISTEN_MS) { dualPrintf("RX_WINDOW_END\n"); break; }
        if (st.received > 0 && (now - lastPktMs) > RX_SILENCE_MS) {
            dualPrintf("RX_SILENCE_END\n"); break;
        }
        if (!rfIrq()) continue;      // DIO8 poll (proven)

        uint32_t irq = rfGetIrqStatus();
        if (irq & IRQ_CRC_ERROR) {
            st.crcErrors++;
            rfClearRxFifo();
            rfClearIrq();
            rfSetRx();
            continue;
        }
        if (!(irq & IRQ_RX_DONE)) {  // timeout or other — re-arm
            rfClearIrq();
            rfSetRx();
            continue;
        }

        // RSSI FIRST (before FIFO ops — proven ordering)
        FlrcPktStatus ps;
        rfFlrcGetPktStatus(&ps);
        rfReadRxFifo(buf, FLRC_PAYLOAD_SZ);

        if (buf[0] == 0xDE && buf[1] == 0xAD && buf[2] == 0xBE && buf[3] == 0xEF) {
            st.totalFromTx = ((uint32_t)buf[4] << 24) | ((uint32_t)buf[5] << 16) |
                             ((uint32_t)buf[6] << 8)  | (uint32_t)buf[7];
            ended = true;
        } else {
            uint32_t seq = ((uint32_t)buf[0] << 24) | ((uint32_t)buf[1] << 16) |
                           ((uint32_t)buf[2] << 8)  | (uint32_t)buf[3];
            st.received++;
            if (seq == st.lastSeq) st.duplicates++;  // proven semantics
            st.lastSeq = seq;
            st.rssiSum += ps.rssi_avg_dbm; st.rssiCount++;
            if (ps.rssi_avg_dbm < st.rssiMin) st.rssiMin = ps.rssi_avg_dbm;
            if (ps.rssi_avg_dbm > st.rssiMax) st.rssiMax = ps.rssi_avg_dbm;
            lastPktMs = millis();
            if (st.received <= 5 || (st.received % 100) == 0) {
                dualPrintf("PKT rx=%lu seq=%lu rssi=%d raw=[%02X %02X %02X %02X %02X] fl=0x%02X\n",
                           (unsigned long)st.received, (unsigned long)seq,
                           ps.rssi_avg_dbm, ps.raw[0], ps.raw[1], ps.raw[2],
                           ps.raw[3], ps.raw[4], ps.flags);
            }
        }
        digitalWrite(PIN_LED, HIGH);

        // per-packet hygiene + re-arm (proven)
        rfClearRxFifo();
        rfClearErrors();
        rfClearIrq();
        rfSetRx();
    }

    uint32_t elapsedMs = millis() - startMs;
    uint32_t total = st.totalFromTx ? st.totalFromTx : (st.lastSeq + 1);
    uint32_t lost = total > st.received ? (total - st.received) : 0;
    float per = total ? 100.0f * (float)lost / (float)total : 0.0f;
    float kbps = (elapsedMs && st.received)
                 ? ((float)st.received * FLRC_PAYLOAD_SZ * 8.0f) / (float)elapsedMs : 0.0f;
    float rssiAvg = st.rssiCount ? (float)st.rssiSum / (float)st.rssiCount : 0.0f;
    if (st.rssiCount == 0) { st.rssiMin = 0; st.rssiMax = 0; }
    uint32_t unique = st.received - st.duplicates;

    dualPrintf("RESULT_RX,rx=%lu,unique=%lu,dup=%lu,lost=%lu,total=%lu,per=%.2f,"
               "elapsed_ms=%lu,throughput_kbps=%.1f,rssi_avg_dbm=%.1f,"
               "rssi_min_dbm=%d,rssi_max_dbm=%d,crc_err=%lu,pkt_bytes=%d,"
               "freq_mhz=%.1f,bitrate_kbps=%lu\n",
               (unsigned long)st.received, (unsigned long)unique,
               (unsigned long)st.duplicates, (unsigned long)lost,
               (unsigned long)total, per, (unsigned long)elapsedMs, kbps,
               rssiAvg, st.rssiMin, st.rssiMax, (unsigned long)st.crcErrors,
               FLRC_PAYLOAD_SZ, gFreqMHz, (unsigned long)gKbps);
    digitalWrite(PIN_LED, LOW);
}

// ─── Serial command handling ─────────────────────────────────────────────
static void handleLine(const char* line) {
    if (!strncmp(line, "TX", 2))  { gIsTxRole = true;  dualPrintf("ROLE=TX\n"); }
    else if (!strncmp(line, "RX", 2)) { gIsTxRole = false; dualPrintf("ROLE=RX\n"); }
    else if (!strncmp(line, "RUN", 3)) {
        gRadioOk = initRadio();
        if (gRadioOk) { if (gIsTxRole) runTxBurst(); else runRxSession(); }
    }
    else if (!strncmp(line, "INIT", 4)) { gRadioOk = initRadio(); }
    else if (!strncmp(line, "STATUS", 6)) {
        dualPrintf("STATUS role=%s radio=%s freq=%.1f kbps=%lu pwr=%.1f spi=%lu\n",
                   gIsTxRole ? "TX" : "RX", gRadioOk ? "ok" : "down",
                   gFreqMHz, (unsigned long)gKbps, gPowerDbm,
                   (unsigned long)E80_SPI_HZ);
    }
    else if (!strncmp(line, "POWER ", 6)) {
        gPowerDbm = atof(line + 6);
        dualPrintf("POWER=%.1f dBm (half-db code %u)\n", gPowerDbm,
                   (unsigned)powerDbmToHalfDb(gPowerDbm));
    }
    else if (!strncmp(line, "FREQ ", 5)) {
        float f = atof(line + 5);
        if (f >= 850.0f && f <= 930.0f) { gFreqMHz = f; dualPrintf("FREQ=%.1f\n", f); }
        else dualPrintf("FREQ out of E80-900 range (850-930)\n");
    }
    else if (!strncmp(line, "HELP", 4) || !strncmp(line, "H", 1)) {
        dualPrintf("RUN STATUS INIT TX RX POWER <dbm> FREQ <mhz>\n");
    }
}

static void pollSerial(Stream& s, char* line, size_t& len) {
    while (s.available()) {
        char c = (char)s.read();
        if (c == '\n' || c == '\r') {
            if (len) { line[len] = 0; handleLine(line); len = 0; }
        } else if (len < 31) {
            line[len++] = c;
        }
    }
}

// ─── Setup / loop ────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    Serial1.setTX(12);
    Serial1.setRX(13);
    Serial1.begin(115200);
    delay(2000);

    pinMode(PIN_CS, OUTPUT);
    pinMode(PIN_RST, OUTPUT);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);
    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_ROLE, INPUT_PULLUP);
    digitalWrite(PIN_CS, HIGH);
    digitalWrite(PIN_RST, LOW);
    digitalWrite(PIN_LED, LOW);

    spiRf.begin();

    dualPrintf("\n=== E80 FLRC-650 BENCH — %s ===\n", E80_HOST_NAME);
    dualPrintf("Pins: SCK=GP%d MOSI=GP%d MISO=GP%d CS=GP%d BUSY=GP%d IRQ(DIO8)=GP%d RST=GP%d "
               "ROLE=GP%d LED=GP%d\n",
               PIN_SCK, PIN_MOSI, PIN_MISO, PIN_CS, PIN_BUSY, PIN_IRQ, PIN_RST,
               PIN_ROLE, PIN_LED);
    dualPrintf("SPI=%lu Hz  FLRC-%lu  payload=%dB  count=%d\n",
               (unsigned long)E80_SPI_HZ, (unsigned long)gKbps,
               FLRC_PAYLOAD_SZ, BENCH_PKT_COUNT);

    // role strap + serial override window
    gIsTxRole = (digitalRead(PIN_ROLE) == HIGH);
    dualPrintf("ROLE_PIN GP15=%d -> %s (strap to GND for RX). Serial TX/RX to "
               "override, %ds window...\n",
               (int)(gIsTxRole ? 1 : 0), gIsTxRole ? "TX" : "RX",
               BENCH_ROLE_WINDOW_MS / 1000);
    char line[32]; size_t len = 0;
    uint32_t t0 = millis();
    while ((millis() - t0) < BENCH_ROLE_WINDOW_MS) {
        pollSerial(Serial, line, len);
        pollSerial(Serial1, line, len);
        digitalWrite(PIN_LED, ((millis() / 250) & 1) ? HIGH : LOW);
    }
    digitalWrite(PIN_LED, LOW);
    dualPrintf("ROLE_FINAL=%s\n", gIsTxRole ? "TX" : "RX");

    gRadioOk = initRadio();
}

void loop() {
    static char line[32]; static size_t len = 0;
    pollSerial(Serial, line, len);
    pollSerial(Serial1, line, len);

    if (!gRadioOk) { delay(1000); return; }

    if (gIsTxRole) {
        dualPrintf("TX burst in %ds...\n", BENCH_AUTO_START_MS / 1000);
        delay(BENCH_AUTO_START_MS);
        runTxBurst();
        dualPrintf("Next burst in 10s (send RUN to retrigger)\n");
        delay(10000);
    } else {
        runRxSession();
        dualPrintf("RX re-arm in 5s\n");
        delay(5000);
    }
}
