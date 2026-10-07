/**
 * @file    temp_comp.h
 * @brief   On-board temperature-sensor-based drift compensation for the LR2021
 *          (ADR-057).  Pure C API — no Arduino, no SPI hardware dependency, so
 *          the whole module is unit-testable on the host
 *          (`make -C firmware/rp2040/host-tests && ./host-tests/test_temp_comp`).
 *
 * THE IDEA
 * --------
 * The LR2021's 32 MHz reference is a crystal on the crystal-configured (bare
 * NiceRF LoRa2021) variant and drifts with temperature. The chip carries an
 * ON-CHIP temperature sensor, and crucially one of its two sources sits
 * ADJACENT TO THE CRYSTAL — so it measures the temperature of the thing that
 * actually drifts, not a board-level proxy.
 *
 * Layers (ADR-057 D2):
 *   (a) read TEMP_SOURCE_XOSC over SPI                      -> read functions
 *   (b) per-unit calibration curve (bench-characterised)    -> temp_comp_curve_t
 *   (c) apply the correction (static trim and/or on-chip
 *       NTC loop)                                           -> frame builders
 *   (d) GPS 1PPS-gated discipline                           -> pps_gate
 *   (e) MS5611 cross-check so a sensor FAULT is detectable  -> cross-check API
 *
 * EVERYTHING VERIFIED — PROVENANCE (do not "improve" these from memory)
 * ---------------------------------------------------------------------
 * Vendored RadioLib, `tracker/firmware/components/RadioLib/src/modules/LR2021/`
 *   LR2021_commands.h:32    RADIOLIB_LR2021_CMD_GET_TEMP          = 0x0125
 *   LR2021_commands.h:249   RADIOLIB_LR2021_TEMP_SOURCE_VBE       = 0x00 << 4
 *   LR2021_commands.h:250   RADIOLIB_LR2021_TEMP_SOURCE_XOSC      = 0x01 << 4
 *   LR2021_commands.h:252   RADIOLIB_LR2021_TEMP_FORMAT_DEG_C     = 0x01 << 3
 *   LR2021_commands.h:246   RADIOLIB_LR2021_MEAS_RESOLUTION_OFFSET= 8
 *   LR2021_commands.h:55    RADIOLIB_LR2021_CMD_SET_XOSC_CP_TRIM  = 0x0131
 *   LR2021_cmds_chip_control.cpp:171-180  getTemp() packs the argument byte
 *                                         (source & 0x30) | DEG_C | ((8+bits)&7)
 *                                         and scales the 2-byte reply raw/320.0f
 *   LR2021.h:595            float getTemperature(uint8_t source, uint8_t bits = 13)
 *   LR2021.cpp:987-998      getTemperature() -> 0.0f on ANY error (see note below)
 *   LR2021_cmds_chip_control.cpp:306  setXoscCpTrim(xta, xtb, startTime)
 *                                         frame = { 0x01, 0x31, xta&0x3F, xtb&0x3F, startTime }
 *
 * Vendored Semtech driver, `firmware/e80-stm32-bench/third_party/Radio/`
 * `lr20xx_driver/`  (an INDEPENDENT implementation — used here to cross-check)
 *   src/lr20xx_system.c:142 LR20XX_SYSTEM_GET_TEMP_OC        = 0x0125
 *   src/lr20xx_system.c:149 LR20XX_SYSTEM_CONFIGURE_XOSC_OC  = 0x0131
 *   src/lr20xx_system.c:150 LR20XX_SYSTEM_SET_TEMP_COMP_CFG_OC = 0x0132
 *   src/lr20xx_system.c:151 LR20XX_SYSTEM_SET_NTC_PARAMS_OC  = 0x0133
 *   src/lr20xx_system.c:105 LR20XX_SYSTEM_MEASURE_LENGTH     = 2
 *   src/lr20xx_system.c:71  GET_TEMP_CMD_LENGTH              = 3  ({0x01,0x25,arg})
 *   src/lr20xx_system.c:458-475  get_temp(): arg byte (src<<4)+(format<<3)+res,
 *                                read 2 bytes; reply re-assembled (b0<<8|b1) >> 3
 *   src/lr20xx_system.c:566-577  configure_xosc(xta, xtb, wait_time_us)
 *                                frame = { 0x01, 0x31, xta, xtb, wait }
 *   src/lr20xx_system.c:579-589  set_temp_comp_cfg(mode, is_ntc_en)
 *                                frame = { 0x01, 0x32, ((ntc_en?1:0)<<2) + mode }
 *   src/lr20xx_system.c:591-604  set_ntc_params(r_ratio, beta, delay)
 *                                frame = { 0x01, 0x33, r>>8, r, b>>8, b, delay }
 *   inc/lr20xx_system.h:391-411  get_temp() doc: UNIT format is "[°C] in 13.5sb
 *                                format, the first byte returned contains the
 *                                integer part, the second the fractional part"
 *
 * *** THE TWO DRIVERS DISAGREE ON THE DEGREE-CELSIUS SCALE. ***
 * RadioLib divides the UNsigned 16-bit reply by 320.0; the Semtech header
 * documents a byte0=integer / byte1=fractional layout whose own reassembly is
 * (b0<<8|b1)>>3, i.e. an LSB of 1/32 °C. These cannot both be right, and
 * RadioLib's unsigned read cannot even represent the sub-zero temperatures this
 * mission lives in. This module therefore exposes the scale as a parameter
 * (TEMP_COMP_DEG_C_SCALE_*) and records the reconciliation as an OPEN ITEM:
 * the bench cold-soak (known absolute temperature) pins it before any curve is
 * trusted. Nothing here silently picks a winner.
 *
 * NOT VERIFIED — do not treat as fact (all marked TODO(unverified) in place):
 *   - the numeric mapping correction_ppm -> SetXoscCpTrim ft/xta/xtb codes;
 *   - whether the chip hard-errors on SetTempCompCfg when a TCXO was configured;
 *   - the NTC pin break-out on the owned bare NiceRF LoRa2021 module;
 *   - the hardware path that counts the 32 MHz reference between 1PPS edges.
 */

