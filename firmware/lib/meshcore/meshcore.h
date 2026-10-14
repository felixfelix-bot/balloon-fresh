// Generated from template_values.sh by scripts/gen_meshcore_header.py.
// Do not edit by hand: change the constant's single source of truth instead.
#pragma once

#include <cstdint>

namespace balloon {
namespace mesh {
namespace tpl {

constexpr uint8_t  MESH_WIRE_VERSION   = 1u;
constexpr uint8_t  MESH_HEADER_SIZE    = 10u;
constexpr uint8_t  MESH_MAX_PAYLOAD    = 64u;
constexpr uint32_t MESH_MAX_DATAGRAM   = 512u;
constexpr uint8_t  MESH_MAX_FRAGS      = 64u;
constexpr uint8_t  MESH_MAX_NEIGHBORS  = 8u;
constexpr uint32_t MESH_NO_WAKE        = 4294967295u;
constexpr uint32_t MESH_MAX_BACKOFF_MS = 1048576u;
constexpr uint32_t MESH_MAX_QUEUE      = 256u;
constexpr uint8_t  MESH_NODES          = 8u;

}  // namespace tpl
}  // namespace mesh
}  // namespace balloon
