#include "mesh_aes.h"

#include <cstring>

namespace balloon {
namespace meshtastic {
namespace {

// GF(2^8) multiply modulo the AES polynomial x^8 + x^4 + x^3 + x + 1 (0x11B).
uint8_t gf_mul(uint8_t a, uint8_t b) {
  uint8_t r = 0;
  for (int i = 0; i < 8; ++i) {
    if (b & 1) r ^= a;
    const uint8_t hi = (uint8_t)(a & 0x80);
    a = (uint8_t)(a << 1);
    if (hi) a ^= 0x1B;
    b = (uint8_t)(b >> 1);
  }
  return r;
}

// a^-1 in GF(2^8)* is a^254.
uint8_t gf_inv(uint8_t a) {
  if (a == 0) return 0;
  uint8_t r = 1;
  for (int i = 0; i < 254; ++i) r = gf_mul(r, a);
  return r;
}

// FIPS-197 5.1.1: s = affine(b^-1) with the published affine matrix.
uint8_t sbox_at(uint8_t x) {
  const uint8_t inv = gf_inv(x);
  const uint8_t s = (uint8_t)(inv ^ ((inv << 1) | (inv >> 7)) ^
                              ((inv << 2) | (inv >> 6)) ^
                              ((inv << 3) | (inv >> 5)) ^
                              ((inv << 4) | (inv >> 4)));
  return (uint8_t)(s ^ 0x63);
}

void rot_word(uint8_t *w) {
  const uint8_t t = w[0];
  w[0] = w[1];
  w[1] = w[2];
  w[2] = w[3];
  w[3] = t;
}

// FIPS-197 5.3.4: xtime(), i.e. x * {02}.
uint8_t xtime(uint8_t x) {
  return (uint8_t)((x << 1) ^ ((x & 0x80) ? 0x1B : 0x00));
}

void add_round_key(uint8_t *state, const uint8_t *rk) {
  for (int i = 0; i < 16; ++i) state[i] ^= rk[i];
}

void sub_bytes(uint8_t *state) {
  const uint8_t *sb = aes_sbox();
  for (int i = 0; i < 16; ++i) state[i] = sb[state[i]];
}

// State is column-major: index 4*c + r is row r of column c.
void shift_rows(uint8_t *s) {
  uint8_t t;
  // row 1 rotates left by 1
  t = s[1];  s[1] = s[5];   s[5] = s[9];   s[9] = s[13];  s[13] = t;
  // row 2 rotates left by 2
  t = s[2];  s[2] = s[10];  s[10] = t;
  t = s[6];  s[6] = s[14];  s[14] = t;
  // row 3 rotates left by 3 (== right by 1)
  t = s[15]; s[15] = s[11]; s[11] = s[7];  s[7] = s[3];   s[3] = t;
}

void mix_columns(uint8_t *s) {
  for (int c = 0; c < 4; ++c) {
    uint8_t *col = s + 4 * c;
    const uint8_t a0 = col[0], a1 = col[1], a2 = col[2], a3 = col[3];
    col[0] = (uint8_t)(gf_mul(a0, 2) ^ gf_mul(a1, 3) ^ a2 ^ a3);
    col[1] = (uint8_t)(a0 ^ gf_mul(a1, 2) ^ gf_mul(a2, 3) ^ a3);
    col[2] = (uint8_t)(a0 ^ a1 ^ gf_mul(a2, 2) ^ gf_mul(a3, 3));
    col[3] = (uint8_t)(gf_mul(a0, 3) ^ a1 ^ a2 ^ gf_mul(a3, 2));
  }
}

// Increment only the low kCtrCounterBytes of the counter block, big-endian,
// mirroring upstream's CTR implementation with setCounterSize(4).
void increment_counter(uint8_t *counter) {
  const int stop = (int)(kAesBlockLen - kCtrCounterBytes);
  for (int i = (int)kAesBlockLen - 1; i >= stop; --i) {
    if (++counter[i] != 0) break;
  }
}

}  // namespace

const uint8_t *aes_sbox() {
  static uint8_t table[256];
  static bool built = false;
  if (!built) {
    for (int i = 0; i < 256; ++i) table[i] = sbox_at((uint8_t)i);
    built = true;
  }
  return table;
}

bool aes_set_key(AesKey *k, const uint8_t *key, size_t key_len) {
  if (k == nullptr || key == nullptr) return false;
  int nk;  // key length in 32-bit words
  int nr;  // number of rounds
  if (key_len == 16) {
    nk = 4;
    nr = 10;
  } else if (key_len == 32) {
    nk = 8;
    nr = 14;
  } else {
    return false;
  }

  k->rounds = nr;
  const int total_words = 4 * (nr + 1);

  for (int i = 0; i < nk; ++i) {
    for (int j = 0; j < 4; ++j) k->round_key[4 * i + j] = key[4 * i + j];
  }

  const uint8_t *sb = aes_sbox();
  uint8_t rcon = 1;
  for (int i = nk; i < total_words; ++i) {
    uint8_t temp[4];
    std::memcpy(temp, k->round_key + 4 * (i - 1), 4);
    if (i % nk == 0) {
      rot_word(temp);
      for (int j = 0; j < 4; ++j) temp[j] = sb[temp[j]];
      temp[0] ^= rcon;
      rcon = xtime(rcon);
    } else if (nk > 6 && (i % nk) == 4) {
      for (int j = 0; j < 4; ++j) temp[j] = sb[temp[j]];
    }
    for (int j = 0; j < 4; ++j) {
      k->round_key[4 * i + j] =
          (uint8_t)(k->round_key[4 * (i - nk) + j] ^ temp[j]);
    }
  }
  return true;
}

// Only the forward direction is implemented: CTR mode never decrypts a block,
// it only encrypts counter blocks. Adding an inverse path here would be dead
// code, and this file is small enough that dead code would be noticed.
void aes_encrypt_block(const AesKey &k, const uint8_t *in, uint8_t *out) {
  uint8_t state[16];
  std::memcpy(state, in, 16);
  add_round_key(state, k.round_key);
  for (int round = 1; round < k.rounds; ++round) {
    sub_bytes(state);
    shift_rows(state);
    mix_columns(state);
    add_round_key(state, k.round_key + 16 * round);
  }
  sub_bytes(state);
  shift_rows(state);
  add_round_key(state, k.round_key + 16 * k.rounds);
  std::memcpy(out, state, 16);
}

bool aes_ctr_init(AesCtr *c, const uint8_t *key, size_t key_len,
                  const uint8_t *nonce) {
  if (c == nullptr || nonce == nullptr) return false;
  if (!aes_set_key(&c->key, key, key_len)) return false;
  std::memcpy(c->counter, nonce, kAesBlockLen);
  c->pos = kAesBlockLen;  // force a refill before the first byte
  return true;
}

void aes_ctr_xor(AesCtr *c, uint8_t *buf, size_t len) {
  for (size_t i = 0; i < len; ++i) {
    if (c->pos >= kAesBlockLen) {
      aes_encrypt_block(c->key, c->counter, c->keystream);
      increment_counter(c->counter);
      c->pos = 0;
    }
    buf[i] ^= c->keystream[c->pos++];
  }
}

}  // namespace meshtastic
}  // namespace balloon
