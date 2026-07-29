idf_component_register(SRCS "blossom_main.c" "blossom_handlers.c"
                       INCLUDE_DIRS "."
                       REQUIRES esp_http_server nvs_flash esp_wifi blossom_storage)
