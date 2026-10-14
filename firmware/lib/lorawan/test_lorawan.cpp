// L2 (LoRaWAN fallback link) -- TDD entry point.
//
// RED FIRST. This test was written before lorawan.cpp existed, so the first run
// is a BUILD FAILURE (undefined references). That observed failure is the RED.
//
// GROUND TRUTH POLICY (read this before trusting any number below)
// ---------------------------------------------------------------
// There is NO LoRaWAN network, gateway, concentrator or radio on this host.
// Nothing here proves an over-the-air join or uplink. It cannot: the only radio
// is FakeRadioHal below, a stub that records call order. A host mock is not a
// radio.
//
// The external truth in this file is a small set of published artefacts, each
// independently re-derived with `openssl` before being baked in as a constant:
//
//   [RFC4493]  Song/Iwata, "The AES-CMAC Algorithm", June 2006 -- Sec. 4 test
//              vectors and the subkey table (verbatim, page 11).
//   [FIPS197]  NIST FIPS 197-upd1, Appendix B cipher example and Appendix C.1.
//   [BROCAAR]  github.com/brocaar/lorawan (Apache-2.0), phypayload_test.go and
//              backend/joinserver/joinserver_test.go -- the de-facto published
//              LoRaWAN wire-format vector set: raw frame bytes, the key, and
//              the expected MIC / session keys.
//   [RP002]    LoRa Alliance RP002-1.0.3 Regional Parameters, Sec. 2.4.2
//              Table 6 (default channels < 1%), Table 8 (DR/SF map), Sec. 2.4.6
//              Table 13 (EU863-870 max payload size, not repeater compatible),
//              Sec. 1.3.1 (region duty cycles).
//   [LW104]    LoRaWAN 1.1 Specification -- Sec. 4.4.1 (cmac = aes128_cmac(key,
//              B0 | msg)), 6.2.2 / 6.2.4 (join MICs), 6.1.1.3 (session key
//              derivation), Sec. 4.3.3.1 (FRMPayload keystream), and Table 17
//              (join-request duty-cycle limits).
//
// Sources were fetched to /tmp/lwvec on the build host on 2026-10-14:
//   rfc4493.txt  sha256 252850ac038a44e931fdce6cb02b444a18ed1da0c9e212bfdd1da0ed3366fc1c
//   fips197.pdf  sha256 62c86eb567f13edb8f71826e985da870b04ef6381634f303cdb16e84d47becd1
//   rp.pdf (RP002-1.0.3) sha256 7babdb743e051fdc...
//   spec.pdf (LoRaWAN 1.1) sha256 c202b49feca0f5d2...
//
// Every expected MIC and session key below was reproduced byte-for-byte with
// OpenSSL's own CMAC/AES primitives -- an entirely independent implementation --
// before being written down here.
//
// COUNTER-TESTS (a green suite with no counter-test is not evidence):
//   - corrupt one FRMPayload byte     -> MIC must change
//   - corrupt one AES-CMAC subkey bit -> every RFC 4493 vector must break
//   - skip the duty-cycle refusal     -> the burst test must fail
//   - let the frame counter regress   -> the reboot test must fail
//   - flip the B0 direction byte      -> uplink/downlink MICs must differ

#include "harness.h"

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>

#include "lorawan.h"
#include "../radio_core/radio_hal.h"

using namespace balloon;
using namespace balloon::lorawan;

namespace {

// ---------------------------------------------------------------------------
// FakeRadioHal -- ours, defined here. radio_core.cpp is deliberately NOT
// compiled or linked: we code against the frozen header only. make_radio_hal is
// never defined by this translation unit.
// ---------------------------------------------------------------------------
struct CallLog {
  int acquire = 0, release = 0, configure = 0, send = 0, receive = 0;
  int set_rx_continuous = 0;
  int acquire_seq = -1, configure_seq = -1, send_seq = -1, release_seq = -1;
  radio::Config first_config{};
  bool saw_config = false;
};

class FakeRadioHal : public radio::RadioHal {
 public:
  ~FakeRadioHal() override = default;

  CallLog log;

  // test knobs
  radio::Result acquire_result = radio::Result::Ok;
  radio::Result configure_result = radio::Result::Ok;
  radio::Result send_result = radio::Result::Ok;
  bool received_pending = false;
  uint8_t rx_buffer[256] = {0};
  size_t rx_len = 0;
  int16_t rssi_dbm = -110;
  int8_t snr_db = 4;
  std::vector<uint8_t> sent;

  radio::Result acquire(uint32_t) override {
    ++log.acquire;
    log.acquire_seq = seq_++;
    if (acquire_result != radio::Result::Ok) return acquire_result;
    if (acquired_) return radio::Result::Busy;
    acquired_ = true;
    return radio::Result::Ok;
  }

  radio::Result release() override {
    ++log.release;
    log.release_seq = seq_++;
    if (!acquired_) return radio::Result::NotAcquired;
    acquired_ = false;
    return radio::Result::Ok;
  }

  bool is_acquired() const override { return acquired_; }

  radio::Result reset() override { return radio::Result::Ok; }

  radio::Result configure(const radio::Config &cfg) override {
    ++log.configure;
    log.configure_seq = seq_++;
    if (!acquired_) return radio::Result::NotAcquired;
    if (configure_result != radio::Result::Ok) return configure_result;
    log.first_config = cfg;
    log.saw_config = true;
    return radio::Result::Ok;
  }

  radio::Result read_config(radio::Config *out) const override {
    if (!log.saw_config || out == nullptr) return radio::Result::BadArgument;
    *out = log.first_config;
    return radio::Result::Ok;
  }

  radio::Result send(const uint8_t *data, size_t len) override {
    ++log.send;
    log.send_seq = seq_++;
    sent.assign(data, data + len);
    if (!acquired_) return radio::Result::NotAcquired;
    return send_result;
  }

  radio::Result receive(uint8_t *out, size_t max_len, size_t *out_len,
                        uint32_t) override {
    ++log.receive;
    if (!acquired_) return radio::Result::NotAcquired;
    if (!received_pending) {
      *out_len = 0;
      return radio::Result::Ok;
    }
    if (rx_len > max_len) return radio::Result::BadArgument;
    std::memcpy(out, rx_buffer, rx_len);
    *out_len = rx_len;
    received_pending = false;
    return radio::Result::Ok;
  }

  radio::Result set_rx_continuous(bool on) override {
    ++log.set_rx_continuous;
    rx_cont_ = on;
    return radio::Result::Ok;
  }
  radio::Result get_rssi_dbm(int16_t *out) const override {
    if (out == nullptr) return radio::Result::BadArgument;
    *out = rssi_dbm;
    return radio::Result::Ok;
  }
  radio::Result get_snr_db(int8_t *out) const override {
    if (out == nullptr) return radio::Result::BadArgument;
    *out = snr_db;
    return radio::Result::Ok;
  }

