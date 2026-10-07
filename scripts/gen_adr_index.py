#!/usr/bin/env python3
"""gen_adr_index.py — mechanically generate docs/adr/INDEX.md.

The index is generated, never hand-edited: run this script after adding an ADR.
It walks docs/adr/, groups files by their leading NNN number, extracts each
file's own title (first markdown heading) and Status (its own Status header),
and writes the canonical number -> filename map plus a collision report.

Collision policy encoded here (see docs/adr/INDEX.md for the prose rule):
  * NO file is ever renamed or renumbered.
  * Where a collision is resolvable from evidence, VERDICTS below states which
    file is the live record and which is superseded, and names the source of
    that evidence.
  * Where it is not resolvable, the index prints
    `UNRESOLVED - needs an operator decision` rather than guessing.

Usage:  python3 scripts/gen_adr_index.py            # writes docs/adr/INDEX.md
        python3 scripts/gen_adr_index.py --stdout   # print instead
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ALLOCATION_FLOOR = 44
NUMBERED = re.compile(r"^(\d{3})-(.*)\.md$")
ANY_NUMBER = re.compile(r"^(\d{3})-")
NON_CONFORMING = re.compile(r"^(ADR-\d+|adr-)", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Hand-derived collision verdicts. Each value is the exact one-line verdict
# printed in the index. Only put text here that is *derived from evidence*:
# a file's own Status header, or a supersede pointer inside a committed record
# (the pointer's source is named inline). Everything else is UNRESOLVED.
# ---------------------------------------------------------------------------
COLLISION_VERDICTS: dict[int, str] = {
    2: (
        "**LIVE:** `002-lr2021-as-rf-chip.md` (Status `Akzeptiert`) — the LR2021 "
        "chip selection. **SUPERSEDED:** none. The other file is an unrelated "
        "Accepted record (`002-tollgate-over-fips-mesh-udp.md`, transport layer), "
        "so no supersede chain joins them → "
        "`UNRESOLVED - needs an operator decision`."
    ),
    17: (
        "**LIVE:** `017-phase-sync-via-reference-clocks.md` and "
        "`017-version-tagging-policy.md` (both Status `Accepted`, unrelated "
        "topics). **SUPERSEDED:** `017-lr2021-only-ban-sx1280.md` — its own "
        "Status header reads `SUPERSEDED by ADR-020` (2026-07-23). Three "
        "unrelated records share 017 → "
        "`UNRESOLVED - needs an operator decision`."
    ),
    18: (
        "**LIVE:** `018-multi-mode-range-characterization.md` (Status "
        "`Accepted (2026-07-22)`). **SUPERSEDED:** `018-tx-autonomy-requirement.md` "
        "— its own Status header reads `Superseded (partial) — 2026-07-27` and "
        "names no successor number, so the *number* is still not allocated → "
        "`UNRESOLVED - needs an operator decision`."
    ),
    19: (
        "**LIVE:** both — `019-gps-synchronized-mode-switching.md` (Status "
        "`Accepted (2026-07-22)`) and `019-tx-rx-sync-invariant.md` (Status "
        "`Accepted`). **SUPERSEDED:** none; they are unrelated topics with no "
        "supersede pointer between them → "
        "`UNRESOLVED - needs an operator decision`."
    ),
    20: (
        "**LIVE:** both — `020-deprecate-radiolib-adopt-raw-lr2021-spi.md` "
        "(Status `Accepted (2026-07-23)`, itself states it `Supersedes ADR-017`) "
        "and `020-reproducible-build-flash-test.md` (Status `Accepted`). "
        "**SUPERSEDED:** none (the 017 → 020 pointer is cross-number, it does not "
        "allocate 020) → `UNRESOLVED - needs an operator decision`."
    ),
    25: (
        "**LIVE:** both — `025-shared-hardware-flock-mutex.md` (Status "
        "`ACCEPTED`) and `025-e-hash-relay-transport-layer.md` (Status "
        "`Proposed`). **SUPERSEDED:** none; unrelated topics, no supersede "
        "pointer → `UNRESOLVED - needs an operator decision`."
    ),
    28: (
        "**LIVE:** `028-schematic-first-three-variants.md` — cited as the "
        "**accepted ADR-028** by `docs/coordination/PCB-MASTER-EXECUTION-PLAN.md` "
        "(lines 10 and 683) and committed later (`862c0c5`, 2026-08-05). "
        "**SUPERSEDED:** `028-three-variant-pcb-design.md` (`3356695`, same day, "
        "the earlier proposal); its own body says of the earlier script-generated "
        "workflow *\"The schematic-first approach replaces this entirely.\"* "
        "Both documents cover the same subject (three MCU variants), so this "
        "collision IS resolvable. *(Files are NOT renamed — see the rule above.)*"
    ),
    29: (
        "**LIVE:** `029-dual-band-flight-board.md` (Status `Proposed`) — the v9 "
        "design of record. **ANNEX (not a competing record):** "
        "`029-f33-sx1280-pin-plan.md`, which declares itself the pin plan for this "
        "ADR's D2b(b) and is named as such in ADR-029 §Rollout item 7. "
        "**UNRESOLVED:** `029-firmware-output-harmonization.md` (Status "
        "`APPROVED`) is an unrelated firmware record claiming the same number; "
        "ADR-029's own O7 flags it as unresolved → "
        "`UNRESOLVED - needs an operator decision`."
    ),
}


# ---------------------------------------------------------------------------
# extraction
# ---------------------------------------------------------------------------

def title_of(path: Path) -> str:
    """First markdown heading, with the ADR/NNN prefix stripped."""
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            title = re.sub(r"^ADR[-\s]*0*\d+[a-z]?\s*[:—–-]\s*", "", title)
            title = re.sub(r"^ADR[-\s]*\d+\s*", "", title)
            return title.strip() or path.stem
    return path.stem


def status_of(path: Path) -> str:
    """The file's own Status value, normalised to one short line."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        # "**Status:** ACCEPTED"
        match = re.match(r"^\*\*Status:\*\*\s*(.+)$", stripped, re.IGNORECASE)
        if match:
            return _short(match.group(1))
        # "- **Status:** Proposed"
        match = re.match(r"^[-*]\s*\*\*Status:\*\*\s*(.+)$", stripped, re.IGNORECASE)
        if match:
            return _short(match.group(1))
        # "- Status: **Proposed** — ..."
        match = re.match(r"^[-*]\s*Status:\s*(.+)$", stripped, re.IGNORECASE)
        if match:
            return _short(match.group(1), split_dash=True)
        # "Status: proposed implementation baseline, ..." (bare)
        match = re.match(r"^Status:\s*(.+)$", stripped)
        if match:
            return _short(match.group(1), split_dash=True)
        # "## Status" heading -> value is the next non-empty line
        if re.match(r"^#{1,3}\s*Status\s*$", stripped, re.IGNORECASE):
            for nxt in lines[idx + 1:]:
                value = nxt.strip()
                if value:
                    return _short(value, split_dash=True)
    return "UNKNOWN"


