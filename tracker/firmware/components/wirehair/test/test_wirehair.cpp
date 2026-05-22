#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

extern "C" {
#include "wirehair/wirehair.h"
}

static int g_pass = 0;
static int g_fail = 0;

#define TEST(name) printf("  TEST: %s ... ", name)
#define PASS() do { printf("PASS\n"); g_pass++; } while(0)
#define FAIL(msg) do { printf("FAIL: %s\n", msg); g_fail++; } while(0)
#define CHECK(cond, msg) do { if (!(cond)) { FAIL(msg); return; } } while(0)

static void test_init(void) {
    TEST("wirehair_init succeeds");
    WirehairResult r = wirehair_init();
    if (r == Wirehair_Success) PASS(); else FAIL("init returned non-success");
}

static void test_encode_decode_small(void) {
    TEST("encode+decode 28B telemetry (N=1 returns null, as documented)");
    WirehairCodec enc = wirehair_encoder_create(0, "test_28_bytes_padding_here", 28, 28);
    if (enc == nullptr) {
        PASS();
    } else {
        wirehair_free(enc);
        FAIL("N=1 should fail per Wirehair API (N >= 2 required)");
    }
}

static void test_encode_decode_two_block(void) {
    TEST("encode+decode 50B with 25B blocks (systematic, N=2)");
    const uint64_t msg_bytes = 50;
    const uint32_t block_bytes = 25;
    uint8_t message[50];
    for (int i = 0; i < 50; i++) message[i] = i ^ 0x55;

    WirehairCodec enc = wirehair_encoder_create(0, message, msg_bytes, block_bytes);
    CHECK(enc != nullptr, "encoder create failed");

    WirehairCodec dec = wirehair_decoder_create(0, msg_bytes, block_bytes);
    CHECK(dec != nullptr, "decoder create failed");

    uint8_t block[25];
    WirehairResult r = Wirehair_NeedMore;
    for (uint32_t i = 0; i < 2 && r != Wirehair_Success; i++) {
        uint32_t written = 0;
        wirehair_encode(enc, i, block, block_bytes, &written);
        r = wirehair_decode(dec, i, block, written);
    }
    CHECK(r == Wirehair_Success, "decode should succeed with 2 blocks");

    uint8_t output[50];
    r = wirehair_recover(dec, output, msg_bytes);
    CHECK(r == Wirehair_Success, "recover failed");
    CHECK(memcmp(message, output, msg_bytes) == 0, "data mismatch");

    wirehair_free(enc);
    wirehair_free(dec);
    PASS();
}

static void test_encode_decode_multi_block(void) {
    TEST("encode+decode 200B with 50B blocks, 0% loss");
    const uint64_t msg_bytes = 200;
    const uint32_t block_bytes = 50;
    uint8_t *message = (uint8_t *)malloc(msg_bytes);
    for (uint64_t i = 0; i < msg_bytes; i++) message[i] = (uint8_t)(i * 7 + 3);

    WirehairCodec enc = wirehair_encoder_create(0, message, msg_bytes, block_bytes);
    CHECK(enc != nullptr, "encoder create failed");

    WirehairCodec dec = wirehair_decoder_create(0, msg_bytes, block_bytes);
    CHECK(dec != nullptr, "decoder create failed");

    uint32_t N = (uint32_t)((msg_bytes + block_bytes - 1) / block_bytes);

    uint8_t *block = (uint8_t *)malloc(block_bytes);
    WirehairResult r = Wirehair_NeedMore;
    for (uint32_t i = 0; i < N && r != Wirehair_Success; i++) {
        uint32_t written = 0;
        wirehair_encode(enc, i, block, block_bytes, &written);
        r = wirehair_decode(dec, i, block, written);
    }
    CHECK(r == Wirehair_Success, "decode should succeed after N blocks");

    uint8_t *output = (uint8_t *)malloc(msg_bytes);
    r = wirehair_recover(dec, output, msg_bytes);
    CHECK(r == Wirehair_Success, "recover failed");
    CHECK(memcmp(message, output, msg_bytes) == 0, "data mismatch");

    wirehair_free(enc);
    wirehair_free(dec);
    free(block);
    free(message);
    free(output);
    PASS();
}

