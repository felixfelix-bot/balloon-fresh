#pragma once

#include <stdint.h>

enum BenchMode { MODE_NONE, MODE_FLRC, MODE_LORA };
enum BenchRole { ROLE_NONE, ROLE_TX, ROLE_RX };

struct BenchConfig {
    BenchMode mode;
    float freq;
    uint16_t br;
    uint8_t sf;
    float bw;
    uint8_t cr;
    int8_t pwr;
    uint16_t pktSize;
    uint16_t pktCount;
    uint16_t txDelayMs;
    uint16_t preambleLen;
    BenchRole role;

    BenchConfig() :
        mode(MODE_FLRC), freq(868.0f), br(325), sf(9), bw(125.0f),
        cr(0x01), pwr(22), pktSize(50), pktCount(1000), txDelayMs(5),
        preambleLen(16), role(ROLE_NONE) {}
};

struct TxResults {
    uint32_t sent;
    uint32_t errors;
    uint32_t elapsedMs;
    float throughputKbps;
    float timePerPktMs;
    float pktRate;

    TxResults() : sent(0), errors(0), elapsedMs(0),
        throughputKbps(0), timePerPktMs(0), pktRate(0) {}
};

struct RxResults {
    uint32_t received;
    uint32_t crcErrors;
    uint32_t lost;
    uint32_t elapsedMs;
    float throughputKbps;
    float perPct;
    float berEstimatePct;
    float avgRssi;
    int16_t minRssi;
    int16_t maxRssi;
    float avgSnr;
    float minSnr;
    float maxSnr;
    uint32_t payloadCorrupt;
    uint32_t bitErrorsTotal;
    uint32_t bitsCheckedTotal;
    uint16_t burstLossMax;
    float burstLossAvg;
    uint32_t outOfOrder;
    uint32_t totalSentByTx;

    RxResults() : received(0), crcErrors(0), lost(0), elapsedMs(0),
        throughputKbps(0), perPct(0), berEstimatePct(0),
        avgRssi(0), minRssi(0), maxRssi(0),
        avgSnr(0), minSnr(0), maxSnr(0),
        payloadCorrupt(0), bitErrorsTotal(0), bitsCheckedTotal(0),
        burstLossMax(0), burstLossAvg(0), outOfOrder(0), totalSentByTx(0) {}
};
