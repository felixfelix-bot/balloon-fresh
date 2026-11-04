#!/usr/bin/env python3
"""test_keymaterial_safety.py — collision, redaction and no-key-file-access.

Card t_143add66 (e80-bench): "Add env-driven unit tests for keymaterial module"
— this file is the *safety* half of that card, complementary to the behaviour
suite in ``tools/test_keymaterial.py``.

What it pins
------------
1. **Collision.** Client and server key material set to the SAME key must raise
   ``KeyCollisionError`` (a ``RuntimeError`` subclass), with a message that names
   the colliding x-only pubkey and refuses to publish — and leaks nothing.
2. **Redaction.** ``repr(k)``, ``str(k)`` and ``f"{k!r}"`` interpolation all show
   the module's ``{redacted}`` marker and contain none of the secret strings.
3. **No key-file access — static.** ``keymaterial.py`` and every ``tools/``
   module that consumes it (discovered by AST, not by import) contain no file
   read whose path is key-shaped, and no ``*_FILE``-style env lookup.
4. **No key-file access — runtime.** With ``load_keys()`` under a poisoned
   ``builtins.open`` / ``Path.read_text`` / ``Path.read_bytes`` the loader still
   returns a ``KeyMaterial``: the loader is env-only, demonstrated not asserted.

Provenance / reconciliation (important)
--------------------------------------
The brief for this task asked for ``tools/tests/test_keymaterial_safety.py`` and
told us to use fixtures from ``tools/tests/conftest.py`` (``TEST_HEX_A``,
``TEST_HEX_B``, ``TEST_HEX_SERVER``, ``nsec_from_hex``, ``set_env``,
``clear_env``, ``client_secrets``).  Neither of those paths exists anywhere in
this repo — not on disk, not in any local or remote ref, not in any other
worktree — and no ref has ever contained a repo-root ``tools/`` directory for
this project.  The real module lives at
``firmware/e80-stm32-bench/tools/keymaterial.py`` on branch
``pr/e80-cvm-consolidated``, which is where the card's own PRECONDITION points.

So this file re-bases on the real artifact: same file name, real tools/
directory, on a branch that actually contains ``keymaterial.py``.  Because the
briefed conftest does not exist and the task allows exactly one new file, the
briefed fixture *names* are provided locally below — ``TEST_HEX_A``,
``TEST_HEX_B``, ``TEST_HEX_SERVER``, ``nsec_from_hex``, ``set_env``,
``clear_env``, ``client_secrets`` — defined against the module's real
``ALL_ENV_NAMES`` and real behaviour.

No key literals: every secret is derived in-process.  ``TEST_HEX_A`` is the
scalar ``d = 17`` and the collision key is ``d = 1`` (whose x-only pubkey is the
published secp256k1 generator X, used here as an *independent* reference — see
``GENERATOR_X``).  No key file is created or read.

Run (from ``firmware/e80-stm32-bench``):
    python -m pytest tools/tests/test_keymaterial_safety.py -q
"""

from __future__ import annotations

import ast
import builtins
import contextlib
import io
import os
import pathlib
import re
import sys
import tokenize

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: make ``keymaterial`` importable from tools/.
#
# pytest inserts the *test file's* directory (tools/tests/) into sys.path, not
# the tools/ directory that holds the module under test.  The briefed
# tools/tests/conftest.py would have done this; since this task creates exactly
# one file, the bootstrap lives here.
# ---------------------------------------------------------------------------
TOOLS_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import keymaterial as km  # noqa: E402  (needs the bootstrap above)

# ---------------------------------------------------------------------------
# Fixture replacements for the absent tools/tests/conftest.py (see docstring).
# ---------------------------------------------------------------------------
#: d = 1 -> its x-only pubkey IS the secp256k1 generator X.  Hard-coded as an
#: independent reference so the collision assertion does not merely compare the
#: module against itself.
GENERATOR_X = "79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"

#: Scalar order of secp256k1 (the module's own constant, reused for sampling).
_CURVE_ORDER = km._N


def _secret_hex(scalar: int) -> str:
    """A deterministic, in-range 32-byte secret as lowercase hex (no literals)."""
    if not 1 <= scalar < _CURVE_ORDER:
        raise ValueError("test scalar out of range")
    return format(scalar, "064x")


