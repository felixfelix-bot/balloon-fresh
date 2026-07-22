/*
 * sweep_config.h — 10-config mode table for LR2021 multi-mode sweep
 * See ADR-018 and ADR-019
 */
#pragma once
#include <Arduino.h>
#include <RadioLib.h>

// Sweep config IDs
#define SWEEP_FLRC_2600   0
#define SWEEP_FLRC_1300   1
#define SWEEP_FLRC_650    2
#define SWEEP_FLRC_260    3
#define SWEEP_GFSK_1000   4
#define SWEEP_GFSK_48     5
#define SWEEP_LORA_SF5    6
#define SWEEP_LORA_SF7    7
#define SWEEP_LORA_SF9    8
#define SWEEP_LORA_SF12   9
#define SWEEP_COUNT       10

// Config table: mode_id, modulation enum, frequency, bitrate/SF, BW, window_ms
enum ModulationType { MOD_FLRC, MOD_LORA, MOD_GFSK };

struct SweepConfig {
    uint8_t id;
    ModulationType mod;
    float freq;
    uint16_t bitrate;     // FLRC/GFSK bitrate in kbps
    uint8_t sf;           // LoRa spreading factor (ignored for FLRC/GFSK)
    float bw_khz;         // LoRa bandwidth in kHz (ignored for FLRC/GFSK)
    int8_t power;
    uint16_t window_ms;   // time to spend in this config
    const char* name;
};

static const SweepConfig SWEEP_TABLE[SWEEP_COUNT] = {
    { SWEEP_FLRC_2600, MOD_FLRC, 2440.0, 2600, 0, 2666,  13, 1000, "FLRC_2600" },
    { SWEEP_FLRC_1300, MOD_FLRC, 2440.0, 1300, 0, 1333,  13, 1000, "FLRC_1300" },
    { SWEEP_FLRC_650,  MOD_FLRC, 2440.0,  650, 0,  888,  13, 1000, "FLRC_650"  },
    { SWEEP_FLRC_260,  MOD_FLRC, 2440.0,  260, 0,  444,  13, 1000, "FLRC_260"  },
    { SWEEP_GFSK_1000, MOD_GFSK, 2440.0, 1000, 0,  500,  13, 1000, "GFSK_1000" },
    { SWEEP_GFSK_48,   MOD_GFSK, 2440.0,    5, 0,   50,  13, 5000, "GFSK_4.8"  },
    { SWEEP_LORA_SF5,  MOD_LORA, 2440.0,    0, 5, 1000,  13, 2000, "LoRa_SF5"  },
    { SWEEP_LORA_SF7,  MOD_LORA, 2440.0,    0, 7,  250,  13, 3000, "LoRa_SF7"  },
    { SWEEP_LORA_SF9,  MOD_LORA, 2440.0,    0, 9,  125,  13, 8000, "LoRa_SF9"  },
    { SWEEP_LORA_SF12, MOD_LORA, 2440.0,    0, 12,  31,  13,30000, "LoRa_SF12" },
};

// Total sweep time (sum of windows + switching overhead)
static const uint16_t SWEEP_GUARD_MS = 200;  // guard between configs
static const uint16_t SWEEP_TOTAL_MS = 55000; // ~55 seconds

// Packet format: mode_id(1) + seq(4) + timestamp(4) + padding
#define SWEEP_PKT_SIZE 20
