// test_radio.cpp — FW-5a host tests: radio backend TX + band matrix.
//
// Provenance for every expected byte (see src/flrc_range_host_radio.h):
//   - sweep cold-init backbone : src/flrc_range_tx_sweep.cpp rawInitRadio
//   - per-band init matrix     : src/dual_radio_gps_sweep_tx.cpp L497-602
//   - SET_TX_PATH + PA select  : src/multi_radio_sweep_gps_v4.cpp L786-793
//   - ms->RTC-step ticks       : vendored lr20xx_driver (32768 Hz RTC)
//
// Build: make -C firmware/rp2040/host-tests test_radio

#include <cstdio>
#include <cstring>
#include <vector>

#include "flrc_range_host_radio.h"
#include "flrc_range_host_safety.h"

static int failures = 0;

#define CHECK(cond)                                                          \
    do {                                                                     \
        if (!(cond)) {                                                       \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);           \
            failures++;                                                      \
        }                                                                    \
    } while (0)

/* ── command recorder sink ─────────────────────────────────────────── */

struct Rec {
    struct Ent {
        uint8_t b[12];
        size_t n;
        uint32_t delay_after;
    };
    std::vector<Ent> e;

    static void sink(void *user, const uint8_t *cmd, size_t len, uint32_t d) {
        Rec *r = static_cast<Rec *>(user);
        Ent x;
        memset(&x, 0, sizeof x);
        x.n = len > sizeof x.b ? sizeof x.b : len;
        for (size_t i = 0; i < x.n; i++) x.b[i] = cmd[i];
        x.delay_after = d;
        r->e.push_back(x);
    }

    size_t count() const { return e.size(); }

    /* entry idx must equal the given bytes (and optionally delay) */
    bool at(size_t idx, const uint8_t *bytes, size_t n, uint32_t delay = 0) const {
        if (idx >= e.size()) return false;
        const Ent &x = e[idx];
        if (x.n != n) return false;
        if (memcmp(x.b, bytes, n) != 0) return false;
        if (delay && x.delay_after != delay) return false;
        return true;
    }
};

static void expect(const Rec &r, size_t idx, const char *what,
                   std::initializer_list<uint8_t> bytes, uint32_t delay = 0) {
    std::vector<uint8_t> v(bytes);
    if (!r.at(idx, v.data(), v.size(), delay)) {
        printf("FAIL %s: entry %zu mismatch (got %zu bytes:", what, idx,
               idx < r.count() ? r.e[idx].n : 0);
        if (idx < r.count())
            for (size_t i = 0; i < r.e[idx].n; i++) printf(" %02X", r.e[idx].b[i]);
        printf(", expected:");
        for (uint8_t b : v) printf(" %02X", b);
        printf(")\n");
        failures++;
    }
}

/* ── configs under test ────────────────────────────────────────────── */

static bench_radio_cfg_t flrc_lf_cfg() {
    bench_radio_cfg_t c{};
    c.mod = BENCH_MOD_FLRC;
    c.freq_hz = 868000000U;
    c.flrc_br_kbps = 650;
    c.dbm = 10;
    c.pkt_len = 51;
    c.tx_timeout_ms = 100; /* FW-4 floor */
    return c;
}

static bench_radio_cfg_t flrc_hf_cfg() {
    bench_radio_cfg_t c{};
    c.mod = BENCH_MOD_FLRC;
    c.freq_hz = 2440000000U;
    c.flrc_br_kbps = 2600;
    c.dbm = 12;
    c.pkt_len = 127;
    c.tx_timeout_ms = 100;
    return c;
}

static bench_radio_cfg_t lora_lf_cfg(uint8_t sf, uint8_t bw_code) {
    bench_radio_cfg_t c{};
    c.mod = BENCH_MOD_LORA;
    c.freq_hz = 868000000U;
    c.lora_sf = sf;
    c.lora_bw_code = bw_code;
    c.lora_cr = 1;
    c.dbm = 10;
    c.pkt_len = 51;
    c.tx_timeout_ms = 100;
    return c;
}

/* ── 1. band matrix ────────────────────────────────────────────────── */

static void test_band_matrix_lf() {
    bench_radio_band_params_t p = bench_radio_band_for_freq(868000000U);
    CHECK(!p.is_hf);
    CHECK(p.rx_path == 0x00);
    CHECK(p.tx_path == 0x00);
    CHECK(p.pa_sel == 0x00);
    CHECK(p.fe_freq == 0x00D9); /* (868/4)+0.5 = 217 */

    p = bench_radio_band_for_freq(869525000U);
    CHECK(!p.is_hf && p.fe_freq == 0x00D9);
}