#: The colliding key: d = 1.
TEST_HEX_ONE = _secret_hex(1)
#: The well-behaved client key: d = 17.
TEST_HEX_A = _secret_hex(17)
#: A second well-behaved key (alternate form / wrong-key paths).
TEST_HEX_B = _secret_hex(42)
#: The server key material for the happy path: d = 99.
TEST_HEX_SERVER = _secret_hex(99)

_BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32_GENERATOR = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)


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


def _bech32_encode(hrp: str, data8: bytes) -> str:
    """encode(hrp, bytes) -> bech32 string (test-only, no third-party dep)."""
    acc, bits, data5 = 0, 0, []
    for byte in data8:
        acc = (acc << 8) | byte
        bits += 8
        while bits >= 5:
            bits -= 5
            data5.append((acc >> bits) & 31)
    if bits:
        data5.append((acc << (5 - bits)) & 31)
    hrp_expanded = _bech32_hrp_expand(hrp)
    polymod = _bech32_polymod(hrp_expanded + data5 + [0] * 6) ^ 1
    checksum = [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]
    return hrp + "1" + "".join(_BECH32_CHARSET[d] for d in data5 + checksum)


def nsec_from_hex(hex_secret: str) -> str:
    """The bech32 ``nsec1...`` form of a 32-byte secret."""
    return _bech32_encode("nsec", bytes.fromhex(hex_secret))


#: Every secret string this suite uses, in both forms the brief names — the hex
#: form and the bech32 ``nsec1...`` form.  Assertions check absence of ALL of
#: these, so a leak of either spelling fails.
client_secrets = (
    TEST_HEX_A,
    TEST_HEX_B,
    TEST_HEX_SERVER,
    nsec_from_hex(TEST_HEX_A),
    nsec_from_hex(TEST_HEX_B),
    nsec_from_hex(TEST_HEX_SERVER),
)


def set_env(**values) -> None:
    """Set env vars (``None`` unsets), the only key source the module reads."""
    for name, value in values.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def clear_env() -> None:
    """Remove every env name the module reads (from the module's own list)."""
    for name in km.ALL_ENV_NAMES:
        os.environ.pop(name, None)


@pytest.fixture(autouse=True)
def _clean_env():
    """No key env var leaks in from the host, and none leaks out."""
    saved = {name: os.environ.get(name) for name in km.ALL_ENV_NAMES}
    clear_env()
    try:
        yield
    finally:
        clear_env()
        for name, value in saved.items():
            if value is not None:
                os.environ[name] = value


