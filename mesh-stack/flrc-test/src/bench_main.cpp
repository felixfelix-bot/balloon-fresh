#include <Arduino.h>
#include "EspIdfHal.h"
#include "prbs.h"
#include "config.h"

#define LR2021_SCK  6
#define LR2021_MISO 2
#define LR2021_MOSI 7
#define LR2021_CS   10
#define LR2021_IRQ  5
#define LR2021_RST  3
#define LR2021_BUSY 4

static EspIdfHal hal(LR2021_SCK, LR2021_MISO, LR2021_MOSI);
static Module mod(&hal, LR2021_CS, LR2021_IRQ, LR2021_RST, LR2021_BUSY);
static LR2021 radio(&mod);

static BenchConfig cfg;
static volatile bool rxFlag = false;
static bool running = false;
static bool done = false;
static bool radioInited = false;

static TxResults txRes;
static RxResults rxRes;

#define MAX_PACKETS 65535
static uint8_t *rxBitfield = nullptr;
static uint32_t rxBitfieldSize = 0;

static int32_t rssiSum = 0;
static float snrSum = 0;
static uint32_t rssiCount = 0;
static int16_t rssiMin = 32767;
static int16_t rssiMax = -32768;
static float snrMin = 999.0f;
static float snrMax = -999.0f;
static uint32_t lastRxSeq = 0xFFFFFFFF;
static uint16_t currentBurstLen = 0;
static uint32_t totalBurstLen = 0;
static uint32_t burstCount = 0;
static uint32_t rxStartTime = 0;
static uint32_t txStartTime = 0;
static uint32_t txCurrentPkt = 0;

static void IRAM_ATTR onRxIrq(void) {
    rxFlag = true;
}

static void initRadio() {
    int16_t state;
    if (cfg.mode == MODE_FLRC) {
        state = radio.beginFLRC(cfg.freq, cfg.br, cfg.cr, cfg.pwr, cfg.preambleLen, RADIOLIB_SHAPING_0_5, 0.0f);
    } else {
        state = radio.begin(cfg.freq, cfg.bw, cfg.sf, cfg.cr,
                           RADIOLIB_LR2021_LORA_SYNC_WORD_PRIVATE,
                           cfg.pwr, cfg.preambleLen, 0.0f);
    }
    if (state != RADIOLIB_ERR_NONE) {
        Serial.printf("ERR: Radio init failed: %d\n", state);
        radioInited = false;
        return;
    }
    radioInited = true;
    Serial.printf("OK: Radio init %s %.1f MHz", cfg.mode == MODE_FLRC ? "FLRC" : "LoRa", cfg.freq);
    if (cfg.mode == MODE_FLRC) {
        Serial.printf(" BR=%d CR=0x%02X", cfg.br, cfg.cr);
    } else {
        Serial.printf(" SF%d BW=%.0f CR=%d", cfg.sf, cfg.bw, cfg.cr);
    }
    Serial.printf(" PWR=%d SIZE=%d COUNT=%d DELAY=%d\n", cfg.pwr, cfg.pktSize, cfg.pktCount, cfg.txDelayMs);
}

static void resetCounters() {
    txRes = TxResults();
    rxRes = RxResults();
    rssiSum = 0;
    snrSum = 0;
    rssiCount = 0;
    rssiMin = 32767;
    rssiMax = -32768;
    snrMin = 999.0f;
    snrMax = -999.0f;
    lastRxSeq = 0xFFFFFFFF;
    currentBurstLen = 0;
    totalBurstLen = 0;
    burstCount = 0;
    rxStartTime = 0;
    txStartTime = 0;
    txCurrentPkt = 0;
    if (rxBitfield) {
        memset(rxBitfield, 0, rxBitfieldSize);
    }
}

static void allocBitfield() {
    if (rxBitfield) {
        free(rxBitfield);
        rxBitfield = nullptr;
    }
    rxBitfieldSize = (cfg.pktCount + 7) / 8;
    rxBitfield = (uint8_t *)calloc(rxBitfieldSize, 1);
    if (!rxBitfield) {
        Serial.println("ERR: Out of memory for seq bitfield");
    }
}

