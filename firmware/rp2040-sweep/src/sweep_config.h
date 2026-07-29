/*
 * sweep_config.h — Config for FLRC sweep + fixed mode
 */
#pragma once
#include <Arduino.h>

struct SweepSlot {
    uint8_t  mode_id;
    float    freq_mhz;
    uint16_t bitrate_kbps;
    uint16_t pkt_size;
    uint16_t duration_ms;
    const char* name;
};

// Phase 1A: Fixed mode — both at 2600 kbps, continuous
// Use this to verify the link before sweeping
static const SweepSlot FIXED_MODE = {
    0xAA, 2440.0, 2600, 127, 0xFFFF, "FIXED-2600"
};

// Phase 1B: FLRC sweep — 4 bitrates at 2.4 GHz
static const SweepSlot SWEEP_TABLE[] = {
    { 1, 2440.0, 2600, 127, 5000, "FLRC-2600" },
    { 2, 2440.0, 1300, 127, 5000, "FLRC-1300" },
    { 3, 2440.0,  650, 127, 5000, "FLRC-650"  },
    { 4, 2440.0,  260, 127, 5000, "FLRC-260"  },
};
static const int NUM_SWEEP_SLOTS = 4;
static const uint16_t GUARD_MS = 200;
