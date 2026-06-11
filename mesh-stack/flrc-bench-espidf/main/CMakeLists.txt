idf_component_register(SRCS "bench_main.cpp" "autonomous_main.cpp" "nvs_results.cpp" "prbs.cpp"
                       INCLUDE_DIRS "."
                       REQUIRES driver esp_timer nvs_flash)