#ifndef TEMP_COMP_H
#define TEMP_COMP_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ======================================================================== */
/*  1. Verified LR2021 command/field constants                              */
/* ======================================================================== */

#define TEMP_COMP_LR2021_CMD_GET_TEMP          0x0125u  /* commands.h:32      */
#define TEMP_COMP_LR2021_CMD_SET_XOSC_CP_TRIM  0x0131u  /* commands.h:55      */
#define TEMP_COMP_LR2021_CMD_SET_TEMP_COMP_CFG 0x0132u  /* Semtech system.c:150
                                                         * ABSENT from the
                                                         * vendored RadioLib  */
#define TEMP_COMP_LR2021_CMD_SET_NTC_PARAMS    0x0133u  /* Semtech system.c:151
                                                         * ABSENT from the
                                                         * vendored RadioLib  */

/* GetTemp argument byte fields (RadioLib commands.h:246-252).  These are the
 * ALREADY-SHIFTED wire values, exactly as the vendored header defines them —
 * the argument byte is (source & 0x30) | (DEG_C << 3) | ((8+bits) & 7). */
#define TEMP_COMP_LR2021_TEMP_SOURCE_VBE       (0x00u << 4) /* 0x00 general die */
#define TEMP_COMP_LR2021_TEMP_SOURCE_XOSC      (0x01u << 4) /* 0x10 XTAL-adjacent*/
#define TEMP_COMP_LR2021_TEMP_FORMAT_RAW       0x00u
#define TEMP_COMP_LR2021_TEMP_FORMAT_DEG_C     0x01u
#define TEMP_COMP_LR2021_MEAS_RESOLUTION_OFFSET 8u

/* RadioLib getTemperature() default resolution (LR2021.h:595). */
#define TEMP_COMP_LR2021_TEMP_DEFAULT_BITS     13u

/* Command frame lengths, from the vendored Semtech driver. */
#define TEMP_COMP_GET_TEMP_CMD_LEN   3u   /* {0x01, 0x25, arg} (system.c:71)  */
#define TEMP_COMP_GET_TEMP_RPL_LEN   2u   /* MEASURE_LENGTH (system.c:105)    */
#define TEMP_COMP_XOSC_TRIM_FRAME_LEN 5u  /* system.c:77 = 2 + 3              */
#define TEMP_COMP_TEMP_COMP_CFG_FRAME_LEN 3u
#define TEMP_COMP_NTC_PARAMS_FRAME_LEN 7u

