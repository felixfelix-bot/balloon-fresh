#pragma once

#include <stdint.h>
#include <stddef.h>

void prbs15_fill(uint8_t *buf, size_t len, uint32_t seed);
uint16_t prbs15_verify(const uint8_t *buf, size_t len, uint32_t seed, uint16_t *out_bytes_bad);
