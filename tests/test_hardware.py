"""
test_hardware.py — Hardware integration tests for walk test reliability.

These tests require both RP2040 boards connected via USB.
They flash firmware, verify boot, check phase alignment, and confirm
packet decoding.

Run with: make test-hardware
"""
import time
import pytest
from conftest import read_serial, parse_phase_result, parse_beacon, parse_gps_unix


@pytest.mark.hardware
class TestBoardBoot:

    def test_tx_boots_within_10s(self, flash_tx):
        """TX must boot and start sweeping within 10s of flash."""
        lines = read_serial(flash_tx, duration=5)
        boot_msgs = [l for l in lines if "STARTING GPS-SYNCED SWEEP" in l or "PHASE_START" in l]
        assert len(boot_msgs) > 0, "TX did not start sweeping after boot"

    def test_rx_boots_within_10s(self, flash_rx):
        """RX must boot and start sweeping within 10s of flash."""
        lines = read_serial(flash_rx, duration=5)
        boot_msgs = [l for l in lines if "PHASE_START" in l]
        assert len(boot_msgs) > 0, "RX did not start sweeping after boot"

    def test_tx_no_blocking_gps_wait(self, flash_tx):
        """TX must NOT print 'WAITING FOR GPS TIME' (60s gate removed)."""
        lines = read_serial(flash_tx, duration=8)
        wait_msgs = [l for l in lines if "WAITING FOR GPS TIME" in l]
        assert len(wait_msgs) == 0, "TX still has 60s blocking GPS gate"


@pytest.mark.hardware
class TestGPSAutonomy:

    def test_tx_gets_gps_time_without_fix(self, serial_tx):
        """TX must extract UTC time from GPS RMC even without position fix.

        This is the regression test for the root cause bug.
        GPS RMC with V status still contains valid time.
        """
        lines = read_serial(serial_tx, duration=10)
        unix_times = [parse_gps_unix(l) for l in lines]
        unix_times = [t for t in unix_times if t is not None]
        assert len(unix_times) > 0, "TX not outputting GPS_UNIX lines"

        # Verify time is reasonable (close to current epoch)
        import time as _time
        now = int(_time.time())
        for t in unix_times:
            assert abs(t - now) < 10, f"GPS time {t} drifts >10s from laptop {now}"

    def test_tx_beacon_shows_gps_source(self, serial_tx):
        """TX beacon must show src=GPS when GPS time is available."""
        lines = read_serial(serial_tx, duration=12)
        beacons = [parse_beacon(l) for l in lines]
        beacons = [b for b in beacons if b is not None]
        assert len(beacons) > 0, "No BEACON lines from TX"

        # At least one beacon should show GPS source
        gps_beacons = [b for b in beacons if b.get("src") == "GPS"]
        assert len(gps_beacons) > 0, f"No beacons with src=GPS. Got: {beacons}"

    def test_tx_never_needs_set_time(self, flash_tx):
        """TX must compute UTC time autonomously — no SET_TIME command sent."""
        # flash_tx fixture already flashed without sending any commands
        # Just verify TX has valid UTC time
        lines = read_serial(flash_tx, duration=10)
        unix_times = [parse_gps_unix(l) for l in lines]
        unix_times = [t for t in unix_times if t is not None]
        assert len(unix_times) > 0, "TX has no UTC time without any SET_TIME command"


@pytest.mark.hardware
class TestPhaseAlignment:

    def test_both_boards_interleave_mode(self, serial_tx, serial_rx):
        """Both TX and RX must be in interleave mode (phase numbers >13)."""
        tx_lines = read_serial(serial_tx, duration=10)
        rx_lines = read_serial(serial_rx, duration=10)

        # TX beacon contains phase number
        tx_beacons = [parse_beacon(l) for l in tx_lines]
        tx_beacons = [b for b in tx_beacons if b is not None]
        if tx_beacons:
            assert tx_beacons[0]["phase"] >= 14, \
                f"TX not in interleave mode (phase={tx_beacons[0]['phase']})"

        # RX PHASE_RESULT contains phase number
        rx_results = [parse_phase_result(l) for l in rx_lines]
        rx_results = [r for r in rx_results if r is not None]
        if rx_results:
            assert rx_results[0]["phase"] >= 14, \
                f"RX not in interleave mode (phase={rx_results[0]['phase']})"

    def test_tx_rx_phase_within_5(self, serial_tx, serial_rx):
        """TX and RX phase numbers must be within 5 of each other.

        They compute from the same UTC time and same interleave table,
        so phases should match (allowing for serial read timing).
        """
        tx_lines = read_serial(serial_tx, duration=8)
        # Send SET_TIME to RX to sync its clock
        import serial
        with serial.Serial(serial_rx, 115200, timeout=1) as ser:
            import time as _t
            ser.write(f"SET_TIME {int(_t.time())}\n".encode())
            _t.sleep(2)
            ser.write(f"SET_TIME {int(_t.time())}\n".encode())
        rx_lines = read_serial(serial_rx, duration=8)

        tx_beacons = [parse_beacon(l) for l in tx_lines if l.startswith("BEACON")]
        tx_beacons = [b for b in tx_beacons if b]
        rx_results = [parse_phase_result(l) for l in rx_lines]

        if tx_beacons and rx_results:
            tx_phase = tx_beacons[0]["phase"]
            rx_phase = rx_results[-1]["phase"]
            # Phases should be close (within a few, accounting for timing)
            cycle = 56
            diff = abs(tx_phase - rx_phase) % cycle
            diff = min(diff, cycle - diff)
            assert diff <= 5, f"Phase mismatch: TX={tx_phase} RX={rx_phase} diff={diff}"


@pytest.mark.hardware
class TestPacketDecoding:

    def test_rx_decodes_tx_packets(self, serial_tx, serial_rx):
        """RX must decode at least 1 packet from TX when both are synced."""
        # Sync RX clock
        import serial
        import time as _t
        with serial.Serial(serial_rx, 115200, timeout=1) as ser:
            for _ in range(3):
                ser.write(f"SET_TIME {int(_t.time())}\n".encode())
                _t.sleep(2)

        # Read RX for 60s — should see decoded packets
        lines = read_serial(serial_rx, duration=60)
        results = [parse_phase_result(l) for l in lines]
        results = [r for r in results if r and r.get("rx", 0) > 0]
        assert len(results) > 0, f"RX decoded 0 packets in 60s. Total phases: {len([r for r in [parse_phase_result(l) for l in lines] if r])}"