/* Byte scales for the °C reply.  See the DISAGREEMENT note above. */
#define TEMP_COMP_DEG_C_SCALE_RADIOLIB 320.0f /* LR2021_cmds_chip_control.cpp:177 */
#define TEMP_COMP_DEG_C_SCALE_SEMTECH  256.0f /* system.c:465 reassembly >>3
                                               * (b0=integer part, b1=fraction)
                                               * => 1/256 °C LSB in the 16-bit
                                               * pair; TODO(unverified)        */

/* Foot-capacitance trim codes are 6-bit fields in the 0x0131 frame
 * (RadioLib masks xta/xtb with 0x3F — LR2021_cmds_chip_control.cpp:307). */
#define TEMP_COMP_XOSC_TRIM_CODE_MAX   0x3Fu

/* ======================================================================== */
/*  2. Return codes                                                         */
/* ======================================================================== */

#define TEMP_COMP_OK                        0
#define TEMP_COMP_ERR_ARG                 (-1)  /* bad pointer/range          */
#define TEMP_COMP_ERR_CURVE_FULL          (-2)  /* calibration curve storage  */
#define TEMP_COMP_ERR_CURVE_DUP_TEMP      (-3)  /* duplicate temperature node */
#define TEMP_COMP_ERR_CURVE_NOT_SORTED    (-4)
#define TEMP_COMP_ERR_SPI                 (-5)  /* transport/SPIcommand failed*/
#define TEMP_COMP_ERR_UNVERIFIED_MAPPING  (-6)  /* TODO(unverified) stub      */
#define TEMP_COMP_ERR_NOT_ARMED           (-7)

/* ======================================================================== */
/*  3. SPI transport abstraction                                            */
/* ======================================================================== */

/**
 * Read a command frame from the radio and return the reply.
 *
 * `cmd` is the full outgoing frame, opcode first: e.g. GetTemp is
 * {0x01, 0x25, arg} (TEMP_COMP_GET_TEMP_CMD_LEN = 3) and the reply is 2 bytes
 * (TEMP_COMP_GET_TEMP_RPL_LEN).  This mirrors BOTH vendored drivers' HAL:
 * RadioLib `SPIcommand(..., reqBuff, ..., rplBuff, ...)` and Semtech
 * `lr20xx_hal_read(context, cbuffer, clen, rbuffer, rlen)`.
 *
 * Must return TEMP_COMP_OK on success and a negative TEMP_COMP_ERR_* otherwise.
 */
typedef int (*temp_comp_spi_read_fn)(void *ctx,
                                     const uint8_t *cmd, size_t cmd_len,
                                     uint8_t *rpl, size_t rpl_len);

typedef struct
{
    temp_comp_spi_read_fn read;
    void                 *ctx;
} temp_comp_spi_t;

/* ======================================================================== */
/*  4. Layer (a) — read the on-chip sensor                                  */
/* ======================================================================== */

/**
 * Build the GetTemp argument byte exactly as the vendored drivers do:
 *   (source & 0x30) | (FORMAT_DEG_C << 3) | ((MEAS_RESOLUTION_OFFSET + bits) & 0x07)
 * `source` is TEMP_COMP_LR2021_TEMP_SOURCE_XOSC or _VBE.
 * (RadioLib LR2021_cmds_chip_control.cpp:172; Semtech system.c:463.)
 */
uint8_t temp_comp_lr2021_get_temp_arg(uint8_t source, uint8_t bits);

/**
 * RadioLib's °C conversion, verbatim: reply reassembled UNsigned then / 320.0f.
 * Kept for wire-compatibility with the vendored RadioLib wrapper, but note it
 * cannot represent negative temperatures — see the disagreement note above.
 */
float temp_comp_deg_c_from_raw_radiolib(uint16_t raw);

/**
 * Semtech-documented UNIT layout: byte0 = integer part, byte1 = fractional
 * part.  Sign is carried by byte0 (read as int8_t); the fraction is added
 * unsigned.  This is the form the reader uses because it *can* go sub-zero.
 * TODO(unverified): the fractional-byte convention (unsigned fraction with the
 * sign on the integer byte) is inferred from the header prose, not from a
 * worked datasheet example; pinned by the bench cold-soak.
 */
