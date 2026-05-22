idf_component_register(
    SRCS "fips_transport.cpp"
    INCLUDE_DIRS "include"
    REQUIRES mbedtls micro_ecc
)
