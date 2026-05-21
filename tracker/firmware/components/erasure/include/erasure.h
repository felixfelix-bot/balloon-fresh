#pragma once

#include <stdint.h>
#include <stdbool.h>

#define ERASURE_MAX_FRAGS     64
#define ERASURE_MAX_REDUNDANCY 32
#define ERASURE_MAX_FRAG_SIZE 242

typedef struct {
    uint16_t frag_nb;
    uint8_t  frag_size;
    uint16_t frag_nb_lost;

    uint8_t  *matrix_m2b;
    uint16_t m2b_rows;

    uint16_t frag_nb_missing[ERASURE_MAX_FRAGS];
    uint8_t  *assembly_buf;

    uint16_t frags_received;
    bool     complete;
} erasure_decoder_t;

typedef struct {
    uint16_t frag_nb;
    uint8_t  frag_size;
    uint8_t  *data;
} erasure_encoder_t;

void erasure_decoder_init(erasure_decoder_t *dec, uint16_t frag_nb, uint8_t frag_size,
                          uint8_t *assembly_buf, uint8_t *matrix_buf);
int erasure_decoder_process(erasure_decoder_t *dec, uint16_t frag_counter, const uint8_t *raw_data);
bool erasure_decoder_is_complete(const erasure_decoder_t *dec);

void erasure_encoder_init(erasure_encoder_t *enc, uint16_t frag_nb, uint8_t frag_size, uint8_t *data);
void erasure_encode_redundant(const erasure_encoder_t *enc, uint16_t redundancy_index, uint8_t *out);
