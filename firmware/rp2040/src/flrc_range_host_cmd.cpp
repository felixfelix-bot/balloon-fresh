/**
 * @file    flrc_range_host_cmd.cpp
 * @brief   Pure console command parser for the host-driven range bench (FW-2).
 *
 * Port of E80 bench_cmd.c (~/repos/balloon-e80bench/firmware/e80-stm32-bench/
 * src/bench_cmd.c) adapted to plan §1 REV-2 grammar. See flrc_range_host_cmd.h
 * for the grammar deltas and the error-class split between this parser
 * (OK/ARG/RANGE/UNKNOWN) and the FW-6 dispatch layer (BUSY/INHIBITED/
 * POWER-LOCKED).
 *
 * No dynamic allocation, no Arduino includes — pure TU for firmware + tests.
 */

#include "flrc_range_host_cmd.h"

#include <stddef.h>

int rh_strcaseeq(const char* a, const char* b)
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

bool rh_parse_u32(const char* s, uint32_t* out)
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

bool rh_parse_i8(const char* s, int8_t* out)
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
    if (!rh_parse_u32(s, &v))
        return false;
    int32_t sv = neg ? -(int32_t)v : (int32_t)v;
    if (sv < -128 || sv > 127)
        return false;
    *out = (int8_t)sv;
    return true;
}

rh_cmd_err_t rh_cmd_tokenize(const char* line, char tokens[][RH_CMD_ARG_MAX],
                             int max_tokens, int* ntok)
{
    int n = 0;
    const char* p = line;

    while (*p != '\0')
    {
        while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n')
            p++;
        if (*p == '\0')
            break;
        if (n >= max_tokens)
            return RH_CMD_E_ARG;
        int len = 0;
        while (*p != '\0' && *p != ' ' && *p != '\t' && *p != '\r' && *p != '\n')
        {
            if (len >= RH_CMD_ARG_MAX - 1)
                return RH_CMD_E_ARG;
            tokens[n][len++] = *p++;
        }
        tokens[n][len] = '\0';
        n++;
    }
    *ntok = n;
    return RH_CMD_OK;
}

/* FLRC bitrate table: kbps -> bps (LR2021 legal rates, §1) */
static uint32_t flrc_br_hz(uint32_t br_kbps, bool* ok)
{
    switch (br_kbps)
    {
    case 260:  *ok = true; return 260000;
    case 325:  *ok = true; return 325000;
    case 520:  *ok = true; return 520000;
    case 650:  *ok = true; return 650000;
    case 1040: *ok = true; return 1040000;
    case 1300: *ok = true; return 1300000;
    case 2080: *ok = true; return 2080000;
    case 2600: *ok = true; return 2600000;
    default:   *ok = false; return 0;
    }
}

