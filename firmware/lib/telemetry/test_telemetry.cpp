// TDD entry point for S1. This test is written BEFORE the implementation, and
// its RED state is a build failure (telemetry.cpp does not exist yet).
//
// Counter-tests (must be able to fail):
//   - corrupt one payload byte  -> decode() must return BadCrc, not Ok
//   - truncate the buffer       -> decode() must return TooShort
//   - bump the version byte     -> decode() must return BadVersion
//   - undersized output buffer  -> encode() must return 0, not a partial write
#include "harness.h"
#include "telemetry.h"

using namespace balloon;

static TelemetryRecord sample() {
  TelemetryRecord r{};
  r.ntc_sense_mv = 512.5f;
  r.scap_adc_mv = 4210.0f;
  r.f33_vsense_mv = 3301.25f;
  r.hub_pv_mid1_mv = 2100.0f;
  r.hub_pv_p_mv = 4300.0f;
  r.hub_pv_n_mv = 4250.0f;
  r.gps_fix = 1;
  r.gps_sats = 9;
  r.gps_alt_m = 8314.5f;
  r.gps_vdop = 1.42f;
  r.link_rssi_dbm = -97.5f;
  r.link_snr_db = 8.25f;
  r.uptime_s = 3600;
  r.reset_cause = 1;  // power-on
  r.boot_count = 42;
  r.exp_mode = 2;  // cold-start experiment
  return r;
}

void run_tests() {
  CASE("encoded_size matches what encode writes");
  {
    uint8_t buf[256];
    size_t n = encode(sample(), buf, sizeof buf);
    CHECK_EQ(n, encoded_size());
  }

  CASE("round trip preserves every field");
  {
    uint8_t buf[256];
    TelemetryRecord in = sample();
    size_t n = encode(in, buf, sizeof buf);
    CHECK(n > 0);

    TelemetryRecord out{};
    CHECK(decode(buf, n, out) == DecodeResult::Ok);
    CHECK_NEAR(out.ntc_sense_mv, in.ntc_sense_mv, 0.01);
    CHECK_NEAR(out.scap_adc_mv, in.scap_adc_mv, 0.01);
    CHECK_NEAR(out.f33_vsense_mv, in.f33_vsense_mv, 0.01);
    CHECK_NEAR(out.gps_alt_m, in.gps_alt_m, 0.01);
    CHECK_NEAR(out.link_rssi_dbm, in.link_rssi_dbm, 0.01);
    CHECK_EQ(out.gps_fix, in.gps_fix);
    CHECK_EQ(out.gps_sats, in.gps_sats);
    CHECK_EQ(out.uptime_s, in.uptime_s);
    CHECK_EQ(out.boot_count, in.boot_count);
    CHECK_EQ(out.reset_cause, in.reset_cause);
    CHECK_EQ(out.exp_mode, in.exp_mode);
  }

  CASE("COUNTER-TEST: a single flipped payload byte must be rejected");
  {
    uint8_t buf[256];
    size_t n = encode(sample(), buf, sizeof buf);
    buf[1] ^= 0x01;  // first payload byte
    TelemetryRecord out{};
    CHECK(decode(buf, n, out) == DecodeResult::BadCrc);
  }

  CASE("COUNTER-TEST: truncated buffer must be rejected, not misread");
  {
    uint8_t buf[256];
    size_t n = encode(sample(), buf, sizeof buf);
    TelemetryRecord out{};
    CHECK(decode(buf, n - 1, out) == DecodeResult::TooShort);
    CHECK(decode(buf, 0, out) == DecodeResult::TooShort);
  }

  CASE("COUNTER-TEST: unknown version must be rejected");
  {
    uint8_t buf[256];
    size_t n = encode(sample(), buf, sizeof buf);
    buf[0] = 0x7F;
    TelemetryRecord out{};
    CHECK(decode(buf, n, out) == DecodeResult::BadVersion);
  }

  CASE("COUNTER-TEST: undersized output must not partially write");
  {
    uint8_t small[4];
    CHECK_EQ(encode(sample(), small, sizeof small), 0);
    CHECK_EQ(encode(sample(), nullptr, 0), 0);
  }
}

TEST_MAIN()
