#!/usr/bin/env python3
"""Host unit tests for the RFA-1b matrix runner's pure logic.

The bench itself needs hardware, but the parts that decide WHAT was measured
must not be trusted on inspection: the per-cell filtering (the RX board keeps
receiving and the TX sequence counter is persistent, so a whole-capture count
would mix bursts) and the ops builders (command syntax the firmware accepts).

Run: cd tools && python3 -m pytest test_rfa1b_pram_matrix.py -v
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import rfa1b_pram_matrix as m  # noqa: E402


PKT = ("PKT,0,{cfg},0,{seq},{ts},-21,0,{crc},0,0,869850000,FLRC,8,125,1,22,128,"
       "0,0,0,0,0,0,1234")


def test_parse_lines_filters_by_config_id():
    cfg1 = [PKT.format(cfg=1, seq=i, ts=100 + i, crc=1) for i in range(200)]
    cfg2 = [PKT.format(cfg=2, seq=500 + i, ts=900 + i, crc=0) for i in range(3)]
    lines = ["OK MOD flrc br=260000 pa=10"] + cfg2 + cfg1 + [
        "STAT role=RX sent=0 sent_ok=0 rx=200 crc_err=0 per_x1e6=0 elapsed_s=3.0 kbps=40"]

    got = m.parse_lines(lines, config_id=1)
    assert len(got["pkts"]) == 200
    assert got["pkts_other_config"] == 3          # the neighbouring cell's tail
    assert all(p["crc_ok"] == 1 for p in got["pkts"])
    assert got["stat"]["rx"] == "200"

    got2 = m.parse_lines(lines, config_id=2)
    assert len(got2["pkts"]) == 3
    assert all(p["crc_ok"] == 0 for p in got2["pkts"])


def test_parse_lines_without_filter_sees_everything():
    lines = [PKT.format(cfg=1, seq=1, ts=1, crc=1), PKT.format(cfg=2, seq=2, ts=2, crc=0)]
    got = m.parse_lines(lines)
    assert len(got["pkts"]) == 2
    assert got["pkts_other_config"] == 0


def test_parse_lines_survives_truncated_and_garbage_lines():
    lines = ["PKT,0,1", "PKT,garbage,not,numbers", PKT.format(cfg=1, seq=7, ts=7, crc=1),
             "", "CONFIG_START,1,0,4242", "ID E80BENCH v1.2 fw=abc patch=0"]
    got = m.parse_lines(lines, config_id=1)
    assert len(got["pkts"]) == 1
    assert got["config_markers"] == ["CONFIG_START,1,0,4242"]
    assert got["id"]["fw"] == "abc"
    assert got["id"]["patch"] == "0"


def test_pre_ops_marks_the_arm_and_the_cell():
    ops = m.pre_ops(260, "TX", "on", 4)
    cmds = [o["cmd"] for o in ops]
    assert cmds[0].startswith("PATCH ON")
    assert "CONFIG 4 0" in cmds
    assert "MOD flrc 260 10" in cmds
    assert f"FREQ {m.FREQ_HZ}" in cmds
    assert "POWER MODE OUTDOOR 2026" in cmds
    assert f"PA {m.PA_DBM}" in cmds
    assert "ROLE TX" in cmds
    # Baseline arm (fw without PATCH) must not send PATCH at all.
    assert all("PATCH" not in c for c in [o["cmd"] for o in m.pre_ops(260, "TX", "none", 1)])


def test_rx_ops_expects_the_rx_start_reply_and_listens_after_it():
    ops = m.rx_ops(260, "on", 128)
    assert ops[0]["cmd"].startswith("START N=200 LEN=128 GAP=")
    # The RX branch answers "OK RX ARMED len=<n>"; expecting "OK START" made the
    # agent retry START three times, each retry re-resetting the RX stats.
    assert ops[0]["expect"] == "OK RX ARMED"
    assert ops[0]["retries"] == 1
    assert ops[1]["op"] == "listen"
    assert ops[1]["mark"].startswith("LISTENING")
    # The listen window must outlast burst + the host-side config latency.
    assert ops[1]["seconds"] > 25.0
    assert ops[2]["cmd"] == "STAT?"


def test_tx_burst_ops_arm_and_start_in_one_write():
    ops = m.tx_burst_ops(64)
    assert "\n" in ops[0]["cmd"]           # ONE serial write: IWDG window
    assert ops[0]["cmd"].startswith("ARM TX\nSTART N=200 LEN=64 GAP=")
    assert ops[1]["op"] == "wait"
    assert ops[1]["expect"] == "TX DONE"


def test_config_ids_are_unique_per_cell_and_never_zero():
    ids = list(range(1, len(m.CELLS) + 1))
    assert len(set(ids)) == len(m.CELLS) == 6
    assert 0 not in ids                    # 0 is the firmware's default tag


@pytest.mark.parametrize("cell", m.CELLS)
def test_cell_matrix_matches_the_card(cell):
    br, ln = cell
    assert br in (260, 650)
    assert ln in (64, 128, 255)


def test_tx_rate_detour_prepends_a_lora_hop_and_reapplies_the_role():
    """RFA-1c pre-flash control: MOD alone only rewrites cfg on a TX board, so
    the LoRa hop is worthless unless ROLE TX follows it — that is the command
    that calls apply_cfg() and re-runs the reset+calibrate bring-up."""
    ops = m.pre_ops(650, "TX", "none", 3, detour=True)
    cmds = [o["cmd"] for o in ops]
    assert cmds[0] == f"MOD loRa {m.DETOUR_SF} {m.DETOUR_BW_KHZ}"
    assert cmds[1] == "ROLE TX"
    assert cmds.index("MOD flrc 650 10") > 1        # the cell's real rate, after the hop
    assert "CONFIG 3 0" in cmds and cmds[-1] == "ROLE TX"


def test_rate_detour_is_off_by_default_and_role_follows_the_arm():
    assert all("loRa" not in o["cmd"] for o in m.pre_ops(650, "TX", "none", 1))
    # the RX arm needs the same hop: MOD re-arms RX through radio_rearm_rx, and
    # the ROLE re-issue makes the two arms byte-identical.
    rxc = [o["cmd"] for o in m.pre_ops(650, "RX", "none", 1, detour=True)]
    assert rxc[0] == f"MOD loRa {m.DETOUR_SF} {m.DETOUR_BW_KHZ}"
    assert rxc[1] == "ROLE RX"


def test_remote_listen_marker_carries_host_prefix():
    """Regression (2026-10-14): run_ops returned the marker path WITHOUT the
    ssh host prefix, so wait_mark() stat()ed a local path for a remote board,
    never saw the marker, burned the whole timeout, and the TX burst fired into
    a receiver that had not opened its window -> phantom "0 packets" cells.
    Any non-waiting run must hand back a host-qualified handle."""
    from unittest import mock

    board_host = m.Board("RX", "x240", "/dev/ttyUSB0")
    board_local = m.Board("RX", None, "/dev/ttyUSB0")

    # the real invocation is only touched through a Popen we stub out
    with mock.patch.object(m.subprocess, "Popen") as popen:
        popen.return_value = mock.Mock(returncode=0)
        remote = m.run_ops(board_host, [], "/tmp/out.json", "rx_tag", wait=False)
        local = m.run_ops(board_local, [], "/tmp/out.json", "rx_tag", wait=False)

    assert remote["mark"] == "x240:/tmp/rfa1b_rx_tag.mark", remote["mark"]
    assert ":" not in local["mark"], local["mark"]
    # and the prefixed handle must be what wait_mark() splits on
    assert m.wait_mark("x240:/tmp/nonexistent.mark", 0.01) is False


# ---------------------------------------------------------------- RFA-1c detour
def test_detour_defaults_on_while_the_fix_is_unflashable():
    """Regression (2026-10-14): the boards still run pre-fix fw 5fa7912 and no
    write path to the MCU exists (BOOT0 tied to GND, SWD never linked), so a
    260->650 cell would measure the BUG instead of the radio. The detour must
    therefore be ON whenever nothing says otherwise."""
    from unittest import mock
    with mock.patch.dict(os.environ, {}, clear=True):
        assert m.detour_enabled("RFA1C_TX_RATE_DETOUR", None) is True
        assert m.detour_enabled("RFA1C_RX_RATE_DETOUR", None) is True


def test_explicit_flag_beats_the_environment():
    """--no-detour is the post-flash escape hatch: once the RFA-1c firmware runs
    on the boards it re-calibrates by itself and a detour would be wrong."""
    from unittest import mock
    with mock.patch.dict(os.environ, {"RFA1C_TX_RATE_DETOUR": "1"}, clear=True):
        assert m.detour_enabled("RFA1C_TX_RATE_DETOUR", False) is False
    with mock.patch.dict(os.environ, {"RFA1C_TX_RATE_DETOUR": "0"}, clear=True):
        assert m.detour_enabled("RFA1C_TX_RATE_DETOUR", True) is True


def test_environment_can_switch_one_arm_off_independently():
    """The 5 pre-flash matrices showed the deaf end is the RECEIVER (TX-only
    detour = 2 bad cells, RX-only detour = 0). Both arms must stay switchable
    apart so that finding can be re-checked on demand."""
    from unittest import mock
    with mock.patch.dict(os.environ, {"RFA1C_TX_RATE_DETOUR": "0"}, clear=True):
        assert m.detour_enabled("RFA1C_TX_RATE_DETOUR", None) is False
        assert m.detour_enabled("RFA1C_RX_RATE_DETOUR", None) is True


def test_detour_prefixes_a_lora_hop_before_the_flrc_rate():
    """The hop is what forces the bring-up; it must come BEFORE the FLRC MOD so
    the rate change lands on an already-moved modem."""
    ops = m.pre_ops(650, "TX", "none", 1, detour=True)
    cmds = [o["cmd"] for o in ops]
    lora_i = next(i for i, c in enumerate(cmds) if c.startswith("MOD loRa"))
    flrc_i = next(i for i, c in enumerate(cmds) if c.startswith("MOD flrc 650"))
    assert lora_i < flrc_i, cmds
    assert "OK ROLE TX" in [o.get("expect") for o in ops[:lora_i + 2]], cmds


def test_no_detour_keeps_the_original_short_sequence():
    """Without the detour nothing extra may be injected — the pre-flash control
    A/B only means something if the untouched path stays untouched."""
    plain = [o["cmd"] for o in m.pre_ops(650, "TX", "none", 1, detour=False)]
    assert not any(c.startswith("MOD loRa") for c in plain), plain
    assert plain.count("MOD flrc 650 10") == 1, plain
