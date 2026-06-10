idf_component_register(SRCS "gs_main.cpp"
                       INCLUDE_DIRS "."
                       REQUIRES RadioLib esp_timer driver telemetry
                                pipeline erasure frag fips_transport micro_ecc mbedtls
                                nvs_flash)
