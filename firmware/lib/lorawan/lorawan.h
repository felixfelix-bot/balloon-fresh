// L2 -- LoRaWAN fallback link. Header-only surface; lorawan.cpp implements it.
//
// SCOPE. This is the LoRaWAN 1.0-class class-A uplink path for the balloon's
// long-range fallback when the primary 2.4 GHz FLRC link is out of range. It is
// deterministic, allocation-free, and has NO dependency on radio_core: it codes
// against radio_hal.h (the frozen contract) and is tested with a fake HAL.
//
// WHAT THIS IS NOT. There is no network server, no gateway and no radio anywhere
// in this repository. Nothing in this module has ever completed an over-the-air
// join, and no test claims one. The only external ground truth exercised is the
// published test-vector set (RFC 4493, FIPS 197, LoRaWAN 1.1, RP002-1.0.3) --
// see test_lorawan.cpp for the provenance of every constant.
//
// REGION. EU868, DR0..DR5 (SF12..SF7 at 125 kHz), the three mandatory join
// channels 868.1/868.3/868.5 MHz sharing a < 1% sub-band, plus the 10% band at
// 869.4-869.65 MHz. [RP002-1.0.3] Sec. 2.4.2 / 1.3.1.
#pragma once

#include <cstddef>
#include <cstdint>

#include "../radio_core/radio_hal.h"

