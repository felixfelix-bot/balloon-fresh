#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <assert.h>

#define TELEMETRY_SIZE 28

#define TELEMETRY_FLAG_GPS_VALID    (1 << 7)
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

static const uint16_t CRC16_TABLE[256] = {
    0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50A5, 0x60C6, 0x70E7,
    0x8108, 0x9129, 0xA14A, 0xB16B, 0xC18C, 0xD1AD, 0xE1CE, 0xF1EF,
    0x1231, 0x0210, 0x3273, 0x2252, 0x52B5, 0x4294, 0x72F7, 0x62D6,
    0x9339, 0x8318, 0xB37B, 0xA35A, 0xD3BD, 0xC39C, 0xF3FF, 0xE3DE,
    0x2462, 0x3443, 0x0420, 0x1401, 0x64E6, 0x74C7, 0x44A4, 0x5485,
    0xA56A, 0xB54B, 0x8528, 0x9509, 0xE5EE, 0xF5CF, 0xC5AC, 0xD58D,
    0x3653, 0x2672, 0x1611, 0x0630, 0x76D7, 0x66F6, 0x5695, 0x46B4,
    0xB75B, 0xA77A, 0x9719, 0x8738, 0xF7DF, 0xE7FE, 0xD79D, 0xC7BC,
    0x48C4, 0x58E5, 0x6886, 0x78A7, 0x0840, 0x1861, 0x2802, 0x3823,
    0xC9CC, 0xD9ED, 0xE98E, 0xF9AF, 0x8948, 0x9969, 0xA90A, 0xB92B,
    0x5AF5, 0x4AD4, 0x7AB7, 0x6A96, 0x1A71, 0x0A50, 0x3A33, 0x2A12,
    0xDBFD, 0xCBDC, 0xFBBF, 0xEB9E, 0x9B79, 0x8B58, 0xBB3B, 0xAB1A,
    0x6CA6, 0x7C87, 0x4CE4, 0x5CC5, 0x2C22, 0x3C03, 0x0C60, 0x1C41,
    0xEDAE, 0xFD8F, 0xCDEC, 0xDDCD, 0xAD2A, 0xBD0B, 0x8D68, 0x9D49,
    0x7E97, 0x6EB6, 0x5ED5, 0x4EF4, 0x3E13, 0x2E32, 0x1E51, 0x0E70,
    0xFF9F, 0xEFBE, 0xDFDD, 0xCFFC, 0xBF1B, 0xAF3A, 0x9F59, 0x8F78,
    0x9188, 0x81A9, 0xB1CA, 0xA1EB, 0xD10C, 0xC12D, 0xF14E, 0xE16F,
    0x1080, 0x00A1, 0x30C2, 0x20E3, 0x5004, 0x4025, 0x7046, 0x6067,
    0x83B9, 0x9398, 0xA3FB, 0xB3DA, 0xC33D, 0xD31C, 0xE37F, 0xF35E,
    0x02B1, 0x1290, 0x22F3, 0x32D2, 0x4235, 0x5214, 0x6277, 0x7256,
    0xB5EA, 0xA5CB, 0x95A8, 0x8589, 0xF56E, 0xE54F, 0xD52C, 0xC50D,
    0x34E2, 0x24C3, 0x14A0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
    0xA7DB, 0xB7FA, 0x8799, 0x97B8, 0xE75F, 0xF77E, 0xC71D, 0xD73C,
    0x26D3, 0x36F2, 0x0691, 0x16B0, 0x6657, 0x7676, 0x4615, 0x5634,
    0xD94C, 0xC96D, 0xF90E, 0xE92F, 0x99C8, 0x89E9, 0xB98A, 0xA9AB,
    0x5844, 0x4865, 0x7806, 0x6827, 0x18C0, 0x08E1, 0x3882, 0x28A3,
    0xCB7D, 0xDB5C, 0xEB3F, 0xFB1E, 0x8BF9, 0x9BD8, 0xABBB, 0xBB9A,
    0x4A75, 0x5A54, 0x6A37, 0x7A16, 0x0AF1, 0x1AD0, 0x2AB3, 0x3A92,
    0xFD2E, 0xED0F, 0xDD6C, 0xCD4D, 0xBDAA, 0xAD8B, 0x9DE8, 0x8DC9,
    0x7C26, 0x6C07, 0x5C64, 0x4C45, 0x3CA2, 0x2C83, 0x1CE0, 0x0CC1,
    0xEF1F, 0xFF3E, 0xCF5D, 0xDF7C, 0xAF9B, 0xBFBA, 0x8FD9, 0x9FF8,
    0x6E17, 0x7E36, 0x4E55, 0x5E74, 0x2E93, 0x3EB2, 0x0ED1, 0x1EF0,
};

