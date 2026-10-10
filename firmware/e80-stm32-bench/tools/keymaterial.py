#!/usr/bin/env python3
"""keymaterial.py — the ONE env-only source of signed key material.

Card t_4c98fbe7 (e80-bench).  Environment variables are the ONLY source of
signed key material for the gift-wrap publish path.  This module is the single
entry point: the gift-wrap builder and the relay publisher both call
:func:`load_keys`, and no other module in ``tools/`` reads a secret.

Guarantees
----------
* **One accessor.**  :func:`load_keys` is the only public function that returns
  key material.  It is the only place a secret enters the process.
* **Call-time reads.**  Every value is read from ``os.environ`` *inside*
  :func:`load_keys`.  There are no module-level secret constants, no
  ``@lru_cache``, and no import-time reads, so setting the environment after the
  import still works and a stale value can never be captured.
* **No literals, no disk reads.**  Secrets are never hard-coded and never read
  from a file on this path.
* **No logging of secrets.**  :class:`KeyMaterial` redacts every secret in its
  ``__repr__``/``__str__``; error messages name variables and pubkeys only.
* **Hard separation.**  ``client_pubkey`` MUST differ from ``server_pubkey``.
  A collision raises :class:`KeyCollisionError` (a distinct type) before any
  relay is contacted — a shared key makes the client unwrap its own gift wraps
  and self-deliver on its subscription.

Environment variables (exact names)
-----------------------------------
Accepted names, canonical first — the canonical name always wins when several
are set, and every alias is read from the environment only (ADR-range-sync-cvm
§2.3 lists the same precedence):

Client key (required, exactly one *combination*) — the RX/publisher role:
    ``CVM_RX_NSEC`` / ``CVM_RX_HEX``          — canonical (see RANGE-TEST-GUIDE.md)
    ``CVM_CLIENT_NSEC`` / ``CVM_CLIENT_HEX``  — aliases (shared)
    ``E80_RX_NSEC`` / ``E80_RX_HEX``          — E80_* aliases (RX-only)
    ``E80_CLIENT_NSEC`` / ``E80_CLIENT_HEXKEY`` — legacy names of this module (shared)
Either an nsec or a hex secret may be set; if BOTH are set they must resolve
to the same pubkey, otherwise :func:`load_keys` refuses (an ambiguous key is a
configuration bug).  Two names of the *same* kind are not an error: the
canonical one wins.

Client key for the TX/listener role (``TX_CLIENT_NSEC_NAMES`` /
``TX_CLIENT_HEX_NAMES``, passed by ``cvm_tx_listener.load_and_check_keys``):
    ``CVM_TX_NSEC`` / ``CVM_TX_HEX``          — canonical TX name
    plus every SHARED alias above (``CVM_CLIENT_*``, ``E80_CLIENT_*``).
The RX-role-only names — ``CVM_RX_NSEC``/``CVM_RX_HEX`` (canonical) and the
``E80_RX_NSEC``/``E80_RX_HEX`` aliases — are NEVER read for the TX role, so a
host that exports both roles cannot sign TX traffic with the RX key.  The
exclusion is by name (``RX_ROLE_NSEC_NAMES``/``RX_ROLE_HEX_NAMES``), not by
position, and is asserted at import time by ``_assert_role_separation``.

Server key material (required):
    ``CVM_SERVER_NSEC``   — bech32 ``nsec1...`` (its pubkey is derived)
    ``CVM_SERVER_HEX``    — x-only 64-char hex pubkey or ``npub1...``
  ``E80_SERVER_NSEC`` / ``E80_SERVER_PUBKEY`` are accepted aliases.  At least one
  must be set; when both are set they must agree.  The server pubkey backs the
  ``client != server`` assertion.

Relay auth (optional):
    ``CVM_RELAY_AUTH``    — bech32 ``nsec1...`` or 64-char hex relay-auth key
                            (``E80_RELAY_AUTH`` is accepted as an alias).
  Read here (not at the call site) when the publish path needs relay auth.

Pure standard library: bech32 + secp256k1 are implemented locally, so the
module imports and runs in a bare image with no third-party dependency.

Run:  python3 -m pytest tools/test_keymaterial.py -v
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, Sequence

__all__ = [
    "load_keys",
    "KeyMaterial",
    "KeyMaterialError",
    "MissingKeyError",
    "KeyCollisionError",
    "ENV_CLIENT_NSEC",
    "ENV_CLIENT_HEXKEY",
    "ENV_SERVER_NSEC",
    "ENV_SERVER_PUBKEY",
    "ENV_RELAY_AUTH",
    "CLIENT_NSEC_NAMES",
    "CLIENT_HEX_NAMES",
    "RX_ROLE_NSEC_NAMES",
    "RX_ROLE_HEX_NAMES",
    "TX_CLIENT_NSEC_NAMES",
    "TX_CLIENT_HEX_NAMES",
    "ENV_TX_CLIENT_NSEC",
    "ENV_TX_CLIENT_HEX",
    "SERVER_NSEC_NAMES",
    "SERVER_PUBKEY_NAMES",
    "RELAY_AUTH_NAMES",
    "ALL_ENV_NAMES",
]

# ---------------------------------------------------------------------------
# Env var names — the ONLY place key material may come from.
#
# Precedence is ADR-range-sync-cvm §2.3's: the canonical ``CVM_*`` name first,
# then the alias chain.  ``load_env_secrets()`` in cvm_armed_publisher.py uses
# exactly the same order, and RANGE-TEST-GUIDE.md documents the canonical names
# as the operator interface, so the publish path (which resolves keys through
# this module) must accept them.
# ---------------------------------------------------------------------------
ENV_CLIENT_NSEC = "CVM_RX_NSEC"
ENV_CLIENT_HEXKEY = "CVM_RX_HEX"
ENV_SERVER_NSEC = "CVM_SERVER_NSEC"
ENV_SERVER_PUBKEY = "CVM_SERVER_HEX"
ENV_RELAY_AUTH = "CVM_RELAY_AUTH"

#: Accepted aliases (canonical names above always win when several are set).
ENV_CLIENT_ALIAS_NSEC = "CVM_CLIENT_NSEC"
ENV_CLIENT_ALIAS_HEX = "CVM_CLIENT_HEX"
ENV_CLIENT_E80_NSEC = "E80_RX_NSEC"
ENV_CLIENT_E80_HEX = "E80_RX_HEX"
ENV_CLIENT_LEGACY_NSEC = "E80_CLIENT_NSEC"
ENV_CLIENT_LEGACY_HEX = "E80_CLIENT_HEXKEY"
ENV_SERVER_E80_NSEC = "E80_SERVER_NSEC"
ENV_SERVER_E80_PUBKEY = "E80_SERVER_PUBKEY"
ENV_RELAY_AUTH_E80 = "E80_RELAY_AUTH"

#: The TX role's own client key (RANGE-TEST-GUIDE.md TX step: ``CVM_TX_*``).
ENV_TX_CLIENT_NSEC = "CVM_TX_NSEC"
ENV_TX_CLIENT_HEX = "CVM_TX_HEX"

#: Accepted env names per logical value, in precedence order (RX role).
CLIENT_NSEC_NAMES = (ENV_CLIENT_NSEC, ENV_CLIENT_ALIAS_NSEC,
                     ENV_CLIENT_E80_NSEC, ENV_CLIENT_LEGACY_NSEC)
CLIENT_HEX_NAMES = (ENV_CLIENT_HEXKEY, ENV_CLIENT_ALIAS_HEX,
                    ENV_CLIENT_E80_HEX, ENV_CLIENT_LEGACY_HEX)

#: RX-ROLE-ONLY names: the canonical ``CVM_RX_*`` names and the ``E80_RX_*``
#: aliases.  They identify the publisher side, so a TX-role host must never read
#: them — that is what role separation means here.  Spelled out explicitly
#: (never derived by index slicing) so re-ordering or inserting into
#: ``CLIENT_*_NAMES`` cannot silently smuggle one into the TX chain.
RX_ROLE_NSEC_NAMES = (ENV_CLIENT_NSEC, ENV_CLIENT_E80_NSEC)
RX_ROLE_HEX_NAMES = (ENV_CLIENT_HEXKEY, ENV_CLIENT_E80_HEX)

#: TX-role chain: its own canonical ``CVM_TX_*`` name first, then every SHARED
#: client name, built by EXCLUDING :data:`RX_ROLE_NSEC_NAMES` /
#: :data:`RX_ROLE_HEX_NAMES` from the RX chain.  What this actually guarantees:
#: (1) NO RX-role-only spelling (``CVM_RX_NSEC``/``CVM_RX_HEX``/``E80_RX_NSEC``/
#: ``E80_RX_HEX``) is ever read for the TX role, whatever the order of
#: ``CLIENT_*_NAMES``; (2) the SHARED names (``CVM_CLIENT_NSEC``/
#: ``CVM_CLIENT_HEX``/``E80_CLIENT_NSEC``/``E80_CLIENT_HEXKEY``) stay accepted
#: for BOTH roles, in their original relative precedence order.
TX_CLIENT_NSEC_NAMES = (ENV_TX_CLIENT_NSEC,) + tuple(
    name for name in CLIENT_NSEC_NAMES if name not in RX_ROLE_NSEC_NAMES)
TX_CLIENT_HEX_NAMES = (ENV_TX_CLIENT_HEX,) + tuple(
    name for name in CLIENT_HEX_NAMES if name not in RX_ROLE_HEX_NAMES)

SERVER_NSEC_NAMES = (ENV_SERVER_NSEC, ENV_SERVER_E80_NSEC)
SERVER_PUBKEY_NAMES = (ENV_SERVER_PUBKEY, ENV_SERVER_E80_PUBKEY)
RELAY_AUTH_NAMES = (ENV_RELAY_AUTH, ENV_RELAY_AUTH_E80)

#: Every name this module reads — handy for tests that must scrub the
#: environment completely before asserting on a missing key.
ALL_ENV_NAMES = tuple(dict.fromkeys(
    tuple(CLIENT_NSEC_NAMES) + tuple(CLIENT_HEX_NAMES)
    + tuple(TX_CLIENT_NSEC_NAMES) + tuple(TX_CLIENT_HEX_NAMES)
    + tuple(SERVER_NSEC_NAMES) + tuple(SERVER_PUBKEY_NAMES)
    + tuple(RELAY_AUTH_NAMES)))


def _assert_role_separation() -> None:
    """Import-time invariant: a TX chain never carries an RX-role-only name.

    Guards the guarantee above against a future edit (for instance a return to
    positional slicing): the module fails to import — loudly — rather than
    silently letting the TX role read and sign with an RX key.
    """
    overlap = sorted((set(TX_CLIENT_NSEC_NAMES) & set(RX_ROLE_NSEC_NAMES))
                     | (set(TX_CLIENT_HEX_NAMES) & set(RX_ROLE_HEX_NAMES)))
    if overlap:
        raise AssertionError(
            "role separation violated: RX-role-only env name(s) {} appear in a "
            "TX key chain".format(", ".join(overlap)))


_assert_role_separation()


# ---------------------------------------------------------------------------
# Errors — loud, actionable, and never echoing a secret.
# ---------------------------------------------------------------------------
class KeyMaterialError(RuntimeError):
    """Base class for key-material configuration errors."""


class MissingKeyError(KeyMaterialError):
    """A required key env var is absent (env only — never a CLI fallback)."""


class KeyCollisionError(KeyMaterialError):
    """Client and server keys resolve to the same pubkey — refuses to publish."""


# ---------------------------------------------------------------------------
# Minimal bech32 + secp256k1 (no third-party dependency).
# ---------------------------------------------------------------------------
_BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32_GENERATOR = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)

# secp256k1 domain parameters.
_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_GX = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
_GY = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8


def _bech32_polymod(values):
    chk = 1
    for value in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ value
        for i in range(5):
            chk ^= _BECH32_GENERATOR[i] if ((top >> i) & 1) else 0
    return chk


def _bech32_hrp_expand(hrp):
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def _bech32_decode(bech):
    """Return ``(hrp, data5)`` or raise ValueError.  Checksum-verified."""
    if not isinstance(bech, str):
        raise ValueError("bech32 value must be a string")
    if any(ord(c) < 33 or ord(c) > 126 for c in bech):
        raise ValueError("bech32 value has an invalid character")
    if bech.lower() != bech and bech.upper() != bech:
        raise ValueError("bech32 value is mixed case")
    bech = bech.lower()
    pos = bech.rfind("1")
    if pos < 1 or pos + 7 > len(bech) or len(bech) > 90:
        raise ValueError("bech32 value has an invalid separator position")
    hrp = bech[:pos]
    if any(c not in _BECH32_CHARSET for c in bech[pos + 1:]):
        raise ValueError("bech32 value has an invalid data character")
    data = [_BECH32_CHARSET.find(c) for c in bech[pos + 1:]]
    if _bech32_polymod(_bech32_hrp_expand(hrp) + data) != 1:
        raise ValueError("bech32 checksum failed")
    return hrp, data[:-6]


def _convertbits(data, frombits, tobits, pad=True):
    acc = 0
    bits = 0
    ret = []
    maxv = (1 << tobits) - 1
    for value in data:
        if value < 0 or (value >> frombits):
            raise ValueError("invalid value in bech32 data")
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        raise ValueError("invalid padding in bech32 data")
    return ret


def _decode_secret(value: str) -> bytes:
    """nsec1... (bech32) or 64-hex -> 32-byte secp256k1 secret."""
    text = value.strip()
    if text.lower().startswith("nsec1"):
        hrp, data5 = _bech32_decode(text)
        if hrp != "nsec":
            raise ValueError("expected an nsec1... value")
        raw = bytes(_convertbits(data5, 5, 8, False))
        if len(raw) != 32:
            raise ValueError("nsec payload is not 32 bytes")
    elif len(text) == 64 and all(c in "0123456789abcdefABCDEF" for c in text):
        raw = bytes.fromhex(text)
    else:
        raise ValueError("secret is neither bech32 nsec1... nor 64-char hex")
    return raw


def _decode_pubkey(value: str) -> str:
    """x-only 64-hex or npub1... -> x-only 64-char lowercase hex pubkey."""
    text = value.strip()
    if text.lower().startswith("npub1"):
        hrp, data5 = _bech32_decode(text)
        if hrp != "npub":
            raise ValueError("expected an npub1... value")
        raw = bytes(_convertbits(data5, 5, 8, False))
        if len(raw) != 32:
            raise ValueError("npub payload is not 32 bytes")
        return raw.hex()
    if len(text) == 64 and all(c in "0123456789abcdefABCDEF" for c in text):
        return text.lower()
    raise ValueError("pubkey is neither bech32 npub1... nor 64-char hex")


def _xonly_pubkey(secret: bytes) -> str:
    """secp256k1 x-only (BIP340) pubkey hex for a 32-byte secret."""
    if len(secret) != 32:
        raise ValueError("secret must be 32 bytes")
    d = int.from_bytes(secret, "big")
    if not (1 <= d < _N):
        raise ValueError("secret is out of range for secp256k1")
    # Scalar multiplication via double-and-add (affine, no dependency).
    x, y = _GX, _GY
    rx, ry = 0, 0  # point at infinity
    for bit in bin(d)[2:]:
        rx, ry = _point_double(rx, ry)
        if bit == "1":
            rx, ry = _point_add(rx, ry, x, y)
    return format(rx, "064x")


def _point_double(x, y):
    if y == 0:
        return 0, 0
    m = (3 * x * x) * pow(2 * y, _P - 2, _P) % _P
    nx = (m * m - 2 * x) % _P
    ny = (m * (x - nx) - y) % _P
    return nx, ny


def _point_add(x1, y1, x2, y2):
    if x1 == 0 and y1 == 0:
        return x2, y2
    if x2 == 0 and y2 == 0:
        return x1, y1
    if x1 == x2:
        if (y1 + y2) % _P == 0:
            return 0, 0
        return _point_double(x1, y1)
    m = (y2 - y1) * pow(x2 - x1, _P - 2, _P) % _P
    nx = (m * m - x1 - x2) % _P
    ny = (m * (x1 - nx) - y1) % _P
    return nx, ny


# ---------------------------------------------------------------------------
# KeyMaterial
# ---------------------------------------------------------------------------
def _redact(value: Optional[str]) -> str:
    return "{redacted}" if value else "{unset}"


@dataclass
class KeyMaterial:
    """The resolved publish-path key material.

    ``client_pubkey`` / ``server_pubkey`` are derived x-only hex pubkeys.  The
    secret fields are redacted by ``__repr__``/``__str__`` so a traceback or a
    log line can never leak them.
    """

    client_secret: str
    client_pubkey: str
    server_pubkey: str
    server_secret: Optional[str] = None
    relay_auth: Optional[str] = None

    def __repr__(self) -> str:
        return (
            "KeyMaterial(client_pubkey={!r}, server_pubkey={!r}, "
            "client_secret={}, server_secret={}, relay_auth={})".format(
                self.client_pubkey,
                self.server_pubkey,
                _redact(self.client_secret),
                _redact(self.server_secret),
                _redact(self.relay_auth),
            )
        )

    __str__ = __repr__


# ---------------------------------------------------------------------------
# The single accessor.
# ---------------------------------------------------------------------------

# Required environment variables, read AT CALL TIME inside load_keys()
# (canonical name first, then the accepted aliases — see the name tuples above):
#   CVM_RX_NSEC      (nsec1...) OR CVM_RX_HEX     (64-hex)  -> client key
#                     aliases: CVM_CLIENT_NSEC/HEX, E80_RX_NSEC/HEX,
#                              E80_CLIENT_NSEC/E80_CLIENT_HEXKEY
#   CVM_SERVER_NSEC  (nsec1...) and/or CVM_SERVER_HEX (hex/npub)
#                     aliases: E80_SERVER_NSEC / E80_SERVER_PUBKEY
#   CVM_RELAY_AUTH   (nsec1.../64-hex)  optional relay auth  (alias E80_RELAY_AUTH)
# The TX listener passes the TX_CLIENT_*_NAMES tuple: CVM_TX_NSEC / CVM_TX_HEX
# first, then the SHARED aliases (CVM_CLIENT_*, E80_CLIENT_*).  The RX-role-only
# names (CVM_RX_*, E80_RX_*) are excluded by construction — see
# RX_ROLE_NSEC_NAMES / RX_ROLE_HEX_NAMES — so a host exporting both roles can
# never sign TX traffic with the RX key.
def load_keys(*, client_names: Optional[Sequence[str]] = None,
              client_hex_names: Optional[Sequence[str]] = None) -> KeyMaterial:
    """Resolve all publish-path key material from the environment.

    ``client_names``/``client_hex_names`` select which env names hold *this
    role's* client key: the publisher keeps the defaults (``CVM_RX_*`` first),
    the TX listener passes :data:`TX_CLIENT_NSEC_NAMES` /
    :data:`TX_CLIENT_HEX_NAMES` so a ``CVM_TX_*``-only environment resolves.

    Reads ``os.environ`` at call time (no cache, no import-time read) and
    returns a :class:`KeyMaterial` with derived x-only pubkeys.  Raises
    :class:`MissingKeyError` when a required variable is absent (naming the
    variable only) and :class:`KeyCollisionError` when the client and server
    keys resolve to the same pubkey.
    """
    env = os.environ
    nsec_names = tuple(client_names or CLIENT_NSEC_NAMES)
    hex_names = tuple(client_hex_names or CLIENT_HEX_NAMES)

    # --- client key: nsec and/or hexkey --------------------------------
    client_nsec = _first_env(env, *nsec_names)
    client_hex = _first_env(env, *hex_names)
    if not client_nsec and not client_hex:
        raise MissingKeyError(
            "no client key is set; export {} or {} (accepted aliases: {})"
            .format(nsec_names[0], hex_names[0],
                    ", ".join(nsec_names[1:] + hex_names[1:])))
    client_secret = client_nsec or client_hex
    client_pubkey = _xonly_pubkey(_decode_secret(client_secret))
    if client_nsec and client_hex:
        other = _xonly_pubkey(_decode_secret(client_hex))
        if other != client_pubkey:
            raise KeyMaterialError(
                "{} and {} are both set but resolve to different pubkeys "
                "({} vs {}); export exactly one".format(
                    ENV_CLIENT_NSEC, ENV_CLIENT_HEXKEY, client_pubkey, other))

    # --- server key material -------------------------------------------
    server_nsec = _first_env(env, *SERVER_NSEC_NAMES)
    server_pub_env = _first_env(env, *SERVER_PUBKEY_NAMES)
    if not server_nsec and not server_pub_env:
        raise MissingKeyError(
            "no server key is set; export {} or {} (aliases: {} / {})"
            .format(ENV_SERVER_NSEC, ENV_SERVER_PUBKEY, ENV_SERVER_E80_NSEC,
                    ENV_SERVER_E80_PUBKEY))
    if server_nsec:
        server_pubkey = _xonly_pubkey(_decode_secret(server_nsec))
        if server_pub_env and _decode_pubkey(server_pub_env) != server_pubkey:
            raise KeyMaterialError(
                "{} and {} disagree ({} vs {}); export matching values".format(
                    ENV_SERVER_NSEC, ENV_SERVER_PUBKEY, server_pubkey,
                    _decode_pubkey(server_pub_env)))
    else:
        server_pubkey = _decode_pubkey(server_pub_env)

    # --- relay auth (optional) -----------------------------------------
    relay_auth = _first_env(env, *RELAY_AUTH_NAMES) or None

    # --- the hard invariant: compare DERIVED PUBKEYS only ---------------
    if client_pubkey == server_pubkey:
        raise KeyCollisionError(
            "client key and server key resolve to the same pubkey "
            "(x-only {}); refusing to publish".format(client_pubkey))

    return KeyMaterial(
        client_secret=client_secret,
        client_pubkey=client_pubkey,
        server_pubkey=server_pubkey,
        server_secret=server_nsec or None,
        relay_auth=relay_auth,
    )


def _clean(value: Optional[str]) -> str:
    return value.strip() if isinstance(value, str) else ""


def _first_env(env, *names: str) -> str:
    """First set, non-blank value among ``names`` (precedence order).

    A blank/whitespace-only value counts as unset, so ``export CVM_RX_NSEC=``
    cannot silently shadow a real alias.
    """
    for name in names:
        value = _clean(env.get(name))
        if value:
            return value
    return ""
