if(CONFIG_ENABLE_MESH_RADIO)
    # ── Mesh radio test app: minimal deps, no RadioLib ──
    message(STATUS "Mesh radio app enabled: building mesh_radio_main.c (not app_main.cpp)")
    idf_component_register(
        SRCS "mesh_radio_main.c"
        INCLUDE_DIRS "."
        REQUIRES esp_timer driver lr2021_radio mesh_adapter pipeline erasure frag
    )
    target_include_directories(${COMPONENT_LIB} PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}/../components/lr2021_radio/include
        ${CMAKE_CURRENT_LIST_DIR}/../components/mesh_adapter/include
        ${CMAKE_CURRENT_LIST_DIR}/../components/pipeline/include
        ${CMAKE_CURRENT_LIST_DIR}/../components/erasure/include
        ${CMAKE_CURRENT_LIST_DIR}/../components/frag/include
    )
else()
    # ── Default tracker / tollgate / relay app ──
    set(COMPONENT_REQUIRES
        lr2021_transport esp_timer driver bmp280 power_manager telemetry
        antenna_switch sky66112 gps cli secp256k1
    )

    # Only require RadioLib if its CMakeLists.txt exists (defensive guard; kept from radio-glue)
    if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/../components/RadioLib/CMakeLists.txt")
        list(APPEND COMPONENT_REQUIRES RadioLib)
    else()
        message(WARNING "RadioLib component missing CMakeLists.txt — skipping")
    endif()

    if(CONFIG_ENABLE_MESH)
        list(APPEND COMPONENT_REQUIRES pipeline erasure frag mesh_adapter)
    endif()

    if(CONFIG_ENABLE_TDMA)
        list(APPEND COMPONENT_REQUIRES tdma)
    endif()

    if(CONFIG_ENABLE_NOSTR_STORE)
        list(APPEND COMPONENT_REQUIRES nostr_store)
    endif()

    if(CONFIG_ENABLE_RELAY_MODE)
        list(APPEND COMPONENT_REQUIRES nostr_store secp256k1)
    endif()

    if(CONFIG_ENABLE_MESHCORE)
        list(APPEND COMPONENT_REQUIRES meshcore)
        message(STATUS "MeshCore enabled, adding meshcore to REQUIRES")
    endif()

    set(APP_SRCS "app_main.cpp" "radio_task.cpp" "app_task.cpp")

    if(CONFIG_ENABLE_TOLLGATE)
        list(APPEND APP_SRCS "tollgate_payment_proto.c")
    endif()

    idf_component_register(
        SRCS ${APP_SRCS}
        INCLUDE_DIRS "."
        REQUIRES ${COMPONENT_REQUIRES}
        PRIV_REQUIRES meshcore mesh_adapter nostr_store secp256k1
    )

    target_compile_definitions(${COMPONENT_LIB} PRIVATE
        LR2021_SPI_DEBUG=0
    )
endif()
