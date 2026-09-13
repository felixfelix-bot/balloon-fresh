#!/usr/bin/env python3
"""test_range_check.py — union test suite for the consolidated range-check.

Run:  python3 -m pytest tools/test_range_check.py -v
      (or `make range-test-host` from firmware/e80-stm32-bench/)

Two lineages, both kept green by this file:

v1 (main / worker-balloon/range-check) — CLI-level behavior:
  - Per cfg i: rows with session==SESSION && config==i.
  - counted = best pass across replicates with replicate > WARMUP_REPLICATES
    (first 2 replicates are warmups, never counted).
  - MISS = no counted pkts; THIN = best pass < thin_frac*n_pkts; else OK.
  - PASS iff all OK (exit 0); GAPS exit 1 + resend preset with ONLY the
    missing+thin cfgs (v1 renumbered form + v2 idx-preserved form).
  - Zero STAT rows for the session = LOGGING GAP verdict (logger problem,
    no resend file). STAT rows with rx=0 are DATA (RF death), not a gap.
  - STAT parsing survives the per_ci_x1e6=[lo,hi] bracket-comma.
  - load_config_preset resolves repo-root-relative CONFIGS paths.
  - Makefile wiring: range-check target + relative T0=+NN resolution.

v2 (worker-balloon/range-check2) — library-level behavior:
  - T0-anchored cycle scheduling (compute_cycle_len / build_preset_schedule /
    compute_late_skip): no drift, no silent late-launch re-anchoring.
  - analyze_capture best-pass semantics + summary/render helpers.
  - rx-log parsing (harmonized + legacy) + T0-tagged per-stop log discovery.
  - merge_csvs best-pass harmonized merge + STAT bracket-CI parsing.
  - Makefile wiring: T0-tagged log filenames + --skip-late-configs.

Fixtures are synthetic rx-log text built with the SAME formatters the rx
logger uses (e80_bench_ctl.format_pkt_line / format_stat_line), so the
tests track the real on-wire format. No hardware, no serial.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

import pytest

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
E80_DIR = os.path.dirname(TOOLS_DIR)
REPO_ROOT = os.path.abspath(os.path.join(E80_DIR, "..", ".."))

sys.path.insert(0, TOOLS_DIR)

import e80_bench_ctl as ctl  # noqa: E402
import merge_csvs             # noqa: E402
import range_check            # noqa: E402
from e80_bench_ctl import format_pkt_line, format_stat_line, load_config_preset  # noqa: E402

SESSION = 2608281130
OTHER_SESSION = 9912312359


# -----------------------------------------------------------------------
# Fixture builders (mirror the real rx-log format) — v1 lineage
# -----------------------------------------------------------------------

def make_preset_dict(n_cfgs=3, n_pkts=10):
    """Small stop-like preset with the same schema as configs/per-stop/."""
    cfgs = []
    for i in range(n_cfgs):
        cfgs.append({
            "label": "CFG%d" % i,
            "band": "868",
            "mod": "flrc" if i % 2 == 0 else "lora",
            "sf": None if i % 2 == 0 else 5 + i,
            "bw": None if i % 2 == 0 else 500,
            "br": 650 + i if i % 2 == 0 else None,
            "pa": 22,
            "freq": 869525000,
            "plen": 255,
            "gap": 1000,
            "n_pkts": n_pkts,
        })
    return {"name": "stop-test", "description": "synthetic test stop", "configs": cfgs}


def write_preset(tmp_path, preset=None, name="stop-50m.json"):
    preset = preset or make_preset_dict()
    per_stop = tmp_path / "configs" / "per-stop"
    per_stop.mkdir(parents=True, exist_ok=True)
    path = per_stop / name
    path.write_text(json.dumps(preset, indent=2))
    return str(path)


def pkt_line(config, replicate, seq=1, session=SESSION):
    return format_pkt_line({
        "session_id": session, "config_id": config, "replicate": replicate,
        "seq": seq, "ts_ms": 1000 + seq, "rssi_dbm": -80.5, "snr_db": 9.0,
        "crc_ok": 1, "bit_err": 0, "bytes_bad": 0, "freq_hz": 869525000,
        "mod": "flrc", "sf": 0, "bw_khz": 1200, "cr": 1, "power_dbm": 22,
        "pkt_size": 255, "gps_fix": 0, "gps_lat": 0.0, "gps_lon": 0.0,
        "gps_alt": 0.0, "gps_sats": 0, "gps_hdop": 0.0,
    })


def stat_line(config, replicate, rx=10, session=SESSION):
    return format_stat_line("RX", {
        "sent": 12, "sent_ok": 12, "recv": rx, "crc_err": 0,
        "per_pct": 0.0, "per_ci_lo_pct": 0.0, "per_ci_hi_pct": 25.8,
        "elapsed_s": 1.234, "kbps": 42.5, "rssi": -80.5, "snr": 9.0,
        "drops": 0, "gap_us": 1000,
    }, session, config, replicate)


def write_rx_log(tmp_path, lines, name="rx-log.csv"):
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n")
    return str(path)


def clean_log(n_cfgs=3, n_pkts=10, replicate=3):
    """Every cfg fully received on replicate 3 (+ warmup rows on 1,2)."""
    lines = ["# DISTRIBUTED_RX_MODE t0=2026-08-28T11:30:00 loop=3"]
    for c in range(n_cfgs):
        for rep in (1, 2):  # warmups — logged but never counted
            for s in range(2):
                lines.append(pkt_line(c, rep, seq=s))
            lines.append(stat_line(c, rep, rx=2))
        for s in range(n_pkts):
            lines.append(pkt_line(c, replicate, seq=s))
        lines.append(stat_line(c, replicate, rx=n_pkts))
    return lines


def run_tool(tmp_path, dist="50m", session=str(SESSION), rx_log=None,
             preset=None, repo_root=None, extra=()):
    """Run range_check.py as a subprocess; return CompletedProcess."""
    cmd = [sys.executable, os.path.join(TOOLS_DIR, "range_check.py"),
           "--dist", dist, "--session", session,
           "--rx-log", rx_log or str(tmp_path / "rx-log.csv")]
    if preset:
        cmd += ["--configs", preset]
    if repo_root:
        cmd += ["--repo-root", repo_root]
    cmd += list(extra)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=E80_DIR)


RESEND_NAME = "configs/resend-50m-s%d.json" % SESSION
TX_ONE_LINER = ("make range-tx CONFIGS=%s T0=+90 "
                "PROBE=148757200D2D1425 PORT=<from detect>" % RESEND_NAME)


# -----------------------------------------------------------------------
# Verdicts + exit codes — v1 lineage
# -----------------------------------------------------------------------

class TestVerdicts:
    """PASS / GAPS(MISS|THIN) / LOGGING GAP verdicts and exit codes."""

    def test_clean_pass_exit0(self, tmp_path):
        preset = write_preset(tmp_path)
        log = write_rx_log(tmp_path, clean_log())
        r = run_tool(tmp_path, preset=preset, rx_log=log, repo_root=str(tmp_path))
        assert r.returncode == 0, r.stdout + r.stderr
        assert "50m s%d: PASS (3/3 clean)" % SESSION in r.stdout

    def test_missing_cfg_is_miss_and_gap(self, tmp_path):
        # drop ALL of cfg1's packets (warmups + counted pass) — a config
        # the radio never heard. Under the conditional warmup rule a
        # capture with <= WARMUP_REPLICATES replicates counts them, so a
        # true MISS needs zero captured packets for the config.
        lines = [ln for ln in clean_log(n_cfgs=3)
                 if not (ln.startswith("PKT,") and re.match(r"PKT,\d+,1,", ln))]
        preset = write_preset(tmp_path)
        log = write_rx_log(tmp_path, lines)
        r = run_tool(tmp_path, preset=preset, rx_log=log, repo_root=str(tmp_path))
        assert r.returncode == 1
        assert "GAPS" in r.stdout
        assert "c1:MISS" in r.stdout
        assert "(2/3 clean)" in r.stdout

    def test_thin_cfg_reports_count(self, tmp_path):
        lines = clean_log(n_cfgs=3)
        thin = [pkt_line(2, 3, seq=s) for s in range(3)]  # only 3 of 10
        lines = [ln for ln in lines
                 if not (ln.startswith("PKT,") and ",2,3," in ln)] + thin
        preset = write_preset(tmp_path)
        log = write_rx_log(tmp_path, lines)
        r = run_tool(tmp_path, preset=preset, rx_log=log, repo_root=str(tmp_path))
        assert r.returncode == 1
        assert "c2:THIN 3/10" in r.stdout

    def test_warmup_only_is_gaps_not_logging_gap(self, tmp_path):
        lines = ["# DISTRIBUTED_RX_MODE"]
        for c in range(3):
            for rep in (1, 2):  # only warmup replicates present
                lines.append(pkt_line(c, rep, seq=0))
                lines.append(stat_line(c, rep, rx=1))
        preset = write_preset(tmp_path)
        log = write_rx_log(tmp_path, lines)
        r = run_tool(tmp_path, preset=preset, rx_log=log, repo_root=str(tmp_path))
        assert r.returncode == 1
        assert "LOGGING GAP" not in r.stdout
        assert "GAPS" in r.stdout
        assert "(0/3 clean)" in r.stdout

    def test_empty_log_is_logging_gap(self, tmp_path):
        preset = write_preset(tmp_path)
        log = write_rx_log(tmp_path, [])
        r = run_tool(tmp_path, preset=preset, rx_log=log, repo_root=str(tmp_path))
        assert r.returncode == 1
        assert "LOGGING GAP" in r.stdout
        assert not (tmp_path / RESEND_NAME).exists()

    def test_missing_log_file_is_logging_gap(self, tmp_path):
        preset = write_preset(tmp_path)
        r = run_tool(tmp_path, preset=preset,
                     rx_log=str(tmp_path / "nope.csv"), repo_root=str(tmp_path))
        assert r.returncode == 1
        assert "LOGGING GAP" in r.stdout

    def test_rx0_stat_rows_are_rf_death_not_gap(self, tmp_path):
        lines = ["# DISTRIBUTED_RX_MODE"]
        for c in range(3):
            lines.append(stat_line(c, 3, rx=0))  # logger alive, radio heard nothing
        preset = write_preset(tmp_path)
        log = write_rx_log(tmp_path, lines)
        r = run_tool(tmp_path, preset=preset, rx_log=log, repo_root=str(tmp_path))
        assert r.returncode == 1
        assert "LOGGING GAP" not in r.stdout
        assert "c0:MISS" in r.stdout  # data verdict: RF death

    def test_other_session_rows_ignored(self, tmp_path):
        lines = ["# two sessions interleaved"]
        for c in range(3):
            for s in range(10):
                lines.append(pkt_line(c, 3, seq=s, session=OTHER_SESSION))
            lines.append(stat_line(c, 3, rx=10, session=OTHER_SESSION))
            lines.append(stat_line(c, 3, rx=0, session=SESSION))
        preset = write_preset(tmp_path)
        log = write_rx_log(tmp_path, lines)
        r = run_tool(tmp_path, preset=preset, rx_log=log, repo_root=str(tmp_path))
        assert "LOGGING GAP" not in r.stdout
        assert "c0:MISS" in r.stdout

    def test_multi_replicate_counts_best_pass(self, tmp_path):
        """4 pkts on rep3 + 6 pkts on rep4: best pass 6/10 >= thin_frac — OK.

        (v1 summed across replicates; the harmonized merge policy counts the
        BEST pass, matching merge_csvs — 6/10 still clears the 0.5 floor.)
        """
        lines = ["# 4 pkts on rep3 + 6 pkts on rep4 = full"]
        for c in range(3):
            for s in range(4):
                lines.append(pkt_line(c, 3, seq=s))
            for s in range(6):
                lines.append(pkt_line(c, 4, seq=s))
            lines.append(stat_line(c, 3, rx=4))
            lines.append(stat_line(c, 4, rx=6))
        preset = write_preset(tmp_path)
        log = write_rx_log(tmp_path, lines)
        r = run_tool(tmp_path, preset=preset, rx_log=log, repo_root=str(tmp_path))
        assert r.returncode == 0, r.stdout + r.stderr

    def test_dist_bare_number_normalizes(self, tmp_path):
        preset = write_preset(tmp_path, name="stop-100m.json")
        log = write_rx_log(tmp_path, clean_log())
        r = run_tool(tmp_path, dist="100", preset=preset, rx_log=log,
                     repo_root=str(tmp_path))
        assert r.returncode == 0
        assert "100m s%d: PASS" % SESSION in r.stdout


# -----------------------------------------------------------------------
# Warmup exclusion vs single-cycle (loop=1) stops — sweep-day hotfix
# -----------------------------------------------------------------------

class TestLoop1WarmupRegression:
    """loop=1 stops log replicate=1 for every packet.

    e80_bench_ctl sends ``CONFIG <idx> <cycle>`` so the CSV ``replicate``
    field IS the cycle number, and ``make range-tx`` defaults ``--loop 1``
    → single-cycle stops produce replicate=1-only captures. The old
    unconditional ``replicate > WARMUP_REPLICATES`` filter turned complete
    single-cycle captures into all-MISS verdicts + bogus full resend
    presets. The exclusion must be conditional: only drop the first
    WARMUP_REPLICATES when MORE than WARMUP_REPLICATES distinct
    replicates exist for the config (a multi-cycle run).
    """

    def test_loop1_full_reception_is_complete(self, tmp_path):
        """Every packet replicate=1, reception complete → COMPLETE/OK."""
        lines = ["# DISTRIBUTED_RX_MODE t0=2026-08-28T12:00:00 loop=1"]
        for c in range(3):
            for s in range(10):
                lines.append(pkt_line(c, 1, seq=s))
            lines.append(stat_line(c, 1, rx=10))
        preset = write_preset(tmp_path)
        log = write_rx_log(tmp_path, lines)
        r = run_tool(tmp_path, preset=preset, rx_log=log, repo_root=str(tmp_path))
        assert r.returncode == 0, r.stdout + r.stderr
        assert "50m: COMPLETE 3/3" in r.stdout
        assert "50m s%d: PASS (3/3 clean)" % SESSION in r.stdout
        assert "MISS" not in r.stdout
        assert not (tmp_path / RESEND_NAME).exists()

    def test_loop1_counted_gt_zero(self):
        """Library level: replicate=1-only capture with warmup_replicates=2
        must still count (>0) — was all-MISS before the fix."""
        cfgs = [_cfg(0, n_pkts=10), _cfg(1, n_pkts=10)]
        pkts = ([{"config_id": 0, "replicate": 1}] * 10 +
                [{"config_id": 1, "replicate": 1}] * 3)
        per = range_check.analyze_capture(
            cfgs, pkts, warmup_replicates=range_check.WARMUP_REPLICATES)
        assert per[0]["per_replicate"] == {1: 10}
        assert per[0]["n_recv"] == 10
        assert per[0]["status"] == "OK"
        assert per[1]["per_replicate"] == {1: 3}
        assert per[1]["n_recv"] > 0
        assert per[1]["status"] == "THIN"

    def test_replicates_1_and_2_only_fully_counted(self, tmp_path):
        """<= WARMUP_REPLICATES distinct replicates → nothing excluded."""
        lines = ["# DISTRIBUTED_RX_MODE t0=2026-08-28T12:00:00 loop=2"]
        for c in range(3):
            for rep in (1, 2):
                for s in range(10):
                    lines.append(pkt_line(c, rep, seq=s))
                lines.append(stat_line(c, rep, rx=10))
        preset = write_preset(tmp_path)
        log = write_rx_log(tmp_path, lines)
        r = run_tool(tmp_path, preset=preset, rx_log=log, repo_root=str(tmp_path))
        assert r.returncode == 0, r.stdout + r.stderr
        assert "50m: COMPLETE 3/3" in r.stdout
        assert "MISS" not in r.stdout

    def test_multi_cycle_warmups_still_excluded_best_pass(self, tmp_path):
        """replicates 1..4: warmups 1-2 excluded, best pass of 3-4 wins.

        Warmups are FULL (10/10) and the counted passes are 4 and 6 pkts —
        if warmups leaked into the count the verdict would flip to 10/10.
        """
        lines = ["# DISTRIBUTED_RX_MODE t0=2026-08-28T12:00:00 loop=4"]
        for c in range(3):
            for rep in (1, 2):
                for s in range(10):
                    lines.append(pkt_line(c, rep, seq=s))
                lines.append(stat_line(c, rep, rx=10))
            for s in range(4):
                lines.append(pkt_line(c, 3, seq=s))
            lines.append(stat_line(c, 3, rx=4))
            for s in range(6):
                lines.append(pkt_line(c, 4, seq=s))
            lines.append(stat_line(c, 4, rx=6))
        preset = write_preset(tmp_path)
        log = write_rx_log(tmp_path, lines)
        r = run_tool(tmp_path, preset=preset, rx_log=log, repo_root=str(tmp_path))
        assert r.returncode == 0, r.stdout + r.stderr  # 6/10 >= thin_frac
        assert "6/10" in r.stdout      # best pass of reps 3-4
        assert "10/10" not in r.stdout  # warmups 1-2 did NOT leak in

    def test_multi_cycle_per_replicate_exact(self):
        """Library level: replicates 1..4 → per_replicate {3:4, 4:6}."""
        cfgs = [_cfg(0, n_pkts=10)]
        pkts = ([{"config_id": 0, "replicate": 1}] * 10 +
                [{"config_id": 0, "replicate": 2}] * 10 +
                [{"config_id": 0, "replicate": 3}] * 4 +
                [{"config_id": 0, "replicate": 4}] * 6)
        per = range_check.analyze_capture(
            cfgs, pkts, warmup_replicates=range_check.WARMUP_REPLICATES)
        assert per[0]["per_replicate"] == {3: 4, 4: 6}
        assert per[0]["n_recv"] == 6
        assert per[0]["status"] == "OK"


# -----------------------------------------------------------------------
# Resend preset output — v1 lineage
# -----------------------------------------------------------------------

class TestResendPreset:
    """On GAPS: write resend-<DIST>-s<SESSION>.json with ONLY gap cfgs."""

    def test_resend_contains_only_gapped_cfgs(self, tmp_path):
        lines = clean_log(n_cfgs=3)
        # cfg0: thin (3/10); cfg1: miss (drop counted rows); cfg2: clean
        lines = [ln for ln in lines if not (ln.startswith("PKT,") and ",0,3," in ln)]
        lines += [pkt_line(0, 3, seq=s) for s in range(3)]
        lines = [ln for ln in lines
                 if not (ln.startswith("PKT,") and ",1,3," in ln)]
        preset = write_preset(tmp_path)
        log = write_rx_log(tmp_path, lines)
        r = run_tool(tmp_path, preset=preset, rx_log=log, repo_root=str(tmp_path))
        assert r.returncode == 1
        resend = tmp_path / RESEND_NAME
        assert resend.exists()
        data = json.loads(resend.read_text())
        assert len(data["configs"]) == 2
        assert [c["label"] for c in data["configs"]] == ["CFG0", "CFG1"]

    def test_resend_schema_loads_via_load_config_preset(self, tmp_path):
        lines = [ln for ln in clean_log(n_cfgs=3)
                 if not (ln.startswith("PKT,") and ",2,3," in ln)]
        preset = write_preset(tmp_path)
        log = write_rx_log(tmp_path, lines)
        run_tool(tmp_path, preset=preset, rx_log=log, repo_root=str(tmp_path))
        resend = tmp_path / RESEND_NAME
        cfgs = load_config_preset(str(resend))
        assert len(cfgs) == 1
        assert cfgs[0]["label"] == "CFG2"
        assert cfgs[0]["n_pkts"] == 10
        assert cfgs[0]["idx"] == 0  # renumbered for the new session

    def test_real_stop50_resend_roundtrip(self, tmp_path):
        """Resend of real stop-50m cfgs must stay load_config_preset-valid."""
        lines = [ln for ln in clean_log(n_cfgs=10)
                 if not (ln.startswith("PKT,") and ",9,3," in ln)]
        preset = write_preset(tmp_path, preset=json.loads(
            open(os.path.join(REPO_ROOT, "configs", "per-stop", "stop-50m.json")).read()))
        log = write_rx_log(tmp_path, lines)
        r = run_tool(tmp_path, preset=preset, rx_log=log, repo_root=str(tmp_path))
        assert r.returncode == 1
        cfgs = load_config_preset(str(tmp_path / RESEND_NAME))
        assert len(cfgs) == 1
        assert cfgs[0]["label"] == "2G4-LoRa-SF5 BW500 LEN255"
        assert cfgs[0]["n_pkts"] == 10

    def test_tx_one_liner_printed_verbatim(self, tmp_path):
        lines = [ln for ln in clean_log(n_cfgs=3)
                 if not (ln.startswith("PKT,") and ",1,3," in ln)]
        preset = write_preset(tmp_path)
        log = write_rx_log(tmp_path, lines)
        r = run_tool(tmp_path, preset=preset, rx_log=log, repo_root=str(tmp_path))
        assert TX_ONE_LINER in r.stdout

    def test_no_resend_on_pass(self, tmp_path):
        preset = write_preset(tmp_path)
        log = write_rx_log(tmp_path, clean_log())
        run_tool(tmp_path, preset=preset, rx_log=log, repo_root=str(tmp_path))
        assert not (tmp_path / "configs" / ("resend-50m-s%d.json" % SESSION)).exists()


# -----------------------------------------------------------------------
# STAT row parsing (bracket field contains a comma) — v1 lineage
# -----------------------------------------------------------------------

class TestStatParsing:
    def test_parse_stat_row_handles_bracket_comma(self):
        d = range_check.parse_stat_row(
            "STAT,role=RX,sent=12,sent_ok=12,rx=10,crc_err=0,per_x1e6=0,"
            "per_ci_x1e6=[0,258000],elapsed_s=1.234,kbps=42.500,"
            "rssi_avg_dbm=-80.500,snr_avg_db=9.000,session=%d,config=2,"
            "replicate=3,drops=0,gap_us=1000" % SESSION)
        assert d["role"] == "RX"
        assert d["rx"] == "10"
        assert d["session"] == str(SESSION)
        assert d["config"] == "2"
        assert d["replicate"] == "3"
        assert d["per_ci_x1e6"] == "[0,258000]"

    def test_parse_stat_row_rejects_non_stat(self):
        assert range_check.parse_stat_row("# comment") is None
        assert range_check.parse_stat_row("PKT,1,2,3") is None


# -----------------------------------------------------------------------
# load_config_preset: repo-root-relative CONFIGS paths (resend one-liner)
# -----------------------------------------------------------------------

class TestLoadPresetRootRelative:
    """`CONFIGS=configs/resend-...json` from repo root must resolve even
    though e80_bench_ctl runs with cwd=firmware/e80-stm32-bench."""

    def test_configs_relative_to_repo_root(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)  # cwd without ./configs
        cfgs = load_config_preset("configs/per-stop/stop-50m.json")
        assert len(cfgs) == 10
        assert cfgs[0]["label"] == "FLRC-2600 LEN511"


# ---------------------------------------------------------------------------
# T0-anchored cycles — v2 lineage
# ---------------------------------------------------------------------------

def _cfg(idx, n_pkts=10, freq=870e6, mod="lora", sf=7, br=None, expected_s=9.0):
    return {
        "idx": idx, "label": "cfg{} sf{}".format(idx, sf), "mod": mod,
        "sf": sf, "bw": 125, "br": br, "pa": 22, "freq": freq,
        "plen": 255, "gap": 10000, "n_pkts": n_pkts,
        "airtime_s": 0.3, "expected_s": expected_s,
    }


class TestCycleAnchoring(unittest.TestCase):
    TIMING = dict(t0_margin=30, guard=5, settle=1, rx_lead=3,
                  swd_reset_s=2, band_swap_s=30)

    def test_cycle_len_rounds_up_to_whole_minute(self):
        cfgs = [_cfg(0), _cfg(1)]
        cl = ctl.compute_cycle_len(cfgs, **self.TIMING)
        self.assertGreater(cl, 0)
        self.assertEqual(cl % 60, 0)

    def test_cycle_len_identical_across_call_order(self):
        cfgs = [_cfg(0), _cfg(1, freq=2400e6)]
        a = ctl.compute_cycle_len(cfgs, **self.TIMING)
        b = ctl.compute_cycle_len(list(reversed(cfgs)), **self.TIMING)
        # reversed list is a DIFFERENT schedule; same list twice must match
        a2 = ctl.compute_cycle_len(cfgs, **self.TIMING)
        self.assertEqual(a, a2)

    def test_cycle_len_includes_band_wrap_gap(self):
        same_band = [_cfg(0, freq=870e6), _cfg(1, freq=870e6)]
        wraps = [_cfg(0, freq=870e6), _cfg(1, freq=2400e6)]
        cl_same = ctl.compute_cycle_len(same_band, **self.TIMING)
        cl_wrap = ctl.compute_cycle_len(wraps, **self.TIMING)
        # wrapping preset pays band_swap_s at the inter-config gap AND at
        # the wrap back to config 0 — must be strictly longer
        self.assertGreater(cl_wrap, cl_same)

    def test_late_launch_detected_against_true_schedule(self):
        """The regression that caused session 2608281130: a 150s-late RX
        must be DETECTED (skip index >= 1 or None), never silently
        re-anchored onto a fresh local schedule."""
        cfgs = [_cfg(i) for i in range(10)]
        t0 = 1_000_000
        starts = ctl.build_preset_schedule(cfgs, t0, **self.TIMING)
        idx = ctl.compute_late_skip(starts, now=t0 + 150, rx_lead=3)
        # either some configs remain joinable (idx < len) or all passed
        # (None) — but it must NOT return 0 (= "on time"), which is what
        # the old local re-anchoring always claimed.
        self.assertNotEqual(idx, 0)
        if idx is not None:
            self.assertGreaterEqual(idx, 1)

    def test_all_cycles_anchor_to_shared_t0(self):
        cfgs = [_cfg(0), _cfg(1)]
        cl = ctl.compute_cycle_len(cfgs, **self.TIMING)
        t0 = 1_000_000
        for cycle in (1, 2, 5):
            t0_cycle = t0 + (cycle - 1) * cl
            starts = ctl.build_preset_schedule(cfgs, t0_cycle, **self.TIMING)
            self.assertAlmostEqual(starts[0], t0_cycle + self.TIMING["t0_margin"],
                                   delta=0.001)
            # every cycle k+1 anchor must be AFTER cycle k's last capture
            starts_k = ctl.build_preset_schedule(cfgs, t0, **self.TIMING)
            last_end = starts_k[-1] + cfgs[-1]["expected_s"] + \
                self.TIMING["settle"] + self.TIMING["guard"]
            self.assertGreaterEqual(t0 + cl + self.TIMING["t0_margin"], last_end)


# ---------------------------------------------------------------------------
# range_check analysis — v2 lineage
# ---------------------------------------------------------------------------

class TestAnalyzeCapture(unittest.TestCase):
    def test_ok_thin_miss(self):
        cfgs = [_cfg(0, n_pkts=10), _cfg(1, n_pkts=10), _cfg(2, n_pkts=10)]
        pkts = (
            [{"config_id": 0, "replicate": 1}] * 10 +
            [{"config_id": 1, "replicate": 1}] * 3 +
            [{"config_id": 7, "replicate": 1}] * 5   # foreign config
        )
        per = range_check.analyze_capture(cfgs, pkts)
        self.assertEqual(per[0]["status"], "OK")
        self.assertEqual(per[1]["status"], "THIN")
        self.assertEqual(per[2]["status"], "MISS")
        self.assertEqual(per[0]["n_recv"], 10)
        self.assertEqual(per[1]["n_recv"], 3)

    def test_best_pass_across_replicates(self):
        cfgs = [_cfg(0, n_pkts=10)]
        pkts = ([{"config_id": 0, "replicate": 1}] * 2 +
                [{"config_id": 0, "replicate": 2}] * 9)
        per = range_check.analyze_capture(cfgs, pkts)
        self.assertEqual(per[0]["n_recv"], 9)
        self.assertEqual(per[0]["status"], "OK")
        self.assertEqual(per[0]["per_replicate"], {1: 2, 2: 9})

    def test_warmup_replicates_excluded_when_requested(self):
        """CLI path: warmup replicates never count (v1 decision procedure)."""
        cfgs = [_cfg(0, n_pkts=10)]
        pkts = ([{"config_id": 0, "replicate": 1}] * 2 +
                [{"config_id": 0, "replicate": 2}] * 2 +
                [{"config_id": 0, "replicate": 3}] * 6)
        per = range_check.analyze_capture(cfgs, pkts,
                                          warmup_replicates=range_check.WARMUP_REPLICATES)
        self.assertEqual(per[0]["per_replicate"], {3: 6})
        self.assertEqual(per[0]["n_recv"], 6)
        self.assertEqual(per[0]["status"], "OK")  # 6/10 >= 0.5

    def test_summary_lines(self):
        per = {
            0: {"n_pkts": 10, "n_recv": 10, "per_replicate": {1: 10}, "status": "OK"},
            1: {"n_pkts": 10, "n_recv": 0, "per_replicate": {}, "status": "MISS"},
            2: {"n_pkts": 10, "n_recv": 3, "per_replicate": {1: 3}, "status": "THIN"},
        }
        self.assertEqual(range_check.render_summary_line("872m", per),
                         "872m: GAPS c1 MISS, c2 THIN 3/10")
        ok = {0: {"n_pkts": 10, "n_recv": 10, "per_replicate": {1: 10}, "status": "OK"}}
        self.assertEqual(range_check.render_summary_line("50m", ok),
                         "50m: COMPLETE 1/1")

    def test_resend_preset_gaps_only_idx_preserved(self):
        cfgs = [_cfg(0), _cfg(1), _cfg(2)]
        per = {
            0: {"status": "OK"},
            1: {"status": "MISS"},
            2: {"status": "THIN", "n_recv": 3, "n_pkts": 10},
        }
        preset = range_check.build_resend_preset(cfgs, per, "872m", 2608281225)
        self.assertIsNotNone(preset)
        self.assertEqual([c["idx"] for c in preset["configs"]], [1, 2])
        self.assertEqual(preset["name"], "resend-872m-2608281225")
        self.assertIsNone(range_check.build_resend_preset(
            cfgs, {i: {"status": "OK"} for i in range(3)}, "50m", 1))

    def test_next_t0_boundary(self):
        self.assertEqual(range_check.next_t0(300, now=1000), 1200)
        self.assertEqual(range_check.next_t0(300, now=1200), 1500)

    def test_resend_commands_format(self):
        cmds = range_check.format_resend_commands(
            "configs/resend/resend-872m-2608281225.json", 1787921400, "872m")
        self.assertEqual(len(cmds), 2)
        self.assertIn("make range-tx DIST=872m "
                      "CONFIGS=configs/resend/resend-872m-2608281225.json "
                      "T0=1787921400 SESSION_ID=", cmds[0])
        self.assertIn("make range-rx", cmds[1])


# ---------------------------------------------------------------------------
# rx-log parsing (harmonized + legacy) — v2 lineage
# ---------------------------------------------------------------------------

def _pkt_line(sess, cfg, rep, seq, rssi=-80.0):
    return ("PKT,{},{},{},{},123,{:.1f},10.0,1,0,0,868000000,lora,7,125,0,"
            "22,255,0,0,0,0,0,0".format(sess, cfg, rep, seq, rssi))


class TestParseRxLog(unittest.TestCase):
    def test_harmonized(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write("# DISTRIBUTED_RX_MODE t0=...\n")
            f.write(_pkt_line(2608281225, 0, 1, 4) + "\n")
            f.write(_pkt_line(2608281225, 0, 1, 5) + "\n")
            f.write(_pkt_line(2608280930, 3, 1, 9) + "\n")
            path = f.name
        try:
            pkts, sessions = range_check.parse_rx_log(path)
            self.assertEqual(len(pkts), 3)
            self.assertEqual(sessions, {2608281225, 2608280930})
            self.assertEqual(pkts[0]["config_id"], 0)
        finally:
            os.unlink(path)

    def test_legacy(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write("session,config,pkt_idx,ts_ms,rssi_dbm,snr_db,crc_ok,"
                    "bit_err,freq_hz,mod,sf_or_br,bw,pa_dbm,len,pcrc16,captured_ts\n")
            f.write("2608281225,0,2,200,-78.0,10.0,1,0,868000000,flrc,650,0,10,64,0,"
                    "2026-08-28T17:55:50\n")
            path = f.name
        try:
            pkts, sessions = range_check.parse_rx_log(path)
            self.assertEqual(len(pkts), 1)
            self.assertEqual(sessions, {2608281225})
        finally:
            os.unlink(path)

    def test_missing_file_is_empty(self):
        pkts, sessions = range_check.parse_rx_log("/nonexistent/rx-log.csv")
        self.assertEqual(pkts, [])
        self.assertEqual(sessions, set())


# ---------------------------------------------------------------------------
# merge_csvs: harmonized best-pass — v2 lineage
# ---------------------------------------------------------------------------

def _tx_stat_line(sess, cfg, rep, n_pkts=10, label="cfg"):
    st = {"sent": n_pkts + 2, "sent_ok": n_pkts, "recv": 0, "crc_err": 0,
          "per_pct": 0.0, "elapsed_s": 9.0, "kbps": None, "rssi": None,
          "snr": None, "drops": 0, "gap_us": 10000,
          "label": label, "n_pkts": n_pkts, "plen": 255}
    return ctl.format_stat_line("TX", st, sess, cfg, replicate=rep)


class TestMergeBestPass(unittest.TestCase):
    def test_best_pass_not_union(self):
        """rep1 catches 4/10, rep2 catches 9/10 -> PER from rep2 (10%),
        NOT from the union (which would claim 0% for the 5 shared-lost)."""
        with tempfile.TemporaryDirectory() as d:
            tx = os.path.join(d, "tx.csv")
            rx = os.path.join(d, "rx.csv")
            with open(tx, "w") as f:
                f.write(_tx_stat_line(2608281225, 0, 1) + "\n")
                f.write(_tx_stat_line(2608281225, 0, 2) + "\n")
            with open(rx, "w") as f:
                # rep1: seq 0-3 (4 pkts)
                for s in range(4):
                    f.write(_pkt_line(2608281225, 0, 1, s) + "\n")
                # rep2: 9 of 10 pkts (seqs 0-9, misses seq 3)
                for s in range(10):
                    if s == 3:
                        continue
                    f.write(_pkt_line(2608281225, 0, 2, s) + "\n")
                # foreign: config not in TX log
                f.write(_pkt_line(2608281225, 9, 1, 0) + "\n")
            combined = merge_csvs.merge_csvs(tx, rx, d)
            received = sum(1 for r in combined if r["status"] == "received")
            lost = [r for r in combined if r["status"] == "lost"]
            self.assertEqual(len(combined), 10)   # denominator = n_pkts, not union
            self.assertEqual(received, 9)
            self.assertEqual(len(lost), 1)
            # pkt_idx is normalized positionally per (config, replicate):
            # rep2 captured seqs 0-2,4-8 -> normalized 0-8, so the LAST
            # expected index is the lost one
            self.assertEqual(lost[0]["pkt_idx"], 9)
            self.assertEqual(lost[0]["replicate"], 2)
            with open(os.path.join(d, "combined-range-report.md")) as f:
                report = f.read()
            self.assertIn("best pass", report)
            self.assertIn("r1: 4", report)
            self.assertIn("r2: 9", report)

    def test_legacy_still_merges(self):
        """Old-format logs keep working (regression guard)."""
        with tempfile.TemporaryDirectory() as d:
            tx = os.path.join(d, "tx.csv")
            rx = os.path.join(d, "rx.csv")
            with open(tx, "w") as f:
                f.write("session,config_idx,n_pkts,sent_ok,label\n")
                f.write("2608281225,0,10,10,cfg0\n")
            with open(rx, "w") as f:
                f.write("session,config,pkt_idx,ts_ms,rssi_dbm,snr_db,crc_ok,"
                        "bit_err,freq_hz,mod,sf_or_br,bw,pa_dbm,len,pcrc16,captured_ts\n")
                for i in range(10):
                    f.write("2608281225,0,{},{},-80.0,10.0,1,0,868000000,lora,7,125,22,"
                            "255,0,2026-08-28T18:00:00\n".format(i, i * 100))
            combined = merge_csvs.merge_csvs(tx, rx, d)
            self.assertEqual(len(combined), 10)
            self.assertTrue(all(r["status"] == "received" for r in combined))

    def test_stat_line_parse_with_bracket_ci(self):
        line = _tx_stat_line(2608281225, 3, 1, n_pkts=10, label="LoRa-SF7")
        d = merge_csvs.parse_stat_line(line)
        self.assertIsNotNone(d)
        self.assertEqual(d["role"], "TX")
        self.assertEqual(d["per_ci_x1e6"], "[0,0]")
        self.assertEqual(d["n_pkts"], "10")
        self.assertEqual(d["label"], "LoRa-SF7")

    def test_resend_preset_idx_preserved_through_reload(self):
        """The trimmed preset must keep ORIGINAL idx values after a
        load_config_preset round-trip (logs stay consistent with the
        full preset's numbering across re-send passes)."""
        cfgs = ctl.load_config_preset({
            "configs": [
                {"label": "a", "mod": "lora", "sf": 7, "bw": 125, "pa": 22,
                 "freq": 870e6, "plen": 255, "gap": 10000, "n_pkts": 10, "idx": 4},
                {"label": "b", "mod": "lora", "sf": 12, "bw": 125, "pa": 22,
                 "freq": 870e6, "plen": 255, "gap": 10000, "n_pkts": 10, "idx": 7},
            ]
        })
        self.assertEqual([c["idx"] for c in cfgs], [4, 7])
        # no explicit idx -> positional (back-compat)
        pos = ctl.load_config_preset({
            "configs": [
                {"label": "x", "mod": "lora", "sf": 7, "bw": 125, "pa": 22,
                 "freq": 870e6, "plen": 255, "gap": 10000, "n_pkts": 10},
            ]
        })
        self.assertEqual([c["idx"] for c in pos], [0])


# ---------------------------------------------------------------------------
# Makefile wiring: range-check target + relative T0=+NN — v1 lineage
# ---------------------------------------------------------------------------

class TestMakefileWiring:
    def _make(self, args, cwd):
        return subprocess.run(["make"] + args, capture_output=True,
                              text=True, cwd=cwd)

    def test_bench_range_check_target_exists(self):
        r = self._make(["-n", "range-check", "DIST=50m", "SESSION=x"], E80_DIR)
        assert r.returncode == 0, r.stderr
        assert "range_check.py" in r.stdout
        assert "--session x" in r.stdout

    def test_root_range_check_proxy(self):
        r = self._make(["-n", "range-check", "DIST=50m", "SESSION=x"], REPO_ROOT)
        assert r.returncode == 0, r.stderr
        assert "range_check.py" in r.stdout

    def test_relative_t0_resolved_to_epoch(self):
        r = self._make(["-n", "range-tx", "T0=+90"], E80_DIR)
        assert r.returncode == 0, r.stderr
        assert "--t0 +90" not in r.stdout
        assert re.search(r"--t0 1\d{9}", r.stdout), r.stdout

    def test_absolute_t0_untouched(self):
        r = self._make(["-n", "range-tx", "T0=1790000000"], E80_DIR)
        assert "--t0 1790000000" in r.stdout


# ---------------------------------------------------------------------------
# Makefile wiring: T0-tagged log filenames + late-join flag — v2 lineage
# ---------------------------------------------------------------------------

class TestMakefileLogNaming(unittest.TestCase):
    FWDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_range_tx_log_filename_includes_t0_and_session(self):
        out = subprocess.run(
            ["make", "-n", "range-tx", "DIST=50m",
             "T0=1787921400", "SESSION_ID=2608281250"],
            cwd=self.FWDIR, capture_output=True, text=True)
        self.assertIn("--tx-log", out.stdout)
        self.assertIn("tx-log-t01787921400-2608281250.csv", out.stdout)
        self.assertIn("stop-50m", out.stdout)

    def test_range_rx_late_join_flag(self):
        out = subprocess.run(
            ["make", "-n", "range-rx", "DIST=50m",
             "T0=1787921400", "SESSION_ID=2608281250"],
            cwd=self.FWDIR, capture_output=True, text=True)
        self.assertIn("--skip-late-configs", out.stdout)
        self.assertIn("rx-log-t01787921400-2608281250.csv", out.stdout)


# ---------------------------------------------------------------------------
# session_id join (GO-mode log dirs) with a t0 fallback — v3 lineage
#
# The two on-disk layouts one launch can produce:
#   legacy boundary/manual: logs/s<sid>-t0<epoch>/stop-<dist>/rx-log-*.csv
#   GO mode (--sync cvm):   logs/s<sid>-go<epoch>/rx-log.csv  (no stop level)
# range_check joins primarily on session_id (session dir name + the launch
# header's session=<sid> token) and falls back to the legacy t0 rule.
# ---------------------------------------------------------------------------

LEGACY_SESSION = "2608281250"          # legacy 10-digit int session form
GO_SESSION = "2609130435a3f"           # GO form: %y%m%d%H%M + 3-hex nonce
GO_OTHER_SESSION = "2609130501b7c"
SID_T0 = 1787921400                    # launch epoch (same value the
                                       # Makefile log-naming test uses)


def _sid_iso(t0):
    """Local-time ISO stamp exactly as the runners write it in the header."""
    return datetime.datetime.fromtimestamp(t0).isoformat()


def _write_log(path, lines):
    """Write a log file (creating parents); returns the path."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return path


def go_log(tmp_path, session=GO_SESSION, t0=SID_T0, role="rx"):
    """logs/s<session>-go<t0>/<role>-log.csv — the GO-mode layout.

    Mirrors the real writers: the RX banner (DISTRIBUTED_RX_MODE) carries no
    session= token, the RX/TX GO_MODE line does; the TX banner carries both.
    GO mode has NO `stop-<dist>` level — the stop lives in the ARMED/header.
    """
    d = tmp_path / "logs" / "s{}-go{}".format(session, t0)
    d.mkdir(parents=True, exist_ok=True)
    lines = []
    if role == "rx":
        lines.append("# DISTRIBUTED_RX_MODE t0={} port=/dev/ttyUSB1 loop=1"
                     .format(_sid_iso(t0)))
    else:
        lines.append("# DISTRIBUTED_TX_MODE session={} t0={} port=/dev/ttyUSB2 "
                     "loop=1".format(session, _sid_iso(t0)))
    lines.append("# GO_MODE sync=cvm source=generate session={} t_ready={} "
                 "t0={} deadline_mono=1.0 armed_seq=7".format(
                     session, _sid_iso(t0), _sid_iso(t0)))
    return _write_log(str(d / "{}-log.csv".format(role)), lines)


def legacy_stop_log(tmp_path, session=LEGACY_SESSION, t0=SID_T0, dist="50m"):
    """logs/s<session>-t0<t0>/stop-<dist>/rx-log-t0<t0>-<session>.csv."""
    d = tmp_path / "logs" / "s{}-t0{}".format(session, t0) / ("stop-" + dist)
    d.mkdir(parents=True, exist_ok=True)
    return _write_log(
        str(d / "rx-log-t0{}-{}.csv".format(t0, session)),
        ["# DISTRIBUTED_RX_MODE t0={} port=/dev/ttyUSB1 loop=1"
         .format(_sid_iso(t0))])


class TestLaunchTagT0Extraction:
    """t0_from_filename() accepts BOTH launch tags: -t0<epoch> and -go<epoch>."""

    def test_go_session_dir_t0(self, tmp_path):
        rx = go_log(tmp_path, role="rx")
        assert range_check.t0_from_filename(rx) == SID_T0

    def test_go_basename_t0(self, tmp_path):
        p = _write_log(str(tmp_path / "tx-log-go{}.csv".format(SID_T0)),
                       ["# GO_MODE sync=cvm session={} t0=x".format(GO_SESSION)])
        assert range_check.t0_from_filename(p) == SID_T0

    def test_legacy_tag_in_basename_unchanged(self, tmp_path):
        rx = legacy_stop_log(tmp_path)
        assert range_check.t0_from_filename(rx) == SID_T0

    def test_legacy_tag_in_parent_dir_unchanged(self, tmp_path):
        d = tmp_path / "logs" / "s{}-t0{}".format(LEGACY_SESSION, SID_T0)
        p = _write_log(str(d / "rx-log.csv"), [])
        assert range_check.t0_from_filename(p) == SID_T0

    def test_untagged_plain_log_is_none(self):
        assert range_check.t0_from_filename("/somewhere/rx-log.csv") is None

    def test_go_dir_t0_sources_labelled(self, tmp_path):
        rx = go_log(tmp_path, role="rx")
        srcs = dict(range_check.t0_sources(rx))
        assert srcs
        assert set(srcs.values()) == {SID_T0}
        assert any("-go{}".format(SID_T0) in lbl for lbl in srcs), srcs


class TestSessionFromFilename:
    """session_from_filename(): the s<session>-{t0,go}<epoch> dir name."""

    def test_legacy_int_session_dir(self, tmp_path):
        rx = legacy_stop_log(tmp_path)
        assert range_check.session_from_filename(rx) == LEGACY_SESSION

    def test_go_nonce_session_dir(self, tmp_path):
        rx = go_log(tmp_path, role="rx")
        assert range_check.session_from_filename(rx) == GO_SESSION

    def test_no_session_dir_is_none(self, tmp_path):
        p = _write_log(str(tmp_path / "rx-log.csv"),
                       ["# DISTRIBUTED_RX_MODE t0=x loop=1"])
        assert range_check.session_from_filename(p) is None


class TestSessionFromHeader:
    """session_from_header(): the session=<sid> token of the launch banner."""

    def test_go_rx_banner_has_no_session_but_go_line_does(self, tmp_path):
        rx = go_log(tmp_path, role="rx")
        assert range_check.session_from_header(rx) == GO_SESSION

    def test_go_tx_distributed_banner_session(self, tmp_path):
        tx = go_log(tmp_path, role="tx")
        assert range_check.session_from_header(tx) == GO_SESSION

    def test_legacy_distributed_banner_with_session(self, tmp_path):
        p = _write_log(
            str(tmp_path / "tx-log.csv"),
            ["# DISTRIBUTED_TX_MODE session={} t0=2026-09-13T04:50:00 port=x "
             "loop=1".format(LEGACY_SESSION)])
        assert range_check.session_from_header(p) == LEGACY_SESSION

    def test_header_without_session_is_none(self, tmp_path):
        p = _write_log(str(tmp_path / "rx-log.csv"),
                       ["# DISTRIBUTED_RX_MODE t0=2026-09-13T04:50:00 loop=1"])
        assert range_check.session_from_header(p) is None

    def test_missing_file_is_none(self):
        assert range_check.session_from_header("/nonexistent/rx-log.csv") is None

    def test_session_sources_shape_and_labels(self, tmp_path):
        rx = go_log(tmp_path, role="rx")
        srcs = range_check.session_sources(rx)
        assert [s for _l, s in srcs] == [GO_SESSION, GO_SESSION]
        assert any("dir" in lbl for lbl, _s in srcs), srcs
        assert any("header" in lbl for lbl, _s in srcs), srcs


class TestSessionFirstJoin:
    """check_t0_match(): session_id first, legacy t0 rule as the fallback."""

    def test_session_mismatch_is_loud(self, tmp_path):
        rx = go_log(tmp_path, session=GO_SESSION, role="rx")
        tx = go_log(tmp_path, session=GO_OTHER_SESSION, role="tx")
        ok, msg = range_check.check_t0_match(rx, tx)
        assert not ok
        assert "SESSION MISMATCH" in msg
        assert GO_SESSION in msg
        assert GO_OTHER_SESSION in msg
        assert os.path.basename(rx) in msg and os.path.basename(tx) in msg
        assert "NOT from the same launch" in msg

    def test_session_mismatch_names_every_source_label(self, tmp_path):
        rx = go_log(tmp_path, session=GO_SESSION, role="rx")
        tx = go_log(tmp_path, session=GO_OTHER_SESSION, role="tx")
        _ok, msg = range_check.check_t0_match(rx, tx)
        for lbl, _s in (range_check.session_sources(rx)
                        + range_check.session_sources(tx)):
            assert lbl in msg, (lbl, msg)

    def test_same_session_and_t0_ok(self, tmp_path):
        rx = go_log(tmp_path, session=GO_SESSION, role="rx")
        tx = go_log(tmp_path, session=GO_SESSION, role="tx")
        ok, msg = range_check.check_t0_match(rx, tx)
        assert ok, msg
        assert str(SID_T0) in msg

    def test_same_session_but_t0_disagreement_still_loud(self, tmp_path):
        rx = go_log(tmp_path, session=GO_SESSION, t0=SID_T0, role="rx")
        tx = go_log(tmp_path, session=GO_SESSION, t0=SID_T0 + 60, role="tx")
        ok, msg = range_check.check_t0_match(rx, tx)
        assert not ok
        assert "T0 MISMATCH" in msg
        assert str(SID_T0) in msg and str(SID_T0 + 60) in msg

    def test_one_sided_session_falls_back_to_t0(self, tmp_path):
        # rx is GO-tagged; tx is a plain t0-tagged tx log (no session at all)
        rx = go_log(tmp_path, session=GO_SESSION, role="rx")
        tx = _write_log(
            str(tmp_path / "tx-log-t0{}.csv".format(SID_T0)),
            ["# DISTRIBUTED_TX_MODE t0={} port=x loop=1".format(_sid_iso(SID_T0))])
        ok, msg = range_check.check_t0_match(rx, tx)
        assert ok, msg

    def test_legacy_t0_only_pair_unchanged(self, tmp_path):
        # legacy manual/boundary pair: no session anywhere, only t0
        rx = _write_log(
            str(tmp_path / "rx-log-t0{}.csv".format(SID_T0)),
            ["# DISTRIBUTED_RX_MODE t0={} loop=1".format(_sid_iso(SID_T0))])
        tx = _write_log(
            str(tmp_path / "tx-log-t0{}.csv".format(SID_T0)),
            ["# DISTRIBUTED_TX_MODE t0={} loop=1".format(_sid_iso(SID_T0))])
        ok, msg = range_check.check_t0_match(rx, tx)
        assert ok, msg

    def test_legacy_t0_only_mismatch_unchanged(self, tmp_path):
        rx = _write_log(
            str(tmp_path / "rx-log-t0{}.csv".format(SID_T0)),
            ["# DISTRIBUTED_RX_MODE t0={} loop=1".format(_sid_iso(SID_T0))])
        tx = _write_log(
            str(tmp_path / "tx-log-t0{}.csv".format(SID_T0 + 300)),
            ["# DISTRIBUTED_TX_MODE t0={} loop=1"
             .format(_sid_iso(SID_T0 + 300))])
        ok, msg = range_check.check_t0_match(rx, tx)
        assert not ok
        assert "T0 MISMATCH" in msg


class TestFindRxLogsGoLayout:
    """find_rx_logs(): the GO layout is discoverable, legacy patterns kept."""

    def test_finds_go_layout_log(self, tmp_path):
        rx = go_log(tmp_path, session=GO_SESSION, role="rx")
        got = range_check.find_rx_logs("50m", GO_SESSION, [str(tmp_path)])
        assert [os.path.realpath(p) for p in got] == [os.path.realpath(rx)]

    def test_go_layout_found_for_any_dist(self, tmp_path):
        # the GO dir carries no stop-<dist> level, so it is a candidate for
        # every DIST of that session
        rx = go_log(tmp_path, session=GO_SESSION, role="rx")
        got = range_check.find_rx_logs("70km", GO_SESSION, [str(tmp_path)])
        assert os.path.realpath(rx) in [os.path.realpath(p) for p in got]

    def test_go_layout_found_without_explicit_session(self, tmp_path):
        rx = go_log(tmp_path, session=GO_SESSION, role="rx")
        got = range_check.find_rx_logs("50m", None, [str(tmp_path)])
        assert os.path.realpath(rx) in [os.path.realpath(p) for p in got]

    def test_session_tagged_beats_newer_foreign_log(self, tmp_path):
        mine = go_log(tmp_path, session=GO_SESSION, role="rx")
        foreign = legacy_stop_log(tmp_path, session=LEGACY_SESSION)
        os.utime(mine, (1000, 1000))
        os.utime(foreign, (2000, 2000))          # newer, but not our session
        got = range_check.find_rx_logs("50m", GO_SESSION, [str(tmp_path)])
        assert os.path.realpath(got[0]) == os.path.realpath(mine)

    def test_legacy_patterns_still_discovered(self, tmp_path):
        a = legacy_stop_log(tmp_path, session=LEGACY_SESSION)
        b = _write_log(str(tmp_path / "logs" / str(LEGACY_SESSION) / "stop-50m"
                           / "rx-log-s.csv"), [])
        c = _write_log(str(tmp_path / "logs" / "s9-t01" / "stop-50m"
                           / "rx-log-x.csv"), [])
        got = {os.path.realpath(p)
               for p in range_check.find_rx_logs("50m", LEGACY_SESSION,
                                                 [str(tmp_path)])}
        assert {os.path.realpath(a), os.path.realpath(b),
                os.path.realpath(c)} <= got

    def test_realpath_dedupe_holds_for_go_layout(self, tmp_path):
        rx = go_log(tmp_path, session=GO_SESSION, role="rx")
        got = range_check.find_rx_logs(
            "50m", GO_SESSION, [str(tmp_path), str(tmp_path)])
        assert len([p for p in got
                    if os.path.realpath(p) == os.path.realpath(rx)]) == 1


class TestNoRxLogMessage:
    """main(): the discovery-miss error names BOTH log-dir schemes."""

    def test_error_names_both_layouts(self, tmp_path):
        preset = write_preset(tmp_path)
        r = subprocess.run(
            [sys.executable, os.path.join(TOOLS_DIR, "range_check.py"),
             "--dist", "70km", "--configs", preset,
             "--repo-root", str(tmp_path)],
            capture_output=True, text=True, cwd=str(tmp_path))
        assert r.returncode == 2, r.stderr
        assert "s<session>-t0<t0>" in r.stderr, r.stderr
        assert "s<session>-go<t0>" in r.stderr, r.stderr
        assert "stop-70km" in r.stderr, r.stderr


class TestGoBoardSessionMatch:
    """GO sessions reach PKT rows as their u32 board projection.

    The bench firmware SESSION command is u32 (src/bench_cmd.c), so a GO
    session id (<%y%m%d%H%M><3-hex nonce>) can never be echoed on the wire:
    the board carries the 10-digit prefix. The analyzer must accept a PKT row
    whose session equals that projection, or a GO log reads as all-MISS.
    """

    def test_go_session_matches_its_board_projection(self):
        assert range_check._session_matches(2609130435, "2609130435a3f")

    def test_legacy_numeric_match_unchanged(self):
        assert range_check._session_matches(2609130435, "2609130435")
        assert not range_check._session_matches(2609130435, "2609130436")

    def test_other_projection_does_not_match(self):
        assert not range_check._session_matches(2609130436, "2609130435a3f")

    def test_full_go_session_still_matches_itself(self):
        assert range_check._session_matches("2609130435a3f", "2609130435a3f")

    def test_non_numeric_row_does_not_match_a_go_session(self):
        assert not range_check._session_matches("bench-a", "2609130435a3f")


# -----------------------------------------------------------------------
# GO-mode log/analysis consistency — cold-review blockers 1-3
#
# The RX is the session authority (full GO id: %y%m%d%H%M + 3-hex nonce) but
# the BOARD can only carry a u32 SESSION (src/bench_cmd.c), so every row a run
# writes is the projection (e80_bench_ctl.wire_session_id) while the banner /
# dir name keep the full id. These tests drive the tool's OWN writers and then
# the analysis tools over the resulting pair: a spelling or join-key mismatch
# must never come back as a confident wrong verdict.
#
# A GO session dir also has NO stop-<dist> level, so "which stop is this?"
# must be verified from the GO_MODE banner token (or the ARMED the RX left in
# the same dir) instead of being assumed.
# -----------------------------------------------------------------------

GO_U32 = 2609130435                  # board projection of GO_SESSION


def go_session_dir(tmp_path, session=GO_SESSION, t0=SID_T0):
    d = tmp_path / "logs" / "s{}-go{}".format(session, t0)
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


def go_banner_lines(session=GO_SESSION, stop="50m", t0=SID_T0,
                    stop_token=True):
    """The two launch-banner lines run_rx_mode writes at the top of a GO rx-log."""
    go = "# GO_MODE sync=cvm source=generate session={} ".format(session)
    if stop_token:
        go += "stop={} ".format(stop)
    go += ("t_ready={} t0={} deadline_mono=1.0 armed_seq=1".format(
        _sid_iso(t0), _sid_iso(t0)))
    return ["# DISTRIBUTED_RX_MODE t0={} port=/dev/ttyUSB1 loop=1".format(
        _sid_iso(t0)), go]


def write_go_preset(tmp_path, n_cfgs=2, n_pkts=10, name="stop-50m.json"):
    """Preset for the GO fixtures — MUST agree with go_rx_log/go_tx_log shape.

    go_rx_log/go_tx_log log 2 configs x 10 pkts by default, so the preset has
    to describe the same 2 configs: write_preset()'s 3-config default would
    (correctly) report c2 as MISS — a config of the preset that was never
    received is a MISS/GAPS verdict, not a logging gap — and exit 1. Pairing
    the fixtures here keeps the GO analysis tests about the session/stop join
    rather than about a preset/log shape mismatch.
    """
    return write_preset(tmp_path,
                        preset=make_preset_dict(n_cfgs=n_cfgs, n_pkts=n_pkts),
                        name=name)


def go_rx_log(tmp_path, session=GO_SESSION, stop="50m", t0=SID_T0,
              n_cfgs=2, n_pkts=10, stop_token=True, armed_stop=None):
    """A GO rx-log written by the TOOL'S OWN writers.

    PKT/STAT rows carry ctl.wire_session_id(session) — the u32 the firmware
    SESSION command can carry — while the dir name and the banner keep the full
    RX-authoritative id. armed_stop also writes the ARMED artefact the RX
    leaves next to its log (the pre-/alternative stop source).
    """
    d = go_session_dir(tmp_path, session, t0)
    path = os.path.join(d, "rx-log.csv")
    _write_log(path, go_banner_lines(session, stop, t0, stop_token))
    wire = ctl.wire_session_id(session)
    log = ctl.HarmonizedRxLogWriter(path)
    for c in range(n_cfgs):
        for s in range(n_pkts):
            log.pkt_line({
                "session_id": wire, "config_id": c, "replicate": 1, "seq": s,
                "ts_ms": 1000 + s, "rssi_dbm": -80.5, "snr_db": 9.0,
                "crc_ok": 1, "bit_err": 0, "bytes_bad": 0,
                "freq_hz": 869525000, "mod": "flrc", "sf": 0, "bw_khz": 1200,
                "cr": 1, "power_dbm": 22, "pkt_size": 255, "gps_fix": 0,
                "gps_lat": 0.0, "gps_lon": 0.0, "gps_alt": 0.0,
                "gps_sats": 0, "gps_hdop": 0.0,
            })
        log.stat_line("RX", {"sent": n_pkts + 2, "sent_ok": n_pkts + 2,
                             "recv": n_pkts, "crc_err": 0, "per_pct": 0.0,
                             "elapsed_s": 1.0, "kbps": 42.5, "rssi": -80.5,
                             "snr": 9.0, "drops": 0, "gap_us": 1000},
                      wire, c, 1)
    if armed_stop is not None:
        with open(os.path.join(d, "armed.json"), "w") as f:
            json.dump({"type": "ARMED", "session_id": session,
                       "stop": armed_stop, "t_ready_utc": t0,
                       "preset_hash": "deadbeefcafe", "seq": 1}, f)
    return path


def go_tx_log(tmp_path, session=GO_SESSION, stop="50m", t0=SID_T0,
              n_cfgs=2, n_pkts=10, wire_session=True):
    """A GO tx-log written by HarmonizedTxLogWriter (one STAT row per config).

    wire_session=False reproduces the pre-fix spelling where the TX STAT rows
    carried the full GO id — the other half of the join-key mismatch.
    """
    d = go_session_dir(tmp_path, session, t0)
    path = os.path.join(d, "tx-log.csv")
    sid = ctl.wire_session_id(session) if wire_session else session
    log = ctl.HarmonizedTxLogWriter(path, session_id=sid)
    log.comment("DISTRIBUTED_TX_MODE session={} t0={} port=/dev/ttyUSB2 "
                "loop=1".format(session, _sid_iso(t0)))
    log.comment("GO_MODE sync=cvm source=file session={} stop={} t_ready={} "
                "t0={} deadline_mono=1.0 armed_seq=1".format(
                    session, stop, _sid_iso(t0), _sid_iso(t0)))
    for c in range(n_cfgs):
        log.stat_line(c, {"sent": n_pkts + 2, "sent_ok": n_pkts + 2,
                          "recv": 0, "crc_err": 0, "per_pct": 0.0,
                          "gap_us": 1000, "label": "CFG{}".format(c),
                          "n_pkts": n_pkts, "plen": 255}, replicate=1)
    return path


def run_range_check(tmp_path, dist="50m", session=None, extra=()):
    """Run range_check.py as a subprocess with cwd = tmp_path (a search root)."""
    cmd = [sys.executable, os.path.join(TOOLS_DIR, "range_check.py"),
           "--dist", dist, "--repo-root", str(tmp_path)]
    if session:
        cmd += ["--session", session]
    cmd += list(extra)
    return subprocess.run(cmd, capture_output=True, text=True,
                          cwd=str(tmp_path))


class TestGoSessionMatchIsSymmetric:
    """_session_matches(): either side may be the u32 board projection.

    The auto-session path can hand over the u32 (max PKT session) while the
    banner/dir carry the full GO id, so the comparison must project BOTH
    sides — it used to project only the expected side and reported a false
    LOGGING GAP on the tool's primary documented path.
    """

    def test_u32_expected_matches_a_full_go_row(self):
        assert range_check._session_matches(GO_U32, GO_SESSION)

    def test_full_go_expected_matches_a_u32_row(self):
        assert range_check._session_matches(GO_SESSION, GO_U32)

    def test_full_go_row_still_matches_itself(self):
        assert range_check._session_matches(GO_SESSION, GO_SESSION)

    def test_other_projection_still_refused(self):
        assert not range_check._session_matches(str(GO_U32 + 1), GO_SESSION)

    def test_non_numeric_row_still_refused(self):
        assert not range_check._session_matches("bench-a", GO_SESSION)


class TestGoLogAnalysis:
    """range_check over the GO log pair the tool's own writers produce."""

    def test_explicit_rx_log_without_session_is_not_a_logging_gap(self, tmp_path):
        # the reviewer's repro of blocker 1: `--dist 50m --rx-log <GO rx-log>`
        # with no --session printed "LOGGING GAP (0 STAT rows ...)" and exit 1.
        write_go_preset(tmp_path)
        rx = go_rx_log(tmp_path)
        r = run_range_check(tmp_path, extra=["--rx-log", rx])
        assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
        assert "LOGGING GAP" not in r.stdout, r.stdout
        assert "PASS" in r.stdout, r.stdout

    def test_auto_session_is_the_launch_authority_not_the_pkt_rows(self, tmp_path):
        write_go_preset(tmp_path)
        rx = go_rx_log(tmp_path)
        r = run_range_check(tmp_path, extra=["--rx-log", rx])
        assert "session: {} (auto".format(GO_SESSION) in r.stdout, r.stdout
        # the PKT rows only ever carry the u32 projection — that is why the
        # auto-session must prefer the launch dir / banner token.
        _pkts, sessions = range_check.parse_rx_log(rx)
        assert sessions == {GO_U32}, sessions

    def test_u32_session_form_matches_the_same_log(self, tmp_path):
        # the obvious guess from the PKT rows must work too (the STAT rows
        # carry the same wire spelling now).
        write_go_preset(tmp_path)
        rx = go_rx_log(tmp_path)
        r = run_range_check(tmp_path, session=str(GO_U32),
                            extra=["--rx-log", rx])
        assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
        assert "PASS" in r.stdout, r.stdout


class TestGoMergeJoin:
    """merge_csvs over a GO tx/rx pair: a perfect pass merges to 0 lost."""

    def _merge_cli(self, tmp_path, tx, rx):
        out = tmp_path / "out"
        out.mkdir(exist_ok=True)
        r = subprocess.run(
            [sys.executable, os.path.join(TOOLS_DIR, "merge_csvs.py"),
             "--tx", tx, "--rx", rx, "--out-dir", str(out)],
            capture_output=True, text=True, cwd=str(tmp_path))
        return r, out

    def test_perfect_go_pass_merges_to_zero_lost(self, tmp_path):
        # the reviewer's repro of blocker 2: a perfect GO pass used to merge to
        # "0/100 received, 100 lost, PER=100.0%" + 100 foreign packets.
        tx = go_tx_log(tmp_path)
        rx = go_rx_log(tmp_path)
        r, out = self._merge_cli(tmp_path, tx, rx)
        assert r.returncode == 0, r.stderr
        assert "20/20 received, 0 lost" in r.stdout, r.stdout
        assert "PER=0.0%" in r.stdout, r.stdout
        report = (out / "combined-range-report.md").read_text()
        assert "| Foreign packets | 0 |" in report, report

    def test_tx_log_with_the_full_go_id_still_joins(self, tmp_path):
        # the two logs of one GO run may spell the session differently (older
        # TX logs carry the full id): normalising BOTH sides keeps the
        # (session, config) join intact rather than reporting 100% loss.
        tx = go_tx_log(tmp_path, wire_session=False)
        rx = go_rx_log(tmp_path)
        out = tmp_path / "out"
        out.mkdir()
        combined = merge_csvs.merge_csvs(tx, rx, str(out))
        assert [row for row in combined if row["status"] == "lost"] == []
        assert len(combined) == 20
        assert "| Foreign packets | 0 |" in (
            out / "combined-range-report.md").read_text()

    def test_writers_use_one_wire_spelling(self):
        assert ctl.wire_session_id(GO_SESSION) == GO_U32
        assert ctl.wire_session_id(str(GO_U32)) == GO_U32
        assert ctl.wire_session_id(GO_SESSION) == ctl.board_session_id(GO_SESSION)


class TestGoStopGuard:
    """A GO session dir has no stop-<dist> level: the stop must be verified.

    Otherwise a 50m GO log is a discovery candidate for 70km and the tool
    printed a confident PASS for a stop that was never run (verdict-changing
    regression vs the legacy layout, which exits 2 with no stop dir).
    """

    def test_banner_stop_token_is_read(self, tmp_path):
        rx = go_rx_log(tmp_path, stop="50m")
        assert range_check.go_stop_from_header(rx) == "50m"
        assert [s for _lbl, s in range_check.go_stop_sources(rx)] == ["50m"]

    def test_armed_json_is_the_fallback_source(self, tmp_path):
        rx = go_rx_log(tmp_path, stop="50m", stop_token=False,
                       armed_stop="50m")
        assert range_check.go_stop_from_header(rx) is None
        assert range_check.go_stop_from_armed(rx) == "50m"
        assert [s for _lbl, s in range_check.go_stop_sources(rx)] == ["50m"]

    def test_other_stop_is_refused_loudly(self, tmp_path):
        write_preset(tmp_path, preset=make_preset_dict(n_cfgs=2, n_pkts=10),
                     name="stop-70km.json")
        rx = go_rx_log(tmp_path, stop="50m")
        r = run_range_check(tmp_path, dist="70km", session=GO_SESSION,
                            extra=["--rx-log", rx])
        assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
        assert "PASS" not in r.stdout, r.stdout
        assert "50m" in r.stderr and "70km" in r.stderr, r.stderr

    def test_armed_json_alone_refuses_a_mismatched_stop(self, tmp_path):
        write_preset(tmp_path, preset=make_preset_dict(n_cfgs=2, n_pkts=10),
                     name="stop-70km.json")
        rx = go_rx_log(tmp_path, stop="50m", stop_token=False,
                       armed_stop="50m")
        r = run_range_check(tmp_path, dist="70km", session=GO_SESSION,
                            extra=["--rx-log", rx])
        assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)

    def test_matching_stop_is_still_analysed(self, tmp_path):
        write_go_preset(tmp_path)
        rx = go_rx_log(tmp_path, stop="50m")
        r = run_range_check(tmp_path, dist="50m", extra=["--rx-log", rx])
        assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
        assert "PASS" in r.stdout, r.stdout

    def test_discovery_drops_a_go_log_of_another_stop(self, tmp_path):
        other = go_rx_log(tmp_path, session=GO_OTHER_SESSION, stop="70km",
                          t0=SID_T0 + 300)
        mine = go_rx_log(tmp_path, session=GO_SESSION, stop="50m")
        got = [os.path.realpath(p) for p in
               range_check.find_rx_logs("70km", None, [str(tmp_path)])]
        assert os.path.realpath(mine) not in got
        assert os.path.realpath(other) in got

    def test_discovery_keeps_a_stop_less_go_log(self, tmp_path):
        # a log with no stop source anywhere cannot be classified: keep it a
        # candidate (warn), never silently drop the only log there is.
        rx = go_rx_log(tmp_path, stop_token=False)
        got = [os.path.realpath(p) for p in
               range_check.find_rx_logs("70km", None, [str(tmp_path)])]
        assert os.path.realpath(rx) in got

    def test_stop_sentinel_is_not_a_claimed_stop(self, tmp_path):
        # round-2 review repro: --stop defaults to the "?" sentinel, so a
        # documented-default GO launch writes stop=? into BOTH stop sources.
        # The guard read that as a claimed stop named "?" and refused the
        # healthy log with exit 2 — a pass that could never be scored.
        write_go_preset(tmp_path)
        rx = go_rx_log(tmp_path, stop="?")
        assert range_check.go_stop_from_header(rx) is None
        assert range_check.go_stop_from_armed(rx) is None
        assert range_check.go_stop_sources(rx) == []
        ok, msg = range_check.check_go_stop_match(rx, "50m")
        assert ok, msg
        assert "cannot verify" in msg, msg
        r = run_range_check(tmp_path, dist="50m", extra=["--rx-log", rx])
        assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
        assert "PASS" in r.stdout, r.stdout

    def test_stop_sentinel_in_armed_is_not_a_claimed_stop(self, tmp_path):
        # same sentinel, other source: the banner carries no stop token and
        # armed.json carries "?" — still "no stop source", not "stop ?".
        write_go_preset(tmp_path)
        rx = go_rx_log(tmp_path, stop_token=False, armed_stop="?")
        assert range_check.go_stop_from_header(rx) is None
        assert range_check.go_stop_from_armed(rx) is None
        assert range_check.go_stop_sources(rx) == []
        r = run_range_check(tmp_path, dist="50m", extra=["--rx-log", rx])
        assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
        assert "PASS" in r.stdout, r.stdout

    def test_empty_stop_token_is_not_a_claimed_stop(self, tmp_path):
        # "" is the other spelling of "not recorded" (the ARMED/banner token
        # is written from an optional CLI value).
        write_go_preset(tmp_path)
        rx = go_rx_log(tmp_path, stop="")
        assert range_check.go_stop_from_header(rx) is None
        assert range_check.go_stop_sources(rx) == []
        r = run_range_check(tmp_path, dist="50m", extra=["--rx-log", rx])
        assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
        assert "PASS" in r.stdout, r.stdout

    def test_sentinel_armed_does_not_mask_a_real_banner_stop(self, tmp_path):
        # the fix must stay narrow: a REAL stop token still counts even when
        # the other source is the sentinel, or "?" would excuse a wrong stop.
        write_preset(tmp_path, preset=make_preset_dict(n_cfgs=2, n_pkts=10),
                     name="stop-70km.json")
        rx = go_rx_log(tmp_path, stop="50m", armed_stop="?")
        assert range_check.go_stop_from_header(rx) == "50m"
        assert [s for _lbl, s in range_check.go_stop_sources(rx)] == ["50m"]
        r = run_range_check(tmp_path, dist="70km", session=GO_SESSION,
                            extra=["--rx-log", rx])
        assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
        assert "PASS" not in r.stdout, r.stdout


if __name__ == "__main__":
    unittest.main()
