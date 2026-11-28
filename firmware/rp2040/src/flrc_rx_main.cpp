/*
 * flrc_rx_main.cpp — RP2040 FLRC Speed RX for the LR2021 speed-record test
 *
 * RX half of the speed test. The ESP32-C3 TX (mesh-stack/flrc-bench-espidf,
 * fifo_tx.cpp) blasts numbered 255-byte FLRC packets at BR=2600 uncoded on
 * 2450 MHz; this firmware counts them as fast as the RP2040 can pull them
 * out of the LR2021.
 *
 * Strategy (v1 — deliberately simple):
 *   1. RadioLib beginFLRC() does the full modulation config (same parameters
 *      as the ESP32 TX so the pair is interop-verified).
 *   2. RadioLib startReceive() arms the receiver once and routes RX_DONE
 *      onto the DIO9 IRQ pin.
 *   3. From then on the hot path is a raw SPI polling loop using the LR2021
 *      opcodes already verified on the ESP32 (LR2021_commands.h):
 *        SET_RX                  0x020C  (+3-byte timeout)
 *        GET_AND_CLEAR_IRQ_STATUS 0x0117 (opcode, then read 4 bytes)
 *        GET_RX_PKT_LENGTH       0x0212 (opcode, then read 2 bytes BE)
 *        READ_RX_FIFO            0x0001 (opcode, then read N bytes)
 *      No PIO/DMA, no RadioLib calls, no per-packet serial output.
 *
 * Per-packet sequence (timings recorded with micros()):
 *   IRQ pin HIGH → GET_AND_CLEAR_IRQ_STATUS → GET_RX_PKT_LENGTH →
 *   READ_RX_FIFO → SET_RX (re-arm) → account packet
 *
 * Serial commands (USB CDC, line-terminated):
 *   RUN     start receiving (ends on 0xDEADBEEF end-marker seq, idle
 *           timeout, or 200k-packet safety cap)
 *   CONFIG  print current radio/SPI configuration
 *   RESULTS print stats from the last (or current) run
 *   HELP    command list
 */

#include <Arduino.h>
#include <SPI.h>
#include <ctype.h>
#include <RadioLib.h>
#include "pins.h"

// ─── Radio configuration (must match the ESP32 TX: fifo_tx.cpp) ───────
#define FLRC_FREQ_MHZ   2450.0f                       // 2.4 GHz ISM
#define FLRC_BR_KBPS    2600                          // max FLRC bitrate
#define FLRC_CR         RADIOLIB_LR2021_FLRC_CR_1_0   // uncoded
#define FLRC_PWR_DBM    22                            // TX power (unused on RX)
#define FLRC_PREAMBLE   16
#define FLRC_SHAPING    RADIOLIB_SHAPING_0_5          // Gauss BT=0.5
#define FLRC_TCXO_V     0.0f                          // XTAL, no TCXO

#define PKT_SIZE        255                           // fixed packet length
#define SPI_FREQ_HZ     18000000UL                    // SPI0 clock to LR2021

// ─── Run control ──────────────────────────────────────────────────────
#define FIRST_WAIT_MS   15000     // wait this long for the first packet
#define IDLE_WAIT_MS    3000      // stop after this much packet silence
#define MAX_PACKETS     200000UL  // hard safety cap
#define REPORT_EVERY    100       // progress line cadence (packets)
#define SEQ_END_MARKER  0xDEADBEEFUL

// ─── LR2021 raw SPI opcodes (LR2021_commands.h; ESP32-verified) ───────
#define OPC_SET_RX              0x020C
#define OPC_GET_AND_CLEAR_IRQ   0x0117
#define OPC_GET_RX_PKT_LENGTH   0x0212
#define OPC_READ_RX_FIFO        0x0001

// SET_RX 3-byte timeout. 0x000000 = "Rx single mode, no timeout" (per
// LR2021_commands.h RX_TIMEOUT_NONE) — receive one packet, IRQ, then the
// firmware re-arms with another SET_RX. 0xFFFFFF is Rx continuous mode
// (what the ESP32 fast_rx used and did NOT re-arm between packets).
#define RX_TIMEOUT      0x000000UL

// IRQ status bits. The task's ESP32-verified finding: RX_DONE = bit 19.
// (The vendored RadioLib master header instead documents bit 18 as RX_DONE
// and 19 as TX_DONE.) We treat either as RX_DONE and count both, so the
// first live run shows which convention this silicon actually follows.
#define IRQ_RX_DONE_TASK  (1UL << 19)
#define IRQ_RX_DONE_HDR   (1UL << 18)
#define IRQ_TIMEOUT       (1UL << 21)
#define IRQ_CRC_ERROR     (1UL << 22)