static void setSeqBit(uint32_t seq) {
    if (seq < cfg.pktCount && rxBitfield) {
        rxBitfield[seq / 8] |= (1 << (seq % 8));
    }
}

static void startRx() {
    resetCounters();
    allocBitfield();
    radio.setPacketReceivedAction(onRxIrq);
    rxStartTime = millis();
    radio.startReceive();
    running = true;
    done = false;
    Serial.println("OK: RX started");
}

static void processRxPacket() {
    int16_t len = radio.getPacketLength();
    if (len <= 0) {
        radio.standby();
        radio.startReceive();
        return;
    }

    uint8_t buf[256];
    int16_t state = radio.readData(buf, len);

    if (len == 8 && buf[0] == 0xDE && buf[1] == 0xAD && buf[2] == 0xBE && buf[3] == 0xEF) {
        rxRes.totalSentByTx = (uint32_t)buf[4] << 24 | (uint32_t)buf[5] << 16 |
                              (uint32_t)buf[6] << 8 | (uint32_t)buf[7];
        rxRes.elapsedMs = millis() - rxStartTime;
        running = false;
        done = true;
        radio.standby();
        return;
    }

    if (state != RADIOLIB_ERR_NONE) {
        rxRes.crcErrors++;
        radio.standby();
        radio.startReceive();
        return;
    }

    if (len < 4) {
        radio.standby();
        radio.startReceive();
        return;
    }

    uint32_t seq = (uint32_t)buf[0] << 24 | (uint32_t)buf[1] << 16 |
                   (uint32_t)buf[2] << 8 | (uint32_t)buf[3];

    float rssi = radio.getRSSI(false);
    int16_t rssi_i = (int16_t)(rssi);
    float snr = 0;
    if (cfg.mode == MODE_LORA) {
        snr = radio.getSNR();
    }

    rssiSum += rssi_i;
    snrSum += snr;
    rssiCount++;
    if (rssi_i < rssiMin) rssiMin = rssi_i;
    if (rssi_i > rssiMax) rssiMax = rssi_i;
    if (snr < snrMin) snrMin = snr;
    if (snr > snrMax) snrMax = snr;

    setSeqBit(seq);

    if (lastRxSeq != 0xFFFFFFFF && seq != lastRxSeq + 1) {
        if (seq < lastRxSeq) {
            rxRes.outOfOrder++;
        } else {
            uint32_t gap = seq - lastRxSeq - 1;
            if (gap > rxRes.burstLossMax) rxRes.burstLossMax = (uint16_t)gap;
            currentBurstLen += gap;
            totalBurstLen += gap;
            burstCount++;
        }
    }
    lastRxSeq = seq;

    if (len > 4) {
        uint16_t bytesBad = 0;
        uint16_t bitErr = prbs15_verify(buf + 4, len - 4, seq, &bytesBad);
        if (bitErr > 0) {
            rxRes.payloadCorrupt++;
            rxRes.bitErrorsTotal += bitErr;
        }
        rxRes.bitsCheckedTotal += (len - 4) * 8;
    }

    rxRes.received++;
    if (rxRes.received % 100 == 0) {
        Serial.printf("RX: %lu pkts, RSSI=%.0f, SNR=%.1f, seq=%lu\n",
                      (unsigned long)rxRes.received, rssi, snr, (unsigned long)seq);
    }

    radio.standby();
    radio.startReceive();
}

static void startTx() {
    resetCounters();
    txStartTime = millis();
    txCurrentPkt = 0;
    running = true;
    done = false;
    Serial.printf("TX: Starting %d pkts in 2s...\n", cfg.pktCount);
    delay(2000);
    txStartTime = millis();
}

