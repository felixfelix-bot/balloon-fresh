"""Unit tests for tools/keymaterial.py — the single env-only key entry point.

Acceptance (card t_9db98e6d):
  (a) keys loaded from env,
  (b) missing env var raises,
  (c) identical client/server pubkeys raises,
  (d) no secret string appears in captured log output.

All key material here is FAKE (monkeypatched env + an injected fake nostr_sdk).
No real nsec/hex ever enters the process or the repo.
"""

import hashlib
import logging
import sys
import types

import pytest

import keymaterial
from keymaterial import (
    ENV_CLIENT_HEX,
    ENV_CLIENT_NSEC,
    ENV_RX_NSEC,
    ENV_SERVER_HEX,
    ENV_SERVER_NSEC,
    ENV_TX_NSEC,
    EnvKeyError,
    KeyCollisionError,
    assert_keys_differ,
    load_and_check_keys,
    load_env_secrets,
    redact,
)

# Fake secrets — never real key material. Shaped like the real thing only so the
# loader's nsec/hex handling is exercised.
FAKE_CLIENT_NSEC = "nsec1" + "q" * 58
FAKE_SERVER_NSEC = "nsec1" + "p" * 58
FAKE_CLIENT_HEX = "11" * 32
FAKE_SERVER_HEX = "22" * 32


def _install_fake_nostr_sdk(monkeypatch, pubkey_map=None):
    """Inject a minimal fake nostr_sdk for the lazy `load_keys` import.

    `pubkey_map` lets a test force two distinct secrets to map to the SAME
    pubkey (the collision case). Default derivation is sha256(secret).
    """
    ns = types.ModuleType("nostr_sdk")
    forced = dict(pubkey_map or {})

    class PublicKey:
        def __init__(self, h):
            self._h = h

        def to_hex(self):
            return self._h

    class Keys:
        def __init__(self, secret, pub):
            self.secret = secret
            self._pub = pub

        @classmethod
        def parse(cls, secret):
            pub = forced.get(secret,
                             hashlib.sha256(secret.encode()).hexdigest())
            return cls(secret, pub)

        def public_key(self):
            return PublicKey(self._pub)

    setattr(ns, "Keys", Keys)
    setattr(ns, "PublicKey", PublicKey)
    monkeypatch.setitem(sys.modules, "nostr_sdk", ns)
    return ns


# ---------------------------------------------------------------------------
# (a) keys loaded from env
# ---------------------------------------------------------------------------

class TestLoadFromEnv:

    def test_client_and_server_nsec_from_env(self, monkeypatch):
        monkeypatch.setenv(ENV_CLIENT_NSEC, FAKE_CLIENT_NSEC)
        monkeypatch.setenv(ENV_SERVER_NSEC, FAKE_SERVER_NSEC)
        pair = load_env_secrets()
        assert pair.client == FAKE_CLIENT_NSEC
        assert pair.server == FAKE_SERVER_NSEC

    def test_hex_accepted_for_both_sides(self):
        env = {ENV_CLIENT_HEX: FAKE_CLIENT_HEX, ENV_SERVER_HEX: FAKE_SERVER_HEX}
        pair = load_env_secrets(env)
        assert pair.client == FAKE_CLIENT_HEX
        assert pair.server == FAKE_SERVER_HEX

    def test_rx_alias_resolves_client(self):
        env = {ENV_RX_NSEC: FAKE_CLIENT_NSEC, ENV_SERVER_NSEC: FAKE_SERVER_NSEC}
        assert load_env_secrets(env).client == FAKE_CLIENT_NSEC

    def test_tx_alias_resolves_client(self):
        env = {ENV_TX_NSEC: FAKE_CLIENT_NSEC, ENV_SERVER_NSEC: FAKE_SERVER_NSEC}
        assert load_env_secrets(env).client == FAKE_CLIENT_NSEC

    def test_explicit_env_mapping_ignores_process_env(self, monkeypatch):
        monkeypatch.setenv(ENV_CLIENT_NSEC, FAKE_SERVER_NSEC)  # decoy
        env = {ENV_CLIENT_NSEC: FAKE_CLIENT_NSEC, ENV_SERVER_NSEC: FAKE_SERVER_NSEC}
        assert load_env_secrets(env).client == FAKE_CLIENT_NSEC

    def test_accessor_loads_distinct_keys_from_env(self, monkeypatch):
        _install_fake_nostr_sdk(monkeypatch)
        env = {ENV_CLIENT_NSEC: FAKE_CLIENT_NSEC, ENV_SERVER_NSEC: FAKE_SERVER_NSEC}
        client_keys, server_keys = load_and_check_keys(env)
        assert client_keys.public_key().to_hex() != server_keys.public_key().to_hex()
        assert (client_keys.public_key().to_hex()
                == hashlib.sha256(FAKE_CLIENT_NSEC.encode()).hexdigest())


# ---------------------------------------------------------------------------
# (b) missing env var raises
# ---------------------------------------------------------------------------

