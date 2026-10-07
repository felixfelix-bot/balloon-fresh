/**
 * @file    temp_comp.cpp
 * @brief   ADR-057 implementation: LR2021 on-chip (XOSC-adjacent) temperature
 *          read, per-unit calibration curve, correction-application hook,
 *          1PPS-gated discipline state machine, and the MS5611 cross-check.
 *
 * Pure C++ — no Arduino, no SPI hardware.  See temp_comp.h for the full
 * provenance table; every constant here traces to a named vendored-source line
 * or carries TODO(unverified).
 *
 * Build/verify:  make -C firmware/rp2040/host-tests && ./host-tests/test_temp_comp
 */

#include "temp_comp.h"

/* Deliberately NO <math.h>: the module is embedded firmware, so its only two
 * libm needs (NaN test and |x|) are inlined here.  This keeps temp_comp.cpp
 * freestanding-clean with no libm/libc dependency at all, which also lets the
 * exact same translation unit cross-compile for the RP2040 (Cortex-M0+). */

static inline int tc_is_nan(float x)
{
    /* IEEE-754: a NaN is not equal to itself.  No libm needed. */
    return (x != x) ? 1 : 0;
}

static inline float tc_fabsf(float x)
{
    return (x < 0.0f) ? -x : x;
}

/* ------------------------------------------------------------------------- */
/* helpers                                                                   */
/* ------------------------------------------------------------------------- */

static int curve_points_are_sorted(const temp_comp_curve_point_t *pts, uint8_t n)
{
    for (uint8_t i = 1; i < n; ++i)
    {
        if (!(pts[i].temp_c > pts[i - 1].temp_c)) /* also rejects NaN / dup */
        {
            return 0;
        }
    }
    return 1;
}

/* ------------------------------------------------------------------------- */
/* 4. Layer (a) — read the on-chip sensor                                    */
/* ------------------------------------------------------------------------- */

uint8_t temp_comp_lr2021_get_temp_arg(uint8_t source, uint8_t bits)
{
    /* Mirrors RadioLib LR2021_cmds_chip_control.cpp:172 (and the Semtech
     * driver at src/lr20xx_system.c:463 — same packing, independently). */
    const uint8_t res_field =
        (uint8_t)((TEMP_COMP_LR2021_MEAS_RESOLUTION_OFFSET + bits) & 0x07u);
    return (uint8_t)((source & 0x30u) |
                     (TEMP_COMP_LR2021_TEMP_FORMAT_DEG_C << 3) |
                     res_field);
}

float temp_comp_deg_c_from_raw_radiolib(uint16_t raw)
{
    /* LR2021_cmds_chip_control.cpp:171-180, verbatim arithmetic. */
    return (float)raw / TEMP_COMP_DEG_C_SCALE_RADIOLIB;
}

float temp_comp_deg_c_from_reply_semtech(const uint8_t reply[2])
{
    /* inc/lr20xx_system.h:399-400 — "the first byte returned contains the
     * integer part, the second the fractional part".  Sign rides on byte 0. */
    const int8_t  integer_part    = (int8_t)reply[0];
    const uint8_t fractional_part = reply[1];
    return (float)integer_part +
           (float)fractional_part / TEMP_COMP_DEG_C_SCALE_SEMTECH;
}

float temp_comp_deg_c_from_raw_signed(int16_t raw, float scale)
{
    if (!(scale > 0.0f))
    {
        return 0.0f;
    }
    return (float)raw / scale;
}