static void txNextPacket() {
    if (txCurrentPkt >= cfg.pktCount) {
        uint8_t endBuf[8] = {0xDE, 0xAD, 0xBE, 0xEF,
                             (uint8_t)(txRes.sent >> 24), (uint8_t)(txRes.sent >> 16),
                             (uint8_t)(txRes.sent >> 8), (uint8_t)(txRes.sent)};
        radio.transmit(endBuf, 8);
        txRes.elapsedMs = millis() - txStartTime;
        running = false;
        done = true;
        Serial.println("TX: End marker sent");
        return;
    }

    uint8_t buf[255];
    buf[0] = (txCurrentPkt >> 24) & 0xFF;
    buf[1] = (txCurrentPkt >> 16) & 0xFF;
    buf[2] = (txCurrentPkt >> 8) & 0xFF;
    buf[3] = txCurrentPkt & 0xFF;
    if (cfg.pktSize > 4) {
        prbs15_fill(buf + 4, cfg.pktSize - 4, txCurrentPkt);
    }

    int16_t state = radio.transmit(buf, cfg.pktSize);
    if (state == RADIOLIB_ERR_NONE) {
        txRes.sent++;
    } else {
        txRes.errors++;
        if (txRes.errors <= 10 || txRes.errors % 100 == 0) {
            Serial.printf("TX: error %d at pkt %lu: %d\n", (int)txRes.errors, (unsigned long)txCurrentPkt, state);
        }
    }

    txCurrentPkt++;
    if (txCurrentPkt % 100 == 0) {
        Serial.printf("TX: %lu/%d\n", (unsigned long)txCurrentPkt, cfg.pktCount);
    }

    if (cfg.txDelayMs > 0) {
        delay(cfg.txDelayMs);
    }
}

static void printResults() {
    if (cfg.role == ROLE_TX && done) {
        float sec = txRes.elapsedMs / 1000.0f;
        if (txRes.sent > 0 && sec > 0) {
            txRes.throughputKbps = (txRes.sent * cfg.pktSize * 8.0f) / (sec * 1000.0f);
            txRes.timePerPktMs = txRes.elapsedMs / (float)txRes.sent;
            txRes.pktRate = txRes.sent / sec;
        }
        Serial.println("=== TX RESULTS ===");
        Serial.printf("sent,%lu\n", (unsigned long)txRes.sent);
        Serial.printf("tx_errors,%lu\n", (unsigned long)txRes.errors);
        Serial.printf("elapsed_ms,%lu\n", (unsigned long)txRes.elapsedMs);
        Serial.printf("throughput_kbps,%.1f\n", txRes.throughputKbps);
        Serial.printf("time_per_pkt_ms,%.2f\n", txRes.timePerPktMs);
        Serial.printf("pkt_rate,%.1f\n", txRes.pktRate);
        Serial.println("=== TX END ===");
        done = false;
    }

    if (cfg.role == ROLE_RX && done) {
        float sec = rxRes.elapsedMs / 1000.0f;
        uint32_t total = rxRes.totalSentByTx > 0 ? rxRes.totalSentByTx : rxRes.received;
        rxRes.lost = total > rxRes.received ? total - rxRes.received : 0;
        if (total > 0) rxRes.perPct = (rxRes.lost * 100.0f) / total;
        if (sec > 0) rxRes.throughputKbps = (rxRes.received * cfg.pktSize * 8.0f) / (sec * 1000.0f);
        if (rxRes.bitsCheckedTotal > 0) {
            rxRes.berEstimatePct = (rxRes.bitErrorsTotal * 100.0f) / rxRes.bitsCheckedTotal;
        }
        if (rssiCount > 0) rxRes.avgRssi = (float)rssiSum / rssiCount;
        rxRes.minRssi = rssiMin == 32767 ? 0 : rssiMin;
        rxRes.maxRssi = rssiMax == -32768 ? 0 : rssiMax;
        if (rssiCount > 0) rxRes.avgSnr = snrSum / rssiCount;
        rxRes.minSnr = snrMin == 999.0f ? 0 : snrMin;
        rxRes.maxSnr = snrMax == -999.0f ? 0 : snrMax;
        if (burstCount > 0) rxRes.burstLossAvg = (float)totalBurstLen / burstCount;

        Serial.println("=== RX RESULTS ===");
        Serial.printf("received,%lu\n", (unsigned long)rxRes.received);
        Serial.printf("crc_errors,%lu\n", (unsigned long)rxRes.crcErrors);
        Serial.printf("lost,%lu\n", (unsigned long)rxRes.lost);
        Serial.printf("total_sent_by_tx,%lu\n", (unsigned long)rxRes.totalSentByTx);
        Serial.printf("elapsed_ms,%lu\n", (unsigned long)rxRes.elapsedMs);
        Serial.printf("throughput_kbps,%.1f\n", rxRes.throughputKbps);
        Serial.printf("per_pct,%.3f\n", rxRes.perPct);
        Serial.printf("ber_estimate_pct,%.6f\n", rxRes.berEstimatePct);
        Serial.printf("avg_rssi,%.1f\n", rxRes.avgRssi);
        Serial.printf("min_rssi,%d\n", rxRes.minRssi);
        Serial.printf("max_rssi,%d\n", rxRes.maxRssi);
        Serial.printf("avg_snr,%.1f\n", rxRes.avgSnr);
        Serial.printf("min_snr,%.1f\n", rxRes.minSnr);
        Serial.printf("max_snr,%.1f\n", rxRes.maxSnr);
        Serial.printf("payload_corrupt,%lu\n", (unsigned long)rxRes.payloadCorrupt);
        Serial.printf("bit_errors_total,%lu\n", (unsigned long)rxRes.bitErrorsTotal);
        Serial.printf("bits_checked_total,%lu\n", (unsigned long)rxRes.bitsCheckedTotal);
        Serial.printf("burst_loss_max,%d\n", rxRes.burstLossMax);
        Serial.printf("burst_loss_avg,%.1f\n", rxRes.burstLossAvg);
        Serial.printf("out_of_order,%lu\n", (unsigned long)rxRes.outOfOrder);
        Serial.println("=== RX END ===");

        if (rxBitfield && rxRes.totalSentByTx > 0) {
            Serial.print("SEQGAPS:");
            bool inGap = false;
            uint32_t gapStart = 0;
            for (uint32_t i = 0; i < rxRes.totalSentByTx && i < cfg.pktCount; i++) {
                bool received = rxBitfield[i / 8] & (1 << (i % 8));
                if (!received && !inGap) {
                    gapStart = i;
                    inGap = true;
                } else if (received && inGap) {
                    if (gapStart == i - 1) {
                        Serial.printf(" %lu", gapStart);
                    } else {
                        Serial.printf(" %lu-%lu", gapStart, i - 1);
                    }
                    inGap = false;
                }
            }
            if (inGap) {
                if (gapStart <= cfg.pktCount - 2) {
                    Serial.printf(" %lu-%lu", gapStart, cfg.pktCount - 1);
                } else {
                    Serial.printf(" %lu", gapStart);
                }
            }
            Serial.println();
        }
        done = false;
    }
}

