#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <assert.h>

#include "telemetry.h"

static void test_crc16_empty(void) {
    uint16_t crc = telemetry_crc16((const uint8_t *)"", 0);
    assert(crc == 0xFFFF);
    printf("PASS\n");
}

static void test_crc16_deterministic(void) {
    uint8_t data[28];
    memset(data, 0xAB, sizeof(data));
    uint16_t crc1 = telemetry_crc16(data, 26);
    uint16_t crc2 = telemetry_crc16(data, 26);
    assert(crc1 == crc2);
    printf("PASS (crc=0x%04X)\n", crc1);
}

static void test_crc16_different_data(void) {
    uint8_t data1[26], data2[26];
    memset(data1, 0x00, sizeof(data1));
    memset(data2, 0xFF, sizeof(data2));
    uint16_t crc1 = telemetry_crc16(data1, 26);
    uint16_t crc2 = telemetry_crc16(data2, 26);
    assert(crc1 != crc2);
    printf("PASS (crc1=0x%04X crc2=0x%04X)\n", crc1, crc2);
}

static void test_fill_sets_fields(void) {
    telemetry_packet_t pkt;
    memset(&pkt, 0, sizeof(pkt));

    telemetry_fill(&pkt, 22.5f, 1013.3f, 12000.0f, 3300, 42);

    assert(pkt.seq == 42);
    assert(pkt.temperature_cdeg == 2250);
    assert(pkt.pressure_hpa == 10133);
    assert(pkt.voltage_mv == 3300);
    assert(pkt.tx_mode == 0);
    assert(pkt.antenna == 0);
    printf("PASS\n");
}

static void test_fill_negative_temp(void) {
    telemetry_packet_t pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.altitude_m = 5000;

    telemetry_fill(&pkt, -40.0f, 980.0f, 0, 2800, 1);

    assert(pkt.temperature_cdeg == -4000);
    assert(pkt.pressure_hpa == 9800);
    assert(pkt.altitude_m == 5000);
    assert(pkt.seq == 1);
    printf("PASS\n");
}

static void test_fill_updates_crc(void) {
    telemetry_packet_t pkt;
    memset(&pkt, 0, sizeof(pkt));

    telemetry_fill(&pkt, 25.0f, 1013.0f, 10000, 3500, 10);

    uint8_t *raw = (uint8_t *)&pkt;
    uint16_t calc_crc = telemetry_crc16(raw, TELEMETRY_SIZE - 2);
    assert(pkt.crc16 == calc_crc);
    printf("PASS (crc=0x%04X)\n", pkt.crc16);
}

static void test_serialize_roundtrip(void) {
    telemetry_packet_t pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.callsign_hash = 0xDEADBEEF;
    pkt.seq = 100;
    telemetry_fill(&pkt, 20.0f, 1000.0f, 8000, 3100, 100);

    uint8_t buf[TELEMETRY_SIZE];
    telemetry_serialize(&pkt, buf);
    assert(memcmp(buf, &pkt, TELEMETRY_SIZE) == 0);
    printf("PASS\n");
}

static void test_validate_ok(void) {
    telemetry_packet_t pkt;
    memset(&pkt, 0, sizeof(pkt));
    telemetry_fill(&pkt, 20.0f, 1000.0f, 8000, 3100, 1);

    uint8_t buf[TELEMETRY_SIZE];
    telemetry_serialize(&pkt, buf);
    assert(telemetry_validate(buf, TELEMETRY_SIZE));
    printf("PASS\n");
}

static void test_validate_wrong_size(void) {
    uint8_t buf[20];
    assert(!telemetry_validate(buf, 20));
    assert(!telemetry_validate(buf, 0));
    assert(!telemetry_validate(buf, 30));
    printf("PASS\n");
}

static void test_validate_corrupted(void) {
    telemetry_packet_t pkt;
    memset(&pkt, 0, sizeof(pkt));
    telemetry_fill(&pkt, 20.0f, 1000.0f, 8000, 3100, 1);

    uint8_t buf[TELEMETRY_SIZE];
    telemetry_serialize(&pkt, buf);
    buf[10] ^= 0xFF;
    assert(!telemetry_validate(buf, TELEMETRY_SIZE));
    printf("PASS\n");
}

static void test_validate_crc_little_endian(void) {
    telemetry_packet_t pkt;
    memset(&pkt, 0, sizeof(pkt));
    telemetry_fill(&pkt, 20.0f, 1000.0f, 8000, 3100, 1);

    uint8_t buf[TELEMETRY_SIZE];
    telemetry_serialize(&pkt, buf);

    uint16_t expected_crc = telemetry_crc16(buf, TELEMETRY_SIZE - 2);
    uint16_t stored_crc = buf[TELEMETRY_SIZE - 2] | (buf[TELEMETRY_SIZE - 1] << 8);
    assert(stored_crc == expected_crc);
    printf("PASS (stored=0x%04X expected=0x%04X)\n", stored_crc, expected_crc);
}

int main(void) {
    printf("\n=== Telemetry Tests ===\n\n");

    printf("TEST 1: CRC16 empty... ");
    test_crc16_empty();

    printf("TEST 2: CRC16 deterministic... ");
    test_crc16_deterministic();

    printf("TEST 3: CRC16 different data... ");
    test_crc16_different_data();

    printf("TEST 4: fill sets fields... ");
    test_fill_sets_fields();

    printf("TEST 5: fill negative temperature... ");
    test_fill_negative_temp();

    printf("TEST 6: fill updates CRC... ");
    test_fill_updates_crc();

    printf("TEST 7: serialize roundtrip... ");
    test_serialize_roundtrip();

    printf("TEST 8: validate OK... ");
    test_validate_ok();

    printf("TEST 9: validate wrong size... ");
    test_validate_wrong_size();

    printf("TEST 10: validate corrupted... ");
    test_validate_corrupted();

    printf("TEST 11: validate CRC little-endian... ");
    test_validate_crc_little_endian();

    printf("\n=== Results: 11/11 passed ===\n");
    return 0;
}