namespace balloon {
namespace lorawan {

// ===========================================================================
// AES-128 (FIPS 197) -- one block, encrypt and the inverse
// ===========================================================================
struct Aes128 {
  uint8_t round_keys[176];  // 11 round keys x 16 bytes
};

void aes128_init(Aes128 *ctx, const uint8_t key[16]);
void aes128_encrypt_block(const Aes128 *ctx, const uint8_t in[16], uint8_t out[16]);

// One-shot ECB. The inverse direction is what a join-accept needs ([LW104]
// Sec. 6.2.3: the network *decrypts* the join-accept with the block cipher).
void aes128_ecb_encrypt(const uint8_t key[16], const uint8_t in[16], uint8_t out[16]);
void aes128_ecb_decrypt(const uint8_t key[16], const uint8_t in[16], uint8_t out[16]);

// ===========================================================================
// AES-CMAC [RFC4493]
// ===========================================================================
void aes_cmac(const uint8_t key[16], const uint8_t *msg, size_t len, uint8_t out[16]);

// Exposed so the counter-test can feed a deliberately corrupted subkey through
// exactly the same MAC core the RFC 4493 vectors use.
void aes_cmac_subkeys(const uint8_t key[16], uint8_t k1[16], uint8_t k2[16]);
void aes_cmac_with_subkeys(const uint8_t key[16], const uint8_t k1[16],
                           const uint8_t k2[16], const uint8_t *msg, size_t len,
                           uint8_t out[16]);

// ===========================================================================
// LoRaWAN MICs [LW104] Sec. 4.4.1 / 6.2.2 / 6.2.4
//   cmac = aes128_cmac(key, B0 | msg) ; MIC = cmac[0..3]
//   B0   = 0x49 | 0x0000 | 0x0000 | Dir | DevAddr(4, LE) | FCnt(4, LE) | 0x00
//          | len(msg)
//   msg  = MHDR | FHDR | FPort | FRMPayload   (for data frames)
// ===========================================================================
void lorawan_mic_uplink(const uint8_t nwk_s_key[16], uint32_t dev_addr,
                        uint32_t fcnt, const uint8_t *msg, size_t msg_len,
                        uint8_t mic_out[4]);
void lorawan_mic_downlink(const uint8_t nwk_s_key[16], uint32_t dev_addr,
                          uint32_t fcnt, const uint8_t *msg, size_t msg_len,
                          uint8_t mic_out[4]);

// cmac = aes128_cmac(NwkKey, MHDR | JoinEUI | DevEUI | DevNonce)
void lorawan_join_request_mic(const uint8_t nwk_key[16], const uint8_t *msg,
                              size_t msg_len, uint8_t mic_out[4]);

// ===========================================================================
// FRMPayload encryption [LW104] Sec. 4.3.3.1 -- an involution (AES-CTR-like)
//   Ai = 0x01 | 0x00000000 | Dir | DevAddr(4, LE) | FCnt(4, LE) | 0x00 | i
//   S  = aes128_encrypt(K, Ai) ; ct_i = (p_i xor S_i)
// ===========================================================================
void lorawan_crypt_frmpayload(const uint8_t key[16], uint32_t dev_addr,
                              uint8_t dir, uint32_t fcnt, const uint8_t *in,
                              uint8_t *out, size_t len);

// ===========================================================================
// Session key derivation ([LW104] Sec. 6.1.1.3, OptNeg unset / 1.0 form)
//   NwkSKey = aes128_encrypt(NwkKey, 0x01 | JoinNonce(4, LE) | NetID(3) |
//                            DevNonce(2, LE) | pad7)
//   AppSKey = aes128_encrypt(NwkKey, 0x02 | ...same...)
// `net_id` is in wire order (the order it appears on the air).
// ===========================================================================
void derive_session_keys_1_0(const uint8_t nwk_key[16], uint32_t join_nonce,
                             const uint8_t net_id[3], const uint8_t join_eui[8],
                             uint16_t dev_nonce, uint8_t nwk_s_key_out[16],
                             uint8_t app_s_key_out[16]);

// ===========================================================================
// EU868 data rates and payload limits [RP002-1.0.3]
// ===========================================================================
// Sec. 2.4.6 Table 13, "not repeater compatible". The task spec quotes the
// application-payload column N; M is the MACPayload column, kept for completeness.
int eu868_max_app_payload(int dr);   // N; -1 if DR is not DR0..DR5
int eu868_max_mac_payload(int dr);   // M; -1 if DR is not DR0..DR5
int eu868_sf_for_dr(int dr);         // Table 8; -1 if unknown
uint32_t eu868_bandwidth_hz_for_dr(int dr);
bool payload_fits(size_t app_payload_len, int dr);

// ===========================================================================
// Time on air (Semtech LoRa modem formula)
//   Tsym  = 2^SF / BW
//   Tpre  = (n_preamble + 4.25) * Tsym
//   n_sym = 8 + max(ceil((8*PL - 4*SF + 28 + 16 - 20*IH) /
//                         (4*(SF - 2*DE))) * CR, 0)     [CR = 5..8]
//   ToA   = Tpre + n_sym * Tsym
// `coding_rate` is the denominator (5 => 4/5). `low_data_rate_opt` is the DE
// bit, which is mandatory for SF11/SF12 at 125 kHz.
// ===========================================================================
uint32_t lora_symbol_duration_us(uint8_t sf, uint32_t bandwidth_hz);
int lora_payload_symbol_count(size_t payload_len, uint8_t sf, uint8_t coding_rate,
                              bool header_enabled, bool low_data_rate_opt);
uint32_t lora_time_on_air_us(size_t payload_len, uint8_t sf, uint32_t bandwidth_hz,
                             uint8_t coding_rate, uint16_t preamble_symbols,
                             bool header_enabled, bool low_data_rate_opt);
// LDRO applied automatically for SF11/SF12 at 125 kHz, as the regional
// parameters require.
uint32_t eu868_time_on_air_us(int dr, size_t payload_len,
                              uint16_t preamble_symbols, uint8_t coding_rate);

// ===========================================================================
// Duty-cycle limiter -- [RP002-1.0.3] Sec. 2.4.2 Table 6 and Sec. 1.3.1
// ===========================================================================
constexpr int kEu868DefaultChannelCount = 3;
extern const uint32_t kEu868DefaultChannelsHz[kEu868DefaultChannelCount];

int eu868_sub_band_index(uint32_t freq_hz);       // -1 if no EU868 sub-band covers it
int eu868_sub_band_count();
uint32_t eu868_sub_band_duty_num(int band);       // duty = num/den
uint32_t eu868_sub_band_duty_den(int band);
const char *eu868_sub_band_name(int band);

struct DutyCycleVerdict {
  bool allowed;
  int band;
  uint32_t wait_ms;   // how long until this frame would be legal (0 if allowed)
};

// Sliding one-hour window per sub-band. The budget is duty_num/duty_den of one
// hour, and it is shared by every channel in the band -- that is the point of a
// sub-band model, and it is asserted in the tests.
class DutyCycleLimiter {
 public:
  explicit DutyCycleLimiter(uint32_t duty_denominator = 100);

