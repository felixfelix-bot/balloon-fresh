/**
 * @file    test_temp_comp.cpp
 * @brief   Host unit tests for the ADR-058 temperature-compensation module
 *          (src/temp_comp.cpp): the LR2021 GetTemp argument packing and °C
 *          conversion, the per-unit calibration curve (identity until the bench
 *          fills it), the verified command-frame builders, the honest
 *          TODO(unverified) ppm->trim stub, the MS5611 cross-check, and the
 *          1PPS-gated discipline arithmetic/state machine.
 *
 * Every expected byte/constant here is pinned to the vendored sources named in
 * src/temp_comp.h — this test is what stops the module drifting from them.
 *
 * Run:  make -C firmware/rp2040/host-tests && ./host-tests/test_temp_comp
 */

#include "temp_comp.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

static int failures = 0;

#define CHECK(cond)                                                            \
    do                                                                         \
    {                                                                          \
        if (!(cond))                                                           \
        {                                                                      \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);             \
            ++failures;                                                        \
        }                                                                      \
    } while (0)

static int near_f(float a, float b, float tol)
{
    return fabsf(a - b) <= tol;
}

static int near_d(double a, double b, double tol)
{
    return fabs(a - b) <= tol;
}

/* ------------------------------------------------------------------------- */
/* Layer (a): GetTemp argument packing                                       */
/* ------------------------------------------------------------------------- */

static void test_get_temp_arg_packing(void)
{
    /* XOSC + 13 bits: (0x01<<4) | (0x01<<3) | ((8+13)&7 == 5) = 0x1D.
     * RadioLib LR2021_cmds_chip_control.cpp:172; Semtech system.c:463. */
    CHECK(temp_comp_lr2021_get_temp_arg(TEMP_COMP_LR2021_TEMP_SOURCE_XOSC, 13u)
          == 0x1Du);

    /* VBE + 13 bits: 0x00 | 0x08 | 0x05 = 0x0D. */
    CHECK(temp_comp_lr2021_get_temp_arg(TEMP_COMP_LR2021_TEMP_SOURCE_VBE, 13u)
          == 0x0Du);

    /* XOSC + 8 bits: (8+8)&7 = 0 -> 0x10 | 0x08 = 0x18. */
    CHECK(temp_comp_lr2021_get_temp_arg(TEMP_COMP_LR2021_TEMP_SOURCE_XOSC, 8u)
          == 0x18u);

    /* An out-of-range resolution must not corrupt the source/format fields. */
    CHECK((temp_comp_lr2021_get_temp_arg(TEMP_COMP_LR2021_TEMP_SOURCE_XOSC, 99u)
           & 0x30u) == TEMP_COMP_LR2021_TEMP_SOURCE_XOSC);
}

/* ------------------------------------------------------------------------- */
/* Layer (a): °C conversions                                                 */
/* ------------------------------------------------------------------------- */

static void test_deg_c_conversions(void)
{
    /* RadioLib verbatim: raw / 320.0f (LR2021_cmds_chip_control.cpp:177). */
    CHECK(near_f(temp_comp_deg_c_from_raw_radiolib(320u), 1.0f, 1e-6f));
    CHECK(near_f(temp_comp_deg_c_from_raw_radiolib(6400u), 20.0f, 1e-5f));
    CHECK(near_f(temp_comp_deg_c_from_raw_radiolib(0u), 0.0f, 1e-6f));

    /* Semtech documented UNIT layout: byte0 = integer part, byte1 = fraction. */
    const uint8_t plus25[2] = {25u, 0u};
    CHECK(near_f(temp_comp_deg_c_from_reply_semtech(plus25), 25.0f, 1e-6f));

    const uint8_t plus25_half[2] = {25u, 128u};
    CHECK(near_f(temp_comp_deg_c_from_reply_semtech(plus25_half), 25.5f, 1e-6f));

    /* sub-zero: this is the whole reason the signed path exists. */
    const uint8_t minus60[2] = {(uint8_t)(int8_t)(-60), 0u};
    CHECK(near_f(temp_comp_deg_c_from_reply_semtech(minus60), -60.0f, 1e-6f));

    const uint8_t minus60_half[2] = {(uint8_t)(int8_t)(-60), 128u};
    CHECK(near_f(temp_comp_deg_c_from_reply_semtech(minus60_half), -59.5f, 1e-6f));

    /* Signed raw with an explicit scale (scale pinned by the bench soak). */
    CHECK(near_f(temp_comp_deg_c_from_raw_signed((int16_t)-1920, 32.0f),
                 -60.0f, 1e-6f));
    CHECK(near_f(temp_comp_deg_c_from_raw_signed((int16_t)6400, 256.0f),
                 25.0f, 1e-6f));
    /* An invalid scale must not divide by zero. */
    CHECK(near_f(temp_comp_deg_c_from_raw_signed((int16_t)100, 0.0f), 0.0f, 1e-9f));
}