class TestMissingEnvRaises:

    def test_missing_client_raises(self):
        with pytest.raises(EnvKeyError) as ei:
            load_env_secrets({ENV_SERVER_NSEC: FAKE_SERVER_NSEC})
        assert ENV_CLIENT_NSEC in str(ei.value)
        assert FAKE_SERVER_NSEC not in str(ei.value)  # no value in the error

    def test_missing_server_raises(self):
        with pytest.raises(EnvKeyError) as ei:
            load_env_secrets({ENV_CLIENT_NSEC: FAKE_CLIENT_NSEC})
        assert ENV_SERVER_NSEC in str(ei.value)

    def test_blank_or_whitespace_treated_missing(self):
        with pytest.raises(EnvKeyError):
            load_env_secrets({ENV_CLIENT_NSEC: "   ",
                              ENV_SERVER_NSEC: FAKE_SERVER_NSEC})

    def test_empty_env_raises(self):
        with pytest.raises(EnvKeyError):
            load_env_secrets({})

    def test_accessor_missing_server_raises(self, monkeypatch):
        _install_fake_nostr_sdk(monkeypatch)
        with pytest.raises(EnvKeyError):
            load_and_check_keys({ENV_CLIENT_NSEC: FAKE_CLIENT_NSEC})


# ---------------------------------------------------------------------------
# (c) identical client/server pubkeys raises
# ---------------------------------------------------------------------------

class TestKeyCollision:

    def test_assert_keys_differ_raises_on_identical(self):
        with pytest.raises(KeyCollisionError) as ei:
            assert_keys_differ(FAKE_CLIENT_HEX, FAKE_CLIENT_HEX.upper())
        assert "client" in str(ei.value).lower()

    def test_assert_keys_differ_ok_on_distinct(self):
        assert_keys_differ(FAKE_CLIENT_HEX, FAKE_SERVER_HEX)

    def test_assert_keys_differ_raises_on_empty(self):
        with pytest.raises(KeyCollisionError):
            assert_keys_differ("", FAKE_SERVER_HEX)

    def test_accessor_raises_when_pubkeys_collide(self, monkeypatch):
        # two DISTINCT secrets forced to the same pubkey
        _install_fake_nostr_sdk(monkeypatch, pubkey_map={
            FAKE_CLIENT_NSEC: "ab" * 32,
            FAKE_SERVER_NSEC: "ab" * 32,
        })
        env = {ENV_CLIENT_NSEC: FAKE_CLIENT_NSEC, ENV_SERVER_NSEC: FAKE_SERVER_NSEC}
        with pytest.raises(KeyCollisionError):
            load_and_check_keys(env)


# ---------------------------------------------------------------------------
# (d) no secret string appears in captured log output
# ---------------------------------------------------------------------------

class TestNoSecretInLogs:

    def test_no_secret_in_captured_logs(self, monkeypatch, caplog):
        _install_fake_nostr_sdk(monkeypatch)
        env = {ENV_CLIENT_NSEC: FAKE_CLIENT_NSEC, ENV_SERVER_NSEC: FAKE_SERVER_NSEC}
        with caplog.at_level(logging.DEBUG, logger="keymaterial"):
            load_and_check_keys(env)
        text = caplog.text
        assert FAKE_CLIENT_NSEC not in text
        assert FAKE_SERVER_NSEC not in text
        # and the loader did log a redacted marker (so (d) is not vacuous)
        assert "redacted" in text.lower()

    def test_redact_never_contains_secret_characters(self):
        out = redact(FAKE_CLIENT_NSEC)
        assert FAKE_CLIENT_NSEC not in out
        assert "q" * 8 not in out  # the secret's body must not leak
        assert "redacted" in out.lower()

    def test_keypair_repr_hides_secret(self):
        pair = load_env_secrets({ENV_CLIENT_NSEC: FAKE_CLIENT_NSEC,
                                 ENV_SERVER_NSEC: FAKE_SERVER_NSEC})
        text = repr(pair)
        assert FAKE_CLIENT_NSEC not in text
        assert FAKE_SERVER_NSEC not in text


# ---------------------------------------------------------------------------
# single entry point: usable by BOTH the gift-wrap builder and the publisher
# ---------------------------------------------------------------------------

class TestSingleEntryPoint:

    def test_module_imports_without_nostr_sdk(self, monkeypatch):
        # the env layer must not require the SDK, so any call site can use it
        monkeypatch.setitem(sys.modules, "nostr_sdk", None)
        import importlib
        importlib.reload(keymaterial)
        env = {ENV_CLIENT_NSEC: FAKE_CLIENT_NSEC, ENV_SERVER_NSEC: FAKE_SERVER_NSEC}
        assert keymaterial.load_env_secrets(env).client == FAKE_CLIENT_NSEC

    def test_giftwrap_builder_and_relay_publisher_share_one_accessor(self,
                                                                     monkeypatch):
        """Both call-site shapes obtain keys ONLY via the shared accessor."""
        _install_fake_nostr_sdk(monkeypatch)
        env = {ENV_CLIENT_NSEC: FAKE_CLIENT_NSEC, ENV_SERVER_NSEC: FAKE_SERVER_NSEC}

        seen = []

        def gift_wrap_builder():
            client_keys, server_keys = keymaterial.load_and_check_keys(env)
            seen.append(("wrap", client_keys.public_key().to_hex()))
            return client_keys

        def relay_publisher():
            client_keys, server_keys = keymaterial.load_and_check_keys(env)
            seen.append(("publish", client_keys.public_key().to_hex()))
            return server_keys

        gift_wrap_builder()
        relay_publisher()
        assert len(seen) == 2
        assert seen[0][1] == seen[1][1]  # same client key from the one accessor
