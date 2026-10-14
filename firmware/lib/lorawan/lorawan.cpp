#include "lorawan.h"

#include <cstring>

namespace balloon {
namespace lorawan {

namespace {

// ===========================================================================
// AES-128 key schedule and the round function (FIPS 197 Sec. 5.1 / 5.3)
// ===========================================================================
constexpr uint8_t kSbox[256] = {
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16};

constexpr uint8_t kInvSbox[256] = {
    0x52, 0x09, 0x6a, 0xd5, 0x30, 0x36, 0xa5, 0x38, 0xbf, 0x40, 0xa3, 0x9e, 0x81, 0xf3, 0xd7, 0xfb,
    0x7c, 0xe3, 0x39, 0x82, 0x9b, 0x2f, 0xff, 0x87, 0x34, 0x8e, 0x43, 0x44, 0xc4, 0xde, 0xe9, 0xcb,
    0x54, 0x7b, 0x94, 0x32, 0xa6, 0xc2, 0x23, 0x3d, 0xee, 0x4c, 0x95, 0x0b, 0x42, 0xfa, 0xc3, 0x4e,
    0x08, 0x2e, 0xa1, 0x66, 0x28, 0xd9, 0x24, 0xb2, 0x76, 0x5b, 0xa2, 0x49, 0x6d, 0x8b, 0xd1, 0x25,
    0x72, 0xf8, 0xf6, 0x64, 0x86, 0x68, 0x98, 0x16, 0xd4, 0xa4, 0x5c, 0xcc, 0x5d, 0x65, 0xb6, 0x92,
    0x6c, 0x70, 0x48, 0x50, 0xfd, 0xed, 0xb9, 0xda, 0x5e, 0x15, 0x46, 0x57, 0xa7, 0x8d, 0x9d, 0x84,
    0x90, 0xd8, 0xab, 0x00, 0x8c, 0xbc, 0xd3, 0x0a, 0xf7, 0xe4, 0x58, 0x05, 0xb8, 0xb3, 0x45, 0x06,
    0xd0, 0x2c, 0x1e, 0x8f, 0xca, 0x3f, 0x0f, 0x02, 0xc1, 0xaf, 0xbd, 0x03, 0x01, 0x13, 0x8a, 0x6b,
    0x3a, 0x91, 0x11, 0x41, 0x4f, 0x67, 0xdc, 0xea, 0x97, 0xf2, 0xcf, 0xce, 0xf0, 0xb4, 0xe6, 0x73,
    0x96, 0xac, 0x74, 0x22, 0xe7, 0xad, 0x35, 0x85, 0xe2, 0xf9, 0x37, 0xe8, 0x1c, 0x75, 0xdf, 0x6e,
    0x47, 0xf1, 0x1a, 0x71, 0x1d, 0x29, 0xc5, 0x89, 0x6f, 0xb7, 0x62, 0x0e, 0xaa, 0x18, 0xbe, 0x1b,
    0xfc, 0x56, 0x3e, 0x4b, 0xc6, 0xd2, 0x79, 0x20, 0x9a, 0xdb, 0xc0, 0xfe, 0x78, 0xcd, 0x5a, 0xf4,
    0x1f, 0xdd, 0xa8, 0x33, 0x88, 0x07, 0xc7, 0x31, 0xb1, 0x12, 0x10, 0x59, 0x27, 0x80, 0xec, 0x5f,
    0x60, 0x51, 0x7f, 0xa9, 0x19, 0xb5, 0x4a, 0x0d, 0x2d, 0xe5, 0x7a, 0x9f, 0x93, 0xc9, 0x9c, 0xef,
    0xa0, 0xe0, 0x3b, 0x4d, 0xae, 0x2a, 0xf5, 0xb0, 0xc8, 0xeb, 0xbb, 0x3c, 0x83, 0x53, 0x99, 0x61,
    0x17, 0x2b, 0x04, 0x7e, 0xba, 0x77, 0xd6, 0x26, 0xe1, 0x69, 0x14, 0x63, 0x55, 0x21, 0x0c, 0x7d};

constexpr uint8_t kRcon[11] = {0x00, 0x01, 0x02, 0x04, 0x08, 0x10,
                               0x20, 0x40, 0x80, 0x1b, 0x36};

inline uint8_t xtime(uint8_t x) {
  return static_cast<uint8_t>((x << 1) ^ ((x & 0x80) ? 0x1b : 0x00));
}

inline uint8_t gmul(uint8_t a, uint8_t b) {
  uint8_t r = 0;
  while (b) {
    if (b & 1) r ^= a;
    a = xtime(a);
    b >>= 1;
  }
  return r;
}

void sub_bytes(uint8_t s[16]) {
  for (int i = 0; i < 16; ++i) s[i] = kSbox[s[i]];
}
void inv_sub_bytes(uint8_t s[16]) {
  for (int i = 0; i < 16; ++i) s[i] = kInvSbox[s[i]];
}

// State is column-major: s[r + 4c]. ShiftRows moves row r left by r.
void shift_rows(uint8_t s[16]) {
  uint8_t t[16];
  for (int r = 0; r < 4; ++r)
    for (int c = 0; c < 4; ++c) t[r + 4 * c] = s[r + 4 * ((c + r) & 3)];
  for (int i = 0; i < 16; ++i) s[i] = t[i];
}
void inv_shift_rows(uint8_t s[16]) {
  uint8_t t[16];
  for (int r = 0; r < 4; ++r)
    for (int c = 0; c < 4; ++c) t[r + 4 * c] = s[r + 4 * ((c - r + 4) & 3)];
  for (int i = 0; i < 16; ++i) s[i] = t[i];
}

void mix_columns(uint8_t s[16]) {
  for (int c = 0; c < 4; ++c) {
    uint8_t *p = s + 4 * c;
    const uint8_t a0 = p[0], a1 = p[1], a2 = p[2], a3 = p[3];
    p[0] = static_cast<uint8_t>(xtime(a0) ^ (xtime(a1) ^ a1) ^ a2 ^ a3);
    p[1] = static_cast<uint8_t>(a0 ^ xtime(a1) ^ (xtime(a2) ^ a2) ^ a3);
    p[2] = static_cast<uint8_t>(a0 ^ a1 ^ xtime(a2) ^ (xtime(a3) ^ a3));
    p[3] = static_cast<uint8_t>((xtime(a0) ^ a0) ^ a1 ^ a2 ^ xtime(a3));
  }
}

void inv_mix_columns(uint8_t s[16]) {
  for (int c = 0; c < 4; ++c) {
    uint8_t *p = s + 4 * c;
    const uint8_t a0 = p[0], a1 = p[1], a2 = p[2], a3 = p[3];
    p[0] = static_cast<uint8_t>(gmul(a0, 14) ^ gmul(a1, 11) ^ gmul(a2, 13) ^ gmul(a3, 9));
    p[1] = static_cast<uint8_t>(gmul(a0, 9) ^ gmul(a1, 14) ^ gmul(a2, 11) ^ gmul(a3, 13));
    p[2] = static_cast<uint8_t>(gmul(a0, 13) ^ gmul(a1, 9) ^ gmul(a2, 14) ^ gmul(a3, 11));
    p[3] = static_cast<uint8_t>(gmul(a0, 11) ^ gmul(a1, 13) ^ gmul(a2, 9) ^ gmul(a3, 14));
  }
}

void add_round_key(uint8_t s[16], const uint8_t *rk) {
  for (int i = 0; i < 16; ++i) s[i] ^= rk[i];
}

void cipher(const Aes128 *ctx, const uint8_t in[16], uint8_t out[16]) {
  uint8_t s[16];
  std::memcpy(s, in, 16);
  add_round_key(s, ctx->round_keys);
  for (int round = 1; round < 10; ++round) {
    sub_bytes(s);
    shift_rows(s);
    mix_columns(s);
    add_round_key(s, ctx->round_keys + 16 * round);
  }
  sub_bytes(s);
  shift_rows(s);
  add_round_key(s, ctx->round_keys + 16 * 10);
  std::memcpy(out, s, 16);
}

void inv_cipher(const Aes128 *ctx, const uint8_t in[16], uint8_t out[16]) {
  uint8_t s[16];
  std::memcpy(s, in, 16);
  add_round_key(s, ctx->round_keys + 16 * 10);
  for (int round = 9; round > 0; --round) {
    inv_shift_rows(s);
    inv_sub_bytes(s);
    add_round_key(s, ctx->round_keys + 16 * round);
    inv_mix_columns(s);
  }
  inv_shift_rows(s);
  inv_sub_bytes(s);
  add_round_key(s, ctx->round_keys);
  std::memcpy(out, s, 16);
}

constexpr uint8_t kRb = 0x87;

void shift_left_1(uint8_t b[16]) {
  uint8_t carry = 0;
  for (int i = 15; i >= 0; --i) {
    const uint8_t next = static_cast<uint8_t>(b[i] >> 7);
    b[i] = static_cast<uint8_t>((b[i] << 1) | carry);
    carry = next;
  }
  b[15] = static_cast<uint8_t>(b[15] ^ (carry ? kRb : 0x00));
}

// ===========================================================================
// EU868 sub-band table. [RP002-1.0.3] Sec. 1.3.1 gives the region duty cycle as
// < 1%; the band split below follows the ETSI/ERC 70-03 assignments that the
// regional parameters reference (868.0-868.6, 868.7-869.2, 869.4-869.65,
// 869.7-870.0), with the mandatory join channels 868.1/868.3/868.5 all landing
// inside the first one.
// ===========================================================================
struct SubBand {
  uint32_t lo_hz;
  uint32_t hi_hz;   // exclusive
  uint32_t duty_num;
  uint32_t duty_den;
  const char *name;
};

const SubBand kSubBands[4] = {
    {868000000u, 868600000u, 1u, 100u, "EU868-868.0-868.6-1pct"},      // join channels
    {868700000u, 869200000u, 1u, 100u, "EU868-868.7-869.2-1pct"},
    {869400000u, 869650000u, 1u, 10u, "EU868-869.4-869.65-10pct"},
    {869700000u, 870000000u, 1u, 100u, "EU868-869.7-870.0-1pct"},
};

constexpr int kSubBandCount = 4;

}  // namespace

// ===========================================================================
// AES-128 public surface
// ===========================================================================
void aes128_init(Aes128 *ctx, const uint8_t key[16]) {
  if (ctx == nullptr || key == nullptr) return;
  std::memcpy(ctx->round_keys, key, 16);
  uint8_t temp[4];
  for (int i = 4; i < 44; ++i) {
    std::memcpy(temp, ctx->round_keys + 4 * (i - 1), 4);
    if (i % 4 == 0) {
      const uint8_t t0 = temp[0];
      temp[0] = kSbox[temp[1]];
      temp[1] = kSbox[temp[2]];
      temp[2] = kSbox[temp[3]];
      temp[3] = kSbox[t0];
      temp[0] ^= kRcon[i / 4];
    }
    for (int j = 0; j < 4; ++j)
      ctx->round_keys[4 * i + j] = static_cast<uint8_t>(ctx->round_keys[4 * (i - 4) + j] ^ temp[j]);
  }
}

void aes128_encrypt_block(const Aes128 *ctx, const uint8_t in[16], uint8_t out[16]) {
  if (ctx == nullptr) return;
  cipher(ctx, in, out);
}

void aes128_ecb_encrypt(const uint8_t key[16], const uint8_t in[16], uint8_t out[16]) {
  Aes128 ctx;
  aes128_init(&ctx, key);
  cipher(&ctx, in, out);
}

void aes128_ecb_decrypt(const uint8_t key[16], const uint8_t in[16], uint8_t out[16]) {
  Aes128 ctx;
  aes128_init(&ctx, key);
  inv_cipher(&ctx, in, out);
}

// ===========================================================================
// AES-CMAC [RFC4493]
// ===========================================================================
void aes_cmac_subkeys(const uint8_t key[16], uint8_t k1[16], uint8_t k2[16]) {
  uint8_t l[16];
  uint8_t zero[16];
  std::memset(zero, 0, 16);
  aes128_ecb_encrypt(key, zero, l);

  uint8_t k1t[16], k2t[16];
  std::memcpy(k1t, l, 16);
  shift_left_1(k1t);
  std::memcpy(k1, k1t, 16);

  std::memcpy(k2t, k1t, 16);
  shift_left_1(k2t);
  std::memcpy(k2, k2t, 16);
}

void aes_cmac_with_subkeys(const uint8_t key[16], const uint8_t k1[16],
                           const uint8_t k2[16], const uint8_t *msg, size_t len,
                           uint8_t out[16]) {
  Aes128 ctx;
  aes128_init(&ctx, key);

  const size_t nblocks = (len + 15) / 16;
  uint8_t last[16];
  std::memset(last, 0, 16);

  if (nblocks == 0) {
    // len == 0: one padded block, K2
    last[0] = 0x80;
    for (int i = 0; i < 16; ++i) last[i] ^= k2[i];
  } else if (len % 16 == 0) {
    std::memcpy(last, msg + 16 * (nblocks - 1), 16);
    for (int i = 0; i < 16; ++i) last[i] ^= k1[i];
  } else {
    const size_t rem = len % 16;
    uint8_t buf[16];
    std::memset(buf, 0, 16);
    std::memcpy(buf, msg + 16 * (nblocks - 1), rem);
    buf[rem] = 0x80;
    for (int i = 0; i < 16; ++i) last[i] = static_cast<uint8_t>(buf[i] ^ k2[i]);
  }

  uint8_t x[16];
  std::memset(x, 0, 16);
  for (size_t i = 0; i + 1 < nblocks; ++i) {
    uint8_t blk[16];
    for (int j = 0; j < 16; ++j) blk[j] = static_cast<uint8_t>(x[j] ^ msg[16 * i + j]);
    cipher(&ctx, blk, x);
  }
  uint8_t blk[16];
  for (int j = 0; j < 16; ++j) blk[j] = static_cast<uint8_t>(x[j] ^ last[j]);
  cipher(&ctx, blk, out);
}

void aes_cmac(const uint8_t key[16], const uint8_t *msg, size_t len, uint8_t out[16]) {
  uint8_t k1[16], k2[16];
  aes_cmac_subkeys(key, k1, k2);
  aes_cmac_with_subkeys(key, k1, k2, msg, len, out);
}

// ===========================================================================
// LoRaWAN MICs
// ===========================================================================
namespace {

void build_b0(uint8_t dir, uint32_t dev_addr, uint32_t fcnt, size_t msg_len,
              uint8_t b0[16]) {
  std::memset(b0, 0, 16);
  b0[0] = 0x49;
  // b0[1..2] = ConfFCnt (0x0000 outside a 1.1 acknowledged exchange)
  b0[3] = 0x00;
  b0[4] = 0x00;
  b0[5] = dir;
  b0[6] = static_cast<uint8_t>(dev_addr & 0xFFu);
  b0[7] = static_cast<uint8_t>((dev_addr >> 8) & 0xFFu);
  b0[8] = static_cast<uint8_t>((dev_addr >> 16) & 0xFFu);
  b0[9] = static_cast<uint8_t>((dev_addr >> 24) & 0xFFu);
  b0[10] = static_cast<uint8_t>(fcnt & 0xFFu);
  b0[11] = static_cast<uint8_t>((fcnt >> 8) & 0xFFu);
  b0[12] = static_cast<uint8_t>((fcnt >> 16) & 0xFFu);
  b0[13] = static_cast<uint8_t>((fcnt >> 24) & 0xFFu);
  b0[14] = 0x00;
  b0[15] = static_cast<uint8_t>(msg_len & 0xFFu);
}

// cmac = aes128_cmac(key, B0 | msg). B0 is a PREFIX, not a suffix -- see
// [LW104] Sec. 4.4.1 ("cmac = aes128_cmac(key, B0 | msg)") and LoRaMac-node's
// SecureElementComputeAesCmac(micBuff /*B0*/, msg, len, ...).
void mic_with_b0(const uint8_t key[16], const uint8_t b0[16], const uint8_t *msg,
                 size_t msg_len, uint8_t mic_out[4]) {
  // B0 is a 16-byte PREFIX, so the staging buffer needs 16 bytes of headroom
  // on top of the largest legal frame (242 B FRMPayload + 12 B overhead).
  uint8_t buf[16 + 256];
  if (msg_len > 256) {
    std::memset(mic_out, 0, 4);
    return;
  }
  std::memcpy(buf, b0, 16);
  if (msg != nullptr && msg_len > 0) std::memcpy(buf + 16, msg, msg_len);
  uint8_t mac[16];
  aes_cmac(key, buf, 16 + msg_len, mac);
  std::memcpy(mic_out, mac, 4);
}

}  // namespace

void lorawan_mic_uplink(const uint8_t nwk_s_key[16], uint32_t dev_addr,
                        uint32_t fcnt, const uint8_t *msg, size_t msg_len,
                        uint8_t mic_out[4]) {
  uint8_t b0[16];
  build_b0(0x00, dev_addr, fcnt, msg_len, b0);
  mic_with_b0(nwk_s_key, b0, msg, msg_len, mic_out);
}

void lorawan_mic_downlink(const uint8_t nwk_s_key[16], uint32_t dev_addr,
                          uint32_t fcnt, const uint8_t *msg, size_t msg_len,
                          uint8_t mic_out[4]) {
  uint8_t b0[16];
  build_b0(0x01, dev_addr, fcnt, msg_len, b0);
  mic_with_b0(nwk_s_key, b0, msg, msg_len, mic_out);
}

void lorawan_join_request_mic(const uint8_t nwk_key[16], const uint8_t *msg,
                              size_t msg_len, uint8_t mic_out[4]) {
  uint8_t mac[16];
  aes_cmac(nwk_key, msg, msg_len, mac);
  std::memcpy(mic_out, mac, 4);
}

// ===========================================================================
// FRMPayload encryption
// ===========================================================================
void lorawan_crypt_frmpayload(const uint8_t key[16], uint32_t dev_addr,
                              uint8_t dir, uint32_t fcnt, const uint8_t *in,
                              uint8_t *out, size_t len) {
  if (in == nullptr || out == nullptr) return;
  for (size_t i = 0; i < len; i += 16) {
    const uint8_t block_index = static_cast<uint8_t>(i / 16 + 1);
    uint8_t a[16];
    std::memset(a, 0, 16);
    a[0] = 0x01;
    a[5] = dir;
    a[6] = static_cast<uint8_t>(dev_addr & 0xFFu);
    a[7] = static_cast<uint8_t>((dev_addr >> 8) & 0xFFu);
    a[8] = static_cast<uint8_t>((dev_addr >> 16) & 0xFFu);
    a[9] = static_cast<uint8_t>((dev_addr >> 24) & 0xFFu);
    a[10] = static_cast<uint8_t>(fcnt & 0xFFu);
    a[11] = static_cast<uint8_t>((fcnt >> 8) & 0xFFu);
    a[12] = static_cast<uint8_t>((fcnt >> 16) & 0xFFu);
    a[13] = static_cast<uint8_t>((fcnt >> 24) & 0xFFu);
    a[15] = block_index;
    uint8_t s[16];
    aes128_ecb_encrypt(key, a, s);
    const size_t n = (len - i < 16) ? (len - i) : 16;
    for (size_t j = 0; j < n; ++j) out[i + j] = static_cast<uint8_t>(in[i + j] ^ s[j]);
  }
}

// ===========================================================================
// Session key derivation
// ===========================================================================
void derive_session_keys_1_0(const uint8_t nwk_key[16], uint32_t join_nonce,
                             const uint8_t net_id[3], const uint8_t join_eui[8],
                             uint16_t dev_nonce, uint8_t nwk_s_key_out[16],
                             uint8_t app_s_key_out[16]) {
  (void)join_eui;  // only used in the OptNeg (1.1) form
  // B = typ | JoinNonce(3, LE) | NetID(3, **reverse** of wire order) |
  //     DevNonce(2, LE) | 0x00 x7
  //
  // The JoinNonce is a 24-bit counter, not the 32-bit value used in B0 --
  // marshalling it as 4 bytes shifts NetID and silently derives wrong keys.
  // NetID is stored on the air as 0x01 0x02 0x03 but enters the derivation
  // block reversed; `net_id` arrives here in wire order. Both conventions are
  // forced by the published joinserver vector (JoinNonce 65536, NetID
  // 0x010203, DevNonce 258 -> NwkSKey df53c35f.., AppSKey 927b9c91..).
  uint8_t base[16];
  std::memset(base, 0, 16);
  base[0] = 0x01;  // NwkSKey / FNwkSIntKey
  base[1] = static_cast<uint8_t>(join_nonce & 0xFFu);
  base[2] = static_cast<uint8_t>((join_nonce >> 8) & 0xFFu);
  base[3] = static_cast<uint8_t>((join_nonce >> 16) & 0xFFu);
  base[4] = net_id[2];
  base[5] = net_id[1];
  base[6] = net_id[0];
  base[7] = static_cast<uint8_t>(dev_nonce & 0xFFu);
  base[8] = static_cast<uint8_t>((dev_nonce >> 8) & 0xFFu);
  aes128_ecb_encrypt(nwk_key, base, nwk_s_key_out);

  base[0] = 0x02;  // AppSKey
  aes128_ecb_encrypt(nwk_key, base, app_s_key_out);
}

// ===========================================================================
// EU868 data rates
// ===========================================================================
namespace {
struct DrInfo {
  uint8_t sf;
  uint32_t bw;
  int max_n;
  int max_m;
};
// [RP002-1.0.3] Table 8 (DR/SF map) and Table 13 (max payload, not repeater
// compatible). DR6 (SF7/250k) is deliberately outside the DR0..DR5 set the
// balloon uses.
const DrInfo kDr[6] = {
    {12, 125000u, 51, 59},
    {11, 125000u, 51, 59},
    {10, 125000u, 51, 59},
    {9, 125000u, 115, 123},
    {8, 125000u, 242, 250},
    {7, 125000u, 242, 250},
};
}  // namespace

int eu868_max_app_payload(int dr) {
  if (dr < 0 || dr > 5) return -1;
  return kDr[dr].max_n;
}
int eu868_max_mac_payload(int dr) {
  if (dr < 0 || dr > 5) return -1;
  return kDr[dr].max_m;
}
int eu868_sf_for_dr(int dr) {
  if (dr < 0 || dr > 5) return -1;
  return kDr[dr].sf;
}
uint32_t eu868_bandwidth_hz_for_dr(int dr) {
  if (dr < 0 || dr > 5) return 0;
  return kDr[dr].bw;
}
bool payload_fits(size_t app_payload_len, int dr) {
  const int max_n = eu868_max_app_payload(dr);
  if (max_n < 0) return false;  // unknown DR is never a fit
  return app_payload_len <= static_cast<size_t>(max_n);
}

// ===========================================================================
// Time on air
// ===========================================================================
uint32_t lora_symbol_duration_us(uint8_t sf, uint32_t bandwidth_hz) {
  if (bandwidth_hz == 0 || sf < 5 || sf > 12) return 0;
  return static_cast<uint32_t>((1u << sf) * 1000000ull / bandwidth_hz);
}

int lora_payload_symbol_count(size_t payload_len, uint8_t sf, uint8_t coding_rate,
                              bool header_enabled, bool low_data_rate_opt) {
  if (sf < 5 || sf > 12) return -1;
  if (coding_rate < 5 || coding_rate > 8) return -1;
  const int de = low_data_rate_opt ? 1 : 0;
  const int ih = header_enabled ? 0 : 1;
  const int a = static_cast<int>(8 * payload_len) - 4 * sf + 28 + 16 - 20 * ih;
  const int b = 4 * (sf - 2 * de);
  int inner = 0;
  if (a > 0) inner = (a + b - 1) / b;  // ceil
  if (inner < 0) inner = 0;
  return 8 + inner * static_cast<int>(coding_rate);
}

uint32_t lora_time_on_air_us(size_t payload_len, uint8_t sf, uint32_t bandwidth_hz,
                             uint8_t coding_rate, uint16_t preamble_symbols,
                             bool header_enabled, bool low_data_rate_opt) {
  const uint32_t tsym = lora_symbol_duration_us(sf, bandwidth_hz);
  if (tsym == 0) return 0;
  const int n = lora_payload_symbol_count(payload_len, sf, coding_rate,
                                         header_enabled, low_data_rate_opt);
  if (n < 0) return 0;
  const uint64_t tpre = static_cast<uint64_t>(100u * preamble_symbols + 425u) * tsym / 100u;
  return static_cast<uint32_t>(tpre + static_cast<uint64_t>(n) * tsym);
}

uint32_t eu868_time_on_air_us(int dr, size_t payload_len,
                              uint16_t preamble_symbols, uint8_t coding_rate) {
  const uint8_t sf = static_cast<uint8_t>(eu868_sf_for_dr(dr));
  if (eu868_max_app_payload(dr) < 0) return 0;
  const uint32_t bw = eu868_bandwidth_hz_for_dr(dr);
  // Mandatory low-data-rate optimisation for SF11/SF12 at 125 kHz
  // [RP002-1.0.3 Sec. 2.4.3 / TS001].
  const bool ldro = (sf >= 11 && bw == 125000u);
  return lora_time_on_air_us(payload_len, sf, bw, coding_rate, preamble_symbols,
                             true, ldro);
}

// ===========================================================================
// EU868 sub-bands
// ===========================================================================
const uint32_t kEu868DefaultChannelsHz[kEu868DefaultChannelCount] = {
    868100000u, 868300000u, 868500000u};

int eu868_sub_band_index(uint32_t freq_hz) {
  for (int i = 0; i < kSubBandCount; ++i) {
    if (freq_hz >= kSubBands[i].lo_hz && freq_hz < kSubBands[i].hi_hz) return i;
  }
  return -1;
}
int eu868_sub_band_count() { return kSubBandCount; }

uint32_t eu868_sub_band_duty_num(int band) {
  if (band < 0 || band >= kSubBandCount) return 0;
  return kSubBands[band].duty_num;
}
uint32_t eu868_sub_band_duty_den(int band) {
  if (band < 0 || band >= kSubBandCount) return 0;
  return kSubBands[band].duty_den;
}
const char *eu868_sub_band_name(int band) {
  if (band < 0 || band >= kSubBandCount) return "none";
  return kSubBands[band].name;
}

// ===========================================================================
// Duty-cycle limiter
// ===========================================================================
DutyCycleLimiter::DutyCycleLimiter(uint32_t duty_denominator)
    : duty_den_(duty_denominator == 0 ? 100 : duty_denominator) {}

void DutyCycleLimiter::set_band_duty_override(int band, uint32_t num, uint32_t den) {
  if (band < 0 || band >= 8) return;
  override_num_[band] = num;
  override_den_[band] = den;
}

void DutyCycleLimiter::push(uint64_t at_ms, uint32_t ms, int band) {
  log_[head_].at_ms = at_ms;
  log_[head_].ms = ms;
  log_[head_].band = static_cast<int8_t>(band);
  head_ = (head_ + 1) % kMaxEntries;
  if (size_ < kMaxEntries) ++size_;
}

void DutyCycleLimiter::budget_for(int band, uint32_t *num, uint32_t *den) const {
  *num = eu868_sub_band_duty_num(band);
  *den = eu868_sub_band_duty_den(band);
  if (band >= 0 && band < 8 && override_den_[band] != 0) {
    *num = override_num_[band];
    *den = override_den_[band];
  }
}

uint32_t DutyCycleLimiter::band_airtime_ms(int band, uint64_t from_ms,
                                           uint64_t to_ms) const {
  if (band < 0) return 0;
  uint32_t used = 0;
  for (int i = 0; i < size_; ++i) {
    const int idx = (head_ - 1 - i + 2 * kMaxEntries) % kMaxEntries;
    const Entry &e = log_[idx];
    if (e.band != band) continue;
    if (e.at_ms < from_ms || e.at_ms >= to_ms) continue;
    used += e.ms;
  }
  return used;
}

uint32_t DutyCycleLimiter::charged(int band, uint64_t now_ms) const {
  if (band < 0) return 0;
  uint32_t used = 0;
  for (int i = 0; i < size_; ++i) {
    const int idx = (head_ - 1 - i + 2 * kMaxEntries) % kMaxEntries;
    const Entry &e = log_[idx];
    if (e.band != band) continue;
    // A charge logged at T is released at exactly T + 1 h, so the boundary is
    // exclusive. `earliest()` uses the same predicate, which is what keeps the
    // instant it predicts actually legal.
    if (now_ms >= e.at_ms && (now_ms - e.at_ms) < 3600000ull) used += e.ms;
  }
  return used;
}

DutyCycleVerdict DutyCycleLimiter::request(uint32_t freq_hz, uint32_t airtime_ms,
                                           uint64_t now_ms) {
  DutyCycleVerdict v{};
  v.allowed = false;
  v.band = eu868_sub_band_index(freq_hz);
  v.wait_ms = 0;
  if (v.band < 0) {
    ++blocked_;
    return v;
  }

  uint32_t num = 0, den = 0;
  budget_for(v.band, &num, &den);
  if (den == 0 || num == 0) {
    // A zero budget cannot satisfy any request, not even a zero-airtime one.
    ++blocked_;
    v.wait_ms = 3600000u;
    return v;
  }

  // The budget is duty_num/duty_den of one hour, sliding.
  const uint32_t budget_ms = static_cast<uint32_t>(3600000ull * num / den);
  const uint32_t used = charged(v.band, now_ms);

  if (used + airtime_ms <= budget_ms) {
    push(now_ms, airtime_ms, v.band);
    v.allowed = true;
    return v;
  }

  // Refused: report when this frame would become legal. The oldest charge of
  // THIS band inside the window has to age out first.
  uint64_t oldest = now_ms;
  bool found = false;
  for (int i = 0; i < size_; ++i) {
    const int idx = (head_ - 1 - i + 2 * kMaxEntries) % kMaxEntries;
    const Entry &e = log_[idx];
    if (e.band != v.band) continue;
    if (e.at_ms > now_ms || (now_ms - e.at_ms) >= 3600000ull) continue;
    if (!found || e.at_ms < oldest) {
      oldest = e.at_ms;
      found = true;
    }
  }
  if (found) {
    const uint64_t release = oldest + 3600000ull;
    v.wait_ms = (release > now_ms) ? static_cast<uint32_t>(release - now_ms) : 1u;
  } else {
    v.wait_ms = 3600000u;
  }
  if (v.wait_ms == 0) v.wait_ms = 1u;
  ++blocked_;
  return v;
}

bool DutyCycleLimiter::can_send(uint32_t freq_hz, uint32_t airtime_ms, uint64_t now_ms) {
  DutyCycleVerdict v = request(freq_hz, airtime_ms, now_ms);
  return v.allowed;
}

uint64_t DutyCycleLimiter::earliest(uint32_t freq_hz, uint32_t airtime_ms,
                                    uint64_t now_ms) {
  const int band = eu868_sub_band_index(freq_hz);
  if (band < 0) return now_ms + 1;

  uint32_t num = 0, den = 0;
  budget_for(band, &num, &den);
  if (den == 0 || num == 0) return UINT64_MAX;
  const uint32_t budget_ms = static_cast<uint32_t>(3600000ull * num / den);

  // Charges of this band that are already logged, ascending by time.
  uint64_t at[kMaxEntries];
  uint32_t ms[kMaxEntries];
  int n = 0;
  for (int i = 0; i < size_ && n < kMaxEntries; ++i) {
    const int idx = (head_ - 1 - i + 2 * kMaxEntries) % kMaxEntries;
    const Entry &e = log_[idx];
    if (e.band != band) continue;
    at[n] = e.at_ms;
    ms[n] = e.ms;
    ++n;
  }
  for (int i = 1; i < n; ++i) {
    const uint64_t ka = at[i];
    const uint32_t km = ms[i];
    int j = i - 1;
    while (j >= 0 && at[j] > ka) {
      at[j + 1] = at[j];
      ms[j + 1] = ms[j];
      --j;
    }
    at[j + 1] = ka;
    ms[j + 1] = km;
  }

  // Drop the oldest charge, one at a time, until the frame fits.
  for (int first_alive = 0; first_alive <= n; ++first_alive) {
    const uint64_t t =
        (first_alive == 0) ? now_ms : at[first_alive - 1] + 3600000ull;
    if (t < now_ms) continue;
    uint32_t used = 0;
    for (int i = first_alive; i < n; ++i) {
      if (at[i] > t) break;
      if (t - at[i] < 3600000ull) used += ms[i];
    }
    if (used + airtime_ms <= budget_ms) return t;
  }
  return now_ms + 3600000ull;
}

// ===========================================================================
// Join-request duty cycle -- [LW104] Table 17
// ===========================================================================
void JoinBackoff::reset(uint64_t now_ms) {
  head_ = 0;
  size_ = 0;
  reset_ms_ = now_ms;
}

void JoinBackoff::record(uint32_t airtime_ms, uint64_t now_ms) {
  log_[head_] = Entry{now_ms, airtime_ms};
  head_ = (head_ + 1) % kMaxEntries;
  if (size_ < kMaxEntries) ++size_;
}

uint32_t JoinBackoff::join_airtime_ms(uint64_t from_ms, uint64_t to_ms) const {
  uint32_t used = 0;
  for (int i = 0; i < size_; ++i) {
    const int idx = (head_ - 1 - i + 2 * kMaxEntries) % kMaxEntries;
    const Entry &e = log_[idx];
    if (e.at_ms < from_ms || e.at_ms >= to_ms) continue;
    used += e.ms;
  }
  return used;
}

bool JoinBackoff::allowed(uint32_t airtime_ms, uint64_t now_ms) const {
  if (now_ms < reset_ms_) return false;
  const uint64_t elapsed = now_ms - reset_ms_;

  // [LW104] Table 17 is three ROWS, each an aggregated cap over its own
  // interval -- not one growth-only accumulator:
  //   elapsed <  1 h : <= 36 s over [reset, now]
  //   elapsed < 11 h : <= 36 s over [reset+1h, now]  (a fresh 36 s at the hour,
  //                    shared by the whole hour-2..hour-11 class)
  //   otherwise      : <= 8.7 s over any rolling 24 h
  uint64_t from = 0;
  uint64_t cap = kSteadyStateCapMs;
  if (elapsed < kFirstHourEndMs) {
    from = reset_ms_;
    cap = kFirstHourCapMs;
  } else if (elapsed < kSecondWindowEndMs) {
    from = reset_ms_ + kFirstHourEndMs;
    cap = kSecondWindowCapMs;
  } else {
    from = (now_ms > kSteadyStateWindowMs) ? (now_ms - kSteadyStateWindowMs) : 0;
    cap = kSteadyStateCapMs;
  }

  const uint32_t used = join_airtime_ms(from, now_ms + 1);
  return static_cast<uint64_t>(used) + airtime_ms <= cap;
}

// ===========================================================================
// Frame counters
// ===========================================================================
void FrameCounters::init(uint32_t persisted_uplink, uint32_t persisted_downlink,
                         bool allow_rollover) {
  // The persisted value is a FLOOR. A stale store must never move the counter
  // backwards: replaying counters the network server already saw is a silent
  // outage, not a cosmetic bug.
  if (persisted_uplink > high_water_) high_water_ = persisted_uplink;
  if (persisted_downlink > downlink_last_) {
    downlink_last_ = persisted_downlink;
    has_downlink_ = true;
  }
  // The floor applies to the read cursor as well as the high-water mark, so a
  // stale persisted value can never drag the counter backwards.
  if (uplink_ < high_water_) uplink_ = high_water_;
  allow_rollover_ = allow_rollover;
}

bool FrameCounters::can_take_uplink() const {
  if (uplink_ != 0xFFFFFFFFu) return true;
  return allow_rollover_;
}

uint32_t FrameCounters::take_uplink() {
  const uint32_t v = uplink_;
  if (wrap_pending_) {
    // The previous call consumed 0xFFFFFFFF; this value is the re-use.
    rolled_over_ = true;
    wrap_pending_ = false;
  }
  if (uplink_ != 0xFFFFFFFFu) {
    ++uplink_;
  } else if (allow_rollover_) {
    uplink_ = 0;
    wrap_pending_ = true;
  }
  if (v > high_water_) high_water_ = v;
  return v;
}

bool FrameCounters::exhausted() const {
  return uplink_ == 0xFFFFFFFFu && !allow_rollover_;
}

bool FrameCounters::accept_downlink(uint32_t fcnt) {
  if (has_downlink_ && fcnt <= downlink_last_) return false;
  downlink_last_ = fcnt;
  has_downlink_ = true;
  return true;
}

void FrameCounters::snapshot(uint32_t *uplink_out, uint32_t *downlink_out) const {
  if (uplink_out != nullptr) *uplink_out = uplink_;
  if (downlink_out != nullptr) *downlink_out = downlink_last_;
}

// ===========================================================================
// MAC layer
// ===========================================================================
LorawanMac::LorawanMac(radio::RadioHal *hal, const MacConfig &cfg)
    : hal_(hal), cfg_(cfg), duty_(cfg.duty_denominator == 0 ? 100 : cfg.duty_denominator) {
  retries_left_ = cfg_.join_retry_max;
  counters_.init(0, 0);
}

LorawanMac::~LorawanMac() {
  if (hal_ != nullptr && hal_->is_acquired()) hal_->release();
}

uint32_t LorawanMac::airtime_for(int dr, size_t phy_len) const {
  return eu868_time_on_air_us(dr, phy_len, cfg_.preamble_symbols, cfg_.coding_rate);
}

radio::Result LorawanMac::transmit(const uint8_t *frame, size_t len, uint32_t freq_hz,
                                   int dr) {
  if (hal_ == nullptr) return radio::Result::BusError;
  if (hal_->acquire(1000) != radio::Result::Ok) return radio::Result::Busy;
  radio::Config c{};
  c.modulation = radio::Modulation::Lora;
  c.frequency_hz = freq_hz;
  c.bandwidth_hz = eu868_bandwidth_hz_for_dr(dr);
  c.spreading_factor = static_cast<uint8_t>(eu868_sf_for_dr(dr));
  c.coding_rate = cfg_.coding_rate;
  c.tx_power_dbm = cfg_.tx_power_dbm;
  c.preamble_symbols = cfg_.preamble_symbols;
  c.crc_on = true;
  if (hal_->configure(c) != radio::Result::Ok) {
    hal_->release();
    return radio::Result::BusError;
  }
  const radio::Result r = hal_->send(frame, len);
  hal_->release();
  return r;
}

radio::Result LorawanMac::start_join(uint64_t now_ms) {
  if (state_ == JoinState::Joined) return radio::Result::Ok;
  if (retries_left_ == 0) return radio::Result::BadArgument;

  uint8_t frame[23];
  frame[0] = 0x00;  // MHDR: MType = JoinRequest, Major = R1
  std::memcpy(frame + 1, cfg_.join_eui, 8);
  std::memcpy(frame + 9, cfg_.dev_eui, 8);
  // DevNonce is little-endian and MUST advance on every try ([LW104] 6.2.2).
  frame[17] = static_cast<uint8_t>(dev_nonce_ & 0xFFu);
  frame[18] = static_cast<uint8_t>((dev_nonce_ >> 8) & 0xFFu);
  uint8_t mic[4];
  lorawan_join_request_mic(cfg_.app_key, frame, 19, mic);
  std::memcpy(frame + 19, mic, 4);

  // airtime_for() is microseconds; the join budget is in milliseconds.
  const uint32_t toa = (airtime_for(cfg_.join_dr, sizeof(frame)) + 999u) / 1000u;
  if (!join_backoff_.allowed(toa, now_ms)) return radio::Result::Busy;

  const radio::Result r = transmit(frame, sizeof(frame), cfg_.join_channel_hz, cfg_.join_dr);
  if (r != radio::Result::Ok) return r;

  join_backoff_.record(toa, now_ms);
  ++dev_nonce_;
  if (retries_left_ > 0) --retries_left_;
  state_ = JoinState::Requesting;
  return radio::Result::Ok;
}

bool LorawanMac::accept_join_accept(const uint8_t *frame, size_t len) {
  // [LW104] Sec. 6.2.3: MHDR(0x20) | AES-decrypt(AppKey, 16 B). The 16 B of
  // ciphertext carry 12 B of MACPayload + a 4 B MIC.
  if (len != 17) return false;
  if (frame[0] != 0x20) return false;

  // [LW104] Sec. 6.2.3. In LoRaWAN 1.0 the network *inverse*-ciphers the
  // join-accept, so a 1.0 device recovers the plaintext by running the cipher
  // FORWARD. (1.1 flipped this to a plain AES decrypt.) Getting the direction
  // backwards still "works" cryptographically -- it just yields the wrong
  // bytes and the MIC then fails, which is exactly how it presents.
  uint8_t plain[16];
  aes128_ecb_encrypt(cfg_.app_key, frame + 1, plain);

  // MIC = cmac(NwkKey, MHDR | JoinNonce | NetID | DevAddr | DLSettings |
  //            RxDelay | CFList)   -- over the PLAINTEXT
  uint8_t msg[16];
  msg[0] = 0x20;
  std::memcpy(msg + 1, plain, 12);
  uint8_t mac[16];
  aes_cmac(cfg_.app_key, msg, 13, mac);
  if (std::memcmp(mac, plain + 12, 4) != 0) return false;

  const uint32_t join_nonce = static_cast<uint32_t>(plain[0]) |
                              (static_cast<uint32_t>(plain[1]) << 8) |
                              (static_cast<uint32_t>(plain[2]) << 16);
  const uint8_t net_id[3] = {plain[3], plain[4], plain[5]};
  const uint32_t dev_addr = static_cast<uint32_t>(plain[6]) |
                            (static_cast<uint32_t>(plain[7]) << 8) |
                            (static_cast<uint32_t>(plain[8]) << 16) |
                            (static_cast<uint32_t>(plain[9]) << 24);

  // DevAddr 0x00000000 is not assignable ([LW104]). The MIC above proves the
  // frame came from a key holder; it does not make the address usable.
  if (dev_addr == 0u) return false;

  session_.joined = true;
  session_.dev_addr = dev_addr;
  session_.net_id[0] = net_id[0];
  session_.net_id[1] = net_id[1];
  session_.net_id[2] = net_id[2];
  session_.dev_nonce = static_cast<uint16_t>(dev_nonce_ == 0 ? 0 : dev_nonce_ - 1);
  derive_session_keys_1_0(cfg_.app_key, join_nonce, net_id, cfg_.join_eui,
                          session_.dev_nonce, session_.nwk_skey, session_.app_skey);
  counters_.init(0, 0);
  state_ = JoinState::Joined;
  return true;
}

radio::Result LorawanMac::poll(uint64_t) {
  if (hal_ == nullptr) return radio::Result::BusError;
  if (hal_->acquire(1000) != radio::Result::Ok) return radio::Result::Busy;
  uint8_t rx[256];
  size_t n = 0;
  const radio::Result r = hal_->receive(rx, sizeof(rx), &n, 1000);
  hal_->release();
  if (r != radio::Result::Ok) return r;
  if (n == 0) {
    if (state_ == JoinState::Requesting && retries_left_ == 0) state_ = JoinState::Failed;
    return radio::Result::Ok;
  }
  if (state_ == JoinState::Requesting || state_ == JoinState::Idle) {
    accept_join_accept(rx, n);
  }
  return radio::Result::Ok;
}

radio::Result LorawanMac::send_uplink(const uint8_t *payload, size_t len,
                                      uint8_t fport, int dr, uint32_t freq_hz,
                                      uint64_t now_ms) {
  if (!session_.joined || state_ != JoinState::Joined) return radio::Result::NotAcquired;
  if (payload == nullptr && len > 0) return radio::Result::BadArgument;
  if (!payload_fits(len, dr)) return radio::Result::BadArgument;
  if (!counters_.can_take_uplink()) return radio::Result::BadArgument;

  // MHDR | DevAddr(4, LE) | FCtrl | FCnt(2, LE) | FPort | FRMPayload | MIC
  uint8_t frame[1 + 4 + 1 + 2 + 1 + 242 + 4];
  const uint32_t fcnt = counters_.uplink_next();
  size_t off = 0;
  frame[off++] = 0x40;  // UnconfirmedDataUp, Major R1
  frame[off++] = static_cast<uint8_t>(session_.dev_addr & 0xFFu);
  frame[off++] = static_cast<uint8_t>((session_.dev_addr >> 8) & 0xFFu);
  frame[off++] = static_cast<uint8_t>((session_.dev_addr >> 16) & 0xFFu);
  frame[off++] = static_cast<uint8_t>((session_.dev_addr >> 24) & 0xFFu);
  frame[off++] = 0x00;  // FCtrl: no ADR, no ACK, FOptsLen 0
  frame[off++] = static_cast<uint8_t>(fcnt & 0xFFu);
  frame[off++] = static_cast<uint8_t>((fcnt >> 8) & 0xFFu);
  frame[off++] = fport;
  uint8_t cipher[242];
  lorawan_crypt_frmpayload(session_.app_skey, session_.dev_addr, 0, fcnt, payload,
                           cipher, len);
  std::memcpy(frame + off, cipher, len);
  off += len;
  uint8_t mic[4];
  lorawan_mic_uplink(session_.nwk_skey, session_.dev_addr, fcnt, frame, off, mic);
  std::memcpy(frame + off, mic, 4);
  off += 4;

  // ...and likewise here: the duty-cycle budget is in milliseconds.
  const uint32_t toa = (airtime_for(dr, off) + 999u) / 1000u;
  if (!duty_.can_send(freq_hz, toa, now_ms)) return radio::Result::Busy;

  const radio::Result r = transmit(frame, off, freq_hz, dr);
  if (r != radio::Result::Ok) return r;      // a failed send must NOT burn an FCnt
  counters_.take_uplink();
  return radio::Result::Ok;
}

}  // namespace lorawan
}  // namespace balloon