/* A fake transport: returns a canned reply and records the frame it was given
 * — this is how the module is exercised without hardware. */
typedef struct
{
    uint8_t reply[2];
    uint8_t seen_cmd[8];
    size_t  seen_cmd_len;
    size_t  seen_rpl_len;
    int     rc;
    int     calls;
} fake_spi_t;

static int fake_spi_read(void *ctx, const uint8_t *cmd, size_t cmd_len,
                         uint8_t *rpl, size_t rpl_len)
{
    fake_spi_t *f = (fake_spi_t *)ctx;
    ++f->calls;
    f->seen_cmd_len = cmd_len;
    f->seen_rpl_len = rpl_len;
    for (size_t i = 0; (i < cmd_len) && (i < sizeof(f->seen_cmd)); ++i)
    {
        f->seen_cmd[i] = cmd[i];
    }
    if (f->rc == TEMP_COMP_OK)
    {
        for (size_t i = 0; (i < rpl_len) && (i < 2u); ++i)
        {
            rpl[i] = f->reply[i];
        }
    }
    return f->rc;
}

static void test_read_via_transport(void)
{
    fake_spi_t fake;
    memset(&fake, 0, sizeof(fake));
    fake.reply[0] = (uint8_t)(int8_t)(-55);
    fake.reply[1] = 64u; /* +0.25 °C */
    fake.rc      = TEMP_COMP_OK;

    temp_comp_spi_t spi;
    spi.read = fake_spi_read;
    spi.ctx  = &fake;

    float t = 12345.0f;
    const int rc = temp_comp_lr2021_read_xosc_deg_c(&spi, &t);

    CHECK(rc == TEMP_COMP_OK);
    CHECK(near_f(t, -54.75f, 1e-5f));
    CHECK(fake.calls == 1);
    CHECK(fake.seen_cmd_len == TEMP_COMP_GET_TEMP_CMD_LEN);
    CHECK(fake.seen_rpl_len == TEMP_COMP_GET_TEMP_RPL_LEN);
    CHECK(fake.seen_cmd[0] == 0x01u);
    CHECK(fake.seen_cmd[1] == 0x25u);
    CHECK(fake.seen_cmd[2] == 0x1Du); /* XOSC, DEG_C, 13 bits */

    /* The VBE convenience wrapper must ask for the other source. */
    fake.calls = 0;
    const int rc2 = temp_comp_lr2021_read_vbe_deg_c(&spi, &t);
    CHECK(rc2 == TEMP_COMP_OK);
    CHECK(fake.seen_cmd[2] == 0x0Du);

    /* A transport failure must NOT be reported as a 0.0 °C reading — that is
     * exactly the RadioLib getTemperature() trap this module avoids. */
    fake.rc = TEMP_COMP_ERR_SPI;
    t = 777.0f;
    const int rc3 = temp_comp_lr2021_read_xosc_deg_c(&spi, &t);
    CHECK(rc3 == TEMP_COMP_ERR_SPI);
    CHECK(near_f(t, 777.0f, 1e-6f)); /* untouched on failure */

    /* Null-safety. */
    CHECK(temp_comp_lr2021_read_xosc_deg_c(NULL, &t) == TEMP_COMP_ERR_ARG);
    CHECK(temp_comp_lr2021_read_xosc_deg_c(&spi, NULL) == TEMP_COMP_ERR_ARG);
}

/* ------------------------------------------------------------------------- */
/* Layer (e): MS5611 cross-check                                             */
/* ------------------------------------------------------------------------- */

