idf_component_register(SRCS "bench_main.cpp" "autonomous_main.cpp" "range_test.cpp" "dump_main.cpp" "spi_loopback.cpp" "continuity_test.cpp" "fifo_test.cpp" "profile_rx.cpp" "nvs_results.cpp" "prbs.cpp"
                       INCLUDE_DIRS "."
                       REQUIRES driver esp_timer nvs_flash gps)
