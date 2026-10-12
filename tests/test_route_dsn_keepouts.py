#!/usr/bin/env python3
"""Regression: keepouts must be DERIVED from board J_W* geometry, not hard-coded.

WHY: run 7 showed the router laying 12 tracks along the wing-socket slots (DRC
anonymous Edge.Cuts rectangles 10 -> 17). The fix is a DSN keepout over each
slot. A hard-coded coordinate table would silently rot the moment a socket
moves, so the only acceptable implementation reads the socket boxes off the
board. These tests pin that property plus the insertion safety.
"""
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HARDWARE = REPO / "tracker" / "hardware"
PY = "/usr/bin/python3.14"
BOARD = "tracker/hardware/hub_board_v9_routed_stitched.kicad_pcb"

PRELUDE = (
    "import sys\n"
    "sys.path.insert(0, '/usr/lib/python3/dist-packages')\n"
    f"sys.path.insert(0, r'{HARDWARE}')\n"
    "import route_hub_v9_freerouting as R\n"
)


def _run(body: str) -> str:
    r = subprocess.run([PY, "-c", PRELUDE + body], cwd=str(REPO),
                       capture_output=True, text=True, timeout=240)
    return (r.stdout or "") + (r.stderr or "")


def test_keepout_regions_derived_from_board_geometry():
    """Four J_W* sockets with Edge.Cuts => four keepout regions, and the
    keepout count must track the live board, not a constant."""
    out = _run(
        f"R.export_dsn('{BOARD}','/tmp/ko_test.dsn')\n"
        "c=open('/tmp/ko_test.dsn').read()\n"
        "print('KEEPOUTS', c.count('(keepout'))\n"
    )
    assert "KEEPOUTS 4" in out, f"expected 4 keepout regions (one per J_W*), got:\n{out[-600:]}"


def test_keepout_polygons_land_inside_dsn_structure():
    """The keepouts must be inserted into (structure ...), before the library."""
    out = _run(
        f"R.export_dsn('{BOARD}','/tmp/ko_test2.dsn')\n"
        "c=open('/tmp/ko_test2.dsn').read()\n"
        "s=c.index('(structure'); e=c.index('(library')\n"
        "seg=c[s:e]\n"
        "print('IN_STRUCT', seg.count('(keepout'), 'VIAS', seg.count('(via'))\n"
    )
    m = re.search(r"IN_STRUCT (\d+) VIAS (\d+)", out)
    assert m, f"could not parse:\n{out[-600:]}"
    assert int(m.group(1)) == 4, f"keepouts not inside structure block:\n{out[-600:]}"
    assert int(m.group(2)) >= 1, f"via defs missing -- insertion broke DSN:\n{out[-600:]}"


def test_keepout_is_idempotent():
    """Re-running must not stack duplicate keepout blocks."""
    out = _run(
        f"R.export_dsn('{BOARD}','/tmp/ko_idem.dsn')\n"
        f"R.patch_dsn_keepouts('/tmp/ko_idem.dsn','{BOARD}')\n"
        "print('COUNT', open('/tmp/ko_idem.dsn').read().count('(keepout'))\n"
    )
    assert "COUNT 4" in out, f"idempotency broken (expected 4, no doubling):\n{out[-600:]}"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    bad = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
            bad += 1
    sys.exit(1 if bad else 0)
