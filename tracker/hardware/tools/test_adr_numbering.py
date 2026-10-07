#!/usr/bin/env python3
"""ADR numbering gate, task-specified location.

The assertions live in ``tests/test_adr_numbering.py`` (the directory pytest already
collects: ``testpaths = tests`` in pytest.ini / pyproject.toml).  This module loads
them by path and re-exports the ``test_*`` functions so the gate also runs when the
file is invoked directly, as the sibling ``test_bom_temp_gate.py`` in this directory
is:

    python3 -m pytest tracker/hardware/tools/test_adr_numbering.py -v
"""

import importlib.util
import pathlib

_ROOT = pathlib.Path(__file__).resolve().parents[3]
_CANONICAL = _ROOT / "tests" / "test_adr_numbering.py"

_spec = importlib.util.spec_from_file_location("_adr_numbering_canonical", _CANONICAL)
assert _spec is not None and _spec.loader is not None, _CANONICAL
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Re-exported for pytest collection (same assertions, single implementation).
adr_dir = _mod.adr_dir
ALLOWLIST = _mod.ALLOWLIST
test_adr_filenames_match_convention = _mod.test_adr_filenames_match_convention
test_allowlist_entries_still_exist = _mod.test_allowlist_entries_still_exist
test_numbers_are_not_duplicated = _mod.test_numbers_are_not_duplicated


if __name__ == "__main__":
    import sys
    for name in sorted(n for n in dir(_mod) if n.startswith("test_")):
        getattr(_mod, name)()
        print("ok  %s" % name)
    sys.exit(0)
