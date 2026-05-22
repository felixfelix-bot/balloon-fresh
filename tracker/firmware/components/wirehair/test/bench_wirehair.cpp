#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <chrono>

extern "C" {
#include "wirehair/wirehair.h"
}

static double benchmark_encode(uint64_t msg_bytes, uint32_t block_bytes, int extra_blocks) {
    uint8_t *message = (uint8_t *)malloc(msg_bytes);
    for (uint64_t i = 0; i < msg_bytes; i++) message[i] = i & 0xFF;

    WirehairCodec enc = wirehair_encoder_create(0, message, msg_bytes, block_bytes);
    if (!enc) { free(message); return -1; }

    uint32_t N = (uint32_t)((msg_bytes + block_bytes - 1) / block_bytes);
    uint32_t total = N + extra_blocks;

    uint8_t *block = (uint8_t *)malloc(block_bytes);

    auto start = std::chrono::high_resolution_clock::now();

    for (uint32_t i = 0; i < total; i++) {
        uint32_t written = 0;
        wirehair_encode(enc, i, block, block_bytes, &written);
    }

    auto end = std::chrono::high_resolution_clock::now();

    double us = std::chrono::duration<double, std::micro>(end - start).count();

    wirehair_free(enc);
    free(block);
    free(message);

    return us / total;
}

static double benchmark_decode(uint64_t msg_bytes, uint32_t block_bytes, int extra_blocks, double loss_rate) {
    uint8_t *message = (uint8_t *)malloc(msg_bytes);
    for (uint64_t i = 0; i < msg_bytes; i++) message[i] = i ^ 0xAA;

    WirehairCodec enc = wirehair_encoder_create(0, message, msg_bytes, block_bytes);
    if (!enc) { free(message); return -1; }

    uint32_t N = (uint32_t)((msg_bytes + block_bytes - 1) / block_bytes);

    WirehairCodec dec = wirehair_decoder_create(0, msg_bytes, block_bytes);
    if (!dec) { wirehair_free(enc); free(message); return -1; }

    uint8_t *block = (uint8_t *)malloc(block_bytes);
    uint32_t block_id = 0;
    int received = 0;

    auto start = std::chrono::high_resolution_clock::now();

    while (true) {
        if (((double)rand() / RAND_MAX) >= loss_rate || block_id < N) {
            uint32_t written = 0;
            wirehair_encode(enc, block_id, block, block_bytes, &written);

            WirehairResult r = wirehair_decode(dec, block_id, block, written);
            received++;

            if (r == Wirehair_Success) break;
        }
        block_id++;
    }

    auto end = std::chrono::high_resolution_clock::now();

    uint8_t *output = (uint8_t *)malloc(msg_bytes);
    wirehair_recover(dec, output, msg_bytes);

    int ok = (memcmp(message, output, msg_bytes) == 0);

    double us = std::chrono::duration<double, std::micro>(end - start).count();

    wirehair_free(enc);
    wirehair_free(dec);
    free(block);
    free(message);
    free(output);

    return ok ? (us / received) : -1;
}

struct bench_config {
    const char *name;
    uint64_t msg_bytes;
    uint32_t block_bytes;
    int extra;
};

