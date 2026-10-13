# RadioLib is provided as a managed component via idf_component.yml.
idf_component_register(SRCS "main.cpp"
                       INCLUDE_DIRS "."
                       REQUIRES RadioLib driver esp_timer)