// ─── Radio objects ────────────────────────────────────────────────────
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);
static ArduinoHal *hal = nullptr;
static Module *mod = nullptr;
static LR2021 *radio = nullptr;

static uint8_t pktbuf[PKT_SIZE];

// ─── Statistics ───────────────────────────────────────────────────────
struct RxStats {
    uint32_t received;      // total packets pulled from the FIFO
    uint32_t unique;        // packets with a new sequence number
    uint32_t duplicates;    // same seq as previous packet
    uint32_t bytes;         // sum of received packet lengths
    uint32_t first_seq;     // seq of first packet (TX starts at 0)
    uint32_t last_seq;
    uint32_t max_seq;
    uint32_t seq_resets;    // TX loop restarts (seq went backwards)
    uint32_t end_markers;   // DEADBEEF packets seen
    uint32_t irq_bit19;     // IRQ status had bit 19 set
    uint32_t irq_bit18;     // IRQ status had bit 18 set
    uint32_t crc_errors;
    uint32_t irq_timeouts;
    uint32_t bad_len;       // pkt length 0 or > PKT_SIZE (clamped)
    uint32_t min_proc_us, max_proc_us;   // IRQ pin → SET_RX re-arm done
    uint32_t min_fifo_us, max_fifo_us;   // IRQ pin → FIFO read done
    uint64_t sum_proc_us, sum_fifo_us;
    uint32_t start_ms, elapsed_ms;
    const char *stop_reason;
};
static RxStats S;

static void stats_reset() {
    memset(&S, 0, sizeof(S));
    S.min_proc_us = 0xFFFFFFFFUL;
    S.min_fifo_us = 0xFFFFFFFFUL;
    S.stop_reason = "none";
}

// ─── Raw SPI helpers (hot path — no RadioLib, no Serial) ──────────────

static inline void busy_wait() { while (digitalRead(PIN_BUSY) == HIGH) {} }
static inline void cs_low()    { digitalWrite(PIN_SPI_CS, LOW); }
static inline void cs_high()   { digitalWrite(PIN_SPI_CS, HIGH); }

// One CS assertion, two transfers: opcode bytes out, then data in/out.
// SPI.transfer(buf, len) is in-place (MISO overwrites buf) which is fine
// for both command output and data input.
static void raw_write(const uint8_t *cmd, size_t cmd_len) {
    busy_wait();
    cs_low();
    SPI.transfer(const_cast<uint8_t *>(cmd), cmd_len);
    cs_high();
}

static void raw_read(const uint8_t *cmd, size_t cmd_len,
                     uint8_t *data, size_t data_len) {
    busy_wait();
    cs_low();
    SPI.transfer(const_cast<uint8_t *>(cmd), cmd_len);
    SPI.transfer(data, data_len);
    cs_high();
}

static void raw_set_rx() {
    uint8_t cmd[5] = {
        (uint8_t)(OPC_SET_RX >> 8), (uint8_t)(OPC_SET_RX & 0xFF),
        (uint8_t)((RX_TIMEOUT >> 16) & 0xFF),
        (uint8_t)((RX_TIMEOUT >> 8) & 0xFF),
        (uint8_t)(RX_TIMEOUT & 0xFF),
    };
    raw_write(cmd, sizeof(cmd));
}

static uint32_t raw_get_and_clear_irq() {
    uint8_t cmd[2] = { (uint8_t)(OPC_GET_AND_CLEAR_IRQ >> 8),
                       (uint8_t)(OPC_GET_AND_CLEAR_IRQ & 0xFF) };
    uint8_t in[4] = { 0 };
    raw_read(cmd, sizeof(cmd), in, sizeof(in));
    return ((uint32_t)in[0] << 24) | ((uint32_t)in[1] << 16) |
           ((uint32_t)in[2] << 8) | (uint32_t)in[3];
}

static uint16_t raw_get_pkt_length() {
    uint8_t cmd[2] = { (uint8_t)(OPC_GET_RX_PKT_LENGTH >> 8),
                       (uint8_t)(OPC_GET_RX_PKT_LENGTH & 0xFF) };
    uint8_t in[2] = { 0 };
    raw_read(cmd, sizeof(cmd), in, sizeof(in));
    return (uint16_t)((in[0] << 8) | in[1]);
}

static void raw_read_fifo(uint8_t *buf, size_t len) {
    uint8_t cmd[2] = { (uint8_t)(OPC_READ_RX_FIFO >> 8),
                       (uint8_t)(OPC_READ_RX_FIFO & 0xFF) };
    raw_read(cmd, sizeof(cmd), buf, len);
}

