idf_component_register(
    SRCS
        "meshcore/Utils.cpp"
        "meshcore/Identity.cpp"
        "meshcore/Packet.cpp"
        "meshcore/Dispatcher.cpp"
        "meshcore/Mesh.cpp"
        "meshcore/StaticPoolPacketManager.cpp"
        "ed25519/fe.c"
        "ed25519/ge.c"
        "ed25519/sc.c"
        "ed25519/sha512.c"
        "ed25519/keypair.c"
        "ed25519/key_exchange.c"
        "ed25519/sign.c"
        "ed25519/verify.c"
        "ed25519/add_scalar.c"
        "ed25519/seed.c"
    INCLUDE_DIRS
        "meshcore"
        "ed25519"
        "esp_idf"
    REQUIRES
        mbedtls
)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wno-unused-parameter -Wno-missing-field-initializers)
target_compile_definitions(${COMPONENT_LIB} PUBLIC ESP_PLATFORM=1)
