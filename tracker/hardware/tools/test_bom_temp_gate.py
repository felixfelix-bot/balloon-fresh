#!/usr/bin/env python3
"""Tests for the ADR-043 deterministic BOM cold-temperature gate.

Run:  python3 -m pytest tracker/hardware/tools/test_bom_temp_gate.py -q
  or: python3 tracker/hardware/tools/test_bom_temp_gate.py
"""

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bom_temp_gate as g  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def _write(path, rows, header=("ref", "value", "mpn", "rated_min_c", "rated_max_c", "source")):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for r in rows:
            w.writerow(r)
    return path


def _run(bom, ratings, mission=-60.0, strict=False):
    argv = ["--bom", bom, "--ratings", ratings, "--mission-min", str(mission)]
    if strict:
        argv.append("--strict-provenance")
    return g.main(argv)


def test_all_parts_in_range_is_pass(tmp_path):
    bom = _write(str(tmp_path / "b.csv"), [
        ("U9", "COLDCHIP", "", "-65", "125", "datasheet"),
        ("R1", "10k", "", "-60", "155", "datasheet"),  # boundary: == mission min -> PASS
    ])
    ratings = _write(str(tmp_path / "r.csv"), [], header=("key", "rated_min_c", "rated_max_c", "source"))
    assert _run(bom, ratings) == g.EXIT_PASS


def test_part_above_mission_min_is_fail(tmp_path):
    bom = _write(str(tmp_path / "b.csv"), [
        ("U2", "LoRa2021_Gen4", "", "-40", "85", "docs/assets/lr2021/README.md:137"),
        ("R1", "10k", "", "-60", "155", "datasheet"),
    ])
    ratings = _write(str(tmp_path / "r.csv"), [], header=("key", "rated_min_c", "rated_max_c", "source"))
    assert _run(bom, ratings) == g.EXIT_FAIL


def test_missing_temperature_is_cannot_verify_not_pass(tmp_path):
    bom = _write(str(tmp_path / "b.csv"), [
        ("U9", "MYSTERYCHIP", "", "", "", ""),
        ("R1", "10k", "", "-65", "155", "datasheet"),
    ])
    ratings = _write(str(tmp_path / "r.csv"), [], header=("key", "rated_min_c", "rated_max_c", "source"))
    rc = _run(bom, ratings)
    assert rc == g.EXIT_CANNOT_VERIFY
    assert rc != g.EXIT_PASS  # never a silent pass


def test_fail_outranks_cannot_verify(tmp_path):
    bom = _write(str(tmp_path / "b.csv"), [
        ("U2", "LoRa2021_Gen4", "", "-40", "85", "src"),
        ("U9", "MYSTERYCHIP", "", "", "", ""),
    ])
    ratings = _write(str(tmp_path / "r.csv"), [], header=("key", "rated_min_c", "rated_max_c", "source"))
    assert _run(bom, ratings) == g.EXIT_FAIL


def test_ratings_db_lookup_by_value(tmp_path):
    bom = _write(str(tmp_path / "b.csv"), [("C_CAP", "1F_5.5V", "", "", "", "")])
    ratings = _write(str(tmp_path / "r.csv"),
                     [("1F_5.5V", "-40", "70", "docs/adr/006-supercapacitor-power.md:63")],
                     header=("key", "rated_min_c", "rated_max_c", "source"))
    assert _run(bom, ratings) == g.EXIT_FAIL  # -40 > -60


def test_empty_bom_is_cannot_verify(tmp_path):
    bom = _write(str(tmp_path / "b.csv"), [])
    ratings = _write(str(tmp_path / "r.csv"), [], header=("key", "rated_min_c", "rated_max_c", "source"))
    assert _run(bom, ratings) == g.EXIT_CANNOT_VERIFY


def test_missing_file_is_cannot_verify(tmp_path):
    assert g.main(["--bom", str(tmp_path / "nope.csv")]) == g.EXIT_CANNOT_VERIFY


def test_strict_provenance_fails_unverified_source_closed(tmp_path):
    bom = _write(str(tmp_path / "b.csv"), [("U1", "ESP32-C3-WROOM-02", "", "-40", "85", "TODO(unverified)")])
    ratings = _write(str(tmp_path / "r.csv"), [], header=("key", "rated_min_c", "rated_max_c", "source"))
    assert _run(bom, ratings, strict=False) == g.EXIT_FAIL
    assert _run(bom, ratings, strict=True) == g.EXIT_CANNOT_VERIFY


def test_seed_ratings_flag_the_two_known_offenders(tmp_path):
    bom = _write(str(tmp_path / "b.csv"), [
        ("U2", "LoRa2021_Gen4", "", "", "", ""),
        ("C_CAP", "1F_5.5V", "", "", "", ""),
    ])
    assert _run(bom, os.path.join(HERE, "bom_ratings.csv")) == g.EXIT_FAIL


def test_real_v8i_pcb_gate_runs_and_reports_offenders():
    """Real PCB path: derive BOM from v8i_krt_gnss.kicad_pcb if reachable.

    The PCB lives in a sibling worktree; skip (not fail) if it is not present
    so the test is portable, but assert hard when it IS present.
    """
    pcb = "/home/c03rad0r/worktrees/v8j-ms5611-reroute/tracker/hardware/output/v8i_krt_gnss.kicad_pcb"
    if not os.path.exists(pcb):
        return  # portable skip
    rc = g.main(["--pcb", pcb, "--ratings", os.path.join(HERE, "bom_ratings.csv")])
    # LR2021 is rated -40 C, mission is -60 C -> must FAIL, never PASS.
    assert rc == g.EXIT_FAIL


def test_pcb_parser_finds_28_footprints():
    pcb = "/home/c03rad0r/worktrees/v8j-ms5611-reroute/tracker/hardware/output/v8i_krt_gnss.kicad_pcb"
    if not os.path.exists(pcb):
        return
    rows = g.parse_pcb(pcb)
    assert len(rows) == 28
    vals = {r[1] for r in rows}
    assert "LoRa2021_Gen4" in vals


def _run_all():
    import tempfile
    import pathlib
    import traceback

    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    passed = failed = 0
    for name, fn in tests:
        with tempfile.TemporaryDirectory() as td:
            try:
                if "tmp_path" in fn.__code__.co_varnames:
                    fn(pathlib.Path(td))
                else:
                    fn()
                print("PASS", name)
                passed += 1
            except AssertionError:
                print("FAIL", name)
                traceback.print_exc()
                failed += 1
    print("\n%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())