int temp_comp_lr2021_read_deg_c(const temp_comp_spi_t *spi, uint8_t source,
                                uint8_t bits, float *out_deg_c)
{
    if ((spi == NULL) || (spi->read == NULL) || (out_deg_c == NULL))
    {
        return TEMP_COMP_ERR_ARG;
    }

    uint8_t frame[TEMP_COMP_GET_TEMP_CMD_LEN]; /* {0x01, 0x25, arg} */
    frame[0] = (uint8_t)(TEMP_COMP_LR2021_CMD_GET_TEMP >> 8);
    frame[1] = (uint8_t)(TEMP_COMP_LR2021_CMD_GET_TEMP & 0xFFu);
    frame[2] = temp_comp_lr2021_get_temp_arg(source, bits);

    uint8_t reply[TEMP_COMP_GET_TEMP_RPL_LEN] = {0u, 0u};

    const int rc = spi->read(spi->ctx, frame, sizeof(frame),
                             reply, sizeof(reply));
    if (rc != TEMP_COMP_OK)
    {
        return TEMP_COMP_ERR_SPI;
    }

    /* Signed-capable conversion so the −60 °C mission is representable —
     * RadioLib's unsigned /320.0f path is kept available by callers that need
     * wire-compatibility, but is NOT the default here (see temp_comp.h). */
    *out_deg_c = temp_comp_deg_c_from_reply_semtech(reply);
    return TEMP_COMP_OK;
}

int temp_comp_lr2021_read_xosc_deg_c(const temp_comp_spi_t *spi, float *out_deg_c)
{
    return temp_comp_lr2021_read_deg_c(
        spi, TEMP_COMP_LR2021_TEMP_SOURCE_XOSC,
        TEMP_COMP_LR2021_TEMP_DEFAULT_BITS, out_deg_c);
}

int temp_comp_lr2021_read_vbe_deg_c(const temp_comp_spi_t *spi, float *out_deg_c)
{
    return temp_comp_lr2021_read_deg_c(
        spi, TEMP_COMP_LR2021_TEMP_SOURCE_VBE,
        TEMP_COMP_LR2021_TEMP_DEFAULT_BITS, out_deg_c);
}

/* ------------------------------------------------------------------------- */
/* 5. Layer (e) — MS5611 cross-check                                         */
/* ------------------------------------------------------------------------- */

int temp_comp_crosscheck(float lr2021_xosc_deg_c, float ms5611_deg_c,
                         float max_delta_c, temp_comp_crosscheck_t *out)
{
    if (out == NULL)
    {
        return TEMP_COMP_ERR_ARG;
    }

    const float max_delta =
        (max_delta_c < TEMP_COMP_CROSSCHECK_MIN_DELTA_C)
            ? TEMP_COMP_CROSSCHECK_MIN_DELTA_C
            : max_delta_c;

    out->delta_c     = lr2021_xosc_deg_c - ms5611_deg_c;
    out->max_delta_c = max_delta;
    out->fault       = (tc_fabsf(out->delta_c) > max_delta) ? 1u : 0u;

    /* NaN in either input must not read as "healthy". */
    if (tc_is_nan(out->delta_c))
    {
        out->fault = 1u;
    }
    return TEMP_COMP_OK;
}

/* ------------------------------------------------------------------------- */
/* 6. Layer (b) — the per-unit calibration curve                             */
/* ------------------------------------------------------------------------- */

void temp_comp_curve_init_empty(temp_comp_curve_t *curve)
{
    if (curve == NULL)
    {
        return;
    }
    curve->n = 0u;
    for (uint8_t i = 0u; i < TEMP_COMP_CURVE_MAX_POINTS; ++i)
    {
        curve->pts[i].temp_c = 0.0f;
        curve->pts[i].ppm    = 0.0f;
    }
}

int temp_comp_curve_add_point(temp_comp_curve_t *curve, float temp_c, float ppm)
{
    if ((curve == NULL) || tc_is_nan(temp_c) || tc_is_nan(ppm))
    {
        return TEMP_COMP_ERR_ARG;
    }
    if (curve->n >= (uint8_t)TEMP_COMP_CURVE_MAX_POINTS)
    {
        return TEMP_COMP_ERR_CURVE_FULL;
    }

    /* Find the insertion slot; reject an exact duplicate temperature so the
     * interpolation is never ambiguous. */
    uint8_t slot = 0u;
    while ((slot < curve->n) && (curve->pts[slot].temp_c < temp_c))
    {
        ++slot;
    }
    if ((slot < curve->n) && (curve->pts[slot].temp_c == temp_c))
    {
        return TEMP_COMP_ERR_CURVE_DUP_TEMP;
    }

    for (uint8_t i = curve->n; i > slot; --i)
    {
        curve->pts[i] = curve->pts[i - 1u];
    }
    curve->pts[slot].temp_c = temp_c;
    curve->pts[slot].ppm    = ppm;
    ++curve->n;
    return TEMP_COMP_OK;
}

