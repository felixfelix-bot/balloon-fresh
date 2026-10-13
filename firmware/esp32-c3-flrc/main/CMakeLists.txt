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

# CONTINUOUS_TX: infinite TX loop for LA benchmark (no TX_PKT_COUNT limit).
# Enable via:  idf.py -DCONTINUOUS_TX=1 build
if(DEFINED CONTINUOUS_TX AND CONTINUOUS_TX)
    target_compile_definitions(${COMPONENT_LIB} PRIVATE CONTINUOUS_TX)
endif()

# Configurable TX payload size for payload-size sweep.
# Default 255 if not set.  Override via:  idf.py -DTX_PKT_SIZE=64 build
if(DEFINED TX_PKT_SIZE AND NOT TX_PKT_SIZE STREQUAL "")
    target_compile_definitions(${COMPONENT_LIB} PRIVATE TX_PKT_SIZE=${TX_PKT_SIZE})
endif()
