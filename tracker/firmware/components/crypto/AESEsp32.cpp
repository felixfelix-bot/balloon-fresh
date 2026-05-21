/*
 * Copyright (C) 2018 Southern Storm Software, Pty Ltd.
 *
 * Permission is hereby granted, free of charge, to any person obtaining a
 * copy of this software and associated documentation files (the "Software"),
 * to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense,
 * and/or sell copies of the Software, and to permit persons to whom the
 * Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included
 * in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
 * OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 * FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
 * DEALINGS IN THE SOFTWARE.
 */

#include "AES.h"
#include "Crypto.h"
#include <string.h>

// AES implementation for ESP32 using the hardware crypto module.

#if defined(CRYPTO_AES_ESP32)

#include "aes/esp_aes.h"

static inline esp_aes_context *aes_ctx_from_buf(uint8_t *buf) {
    return reinterpret_cast<esp_aes_context *>(buf);
}

AESCommon::AESCommon(uint8_t keySize)
{
    memset(ctx, 0, sizeof(ctx));
    esp_aes_init(aes_ctx_from_buf(ctx));
    aes_ctx_from_buf(ctx)->key_bytes = keySize;
}

AESCommon::~AESCommon()
{
    esp_aes_free(aes_ctx_from_buf(ctx));
    clean(ctx, sizeof(ctx));
}

size_t AESCommon::blockSize() const
{
    return 16;
}

size_t AESCommon::keySize() const
{
    return aes_ctx_from_buf(const_cast<uint8_t *>(ctx))->key_bytes;
}

bool AESCommon::setKey(const uint8_t *key, size_t len)
{
    if (len == aes_ctx_from_buf(ctx)->key_bytes) {
        esp_aes_setkey(aes_ctx_from_buf(ctx), key, len * 8);
        return true;
    }
    return false;
}

void AESCommon::encryptBlock(uint8_t *output, const uint8_t *input)
{
    esp_aes_crypt_ecb(aes_ctx_from_buf(ctx), 1, input, output);
}

void AESCommon::decryptBlock(uint8_t *output, const uint8_t *input)
{
    esp_aes_crypt_ecb(aes_ctx_from_buf(ctx), 0, input, output);
}

void AESCommon::clear()
{
    uint8_t keySize = aes_ctx_from_buf(ctx)->key_bytes;
    esp_aes_free(aes_ctx_from_buf(ctx));
    clean(ctx, sizeof(ctx));
    esp_aes_init(aes_ctx_from_buf(ctx));
    aes_ctx_from_buf(ctx)->key_bytes = keySize;
}

AES128::~AES128()
{
}

AES192::~AES192()
{
}

AES256::~AES256()
{
}

#endif // CRYPTO_AES_ESP32