static void printCsvHeader() {
    Serial.println("test_id,mode,freq_mhz,br_kbps,sf,bw_khz,cr,pwr_dbm,pkt_size,pkt_count,tx_delay_ms,"
                    "tx_sent,tx_errors,tx_elapsed_ms,tx_throughput_kbps,tx_time_per_pkt_ms,"
                    "rx_received,rx_crc_errors,rx_lost,rx_elapsed_ms,rx_throughput_kbps,"
                    "per_pct,ber_estimate_pct,"
                    "avg_rssi,min_rssi,max_rssi,avg_snr,min_snr,max_snr,"
                    "payload_corrupt,bit_errors_total,bits_checked_total,"
                    "burst_loss_max,burst_loss_avg,out_of_order,distance_m,notes");
}

static void printConfig() {
    Serial.printf("mode=%s freq=%.1f ", cfg.mode == MODE_FLRC ? "FLRC" : "LORA", cfg.freq);
    if (cfg.mode == MODE_FLRC) {
        Serial.printf("br=%d cr=0x%02X ", cfg.br, cfg.cr);
    } else {
        Serial.printf("sf=%d bw=%.0f cr=%d ", cfg.sf, cfg.bw, cfg.cr);
    }
    Serial.printf("pwr=%d size=%d count=%d delay=%d role=%s\n",
                  cfg.pwr, cfg.pktSize, cfg.pktCount, cfg.txDelayMs,
                  cfg.role == ROLE_TX ? "TX" : cfg.role == ROLE_RX ? "RX" : "NONE");
}

static char cmdBuf[128];
static uint8_t cmdIdx = 0;