// ─── Radio init via RadioLib (one-time, cold path) ────────────────────

static bool init_radio() {
    // SPI0 on our wiring: SCK=GP2, MOSI(TX)=GP3, MISO(RX)=GP4, CS=GP5.
    SPI.setRX(PIN_SPI_MISO);
    SPI.setTX(PIN_SPI_MOSI);
    SPI.setSCK(PIN_SPI_SCK);
    SPI.setCS(PIN_SPI_CS);

    pinMode(PIN_SPI_CS, OUTPUT);
    digitalWrite(PIN_SPI_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT_PULLDOWN);
    pinMode(PIN_RST, OUTPUT);
    digitalWrite(PIN_RST, HIGH);

    // Hardware reset (same timing as radio.cpp / ESP32 bringup)
    delay(10);
    digitalWrite(PIN_RST, LOW);
    delayMicroseconds(200);
    digitalWrite(PIN_RST, HIGH);
    delay(10);
    uint32_t t0 = millis();
    while (digitalRead(PIN_BUSY) == HIGH) {
        if (millis() - t0 > 1000) return false;
    }

    hal = new ArduinoHal(SPI, spiSettings);
    mod = new Module(hal, PIN_SPI_CS, PIN_IRQ, PIN_RST, PIN_BUSY);
    radio = new LR2021(mod);
    radio->irqDioNum = 9;              // IRQ routed on DIO9 (physical wiring)

    radio->standby();
    int16_t state = radio->beginFLRC(FLRC_FREQ_MHZ, FLRC_BR_KBPS, FLRC_CR,
                                     FLRC_PWR_DBM, FLRC_PREAMBLE, FLRC_SHAPING,
                                     FLRC_TCXO_V);
    if (state != RADIOLIB_ERR_NONE) {
        Serial.print("RADIO_INIT_FAILED code=");
        Serial.println(state);
        return false;
    }

    radio->fixedPacketLengthMode(PKT_SIZE);

    // Arm once through RadioLib: this configures the DIO9 IRQ routing
    // (RX_DONE → IRQ pin). The hot loop then drives the chip raw.
    state = radio->startReceive();
    if (state != RADIOLIB_ERR_NONE) {
        Serial.print("RADIO_START_RX_FAILED code=");
        Serial.println(state);
        return false;
    }
    return true;
}

// ─── RUN: the raw SPI receive loop ────────────────────────────────────

static void print_progress() {
    float elapsed = (float)S.elapsed_ms;
    float kbps = (elapsed > 0.0f) ? (float)S.bytes * 8.0f / elapsed : 0.0f;
    char b[96];
    snprintf(b, sizeof(b),
             "PROGRESS,recv=%lu,uniq=%lu,dup=%lu,last_seq=%lu,ms=%lu,kbps=%.1f",
             (unsigned long)S.received, (unsigned long)S.unique,
             (unsigned long)S.duplicates, (unsigned long)S.last_seq,
             (unsigned long)S.elapsed_ms, kbps);
    Serial.println(b);
}

