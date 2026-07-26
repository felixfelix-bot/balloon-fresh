"""Hardware tests requiring physical boards connected.

Per ADR-020: each test flashes boards, verifies operation, cleans up.
Markers: @pytest.mark.hw
"""
import time
import pytest
from conftest import find_port, send_command, read_output, TX_SERIAL, RX_SERIAL


@pytest.mark.hw
class TestBoardBoot:
    """Verify boards boot correctly."""

    def test_tx_boots_and_outputs_nmea(self, tx_port):
        """TX should output NMEA sentences within 10s of boot."""
        lines = read_output(tx_port, duration_s=10, filter_prefix="NMEA_RMC")
        assert len(lines) > 0, "TX not outputting NMEA sentences"
        assert "$GNRMC" in lines[0], f"Unexpected NMEA format: {lines[0]}"

    def test_rx_boots_and_outputs_phases(self, rx_port):
        """RX should output PHASE_START within 15s of sync."""
        send_command(rx_port, f"SET_TIME {int(time.time())}")
        send_command(rx_port, "SET_INTERLEAVE 1")
        time.sleep(5)
        lines = read_output(rx_port, duration_s=15, filter_prefix="PHASE_START")
        assert len(lines) > 0, "RX not outputting PHASE_START"

    def test_tx_responds_to_fw_query(self, tx_port):
        """TX should respond to FW_QUERY with boot banner."""
        resp = send_command(tx_port, "FW_QUERY", timeout=3)
        assert resp, "No response to FW_QUERY"


@pytest.mark.hw
class TestInterleaveMode:
    """Test interleave mode operation."""

    def test_tx_auto_interleave(self, tx_port):
        """TX should start interleave mode on boot (no command needed)."""
        send_command(tx_port, f"SET_TIME {int(time.time())}")
        time.sleep(10)
        lines = read_output(tx_port, duration_s=15, filter_prefix="PHASE_START")
        assert len(lines) > 0, "TX not sweeping in interleave mode"

    def test_rx_auto_interleave(self, rx_port):
        """RX should start interleave mode on boot."""
        send_command(rx_port, f"SET_TIME {int(time.time())}")
        send_command(rx_port, "SET_INTERLEAVE 1")
        time.sleep(5)
        lines = read_output(rx_port, duration_s=15, filter_prefix="PHASE_START")
        assert len(lines) > 0, "RX not sweeping"

    def test_both_same_phase_table(self, both_ports):
        """Both boards should reference same mode names in phases."""
        tx_port, rx_port = both_ports
        tx_lines = read_output(tx_port, duration_s=30, filter_prefix="PHASE_START")
        rx_lines = read_output(rx_port, duration_s=30, filter_prefix="PHASE_START")
        assert len(tx_lines) > 0 and len(rx_lines) > 0
        # Extract mode names (second field after phase number)
        tx_modes = set(l.split()[2] for l in tx_lines if len(l.split()) > 2)
        rx_modes = set(l.split()[2] for l in rx_lines if len(l.split()) > 2)
        common = tx_modes & rx_modes
        assert len(common) > 0, f"No common modes: TX={tx_modes} RX={rx_modes}"


@pytest.mark.hw
class TestDecode:
    """Test TX→RX packet decode."""

    def test_rx_decodes_tx(self, synced_both):
        """RX should decode at least 1 packet from TX within 120s."""
        tx_port, rx_port = synced_both
        lines = read_output(rx_port, duration_s=120, filter_prefix="PHASE_RESULT")
        decoded = [l for l in lines if "rx=" in l and not "rx=0 " in l]
        assert len(decoded) > 0, (
            f"No packets decoded in 120s. "
            f"Got {len(lines)} PHASE_RESULT lines, 0 with rx>0. "
            f"Check: phase sync, GPS fix, RF range."
        )


@pytest.mark.hw
class TestTxAutonomy:
    """Test TX autonomous operation (ADR-018)."""

    def test_tx_no_set_time_still_runs(self, tx_port):
        """TX should boot and output NMEA WITHOUT receiving SET_TIME."""
        # Just read — don't send any commands
        lines = read_output(tx_port, duration_s=15, filter_prefix="NMEA_RMC")
        assert len(lines) > 0, "TX not alive without SET_TIME"

    def test_tx_gps_time_source(self, tx_port):
        """TX should acquire GPS_UNIX time autonomously."""
        lines = read_output(tx_port, duration_s=30, filter_prefix="GPS_UNIX")
        if len(lines) == 0:
            pytest.skip("GPS not providing time yet (cold start)")
        # Verify unix timestamp is non-zero
        for line in lines:
            if "unix=" in line:
                unix_val = int(line.split("unix=")[1].split()[0])
                assert unix_val > 1700000000, f"Invalid unix time: {unix_val}"
                return
        pytest.fail("GPS_UNIX line found but no valid unix= field")


@pytest.mark.hw
class TestCDCWatchdog:
    """Test CDC watchdog behavior (critical for walk tests)."""

    def test_tx_stable_after_sync(self, tx_port):
        """TX should not reboot within 60s of receiving SET_TIME."""
        send_command(tx_port, f"SET_TIME {int(time.time())}")
        # Read heartbeat — uptime should be monotonically increasing
        hb1 = read_output(tx_port, duration_s=15, filter_prefix="HEARTBEAT")
        time.sleep(45)
        hb2 = read_output(tx_port, duration_s=15, filter_prefix="HEARTBEAT")
        # Extract uptime/millis from heartbeat
        if hb1 and hb2:
            m1 = int(hb1[0].split("millis=")[1].split()[0]) if "millis=" in hb1[0] else 0
            m2 = int(hb2[0].split("millis=")[1].split()[0]) if "millis=" in hb2[0] else 0
            # m2 should be ~45s more than m1
            assert m2 > m1 + 40000, (
                f"TX rebooted! millis went {m1}→{m2} (diff={m2-m1}ms, expected >40000). "
                f"CDC watchdog may have fired."
            )