float temp_comp_deg_c_from_reply_semtech(const uint8_t reply[2]);

/**
 * Signed 16-bit raw scaled by an explicit factor.  `scale` is one of
 * TEMP_COMP_DEG_C_SCALE_*; the bench decides which.
 */
float temp_comp_deg_c_from_raw_signed(int16_t raw, float scale);

/**
 * Read the LR2021 temperature from `source` and return it in degrees Celsius.
 *
 * Returns TEMP_COMP_OK and writes *out_deg_c on success.  On failure it returns
 * a negative TEMP_COMP_ERR_* and does NOT write *out_deg_c — deliberately,
 * because RadioLib's getTemperature() returns 0.0f on error and 0.0 °C is a
 * perfectly valid reading, so a caller cannot tell success from failure.
 */
int temp_comp_lr2021_read_deg_c(const temp_comp_spi_t *spi, uint8_t source,
                                uint8_t bits, float *out_deg_c);

/* Convenience: the two sources this design uses. */
int temp_comp_lr2021_read_xosc_deg_c(const temp_comp_spi_t *spi, float *out_deg_c);
int temp_comp_lr2021_read_vbe_deg_c(const temp_comp_spi_t *spi, float *out_deg_c);

/* ======================================================================== */
/*  5. Layer (e) — MS5611 cross-check (fault detection, not control)         */
/* ======================================================================== */

/**
 * MS5611-01BA03 is a calibrated pressure AND temperature sensor, so it is an
 * INDEPENDENT thermometer next to the radio.  Its job here is to turn a silent
 * temperature-sensor FAULT into a detectable one: if the LR2021 XOSC reading
 * and the MS5611 reading diverge beyond `max_delta_c` (plus the LR2021's own
 * self-heating offset), the drift compensation must be declared untrustworthy
 * and telemetry flagged — never compensated with a bad temperature.
 *
 * TODO(unverified): the MS5611 temperature accuracy figure (±0.8 °C at 25 °C is
 * the commonly quoted MS5611-01BA03 datasheet value) is NOT verifiable from
 * this repo — the TE datasheet is not in-tree. `max_delta_c` is therefore a
 * caller-supplied constant, and the ADR records the figure as unverified.
 */
#define TEMP_COMP_CROSSCHECK_MIN_DELTA_C  0.5f  /* floor for the sanity window */

typedef struct
{
    float delta_c;      /* lr2021_xosc_deg_c - ms5611_deg_c                 */
    float max_delta_c;  /* |delta| > this => fault                          */
    uint8_t fault;      /* 1 = sensors disagree beyond max_delta_c          */
} temp_comp_crosscheck_t;

int temp_comp_crosscheck(float lr2021_xosc_deg_c, float ms5611_deg_c,
                         float max_delta_c, temp_comp_crosscheck_t *out);

/* ======================================================================== */
/*  6. Layer (b) — the per-unit calibration curve                           */
/* ======================================================================== */

#define TEMP_COMP_CURVE_MAX_POINTS 16u

/**
 * One characterised bench point: at `temp_c` the reference is off by `ppm`
 * (sign convention: correction to ADD to the nominal carrier, i.e.
 * f_set = f_nominal - ppm*1e-6*f_nominal... see temp_comp_correction_for_temp).
 */
typedef struct
{
    float temp_c;
    float ppm;
} temp_comp_curve_point_t;

/**
 * The per-unit curve.  EMPTY (n == 0) means IDENTITY: compensation is exactly
 * 0.0 ppm.  The module never invents coefficients — the array stays empty until
 * the bench characterisation (ADR-057 D5, -60..+25 °C) fills it, and the bench
 * result is stored in NON-VOLATILE storage (ADR-057 D4).
 */
typedef struct
{
    temp_comp_curve_point_t pts[TEMP_COMP_CURVE_MAX_POINTS];
    uint8_t                 n;
} temp_comp_curve_t;

void  temp_comp_curve_init_empty(temp_comp_curve_t *curve);

/** Insert a point keeping the array ascending by temp_c.  Duplicate
 *  temperatures are rejected (TEMP_COMP_ERR_CURVE_DUP_TEMP) so the
 *  interpolation is never ambiguous. */
int   temp_comp_curve_add_point(temp_comp_curve_t *curve, float temp_c, float ppm);

