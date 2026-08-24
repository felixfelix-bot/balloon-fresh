idf_component_register(
    SRCS "blossom_crypto.c"
    INCLUDE_DIRS "include"
    REQUIRES secp256k1 mbedtls json
)
