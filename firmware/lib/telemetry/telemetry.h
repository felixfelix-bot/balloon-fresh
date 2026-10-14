// S1 — telemetry record. THE shared type: every other module depends on this,
// and nothing else. Host-testable: the wire format is pure, no I/O.
//
// Board sources for the electrical fields (hub v9 sense lines):
//   ntc_sense_mv    NTC_SENSE     thermistor, battery/board temperature
//   scap_adc_mv     SCAP_ADC      supercap voltage (DNP on the first order)
//   f33_vsense_mv   F33_VSENSE    3V3 rail sense
//   hub_pv_mid1_mv  HUB_PV_MID1   solar wing mid-point
//   hub_pv_p_mv     HUB_PV_P      solar wing + terminal
//   hub_pv_n_mv     HUB_PV_N      solar wing - terminal
#pragma once

#include <cstddef>
#include <cstdint>

namespace balloon {

// Bump on ANY layout change. Decoders must reject versions they do not know
// rather than reinterpret bytes.
constexpr uint8_t TELEMETRY_VERSION = 1;

#pragma pack(push, 1)
struct TelemetryRecord {
  // electrical (millivolts)
  float ntc_sense_mv;
  float scap_adc_mv;
  float f33_vsense_mv;
  float hub_pv_mid1_mv;
  float hub_pv_p_mv;
  float hub_pv_n_mv;
  // GNSS
  uint8_t gps_fix;      // 0 = none
  uint8_t gps_sats;     // satellites used
  float gps_alt_m;      // MSL altitude, metres
  float gps_vdop;       // vertical dilution of precision
  // link (SX1280 FLRC, or the LoRa fallback when out of range)
  float link_rssi_dbm;
  float link_snr_db;
  // housekeeping / forensics
  uint32_t uptime_s;
  uint8_t reset_cause;  // mirror of esp_reset_reason(), see resetlog
  uint32_t boot_count;
  uint8_t exp_mode;     // active experiment slot, 0 = none
};
#pragma pack(pop)

enum class DecodeResult {
  Ok = 0,
  TooShort,    // buffer smaller than the encoded size
  BadVersion,  // version byte is not TELEMETRY_VERSION
  BadCrc,      // payload did not match its checksum
};

// Wire format, little-endian:
//   [0]      version (1 byte)
//   [1..N]   payload (sizeof(TelemetryRecord))
//   [N+1..4] CRC32 over version+payload
// CRC: IEEE 802.3 polynomial 0xEDB88320, init 0xFFFFFFFF, final XOR 0xFFFFFFFF.
constexpr size_t encoded_size() { return 1 + sizeof(TelemetryRecord) + 4; }

// Returns bytes written, or 0 if out is null or cap < encoded_size().
size_t encode(const TelemetryRecord &rec, uint8_t *out, size_t cap);

// Never partially fills `out` on failure: on any non-Ok result the caller must
// treat `out` as undefined, so callers cannot accidentally use torn data.
DecodeResult decode(const uint8_t *in, size_t len, TelemetryRecord &out);

// Exposed for the CRC counter-test: corrupting one payload byte must change this.
uint32_t crc32(const uint8_t *data, size_t len);

}  // namespace balloon
