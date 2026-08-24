idf_component_register(
    SRCS "secp_test.c"
    INCLUDE_DIRS "."
)

# secp256k1 upstream uses static helpers that are intentionally unused per-module;
# silence the warning so it does not get promoted to an error by the IDF defaults.
target_compile_options(${COMPONENT_LIB} PRIVATE -Wno-unused-function)