int temp_comp_curve_load(temp_comp_curve_t *curve,
                         const temp_comp_curve_point_t *pts, uint8_t n)
{
    if ((curve == NULL) || (n > (uint8_t)TEMP_COMP_CURVE_MAX_POINTS))
    {
        return TEMP_COMP_ERR_ARG;
    }
    if (n > 0u)
    {
        if (pts == NULL)
        {
            return TEMP_COMP_ERR_ARG;
        }
        if (!curve_points_are_sorted(pts, n))
        {
            return TEMP_COMP_ERR_CURVE_NOT_SORTED;
        }
    }

    temp_comp_curve_init_empty(curve);
    for (uint8_t i = 0u; i < n; ++i)
    {
        curve->pts[i] = pts[i];
    }
    curve->n = n;
    return TEMP_COMP_OK;
}

uint8_t temp_comp_curve_is_identity(const temp_comp_curve_t *curve)
{
    return ((curve == NULL) || (curve->n == 0u)) ? 1u : 0u;
}

float temp_comp_curve_correction_ppm(const temp_comp_curve_t *curve, float temp_c)
{
    /* Identity until the bench fills the curve — never an invented value. */
    if ((curve == NULL) || (curve->n == 0u) || tc_is_nan(temp_c))
    {
        return 0.0f;
    }
    if (curve->n == 1u)
    {
        return curve->pts[0].ppm;
    }

    /* Clamp outside the characterised span. */
    if (temp_c <= curve->pts[0].temp_c)
    {
        return curve->pts[0].ppm;
    }
    if (temp_c >= curve->pts[curve->n - 1u].temp_c)
    {
        return curve->pts[curve->n - 1u].ppm;
    }

    for (uint8_t i = 1u; i < curve->n; ++i)
    {
        const float t0 = curve->pts[i - 1u].temp_c;
        const float t1 = curve->pts[i].temp_c;
        if (temp_c <= t1)
        {
            const float span = t1 - t0;
            if (!(span > 0.0f))
            {
                return curve->pts[i].ppm;
            }
            const float w = (temp_c - t0) / span;
            return curve->pts[i - 1u].ppm +
                   w * (curve->pts[i].ppm - curve->pts[i - 1u].ppm);
        }
    }
    return curve->pts[curve->n - 1u].ppm;
}

int temp_comp_correction_for_temp(const temp_comp_curve_t *curve, float temp_c,
                                  uint32_t nominal_hz,
                                  float *corr_ppm_out, float *corr_hz_out)
{
    if ((corr_ppm_out == NULL) || (corr_hz_out == NULL))
    {
        return TEMP_COMP_ERR_ARG;
    }

    const float ppm = temp_comp_curve_correction_ppm(curve, temp_c);
    *corr_ppm_out = ppm;
    /* delta_hz = f_nominal * (ppm * 1e-6) */
    *corr_hz_out  = (float)nominal_hz * (ppm * 1.0e-6f);
    return TEMP_COMP_OK;
}

/* ------------------------------------------------------------------------- */
/* 7. Layer (c) — apply the correction                                       */
/* ------------------------------------------------------------------------- */

void temp_comp_build_xosc_cp_trim_frame(uint8_t xta, uint8_t xtb,
                                        uint8_t wait_time_us, uint8_t out[5])
{
    if (out == NULL)
    {
        return;
    }
    /* {0x01, 0x31, xta & 0x3F, xtb & 0x3F, wait} — RadioLib
     * LR2021_cmds_chip_control.cpp:306-309; same 5-byte shape in the Semtech
     * driver's configure_xosc (src/lr20xx_system.c:566-577). */
    out[0] = (uint8_t)(TEMP_COMP_LR2021_CMD_SET_XOSC_CP_TRIM >> 8);
    out[1] = (uint8_t)(TEMP_COMP_LR2021_CMD_SET_XOSC_CP_TRIM & 0xFFu);
    out[2] = (uint8_t)(xta & TEMP_COMP_XOSC_TRIM_CODE_MAX);
    out[3] = (uint8_t)(xtb & TEMP_COMP_XOSC_TRIM_CODE_MAX);
    out[4] = wait_time_us;
}

