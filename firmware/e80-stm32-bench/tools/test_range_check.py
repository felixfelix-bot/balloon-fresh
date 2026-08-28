#!/usr/bin/env python3
"""test_range_check.py — tests for post-stop rx-log coverage verdict + re-send.

Run:  python3 -m pytest tools/test_range_check.py -v

Covers the range-check decision procedure (approved design):
  - Per cfg i: rows with session==SESSION && config==i.
  - counted = PKT rows with replicate >= 3 (first 2 replicates are warmups,
    never counted).
  - MISS  = no counted rows; THIN = counted < n_pkts; else OK.
  - PASS iff all OK (exit 0); GAPS exit 1 + resend preset with ONLY the
    missing+thin cfgs.
  - Zero STAT rows for the session = LOGGING GAP verdict (logger problem,
    no resend file). STAT rows with rx=0 are DATA (RF death), not a gap.

Fixtures are synthetic rx-log text built with the SAME formatters the rx
logger uses (e80_bench_ctl.format_pkt_line / format_stat_line), so the
tests track the real on-wire format. No hardware, no serial.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import pytest

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
E80_DIR = os.path.dirname(TOOLS_DIR)
REPO_ROOT = os.path.abspath(os.path.join(E80_DIR, "..", ".."))

sys.path.insert(0, TOOLS_DIR)

from e80_bench_ctl import format_pkt_line, format_stat_line, load_config_preset  # noqa: E402

SESSION = 2608281130
OTHER_SESSION = 9912312359


# -----------------------------------------------------------------------
# Fixture builders (mirror the real rx-log format)
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
# Verdicts + exit codes
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
        lines = clean_log(n_cfgs=3)
        # drop cfg1's replicate-3 rows entirely (keep its warmups)
        lines = [ln for ln in lines
                 if not (ln.startswith("PKT,") and ",1,3," in ln)
                 and not (ln.startswith("STAT,") and "config=1,replicate=3" in ln)]
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

    def test_multi_replicate_counts_sum(self, tmp_path):
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
# Resend preset output
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
# STAT row parsing (bracket field contains a comma)
# -----------------------------------------------------------------------

class TestStatParsing:
    def test_parse_stat_row_handles_bracket_comma(self):
        import range_check
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
        import range_check
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


# -----------------------------------------------------------------------
# Makefile wiring: range-check target + relative T0=+NN
# -----------------------------------------------------------------------

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