static void test_band_matrix_hf() {
    bench_radio_band_params_t p = bench_radio_band_for_freq(2440000000U);
    CHECK(p.is_hf);
    CHECK(p.rx_path == 0x01);
    CHECK(p.tx_path == 0x01);
    CHECK(p.pa_sel == 0x80);
    CHECK(p.fe_freq == 0x8262); /* 610 | 0x8000 */
}

static void test_band_matrix_threshold() {
    CHECK(!bench_radio_band_for_freq(1500000000U).is_hf); /* boundary: LF */
    CHECK(bench_radio_band_for_freq(1500000001U).is_hf);  /* above: HF */
}

/* ── 2. chip TX timeout ticks (FW-4 -> SET_TX) ─────────────────────── */

static void test_tx_timeout_ticks() {
    /* vendored driver: ticks = ms * 32768 / 1000 */
    CHECK(bench_radio_tx_timeout_ticks(100U) == 3276U);
    CHECK(bench_radio_tx_timeout_ticks(60000U) == 1966080U);
    /* 24-bit SetTx register cap */
    CHECK(bench_radio_tx_timeout_ticks(600000U) == 0xFFFFFFU);
    /* FW-4 output domain [100, 60000] ms never maps to 0x000000 (continuous) */
    CHECK(bench_radio_tx_timeout_ticks(100U) != 0U);
    CHECK(bench_radio_tx_timeout_ticks(60000U) != 0U);
}

static void test_set_tx_bytes() {
    uint8_t b[5];
    bench_radio_set_tx_bytes(1966080U, b); /* 60000 ms */
    const uint8_t want1[] = {0x02, 0x0D, 0x1E, 0x00, 0x00};
    CHECK(memcmp(b, want1, 5) == 0);

    bench_radio_set_tx_bytes(3276U, b); /* 100 ms */
    const uint8_t want2[] = {0x02, 0x0D, 0x00, 0x0C, 0xCC};
    CHECK(memcmp(b, want2, 5) == 0);

    /* NEVER the sweep-fw continuous-TX pattern for a FW-4 timeout */
    const uint8_t cont[] = {0x02, 0x0D, 0x00, 0x00, 0x00};
    for (uint32_t ms = 100; ms <= 60000; ms += 997) {
        bench_radio_set_tx_bytes(bench_radio_tx_timeout_ticks(ms), b);
        if (memcmp(b, cont, 5) == 0) {
            printf("FAIL set_tx continuous pattern at %lu ms\n", (unsigned long)ms);
            failures++;
            break;
        }
    }
}

static void test_fw4_integration_ticks() {
    /* set_tx carries the FW-4 chip timeout for the active config (B1). */
    uint32_t ms = bench_safety_tx_timeout_ms(BENCH_MOD_FLRC, 7, 250000, 650000, 51);
    uint32_t t = bench_radio_tx_timeout_ticks(ms);
    CHECK(ms >= 100 && ms <= 60000);
    CHECK(t != 0 && t <= 0xFFFFFFU);

    ms = bench_safety_tx_timeout_ms(BENCH_MOD_LORA, 12, 125000, 0, 255);
    t = bench_radio_tx_timeout_ticks(ms);
    CHECK(ms >= 100 && ms <= 60000);
    CHECK(t != 0 && t <= 0xFFFFFFU);
}

/* ── 3. small helpers ──────────────────────────────────────────────── */

static void test_flrc_br_to_code() {
    CHECK(bench_radio_flrc_br_to_code(2600) == 0x00);
    CHECK(bench_radio_flrc_br_to_code(2080) == 0x01);
    CHECK(bench_radio_flrc_br_to_code(1300) == 0x02);
    CHECK(bench_radio_flrc_br_to_code(1040) == 0x03);
    CHECK(bench_radio_flrc_br_to_code(650) == 0x04);
    CHECK(bench_radio_flrc_br_to_code(520) == 0x05);
    CHECK(bench_radio_flrc_br_to_code(325) == 0x06);
    CHECK(bench_radio_flrc_br_to_code(260) == 0x07);
    CHECK(bench_radio_flrc_br_to_code(999) == BENCH_RADIO_FLRC_BR_INVALID);
}

static void test_tx_power_byte() {
    /* exact half-dB math for integer dBm (sweep float helper off by 0.5 on
     * negative powers); two's-complement byte per SET_TX_PARAMS signed field */
    CHECK(bench_radio_tx_power_byte(-18) == 0xDC);
    CHECK(bench_radio_tx_power_byte(0) == 0x00);
    CHECK(bench_radio_tx_power_byte(10) == 0x14);
    CHECK(bench_radio_tx_power_byte(12) == 0x18);
    CHECK(bench_radio_tx_power_byte(22) == 0x2C);
}