static uint16_t telemetry_crc16(const uint8_t *data, uint8_t len)
{
    uint16_t crc = 0xFFFF;
    for (uint8_t i = 0; i < len; i++) {
        crc = (crc << 8) ^ CRC16_TABLE[(crc >> 8) ^ data[i]];
    }
    return crc;
}

static void fill_crc(telemetry_packet_t *pkt)
{
    uint8_t *raw = (uint8_t *)pkt;
    pkt->crc16 = telemetry_crc16(raw, TELEMETRY_SIZE - 2);
}

static bool validate(const uint8_t *buf, uint8_t len)
{
    if (len != TELEMETRY_SIZE) return false;
    uint16_t received = buf[TELEMETRY_SIZE - 2] | (buf[TELEMETRY_SIZE - 1] << 8);
    uint16_t calculated = telemetry_crc16(buf, TELEMETRY_SIZE - 2);
    return received == calculated;
}

static int test_count = 0;
static int pass_count = 0;

#define TEST(name) do { test_count++; printf("TEST: %s... ", name); } while(0)
#define PASS() do { pass_count++; printf("PASS\n"); } while(0)
#define FAIL(msg) do { printf("FAIL: %s\n", msg); } while(0)
#define ASSERT_EQ(a, b) do { if ((a) != (b)) { FAIL(#a " != " #b); return; } } while(0)

static void test_packet_size(void)
{
    TEST("packet size matches struct");
    ASSERT_EQ(sizeof(telemetry_packet_t), (size_t)TELEMETRY_SIZE);
    PASS();
}

static void test_crc_zero_data(void)
{
    TEST("CRC of all zeros");
    uint8_t data[24] = {0};
    uint16_t crc = telemetry_crc16(data, 24);
    ASSERT_EQ(crc > 0, true);
    PASS();
}

static void test_crc_single_byte(void)
{
    TEST("CRC of single byte");
    uint16_t crc1 = telemetry_crc16((uint8_t*)"\x00", 1);
    uint16_t crc2 = telemetry_crc16((uint8_t*)"\x01", 1);
    ASSERT_EQ(crc1 != crc2, true);
    PASS();
}

static void test_crc_deterministic(void)
{
    TEST("CRC is deterministic");
    uint8_t data[] = {0x42, 0x4C, 0x4E, 0x00};
    uint16_t crc1 = telemetry_crc16(data, 4);
    uint16_t crc2 = telemetry_crc16(data, 4);
    ASSERT_EQ(crc1, crc2);
    PASS();
}

static void test_validate_good_packet(void)
{
    TEST("validate good packet");
    telemetry_packet_t pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.callsign_hash = 0x424C4E;
    pkt.seq = 42;
    pkt.voltage_mv = 4200;
    pkt.flags = TELEMETRY_FLAG_GPS_VALID;
    fill_crc(&pkt);

    uint8_t buf[TELEMETRY_SIZE];
    memcpy(buf, &pkt, TELEMETRY_SIZE);
    ASSERT_EQ(validate(buf, TELEMETRY_SIZE), true);
    PASS();
}

static void test_validate_corrupted_packet(void)
{
    TEST("validate corrupted packet");
    telemetry_packet_t pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.callsign_hash = 0x424C4E;
    pkt.seq = 1;
    fill_crc(&pkt);

    uint8_t buf[TELEMETRY_SIZE];
    memcpy(buf, &pkt, TELEMETRY_SIZE);
    buf[5] ^= 0xFF;
    ASSERT_EQ(validate(buf, TELEMETRY_SIZE), false);
    PASS();
}

static void test_validate_wrong_length(void)
{
    TEST("validate wrong length");
    uint8_t buf[20] = {0};
    ASSERT_EQ(validate(buf, 20), false);
    PASS();
}

static void test_sequence_counter(void)
{
    TEST("sequence counter in packet");
    telemetry_packet_t pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.callsign_hash = 0x424C4E;
    pkt.seq = 12345;
    fill_crc(&pkt);
    ASSERT_EQ(pkt.seq, (uint16_t)12345);
    PASS();
}

