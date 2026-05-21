idf_component_register(
    SRCS
        "Crypto.cpp"
        "Hash.cpp"
        "BlockCipher.cpp"
        "Cipher.cpp"
        "SHA256.cpp"
        "SHA512.cpp"
        "BigNumberUtil.cpp"
        "Curve25519.cpp"
        "Ed25519.cpp"
        "AESEsp32.cpp"
        "CTR.cpp"
        "ChaCha.cpp"
        "RNG.cpp"
        "NoiseSource.cpp"
    INCLUDE_DIRS "include"
    REQUIRES nvs_flash mbedtls esp_timer
)

target_compile_definitions(${COMPONENT_LIB} PRIVATE
    CRYPTO_AES_ESP32
    ESP32
)
