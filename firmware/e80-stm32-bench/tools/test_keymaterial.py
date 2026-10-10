#!/usr/bin/env python3
"""test_keymaterial.py — env-only key accessor tests (card t_4c98fbe7).

Covers the three acceptance smoke scenarios (happy path, collision, missing
variable) plus redaction, call-time reads, the hexkey/npub paths, and a
cross-check of the pure-Python secp256k1 derivation against ``coincurve`` when
it is installed.

No real secrets: every key is generated in-process and injected via ``env``.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import io
import os
import secrets
import unittest
import unittest.mock

import keymaterial as km

# ---------------------------------------------------------------------------
# bech32 encoders (test-only helpers, so no third-party dependency is needed)
# ---------------------------------------------------------------------------
_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_GEN = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)


def _polymod(values):
    chk = 1
    for value in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ value
        for i in range(5):
            chk ^= _GEN[i] if ((top >> i) & 1) else 0
    return chk


def _hrp_expand(hrp):
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def _convertbits(data, frombits, tobits):
    acc = bits = 0
    ret = []
    for value in data:
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & ((1 << tobits) - 1))
    if bits:
        ret.append((acc << (tobits - bits)) & ((1 << tobits) - 1))
    return ret


def _bech32_encode(hrp, payload32: bytes) -> str:
    data = _convertbits(list(payload32), 8, 5)
    pm = _polymod(_hrp_expand(hrp) + data + [0, 0, 0, 0, 0, 0]) ^ 1
    chk = [(pm >> 5 * (5 - i)) & 31 for i in range(6)]
    return hrp + "1" + "".join(_CHARSET[x] for x in data + chk)


def _nsec(secret32: bytes) -> str:
    return _bech32_encode("nsec", secret32)


def _npub(secret32: bytes) -> str:
    return _bech32_encode("npub", bytes.fromhex(km._xonly_pubkey(secret32)))


def _hexpub(secret32: bytes) -> str:
    return km._xonly_pubkey(secret32)


class _Env(unittest.TestCase):
    """Base: snapshot/restore every accepted env name around every test.

    ``km.ALL_ENV_NAMES`` (not just the canonical five) so a developer's exported
    ``E80_RX_NSEC``/``CVM_CLIENT_HEX`` alias can never leak into a test.
    """

    KEYS = km.ALL_ENV_NAMES

    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in self.KEYS}
        for k in self.KEYS:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class TestDerivation(_Env):
    def test_xonly_matches_coincurve(self):
        try:
            import coincurve
        except ImportError:  # pragma: no cover - coincurve optional
            self.skipTest("coincurve not installed")
        for _ in range(4):
            secret = secrets.token_bytes(32)
            ref = coincurve.PrivateKey(secret).public_key.format(
                compressed=True)[1:].hex()
            self.assertEqual(km._xonly_pubkey(secret), ref)

    def test_npub_decodes_to_pubkey(self):
        secret = secrets.token_bytes(32)
        self.assertEqual(km._decode_pubkey(_npub(secret)), _hexpub(secret))


class TestHappyPath(_Env):
    def test_smoke1_distinct_nsec_keys(self):
        c, s = secrets.token_bytes(32), secrets.token_bytes(32)
        os.environ[km.ENV_CLIENT_NSEC] = _nsec(c)
        os.environ[km.ENV_SERVER_NSEC] = _nsec(s)
        k = km.load_keys()
        self.assertNotEqual(k.client_pubkey, k.server_pubkey)
        self.assertEqual(k.client_pubkey, _hexpub(c))
        self.assertEqual(k.server_pubkey, _hexpub(s))

    def test_server_pubkey_only(self):
        c, s = secrets.token_bytes(32), secrets.token_bytes(32)
        os.environ[km.ENV_CLIENT_NSEC] = _nsec(c)
        os.environ[km.ENV_SERVER_PUBKEY] = _hexpub(s)
        k = km.load_keys()
        self.assertEqual(k.server_pubkey, _hexpub(s))
        self.assertIsNone(k.server_secret)

    def test_server_npub_accepted(self):
        c, s = secrets.token_bytes(32), secrets.token_bytes(32)
        os.environ[km.ENV_CLIENT_NSEC] = _nsec(c)
        os.environ[km.ENV_SERVER_PUBKEY] = _npub(s)
        self.assertEqual(km.load_keys().server_pubkey, _hexpub(s))

    def test_client_hexkey(self):
        c, s = secrets.token_bytes(32), secrets.token_bytes(32)
        os.environ[km.ENV_CLIENT_HEXKEY] = c.hex()
        os.environ[km.ENV_SERVER_NSEC] = _nsec(s)
        self.assertEqual(km.load_keys().client_pubkey, _hexpub(c))

    def test_client_nsec_and_hexkey_agree(self):
        c, s = secrets.token_bytes(32), secrets.token_bytes(32)
        os.environ[km.ENV_CLIENT_NSEC] = _nsec(c)
        os.environ[km.ENV_CLIENT_HEXKEY] = c.hex()
        os.environ[km.ENV_SERVER_NSEC] = _nsec(s)
        self.assertEqual(km.load_keys().client_pubkey, _hexpub(c))

    def test_client_nsec_and_hexkey_disagree_refused(self):
        c, other, s = (secrets.token_bytes(32) for _ in range(3))
        os.environ[km.ENV_CLIENT_NSEC] = _nsec(c)
        os.environ[km.ENV_CLIENT_HEXKEY] = other.hex()
        os.environ[km.ENV_SERVER_NSEC] = _nsec(s)
        with self.assertRaises(km.KeyMaterialError):
            km.load_keys()

    def test_server_nsec_and_pubkey_disagree_refused(self):
        c, s, other = (secrets.token_bytes(32) for _ in range(3))
        os.environ[km.ENV_CLIENT_NSEC] = _nsec(c)
        os.environ[km.ENV_SERVER_NSEC] = _nsec(s)
        os.environ[km.ENV_SERVER_PUBKEY] = _hexpub(other)
        with self.assertRaises(km.KeyMaterialError):
            km.load_keys()

    def test_relay_auth_read_here(self):
        c, s = secrets.token_bytes(32), secrets.token_bytes(32)
        os.environ[km.ENV_CLIENT_NSEC] = _nsec(c)
        os.environ[km.ENV_SERVER_NSEC] = _nsec(s)
        relay = _nsec(secrets.token_bytes(32))
        os.environ[km.ENV_RELAY_AUTH] = relay
        self.assertEqual(km.load_keys().relay_auth, relay)


class TestCollision(_Env):
    def test_smoke2_same_key_raises_collision(self):
        secret = secrets.token_bytes(32)
        os.environ[km.ENV_CLIENT_NSEC] = _nsec(secret)
        os.environ[km.ENV_SERVER_NSEC] = _nsec(secret)
        with self.assertRaises(km.KeyCollisionError) as ctx:
            km.load_keys()
        msg = str(ctx.exception)
        self.assertIn(_hexpub(secret), msg)          # pubkey is named
        self.assertNotIn(_nsec(secret), msg)         # secret is NOT
        self.assertNotIn(secret.hex(), msg)

    def test_collision_is_a_runtimeerror(self):
        self.assertTrue(issubclass(km.KeyCollisionError, RuntimeError))

    def test_collision_via_pubkey_side(self):
        secret = secrets.token_bytes(32)
        os.environ[km.ENV_CLIENT_NSEC] = _nsec(secret)
        os.environ[km.ENV_SERVER_PUBKEY] = _hexpub(secret)
        with self.assertRaises(km.KeyCollisionError):
            km.load_keys()


class TestMissing(_Env):
    def test_smoke3_missing_client_names_variable(self):
        s = secrets.token_bytes(32)
        os.environ[km.ENV_SERVER_NSEC] = _nsec(s)
        with self.assertRaises(km.MissingKeyError) as ctx:
            km.load_keys()
        msg = str(ctx.exception)
        self.assertIn(km.ENV_CLIENT_NSEC, msg)
        self.assertNotIn(_nsec(s), msg)

    def test_missing_server_names_variable(self):
        c = secrets.token_bytes(32)
        os.environ[km.ENV_CLIENT_NSEC] = _nsec(c)
        with self.assertRaises(km.MissingKeyError) as ctx:
            km.load_keys()
        msg = str(ctx.exception)
        self.assertIn(km.ENV_SERVER_NSEC, msg)
        self.assertIn(km.ENV_SERVER_PUBKEY, msg)
        self.assertNotIn(_nsec(c), msg)


class TestHygiene(_Env):
    def test_smoke_repr_redacts_all_secrets(self):
        c, s = secrets.token_bytes(32), secrets.token_bytes(32)
        relay = secrets.token_bytes(32)
        os.environ[km.ENV_CLIENT_NSEC] = _nsec(c)
        os.environ[km.ENV_SERVER_NSEC] = _nsec(s)
        os.environ[km.ENV_RELAY_AUTH] = relay.hex()
        k = km.load_keys()
        for blob in (repr(k), str(k)):
            self.assertNotIn(_nsec(c), blob)
            self.assertNotIn(_nsec(s), blob)
            self.assertNotIn(c.hex(), blob)
            self.assertNotIn(relay.hex(), blob)
            self.assertIn("redacted", blob)
        # pubkeys are fine to show
        self.assertIn(k.client_pubkey, repr(k))
        self.assertIn(k.server_pubkey, repr(k))

    def test_call_time_read_not_import_time(self):
        c, s = secrets.token_bytes(32), secrets.token_bytes(32)
        # env set AFTER import — must still be honoured (no import-time read)
        os.environ[km.ENV_CLIENT_NSEC] = _nsec(c)
        os.environ[km.ENV_SERVER_NSEC] = _nsec(s)
        self.assertEqual(km.load_keys().client_pubkey, _hexpub(c))
        # change env at call time again — new value observed
        c2 = secrets.token_bytes(32)
        os.environ[km.ENV_CLIENT_NSEC] = _nsec(c2)
        self.assertEqual(km.load_keys().client_pubkey, _hexpub(c2))

    def test_no_module_level_secret_constants(self):
        for name in dir(km):
            if name.startswith("_"):
                continue
            value = getattr(km, name)
            if isinstance(value, str):
                self.assertNotRegex(value, r"^nsec1[0-9a-z]{20,}$")
                self.assertNotRegex(value, r"^[0-9a-fA-F]{64}$")


# ---------------------------------------------------------------------------
# Publish-path wiring (card t_4c98fbe7 STEP 2/3)
# ---------------------------------------------------------------------------
def _optional_import(name):
    """Import a publisher module, or None when it is not on this branch."""
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


class TestPublishPathWiring(_Env):
    """The builder and the relay publisher must use the ONE env-only accessor."""

    def test_builder_resolves_keys_via_load_keys(self):
        gw = _optional_import("nostr_giftwrap")
        if gw is None:
            self.skipTest("nostr_giftwrap not on this branch")
        with unittest.mock.patch.object(
                km, "load_keys", side_effect=RuntimeError("via accessor")):
            with self.assertRaises(RuntimeError) as ctx:
                asyncio.run(gw.build_gift_wrap({"type": "ARMED"}, "npub1xyz"))
        self.assertIn("via accessor", str(ctx.exception))

    def test_publisher_resolves_keys_via_load_keys(self):
        pub = _optional_import("cvm_armed_publisher")
        if pub is None:
            self.skipTest("cvm_armed_publisher not on this branch")
        with unittest.mock.patch.object(
                km, "load_keys", side_effect=RuntimeError("via accessor")):
            with self.assertRaises(RuntimeError) as ctx:
                asyncio.run(pub.run(object(), env={}))
        self.assertIn("via accessor", str(ctx.exception))

    def test_error_taxonomy_shared_with_the_accessor(self):
        for name in ("cvm_armed_publisher", "cvm_tx_listener"):
            mod = _optional_import(name)
            if mod is None:
                self.skipTest("{} not on this branch".format(name))
            self.assertIs(mod.EnvKeyError, km.MissingKeyError)
            self.assertIs(mod.KeyCollisionError, km.KeyCollisionError)

    def test_publisher_main_exits_cleanly_on_missing_key(self):
        pub = _optional_import("cvm_armed_publisher")
        if pub is None:
            self.skipTest("cvm_armed_publisher not on this branch")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = pub.main(["--stop", "x"])
        self.assertEqual(rc, 2)
        self.assertIn(km.ENV_CLIENT_NSEC, err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())


class TestEnvNamePrecedence(_Env):
    """ADR §2.3 / RANGE-TEST-GUIDE.md: the canonical names must resolve here.

    The publish path (`cvm_armed_publisher.run`) resolves keys through
    `keymaterial.load_keys`, so a module that only accepted its own legacy
    ``E80_CLIENT_*`` names would refuse to start on the environment the guide
    tells the operator to export.
    """

    def _distinct(self):
        c, s = secrets.token_bytes(32), secrets.token_bytes(32)
        return c, s

    def test_canonical_cvm_names_resolve(self):
        c, s = self._distinct()
        os.environ["CVM_RX_NSEC"] = _nsec(c)
        os.environ["CVM_SERVER_HEX"] = _hexpub(s)
        kmk = km.load_keys()
        self.assertEqual(kmk.client_pubkey, km._xonly_pubkey(c))
        self.assertEqual(kmk.server_pubkey, km._xonly_pubkey(s))

    def test_canonical_hex_and_server_nsec_resolve(self):
        c, s = self._distinct()
        os.environ["CVM_RX_HEX"] = c.hex()
        os.environ["CVM_SERVER_NSEC"] = _nsec(s)
        kmk = km.load_keys()
        self.assertEqual(kmk.client_pubkey, km._xonly_pubkey(c))
        self.assertEqual(kmk.server_pubkey, km._xonly_pubkey(s))

    def test_client_alias_names_resolve(self):
        for name in ("CVM_CLIENT_NSEC", "E80_RX_NSEC", "E80_CLIENT_NSEC"):
            with self.subTest(client_nsec=name):
                self.setUp()
                c, s = self._distinct()
                os.environ[name] = _nsec(c)
                os.environ["CVM_SERVER_HEX"] = _hexpub(s)
                self.assertEqual(km.load_keys().client_pubkey,
                                 km._xonly_pubkey(c))
        for name in ("CVM_CLIENT_HEX", "E80_RX_HEX", "E80_CLIENT_HEXKEY"):
            with self.subTest(client_hex=name):
                self.setUp()
                c, s = self._distinct()
                os.environ[name] = c.hex()
                os.environ["CVM_SERVER_HEX"] = _hexpub(s)
                self.assertEqual(km.load_keys().client_pubkey,
                                 km._xonly_pubkey(c))

    def test_server_alias_names_resolve(self):
        for name in ("E80_SERVER_NSEC", "E80_SERVER_PUBKEY"):
            with self.subTest(server=name):
                self.setUp()
                c, s = self._distinct()
                os.environ["CVM_RX_NSEC"] = _nsec(c)
                os.environ[name] = (_nsec(s) if name.endswith("_NSEC")
                                    else _hexpub(s))
                self.assertEqual(km.load_keys().server_pubkey,
                                 km._xonly_pubkey(s))

    def test_relay_auth_alias_resolves(self):
        c, s = self._distinct()
        os.environ["CVM_RX_NSEC"] = _nsec(c)
        os.environ["CVM_SERVER_HEX"] = _hexpub(s)
        os.environ["E80_RELAY_AUTH"] = secrets.token_bytes(32).hex()
        self.assertTrue(km.load_keys().relay_auth)

    def test_canonical_name_wins_over_alias(self):
        c, s, other = (secrets.token_bytes(32) for _ in range(3))
        os.environ["CVM_RX_NSEC"] = _nsec(c)          # canonical
        os.environ["E80_CLIENT_NSEC"] = _nsec(other)  # stale/conflicting alias
        os.environ["CVM_SERVER_HEX"] = _hexpub(s)
        self.assertEqual(km.load_keys().client_pubkey, km._xonly_pubkey(c))

    def test_blank_canonical_does_not_shadow_a_real_alias(self):
        c, s = self._distinct()
        os.environ["CVM_RX_NSEC"] = "   "
        os.environ["E80_RX_NSEC"] = _nsec(c)
        os.environ["CVM_SERVER_HEX"] = _hexpub(s)
        self.assertEqual(km.load_keys().client_pubkey, km._xonly_pubkey(c))

    def test_missing_key_message_names_every_accepted_name(self):
        os.environ["CVM_SERVER_HEX"] = _hexpub(secrets.token_bytes(32))
        with self.assertRaises(km.MissingKeyError) as ctx:
            km.load_keys()
        msg = str(ctx.exception)
        for name in km.CLIENT_NSEC_NAMES + km.CLIENT_HEX_NAMES:
            self.assertIn(name, msg, "{} missing from the error message"
                          .format(name))

    def test_accessor_names_agree_with_the_message_layer(self):
        """One logical key, one name set — no drift between the two accessors."""
        pub = _optional_import("cvm_armed_publisher")
        if pub is None:
            self.skipTest("cvm_armed_publisher not on this branch")
        self.assertEqual(pub.ENV_CLIENT_NSEC, km.ENV_CLIENT_NSEC)
        self.assertEqual(pub.ENV_CLIENT_HEX, km.ENV_CLIENT_HEXKEY)
        self.assertEqual(pub.ENV_SERVER_NSEC, km.ENV_SERVER_NSEC)
        self.assertEqual(pub.ENV_SERVER_HEX, km.ENV_SERVER_PUBKEY)
        self.assertIn(pub.ENV_CLIENT_E80_NSEC, km.CLIENT_NSEC_NAMES)
        self.assertIn(pub.ENV_CLIENT_ALIAS_NSEC, km.CLIENT_NSEC_NAMES)


if __name__ == "__main__":
    unittest.main()
