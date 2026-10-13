#!/usr/bin/env python3
"""LR2021 LoRa BW table — host-side parser for the FW-1 shared single source.

Parses firmware/rp2040/src/lr2021_bw_codes.h (the LR2021_BW_TABLE X-macro
rows between the BEGIN/END markers) at runtime, so firmware and host scripts
share literally one table. Ground truth provenance is documented in that
header and in docs/bw-code-table.md.

Usage:
    from lr2021_bw_codes import khz_to_code, code_to_hz, load_bw_table
    python3 tools/lr2021_bw_codes.py          # pretty-print the table
"""
import os
import re
import sys
from dataclasses import dataclass

HEADER_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    os.pardir, "firmware", "rp2040", "src", "lr2021_bw_codes.h",
)

_ROW_RE = re.compile(
    r"^\s*X\(\s*(\d+)\s*,\s*(0[xX][0-9A-Fa-f]+)\s*,\s*(\d+)UL?\s*\)"
)


@dataclass(frozen=True)
class BwRow:
    khz_label: int   # console label, e.g. 125 for "MOD LORA 7 125"
    code: int        # SetModulationParams BW nibble, 0x00..0x0F
    hz: int          # driver get_bw_in_hz() constant


def _table_region(text: str) -> str:
    """Text between LR2021_BW_TABLE_BEGIN and LR2021_BW_TABLE_END markers."""
    begin = text.index("LR2021_BW_TABLE_BEGIN")
    end = text.index("LR2021_BW_TABLE_END")
    return text[begin:end]


def load_bw_table(path: str = HEADER_PATH) -> list:
    """Parse the X-macro rows; raise ValueError on malformed/empty table."""
    with open(path, "r", encoding="utf-8") as f:
        region = _table_region(f.read())
    rows = []
    for line in region.splitlines():
        m = _ROW_RE.match(line)
        if m:
            rows.append(BwRow(int(m.group(1)), int(m.group(2), 16),
                              int(m.group(3))))
    if not rows:
        raise ValueError(f"no BW rows parsed from {path!r}")
    return rows


def code_to_hz(code: int):
    """Wire code -> driver Hz constant; None for unknown codes."""
    for r in load_bw_table():
        if r.code == code:
            return r.hz
    return None


def hz_to_code(hz: int):
    """Exact driver Hz constant -> wire code; None if absent."""
    for r in load_bw_table():
        if r.hz == hz:
            return r.code
    return None


def khz_to_code(khz: int):
    """Console kHz label -> wire code; None if not a table label."""
    for r in load_bw_table():
        if r.khz_label == khz:
            return r.code
    return None


def _main(argv=None) -> int:
    rows = load_bw_table()
    print(f"# LR2021 LoRa BW table ({len(rows)} rows) — {os.path.relpath(HEADER_PATH)}")
    print(f"{'kHz':>6}  {'code':>6}  {'hz':>10}  enum")
    for r in sorted(rows, key=lambda r: r.code):
        print(f"{r.khz_label:>6}  {r.code:#04x}    {r.hz:>10}  "
              f"LR2021_LORA_BW_{r.khz_label}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
