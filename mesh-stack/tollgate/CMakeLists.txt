# ESP-IDF project root for tollgate-balloon-test.
# Minimal skeleton that links tollgate_balloon (+ nucula + secp256k1) so we can
# verify the extracted payment components compile + link for ESP32-C3 and measure
# flash/RAM usage. See docs/BUILD-SIZE-REPORT.md for results.
cmake_minimum_required(VERSION 3.16)

# Pull in the standalone components under components/. main/ is auto-discovered.
# Also pull in tracker/firmware/components/ for lr2021_transport, mesh_adapter,
# pipeline, erasure, frag (radio hardware + mesh fragmentation layers).
set(EXTRA_COMPONENT_DIRS
    "components"
    "../../tracker/firmware/components"
)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(tollgate-balloon-test)