static void test_crosscheck(void)
{
    temp_comp_crosscheck_t x;

    CHECK(temp_comp_crosscheck(-55.0f, -55.2f, 0.8f, &x) == TEMP_COMP_OK);
    CHECK(x.fault == 0u);
    CHECK(near_f(x.delta_c, 0.2f, 1e-5f));

    /* Beyond the window => fault (detectable, not silent). */
    CHECK(temp_comp_crosscheck(-55.0f, -40.0f, 0.8f, &x) == TEMP_COMP_OK);
    CHECK(x.fault == 1u);

    /* Boundary is strict (> max). */
    CHECK(temp_comp_crosscheck(0.0f, 0.8f, 0.8f, &x) == TEMP_COMP_OK);
    CHECK(x.fault == 0u);

    /* A window below the sanity floor is clamped up to the floor. */
    CHECK(temp_comp_crosscheck(0.0f, 0.4f, 0.1f, &x) == TEMP_COMP_OK);
    CHECK(near_f(x.max_delta_c, TEMP_COMP_CROSSCHECK_MIN_DELTA_C, 1e-6f));
    CHECK(x.fault == 0u);
    CHECK(temp_comp_crosscheck(0.0f, 0.9f, 0.1f, &x) == TEMP_COMP_OK);
    CHECK(x.fault == 1u);

    /* NaN must never read as healthy. */
    CHECK(temp_comp_crosscheck(NAN, 0.0f, 5.0f, &x) == TEMP_COMP_OK);
    CHECK(x.fault == 1u);

    CHECK(temp_comp_crosscheck(0.0f, 0.0f, 1.0f, NULL) == TEMP_COMP_ERR_ARG);
}

/* ------------------------------------------------------------------------- */
/* Layer (b): the calibration curve                                          */
/* ------------------------------------------------------------------------- */

static void test_curve_identity_until_characterised(void)
{
    temp_comp_curve_t c;
    temp_comp_curve_init_empty(&c);

    CHECK(temp_comp_curve_is_identity(&c) == 1u);
    CHECK(c.n == 0u);
    /* Identity means EXACTLY zero — no invented coefficients. */
    CHECK(temp_comp_curve_correction_ppm(&c, -60.0f) == 0.0f);
    CHECK(temp_comp_curve_correction_ppm(&c, 0.0f) == 0.0f);
    CHECK(temp_comp_curve_correction_ppm(&c, 25.0f) == 0.0f);

    /* A NULL curve behaves the same way rather than crashing. */
    CHECK(temp_comp_curve_is_identity(NULL) == 1u);
    CHECK(temp_comp_curve_correction_ppm(NULL, 0.0f) == 0.0f);
}

static void test_curve_insertion_and_ordering(void)
{
    temp_comp_curve_t c;
    temp_comp_curve_init_empty(&c);

    CHECK(temp_comp_curve_add_point(&c, 25.0f, 5.0f) == TEMP_COMP_OK);
    CHECK(temp_comp_curve_add_point(&c, -40.0f, -10.0f) == TEMP_COMP_OK);
    CHECK(temp_comp_curve_add_point(&c, 0.0f, 0.0f) == TEMP_COMP_OK);
    CHECK(c.n == 3u);
    CHECK(c.pts[0].temp_c == -40.0f);
    CHECK(c.pts[1].temp_c == 0.0f);
    CHECK(c.pts[2].temp_c == 25.0f);

    /* Duplicate temperature => rejected (interpolation stays unambiguous). */
    CHECK(temp_comp_curve_add_point(&c, 0.0f, 1.0f)
          == TEMP_COMP_ERR_CURVE_DUP_TEMP);
    CHECK(c.n == 3u);

    /* NaN inputs are refused. */
    CHECK(temp_comp_curve_add_point(&c, NAN, 1.0f) == TEMP_COMP_ERR_ARG);
    CHECK(temp_comp_curve_add_point(&c, 1.0f, NAN) == TEMP_COMP_ERR_ARG);

    /* Fill to capacity, then one more must report FULL. */
    {
        temp_comp_curve_t f;
        temp_comp_curve_init_empty(&f);
        int ok = 1;
        for (int k = 0; k < (int)TEMP_COMP_CURVE_MAX_POINTS; ++k)
        {
            ok = ok && (temp_comp_curve_add_point(&f, (float)k, (float)k)
                        == TEMP_COMP_OK);
        }
        CHECK(ok);
        CHECK(f.n == TEMP_COMP_CURVE_MAX_POINTS);
        CHECK(temp_comp_curve_add_point(&f, 100.0f, 0.0f)
              == TEMP_COMP_ERR_CURVE_FULL);
    }
}