void temp_comp_build_temp_comp_cfg_frame(uint8_t mode, uint8_t ntc_en,
                                         uint8_t out[3])
{
    if (out == NULL)
    {
        return;
    }
    /* {0x01, 0x32, ((ntc_en?1:0) << 2) + mode} — Semtech
     * src/lr20xx_system.c:579-589.  CRYSTAL-configured modules only. */
    out[0] = (uint8_t)(TEMP_COMP_LR2021_CMD_SET_TEMP_COMP_CFG >> 8);
    out[1] = (uint8_t)(TEMP_COMP_LR2021_CMD_SET_TEMP_COMP_CFG & 0xFFu);
    out[2] = (uint8_t)(((ntc_en ? 1u : 0u) << 2) | (uint8_t)(mode & 0x03u));
}

int temp_comp_build_ntc_params_frame(uint16_t ntc_r_ratio, uint16_t ntc_beta,
                                     uint8_t delay, uint8_t out[7])
{
    if (out == NULL)
    {
        return TEMP_COMP_ERR_ARG;
    }
    /* {0x01, 0x33, ratio>>8, ratio, beta>>8, beta, delay} — Semtech
     * src/lr20xx_system.c:591-604.  ratio is a 10.9b resistance bias ratio,
     * beta's unit is 2 K, delay is the first-order time-delay coefficient
     * (inc/lr20xx_system.h:528-539). */
    out[0] = (uint8_t)(TEMP_COMP_LR2021_CMD_SET_NTC_PARAMS >> 8);
    out[1] = (uint8_t)(TEMP_COMP_LR2021_CMD_SET_NTC_PARAMS & 0xFFu);
    out[2] = (uint8_t)(ntc_r_ratio >> 8);
    out[3] = (uint8_t)(ntc_r_ratio & 0xFFu);
    out[4] = (uint8_t)(ntc_beta >> 8);
    out[5] = (uint8_t)(ntc_beta & 0xFFu);
    out[6] = delay;
    return TEMP_COMP_OK;
}

int temp_comp_ppm_to_xosc_cp_trim(float corr_ppm, uint8_t *xta_out, uint8_t *xtb_out)
{
    /* TODO(unverified): SetXoscCpTrim takes raw 6-bit foot-capacitance codes,
     * not ppm, and no ppm->code mapping exists in either vendored driver (nor
     * in ADR-042 / ADR-056).  Refuse rather than invent one. */
    (void)corr_ppm;
    (void)xta_out;
    (void)xtb_out;
    return TEMP_COMP_ERR_UNVERIFIED_MAPPING;
}

int temp_comp_apply_correction(const temp_comp_curve_t *curve, float temp_c,
                               uint32_t nominal_hz,
                               uint8_t xta, uint8_t xtb, uint8_t wait_time_us,
                               uint8_t frame_out[TEMP_COMP_XOSC_TRIM_FRAME_LEN],
                               float *corr_ppm_out, float *corr_hz_out)
{
    if ((frame_out == NULL) || (corr_ppm_out == NULL) || (corr_hz_out == NULL))
    {
        return TEMP_COMP_ERR_ARG;
    }

    for (uint8_t i = 0u; i < TEMP_COMP_XOSC_TRIM_FRAME_LEN; ++i)
    {
        frame_out[i] = 0u;
    }

    const int rc = temp_comp_correction_for_temp(curve, temp_c, nominal_hz,
                                                 corr_ppm_out, corr_hz_out);
    if (rc != TEMP_COMP_OK)
    {
        return rc;
    }

    /* No bench data yet: nothing to apply, and that is not an error — the
     * identity curve is the honest state before the characterisation. */
    if (temp_comp_curve_is_identity(curve))
    {
        return TEMP_COMP_OK;
    }

    /* Bench data exists, but the ppm->trim-code mapping does not.  Emit the
     * verified frame shape only if the caller supplied trim codes; either way
     * report UNVERIFIED so the caller logs and does not fly on it. */
    if ((xta != 0u) || (xtb != 0u))
    {
        temp_comp_build_xosc_cp_trim_frame(xta, xtb, wait_time_us, frame_out);
    }
    return TEMP_COMP_ERR_UNVERIFIED_MAPPING;
}

