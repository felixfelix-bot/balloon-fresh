"""Single env-only key entry point for the gift-wrap publish path.

THE one place signed key material enters the process (ADR-range-sync-cvm §2.3:
"keys via env, never a CLI arg").  The NIP-59 gift-wrap builder and every relay
publisher (ARMED / TX listener / verdict) obtain their secrets from here, so
there is exactly one code path that reads a secret and exactly one place that
enforces the client!=server invariant.

Contract
--------
* Secrets are read from ENVIRONMENT VARIABLES ONLY — this module exposes no
  function that accepts a secret as an argument and the call sites expose no
  key-bearing CLI option.
* The client key MUST differ from the server key.  A shared key makes the
  client unwrap its own gift wraps and self-deliver on its subscription, so
  ``load_and_check_keys()`` refuses to start instead.
* A secret is NEVER logged, traced, or included in a repr/exception message.
  ``redact()`` yields a marker with the encoding kind and length only —
  not a single character of the secret.

Nostr SDK is imported lazily inside :func:`load_keys`, so the env layer itself
has no third-party dependency and can be imported/tested anywhere.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple

__all__ = [
    "ENV_CLIENT_NSEC",
    "ENV_CLIENT_HEX",
    "ENV_RX_NSEC",
    "ENV_RX_HEX",
    "ENV_TX_NSEC",
    "ENV_TX_HEX",
    "ENV_SERVER_NSEC",
    "ENV_SERVER_HEX",
    "EnvKeyError",
    "KeyCollisionError",
    "KeyPair",
    "redact",
    "load_env_secrets",
    "assert_keys_differ",
    "load_keys",
    "load_and_check_keys",
]

log = logging.getLogger("keymaterial")

# --------------------------------------------------------------------------
# Env var names — the ONLY place key material may come from.
# The RX/TX spellings are aliases so the same accessor serves every publisher
# role without the secret ever being passed on a command line.
# --------------------------------------------------------------------------
ENV_CLIENT_NSEC = "CVM_CLIENT_NSEC"
ENV_CLIENT_HEX = "CVM_CLIENT_HEX"
ENV_RX_NSEC = "CVM_RX_NSEC"
ENV_RX_HEX = "CVM_RX_HEX"
ENV_TX_NSEC = "CVM_TX_NSEC"
ENV_TX_HEX = "CVM_TX_HEX"
ENV_SERVER_NSEC = "CVM_SERVER_NSEC"
ENV_SERVER_HEX = "CVM_SERVER_HEX"

_CLIENT_NSEC_VARS = (ENV_CLIENT_NSEC, ENV_RX_NSEC, ENV_TX_NSEC)
_CLIENT_HEX_VARS = (ENV_CLIENT_HEX, ENV_RX_HEX, ENV_TX_HEX)
_SERVER_NSEC_VARS = (ENV_SERVER_NSEC,)
_SERVER_HEX_VARS = (ENV_SERVER_HEX,)


class EnvKeyError(RuntimeError):
    """A required key env var is absent (env only — never a CLI fallback)."""


class KeyCollisionError(RuntimeError):
    """Client and server keys are identical — refuses to start."""


def redact(secret: Optional[str]) -> str:
    """Return a log-safe marker for `secret` (NEVER any secret characters)."""
    if not secret:
        return "<redacted:empty>"
    if secret.startswith("nsec1"):
        kind = "nsec"
    elif len(secret) == 64 and all(c in "0123456789abcdefABCDEF" for c in secret):
        kind = "hex"
    else:
        kind = "opaque"
    return "<redacted:{}:len={}>".format(kind, len(secret))


@dataclass(frozen=True)
class KeyPair:
    """Raw client/server secrets as read from the environment."""

    client: str
    server: str

    def __repr__(self) -> str:  # never leak the secret via repr()
        return "KeyPair(client={}, server={})".format(
            redact(self.client), redact(self.server))


def _first(env: Mapping[str, str], *names: str) -> Optional[str]:
    for name in names:
        value = env.get(name)
        if value and value.strip():
            return value.strip()
    return None


def load_env_secrets(env: Optional[Mapping[str, str]] = None) -> KeyPair:
    """Read client + server key material from env vars ONLY.

    Returns a :class:`KeyPair` of raw secrets (nsec1... or 64-char hex).
    Raises :class:`EnvKeyError` when either side is missing — there is
    deliberately no CLI fallback.
    """
    env = os.environ if env is None else env
    client = _first(env, *( _CLIENT_NSEC_VARS + _CLIENT_HEX_VARS))
    server = _first(env, *(_SERVER_NSEC_VARS + _SERVER_HEX_VARS))
    if not client:
        raise EnvKeyError(
            "missing client key: set {} (or {} / {} / {}) — "
            "env only, never a CLI arg".format(
                ENV_CLIENT_NSEC, ENV_CLIENT_HEX, ENV_RX_NSEC, ENV_TX_NSEC))
    if not server:
        raise EnvKeyError(
            "missing server key: set {} or {} — required for the "
            "client!=server assertion".format(ENV_SERVER_NSEC, ENV_SERVER_HEX))
    pair = KeyPair(client=client, server=server)
    log.info("key material loaded: client=%s server=%s",
             redact(client), redact(server))
    return pair


def assert_keys_differ(client_pub_hex: str, server_pub_hex: str) -> None:
    """ADR §2.3: the client key MUST differ from the server key.

    A shared key makes the client unwrap its own gift wraps and self-deliver
    on the subscription — refuse to start instead.
    """
    if not client_pub_hex or not server_pub_hex:
        raise KeyCollisionError("missing pubkey for the key-difference check")
    if client_pub_hex.lower() == server_pub_hex.lower():
        raise KeyCollisionError(
            "client pubkey == server pubkey ({}…) — refusing to start: the "
            "gift-wrap publisher and the board server must use distinct "
            "keys".format(client_pub_hex[:16]))


def load_keys(secret: str) -> Any:
    """Parse an nsec/hex secret into ``nostr_sdk.Keys`` (lazy SDK import)."""
    import nostr_sdk  # local import: env layer stays dependency-free
    return nostr_sdk.Keys.parse(secret)


def load_and_check_keys(
        env: Optional[Mapping[str, str]] = None) -> Tuple[Any, Any]:
    """The thin accessor: load both keys from env and enforce separation.

    Returns ``(client_keys, server_keys)`` — the single call the gift-wrap
    builder and every relay publisher make.  Raises :class:`EnvKeyError` (env
    missing) or :class:`KeyCollisionError` (client == server).
    """
    pair = load_env_secrets(env)
    client_keys = load_keys(pair.client)
    server_keys = load_keys(pair.server)
    assert_keys_differ(client_keys.public_key().to_hex(),
                       server_keys.public_key().to_hex())
    return client_keys, server_keys