static void test_cfg_valid() {
    bench_radio_cfg_t c = flrc_lf_cfg();
    CHECK(bench_radio_cfg_valid(&c));

    c.flrc_br_kbps = 999;
    CHECK(!bench_radio_cfg_valid(&c));

    c = lora_lf_cfg(7, 0x05);
    CHECK(bench_radio_cfg_valid(&c));

    c.lora_sf = 13;
    CHECK(!bench_radio_cfg_valid(&c));
    c.lora_sf = 7;
    c.lora_bw_code = 0x99;
    CHECK(!bench_radio_cfg_valid(&c));
    c.lora_bw_code = 0x05;
    c.pkt_len = 0;
    CHECK(!bench_radio_cfg_valid(&c));
    c.pkt_len = 255;
    CHECK(bench_radio_cfg_valid(&c));
    c.pkt_len = 256; /* over FLRC FIFO / LoRa payload byte */
    CHECK(!bench_radio_cfg_valid(&c));
}

/* ── 4. full init sequences ────────────────────────────────────────── */

static void test_full_init_flrc_lf() {
    Rec r;
    bench_radio_cfg_t c = flrc_lf_cfg();
    bench_radio_emit_full_init(&c, Rec::sink, &r);

    CHECK(r.count() == 17);
    expect(r, 0, "cold preamble 1", {0x01, 0x11, 0x00, 0x00}, 1);
    expect(r, 1, "cold preamble 2", {0x01, 0x28, 0x01}, 5);
    expect(r, 2, "pkt type FLRC", {0x02, 0x07, 0x04}, 1); /* dual_radio 0x04 */
    expect(r, 3, "rf freq 868", {0x02, 0x00, 0x42, 0xC4, 0xEC}, 1);
    expect(r, 4, "rx path LF", {0x02, 0x01, 0x00, 0x00}, 1);
    expect(r, 5, "cal front end LF", {0x01, 0x23, 0x00, 0xD9, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00}, 5);
    expect(r, 6, "calibrate", {0x01, 0x22, 0x5F}, 5);
    expect(r, 7, "flrc mod 650k", {0x02, 0x48, 0x04, 0x25}, 1);
    expect(r, 8, "flrc sync", {0x02, 0x4C, 0x01, 0x12, 0xAD, 0x10, 0x1B}, 1);
    expect(r, 9, "flrc pkt len 51", {0x02, 0x49, 0x0C, 0x4C, 0x00, 0x33}, 1);
    expect(r, 10, "tx path LF", {0x02, 0x02, 0x00, 0x00}, 1);
    expect(r, 11, "pa select LF", {0x02, 0x02, 0x00, 0x00, 0x60, 0x07, 0x10}, 1);
    expect(r, 12, "tx params 10dBm", {0x02, 0x03, 0x14, 0x04}, 1);
    expect(r, 13, "fallback", {0x02, 0x06, 0x03}, 1);
    expect(r, 14, "dio irq routing", {0x01, 0x12, 0x09, 0x11}, 1);
    expect(r, 15, "dio irq mask", {0x01, 0x15, 0x09, 0x00, 0x08, 0x00, 0x00}, 1);
    expect(r, 16, "clear irq", {0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF}, 10);
}

static void test_full_init_flrc_hf() {
    Rec r;
    bench_radio_cfg_t c = flrc_hf_cfg();
    bench_radio_emit_full_init(&c, Rec::sink, &r);

    CHECK(r.count() == 17);
    expect(r, 2, "pkt type", {0x02, 0x07, 0x04});
    expect(r, 3, "rf freq 2440", {0x02, 0x00, 0xBB, 0xB1, 0x3B});
    expect(r, 4, "rx path HF", {0x02, 0x01, 0x01, 0x00});
    expect(r, 5, "cal front end HF", {0x01, 0x23, 0x82, 0x62, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00});
    expect(r, 7, "flrc mod 2600k", {0x02, 0x48, 0x00, 0x25});
    expect(r, 9, "flrc pkt len 127", {0x02, 0x49, 0x0C, 0x4C, 0x00, 0x7F});
    expect(r, 10, "tx path HF", {0x02, 0x02, 0x01, 0x00});
    expect(r, 11, "pa select HF", {0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10});
    expect(r, 12, "tx params 12dBm", {0x02, 0x03, 0x18, 0x04});
}

