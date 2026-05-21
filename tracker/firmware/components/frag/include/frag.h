#pragma once

#include <stdint.h>
#include <stdbool.h>

#define FRAG_HEADER_SIZE 6
#define FRAG_MAX_PAYLOAD 236
#define FRAG_MAX_FRAMES  64

typedef struct __attribute__((packed)) {
    uint16_t block_id;
    uint8_t  frag_index;
    uint8_t  original_count;
    uint16_t crc16;
} frag_header_t;

typedef struct {
    uint16_t block_id;
    uint8_t  original_count;
    uint8_t  frag_size;
    uint16_t frags_received;

    uint8_t  received_map[(FRAG_MAX_FRAMES + 7) / 8];
    uint8_t  *assembly_buf;
    uint32_t assembly_size;

    bool complete;
} frag_reassembler_t;

uint16_t frag_crc16(const uint8_t *data, uint8_t len);

void frag_reassembler_init(frag_reassembler_t *ra, uint16_t block_id,
                           uint8_t original_count, uint8_t frag_size,
                           uint8_t *assembly_buf, uint32_t assembly_size);

int frag_reassembler_feed(frag_reassembler_t *ra, const uint8_t *frame, uint16_t frame_len);

uint16_t frag_make_frame(uint16_t block_id, uint8_t frag_index, uint8_t original_count,
                         const uint8_t *payload, uint8_t payload_len,
                         uint8_t *out, uint16_t out_size);