static void processCommand(const char *cmd) {
    while (*cmd == ' ' || *cmd == '\t') cmd++;
    if (strlen(cmd) == 0) return;

    if (strcmp(cmd, "CONFIG") == 0) {
        printConfig();
    } else if (strcmp(cmd, "CSVHEADER") == 0) {
        printCsvHeader();
    } else if (strcmp(cmd, "STATUS") == 0) {
        Serial.printf("state=%s radio=%s\n",
                      running ? "RUNNING" : "IDLE",
                      radioInited ? "OK" : "NOT_INIT");
    } else if (strcmp(cmd, "RESULTS") == 0) {
        printResults();
    } else if (strncmp(cmd, "MODE ", 5) == 0) {
        if (strcmp(cmd + 5, "FLRC") == 0) cfg.mode = MODE_FLRC;
        else if (strcmp(cmd + 5, "LORA") == 0) cfg.mode = MODE_LORA;
        else Serial.printf("ERR: Unknown mode '%s'\n", cmd + 5);
    } else if (strncmp(cmd, "FREQ ", 5) == 0) {
        cfg.freq = atof(cmd + 5);
    } else if (strncmp(cmd, "BR ", 3) == 0) {
        cfg.br = atoi(cmd + 3);
    } else if (strncmp(cmd, "SF ", 3) == 0) {
        cfg.sf = atoi(cmd + 3);
    } else if (strncmp(cmd, "BW ", 3) == 0) {
        cfg.bw = atof(cmd + 3);
    } else if (strncmp(cmd, "CR ", 3) == 0) {
        cfg.cr = (uint8_t)strtol(cmd + 3, nullptr, 0);
    } else if (strncmp(cmd, "PWR ", 4) == 0) {
        cfg.pwr = atoi(cmd + 4);
    } else if (strncmp(cmd, "SIZE ", 5) == 0) {
        cfg.pktSize = atoi(cmd + 5);
    } else if (strncmp(cmd, "COUNT ", 6) == 0) {
        cfg.pktCount = atoi(cmd + 6);
    } else if (strncmp(cmd, "DELAY ", 6) == 0) {
        cfg.txDelayMs = atoi(cmd + 6);
    } else if (strncmp(cmd, "PREAMBLE ", 9) == 0) {
        cfg.preambleLen = atoi(cmd + 9);
    } else if (strncmp(cmd, "ROLE ", 5) == 0) {
        if (strcmp(cmd + 5, "TX") == 0) cfg.role = ROLE_TX;
        else if (strcmp(cmd + 5, "RX") == 0) cfg.role = ROLE_RX;
        else Serial.printf("ERR: Unknown role '%s'\n", cmd + 5);
    } else if (strcmp(cmd, "RUN") == 0) {
        if (running) {
            Serial.println("ERR: Already running");
            return;
        }
        initRadio();
        if (!radioInited) return;
        if (cfg.role == ROLE_TX) startTx();
        else if (cfg.role == ROLE_RX) startRx();
        else Serial.println("ERR: Set ROLE first");
    } else if (strcmp(cmd, "STOP") == 0) {
        running = false;
        radio.standby();
        Serial.println("OK: Stopped");
    } else if (strcmp(cmd, "HELP") == 0) {
        Serial.println("Commands: MODE FLRC|LORA, FREQ, BR, SF, BW, CR, PWR, SIZE, COUNT, DELAY, PREAMBLE, ROLE TX|RX, RUN, STOP, CONFIG, RESULTS, CSVHEADER, STATUS, SEQLOG, HELP");
    } else {
        Serial.printf("ERR: Unknown command '%s'\n", cmd);
    }
}

void setup() {
    Serial.begin(115200);
    delay(2000);
    Serial.println("=== LR2021 Benchmarker v1.0 ===");
    Serial.println("Type HELP for commands");
}

void loop() {
    while (Serial.available()) {
        char c = Serial.read();
        if (c == '\n' || c == '\r') {
            if (cmdIdx > 0) {
                cmdBuf[cmdIdx] = '\0';
                processCommand(cmdBuf);
                cmdIdx = 0;
            }
        } else if (cmdIdx < sizeof(cmdBuf) - 1) {
            cmdBuf[cmdIdx++] = c;
        }
    }

    if (running) {
        if (cfg.role == ROLE_TX) {
            txNextPacket();
        }
        if (cfg.role == ROLE_RX && rxFlag) {
            rxFlag = false;
            processRxPacket();
        }
    }

    if (done) {
        printResults();
    }
}
