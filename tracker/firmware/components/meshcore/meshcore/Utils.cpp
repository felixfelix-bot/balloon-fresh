#include "Utils.h"

#ifdef ESP_PLATFORM
#include "mbedtls/sha256.h"
#include "mbedtls/aes.h"
#include "mbedtls/md.h"
#else
#include <AES.h>
#include <SHA256.h>
#endif

#ifdef ARDUINO
  #include <Arduino.h>
#endif

namespace mesh {

uint32_t RNG::nextInt(uint32_t _min, uint32_t _max) {
  uint32_t num;
  random((uint8_t *) &num, sizeof(num));
  return (num % (_max - _min)) + _min;
}

void Utils::sha256(uint8_t *hash, size_t hash_len, const uint8_t* msg, int msg_len) {
#ifdef ESP_PLATFORM
  uint8_t full[32];
  mbedtls_sha256_context ctx;
  mbedtls_sha256_starts(&ctx, 0);
  mbedtls_sha256_update(&ctx, msg, msg_len);
  mbedtls_sha256_finish(&ctx, full);
  memcpy(hash, full, hash_len);
#else
  SHA256 sha;
  sha.update(msg, msg_len);
  sha.finalize(hash, hash_len);
#endif
}

void Utils::sha256(uint8_t *hash, size_t hash_len, const uint8_t* frag1, int frag1_len, const uint8_t* frag2, int frag2_len) {
#ifdef ESP_PLATFORM
  uint8_t full[32];
  mbedtls_sha256_context ctx;
  mbedtls_sha256_starts(&ctx, 0);
  mbedtls_sha256_update(&ctx, frag1, frag1_len);
  mbedtls_sha256_update(&ctx, frag2, frag2_len);
  mbedtls_sha256_finish(&ctx, full);
  memcpy(hash, full, hash_len);
#else
  SHA256 sha;
  sha.update(frag1, frag1_len);
  sha.update(frag2, frag2_len);
  sha.finalize(hash, hash_len);
#endif
}

int Utils::decrypt(const uint8_t* shared_secret, uint8_t* dest, const uint8_t* src, int src_len) {
  uint8_t* dp = dest;
  const uint8_t* sp = src;

#ifdef ESP_PLATFORM
  mbedtls_aes_context aes;
  mbedtls_aes_setkey_dec(&aes, shared_secret, CIPHER_KEY_SIZE * 8);
  while (sp - src < src_len) {
    mbedtls_aes_crypt_ecb(&aes, MBEDTLS_AES_DECRYPT, sp, dp);
    dp += 16; sp += 16;
  }
  mbedtls_aes_free(&aes);
#else
  AES128 aes;
  aes.setKey(shared_secret, CIPHER_KEY_SIZE);
  while (sp - src < src_len) {
    aes.decryptBlock(dp, sp);
    dp += 16; sp += 16;
  }
#endif

  return sp - src;
}

int Utils::encrypt(const uint8_t* shared_secret, uint8_t* dest, const uint8_t* src, int src_len) {
  uint8_t* dp = dest;

#ifdef ESP_PLATFORM
  mbedtls_aes_context aes;
  mbedtls_aes_setkey_enc(&aes, shared_secret, CIPHER_KEY_SIZE * 8);
  int rem = src_len;
  while (rem >= 16) {
    mbedtls_aes_crypt_ecb(&aes, MBEDTLS_AES_ENCRYPT, src, dp);
    dp += 16; src += 16; rem -= 16;
  }
  if (rem > 0) {
    uint8_t tmp[16];
    memset(tmp, 0, 16);
    memcpy(tmp, src, rem);
    mbedtls_aes_crypt_ecb(&aes, MBEDTLS_AES_ENCRYPT, tmp, dp);
    dp += 16;
  }
  mbedtls_aes_free(&aes);
#else
  AES128 aes;
  aes.setKey(shared_secret, CIPHER_KEY_SIZE);
  while (src_len >= 16) {
    aes.encryptBlock(dp, src);
    dp += 16; src += 16; src_len -= 16;
  }
  if (src_len > 0) {
    uint8_t tmp[16];
    memset(tmp, 0, 16);
    memcpy(tmp, src, src_len);
    aes.encryptBlock(dp, tmp);
    dp += 16;
  }
#endif
  return dp - dest;
}

static void compute_hmac(const uint8_t* key, size_t key_len, const uint8_t* msg, size_t msg_len, uint8_t* out, size_t out_len) {
#ifdef ESP_PLATFORM
  uint8_t full_hmac[32];
  const mbedtls_md_info_t* md_info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  mbedtls_md_hmac(md_info, key, key_len, msg, msg_len, full_hmac);
  memcpy(out, full_hmac, out_len);
#else
  SHA256 sha;
  sha.resetHMAC(key, key_len);
  sha.update(msg, msg_len);
  sha.finalizeHMAC(key, key_len, out, out_len);
#endif
}

int Utils::encryptThenMAC(const uint8_t* shared_secret, uint8_t* dest, const uint8_t* src, int src_len) {
  int enc_len = encrypt(shared_secret, dest + CIPHER_MAC_SIZE, src, src_len);
  compute_hmac(shared_secret, PUB_KEY_SIZE, dest + CIPHER_MAC_SIZE, enc_len, dest, CIPHER_MAC_SIZE);
  return CIPHER_MAC_SIZE + enc_len;
}

int Utils::MACThenDecrypt(const uint8_t* shared_secret, uint8_t* dest, const uint8_t* src, int src_len) {
  if (src_len <= CIPHER_MAC_SIZE) return 0;

  uint8_t hmac[CIPHER_MAC_SIZE];
  compute_hmac(shared_secret, PUB_KEY_SIZE, src + CIPHER_MAC_SIZE, src_len - CIPHER_MAC_SIZE, hmac, CIPHER_MAC_SIZE);
  if (memcmp(hmac, src, CIPHER_MAC_SIZE) == 0) {
    return decrypt(shared_secret, dest, src + CIPHER_MAC_SIZE, src_len - CIPHER_MAC_SIZE);
  }
  return 0;
}

static const char hex_chars[] = "0123456789ABCDEF";

void Utils::toHex(char* dest, const uint8_t* src, size_t len) {
  while (len > 0) {
    uint8_t b = *src++;
    *dest++ = hex_chars[b >> 4];
    *dest++ = hex_chars[b & 0x0F];
    len--;
  }
  *dest = 0;
}

void Utils::printHex(
#ifdef ARDUINO
Stream& s,
#endif
const uint8_t* src, size_t len) {
  while (len > 0) {
    uint8_t b = *src++;
#ifdef ARDUINO
    s.print(hex_chars[b >> 4]);
    s.print(hex_chars[b & 0x0F]);
#else
    (void)b;
#endif
    len--;
  }
}

static uint8_t hexVal(char c) {
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= '0' && c <= '9') return c - '0';
  return 0;
}

bool Utils::isHexChar(char c) {
  return c == '0' || hexVal(c) > 0;
}

bool Utils::fromHex(uint8_t* dest, int dest_size, const char *src_hex) {
  int len = strlen(src_hex);
  if (len != dest_size*2) return false;  // incorrect length

  uint8_t* dp = dest;
  while (dp - dest < dest_size) {
    char ch = *src_hex++;
    char cl = *src_hex++;
    *dp++ = (hexVal(ch) << 4) | hexVal(cl);
  }
  return true;
}

int Utils::parseTextParts(char* text, const char* parts[], int max_num, char separator) {
  int num = 0;
  char* sp = text;
  while (*sp && num < max_num) {
    parts[num++] = sp;
    while (*sp && *sp != separator) sp++;
    if (*sp) {
       *sp++ = 0;  // replace the seperator with a null, and skip past it
    }
  }
  // if we hit the maximum parts, make sure LAST entry does NOT have separator 
  while (*sp && *sp != separator) sp++;
  if (*sp) {
    *sp = 0;  // replace the separator with null
  }
  return num;
}

}