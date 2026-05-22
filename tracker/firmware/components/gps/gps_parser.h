#pragma once

#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdlib.h>

typedef struct {
    bool fix;
    int32_t latitude;
    int32_t longitude;
    uint16_t altitude_m;
    uint8_t sats;
    float hdop;
} gps_parser_data_t;

static bool gps_parse_nmea_gga(const char *sentence, gps_parser_data_t *data)
{
    const char *p = strchr(sentence, ',');
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

static bool gps_parse_nmea_rmc(const char *sentence, gps_parser_data_t *data)
{
    const char *p = strchr(sentence, ',');
    if (!p) return false;

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

    if (status[0] != 'A') return false;

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

    return true;
}
