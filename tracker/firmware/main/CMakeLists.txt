set(COMPONENT_REQUIRES
    RadioLib esp_timer driver bmp280 power_manager telemetry
    antenna_switch sky66112 gps cli
)

if(CONFIG_ENABLE_MESH)
    list(APPEND COMPONENT_REQUIRES pipeline erasure frag mesh_adapter)
endif()

if(CONFIG_ENABLE_TDMA)
    list(APPEND COMPONENT_REQUIRES tdma)
endif()

if(CONFIG_ENABLE_NOSTR_STORE)
    list(APPEND COMPONENT_REQUIRES nostr_store)
endif()

idf_component_register(
    SRCS "app_main.cpp"
    INCLUDE_DIRS "."
    REQUIRES ${COMPONENT_REQUIRES}
)