rh_cmd_err_t rh_cmd_parse(const char* line, rh_cmd_t* out)
{
    char tokens[RH_CMD_MAX_TOKENS][RH_CMD_ARG_MAX];
    int ntok = 0;

    out->id = RH_CMD_NONE;

    rh_cmd_err_t e = rh_cmd_tokenize(line, tokens, RH_CMD_MAX_TOKENS, &ntok);
    if (e != RH_CMD_OK)
    {
        out->err = e;
        return e;
    }
    if (ntok == 0)
    {
        out->err = RH_CMD_E_ARG; /* empty/whitespace-only line: no command */
        return RH_CMD_E_ARG;
    }

    out->err = RH_CMD_OK;

    /* ---- no-argument commands ------------------------------------------ */

    if (rh_strcaseeq(tokens[0], "ID?"))
    {
        if (ntok != 1)
            return (out->err = RH_CMD_E_ARG);
        out->id = RH_CMD_ID;
        return RH_CMD_OK;
    }
    if (rh_strcaseeq(tokens[0], "STAT?"))
    {
        if (ntok != 1)
            return (out->err = RH_CMD_E_ARG);
        out->id = RH_CMD_STAT;
        return RH_CMD_OK;
    }
    if (rh_strcaseeq(tokens[0], "STOP"))
    {
        if (ntok != 1)
            return (out->err = RH_CMD_E_ARG);
        out->id = RH_CMD_STOP;
        return RH_CMD_OK;
    }
    if (rh_strcaseeq(tokens[0], "START"))
    {
        /* REV-2: START is bare — LEN/N/GAP are standalone commands and
         * carry the burst config; E80-style kwargs are a syntax error. */
        if (ntok != 1)
            return (out->err = RH_CMD_E_ARG);
        out->id = RH_CMD_START;
        return RH_CMD_OK;
    }
    if (rh_strcaseeq(tokens[0], "HELP") || rh_strcaseeq(tokens[0], "?"))
    {
        if (ntok != 1)
            return (out->err = RH_CMD_E_ARG);
        out->id = RH_CMD_HELP;
        return RH_CMD_OK;
    }

    /* ---- ROLE TX|RX|NONE ------------------------------------------------- */

    if (rh_strcaseeq(tokens[0], "ROLE"))
    {
        if (ntok != 2)
            return (out->err = RH_CMD_E_ARG);
        if (rh_strcaseeq(tokens[1], "TX"))
            out->role = RH_ROLE_TX;
        else if (rh_strcaseeq(tokens[1], "RX"))
            out->role = RH_ROLE_RX;
        else if (rh_strcaseeq(tokens[1], "NONE"))
            out->role = RH_ROLE_NONE;
        else
            return (out->err = RH_CMD_E_ARG);
        out->id = RH_CMD_ROLE;
        return RH_CMD_OK;
    }

    /* ---- MOD FLRC <br_kbps> | MOD LORA <sf> <bw_khz> -------------------- */

    if (rh_strcaseeq(tokens[0], "MOD"))
    {
        uint32_t v;

        if (ntok < 2)
            return (out->err = RH_CMD_E_ARG); /* bare "MOD": no modulation word */

        if (rh_strcaseeq(tokens[1], "FLRC"))
        {
            if (ntok != 3 || !rh_parse_u32(tokens[2], &v))
                return (out->err = RH_CMD_E_ARG);
            bool ok = false;
            out->mod = BENCH_MOD_FLRC;
            out->br_bps = flrc_br_hz(v, &ok);
            if (!ok)
                return (out->err = RH_CMD_E_RANGE);
            out->id = RH_CMD_MOD;
            return RH_CMD_OK;
        }
        if (rh_strcaseeq(tokens[1], "LORA"))
        {
            if (ntok != 4 || !rh_parse_u32(tokens[2], &v))
                return (out->err = RH_CMD_E_ARG);
            if (v < 5 || v > 12)
                return (out->err = RH_CMD_E_RANGE);
            uint32_t bw_khz;
            if (!rh_parse_u32(tokens[3], &bw_khz))
                return (out->err = RH_CMD_E_ARG);
            out->mod = BENCH_MOD_LORA;
            out->sf = (uint8_t)v;
            switch (bw_khz)
            {
            case 125: out->bw_hz = 125000; break;
            case 250: out->bw_hz = 250000; break;
            case 500: out->bw_hz = 500000; break;
            default:  return (out->err = RH_CMD_E_RANGE);
            }
            out->id = RH_CMD_MOD;
            return RH_CMD_OK;
        }
        /* unknown modulation word, or missing word ("MOD" alone) */
        return (out->err = RH_CMD_E_ARG);
    }

    /* ---- FREQ <hz> — EU SRD hard clamp 863..870 MHz (§1) ----------------- */

    if (rh_strcaseeq(tokens[0], "FREQ"))
    {
        if (ntok != 2 || !rh_parse_u32(tokens[1], &out->freq_hz))
            return (out->err = RH_CMD_E_ARG);
        if (out->freq_hz < RH_FREQ_MIN_HZ || out->freq_hz > RH_FREQ_MAX_HZ)
            return (out->err = RH_CMD_E_RANGE);
        out->id = RH_CMD_FREQ;
        return RH_CMD_OK;
    }

    /* ---- PA <dbm> — range only; >10 dBm unlock is FW-6 dispatch ---------- */

    if (rh_strcaseeq(tokens[0], "PA"))
    {
        if (ntok != 2 || !rh_parse_i8(tokens[1], &out->txpow_dbm))
            return (out->err = RH_CMD_E_ARG);
        if (out->txpow_dbm < RH_PA_MIN_DBM || out->txpow_dbm > RH_PA_MAX_DBM)
            return (out->err = RH_CMD_E_RANGE);
        out->id = RH_CMD_PA;
        return RH_CMD_OK;
    }

    /* ---- standalone LEN / N / GAP (REV-2 grammar) ------------------------ */

    if (rh_strcaseeq(tokens[0], "LEN"))
    {
        if (ntok != 2 || !rh_parse_u32(tokens[1], &out->len_bytes))
            return (out->err = RH_CMD_E_ARG);
        if (out->len_bytes < RH_LEN_MIN || out->len_bytes > RH_LEN_MAX)
            return (out->err = RH_CMD_E_RANGE);
        out->id = RH_CMD_LEN;
        return RH_CMD_OK;
    }
    if (rh_strcaseeq(tokens[0], "N"))
    {
        if (ntok != 2 || !rh_parse_u32(tokens[1], &out->n_pkts))
            return (out->err = RH_CMD_E_ARG);
        if (out->n_pkts < RH_N_MIN || out->n_pkts > RH_N_MAX)
            return (out->err = RH_CMD_E_RANGE);
        out->id = RH_CMD_N;
        return RH_CMD_OK;
    }
    if (rh_strcaseeq(tokens[0], "GAP"))
    {
        if (ntok != 2 || !rh_parse_u32(tokens[1], &out->gap_us))
            return (out->err = RH_CMD_E_ARG);
        if (out->gap_us < RH_GAP_MIN_US || out->gap_us > RH_GAP_MAX_US)
            return (out->err = RH_CMD_E_RANGE);
        out->id = RH_CMD_GAP;
        return RH_CMD_OK;
    }

    /* ---- POWER MODE OUTDOOR <pin> (pin == 2026, §1) ---------------------- */

    if (rh_strcaseeq(tokens[0], "POWER"))
    {
        if (ntok != 4 || !rh_strcaseeq(tokens[1], "MODE") ||
            !rh_strcaseeq(tokens[2], "OUTDOOR") || !rh_parse_u32(tokens[3], &out->pin))
            return (out->err = RH_CMD_E_ARG);
        if (out->pin != RH_POWER_PIN)
            return (out->err = RH_CMD_E_ARG);
        out->id = RH_CMD_POWER_OUTDOOR;
        return RH_CMD_OK;
    }

    return (out->err = RH_CMD_E_UNKNOWN);
}

const char* rh_cmd_err_str(rh_cmd_err_t e)
{
    switch (e)
    {
    case RH_CMD_OK:            return "OK";
    case RH_CMD_E_ARG:         return "ARG";
    case RH_CMD_E_RANGE:       return "RANGE";
    case RH_CMD_E_BUSY:        return "BUSY";
    case RH_CMD_E_INHIBITED:   return "INHIBITED";
    case RH_CMD_E_POWER_LOCKED: return "POWER-LOCKED";
    case RH_CMD_E_UNKNOWN:     return "UNKNOWN";
    }
    return "?";
}

bool rh_cmd_is_config(rh_cmd_id_t id)
{
    switch (id)
    {
    case RH_CMD_MOD:
    case RH_CMD_FREQ:
    case RH_CMD_PA:
    case RH_CMD_LEN:
        return true;
    default:
        return false;
    }
}