static void test_curve_interpolation_and_clamping(void)
{
    temp_comp_curve_point_t pts[3];
    pts[0].temp_c = -40.0f; pts[0].ppm = -10.0f;
    pts[1].temp_c =   0.0f; pts[1].ppm =   0.0f;
    pts[2].temp_c =  25.0f; pts[2].ppm =   5.0f;

    temp_comp_curve_t c;
    CHECK(temp_comp_curve_load(&c, pts, 3u) == TEMP_COMP_OK);
    CHECK(c.n == 3u);

    /* Node values exact. */
    CHECK(near_f(temp_comp_curve_correction_ppm(&c, -40.0f), -10.0f, 1e-6f));
    CHECK(near_f(temp_comp_curve_correction_ppm(&c, 0.0f), 0.0f, 1e-6f));
    CHECK(near_f(temp_comp_curve_correction_ppm(&c, 25.0f), 5.0f, 1e-6f));

    /* Midpoint of [-40, 0] -> -5.0 ppm. */
    CHECK(near_f(temp_comp_curve_correction_ppm(&c, -20.0f), -5.0f, 1e-5f));
    /* Midpoint of [0, 25] -> 2.5 ppm. */
    CHECK(near_f(temp_comp_curve_correction_ppm(&c, 12.5f), 2.5f, 1e-5f));

    /* Clamped outside the characterised span, in both directions. */
    CHECK(near_f(temp_comp_curve_correction_ppm(&c, -60.0f), -10.0f, 1e-6f));
    CHECK(near_f(temp_comp_curve_correction_ppm(&c, 85.0f), 5.0f, 1e-6f));

    /* Unsorted input must be refused, not silently accepted. */
    temp_comp_curve_point_t bad[2];
    bad[0].temp_c = 10.0f; bad[0].ppm = 1.0f;
    bad[1].temp_c =  5.0f; bad[1].ppm = 2.0f;
    CHECK(temp_comp_curve_load(&c, bad, 2u) == TEMP_COMP_ERR_CURVE_NOT_SORTED);

    /* Too many points for the fixed storage. */
    CHECK(temp_comp_curve_load(&c, pts, (uint8_t)(TEMP_COMP_CURVE_MAX_POINTS + 1u))
          == TEMP_COMP_ERR_ARG);

    /* Empty load is legal and yields identity. */
    CHECK(temp_comp_curve_load(&c, NULL, 0u) == TEMP_COMP_OK);
    CHECK(temp_comp_curve_is_identity(&c) == 1u);
}

static void test_correction_for_temp_hz(void)
{
    temp_comp_curve_point_t pts[2];
    pts[0].temp_c = -40.0f; pts[0].ppm = -10.0f;
    pts[1].temp_c =  25.0f; pts[1].ppm =   5.0f;

    temp_comp_curve_t c;
    CHECK(temp_comp_curve_load(&c, pts, 2u) == TEMP_COMP_OK);

    /* At -40 °C: -10 ppm at the 2.4 GHz carrier => -24 000 Hz exactly. */
    float ppm = 0.0f, hz = 0.0f;
    CHECK(temp_comp_correction_for_temp(&c, -40.0f, 2400000000u, &ppm, &hz)
          == TEMP_COMP_OK);
    CHECK(near_f(ppm, -10.0f, 1e-5f));
    CHECK(near_f(hz, -24000.0f, 1.0f));

    /* Interpolated point 0 °C: w = 40/65, ppm = -10 + 15*40/65. */
    const float expect_ppm = -10.0f + 15.0f * (40.0f / 65.0f);
    CHECK(temp_comp_correction_for_temp(&c, 0.0f, 2400000000u, &ppm, &hz)
          == TEMP_COMP_OK);
    CHECK(near_f(ppm, expect_ppm, 1e-4f));
    CHECK(near_f(hz, 2400000000.0f * expect_ppm * 1e-6f, 5.0f));

    /* Identity curve -> exactly zero, no error. */
    temp_comp_curve_t id;
    temp_comp_curve_init_empty(&id);
    CHECK(temp_comp_correction_for_temp(&id, -55.0f, 2400000000u, &ppm, &hz)
          == TEMP_COMP_OK);
    CHECK(ppm == 0.0f);
    CHECK(hz == 0.0f);

    CHECK(temp_comp_correction_for_temp(&c, 0.0f, 1u, NULL, &hz)
          == TEMP_COMP_ERR_ARG);
}

