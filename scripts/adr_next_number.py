#!/usr/bin/env python3
"""adr_next_number.py — the single source of truth for the next free ADR number.

RULE (also stated at the top of docs/adr/INDEX.md)
--------------------------------------------------
New ADRs get their number from THIS script. Do not pick a number by hand and do
not renumber or rename an existing ADR file: references to them exist outside
`docs/adr/` (code, coordination docs, branch names) and renumbering breaks them.
If a number is already taken by more than one file, that is a *collision* to be
recorded in `docs/adr/INDEX.md` — never silently fixed by a rename.

Allocation floor is **044**: numbers 001-043 are historical territory (and 044 is
the first number this rule was written for). The script therefore never proposes
a number below 044, even if a low number happens to be free.

WHAT IT PRINTS
--------------
On success it prints a single integer (the next free number at or above 044) to
stdout and exits 0, so it composes:

    N=$(scripts/adr_next_number.py)
    git mv / new file docs/adr/${N}-my-new-record.md

EXIT CODES
----------
    0   a free number was found and printed
    1   the requested number is already taken (`--number N` / `--path P` given
        and its target path already exists)
    2   usage error, or docs/adr/ cannot be read
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ALLOCATION_FLOOR = 44
NUMBERED = re.compile(r"^(\d{3})-")


def find_adr_dir() -> Path:
    """Locate docs/adr/ from this script's location (repo-root relative)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "docs" / "adr"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("docs/adr/ not found above " + str(here))


def taken_numbers(adr_dir: Path) -> dict[int, list[str]]:
    """Map number -> [filenames] for every file shaped like NNN-*.md."""
    taken: dict[int, list[str]] = {}
    for entry in sorted(adr_dir.iterdir()):
        if not entry.is_file() or entry.suffix != ".md":
            continue
        match = NUMBERED.match(entry.name)
        if match:
            taken.setdefault(int(match.group(1)), []).append(entry.name)
    return taken


def next_free(taken: dict[int, list[str]], floor: int = ALLOCATION_FLOOR) -> int:
    n = floor
    while n in taken:
        n += 1
    return n


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Print the next free ADR number (>= 044).",
    )
    parser.add_argument(
        "--number", type=int, default=None,
        help="verify a specific number instead of searching; exits 1 if taken",
    )
    parser.add_argument(
        "--path", default=None,
        help="verify a specific target path; exits 1 if that file already exists",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="also print the taken numbers and their files to stderr",
    )
    args = parser.parse_args(argv)

    try:
        adr_dir = find_adr_dir()
    except FileNotFoundError as exc:
        print(f"adr_next_number: cannot locate docs/adr/: {exc}", file=sys.stderr)
        return 2

    try:
        taken = taken_numbers(adr_dir)
    except OSError as exc:
        print(f"adr_next_number: cannot read {adr_dir}: {exc}", file=sys.stderr)
        return 2

    if args.list:
        for number in sorted(taken):
            print(f"  {number:03d}: {', '.join(taken[number])}", file=sys.stderr)

    # Explicit target path check — the literal "exit non-zero if the target path
    # already exists" clause, applied before any search.
    if args.path:
        target = Path(args.path)
        if target.exists():
            print(f"adr_next_number: TAKEN — {target} already exists", file=sys.stderr)
            return 1
        match = NUMBERED.match(target.name)
        if not match:
            print(f"adr_next_number: {target.name!r} is not shaped NNN-description.md",
                  file=sys.stderr)
            return 2
        number = int(match.group(1))
        if number in taken:
            print(f"adr_next_number: TAKEN — {number:03d} used by "
                  f"{', '.join(taken[number])}", file=sys.stderr)
            return 1
        print(f"{number}")
        return 0

    if args.number is not None:
        if args.number in taken:
            print(f"adr_next_number: TAKEN — {args.number:03d} used by "
                  f"{', '.join(taken[args.number])}", file=sys.stderr)
            return 1
        print(f"{args.number}")
        return 0

    print(next_free(taken))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