static void test_loss_recovery(void) {
    TEST("encode+decode 500B with 100B blocks, 30% loss");
    const uint64_t msg_bytes = 500;
    const uint32_t block_bytes = 100;
    uint8_t *message = (uint8_t *)malloc(msg_bytes);
    for (uint64_t i = 0; i < msg_bytes; i++) message[i] = (uint8_t)(i ^ 0xAA);

    WirehairCodec enc = wirehair_encoder_create(0, message, msg_bytes, block_bytes);
    CHECK(enc != nullptr, "encoder create failed");

    WirehairCodec dec = wirehair_decoder_create(0, msg_bytes, block_bytes);
    CHECK(dec != nullptr, "decoder create failed");

    uint32_t N = (uint32_t)((msg_bytes + block_bytes - 1) / block_bytes);
    srand(42);

    uint8_t *block = (uint8_t *)malloc(block_bytes);
    WirehairResult r = Wirehair_NeedMore;
    uint32_t block_id = 0;
    int received = 0;

    while (r != Wirehair_Success && block_id < N + 20) {
        if ((double)rand() / RAND_MAX >= 0.3 || block_id < N) {
            uint32_t written = 0;
            wirehair_encode(enc, block_id, block, block_bytes, &written);
            r = wirehair_decode(dec, block_id, block, written);
            received++;
        }
        block_id++;
    }
    CHECK(r == Wirehair_Success, "decode should eventually succeed");

    uint8_t *output = (uint8_t *)malloc(msg_bytes);
    r = wirehair_recover(dec, output, msg_bytes);
    CHECK(r == Wirehair_Success, "recover failed");
    CHECK(memcmp(message, output, msg_bytes) == 0, "data mismatch after loss");

    wirehair_free(enc);
    wirehair_free(dec);
    free(block);
    free(message);
    free(output);
    PASS();
}

static void test_recover_single_block(void) {
    TEST("wirehair_recover_block for single missing block");
    const uint64_t msg_bytes = 300;
    const uint32_t block_bytes = 100;
    uint8_t *message = (uint8_t *)malloc(msg_bytes);
    for (uint64_t i = 0; i < msg_bytes; i++) message[i] = (uint8_t)(i + 17);

    WirehairCodec enc = wirehair_encoder_create(0, message, msg_bytes, block_bytes);
    CHECK(enc != nullptr, "encoder create failed");

    WirehairCodec dec = wirehair_decoder_create(0, msg_bytes, block_bytes);
    CHECK(dec != nullptr, "decoder create failed");

    uint32_t N = (uint32_t)((msg_bytes + block_bytes - 1) / block_bytes);

    uint8_t *block = (uint8_t *)malloc(block_bytes);
    WirehairResult r = Wirehair_NeedMore;
    for (uint32_t i = 0; i < N + 2 && r != Wirehair_Success; i++) {
        if (i == 1) continue;
        uint32_t written = 0;
        wirehair_encode(enc, i, block, block_bytes, &written);
        r = wirehair_decode(dec, i, block, written);
    }
    CHECK(r == Wirehair_Success, "decode should succeed with extra blocks");

    uint8_t recovered[100];
    uint32_t bytes_out = 0;
    r = wirehair_recover_block(dec, 1, recovered, &bytes_out);
    CHECK(r == Wirehair_Success, "recover_block failed");
    CHECK(bytes_out <= block_bytes, "bytes_out too large");
    CHECK(memcmp(recovered, message + 1 * block_bytes, block_bytes) == 0,
          "recovered block mismatch");

    wirehair_free(enc);
    wirehair_free(dec);
    free(block);
    free(message);
    PASS();
}