int main(void) {
    if (wirehair_init() != Wirehair_Success) {
        printf("wirehair_init() failed\n");
        return 1;
    }

    printf("\n=== Wirehair x86 Benchmark ===\n");
    printf("(Extrapolate to ESP32-C3 RISC-V 80 MHz: ~3-5x slower)\n\n");

    struct bench_config configs[] = {
        {"28B telemetry",     28,   28,  0},
        {"100B short msg",   100,   50,  1},
        {"200B Nostr event", 200,   80,  2},
        {"500B Nostr event", 500,  120,  3},
        {"1KB mesh payload", 1024, 128,  5},
        {"2KB bulk data",    2048, 128,  8},
        {"4KB max block",    4096, 128, 16},
    };

    printf("%-22s %6s %5s %5s %10s %10s %10s\n",
           "Scenario", "MsgB", "Blk", "N", "Enc us/blk", "Dec us/blk", "ESP32 est");
    printf("%-22s %6s %5s %5s %10s %10s %10s\n",
           "", "", "", "", "", "", "(4x slower)");
    printf("─────────────────────────────────────────────────────────────────────\n");

    for (auto &c : configs) {
        uint32_t N = (uint32_t)((c.msg_bytes + c.block_bytes - 1) / c.block_bytes);

        double enc_us = benchmark_encode(c.msg_bytes, c.block_bytes, c.extra);
        double dec_us = benchmark_decode(c.msg_bytes, c.block_bytes, c.extra, 0.2);

        printf("%-22s %6lu %5u %5u %9.1f  %9.1f  %9.1f\n",
               c.name, (unsigned long)c.msg_bytes, c.block_bytes, N,
               enc_us, dec_us, dec_us * 4);
    }

    printf("\n--- Loss recovery at 30%% loss ---\n\n");

    printf("%-22s %5s %10s %10s %s\n",
           "Scenario", "Blks", "Dec us", "ESP32 us", "Result");
    printf("──────────────────────────────────────────────────────────\n");

    struct bench_config loss_configs[] = {
        {"200B @ 30%% loss", 200,  80, 3},
        {"500B @ 30%% loss", 500, 120, 5},
        {"1KB  @ 30%% loss", 1024, 128, 8},
    };

    for (auto &c : loss_configs) {
        uint32_t N = (uint32_t)((c.msg_bytes + c.block_bytes - 1) / c.block_bytes);

        uint8_t *message = (uint8_t *)malloc(c.msg_bytes);
        for (uint64_t i = 0; i < c.msg_bytes; i++) message[i] = i & 0xFF;

        WirehairCodec enc = wirehair_encoder_create(0, message, c.msg_bytes, c.block_bytes);
        WirehairCodec dec = wirehair_decoder_create(0, c.msg_bytes, c.block_bytes);

        uint8_t *block = (uint8_t *)malloc(c.block_bytes);
        int received = 0;
        uint32_t block_id = 0;

        auto start = std::chrono::high_resolution_clock::now();

        while (true) {
            if (block_id < N || ((double)rand() / RAND_MAX) >= 0.3) {
                uint32_t written = 0;
                wirehair_encode(enc, block_id, block, c.block_bytes, &written);
                WirehairResult r = wirehair_decode(dec, block_id, block, written);
                received++;
                if (r == Wirehair_Success) break;
            }
            block_id++;
        }

        auto end = std::chrono::high_resolution_clock::now();
        double us = std::chrono::duration<double, std::micro>(end - start).count();

        uint8_t *output = (uint8_t *)malloc(c.msg_bytes);
        wirehair_recover(dec, output, c.msg_bytes);
        int ok = (memcmp(message, output, c.msg_bytes) == 0);

        printf("%-22s %5d %9.0f  %9.0f  %s\n",
               c.name, received, us, us * 4, ok ? "PASS" : "FAIL");

        wirehair_free(enc);
        wirehair_free(dec);
        free(block);
        free(message);
        free(output);
    }

    printf("\n--- RAM usage estimate (ESP32-C3 has 400 KB SRAM) ---\n\n");
    printf("Wirehair requires: N * block_bytes for recovery blocks\n");
    printf("Plus: N * ~100 bytes for peel state, GE matrix workspace\n");
    printf("Total estimate: N * (block_bytes + 200)\n\n");

    for (auto &c : configs) {
        uint32_t N = (uint32_t)((c.msg_bytes + c.block_bytes - 1) / c.block_bytes);
        uint32_t ram = N * (c.block_bytes + 200);
        printf("  %-22s N=%-4u ~%u KB %s\n",
               c.name, N, ram / 1024,
               ram > 400000 ? "EXCEEDS SRAM" : "OK");
    }

    printf("\n=== Benchmark complete ===\n");
    return 0;
}
