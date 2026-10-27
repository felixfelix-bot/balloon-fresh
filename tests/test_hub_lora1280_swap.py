"""Gates for the U_E28 -> U_LORA1280 swap on hub v10 (ADR-139 step 3).

Asserts the *identity and wiring* of the part, not the routing state — routing is graded by
DRC, and these must keep passing while the link is being re-routed.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
BOARD = REPO / "tracker/hardware/hub_board_v10.kicad_pcb"

# E28 pin -> the net that carried that function
EXPECTED = {
    "1": ("DIO2", "/E28_DIO2"),
    "2": ("DIO3", "/E28_DIO3"),
    "3": ("VCC", "+3V3"),
    "4": ("GND", "GND"),
    "5": ("MISO", "/SPI1_MISO"),
    "6": ("MOSI", "/SPI1_MOSI"),
    "7": ("SCK", "/SPI1_SCK"),
    "8": ("NSS", "/E28_CS_N"),
    "9": ("ANT", ""),
    "10": ("GND", "GND"),
    "11": ("GND", "GND"),
    "12": ("GND", "GND"),
    "13": ("NRESET", "/E28_RESET_N"),
    "14": ("GND", "GND"),
    "15": ("BUSY", "/E28_BUSY"),
    "16": ("DIO1", "/E28_DIO1"),
}


def _pcbnew_ok() -> bool:
    try:
        r = subprocess.run([sys.executable, "-c", "import pcbnew; print(pcbnew.Version())"],
                           capture_output=True, text=True, timeout=60)
        return r.returncode == 0
    except Exception:
        return False


needs_pcbnew = pytest.mark.skipif(not _pcbnew_ok(), reason="pcbnew not importable")


def _dump() -> dict:
    code = f"""
import json, pcbnew
b = pcbnew.LoadBoard({str(BOARD)!r})
refs = [f.GetReference() for f in b.GetFootprints()]
out = {{"refs": refs, "pads": {{}}}}
fp = next((f for f in b.GetFootprints() if f.GetReference() == "U_LORA1280"), None)
if fp is not None:
    out["pos"] = [fp.GetPosition().x / 1e6, fp.GetPosition().y / 1e6]
    for p in fp.Pads():
        out["pads"][p.GetNumber()] = [p.GetPinFunction(), p.GetNetname()]
print(json.dumps(out))
"""
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr[-800:]
    return json.loads(r.stdout.strip().splitlines()[-1])


@needs_pcbnew
def test_new_part_replaces_the_e28():
    d = _dump()
    assert "U_LORA1280" in d["refs"], "the LoRa1280 must be on the board"
    assert "U_E28" not in d["refs"], "the E28 must be gone, not shadowed"


@needs_pcbnew
def test_every_pad_is_on_the_right_net():
    """Pin order changed, so this is the assertion that matters: a swap that kept pin
    numbers but not functions would route SPI onto GND and look structurally fine."""
    d = _dump()
    assert len(d["pads"]) == 16
    for pin, (func, net) in EXPECTED.items():
        got_func, got_net = d["pads"][pin]
        assert got_func == func, f"pin {pin} function {got_func!r} != {func!r}"
        assert (got_net or "") == net, f"pin {pin} net {got_net!r} != {net!r}"


@needs_pcbnew
def test_antenna_pad_is_netless():
    """ADR-137: the antenna attaches at the module. No net, no copper planned to it."""
    d = _dump()
    assert d["pads"]["9"][0] == "ANT"
    assert not d["pads"]["9"][1]


@needs_pcbnew
def test_no_enable_nets_survive():
    """TX_EN/RX_EN do not exist on this part; nothing on the board may still carry them."""
    d = _dump()
    nets = {n for _, n in d["pads"].values() if n}
    assert not any("EN" == n.split("/")[-1] for n in nets)
    assert "TX_EN" not in json.dumps(d) and "RX_EN" not in json.dumps(d)


@needs_pcbnew
def test_placement_clears_the_neighbours():
    """The 16x16 body is taller at the top edge than the 15x20 it replaced and landed
    4.76 mm^2 inside U6's courtyard; the part was shifted +1.5 mm to clear it."""
    code = f"""
import json, pcbnew
b = pcbnew.LoadBoard({str(BOARD)!r})
fp = next(f for f in b.GetFootprints() if f.GetReference() == "U_LORA1280")
c = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
clashes = []
for f in b.GetFootprints():
    if f.GetReference() == "U_LORA1280":
        continue
    try:
        cc = f.GetCourtyard(pcbnew.F_CrtYd)
        if cc.OutlineCount() == 0:
            continue
        cb = cc.BBox()
    except Exception:
        continue
    ox = min(c.GetRight(), cb.GetRight()) - max(c.GetLeft(), cb.GetLeft())
    oy = min(c.GetBottom(), cb.GetBottom()) - max(c.GetTop(), cb.GetTop())
    if ox > 0 and oy > 0:
        clashes.append([f.GetReference(), round(ox * oy / 1e12, 3)])
print(json.dumps(clashes))
"""
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr[-800:]
    clashes = json.loads(r.stdout.strip().splitlines()[-1])
    assert clashes == [], f"courtyard overlaps: {clashes}"
