# Select source file based on Kconfig:
#   CONFIG_FLRC_CONT_TX=y  → main_cont_tx.cpp (continuous TX benchmarking)
#   Default (n)            → main.cpp (TX+RX combined)
if(CONFIG_FLRC_CONT_TX)
    set(MAIN_SRC "main_cont_tx.cpp")
else()
    set(MAIN_SRC "main.cpp")
endif()

idf_component_register(SRCS "${MAIN_SRC}"
                       INCLUDE_DIRS "."
                       REQUIRES driver esp_timer)
