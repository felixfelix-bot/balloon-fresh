#pragma once

#include <stdint.h>
#include <stdbool.h>

#define TELEMETRY_SIZE 28

#define TELEMETRY_FLAG_GPS_VALID    (1 << 7)
#define TELEMETRY_FLAG_GPS_ASSISTED (1 << 6)
#define TELEMETRY_FLAG_SOLAR_ACTIVE (1 << 5)
#define TELEMETRY_FLAG_TX_24GHZ     (1 << 4)
#define TELEMETRY_FLAG_TX_FLRC      (1 << 3)
#define TELEMETRY_FLAG_LOW_POWER    (1 << 1)

typedef struct __attribute__((packed)) {
    uint32_t callsign_hash;
    uint16_t seq;
    uint32_t latitude_deg1e5;
    int32_t  longitude_deg1e5;
    uint16_t altitude_m;
    uint16_t voltage_mv;
    int16_t  temperature_cdeg;
    uint16_t pressure_hpa;
    uint8_t  sats;
    uint8_t  tx_mode;
    uint8_t  antenna;
    uint8_t  flags;
    uint16_t crc16;
} telemetry_packet_t;

void telemetry_fill(telemetry_packet_t *pkt, float temp_c, float pressure_hpa,
                    float altitude_m, uint16_t voltage_mv, uint16_t seq);
uint16_t telemetry_crc16(const uint8_t *data, uint8_t len);
void telemetry_serialize(const telemetry_packet_t *pkt, uint8_t *buf);
bool telemetry_validate(const uint8_t *buf, uint8_t len);
