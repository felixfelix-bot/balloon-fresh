# Minimal ESP-IDF project to measure isolated secp256k1 flash/RAM cost on ESP32-C3.
#
# Reuses the proven blossom-server secp256k1 component via EXTRA_COMPONENT_DIRS.
# That component is built with the C3-tuned config documented in
# docs/blossom-design.md §4 / §7:
#   ENABLE_MODULE_SCHNORRSIG=1, ENABLE_MODULE_EXTRAKEYS=1,
#   ECMULT_GEN_PREC_BITS=4, ECMULT_WINDOW_SIZE=4  (C3 RAM saving vs tollgate's WINDOW=8)
#
# Only the secp256k1 component is pulled in (not blossom_crypto / mbedtls) so the
# `idf.py size --archives` output isolates libsecp256k1.a cleanly.
cmake_minimum_required(VERSION 3.16)

set(EXTRA_COMPONENT_DIRS
    "${CMAKE_CURRENT_SOURCE_DIR}/../../blossom-server/components/secp256k1"
)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(secp_test)