  DutyCycleVerdict request(uint32_t freq_hz, uint32_t airtime_ms, uint64_t now_ms);
  bool can_send(uint32_t freq_hz, uint32_t airtime_ms, uint64_t now_ms);

  // Earliest instant at which `airtime_ms` on this frequency would be legal.
  uint64_t earliest(uint32_t freq_hz, uint32_t airtime_ms, uint64_t now_ms);

  // Airtime charged inside [from_ms, to_ms) for the band covering freq_hz.
  uint32_t band_airtime_ms(int band, uint64_t from_ms, uint64_t to_ms) const;

  uint32_t blocked_count() const { return blocked_; }
  void set_band_duty_override(int band, uint32_t num, uint32_t den);

 private:
  struct Entry {
    uint64_t at_ms = 0;
    uint32_t ms = 0;
    int8_t band = -1;
  };
  static constexpr int kMaxEntries = 512;
  Entry log_[kMaxEntries];
  int head_ = 0;
  int size_ = 0;

  void push(uint64_t at_ms, uint32_t ms, int band);
  void budget_for(int band, uint32_t *num, uint32_t *den) const;
  // Airtime charged to `band` that is still inside `now`'s one-hour window.
  uint32_t charged(int band, uint64_t now_ms) const;

  uint32_t blocked_ = 0;
  uint32_t duty_den_;
  uint32_t override_num_[8] = {0};
  uint32_t override_den_[8] = {0};
};

// ===========================================================================
// Join-request duty cycle -- [LW104] Table 17
//   hours 0..1 after reset : < 36 s aggregated
//   hours 1..11            : < 36 s aggregated
//   after hour 11, per 24 h: < 8.7 s aggregated
// ===========================================================================
class JoinBackoff {
 public:
  void reset(uint64_t now_ms);
  bool allowed(uint32_t airtime_ms, uint64_t now_ms) const;
  void record(uint32_t airtime_ms, uint64_t now_ms);
  uint32_t join_airtime_ms(uint64_t from_ms, uint64_t to_ms) const;

  static constexpr uint32_t kFirstHourCapMs = 36000;
  static constexpr uint32_t kSecondWindowCapMs = 36000;
  static constexpr uint32_t kSteadyStateCapMs = 8700;
  static constexpr uint64_t kFirstHourEndMs = 3600000ull;
  static constexpr uint64_t kSecondWindowEndMs = 11ull * 3600000ull;
  static constexpr uint64_t kSteadyStateWindowMs = 24ull * 3600000ull;

 private:
  static constexpr int kMaxEntries = 512;
  struct Entry {
    uint64_t at_ms = 0;
    uint32_t ms = 0;
  };
  Entry log_[kMaxEntries];
  int head_ = 0;
  int size_ = 0;
  uint64_t reset_ms_ = 0;
};

// ===========================================================================
// Frame counters
// ===========================================================================
// Uplink counter: 32 bit, strictly increasing, never repeated. init() takes a
// persisted value but treats it as a FLOOR: a stale store can never move the
// counter backwards (that would replay frames the server already saw).
// Rollover past 2^32 must be opted into; without it the counter sticks rather
// than silently reusing the whole space.
class FrameCounters {
 public:
  void init(uint32_t persisted_uplink, uint32_t persisted_downlink,
            bool allow_rollover = false);

  uint32_t uplink_next() const { return uplink_; }
  bool can_take_uplink() const;
  uint32_t take_uplink();              // returns the value used
  bool exhausted() const;
  bool rolled_over() const { return rolled_over_; }