/** Load a whole curve (e.g. from NVM). Must be ascending; validated. */
int   temp_comp_curve_load(temp_comp_curve_t *curve,
                           const temp_comp_curve_point_t *pts, uint8_t n);

/** 1 if the curve carries no characterised points (identity). */
uint8_t temp_comp_curve_is_identity(const temp_comp_curve_t *curve);

/**
 * Piecewise-linear correction in ppm at `temp_c`.
 *   - empty curve              -> 0.0 ppm (identity, no invented data)
 *   - below the first point    -> the first point's value (clamped)
 *   - above the last point     -> the last point's value (clamped)
 *   - between two points       -> linear interpolation
 * Never returns NaN for a valid curve.
 */
float temp_comp_curve_correction_ppm(const temp_comp_curve_t *curve, float temp_c);

/**
 * The full layer-(b)+(c) result: correction in ppm and the equivalent
 * frequency offset in Hz at `nominal_hz`.  delta_hz = nominal_hz * ppm * 1e-6.
 */
int temp_comp_correction_for_temp(const temp_comp_curve_t *curve, float temp_c,
                                  uint32_t nominal_hz,
                                  float *corr_ppm_out, float *corr_hz_out);

/* ======================================================================== */
/*  7. Layer (c) — apply the correction                                     */
/* ======================================================================== */

/**
 * Mechanism (c1) — static foot-capacitance trim, SetXoscCpTrim 0x0131.
 * Frame = {0x01, 0x31, xta & 0x3F, xtb & 0x3F, wait_time_us}.  VERIFIED shape:
 * RadioLib LR2021_cmds_chip_control.cpp:306-309 masks with 0x3F; the Semtech
 * driver (system.c:566-577) sends the same 5 bytes with the third payload byte
 * named wait_time_us.  Note the naming delta (RadioLib calls it startTime) —
 * recorded, not resolved.
 */
void temp_comp_build_xosc_cp_trim_frame(uint8_t xta, uint8_t xtb,
                                        uint8_t wait_time_us, uint8_t out[5]);

/**
 * Mechanism (c2) — on-chip temperature-compensation block,
 * SetTempCompCfg 0x0132 + SetNtcParams 0x0133.
 * Frame = {0x01, 0x32, ((ntc_en?1:0) << 2) + mode}.  Verified against the
 * vendored Semtech driver (system.c:579-589).  `mode`: 0=disabled, 1=relative,
 * 2=absolute (per the datasheet field list quoted in ADR-042 Addendum A2).
 *
 * APPLIES TO CRYSTAL-CONFIGURED MODULES ONLY.  The datasheet scopes the block
 * to "if an XTAL 32MHz is used" (ADR-042 Addendum A2, §6.12.1), so the F33 —
 * whose 0.5 ppm TCXO is non-overridable — is out of scope and does not need it.
 * TODO(unverified): whether the chip returns a HARD ERROR when a TCXO was
 * configured; the vendored drivers perform no such check.
 */
void temp_comp_build_temp_comp_cfg_frame(uint8_t mode, uint8_t ntc_en,
                                         uint8_t out[3]);
int  temp_comp_build_ntc_params_frame(uint16_t ntc_r_ratio, uint16_t ntc_beta,
                                      uint8_t delay, uint8_t out[7]);

/**
 * TODO(unverified) — THE MISSING MAPPING.
 * SetXoscCpTrim takes raw 6-bit foot-capacitance codes, NOT a ppm figure, and
 * NO ppm->code mapping is documented in either vendored driver.  This function
 * therefore always returns TEMP_COMP_ERR_UNVERIFIED_MAPPING and writes nothing:
 * it exists so the caller's code path is explicit and testable rather than
 * silently absent.  It must be replaced by a bench-measured mapping before this
 * mechanism is used to fly.
 */
int temp_comp_ppm_to_xosc_cp_trim(float corr_ppm, uint8_t *xta_out, uint8_t *xtb_out);

/**
 * The documented hook that applies the correction to the radio configuration.
 *
 * Behaviour (deliberately conservative):
 *   - identity curve (no bench data)      -> returns TEMP_COMP_OK, corr 0,
 *                                            frame left zeroed, nothing applied;
 *   - characterised curve + mapping still
 *     unverified                          -> returns
 *                                            TEMP_COMP_ERR_UNVERIFIED_MAPPING
 *                                            after reporting the correction, so
 *                                            the caller LOGS and does NOT trim.
 * A caller may pass caller-supplied xta/xtb (from a bench-measured mapping) to
 * get a real 0x0131 frame emitted.
 */