static void print_results() {
    float elapsed = (float)S.elapsed_ms;
    float kbps = (elapsed > 0.0f) ? (float)S.bytes * 8.0f / elapsed : 0.0f;
    float avg_proc = (S.received > 0)
        ? (float)S.sum_proc_us / (float)S.received : 0.0f;
    float avg_fifo = (S.received > 0)
        ? (float)S.sum_fifo_us / (float)S.received : 0.0f;

    // Loss estimate from the TX sequence numbering: the TX sends seq
    // 0..N-1 per burst, so expected = max_seq + 1. Under-counts loss when
    // the TX loops (seq_resets > 1) — see seq_resets below.
    uint32_t expected = (S.max_seq > 0 || S.received > 0) ? S.max_seq + 1 : 0;
    float loss_pct = (expected > S.unique)
        ? 100.0f * (float)(expected - S.unique) / (float)expected : 0.0f;

    char b[128];
    Serial.println("=============================================");
    snprintf(b, sizeof(b), "  Stop reason: %s", S.stop_reason);
    Serial.println(b);
    snprintf(b, sizeof(b), "  Received:    %lu  (%lu bytes)",
             (unsigned long)S.received, (unsigned long)S.bytes);
    Serial.println(b);
    snprintf(b, sizeof(b), "  Unique:      %lu   Duplicates: %lu",
             (unsigned long)S.unique, (unsigned long)S.duplicates);
    Serial.println(b);
    snprintf(b, sizeof(b), "  Seq range:   %lu..%lu (resets=%lu)",
             (unsigned long)S.first_seq, (unsigned long)S.max_seq,
             (unsigned long)S.seq_resets);
    Serial.println(b);
    snprintf(b, sizeof(b), "  Loss:        %.2f %%  (vs max_seq+1)", loss_pct);
    Serial.println(b);
    snprintf(b, sizeof(b), "  Throughput:  %.1f kbps over %lu ms",
             kbps, (unsigned long)S.elapsed_ms);
    Serial.println(b);
    snprintf(b, sizeof(b), "  Proc time:   min=%lu avg=%.1f max=%lu us (IRQ->re-arm)",
             (unsigned long)S.min_proc_us, avg_proc,
             (unsigned long)S.max_proc_us);
    Serial.println(b);
    snprintf(b, sizeof(b), "  FIFO read:   min=%lu avg=%.1f max=%lu us (IRQ->read)",
             (unsigned long)S.min_fifo_us, avg_fifo,
             (unsigned long)S.max_fifo_us);
    Serial.println(b);
    snprintf(b, sizeof(b), "  IRQ bits:    b19=%lu b18=%lu crc_err=%lu tmo=%lu bad_len=%lu",
             (unsigned long)S.irq_bit19, (unsigned long)S.irq_bit18,
             (unsigned long)S.crc_errors, (unsigned long)S.irq_timeouts,
             (unsigned long)S.bad_len);
    Serial.println(b);
    Serial.println("=============================================");
    snprintf(b, sizeof(b),
             "RESULT_RX,%lu,%lu,%lu,%.2f,%.1f,%lu,%.1f,%lu",
             (unsigned long)S.received, (unsigned long)S.unique,
             (unsigned long)S.duplicates, loss_pct, kbps,
             (unsigned long)S.min_proc_us, avg_proc,
             (unsigned long)S.max_proc_us);
    Serial.println(b);
}

static void cmd_run() {
    stats_reset();
    Serial.println("RUN_START flrc=2450MHz/2600/uncoded/255B");
    Serial.println(F("PROGRESS,recv,uniq,dup,last_seq,ms,kbps"));

    SPI.beginTransaction(spiSettings);   // held for the whole run
    S.start_ms = millis();
    uint32_t last_pkt_ms = S.start_ms;
    uint32_t since_report = 0;

    raw_set_rx();

    for (;;) {
        uint32_t now = millis();
        S.elapsed_ms = now - S.start_ms;
        if (S.received == 0) {
            if (S.elapsed_ms > FIRST_WAIT_MS) { S.stop_reason = "first_timeout"; break; }
        } else if (now - last_pkt_ms > IDLE_WAIT_MS) {
            S.stop_reason = "idle_timeout"; break;
        }
        if (S.received >= MAX_PACKETS) { S.stop_reason = "packet_cap"; break; }

        // Fast path: poll the DIO9 IRQ pin — zero SPI cost while idle.
        if (digitalRead(PIN_IRQ) != HIGH) continue;

        uint32_t t_irq = micros();

        uint32_t status = raw_get_and_clear_irq();
        if (status & IRQ_RX_DONE_TASK) S.irq_bit19++;
        if (status & IRQ_RX_DONE_HDR)  S.irq_bit18++;
        if (status & IRQ_CRC_ERROR)    S.crc_errors++;
        if (status & IRQ_TIMEOUT)      S.irq_timeouts++;

        bool rx_done = (status & (IRQ_RX_DONE_TASK | IRQ_RX_DONE_HDR)) != 0;
        if (!rx_done) continue;          // some other IRQ source; already cleared

        uint16_t len = raw_get_pkt_length();
        if (len == 0 || len > PKT_SIZE) {
            S.bad_len++;
            len = PKT_SIZE;
        }
        raw_read_fifo(pktbuf, len);
        uint32_t t_fifo = micros();

        raw_set_rx();                    // re-arm before accounting
        uint32_t t_rearm = micros();

        uint32_t seq = ((uint32_t)pktbuf[0] << 24) | ((uint32_t)pktbuf[1] << 16) |
                       ((uint32_t)pktbuf[2] << 8) | (uint32_t)pktbuf[3];

        if (seq == SEQ_END_MARKER) {
            S.end_markers++;
            S.stop_reason = "end_marker";
            break;
        }

        S.received++;
        S.bytes += len;
        if (S.received == 1) {
            S.first_seq = seq;
        } else if (seq == S.last_seq) {
            S.duplicates++;
        } else {
            S.unique++;
        }
        if (seq < S.last_seq && S.received > 1) S.seq_resets++;   // TX burst restart
        S.last_seq = seq;
        if (seq > S.max_seq) S.max_seq = seq;

        uint32_t fifo_us = t_fifo - t_irq;
        uint32_t proc_us = t_rearm - t_irq;
        if (fifo_us < S.min_fifo_us) S.min_fifo_us = fifo_us;
        if (fifo_us > S.max_fifo_us) S.max_fifo_us = fifo_us;
        S.sum_fifo_us += fifo_us;
        if (proc_us < S.min_proc_us) S.min_proc_us = proc_us;
        if (proc_us > S.max_proc_us) S.max_proc_us = proc_us;
        S.sum_proc_us += proc_us;

        last_pkt_ms = now;
        if (++since_report >= REPORT_EVERY) {
            since_report = 0;
            digitalWrite(PIN_LED, !digitalRead(PIN_LED));
            print_progress();
        }
    }

    SPI.endTransaction();
    Serial.println("RUN_DONE");
    print_results();
}

