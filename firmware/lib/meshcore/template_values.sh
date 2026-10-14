# Single source of truth for the meshcore sizing constants, as plain text.
#
# WHY THIS EXISTS: a MeshCore packet header that is one byte wider than the
# firmware allows must fail at build time, not at 20000 m. Compiled constants
# live in meshcodec.h / mesh.h / meshsim.h; meshcore.h.in is the CAPI shim those
# values are rendered into. This file is the independent third copy, and
# test_meshcore.cpp diffs it against the compiled values, so a change that
# updates only one of them fails the host suite instead of shipping.
#
# Format: NAME value, one per line. Add a line here when you add a constant, and
# template_values_match_compiled() will start checking it.
MESH_WIRE_VERSION 1
MESH_HEADER_SIZE 10
MESH_MAX_PAYLOAD 64
MESH_MAX_DATAGRAM 512
MESH_MAX_FRAGS 64
MESH_MAX_NEIGHBORS 8
MESH_NO_WAKE 4294967295
MESH_MAX_BACKOFF_MS 1048576
MESH_MAX_QUEUE 256
MESH_NODES 8
