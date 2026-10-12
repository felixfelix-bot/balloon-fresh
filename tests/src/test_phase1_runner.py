#!/usr/bin/env python3
"""Unit tests for the Phase 1 test runner — pure simulation, no hardware.

Covers protocol parsing, statistics computation, the mock serial backend,
end-to-end mode orchestration (single/dual TX, dual RX), and the CLI.

Run:
    python -m pytest tests/src/test_phase1_runner.py -v
    python -m pytest tests/src/test_phase1_runner.py -v -m simulate
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RUNNER_PATH = REPO_ROOT / "tests" / "phase1_test_runner.py"


def _load_runner():
    """Load tests/phase1_test_runner.py as a module (hyphen-free name)."""
    spec = importlib.util.spec_from_file_location("phase1_test_runner", RUNNER_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["phase1_test_runner"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def runner():
    return _load_runner()


# --------------------------------------------------------------------------- #
# Protocol parsing
# --------------------------------------------------------------------------- #
class TestParsing:
    @pytest.mark.simulate
    def test_canonical_9_field(self, runner):
        pkt = runner.parse_packet_line("1,42,-75.0,8.0,10,60,30,40,140")
        assert pkt is not None
        assert pkt.index == 1 and pkt.seq == 42
        assert pkt.rssi == -75.0 and pkt.snr == 8.0
        assert pkt.total_us == 140

    @pytest.mark.simulate
    def test_rp2040_timing_only(self, runner):
        pkt = runner.parse_packet_line("3,100,12,61,31,41,145")
        assert pkt is not None
        assert pkt.seq == 100
        assert pkt.rssi is None and pkt.snr is None
        assert pkt.read_us == 61 and pkt.total_us == 145

    @pytest.mark.simulate
    def test_bench_wrapped_packet(self, runner):
        line = "I (1234) BENCH: PKT,5,200,-70.5,9.0,11,62,32,42,147"
        pkt = runner.parse_packet_line(line)
        assert pkt is not None
        assert pkt.seq == 200 and pkt.rssi == -70.5

    @pytest.mark.simulate
    def test_non_packet_lines_rejected(self, runner):
        assert runner.parse_packet_line("") is None
        assert runner.parse_packet_line("pkt,seq,rssi,snr,...") is None
        assert runner.parse_packet_line("RESULT,500,498,2,0,2600,140,141,143") is None
        assert runner.parse_packet_line("=== footer ===") is None
        assert runner.parse_packet_line("garbage,not,a,pkt") is None
        assert runner.parse_packet_line("x,2,3") is None  # non-numeric index

    @pytest.mark.simulate
    def test_result_positional(self, runner):
        r = runner.parse_result_line("RESULT,500,498,2,0,2600.0,140,141.2,143")
        assert r is not None
        assert r["received"] == 500 and r["unique"] == 498
        assert r["duplicates"] == 2 and r["throughput_kbps"] == 2600.0

    @pytest.mark.simulate
    def test_result_key_value(self, runner):
        r = runner.parse_result_line("RESULT,received=100,loss_pct=2.5")
        assert r is not None
        assert r["received"] == 100.0 and r["loss_pct"] == 2.5

    @pytest.mark.simulate
    def test_result_bench_wrapped(self, runner):
        r = runner.parse_result_line("I (5) BENCH: RESULT,100,99,1,0,2600,140,141,143")
        assert r is not None and r["unique"] == 99

    @pytest.mark.simulate
    def test_result_garbage(self, runner):
        assert runner.parse_result_line("RESULT,garbage") is None
        assert runner.parse_result_line("not a result") is None


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #
class TestStats:
    def _pkts(self, runner, seqs, rssi=None, total=None):
        out = []
        for i, s in enumerate(seqs):
            out.append(runner.PacketRecord(
                index=i + 1, seq=s,
                rssi=rssi[i] if rssi else None,
                total_us=total[i] if total else None))
        return out

    @pytest.mark.simulate
    def test_packet_loss(self, runner):
        # 480 unique of 500 expected => 4% loss.
        pkts = self._pkts(runner, list(range(480)))
        s = runner.compute_stats(pkts, expected_packets=500)
        assert s.unique_seqs == 480
        assert s.packet_loss_pct == pytest.approx(4.0)
        assert s.duplicates == 0 and s.out_of_order == 0

    @pytest.mark.simulate
    def test_duplicates_and_out_of_order(self, runner):
        # seqs: 0,1,2,2,3,1 — one duplicate, one out-of-order.
        pkts = self._pkts(runner, [0, 1, 2, 2, 3, 1])
        s = runner.compute_stats(pkts, expected_packets=4)
        assert s.packets_received == 6
        assert s.duplicates == 2  # two repeats of already-seen seqs
        assert s.out_of_order >= 1
        assert s.packet_loss_pct == 0.0  # all 4 unique present

    @pytest.mark.simulate
    def test_rssi_stats(self, runner):
        pkts = self._pkts(runner, range(10),
                          rssi=[-70, -72, -71, -69, -73, -70, -71, -72, -70, -71])
        s = runner.compute_stats(pkts, expected_packets=10)
        assert s.rssi_count == 10
        assert s.rssi_min == -73.0 and s.rssi_max == -69.0
        assert s.rssi_avg == pytest.approx(-70.9, abs=0.1)
        assert s.rssi_p95 is not None and s.rssi_min <= s.rssi_p95 <= s.rssi_max

    @pytest.mark.simulate
    def test_no_rssi_yields_none(self, runner):
        pkts = self._pkts(runner, range(100))
        s = runner.compute_stats(pkts, expected_packets=100)
        assert s.rssi_min is None and s.rssi_avg is None and s.rssi_count == 0
        assert s.packet_loss_pct == 0.0

    @pytest.mark.simulate
    def test_timing_stats(self, runner):
        pkts = self._pkts(runner, range(5), total=[140, 145, 141, 200, 143])
        s = runner.compute_stats(pkts, expected_packets=5)
        assert s.total_min_us == 140 and s.total_max_us == 200
        assert s.total_avg_us == pytest.approx((140 + 145 + 141 + 200 + 143) / 5)

    @pytest.mark.simulate
    def test_empty_packets(self, runner):
        s = runner.compute_stats([], expected_packets=500)
        assert s.packets_received == 0
        assert s.packet_loss_pct == 100.0


# --------------------------------------------------------------------------- #
# Mock backend
# --------------------------------------------------------------------------- #
class TestMockBackend:
    @pytest.mark.simulate
    def test_boot_then_packets_on_start(self, runner):
        be = runner.make_mock_nodes()["RP2040-A"]
        # Boot lines come out first.
        assert be.readline(1.0).strip() == b"BOOT"
        assert be.readline(1.0).strip() == b"READY"
        # Nothing pending until START is written.
        assert be.readline(0.05) == b""
        # Send START -> packets + RESULT stream.
        be.write(b"S\n")
        lines = []
        while True:
            raw = be.readline(0.5)
            if not raw:
                break
            lines.append(raw.decode().strip())
        assert lines[0] == "START"
        assert lines[1].startswith("pkt,")
        assert any(ln.startswith("RESULT,") for ln in lines)
        # 20 packets between header and RESULT.
        pkt_lines = [ln for ln in lines if runner.parse_packet_line(ln)]
        assert len(pkt_lines) == 20


# --------------------------------------------------------------------------- #
# End-to-end orchestration (mock serial, no hardware)
# --------------------------------------------------------------------------- #
class _MockOrchestrationMixin:
    """Mock-backend helpers shared by the orchestration tests and the
    regression locks below (a plain mixin, so pytest does not collect it)."""

    def _runner_with_mocks(self, runner, rx_script, tx_count=1):
        """Build a Phase1Runner wired to mock nodes emitting rx_script.

        Every node is given the same ``rx_on_write`` emitter, mirroring
        :func:`phase1_test_runner.make_mock_nodes`.  Which node is RX varies
        across the matrix (1D/1E use an ESP32 as RX, 1F uses two receivers), so
        the emitter must be installed on *all* nodes: otherwise a mode whose RX
        node has a no-op ``on_write`` silently collects zero packets and the
        dual-RX merge (mode 1F) is never actually exercised.
        """
        def rx_on_write(text):
            if not text.strip().lower().startswith("s"):
                return []
            return list(rx_script)

        nodes = {
            "RP2040-A": runner.MockSerialBackend(boot_lines=["READY"],
                                                 on_write=rx_on_write),
            "ESP32-B": runner.MockSerialBackend(boot_lines=["READY"],
                                                on_write=rx_on_write),
            "ESP32-C": runner.MockSerialBackend(boot_lines=["READY"],
                                                on_write=rx_on_write),
        }
        node_ports = {n: n for n in nodes}
        factory = runner.mock_backend_factory(nodes)
        return runner.Phase1Runner(
            node_ports=node_ports, backend_factory=factory, baud=115200,
            timeout_s=2.0, logger=lambda _m: None), nodes

    def _script(self, runner, n=480, base_rssi=-75.0, drop=0):
        """Canonical RX script: header + n packets + RESULT, with `drop` gaps."""
        lines = ["pkt,seq,rssi,snr,irq_us,read_us,clr_us,rx_us,total_us"]
        seq = 0
        emitted = 0
        while emitted < n:
            if drop and emitted and emitted % (100 // max(drop, 1)) == 0:
                seq += 1  # simulate a lost sequence number
            rssi = base_rssi + (emitted % 5)
            lines.append(f"{emitted+1},{seq},{rssi:.1f},8.0,10,60,30,40,140")
            seq += 1
            emitted += 1
        lines.append(f"RESULT,{n},{n},0,0,2600.0,140,140.0,140")
        return lines


class TestOrchestration(_MockOrchestrationMixin):
    @pytest.mark.simulate
    def test_single_tx_rx_mode_1A(self, runner, tmp_path):
        r_inst, _nodes = self._runner_with_mocks(runner, self._script(runner, n=480))
        mode = runner.TEST_MODES["1A"]
        res = r_inst.run_mode(mode)
        assert res.ok
        assert res.stats.unique_seqs == 480
        assert res.stats.packet_loss_pct == pytest.approx(4.0)  # 20 of 500 lost
        assert res.stats.rssi_avg is not None
        # CSV + JSON outputs.
        csv_path = runner.write_mode_csv(res, tmp_path)
        assert csv_path.exists()
        summary = runner.write_summary_json([res], tmp_path)
        data = json.loads(summary.read_text())
        assert "1A" in data["modes"]
        assert data["modes"]["1A"]["stats"]["packet_loss_pct"] == pytest.approx(4.0)

    @pytest.mark.simulate
    def test_dual_rx_mode_1F_merges_packets(self, runner):
        # Both RX nodes emit the same script -> merged packet count doubles,
        # but unique seqs stay at n (duplicates across receivers).
        r_inst, _nodes = self._runner_with_mocks(runner, self._script(runner, n=500))
        mode = runner.TEST_MODES["1F"]  # ESP32-B TX -> A+C RX
        res = r_inst.run_mode(mode)
        assert res.ok
        assert res.stats.packets_received == 1000  # 500 per RX node
        assert res.stats.unique_seqs == 500        # deduped by seq
        assert res.stats.duplicates == 500
        assert res.stats.packet_loss_pct == 0.0

    @pytest.mark.simulate
    def test_dual_tx_mode_1C_staggered(self, runner):
        r_inst, _nodes = self._runner_with_mocks(runner, self._script(runner, n=500))
        mode = runner.TEST_MODES["1C"]  # B+C TX -> A RX
        res = r_inst.run_mode(mode)
        assert res.ok
        # RP2040-A is the only RX; receives 500 packets.
        assert res.stats.packets_received == 500
        assert res.mode == "1C"
        assert set(res.tx_nodes) == {"ESP32-B", "ESP32-C"}

    @pytest.mark.simulate
    def test_csv_footer_has_stats(self, runner, tmp_path):
        r_inst, _nodes = self._runner_with_mocks(runner, self._script(runner, n=500))
        res = r_inst.run_mode(runner.TEST_MODES["1E"])
        csv_path = runner.write_mode_csv(res, tmp_path)
        text = csv_path.read_text()
        lines = text.splitlines()
        # The header is this file's own per-packet schema (runner.CSV_FIELDS):
        # its first column is "index" (the receiver-side arrival index), which
        # is a different quantity from "seq" (the transmitter's sequence
        # number).  "pkt,seq,rssi,..." is the *firmware* output dialect that
        # parse_packet_line consumes (and explicitly rejects as a non-packet
        # line) -- it is not the header of this CSV.
        assert lines[0] == ",".join(runner.CSV_FIELDS)
        assert "index,seq,rssi" in lines[0]
        assert "# packet_loss_pct" in text
        assert "# rssi_avg" in text
        # Footer stat lines parse as "# key,value".
        footer = {}
        for ln in lines:
            if ln.startswith("# ") and "," in ln:
                k, _, v = ln[2:].partition(",")
                footer[k] = v
        assert int(footer["packets_received"]) == 500
        assert int(footer["unique_seqs"]) == 500
        assert float(footer["packet_loss_pct"]) == pytest.approx(0.0)  # 0% loss
        assert float(footer["rssi_avg"]) == pytest.approx(-73.0)


# --------------------------------------------------------------------------- #
# Config loading
# --------------------------------------------------------------------------- #
class TestConfig:
    @pytest.mark.simulate
    def test_json_fallback_without_yaml(self, runner, tmp_path, monkeypatch):
        # Force YAML unavailable path even if pyyaml is installed.
        monkeypatch.setattr(runner, "_yaml", None)
        cfg_path = tmp_path / "cfg.json"
        cfg_path.write_text(json.dumps({
            "baud": 230400,
            "nodes": {"ESP32-B": "/dev/ttyACM3"},
        }))
        cfg = runner.load_config(cfg_path)
        assert cfg["baud"] == 230400
        assert cfg["nodes"]["ESP32-B"] == "/dev/ttyACM3"

    @pytest.mark.simulate
    def test_none_config_defaults(self, runner):
        cfg = runner.load_config(None)
        assert cfg["baud"] == 115200
        assert cfg["nodes"] == {}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
class TestCLI:
    @pytest.mark.simulate
    def test_list_modes(self, runner, capsys):
        rc = runner.main(["--list-modes"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "1A" in out and "1F" in out
        assert "ESP32-B" in out

    @pytest.mark.simulate
    def test_mock_all_writes_outputs(self, runner, tmp_path, capsys):
        rc = runner.main(["--mock", "--all", "--out", str(tmp_path)])
        out = capsys.readouterr().out
        assert rc == 0, out
        # 6 per-mode CSVs + summary.json.
        csvs = list(tmp_path.glob("test-*.csv"))
        assert len(csvs) == 6
        assert (tmp_path / "summary.json").exists()
        summary = json.loads((tmp_path / "summary.json").read_text())
        assert set(summary["modes"]) == {"1A", "1B", "1C", "1D", "1E", "1F"}
        assert "6/6 modes completed" in out

    @pytest.mark.simulate
    def test_mock_single_mode(self, runner, tmp_path):
        rc = runner.main(["--mock", "--mode", "1D", "--out", str(tmp_path)])
        assert rc == 0
        assert (tmp_path / "test-1D.csv").exists()
        assert (tmp_path / "summary.json").exists()


# --------------------------------------------------------------------------- #
# Regression locks (2026-10-07 suite triage)
#
# These three defects were invisible while the suite could not run as a whole
# (two collection-time defects destroyed the run before 1351ed2). Each test
# below fails against the pre-triage code and locks the fix in.
# --------------------------------------------------------------------------- #
class TestRegressions(_MockOrchestrationMixin):
    @pytest.mark.simulate
    def test_result_line_never_invents_a_record_from_garbage(self, runner):
        """BUG 1: parse_result_line accepted garbage and invented a dict.

        ``parse_result_line("RESULT,garbage")`` returned ``{"received": None}``
        instead of ``None``: the positional branch zipped the key list against
        whatever tokens were present and stored ``None`` for each unparseable
        one, so *any* malformed line was reported as a result footer.
        """
        for line in [
            "RESULT,garbage",
            "RESULT,x,y,z",
            "RESULT,500,garbage",           # partially numeric
            "RESULT,status=ok",             # no numeric field at all
            "RESULT,received=notanumber",
        ]:
            assert runner.parse_result_line(line) is None, line

        # Well-formed footers (both dialects) must still parse, and the values
        # must still be typed as before (ints for counts/timing, floats for
        # throughput/avg).
        pos = runner.parse_result_line("RESULT,500,498,2,0,2600.0,140,141.2,143")
        assert pos is not None and pos["received"] == 500
        assert isinstance(pos["received"], int) and isinstance(pos["unique"], int)
        assert pos["avg_us"] == 141.2
        kv = runner.parse_result_line("RESULT,received=100,loss_pct=2.5")
        assert kv == {"received": 100.0, "loss_pct": 2.5}
        # A float-formatted timing field is still a valid footer.
        assert runner.parse_result_line("RESULT,5,5,0,0,2600,140.0,140.0,143.0")

    @pytest.mark.simulate
    def test_dual_rx_merge_sums_both_receivers(self, runner):
        """BUG 2: mode 1F must merge packets from *both* RX nodes.

        Two receivers hearing the same 500-packet transmission each report the
        same 500 seqs, so the merged tally is 1000 received / 500 unique / 500
        duplicates.  The mock fixture used to leave the second RX node with a
        no-op ``on_write``, so the merge was never exercised and the mode
        silently reported half the traffic.
        """
        r_inst, _nodes = self._runner_with_mocks(runner, self._script(runner, n=500))
        res = r_inst.run_mode(runner.TEST_MODES["1F"])
        assert res.ok
        assert res.mode == "1F"
        assert set(res.rx_nodes) == {"RP2040-A", "ESP32-C"}
        assert res.stats.packets_received == 1000
        assert res.stats.unique_seqs == 500
        assert res.stats.duplicates == 500
        assert res.stats.packet_loss_pct == 0.0
        assert len(res.packets) == 1000
        # Both receivers' contributions must be individually visible, so a
        # silent/dead RX node can never hide behind the aggregate again.
        per_node = {}
        for n in res.rx_nodes:
            prefixed = [ln for ln in res.raw_log if ln.startswith(f"[{n}] ")]
            parsed = [runner.parse_packet_line(ln.split("] ", 1)[1])
                      for ln in prefixed]
            per_node[n] = sum(1 for p in parsed if p is not None)
        assert per_node == {"RP2040-A": 500, "ESP32-C": 500}

    @pytest.mark.simulate
    def test_single_rx_mode_is_not_double_counted(self, runner):
        """Guard for BUG 2's fix: a one-receiver mode must not sum twice."""
        r_inst, _nodes = self._runner_with_mocks(runner, self._script(runner, n=500))
        res = r_inst.run_mode(runner.TEST_MODES["1A"])  # ESP32-B TX -> RP2040-A RX
        assert res.stats.packets_received == 500
        assert res.stats.unique_seqs == 500
        assert res.stats.duplicates == 0
        assert [ln for ln in res.raw_log if not ln.startswith("[RP2040-A] ")] == []

    @pytest.mark.simulate
    def test_csv_header_and_footer_are_the_runner_schema(self, runner, tmp_path):
        """BUG 3: the CSV header/footer contract is the runner's own schema.

        The stale assertion expected the firmware dialect header
        (``pkt,seq,rssi``) in the runner's output CSV, whose first column is
        ``index`` (runner.CSV_FIELDS).  Lock the real contract, and the footer
        values, in place.
        """
        r_inst, _nodes = self._runner_with_mocks(runner, self._script(runner, n=500))
        res = r_inst.run_mode(runner.TEST_MODES["1A"])
        path = runner.write_mode_csv(res, tmp_path)
        lines = path.read_text().splitlines()
        assert lines[0] == ",".join(runner.CSV_FIELDS)

        footer = {}
        for ln in lines:
            if ln.startswith("# ") and "," in ln:
                k, _, v = ln[2:].partition(",")
                footer[k] = v
        s = res.stats
        assert int(footer["packets_received"]) == s.packets_received == 500
        assert int(footer["unique_seqs"]) == s.unique_seqs == 500
        assert int(footer["duplicates"]) == s.duplicates == 0
        assert int(footer["expected_packets"]) == s.expected_packets == 500
        assert float(footer["packet_loss_pct"]) == pytest.approx(s.packet_loss_pct)
        # One CSV data row per parsed packet.
        data_rows = [ln for ln in lines if ln and not ln.startswith("#")][1:]
        assert len(data_rows) == len(res.packets) == 500
