idf_component_register(
    SRCS "lr2021_radio.c"
    INCLUDE_DIRS "include"
    REQUIRES driver esp_rom esp_timer esp_driver_gpio esp_driver_spi
)