int temp_comp_apply_correction(const temp_comp_curve_t *curve, float temp_c,
                               uint32_t nominal_hz,
                               uint8_t xta, uint8_t xtb, uint8_t wait_time_us,
                               uint8_t frame_out[TEMP_COMP_XOSC_TRIM_FRAME_LEN],
                               float *corr_ppm_out, float *corr_hz_out);

/* ======================================================================== */
/*  8. Layer (d) — 1PPS-gated discipline loop (stub + arithmetic)           */
/* ======================================================================== */

/* LR2021 crystal reference: 32 MHz (ADR-042 Addendum A5; the analysis's
 * 1PPS resolution table uses 32 MHz for the LR2021 and 52 MHz for the SX1280). */
#define TEMP_COMP_REF_HZ_LR2021  32000000u
#define TEMP_COMP_REF_HZ_SX1280  52000000u

/* Longest averaging window the stub will accept, in seconds. */
#define TEMP_COMP_PPS_MAX_WINDOW_S 1000u

/**
 * Counting resolution of the 1PPS-gated measurement, in ppm.
 *
 *   one whole cycle of the reference is the smallest countable unit, so over a
 *   window of M seconds the fractional-frequency resolution is
 *         df/f = 1 / (f_ref * M)
 *   hence  ppm = 1e6 / (f_ref * M).
 *
 * At 32 MHz: 1 s -> 0.03125 ppm, 10 s -> 0.003125 ppm, 100 s -> 0.0003125 ppm.
 * (Matches the analysis table `docs/analysis/thermal-and-frequency-drift.md`
 * §3.2, "1/(f_ref·T)" — pure arithmetic, no datasheet.)
 * Returns 0.0 for an unusable f_ref/window.
 */
double temp_comp_pps_resolution_ppm(uint32_t ref_hz, uint32_t window_s);

/** Integer ppb form of the same quantity (truncated): 1e9 / (f_ref * M). */
uint32_t temp_comp_pps_resolution_ppb(uint32_t ref_hz, uint32_t window_s);

/**
 * Fractional error from a gated count, in ppm:
 *   df/f = (N_measured - f_ref*M) / (f_ref*M),  ppm = 1e6 * df/f.
 */
double temp_comp_pps_frac_error_ppm(uint64_t n_measured, uint32_t ref_hz,
                                    uint32_t window_s);

typedef struct
{
    uint32_t ref_hz;             /* reference being counted                  */
    uint32_t window_s;           /* M: PPS intervals to average over         */
    uint32_t pps_edges;          /* edges seen since begin()                 */
    uint64_t first_count;        /* ref counter at the first edge            */
    uint64_t last_count;         /* ref counter at the most recent edge      */
    uint8_t  armed;              /* 1 between begin() and a completed window */
    uint8_t  ready;              /* 1 once one full window has been collected*/
    double   last_ppm;           /* result of the most recent full window    */
} temp_comp_pps_gate_t;

int  temp_comp_pps_gate_begin(temp_comp_pps_gate_t *g, uint32_t ref_hz,
                              uint32_t window_s);
int  temp_comp_pps_gate_reset(temp_comp_pps_gate_t *g);
/**
 * Feed a PPS edge and the reference-counter value sampled at that edge.
 * Returns TEMP_COMP_OK.  When the window completes (window_s + 1 edges have
 * been seen) it sets g->ready = 1, computes g->last_ppm and leaves the gate
 * ready for the next window (rolling).
 *
 * TODO(unverified): the HARDWARE path that actually counts the 32 MHz reference
 * between PPS edges is NOT confirmed — which timer/PIO peripheral counts it, and
 * whether the discipline edge is GNSS_PPS on GPIO21 (ADR-108) on this board, are
 * both open.  This is the state machine and its arithmetic only.
 */
int  temp_comp_pps_gate_on_pps(temp_comp_pps_gate_t *g, uint64_t ref_count_now);

#ifdef __cplusplus
}
#endif

#endif /* TEMP_COMP_H */
