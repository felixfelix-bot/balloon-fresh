/**
 * @file    bench_cmd.c
 * @brief   Portable text-protocol command parser for the E80 bench firmware.
 */

#include "bench_cmd.h"
#include "buffer.h" /* BUF_CAPACITY (macro-only dependency; no link dep) */

#include <stddef.h>

int bench_strcaseeq(const char* a, const char* b)
{
    while (*a != '\0' && *b != '\0')
    {
        char ca = *a;
        char cb = *b;
        if (ca >= 'a' && ca <= 'z')
            ca = (char)(ca - 'a' + 'A');
        if (cb >= 'a' && cb <= 'z')
            cb = (char)(cb - 'a' + 'A');
        if (ca != cb)
            return 0;
        a++;
        b++;
    }
    return (*a == '\0') && (*b == '\0');
}

bool bench_parse_u32(const char* s, uint32_t* out)
{
    if (s == NULL || *s == '\0')
        return false;
    uint32_t v = 0;
    for (const char* p = s; *p != '\0'; p++)
    {
        if (*p < '0' || *p > '9')
            return false;
        uint32_t d = (uint32_t)(*p - '0');
        if (v > (0xFFFFFFFFUL - d) / 10UL)
            return false; /* overflow */
        v = v * 10UL + d;
    }
    *out = v;
    return true;
}

bool bench_parse_i8(const char* s, int8_t* out)
{
    if (s == NULL || *s == '\0')
        return false;
    bool neg = false;
    if (*s == '-')
    {
        neg = true;
        s++;
    }
    else if (*s == '+')
    {
        s++;
    }
    if (*s == '\0')
        return false;
    uint32_t v = 0;
    if (!bench_parse_u32(s, &v))
        return false;
    int32_t sv = neg ? -(int32_t)v : (int32_t)v;
    if (sv < -128 || sv > 127)
        return false;
    *out = (int8_t)sv;
    return true;
}

static bench_cmd_err_t split_tokens(const char* line, char tokens[][E80_CMD_ARG_MAX], int* ntok)
{
    int n = 0;
    const char* p = line;

    while (*p != '\0')
    {
        while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n')
            p++;
        if (*p == '\0')
            break;
        if (n >= E80_CMD_MAX_TOKENS)
            return BENCH_CMD_E_SYNTAX;
        int len = 0;
        while (*p != '\0' && *p != ' ' && *p != '\t' && *p != '\r' && *p != '\n')
        {
            if (len >= E80_CMD_ARG_MAX - 1)
                return BENCH_CMD_E_SYNTAX;
            tokens[n][len++] = *p++;
        }
        tokens[n][len] = '\0';
        n++;
    }
    *ntok = n;
    return BENCH_CMD_OK;
}

/* BUF LOAD crc field: 1-4 hex digits, case-insensitive, no 0x prefix.
 * Rejections (>4 digits, non-hex) are BENCH_CMD_E_ARG at the parse layer. */
static bool bench_parse_hex16(const char* s, uint16_t* out)
{
    if (s == NULL || *s == '\0')
        return false;
    uint32_t v = 0;
    int digits = 0;
    for (const char* p = s; *p != '\0'; p++)
    {
        char c = *p;
        if (c >= '0' && c <= '9')
            c = (char)(c - '0');
        else if (c >= 'a' && c <= 'f')
            c = (char)(c - 'a' + 10);
        else if (c >= 'A' && c <= 'F')
            c = (char)(c - 'A' + 10);
        else
            return false;
        if (++digits > 4)
            return false; /* "12345" etc. */
        v = (v << 4) | (uint32_t)(uint8_t)c;
    }
    *out = (uint16_t)v;
    return true;
}