/* ------------------------------------------------------------------------- */
/* Layer (c): command frames + the unverified mapping stub                   */
/* ------------------------------------------------------------------------- */

static void test_frame_builders(void)
{
    uint8_t f5[5];
    temp_comp_build_xosc_cp_trim_frame(0x1Au, 0x2Bu, 0x10u, f5);
    CHECK(f5[0] == 0x01u && f5[1] == 0x31u);
    CHECK(f5[2] == 0x1Au && f5[3] == 0x2Bu && f5[4] == 0x10u);

    /* 6-bit fields are masked, exactly as RadioLib does (0x3F). */
    temp_comp_build_xosc_cp_trim_frame(0xFFu, 0x40u, 0x00u, f5);
    CHECK(f5[2] == 0x3Fu && f5[3] == 0x00u);

    uint8_t f3[3];
    temp_comp_build_temp_comp_cfg_frame(2u, 1u, f3);
    CHECK(f3[0] == 0x01u && f3[1] == 0x32u);
    CHECK(f3[2] == 0x06u); /* (1 << 2) | 2 */

    temp_comp_build_temp_comp_cfg_frame(0u, 0u, f3);
    CHECK(f3[2] == 0x00u);

    uint8_t f7[7];
    CHECK(temp_comp_build_ntc_params_frame(0x0123u, 0x0456u, 0x05u, f7)
          == TEMP_COMP_OK);
    const uint8_t expect7[7] = {0x01u, 0x33u, 0x01u, 0x23u, 0x04u, 0x56u, 0x05u};
    CHECK(memcmp(f7, expect7, sizeof(expect7)) == 0);
    CHECK(temp_comp_build_ntc_params_frame(0u, 0u, 0u, NULL) == TEMP_COMP_ERR_ARG);

    /* Null out-pointers must be tolerated, not dereferenced. */
    temp_comp_build_xosc_cp_trim_frame(1u, 2u, 3u, NULL);
    temp_comp_build_temp_comp_cfg_frame(1u, 1u, NULL);
}

static void test_unverified_mapping_stub(void)
{
    uint8_t xta = 0xAAu, xtb = 0xBBu;
    /* The ppm->trim-code mapping does NOT exist in any vendored source.  The
     * stub must refuse and must not fabricate codes. */
    CHECK(temp_comp_ppm_to_xosc_cp_trim(3.5f, &xta, &xtb)
          == TEMP_COMP_ERR_UNVERIFIED_MAPPING);
    CHECK(xta == 0xAAu);
    CHECK(xtb == 0xBBu);
}

static void test_apply_correction_hook(void)
{
    uint8_t frame[TEMP_COMP_XOSC_TRIM_FRAME_LEN];
    float ppm = 0.0f, hz = 0.0f;

    /* (1) Identity curve: nothing to apply, and that is NOT an error. */
    temp_comp_curve_t id;
    temp_comp_curve_init_empty(&id);
    memset(frame, 0xEE, sizeof(frame));
    CHECK(temp_comp_apply_correction(&id, -50.0f, 2400000000u, 0u, 0u, 0u,
                                     frame, &ppm, &hz) == TEMP_COMP_OK);
    CHECK(ppm == 0.0f && hz == 0.0f);
    for (size_t i = 0; i < sizeof(frame); ++i)
    {
        CHECK(frame[i] == 0x00u);
    }

    /* (2) Characterised curve but no trim codes yet: report the correction and
     *     the UNVERIFIED status so the caller logs and does not fly on it. */
    temp_comp_curve_point_t pts[2];
    pts[0].temp_c = -60.0f; pts[0].ppm = -12.0f;
    pts[1].temp_c =  25.0f; pts[1].ppm =   4.0f;
    temp_comp_curve_t c;
    CHECK(temp_comp_curve_load(&c, pts, 2u) == TEMP_COMP_OK);

    memset(frame, 0, sizeof(frame));
    CHECK(temp_comp_apply_correction(&c, -60.0f, 2400000000u, 0u, 0u, 0u,
                                     frame, &ppm, &hz)
          == TEMP_COMP_ERR_UNVERIFIED_MAPPING);
    CHECK(near_f(ppm, -12.0f, 1e-5f));
    CHECK(near_f(hz, -28800.0f, 1.0f));
    for (size_t i = 0; i < sizeof(frame); ++i)
    {
        CHECK(frame[i] == 0x00u); /* no frame emitted without trim codes */
    }

    /* (3) Bench-supplied trim codes: the VERIFIED 0x0131 frame is emitted, and
     *     the function still honestly reports that the mapping is unverified. */
    CHECK(temp_comp_apply_correction(&c, -60.0f, 2400000000u, 0x05u, 0x07u, 0x0Au,
                                     frame, &ppm, &hz)
          == TEMP_COMP_ERR_UNVERIFIED_MAPPING);
    CHECK(frame[0] == 0x01u && frame[1] == 0x31u);
    CHECK(frame[2] == 0x05u && frame[3] == 0x07u && frame[4] == 0x0Au);

    CHECK(temp_comp_apply_correction(&id, 0.0f, 1u, 0u, 0u, 0u, NULL, &ppm, &hz)
          == TEMP_COMP_ERR_ARG);
}

