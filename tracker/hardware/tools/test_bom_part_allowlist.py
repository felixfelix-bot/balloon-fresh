"""RED test for the BOM/board ordering-trap gate (tracker/hardware/tools/bom_part_allowlist.py).

The trap: G-NiceRF makes two modules whose names differ by one character in the
chip generation:

    CORRECT  : G-NiceRF LoRa2021F33-2G4   (SEMTECH LR2021)
    FORBIDDEN: G-NiceRF LoRa1121F33-2G4   (SEMTECH LR1121)  <- a DIFFERENT module

The LCSC/JLC catalogue listing for the wrong one is `LoRa1121F33-2G4-868MHz`.
ADR-029 records this as a live trap for whoever places the JLCPCB order.

Contract (fail-closed, deterministic, no network, no inference):

    exit 0  -> input read, no forbidden token found
    exit 1  -> input read, at least one forbidden token found
    exit 2  -> input could not be read (missing file, unreadable, no path given)

The forbidden tokens are matched case-insensitively as substrings:
    "LoRa1121", "LR1121", "LoRa1121F33-2G4-868MHz"
"""

import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
CHECKER = TOOLS / "bom_part_allowlist.py"


def run_checker(*args):
    """Run the checker as a real subprocess so the exit code is the real exit code."""
    proc = subprocess.run(
        [sys.executable, str(CHECKER), *[str(a) for a in args]],
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


# --------------------------------------------------------------------------
# 1. exit 2 — cannot read the input (fail-closed)
# --------------------------------------------------------------------------

def test_no_argument_is_exit_2():
    code, out, err = run_checker()
    assert code == 2, f"no argument must be exit 2, got {code}\n{out}\n{err}"


def test_missing_file_is_exit_2(tmp_path):
    code, out, err = run_checker(tmp_path / "does_not_exist.kicad_pcb")
    assert code == 2, f"missing file must be exit 2, got {code}\n{out}\n{err}"


def test_directory_is_exit_2(tmp_path):
    code, out, err = run_checker(tmp_path)
    assert code == 2, f"a directory must be exit 2, got {code}\n{out}\n{err}"


# --------------------------------------------------------------------------
# 2. exit 1 — the trap, in each file flavour
# --------------------------------------------------------------------------

def test_text_bom_with_lcsc_listing_name_fails(tmp_path):
    bom = tmp_path / "bom.csv"
    bom.write_text(
        "Comment,Designator,Footprint,LCSC\n"
        'LoRa1121F33-2G4-868MHz,U1,RF_Module,C123456\n',
        encoding="utf-8",
    )
    code, out, err = run_checker(bom)
    assert code == 1, f"forbidden part must be exit 1, got {code}\n{out}\n{err}"
    assert "LoRa1121" in out


def test_kicad_pcb_with_forbidden_footprint_fails(tmp_path):
    pcb = tmp_path / "board.kicad_pcb"
    pcb.write_text(
        "(kicad_pcb (version 20240108)\n"
        '  (footprint "RF_Module:LoRa1121F33_2G4" (layer "F.Cu")\n'
        '    (property "Reference" "U1")\n'
        "  )\n"
        ")\n",
        encoding="utf-8",
    )
    code, out, err = run_checker(pcb)
    assert code == 1, f"forbidden footprint must be exit 1, got {code}\n{out}\n{err}"


def test_netlist_with_bare_chip_name_fails(tmp_path):
    net = tmp_path / "board.net"
    net.write_text('(comp (ref U1) (value LR1121) (footprint RF_Module:LoRa2021))\n',
                   encoding="utf-8")
    code, out, err = run_checker(net)
    assert code == 1, f"bare LR1121 must be exit 1, got {code}\n{out}\n{err}"


def test_forbidden_token_is_case_insensitive(tmp_path):
    bom = tmp_path / "bom.txt"
    bom.write_text("U1 lora1121f33-2g4-868mhz consign\n", encoding="utf-8")
    code, out, err = run_checker(bom)
    assert code == 1, f"lowercase lora1121 must be exit 1, got {code}\n{out}\n{err}"


def test_report_names_the_line(tmp_path):
    bom = tmp_path / "bom.csv"
    bom.write_text("Comment\nC1\nLoRa1121F33-2G4-868MHz\n", encoding="utf-8")
    code, out, err = run_checker(bom)
    assert code == 1
    # the operator must be told WHERE, not just that something is wrong
    assert "3" in out, f"expected the offending line number (3) in the report:\n{out}"


# --------------------------------------------------------------------------
# 3. exit 0 — the correct part must pass
# --------------------------------------------------------------------------

def test_correct_module_passes(tmp_path):
    bom = tmp_path / "bom.csv"
    bom.write_text(
        "Comment,LCSC\n"
        "LoRa2021F33-2G4-868MHz,C12345\n",   # correct part, note the 2021
        encoding="utf-8",
    )
    code, out, err = run_checker(bom)
    assert code == 0, f"correct module must be exit 0, got {code}\n{out}\n{err}"


def test_bare_lora2021_and_sx1280_pass(tmp_path):
    bom = tmp_path / "bom.csv"
    bom.write_text(
        "Comment,Designator\n"
        "LoRa2021_Castellated,U2\n"
        "LoRa2021_Gen4,U3\n"
        "SX1280IMLTRT,U4\n"
        "ESP32-S3-WROOM-1U-N8R8,U5\n"
        "MAX-M10S,U6\n",
        encoding="utf-8",
    )
    code, out, err = run_checker(bom)
    assert code == 0, f"correct parts must be exit 0, got {code}\n{out}\n{err}"


def test_empty_file_passes(tmp_path):
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    code, out, err = run_checker(empty)
    assert code == 0, f"empty input is clean, got {code}\n{out}\n{err}"


# --------------------------------------------------------------------------
# 4. multiple paths, and a token that merely looks close must NOT fire
# --------------------------------------------------------------------------

def test_multiple_inputs_one_dirty_fails(tmp_path):
    clean = tmp_path / "clean.csv"
    clean.write_text("LoRa2021F33-2G4\n", encoding="utf-8")
    dirty = tmp_path / "dirty.csv"
    dirty.write_text("LR1121\n", encoding="utf-8")
    code, out, err = run_checker(clean, dirty)
    assert code == 1, f"one dirty input must fail the run, got {code}\n{out}\n{err}"


def test_near_miss_tokens_do_not_fire(tmp_path):
    """Substrings that must NOT trip the gate (guards against over-broad matching)."""
    bom = tmp_path / "bom.csv"
    bom.write_text(
        "description\n"
        "LR2021 module\n"
        "LoRa2021F33-2G4-433MHz\n"
        "SX1121\n"
        "LR1120\n",
        encoding="utf-8",
    )
    code, out, err = run_checker(bom)
    assert code == 0, f"near-miss tokens must not fire, got {code}\n{out}\n{err}"
