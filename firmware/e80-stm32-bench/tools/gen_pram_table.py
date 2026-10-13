#!/usr/bin/env python3
"""Generate src/pram_patch_table.c from the ExpressLRS LR2021 PRAM header.

Provenance (reproduce with the ELRS clone at ~/worktrees/rfa1-elrs/ExpressLRS):
    src/lib/LR2021Driver/LR2021PRAM.h  ->  constexpr uint32_t pram_lr2021[560]

Usage:
    python3 tools/gen_pram_table.py <LR2021PRAM.h> [out.c]

The emitted table is checked in (the firmware build must not depend on an ELRS
checkout). The generator also prints the CRC32 of the parsed table so the
firmware-side `pramcrc=` value can be verified independently.
"""

from __future__ import annotations

import re
import sys
import zlib
from pathlib import Path

EXPECTED_WORDS = 560
WORDS_PER_LINE = 6


def parse_table(header: Path) -> list[int]:
    text = header.read_text()
    m = re.search(r"pram_lr2021\s*\[\s*(\d+)\s*\]\s*=\s*\{(.*?)\};", text, re.S)
    if not m:
        raise SystemExit(f"no pram_lr2021[] initializer found in {header}")
    declared = int(m.group(1))
    body = m.group(2)
    words = [int(tok, 0) for tok in re.findall(r"0x[0-9a-fA-F]+|\b\d+\b", body)]
    if declared != len(words):
        raise SystemExit(f"declared {declared} words but parsed {len(words)}")
    if declared != EXPECTED_WORDS:
        raise SystemExit(f"expected {EXPECTED_WORDS} words, header declares {declared}")
    for w in words:
        if not 0 <= w <= 0xFFFFFFFF:
            raise SystemExit(f"word out of range: {w}")
    return words


def emit(words: list[int], source_note: str) -> str:
    lines = [
        "/**",
        " * @file    pram_patch_table.c",
        " * @brief   LR2021 PRAM (patch RAM) image uploaded at radio bring-up.",
        " *",
        " * GENERATED - do not hand-edit. Regenerate with",
        " *   python3 tools/gen_pram_table.py <path>/LR2021PRAM.h src/pram_patch_table.c",
        " *",
        f" * Source: {source_note}",
        " * Content: constexpr uint32_t pram_lr2021[560] (560 x uint32 = 2240 B).",
        " * ExpressLRS uploads this unconditionally in LR2021Driver::Begin()",
        " * (LR2021.cpp:112 -> LoadPatchRAM, LR2021Patch.cpp:42-71).",
        " *",
        f" * Table CRC32 (IEEE, reflected, init 0xFFFFFFFF, xorout 0xFFFFFFFF): 0x{words_crc(words):08X}",
        " */",
        "",
        '#include "pram_patch.h"',
        "",
        f"const uint32_t pram_patch_table[PRAM_PATCH_WORDS] = {{",
    ]
    for i in range(0, len(words), WORDS_PER_LINE):
        chunk = words[i : i + WORDS_PER_LINE]
        rendered = ", ".join(f"0x{w:08x}u" for w in chunk)
        lines.append(f"    {rendered},")
    lines += ["};", ""]
    return "\n".join(lines)


def words_crc(words: list[int]) -> int:
    return zlib.crc32(b"".join(w.to_bytes(4, "big") for w in words)) & 0xFFFFFFFF


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    header = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("src/pram_patch_table.c")
    words = parse_table(header)
    note = f"{header} (ExpressLRS master; see docs/RFA1-ELRS-LR2021-DIFF-2026-10-12.md)"
    out.write_text(emit(words, note))
    print(f"wrote {out}: {len(words)} words, crc32=0x{words_crc(words):08X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