bench_cmd_err_t bench_cmd_parse(const char* line, bench_cmd_t* out)
{
    char tokens[E80_CMD_MAX_TOKENS][E80_CMD_ARG_MAX];
    int ntok = 0;

    out->id = BENCH_CMD_NONE;

    bench_cmd_err_t e = split_tokens(line, tokens, &ntok);
    if (e != BENCH_CMD_OK)
    {
        out->err = e;
        return e;
    }
    if (ntok == 0)
    {
        out->err = BENCH_CMD_E_SYNTAX;
        return BENCH_CMD_E_SYNTAX;
    }

    out->err = BENCH_CMD_OK;

    if (bench_strcaseeq(tokens[0], "ID?"))
    {
        if (ntok != 1)
            return (out->err = BENCH_CMD_E_SYNTAX);
        out->id = BENCH_CMD_ID;
        return BENCH_CMD_OK;
    }
    if (bench_strcaseeq(tokens[0], "STAT?"))
    {
        if (ntok != 1)
            return (out->err = BENCH_CMD_E_SYNTAX);
        out->id = BENCH_CMD_STAT;
        return BENCH_CMD_OK;
    }
    if (bench_strcaseeq(tokens[0], "STOP"))
    {
        if (ntok != 1)
            return (out->err = BENCH_CMD_E_SYNTAX);
        out->id = BENCH_CMD_STOP;
        return BENCH_CMD_OK;
    }
    if (bench_strcaseeq(tokens[0], "FLASH"))
    {
        /* No arguments: the jump decision depends only on the IWDG state. */
        if (ntok != 1)
            return (out->err = BENCH_CMD_E_SYNTAX);
        out->id = BENCH_CMD_FLASH;
        return BENCH_CMD_OK;
    }
    if (bench_strcaseeq(tokens[0], "HELP") || bench_strcaseeq(tokens[0], "?"))
    {
        if (ntok != 1)
            return (out->err = BENCH_CMD_E_SYNTAX);
        out->id = BENCH_CMD_HELP;
        return BENCH_CMD_OK;
    }
    if (bench_strcaseeq(tokens[0], "ARM"))
    {
        /* ARM TX */
        if (ntok != 2 || !bench_strcaseeq(tokens[1], "TX"))
            return (out->err = BENCH_CMD_E_SYNTAX);
        out->id = BENCH_CMD_ARM_TX;
        return BENCH_CMD_OK;
    }
    if (bench_strcaseeq(tokens[0], "ROLE"))
    {
        if (ntok != 2)
            return (out->err = BENCH_CMD_E_SYNTAX);
        if (bench_strcaseeq(tokens[1], "TX"))
            out->role = BENCH_ROLE_TX;
        else if (bench_strcaseeq(tokens[1], "RX"))
            out->role = BENCH_ROLE_RX;
        else if (bench_strcaseeq(tokens[1], "NONE"))
            out->role = BENCH_ROLE_NONE;
        else
            return (out->err = BENCH_CMD_E_ARG);
        out->id = BENCH_CMD_ROLE;
        return BENCH_CMD_OK;
    }
    if (bench_strcaseeq(tokens[0], "FREQ"))
    {
        if (ntok != 2 || !bench_parse_u32(tokens[1], &out->freq_hz))
            return (out->err = BENCH_CMD_E_ARG);
        out->id = BENCH_CMD_FREQ;
        return BENCH_CMD_OK;
    }
    if (bench_strcaseeq(tokens[0], "PA"))
    {
        if (ntok != 2 || !bench_parse_i8(tokens[1], &out->txpow_dbm))
            return (out->err = BENCH_CMD_E_ARG);
        out->id = BENCH_CMD_PA;
        return BENCH_CMD_OK;
    }
    if (bench_strcaseeq(tokens[0], "BAND"))
    {
        /* BAND OVERRIDE <pin> */
        if (ntok != 3 || !bench_strcaseeq(tokens[1], "OVERRIDE") || !bench_parse_u32(tokens[2], &out->pin))
            return (out->err = BENCH_CMD_E_ARG);
        out->id = BENCH_CMD_BAND_OVERRIDE;
        return BENCH_CMD_OK;
    }
    if (bench_strcaseeq(tokens[0], "POWER"))
    {
        /* POWER MODE OUTDOOR <pin> */
        if (ntok != 4 || !bench_strcaseeq(tokens[1], "MODE") ||
            !bench_strcaseeq(tokens[2], "OUTDOOR") || !bench_parse_u32(tokens[3], &out->pin))
            return (out->err = BENCH_CMD_E_SYNTAX);
        out->id = BENCH_CMD_POWER_OUTDOOR;
        return BENCH_CMD_OK;
    }
    if (bench_strcaseeq(tokens[0], "MOD"))
    {
        /* MOD loRa <sf> <bw_khz>  |  MOD flrc <br_kbps> <dbm> */
        if (ntok != 4)
            return (out->err = BENCH_CMD_E_SYNTAX);
        uint32_t v;
        if (!bench_parse_u32(tokens[2], &v))
            return (out->err = BENCH_CMD_E_ARG);

        if (bench_strcaseeq(tokens[1], "LORA"))
        {
            out->mod = BENCH_MOD_LORA;
            out->sf = (uint8_t)v;
            uint32_t bw_khz;
            if (!bench_parse_u32(tokens[3], &bw_khz))
                return (out->err = BENCH_CMD_E_ARG);
            switch (bw_khz)
            {
            case 125: out->bw_hz = 125000; break;
            case 250: out->bw_hz = 250000; break;
            case 500: out->bw_hz = 500000; break;
            default: return (out->err = BENCH_CMD_E_RANGE);
            }
            if (out->sf < 5 || out->sf > 12)
                return (out->err = BENCH_CMD_E_RANGE);
        }
        else if (bench_strcaseeq(tokens[1], "FLRC"))
        {
            out->mod = BENCH_MOD_FLRC;
            switch (v)
            {
            case 260: out->br_bps = 260000; break;
            case 325: out->br_bps = 325000; break;
            case 520: out->br_bps = 520000; break;
            case 650: out->br_bps = 650000; break;
            case 1040: out->br_bps = 1040000; break;
            case 1300: out->br_bps = 1300000; break;
            case 2080: out->br_bps = 2080000; break;
            case 2600: out->br_bps = 2600000; break;
            default: return (out->err = BENCH_CMD_E_RANGE);
            }
            if (!bench_parse_i8(tokens[3], &out->txpow_dbm))
                return (out->err = BENCH_CMD_E_ARG);
            if (out->txpow_dbm < 0 || out->txpow_dbm > 22)
                return (out->err = BENCH_CMD_E_RANGE);
        }
        else
        {
            return (out->err = BENCH_CMD_E_ARG);
        }
        out->id = BENCH_CMD_MOD;
        return BENCH_CMD_OK;
    }
    if (bench_strcaseeq(tokens[0], "START"))
    {
        /* START [N=<pkts>] [LEN=<bytes>] [GAP=<us>] - order independent */
        out->n_pkts = 100;
        out->len_bytes = 255;
        out->gap_us = 5000;
        out->has_n = out->has_len = out->has_gap = false;
        for (int i = 1; i < ntok; i++)
        {
            char key[E80_CMD_ARG_MAX];
            int k = 0;
            while (tokens[i][k] != '\0' && tokens[i][k] != '=')
            {
                key[k] = tokens[i][k];
                k++;
            }
            key[k] = '\0';
            const char* val = (tokens[i][k] == '=') ? &tokens[i][k + 1] : "";
            uint32_t v;
            if (!bench_parse_u32(val, &v))
                return (out->err = BENCH_CMD_E_ARG);
            if (bench_strcaseeq(key, "N"))
            {
                if (v == 0 || v > 1000000UL)
                    return (out->err = BENCH_CMD_E_RANGE);
                out->n_pkts = v;
                out->has_n = true;
            }
            else if (bench_strcaseeq(key, "LEN"))
            {
                if (v < 6 || v > 511)
                    return (out->err = BENCH_CMD_E_RANGE);
                out->len_bytes = v;
                out->has_len = true;
            }
            else if (bench_strcaseeq(key, "GAP"))
            {
                if (v < 100 || v > 100000000UL)
                    return (out->err = BENCH_CMD_E_RANGE);
                out->gap_us = v;
                out->has_gap = true;
            }
            else
            {
                return (out->err = BENCH_CMD_E_ARG);
            }
        }
        out->id = BENCH_CMD_START;
        return BENCH_CMD_OK;
    }

    if (bench_strcaseeq(tokens[0], "SESSION"))
    {
        /* SESSION <id> */
        if (ntok != 2 || !bench_parse_u32(tokens[1], &out->session_id))
            return (out->err = BENCH_CMD_E_ARG);
        out->id = BENCH_CMD_SESSION;
        return BENCH_CMD_OK;
    }
    if (bench_strcaseeq(tokens[0], "CONFIG"))
    {
        /* CONFIG <id> <replicate> */
        if (ntok != 3 ||
            !bench_parse_u32(tokens[1], &out->config_id) ||
            !bench_parse_u32(tokens[2], &out->replicate))
            return (out->err = BENCH_CMD_E_ARG);
        out->id = BENCH_CMD_CONFIG;
        return BENCH_CMD_OK;
    }

    if (bench_strcaseeq(tokens[0], "PRBS9"))
    {
        /* PRBS9 ON|OFF — chip-level PRBS9 TX test mode */
        if (ntok != 2)
            return (out->err = BENCH_CMD_E_SYNTAX);
        if (bench_strcaseeq(tokens[1], "ON"))
            out->prbs9_enable = true;
        else if (bench_strcaseeq(tokens[1], "OFF"))
            out->prbs9_enable = false;
        else
            return (out->err = BENCH_CMD_E_ARG);
        out->id = BENCH_CMD_PRBS9;
        return BENCH_CMD_OK;
    }

    if (bench_strcaseeq(tokens[0], "PRBS"))
    {
        /* PRBS ON|OFF — toggle PRBS-15 RX verification */
        if (ntok != 2)
            return (out->err = BENCH_CMD_E_SYNTAX);
        if (bench_strcaseeq(tokens[1], "ON"))
            out->prbs_enable = true;
        else if (bench_strcaseeq(tokens[1], "OFF"))
            out->prbs_enable = false;
        else
            return (out->err = BENCH_CMD_E_ARG);
        out->id = BENCH_CMD_PRBS;
        return BENCH_CMD_OK;
    }

    if (bench_strcaseeq(tokens[0], "BUF"))
    {
        /* TX buffer: BUF CLEAR | BUF STATUS | BUF LOAD <n> <crc16_hex>
         * (tx-buffer-spec). The reject MATRIX (role RX / burst / armed) is
         * runtime state — checked in bench.c's handler, not here. */
        if (ntok < 2)
            return (out->err = BENCH_CMD_E_SYNTAX); /* bare "BUF" */
        if (bench_strcaseeq(tokens[1], "CLEAR"))
        {
            if (ntok != 2)
                return (out->err = BENCH_CMD_E_SYNTAX); /* "BUF CLEAR X" */
            out->id = BENCH_CMD_BUF_CLEAR;
            return BENCH_CMD_OK;
        }
        if (bench_strcaseeq(tokens[1], "STATUS"))
        {
            if (ntok != 2)
                return (out->err = BENCH_CMD_E_SYNTAX); /* "BUF STATUS 1" */
            out->id = BENCH_CMD_BUF_STATUS;
            return BENCH_CMD_OK;
        }
        if (bench_strcaseeq(tokens[1], "LOAD"))
        {
            if (ntok != 4)
                return (out->err = BENCH_CMD_E_SYNTAX); /* missing/extra args */
            if (!bench_parse_u32(tokens[2], &out->buf_load_n))
                return (out->err = BENCH_CMD_E_ARG); /* non-numeric / u32 overflow */
            if (out->buf_load_n == 0 || out->buf_load_n > BUF_CAPACITY)
                return (out->err = BENCH_CMD_E_RANGE); /* 1..4096 */
            if (!bench_parse_hex16(tokens[3], &out->buf_load_crc))
                return (out->err = BENCH_CMD_E_ARG); /* not 1-4 hex digits */
            out->id = BENCH_CMD_BUF_LOAD;
            return BENCH_CMD_OK;
        }
        return (out->err = BENCH_CMD_E_ARG); /* "BUF FOO": known word, bad subcommand */
    }

    return (out->err = BENCH_CMD_E_UNKNOWN);
}

const char* bench_cmd_err_str(bench_cmd_err_t e)
{
    switch (e)
    {
    case BENCH_CMD_OK: return "OK";
    case BENCH_CMD_E_SYNTAX: return "SYNTAX";
    case BENCH_CMD_E_ARG: return "ARG";
    case BENCH_CMD_E_RANGE: return "RANGE";
    case BENCH_CMD_E_UNKNOWN: return "UNKNOWN";
    }
    return "?";
}

/* ---- START per-mod LEN gate (FIX-T2) ---------------------------------- */

/* TDD RED STUB: wrong on purpose so the truth-table test fails before the
 * GREEN implementation lands. Returns "" (never NULL) so strcmp-based
 * assertions crash nowhere. */
bool bench_start_len_ok(bench_mod_t mod, uint32_t len)
{
    (void)mod;
    (void)len;
    return true;
}

const char* bench_start_len_err_str(void)
{
    return "";
}
