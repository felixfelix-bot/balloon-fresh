idf_component_register(SRCS "gs_main.cpp"
                       INCLUDE_DIRS "."
                       REQUIRES RadioLib esp_timer driver telemetry
                                esp_wifi esp_netif esp_http_client nvs_flash
                                pipeline erasure frag fips_transport micro_ecc mbedtls)
