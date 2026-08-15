/**
 * @file    bench_payload.c
 * @brief   Bench payload generator: seq header + xorshift32 LFSR fill.
 */

#include "bench_payload.h"

uint32_t bench_lfsr_next(uint32_t* state)
{
    uint32_t x = *state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *state = x;
    return x;
}

static void put_u32le(uint8_t* p, uint32_t v)
{
    p[0] = (uint8_t)(v & 0xFF);
    p[1] = (uint8_t)((v >> 8) & 0xFF);
    p[2] = (uint8_t)((v >> 16) & 0xFF);
    p[3] = (uint8_t)((v >> 24) & 0xFF);
}

static uint32_t get_u32le(const uint8_t* p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

void bench_payload_build(uint8_t* buf, uint32_t len, uint32_t seq)
{
    /* Seed the LFSR from the sequence number, forcing a non-zero state. */
    uint32_t st = seq ^ 0x1A2B3C4DU;
    if (st == 0)
        st = 0xDEADBEEFU;

    put_u32le(&buf[0], seq);
    buf[4] = (uint8_t)(len & 0xFF);
    buf[5] = (uint8_t)((len >> 8) & 0xFF);

    for (uint32_t i = BENCH_PAYLOAD_HDR_LEN; i < len; i++)
    {
        if ((i - BENCH_PAYLOAD_HDR_LEN) % 4 == 0)
            bench_lfsr_next(&st);
        buf[i] = (uint8_t)(st >> (((i - BENCH_PAYLOAD_HDR_LEN) % 4) * 8));
    }
}

uint32_t bench_payload_seq(const uint8_t* buf)
{
    return get_u32le(buf);
}

uint16_t bench_payload_len_field(const uint8_t* buf)
{
    return (uint16_t)buf[4] | ((uint16_t)buf[5] << 8);
}

int bench_payload_verify(const uint8_t* buf, uint32_t len)
{
    if (len < BENCH_PAYLOAD_HDR_LEN)
        return 0;

    uint32_t seq = get_u32le(buf);
    uint32_t st = seq ^ 0x1A2B3C4DU;
    if (st == 0)
        st = 0xDEADBEEFU;

    for (uint32_t i = BENCH_PAYLOAD_HDR_LEN; i < len; i++)
    {
        if ((i - BENCH_PAYLOAD_HDR_LEN) % 4 == 0)
            bench_lfsr_next(&st);
        if (buf[i] != (uint8_t)(st >> (((i - BENCH_PAYLOAD_HDR_LEN) % 4) * 8)))
            return 0;
    }
    return 1;
}