/* ------------------------------------------------------------------------- */
/* 8. Layer (d) — 1PPS-gated discipline                                      */
/* ------------------------------------------------------------------------- */

double temp_comp_pps_resolution_ppm(uint32_t ref_hz, uint32_t window_s)
{
    if ((ref_hz == 0u) || (window_s == 0u))
    {
        return 0.0;
    }
    /* df/f = 1 / (f_ref * M)  =>  ppm = 1e6 / (f_ref * M) */
    return 1.0e6 / ((double)ref_hz * (double)window_s);
}

uint32_t temp_comp_pps_resolution_ppb(uint32_t ref_hz, uint32_t window_s)
{
    if ((ref_hz == 0u) || (window_s == 0u))
    {
        return 0u;
    }
    /* ppb = 1e9 / (f_ref * M), integer-truncated. */
    const uint64_t denom = (uint64_t)ref_hz * (uint64_t)window_s;
    if (denom == 0u)
    {
        return 0u;
    }
    return (uint32_t)(1000000000ULL / denom);
}

double temp_comp_pps_frac_error_ppm(uint64_t n_measured, uint32_t ref_hz,
                                    uint32_t window_s)
{
    if ((ref_hz == 0u) || (window_s == 0u))
    {
        return 0.0;
    }
    const double ideal = (double)ref_hz * (double)window_s;
    if (!(ideal > 0.0))
    {
        return 0.0;
    }
    return 1.0e6 * (((double)n_measured - ideal) / ideal);
}

int temp_comp_pps_gate_begin(temp_comp_pps_gate_t *g, uint32_t ref_hz,
                             uint32_t window_s)
{
    if (g == NULL)
    {
        return TEMP_COMP_ERR_ARG;
    }
    if ((ref_hz == 0u) || (window_s == 0u) ||
        (window_s > TEMP_COMP_PPS_MAX_WINDOW_S))
    {
        return TEMP_COMP_ERR_ARG;
    }

    g->ref_hz      = ref_hz;
    g->window_s    = window_s;
    g->pps_edges   = 0u;
    g->first_count = 0u;
    g->last_count  = 0u;
    g->armed       = 1u;
    g->ready       = 0u;
    g->last_ppm    = 0.0;
    return TEMP_COMP_OK;
}

int temp_comp_pps_gate_reset(temp_comp_pps_gate_t *g)
{
    if ((g == NULL) || (g->armed == 0u))
    {
        return TEMP_COMP_ERR_NOT_ARMED;
    }
    g->pps_edges   = 0u;
    g->first_count = 0u;
    g->last_count  = 0u;
    g->ready       = 0u;
    g->last_ppm    = 0.0;
    return TEMP_COMP_OK;
}

int temp_comp_pps_gate_on_pps(temp_comp_pps_gate_t *g, uint64_t ref_count_now)
{
    if ((g == NULL) || (g->armed == 0u))
    {
        return TEMP_COMP_ERR_NOT_ARMED;
    }

    if (g->pps_edges == 0u)
    {
        g->first_count = ref_count_now;
    }
    g->last_count = ref_count_now;
    ++g->pps_edges;

    /* window_s intervals need window_s + 1 edges (first edge anchors the
     * window; the counter delta spans M whole seconds). */
    if (g->pps_edges > g->window_s)
    {
        /* The 32-bit reference counter wraps; a wrap would corrupt the delta,
         * so a measured delta smaller than one full second of counts is
         * rejected as a missed wrap rather than reported as a huge error. */
        const uint64_t min_expected =
            (uint64_t)g->ref_hz * (uint64_t)g->window_s;
        if (g->last_count >= g->first_count)
        {
            const uint64_t measured = g->last_count - g->first_count;
            if (measured >= min_expected / 2u)
            {
                g->last_ppm = temp_comp_pps_frac_error_ppm(
                    measured, g->ref_hz, g->window_s);
                g->ready = 1u;
            }
        }

        /* Roll into the next window from this edge. */
        g->pps_edges   = 1u;
        g->first_count = ref_count_now;
    }

    return TEMP_COMP_OK;
}
