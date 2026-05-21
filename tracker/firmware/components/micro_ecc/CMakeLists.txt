idf_component_register(
    SRCS "uECC.c" "micro_ecc_init.c"
    INCLUDE_DIRS "include"
    REQUIRES
)

target_compile_options(${COMPONENT_LIB} PRIVATE
    -DuECC_SUPPORTS_secp160r1=0
    -DuECC_SUPPORTS_secp192r1=0
    -DuECC_SUPPORTS_secp224r1=0
    -DuECC_SUPPORTS_secp256r1=0
    -DuECC_SUPPORTS_secp256k1=1
    -DuECC_OPTIMIZATION_LEVEL=2
    -DuECC_SQUARE_FUNC=0
    -DuECC_ENABLE_VLI_API=0
    -DuECC_RNG_MAX_TRIES=64
)
