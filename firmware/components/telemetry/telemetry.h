#pragma once

#include <stdint.h>
#include <stdbool.h>

#define TELEMETRY_SIZE 24

typedef struct __attribute__((packed)) {
    uint32_t callsign_hash;
    uint32_t latitude_deg1e5;
    int32_t longitude_deg1e5;
    uint16_t altitude_m;
    uint16_t voltage_mv;
    int16_t temperature_cdeg;
    uint16_t pressure_hpa;
    uint8_t sats;
    uint8_t tx_mode;
    uint8_t antenna;
    uint8_t flags;
    uint16_t crc16;
} telemetry_packet_t;

void telemetry_fill(telemetry_packet_t *pkt, float temp_c, float pressure_hpa,
                    float altitude_m, uint16_t voltage_mv, uint16_t seq);
uint16_t telemetry_crc16(const uint8_t *data, uint8_t len);
void telemetry_serialize(const telemetry_packet_t *pkt, uint8_t *buf);
bool telemetry_validate(const uint8_t *buf, uint8_t len);