static void test_decoder_becomes_encoder(void) {
    TEST("decoder_becomes_encoder roundtrip");
    const uint64_t msg_bytes = 200;
    const uint32_t block_bytes = 50;
    uint8_t *message = (uint8_t *)malloc(msg_bytes);
    for (uint64_t i = 0; i < msg_bytes; i++) message[i] = (uint8_t)(i * 3);

    WirehairCodec enc1 = wirehair_encoder_create(0, message, msg_bytes, block_bytes);
    CHECK(enc1 != nullptr, "encoder1 create failed");

    WirehairCodec dec = wirehair_decoder_create(0, msg_bytes, block_bytes);
    CHECK(dec != nullptr, "decoder create failed");

    uint32_t N = (uint32_t)((msg_bytes + block_bytes - 1) / block_bytes);
    uint8_t *block = (uint8_t *)malloc(block_bytes);

    for (uint32_t i = 0; i < N; i++) {
        uint32_t written = 0;
        wirehair_encode(enc1, i, block, block_bytes, &written);
        wirehair_decode(dec, i, block, written);
    }

    WirehairResult r = wirehair_decoder_becomes_encoder(dec);
    CHECK(r == Wirehair_Success, "becomes_encoder failed");

    WirehairCodec dec2 = wirehair_decoder_create(0, msg_bytes, block_bytes);
    CHECK(dec2 != nullptr, "decoder2 create failed");

    for (uint32_t i = 0; i < N; i++) {
        uint32_t written = 0;
        wirehair_encode(dec, i, block, block_bytes, &written);
        wirehair_decode(dec2, i, block, written);
    }

    uint8_t *output = (uint8_t *)malloc(msg_bytes);
    r = wirehair_recover(dec2, output, msg_bytes);
    CHECK(r == Wirehair_Success, "recover2 failed");
    CHECK(memcmp(message, output, msg_bytes) == 0, "roundtrip data mismatch");

    wirehair_free(enc1);
    wirehair_free(dec);
    wirehair_free(dec2);
    free(block);
    free(message);
    free(output);
    PASS();
}

static void test_codec_reuse(void) {
    TEST("codec reuse with wirehair_encoder_create(reuseOpt)");
    const uint64_t msg_bytes = 100;
    const uint32_t block_bytes = 50;

    uint8_t msg1[100], msg2[100];
    for (int i = 0; i < 100; i++) { msg1[i] = i; msg2[i] = i ^ 0xFF; }

    WirehairCodec enc = wirehair_encoder_create(0, msg1, msg_bytes, block_bytes);
    CHECK(enc != nullptr, "encoder create failed");

    WirehairCodec enc2 = wirehair_encoder_create(enc, msg2, msg_bytes, block_bytes);
    CHECK(enc2 != nullptr, "encoder reuse failed");
    CHECK(enc2 == enc, "reuse should return same pointer");

    WirehairCodec dec = wirehair_decoder_create(0, msg_bytes, block_bytes);
    uint8_t block[50];
    uint32_t N = (msg_bytes + block_bytes - 1) / block_bytes;

    for (uint32_t i = 0; i < N; i++) {
        uint32_t written = 0;
        wirehair_encode(enc2, i, block, block_bytes, &written);
        wirehair_decode(dec, i, block, written);
    }

    uint8_t output[100];
    wirehair_recover(dec, output, msg_bytes);
    CHECK(memcmp(msg2, output, msg_bytes) == 0, "reused encoder data mismatch");

    wirehair_free(enc2);
    wirehair_free(dec);
    PASS();
}

static void test_invalid_input(void) {
    TEST("invalid inputs return errors");
    WirehairCodec enc = wirehair_encoder_create(0, nullptr, 100, 50);
    CHECK(enc == nullptr, "null message should fail");

    WirehairCodec enc2 = wirehair_encoder_create(0, "test", 4, 50);
    CHECK(enc2 == nullptr, "N=1 should fail (too small)");

    WirehairResult r = wirehair_encode(nullptr, 0, nullptr, 0, nullptr);
    CHECK(r != Wirehair_Success, "encode with null codec should fail");

    PASS();
}

int main(void) {
    printf("\n=== Wirehair Unit Tests ===\n\n");

    test_init();
    test_encode_decode_small();
    test_encode_decode_two_block();
    test_encode_decode_multi_block();
    test_loss_recovery();
    test_recover_single_block();
    test_decoder_becomes_encoder();
    test_codec_reuse();
    test_invalid_input();

    printf("\n%d/%d passed", g_pass, g_pass + g_fail);
    if (g_fail > 0) printf(" (%d FAILED)", g_fail);
    printf("\n");

    return g_fail > 0 ? 1 : 0;
}
