#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <assert.h>
#include "../include/erasure.h"

#define FRAG_NB   10
#define FRAG_SIZE 20
#define REDUNDANCY 5

static uint8_t original[FRAG_NB * FRAG_SIZE];
static uint8_t assembly[(FRAG_NB + FRAG_NB) * FRAG_SIZE];
static uint8_t matrix_buf[((ERASURE_MAX_REDUNDANCY >> 3) + 1) * ERASURE_MAX_REDUNDANCY];

static void fill_original(void)
{
    for (int i = 0; i < (int)sizeof(original); i++) {
        original[i] = (uint8_t)(rand() & 0xFF);
    }
}

static void test_no_loss(void)
{
    printf("TEST: no loss (all original fragments)... ");
    fill_original();

    erasure_decoder_t dec;
    erasure_decoder_init(&dec, FRAG_NB, FRAG_SIZE, assembly, matrix_buf);

    for (uint16_t i = 1; i <= FRAG_NB; i++) {
        int r = erasure_decoder_process(&dec, i, original + (i - 1) * FRAG_SIZE);
        assert(r == 1 || r == 0);
    }

    assert(erasure_decoder_is_complete(&dec));
    assert(memcmp(original, assembly, sizeof(original)) == 0);
    printf("PASS\n");
}

static void test_single_loss_with_redundancy(void)
{
    printf("TEST: single loss recovered by 1 redundant fragment... ");
    fill_original();

    erasure_decoder_t dec;
    erasure_decoder_init(&dec, FRAG_NB, FRAG_SIZE, assembly, matrix_buf);

    bool lost[FRAG_NB] = {false};
    lost[5] = true;

    for (uint16_t i = 1; i <= FRAG_NB; i++) {
        if (lost[i - 1]) continue;
        erasure_decoder_process(&dec, i, original + (i - 1) * FRAG_SIZE);
    }

    assert(!erasure_decoder_is_complete(&dec));

    erasure_encoder_t enc;
    erasure_encoder_init(&enc, FRAG_NB, FRAG_SIZE, original);

    uint8_t redundant[FRAG_SIZE];
    erasure_encode_redundant(&enc, 0, redundant);
    erasure_decoder_process(&dec, FRAG_NB + 1, redundant);

    assert(erasure_decoder_is_complete(&dec));
    assert(memcmp(original, assembly, sizeof(original)) == 0);
    printf("PASS\n");
}

static void test_multi_loss_with_redundancy(void)
{
    printf("TEST: 3 losses recovered by redundant fragments... ");
    fill_original();

    erasure_decoder_t dec;
    erasure_decoder_init(&dec, FRAG_NB, FRAG_SIZE, assembly, matrix_buf);

    bool lost[FRAG_NB] = {false};
    lost[2] = true;
    lost[5] = true;
    lost[8] = true;

    for (uint16_t i = 1; i <= FRAG_NB; i++) {
        if (lost[i - 1]) continue;
        erasure_decoder_process(&dec, i, original + (i - 1) * FRAG_SIZE);
    }

    assert(!erasure_decoder_is_complete(&dec));

    erasure_encoder_t enc;
    erasure_encoder_init(&enc, FRAG_NB, FRAG_SIZE, original);

    uint8_t redundant[FRAG_SIZE];
    for (uint16_t r = 0; r < REDUNDANCY; r++) {
        erasure_encode_redundant(&enc, r, redundant);
        erasure_decoder_process(&dec, FRAG_NB + 1 + r, redundant);
    }

    assert(erasure_decoder_is_complete(&dec));
    assert(memcmp(original, assembly, sizeof(original)) == 0);
    printf("PASS\n");
}

static void test_all_original_lost(void)
{
    printf("TEST: all original fragments lost, recovered by redundancy... ");
    fill_original();

    erasure_decoder_t dec;
    erasure_decoder_init(&dec, FRAG_NB, FRAG_SIZE, assembly, matrix_buf);

    erasure_encoder_t enc;
    erasure_encoder_init(&enc, FRAG_NB, FRAG_SIZE, original);

    for (uint16_t r = 0; r < FRAG_NB + 2; r++) {
        uint8_t redundant[FRAG_SIZE];
        erasure_encode_redundant(&enc, r, redundant);
        erasure_decoder_process(&dec, FRAG_NB + 1 + r, redundant);
    }

    assert(erasure_decoder_is_complete(&dec));
    assert(memcmp(original, assembly, sizeof(original)) == 0);
    printf("PASS\n");
}

static void test_random_losses(void)
{
    printf("TEST: random 30%% loss pattern (20 trials)... ");
    int recovered = 0;

    for (int trial = 0; trial < 20; trial++) {
        fill_original();

        erasure_decoder_t dec;
        erasure_decoder_init(&dec, FRAG_NB, FRAG_SIZE, assembly, matrix_buf);

        bool lost[FRAG_NB] = {false};
        int loss_count = 0;
        for (int i = 0; i < FRAG_NB; i++) {
            if ((rand() % 100) < 30) {
                lost[i] = true;
                loss_count++;
            }
        }

        for (uint16_t i = 1; i <= FRAG_NB; i++) {
            if (lost[i - 1]) continue;
            erasure_decoder_process(&dec, i, original + (i - 1) * FRAG_SIZE);
        }

        if (erasure_decoder_is_complete(&dec)) {
            int data_ok = memcmp(original, assembly, FRAG_NB * FRAG_SIZE) == 0;
            if (data_ok) recovered++; else recovered += 0;
            continue;
        }

        erasure_encoder_t enc;
        erasure_encoder_init(&enc, FRAG_NB, FRAG_SIZE, original);

        for (uint16_t r = 0; r < loss_count + 8; r++) {
            uint8_t redundant[FRAG_SIZE];
            erasure_encode_redundant(&enc, r, redundant);
            erasure_decoder_process(&dec, FRAG_NB + 1 + r, redundant);
            if (erasure_decoder_is_complete(&dec)) break;
        }

        if (erasure_decoder_is_complete(&dec)) {
            int data_ok = memcmp(original, assembly, FRAG_NB * FRAG_SIZE) == 0;
            if (data_ok) recovered++;
        }
    }

    printf("PASS (%d/20 recovered with correct data)\n", recovered);
    assert(recovered >= 12);
}

int main(void)
{
    srand(42);
    printf("\n=== Erasure Coding Tests ===\n\n");
    test_no_loss();
    test_single_loss_with_redundancy();
    test_multi_loss_with_redundancy();
    test_all_original_lost();
    test_random_losses();
    printf("\n=== Results: 5/5 passed ===\n");
    return 0;
}
