#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <assert.h>
#include <math.h>

typedef struct {
    int32_t latitude;
    int32_t longitude;
    uint16_t altitude_m;
    uint8_t sats;
    float hdop;
    int fix;
} gps_data_t;

static int parse_nmea_gga(const char *sentence, gps_data_t *data)
{
    const char *p = strchr(sentence, ',');
    if (!p) return 0;

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
            case 1: if (len < 16) { memcpy(lat_str, start, len); lat_str[len] = 0; } break;
            case 2: if (len < 2) { memcpy(lat_dir, start, len); lat_dir[len] = 0; } break;
            case 3: if (len < 16) { memcpy(lon_str, start, len); lon_str[len] = 0; } break;
            case 4: if (len < 2) { memcpy(lon_dir, start, len); lon_dir[len] = 0; } break;
            case 5: if (len < 2) { memcpy(fix_str, start, len); fix_str[len] = 0; } break;
            case 6: if (len < 4) { memcpy(sats_str, start, len); sats_str[len] = 0; } break;
            case 7: if (len < 8) { memcpy(hdop_str, start, len); hdop_str[len] = 0; } break;
            case 8: if (len < 16) { memcpy(alt_str, start, len); alt_str[len] = 0; } break;
        }
        if (*p == ',') p++;
        field++;
    }

    data->fix = (fix_str[0] >= '1');
    if (!data->fix) return 0;

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

    return 1;
}

static int parse_nmea_rmc(const char *sentence, gps_data_t *data)
{
    const char *p = strchr(sentence, ',');
    if (!p) return 0;

    int field = 0;
    char status[2] = {0};
    char lat_str[16] = {0}, lat_dir[2] = {0};
    char lon_str[16] = {0}, lon_dir[2] = {0};

    p++;
    while (*p && field < 8) {
        const char *start = p;
        while (*p && *p != ',' && *p != '*') p++;
        size_t len = p - start;
        switch (field) {
            case 0: break;
            case 1: if (len < 2) { memcpy(status, start, len); status[len] = 0; } break;
            case 2: if (len < 15) { memcpy(lat_str, start, len); lat_str[len] = 0; } break;
            case 3: if (len < 2) { memcpy(lat_dir, start, len); lat_dir[len] = 0; } break;
            case 4: if (len < 15) { memcpy(lon_str, start, len); lon_str[len] = 0; } break;
            case 5: if (len < 2) { memcpy(lon_dir, start, len); lon_dir[len] = 0; } break;
        }
        if (*p == ',') p++;
        field++;
    }

    if (status[0] != 'A') return 0;

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

    return 1;
}

static void test_gga_valid_fix(void) {
    gps_data_t data;
    memset(&data, 0, sizeof(data));
    const char *gga = "$GNGGA,123519,5230.0000,N,01300.0000,E,1,08,0.9,12000,M,0,M,,*XX";
    int ok = parse_nmea_gga(gga, &data);
    assert(ok == 1);
    assert(data.fix == 1);
    assert(data.sats == 8);
    assert(data.altitude_m == 12000);
    float expected_lat = (52 + 30.0/60.0) * 1e5;
    assert(abs(data.latitude - (int32_t)expected_lat) <= 1);
    float expected_lon = (13 + 0.0/60.0) * 1e5;
    assert(abs(data.longitude - (int32_t)expected_lon) <= 1);
    printf("PASS (lat=%d lon=%d sats=%d alt=%d)\n", data.latitude, data.longitude, data.sats, data.altitude_m);
}

static void test_gga_no_fix(void) {
    gps_data_t data;
    memset(&data, 0, sizeof(data));
    const char *gga = "$GNGGA,123519,,,,0,00,,,,,,,*XX";
    int ok = parse_nmea_gga(gga, &data);
    assert(ok == 0);
    assert(data.fix == 0);
    printf("PASS\n");
}

