#!/usr/bin/env python3
"""bom_part_allowlist.py — fail-closed ordering-trap gate for the balloon v9 BOM.

WHY THIS EXISTS
---------------
Two G-NiceRF module families differ by one character in the chip generation, and
the wrong one is what a JLCPCB/LCSC search surfaces first:

    CORRECT   : LoRa2021F33-2G4          SEMTECH LR2021   (ours; in ADR-029 D2/D2b)
    FORBIDDEN : LoRa1121F33-2G4(/-868MHz) SEMTECH LR1121 (a DIFFERENT module)

The LCSC/JLC catalogue listing name for the wrong part is
`LoRa1121F33-2G4-868MHz`. ADR-029 records this as *"a live trap for whoever places
the order"*, and the operator's 2026-10-05 decision list (JLCPCB BOM/CPL card
`t_3b823ea8`, item 4) states verbatim that this listing "must not be ordered".

WHAT IT CHECKS
--------------
Any BOM or board file (KiCad `.kicad_pcb`, a netlist, or a plain-text/CSV BOM),
scanned as text for these forbidden tokens, case-insensitively, as substrings:

    LoRa1121
    LR1121
    LoRa1121F33-2G4-868MHz

The third is a strict superset of the first, and is kept as an explicit token so
that the report names the exact catalogue listing an operator would have pasted.

CONTRACT (deterministic; no network, no model, no inference)

    exit 0   input(s) read, no forbidden token found  (clean)
    exit 1   input(s) read, >=1 forbidden token found (FAIL -- do not order)
    exit 2   an input could not be read               (fail-closed)

Any number of paths may be given; ALL are checked and any single hit fails the
run (exit 1). Unreadable inputs (missing path, directory, permission error,
undecodable bytes) are exit 2, evaluated BEFORE the token scan so a scan can
never "pass" on an input that was in fact not read.

CAVEAT, STATED HONESTLY
-----------------------
This is a *name* gate, not a part-identity gate. It cannot tell you whether the
MPN a supplier ships really is an LR2021. It closes exactly the one trap that
ADR-029 names, and nothing more.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The forbidden tokens. Order matters only for reporting priority.
FORBIDDEN_TOKENS = (
    "LoRa1121F33-2G4-868MHz",  # the LCSC/JLC catalogue listing name (most specific)
    "LoRa1121",                # the G-NiceRF module name on the wrong chip
    "LR1121",                  # the bare Semtech chip name on the wrong module
)

EXIT_CLEAN = 0
EXIT_FAIL = 1
EXIT_UNREADABLE = 2

MAX_BYTES = 64 * 1024 * 1024  # refuse to slurp anything absurd; guards fat-fingers


def read_input(path: Path) -> tuple[str | None, str | None]:
    """Return (text, error). Exactly one is None.

    A directory, a missing path, an unreadable file or undecodable bytes all
    yield an error string -- never a silent empty scan (fail-closed).
    """
    if not path.exists():
        return None, "no such file or directory"
    if path.is_dir():
        return None, "is a directory, not a file"
    try:
        size = path.stat().st_size
        if size > MAX_BYTES:
            return None, f"refusing to scan {size} bytes (> {MAX_BYTES})"
        data = path.read_bytes()
    except OSError as exc:
        return None, f"read error: {exc.strerror or exc}"
    # latin-1 never fails to decode; we only need ASCII token matching.
    return data.decode("latin-1"), None


def scan(path: Path, text: str) -> list[tuple[int, str, str]]:
    """Return [(lineno, token, line_text)] for every forbidden token occurrence."""
    hits: list[tuple[int, str, str]] = []
    lowered = [t.lower() for t in FORBIDDEN_TOKENS]
    for lineno, line in enumerate(text.splitlines(), start=1):
        low = line.lower()
        for token, token_low in zip(FORBIDDEN_TOKENS, lowered):
            if token_low in low:
                hits.append((lineno, token, line.strip()))
    return hits


def main(argv: list[str]) -> int:
    if not argv:
        print("bom_part_allowlist: FAIL-CLOSED — no input path given.", file=sys.stderr)
        print("usage: bom_part_allowlist.py <bom-or-board-file> [more files...]",
              file=sys.stderr)
        return EXIT_UNREADABLE

    texts: list[tuple[Path, str]] = []
    unreadable: list[tuple[Path, str]] = []

    for raw in argv:
        path = Path(raw)
        text, error = read_input(path)
        if error is not None:
            unreadable.append((path, error))
        else:
            texts.append((path, text))

    # Fail-closed: an input we could not read is exit 2, regardless of the rest.
    if unreadable:
        for path, error in unreadable:
            print(f"bom_part_allowlist: CANNOT READ {path}: {error}", file=sys.stderr)
        print("bom_part_allowlist: exit 2 — an input was not read; refusing to report "
              "a clean result.", file=sys.stderr)
        return EXIT_UNREADABLE

    any_hit = False
    for path, text in texts:
        hits = scan(path, text)
        if not hits:
            print(f"OK   {path}: no forbidden token ({len(FORBIDDEN_TOKENS)} tokens scanned)")
            continue
        any_hit = True
        for lineno, token, line in hits:
            print(f"FAIL {path}:{lineno}: forbidden token {token!r} in: {line}")

    if any_hit:
        print()
        print("bom_part_allowlist: exit 1 — DO NOT ORDER. The forbidden module is")
        print("  G-NiceRF LoRa1121F33-2G4 (SEMTECH LR1121), a DIFFERENT chip.")
        print("  The correct part is G-NiceRF LoRa2021F33-2G4 (SEMTECH LR2021).")
        print("  Authority: docs/adr/029-dual-band-flight-board.md (D2, O0).")
        return EXIT_FAIL

    print("bom_part_allowlist: exit 0 — clean.")
    return EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
