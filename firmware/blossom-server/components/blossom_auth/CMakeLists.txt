idf_component_register(SRCS "blossom_auth.c"
                       INCLUDE_DIRS "include"
                       REQUIRES blossom_crypto json mbedtls esp_http_server esp_timer)