// ─── CONFIG / HELP ────────────────────────────────────────────────────

static void cmd_config() {
    Serial.println(F("CONFIG:"));
    Serial.println(F("  radio   : LR2021 FLRC 2450.0 MHz, BR=2600 kbps, CR=1/0 (uncoded)"));
    Serial.println(F("  tx cfg  : +22 dBm, preamble=16, shaping=BT 0.5, TCXO off (XTAL)"));
    Serial.println(F("  packets : 255 bytes fixed length, seq = first 4 bytes BE"));
    Serial.println(F("  spi     : SPI0 18000000 Hz, MODE0"));
    Serial.println(F("  pins    : sck=GP2 mosi=GP3 miso=GP4 cs=GP5 busy=GP6 irq=GP7 rst=GP8"));
    Serial.println(F("  opcodes : set_rx=0x020C getclr_irq=0x0117 pkt_len=0x0212 rx_fifo=0x0001"));
    Serial.println(F("  rx mode : SET_RX timeout=0x000000 (single, re-arm per packet)"));
    Serial.println(F("  rx_done : IRQ bit 19 (bit 18 also counted — header docs differ)"));
    Serial.println(F("  end     : seq 0xDEADBEEF or idle timeout"));
}

static void cmd_help() {
    Serial.println(F("Commands (USB CDC, line-terminated):"));
    Serial.println(F("  RUN     start the FLRC RX speed test"));
    Serial.println(F("  CONFIG  show radio/SPI configuration"));
    Serial.println(F("  RESULTS print stats from the last run"));
    Serial.println(F("  HELP    this text"));
}

// ─── Arduino entry points ─────────────────────────────────────────────

void setup() {
    Serial.begin(115200);
    uint32_t t0 = millis();
    while (!Serial && millis() - t0 < 4000) {}   // USB CDC attach, max 4 s
    delay(100);

    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_LED, LOW);
    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_LED, HIGH); delay(150);
        digitalWrite(PIN_LED, LOW);  delay(150);
    }

    Serial.println(F("FLRC_RX_BOOT rp2040 flrc speed rx v1 (raw spi loop)"));

    stats_reset();
    if (!init_radio()) {
        Serial.println(F("HALT: radio init failed — check wiring / LR2021"));
        while (true) { delay(1000); }
    }
    Serial.println(F("RADIO_INIT_OK flrc=2450MHz br=2600 cr=1_0 pwr=22dBm pre=16 bt=0.5 pkt=255"));
    Serial.println(F("READY — send RUN / CONFIG / RESULTS / HELP"));
}

static char cmdbuf[32];
static size_t cmdlen = 0;

static void handle_command(const char *cmd) {
    if      (!strcmp(cmd, "RUN"))     cmd_run();
    else if (!strcmp(cmd, "CONFIG"))  cmd_config();
    else if (!strcmp(cmd, "RESULTS")) print_results();
    else if (!strcmp(cmd, "HELP"))    cmd_help();
    else {
        Serial.print(F("UNKNOWN command: "));
        Serial.println(cmd);
        cmd_help();
    }
}

void loop() {
    while (Serial.available() > 0) {
        char c = (char)Serial.read();
        if (c == '\r' || c == '\n') {
            if (cmdlen > 0) {
                cmdbuf[cmdlen] = '\0';
                handle_command(cmdbuf);
                cmdlen = 0;
            }
        } else if (cmdlen < sizeof(cmdbuf) - 1) {
            cmdbuf[cmdlen++] = toupper((int)c);
        }
    }
    delay(1);
}
