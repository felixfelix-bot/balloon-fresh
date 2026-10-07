#!/usr/bin/env python3
"""Gate: `docs/adr/` must have no duplicate ADR numbers and conventional filenames.

Two invariants, both enforced here (see the renumber-collision card):

1. **No duplicate ADR numbers.** Every `NNN-slug.md` file in `docs/adr/` claims the
   number `NNN`. Two files at one number is a defect: a decision record cannot be
   cited unambiguously. Displaced historical records live at 100+ so they cannot
   race the sequential allocation (which continues from 044 upward).
2. **Conventional filenames.** Every ADR filename matches
   ``^[0-9]{3}-[a-z0-9-]+\\.md$``. Anything else must be listed in ``ALLOWLIST``
   below *with a reason*, so a new stray file fails the gate instead of silently
   escaping it.

Run:  python3 -m pytest tests/test_adr_numbering.py -v
  or: python3 tracker/hardware/tools/test_adr_numbering.py -v
"""

import pathlib
import re
from collections import defaultdict

# Files in docs/adr/ that are intentionally outside the NNN-slug convention.
# Anything here is excluded from BOTH checks. Each needs a reason.
ALLOWLIST = {
    "ADR-001-tollgate-over-lr2021.md": (
        "Unnumbered legacy artefact: written before the NNN-slug convention and named "
        "by hand after the ADR it responds to. It is deliberately left in place (and is "
        "the counterpart of the 100-range displacement) because it does not claim a "
        "sequential slot the way an NNN- file does; renaming it is out of scope for the "
        "renumber-collision card."
    ),
    "adr-e-hash-relay-DECISIONS.md": (
        "Unnumbered companion decision list for the e-hash relay ADR (D1-D10), not an ADR "
        "in its own right: it carries no number to collide and is referenced by relative "
        "link from mesh-stack/protocol/ehash-interface-boundary.md."
    ),
}

FILENAME_RE = re.compile(r"^[0-9]{3}-[a-z0-9-]+\.md$")
NUMBER_RE = re.compile(r"^([0-9]{3})-")


def adr_dir():
    """Locate docs/adr by walking up from this file (works in a git worktree)."""
    here = pathlib.Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        cand = parent / "docs" / "adr"
        if cand.is_dir() and (parent / ".git").exists():
            return cand
    raise RuntimeError("could not locate docs/adr above %s" % here)


def adr_markdown_files():
    return sorted(p for p in adr_dir().iterdir() if p.is_file() and p.suffix == ".md")


def test_adr_filenames_match_convention():
    """Every docs/adr/*.md is NNN-slug.md or explicitly allowlisted."""
    offending = [
        p.name for p in adr_markdown_files()
        if not FILENAME_RE.match(p.name) and p.name not in ALLOWLIST
    ]
    assert not offending, (
        "docs/adr/ filenames that do not match %s and are not in ALLOWLIST: %s"
        % (FILENAME_RE.pattern, offending)
    )


def test_allowlist_entries_still_exist():
    """A stale allowlist entry would hide a future violation."""
    present = {p.name for p in adr_markdown_files()}
    missing = sorted(set(ALLOWLIST) - present)
    assert not missing, "ALLOWLIST names that no longer exist in docs/adr/: %s" % missing


def test_numbers_are_not_duplicated():
    """No two docs/adr/ files may claim the same NNN."""
    by_number = defaultdict(list)
    for p in adr_markdown_files():
        m = NUMBER_RE.match(p.name)
        if m:
            by_number[m.group(1)].append(p.name)
    dups = {num: names for num, names in by_number.items() if len(names) > 1}
    assert not dups, "duplicate ADR numbers in docs/adr/: %s" % {
        num: sorted(names) for num, names in sorted(dups.items())
    }
