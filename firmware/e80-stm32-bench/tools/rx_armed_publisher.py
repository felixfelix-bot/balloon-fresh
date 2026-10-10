#!/usr/bin/env python3
"""rx_armed_publisher.py — RX-side ARMED publisher *core* (session authority).

This is the card-specified import surface for the RX-side ARMED publisher core:
session-id minting, the ARMED payload schema, and env-only key loading with the
``client != server`` startup assertion. The publish + re-broadcast-loop layers
import from here instead of reaching into the transport module directly.

The implementation is NOT duplicated here. The single source of truth is:

  * ``cvm_sync.py``            — message layer (ADR-range-sync-cvm.md §2.3):
                                 ``generate_session_id``, ``build_armed``,
                                 ``validate_armed``, ``compute_t0``,
                                 ``ARMED_REQUIRED``.
  * ``cvm_armed_publisher.py`` — RX publisher (transport + core wrappers):
                                 ``generate_session_id``, ``build_armed_payload``,
                                 ``arm_session``, ``load_env_secrets``,
                                 ``assert_keys_differ``, ``load_and_check_keys``,
                                 the relay set and the gift-wrap transport.

This module re-exports that contract under the name the range-sync workstream
references, so callers get one stable import (``import rx_armed_publisher``)
while there remains exactly ONE implementation (and ONE test suite of record:
``test_cvm_sync.py`` + ``test_cvm_armed_publisher.py``).

Contract notes
--------------
* RX is the SOLE session authority:
  ``session_id = urllib.parse.quote(strftime('%y%m%d%H%M'), safe='') + <3-hex>``
  where the 3 lowercase-hex nonce comes from the CSPRNG. The timestamp is
  percent-encoded even though the directive output is pure digits (a no-op), so
  no ``%`` or URL-unsafe residue can ever reach a log-dir name.
* The ARMED payload carries the pinned schema. ``ARMED_PAYLOAD_FIELDS`` below
  is the *required* field set as hardened by Gate-2.5 R1 — it includes
  ``created_at``. (An earlier draft listed only
  ``session_id, stop, t_ready_utc, preset_hash, seq``; the reviewed contract
  made ``created_at`` REQUIRED so an ARMED that omits it can never skip the
  freshness window. Do not drop it.)
* Key material is read from ENV VARS ONLY — there is deliberately no CLI
  fallback. ``cvm_armed_publisher.build_parser`` exposes no key/secret option.
* The client key MUST differ from the server key; ``assert_keys_differ`` raises
  ``KeyCollisionError`` otherwise (a shared key self-delivers on subscribe).

Importable without ``nostr_sdk`` (the SDK is touched only inside lazy key
loading / the transport), so the core is unit-testable in a bare Python image.

Run:  python3 -m pytest tools/test_rx_armed_publisher.py -v
"""

from __future__ import annotations

import os
import sys

# Sibling imports (cvm_sync, cvm_armed_publisher) — same convention as the other
# tools/ modules: make sure this file's directory is importable.
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import cvm_sync as _cvm_sync  # noqa: E402
import cvm_armed_publisher as _core  # noqa: E402

# ---------------------------------------------------------------------------
# Schema constants (single source of truth: cvm_sync / cvm_armed_publisher)
# ---------------------------------------------------------------------------

#: Required ARMED fields as consumed by ``cvm_sync.validate_armed``. Includes
#: ``created_at`` (Gate-2.5 R1); see the module docstring.
ARMED_PAYLOAD_FIELDS = _cvm_sync.ARMED_REQUIRED

#: The full on-the-wire ARMED envelope (``type`` + required + ``author``).
ARMED_FIELDS = _core.ARMED_FIELDS

#: Gift-wrap kind (NIP-59 outer wrap) — re-exported for the publish layer.
KIND_GIFT_WRAP = _cvm_sync.KIND_GIFT_WRAP

#: Relay failover set (dead relays already filtered) — re-exported.
FAILOVER_RELAYS = _core.FAILOVER_RELAYS

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

EnvKeyError = _core.EnvKeyError
KeyCollisionError = _core.KeyCollisionError
PlaintextKindError = _core.PlaintextKindError

# ---------------------------------------------------------------------------
# Session authority + ARMED payload (delegates to the canonical implementation)
# ---------------------------------------------------------------------------

generate_session_id = _core.generate_session_id
validate_session_id = _core.validate_session_id
build_armed_payload = _core.build_armed_payload
arm_session = _core.arm_session
preset_hash_for = _core.preset_hash_for

#: Explicit alias: "mint" is the verb the session-authority contract uses.
mint_session_id = _core.generate_session_id

# ---------------------------------------------------------------------------
# Env-only key loading + client/server separation
# ---------------------------------------------------------------------------

load_env_secrets = _core.load_env_secrets
assert_keys_differ = _core.assert_keys_differ
load_keys = _core.load_keys
load_and_check_keys = _core.load_and_check_keys
tx_npub_from_env = _core.tx_npub_from_env

# ---------------------------------------------------------------------------
# Relay set + CLI (for the publish/loop layers)
# ---------------------------------------------------------------------------

failover_relays = _core.failover_relays
build_parser = _core.build_parser

__all__ = [
    # schema
    "ARMED_PAYLOAD_FIELDS", "ARMED_FIELDS", "KIND_GIFT_WRAP",
    "FAILOVER_RELAYS",
    # errors
    "EnvKeyError", "KeyCollisionError", "PlaintextKindError",
    # session authority + payload
    "generate_session_id", "mint_session_id", "validate_session_id",
    "build_armed_payload", "arm_session", "preset_hash_for",
    # keys
    "load_env_secrets", "assert_keys_differ", "load_keys",
    "load_and_check_keys", "tx_npub_from_env",
    # relays + cli
    "failover_relays", "build_parser",
]