def _short(value: str, split_dash: bool = False) -> str:
    """Normalise a raw Status value to one short phrase."""
    value = re.sub(r"\*\*", "", value).strip().rstrip(".")
    if split_dash:
        value = value.split(" — ")[0].split(" - ")[0].strip()
    # "Proposed (2026-10-05). The direction is ..." -> "Proposed"
    value = value.split(" (")[0].strip().rstrip(".")
    return value or "UNKNOWN"


def collect(adr_dir: Path):
    numbered: dict[int, list[Path]] = {}
    nonconforming: list[Path] = []
    unnumbered: list[Path] = []
    for entry in sorted(adr_dir.iterdir()):
        if not entry.is_file() or entry.suffix != ".md":
            continue
        if entry.name == "INDEX.md":
            continue
        match = NUMBERED.match(entry.name)
        if match:
            numbered.setdefault(int(match.group(1)), []).append(entry)
        elif ANY_NUMBER.match(entry.name) or NON_CONFORMING.match(entry.name):
            nonconforming.append(entry)
        else:
            unnumbered.append(entry)
    return numbered, nonconforming, unnumbered


def build(adr_dir: Path) -> str:
    numbered, nonconforming, unnumbered = collect(adr_dir)
    max_number = max(numbered) if numbered else 0
    out: list[str] = []

    out.append("# ADR index — canonical number → filename map")
    out.append("")
    out.append("**This file is GENERATED.** Do not hand-edit it: run")
    out.append("`python3 scripts/gen_adr_index.py` after adding or removing an ADR.")
    out.append("")
    out.append("## The numbering rule (binding)")
    out.append("")
    out.append("- A new ADR takes its number from `scripts/adr_next_number.py`, which")
    out.append(f"  prints the next free number at or above **{ALLOCATION_FLOOR:03d}** and exits")
    out.append("  non-zero if its target path already exists. Do not pick a number by hand.")
    out.append(f"- **{ALLOCATION_FLOOR:03d} and above are reserved for sequential allocation.**")
    out.append("  Numbers 001–043 are historical.")
    out.append("- **Never rename or renumber an existing ADR file.** References to them exist")
    out.append("  outside `docs/adr/` (code, coordination docs, branch names, external links)")
    out.append("  and a rename silently breaks them. A number used by two files is a")
    out.append("  *collision*: record it here, do not fix it by renaming.")
    out.append("- Where a collision cannot be resolved from evidence (a file's own Status")
    out.append("  header, or a supersede pointer inside a committed record), this index says")
    out.append("  `UNRESOLVED - needs an operator decision`. It never guesses.")
    out.append("")
    out.append(f"Generated from `docs/adr/`: **{len(numbered)}** distinct")
    out.append(f"numbers, **{sum(len(v) for v in numbered.values())}** numbered files, "
               f"**{len(nonconforming) + len(unnumbered)}** non-conforming filenames.")
    out.append("")

    # ---- collisions ------------------------------------------------------
    collisions = {n: files for n, files in sorted(numbered.items()) if len(files) > 1}
    out.append("## Collisions")
    out.append("")
    if not collisions:
        out.append("None.")
    else:
        for number, files in collisions.items():
            names = ", ".join(f"`{p.name}`" for p in files)
            out.append(f"- **{number:03d} ({len(files)}x)** — {names}")
            verdict = COLLISION_VERDICTS.get(number)
            if verdict:
                out.append(f"  - {verdict}")
            else:
                out.append("  - `UNRESOLVED - needs an operator decision`")
    out.append("")

    # ---- full map --------------------------------------------------------
    out.append("## Number → files")
    out.append("")
    out.append("| # | file | title | own Status |")
    out.append("|---|---|---|---|")
    for number in sorted(numbered):
        for path in numbered[number]:
            flag = " **(COLLISION)**" if len(numbered[number]) > 1 else ""
            out.append(
                f"| {number:03d}{flag} | `{path.name}` | {title_of(path)} "
                f"| {status_of(path)} |"
            )
    out.append(f"| ≥{ALLOCATION_FLOOR:03d} | *(reserved)* | "
               f"next free: `scripts/adr_next_number.py` → {next_free(numbered):03d} "
               f"| — |")
    out.append("")

    # ---- non-conforming --------------------------------------------------
    out.append("## Non-conforming filenames (not `NNN-description.md`)")
    out.append("")
    out.append("These are listed so they are not mistaken for free numbers. They are NOT")
    out.append("renamed by this script (see the rule). Note that `ADR-001-tollgate-over-lr2021.md`")
    out.append("effectively competes for number **001** with `001-esp32-c3-as-mcu.md`; it is")
    out.append("recorded here rather than silently renumbered, and that pair also needs an")
    out.append("operator decision.")
    out.append("")
    for path in nonconforming + unnumbered:
        out.append(f"- `{path.name}` — {title_of(path)} (own Status: {status_of(path)})")
    out.append("")
    return "\n".join(out) + "\n"


def next_free(numbered: dict[int, list[Path]]) -> int:
    n = ALLOCATION_FLOOR
    while n in numbered:
        n += 1
    return n


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args(argv)

    adr_dir = Path(__file__).resolve().parents[1] / "docs" / "adr"
    if not adr_dir.is_dir():
        print(f"gen_adr_index: no docs/adr/ at {adr_dir}", file=sys.stderr)
        return 2
    text = build(adr_dir)
    if args.stdout:
        sys.stdout.write(text)
    else:
        (adr_dir / "INDEX.md").write_text(text, encoding="utf-8")
        print(f"wrote {adr_dir / 'INDEX.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