def _publish_path_modules() -> list[pathlib.Path]:
    """``keymaterial.py`` plus every tools/ module that consumes it.

    Discovered by AST so the publish path is never *imported* here (importing
    it drags in network-facing machinery).
    """
    modules = [TOOLS_DIR / "keymaterial.py"]
    for path in sorted(TOOLS_DIR.glob("*.py")):
        if path.name == "keymaterial.py" or path.name.startswith("test_"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(a.name == "keymaterial" for a in node.names):
                    modules.append(path)
                    break
            elif isinstance(node, ast.ImportFrom):
                if node.module == "keymaterial":
                    modules.append(path)
                    break
    return modules


# ---------------------------------------------------------------------------
# The static scanner.  Comments and docstrings are stripped first, so prose
# that mentions keys cannot false-positive; a positive control proves the scan
# can actually spot a violation.
# ---------------------------------------------------------------------------
_FLAGGED_PATH = re.compile(r"key|nsec|secret", re.I)
_GATE_ENV_NAME = re.compile(
    r"KEY_FILE|NSEC_FILE|SECRET_FILE|PRIVKEY_FILE|KEY_PATH|NSEC_PATH|"
    r"SECRET_PATH|\w*_FILE\b",
    re.I,
)
_FILE_READS = re.compile(r"\b(open|read_text|read_bytes|readlines)\s*\(")


def _strip_comments_and_docstrings(source: str) -> str:
    """Remove comments and docstrings, keeping every other string literal.

    Only *standalone* strings are docstrings: a literal is blanked when the
    previous significant token ends a statement (NEWLINE/INDENT/DEDENT/start) and
    the next one begins a statement (NEWLINE/ENDMARKER).  A literal passed to a
    call (``open("key_file")``) or assigned to a name therefore SURVIVES, which
    is exactly what lets the scan below see a real violation.  (An earlier
    version blanked every string token and could not spot one -- see
    ``test_scanner_is_not_vacuous``, which pins that mistake.)
    """
    tokens = [tok for tok in
              tokenize.generate_tokens(io.StringIO(source).readline)
              if tok.type not in (tokenize.NL, tokenize.COMMENT)]
    out = []
    for index, tok in enumerate(tokens):
        if tok.type == tokenize.STRING and tok.string[:1] in "\"'":
            previous = tokens[index - 1].type if index else None
            following = tokens[index + 1].type if index + 1 < len(tokens) else None
            standalone = previous in (None, tokenize.NEWLINE, tokenize.INDENT,
                                      tokenize.DEDENT)
            if standalone and following in (None, tokenize.NEWLINE,
                                            tokenize.ENDMARKER):
                out.append(tok._replace(string='""'))
                continue
        out.append(tok)
    return tokenize.untokenize(out)


#: Non-key env names the publish path legitimately reads (public npub only).
_NON_KEY_ENV_NAMES = frozenset({"CVM_TX_NPUB", "CVM_RX_NPUB"})

#: An environment-variable name, as opposed to an ordinary identifier.
_ENV_NAME_SHAPE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _resolved_env_names(source: str) -> set:
    """Env names ``source`` actually looks up, module-level constants resolved.

    Catches ``os.environ[name]`` and ``env.get(name)`` whether ``name`` is a
    literal or a module-level string constant, so a ``*_FILE`` lookup cannot
    hide behind a variable.  This is the check that a plain text grep misses.
    """
    tree = ast.parse(source)
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) \
                and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = node.value.value

    def resolve(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return constants.get(node.id)
        return None

    found = set()
    for node in ast.walk(tree):
        argument = None
        if isinstance(node, ast.Call) \
                and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "get" and node.args:
            argument = node.args[0]
        elif isinstance(node, ast.Subscript):
            argument = node.slice
        if argument is None:
            continue
        value = resolve(argument)
        if value and _ENV_NAME_SHAPE.match(value):
            found.add(value)
    return found


def _key_file_violations(source: str) -> list[str]:
    """File reads whose argument is key-shaped, per source text (comments out)."""
    clean = _strip_comments_and_docstrings(source)
    violations = []
    for match in _FILE_READS.finditer(clean):
        opening = clean.find("(", match.end() - 1)
        depth, index = 1, opening + 1
        while index < len(clean) and depth:
            if clean[index] == "(":
                depth += 1
            elif clean[index] == ")":
                depth -= 1
            index += 1
        call = clean[match.end() - 1:index]
        if _FLAGGED_PATH.search(call):
            violations.append("{} -> {}".format(match.group(1), call.strip()))
    for name in _GATE_ENV_NAME.findall(clean):
        violations.append("env lookup of {}".format(name))
    return violations


# ---------------------------------------------------------------------------
# 1. Collision
# ---------------------------------------------------------------------------
class TestCollision:
    def test_key_collision_error_is_a_runtime_error(self):
        assert issubclass(km.KeyCollisionError, RuntimeError) is True

    def test_collision_names_the_pubkey_and_refuses(self):
        # Same secret on both roles -> same derived pubkey.  Refuse, loudly.
        set_env(**{km.ENV_CLIENT_HEXKEY: TEST_HEX_ONE,
                   km.ENV_SERVER_NSEC: TEST_HEX_ONE})
        with pytest.raises(km.KeyCollisionError) as excinfo:
            km.load_keys()

        message = str(excinfo.value)

        # The colliding x-only pubkey, exactly (independently: d=1 -> G).
        assert km._xonly_pubkey(bytes.fromhex(TEST_HEX_ONE)) == GENERATOR_X
        assert GENERATOR_X in message

        # A refusal, in the module's documented wording.
        assert re.search(r"refus", message), message

        # ... and not a single byte of secret material.
        for secret in client_secrets:
            assert secret not in message, "collision message leaked a secret"

    def test_collision_is_checked_before_any_publication(self):
        """A collision must be refused even with relay auth fully configured."""
        set_env(**{km.ENV_CLIENT_HEXKEY: TEST_HEX_ONE,
                   km.ENV_SERVER_NSEC: TEST_HEX_ONE,
                   km.ENV_RELAY_AUTH: TEST_HEX_B})
        with pytest.raises(km.KeyCollisionError):
            km.load_keys()

    def test_agreeing_roles_do_not_collide(self):
        """Control: differing keys load fine, so the refusal is key-specific."""
        set_env(**{km.ENV_CLIENT_HEXKEY: TEST_HEX_A,
                   km.ENV_SERVER_NSEC: TEST_HEX_SERVER})
        material = km.load_keys()
        assert isinstance(material, km.KeyMaterial)
        assert material.client_pubkey != material.server_pubkey


# ---------------------------------------------------------------------------
# 2. Redaction
# ---------------------------------------------------------------------------
class TestRedaction:
    @staticmethod
    def _loaded():
        set_env(**{km.ENV_CLIENT_HEXKEY: TEST_HEX_A,
                   km.ENV_SERVER_NSEC: TEST_HEX_SERVER,
                   km.ENV_RELAY_AUTH: TEST_HEX_B})
        return km.load_keys()

    def test_repr_and_str_redact_every_secret(self):
        material = self._loaded()

        for rendered, label in ((repr(material), "repr"),
                                (str(material), "str")):
            assert "{redacted}" in rendered, label
            assert "{unset}" not in rendered, label  # relay_auth is set
            for secret in client_secrets:
                assert secret not in rendered, \
                    "{} leaked a secret".format(label)
            # ...and not the secrets' pubkey-derived neighbours either: the
            # rendered form must expose pubkeys only.
            assert material.client_pubkey in rendered
            assert material.server_pubkey in rendered

    def test_interpolation_forms_redact(self):
        material = self._loaded()

        for rendered, label in ((f"{material}", "f-string"),
                                (f"{material!r}", "f-string !r"),
                                ("{}".format(material), "format"),
                                ("{0!r}".format(material), "format !r"),
                                ("%s" % (material,), "percent-s"),
                                ("%r" % (material,), "percent-r")):
            assert "{redacted}" in rendered, label
            for secret in client_secrets:
                assert secret not in rendered, \
                    "{} leaked a secret".format(label)

    def test_secret_fields_are_present_but_masked(self):
        """Redaction masks real values rather than dropping the fields."""
        material = self._loaded()
        assert material.client_secret == TEST_HEX_A
        assert material.server_secret == TEST_HEX_SERVER
        rendered = repr(material)
        assert "client_secret={redacted}" in rendered
        assert "server_secret={redacted}" in rendered
        assert "relay_auth={redacted}" in rendered

    def test_unset_optional_field_renders_unset(self):
        set_env(**{km.ENV_CLIENT_HEXKEY: TEST_HEX_A,
                   km.ENV_SERVER_NSEC: TEST_HEX_SERVER})
        material = km.load_keys()
        assert material.relay_auth is None
        assert "relay_auth={unset}" in repr(material)


# ---------------------------------------------------------------------------
# 3. No key-file access — static
# ---------------------------------------------------------------------------
class TestNoKeyFileAccessStatic:
    def test_scanner_is_not_vacuous(self):
        """Positive control: the scanner must flag a synthetic violation."""
        sample = (
            "import os\n"
            'def k():\n'
            '    """read my key"""\n'
            '    with open(os.environ["E80_KEY_FILE"]) as fh:\n'
            "        return fh.read()\n"
        )
        violations = _key_file_violations(sample)
        assert violations, "scanner failed to flag a synthetic key-file read"

    def test_comments_and_docstrings_do_not_false_positive(self):
        """Prose about keys is not a violation (the brief's narrowness rule)."""
        sample = (
            '"""This module never opens a key file or nsec secret file."""\n'
            "# we deliberately do not read secret_file or key_file here\n"
            "VALUE = 1  # no nsec file access, ever\n"
        )
        assert _key_file_violations(sample) == []

    def test_publish_path_has_no_key_file_reads(self):
        modules = _publish_path_modules()
        # Non-vacuity: the accessor plus at least one real consumer.
        names = sorted(path.name for path in modules)
        assert "keymaterial.py" in names
        assert len(names) > 1, names

        offenders = {}
        for path in modules:
            violations = _key_file_violations(path.read_text(encoding="utf-8"))
            if violations:
                offenders[path.name] = violations

        assert not offenders, \
            "key-file access found on the publish path: {}".format(offenders)

    def test_the_accessor_module_reads_no_file_at_all(self):
        """keymaterial.py is stricter than its consumers: no file reads, period."""
        clean = _strip_comments_and_docstrings(
            (TOOLS_DIR / "keymaterial.py").read_text(encoding="utf-8"))
        assert not _FILE_READS.findall(clean), "keymaterial.py performs file I/O"

    def test_no_key_file_style_env_name_is_even_spelled(self):
        """The ``*_FILE`` naming convention never appears in the code."""
        for path in _publish_path_modules():
            clean = _strip_comments_and_docstrings(
                path.read_text(encoding="utf-8"))
            offenders = sorted({word for word in re.findall(r"\w+", clean)
                                if _GATE_ENV_NAME.fullmatch(word)})
            assert not offenders, "{}: {}".format(path.name, offenders)

    def test_env_name_scanner_is_not_vacuous(self):
        """Positive control: a ``*_FILE`` lookup behind a constant IS caught."""
        sample = (
            "import os\n"
            'KEY_FILE_ENV = "E80_KEY_FILE"\n'
            "def k():\n"
            "    return os.environ[KEY_FILE_ENV]\n"
        )
        names = _resolved_env_names(sample)
        assert "E80_KEY_FILE" in names, names
        assert "E80_KEY_FILE" not in km.ALL_ENV_NAMES
        assert _GATE_ENV_NAME.fullmatch("E80_KEY_FILE")

    def test_only_declared_env_names_are_looked_up(self):
        """Every env name the publish path resolves is one keymaterial declares."""
        for path in _publish_path_modules():
            for name in _resolved_env_names(path.read_text(encoding="utf-8")):
                assert name in km.ALL_ENV_NAMES or name in _NON_KEY_ENV_NAMES, \
                    "{} looks up undeclared env name {}".format(path.name, name)

    def test_declared_env_names_are_not_key_file_paths(self):
        """The accessor's own vocabulary contains no file-path-style name."""
        assert [name for name in km.ALL_ENV_NAMES
                if _GATE_ENV_NAME.search(name)] == []


# ---------------------------------------------------------------------------
# 4. No key-file access — runtime
# ---------------------------------------------------------------------------
@contextlib.contextmanager
def _forbid_file_access():
    """Poison file reads so any attempt raises AssertionError.

    ``builtins.open``, ``pathlib.Path.read_text`` and ``pathlib.Path.read_bytes``
    all raise, so a loader that reads a key file cannot pass silently.
    """
    real_open = builtins.open
    real_read_text = pathlib.Path.read_text
    real_read_bytes = pathlib.Path.read_bytes

    def denied(*args, **kwargs):
        raise AssertionError(
            "file access attempted on the key path: args={!r} kwargs={!r}".format(
                args, kwargs))

    builtins.open = denied
    pathlib.Path.read_text = denied
    pathlib.Path.read_bytes = denied
    try:
        yield
    finally:
        builtins.open = real_open
        pathlib.Path.read_text = real_read_text
        pathlib.Path.read_bytes = real_read_bytes


class TestNoKeyFileAccessRuntime:
    def test_the_guard_actually_blocks(self):
        """Positive control: the poison is live, so the next test means something."""
        before_open = builtins.open
        with _forbid_file_access():
            assert builtins.open is not before_open
            with pytest.raises(AssertionError):
                builtins.open("some_key_file.txt")
            with pytest.raises(AssertionError):
                pathlib.Path("some_nsec_file.txt").read_text()
            with pytest.raises(AssertionError):
                pathlib.Path("some_secret_file.txt").read_bytes()
        assert builtins.open is before_open  # restored

    def test_load_keys_succeeds_with_all_file_access_blocked(self):
        set_env(**{km.ENV_CLIENT_HEXKEY: TEST_HEX_A,
                   km.ENV_SERVER_NSEC: TEST_HEX_SERVER,
                   km.ENV_RELAY_AUTH: TEST_HEX_B})

        with _forbid_file_access():
            material = km.load_keys()

        assert isinstance(material, km.KeyMaterial)
        assert material.client_secret == TEST_HEX_A
        assert material.server_secret == TEST_HEX_SERVER
        assert material.relay_auth == TEST_HEX_B

    def test_collision_refusal_also_needs_no_file(self):
        set_env(**{km.ENV_CLIENT_HEXKEY: TEST_HEX_ONE,
                   km.ENV_SERVER_NSEC: TEST_HEX_ONE})
        with _forbid_file_access():
            with pytest.raises(km.KeyCollisionError):
                km.load_keys()

    def test_no_key_file_was_created_by_this_suite(self):
        """The suite must not have written a key file into tools/."""
        suspicious = [
            path for path in TOOLS_DIR.rglob("*")
            if path.is_file()
            and re.search(r"key|nsec|secret", path.name, re.I)
            and path.suffix in {".json", ".env", ".txt", ".pem", ".key", ".hex"}
        ]
        assert not suspicious, suspicious