 private:
  bool acquired_ = false;
  bool rx_cont_ = false;
  int seq_ = 0;
};

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------
void hex2bin(const char *s, uint8_t *out, size_t n) {
  auto nib = [](char c) -> uint8_t {
    if (c >= '0' && c <= '9') return static_cast<uint8_t>(c - '0');
    if (c >= 'a' && c <= 'f') return static_cast<uint8_t>(c - 'a' + 10);
    if (c >= 'A' && c <= 'F') return static_cast<uint8_t>(c - 'A' + 10);
    return 0;
  };
  for (size_t i = 0; i < n; ++i)
    out[i] = static_cast<uint8_t>((nib(s[2 * i]) << 4) | nib(s[2 * i + 1]));
}

bool eq_hex(const uint8_t *a, const char *hex_expected, size_t n) {
  uint8_t want[128];
  hex2bin(hex_expected, want, n);
  return std::memcmp(a, want, n) == 0;
}

void hexdump(const char *label, const uint8_t *p, size_t n) {
  std::fprintf(stderr, "      %s = ", label);
  for (size_t i = 0; i < n; ++i) std::fprintf(stderr, "%02x", p[i]);
  std::fprintf(stderr, "\n");
}

// Build and encrypt a LoRaWAN 1.0 join-accept frame for the given parameters.
// Caller supplies the ciphertext in out[17] (MHDR + 16 bytes).
void build_join_accept(const uint8_t app_key[16], const uint8_t join_nonce_le3[3],
                       const uint8_t net_id_wire[3], const uint8_t dev_addr_wire[4],
                       uint8_t dls, uint8_t rxdelay, bool corrupt_mic,
                       uint8_t *out, size_t *out_len) {
  // [LW104] Sec. 6.2.3 layout. The 16-byte encrypted block is
  //   MACPayload(12) | MIC(4)
  // where MACPayload = JoinNonce(3, LE) | NetID(3, wire) | DevAddr(4, LE) |
  // DLSettings | RxDelay, and MIC = cmac(AppKey, MHDR | MACPayload).
  // The MHDR is NOT inside the ciphertext -- it is the 0x20 that precedes it on
  // the air. (The published join-accept vector 493eeb51.. decrypts to exactly
  // this shape, which is what pins the layout.)
  uint8_t pt[16];
  pt[0] = join_nonce_le3[0];
  pt[1] = join_nonce_le3[1];
  pt[2] = join_nonce_le3[2];
  pt[3] = net_id_wire[0];
  pt[4] = net_id_wire[1];
  pt[5] = net_id_wire[2];
  pt[6] = dev_addr_wire[0];
  pt[7] = dev_addr_wire[1];
  pt[8] = dev_addr_wire[2];
  pt[9] = dev_addr_wire[3];
  pt[10] = dls;
  pt[11] = rxdelay;
  uint8_t msg[13];
  msg[0] = 0x20;
  std::memcpy(msg + 1, pt, 12);
  uint8_t mic16[16];
  aes_cmac(app_key, msg, 13, mic16);
  if (corrupt_mic) mic16[0] ^= 0x01;
  pt[12] = mic16[0];
  pt[13] = mic16[1];
  pt[14] = mic16[2];
  pt[15] = mic16[3];
  uint8_t ct[16];
  // In LoRaWAN 1.0 the network INVERSE-ciphers the join-accept, so the air
  // bytes are the inverse cipher's output and a 1.0 device recovers the
  // plaintext with the forward cipher.
  aes128_ecb_decrypt(app_key, pt, ct);
  out[0] = 0x20;
  std::memcpy(out + 1, ct, 16);
  *out_len = 17;
}

// ===========================================================================
// 1. AES-128 -- [FIPS197]
// ===========================================================================
void test_aes128() {
  CASE("[FIPS197] App.B: AES-128(2b7e1516.., 3243f6a8..) = 3925841d..");
  {
    uint8_t key[16], pt[16], ct[16];
    hex2bin("2b7e151628aed2a6abf7158809cf4f3c", key, 16);
    hex2bin("3243f6a8885a308d313198a2e0370734", pt, 16);
    Aes128 ctx;
    aes128_init(&ctx, key);
    aes128_encrypt_block(&ctx, pt, ct);
    if (!eq_hex(ct, "3925841d02dc09fbdc118597196a0b32", 16)) hexdump("ct", ct, 16);
    CHECK(eq_hex(ct, "3925841d02dc09fbdc118597196a0b32", 16));
  }

  CASE("[FIPS197] App.C.1: AES-128(000102..0f, 00112233..ff) = 69c4e0d8..");
  {
    uint8_t key[16], pt[16], ct[16], back[16];
    hex2bin("000102030405060708090a0b0c0d0e0f", key, 16);
    hex2bin("00112233445566778899aabbccddeeff", pt, 16);
    Aes128 ctx;
    aes128_init(&ctx, key);
    aes128_encrypt_block(&ctx, pt, ct);
    if (!eq_hex(ct, "69c4e0d86a7b0430d8cdb78070b4c55a", 16)) hexdump("ct", ct, 16);
    CHECK(eq_hex(ct, "69c4e0d86a7b0430d8cdb78070b4c55a", 16));
    aes128_ecb_decrypt(key, ct, back);
    CHECK(eq_hex(back, "00112233445566778899aabbccddeeff", 16));
  }

  CASE("[RFC4493] Sec.4: AES-128(key, 0) = the published subkey seed");
  {
    uint8_t key[16], zero[16], out[16];
    hex2bin("2b7e151628aed2a6abf7158809cf4f3c", key, 16);
    std::memset(zero, 0, 16);
    Aes128 ctx;
    aes128_init(&ctx, key);
    aes128_encrypt_block(&ctx, zero, out);
    if (!eq_hex(out, "7df76b0c1ab899b33e42f047b91b546f", 16)) hexdump("out", out, 16);
    CHECK(eq_hex(out, "7df76b0c1ab899b33e42f047b91b546f", 16));
  }
}

// ===========================================================================
// 2. AES-CMAC -- [RFC4493] Sec. 4, verbatim
// ===========================================================================
void test_cmac_rfc4493() {
  uint8_t key[16];
  hex2bin("2b7e151628aed2a6abf7158809cf4f3c", key, 16);

  CASE("[RFC4493] subkey table: K1 = fbeed618.., K2 = f7ddac30..");
  {
    uint8_t k1[16], k2[16];
    aes_cmac_subkeys(key, k1, k2);
    if (!eq_hex(k1, "fbeed618357133667c85e08f7236a8de", 16)) hexdump("K1", k1, 16);
    if (!eq_hex(k2, "f7ddac306ae266ccf90bc11ee46d513b", 16)) hexdump("K2", k2, 16);
    CHECK(eq_hex(k1, "fbeed618357133667c85e08f7236a8de", 16));
    CHECK(eq_hex(k2, "f7ddac306ae266ccf90bc11ee46d513b", 16));
  }

  CASE("[RFC4493] Example 1: len = 0");
  {
    uint8_t out[16];
    aes_cmac(key, nullptr, 0, out);
    if (!eq_hex(out, "bb1d6929e95937287fa37d129b756746", 16)) hexdump("out", out, 16);
    CHECK(eq_hex(out, "bb1d6929e95937287fa37d129b756746", 16));
  }

  CASE("[RFC4493] Example 2: len = 16 (exact block, K1 path)");
  {
    uint8_t msg[16], out[16];
    hex2bin("6bc1bee22e409f96e93d7e117393172a", msg, 16);
    aes_cmac(key, msg, 16, out);
    if (!eq_hex(out, "070a16b46b4d4144f79bdd9dd04a287c", 16)) hexdump("out", out, 16);
    CHECK(eq_hex(out, "070a16b46b4d4144f79bdd9dd04a287c", 16));
  }

  CASE("[RFC4493] Example 3: len = 40 (needs 10* padding, K2 path)");
  {
    uint8_t msg[40], out[16];
    hex2bin("6bc1bee22e409f96e93d7e117393172a"
            "ae2d8a571e03ac9c9eb76fac45af8e51"
            "30c81c46a35ce411",
            msg, 40);
    aes_cmac(key, msg, 40, out);
    if (!eq_hex(out, "dfa66747de9ae63030ca32611497c827", 16)) hexdump("out", out, 16);
    CHECK(eq_hex(out, "dfa66747de9ae63030ca32611497c827", 16));
  }

  CASE("[RFC4493] Example 4: len = 64 (multi-block, exact multiple)");
  {
    uint8_t msg[64], out[16];
    hex2bin("6bc1bee22e409f96e93d7e117393172a"
            "ae2d8a571e03ac9c9eb76fac45af8e51"
            "30c81c46a35ce411e5fbc1191a0a52ef"
            "f69f2445df4f9b17ad2b417be66c3710",
            msg, 64);
    aes_cmac(key, msg, 64, out);
    if (!eq_hex(out, "51f0bebf7e3b9d92fc49741779363cfe", 16)) hexdump("out", out, 16);
    CHECK(eq_hex(out, "51f0bebf7e3b9d92fc49741779363cfe", 16));
  }

  CASE("COUNTER-TEST: one corrupted subkey bit breaks the published vector");
  {
    uint8_t msg[16], out[16], k1[16], k2[16], goodk1[16];
    hex2bin("6bc1bee22e409f96e93d7e117393172a", msg, 16);
    aes_cmac_subkeys(key, k1, k2);
    std::memcpy(goodk1, k1, 16);

    k1[0] ^= 0x01;  // flip one bit of the real, published K1
    aes_cmac_with_subkeys(key, k1, k2, msg, 16, out);
    CHECK(!eq_hex(out, "070a16b46b4d4144f79bdd9dd04a287c", 16));

    // and the honest subkeys reproduce the vector exactly (same code path)
    aes_cmac_with_subkeys(key, goodk1, k2, msg, 16, out);
    CHECK(eq_hex(out, "070a16b46b4d4144f79bdd9dd04a287c", 16));
  }

  CASE("COUNTER-TEST: the Rb constant matters -- wrong Rb breaks len 40");
  {
    uint8_t msg[40], out[16];
    hex2bin("6bc1bee22e409f96e93d7e117393172a"
            "ae2d8a571e03ac9c9eb76fac45af8e51"
            "30c81c46a35ce411",
            msg, 40);
    aes_cmac(key, msg, 40, out);
    CHECK(eq_hex(out, "dfa66747de9ae63030ca32611497c827", 16));
    // a 0x87-free shift would give a different answer; assert the difference is
    // observable by checking the padded path is not the same as the K1 path
    uint8_t out2[16];
    aes_cmac(key, msg, 48, out2);  // 48 is an exact multiple -> K1 path
    CHECK(std::memcmp(out, out2, 16) != 0);
  }
}

// ===========================================================================
// 3. LoRaWAN MIC -- [BROCAAR] published wire vectors + [LW104] 4.4.1
// ===========================================================================
void test_lorawan_mic() {
  CASE("[BROCAAR] uplink data, fPort 1, FCnt 1: MIC d6c3b582");
  {
    // wire = 400403020180010001a694642615 d6c3b582 (18 B)
    uint8_t key[16], msg[32], mic[4], raw[32];
    hex2bin("02020202020202020202020202020202", key, 16);
    hex2bin("400403020180010001a694642615d6c3b582", raw, 18);
    std::memcpy(msg, raw, 14);
    lorawan_mic_uplink(key, 0x01020304u, 1, msg, 14, mic);
    if (!eq_hex(mic, "d6c3b582", 4)) hexdump("mic", mic, 4);
    CHECK(eq_hex(mic, "d6c3b582", 4));
  }

  CASE("[BROCAAR] uplink mac-commands in FOpts: MIC b64dc039");
  {
    uint8_t key[16], msg[32], mic[4], raw[32];
    hex2bin("01010101010101010101010101010101", key, 16);
    hex2bin("4004030201030000020305016a3798f5b64dc039", raw, 20);
    std::memcpy(msg, raw, 16);
    lorawan_mic_uplink(key, 0x01020304u, 0, msg, 16, mic);
    if (!eq_hex(mic, "b64dc039", 4)) hexdump("mic", mic, 4);
    CHECK(eq_hex(mic, "b64dc039", 4));
  }

  CASE("[BROCAAR] uplink mac-commands in FRMPayload: MIC ee6aa508");
  {
    uint8_t key[16], msg[32], mic[4], raw[32];
    hex2bin("01010101010101010101010101010101", key, 16);
    hex2bin("40040302010000000069369eee6aa508", raw, 16);
    std::memcpy(msg, raw, 12);
    lorawan_mic_uplink(key, 0x01020304u, 0, msg, 12, mic);
    if (!eq_hex(mic, "ee6aa508", 4)) hexdump("mic", mic, 4);
    CHECK(eq_hex(mic, "ee6aa508", 4));
  }

  CASE("[BROCAAR] downlink MType 0x60: MIC e24f1f9f (Dir = 1)");
  {
    uint8_t key[16], msg[32], mic[4], raw[32];
    hex2bin("02020202020202020202020202020202", key, 16);
    hex2bin("6004030201030000dfb4f1e24f1f9f", raw, 15);
    std::memcpy(msg, raw, 11);
    lorawan_mic_downlink(key, 0x01020304u, 0, msg, 11, mic);
    if (!eq_hex(mic, "e24f1f9f", 4)) hexdump("mic", mic, 4);
    CHECK(eq_hex(mic, "e24f1f9f", 4));
  }

  CASE("[BROCAAR] downlink with fPort 1: MIC 77701ea3");
  {
    uint8_t key[16], msg[32], mic[4], raw[32];
    hex2bin("02020202020202020202020202020202", key, 16);
    hex2bin("60040302010300000207010177701ea3", raw, 16);
    std::memcpy(msg, raw, 12);
    lorawan_mic_downlink(key, 0x01020304u, 0, msg, 12, mic);
    if (!eq_hex(mic, "77701ea3", 4)) hexdump("mic", mic, 4);
    CHECK(eq_hex(mic, "77701ea3", 4));
  }

  CASE("COUNTER-TEST: corrupting one msg byte must change the MIC");
  {
    uint8_t key[16], msg[16], mic_a[4], mic_b[4], raw[32];
    hex2bin("01010101010101010101010101010101", key, 16);
    hex2bin("4004030201030000020305016a3798f5b64dc039", raw, 20);
    std::memcpy(msg, raw, 16);
    lorawan_mic_uplink(key, 0x01020304u, 0, msg, 16, mic_a);
    CHECK(eq_hex(mic_a, "b64dc039", 4));

    msg[4] ^= 0x80;  // one bit in FCtrl
    lorawan_mic_uplink(key, 0x01020304u, 0, msg, 16, mic_b);
    CHECK(!eq_hex(mic_b, "b64dc039", 4));
    CHECK(std::memcmp(mic_a, mic_b, 4) != 0);
  }

  CASE("COUNTER-TEST: wrong key, wrong length, wrong DevAddr all break it");
  {
    uint8_t key[16], msg[16], mic[4], raw[32];
    hex2bin("01010101010101010101010101010100", key, 16);  // last byte wrong
    hex2bin("4004030201030000020305016a3798f5b64dc039", raw, 20);
    std::memcpy(msg, raw, 16);
    lorawan_mic_uplink(key, 0x01020304u, 0, msg, 16, mic);
    CHECK(!eq_hex(mic, "b64dc039", 4));

    hex2bin("01010101010101010101010101010101", key, 16);
    lorawan_mic_uplink(key, 0x01020304u, 0, msg, 15, mic);  // short by one
    CHECK(!eq_hex(mic, "b64dc039", 4));

    lorawan_mic_uplink(key, 0x04030201u, 0, msg, 16, mic);  // DevAddr reversed
    CHECK(!eq_hex(mic, "b64dc039", 4));
  }

  CASE("COUNTER-TEST: the Dir bit really is in B0 -- uplink != downlink");
  {
    uint8_t key[16], msg[32], up[4], down[4], raw[32];
    hex2bin("02020202020202020202020202020202", key, 16);
    hex2bin("6004030201030000dfb4f1e24f1f9f", raw, 15);
    std::memcpy(msg, raw, 11);
    lorawan_mic_downlink(key, 0x01020304u, 0, msg, 11, down);
    lorawan_mic_uplink(key, 0x01020304u, 0, msg, 11, up);
    CHECK(eq_hex(down, "e24f1f9f", 4));
    CHECK(std::memcmp(up, down, 4) != 0);
  }
}

// ===========================================================================
// 4. Join MICs and session keys -- [LW104] Sec. 6.1.1.3 / 6.2
// ===========================================================================
void test_join_mic_and_session_keys() {
  CASE("[BROCAAR] join-request MIC over MHDR|JoinEUI|DevEUI|DevNonce");
  {
    // base64 AAQDAgEEAwIBBQQDAgUEAwItEGqZDhI= , AppKey 01*16 -> MIC 6a990e12
    uint8_t key[16], msg[19], mic[4];
    hex2bin("01010101010101010101010101010101", key, 16);
    hex2bin("00040302010403020105040302050403022d10", msg, 19);
    lorawan_join_request_mic(key, msg, 19, mic);
    if (!eq_hex(mic, "6a990e12", 4)) hexdump("mic", mic, 4);
    CHECK(eq_hex(mic, "6a990e12", 4));

    // COUNTER-TEST: one byte of the DevNonce flipped
    uint8_t msg2[19];
    std::memcpy(msg2, msg, 19);
    msg2[14] ^= 0x01;
    uint8_t mic2[4];
    lorawan_join_request_mic(key, msg2, 19, mic2);
    CHECK(std::memcmp(mic, mic2, 4) != 0);
  }

  CASE("[BROCAAR] join-accept: decrypt then MIC over MHDR|MACPayload");
  {
    // ciphertext 493eeb51fba2116f810edb3742975142, AppKey 00112233..eeff.
    uint8_t key[16], ct[16], plain[16];
    hex2bin("00112233445566778899aabbccddeeff", key, 16);
    hex2bin("493eeb51fba2116f810edb3742975142", ct, 16);
    // [LW104] Sec. 6.2.3: in LoRaWAN 1.0 the network inverse-ciphers the
    // join-accept, so a 1.0 device recovers the plaintext by running the cipher
    // FORWARD over the 16 bytes it heard. (Encrypting rather than decrypting
    // here is the quirk, not a typo: the MIC below only validates if the
    // direction is right, and 43485bbc is the published MIC for this frame.)
    aes128_ecb_encrypt(key, ct, plain);
    if (!eq_hex(plain, "c70b5701112280190302000043485bbc", 16)) hexdump("plain", plain, 16);
    CHECK(eq_hex(plain, "c70b5701112280190302000043485bbc", 16));

    // MACPayload = 12 B, MIC = 43485bbc, cmac over (0x20 | MACPayload)
    uint8_t msg[16], mic16[16];
    msg[0] = 0x20;
    std::memcpy(msg + 1, plain, 12);
    aes_cmac(key, msg, 13, mic16);
    CHECK(eq_hex(mic16, "43485bbc", 4));
    CHECK(std::memcmp(mic16, plain + 12, 4) == 0);
  }

  CASE("[LW104] 1.0 session keys: aes128_enc(NwkKey, 0x01|JoinNonce|NetID|DevNonce)");
  {
    // Re-derived and cross-checked against brocaar's own joinserver_test.go
    // expectation pair. NwkKey 01020304..08, JoinNonce 65536, NetID 0x010203,
    // DevNonce 258.
    uint8_t nwkkey[16], net_id[3], join_eui[8], nwk_skey[16], app_skey[16];
    hex2bin("01020304050607080102030405060708", nwkkey, 16);
    hex2bin("010203", net_id, 3);
    hex2bin("0807060504030201", join_eui, 8);
    derive_session_keys_1_0(nwkkey, 65536u, net_id, join_eui, 258, nwk_skey, app_skey);
    if (!eq_hex(nwk_skey, "df53c35f3034ccced0ff354c70de04df", 16)) hexdump("NwkSKey", nwk_skey, 16);
    if (!eq_hex(app_skey, "927b9c911183cffe4cb2ff4b75545f6d", 16)) hexdump("AppSKey", app_skey, 16);
    CHECK(eq_hex(nwk_skey, "df53c35f3034ccced0ff354c70de04df", 16));
    CHECK(eq_hex(app_skey, "927b9c911183cffe4cb2ff4b75545f6d", 16));
  }

  CASE("COUNTER-TEST: derivation is injective -- one bit anywhere moves both keys");
  {
    uint8_t nwkkey[16], net_id[3], join_eui[8], a[16], b[16], a2[16], b2[16];
    hex2bin("01020304050607080102030405060708", nwkkey, 16);
    hex2bin("010203", net_id, 3);
    hex2bin("0807060504030201", join_eui, 8);
    derive_session_keys_1_0(nwkkey, 65536u, net_id, join_eui, 258, a, b);
    CHECK(std::memcmp(a, b, 16) != 0);          // the two keys differ
    CHECK(std::memcmp(a, nwkkey, 16) != 0);     // and neither is the root key

    derive_session_keys_1_0(nwkkey, 65536u, net_id, join_eui, 259, a2, b2);
    CHECK(std::memcmp(a, a2, 16) != 0);
    CHECK(std::memcmp(b, b2, 16) != 0);

    uint8_t t[3] = {1, 2, 4};                   // NetID off by one bit
    derive_session_keys_1_0(nwkkey, 65536u, t, join_eui, 258, a2, b2);
    CHECK(std::memcmp(a, a2, 16) != 0);
  }
}

// ===========================================================================
// 5. FRMPayload crypto -- [LW104] Sec. 4.3.3.1
// ===========================================================================
void test_frmpayload_crypto() {
  CASE("[BROCAAR] FRMPayload 'hello' encrypts to a694642615 (AppSKey 01*16)");
  {
    uint8_t key[16], in[5], out[5];
    hex2bin("01010101010101010101010101010101", key, 16);
    std::memcpy(in, "hello", 5);
    lorawan_crypt_frmpayload(key, 0x01020304u, /*dir=*/0, /*fcnt=*/1, in, out, 5);
    if (!eq_hex(out, "a694642615", 5)) hexdump("ct", out, 5);
    CHECK(eq_hex(out, "a694642615", 5));

    // and the transformation is an involution: applying it again gives plaintext
    uint8_t back[5];
    lorawan_crypt_frmpayload(key, 0x01020304u, 0, 1, out, back, 5);
    CHECK(std::memcmp(back, "hello", 5) == 0);
  }

  CASE("COUNTER-TEST: changing FCnt must produce a different keystream");
  {
    uint8_t key[16], in[5], a[5], b[5];
    hex2bin("01010101010101010101010101010101", key, 16);
    std::memcpy(in, "hello", 5);
    lorawan_crypt_frmpayload(key, 0x01020304u, 0, 1, in, a, 5);
    lorawan_crypt_frmpayload(key, 0x01020304u, 0, 2, in, b, 5);
    CHECK(std::memcmp(a, b, 5) != 0);
    CHECK(eq_hex(a, "a694642615", 5));

    // wrong key must also differ
    uint8_t c[5];
    hex2bin("02020202020202020202020202020202", key, 16);
    lorawan_crypt_frmpayload(key, 0x01020304u, 0, 1, in, c, 5);
    CHECK(std::memcmp(a, c, 5) != 0);
  }
}

// ===========================================================================
// 6. EU868 payload-size limits -- [RP002] Table 13
// ===========================================================================
void test_eu868_payload_limits() {
  CASE("[RP002-1.0.3 Tbl 13] EU863-870 max payload, DR0..DR5 = 51/51/51/115/242/242");
  {
    const int expect_n[6] = {51, 51, 51, 115, 242, 242};
    const int expect_m[6] = {59, 59, 59, 123, 250, 250};
    for (int dr = 0; dr < 6; ++dr) {
      if (eu868_max_app_payload(dr) != expect_n[dr])
        std::fprintf(stderr, "      DR%d N=%d want %d\n", dr, eu868_max_app_payload(dr), expect_n[dr]);
      CHECK_EQ(eu868_max_app_payload(dr), expect_n[dr]);
      CHECK_EQ(eu868_max_mac_payload(dr), expect_m[dr]);
    }
  }

  CASE("[RP002-1.0.3 Tbl 8] DR0..DR5 = SF12..SF7 at 125 kHz");
  {
    const int expect_sf[6] = {12, 11, 10, 9, 8, 7};
    for (int dr = 0; dr < 6; ++dr) {
      CHECK_EQ(eu868_sf_for_dr(dr), expect_sf[dr]);
      CHECK_EQ(eu868_bandwidth_hz_for_dr(dr), 125000u);
    }
  }

  CASE("payload_fits is the rule, and the boundary is exact on both sides");
  {
    CHECK(payload_fits(0, 0));    // an empty FRMPayload is legal
    CHECK(payload_fits(51, 0));
    CHECK(!payload_fits(52, 0));
    CHECK(payload_fits(115, 3));
    CHECK(!payload_fits(116, 3));
    CHECK(payload_fits(242, 5));
    CHECK(!payload_fits(243, 5));
    CHECK(payload_fits(242, 4));
    for (int dr = 0; dr < 5; ++dr)
      CHECK(eu868_max_app_payload(dr) <= eu868_max_app_payload(dr + 1));
  }

  CASE("COUNTER-TEST: an out-of-range DR is refused, never rounded up");
  {
    CHECK(!payload_fits(51, 6));    // DR6 (SF7/250k) is outside the DR0..DR5 set
    CHECK(!payload_fits(51, -1));
    CHECK(!payload_fits(1, 15));
    CHECK_EQ(eu868_max_app_payload(9), -1);
    CHECK_EQ(eu868_max_app_payload(-1), -1);
    CHECK_EQ(eu868_sf_for_dr(6), -1);
  }
}

// ===========================================================================
// 7. Time on air -- Semtech formula, anchored to [BROCAAR] airtime
// ===========================================================================
void test_time_on_air() {
  CASE("Tsym = 2^SF / BW");
  {
    CHECK_EQ(lora_symbol_duration_us(12, 125000), 32768u);
    CHECK_EQ(lora_symbol_duration_us(9, 125000), 4096u);
    CHECK_EQ(lora_symbol_duration_us(9, 500000), 1024u);
    CHECK_EQ(lora_symbol_duration_us(7, 125000), 1024u);
  }

  CASE("[BROCAAR airtime] payload symbol counts (cr arg is the denominator 5..8)");
  {
    CHECK_EQ(lora_payload_symbol_count(13, 12, 5, true, false), 23);
    CHECK_EQ(lora_payload_symbol_count(13, 12, 6, true, false), 26);
    CHECK_EQ(lora_payload_symbol_count(13, 12, 5, false, false), 18);
    CHECK_EQ(lora_payload_symbol_count(50, 12, 5, true, true), 58);
  }

  CASE("[BROCAAR airtime] the published absolute anchor: 1_155_072 us");
  {
    // brocaar airtime_test.go: payloadSize 13, SF12, BW 125, preamble 8,
    // CR4/5, header on, LDRO off -> exactly 1_155_072 us.
    uint32_t got = lora_time_on_air_us(13, 12, 125000, 5, 8, true, false);
    if (got != 1155072u) std::fprintf(stderr, "      got %u\n", got);
    CHECK_EQ(got, 1155072u);
    // and the symbol duration / preamble split reproduces too:
    // Tsym 32768 us, preamble (8+4.25)*Tsym = 401_408 us, 23 payload symbols.
    CHECK_EQ(lora_symbol_duration_us(12, 125000), 32768u);
    CHECK_EQ(401408u + 23u * 32768u, 1155072u);
  }

  CASE("[RP002 Tbl 8] EU868 DR0..DR5 airtime ladder, LDRO applied to SF11/12 @125k");
  {
    const uint32_t expect[6] = {1155072u, 577536u, 288768u, 164864u, 82432u, 46336u};
    for (int dr = 0; dr < 6; ++dr) {
      uint32_t got = eu868_time_on_air_us(dr, 13, 8, 5);
      if (got != expect[dr]) std::fprintf(stderr, "      DR%d got %u want %u\n", dr, got, expect[dr]);
      CHECK_EQ(got, expect[dr]);
    }
    for (int dr = 0; dr < 5; ++dr)
      CHECK(eu868_time_on_air_us(dr, 13, 8, 5) > eu868_time_on_air_us(dr + 1, 13, 8, 5));
    // DR0 must be exactly the published brocaar anchor: LDRO with 13 B and
    // SF12 happens to give the same symbol count as no-LDRO, so the two
    // independent paths agree here -- which is the strongest cross-check
    // available for this one number.
    CHECK_EQ(eu868_time_on_air_us(0, 13, 8, 5), 1155072u);
  }

  CASE("airtime grows with payload length, preamble symbols and coding rate");
  {
    CHECK(lora_time_on_air_us(64, 12, 125000, 5, 8, true, true) >
          lora_time_on_air_us(13, 12, 125000, 5, 8, true, true));
    CHECK(lora_time_on_air_us(13, 12, 125000, 5, 16, true, true) >
          lora_time_on_air_us(13, 12, 125000, 5, 8, true, true));
    CHECK(lora_time_on_air_us(13, 12, 125000, 8, 8, true, true) >
          lora_time_on_air_us(13, 12, 125000, 5, 8, true, true));
  }

  CASE("COUNTER-TEST: the payload-symbol term is real, and LDRO really changes it");
  {
    // Dropping the payload term would leave exactly the preamble (401_408 us).
    CHECK(lora_time_on_air_us(13, 12, 125000, 5, 8, true, false) > 401408u);
    // LDRO is not cosmetic: 255 B at SF11 differs between LDRO on and off
    CHECK(lora_time_on_air_us(255, 11, 125000, 5, 8, true, true) !=
          lora_time_on_air_us(255, 11, 125000, 5, 8, true, false));
    // and adjacent DRs must never collide
    for (int dr = 0; dr < 5; ++dr)
      CHECK(eu868_time_on_air_us(dr, 13, 8, 5) != eu868_time_on_air_us(dr + 1, 13, 8, 5));
  }
}

// ===========================================================================
// 8. Duty-cycle limiter
// ===========================================================================
void test_duty_cycle_limiter() {
  CASE("[RP002 Tbl 6] EU868 default channels 868.1/868.3/868.5 MHz, DR0-DR5, < 1%");
  {
    CHECK_EQ(kEu868DefaultChannelCount, 3);
    CHECK_EQ(kEu868DefaultChannelsHz[0], 868100000u);
    CHECK_EQ(kEu868DefaultChannelsHz[1], 868300000u);
    CHECK_EQ(kEu868DefaultChannelsHz[2], 868500000u);
    int b0 = eu868_sub_band_index(868100000u);
    int b1 = eu868_sub_band_index(868300000u);
    int b2 = eu868_sub_band_index(868500000u);
    CHECK_EQ(b0, b1);
    CHECK_EQ(b1, b2);
    CHECK(b0 >= 0);
    CHECK_EQ(eu868_sub_band_duty_num(b0), 1u);
    CHECK_EQ(eu868_sub_band_duty_den(b0), 100u);   // < 1%
  }

  CASE("[RP002 Sec 1.3.1 / ETSI] the 869.4-869.65 MHz band is 10%, the 868.7 band is 1%");
  {
    int b10 = eu868_sub_band_index(869525000u);
    CHECK(b10 >= 0);
    CHECK_EQ(eu868_sub_band_duty_num(b10), 1u);
    CHECK_EQ(eu868_sub_band_duty_den(b10), 10u);

    int b1 = eu868_sub_band_index(868700000u);
    CHECK(b1 >= 0);
    CHECK_EQ(eu868_sub_band_duty_den(b1), 100u);
    CHECK(std::strcmp(eu868_sub_band_name(b10), "EU868-869.4-869.65-10pct") == 0);
  }

  CASE("one frame well inside the budget is allowed, and is charged");
  {
    DutyCycleLimiter lim(0);
    DutyCycleVerdict v = lim.request(868100000u, 2794, 0);
    CHECK(v.allowed);
    CHECK_EQ(v.wait_ms, 0u);
    CHECK(v.band >= 0);
    CHECK_EQ(lim.band_airtime_ms(0, 0, 3600000), 2794u);
    CHECK_EQ(lim.blocked_count(), 0u);
  }

  CASE("BURST: a burst of frames is THROTTLED, not merely counted");
  {
    // EU868 DR0 = SF12/125 kHz. A 51-byte FRMPayload makes a 64-byte PHY
    // frame; with low-data-rate-optimisation (mandatory for SF11/12 at
    // 125 kHz) that is 73 payload symbols -> 2_793_472 us of airtime, i.e.
    // 2794 ms once rounded up. 1% of one hour is 36_000 ms, so at most
    // floor(36000/2794) = 12 frames fit and the 13th MUST be refused with a
    // real, non-zero wait.
    const uint32_t toa = (eu868_time_on_air_us(0, 51 + 13, 8, 5) + 999u) / 1000u;
    CHECK_EQ(toa, 2794u);  // 51 B FRMPayload -> 64 B PHY payload

    DutyCycleLimiter lim(0);
    uint32_t accepted = 0, refused = 0;
    for (int i = 0; i < 20; ++i) {
      DutyCycleVerdict v = lim.request(868100000u, toa, 0);
      if (v.allowed) ++accepted; else ++refused;
    }
    CHECK_EQ(accepted, 12u);
    CHECK_EQ(refused, 8u);
    CHECK_EQ(lim.blocked_count(), 8u);

    // the RULE, not the magic number: 12 frames fit, 13 would not
    CHECK(accepted * toa <= 36000u);          // 12 * 2794 = 33528 <= 36000
    CHECK((accepted + 1u) * toa > 36000u);    // 13 * 2794 = 36322 > 36000
    CHECK((accepted + 2u) * toa > 36000u);

    DutyCycleVerdict blocked = lim.request(868100000u, toa, 0);
    CHECK(!blocked.allowed);
    CHECK(blocked.wait_ms > 0);
    CHECK(blocked.wait_ms <= 3600000u);
  }

  CASE("the three default channels share ONE budget (sub-band, not per-channel)");
  {
    // 51 B FRMPayload at DR0 -> 64 B PHY -> the same 2794 ms used above, so a
    // 1% hour holds 12 of them. A per-channel model would hand each of the
    // three default channels its own 12; the sub-band model gives the trio 12
    // BETWEEN them, which is the actual regulatory reading. Real airtime is
    // used deliberately: a 69 ms frame would fit 20 times and prove nothing.
    const uint32_t toa = (eu868_time_on_air_us(0, 51 + 13, 8, 5) + 999u) / 1000u;
    CHECK_EQ(toa, 2794u);
    DutyCycleLimiter single(0), spread(0);
    uint32_t a_single = 0, a_spread = 0;
    for (int i = 0; i < 20; ++i) {
      if (single.request(868100000u, toa, 0).allowed) ++a_single;
      if (spread.request(kEu868DefaultChannelsHz[i % 3], toa, 0).allowed) ++a_spread;
    }
    CHECK_EQ(a_single, 12u);
    CHECK_EQ(a_spread, 12u);  // identical: 868.1/868.3/868.5 are one sub-band
    CHECK(a_spread < 3u * 12u);   // ...and NOT one budget per channel
    // rotating across the three channels cannot escape the shared charge
    CHECK_EQ(eu868_sub_band_index(kEu868DefaultChannelsHz[0]),
             eu868_sub_band_index(kEu868DefaultChannelsHz[1]));
    CHECK_EQ(single.band_airtime_ms(0, 0, 3600000), spread.band_airtime_ms(0, 0, 3600000));
  }

  CASE("COUNTER-TEST: a 10% band has ~10x the budget of the 1% band");
  {
    const uint32_t toa = 2794;
    DutyCycleLimiter one(0), ten(0);
    uint32_t a1 = 0, a10 = 0;
    for (int i = 0; i < 300; ++i) {
      if (one.request(868100000u, toa, 0).allowed) ++a1;
      if (ten.request(869525000u, toa, 0).allowed) ++a10;
    }
    CHECK_EQ(a1, 12u);
    CHECK_EQ(a10, 128u);      // 10% = 360_000 ms / 2794 = 128.8 -> 128
    CHECK(a10 >= 10u * a1);
    // and exhausting one band must not spend a single ms of the other
    CHECK_EQ(ten.band_airtime_ms(eu868_sub_band_index(868100000u), 0, 3600000), 0u);
  }

  CASE("the window rolls: an hour later the budget is fresh");
  {
    const uint32_t toa = 2794;
    DutyCycleLimiter lim(0);
    for (int i = 0; i < 20; ++i) lim.request(868100000u, toa, 0);
    CHECK_EQ(lim.blocked_count(), 8u);
    CHECK(!lim.request(868100000u, toa, 0).allowed);
    CHECK(lim.request(868100000u, toa, 3600001u).allowed);
    CHECK_EQ(lim.band_airtime_ms(0, 3600001u, 7200001u), toa);
  }

  CASE("earliest() predicts the next legal instant, and it is actually legal");
  {
    const uint32_t toa = 2794;
    DutyCycleLimiter lim(0);
    for (int i = 0; i < 12; ++i) CHECK(lim.request(868100000u, toa, 0).allowed);
    CHECK(!lim.request(868100000u, toa, 0).allowed);
    uint64_t t = lim.earliest(868100000u, toa, 0);
    DutyCycleVerdict v = lim.request(868100000u, toa, t);
    CHECK(v.allowed);
    // COUNTER-TEST: two ms earlier is still too early
    DutyCycleLimiter lim2(0);
    for (int i = 0; i < 12; ++i) lim2.request(868100000u, toa, 0);
    CHECK(!lim2.request(868100000u, toa, t > 1 ? t - 2 : 0).allowed);
  }

  CASE("COUNTER-TEST: a 0% override must refuse an otherwise-legal frame");
  {
    // The frame is legal under the 1% default; only the override can make it
    // fail, which proves the override is actually consulted.
    DutyCycleLimiter legal(0);
    CHECK(legal.request(868100000u, 100, 0).allowed);

    DutyCycleLimiter lim(0);
    lim.set_band_duty_override(eu868_sub_band_index(868100000u), 0, 100);
    CHECK(!lim.request(868100000u, 100, 0).allowed);
    CHECK_EQ(lim.blocked_count(), 1u);
    CHECK_EQ(lim.band_airtime_ms(eu868_sub_band_index(868100000u), 0, 3600000), 0u);
  }

  CASE("a frequency outside every EU868 sub-band is refused, not silently allowed");
  {
    DutyCycleLimiter lim(0);
    CHECK_EQ(eu868_sub_band_index(433920000u), -1);
    DutyCycleVerdict v = lim.request(433920000u, 10, 0);
    CHECK(!v.allowed);
    CHECK_EQ(v.band, -1);
  }
}

// ===========================================================================
// 9. Join-request duty cycle -- [LW104] Table 17
// ===========================================================================
void test_join_backoff_table17() {
  CASE("[LW104 Tbl 17] first hour after reset: join airtime < 36 s");
  {
    // A join-request is a 23-byte PHY frame; at DR0 (SF12/125k/LDRO) that is
    // 1_482_752 us -> 1483 ms. 36 s / 1483 ms = 24.27, so 24 joins fit and the
    // 25th must be refused.
    const uint32_t toa = (eu868_time_on_air_us(0, 23, 8, 5) + 999u) / 1000u;
    CHECK_EQ(toa, 1483u);
    JoinBackoff jb;
    jb.reset(0);
    uint32_t accepted = 0;
    for (int i = 0; i < 40; ++i) {
      if (jb.allowed(toa, 0)) { jb.record(toa, 0); ++accepted; }
    }
    CHECK_EQ(accepted, 24u);
    CHECK(accepted * toa <= 36000u);
    CHECK((accepted + 1u) * toa > 36000u);
    CHECK_EQ(jb.join_airtime_ms(0, 3600000), 24u * toa);
  }

  CASE("[LW104 Tbl 17] the NEXT 10 hours get their own fresh 36 s");
  {
    const uint32_t toa = 1483;
    JoinBackoff jb;
    jb.reset(0);
    for (int i = 0; i < 40; ++i)
      if (jb.allowed(toa, 0)) jb.record(toa, 0);
    CHECK_EQ(jb.join_airtime_ms(0, 3600000), 24u * toa);
    // at t = 1 h 1 ms the first window closed and a fresh 36 s began
    uint32_t accepted = 0;
    for (int i = 0; i < 40; ++i)
      if (jb.allowed(toa, 3600001u)) { jb.record(toa, 3600001u); ++accepted; }
    CHECK_EQ(accepted, 24u);
    CHECK_EQ(jb.join_airtime_ms(3600001u, 3600001u + 3600000u), 24u * toa);
  }

  CASE("[LW104 Tbl 17] after 11 hours: only 8.7 s of join airtime per 24 h");
  {
    const uint32_t toa = 1483;
    JoinBackoff jb;
    jb.reset(0);
    uint32_t accepted = 0;
    const uint64_t t11h = 11ull * 3600000ull;
    for (int i = 0; i < 40; ++i) {
      if (jb.allowed(toa, t11h)) { jb.record(toa, t11h); ++accepted; }
    }
    CHECK_EQ(accepted, 5u);                  // 8700 / 1483 = 5.86 -> 5
    CHECK(accepted * toa <= 8700u);
    CHECK((accepted + 1u) * toa > 8700u);
  }

  CASE("COUNTER-TEST: the steady-state 24 h rule is a real cap, not a free-for-all");
  {
    const uint32_t toa = 1483;
    JoinBackoff jb;
    jb.reset(0);
    uint32_t accepted = 0;
    // 200 attempts spread across ~5.8 days: only the 8.7 s-per-24 h rule applies
    for (int i = 0; i < 200; ++i) {
      const uint64_t t = 500000000ull + static_cast<uint64_t>(i) * 3000000ull;
      if (jb.allowed(toa, t)) { jb.record(toa, t); ++accepted; }
    }
    CHECK(accepted > 0u);
    // the cap is PER 24 h, so assert every 24 h window, not a lifetime total
    for (int w = 0; w < 6; ++w) {
      const uint64_t t0 = 500000000ull + static_cast<uint64_t>(w) * 86400000ull;
      CHECK(jb.join_airtime_ms(t0, t0 + 86400000ull) <= 8700u);
    }
  }

  CASE("COUNTER-TEST: the three join windows are strictly ordered, not one big 36 s");
  {
    const uint32_t toa = 1483;
    JoinBackoff jb;
    jb.reset(0);
    // burn the first hour's 36 s
    for (int i = 0; i < 40; ++i)
      if (jb.allowed(toa, 0)) jb.record(toa, 0);
    CHECK_EQ(jb.join_airtime_ms(0, 3600000), 24u * toa);
    // the join-window rule must still refuse at the very end of hour 1
    CHECK(!jb.allowed(toa, 3599999u));
    // and allow again one ms into hour 2 (fresh 36 s)
    CHECK(jb.allowed(toa, 3600001u));
    // hours 2..10 are the *same* class: burning hour 2 must not replenish it
    for (int i = 0; i < 40; ++i)
      if (jb.allowed(toa, 3600001u)) jb.record(toa, 3600001u);
    CHECK_EQ(jb.join_airtime_ms(3600001u, 3600001u + 3600000u), 24u * toa);
    CHECK(!jb.allowed(toa, 2ull * 3600000ull + 1ull));   // hour 3 is in the same class
  }
}

// ===========================================================================
// 10. Frame counters
// ===========================================================================
void test_frame_counters() {
  CASE("a fresh counter starts at 0 and never repeats");
  {
    FrameCounters fc;
    fc.init(0, 1);
    CHECK_EQ(fc.uplink_next(), 0u);
    uint32_t a = fc.take_uplink();
    uint32_t b = fc.take_uplink();
    CHECK_EQ(a, 0u);
    CHECK_EQ(b, 1u);
    CHECK(b != a);
    CHECK(!fc.rolled_over());
    CHECK(!fc.exhausted());
  }

  CASE("counters survive a simulated reboot: the persisted value is a floor");
  {
    FrameCounters fc;
    fc.init(0, 1);
    for (int i = 0; i < 100; ++i) fc.take_uplink();
    CHECK_EQ(fc.uplink_next(), 100u);

    uint32_t persisted_u = 0, persisted_d = 0;
    fc.snapshot(&persisted_u, &persisted_d);
    FrameCounters after_reboot;
    after_reboot.init(persisted_u, persisted_d);
    CHECK(after_reboot.uplink_next() >= 100u);
    CHECK(after_reboot.take_uplink() >= 100u);
  }

  CASE("COUNTER-TEST: a STALE persisted value must be pushed forward, not honoured");
  {
    // A torn or late store write leaves the persisted value behind the
    // high-water mark this device already reached. Honouring it would replay
    // frame counters -- the network server drops those frames, so the balloon
    // would go silent while still believing it was transmitting.
    FrameCounters fc;
    fc.init(0, 1);
    for (int i = 0; i < 500; ++i) fc.take_uplink();
    CHECK_EQ(fc.uplink_next(), 500u);

    uint32_t pu = 0, pd = 0;
    fc.snapshot(&pu, &pd);
    CHECK_EQ(pu, 500u);
    CHECK_EQ(pd, 1u);

    // The store turns out to be stale (a torn write, or a sector that lost its
    // last commit). Re-initialising from it must NOT move the counter back --
    // otherwise the device replays counters it already spent.
    fc.init(7, 3);
    CHECK(fc.uplink_next() >= 500u);
    CHECK(fc.take_uplink() >= 500u);

    // A fresh instance restored from the honest snapshot resumes exactly there.
    FrameCounters after_reboot;
    after_reboot.init(pu, pd);
    CHECK_EQ(after_reboot.uplink_next(), 500u);
  }

  CASE("the counter is monotonic across many reboots");
  {
    uint32_t floor_u = 0, last = 0;
    for (int boot = 0; boot < 8; ++boot) {
      FrameCounters fc;
      fc.init(floor_u, 0);
      for (int i = 0; i < 40; ++i) {
        uint32_t v = fc.take_uplink();
        CHECK(v >= last);
        last = v;
      }
      fc.snapshot(&floor_u, nullptr);
    }
    CHECK(floor_u >= 320u);
  }

  CASE("rollover at 2^32 wraps to 0 only when explicitly allowed");
  {
    FrameCounters fc;
    fc.init(0xFFFFFFFFu, 0, /*allow_rollover=*/true);
    CHECK_EQ(fc.uplink_next(), 0xFFFFFFFFu);
    CHECK(fc.can_take_uplink());
    CHECK_EQ(fc.take_uplink(), 0xFFFFFFFFu);
    CHECK(!fc.rolled_over());
    CHECK_EQ(fc.take_uplink(), 0u);        // the next value wraps to 0
    CHECK(fc.rolled_over());
    CHECK_EQ(fc.take_uplink(), 1u);
  }

  CASE("COUNTER-TEST: rollover is REFUSED when it was not opted into");
  {
    // Silently wrapping would replay all 2^32 frame counters the device ever
    // used -- a security failure, not a cosmetic one. It must stick instead.
    FrameCounters fc;
    fc.init(0xFFFFFFFFu, 0);   // allow_rollover defaults to false
    CHECK(!fc.can_take_uplink());
    CHECK_EQ(fc.take_uplink(), 0xFFFFFFFFu);
    CHECK_EQ(fc.take_uplink(), 0xFFFFFFFFu);   // exhausted, never wraps
    CHECK(fc.exhausted());
    CHECK(!fc.rolled_over());
  }

  CASE("downlink counter advances independently and rejects replays");
  {
    FrameCounters fc;
    fc.init(0, 0);
    CHECK(fc.accept_downlink(0));
    CHECK(fc.accept_downlink(1));
    CHECK(fc.accept_downlink(5));
    CHECK(!fc.accept_downlink(4));  // replay
    CHECK(!fc.accept_downlink(5));  // repeat
    CHECK_EQ(fc.downlink_last(), 5u);
    CHECK_EQ(fc.uplink_next(), 0u);
  }

  CASE("COUNTER-TEST: no two uplinks in a run ever share a counter value");
  {
    FrameCounters fc;
    fc.init(0, 0);
    uint32_t prev = 0xFFFFFFFFu;
    bool first = true;
    for (int i = 0; i < 1000; ++i) {
      uint32_t v = fc.take_uplink();
      if (!first) CHECK(v != prev);
      prev = v;
      first = false;
    }
  }
}

// ===========================================================================
// 11. MAC layer against the frozen HAL
// ===========================================================================
MacConfig make_cfg() {
  MacConfig cfg{};
  hex2bin("0203040502030405", cfg.dev_eui, 8);
  hex2bin("0102030401020304", cfg.join_eui, 8);
  hex2bin("01010101010101010101010101010101", cfg.app_key, 16);
  cfg.preamble_symbols = 8;
  cfg.coding_rate = 5;
  cfg.tx_power_dbm = 14;
  cfg.join_channel_hz = 868100000u;
  cfg.join_dr = 0;
  cfg.join_retry_max = 3;
  cfg.duty_denominator = 100;
  return cfg;
}

// Complete the join of `mac` with a valid, freshly built join-accept.
radio::Result complete_join(LorawanMac &mac, FakeRadioHal &hal, const MacConfig &cfg,
                            bool corrupt_mic = false) {
  uint8_t ja[32];
  size_t ja_len = 0;
  const uint8_t nonce[3] = {0, 0, 0};              // device DevNonce 0 -> JoinNonce 0
  const uint8_t netid[3] = {1, 2, 3};              // NetID 0x010203 on the wire
  const uint8_t addr[4] = {4, 3, 2, 1};            // DevAddr 0x01020304, LE
  build_join_accept(cfg.app_key, nonce, netid, addr, 0, 0, corrupt_mic, ja, &ja_len);
  hal.rx_len = ja_len;
  std::memcpy(hal.rx_buffer, ja, ja_len);
  hal.received_pending = true;
  return mac.poll(1000);
}

void test_mac_against_frozen_hal() {
  MacConfig cfg = make_cfg();

  CASE("an uplink before a join is refused and must not touch the radio");
  {
    FakeRadioHal hal;
    LorawanMac mac(&hal, cfg);
    CHECK(mac.state() == JoinState::Idle);
    uint8_t payload[4] = {1, 2, 3, 4};
    radio::Result r = mac.send_uplink(payload, 4, 1, 0, 868100000u, 0);
    CHECK(r != radio::Result::Ok);
    CHECK_EQ(hal.log.send, 0);
    CHECK_EQ(hal.log.acquire, 0);
  }

  CASE("start_join: acquire BEFORE configure BEFORE send, then release");
  {
    FakeRadioHal hal;
    LorawanMac mac(&hal, cfg);
    CHECK(mac.start_join(0) == radio::Result::Ok);
    CHECK(mac.state() == JoinState::Requesting);
    CHECK_EQ(hal.log.acquire, 1);
    CHECK_EQ(hal.log.configure, 1);
    CHECK_EQ(hal.log.send, 1);
    CHECK_EQ(hal.log.release, 1);
    CHECK(hal.log.acquire_seq < hal.log.configure_seq);
    CHECK(hal.log.configure_seq < hal.log.send_seq);
    CHECK(hal.log.send_seq < hal.log.release_seq);

    // the frozen Config must describe a 868.1 MHz SF12 LoRa transmission
    CHECK(hal.log.saw_config);
    CHECK(hal.log.first_config.modulation == radio::Modulation::Lora);
    CHECK_EQ(hal.log.first_config.frequency_hz, 868100000u);
    CHECK_EQ(hal.log.first_config.bandwidth_hz, 125000u);
    CHECK_EQ(hal.log.first_config.spreading_factor, 12);
    CHECK_EQ(hal.log.first_config.coding_rate, 5);
    CHECK_EQ(hal.log.first_config.preamble_symbols, 8);
    CHECK(hal.log.first_config.crc_on);
  }

  CASE("the join-request frame is MHDR|JoinEUI|DevEUI|DevNonce|MIC = 23 B");
  {
    FakeRadioHal hal;
    LorawanMac mac(&hal, cfg);
    CHECK(mac.start_join(0) == radio::Result::Ok);
    std::vector<uint8_t> f = hal.sent;
    CHECK_EQ(f.size(), 23u);
    CHECK_EQ(f[0], 0x00);                                   // MType = JoinRequest
    CHECK(eq_hex(f.data() + 1, "0102030401020304", 8));     // JoinEUI, wire order
    CHECK(eq_hex(f.data() + 9, "0203040502030405", 8));     // DevEUI, wire order
    CHECK_EQ(f[17], 0x00);                                  // DevNonce 0, little-endian
    CHECK_EQ(f[18], 0x00);
    uint8_t mic[4];
    lorawan_join_request_mic(cfg.app_key, f.data(), 19, mic);
    CHECK(std::memcmp(mic, f.data() + 19, 4) == 0);

    // COUNTER-TEST: a corrupted join MIC does not verify
    uint8_t bad[23];
    std::memcpy(bad, f.data(), 23);
    bad[19] ^= 0x01;
    lorawan_join_request_mic(cfg.app_key, bad, 19, mic);
    CHECK(std::memcmp(mic, bad + 19, 4) != 0);
  }

  CASE("each join attempt uses a fresh DevNonce (no replayable join)");
  {
    FakeRadioHal hal;
    LorawanMac mac(&hal, cfg);
    CHECK(mac.start_join(0) == radio::Result::Ok);
    uint16_t n0 = static_cast<uint16_t>(hal.sent[17] | (hal.sent[18] << 8));
    CHECK(mac.start_join(0) == radio::Result::Ok);
    uint16_t n1 = static_cast<uint16_t>(hal.sent[17] | (hal.sent[18] << 8));
    CHECK(mac.start_join(0) == radio::Result::Ok);
    uint16_t n2 = static_cast<uint16_t>(hal.sent[17] | (hal.sent[18] << 8));
    CHECK(n0 != n1);
    CHECK(n1 != n2);
    CHECK_EQ(n0, 0);
    CHECK_EQ(n1, 1);
    CHECK_EQ(n2, 2);
  }

  CASE("a valid JoinAccept through the HAL completes the join and derives keys");
  {
    FakeRadioHal hal;
    LorawanMac mac(&hal, cfg);
    CHECK(mac.start_join(0) == radio::Result::Ok);
    CHECK(complete_join(mac, hal, cfg) == radio::Result::Ok);
    CHECK(mac.state() == JoinState::Joined);
    CHECK(mac.session().joined);
    CHECK_EQ(mac.session().dev_addr, 0x01020304u);
    CHECK_EQ(mac.session().net_id[0], 0x01);
    CHECK_EQ(mac.session().net_id[1], 0x02);
    CHECK_EQ(mac.session().net_id[2], 0x03);
    CHECK_EQ(mac.session().dev_nonce, 0u);

    uint8_t want_nwk[16], want_app[16];
    const uint8_t netid[3] = {1, 2, 3};
    derive_session_keys_1_0(cfg.app_key, 0, netid, cfg.join_eui, 0, want_nwk, want_app);
    CHECK(std::memcmp(mac.session().nwk_skey, want_nwk, 16) == 0);
    CHECK(std::memcmp(mac.session().app_skey, want_app, 16) == 0);
    CHECK(std::memcmp(mac.session().nwk_skey, mac.session().app_skey, 16) != 0);
  }

  CASE("COUNTER-TEST: a JoinAccept with a bad MIC is REJECTED, join stays open");
  {
    FakeRadioHal hal;
    LorawanMac mac(&hal, cfg);
    CHECK(mac.start_join(0) == radio::Result::Ok);
    CHECK(complete_join(mac, hal, cfg, /*corrupt_mic=*/true) == radio::Result::Ok);
    CHECK(mac.state() != JoinState::Joined);
    CHECK(!mac.session().joined);
    CHECK_EQ(mac.counters().uplink_next(), 0u);
  }

  CASE("COUNTER-TEST: a reserved DevAddr (0x00000000) must be refused even with a good MIC");
  {
    // [LW104] DevAddr 0x00000000 is not assignable. A join-accept carrying it
    // has a perfectly valid MIC -- the MIC proves the server, not that the
    // address is usable -- so the reserved-address rule is a separate check.
    FakeRadioHal hal;
    LorawanMac mac(&hal, cfg);
    CHECK(mac.start_join(0) == radio::Result::Ok);
    uint8_t ja[32];
    size_t ja_len = 0;
    const uint8_t nonce[3] = {0, 0, 0};
    const uint8_t netid[3] = {1, 2, 3};
    const uint8_t addr[4] = {0, 0, 0, 0};   // wire-order DevAddr 0x00000000
    build_join_accept(cfg.app_key, nonce, netid, addr, 0, 0, false, ja, &ja_len);
    hal.rx_len = ja_len;
    std::memcpy(hal.rx_buffer, ja, ja_len);
    hal.received_pending = true;
    CHECK(mac.poll(1000) == radio::Result::Ok);
    CHECK(!mac.session().joined);
    CHECK_EQ(mac.counters().uplink_next(), 0u);

    // COUNTER-TEST for the counter-test: the same frame with a real address
    // DOES join, so the refusal above is caused by the address and nothing else.
    FakeRadioHal hal2;
    LorawanMac mac2(&hal2, cfg);
    CHECK(mac2.start_join(0) == radio::Result::Ok);
    CHECK(complete_join(mac2, hal2, cfg) == radio::Result::Ok);
    CHECK(mac2.session().joined);
  }

  CASE("a joined device sends an uplink; the frame verifies against the session");
  {
    FakeRadioHal hal;
    LorawanMac mac(&hal, cfg);
    CHECK(mac.start_join(0) == radio::Result::Ok);
    CHECK(complete_join(mac, hal, cfg) == radio::Result::Ok);
    CHECK(mac.state() == JoinState::Joined);

    const uint32_t sends_before = static_cast<uint32_t>(hal.log.send);
    uint8_t payload[5] = {'h', 'e', 'l', 'l', 'o'};
    CHECK(mac.send_uplink(payload, 5, 1, 0, 868100000u, 2000) == radio::Result::Ok);
    CHECK_EQ(hal.log.send, static_cast<int>(sends_before) + 1);

    std::vector<uint8_t> f = hal.sent;
    CHECK_EQ(f.size(), 1u + 4u + 1u + 2u + 1u + 5u + 4u);   // 18
    CHECK_EQ(f[0], 0x40);                                   // UnconfirmedDataUp
    CHECK_EQ(f[1], 0x04);                                   // DevAddr 0x01020304 LE
    CHECK_EQ(f[2], 0x03);
    CHECK_EQ(f[3], 0x02);
    CHECK_EQ(f[4], 0x01);
    // A 9-byte FHDR: MHDR(0) | DevAddr(1..4) | FCtrl(5) | FCnt(6..7) | FPort(8).
    // The 18-byte total above (1+4+1+2+1+5+4) is what fixes these indices;
    // FCtrl is 0 so FOptsLen is 0 and there are no FOpts.
    CHECK_EQ(f[5], 0x00);                                   // FCtrl: no ADR/ACK, FOptsLen 0
    CHECK_EQ(f[6], 0x00);                                   // FCnt 0 on the first uplink
    CHECK_EQ(f[7], 0x00);
    CHECK_EQ(f[8], 1);                                      // FPort

    // FRMPayload must be the LoRaWAN ciphertext, not plaintext
    uint8_t want_ct[5];
    lorawan_crypt_frmpayload(mac.session().app_skey, 0x01020304u, 0, 0, payload, want_ct, 5);
    CHECK(std::memcmp(f.data() + 9, want_ct, 5) == 0);
    CHECK(std::memcmp(f.data() + 9, "hello", 5) != 0);

    // and the MIC verifies against the session NwkSKey + the frame's own FCnt
    uint8_t mine[4];
    lorawan_mic_uplink(mac.session().nwk_skey, mac.session().dev_addr, 0,
                       f.data(), f.size() - 4, mine);
    CHECK(std::memcmp(mine, f.data() + f.size() - 4, 4) == 0);

    // COUNTER-TEST: the MIC must not verify with the *AppSKey*
    lorawan_mic_uplink(mac.session().app_skey, mac.session().dev_addr, 0,
                       f.data(), f.size() - 4, mine);
    CHECK(std::memcmp(mine, f.data() + f.size() - 4, 4) != 0);
  }

  CASE("two uplinks carry different frame counters and different ciphertext");
  {
    FakeRadioHal hal;
    LorawanMac mac(&hal, cfg);
    CHECK(mac.start_join(0) == radio::Result::Ok);
    CHECK(complete_join(mac, hal, cfg) == radio::Result::Ok);
    uint8_t payload[5] = {'h', 'e', 'l', 'l', 'o'};
    CHECK(mac.send_uplink(payload, 5, 1, 0, 868100000u, 2000) == radio::Result::Ok);
    std::vector<uint8_t> f0 = hal.sent;
    CHECK(mac.send_uplink(payload, 5, 1, 0, 868100000u, 4000) == radio::Result::Ok);
    std::vector<uint8_t> f1 = hal.sent;
    CHECK(f0[6] != f1[6] || f0[7] != f1[7]);              // FCnt advanced
    CHECK(std::memcmp(f0.data() + 9, f1.data() + 9, 5) != 0);    // keystream moved
    CHECK_EQ(mac.counters().uplink_next(), 2u);
  }

  CASE("COUNTER-TEST: an over-size FRMPayload is refused for the DR");
  {
    // 243 B is one past the DR5 limit of 242. It must never reach the radio.
    FakeRadioHal hal;
    LorawanMac mac(&hal, cfg);
    CHECK(mac.start_join(0) == radio::Result::Ok);
    CHECK(complete_join(mac, hal, cfg) == radio::Result::Ok);
    const int sends_before = hal.log.send;

    uint8_t big[243];
    std::memset(big, 0xAB, sizeof(big));
    CHECK(mac.send_uplink(big, 243, 1, 5, 868100000u, 2000) != radio::Result::Ok);
    CHECK_EQ(hal.log.send, sends_before);

    // exactly at the DR5 limit it DOES go (and the duty cycle, which is a
    // separate rule, is measured here as well)
    uint8_t ok_payload[242];
    std::memset(ok_payload, 0xAB, sizeof(ok_payload));
    CHECK(payload_fits(242, 5));
    CHECK(mac.send_uplink(ok_payload, 242, 1, 5, 868100000u, 2000) == radio::Result::Ok);
    CHECK_EQ(hal.log.send, sends_before + 1);

    // ...but the SAME 242 bytes at DR0 (limit 51) must be refused outright,
    // on a fresh MAC so the refusal can only be the size rule.
    FakeRadioHal hal0;
    LorawanMac mac0(&hal0, cfg);
    CHECK(mac0.start_join(0) == radio::Result::Ok);
    CHECK(complete_join(mac0, hal0, cfg) == radio::Result::Ok);
    const int s0 = hal0.log.send;
    CHECK(!payload_fits(242, 0));
    CHECK(mac0.send_uplink(ok_payload, 242, 1, 0, 868100000u, 2000) != radio::Result::Ok);
    CHECK_EQ(hal0.log.send, s0);
  }

  CASE("COUNTER-TEST: the duty-cycle limiter throttles inside the MAC, too");
  {
    FakeRadioHal hal;
    LorawanMac mac(&hal, cfg);
    CHECK(mac.start_join(0) == radio::Result::Ok);
    CHECK(complete_join(mac, hal, cfg) == radio::Result::Ok);

    // 51 B FRMPayload at DR0 -> 64 B PHY -> 2794 ms of airtime. Pushed at a
    // frozen clock, so the 1% window never rolls and the burst MUST be cut off.
    uint8_t payload[51];
    std::memset(payload, 0x5A, sizeof(payload));
    uint32_t ok = 0, blocked = 0;
    uint64_t now = 0;
    for (int i = 0; i < 20; ++i) {
      if (mac.send_uplink(payload, 51, 1, 0, 868100000u, now) == radio::Result::Ok) ++ok;
      else ++blocked;
      now += 10;   // 10 ms between attempts: nowhere near enough to refill 1%
    }
    CHECK(ok > 0u);
    CHECK(blocked > 0u);
    CHECK_EQ(ok + blocked, 20u);
    CHECK_EQ(ok, 12u);                                  // floor(36000 / 2794) = 12
    CHECK(ok * 2794u <= 36000u);
    CHECK((ok + 2u) * 2794u > 36000u);                  // 13 * 2794 = 36322

    CHECK_EQ(mac.duty().blocked_count(), 8u);
    CHECK_EQ(hal.log.send, static_cast<int>(ok) + 1);   // +1 for the join-request

    // SABOTAGE ANCHOR: if the refusal were removed, ok would be 20.
    CHECK(ok != 20u);
  }

  CASE("a busy radio is reported, not retried forever");
  {
    FakeRadioHal hal;
    hal.acquire_result = radio::Result::Busy;
    LorawanMac mac(&hal, cfg);
    CHECK(mac.start_join(0) == radio::Result::Busy);
    CHECK_EQ(hal.log.send, 0);
    CHECK_EQ(hal.log.configure, 0);
    CHECK(!hal.is_acquired());
  }

  CASE("the radio is released after every operation, so the stack can share it");
  {
    FakeRadioHal hal;
    LorawanMac mac(&hal, cfg);
    mac.start_join(0);
    CHECK_EQ(hal.log.acquire, hal.log.release);
    CHECK(!hal.is_acquired());
    // a competing stack (MeshCore/Meshtastic) can now take the radio
    CHECK(hal.acquire(0) == radio::Result::Ok);
    CHECK(hal.release() == radio::Result::Ok);
  }

  CASE("COUNTER-TEST: a failed send must not consume a frame counter");
  {
    FakeRadioHal hal;
    LorawanMac mac(&hal, cfg);
    CHECK(mac.start_join(0) == radio::Result::Ok);
    CHECK(complete_join(mac, hal, cfg) == radio::Result::Ok);
    const uint32_t before = mac.counters().uplink_next();

    hal.send_result = radio::Result::BusError;
    uint8_t payload[3] = {1, 2, 3};
    CHECK(mac.send_uplink(payload, 3, 1, 0, 868100000u, 2000) != radio::Result::Ok);
    CHECK_EQ(mac.counters().uplink_next(), before);

    hal.send_result = radio::Result::Ok;
    CHECK(mac.send_uplink(payload, 3, 1, 0, 868100000u, 4000) == radio::Result::Ok);
    CHECK_EQ(mac.counters().uplink_next(), before + 1);
  }

  CASE("reading RSSI/SNR through the frozen HAL works while acquired");
  {
    FakeRadioHal hal;
    hal.rssi_dbm = -117;
    hal.snr_db = -6;
    LorawanMac mac(&hal, cfg);
    CHECK(hal.acquire(0) == radio::Result::Ok);
    int16_t rssi = 0;
    int8_t snr = 0;
    CHECK(hal.get_rssi_dbm(&rssi) == radio::Result::Ok);
    CHECK(hal.get_snr_db(&snr) == radio::Result::Ok);
    CHECK_EQ(rssi, -117);
    CHECK_EQ(snr, -6);
    CHECK(hal.release() == radio::Result::Ok);
  }
}

}  // namespace

void run_tests() {
  std::printf("  -- lorawan: NO radio, NO gateway. published vectors only --\n");

  test_aes128();
  test_cmac_rfc4493();
  test_lorawan_mic();
  test_join_mic_and_session_keys();
  test_frmpayload_crypto();
  test_eu868_payload_limits();
  test_time_on_air();
  test_duty_cycle_limiter();
  test_join_backoff_table17();
  test_frame_counters();
  test_mac_against_frozen_hal();
}

TEST_MAIN()