static void test_full_init_lora() {
    /* SF7 BW250 CR1: sfBw=0x75, ldro=0 (0.512 ms sym < 16 ms) */
    Rec r;
    bench_radio_cfg_t c = lora_lf_cfg(7, 0x05);
    bench_radio_emit_full_init(&c, Rec::sink, &r);

    CHECK(r.count() == 17);
    expect(r, 2, "pkt type LoRa", {0x02, 0x07, 0x00});
    expect(r, 4, "rx path LF", {0x02, 0x01, 0x00, 0x00});
    expect(r, 7, "lora mod SF7/250k", {0x02, 0x20, 0x75, 0x10});
    expect(r, 8, "lora sync", {0x02, 0x23, 0x12});
    expect(r, 9, "lora pkt", {0x02, 0x21, 0x00, 0x08, 0x33, 0x02});

    /* SF12 BW125: sfBw=0xC4, ldro=1 (32.8 ms sym > 16 ms) */
    Rec r2;
    c = lora_lf_cfg(12, 0x04);
    bench_radio_emit_full_init(&c, Rec::sink, &r2);
    expect(r2, 7, "lora mod SF12/125k", {0x02, 0x20, 0xC4, 0x11});
}

/* ── 5. band-aware reinit ──────────────────────────────────────────── */

static void test_reinit_flrc() {
    Rec r;
    bench_radio_cfg_t c = flrc_lf_cfg();
    bench_radio_emit_reinit(&c, Rec::sink, &r);

    CHECK(r.count() == 11);
    expect(r, 0, "standby", {0x02, 0x00, 0x01}, 1);
    expect(r, 1, "rx path LF", {0x02, 0x01, 0x00, 0x00}, 1);
    expect(r, 2, "front end recALIB (freq may change)", {0x01, 0x23, 0x00, 0xD9, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00}, 5);
    expect(r, 3, "flrc mod", {0x02, 0x48, 0x04, 0x25}, 1);
    expect(r, 4, "flrc sync", {0x02, 0x4C, 0x01, 0x12, 0xAD, 0x10, 0x1B}, 1);
    expect(r, 5, "flrc pkt", {0x02, 0x49, 0x0C, 0x4C, 0x00, 0x33}, 1);
    expect(r, 6, "calibrate", {0x01, 0x22, 0x5F}, 5);
    expect(r, 7, "tx path LF", {0x02, 0x02, 0x00, 0x00}, 1);
    expect(r, 8, "pa select LF", {0x02, 0x02, 0x00, 0x00, 0x60, 0x07, 0x10}, 1);
    expect(r, 9, "tx params", {0x02, 0x03, 0x14, 0x04}, 1);
    expect(r, 10, "clear", {0x02, 0x0B, 0x02}, 1);
}

static void test_reinit_lora() {
    Rec r;
    bench_radio_cfg_t c = lora_lf_cfg(7, 0x05);
    bench_radio_emit_reinit(&c, Rec::sink, &r);

    CHECK(r.count() == 11);
    expect(r, 0, "standby", {0x02, 0x00, 0x01});
    expect(r, 3, "lora mod", {0x02, 0x20, 0x75, 0x10});
    expect(r, 6, "calibrate", {0x01, 0x22, 0x5F});
    expect(r, 10, "clear", {0x02, 0x0B, 0x02});
}

/* ── 6. LF runs must never carry HF-hardwired bytes (B1 bug class) ─── */

static void test_no_hf_hardwire_on_lf() {
    Rec r;
    bench_radio_cfg_t c = flrc_lf_cfg();
    bench_radio_emit_full_init(&c, Rec::sink, &r);
    bench_radio_emit_reinit(&c, Rec::sink, &r);

    const uint8_t rxHf[] = {0x02, 0x01, 0x01, 0x00};
    const uint8_t txHf[] = {0x02, 0x02, 0x01, 0x00};
    const uint8_t paHf[] = {0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10};
    for (const auto &x : r.e) {
        if (x.n == 4 && (memcmp(x.b, rxHf, 4) == 0 || memcmp(x.b, txHf, 4) == 0)) {
            printf("FAIL HF-hardwired path cmd in LF sequence\n");
            failures++;
        }
        if (x.n == 7 && memcmp(x.b, paHf, 7) == 0) {
            printf("FAIL HF PA select (0x80) in LF sequence\n");
            failures++;
        }
    }
}

int main() {
    test_band_matrix_lf();
    test_band_matrix_hf();
    test_band_matrix_threshold();
    test_tx_timeout_ticks();
    test_set_tx_bytes();
    test_fw4_integration_ticks();
    test_flrc_br_to_code();
    test_tx_power_byte();
    test_cfg_valid();
    test_full_init_flrc_lf();
    test_full_init_flrc_hf();
    test_full_init_lora();
    test_reinit_flrc();
    test_reinit_lora();
    test_no_hf_hardwire_on_lf();

    if (failures == 0) {
        printf("test_radio: ALL PASS\n");
        return 0;
    }
    printf("test_radio: %d FAILURE(S)\n", failures);
    return 1;
}