/* ------------------------------------------------------------------------- */
/* Layer (d): 1PPS-gated discipline                                          */
/* ------------------------------------------------------------------------- */

static void test_pps_resolution_arithmetic(void)
{
    /* 1 / (f_ref * M), from docs/analysis/thermal-and-frequency-drift.md §3.2 */
    CHECK(near_d(temp_comp_pps_resolution_ppm(TEMP_COMP_REF_HZ_LR2021, 1u),
                 0.03125, 1e-12));
    CHECK(near_d(temp_comp_pps_resolution_ppm(TEMP_COMP_REF_HZ_LR2021, 10u),
                 0.003125, 1e-12));
    CHECK(near_d(temp_comp_pps_resolution_ppm(TEMP_COMP_REF_HZ_LR2021, 100u),
                 0.0003125, 1e-12));
    CHECK(near_d(temp_comp_pps_resolution_ppm(TEMP_COMP_REF_HZ_SX1280, 1u),
                 0.0192307692307692, 1e-12));

    /* Integer ppb form, truncated. */
    CHECK(temp_comp_pps_resolution_ppb(TEMP_COMP_REF_HZ_LR2021, 1u) == 31u);
    CHECK(temp_comp_pps_resolution_ppb(TEMP_COMP_REF_HZ_LR2021, 10u) == 3u);
    CHECK(temp_comp_pps_resolution_ppb(TEMP_COMP_REF_HZ_SX1280, 1u) == 19u);

    /* Degenerate arguments return 0 rather than dividing by zero. */
    CHECK(temp_comp_pps_resolution_ppm(0u, 1u) == 0.0);
    CHECK(temp_comp_pps_resolution_ppm(1u, 0u) == 0.0);
    CHECK(temp_comp_pps_resolution_ppb(0u, 0u) == 0u);
}

static void test_pps_frac_error(void)
{
    /* Exactly the ideal count => 0 ppm. */
    CHECK(near_d(temp_comp_pps_frac_error_ppm(32000000ULL,
                                              TEMP_COMP_REF_HZ_LR2021, 1u),
                 0.0, 1e-9));
    /* +32 counts over 32e6 => +1 ppm exactly. */
    CHECK(near_d(temp_comp_pps_frac_error_ppm(32000032ULL,
                                              TEMP_COMP_REF_HZ_LR2021, 1u),
                 1.0, 1e-9));
    /* -32 counts => -1 ppm. */
    CHECK(near_d(temp_comp_pps_frac_error_ppm(31999968ULL,
                                              TEMP_COMP_REF_HZ_LR2021, 1u),
                 -1.0, 1e-9));
    /* Over a 10 s window, +320 counts => +1 ppm. */
    CHECK(near_d(temp_comp_pps_frac_error_ppm(320000320ULL,
                                              TEMP_COMP_REF_HZ_LR2021, 10u),
                 1.0, 1e-9));
    CHECK(temp_comp_pps_frac_error_ppm(0ULL, 0u, 1u) == 0.0);
}

