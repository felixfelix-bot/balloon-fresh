"""Static guards pinning the gift-wrap construction surface (ADR-033).

These guards fail when a new kind-1059 construction/unwrap path or a new
``KIND_GIFT_WRAP`` definition appears in the CVM tooling, so the public
"single canonical wrap primitive" claim cannot silently expire.

Pure AST — no ``nostr_sdk`` import required, so it runs in a bare CI image.
Re-verified against trunk ``e7ec2d0`` on 2026-10-06.
"""
import ast
from pathlib import Path

TOOLS = Path(__file__).parent

# Per-file counts of calls to the upstream wrap primitive.
EXPECTED_CALLS = {
    "cvm_board_server.py": {"gift_wrap": 1, "from_gift_wrap": 1},
    "cvm_campaign.py": {"gift_wrap": 2, "from_gift_wrap": 1},
    "cvm_relay_test.py": {"gift_wrap": 1},
    "test_cvm_board_server.py": {"gift_wrap": 1, "from_gift_wrap": 1},
}

# Modules allowed to author a local KIND_GIFT_WRAP constant. Enumerated rather
# than collapsed so that new duplication trips the test (see ADR-033 §Context).
EXPECTED_KIND_DEFS = {"cvm_board_server.py", "cvm_campaign.py", "cvm_sync.py"}

WRAP_ATTRS = ("gift_wrap", "from_gift_wrap")

# The seal-based upstream entry point is a latent second construction path.
FORBIDDEN_NAMES = ("gift_wrap_from_seal",)


def _trees():
    for py in sorted(TOOLS.glob("*.py")):
        try:
            yield py, ast.parse(py.read_text())
        except SyntaxError:  # pragma: no cover - not this test's job to police
            continue


def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _giftwrap_calls(path):
    counts = {}
    for node in ast.walk(ast.parse(path.read_text())):
        if not isinstance(node, ast.Call):
            continue
        name = _dotted(node.func)
        if not name:
            continue
        attr = name.rsplit(".", 1)[-1]
        if attr in WRAP_ATTRS:
            assert name.startswith("nostr_sdk."), (
                f"{path.name}:{node.lineno}: {name} is not a nostr_sdk.* call"
            )
            counts[attr] = counts.get(attr, 0) + 1
    return counts


def _kind_def_modules():
    mods = set()
    for py, tree in _trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                if node.value.value == 1059 and any(
                    isinstance(t, ast.Name) and t.id == "KIND_GIFT_WRAP"
                    for t in node.targets
                ):
                    mods.add(py.name)
    return mods


def test_wrap_call_sites_are_pinned():
    for fname, expected in EXPECTED_CALLS.items():
        assert _giftwrap_calls(TOOLS / fname) == expected, fname


def test_kind_constant_definitions_are_pinned():
    assert _kind_def_modules() == EXPECTED_KIND_DEFS


def test_no_local_wrap_wrapper():
    for py, tree in _trees():
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert node.name not in WRAP_ATTRS, (
                    f"{py.name}:{node.lineno}: local {node.name}() wrapper"
                )


def test_seal_based_second_path_not_used():
    for py, tree in _trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
                raise AssertionError(f"{py.name}:{node.lineno}: uses {node.id}")
            if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_NAMES:
                raise AssertionError(f"{py.name}:{node.lineno}: uses .{node.attr}")