static void test_gps_coordinates(void)
{
    TEST("GPS coordinate encoding");
    telemetry_packet_t pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.callsign_hash = 0x424C4E;
    pkt.latitude_deg1e5 = 5073450;   // 50.73450 N (Bonn)
    pkt.longitude_deg1e5 = 710050;   // 7.10050 E
    pkt.altitude_m = 60;
    pkt.sats = 8;
    pkt.flags = TELEMETRY_FLAG_GPS_VALID;
    fill_crc(&pkt);

    uint8_t buf[TELEMETRY_SIZE];
    memcpy(buf, &pkt, TELEMETRY_SIZE);

    telemetry_packet_t decoded;
    memcpy(&decoded, buf, TELEMETRY_SIZE);

    ASSERT_EQ(decoded.latitude_deg1e5, (uint32_t)5073450);
    ASSERT_EQ(decoded.longitude_deg1e5, (int32_t)710050);
    ASSERT_EQ(decoded.altitude_m, (uint16_t)60);
    ASSERT_EQ(decoded.sats, (uint8_t)8);
    ASSERT_EQ(decoded.flags & TELEMETRY_FLAG_GPS_VALID, TELEMETRY_FLAG_GPS_VALID);
    PASS();
}

static void test_negative_longitude(void)
{
    TEST("negative longitude (West)");
    telemetry_packet_t pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.callsign_hash = 0x424C4E;
    pkt.longitude_deg1e5 = -710050;  // 7.10050 W
    fill_crc(&pkt);

    ASSERT_EQ(pkt.longitude_deg1e5, (int32_t)(-710050));
    PASS();
}

static void test_temperature_encoding(void)
{
    TEST("temperature encoding (-40.25 C)");
    telemetry_packet_t pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.callsign_hash = 0x424C4E;
    pkt.temperature_cdeg = -4025;
    fill_crc(&pkt);
    float temp = (float)pkt.temperature_cdeg / 100.0f;
    ASSERT_EQ(temp < -40.0f && temp > -41.0f, true);
    PASS();
}

static void test_pressure_encoding(void)
{
    TEST("pressure encoding (1013.25 hPa)");
    telemetry_packet_t pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.callsign_hash = 0x424C4E;
    pkt.pressure_hpa = 10133;  // 1013.3 hPa * 10
    fill_crc(&pkt);
    float pres = (float)pkt.pressure_hpa / 10.0f;
    ASSERT_EQ(pres > 1013.0f && pres < 1014.0f, true);
    PASS();
}

static void test_low_voltage_flag(void)
{
    TEST("low voltage flag");
    telemetry_packet_t pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.callsign_hash = 0x424C4E;
    pkt.flags = TELEMETRY_FLAG_LOW_POWER;
    fill_crc(&pkt);
    ASSERT_EQ(pkt.flags & TELEMETRY_FLAG_LOW_POWER, TELEMETRY_FLAG_LOW_POWER);
    PASS();
}

static void test_serialization_roundtrip(void)
{
    TEST("serialization roundtrip");
    telemetry_packet_t original;
    memset(&original, 0, sizeof(original));
    original.callsign_hash = 0x424C4E;
    original.seq = 999;
    original.latitude_deg1e5 = 5073450;
    original.longitude_deg1e5 = 710050;
    original.altitude_m = 12345;
    original.voltage_mv = 4200;
    original.temperature_cdeg = -2575;
    original.pressure_hpa = 2567;
    original.sats = 12;
    original.tx_mode = 0;
    original.antenna = 0;
    original.flags = TELEMETRY_FLAG_GPS_VALID;
    fill_crc(&original);

    uint8_t buf[TELEMETRY_SIZE];
    memcpy(buf, &original, TELEMETRY_SIZE);

    ASSERT_EQ(validate(buf, TELEMETRY_SIZE), true);

    telemetry_packet_t decoded;
    memcpy(&decoded, buf, TELEMETRY_SIZE);

    ASSERT_EQ(decoded.callsign_hash, original.callsign_hash);
    ASSERT_EQ(decoded.seq, original.seq);
    ASSERT_EQ(decoded.latitude_deg1e5, original.latitude_deg1e5);
    ASSERT_EQ(decoded.longitude_deg1e5, original.longitude_deg1e5);
    ASSERT_EQ(decoded.altitude_m, original.altitude_m);
    ASSERT_EQ(decoded.voltage_mv, original.voltage_mv);
    ASSERT_EQ(decoded.temperature_cdeg, original.temperature_cdeg);
    ASSERT_EQ(decoded.pressure_hpa, original.pressure_hpa);
    ASSERT_EQ(decoded.sats, original.sats);
    ASSERT_EQ(decoded.flags, original.flags);
    PASS();
}

typedef struct {
    bool fix;
    int32_t latitude;
    int32_t longitude;
    uint16_t altitude_m;
    uint8_t sats;
    float hdop;
} gps_data_t;