  bool accept_downlink(uint32_t fcnt);
  uint32_t downlink_last() const { return downlink_last_; }

  void snapshot(uint32_t *uplink_out, uint32_t *downlink_out) const;

 private:
  uint32_t uplink_ = 0;
  uint32_t high_water_ = 0;
  uint32_t downlink_last_ = 0;
  bool has_downlink_ = false;
  bool allow_rollover_ = false;
  // Set the instant 0xFFFFFFFF wraps, but only REPORTED once the counter has
  // actually been re-used at 0 -- i.e. the wrap has been handed out, not just
  // scheduled.
  bool wrap_pending_ = false;
  bool rolled_over_ = false;
};

// ===========================================================================
// Join state machine + class-A uplink, against the frozen radio HAL
// ===========================================================================
enum class JoinState : uint8_t {
  Idle = 0,        // never joined, no join in flight
  Requesting,      // a join-request has been sent, awaiting accept
  Joined,          // session established
  Failed,          // retries exhausted
};

struct MacConfig {
  uint8_t dev_eui[8];      // wire order
  uint8_t join_eui[8];     // wire order
  uint8_t app_key[16];     // LoRaWAN 1.0 root key
  uint8_t app_eui[8];      // kept for API symmetry; unused in 1.0
  uint32_t join_channel_hz;
  int join_dr;
  uint8_t join_retry_max;
  uint16_t preamble_symbols;
  uint8_t coding_rate;     // 5..8
  int8_t tx_power_dbm;
  uint32_t duty_denominator;   // 100 = 1%
};

struct Session {
  bool joined = false;
  uint32_t dev_addr = 0;
  uint8_t net_id[3] = {0, 0, 0};
  uint16_t dev_nonce = 0;
  uint8_t nwk_skey[16] = {0};
  uint8_t app_skey[16] = {0};
};

class LorawanMac {
 public:
  LorawanMac(radio::RadioHal *hal, const MacConfig &cfg);
  ~LorawanMac();

  LorawanMac(const LorawanMac &) = delete;
  LorawanMac &operator=(const LorawanMac &) = delete;

  JoinState state() const { return state_; }
  uint8_t join_retries_left() const { return retries_left_; }

  // Send a join-request. Increments DevNonce, programs the HAL, transmits,
  // then releases the radio. Returns the HAL's verdict.
  radio::Result start_join(uint64_t now_ms);

  // Drain the receive path once (called after each uplink's RX windows). On a
  // valid join-accept this completes the join and derives the session keys.
  radio::Result poll(uint64_t now_ms);

  // Class-A uplink. Refuses (and transmits nothing) if not joined, if the
  // payload exceeds the data rate's limit, or if the duty cycle forbids it.
  radio::Result send_uplink(const uint8_t *payload, size_t len, uint8_t fport,
                            int dr, uint32_t freq_hz, uint64_t now_ms);

  const Session &session() const { return session_; }
  const FrameCounters &counters() const { return counters_; }
  FrameCounters &counters() { return counters_; }
  const DutyCycleLimiter &duty() const { return duty_; }
  DutyCycleLimiter &duty() { return duty_; }
  const MacConfig &config() const { return cfg_; }

  // Air time a PHY frame of `phy_len` bytes would occupy at `dr`.
  uint32_t airtime_for(int dr, size_t phy_len) const;

 private:
  radio::Result transmit(const uint8_t *frame, size_t len, uint32_t freq_hz, int dr);
  bool accept_join_accept(const uint8_t *frame, size_t len);

  radio::RadioHal *hal_;
  MacConfig cfg_;
  Session session_;
  FrameCounters counters_;
  DutyCycleLimiter duty_;
  JoinBackoff join_backoff_;
  JoinState state_ = JoinState::Idle;
  uint8_t retries_left_ = 0;
  uint16_t dev_nonce_ = 0;
  bool duty_initialized_ = false;
};

}  // namespace lorawan
}  // namespace balloon