static void test_pps_gate_state_machine(void)
{
    temp_comp_pps_gate_t g;
    memset(&g, 0, sizeof(g));

    /* Operating an un-armed gate is an error, not a silent zero. */
    CHECK(temp_comp_pps_gate_on_pps(&g, 0u) == TEMP_COMP_ERR_NOT_ARMED);
    CHECK(temp_comp_pps_gate_reset(&g) == TEMP_COMP_ERR_NOT_ARMED);

    CHECK(temp_comp_pps_gate_begin(&g, TEMP_COMP_REF_HZ_LR2021, 3u)
          == TEMP_COMP_OK);
    CHECK(g.armed == 1u && g.ready == 0u);

    /* Three PPS intervals need four edges.  Window 1: perfect. */
    CHECK(temp_comp_pps_gate_on_pps(&g, 0u) == TEMP_COMP_OK);
    CHECK(g.ready == 0u);
    CHECK(temp_comp_pps_gate_on_pps(&g, 32000000ULL) == TEMP_COMP_OK);
    CHECK(g.ready == 0u);
    CHECK(temp_comp_pps_gate_on_pps(&g, 64000000ULL) == TEMP_COMP_OK);
    CHECK(g.ready == 0u);
    CHECK(temp_comp_pps_gate_on_pps(&g, 96000000ULL) == TEMP_COMP_OK);
    CHECK(g.ready == 1u);
    CHECK(near_d(g.last_ppm, 0.0, 1e-9));
    /* rolled: next window already has one edge anchored at 96e6 */
    CHECK(g.pps_edges == 1u && g.first_count == 96000000ULL);

    /* Window 2: +1 ppm (a 96-count surplus over 96e6 counts). */
    g.ready = 0u;
    CHECK(temp_comp_pps_gate_on_pps(&g, 96000000ULL + 32000032ULL)
          == TEMP_COMP_OK);
    CHECK(g.ready == 0u);
    CHECK(temp_comp_pps_gate_on_pps(&g, 96000000ULL + 64000064ULL)
          == TEMP_COMP_OK);
    CHECK(temp_comp_pps_gate_on_pps(&g, 96000000ULL + 96000096ULL)
          == TEMP_COMP_OK);
    CHECK(g.ready == 1u);
    CHECK(near_d(g.last_ppm, 1.0, 1e-9));

    /* Argument validation. */
    CHECK(temp_comp_pps_gate_begin(&g, 0u, 1u) == TEMP_COMP_ERR_ARG);
    CHECK(temp_comp_pps_gate_begin(&g, TEMP_COMP_REF_HZ_LR2021, 0u)
          == TEMP_COMP_ERR_ARG);
    CHECK(temp_comp_pps_gate_begin(&g, TEMP_COMP_REF_HZ_LR2021,
                                   TEMP_COMP_PPS_MAX_WINDOW_S + 1u)
          == TEMP_COMP_ERR_ARG);
    CHECK(temp_comp_pps_gate_begin(NULL, 1u, 1u) == TEMP_COMP_ERR_ARG);

    /* reset() clears a live gate. */
    CHECK(temp_comp_pps_gate_begin(&g, TEMP_COMP_REF_HZ_LR2021, 2u)
          == TEMP_COMP_OK);
    CHECK(temp_comp_pps_gate_on_pps(&g, 5u) == TEMP_COMP_OK);
    CHECK(temp_comp_pps_gate_reset(&g) == TEMP_COMP_OK);
    CHECK(g.pps_edges == 0u && g.ready == 0u);
}

/* ------------------------------------------------------------------------- */

int main(void)
{
    test_get_temp_arg_packing();
    test_deg_c_conversions();
    test_read_via_transport();
    test_crosscheck();
    test_curve_identity_until_characterised();
    test_curve_insertion_and_ordering();
    test_curve_interpolation_and_clamping();
    test_correction_for_temp_hz();
    test_frame_builders();
    test_unverified_mapping_stub();
    test_apply_correction_hook();
    test_pps_resolution_arithmetic();
    test_pps_frac_error();
    test_pps_gate_state_machine();

    if (failures == 0)
    {
        printf("test_temp_comp: all checks passed\n");
        return 0;
    }
    printf("test_temp_comp: %d check(s) FAILED\n", failures);
    return 1;
}