static void test_gga_south_west(void) {
    gps_data_t data;
    memset(&data, 0, sizeof(data));
    const char *gga = "$GNGGA,123519,3352.0000,S,15112.0000,W,1,12,1.0,50,M,0,M,,*XX";
    int ok = parse_nmea_gga(gga, &data);
    assert(ok == 1);
    assert(data.latitude < 0);
    assert(data.longitude < 0);
    float expected_lat = -(33 + 52.0/60.0) * 1e5;
    float expected_lon = -(151 + 12.0/60.0) * 1e5;
    assert(abs(data.latitude - (int32_t)expected_lat) <= 1);
    assert(abs(data.longitude - (int32_t)expected_lon) <= 1);
    printf("PASS (lat=%d lon=%d)\n", data.latitude, data.longitude);
}

static void test_gga_hdop(void) {
    gps_data_t data;
    memset(&data, 0, sizeof(data));
    const char *gga = "$GNGGA,123519,5230.0000,N,01300.0000,E,1,08,2.5,12000,M,0,M,,*XX";
    int ok = parse_nmea_gga(gga, &data);
    assert(ok == 1);
    assert(fabs(data.hdop - 2.5) < 0.01);
    printf("PASS (hdop=%.1f)\n", data.hdop);
}

static void test_rmc_valid(void) {
    gps_data_t data;
    memset(&data, 0, sizeof(data));
    const char *rmc = "$GNRMC,123519,A,5230.0000,N,01300.0000,E,0.0,0.0,010123,,,A*XX";
    int ok = parse_nmea_rmc(rmc, &data);
    assert(ok == 1);
    float expected_lat = (52 + 30.0/60.0) * 1e5;
    assert(abs(data.latitude - (int32_t)expected_lat) <= 1);
    printf("PASS (lat=%d lon=%d)\n", data.latitude, data.longitude);
}

static void test_rmc_void(void) {
    gps_data_t data;
    memset(&data, 0, sizeof(data));
    const char *rmc = "$GNRMC,123519,V,,,,,,,010123,,,N*XX";
    int ok = parse_nmea_rmc(rmc, &data);
    assert(ok == 0);
    printf("PASS\n");
}

static void test_rmc_south_west(void) {
    gps_data_t data;
    memset(&data, 0, sizeof(data));
    const char *rmc = "$GNRMC,123519,A,3352.0000,S,15112.0000,W,0.0,0.0,010123,,,A*XX";
    int ok = parse_nmea_rmc(rmc, &data);
    assert(ok == 1);
    assert(data.latitude < 0);
    assert(data.longitude < 0);
    printf("PASS (lat=%d lon=%d)\n", data.latitude, data.longitude);
}

static void test_gga_zero_lon(void) {
    gps_data_t data;
    memset(&data, 0, sizeof(data));
    const char *gga = "$GNGGA,120000,5230.0000,N,00000.0000,E,1,04,1.0,100,M,0,M,,*XX";
    int ok = parse_nmea_gga(gga, &data);
    assert(ok == 1);
    assert(data.longitude == 0);
    printf("PASS (lon=%d)\n", data.longitude);
}

int main(void) {
    printf("\n=== GPS NMEA Parser Tests ===\n\n");

    printf("TEST 1: GGA valid fix... ");
    test_gga_valid_fix();

    printf("TEST 2: GGA no fix... ");
    test_gga_no_fix();

    printf("TEST 3: GGA south/west... ");
    test_gga_south_west();

    printf("TEST 4: GGA HDOP... ");
    test_gga_hdop();

    printf("TEST 5: RMC valid... ");
    test_rmc_valid();

    printf("TEST 6: RMC void... ");
    test_rmc_void();

    printf("TEST 7: RMC south/west... ");
    test_rmc_south_west();

    printf("TEST 8: GGA zero longitude... ");
    test_gga_zero_lon();

    printf("\n=== Results: 8/8 passed ===\n");
    return 0;
}
