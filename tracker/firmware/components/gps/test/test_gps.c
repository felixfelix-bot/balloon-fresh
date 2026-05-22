#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <assert.h>
#include <math.h>

#include "../gps_parser.h"

static void test_gga_valid_fix(void) {
    gps_parser_data_t data;
    memset(&data, 0, sizeof(data));
    const char *gga = "$GNGGA,123519,5230.0000,N,01300.0000,E,1,08,0.9,12000,M,0,M,,*XX";
    bool ok = gps_parse_nmea_gga(gga, &data);
    assert(ok);
    assert(data.fix == true);
    assert(data.sats == 8);
    assert(data.altitude_m == 12000);
    float expected_lat = (52 + 30.0/60.0) * 1e5;
    assert(abs(data.latitude - (int32_t)expected_lat) <= 1);
    float expected_lon = (13 + 0.0/60.0) * 1e5;
    assert(abs(data.longitude - (int32_t)expected_lon) <= 1);
    printf("PASS (lat=%d lon=%d sats=%d alt=%d)\n", data.latitude, data.longitude, data.sats, data.altitude_m);
}

static void test_gga_no_fix(void) {
    gps_parser_data_t data;
    memset(&data, 0, sizeof(data));
    const char *gga = "$GNGGA,123519,,,,0,00,,,,,,,*XX";
    bool ok = gps_parse_nmea_gga(gga, &data);
    assert(!ok);
    assert(data.fix == false);
    printf("PASS\n");
}

static void test_gga_south_west(void) {
    gps_parser_data_t data;
    memset(&data, 0, sizeof(data));
    const char *gga = "$GNGGA,123519,3352.0000,S,15112.0000,W,1,12,1.0,50,M,0,M,,*XX";
    bool ok = gps_parse_nmea_gga(gga, &data);
    assert(ok);
    assert(data.latitude < 0);
    assert(data.longitude < 0);
    float expected_lat = -(33 + 52.0/60.0) * 1e5;
    float expected_lon = -(151 + 12.0/60.0) * 1e5;
    assert(abs(data.latitude - (int32_t)expected_lat) <= 1);
    assert(abs(data.longitude - (int32_t)expected_lon) <= 1);
    printf("PASS (lat=%d lon=%d)\n", data.latitude, data.longitude);
}

static void test_gga_hdop(void) {
    gps_parser_data_t data;
    memset(&data, 0, sizeof(data));
    const char *gga = "$GNGGA,123519,5230.0000,N,01300.0000,E,1,08,2.5,12000,M,0,M,,*XX";
    bool ok = gps_parse_nmea_gga(gga, &data);
    assert(ok);
    assert(fabs(data.hdop - 2.5) < 0.01);
    printf("PASS (hdop=%.1f)\n", data.hdop);
}

static void test_rmc_valid(void) {
    gps_parser_data_t data;
    memset(&data, 0, sizeof(data));
    const char *rmc = "$GNRMC,123519,A,5230.0000,N,01300.0000,E,0.0,0.0,010123,,,A*XX";
    bool ok = gps_parse_nmea_rmc(rmc, &data);
    assert(ok);
    float expected_lat = (52 + 30.0/60.0) * 1e5;
    assert(abs(data.latitude - (int32_t)expected_lat) <= 1);
    printf("PASS (lat=%d lon=%d)\n", data.latitude, data.longitude);
}

static void test_rmc_void(void) {
    gps_parser_data_t data;
    memset(&data, 0, sizeof(data));
    const char *rmc = "$GNRMC,123519,V,,,,,,,010123,,,N*XX";
    bool ok = gps_parse_nmea_rmc(rmc, &data);
    assert(!ok);
    printf("PASS\n");
}

static void test_rmc_south_west(void) {
    gps_parser_data_t data;
    memset(&data, 0, sizeof(data));
    const char *rmc = "$GNRMC,123519,A,3352.0000,S,15112.0000,W,0.0,0.0,010123,,,A*XX";
    bool ok = gps_parse_nmea_rmc(rmc, &data);
    assert(ok);
    assert(data.latitude < 0);
    assert(data.longitude < 0);
    printf("PASS (lat=%d lon=%d)\n", data.latitude, data.longitude);
}

static void test_gga_zero_lon(void) {
    gps_parser_data_t data;
    memset(&data, 0, sizeof(data));
    const char *gga = "$GNGGA,120000,5230.0000,N,00000.0000,E,1,04,1.0,100,M,0,M,,*XX";
    bool ok = gps_parse_nmea_gga(gga, &data);
    assert(ok);
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