static bool parse_gga(const char *sentence, gps_data_t *data)
{
    if (!strstr(sentence, "$GPGGA") && !strstr(sentence, "$GNGGA")) return false;
    char *p = strchr(sentence, ',');
    if (!p) return false;

    int field = 0;
    char lat_str[16] = {0}, lat_dir[2] = {0};
    char lon_str[16] = {0}, lon_dir[2] = {0};
    char alt_str[16] = {0}, sats_str[4] = {0};
    char hdop_str[8] = {0};
    char fix_str[2] = {0};

    p++;
    while (*p && field < 15) {
        const char *start = p;
        while (*p && *p != ',' && *p != '*') p++;
        size_t len = p - start;
        switch (field) {
            case 1: if (len < 16) strncpy(lat_str, start, len); break;
            case 2: if (len < 2) strncpy(lat_dir, start, len); break;
            case 3: if (len < 16) strncpy(lon_str, start, len); break;
            case 4: if (len < 2) strncpy(lon_dir, start, len); break;
            case 5: if (len < 2) strncpy(fix_str, start, len); break;
            case 6: if (len < 4) strncpy(sats_str, start, len); break;
            case 7: if (len < 8) strncpy(hdop_str, start, len); break;
            case 8: if (len < 16) strncpy(alt_str, start, len); break;
        }
        if (*p == ',') p++;
        field++;
    }

    data->fix = (fix_str[0] >= '1');
    if (!data->fix) return false;

    if (strlen(lat_str) >= 4) {
        int deg = atoi(lat_str) / 100;
        float min = atof(lat_str + 2);
        data->latitude = (int32_t)((deg + min / 60.0) * 1e5);
        if (lat_dir[0] == 'S') data->latitude = -data->latitude;
    }

    if (strlen(lon_str) >= 5) {
        int deg = atoi(lon_str) / 100;
        float min = atof(lon_str + 3);
        data->longitude = (int32_t)((deg + min / 60.0) * 1e5);
        if (lon_dir[0] == 'W') data->longitude = -data->longitude;
    }

    data->sats = (uint8_t)atoi(sats_str);
    data->hdop = atof(hdop_str);
    data->altitude_m = (uint16_t)atof(alt_str);

    return true;
}

static void test_gga_bonn(void)
{
    TEST("GGA parsing (Bonn: 50.7345 N, 7.1005 E)");
    gps_data_t data;
    memset(&data, 0, sizeof(data));
    bool ok = parse_gga("$GPGGA,123519,5044.070,N,00706.030,E,1,08,0.9,545.4,M,46.9,M,,*47", &data);
    ASSERT_EQ(ok, true);
    ASSERT_EQ(data.fix, true);
    ASSERT_EQ(data.sats, (uint8_t)8);

    float lat = (float)data.latitude / 1e5f;
    float lon = (float)data.longitude / 1e5f;

    bool lat_ok = lat > 50.73f && lat < 50.75f;
    bool lon_ok = lon > 7.09f && lon < 7.11f;
    ASSERT_EQ(lat_ok && lon_ok, true);
    PASS();
}

static void test_gga_no_fix(void)
{
    TEST("GGA parsing (no fix)");
    gps_data_t data;
    memset(&data, 0, sizeof(data));
    bool ok = parse_gga("$GPGGA,123519,5044.070,N,00706.030,E,0,00,0.9,,,,,,*00", &data);
    ASSERT_EQ(ok, false);
    ASSERT_EQ(data.fix, false);
    PASS();
}

static void test_gga_negative_lon(void)
{
    TEST("GGA parsing (New York: 40.7128 N, 74.0060 W)");
    gps_data_t data;
    memset(&data, 0, sizeof(data));
    bool ok = parse_gga("$GPGGA,123519,4042.768,N,07400.360,W,1,08,0.9,10.0,M,46.9,M,,*00", &data);
    ASSERT_EQ(ok, true);
    ASSERT_EQ(data.longitude < 0, true);

    float lon = (float)data.longitude / 1e5f;
    bool lon_ok = lon < -73.99f && lon > -74.01f;
    ASSERT_EQ(lon_ok, true);
    PASS();
}

int main(void)
{
    printf("\n=== Telemetry Protocol Tests ===\n\n");

    test_packet_size();
    test_crc_zero_data();
    test_crc_single_byte();
    test_crc_deterministic();
    test_validate_good_packet();
    test_validate_corrupted_packet();
    test_validate_wrong_length();
    test_sequence_counter();
    test_gps_coordinates();
    test_negative_longitude();
    test_temperature_encoding();
    test_pressure_encoding();
    test_low_voltage_flag();
    test_serialization_roundtrip();

    printf("\n=== GPS NMEA Parser Tests ===\n\n");

    test_gga_bonn();
    test_gga_no_fix();
    test_gga_negative_lon();

    printf("\n=== Results: %d/%d passed ===\n\n", pass_count, test_count);

    return (pass_count == test_count) ? 0 : 1;
}
